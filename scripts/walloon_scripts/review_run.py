# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Mechanical half of the run review — everything a script can decide on its own.

Implements levels 0-4 (and the cheap parts of 5-6) of
``docs/run-review-checklist.md``: provenance, solver convergence, soft-link
fidelity, accounting identities, and whether the model's own constraints were
respected. Judgement calls — "is 14 GW of Walloon onshore wind plausible?" — stay
with the human and belong in section 11 of the run's ``docs/logs/`` solve log.

The script never solves anything. It reads a results tree and, unless ``--csv-only``
is given, the four solved networks.

Usage::

    python scripts/walloon_scripts/review_run.py results/walloon/scen_demande_haute
    python scripts/walloon_scripts/review_run.py results/walloon/scen_demande_haute --full
    python scripts/walloon_scripts/review_run.py results/walloon/scen_demande_haute --csv-only

``--full`` adds the slow per-bus balance sweep. Exit status is 1 if any check
FAILs, so this can gate a publication step.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

HORIZONS = (2025, 2030, 2040, 2050)
WAL = "BEWAL"
BE_NODES = ("BEWAL", "BEVLG", "BEBRU")

# Level 5.4 plausibility windows. Deliberately wide: these are lie-detectors, not
# calibration targets.
CF_WINDOWS = {
    "onwind": (0.18, 0.32),
    "solar": (0.08, 0.15),
    "solar-hsat": (0.09, 0.17),
    "solar rooftop": (0.07, 0.14),
    "offwind-ac": (0.33, 0.55),
    "offwind-dc": (0.33, 0.55),
    "ror": (0.15, 0.45),
}

# Walloon annual-energy potentials that are written in GWh/an in
# data/walloon/custom_potentials.csv but live as e_sum_max (MWh) in the network.
ANNUAL_ENERGY_CARRIERS = ("biogas", "solid biomass", "solid biomass transported")

# TIMES row(s) each BEWAL load carrier must reproduce, and the tolerance.
SOFTLINK_MAP = {
    "industry electricity": (["electricity"], 0.002),
    "gas for industry": (["methane"], 0.002),
    "naphtha for industry": (["naphtha"], 0.005),
    "solid biomass for industry": (["solid biomass"], 0.005),
    "kerosene for aviation": (
        ["total domestic aviation", "total international aviation"], 0.002),
    "coal for industry": (["coal", "coke"], 0.02),
}


class Report:
    """Collects PASS/WARN/FAIL lines and prints them grouped by level."""

    LEVELS = {"PASS": 0, "INFO": 0, "WARN": 1, "FAIL": 2}

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str, str]] = []

    def add(self, level: str, section: str, check: str, detail: str = "") -> None:
        self.rows.append((level, section, check, detail))

    def ok(self, s, c, d=""):
        self.add("PASS", s, c, d)

    def info(self, s, c, d=""):
        self.add("INFO", s, c, d)

    def warn(self, s, c, d=""):
        self.add("WARN", s, c, d)

    def fail(self, s, c, d=""):
        self.add("FAIL", s, c, d)

    @property
    def worst(self) -> int:
        return max((self.LEVELS[r[0]] for r in self.rows), default=0)

    def render(self) -> str:
        out = []
        section = None
        for lvl, sec, check, detail in self.rows:
            if sec != section:
                out.append("")
                out.append(f"── {sec} " + "─" * max(4, 76 - len(sec)))
                section = sec
            mark = {"PASS": "  ok  ", "INFO": " info ", "WARN": " WARN ", "FAIL": " FAIL "}[lvl]
            out.append(f"[{mark}] {check}")
            if detail:
                for line in str(detail).rstrip().splitlines():
                    out.append(f"           {line}")
        n = pd.Series([r[0] for r in self.rows]).value_counts()
        out.append("")
        out.append("─" * 80)
        out.append("  ".join(f"{k}: {int(v)}" for k, v in n.items()))
        return "\n".join(out)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def load_energy(n, names) -> float:
    """Annual energy of Load components, tolerating static p_set."""
    w = n.snapshot_weightings.objective
    tot = 0.0
    tvar = n.loads_t.p_set.columns
    for i in names:
        if i in tvar:
            tot += float((n.loads_t.p_set[i] * w).sum())
        else:
            tot += float(n.loads.p_set[i] * w.sum())
    return tot


