# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Cap on all CO₂ captured in Wallonia (TIMES alignment, 2026-10-10).

Toy LP: 10 t/h of process CO₂ at BEWAL is either captured onto
`BEWAL co2 stored` (free) or vented at 20 EUR/t, the stand-in for the carbon
price. Captured CO₂ leaves by a free pipeline to a German sink or is used
locally at 5 EUR/t (power-to-fuel). Flanders can send 10 t/h through Wallonia.
"""

from __future__ import annotations

from pathlib import Path

import pypsa
import pytest
import yaml

from scripts.walloon_scripts.named_pins import (
    add_co2_capture_limit,
    captured_co2_expr,
)

ROOT = Path(__file__).resolve().parents[1]
HOURS = 4380.0  # two snapshots of half a year
ANNUAL_T = 10.0 * 2 * HOURS  # Walloon process CO₂, t/a
VENT = 20.0  # EUR/t


def _network(transit: bool = False, local_use: bool = False) -> pypsa.Network:
    n = pypsa.Network()
    n.set_snapshots(range(2))
    n.snapshot_weightings["generators"] = HOURS
    n.snapshot_weightings["objective"] = HOURS
    n.add("Carrier", ["co2", "co2 stored", "CO2 pipeline", "process emissions CC",
                      "vent", "use", "Fischer-Tropsch"])
    for node in ("BEWAL", "DE", "BEVLG"):
        n.add("Bus", f"{node} co2 stored", carrier="co2 stored", location=node)
    n.add("Bus", "BEWAL process emissions", carrier="co2", location="BEWAL")
    n.add("Bus", "co2 atmosphere", carrier="co2")
    n.add("Bus", "fuel", carrier="use")
    n.add("Bus", "H2", carrier="use")
    n.add("Generator", "process", bus="BEWAL process emissions", p_nom=10.0,
          p_min_pu=1.0, carrier="co2")
    n.add("Link", "BEWAL process emissions CC", bus0="BEWAL process emissions",
          bus1="co2 atmosphere", bus2="BEWAL co2 stored", efficiency=0.0,
          efficiency2=1.0, p_nom=100.0, carrier="process emissions CC")
    n.add("Link", "vent", bus0="BEWAL process emissions", bus1="co2 atmosphere",
          p_nom=100.0, marginal_cost=VENT, carrier="vent")
    n.add("Generator", "atmosphere", bus="co2 atmosphere", p_nom=100.0,
          p_min_pu=-1.0, p_max_pu=0.0, carrier="co2")
    n.add("Generator", "DE sink", bus="DE co2 stored", p_nom=100.0,
          p_min_pu=-1.0, p_max_pu=0.0, carrier="co2 stored")
    n.add("Link", "CO2 pipeline BEWAL -> DE", bus0="BEWAL co2 stored",
          bus1="DE co2 stored", p_nom=100.0, p_min_pu=-1.0, carrier="CO2 pipeline")
    if local_use:
        # A use port with a NEGATIVE efficiency into the bus: it takes CO₂ off
        # `co2 stored` and must not count as capture.
        n.add("Generator", "H2 supply", bus="H2", p_nom=100.0, carrier="use")
        n.add("Link", "BEWAL Fischer-Tropsch", bus0="H2", bus1="fuel",
              bus2="BEWAL co2 stored", efficiency=1.0, efficiency2=-1.0,
              p_nom=100.0, marginal_cost=5.0, carrier="Fischer-Tropsch")
        n.add("Generator", "fuel sink", bus="fuel", p_nom=100.0, p_min_pu=-1.0,
              p_max_pu=0.0, carrier="use")
    if transit:
        n.add("Generator", "flemish capture", bus="BEVLG co2 stored", p_nom=10.0,
              p_min_pu=1.0, carrier="co2 stored")
        n.add("Link", "CO2 pipeline BEVLG -> BEWAL", bus0="BEVLG co2 stored",
              bus1="BEWAL co2 stored", p_nom=100.0, p_min_pu=-1.0,
              carrier="CO2 pipeline")
    return n


def _solve(n, kt, price):
    status, _ = n.optimize(
        solver_name="highs",
        extra_functionality=lambda n, s: add_co2_capture_limit(n, "BEWAL", kt, price),
    )
    assert status == "ok"
    w = n.snapshot_weightings.generators
    captured = (n.links_t.p0["BEWAL process emissions CC"] * w).sum()
    vented = (n.links_t.p0["vent"] * w).sum()
    mu = n.global_constraints.at["co2_capture_limit_BEWAL", "mu"]
    return captured, vented, mu


def test_hard_cap_vents_the_rest():
    captured, vented, mu = _solve(_network(), ANNUAL_T / 2 / 1e3, None)
    assert captured == pytest.approx(ANNUAL_T / 2, rel=1e-6)
    assert vented == pytest.approx(ANNUAL_T / 2, rel=1e-6)
    # The dual is the rent of a captured tonne: the carbon price it avoids.
    assert mu == pytest.approx(-VENT, rel=1e-6)


def test_slack_cap_has_a_zero_dual():
    captured, vented, mu = _solve(_network(), 2 * ANNUAL_T / 1e3, None)
    assert captured == pytest.approx(ANNUAL_T, rel=1e-6)
    assert vented == pytest.approx(0.0, abs=1e-6)
    assert mu == pytest.approx(0.0, abs=1e-9)


def test_cheap_overage_is_paid_instead():
    captured, vented, mu = _solve(_network(), ANNUAL_T / 2 / 1e3, 1.0)
    assert captured == pytest.approx(ANNUAL_T, rel=1e-6)
    assert vented == pytest.approx(0.0, abs=1e-6)
    assert mu == pytest.approx(-1.0, rel=1e-6)


def test_dear_overage_acts_as_the_cap():
    captured, vented, mu = _solve(_network(), ANNUAL_T / 2 / 1e3, 500.0)
    assert captured == pytest.approx(ANNUAL_T / 2, rel=1e-6)
    assert mu == pytest.approx(-VENT, rel=1e-6)


def test_local_use_does_not_free_room():
    """Unlike lever D, using the CO₂ in Wallonia does not lift the cap."""
    captured, vented, mu = _solve(_network(local_use=True), ANNUAL_T / 2 / 1e3, None)
    assert captured == pytest.approx(ANNUAL_T / 2, rel=1e-6)
    assert vented == pytest.approx(ANNUAL_T / 2, rel=1e-6)


def test_transit_is_not_capture():
    """Flemish CO₂ arriving by pipeline is not Walloon capture: the cap stays slack."""
    captured, vented, mu = _solve(_network(transit=True), 1.5 * ANNUAL_T / 1e3, None)
    assert captured == pytest.approx(ANNUAL_T, rel=1e-6)
    assert mu == pytest.approx(0.0, abs=1e-9)


def test_expression_counts_capture_ports_only():
    n = _network(transit=True, local_use=True)
    n.optimize.create_model()
    terms = str(captured_co2_expr(n, "BEWAL"))
    assert "BEWAL process emissions CC" in terms
    for other in ("vent", "Fischer-Tropsch", "CO2 pipeline"):
        assert other not in terms


def test_ptx_report_reads_capture_cap():
    from scripts.walloon_scripts.ptx_report import co2_balance

    n = _network()
    _solve(n, ANNUAL_T / 2 / 1e3, 1.0)
    got = co2_balance(n, "BEWAL")
    assert got["capture total"] == pytest.approx(ANNUAL_T / 1e6, abs=1e-3)
    assert got["capture cap"] == pytest.approx(ANNUAL_T / 2 / 1e6, abs=1e-3)
    assert got["capture overage"] == pytest.approx(ANNUAL_T / 2 / 1e6, abs=1e-3)
    assert got["capture cap dual EUR/t"] == pytest.approx(-1.0, abs=1e-3)


def test_on_and_equal_to_the_convergence_table():
    """Base config: the cap is ON (2026-10-10) and carries the convergence table's bounds.

    `config:sector.co2_capture_limit.kt` is a per-horizon mapping that
    build_common_parameters.py does not patch, so this is what keeps the two
    from drifting apart.
    """
    import pandas as pd

    cfg = yaml.safe_load((ROOT / "config/config.walloon.yaml").read_text())
    cap = cfg["sector"]["co2_capture_limit"]
    assert cap["enable"] is True
    assert cap["node"] == "BEWAL"
    master = pd.read_csv(ROOT / "config/input_parameters_for_models.csv")
    rows = master[
        (master["pypsa_wal_target"] == "config:sector.co2_capture_limit.kt")
        & (master["status"] == "active")
    ]
    table = {int(y): float(v) for y, v in zip(rows["year"], rows["value"])}
    assert table == {2030: 2000.0, 2035: 4000.0, 2040: 6000.0, 2045: 7000.0, 2050: 8000.0}
    assert {int(y): float(v) for y, v in cap["kt"].items()} == table
    # Above the highest carbon price at which the cap must bind (2050 system
    # CO2 dual 654 EUR/t in the 6 Oct central), or the valve is paid instead.
    assert cap["overage_price"] >= 700


def test_no_batch_scenario_opts_out():
    """Every batch scenario inherits the cap, so each sensitivity is a one-change delta."""
    cfg = yaml.safe_load((ROOT / "config/config.walloon.yaml").read_text())
    scenarios = yaml.safe_load((ROOT / "config/scenarios.walloon.yaml").read_text())
    for name in cfg["run"]["name"]:
        sector = scenarios[name].get("sector") or {}
        assert "co2_capture_limit" not in sector, f"{name} overrides the capture cap"
