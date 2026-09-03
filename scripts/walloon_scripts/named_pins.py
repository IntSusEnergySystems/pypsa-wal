# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""TIMES-aligned LP pins applied at solve time (items 8 and 9).

Rooftop share and industry-CC capture are not CCL rows: they constrain a
*ratio* of extendable generators and an *annual mass* of captured CO₂.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import xarray as xr

logger = logging.getLogger(__name__)

SOLAR_ALL_CARRIERS = ("solar", "solar-utility", "solar-hsat", "solar rooftop")

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


def alias_low_voltage_countries(n) -> None:
    """Copy each AC bus's country onto its `` low voltage`` child.

    Rooftop PV sits on the LV bus. ``sanitize_locations`` fills an empty LV
    ``country`` from the parent's ISO code, so rooftop is counted against the
    Belgian ``solar-all`` cap instead of BEWAL. After region buses have been
    rewritten to their own names, copy that country down.
    """
    suffix = " low voltage"
    for bus in n.buses.index:
        name = str(bus)
        if not name.endswith(suffix):
            continue
        parent = name[: -len(suffix)]
        if parent in n.buses.index:
            n.buses.at[bus, "country"] = n.buses.at[parent, "country"]


def add_rooftop_share_constraint(n, node: str, share: float) -> None:
    """``solar rooftop`` ≥ ``share`` × all solar at ``node`` (by location)."""
    if share <= 0:
        return
    loc = n.generators.bus.map(n.buses.location)
    rooftop = n.generators.index[
        (n.generators.carrier == "solar rooftop") & (loc == node)
    ]
    total = n.generators.index[
        n.generators.carrier.isin(SOLAR_ALL_CARRIERS) & (loc == node)
    ]
    lhs_r = _p_nom_sum(n, rooftop)
    lhs_t = _p_nom_sum(n, total)
    if lhs_r is None or lhs_t is None:
        logger.warning(
            "Rooftop share: no solar generators at %s, skip.", node
        )
        return
    n.model.add_constraints(
        lhs_r >= float(share) * lhs_t,
        name=f"rooftop_share_{node}",
    )
    logger.info(
        "Pinned %s rooftop PV to ≥ %.1f %% of solar-all.", node, 100 * share
    )


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
