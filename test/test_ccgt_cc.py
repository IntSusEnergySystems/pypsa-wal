# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""CCGT with post-combustion capture: parameter algebra and Link wiring."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pypsa
import pytest

from scripts.prepare_sector_network import (
    CCGT_CC_CAPTURE_TECH,
    add_ccgt_cc,
    ccgt_cc_link_params,
)
from scripts.walloon_scripts.calculate_costs import _categorise_main_tech


def _costs(
    *,
    eta: float = 0.60,
    co2: float = 0.198,
    capture_rate: float = 0.95,
    elec: float = 0.02,
    compression: float = 0.075,
    ccgt_capex: float = 100_000.0,
    capture_capex: float = 2_500_000.0,
    vom: float = 5.0,
    lifetime: float = 25.0,
    capture_tech: str = CCGT_CC_CAPTURE_TECH,
) -> pd.DataFrame:
    costs = pd.DataFrame(
        index=["CCGT", "gas", capture_tech],
        columns=[
            "efficiency",
            "capital_cost",
            "VOM",
            "lifetime",
            "CO2 intensity",
            "capture_rate",
            "electricity-input",
            "compression-electricity-input",
        ],
        dtype=float,
    )
    costs.loc["CCGT", ["efficiency", "capital_cost", "VOM", "lifetime"]] = [
        eta,
        ccgt_capex,
        vom,
        lifetime,
    ]
    costs.loc["gas", "CO2 intensity"] = co2
    costs.loc[
        capture_tech,
        [
            "capture_rate",
            "capital_cost",
            "electricity-input",
            "compression-electricity-input",
        ],
    ] = [capture_rate, capture_capex, elec, compression]
    return costs


def test_ccgt_cc_params_match_coal_cc_algebra():
    costs = _costs()
    p = ccgt_cc_link_params(costs)
    elec_penalty = (0.02 + 0.075) * 0.198
    assert p["efficiency"] == pytest.approx(0.60 - elec_penalty)
    assert p["efficiency2"] + p["efficiency3"] == pytest.approx(0.198)
    assert p["efficiency3"] == pytest.approx(0.198 * 0.95)
    assert p["efficiency"] > 0.5
    assert p["capital_cost"] == pytest.approx(0.60 * 100_000.0 + 2_500_000.0 * 0.198)
    assert p["marginal_cost"] == pytest.approx(0.60 * 5.0)
    assert p["lifetime"] == 25.0
    assert p["capture_tech"] == CCGT_CC_CAPTURE_TECH


def test_ccgt_cc_missing_cost_row_raises():
    costs = _costs().drop(index=["gas"])
    with pytest.raises(KeyError, match="CCGT-CC is missing"):
        ccgt_cc_link_params(costs)


def test_add_ccgt_cc_wires_four_buses():
    costs = _costs()
    n = pypsa.Network()
    n.add("Bus", "BEWAL", carrier="AC")
    n.add("Bus", "BEWAL gas", carrier="gas")
    n.add("Bus", "co2 atmosphere", carrier="co2")
    n.add("Bus", "BEWAL co2 stored", carrier="co2 stored")

    spatial = SimpleNamespace()
    spatial.gas = SimpleNamespace(
        df=pd.DataFrame({"nodes": ["BEWAL gas"]}, index=["BEWAL"])
    )
    spatial.co2 = SimpleNamespace(
        df=pd.DataFrame({"nodes": ["BEWAL co2 stored"]}, index=["BEWAL"])
    )
    pop_layout = pd.DataFrame(index=["BEWAL"])

    add_ccgt_cc(n, costs, pop_layout, spatial)

    name = "BEWAL CCGT CC"
    assert name in n.links.index
    link = n.links.loc[name]
    assert link.carrier == "CCGT CC"
    assert link.bus0 == "BEWAL gas"
    assert link.bus1 == "BEWAL"
    assert link.bus2 == "co2 atmosphere"
    assert link.bus3 == "BEWAL co2 stored"
    assert bool(link.p_nom_extendable)
    p = ccgt_cc_link_params(costs)
    assert link.efficiency == pytest.approx(p["efficiency"])
    assert link.efficiency2 == pytest.approx(p["efficiency2"])
    assert link.efficiency3 == pytest.approx(p["efficiency3"])


def test_categorise_does_not_treat_unabated_ccgt_as_ccs():
    assert _categorise_main_tech("CCGT") == "CCGT"
    assert _categorise_main_tech("CCGT CC") == "CCGT+CCS"
    assert _categorise_main_tech("ccgt-ccs") == "CCGT+CCS"
