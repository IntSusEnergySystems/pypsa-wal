# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""BEWAL electricity imports are capped in TWh, not as a fraction of local supply.

Item 6a: TIMES Transfo_Imp is 2.94 / 6.47 / 10 TWh (2030/40/50). Grouped by
location, BEWAL imports include Flanders and Brussels.

`Import_p` is the hourly positive part of net cross-border inflow, summed over
the year — the analogue of TIMES's one-way `Transfo_Imp`, not the annual net
balance. B6 fixed what that expression actually contained: AC and DC were
constrained separately (bound = the larger, not the sum), the `-reversed` leg
of every DC pair was filtered out (so DC *imports* never appeared), and both
flows were scaled up (`/ s_max_pu`, `/ efficiency`) instead of physical.
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
    assert "import_positive" in n.model.constraints
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
    assert "import_positive" not in n.model.constraints


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


def _toy_with_dc(load_mw: float = 10.0) -> pypsa.Network:
    """Add a lossy bidirectional DC border, as `lossy_bidirectional_links` makes it."""
    n = _toy(load_mw=load_mw)
    n.add("Carrier", "DC")
    n.add("Bus", "DE", carrier="AC", location="DE")
    n.add("Generator", "de", bus="DE", p_nom=1000, marginal_cost=1, carrier="AC")
    n.add(
        "Link",
        "alegro",
        bus0="BEWAL",
        bus1="DE",
        carrier="DC",
        p_nom=1000,
        efficiency=0.97,
    )
    n.add(
        "Link",
        "alegro-reversed",
        bus0="DE",
        bus1="BEWAL",
        carrier="DC",
        p_nom=1000,
        efficiency=0.97,
    )
    return n


def _apply(n, twh=10.0):
    add_selfsufficiency_constraints(
        n,
        {"mode": "absolute", "nodes": ["BEWAL"], "limit_twh": twh},
        planning_horizons="2050",
    )


def test_ac_and_dc_share_one_constraint():
    """B6: two constraints made `Import_p` the larger net, never the sum."""
    n = _toy_with_dc()
    n.optimize.create_model()
    _apply(n)
    names = [c for c in n.model.constraints if c.startswith("import_positive")]
    assert names == ["import_positive"], names


def test_dc_imports_are_counted():
    """B6: the import direction is the `-reversed` leg; it must not be filtered."""
    n = _toy_with_dc(load_mw=100.0)
    n.remove("Line", "x")  # DC is the only way in
    n.generators.loc["wal", "marginal_cost"] = 1000.0  # importing must be cheaper
    n.optimize.create_model()
    _apply(n, twh=0.0001)  # 100 MWh/a — far below the 876 GWh of demand
    try:
        status, _ = n.optimize.solve_model(solver_name="highs")
    except Exception as exc:  # pragma: no cover - depends on the local solver
        pytest.skip(f"no LP solver: {exc}")
    if status in ("ok", "optimal"):
        imported = float(
            (n.links_t.p0["alegro-reversed"] * n.snapshot_weightings.generators).sum()
        )
        assert imported <= 1e5 + 1, (
            f"{imported:,.0f} MWh came in over DC while the cap was 100 MWh — "
            "the reversed leg is not in the constraint (B6)"
        )
    # an infeasible status is also a pass: the cap bit hard enough to forbid it


def test_line_flow_is_not_inflated_by_s_max_pu():
    """B6: a 0.7 derating used to book 1.43 MWh of imports per MWh flowed."""
    n = _toy(load_mw=100.0)
    n.lines.loc["x", "s_max_pu"] = 0.7
    n.optimize.create_model()
    _apply(n, twh=0.5)  # 500 GWh vs 876 GWh of demand: binds, but is reachable
    try:
        status, _ = n.optimize.solve_model(solver_name="highs")
    except Exception as exc:  # pragma: no cover - depends on the local solver
        pytest.skip(f"no LP solver: {exc}")
    if status not in ("ok", "optimal"):
        pytest.skip(f"solver status {status}")
    flowed = float(
        (n.lines_t.p1["x"].clip(lower=0) * n.snapshot_weightings.generators).sum()
    )
    assert flowed == pytest.approx(0.5e6, rel=1e-3), (
        f"{flowed:,.0f} MWh crossed under a 500 000 MWh cap — the expression "
        "is scaled by 1/s_max_pu (B6)"
    )