def bus_balance(n, buses) -> pd.Series:
    """Annual energy into a set of buses, by source. Sums to ~0 when consistent."""
    w = n.snapshot_weightings.objective
    out: dict[str, float] = {}

    g = n.generators[n.generators.bus.isin(buses)]
    if len(g):
        s = n.generators_t.p[g.index].mul(w, axis=0).sum().groupby(g.carrier).sum()
        out.update({f"gen:{k}": v for k, v in s.items()})

    su = n.storage_units[n.storage_units.bus.isin(buses)]
    if len(su):
        s = n.storage_units_t.p[su.index].mul(w, axis=0).sum().groupby(su.carrier).sum()
        out.update({f"su:{k}": v for k, v in s.items()})

    st = n.stores[n.stores.bus.isin(buses)]
    if len(st):
        s = -n.stores_t.p[st.index].mul(w, axis=0).sum().groupby(st.carrier).sum()
        out.update({f"store:{k}": -v for k, v in s.items()})

    ld = n.loads[n.loads.bus.isin(buses)]
    if len(ld):
        out["load"] = -load_energy(n, ld.index)

    # every link port, so multi-port links (CHP, DAC, CC) balance too
    for i in range(6):
        col, pcol = f"bus{i}", f"p{i}"
        if col not in n.links.columns or pcol not in n.links_t:
            continue
        lk = n.links[n.links[col].isin(buses)]
        if not len(lk):
            continue
        s = -n.links_t[pcol][lk.index].mul(w, axis=0).sum().groupby(lk.carrier).sum()
        for k, v in s.items():
            out[f"link{i}:{k}"] = out.get(f"link{i}:{k}", 0.0) + v

    for end in ("bus0", "bus1"):
        li = n.lines[n.lines[end].isin(buses)]
        if not len(li):
            continue
        p = n.lines_t.p0 if end == "bus0" else n.lines_t.p1
        s = -p[li.index].mul(w, axis=0).sum().sum()
        out["lines"] = out.get("lines", 0.0) + float(s)

    return pd.Series(out)


def links_to(n, node, carrier=None):
    """Links whose *output* (bus1) sits at `node` — the port capacity is quoted at."""
    l = n.links[n.links.bus1.map(n.buses.location) == node]
    return l if carrier is None else l[l.carrier == carrier]


# --------------------------------------------------------------------------- #
# level 0 — provenance
# --------------------------------------------------------------------------- #

def check_provenance(run: Path, rep: Report) -> dict:
    sec = "0 · provenance"
    meta: dict = {}

    rj = run / "run.json"
    if rj.exists():
        meta = json.loads(rj.read_text())
        rep.info(sec, "run.json", "\n".join(f"{k}: {v}" for k, v in meta.items()
                                            if k in ("upload_id", "git_commit", "git_branch",
                                                     "configfile", "uploaded_at")))
    else:
        rep.info(sec, "run.json absent (local run)")

    cfgs = sorted((run / "configs").glob("config.base_s_adm___*.yaml"))
    if len(cfgs) != len(HORIZONS):
        rep.warn(sec, f"expected {len(HORIZONS)} per-horizon config snapshots, found {len(cfgs)}")
    if cfgs:
        base = cfgs[0].read_text().splitlines()
        for c in cfgs[1:]:
            diff = [l for a, l in zip(base, c.read_text().splitlines()) if a != l]
            odd = [l for l in diff if "planning_horizons" not in l]
            if odd:
                rep.fail(sec, f"{c.name} differs from {cfgs[0].name} beyond planning_horizons",
                         "\n".join(odd[:6]))
        else:
            rep.ok(sec, "all horizon configs identical apart from planning_horizons")

        text = cfgs[0].read_text()
        for key, why in (
            ("heat_stock_age_profile", "inherited heat-pump stock over-ages; HP capacity falls 2025→2030"),
            ("bev_natural_charging_split", "EV three-profile split inactive"),
            ("local_bev_dsm", "Elia natural/local charging weights inactive"),
        ):
            if key not in text:
                rep.warn(sec, f"`{key}` absent from the effective config", why)
        m = re.search(r"resolution_sector:\s*(\S+)", text)
        if m:
            rep.info(sec, f"clustering.temporal.resolution_sector = {m.group(1)}")
        m = re.search(r"times_file:\s*(\S+)", text)
        if m:
            rep.info(sec, f"sector.times_file = {m.group(1)}")
        m = re.search(r"default_cutout:\s*\"?([\w\-]+)", text)
        y_cut = re.search(r"europe-(\d{4})", m.group(1)) if m else None
        m2 = re.search(r"start:\s*\"(\d{4})", text)
        if y_cut and m2:
            if y_cut.group(1) == m2.group(1):
                rep.ok(sec, f"weather year consistent ({m2.group(1)})")
            else:
                rep.fail(sec, "snapshots year != cutout year",
                         f"snapshots {m2.group(1)} vs cutout {y_cut.group(1)}")
    return meta


