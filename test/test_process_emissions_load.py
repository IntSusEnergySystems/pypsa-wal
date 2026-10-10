# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""BEWAL process-emissions load carries the TIMES **gross fossil process** CO2.

``docs/ccs_alignment.md`` S11.1 (worklist item 12, corrected by B4, settled
2026-10-10). The PyPSA Load is the injection onto the process-emissions bus,
*upstream* of ``process emissions CC``. TIMES splits the process CO2 in two:
``INDCO2P`` is what reaches the atmosphere, and the CC process variants capture
the rest into ``INDCO2c``. Loading only ``INDCO2P`` left 2040 with 357 kt of
process CO2 against a 5 077 kt capture floor (B4).

``INDCO2c`` is not all process CO2: a kiln or oxy-fuel furnace with capture
also captures its FUEL CO2 and books it as a negative ``INDCO2N``. In PyPSA that
CO2 comes from the industrial fuel demand and is captured by solid biomass /
gas for industry CC, so it must stay off this bus. Until 2026-10-10 it was on
it: 5 434 kt in 2040 instead of 3 875 (3 Sep export), 1.2-1.6 Mt/a of phantom
fossil CO2 from 2035. Values here: ``INDCO2P + INDCO2c - fuel CO2 captured``
of the 2 Oct central (``extract_times_softlink_values.process_emissions_breakdown``).
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
VD = ROOT / "data" / "walloon" / "scen_central_v01_261002_0210.vd"
HORIZONS = (2025, 2030, 2040, 2050)
# Gross process CO2 (kt), 2 Oct central. No CC process runs before 2035, so
# gross equals emitted in 2025 and 2030 (2025 column, not 2021).
EXPECTED_KT = {2025: 4411.62, 2030: 3946.10, 2040: 3875.28, 2050: 3880.12}
#: what TIMES leaves in the atmosphere — must NOT be what the Load carries (B4)
EMITTED_ONLY_KT = {2040: 1112.09, 2050: 353.14}
#: all of INDCO2c, fuel CO2 included — must NOT be added either (2026-10-10)
CAPTURED_ALL_KT = {2040: 4145.3, 2050: 5119.6}


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


def test_load_is_gross_process_co2_only():
    """Neither the atmosphere residual (B4) nor process + fuel CO2 (2026-10-10)."""
    rows = _csv_rows()
    bewal = rows[rows["bus"] == "BEWAL"]
    for year in (2040, 2050):
        val = float(bewal.loc[bewal["year"].astype(int) == year, "value"].iloc[0])
        assert val != pytest.approx(EMITTED_ONLY_KT[year], rel=0.01), (
            f"{year} load is TIMES's atmosphere residual, not the gross inventory (B4)"
        )
        assert val < EMITTED_ONLY_KT[year] + CAPTURED_ALL_KT[year] - 1000, (
            f"{year} load still carries the fuel CO2 the kilns capture: it is "
            "captured in PyPSA by solid biomass / gas for industry CC"
        )


@pytest.mark.skipif(not VD.exists(), reason="central .vd not fetched on this machine")
def test_load_is_the_central_export():
    """The Load must be re-derived when the central export changes."""
    from scripts.walloon_scripts.extract_times_softlink_values import (
        load_vd,
        process_emissions_gross_kt,
    )

    gross = process_emissions_gross_kt(load_vd(VD))
    bewal = _csv_rows()
    bewal = bewal[bewal["bus"] == "BEWAL"]
    for _, row in bewal.iterrows():
        year = int(row["year"])
        assert float(row["value"]) == pytest.approx(gross[year], abs=0.01), (
            f"{year}: custom_potentials.csv has {row['value']} kt, the central "
            f"export gives {gross[year]:.2f}. Re-derive with "
            "extract_times_softlink_values.py <vd> and update the BEWAL rows."
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
        "BEWAL,process emissions,p_set,3880.12,kt/year,2050,TIMES,item 12,\n"
    )
    n = _network()
    update_BEWAL_potentials(n, 2050, walloon_potentials=str(csv))
    nhours = float(n.snapshot_weightings["objective"].sum())
    annual_kt = -float(n.loads.at["BEWAL process emissions", "p_set"]) * nhours / 1e3
    assert annual_kt == pytest.approx(EXPECTED_KT[2050])
