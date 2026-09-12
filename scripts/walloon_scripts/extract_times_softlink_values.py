#!/usr/bin/env python3
"""Extract the per-scenario TIMES softlink values from a `.vd`.

Three of the Walloon scenario settings are **TIMES outputs fed back into
PyPSA**, not PyPSA assumptions. They were hand-extracted once from the central
`.vd` (see the header comments of the generated CSVs), which is fine for one
scenario and wrong for a batch: every sensitivity has its own import
trajectory, its own PV mix and its own industrial capture, and silently
inheriting the central scenario's numbers turns a sensitivity into a hybrid.

    self_sufficiency.limit_twh   VAR_Act of `Transfo_Imp`   (one-way annual
                                 Walloon electricity inflow, TWh/a)
    sector.rooftop_share         VAR_Cap of the ERNW_PV-* plant processes
                                 (roof / (roof + greenfield))
    sector.industry_cc_floor     VAR_FOut of CO2STOCK at `STORAGEMININD`
                                 (industrial CO2 captured, kt/a)

Usage:
    # one scenario, print the YAML/CSV to paste or write
    python scripts/walloon_scripts/extract_times_softlink_values.py \
        data/walloon/scen_central_v01_260911_1109.vd

    # write the two generated CSVs for a scenario and print its YAML block
    python scripts/walloon_scripts/extract_times_softlink_values.py \
        data/walloon/scen_sensibilite_taxshift_260911_1109.vd \
        --scenario scen_taxshift --write

    # prove the extractor against the known-good central values
    python scripts/walloon_scripts/extract_times_softlink_values.py \
        data/walloon/scen_central_demande_haute_v01_260907_0709.vd --self-test

`--self-test` reproduces the numbers that were hand-extracted on 2026-09-04/05
and currently sit in the tree, so a change to this script that breaks the
agreement with the hand extraction fails loudly instead of quietly moving
every scenario.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WAL = ROOT / "data" / "walloon"

VD_COLUMNS = [
    "Attribute", "Commodity", "Process", "Period",
    "Region", "Vintage", "TimeSlice", "UserConstraint", "Value",
]

# Walloon region code in TIMES-WAL.
REGION = "RW"

# One-way annual electricity inflow. `solve_network.py` documents the PyPSA
# analogue (`Import_p`) as the hourly positive part of BEWAL net inflow summed
# over the year — including the other Belgian regions, because TIMES-WAL's
# system boundary is Wallonia.
IMPORT_PROCESS = "Transfo_Imp"

# Rooftop = buildings + large roof + residential homes; the denominator adds
# greenfield. VAR_Ncap is NOT added and the demand-side RSDPVELC / COMPVELC /
# INDPVELC and the resource process ELCSOL00 are excluded — see the header of
# data/walloon/times_pv_rooftop_share.csv.
PV_ROOF = ("ERNW_PV-Buildings_SOL_N", "ERNW_PV-Large_Roof_SOL_N", "ERNW_PV-RES_Homes_SOL_N")
PV_GROUND = ("ERNW_PV-GreenField_SOL_N",)

# Demand-side PV, excluded by the convention above. All four are behind-the-
# meter and therefore rooftop. Excluding them is only harmless while the plant
# processes dominate: PyPSA's `add_rooftop_share_constraint` compares `solar
# rooftop` against the WHOLE BEWAL solar fleet, so the honest TIMES analogue
# includes these. Kept out of the default to preserve the share the central
# scenario has been run with; `--include-demand-side` switches convention and
# the divergence is always reported.
PV_DEMAND_SIDE = ("RSDPVELC", "COMPVELC", "INDPVELC", "AGRPVELC")

# Report loudly when the two conventions disagree by more than this (per unit).
SHARE_DIVERGENCE_WARN = 0.05

CAPTURE_PROCESS = "STORAGEMININD"
CAPTURE_COMMODITY = "CO2STOCK"

# Hand-extracted reference values currently in the tree (2026-09-04/05), used
# by --self-test. Their source is `scen_central_demande_haute_v2_260903_0309.vd`
# — the 3 Sept export, NOT the 7 Sept one the last production run took its
# demands from. This extractor reproduces all five exactly against the 3 Sept
# vd; against the 7 Sept vd the rooftop share is 0.6 pp lower and the 2035
# capture 2.2 % lower, which is a genuine difference between the two TIMES
# runs rather than an extraction error. Self-test with the 3 Sept file.
SELF_TEST = {
    "imports_twh": {2030: 2.94, 2040: 6.47, 2050: 10.0},
    "capture_kt": {2035: 4364.60197031038, 2040: 5076.88289217246},
}


def load_vd(path: Path) -> pd.DataFrame:
    """Read a VEDA `.vd` dump. Comment lines start with `*`."""
    df = pd.read_csv(
        path, comment="*", header=None, names=VD_COLUMNS,
        quotechar='"', dtype=str, low_memory=False,
    )
    df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    df["Period"] = pd.to_numeric(df["Period"], errors="coerce").astype("Int64")
    return df.dropna(subset=["Value", "Period"])


def _sum_by_period(df: pd.DataFrame) -> dict[int, float]:
    return {int(y): float(v) for y, v in df.groupby("Period")["Value"].sum().items()}


def electricity_imports_twh(vd: pd.DataFrame) -> dict[int, float]:
    """Annual one-way Walloon electricity inflow, TWh/a.

    VAR_Act of `Transfo_Imp` is reported per timeslice and vintage; the annual
    figure is their sum. TIMES-WAL reports activity in PJ, so the sum is
    converted (1 TWh = 3.6 PJ).
    """
    sel = vd[
        (vd["Attribute"] == "VAR_Act")
        & (vd["Process"] == IMPORT_PROCESS)
        & (vd["Region"] == REGION)
    ]
    return {y: v / 3.6 for y, v in _sum_by_period(sel).items()}


def pv_capacity_gw(
    vd: pd.DataFrame, include_demand_side: bool = False
) -> dict[int, tuple[float, float]]:
    """(rooftop, greenfield) Walloon PV capacity per period, GW."""
    cap = vd[(vd["Attribute"] == "VAR_Cap") & (vd["Region"] == REGION)]
    roof_procs = list(PV_ROOF) + (list(PV_DEMAND_SIDE) if include_demand_side else [])
    roof = _sum_by_period(cap[cap["Process"].isin(roof_procs)])
    ground = _sum_by_period(cap[cap["Process"].isin(PV_GROUND)])
    return {
        y: (roof.get(y, 0.0), ground.get(y, 0.0))
        for y in sorted(set(roof) | set(ground))
    }


def pv_rooftop_share(
    vd: pd.DataFrame, include_demand_side: bool = False
) -> dict[int, float]:
    """Rooftop share of Walloon PV capacity, per unit."""
    out: dict[int, float] = {}
    for year, (roof, ground) in pv_capacity_gw(vd, include_demand_side).items():
        if roof + ground > 0:
            out[year] = roof / (roof + ground)
    return out


def industrial_capture_kt(vd: pd.DataFrame) -> dict[int, float]:
    """Industrial CO2 sent to storage, kt/a."""
    sel = vd[
        (vd["Attribute"] == "VAR_FOut")
        & (vd["Process"] == CAPTURE_PROCESS)
        & (vd["Commodity"] == CAPTURE_COMMODITY)
        & (vd["Region"] == REGION)
    ]
    return _sum_by_period(sel)


def _fmt(d: dict[int, float], nd: int) -> str:
    return "\n".join(f"      {y}: {v:.{nd}f}" for y, v in sorted(d.items()))


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("vd", type=Path, help="TIMES .vd export")
    ap.add_argument("--scenario", help="scenario name; required with --write")
    ap.add_argument("--write", action="store_true",
                    help="write data/walloon/times_{pv_rooftop_share,industrial_capture}_<scenario>.csv")
    ap.add_argument("--self-test", action="store_true",
                    help="check against the hand-extracted central values")
    ap.add_argument("--include-demand-side", action="store_true",
                    help=("count RSDPVELC/COMPVELC/INDPVELC/AGRPVELC as rooftop. "
                          "Off by default to keep the convention the central "
                          "scenario was run with; the divergence is always reported."))
    ap.add_argument("--horizons", type=int, nargs="+", default=[2030, 2040, 2050],
                    help="horizons for the self_sufficiency block (default: 2030 2040 2050)")
    args = ap.parse_args()

    if args.write and not args.scenario:
        ap.error("--write needs --scenario")
    if not args.vd.is_file():
        ap.error(f"no such file: {args.vd}")

    vd = load_vd(args.vd)
    imports = electricity_imports_twh(vd)
    rooftop = pv_rooftop_share(vd, args.include_demand_side)
    other = pv_rooftop_share(vd, not args.include_demand_side)
    capture = industrial_capture_kt(vd)

    print(f"# {args.vd.name}  ({len(vd):,} rows)")
    print("\n# self_sufficiency.limit_twh (TWh/a, TIMES Transfo_Imp)")
    print(_fmt({y: v for y, v in imports.items() if y in args.horizons}, 2))
    convention = "all PV incl. demand-side" if args.include_demand_side else "plant PV only"
    print(f"\n# rooftop share (per unit, {convention})")
    print(_fmt(rooftop, 4))

    # The two conventions agree while the plant processes dominate and diverge
    # sharply when they do not — realiste 2030 is 0.35 plant-only vs 0.90 all-PV,
    # because TIMES builds almost no plant PV that year while 2.2 GW of
    # behind-the-meter PV stays on the roofs. Pinning the plant-only share there
    # would force PyPSA to make two thirds of Walloon 2030 PV ground-mounted.
    diverging = {
        y: (rooftop[y], other[y])
        for y in sorted(set(rooftop) & set(other))
        if abs(rooftop[y] - other[y]) > SHARE_DIVERGENCE_WARN
    }
    if diverging:
        alt = "plant PV only" if args.include_demand_side else "all PV incl. demand-side"
        print(f"\n# WARNING: the two rooftop-share conventions disagree by more than "
              f"{SHARE_DIVERGENCE_WARN:.0%}:")
        for y, (a, b) in diverging.items():
            print(f"#   {y}: {a:.4f} ({convention})  vs  {b:.4f} ({alt})")
        print("#   PyPSA pins `solar rooftop` against the WHOLE BEWAL solar fleet, so a "
              "\n#   large gap means the pinned share does not describe that fleet. "
              "Review\n#   before running, or turn rooftop_share off for this scenario.")

    print("\n# industrial capture (kt/a)")
    print(_fmt(capture, 2))

    if args.self_test:
        bad = []
        for year, want in SELF_TEST["imports_twh"].items():
            got = imports.get(year)
            # The tree's 2050 value is the rounded 10.0; allow 1 % or 0.05 TWh.
            if got is None or abs(got - want) > max(0.05, 0.01 * want):
                bad.append(f"imports {year}: got {got}, tree has {want}")
        for year, want in SELF_TEST["capture_kt"].items():
            got = capture.get(year)
            if got is None or abs(got - want) > 0.01 * want:
                bad.append(f"capture {year}: got {got}, tree has {want}")
        if bad:
            print("\nSELF-TEST FAILED:")
            for b in bad:
                print(f"  ✗ {b}")
            return 1
        print("\nSELF-TEST PASSED — matches the hand-extracted values in the tree.")

    if args.write:
        rp = WAL / f"times_pv_rooftop_share_{args.scenario}.csv"
        cp = WAL / f"times_industrial_capture_{args.scenario}.csv"
        hdr = f"# Extracted from {args.vd.name} by scripts/walloon_scripts/{Path(__file__).name}.\n"
        # `rooftop_gw` / `utility_gw` are not read by the model (only `share`
        # is); they are carried so a reviewer can see whether the pinned share
        # corresponds to a capacity PyPSA can actually reach.
        caps = pv_capacity_gw(vd, args.include_demand_side)
        rp.write_text(
            hdr + f"# Rooftop share of TIMES PV capacity (VAR_Cap, {convention}).\n"
            + "year,share,rooftop_gw,utility_gw\n"
            + "".join(
                f"{y},{v:.6f},{caps[y][0]:.6f},{caps[y][1]:.6f}\n"
                for y, v in sorted(rooftop.items())
            )
        )
        cp.write_text(
            hdr + "# TIMES STORAGEMININD VAR_FOut of CO2STOCK, kt/a.\n"
            + "year,kt\n"
            + "".join(f"{y},{v:.6f}\n" for y, v in sorted(capture.items()))
        )
        print(f"\nwrote {rp.relative_to(ROOT)}\nwrote {cp.relative_to(ROOT)}")
        print("\nYAML for config/scenarios.walloon.yaml:")
        print(f"  sector:\n    rooftop_share:\n      enable: true\n      node: BEWAL\n"
              f"      file: {rp.relative_to(ROOT)}\n"
              f"    industry_cc_floor:\n      enable: true\n      node: BEWAL\n"
              f"      file: {cp.relative_to(ROOT)}")
        print("  self_sufficiency:\n    self_sufficiency_constraint: true\n"
              "    mode: absolute\n    nodes:\n    - BEWAL\n    limit_twh:")
        print(_fmt({y: v for y, v in imports.items() if y in args.horizons}, 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
