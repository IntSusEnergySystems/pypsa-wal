# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/PyPSA/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""Split the 2025 Walloon PV standing fleet between rooftop and utility.

The historical fleet arrives from IRENASTAT labelled entirely `solar`
(utility), while about two thirds of it is rooftop. Item 8's TIMES share pin
needs that split in the base year: imposed on an all-utility fleet it demands
GW of new rooftop inside a corridor of megawatts (docs/temporary_improvement_plans.md
B5). This moves `rooftop_mw` of the standing BEWAL vintages onto
`<node> low voltage` as non-extendable `solar rooftop` generators, newest
vintage first. add_brownfield carries the relabelled fleet forward, so the
split holds in every later horizon; the agg `solar-all` pin (total PV) and the
TIMES share (2030+) do the rest.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def load_baseyear_pv_split(path: str) -> pd.DataFrame:
    return pd.read_csv(path, comment="#")


def split_baseyear_pv(
    n,
    node: str,
    rooftop_mw: float,
    low_voltage_suffix: str = " low voltage",
) -> None:
    """Relabel ``rooftop_mw`` of ``node``'s standing ``solar`` fleet as rooftop.

    The counterpart generators keep build year, lifetime and profile of the
    vintage they are carved from and take cost attributes from the network's
    extendable rooftop candidates, mirroring how the utility vintages inherit
    the utility candidates' costs.
    """
    standing = n.generators.index[
        (n.generators.bus == node)
        & (n.generators.carrier == "solar")
        & ~n.generators.p_nom_extendable
        & (n.generators.p_nom > 0)
    ]
    if standing.empty:
        logger.warning(
            "Base-year PV split: no standing `solar` fleet at %s, skip.", node
        )
        return

    rooftop_cost = n.generators.loc[
        n.generators.carrier == "solar rooftop",
        ["capital_cost", "marginal_cost", "efficiency"],
    ].mean()
    lv_bus = node + low_voltage_suffix
    if lv_bus not in n.buses.index:
        logger.warning(
            "Base-year PV split: no %s bus in the network, skip.", lv_bus
        )
        return

    order = standing[n.generators.loc[standing, "build_year"].argsort()[::-1]]
    remaining = float(rooftop_mw)
    for name in order:
        if remaining <= 0:
            break
        take = min(float(n.generators.at[name, "p_nom"]), remaining)
        if take <= 0:
            continue
        rooftop_name = str(name).replace(" solar-", " solar rooftop-")
        profile = n.generators_t.p_max_pu[name].rename(rooftop_name)
        n.add(
            "Generator",
            rooftop_name,
            bus=lv_bus,
            carrier="solar rooftop",
            p_nom=take,
            p_nom_extendable=False,
            marginal_cost=rooftop_cost["marginal_cost"],
            capital_cost=rooftop_cost["capital_cost"],
            efficiency=rooftop_cost["efficiency"],
            p_max_pu=profile,
            build_year=n.generators.at[name, "build_year"],
            lifetime=n.generators.at[name, "lifetime"],
        )
        if take >= float(n.generators.at[name, "p_nom"]) - 1e-6:
            n.remove("Generator", name)
        else:
            n.generators.at[name, "p_nom"] -= take
        remaining -= take
        logger.info(
            "Base-year PV split: %s rooftop <- %.1f MW of %s.",
            node,
            take,
            name,
        )

    if remaining > 0.5:
        logger.warning(
            "Base-year PV split: standing fleet short by %.1f MW; "
            "rooftop floor is %s - %.1f MW only.",
            remaining,
            node,
            rooftop_mw - remaining,
        )


def apply_baseyear_pv_split(n, cfg: dict, baseyear: int) -> None:
    """Entry point: read the CSV named by ``cfg`` and split matching nodes."""
    if not cfg.get("enable"):
        return
    df = load_baseyear_pv_split(cfg["file"])
    rows = df[df["year"] == int(baseyear)]
    if rows.empty:
        logger.info(
            "Base-year PV split: no row for %s in %s, skip.",
            baseyear,
            cfg["file"],
        )
        return
    for _, row in rows.iterrows():
        split_baseyear_pv(n, row["node"], float(row["rooftop_mw"]))
