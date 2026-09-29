# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""The 10 MW capacity threshold must not delete the nuclear new-build seed.

``data/custom_powerplants.csv`` carries a 0.01 MW ``New`` nuclear row per node.
That link is the unbounded investment option. The 2026-09-24 central run
applied ``threshold_capacity: 10`` to it, so 2050 could only keep the Tihange
retrofit (1.03 GW_e) under a floor of 3 GW.
"""

from __future__ import annotations

import pandas as pd
import pypsa
import pytest

from scripts.add_brownfield import add_brownfield
from scripts.add_existing_baseyear import _keep_existing_capacity


def test_baseyear_filter_keeps_the_nuclear_seed_and_drops_other_dust():
    capacity = pd.Series({"BEWAL": 0.01, "BEVLG": 1030.0})
    kept = _keep_existing_capacity(capacity, "nuclear", capacity_threshold=10)
    assert list(kept.index) == ["BEWAL", "BEVLG"]

    other = _keep_existing_capacity(capacity, "CCGT", capacity_threshold=10)
    assert list(other.index) == ["BEVLG"]


def _seed_link(n, name, carrier, p_nom_opt):
    n.add(
        "Link",
        name,
        bus0="uranium",
        bus1="BEWAL",
        carrier=carrier,
        p_nom=p_nom_opt,
        p_nom_opt=p_nom_opt,
        p_nom_extendable=True,
        p_nom_max=float("inf"),
        build_year=2025,
        lifetime=60,
        efficiency=0.326,
    )


def test_brownfield_keeps_an_unbuilt_nuclear_link():
    # Later horizons do not re-run add_existing_baseyear. The fresh network
    # only receives the seed if brownfield copies it.
    n = pypsa.Network()
    n.add("Bus", "BEWAL", carrier="AC")
    n.add("Bus", "uranium", carrier="uranium")
    n_p = pypsa.Network()
    n_p.add("Bus", "BEWAL", carrier="AC")
    n_p.add("Bus", "uranium", carrier="uranium")
    _seed_link(n_p, "BEWAL nuclear-2025", "nuclear", 0.030675)
    _seed_link(n_p, "BEWAL OCGT-2025", "OCGT", 0.05)

    add_brownfield(n, n_p, year=2050, capacity_threshold=10)

    assert "BEWAL nuclear-2025" in n.links.index
    assert n.links.at["BEWAL nuclear-2025", "p_nom"] == pytest.approx(0.030675)
    assert "BEWAL OCGT-2025" not in n.links.index
