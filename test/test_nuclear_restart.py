# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Restart of a reactor that has already left the network (Tihange 1, 2026-10-10).

`retrofit_retired_nuclear` extends a plant only in the step where it retires.
Tihange 1 retired in 2025, so the 4 GW scenario needs a separate restart
option at the Tihange 3 extension cost, offered once, then renewed by the
ordinary retrofit when its 10 years run out.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pypsa
import pytest
import yaml

from scripts.walloon_scripts.nuclear_helper import (
    restart_options,
    restart_retired_nuclear,
    retrofit_retired_nuclear,
)

ROOT = Path(__file__).resolve().parents[1]
EFF = 0.326
RETRO_CC = 262_000.0  # EUR/MW_e/a, the order of 1 800 EUR/kW over 10 years
TIHANGE_1 = {"Tihange 1": {"node": "BEWAL", "p_nom_e": 962, "from_year": 2035,
                           "cost_key": "nuclear retrofit"}}
TEN_YEAR = [2025, 2030, 2040, 2050]
FIVE_YEAR = [2025, 2030, 2035, 2040, 2045, 2050]


def _costs() -> pd.DataFrame:
    return pd.DataFrame(
        {"capital_cost": [RETRO_CC, 875_000.0], "lifetime": [10.0, 40.0]},
        index=["nuclear retrofit", "nuclear"],
    )


def _network() -> pypsa.Network:
    n = pypsa.Network()
    n.add("Bus", "EU uranium", carrier="uranium")
    n.add("Bus", "BEWAL", carrier="AC")
    n.add("Link", "BEWAL nuclear-2025", bus0="EU uranium", bus1="BEWAL",
          carrier="nuclear", efficiency=EFF, p_nom=0.03, p_nom_extendable=True,
          capital_cost=875_000.0 * EFF, marginal_cost=4.5, build_year=2025,
          lifetime=60.0)
    return n


def _restart(n, year, horizons=TEN_YEAR, plants=TIHANGE_1):
    return restart_retired_nuclear(n, year, horizons, _costs(), plants)


@pytest.mark.parametrize("year,offered", [(2025, False), (2030, False), (2040, True), (2050, False)])
def test_offered_once_in_the_first_horizon_after_from_year(year, offered):
    n = _network()
    added = _restart(n, year)
    assert bool(added) is offered


def test_five_year_grid_offers_it_in_2035():
    assert _restart(_network(), 2035, FIVE_YEAR)
    assert not _restart(_network(), 2040, FIVE_YEAR)


def test_restart_is_priced_and_sized_like_the_tihange_3_extension():
    n = _network()
    (name,) = _restart(n, 2040)
    link = n.links.loc[name]
    assert link.carrier == "nuclear"
    assert link.bus0 == "EU uranium" and link.bus1 == "BEWAL"
    assert link.p_nom_extendable
    assert link.p_nom == 0.0 and link.p_nom_min == 0.0
    assert link.p_nom_max * link.efficiency == pytest.approx(962.0)
    assert link.build_year == 2040
    assert link.lifetime == 10.0
    # Per MW of uranium input, like retrofit_retired_nuclear.
    assert link.capital_cost == pytest.approx(RETRO_CC * EFF)
    # The new-build option it was copied from is untouched.
    assert n.links.at["BEWAL nuclear-2025", "capital_cost"] == pytest.approx(875_000.0 * EFF)


def test_restart_is_renewed_by_the_ordinary_retrofit():
    """At the end of its 10 years the restarted unit retires like Tihange 3 and is renewed."""
    n = _network()
    (name,) = _restart(n, 2040)
    n.links.loc[name, "p_nom_opt"] = 962.0 / EFF
    retired = n.links.loc[[name]]
    n2050 = _network()
    retrofit_retired_nuclear(n2050, retired, 2050, _costs(), retrofit_nuclear_once=False)
    renewal = f"{name} retrofit"
    assert renewal in n2050.links.index
    assert n2050.links.at[renewal, "p_nom_max"] == pytest.approx(962.0 / EFF)
    assert n2050.links.at[renewal, "build_year"] == 2050
    # And the restart itself is not offered a second time in 2050.
    assert not _restart(n2050, 2050)


def test_no_nuclear_link_at_the_node_fails_loudly():
    n = pypsa.Network()
    n.add("Bus", "BEWAL", carrier="AC")
    with pytest.raises(ValueError, match="no nuclear link"):
        _restart(n, 2040)


def test_disabled_by_default():
    cfg = yaml.safe_load((ROOT / "config/config.walloon.yaml").read_text())
    assert cfg["electricity"]["nuclear_restart"]["enable"] is False
    assert restart_options(cfg) == {}
    t1 = cfg["electricity"]["nuclear_restart"]["plants"]["Tihange 1"]
    assert t1 == {"node": "BEWAL", "p_nom_e": 962, "from_year": 2035,
                  "cost_key": "nuclear retrofit"}
    on = {"electricity": {"nuclear_restart": {"enable": True, "plants": TIHANGE_1}}}
    assert restart_options(on) == TIHANGE_1
