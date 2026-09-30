# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""`scen_test_lowccs_ptx`: the low-CCS / power-to-fuel TEST of 2026-09-30.

It must be the central scenario plus exactly three changes (lever D, no TIMES
capture floor, no power-to-X must-runs), or a difference against the central
cannot be attributed to them. It must also stay out of the cabinet batch and
out of publication. Design: docs/logs/2026-09-30_cabinet_batch_20260930_2010_1h.md §12.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from scripts._helpers import update_config
from scripts.walloon_scripts.named_pins import lookup_year_value

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
NAME = "scen_test_lowccs_ptx"
CHANGED = {
    "co2_export_limit",
    "industry_cc_floor",
    "min_part_load_fischer_tropsch",
    "min_part_load_methanolisation",
    "min_part_load_methanation",
}


def _load(name):
    return yaml.safe_load((CONFIG / name).read_text())


@pytest.fixture(scope="module")
def merged():
    base = _load("config.default.yaml")
    update_config(base, _load("config.walloon.yaml"))
    scen = _load("scenarios.walloon.yaml")
    test, central = copy.deepcopy(base), copy.deepcopy(base)
    update_config(test, scen[NAME])
    update_config(central, scen["scen_central"])
    return test, central


def test_only_the_three_levers_differ_from_the_central(merged):
    test, central = merged
    for key in set(test) | set(central):
        if key != "sector":
            assert test.get(key) == central.get(key), key
    diff = {k for k in set(test["sector"]) | set(central["sector"])
            if test["sector"].get(k) != central["sector"].get(k)}
    assert diff == CHANGED


def test_the_levers_have_the_documented_values(merged):
    sector = merged[0]["sector"]
    cap = sector["co2_export_limit"]
    assert cap["enable"] and cap["node"] == "BEWAL"
    assert cap["overage_price"] == 500
    assert {y: lookup_year_value(cap, y, "kt", "kt") for y in (2025, 2030, 2035, 2040, 2045, 2050)} == {
        2025: None, 2030: None, 2035: None, 2040: 3000.0, 2045: 3000.0, 2050: 3000.0,
    }
    assert sector["industry_cc_floor"]["enable"] is False
    for key in ("fischer_tropsch", "methanolisation", "methanation"):
        assert sector[f"min_part_load_{key}"] == 0, key
    # DAC is the documented last resort, not part of the test.
    assert sector["dac"] is False


def test_it_runs_at_production_resolution_and_weather(merged):
    test = merged[0]
    assert test["clustering"]["temporal"]["resolution_sector"] == "1h"
    assert test["snapshots"]["start"].startswith("2010")
    assert "2010" in test["atlite"]["default_cutout"]


def test_the_run_layer_selects_it_and_cannot_publish():
    layer = _load("config.test_lowccs_ptx.yaml")
    assert layer["run"]["name"] == [NAME]
    assert layer["html_publish"]["enable"] is False


def test_it_is_not_part_of_the_cabinet_batch():
    assert NAME not in _load("config.walloon.yaml")["run"]["name"]
    listed = [s["name"] for s in _load("pypsa2html.yaml")["scenarios"]]
    assert NAME not in listed, "a test run must not enter the combined report"


def test_the_export_limit_is_off_by_default():
    base = _load("config.walloon.yaml")["sector"]["co2_export_limit"]
    assert base["enable"] is False and not base["kt"]
