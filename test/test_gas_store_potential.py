# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Wallonia has no underground gas store, so the PyPSA one must be pinned to 0.

``prepare_sector_network.add_carrier_buses`` gives every gas bus an extendable
``Store`` with ``e_nom_max = inf``; ``add_gas_network`` then writes ``e_nom_min``
from ``gas_input_nodes["storage"]``, which is 0 at BEWAL. The result is an
unbounded endogenous store on a node whose only two sites (Anderlues,
Péronnes-lez-Binche) closed on 1 November 2012 — the 26 Aug run built
130–203 GWh of it. See ``docs/temporary_improvement_plans.md`` item 1.

Flanders must keep Loenhout, so the cap has to be per-bus, not per-carrier.
"""

from __future__ import annotations

from pathlib import Path

import pypsa
import pytest

from scripts.walloon_scripts.BEWAL_potentials import (
    apply_gas_store_cap,
    update_BEWAL_potentials,
)

ROW = (
    "bus,technology,parameter,value,unit,year,source,further_description,year_currency\n"
    "BEWAL,gas storage,e_nom_max,0,MWh,2050,,,\n"
)


def _gas_network(wal_e_nom_min: float = 0.0) -> pypsa.Network:
    """Two gas buses, each with the unbounded extendable Store PyPSA-Eur builds."""
    n = pypsa.Network()
    n.add("Carrier", "gas")
    for bus, e_nom_min in (("BEWAL", wal_e_nom_min), ("BEVLG", 545_280.0)):
        n.add("Bus", f"{bus} gas", carrier="gas", location=bus)
        n.add(
            "Store",
            f"{bus} gas Store",
            bus=f"{bus} gas",
            carrier="gas",
            e_nom_extendable=True,
            e_nom_min=e_nom_min,
            e_nom_max=float("inf"),
            e_cyclic=True,
            lifetime=float("inf"),
        )
    return n


def test_cap_zeroes_wallonia_and_leaves_loenhout_alone(tmp_path: Path):
    csv = tmp_path / "custom_potentials.csv"
    csv.write_text(ROW)
    n = _gas_network()

    update_BEWAL_potentials(n, 2050, walloon_potentials=str(csv))

    assert n.stores.at["BEWAL gas Store", "e_nom_max"] == 0.0
    assert n.stores.at["BEVLG gas Store", "e_nom_max"] == float("inf")
    assert n.stores.at["BEVLG gas Store", "e_nom_min"] == pytest.approx(545_280.0)


def test_cap_only_applies_to_the_requested_horizon(tmp_path: Path):
    csv = tmp_path / "custom_potentials.csv"
    csv.write_text(ROW)
    n = _gas_network()

    update_BEWAL_potentials(n, 2040, walloon_potentials=str(csv))

    assert n.stores.at["BEWAL gas Store", "e_nom_max"] == float("inf")


def test_ceiling_pulls_down_an_inherited_floor():
    """`e_nom_min > e_nom_max` is an infeasible LP, not a silently ignored cap."""
    n = _gas_network(wal_e_nom_min=130_000.0)

    apply_gas_store_cap(n, "BEWAL", "e_nom_max", 0.0)

    assert n.stores.at["BEWAL gas Store", "e_nom_min"] == 0.0
    assert n.stores.at["BEWAL gas Store", "e_nom"] == 0.0
    assert (
        n.stores.at["BEWAL gas Store", "e_nom_min"]
        <= n.stores.at["BEWAL gas Store", "e_nom_max"]
    )


def test_missing_store_warns_instead_of_raising(caplog):
    n = _gas_network()
    n.remove("Store", "BEWAL gas Store")

    apply_gas_store_cap(n, "BEWAL", "e_nom_max", 0.0)

    assert "No gas Store at bus BEWAL" in caplog.text


def test_capped_store_solves_and_stays_empty():
    """A winter-peak toy LP that would otherwise build a Walloon seasonal store."""
    n = _gas_network()
    n.set_snapshots(range(4))

    for bus in ("BEWAL", "BEVLG"):
        n.add("Bus", bus, carrier="AC")
        n.add(
            "Link",
            f"{bus} OCGT",
            bus0=f"{bus} gas",
            bus1=bus,
            carrier="gas",
            efficiency=1.0,
            p_nom=100.0,
        )
        # cheap gas in the first two snapshots, expensive in the last two:
        # storing is worth 20/MWh, so an uncapped store is always built
        n.add(
            "Generator",
            f"{bus} gas import",
            bus=f"{bus} gas",
            carrier="gas",
            p_nom=100.0,
            marginal_cost=[10.0, 10.0, 30.0, 30.0],
        )
        n.add("Load", f"{bus} load", bus=bus, p_set=50.0)

    # storing must be cheap enough to be built, but not free
    n.stores["capital_cost"] = 0.1

    status, _ = n.optimize(solver_name="highs")
    assert status == "ok"
    # uncapped, the store is worth building: this is the 2025-2040 artefact
    assert n.stores.at["BEWAL gas Store", "e_nom_opt"] > 0.0

    apply_gas_store_cap(n, "BEWAL", "e_nom_max", 0.0)
    status, _ = n.optimize(solver_name="highs")

    assert status == "ok"  # the gas bus still balances without a local store
    assert n.stores.at["BEWAL gas Store", "e_nom_opt"] == pytest.approx(0.0, abs=1e-6)
    assert n.stores.at["BEVLG gas Store", "e_nom_opt"] >= 545_280.0
