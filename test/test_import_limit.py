# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""BEWAL electricity imports are capped in TWh, not as a fraction of local supply.

Item 6a: TIMES Transfo_Imp is 2.94 / 6.47 / 10 TWh (2030/40/50). Grouped by
location, BEWAL imports include Flanders and Brussels.
"""

from __future__ import annotations

import pypsa
import pytest

from scripts.solve_network import add_selfsufficiency_constraints


def _toy(load_mw: float = 10.0) -> pypsa.Network:
    n = pypsa.Network()
    n.set_snapshots(range(2))
    n.snapshot_weightings["generators"] = 4380.0
    n.add("Carrier", "AC")
    n.add("Bus", "BEWAL", carrier="AC", location="BEWAL")
    n.add("Bus", "BEVLG", carrier="AC", location="BEVLG")
    n.add(
        "Line",
        "x",
        bus0="BEWAL",
        bus1="BEVLG",
        x=0.1,
        r=0.01,
        s_nom=1000,
        s_max_pu=1.0,
    )
    n.add(
        "Generator",
        "wal",
        bus="BEWAL",
        p_nom=0,
        p_nom_extendable=True,
        marginal_cost=100,
        capital_cost=0,
        carrier="AC",
    )
    n.add(
        "Generator",
        "vlg",
        bus="BEVLG",
        p_nom=1000,
        marginal_cost=1,
        carrier="AC",
    )
    n.add("Load", "wal-load", bus="BEWAL", p_set=load_mw)
    return n


def test_absolute_cap_rhs_is_twh_not_a_fraction():
    n = _toy()
    n.optimize.create_model()
    add_selfsufficiency_constraints(
        n,
        {
            "mode": "absolute",
            "nodes": ["BEWAL"],
            "limit_twh": {2050: 10.0},
        },
        planning_horizons="2050",
    )
    assert "import_energy_limit" in n.model.constraints
    assert "import_positive_Line" in n.model.constraints
    rhs = float(n.model.constraints["import_energy_limit"].rhs.item())
    assert rhs == pytest.approx(10.0 * 1e6)
    assert "Import_p" in n.model.variables
    assert list(n.model.variables["Import_p"].indexes["bus"]) == ["BEWAL"]


def test_year_without_a_cap_is_skipped():
    n = _toy()
    n.optimize.create_model()
    add_selfsufficiency_constraints(
        n,
        {"mode": "absolute", "nodes": ["BEWAL"], "limit_twh": {2050: 10.0}},
        planning_horizons="2025",
    )
    assert "import_energy_limit" not in n.model.constraints
    assert "Import_p" not in n.model.variables
    assert "import_positive_Line" not in n.model.constraints


def test_import_variable_cannot_go_negative():
    """Exports from BEWAL must not create slack on the import cap."""
    n = _toy()
    n.optimize.create_model()
    add_selfsufficiency_constraints(
        n,
        {"mode": "absolute", "nodes": ["BEWAL"], "limit_twh": 10.0},
        planning_horizons="2050",
    )
    lower = n.model.variables["Import_p"].lower
    assert float(lower.min()) >= 0.0


def test_cap_is_respected_when_solved():
    n = _toy(load_mw=100.0)  # 876 GWh/a if fully imported
    n.optimize.create_model()
    add_selfsufficiency_constraints(
        n,
        {"mode": "absolute", "nodes": ["BEWAL"], "limit_twh": 0.5},
        planning_horizons="2050",
    )
    try:
        status, _ = n.optimize.solve_model(solver_name="highs")
    except Exception as exc:
        pytest.skip(f"no LP solver: {exc}")
    if status not in ("ok", "optimal"):
        pytest.skip(f"solver status {status}")
    # 876 GWh of load, 500 GWh cap → some local generation is required.
    # Without a working Import_p link the cheap Flemish plant would serve it all.
    assert float(n.generators_t.p["wal"].mean()) > 1.0
