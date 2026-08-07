# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Tests for the TIMES heating soft-link (option C).

The three things that can silently go wrong, and which nothing else checks:

* **Sign convention.** Heat pumps are reversed links (``bus0`` is the heat bus,
  ``p <= 0``, heat delivered is ``-p``) while boilers and resistive heaters are
  conventional (``heat = efficiency * p``). Getting one of them backwards
  produces a feasible LP with a meaningless mix.
* **Unit of the base-year stock.** ``existing_heating_distribution`` is in MW
  thermal *output* — ``add_existing_baseyear`` divides by the boiler efficiency
  itself, and a heat pump's ``p_nom`` is thermal because ``p_min_pu = -1``. A COP
  or an efficiency applied here would be a double conversion.
* **Placement.** A capacity written to a ``(heat name, technology)`` pair PyPSA
  cannot site — ``services rural`` (the sub-system is deleted), or a ground heat
  pump on ``urban decentral`` (``heat_pump_sources`` lists only ``air``) — is
  dropped by ``add_existing_baseyear`` without a word.
"""

from types import SimpleNamespace

import pandas as pd
import pypsa
import pytest

from scripts.walloon_scripts.times_heat_softlink import (
    DECENTRAL_HEAT_SYSTEMS,
    _group_carriers,
    add_times_heat_mix_constraints,
    apply_times_base_year_stock,
    decentral_heat_buses,
    heat_injection_terms,
    split_residential_heat_target,
    times_heat_options,
    times_heat_stock_capacities,
)

NODE = "BEWAL"


# --------------------------------------------------------------------------- #
# Options
# --------------------------------------------------------------------------- #


def test_options_default_to_the_legacy_behaviour():
    opts = times_heat_options({})
    assert opts["urban_rural_split"] == "times"
    assert opts["base_year_capacities"] is False
    assert opts["energy_mix"]["enable"] is False


def test_options_merge_partially():
    opts = times_heat_options(
        {"sector": {"times_heat": {"energy_mix": {"enable": True}}}}
    )
    assert opts["energy_mix"]["enable"] is True
    # untouched sub-keys keep their defaults
    assert opts["energy_mix"]["mode"] == "share"
    assert opts["energy_mix"]["tolerance"] == 0.05
    assert opts["urban_rural_split"] == "times"


@pytest.mark.parametrize(
    "block, match",
    [
        ({"urban_rural_split": "geographic"}, "urban_rural_split"),
        ({"energy_mix": {"mode": "absolutely"}}, "mode"),
        ({"energy_mix": {"tolerance": 1.5}}, "tolerance"),
        ({"energy_mix": {"tolerance": -0.1}}, "tolerance"),
    ],
)
def test_bad_options_are_rejected(block, match):
    with pytest.raises(ValueError, match=match):
        times_heat_options({"sector": {"times_heat": block}})


# --------------------------------------------------------------------------- #
# Urban/rural split of the demand
# --------------------------------------------------------------------------- #

URBAN = "BEWAL residential urban decentral heat"
RURAL = "BEWAL residential rural heat"


@pytest.fixture
def split_weights():
    # TIMES 2025: 8.7624 urban / 12.4688 rural → 58.7 % rural.
    times = pd.Series({URBAN: 8.7624, RURAL: 12.4688})
    # PyPSA: 1 - urban_fraction = 0.0793 rural against 0.8833 urban decentral.
    pypsa_w = pd.Series({URBAN: 0.8833, RURAL: 0.0793})
    return times, pypsa_w


@pytest.mark.parametrize("mode", ["times", "times_base_year", "pypsa"])
def test_split_preserves_the_total(mode, split_weights):
    times, pypsa_w = split_weights
    total = 15.7548
    out = split_residential_heat_target(total, mode, pypsa_w, times)
    assert out.sum() == pytest.approx(total)
    assert set(out.index) == {URBAN, RURAL}


def test_times_split_follows_the_times_weights(split_weights):
    times, pypsa_w = split_weights
    out = split_residential_heat_target(21.2312, "times", pypsa_w, times)
    assert out[RURAL] / out.sum() == pytest.approx(12.4688 / 21.2312)


def test_pypsa_split_follows_the_population_weights(split_weights):
    times, pypsa_w = split_weights
    out = split_residential_heat_target(21.2312, "pypsa", pypsa_w, times)
    assert out[RURAL] / out.sum() == pytest.approx(0.0793 / (0.0793 + 0.8833))


def test_base_year_split_uses_the_weights_it_is_handed(split_weights):
    """`times_base_year` differs from `times` only in *which* horizon's weights.

    The caller passes the base-year TIMES weights; the function must not
    re-derive them from the current horizon.
    """
    _times_now, pypsa_w = split_weights
    base_year = pd.Series({URBAN: 8.7624, RURAL: 12.4688})
    out = split_residential_heat_target(15.7548, "times_base_year", pypsa_w, base_year)
    assert out[RURAL] / out.sum() == pytest.approx(12.4688 / 21.2312)


def test_zero_weights_fall_back_to_an_even_split(split_weights):
    _times, pypsa_w = split_weights
    zero = pd.Series({URBAN: 0.0, RURAL: 0.0})
    out = split_residential_heat_target(10.0, "times", pypsa_w, zero)
    assert out[URBAN] == pytest.approx(5.0)
    assert out[RURAL] == pytest.approx(5.0)


# --------------------------------------------------------------------------- #
# Base-year stock
# --------------------------------------------------------------------------- #


@pytest.fixture
def times_capacities():
    """A miniature ``heating_capacities_{year}.csv``."""
    return pd.DataFrame(
        [
            # residential, both TIMES heat systems
            ("gas boiler", "residential", "rural", "gas boiler", 4468.4, True),
            ("gas boiler", "residential", "urban decentral", "gas boiler", 4439.7, True),
            ("heat pump", "residential", "rural", "air heat pump", 157.6, True),
            (
                "heat pump",
                "residential",
                "urban decentral",
                "ground heat pump",
                1.0,
                True,
            ),
            # services — must all end up on `services urban decentral`
            ("gas boiler", "services", "urban decentral", "gas boiler", 3414.5, True),
            ("heat pump", "services", "urban decentral", "ground heat pump", 7.0, True),
            # not transferable: no PyPSA stock column
            ("solar thermal", "residential", "rural", "", 33.2, False),
            # not transferable: district-heating substations
            ("district heating", "district", "urban central", "", 224.4, False),
        ],
        columns=[
            "group",
            "sector",
            "times_heat_system",
            "pypsa_stock_technology",
            "MW_th",
            "transferable",
        ],
    )


def test_stock_keeps_every_transferable_mw(times_capacities):
    stock = times_heat_stock_capacities(times_capacities, "times", 0.0793)
    transferable = times_capacities.loc[times_capacities["transferable"], "MW_th"].sum()
    assert stock.sum() == pytest.approx(transferable)


def test_stock_drops_untransferable_capacity(times_capacities):
    stock = times_heat_stock_capacities(times_capacities, "times", 0.0793)
    assert 33.2 not in stock.to_numpy()
    assert not any("urban central" in name for name, _ in stock.index)


def test_stock_never_lands_on_services_rural(times_capacities):
    """`write_wallon_heat_demands` deletes the whole `BEWAL services rural` system."""
    for mode in ("times", "times_base_year", "pypsa"):
        stock = times_heat_stock_capacities(times_capacities, mode, 0.0793)
        assert "services rural" not in {name for name, _ in stock.index}


def test_ground_heat_pumps_are_folded_onto_rural(times_capacities):
    """PyPSA can only site a ground-source heat pump on a rural bus."""
    stock = times_heat_stock_capacities(times_capacities, "times", 0.0793)
    assert stock.get(("residential urban decentral", "ground heat pump"), 0.0) == 0.0
    assert stock[("residential rural", "ground heat pump")] == pytest.approx(1.0)
    # A services ground heat pump has nowhere to go at all: `services rural` is
    # deleted, so it must not silently reappear on urban decentral either.
    assert stock.get(("services urban decentral", "ground heat pump"), 0.0) == 0.0


def test_air_heat_pumps_are_folded_onto_urban_decentral(times_capacities):
    stock = times_heat_stock_capacities(times_capacities, "times", 0.0793)
    assert stock.get(("residential rural", "air heat pump"), 0.0) == 0.0
    assert stock[("residential urban decentral", "air heat pump")] == pytest.approx(157.6)


def test_times_split_keeps_the_times_labels(times_capacities):
    stock = times_heat_stock_capacities(times_capacities, "times", 0.0793)
    assert stock[("residential rural", "gas boiler")] == pytest.approx(4468.4)
    assert stock[("residential urban decentral", "gas boiler")] == pytest.approx(4439.7)


def test_pypsa_split_reallocates_residential_by_the_population_fraction(
    times_capacities,
):
    frac = 0.0793
    stock = times_heat_stock_capacities(times_capacities, "pypsa", frac)
    residential_gas = 4468.4 + 4439.7
    assert stock[("residential rural", "gas boiler")] == pytest.approx(
        residential_gas * frac
    )
    assert stock[("residential urban decentral", "gas boiler")] == pytest.approx(
        residential_gas * (1 - frac)
    )
    # Services capacity is untouched by the residential split.
    assert stock[("services urban decentral", "gas boiler")] == pytest.approx(3414.5)


@pytest.fixture
def existing_distribution():
    columns = pd.MultiIndex.from_product(
        [
            [
                "urban central",
                "residential rural",
                "residential urban decentral",
                "services rural",
                "services urban decentral",
            ],
            [
                "gas boiler",
                "oil boiler",
                "resistive heater",
                "air heat pump",
                "ground heat pump",
                "biomass boiler",
            ],
        ],
        names=["heat name", "technology"],
    )
    return pd.DataFrame(1.0, index=["BEWAL", "BEVLG"], columns=columns)


def test_apply_stock_overwrites_only_the_target_node(
    existing_distribution, times_capacities
):
    stock = times_heat_stock_capacities(times_capacities, "times", 0.0793)
    out = apply_times_base_year_stock(existing_distribution, stock, NODE)
    assert out.loc["BEVLG"].equals(existing_distribution.loc["BEVLG"])
    assert out.loc[NODE].sum() == pytest.approx(stock.sum())
    # A technology TIMES does not have must be zeroed, not left at the EU value.
    assert out.loc[NODE, ("residential rural", "oil boiler")] == 0.0
    assert out.loc[NODE, ("services rural", "gas boiler")] == 0.0


def test_apply_stock_rejects_an_unknown_node(existing_distribution, times_capacities):
    stock = times_heat_stock_capacities(times_capacities, "times", 0.0793)
    with pytest.raises(KeyError, match="not a node"):
        apply_times_base_year_stock(existing_distribution, stock, "BEXXX")


def test_apply_stock_rejects_an_unknown_technology(existing_distribution):
    stock = pd.Series(
        {("residential rural", "hydrogen boiler"): 10.0},
    )
    stock.index = pd.MultiIndex.from_tuples(
        stock.index, names=["heat name", "technology"]
    )
    with pytest.raises(KeyError, match="no matching"):
        apply_times_base_year_stock(existing_distribution, stock, NODE)


# --------------------------------------------------------------------------- #
# Network-side selection and signs
# --------------------------------------------------------------------------- #


def _toy_network(cop: float = 3.0, hours: int = 4) -> pypsa.Network:
    """A BEWAL-shaped decentral heat system: two heat buses, four suppliers."""
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2013-01-01", periods=hours, freq="6h"))
    n.snapshot_weightings.loc[:, :] = 6.0

    n.add("Bus", "BEWAL", carrier="AC")
    n.add("Bus", "BEWAL low voltage", carrier="low voltage")
    n.add("Bus", "BEWAL gas", carrier="gas")
    for system in DECENTRAL_HEAT_SYSTEMS:
        n.add("Bus", f"BEWAL {system} heat", carrier=f"{system} heat")
    # An out-of-scope bus, to prove the selection stops at the decentral systems.
    n.add("Bus", "BEWAL urban central heat", carrier="urban central heat")

    n.add("Generator", "BEWAL gas supply", bus="BEWAL gas", p_nom=1e5, marginal_cost=40)
    n.add("Generator", "BEWAL elec", bus="BEWAL", p_nom=1e5, marginal_cost=60)
    n.add("Link", "BEWAL distribution", bus0="BEWAL", bus1="BEWAL low voltage",
          p_nom=1e5, efficiency=1.0)

    for system in DECENTRAL_HEAT_SYSTEMS:
        heat = f"BEWAL {system} heat"
        n.add("Link", f"BEWAL {system} gas boiler-2025", bus0="BEWAL gas", bus1=heat,
              carrier=f"{system} gas boiler", efficiency=0.9,
              p_nom_extendable=True, capital_cost=1e-3)
        n.add("Link", f"BEWAL {system} resistive heater-2025",
              bus0="BEWAL low voltage", bus1=heat,
              carrier=f"{system} resistive heater", efficiency=0.99,
              p_nom_extendable=True, capital_cost=1e-3)
        # Reversed heat pump: bus0 is the heat bus, efficiency = 1/COP.
        n.add("Link", f"BEWAL {system} air heat pump-2025", bus0=heat,
              bus1="BEWAL low voltage", carrier=f"{system} air heat pump",
              efficiency=1 / cop, p_max_pu=0.0, p_min_pu=-1.0,
              p_nom_extendable=True, capital_cost=1e-3)
        # Storage links touch the same bus and must never be picked up.
        n.add("Link", f"BEWAL {system} water tanks charger-2025", bus0=heat,
              bus1=f"BEWAL {system} water tanks",
              carrier=f"{system} water tanks charger", p_nom=10.0)
        n.add("Bus", f"BEWAL {system} water tanks", carrier=f"{system} water tanks")
        # Expensive enough that the unconstrained optimum builds none, as in the
        # real model (PyPSA-Wal builds 0.01 MW of BEWAL solar thermal in 2025).
        n.add("Generator", f"BEWAL {system} solar thermal collector-2025", bus=heat,
              carrier=f"{system} solar thermal", p_nom_extendable=True,
              capital_cost=1e4, p_max_pu=0.5)
        n.add("Load", heat, bus=heat, p_set=100.0)
    n.add("Link", "BEWAL urban central gas boiler-2025", bus0="BEWAL gas",
          bus1="BEWAL urban central heat", carrier="urban central gas boiler",
          efficiency=0.9, p_nom_extendable=True, capital_cost=1.0)
    return n


def test_decentral_heat_buses_excludes_urban_central():
    n = _toy_network()
    buses = decentral_heat_buses(n, NODE)
    assert list(buses) == ["BEWAL rural heat", "BEWAL urban decentral heat"]


def test_group_carriers_expands_over_both_systems():
    assert _group_carriers(["gas boiler"]) == [
        "rural gas boiler",
        "urban decentral gas boiler",
    ]


def test_boiler_coefficient_is_the_efficiency():
    n = _toy_network()
    buses = decentral_heat_buses(n, NODE)
    index, coeffs = heat_injection_terms(n, buses, ["gas boiler"], "Link")
    assert set(index) == {
        "BEWAL rural gas boiler-2025",
        "BEWAL urban decentral gas boiler-2025",
    }
    assert (coeffs == 0.9).all()


def test_heat_pump_coefficient_is_minus_one():
    """Reversed link: heat delivered is ``-p``, whatever the COP."""
    n = _toy_network(cop=4.0)
    buses = decentral_heat_buses(n, NODE)
    index, coeffs = heat_injection_terms(n, buses, ["air heat pump"], "Link")
    assert len(index) == 2
    assert (coeffs == -1.0).all()


def test_generator_coefficient_is_one():
    n = _toy_network()
    buses = decentral_heat_buses(n, NODE)
    index, coeffs = heat_injection_terms(n, buses, ["solar thermal"], "Generator")
    assert len(index) == 2
    assert (coeffs == 1.0).all()


def test_storage_and_out_of_scope_components_are_not_selected():
    n = _toy_network()
    buses = decentral_heat_buses(n, NODE)
    index, _ = heat_injection_terms(n, buses, ["gas boiler"], "Link")
    assert not any("water tanks" in name for name in index)
    assert not any("urban central" in name for name in index)


def test_time_dependent_efficiency_is_refused():
    n = _toy_network()
    name = "BEWAL rural gas boiler-2025"
    n.links_t.efficiency[name] = pd.Series(0.9, index=n.snapshots)
    buses = decentral_heat_buses(n, NODE)
    with pytest.raises(NotImplementedError, match="Time-dependent efficiency"):
        heat_injection_terms(n, buses, ["gas boiler"], "Link")


def test_ambiguous_two_port_link_is_refused():
    n = _toy_network()
    n.add("Link", "BEWAL rural weird-2025", bus0="BEWAL rural heat",
          bus1="BEWAL urban decentral heat", carrier="rural gas boiler",
          efficiency=1.0, p_nom=1.0)
    buses = decentral_heat_buses(n, NODE)
    with pytest.raises(ValueError, match="both ports"):
        heat_injection_terms(n, buses, ["gas boiler"], "Link")


# --------------------------------------------------------------------------- #
# End to end: does the LP actually deliver the TIMES mix?
# --------------------------------------------------------------------------- #


def _targets_frame(shares: dict[str, float]) -> pd.DataFrame:
    meta = {
        "heat pump": ("air heat pump", "Link", "<="),
        "gas boiler": ("gas boiler", "Link", ">="),
        "resistive heater": ("resistive heater", "Link", ">="),
        "solar thermal": ("solar thermal", "Generator", ">="),
    }
    rows = [
        {
            "year": 2025,
            "group": group,
            "scope": "decentral",
            "constrained": True,
            "pypsa_component": meta[group][1],
            "pypsa_carriers": meta[group][0],
            "sense": meta[group][2],
            "TWh": share * 10.0,
            "PJ": share * 36.0,
            "share": share,
            "times_categories": "",
        }
        for group, share in shares.items()
    ]
    rows.append(
        {
            "year": 2025,
            "group": "district heating",
            "scope": "urban central",
            "constrained": False,
            "pypsa_component": "",
            "pypsa_carriers": "",
            "sense": "none",
            "TWh": 1.0,
            "PJ": 3.6,
            "share": 0.0,
            "times_categories": "",
        }
    )
    return pd.DataFrame(rows)


def _mock_snakemake(tmp_path, targets: pd.DataFrame, **energy_mix) -> SimpleNamespace:
    path = tmp_path / "heating_targets_2025.csv"
    targets.to_csv(path, index=False)
    return SimpleNamespace(
        config={
            "sector": {
                "times_heat": {
                    "node": NODE,
                    "energy_mix": {"enable": True, **energy_mix},
                }
            }
        },
        input=SimpleNamespace(heating_targets=str(path)),
    )


def _realised_shares(n: pypsa.Network) -> pd.Series:
    """Heat delivered to the decentral buses per group, in MWh_th."""
    buses = decentral_heat_buses(n, NODE)
    w = n.snapshot_weightings.generators
    out = {}
    for group, (carriers, component) in {
        "heat pump": (["air heat pump"], "Link"),
        "gas boiler": (["gas boiler"], "Link"),
        "resistive heater": (["resistive heater"], "Link"),
        "solar thermal": (["solar thermal"], "Generator"),
    }.items():
        index, coeffs = heat_injection_terms(n, buses, carriers, component)
        p = n.links_t.p0 if component == "Link" else n.generators_t.p
        out[group] = float((p[index] * coeffs).mul(w, axis=0).to_numpy().sum())
    series = pd.Series(out)
    return series / series.sum()


@pytest.mark.parametrize("mode", ["share", "absolute"])
def test_constraints_deliver_the_times_mix(tmp_path, mode):
    """Without the constraint the LP picks the heat pump; with it, it must not.

    The toy network is built so the unconstrained optimum is heat-pump dominated
    (a COP of 3 beats a 0.9 gas boiler at these fuel prices), which is exactly the
    2025 divergence the soft-link exists to close.
    """
    shares = {
        "heat pump": 0.10,
        "gas boiler": 0.60,
        "resistive heater": 0.25,
        "solar thermal": 0.05,
    }
    free = _toy_network()
    free.optimize(solver_name="highs")
    baseline = _realised_shares(free)
    assert baseline["heat pump"] > 0.5, "toy network should favour the heat pump"

    n = _toy_network()
    snakemake = _mock_snakemake(tmp_path, _targets_frame(shares), mode=mode)
    if mode == "absolute":
        # Absolute targets are annual TWh and get scaled by the fraction of a year
        # the network covers, so the toy's 24 h of load must be grossed up to an
        # annual figure or the constraints are ~0 and prove nothing.
        total_mwh = float(
            (n.loads.p_set * n.snapshot_weightings.generators.sum()).sum()
        )
        nyears = n.snapshot_weightings.objective.sum() / 8760.0
        targets = _targets_frame(shares)
        targets["TWh"] = targets["share"] * total_mwh / nyears / 1e6
        snakemake = _mock_snakemake(tmp_path, targets, mode=mode)

    status, condition = n.optimize(
        solver_name="highs",
        extra_functionality=lambda net, sns: add_times_heat_mix_constraints(
            net, sns, snakemake
        ),
    )
    assert (status, condition) == ("ok", "optimal")

    realised = _realised_shares(n)
    tol = 0.05
    assert realised["heat pump"] <= shares["heat pump"] * (1 + tol) + 1e-6
    for group in ("gas boiler", "resistive heater", "solar thermal"):
        assert realised[group] >= shares[group] * (1 - tol) - 1e-6, (
            f"{group}: realised {realised[group]:.4f} < target {shares[group]:.4f}"
        )
    assert n.objective > free.objective, "the TIMES mix must cost more than the optimum"


def test_disabled_option_adds_no_constraint(tmp_path):
    n = _toy_network()
    snakemake = _mock_snakemake(tmp_path, _targets_frame({"gas boiler": 1.0}))
    snakemake.config["sector"]["times_heat"]["energy_mix"]["enable"] = False
    n.optimize.create_model()
    before = set(n.model.constraints)
    add_times_heat_mix_constraints(n, n.snapshots, snakemake)
    assert set(n.model.constraints) == before


def test_missing_targets_input_is_a_clear_error():
    n = _toy_network()
    snakemake = SimpleNamespace(
        config={"sector": {"times_heat": {"energy_mix": {"enable": True}}}},
        input=SimpleNamespace(heating_targets=[]),
    )
    with pytest.raises(ValueError, match="heating_targets"):
        add_times_heat_mix_constraints(n, n.snapshots, snakemake)


def test_slack_group_is_left_unconstrained(tmp_path):
    n = _toy_network()
    targets = _targets_frame(
        {"heat pump": 0.1, "gas boiler": 0.6, "resistive heater": 0.25,
         "solar thermal": 0.05}
    )
    snakemake = _mock_snakemake(tmp_path, targets, slack_groups=["gas boiler"])
    n.optimize.create_model()
    add_times_heat_mix_constraints(n, n.snapshots, snakemake)
    names = set(n.model.constraints)
    assert "times_heat_mix_gas boiler" not in names
    assert "times_heat_mix_heat pump" in names


def test_penalty_turns_an_impossible_mix_into_a_priced_relaxation(tmp_path):
    """The property the whole myopic chain depends on: no mix can be infeasible.

    A hard `>=` on the TIMES gas share is jointly infeasible with PyPSA's Walloon
    CO2 cap and EU biomass limit in 2040, and an infeasible sector LP does not just
    fail — `solve_network.py` then computes a Gurobi IIS on 1.3 M rows, which never
    returns, so one horizon hangs the whole chain. Here the same situation is
    reproduced in miniature by starving the gas supply.
    """
    shares = {
        "heat pump": 0.10,
        "gas boiler": 0.60,
        "resistive heater": 0.25,
        "solar thermal": 0.05,
    }

    hard = _toy_network()
    hard.generators.loc["BEWAL gas supply", "p_nom"] = 5.0
    sm_hard = _mock_snakemake(tmp_path, _targets_frame(shares), penalty=0.0)
    status, _ = hard.optimize(
        solver_name="highs",
        extra_functionality=lambda net, sns: add_times_heat_mix_constraints(
            net, sns, sm_hard
        ),
    )
    assert status != "ok", "hard constraints should be infeasible here"

    soft = _toy_network()
    soft.generators.loc["BEWAL gas supply", "p_nom"] = 5.0
    sm_soft = _mock_snakemake(tmp_path, _targets_frame(shares), penalty=1000.0)
    status, condition = soft.optimize(
        solver_name="highs",
        extra_functionality=lambda net, sns: add_times_heat_mix_constraints(
            net, sns, sm_soft
        ),
    )
    assert (status, condition) == ("ok", "optimal")

    slack = (
        soft.model.variables["TimesHeatMix-slack"].solution.to_series().astype(float)
    )
    # Only the group that cannot be served is relaxed …
    assert slack["gas boiler"] > 0
    # … the others still respect their bounds.
    assert slack.drop("gas boiler").max() == pytest.approx(0.0, abs=1e-6)
    realised = _realised_shares(soft)
    assert realised["heat pump"] <= shares["heat pump"] * 1.05 + 1e-6
    assert realised["solar thermal"] >= shares["solar thermal"] * 0.95 - 1e-6


def test_no_slack_variable_when_penalty_is_zero(tmp_path):
    n = _toy_network()
    sm = _mock_snakemake(tmp_path, _targets_frame({"gas boiler": 0.6, "heat pump": 0.4}),
                         penalty=0.0)
    n.optimize.create_model()
    add_times_heat_mix_constraints(n, n.snapshots, sm)
    assert "TimesHeatMix-slack" not in set(n.model.variables)


def test_penalty_is_validated():
    with pytest.raises(ValueError, match="penalty"):
        times_heat_options(
            {"sector": {"times_heat": {"energy_mix": {"penalty": -1}}}}
        )
    # null / false mean "hard constraints", not an error
    for value in (None, False, 0):
        opts = times_heat_options(
            {"sector": {"times_heat": {"energy_mix": {"penalty": value}}}}
        )
        assert opts["energy_mix"]["penalty"] == 0.0


def test_zero_target_forbids_the_technology_by_default(tmp_path):
    """TIMES retires oil by 2050; `>= 0` would be vacuous, `<= 0` is the point."""
    n = _toy_network()
    targets = _targets_frame({"heat pump": 1.0, "gas boiler": 0.0})
    snakemake = _mock_snakemake(tmp_path, targets)
    n.optimize.create_model()
    add_times_heat_mix_constraints(n, n.snapshots, snakemake)
    assert "times_heat_mix_gas boiler" in set(n.model.constraints)
    assert "times_heat_mix_heat pump" in set(n.model.constraints)


def test_zero_target_can_be_left_free(tmp_path):
    n = _toy_network()
    targets = _targets_frame({"heat pump": 1.0, "gas boiler": 0.0})
    snakemake = _mock_snakemake(tmp_path, targets, zero_target="free")
    n.optimize.create_model()
    add_times_heat_mix_constraints(n, n.snapshots, snakemake)
    assert "times_heat_mix_gas boiler" not in set(n.model.constraints)


def test_forbidden_technology_is_actually_not_used(tmp_path):
    """A `<= 0` on a retired technology must be feasible and binding."""
    n = _toy_network()
    targets = _targets_frame(
        {"heat pump": 0.7, "gas boiler": 0.0, "resistive heater": 0.3}
    )
    snakemake = _mock_snakemake(tmp_path, targets)
    status, condition = n.optimize(
        solver_name="highs",
        extra_functionality=lambda net, sns: add_times_heat_mix_constraints(
            net, sns, snakemake
        ),
    )
    assert (status, condition) == ("ok", "optimal")
    assert _realised_shares(n)["gas boiler"] == pytest.approx(0.0, abs=1e-6)
