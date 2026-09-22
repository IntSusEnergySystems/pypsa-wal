# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Turn eligible area into installable capacity and annual energy.

Capacity is ``eligible area x capacity density``.  Three densities are carried
through every case:

``pypsa_eur``   3.0 MW/km^2, the value in PyPSA-Eur's ``config.default.yaml``.
``derived``     p_nom / (5D x 7D), i.e. the density implied by the turbine's own
                geometry at conventional array spacing.  This is the honest
                technical figure for land that has already been filtered down to
                genuinely developable parcels.
``dense``       8 MW/km^2, a 4D x 6D upper bound.

The capacity factor is computed exactly as PyPSA-Eur does it: the generator
layout inside each region is proportional to ``eligible area x capacity
factor``, so that better cells carry more machines, and the profile is the
capacity-weighted mean of the cell profiles.  Full-load hours follow from the
annual mean of that profile.
"""

import json
import logging
from pathlib import Path

import atlite
import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

logger = logging.getLogger(__name__)


def capacity_densities(cfg, turbine, spacing_crosswind, spacing_downwind):
    D = float(turbine["rotor_diameter"]) / 1000.0  # km
    derived = float(turbine["p_nom"]) / (spacing_crosswind * D * spacing_downwind * D)
    out = {}
    for name, value in cfg.items():
        out[name] = round(derived, 3) if value is None else float(value)
    return out


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    crs = snakemake.params.crs
    turbine = snakemake.params.turbine
    densities = capacity_densities(
        snakemake.params.capacity_densities,
        turbine,
        snakemake.params.spacing_crosswind,
        snakemake.params.spacing_downwind,
    )
    logger.info("capacity densities MW/km2: %s", densities)

    ds = xr.open_dataset(snakemake.input.availability)
    # The availability matrix carries a length-1 `bus` dimension; atlite's
    # `wind(layout=...)` wants a plain (y, x) field.
    eligible = ds["eligible_area"].squeeze("bus", drop=True)

    regions = gpd.read_file(snakemake.input.regions, layer="regions")
    regions = regions.set_index("name").loc[[snakemake.wildcards.region]]
    regions.index.name = "bus"

    # The availability matrix spans the whole European cutout but is zero
    # everywhere outside Wallonia.  Trim both to the region's bounding box
    # before touching the 8760-hour wind data: computing the profile on the
    # full grid would be ~2 GB of floats for a result that is 40 cells wide.
    minx, miny, maxx, maxy = regions.to_crs(4326).total_bounds
    pad = 0.5
    box = dict(x=slice(minx - pad, maxx + pad), y=slice(miny - pad, maxy + pad))
    eligible = eligible.sel(**box)
    logger.info("trimmed to %s cells", dict(eligible.sizes))

    cutout = atlite.Cutout(snakemake.input.cutout).sel(**box)

    # Per-cell capacity factor for this turbine class.
    cf = cutout.wind(turbine=turbine["atlite_model"], capacity_factor=True)

    # PyPSA-Eur's layout: capacity is spread over cells in proportion to
    # eligible area times capacity factor, then the profile is the
    # capacity-weighted mean.  The weights are what matters, not their scale.
    weights = eligible * cf
    total_area = float(eligible.sum())

    if total_area <= 0:
        raise RuntimeError("no eligible area left — check the exclusion layers")

    layout = weights / float(weights.sum())

    # `shapes` must be in the cutout's own CRS (EPSG:4326); regions.gpkg is
    # stored in the equal-area working CRS.
    profile = cutout.wind(
        turbine=turbine["atlite_model"],
        layout=layout,
        shapes=regions.to_crs(4326),
        per_unit=True,
    )
    series = profile.isel(bus=0).to_pandas()
    flh = float(series.sum())
    mean_cf = float(series.mean())

    # Area-weighted mean capacity factor, i.e. what the resource looks like
    # before the siting weights are applied.  Reported as a cross-check.
    cf_area_weighted = float((eligible * cf).sum() / eligible.sum())

    rows = []
    for name, density in densities.items():
        p_nom_max = total_area * density
        rows.append(
            {
                "scenario": snakemake.wildcards.scenario,
                "turbine": snakemake.wildcards.turbine,
                "region": snakemake.wildcards.region,
                "density_case": name,
                "capacity_density_mw_km2": density,
                "eligible_area_km2": round(total_area, 2),
                "p_nom_max_mw": round(p_nom_max, 0),
                "flh_h": round(flh, 0),
                "mean_capacity_factor": round(mean_cf, 4),
                "cf_area_weighted": round(cf_area_weighted, 4),
                "energy_twh": round(p_nom_max * flh / 1e6, 3),
                "n_turbines": int(round(p_nom_max / turbine["p_nom"])),
            }
        )

    df = pd.DataFrame(rows)
    Path(snakemake.output.table).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(snakemake.output.table, index=False)

    series.rename("p_max_pu").to_frame().to_csv(snakemake.output.profile)
    logger.info("\n%s", df.to_string(index=False))
