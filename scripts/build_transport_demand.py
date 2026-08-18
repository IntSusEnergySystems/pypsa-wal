# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Build land transport demand per clustered model region including efficiency
improvements due to drivetrain changes, time series for electric vehicle
availability and demand-side management constraints.
"""

import logging

import numpy as np
import pandas as pd
import pypsa
import xarray as xr

from scripts._helpers import (
    configure_logging,
    generate_periodic_profiles,
    get,
    get_snapshots,
    set_scenario_config,
)

logger = logging.getLogger(__name__)


def build_nodal_transport_data(fn, pop_layout, year):
    # get numbers of car and fuel efficiency per country
    transport_data = pd.read_csv(fn, index_col=[0, 1])
    transport_data = transport_data.xs(year, level="year")

    # break number of cars down to nodal level based on population density
    nodal_transport_data = transport_data.loc[pop_layout.ct].fillna(0.0)
    nodal_transport_data.index = pop_layout.index
    nodal_transport_data["number cars"] = (
        pop_layout["fraction"] * nodal_transport_data["number cars"]
    )
    # fill missing fuel efficiency with average data
    nodal_transport_data.loc[
        nodal_transport_data["average fuel efficiency"] == 0.0,
        "average fuel efficiency",
    ] = transport_data["average fuel efficiency"].mean()

    return nodal_transport_data


def build_transport_demand(traffic_fn, airtemp_fn, nodes, nodal_transport_data):
    """
    Returns transport demand per bus in unit km driven [100 km].
    """
    # averaged weekly counts from the year 2010-2015
    traffic = pd.read_csv(traffic_fn, skiprows=2, usecols=["count"]).squeeze("columns")

    # create annual profile take account time zone + summer time
    transport_shape = generate_periodic_profiles(
        dt_index=snapshots,
        nodes=nodes,
        weekly_profile=traffic.values,
    )
    transport_shape = transport_shape / transport_shape.sum()
    
    if not suff_demand:
      # get heating demand for correction to demand time series
      temperature = xr.open_dataarray(airtemp_fn).to_pandas()

      # correction factors for vehicle heating
      dd_ICE = transport_degree_factor(
        temperature,
        options["transport_heating_deadband_lower"],
        options["transport_heating_deadband_upper"],
        options["ICE_lower_degree_factor"],
        options["ICE_upper_degree_factor"],
    )

      # divide out the heating/cooling demand from ICE totals
      ice_correction = (transport_shape * (1 + dd_ICE)).sum() / transport_shape.sum()

    if times_demand:
        wallon_node = config["run"]["wallon_node"]
        # unit TWh
        energy_totals_transport = (
        pop_weighted_energy_totals["total road"]
        + pop_weighted_energy_totals["total rail"].where(pop_weighted_energy_totals.index != wallon_node, 0)
        - pop_weighted_energy_totals["electricity rail"].where(pop_weighted_energy_totals.index != wallon_node, 0)
        )
        # average fuel efficiency in MWh/100 km
        eff = nodal_transport_data["average fuel efficiency"]
        transport = (transport_shape.multiply(energy_totals_transport) * 1e6 * nyears)
        other_nodes = transport.columns.drop(wallon_node, errors='ignore')
        eff = eff[other_nodes]
        transport[other_nodes] = transport[other_nodes].divide(
        eff * ice_correction[other_nodes]
        )
    elif suff_demand:
        energy_totals_transport = (
            pop_weighted_energy_totals["total road"]
        )
        transport = (
            (transport_shape.multiply(energy_totals_transport) * 1e6 * nyears)
        )
    else:
        energy_totals_transport = (
        pop_weighted_energy_totals["total road"]
        + pop_weighted_energy_totals["total rail"]
        - pop_weighted_energy_totals["electricity rail"]
        )
        # average fuel efficiency in MWh/100 km
        eff = nodal_transport_data["average fuel efficiency"]
        transport = (transport_shape.multiply(energy_totals_transport) * 1e6 * nyears)
        transport = transport.divide(
        eff * ice_correction
        )
    return transport


def transport_degree_factor(
    temperature,
    deadband_lower=15,
    deadband_upper=20,
    lower_degree_factor=0.5,
    upper_degree_factor=1.6,
):
    """
    Work out how much energy demand in vehicles increases due to heating and
    cooling.

    There is a deadband where there is no increase. Degree factors are %
    increase in demand compared to no heating/cooling fuel consumption.
    Returns per unit increase in demand for each place and time
    """

    dd = temperature.copy()

    dd[(temperature > deadband_lower) & (temperature < deadband_upper)] = 0.0

    dT_lower = deadband_lower - temperature[temperature < deadband_lower]
    dd[temperature < deadband_lower] = lower_degree_factor / 100 * dT_lower

    dT_upper = temperature[temperature > deadband_upper] - deadband_upper
    dd[temperature > deadband_upper] = upper_degree_factor / 100 * dT_upper

    return dd


def bev_availability_profile(fn, snapshots, nodes, options, investment_year):
    """
    Derive plugged-in availability for passenger electric vehicles.
    """
    # car count in typical week
    traffic = pd.read_csv(fn, skiprows=2, usecols=["count"]).squeeze("columns")
    # maximum share plugged-in availability for passenger electric vehicles
    avail_max = get(options["bev_avail_max"], investment_year)
    # average share plugged-in availability for passenger electric vehicles
    avail_mean = get(options["bev_avail_mean"], investment_year)
    # minimum share plugged-in availability for passenger electric vehicles
    avail_min = get(options["bev_avail_min"], investment_year)

    if avail_min < 0:
        logger.warning(
            "Minimum BEV availability is negative, which may lead to infeasibility."
        )
    if avail_max < avail_min:
        logger.warning(
            "Maximum BEV availability is lower than minimum, which may "
            "lead to infeasibility."
        )

    # linear scaling, highest when traffic is lowest, decreases if traffic increases
    avail = avail_max - (avail_max - avail_mean) * (traffic - traffic.min()) / (
        traffic.mean() - traffic.min()
    )

    # floor to avail_min so the profile never drops low enough to cause infeasibility
    avail = avail.clip(lower=avail_min)

    return generate_periodic_profiles(
        dt_index=snapshots,
        nodes=nodes,
        weekly_profile=avail.values,
    )


def bev_dsm_profile(snapshots, nodes, options):
    dsm_week = np.zeros((24 * 7,))

    # assuming that at a certain time ("bev_dsm_restriction_time") EVs have to
    # be charged to a minimum value (defined in bev_dsm_restriction_value)
    dsm_week[(np.arange(0, 7, 1) * 24 + options["bev_dsm_restriction_time"])] = options[
        "bev_dsm_restriction_value"
    ]

    return generate_periodic_profiles(
        dt_index=snapshots,
        nodes=nodes,
        weekly_profile=dsm_week,
    )


def build_natural_charging_shape(fn, snapshots, nodes, investment_year):
    """
    Build a normalized weekly charging shape from Elia's observed hourly
    natural (non-flexible) charging profile for the vintage closest to
    ``investment_year``.

    ``investment_year`` is the planning horizon, not the.
    Because the data CSV may contain vintages that do not match the planning horizon (e.g. 2026, 2036),
    the vintage numerically closest to ``investment_year`` is used
    (if tied, the lower vintage is used).
    """
    daily = pd.read_csv(fn)
    available_years = sorted(daily["year"].unique())
    year = min(available_years, key=lambda y: (abs(y - investment_year), y))
    daily = daily[daily["year"] == year].sort_values("hour")
    weekly_profile = np.tile(daily["natural_charging_profile"].values, 7)

    shape = generate_periodic_profiles(
        dt_index=snapshots,
        nodes=nodes,
        weekly_profile=weekly_profile,
    )
    return shape / shape.sum()


def split_transport_demand(total_transport_demand, natural_charging_shape, bev_dsm_availability):
    """
    Split transport demand into a flexible and inflexible demand.

    FLexible demand has the same temporal shape as ``transport``, scaled by ``bev_dsm_availability`` and the inflexible
    demand is reshaped to follow Elia's natural charging profile), conserving each node's total energy.

    The flexible share follows actual fuel/power consumption in the cars (i.e. driving demand),
    while the inflexible share follows actual observed charging behaviour (Elia's natural charging profile).
    """
    # to get flexible demand, multiple total transport demand by the share of flexible demand (bev_dsm_availability)
    transport_flexible = total_transport_demand * bev_dsm_availability

    # to get inflexible demand, multiply total transport demand by the share of inflexible demand (1 - bev_dsm_availability)
    # and then multiply by Elia's natural charging profile to reshape in time
    inflexible_total = total_transport_demand.sum() * (1 - bev_dsm_availability)
    transport_inflexible = natural_charging_shape.mul(inflexible_total, axis=1)

    # add check to ensure that total energy equals the sum of the split (flexible + inflexible)
    total_orig = total_transport_demand.sum().sum()
    total_split = transport_flexible.sum().sum() + transport_inflexible.sum().sum()
    assert np.isclose(total_orig, total_split, rtol=1e-6), (
        f"transport split does not match: {total_orig} vs {total_split}"
    )

    return transport_flexible, transport_inflexible


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake("build_transport_demand", clusters=128,planning_horizons="2030",)
    configure_logging(snakemake)
    set_scenario_config(snakemake)
    config = snakemake.config
    study = config["run"]["name"]
    times_demand = config.get("sector", {}).get("times_demand", False)
    suff_demand = config.get("sector", {}).get("suff_demand", False)
    pop_layout = pd.read_csv(snakemake.input.clustered_pop_layout, index_col=0)

    nodes = pop_layout.index

    pop_weighted_energy_totals = pd.read_csv(
        snakemake.input.pop_weighted_energy_totals, index_col=0
    )

    options = snakemake.params.sector
    investment_year = int(snakemake.wildcards.planning_horizons)

    snapshots = get_snapshots(
        snakemake.params.snapshots, snakemake.params.drop_leap_day, tz="UTC"
    )

    n = pypsa.Network(snakemake.input.network)
    nyears = len(snapshots) / 8760

    energy_totals_year = snakemake.params.energy_totals_year
    nodal_transport_data = build_nodal_transport_data(
        snakemake.input.transport_data, pop_layout, energy_totals_year
    )

    transport_demand = build_transport_demand(
        snakemake.input.traffic_data_KFZ,
        snakemake.input.temp_air_total,
        nodes,
        nodal_transport_data,
    )

    avail_profile = bev_availability_profile(
        snakemake.input.traffic_data_Pkw, snapshots, nodes, options, investment_year
    )

    dsm_profile = bev_dsm_profile(snapshots, nodes, options)

    natural_charging_shape = build_natural_charging_shape(
        snakemake.input.elia_natural_charging_profile, snapshots, nodes, investment_year
    )

    nodal_transport_data.to_csv(snakemake.output.transport_data)
    transport_demand.to_csv(snakemake.output.transport_demand)
    avail_profile.to_csv(snakemake.output.avail_profile)
    dsm_profile.to_csv(snakemake.output.dsm_profile)
    natural_charging_shape.to_csv(snakemake.output.natural_charging_shape)
