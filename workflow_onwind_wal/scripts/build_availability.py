# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Run the atlite land-eligibility analysis for one (scenario, turbine, region).

Two modes:

``corine``
    Byte-for-byte the logic of PyPSA-Eur's ``determine_availability_matrix.py``
    — CORINE grid codes as an inclusion mask, a 1 km buffer around the urban and
    transport codes, and the Natura 2000 raster.  This reproduces the number the
    model uses today and is the baseline the rest of the ladder is measured
    against.

``walloon``
    The Walloon legal constraint set, supplied as vector layers by
    ``build_exclusion_layers.py``.

The output is the atlite availability matrix (share of each cutout grid cell
that survives the exclusions) plus the eligible area per cell, which is all the
downstream steps need.
"""

import json
import logging
from pathlib import Path

import atlite
import geopandas as gpd
import xarray as xr
from atlite.gis import ExclusionContainer

logger = logging.getLogger(__name__)


# Layers carried as rasters rather than vectors: the scattered-dwelling setback
# (buffering 1.5 M address points as vectors is intractable; an exact distance
# transform on a 50 m grid is equivalent at this resolution) and the slope
# criterion (a grid by nature).
RASTER_LAYERS = {"dwelling_setback": "dwelling_raster", "slope": "slope_raster"}


def build_excluder(scenario, params, layers_path, crs, res):
    excluder = ExclusionContainer(crs=crs, res=res)

    if scenario["mode"] == "corine":
        excluder.add_raster(
            params["corine"],
            codes=scenario["corine_grid_codes"],
            invert=True,
            crs=3035,
        )
        if scenario.get("corine_distance", 0) > 0:
            excluder.add_raster(
                params["corine"],
                codes=scenario["corine_distance_grid_codes"],
                buffer=scenario["corine_distance"],
                crs=3035,
            )
        if scenario.get("natura"):
            excluder.add_raster(params["natura"], nodata=0, allow_no_overlap=True)
        return excluder, list(scenario["corine_grid_codes"])

    used = []
    for name in scenario["layers"]:
        if name in RASTER_LAYERS:
            excluder.add_raster(
                params[RASTER_LAYERS[name]], codes=[1], crs=crs, nodata=255
            )
            used.append(name)
            continue
        # Paths, not GeoDataFrames: atlite's `all_closed` check refuses to
        # parallelise otherwise.  The layers are already in the workflow CRS.
        path = Path(layers_path) / f"{name}.gpkg"
        if not path.exists():
            logger.warning("layer %s not present in %s, skipped", name, layers_path)
            continue
        excluder.add_geometry(str(path))
        used.append(name)
    if not used:
        raise RuntimeError(f"scenario {scenario} produced no exclusion layer")
    return excluder, used


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    crs = snakemake.params.crs
    res = snakemake.params.res
    scenario = snakemake.params.scenario
    region_name = snakemake.wildcards.region

    regions = gpd.read_file(snakemake.input.regions, layer="regions")
    regions = regions.set_index("name").loc[[region_name]].to_crs(crs)
    regions.index.name = "bus"

    cutout = atlite.Cutout(snakemake.input.cutout)

    excluder, used = build_excluder(
        scenario,
        {
            "corine": snakemake.input.get("corine"),
            "natura": snakemake.input.get("natura"),
            "dwelling_raster": snakemake.input.get("dwelling_raster"),
            "slope_raster": snakemake.input.get("slope_raster"),
        },
        snakemake.input.get("layers"),
        crs,
        res,
    )

    logger.info("scenario %s, layers %s", snakemake.wildcards.scenario, used)
    availability = cutout.availabilitymatrix(
        regions, excluder, nprocesses=snakemake.threads, disable_progressbar=True
    )

    # Eligible area per cutout cell, in km^2.  `cutout.grid` carries the cell
    # polygons; areas are computed in the same equal-area CRS as the exclusions.
    grid = cutout.grid.set_index(["y", "x"]).to_crs(crs)
    cell_area = xr.DataArray(
        grid.area.values.reshape(availability.sizes["y"], availability.sizes["x"]) / 1e6,
        coords=[availability.coords["y"], availability.coords["x"]],
    )
    eligible = availability * cell_area

    ds = xr.Dataset(
        {"availability": availability, "eligible_area": eligible, "cell_area": cell_area}
    )
    ds.attrs["scenario"] = snakemake.wildcards.scenario
    ds.attrs["turbine"] = snakemake.wildcards.turbine
    ds.attrs["region"] = region_name
    ds.attrs["layers"] = ", ".join(map(str, used))
    ds.to_netcdf(snakemake.output.availability)

    total = float(eligible.sum())
    region_area = float(regions.area.sum() / 1e6)
    stats = {
        "scenario": snakemake.wildcards.scenario,
        "turbine": snakemake.wildcards.turbine,
        "region": region_name,
        "region_area_km2": round(region_area, 1),
        "eligible_area_km2": round(total, 2),
        "eligible_share_pct": round(100 * total / region_area, 2),
        "layers": used,
    }
    Path(snakemake.output.stats).write_text(json.dumps(stats, indent=2))
    logger.info("%s", json.dumps(stats))
