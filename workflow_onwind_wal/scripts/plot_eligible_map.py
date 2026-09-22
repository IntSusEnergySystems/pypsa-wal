# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
The map the whole study is for: where, at 100 m resolution, a turbine may stand.

``atlite.gis.shape_availability`` rasterises the full reference exclusion set
over the Walloon shape and returns the surviving cells, so this is the exact
raster the potential is integrated from --- not a redrawing of the input layers.

A GeoTIFF is written alongside the figure so the result can be opened in QGIS
and checked parcel by parcel, which is what an administration will want to do.
"""

import json
import logging
from pathlib import Path

import atlite
import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from atlite.gis import ExclusionContainer, shape_availability
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from scipy.ndimage import label

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
    scenario = cfg["scenarios"][cfg["reference_scenario"]]

    regions = gpd.read_file(snakemake.input.regions, layer="regions").to_crs(crs)
    admin = regions[regions["name"] == "admin"]
    model = regions[regions["name"] == "model"]

    excluder = ExclusionContainer(crs=crs, res=res)
    for name in scenario["layers"]:
        if name == "dwelling_setback":
            excluder.add_raster(
                snakemake.input.dwelling_raster, codes=[1], crs=crs, nodata=255
            )
            continue
        path = Path(snakemake.input.layer_dir) / f"{name}.gpkg"
        if path.exists():
            excluder.add_geometry(str(path))

    masked, transform = shape_availability(admin.geometry, excluder)
    eligible_km2 = float(masked.sum()) * res * res / 1e6
    logger.info("eligible at %d m: %.1f km2", res, eligible_km2)

    # ------------------------------------------------------------------
    # Fragmentation.  The capacity density assumes an array at 5D x 7D
    # spacing, which only makes sense on a patch big enough to hold one.  A
    # patch smaller than a single turbine's footprint contributes area to the
    # integral but could never hold a machine; a patch smaller than four
    # footprints could not hold a "parc eolien" as the 2024 cadre de reference
    # defines one.  Both fractions are reported rather than netted out,
    # because the cut-off is a judgement the reader should see.
    # ------------------------------------------------------------------
    turbine = cfg["turbines"][cfg["reference_turbine"]]
    D = float(turbine["rotor_diameter"]) / 1000.0
    footprint = cfg["turbines"]["spacing_crosswind"] * D * (
        cfg["turbines"]["spacing_downwind"] * D
    )
    labels, n = label(masked.astype(bool))
    sizes = np.bincount(labels.ravel())[1:] * res * res / 1e6
    frag = {
        "n_patches": int(n),
        "footprint_km2": round(footprint, 3),
        "median_patch_km2": round(float(np.median(sizes)), 4),
        "area_km2": round(eligible_km2, 1),
        "area_in_patches_ge_1_turbine_km2": round(float(sizes[sizes >= footprint].sum()), 1),
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

    # GeoTIFF, for inspection
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

    # Figure
    fig, ax = plt.subplots(figsize=(10, 6.4))
    from rasterio.plot import plotting_extent

    extent = plotting_extent(masked, transform)
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
    model.boundary.plot(ax=ax, color="crimson", linewidth=1.0, linestyle="--", zorder=4)
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
            Line2D([], [], color="crimson", linestyle="--", label="PyPSA-Wal BEWAL node"),
            Patch(
                facecolor="none",
                edgecolor="none",
                label=(
                    f"{frag['share_ge_4_turbines_pct']:.0f} % of it sits in patches "
                    f"large enough for a four-turbine farm"
                ),
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
