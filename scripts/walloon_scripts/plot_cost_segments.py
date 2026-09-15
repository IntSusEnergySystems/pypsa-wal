#!/usr/bin/env python3
"""Total Walloon system cost by segment — the cabinet deck's cost chart.

Redraw of the ClimAct slide *"Coûts totaux de tous les vecteurs du système par
segment – Milliards €/an – [PyPSA]"* against the September 2026 batch, with the
scenario set reduced to **central** and **retard nucléaire**.

Where the numbers come from
---------------------------
``<run>/explorer/pypsa/costs_segments.csv``, written by ClimAct's extraction
(``cluster/extract_explorer.sh`` → ``climact-pypsa-eur_results_extraction``).
That file is the *canonical* definition behind the original slide, so the chart
stays comparable with what the cabinet has already seen. Rows are keyed
``<segment>_<region>``; this script reads the five ``*_wl`` segments and their
``Total`` row:

===============  =========================================================
Production       generation and conversion assets (CAPEX + OPEX)
Imports          net cost of energy crossing into the region, valued at the
                 nodal marginal price — electricity, methane, oil, hydrogen,
                 netted, so a net *exporting* region shows a negative term
Stockage         storage assets
Transmission     AC/DC lines, gas / H2 / CO2 pipelines
Distribution     the electricity distribution grid
===============  =========================================================

Because it reads the extraction rather than the networks, it runs in under a
second and needs no ``pypsa``.

Caveat on the Transmission slice
--------------------------------
ClimAct's extraction groups branch costs by PyPSA's ``location`` attribute,
which ``assign_locations`` sets from the *first* bus — so an interconnector is
booked wholly to whichever of the two region codes sorts first, not split
between them. Wallonia therefore carries its links to ``FR``/``LU`` in full and
its links to ``BEBRU``/``BEVLG`` not at all. The 50/50 sharing added to
``scripts/make_summary.py`` on 2026-09-15 fixes ``nodal_costs.csv`` but has not
propagated to this extraction. It moves roughly 5 % of the regional total
between neighbours and, since both scenarios use the same attribution, leaves
every scenario *difference* on this chart untouched.

Usage
-----
::

    python scripts/walloon_scripts/plot_cost_segments.py \\
        --runs results/walloon/scen_central results/walloon/scen_retardnucleaire \\
        --labels "Central" "Retard nucléaire" \\
        --horizons 2030 2040 2050 --region wl --lang fr --outdir docs/figures

More than two runs simply add more bars per horizon, in the order given; every
bar after the first is annotated with its deviation from the first. ``--bare``
additionally writes a title-less variant to drop under a slide title.

Needs only ``pandas`` + ``matplotlib`` — any environment will do.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import pandas as pd

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Validated stacked palette, bottom of the stack first (light mode): all six
# checks pass, worst adjacent CVD ΔE 9.1, worst normal-vision ΔE 22.9. The
# contrast WARN on three slots is relieved by the value table under the chart.
SEGMENTS = [
    # key in costs_segments.csv | colour | white text on it?
    ("distr", "#e87ba4", False),
    ("tran", "#4a3aa7", True),
    ("sto", "#eda100", False),
    ("net_imp", "#1baf7a", True),
    ("prod", "#2a78d6", True),
]
INK = "#0b0b0b"
INK2 = "#52514e"
INK3 = "#8a8a85"
GRID = "#e3e2de"
SURFACE = "#fcfcfb"
BAND = "#f2f1ed"
HARD = "#e34948"

#: Display names for the scenarios this deck uses; anything else falls back to
#: the directory name with the ``scen_`` prefix stripped.
SCENARIO_NAMES = {
    "fr": {
        "scen_central": "Central",
        "scen_retardnucleaire": "Retard nucléaire",
        "scen_realiste_nets": "Réaliste",
        "scen_realiste_nobnd30": "Réaliste sans borne 2030",
        "scen_taxshift": "Tax shift",
        "scen_taxshift_plus": "Tax shift +",
        "scen_biomethane_industrie": "Biométhane industrie",
        "scen_central_2013": "Central (météo 2013)",
    },
    "en": {
        "scen_central": "Central",
        "scen_retardnucleaire": "Delayed nuclear",
        "scen_realiste_nets": "Realistic",
        "scen_realiste_nobnd30": "Realistic, no 2030 bound",
        "scen_taxshift": "Tax shift",
        "scen_taxshift_plus": "Tax shift +",
        "scen_biomethane_industrie": "Biomethane industry",
        "scen_central_2013": "Central (2013 weather)",
    },
}

L10N = {
    "fr": {
        "title": "Coûts totaux du système wallon par segment",
        "subtitle": "Tous vecteurs énergétiques — milliards €/an — PyPSA, "
                    "batch cabinet de septembre 2026",
        "ylabel": "milliards €/an",
        "total": "Total",
        "prod": "Production",
        "net_imp": "Imports nets",
        "sto": "Stockage",
        "tran": "Transport",
        "distr": "Distribution",
        "footnote": "Imports nets : énergie entrant dans la région valorisée au "
                    "prix marginal nodal, nette des exports. Source : "
                    "explorer/pypsa/costs_segments.csv.",
    },
    "en": {
        "title": "Total Walloon system cost by segment",
        "subtitle": "All energy vectors — billion €/yr — PyPSA, September 2026 "
                    "cabinet batch",
        "ylabel": "billion €/yr",
        "total": "Total",
        "prod": "Production",
        "net_imp": "Net imports",
        "sto": "Storage",
        "tran": "Transmission",
        "distr": "Distribution",
        "footnote": "Net imports: energy entering the region valued at the nodal "
                    "marginal price, net of exports. Source: "
                    "explorer/pypsa/costs_segments.csv.",
    },
}


# --------------------------------------------------------------------------- #
def read_segments(run: Path, region: str, horizons: list[str]) -> pd.DataFrame:
    """Segment × horizon table in bn€/yr for one results tree."""
    path = run / "explorer" / "pypsa" / "costs_segments.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found — run cluster/extract_explorer.sh for this scenario"
        )
    raw = pd.read_csv(path)
    wanted = {f"{key}_{region}": key for key, _, _ in SEGMENTS}
    sel = raw[raw.config.isin(wanted) & (raw["cost/carrier"] == "Total")]
    missing = set(wanted) - set(sel.config)
    if missing:
        raise ValueError(f"{path}: missing segment rows {sorted(missing)}")
    absent = [h for h in horizons if h not in sel.columns]
    if absent:
        raise ValueError(f"{path}: no column for horizon(s) {absent}")
    out = sel.set_index(sel.config.map(wanted))[horizons] / 1e9
    return out.loc[[key for key, _, _ in SEGMENTS]]


def dec(v: float, dp: int, lang: str) -> str:
    return f"{v:.{dp}f}".replace(".", ",") if lang == "fr" else f"{v:.{dp}f}"


def signed(v: float, dp: int, lang: str) -> str:
    sep = " " if lang == "fr" else ""
    txt = f"{v:+.{dp}f}{sep}%"
    return (txt.replace(".", ",") if lang == "fr" else txt).replace("-", "−")


# --------------------------------------------------------------------------- #
def style():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans"],
        "font.size": 10.5,
        "figure.autolayout": False,
        "text.color": INK,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
    })


def bar_positions(n_h: int, n_s: int, pitch: float = 1.02, gap: float = 1.05):
    """x of every bar, grouped by horizon, plus each group's centre."""
    xs, centres, base = [], [], 0.0
    for _ in range(n_h):
        group = [base + i * pitch for i in range(n_s)]
        xs.append(group)
        centres.append(sum(group) / n_s)
        base = group[-1] + pitch + gap
    return xs, centres


