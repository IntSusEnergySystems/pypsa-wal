# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""The CO2StoP ceiling binds the standing fleet, not one myopic vintage.

Lever A of ``docs/co2-sequestration.md`` §5.2: ``prepare_sector_network``
writes the annualised CO2StoP ceiling on the ``co2 sequestered`` Store it
builds for *this* horizon, and ``add_brownfield`` then carries the earlier
horizons' Stores onto the same bus. Measured on the solved networks, DE
reached 130.1 Mt/a installed in 2040 and 209.2 Mt/a in 2050 against a 79.1
Mt/a ceiling (NL 3.00x, GB 1.46x). Nothing caught it: the pooled
``co2_sequestration_limit`` backstop is 1 000 Mt from 2035 on purpose.
"""

from __future__ import annotations

import numpy as np
import pypsa
import pytest

from scripts.walloon_scripts.sequestration_bounds import (
    apply_sequestration_fleet_cap,
    sequestration_fleet_ceiling,
)

# Annualised CO2StoP ceilings actually in the tree, in tonnes per year.
DE_CEILING = 79.1e6
NL_CEILING = 9.1e6


def _network(vintages: dict[str, list[tuple[str, float, bool]]]) -> pypsa.Network:
    """One CO₂ node per key; each entry is (suffix, e_nom or e_nom_max, extendable)."""
    n = pypsa.Network()
    n.add("Carrier", "co2 sequestered")
    for node, stores in vintages.items():
        bus = f"{node} co2 sequestered"
        n.add("Bus", bus, carrier="co2 sequestered", location=node)
        for suffix, value, extendable in stores:
            n.add(
                "Store",
                f"{bus}{suffix}",
                bus=bus,
                carrier="co2 sequestered",
                e_nom_extendable=extendable,
                e_nom=0.0 if extendable else value,
                e_nom_max=value if extendable else value,
            )
    return n


def test_ceiling_is_read_from_the_extendable_vintage():
    n = _network(
        {
            "DE0 0": [
                ("-2030", 51.0e6, False),
                ("-2040", DE_CEILING, True),
            ]
        }
    )
    ceiling = sequestration_fleet_ceiling(n)
    assert ceiling["DE0 0"] == pytest.approx(DE_CEILING)


def test_inherited_vintages_are_subtracted_from_this_horizons_headroom():
    """The 2040 bug, in miniature: 51 Mt/a standing must leave 28.1, not 79.1."""
    n = _network(
        {
            "DE0 0": [
                ("-2030", 51.0e6, False),
                ("-2040", DE_CEILING, True),
            ]
        }
    )
    apply_sequestration_fleet_cap(n)
    new = n.stores.at["DE0 0 co2 sequestered-2040", "e_nom_max"]
    assert new == pytest.approx(DE_CEILING - 51.0e6)
    fleet = (
        n.stores.at["DE0 0 co2 sequestered-2030", "e_nom"]
        + n.stores.at["DE0 0 co2 sequestered-2040", "e_nom_max"]
    )
    assert fleet == pytest.approx(DE_CEILING)


def test_a_saturated_reservoir_leaves_no_headroom_rather_than_negative():
    n = _network(
        {
            "NL0 0": [
                ("-2030", 9.1e6, False),
                ("-2040", 9.1e6, False),
                ("-2050", NL_CEILING, True),
            ]
        }
    )
    apply_sequestration_fleet_cap(n)
    assert n.stores.at["NL0 0 co2 sequestered-2050", "e_nom_max"] == 0.0


def test_a_crumb_of_headroom_is_snapped_to_exactly_zero():
    """An inherited vintage that fills the reservoir must leave 0, not 7e-4 t.

    Floating point makes `ceiling - inherited` a tiny positive number, and a
    tiny *finite upper bound* on a variable is the numerical pathology lever B
    exists to remove: NL landed at 7.337e-04 t against a 9.09 Mt/a ceiling on
    2026-09-22 and carried the 2040/2050 bound spread to 1.36e12, against a
    gate of ~1e9.
    """
    n = _network(
        {
            "NL0 0": [
                ("-2030", NL_CEILING - 7.336978e-04, False),
                ("-2040", NL_CEILING, True),
            ]
        }
    )
    apply_sequestration_fleet_cap(n)
    assert n.stores.at["NL0 0 co2 sequestered-2040", "e_nom_max"] == 0.0


def test_real_headroom_is_not_snapped():
    """The epsilon is one millionth of the reservoir, not a blanket rounding."""
    keep = NL_CEILING * 1e-4  # 100x the epsilon
    n = _network(
        {
            "NL0 0": [
                ("-2030", NL_CEILING - keep, False),
                ("-2040", NL_CEILING, True),
            ]
        }
    )
    apply_sequestration_fleet_cap(n)
    assert n.stores.at["NL0 0 co2 sequestered-2040", "e_nom_max"] == pytest.approx(
        keep, rel=1e-6
    )


def test_base_year_is_untouched():
    """No inherited vintage: the ceiling prepare_sector_network wrote stands."""
    n = _network({"DE0 0": [("-2025", DE_CEILING, True)]})
    apply_sequestration_fleet_cap(n)
    assert n.stores.at["DE0 0 co2 sequestered-2025", "e_nom_max"] == pytest.approx(
        DE_CEILING
    )


def test_unbounded_nodes_are_left_alone():
    """`regional_co2_sequestration_potential: false` means no ceiling to apply."""
    n = _network(
        {
            "DE0 0": [
                ("-2030", 51.0e6, False),
                ("-2040", np.inf, True),
            ]
        }
    )
    apply_sequestration_fleet_cap(n)
    assert not np.isfinite(n.stores.at["DE0 0 co2 sequestered-2040", "e_nom_max"])


def test_each_node_is_capped_on_its_own_reservoir():
    n = _network(
        {
            "DE0 0": [("-2030", 51.0e6, False), ("-2040", DE_CEILING, True)],
            "NL0 0": [("-2030", 2.0e6, False), ("-2040", NL_CEILING, True)],
        }
    )
    apply_sequestration_fleet_cap(n)
    assert n.stores.at["DE0 0 co2 sequestered-2040", "e_nom_max"] == pytest.approx(
        DE_CEILING - 51.0e6
    )
    assert n.stores.at["NL0 0 co2 sequestered-2040", "e_nom_max"] == pytest.approx(
        NL_CEILING - 2.0e6
    )


def test_runs_before_the_belgian_override_in_add_brownfield():
    """Order matters: `update_BEWAL_potentials` writes the documented 0 last.

    Belgian nodes have no CO2StoP site, so their ceiling is the
    ``custom_potentials.csv`` override, applied with its own fleet arithmetic
    by ``apply_co2_store_cap``. If the generic cap ran after it, it would read
    the already-netted residual as the ceiling and net it twice.
    """
    import inspect

    import scripts.add_brownfield as ab

    src = inspect.getsource(ab)
    generic = src.index("apply_sequestration_fleet_cap(n)")
    belgian = src.index("update_BEWAL_potentials(\n        n=n,")
    assert generic < belgian
