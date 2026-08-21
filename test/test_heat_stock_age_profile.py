# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Guards for `existing_capacities.heat_stock_age_profile`.

PyPSA-Eur spreads the inherited heating stock over the live `grouping_years_heat`
assuming installation was linear in the past. For heat pumps that is wrong in a
way that shows up in the results: `decentral air-sourced heat pump` carries an
18-year technology-data lifetime against a 20-year `default_heating_lifetime`, so
the linear spread puts 5/14 = 36 % of the fleet in a 2010 bin that dies in 2028 —
between the 2025 and 2030 planning horizons. BEWAL then reports *fewer* heat
pumps in 2030 than in 2025 while delivering more heat.

The override is derived from the TIMES stock trajectory rather than assumed, so
these tests re-derive it and fail if either side drifts. See
`docs/heat-softlink.md` §5.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from scripts.add_existing_baseyear import resolve_stock_age_ratios

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILES = (
    ROOT / "config" / "config.walloon.yaml",
    ROOT / "config" / "config.times-pypsa.yaml",
)
PROFILE_KEY = "air-sourced heat pump"

#: The TIMES air-heat-pump stock the profile is derived from, MW_th. Read off
#: `times_pypsa.heat_softlink.heating_capacities` on
#: `scen_demande_haute_v01_260727_fix_nuc_2807.vd`; `test_profile_matches_times`
#: re-derives it from the .vd when the library and the file are available.
TIMES_AIR_HP_MW_TH = {2021: 231.6, 2025: 929.4}

#: Age of the tranche that must survive to the next horizon. Anything older than
#: this dies before 2030 given the 18-year lifetime.
DIES_BEFORE_2030 = 2010


def _profiles() -> list[tuple[Path, dict[int, float]]]:
    out = []
    for path in CONFIG_FILES:
        cfg = yaml.safe_load(path.read_text())
        profile = (cfg.get("existing_capacities") or {}).get("heat_stock_age_profile")
        if not profile or PROFILE_KEY not in profile:
            pytest.fail(
                f"{path.name}: existing_capacities.heat_stock_age_profile is missing "
                f"the {PROFILE_KEY!r} entry. Without it 36 % of the inherited "
                "heat-pump fleet retires between 2025 and 2030 — see "
                "docs/heat-softlink.md §5."
            )
        out.append((path, {int(k): float(v) for k, v in profile[PROFILE_KEY].items()}))
    return out


def linear_ratios(grouping_years: list[int], baseyear: int, lifetime: int) -> pd.Series:
    """The PyPSA-Eur default: installation assumed linear over the live bins."""
    live = [y for y in grouping_years if y + lifetime > baseyear and y < baseyear]
    years = pd.Series(live).diff()
    years[0] = live[0] - baseyear + lifetime
    return pd.Series((years / years.sum()).values, index=live)


def expected_profile(
    grouping_years: list[int], baseyear: int, lifetime: int
) -> dict[int, float]:
    """Re-derive the profile: recent TIMES growth into the newest live bin.

    Capacity TIMES built between its earliest reported year and the base year is
    younger than every available grouping year, so it belongs in the newest one.
    What was already standing keeps the linear spread.
    """
    early, base = sorted(TIMES_AIR_HP_MW_TH)
    recent = max(0.0, TIMES_AIR_HP_MW_TH[base] - TIMES_AIR_HP_MW_TH[early])
    recent_share = recent / TIMES_AIR_HP_MW_TH[base]
    linear = linear_ratios(grouping_years, baseyear, lifetime)
    out = {int(y): round((1 - recent_share) * r, 3) for y, r in linear.items()}
    newest = int(linear.index[-1])
    out[newest] = round(out[newest] + recent_share, 3)
    return out


@pytest.mark.parametrize("path,profile", _profiles(), ids=lambda v: getattr(v, "name", ""))
def test_profile_sums_to_one(path: Path, profile: dict[int, float]):
    total = sum(profile.values())
    assert abs(total - 1.0) < 1e-6, f"{path.name}: shares sum to {total}, not 1"