# --------------------------------------------------------------------------- #
# level 1 — solver
# --------------------------------------------------------------------------- #

def check_solver(run: Path, rep: Report) -> None:
    sec = "1 · solve"
    for y in HORIZONS:
        log = run / "logs" / f"base_s_adm___{y}_solver.log"
        if not log.exists():
            rep.fail(sec, f"{y}: solver log missing")
            continue
        txt = log.read_text(errors="ignore")
        m = re.search(r"Optimal objective\s+([-\d.e+]+)", txt)
        if m:
            rep.ok(sec, f"{y}: Optimal objective {float(m.group(1)):.6e}")
        else:
            rep.fail(sec, f"{y}: no 'Optimal objective' in the solver log")
        if re.search(r"^Crossover\s+0", txt, re.M):
            rep.info(sec, f"{y}: Crossover 0 — interior solution; individual values carry "
                          "solver-tolerance noise, do not read 3 significant figures")
        warns = sorted(set(re.findall(r"Warning: Model contains ([\w ]+)", txt)))
        if warns:
            rep.warn(sec, f"{y}: Gurobi conditioning warnings", ", ".join(warns))
        m = re.search(r"Bounds range\s+\[([^\]]+)\]", txt)
        if m:
            rep.info(sec, f"{y}: bounds range [{m.group(1)}]")


# --------------------------------------------------------------------------- #
# level 2 — soft link
# --------------------------------------------------------------------------- #

def times_demands(run: Path, scenario: str, year: int) -> pd.Series | None:
    """Locate resources/<prefix>/<scenario>/wallon_demands_<year>.csv for this run."""
    root = Path.cwd()
    cands = list((root / "resources").glob(f"*/{scenario}/wallon_demands_{year}.csv"))
    cands += list((root / "resources").glob(f"{scenario}/wallon_demands_{year}.csv"))
    cands += [run / f"resources/wallon_demands_{year}.csv"]
    for c in cands:
        if c.exists():
            return pd.read_csv(c, index_col=0)["TWh"]
    return None


