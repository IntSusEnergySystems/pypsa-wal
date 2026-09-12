#!/usr/bin/env python3
"""Generate the nuclear CAPEX tipping-point sweep.

The question (cabinet sensitivity, Sept 2026): *with Walloon nuclear capacity
left to the optimiser, how low must the investment cost of new nuclear go
before 2 GW of new capacity appears in the mix — 3 GW in total once the
existing prolonged plant is counted?*

One scenario per CAPEX point. Each writes a `config/scenarios/<name>.csv`
override table in the master CSV's schema, carrying exactly three kinds of row:

1. ``cost:nuclear:investment`` at the swept value (2030 / 2040 / 2050).

2. ``agg:BEWAL:nuclear-all:min`` relaxed to the **existing prolonged fleet**
   (Tihange 3 LTO, 1 000 MW) at 2045 and 2050. The central scenario pins
   min = max there (1 750 / 3 000 MW) to reproduce the TIMES trajectory
   exactly; a pinned capacity cannot reveal a tipping point. The *max* is left
   at the central value, so the sweep answers "does the optimiser fill the
   envelope the central scenario imposes?" — which is the question asked.

3. ``agg:BE:nuclear-all:min`` lowered by the same amount.

   **Row 3 is the trap.** `add_CCL_constraints` groups by (location, carrier),
   and `BE` is a parent row over BEVLG + BEWAL + BEBRU. Relaxing BEWAL alone
   leaves BE's 2050 floor at 6 000 MW = 3 000 BEVLG + 3 000 BEWAL, which
   re-imposes the full Walloon build through the parent and yields a flat
   sweep that looks like "nuclear is always built". BE's floor therefore has
   to fall to BEVLG's own contribution plus the Walloon LTO:

       2045  2 750 -> 2 000   (1 000 BEVLG + 1 000 BEWAL LTO)
       2050  6 000 -> 4 000   (3 000 BEVLG + 1 000 BEWAL LTO)

   Flanders' own caps are untouched, so the surrounding nodes keep the central
   trajectory exactly as specified.

Usage:
    python scripts/walloon_scripts/make_nuclear_sweep.py            # write
    python scripts/walloon_scripts/make_nuclear_sweep.py --dry-run
    python scripts/walloon_scripts/make_nuclear_sweep.py --capex 9500 6000 3000

Then materialise the input files and register the scenarios:
    python scripts/build_common_parameters.py --write --all-scenarios
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "config" / "input_parameters_for_models.csv"
OUT_DIR = ROOT / "config" / "scenarios"

# EUR2025/kW_e. 9500 is the central value (data/walloon/custom_costs.csv,
# "Mecatech Forum du nucleaire IEA") and is included so the sweep carries its
# own reference point: same free-capacity setup, unchanged cost.
DEFAULT_CAPEX = (9500, 7500, 6000, 5000, 4000, 3000)

# Walloon nuclear that exists without any new build: Tihange 3 long-term
# operation, repeatable retrofit (`electricity.retrofit_nuclear_once: false`).
LTO_BEWAL_MW = 1000

# (target, year) -> relaxed floor. See the module docstring, point 3.
AGG_FLOORS = {
    ("agg:BEWAL:nuclear-all:min", 2045.0): LTO_BEWAL_MW,
    ("agg:BEWAL:nuclear-all:min", 2050.0): LTO_BEWAL_MW,
    ("agg:BE:nuclear-all:min", 2045.0): 1000 + LTO_BEWAL_MW,
    ("agg:BE:nuclear-all:min", 2050.0): 3000 + LTO_BEWAL_MW,
}

SOURCE = "PyPSA nuclear tipping-point sweep (cabinet sensitivity 2026-09)"


def scenario_name(capex: int) -> str:
    return f"scen_nuctip_{capex}"


def build_override(master: pd.DataFrame, capex: int) -> pd.DataFrame:
    """Whole-row overrides for one CAPEX point, in the master's schema."""
    rows: list[pd.Series] = []

    inv = master[master["pypsa_wal_target"] == "cost:nuclear:investment"]
    if inv.empty:
        sys.exit("master CSV has no cost:nuclear:investment row")
    for _, r in inv.iterrows():
        row = r.copy()
        row["value"] = float(capex)
        row["source"] = SOURCE
        row["note_complementaire"] = (
            f"Swept value, {capex} EUR2025/kW_e. Central scenario: "
            f"{float(inv['value'].iloc[0]):.0f}. Varied to locate the cost at "
            "which the optimiser builds 2 GW of new Walloon nuclear (3 GW "
            "total with the prolonged plant). Nothing else in the cost table "
            "moves, so a difference against another sweep point is "
            "attributable to nuclear CAPEX alone."
        )
        rows.append(row)

    for (target, year), value in AGG_FLOORS.items():
        sel = master[
            (master["pypsa_wal_target"] == target) & (master["year"] == year)
        ]
        if sel.empty:
            sys.exit(f"master CSV has no row {target} @ {year:.0f}")
        row = sel.iloc[0].copy()
        old = float(row["value"])
        row["value"] = float(value)
        row["source"] = SOURCE
        row["note_complementaire"] = (
            f"Floor relaxed {old:.0f} -> {value:.0f} MW so nuclear capacity is "
            "chosen by the optimiser instead of pinned to the TIMES "
            "trajectory. The matching p_nom_max is deliberately left at the "
            "central value: the sweep asks whether the optimiser fills the "
            "envelope, not whether it would exceed it. The BE parent row moves "
            "by the same amount because add_CCL_constraints groups by "
            "(location, carrier) and a 6 000 MW BE floor would re-impose the "
            "Walloon build through the parent. Flanders is unchanged."
        )
        rows.append(row)

    return pd.DataFrame(rows)[master.columns.tolist()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capex", type=int, nargs="+", default=list(DEFAULT_CAPEX),
                    metavar="EUR_PER_KW",
                    help=f"CAPEX points to sweep (default: {' '.join(map(str, DEFAULT_CAPEX))})")
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    args = ap.parse_args()

    master = pd.read_csv(MASTER)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for capex in sorted(set(args.capex), reverse=True):
        name = scenario_name(capex)
        frame = build_override(master, capex)
        path = OUT_DIR / f"{name}.csv"
        print(f"{'would write' if args.dry_run else 'wrote'} "
              f"{path.relative_to(ROOT)}  ({len(frame)} override rows, "
              f"nuclear investment = {capex} EUR2025/kW_e)")
        if not args.dry_run:
            frame.to_csv(path, index=False, lineterminator="\n")

    print(
        "\nNext:\n"
        "  python scripts/build_common_parameters.py --write --all-scenarios\n"
        "  # then register the scenarios in config/scenarios.walloon.yaml"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
