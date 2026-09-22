# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""TIMES-aligned LP pins applied at solve time (items 8 and 9).

The rooftop floor and the industry-CC capture floor are not CCL rows: they
constrain an *absolute capacity* of one carrier at one node and an *annual
mass* of captured CO₂.

Item 8 used to be a **share** pin (``solar rooftop`` >= s x solar-all). It was
replaced by an absolute floor on 2026-09-22: a share fixes the *composition*
of the Walloon PV fleet without fixing its size, and it does so by making
every MW of ground-mounted PV drag 1/s - 1 MW of dearer rooftop along.
`docs/co2-sequestration.md` S7.2 measured the consequence — ground-mounted PV
earning +4 790 EUR/MW/a stopped at 6 % of its potential because of the bundle,
so the model's cheapest abatement was suppressed by a TIMES *composition*
assumption. The floor transfers what TIMES actually decides (how much roof is
used) and leaves the ground-mounted tranche to the optimiser. There is
deliberately **no** floor and no ceiling on ground-mounted PV.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import xarray as xr

logger = logging.getLogger(__name__)

# Captured CO₂ sits on `co2 stored`. Atmosphere terms are the complement
# (uncaptured, or the BECCS credit) and must not be added here.
INDUSTRY_CC_CAPTURE = (
    ("process emissions CC", "efficiency2"),
    ("solid biomass for industry CC", "efficiency3"),
    ("gas for industry CC", "efficiency3"),
)


def planning_year(planning_horizons) -> int | None:
    if planning_horizons is None:
        return None
    digits = "".join(ch for ch in str(planning_horizons) if ch.isdigit())
    if len(digits) < 4:
        return None
    return int(digits[-4:])


def year_map(path: Path | str, value_col: str) -> dict[int, float]:
    df = pd.read_csv(path, comment="#")
    return {int(y): float(v) for y, v in zip(df["year"], df[value_col])}


def lookup_year_value(cfg: dict, year: int | None, inline_key: str, file_col: str):
    """A per-year number from an inline dict or a CSV ``file``."""
    if year is None:
        return None
    inline = cfg.get(inline_key)
    if isinstance(inline, dict):
        if year in inline:
            return float(inline[year])
        if str(year) in inline:
            return float(inline[str(year)])
    path = cfg.get("file")
    if path:
        return year_map(path, file_col).get(year)
    return None


def add_rooftop_floor_constraint(n, node: str, gw: float) -> None:
    """Standing ``solar rooftop`` capacity at ``node`` ≥ ``gw`` GW.

    ``gw`` is TIMES ``VAR_Cap`` of the rooftop PV plant processes
    (``ERNW_PV-{Buildings,Large_Roof,RES_Homes}``) — the ``rooftop_gw`` column
    of ``data/walloon/times_pv_rooftop_share*.csv``. The sum runs over *every*
    vintage at the node, standing and extendable, because the ceiling TIMES
    reports is a fleet figure, not this horizon's addition.

    Ground-mounted PV is deliberately untouched: no floor, no ceiling, no
    ratio to rooftop. Only ``p_nom_max`` (13 GW at BEWAL,
    ``custom_potentials.csv``) and the CCL build rate bound it.
    """
    if gw is None or float(gw) <= 0:
        return
    loc = n.generators.bus.map(n.buses.location)
    rooftop = n.generators.index[
        (n.generators.carrier == "solar rooftop") & (loc == node)
    ]
    lhs = _p_nom_sum(n, rooftop)
    if lhs is None:
        logger.warning("Rooftop floor: no rooftop PV generators at %s, skip.", node)
        return
    mw = float(gw) * 1e3
    if isinstance(lhs, float):
        # Every vintage at the node is non-extendable: there is no decision
        # variable to constrain, so the floor is either already met or the LP
        # would be infeasible for a reason the solver could not explain.
        if lhs + 1e-6 < mw:
            raise ValueError(
                f"Rooftop floor at {node}: {mw:.0f} MW required but only "
                f"{lhs:.0f} MW of non-extendable rooftop PV exists and none "
                "is extendable — the LP cannot reach the floor."
            )
        logger.info(
            "Rooftop floor at %s already met by %.0f MW of standing capacity "
            "(floor %.0f MW); no constraint added.",
            node,
            lhs,
            mw,
        )
        return
    n.model.add_constraints(lhs >= mw, name=f"rooftop_floor_{node}")
    logger.info("Pinned %s rooftop PV to ≥ %.0f MW (TIMES %.3f GW).", node, mw, gw)


def add_industry_cc_floor(n, node: str, kt: float) -> None:
    """Annual captured tCO₂ from industry CC at ``node`` ≥ ``kt`` × 1000."""
    if kt <= 0:
        return
    weights = n.snapshot_weightings.generators
    captured = None
    for carrier, eff_col in INDUSTRY_CC_CAPTURE:
        links = n.links.loc[n.links.carrier == carrier]
        if links.empty:
            continue
        loc = links.bus0.map(n.buses.location)
        links = links.loc[loc == node]
        if links.empty:
            continue
        p = n.model["Link-p"].loc[:, links.index]
        link_dim = p.dims[1]
        eff = xr.DataArray(
            links[eff_col].astype(float).values,
            coords={link_dim: links.index},
            dims=[link_dim],
        )
        term = (p * eff * weights).sum()
        captured = term if captured is None else captured + term
    if captured is None:
        logger.warning("Industry CC floor: no capture links at %s, skip.", node)
        return
    n.model.add_constraints(
        captured >= float(kt) * 1e3,
        name="industry_cc_floor",
    )
    logger.info("Pinned %s industry CC capture to ≥ %.1f kt/a.", node, kt)


def _p_nom_sum(n, names: pd.Index):
    if names.empty:
        return None
    p_nom = n.model["Generator-p_nom"]
    dim = p_nom.dims[0]
    ext_index = p_nom.indexes[dim]
    ext = names.intersection(ext_index)
    cst = names.difference(ext_index)
    const = float(n.generators.loc[cst, "p_nom"].sum()) if len(cst) else 0.0
    if len(ext) == 0:
        return const
    expr = p_nom.loc[ext].sum()
    return expr + const if const else expr
