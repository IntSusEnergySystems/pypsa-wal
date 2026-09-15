#!/usr/bin/env python3
"""Weather-year sensitivity figure for the cabinet slide deck (2010 vs 2013).

The question the slide answers
------------------------------
The Walloon runs use **2010** as the reference weather year and **2013** as the
counterfactual. Why does the weather year matter at all, given that the demand
is not a PyPSA result?

Because the soft-link splits the two roles cleanly:

* **TIMES sets the annual energy.** Every Walloon load — electricity, heat,
  transport, industry — carries the *same annual total* in both runs, to the
  last decimal. The weather year cannot move it. The script verifies this
  rather than assuming it (``--check`` prints the per-load audit).
* **The weather year sets the resource and the timing.** It drives the wind,
  PV and run-of-river profiles, *and* the temperature that redistributes the
  TIMES heat envelope across the 8 760 hours. Same annual energy, different
  hour-by-hour shape.

2010 is the stress case not because it is poorer on annual average — it is only
~2 % poorer on renewable yield — but because it stacks a cold, still December on
top of the year's weakest renewable month. The figure is built to show exactly
that coincidence.

What it computes
----------------
1. *Demand audit* — per-load annual totals in both runs, plus the hourly L1
   re-shuffling, i.e. how much of the same annual energy moved to other hours.
2. *Reference-fleet renewable yield* — run A's installed fleet at the chosen
   horizon is applied to **both** weather years' ``p_max_pu``. Holding the fleet
   fixed isolates the weather; comparing each run's own generation would mix in
   the optimiser's response.
3. *Monthly supply/demand mirror* — wind + PV output against heat demand.
4. *System response* — the capacities the optimiser builds in each run.

Outputs ``weather_year_<horizon>.{png,pdf,svg}`` plus a Markdown summary table.

Usage
-----
::

    python scripts/walloon_scripts/compare_weather_years.py \
        --run-a results/walloon/scen_central \
        --run-b results/walloon_2013/scen_central_2013 \
        --label-a 2010 --label-b 2013 \
        --horizon 2050 --region BEWAL --outdir docs/figures

Any two runs that share a network naming scheme work — the weather-year pair is
just the case it was written for. ``--check`` adds the per-load demand audit to
stdout; ``--lang fr`` writes the French labelling (``*_fr.png``) for the Walloon
deck; ``--bare`` additionally writes a title-less variant for
``make_weather_year_slide.py`` to place under a slide title.

Note on the annual heat envelope
--------------------------------
Because TIMES fixes the annual heat energy, a cold year shifts heat *within* the
year but never raises the yearly total. A real 2010 would have consumed more heat
overall, so the stress this figure shows is the **timing** component only — the
volume component is out of PyPSA's reach by construction. That makes the 2010
case conservative, and the slide says so.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd

mpl.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.gridspec import GridSpec  # noqa: E402

import pypsa  # noqa: E402

# --- palette (validated: adjacent CVD dE 24.7, normal-vision dE 33.6) ---------
C_A = "#eb6834"  # run A — the stress year, warm
C_B = "#2a78d6"  # run B — the counterfactual, cool
C_HARD = "#e34948"  # "tighter in A"
C_EASY = "#2a78d6"  # "looser in A"
C_NULL = "#8a8a85"  # no change
INK = "#0b0b0b"
INK2 = "#52514e"
INK3 = "#8a8a85"
GRID = "#e3e2de"
SURFACE = "#fcfcfb"

WIND = ["onwind"]
PV = ["solar", "solar rooftop", "solar-hsat"]
MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]  # same in FR

# All figure wording lives here; --lang picks a column. Keys are referenced by
# name below, so a missing translation fails loudly rather than silently
# falling back to English.
L10N = {
    "en": {
        "legend_title": "weather year",
        "supply": "Renewable supply",
        "supply_sub": "wind + PV on the same fleet — {a} vs {b} TWh/yr",
        "heat": "Heat demand",
        "heat_sub": "set by TIMES — {a} TWh/yr in both years",
        "ylabel": "GWh per month",
        "december": "December {la}",
        "relative": "{la} relative to {lb}",
        "title": "The weather year moves the supply, not the demand",
        "subtitle": "Wallonia, {hz} — the TIMES demand is identical in both runs; "
                    "only the resource and its timing change",
        "footnote": "TIMES fixes the annual heat energy, so a cold year shifts heat "
                    "within the year but never raises the yearly total — the volume "
                    "effect of a cold {la} is outside PyPSA by construction.",
        "g_annual": "Annual energy — set by TIMES",
        "g_weather": "Weather — resource and timing",
        "g_response": "System response — what {hz} builds",
        "r_demand": "Final demand, all vectors",
        "r_heat": "Heat demand",
        "r_wind": "Wind yield, same fleet",
        "r_solar": "Solar yield, same fleet",
        "r_winter": "Winter (Dec–Feb) renewables",
        "r_dec_vre": "December renewables",
        "r_dec_heat": "December heat demand",
        "r_cap_wind": "Onshore wind capacity",
        "r_cap_batt": "Battery storage",
    },
    "fr": {
        "legend_title": "année météo",
        "supply": "Production renouvelable",
        "supply_sub": "éolien + PV à parc identique — {a} contre {b} TWh/an",
        "heat": "Demande de chaleur",
        "heat_sub": "fixée par TIMES — {a} TWh/an les deux années",
        "ylabel": "GWh par mois",
        "december": "Décembre {la}",
        "relative": "{la} par rapport à {lb}",
        "title": "L'année météo déplace la production, pas la demande",
        "subtitle": "Wallonie, {hz} — la demande TIMES est identique dans les deux "
                    "runs ; seules la ressource et son calendrier changent",
        "footnote": "TIMES fixant l'énergie annuelle de chaleur, une année froide "
                    "déplace la chaleur dans l'année sans augmenter le total annuel : "
                    "l'effet de volume est hors du périmètre de PyPSA.",
        "g_annual": "Énergie annuelle — fixée par TIMES",
        "g_weather": "Météo — ressource et calendrier",
        "g_response": "Réponse du système — ce que {hz} construit",
        "r_demand": "Demande finale, tous vecteurs",
        "r_heat": "Demande de chaleur",
        "r_wind": "Éolien, parc identique",
        "r_solar": "Solaire, parc identique",
        "r_winter": "Renouvelables (déc.–févr.)",
        "r_dec_vre": "Renouvelables de décembre",
        "r_dec_heat": "Chaleur de décembre",
        "r_cap_wind": "Éolien terrestre installé",
        "r_cap_batt": "Stockage batterie",
    },
}


# --------------------------------------------------------------------------- #
# data extraction
# --------------------------------------------------------------------------- #
def network_path(run: Path, horizon: str) -> Path:
    """Locate the solved network for ``horizon`` inside a results tree."""
    hits = sorted((run / "networks").glob(f"*{horizon}.nc"))
    if not hits:
        raise FileNotFoundError(f"no network for horizon {horizon} under {run}/networks")
    return hits[-1]


def dense(static: pd.Series, varying: pd.DataFrame, snapshots) -> pd.DataFrame:
    """Time-varying frame with the static default filled in where absent."""
    out = varying.reindex(columns=static.index)
    flat = pd.DataFrame(
        np.tile(static.values, (len(snapshots), 1)), index=snapshots, columns=static.index
    )
    return out.fillna(flat)


def regional_loads(n: pypsa.Network, region: str) -> pd.DataFrame:
    ld = n.loads[n.loads.bus.str.startswith(region)]
    lt = dense(ld.p_set, n.loads_t.p_set, n.snapshots)
    lt.index = pd.to_datetime(n.snapshots)
    return lt


def res_fleet(n: pypsa.Network, region: str) -> pd.DataFrame:
    g = n.generators
    return g[g.bus.str.startswith(region) & g.carrier.isin(WIND + PV)]


def reference_yield(n: pypsa.Network, fleet: pd.DataFrame) -> pd.DataFrame:
    """Hourly wind/PV output of a *fixed* fleet under this network's weather."""
    pu = dense(fleet.p_max_pu, n.generators_t.p_max_pu, n.snapshots).reindex(
        columns=fleet.index
    )
    mw = pu.mul(fleet.p_nom_opt, axis=1)
    wind_cols = [c for c in fleet.index if fleet.carrier[c] in WIND]
    pv_cols = [c for c in fleet.index if fleet.carrier[c] in PV]
    out = pd.DataFrame(
        {"wind": mw[wind_cols].sum(axis=1), "pv": mw[pv_cols].sum(axis=1)}
    )
    out.index = pd.to_datetime(n.snapshots)
    return out


