# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Prepare and extend default cost data with custom cost modifications. Custom costs can target all planning horizons
and / or technologies using the 'all' identifier.

Preparing the cost data includes:
- aligning all units to conventional units (i.e. MW / MWh),
- filling in missing data,
- computing 'capital_cost' parameter (annualised investment costs and FOM),
- computing 'marginal_cost' parameter (fuel costs and VOM),
- computing storage costs for batteries and hydrogen,
- (deprecated) overwriting attributes using config-based modifications.

Inputs
------

- ``resources/costs_{planning_horizons}.csv``: Default cost data for specified planning horizon
- (by default) ``data/custom_costs.csv``: Custom cost modifications (can be configured with `costs:custom_costs:file`

Outputs
-------

- ``resources/costs_{planning_horizons}_processed.csv``: Prepared cost data with custom modifications applied
"""

import logging
import warnings

import pandas as pd
import pypsa

from scripts.add_electricity import STORE_LOOKUP, calculate_annuity

logger = logging.getLogger(__name__)


def overwrite_costs(costs: pd.DataFrame, custom_costs: pd.DataFrame) -> pd.DataFrame:
    """
    Apply custom cost modifications to costs data.

    Parameters
    ----------
    costs : pd.DataFrame
        Base cost assumptions.
    custom_costs : pd.DataFrame
        Custom cost modifications.

    Returns
    -------
    pd.DataFrame
        Updated cost data with custom modifications applied (if applicable).
    """
    if custom_costs.empty:
        return costs

    all_techs = custom_costs.query("technology=='all'").dropna(axis=1, how="all")
    custom_costs = custom_costs.query("technology != 'all'").dropna(axis=1, how="all")

    # Add technologies that don't already exist
    missing_idx = custom_costs.index.difference(costs.index)
    if len(missing_idx) > 0:
        costs = pd.concat([costs, custom_costs.loc[missing_idx]])

    # Overwrite unique pairs of (technology, parameter)
    for param in custom_costs.columns:
        custom_col = custom_costs[param].dropna()
        costs.loc[custom_col.index, param] = custom_col

    # If technology "all" exists, propagate its parameter values to all other technologies
    if not all_techs.empty:
        for param in all_techs.columns:
            costs.loc[:, param] = all_techs.loc["all", param]

    return costs


#: Cost-table technologies renamed after the annuity is computed. Kept in step
#: with ``scripts/build_common_parameters.py::COST_TABLE_RENAMES``, which uses
#: it to name the generated ``discount_rates.csv`` rows
#: (``test_cost_table_renames_agree`` pins the two together).
COST_TABLE_RENAMES = {"solar-utility single-axis tracking": "solar-hsat"}


def prepare_costs(
    costs: pd.DataFrame,
    config: dict,
    max_hours: dict = None,
    nyears: float = 1.0,
    custom_costs_fn: str | None = None,
    planning_horizon: str | None = None,
    hurdle_rate_fn: str | None = None,
) -> pd.DataFrame:
    """
    Standardize and prepare extended costs data.

    Parameters
    ----------
    costs : pd.DataFrame
        DataFrame containing extended costs
    config : dict
        Dictionary containing cost-related configuration parameters
    max_hours : dict, optional
        Dictionary specifying maximum hours for storage technologies
    nyears : float, optional
        Number of years for investment, by default 1.0
    custom_costs_fn : str, optional
        Custom cost modifications file path (default None).
    planning_horizon : str, optional
        Planning horizon for filtering custom and hurdle rate rows.
    hurdle_rate_fn : str, optional
        Per-technology hurdle rate CSV path (default None).

    Returns
    -------
    costs : pd.DataFrame
        DataFrame containing the prepared cost data

    """

    def _convert_to_MW(cost_df: pd.DataFrame) -> pd.DataFrame:
        # correct units to MW and EUR
        cost_df.loc[cost_df.unit.str.contains("/kW"), "value"] *= 1e3
        cost_df.loc[cost_df.unit.str.contains("/GW"), "value"] /= 1e3

        cost_df.unit = cost_df.unit.str.replace("/kW", "/MW")
        cost_df.unit = cost_df.unit.str.replace("/GW", "/MW")
        return cost_df

    if planning_horizon is None and "snakemake" in globals():
        planning_horizon = str(snakemake.wildcards.planning_horizons)

    # Load custom costs and categorize into two sets:
    # - Raw attributes: overwritten before cost preparation
    # - Prepared attributes: overwritten after cost preparation
    custom_raw = pd.DataFrame()
    custom_prepared = pd.DataFrame()
    if custom_costs_fn is not None:
        custom_costs = pd.read_csv(
            custom_costs_fn,
            dtype={"planning_horizon": "str"},
            index_col=["technology", "parameter"],
        ).query("planning_horizon in [@planning_horizon, 'all']")

        custom_costs = _convert_to_MW(custom_costs)

        custom_costs = custom_costs.drop("planning_horizon", axis=1).value.unstack(
            level=1
        )

        prepared_attrs = ["marginal_cost", "capital_cost"]
        raw_attrs = list(set(custom_costs.columns) - set(prepared_attrs))
        custom_raw = custom_costs[raw_attrs].dropna(axis=0, how="all")
        custom_prepared = custom_costs.filter(prepared_attrs).dropna(axis=0, how="all")

    # Copy marginal_cost and capital_cost for backward compatibility
    for key in ("marginal_cost", "capital_cost"):
        if key in config:
            config["overwrites"][key] = config[key]

    costs = _convert_to_MW(costs)

    # min_count=1 is important to generate NaNs which are then filled by fillna
    costs = costs.value.unstack(level=1).groupby("technology").sum(min_count=1)

    # Process overwrites for various attributes
    costs = overwrite_costs(costs, custom_raw)
    costs = costs.fillna(config["fill_values"])
    for attr in (
        "investment",
        "lifetime",
        "FOM",
        "VOM",
        "efficiency",
        "fuel",
        "standing losses",
    ):
        overwrites = config["overwrites"].get(attr)
        if overwrites is not None:
            overwrites = pd.Series(overwrites)
            costs.loc[overwrites.index, attr] = overwrites
            warnings.warn(
                "Config-based cost overwrites is deprecated. Use external file instead (by default 'data/custom_costs.csv').",
                DeprecationWarning,
            )
            logger.info(f"Overwriting {attr} with:\n{overwrites}")

    # Per-technology hurdle rates (config/input_parameters_for_models.csv via
    # build_common_parameters.py). Authoritative: applied after the fill_values
    # fallback and before the annuity, so it wins over technology-data too.
    if hurdle_rate_fn is not None:
        hurdle = pd.read_csv(
            hurdle_rate_fn, dtype={"planning_horizon": "str"}
        ).query("planning_horizon in [@planning_horizon, 'all']")
        rates = hurdle.set_index("technology")["value"]
        # The hurdle file is generated with the technology names the cost table
        # carries *after* COST_TABLE_RENAMES, but the rename happens below,
        # after the annuity. Map back, or the renamed technology silently keeps
        # the fill_values fallback: `solar-hsat` did, at 7 % instead of the
        # 7.5 % TIMES hurdle its row asks for, i.e. ~3 % too cheap.
        rates = rates.rename(index={new: old for old, new in COST_TABLE_RENAMES.items()})
        unknown = rates.index.difference(costs.index)
        if len(unknown):
            logger.warning(
                "%s lists %d technology(ies) absent from the cost table, ignored: %s",
                hurdle_rate_fn,
                len(unknown),
                sorted(unknown),
            )
        known = rates.index.intersection(costs.index)
        costs.loc[known, "discount rate"] = rates.loc[known].astype(float)
        missing = costs.index.difference(rates.index)
        if len(missing):
            logger.warning(
                "%d technology(ies) have no hurdle rate and keep the "
                "costs.fill_values fallback %.4g: %s",
                len(missing),
                config["fill_values"]["discount rate"],
                sorted(missing),
            )

    assert costs["discount rate"].notna().all(), (
        "NaN discount rate would silently produce NaN capital_cost for: "
        f"{sorted(costs.index[costs['discount rate'].isna()])}"
    )

    annuity_factor = calculate_annuity(costs["lifetime"], costs["discount rate"])
    annuity_factor_fom = annuity_factor + costs["FOM"] / 100.0
    costs["capital_cost"] = annuity_factor_fom * costs["investment"] * nyears

    costs.loc["waste"] = costs.loc["waste CHP"]
    costs.at["waste", "CO2 intensity"] = costs.at["oil", "CO2 intensity"]

    costs.at["OCGT", "fuel"] = costs.at["gas", "fuel"]
    costs.at["CCGT", "fuel"] = costs.at["gas", "fuel"]

    costs["marginal_cost"] = costs["VOM"] + costs["fuel"] / costs["efficiency"]

    costs.at["OCGT", "CO2 intensity"] = costs.at["gas", "CO2 intensity"]
    costs.at["CCGT", "CO2 intensity"] = costs.at["gas", "CO2 intensity"]

    # `solar` is the electricity-network ground-mount carrier; it takes the
    # utility cost, so its own `investment` row is decorative and was removed
    # from custom_costs.csv on 2026-09-05.
    costs.at["solar", "capital_cost"] = costs.at["solar-utility", "capital_cost"]
    costs = costs.rename(COST_TABLE_RENAMES)

    costs = costs.rename(columns={"standing losses": "standing_losses"})

    # Calculate storage costs if max_hours is provided
    if max_hours is not None:

        def costs_for_storage(store=None, link1=None, link2=None, max_hours=1.0):
            capital_cost = 0
            if store is not None:
                capital_cost += max_hours * store["capital_cost"]
            if link1 is not None:
                capital_cost += link1["capital_cost"]
            if link2 is not None:
                capital_cost += link2["capital_cost"]
            return pd.Series(
                {
                    "capital_cost": capital_cost,
                    "marginal_cost": 0.0,
                    "CO2 intensity": 0.0,
                    "standing_losses": 0.0,
                }
            )

        costs_i = costs.index
        for k, v in max_hours.items():
            tech = STORE_LOOKUP[k]
            store = tech.get("store") if tech.get("store") in costs_i else None
            bicharger = (
                tech.get("bicharger") if tech.get("bicharger") in costs_i else None
            )
            charger = tech.get("charger") if tech.get("charger") in costs_i else None
            discharger = (
                tech.get("discharger") if tech.get("discharger") in costs_i else None
            )
            if bicharger:
                costs.loc[k] = costs_for_storage(
                    costs.loc[store],
                    costs.loc[bicharger],
                    max_hours=v,
                )
            elif store:
                costs.loc[k] = costs_for_storage(
                    costs.loc[store],
                    costs.loc[charger] if charger else None,
                    costs.loc[discharger] if discharger else None,
                    max_hours=v,
                )

    # Overwrite marginal and capital costs
    costs = overwrite_costs(costs, custom_prepared)
    for attr in ("marginal_cost", "capital_cost"):
        overwrites = config["overwrites"].get(attr)
        if overwrites is not None:
            overwrites = pd.Series(overwrites)
            idx = overwrites.index.intersection(costs.index)
            costs.loc[idx, attr] = overwrites.loc[idx]
            warnings.warn(
                "Config-based cost overwrites is deprecated. Use external file instead (by default 'data/custom_costs.csv').",
                DeprecationWarning,
            )
            logger.info(f"Overwriting {attr} with:\n{overwrites}")

    return costs


if __name__ == "__main__":
    if "snakemake" not in globals():
        from _helpers import mock_snakemake

        snakemake = mock_snakemake("process_cost_data", planning_horizons=2030)

    cost_params = snakemake.params["costs"]

    n = pypsa.Network(snakemake.input.network)
    nyears = n.snapshot_weightings.generators.sum() / 8760.0
    planning_horizon = str(snakemake.wildcards.planning_horizons)

    # Retrieve costs assumptions
    costs = pd.read_csv(snakemake.input.costs, index_col=["technology", "parameter"])

    # Prepare costs
    costs_processed = prepare_costs(
        costs,
        cost_params,
        snakemake.params.max_hours,
        nyears,
        custom_costs_fn=snakemake.input.get("custom_costs"),
        planning_horizon=planning_horizon,
        hurdle_rate_fn=snakemake.input.get("hurdle_rates"),
    )

    costs_processed.to_csv(snakemake.output[0])
