# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Tests for the TIMES heating soft-link, option B' (reconstructed profiles).

What can silently go wrong here, and what nothing else checks:

* **Closure.** The reconstructed profiles must sum to the heat load at *every*
  snapshot and on *every* bus. If they do not, the bus balance absorbs the
  difference through the heat vent or the water tank and the mix quietly stops
  being TIMES's. Both closure identities are asserted inside the code; these
  tests make sure the assertions actually fire.
* **The static load.** ``BEWAL agriculture heat`` is re-bussed onto the tertiary
  decentral bus with a *scalar* ``p_set``, so it is absent from
  ``loads_t.p_set``. Reading only the time-varying frame drops it from the
  denominator and breaks closure by ~0.5 %.
* **Solar thermal.** It is the only group with a dispatch ceiling. Giving it the
  load shape makes the LP infeasible in January; giving the others the *full*
  load rather than the residual breaks closure.
* **Sign conventions.** Inherited from option C, but re-checked end to end here
  because a wrong sign produces a feasible LP with a meaningless mix.
* **The relaxation.** One scalar per group, spread over the year in proportion
  to the profile. It must relax when the mix is physically impossible (or the
  myopic chain hangs on a Gurobi IIS) and must not relax otherwise.
"""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pypsa
import pytest

from scripts.walloon_scripts.times_heat_profiles import (
    SOLAR_GROUP,
    add_times_heat_profile_constraints,
    decentral_heat_load,
    reconstruct_profiles,
    solar_availability,
)
from scripts.walloon_scripts.times_heat_softlink import (
    DECENTRAL_HEAT_SYSTEMS,
    decentral_heat_buses,
    heat_injection_terms,
    times_heat_options,
)

NODE = "BEWAL"
BUSES = [f"{NODE} {system} heat" for system in DECENTRAL_HEAT_SYSTEMS]

# The four groups the toy network can express. `oil boiler` and `biomass boiler`
# are left out deliberately: the real payload always carries six, and the code
# must not assume a fixed set.
GROUP_META = {
    "heat pump": ("air heat pump", "Link"),
    "gas boiler": ("gas boiler", "Link"),
    "resistive heater": ("resistive heater", "Link"),
    SOLAR_GROUP: ("solar thermal", "Generator"),
}


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def _toy_network(cop: float = 3.0, hours: int = 48, vintages=("2025",)) -> pypsa.Network:
    """A miniature of the Walloon decentral heat system.

    Deliberately shares the shape of the real one: a winter-heavy load profile, a
    solar profile that is zero at night, several vintages per carrier, storage
    links on the same bus, and an unconstrained optimum that is heat-pump
    dominated (as the real 2025 network is).
    """
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2013-01-01", periods=hours, freq="6h"))
    n.snapshot_weightings.loc[:, :] = 6.0

    n.add("Bus", NODE, carrier="AC")
    n.add("Bus", f"{NODE} low voltage", carrier="low voltage")
    n.add("Bus", f"{NODE} gas", carrier="gas")
    for system in DECENTRAL_HEAT_SYSTEMS:
        n.add("Bus", f"{NODE} {system} heat", carrier=f"{system} heat")
    n.add("Bus", f"{NODE} urban central heat", carrier="urban central heat")

    n.add("Carrier", "gas", co2_emissions=0.198)
    n.add("Generator", f"{NODE} gas supply", bus=f"{NODE} gas", carrier="gas",
          p_nom=1e5, marginal_cost=40)
    n.add("Generator", f"{NODE} elec", bus=NODE, p_nom=1e5, marginal_cost=60)
    n.add("Link", f"{NODE} distribution", bus0=NODE, bus1=f"{NODE} low voltage",
          p_nom=1e5, efficiency=1.0)

    # Winter-heavy heat load, and a solar profile that is zero at night — the two
    # shapes whose interaction the reconstruction has to get right.
    t = np.arange(hours)
    demand = 100 + 60 * np.cos(2 * np.pi * t / hours)
    daylight = np.where(t % 4 == 1, 0.6, np.where(t % 4 == 2, 0.4, 0.0))

    for system in DECENTRAL_HEAT_SYSTEMS:
        heat = f"{NODE} {system} heat"
        scale = 1.0 if system == "rural" else 1.3
        for vintage in vintages:
            n.add("Link", f"{NODE} {system} gas boiler-{vintage}", bus0=f"{NODE} gas",
                  bus1=heat, carrier=f"{system} gas boiler", efficiency=0.9,
                  p_nom_extendable=True, capital_cost=1e-3)
            n.add("Link", f"{NODE} {system} resistive heater-{vintage}",
                  bus0=f"{NODE} low voltage", bus1=heat,
                  carrier=f"{system} resistive heater", efficiency=0.99,
                  p_nom_extendable=True, capital_cost=1e-3)
            # Reversed heat pump: bus0 is the heat bus, efficiency = 1/COP.
            n.add("Link", f"{NODE} {system} air heat pump-{vintage}", bus0=heat,
                  bus1=f"{NODE} low voltage", carrier=f"{system} air heat pump",
                  efficiency=1 / cop, p_max_pu=0.0, p_min_pu=-1.0,
                  p_nom_extendable=True, capital_cost=1e-3)
            # Expensive enough that the unconstrained optimum builds none, as in
            # the real model (PyPSA-Wal builds 0.01 MW of BEWAL solar thermal).
            n.add("Generator", f"{NODE} {system} solar thermal collector-{vintage}",
                  bus=heat, carrier=f"{system} solar thermal", p_nom_extendable=True,
                  capital_cost=1e4,
                  p_max_pu=pd.Series(daylight, index=n.snapshots))
        # Storage on the same bus: must never be selected as a supply technology.
        n.add("Bus", f"{NODE} {system} water tanks", carrier=f"{system} water tanks")
        n.add("Link", f"{NODE} {system} water tanks charger-2025", bus0=heat,
              bus1=f"{NODE} {system} water tanks",
              carrier=f"{system} water tanks charger", p_nom=10.0)
        n.add("Link", f"{NODE} {system} water tanks discharger-2025",
              bus0=f"{NODE} {system} water tanks", bus1=heat,
              carrier=f"{system} water tanks discharger", p_nom=10.0)
        n.add("Store", f"{NODE} {system} water tanks-2025",
              bus=f"{NODE} {system} water tanks", carrier=f"{system} water tanks",
              e_nom=50.0)
        # The heat vent, so over-supply has somewhere to go, exactly as in the
        # real network (a Generator with p_max_pu = 0, p_min_pu = -1).
        n.add("Generator", f"{NODE} {system} heat vent", bus=heat,
              carrier=f"{system} heat vent", p_nom=1e4, p_max_pu=0.0,
              p_min_pu=-1.0, marginal_cost=-0.02, sign=1.0)
        n.add("Load", f"{NODE} {system} heat", bus=heat,
              p_set=pd.Series(demand * scale, index=n.snapshots))

    # A static load on the tertiary decentral bus, like `BEWAL agriculture heat`.
    n.add("Load", f"{NODE} agriculture heat", bus=f"{NODE} urban decentral heat",
          p_set=5.0)
    n.add("Link", f"{NODE} urban central gas boiler-2025", bus0=f"{NODE} gas",
          bus1=f"{NODE} urban central heat", carrier="urban central gas boiler",
          efficiency=0.9, p_nom_extendable=True, capital_cost=1.0)
    return n


def _targets_frame(shares: dict[str, float]) -> pd.DataFrame:
    rows = [
        {
            "year": 2025,
            "group": group,
            "scope": "decentral",
            "constrained": True,
            "pypsa_component": GROUP_META[group][1],
            "pypsa_carriers": GROUP_META[group][0],
            "sense": "==",
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


def _mock_snakemake(tmp_path, targets: pd.DataFrame, **profile) -> SimpleNamespace:
    path = tmp_path / "heating_targets_2025.csv"
    targets.to_csv(path, index=False)
    return SimpleNamespace(
        config={
            "sector": {
                "times_heat": {
                    "node": NODE,
                    "profile": {"enable": True, "export": False, **profile},
                }
            }
        },
        input=SimpleNamespace(heating_targets=str(path)),
        wildcards=SimpleNamespace(planning_horizons="2025"),
        log=None,
        output=SimpleNamespace(network=str(tmp_path / "out.nc")),
    )


SHARES = {
    "heat pump": 0.10,
    "gas boiler": 0.60,
    "resistive heater": 0.25,
    SOLAR_GROUP: 0.05,
}


# --------------------------------------------------------------------------- #
# Options
# --------------------------------------------------------------------------- #


def test_profile_defaults_to_off_and_to_the_heat_pump_absorber():
    opts = times_heat_options({})
    assert opts["profile"]["enable"] is False
    assert opts["profile"]["absorber"] == "heat pump"
    assert opts["profile"]["penalty"] == 1000.0
    assert opts["profile"]["free_groups"] == []


def test_enabling_both_mechanisms_is_refused():
    """They impose the same information through incompatible constraints."""
    with pytest.raises(ValueError, match="alternative mechanisms"):
        times_heat_options(
            {
                "sector": {
                    "times_heat": {
                        "energy_mix": {"enable": True},
                        "profile": {"enable": True},
                    }
                }
            }
        )


def test_option_c_options_are_untouched_by_the_new_block():
    opts = times_heat_options({"sector": {"times_heat": {"profile": {"enable": True}}}})
    assert opts["energy_mix"]["enable"] is False
    assert opts["energy_mix"]["mode"] == "share"
    assert opts["energy_mix"]["tolerance"] == 0.05


@pytest.mark.parametrize(
    "block, match",
    [
        ({"profile": {"absorber": ""}}, "absorber"),
        ({"profile": {"penalty": -1}}, "penalty"),
    ],
)
def test_bad_profile_options_are_rejected(block, match):
    with pytest.raises(ValueError, match=match):
        times_heat_options({"sector": {"times_heat": block}})


# --------------------------------------------------------------------------- #
# The load, which is where the quiet 0.5 % error lives
# --------------------------------------------------------------------------- #


def test_decentral_load_includes_the_static_agriculture_load():
    n = _toy_network()
    buses = decentral_heat_buses(n, NODE)
    load = decentral_heat_load(n, buses, n.snapshots)
    urban = f"{NODE} urban decentral heat"
    expected = n.loads_t.p_set[f"{NODE} urban decentral heat"] + 5.0
    assert np.allclose(load[urban].to_numpy(), expected.to_numpy())
    assert list(load.columns) == list(buses)


def test_decentral_load_ignores_the_urban_central_bus():
    n = _toy_network()
    n.add("Load", f"{NODE} district heating", bus=f"{NODE} urban central heat",
          p_set=1000.0)
    buses = decentral_heat_buses(n, NODE)
    load = decentral_heat_load(n, buses, n.snapshots)
    assert float(load.to_numpy().max()) < 1000.0


# --------------------------------------------------------------------------- #
# Solar thermal availability
# --------------------------------------------------------------------------- #


def test_solar_availability_returns_the_collector_profile():
    n = _toy_network()
    avail = solar_availability(n, f"{NODE} rural heat", n.snapshots)
    assert avail.max() == pytest.approx(0.6)
    assert (avail == 0).sum() > 0, "the profile must be zero at night"


def test_divergent_solar_vintages_are_refused():
    """Averaging two disagreeing profiles would hide a network change."""
    n = _toy_network(vintages=("2025", "2030"))
    name = f"{NODE} rural solar thermal collector-2030"
    n.generators_t.p_max_pu[name] = pd.Series(0.9, index=n.snapshots)
    with pytest.raises(ValueError, match="different p_max_pu"):
        solar_availability(n, f"{NODE} rural heat", n.snapshots)


def test_missing_solar_generator_is_a_clear_error():
    n = _toy_network()
    n.remove("Generator", [g for g in n.generators.index if "solar thermal" in g])
    with pytest.raises(ValueError, match="No solar-thermal generator"):
        solar_availability(n, f"{NODE} rural heat", n.snapshots)


# --------------------------------------------------------------------------- #
# The reconstruction — the two identities everything rests on
# --------------------------------------------------------------------------- #


@pytest.fixture
def reconstruction():
    n = _toy_network()
    buses = decentral_heat_buses(n, NODE)
    load = decentral_heat_load(n, buses, n.snapshots)
    avail = pd.DataFrame(
        {bus: solar_availability(n, bus, n.snapshots) for bus in buses}
    )
    w = n.snapshot_weightings.generators
    return n, load, avail, w, reconstruct_profiles(load, pd.Series(SHARES), avail, w)


def test_profiles_close_on_the_load_at_every_snapshot(reconstruction):
    _n, load, _avail, _w, profiles = reconstruction
    total = sum(profiles.values())
    assert np.allclose(total.to_numpy(), load.to_numpy(), rtol=1e-12, atol=1e-9)


def test_profiles_reproduce_the_times_shares_exactly(reconstruction):
    _n, load, _avail, w, profiles = reconstruction
    annual = float(load.mul(w, axis=0).to_numpy().sum())
    for group, share in SHARES.items():
        got = float(profiles[group].mul(w, axis=0).to_numpy().sum())
        assert got == pytest.approx(share * annual, rel=1e-12)


def test_each_bus_gets_the_same_mix(reconstruction):
    """Per-bus, not summed over both: the model must not sort technologies."""
    _n, _load, _avail, w, profiles = reconstruction
    for bus in BUSES:
        per_bus = pd.Series(
            {g: float((f[bus] * w).sum()) for g, f in profiles.items()}
        )
        shares = per_bus / per_bus.sum()
        for group, want in SHARES.items():
            assert shares[group] == pytest.approx(want, rel=1e-10)


def test_solar_follows_its_own_availability_not_the_load(reconstruction):
    """A load-shaped solar target peaks in January and is instantly infeasible."""
    _n, _load, avail, _w, profiles = reconstruction
    solar = profiles[SOLAR_GROUP][BUSES[0]]
    dark = avail[BUSES[0]] == 0
    assert (solar[dark] == 0).all()
    ratio = (solar[~dark] / avail[BUSES[0]][~dark]).round(9)
    assert ratio.nunique() == 1, "solar must be proportional to its availability"


def test_other_groups_share_the_residual_not_the_full_load(reconstruction):
    _n, load, _avail, _w, profiles = reconstruction
    residual = load - profiles[SOLAR_GROUP]
    gas = profiles["gas boiler"]
    expected = residual * (SHARES["gas boiler"] / (1 - SHARES[SOLAR_GROUP]))
    assert np.allclose(gas.to_numpy(), expected.to_numpy())


def test_a_zero_share_gives_a_zero_profile(reconstruction):
    """Option C needed `zero_target: forbid` for this; B' gets it for free."""
    _n, load, avail, w, _profiles = reconstruction
    shares = pd.Series({**SHARES, "gas boiler": 0.60 + 0.25, "resistive heater": 0.0})
    profiles = reconstruct_profiles(load, shares, avail, w)
    assert float(profiles["resistive heater"].abs().to_numpy().max()) == 0.0


