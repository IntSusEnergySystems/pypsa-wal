# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Aggregate capacity caps: master CSV → agg_p_nom_minmax_demande_haute.csv."""

from __future__ import annotations

import shutil
from pathlib import Path

from scripts.build_common_parameters import (
    AGG_FILE,
    collect_targets,
    load_master,
    patch_agg_p_nom,
    planning_horizons,
    _parse_agg_header,
)

# Trajectory authored in docs/nuclear-alignment-20260816.md (MW_e, total).
EXPECTED = {
    ("BEWAL", "nuclear-all", "min"): {2035: 1000, 2040: 1000, 2045: 1750, 2050: 3000},
    ("BEWAL", "nuclear-all", "max"): {2035: 1030, 2040: 1030, 2045: 1750, 2050: 3000},
    ("BE", "nuclear-all", "min"): {2035: 2000, 2040: 2000, 2045: 1750, 2050: 3000},
    ("BE", "nuclear-all", "max"): {2035: 2030, 2040: 2030, 2045: 1750, 2050: 3000},
}

# Walloon dispatchable-gas floor, technology-neutral over CCGT + CCGT CC. Unlike
# nuclear this one does anchor 2025/2030: the legacy gas fleet is well below it.
EXPECTED_GAS = {
    ("BEWAL", "CCGT-all", "min"): {2025: 1740, 2030: 1740, 2040: 1740, 2050: 1740},
}


def _cells(path: Path, country: str, carrier: str) -> dict[tuple[int, str], str]:
    lines = path.read_text().splitlines()
    columns = _parse_agg_header(lines)
    for line in lines[3:]:
        parts = line.split(",")
        if parts[:2] != [country, carrier]:
            continue
        out: dict[tuple[int, str], str] = {}
        for i, (year, bound) in enumerate(columns):
            val = parts[2 + i] if 2 + i < len(parts) else ""
            out[(int(year), bound)] = val
        return out
    raise AssertionError(f"no {country},{carrier} row in {path}")


def test_master_csv_anchors_match_alignment():
    targets = collect_targets(load_master(), "agg", planning_horizons(), nparts=3)
    assert set(targets) == set(EXPECTED) | set(EXPECTED_GAS)
    for key, anchors in EXPECTED.items():
        got = {int(y): v for y, v in targets[key].anchors.items()}
        assert got == anchors, key
        # hold-forward must not invent a 2025/2030 cap (legacy fleet, no CCL)
        assert 2025 not in targets[key].anchors
        assert 2030 not in targets[key].anchors


def test_walloon_gas_floor_is_technology_neutral():
    """The floor must sit on CCGT-all, not on unabated CCGT.

    A floor on `CCGT` alone forced 1 740 MW_e of unabated capacity into
    Wallonia at every horizon and left no room for `CCGT CC`, which the 2050
    run built in Germany (8 465 MW_e) and Brussels (1 116 MW_e) but not in
    Wallonia. `agg_ccgt` folds both carriers into `CCGT-all`, so the adequacy
    requirement no longer picks the technology.
    """
    targets = collect_targets(load_master(), "agg", planning_horizons(), nparts=3)
    for key, anchors in EXPECTED_GAS.items():
        assert key in targets, key
        got = {int(y): v for y, v in targets[key].anchors.items()}
        assert got == anchors, key
    assert ("BEWAL", "CCGT", "min") not in targets


def test_demande_haute_file_already_in_sync():
    patch = patch_agg_p_nom(load_master(), planning_horizons(), dry_run=True)
    assert patch.ok, patch.errors
    assert patch.changes == []
    assert patch.managed == len(EXPECTED) + len(EXPECTED_GAS)


def test_write_restores_scrambled_caps(tmp_path: Path):
    dest = tmp_path / "agg_p_nom_minmax_demande_haute.csv"
    shutil.copy(AGG_FILE, dest)

    lines = dest.read_text().splitlines()
    columns = _parse_agg_header(lines)
    idx_2050_max = next(
        i for i, (y, b) in enumerate(columns) if y == "2050" and b == "max"
    )
    for i, line in enumerate(lines):
        parts = line.split(",")
        if parts[:2] == ["BEWAL", "nuclear-all"]:
            parts[2 + idx_2050_max] = "9999"
            lines[i] = ",".join(parts)
    dest.write_text("\n".join(lines) + "\n")
    assert _cells(dest, "BEWAL", "nuclear-all")[(2050, "max")] == "9999"

    patch = patch_agg_p_nom(
        load_master(), planning_horizons(), dry_run=False, path=dest
    )
    assert patch.ok, patch.errors
    assert any("BEWAL nuclear-all 2050 max" in c and "3000" in c for c in patch.changes)

    bewal = _cells(dest, "BEWAL", "nuclear-all")
    be = _cells(dest, "BE", "nuclear-all")
    for year, bound in ((2035, "min"), (2040, "max"), (2045, "min"), (2050, "max")):
        assert float(bewal[(year, bound)]) == EXPECTED[("BEWAL", "nuclear-all", bound)][
            year
        ]
        assert float(be[(year, bound)]) == EXPECTED[("BE", "nuclear-all", bound)][year]
    # 2025/2030 must stay empty (not hold-forward from 2035)
    for year in (2025, 2030):
        assert bewal[(year, "min")] == ""
        assert bewal[(year, "max")] == ""
        assert be[(year, "min")] == ""
        assert be[(year, "max")] == ""
