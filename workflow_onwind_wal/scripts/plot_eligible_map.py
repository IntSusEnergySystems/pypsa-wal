# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
The map the whole study is for: where, at 100 m resolution, a turbine may stand.

The raster comes from ``build_eligible_raster.py``, so what is drawn here is
exactly the object the capacity is derived from.
"""

import json
import logging

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.patches import Patch
from rasterio.plot import plotting_extent

mpl.use("Agg")
logger = logging.getLogger(__name__)

plt.rcParams.update({"font.size": 9, "figure.dpi": 220, "savefig.bbox": "tight"})


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

    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    admin = regions[regions["name"] == "admin"]

    with rasterio.open(snakemake.input.raster) as src:
        masked = src.read(1)
        extent = plotting_extent(masked, src.transform)

    frag = json.loads(open(snakemake.input.fragmentation).read())
    placement = pd.read_csv(snakemake.input.placement)
    ref = placement[
        (placement["spacing_case"] == cfg["placement"]["reference_case"])
        & (placement["model"] == cfg["placement"]["reference_model"])
        & (
            placement["interfarm_distance_m"]
            == float(cfg["placement"]["farm"]["reference_interfarm_distance_m"])
        )
    ].iloc[0]
    eligible_km2 = frag["area_km2"]

    fig, ax = plt.subplots(figsize=(10, 6.4))
    admin.plot(ax=ax, color="#f1f3f5", edgecolor="none", zorder=1)
    # imshow defaults to zorder 0, i.e. behind the patch just drawn.
    ax.imshow(
        np.ma.masked_where(masked == 0, masked),
        extent=extent,
        origin="upper",
        cmap=mpl.colors.ListedColormap(["#2b8a3e"]),
        interpolation="nearest",
        zorder=2,
    )
    admin.boundary.plot(ax=ax, color="0.2", linewidth=0.7, zorder=3)
    ax.set_axis_off()
    ax.set_aspect("equal")
    ax.legend(
        handles=[
            Patch(
                facecolor="#2b8a3e",
                label=(
                    f"land where a turbine may stand — "
                    f"{eligible_km2:,.0f} km$^2$".replace(",", " ")
                ),
            ),
            Patch(facecolor="#f1f3f5", edgecolor="0.2", label="Walloon Region"),
            Patch(
                facecolor="none",
                edgecolor="none",
                label=(
                    f"{frag['n_patches']:,} patches, median "
                    f"{frag['median_patch_km2'] * 100:.0f} ha; the allocation "
                    f"model fits {int(ref['n_turbines']):,} machines in "
                    f"{int(ref['n_farms']):,} farms ({ref['p_nom_max_mw']:,.0f} MW)"
                ).replace(",", " "),
            ),
        ],
        loc="lower left",
        frameon=False,
        fontsize=8.5,
    )
    ax.set_title(
        "Walloon onshore wind: the eligible land after every implemented "
        "constraint\n"
        f"(scenario {cfg['reference_scenario']}, "
        f"{cfg['turbines'][cfg['reference_turbine']]['label']}, "
        f"{res} m raster)"
    )
    fig.savefig(snakemake.output.figure)
    plt.close(fig)
    logger.info("wrote %s", snakemake.output.figure)
