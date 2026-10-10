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


#: Links that take CO₂ off a node's `co2 stored` bus towards storage: the
#: inter-node pipelines and the node's own `co2 sequestered` link.
CO2_EXPORT_CARRIERS = ("CO2 pipeline", "co2 sequestered")


def add_co2_export_limit(n, node: str, kt: float, overage_price=None) -> None:
    """Net annual CO₂ leaving ``node``'s `co2 stored` bus ≤ ``kt`` × 1000 t.

    Lever D of `docs/co2-sequestration.md` §10.2: Wallonia has no domestic sink,
    so "less CCS" physically means "less CO₂ leaves Wallonia". The cap is on the
    *net* outflow of the bus, so Flemish and Brussels transit cancels and the
    constraint needs no list of capture carriers: flow out on links whose
    ``bus0`` is the bus, minus the CO₂ delivered by links whose ``bus1`` is it.

    With ``overage_price`` (EUR/t) the cap is a ship-or-pay subscription —
    tonnes above it are allowed at that price, so the constraint can never make
    the LP infeasible (the doc's "overage valve is mandatory"). Without it the
    cap is hard.

    The row is registered as the ``GlobalConstraint`` ``co2_export_limit_<node>``
    so its dual (EUR/t, ≤ 0 when binding) is written into the solved network,
    as for ``co2_limit_per_country<ct>``. The overage itself is not stored; it
    is ``max(0, net export − constant)``, recomputable from the link flows.
    """
    bus = f"{node} co2 stored"
    links = n.links.loc[n.links.carrier.isin(CO2_EXPORT_CARRIERS)]
    out_links = links.index[links.bus0 == bus]
    in_links = links.index[links.bus1 == bus]
    if out_links.empty and in_links.empty:
        logger.warning("CO2 export limit: no CO2 pipeline at %s, skip.", bus)
        return
    weights = n.snapshot_weightings.generators
    p = n.model["Link-p"]
    link_dim = p.dims[1]
    outflow = None
    if len(out_links):
        outflow = (p.loc[:, out_links] * weights).sum()
    if len(in_links):
        eff = xr.DataArray(
            links.loc[in_links, "efficiency"].astype(float).values,
            coords={link_dim: in_links},
            dims=[link_dim],
        )
        inflow = (p.loc[:, in_links] * eff * weights).sum()
        outflow = -inflow if outflow is None else outflow - inflow
    cap_t = float(kt) * 1e3
    name = f"co2_export_limit_{node}"
    if overage_price:
        over = n.model.add_variables(lower=0, name=f"co2_export_overage_{node}")
        n.model.add_constraints(outflow - over <= cap_t, name=f"GlobalConstraint-{name}")
        n.model.objective = n.model.objective + float(overage_price) * over
        logger.info(
            "Capped %s net CO2 export at %.0f kt/a, overage at %.0f EUR/t.",
            node, kt, float(overage_price),
        )
    else:
        n.model.add_constraints(outflow <= cap_t, name=f"GlobalConstraint-{name}")
        logger.info("Capped %s net CO2 export at %.0f kt/a (hard).", node, kt)
    n.add("GlobalConstraint", name, constant=cap_t, sense="<=", type="")


#: Carriers that move CO₂ between `co2 stored` buses or out of one. They are
#: not capture, so they never count as the node's own supply.
CO2_TRANSPORT_CARRIERS = ("CO2 pipeline", "co2 sequestered")


def captured_co2_expr(n, node: str, label: str = "CO2 capture"):
    """Annual tCO₂ that ``node``'s own links put on its `co2 stored` bus.

    Every non-transport link port ``bus<k>`` (k ≥ 1) into the bus with a
    positive efficiency: industry, power and CHP capture, SMR CC, DAC. Ports
    with a negative efficiency are local *use* (Fischer-Tropsch,
    methanolisation, Sabatier) and are not subtracted; pipelines and the
    node's ``co2 sequestered`` link are transport. No carrier list, so a
    capture technology added later is counted without an edit here.

    Returns a linopy expression, or ``None`` when nothing captures at the node.
    """
    bus = f"{node} co2 stored"
    weights = n.snapshot_weightings.generators
    p = n.model["Link-p"]
    link_dim = p.dims[1]
    others = n.links.loc[~n.links.carrier.astype(str).isin(CO2_TRANSPORT_CARRIERS)]
    ports = [c[3:] for c in others.columns if c.startswith("bus") and c[3:].isdigit()]
    captured = None
    for k in ports:
        if k == "0":
            continue
        eff_col = "efficiency" if k == "1" else f"efficiency{k}"
        if eff_col not in others:
            continue
        sel = others.index[(others[f"bus{k}"] == bus) & (others[eff_col].astype(float) > 0)]
        if sel.empty:
            continue
        if eff_col in n.links_t and not n.links_t[eff_col].columns.intersection(sel).empty:
            logger.warning(
                "%s: time-varying %s on %s; static value used.",
                label, eff_col, list(n.links_t[eff_col].columns.intersection(sel)),
            )
        eff = xr.DataArray(
            others.loc[sel, eff_col].astype(float).values,
            coords={link_dim: sel},
            dims=[link_dim],
        )
        term = (p.loc[:, sel] * eff * weights).sum()
        captured = term if captured is None else captured + term
    return captured