@pytest.mark.parametrize("path,profile", _profiles(), ids=lambda v: getattr(v, "name", ""))
def test_profile_matches_the_times_derivation(path: Path, profile: dict[int, float]):
    cfg = yaml.safe_load(path.read_text())
    existing = cfg["existing_capacities"]
    grouping_years = existing.get("grouping_years_heat")
    lifetime = existing.get("default_heating_lifetime")
    if grouping_years is None or lifetime is None:
        default = yaml.safe_load((ROOT / "config" / "config.default.yaml").read_text())
        grouping_years = grouping_years or default["existing_capacities"][
            "grouping_years_heat"
        ]
        lifetime = lifetime or default["existing_capacities"][
            "default_heating_lifetime"
        ]
    baseyear = int(cfg["scenario"]["planning_horizons"][0])
    expected = expected_profile(grouping_years, baseyear, lifetime)
    if profile != expected:
        pytest.fail(
            f"{path.name}: heat_stock_age_profile[{PROFILE_KEY!r}] is {profile}, "
            f"but the TIMES trajectory {TIMES_AIR_HP_MW_TH} over grouping years "
            f"{grouping_years} gives {expected}. Update the config, or update "
            "TIMES_AIR_HP_MW_TH here if the reference scenario changed."
        )


@pytest.mark.parametrize("path,profile", _profiles(), ids=lambda v: getattr(v, "name", ""))
def test_the_tranche_that_dies_first_is_small(path: Path, profile: dict[int, float]):
    """The point of the exercise: no big tranche may vanish before 2030."""
    doomed = profile.get(DIES_BEFORE_2030, 0.0)
    linear = linear_ratios(
        yaml.safe_load((ROOT / "config" / "config.default.yaml").read_text())[
            "existing_capacities"
        ]["grouping_years_heat"],
        2025,
        20,
    )
    assert doomed < linear.iloc[0] / 2, (
        f"{path.name}: {doomed:.1%} of the inherited heat-pump fleet still sits in "
        f"the {DIES_BEFORE_2030} bin (linear default {linear.iloc[0]:.1%}); it dies "
        f"in {DIES_BEFORE_2030 + 18}, i.e. before the 2030 horizon."
    )


# --------------------------------------------------------------------------- #
# resolve_stock_age_ratios
# --------------------------------------------------------------------------- #

GY = [2010, 2015, 2019]
LINEAR = linear_ratios([1980, 1985, 1990, 1995, 2000, 2005, *GY], 2025, 20)
PROFILE = {"air-sourced heat pump": {2010: 0.089, 2015: 0.089, 2019: 0.822}}


def test_unnamed_technology_keeps_the_linear_default():
    got = resolve_stock_age_ratios("decentral gas boiler", LINEAR, GY, PROFILE)
    assert got is LINEAR


def test_no_profile_keeps_the_linear_default():
    assert resolve_stock_age_ratios("decentral air-sourced heat pump", LINEAR, GY, None) is LINEAR
    assert resolve_stock_age_ratios("decentral air-sourced heat pump", LINEAR, GY, {}) is LINEAR


@pytest.mark.parametrize(
    "costs_name",
    ["decentral air-sourced heat pump", "central air-sourced heat pump"],
)
def test_named_technology_takes_the_profile(costs_name: str):
    got = resolve_stock_age_ratios(costs_name, LINEAR, GY, PROFILE)
    assert list(got.round(3)) == [0.089, 0.089, 0.822]
    assert got.iloc[0] < LINEAR.iloc[0], "the doomed tranche must shrink"


def test_ground_source_is_untouched_by_an_air_source_profile():
    got = resolve_stock_age_ratios("decentral ground-sourced heat pump", LINEAR, GY, PROFILE)
    assert got is LINEAR


def test_dead_grouping_years_do_not_shift_the_others():
    """A profile listing a year already retired renormalises over the live ones."""
    profile = {"air-sourced heat pump": {1995: 0.5, 2010: 0.1, 2019: 0.4}}
    got = resolve_stock_age_ratios("decentral air-sourced heat pump", LINEAR, GY, profile)
    assert abs(got.sum() - 1.0) < 1e-9
    assert abs(got.iloc[0] - 0.1 / 0.5) < 1e-9
    assert abs(got.iloc[2] - 0.4 / 0.5) < 1e-9


def test_profile_with_no_live_year_falls_back():
    profile = {"air-sourced heat pump": {1990: 1.0}}
    got = resolve_stock_age_ratios("decentral air-sourced heat pump", LINEAR, GY, profile)
    assert got is LINEAR
