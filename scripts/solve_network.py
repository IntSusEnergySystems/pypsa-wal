# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Solves optimal operation and capacity for a network with the option to
iteratively optimize while updating line reactances.

This script is used for optimizing the electrical network as well as the
sector coupled network.

Description
-----------

Total annual system costs are minimised with PyPSA. The full formulation of the
linear optimal power flow (plus investment planning
is provided in the
`documentation of PyPSA <https://pypsa.readthedocs.io/en/latest/optimal_power_flow.html#linear-optimal-power-flow>`_.

The optimization is based on the :func:`network.optimize` function.
Additionally, some extra constraints specified in :mod:`solve_network` are added.

.. note::

    The rules ``solve_elec_networks`` and ``solve_sector_networks`` run
    the workflow for all scenarios in the configuration file (``scenario:``)
    based on the rule :mod:`solve_network`.
"""

import importlib
import logging
import os
import re
import sys
from functools import partial
from typing import Any

import linopy
import numpy as np
import pandas as pd
from pathlib import Path
import pypsa
import xarray as xr
import yaml
from linopy.remote.oetc import OetcCredentials, OetcHandler, OetcSettings
from pypsa.descriptors import get_activity_mask
from pypsa.descriptors import get_switchable_as_dense as get_as_dense
from scripts.prepare_sector_network import determine_emission_sectors
from scripts.walloon_scripts.named_pins import (
    add_industry_cc_floor,
    add_rooftop_share_constraint,
    lookup_year_value,
    planning_year,
)
from scripts._benchmark import memory_logger
from scripts._helpers import (
    PYPSA_V1,
    configure_logging,
    get,
    set_scenario_config,
    update_config_from_wildcards,
)

logger = logging.getLogger(__name__)

# Allow for PyPSA versions <0.35
if PYPSA_V1:
    pypsa.network.power_flow.logger.setLevel(logging.WARNING)
else:
    pypsa.pf.logger.setLevel(logging.WARNING)


class ObjectiveValueError(Exception):
    pass


def add_land_use_constraint_perfect(n: pypsa.Network) -> None:
    """
    Add global constraints for tech capacity limit.

    Parameters
    ----------
    n : pypsa.Network
        The PyPSA network instance

    Returns
    -------
    pypsa.Network
        Network with added land use constraints
    """
    logger.info("Add land-use constraint for perfect foresight")

    def compress_series(s):
        def process_group(group):
            if group.nunique() == 1:
                return pd.Series(group.iloc[0], index=[None])
            else:
                return group

        return s.groupby(level=[0, 1]).apply(process_group)

    def new_index_name(t):
        # Convert all elements to string and filter out None values
        parts = [str(x) for x in t if x is not None]
        # Join with space, but use a dash for the last item if not None
        return " ".join(parts[:2]) + (f"-{parts[-1]}" if len(parts) > 2 else "")

    def check_p_min_p_max(p_nom_max):
        p_nom_min = n.generators[ext_i].groupby(grouper).sum().p_nom_min
        p_nom_min = p_nom_min.reindex(p_nom_max.index)
        check = (
            p_nom_min.groupby(level=[0, 1]).sum()
            > p_nom_max.groupby(level=[0, 1]).min()
        )
        if check.sum():
            logger.warning(
                f"summed p_min_pu values at node larger than technical potential {check[check].index}"
            )

    grouper = [n.generators.carrier, n.generators.bus, n.generators.build_year]
    ext_i = n.generators.p_nom_extendable
    # get technical limit per node and investment period
    p_nom_max = n.generators[ext_i].groupby(grouper).min().p_nom_max
    # drop carriers without tech limit
    p_nom_max = p_nom_max[~p_nom_max.isin([np.inf, np.nan])]
    # carrier
    carriers = p_nom_max.index.get_level_values(0).unique()
    gen_i = n.generators[(n.generators.carrier.isin(carriers)) & (ext_i)].index
    n.generators.loc[gen_i, "p_nom_min"] = 0
    # check minimum capacities
    check_p_min_p_max(p_nom_max)
    # drop multi entries in case p_nom_max stays constant in different periods
    # p_nom_max = compress_series(p_nom_max)
    # adjust name to fit syntax of nominal constraint per bus
    df = p_nom_max.reset_index()
    df["name"] = df.apply(
        lambda row: f"nom_max_{row['carrier']}"
        + (f"_{row['build_year']}" if row["build_year"] is not None else ""),
        axis=1,
    )

    for name in df.name.unique():
        df_carrier = df[df.name == name]
        bus = df_carrier.bus
        n.buses.loc[bus, name] = df_carrier.p_nom_max.values


def add_land_use_constraint(n: pypsa.Network, planning_horizons: str) -> None:
    """
    Add land use constraints for renewable energy potential.

    Parameters
    ----------
    n : pypsa.Network
        The PyPSA network instance
    planning_horizons : str
        The planning horizon year as string

    Returns
    -------
    pypsa.Network
        Modified PyPSA network with constraints added
    """
    # warning: this will miss existing offwind which is not classed AC-DC and has carrier 'offwind'

    for carrier in [
        "solar",
        "solar rooftop",
        "solar-hsat",
        "onwind",
        "offwind-ac",
        "offwind-dc",
        "offwind-float",
    ]:
        ext_i = (n.generators.carrier == carrier) & ~n.generators.p_nom_extendable
        grouper = n.generators.loc[ext_i].index.str.replace(
            f" {carrier}.*$", "", regex=True
        )
        existing = n.generators.loc[ext_i, "p_nom"].groupby(grouper).sum()
        existing.index += f" {carrier}-{planning_horizons}"
        # a bus can carry existing capacity without a current-vintage extendable
        # twin (retired carrier, custom busmap); indexing those would raise
        existing = existing.reindex(existing.index.intersection(n.generators.index))
        n.generators.loc[existing.index, "p_nom_max"] -= existing

    # check if existing capacities are larger than technical potential
    existing_large = n.generators[
        n.generators["p_nom_min"] > n.generators["p_nom_max"]
    ].index
    if len(existing_large):
        logger.warning(
            f"Existing capacities larger than technical potential for {existing_large},\
                        adjust technical potential to existing capacities"
        )
        n.generators.loc[existing_large, "p_nom_max"] = n.generators.loc[
            existing_large, "p_nom_min"
        ]

    n.generators["p_nom_max"] = n.generators["p_nom_max"].clip(lower=0)


def add_solar_potential_constraints(n: pypsa.Network, config: dict) -> None:
    """
    Add constraint to make sure the sum capacity of all solar technologies (fixed, tracking, ets. ) is below the region potential.

    Example:
    ES1 0: total solar potential is 10 GW, meaning:
           solar potential : 10 GW
           solar-hsat potential : 8 GW (solar with single axis tracking is assumed to have higher land use)
    The constraint ensures that:
           solar_p_nom + solar_hsat_p_nom * 1.13 <= 10 GW
    """
    land_use_factors = {
        "solar-hsat": config["renewable"]["solar"]["capacity_per_sqkm"]
        / config["renewable"]["solar-hsat"]["capacity_per_sqkm"],
    }
    rename = {} if PYPSA_V1 else {"Generator-ext": "Generator"}

    solar_carriers = ["solar", "solar-hsat"]
    solar = n.generators[
        n.generators.carrier.isin(solar_carriers) & n.generators.p_nom_extendable
    ].index

    solar_today = n.generators[
        (n.generators.carrier == "solar") & (n.generators.p_nom_extendable)
    ].index
    solar_hsat = n.generators[(n.generators.carrier == "solar-hsat")].index

    if solar.empty:
        return

    land_use = pd.DataFrame(1, index=solar, columns=["land_use_factor"])
    for carrier, factor in land_use_factors.items():
        land_use = land_use.apply(
            lambda x: (x * factor) if carrier in x.name else x, axis=1
        )

    location = pd.Series(n.buses.index, index=n.buses.index)
    ggrouper = n.generators.loc[solar].bus
    rhs = (
        n.generators.loc[solar_today, "p_nom_max"]
        .groupby(n.generators.loc[solar_today].bus.map(location))
        .sum()
        - n.generators.loc[solar_hsat, "p_nom"]
        .groupby(n.generators.loc[solar_hsat].bus.map(location))
        .sum()
        * land_use_factors["solar-hsat"]
    ).clip(lower=0)

    lhs = (
        (n.model["Generator-p_nom"].rename(rename).loc[solar] * land_use.squeeze())
        .groupby(ggrouper)
        .sum()
    )

    logger.info("Adding solar potential constraint.")
    n.model.add_constraints(lhs <= rhs, name="solar_potential")


def add_co2_sequestration_limit(
    n: pypsa.Network,
    limit_dict: dict[str, float],
    planning_horizons: str | None,
) -> None:
    """
    Add a global constraint on the amount of Mt CO2 that can be sequestered.

    Parameters
    ----------
    n : pypsa.Network
        The PyPSA network instance
    limit_dict : dict[str, float]
        CO2 sequestration potential limit constraints by year.
    planning_horizons : str, optional
        The current planning horizon year or None in perfect foresight
    """

    if not n.investment_periods.empty:
        nyears = n.snapshot_weightings.groupby(level="period").generators.sum() / 8760
        periods = n.investment_periods
        limit = pd.Series(
            {period: nyears[period] * get(limit_dict, period) for period in periods}
        )
        limit.index = limit.index.map(lambda s: f"co2_sequestration_limit-{s}")
        names = limit.index
    else:
        nyears = n.snapshot_weightings.generators.sum() / 8760
        limit = get(limit_dict, int(planning_horizons)) * nyears
        periods = np.nan
        names = "co2_sequestration_limit"

    n.add(
        "GlobalConstraint",
        names,
        sense=">=",
        constant=-limit * 1e6,
        type="operational_limit",
        carrier_attribute="co2 sequestered",
        investment_period=periods,
    )


def add_carbon_constraint(n: pypsa.Network, snapshots: pd.DatetimeIndex) -> None:
    glcs = n.global_constraints.query('type == "co2_atmosphere"')
    if glcs.empty:
        return
    for name, glc in glcs.iterrows():
        carattr = glc.carrier_attribute
        emissions = n.carriers.query(f"{carattr} != 0")[carattr]

        if emissions.empty:
            continue

        # stores
        bus_carrier = n.stores.bus.map(n.buses.carrier)
        stores = n.stores[bus_carrier.isin(emissions.index) & ~n.stores.e_cyclic]
        if not stores.empty:
            last = n.snapshot_weightings.reset_index().groupby("period").last()
            last_i = last.set_index([last.index, last.timestep]).index
            final_e = n.model["Store-e"].loc[last_i, stores.index]
            time_valid = int(glc.loc["investment_period"])
            time_i = pd.IndexSlice[time_valid, :]
            lhs = final_e.loc[time_i, :] - final_e.shift(snapshot=1).loc[time_i, :]

            rhs = glc.constant
            n.model.add_constraints(lhs <= rhs, name=f"GlobalConstraint-{name}")


def add_carbon_budget_constraint(n: pypsa.Network, snapshots: pd.DatetimeIndex) -> None:
    glcs = n.global_constraints.query('type == "Co2Budget"')
    if glcs.empty:
        return
    for name, glc in glcs.iterrows():
        carattr = glc.carrier_attribute
        emissions = n.carriers.query(f"{carattr} != 0")[carattr]

        if emissions.empty:
            continue

        # stores
        bus_carrier = n.stores.bus.map(n.buses.carrier)
        stores = n.stores[bus_carrier.isin(emissions.index) & ~n.stores.e_cyclic]
        if not stores.empty:
            last = n.snapshot_weightings.reset_index().groupby("period").last()
            last_i = last.set_index([last.index, last.timestep]).index
            final_e = n.model["Store-e"].loc[last_i, stores.index]
            time_valid = int(glc.loc["investment_period"])
            time_i = pd.IndexSlice[time_valid, :]
            weighting = n.investment_period_weightings.loc[time_valid, "years"]
            lhs = final_e.loc[time_i, :] * weighting

            rhs = glc.constant
            n.model.add_constraints(lhs <= rhs, name=f"GlobalConstraint-{name}")


def add_max_growth(n: pypsa.Network, opts: dict) -> None:
    """
    Add maximum growth rates for different carriers.
    """

    # take maximum yearly difference between investment periods since historic growth is per year
    factor = n.investment_period_weightings.years.max() * opts["factor"]
    for carrier in opts["max_growth"].keys():
        max_per_period = opts["max_growth"][carrier] * factor
        logger.info(
            f"set maximum growth rate per investment period of {carrier} to {max_per_period} GW."
        )
        n.carriers.loc[carrier, "max_growth"] = max_per_period * 1e3

    for carrier in opts["max_relative_growth"].keys():
        max_r_per_period = opts["max_relative_growth"][carrier]
        logger.info(
            f"set maximum relative growth per investment period of {carrier} to {max_r_per_period}."
        )
        n.carriers.loc[carrier, "max_relative_growth"] = max_r_per_period


def add_retrofit_gas_boiler_constraint(
    n: pypsa.Network, snapshots: pd.DatetimeIndex
) -> None:
    """
    Allow retrofitting of existing gas boilers to H2 boilers and impose load-following must-run condition on existing gas boilers.
    Modifies the network in place, no return value.

    n : pypsa.Network
        The PyPSA network to be modified
    snapshots : pd.DatetimeIndex
        The snapshots of the network
    """
    c = "Link"
    logger.info("Add constraint for retrofitting gas boilers to H2 boilers.")
    # existing gas boilers
    mask = n.links.carrier.str.contains("gas boiler") & ~n.links.p_nom_extendable
    gas_i = n.links[mask].index
    mask = n.links.carrier.str.contains("retrofitted H2 boiler")
    h2_i = n.links[mask].index

    n.links.loc[gas_i, "p_nom_extendable"] = True
    p_nom = n.links.loc[gas_i, "p_nom"]
    n.links.loc[gas_i, "p_nom"] = 0

    # heat profile
    cols = n.loads_t.p_set.columns[
        n.loads_t.p_set.columns.str.contains("heat")
        & ~n.loads_t.p_set.columns.str.contains("industry")
        & ~n.loads_t.p_set.columns.str.contains("agriculture")
    ]
    profile = n.loads_t.p_set[cols].div(
        n.loads_t.p_set[cols].groupby(level=0).max(), level=0
    )
    # to deal if max value is zero
    profile.fillna(0, inplace=True)
    profile.rename(columns=n.loads.bus.to_dict(), inplace=True)
    profile = profile.reindex(columns=n.links.loc[gas_i, "bus1"])
    profile.columns = gas_i

    rhs = profile.mul(p_nom)

    dispatch = n.model["Link-p"]
    active = get_activity_mask(n, c, snapshots, gas_i)
    rhs = rhs[active]
    if PYPSA_V1:
        p_gas = dispatch.sel(name=gas_i)
        p_h2 = dispatch.sel(name=h2_i)
    else:
        p_gas = dispatch.sel(Link=gas_i)
        p_h2 = dispatch.sel(Link=h2_i)

    lhs = p_gas + p_h2

    n.model.add_constraints(lhs == rhs, name="gas_retrofit")


def prepare_network(
    n: pypsa.Network,
    solve_opts: dict,
    foresight: str,
    planning_horizons: str | None,
    co2_sequestration_potential: dict[str, float],
    limit_max_growth: dict[str, Any] | None = None,
) -> None:
    """
    Prepare network with various constraints and modifications.

    Parameters
    ----------
    n : pypsa.Network
        The PyPSA network instance
    solve_opts : Dict
        Dictionary of solving options containing clip_p_max_pu, load_shedding etc.
    foresight : str
        Planning foresight type ('myopic' or 'perfect')
    planning_horizons : str or None
        The current planning horizon year or None for perfect foresight
    co2_sequestration_potential : Dict[str, float]
        CO2 sequestration potential constraints by year

    Returns
    -------
    pypsa.Network
        Modified PyPSA network with added constraints
    """
    if "clip_p_max_pu" in solve_opts:
        for df in (
            n.generators_t.p_max_pu,
            n.generators_t.p_min_pu,
            n.links_t.p_max_pu,
            n.links_t.p_min_pu,
            n.storage_units_t.inflow,
        ):
            df.where(df.abs() > solve_opts["clip_p_max_pu"], other=0.0, inplace=True)

    if load_shedding := solve_opts.get("load_shedding"):
        # intersect between macroeconomic and surveybased willingness to pay
        # http://journal.frontiersin.org/article/10.3389/fenrg.2015.00055/full
        n.add("Carrier", "load")
        buses_i = n.buses.index
        if isinstance(load_shedding, bool):
            load_shedding = 1e5  # Eur/MWh

        n.add(
            "Generator",
            buses_i,
            " load",
            bus=buses_i,
            carrier="load",
            marginal_cost=load_shedding,  # Eur/MWh
            p_nom=np.inf,
        )

    if solve_opts.get("curtailment_mode"):
        n.add("Carrier", "curtailment", color="#fedfed", nice_name="Curtailment")
        n.generators_t.p_min_pu = n.generators_t.p_max_pu
        buses_i = n.buses.query("carrier == 'AC'").index
        n.add(
            "Generator",
            buses_i,
            suffix=" curtailment",
            bus=buses_i,
            p_min_pu=-1,
            p_max_pu=0,
            marginal_cost=-0.1,
            carrier="curtailment",
            p_nom=1e6,
        )

    if solve_opts.get("noisy_costs"):
        for t in n.components:
            # if 'capital_cost' in t.static:
            #    t.static['capital_cost'] += 1e1 + 2.*(np.random.random(len(t.static)) - 0.5)
            if "marginal_cost" in t.static:
                t.static["marginal_cost"] += 1e-2 + 2e-3 * (
                    np.random.random(len(t.static)) - 0.5
                )

        for t in n.components[["Line", "Link"]]:
            if t.static.empty:
                continue
            t.static["capital_cost"] += (
                1e-1 + 2e-2 * (np.random.random(len(t.static)) - 0.5)
            ) * t.static["length"]

    if solve_opts.get("nhours"):
        nhours = solve_opts["nhours"]
        n.set_snapshots(n.snapshots[:nhours])
        n.snapshot_weightings[:] = 8760.0 / nhours

    if foresight == "myopic" and planning_horizons:
        add_land_use_constraint(n, planning_horizons)

    if foresight == "perfect":
        add_land_use_constraint_perfect(n)
        if limit_max_growth is not None and limit_max_growth["enable"]:
            add_max_growth(n, limit_max_growth)

    if n.stores.carrier.eq("co2 sequestered").any():
        limit_dict = co2_sequestration_potential
        add_co2_sequestration_limit(
            n, limit_dict=limit_dict, planning_horizons=planning_horizons
        )
    


def res_growth_allowance(config, planning_horizons):
    """MW of new RES build allowed in this planning period, per (country, carrier).

    The build-rate limit of ``docs/renewable-potentials.md`` section 3:

        new build in a period <= growth_multiplier x record annual addition x years

    ``record annual addition`` is the best single year observed 2000-2024 in IRENA
    statistics, precomputed into ``build_rates_file`` by
    ``scripts/walloon_scripts/build_res_build_rates.py`` (IRENASTAT needs internet
    and a populated cache, which a cluster compute node does not have).

    Returns MW of *new* capacity, which is directly comparable to the
    ``agg_p_nom_max`` right-hand side because ``include_existing`` has already
    subtracted the standing fleet from it. Returns ``None`` when the limit is not
    configured, or for the first planning horizon, which is pinned to the
    historical fleet by the CSV rather than bounded by a growth rate.
    """
    opts = config["solving"]["agg_p_nom_limits"]
    multiplier = opts.get("growth_multiplier")
    path = opts.get("build_rates_file")
    if not multiplier or not path or not Path(path).exists():
        if multiplier or path:
            logger.warning(
                "RES growth limit not applied: growth_multiplier=%r build_rates_file=%r",
                multiplier,
                path,
            )
        return None

    horizons = sorted(int(y) for y in config["scenario"]["planning_horizons"])
    year = int(planning_horizons)
    if year not in horizons or horizons.index(year) == 0:
        return None  # base year: pinned by the CSV, no previous horizon to grow from
    years = year - horizons[horizons.index(year) - 1]

    rates = pd.read_csv(path, comment="#")
    allowance = (
        rates.set_index(["node", "carrier"]).record_annual_MW * multiplier * years
    )
    allowance.index = allowance.index.rename(["country", "carrier"])
    logger.info(
        "RES growth limit: %.1f x IRENA record x %d yr for %d (country, carrier) groups",
        multiplier,
        years,
        len(allowance),
    )
    return allowance


def corridor_tolerance(agg_p_nom_minmax_raw: pd.DataFrame) -> pd.Series:
    """Per-(country, carrier) corridor width, read from the caps file itself.

    The `tolerance` column of ``agg_p_nom_minmax*.csv`` holds a *relative* width,
    e.g. ``0.005`` for half a percent; a blank cell means zero, i.e. leave the
    corridor exactly as stated. It lives in the data because it is a statement
    about the capacity figures on that row -- how precisely the source pins that
    country's fleet -- and not a property of the solver or of the code.

    Rows with no tolerance column at all (the upstream `data/agg_p_nom_minmax.csv`
    predates it) get zero throughout, which reproduces the previous behaviour.
    """
    if ("tolerance", "rel") in agg_p_nom_minmax_raw.columns:
        column = agg_p_nom_minmax_raw[("tolerance", "rel")]
    elif "tolerance" in agg_p_nom_minmax_raw.columns:
        column = agg_p_nom_minmax_raw["tolerance"]
    else:
        return pd.Series(0.0, index=agg_p_nom_minmax_raw.index)
    return pd.to_numeric(column, errors="coerce").fillna(0.0)


def widen_collapsed_corridors(
    agg_p_nom_minmax: pd.DataFrame,
    tolerance: pd.Series,
    planning_horizons: str | None,
) -> pd.DataFrame:
    """Stop an aggregate capacity corridor from being an exact equality.

    Where the CSV states ``min == max`` for a (country, carrier) group, the two
    ``agg_p_nom`` constraints together pin a *sum* of extendable capacities to an
    exact value. With ``include_existing`` both sides then subtract the same
    standing fleet, so the residual right-hand side is a difference of two nearly
    equal large numbers -- 0.20 MW for BE ``offwind-all`` in 2025, against
    individual ``p_nom_max`` bounds summing to 16 000 MW. A barrier method has to
    drive an aggregate of variables whose bounds span five orders of magnitude
    onto that point from both sides, and on 2026-08-29 it stalled 3.4 % above its
    own dual bound rather than converging.

    Widening the ceiling to ``min * (1 + tolerance)`` costs at most `tolerance` of
    the pinned fleet and leaves a corridor the barrier can sit inside. The width
    comes from the caps file, per row -- see :func:`corridor_tolerance`.
    """
    both = agg_p_nom_minmax[["min", "max"]].dropna()
    if both.empty:
        return agg_p_nom_minmax
    tol = tolerance.reindex(both.index).fillna(0.0)
    collapsed = both.index[
        ((both["max"] - both["min"]).abs() <= 1e-6 * both["min"].abs().clip(lower=1.0))
        & (tol > 0)
    ]
    if collapsed.empty:
        return agg_p_nom_minmax
    agg_p_nom_minmax = agg_p_nom_minmax.copy()
    agg_p_nom_minmax.loc[collapsed, "max"] = agg_p_nom_minmax.loc[
        collapsed, "min"
    ] * (1 + tolerance.reindex(collapsed).fillna(0.0))
    logger.info(
        "Widened %d collapsed capacity corridor(s) for %s: %s",
        len(collapsed),
        planning_horizons,
        ", ".join(
            f"{a} {b} by {100 * tolerance.get((a, b), 0.0):.2f} %"
            for a, b in collapsed
        ),
    )
    return agg_p_nom_minmax


def _widen_against(
    maximum: pd.Series,
    minimum: pd.Series,
    tolerance: pd.Series,
    planning_horizons: str | None,
    what: str,
) -> pd.Series:
    """Lift ``maximum`` off ``minimum`` wherever the two coincide.

    The companion to :func:`widen_collapsed_corridors`, for corridors that are
    open in the CSV but collapse while the right-hand sides are built. Widening
    the ceiling rather than lowering the floor keeps every policy floor exactly
    as stated. The width is the same per-row figure from the caps file, so a
    group the file does not mention is left alone.
    """
    if maximum.empty or minimum.empty:
        return maximum
    lo = minimum.reindex(maximum.index)
    tol = tolerance.reindex(maximum.index).fillna(0.0)
    collapsed = [
        k
        for k in maximum.index
        if pd.notna(lo.get(k))
        and tol.get(k, 0.0) > 0
        and abs(maximum[k] - lo[k]) <= 1e-6 * max(abs(lo[k]), 1.0)
    ]
    if not collapsed:
        return maximum
    maximum = maximum.copy()
    maximum.loc[collapsed] = lo.loc[collapsed] * (1 + tol.reindex(collapsed))
    logger.info(
        "Widened %d collapsed %s corridor(s) for %s: %s",
        len(collapsed),
        what,
        planning_horizons,
        ", ".join(f"{a} {b} by {100 * tol.get((a, b), 0.0):.2f} %" for a, b in collapsed),
    )
    return maximum


def _parent_country(n: pypsa.Network, region: str) -> str | None:
    """ISO code a region node belongs to (`BEWAL` -> `BE`).

    Read from the buses at that location rather than from the node's own AC
    bus, so an already-solved network whose `country` column was rewritten by
    an older version of this function still resolves correctly.
    """
    at_loc = n.buses[n.buses.location.astype(str) == str(region)]
    codes = [
        str(c)
        for c in at_loc.country.astype(str)
        if str(c) not in ("", "nan", str(region))
    ]
    if not codes:
        return None
    return pd.Series(codes).mode().iloc[0]


def add_CCL_constraints(
    n: pypsa.Network, config: dict, planning_horizons: str | None
) -> None:
    """
    Add CCL (country & carrier limit) constraint to the network.

    Add minimum and maximum levels of generator nominal capacity per carrier
    for individual countries. Opts and path for agg_p_nom_minmax.csv must be defined
    in config.yaml. Default file is available at data/agg_p_nom_minmax.csv.

    Parameters
    ----------
    n : pypsa.Network
        The PyPSA network instance
    config : dict
        Configuration dictionary
    planning_horizons : str, optional
        The current planning horizon year or None in perfect foresight

    Example
    -------
    scenario:
        opts: [Co2L-CCL-24h]
    electricity:
        agg_p_nom_limits: data/agg_p_nom_minmax.csv
    """

    assert planning_horizons is not None, (
        "add_CCL_constraints are not implemented for perfect foresight, yet"
    )
    
    agg_p_nom_minmax = pd.read_csv(
        config["solving"]["agg_p_nom_limits"]["file"], index_col=[0, 1], header=[0, 1]
    )
    # Per-row corridor widths travel with the caps themselves, not with the code.
    tolerance = corridor_tolerance(agg_p_nom_minmax)

    if planning_horizons in agg_p_nom_minmax.columns:
        agg_p_nom_minmax = agg_p_nom_minmax[planning_horizons]
    else:
        return

    agg_p_nom_minmax = widen_collapsed_corridors(
        agg_p_nom_minmax, tolerance, planning_horizons
    )

    # A region row detaches that region from its parent country *for the carrier
    # it names, and only that carrier*. The previous implementation rewrote
    # `n.buses.country` per bus, which is carrier-blind: the first BEVLG row
    # (`BEVLG,nuclear-all`, 87552368) silently removed Flanders from every `BE`
    # row, so the 2025 offshore pin grouped nothing (2025 built the full 8 GW
    # potential) and 2030 applied Elia's whole 10 GW solar remainder to
    # Brussels, which has no land left -- an empty LP in 0 barrier iterations.
    # See B1 in docs/temporary_improvement_plans.md. The bus table is no longer
    # mutated, so there is nothing to restore afterwards either.
    rows = set(agg_p_nom_minmax.index)
    carriers_in_file = agg_p_nom_minmax.index.get_level_values(1).unique()
    locations = set(n.buses.location.dropna().astype(str))
    regions = sorted(set(agg_p_nom_minmax.index.get_level_values(0)) & locations)

    for region in regions:
        parent = _parent_country(n, region)
        if parent is None:
            continue
        # when a region has its own entry, subtract it from its parent country
        for carrier in carriers_in_file:
            region_idx = (region, carrier)
            parent_idx = (parent, carrier)
            if region_idx not in agg_p_nom_minmax.index:
                continue
            if parent_idx not in agg_p_nom_minmax.index:
                continue
            for col in agg_p_nom_minmax.columns:
                region_val = agg_p_nom_minmax.loc[region_idx, col]
                parent_val = agg_p_nom_minmax.loc[parent_idx, col]
                if pd.isna(region_val) or pd.isna(parent_val):
                    continue
                agg_p_nom_minmax.loc[parent_idx, col] = max(parent_val - region_val, 0)

    def ccl_country(comp: pd.DataFrame, bus_col: str) -> pd.Series:
        """Group key: the region when the caps file names (region, carrier).

        Otherwise the bus keeps its own country, so a `BE` row still covers
        every Belgian node for the carriers no region row claims.
        """
        buses = comp[bus_col]
        loc = buses.map(n.buses.location).astype(object)
        ctry = buses.map(n.buses.country).astype(object)
        claimed = pd.Series(
            [(a, b) in rows for a, b in zip(loc, comp.carrier.astype(object))],
            index=comp.index,
        )
        return loc.where(claimed, ctry).rename(bus_col)

    logger.info("Adding generation capacity constraints per carrier and country")
    p_nom = n.model["Generator-p_nom"]
    p_nom_link = n.model["Link-p_nom"]

    gens = n.generators.query("p_nom_extendable")
    links = n.links.query("p_nom_extendable")

    if not PYPSA_V1:
        gens = gens.rename_axis(index="Generator-ext")
        links = links.rename_axis(index="Link-ext")

    if config["solving"]["agg_p_nom_limits"]["agg_offwind"]:
        rename_offwind = {
            "offwind-ac": "offwind-all",
            "offwind-dc": "offwind-all",
            "offwind-float": "offwind-all",
            "offwind": "offwind-all",
        }
        gens = gens.replace(rename_offwind)
    if config["solving"]["agg_p_nom_limits"]["agg_solar"]:
        rename_solar = {
            "solar": "solar-all",
            "solar-utility": "solar-all",
            "solar-hsat": "solar-all",
            # Rooftop belongs in the group. The numbers in the caps file are
            # Elia's *total* PV fleet (BE 9 751 MW in 2025, BEWAL 4 088), and
            # res_build_rates.csv derives the regional split from that same
            # total. With rooftop outside, the base-year pin bounded utility
            # alone and the 2025 solve came out at 5 510 MW of Walloon PV
            # against a 4 088 MW pin. It was taken out on 2026-09-02 because
            # item 8's share pin then needs ~1.4 GW of rooftop inside a 20 MW
            # corridor; that is a fault in the share pin, not in the group —
            # PyPSA labels the whole historical fleet `solar` while TIMES has
            # 0.5 GW rooftop + 1.4 GW utility in 2025. Item 8 stays off until
            # that base year is reconciled. See B5 of
            # docs/temporary_improvement_plans.md.
            "solar rooftop": "solar-all",
        }
        gens = gens.replace(rename_solar)
    if config["solving"]["agg_p_nom_limits"]["agg_nuclear"]:
        if foresight == "overnight":
            rename_nuclear = {
                "nuclear": "nuclear-all",
                "nuclear (SMR)": "nuclear-all",
            }
            gens = gens.replace(rename_nuclear)
        else:
            rename_nuclear = {
            "nuclear": "nuclear-all",
            "nuclear (SMR)": "nuclear-all",
            }
            links = links.replace(rename_nuclear)
    if config["solving"]["agg_p_nom_limits"]["agg_ccgt"]:
        links = links.replace({"CCGT": "CCGT-all", "CCGT CC": "CCGT-all"})
    grouper = pd.concat([ccl_country(gens, "bus"), gens.carrier], axis=1)
    grouper_links = pd.concat([ccl_country(links, "bus1"), links.carrier], axis=1)
    lhs = p_nom.groupby(grouper).sum().rename(bus="country")
    lhs_groups = lhs.indexes["group"] if "group" in lhs.indexes else pd.Index([])

    if not links.empty:
        eff_links = xr.DataArray(
            links.efficiency,
            coords={p_nom_link.dims[0]: links.index},
            dims=[p_nom_link.dims[0]],
        )
        p_nom_e = p_nom_link.loc[links.index] * eff_links
        lhs_links = p_nom_e.groupby(grouper_links).sum().rename(bus1="country")
    else:
        lhs_links = xr.DataArray([])

    if config["solving"]["agg_p_nom_limits"]["include_existing"]:
        gens_cst = n.generators.query("~p_nom_extendable").rename_axis(
            index="Generator-cst"
        )
        gens_cst = gens_cst[
            (gens_cst["build_year"] + gens_cst["lifetime"]) >= int(planning_horizons)
        ]
        links_cst = n.links.query("~p_nom_extendable").rename_axis(index="Link-cst")
        links_cst = links_cst[
            (links_cst["build_year"] + links_cst["lifetime"]) >= int(planning_horizons)
        ]
        if config["solving"]["agg_p_nom_limits"]["agg_offwind"]:
            gens_cst = gens_cst.replace(rename_offwind)
        if config["solving"]["agg_p_nom_limits"]["agg_solar"]:
            gens_cst = gens_cst.replace(rename_solar)
        if config["solving"]["agg_p_nom_limits"]["agg_nuclear"]:
            if foresight == "overnight":
                gens_cst = gens_cst.replace(rename_nuclear)
            else:
                links_cst = links_cst.replace(rename_nuclear)
        if config["solving"]["agg_p_nom_limits"]["agg_ccgt"]:
            links_cst = links_cst.replace({"CCGT": "CCGT-all", "CCGT CC": "CCGT-all"})
        rhs_cst = (
            pd.concat(
                [ccl_country(gens_cst, "bus"), gens_cst[["carrier", "p_nom"]]],
                axis=1,
            )
            .groupby(["bus", "carrier"])
            .sum()
        )
        links_cst = links_cst.assign(p_nom_e=links_cst.p_nom * links_cst.efficiency)
        rhs_cst_links = (
            pd.concat(
                [
                    ccl_country(links_cst, "bus1"),
                    links_cst[["carrier", "p_nom_e"]],
                ],
                axis=1,
            )
            .groupby(["bus1", "carrier"])
            .sum()
        )
        rhs_cst.index = rhs_cst.index.rename({"bus": "country"})
        rhs_cst_links.index = rhs_cst_links.index.rename({"bus1": "country"})
        rhs_min = agg_p_nom_minmax["min"].dropna()
        idx_min = rhs_min.index.join(rhs_cst.index, how="left")
        idx_min_links = rhs_min.index.join(rhs_cst_links.index, how="left")
        rhs_min = rhs_min.reindex(idx_min).fillna(0)
        rhs_min_links = rhs_min.reindex(idx_min_links).fillna(0)
        rhs = (rhs_min - rhs_cst.reindex(idx_min).fillna(0).p_nom).dropna()
        rhs_links = (
            rhs_min_links - rhs_cst_links.reindex(idx_min_links).fillna(0).p_nom_e
        ).dropna()
        rhs[rhs < 0] = 0
        rhs_links[rhs_links < 0] = 0
        # A TYNDP min cannot demand more new-build than remaining p_nom_max
        # (land-use already subtracted existing). 2050 NL offwind-all IIS:
        # min 1713 MW vs remaining potential 1163 MW → infeasible_or_unbounded.
        remaining_max = (
            pd.concat([grouper, gens.p_nom_max.rename("p_nom")], axis=1)
            .groupby(["bus", "carrier"])
            .sum()
            .p_nom
            .replace(np.inf, np.nan)
        )
        remaining_max.index = remaining_max.index.rename({"bus": "country"})
        rhs = rhs.clip(upper=remaining_max.reindex(rhs.index).fillna(np.inf))
        remaining_max_links = (
            pd.concat(
                [
                    grouper_links,
                    (links.p_nom_max * links.efficiency).rename("p_nom_e"),
                ],
                axis=1,
            )
            .groupby(["bus1", "carrier"])
            .sum()
            .p_nom_e
            .replace(np.inf, np.nan)
        )
        remaining_max_links.index = remaining_max_links.index.rename(
            {"bus1": "country"}
        )
        rhs_links = rhs_links.clip(
            upper=remaining_max_links.reindex(rhs_links.index).fillna(np.inf)
        )
        # The floor is left alone. This used to clip it down to the build-rate
        # limit so it could not sit above the ceiling the max branch applies
        # below -- but where a national target needs more than the industry has
        # ever built (German onshore wind, British offshore) that made the
        # corridor a single point, and across ~8 groups at once the feasible set
        # became a needle the barrier could not find: 2030 failed twice with
        # "Numerical trouble encountered" (269 iter / 3940 s and 201 / 2424 s,
        # Gurobi reporting "may be infeasible or unbounded"), while the same
        # model with the limit switched off solved to 3.69e11 in 169 iterations.
        # The max branch drops the ceiling for those groups instead.
        minimum = xr.DataArray(rhs).rename(dim_0="group")
        minimum_links = xr.DataArray(rhs_links).rename(dim_0="group")
    else:
        minimum = xr.DataArray(agg_p_nom_minmax["min"].dropna()).rename(dim_0="group")
        minimum_links = xr.DataArray(agg_p_nom_minmax["min"].dropna()).rename(
            dim_0="group"
        )

    index = minimum.indexes["group"].intersection(lhs.indexes["group"])
    index_links = minimum_links.indexes["group"].intersection(
        lhs_links.indexes["group"]
    )
    if not index.empty:
        n.model.add_constraints(
            lhs.sel(group=index) >= minimum.loc[index], name="agg_p_nom_min"
        )
    if not index_links.empty:
        n.model.add_constraints(
            lhs_links.sel(group=index_links) >= minimum_links.loc[index_links],
            name="agg_p_nom_min_links",
        )

    if config["solving"]["agg_p_nom_limits"]["include_existing"]:
        rhs_max = agg_p_nom_minmax["max"].dropna()
        idx_max = rhs_max.index.join(rhs_cst.index, how="left")
        idx_max_links = rhs_max.index.join(rhs_cst_links.index, how="left")
        rhs_max = rhs_max.reindex(idx_max).fillna(0)
        # the max for links mirrors the min branch: subtract non-extendable
        # existing capacity so the cap applies to the total. (Previously this
        # reused `rhs_links` from the min computation, so nuclear/CCGT link
        # maxima were silently enforced as a second minimum instead of a cap.)
        rhs_max_links = rhs_max.reindex(idx_max_links).fillna(0)
        rhs_links = (
            rhs_max_links - rhs_cst_links.reindex(idx_max_links).fillna(0).p_nom_e
        ).dropna()
        # a cap can never bind below the extendable lower bounds (brownfield
        # links carry p_nom_min > 0), so raise it there instead of flooring at
        # zero and making the LP infeasible
        lower_bounds_links = (
            pd.concat(
                [
                    grouper_links,
                    (links.p_nom_min * links.efficiency).rename("p_nom_e"),
                ],
                axis=1,
            )
            .groupby(["bus1", "carrier"])
            .sum()
            .p_nom_e
        )
        lower_bounds_links.index = lower_bounds_links.index.rename(
            {"bus1": "country"}
        )
        rhs_links = rhs_links.clip(
            lower=lower_bounds_links.reindex(rhs_links.index).fillna(0)
        )
        # generators need the same treatment as links above. Without it the cap
        # bound only the extendable tranche, so a myopic cap reset at every
        # horizon and the fleet grew past the aggregate limit.
        rhs_gens = (rhs_max - rhs_cst.reindex(idx_max).fillna(0).p_nom).dropna()
        # A standing fleet above its own cap is the one failure Gurobi reports
        # as "infeasible or unbounded in 0 barrier iterations", with no IIS and
        # no clue which group did it: 2030 was misdiagnosed three times that way
        # (items 6a, 8 and 11 in turn) before the cause was found. Say it out
        # loud instead. B1/B8 of docs/temporary_improvement_plans.md.
        over = rhs_gens[rhs_gens < -1e-6]
        for (country, carrier), gap in over.items():
            logger.warning(
                "%s %s at %s: the standing fleet already exceeds the aggregate "
                "cap by %.0f MW. Nothing new can be built and the corridor may "
                "be empty — check the previous horizon's solved network.",
                country,
                carrier,
                planning_horizons,
                -gap,
            )
        lower_bounds_gens = (
            pd.concat([grouper, gens.p_nom_min.rename("p_nom")], axis=1)
            .groupby(["bus", "carrier"])
            .sum()
            .p_nom
        )
        lower_bounds_gens.index = lower_bounds_gens.index.rename({"bus": "country"})
        rhs_gens = rhs_gens.clip(
            lower=lower_bounds_gens.reindex(rhs_gens.index).fillna(0)
        )
        # The build-rate limit is the operative ceiling past the base year: it
        # applies to every (country, carrier) in the rate table, whether or not
        # the CSV states a max, so the CSV only has to carry the 2025 base year
        # and the 2030 corridor. The land/sea potential is enforced separately as
        # `p_nom_max` by add_land_use_constraint, so a group ends up bounded by
        # min(potential, growth) exactly as intended.
        growth = res_growth_allowance(config, planning_horizons)
        if growth is not None:
            # A stated floor outranks the build-rate ceiling. Where a national
            # target already needs at least everything the growth limit allows,
            # imposing the limit as well pins the group to a point; dropping it
            # leaves the floor exactly as stated and lets land use (`p_nom_max`)
            # be the binding ceiling instead. Warn rather than silently reconcile
            # the two -- "this target exceeds the build-rate limit" is a finding
            # about the scenario, not a detail to bury.
            floors = rhs.reindex(growth.index)
            conflicting = growth.index[floors.notna() & (growth <= floors)]
            if len(conflicting):
                logger.warning(
                    "Build-rate limit dropped for %d group(s) at %s: the stated "
                    "capacity floor already meets or exceeds %s x the record "
                    "annual addition. %s",
                    len(conflicting),
                    planning_horizons,
                    config["solving"]["agg_p_nom_limits"].get("growth_multiplier"),
                    "; ".join(
                        f"{a} {b}: floor {floors[(a, b)]:.0f} MW vs limit "
                        f"{growth[(a, b)]:.0f} MW"
                        for a, b in conflicting
                    ),
                )
                growth = growth.drop(conflicting)
        if growth is not None and not growth.empty:
            union = rhs_gens.index.union(growth.index.intersection(lhs_groups))
            rhs_gens = rhs_gens.reindex(union)
            g = growth.reindex(union)
            rhs_gens = pd.concat([rhs_gens, g], axis=1).min(axis=1).dropna()
            rhs_gens = rhs_gens.clip(
                lower=lower_bounds_gens.reindex(rhs_gens.index).fillna(0)
            )
        # The growth clip can collapse a corridor that the CSV left open: the min
        # branch clips its floor *up* to the growth allowance and this branch
        # clips its ceiling *down* to the same number, so a group whose national
        # target exceeds the record build rate ends up with min == max. At 2030
        # that is BEWAL onwind (2509 MW), DE onwind (48910) and GB offwind-all
        # (26720), and the 2030 barrier hit "Numerical trouble encountered" with
        # its dual infeasibility pinned at 4.2e-04 for 200 iterations. Same
        # remedy as the base year, applied to whatever the collapse produced.
        rhs_gens = _widen_against(rhs_gens, rhs, tolerance, planning_horizons, "generators")
        rhs_links = _widen_against(
            rhs_links, minimum_links.to_series(), tolerance, planning_horizons, "links"
        )
        maximum = xr.DataArray(rhs_gens).rename(dim_0="group")
        maximum_links = xr.DataArray(rhs_links).rename(dim_0="group")
    else:
        maximum = xr.DataArray(agg_p_nom_minmax["max"].dropna()).rename(dim_0="group")
        maximum_links = xr.DataArray(agg_p_nom_minmax["max"].dropna()).rename(
            dim_0="group"
        )

    index = maximum.indexes["group"].intersection(lhs.indexes["group"])
    index_links = maximum_links.indexes["group"].intersection(
        lhs_links.indexes["group"]
    )
    if not index.empty:
        n.model.add_constraints(
            lhs.sel(group=index) <= maximum.loc[index], name="agg_p_nom_max"
        )
    if not index_links.empty:
        n.model.add_constraints(
            lhs_links.sel(group=index_links) <= maximum_links.loc[index_links],
            name="agg_p_nom_max_links",
        )

    # Nothing to reset: `n.buses.country` is never mutated, so the solved
    # network keeps the real ISO codes and downstream consumers (national CO2
    # attribution, review_run, pypsa2html) group by `location` as they expect.


def add_EQ_constraints(n, o, scaling=1e-1):
    """
    Add equity constraints to the network.

    Currently this is only implemented for the electricity sector only.

    Opts must be specified in the config.yaml.

    Parameters
    ----------
    n : pypsa.Network
    o : str

    Example
    -------
    scenario:
        opts: [Co2L-EQ0.7-24h]

    Require each country or node to on average produce a minimal share
    of its total electricity consumption itself. Example: EQ0.7c demands each country
    to produce on average at least 70% of its consumption; EQ0.7 demands
    each node to produce on average at least 70% of its consumption.
    """
    # TODO: Generalize to cover myopic and other sectors?
    float_regex = r"[0-9]*\.?[0-9]+"
    level = float(re.findall(float_regex, o)[0])
    if o[-1] == "c":
        ggrouper = n.generators.bus.map(n.buses.country)
        lgrouper = n.loads.bus.map(n.buses.country)
        sgrouper = n.storage_units.bus.map(n.buses.country)
    else:
        ggrouper = n.generators.bus
        lgrouper = n.loads.bus
        sgrouper = n.storage_units.bus
    load = (
        n.snapshot_weightings.generators
        @ n.loads_t.p_set.groupby(lgrouper, axis=1).sum()
    )
    inflow = (
        n.snapshot_weightings.stores
        @ n.storage_units_t.inflow.groupby(sgrouper, axis=1).sum()
    )
    inflow = inflow.reindex(load.index).fillna(0.0)
    rhs = scaling * (level * load - inflow)
    p = n.model["Generator-p"]
    lhs_gen = (
        (p * (n.snapshot_weightings.generators * scaling))
        .groupby(ggrouper.to_xarray())
        .sum()
        .sum("snapshot")
    )
    # TODO: double check that this is really needed, why do have to subtract the spillage
    if not n.storage_units_t.inflow.empty:
        spillage = n.model["StorageUnit-spill"]
        lhs_spill = (
            (spillage * (-n.snapshot_weightings.stores * scaling))
            .groupby(sgrouper.to_xarray())
            .sum()
            .sum("snapshot")
        )
        lhs = lhs_gen + lhs_spill
    else:
        lhs = lhs_gen
    n.model.add_constraints(lhs >= rhs, name="equity_min")


def add_BAU_constraints(n: pypsa.Network, config: dict) -> None:
    """
    Add business-as-usual (BAU) constraints for minimum capacities.

    Parameters
    ----------
    n : pypsa.Network
        PyPSA network instance
    config : dict
        Configuration dictionary containing BAU minimum capacities
    """
    mincaps = pd.Series(config["electricity"]["BAU_mincapacities"])
    p_nom = n.model["Generator-p_nom"]
    ext_i = n.generators.query("p_nom_extendable")
    ext_carrier_i = xr.DataArray(ext_i.carrier)
    if not PYPSA_V1:
        ext_carrier_i = ext_carrier_i.rename_axis("Generator-ext")
    lhs = p_nom.groupby(ext_carrier_i).sum()
    rhs = mincaps[lhs.indexes["carrier"]].rename_axis("carrier")
    n.model.add_constraints(lhs >= rhs, name="bau_mincaps")


# TODO: think about removing or make per country
def add_SAFE_constraints(n, config):
    """
    Add a capacity reserve margin of a certain fraction above the peak demand.
    Renewable generators and storage do not contribute. Ignores network.

    Parameters
    ----------
        n : pypsa.Network
        config : dict

    Example
    -------
    config.yaml requires to specify opts:

    scenario:
        opts: [Co2L-SAFE-24h]
    electricity:
        SAFE_reservemargin: 0.1
    Which sets a reserve margin of 10% above the peak demand.
    """
    peakdemand = n.loads_t.p_set.sum(axis=1).max()
    margin = 1.0 + config["electricity"]["SAFE_reservemargin"]
    reserve_margin = peakdemand * margin
    conventional_carriers = config["electricity"]["conventional_carriers"]  # noqa: F841
    ext_gens_i = n.generators.query(
        "carrier in @conventional_carriers & p_nom_extendable"
    ).index
    p_nom = n.model["Generator-p_nom"].loc[ext_gens_i]
    lhs = p_nom.sum()
    exist_conv_caps = n.generators.query(
        "~p_nom_extendable & carrier in @conventional_carriers"
    ).p_nom.sum()
    rhs = reserve_margin - exist_conv_caps
    n.model.add_constraints(lhs >= rhs, name="safe_mintotalcap")


def add_operational_reserve_margin(n, sns, config):
    """
    Build reserve margin constraints based on the formulation given in
    https://genxproject.github.io/GenX/dev/core/#Reserves.

    Parameters
    ----------
        n : pypsa.Network
        sns: pd.DatetimeIndex
        config : dict

    Example:
    --------
    config.yaml requires to specify operational_reserve:
    operational_reserve: # like https://genxproject.github.io/GenX/dev/core/#Reserves
        activate: true
        epsilon_load: 0.02 # percentage of load at each snapshot
        epsilon_vres: 0.02 # percentage of VRES at each snapshot
        contingency: 400000 # MW
    """
    reserve_config = config["electricity"]["operational_reserve"]
    EPSILON_LOAD = reserve_config["epsilon_load"]
    EPSILON_VRES = reserve_config["epsilon_vres"]
    CONTINGENCY = reserve_config["contingency"]

    # Reserve Variables
    n.model.add_variables(
        0, np.inf, coords=[sns, n.generators.index], name="Generator-r"
    )
    reserve = n.model["Generator-r"]
    summed_reserve = reserve.sum("Generator")

    # Share of extendable renewable capacities
    ext_i = n.generators.query("p_nom_extendable").index
    vres_i = n.generators_t.p_max_pu.columns
    if not ext_i.empty and not vres_i.empty:
        capacity_factor = n.generators_t.p_max_pu[vres_i.intersection(ext_i)]
        p_nom_vres = n.model["Generator-p_nom"].loc[vres_i.intersection(ext_i)]
        if not PYPSA_V1:
            p_nom_vres = p_nom_vres.rename({"Generator-ext": "Generator"})
        lhs = summed_reserve + (
            p_nom_vres * (-EPSILON_VRES * xr.DataArray(capacity_factor))
        ).sum("Generator")

        # Total demand per t
        demand = get_as_dense(n, "Load", "p_set").sum(axis=1)

        # VRES potential of non extendable generators
        capacity_factor = n.generators_t.p_max_pu[vres_i.difference(ext_i)]
        renewable_capacity = n.generators.p_nom[vres_i.difference(ext_i)]
        potential = (capacity_factor * renewable_capacity).sum(axis=1)

        # Right-hand-side
        rhs = EPSILON_LOAD * demand + EPSILON_VRES * potential + CONTINGENCY

        n.model.add_constraints(lhs >= rhs, name="reserve_margin")

    # additional constraint that capacity is not exceeded
    gen_i = n.generators.index
    ext_i = n.generators.query("p_nom_extendable").index
    fix_i = n.generators.query("not p_nom_extendable").index

    dispatch = n.model["Generator-p"]
    reserve = n.model["Generator-r"]

    capacity_variable = n.model["Generator-p_nom"]
    if not PYPSA_V1:
        capacity_variable = capacity_variable.rename({"Generator-ext": "Generator"})
    capacity_fixed = n.generators.p_nom[fix_i]

    p_max_pu = get_as_dense(n, "Generator", "p_max_pu")

    lhs = dispatch + reserve - capacity_variable * xr.DataArray(p_max_pu[ext_i])

    rhs = (p_max_pu[fix_i] * capacity_fixed).reindex(columns=gen_i, fill_value=0)

    n.model.add_constraints(lhs <= rhs, name="Generator-p-reserve-upper")


def add_TES_energy_to_power_ratio_constraints(n: pypsa.Network) -> None:
    """
    Add TES constraints to the network.

    For each TES storage unit, enforce:
        Store-e_nom - etpr * Link-p_nom == 0

    Parameters
    ----------
    n : pypsa.Network
        A PyPSA network with TES and heating sectors enabled.

    Raises
    ------
    ValueError
        If no valid TES storage or charger links are found.
    RuntimeError
        If the TES storage and charger indices do not align.
    """
    indices_charger_p_nom_extendable = n.links.index[
        n.links.index.str.contains("water tanks charger|water pits charger")
        & n.links.p_nom_extendable
    ]
    indices_stores_e_nom_extendable = n.stores.index[
        n.stores.index.str.contains("water tanks|water pits")
        & n.stores.e_nom_extendable
    ]

    if indices_charger_p_nom_extendable.empty or indices_stores_e_nom_extendable.empty:
        logger.warning(
            "No valid extendable charger links or stores found for TES energy-to-power constraints.Not enforcing TES energy-to-power ratio constraints!"
        )
        return

    energy_to_power_ratio_values = n.links.loc[
        indices_charger_p_nom_extendable, "energy to power ratio"
    ].values

    linear_expr_list = []
    for charger, tes, energy_to_power_value in zip(
        indices_charger_p_nom_extendable,
        indices_stores_e_nom_extendable,
        energy_to_power_ratio_values,
    ):
        charger_var = n.model["Link-p_nom"].loc[charger]
        if not tes == charger.replace(" charger", ""):
            # e.g. "DE0 0 urban central water tanks charger-2050" -> "DE0 0 urban central water tanks-2050"
            raise RuntimeError(
                f"Charger {charger} and TES {tes} do not match. "
                "Ensure that the charger and TES are in the same location and refer to the same technology."
            )
        store_var = n.model["Store-e_nom"].loc[tes]
        linear_expr = store_var - energy_to_power_value * charger_var
        linear_expr_list.append(linear_expr)

    # Merge the individual expressions
    dim = "Store-ext, Link-ext" if PYPSA_V1 else "name"
    merged_expr = linopy.expressions.merge(
        linear_expr_list, dim=dim, cls=type(linear_expr_list[0])
    )

    n.model.add_constraints(merged_expr == 0, name="TES_energy_to_power_ratio")


def add_TES_charger_ratio_constraints(n: pypsa.Network) -> None:
    """
    Add TES charger ratio constraints.

    For each TES unit, enforce:
        Link-p_nom(charger) - efficiency * Link-p_nom(discharger) == 0

    Parameters
    ----------
    n : pypsa.Network
        A PyPSA network with TES and heating sectors enabled.

    Raises
    ------
    ValueError
        If no valid TES discharger or charger links are found.
    RuntimeError
        If the charger and discharger indices do not align.
    """
    indices_charger_p_nom_extendable = n.links.index[
        n.links.index.str.contains(
            "water tanks charger|water pits charger|aquifer thermal energy storage charger"
        )
        & n.links.p_nom_extendable
    ]
    indices_discharger_p_nom_extendable = n.links.index[
        n.links.index.str.contains(
            "water tanks discharger|water pits discharger|aquifer thermal energy storage discharger"
        )
        & n.links.p_nom_extendable
    ]

    if (
        indices_charger_p_nom_extendable.empty
        or indices_discharger_p_nom_extendable.empty
    ):
        logger.warning(
            "No valid extendable TES discharger or charger links found for TES charger ratio constraints. Not enforcing TES charger_ratio constraints."
        )
        return

    for charger, discharger in zip(
        indices_charger_p_nom_extendable, indices_discharger_p_nom_extendable
    ):
        if not charger.replace(" charger", " ") == discharger.replace(
            " discharger", " "
        ):
            # e.g. "DE0 0 urban central water tanks charger-2050" -> "DE0 0 urban central water tanks-2050"
            raise RuntimeError(
                f"Charger {charger} and discharger {discharger} do not match. "
                "Ensure that the charger and discharger are in the same location and refer to the same technology."
            )

    eff_discharger = n.links.efficiency[indices_discharger_p_nom_extendable].values
    lhs = (
        n.model["Link-p_nom"].loc[indices_charger_p_nom_extendable]
        - n.model["Link-p_nom"].loc[indices_discharger_p_nom_extendable]
        * eff_discharger
    )

    n.model.add_constraints(lhs == 0, name="TES_charger_ratio")


def add_battery_constraints(n):
    """
    Add constraint ensuring that charger = discharger, i.e.
    1 * charger_size - efficiency * discharger_size = 0
    """
    if not n.links.p_nom_extendable.any():
        return

    discharger_bool = n.links.index.str.contains("battery discharger")
    charger_bool = n.links.index.str.contains("battery charger")

    dischargers_ext = n.links[discharger_bool].query("p_nom_extendable").index
    chargers_ext = n.links[charger_bool].query("p_nom_extendable").index

    eff = n.links.efficiency[dischargers_ext].values
    lhs = (
        n.model["Link-p_nom"].loc[chargers_ext]
        - n.model["Link-p_nom"].loc[dischargers_ext] * eff
    )

    n.model.add_constraints(lhs == 0, name="Link-charger_ratio")


def add_lossy_bidirectional_link_constraints(n):
    if not n.links.p_nom_extendable.any() or not any(n.links.get("reversed", [])):
        return

    carriers = n.links.loc[n.links.reversed, "carrier"].unique()  # noqa: F841
    backwards = n.links.query(
        "carrier in @carriers and p_nom_extendable and reversed and active"
    ).index
    forwards = backwards.str.replace("-reversed", "")
    lhs = n.model["Link-p_nom"].loc[backwards]
    rhs = n.model["Link-p_nom"].loc[forwards]
    n.model.add_constraints(lhs == rhs, name="Link-bidirectional_sync")


def add_chp_constraints(n):
    electric = (
        n.links.index.str.contains("urban central")
        & n.links.index.str.contains("CHP")
        & n.links.index.str.contains("electric")
    )
    heat = (
        n.links.index.str.contains("urban central")
        & n.links.index.str.contains("CHP")
        & n.links.index.str.contains("heat")
    )

    electric_ext = n.links[electric].query("p_nom_extendable").index
    heat_ext = n.links[heat].query("p_nom_extendable").index

    electric_fix = n.links[electric].query("~p_nom_extendable").index
    heat_fix = n.links[heat].query("~p_nom_extendable").index

    p = n.model["Link-p"]  # dimension: [time, link]

    # output ratio between heat and electricity and top_iso_fuel_line for extendable
    if not electric_ext.empty:
        p_nom = n.model["Link-p_nom"]

        lhs = (
            p_nom.loc[electric_ext]
            * (n.links.p_nom_ratio * n.links.efficiency)[electric_ext].values
            - p_nom.loc[heat_ext] * n.links.efficiency[heat_ext].values
        )
        n.model.add_constraints(lhs == 0, name="chplink-fix_p_nom_ratio")

        rename = {} if PYPSA_V1 else {"Link-ext": "Link"}
        lhs = (
            p.loc[:, electric_ext]
            + p.loc[:, heat_ext]
            - p_nom.rename(rename).loc[electric_ext]
        )
        n.model.add_constraints(lhs <= 0, name="chplink-top_iso_fuel_line_ext")

    # top_iso_fuel_line for fixed
    if not electric_fix.empty:
        lhs = p.loc[:, electric_fix] + p.loc[:, heat_fix]
        rhs = n.links.p_nom[electric_fix]
        n.model.add_constraints(lhs <= rhs, name="chplink-top_iso_fuel_line_fix")

    # back-pressure
    if not electric.empty:
        lhs = (
            p.loc[:, heat] * (n.links.efficiency[heat] * n.links.c_b[electric].values)
            - p.loc[:, electric] * n.links.efficiency[electric]
        )
        n.model.add_constraints(lhs <= rhs, name="chplink-backpressure")


def add_pipe_retrofit_constraint(n):
    """
    Add constraint for retrofitting existing CH4 pipelines to H2 pipelines.
    """
    if "reversed" not in n.links.columns:
        n.links["reversed"] = False
    gas_pipes_i = n.links.query(
        "carrier == 'gas pipeline' and p_nom_extendable and ~reversed and active"
    ).index
    h2_retrofitted_i = n.links.query(
        "carrier == 'H2 pipeline retrofitted' and p_nom_extendable and ~reversed and active"
    ).index

    if h2_retrofitted_i.empty or gas_pipes_i.empty:
        return

    p_nom = n.model["Link-p_nom"]

    CH4_per_H2 = 1 / n.config["sector"]["H2_retrofit_capacity_per_CH4"]
    lhs = p_nom.loc[gas_pipes_i] + CH4_per_H2 * p_nom.loc[h2_retrofitted_i]
    rhs = n.links.p_nom[gas_pipes_i]
    if not PYPSA_V1:
        rhs = rhs.rename_axis("Link-ext")

    n.model.add_constraints(lhs == rhs, name="Link-pipe_retrofit")


def add_flexible_egs_constraint(n):
    """
    Upper bounds the charging capacity of the geothermal reservoir according to
    the well capacity.
    """
    well_index = n.links.loc[n.links.carrier == "geothermal heat"].index
    storage_index = n.storage_units.loc[
        n.storage_units.carrier == "geothermal heat"
    ].index

    p_nom_rhs = n.model["Link-p_nom"].loc[well_index]
    p_nom_lhs = n.model["StorageUnit-p_nom"].loc[storage_index]

    n.model.add_constraints(
        p_nom_lhs <= p_nom_rhs,
        name="upper_bound_charging_capacity_of_geothermal_reservoir",
    )


def add_import_limit_constraint(n: pypsa.Network, sns: pd.DatetimeIndex):
    """
    Add constraint for limiting green energy imports (synthetic and biomass).
    Does not include fossil fuel imports.
    """

    nyears = n.snapshot_weightings.generators.sum() / 8760

    import_links = n.links.loc[n.links.carrier.str.contains("import")].index
    import_gens = n.generators.loc[n.generators.carrier.str.contains("import")].index

    limit = n.config["sector"]["imports"]["limit"]
    limit_sense = n.config["sector"]["imports"]["limit_sense"]

    if (import_links.empty and import_gens.empty) or not np.isfinite(limit):
        return

    weightings = n.snapshot_weightings.loc[sns, "generators"]

    # everything needs to be in MWh_fuel
    eff = n.links.loc[import_links, "efficiency"]

    p_gens = n.model["Generator-p"].loc[sns, import_gens]
    p_links = n.model["Link-p"].loc[sns, import_links]

    lhs = (p_gens * weightings).sum() + (p_links * eff * weightings).sum()

    rhs = limit * 1e6 * nyears

    n.model.add_constraints(lhs, limit_sense, rhs, name="import_limit")


def add_co2_atmosphere_constraint(n, snapshots):
    glcs = n.global_constraints[n.global_constraints.type == "co2_atmosphere"]

    if glcs.empty:
        return
    for name, glc in glcs.iterrows():
        carattr = glc.carrier_attribute
        emissions = n.carriers.query(f"{carattr} != 0")[carattr]

        if emissions.empty:
            continue

        # stores
        bus_carrier = n.stores.bus.map(n.buses.carrier)
        stores = n.stores[bus_carrier.isin(emissions.index) & ~n.stores.e_cyclic]
        if not stores.empty:
            last_i = snapshots[-1]
            lhs = n.model["Store-e"].loc[last_i, stores.index]
            rhs = glc.constant

            n.model.add_constraints(lhs <= rhs, name=f"GlobalConstraint-{name}")

def add_selfsufficiency_constraints(n, settings, planning_horizons=None):
    """Cap annual electricity imports, as a fraction of local supply or in TWh.

    The original formulation (Koen van Greevenbroek) uses an ``Import_p``
    variable per location, lower-bounded by net inflows on AC lines and DC
    links, and caps the annual sum at ``(1 - level) * local_energy``. Item 6a
    keeps that machinery and adds an **absolute TWh** right-hand side scoped
    to a list of nodes (BEWAL).

    What the variable measures: the **hourly positive part of net cross-border
    inflow**, summed over the year. Exports never net imports off
    (``Import_p >= 0``), which is the right analogue of the TIMES
    ``Transfo_Imp`` process — also a one-way annual flow — and is *not* the
    annual net balance. B6 fixed three defects in the expression: AC and DC
    were capped separately (so the bound was the larger, not the sum), the
    ``-reversed`` leg of every DC pair was filtered out (so DC imports were
    invisible), and both flows were inflated (``/ s_max_pu`` on lines,
    ``/ efficiency`` on links) instead of using the physical flow.
    """
    if isinstance(settings, (int, float)):
        settings = {"mode": "fraction", "level": float(settings)}

    mode = settings.get("mode", "fraction")
    requested = settings.get("nodes")
    if requested is not None:
        requested = [str(x) for x in requested]

    logger.info("Adding self sufficiency constraint (mode=%s)", mode)

    rhs_twh = None
    if mode == "absolute":
        year = planning_year(planning_horizons)
        limit_twh = settings.get("limit_twh")
        if isinstance(limit_twh, dict) and year is not None:
            rhs_twh = limit_twh.get(year, limit_twh.get(str(year)))
        elif isinstance(limit_twh, (int, float)):
            rhs_twh = limit_twh
        if rhs_twh is None:
            # Loud: a cap that silently does nothing on one horizon is the same
            # failure class as the lifetime override that never reached the
            # model (B7) and the `solar-hsat` hurdle rate that never matched.
            logger.warning(
                "Self-sufficiency absolute cap is ENABLED but `limit_twh` has "
                "no entry for planning horizon %s (keys: %s) — the cap is "
                "INACTIVE this horizon.",
                year,
                sorted(settings.get("limit_twh") or {}),
            )
            return

    def group(df, b="bus"):
        mapped = df[b].map(n.buses.location)
        mapped.name = "bus"
        return mapped.to_xarray()

    locations = n.buses.location.dropna().drop_duplicates()
    if requested:
        locations = locations[locations.isin(requested)]
    if locations.empty:
        logger.warning("Self-sufficiency: no matching locations, skip")
        return

    n.model.add_variables(
        coords={"bus": locations.rename("bus"), "snapshot": n.snapshots},
        dims=("bus", "snapshot"),
        name="Import_p",
        lower=0,
    )

    cross_region_lines = n.lines.loc[
        (group(n.lines, b="bus0") != group(n.lines, b="bus1")).to_numpy()
    ]
    cross_region_links = n.links.iloc[0:0]
    if not n.links.empty:
        cross_region_links = n.links.loc[
            (group(n.links, b="bus0") != group(n.links, b="bus1")).to_numpy()
        ]
        if not cross_region_links.empty:
            # Keep BOTH legs of a lossy bidirectional pair. Dropping the
            # `-reversed` leg dropped the *import* direction: BEWAL's only DC
            # border is ALEGrO, whose reversed link (DE -> BEWAL) carries every
            # imported MWh, so the cap saw exports only. B6.
            cross_region_links = cross_region_links.loc[
                cross_region_links.carrier.isin(["DC"])
            ]

    import_buses = list(n.model["Import_p"].indexes["bus"])

    # One expression over AC and DC together. Adding a constraint per component
    # made `Import_p` the *larger* of the two nets rather than their sum. B6.
    net_total = None
    for component_name, df in (
        ("Line", cross_region_lines),
        ("Link", cross_region_links),
    ):
        if df.empty:
            continue

        if component_name == "Line":
            # physical flow: `s` is what crosses the border. Dividing by
            # `s_max_pu` (0.7 here) inflated every AC import by 43 %. B6.
            flow = n.model["Line-s"].loc[:, df.index]
            # With `solving.options.transmission_losses` PyPSA books half the
            # line loss against each end (constraints.py, `Line/loss/bus0` and
            # `bus1`, both -0.5), so a node receives `s - loss/2` and sends
            # `s + loss/2`. Using raw `s` at both ends counts energy that never
            # arrives. B6 applied this same "count what arrives" rule to links
            # (`p * efficiency`); lines were lossless when it was written.
            half_loss = None
            if "Line-loss" in n.model.variables:
                loss = n.model["Line-loss"]
                idx = df.index.intersection(loss.indexes[loss.dims[-1]])
                if len(idx) == len(df.index):
                    half_loss = 0.5 * loss.loc[:, df.index]
                elif len(idx):
                    logger.warning(
                        "Self-sufficiency: `Line-loss` covers %d of %d "
                        "cross-region lines; ignoring losses in the cap.",
                        len(idx),
                        len(df.index),
                    )
            arriving = flow if half_loss is None else flow - half_loss
            leaving = flow if half_loss is None else flow + half_loss
            inflow = arriving.groupby(group(df, "bus1")).sum()
            outflow = leaving.groupby(group(df, "bus0")).sum()
        else:
            # `p` is withdrawn at bus0; `p * efficiency` arrives at bus1.
            eff = df["efficiency"]
            flow = n.model["Link-p"].loc[:, df.index]
            inflow = (flow * eff).groupby(group(df, "bus1")).sum()
            outflow = flow.groupby(group(df, "bus0")).sum()

        bus_dim = "bus"
        in_buses = list(inflow.indexes[bus_dim])
        out_buses = list(outflow.indexes[bus_dim])
        union = list(dict.fromkeys(in_buses + out_buses))
        if not union:
            continue
        inflow = inflow.reindex({bus_dim: union}, fill_value=0)
        outflow = outflow.reindex({bus_dim: union}, fill_value=0)
        net = (inflow - outflow).reindex({bus_dim: import_buses}, fill_value=0)
        net_total = net if net_total is None else net_total + net

    if net_total is not None:
        n.model.add_constraints(
            n.model["Import_p"] >= net_total,
            name="import_positive",
        )

    imported_elec = (
        n.model["Import_p"] * n.snapshot_weightings.generators
    ).sum("snapshot")

    if mode == "absolute":
        rhs_mwh = float(rhs_twh) * 1e6
        # One named constraint per node, under the `GlobalConstraint-<name>`
        # convention PyPSA uses to map duals back (same as the per-country CO2
        # caps). Without it the cap left no trace in the solved `.nc`: neither
        # `review_run.py` nor the report could check compliance, and the
        # shadow price of an imported MWh -- the most interesting output the
        # cap produces -- was thrown away with the model.
        for node in import_buses:
            gc_name = f"import_limit_{node}"
            n.model.add_constraints(
                imported_elec.sel(bus=node) <= rhs_mwh,
                name=f"GlobalConstraint-{gc_name}",
            )
            n.add(
                "GlobalConstraint",
                gc_name,
                constant=rhs_mwh,
                sense="<=",
                type="",
                carrier_attribute="",
            )
        logger.info(
            "Capped electricity imports at %s to %.2f TWh/a "
            "(one-way annual inflow, AC + DC, includes the other Belgian "
            "regions).",
            import_buses,
            float(rhs_twh),
        )
        return

    # Fraction of local production (original formulation).
    cfg = getattr(n, "config", None) or {}
    local_gen_carriers = list(
        set(cfg.get("pypsa_eur", {}).get("Generator", []) + ["solar rooftop"])
    )
    local_gen_i = n.generators.loc[
        n.generators.carrier.isin(local_gen_carriers)
        & (n.generators.bus.map(n.buses.location) != "EU")
    ].index
    local_energy = None
    if len(local_gen_i) > 0:
        local_gen_p = (
            n.model["Generator-p"]
            .loc[:, local_gen_i]
            .groupby(group(n.generators.loc[local_gen_i]))
            .sum()
        )
        local_energy = (local_gen_p * n.snapshot_weightings.generators).sum(
            "snapshot"
        )

    local_hydro_i = n.storage_units.loc[n.storage_units.carrier == "hydro"].index
    if len(local_hydro_i) > 0:
        local_hydro_p = (
            n.model["StorageUnit-p_dispatch"]
            .loc[:, local_hydro_i]
            .groupby(group(n.storage_units.loc[local_hydro_i]))
            .sum()
        )
        local_hydro = (local_hydro_p * n.snapshot_weightings.stores).sum("snapshot")
        local_energy = (
            local_hydro if local_energy is None else local_energy + local_hydro
        )

    conv_carriers = cfg.get("electricity", {}).get("conventional_carriers", [])
    local_conv_gen_i = n.links.loc[n.links.carrier.isin(conv_carriers)].index
    if len(local_conv_gen_i) > 0:
        local_conv_gen_p = n.model["Link-p"].loc[:, local_conv_gen_i]
        efficiencies = n.links.loc[local_conv_gen_i, "efficiency"]
        local_conv_gen_p = (
            (local_conv_gen_p * efficiencies)
            .groupby(group(n.links.loc[local_conv_gen_i], b="bus1"))
            .sum()
            .rename({"bus1": "bus"})
        )
        local_conv = (local_conv_gen_p * n.snapshot_weightings.generators).sum(
            "snapshot"
        )
        local_energy = local_conv if local_energy is None else local_energy + local_conv

    if local_energy is None:
        logger.warning("Self-sufficiency fraction mode: no local generation, skip")
        return

    level = float(settings.get("level", 0.7))
    n.model.add_constraints(
        imported_elec <= (1 - level) * local_energy,
        name="import_energy_limit",
    )

NATIONAL_CO2_COUNTRIES = ["BEBRU", "BEVLG", "BEWAL", "DE", "FR", "NL", "GB", "LU"]

# Aviation is out of scope for the *national* CO2 targets, on both sides of the
# constraint. Three reasons, in order of weight:
#   1. the authoritative trajectory in config/input_parameters_for_models.csv is
#      defined "hors aviation internationale & UTCATF";
#   2. international bunkers are memo items outside national inventories, and
#      the EU Effort Sharing Regulation excludes them;
#   3. it cannot be charged nationally without error. Kerosene is drawn from the
#      single `EU oil` bus, a large share of which is carbon-neutral
#      Fischer-Tropsch product, but that negative sits on location "EU" and the
#      attribution below drops "EU" — so the consumer pays a fossil factor for
#      fuel nobody is credited with decarbonising.
# Aviation stays in the global `CO2Limit`, where the carbon balance does close.
# Domestic aviation goes with it: the model has a single kerosene carrier and
# cannot separate the two (it is 0.4 % of Belgian aviation emissions).
AVIATION_SECTORS = ["domestic aviation", "international aviation"]
AVIATION_CARRIER = "kerosene for aviation"


def national_include_aviation(n) -> bool:
    """Item 13: aviation on the national cap, both sides, default off."""
    cfg = getattr(n, "config", None)
    if not isinstance(cfg, dict):
        return False
    return bool(cfg.get("co2_budget_national_include_aviation", False))


def national_co2_sectors(sectors, include_aviation: bool) -> list[str]:
    """RHS of the national cap. Must match the LHS filter in ``national_co2_expression``."""
    if include_aviation:
        return list(sectors)
    return [s for s in sectors if s not in AVIATION_SECTORS]

# emissions of these are accounted for at the European level, not nationally
NATIONAL_CO2_EXCLUDE = ["EU oil refining", "EU methanol import", "EU oil import"]

# carriers whose location sits on the input side rather than on bus1
NATIONAL_CO2_SOURCE_PATTERNS = [
    "process emissions",
    "HVC to air",
    "electrobiofuels",
    "unsustainable bioliquids",
    "biomass-to-methanol",
    "biomass to liquid",
]


def national_co2_country(n):
    """Country each link's CO2 is booked to, for the national accounts.

    Most country-specific links keep their locational information in ``bus1``.
    DAC is the exception (``bus3``), as are the source patterns, whose location
    sits on ``bus0``. Links that end up on ``EU`` are dropped: no national
    account can claim them.
    """
    country = n.links.bus1.map(n.buses.location)

    if "bus3" in n.links:
        country_DAC = n.links[n.links.carrier == "DAC"].bus3.map(n.buses.location)
        country[country_DAC.index] = country_DAC

    for pattern in NATIONAL_CO2_SOURCE_PATTERNS:
        source = n.links[n.links.carrier.str.contains(pattern)].bus0.map(
            n.buses.location
        )
        country[source.index] = source

    mask = country.isna() | (country == "")
    country[mask] = country[mask].index
    return country[country != "EU"]


def national_co2_expression(n, include_aviation: bool | None = None):
    """Linopy expression for annual CO2 per country, in t.

    Shared by the national cap and the national CO2 price so the two can never
    disagree on scope. Sums every link port that touches the ``co2`` carrier —
    i.e. ``co2 atmosphere`` — weighted by that port's efficiency.

    Aviation is excluded unless ``co2_budget_national_include_aviation`` is
    true (item 13). The flag must move the RHS in ``add_co2limit_country``
    at the same time.
    """
    p = n.model["Link-p"]  # dimension: (time, component)
    country = national_co2_country(n)
    if include_aviation is None:
        include_aviation = national_include_aviation(n)

    exclude = np.array(NATIONAL_CO2_EXCLUDE, dtype=object)
    if not include_aviation:
        exclude = np.append(
            exclude,
            n.links.index[
                n.links.carrier.astype(str).str.contains(AVIATION_CARRIER, na=False)
            ].values,
        )

    lhs = []
    for port in [col[3:] for col in n.links if col.startswith("bus")]:
        if port == str(0):
            efficiency = (
                n.links["efficiency"].apply(lambda x: 1.0).rename("efficiency0")
            )
        elif port == str(1):
            efficiency = n.links["efficiency"]
        else:
            efficiency = n.links[f"efficiency{port}"]
        mask = n.links[f"bus{port}"].map(n.buses.carrier).eq("co2")

        idx = n.links[mask].index
        idx = idx[~np.isin(idx, exclude)]
        idx = idx[idx.isin(country.index)]
        grouping = country.loc[idx]

        if not grouping.isnull().all():
            expr = (
                (p.loc[:, idx] * efficiency[idx])
                .groupby(grouping, axis=1)
                .sum()
                * n.snapshot_weightings.generators
            ).sum(dims="snapshot")
            lhs.append(expr)

    return sum(lhs)  # dimension: (country)


def add_co2limit_country(n, limit_countries, nyears=1.0):
    """
    Add a set of emissions limit constraints for specified countries.
    The countries and emissions limits are specified in the config file entry 'co2_budget_country_{investment_year}'.
    Parameters
    ----------
    n : pypsa.Network
    config : dict
    limit_countries : dict
    nyears: float, optional
        Used to scale the emissions constraint to the number of snapshots of the base network.
    """
    logger.info(f"Adding CO2 budget limit for each country as per unit of 1990 levels")

    countries = NATIONAL_CO2_COUNTRIES

    # TODO: import function from prepare_sector_network? Move to common place?
    sectors = determine_emission_sectors(options)
    national_sectors = national_co2_sectors(sectors, national_include_aviation(n))

    # convert Mt to tCO2
    co2_totals = 1e6 * pd.read_csv(snakemake.input.co2_totals_name, index_col=0)
    co2_limit_countries = co2_totals.loc[countries, national_sectors].sum(axis=1)
    if foresight == "overnight":
        updates = {
            "BEBRU": 9000000,
            "BEVLG": 56000000,
            "BEWAL": 31000000,
            "DE": 649000000,
            "FR": 369000000,
            "NL": 147000000,
            "GB": 385000000,
            "LU": 9000000
        }
        co2_limit_countries.update(updates)
    co2_limit_countries = co2_limit_countries.loc[
        co2_limit_countries.index.isin(limit_countries.keys())
    ]
    if suff_demand:
        lulucf = co2_totals.loc[countries, 'LULUCF']
        lulucf[lulucf > 0] = 0
        lulucf = lulucf * -1
        co2_limit_countries *= co2_limit_countries.index.map(limit_countries) * nyears
        co2_limit_countries = (co2_limit_countries + lulucf)
    else:
        co2_limit_countries *= co2_limit_countries.index.map(limit_countries) * nyears
        co2_limit_countries = (co2_limit_countries)

    lhs = national_co2_expression(n)  # dimension: (country)
    lhs = lhs.rename({list(lhs.dims)[0]: "snapshot"})
    rhs = pd.Series(co2_limit_countries)  # dimension: (country)
    for ct in lhs.indexes["snapshot"]:
        n.model.add_constraints(
            lhs.loc[ct] <= rhs[ct],
            name=f"GlobalConstraint-co2_limit_per_country{ct}",
        )
        n.add(
            "GlobalConstraint",
            f"co2_limit_per_country{ct}",
            constant=rhs[ct],
            sense="<=",
            type="",
        )

def add_co2price_country(n, co2_price_countries, nyears=1.0):
    """
    Add a CO2 price per country by internalizing emissions into the objective.

    Parameters
    ----------
    n : pypsa.Network
    co2_price_countries : dict
        CO2 price in €/tCO2 per country (keys must match country codes)
    nyears : float, optional
        Scaling factor for snapshot weighting
    """

    logger.info("Adding CO2 price per country to objective function")

    lhs = national_co2_expression(n)  # dimension: (country)
    dim = list(lhs.dims)[0]
    price = pd.Series(co2_price_countries)
    # align with lhs countries
    price = price.reindex(lhs.indexes[dim]).fillna(0.0)
    price_da = xr.DataArray(price, dims=[dim])
    # total CO2 cost
    co2_cost = (lhs * price_da * nyears).sum(dim=dim)
    n.model.objective = n.model.objective + co2_cost

    logger.info("CO2 pricing successfully added to objective.")
    
    
def extra_functionality(
    n: pypsa.Network, snapshots: pd.DatetimeIndex, planning_horizons: str | None = None
) -> None:
    """
    Add custom constraints and functionality.

    Parameters
    ----------
    n : pypsa.Network
        The PyPSA network instance with config and params attributes
    snapshots : pd.DatetimeIndex
        Simulation timesteps
    planning_horizons : str, optional
        The current planning horizon year or None in perfect foresight

    Collects supplementary constraints which will be passed to
    ``pypsa.optimization.optimize``.

    If you want to enforce additional custom constraints, this is a good
    location to add them. The arguments ``opts`` and
    ``snakemake.config`` are expected to be attached to the network.
    """
    config = n.config
    constraints = config["solving"].get("constraints", {})
    if constraints["BAU"] and n.generators.p_nom_extendable.any():
        add_BAU_constraints(n, config)
    if constraints["SAFE"] and n.generators.p_nom_extendable.any():
        add_SAFE_constraints(n, config)
    if constraints["CCL"] and n.generators.p_nom_extendable.any():
        add_CCL_constraints(n, config, planning_horizons)

    reserve = config["electricity"].get("operational_reserve", {})
    if reserve.get("activate"):
        add_operational_reserve_margin(n, snapshots, config)

    if EQ_o := constraints["EQ"]:
        add_EQ_constraints(n, EQ_o.replace("EQ", ""))

    if {"solar-hsat", "solar"}.issubset(
        config["electricity"]["renewable_carriers"]
    ) and {"solar-hsat", "solar"}.issubset(
        config["electricity"]["extendable_carriers"]["Generator"]
    ):
        add_solar_potential_constraints(n, config)

    if n.config.get("sector", {}).get("tes", False):
        if n.buses.index.str.contains(
            r"urban central heat|urban decentral heat|rural heat",
            case=False,
            na=False,
        ).any():
            add_TES_energy_to_power_ratio_constraints(n)
            add_TES_charger_ratio_constraints(n)

    add_battery_constraints(n)
    add_lossy_bidirectional_link_constraints(n)
    add_pipe_retrofit_constraint(n)
    if n._multi_invest:
        add_carbon_constraint(n, snapshots)
        add_carbon_budget_constraint(n, snapshots)
        add_retrofit_gas_boiler_constraint(n, snapshots)
    else:
        add_co2_atmosphere_constraint(n, snapshots)

    if config["sector"]["enhanced_geothermal"]["enable"]:
        add_flexible_egs_constraint(n)

    if config["sector"]["imports"]["enable"]:
        add_import_limit_constraint(n, snapshots)
    ss = config.get("self_sufficiency") or {}
    if ss.get("self_sufficiency_constraint"):
        add_selfsufficiency_constraints(n, ss, planning_horizons)

    sector_cfg = config.get("sector") or {}
    rooftop_cfg = sector_cfg.get("rooftop_share") or {}
    if rooftop_cfg.get("enable"):
        year = planning_year(planning_horizons)
        share = lookup_year_value(rooftop_cfg, year, "shares", "share")
        node = rooftop_cfg.get("node", "BEWAL")
        if share is not None:
            add_rooftop_share_constraint(n, node, float(share))
    cc_cfg = sector_cfg.get("industry_cc_floor") or {}
    if cc_cfg.get("enable"):
        year = planning_year(planning_horizons)
        kt = lookup_year_value(cc_cfg, year, "kt", "kt")
        node = cc_cfg.get("node", "BEWAL")
        if kt is not None:
            add_industry_cc_floor(n, node, float(kt))
    if n.config["co2_budget_national"]:
        # prepare co2 constraint
        nhours = n.snapshot_weightings.generators.sum()
        nyears = nhours / 8760
        investment_year = int(snakemake.wildcards.planning_horizons[-4:])
        limit_countries = snakemake.config["budget_national"][investment_year]
        # add co2 constraint for each country
        add_co2limit_country(n, limit_countries, nyears)

    if n.config["co2_price_national"]:
        # prepare co2 constraint
        nhours = n.snapshot_weightings.generators.sum()
        nyears = nhours / 8760
        investment_year = int(snakemake.wildcards.planning_horizons[-4:])
        co2_price_countries = snakemake.config["price_national"][investment_year]
        # add co2 constraint for each country
        add_co2price_country(n,co2_price_countries,nyears)

    if n.params.custom_extra_functionality:
        source_path = n.params.custom_extra_functionality
        assert os.path.exists(source_path), f"{source_path} does not exist"
        sys.path.append(os.path.dirname(source_path))
        module_name = os.path.splitext(os.path.basename(source_path))[0]
        module = importlib.import_module(module_name)
        custom_extra_functionality = getattr(module, module_name)
        custom_extra_functionality(n, snapshots, snakemake)  # pylint: disable=E0601


def check_objective_value(n: pypsa.Network, solving: dict) -> None:
    """
    Check if objective value matches expected value within tolerance.

    Parameters
    ----------
    n : pypsa.Network
        Network with solved objective
    solving : Dict
        Dictionary containing objective checking parameters

    Raises
    ------
    ObjectiveValueError
        If objective value differs from expected value beyond tolerance
    """
    check_objective = solving["check_objective"]
    if check_objective["enable"]:
        atol = check_objective["atol"]
        rtol = check_objective["rtol"]
        expected_value = check_objective["expected_value"]
        if not np.isclose(n.objective, expected_value, atol=atol, rtol=rtol):
            raise ObjectiveValueError(
                f"Objective value {n.objective} differs from expected value "
                f"{expected_value} by more than {atol}."
            )


def collect_kwargs(
    config: dict,
    solving: dict,
    planning_horizons: str | None = None,
    log_fn: str | None = None,
    mode: str = "single",
) -> tuple[dict, dict]:
    """
    Prepare keyword arguments separated for model creation and model solving.

    Parameters
    ----------
    config : dict
        Configuration dictionary containing solver settings
    solving : dict
        Dictionary of solving options and configuration
    planning_horizons : str, optional
        The current planning horizon year or None in perfect foresight
    log_fn : str, optional
        Path to solver log file
    mode : str, optional
        Optimization mode: 'single', 'rolling_horizon', or 'iterative'
        Default is 'single'

    Returns
    -------
    tuple[dict, dict]
        Two dictionaries: (model_kwargs, solve_kwargs)
        - model_kwargs: Arguments for n.optimize.create_model()
        - solve_kwargs: Arguments for n.optimize.solve_model()
        For 'rolling_horizon' and 'iterative' modes, returns merged kwargs
        with additional mode-specific parameters
    """
    set_of_options = solving["solver"]["options"]
    cf_solving = solving["options"]

    # Model creation kwargs
    model_kwargs = {}
    model_kwargs["multi_investment_periods"] = config["foresight"] == "perfect"
    model_kwargs["transmission_losses"] = cf_solving.get("transmission_losses", False)
    model_kwargs["linearized_unit_commitment"] = cf_solving.get(
        "linearized_unit_commitment", False
    )

    # Solve kwargs
    solver_name = solving["solver"]["name"]
    solver_options = solving["solver_options"][set_of_options] if set_of_options else {}

    solve_kwargs = {}
    solve_kwargs["solver_name"] = solver_name
    solve_kwargs["solver_options"] = solver_options
    solve_kwargs["assign_all_duals"] = cf_solving.get("assign_all_duals", False)
    solve_kwargs["io_api"] = cf_solving.get("io_api", None)
    solve_kwargs["keep_files"] = cf_solving.get("keep_files", False)

    if log_fn:
        solve_kwargs["log_fn"] = log_fn

    oetc = solving.get("oetc", None)
    if oetc:
        oetc["credentials"] = OetcCredentials(
            email=os.environ["OETC_EMAIL"], password=os.environ["OETC_PASSWORD"]
        )
        oetc["solver"] = solver_name
        oetc["solver_options"] = solver_options
        oetc_settings = OetcSettings(**oetc)
        oetc_handler = OetcHandler(oetc_settings)
        solve_kwargs["remote"] = oetc_handler

    if solver_name == "gurobi":
        logging.getLogger("gurobipy").setLevel(logging.CRITICAL)

    # Handle special modes
    if mode == "rolling_horizon":
        all_kwargs = {**model_kwargs, **solve_kwargs}
        all_kwargs["horizon"] = cf_solving.get("horizon", 365)
        all_kwargs["overlap"] = cf_solving.get("overlap", 0)
        return all_kwargs, {}

    elif mode == "iterative":
        all_kwargs = {**model_kwargs, **solve_kwargs}
        all_kwargs["track_iterations"] = cf_solving["track_iterations"]
        all_kwargs["min_iterations"] = cf_solving["min_iterations"]
        all_kwargs["max_iterations"] = cf_solving["max_iterations"]

        if cf_solving["post_discretization"].get("enable", False):
            logger.info("Add post-discretization parameters.")
            all_kwargs.update(cf_solving["post_discretization"])

        return all_kwargs, {}

    return model_kwargs, solve_kwargs


def create_optimization_model(
    n: pypsa.Network,
    config: dict,
    params: dict,
    model_kwargs: dict,
    solve_kwargs: dict,
    planning_horizons: str | None = None,
) -> None:
    """
    Prepare optimization problem by creating model and adding extra functionality.

    This function:
    1. Attaches config and params to network for extra_functionality
    2. Creates the optimization model
    3. Adds extra functionality (custom constraints)

    Parameters
    ----------
    n : pypsa.Network
        The PyPSA network instance
    config : dict
        Configuration dictionary containing solver settings
    params : dict
        Dictionary of solving parameters
    model_kwargs : dict
        Arguments for n.optimize.create_model()
    solve_kwargs : dict
        Arguments for n.optimize.solve_model()
    planning_horizons : str, optional
        The current planning horizon year or None in perfect foresight
    """
    # Add config and params to network for extra_functionality
    n.config = config
    n.params = params

    # Create optimization model
    logger.info("Creating optimization model...")
    n.optimize.create_model(**model_kwargs)

    # Add extra functionality (custom constraints)
    logger.info("Adding extra functionality (custom constraints)...")
    extra_functionality(n, n.snapshots, planning_horizons)

def add_adjust_caps(
    n: pypsa.Network,
) -> None:
    investment_year = int(snakemake.wildcards.planning_horizons[-4:])
    n.generators.loc["DE 0 onwind", "p_nom"] = 68000
    n.generators.loc["DE 0 onwind", "p_nom_min"] = 68000
    n.generators.loc["DE 0 offwind-ac", "p_nom"] = 10000
    n.generators.loc["DE 0 offwind-ac", "p_nom_min"] = 10000
    n.generators.loc["FR 0 offwind-ac", "p_nom"] = 1600
    n.generators.loc["FR 0 offwind-ac", "p_nom_min"] = 1600
    n.generators.loc["GB 0 onwind", "p_nom"] = 15000
    n.generators.loc["GB 0 onwind", "p_nom_min"] = 15000
    n.generators.loc["FR 0 onwind", "p_nom"] = 24000
    n.generators.loc["FR 0 onwind", "p_nom_min"] = 24000
    n.generators.loc["NL 0 offwind-ac", "p_nom"] = 4700
    n.generators.loc["NL 0 offwind-ac", "p_nom_min"] = 4700
    n.generators.loc["GB 0 offwind-ac", "p_nom"] = 16000
    n.generators.loc["GB 0 offwind-ac", "p_nom_min"] = 16000
    n.generators.loc["FR nuclear", "p_nom_min"] = 62907.02
    n.generators.loc["FR nuclear", "p_nom"] = 62907.02
    n.generators.loc["NL nuclear", "p_nom_min"] = 485
    n.generators.loc["NL nuclear", "p_nom"] = 485
    n.generators.loc["GB nuclear", "p_nom_min"] = 5510
    n.generators.loc["GB nuclear", "p_nom"] = 5510
    # if investment_year == 2025:
    n.generators.loc["BEWAL nuclear", "p_nom_min"] = 1980
    n.generators.loc["BEWAL nuclear", "p_nom"] = 1980
    n.generators.loc["BEVLG nuclear", "p_nom_min"] = 1980
    n.generators.loc["BEVLG nuclear", "p_nom"] = 1980
    # elif investment_year > 2025:
    #   n.generators.loc["BEWAL nuclear", "p_nom_min"] = 1000
    #   n.generators.loc["BEWAL nuclear", "p_nom"] = 1000
    #   n.generators.loc["BEVLG nuclear", "p_nom_min"] = 1000
    #   n.generators.loc["BEVLG nuclear", "p_nom"] = 1000
    # else:
    #  n.generators.loc["BEWAL nuclear", "p_nom_min"] = 0
    #  n.generators.loc["BEWAL nuclear", "p_nom"] = 0
    #  n.generators.loc["BEVLG nuclear", "p_nom_min"] = 0
    #  n.generators.loc["BEVLG nuclear", "p_nom"] = 0

if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "solve_sector_network",
            opts="",
            clusters="5",
            configfiles="config/test/config.overnight.yaml",
            sector_opts="",
            planning_horizons="2030",
        )
    configure_logging(snakemake)
    set_scenario_config(snakemake)
    update_config_from_wildcards(snakemake.config, snakemake.wildcards)
    options = snakemake.params.sector
    solve_opts = snakemake.params.solving["options"]
    cf_solving = snakemake.params.solving["options"]
    config = snakemake.config
    suff_demand = config.get("sector", {}).get("suff_demand", False)
    np.random.seed(solve_opts.get("seed", 123))

    # Load network
    n = pypsa.Network(snakemake.input.network)
    planning_horizons = snakemake.wildcards.get("planning_horizons", None)
    foresight=snakemake.params.foresight
    # Prepare network (settings before solving)
    prepare_network(
        n,
        solve_opts=snakemake.params.solving["options"],
        foresight=snakemake.params.foresight,
        planning_horizons=planning_horizons,
        co2_sequestration_potential=snakemake.params["co2_sequestration_potential"],
        limit_max_growth=snakemake.params.get("sector", {}).get("limit_max_growth"),
    )
    if foresight == "overnight":
        add_adjust_caps(n)
    # Determine solve mode
    rolling_horizon = cf_solving.get("rolling_horizon", False)
    skip_iterations = cf_solving.get("skip_iterations", False)

    if not n.lines.s_nom_extendable.any():
        skip_iterations = True
        logger.info("No expandable lines found. Skipping iterative solving.")

    logging_frequency = snakemake.config.get("solving", {}).get(
        "mem_logging_frequency", 30
    )

    # Solve network based on mode
    with memory_logger(
        filename=getattr(snakemake.log, "memory", None), interval=logging_frequency
    ) as mem:
        if rolling_horizon and snakemake.rule == "solve_operations_network":
            logger.info("Using rolling horizon optimization...")
            all_kwargs, _ = collect_kwargs(
                snakemake.config,
                snakemake.params.solving,
                planning_horizons,
                log_fn=snakemake.log.solver,
                mode="rolling_horizon",
            )

            n.config = snakemake.config
            n.params = snakemake.params
            all_kwargs["extra_functionality"] = partial(
                extra_functionality, planning_horizons=planning_horizons
            )
            n.optimize.optimize_with_rolling_horizon(**all_kwargs)
            status, condition = "", ""

        elif skip_iterations:
            logger.info("Using single-pass optimization...")
            model_kwargs, solve_kwargs = collect_kwargs(
                snakemake.config,
                snakemake.params.solving,
                planning_horizons,
                log_fn=snakemake.log.solver,
                mode="single",
            )
            create_optimization_model(
                n,
                config=snakemake.config,
                params=snakemake.params,
                model_kwargs=model_kwargs,
                solve_kwargs=solve_kwargs,
                planning_horizons=planning_horizons,
            )

            logger.info("Solving model...")
            status, condition = n.optimize.solve_model(**solve_kwargs)

        else:
            logger.info("Using iterative transmission expansion optimization...")

            all_kwargs, _ = collect_kwargs(
                snakemake.config,
                snakemake.params.solving,
                planning_horizons,
                log_fn=snakemake.log.solver,
                mode="iterative",
            )

            n.config = snakemake.config
            n.params = snakemake.params
            all_kwargs["extra_functionality"] = partial(
                extra_functionality, planning_horizons=planning_horizons
            )
            status, condition = n.optimize.optimize_transmission_expansion_iteratively(
                **all_kwargs
            )

    logger.info(f"Maximum memory usage: {mem.mem_usage}")

    # Check results
    if not rolling_horizon:
        if status != "ok":
            logger.warning(
                f"Solving status '{status}' with termination condition '{condition}'"
            )
        check_objective_value(n, snakemake.params.solving)

    if condition == "infeasible_or_unbounded":
        # Substring "infeasible" used to send a 31 M-row 1h model into IIS
        # for hours (2026-09-02 job 11107735). Raise; do not diagnose here.
        raise RuntimeError(
            "Solving termination condition 'infeasible_or_unbounded' "
            f"(status '{status}'); refusing IIS on a full-year model."
        )

    if "warning" in condition:
        raise RuntimeError("Solving status 'warning'. Discarding solution.")

    if condition == "infeasible":
        labels = n.model.compute_infeasibilities()
        logger.info(f"Labels:\n{labels}")
        n.model.print_infeasibilities()
        raise RuntimeError("Solving status 'infeasible'. Infeasibilities computed.")

    if condition not in ["optimal"]:
        # e.g. Gurobi's "numerical trouble" barrier abort arrives as
        # status='warning', condition='other'. Without this guard the solve
        # exports an unoptimized network, snakemake sees the rule as done, and
        # the myopic chain brownfields an all-zero fleet into later horizons.
        #
        # 'suboptimal' is refused too. Upstream tolerates it because it is what
        # a TimeLimit hit looks like, and a time-limited point is still usable.
        # No TimeLimit is configured in this workflow, so the only way to reach
        # 'suboptimal' here is a barrier that stalled on numerics -- on
        # 2026-08-29 the 2025 solve stopped 3.4 % above its own dual bound and
        # the chain quietly carried that fleet into 2030.
        raise RuntimeError(
            f"Solving termination condition '{condition}' (status '{status}'); "
            "refusing to export a network without a certified solution."
        )

    n.meta = dict(snakemake.config, **dict(wildcards=dict(snakemake.wildcards)))
    n.export_to_netcdf(snakemake.output.network)

    if snakemake.output.get("model"):
        n.model.to_netcdf(snakemake.output.model)

    with open(snakemake.output.config, "w") as file:
        yaml.dump(
            n.meta,
            file,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
