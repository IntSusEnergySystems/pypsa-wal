# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Rooftop PV carries an absolute TIMES floor; ground-mounted PV carries none.

Item 8. Until 2026-09-22 this was a *share* pin (``solar rooftop`` >= s x
solar-all), which fixed the composition of the Walloon PV fleet without fixing
its size and made every MW of ground-mounted PV drag 1/s - 1 MW of dearer
rooftop along — the mechanism ``docs/co2-sequestration.md`` §7.2 measured
throttling the model's cheapest abatement. The floor transfers the TIMES roof
capacity (``rooftop_gw``, ``VAR_Cap`` of the ERNW_PV roof processes) and leaves
the ground-mounted tranche free.

Rooftop sits on the ``BEWAL low voltage`` bus, whose *country* is the national
code. Since B1 the CCL groups by ``(bus location, carrier)``, so the LV bus is
BEWAL by construction and no country alias is needed.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd
import pypsa
import pytest

from scripts.walloon_scripts.named_pins import (
    add_rooftop_floor_constraint,
    year_map,
)

ROOT = Path(__file__).resolve().parents[1]
SHARE_CSV = ROOT / "data" / "walloon" / "times_pv_rooftop_share.csv"
CENTRAL_CSV = ROOT / "data" / "walloon" / "times_pv_rooftop_share_scen_central.csv"


def _network() -> pypsa.Network:
    n = pypsa.Network()
    n.set_snapshots(range(2))
    n.snapshot_weightings["generators"] = 4380.0
    n.add("Carrier", ["AC", "low voltage", "solar", "solar rooftop"])
    n.add("Bus", "BEWAL", carrier="AC", country="BE", location="BEWAL")
    n.add(
        "Bus",
        "BEWAL low voltage",
        carrier="low voltage",
        country="BE",
        location="BEWAL",
    )
    n.add(
        "Generator",
        "BEWAL solar",
        bus="BEWAL",
        carrier="solar",
        p_nom=0,
        p_nom_extendable=True,
        p_nom_max=10000,
        capital_cost=1.0,
        marginal_cost=0.0,
    )
    n.add(
        "Generator",
        "BEWAL solar rooftop",
        bus="BEWAL low voltage",
        carrier="solar rooftop",
        p_nom=0,
        p_nom_extendable=True,
        p_nom_max=10000,
        capital_cost=2.0,
        marginal_cost=0.0,
    )
    n.add("Load", "d", bus="BEWAL", p_set=1.0)
    return n


def test_rooftop_groups_with_bewal_by_location():
    """No alias needed: the LV bus already carries the region as its location."""
    n = _network()
    assert n.buses.at["BEWAL low voltage", "country"] == "BE"
    location = n.generators.bus.map(n.buses.location)
    assert location["BEWAL solar rooftop"] == "BEWAL"
    assert location["BEWAL solar"] == "BEWAL"


def test_floor_forces_the_times_capacity():
    n = _network()
    n.optimize.create_model()
    add_rooftop_floor_constraint(n, "BEWAL", 4.5)  # GW
    assert "rooftop_floor_BEWAL" in n.model.constraints
    try:
        status, _ = n.optimize.solve_model(solver_name="highs")
    except Exception as exc:
        pytest.skip(f"no LP solver: {exc}")
    if status not in ("ok", "optimal"):
        pytest.skip(f"solver status {status}")
    assert float(n.generators.at["BEWAL solar rooftop", "p_nom_opt"]) >= 4500 - 1e-3


def test_ground_mounted_pv_is_not_dragged_by_the_floor():
    """The point of the change: rooftop is floored, ground-mounted is free.

    Under the share pin the two carriers were tied — rooftop >= s x solar-all
    means every MW of ground-mounted PV needs s/(1-s) MW of rooftop, which is
    what stalled `solar-hsat` at 6 % of its potential in 2040
    (docs/co2-sequestration.md §7.2). With a floor, the ground-mounted tranche
    solves to exactly the same value whether the floor is there or not.
    """

    def _ground(with_floor: bool) -> float:
        n = _network()
        n.optimize.create_model()
        if with_floor:
            add_rooftop_floor_constraint(n, "BEWAL", 4.5)
        status, _ = n.optimize.solve_model(solver_name="highs")
        if status not in ("ok", "optimal"):
            pytest.skip(f"solver status {status}")
        return float(n.generators.at["BEWAL solar", "p_nom_opt"])

    try:
        free, floored = _ground(False), _ground(True)
    except Exception as exc:  # no LP solver
        pytest.skip(f"no LP solver: {exc}")
    assert floored == pytest.approx(free)


