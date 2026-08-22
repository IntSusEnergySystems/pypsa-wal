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

By default, horizons past Elia's last year (2036) are **held, not
extrapolated**: a behavioural adoption curve extended 14 years beyond its source
is worse than the last observed point, and extra flexibility normally comes from
Elia's own **scenario** axis instead.

``--extrapolate`` opts out of that, for a deliberately ambitious case that has to
say something about 2040 and 2050 rather than freeze 2036. It continues the two
adoption fractions Elia does trend — the steerable ("smart") share ``1 - V0`` and
the market share *of* steerable charging ``(V1M+V2M) / (1 - V0)`` — as **saturating
logistics anchored on Elia's own last observed value**:

* linear in log-odds against a ceiling, so growth decelerates and the share can
  never pass the ceiling or turn negative — which straight-line extrapolation of
  either fraction does before 2050;
* the slope is read from Elia's own last ``--fit-window`` years (2030 → 2036 by
  default), not fitted through the whole series, so the extrapolated path passes
  **exactly** through the 2036 value and is continuous with the data;
* the smart ceiling is **derived** from the public-charging share at Elia's last
  year — Elia assumes no flexibility from public charging, so public-charged
  energy is unmanaged by construction and ``1 - public`` bounds the steerable
  share. The market ceiling is the one number nothing in the data pins; it is an
  explicit assumption, and ``--market-ceiling`` prints its own sensitivity band.

The **location** split (level 2/3) is never extrapolated, even with
``--extrapolate``. It is driven by the company-car → private-ownership shift,
which has run its course by 2036 (home charging 0.53 → 0.70), so there is no
mechanism left to continue; holding it is also what keeps the public share — and
therefore the smart ceiling — at one auditable value.

Usage::

    python scripts/walloon_scripts/build_ev_charging_weights.py
    python scripts/walloon_scripts/build_ev_charging_weights.py \
        --scenario "Current commitments - High Flex" --horizons 2025 2030 2040 2050
    python scripts/walloon_scripts/build_ev_charging_weights.py \
        --scenario "Current commitments - High Flex" --extrapolate
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd
import yaml

DATA = Path("data/walloon/elia_adeqflex2025")
DEFAULT_SCENARIO = "Current commitments"
#: Every horizon config.default.yaml lists, so a generated block cannot let a
#: PyPSA-Eur default leak into an unlisted year.
DEFAULT_HORIZONS = (2020, 2025, 2030, 2035, 2040, 2045, 2050)

#: Elia covers 2023-2036. Anything outside is clamped to the nearest end rather
#: than extrapolated: a behavioural adoption curve extended past its source is
#: worse than its nearest observed point, and clamping is auditable.
FIRST_ELIA_YEAR = 2023
LAST_ELIA_YEAR = 2036

#: --extrapolate only. Years of Elia data the log-odds slope is read from. Six
#: years (2030 -> 2036) is long enough that the 2-decimal rounding of each mode
#: share cannot dominate the slope, and short enough to describe the mature part
#: of the curve rather than the take-off.
DEFAULT_FIT_WINDOW = 6

#: --extrapolate only. Ceiling on the market (V1M+V2M) share *of* steerable
#: charging. **Elia pins nothing here**: this is the one invented number in the
#: extrapolation, and it is stated rather than derived. 0.70 says that at full
#: maturity seven tenths of steerable charging is explicitly market-steered
#: (aggregator / dynamic contract) and the remaining three tenths stays locally
#: optimised -- PV self-consumption and static-tariff timers, which are V1H by
#: Elia's definition however cheap wholesale power gets. Elia's own High Flex
#: reaches 0.337 by 2036 and is still rising, so the ceiling binds only after the
#: data ends. The audit prints a 0.60/0.70/0.80 band so its weight is visible.
DEFAULT_MARKET_CEILING = 0.70

NATURAL_MODES = ["V0"]
LOCAL_MODES = ["V1H", "V2H"]
MARKET_MODES = ["V1M", "V2M"]

#: The four home local curves in the profile CSV, and the work curve.
HOME_CURVES = ["sunny_PV", "sunny_noPV", "cloudy_PV", "cloudy_noPV"]
WORK_CURVE = "work"


def clamp(horizon: int, index) -> int:
    """Nearest year the table actually has.

    The two tables do not span the same years -- mode shares start at 2023,
    location shares at 2025 -- so each lookup is clamped to its own range rather
    than to one global window.
    """
    years = sorted(int(y) for y in index)
    return min(max(int(horizon), years[0]), years[-1])


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


