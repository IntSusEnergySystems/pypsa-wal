# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/PyPSA/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""The agg base-year pin already determines the fleet: do not force
IRENASTAT's recent-year share on top of it.

Regression for the 2026-09-05 1h review: the 2025 grouping bin (IRENA diffs
2021-2024) landed on the extendable 2025 candidates as ``p_nom_min`` (BEWAL
solar 1 802 MW on top of a 2 286 MW standing fleet, against a 2 668 MW pin),
so the base year overshot every tight pin and the review failed four
``aggregate max exceeded`` checks on an otherwise optimal run.
"""

from pathlib import Path

import pandas as pd
import pytest

from scripts.walloon_scripts.baseyear_forced_build import (
    baseyear_pins,
    reconcile_baseyear_forced_build,
)

REPO = Path(__file__).resolve().parents[1]
GROUPS = [2005, 2010, 2015, 2020, 2025]


def _agg(tmp_path, rows):
    """Minimal agg caps file: (node, carrier) -> (min, max) for 2025."""
    index = pd.MultiIndex.from_tuples(sorted(rows), names=["country", "carrier"])
    frame = pd.DataFrame(
        [[rows[k][0], rows[k][1]] for k in sorted(rows)],
        index=index,
        columns=pd.MultiIndex.from_tuples([("2025", "min"), ("2025", "max")]),
    )
    path = tmp_path / "caps.csv"
    frame.to_csv(path)
    return str(path)


def _dfagg(rows):
    """df_agg-shaped frame: (bus, Fueltype, DateIn, DateOut, Capacity)."""
    df = pd.DataFrame(
        rows, columns=["bus", "Fueltype", "DateIn", "DateOut", "Capacity"]
    )
    return df


def test_scaled_to_the_pin_headroom(tmp_path):
    agg = _agg(tmp_path, {("BEWAL", "solar-all"): (2668.0, 2668.0)})
    df = _dfagg(
        [
            ("BEWAL", "solar", 2015, 2040, 516.1),
            ("BEWAL", "solar", 2020, 2045, 1770.0),
            # IRENA 2021-2024 diffs, all binned into grouping-year 2025
            ("BEWAL", "solar", 2021, 2046, 201.7),
            ("BEWAL", "solar", 2022, 2047, 355.2),
            ("BEWAL", "solar", 2023, 2048, 658.5),
            ("BEWAL", "solar", 2024, 2049, 586.9),
        ]
    )
    reconcile_baseyear_forced_build(df, agg, 2025, GROUPS)
    forced = df.loc[df["DateIn"] >= 2021, "Capacity"].sum()
    # headroom = 2668 - (516.1 + 1770) = 381.9 against 1802.2 of forced build
    assert forced == pytest.approx(381.9, abs=0.2)
    # standing untouched
    assert df.loc[df["DateIn"] < 2021, "Capacity"].sum() == pytest.approx(
        2286.1
    )


def test_dropped_when_standing_covers_the_pin(tmp_path):
    agg = _agg(tmp_path, {("BEWAL", "onwind"): (1560.0, 1560.0)})
    df = _dfagg(
        [
            ("BEWAL", "onwind", 2010, 2035, 1000.0),
            ("BEWAL", "onwind", 2015, 2040, 694.0),
            ("BEWAL", "onwind", 2023, 2048, 655.0),
        ]
    )
    reconcile_baseyear_forced_build(df, agg, 2025, GROUPS)
    assert (df["DateIn"] >= 2021).sum() == 0
    assert df["Capacity"].sum() == pytest.approx(1694.0)


def test_no_pin_no_touch(tmp_path):
    agg = _agg(tmp_path, {("FR", "solar-all"): (21521.0, 21521.0)})
    df = _dfagg(
        [("DE", "solar", 2020, 2045, 50000.0), ("DE", "solar", 2024, 2049, 38160.0)]
    )
    before = df["Capacity"].sum()
    reconcile_baseyear_forced_build(df, agg, 2025, GROUPS)
    assert df["Capacity"].sum() == pytest.approx(before)


def test_open_corridor_no_touch(tmp_path):
    agg = _agg(tmp_path, {("BEWAL", "solar-all"): (2000.0, 9000.0)})
    df = _dfagg(
        [("BEWAL", "solar", 2020, 2045, 2286.0), ("BEWAL", "solar", 2024, 2049, 1802.2)]
    )
    before = df["Capacity"].sum()
    reconcile_baseyear_forced_build(df, agg, 2025, GROUPS)
    assert df["Capacity"].sum() == pytest.approx(before)


def test_standing_untouched_without_the_flag(tmp_path):
    """F7 default: the standing overshoot is warned about, not rewritten."""
    agg = _agg(tmp_path, {("BEWAL", "onwind"): (1560.0, 1560.0)})
    df = _dfagg(
        [
            ("BEWAL", "onwind", 2010, 2035, 1000.0),
            ("BEWAL", "onwind", 2015, 2040, 694.3),
            ("BEWAL", "onwind", 2023, 2048, 655.0),
        ]
    )
    reconcile_baseyear_forced_build(df, agg, 2025, GROUPS)
    assert df["Capacity"].sum() == pytest.approx(1694.3)


def test_standing_scaled_to_the_pin(tmp_path):
    """F7: the IRENASTAT land-potential split loses to the measured pin."""
    agg = _agg(tmp_path, {("BEWAL", "onwind"): (1560.0, 1560.0)})
    df = _dfagg(
        [
            ("BEWAL", "onwind", 2005, 2030, 108.1),
            ("BEWAL", "onwind", 2010, 2035, 381.6),
            ("BEWAL", "onwind", 2015, 2040, 538.9),
            ("BEWAL", "onwind", 2020, 2045, 665.7),
            ("BEWAL", "onwind", 2023, 2048, 655.0),
        ]
    )
    reconcile_baseyear_forced_build(df, agg, 2025, GROUPS, scale_standing=True)
    # forced tranche gone, standing scaled to land exactly on the pin
    assert (df["DateIn"] >= 2021).sum() == 0
    assert df["Capacity"].sum() == pytest.approx(1560.0)
    # scaled pro rata, so the vintage mix is preserved
    assert df.loc[df["DateIn"] == 2005, "Capacity"].iloc[0] == pytest.approx(
        108.1 * 1560.0 / 1694.3, rel=1e-6
    )


def test_standing_under_the_pin_untouched_with_the_flag(tmp_path):
    """The flag only bites on an overshoot; headroom is left for the pin."""
    agg = _agg(tmp_path, {("BEWAL", "solar-all"): (2668.0, 2668.0)})
    df = _dfagg(
        [
            ("BEWAL", "solar", 2015, 2040, 516.1),
            ("BEWAL", "solar", 2020, 2045, 1770.0),
            ("BEWAL", "solar", 2023, 2048, 1802.2),
        ]
    )
    reconcile_baseyear_forced_build(df, agg, 2025, GROUPS, scale_standing=True)
    assert df.loc[df["DateIn"] < 2021, "Capacity"].sum() == pytest.approx(2286.1)
    assert df["Capacity"].sum() == pytest.approx(2668.0)


def test_standing_scaled_when_there_is_no_forced_tranche(tmp_path):
    """An overshoot with nothing to clip still reaches the pin."""
    agg = _agg(tmp_path, {("BEWAL", "onwind"): (1560.0, 1560.0)})
    df = _dfagg(
        [
            ("BEWAL", "onwind", 2010, 2035, 1000.0),
            ("BEWAL", "onwind", 2015, 2040, 694.3),
        ]
    )
    reconcile_baseyear_forced_build(df, agg, 2025, GROUPS, scale_standing=True)
    assert df["Capacity"].sum() == pytest.approx(1560.0)


def test_real_files_agree():
    pins = baseyear_pins(
        str(REPO / "data/walloon/agg_p_nom_minmax_demande_haute.csv"), 2025
    )
    assert pins[("BEWAL", "solar-all")] == pytest.approx(2668.0)
    assert pins[("BEWAL", "onwind")] == pytest.approx(1560.0)
