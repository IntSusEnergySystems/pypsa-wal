# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/PyPSA/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""No carbon capture on power and CHP plants before a given horizon.

Decision (2026-09-05): capture fitted to *power plants* — CCGT CC, the urban
central gas and solid-biomass CHP CC variants, waste CHP CC, the Allam cycle —
is not planned in Belgium in the short term, so it must not be available to the
optimiser before 2040. Industrial capture is a different question and is left
alone: ``process emissions CC``, ``solid biomass for industry CC``,
``gas for industry CC`` and ``SMR CC`` are what TIMES's ``STORAGEMININD`` floor
(item 9) is built from, and zeroing them would contradict it.

The threshold is a config value rather than a hard-coded year because it is a
policy assumption, and it comes from
``config/input_parameters_for_models.csv`` (``config:sector.power_plant_cc_from_year``)
so that TIMES and PyPSA read it from the same table.
"""

from __future__ import annotations

import logging

import pypsa

logger = logging.getLogger(__name__)

#: Link carriers that are carbon capture *on a power or CHP plant*. Industrial
#: and hydrogen-side capture is deliberately absent — see the module docstring.
POWER_PLANT_CC_CARRIERS = (
    "CCGT CC",
    "urban central gas CHP CC",
    "urban central solid biomass CHP CC",
    "waste CHP CC",
    "coal CC",
    "allam gas",
    "allam methanol",
)


def disable_power_plant_cc(
    n: pypsa.Network, investment_year: int, from_year: int | None
) -> float:
    """Zero every power/CHP capture link in horizons before ``from_year``.

    Returns the MW of extendable headroom removed (0.0 when the option is off
    or the horizon is at or past the threshold). Non-extendable vintages are
    left untouched: an inherited plant is a fact, not a choice, and clipping it
    here would silently rewrite the brownfield fleet.
    """
    if from_year is None or investment_year >= int(from_year):
        return 0.0

    mask = n.links.carrier.isin(POWER_PLANT_CC_CARRIERS) & n.links.p_nom_extendable
    if not mask.any():
        logger.info(
            "No power-plant CC to disable in %s (threshold %s).",
            investment_year,
            from_year,
        )
        return 0.0

    idx = n.links.index[mask]
    removed = float(n.links.loc[idx, "p_nom_max"].replace(float("inf"), 0.0).sum())
    n.links.loc[idx, "p_nom_extendable"] = False
    n.links.loc[idx, ["p_nom", "p_nom_min", "p_nom_max"]] = 0.0

    for carrier, count in n.links.loc[idx, "carrier"].value_counts().items():
        logger.info(
            "Power-plant CC off in %s (< %s, not planned in the short term): "
            "%d %s link(s) fixed at 0 MW.",
            investment_year,
            from_year,
            count,
            carrier,
        )
    return removed
