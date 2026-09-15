# SPDX-License-Identifier: MIT
"""
Recover the natural/local split of the inflexible EV load, for reporting.

`build_transport_demand.build_natural_charging_shape` blends Elia's six 24 h
curves into **one** normalised shape, and `split_transport_demand` puts the
whole non-market slice of EV demand on it as a single
``land transport EV inflexible`` load.  Elia's three flexibility modes are
therefore in the inputs but not in the network:

===========================  ==========================================
Elia mode                    where it is in the network
===========================  ==========================================
market (``V1M+V2M``)         ``land transport EV`` on the EV-battery bus
natural (``V0``)             blended into
local (``V1H+V2H``)            ``land transport EV inflexible``
===========================  ==========================================

The blend is **linear with known weights**, so the two blended modes can be
separated again exactly — no approximation, and nothing about the LP changes.
That is what this script does: it writes, per snapshot and per node, the two
shape components the inflexible load is made of.  The reporting layer splits the
solved load in their ratio and gets the third bar of the "EV charging energy by
mode" chart.

Why a separate rule rather than a second output of ``build_transport_demand``:
adding an output there would mark that rule out of date, and everything
downstream of it — including every solve — with it.  This file is read only by
the report, so nothing it touches can invalidate a solved network.

Method
------
For any weight vector ``w`` summing to 1, ``build_natural_charging_shape``
returns ``S_w(t) = U_w(t) / Σ_t U_w(t)`` with ``U_w = Σ_k w_k c_k``.  Building it
three times — with the configured weights, with natural alone, and with the
local curves renormalised over themselves — gives

    S_full = α · S_natural + (1 − α) · S_local

because all three sum to 1 over the year, and ``α = w_natural · Σ_t c_natural /
Σ_t U_full`` is exactly the natural share of the inflexible **energy**.  ``α`` is
read back from that identity by least squares (exact up to floating point), so
the vintage selection, the per-node time zones and the normalisation all stay in
the production function and cannot drift from what the network was built with.

The two components written out are ``α · S_natural(t)`` and
``(1 − α) · S_local(t)``, and the script asserts they sum back to the production
shape before writing.

Output
------
``resources/<run>/ev_charging_mode_split_s_{clusters}_{planning_horizons}.csv``
— index: the model snapshots; columns: a two-level ``(mode, node)`` header with
``mode`` in ``{natural, local}``; values: that mode's share of the inflexible EV
**load**, so the two sum to the production
``natural_charging_shape_s_{clusters}_{planning_horizons}.csv`` at every
snapshot and to 1 over the year.

Two components rather than one ratio, because a run solved at a coarser
resolution than 1 h has to aggregate them: a ratio would have to be re-weighted
by the load, whereas the components average exactly the way the load does.
Node-dependent because ``generate_periodic_profiles`` maps hours through each
node's own time zone.
"""

import logging

import pandas as pd

from scripts._helpers import (
    configure_logging,
    get_snapshots,
    set_scenario_config,
)
from scripts.build_transport_demand import build_natural_charging_shape

logger = logging.getLogger(__name__)

#: The Elia column that is uncontrolled charging (``V0``).  Every other column
#: of the profile CSV is a local-flexibility curve (``V1H``/``V2H``).
NATURAL_CURVE = "natural"


def resolve_weights(charging_weights: dict, investment_year: int) -> dict:
    """The ``sector.local_bev_dsm`` entry used for ``investment_year``.

    Mirrors the horizon fallback of
    :func:`scripts.build_transport_demand.build_natural_charging_shape` — hold
    the nearest earlier horizon rather than interpolate a behavioural split.
    Kept to three lines deliberately: the blending, the vintage choice and the
    normalisation are *not* reimplemented here, only the horizon lookup.
    """
    weights = charging_weights.get(investment_year)
    if weights is not None:
        return dict(weights)
    earlier = [y for y in sorted(charging_weights) if y < investment_year]
    if not earlier:
        raise ValueError(
            f"sector.local_bev_dsm has no entry at or before {investment_year} "
            f"(has {sorted(charging_weights)}). Add the horizon."
        )
    logger.warning(
        "sector.local_bev_dsm has no entry for %s; holding the %s weights",
        investment_year,
        earlier[-1],
    )
    return dict(charging_weights[earlier[-1]])


def _renormalise(weights: dict, keys) -> dict | None:
    """``weights`` restricted to ``keys`` and rescaled to sum to 1."""
    subset = {k: float(weights.get(k, 0.0)) for k in keys}
    total = sum(subset.values())
    if total <= 0:
        return None
    return {k: v / total for k, v in subset.items()}


