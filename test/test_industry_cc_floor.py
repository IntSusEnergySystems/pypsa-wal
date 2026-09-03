# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Industry CC capture at BEWAL is floored at TIMES STORAGEMININD (item 9)."""

from __future__ import annotations

from pathlib import Path

import pypsa
import pytest

from scripts.walloon_scripts.named_pins import (
    add_industry_cc_floor,
    year_map,
)

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "walloon" / "times_industrial_capture.csv"


def _network() -> pypsa.Network:
    n = pypsa.Network()
    n.set_snapshots(range(2))
    n.snapshot_weightings["generators"] = 4380.0
    n.add("Carrier", ["process emissions", "co2 stored", "gas"])
    n.add(
        "Bus",
        "BEWAL process emissions",
        carrier="process emissions",
        location="BEWAL",
    )
    n.add("Bus", "BEWAL co2 stored", carrier="co2 stored", location="BEWAL")
    n.add("Bus", "co2 atmosphere", carrier="co2 stored", location="EU")
    n.add(
        "Link",
        "BEWAL process emissions CC",
        bus0="BEWAL process emissions",
        bus1="co2 atmosphere",
        bus2="BEWAL co2 stored",
        carrier="process emissions CC",
        efficiency=0.1,
        efficiency2=0.9,
        p_nom=10.0,
        p_nom_extendable=True,
        capital_cost=1.0,
        marginal_cost=0.0,
    )
    n.add(
        "Generator",
        "inventory",
        bus="BEWAL process emissions",
        p_nom=10.0,
        marginal_cost=0.0,
    )
    n.add("Load", "sink", bus="BEWAL co2 stored", p_set=0.0)
    return n


def test_csv_is_the_vd_storageminind_volume():
    kt = year_map(CSV, "kt")
    assert 2025 not in kt
    assert 2030 not in kt
    assert kt[2040] == pytest.approx(5076.88289217246)
    assert kt[2050] == pytest.approx(4826.40081849059)


def test_floor_is_annual_tonnes():
    n = _network()
    n.optimize.create_model()
    add_industry_cc_floor(n, "BEWAL", kt=1.0)  # 1000 t/a
    assert "industry_cc_floor" in n.model.constraints
    rhs = float(n.model.constraints["industry_cc_floor"].rhs.item())
    assert rhs == pytest.approx(1000.0)


def test_zero_or_missing_volume_is_a_noop():
    n = _network()
    n.optimize.create_model()
    add_industry_cc_floor(n, "BEWAL", kt=0.0)
    assert "industry_cc_floor" not in n.model.constraints