def draw_bars(ax, data, xs, centres, horizons, labels, T, lang, left):
    width = 0.86
    top = max(df.sum().max() for df in data)
    ax.set_xlim(left, xs[-1][-1] + 0.82)
    ax.set_ylim(0, top * 1.32)

    for gi, horizon in enumerate(horizons):
        # A whisper of a band, instead of the original's heavy grey panels.
        ax.axvspan(xs[gi][0] - width * 0.78, xs[gi][-1] + width * 0.78,
                   color=BAND, zorder=0)
        ax.text(centres[gi], top * 1.265, horizon, ha="center", va="center",
                fontsize=13, weight="bold", color=INK, zorder=5)

        for si, x in enumerate(xs[gi]):
            col = data[si][horizon]
            bottom = 0.0
            for key, colour, on_dark in SEGMENTS:
                v = col[key]
                ax.bar(x, v, bottom=bottom, width=width, color=colour, zorder=3,
                       edgecolor=SURFACE, linewidth=1.4)
                bottom += v
            ax.text(x, bottom + top * 0.028, dec(bottom, 1, lang), ha="center",
                    va="bottom", fontsize=12, weight="bold", color=INK, zorder=5)

        # Deviation of every later scenario from the first, sitting just above
        # this horizon's own bars rather than at a fixed height.
        ref = data[0][horizon].sum()
        tallest = max(data[si][horizon].sum() for si in range(len(data)))
        for si in range(1, len(data)):
            cur = data[si][horizon].sum()
            delta = 100 * (cur / ref - 1) if ref else float("nan")
            strong = abs(delta) >= 1.0
            colour = HARD if strong else INK3
            y = tallest + top * 0.135
            # An arrow head implies movement, so only a real delta gets one; a
            # flat pair keeps the same connector so the grammar stays constant.
            ax.annotate("", xy=(xs[gi][si], y), xytext=(xs[gi][0], y), zorder=5,
                        arrowprops=dict(arrowstyle="-|>" if strong else "-",
                                        color=colour, lw=1.2, shrinkA=0, shrinkB=0))
            ax.text((xs[gi][0] + xs[gi][si]) / 2, y + top * 0.022,
                    signed(delta, 1, lang), ha="center", va="bottom", fontsize=11.5,
                    weight="bold", color=colour, zorder=6)

    ax.set_xticks([x for g in xs for x in g],
                  [lab for _ in horizons for lab in labels])
    ax.tick_params(axis="x", length=0, labelsize=10.5, pad=6)
    ax.tick_params(axis="y", length=0, labelsize=10)
    ax.set_yticks([t for t in ax.get_yticks() if 0 <= t <= top * 1.05])
    ax.set_ylabel(T["ylabel"], color=INK2, fontsize=10)
    ax.grid(axis="y", color=GRID, lw=0.7, zorder=1)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    return top


