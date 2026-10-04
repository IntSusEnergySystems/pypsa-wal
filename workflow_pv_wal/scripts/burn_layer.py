# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Burn one vector layer onto the study grid.

A layer is one entry of ``config.layers`` (an exclusion) or of
``config.masks`` (a test behind a gisement).  It is read from one or several
downloads, filtered on attribute values, optionally reduced to features above
a minimum area, buffered feature by feature and rasterised: a cell is 1 when
its centre falls inside a (buffered) feature.

Nothing is unioned as a vector.  The wind study dissolved each layer into one
geometry before handing it to atlite, which on 44 000 plan-de-secteur polygons
needed the 124 GB of the home workstation; rasterising the features one by one
gives the same cells in a few hundred MB, because overlapping features simply
burn the same cell twice.

Point features (e.g. the CSIS caves when mapped as points) without a buffer
would burn a single cell; they are given the configured buffer or, failing
one, a 10 m radius so they are not lost between cell centres.
"""

import json
import logging
from pathlib import Path

# rasterio before geopandas: see workflow_onwind_wal/scripts/retrieve_slope_raster.py.
import rasterio
import geopandas as gpd
import numpy as np
from rasterio.features import rasterize
from rasterio.transform import Affine

logger = logging.getLogger(__name__)

CHUNK = 20000
POINT_RADIUS = 10.0


def read_source(path, crs, flt, min_area_ha, max_area_ha=None):
    gdf = gpd.read_file(path, layer="data")
    n0 = len(gdf)
    for field, values in (flt or {}).items():
        if field not in gdf.columns:
            raise KeyError(f"{path}: no field {field}; fields are {list(gdf.columns)}")
        vals = gdf[field].astype(str).str.strip()
        unknown = sorted(set(map(str, values)) - set(vals))
        if unknown:
            # A label that matches nothing silently drops a zone (the wind study
            # lost 148 km2 of extraction zoning that way): refuse it.
            raise ValueError(f"{path}: {field} has no value {unknown}; values are "
                             f"{sorted(set(vals))[:40]}")
        gdf = gdf[vals.isin([str(v) for v in values])]
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].to_crs(crs)
    if min_area_ha:
        gdf = gdf[gdf.area >= float(min_area_ha) * 1e4]
    if max_area_ha:
        gdf = gdf[gdf.area <= float(max_area_ha) * 1e4]
    logger.info("%s: %d of %d features kept", Path(path).name, len(gdf), n0)
    return gdf


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=open(snakemake.log[0], "w"))  # noqa: SIM115

    spec = snakemake.params.spec
    grid = json.loads(Path(snakemake.input.grid).read_text())
    crs = grid["crs"]
    transform = Affine(*grid["transform"])
    shape = (grid["height"], grid["width"])
    buffer_m = float(spec.get("buffer_m") or 0.0)

    items = spec["source"] if isinstance(spec["source"], list) else [spec["source"]]
    out = np.zeros(shape, dtype=np.uint8)
    n_feat = 0
    for item in items:
        name, flt = (item, spec.get("filter")) if isinstance(item, str) else (
            item["source"], item.get("filter"))
        gdf = read_source(snakemake.input.sources[items.index(item)], crs, flt,
                          spec.get("min_area_ha"), spec.get("max_area_ha"))
        geoms = gdf.geometry
        is_pt = geoms.geom_type.isin(["Point", "MultiPoint"])
        if buffer_m > 0:
            geoms = geoms.buffer(buffer_m)
        elif is_pt.any():
            geoms = geoms.where(~is_pt, geoms.buffer(POINT_RADIUS))
        geoms = geoms[~geoms.is_empty].values
        for i in range(0, len(geoms), CHUNK):
            rasterize(((g, 1) for g in geoms[i:i + CHUNK]), out=out, transform=transform,
                      default_value=1, dtype="uint8")
        n_feat += len(geoms)

    with rasterio.open(snakemake.input.region_mask) as src:
        region = src.read(1).astype(bool)
    out[~region] = 0
    cells = int(out.sum())
    with rasterio.open(snakemake.output.raster, "w", driver="GTiff", height=shape[0],
                       width=shape[1], count=1, dtype="uint8", crs=f"EPSG:{crs}",
                       transform=transform, compress="deflate", tiled=True, nbits=1) as dst:
        dst.write(out, 1)
    stats = {"layer": snakemake.wildcards.layer, "features": int(n_feat),
             "buffer_m": buffer_m, "cells": cells,
             "area_km2": round(cells * grid["res"] ** 2 / 1e6, 2),
             "share_of_region_pct": round(100 * cells / grid["region_cells"], 3)}
    Path(snakemake.output.stats).write_text(json.dumps(stats, indent=2))
    logger.info("%s", stats)
