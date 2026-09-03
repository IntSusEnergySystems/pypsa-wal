# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Pit thermal energy storage: finite ``e_nom_max`` from heat demand.

Item 16: the urban-central water-pit Store is extendable with ``capital_cost
= 0`` and no ceiling, so the TES energy-to-power equality invents tens of GW
of charger. Bound the store at ``weeks`` of that node's urban-central heat
demand (default 4 ≈ 100–200 GWh_th in Wallonia).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pypsa

logger = logging.getLogger(__name__)

WEEKS_PER_YEAR = 52.0


def ptes_store_e_nom_max(
    n: pypsa.Network,
    nodes,
    weeks: float,
    heat_system: str = "urban central",
) -> pd.Series:
    """MWh_th ceiling per node: ``weeks`` of that node's DH energy demand."""
    weights = n.snapshot_weightings
    if "generators" in weights.columns:
        weights = weights["generators"]
    else:
        weights = weights["objective"] if "objective" in weights.columns else weights.iloc[:, 0]
    nhours = float(weights.sum())
    index = pd.Index(nodes)
    out = pd.Series(np.inf, index=index, dtype=float)
    if weeks is None or not np.isfinite(weeks) or weeks <= 0:
        return out
    for node in index:
        load = f"{node} {heat_system} heat"
        if load in n.loads_t.p_set.columns:
            annual = float((n.loads_t.p_set[load] * weights).sum())
        elif load in n.loads.index:
            annual = float(n.loads.at[load, "p_set"] * nhours)
        else:
            continue
        out[node] = annual * (float(weeks) / WEEKS_PER_YEAR)
    return out


def apply_ptes_fleet_cap(
    n: pypsa.Network,
    weeks: float,
    heat_system: str = "urban central",
) -> None:
    """Turn the per-vintage ``e_nom_max`` into a cap on the standing fleet.

    ``prepare_sector_network`` writes the ceiling on the Store it builds for one
    horizon. ``add_brownfield`` then carries earlier vintages in as separate,
    non-extendable Stores, so without this the fleet could reach ``weeks`` ×
    (number of horizons) — the same "the cap binds the extendable tranche only"
    pattern the aggregate capacity limits already had. Called after brownfield:
    inherited vintages keep their ``e_nom`` and the residual is written on the
    extendable one. Item 16 / B9.
    """
    carrier = f"{heat_system} water pits"
    pits = n.stores.loc[n.stores.carrier.astype(str) == carrier]
    if pits.empty:
        return
    nodes = sorted({str(b) for b in pits.bus.map(n.buses.location).dropna()})
    ceiling = ptes_store_e_nom_max(n, nodes, weeks, heat_system)

    for node in nodes:
        cap = float(ceiling.get(node, np.inf))
        if not np.isfinite(cap):
            continue
        at_node = pits.index[pits.bus.map(n.buses.location).astype(str) == node]
        ext = [s for s in at_node if bool(n.stores.at[s, "e_nom_extendable"])]
        inherited = float(
            n.stores.loc[[s for s in at_node if s not in ext], "e_nom"].sum()
        )
        residual = max(cap - inherited, 0.0)
        if not ext:
            continue
        share = residual / len(ext)
        for store in ext:
            n.stores.at[store, "e_nom_max"] = min(
                float(n.stores.at[store, "e_nom_max"]), share
            )
        logger.info(
            "PTES fleet cap at %s: %.0f MWh_th ceiling, %.0f MWh_th inherited, "
            "%.0f MWh_th left for the new vintage.",
            node,
            cap,
            inherited,
            residual,
        )
