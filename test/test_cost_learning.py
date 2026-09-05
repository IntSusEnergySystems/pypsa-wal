# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""Cost trajectories must fall with learning, and reach the right technology.

The 2026-09-05 run review (F1) found every PV capital cost *rising* 2025->2050:
``custom_costs.csv`` carried one ``all``-horizon investment while
technology-data's FOM **percentage** keeps climbing — it is calibrated against
that catalogue's own falling CAPEX, so applied to a flat Walloon CAPEX it makes
the annuity grow. Utility PV came out at 81 EUR/MWh in 2050 against a
101.5 EUR/MWh Walloon price, which is why the model retired PV instead of
rebuilding it.

The fix keeps the Walloon literature figure as the **2025 anchor** and scales
2030/2040/2050 by technology-data's own rate for that technology. These tests
pin the three things that can silently undo it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from process_cost_data import COST_TABLE_RENAMES, prepare_costs  # noqa: E402

HORIZONS = (2025, 2030, 2040, 2050)
ARCHIVE = ROOT / "data" / "costs" / "archive" / "v0.14.0"
MASTER = ROOT / "config" / "input_parameters_for_models.csv"
CUSTOM_COSTS = ROOT / "data" / "walloon" / "custom_costs.csv"
HURDLES = ROOT / "data" / "walloon" / "discount_rates.csv"


@pytest.fixture(scope="module")
def technology_data() -> pd.DataFrame:
    """Investment per technology and horizon from the pinned archive."""
    cols = {}
    for year in HORIZONS:
        raw = pd.read_csv(ARCHIVE / f"costs_{year}.csv")
        raw = raw[raw.parameter == "investment"].set_index("technology")["value"]
        cols[year] = raw[~raw.index.duplicated()]
    return pd.DataFrame(cols)


@pytest.fixture(scope="module")
def walloon_config() -> dict:
    return yaml.safe_load((ROOT / "config" / "config.walloon.yaml").read_text())


@pytest.fixture(scope="module")
def processed(walloon_config) -> dict[int, pd.DataFrame]:
    """The processed cost table for each horizon, as the workflow builds it."""
    default = yaml.safe_load((ROOT / "config" / "config.default.yaml").read_text())
    costs_cfg = {**default["costs"], **walloon_config.get("costs", {})}
    max_hours = walloon_config.get("electricity", {}).get(
        "max_hours", default["electricity"]["max_hours"]
    )
    out = {}
    for year in HORIZONS:
        raw = pd.read_csv(
            ARCHIVE / f"costs_{year}.csv", index_col=["technology", "parameter"]
        )
        out[year] = prepare_costs(
            raw,
            dict(costs_cfg),
            max_hours,
            1.0,
            custom_costs_fn=str(CUSTOM_COSTS),
            planning_horizon=str(year),
            hurdle_rate_fn=str(HURDLES),
        )
    return out


def _active_investment_targets() -> dict[str, dict[int, float]]:
    df = pd.read_csv(MASTER)
    df = df[
        df["status"].eq("active")
        & df["parameter"].eq("investment")
        & df["pypsa_wal_target"].astype(str).str.startswith("cost:")
    ]
    out: dict[str, dict[int, float]] = {}
    for target, group in df.groupby("pypsa_wal_target"):
        tech = str(target).split(":", 1)[1].rsplit(":", 1)[0]
        values = {
            int(float(r.year)): float(r.value)
            for r in group.itertuples()
            if pd.notna(r.year) and pd.notna(r.value)
        }
        if values:
            out[tech] = values
    return out


def test_investment_trajectories_follow_technology_data(technology_data):
    """Every managed investment must move with the catalogue, not sit flat.

    Walloon overrides are allowed to set the *level* — that is the point of
    ``custom_costs.csv`` — but not to freeze the *shape*. A flat trajectory on
    a learning technology is what F1 was.
    """
    offenders = []
    for tech, values in _active_investment_targets().items():
        if tech not in technology_data.index:
            continue  # e.g. `nuclear retrofit`: no catalogue entry to follow
        years = sorted(set(values) & set(HORIZONS))
        assert years, f"{tech}: no value on any planning horizon"
        base = min(years)
        for year in years:
            want = technology_data.at[tech, year] / technology_data.at[tech, base]
            got = values[year] / values[base]
            if abs(got - want) > 0.01 * want:
                offenders.append(
                    f"{tech} @ {year}: master CSV x{got:.4f} vs "
                    f"technology-data x{want:.4f} (relative to {base})"
                )
    assert not offenders, "investment trajectory does not follow technology-data:\n" + "\n".join(
        offenders
    )


@pytest.mark.parametrize(
    "tech",
    [
        "solar-utility",
        "solar-rooftop",
        "solar-hsat",
        "onwind",
        "offwind",
        "battery storage",
        "battery inverter",
        "electrolysis",
        "biogas",
        "biogas upgrading",
    ],
)
def test_capital_cost_falls_between_2025_and_2050(processed, tech):
    """End-to-end: the number the LP actually sees has to come down."""
    series = pd.Series({year: processed[year].at[tech, "capital_cost"] for year in HORIZONS})
    assert series.is_monotonic_decreasing, f"{tech} capital_cost not falling:\n{series}"
    assert series[2050] < 0.98 * series[2025], (
        f"{tech}: 2050 capital_cost is {series[2050] / series[2025]:.3f} of 2025 — "
        "learning is not reaching the cost table"
    )


def test_cost_table_renames_agree():
    """``build_common_parameters`` names hurdle rows with the same map."""
    import build_common_parameters as bcp

    assert bcp.COST_TABLE_RENAMES == COST_TABLE_RENAMES


def test_hurdle_rate_reaches_the_renamed_technology(processed):
    """``solar-hsat``'s row must land, not leave it on the fill_values default.

    ``discount_rates.csv`` is generated with the post-rename name while
    ``prepare_costs`` applies hurdle rates *before* the rename, so without the
    inverse mapping tracking PV silently used 7 % instead of its 7.5 % TIMES
    hurdle — about 3 % too cheap.
    """
    hurdle = pd.read_csv(HURDLES).set_index("technology")["value"]
    wanted = float(hurdle.loc["solar-hsat"])
    for year in HORIZONS:
        assert processed[year].at["solar-hsat", "discount rate"] == pytest.approx(wanted)
    # and the fallback is genuinely different, so the test can fail
    default = yaml.safe_load((ROOT / "config" / "config.default.yaml").read_text())
    assert wanted != default["costs"]["fill_values"]["discount rate"]
