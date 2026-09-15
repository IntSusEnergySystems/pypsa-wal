#!/usr/bin/env python3
"""Nuclear CAPEX tipping point — three alternative single-plot designs.

Replaces the pypsa2html sweep chart for slide use. That chart draws one line
per planning horizon against the swept cost, which is the honest default for a
sweep but a poor picture of *this* one: 2025, 2030 and 2040 are fixed by the
existing fleet and the Tihange 3 LTO, so three of the four lines are flat and
identical and only 2050 carries a result. Three quarters of the ink says
nothing, and the flat lines lie on top of each other.

Each design below therefore throws the constant horizons away — or states their
constancy once — and spends the whole plot on the question the sweep was run to
answer: **at what investment cost does the optimiser choose to build new
Walloon nuclear?**

    ramp     Capacity in 2050 against the swept cost, with the LTO floor as a
             baseline band, the threshold shaded, and the central scenario's
             own cost assumption marked. Closest to the original; the most
             complete and the least interpreted.
    gauge    One cost axis split into "builds new nuclear" and "builds none",
             with the gap between the central assumption and the threshold
             called out as a single number. The most slide-like; drops the
             capacity detail to a strip.
    matrix   The whole sweep as a labelled grid, horizons x cost. Compact and
             complete, and it shows *why* the line chart looked broken — only
             the 2050 row varies.

What the runs say (September 2026 batch, BEWAL, GW_e)::

    cost EUR2025/kW_e   2025   2030   2040   2050
    4500               1.992  1.030  1.030  3.000   <- full envelope built
    5500               1.992  1.030  1.030  2.144   <- about half
    6000 .. 9500       1.992  1.030  1.030  1.030   <- nothing new

The central scenario assumes **9 500 EUR2025/kW_e** and still carries 3.0 GW in
2050 — because the TIMES trajectory pins it there, not because the optimiser
chose it. That gap is the point of the sweep, and every design marks it.

Usage
-----
::

    python scripts/walloon_scripts/plot_nuclear_tipping.py \\
        --runs results/walloon/scen_nuctip_*  --style ramp --lang fr

    # re-render instantly from the extracted table instead of the networks
    python scripts/walloon_scripts/plot_nuclear_tipping.py \\
        --table docs/figures/nuclear_tipping.csv --style gauge

Reading the networks takes ~1 min per horizon set; the extracted table is
written next to the figure so design iterations need no second pass. ``--style
all`` writes all three.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Rectangle  # noqa: E402

# House palette, shared with compare_weather_years.py / plot_cost_segments.py.
BUILD = "#2a78d6"   # capacity the optimiser chooses to build
FLOOR = "#b9b8b2"   # the LTO plant, there in every run
HARD = "#e34948"    # the central scenario's assumption, and the threshold
INK = "#0b0b0b"
INK2 = "#52514e"
INK3 = "#8a8a85"
GRID = "#e3e2de"
SURFACE = "#fcfcfb"
TINT = "#f4eee7"

L10N = {
    "fr": {
        "title_ramp": "À quel coût le nucléaire devient-il rentable ?",
        "title_gauge": "Le nucléaire n'est jamais choisi au coût retenu",
        "title_matrix": "Capacité nucléaire wallonne — balayage du coût d'investissement",
        "sub_ramp": "Capacité nucléaire wallonne en {hz} selon le coût d'investissement "
                    "du neuf — {n} runs PyPSA",
        "sub_gauge": "Coût d'investissement overnight du nucléaire neuf — "
                     "ce que le scénario central suppose, et ce qu'il faudrait",
        "sub_matrix": "GW électriques installés en Wallonie — {n} runs × {h} horizons",
        "xlabel": "Coût d'investissement overnight du nucléaire neuf [€2025/kW_e]",
        "ylabel": "GW électriques",
        "floor": "Tihange 3 (LTO) — {v} GW, présent dans tous les cas",
        "new": "Nouveau nucléaire construit par l'optimiseur",
        "threshold": "seuil",
        "central": "hypothèse centrale\n{v} €/kW",
        "zone_yes": "l'optimiseur construit\ndu nouveau nucléaire",
        "zone_no": "il n'en construit aucun",
        "gap": "−{v} %",
        "gap_note": "de baisse nécessaire pour que\nle nucléaire neuf soit choisi",
        "headline": "Au coût retenu dans le scénario central, l'optimiseur ne construit\n"
                    "aucun nouveau nucléaire. Les 3 GW de 2050 sont imposés par TIMES.",
        "row_note": "Seul 2050 réagit : avant, le parc est fixé par l'existant et la LTO.",
        "footnote": "Balayage nuclear tipping-point, batch cabinet de septembre 2026 "
                    "(scen_nuctip_*). Capacités électriques nettes, nœud BEWAL.",
        "none": "aucun",
    },
    "en": {
        "title_ramp": "At what cost does new nuclear become economic?",
        "title_gauge": "New nuclear is never chosen at the assumed cost",
        "title_matrix": "Walloon nuclear capacity — investment cost sweep",
        "sub_ramp": "Walloon nuclear capacity in {hz} against the investment cost of "
                    "new build — {n} PyPSA runs",
        "sub_gauge": "Overnight investment cost of new nuclear — what the central "
                     "scenario assumes, and what it would take",
        "sub_matrix": "Installed GW electric in Wallonia — {n} runs × {h} horizons",
        "xlabel": "Overnight investment cost of new nuclear [EUR2025/kW_e]",
        "ylabel": "GW electric",
        "floor": "Tihange 3 (LTO) — {v} GW, present in every run",
        "new": "New nuclear the optimiser chooses to build",
        "threshold": "threshold",
        "central": "central assumption\n{v} EUR/kW",
        "zone_yes": "the optimiser builds\nnew nuclear",
        "zone_no": "it builds none",
        "gap": "−{v}%",
        "gap_note": "cost reduction needed before\nnew nuclear is chosen",
        "headline": "At the cost the central scenario assumes, the optimiser builds no\n"
                    "new nuclear. Its 3 GW in 2050 are imposed by TIMES.",
        "row_note": "Only 2050 responds: before it, the fleet is set by the existing "
                    "plant and the LTO.",
        "footnote": "Nuclear tipping-point sweep, September 2026 cabinet batch "
                    "(scen_nuctip_*). Net electrical capacity, node BEWAL.",
        "none": "none",
    },
}


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def read_runs(runs: list[Path], horizons: list[str]) -> pd.DataFrame:
    """Electrical nuclear capacity per (swept cost, horizon), in GW_e.

    The nuclear Link's ``p_nom_opt`` is *thermal* input; multiplying by the
    link efficiency is what turns it into the electrical figure every other
    chart and every reader means by "GW of nuclear".
    """
    import pypsa  # imported late: --table skips it entirely

    rows: dict[float, dict[str, float]] = {}
    for run in runs:
        match = re.search(r"(\d+)\s*$", run.name)
        if not match:
            raise ValueError(f"cannot read a swept cost from the run name {run.name!r}")
        cost = float(match.group(1))
        out: dict[str, float] = {}
        for horizon in horizons:
            hits = sorted((run / "networks").glob(f"*{horizon}.nc"))
            if not hits:
                raise FileNotFoundError(f"no network for {horizon} under {run}/networks")
            n = pypsa.Network(str(hits[-1]))
            link = n.links[(n.links.carrier == "nuclear")
                           & n.links.bus1.str.startswith("BEWAL")]
            out[horizon] = float((link.p_nom_opt * link.efficiency).sum() / 1e3)
        rows[cost] = out
    frame = pd.DataFrame(rows).T.sort_index()
    frame.index.name = "cost"
    return frame


def floor_level(frame: pd.DataFrame, horizon: str) -> float:
    """Capacity every run carries — the LTO plant, i.e. the cheapest outcome."""
    return float(frame[horizon].min())


def threshold(frame: pd.DataFrame, horizon: str) -> tuple[float, float]:
    """(last cost that still builds, first cost that builds nothing).

    The sweep is six points, so the tipping price is an interval, not a number.
    Quoting its upper end is the conservative claim: *at least* this much of a
    reduction is needed.
    """
    floor = floor_level(frame, horizon)
    built = frame.index[frame[horizon] > floor + 1e-6]
    none = frame.index[frame[horizon] <= floor + 1e-6]
    lo = float(built.max()) if len(built) else float(frame.index.min())
    hi = float(none.min()) if len(none) else float(frame.index.max())
    return lo, hi


def dec(v: float, dp: int, lang: str) -> str:
    return f"{v:.{dp}f}".replace(".", ",") if lang == "fr" else f"{v:.{dp}f}"


def money(v: float, lang: str) -> str:
    return f"{v:,.0f}".replace(",", " " if lang == "fr" else ",")


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
# design 1 — the ramp
# --------------------------------------------------------------------------- #
def draw_ramp(frame, T, lang, horizon, central):
    costs = frame.index.to_numpy(dtype=float)
    caps = frame[horizon].to_numpy(dtype=float)
    base = floor_level(frame, horizon)
    lo, hi = threshold(frame, horizon)

    fig = plt.figure(figsize=(11.6, 6.3))
    ax = fig.add_axes([0.075, 0.155, 0.905, 0.60])
    span = (costs.min() - 450, max(costs.max(), central) + 700)
    ax.set_xlim(*span)
    ax.set_ylim(0, caps.max() * 1.30)

    ax.axhspan(0, base, color=FLOOR, alpha=0.35, zorder=1)
    ax.axvspan(lo, hi, color=HARD, alpha=0.10, zorder=1)
    ax.fill_between(costs, base, caps, color=BUILD, alpha=0.22, zorder=2)
    ax.plot(costs, caps, color=BUILD, lw=2.6, zorder=4,
            marker="o", markersize=9, markerfacecolor=BUILD,
            markeredgecolor=SURFACE, markeredgewidth=1.6)
    ax.axhline(base, color=INK2, lw=1.1, ls=(0, (5, 3)), zorder=3)

    for cost, cap in zip(costs, caps):
        extra = cap - base
        ax.annotate(dec(cap, 2, lang) if extra > 1e-6 else dec(cap, 2, lang),
                    xy=(cost, cap), xytext=(0, 13), textcoords="offset points",
                    ha="center", fontsize=10.5, weight="bold",
                    color=BUILD if extra > 1e-6 else INK3, zorder=6)
        if extra > 1e-6:
            ax.annotate(f"+{dec(extra, 2, lang)} GW", xy=(cost, (cap + base) / 2),
                        xytext=(14, 0), textcoords="offset points", va="center",
                        ha="left", fontsize=10, weight="bold", color=BUILD, zorder=6,
                        bbox=dict(facecolor=SURFACE, edgecolor="none",
                                  boxstyle="round,pad=0.25", alpha=0.85))

    ax.text(span[0] + 120, base * 0.46, T["floor"].format(v=dec(base, 2, lang)),
            fontsize=10, color=INK2, va="center", zorder=5)
    ax.text((lo + hi) / 2, caps.max() * 1.20, T["threshold"], ha="center",
            fontsize=10, color=HARD, style="italic", zorder=6)
    ax.annotate("", xy=(lo, caps.max() * 1.15), xytext=(hi, caps.max() * 1.15),
                arrowprops=dict(arrowstyle="<->", color=HARD, lw=1.1), zorder=6)

    ax.axvline(central, color=HARD, lw=1.6, ls=(0, (4, 3)), zorder=5)
    ax.text(central - 170, caps.max() * 0.72,
            T["central"].format(v=money(central, lang)), ha="right", va="center",
            fontsize=10.5, weight="bold", color=HARD, zorder=6)

    ax.set_xticks(costs, [money(c, lang) for c in costs])
    ax.set_xlabel(T["xlabel"], color=INK2, fontsize=10.5, labelpad=8)
    ax.set_ylabel(T["ylabel"], color=INK2, fontsize=10.5)
    ax.grid(axis="y", color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    bare_axes(ax)

    box = ax.text(span[1] - 200, caps.max() * 0.98, T["headline"], ha="right",
                  va="top", fontsize=11, color=INK, zorder=7, linespacing=1.5)
    box.set_bbox(dict(facecolor=TINT, edgecolor="none", boxstyle="round,pad=0.6"))
    return fig


# --------------------------------------------------------------------------- #
# design 2 — the gauge
# --------------------------------------------------------------------------- #
def draw_gauge(frame, T, lang, horizon, central):
    costs = frame.index.to_numpy(dtype=float)
    caps = frame[horizon].to_numpy(dtype=float)
    base = floor_level(frame, horizon)
    lo, hi = threshold(frame, horizon)
    cut = hi                       # conservative: the cheapest cost that builds nothing
    drop = 100 * (1 - cut / central)

    fig = plt.figure(figsize=(11.6, 5.9))
    ax = fig.add_axes([0.055, 0.095, 0.90, 0.70])
    span = (costs.min() - 700, max(costs.max(), central) + 700)
    ax.set_xlim(*span)
    ax.set_ylim(-1.95, 1.75)
    ax.axis("off")
    scale = 0.55 / max(caps.max() - base, 1e-9)   # GW -> axis units for the stubs

    # the cost axis, split into the two regimes
    ax.add_patch(Rectangle((span[0], -0.16), cut - span[0], 0.32, color=BUILD,
                           alpha=0.85, zorder=3))
    ax.add_patch(Rectangle((cut, -0.16), span[1] - cut, 0.32, color=FLOOR,
                           alpha=0.55, zorder=3))
    ax.text(span[0] + 180, 1.12, T["zone_yes"], fontsize=12, color=BUILD,
            weight="bold", va="bottom", linespacing=1.45)
    ax.text(cut + (span[1] - cut) * 0.38, 1.12, T["zone_no"], fontsize=12,
            color=INK2, weight="bold", va="bottom", ha="center")

    # the swept points, with what each one builds
    for cost, cap in zip(costs, caps):
        extra = cap - base
        ax.plot([cost], [0.0], marker="o", markersize=9, color=SURFACE,
                markeredgecolor=INK2, markeredgewidth=1.4, zorder=5)
        ax.text(cost, -0.30, money(cost, lang), ha="center", va="top",
                fontsize=10.5, color=INK2)
        if extra > 1e-6:
            ax.add_patch(Rectangle((cost - 135, 0.20), 270, extra * scale,
                                   color=BUILD, zorder=4))
            ax.text(cost, 0.26 + extra * scale, f"+{dec(extra, 2, lang)} GW",
                    ha="center", va="bottom", fontsize=10, color=BUILD,
                    weight="bold")
        else:
            ax.text(cost, 0.26, T["none"], ha="center", va="bottom", fontsize=10,
                    color=INK3, style="italic")

    # the gap that is the whole point
    ax.add_patch(FancyArrowPatch((central, -0.78), (cut, -0.78),
                                 arrowstyle="<|-|>", mutation_scale=16,
                                 color=HARD, lw=1.6, zorder=6))
    ax.plot([central, central], [-0.86, 0.16], color=HARD, lw=1.6,
            ls=(0, (4, 3)), zorder=5)
    ax.plot([cut, cut], [-0.86, 0.16], color=HARD, lw=1.6, ls=(0, (4, 3)), zorder=5)
    ax.text((central + cut) / 2, -0.96, T["gap"].format(v=dec(drop, 0, lang)),
            ha="center", va="top", fontsize=30, weight="bold", color=HARD)
    ax.text((central + cut) / 2, -1.46, T["gap_note"], ha="center", va="top",
            fontsize=11, color=INK2, linespacing=1.45)
    ax.text(central, 1.66, T["central"].format(v=money(central, lang)),
            ha="center", va="top", fontsize=11.5, weight="bold", color=HARD,
            linespacing=1.45)
    ax.annotate("", xy=(central, 0.52), xytext=(central, 1.16),
                arrowprops=dict(arrowstyle="-|>", color=HARD, lw=1.5))
    return fig


# --------------------------------------------------------------------------- #
# design 3 — the matrix
# --------------------------------------------------------------------------- #
def draw_matrix(frame, T, lang, horizon, central):
    horizons = list(frame.columns)
    costs = frame.index.to_numpy(dtype=float)
    base = floor_level(frame, horizon)
    top = float(frame.to_numpy().max())

    fig = plt.figure(figsize=(11.6, 5.3))
    ax = fig.add_axes([0.105, 0.175, 0.875, 0.545])
    ax.set_xlim(-0.5, len(costs) - 0.5)
    ax.set_ylim(len(horizons) - 0.35, -1.15)
    ax.axis("off")

    for r, hz in enumerate(horizons):
        for c, cost in enumerate(costs):
            v = float(frame.loc[cost, hz])
            built = hz == horizon and v > base + 1e-6
            shade = 0.10 + 0.72 * (v - base) / max(top - base, 1e-9) if built else 0.0
            ax.add_patch(Rectangle((c - 0.46, r - 0.40), 0.92, 0.80, zorder=2,
                                   facecolor=BUILD if built else "#eeeeea",
                                   alpha=shade if built else 1.0, edgecolor=SURFACE,
                                   linewidth=2.0))
            ax.text(c, r, dec(v, 2, lang), ha="center", va="center", fontsize=11.5,
                    color=INK if built else INK2,
                    weight="bold" if built else "normal", zorder=4)
        ax.text(-0.72, r, hz, ha="right", va="center", fontsize=11.5, zorder=4,
                weight="bold" if hz == horizon else "normal",
                color=INK if hz == horizon else INK2)
    for c, cost in enumerate(costs):
        ax.text(c, -0.62, money(cost, lang), ha="center", va="bottom",
                fontsize=11, color=HARD if cost == central else INK2,
                weight="bold" if cost == central else "normal", zorder=4)
    if central in costs:
        c = int(np.where(costs == central)[0][0])
        ax.add_patch(Rectangle((c - 0.49, -0.46), 0.98, len(horizons) - 0.08,
                               fill=False, edgecolor=HARD, lw=1.8, zorder=5))
        ax.text(c, -1.02, T["central"].format(v=money(central, lang)).split("\n")[0],
                ha="center", va="bottom", fontsize=10.5, weight="bold", color=HARD,
                zorder=6)
    ax.text(-0.5, len(horizons) - 0.52, T["row_note"], ha="left", va="top",
            fontsize=10.5, color=INK2, style="italic")
    return fig


DESIGNS = {"ramp": draw_ramp, "gauge": draw_gauge, "matrix": draw_matrix}


# --------------------------------------------------------------------------- #
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", type=Path, nargs="+", default=None,
                   help="sweep result trees; the swept cost is read off the name")
    p.add_argument("--table", type=Path, default=None,
                   help="skip the networks and read a previously extracted CSV")
    p.add_argument("--horizons", nargs="+", default=["2025", "2030", "2040", "2050"])
    p.add_argument("--horizon", default="2050", help="the horizon the sweep moves")
    p.add_argument("--central", type=float, default=9500.0,
                   help="cost assumed by the central scenario, marked on every design")
    p.add_argument("--style", default="all", choices=[*DESIGNS, "all"])
    p.add_argument("--lang", choices=sorted(L10N), default="fr")
    p.add_argument("--outdir", type=Path, default=Path("docs/figures"))
    args = p.parse_args()

    if args.table:
        frame = pd.read_csv(args.table, index_col=0)
        frame.columns = [str(c) for c in frame.columns]
    else:
        runs = args.runs or sorted(Path("results/walloon").glob("scen_nuctip_*"))
        if not runs:
            p.error("no sweep runs found; pass --runs or --table")
        frame = read_runs(list(runs), args.horizons)
    if args.horizon not in frame.columns:
        p.error(f"--horizon {args.horizon} not in {list(frame.columns)}")

    args.outdir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.outdir / "nuclear_tipping.csv")
    T = L10N[args.lang]
    lo, hi = threshold(frame, args.horizon)
    style()

    wanted = list(DESIGNS) if args.style == "all" else [args.style]
    for name in wanted:
        fig = DESIGNS[name](frame, T, args.lang, args.horizon, args.central)
        subtitle = T[f"sub_{name}"].format(hz=args.horizon, n=len(frame),
                                           h=len(frame.columns))
        header(fig, T[f"title_{name}"], subtitle, T["footnote"])
        suffix = "" if args.lang == "fr" else f"_{args.lang}"
        stem = args.outdir / f"nuclear_tipping_{name}{suffix}"
        for ext in ("png", "pdf", "svg"):
            fig.savefig(f"{stem}.{ext}", dpi=300)
        plt.close(fig)
        print(f"written: {stem}.png / .pdf / .svg")

    print(f"\nthreshold: new build at <= {lo:.0f}, none from {hi:.0f} "
          f"EUR2025/kW_e; central assumption {args.central:.0f} "
          f"(-{100 * (1 - hi / args.central):.0f} % needed)")
    print(frame.round(3).to_string())


if __name__ == "__main__":
    main()
