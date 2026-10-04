# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
# SPDX-License-Identifier: MIT
"""
Summary charts of the report.

``funnel.png``       land left after each family of rules, then the park rule
``gisements.png``    technical and reference capacity by gisement group
``sensitivity.png``  every case as a change to the reference capacity, by
                     group, ranked; policy cases that open farmland are shown
                     on their own axis because they are an order of magnitude
                     larger than the rest (one axis per chart, no dual axis)
"""

import json
import logging
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from plot_maps import GROUPS  # noqa: E402

logger = logging.getLogger(__name__)

BG = "#F5F0E8"
INK = "#222222"
MUTED = "#6b675f"
GRID = "#d9d3c7"
UP = "#b5452c"     # warm: a choice that raises the potential
DOWN = "#2f6690"   # cool: a choice that lowers it
LABELS = {
    "region": "Walloon Region",
    "nature": "− nature",
    "forest": "− forest and green zones",
    "landscape": "− landscape and heritage",
    "hazard": "− natural hazards",
    "built": "− buildings and networks",
    "cover": "− woodland (land cover)",
    "terrain": "− slope, north-facing slopes",
    "water": "− water",
    "park_rule": "− parks < 1 ha or < 60 m wide",
}


def style(ax):
    ax.set_facecolor(BG)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


if __name__ == "__main__":
    if "snakemake" not in globals():
        raise SystemExit("run through snakemake")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        stream=open(snakemake.log[0], "w"))  # noqa: SIM115

    head = json.loads(open(snakemake.input.headline).read())

    # ---- funnel --------------------------------------------------------------
    steps = [("region", head["region_ha"])] + [(f["family"], f["left_ha"]) for f in head["funnel"]]
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=200)
    fig.patch.set_facecolor(BG)
    style(ax)
    ys = list(range(len(steps)))[::-1]
    for y, (k, v) in zip(ys, steps):
        ax.barh(y, v / 100, height=0.62, color="#2B8A3E" if k in ("region", "park_rule") else "#8fbf9a")
        ax.text(v / 100 + 150, y, f"{v / 100:,.0f} km²".replace(",", " "), va="center",
                fontsize=8, color=INK)
    ax.set_yticks(ys, [LABELS.get(k, k) for k, _ in steps], fontsize=8, color=INK)
    ax.set_xlabel("land left, km²", fontsize=8, color=MUTED)
    ax.set_xlim(0, head["region_ha"] / 100 * 1.15)
    fig.tight_layout()
    fig.savefig(snakemake.output.funnel, facecolor=BG)
    plt.close(fig)

    # ---- gisements -------------------------------------------------------------
    g = head["gisements"]
    rows = []
    for colour, label, members in GROUPS:
        rows.append({"label": label.split(":")[0], "colour": colour,
                     "technical": sum(g[m]["technical_mwc"] for m in members if m in g) / 1e3,
                     "reference": sum(g[m]["policy_mwc"] for m in members if m in g) / 1e3})
    df = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), dpi=200, sharey=True)
    fig.patch.set_facecolor(BG)
    for ax, col, title in zip(axes, ["technical", "reference"],
                              ["Technical: every eligible hectare", "Reference: what the rules open"]):
        style(ax)
        y = range(len(df))[::-1]
        ax.barh(list(y), df[col], color=df["colour"], height=0.62)
        for yy, v in zip(y, df[col]):
            ax.text(v + df[col].max() * 0.02, yy, f"{v:,.1f}".replace(",", " "), va="center",
                    fontsize=8, color=INK)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.set_xlabel("GWc", fontsize=8, color=MUTED)
        ax.set_xlim(0, max(df[col].max() * 1.25, 0.1))
    axes[0].set_yticks(list(range(len(df))[::-1]), df["label"], fontsize=8, color=INK)
    fig.tight_layout()
    fig.savefig(snakemake.output.gisements, facecolor=BG)
    plt.close(fig)

    # ---- sensitivity -------------------------------------------------------------
    s = pd.read_csv(snakemake.input.sensitivity)
    ref = float(s.loc[s["case"] == "reference", "policy_mwc"].iloc[0])
    s = s[s["case"] != "reference"].copy()
    s["delta_gw"] = (s["policy_mwc"] - ref) / 1e3
    big = s["case"].str.startswith("agri_") & ~s["case"].eq("agri_zone_poor_soils")
    parts = [("Opening farmland (policy)", s[big]), ("Every other choice", s[~big])]
    fig, axes = plt.subplots(2, 1, figsize=(8.5, 8.5), dpi=200,
                             gridspec_kw={"height_ratios": [max(1, big.sum()), max(1, (~big).sum())]})
    fig.patch.set_facecolor(BG)
    for ax, (title, d) in zip(axes, parts):
        style(ax)
        d = d.sort_values("delta_gw")
        y = range(len(d))
        ax.barh(list(y), d["delta_gw"], color=[UP if v > 0 else DOWN for v in d["delta_gw"]],
                height=0.62)
        span = max(abs(d["delta_gw"]).max(), 0.05)
        for yy, v, p in zip(y, d["delta_gw"], d["delta_pct"]):
            ax.text(v + (0.02 if v >= 0 else -0.02) * span, yy,
                    f"{v:+,.2f} GWc ({p:+.0f} %)".replace(",", " "), va="center",
                    ha="left" if v >= 0 else "right", fontsize=7, color=INK)
        ax.set_yticks(list(y), [f"{l}" for l in d["label"]], fontsize=7, color=INK)
        ax.axvline(0, color=MUTED, linewidth=0.8)
        ax.set_xlim(-1.7 * span, 2.3 * span)
        ax.set_title(title, fontsize=9, color=INK, loc="left")
        ax.set_xlabel(f"change to the reference ({ref / 1e3:.1f} GWc), GWc", fontsize=8, color=MUTED)
    fig.tight_layout()
    fig.savefig(snakemake.output.sensitivity, facecolor=BG)
    plt.close(fig)