def test_a_zero_solar_share_is_still_pinned_to_zero(reconstruction):
    """Solar is built by a different branch, so its zero case needs its own test.

    Left out of the profile set it would be *unconstrained*, free to produce, and
    the extra heat would have to be vented — quietly breaking both the closure and
    the mix.
    """
    _n, load, avail, w, _profiles = reconstruction
    shares = pd.Series({**SHARES, SOLAR_GROUP: 0.0, "gas boiler": 0.65})
    profiles = reconstruct_profiles(load, shares, avail, w)
    assert SOLAR_GROUP in profiles
    assert float(profiles[SOLAR_GROUP].abs().to_numpy().max()) == 0.0


def test_shares_that_do_not_sum_to_one_are_refused(reconstruction):
    _n, load, avail, w, _profiles = reconstruction
    with pytest.raises(ValueError, match="sum to"):
        reconstruct_profiles(load, pd.Series({"gas boiler": 0.9}), avail, w)


def test_a_solar_share_larger_than_the_load_is_refused(reconstruction):
    """The one way the reconstruction itself can produce an infeasible target."""
    _n, load, avail, w, _profiles = reconstruction
    shares = pd.Series({SOLAR_GROUP: 0.9, "gas boiler": 0.1})
    with pytest.raises(ValueError, match="exceeds the heat load"):
        reconstruct_profiles(load, shares, avail, w)