def check_softlink(nets, run: Path, scenario: str, rep: Report) -> None:
    sec = "2 · TIMES soft link"
    missing = False
    for y, n in nets.items():
        T = times_demands(run, scenario, y)
        if T is None:
            missing = True
            continue
        ld = n.loads[n.loads.bus.map(n.buses.location) == WAL]

        # --- 2.2 EV identity
        eff = 0.9
        flex = ld.index[ld.carrier == "land transport EV"]
        infl = ld.index[ld.carrier == "land transport EV inflexible"]
        grid = (load_energy(n, flex) / eff + load_energy(n, infl)) / 1e6
        ref = float(T.get("electricity road", np.nan))
        if ref and not np.isnan(ref):
            dev = grid / ref - 1
            msg = f"{y}: PyPSA {grid:.3f} TWh vs TIMES {ref:.3f} ({dev:+.2%})"
            if abs(dev) <= 0.001:
                rep.ok(sec, "EV grid draw = TIMES `electricity road` — " + msg)
            elif abs(dev - 0.0556) < 0.004:
                rep.fail(sec, "EV charger loss counted on the flexible branch only — " + msg,
                         "docs/ev-charging-softlink.md §3")
            elif abs(dev - 0.11) < 0.01:
                rep.fail(sec, "EV charger loss double-counted — " + msg,
                         "docs/ev-charging-softlink.md §3.1")
            else:
                rep.warn(sec, "EV grid draw deviates from TIMES — " + msg)

        # --- 2.3 the other transferred carriers
        for carrier, (rows, tol) in SOFTLINK_MAP.items():
            names = ld.index[ld.carrier == carrier]
            if not len(names):
                continue
            have = load_energy(n, names) / 1e6
            want = float(sum(T.get(r, 0.0) for r in rows))
            if want == 0:
                continue
            dev = have / want - 1
            msg = f"{y}: {carrier} {have:.3f} vs TIMES {want:.3f} ({dev:+.2%})"
            (rep.ok if abs(dev) <= tol else rep.warn)(sec, msg)

        # --- total electricity
        elec_rows = ["total electricity residential", "total electricity services",
                     "electricity road", "electricity rail", "electricity",
                     "total agriculture electricity", "residential cooking electricity"]
        want = float(sum(T.get(r, 0.0) for r in elec_rows))
        ebuses = n.buses.index[(n.buses.location == WAL)
                               & n.buses.carrier.isin(["AC", "low voltage", "EV battery"])]
        have = load_energy(n, n.loads.index[n.loads.bus.isin(ebuses)]) / 1e6
        dev = have / want - 1 if want else np.nan
        msg = f"{y}: BEWAL electric load {have:.3f} TWh vs TIMES total {want:.3f} ({dev:+.2%})"
        (rep.ok if abs(dev) <= 0.005 else rep.warn)(sec, msg)

    if missing:
        rep.warn(sec, "wallon_demands_<year>.csv not found — soft-link checks skipped",
                 "expected under resources/<prefix>/<scenario>/")

    # --- 2.4 heat-pump capacity trajectory (MW at bus0 = heat, see checklist 4.4)
    caps = {}
    for y, n in nets.items():
        hp = n.links[n.links.carrier.str.contains("heat pump", na=False)]
        hp = hp[(hp.bus0.map(n.buses.location) == WAL) | (hp.bus1.map(n.buses.location) == WAL)]
        caps[y] = hp.p_nom_opt.sum()
    s = pd.Series(caps)
    txt = ", ".join(f"{y}: {v:,.0f}" for y, v in s.items())
    if len(s) > 1 and s.diff().dropna().lt(0).any():
        drops = [f"{a}->{b}" for a, b in zip(s.index[:-1], s.index[1:]) if s[b] < s[a]]
        rep.warn(sec, "BEWAL heat-pump capacity falls across a horizon step (" + ", ".join(drops) + ")",
                 f"MW: {txt}\ncheck existing_capacities.heat_stock_age_profile; under option B' this "
                 "may instead be the pinned peak — read heat delivered, not capacity")
    else:
        rep.ok(sec, f"BEWAL heat-pump capacity non-decreasing (MW: {txt})")


# --------------------------------------------------------------------------- #
# level 3 — accounting identities
# --------------------------------------------------------------------------- #

