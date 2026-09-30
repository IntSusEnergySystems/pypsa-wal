#!/usr/bin/env python3
# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
#
# SPDX-License-Identifier: MIT
"""PyPSA ↔ TIMES harmonisation table for energy-bill reporting.

TIMES reports the effect of the scenarios on electricity and gas bills per user
type. This script puts, for every horizon, the PyPSA quantity next to the TIMES
quantity it has to be consistent with, and flags the gaps
(docs/network-costs-review-20260928.md §8):

A  volumes by voltage level and gas by sector (tolerance ±2 %)
B  commodity prices: Belgian zonal electricity price, gas, CO₂ (±10 %)
C  network revenue requirements (from ``network_cost_report.py``) turned into
   €/MWh and set against the TIMES "Fuel Tech" mark-ups; the residual is what
   the mark-up must contain besides the network (taxes, levies, support)
S  support needs: annualised cost minus market revenue of Belgian generation

Writes ``<run>/csvs/bill_harmonisation.csv``. Run ``network_cost_report.py`` on
the same tree first.

Usage::

    python scripts/walloon_scripts/bill_harmonisation.py results/walloon/scen_central
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import yaml

NODE = "BEWAL"
BE = ("BEWAL", "BEVLG", "BEBRU")
HORIZONS = (2025, 2030, 2040, 2050)
PJ = 3.6  # TWh per PJ... inverse: 1 PJ = 1/3.6 TWh; M€/PJ x 3.6 = €/MWh... see _eur_mwh
FUEL_TECH = {
    "RSDELC00": ("electricity", "residential"),
    "COMELC00": ("electricity", "services"),
    "INDELC00": ("electricity", "industry"),
    "AGRELC00": ("electricity", "agriculture"),
    "RSDGMX00": ("gas", "residential"),
    "COMGMX00": ("gas", "services"),
    "INDGMX00": ("gas", "industry (distribution mix)"),
    "INDGAS00": ("gas", "industry (transport)"),
}
ELC = ("ELCHIG", "ELCHIGG", "ELCMED", "ELCLOW")


def read_vd(fn: Path) -> dict:
    """The few TIMES attributes the table needs, summed per key (PJ, M€)."""
    fin = defaultdict(float)          # (commodity, sector prefix, period) -> PJ
    act = defaultdict(float)          # (process, period) -> PJ
    cost = defaultdict(float)         # (process, period) -> M€
    marg = defaultdict(list)          # (commodity, period) -> [M€/PJ]
    with open(fn, encoding="latin-1") as f:
        for line in f:
            if not line.startswith('"'):
                continue
            a = line[1:line.index('"', 1)]
            if a not in ("VAR_FIn", "VAR_Act", "Cost_Act", "EQ_CombalM"):
                continue
            r = next(csv.reader([line]))
            c, p, per, v = r[1], r[2], r[3], float(r[8])
            if a == "VAR_FIn" and c in ELC and not p.startswith("EVTRANS"):
                fin[(c, p[:3].upper(), per)] += v
            elif a == "VAR_Act" and p in FUEL_TECH:
                act[(p, per)] += v
            elif a == "Cost_Act" and p in FUEL_TECH:
                cost[(p, per)] += v
            elif a == "EQ_CombalM" and c in ELC + ("GASNAT",):
                marg[(c, per)].append(v)
    return dict(fin=fin, act=act, cost=cost, marg=marg)


def pypsa_horizon(n: pypsa.Network) -> dict:
    w = n.snapshot_weightings.generators
    mp = n.buses_t.marginal_price
    L = n.links
    out = {}
    # A1 electricity by level at BEWAL
    d = L.index[(L.carrier == "electricity distribution grid") & (L.bus0 == NODE)]
    lv = (n.links_t.p0[d].clip(lower=0).sum(axis=1) * w).sum() / 1e6
    hv_loads = n.loads.index[n.loads.bus == NODE]
    hv = (n.loads_t.p[hv_loads].sum(axis=1) * w).sum() / 1e6
    out["A1_lv_mv_TWh"] = lv
    out["A1_hv_loads_TWh"] = hv
    # B1 zonal price, weighted by the LV inflow of the three Belgian nodes
    flows = {}
    for b in BE:
        di = L.index[(L.carrier == "electricity distribution grid") & (L.bus0 == b)]
        flows[b] = n.links_t.p0[di].clip(lower=0).sum(axis=1)
    tot = sum(flows.values())
    zonal = sum(mp[b] * flows[b] for b in BE) / tot.replace(0, np.nan)
    out["B1_zonal_time_avg"] = float(zonal.mean())
    out["B1_zonal_load_weighted"] = float((zonal * tot * w).sum() / (tot * w).sum())
    out["B1_BEWAL_nodal_time_avg"] = float(mp[NODE].mean())
    lvb = f"{NODE} low voltage"
    f = flows[NODE]
    out["B2_LV_price_flow_weighted"] = float((mp[lvb] * f * w).sum() / (f * w).sum())
    out["B2_HV_price_flow_weighted"] = float((mp[NODE] * f * w).sum() / (f * w).sum())
    out["B3_gas_BEWAL"] = float(mp.get(f"{NODE} gas", pd.Series(np.nan)).mean())
    gc = n.global_constraints
    out["B4_co2_EU"] = float(-gc.mu.get("CO2Limit", np.nan))
    # S1 support needs of Belgian generation
    s = {}
    g = n.generators[n.generators.bus.isin(list(BE) + [b + " low voltage" for b in BE])]
    for car, gg in g.groupby("carrier"):
        if car not in ("onwind", "solar", "solar-hsat", "solar rooftop", "offwind-ac", "offwind-dc", "ror"):
            continue
        p = n.generators_t.p[gg.index]
        rev = sum((p[i] * mp[r.bus] * w).sum() for i, r in gg.iterrows())
        cost = (gg.p_nom_opt * gg.capital_cost).sum() + sum((p[i] * r.marginal_cost * w).sum() for i, r in gg.iterrows())
        s[car] = (cost - rev) / 1e6
    ll = L[L.bus1.isin(BE) & L.carrier.isin(["nuclear", "CCGT", "OCGT"])]
    for car, gg in ll.groupby("carrier"):
        rev = sum((-n.links_t.p1[i] * mp[r.bus1] * w).sum() - (n.links_t.p0[i] * mp[r.bus0] * w).sum() for i, r in gg.iterrows())
        cost = (gg.p_nom_opt * gg.capital_cost).sum() + sum((n.links_t.p0[i] * r.marginal_cost * w).sum() for i, r in gg.iterrows())
        s[car] = (cost - rev) / 1e6
    out["S1"] = s
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", type=Path)
    args = ap.parse_args()
    logging.disable(logging.WARNING)
    run = args.run
    cfg = yaml.safe_load((run / "configs" / "config.base_s_adm___2050.yaml").read_text())
    vd = read_vd(Path(cfg["sector"]["times_file"]))
    netcost = pd.read_csv(run / "csvs" / "network_costs_calibrated.csv")

    rows = []

    def add(group, var, y, py, tm, unit, tol=None, note=""):
        delta = (py / tm - 1) if (tm not in (None, 0) and py is not None and not np.isnan(tm) and not np.isnan(py)) else np.nan
        status = "" if tol is None or np.isnan(delta) else ("pass" if abs(delta) <= tol else "GAP")
        rows.append(dict(group=group, variable=var, year=y, pypsa=py, times=tm, unit=unit,
                         rel_diff=delta, status=status, note=note))

    for y in HORIZONS:
        fn = run / "networks" / f"base_s_adm___{y}.nc"
        if not fn.exists():
            continue
        per = str(y)
        p = pypsa_horizon(pypsa.Network(fn))
        fin = {k: v for k, v in vd["fin"].items() if k[2] == per}
        t_lv_mv = sum(v for (c, s, _), v in fin.items() if c in ("ELCMED", "ELCLOW")) / 3.6
        t_hv = sum(v for (c, s, _), v in fin.items() if c in ("ELCHIGG", "ELCHIG") and s != "EVT") / 3.6
        add("A volumes", "electricity behind the distribution link (LV+MV)", y, p["A1_lv_mv_TWh"], t_lv_mv, "TWh", 0.02,
            "PyPSA link inflow includes the 5 % distribution losses; TIMES counts delivered MV+LV consumption")
        add("A volumes", "electricity drawn at HV (loads on the AC bus)", y, p["A1_hv_loads_TWh"], t_hv, "TWh", 0.02,
            "TIMES ELCHIGG/ELCHIG consumers (industry, rail, power-sector own use)")
        # B prices
        def tmarg(c):
            v = vd["marg"].get((c, per))
            return float(np.mean(v)) * 3.6 if v else np.nan
        add("B prices", "wholesale electricity (BE zonal, time average)", y, p["B1_zonal_time_avg"], tmarg("ELCHIG"),
            "EUR/MWh", 0.10, "TIMES: unweighted mean of EQ_CombalM over its timeslices (durations not in the .vd)")
        add("B prices", "wholesale electricity (BE zonal, load weighted)", y, p["B1_zonal_load_weighted"], tmarg("ELCHIG"),
            "EUR/MWh", 0.10)
        add("B prices", "LV price minus HV price (distribution rent + losses)", y,
            p["B2_LV_price_flow_weighted"] - p["B2_HV_price_flow_weighted"], tmarg("ELCLOW") - tmarg("ELCHIG"),
            "EUR/MWh", None, "PyPSA: recovers the distribution annuity; must not be added to a network tariff")
        add("B prices", "wholesale gas", y, p["B3_gas_BEWAL"], tmarg("GASNAT"), "EUR/MWh", 0.10)
        add("B prices", "EU ETS1 CO2 price (PyPSA dual)", y, p["B4_co2_EU"], np.nan, "EUR/t", None,
            "TIMES ETS price to be supplied by ICEDD")
        # C network revenue requirements vs mark-ups
        nc = netcost[netcost.year == y]
        def v(net, view=None, layers=None, items=None):
            m = nc.network == net
            if view:
                m &= nc.view == view
            if layers:
                m &= nc.layer.isin(layers)
            if items:
                m &= nc["item"].isin(items)
            return nc[m].value.sum()
        r_dist = (v("electricity_distribution", layers=["L1", "L2", "L3"])
                  + v("electricity_distribution", view="regulated", layers=["L4"])
                  + v("electricity_distribution", view="model", layers=["L4"]))
        r_tran = v("electricity_transmission", view="tariff")
        r_gas = v("gas_distribution", view="regulated") + v("methane_transmission", view="tariff")
        e_all = t_lv_mv + t_hv
        add("C networks", "electricity distribution revenue requirement", y, r_dist, np.nan, "MEUR/a", None,
            "L1+L2+L3+L4 of network_costs_calibrated.csv")
        add("C networks", "  per MWh of MV+LV consumption", y, r_dist / t_lv_mv if t_lv_mv else np.nan, np.nan, "EUR/MWh")
        add("C networks", "electricity transmission (tariff view)", y, r_tran, np.nan, "MEUR/a")
        add("C networks", "  per MWh of Walloon consumption", y, r_tran / e_all if e_all else np.nan, np.nan, "EUR/MWh")
        gas_vol = sum(vd["act"].get((pp, per), 0.0) for pp in ("RSDGMX00", "COMGMX00")) / 3.6
        add("C networks", "gas distribution + transmission", y, r_gas, np.nan, "MEUR/a")
        add("C networks", "  per MWh of residential + services gas", y, r_gas / gas_vol if gas_vol else np.nan,
            np.nan, "EUR/MWh", None, "the death-spiral indicator as volumes fall")
        # mark-ups: network part vs residual (taxes, levies, support)
        net_el = (r_dist / t_lv_mv if t_lv_mv else np.nan) + (r_tran / e_all if e_all else np.nan)
        for proc, (carrier, sector) in FUEL_TECH.items():
            a = vd["act"].get((proc, per), 0.0)
            c = vd["cost"].get((proc, per), 0.0)
            if not a:
                continue
            mk = c / a * 3.6
            if carrier == "electricity" and sector != "industry":
                netp = net_el
            elif carrier == "electricity":
                netp = r_tran / e_all if e_all else np.nan
            elif sector in ("residential", "services"):
                netp = r_gas / gas_vol if gas_vol else np.nan
            else:
                netp = np.nan
            add("C mark-ups", f"TIMES {proc} ({carrier}, {sector}) mark-up vs network cost", y, netp, mk, "EUR/MWh",
                None, f"residual {mk - netp:.1f} EUR/MWh = taxes + levies + support, if the mark-up holds them")
        # C5 reconciliation: what TIMES collects through its electricity mark-ups
        # (Σ Cost_Act = Σ mark-up x volume) against the network revenue PyPSA's
        # calibrated system requires. The excess is what the mark-ups hold besides
        # the network (taxes, levies, support) -- or a network cost TIMES counts twice.
        collected = sum(vd["cost"].get((pp, per), 0.0) for pp, (car, _) in FUEL_TECH.items() if car == "electricity")
        add("C reconciliation", "electricity: network revenue required (PyPSA) vs mark-ups collected (TIMES)", y,
            r_dist + r_tran, collected, "MEUR/a", None,
            "TIMES - PyPSA = taxes + levies + support inside the mark-ups; ICEDD to confirm their content")
        collected_g = sum(vd["cost"].get((pp, per), 0.0) for pp, (car, _) in FUEL_TECH.items() if car == "gas")
        add("C reconciliation", "gas: network revenue required (PyPSA) vs mark-ups collected (TIMES)", y,
            r_gas, collected_g, "MEUR/a", None, "same reading for gas; includes ETS2 if TIMES books it there")
        # S support needs
        for car, gap in p["S1"].items():
            add("S support", f"cost minus market revenue, BE {car}", y, gap, np.nan, "MEUR/a")

    df = pd.DataFrame(rows)
    out = run / "csvs" / "bill_harmonisation.csv"
    df.to_csv(out, index=False)
    pd.set_option("display.width", 220, "display.max_colwidth", 70)
    show = df.pivot_table(index=["group", "variable", "unit"], columns="year", values=["pypsa", "times"], aggfunc="first")
    print(show.round(1).to_string())
    gaps = df[df.status == "GAP"]
    print(f"\n{len(gaps)} gap(s) beyond tolerance; wrote {out}")


if __name__ == "__main__":
    main()