# --------------------------------------------------------------------------- #
# End to end
# --------------------------------------------------------------------------- #


def _realised(n: pypsa.Network) -> pd.DataFrame:
    """Heat delivered per group and snapshot, MW, from a solved network."""
    buses = decentral_heat_buses(n, NODE)
    out = {}
    for group, (carrier, component) in GROUP_META.items():
        index, coeffs = heat_injection_terms(n, buses, [carrier], component)
        p = n.links_t.p0 if component == "Link" else n.generators_t.p
        out[group] = (p[index] * coeffs).sum(axis=1)
    return pd.DataFrame(out)


def test_pinned_profiles_deliver_the_times_mix_at_every_snapshot(tmp_path):
    """The claim option B' exists to make, checked hour by hour rather than annually."""
    free = _toy_network()
    free.optimize(solver_name="highs")
    baseline = _realised(free)
    w = free.snapshot_weightings.generators
    annual = baseline.mul(w, axis=0).sum()
    assert annual["heat pump"] / annual.sum() > 0.5, "toy must favour the heat pump"

    n = _toy_network()
    snakemake = _mock_snakemake(tmp_path, _targets_frame(SHARES))
    status, condition = n.optimize(
        solver_name="highs",
        extra_functionality=lambda net, sns: add_times_heat_profile_constraints(
            net, sns, snakemake
        ),
    )
    assert (status, condition) == ("ok", "optimal")

    realised = _realised(n)

    # Every *pinned* group tracks its reconstructed profile exactly, snapshot by
    # snapshot. This is the claim option B' exists to make.
    for group in SHARES:
        if group == "heat pump":
            continue  # the absorber — see below and the dedicated test
        assert np.allclose(
            realised[group].to_numpy(),
            _reference_profile(n, group).to_numpy(),
            atol=1e-6,
        ), f"{group}: realised dispatch strays from its reconstructed profile"

    # The absorber is pinned in *energy* by the bus balance, not by a row, so it
    # may still shift within the horizon through the water tank.
    annual = realised.mul(w, axis=0).sum()
    reference = _reference_profile(n, "heat pump").mul(w).sum()
    assert annual["heat pump"] == pytest.approx(reference, rel=1e-6)

    # Annually the mix is TIMES's exactly — no tolerance, unlike option C.
    for group, want in SHARES.items():
        assert annual[group] / annual.sum() == pytest.approx(want, rel=1e-6)

    # Hourly, the *pinned non-solar* groups hold a constant ratio to one another,
    # because solar necessarily follows the sun and the rest share the residual.
    pinned = realised[["gas boiler", "resistive heater"]]
    ratio = (pinned["gas boiler"] / pinned["resistive heater"]).round(9)
    assert ratio.nunique() == 1

    assert n.objective > free.objective, "the TIMES mix must cost more than the optimum"