def add_co2_disposal_own_capture(n, node: str) -> None:
    """Annual CO₂ into ``node``'s disposal route ≤ CO₂ captured at ``node``.

    The route of :func:`BEWAL_potentials.apply_co2_disposal_service` is a
    Walloon subscription, priced below the endogenous disposal price in 2050.
    Without this row the LP would pipe Flemish or foreign CO₂ into Wallonia to
    use it. The bound is the CO₂ the node's own links put on its `co2 stored`
    bus: every non-transport link port ``bus<k>`` (k ≥ 1) with a positive
    efficiency, i.e. capture (industry, power, CHP, SMR, DAC). Ports with a
    negative efficiency are local *use* (Fischer-Tropsch, methanolisation) and
    are not subtracted, so local use may still draw on imported CO₂.

    No row is added while the node's ``co2 sequestered`` Stores hold no
    capacity (route closed). Registered as GlobalConstraint
    ``co2_disposal_own_capture_<node>`` so the dual survives into the network.
    """
    bus = f"{node} co2 stored"
    seq_bus = f"{node} co2 sequestered"
    stores = n.stores.loc[
        (n.stores.carrier.astype(str) == "co2 sequestered") & (n.stores.bus == seq_bus)
    ]
    room = float(stores.e_nom.sum())
    ext = stores.e_nom_extendable.fillna(False).astype(bool)
    room += float(stores.loc[ext, "e_nom_max"].clip(upper=1e12).sum())
    if room <= 0:
        return
    seq_links = n.links.index[
        (n.links.carrier.astype(str) == "co2 sequestered") & (n.links.bus0 == bus)
    ]
    if seq_links.empty:
        logger.warning("CO2 disposal own-capture: no co2 sequestered link at %s, skip.", bus)
        return
    weights = n.snapshot_weightings.generators
    p = n.model["Link-p"]
    disposed = (p.loc[:, seq_links] * weights).sum()

    captured = captured_co2_expr(n, node, "CO2 disposal own-capture")
    name = f"co2_disposal_own_capture_{node}"
    if captured is None:
        n.model.add_constraints(disposed <= 0, name=f"GlobalConstraint-{name}")
    else:
        n.model.add_constraints(disposed - captured <= 0, name=f"GlobalConstraint-{name}")
    n.add("GlobalConstraint", name, constant=0.0, sense="<=", type="")
    logger.info("CO2 disposal route at %s limited to the node's own capture.", node)


def add_co2_capture_limit(n, node: str, kt: float, overage_price=None) -> None:
    """Annual CO₂ captured at ``node`` ≤ ``kt`` × 1000 t (2026-10-10).

    Aligns PyPSA with TIMES-WAL, which bounds what Wallonia captures and sends
    to storage (the ``CO2STG01`` bound: "tout ce qui est capturé"). The sum is
    :func:`captured_co2_expr`: every capture port into ``<node> co2 stored``,
    industry, power, CHP, SMR CC and DAC alike, whatever happens to the CO₂
    next (pipeline, route or local use). Unlike lever D
    (:func:`add_co2_export_limit`), local use does not free room under the cap.

    With ``overage_price`` (EUR/t) tonnes above the cap are allowed at that
    price, so the row can never make the LP infeasible; a non-zero overage in a
    solved network says the cap is tighter than the rest of the model can
    meet. Without it the cap is hard.

    Registered as ``GlobalConstraint`` ``co2_capture_limit_<node>``: its dual
    (EUR/t, ≤ 0 when binding) is the scarcity rent of a captured tonne.
    """
    captured = captured_co2_expr(n, node, "CO2 capture limit")
    if captured is None:
        logger.warning("CO2 capture limit: nothing captures at %s, skip.", node)
        return
    cap_t = float(kt) * 1e3
    name = f"co2_capture_limit_{node}"
    if overage_price:
        over = n.model.add_variables(lower=0, name=f"co2_capture_overage_{node}")
        n.model.add_constraints(captured - over <= cap_t, name=f"GlobalConstraint-{name}")
        n.model.objective = n.model.objective + float(overage_price) * over
        logger.info(
            "Capped %s CO2 capture at %.0f kt/a, overage at %.0f EUR/t.",
            node, kt, float(overage_price),
        )
    else:
        n.model.add_constraints(captured <= cap_t, name=f"GlobalConstraint-{name}")
        logger.info("Capped %s CO2 capture at %.0f kt/a (hard).", node, kt)
    n.add("GlobalConstraint", name, constant=cap_t, sense="<=", type="")


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
