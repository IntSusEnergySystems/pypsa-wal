# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Utility battery p_nom_min floors: master CSV → custom_potentials → network."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pypsa

from scripts.build_common_parameters import (
    POTENTIALS_FILE,
    collect_targets,
    load_master,
    patch_potentials,
    planning_horizons,
)
from scripts.walloon_scripts.BEWAL_potentials import (
    UTILITY_BATTERY_HOURS,
    apply_battery_p_nom_min,
    update_BEWAL_potentials,
)

# Floors authored in docs/belgium-batteries-20260818.md (MW, AC).
EXPECTED = {
    ("BEWAL", "battery", "p_nom_min"): {2025: 286, 2030: 410, 2040: 410, 2050: 410},
    ("BEVLG", "battery", "p_nom_min"): {2025: 250, 2030: 1860, 2040: 1860, 2050: 1860},
    ("BEBRU", "battery", "p_nom_min"): {2025: 0, 2030: 0, 2040: 0, 2050: 0},
}


def _toy_battery_network(*buses: str, year: int | None = None) -> pypsa.Network:
    n = pypsa.Network()
    suffix = f"-{year}" if year is not None else ""
    for bus in buses:
        n.add("Bus", bus, carrier="AC")
        n.add("Bus", f"{bus} battery", carrier="battery")
        n.add(
            "Store",
            f"{bus} battery{suffix}",
            bus=f"{bus} battery",
            carrier="battery",
            e_nom_extendable=True,
            e_nom=0.0,
            e_nom_min=0.0,
        )
        n.add(
            "Link",
            f"{bus} battery charger{suffix}",
            bus0=bus,
            bus1=f"{bus} battery",
            carrier="battery charger",
            p_nom_extendable=True,
            p_nom=0.0,
            p_nom_min=0.0,
            efficiency=0.98,
        )
        n.add(
            "Link",
            f"{bus} battery discharger{suffix}",
            bus0=f"{bus} battery",
            bus1=bus,
            carrier="battery discharger",
            p_nom_extendable=True,
            p_nom=0.0,
            p_nom_min=0.0,
            efficiency=0.98,
        )
        n.add(
            "Link",
            f"{bus} home battery charger",
            bus0=bus,
            bus1=bus,
            carrier="home battery charger",
            p_nom_extendable=True,
            p_nom=0.0,
            p_nom_min=0.0,
        )
    return n


def test_master_csv_battery_anchors_expand():
    targets = collect_targets(load_master(), "potential", planning_horizons(), nparts=3)
    for key, values in EXPECTED.items():
        assert key in targets, key
        got = {int(y): v for y, v in targets[key].values.items()}
        assert got == values, key
        assert set(targets[key].anchors) == {2025, 2030}


def test_custom_potentials_in_sync():
    patch = patch_potentials(load_master(), planning_horizons(), dry_run=True)
    assert patch.ok, patch.errors
    battery_changes = [c for c in patch.changes if "battery" in c]
    assert battery_changes == []
    pots = pd.read_csv(POTENTIALS_FILE)
    batt = pots[pots["technology"] == "battery"]
    assert set(batt["bus"]) == {"BEWAL", "BEVLG", "BEBRU"}
    for (bus, _, param), years in EXPECTED.items():
        rows = batt[(batt["bus"] == bus) & (batt["parameter"] == param)]
        got = {int(y): float(v) for y, v in zip(rows["year"], rows["value"])}
        assert got == years, bus


def test_overnight_names_get_the_floor():
    n = _toy_battery_network("BEWAL", "BEVLG", "BEBRU")
    apply_battery_p_nom_min(n, "BEWAL", 286, 2025)
    apply_battery_p_nom_min(n, "BEVLG", 250, 2025)
    apply_battery_p_nom_min(n, "BEBRU", 0, 2025)
    assert n.links.at["BEWAL battery charger", "p_nom_min"] == 286
    assert n.links.at["BEWAL battery discharger", "p_nom_min"] == 286
    assert n.stores.at["BEWAL battery", "e_nom_min"] == 286 * UTILITY_BATTERY_HOURS
    assert n.links.at["BEVLG battery charger", "p_nom_min"] == 250
    assert n.links.at["BEBRU battery charger", "p_nom_min"] == 0
    assert n.links.at["BEWAL home battery charger", "p_nom_min"] == 0


def test_myopic_residual_after_existing_vintage():
    n = _toy_battery_network("BEWAL", year=2025)
    n.links.loc["BEWAL battery charger-2025", ["p_nom", "p_nom_extendable"]] = (286, False)
    n.stores.loc["BEWAL battery-2025", ["e_nom", "e_nom_extendable"]] = (
        286 * UTILITY_BATTERY_HOURS,
        False,
    )
    n.add("Bus", "BEWAL battery extra")
    n.add(
        "Store",
        "BEWAL battery-2030",
        bus="BEWAL battery",
        carrier="battery",
        e_nom_extendable=True,
        e_nom=0.0,
        e_nom_min=0.0,
    )
    n.add(
        "Link",
        "BEWAL battery charger-2030",
        bus0="BEWAL",
        bus1="BEWAL battery",
        carrier="battery charger",
        p_nom_extendable=True,
        p_nom=0.0,
        p_nom_min=0.0,
        efficiency=0.98,
    )
    n.add(
        "Link",
        "BEWAL battery discharger-2030",
        bus0="BEWAL battery",
        bus1="BEWAL",
        carrier="battery discharger",
        p_nom_extendable=True,
        p_nom=0.0,
        p_nom_min=0.0,
        efficiency=0.98,
    )
    apply_battery_p_nom_min(n, "BEWAL", 410, 2030)
    # 410 − 286 already built in 2025
    assert n.links.at["BEWAL battery charger-2030", "p_nom_min"] == 124
    assert n.links.at["BEWAL battery discharger-2030", "p_nom_min"] == 124
    assert n.stores.at["BEWAL battery-2030", "e_nom_min"] == 124 * UTILITY_BATTERY_HOURS
    # existing vintage is left alone
    assert n.links.at["BEWAL battery charger-2025", "p_nom_min"] == 0


def test_update_bewal_potentials_from_csv(tmp_path: Path):
    csv = tmp_path / "custom_potentials.csv"
    csv.write_text(
        "bus,technology,parameter,value,unit,year,source,further_description,year_currency\n"
        "BEWAL,battery,p_nom_min,286,MW,2025,docs/belgium-batteries-20260818.md,,\n"
        "BEVLG,battery,p_nom_min,250,MW,2025,docs/belgium-batteries-20260818.md,,\n"
    )
    n = _toy_battery_network("BEWAL", "BEVLG")
    update_BEWAL_potentials(n, 2025, walloon_potentials=str(csv))
    assert n.links.at["BEWAL battery charger", "p_nom_min"] == 286
    assert n.links.at["BEVLG battery charger", "p_nom_min"] == 250
    assert n.stores.at["BEWAL battery", "e_nom_min"] == 286 * UTILITY_BATTERY_HOURS
