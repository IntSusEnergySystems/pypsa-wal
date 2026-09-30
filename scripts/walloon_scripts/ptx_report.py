# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""Power-to-X and the Walloon CO2 balance of a solved run, per horizon.

Written for the low-CCS / power-to-fuel test (`scen_test_lowccs_ptx`,
docs/logs/2026-09-30_cabinet_batch_20260930_2010_1h.md §12), usable on any run:

    python scripts/walloon_scripts/ptx_report.py results/walloon/scen_test_lowccs_ptx \\
        --against results/walloon/scen_central [--node BEWAL] [--out ptx.csv]

For each horizon it reports:

* the node's CO2 balance: capture by carrier, the lever-D net export, the cap,
  its dual (GlobalConstraint ``co2_export_limit_<node>``) and the overage
  (net export above the cap), and the CO2 drawn by utilisation links;
* power-to-X capacity (MW of input, all vintages) and throughput (TWh of input)
  by node — where the hydrogen and the synthetic fuel are made matters as much
  as whether they are;
* the node's hydrogen balance: electrolysis, SMR, SMR CC, net pipeline import.
  FT on imported SMR hydrogen is gas-to-liquid, not power-to-fuel;
* the prices that decide it, and the free-dispatch capex recovery of this
  horizon's extendable FT and electrolyser at the node (100 % = break-even).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

from scripts.walloon_scripts.named_pins import CO2_EXPORT_CARRIERS

PTX = ["H2 Electrolysis", "Fischer-Tropsch", "methanolisation", "Sabatier",
       "SMR", "SMR CC", "DAC"]
NODES = ["BEWAL", "BEVLG", "BEBRU", "FR", "DE", "NL", "GB", "LU"]


def ports(n):
    """(bus column, efficiency column) for every port after bus0."""
    out = []
    for c in n.links.columns:
        m = re.fullmatch(r"bus(\d+)", c)
        if m and m.group(1) != "0":
            k = m.group(1)
            out.append((c, "efficiency" if k == "1" else f"efficiency{k}"))
    return out


def energy(n, link) -> float:
    """Annual input flow on bus0, MWh (0 for a link with no dispatch)."""
    if link not in n.links_t.p0:
        return 0.0
    return float((n.links_t.p0[link] * n.snapshot_weightings.generators).sum())


def location(n, link) -> str:
    row = n.links.loc[link]
    bus = row.bus1 if row.carrier == "DAC" else row.bus0
    loc = n.buses.location.get(bus, "")
    return loc if loc else link.split(" ")[0]


def mean_price(n, bus):
    if bus not in n.buses_t.marginal_price:
        return np.nan
    w = n.snapshot_weightings.generators
    return float((n.buses_t.marginal_price[bus] * w).sum() / w.sum())


def recovery(n, carrier, node) -> float:
    """Free-dispatch gross margin / annualised capex of this horizon's vintage, %."""
    cand = n.links[(n.links.carrier == carrier) & n.links.p_nom_extendable]
    cand = cand[[location(n, l) == node for l in cand.index]]
    if cand.empty or not cand.capital_cost.iloc[-1]:
        return np.nan
    link = cand.index[-1]
    row = n.links.loc[link]
    lam = n.buses_t.marginal_price
    if row.bus0 not in lam:
        return np.nan
    margin = -lam[row.bus0] - row.marginal_cost
    for bus_col, eff_col in ports(n):
        bus, eff = row[bus_col], row.get(eff_col, np.nan)
        if isinstance(bus, str) and bus in lam and not pd.isna(eff) and eff:
            margin = margin + eff * lam[bus]
    pmax = n.get_switchable_as_dense("Link", "p_max_pu")[link]
    w = n.snapshot_weightings.objective
    gross = float((w * np.maximum(margin, 0) * pmax).sum())
    return 100 * gross / row.capital_cost


