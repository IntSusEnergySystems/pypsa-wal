# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Urban-central water pits get a finite e_nom_max from DH demand (item 16)."""

from __future__ import annotations

import numpy as np
import pypsa
import pytest

from scripts.walloon_scripts.ptes_bounds import ptes_store_e_nom_max


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
