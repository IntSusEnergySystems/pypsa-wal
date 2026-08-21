# SPDX-License-Identifier: MIT
"""
Derive mutually consistent EV charging weights from the Elia AdeqFlex tables.

The three charging profiles are weighted at three levels, and the levels must not
be mixed:

1. **Flexibility mode** — natural (Elia ``V0``) / local (``V1H+V2H``) / market
   (``V1M+V2M``). All three come from one row of
   ``ev_operation_mode_shares.csv``, so they are consistent *by construction*
   only if they are read from the **same (scenario, year)** cell. pypsa-wal splits
   them across two config keys: ``sector.bev_dsm_availability`` takes the market
   share, and ``sector.local_bev_dsm`` takes natural vs local **renormalised over
   the two**, because it is applied to what is left after the market slice.
2. **Inside the natural profile** — home / work / public, from
   ``ev_v0_location_shares.csv``. Elia's published ``natural`` column is exactly
   this weighted sum (verified to ≤ 0.0006 per hour), so any horizon can be built
   from the shares instead of snapping to the 2026 or 2036 vintage.
3. **Inside the local profile** — work vs home, and sunny/cloudy × with/without
   PV among the home variants. **Elia publishes no weights for this level.** The
   work/home split is taken from the V0 location split restricted to home+work
   (Elia assumes no flexibility from public charging), which is the only
   Elia-grounded proxy available. The PV and sky splits need a model-side input:
   see ``docs/ev-charging-softlink.md`` §4.

Horizons past Elia's last year (2036) are **held, not extrapolated**: a
behavioural adoption curve extended 14 years beyond its source is worse than the
last observed point. Extra flexibility for a high-flex case comes from Elia's own
**scenario** axis instead — its "High Flex" sensitivity reaches a 0.28 market
share at 2036, which is where the pypsa-wal 2050 value should come from.

Usage::

    python scripts/walloon_scripts/build_ev_charging_weights.py
    python scripts/walloon_scripts/build_ev_charging_weights.py \
        --scenario "Current commitments - High Flex" --horizons 2025 2030 2040 2050
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml

DATA = Path("data/walloon/elia_adeqflex2025")
DEFAULT_SCENARIO = "Current commitments"
DEFAULT_HORIZONS = (2025, 2030, 2040, 2050)

#: Elia stops at 2036. Anything later holds that year rather than extrapolating.
LAST_ELIA_YEAR = 2036

NATURAL_MODES = ["V0"]
LOCAL_MODES = ["V1H", "V2H"]
MARKET_MODES = ["V1M", "V2M"]

#: The four home local curves in the profile CSV, and the work curve.
HOME_CURVES = ["sunny_PV", "sunny_noPV", "cloudy_PV", "cloudy_noPV"]
WORK_CURVE = "work"


def elia_year(horizon: int) -> int:
    return min(int(horizon), LAST_ELIA_YEAR)


def mode_shares(scenario: str) -> pd.DataFrame:
    """Natural / local / market share of the fleet, per Elia year."""
    m = pd.read_csv(DATA / "ev_operation_mode_shares.csv")
    sub = m[m["scenario"] == scenario]
    if sub.empty:
        raise SystemExit(
            f"unknown scenario {scenario!r}; have {sorted(m['scenario'].unique())}"
        )
    piv = sub.pivot(index="year", columns="mode", values="share")
    out = pd.DataFrame(
        {
            "natural": piv[NATURAL_MODES].sum(axis=1),
            "local": piv[LOCAL_MODES].sum(axis=1),
            "market": piv[MARKET_MODES].sum(axis=1),
        }
    )
    # Elia rounds each mode to 2 decimals, so the three do not sum to exactly 1.
    return out.div(out.sum(axis=1), axis=0)


def location_shares() -> pd.DataFrame:
    return pd.read_csv(DATA / "ev_v0_location_shares.csv").pivot(
        index="year", columns="location", values="share"
    )


def weights(scenario: str, horizons: tuple[int, ...]) -> dict:
    """The two config blocks, consistent by construction."""
    modes = mode_shares(scenario)
    loc = location_shares()

    availability, local_bev_dsm, audit = {}, {}, []
    for h in horizons:
        y = elia_year(h)
        m = modes.loc[y]
        # Level 1: the market slice is taken off the top; natural vs local is
        # renormalised over the remainder, because that is where it is applied.
        rest = m["natural"] + m["local"]
        natural = float(m["natural"] / rest)
        local = 1.0 - natural
        # Level 3: work vs home from the V0 split, public excluded (Elia assumes
        # no flexibility from public charging).
        l = loc.loc[y]
        work_of_local = float(l["work"] / (l["home"] + l["work"]))
        home_of_local = 1.0 - work_of_local
        # Level 3b: no Elia weights for sky x PV -- equal until a model-side
        # input replaces them.
        per_home = local * home_of_local / len(HOME_CURVES)

        availability[h] = round(float(m["market"]), 3)
        block = {"natural": round(natural, 3)}
        block.update({c: round(per_home, 4) for c in HOME_CURVES})
        block[WORK_CURVE] = round(local * work_of_local, 4)
        # Absorb the rounding residual into the largest entry so the assertion in
        # build_natural_charging_shape cannot trip.
        residual = 1.0 - sum(block.values())
        biggest = max(block, key=block.get)
        block[biggest] = round(block[biggest] + residual, 4)
        local_bev_dsm[h] = block

        audit.append(
            {
                "horizon": h,
                "elia_year": y,
                "held": y != h,
                "market": availability[h],
                "natural_abs": round(natural * (1 - m["market"]), 3),
                "local_abs": round(local * (1 - m["market"]), 3),
                "elia_natural_abs": round(float(m["natural"]), 3),
                "elia_local_abs": round(float(m["local"]), 3),
                "work_of_local": round(work_of_local, 3),
            }
        )
    return {
        "bev_dsm_availability": availability,
        "local_bev_dsm": local_bev_dsm,
        "audit": pd.DataFrame(audit).set_index("horizon"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO)
    parser.add_argument("--horizons", type=int, nargs="+", default=list(DEFAULT_HORIZONS))
    args = parser.parse_args()

    w = weights(args.scenario, tuple(args.horizons))
    pd.set_option("display.width", 200)
    print(f"# Elia scenario: {args.scenario}\n")
    print("Consistency audit (abs = share of the whole fleet):")
    print(w["audit"].to_string())
    print("\n# --- paste into sector: ---")
    print(yaml.safe_dump({"bev_dsm_availability": w["bev_dsm_availability"]},
                         default_flow_style=False, sort_keys=True))
    print(yaml.safe_dump({"local_bev_dsm": w["local_bev_dsm"]},
                         default_flow_style=False, sort_keys=True))


if __name__ == "__main__":
    main()