def check_identities(nets, rep: Report, full: bool) -> None:
    sec = "3 · accounting"
    carriers = ["AC", "low voltage"]
    if full:
        carriers += ["H2", "gas", "solid biomass", "biogas",
                     "rural heat", "urban decentral heat", "urban central heat"]
    for y, n in nets.items():
        for bc in carriers:
            buses = n.buses.index[(n.buses.location == WAL) & (n.buses.carrier == bc)]
            if not len(buses):
                continue
            s = bus_balance(n, buses)
            resid = s.sum() / 1e6
            gross = s[s > 0].sum() / 1e6
            rel = abs(resid) / gross if gross else 0.0
            msg = f"{y} BEWAL '{bc}': residual {resid:+.4f} TWh on {gross:.1f} TWh gross ({rel:.2%})"
            if rel < 1e-3:
                rep.ok(sec, msg)
            elif rel < 5e-3:
                rep.warn(sec, msg)
            else:
                rep.fail(sec, msg, "a link port (bus2/bus3, efficiency2/3) is probably unaccounted")

        # Belgium-wide electricity
        beb = n.buses.index[n.buses.location.isin(BE_NODES)
                            & n.buses.carrier.isin(["AC", "low voltage"])]
        s = bus_balance(n, beb)
        gross = s[s > 0].sum() / 1e6
        rel = abs(s.sum() / 1e6) / gross if gross else 0
        msg = f"{y} Belgium AC+LV: residual {s.sum()/1e6:+.4f} TWh on {gross:.1f} TWh gross ({rel:.2%})"
        (rep.ok if rel < 5e-3 else rep.warn)(sec, msg)

    # annual-energy limits
    for y, n in nets.items():
        for car in ANNUAL_ENERGY_CARRIERS:
            g = n.generators[(n.generators.bus.map(n.buses.location) == WAL)
                             & (n.generators.carrier == car)]
            if not len(g) or "e_sum_max" not in g:
                continue
            used = n.generators_t.p[g.index].mul(
                n.snapshot_weightings.generators, axis=0).sum().sum() / 1e6
            cap = g.e_sum_max.sum() / 1e6
            if not np.isfinite(cap):
                continue
            msg = f"{y} BEWAL {car}: {used:.3f} TWh used of e_sum_max {cap:.3f} TWh"
            if used <= cap * 1.001:
                rep.ok(sec, msg)
            else:
                rep.fail(sec, msg, "annual-energy potential exceeded")


# --------------------------------------------------------------------------- #
# level 4 — constraints
# --------------------------------------------------------------------------- #

REN_AGG = {"offwind-ac": "offwind-all", "offwind-dc": "offwind-all",
           "offwind-float": "offwind-all", "offwind": "offwind-all",
           "solar": "solar-all", "solar-utility": "solar-all",
           "solar-hsat": "solar-all", "solar rooftop": "solar-all",
           "nuclear": "nuclear-all", "nuclear (SMR)": "nuclear-all"}
LINK_AGG = {"nuclear-all", "CCGT", "CCGT-all"}


def check_agg_limits(nets, agg_file: Path, rep: Report) -> None:
    sec = "4.1 · aggregate capacity limits"
    if not agg_file or not agg_file.exists():
        rep.warn(sec, f"limits file not found ({agg_file}) — skipped")
        return
    agg = pd.read_csv(agg_file, index_col=[0, 1], header=[0, 1])
    rep.info(sec, f"file: {agg_file}")

    # a 10x-out-of-line value in a row is almost always a typo
    for (region, car), row in agg.iterrows():
        vals = pd.to_numeric(row.xs("min", level=1), errors="coerce").dropna()
        if len(vals) < 3:
            continue
        med = vals[vals > 0].median()
        if not med or np.isnan(med):
            continue
        odd = vals[vals > 8 * med]
        for yr, v in odd.items():
            rep.warn(sec, f"suspicious value in the limits file: {region}/{car} {yr} min = {v:,.0f}",
                     f"other years median {med:,.0f} — verify this is not a decimal typo")

    for y, n in nets.items():
        g = n.generators.copy()
        g["node"] = g.bus.map(n.buses.location)
        g["cg"] = g.carrier.replace(REN_AGG)
        l = n.links.copy()
        l["node"] = l.bus1.map(n.buses.location)
        l["cg"] = l.carrier.replace(REN_AGG)

        for (region, car) in agg.index:
            if (str(y), "max") not in agg.columns:
                continue
            cap = pd.to_numeric(pd.Series([agg.loc[(region, car), (str(y), "max")]]),
                                errors="coerce").iloc[0]
            if not np.isfinite(cap):
                continue
            nodes = list(BE_NODES) if region == "BE" else [region]
            if car in LINK_AGG:
                s = l[l.node.isin(nodes) & (l.cg == car)]
                if not len(s):
                    continue
                tot = float((s.p_nom_opt * s.efficiency).sum())
                ext = float((s[s.p_nom_extendable].p_nom_opt
                             * s[s.p_nom_extendable].efficiency).sum())
                unit = "MW_e"
            else:
                s = g[g.node.isin(nodes) & (g.cg == car)]
                if not len(s):
                    continue
                tot = float(s.p_nom_opt.sum())
                ext = float(s[s.p_nom_extendable].p_nom_opt.sum())
                unit = "MW"
            msg = (f"{y} {region}/{car}: total {tot:,.0f} {unit} vs max {cap:,.0f} "
                   f"(extendable tranche {ext:,.0f})")
            if tot <= cap * 1.001:
                rep.ok(sec, msg)
            elif abs(ext - cap) < max(1.0, 0.001 * cap):
                rep.fail(sec, "cap bound the EXTENDABLE tranche only — " + msg,
                         "add_CCL_constraints does not subtract existing capacity from the "
                         "generator `max` RHS, so a myopic cap resets every horizon "
                         "(docs/run-review-checklist.md §4.1)")
            else:
                rep.fail(sec, "aggregate max exceeded — " + msg)


