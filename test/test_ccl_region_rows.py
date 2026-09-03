# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""A region row must detach that region for its own carrier, and no other.

Improvement-plan B1. `add_CCL_constraints` used to rewrite `n.buses.country`
per *bus*, which is carrier-blind: the first `BEVLG` row ever added
(`BEVLG,nuclear-all`, 87552368) silently removed Flanders from **every** `BE`
row. The 2025 offshore pin (`BE,offwind-all min = max = 2262`) then grouped
nothing and the base year built the full 8 GW potential; the 2030 solve applied
Elia's whole 10 GW solar remainder to Brussels alone — an empty LP in 0 barrier
iterations, misdiagnosed three times before the cause was found.

The fixture is shaped like the real 3-node Belgium: offshore wind only on the
coast, onshore wind everywhere, the only nuclear link in Flanders, and a dear
backup generator at every node so the LP can always balance and the optimiser
builds each cheap carrier right up to whatever cap the CCL writes.
"""

from __future__ import annotations

import pandas as pd
import pypsa
import pytest

import scripts.solve_network as sn

#: enough load that a cheap carrier is always built to its ceiling
NODE_LOAD = 4000.0


def _caps(tmp_path, rows: dict[tuple[str, str], dict[str, float]]):
    """Write a minimal two-level agg_p_nom_minmax CSV for one horizon."""
    index = pd.MultiIndex.from_tuples(sorted(rows), names=["country", "carrier"])
    frame = pd.DataFrame(
        [[rows[k].get("min"), rows[k].get("max")] for k in sorted(rows)],
        index=index,
        columns=pd.MultiIndex.from_tuples([("2030", "min"), ("2030", "max")]),
    )
    path = tmp_path / "caps.csv"
    frame.to_csv(path)
    return path


def _config(path):
    return {
        "solving": {
            "agg_p_nom_limits": {
                "file": str(path),
                "agg_offwind": True,
                "agg_solar": False,
                "agg_nuclear": True,
                "agg_ccgt": False,
                "include_existing": False,
                "growth_multiplier": None,
                "build_rates_file": None,
            }
        }
    }


def _network() -> pypsa.Network:
    """BEWAL / BEVLG / BEBRU, every bus country `BE`, locations per node."""
    n = pypsa.Network()
    n.set_snapshots(range(2))
    n.add("Carrier", ["AC", "offwind-ac", "onwind", "OCGT", "nuclear", "uranium"])
    for node in ("BEWAL", "BEVLG", "BEBRU"):
        n.add("Bus", node, carrier="AC", country="BE", location=node)
        n.add("Load", f"{node} load", bus=node, p_set=NODE_LOAD)
        n.add(
            "Generator",
            f"{node} onwind",
            bus=node,
            carrier="onwind",
            p_nom_extendable=True,
            p_nom_max=5000.0,
            capital_cost=1.0,
            marginal_cost=0.0,
        )
        n.add(
            "Generator",
            f"{node} backup",
            bus=node,
            carrier="OCGT",
            p_nom_extendable=True,
            capital_cost=50.0,
            marginal_cost=100.0,
        )
    n.add("Bus", "BEVLG uranium", carrier="uranium", country="BE", location="BEVLG")
    n.add(
        "Generator",
        "BEVLG offwind",
        bus="BEVLG",
        carrier="offwind-ac",
        p_nom_extendable=True,
        p_nom_max=8000.0,
        capital_cost=1.0,
        marginal_cost=0.0,
    )
    n.add(
        "Link",
        "BEVLG nuclear",
        bus0="BEVLG uranium",
        bus1="BEVLG",
        carrier="nuclear",
        efficiency=0.33,
        p_nom_extendable=True,
        p_nom_max=9000.0,
        capital_cost=1.0,
    )
    return n


def _groups(n, config, horizon="2030"):
    """{group label: rhs} of every `agg_p_nom_max` constraint the CCL writes."""
    n.optimize.create_model()
    sn.add_CCL_constraints(n, config, horizon)
    out = {}
    for name in ("agg_p_nom_max", "agg_p_nom_max_links"):
        if name not in n.model.constraints:
            continue
        rhs = n.model.constraints[name].rhs.to_series()
        out.update({tuple(k): float(v) for k, v in rhs.items()})
    return out


def _built(n, config, carriers, horizon="2030"):
    """Solve with the CCL applied and return the MW built in `carriers`."""
    n.optimize.create_model()
    sn.add_CCL_constraints(n, config, horizon)
    try:
        status, condition = n.optimize.solve_model(solver_name="highs")
    except Exception as exc:  # pragma: no cover - depends on the local solver
        pytest.skip(f"no LP solver: {exc}")
    if status not in ("ok", "optimal"):
        pytest.skip(f"solver status {status} / {condition}")
    g = n.generators
    return float(g.loc[g.carrier.isin(carriers), "p_nom_opt"].sum())


@pytest.fixture(autouse=True)
def _myopic():
    previous = getattr(sn, "foresight", None)
    sn.foresight = "myopic"
    yield
    sn.foresight = previous


def test_be_row_still_covers_flanders_when_a_region_row_names_another_carrier(
    tmp_path,
):
    """The regression itself: a BEVLG *nuclear* row must not free BEVLG offshore."""
    caps = _caps(
        tmp_path,
        {
            ("BE", "offwind-all"): {"max": 2262.0},
            ("BE", "nuclear-all"): {"max": 2000.0},
            ("BEVLG", "nuclear-all"): {"max": 1000.0},
        },
    )
    groups = _groups(_network(), _config(caps))
    assert ("BE", "offwind-all") in groups, (
        "the BE offshore cap grouped nothing — Flanders was detached by the "
        "nuclear row (B1)"
    )
    assert groups[("BE", "offwind-all")] == pytest.approx(2262.0)


def test_offshore_cannot_exceed_the_belgian_cap(tmp_path):
    """End to end: 2025's 8 GW could only happen because the group was empty."""
    caps = _caps(
        tmp_path,
        {
            ("BE", "offwind-all"): {"max": 2262.0},
            ("BEVLG", "nuclear-all"): {"max": 1000.0},
        },
    )
    built = _built(_network(), _config(caps), ["offwind-ac"])
    assert built == pytest.approx(2262.0, abs=1e-3)