def test_the_absorber_keeps_the_decentral_storage_degree_of_freedom(tmp_path):
    """B' pins the mix, not the total: the unpinned group may still use the tank.

    In the real network this is worth almost nothing — the optimised decentral
    water tanks are 0.13 MWh for the whole of rural Wallonia and cycle 0.008-0.017
    TWh a year, against 0.2-2.7 TWh in the district-heating pit store, which B'
    does not touch. The toy tank is lossless and free, so it is used, which is
    what makes the degree of freedom visible here.
    """
    n = _toy_network()
    snakemake = _mock_snakemake(tmp_path, _targets_frame(SHARES))
    n.optimize(
        solver_name="highs",
        extra_functionality=lambda net, sns: add_times_heat_profile_constraints(
            net, sns, snakemake
        ),
    )
    charged = sum(
        float(n.links_t.p0[name].sum())
        for name in n.links.index
        if "water tanks charger" in name
    )
    assert charged > 0, "the absorber should still be able to use the tank"

    realised = _realised(n)
    deviation = realised["heat pump"] - _reference_profile(n, "heat pump")
    assert float(deviation.abs().max()) > 0, "absorber is free within the horizon"
    # …but only within it: over the whole horizon the storage nets out.
    w = n.snapshot_weightings.generators
    assert float((deviation * w).sum()) == pytest.approx(0.0, abs=1e-3)