def check_potentials(nets, pot_file: Path, rep: Report) -> None:
    sec = "4.2 · Walloon potentials"
    if not pot_file or not pot_file.exists():
        rep.warn(sec, f"{pot_file} not found — skipped")
        return
    pot = pd.read_csv(pot_file)
    pot = pot[pot.bus == WAL]
    for _, r in pot[pot.parameter == "p_nom_max"].iterrows():
        y = int(r.year)
        if y not in nets:
            continue
        n = nets[y]
        g = n.generators[(n.generators.bus.map(n.buses.location) == WAL)
                         & (n.generators.carrier == r.technology)]
        if not len(g):
            continue
        tot, ext = float(g.p_nom_opt.sum()), float(g[g.p_nom_extendable].p_nom_opt.sum())
        cap = float(r.value)
        msg = f"{y} BEWAL {r.technology}: total {tot:,.0f} MW vs p_nom_max {cap:,.0f} (extendable {ext:,.0f})"
        if tot <= cap * 1.001:
            rep.ok(sec, msg)
        elif abs(ext - cap) < max(1.0, 0.001 * cap):
            rep.fail(sec, "potential bound the extendable vintage only — " + msg,
                     "per-vintage p_nom_max lets the cap reset at every myopic horizon")
        else:
            rep.fail(sec, "Walloon potential exceeded — " + msg)

    for _, r in pot[(pot.parameter == "p_nom_min") & (pot.technology == "CCGT")].iterrows():
        y = int(r.year)
        if y not in nets:
            continue
        n = nets[y]
        s = links_to(nets[y], WAL, "CCGT")
        if not len(s):
            continue
        ext = float((s[s.p_nom_extendable].p_nom_opt * s[s.p_nom_extendable].efficiency).sum())
        tot = float((s.p_nom_opt * s.efficiency).sum())
        floor = float(r.value)
        msg = f"{y} BEWAL CCGT: total {tot:,.0f} MW_e (extendable {ext:,.0f}) vs p_nom_min {floor:,.0f}"
        if abs(ext - floor) < max(1.0, 0.01 * floor):
            rep.warn(sec, "CCGT floor re-imposed on the new vintage — " + msg,
                     "a floor meant for the total adds `floor` MW_e of NEW capacity at every horizon")
        else:
            rep.ok(sec, msg)


