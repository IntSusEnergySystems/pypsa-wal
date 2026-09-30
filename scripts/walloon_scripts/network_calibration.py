# SPDX-FileCopyrightText: Contributors to PyPSA-Wal
#
# SPDX-License-Identifier: MIT
"""Network-cost calibration hooks for the current (three-node) formulation.

Every value these functions apply is documented, with its source, in
``docs/network-costs-review-20260928.md`` §2–§6. The functions are switched on by
``sector.network_calibration`` in the config and are no-ops when the key is
absent, so a config without the block reproduces the PyPSA-Eur behaviour.

* :func:`split_industry_electricity` moves the HV-connected share of
  ``industry electricity`` off the low-voltage bus. PyPSA-Eur puts every
  electricity load behind the distribution link, so industry connected to Elia
  was paying for, and sizing, a DSO grid it does not use. The share comes from
  TIMES, which draws 70 % of Walloon industrial electricity at HV
  (``VAR_FIn`` on ``ELCHIGG`` vs ``ELCMED``) in every horizon.
* :func:`add_rooftop_pv_hosting_cost` charges *new* rooftop PV the LV
  reinforcement it causes locally. A single regional LV bus never sees rooftop
  PV export, so without it the model has no hosting cost at all.
* :func:`apply_transmission_cost_overrides` replaces the generic
  length × unit-cost annuity of selected corridors by project data (ALEGrO) and
  applies economies of scale to large CO₂ trunks.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pypsa

logger = logging.getLogger(__name__)

LV_SUFFIX = " low voltage"


def split_industry_electricity(n: pypsa.Network, hv_share: float | None) -> pd.Index:
    """Move ``hv_share`` of every LV ``industry electricity`` load to its AC bus.

    Must run after the loads have been moved onto the low-voltage bus by
    ``insert_electricity_distribution_grid``. The HV part keeps the carrier
    ``industry electricity``, so every check that sums that carrier per node
    (``review_run.py`` level 2.3) still sees the whole TIMES demand. It is named
    ``<load> HV``.

    Returns the index of the loads that were created.
    """
    if not hv_share:
        return pd.Index([])
    if not 0 < hv_share < 1:
        raise ValueError(f"industry_hv_share must be in (0, 1), got {hv_share}")

    lv = n.loads.index[
        (n.loads.carrier == "industry electricity")
        & n.loads.bus.str.endswith(LV_SUFFIX)
    ]
    if lv.empty:
        logger.warning("industry_hv_share set but no LV industry electricity load found")
        return pd.Index([])

    hv_names = lv + " HV"
    hv_buses = n.loads.loc[lv, "bus"].str[: -len(LV_SUFFIX)].values

    dynamic = lv.intersection(n.loads_t.p_set.columns)
    static = lv.difference(dynamic)

    if len(static):
        p = n.loads.loc[static, "p_set"]
        n.add(
            "Load",
            static + " HV",
            bus=n.loads.loc[static, "bus"].str[: -len(LV_SUFFIX)].values,
            carrier="industry electricity",
            p_set=(p * hv_share).values,
        )
        n.loads.loc[static, "p_set"] = p * (1 - hv_share)
    if len(dynamic):
        p = n.loads_t.p_set[dynamic]
        hv_p = p * hv_share
        hv_p.columns = dynamic + " HV"
        # add first, then assign the series: pypsa rejects a one-column frame
        # as `p_set` when a single component is added
        n.add(
            "Load",
            dynamic + " HV",
            bus=n.loads.loc[dynamic, "bus"].str[: -len(LV_SUFFIX)].values,
            carrier="industry electricity",
        )
        n.loads_t.p_set[hv_p.columns] = hv_p
        n.loads_t.p_set[dynamic] = p * (1 - hv_share)

    logger.info(
        "Moved %.0f %% of industry electricity to the transmission bus at %d node(s)",
        100 * hv_share,
        len(lv),
    )
    return pd.Index(hv_names)


def _annuity_ratio(costs: pd.DataFrame, reference: str) -> float:
    """Annualised cost per unit of investment of ``reference`` (annuity + FOM)."""
    inv = costs.at[reference, "investment"]
    if not inv:
        raise ValueError(f"cost row {reference!r} has no investment to scale from")
    return costs.at[reference, "capital_cost"] / inv


def add_rooftop_pv_hosting_cost(
    n: pypsa.Network, costs: pd.DataFrame, investment_eur_per_kw: float | None
) -> pd.Index:
    """Add an LV hosting-capacity charge to the capital cost of new rooftop PV.

    The investment (EUR/kWp) is annualised with the lifetime, FOM and discount
    rate of ``electricity distribution grid``, because it *is* distribution grid:
    the LV reinforcement a new rooftop system triggers, which a single regional
    LV bus cannot size on its own. Existing (non-extendable) rooftop PV is sunk
    and left alone.
    """
    if not investment_eur_per_kw:
        return pd.Index([])
    gens = n.generators.index[
        (n.generators.carrier == "solar rooftop") & n.generators.p_nom_extendable
    ]
    adder = (
        investment_eur_per_kw * 1e3 * _annuity_ratio(costs, "electricity distribution grid")
    )
    n.generators.loc[gens, "capital_cost"] += adder
    logger.info(
        "Rooftop PV hosting cost: +%.0f EUR/MW/a on %d generator(s) (%.0f EUR/kWp)",
        adder,
        len(gens),
        investment_eur_per_kw,
    )
    return gens


def _corridor_mask(c: pd.DataFrame, buses: pd.DataFrame, carrier: str, a: str, b: str) -> pd.Series:
    loc0 = c.bus0.map(buses.location).fillna(c.bus0)
    loc1 = c.bus1.map(buses.location).fillna(c.bus1)
    pair = ((loc0 == a) & (loc1 == b)) | ((loc0 == b) & (loc1 == a))
    twin = pd.Series(c.index.str.endswith("-reversed"), index=c.index)
    if "reversed" in c:
        twin |= c["reversed"].fillna(False).astype(bool)
    return (c.carrier == carrier) & pair & ~twin


def read_transmission_cost_overrides(fn: str | None) -> pd.DataFrame:
    """Read the override table (empty frame when ``fn`` is falsy)."""
    cols = ["component", "carrier", "bus0", "bus1", "parameter", "value", "reference"]
    if not fn:
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(fn, comment="#")
    missing = set(cols) - set(df.columns)
    if missing:
        raise ValueError(f"{fn}: missing column(s) {sorted(missing)}")
    bad = set(df.parameter) - {"investment", "capital_cost_factor"}
    if bad:
        raise ValueError(f"{fn}: unknown parameter(s) {sorted(bad)}")
    return df


def apply_transmission_cost_overrides(
    n: pypsa.Network,
    costs: pd.DataFrame,
    overrides: pd.DataFrame,
    parameters: tuple[str, ...] = ("investment", "capital_cost_factor"),
) -> int:
    """Apply per-corridor cost overrides; returns the number of branches changed.

    ``investment`` rows *set* the capital cost from an investment per MW
    (EUR2025/MW, total for the branch, i.e. already including length and
    terminals), annualised like the ``reference`` cost row. Setting is
    idempotent, so these rows are re-applied after every
    ``set_transmission_costs`` call (``add_brownfield``).

    ``capital_cost_factor`` rows *multiply* the capital cost. They are applied
    once, in ``prepare_sector_network``, to the branches that horizon creates;
    carried-forward vintages keep the factor they were built with. Calling them
    twice on the same network would compound, which is why ``add_brownfield``
    passes ``parameters=("investment",)``.

    The reversed twin of a lossy bidirectional link is never touched: its
    capital cost must stay 0 (docs/network-costs-review-20260928.md §6.2).
    """
    changed = 0
    for r in overrides.itertuples():
        if r.parameter not in parameters:
            continue
        comp = {"Line": n.lines, "Link": n.links}[r.component]
        mask = _corridor_mask(comp, n.buses, r.carrier, r.bus0, r.bus1)
        if r.parameter == "capital_cost_factor":
            # only the branches this horizon may still build
            ext = "s_nom_extendable" if r.component == "Line" else "p_nom_extendable"
            mask &= comp[ext]
        idx = comp.index[mask]
        if idx.empty:
            logger.info("No %s %s %s–%s to override", r.component, r.carrier, r.bus0, r.bus1)
            continue
        if r.parameter == "investment":
            comp.loc[idx, "capital_cost"] = float(r.value) * _annuity_ratio(costs, r.reference)
        else:
            comp.loc[idx, "capital_cost"] *= float(r.value)
        changed += len(idx)
        logger.info(
            "Override %s on %s %s %s–%s (%d branch(es)): %s",
            r.parameter, r.component, r.carrier, r.bus0, r.bus1, len(idx), r.value,
        )
    return changed


def co2_scale_factor(q_t_per_h: float, q_ref: float = 300.0, exponent: float = 0.6) -> float:
    """Unit-cost multiplier for a CO₂ trunk of ``q_t_per_h`` against the DEA reference.

    Pipeline cost is taken to scale as capacity**exponent (the six-tenths rule),
    so the cost per unit of capacity scales as capacity**(exponent - 1). The DEA
    value is for a 12-inch line in the 120-500 t/h range; ``q_ref`` is its
    middle. Only economies of scale are applied (factor ≤ 1): a pipeline smaller
    than the reference keeps the DEA cost.
    """
    if not q_t_per_h or q_t_per_h <= q_ref:
        return 1.0
    return float(np.power(q_t_per_h / q_ref, exponent - 1.0))
