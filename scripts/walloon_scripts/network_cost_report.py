#!/usr/bin/env python3
# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
#
# SPDX-License-Identifier: MIT
"""Calibrated Walloon network costs of one solved run, per horizon and layer.

Reads the solved networks, the run's own config and cost tables, and the
exogenous layers of ``data/walloon/network_cost_calibration.csv``, and writes

* ``<run>/csvs/network_costs_calibrated.csv`` — long table: network, view, layer,
  item, horizon, M€2025/a;
* ``<run>/csvs/network_cost_segments.csv`` — the *Distribution* and *Transport*
  totals that ``plot_cost_segments.py --network-costs calibrated`` draws.

Layers and views are those of docs/network-costs-review-20260928.md §2:

* **L1** existing grid (capital charges, sunk, 2025 regulated accounts, constant
  in real terms), **L2** increment (the model's own new capacity, i.e. vintages
  after the first horizon), **L3** non-capacity OPEX, **L4** losses and regulated
  add-ons (PSO, road-use fee, smart meters, other).
* **direct** — the branches touching BEWAL, 50/50 between their two ends, at
  model cost (existing capacity split from the increment).
* **tariff** — what Walloon users pay: the Belgian regulated revenue (Elia,
  Fluxys) plus the Belgian network increments, times Wallonia's share of
  Belgian offtake in that horizon. Elia's tariffs are a national postage stamp.

The segments file uses, for *Distribution*, electricity L1 + L2 + L3 + smart
meters plus gas L1 + L3; for *Transport*, the electricity and methane tariff
views plus the direct H₂ and CO₂ pipelines. Losses are energy (already in
*Production*/*Imports*), and PSO, road-use fee and other add-ons are transfers:
neither is in the segments, both are in the long table.

Usage::

    python scripts/walloon_scripts/network_cost_report.py results/walloon/scen_central
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import yaml

NODE = "BEWAL"
BE = ("BEWAL", "BEVLG", "BEBRU")
HORIZONS = (2025, 2030, 2040, 2050)
CALIBRATION = Path("data/walloon/network_cost_calibration.csv")
INFLATION = 0.024  # nominal 2029 -> EUR2025, 2.4 %/a (2025-2029 CWaPE indexation order)
SKIP_WITHDRAWAL = {
    "DC", "electricity distribution grid", "battery charger", "home battery charger",
    "H2 pipeline", "gas pipeline", "gas pipeline new", "CO2 pipeline", "H2 pipeline retrofitted",
}


def _cal(cal: pd.DataFrame, network: str, item: str, year: int) -> float:
    r = cal[(cal.network == network) & (cal["item"] == item) & (cal.year == year)]
    if r.empty:
        raise KeyError(f"{CALIBRATION}: no {network}/{item}/{year}")
    return float(r.value.iloc[0])


def _twin(c: pd.DataFrame) -> pd.Series:
    t = pd.Series(c.index.str.endswith("-reversed"), index=c.index)
    if "reversed" in c:
        t |= c["reversed"].fillna(False).astype(bool)
    return t


def _branches(n: pypsa.Network) -> pd.DataFrame:
    """Every transmission branch, reversed twins excluded, with end locations."""
    loc = n.buses.location
    rows = []
    lines = n.lines
    for name, r in lines.iterrows():
        rows.append((name, "Line", "AC", loc.get(r.bus0, r.bus0), loc.get(r.bus1, r.bus1),
                     r.s_nom, r.s_nom_opt, r.capital_cost, -1))
    carriers = {"DC": "electricity", "gas pipeline": "methane", "gas pipeline new": "methane",
                "H2 pipeline": "H2", "H2 pipeline retrofitted": "H2", "CO2 pipeline": "CO2"}
    L = n.links[n.links.carrier.isin(carriers) & ~_twin(n.links)]
    for name, r in L.iterrows():
        rows.append((name, "Link", r.carrier, loc.get(r.bus0, r.bus0), loc.get(r.bus1, r.bus1),
                     r.p_nom, r.p_nom_opt, r.capital_cost, r.build_year))
    df = pd.DataFrame(rows, columns=["name", "component", "carrier", "loc0", "loc1", "nom",
                                     "nom_opt", "capital_cost", "build_year"]).set_index("name")
    df["group"] = df.carrier.map(lambda c: "electricity" if c in ("AC", "DC") else carriers[c])
    return df


def _offtake(n: pypsa.Network, carrier_buses: dict[str, list[str]]) -> dict[str, float]:
    """Annual withdrawals (MWh) per Belgian region from the given buses."""
    w = n.snapshot_weightings.generators
    out = {}
    for reg, buses in carrier_buses.items():
        e = (n.loads_t.p[n.loads.index[n.loads.bus.isin(buses)]].sum(axis=1) * w).sum()
        for port in ("0", "1", "2", "3", "4"):
            col = f"bus{port}"
            if col not in n.links:
                continue
            L = n.links[n.links[col].isin(buses) & ~n.links.carrier.isin(SKIP_WITHDRAWAL) & ~_twin(n.links)]
            if len(L):
                e += (getattr(n.links_t, f"p{port}")[L.index].clip(lower=0).sum(axis=1) * w).sum()
        out[reg] = float(e)
    return out


def horizon_rows(n, y, first, cal, cfg, costs) -> list[dict]:
    rows = []

    def add(network, view, layer, item, value):
        rows.append(dict(network=network, view=view, layer=layer, item=item, year=y,
                         value=round(float(value) / 1e6, 3)))

    defl = (1 + INFLATION) ** 4
    ydata = 2025 if y <= 2025 else 2029  # add-ons: 2025 budget, then the 2029 one (smart meters done)
    L = n.links
    w = n.snapshot_weightings.generators

    # ---------------- electricity distribution
    net = "electricity_distribution"
    d = L[(L.carrier == "electricity distribution grid") & (L.bus0 == NODE)]
    new = d.build_year > first
    add(net, "regulated", "L1", "existing grid capital charges", _cal(cal, net, "capital", 2025) * 1e6)
    share = _cal(cal, net, "opex_asset_share", 2025)
    g = _cal(cal, net, "ean_growth", 2024)
    opex = _cal(cal, net, "opex", 2025) * (share + (1 - share) * (1 + g) ** (y - 2025))
    add(net, "regulated", "L3", "OPEX (asset + per connection)", opex * 1e6)
    add(net, "model", "L2", "reinforcement (link vintages after the first horizon)",
        (d.p_nom_opt[new] * d.capital_cost[new]).sum())
    add(net, "model", "memo", "model valuation of the first-horizon vintage (not added)",
        (d.p_nom_opt[~new] * d.capital_cost[~new]).sum())
    host = (cfg.get("sector", {}).get("network_calibration") or {}).get("pv_hosting_investment") or 0
    if host:
        ratio = costs.at["electricity distribution grid", "capital_cost"] / costs.at["electricity distribution grid", "investment"]
        pv = n.generators[(n.generators.carrier == "solar rooftop") & (n.generators.bus == f"{NODE} low voltage")
                          & (n.generators.build_year > first)]
        add(net, "model", "L2", "rooftop PV hosting (inside the PV capital cost)",
            pv.p_nom_opt.sum() * host * 1e3 * ratio)
    flow = n.links_t.p0[d.index].clip(lower=0)
    loss = (flow * (1 - d.efficiency)).sum(axis=1)
    add(net, "model", "L4", "losses (energy at the HV price; in Production/Imports)",
        (loss * n.buses_t.marginal_price[NODE] * w).sum())
    for item, label in [("pso", "public service obligations"), ("road_fee", "road-use fee"),
                        ("smart_meters", "smart meters"), ("other", "other regulated items")]:
        v = _cal(cal, net, item, ydata) / (defl if ydata == 2029 else 1)
        add(net, "regulated", "L4", label, v * 1e6)

    # ---------------- gas distribution
    net = "gas_distribution"
    add(net, "regulated", "L1", "existing grid capital charges (keep pathway)", _cal(cal, net, "capital", 2025) * 1e6)
    add(net, "regulated", "L3", "OPEX", _cal(cal, net, "opex", 2025) * 1e6)
    for item, label in [("road_fee", "road-use fee"), ("pso", "public service obligations"),
                        ("other", "other regulated items")]:
        add(net, "regulated", "L4", label, _cal(cal, net, item, 2025) * 1e6)
    gb = L[((L.carrier.str.contains("gas boiler") & ~L.carrier.str.contains("urban central"))
            | L.carrier.str.contains("micro gas")) & L.index.str.startswith(NODE) & (L.build_year >= first)]
    factor = cfg.get("sector", {}).get("gas_distribution_grid_cost_factor", 1.0)
    charge = factor * costs.at["electricity distribution grid", "capital_cost"]
    add(net, "model", "memo", "avoidable per-boiler charge in the objective (not added)",
        gb.p_nom_opt.sum() * charge)

    # ---------------- transmission: direct 50/50 and tariff view
    br = _branches(n)
    touch = (br.loc0 == NODE) | (br.loc1 == NODE)
    ref = getattr(n, "_ref_nom", None)
    nom0 = br.nom if ref is None else ref.reindex(br.index).fillna(0.0)
    exist = np.minimum(br.nom_opt, nom0).where(br.build_year <= first, 0.0)
    incr = br.nom_opt - exist
    for grp in ("electricity", "methane", "H2", "CO2"):
        m = touch & (br.group == grp)
        add(f"{grp}_transmission", "direct", "L1", "existing branches, 50/50 (model cost)",
            0.5 * (exist[m] * br.capital_cost[m]).sum())
        add(f"{grp}_transmission", "direct", "L2", "new branch capacity, 50/50 (model cost)",
            0.5 * (incr[m] * br.capital_cost[m]).sum())
    # Belgian increments for the tariff view: internal branches 100 %, cross-border 50 %
    be0, be1 = br.loc0.isin(BE), br.loc1.isin(BE)
    weight = np.where(be0 & be1, 1.0, np.where(be0 | be1, 0.5, 0.0))
    be_incr = (incr * br.capital_cost * weight).groupby(br.group).sum()

    el = _offtake(n, {r: [r, f"{r} low voltage"] for r in BE})
    s_el = el[NODE] / sum(el.values())
    gas = _offtake(n, {r: [f"{r} gas"] for r in BE if f"{r} gas" in n.buses.index})
    s_gas = gas.get(NODE, 0.0) / sum(gas.values()) if gas else np.nan
    add("electricity_transmission", "tariff", "L1+L3", "Elia 2025 allowed revenue x Walloon offtake share",
        _cal(cal, "electricity_transmission", "elia_allowed_revenue", 2025) * 1e6 * s_el)
    add("electricity_transmission", "tariff", "L2", "Belgian branch increments x Walloon offtake share",
        be_incr.get("electricity", 0.0) * s_el)
    add("methane_transmission", "tariff", "L1+L3", "Fluxys revenue x Walloon gas offtake share",
        _cal(cal, "gas_transmission", "fluxys_allowed_revenue", 2025) * 1e6 * s_gas)
    rows.append(dict(network="electricity_transmission", view="share", layer="-", item="Walloon offtake share",
                     year=y, value=round(s_el, 4)))
    rows.append(dict(network="methane_transmission", view="share", layer="-", item="Walloon gas offtake share",
                     year=y, value=round(s_gas, 4)))
    return rows


def segments(long: pd.DataFrame) -> pd.DataFrame:
    def s(net, view=None, layers=None, items=None):
        m = long.network == net
        if view:
            m &= long.view == view
        if layers:
            m &= long.layer.isin(layers)
        if items:
            m &= long["item"].isin(items)
        return long[m].groupby("year").value.sum()

    distr = (s("electricity_distribution", layers=["L1", "L2", "L3"])
             + s("electricity_distribution", items=["smart meters"])
             + s("gas_distribution", layers=["L1", "L3"]))
    tran = (s("electricity_transmission", view="tariff", layers=["L1+L3", "L2"])
            + s("methane_transmission", view="tariff", layers=["L1+L3"])
            + s("H2_transmission", view="direct")
            + s("CO2_transmission", view="direct"))
    return pd.DataFrame({"distr_wl": distr, "tran_wl": tran}).T


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", type=Path, help="results tree, e.g. results/walloon/scen_central")
    ap.add_argument("--resources", type=Path, default=None,
                    help="resources tree with costs_<y>_processed.csv (default: results -> resources)")
    args = ap.parse_args()
    logging.disable(logging.WARNING)

    run = args.run
    res = args.resources or Path(str(run).replace("results", "resources", 1))
    cal = pd.read_csv(CALIBRATION, comment="#")
    nets = {y: run / "networks" / f"base_s_adm___{y}.nc" for y in HORIZONS}
    nets = {y: f for y, f in nets.items() if f.exists()}
    if not nets:
        sys.exit(f"no solved networks under {run}/networks")
    first = min(nets)

    rows = []
    ref_nom = None
    for y, fn in sorted(nets.items()):
        n = pypsa.Network(fn)
        cfg_fn = run / "configs" / f"config.base_s_adm___{y}.yaml"
        cfg = yaml.safe_load(cfg_fn.read_text()) if cfg_fn.exists() else {}
        cfn = res / f"costs_{y}_processed.csv"
        costs = pd.read_csv(cfn, index_col=0)
        if y == first:
            ref_nom = _branches(n).nom
        n._ref_nom = ref_nom
        rows += horizon_rows(n, y, first, cal, cfg, costs)

    long = pd.DataFrame(rows)
    out = run / "csvs"
    out.mkdir(exist_ok=True)
    long.to_csv(out / "network_costs_calibrated.csv", index=False)
    seg = segments(long)
    seg.to_csv(out / "network_cost_segments.csv")
    pd.set_option("display.width", 200)
    print(long.pivot_table(index=["network", "view", "layer", "item"], columns="year",
                           values="value", aggfunc="sum").round(1).to_string())
    print("\nsegments (M€2025/a):\n" + seg.round(1).to_string())
    print(f"\nwrote {out / 'network_costs_calibrated.csv'} and {out / 'network_cost_segments.csv'}")


if __name__ == "__main__":
    main()