def test_every_vintage_of_a_carrier_counts_towards_the_profile(tmp_path):
    """Brownfield vintages dispatch too; pinning only the newest would double-count."""
    n = _toy_network(vintages=("2025", "2030"))
    snakemake = _mock_snakemake(tmp_path, _targets_frame(SHARES))
    status, condition = n.optimize(
        solver_name="highs",
        extra_functionality=lambda net, sns: add_times_heat_profile_constraints(
            net, sns, snakemake
        ),
    )
    assert (status, condition) == ("ok", "optimal")
    realised = _realised(n)
    assert np.allclose(
        realised["gas boiler"].to_numpy(),
        _reference_profile(n, "gas boiler").to_numpy(),
        atol=1e-6,
    )
    # both vintages of the pinned carrier are inside the constraint, so the
    # split between them stays endogenous while the total is fixed
    gas_links = [i for i in n.links.index if "rural gas boiler" in i]
    assert len(gas_links) == 2


def test_the_absorber_is_not_pinned(tmp_path):
    n = _toy_network()
    snakemake = _mock_snakemake(tmp_path, _targets_frame(SHARES))
    n.optimize.create_model()
    add_times_heat_profile_constraints(n, n.snapshots, snakemake)
    names = set(n.model.constraints)
    for bus in BUSES:
        assert f"times_heat_profile_heat pump_{bus}" not in names
        assert f"times_heat_profile_gas boiler_{bus}" in names


