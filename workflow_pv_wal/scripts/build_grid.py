# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Define the study grid, once, and write the Region mask on it.

Every layer of the workflow is burnt onto this one grid, so that two layers can
be combined cell by cell without resampling.  The extent is the administrative
Region's bounding box snapped outward to 100 m, so that five 20 m cells make one
cell of the wind study's grid and the two studies can be overlaid.

``region_mask.tif`` is 1 inside the Region, 0 outside (a cell belongs to the
Region when its centre does).
"""

import json
import logging
from pathlib import Path

# rasterio before geopandas: see workflow_onwind_wal/scripts/retrieve_slope_raster.py.
import rasterio
import geopandas as gpd
import numpy as np
from rasterio.features import rasterize
from rasterio.transform import from_origin

logger = logging.getLogger(__name__)

SNAP = 100.0


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    crs = int(snakemake.params.crs)
    res = float(snakemake.params.res)
    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    admin = regions[regions["name"] == "admin"]

    minx, miny, maxx, maxy = admin.total_bounds
    minx = np.floor(minx / SNAP) * SNAP
    miny = np.floor(miny / SNAP) * SNAP
    maxx = np.ceil(maxx / SNAP) * SNAP
    maxy = np.ceil(maxy / SNAP) * SNAP
    width = int(round((maxx - minx) / res))
    height = int(round((maxy - miny) / res))
    transform = from_origin(minx, maxy, res, res)

    mask = rasterize(
        [(g, 1) for g in admin.geometry],
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype="uint8",
    )
    with rasterio.open(
        snakemake.output.region_mask, "w", driver="GTiff", height=height, width=width,
        count=1, dtype="uint8", crs=f"EPSG:{crs}", transform=transform,
        compress="deflate", tiled=True,
    ) as dst:
        dst.write(mask, 1)

    grid = {
        "crs": crs,
        "res": res,
        "bounds": [float(minx), float(miny), float(maxx), float(maxy)],
        "width": width,
        "height": height,
        "transform": list(transform)[:6],
        "region_cells": int(mask.sum()),
        "region_km2": round(float(mask.sum()) * res * res / 1e6, 1),
        "region_polygon_km2": round(float(admin.area.sum()) / 1e6, 1),
    }
    Path(snakemake.output.grid).write_text(json.dumps(grid, indent=2))
    logger.info("grid %d x %d at %.0f m; Region %.1f km2 (%d cells)",
                width, height, res, grid["region_km2"], grid["region_cells"])
