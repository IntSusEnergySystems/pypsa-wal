# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""`scen_noccsccgt`: no carbon capture on Walloon gas-fired plants.

Decided with the cabinet on 2026-09-24 and confirmed on 2026-09-29: industrial
capture is kept, capture on gas power plants (existing and new) is not
allowed. TIMES-WAL drops the CCGT CCS retrofit (E12/E13) and the new
post-combustion CCGT. The PyPSA side is two `potential:BEWAL:<carrier>:p_nom_max`
rows per horizon in `config/scenarios/scen_noccsccgt.csv`, applied by
`update_BEWAL_potentials` to the new-build vintage of each horizon.

Both failure modes here complete a solve and are quietly wrong: a carrier the
potentials branch does not know is skipped with a warning (the cap is never
applied), and a `.loc` assignment on a missing link name appends an all-NaN
link to the network.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pypsa
import pytest
import yaml

from scripts.walloon_scripts.BEWAL_potentials import update_BEWAL_potentials

ROOT = Path(__file__).resolve().parents[1]
WAL = ROOT / "data" / "walloon"
SCENARIOS = ROOT / "config" / "scenarios.walloon.yaml"
GAS_CC = ("CCGT CC", "urban central gas CHP CC")
# Capture that TIMES keeps (STORAGEMININD floor) and the scenario must not touch.
KEPT_CC = ("gas for industry CC", "process emissions CC", "SMR CC",
           "solid biomass for industry CC", "urban central solid biomass CHP CC")
HEADER = "bus,technology,parameter,value,unit,year,source,further_description,year_currency\n"


def _network(year: int) -> pypsa.Network:
    n = pypsa.Network()
    for bus in ("BEWAL", "BEVLG"):
        n.add("Bus", bus, location=bus)
        for carrier in GAS_CC + KEPT_CC:
            n.add(
                "Link",
                f"{bus} {carrier}-{year}",
                bus0=bus,
                bus1=bus,
                carrier=carrier,
                p_nom_extendable=True,
                p_nom_max=float("inf"),
                efficiency=0.5,
            )
    return n


def test_gas_cc_rows_cap_both_carriers_at_bewal_only(tmp_path: Path):
    csv = tmp_path / "custom_potentials.csv"
    csv.write_text(
        HEADER
        + "".join(f"BEWAL,{c},p_nom_max,0,MW,2040,test,,\n" for c in GAS_CC)
    )
    n = _network(2040)
    update_BEWAL_potentials(n, 2040, walloon_potentials=str(csv))

    for carrier in GAS_CC:
        assert n.links.at[f"BEWAL {carrier}-2040", "p_nom_max"] == 0.0, carrier
        assert n.links.at[f"BEVLG {carrier}-2040", "p_nom_max"] == float("inf")
    for carrier in KEPT_CC:
        assert n.links.at[f"BEWAL {carrier}-2040", "p_nom_max"] == float("inf")


def test_row_for_a_missing_link_does_not_create_one(tmp_path: Path):
    csv = tmp_path / "custom_potentials.csv"
    csv.write_text(HEADER + "BEBRU,CCGT CC,p_nom_max,0,MW,2040,test,,\n")
    n = _network(2040)
    before = n.links.index.copy()
    update_BEWAL_potentials(n, 2040, walloon_potentials=str(csv))

    assert n.links.index.equals(before)
    assert not n.links.bus0.isna().any()


@pytest.fixture(scope="module")
def block() -> dict:
    return (yaml.safe_load(SCENARIOS.read_text()) or {}).get("scen_noccsccgt", {})


def test_scenario_uses_its_own_potentials(block):
    assert block, "scen_noccsccgt missing from config/scenarios.walloon.yaml"
    path = block["electricity"]["walloon_potentials"]
    assert path == "data/walloon/custom_potentials_scen_noccsccgt.csv"


ACTIVE_HORIZONS = [
    int(y)
    for y in yaml.safe_load((ROOT / "config" / "config.walloon.yaml").read_text())[
        "scenario"
    ]["planning_horizons"]
]


def test_override_rows_cover_both_planning_grids():
    """The override itself states 2035/2045 too, so a 5-year write applies them."""
    over = pd.read_csv(ROOT / "config" / "scenarios" / "scen_noccsccgt.csv")
    for carrier in GAS_CC:
        years = set(over[over.technology_name_pypsa == carrier].year.astype(int))
        assert years == {2025, 2030, 2035, 2040, 2045, 2050}, carrier


@pytest.mark.parametrize("year", ACTIVE_HORIZONS)
def test_generated_file_caps_every_horizon(year):
    """Every horizon of the active grid.

    The potentials patcher writes the horizons of the grid it runs for, and
    `--write --all-scenarios` rebuilds each copy from the central file, so the
    2035/2045 rows hold the 5-year values only after a write with
    `config.walloon_5y.yaml` as second config. `--check` with that pair fails
    until then, which is the guard for a 5-year run (docs/five_year_periods.md).
    """
    path = WAL / "custom_potentials_scen_noccsccgt.csv"
    if not path.exists():
        pytest.skip("run build_common_parameters.py --write --all-scenarios")
    df = pd.read_csv(path)
    rows = df[(df.bus == "BEWAL") & (df.parameter == "p_nom_max") & (df.year == year)]
    for carrier in GAS_CC:
        hit = rows[rows.technology == carrier]
        assert len(hit) == 1 and float(hit.value.iloc[0]) == 0.0, (carrier, year)
    assert not df.technology.isin(KEPT_CC).any(), "industrial capture must stay untouched"