def co2_balance(n, node) -> dict:
    stored = f"{node} co2 stored"
    rec = {}
    for bus_col, eff_col in ports(n):
        hit = n.links[(n.links[bus_col] == stored)
                      & ~n.links.carrier.isin(CO2_EXPORT_CARRIERS)]
        for link, row in hit.iterrows():
            eff = row.get(eff_col, np.nan)
            if pd.isna(eff) or eff == 0:
                continue
            t = energy(n, link) * eff / 1e6
            key = f"capture {row.carrier}" if eff > 0 else f"use {row.carrier}"
            rec[key] = rec.get(key, 0.0) + abs(t)
    links = n.links[n.links.carrier.isin(CO2_EXPORT_CARRIERS)]
    net = sum(energy(n, l) for l in links.index[links.bus0 == stored])
    net -= sum(energy(n, l) * links.at[l, "efficiency"] for l in links.index[links.bus1 == stored])
    rec["net export (lever D)"] = net / 1e6
    gc = n.global_constraints
    name = f"co2_export_limit_{node}"
    if name in gc.index:
        cap = gc.at[name, "constant"] / 1e6
        rec["export cap"] = cap
        rec["export cap dual EUR/t"] = gc.at[name, "mu"]
        rec["overage"] = max(0.0, rec["net export (lever D)"] - cap)
    return {k: round(v, 3) for k, v in rec.items()}


def h2_balance(n, node) -> dict:
    h2 = f"{node} H2"
    rec = {}
    for carrier in ("H2 Electrolysis", "SMR", "SMR CC"):
        L = n.links[(n.links.carrier == carrier) & (n.links.bus1 == h2)]
        rec[carrier] = sum(energy(n, l) * n.links.at[l, "efficiency"] for l in L.index) / 1e6
    pipes = n.links[n.links.carrier.str.contains("H2 pipeline", na=False)]
    w = n.snapshot_weightings.generators
    imp = 0.0
    for link, row in pipes.iterrows():
        for k in ("0", "1"):
            if row[f"bus{k}"] == h2 and link in getattr(n.links_t, f"p{k}"):
                imp -= float((getattr(n.links_t, f"p{k}")[link] * w).sum())
    rec["net pipeline import"] = imp / 1e6
    return {k: round(v, 3) for k, v in rec.items()}


def report(path: Path, node: str) -> pd.DataFrame:
    rows = []
    for nc in sorted((path / "networks").glob("*.nc")):
        year = int(re.search(r"(\d{4})\.nc$", nc.name).group(1))
        n = pypsa.Network(nc)

        def add(section, metric, value):
            rows.append(dict(run=path.name, year=year, section=section, metric=metric, value=value))

        add("system", "objective (bn EUR)", round(n.objective / 1e9, 4))
        for k, v in co2_balance(n, node).items():
            add(f"{node} CO2 (Mt/a)", k, v)
        for k, v in h2_balance(n, node).items():
            add(f"{node} H2 (TWh/a)", k, v)
        for carrier in PTX:
            L = n.links[n.links.carrier == carrier]
            for loc in NODES:
                idx = [l for l in L.index if location(n, l) == loc]
                mw = float(n.links.loc[idx, "p_nom_opt"].sum()) if idx else 0.0
                twh = sum(energy(n, l) for l in idx) / 1e6
                if mw > 1 or twh > 0.01:
                    add("PtX MW", f"{carrier} @ {loc}", round(mw, 1))
                    add("PtX TWh in", f"{carrier} @ {loc}", round(twh, 2))
        for label, bus in (("co2 stored", f"{node} co2 stored"), ("H2", f"{node} H2"),
                           ("electricity", node), ("EU oil", "EU oil"),
                           ("EU methanol", "EU methanol")):
            add("prices (EUR/unit)", label, round(mean_price(n, bus), 2))
        gc = n.global_constraints
        for label, name in (("CO2Limit dual", "CO2Limit"),
                            (f"{node} national cap dual", f"co2_limit_per_country{node}")):
            if name in gc.index:
                add("prices (EUR/unit)", label, round(float(gc.at[name, "mu"]), 2))
        for carrier in ("Fischer-Tropsch", "H2 Electrolysis", "methanolisation"):
            add(f"{node} capex recovery (%)", carrier, round(recovery(n, carrier, node), 1))
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run", type=Path)
    ap.add_argument("--against", type=Path, help="comparator run, e.g. the central")
    ap.add_argument("--node", default="BEWAL")
    ap.add_argument("--out", type=Path, help="write the tidy table as CSV")
    args = ap.parse_args()
    df = report(args.run, args.node)
    if args.against:
        df = pd.concat([df, report(args.against, args.node)], ignore_index=True)
    if args.out:
        df.to_csv(args.out, index=False)
    table = df.pivot_table(index=["section", "metric"], columns=["year", "run"],
                           values="value", aggfunc="first", sort=False)
    with pd.option_context("display.width", 250, "display.max_rows", 500,
                           "display.max_columns", 20):
        print(table.to_string())


if __name__ == "__main__":
    main()
