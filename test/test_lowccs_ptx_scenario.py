# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""`scen_test_lowccs_ptx`: the low-CCS / power-to-fuel TEST of 2026-09-30.

It must be the central scenario plus exactly three changes (lever D, no TIMES
capture floor, no power-to-X must-runs), or a difference against the central
cannot be attributed to them. Since 2026-10-10 it runs with the cabinet batch
but is never presented as a cabinet scenario. Design:
docs/logs/2026-09-30_cabinet_batch_20260930_2010_1h.md §12; the capture cap it
inherits from the central: docs/logs/2026-10-10_cabinet_batch_nuc3_nuc4_2010_1h.md §3.
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
# The third lever, the power-to-X must-runs at 0, moved into config.walloon.yaml
# for every scenario on 2026-10-04, so it no longer differs from the central.
# The block still states it, and test_the_levers_have_the_documented_values
# still pins the value.
CHANGED = {
    "co2_export_limit",
    "industry_cc_floor",
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


def test_only_the_levers_differ_from_the_central(merged):
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


def test_it_runs_with_the_batch_but_never_as_a_cabinet_scenario():
    """Kept in the batch on 2026-10-10 ("old but interesting", S. Quoilin).

    Until then it stayed out of `run.name`. It now runs with the cabinet batch,
    last, and is still not a cabinet scenario: in the combined report (decided
    1 Oct 2026) it must be labelled as a test.
    """
    names = _load("config.walloon.yaml")["run"]["name"]
    assert names[-1] == NAME, "the test runs last, after the cabinet scenarios"
    listed = {s["name"]: s.get("label", "") for s in _load("pypsa2html.yaml")["scenarios"]}
    if NAME in listed:
        assert listed[NAME].startswith("TEST"), "a test run in the report must be labelled TEST"


def test_the_export_limit_is_off_by_default():
    base = _load("config.walloon.yaml")["sector"]["co2_export_limit"]
    assert base["enable"] is False and not base["kt"]
