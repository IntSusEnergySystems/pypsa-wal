# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Build the two regions on which the potential is evaluated.

``admin``
    The Walloon Region as an administrative entity: the union of the 21 NUTS-3
    areas whose code starts with ``BE3``.  This is what the administration and
    the cabinet mean by "Wallonia", and the denominator of every published
    Walloon land statistic.

``model``
    The ``BEWAL`` onshore region of PyPSA-Wal.  PyPSA-Eur builds it by
    Voronoi-partitioning each country around its substations and clipping to the
    country shape, so it does **not** coincide with the administrative region:
    western Hainaut falls on the Flemish side of the partition.  ``p_nom_max``
    in the model applies to this region, not to the administrative one, so both
    have to be reported.

The difference between the two is written out as well, because its size is a
finding in its own right.
"""

import json
import logging
from pathlib import Path

import geopandas as gpd

logger = logging.getLogger(__name__)


def load_admin(path, prefixes):
    nuts = gpd.read_file(path)
    key = "index" if "index" in nuts.columns else nuts.columns[0]
    mask = nuts[key].astype(str).str.startswith(tuple(prefixes))
    sel = nuts[mask]
    if sel.empty:
        raise RuntimeError(f"no NUTS3 area matching {prefixes} in {path}")
    logger.info("administrative region from %d NUTS3 areas", len(sel))
    return gpd.GeoDataFrame(
        {"name": ["admin"]}, geometry=[sel.union_all()], crs=nuts.crs
    )


def load_model(path, name):
    regions = gpd.read_file(path)
    sel = regions[regions["name"] == name]
    if sel.empty:
        raise RuntimeError(f"region {name} not found in {path}")
    return gpd.GeoDataFrame(
        {"name": ["model"]}, geometry=[sel.union_all()], crs=regions.crs
    )


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    cfg = snakemake.params.region
    crs = snakemake.params.crs

    admin = load_admin(cfg["fallback_shapes"], cfg["fallback_prefix"])
    model = load_model(cfg["shapes"], cfg["name"])

    admin_m = admin.to_crs(crs)
    model_m = model.to_crs(crs)

    # The part of the administrative region that the model attributes to
    # another node, and the part of the model region that is not Walloon.
    outside = admin_m.union_all().difference(model_m.union_all())
    spill = model_m.union_all().difference(admin_m.union_all())

    out = Path(snakemake.output.regions)
    out.parent.mkdir(parents=True, exist_ok=True)
    gpd.GeoDataFrame(
        {"name": ["admin", "model"]},
        geometry=[admin_m.geometry.iloc[0], model_m.geometry.iloc[0]],
        crs=crs,
    ).set_index("name").to_file(out, driver="GPKG", layer="regions")

    gpd.GeoDataFrame(
        {"name": ["walloon_not_in_model", "model_not_walloon"]},
        geometry=[outside, spill],
        crs=crs,
    ).to_file(snakemake.output.mismatch, driver="GPKG", layer="mismatch")

    stats = {
        "admin_area_km2": round(admin_m.area.sum() / 1e6, 1),
        "model_area_km2": round(model_m.area.sum() / 1e6, 1),
        "walloon_area_outside_model_km2": round(outside.area / 1e6, 1),
        "model_area_outside_wallonia_km2": round(spill.area / 1e6, 1),
        "crs": f"EPSG:{crs}",
    }
    stats["model_coverage_pct"] = round(
        100 * stats["model_area_km2"] / stats["admin_area_km2"], 1
    )
    Path(snakemake.output.stats).write_text(json.dumps(stats, indent=2))
    logger.info("%s", json.dumps(stats))
