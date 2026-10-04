# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Retrieve the ground-mounted PV plants and the grid substations of Wallonia
from OpenStreetMap.

The Region publishes no register of ground-mounted PV parks (no count exists
at CWaPE or SPW Énergie either).  OSM maps them as areas: a ``power=plant``
with ``plant:source=solar`` around a whole park, and ``power=generator`` with
``generator:source=solar`` around each block of tables.  Rooftop systems are
also mapped as generators; they are dropped here (``location=roof``, a
``building`` tag, or less than ``MIN_HA``), since the study is about land.

The plants are used only to *test* the constraint set and to measure the
capacity density Walloon parks are actually built at --- never as an input to
the potential --- so an incomplete inventory is acceptable and is reported as
such.

Substations (``power=substation``, with their voltage) are written for the
grid-distance sensitivity.
"""

import json
import logging
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union

logger = logging.getLogger(__name__)

# overpass.private.coffee answers the area query with zero elements (its
# area index is stale), so an empty answer counts as a failure below.
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
ATTEMPTS = 4
BACKOFF = 20.0
MIN_HA = 0.2
# The Region's own boundary relation, not a bounding box: a box around
# Wallonia takes in most of Flanders' tens of thousands of mapped rooftops and
# times the public servers out.
AREA = 'area["ISO3166-2"="BE-WAL"]->.w;'
QUERIES = {
    "pv": (
        "[out:json][timeout:600];" + AREA + "("
        'way["power"="plant"]["plant:source"="solar"](area.w);'
        'relation["power"="plant"]["plant:source"="solar"](area.w);'
        'way["power"="generator"]["generator:source"="solar"]'
        '[!"building"]["location"!~"roof"](area.w);'
        ");out tags geom;"
    ),
    "grid": (
        "[out:json][timeout:600];" + AREA + "("
        'node["power"="substation"](area.w);'
        'way["power"="substation"](area.w);'
        ");out tags center;"
    ),
}
PV_TAGS = ["power", "name", "operator", "plant:source", "generator:source",
           "plant:output:electricity", "generator:output:electricity", "location",
           "generator:method", "start_date", "landuse"]
GRID_TAGS = ["power", "substation", "voltage", "name", "operator"]


def overpass(query):
    last = None
    for attempt in range(ATTEMPTS):
        for endpoint in ENDPOINTS:
            try:
                r = requests.post(endpoint, data={"data": query}, timeout=700,
                                 headers={"User-Agent": "pypsa-wal PV land-eligibility workflow (ULiege)"})
                r.raise_for_status()
                payload = r.json()
                if not payload.get("elements"):
                    raise RuntimeError("empty answer")
                logger.info("served by %s (%d elements)", endpoint, len(payload["elements"]))
                return payload
            except Exception as exc:  # noqa: BLE001 - tried on the next mirror
                last = exc
                logger.warning("%s failed (%s)", endpoint, exc)
        time.sleep(BACKOFF * (attempt + 1))
    raise RuntimeError(f"no Overpass mirror answered: {last}")


def ring(coords):
    pts = [(p["lon"], p["lat"]) for p in coords]
    return Polygon(pts) if len(pts) >= 4 else None


def element_geometry(e):
    if e["type"] == "way":
        return ring(e.get("geometry") or [])
    # relation: outer rings minus inner rings (multipolygon of the simple kind)
    outer, inner = [], []
    for m in e.get("members", []):
        if m.get("type") != "way" or not m.get("geometry"):
            continue
        p = ring(m["geometry"])
        if p is None:
            continue
        (inner if m.get("role") == "inner" else outer).append(p)
    if not outer:
        return None
    g = unary_union([p.buffer(0) for p in outer])
    if inner:
        g = g.difference(unary_union([p.buffer(0) for p in inner]))
    return g


def parse_mw(v):
    """'12 MW', '750 kW', '4.5MWp' -> MW (None if unparseable)."""
    if not v or not isinstance(v, str):
        return None
    s = v.strip().lower().replace(",", ".").replace("wp", "w").replace(" ", "")
    for unit, f in (("gw", 1e3), ("mw", 1.0), ("kw", 1e-3), ("w", 1e-6)):
        if s.endswith(unit):
            try:
                return float(s[: -len(unit)]) * f
            except ValueError:
                return None
    return None


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=open(snakemake.log[0], "w"))  # noqa: SIM115

    crs = snakemake.params.crs
    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    admin = regions[regions["name"] == "admin"].geometry.union_all()

    rows = []
    for e in overpass(QUERIES["pv"])["elements"]:
        g = element_geometry(e)
        if g is None or g.is_empty:
            continue
        t = e.get("tags", {})
        rows.append({"osm_type": e["type"], "osm_id": e["id"],
                     **{k: t.get(k) for k in PV_TAGS}, "geometry": g.buffer(0)})
    pv = gpd.GeoDataFrame(rows, crs=4326).to_crs(crs)
    pv = pv[pv.representative_point().within(admin)].copy()
    pv["area_ha"] = pv.area / 1e4
    pv["kind"] = pv["power"].map({"plant": "plant", "generator": "generator"})
    pv["mw_tag"] = [parse_mw(a) if parse_mw(a) is not None else parse_mw(b)
                    for a, b in zip(pv["plant:output:electricity"],
                                    pv["generator:output:electricity"])]

    # A generator that lies inside a mapped plant is part of it: keep the plant
    # outline, which is the fenced park, and drop its blocks.
    plants = pv[pv["kind"] == "plant"]
    gens = pv[pv["kind"] == "generator"]
    if len(plants) and len(gens):
        inside = gpd.sjoin(gens[["geometry"]].set_geometry(gens.representative_point()),
                           plants[["geometry"]], predicate="within").index.unique()
        gens = gens.drop(index=inside)
    # Free-standing generator blocks closer than 30 m to each other are one park.
    if len(gens):
        merged = gens.buffer(15).union_all().buffer(-15)
        parts = list(merged.geoms) if isinstance(merged, MultiPolygon) else [merged]
        g2 = gpd.GeoDataFrame(geometry=parts, crs=crs)
        agg = gpd.sjoin(gens[["mw_tag", "name", "geometry"]], g2, predicate="intersects")
        mw = agg.groupby("index_right")["mw_tag"].sum(min_count=1)
        name = agg.groupby("index_right")["name"].first()
        g2["mw_tag"] = mw
        g2["name"] = name
        g2["kind"] = "generator_cluster"
    else:
        g2 = gpd.GeoDataFrame(columns=["geometry", "mw_tag", "name", "kind"], crs=crs)
    parks = pd.concat([plants[["kind", "name", "operator", "mw_tag", "start_date", "geometry"]],
                       g2[["kind", "name", "mw_tag", "geometry"]]], ignore_index=True)
    parks = gpd.GeoDataFrame(parks, crs=crs)
    parks["area_ha"] = parks.area / 1e4
    parks = parks[parks["area_ha"] >= MIN_HA].reset_index(drop=True)
    parks.to_file(snakemake.output.pv, driver="GPKG", layer="data")
    logger.info("%d ground-mounted PV parks >= %.1f ha, %.0f ha in all, %d with a "
                "capacity tag", len(parks), MIN_HA, parks["area_ha"].sum(),
                int(parks["mw_tag"].notna().sum()))

    srows = []
    for e in overpass(QUERIES["grid"])["elements"]:
        c = e.get("center") or ({"lat": e["lat"], "lon": e["lon"]} if "lat" in e else None)
        if not c:
            continue
        t = e.get("tags", {})
        srows.append({"osm_id": e["id"], **{k: t.get(k) for k in GRID_TAGS},
                      "geometry": Point(c["lon"], c["lat"])})
    subs = gpd.GeoDataFrame(srows, crs=4326).to_crs(crs)
    subs = subs[subs.within(admin.buffer(5000))].reset_index(drop=True)
    kv = subs["voltage"].fillna("").str.split(";").map(
        lambda xs: max([float(x) for x in xs if x.strip().isdigit()] or [0]) / 1e3)
    subs["max_kv"] = kv
    subs.to_file(snakemake.output.grid, driver="GPKG", layer="data")
    logger.info("%d substations (%d at 30 kV or more)", len(subs), int((kv >= 30).sum()))

    meta = {
        "source": "OpenStreetMap via Overpass API", "licence": "ODbL 1.0",
        "retrieved": time.strftime("%Y-%m-%d"),
        "pv_parks": int(len(parks)), "pv_area_ha": round(float(parks["area_ha"].sum()), 1),
        "pv_with_capacity_tag": int(parks["mw_tag"].notna().sum()),
        "substations": int(len(subs)),
        "min_park_ha": MIN_HA,
    }
    Path(snakemake.output.meta).write_text(json.dumps(meta, indent=2))
