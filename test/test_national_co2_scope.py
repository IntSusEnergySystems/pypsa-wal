# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Aviation belongs to the global CO2 cap, not to the national ones.

``kerosene for aviation`` draws from the single ``EU oil`` bus. A large share of
that pool is carbon-neutral Fischer-Tropsch product, but the Fischer-Tropsch
uptake is booked to location ``EU``, which the national attribution drops. The
consumer was therefore charged a fossil emission factor for fuel nobody was
credited with decarbonising.

In the 2050 solve of ``docs/logs/2026-08-25_scen_demande_haute_2010_1h.md`` this
put 2.230 MtCO2 of aviation on Wallonia against a 1.717 Mt cap — 130 % of the
whole budget from one unabatable line item — and priced the marginal tonne at
2 114 EUR. The authoritative trajectory in
``config/input_parameters_for_models.csv`` is defined "hors aviation
internationale", so the charge was never intended.
"""

from __future__ import annotations

import numpy as np
import pypsa

from scripts.prepare_sector_network import determine_emission_sectors
from scripts.solve_network import (
    AVIATION_CARRIER,
    AVIATION_SECTORS,
    national_co2_country,
    national_co2_expression,
)

CO2_INTENSITY_KEROSENE = 0.2571
CO2_INTENSITY_GAS = 0.198


def _toy_network() -> pypsa.Network:
    """One node burning both kerosene (EU pool) and gas (EU pool) for heat."""
    n = pypsa.Network()
    n.add("Carrier", ["AC", "co2", "oil", "gas", "kerosene for aviation", "heat"])
    n.add("Bus", "BEWAL", carrier="AC")
    n.add("Bus", "BEWAL rural heat", carrier="heat")
    n.add("Bus", "BEWAL kerosene for aviation", carrier="kerosene for aviation")
    n.add("Bus", "EU oil", carrier="oil")
    n.add("Bus", "EU gas", carrier="gas")
    n.add("Bus", "co2 atmosphere", carrier="co2")
    n.buses["location"] = [
        "BEWAL",
        "BEWAL",
        "BEWAL",
        "EU",
        "EU",
        "EU",
    ]

    n.add(
        "Link",
        "BEWAL kerosene for aviation",
        bus0="EU oil",
        bus1="BEWAL kerosene for aviation",
        bus2="co2 atmosphere",
        carrier=AVIATION_CARRIER,
        efficiency=1.0,
        efficiency2=CO2_INTENSITY_KEROSENE,
        p_nom_extendable=True,
        capital_cost=1.0,
    )
    n.add(
        "Link",
        "BEWAL rural gas boiler",
        bus0="EU gas",
        bus1="BEWAL rural heat",
        bus2="co2 atmosphere",
        carrier="rural gas boiler",
        efficiency=0.9,
        efficiency2=CO2_INTENSITY_GAS,
        p_nom_extendable=True,
        capital_cost=1.0,
    )
    n.set_snapshots([0, 1])
    n.optimize.create_model(include_objective_constant=False)
    return n


def _link_labels(n: pypsa.Network, name: str) -> np.ndarray:
    return n.model.variables["Link-p"].labels.sel(name=name).values


def test_aviation_is_dropped_from_the_national_expression():
    n = _toy_network()
    expr = national_co2_expression(n)
    used = np.asarray(expr.vars).ravel()

    assert not np.isin(_link_labels(n, "BEWAL kerosene for aviation"), used).any()
    assert np.isin(_link_labels(n, "BEWAL rural gas boiler"), used).all()


def test_attribution_still_reaches_bewal_through_bus1():
    """The exclusion must not come from a broken attribution."""
    n = _toy_network()
    country = national_co2_country(n)
    assert country["BEWAL kerosene for aviation"] == "BEWAL"
    assert country["BEWAL rural gas boiler"] == "BEWAL"


def test_aviation_stays_in_the_global_sector_list():
    """Only the national scope changes; the global CO2Limit keeps aviation."""
    options = {
        "transport": True,
        "heating": True,
        "industry": True,
        "agriculture": True,
    }
    sectors = determine_emission_sectors(options)
    assert "international aviation" in sectors
    assert "domestic aviation" in sectors

    national = [s for s in sectors if s not in AVIATION_SECTORS]
    assert "international aviation" not in national
    assert "domestic aviation" not in national
    # nothing else may be lost
    assert set(sectors) - set(national) == set(AVIATION_SECTORS)