def test_free_groups_are_not_pinned(tmp_path):
    n = _toy_network()
    snakemake = _mock_snakemake(
        tmp_path, _targets_frame(SHARES), free_groups=["gas boiler"]
    )
    n.optimize.create_model()
    add_times_heat_profile_constraints(n, n.snapshots, snakemake)
    names = set(n.model.constraints)
    for bus in BUSES:
        assert f"times_heat_profile_gas boiler_{bus}" not in names
        assert f"times_heat_profile_resistive heater_{bus}" in names


def test_disabled_option_adds_no_constraint(tmp_path):
    n = _toy_network()
    snakemake = _mock_snakemake(tmp_path, _targets_frame(SHARES))
    snakemake.config["sector"]["times_heat"]["profile"]["enable"] = False
    n.optimize.create_model()
    before = set(n.model.constraints)
    add_times_heat_profile_constraints(n, n.snapshots, snakemake)
    assert set(n.model.constraints) == before


def test_missing_targets_input_is_a_clear_error():
    n = _toy_network()
    snakemake = SimpleNamespace(
        config={"sector": {"times_heat": {"profile": {"enable": True}}}},
        input=SimpleNamespace(heating_targets=[]),
    )
    with pytest.raises(ValueError, match="heating_targets"):
        add_times_heat_profile_constraints(n, n.snapshots, snakemake)


def test_an_absorber_that_is_not_a_group_is_refused(tmp_path):
    n = _toy_network()
    snakemake = _mock_snakemake(tmp_path, _targets_frame(SHARES), absorber="oil boiler")
    n.optimize.create_model()
    with pytest.raises(ValueError, match="not a constrained TIMES heat group"):
        add_times_heat_profile_constraints(n, n.snapshots, snakemake)


