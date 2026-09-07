# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Brownfield biomass boilers burn their own region's biomass.

The regional biomass potentials — Valbiom/ICEDD for Wallonia, PyPSA-Eur's own
elsewhere — are the whole point of `biomass_spatial: true`. They constrain
nothing if a boiler in one region can draw its fuel from a bus in another, and
the receiving generator (`… solid biomass transported`) carries no annual cap of
its own: only the Europe-wide `biomass limit` bounds it.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scripts.add_existing_baseyear import biomass_fuel_buses
from scripts.prepare_sector_network import define_spatial

NODES = pd.Index(["BEBRU", "BEVLG", "BEWAL", "DE1 0", "FR1 0"])


def _spatial(spatial_biomass: bool):
    return define_spatial(
        NODES,
        {
            "biomass_spatial": spatial_biomass,
            "biomass_transport": False,
            "co2_spatial": False,
            "co2_network": False,
            "gas_network": False,
            "H2_network": False,
            "ammonia": False,
            "methanol": {"regional_methanol_demand": False},
            "regional_oil_demand": False,
            "regional_coal_demand": False,
            "shipping_hydrogen_liquefaction": False,
        },
    )


def test_each_node_burns_its_own_biomass():
    buses = biomass_fuel_buses(_spatial(True), NODES)
    assert list(buses) == [f"{node} solid biomass" for node in NODES]


def test_no_node_is_wired_to_the_alphabetically_first_bus():
    """The regression: `spatial.biomass.nodes[0]` sent everybody to Brussels."""
    buses = biomass_fuel_buses(_spatial(True), NODES)
    assert len(set(buses)) == len(NODES)
    assert list(buses).count("BEBRU solid biomass") == 1


def test_a_subset_of_nodes_keeps_its_own_alignment():
    """`n.add` broadcasts bus0 positionally against `nodes`, so order matters."""
    subset = pd.Index(["BEWAL", "DE1 0"])
    assert list(biomass_fuel_buses(_spatial(True), subset)) == [
        "BEWAL solid biomass",
        "DE1 0 solid biomass",
    ]


def test_without_spatial_biomass_every_node_shares_the_eu_bus():
    buses = biomass_fuel_buses(_spatial(False), NODES)
    assert set(buses) == {"EU solid biomass"}
    assert len(buses) == len(NODES)


def test_an_unknown_node_fails_loudly():
    """A bare KeyError 40 minutes into a prepare is not a useful diagnostic."""
    with pytest.raises(KeyError, match="No biomass bus for"):
        biomass_fuel_buses(_spatial(True), pd.Index(["BEWAL", "ZZ1 0"]))