def capacity_table(n: pypsa.Network, region: str) -> pd.Series:
    """Optimised capacity per (component, carrier) in the region."""
    parts = []
    for comp, attr in [("generators", "p_nom_opt"), ("links", "p_nom_opt"),
                       ("stores", "e_nom_opt"), ("storage_units", "p_nom_opt")]:
        df = getattr(n, comp)
        if df.empty:
            continue
        bus = "bus0" if comp == "links" else "bus"
        sel = df[df[bus].str.startswith(region)]
        if sel.empty:
            continue
        parts.append(sel.groupby("carrier")[attr].sum().rename(comp))
    return pd.concat(parts, keys=[p.name for p in parts]) if parts else pd.Series(dtype=float)


def collect(run: Path, horizon: str, region: str, fleet: pd.DataFrame | None):
    n = pypsa.Network(str(network_path(run, horizon)))
    fleet = res_fleet(n, region) if fleet is None else fleet
    loads = regional_loads(n, region)
    heat = loads[[c for c in loads.columns if "heat" in c]].sum(axis=1)
    return {
        "n": n,
        "fleet": fleet,
        "loads": loads,
        "heat": heat,
        "vre": reference_yield(n, fleet),
        "caps": capacity_table(n, region),
    }


# --------------------------------------------------------------------------- #
# figure
# --------------------------------------------------------------------------- #
def style():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans"],
        "font.size": 10.5,
        "figure.autolayout": False,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK2,
        "text.color": INK,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
    })


