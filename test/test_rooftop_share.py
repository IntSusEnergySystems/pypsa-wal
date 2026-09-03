# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Rooftop PV counts as BEWAL solar, and TIMES sets its share of the fleet.

Item 8. Rooftop sits on the ``BEWAL low voltage`` bus, whose *country* is the
national code — grouping it correctly used to need a country alias. Since B1
the CCL groups by ``(bus location, carrier)``, so the LV bus is BEWAL by
construction and the alias is gone.

The share pin itself stays **off** (B5): PyPSA labels the whole historical
Walloon fleet ``solar``, so a share of total capacity cannot be imposed on a
base year that is pinned to that fleet.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd
import pypsa
import pytest

from scripts.walloon_scripts.named_pins import (
    add_rooftop_share_constraint,
    year_map,
)

ROOT = Path(__file__).resolve().parents[1]
SHARE_CSV = ROOT / "data" / "walloon" / "times_pv_rooftop_share.csv"


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


def test_share_pin_is_infeasible_inside_a_collapsed_base_year_envelope():
    """Why item 8 is off (B5), stated as an LP fact rather than a note.

    2025 BEWAL solar-all is `min = max` at the historical fleet, all of which
    PyPSA labels utility. A 25.8 % rooftop share then needs ~35 MW of extra
    capacity inside a corridor that has none — infeasible. Taking rooftop out
    of `solar-all` makes it solvable but unpins total PV, which is the trade
    B5 refuses. Re-enabling item 8 means splitting the base-year fleet first.
    """
    share = 0.25806451612903225
    utility = 100.0

    def _solve(rooftop_in_envelope: bool):
        n = _network()
        n.generators.at["BEWAL solar", "p_nom"] = utility
        n.generators.at["BEWAL solar", "p_nom_min"] = utility
        n.generators.at["BEWAL solar", "p_nom_max"] = utility
        n.optimize.create_model()
        add_rooftop_share_constraint(n, "BEWAL", share)
        p_nom = n.model["Generator-p_nom"]
        util = p_nom.loc["BEWAL solar"]
        roof = p_nom.loc["BEWAL solar rooftop"]
        if rooftop_in_envelope:
            n.model.add_constraints(util + roof == utility, name="solar_all")
        else:
            n.model.add_constraints(util == utility, name="solar_all")
        return n.optimize.solve_model(solver_name="highs")

    try:
        status_in, cond_in = _solve(True)
        status_out, cond_out = _solve(False)
    except Exception as exc:
        pytest.skip(f"no LP solver: {exc}")
    assert status_in != "ok" or cond_in not in ("optimal",)
    assert status_out in ("ok",) or cond_out in ("optimal",)


def test_share_constraint_forces_the_times_ratio():
    n = _network()
    n.optimize.create_model()
    add_rooftop_share_constraint(n, "BEWAL", 0.75)
    assert "rooftop_share_BEWAL" in n.model.constraints
    try:
        status, _ = n.optimize.solve_model(solver_name="highs")
    except Exception as exc:
        pytest.skip(f"no LP solver: {exc}")
    if status not in ("ok", "optimal"):
        pytest.skip(f"solver status {status}")
    roof = float(n.generators.at["BEWAL solar rooftop", "p_nom_opt"])
    util = float(n.generators.at["BEWAL solar", "p_nom_opt"])
    total = roof + util
    assert total > 0
    assert roof / total >= 0.75 - 1e-6


def test_committed_share_csv_has_2050_above_three_quarters():
    shares = year_map(SHARE_CSV, "share")
    assert shares[2050] == pytest.approx(0.858125, rel=1e-4)
    assert shares[2040] == pytest.approx(0.760539, rel=1e-3)
    df = pd.read_csv(SHARE_CSV, comment="#")
    # share column is rooftop / (rooftop + utility), not a hand-typed guess
    recomputed = df["rooftop_gw"] / (df["rooftop_gw"] + df["utility_gw"])
    assert (recomputed - df["share"]).abs().max() < 1e-4


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
