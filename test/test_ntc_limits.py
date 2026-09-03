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
    apply_ntc_floors,
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


def _placeholder_border_network(dc_p_nom: float) -> pypsa.Network:
    """A DE-FR-shaped border: one real AC corridor plus one HVDC candidate.

    `dc_p_nom` is what the candidate carries. In the real clustered network
    `DC2` carries 0 -- it is a TYNDP project placeholder, not an asset.
    """
    n = pypsa.Network()
    n.add("Carrier", ["AC", "DC"])
    n.add("Bus", "DE", carrier="AC", country="DE")
    n.add("Bus", "FR", carrier="AC", country="FR")
    n.add(
        "Line",
        "DE-FR-ac",
        bus0="DE",
        bus1="FR",
        s_nom=6256.0,
        s_nom_max=26256.0,
        s_max_pu=0.7,
        s_nom_extendable=True,
        x=0.1,
        r=0.01,
    )
    n.add(
        "Link",
        "DC2",
        bus0="DE",
        bus1="FR",
        carrier="DC",
        p_nom=dc_p_nom,
        p_nom_max=20000.0 + dc_p_nom,
        p_nom_extendable=True,
        reversed=False,
    )
    return n


def _ntc_file(tmp_path: Path, a: str, b: str, mw: float) -> Path:
    f = tmp_path / f"ntc_{a}_{b}.csv"
    f.write_text(
        "source_country_code,target_country_code,NTC_MW\n"
        f"{a},{b},{mw}\n{b},{a},{mw}\n"
    )
    return f


def test_zero_capacity_dc_candidate_does_not_displace_a_real_ac_corridor(tmp_path):
    """The DE-FR regression: `DC2` carries nothing, so it is not the border.

    Dropping the AC line against a zero-capacity placeholder left DE-FR with no
    base capacity at all -- 4 379 MW usable deleted -- once `apply_ntc_limits`
    stopped writing the NTC into `p_nom`.
    """
    n = _placeholder_border_network(dc_p_nom=0.0)
    apply_ntc_limits(n, _ntc_file(tmp_path, "DEU", "FRA", 4800))

    assert "DE-FR-ac" in n.lines.index, "the real AC corridor was deleted"
    # usable capacity survives, and the ceiling is the NTC
    assert n.lines.at["DE-FR-ac", "s_nom"] * 0.7 == pytest.approx(4379.2)
    assert n.lines.at["DE-FR-ac", "s_nom_max"] * 0.7 == pytest.approx(4800.0)
    # the candidate is held at zero so the border is not counted twice
    assert n.links.at["DC2", "p_nom_max"] == 0.0
    assert n.links.at["DC2", "p_nom_min"] == 0.0


def test_a_dc_link_that_carries_the_border_still_replaces_the_ac_lines(tmp_path):
    """The pre-existing convention must survive for real DC interconnectors."""
    n = _placeholder_border_network(dc_p_nom=1000.0)
    apply_ntc_limits(n, _ntc_file(tmp_path, "DEU", "FRA", 4800))

    assert "DE-FR-ac" not in n.lines.index
    assert n.links.at["DC2", "p_nom_max"] == pytest.approx(4800.0)
    assert n.links.at["DC2", "p_nom"] == pytest.approx(1000.0)


def test_a_dc_only_border_keeps_its_zero_base(tmp_path):
    """DE-GB has no AC line and no asset in service: 0 base, NTC ceiling."""
    n = _placeholder_border_network(dc_p_nom=0.0)
    n.remove("Line", "DE-FR-ac")
    apply_ntc_limits(n, _ntc_file(tmp_path, "DEU", "FRA", 1400))

    assert n.links.at["DC2", "p_nom"] == 0.0
    assert n.links.at["DC2", "p_nom_max"] == pytest.approx(1400.0)


ROOT = Path(__file__).resolve().parents[1]
FLOORS = ROOT / "data" / "walloon" / "ntc_floors.csv"
BOUCLE_USABLE_MW = 9600.0