def draw_table(ax, data, xs, horizons, T, lang, left, right):
    """Swatch + value table under the chart — it doubles as the legend."""
    rows = list(reversed(SEGMENTS)) + [("total", None, None)]
    ax.set_xlim(left, right)
    ax.set_ylim(-len(rows) + 0.4, 1.15)
    ax.axis("off")
    ax.axhline(0.62, color=GRID, lw=1.0, xmin=0, xmax=1)

    for ri, (key, colour, _) in enumerate(rows):
        y = -ri
        is_total = key == "total"
        name = T[key] if not is_total else T["total"]
        if colour:
            ax.add_patch(mpl.patches.Rectangle(
                (left + 0.10, y - 0.17), 0.34, 0.34, color=colour,
                clip_on=False, zorder=3))
        ax.text(left + 0.60, y, name, ha="left", va="center", fontsize=10,
                color=INK if is_total else INK2,
                weight="bold" if is_total else "normal")
        for gi, horizon in enumerate(horizons):
            for si, x in enumerate(xs[gi]):
                v = data[si][horizon].sum() if is_total else data[si][horizon][key]
                ax.text(x, y, dec(v, 1, lang), ha="center", va="center",
                        fontsize=10, color=INK if is_total else INK2,
                        weight="bold" if is_total else "normal")
        if is_total:
            ax.axhline(y + 0.55, color=GRID, lw=1.0, xmin=0, xmax=1)


