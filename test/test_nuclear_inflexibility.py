# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Nuclear must-run: p_min_pu = country availability − margin.

The availability CSV is not 1.0 (BE 0.883, FR 0.616). A hardcoded 90 % floor
would make French nuclear infeasible. docs/nuclear-alignment-20260816.md §6.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pypsa
import pytest
import yaml

from scripts.walloon_scripts.nuclear_helper import (
    DEFAULT_P_MIN_PU_MARGIN,
    apply_nuclear_inflexibility,
    load_nuclear_p_max_pu,
)

CSV = "data/nuclear_p_max_pu.csv"
CONFIG_ON = {
    "conventional": {
        "nuclear": {"p_max_pu": CSV},
        "inflexible_nuclear": {"enable": True, "p_min_pu_margin": 0.10},
    }
}
CONFIG_OFF = {
    "conventional": {
        "nuclear": {"p_max_pu": CSV},
        "inflexible_nuclear": {"enable": False, "p_min_pu_margin": 0.10},
    }
}


def _nuclear_network() -> pypsa.Network:
    """Legacy vintage + retrofit link per country, plus an electricity-only gen."""
    n = pypsa.Network()
    for bus, country in (("BEWAL", "BE"), ("FR", "FR"), ("LU", "LU")):
        n.add("Bus", bus, carrier="AC", country=country, location=bus)
        n.add("Bus", f"{bus} uranium", carrier="uranium", country=country)
        for suffix in (" nuclear-2025", " nuclear-1985 retrofit"):
            n.add(
                "Link",
                bus + suffix,
                bus0=f"{bus} uranium",
                bus1=bus,
                carrier="nuclear",
                p_nom=1000.0,
                p_max_pu=1.0,
                p_min_pu=0.0,
            )
    n.add(
        "Generator",
        "BEWAL nuclear-gen",
        bus="BEWAL",
        carrier="nuclear",
        p_nom=500.0,
        p_max_pu=1.0,
        p_min_pu=0.0,
    )
    n.add(
        "Link",
        "BEWAL CCGT",
        bus0="BEWAL uranium",
        bus1="BEWAL",
        carrier="CCGT",
        p_nom=400.0,
        p_max_pu=1.0,
        p_min_pu=0.0,
    )
    return n


def test_csv_is_not_unity_and_france_is_below_90_percent():
    table = load_nuclear_p_max_pu({"conventional": {"nuclear": {"p_max_pu": CSV}}})
    assert table["BE"] == pytest.approx(0.883)
    assert table["FR"] == pytest.approx(0.616)
    assert table["GB"] == pytest.approx(0.684)
    assert table["NL"] == pytest.approx(0.901)
    assert table["FR"] < 0.90, (
        "a hardcoded 90 % p_min_pu would exceed French p_max_pu "
        f"({table['FR']}) and make the LP infeasible"
    )
    # Every modelled factor minus the default margin stays inside [0, p_max].
    p_min = (table - DEFAULT_P_MIN_PU_MARGIN).clip(lower=0.0)
    assert (p_min <= table).all()
    assert (p_min >= 0).all()


def test_absent_flag_is_a_noop():
    n = _nuclear_network()
    summary = apply_nuclear_inflexibility(n, {"conventional": {"nuclear": {"p_max_pu": CSV}}})
    assert summary["action"] == "skipped"
    assert (n.links.loc[n.links.carrier == "nuclear", "p_max_pu"] == 1.0).all()
    assert (n.links.loc[n.links.carrier == "nuclear", "p_min_pu"] == 0.0).all()


