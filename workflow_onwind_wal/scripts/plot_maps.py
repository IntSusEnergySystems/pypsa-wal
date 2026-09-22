# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Maps for the report.

``map_scenarios``   one panel per scenario of the ladder, showing the share of
                    each cutout cell that survives the exclusions
``map_reference``   the reference scenario at full raster resolution: the
                    eligible envelope drawn against the constraint layers
"""

import logging
from pathlib import Path

import geopandas as gpd
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.patches import Patch

mpl.use("Agg")
logger = logging.getLogger(__name__)

plt.rcParams.update(
    {
        "font.size": 8,
        "axes.titlesize": 9,
        "figure.dpi": 200,
        "savefig.bbox": "tight",
    }
)


def frame(ax, boundary):
    boundary.boundary.plot(ax=ax, color="0.15", linewidth=0.6)
    ax.set_axis_off()
    ax.set_aspect("equal")


def cell_polygons(ds, crs):
    """Reconstruct the cutout cells as polygons from the netCDF coordinates."""
    from shapely.geometry import box

    x = ds.x.values
    y = ds.y.values
    dx = float(np.median(np.diff(x))) if len(x) > 1 else 0.3
    dy = float(np.median(np.diff(y))) if len(y) > 1 else 0.3
    geoms, vals = [], []
    avail = ds["availability"].squeeze("bus", drop=True)
    for j, yy in enumerate(y):
        for i, xx in enumerate(x):
            geoms.append(box(xx - dx / 2, yy - dy / 2, xx + dx / 2, yy + dy / 2))
            vals.append(float(avail.values[j, i]))
    gdf = gpd.GeoDataFrame({"availability": vals}, geometry=geoms, crs=4326)
    return gdf.to_crs(crs)


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
    scenarios = cfg["scenarios"]
    ref_scenario = cfg["reference_scenario"]

    regions = gpd.read_file(snakemake.input.regions, layer="regions")
    admin = regions[regions["name"] == "admin"]

    # ------------------------------------------------------------------
    # 1. Scenario ladder
    # ------------------------------------------------------------------
    paths = {Path(p).stem.split("_admin")[0]: p for p in snakemake.input.availability}
    ordered = [s for s in scenarios if any(k.startswith(f"availability_{s}") for k in paths)]

    ncol = 3
    nrow = int(np.ceil(len(ordered) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.0 * ncol, 3.0 * nrow))
    axes = np.atleast_1d(axes).ravel()

    cmap = plt.get_cmap("YlGn")
    # One scale for all panels so they stay comparable, but square-rooted:
    # a linear scale on a range set by S1 washes S2-S5 out to a uniform pale.
    norm = mpl.colors.PowerNorm(gamma=0.5, vmin=0, vmax=0.6)

    for ax, name in zip(axes, ordered):
        key = next(k for k in paths if k.startswith(f"availability_{name}"))
        ds = xr.open_dataset(paths[key])
        cells = cell_polygons(ds, crs)
        cells = gpd.overlay(
            cells, admin[["geometry"]].to_crs(crs), how="intersection", keep_geom_type=True
        )
        cells.plot(ax=ax, column="availability", cmap=cmap, norm=norm, linewidth=0)
        frame(ax, admin.to_crs(crs))
        area = float(ds["eligible_area"].sum())
        ax.set_title(
            f"{name}\n{scenarios[name]['title']}\n{area:,.0f} km$^2$ eligible".replace(
                ",", " "
            )
        )
    for ax in axes[len(ordered) :]:
        ax.set_axis_off()

    sm = mpl.cm.ScalarMappable(cmap=cmap, norm=norm)
    cbar = fig.colorbar(
        sm, ax=axes.tolist(), orientation="horizontal", fraction=0.03, pad=0.02
    )
    cbar.set_ticks([0, 0.02, 0.05, 0.1, 0.2, 0.4, 0.6])
    cbar.set_label(
        "share of the ERA5 cell available for onshore wind "
        "(square-root scale, common to all panels)"
    )
    fig.suptitle(
        "Walloon onshore-wind land eligibility — successive constraint sets\n"
        f"turbine class {cfg['turbines'][cfg['reference_turbine']]['label']}",
        y=1.02,
    )
    fig.savefig(snakemake.output.scenarios)
    plt.close(fig)

    # ------------------------------------------------------------------
    # 2. Reference scenario at raster resolution
    # ------------------------------------------------------------------
    layers = snakemake.input.layers
    fig, ax = plt.subplots(figsize=(9, 6))

    style = [
        ("eligible_pds", "#2b8a3e", 0.85, "admissible zoning (plan de secteur)"),
        ("nature", "#1c7ed6", 0.35, "Natura 2000, reserves, wetlands, caves"),
        ("landscape", "#f59f00", 0.30, "landscape perimeters (PIP / ADESA)"),
        ("risk", "#7048e8", 0.25, "flood, karst, landslide, water capture"),
    ]
    handles = []
    for name, color, alpha, label in style:
        try:
            g = gpd.read_file(layers, layer=name)
        except Exception:  # noqa: BLE001
            continue
        g.plot(ax=ax, color=color, alpha=alpha, linewidth=0)
        handles.append(Patch(facecolor=color, alpha=alpha, label=label))

    frame(ax, admin.to_crs(crs))
    ax.legend(handles=handles, loc="lower left", frameon=False, fontsize=7)
    ax.set_title(
        "Walloon onshore wind: admissible zoning and the protection layers "
        "laid over it\n(100 m exclusion raster, reference turbine class)"
    )
    fig.savefig(snakemake.output.reference)
    plt.close(fig)

    logger.info("figures written")
