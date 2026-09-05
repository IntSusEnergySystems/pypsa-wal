# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""The Valbiom domestic potential is a total, not a per-generator allowance.

PyPSA-Eur splits Walloon solid biomass across a sustainable and an
unsustainable generator. ``update_BEWAL_potentials`` wrote the remainder
(``potential - upstream``) onto the unsustainable one and then overwrote the
sustainable one with the *full* potential, so BEWAL entered the solve with
``2 * potential - upstream``: 12.0 TWh in 2025 (upstream 0) and 9.18 TWh in
2030 (upstream 2.82) against the 6.0 TWh Valbiom row. F8 of
``docs/logs/2026-09-04_scen_demande_haute_2010_1h_v2.md``.

The same block also grew the Europe-wide ``unsustainable biomass limit`` by
the new remainder without removing BEWAL's previous contribution.
"""

from __future__ import annotations

import pandas as pd
import pypsa
import pytest

from scripts.walloon_scripts.BEWAL_potentials import update_BEWAL_potentials

VALBIOM_GWH = 6000.0  # data/walloon/custom_potentials.csv, all horizons


def _potentials_file(tmp_path, year, value=VALBIOM_GWH):
    path = tmp_path / "custom_potentials.csv"
    pd.DataFrame(
        [
            {
                "bus": "BEWAL",
                "technology": "solid biomass",
                "parameter": "p_nom",
                "value": value,
                "unit": "GWh/an",
                "year": year,
                "source": "Valbiom",
                "further_description": "",
                "year_currency": "",
            }
        ]
    ).to_csv(path, index=False)
    return str(path)


def _network(upstream_sustainable_mwh, upstream_unsustainable_mwh, eu_limit_mwh):
    """BEWAL sustainable + unsustainable solid biomass, plus the EU limit."""
    n = pypsa.Network()
    n.add("Carrier", ["solid biomass", "unsustainable solid biomass"])
    n.add("Bus", "BEWAL solid biomass", carrier="solid biomass", country="BE")
    n.add(
        "Generator",
        "BEWAL solid biomass",
        bus="BEWAL solid biomass",
        carrier="solid biomass",
        p_nom=upstream_sustainable_mwh,
        e_sum_max=upstream_sustainable_mwh,
    )
    n.add(
        "Generator",
        "BEWAL unsustainable solid biomass",
        bus="BEWAL solid biomass",
        carrier="unsustainable solid biomass",
        p_nom=upstream_unsustainable_mwh,
        e_sum_max=upstream_unsustainable_mwh,
    )
    n.add(
        "GlobalConstraint",
        "unsustainable biomass limit",
        sense="<=",
        type="operational_limit",
        constant=eu_limit_mwh,
    )
    return n


def _bewal_total(n):
    idx = ["BEWAL solid biomass", "BEWAL unsustainable solid biomass"]
    return float(n.generators.loc[idx, "e_sum_max"].sum())


@pytest.mark.parametrize(
    "upstream_sustainable",
    [0.0, 2_824_000.0, 6_000_000.0],  # 2025, 2030, and the exactly-equal case
)
def test_split_sums_to_the_valbiom_potential(tmp_path, upstream_sustainable):
    upstream_unsustainable = 1_000_000.0
    n = _network(upstream_sustainable, upstream_unsustainable, 50_000_000.0)
    update_BEWAL_potentials(n, 2030, _potentials_file(tmp_path, 2030))

    assert _bewal_total(n) == pytest.approx(VALBIOM_GWH * 1000)
    # the sustainable generator keeps the upstream split, never the total
    assert n.generators.at["BEWAL solid biomass", "e_sum_max"] == pytest.approx(
        upstream_sustainable
    )
    assert n.generators.at[
        "BEWAL unsustainable solid biomass", "e_sum_max"
    ] == pytest.approx(VALBIOM_GWH * 1000 - upstream_sustainable)


def test_eu_unsustainable_limit_swaps_the_bewal_share(tmp_path):
    n = _network(2_824_000.0, 1_000_000.0, 50_000_000.0)
    update_BEWAL_potentials(n, 2030, _potentials_file(tmp_path, 2030))

    remainder = VALBIOM_GWH * 1000 - 2_824_000.0
    assert n.global_constraints.at[
        "unsustainable biomass limit", "constant"
    ] == pytest.approx(50_000_000.0 - 1_000_000.0 + remainder)


def test_upstream_above_the_potential_zeroes_the_unsustainable_leg(tmp_path):
    """The `elif` branch: Valbiom is below PyPSA-Eur, so it caps the total."""
    n = _network(9_000_000.0, 1_000_000.0, 50_000_000.0)
    update_BEWAL_potentials(n, 2030, _potentials_file(tmp_path, 2030))

    assert n.generators.at[
        "BEWAL unsustainable solid biomass", "e_sum_max"
    ] == pytest.approx(0.0)
    assert _bewal_total(n) == pytest.approx(VALBIOM_GWH * 1000)
    assert n.global_constraints.at[
        "unsustainable biomass limit", "constant"
    ] == pytest.approx(49_000_000.0)


def test_transported_pellets_are_not_part_of_the_domestic_potential(tmp_path):
    """The pellet allowance lives on its own generator and must stay there."""
    n = _network(0.0, 1_000_000.0, 50_000_000.0)
    n.add(
        "Generator",
        "BEWAL solid biomass transported",
        bus="BEWAL solid biomass",
        carrier="solid biomass",
        p_nom=10_000.0,
        e_sum_max=2_250_000.0,
    )
    update_BEWAL_potentials(n, 2030, _potentials_file(tmp_path, 2030))

    assert n.generators.at[
        "BEWAL solid biomass transported", "e_sum_max"
    ] == pytest.approx(2_250_000.0)
    assert _bewal_total(n) == pytest.approx(VALBIOM_GWH * 1000)
