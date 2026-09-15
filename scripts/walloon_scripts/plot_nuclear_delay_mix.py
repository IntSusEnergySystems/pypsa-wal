#!/usr/bin/env python3
"""Reproduction of the cabinet slide comparing central vs. delayed-nuclear mix.

The original slide (built outside this repo) showed installed capacity and
electricity production, central scenario vs. nuclear delay, but its top
stacked segment was an unlabelled black hatch with no legend entry, and its
printed capacity totals silently excluded it. Tracing it back to the networks
(``scen_central`` / ``scen_retardnucleaire``) identifies it as ``CCGT CC`` --
gas combined-cycle plants fitted with carbon capture, a real carrier distinct
from the plain ``CCGT``/``OCGT`` that make up "Gaz". Summing only the
carriers that had a legend entry reproduces the original's printed capacity
totals almost exactly (e.g. 25.3 GW vs. the printed 25 for central 2050); the
true total, black segment included, is 27.9 GW -- about 10% more.

This script rebuilds the same chart -- same two-panel layout, same central
vs. delay comparison, same "central 2050 -> delayed 2050" callout -- with
every stacked segment in the legend (including the corrected "Gaz avec
captage" one) and the totals corrected to match. The right-hand commentary
box from the original is dropped, per instructions; the two panels use the
freed width instead.

Usage
-----
::

    python scripts/walloon_scripts/plot_nuclear_delay_mix.py --lang fr

    # re-render instantly from the extracted table instead of the networks
    python scripts/walloon_scripts/plot_nuclear_delay_mix.py \\
        --table docs/figures/nuclear_delay_mix.csv --lang fr

Reading 8 networks (2 scenarios x 4 horizons) takes a couple of minutes; the
extracted table is written next to the figure so layout iterations skip it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

INK = "#0b0b0b"
INK2 = "#52514e"
INK3 = "#8a8a85"
GRID = "#e3e2de"
SURFACE = "#fcfcfb"
HARD = "#e34948"
TINT = "#f4eee7"

#: (label_fr, label_en, colour, hatch, [(component_kind, [carrier, ...]), ...])
#: Stacking order is bottom -> top; the last entry is the segment that was
#: drawn unlabelled (in black) in the original.
GROUPS = [
    ("Gaz", "Gas", "#a6a6a6", None,
     [("link", ["CCGT", "OCGT", "urban central gas CHP"])]),
    ("Nucléaire", "Nuclear", "#f0a860", None,
     [("link", ["nuclear"])]),
    ("Solaire (sol)", "Solar (ground)", "#cdece0", None,
     [("gen", ["solar-hsat", "solar"])]),
    ("Solaire (toiture)", "Solar (rooftop)", "#2fb8a0", None,
     [("gen", ["solar rooftop"])]),
    ("Éolien", "Wind", "#1a8f74", None,
     [("gen", ["onwind"])]),
    ("Autres (hydraulique, biomasse, H2)", "Other (hydro, biomass, H2)", "#c9c2d9", None,
     [("gen", ["ror"]),
      ("link", ["urban central solid biomass CHP", "urban central solid biomass CHP CC",
                "H2 turbine", "H2 Fuel Cell"])]),
    ("Gaz avec captage (CCGT CC)", "Gas with carbon capture (CCGT CC)", "#1a1a1a", "///",
     [("link", ["CCGT CC", "urban central gas CHP CC"])]),
]

SCENARIOS = [
    ("scen_central", "Scénario central – 3GW", "Central scenario – 3GW"),
    ("scen_retardnucleaire", "Retard nucl.", "Nuclear delay"),
]
HORIZONS = [2025, 2030, 2040, 2050]

L10N = {
    "fr": {
        "panel_cap": "Capacité installée [GW]",
        "panel_gen": "Production d'électricité [TWh/an]",
        "delta": "+{v} %",
        "footnote": "Scénario central vs. retard nucléaire, nœud BEWAL, capacité et "
                    "production électriques. \"Gaz avec captage\" (CCGT CC) corrigé "
                    "dans le total le 2026-09-15 -- il ne l'était pas dans la version "
                    "d'origine.",
    },
    "en": {
        "panel_cap": "Installed capacity [GW]",
        "panel_gen": "Electricity production [TWh/yr]",
        "delta": "+{v}%",
        "footnote": "Central scenario vs. nuclear delay, node BEWAL, electrical "
                    "capacity and production. \"Gas with carbon capture\" (CCGT CC) "
                    "corrected into the total 2026-09-15 -- it was not in the "
                    "original version.",
    },
}


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def _cap_and_gen(n, kind: str, carriers: list[str]) -> tuple[float, float]:
    if kind == "gen":
        sel = n.generators[n.generators.bus.isin(["BEWAL", "BEWAL low voltage"])]
        sel = sel[sel.carrier.isin(carriers)]
        cap_gw = sel.p_nom_opt.sum() / 1e3
        p = n.generators_t.p[sel.index] if len(sel) else pd.DataFrame(index=n.snapshots)
    else:
        sel = n.links[(n.links.bus1 == "BEWAL") & n.links.carrier.isin(carriers)]
        cap_gw = (sel.p_nom_opt * sel.efficiency).sum() / 1e3
        p = -n.links_t.p1[sel.index] if len(sel) else pd.DataFrame(index=n.snapshots)
    gen_twh = 0.0
    if len(p.columns):
        gen_twh = p.multiply(n.snapshot_weightings.generators, axis=0).sum().sum() / 1e6
    return cap_gw, gen_twh


def read_data(results_dir: Path) -> pd.DataFrame:
    """Capacity (GW) and generation (TWh) per scenario/year/group.

    Imported late: ``--table`` skips pypsa (and the multi-minute network
    read) entirely.
    """
    import pypsa

    rows = []
    for scen, *_ in SCENARIOS:
        for horizon in HORIZONS:
            path = results_dir / scen / "networks" / f"base_s_adm___{horizon}.nc"
            n = pypsa.Network(str(path))
            for label_fr, _label_en, *_ in GROUPS:
                cap = gen = 0.0
                for _, _, _, _, specs in [g for g in GROUPS if g[0] == label_fr]:
                    for kind, carriers in specs:
                        c, g_ = _cap_and_gen(n, kind, carriers)
                        cap += c
                        gen += g_
                rows.append({"scenario": scen, "year": horizon, "group": label_fr,
                            "GW": cap, "TWh": gen})
    return pd.DataFrame(rows)


def dec(v: float, dp: int, lang: str) -> str:
    return f"{v:.{dp}f}".replace(".", ",") if lang == "fr" else f"{v:.{dp}f}"


def style():
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
        "font.size": 10.5, "figure.autolayout": False, "text.color": INK,
        "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    })


def bare_axes(ax):
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)


#: Segments light enough to need dark (rather than white) value labels.
LIGHT_BG = {"#a6a6a6", "#cdece0", "#f0a860", "#c9c2d9"}


# --------------------------------------------------------------------------- #
def draw_panel(ax, frame, value_col, T, lang, dp, show_delay_all_years, callout):
    """One stacked-bar panel: central cluster, gap, delay cluster."""
    central = frame[frame.scenario == "scen_central"].pivot(index="year", columns="group",
                                                              values=value_col)
    delay = frame[frame.scenario == "scen_retardnucleaire"].pivot(index="year", columns="group",
                                                                    values=value_col)
    order = [g[0] for g in GROUPS]
    central = central[order].reindex(HORIZONS)
    delay = delay[order].reindex(HORIZONS)

    years_delay = HORIZONS if show_delay_all_years else HORIZONS[-1:]
    n_delay = len(years_delay)
    width = 0.62
    gap = 1.6
    x_central = np.arange(len(HORIZONS), dtype=float)
    x_delay = x_central[-1] + gap + np.arange(n_delay, dtype=float)

    # Totals first, so the value-label threshold can scale with this panel's
    # own height rather than an arbitrary absolute cutoff.
    total_c = central.sum(axis=1).to_numpy(dtype=float)
    total_d = delay[order].reindex(HORIZONS).sum(axis=1).to_numpy(dtype=float)[-n_delay:]
    ymax = max(total_c.max(), total_d.max()) * 1.22
    min_label = 0.03 * ymax

    bottoms_c = np.zeros(len(HORIZONS))
    bottoms_d = np.zeros(n_delay)
    for label_fr, label_en, color, hatch, _ in GROUPS:
        label = label_fr if lang == "fr" else label_en
        text_color = INK if color in LIGHT_BG else SURFACE
        vals_c = central[label_fr].to_numpy(dtype=float)
        ax.bar(x_central, vals_c, width, bottom=bottoms_c, color=color, hatch=hatch,
               edgecolor=SURFACE if hatch is None else INK, linewidth=0.8, zorder=3,
               label=label)
        for xi, v, b in zip(x_central, vals_c, bottoms_c):
            if v > min_label:
                ax.annotate(dec(v, dp, lang), xy=(xi, b + v / 2), ha="center", va="center",
                            fontsize=8.3, color=text_color, zorder=4)
        bottoms_c += vals_c

        vals_d = delay[label_fr].to_numpy(dtype=float)[-n_delay:]
        ax.bar(x_delay, vals_d, width, bottom=bottoms_d, color=color, hatch=hatch,
               edgecolor=SURFACE if hatch is None else INK, linewidth=0.8, zorder=3)
        for xi, v, b in zip(x_delay, vals_d, bottoms_d):
            if v > min_label:
                ax.annotate(dec(v, dp, lang), xy=(xi, b + v / 2), ha="center", va="center",
                            fontsize=8.3, color=text_color, zorder=4)
        bottoms_d += vals_d

    for xi, t in zip(x_central, bottoms_c):
        ax.annotate(dec(t, dp, lang), xy=(xi, t), xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=11, weight="bold", color=INK, zorder=6)
    for xi, t in zip(x_delay, bottoms_d):
        ax.annotate(dec(t, dp, lang), xy=(xi, t), xytext=(0, 6), textcoords="offset points",
                    ha="center", fontsize=11, weight="bold", color=INK, zorder=6)

    sep = (x_central[-1] + x_delay[0]) / 2
    ax.axvline(sep, color=INK3, lw=1.0, ls=(0, (3, 3)), zorder=2)

    if callout:
        x0, y0 = x_central[-1], bottoms_c[-1]
        x1, y1 = x_delay[0], bottoms_d[0]
        ax.plot([x0, x1], [y0, y0], color=INK2, lw=1.0, ls=(0, (3, 3)), zorder=5)
        ax.annotate("", xy=(x1, y1), xytext=(x1, y0),
                    arrowprops=dict(arrowstyle="<->", color=HARD, lw=1.6), zorder=6)
        pct = 100.0 * (y1 / y0 - 1.0)
        ax.text(x1 + 0.38, (y0 + y1) / 2, T["delta"].format(v=dec(pct, 0, lang)),
                ha="left", va="center", fontsize=12.5, weight="bold", color=HARD, zorder=6,
                bbox=dict(facecolor=SURFACE, edgecolor=HARD, boxstyle="round,pad=0.35"))

    all_x = np.concatenate([x_central, x_delay])
    ax.set_xlim(all_x.min() - 0.65, all_x.max() + 1.5)
    ax.set_ylim(0, ymax)
    ax.set_xticks(all_x, [str(y) for y in (HORIZONS + list(years_delay))], fontsize=9.5)
    ax.grid(axis="y", color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    bare_axes(ax)

    y_hdr = -0.145
    ax.text(x_central.mean(), y_hdr, SCENARIOS[0][1 if lang == "fr" else 2], ha="center",
            va="top", fontsize=10.5, weight="bold", color=INK, transform=ax.get_xaxis_transform(),
            clip_on=False)
    ax.plot([x_central[0] - 0.4, x_central[-1] + 0.4], [y_hdr - 0.045, y_hdr - 0.045],
            color=INK, lw=1.1, transform=ax.get_xaxis_transform(), clip_on=False, zorder=6)
    ax.text(x_delay.mean(), y_hdr, SCENARIOS[1][1 if lang == "fr" else 2], ha="center",
            va="top", fontsize=10.5, weight="bold", color=INK, transform=ax.get_xaxis_transform(),
            clip_on=False)
    ax.plot([x_delay[0] - 0.4, x_delay[-1] + 0.4], [y_hdr - 0.045, y_hdr - 0.045],
            color=INK, lw=1.1, transform=ax.get_xaxis_transform(), clip_on=False, zorder=6)


def draw(frame, T, lang):
    style()
    fig = plt.figure(figsize=(15.0, 7.6))
    ax_cap = fig.add_axes([0.055, 0.265, 0.415, 0.58])
    ax_gen = fig.add_axes([0.565, 0.265, 0.415, 0.58])

    draw_panel(ax_cap, frame, "GW", T, lang, 1, show_delay_all_years=False, callout=True)
    draw_panel(ax_gen, frame, "TWh", T, lang, 0, show_delay_all_years=True, callout=False)

    ax_cap.set_title(T["panel_cap"], fontsize=14.5, weight="bold", color=INK, pad=38)
    ax_gen.set_title(T["panel_gen"], fontsize=14.5, weight="bold", color=INK, pad=38)

    handles, labels = ax_cap.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, fontsize=9.7,
               bbox_to_anchor=(0.5, 0.075))
    fig.text(0.055, 0.025, T["footnote"], fontsize=8, color=INK3)
    return fig


# --------------------------------------------------------------------------- #
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--results-dir", type=Path, default=Path("results/walloon"))
    p.add_argument("--table", type=Path, default=None,
                   help="skip the live read, reuse a previously extracted CSV")
    p.add_argument("--lang", choices=sorted(L10N), default="fr")
    p.add_argument("--outdir", type=Path, default=Path("docs/figures"))
    args = p.parse_args()

    if args.table:
        frame = pd.read_csv(args.table)
    else:
        frame = read_data(args.results_dir)

    args.outdir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.outdir / "nuclear_delay_mix.csv", index=False)

    T = L10N[args.lang]
    fig = draw(frame, T, args.lang)
    suffix = "" if args.lang == "fr" else f"_{args.lang}"
    stem = args.outdir / f"nuclear_delay_mix{suffix}"
    for ext in ("png", "pdf", "svg"):
        fig.savefig(f"{stem}.{ext}", dpi=300)
    plt.close(fig)
    print(f"written: {stem}.png / .pdf / .svg")

    totals = frame.groupby(["scenario", "year"])[["GW", "TWh"]].sum()
    print(totals.round(2))


if __name__ == "__main__":
    main()
