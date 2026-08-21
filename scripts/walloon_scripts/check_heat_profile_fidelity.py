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
HORIZONS = [2025, 2030, 2040, 2050]
NODE = "BEWAL"


def roots() -> tuple[Path, Path]:
    if PHASE == "live":
        base = Path("results/walloon") / SCENARIO
    else:
        base = Path("results/_heat_softlink_comparison") / PHASE
    return base / "networks", base / "heating_profiles"


def main() -> None:
    networks, profiles_dir = roots()
    targets_dir = Path("resources/walloon") / SCENARIO
    rows = []
    for year in HORIZONS:
        net_path = networks / f"base_s_adm___{year}.nc"
        prof_path = profiles_dir / f"base_s_adm___{year}.csv"
        if not net_path.exists() or not prof_path.exists():
            print(f"{year}: missing ({net_path.exists()=}, {prof_path.exists()=})")
            continue
        n = pypsa.Network(net_path)
        w = n.snapshot_weightings.generators
        buses = decentral_heat_buses(n, NODE)
        target = pd.read_csv(targets_dir / f"heating_targets_{year}.csv")
        target = target[target["constrained"]].set_index("group")
        profiles = pd.read_csv(prof_path, header=[0, 1], index_col=0)
        profiles.index = n.snapshots

        print(f"\n=== {year} ===")
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
                        "bus": bus.replace(f"{NODE} ", ""),
                        "pinned TWh": float((pinned * w).sum()) / 1e6,
                        "realised TWh": float((realised * w).sum()) / 1e6,
                        "energy gap TWh": energy_gap,
                        "peak |gap| MW": peak_gap,
                        "peak gap % of profile peak": 100 * peak_gap / scale,
                    }
                )
        sub = pd.DataFrame([r for r in rows if r["year"] == year])
        pd.set_option("display.width", 220)
        print(sub.drop(columns="year").to_string(index=False, float_format="%.5f"))
        worst = sub.loc[sub["energy gap TWh"].abs().idxmax()]
        print(
            f"  worst annual gap: {worst['group']} on {worst['bus']}, "
            f"{worst['energy gap TWh']:+.5f} TWh"
        )

    out = pd.DataFrame(rows)
    if len(out):
        path = Path("results/_heat_softlink_comparison") / f"profile_fidelity_{PHASE}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False)
        print(f"\nWritten to {path}")
        print(
            f"\nTotal |annual gap| over every (year, group, bus): "
            f"{out['energy gap TWh'].abs().sum():.5f} TWh"
        )


if __name__ == "__main__":
    main()