def test_standing_vintages_count_towards_the_floor():
    """The floor is a fleet figure, so a brownfield vintage discharges part of it."""
    n = _network()
    n.add(
        "Generator",
        "BEWAL solar rooftop-2025",
        bus="BEWAL low voltage",
        carrier="solar rooftop",
        p_nom=1770.0,  # baseyear_pv_split.csv
        p_nom_extendable=False,
    )
    n.optimize.create_model()
    add_rooftop_floor_constraint(n, "BEWAL", 4.5)
    try:
        status, _ = n.optimize.solve_model(solver_name="highs")
    except Exception as exc:
        pytest.skip(f"no LP solver: {exc}")
    if status not in ("ok", "optimal"):
        pytest.skip(f"solver status {status}")
    new = float(n.generators.at["BEWAL solar rooftop", "p_nom_opt"])
    assert new == pytest.approx(4500 - 1770, abs=1.0)


def test_zero_or_missing_floor_adds_nothing():
    n = _network()
    n.optimize.create_model()
    for gw in (None, 0, -1):
        add_rooftop_floor_constraint(n, "BEWAL", gw)
    assert "rooftop_floor_BEWAL" not in n.model.constraints


def test_unreachable_floor_on_a_frozen_fleet_raises_rather_than_going_infeasible():
    """No extendable rooftop left: say so, instead of letting Gurobi say nothing."""
    n = _network()
    n.generators.loc["BEWAL solar rooftop", "p_nom_extendable"] = False
    n.generators.loc["BEWAL solar rooftop", "p_nom"] = 1770.0
    n.optimize.create_model()
    with pytest.raises(ValueError, match="cannot reach the floor"):
        add_rooftop_floor_constraint(n, "BEWAL", 4.5)


def test_committed_csvs_expose_the_capacity_column_the_model_reads():
    """`rooftop_gw` is what `sector.rooftop_floor` consumes, not `share`."""
    for csv in (SHARE_CSV, CENTRAL_CSV):
        gw = year_map(csv, "rooftop_gw")
        assert gw[2050] > gw[2040] > gw[2030] > 0
        df = pd.read_csv(csv, comment="#")
        # the superseded share column must stay consistent with the capacities
        recomputed = df["rooftop_gw"] / (df["rooftop_gw"] + df["utility_gw"])
        assert (recomputed - df["share"]).abs().max() < 1e-4
    central = year_map(CENTRAL_CSV, "rooftop_gw")
    assert central[2040] == pytest.approx(10.470106, rel=1e-6)
    assert central[2050] == pytest.approx(11.269192, rel=1e-6)


def test_floor_clears_the_baseyear_fleet_so_it_actually_binds():
    """A floor below the 2025 standing fleet would be decoration, not a pin."""
    standing_2025 = 1770.0  # data/walloon/baseyear_pv_split.csv
    gw = year_map(CENTRAL_CSV, "rooftop_gw")
    assert min(gw.values()) * 1e3 > standing_2025


def test_rooftop_is_inside_the_solar_all_group():
    """B5: the caps file holds Elia's *total* PV, so the group must be total PV.

    With `solar rooftop` outside `rename_solar`, the 2025 pin bounded utility
    alone and the solve came out at 5 510 MW of Walloon PV against a 4 088 MW
    historical pin. `res_build_rates.csv` derives the regional split from the
    same total, so the two only agree when rooftop is in the group.
    """
    import scripts.solve_network as sn

    src = inspect.getsource(sn.add_CCL_constraints)
    assert '"solar rooftop": "solar-all"' in src, (
        "rooftop is outside solar-all: the base-year pin no longer bounds "
        "total PV (B5)"
    )
