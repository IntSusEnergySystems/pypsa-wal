# SPDX-License-Identifier: MIT
"""
Reconcile the TIMES and PyPSA decentral-heating cost assumptions.

The heating soft-link makes PyPSA deliver TIMES's appliance mix. That is only
meaningful if the two models price the appliances alike: if PyPSA's heat pumps
are cheaper or its gas dearer than TIMES's, part of the divergence the constraint
removes was a *parameter* inconsistency, and the constraint is papering over it.
``docs/heat-softlink.md`` lists this as the prerequisite for trusting the
transfer.

**The comparison is annuity to annuity**, which is what makes it possible at all:

* PyPSA's ``capital_cost`` *is* an annuity — ``investment x annuity(lifetime,
  hurdle) + investment x FOM`` in EUR/MW/a.
* TIMES ``Cost_Inv`` is a **constant annual payment stream** over the asset's
  life, not an overnight cost. Verified on the reference ``.vd``: ``CHBALTH101``
  builds 0.0045 GW once in 2022 and pays 0.0469 MEUR/a every period to 2040.

So ``Cost_Inv / VAR_Ncap`` in a process's **first** build period is its annuity in
EUR/kW/a and is directly comparable, with **no assumption about lifetime or
discount rate on either side**. Later periods are unusable: their ``Cost_Inv``
carries the streams of earlier vintages.

The overnight cost is *not* recoverable from the ``.vd`` — ``NCAP_COST`` is an
input and the file carries results only. Recovering it needs the VEDA ``~FI_T``
tables from ICEDD/Climact.

Units: TIMES heating capacity is GW of **heat output** (activity is PJ of heat),
so MEUR/GW == EUR/kW_th, matching PyPSA's ``EUR/kW_th`` for every decentral
heating row except ``decentral solar thermal`` (EUR/1000 m2), which is therefore
excluded.

Usage::

    python scripts/walloon_scripts/compare_heat_costs.py \
        --vd ../TIMES_PyPSA/data/scen_demande_haute_v01_260727_fix_nuc_2807.vd \
        --costs resources/times-pypsa/scen_demande_haute/costs_2030_processed.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

#: TIMES `Aggregation Level 2` label -> the PyPSA cost-table technology whose
#: annuity it should be compared against. Only decentral building heat: the
#: district-heating and industrial groups are out of scope of the soft-link.
TIMES_TO_PYPSA = {
    "Residential urban decentral Heat pump": "decentral air-sourced heat pump",
    "Residential rural Heat pump": "decentral air-sourced heat pump",
    "Commercial Heat pump": "decentral air-sourced heat pump",
    "Residential urban decentral gas heater": "decentral gas boiler",
    "Residential rural gas heater": "decentral gas boiler",
    "Commercial gas boiler": "decentral gas boiler",
    "Residential urban decentral oil heater": "decentral oil boiler",
    "Residential rural oil heater": "decentral oil boiler",
    "Commercial Oil boiler": "decentral oil boiler",
    "Residential urban decentral electric heater": "decentral resistive heater",
    "Residential rural electric heater": "decentral resistive heater",
    "Commercial electrical stove": "decentral resistive heater",
    "Residential urban decentral biomass heater": "biomass boiler",
    "Residential rural biomass heater": "biomass boiler",
    "Commercial Biomass boiler": "biomass boiler",
    "Residential urban decentral geothermal heating": "decentral ground-sourced heat pump",
    "Residential rural geothermal heating": "decentral ground-sourced heat pump",
    "commercial Geothermal": "decentral ground-sourced heat pump",
}

#: Excluded because the two sides do not share a capacity unit.
EXCLUDED = {
    "Residential urban decentral solar thermal": "PyPSA prices solar thermal per 1000 m2",
    "Residential rural solar thermal": "PyPSA prices solar thermal per 1000 m2",
    "Commercial solar thermal": "PyPSA prices solar thermal per 1000 m2",
}


def times_annuities(vd_file: Path, mapping_processes: Path) -> pd.DataFrame:
    """EUR/kW_th/a annuity per TIMES heating process, from its first build period."""
    from times_pypsa.pipeline import load_raw_records

    raw = load_raw_records(vd_file, start_year=2020)
    mp = pd.read_csv(mapping_processes).rename(
        columns={"Technology (Process)": "process_code"}
    )
    labels = set(TIMES_TO_PYPSA) | set(EXCLUDED)
    heat = mp[mp["Aggregation Level 2"].isin(labels)]

    piv = (
        raw[
            raw["process_code"].isin(heat["process_code"])
            & raw["variable"].isin(["Cost_Inv", "VAR_Ncap"])
        ]
        .pivot_table(
            index=["process_code", "year"],
            columns="variable",
            values="value",
            aggfunc="sum",
        )
        .fillna(0.0)
    )
    rows = []
    for code, sub in piv.groupby(level=0):
        built = sub[sub["VAR_Ncap"] > 0]
        if built.empty:
            continue
        first = built.index.get_level_values("year").min()
        ncap = float(sub.loc[(code, first), "VAR_Ncap"])
        cost = float(sub.loc[(code, first), "Cost_Inv"])
        if ncap <= 0 or cost <= 0:
            continue
        label = heat.loc[heat["process_code"] == code, "Aggregation Level 2"].iloc[0]
        rows.append(
            {
                "process_code": code,
                "times_label": label,
                "pypsa_technology": TIMES_TO_PYPSA.get(label, ""),
                "first_build_year": int(first),
                "GW_built": ncap,
                # MEUR/GW == EUR/kW
                "times_annuity_eur_per_kw_a": cost / ncap,
            }
        )
    return pd.DataFrame(rows)


def pypsa_annuities(costs_file: Path) -> pd.Series:
    """``capital_cost`` in EUR/kW_th/a from a processed cost table."""
    costs = pd.read_csv(costs_file, index_col=0)
    return costs["capital_cost"] / 1e3


def compare(times: pd.DataFrame, pypsa: pd.Series) -> pd.DataFrame:
    """Capacity-weighted TIMES annuity per PyPSA technology, against PyPSA's."""
    rated = times[times["pypsa_technology"] != ""].copy()
    rated["weight"] = rated["GW_built"]
    grouped = rated.groupby("pypsa_technology").apply(
        lambda g: pd.Series(
            {
                "processes": len(g),
                "GW_built": g["GW_built"].sum(),
                "times_min": g["times_annuity_eur_per_kw_a"].min(),
                "times_max": g["times_annuity_eur_per_kw_a"].max(),
                "times_weighted": (
                    g["times_annuity_eur_per_kw_a"] * g["weight"]
                ).sum()
                / g["weight"].sum(),
            }
        ),
        include_groups=False,
    )
    grouped["pypsa"] = pypsa.reindex(grouped.index)
    grouped["ratio_times_over_pypsa"] = grouped["times_weighted"] / grouped["pypsa"]
    return grouped.sort_values("ratio_times_over_pypsa")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vd", type=Path, required=True)
    parser.add_argument("--costs", type=Path, required=True)
    parser.add_argument(
        "--mapping-processes",
        type=Path,
        default=None,
        help="defaults to the installed times_pypsa data directory",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    mapping = args.mapping_processes
    if mapping is None:
        from times_pypsa import default_mappings_dir

        mapping = Path(default_mappings_dir()) / "mapping_processes.csv"

    times = times_annuities(args.vd, mapping)
    table = compare(times, pypsa_annuities(args.costs))
    pd.set_option("display.width", 200)
    print("Annuity, EUR/kW_th/a — TIMES first-build period vs PyPSA capital_cost\n")
    print(table.round(2).to_string())
    print("\nExcluded, no shared capacity unit:")
    for label, why in EXCLUDED.items():
        print(f"  {label}: {why}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        times.to_csv(args.out, index=False)
        table.to_csv(args.out.with_name(f"{args.out.stem}_summary.csv"))
        print(f"\nWrote {args.out} and its summary.")


if __name__ == "__main__":
    main()