def check_ntc(nets, ntc_dir: Path, rep: Report) -> None:
    sec = "4.3 · interconnection / NTC"
    iso = {"DE": "DEU", "FR": "FRA", "GB": "GBR", "LU": "LUX", "NL": "NLD"}
    for y, n in nets.items():
        f = ntc_dir / f"ntc_{y}.csv"
        if not f.exists():
            rep.warn(sec, f"{f.name} missing — skipped")
            continue
        ntc = pd.read_csv(f)
        ntc = ntc[ntc.source_country_code == "BEL"].set_index("target_country_code")["NTC_MW"]
        for c, code in iso.items():
            if code not in ntc.index:
                continue
            li = n.lines.copy()
            li["l"] = li.bus0.map(n.buses.location)
            li["r"] = li.bus1.map(n.buses.location)
            m = li[(li.l.str.startswith("BE") & li.r.eq(c)) | (li.l.eq(c) & li.r.str.startswith("BE"))]
            lk = n.links.copy()
            lk["l"] = lk.bus0.map(n.buses.location)
            lk["r"] = lk.bus1.map(n.buses.location)
            md = lk[lk.carrier.eq("DC")
                    & ((lk.l.str.startswith("BE") & lk.r.eq(c)) | (lk.l.eq(c) & lk.r.str.startswith("BE")))]
            # OSM DC interconnectors are split fwd/reversed — count the pair once
            dc = float(md.p_nom_opt.sum() / max(len(md), 1)) if len(md) else 0.0
            usable = float((m.s_nom_opt * m.s_max_pu).sum()) + dc
            nominal = float(m.s_nom_opt.sum()) + dc
            want = float(ntc[code])
            msg = (f"{y} BE-{c}: NTC file {want:,.0f} MW | network nominal {nominal:,.0f} | "
                   f"usable (after s_max_pu) {usable:,.0f}")
            if abs(usable - want) <= 0.02 * want:
                rep.ok(sec, msg)
            else:
                rep.warn(sec, f"usable capacity is {usable/want:.0%} of the NTC — " + msg,
                         "AC lines carry s_max_pu=0.7 and DC links do not; decide which "
                         "convention set_NTCs.py should implement")


def check_co2(nets, rep: Report) -> None:
    sec = "4.4 · CO2"
    for y, n in nets.items():
        gc = n.global_constraints
        if not len(gc):
            continue
        glob = gc.loc["CO2Limit"] if "CO2Limit" in gc.index else None
        per = gc[gc.index.str.startswith("co2_limit_per_country")]
        if glob is not None and len(per):
            s = per.constant.sum()
            if abs(s - glob.constant) / max(abs(glob.constant), 1) < 1e-4:
                rep.warn(sec, f"{y}: per-country caps sum EXACTLY to the global CO2Limit "
                              f"({s/1e6:,.1f} Mt) — both bind, so the effective carbon price is "
                              "the SUM of the two duals")
            mu_w = float(per.loc["co2_limit_per_countryBEWAL", "mu"]) if \
                "co2_limit_per_countryBEWAL" in per.index else np.nan
            eff = abs(float(glob.mu)) + abs(mu_w)
            rep.info(sec, f"{y}: effective BEWAL CO2 price = |{float(glob.mu):.1f}| + "
                          f"|{mu_w:.1f}| = {eff:.0f} EUR/t")
        for name in ("co2_sequestration_limit", "biomass limit", "unsustainable biomass limit",
                     "lv_limit"):
            if name in gc.index:
                r = gc.loc[name]
                binding = abs(float(r.mu)) > 1e-6
                rep.info(sec, f"{y}: {name} {r.sense} {float(r.constant):,.3e} "
                              f"mu={float(r.mu):,.2f} {'(BINDING)' if binding else ''}")


# --------------------------------------------------------------------------- #
# level 5/6 — cheap plausibility
# --------------------------------------------------------------------------- #

