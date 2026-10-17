# SPDX-License-Identifier: MIT
"""scen_central_flat_res_costs: renewable costs frozen at their 2025 value, nothing else.

The scenario answers one question - what if renewable technologies (biogas included)
stopped getting cheaper after 2025? - so it must change the cost of exactly the
technologies of ``build_flat_res_costs.FLAT_TECHNOLOGIES`` and not one other row, in
every horizon, and 2025 itself must be the central's. Costs reach a solve through two
channels (per-horizon rows of custom_costs.csv, technology-data's own per-year table);
the second is what a hand edit of the CSV forgets, so the checks run through
``prepare_costs``, the function the workflow calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "walloon_scripts"))

import build_flat_res_costs as flat  # noqa: E402
from process_cost_data import prepare_costs  # noqa: E402

HORIZONS = (2025, 2030, 2040, 2050)
ARCHIVE = ROOT / "data" / "costs" / "archive" / "v0.14.0"
HURDLES = ROOT / "data" / "walloon" / "discount_rates.csv"
COLUMNS = ["investment", "FOM", "VOM", "fuel", "capital_cost", "marginal_cost"]
SCENARIOS = ROOT / "config" / "scenarios.walloon.yaml"


@pytest.fixture(scope="module")
def tables():
    walloon = yaml.safe_load((ROOT / "config" / "config.walloon.yaml").read_text())
    default = yaml.safe_load((ROOT / "config" / "config.default.yaml").read_text())
    cfg = {**default["costs"], **walloon.get("costs", {})}
    max_hours = walloon.get("electricity", {}).get("max_hours", default["electricity"]["max_hours"])

    def build(custom, year):
        raw = pd.read_csv(ARCHIVE / f"costs_{year}.csv", index_col=["technology", "parameter"])
        return prepare_costs(raw, dict(cfg), max_hours, 1.0, custom_costs_fn=str(custom),
                             planning_horizon=str(year), hurdle_rate_fn=str(HURDLES))

    return {
        "central": {y: build(flat.BASE, y) for y in HORIZONS},
        "flat": {y: build(flat.OUT, y) for y in HORIZONS},
    }


def test_committed_file_is_the_generator_output():
    assert flat.OUT.read_text(encoding="utf-8") == flat.render(), (
        "custom_costs_scen_central_flat_res_costs.csv is stale: run "
        "python scripts/walloon_scripts/build_flat_res_costs.py"
    )


def test_2025_is_the_central_2025(tables):
    pd.testing.assert_frame_equal(tables["flat"][2025], tables["central"][2025])


@pytest.mark.parametrize("year", HORIZONS[1:])
def test_only_the_listed_technologies_move(tables, year):
    central, flat_t = tables["central"][year], tables["flat"][year]
    listed = set(flat.FLAT_TECHNOLOGIES)
    others = [t for t in central.index if t not in listed and t != "solar-hsat"]
    pd.testing.assert_frame_equal(central.loc[others], flat_t.loc[others])


@pytest.mark.parametrize("year", HORIZONS[1:])
def test_listed_technologies_equal_their_2025_value(tables, year):
    base, got = tables["flat"][2025], tables["flat"][year]
    renamed = {"solar-utility single-axis tracking": "solar-hsat"}
    for tech in flat.FLAT_TECHNOLOGIES:
        t = renamed.get(tech, tech)
        if t not in base.index:
            continue
        for col in ("investment", "FOM", "VOM", "fuel", "lifetime", "capital_cost"):
            if pd.isna(base.at[t, col]):
                continue
            assert got.at[t, col] == pytest.approx(base.at[t, col], rel=1e-9), (tech, col, year)


def test_the_central_does_learn(tables):
    """The guard has teeth: without the file these technologies do get cheaper."""
    for tech in ("onwind", "solar-utility", "biogas", "offwind"):
        c = tables["central"]
        assert c[2050].at[tech, "investment"] < c[2025].at[tech, "investment"], tech


def test_scenario_block_is_the_central_plus_the_cost_file():
    d = yaml.safe_load(SCENARIOS.read_text())
    block, central = dict(d["scen_central_flat_res_costs"]), d["scen_central"]
    assert block.pop("costs") == {"custom_cost_fn": "data/walloon/custom_costs_scen_central_flat_res_costs.csv"}
    assert block == central
