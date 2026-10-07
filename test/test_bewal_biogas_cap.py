# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""The Walloon biogas row caps TOTAL biogas, in every horizon (2026-10-06).

ICEDD (A. Lempereur, 5 Oct 2026): TIMES-WAL's bound on new digesters
(``BNDACT UP BWBIOGAZ100``) had only been read for 2040 and 2050; it now holds
from 2025, and it excludes the existing biogas and landfill gas of the base year
("environ 2.7 PJ en plus"). The PyPSA row is that bound plus TIMES's existing
production, and it bounds the sustainable *and* the forced "unsustainable"
generator together. Until then the 2025/2030 cap was the loose Valbiom 8.3 TWh,
the 4 Oct central burnt all of it in 2030 (TIMES: 2.1 TWh), and the forced
generator came on top. docs/biogas.md §3.1.
"""

from __future__ import annotations

import pandas as pd
import pypsa
import pytest

import scripts.build_common_parameters as bcp
from scripts.walloon_scripts.BEWAL_potentials import update_BEWAL_potentials

GWH_PER_PJ = 1e3 / 3.6
# BNDACT UP BWBIOGAZ100 (ICEDD message), MINBIOGAS, MINCETGAS in
# scen_central_v01_261002_0210.vd, PJ.
TIMES = {
    2025: (1.00, 2.23223809195052, 0.435466666666667),
    2030: (5.15, 2.23223809195052, 0.3408),
    2035: (9.62, 2.23223809195052, 0.2556),
    2040: (14.40, 2.23223809195052, 0.1704),
    2050: (22.64, 2.23223809195052, 0.0852),
}


def _potentials_file(tmp_path, year, gwh):
    path = tmp_path / "custom_potentials.csv"
    pd.DataFrame(
        [
            {
                "bus": "BEWAL",
                "technology": "biogas",
                "parameter": "p_nom",
                "value": gwh,
                "unit": "GWh/an",
                "year": year,
                "source": "fixture",
                "further_description": "",
                "year_currency": "",
            }
        ]
    ).to_csv(path, index=False)
    return str(path)


def _network(upstream_mwh, forced_mwh=None):
    """BEWAL biogas bus with the optional and, if given, the forced generator."""
    n = pypsa.Network()
    n.add("Carrier", ["biogas", "unsustainable biogas"])
    n.add("Bus", "BEWAL biogas", carrier="biogas")
    n.add(
        "Generator",
        "BEWAL biogas",
        bus="BEWAL biogas",
        carrier="biogas",
        p_nom=upstream_mwh,
        e_sum_max=upstream_mwh,
    )
    if forced_mwh is not None:
        n.add(
            "Generator",
            "BEWAL biogas unsustainable",
            bus="BEWAL biogas",
            carrier="unsustainable biogas",
            p_nom=forced_mwh,
            e_sum_min=forced_mwh,
            e_sum_max=forced_mwh,
        )
    return n


def _total(n):
    return float(n.generators.loc[n.generators.bus == "BEWAL biogas", "e_sum_max"].sum())


def test_forced_volume_counts_against_the_cap(tmp_path):
    """2030: 0.93 TWh forced + the rest optional = the 2.145 TWh cap."""
    n = _network(upstream_mwh=2_360_000.0, forced_mwh=927_000.0)
    update_BEWAL_potentials(n, 2030, _potentials_file(tmp_path, 2030, 2145))

    assert _total(n) == pytest.approx(2_145_000.0)
    assert n.generators.at["BEWAL biogas", "e_sum_max"] == pytest.approx(1_218_000.0)
    forced = n.generators.loc["BEWAL biogas unsustainable"]
    assert forced.e_sum_min == forced.e_sum_max == pytest.approx(927_000.0)


def test_forced_volume_above_the_cap_is_clipped(tmp_path):
    """2025: the biomass key gives Wallonia 1.45 TWh, the cap is 1.02 TWh."""
    n = _network(upstream_mwh=0.0, forced_mwh=1_452_000.0)
    update_BEWAL_potentials(n, 2025, _potentials_file(tmp_path, 2025, 1019))

    assert _total(n) == pytest.approx(1_019_000.0)
    assert n.generators.at["BEWAL biogas", "e_sum_max"] == pytest.approx(0.0)
    forced = n.generators.loc["BEWAL biogas unsustainable"]
    assert forced.e_sum_min == pytest.approx(1_019_000.0)
    assert forced.e_sum_max == pytest.approx(1_019_000.0)
    assert forced.p_nom == pytest.approx(1_019_000.0)


def test_without_a_forced_generator_the_cap_is_the_optional_one(tmp_path):
    """From 2040 the phase-out leaves no forced generator in the network."""
    n = _network(upstream_mwh=7_000_000.0)
    update_BEWAL_potentials(n, 2040, _potentials_file(tmp_path, 2040, 4667))

    assert n.generators.at["BEWAL biogas", "e_sum_max"] == pytest.approx(4_667_000.0)
    assert n.generators.at["BEWAL biogas", "p_nom"] == pytest.approx(4_667_000.0)


def test_shipped_cap_is_the_times_bound_plus_existing_biogas():
    """Master CSV anchors = BNDACT + MINBIOGAS + MINCETGAS, every horizon."""
    tgt = bcp.collect_targets(
        bcp.load_master(), "potential", (2025, 2030, 2035, 2040, 2045, 2050), nparts=3
    )[("BEWAL", "biogas", "p_nom")]
    assert tgt.year_rule == "interp"
    for year, parts in TIMES.items():
        assert tgt.anchors[year] == pytest.approx(sum(parts) * GWH_PER_PJ, abs=0.5), year
    # TIMES's own 2045: BNDACT interpolated to 18.52 PJ, landfill 0.1278 PJ.
    times_2045 = (18.52 + 2.23223809195052 + 0.1278) * GWH_PER_PJ
    assert tgt.values[2045] == pytest.approx(times_2045, abs=0.5)


@pytest.mark.parametrize(
    "path", ["custom_potentials.csv", "custom_potentials_scen_retardnucleaire.csv"]
)
def test_generated_files_carry_the_cap(path):
    df = pd.read_csv(bcp.ROOT / "data" / "walloon" / path)
    rows = df[(df["technology"] == "biogas") & (df["parameter"] == "p_nom")]
    got = dict(zip(rows["year"].astype(int), rows["value"].astype(float)))
    assert got == {2025: 1019, 2030: 2145, 2035: 3363, 2040: 4667, 2045: 5800, 2050: 6933}