def _floors_file(tmp_path: Path, year: int, mw: float) -> Path:
    f = tmp_path / f"floors_{year}.csv"
    f.write_text(
        "year,source_country_code,target_country_code,NTC_MIN_MW\n"
        f"{year},BEWAL,BEVLG,{mw}\n{year},BEVLG,BEWAL,{mw}\n"
    )
    return f


def test_2035_ceiling_covers_the_boucle_floor():
    """A 3.6 GW 2035 ceiling would invert min>max once the floor is 9.6 GW."""
    ntc = ROOT / "data" / "walloon" / "ntc_2035.csv"
    pairs = read_ntc_pairs(ntc)
    usable = pairs[tuple(sorted(["BEWAL", "BEVLG"]))]
    assert usable >= BOUCLE_USABLE_MW


def test_floors_file_starts_in_2035_at_9600():
    floors = pd.read_csv(FLOORS, comment="#")
    by_year = floors.groupby("year")["NTC_MIN_MW"].mean()
    assert 2025 not in by_year.index
    assert 2030 not in by_year.index
    for year in (2035, 2040, 2045, 2050):
        assert by_year.loc[year] == pytest.approx(BOUCLE_USABLE_MW)


def test_apply_ntc_floors_sets_usable_s_nom_min(tmp_path: Path):
    n = _be_network()
    apply_ntc_limits(n, _ntc_file(tmp_path, "BEWAL", "BEVLG", 13200))
    apply_ntc_floors(n, _floors_file(tmp_path, 2040, 9600), 2040)

    usable_min = n.lines.at["WAL-VLG", "s_nom_min"] * 0.7
    usable_max = n.lines.at["WAL-VLG", "s_nom_max"] * 0.7
    assert usable_min == pytest.approx(BOUCLE_USABLE_MW)
    assert usable_max == pytest.approx(13200.0)
    assert usable_min <= usable_max


def test_floor_raises_a_too_low_ceiling(tmp_path: Path):
    n = _be_network()
    apply_ntc_limits(n, _ntc_file(tmp_path, "BEWAL", "BEVLG", 3600))
    apply_ntc_floors(n, _floors_file(tmp_path, 2035, 9600), 2035)

    usable_min = n.lines.at["WAL-VLG", "s_nom_min"] * 0.7
    usable_max = n.lines.at["WAL-VLG", "s_nom_max"] * 0.7
    assert usable_min == pytest.approx(BOUCLE_USABLE_MW)
    assert usable_max == pytest.approx(BOUCLE_USABLE_MW)


def test_floor_is_a_noop_before_2035(tmp_path: Path):
    n = _be_network()
    apply_ntc_limits(n, _ntc_file(tmp_path, "BEWAL", "BEVLG", 3600))
    before = n.lines.at["WAL-VLG", "s_nom_min"]
    apply_ntc_floors(n, _floors_file(tmp_path, 2035, 9600), 2030)
    assert n.lines.at["WAL-VLG", "s_nom_min"] == before


def test_floor_survives_transmission_limit_rebuild(tmp_path: Path):
    """carry_forward of the 2030 grid leaves the floor too low; reapply it."""
    from scripts.add_brownfield import carry_forward_built_grid

    n = _be_network()
    apply_ntc_limits(n, _ntc_file(tmp_path, "BEWAL", "BEVLG", 13200))
    apply_ntc_floors(n, _floors_file(tmp_path, 2040, 9600), 2040)

    n_p = n.copy()
    n_p.lines["s_nom_opt"] = 5000.0  # 2030 standing, below the Boucle floor

    n.lines["s_nom_min"] = 0.0  # wiped as set_transmission_limit can do
    carry_forward_built_grid(n, n_p)
    apply_ntc_floors(n, _floors_file(tmp_path, 2040, 9600), 2040)

    usable_min = n.lines.at["WAL-VLG", "s_nom_min"] * 0.7
    usable_max = n.lines.at["WAL-VLG", "s_nom_max"] * 0.7
    assert usable_min == pytest.approx(BOUCLE_USABLE_MW)
    assert usable_min <= usable_max