def smart_ceiling_from_data(loc: pd.DataFrame) -> float:
    """``1 - public`` at Elia's last location year.

    Elia states that no flexibility is assumed from public charging, so
    public-charged energy is unmanaged (``V0``) whatever the tariff or the
    aggregator does, and its share is a floor on ``V0`` -- equivalently a ceiling
    on the steerable share. Read from the data rather than hard-coded so it moves
    with the table.
    """
    return 1.0 - float(loc.loc[loc.index.max(), "public"])


def _logit(x: float, ceiling: float) -> float:
    return math.log(x / (ceiling - x))


def _expit(z: float, ceiling: float) -> float:
    return ceiling / (1.0 + math.exp(-z))


def _continue(
    series: pd.Series, ceiling: float, window: int, years
) -> tuple[pd.Series, float]:
    """Saturating continuation of one adoption fraction past its last year.

    Linear in log-odds against ``ceiling``, anchored so the curve passes exactly
    through the last observed value: ``x(last) == series[last]`` by construction,
    and the slope is the one Elia's own last ``window`` years imply. Growth
    therefore decelerates towards the ceiling instead of crossing it, which is
    what a straight line in share space does within the horizon of this study.
    """
    last = int(series.index.max())
    anchor = last - window
    if anchor not in series.index:
        raise SystemExit(
            f"fit window of {window} y needs {anchor}, which the Elia table does "
            f"not have (has {int(series.index.min())}-{last})"
        )
    first, latest = float(series.loc[anchor]), float(series.loc[last])
    if not 0.0 < first < ceiling or not 0.0 < latest < ceiling:
        raise SystemExit(
            f"cannot continue in log-odds: {first:.3f} ({anchor}) and "
            f"{latest:.3f} ({last}) must both lie strictly inside "
            f"(0, {ceiling:.3f}). Raise the ceiling or shorten the window."
        )
    z_last = _logit(latest, ceiling)
    slope = (z_last - _logit(first, ceiling)) / window
    if slope <= 0:
        raise SystemExit(
            f"the {anchor}-{last} trend does not rise ({first:.3f} -> "
            f"{latest:.3f}); extrapolating it is not meaningful. Use the "
            "default hold instead of --extrapolate."
        )
    return pd.Series(
        {y: _expit(z_last + slope * (y - last), ceiling) for y in years},
        dtype=float,
    ), slope


def extrapolate_modes(
    modes: pd.DataFrame,
    loc: pd.DataFrame,
    horizons: tuple[int, ...],
    market_ceiling: float,
    smart_ceiling: float | None = None,
    window: int = DEFAULT_FIT_WINDOW,
) -> tuple[pd.DataFrame, dict]:
    """Append rows past Elia's last year, saturating rather than straight-lining.

    The two fractions continued are the ones that are genuinely adoption curves:

    * ``smart = 1 - natural`` -- the steerable share of the fleet, against the
      ``1 - public`` ceiling of ``smart_ceiling_from_data``;
    * ``market_of_smart = market / smart`` -- how much of the steerable share is
      explicitly market-steered rather than locally optimised, against
      ``market_ceiling``, the one stated assumption.

    ``natural``, ``local`` and ``market`` are then rebuilt from the two, so they
    sum to 1 by construction exactly as the Elia rows do.
    """
    last = int(modes.index.max())
    new_years = sorted(y for y in horizons if y > last)
    if not new_years:
        return modes, {}
    if smart_ceiling is None:
        smart_ceiling = smart_ceiling_from_data(loc)

    smart_obs = 1.0 - modes["natural"]
    smart, smart_slope = _continue(smart_obs, smart_ceiling, window, new_years)
    mos, mos_slope = _continue(
        modes["market"] / smart_obs, market_ceiling, window, new_years
    )

    extra = pd.DataFrame(
        {
            "natural": 1.0 - smart,
            "local": smart * (1.0 - mos),
            "market": smart * mos,
        }
    )
    info = {
        "last_elia_year": last,
        "window": window,
        "smart_ceiling": smart_ceiling,
        "market_ceiling": market_ceiling,
        "smart_slope": smart_slope,
        "market_slope": mos_slope,
        "years": new_years,
    }
    return pd.concat([modes, extra]).sort_index(), info


