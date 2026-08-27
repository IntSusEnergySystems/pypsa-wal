#!/usr/bin/env python3
# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Derive the renewable build-rate limits from IRENA annual statistics.

Writes ``data/walloon/res_build_rates.csv``: the single best annual capacity
addition observed per node and carrier, which ``add_CCL_constraints`` multiplies
by ``solving.agg_p_nom_limits.growth_multiplier`` and the length of the planning
period to bound new build. See ``docs/renewable-potentials.md`` §3.

Why a committed file rather than a call at solve time
-----------------------------------------------------
``add_CCL_constraints`` runs inside ``solve_network.py``, i.e. in
``rule solve_sector_network_myopic``, which ``cluster/nic5.sh solve`` executes on
NIC5. ``pm.data.IRENASTAT()`` needs internet and a populated
``~/.local/share/powerplantmatching`` cache, neither of which a compute node is
guaranteed to have. IRENA publishes annually, not per run, so the derivation is a
deliberate step: run this locally, review the diff, commit.

Source
------
``powerplantmatching.data.IRENASTAT()`` — the same series
``scripts/add_existing_baseyear.py`` already uses to place existing renewable
capacity into build-year vintages. Annual additions are ``diff`` of the reported
capacity stock, clipped at zero, exactly as that script computes them. Because it
is a stock series, repowering and decommissioning net out, so these are *net*
additions and understate gross build slightly.

IRENASTAT is country-level. Belgium is split across ``BEWAL`` / ``BEVLG`` /
``BEBRU`` by each region's share of existing capacity in the network — the same
apportionment ``add_existing_baseyear`` uses to distribute IRENA capacity.

Usage
-----
    python scripts/walloon_scripts/build_res_build_rates.py \\
        --network resources/<prefix>/<run>/networks/base_s_adm___2025.nc

    python scripts/walloon_scripts/build_res_build_rates.py --check   # verify in sync
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "walloon" / "res_build_rates.csv"

COUNTRIES = ["BE", "DE", "FR", "GB", "NL", "LU"]
BE_REGIONS = ["BEWAL", "BEVLG", "BEBRU"]
# IRENA technology label -> the carrier name used in agg_p_nom_minmax_*.csv
TECH_MAP = {"Onshore": "onwind", "PV": "solar-all", "Offshore": "offwind-all"}
# network carriers making up each agg carrier, for the Belgian apportionment
FAMILY = {
    "onwind": ["onwind"],
    "solar-all": ["solar", "solar-hsat", "solar rooftop"],
    "offwind-all": ["offwind-ac", "offwind-dc", "offwind-float"],
}


def irena_annual_records() -> pd.DataFrame:
    """Best single-year addition per country and carrier, from IRENASTAT."""
    import powerplantmatching as pm

    ir = pm.data.IRENASTAT().powerplant.convert_country_to_alpha2()
    ir = ir[ir.Country.isin(COUNTRIES)]
    stock = (
        ir.groupby(["Technology", "Country", "Year"]).Capacity.sum().unstack()
    )

    rows = []
    for tech, carrier in TECH_MAP.items():
        if tech not in stock.index.get_level_values(0):
            continue
        # annual additions = diff of the stock series, as add_existing_baseyear does
        additions = stock.loc[tech].diff(axis=1).clip(lower=0)
        for country in additions.index:
            s = additions.loc[country].dropna()
            if s.empty or s.max() <= 0:
                continue
            rows.append(
                {
                    "node": country,
                    "carrier": carrier,
                    "record_annual_MW": round(float(s.max()), 1),
                    "record_year": int(s.idxmax()),
                    "best_5yr_mean_MW": round(float(s.rolling(5).mean().max()), 1),
                    "mean_2020_2024_MW": round(float(s.tail(5).mean()), 1),
                    "source": "IRENASTAT via powerplantmatching, annual additions 2000-2024",
                }
            )
    return pd.DataFrame(rows)


