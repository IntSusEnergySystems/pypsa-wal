# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Belgian CO₂ stores must carry a documented e_nom_max, not a fillna(0).

``prepare_sector_network`` builds one ``co2 sequestered`` Store per node from
the clustered CO2StoP CSV and then ``reindex(...).fillna(0.0)``. BEWAL / BEVLG
/ BEBRU have no offshore site that clears ``min_size``, so they used to land
at 0 with no record that anyone chose that. Item 2 of
``docs/temporary_improvement_plans.md`` writes the ceiling in
``custom_potentials.csv`` instead. There is no priced Northern-Lights export.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pypsa
import pytest
import yaml

from scripts.walloon_scripts.BEWAL_potentials import (
    apply_co2_store_cap,
    update_BEWAL_potentials,
)

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "walloon" / "custom_potentials.csv"
WALLOON_YAML = ROOT / "config" / "config.walloon.yaml"
HORIZONS = (2025, 2030, 2040, 2050)
BELGIAN = ("BEWAL", "BEVLG", "BEBRU")
# Generic non-zero used only to unit-test apply_co2_store_cap; the CSV is 0.
CAP_T = 7.1e6


def _co2_network() -> pypsa.Network:
    """Three Belgian sequestered stores as ``prepare_sector_network`` names them."""
    n = pypsa.Network()
    n.add("Carrier", "co2 sequestered")
    for bus in BELGIAN:
        n.add(
            "Bus",
            f"{bus} co2 sequestered",
            carrier="co2 sequestered",
            location=bus,
        )
        n.add(
            "Store",
            f"{bus} co2 sequestered",
            bus=f"{bus} co2 sequestered",
            carrier="co2 sequestered",
            e_nom_extendable=True,
            e_nom_max=0.0,  # the fillna(0) that item 2 replaces
        )
    return n


def _csv_caps() -> pd.DataFrame:
    df = pd.read_csv(CSV)
    return df[df["technology"] == "co2 storage"].copy()


def test_csv_states_an_e_nom_max_for_every_belgian_node_and_horizon():
    """The ceiling is a row in the file, not a missing CO2StoP entry."""
    caps = _csv_caps()
    assert not caps.empty
    for bus in BELGIAN:
        years = set(caps.loc[caps["bus"] == bus, "year"].astype(int))
        missing = set(HORIZONS) - years
        assert not missing, f"{bus} has no co2 storage e_nom_max for {sorted(missing)}"


def test_all_belgian_zeros_are_authored():
    """0 is the documented choice: no demonstrated CO2StoP site in Belgium."""
    caps = _csv_caps()
    for bus in BELGIAN:
        rows = caps[(caps["bus"] == bus) & (caps["parameter"] == "e_nom_max")]
        assert not rows.empty, f"{bus} missing co2 storage rows"
        assert not rows["source"].fillna("").eq("").any(), f"{bus} source is empty"
        assert (rows["value"].astype(float) == 0.0).all()
        assert (rows["unit"] == "Mt/a").all()
    wal = caps[caps["bus"] == "BEWAL"]
    assert wal["source"].str.contains("CO2StoP").all()
    assert not wal["source"].str.contains("TIMES").any()


def test_apply_writes_tonnes_on_the_sequestered_store():
    n = _co2_network()
    apply_co2_store_cap(n, "BEWAL", "e_nom_max", CAP_T)
    assert n.stores.at["BEWAL co2 sequestered", "e_nom_max"] == pytest.approx(CAP_T)
    assert n.stores.at["BEVLG co2 sequestered", "e_nom_max"] == 0.0


def test_apply_finds_the_vintaged_brownfield_name():
    """add_existing_baseyear renames the store to ``…-2025`` before the cap."""
    n = _co2_network()
    n.stores.rename(index={"BEWAL co2 sequestered": "BEWAL co2 sequestered-2025"}, inplace=True)
    apply_co2_store_cap(n, "BEWAL", "e_nom_max", CAP_T)
    assert n.stores.at["BEWAL co2 sequestered-2025", "e_nom_max"] == pytest.approx(CAP_T)


