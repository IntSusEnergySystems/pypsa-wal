# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""CO₂ geological storage: the CO2StoP ceiling binds the fleet, not a vintage.

``prepare_sector_network`` reads the clustered CO2StoP potential, annualises it
over ``years_of_storage`` and writes the result as ``e_nom_max`` on the
``co2 sequestered`` Store **it builds for this horizon**. ``add_brownfield``
then carries the earlier horizons' Stores in as separate, non-extendable
vintages on the same bus, and nothing subtracts them. A reservoir sized for
79.1 Mt/a (DE) therefore reached 130.1 Mt/a installed by 2040 and 209.2 Mt/a by
2050 — 2.64x its own ceiling; NL 3.00x, GB 1.46x. The pooled
``co2_sequestration_limit`` backstop is deliberately slack (1 000 Mt from 2035)
so it catches none of it.

Measured and documented in ``docs/co2-sequestration.md`` §5.2 (lever A). This
is the same "the cap binds the extendable tranche only" pattern already fixed
for the aggregate capacity limits, for pit thermal storage
(:mod:`scripts.walloon_scripts.ptes_bounds`) and for the Belgian CO₂ stores
(``BEWAL_potentials.apply_co2_store_cap``); this module generalises it to every
node, which is where DE, NL and GB live.

Fixing it raises the scarcity rent — and with it the Walloon disposal price —
*endogenously*, which is why §10 ranks it above any change to
``co2_sequestration_cost``. Doing both double-counts.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import pypsa

logger = logging.getLogger(__name__)

CARRIER = "co2 sequestered"

#: Residual headroom below this fraction of a node's own ceiling is written as
#: exactly zero. Subtracting an inherited vintage that already fills the
#: reservoir leaves a floating-point crumb — NL came out at 7.34e-04 t against a
#: 9.09 Mt/a ceiling on 2026-09-22 — and that crumb is a *finite, near-zero upper
#: bound* on an optimisation variable, i.e. exactly the numerical pathology
#: `existing_capacities.threshold_capacity` exists to remove (lever B, §10). One
#: millionth of a reservoir is nothing anyone would model, so snap it.
RESIDUAL_EPS_REL = 1e-6


def sequestration_fleet_ceiling(n: pypsa.Network) -> pd.Series:
    """Per-location annual injection ceiling, in tonnes, from the Store bounds.

    The ceiling is what ``prepare_sector_network`` wrote on this horizon's
    extendable vintage: the CO2StoP potential clipped at ``max_size`` and
    divided by ``years_of_storage``. It does not vary with the horizon, so the
    largest ``e_nom_max`` seen at a location is that location's ceiling. Nodes
    whose ceiling is infinite (``regional_co2_sequestration_potential`` off)
    are returned as ``inf`` and left alone.
    """
    stores = n.stores.loc[n.stores.carrier.astype(str) == CARRIER]
    if stores.empty:
        return pd.Series(dtype=float)
    loc = stores.bus.map(n.buses.location).astype(str)
    ext = stores.e_nom_extendable.fillna(False).astype(bool)
    # Only the extendable vintage still carries the ceiling; an inherited one
    # carries the *realised* e_nom_max of the horizon that built it, which is
    # already net of whatever was inherited then.
    source = stores.loc[ext] if ext.any() else stores
    return source.e_nom_max.astype(float).groupby(loc[source.index]).max()


def apply_sequestration_fleet_cap(n: pypsa.Network) -> None:
    """Subtract inherited ``co2 sequestered`` vintages from this horizon's ceiling.

    Call **after** ``add_brownfield`` (the inherited vintages must be on the
    network) and **before** ``update_BEWAL_potentials``, which writes the
    documented Belgian override — zero for BEWAL/BEVLG/BEBRU — with its own
    fleet arithmetic and must have the last word at those nodes.

    The base year has no inherited vintage, so this is a no-op there.
    """
    stores = n.stores.loc[n.stores.carrier.astype(str) == CARRIER]
    if stores.empty:
        return
    loc = stores.bus.map(n.buses.location).astype(str)
    ceiling = sequestration_fleet_ceiling(n)

    for node, cap in ceiling.items():
        cap = float(cap)
        if not np.isfinite(cap):
            continue
        at_node = stores.index[loc == node]
        ext = [s for s in at_node if bool(n.stores.at[s, "e_nom_extendable"])]
        inherited = float(n.stores.loc[at_node.difference(ext), "e_nom"].sum())
        residual = max(cap - inherited, 0.0)
        if residual < RESIDUAL_EPS_REL * cap:
            residual = 0.0
        if not ext:
            continue
        # Several extendable vintages on one bus never happens in myopic (one
        # per horizon, and the earlier ones are fixed), but splitting the
        # residual keeps the fleet sum right if it ever does.
        share = residual / len(ext)
        for store in ext:
            n.stores.at[store, "e_nom_max"] = min(
                float(n.stores.at[store, "e_nom_max"]), share
            )
            for floor in ("e_nom_min", "e_nom"):
                if float(n.stores.at[store, floor]) > share:
                    n.stores.at[store, floor] = share
        if inherited > 0:
            logger.info(
                "CO2 sequestration fleet cap at %s: %.3f Mt/a ceiling, "
                "%.3f Mt/a inherited, %.3f Mt/a left for the new vintage.",
                node,
                cap / 1e6,
                inherited / 1e6,
                residual / 1e6,
            )