def belgian_shares(network: Path) -> pd.DataFrame:
    """Each Belgian region's share of existing capacity, per agg carrier."""
    import pypsa

    n = pypsa.Network(str(network))
    g = n.generators
    out = []
    for carrier, members in FAMILY.items():
        sel = g[g.carrier.isin(members)].copy()
        # a generator's region is its bus, with " low voltage" stripped (rooftop)
        sel["region"] = sel.bus.str.replace(" low voltage", "", regex=False)
        sel = sel[sel.region.isin(BE_REGIONS)]
        # existing = standing capacity plus any committed extendable floor
        standing = sel.p_nom.where(~sel.p_nom_extendable, sel.p_nom_min)
        tot = standing.groupby(sel.region).sum()
        if tot.sum() <= 0:
            continue
        for region, mw in tot.items():
            out.append(
                {
                    "node": region,
                    "carrier": carrier,
                    "share": float(mw / tot.sum()),
                    "existing_MW": round(float(mw), 1),
                }
            )
    return pd.DataFrame(out)


def build(network: Path) -> pd.DataFrame:
    records = irena_annual_records()
    shares = belgian_shares(network)

    rows = [r for _, r in records.iterrows()]
    be = records[records.node == "BE"].set_index("carrier")
    for _, s in shares.iterrows():
        if s.carrier not in be.index:
            continue
        parent = be.loc[s.carrier]
        rows.append(
            pd.Series(
                {
                    "node": s.node,
                    "carrier": s.carrier,
                    "record_annual_MW": round(parent.record_annual_MW * s.share, 1),
                    "record_year": parent.record_year,
                    "best_5yr_mean_MW": round(parent.best_5yr_mean_MW * s.share, 1),
                    "mean_2020_2024_MW": round(parent.mean_2020_2024_MW * s.share, 1),
                    "source": (
                        f"IRENASTAT BE annual additions x {s.share:.3f} "
                        f"({s.existing_MW:.0f} of {s.existing_MW / s.share:.0f} MW existing)"
                    ),
                }
            )
        )
    df = pd.DataFrame(rows)
    return df.sort_values(["carrier", "node"]).reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--network", type=Path, help="a 2025 network, for the Belgian split")
    ap.add_argument("--check", action="store_true", help="verify the file is in sync")
    args = ap.parse_args()

    if args.check:
        if not OUT.exists():
            print(f"FAILED — {OUT.name} is missing")
            return 1
        if not args.network:
            print(f"OK — {OUT.name} present ({len(pd.read_csv(OUT, comment=chr(35)))} rows); "
                  "pass --network to re-derive and compare")
            return 0

    if not args.network:
        ap.error("--network is required to build (needed for the Belgian split)")

    df = build(args.network)

    if args.check:
        old = pd.read_csv(OUT, comment="#")
        merged = old.merge(df, on=["node", "carrier"], suffixes=("_file", "_new"))
        drift = merged[
            (merged.record_annual_MW_file - merged.record_annual_MW_new).abs() > 0.5
        ]
        if len(drift) or len(old) != len(df):
            print(f"FAILED — {OUT.name} differs from a fresh derivation:")
            for _, r in drift.iterrows():
                print(f"  {r.node}/{r.carrier}: file {r.record_annual_MW_file} "
                      f"vs derived {r.record_annual_MW_new}")
            if len(old) != len(df):
                print(f"  row count {len(old)} vs {len(df)}")
            return 1
        print(f"OK — {OUT.name} matches a fresh derivation ({len(df)} rows)")
        return 0

    OUT.write_text(
        "# Renewable build-rate limits. Generated by "
        "scripts/walloon_scripts/build_res_build_rates.py — do not edit by hand.\n"
        "# `record_annual_MW` is the operative figure: add_CCL_constraints bounds new\n"
        "# build per horizon at growth_multiplier x record_annual_MW x period years.\n"
        "# See docs/renewable-potentials.md section 3.\n"
        + df.to_csv(index=False)
    )
    print(f"wrote {OUT.relative_to(ROOT)} ({len(df)} rows)")
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
