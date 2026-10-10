# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Industry CC capture at BEWAL is floored at TIMES STORAGEMININD (item 9).

B3: a floor is only meaningful if the inventory it draws on can reach it. With
the process-emissions Load set to TIMES's *atmosphere residual* rather than the
gross inventory (B4), the 2040 floor of 5 077 kt sat above the 4 450 kt ceiling
that all of Walloon industrial gas + biomass + process CO2 can physically
supply, so 2040 and 2050 were infeasible. `test_floor_fits_the_process_inventory`
is the cheap invariant that keeps the two aligned.
"""

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
POTENTIALS = ROOT / "data" / "walloon" / "custom_potentials.csv"
#: `cement capture` capture_rate in the processed cost table
CAPTURE_RATE = 0.95
WAL = ROOT / "data" / "walloon"
#: kt/a the fuel CC links must be able to add to process capture; they
#: delivered 3.5 Mt in the 6 Oct 1 h central's 2040 (1.82 biomass + 1.65 gas)
FUEL_CC_HEADROOM_KT = 3000.0


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
    assert kt[2050] == pytest.approx(4842.48777630522)


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


def test_floor_fits_the_process_inventory():
    """B3: the floor must be reachable from what the inventory and the fuel CC links supply.

    The floor is TIMES's STORAGEMININD, i.e. process CO2 AND the fuel CO2 its
    kilns and oxy-fuel furnaces capture (1.4 Mt of the 4.1 Mt in 2040). Since
    2026-10-10 the process inventory is gross *process* CO2 only, so process
    capture covers 0.95 x the inventory and the rest must come from
    `solid biomass for industry CC` + `gas for industry CC`. That remainder must
    stay below what those links can deliver: 3.5 Mt in the 6 Oct 1 h central
    (1.82 + 1.65), so FUEL_CC_HEADROOM_KT with margin. Also catches an inventory
    that has silently become net-of-capture again (B4): the remainder then
    exceeds the headroom.
    """
    import pandas as pd

    pot = pd.read_csv(POTENTIALS)
    load = pot[(pot["bus"] == "BEWAL") & (pot["technology"] == "process emissions")]
    inventory = {
        int(y): float(v) for y, v in zip(load["year"], load["value"])
    }
    floors = sorted(WAL.glob("times_industrial_capture*.csv"))
    assert floors
    for path in floors:
        for year, kt in year_map(path, "kt").items():
            if year not in inventory:
                continue  # not a planning horizon of this run
            remainder = kt - inventory[year] * CAPTURE_RATE
            assert remainder <= FUEL_CC_HEADROOM_KT, (
                f"{path.name} {year}: the industry-CC floor is {kt:,.0f} kt; "
                f"process capture gives {inventory[year] * CAPTURE_RATE:,.0f} kt, "
                f"leaving {remainder:,.0f} kt for the fuel CC links (B3)"
            )
