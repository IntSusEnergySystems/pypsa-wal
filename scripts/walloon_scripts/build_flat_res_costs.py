# SPDX-License-Identifier: MIT
"""
Build ``data/walloon/custom_costs_scen_central_flat_res_costs.csv``: the central cost
table with the cost of renewable technologies (biogas included) held flat at its 2025
value in every later horizon.

Why a generated file. Costs fall with the planning horizon through two channels:
the per-horizon rows of ``custom_costs.csv`` (learning curves of PV, onshore wind,
biogas ...) and, for every technology without such a row, the horizon's own
technology-data table (``data/costs/archive/v0.14.0/costs_<year>.csv``). A scenario
that wants "no learning for renewables" has to cut both, which a hand edit cannot
do reliably, and the copy would drift as soon as the central costs are updated.
This script reads the two sources once and writes the scenario copy:

* for each technology of ``FLAT_TECHNOLOGIES`` and each parameter of
  ``FLAT_PARAMETERS`` (investment, FOM, VOM, fuel, lifetime) the **2025 effective value** is
  taken - the custom-costs row of 2025 (or ``all``) when there is one, else the
  technology-data 2025 value, which is what ``process_cost_data.py`` would use;
* every per-horizon row of that (technology, parameter) is dropped from the copy and
  one ``all`` row carrying the 2025 value is added, in the unit of its source row so
  that ``process_cost_data._convert_to_MW`` treats it exactly like the original.

Efficiency and discount rates are not touched. Nothing else moves: a 2025
solve of the flat scenario is the central's 2025 solve.

    python scripts/walloon_scripts/build_flat_res_costs.py           # write
    python scripts/walloon_scripts/build_flat_res_costs.py --check   # exit 1 if stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "walloon" / "custom_costs.csv"
RAW_2025 = ROOT / "data" / "costs" / "archive" / "v0.14.0" / "costs_2025.csv"
OUT = ROOT / "data" / "walloon" / "custom_costs_scen_central_flat_res_costs.csv"

BASE_YEAR = "2025"

#: Technology-data names (the cost-table index before ``COST_TABLE_RENAMES``).
#: Renewable generation: wind, PV, hydro, geothermal, solar heat, and the biogas
#: chain. Solid-biomass conversion plants, heat pumps, storage and electrolysis are
#: *not* listed: they are conversion or storage technologies, not renewable resources.
FLAT_TECHNOLOGIES = (
    # wind
    "onwind",
    "offwind",
    "offwind-ac-station",
    "offwind-ac-connection-submarine",
    "offwind-ac-connection-underground",
    "offwind-dc-station",
    "offwind-dc-connection-submarine",
    "offwind-dc-connection-underground",
    "offwind-float",
    "offwind-float-station",
    "offwind-float-connection-submarine",
    "offwind-float-connection-underground",
    # solar PV
    "solar",
    "solar-rooftop",
    "solar-rooftop commercial",
    "solar-rooftop residential",
    "solar-utility",
    "solar-utility single-axis tracking",
    # hydro, geothermal, solar heat
    "hydro",
    "ror",
    "geothermal",
    "central geothermal heat source",
    "central solar thermal",
    "decentral solar thermal",
    # biogas chain
    "biogas",
    "biogas CC",
    "biogas upgrading",
    "biogas manure",
    "biogas plus hydrogen",
)
#: Lifetime is frozen with the costs: technology-data lengthens some lifetimes with the
#: year (central geothermal 25 -> 30 years), which lowers the annuity, so leaving it
#: free would let the annualised capital cost fall although investment and FOM are flat.
FLAT_PARAMETERS = ("investment", "FOM", "VOM", "fuel", "lifetime")

NOTE = (
    "Held flat at the 2025 value (scripts/walloon_scripts/build_flat_res_costs.py): "
    "renewable cost sensitivity, no learning after 2025"
)


def build(base: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """Return the scenario cost table (same columns as ``base``)."""
    base = base.copy()
    raw = raw.set_index(["technology", "parameter"])
    keys = [(t, p) for t in FLAT_TECHNOLOGIES for p in FLAT_PARAMETERS]

    new_rows = []
    drop = pd.Series(False, index=base.index)
    for tech, par in keys:
        rows = base[(base.technology == tech) & (base.parameter == par)]
        eff = rows[rows.planning_horizon.isin([BASE_YEAR, "all"])]
        if len(eff) > 1:
            raise ValueError(f"{tech}/{par}: several custom rows apply to {BASE_YEAR}")
        if len(eff) == 1:
            value, unit = eff.iloc[0]["value"], eff.iloc[0]["unit"]
        elif (tech, par) in raw.index:
            value, unit = raw.loc[(tech, par), "value"], raw.loc[(tech, par), "unit"]
        else:
            continue  # the technology has no such parameter: nothing to freeze
        drop |= (base.technology == tech) & (base.parameter == par)
        new_rows.append(
            {
                "planning_horizon": "all",
                "technology": tech,
                "parameter": par,
                "value": value,
                "unit": unit,
                "source": NOTE,
                "further_description": "",
            }
        )
    out = pd.concat([base[~drop], pd.DataFrame(new_rows)], ignore_index=True)
    return out[list(base.columns)]


def render() -> str:
    # Strings throughout: the untouched rows must come back byte-identical ("25", not "25.0").
    base = pd.read_csv(BASE, dtype=str, keep_default_na=False)
    raw = pd.read_csv(RAW_2025, dtype=str, keep_default_na=False)
    out = build(base, raw)
    return out.to_csv(index=False, lineterminator="\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="fail if the committed file is stale")
    args = ap.parse_args()
    text = render()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print(f"{OUT.relative_to(ROOT)} is stale: re-run without --check", file=sys.stderr)
            return 1
        print("flat renewable costs: in sync")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
