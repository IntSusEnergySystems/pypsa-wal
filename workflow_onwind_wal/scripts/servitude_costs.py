# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
What each of the late-added constraint families costs, on its own and together.

The four families added in scenario ``S6`` --- aeronautical servitudes, the 7 %
slope criterion, classified sites and the reconstructed radar perimeters ---
are the ones an earlier version of this study had to leave out.  Reporting only
their combined effect would hide which of them matters, so each is rasterised
on top of ``S5`` alone as well.

Marginal costs do not add up to the combined cost: the families overlap each
other and overlap what ``S5`` already removes.  Both numbers are reported.
"""

import json
import logging
from pathlib import Path

import geopandas as gpd
from atlite.gis import ExclusionContainer, shape_availability

logger = logging.getLogger(__name__)

RASTER_LAYERS = {"dwelling_setback": "dwelling_raster", "slope": "slope_raster"}


def area_of(layers, inputs, crs, res, shape):
    excluder = ExclusionContainer(crs=crs, res=res)
    for name in layers:
        if name in RASTER_LAYERS:
            excluder.add_raster(inputs[RASTER_LAYERS[name]], codes=[1], crs=crs, nodata=255)
            continue
        path = Path(inputs["layer_dir"]) / f"{name}.gpkg"
        if path.exists():
            excluder.add_geometry(str(path))
        else:
            logger.warning("layer %s absent", name)
    masked, _ = shape_availability(shape, excluder)
    return float(masked.sum()) * res * res / 1e6


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
    base_name = snakemake.params.base_scenario
    ref_name = cfg["reference_scenario"]
    base = list(cfg["scenarios"][base_name]["layers"])
    full = list(cfg["scenarios"][ref_name]["layers"])
    added = [name for name in full if name not in base]

    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    shape = regions[regions["name"] == "admin"].geometry

    inputs = {
        "layer_dir": snakemake.input.layer_dir,
        "dwelling_raster": snakemake.input.dwelling_raster,
        "slope_raster": snakemake.input.slope_raster,
    }

    base_area = area_of(base, inputs, crs, res, shape)
    logger.info("%s: %.1f km2", base_name, base_area)

    out = {
        "turbine": snakemake.wildcards.turbine,
        "base_scenario": base_name,
        "base_area_km2": round(base_area, 1),
        "families": {},
    }
    for name in added:
        a = area_of(base + [name], inputs, crs, res, shape)
        out["families"][name] = {
            "area_after_km2": round(a, 1),
            "removed_km2": round(base_area - a, 1),
            "removed_pct": round(100 * (base_area - a) / base_area, 1),
        }
        logger.info("+%s: %.1f km2 (-%.1f)", name, a, base_area - a)

    combined = area_of(full, inputs, crs, res, shape)
    out["combined_area_km2"] = round(combined, 1)
    out["combined_removed_km2"] = round(base_area - combined, 1)
    out["combined_removed_pct"] = round(100 * (base_area - combined) / base_area, 1)
    logger.info("combined: %.1f km2 (-%.1f)", combined, base_area - combined)

    Path(snakemake.output.table).write_text(json.dumps(out, indent=2))
