# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""BEWAL process-emissions load follows the TIMES VAR_Comnet fossil totals.

Item 12 of ``docs/temporary_improvement_plans.md``: override the PyPSA
``process emissions`` Load (gross production on that bus), not a coefficient
and not capture (item 9). Values are fossil ``INDCO2`` only.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pypsa
import pytest

from scripts.walloon_scripts.BEWAL_potentials import (
    apply_process_emission_load,
    update_BEWAL_potentials,
)

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "walloon" / "custom_potentials.csv"
HORIZONS = (2025, 2030, 2040, 2050)
# Annick / VAR_Comnet fossil totals (kt). 2025 is the 2025 column, not 2021.
EXPECTED_KT = {2025: 4411.62, 2030: 3946.10, 2040: 357.01, 2050: 281.64}


def _network() -> pypsa.Network:
    n = pypsa.Network()
    n.set_snapshots(range(4))
    n.snapshot_weightings["objective"] = 2190.0  # 8760 / 4
    n.add("Carrier", "process emissions")
    n.add(
        "Bus",
        "BEWAL process emissions",
        carrier="process emissions",
        location="BEWAL",
    )
    n.add(
        "Load",
        "BEWAL process emissions",
        bus="BEWAL process emissions",
        carrier="process emissions",
        p_set=-1.0,
    )
    return n


def _csv_rows() -> pd.DataFrame:
    df = pd.read_csv(CSV)
    return df[df["technology"] == "process emissions"].copy()


def test_csv_has_fossil_totals_for_every_horizon():
    rows = _csv_rows()
    assert not rows.empty
    bewal = rows[rows["bus"] == "BEWAL"]
    years = set(bewal["year"].astype(int))
    assert set(HORIZONS) <= years
    for year, kt in EXPECTED_KT.items():
        val = float(bewal.loc[bewal["year"].astype(int) == year, "value"].iloc[0])
        assert val == pytest.approx(kt)
    assert EXPECTED_KT[2025] != pytest.approx(4417.22)


def test_apply_sets_annual_volume_to_the_times_figure():
    n = _network()
    apply_process_emission_load(n, "BEWAL", EXPECTED_KT[2050])
    nhours = float(n.snapshot_weightings["objective"].sum())
    annual_t = -float(n.loads.at["BEWAL process emissions", "p_set"]) * nhours
    assert annual_t == pytest.approx(EXPECTED_KT[2050] * 1e3)


def test_update_bewal_potentials_writes_the_load(tmp_path):
    csv = tmp_path / "custom_potentials.csv"
    csv.write_text(
        "bus,technology,parameter,value,unit,year,source,further_description,year_currency\n"
        "BEWAL,process emissions,p_set,281.64,kt/year,2050,Annick,item 12,\n"
    )
    n = _network()
    update_BEWAL_potentials(n, 2050, walloon_potentials=str(csv))
    nhours = float(n.snapshot_weightings["objective"].sum())
    annual_kt = -float(n.loads.at["BEWAL process emissions", "p_set"]) * nhours / 1e3
    assert annual_kt == pytest.approx(EXPECTED_KT[2050])
