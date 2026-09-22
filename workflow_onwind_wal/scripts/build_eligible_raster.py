# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Rasterise the reference constraint set over Wallonia at the exclusion
resolution, once per turbine class.

``atlite.gis.shape_availability`` is the same code path the availability matrix
uses, so this raster is the object the potential is integrated from --- not a
redrawing of the input layers.  It is written as a GeoTIFF so the result can be
opened in QGIS and checked parcel by parcel, which is what an administration
will want to do, and it is the input to the turbine-placement model.

The fragmentation statistics of the raster are written alongside it.  They are
reported in the study as a description of the land, not as a screen: the
placement model, not a patch-size filter, is what turns this raster into a
capacity.
"""

import json
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from atlite.gis import ExclusionContainer, shape_availability
from scipy.ndimage import label

logger = logging.getLogger(__name__)

# Exclusion layers carried as rasters rather than vectors.
RASTER_LAYERS = {"dwelling_setback": "dwelling_raster", "slope": "slope_raster"}


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    cfg = snakemake.params.config
    crs = cfg["atlite"]["crs"]
    res = cfg["atlite"]["excluder_resolution"]
    scenario = cfg["scenarios"][cfg["reference_scenario"]]
    turbine = cfg["turbines"][snakemake.wildcards.turbine]

    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    admin = regions[regions["name"] == "admin"]

    excluder = ExclusionContainer(crs=crs, res=res)
    for name in scenario["layers"]:
        if name in RASTER_LAYERS:
            excluder.add_raster(
                snakemake.input[RASTER_LAYERS[name]], codes=[1], crs=crs, nodata=255
            )
            continue
        path = Path(snakemake.input.layer_dir) / f"{name}.gpkg"
        if path.exists():
            excluder.add_geometry(str(path))
        else:
            logger.warning("layer %s absent, skipped", name)

    masked, transform = shape_availability(admin.geometry, excluder)
    eligible_km2 = float(masked.sum()) * res * res / 1e6
    logger.info("eligible at %d m: %.1f km2", res, eligible_km2)

    D = float(turbine["rotor_diameter"]) / 1000.0
    footprint = (
        cfg["turbines"]["spacing_crosswind"] * D * cfg["turbines"]["spacing_downwind"] * D
    )
    labels, n = label(masked.astype(bool))
    sizes = np.bincount(labels.ravel())[1:] * res * res / 1e6
    frag = {
        "turbine": snakemake.wildcards.turbine,
        "n_patches": int(n),
        "footprint_km2": round(footprint, 3),
        "median_patch_km2": round(float(np.median(sizes)), 4),
        "area_km2": round(eligible_km2, 1),
        "area_in_patches_ge_1_turbine_km2": round(
            float(sizes[sizes >= footprint].sum()), 1
        ),
        "area_in_patches_ge_4_turbines_km2": round(
            float(sizes[sizes >= 4 * footprint].sum()), 1
        ),
        "largest_patch_km2": round(float(sizes.max()), 1),
    }
    frag["share_ge_1_turbine_pct"] = round(
        100 * frag["area_in_patches_ge_1_turbine_km2"] / eligible_km2, 1
    )
    frag["share_ge_4_turbines_pct"] = round(
        100 * frag["area_in_patches_ge_4_turbines_km2"] / eligible_km2, 1
    )
    Path(snakemake.output.fragmentation).write_text(json.dumps(frag, indent=2))
    logger.info("fragmentation %s", json.dumps(frag))

    with rasterio.open(
        snakemake.output.raster,
        "w",
        driver="GTiff",
        height=masked.shape[0],
        width=masked.shape[1],
        count=1,
        dtype="uint8",
        crs=f"EPSG:{crs}",
        transform=transform,
        compress="deflate",
        nodata=0,
    ) as dst:
        dst.write(masked.astype(np.uint8), 1)
    logger.info("wrote %s", snakemake.output.raster)
