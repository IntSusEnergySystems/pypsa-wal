# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Report maps, drawn from the reference rasters of ``potential.py``.

``map_exclusions.png``  which family of rules removes each piece of land
                        (first family in the funnel order; the land that
                        survives in green)
``map_gisements.png``   the land left after every exclusion and the park rule,
                        coloured by gisement group, with the parks of OSM

The 20 m rasters are drawn at 100 m: each 100 m pixel takes the most frequent
class of its 25 cells, except that surviving land wins as soon as it covers a
fifth of the pixel -- at page scale a 2 ha brownfield would otherwise vanish.

Colours: the exclusion families reuse the five muted, validated colours of the
wind study's infographic (same series, same meaning); the five gisement
groups were validated all-pairs for colour-vision deficiency with the dataviz
palette validator (worst CVD ΔE 13.0, normal-vision ΔE 16.3).
"""

import logging

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from pv_lib import FAMILIES  # noqa: E402

logger = logging.getLogger(__name__)

BG = "#F5F0E8"
AVAILABLE = "#2B8A3E"
EXCLUDED = "#E3DDD2"
# display family -> (colour, label, pipeline families)
DISPLAY_FAMILIES = [
    ("#C4AC8E", "Nature (Natura 2000, reserves, zones naturelles, spoil tips in place)", ["nature"]),
    ("#E9E196", "Forest zone, green zones, woodland", ["forest", "cover"]),
    ("#A780AD", "Landscape and heritage perimeters", ["landscape"]),
    ("#3A70AD", "Natural hazards, slope, north-facing slopes", ["hazard", "terrain"]),
    ("#513249", "Buildings, roads, railways, HV lines, water", ["built", "water"]),
]
# gisement group -> (colour, label, gisements)
GROUPS = [
    ("#4a3aa7", "Degraded land: brownfields, landfills, spoil tips, extraction, verges",
     ["sar", "cet", "terril", "quarry_active", "extraction", "infra_edge"]),
    ("#e87ba4", "Economic-activity and public-service zones", ["zae", "zspec"]),
    ("#2B8A3E", "Farmland — grassland", ["agri_grassland_perm", "agri_grassland_temp", "agri_other"]),
    ("#eda100", "Farmland — arable and perennial crops", ["agri_arable", "agri_perennial"]),
    ("#2a78d6", "Water bodies (floating PV)", ["water_industrial", "water_other"]),
    ("#9a968c", "Other: unfarmed agricultural zone (incl. poor soils), habitat zones, other",
     ["agri_zone_poor", "agri_zone_unfarmed", "habitat", "other"]),
]


def read(path):
    with rasterio.open(path) as src:
        return src.read(1), src.transform


def mode_blocks(cls, f, n_classes, priority=None, priority_share=0.2):
    """Most frequent class per f x f block; `priority` classes win above a share."""
    h, w = (cls.shape[0] // f) * f, (cls.shape[1] // f) * f
    b = cls[:h, :w].reshape(h // f, f, w // f, f).transpose(0, 2, 1, 3).reshape(h // f, w // f, f * f)
    counts = np.stack([(b == k).sum(axis=2) for k in range(n_classes)], axis=0)
    out = counts.argmax(axis=0).astype(np.uint8)
    if priority is not None:
        pc = counts[priority]
        best = np.array(priority)[pc.argmax(axis=0)]
        win = pc.max(axis=0) >= priority_share * f * f
        out[win] = best[win]
    return out


def base_axes(fig, admin, extent):
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(BG)
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_aspect("equal")
    ax.axis("off")
    return ax


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=open(snakemake.log[0], "w"))  # noqa: SIM115

    cfg = snakemake.params.config
    d = snakemake.input.reference
    region, tr = read(snakemake.input.region_mask)
    fam_first, _ = read(f"{d}/family_first.tif")
    gis, _ = read(f"{d}/gisement.tif")
    tech, _ = read(f"{d}/tech_land.tif")
    flt, _ = read(f"{d}/float_ok.tif")
    f = 5
    extent = (tr.c, tr.c + tr.a * region.shape[1], tr.f + tr.e * region.shape[0], tr.f)
    admin = gpd.read_file(snakemake.input.regions, layer="regions")
    admin = admin[admin["name"] == "admin"].to_crs(cfg["grid"]["crs"])

    # ---- exclusions map ------------------------------------------------------
    fams = FAMILIES
    to_disp = np.zeros(len(fams) + 3, dtype=np.uint8)   # pipeline code -> display code
    for di, (_, _, members) in enumerate(DISPLAY_FAMILIES):
        for m in members:
            if m == "water":
                to_disp[len(fams) + 1] = di + 1
            else:
                to_disp[fams.index(m) + 1] = di + 1
    disp = to_disp[np.minimum(fam_first, len(fams) + 1)]
    survive = region.astype(bool) & ((tech > 0) | (flt > 0))
    disp[survive] = len(DISPLAY_FAMILIES) + 1           # available (after the park rule)
    disp[region.astype(bool) & ~survive & (disp == 0)] = len(DISPLAY_FAMILIES) + 2  # park rule
    disp[~region.astype(bool)] = 0
    n = len(DISPLAY_FAMILIES) + 3
    img = mode_blocks(disp, f, n, priority=[len(DISPLAY_FAMILIES) + 1])
    colours = [BG] + [c for c, _, _ in DISPLAY_FAMILIES] + [AVAILABLE, "#CFC8BA"]
    fig = plt.figure(figsize=(10, 6.4), dpi=200)
    ax = base_axes(fig, admin, extent)
    ax.imshow(img, cmap=ListedColormap(colours), vmin=0, vmax=n - 1, extent=extent,
              interpolation="nearest")
    admin.boundary.plot(ax=ax, color="#333333", linewidth=0.6)
    handles = [Patch(color=c, label=l) for c, l, _ in DISPLAY_FAMILIES] + [
        Patch(color="#CFC8BA", label="Too small or too narrow for a park"),
        Patch(color=AVAILABLE, label="Eligible land (drawn wherever it covers a fifth of a 100 m pixel)")]
    ax.legend(handles=handles, loc="lower left", fontsize=7, frameon=False,
              bbox_to_anchor=(0.0, 0.0), title="Land removed by (first rule in the funnel order)",
              title_fontsize=7.5, alignment="left")
    fig.savefig(snakemake.output.exclusions, facecolor=BG)
    plt.close(fig)

    # ---- gisement map ----------------------------------------------------------
    keys = [g["key"] for g in cfg["gisements"]]
    to_grp = np.zeros(len(keys) + 1, dtype=np.uint8)
    for gi, (_, _, members) in enumerate(GROUPS):
        for m in members:
            to_grp[keys.index(m) + 1] = gi + 1
    grp = np.where(survive, to_grp[gis], 0).astype(np.uint8)
    grp[region.astype(bool) & ~survive] = len(GROUPS) + 1
    n = len(GROUPS) + 2
    img = mode_blocks(grp, f, n, priority=list(range(1, len(GROUPS) + 1)))
    colours = [BG] + [c for c, _, _ in GROUPS] + [EXCLUDED]
    fig = plt.figure(figsize=(10, 6.4), dpi=200)
    ax = base_axes(fig, admin, extent)
    ax.imshow(img, cmap=ListedColormap(colours), vmin=0, vmax=n - 1, extent=extent,
              interpolation="nearest")
    admin.boundary.plot(ax=ax, color="#333333", linewidth=0.6)
    parks = gpd.read_file(snakemake.input.parks, layer="data").to_crs(cfg["grid"]["crs"])
    pts = parks.representative_point()
    ax.scatter(pts.x, pts.y, s=np.clip(parks["area_ha"], 2, 40), facecolor="none",
               edgecolor="#111111", linewidth=0.6, zorder=5)
    handles = [Patch(color=c, label=l) for c, l, _ in GROUPS] + [
        Patch(color=EXCLUDED, label="Excluded"),
        plt.Line2D([], [], marker="o", color="none", markeredgecolor="#111111",
                   label=f"Ground-mounted PV parks mapped in OSM ({len(parks)})")]
    ax.legend(handles=handles, loc="lower left", fontsize=7, frameon=False,
              title="Eligible land by gisement (after the park rule)", title_fontsize=7.5,
              alignment="left")
    fig.savefig(snakemake.output.gisements, facecolor=BG)
    plt.close(fig)
    logger.info("maps written")
