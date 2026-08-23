# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Guards for the three-profile EV charging split.

Three properties, none checked anywhere else:

1. **The split conserves energy at the grid meter.** The flexible load sits on
   the EV-battery bus behind the BEV-charger link, which applies
   `bev_charge_efficiency`; the inflexible load sits directly on the AC bus and
   does not. Whichever way the two are aligned, the total drawn from the grid must
   equal the transferred demand — with `times_demand` that demand is the TIMES
   `electricity road` flow, metered upstream of TIMES's own 0.95 charger
   efficiency, so grossing it up again counts the loss twice.
   `docs/ev-charging-softlink.md` §3.1.
2. **The Elia mode weights are mutually consistent.** `bev_dsm_availability` and
   `local_bev_dsm` are two config keys carved out of one Elia row with different
   denominators, so `local_bev_dsm.natural × (1 − bev_dsm_availability)` is what
   must match Elia's `V0`. §3b.
3. **No `config.default.yaml` value leaks into a Walloon horizon.** These options
   are dicts and `update_config` merges dicts key by key, so a horizon a Walloon
   config does not list silently inherits the PyPSA-Eur default — 0.5 for
   `bev_dsm_availability`, 0.0 for `bev_avail_min`.
4. **A scenario overlay that overrides the weights obeys the same three, and
   stays a pure EV delta.** `scen_evflex` exists to be diffed against
   `scen_demande_haute`, which only means anything if the two share a TIMES vd
   and a nuclear trajectory. §4.6.
5. **`p_nom`/`e_nom` scale on the *fleet* share, the load on the *energy* share.**
   The two answer different questions and TIMES exports both; using the energy
   ratio for a vehicle count understated the flexible fleet 3.7× at 2030. The
   count and the share must also come from the same vehicle classes, or their
   product is not a BEV count. §2.
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from snakemake.utils import update_config

from scripts.build_transport_demand import split_transport_demand
from scripts.prepare_sector_network import EV_FLEET_CLASSES, times_ev_fleet

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "config.default.yaml"
#: config.times-pypsa.yaml was folded into config.walloon.yaml (7225e6fb), so
#: there is one study config, plus one entry per scenario overlay that overrides
#: an EV weight key -- an overlay is what a run actually sees, so the invariants
#: have to hold on the merged result, not only on the base config.
BASE_CONFIG = ROOT / "config" / "config.walloon.yaml"
SCENARIO_FILE = ROOT / "config" / "scenarios.walloon.yaml"
#: The scenario `scen_evflex` is a sensitivity *on*: only the EV weights may
#: differ, or the diff stops being an EV-flexibility diff. §4.6.
EVFLEX_BASELINE = "scen_demande_haute"
ELIA_DIR = ROOT / "data" / "walloon" / "elia_adeqflex2025"

#: Dict-valued sector options whose horizons must be fully listed.
YEARLY_KEYS = (
    "bev_dsm_availability",
    "bev_avail_max",
    "bev_avail_mean",
    "bev_avail_min",
    "local_bev_dsm",
)


def _scenarios() -> dict:
    return yaml.safe_load(SCENARIO_FILE.read_text())


def _ev_overlays() -> dict[str, dict]:
    """Scenario overlays that override either EV weight key."""
    return {
        name: overlay
        for name, overlay in _scenarios().items()
        if set((overlay.get("sector") or {})) & {"bev_dsm_availability", "local_bev_dsm"}
    }


def _merged(name: str) -> tuple[dict, dict]:
    """`(what the config/overlay itself says, the config a run would see)`.

    ``name`` is either the base config's file name or a scenario key; a scenario
    is layered on top of the base config the way snakemake's scenario mechanism
    does, so an overlay is checked as it will actually be used.
    """
    own = yaml.safe_load(BASE_CONFIG.read_text())
    if name != BASE_CONFIG.name:
        update_config(own, _scenarios()[name])
    cfg = copy.deepcopy(yaml.safe_load(DEFAULT_CONFIG.read_text()))
    update_config(cfg, own)
    return own, cfg


#: The base config, then every scenario overlay that touches an EV weight.
CONFIG_FILES = (BASE_CONFIG.name, *sorted(_ev_overlays()))