def test_a_nuclear_region_row_does_not_free_flemish_onshore_wind(tmp_path):
    """Same detachment, on the carrier with turbines at every node."""
    caps = _caps(
        tmp_path,
        {
            ("BE", "onwind"): {"max": 3337.0},
            ("BEWAL", "onwind"): {"max": 2359.0},
            ("BEVLG", "nuclear-all"): {"max": 1000.0},
        },
    )
    n = _network()
    # drop the cheap offshore alternative, or Flanders serves its load with it
    # and the onshore ceiling never shows in the result
    n.remove("Generator", "BEVLG offwind")
    built = _built(n, _config(caps), ["onwind"])
    # BEWAL 2359 + the 978 MW remainder shared by BEVLG and BEBRU
    assert built == pytest.approx(3337.0, abs=1e-3)


def test_region_row_is_subtracted_from_its_parent(tmp_path):
    """BEVLG keeps its own cap; the BE remainder covers the other nodes."""
    caps = _caps(
        tmp_path,
        {
            ("BE", "nuclear-all"): {"max": 2000.0},
            ("BEVLG", "nuclear-all"): {"max": 1000.0},
        },
    )
    groups = _groups(_network(), _config(caps))
    assert groups[("BEVLG", "nuclear-all")] == pytest.approx(1000.0)
    assert ("BE", "nuclear-all") not in groups, (
        "no BE-country nuclear link exists, so the remainder group is empty"
    )


def test_region_row_still_wins_for_its_own_carrier(tmp_path):
    """A BEWAL onwind row binds Wallonia, not the whole of Belgium."""
    caps = _caps(
        tmp_path,
        {
            ("BE", "onwind"): {"max": 3337.0},
            ("BEWAL", "onwind"): {"max": 2359.0},
        },
    )
    groups = _groups(_network(), _config(caps))
    assert groups[("BEWAL", "onwind")] == pytest.approx(2359.0)
    assert groups[("BE", "onwind")] == pytest.approx(978.0)


def test_bus_countries_are_not_mutated(tmp_path):
    """The solved network must keep real ISO codes (the reset used to be off)."""
    caps = _caps(
        tmp_path,
        {
            ("BE", "offwind-all"): {"max": 2262.0},
            ("BEVLG", "nuclear-all"): {"max": 1000.0},
        },
    )
    n = _network()
    _groups(n, _config(caps))
    assert set(n.buses.country.unique()) == {"BE"}


def test_a_standing_fleet_above_its_cap_is_reported(tmp_path, caplog):
    """B8: the 'empty LP in 0 iterations' failure must name the group.

    A 2025 network solved under the old grouping carries 8 GW of Belgian
    offshore into a 2030 horizon capped at 2 262 MW. Gurobi calls that
    "infeasible or unbounded" with no IIS; three items were blamed for it in
    turn before the cause was found.
    """
    import logging

    caps = _caps(tmp_path, {("BE", "offwind-all"): {"max": 2262.0}})
    n = _network()
    n.add(
        "Generator",
        "BEVLG offwind-2025",
        bus="BEVLG",
        carrier="offwind-ac",
        p_nom=8000.0,
        p_nom_extendable=False,
        build_year=2025,
        lifetime=30,
    )
    config = _config(caps)
    config["solving"]["agg_p_nom_limits"]["include_existing"] = True
    with caplog.at_level(logging.WARNING):
        _groups(n, config)
    messages = [r.getMessage() for r in caplog.records]
    hits = [m for m in messages if "standing fleet already exceeds" in m]
    assert hits, messages
    assert "offwind-all" in hits[0]
    assert "5738" in hits[0].replace(" ", "")  # 8000 - 2262 MW over the cap
