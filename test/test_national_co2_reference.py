# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Wallonia's national cap uses TIMES-WAL's 1990 reference (2026-09-30)."""

from pathlib import Path

import pandas as pd
import pytest
import yaml

from scripts.solve_network import apply_national_co2_reference

ROOT = Path(__file__).resolve().parents[1]


def test_listed_country_takes_the_reference_others_keep_the_split():
    base = pd.Series({"BEWAL": 33_337e3, "BEVLG": 60_000e3})
    out = apply_national_co2_reference(base, {"BEWAL": 45_600})
    assert out["BEWAL"] == pytest.approx(45_600e3)
    assert out["BEVLG"] == base["BEVLG"]
    assert base["BEWAL"] == 33_337e3  # input not mutated


def test_empty_or_unknown_is_a_no_op():
    base = pd.Series({"BEWAL": 1.0})
    assert apply_national_co2_reference(base, {}).equals(base)
    assert apply_national_co2_reference(base, {"XX": 5}).equals(base)


def test_walloon_config_carries_the_times_reference():
    cfg = yaml.safe_load((ROOT / "config" / "config.walloon.yaml").read_text())
    assert cfg["co2_reference_1990_kt"] == {"BEWAL": 45600}
    # 2030 cap = 0.45 x 45.6 Mt = 20.5 Mt, i.e. room for TIMES's 19.7 Mt without capture
    assert cfg["budget_national"][2030]["BEWAL"] * 45600 == pytest.approx(20520)