def mirror_panel(ax, ma, mb, la, lb, T, lang):
    """Renewable supply above the axis, heat demand below — one shared GWh scale."""
    x = np.arange(12)
    w = 0.38
    up_a, up_b = ma["vre"].values, mb["vre"].values
    dn_a, dn_b = -ma["heat"].values, -mb["heat"].values

    for vals, off, col, lab in [(up_a, -w / 2, C_A, la), (up_b, w / 2, C_B, lb)]:
        ax.bar(x + off, vals, width=w, color=col, label=lab, zorder=3,
               edgecolor=SURFACE, linewidth=0.9)
    for vals, off, col in [(dn_a, -w / 2, C_A), (dn_b, w / 2, C_B)]:
        ax.bar(x + off, vals, width=w, color=col, alpha=0.55, zorder=3,
               edgecolor=SURFACE, linewidth=0.9)

    lim = max(up_a.max(), up_b.max(), -dn_a.min(), -dn_b.min()) * 1.40
    ax.set_xlim(-0.72, 11.72)
    ax.axhline(0, color=INK2, lw=1.0, zorder=5)
    ax.set_xticks(x, MONTHS)
    sep = "\u202f" if lang == "fr" else ","
    ax.set_yticks(np.arange(-6000, 6001, 2000),
                  [f"{abs(t):,.0f}".replace(",", sep)
                   for t in np.arange(-6000, 6001, 2000)])
    ax.set_ylim(-lim, lim)
    ax.set_ylabel(T["ylabel"], color=INK2, fontsize=9.5)
    ax.grid(axis="y", color=GRID, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=9.5)
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)

    ax.text(-0.62, lim * 0.965, T["supply"], fontsize=11,
            color=INK, weight="bold", va="top")
    ax.text(-0.62, lim * 0.80,
            T["supply_sub"].format(a=dec(up_a.sum() / 1e3, 1, lang),
                                   b=dec(up_b.sum() / 1e3, 1, lang)),
            fontsize=9.5, color=INK2, va="top", style="italic")
    ax.text(-0.62, -lim * 0.965, T["heat"], fontsize=11,
            color=INK, weight="bold", va="bottom")
    ax.text(-0.62, -lim * 0.815,
            T["heat_sub"].format(a=dec(-dn_a.sum() / 1e3, 1, lang)),
            fontsize=9.5, color=INK2, va="bottom", style="italic")
    return lim


def dec(v: float, dp: int, lang: str) -> str:
    """Decimal number with the locale's separator."""
    txt = f"{v:.{dp}f}"
    return txt.replace(".", ",") if lang == "fr" else txt


