"""Guards for the aggregate-capacity corridor widening in `solve_network`.

Background. The caps files pin whole (country, carrier) fleets by stating
``min == max`` -- 18 groups in the 2025 base year alone. The two `agg_p_nom`
constraints then pin a *sum* of extendable capacities to an exact value, and with
``include_existing`` both sides subtract the same standing fleet, so the residual
right-hand side is a difference of near-equal numbers: 0.20 MW for BE
``offwind-all`` at 2025, against individual ``p_nom_max`` bounds summing to
16 000 MW. On 2026-08-29 the barrier stopped 3.4 % above its own dual bound
rather than converging on that. Giving the corridor a width fixed it, at the
stock solver settings and in the same wall-clock time (235 iter / 1895 s optimal,
against 212 iter / 1985 s sub-optimal).

The width is *data*, not code: it is a statement about how precisely a given
source pins that country's fleet, so it lives in a `tolerance` column of
``agg_p_nom_minmax*.csv`` and is read per row by `corridor_tolerance`. A row with
a blank cell, or a caps file with no such column, keeps the exact equality.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from solve_network import (
    _widen_against,
    corridor_tolerance,
    widen_collapsed_corridors,
)

CAPS = "data/walloon/agg_p_nom_minmax_demande_haute.csv"


def _frame(rows):
    """rows: (country, carrier, min, max)."""
    idx = pd.MultiIndex.from_tuples(
        [(c, k) for c, k, _, _ in rows], names=["country", "carrier"]
    )
    return pd.DataFrame(
        {"min": [mn for _, _, mn, _ in rows], "max": [mx for _, _, _, mx in rows]},
        index=idx,
    )


def _tol(d):
    return pd.Series(
        d, index=pd.MultiIndex.from_tuples(list(d), names=["country", "carrier"])
    )


# --- reading the tolerance out of the data ------------------------------------


def test_tolerance_is_read_from_the_caps_file():
    raw = pd.read_csv(CAPS, index_col=[0, 1], header=[0, 1])
    tol = corridor_tolerance(raw)
    assert tol[("BE", "offwind-all")] == pytest.approx(0.005)
    assert (tol >= 0).all()
    assert tol.gt(0).sum() >= 15, "base year no longer carries widths -- check the CSV"


def test_blank_tolerance_cell_means_zero():
    raw = pd.read_csv(CAPS, index_col=[0, 1], header=[0, 1])
    tol = corridor_tolerance(raw)
    # a legacy-unreviewed row that states only minima needs no width
    assert tol[("BG", "offwind-all")] == 0.0


def test_caps_file_without_the_column_gets_zero_everywhere():
    """The upstream data/agg_p_nom_minmax.csv predates the column."""
    raw = pd.DataFrame(
        {("2030", "min"): [1.0]},
        index=pd.MultiIndex.from_tuples([("BE", "onwind")], names=["country", "carrier"]),
    )
    tol = corridor_tolerance(raw)
    assert tol.tolist() == [0.0]


# --- corridors the file states as an equality ---------------------------------


def test_collapsed_corridor_is_widened_by_its_own_row_value():
    df = _frame([("BE", "offwind-all", 2262.0, 2262.0)])
    out = widen_collapsed_corridors(df, _tol({("BE", "offwind-all"): 0.005}), "2025")
    assert out.loc[("BE", "offwind-all"), "min"] == 2262.0
    assert out.loc[("BE", "offwind-all"), "max"] == pytest.approx(2262.0 * 1.005)


def test_rows_can_carry_different_widths():
    df = _frame([("BE", "offwind-all", 2000.0, 2000.0), ("LU", "onwind", 227.0, 227.0)])
    tol = _tol({("BE", "offwind-all"): 0.005, ("LU", "onwind"): 0.02})
    out = widen_collapsed_corridors(df, tol, "2025")
    assert out.loc[("BE", "offwind-all"), "max"] == pytest.approx(2010.0)
    assert out.loc[("LU", "onwind"), "max"] == pytest.approx(227.0 * 1.02)


def test_zero_tolerance_keeps_the_equality():
    df = _frame([("BE", "offwind-all", 2262.0, 2262.0)])
    out = widen_collapsed_corridors(df, _tol({("BE", "offwind-all"): 0.0}), "2025")
    pd.testing.assert_frame_equal(out, df)


def test_open_corridor_is_untouched_even_with_a_tolerance():
    df = _frame([("CZ", "onwind", 0.0, 1500.0)])
    out = widen_collapsed_corridors(df, _tol({("CZ", "onwind"): 0.005}), "2025")
    pd.testing.assert_frame_equal(out, df)


def test_missing_bound_is_not_a_corridor():
    df = _frame([("BEWAL", "nuclear-all", 1000.0, float("nan"))])
    out = widen_collapsed_corridors(df, _tol({("BEWAL", "nuclear-all"): 0.005}), "2040")
    pd.testing.assert_frame_equal(out, df)


def test_widened_max_never_falls_below_min():
    df = _frame([("LU", "onwind", 227.0, 227.0)])
    out = widen_collapsed_corridors(df, _tol({("LU", "onwind"): 0.005}), "2025")
    assert (out["max"] >= out["min"]).all()


def test_the_shipped_2025_column_is_actually_widened():
    """Regression on the real file, not a synthetic frame."""
    raw = pd.read_csv(CAPS, index_col=[0, 1], header=[0, 1])
    tol = corridor_tolerance(raw)
    caps = raw["2025"]
    both = caps[["min", "max"]].dropna()
    collapsed = both[
        (both["max"] - both["min"]).abs() <= 1e-6 * both["min"].clip(lower=1)
    ]
    assert len(collapsed) >= 15, "base year no longer pins the fleet -- revisit this"

    out = widen_collapsed_corridors(caps, tol, "2025")
    widened = out.loc[collapsed.index]
    assert (widened["max"] > widened["min"]).all()


# --- corridors that collapse while the right-hand sides are built -------------


def test_growth_collapsed_corridor_is_widened():
    """2040 BE nuclear-all collapses on both the generator and link path."""
    mn = _tol({("BE", "nuclear-all"): 2000.0})
    mx = _tol({("BE", "nuclear-all"): 2000.0})
    out = _widen_against(mx, mn, _tol({("BE", "nuclear-all"): 0.005}), "2040", "links")
    assert out[("BE", "nuclear-all")] == pytest.approx(2010.0)


def test_open_runtime_corridor_is_untouched():
    mn = _tol({("FR", "onwind"): 7817.48})
    mx = _tol({("FR", "onwind"): 19328.0})
    out = _widen_against(mx, mn, _tol({("FR", "onwind"): 0.005}), "2030", "generators")
    assert out[("FR", "onwind")] == 19328.0


def test_group_absent_from_the_caps_file_is_left_alone():
    """No row means no stated width, so nothing to widen."""
    mn = _tol({("DE", "onwind"): 48910.0})
    mx = _tol({("DE", "onwind"): 48910.0})
    out = _widen_against(mx, mn, _tol({("FR", "onwind"): 0.005}), "2030", "generators")
    assert out[("DE", "onwind")] == 48910.0


def test_max_without_a_matching_min_is_untouched():
    mn = _tol({("FR", "onwind"): 7817.48})
    mx = _tol({("BEVLG", "onwind"): 989.0})
    out = _widen_against(mx, mn, _tol({("BEVLG", "onwind"): 0.005}), "2030", "generators")
    assert out[("BEVLG", "onwind")] == 989.0


def test_runtime_widening_never_lowers_a_ceiling():
    mn = _tol({("A", "x"): 100.0, ("B", "y"): 50.0})
    mx = _tol({("A", "x"): 100.0, ("B", "y"): 900.0})
    tol = _tol({("A", "x"): 0.005, ("B", "y"): 0.005})
    out = _widen_against(mx, mn, tol, "2030", "generators")
    assert (out >= mx).all()


# --- a stated floor outranks the build-rate ceiling ---------------------------


def _precedence(growth, floors):
    """The rule add_CCL_constraints applies: drop the ceiling where it cannot sit
    above the floor, rather than clipping the floor down onto it."""
    f = floors.reindex(growth.index)
    conflicting = growth.index[f.notna() & (growth <= f)]
    return growth.drop(conflicting), list(conflicting)


def test_ceiling_below_the_floor_is_dropped_not_reconciled():
    """2030: DE onwind and GB offwind-all need more than 2x the record build."""
    growth = _tol({("DE", "onwind"): 48910.0, ("GB", "offwind-all"): 26720.0})
    floors = _tol({("DE", "onwind"): 57169.0, ("GB", "offwind-all"): 34008.0})
    kept, dropped = _precedence(growth, floors)
    assert kept.empty
    assert len(dropped) == 2


def test_ceiling_above_the_floor_survives():
    growth = _tol({("FR", "onwind"): 19328.0})
    floors = _tol({("FR", "onwind"): 7817.48})
    kept, dropped = _precedence(growth, floors)
    assert not dropped
    assert kept[("FR", "onwind")] == 19328.0


def test_group_without_a_floor_keeps_its_ceiling():
    growth = _tol({("BEVLG", "onwind"): 989.0})
    floors = _tol({("FR", "onwind"): 7817.48})
    kept, dropped = _precedence(growth, floors)
    assert not dropped
    assert kept[("BEVLG", "onwind")] == 989.0


def test_narrow_but_open_corridor_is_left_alone():
    """BEWAL solar-all at 2030: floor 6500, ceiling 6585. Tight, not collapsed."""
    growth = _tol({("BEWAL", "solar-all"): 6585.0})
    floors = _tol({("BEWAL", "solar-all"): 6500.0})
    kept, dropped = _precedence(growth, floors)
    assert not dropped
    assert kept[("BEWAL", "solar-all")] == 6585.0
