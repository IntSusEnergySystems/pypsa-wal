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

import numpy as np
import pandas as pd
import pypsa

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
