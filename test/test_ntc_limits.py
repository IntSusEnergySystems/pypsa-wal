# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""NTC ceilings cover every Belgian region bus, including Wallonia."""

from pathlib import Path

import pandas as pd
import pypsa
import pytest

from scripts.walloon_scripts.set_NTCs import (
    BE_REGION_BUSES,
    _bus_selector,
    apply_ntc_limits,
    read_ntc_pairs,
)


def _be_network() -> pypsa.Network:
    """Three Belgian nodes, Wallonia's country rewritten to BEWAL as in a solve."""
    n = pypsa.Network()
    n.add("Carrier", ["AC", "DC"])
    n.add("Bus", "BEWAL", carrier="AC", country="BEWAL")
    n.add("Bus", "BEVLG", carrier="AC", country="BE")
    n.add("Bus", "BEBRU", carrier="AC", country="BE")
    n.add("Bus", "FR", carrier="AC", country="FR")
    n.add("Bus", "DE", carrier="AC", country="DE")
    n.add(
        "Line",
        "WAL-FR",
        bus0="BEWAL",
        bus1="FR",
        s_nom=2000,
        s_nom_max=20000,
        s_max_pu=0.7,
        s_nom_extendable=True,
        x=0.1,
        r=0.01,
    )
    n.add(
        "Line",
        "VLG-FR",
        bus0="BEVLG",
        bus1="FR",
        s_nom=2000,
        s_nom_max=20000,
        s_max_pu=0.7,
        s_nom_extendable=True,
        x=0.1,
        r=0.01,
    )
    n.add(
        "Line",
        "WAL-VLG",
        bus0="BEWAL",
        bus1="BEVLG",
        s_nom=5000,
        s_nom_max=25000,
        s_max_pu=0.7,
        s_nom_extendable=True,
        x=0.1,
        r=0.01,
    )
    n.add(
        "Link",
        "WAL-DE",
        bus0="BEWAL",
        bus1="DE",
        carrier="DC",
        p_nom=1000,
        p_nom_max=20000,
        p_nom_extendable=True,
        reversed=False,
    )
    return n


def test_bel_selector_includes_wallonia_when_country_is_rewritten():
    n = _be_network()
    buses = _bus_selector(n, "BEL", {"BEL": "BE"})
    assert set(BE_REGION_BUSES) <= set(buses)


def test_region_code_selects_only_that_bus():
    n = _be_network()
    buses = _bus_selector(n, "BEWAL", {})
    assert list(buses) == ["BEWAL"]


def test_apply_ntc_caps_wallonia_france_and_the_internal_corridor(tmp_path: Path):
    ntc = tmp_path / "ntc.csv"
    ntc.write_text(
        "source_country_code,target_country_code,NTC_MW\n"
        "BEL,FRA,2800\n"
        "FRA,BEL,4300\n"
        "BEWAL,BEVLG,9600\n"
        "BEVLG,BEWAL,9600\n"
    )
    n = _be_network()
    apply_ntc_limits(n, ntc)

    # usable AC cap is the pair average: (2800+4300)/2 = 3550 MW
    usable_fr = (n.lines.loc[["WAL-FR", "VLG-FR"], "s_nom_max"] * 0.7).sum()
    assert usable_fr == pytest.approx(3550.0)
    # Wallonia's branch is in the bucket, not left at 20 GW
    assert n.lines.at["WAL-FR", "s_nom_max"] < 20000

    usable_in = n.lines.at["WAL-VLG", "s_nom_max"] * 0.7
    assert usable_in == pytest.approx(9600.0)


def test_read_ntc_pairs_averages_asymmetric_borders(tmp_path: Path):
    ntc = tmp_path / "ntc.csv"
    ntc.write_text(
        "source_country_code,target_country_code,NTC_MW\n"
        "BEL,FRA,2800\n"
        "FRA,BEL,4300\n"
    )
    pairs = read_ntc_pairs(ntc)
    assert pairs[tuple(sorted(["BEL", "FRA"]))] == pytest.approx(3550.0)