def natural_share(
    shape_full: pd.DataFrame,
    shape_natural: pd.DataFrame,
    shape_local: pd.DataFrame,
) -> pd.Series:
    """Energy share ``α`` of natural charging, per node.

    Solves ``S_full = α S_natural + (1 − α) S_local`` in the least-squares sense.
    The system is consistent by construction, so the residual is a float-error
    check rather than a fit: it is asserted in :func:`mode_split`.
    """
    spread = shape_natural - shape_local
    target = shape_full - shape_local
    numerator = (target * spread).sum()
    denominator = (spread * spread).sum()
    return numerator / denominator


def mode_split(
    profile_fn: str,
    snapshots: pd.DatetimeIndex,
    nodes,
    investment_year: int,
    charging_weights: dict,
) -> tuple[pd.DataFrame, pd.Series]:
    """Split the inflexible EV charging shape into its two Elia modes.

    Returns ``(components, annual_share)``: a snapshot × ``(mode, node)`` frame
    whose two modes sum to the production shape, and the natural energy share
    ``α`` per node.
    """
    weights = resolve_weights(charging_weights, investment_year)
    local_keys = [k for k in weights if k != NATURAL_CURVE]

    shape_full = build_natural_charging_shape(
        profile_fn, snapshots, nodes, investment_year, {investment_year: weights}
    )

    natural_only = _renormalise(weights, [NATURAL_CURVE])
    local_only = _renormalise(weights, local_keys)

    # A degenerate config is not an error: it is one mode carrying everything.
    if local_only is None or natural_only is None:
        carrier = "natural" if local_only is None else "local"
        logger.info(
            "only %s charging at %s; the whole blend is that mode",
            carrier,
            investment_year,
        )
        alpha = pd.Series(
            1.0 if carrier == "natural" else 0.0, index=shape_full.columns
        )
        return _assemble(shape_full * alpha, shape_full * (1 - alpha)), alpha

    shape_natural = build_natural_charging_shape(
        profile_fn, snapshots, nodes, investment_year, {investment_year: natural_only}
    )
    shape_local = build_natural_charging_shape(
        profile_fn, snapshots, nodes, investment_year, {investment_year: local_only}
    )

    alpha = natural_share(shape_full, shape_natural, shape_local)

    natural = shape_natural.mul(alpha, axis=1)
    local = shape_local.mul(1 - alpha, axis=1)

    # The identity is exact; a residual means the three shapes were not built on
    # the same index, which would make every number below quietly wrong.
    worst = float((natural + local - shape_full).abs().max().max())
    assert worst < 1e-12, (
        f"natural/local decomposition does not reproduce the production shape "
        f"(worst absolute error {worst:.3e} on a profile summing to 1)"
    )
    return _assemble(natural, local), alpha


def _assemble(natural: pd.DataFrame, local: pd.DataFrame) -> pd.DataFrame:
    """One frame with a ``(mode, node)`` column header."""
    return pd.concat({"natural": natural, "local": local}, axis=1)


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "build_ev_charging_mode_split", clusters="adm", planning_horizons="2030"
        )
    configure_logging(snakemake)
    set_scenario_config(snakemake)

    pop_layout = pd.read_csv(snakemake.input.clustered_pop_layout, index_col=0)
    nodes = pop_layout.index
    investment_year = int(snakemake.wildcards.planning_horizons)
    snapshots = get_snapshots(
        snakemake.params.snapshots, snakemake.params.drop_leap_day, tz="UTC"
    )

    components, alpha = mode_split(
        snakemake.input.natural_charging_profile,
        snapshots,
        nodes,
        investment_year,
        snakemake.params.charging_weights,
    )

    market = snakemake.params.sector.get("bev_dsm_availability", {})
    market_share = market.get(investment_year) if isinstance(market, dict) else market
    if market_share is not None:
        logger.info(
            "%s EV charging modes as a share of the whole fleet: "
            "market %.3f, natural %.3f, local %.3f",
            investment_year,
            market_share,
            float(alpha.mean()) * (1 - market_share),
            (1 - float(alpha.mean())) * (1 - market_share),
        )
    logger.info(
        "natural share of the inflexible load: %.4f (node spread %.2e)",
        float(alpha.mean()),
        float(alpha.max() - alpha.min()),
    )

    components.round(10).to_csv(snakemake.output.mode_split)
