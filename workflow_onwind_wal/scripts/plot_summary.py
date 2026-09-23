# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Two summary charts, both for the administrative Walloon Region:

``waterfall``    eligible land after each successive constraint group
``sensitivity``  left, installable capacity across turbine classes and capacity
                 densities; right, the capacity ladder that actually produces
                 the study's answer --- area times density, the free
                 allocation, parks, the open horizon, the inter-distance
                 sensitivity and the residual allowance --- against the
                 benchmarks
"""

import json
import logging
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

mpl.use("Agg")
logger = logging.getLogger(__name__)

plt.rcParams.update(
    {"font.size": 9, "axes.titlesize": 10, "figure.dpi": 200, "savefig.bbox": "tight"}
)


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=open(snakemake.log[0], "w"),  # noqa: SIM115
    )

    cfg = snakemake.params.config
    ref_turbine = cfg["reference_turbine"]
    ref_scenario = cfg["reference_scenario"]
    bench = cfg["benchmarks"]

    waterfall = pd.read_csv(snakemake.input.waterfall)
    sens = pd.read_csv(snakemake.input.sensitivity)
    headline = json.loads(Path(snakemake.input.headline).read_text())
    pl = headline["placement"]
    resid = headline["residual"]

    # ------------------------------------------------------------------
    # Waterfall
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    x = np.arange(len(waterfall))
    # S0 is PyPSA-Eur's own specification, not a rung of the Walloon ladder;
    # colour it apart so the bars are not read as a single sequence.
    colors = ["#adb5bd" if not lad else "#2b8a3e" for lad in waterfall["in_ladder"]]
    ax.bar(x, waterfall["eligible_area_km2"], color=colors, width=0.62)
    for xi, (area, share) in enumerate(
        zip(waterfall["eligible_area_km2"], waterfall["share_of_region_pct"])
    ):
        ax.text(
            xi,
            area,
            f"{area:,.0f}\n{share:.1f} %".replace(",", " "),
            ha="center",
            va="bottom",
            fontsize=7.5,
        )
    ax.set_xticks(x)
    ax.set_xticklabels(waterfall["scenario"], rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("eligible area [km$^2$]")
    ax.set_ylim(0, waterfall["eligible_area_km2"].max() * 1.30)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(
        handles=[
            Patch(facecolor="#2b8a3e", label="Walloon constraint ladder (cumulative)"),
            Patch(
                facecolor="#adb5bd", label="PyPSA-Eur default (separate specification)"
            ),
        ],
        frameon=False,
        fontsize=8,
        loc="upper right",
    )
    ax.set_title(
        "Land surviving each successive constraint set, administrative Wallonia\n"
        f"({cfg['turbines'][ref_turbine]['label']})"
    )
    fig.savefig(snakemake.output.waterfall)
    plt.close(fig)

    # ------------------------------------------------------------------
    # Sensitivity + capacity ladder
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.0))

    turbines = [t for t in cfg["turbines"] if isinstance(cfg["turbines"][t], dict)]
    densities = list(cfg["capacity_densities"])
    dcolors = {"pypsa_eur": "#adb5bd", "derived": "#2b8a3e", "dense": "#1c7ed6"}

    ax = axes[0]
    width = 0.26
    x = np.arange(len(turbines))
    for k, dcase in enumerate(densities):
        vals = []
        for t in turbines:
            row = sens[(sens["turbine"] == t) & (sens["density_case"] == dcase)]
            vals.append(float(row["p_nom_max_mw"].iloc[0]) if len(row) else np.nan)
        pos = x + (k - (len(densities) - 1) / 2) * width
        ax.bar(pos, vals, width=width, color=dcolors.get(dcase, "0.6"))
        for xi, v in zip(pos, vals):
            if np.isfinite(v):
                ax.text(
                    xi,
                    v,
                    f"{v:,.0f}".replace(",", " "),
                    ha="center",
                    va="bottom",
                    fontsize=7,
                    rotation=90,
                )
    ax.set_xticks(x)
    ax.set_xticklabels(
        [cfg["turbines"][t]["label"].replace(" (", "\n(") for t in turbines], fontsize=8
    )
    ax.set_ylabel("installable capacity [MW]")
    ax.set_title("area $\\times$ capacity density\n(the convention this study replaces)")
    ax.set_ylim(0, max(sens["p_nom_max_mw"]) * 1.25)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(
        handles=[
            Patch(facecolor=dcolors.get(d, "0.6"), label=f"density: {d.replace('_', ' ')}")
            for d in densities
        ],
        frameon=False,
        fontsize=8,
        loc="upper right",
    )

    # The ladder that produces the answer.
    ax = axes[1]
    ids = pl["by_interdistance"]
    steps = [
        ("area $\\times$ density", headline["area_density"]["p_nom_max_mw"], "#adb5bd"),
        ("free allocation", pl["free_p_nom_max_mw"], "#1c7ed6"),
        (f"parks of {pl['min_turbines']}+", pl["no_horizon_p_nom_max_mw"], "#74c0fc"),
        ("+ open horizon", pl["p_nom_max_mw"], "#2b8a3e"),
    ]
    for d in sorted(ids, key=int):
        steps.append((f"+ {int(d) // 1000} km apart (sens.)",
                      ids[d]["p_nom_max_mw"], "#8ce99a"))
    steps.append(("central estimate", resid["central"]["p_nom_max_mw"],
                  "#e8590c"))
    labels = [s[0] for s in steps]
    vals = [s[1] for s in steps]
    cols = [s[2] for s in steps]
    xx = np.arange(len(steps))
    ax.bar(xx, vals, color=cols, width=0.6)
    for xi, v in zip(xx, vals):
        ax.text(
            xi, v, f"{v:,.0f}".replace(",", " "), ha="center", va="bottom", fontsize=7.5
        )
    ax.set_xticks(xx)
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax.set_ylim(0, max(vals) * 1.22)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title(
        f"from eligible land to a technical potential\n"
        f"({cfg['turbines'][ref_turbine]['label']}, scenario {ref_scenario})"
    )

    marks = [
        (
            bench["model_p_nom_max_mw"],
            "crimson",
            "--",
            f"PyPSA-Wal cap today: {bench['model_p_nom_max_mw']:,} MW",
        ),
        (
            headline["bregilab"]["total_mw"],
            "#5f3dc4",
            (0, (4, 2)),
            f"BREGILAB: {headline['bregilab']['total_mw']:,.0f} MW",
        ),
        (
            bench["installed_2024_mw"],
            "0.35",
            ":",
            f"installed end-2024: {bench['installed_2024_mw']:,} MW",
        ),
    ]
    for y, color, style, _ in marks:
        ax.axhline(y, color=color, linestyle=style, linewidth=1)

    fig.legend(
        handles=[
            Line2D([], [], color=c, linestyle=st, label=lab.replace(",", " "))
            for _, c, st, lab in marks
        ],
        loc="lower center",
        ncol=3,
        frameon=False,
        fontsize=8,
        bbox_to_anchor=(0.5, -0.12),
    )
    fig.savefig(snakemake.output.sensitivity)
    plt.close(fig)
    logger.info("summary figures written")