def test_a_group_with_no_component_is_refused(tmp_path):
    """Silently dropping it would break closure and change the mix without a word."""
    n = _toy_network()
    n.remove("Link", [i for i in n.links.index if "resistive heater" in i])
    snakemake = _mock_snakemake(tmp_path, _targets_frame(SHARES))
    n.optimize.create_model()
    with pytest.raises(ValueError, match="cannot be delivered"):
        add_times_heat_profile_constraints(n, n.snapshots, snakemake)


# --------------------------------------------------------------------------- #
# The relaxation — the property the myopic chain depends on
# --------------------------------------------------------------------------- #


def test_penalty_turns_an_impossible_mix_into_a_priced_relaxation(tmp_path):
    """No TIMES mix may make the LP infeasible.

    An infeasible sector LP does not merely fail: ``solve_network.py`` then calls
    ``compute_infeasibilities()``, a Gurobi IIS over ~1.3 M rows which ran 13 h
    without finishing on the 2040 network and blocked the whole myopic chain.
    Here the 2040 situation is reproduced in miniature by starving the gas supply.
    """
    hard = _toy_network()
    hard.generators.loc[f"{NODE} gas supply", "p_nom"] = 5.0
    sm_hard = _mock_snakemake(tmp_path, _targets_frame(SHARES), penalty=0.0)
    status, _ = hard.optimize(
        solver_name="highs",
        extra_functionality=lambda net, sns: add_times_heat_profile_constraints(
            net, sns, sm_hard
        ),
    )
    assert status != "ok", "penalty 0 must be a hard constraint"

    soft = _toy_network()
    soft.generators.loc[f"{NODE} gas supply", "p_nom"] = 5.0
    sm_soft = _mock_snakemake(tmp_path, _targets_frame(SHARES), penalty=1000.0)
    status, condition = soft.optimize(
        solver_name="highs",
        extra_functionality=lambda net, sns: add_times_heat_profile_constraints(
            net, sns, sm_soft
        ),
    )
    assert (status, condition) == ("ok", "optimal")

    unmet = soft.model.variables["TimesHeatProfile-unmet"].solution.to_series()
    assert unmet["gas boiler"] > 1.0, "the starved group must be the one that relaxes"
    assert unmet.drop("gas boiler").max() == pytest.approx(0.0, abs=1e-6)


def test_no_relaxation_is_used_when_the_mix_is_deliverable(tmp_path):
    n = _toy_network()
    snakemake = _mock_snakemake(tmp_path, _targets_frame(SHARES))
    n.optimize(
        solver_name="highs",
        extra_functionality=lambda net, sns: add_times_heat_profile_constraints(
            net, sns, snakemake
        ),
    )
    unmet = n.model.variables["TimesHeatProfile-unmet"].solution.to_series()
    assert float(unmet.max()) == pytest.approx(0.0, abs=1e-6)


def test_relaxation_is_spread_over_the_year_not_concentrated(tmp_path):
    """A per-snapshot slack would let the model relax only in expensive hours,
    re-creating exactly the hourly substitution freedom option B' removes."""
    n = _toy_network()
    n.generators.loc[f"{NODE} gas supply", "p_nom"] = 5.0
    snakemake = _mock_snakemake(tmp_path, _targets_frame(SHARES))
    n.optimize(
        solver_name="highs",
        extra_functionality=lambda net, sns: add_times_heat_profile_constraints(
            net, sns, snakemake
        ),
    )
    realised = _realised(n)
    gas = realised["gas boiler"]
    target = _reference_profile(n, "gas boiler")
    ratio = (gas / target.where(target > 0)).dropna().round(6)
    assert ratio.nunique() == 1, "the shortfall must be proportional, not selective"


def _reference_profile(n: pypsa.Network, group: str) -> pd.Series:
    buses = decentral_heat_buses(n, NODE)
    load = decentral_heat_load(n, buses, n.snapshots)
    avail = pd.DataFrame(
        {bus: solar_availability(n, bus, n.snapshots) for bus in buses}
    )
    w = n.snapshot_weightings.generators
    return reconstruct_profiles(load, pd.Series(SHARES), avail, w)[group].sum(axis=1)