@pytest.mark.parametrize("path", CONFIG_FILES)
def test_no_default_year_leaks_in(path: str):
    """A horizon the config does not list inherits the PyPSA-Eur default."""
    own, cfg = _merged(path)
    mine = own.get("sector") or {}
    leaks = {}
    for key in YEARLY_KEYS:
        if not isinstance(cfg["sector"].get(key), dict):
            continue
        listed = set(mine.get(key) or {})
        if not listed:
            continue
        extra = sorted(set(cfg["sector"][key]) - listed)
        if extra:
            leaks[key] = {y: cfg["sector"][key][y] for y in extra}
    if leaks:
        pytest.fail(
            f"{path}: config.default.yaml values leak into unlisted years "
            f"{leaks}. List every year config.default.yaml lists, or a run at that "
            "horizon silently takes the PyPSA-Eur default (0.5 for "
            "bev_dsm_availability, 0.0 for bev_avail_min)."
        )


@pytest.mark.parametrize("path", CONFIG_FILES)
def test_every_horizon_has_charging_weights(path: str):
    _, cfg = _merged(path)
    horizons = [int(y) for y in cfg["scenario"]["planning_horizons"]]
    weights = cfg["sector"]["local_bev_dsm"]
    missing = [h for h in horizons if h not in weights]
    assert not missing, (
        f"{path}: sector.local_bev_dsm has no entry for {missing}; "
        "build_natural_charging_shape would fall back to an earlier horizon."
    )


@pytest.mark.parametrize("path", CONFIG_FILES)
def test_charging_weights_sum_to_one(path: str):
    _, cfg = _merged(path)
    for year, block in cfg["sector"]["local_bev_dsm"].items():
        total = sum(block.values())
        assert abs(total - 1.0) < 1e-4, (
            f"{path}: local_bev_dsm[{year}] sums to {total}, not 1 — "
            "build_natural_charging_shape asserts on this."
        )


@pytest.mark.parametrize("path", CONFIG_FILES)
def test_weights_name_real_profile_columns(path: str):
    _, cfg = _merged(path)
    profile = ROOT / cfg["sector"]["bev_natural_charging_profile_fn"]
    assert profile.exists(), f"{path}: missing {profile}"
    columns = set(pd.read_csv(profile).columns) - {"hour", "year"}
    for year, block in cfg["sector"]["local_bev_dsm"].items():
        unknown = sorted(set(block) - columns)
        assert not unknown, (
            f"{path}: local_bev_dsm[{year}] names {unknown}, which are not "
            f"columns of {profile.name} ({sorted(columns)})."
        )


def test_split_draws_exactly_the_transferred_demand():
    """Regression: the charger loss must be counted once, not twice.

    With `times_demand`, `profile` is the TIMES `electricity road` flow, metered
    at `fuel_input` — upstream of TIMES's own 0.95 charger efficiency. The
    flexible branch passes through PyPSA's BEV charger, so it must be scaled
    *down* by `bev_charge_efficiency`; grossing the inflexible branch *up*
    instead puts the total 1/eff above the transferred demand.
    """
    hours = pd.date_range("2013-01-01", periods=48, freq="h")
    shape = pd.DataFrame(1.0 / len(hours), index=hours, columns=["BEWAL"])
    total = 3.393e6
    profile = shape * total
    dsm, eff = 0.07, 0.9

    flexible, inflexible = split_transport_demand(profile, shape, dsm)
    assert np.isclose(flexible.sum().sum() + inflexible.sum().sum(), total, rtol=1e-9)

    # What add_EVs does now: scale the flexible load down.
    grid = (flexible.sum().sum() * eff) / eff + inflexible.sum().sum()
    assert np.isclose(grid, total, rtol=1e-9), (
        f"grid draw {grid:.1f} != transferred demand {total:.1f}"
    )

    # What the branch did: gross the inflexible load up. Kept as the counter-case
    # so the regression is unambiguous.
    grid_bad = flexible.sum().sum() / eff + inflexible.sum().sum() / eff
    assert grid_bad > total * 1.10, "the counter-case no longer overshoots"