def signed(v: float, dp: int = 0, lang: str = "en") -> str:
    """Signed percentage with a typographic minus and the locale's separator."""
    sep = "\u202f" if lang == "fr" else ""   # FR sets a thin space before %
    return f"{v:+.{dp}f}{sep}%".replace(".", "," if lang == "fr" else ".") \
                               .replace("-", "\u2212")


def annotate_december(ax, ma, mb, lim, la, T, lang):
    """Mark the month where the two effects compound."""
    ax.axvspan(10.52, 11.72, color="#f4eee7", zorder=1)
    dv = 100 * (ma["vre"].iloc[11] / mb["vre"].iloc[11] - 1)
    dh = 100 * (ma["heat"].iloc[11] / mb["heat"].iloc[11] - 1)
    top = max(ma["vre"].iloc[11], mb["vre"].iloc[11])
    bot = max(ma["heat"].iloc[11], mb["heat"].iloc[11])
    ax.text(11.12, lim * 0.97, T["december"].format(la=la), fontsize=9.5,
            color=INK3, ha="center", va="top", style="italic")
    ax.text(11.12, top + lim * 0.042, signed(dv, lang=lang), fontsize=12.5,
            weight="bold", color=C_HARD, ha="center", va="bottom", zorder=6)
    ax.text(11.12, -bot - lim * 0.050, signed(dh, lang=lang), fontsize=12.5,
            weight="bold", color=C_HARD, ha="center", va="top", zorder=6)


def kpi_panel(ax, rows, lang="en", label_frac=0.40, val_frac=0.16):
    """Signed deltas of run A relative to run B, grouped by what sets them."""
    y, items, heads = 0.0, [], []
    for group, entries in rows:
        heads.append((y, group))
        y -= 0.78
        for label, val, kind in entries:
            items.append((y, label, val,
                          {"hard": C_HARD, "easy": C_EASY, "null": C_NULL}[kind]))
            y -= 1.0
        y -= 0.44

    # Reserve `val_frac` of the axes width on each side for the value labels, and
    # `label_frac` on the left for the row labels, so nothing can overlap.
    vals = [i[2] for i in items]
    pos, neg = max(vals + [0]), min(vals + [0])
    width = (pos - neg) / (1.0 - label_frac - 2 * val_frac)
    ax.set_xlim(pos + val_frac * width - width, pos + val_frac * width)
    ax.set_ylim(y + 0.60, 1.05)
    ax.barh([i[0] for i in items], vals, height=0.50,
            color=[i[3] for i in items], zorder=3)
    ax.axvline(0, color=INK2, lw=1.0, zorder=4)
    ax.set_yticks([])
    ax.set_xticks([])
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)

    blend = mpl.transforms.blended_transform_factory(ax.transAxes, ax.transData)
    pad = width * 0.018
    for ty, lab, v, col in items:
        ax.text(label_frac - 0.030, ty, lab, transform=blend, ha="right",
                va="center", fontsize=9.5, color=INK2)
        ax.text(v + (pad if v >= 0 else -pad), ty,
                signed(v, 1, lang) if abs(v) >= 0.05
                else dec(0.0, 1, lang) + ("\u202f%" if lang == "fr" else "%"),
                ha="left" if v >= 0 else "right", va="center",
                fontsize=10, weight="bold", color=col)
    for hy, head in heads:
        ax.text(0.0, hy, head, transform=blend, ha="left", va="center",
                fontsize=9.5, color=INK3, style="italic")


