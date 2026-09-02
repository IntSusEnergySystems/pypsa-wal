#!/usr/bin/env python3
# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Validate the renewable capacity limits before a solve.

Checks that the stored overrides in an ``agg_p_nom_minmax_*.csv`` match the design
of ``docs/renewable-potentials.md``, and that the build-rate table covers every
node the caps apply to. Cheap enough to run in CI; the failures it catches
otherwise surface hours into a cluster solve.

The design keeps stored overrides to a minimum. Only two things belong in the CSV:

* **2025** — the base year, pinned with ``min == max`` to the historical fleet, so
  it is a calibration rather than an optimisation.
* **2030 min** — the national target, as the floor of the near-term corridor.

Everything else is computed at run time: the ceiling is
``min(land potential, growth allowance)``, where the potential comes from atlite
(overridden per node only for offshore, §2 of the doc) and the growth allowance
from ``growth_multiplier x`` the IRENA annual record ``x`` the period length.

So a stored maximum after 2025, or a stored minimum after 2030, is a stale
override that would silently override a calculation — which is what this checks.

Exception (item 11): ``BE/offwind-all`` may pin 2030 (``min == max`` = standing
fleet) and carry committed-infrastructure floors after 2030. Other groups keep
the original design.

Usage
-----
    python scripts/walloon_scripts/check_res_envelope.py \\
        data/walloon/agg_p_nom_minmax_demande_haute.csv \\
        [--rates data/walloon/res_build_rates.csv] [--multiplier 2.0]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

RES_CARRIERS = ("onwind", "offwind-all", "solar-all")
# nodes the walloon config solves; the file also carries inert rows for countries
# outside `countries:` (BG, DK, IE, …) which are not ours to police
MODELLED = ("BE", "BEWAL", "DE", "FR", "GB", "NL", "LU")
# offshore only exists where there is a coast
NO_OFFSHORE = ("BEWAL", "LU")
BASE_YEAR, CORRIDOR_YEAR = 2025, 2030
# Item 11: Belgian PEZ is committed infrastructure on a slipped calendar, not
# a 2030 NECP floor. This group may pin 2030 (min=max=standing fleet) and
# carry floors after 2030. Every other RES group keeps the original design.
PEZ_RETIME = {("BE", "offwind-all")}


def load_envelope(path: Path) -> pd.DataFrame:
    """Long-format (country, carrier, year, min, max) from the wide CSV."""
    df = pd.read_csv(path, index_col=[0, 1], header=[0, 1])
    years = [c for c in df.columns.get_level_values(0).unique() if str(c).isdigit()]
    rows = []
    for y in years:
        for (country, carrier), row in df[y].iterrows():
            rows.append(
                {
                    "country": country,
                    "carrier": carrier,
                    "year": int(y),
                    "min": row.get("min"),
                    "max": row.get("max"),
                }
            )
    return pd.DataFrame(rows).sort_values(["country", "carrier", "year"])


def expected_groups() -> set[tuple[str, str]]:
    return {
        (n, c)
        for n in MODELLED
        for c in RES_CARRIERS
        if not (c == "offwind-all" and n in NO_OFFSHORE)
    }


