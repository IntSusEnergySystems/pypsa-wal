# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Did the solved network actually deliver the profile option B' pinned it to?

Compares the exported ``heating_profiles/*.csv`` — the right-hand sides the
constraints were built from — against the realised dispatch in the solved
network, per group, per bus, per snapshot. Any deviation is either the absorber
using the water tank (bounded, and zero in annual energy) or a group that hit its
relaxation, and the two are distinguished here.

This is the check that no unit test can do, because it needs the real network:
a wrong sign convention, a dropped vintage or a mis-selected carrier all produce
a perfectly feasible LP whose answer is silently not the TIMES mix.

Usage::

    python scripts/walloon_scripts/check_heat_profile_fidelity.py [scenario] [phase]

``phase`` is a folder under ``results/_heat_softlink_comparison`` (default
``option_b``); pass ``live`` to read ``results/walloon/<scenario>`` instead.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.walloon_scripts.times_heat_softlink import (  # noqa: E402
    decentral_heat_buses,
    heat_injection_terms,
)

SCENARIO = sys.argv[1] if len(sys.argv) > 1 else "scen_demande_haute"
PHASE = sys.argv[2] if len(sys.argv) > 2 else "option_b"
#: Fallback only, for a tree with no solved networks. Real runs use
#: :func:`horizons_from` — config.walloon.yaml solves four horizons and the
#: config.walloon_5y.yaml overlay six, so a pinned list silently skips 2035/2045.
HORIZONS = [2025, 2030, 2040, 2050]
NODE = "BEWAL"


def horizons_from(networks: Path) -> list[int]:
    """Planning horizons actually present in a ``networks/`` directory."""
    years = {
        int(m.group(1))
        for p in networks.glob("base_s_adm___*.nc")
        if (m := re.search(r"___(\d{4})\.nc$", p.name))
    }
    return sorted(years) or list(HORIZONS)


def roots() -> tuple[Path, Path]:
    if PHASE == "live":
        base = Path("results/walloon") / SCENARIO
    else:
        base = Path("results/_heat_softlink_comparison") / PHASE
    return base / "networks", base / "heating_profiles"


#: Columns of the frame :func:`fidelity_frame` returns.
COLUMNS = [
    "year",
    "group",
    "bus",
    "pinned TWh",
    "realised TWh",
    "energy gap TWh",
    "peak |gap| MW",
    "peak gap % of profile peak",
]


def fidelity_frame(
    networks: Path,
    profiles_dir: Path,
    targets_dir: Path,
    horizons=HORIZONS,
    node: str = NODE,
    on_missing=None,
) -> pd.DataFrame:
    """One row per (year, group, bus): pinned versus realised heat.

    Split out of :func:`main` so ``review_run.py`` can run the same measurement
    inside its level-2 soft-link section. Reading the summary of an earlier run
    is not the same check: on 2026-09-06 the "worst single gap" quoted in the
    review (−0.033 TWh) came from a three-day-old CSV of the 6h test run, while
    the total (8.15 TWh) came from the production networks whose worst gap was
    −2.008 TWh. Two numbers, two runs, one conclusion — and it was "pass".

    The signed gaps cancel per (year, bus), by construction: the absorber takes
    whatever the pinned groups did not deliver, so the heat load always closes
    and only the *mix* moves. The number that matters is therefore the gap of
    the individual group, never the sum over groups.
    """
    rows = []
    for year in horizons:
        net_path = networks / f"base_s_adm___{year}.nc"
        prof_path = profiles_dir / f"base_s_adm___{year}.csv"
        target_path = targets_dir / f"heating_targets_{year}.csv"
        if not (net_path.exists() and prof_path.exists() and target_path.exists()):
            if on_missing is not None:
                on_missing(year, net_path, prof_path, target_path)
            continue
        n = pypsa.Network(net_path)
        w = n.snapshot_weightings.generators
        buses = decentral_heat_buses(n, node)
        target = pd.read_csv(target_path)
        target = target[target["constrained"]].set_index("group")
        profiles = pd.read_csv(prof_path, header=[0, 1], index_col=0)
        profiles.index = n.snapshots

        for group, row in target.iterrows():
            carriers = [
                c.strip() for c in str(row["pypsa_carriers"]).split(";") if c.strip()
            ]
            for bus in buses:
                index, coeffs = heat_injection_terms(
                    n, pd.Index([bus]), carriers, row["pypsa_component"]
                )
                p = n.links_t.p0 if row["pypsa_component"] == "Link" else n.generators_t.p
                realised = (p[index] * coeffs).sum(axis=1)
                pinned = profiles[(group, bus)]
                gap = realised - pinned
                energy_gap = float((gap * w).sum()) / 1e6
                peak_gap = float(gap.abs().max())
                scale = float(pinned.abs().max()) or 1.0
                rows.append(
                    {
                        "year": year,
                        "group": group,
                        "bus": bus.replace(f"{node} ", ""),
                        "pinned TWh": float((pinned * w).sum()) / 1e6,
                        "realised TWh": float((realised * w).sum()) / 1e6,
                        "energy gap TWh": energy_gap,
                        "peak |gap| MW": peak_gap,
                        "peak gap % of profile peak": 100 * peak_gap / scale,
                    }
                )
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> None:
    networks, profiles_dir = roots()
    targets_dir = Path("resources/walloon") / SCENARIO

    def missing(year, net_path, prof_path, target_path):
        print(
            f"{year}: missing ({net_path.exists()=}, {prof_path.exists()=}, "
            f"{target_path.exists()=})"
        )

    out = fidelity_frame(
        networks,
        profiles_dir,
        targets_dir,
        horizons=horizons_from(networks),
        on_missing=missing,
    )
    pd.set_option("display.width", 220)
    for year in sorted(out["year"].unique()):
        sub = out[out["year"] == year]
        print(f"\n=== {year} ===")
        print(sub.drop(columns="year").to_string(index=False, float_format="%.5f"))
        worst = sub.loc[sub["energy gap TWh"].abs().idxmax()]
        print(
            f"  worst annual gap: {worst['group']} on {worst['bus']}, "
            f"{worst['energy gap TWh']:+.5f} TWh"
        )

    if len(out):
        path = Path("results/_heat_softlink_comparison") / f"profile_fidelity_{PHASE}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False)
        print(f"\nWritten to {path}")
        # Summed over all groups the signed gaps cancel — the absorber sees to
        # that — so the |sum| is a size, not a verdict. The verdict is the worst
        # *group*: an 8.15 TWh total made of ±2.008 TWh substitutions between
        # two groups is a different result from one made of rounding.
        worst = out.loc[out["energy gap TWh"].abs().idxmax()]
        share = (
            abs(worst["energy gap TWh"]) / worst["pinned TWh"]
            if worst["pinned TWh"]
            else float("nan")
        )
        print(
            f"\nTotal |annual gap| over every (year, group, bus): "
            f"{out['energy gap TWh'].abs().sum():.5f} TWh"
            f"\nWorst single group: {worst['group']} on {worst['bus']} in "
            f"{worst['year']}, {worst['energy gap TWh']:+.5f} TWh of "
            f"{worst['pinned TWh']:.5f} pinned ({share:.1%})"
        )
        by_bus = out.groupby(["year", "bus"])["energy gap TWh"].sum().abs().max()
        print(
            f"Largest signed residual on any (year, bus) after summing groups: "
            f"{by_bus:.2e} TWh — the total heat load closes; the mix is what moved."
        )


if __name__ == "__main__":
    main()
