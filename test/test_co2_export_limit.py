# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Lever D: a cap on the net CO₂ leaving Wallonia (docs/co2-sequestration.md §10.2).

Toy LP: 10 t/h of captured CO₂ appears on `BEWAL co2 stored`. It can leave for
free through a pipeline to a German sink, or be used locally at 5 EUR/t (the
stand-in for power-to-fuel). Flanders sends another 10 t/h through Wallonia.
"""

from __future__ import annotations

import pypsa
import pytest

from scripts.walloon_scripts.named_pins import add_co2_export_limit

HOURS = 4380.0  # two snapshots of half a year
ANNUAL_T = 10.0 * 2 * HOURS  # Walloon capture, t/a


def _network(transit: bool = False) -> pypsa.Network:
    n = pypsa.Network()
    n.set_snapshots(range(2))
    n.snapshot_weightings["generators"] = HOURS
    n.snapshot_weightings["objective"] = HOURS
    n.add("Carrier", ["co2 stored", "CO2 pipeline", "use"])
    for node in ("BEWAL", "DE", "BEVLG"):
        n.add("Bus", f"{node} co2 stored", carrier="co2 stored", location=node)
    n.add("Bus", "fuel", carrier="use")
    n.add("Generator", "capture", bus="BEWAL co2 stored", p_nom=10.0,
          p_min_pu=1.0, carrier="co2 stored")
    n.add("Generator", "DE sink", bus="DE co2 stored", p_nom=100.0,
          p_min_pu=-1.0, p_max_pu=0.0, carrier="co2 stored")
    n.add("Link", "CO2 pipeline BEWAL -> DE", bus0="BEWAL co2 stored",
          bus1="DE co2 stored", p_nom=100.0, p_min_pu=-1.0, carrier="CO2 pipeline")
    n.add("Link", "use", bus0="BEWAL co2 stored", bus1="fuel", p_nom=100.0,
          marginal_cost=5.0, carrier="use")
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
        extra_functionality=lambda n, s: add_co2_export_limit(n, "BEWAL", kt, price),
    )
    assert status == "ok"
    w = n.snapshot_weightings.generators
    exported = (n.links_t.p0["CO2 pipeline BEWAL -> DE"] * w).sum()
    used = (n.links_t.p0["use"] * w).sum()
    mu = n.global_constraints.at["co2_export_limit_BEWAL", "mu"]
    return exported, used, mu


def test_hard_cap_sends_the_rest_to_local_use():
    exported, used, mu = _solve(_network(), ANNUAL_T / 2 / 1e3, None)
    assert exported == pytest.approx(ANNUAL_T / 2, rel=1e-6)
    assert used == pytest.approx(ANNUAL_T / 2, rel=1e-6)
    # The dual survives into the network, at the cost of the local outlet.
    assert mu == pytest.approx(-5.0, rel=1e-6)


def test_slack_cap_has_a_zero_dual():
    """Step 4 of docs/co2-sequestration.md §11: present, signed, not binding."""
    exported, used, mu = _solve(_network(), 2 * ANNUAL_T / 1e3, None)
    assert exported == pytest.approx(ANNUAL_T, rel=1e-6)
    assert used == pytest.approx(0.0, abs=1e-6)
    assert mu == pytest.approx(0.0, abs=1e-9)


def test_cheap_overage_is_paid_instead():
    """Overage below the cost of local use: everything is exported."""
    exported, used, mu = _solve(_network(), ANNUAL_T / 2 / 1e3, 1.0)
    assert exported == pytest.approx(ANNUAL_T, rel=1e-6)
    assert used == pytest.approx(0.0, abs=1e-6)
    assert mu == pytest.approx(-1.0, rel=1e-6)


def test_dear_overage_acts_as_the_cap():
    exported, used, mu = _solve(_network(), ANNUAL_T / 2 / 1e3, 50.0)
    assert exported == pytest.approx(ANNUAL_T / 2, rel=1e-6)
    assert used == pytest.approx(ANNUAL_T / 2, rel=1e-6)
    assert mu == pytest.approx(-5.0, rel=1e-6)


def test_transit_does_not_use_up_the_cap():
    """Flemish CO₂ crossing Wallonia enters and leaves: net zero."""
    exported, used, mu = _solve(_network(transit=True), ANNUAL_T / 2 / 1e3, None)
    assert exported == pytest.approx(ANNUAL_T / 2 + ANNUAL_T, rel=1e-6)
    assert used == pytest.approx(ANNUAL_T / 2, rel=1e-6)
    assert mu == pytest.approx(-5.0, rel=1e-6)


def test_transit_alone_leaves_the_cap_slack():
    """Step 5 of docs/co2-sequestration.md §11, the single most important one.

    Net Walloon export (10 t/h) is under the cap, gross pipe flow (20 t/h) is
    over it. A non-zero dual here would mean the constraint is gross and is
    throttling Flanders.
    """
    exported, used, mu = _solve(_network(transit=True), 1.5 * ANNUAL_T / 1e3, None)
    assert exported == pytest.approx(2 * ANNUAL_T, rel=1e-6)
    assert used == pytest.approx(0.0, abs=1e-6)
    assert mu == pytest.approx(0.0, abs=1e-9)


def test_ptx_report_reads_cap_dual_and_overage():
    """The run report recomputes the overage from flows and reads the stored dual."""
    from scripts.walloon_scripts.ptx_report import co2_balance

    n = _network()
    _solve(n, ANNUAL_T / 2 / 1e3, 1.0)
    got = co2_balance(n, "BEWAL")
    assert got["net export (lever D)"] == pytest.approx(ANNUAL_T / 1e6, abs=1e-3)
    assert got["export cap"] == pytest.approx(ANNUAL_T / 2 / 1e6, abs=1e-3)
    assert got["overage"] == pytest.approx(ANNUAL_T / 2 / 1e6, abs=1e-3)
    assert got["export cap dual EUR/t"] == pytest.approx(-1.0, abs=1e-3)
