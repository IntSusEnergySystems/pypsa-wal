# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/PyPSA/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""Guards for the 2025 Walloon PV base-year split (item 8 / plan B5)."""

from pathlib import Path

import pandas as pd
import pypsa
import pytest

from scripts.walloon_scripts.baseyear_pv_split import (
    apply_baseyear_pv_split,
    split_baseyear_pv,
)

REPO = Path(__file__).parents[1]
SPLIT_CSV = REPO / "data/walloon/baseyear_pv_split.csv"
AGG_CSV = REPO / "data/walloon/agg_p_nom_minmax_demande_haute.csv"


def toy_network():
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2025-01-01", periods=3, freq="h"))
    n.add("Bus", "BEWAL", carrier="AC", country="BE", location="BEWAL")
    n.add("Bus", "BEWAL low voltage", carrier="low voltage", country="BE",
          location="BEWAL")
    vintages = ["BEWAL 0 solar-2010", "BEWAL 0 solar-2015", "BEWAL 0 solar-2020"]
    profiles = pd.DataFrame(
        {
            vintages[0]: [0.1, 0.4, 0.8],
            vintages[1]: [0.0, 0.6, 0.9],
            vintages[2]: [0.0, 0.5, 1.0],
        },
        index=n.snapshots,
    )
    n.add(
        "Generator",
        vintages,
        bus="BEWAL",
        carrier="solar",
        p_nom=[500.0, 800.0, 486.1],
        p_nom_extendable=False,
        build_year=[2010, 2015, 2020],
        lifetime=25,
        capital_cost=71898.0,
        marginal_cost=1.0,
        p_max_pu=profiles,
    )
    n.add(
        "Generator",
        "BEWAL 0 solar rooftop",
        bus="BEWAL low voltage",
        carrier="solar rooftop",
        p_nom=0.0,
        p_nom_extendable=True,
        p_nom_max=7500.0,
        capital_cost=84627.0,
        marginal_cost=1.0,
    )
    return n


def test_split_relabels_newest_first_on_low_voltage():
    n = toy_network()
    split_baseyear_pv(n, "BEWAL", 1770.0)
    roof = n.generators[n.generators.carrier == "solar rooftop"]
    standing = roof[~roof.p_nom_extendable]
    assert standing.p_nom.sum() == pytest.approx(1770.0)
    assert (standing.bus == "BEWAL low voltage").all()
    # newest vintages first: 2020 (486.1) and 2015 (800) fully, 483.9 of 2010
    assert standing.loc["BEWAL 0 solar rooftop-2020", "p_nom"] == pytest.approx(486.1)
    assert standing.loc["BEWAL 0 solar rooftop-2015", "p_nom"] == pytest.approx(800.0)
    assert standing.loc["BEWAL 0 solar rooftop-2010", "p_nom"] == pytest.approx(483.9)
    assert standing.loc["BEWAL 0 solar rooftop-2010", "build_year"] == 2010
    # utility remainder and total fleet unchanged
    solar = n.generators[(n.generators.carrier == "solar")]
    assert solar.p_nom.sum() == pytest.approx(16.1)
    total = n.generators[n.generators.carrier.str.contains("solar")].p_nom.sum()
    assert total == pytest.approx(1786.1)
    # profile copied from the carved vintage
    assert n.generators_t.p_max_pu["BEWAL 0 solar rooftop-2010"].tolist() == [
        0.1, 0.4, 0.8,
    ]
    # cost attributes follow the rooftop candidates, not utility
    assert (standing.capital_cost.round() == 84627.0).all()


def test_split_short_standing_fleet_is_partial():
    n = toy_network()
    split_baseyear_pv(n, "BEWAL", 5000.0)
    roof = n.generators[
        (n.generators.carrier == "solar rooftop") & ~n.generators.p_nom_extendable
    ]
    assert roof.p_nom.sum() == pytest.approx(1786.1)
    assert n.generators[n.generators.carrier == "solar"].p_nom.sum() == pytest.approx(
        0.0
    )


def test_apply_reads_csv_and_filters_year(tmp_path):
    csv = tmp_path / "split.csv"
    csv.write_text(
        "# comment\nnode,year,rooftop_mw,utility_mw,source\n"
        "BEWAL,2025,1000.0,500.0,test\nBEWAL,2030,2000.0,500.0,test\n"
    )
    n = toy_network()
    apply_baseyear_pv_split(n, {"enable": True, "file": str(csv)}, 2025)
    roof = n.generators[
        (n.generators.carrier == "solar rooftop") & ~n.generators.p_nom_extendable
    ]
    assert roof.p_nom.sum() == pytest.approx(1000.0)


def test_apply_disabled_is_noop():
    n = toy_network()
    apply_baseyear_pv_split(n, {"enable": False, "file": str(SPLIT_CSV)}, 2025)
    assert not (
        (n.generators.carrier == "solar rooftop") & ~n.generators.p_nom_extendable
    ).any()


def test_split_csv_matches_the_2025_solar_all_pin():
    split = pd.read_csv(SPLIT_CSV, comment="#")
    agg = pd.read_csv(AGG_CSV, skiprows=3, header=None, index_col=[0, 1])
    pin = float(agg.loc[("BEWAL", "solar-all"), 2])
    assert split["rooftop_mw"].sum() + split["utility_mw"].sum() == pytest.approx(
        pin, abs=1.0
    )