def build_figure(la, lb, horizon, region, ma, mb, rows, outdir: Path,
                 bare: bool = False, lang: str = "en"):
    """Render the two-panel figure.

    ``bare`` drops the title block, for dropping the figure under a slide title
    that carries the same words; the standalone version keeps it.
    """
    T = L10N[lang]
    style()
    # The bare variant is wider and shorter: it sits under a slide title, so it
    # gets the aspect a 16:9 slide can spare rather than the report's.
    width, height = (13.8, 5.5) if bare else (13.4, 6.4)
    top = 0.855 if bare else 0.765
    fig = plt.figure(figsize=(width, height))
    gs = GridSpec(1, 2, width_ratios=[1.58, 1.0], wspace=0.06,
                  left=0.055, right=0.995, top=top, bottom=0.105 * 6.4 / height)
    axL, axR = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])

    lim = mirror_panel(axL, ma, mb, la, lb, T, lang)
    annotate_december(axL, ma, mb, lim, la, T, lang)
    leg = axL.legend(loc="lower left", bbox_to_anchor=(0.0, 1.015), ncol=2,
                     frameon=False, handlelength=0.9, handleheight=0.9,
                     fontsize=10.5, columnspacing=1.4,
                     title=T["legend_title"],
                     title_fontproperties={"size": 9.5, "style": "italic"})
    leg.get_title().set_color(INK3)
    leg._legend_box.align = "left"
    kpi_panel(axR, rows, lang)

    if not bare:
        fig.text(0.055, 0.945, T["title"], fontsize=17, weight="bold", color=INK)
        fig.text(0.055, 0.893, T["subtitle"].format(hz=horizon),
                 fontsize=10.5, color=INK2)
    fig.text(0.635, top + 0.040, T["relative"].format(la=la, lb=lb),
             fontsize=10.5, color=INK3, style="italic")
    fig.text(0.055, 0.020, T["footnote"].format(la=la), fontsize=8.5, color=INK3)

    outdir.mkdir(parents=True, exist_ok=True)
    suffix = ("_bare" if bare else "") + ("" if lang == "en" else f"_{lang}")
    stem = outdir / f"weather_year_{region}_{horizon}{suffix}"
    for ext in ("png", "pdf", "svg"):
        fig.savefig(f"{stem}.{ext}", dpi=300)
    plt.close(fig)
    return stem


# --------------------------------------------------------------------------- #
def pct(a, b):
    return 100 * (a / b - 1) if b else float("nan")