def check(env: pd.DataFrame, rates: pd.DataFrame | None = None) -> list[str]:
    errors: list[str] = []
    ours = env[env.country.isin(MODELLED) & env.carrier.isin(RES_CARRIERS)]

    for row in ours.itertuples():
        key = f"{row.country}/{row.carrier} {row.year}"
        has_min, has_max = pd.notna(row.min), pd.notna(getattr(row, "max"))

        if has_min and has_max and row.min > getattr(row, "max") + 1e-6:
            errors.append(f"{key}: min {row.min:,.0f} > max {getattr(row, 'max'):,.0f} — empty LP")

        if row.year > BASE_YEAR and has_max:
            pez_pin = (row.country, row.carrier) in PEZ_RETIME and row.year == CORRIDOR_YEAR
            if not pez_pin:
                errors.append(
                    f"{key}: stored max {getattr(row, 'max'):,.0f} — after {BASE_YEAR} the "
                    "ceiling is computed as min(land potential, growth allowance); a stored "
                    "value silently overrides it"
                )
            elif abs(row.min - getattr(row, "max")) > 1e-6:
                errors.append(
                    f"{key}: PEZ 2030 pin requires min == max (standing fleet), "
                    f"got min {row.min:,.0f} max {getattr(row, 'max'):,.0f}"
                )
        if row.year > CORRIDOR_YEAR and has_min:
            if (row.country, row.carrier) not in PEZ_RETIME:
                errors.append(
                    f"{key}: stored min {row.min:,.0f} — past {CORRIDOR_YEAR} the scenario is a "
                    "techno-economic optimum with no policy floor"
                )

    present = set(zip(ours.country, ours.carrier))
    for country, carrier in sorted(expected_groups() - present):
        errors.append(f"{country}/{carrier}: no row at all — the group would be unbounded")

    for country, carrier in sorted(expected_groups() & present):
        sub = ours[(ours.country == country) & (ours.carrier == carrier)].set_index("year")
        base = sub.loc[BASE_YEAR] if BASE_YEAR in sub.index else None
        if base is None or pd.isna(base["min"]) or pd.isna(base["max"]):
            errors.append(f"{country}/{carrier}: {BASE_YEAR} must be pinned (min and max set)")
        elif abs(base["min"] - base["max"]) > 1e-6:
            errors.append(
                f"{country}/{carrier} {BASE_YEAR}: min {base['min']:,.0f} != max "
                f"{base['max']:,.0f} — the base year must be a calibration, not an optimisation"
            )
        if CORRIDOR_YEAR not in sub.index or pd.isna(sub.loc[CORRIDOR_YEAR, "min"]):
            errors.append(
                f"{country}/{carrier}: no {CORRIDOR_YEAR} min — the near-term corridor needs a floor"
            )

    if rates is not None:
        have = set(zip(rates.node, rates.carrier))
        for country, carrier in sorted(expected_groups() - have):
            errors.append(
                f"{country}/{carrier}: missing from the build-rate table — no growth limit "
                "would be applied to this group"
            )
    return errors


def report(env: pd.DataFrame, rates: pd.DataFrame | None, multiplier: float) -> None:
    """Show the 2030 corridor and flag the collapses, which are expected."""
    if rates is None:
        return
    r = rates.set_index(["node", "carrier"]).record_annual_MW
    ours = env[env.country.isin(MODELLED) & env.carrier.isin(RES_CARRIERS)]
    print(f"{'node':7s} {'carrier':12s} {'2025 pin':>10s} {'2030 min':>10s} "
          f"{'rate MW/yr':>11s} {'5yr allow':>10s}  note")
    for country, carrier in sorted(expected_groups()):
        sub = ours[(ours.country == country) & (ours.carrier == carrier)].set_index("year")
        if sub.empty:
            continue
        pin = sub.loc[BASE_YEAR, "max"] if BASE_YEAR in sub.index else float("nan")
        floor = sub.loc[CORRIDOR_YEAR, "min"] if CORRIDOR_YEAR in sub.index else float("nan")
        rate = r.get((country, carrier), float("nan"))
        allow = multiplier * rate * (CORRIDOR_YEAR - BASE_YEAR)
        note = ""
        if pd.notna(floor) and pd.notna(allow) and floor - pin > allow:
            note = "target above max growth -> 2030 pinned at max build"
        print(f"{country:7s} {carrier:12s} {pin:10,.0f} {floor:10,.0f} {rate:11,.0f} "
              f"{allow:10,.0f}  {note}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("agg_file", type=Path)
    ap.add_argument("--rates", type=Path, default=Path("data/walloon/res_build_rates.csv"))
    ap.add_argument("--multiplier", type=float, default=2.0)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    env = load_envelope(args.agg_file)
    rates = pd.read_csv(args.rates, comment="#") if args.rates.exists() else None
    if rates is None:
        print(f"note: {args.rates} not found — skipping build-rate coverage checks")

    if not args.quiet:
        report(env, rates, args.multiplier)

    errors = check(env, rates)
    if errors:
        print(f"FAILED — {len(errors)} problem(s) in {args.agg_file.name}:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK — {args.agg_file.name} matches the documented design")
    return 0


if __name__ == "__main__":
    sys.exit(main())