def test_csv_override_beats_the_fillna(tmp_path: Path):
    csv = tmp_path / "custom_potentials.csv"
    csv.write_text(
        "bus,technology,parameter,value,unit,year,source,further_description,year_currency\n"
        "BEWAL,co2 storage,e_nom_max,0,Mt/a,2050,CO2StoP,item 2,\n"
        "BEVLG,co2 storage,e_nom_max,0,Mt/a,2050,documented,item 2,\n"
    )
    n = _co2_network()
    n.stores.at["BEWAL co2 sequestered", "e_nom_max"] = 1e9
    n.stores.at["BEBRU co2 sequestered", "e_nom_max"] = 1e9

    update_BEWAL_potentials(n, 2050, walloon_potentials=str(csv))

    assert n.stores.at["BEWAL co2 sequestered", "e_nom_max"] == pytest.approx(0.0)
    assert n.stores.at["BEVLG co2 sequestered", "e_nom_max"] == 0.0
    assert n.stores.at["BEBRU co2 sequestered", "e_nom_max"] == 1e9  # no row → untouched


def test_zero_cap_wipes_inherited_brownfield_vintages():
    """A documented 0 is a fleet ban, not a residual on the new vintage only."""
    n = _co2_network()
    n.stores.rename(index={"BEWAL co2 sequestered": "BEWAL co2 sequestered-2025"}, inplace=True)
    n.stores.at["BEWAL co2 sequestered-2025", "e_nom_extendable"] = False
    n.stores.at["BEWAL co2 sequestered-2025", "e_nom"] = 7.1e6
    n.stores.at["BEWAL co2 sequestered-2025", "e_nom_max"] = 7.1e6
    n.add(
        "Store",
        "BEWAL co2 sequestered-2030",
        bus="BEWAL co2 sequestered",
        carrier="co2 sequestered",
        e_nom_extendable=True,
        e_nom_max=1e9,
    )
    apply_co2_store_cap(n, "BEWAL", "e_nom_max", 0.0)
    assert n.stores.at["BEWAL co2 sequestered-2025", "e_nom"] == 0.0
    assert n.stores.at["BEWAL co2 sequestered-2025", "e_nom_max"] == 0.0
    assert n.stores.at["BEWAL co2 sequestered-2030", "e_nom_max"] == 0.0


def test_ceiling_pulls_down_an_inherited_floor():
    n = _co2_network()
    n.stores.at["BEWAL co2 sequestered", "e_nom"] = 20e6
    n.stores.at["BEWAL co2 sequestered", "e_nom_min"] = 20e6

    apply_co2_store_cap(n, "BEWAL", "e_nom_max", CAP_T)

    assert n.stores.at["BEWAL co2 sequestered", "e_nom_min"] == pytest.approx(CAP_T)
    assert n.stores.at["BEWAL co2 sequestered", "e_nom"] == pytest.approx(CAP_T)


def test_fleet_cap_leaves_residual_for_the_new_vintage():
    n = _co2_network()
    n.stores.rename(index={"BEWAL co2 sequestered": "BEWAL co2 sequestered-2025"}, inplace=True)
    n.stores.at["BEWAL co2 sequestered-2025", "e_nom_extendable"] = False
    n.stores.at["BEWAL co2 sequestered-2025", "e_nom"] = 2.0e6
    n.add(
        "Store",
        "BEWAL co2 sequestered-2030",
        bus="BEWAL co2 sequestered",
        carrier="co2 sequestered",
        e_nom_extendable=True,
        e_nom_max=0.0,
    )
    apply_co2_store_cap(n, "BEWAL", "e_nom_max", CAP_T)
    assert n.stores.at["BEWAL co2 sequestered-2030", "e_nom_max"] == pytest.approx(CAP_T - 2.0e6)
    assert n.stores.at["BEWAL co2 sequestered-2025", "e_nom"] == pytest.approx(2.0e6)


def test_missing_store_warns_instead_of_raising(caplog):
    n = _co2_network()
    n.remove("Store", "BEWAL co2 sequestered")
    apply_co2_store_cap(n, "BEWAL", "e_nom_max", CAP_T)
    assert "No co2 sequestered Store at bus BEWAL" in caplog.text


def test_geology_ramp_is_back_in_the_walloon_overlay():
    """The pooled EU scalar must not be the long-run limiter (item 2 / 816be537)."""
    cfg = yaml.safe_load(WALLOON_YAML.read_text())
    seq = cfg["sector"]["co2_sequestration_potential"]
    assert seq[2025] == 0
    assert seq[2030] == 60
    assert seq[2040] == 1000
    assert seq[2050] == 1000
    assert cfg["sector"]["regional_co2_sequestration_potential"]["max_size"] == 2.5
