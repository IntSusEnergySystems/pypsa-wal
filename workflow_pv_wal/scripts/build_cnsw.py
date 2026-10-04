# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""Burn the principal soil types of the CNSW (their CODE) onto the study grid."""

import json
from pathlib import Path

import rasterio
import geopandas as gpd
from rasterio.features import rasterize
from rasterio.transform import Affine

if __name__ == "__main__":
    g = json.loads(Path(snakemake.input.grid).read_text())
    tr = Affine(*g["transform"])
    c = gpd.read_file(snakemake.input.soils, layer="data").to_crs(g["crs"])
    code = rasterize(zip(c.geometry, c["CODE"].astype(int)), out_shape=(g["height"], g["width"]),
                     transform=tr, dtype="int32")
    with rasterio.open(snakemake.output[0], "w", driver="GTiff", height=g["height"], width=g["width"],
                       count=1, dtype="int32", crs=f"EPSG:{g['crs']}", transform=tr,
                       compress="deflate", tiled=True) as dst:
        dst.write(code, 1)