def check_plausibility(nets, rep: Report) -> None:
    sec = "5 · plausibility (BEWAL)"
    for y, n in nets.items():
        w = n.snapshot_weightings.generators
        g = n.generators[n.generators.bus.map(n.buses.location) == WAL]
        for car, (lo, hi) in CF_WINDOWS.items():
            s = g[g.carrier == car]
            cap = float(s.p_nom_opt.sum())
            if cap < 1.0:
                continue
            e = float(n.generators_t.p[s.index].mul(w, axis=0).sum().sum())
            cf = e / (cap * float(w.sum()))
            msg = f"{y} {car}: {cap:,.0f} MW, {e/1e6:.2f} TWh, CF {cf:.1%}"
            (rep.ok if lo <= cf <= hi else rep.warn)(sec, msg + f" (expected {lo:.0%}-{hi:.0%})")

        # heat-pump effective COP
        hp = n.links[n.links.carrier.str.contains("heat pump", na=False)]
        hp = hp[(hp.bus0.map(n.buses.location) == WAL) | (hp.bus1.map(n.buses.location) == WAL)]
        if len(hp):
            p0 = float(n.links_t.p0[hp.index].mul(n.snapshot_weightings.objective, axis=0).sum().sum())
            p1 = float(n.links_t.p1[hp.index].mul(n.snapshot_weightings.objective, axis=0).sum().sum())
            heat, elec = max(-p0, -p1), max(p0, p1)
            if elec > 0:
                cop = heat / elec
                msg = f"{y} BEWAL heat pumps: effective COP {cop:.2f} ({heat/1e6:.2f} TWh_th / {elec/1e6:.2f} TWh_e)"
                (rep.ok if 2.0 <= cop <= 4.5 else rep.warn)(sec, msg)

    # build rates
    sec2 = "5.2 · build rates (BEWAL)"
    steps = {2030: 5, 2040: 10, 2050: 10}
    prev = {2030: 2025, 2040: 2030, 2050: 2040}
    for car, limit in (("onwind", 300.0), ("solar", 400.0), ("solar-hsat", 400.0),
                       ("solar rooftop", 400.0)):
        caps = {}
        for y, n in nets.items():
            g = n.generators[(n.generators.bus.map(n.buses.location) == WAL)
                             & (n.generators.carrier == car)]
            caps[y] = float(g.p_nom_opt.sum())
        for y, dt in steps.items():
            if y not in caps or prev[y] not in caps:
                continue
            rate = (caps[y] - caps[prev[y]]) / dt
            if rate > limit:
                rep.warn(sec2, f"{car} {prev[y]}→{y}: +{rate:,.0f} MW/yr "
                               f"({caps[prev[y]]:,.0f} → {caps[y]:,.0f} MW)",
                         f"historical Walloon additions are well below {limit:,.0f} MW/yr")
    # zero-capital-cost degenerate capacities
    sec3 = "5.5 · degenerate (zero-capital-cost) capacities"
    y = max(nets)
    n = nets[y]
    l = n.links[(n.links.bus1.map(n.buses.location) == WAL)
                & (n.links.capital_cost.abs() < 1e-9)
                & (n.links.p_nom_opt > 50)]
    if len(l):
        s = l.groupby("carrier").p_nom_opt.sum().sort_values(ascending=False)
        rep.warn(sec3, f"{y}: capacities with capital_cost = 0 — not a result, do not plot",
                 s.round(0).to_string())


# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", type=Path, help="results/<prefix>/<scenario>")
    ap.add_argument("--full", action="store_true", help="add the slow per-bus balance sweep")
    ap.add_argument("--csv-only", action="store_true", help="skip everything needing the .nc files")
    ap.add_argument("--agg-limits", type=Path, default=None)
    ap.add_argument("--potentials", type=Path,
                    default=Path("data/walloon/custom_potentials.csv"))
    ap.add_argument("--ntc-dir", type=Path, default=Path("data/walloon"))
    ap.add_argument("--scenario", default=None)
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.WARNING)
    run = args.run
    if not run.exists():
        print(f"no such results tree: {run}", file=sys.stderr)
        return 2
    scenario = args.scenario or run.name

    rep = Report()
    check_provenance(run, rep)
    check_solver(run, rep)

    if not args.csv_only:
        import pypsa  # imported late so --csv-only works without a solver env

        nets = {}
        for y in HORIZONS:
            p = run / "networks" / f"base_s_adm___{y}.nc"
            if p.exists():
                nets[y] = pypsa.Network(str(p))
            else:
                rep.fail("0 · provenance", f"solved network missing: {p.name}")
        if nets:
            check_softlink(nets, run, scenario, rep)
            check_identities(nets, rep, args.full)
            agg = args.agg_limits
            if agg is None:
                cfg = next((run / "configs").glob("config.*_*.yaml"), None)
                m = re.search(r"file:\s*(data/walloon/agg_p_nom_minmax_\S+\.csv)",
                              cfg.read_text()) if cfg else None
                agg = Path(m.group(1)) if m else None
            check_agg_limits(nets, agg, rep)
            check_potentials(nets, args.potentials, rep)
            check_ntc(nets, args.ntc_dir, rep)
            check_co2(nets, rep)
            check_plausibility(nets, rep)

    print(rep.render())
    print("\nJudgement calls (levels 5-8) stay with you — see docs/run-review-checklist.md")
    return 1 if rep.worst >= 2 else 0


if __name__ == "__main__":
    sys.exit(main())
