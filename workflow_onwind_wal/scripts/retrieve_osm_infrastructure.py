# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Retrieve from OpenStreetMap the two pieces of transport infrastructure the
Walloon open data does not describe well enough.

``dual carriageways``
    The road part of the CoDT's main communication infrastructure (PIC,
    art. R.II.21-1) is "les autoroutes et les routes de liaisons régionales à
    deux fois deux bandes de circulation".  The plan-de-secteur road layer does
    not say how many lanes a road has, and most of its 5 393 km of "routes de
    liaison" are two-lane roads.  OSM does: a dual carriageway is drawn as two
    one-way ways.  Kept: every ``motorway``, every one-way ``trunk``, and every
    one-way ``primary``/``secondary`` with a limit of at least
    ``min_speed_kmh`` -- which drops urban one-way streets.

``high-speed lines``
    The 190 m railway distance applies to the high-speed network only
    (``railway=rail`` + ``highspeed=yes``); ordinary track takes 50 m.

Overpass instances rate-limit and time out under load; each query is tried on
each mirror in turn, with a backoff.
"""

import json
import logging
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString

logger = logging.getLogger(__name__)

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
ATTEMPTS = 4
BACKOFF = 20.0
BBOX = (49.4, 2.7, 50.9, 6.5)
QUERIES = {
    "roads": (
        "[out:json][timeout:300];("
        'way({0},{1},{2},{3})["highway"~"^(motorway|trunk)$"];'
        'way({0},{1},{2},{3})["highway"~"^(primary|secondary)$"]["oneway"="yes"];'
        ");out tags geom;"
    ).format(*BBOX),
    "hsl": (
        "[out:json][timeout:300];"
        '(way({0},{1},{2},{3})["railway"="rail"]["highspeed"="yes"];);'
        "out tags geom;"
    ).format(*BBOX),
}
TAGS = ["highway", "oneway", "lanes", "maxspeed", "ref", "name", "railway", "highspeed"]


def overpass(query):
    last = None
    for attempt in range(ATTEMPTS):
        for endpoint in ENDPOINTS:
            try:
                r = requests.get(
                    endpoint,
                    params={"data": query},
                    timeout=400,
                    headers={"User-Agent": "pypsa-wal onwind land-eligibility workflow"},
                )
                r.raise_for_status()
                logger.info("served by %s", endpoint)
                return r.json()
            except Exception as exc:  # noqa: BLE001 - tried on the next mirror
                last = exc
                logger.warning("%s failed (%s)", endpoint, exc)
        time.sleep(BACKOFF * (attempt + 1))
    raise RuntimeError(f"no Overpass mirror answered: {last}")


def to_frame(payload, crs):
    rows = []
    for e in payload["elements"]:
        g = e.get("geometry")
        if not g or len(g) < 2:
            continue
        t = e.get("tags", {})
        rows.append(
            {"osm_id": e["id"], **{k: t.get(k) for k in TAGS},
             "geometry": LineString([(p["lon"], p["lat"]) for p in g])}
        )
    return gpd.GeoDataFrame(rows, crs=4326).to_crs(crs)


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    crs = snakemake.params.crs
    min_speed = float(snakemake.params.min_speed_kmh)
    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    # A road just across the border still anchors a corridor inside Wallonia.
    area = regions[regions["name"] == "admin"].geometry.union_all().buffer(1500)

    meta = {"source": "OpenStreetMap via Overpass API", "licence": "ODbL 1.0"}
    roads = to_frame(overpass(QUERIES["roads"]), crs)
    speed = pd.to_numeric(roads["maxspeed"], errors="coerce")
    keep = (
        (roads["highway"] == "motorway")
        | ((roads["highway"] == "trunk") & (roads["oneway"] == "yes"))
        | (roads["highway"].isin(["primary", "secondary"]) & (roads["oneway"] == "yes")
           & (speed >= min_speed))
    )
    roads = roads[keep & roads.intersects(area)].reset_index(drop=True)
    roads["geometry"] = roads.geometry.intersection(area)
    roads.to_file(snakemake.output.roads, driver="GPKG", layer="data")
    km = (roads.length / 1e3).groupby(roads["highway"]).sum().round(0)
    logger.info("dual carriageways kept, km of carriageway: %s", km.to_dict())
    meta["dual_carriageway_km"] = {k: float(v) for k, v in km.items()}

    hsl = to_frame(overpass(QUERIES["hsl"]), crs)
    hsl = hsl[hsl.intersects(area)].reset_index(drop=True)
    hsl["geometry"] = hsl.geometry.intersection(area)
    hsl.to_file(snakemake.output.hsl, driver="GPKG", layer="data")
    meta["high_speed_track_km"] = round(float(hsl.length.sum() / 1e3), 1)
    logger.info("high-speed track: %.0f km", meta["high_speed_track_km"])
    meta["retrieved"] = time.strftime("%Y-%m-%d")
    Path(snakemake.output.meta).write_text(json.dumps(meta, indent=2))