def cap(caps: pd.Series, comp: str, carrier: str) -> float:
    try:
        return float(caps.loc[(comp, carrier)])
    except KeyError:
        return 0.0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run-a", type=Path, default=Path("results/walloon/scen_central"),
                   help="results tree of the reference (stress) weather year")
    p.add_argument("--run-b", type=Path,
                   default=Path("results/walloon_2013/scen_central_2013"),
                   help="results tree of the counterfactual weather year")
    p.add_argument("--label-a", default="2010")
    p.add_argument("--label-b", default="2013")
    p.add_argument("--horizon", default="2050")
    p.add_argument("--region", default="BEWAL")
    p.add_argument("--outdir", type=Path, default=Path("docs/figures"))
    p.add_argument("--lang", choices=sorted(L10N), default="en",
                   help="language of the figure labels")
    p.add_argument("--bare", action="store_true",
                   help="also write a title-less variant for slide use")
    p.add_argument("--check", action="store_true",
                   help="print the per-load demand audit")
    args = p.parse_args()

    A = collect(args.run_a, args.horizon, args.region, None)
    B = collect(args.run_b, args.horizon, args.region, A["fleet"])  # same fleet

    # -- 1. demand audit ---------------------------------------------------- #
    la_, lb_ = A["loads"], B["loads"].reindex(columns=A["loads"].columns)
    ann = pd.DataFrame({"a_TWh": la_.sum() / 1e6, "b_TWh": lb_.sum() / 1e6})
    ann["rel_%"] = 100 * (ann.a_TWh - ann.b_TWh) / ann.a_TWh.abs().replace(0, np.nan)
    hourly = la_.copy()
    hourly.index = pd.RangeIndex(len(hourly))
    hb = lb_.copy()
    hb.index = pd.RangeIndex(len(hb))
    ann["reshuffled_%"] = 100 * (hb - hourly).abs().sum() / hourly.abs().sum().replace(0, np.nan)
    worst = ann["rel_%"].abs().max()

    print(f"\n=== demand audit ({args.region}, {args.horizon}) ===")
    print(f"annual total   {args.label_a}: {ann.a_TWh.sum():9.4f} TWh")
    print(f"annual total   {args.label_b}: {ann.b_TWh.sum():9.4f} TWh")
    print(f"worst per-load annual deviation: {worst:.4g} %   "
          f"-> {'IDENTICAL (TIMES-set)' if worst < 1e-6 else 'NOT identical - investigate'}")
    print(f"hours re-shuffled (L1 / total): "
          f"{100 * (hb - hourly).abs().sum().sum() / hourly.abs().sum().sum():.1f} %")
    if args.check:
        print(ann.round(4).sort_values("a_TWh", ascending=False).to_string())

    # -- 2. monthly series -------------------------------------------------- #
    def monthly(d):
        m = pd.DataFrame({
            "vre": (d["vre"].sum(axis=1)).resample("ME").sum() / 1e3,
            "wind": d["vre"].wind.resample("ME").sum() / 1e3,
            "pv": d["vre"].pv.resample("ME").sum() / 1e3,
            "heat": d["heat"].resample("ME").sum() / 1e3,
        })
        m.index = range(1, 13)
        return m

    ma, mb = monthly(A), monthly(B)

    # -- 3. KPI rows -------------------------------------------------------- #
    djf = [12, 1, 2]
    T = L10N[args.lang]
    rows = [
        (T["g_annual"], [
            (T["r_demand"], pct(ann.a_TWh.sum(), ann.b_TWh.sum()), "null"),
            (T["r_heat"], pct(ma.heat.sum(), mb.heat.sum()), "null"),
        ]),
        (T["g_weather"], [
            (T["r_wind"], pct(ma.wind.sum(), mb.wind.sum()), "hard"),
            (T["r_solar"], pct(ma.pv.sum(), mb.pv.sum()), "easy"),
            (T["r_winter"], pct(ma.vre[djf].sum(), mb.vre[djf].sum()), "hard"),
            (T["r_dec_vre"], pct(ma.vre[12], mb.vre[12]), "hard"),
            (T["r_dec_heat"], pct(ma.heat[12], mb.heat[12]), "hard"),
        ]),
        (T["g_response"].format(hz=args.horizon), [
            (T["r_cap_wind"],
             pct(cap(A["caps"], "generators", "onwind"),
                 cap(B["caps"], "generators", "onwind")), "hard"),
            (T["r_cap_batt"],
             pct(cap(A["caps"], "stores", "battery"),
                 cap(B["caps"], "stores", "battery")), "hard"),
        ]),
    ]

    stem = build_figure(args.label_a, args.label_b, args.horizon, args.region,
                        ma, mb, rows, args.outdir, lang=args.lang)
    if args.bare:
        build_figure(args.label_a, args.label_b, args.horizon, args.region,
                     ma, mb, rows, args.outdir, bare=True, lang=args.lang)

    # -- 4. markdown summary ------------------------------------------------ #
    lines = [f"| Indicator | {args.label_a} | {args.label_b} | {args.label_a} vs {args.label_b} |",
             "|---|---:|---:|---:|",
             f"| Walloon final demand (TWh) | {ann.a_TWh.sum():.2f} | {ann.b_TWh.sum():.2f} "
             f"| {pct(ann.a_TWh.sum(), ann.b_TWh.sum()):+.2f}% |",
             f"| Wind yield, same fleet (TWh) | {ma.wind.sum() / 1e3:.2f} | {mb.wind.sum() / 1e3:.2f} "
             f"| {pct(ma.wind.sum(), mb.wind.sum()):+.1f}% |",
             f"| Solar yield, same fleet (TWh) | {ma.pv.sum() / 1e3:.2f} | {mb.pv.sum() / 1e3:.2f} "
             f"| {pct(ma.pv.sum(), mb.pv.sum()):+.1f}% |",
             f"| Wind + PV yield (TWh) | {ma.vre.sum() / 1e3:.2f} | {mb.vre.sum() / 1e3:.2f} "
             f"| {pct(ma.vre.sum(), mb.vre.sum()):+.1f}% |",
             f"| December renewables (GWh) | {ma.vre[12]:.0f} | {mb.vre[12]:.0f} "
             f"| {pct(ma.vre[12], mb.vre[12]):+.1f}% |",
             f"| December heat demand (GWh) | {ma.heat[12]:.0f} | {mb.heat[12]:.0f} "
             f"| {pct(ma.heat[12], mb.heat[12]):+.1f}% |"]
    for comp, carrier, name in [("generators", "onwind", "Onshore wind (MW)"),
                                ("generators", "solar rooftop", "Rooftop PV (MW)"),
                                ("stores", "battery", "Battery storage (MWh)")]:
        va, vb = cap(A["caps"], comp, carrier), cap(B["caps"], comp, carrier)
        lines.append(f"| {name} | {va:,.0f} | {vb:,.0f} | {pct(va, vb):+.1f}% |")
    md = "\n".join(lines)
    (stem.parent / f"{stem.name}.md").write_text(md + "\n")
    print(f"\n{md}\n\nwritten: {stem}.png / .pdf / .svg / .md")


if __name__ == "__main__":
    main()
