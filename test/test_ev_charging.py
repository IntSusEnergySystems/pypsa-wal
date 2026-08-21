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
"""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from snakemake.utils import update_config

from scripts.build_transport_demand import split_transport_demand

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "config.default.yaml"
#: config.times-pypsa.yaml was folded into config.walloon.yaml (7225e6fb), so
#: there is one study config. Kept as a tuple: scenario overlays may add more.
CONFIG_FILES = (ROOT / "config" / "config.walloon.yaml",)
ELIA_DIR = ROOT / "data" / "walloon" / "elia_adeqflex2025"

#: Dict-valued sector options whose horizons must be fully listed.
YEARLY_KEYS = (
    "bev_dsm_availability",
    "bev_avail_max",
    "bev_avail_mean",
    "bev_avail_min",
    "local_bev_dsm",
)


def _merged(path: Path) -> tuple[dict, dict]:
    own = yaml.safe_load(path.read_text())
    cfg = copy.deepcopy(yaml.safe_load(DEFAULT_CONFIG.read_text()))
    update_config(cfg, own)
    return own, cfg


@pytest.mark.parametrize("path", CONFIG_FILES, ids=lambda p: p.name)
def test_no_default_year_leaks_in(path: Path):
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
            f"{path.name}: config.default.yaml values leak into unlisted years "
            f"{leaks}. List every year config.default.yaml lists, or a run at that "
            "horizon silently takes the PyPSA-Eur default (0.5 for "
            "bev_dsm_availability, 0.0 for bev_avail_min)."
        )


@pytest.mark.parametrize("path", CONFIG_FILES, ids=lambda p: p.name)
def test_every_horizon_has_charging_weights(path: Path):
    _, cfg = _merged(path)
    horizons = [int(y) for y in cfg["scenario"]["planning_horizons"]]
    weights = cfg["sector"]["local_bev_dsm"]
    missing = [h for h in horizons if h not in weights]
    assert not missing, (
        f"{path.name}: sector.local_bev_dsm has no entry for {missing}; "
        "build_natural_charging_shape would fall back to an earlier horizon."
    )


@pytest.mark.parametrize("path", CONFIG_FILES, ids=lambda p: p.name)
def test_charging_weights_sum_to_one(path: Path):
    _, cfg = _merged(path)
    for year, block in cfg["sector"]["local_bev_dsm"].items():
        total = sum(block.values())
        assert abs(total - 1.0) < 1e-4, (
            f"{path.name}: local_bev_dsm[{year}] sums to {total}, not 1 — "
            "build_natural_charging_shape asserts on this."
        )


@pytest.mark.parametrize("path", CONFIG_FILES, ids=lambda p: p.name)
def test_weights_name_real_profile_columns(path: Path):
    _, cfg = _merged(path)
    profile = ROOT / cfg["sector"]["bev_natural_charging_profile_fn"]
    assert profile.exists(), f"{path.name}: missing {profile}"
    columns = set(pd.read_csv(profile).columns) - {"hour", "year"}
    for year, block in cfg["sector"]["local_bev_dsm"].items():
        unknown = sorted(set(block) - columns)
        assert not unknown, (
            f"{path.name}: local_bev_dsm[{year}] names {unknown}, which are not "
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
@pytest.mark.parametrize("path", CONFIG_FILES, ids=lambda p: p.name)
def test_mode_weights_track_an_elia_scenario(path: Path):
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
            f"{path.name}: the mode weights mix Elia scenarios —\n  "
            + "\n  ".join(offenders)
            + "\nDerive both keys from one (scenario, year) cell: "
            "python scripts/walloon_scripts/build_ev_charging_weights.py"
        )
