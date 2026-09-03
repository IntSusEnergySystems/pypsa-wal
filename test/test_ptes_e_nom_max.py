# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Urban-central water pits get a finite e_nom_max from DH demand (item 16)."""

from __future__ import annotations

import numpy as np
import pypsa
import pytest

from scripts.walloon_scripts.ptes_bounds import (
    apply_ptes_fleet_cap,
    ptes_store_e_nom_max,
)


def _network() -> pypsa.Network:
    n = pypsa.Network()
    n.set_snapshots(range(4))
    n.snapshot_weightings["generators"] = 2190.0
    n.snapshot_weightings["objective"] = 2190.0
    n.add("Carrier", "urban central heat")
    n.add("Bus", "BEWAL urban central heat", carrier="urban central heat")
    n.add(
        "Load",
        "BEWAL urban central heat",
        bus="BEWAL urban central heat",
        carrier="urban central heat",
        p_set=1.0,  # MW_th, 8760 MWh/a
    )
    return n


def test_four_weeks_is_a_finite_fraction_of_annual_demand():
    n = _network()
    cap = ptes_store_e_nom_max(n, ["BEWAL"], weeks=4)
    assert cap["BEWAL"] == pytest.approx(8760.0 * 4 / 52)
    assert np.isfinite(cap["BEWAL"])


def test_missing_or_nonpositive_weeks_leave_the_store_unbounded():
    n = _network()
    for weeks in (None, 0, -1, np.inf):
        cap = ptes_store_e_nom_max(n, ["BEWAL"], weeks=weeks)
        assert cap["BEWAL"] == np.inf


def test_node_without_heat_load_stays_unbounded():
    n = _network()
    cap = ptes_store_e_nom_max(n, ["BEVLG"], weeks=4)
    assert cap["BEVLG"] == np.inf


def _network_with_vintages() -> pypsa.Network:
    """One inherited (non-extendable) vintage plus this horizon's Store."""
    n = _network()
    n.add("Carrier", "urban central water pits")
    n.add(
        "Bus",
        "BEWAL urban central water pits",
        carrier="urban central water pits",
        location="BEWAL",
    )
    n.add(
        "Store",
        "BEWAL urban central water pits-2025",
        bus="BEWAL urban central water pits",
        carrier="urban central water pits",
        e_nom=400.0,
        e_nom_extendable=False,
    )
    n.add(
        "Store",
        "BEWAL urban central water pits-2030",
        bus="BEWAL urban central water pits",
        carrier="urban central water pits",
        e_nom_extendable=True,
        e_nom_max=8760.0 * 4 / 52,  # what prepare_sector_network wrote
    )
    return n


def test_fleet_cap_subtracts_inherited_vintages():
    """B9: four weeks is a ceiling on the fleet, not on every vintage."""
    n = _network_with_vintages()
    apply_ptes_fleet_cap(n, weeks=4)
    ceiling = 8760.0 * 4 / 52
    new = float(n.stores.at["BEWAL urban central water pits-2030", "e_nom_max"])
    inherited = float(n.stores.at["BEWAL urban central water pits-2025", "e_nom"])
    assert new == pytest.approx(ceiling - inherited)
    assert new + inherited == pytest.approx(ceiling)


def test_fleet_cap_never_goes_negative():
    n = _network_with_vintages()
    n.stores.loc["BEWAL urban central water pits-2025", "e_nom"] = 10_000.0
    apply_ptes_fleet_cap(n, weeks=4)
    assert float(n.stores.at["BEWAL urban central water pits-2030", "e_nom_max"]) == 0.0


def test_fleet_cap_is_a_noop_without_a_week_count():
    n = _network_with_vintages()
    before = float(n.stores.at["BEWAL urban central water pits-2030", "e_nom_max"])
    apply_ptes_fleet_cap(n, weeks=None)
    assert float(n.stores.at["BEWAL urban central water pits-2030", "e_nom_max"]) == before
