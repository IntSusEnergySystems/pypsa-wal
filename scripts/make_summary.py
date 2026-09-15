# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Create summary CSV files for all scenario runs including costs, capacities,
capacity factors, curtailment, energy balances, prices and other metrics.
"""

import logging

import pandas as pd
import pypsa

from scripts._helpers import configure_logging, set_scenario_config

idx = pd.IndexSlice
logger = logging.getLogger(__name__)

OUTPUTS = [
    "costs",
    "capacities",
    "energy",
    "energy_balance",
    "capacity_factors",
    "metrics",
    "curtailment",
    "prices",
    "weighted_prices",
    "market_values",
    "nodal_costs",
    "nodal_capacities",
    "nodal_energy_balance",
    "nodal_capacity_factors",
]


def assign_carriers(n: pypsa.Network) -> None:
    if "carrier" not in n.lines:
        n.lines["carrier"] = "AC"


def assign_locations(n: pypsa.Network) -> None:
    for c in n.components[n.one_port_components]:
        if c.static.empty:
            continue
        c.static["location"] = c.static.bus.map(n.buses.location)

    for c in n.components[n.branch_components]:
        if c.static.empty:
            continue
        c_bus_cols = c.static.filter(regex="^bus")
        locs = c_bus_cols.apply(lambda c: c.map(n.buses.location)).sort_index(axis=1)
        # Use first location that is not "EU"; take "EU" if nothing else available
        c.static["location"] = locs.apply(
            lambda row: next(
                (loc for loc in row.dropna() if loc != "EU"),
                "EU",
            ),
            axis=1,
        )


#: Bus ``location`` values that are not a real region. ``assign_locations``
#: spells the absence of one as ``"EU"``; the sharing rule below agrees with it.
NO_LOCATION = frozenset({"", "EU", "nan", "None"})


def endpoint_locations(n: pypsa.Network, c: str) -> pd.Series:
    """Per element of component ``c``, the real regions its buses touch.

    A Series of tuples, in bus-column order and de-duplicated. ``("EU",)`` when
    every bus is EU-level, which is how :func:`assign_locations` spells "no
    region" — so a Link on an EU carrier bus keeps the behaviour that function
    already gives it.
    """
    static = n.c[c].static
    bus_cols = sorted(static.filter(regex=r"^bus\d*$").columns)
    if not bus_cols or static.empty:
        return pd.Series([("EU",)] * len(static), index=static.index, dtype=object)

    locs = static[bus_cols].apply(lambda col: col.map(n.buses.location))

    def distinct(row) -> tuple:
        seen = []
        for value in row:
            if isinstance(value, str) and value not in NO_LOCATION and value not in seen:
                seen.append(value)
        return tuple(seen) or ("EU",)

    return locs.apply(distinct, axis=1)


def share_across_endpoints(n: pypsa.Network, per_element: pd.Series) -> pd.Series:
    """Regionalise a per-element statistic, splitting shared assets equally.

    ``assign_locations`` gives a branch a *single* location — its first non-EU
    bus, which for every AC line, HVDC link and cross-border pipeline is
    ``bus0``. An interconnector was therefore charged in full to one of the two
    regions it connects, and which one is decided by the bus order the base
    network happens to carry: for all 11 AC lines of the Walloon model that is
    simply the alphabetically earlier region code, so Wallonia paid for its
    links to ``FR`` and ``LU`` and nothing for its links to ``BEBRU`` and
    ``BEVLG``. Rename a neighbour's code and the bill moves, with the optimum
    untouched.

    Here an asset spanning several regions is split equally between them, so a
    regional figure reads "this region's share of the assets it is connected by"
    rather than "the assets whose code sorts first". Two things are deliberately
    *not* changed: an asset wholly inside one region (the distribution grid,
    every conversion Link) is untouched, and so is a Link whose other ports are
    EU-level carrier buses — nuclear on ``EU uranium``, oil boilers on
    ``EU oil`` — which keeps the attribution §16b established.

    Region sums still reproduce the system total: this redistributes, it does
    not rescale. Pass a statistic computed with ``groupby=False`` so that the
    per-element values carry pypsa's own definition of capex/opex/capacity.

    See docs/logs/2026-09-13_cabinet_batch_all14_2010_1h.md §16d.
    """
    frames = []
    for component in per_element.index.get_level_values("component").unique():
        values = per_element.xs(component, level="component")
        static = n.c[component].static
        frame = pd.DataFrame(
            {
                "value": values,
                "location": endpoint_locations(n, component).reindex(values.index),
                "carrier": static["carrier"].reindex(values.index).astype(str),
            }
        )
        frame["value"] /= frame["location"].map(len)
        frame = frame.explode("location")
        frame["component"] = component
        frames.append(frame)

    if not frames:
        return pd.Series(dtype=float, name="value")
    out = pd.concat(frames, ignore_index=True)
    return out.groupby(["component", "location", "carrier"])["value"].sum()


def assigned_location(n: pypsa.Network, c: str, port: str = "") -> pd.Series:
    """Grouper returning the location `assign_locations` put on the component.

    Use this instead of the string ``"location"`` for anything that belongs to a
    *component* rather than to one of its ports — cost and capacity above all.

    PyPSA's built-in ``location`` grouper (``pypsa.statistics.grouping.Groupers``)
    is a registered method, so it takes precedence over a column of the same name
    and re-derives the location as ``bus{port} -> n.buses.location``. For a branch
    component that is ``bus0``, and for every Link whose input is an EU-level
    carrier bus that is ``"EU"``. The whole of :func:`assign_locations` — which
    deliberately picks the first *non-EU* bus — was therefore discarded, and the
    capital cost and capacity of Walloon nuclear (``bus0 = "EU uranium"``) were
    reported at ``EU`` instead of ``BEWAL``. Measured on the September 2026 batch,
    ``scen_central`` 2050: 2 017 MEUR/a of capex and 3 000 MW_e, i.e. a quarter of
    the Walloon annual cost, missing from every per-node chart. Oil boilers
    (``bus0 = "EU oil"``) were hit the same way at 2025-2040.

    **Not for energy balances.** There the port matters and the built-in grouper is
    right: a nuclear Link withdraws uranium at ``EU`` and injects electricity at
    ``BEWAL``, and both rows are wanted. `calculate_nodal_energy_balance` keeps the
    string grouper for exactly that reason.

    See docs/logs/2026-09-13_cabinet_batch_all14_2010_1h.md §16b.
    """
    return n.c[c].static["location"].rename("location")


def calculate_nodal_capacity_factors(n: pypsa.Network) -> pd.Series:
    """
    Calculate the regional dispatched capacity factors / utilisation rates for each technology carrier based on location bus attribute.
    """
    comps = n.one_port_components ^ {"Store"} | n.passive_branch_components
    return n.statistics.capacity_factor(
        comps=comps, groupby=[assigned_location, "carrier"]
    )


def calculate_capacity_factors(n: pypsa.Network) -> pd.Series:
    """
    Calculate the average dispatched capacity factors / utilisation rates for each technology carrier.

    Returns
    -------
    pd.Series
        MultiIndex Series with levels ["component", "carrier"]
    """

    comps = n.one_port_components ^ {"Store"} | n.passive_branch_components
    return n.statistics.capacity_factor(comps=comps).sort_index()


def calculate_nodal_costs(n: pypsa.Network) -> pd.Series:
    """
    Calculate optimized regional costs for each technology split by marginal and capital costs and based on location bus attribute.

    Returns
    -------
    pd.Series
        MultiIndex Series with levels ["cost", "component", "location", "carrier"]

    An asset that spans two regions — an AC line, an HVDC link, a cross-border
    pipeline — has its cost split equally between them rather than booked to
    whichever end happens to be ``bus0``; see :func:`share_across_endpoints`.
    """
    costs = pd.concat(
        {
            "capital": share_across_endpoints(n, n.statistics.capex(groupby=False)),
            "marginal": share_across_endpoints(n, n.statistics.opex(groupby=False)),
        }
    )
    costs.index.names = ["cost", "component", "location", "carrier"]

    return costs


def calculate_costs(n: pypsa.Network) -> pd.Series:
    """
    Calculate optimized total costs for each technology split by marginal and capital costs.

    Returns
    -------
    pd.Series
        MultiIndex Series with levels ["cost", "component", "carrier"]
    """
    costs = pd.concat(
        {
            "capital": n.statistics.capex(),
            "marginal": n.statistics.opex(),
        }
    )
    costs.index.names = ["cost", "component", "carrier"]

    return costs


def calculate_nodal_capacities(n: pypsa.Network) -> pd.Series:
    """
    Calculate optimized regional capacities for each technology relative to bus/bus0 based on location bus attribute.

    Returns
    -------
    pd.Series
        MultiIndex Series with levels ["component", "location", "carrier"]

    Shared assets are split between the regions they connect, on the same rule
    as the costs, so that the capacity chart and the cost chart describe the
    same half-of-an-interconnector; see :func:`share_across_endpoints`.
    """
    capacities = share_across_endpoints(n, n.statistics.optimal_capacity(groupby=False))
    capacities.index.names = ["component", "location", "carrier"]

    return capacities


def calculate_capacities(n: pypsa.Network) -> pd.Series:
    """
    Calculate optimized total capacities for each technology relative to bus/bus0.

    Returns
    -------
    pd.Series
        MultiIndex Series with levels ["component", "carrier"]
    """
    return n.statistics.optimal_capacity()


def calculate_curtailment(n: pypsa.Network) -> pd.Series:
    """
    Calculate the curtailment of electricity generation technologies in percent.
    """

    carriers = ["AC", "low voltage"]

    duration = n.snapshot_weightings.generators.sum()

    curtailed_abs = n.statistics.curtailment(
        bus_carrier=carriers, aggregate_across_components=True
    )
    available = (
        n.statistics.optimal_capacity("Generator", bus_carrier=carriers) * duration
    )

    curtailed_rel = curtailed_abs / available * 100

    return curtailed_rel.sort_index()


def calculate_energy(n: pypsa.Network) -> pd.Series:
    """
    Calculate the net energy supply (positive) and consumption (negative) by technology carrier across all ports.

    Returns
    -------
    pd.Series
        MultiIndex Series with levels ["component", "carrier"]
    """
    return n.statistics.energy_balance(groupby="carrier").sort_values(ascending=False)


def calculate_energy_balance(n: pypsa.Network) -> pd.Series:
    """
    Calculate the energy supply (positive) and consumption (negative) by technology carrier for each bus carrier.

    Returns
    -------
    pd.Series
        MultiIndex Series with levels ["component", "carrier", "bus_carrier"]

    Examples
    --------
    >>> eb = calculate_energy_balance(n)
    >>> eb.xs("methanol", level='bus_carrier')
    """
    return n.statistics.energy_balance().sort_values(ascending=False)


def calculate_nodal_energy_balance(n: pypsa.Network) -> pd.Series:
    """
    Calculate the regional energy balances (positive values for supply, negative values for consumption) for each technology carrier and bus carrier based on the location bus attribute.

    Returns
    -------
    pd.Series
        MultiIndex Series with levels ["component", "carrier", "location", "bus_carrier"]

    Examples
    --------
    >>> eb = calculate_nodal_energy_balance(n)
    >>> eb.xs(("AC", "BE0 0"), level=["bus_carrier", "location"])
    """
    return n.statistics.energy_balance(groupby=["carrier", "location", "bus_carrier"])


def calculate_metrics(n: pypsa.Network) -> pd.Series:
    """
    Calculate system-level metrics, e.g. shadow prices, grid expansion, total costs.
    Also calculate average, standard deviation and share of zero hours for electricity prices.
    """

    metrics = {}

    dc_links = n.links.query("carrier == 'DC'")
    metrics["line_volume_DC"] = dc_links.eval("length * p_nom_opt").sum()
    metrics["line_volume_AC"] = n.lines.eval("length * s_nom_opt").sum()
    metrics["line_volume"] = metrics["line_volume_AC"] + metrics["line_volume_DC"]

    metrics["total costs"] = n.statistics.capex().sum() + n.statistics.opex().sum()

    buses_i = n.buses.query("carrier == 'AC'").index
    prices = n.buses_t.marginal_price[buses_i]

    # threshold higher than marginal_cost of VRE
    zero_hours = prices.where(prices < 0.1).count().sum()
    metrics["electricity_price_zero_hours"] = zero_hours / prices.size
    metrics["electricity_price_mean"] = prices.unstack().mean()
    metrics["electricity_price_std"] = prices.unstack().std()

    if "lv_limit" in n.global_constraints.index:
        metrics["line_volume_limit"] = n.global_constraints.at["lv_limit", "constant"]
        metrics["line_volume_shadow"] = n.global_constraints.at["lv_limit", "mu"]

    if "CO2Limit" in n.global_constraints.index:
        metrics["co2_shadow"] = n.global_constraints.at["CO2Limit", "mu"]

    if "co2_sequestration_limit" in n.global_constraints.index:
        metrics["co2_storage_shadow"] = n.global_constraints.at[
            "co2_sequestration_limit", "mu"
        ]

    return pd.Series(metrics).sort_index()


def calculate_prices(n: pypsa.Network) -> pd.Series:
    """
    Calculate time-averaged prices per carrier.
    """
    return n.buses_t.marginal_price.mean().groupby(n.buses.carrier).mean().sort_index()


def calculate_weighted_prices(n: pypsa.Network) -> pd.Series:
    """
    Calculate load-weighted prices per bus carrier.
    """
    carriers = n.buses.carrier.unique()

    weighted_prices = {}

    for carrier in carriers:
        load = n.statistics.withdrawal(
            groupby="bus",
            aggregate_time=False,
            bus_carrier=carrier,
            aggregate_across_components=True,
        ).T

        if not load.empty and load.sum().sum() > 0:
            price = n.buses_t.marginal_price.loc[:, n.buses.carrier == carrier]
            price = price.reindex(columns=load.columns, fill_value=1)

            weights = n.snapshot_weightings.generators
            a = weights @ (load * price).sum(axis=1)
            b = weights @ load.sum(axis=1)
            weighted_prices[carrier] = a / b

    return pd.Series(weighted_prices).sort_index()


def calculate_market_values(n: pypsa.Network) -> pd.Series:
    """
    Calculate market values for electricity.
    """
    return (
        n.statistics.market_value(bus_carrier="AC", aggregate_across_components=True)
        .sort_values()
        .dropna()
    )


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "make_summary",
            clusters="5",
            opts="",
            sector_opts="",
            planning_horizons="2030",
            configfiles="config/test/config.overnight.yaml",
        )

    configure_logging(snakemake)
    set_scenario_config(snakemake)

    n = pypsa.Network(snakemake.input.network)
    assign_carriers(n)
    assign_locations(n)

    pypsa.set_option("params.statistics.nice_names", False)
    pypsa.set_option("params.statistics.drop_zero", False)

    for output in OUTPUTS:
        globals()["calculate_" + output](n).to_csv(snakemake.output[output])
