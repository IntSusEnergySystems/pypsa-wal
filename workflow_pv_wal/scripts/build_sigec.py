# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Burn the 2024 agricultural parcels (SIGEC, "demande de superficie") onto the
study grid, as an agrivoltaic class per cell and a parcel index.

The class of each parcel follows ``config.sigec_classes``: its INSPIRE crop
class (``CROP_ID``), overridden for single crop codes (``CULT_CODE``).
1 permanent grassland, 2 temporary grassland and fodder, 3 arable crops,
4 perennial crops, 5 fallow and agri-environmental strips; 0 = not declared.

The parcel index (1-based row number in ``sigec_parcels.gpkg``, which this
script also writes, reprojected and slimmed) lets the potential be reported
per parcel and per farm-size class downstream.
"""

import json
import logging
from pathlib import Path

import rasterio
import fiona
import geopandas as gpd
import numpy as np
from rasterio.features import rasterize
from rasterio.transform import Affine

logger = logging.getLogger(__name__)

CHUNK = 20000


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=open(snakemake.log[0], "w"))  # noqa: SIM115

    cfg = snakemake.params.classes
    grid = json.loads(Path(snakemake.input.grid).read_text())
    transform = Affine(*grid["transform"])
    shape = (grid["height"], grid["width"])

    gpkgs = sorted(Path(snakemake.input.folder).parent.rglob("*.gpkg"))
    layer = None
    for path in gpkgs:
        for lyr in fiona.listlayers(path):
            with fiona.open(path, layer=lyr) as src:
                if "CULT_CODE" in src.schema["properties"] and "CROP_ID" in src.schema["properties"]:
                    layer = (path, lyr)
                    break
        if layer:
            break
    if layer is None:
        raise RuntimeError(f"no parcel layer with CULT_CODE and CROP_ID in {gpkgs}")
    logger.info("reading %s, layer %s", *layer)
    gdf = gpd.read_file(layer[0], layer=layer[1],
                        columns=["CULT_CODE", "CULT_NOM", "CROP_ID", "DECLARED"])
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].to_crs(grid["crs"])

    code = gdf["CULT_CODE"].astype(str).str.strip()
    cls = gdf["CROP_ID"].map(cfg["crop_id"])
    over = code.map({str(k): v for k, v in cfg["codes"].items()})
    cls = over.fillna(cls)
    unknown = gdf.loc[cls.isna(), "CROP_ID"].value_counts()
    if len(unknown):
        raise ValueError(f"CROP_ID without a class in config.sigec_classes: {unknown.to_dict()}")
    gdf["pv_class"] = cls.astype(np.uint8)
    gdf = gdf.reset_index(drop=True)
    gdf["pid"] = np.arange(1, len(gdf) + 1, dtype=np.int32)

    classes = np.zeros(shape, dtype=np.uint8)
    pids = np.zeros(shape, dtype=np.int32)
    geoms = gdf.geometry.values
    for i in range(0, len(gdf), CHUNK):
        sl = slice(i, i + CHUNK)
        rasterize(zip(geoms[sl], gdf["pv_class"].values[sl]), out=classes,
                  transform=transform, dtype="uint8")
        rasterize(zip(geoms[sl], gdf["pid"].values[sl]), out=pids,
                  transform=transform, dtype="int32")
        logger.info("burnt %d / %d parcels", min(i + CHUNK, len(gdf)), len(gdf))

    with rasterio.open(snakemake.input.region_mask) as src:
        region = src.read(1).astype(bool)
    classes[~region] = 0
    pids[~region] = 0
    base = dict(driver="GTiff", height=shape[0], width=shape[1], count=1,
                crs=f"EPSG:{grid['crs']}", transform=transform, compress="deflate", tiled=True)
    with rasterio.open(snakemake.output.classes, "w", dtype="uint8", **base) as dst:
        dst.write(classes, 1)
    with rasterio.open(snakemake.output.pids, "w", dtype="int32", **base) as dst:
        dst.write(pids, 1)
    gdf[["pid", "CULT_CODE", "CULT_NOM", "CROP_ID", "DECLARED", "pv_class", "geometry"]].to_file(
        snakemake.output.parcels, driver="GPKG", layer="data")

    res2 = grid["res"] ** 2 / 1e4
    burnt = np.bincount(classes[region].ravel(), minlength=6) * res2
    stats = {
        "parcels": int(len(gdf)),
        "declared_ha_by_class": {int(k): round(float(v), 1)
                                 for k, v in gdf.groupby("pv_class")["DECLARED"].sum().items()},
        "burnt_ha_by_class": {k: round(float(burnt[k]), 1) for k in range(1, 6)},
        "declared_ha": round(float(gdf["DECLARED"].sum()), 1),
        "burnt_ha": round(float(burnt[1:].sum()), 1),
    }
    Path(snakemake.output.stats).write_text(json.dumps(stats, indent=2))
    logger.info("%s", stats)
