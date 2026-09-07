# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""No carbon capture on power/CHP plants before `sector.power_plant_cc_from_year`.

Decision 2026-09-05: capture fitted to power plants is not planned in the short
term. Industrial capture is a separate question and must survive untouched —
`process emissions CC`, `solid biomass for industry CC`, `gas for industry CC`
and `SMR CC` carry TIMES's STORAGEMININD floor (item 9), so gating them here
would contradict it.

The threshold is a policy assumption, so it lives in
`config/input_parameters_for_models.csv` and is synced into the overlay by
`build_common_parameters.py`. The last test guards that path: a value that never
reaches the model is the failure class this project keeps finding.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pypsa
import pytest
import yaml

from scripts.walloon_scripts.power_plant_cc import (
    POWER_PLANT_CC_CARRIERS,
    disable_power_plant_cc,
)

REPO = Path(__file__).resolve().parents[1]

POWER = ["CCGT CC", "urban central gas CHP CC", "urban central solid biomass CHP CC"]
INDUSTRY = [
    "process emissions CC",
    "solid biomass for industry CC",
    "gas for industry CC",
    "SMR CC",
]


def _network(extendable=True):
    n = pypsa.Network()
    n.add("Bus", "BEWAL")
    for carrier in POWER + INDUSTRY:
        n.add("Carrier", carrier)
        n.add(
            "Link",
            f"BEWAL {carrier}",
            bus0="BEWAL",
            bus1="BEWAL",
            carrier=carrier,
            p_nom_extendable=extendable,
            p_nom_max=5000.0,
        )
    return n


def _cap(n, carrier):
    row = n.links.loc[f"BEWAL {carrier}"]
    return float(row.p_nom_max), bool(row.p_nom_extendable)


def test_power_plant_cc_is_off_before_the_threshold():
    n = _network()
    disable_power_plant_cc(n, 2030, 2040)
    for carrier in POWER:
        assert _cap(n, carrier) == (0.0, False), carrier


def test_industrial_cc_is_never_touched():
    n = _network()
    disable_power_plant_cc(n, 2030, 2040)
    for carrier in INDUSTRY:
        assert _cap(n, carrier) == (5000.0, True), carrier


@pytest.mark.parametrize("year", [2040, 2050])
def test_available_from_the_threshold_on(year):
    n = _network()
    disable_power_plant_cc(n, year, 2040)
    for carrier in POWER + INDUSTRY:
        assert _cap(n, carrier) == (5000.0, True), carrier


def test_none_keeps_upstream_behaviour():
    n = _network()
    disable_power_plant_cc(n, 2025, None)
    for carrier in POWER + INDUSTRY:
        assert _cap(n, carrier) == (5000.0, True), carrier


def test_inherited_vintages_are_left_alone():
    """A standing plant is a fact; clipping it here would rewrite brownfield."""
    n = _network(extendable=False)
    n.links["p_nom"] = 900.0
    disable_power_plant_cc(n, 2030, 2040)
    for carrier in POWER:
        assert float(n.links.at[f"BEWAL {carrier}", "p_nom"]) == 900.0, carrier


def test_carrier_list_excludes_industrial_capture():
    for carrier in INDUSTRY:
        assert carrier not in POWER_PLANT_CC_CARRIERS


def _csv_row():
    """The single `config:sector.power_plant_cc_from_year` row of the master CSV."""
    raw = (REPO / "config/input_parameters_for_models.csv").read_text(encoding="utf-8")
    rows = list(csv.reader(io.StringIO(raw, newline="")))
    idx = {h: i for i, h in enumerate(rows[0])}
    hits = [
        r
        for r in rows[1:]
        if r[idx["pypsa_wal_target"]] == "config:sector.power_plant_cc_from_year"
    ]
    assert len(hits) == 1, "expected exactly one row for this target"
    return hits[0], idx


def _overlay_value():
    cfg = yaml.safe_load((REPO / "config/config.walloon.yaml").read_text())
    return cfg["sector"].get("power_plant_cc_from_year")


def test_shipped_default_is_off():
    """The option must be committed OFF: it is a policy switch, not a fix.

    Turning it on changes the LP, so it may only be enabled deliberately —
    flip the CSV row to `status: active` and run `--write`.
    """
    assert _overlay_value() is None


def test_csv_row_and_overlay_agree():
    """Whatever the CSV says must be what the overlay says — in both states.

    Active: the overlay carries the CSV value. Not active: the sync does not
    manage the key, so the overlay must not be enabling it behind the CSV's
    back. A row that says one thing while the model does another is the
    failure class this project keeps finding.
    """
    row, idx = _csv_row()
    value = _overlay_value()
    if row[idx["status"]] == "active":
        assert value == int(float(row[idx["value"]]))
    else:
        assert value is None
