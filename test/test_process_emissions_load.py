# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""BEWAL process-emissions load carries the TIMES **gross** fossil process CO2.

Item 12 of ``docs/temporary_improvement_plans.md``, corrected by B4. The PyPSA
Load is the injection onto the process-emissions bus, *upstream* of
``process emissions CC``. TIMES splits the same quantity in two: ``INDCO2P``
(``VAR_Comnet``) is what reaches the atmosphere and ``INDCO2c`` (``VAR_FOut``
of the CC process variants, consumed by ``STORAGEMININD``) is what is captured.
Loading only ``INDCO2P`` books TIMES's capture twice — once by leaving it out of
the inventory and again through item 9's capture floor — and left 2040 with
357 kt of process CO2 against a 5 077 kt capture floor, which no combination of
Walloon industrial gas and biomass can meet. Values here are
``INDCO2P + INDCO2c``; biogenic ``INDCO2b`` stays off this bus.
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
# Gross = INDCO2P + INDCO2c (kt). 2025 is the 2025 column, not 2021; no CC
# process runs before 2035, so gross equals emitted in 2025 and 2030.
EXPECTED_KT = {2025: 4411.62, 2030: 3946.10, 2040: 5433.90, 2050: 5108.04}
#: what TIMES leaves in the atmosphere — must NOT be what the Load carries
EMITTED_ONLY_KT = {2025: 4411.62, 2030: 3946.10, 2040: 357.01, 2050: 281.64}
#: STORAGEMININD (item 9). The cross-check that the Load can feed the floor
#: lives in test_industry_cc_floor.py, which reads both CSVs.
CAPTURED_KT = {2040: 5076.88, 2050: 4826.40}


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
    assert EXPECTED_KT[2025] != pytest.approx(4417.22)  # not the 2021 row


def test_load_is_gross_not_the_atmosphere_residual():
    """B4: the 2040/2050 rows must not be TIMES's post-capture emissions."""
    rows = _csv_rows()
    bewal = rows[rows["bus"] == "BEWAL"]
    for year in (2040, 2050):
        val = float(bewal.loc[bewal["year"].astype(int) == year, "value"].iloc[0])
        assert val != pytest.approx(EMITTED_ONLY_KT[year]), (
            f"{year} load is TIMES's atmosphere residual, not the gross "
            "inventory the PyPSA bus needs (B4)"
        )
        assert val == pytest.approx(
            EMITTED_ONLY_KT[year] + CAPTURED_KT[year], abs=0.02
        )



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
        "BEWAL,process emissions,p_set,5108.04,kt/year,2050,TIMES,item 12,\n"
    )
    n = _network()
    update_BEWAL_potentials(n, 2050, walloon_potentials=str(csv))
    nhours = float(n.snapshot_weightings["objective"].sum())
    annual_kt = -float(n.loads.at["BEWAL process emissions", "p_set"]) * nhours / 1e3
    assert annual_kt == pytest.approx(EXPECTED_KT[2050])
