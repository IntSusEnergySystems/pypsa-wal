# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Retrieve the positions of the standing Walloon wind turbines from OpenStreetMap.

The Walloon Region does not publish turbine coordinates as open data.  OSM does:
every large machine in Belgium carries ``power=generator`` with
``generator:source=wind``, mapped from orthophotos, and the coverage of the
Walloon fleet is essentially complete.  The positions are used only to *test*
the constraint set --- they are never an input to the potential --- so an
imperfect inventory is acceptable and its incompleteness is reported.
"""

import json
import logging
import time
from pathlib import Path

import geopandas as gpd
import requests

logger = logging.getLogger(__name__)

# Overpass instances rate-limit and time out under load; the query is tried on
# each mirror in turn, with a backoff, before the rule is allowed to fail.
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
]
ATTEMPTS = 3
BACKOFF = 20.0
# Bounding box comfortably around Wallonia; the result is clipped afterwards.
BBOX = (49.4, 2.7, 50.9, 6.5)
QUERY = (
    "[out:json][timeout:180];"
    "(node({0},{1},{2},{3})[\"generator:source\"=\"wind\"];"
    "way({0},{1},{2},{3})[\"generator:source\"=\"wind\"];);"
    "out center;"
).format(*BBOX)


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    crs = snakemake.params.crs
    # Overpass rejects a urlencoded POST body from some clients; a GET with the
    # query as a parameter is accepted everywhere.
    payload = None
    last = None
    for attempt in range(ATTEMPTS):
        for endpoint in ENDPOINTS:
            try:
                r = requests.get(
                    endpoint,
                    params={"data": QUERY},
                    timeout=300,
                    headers={"User-Agent": "pypsa-wal onwind land-eligibility workflow"},
                )
                r.raise_for_status()
                payload = r.json()
                logger.info("served by %s", endpoint)
                break
            except Exception as exc:  # noqa: BLE001 - tried on the next mirror
                last = exc
                logger.warning("%s failed (%s)", endpoint, exc)
        if payload is not None:
            break
        time.sleep(BACKOFF * (attempt + 1))
    if payload is None:
        raise RuntimeError(f"no Overpass mirror answered: {last}")
    elements = payload["elements"]
    logger.info("%d wind generators in the bounding box", len(elements))

    lats, lons, ids = [], [], []
    for e in elements:
        lat = e.get("lat", (e.get("center") or {}).get("lat"))
        lon = e.get("lon", (e.get("center") or {}).get("lon"))
        if lat is None or lon is None:
            continue
        lats.append(lat)
        lons.append(lon)
        ids.append(f"{e['type']}/{e['id']}")

    pts = gpd.GeoDataFrame(
        {"osm_id": ids}, geometry=gpd.points_from_xy(lons, lats), crs=4326
    ).to_crs(crs)

    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    admin = regions[regions["name"] == "admin"].geometry.union_all()
    inside = pts[pts.within(admin)].reset_index(drop=True)
    logger.info("%d of them inside the Walloon Region", len(inside))

    inside.to_file(snakemake.output.points, driver="GPKG", layer="data")
    Path(snakemake.output.meta).write_text(
        json.dumps(
            {
                "source": "OpenStreetMap via Overpass API",
                "licence": "ODbL 1.0",
                "query": QUERY,
                "features_in_bbox": len(elements),
                "features_in_wallonia": int(len(inside)),
            },
            indent=2,
        )
    )
