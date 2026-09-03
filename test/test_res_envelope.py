# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""The stored renewable overrides must match the documented design.

``docs/renewable-potentials.md`` keeps stored overrides to a minimum: the CSV
carries the pinned 2025 base year and the 2030 corridor floor, and nothing else.
Ceilings are computed at solve time as ``min(land potential, growth allowance)``.

Two production failures motivate the invariants:

* 2026-08-26, 2050 horizon **infeasible** — an ``agg_p_nom_min`` above the
  reachable ``p_nom_max`` is an empty LP.
* 2026-08-26, ``review_run.py`` FAIL — a 2025 cap below the capacity the model
  already had standing.

A stored maximum after 2025 is the new failure mode this guards: it would
silently override the computed ceiling.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.walloon_scripts.check_res_envelope import (
    BASE_YEAR,
    CORRIDOR_YEAR,
    check,
    expected_groups,
    load_envelope,
)

ROOT = Path(__file__).resolve().parents[1]
AGG_FILES = sorted((ROOT / "data" / "walloon").glob("agg_p_nom_minmax_*.csv"))
# scenarios converted to the documented design; `_sensitivity` keys Belgium per
# region instead of parent+region and has not been converted
CONVERTED = [
    p for p in AGG_FILES
    if p.stem.rsplit("_", 1)[-1] in {"demande_haute", "base", "corrige"}
]
RATES = ROOT / "data" / "walloon" / "res_build_rates.csv"


def _rates():
    return pd.read_csv(RATES, comment="#") if RATES.exists() else None


def test_there_are_scenario_files_to_check():
    assert AGG_FILES, "no agg_p_nom_minmax_*.csv found"
    assert CONVERTED, "no converted scenario files found"


def test_build_rate_table_exists_and_is_populated():
    """Without it no growth limit is applied and 2040/2050 are unbounded."""
    assert RATES.exists(), f"{RATES} missing — run build_res_build_rates.py"
    df = _rates()
    assert not df.empty
    assert (df.record_annual_MW > 0).all(), "a zero rate would freeze that group"


@pytest.mark.parametrize("path", CONVERTED, ids=lambda p: p.stem)
def test_matches_the_documented_design(path: Path):
    """2025 pinned, 2030 floor present, no stored ceilings after 2025."""
    errors = check(load_envelope(path), _rates())
    assert not errors, f"{path.name}:\n" + "\n".join(f"  - {e}" for e in errors)


@pytest.mark.parametrize("path", CONVERTED, ids=lambda p: p.stem)
def test_every_modelled_group_is_covered(path: Path):
    """A group with no row at all gets no cap and no floor."""
    env = load_envelope(path)
    present = set(zip(env.country, env.carrier))
    missing = sorted(expected_groups() - present)
    assert not missing, f"{path.name}: no rows for " + ", ".join(f"{a}/{b}" for a, b in missing)


def _csv(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(
        ",,2025,2025,2030,2030,2050,2050\n"
        ",,min,max,min,max,min,max\n"
        "country,carrier,,,,,,\n" + body
    )
    return p


def test_rejects_an_inverted_bound(tmp_path):
    """Guards that cannot fail are not guards."""
    bad = _csv(tmp_path, "inv.csv", "DE,onwind,900,500,,,,\n")
    assert any("empty LP" in e for e in check(load_envelope(bad)))


def test_rejects_an_unpinned_base_year(tmp_path):
    bad = _csv(tmp_path, "unpinned.csv", "DE,onwind,100,900,115000,,,\n")
    assert any("calibration" in e for e in check(load_envelope(bad)))


def test_rejects_a_stored_ceiling_after_the_base_year(tmp_path):
    """The new failure mode: a stale max would override the computed ceiling."""
    bad = _csv(tmp_path, "stale.csv", "DE,onwind,100,100,115000,180000,,\n")
    assert any("ceiling is computed" in e for e in check(load_envelope(bad)))


def test_pez_retime_allows_a_2030_pin_and_later_floors(tmp_path):
    """Item 11: BE offwind-all is the one group allowed to pin 2030 and floor 2040+."""
    good = _csv(
        tmp_path,
        "pez.csv",
        "BE,offwind-all,2262,2262,2262,2262,5800,\n"
        "DE,onwind,100,100,115000,,,\n",
    )
    # Need a 2025 pin + 2030 min for DE; the extra 2050 min on BE is the PEZ floor.
    # The helper CSV only has 2025/2030/2050 columns — 2050 min=5800 is the later floor.
    errors = check(load_envelope(good))
    assert not any("BE/offwind-all" in e for e in errors)


def test_pez_2030_pin_must_be_min_eq_max(tmp_path):
    """A 2030 stored max on BE offwind-all is only legal as a pin."""
    bad = _csv(
        tmp_path,
        "pez_unequal.csv",
        "BE,offwind-all,2262,2262,2262,5800,,\n",
    )
    assert any("PEZ 2030 pin" in e for e in check(load_envelope(bad)))


def test_rejects_a_policy_floor_past_the_corridor(tmp_path):
    bad = _csv(tmp_path, "floor.csv", "DE,onwind,100,100,115000,,150000,\n")
    assert any("techno-economic optimum" in e for e in check(load_envelope(bad)))


def test_rejects_a_group_missing_from_the_rate_table(tmp_path):
    bad = _csv(tmp_path, "norate.csv", "DE,onwind,100,100,115000,,,\n")
    rates = pd.DataFrame({"node": ["FR"], "carrier": ["onwind"], "record_annual_MW": [1.0]})
    assert any("build-rate table" in e for e in check(load_envelope(bad), rates))


def test_be_offwind_2030_is_the_standing_fleet():
    """Item 11: no new Belgian offshore before 2030, so 2030 pins the fleet.

    The press review is unambiguous — PEZ-1 tender withdrawn Jul 2025, island
    operational 1 Oct 2031 — so 2030 is `min = max = 2262`, the 2024 standing
    fleet. The 8 GW pin this replaces was a work-around for the carrier-blind
    CCL rewrite (B1/B2), which let 2025 build the whole technical potential.
    """
    path = ROOT / "data" / "walloon" / "agg_p_nom_minmax_demande_haute.csv"
    env = load_envelope(path)
    row = env[
        (env.country == "BE") & (env.carrier == "offwind-all") & (env.year == 2030)
    ]
    assert len(row) == 1
    assert float(row.iloc[0]["min"]) == 2262
    assert float(row.iloc[0]["max"]) == 2262


def test_no_hand_split_bevlg_res_rows():
    """The Elia targets are Belgian; the CCL splits them, not the caps file.

    `BEVLG,solar-all` 10 000 and `BEVLG,onwind` 2 000 were arithmetic done by
    hand (BE minus BEWAL) to stop the remainder landing on Brussels. With
    `add_CCL_constraints` grouping per (region, carrier) the `BE` row covers
    BEVLG and BEBRU together again, so those rows have to go — otherwise the
    national target is silently re-split every time Elia updates it.
    """
    path = ROOT / "data" / "walloon" / "agg_p_nom_minmax_demande_haute.csv"
    env = load_envelope(path)
    for carrier in ("solar-all", "onwind", "offwind-all"):
        rows = env[(env.country == "BEVLG") & (env.carrier == carrier)]
        assert rows.empty, (
            f"BEVLG/{carrier} is a hand-computed split of the BE row; the CCL "
            "does that arithmetic itself now (B1/B2)"
        )


def test_base_and_corridor_years_are_what_the_doc_says():
    assert (BASE_YEAR, CORRIDOR_YEAR) == (2025, 2030)
