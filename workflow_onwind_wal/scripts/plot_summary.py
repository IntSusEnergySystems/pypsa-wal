# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Two summary charts:

``waterfall``    eligible land and installable capacity after each successive
                 constraint group, for both regions
``sensitivity``  installable capacity in the reference scenario across turbine
                 classes and capacity densities, against the benchmarks
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
    ref_density = cfg["reference_density"]
    ref_scenario = cfg["reference_scenario"]
    bench = cfg["benchmarks"]

    waterfall = pd.read_csv(snakemake.input.waterfall)
    summary = pd.read_csv(snakemake.input.summary)
    sens = pd.read_csv(snakemake.input.sensitivity)
    headline = json.loads(Path(snakemake.input.headline).read_text())
    dev = headline["developable"]

    # ------------------------------------------------------------------
    # Waterfall
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    labels = {"admin": "Wallonia (administrative)", "model": "PyPSA-Wal BEWAL node"}
    for ax, region in zip(axes, ["admin", "model"]):
        sub = waterfall[waterfall["region"] == region]
        x = np.arange(len(sub))
        # S0 is PyPSA-Eur's own specification, not a rung of the Walloon ladder;
        # colour it apart so the bars are not read as a single sequence.
        colors = ["#adb5bd" if not lad else "#2b8a3e" for lad in sub["in_ladder"]]
        ax.bar(x, sub["eligible_area_km2"], color=colors, width=0.62)
        for xi, (area, share) in enumerate(
            zip(sub["eligible_area_km2"], sub["share_of_region_pct"])
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
        ax.set_xticklabels(sub["scenario"], rotation=25, ha="right", fontsize=8)
        ax.set_ylabel("eligible area [km$^2$]")
        ax.set_title(labels[region])
        ax.set_ylim(0, sub["eligible_area_km2"].max() * 1.30)
        ax.spines[["top", "right"]].set_visible(False)

    axes[0].legend(
        handles=[
            Patch(facecolor="#2b8a3e", label="Walloon constraint ladder (cumulative)"),
            Patch(facecolor="#adb5bd", label="PyPSA-Eur default (separate specification)"),
        ],
        frameon=False,
        fontsize=8,
        loc="upper right",
    )
    fig.suptitle(
        "Land surviving each successive constraint set "
        f"({cfg['turbines'][ref_turbine]['label']})",
        y=1.01,
    )
    fig.savefig(snakemake.output.waterfall)
    plt.close(fig)

    # ------------------------------------------------------------------
    # Sensitivity
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)

    turbines = [t for t in cfg["turbines"] if isinstance(cfg["turbines"][t], dict)]
    densities = list(cfg["capacity_densities"])
    colors = {"pypsa_eur": "#adb5bd", "derived": "#2b8a3e", "dense": "#1c7ed6"}

    for ax, region in zip(axes, ["admin", "model"]):
        sub = sens[sens["region"] == region]
        width = 0.26
        x = np.arange(len(turbines))
        for k, dcase in enumerate(densities):
            vals, dens = [], []
            for t in turbines:
                row = sub[(sub["turbine"] == t) & (sub["density_case"] == dcase)]
                vals.append(float(row["p_nom_max_mw"].iloc[0]) if len(row) else np.nan)
                dens.append(
                    float(row["capacity_density_mw_km2"].iloc[0]) if len(row) else np.nan
                )
            pos = x + (k - (len(densities) - 1) / 2) * width
            ax.bar(
                pos,
                vals,
                width=width,
                color=colors.get(dcase, "0.6"),
            )
            for xi, v, d in zip(pos, vals, dens):
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
            [cfg["turbines"][t]["label"].replace(" (", "\n(") for t in turbines],
            fontsize=8,
        )
        ax.set_title(labels[region])
        ax.spines[["top", "right"]].set_visible(False)

    axes[0].set_ylabel("installable capacity [MW]")

    # Reference lines: the cap in force, the standing fleet, and the two
    # developability-screened figures that bracket the credible answer.
    marks = [
        (bench["model_p_nom_max_mw"], "crimson", "--",
         f"PyPSA-Wal cap today: {bench['model_p_nom_max_mw']:,} MW"),
        (dev["ge1_mw"], "#1864ab", "-.",
         f"developable (patches ≥ 1 array): {dev['ge1_mw']:,} MW"),
        (2559, "#5f3dc4", (0, (4, 2)),
         "SPW 2022 site-by-site: 2 559 MW"),
        (bench["installed_2024_mw"], "0.35", ":",
         f"installed end-2024: {bench['installed_2024_mw']:,} MW"),
    ]
    for ax in axes:
        for y, color, style, _ in marks:
            ax.axhline(y, color=color, linestyle=style, linewidth=1)
    axes[0].set_ylim(0, max(sens["p_nom_max_mw"]) * 1.12)

    handles = [
        Patch(facecolor=colors.get(d, "0.6"), label=f"density: {d.replace('_', ' ')}")
        for d in densities
    ] + [
        Line2D([], [], color=c, linestyle=st, label=lab.replace(",", " "))
        for _, c, st, lab in marks
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=8,
        bbox_to_anchor=(0.5, -0.14),
    )

    fig.suptitle(
        f"Installable capacity in scenario {ref_scenario} "
        "— sensitivity to turbine class and array spacing",
        y=1.02,
    )
    fig.savefig(snakemake.output.sensitivity)
    plt.close(fig)
    logger.info("summary figures written")