def test_add_evs_scales_the_flexible_branch_not_the_inflexible_one():
    """Pin the direction of the correction in the source."""
    source = (ROOT / "scripts" / "prepare_sector_network.py").read_text()
    assert 'profile_flexible *= options["bev_charge_efficiency"]' in source, (
        "add_EVs no longer scales the flexible load by the charge efficiency"
    )
    assert 'profile_inflexible /= options["bev_charge_efficiency"]' not in source, (
        "add_EVs grosses the inflexible load up again — that counts TIMES's own "
        "0.95 charger efficiency twice. docs/ev-charging-softlink.md §3.1"
    )


@pytest.mark.skipif(not ELIA_DIR.exists(), reason="Elia reference tables not extracted")
@pytest.mark.parametrize("path", CONFIG_FILES)
def test_mode_weights_track_an_elia_scenario(path: str):
    """`natural x (1 - market)` must match some Elia scenario's V0 share.

    Not pinned to one scenario -- the point is that the pair is internally
    consistent, i.e. it corresponds to a real Elia cell rather than mixing the
    market share of one case with the natural/local split of another.
    """
    _, cfg = _merged(path)
    modes = pd.read_csv(ELIA_DIR / "ev_operation_mode_shares.csv")
    piv = modes.pivot_table(index=["scenario", "year"], columns="mode", values="share")
    piv["natural"] = piv["V0"]
    piv["market"] = piv[["V1M", "V2M"]].sum(axis=1)

    horizons = [int(y) for y in cfg["scenario"]["planning_horizons"]]
    offenders = []
    for h in horizons:
        market = cfg["sector"]["bev_dsm_availability"][h]
        natural_abs = cfg["sector"]["local_bev_dsm"][h]["natural"] * (1 - market)
        elia_year = min(h, int(piv.index.get_level_values("year").max()))
        cells = piv.xs(elia_year, level="year")
        # closest Elia scenario on the market share, then check natural agrees
        best = (cells["market"] - market).abs().idxmin()
        if abs(cells.loc[best, "natural"] - natural_abs) > 0.05:
            offenders.append(
                f"{h}: market {market:.3f} is closest to Elia {best!r} "
                f"({cells.loc[best, 'market']:.3f}), whose V0 is "
                f"{cells.loc[best, 'natural']:.3f}, but the config implies "
                f"{natural_abs:.3f}"
            )
    if offenders:
        pytest.fail(
            f"{path}: the mode weights mix Elia scenarios —\n  "
            + "\n  ".join(offenders)
            + "\nDerive both keys from one (scenario, year) cell: "
            "python scripts/walloon_scripts/build_ev_charging_weights.py"
        )


