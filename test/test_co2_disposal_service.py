# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""The TIMES-priced CO₂ disposal route at BEWAL (TIMES-WAL ``CO2STG01``).

Decided 2026-10-04 (docs/logs/2026-10-04_cabinet_batch_20261002_2010_1h.md §3):
Walloon-captured CO₂ may leave through a priced, volume-capped export service,
on top of the endogenous pipeline route. Toy LP: 10 t/h captured in Wallonia,
optionally 10 t/h captured in Flanders and piped through Wallonia, a German
sink at 100 EUR/t and the Walloon route at 64 EUR/t.
"""

from __future__ import annotations

import pandas as pd
import pypsa
import pytest

from scripts.walloon_scripts.BEWAL_potentials import (
    apply_co2_disposal_service,
    update_BEWAL_potentials,
)
from scripts.walloon_scripts.named_pins import add_co2_disposal_own_capture

HOURS = 4380.0  # two snapshots of half a year
ANNUAL_T = 10.0 * 2 * HOURS  # Walloon capture, t/a
ROUTE_PRICE = 64.0
DE_PRICE = 100.0


def _network(flemish: bool = False) -> pypsa.Network:
    n = pypsa.Network()
    n.set_snapshots(range(2))
    for w in ("generators", "objective", "stores"):
        n.snapshot_weightings[w] = HOURS
    n.add("Carrier", ["co2 stored", "co2 sequestered", "CO2 pipeline", "flue", "capture"])
    for node in ("BEWAL", "BEVLG", "DE"):
        n.add("Bus", f"{node} co2 stored", carrier="co2 stored", location=node)
        n.add("Bus", f"{node} flue", carrier="flue", location=node)
    n.add("Bus", "BEWAL co2 sequestered", carrier="co2 sequestered", location="BEWAL")
    # Walloon capture: a link onto `co2 stored` (port 1, positive efficiency).
    n.add("Generator", "BEWAL flue gas", bus="BEWAL flue", p_nom=10.0, p_min_pu=1.0,
          carrier="flue")
    n.add("Link", "BEWAL process emissions CC", bus0="BEWAL flue",
          bus1="BEWAL co2 stored", p_nom=10.0, carrier="capture")
    n.add("Generator", "DE sink", bus="DE co2 stored", p_nom=100.0, p_min_pu=-1.0,
          p_max_pu=0.0, marginal_cost=-DE_PRICE, carrier="co2 stored")
    n.add("Link", "CO2 pipeline BEWAL -> DE", bus0="BEWAL co2 stored",
          bus1="DE co2 stored", p_nom=100.0, p_min_pu=-1.0, carrier="CO2 pipeline")
    # The BEWAL sequestration pair as prepare_sector_network builds it, with the
    # documented Belgian zero on the Store.
    n.add("Link", "BEWAL co2 sequestered", bus0="BEWAL co2 stored",
          bus1="BEWAL co2 sequestered", p_nom_extendable=True, carrier="co2 sequestered")
    n.add("Store", "BEWAL co2 sequestered", bus="BEWAL co2 sequestered",
          e_nom_extendable=True, e_nom_max=0.0, capital_cost=30.0,
          e_cyclic=False, carrier="co2 sequestered")
    if flemish:
        n.add("Generator", "BEVLG flue gas", bus="BEVLG flue", p_nom=10.0,
              p_min_pu=1.0, carrier="flue")
        n.add("Link", "BEVLG process emissions CC", bus0="BEVLG flue",
              bus1="BEVLG co2 stored", p_nom=10.0, carrier="capture")
        n.add("Link", "CO2 pipeline BEVLG -> BEWAL", bus0="BEVLG co2 stored",
              bus1="BEWAL co2 stored", p_nom=100.0, p_min_pu=-1.0,
              carrier="CO2 pipeline")
    return n


def _solve(n, own_capture: bool = True):
    def extra(n, s):
        if own_capture:
            add_co2_disposal_own_capture(n, "BEWAL")

    status, _ = n.optimize(solver_name="highs", extra_functionality=extra)
    assert status == "ok"
    w = n.snapshot_weightings.generators
    route = float((n.links_t.p0["BEWAL co2 sequestered"] * w).sum())
    to_de = float((n.links_t.p0["CO2 pipeline BEWAL -> DE"] * w).sum())
    return route, to_de


def test_closed_route_keeps_the_documented_zero():
    n = _network()
    apply_co2_disposal_service(n, "BEWAL", 0.0, ROUTE_PRICE)
    assert n.stores.at["BEWAL co2 sequestered", "e_nom_max"] == 0.0
    assert n.stores.at["BEWAL co2 sequestered", "capital_cost"] == 30.0
    assert n.links.at["BEWAL co2 sequestered", "marginal_cost"] == 0.0
    route, to_de = _solve(n)
    assert route == pytest.approx(0.0, abs=1e-6)
    assert to_de == pytest.approx(ANNUAL_T, rel=1e-6)


def test_open_route_is_priced_per_tonne_and_capped():
    n = _network()
    apply_co2_disposal_service(n, "BEWAL", ANNUAL_T / 2, ROUTE_PRICE)
    assert n.stores.at["BEWAL co2 sequestered", "capital_cost"] == 0.0
    assert n.links.at["BEWAL co2 sequestered", "marginal_cost"] == ROUTE_PRICE
    route, to_de = _solve(n)
    # Cheaper than Germany, so it fills; the rest still leaves by pipeline.
    assert route == pytest.approx(ANNUAL_T / 2, rel=1e-6)
    assert to_de == pytest.approx(ANNUAL_T / 2, rel=1e-6)
    assert n.objective == pytest.approx(ANNUAL_T / 2 * (ROUTE_PRICE + DE_PRICE), rel=1e-6)


def test_inherited_vintages_count_against_the_ceiling():
    n = _network()
    n.add("Store", "BEWAL co2 sequestered-2040", bus="BEWAL co2 sequestered",
          e_nom=ANNUAL_T / 4, carrier="co2 sequestered", e_cyclic=False)
    apply_co2_disposal_service(n, "BEWAL", ANNUAL_T / 2, ROUTE_PRICE)
    assert n.stores.at["BEWAL co2 sequestered", "e_nom_max"] == pytest.approx(ANNUAL_T / 4)
    route, _ = _solve(n)
    assert route == pytest.approx(ANNUAL_T / 2, rel=1e-6)


def test_flemish_co2_cannot_use_the_walloon_route():
    """Without the row the cheap route would take Flanders' 10 t/h as well."""
    n = _network(flemish=True)
    apply_co2_disposal_service(n, "BEWAL", 4 * ANNUAL_T, ROUTE_PRICE)
    route, to_de = _solve(n, own_capture=False)
    assert route == pytest.approx(2 * ANNUAL_T, rel=1e-6)  # the leak

    n = _network(flemish=True)
    apply_co2_disposal_service(n, "BEWAL", 4 * ANNUAL_T, ROUTE_PRICE)
    route, to_de = _solve(n)
    assert route == pytest.approx(ANNUAL_T, rel=1e-6)
    assert to_de == pytest.approx(ANNUAL_T, rel=1e-6)  # Flanders' tonnes, in transit
    mu = n.global_constraints.at["co2_disposal_own_capture_BEWAL", "mu"]
    assert mu == pytest.approx(-(DE_PRICE - ROUTE_PRICE), rel=1e-6)


