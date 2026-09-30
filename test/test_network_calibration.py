# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
#
# SPDX-License-Identifier: MIT

"""Network-cost calibration (docs/network-costs-review-20260928.md §2–§6).

Covers the reversed-DC costing bug, the three calibration hooks of
``scripts/walloon_scripts/network_calibration.py`` and the shared-parameter rows
they rely on.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import pytest
import yaml

from scripts.add_electricity import set_transmission_costs
from scripts.prepare_network import set_transmission_limit
from scripts.walloon_scripts.network_calibration import (
    add_rooftop_pv_hosting_cost,
    apply_transmission_cost_overrides,
    co2_scale_factor,
    read_transmission_cost_overrides,
    split_industry_electricity,
)

ROOT = Path(__file__).resolve().parents[1]

COSTS = pd.DataFrame(
    {
        "capital_cost": [70.0, 56.0, 336.0, 60_000.0, 41_430.0, 6_000.0],
        "investment": [450.0, 600.0, 3220.0, 640_000.0, 620_000.0, 640_000.0],
    },
    index=[
        "HVAC overhead",
        "HVDC overhead",
        "HVDC submarine",
        "HVDC inverter pair",
        "electricity distribution grid",
        "CO2 pipeline",
    ],
)


def _dc_network() -> pypsa.Network:
    """One HVDC link split like `lossy_bidirectional_links` splits it."""
    n = pypsa.Network()
    n.add("Carrier", ["AC", "DC"])
    n.add("Bus", ["BEWAL", "DE"], carrier="AC", v_nom=380.0, location=["BEWAL", "DE"])
    n.add(
        "Link", "alegro", bus0="BEWAL", bus1="DE", carrier="DC", p_nom=1000.0,
        length=281.0, underwater_fraction=0.0, p_min_pu=0.0,
    )
    n.add(
        "Link", "alegro-reversed", bus0="DE", bus1="BEWAL", carrier="DC", p_nom=1000.0,
        length=0.0, underwater_fraction=0.0, p_min_pu=0.0, capital_cost=0.0,
    )
    n.links["reversed"] = [False, True]
    return n


# --------------------------------------------------------------------------- #
# §6.2: the reversed twin must never be priced
# --------------------------------------------------------------------------- #
def test_set_transmission_costs_leaves_reversed_twin_at_zero():
    n = _dc_network()
    set_transmission_costs(n, COSTS)
    assert n.links.at["alegro-reversed", "capital_cost"] == 0.0
    assert n.links.at["alegro", "capital_cost"] == pytest.approx(281.0 * 56.0 + 60_000.0)


def test_twin_recognised_by_name_even_without_flag():
    n = _dc_network()
    n.links = n.links.drop(columns="reversed")
    set_transmission_costs(n, COSTS)
    assert n.links.at["alegro-reversed", "capital_cost"] == 0.0


def test_set_transmission_limit_as_add_brownfield_calls_it():
    """The path that actually broke: re-costing once the twins exist."""
    n = _dc_network()
    set_transmission_limit(n, "v", "opt", COSTS)
    assert n.links.at["alegro-reversed", "capital_cost"] == 0.0


# --------------------------------------------------------------------------- #
# E6: HV industry leaves the LV bus
# --------------------------------------------------------------------------- #
def _lv_network(dynamic: bool) -> pypsa.Network:
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2030-01-01", periods=3, freq="h"))
    n.add("Bus", ["BEWAL", "BEWAL low voltage"], carrier=["AC", "low voltage"], location="BEWAL")
    p = pd.Series([100.0, 120.0, 80.0], index=n.snapshots)
    n.add(
        "Load", "BEWAL industry electricity", bus="BEWAL low voltage",
        carrier="industry electricity", p_set=p if dynamic else 100.0,
    )
    n.add("Load", "BEWAL", bus="BEWAL low voltage", carrier="electricity", p_set=50.0)
    return n


@pytest.mark.parametrize("dynamic", [False, True])
def test_industry_split_conserves_energy_and_moves_share_to_ac(dynamic):
    n = _lv_network(dynamic)
    before = n.loads_t.p_set.sum().sum() if dynamic else n.loads.p_set.sum()
    created = split_industry_electricity(n, 0.7)
    assert list(created) == ["BEWAL industry electricity HV"]
    hv = n.loads.loc["BEWAL industry electricity HV"]
    assert hv.bus == "BEWAL" and hv.carrier == "industry electricity"
    if dynamic:
        lv_p = n.loads_t.p_set["BEWAL industry electricity"]
        hv_p = n.loads_t.p_set["BEWAL industry electricity HV"]
        np.testing.assert_allclose(hv_p / (hv_p + lv_p), 0.7)
        assert (lv_p + hv_p).sum() == pytest.approx(before)
    else:
        assert hv.p_set == pytest.approx(70.0)
        assert n.loads.at["BEWAL industry electricity", "p_set"] == pytest.approx(30.0)
        assert n.loads.p_set.sum() == pytest.approx(before)
    # the ordinary electricity load is untouched
    assert n.loads.at["BEWAL", "bus"] == "BEWAL low voltage"


def test_industry_split_is_a_noop_without_share():
    n = _lv_network(False)
    assert split_industry_electricity(n, None).empty
    assert len(n.loads) == 2


def test_industry_split_rejects_nonsense_share():
    with pytest.raises(ValueError):
        split_industry_electricity(_lv_network(False), 1.2)


# --------------------------------------------------------------------------- #
# E8: hosting cost on NEW rooftop PV only
# --------------------------------------------------------------------------- #
def test_pv_hosting_cost_only_on_extendable_rooftop():
    n = pypsa.Network()
    n.add("Bus", "BEWAL low voltage")
    n.add("Generator", "new", bus="BEWAL low voltage", carrier="solar rooftop",
          p_nom_extendable=True, capital_cost=50_000.0)
    n.add("Generator", "old", bus="BEWAL low voltage", carrier="solar rooftop",
          p_nom_extendable=False, capital_cost=50_000.0)
    n.add("Generator", "utility", bus="BEWAL low voltage", carrier="solar",
          p_nom_extendable=True, capital_cost=40_000.0)
    add_rooftop_pv_hosting_cost(n, COSTS, 120.0)
    ratio = 41_430.0 / 620_000.0
    assert n.generators.at["new", "capital_cost"] == pytest.approx(50_000.0 + 120e3 * ratio)
    assert n.generators.at["old", "capital_cost"] == 50_000.0
    assert n.generators.at["utility", "capital_cost"] == 40_000.0


# --------------------------------------------------------------------------- #
# TR5 / TR12: per-corridor overrides
# --------------------------------------------------------------------------- #
def _overrides() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ["Link", "DC", "BEWAL", "DE", "investment", 692_600.0, "HVDC inverter pair"],
            ["Link", "CO2 pipeline", "DE", "BEWAL", "capital_cost_factor", 0.6, ""],
        ],
        columns=["component", "carrier", "bus0", "bus1", "parameter", "value", "reference"],
    )


def test_investment_override_is_idempotent_and_skips_twin():
    n = _dc_network()
    set_transmission_costs(n, COSTS)
    for _ in range(2):  # prepare_sector_network, then add_brownfield
        apply_transmission_cost_overrides(n, COSTS, _overrides(), parameters=("investment",))
    assert n.links.at["alegro", "capital_cost"] == pytest.approx(692_600.0 * 60_000.0 / 640_000.0)
    assert n.links.at["alegro-reversed", "capital_cost"] == 0.0


def test_factor_override_hits_extendable_branches_once():
    n = pypsa.Network()
    n.add("Bus", ["BEWAL co2 stored", "DE co2 stored"], location=["BEWAL", "DE"])
    n.add("Link", "CO2 pipeline BEWAL -> DE-2030", bus0="BEWAL co2 stored",
          bus1="DE co2 stored", carrier="CO2 pipeline", p_nom_extendable=True,
          capital_cost=1000.0)
    n.add("Link", "CO2 pipeline BEWAL -> DE-2025", bus0="BEWAL co2 stored",
          bus1="DE co2 stored", carrier="CO2 pipeline", p_nom_extendable=False,
          capital_cost=1000.0)
    apply_transmission_cost_overrides(n, COSTS, _overrides())
    assert n.links.at["CO2 pipeline BEWAL -> DE-2030", "capital_cost"] == pytest.approx(600.0)
    assert n.links.at["CO2 pipeline BEWAL -> DE-2025", "capital_cost"] == 1000.0
    # add_brownfield passes investment only: the factor must not compound
    apply_transmission_cost_overrides(n, COSTS, _overrides(), parameters=("investment",))
    assert n.links.at["CO2 pipeline BEWAL -> DE-2030", "capital_cost"] == pytest.approx(600.0)


def test_co2_scale_factor_is_economies_only():
    assert co2_scale_factor(100.0) == 1.0
    assert co2_scale_factor(300.0) == 1.0
    assert co2_scale_factor(1089.0) == pytest.approx((1089 / 300) ** -0.4)
    assert 0 < co2_scale_factor(5000.0) < co2_scale_factor(1000.0) < 1


def test_shipped_override_table_is_readable():
    fn = ROOT / "data" / "walloon" / "transmission_cost_overrides.csv"
    df = read_transmission_cost_overrides(str(fn))
    alegro = df[(df.carrier == "DC") & (df.parameter == "investment")]
    assert len(alegro) == 1 and 6e5 < alegro.value.iloc[0] < 8e5
    co2 = df[df.carrier == "CO2 pipeline"]
    assert len(co2) and (co2.value > 0).all() and (co2.value < 1).all()


# --------------------------------------------------------------------------- #
# the shared-parameter rows the calibration relies on
# --------------------------------------------------------------------------- #
def test_network_discount_rates_generated():
    rates = pd.read_csv(ROOT / "data" / "walloon" / "discount_rates.csv")
    rates = rates.set_index("technology")["value"]
    for tech in ["electricity distribution grid", "HVAC overhead", "HVDC inverter pair",
                 "CO2 pipeline", "CH4 (g) pipeline", "H2 (g) pipeline"]:
        assert rates[tech] == pytest.approx(0.035), tech
    # producer-paid connections keep the power-sector hurdle
    assert rates["electricity grid connection"] == pytest.approx(0.075)


def test_calibrated_investments_in_custom_costs():
    cc = pd.read_csv(ROOT / "data" / "walloon" / "custom_costs.csv")
    row = cc[(cc.technology == "electricity distribution grid") & (cc.parameter == "investment")]
    assert float(row.value.iloc[0]) == pytest.approx(620.0)
    row = cc[(cc.technology == "HVAC overhead") & (cc.parameter == "investment")]
    assert float(row.value.iloc[0]) == pytest.approx(450.0)


def test_config_switches_on_calibration():
    cfg = yaml.safe_load((ROOT / "config" / "config.walloon.yaml").read_text())
    sec = cfg["sector"]
    assert sec["network_calibration"]["industry_hv_share"] == pytest.approx(0.70)
    assert sec["transmission_efficiency"]["electricity distribution grid"]["efficiency_static"] == 0.95
    # ~5 EUR/kW_th/a of avoidable gas-grid cost against the recalibrated annuity
    annuity = 0.035 / (1 - 1.035 ** -40) + 0.02
    assert sec["gas_distribution_grid_cost_factor"] * 620 * annuity == pytest.approx(5.0, abs=0.3)
