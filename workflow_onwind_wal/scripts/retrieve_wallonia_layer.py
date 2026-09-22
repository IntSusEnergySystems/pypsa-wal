# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Download one layer of the Walloon ESRI-REST geoservices into a GeoPackage.

The Géoportail de la Wallonie publishes every reference dataset used by this
workflow as an ArcGIS ``MapServer`` with ``Query`` capability, under a CC-BY 4.0
licence.  The servers cap a single response at ``maxRecordCount`` features
(2 000 for all layers used here), so the download is paginated with
``resultOffset`` / ``resultRecordCount``.

The output is written in EPSG:31370 (Belgian Lambert 72), the native CRS of the
source data, and re-projected downstream.  Downloads are idempotent: snakemake
marks them ``protected`` so a re-run does not hit the servers again.
"""

import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import shape

logger = logging.getLogger(__name__)

BASE = "https://geoservices.wallonie.be/arcgis/rest/services"
SRS = 31370
RETRIES = 4
BACKOFF = 5.0


def _page(session, url, params, offset, page_size):
    """Fetch one page of features, retrying on transient failures."""
    q = dict(params)
    q.update(resultOffset=offset, resultRecordCount=page_size)
    last = None
    for attempt in range(RETRIES):
        try:
            r = session.get(url, params=q, timeout=180)
            r.raise_for_status()
            payload = r.json()
            if "error" in payload:
                raise RuntimeError(payload["error"])
            return payload.get("features", [])
        except Exception as exc:  # noqa: BLE001 - retried below
            last = exc
            logger.warning(
                "offset %d attempt %d/%d failed (%s)", offset, attempt + 1, RETRIES, exc
            )
            time.sleep(BACKOFF * (attempt + 1))
    raise RuntimeError(f"giving up on offset {offset}: {last}")


def download_layer(
    service, layer, fields, page_size=2000, workers=1, where="1=1", simplify=None
):
    url = f"{BASE}/{service}/MapServer/{layer}/query"
    session = requests.Session()

    params = {
        "where": where,
        "outFields": ",".join(fields) if fields else "OBJECTID",
        "returnGeometry": "true",
        "outSR": SRS,
        "f": "geojson",
    }
    if simplify:
        # Server-side generalisation, in map units (m).  Only ever used on
        # layers whose native precision is far finer than the 100 m exclusion
        # raster, so it cannot change the result.
        params["maxAllowableOffset"] = simplify

    count = session.get(
        url, params={"where": where, "returnCountOnly": "true", "f": "json"}, timeout=120
    ).json()["count"]
    logger.info("%s/%s: %d features", service, layer, count)

    offsets = list(range(0, count, page_size))
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pages = list(
                pool.map(lambda o: _page(session, url, params, o, page_size), offsets)
            )
    else:
        pages = [_page(session, url, params, o, page_size) for o in offsets]

    feats = [f for page in pages for f in page]
    if not feats:
        raise RuntimeError(f"{service}/{layer} returned no features")
    if len(feats) < count:
        # ArcGIS occasionally drops features whose geometry fails to serialise.
        logger.warning("expected %d features, got %d", count, len(feats))

    geoms, records = [], []
    for f in feats:
        if f.get("geometry") is None:
            continue
        geoms.append(shape(f["geometry"]))
        records.append(f.get("properties", {}))

    gdf = gpd.GeoDataFrame(
        pd.DataFrame.from_records(records), geometry=geoms, crs=f"EPSG:{SRS}"
    )
    return gdf, count


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    spec = snakemake.params.spec
    gdf, count = download_layer(
        spec["service"],
        spec["layer"],
        spec.get("fields") or [],
        page_size=spec.get("page_size", 2000),
        workers=spec.get("workers", 1),
        where=spec.get("where", "1=1"),
        simplify=spec.get("simplify"),
    )

    expected = spec.get("count")
    if expected is not None and abs(count - expected) / max(expected, 1) > 0.20:
        logger.warning(
            "feature count %d deviates by more than 20%% from the %d recorded "
            "in config.yaml — the upstream dataset has been revised, re-check "
            "the report before quoting it",
            count,
            expected,
        )

    out = Path(snakemake.output[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out, driver="GPKG", layer="data")

    meta = {
        "service": spec["service"],
        "layer": spec["layer"],
        "title": spec.get("title"),
        "where": spec.get("where", "1=1"),
        "url": f"{BASE}/{spec['service']}/MapServer/{spec['layer']}",
        "features_server": count,
        "features_written": int(len(gdf)),
        "crs": f"EPSG:{SRS}",
        "retrieved": time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "licence": "CC-BY 4.0, SPW — Géoportail de la Wallonie",
    }
    Path(snakemake.output[1]).write_text(json.dumps(meta, indent=2))
    logger.info("wrote %s (%d features)", out, len(gdf))
    sys.stderr.flush()