def build_figure(data, labels, horizons, T, lang, outdir: Path, bare: bool):
    style()
    n_rows = len(SEGMENTS) + 1
    height = (4.05 if bare else 4.75) + 0.30 * n_rows
    fig = plt.figure(figsize=(11.6, height))
    table_frac = 0.30 * n_rows / height
    top = 0.905 if bare else 0.815
    gs = fig.add_gridspec(2, 1, height_ratios=[1 - table_frac, table_frac],
                          hspace=0.06, left=0.052, right=0.985,
                          top=top, bottom=0.085)
    ax, axt = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])

    xs, centres = bar_positions(len(horizons), len(labels))
    left = xs[0][0] - 2.15          # room for the table's label column
    draw_bars(ax, data, xs, centres, horizons, labels, T, lang, left)
    draw_table(axt, data, xs, horizons, T, lang, left, xs[-1][-1] + 0.75)

    if not bare:
        fig.text(0.052, 0.945, T["title"], fontsize=17, weight="bold", color=INK)
        fig.text(0.052, 0.888, T["subtitle"], fontsize=10.5, color=INK2)
    fig.text(0.052, 0.022, T["footnote"], fontsize=8.5, color=INK3)

    outdir.mkdir(parents=True, exist_ok=True)
    suffix = ("_bare" if bare else "") + ("" if lang == "fr" else f"_{lang}")
    stem = outdir / f"cost_segments{suffix}"
    for ext in ("png", "pdf", "svg"):
        fig.savefig(f"{stem}.{ext}", dpi=300)
    plt.close(fig)
    return stem


# --------------------------------------------------------------------------- #
def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", type=Path, nargs="+",
                   default=[Path("results/walloon/scen_central"),
                            Path("results/walloon/scen_retardnucleaire")],
                   help="results trees, in plotting order; the first is the reference")
    p.add_argument("--labels", nargs="+", default=None,
                   help="bar labels; defaults to SCENARIO_NAMES or the directory name")
    p.add_argument("--horizons", nargs="+", default=["2030", "2040", "2050"])
    p.add_argument("--region", default="wl",
                   help="region suffix in costs_segments.csv (wl, fl, bx, be, ...)")
    p.add_argument("--lang", choices=sorted(L10N), default="fr")
    p.add_argument("--outdir", type=Path, default=Path("docs/figures"))
    p.add_argument("--bare", action="store_true",
                   help="also write a title-less variant for slide use")
    args = p.parse_args()

    names = SCENARIO_NAMES[args.lang]
    labels = args.labels or [names.get(r.name, r.name.replace("scen_", ""))
                             for r in args.runs]
    if len(labels) != len(args.runs):
        p.error(f"{len(args.runs)} runs but {len(labels)} labels")
    T = L10N[args.lang]

    data = [read_segments(r, args.region, args.horizons) for r in args.runs]

    stem = build_figure(data, labels, args.horizons, T, args.lang, args.outdir, False)
    if args.bare:
        build_figure(data, labels, args.horizons, T, args.lang, args.outdir, True)

    # Markdown summary, same numbers as the on-figure table.
    head = "| " + T["ylabel"] + " | " + " | ".join(
        f"{h} {lab}" for h in args.horizons for lab in labels) + " |"
    lines = [head, "|" + "---|" * (1 + len(args.horizons) * len(labels))]
    for key, _, _ in reversed(SEGMENTS):
        vals = [dec(d[h][key], 2, args.lang) for h in args.horizons for d in data]
        lines.append(f"| {T[key]} | " + " | ".join(vals) + " |")
    vals = [dec(d[h].sum(), 2, args.lang) for h in args.horizons for d in data]
    lines.append(f"| **{T['total']}** | " + " | ".join(f"**{v}**" for v in vals) + " |")
    if len(data) > 1:
        lines += ["", "| vs " + labels[0] + " | " + " | ".join(args.horizons) + " |",
                  "|" + "---|" * (1 + len(args.horizons))]
        for si in range(1, len(data)):
            d = [signed(100 * (data[si][h].sum() / data[0][h].sum() - 1), 1, args.lang)
                 for h in args.horizons]
            lines.append(f"| {labels[si]} | " + " | ".join(d) + " |")
    md = "\n".join(lines)
    (stem.parent / f"{stem.name}.md").write_text(md + "\n", encoding="utf-8")
    print(md)
    print(f"\nwritten: {stem}.png / .pdf / .svg / .md")


if __name__ == "__main__":
    main()