def _generator():
    """`build_ev_charging_weights` loaded by path.

    `scripts/walloon_scripts` is not a package, and making it one to run one test
    would change how every script in it is invoked.
    """
    path = ROOT / "scripts" / "walloon_scripts" / "build_ev_charging_weights.py"
    spec = importlib.util.spec_from_file_location("build_ev_charging_weights", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # DATA is relative to the repo root; pytest may be invoked from elsewhere.
    module.DATA = ROOT / module.DATA
    return module


@pytest.mark.skipif(not ELIA_DIR.exists(), reason="Elia reference tables not extracted")
def test_evflex_block_is_exactly_what_the_generator_produces():
    """`scen_evflex` must be regenerated, never hand-edited.

    Hand-editing one horizon of one key is the failure mode the whole generator
    exists to prevent: the two keys have different denominators, so a plausible
    edit to either silently describes no real Elia case. Pinning the block to the
    generator's output makes an edit a test failure rather than a silent one.
    §4.6.
    """
    overlay = _scenarios()["scen_evflex"]["sector"]
    gen = _generator()
    produced = gen.weights(
        "Current commitments - High Flex",
        tuple(sorted(overlay["local_bev_dsm"])),
        extrapolate=True,
    )
    assert overlay["bev_dsm_availability"] == produced["bev_dsm_availability"], (
        "scen_evflex.sector.bev_dsm_availability drifted from the generator. "
        "Regenerate both keys together: build_ev_charging_weights.py "
        '--scenario "Current commitments - High Flex" --extrapolate'
    )
    assert overlay["local_bev_dsm"] == produced["local_bev_dsm"], (
        "scen_evflex.sector.local_bev_dsm drifted from the generator. Regenerate "
        "both keys together -- editing one alone mixes denominators."
    )


@pytest.mark.skipif(not ELIA_DIR.exists(), reason="Elia reference tables not extracted")
@pytest.mark.parametrize("path", CONFIG_FILES)
def test_flexible_share_stays_under_the_public_charging_ceiling(path: str):
    """Elia assumes no flexibility from public charging.

    Public-charged energy is unmanaged (`V0`) whatever the tariff or the
    aggregator does, so its share is a floor on the natural share and
    `1 - public` is a ceiling on everything steerable -- `bev_dsm_availability`
    included. Not binding in the base case (0.18 against 0.85); it is the
    binding constraint on the extrapolated case, which saturates against it.
    §4.6, and work item 9 in §6.
    """
    _, cfg = _merged(path)
    loc = pd.read_csv(ELIA_DIR / "ev_v0_location_shares.csv")
    public = loc[loc["location"] == "public"].set_index("year")["share"]
    ceiling = 1.0 - float(public.loc[public.index.max()])
    # `natural` is written to 3 decimals and the market share to 3, so a block
    # that saturates *on* the ceiling -- which the extrapolated 2050 does by
    # construction -- lands a rounding step either side of it.
    tol = 1e-3

    for year, market in cfg["sector"]["bev_dsm_availability"].items():
        natural_abs = cfg["sector"]["local_bev_dsm"][year]["natural"] * (1 - market)
        steerable = 1.0 - natural_abs
        assert market <= ceiling + tol, (
            f"{path}: bev_dsm_availability[{year}] = {market} exceeds "
            f"1 - public = {ceiling:.3f}; Elia assumes no flexibility from public "
            "charging, so the market share cannot legitimately be that high."
        )
        assert steerable <= ceiling + tol, (
            f"{path}: at {year} the steerable share (market + local) is "
            f"{steerable:.3f}, above 1 - public = {ceiling:.3f}. The natural share "
            "cannot fall below the public-charging share."
        )


@pytest.mark.skipif(not ELIA_DIR.exists(), reason="Elia reference tables not extracted")
def test_extrapolated_shares_are_monotone_in_absolute_terms():
    """The extrapolation must not invert the trend it continues.

    The check is on **absolute** fleet shares, not on the config numbers:
    `local_bev_dsm.natural` is renormalised over natural+local, so it legitimately
    *rises* after 2040 while the absolute natural share still falls. Reading
    monotonicity off the config key directly is the mistake this pins. §4.6.
    """
    overlay = _scenarios()["scen_evflex"]["sector"]
    years = sorted(overlay["local_bev_dsm"])
    natural, market = [], []
    for y in years:
        m = overlay["bev_dsm_availability"][y]
        natural.append(overlay["local_bev_dsm"][y]["natural"] * (1 - m))
        market.append(m)
    assert all(b <= a + 1e-9 for a, b in zip(natural, natural[1:])), (
        f"absolute natural share is not monotonically falling: "
        f"{dict(zip(years, natural))}"
    )
    assert all(b >= a - 1e-9 for a, b in zip(market, market[1:])), (
        f"market share is not monotonically rising: {dict(zip(years, market))}"
    )


def test_evflex_differs_from_its_baseline_only_in_the_ev_weights():
    """`scen_evflex` is a sensitivity *on* `scen_demande_haute`.

    A diff between the two is only an EV-flexibility diff if everything else --
    the TIMES vd above all, but also the nuclear trajectory and the aggregate
    capacity caps -- is identical. Copied rather than inherited, because the
    scenario mechanism has no inheritance, so nothing but this test stops the two
    from drifting when the study vd is updated. §4.6.
    """
    scenarios = _scenarios()
    evflex = copy.deepcopy(scenarios["scen_evflex"])
    baseline = copy.deepcopy(scenarios[EVFLEX_BASELINE])
    for key in ("bev_dsm_availability", "local_bev_dsm"):
        evflex["sector"].pop(key)
    assert evflex == baseline, (
        f"scen_evflex differs from {EVFLEX_BASELINE} outside the EV weight keys, "
        "so a diff between the two is no longer an EV-flexibility sensitivity. "
        f"Non-EV overrides must be copied from {EVFLEX_BASELINE} verbatim "
        f"(notably sector.times_file).\n  scen_evflex: {evflex}\n  "
        f"{EVFLEX_BASELINE}: {baseline}"
    )


# --- E1-E3: the fleet share for fleet quantities -----------------------------

FLEET_CSV = """\
year,vehicle_class,pypsa_engine_type,stock_kveh,activity_bvkm,stock_share,activity_share
2030,cars,electric,987.9,14.93,0.5294,0.4996
2030,cars,fuel_cell,0.0,0.0,0.0,0.0
2030,cars,ice,878.1,14.95,0.4706,0.5004
2030,light commercial vehicles,electric,0.1,0.0,0.0003,0.0003
2030,light commercial vehicles,fuel_cell,0.0,0.0,0.0,0.0
2030,light commercial vehicles,ice,308.7,5.64,0.9997,0.9997
"""


def test_times_ev_fleet_returns_count_and_share_from_the_same_classes(tmp_path):
    """Their product must be the BEV count, which is what `p_nom` is built from."""
    fn = tmp_path / "road_transport_2030_shares.csv"
    fn.write_text(FLEET_CSV)

    cars, share = times_ev_fleet(fn, classes=("cars",))
    assert cars == pytest.approx(1_866_000)
    assert share == pytest.approx(987.9 / 1866.0, rel=1e-6)
    assert cars * share == pytest.approx(987_900)

    # The class boundary is immaterial to the product: adding LDVs moves the
    # share a long way and the BEV count barely at all, because TIMES has ~0
    # electric vans. That is why picking one boundary for BOTH is what matters.
    wide_cars, wide_share = times_ev_fleet(
        fn, classes=("cars", "light commercial vehicles")
    )
    assert wide_share < share - 0.07
    assert wide_cars * wide_share == pytest.approx(cars * share, rel=1e-3)


def test_times_ev_fleet_rejects_an_unknown_vehicle_class(tmp_path):
    """A group-definition change that renames a class must not size the EVs at 0."""
    fn = tmp_path / "road_transport_2030_shares.csv"
    fn.write_text(FLEET_CSV)
    with pytest.raises(ValueError, match="no rows for vehicle class"):
        times_ev_fleet(fn, classes=("passenger cars",))


@pytest.mark.skipif(not ELIA_DIR.exists(), reason="Elia reference tables not extracted")
def test_default_fleet_classes_match_the_car_count_and_car_parameters():
    """`EV_FLEET_CLASSES` must stay the boundary `number cars` and `bev_energy` use.

    `bev_energy` (60 kWh) and `bev_charge_rate` (11 kW) are passenger-car
    figures, so widening the class set without revisiting them would put a
    car-sized battery in every van. §2.
    """
    assert EV_FLEET_CLASSES == ("cars",), (
        "EV_FLEET_CLASSES changed; bev_energy and bev_charge_rate are "
        "passenger-car parameters and `number cars` counts passenger cars, so "
        "widening the boundary needs all three revisited together."
    )


def test_fleet_quantities_do_not_use_the_energy_share():
    """Pin the split of the two shares in the source.

    Reverting `p_nom`/`e_nom` to `electric_share` is a silent 3.7× understatement
    at 2030 -- nothing in a solved network says which share sized the charger.
    """
    source = (ROOT / "scripts" / "prepare_sector_network.py").read_text()
    assert (
        'p_nom = number_cars * options["bev_charge_rate"] * electric_share_fleet'
        in source
    ), "the BEV charger p_nom no longer scales on the fleet share (E1)"
    assert (
        'p_nom = number_cars * options["bev_charge_rate"] * electric_share\n' not in source
    ), (
        "the BEV charger p_nom is back on the energy share; that understates the "
        "flexible fleet 3.7x at 2030. docs/ev-charging-softlink.md S2"
    )
    # The load must keep the energy share, or the grid draw stops matching TIMES.
    assert "profile[wallon_node] = electric_share[wallon_node] * profile[wallon_node]" in source, (
        "the Walloon EV load no longer uses the TIMES energy ratio, so its grid "
        "draw no longer equals the transferred `electricity road`. S3"
    )
