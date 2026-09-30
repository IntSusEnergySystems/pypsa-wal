# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Neighbouring countries' nuclear follows their national plans.

Until 2026-09-30 the caps file carried `legacy-unreviewed` foreign nuclear rows
in the MIN columns (FR >= 61 761 MW in 2030 and 62 907 MW from 2040, GB >=
13 236 MW from 2040). `add_CCL_constraints` only adds a floor for a group with
extendable links, so they were inert when the 10 MW cleanup deleted the
`nuclear-2025` options (24 Sep) and forced a 49 GW French "rebuild" by 2030 as
soon as the options survived (15 and 29 Sep). The model's own French fleet
retires on 38-41-year lifetimes (13 GW left in 2030, 0 in 2050), so a floor is
needed: the corridor pins each neighbour to its plan, 2025 being a cap only.

Sources and the per-cell reasoning are on the rows of
config/input_parameters_for_models.csv; the summary is in
docs/logs/2026-09-30_cabinet_batch_20260930_2010_1h.md §3.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
WAL = ROOT / "data" / "walloon"
CENTRAL = WAL / "agg_p_nom_minmax_demande_haute.csv"
YEARS = (2025, 2030, 2035, 2040, 2045, 2050)

# MW_e, total incl. the standing fleet. 2025: (min, max) = (0, real fleet).
PLAN = {
    "FR": {2025: (0, 62900), 2030: 62900, 2035: 62900, 2040: 66000, 2045: 55000, 2050: 54000},
    "GB": {2025: (0, 5900), 2030: 2800, 2035: 4500, 2040: 9100, 2045: 11500, 2050: 14000},
    "NL": {2025: (0, 485), 2030: 485, 2035: 485, 2040: 2100, 2045: 3700, 2050: 7000},
    "DE": {y: (None, 0) for y in YEARS},
    "LU": {y: (None, 0) for y in YEARS},
}


def _corridor(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=[0, 1], header=[0, 1])
    return df


def _bounds(df: pd.DataFrame, country: str, year: int) -> tuple[float | None, float | None]:
    row = df.loc[(country, "nuclear-all")]
    lo, hi = row[(str(year), "min")], row[(str(year), "max")]
    return (None if pd.isna(lo) else float(lo), None if pd.isna(hi) else float(hi))


@pytest.mark.parametrize("country", sorted(PLAN))
@pytest.mark.parametrize("year", YEARS)
def test_central_corridor_is_the_plan(country, year):
    want = PLAN[country][year]
    if not isinstance(want, tuple):
        want = (want, want)
    got = _bounds(_corridor(CENTRAL), country, year)
    assert got == tuple(None if w is None else float(w) for w in want), (country, year, got)


@pytest.mark.parametrize("country", sorted(PLAN))
def test_rows_are_tagged_and_widened(country):
    df = _corridor(CENTRAL)
    row = df.loc[(country, "nuclear-all")]
    assert row[("source", "tag")] == "national-plans-2026-09"
    # A min = max pin needs a tolerance, or widen_collapsed_corridors leaves an
    # exact equality for the barrier to hit (docs/renewable-potentials.md).
    assert float(row[("tolerance", "rel")]) == pytest.approx(0.01)


@pytest.mark.parametrize(
    "path", sorted(WAL.glob("agg_p_nom_minmax_scen_*.csv")), ids=lambda p: p.stem
)
def test_every_scenario_copy_has_the_same_neighbours(path):
    """Neighbours are an exogenous assumption: no sensitivity may move them."""
    central, copy = _corridor(CENTRAL), _corridor(path)
    for country in PLAN:
        pd.testing.assert_series_equal(
            central.loc[(country, "nuclear-all")], copy.loc[(country, "nuclear-all")],
            check_names=False,
        )


@pytest.mark.parametrize("country", ["FR", "GB", "NL"])
def test_the_2025_base_year_has_no_floor(country):
    """2025 stays as calibrated: a cap at the real fleet, never a forced build."""
    lo, hi = _bounds(_corridor(CENTRAL), country, 2025)
    assert lo in (None, 0.0) and hi is not None and hi > 0
