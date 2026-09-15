#!/usr/bin/env python3
"""Walloon energy self-sufficiency — three alternative single-plot designs.

Replaces the pypsa2html self-sufficiency chart for slide use. That chart is a
plain two-line time series (primary energy / electricity, in %) plus a
separate dropdown-switched bar chart for the TWh balance behind it — correct,
but two disconnected views and not designed for a cabinet audience.

It also used to run on the wrong nuclear convention. ``features.nuclear_primary``
has three settings (``docs`` in ``pypsa2html.indicators.NUCLEAR_PRIMARY_LABELS``):
fuel heat imported (``uranium``, the IEA convention, ~3x electrical output),
electrical output counted as domestic (``electricity``), or electrical output
still counted as an import (``electricity_import``) because the fuel is not
mined here. Only the *origin* changes between the last two: ``electricity``
moves nuclear's kWh across the domestic/import line as well as resizing it,
which roughly doubles Wallonia's headline independence and reads as a bigger
effect than it is. ``electricity_import`` changes only the magnitude, and is
the agreed convention (2026-09-15) — see ``config/pypsa2html.yaml``.

    trend    Both self-sufficiency ratios (primary energy, electricity) across
              all 4 horizons, on a shared 0-100+ % axis. The most complete
              view, closest to the original.
    gauges   One semi-donut gauge per horizon for primary self-sufficiency,
              reading left to right as a timeline, with the electricity figure
              as a small caption underneath. The most slide-like.
    bars     Domestic production vs. net imports in TWh, primary energy and
              electricity side by side, self-sufficiency % labelled above each
              bar. Grounds the ratios in real magnitudes.

What the runs say (central scenario, node BEWAL, ``electricity_import``
convention)::

    year                        2025   2030   2040   2050
    primary self-sufficiency   20.0%  20.7%  34.8%  45.0%
    electricity self-suff.    101.1%  95.2%  93.1%  89.9%
    primary energy, total TWh  122.4  121.4  122.2  122.3   <- stable
    electricity demand, TWh     23.9   31.7   57.3   73.2   <- triples

Two findings worth putting on the slide together: primary self-sufficiency
roughly doubles because total primary energy demand is flat (~122 TWh/year
throughout) while its domestic share grows (24.5 -> 55.0 TWh) as electrified
end-uses replace imported fossil fuels. Electricity self-sufficiency *falls*
slightly (101% -> 90%) even though domestic generation more than triples,
because domestic demand grows a little faster than domestic supply. Neither
number tells the whole story alone.

Usage
-----
::

    python scripts/walloon_scripts/plot_self_sufficiency.py --style trend --lang fr

    # re-render instantly from the extracted table instead of the networks
    python scripts/walloon_scripts/plot_self_sufficiency.py \\
        --table docs/figures/self_sufficiency.csv --style gauges

Reading the networks takes about a minute (four horizons' worth of flow
extraction); the extracted table is written next to the figures so design
iterations need no second pass. ``--style all`` writes all three.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Wedge  # noqa: E402

# House palette, shared with plot_nuclear_tipping.py / compare_weather_years.py.
PRIMARY = "#2a78d6"    # primary-energy self-sufficiency (the headline metric)
ELEC = "#0ea5a3"       # electricity self-sufficiency (context, roughly stable)
DOMESTIC = "#32bf84"   # domestic production -- matches pypsa2html's own "prod" colour
IMPORTS = "#ffb07c"    # net imports -- matches pypsa2html's own "imp" colour
HARD = "#e34948"       # the number that matters
INK = "#0b0b0b"
INK2 = "#52514e"
INK3 = "#8a8a85"
GRID = "#e3e2de"
SURFACE = "#fcfcfb"
TINT = "#f4eee7"

#: Translation of pypsa2html's ``NUCLEAR_PRIMARY_LABELS`` keys for the footnote.
MODE_LABELS = {
    "fr": {
        "uranium": "combustible importé (convention IEA)",
        "electricity": "électricité, comptée domestique",
        "electricity_import": "électricité, comptée importée",
    },
    "en": {
        "uranium": "imported fuel heat (IEA convention)",
        "electricity": "electricity, counted domestic",
        "electricity_import": "electricity, counted imported",
    },
}

L10N = {
    "fr": {
        "title_trend": "L'indépendance énergétique wallonne, à deux vitesses",
        "sub_trend": "Autosuffisance en énergie primaire et en électricité — "
                     "scénario central, nœud BEWAL",
        "title_gauges": "L'autosuffisance énergétique wallonne double d'ici 2050",
        "sub_gauges": "Part de l'énergie primaire couverte par la production "
                      "wallonne, par horizon",
        "title_bars": "D'où vient l'énergie consommée en Wallonie ?",
        "sub_bars": "Production domestique et importations nettes, énergie "
                    "primaire et électricité — TWh/an",
        "footnote": "Convention nucléaire : {mode}. Scénario central, nœud BEWAL "
                    "— batch cabinet de septembre 2026.",
        "label_primary": "Énergie primaire",
        "label_electricity": "Électricité",
        "label_domestic": "Production domestique",
        "label_import": "Importations nettes",
        "xlabel": "Horizon",
        "ylabel_pct": "% d'autosuffisance",
        "ylabel_twh": "TWh/an",
        "gap_note": "écart entre les deux\nindicateurs",
        "gauge_caption": "{dom} / {tot} TWh domestiques\nÉlec. {el} %",
        "delta": "+{v} points\nentre 2025 et 2050",
    },
    "en": {
        "title_trend": "Walloon energy independence, at two speeds",
        "sub_trend": "Primary-energy and electricity self-sufficiency — "
                     "central scenario, node BEWAL",
        "title_gauges": "Walloon energy self-sufficiency doubles by 2050",
        "sub_gauges": "Share of primary energy covered by Walloon production, "
                      "by horizon",
        "title_bars": "Where does Wallonia's energy come from?",
        "sub_bars": "Domestic production and net imports, primary energy and "
                    "electricity — TWh/yr",
        "footnote": "Nuclear convention: {mode}. Central scenario, node BEWAL "
                    "— September 2026 cabinet batch.",
        "label_primary": "Primary energy",
        "label_electricity": "Electricity",
        "label_domestic": "Domestic production",
        "label_import": "Net imports",
        "xlabel": "Horizon",
        "ylabel_pct": "% self-sufficiency",
        "ylabel_twh": "TWh/yr",
        "gap_note": "gap between the two\nindicators",
        "gauge_caption": "{dom} / {tot} TWh domestic\nElec. {el} %",
        "delta": "+{v} points\nfrom 2025 to 2050",
    },
}


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def read_data(
    scenario: str, node: str, config_path: Path, mode: str | None, horizons: list[int]
) -> tuple[pd.DataFrame, str]:
    """Self-sufficiency ratios and TWh balances for one scenario/node.

    Imported late: ``--table`` skips pypsa2html (and the ~1 min network read)
    entirely.
    """
    from pypsa2html import indicators as ind
    from pypsa2html.config import load_config
    from pypsa2html.context import build_context

    config = load_config(config_path)
    ctx = build_context(config, scenario_name=scenario)
    if mode:
        ctx.config.features.nuclear_primary = mode
    detail = ind.self_sufficiency_detail(ctx, node=node)
    if detail is None:
        raise RuntimeError(f"no self-sufficiency data for node {node!r} in scenario {scenario!r}")

    frame = pd.DataFrame(
        {
            "primary_ratio": detail.ratio["primary"],
            "electricity_ratio": detail.ratio["electricity"],
            "primary_domestic": detail.primary["domestic"],
            "primary_import": detail.primary["net_import"],
            "electricity_domestic": detail.electricity["domestic"],
            "electricity_import": detail.electricity["net_import"],
        }
    ).reindex(horizons)
    frame.index.name = "year"
    return frame, ind.nuclear_primary_mode(ctx)


def dec(v: float, dp: int, lang: str) -> str:
    return f"{v:.{dp}f}".replace(".", ",") if lang == "fr" else f"{v:.{dp}f}"


def style():
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
        "font.size": 10.5, "figure.autolayout": False, "text.color": INK,
        "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    })


def header(fig, title, subtitle, footnote):
    fig.text(0.055, 0.945, title, fontsize=17.5, weight="bold", color=INK)
    fig.text(0.055, 0.888, subtitle, fontsize=10.5, color=INK2)
    fig.text(0.055, 0.025, footnote, fontsize=8.5, color=INK3)


def bare_axes(ax):
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)


# --------------------------------------------------------------------------- #
# design 1 — the trend
# --------------------------------------------------------------------------- #
def draw_trend(frame, T, lang):
    years = frame.index.to_numpy(dtype=int)
    pe = frame["primary_ratio"].to_numpy(dtype=float)
    el = frame["electricity_ratio"].to_numpy(dtype=float)

    fig = plt.figure(figsize=(11.6, 6.3))
    ax = fig.add_axes([0.08, 0.155, 0.845, 0.60])
    ax.set_xlim(years.min() - 2.8, years.max() + 4.2)
    top = max(el.max(), pe.max()) * 1.20
    ax.set_ylim(0, top)

    ax.fill_between(years, pe, el, color=INK3, alpha=0.14, zorder=1)
    ax.axhline(100, color=INK3, lw=1.0, ls=(0, (2, 2)), zorder=1)
    ax.text(years.max() + 1.4, 100, "100%", fontsize=9, color=INK3, va="bottom", ha="left",
            zorder=6, bbox=dict(facecolor=SURFACE, edgecolor="none", pad=0.5))

    ax.plot(years, el, color=ELEC, lw=2.4, marker="o", markersize=8,
            markerfacecolor=ELEC, markeredgecolor=SURFACE, markeredgewidth=1.4, zorder=4)
    ax.plot(years, pe, color=PRIMARY, lw=2.8, marker="o", markersize=9,
            markerfacecolor=PRIMARY, markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=5)

    for x, y in zip(years, el):
        ax.annotate(dec(y, 0, lang), xy=(x, y), xytext=(0, 11), textcoords="offset points",
                    ha="center", fontsize=9.5, color=ELEC, weight="bold", zorder=6)
    for x, y in zip(years, pe):
        ax.annotate(dec(y, 0, lang), xy=(x, y), xytext=(0, -18), textcoords="offset points",
                    ha="center", fontsize=10.5, color=PRIMARY, weight="bold", zorder=6)

    ax.annotate(T["label_electricity"], xy=(years[-1], el[-1]), xytext=(14, 4),
                textcoords="offset points", ha="left", va="center", color=ELEC,
                fontsize=11.5, weight="bold", zorder=6)
    ax.annotate(T["label_primary"], xy=(years[-1], pe[-1]), xytext=(14, -6),
                textcoords="offset points", ha="left", va="center", color=PRIMARY,
                fontsize=11.5, weight="bold", zorder=6)

    mid = len(years) // 2
    gap_y = (pe[mid] + el[mid]) / 2
    ax.text(years[mid], gap_y, T["gap_note"], ha="center", va="center", fontsize=9,
            color=INK2, style="italic", zorder=6, linespacing=1.4,
            bbox=dict(facecolor=SURFACE, edgecolor="none", boxstyle="round,pad=0.3", alpha=0.85))

    ax.set_xticks(years)
    ax.set_xlabel(T["xlabel"], color=INK2, fontsize=10.5, labelpad=8)
    ax.set_ylabel(T["ylabel_pct"], color=INK2, fontsize=10.5)
    ax.grid(axis="y", color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    bare_axes(ax)
    return fig


# --------------------------------------------------------------------------- #
# design 2 — the gauges
# --------------------------------------------------------------------------- #
def draw_gauges(frame, T, lang):
    years = frame.index.tolist()
    n = len(years)
    pe = frame["primary_ratio"]
    el = frame["electricity_ratio"]
    dom = frame["primary_domestic"]
    tot = frame["primary_domestic"] + frame["primary_import"]

    fig = plt.figure(figsize=(11.6, 5.7))
    ax = fig.add_axes([0.03, 0.06, 0.94, 0.66])
    ax.set_xlim(-0.65, n - 0.35)
    ax.set_ylim(-0.42, 1.35)
    ax.axis("off")

    r = 0.40
    for i, y in enumerate(years):
        ratio = float(pe.loc[y])
        frac = min(ratio, 100) / 100.0
        ax.add_patch(Wedge((i, 0.0), r, 0, 180, width=r * 0.34, facecolor="#eeeeea",
                           edgecolor=SURFACE, linewidth=2.0, zorder=2))
        ax.add_patch(Wedge((i, 0.0), r, 180 - 180 * frac, 180, width=r * 0.34,
                           facecolor=PRIMARY, edgecolor=SURFACE, linewidth=2.0, zorder=3))
        ax.text(i, 0.145, f"{dec(ratio, 0, lang)}%", ha="center", va="center",
                fontsize=18.5, weight="bold", color=PRIMARY, zorder=4)
        ax.text(i, -0.10, str(y), ha="center", va="center", fontsize=12.5,
                weight="bold", color=INK, zorder=4)
        ax.text(i, -0.24, T["gauge_caption"].format(
                    dom=dec(float(dom.loc[y]), 0, lang), tot=dec(float(tot.loc[y]), 0, lang),
                    el=dec(float(el.loc[y]), 0, lang)),
                ha="center", va="top", fontsize=9, color=INK2, linespacing=1.55, zorder=4)

    ax.annotate("", xy=(n - 1, 0.66), xytext=(0, 0.66),
                arrowprops=dict(arrowstyle="-|>", color=HARD, lw=1.7), zorder=5)
    delta = float(pe.iloc[-1] - pe.iloc[0])
    ax.text((n - 1) / 2, 0.74, T["delta"].format(v=dec(delta, 0, lang)),
            ha="center", va="bottom", fontsize=13, weight="bold", color=HARD, linespacing=1.4)
    return fig


# --------------------------------------------------------------------------- #
# design 3 — the bars
# --------------------------------------------------------------------------- #
def draw_bars(frame, T, lang):
    years = frame.index.tolist()
    x = np.arange(len(years))
    width = 0.6

    fig = plt.figure(figsize=(11.6, 6.0))
    axp = fig.add_axes([0.075, 0.155, 0.40, 0.585])
    axe = fig.add_axes([0.575, 0.155, 0.40, 0.585])

    panels = (
        (axp, "primary_domestic", "primary_import", "primary_ratio", T["label_primary"]),
        (axe, "electricity_domestic", "electricity_import", "electricity_ratio",
         T["label_electricity"]),
    )
    for ax, dom_col, imp_col, ratio_col, title in panels:
        dom = frame[dom_col].to_numpy(dtype=float)
        imp = frame[imp_col].to_numpy(dtype=float)
        ratio = frame[ratio_col].to_numpy(dtype=float)
        total = dom + imp
        ceiling = max((dom + np.clip(imp, 0, None)).max(), total.max()) * 1.30

        ax.bar(x, dom, width, color=DOMESTIC, zorder=3, label=T["label_domestic"])
        ax.bar(x, imp, width, bottom=dom, color=IMPORTS, zorder=3, label=T["label_import"])
        for xi, t in zip(x, total):
            ax.plot([xi - width / 2, xi + width / 2], [t, t], color=INK, lw=1.3, zorder=5)
        for xi, r, t, d in zip(x, ratio, total, dom):
            ax.annotate(f"{dec(r, 0, lang)}%", xy=(xi, max(t, d)), xytext=(0, 8),
                        textcoords="offset points", ha="center", fontsize=10.5,
                        weight="bold", color=INK, zorder=6)

        ax.set_xticks(x, [str(y) for y in years])
        ax.set_ylim(0, ceiling)
        ax.set_ylabel(T["ylabel_twh"], color=INK2, fontsize=10)
        ax.set_title(title, fontsize=12.5, weight="bold", color=INK, pad=10)
        ax.grid(axis="y", color=GRID, lw=0.7, zorder=0)
        ax.set_axisbelow(True)
        bare_axes(ax)

    axp.legend(loc="upper left", frameon=False, fontsize=9.5)
    return fig


DESIGNS = {"trend": draw_trend, "gauges": draw_gauges, "bars": draw_bars}


# --------------------------------------------------------------------------- #
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scenario", default="scen_central")
    p.add_argument("--node", default="BEWAL")
    p.add_argument("--config", type=Path, default=Path("config/pypsa2html.yaml"))
    p.add_argument("--mode", choices=["uranium", "electricity", "electricity_import"],
                   default=None,
                   help="override features.nuclear_primary; default: whatever the config says")
    p.add_argument("--horizons", nargs="+", type=int, default=[2025, 2030, 2040, 2050])
    p.add_argument("--table", type=Path, default=None,
                   help="skip the live read, reuse a previously extracted CSV")
    p.add_argument("--style", default="all", choices=[*DESIGNS, "all"])
    p.add_argument("--lang", choices=sorted(L10N), default="fr")
    p.add_argument("--outdir", type=Path, default=Path("docs/figures"))
    args = p.parse_args()

    if args.table:
        frame = pd.read_csv(args.table, index_col="year")
        mode_used = args.mode or "electricity_import"
    else:
        frame, mode_used = read_data(
            args.scenario, args.node, args.config, args.mode, args.horizons
        )

    args.outdir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.outdir / "self_sufficiency.csv")
    T = L10N[args.lang]
    mode_label = MODE_LABELS[args.lang].get(mode_used, mode_used)
    style()

    wanted = list(DESIGNS) if args.style == "all" else [args.style]
    for name in wanted:
        fig = DESIGNS[name](frame, T, args.lang)
        header(fig, T[f"title_{name}"], T[f"sub_{name}"],
               T["footnote"].format(mode=mode_label))
        suffix = "" if args.lang == "fr" else f"_{args.lang}"
        stem = args.outdir / f"self_sufficiency_{name}{suffix}"
        for ext in ("png", "pdf", "svg"):
            fig.savefig(f"{stem}.{ext}", dpi=300)
        plt.close(fig)
        print(f"written: {stem}.png / .pdf / .svg")

    print(f"\nmode: {mode_used} ({mode_label})")
    print(frame.round(2).to_string())


if __name__ == "__main__":
    main()