def test_enable_sets_country_bounds_on_legacy_new_and_retrofit():
    n = _nuclear_network()
    summary = apply_nuclear_inflexibility(n, CONFIG_ON)
    assert summary["action"] == "applied"
    assert summary["links"] == 6
    assert summary["generators"] == 1

    be_max, fr_max = 0.883, 0.616
    be_min, fr_min = be_max - 0.10, fr_max - 0.10
    for name in ("BEWAL nuclear-2025", "BEWAL nuclear-1985 retrofit"):
        assert n.links.at[name, "p_max_pu"] == pytest.approx(be_max)
        assert n.links.at[name, "p_min_pu"] == pytest.approx(be_min)
    for name in ("FR nuclear-2025", "FR nuclear-1985 retrofit"):
        assert n.links.at[name, "p_max_pu"] == pytest.approx(fr_max)
        assert n.links.at[name, "p_min_pu"] == pytest.approx(fr_min)
        assert n.links.at[name, "p_min_pu"] < n.links.at[name, "p_max_pu"]
        assert n.links.at[name, "p_min_pu"] < 0.90
    # LU is not in the CSV → cap stays 1.0, floor is 1.0 − margin.
    assert n.links.at["LU nuclear-2025", "p_max_pu"] == pytest.approx(1.0)
    assert n.links.at["LU nuclear-2025", "p_min_pu"] == pytest.approx(0.90)
    assert n.generators.at["BEWAL nuclear-gen", "p_max_pu"] == pytest.approx(be_max)
    assert n.generators.at["BEWAL nuclear-gen", "p_min_pu"] == pytest.approx(be_min)
    # Unrelated carriers are untouched.
    assert n.links.at["BEWAL CCGT", "p_max_pu"] == 1.0
    assert n.links.at["BEWAL CCGT", "p_min_pu"] == 0.0


def test_enable_false_restores_unconstrained_links():
    n = _nuclear_network()
    apply_nuclear_inflexibility(n, CONFIG_ON)
    summary = apply_nuclear_inflexibility(n, CONFIG_OFF)
    assert summary["action"] == "restored"
    nuc = n.links.carrier == "nuclear"
    assert (n.links.loc[nuc, "p_max_pu"] == 1.0).all()
    assert (n.links.loc[nuc, "p_min_pu"] == 0.0).all()
    # Generators keep their (CSV) p_max_pu; only the floor is lifted.
    assert n.generators.at["BEWAL nuclear-gen", "p_min_pu"] == 0.0


def test_time_varying_p_max_pu_is_dropped_so_static_bounds_apply():
    n = _nuclear_network()
    n.set_snapshots(pd.date_range("2010-01-01", periods=3, freq="h"))
    n.links_t.p_max_pu["BEWAL nuclear-2025"] = 1.0
    apply_nuclear_inflexibility(n, CONFIG_ON)
    assert "BEWAL nuclear-2025" not in n.links_t.p_max_pu.columns
    assert n.links.at["BEWAL nuclear-2025", "p_max_pu"] == pytest.approx(0.883)


def test_negative_margin_is_rejected():
    n = _nuclear_network()
    cfg = {
        "conventional": {
            "nuclear": {"p_max_pu": CSV},
            "inflexible_nuclear": {"enable": True, "p_min_pu_margin": -0.05},
        }
    }
    with pytest.raises(ValueError, match="p_min_pu_margin"):
        apply_nuclear_inflexibility(n, cfg)


def test_walloon_config_enables_the_switch():
    walloon = yaml.safe_load(Path("config/config.walloon.yaml").read_text())
    opts = walloon["conventional"]["inflexible_nuclear"]
    assert opts["enable"] is True
    assert opts["p_min_pu_margin"] == pytest.approx(0.10)


def test_input_conventional_ignores_the_inflexible_block():
    """add_electricity only turns conventional.<carrier> CSV paths into inputs."""
    conventional = {
        "unit_commitment": False,
        "nuclear": {"p_max_pu": CSV},
        "inflexible_nuclear": {"enable": True, "p_min_pu_margin": 0.10},
    }
    carriers = ["nuclear", "OCGT"]
    inputs = {
        f"conventional_{carrier}_{attr}": fn
        for carrier, d in conventional.items()
        if carrier in carriers and isinstance(d, dict)
        for attr, fn in d.items()
        if str(fn).startswith("data/")
    }
    assert inputs == {"conventional_nuclear_p_max_pu": CSV}
