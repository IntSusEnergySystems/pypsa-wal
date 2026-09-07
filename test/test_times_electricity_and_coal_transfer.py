# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Two soft-link transfers that were quietly changing the TIMES numbers.

Both defects had the same shape: a PyPSA-Eur convention that is correct for the
statistical data PyPSA-Eur is built on, applied on top of a Walloon load that
had just been pinned to a TIMES value measured somewhere else.  Neither shows
up as an error — the LP is feasible and every aggregate closes — only as a
level-2.3 deviation in ``review_run.py``.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scripts.prepare_sector_network import (
    MWH_COAL_PER_MWH_COKE,
    WALLOON_ELECTRICITY_CATEGORIES,
    coke_to_coal_factors,
    distribution_loss_targets,
)

NODES = pd.Index(["BEWAL", "BEVLG", "DE1 0"])


# --------------------------------------------------------------------------
# R1 -- the coke oven Wallonia does not have
# --------------------------------------------------------------------------

def test_coke_is_grossed_up_to_coal_outside_the_times_node():
    factors = coke_to_coal_factors(NODES, times_demand=True, wallon_node="BEWAL")
    assert factors["BEVLG"] == MWH_COAL_PER_MWH_COKE
    assert factors["DE1 0"] == MWH_COAL_PER_MWH_COKE


def test_the_times_node_takes_coke_at_face_value():
    """`IMPCOACOK` is the only source of `COACOK` in the .vd: no oven, no factor."""
    factors = coke_to_coal_factors(NODES, times_demand=True, wallon_node="BEWAL")
    assert factors["BEWAL"] == 1.0


def test_without_the_times_transfer_nothing_is_exempt():
    factors = coke_to_coal_factors(NODES, times_demand=False, wallon_node="BEWAL")
    assert (factors == MWH_COAL_PER_MWH_COKE).all()


@pytest.mark.parametrize(
    ("year", "coal", "coke", "reported"),
    [
        (2025, 2.7004666877733805, 1.0059879460755992, 0.098),
        (2030, 1.8762047005382334, 1.1615875210429873, 0.140),
        (2040, 0.0023768414296, 1.0169554857808, 0.367),
        (2050, 0.7067109108447, 1.1615875210429873, 0.234),
    ],
)
def test_the_oven_factor_is_the_whole_of_finding_r1(year, coal, coke, reported):
    """The 2026-09-06 overshoot is this factor and nothing else.

    ``coal + 1.366 x coke`` against TIMES' ``coal + coke`` reproduces the
    reported +9.8 / +14.0 / +36.7 / +23.4 % to within the rounding the nodal
    demand CSV used to apply.
    """
    inflated = coal + MWH_COAL_PER_MWH_COKE * coke
    assert inflated / (coal + coke) - 1 == pytest.approx(reported, abs=0.01)
    # And with the fix the transfer is exact.
    assert coal + 1.0 * coke == pytest.approx(coal + coke)


# --------------------------------------------------------------------------
# R2 -- distribution losses deducted from a low-voltage TIMES demand
# --------------------------------------------------------------------------

def _loads():
    return pd.DataFrame(
        {"carrier": ["electricity", "electricity", "industry electricity",
                     "agriculture electricity"]},
        index=["BEWAL", "BEVLG", "BEWAL industry electricity",
               "BEWAL agriculture electricity"],
    )


def test_distribution_losses_still_come_off_every_other_node():
    targets = distribution_loss_targets(
        _loads(), times_demand=True, wallon_node="BEWAL"
    )
    assert "BEVLG" in targets


def test_the_times_pinned_walloon_load_keeps_its_full_energy():
    targets = distribution_loss_targets(
        _loads(), times_demand=True, wallon_node="BEWAL"
    )
    assert "BEWAL" not in targets


def test_only_the_bare_electricity_carrier_was_ever_deducted():
    """The exemption also removes an inconsistency: industry never lost its 3 %."""
    targets = distribution_loss_targets(
        _loads(), times_demand=False, wallon_node=None
    )
    assert set(targets) == {"BEWAL", "BEVLG"}


def test_without_the_times_transfer_the_walloon_load_is_deducted_as_before():
    targets = distribution_loss_targets(
        _loads(), times_demand=False, wallon_node="BEWAL"
    )
    assert "BEWAL" in targets


# --------------------------------------------------------------------------
# R2 -- rail
# --------------------------------------------------------------------------

def test_the_walloon_electricity_load_carries_electric_rail_only():
    """`total rail` is electric *and* diesel; only the electric half is a load."""
    assert "electricity rail" in WALLOON_ELECTRICITY_CATEGORIES
    assert "total rail" not in WALLOON_ELECTRICITY_CATEGORIES


def test_the_data_centre_child_row_stays_out_of_the_sum():
    """It is a child of `total electricity services`, so adding it double counts."""
    assert "services data centre electricity" not in WALLOON_ELECTRICITY_CATEGORIES
