# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""
Existing capacities configuration.

See docs in https://pypsa-eur.readthedocs.io/en/latest/configuration.html#existing-capacities
"""

from pydantic import Field

from scripts.lib.validation.config._base import ConfigModel


class ExistingCapacitiesConfig(ConfigModel):
    """Configuration for `existing_capacities` settings."""

    grouping_years_power: list[int] = Field(
        default_factory=lambda: [
            1920,
            1950,
            1955,
            1960,
            1965,
            1970,
            1975,
            1980,
            1985,
            1990,
            1995,
            2000,
            2005,
            2010,
            2015,
            2020,
            2025,
            2030,
        ],
        description="Intervals to group existing capacities for power.",
    )
    grouping_years_heat: list[int] = Field(
        default_factory=lambda: [
            1980,
            1985,
            1990,
            1995,
            2000,
            2005,
            2010,
            2015,
            2019,
        ],
        description="Intervals to group existing capacities for heat.",
    )
    threshold_capacity: float = Field(
        10,
        description="Capacities (MW) of generators and links below threshold are removed during add_existing_capacities.",
    )
    default_heating_lifetime: int = Field(
        20,
        description="Default lifetime for heating technologies (years).",
    )
    heat_stock_age_profile: dict[str, dict[int, float]] | None = Field(
        None,
        description="Optional per-technology age distribution of the inherited heating stock, `{cost technology substring: {grouping year: share}}`. Without it every technology is spread over the live `grouping_years_heat` assuming installation was linear in the past. That over-ages a fleet that grew recently: a heat pump whose technology-data lifetime is shorter than `default_heating_lifetime` then loses its oldest tranche between two planning horizons, so the reported capacity falls while the delivered heat rises. Shares are reindexed on the live grouping years and renormalised.",
    )
    conventional_carriers: list[str] = Field(
        default_factory=lambda: ["lignite", "coal", "oil", "uranium"],
        description="List of conventional power plants to include in the sectoral network.",
    )