def test_no_row_while_the_route_is_closed():
    n = _network(flemish=True)
    _solve(n)
    assert "co2_disposal_own_capture_BEWAL" not in n.global_constraints.index


def test_potentials_rows_open_the_route(tmp_path):
    """kt/a and the two price legs, as the generated potentials files carry them."""
    rows = [
        ("co2 storage", "e_nom_max", "0", "Mt/a"),
        ("co2 disposal service", "e_nom_max", "6000", "ktCO2/year"),
        ("co2 disposal service", "vom_downstream", "58", "EUR2025/tCO2"),
        ("co2 disposal service", "vom_onshore", "13.8", "EUR2025/tCO2"),
    ]
    path = tmp_path / "potentials.csv"
    pd.DataFrame(
        [{"bus": "BEWAL", "technology": t, "parameter": p, "value": v, "unit": u,
          "year": 2040} for t, p, v, u in rows]
    ).to_csv(path, index=False)
    n = _network()
    update_BEWAL_potentials(n, 2040, str(path))
    assert n.stores.at["BEWAL co2 sequestered", "e_nom_max"] == pytest.approx(6e6)
    assert n.links.at["BEWAL co2 sequestered", "marginal_cost"] == pytest.approx(71.8)


def test_a_missing_price_leg_fails_loudly(tmp_path):
    path = tmp_path / "potentials.csv"
    pd.DataFrame(
        [{"bus": "BEWAL", "technology": "co2 disposal service", "parameter": "e_nom_max",
          "value": "6000", "unit": "ktCO2/year", "year": 2040}]
    ).to_csv(path, index=False)
    with pytest.raises(ValueError, match="vom_downstream"):
        update_BEWAL_potentials(_network(), 2040, str(path))