def weights(
    scenario: str,
    horizons: tuple[int, ...],
    extrapolate: bool = False,
    market_ceiling: float = DEFAULT_MARKET_CEILING,
    smart_ceiling: float | None = None,
    window: int = DEFAULT_FIT_WINDOW,
) -> dict:
    """The two config blocks, consistent by construction."""
    modes = mode_shares(scenario)
    loc = location_shares()

    elia_years = set(modes.index)
    info = {}
    if extrapolate:
        modes, info = extrapolate_modes(
            modes, loc, horizons, market_ceiling, smart_ceiling, window
        )

    availability, local_bev_dsm, audit = {}, {}, []
    for h in horizons:
        y = clamp(h, modes.index)
        m = modes.loc[y]
        # Level 1: the market slice is taken off the top; natural vs local is
        # renormalised over the remainder, because that is where it is applied.
        rest = m["natural"] + m["local"]
        natural = float(m["natural"] / rest)
        local = 1.0 - natural
        # Level 3: work vs home from the V0 split, public excluded (Elia assumes
        # no flexibility from public charging).
        l = loc.loc[clamp(h, loc.index)]
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
                "source_year": y,
                "basis": (
                    "elia"
                    if y in elia_years and y == h
                    else "held"
                    if y in elia_years
                    else "extrapolated"
                ),
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
        "info": info,
    }


#: Printed next to the chosen market ceiling so the reader can see how much of
#: the 2050 answer that one assumption carries.
SENSITIVITY_CEILINGS = (0.60, 0.70, 0.80)


def market_ceiling_sensitivity(
    scenario: str, horizons: tuple[int, ...], window: int, smart_ceiling: float | None
) -> pd.DataFrame:
    """`bev_dsm_availability` per horizon for each candidate market ceiling."""
    rows = {}
    for ceiling in SENSITIVITY_CEILINGS:
        w = weights(scenario, horizons, True, ceiling, smart_ceiling, window)
        rows[f"market_ceiling={ceiling:.2f}"] = w["bev_dsm_availability"]
    return pd.DataFrame(rows).T


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO)
    parser.add_argument("--horizons", type=int, nargs="+", default=list(DEFAULT_HORIZONS))
    parser.add_argument(
        "--extrapolate",
        action="store_true",
        help="continue the adoption fractions past Elia's last year as saturating "
        "logistics instead of holding it. Off by default -- holding is the rule; "
        "see the module docstring for the three conditions this satisfies.",
    )
    parser.add_argument(
        "--market-ceiling",
        type=float,
        default=DEFAULT_MARKET_CEILING,
        help="--extrapolate only: long-run ceiling on the market share OF steerable "
        f"charging. Nothing in the Elia data pins it (default {DEFAULT_MARKET_CEILING}).",
    )
    parser.add_argument(
        "--smart-ceiling",
        type=float,
        default=None,
        help="--extrapolate only: long-run ceiling on the steerable share of the "
        "fleet. Defaults to 1 - public charging share at Elia's last year.",
    )
    parser.add_argument(
        "--fit-window",
        type=int,
        default=DEFAULT_FIT_WINDOW,
        help="--extrapolate only: years of Elia data the log-odds slope is read "
        f"from (default {DEFAULT_FIT_WINDOW}, i.e. 2030-2036).",
    )
    args = parser.parse_args()

    horizons = tuple(args.horizons)
    w = weights(
        args.scenario,
        horizons,
        args.extrapolate,
        args.market_ceiling,
        args.smart_ceiling,
        args.fit_window,
    )
    pd.set_option("display.width", 200)
    print(f"# Elia scenario: {args.scenario}")
    info = w["info"]
    if info:
        print(
            f"# Extrapolated past {info['last_elia_year']}: saturating logistic, "
            f"log-odds slope from {info['last_elia_year'] - info['window']}-"
            f"{info['last_elia_year']}, anchored on {info['last_elia_year']}.\n"
            f"#   steerable share  ceiling {info['smart_ceiling']:.3f} "
            f"(= 1 - public, from the data), log-odds slope {info['smart_slope']:.3f}/y\n"
            f"#   market of that   ceiling {info['market_ceiling']:.3f} "
            f"(ASSUMPTION), log-odds slope {info['market_slope']:.3f}/y\n"
            f"# The location split is held at Elia's last year, not extrapolated."
        )
    elif args.extrapolate:
        print(f"# --extrapolate had nothing to do: no horizon in {horizons} is past "
              f"Elia's last year.")
    else:
        print("# Horizons past Elia's last year hold it (no --extrapolate).")
    print("\nConsistency audit (abs = share of the whole fleet):")
    print(w["audit"].to_string())
    if info:
        print(
            "\nHow much the market ceiling carries (bev_dsm_availability per horizon):"
        )
        print(
            market_ceiling_sensitivity(
                args.scenario, horizons, args.fit_window, args.smart_ceiling
            ).to_string()
        )
    print("\n# --- paste into sector: ---")
    print(yaml.safe_dump({"bev_dsm_availability": w["bev_dsm_availability"]},
                         default_flow_style=False, sort_keys=True))
    print(yaml.safe_dump({"local_bev_dsm": w["local_bev_dsm"]},
                         default_flow_style=False, sort_keys=True))


if __name__ == "__main__":
    main()
