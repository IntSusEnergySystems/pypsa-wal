# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""The transmission floor may never rise above the NTC ceiling.

`transmission_limit: vopt` activates a branch of `set_transmission_limit` that
was dead under `v1.0`::

    if factor == "opt" or float(factor) > 1.0:
        n.lines["s_nom_min"] = lines_s_nom

`lines_s_nom` is `n.lines.s_nom.where(n.lines.type == "", _lines_s_nom)`, and in
pypsa-wal `n.lines.type` is *not* empty -- it stays
`"Al/St 240/40 4-bundle 380.0"` through clustering. So the floor is rebuilt from
the conductor rating and the derating `apply_ntc_limits` wrote into
`s_nom` / `s_nom_max` is discarded. On the real 2030 network that inverted the
bounds of six of ten AC lines; PyPSA only warns, then Gurobi returns
`infeasible_or_unbounded`.

`add_brownfield.carry_forward_built_grid` runs immediately after
`set_transmission_limit` and clips the floor back under the ceiling.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pypsa
import pytest

from scripts.add_brownfield import carry_forward_built_grid
from scripts.prepare_network import set_transmission_limit

# rows set_transmission_costs looks up; the values do not matter here
COSTS = pd.DataFrame(
    {"capital_cost": [1.0, 1.0, 1.0, 1.0]},
    index=["HVAC overhead", "HVDC overhead", "HVDC submarine", "HVDC inverter pair"],
)


def _derated_network() -> pypsa.Network:
    """DE-NL as the clustered grid has it, then capped by its 5 000 MW NTC.

    The conductor rating is 13 584.8 MW (9 509 usable); the NTC allows
    7 142.9 MW nominal (5 000 usable). `type` is left populated, as it is in
    every pypsa-wal network.
    """
    n = pypsa.Network()
    n.add("Carrier", ["AC", "DC"])
    n.add("Bus", "DE", carrier="AC", country="DE", v_nom=380.0)
    n.add("Bus", "NL", carrier="AC", country="NL", v_nom=380.0)
    n.add(
        "Line",
        "DE-NL",
        bus0="DE",
        bus1="NL",
        type="Al/St 240/40 4-bundle 380.0",
        num_parallel=6.0,
        length=300.571422,
        s_nom=7142.9,          # already derated by apply_ntc_limits
        s_nom_min=0.0,
        s_nom_max=7142.9,      # NTC / s_max_pu
        s_max_pu=0.7,
        x=0.1,
        r=0.01,
    )
    return n


def _previous(n: pypsa.Network, s_nom_opt: float) -> pypsa.Network:
    n_p = n.copy()
    n_p.lines["s_nom_opt"] = s_nom_opt
    return n_p


def test_conductor_type_would_push_the_floor_above_the_ntc_ceiling():
    """Guards the mechanism itself, so a future `type == ""` cannot hide it."""
    n = _derated_network()
    set_transmission_limit(n, "v", "opt", COSTS)

    assert n.lines.at["DE-NL", "s_nom_extendable"]
    # the floor came from the conductor, not from the derated s_nom
    assert n.lines.at["DE-NL", "s_nom_min"] > n.lines.at["DE-NL", "s_nom_max"]


def test_carry_forward_clips_the_floor_to_the_ceiling():
    n = _derated_network()
    set_transmission_limit(n, "v", "opt", COSTS)
    carry_forward_built_grid(n, _previous(n, s_nom_opt=0.0))

    assert n.lines.at["DE-NL", "s_nom_min"] == pytest.approx(7142.9)
    assert n.lines.at["DE-NL", "s_nom_min"] <= n.lines.at["DE-NL", "s_nom_max"]


def test_the_previous_horizon_is_still_carried_forward():
    """Clipping must not cost us the build the last horizon paid for.

    The ceiling is raised to 12 000 so the previous optimum sits above the
    conductor rating (10 188.6 MW here) but below the cap -- the case where the
    carry-forward, not today's grid, has to set the floor.
    """
    n = _derated_network()
    n.lines.loc["DE-NL", ["s_nom_min", "s_nom_max"]] = [0.0, 12000.0]
    set_transmission_limit(n, "v", "opt", COSTS)
    conductor = n.lines.at["DE-NL", "s_nom_min"]
    carry_forward_built_grid(n, _previous(n, s_nom_opt=11000.0))

    assert conductor < 11000.0 < 12000.0, "premise: the carry-forward must win"
    assert n.lines.at["DE-NL", "s_nom_min"] == pytest.approx(11000.0)


def test_dc_floor_is_clipped_too():
    n = _derated_network()
    n.add(
        "Link",
        "DE-NL-dc",
        bus0="DE",
        bus1="NL",
        carrier="DC",
        length=300.0,
        underwater_fraction=0.0,
        p_nom=1000.0,
        p_nom_max=1000.0,
        reversed=False,
    )
    set_transmission_limit(n, "v", "opt", COSTS)
    # a previous optimum above a cap that has since been lowered
    carry_forward_built_grid(n, _previous(n, s_nom_opt=0.0).copy())
    n_p = n.copy()
    n_p.links["p_nom_opt"] = 5000.0
    carry_forward_built_grid(n, n_p)

    assert n.links.at["DE-NL-dc", "p_nom_min"] == pytest.approx(1000.0)


def test_no_inverted_bounds_survive_the_brownfield_sequence():
    n = _derated_network()
    set_transmission_limit(n, "v", "opt", COSTS)
    carry_forward_built_grid(n, _previous(n, s_nom_opt=0.0))

    assert not (n.lines.s_nom_min > n.lines.s_nom_max + 1e-6).any()
    dc = n.links.carrier == "DC"
    assert not (n.links.loc[dc, "p_nom_min"] > n.links.loc[dc, "p_nom_max"] + 1e-6).any()
