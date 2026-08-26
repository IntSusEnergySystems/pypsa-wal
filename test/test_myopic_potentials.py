# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Myopic capacity potentials must cap the fleet, not each new vintage.

Three independent mechanisms used to re-apply the same limit to every horizon,
so a four-horizon chain could end up with four times the potential:

* ``add_land_use_constraint`` (per-bus ``p_nom_max``) was gated off whenever the
  CCL constraint was on;
* ``add_CCL_constraints`` subtracted existing capacity from the aggregate
  ``min`` and from the link ``max``, but not from the generator ``max``;
* ``custom_potentials.csv`` ``p_nom_min`` rows were written onto the new vintage
  instead of the fleet.

Symptom in ``docs/logs/2026-08-25_scen_demande_haute_2010_1h.md`` §11.5: 2050
BEWAL onwind 12 395 MW against a 6 500 MW potential, with the extendable
tranche *exactly* 6 500.
"""

from __future__ import annotations

from pathlib import Path

import pypsa
import pytest

import scripts.solve_network as sn
from scripts.solve_network import add_CCL_constraints, add_land_use_constraint
from scripts.walloon_scripts.BEWAL_potentials import (
    apply_link_p_nom_min,
    update_BEWAL_potentials,
)

CAP = 6500.0


def _wind_network(existing: float, cap: float = CAP) -> pypsa.Network:
    """One bus with an existing 2030 wind vintage and an extendable 2050 one."""
    n = pypsa.Network()
    n.add("Carrier", ["AC", "gas", "onwind", "CCGT", "CCGT CC"])
    n.add("Bus", "BEWAL", carrier="AC", country="BE")
    n.add(
        "Generator",
        "BEWAL 0 onwind-2030",
        bus="BEWAL",
        carrier="onwind",
        p_nom=existing,
        p_nom_extendable=False,
        build_year=2030,
        lifetime=30,
    )
    n.add(
        "Generator",
        "BEWAL 0 onwind-2050",
        bus="BEWAL",
        carrier="onwind",
        p_nom_extendable=True,
        p_nom_max=cap,
        capital_cost=1e5,
        build_year=2050,
        lifetime=30,
    )
    return n


def test_land_use_subtracts_existing_from_the_new_vintage():
    n = _wind_network(existing=4000.0)
    add_land_use_constraint(n, "2050")
    assert n.generators.at["BEWAL 0 onwind-2050", "p_nom_max"] == pytest.approx(2500.0)
    # the existing vintage keeps its own p_nom
    assert n.generators.at["BEWAL 0 onwind-2030", "p_nom"] == pytest.approx(4000.0)


def test_land_use_clips_at_zero_when_existing_exceeds_the_potential():
    n = _wind_network(existing=9000.0)
    add_land_use_constraint(n, "2050")
    assert n.generators.at["BEWAL 0 onwind-2050", "p_nom_max"] == 0.0


def test_land_use_tolerates_a_bus_without_a_current_vintage():
    """A retired carrier leaves existing capacity with no extendable twin."""
    n = _wind_network(existing=4000.0)
    n.remove("Generator", "BEWAL 0 onwind-2050")
    add_land_use_constraint(n, "2050")  # must not raise


def _agg_file(tmp_path: Path, *, maximum: float, minimum: float = 0.0) -> str:
    path = tmp_path / "agg_p_nom_minmax.csv"
    path.write_text(
        ",,2050,2050\n"
        ",,min,max\n"
        "country,carrier,,\n"
        f"BE,onwind,{minimum},{maximum}\n"
    )
    return str(path)


def _ccl_config(file: str) -> dict:
    return {
        "solving": {
            "agg_p_nom_limits": {
                "file": file,
                "agg_offwind": True,
                "agg_solar": True,
                "agg_nuclear": True,
                "agg_ccgt": True,
                "include_existing": True,
            }
        }
    }


def _ccl_network(existing: float, floor: float = 0.0) -> pypsa.Network:
    n = _wind_network(existing=existing)
    n.generators.loc["BEWAL 0 onwind-2050", "p_nom_min"] = floor
    n.generators.loc["BEWAL 0 onwind-2050", "p_nom_max"] = 1e6
    # add_CCL_constraints reads Link-p_nom unconditionally
    n.add("Bus", "EU gas", carrier="gas", country="EU")
    n.add(
        "Link",
        "BEWAL CCGT-2050",
        bus0="EU gas",
        bus1="BEWAL",
        carrier="CCGT",
        efficiency=0.6,
        p_nom_extendable=True,
        capital_cost=5e4,
        build_year=2050,
        lifetime=25,
    )
    n.set_snapshots([0])
    n.optimize.create_model(include_objective_constant=False)
    return n


def _agg_max_rhs(n: pypsa.Network) -> float:
    return float(n.model.constraints["agg_p_nom_max"].rhs.values.ravel()[0])


def test_ccl_generator_max_binds_the_fleet_not_the_tranche(tmp_path, monkeypatch):
    monkeypatch.setattr(sn, "foresight", "myopic", raising=False)
    n = _ccl_network(existing=4000.0)
    add_CCL_constraints(n, _ccl_config(_agg_file(tmp_path, maximum=CAP)), "2050")
    # 6500 cap − 4000 already standing = 2500 left for the new vintage
    assert _agg_max_rhs(n) == pytest.approx(2500.0)


def test_ccl_generator_max_never_binds_below_the_brownfield_floor(
    tmp_path, monkeypatch
):
    """A cap below the extendable lower bound must be raised, not made infeasible."""
    monkeypatch.setattr(sn, "foresight", "myopic", raising=False)
    n = _ccl_network(existing=9000.0, floor=300.0)
    add_CCL_constraints(n, _ccl_config(_agg_file(tmp_path, maximum=CAP)), "2050")
    assert _agg_max_rhs(n) == pytest.approx(300.0)


def _ccgt_network(carrier: str, efficiency: float, existing_el: float) -> pypsa.Network:
    n = pypsa.Network()
    n.add("Bus", "BEWAL", carrier="AC", country="BE")
    n.add("Bus", "EU gas", carrier="gas", country="EU")
    for year, p_nom_el, extendable in ((2030, existing_el, False), (2050, 0.0, True)):
        n.add(
            "Link",
            f"BEWAL {carrier}-{year}",
            bus0="EU gas",
            bus1="BEWAL",
            carrier=carrier,
            efficiency=efficiency,
            p_nom=p_nom_el / efficiency,
            p_nom_extendable=extendable,
            build_year=year,
            lifetime=25,
        )
    return n


@pytest.mark.parametrize("carrier,efficiency", [("CCGT", 0.60), ("CCGT CC", 0.52)])
def test_ccgt_floor_is_a_fleet_floor(carrier, efficiency):
    n = _ccgt_network(carrier, efficiency, existing_el=1000.0)
    apply_link_p_nom_min(n, "BEWAL", carrier, 1740.0, 2050, electrical=True)
    # 740 MW_el of residual, expressed on the fuel bus with this link's own eta
    assert n.links.at[f"BEWAL {carrier}-2050", "p_nom_min"] == pytest.approx(
        740.0 / efficiency
    )
    assert n.links.at[f"BEWAL {carrier}-2030", "p_nom_min"] == 0.0


def test_ccgt_floor_is_zero_once_the_fleet_already_meets_it():
    n = _ccgt_network("CCGT", 0.60, existing_el=1740.0)
    apply_link_p_nom_min(n, "BEWAL", "CCGT", 1740.0, 2050, electrical=True)
    assert n.links.at["BEWAL CCGT-2050", "p_nom_min"] == 0.0


def test_ccgt_and_ccgt_cc_floors_do_not_leak_into_each_other():
    n = _ccgt_network("CCGT", 0.60, existing_el=1740.0)
    for year, extendable in ((2030, False), (2050, True)):
        n.add(
            "Link",
            f"BEWAL CCGT CC-{year}",
            bus0="EU gas",
            bus1="BEWAL",
            carrier="CCGT CC",
            efficiency=0.52,
            p_nom=0.0,
            p_nom_extendable=extendable,
            build_year=year,
            lifetime=25,
        )
    apply_link_p_nom_min(n, "BEWAL", "CCGT CC", 1740.0, 2050, electrical=True)
    # unabated capacity does not count toward the capture floor
    assert n.links.at["BEWAL CCGT CC-2050", "p_nom_min"] == pytest.approx(1740.0 / 0.52)
    assert n.links.at["BEWAL CCGT-2050", "p_nom_min"] == 0.0


def test_update_bewal_potentials_routes_ccgt_p_nom_min_through_the_fleet_floor(
    tmp_path: Path,
):
    csv = tmp_path / "custom_potentials.csv"
    csv.write_text(
        "bus,technology,parameter,value,unit,year,source,further_description,year_currency\n"
        "BEWAL,CCGT,p_nom_min,1740,MW_el,2050,,,\n"
    )
    n = _ccgt_network("CCGT", 0.60, existing_el=1740.0)
    update_BEWAL_potentials(n, 2050, walloon_potentials=str(csv))
    assert n.links.at["BEWAL CCGT-2050", "p_nom_min"] == 0.0
