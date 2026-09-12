# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""The Walloon biomass envelope: one domestic potential, one import cap.

Two rows described the same physical flow — imported pellets — with different
values, on different components, and only one of them under
`build_common_parameters`:

* `solid biomass import` / `e_nom` 4.0-6.0 TWh, managed by the master CSV,
  targeting a Store that `sector.solid_biomass_import.enable: false` never
  builds — so it applied to nothing;
* `solid biomass transported` / `e_sum_max` 2.0-3.0 TWh, exactly half, applied
  to the generator that does bind, and an *unmanaged* row invisible to the
  shared-parameter check.

TIMES imports no solid biomass at all in any horizon (`IMPBIOPEL` never
activates; Wallonia *exports* 3.33 TWh of pellets in 2025 and 1.97 TWh of chips
in 2030), so the cap that binds is the one to keep honest.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
POTENTIALS = ROOT / "data" / "walloon" / "custom_potentials.csv"
MASTER = ROOT / "config" / "input_parameters_for_models.csv"


def _rows(path, **match):
    with open(path, newline="", encoding="utf-8") as handle:
        return [r for r in csv.DictReader(handle)
                if all(r.get(k) == v for k, v in match.items())]


def test_the_icedd_domestic_potential_is_the_one_in_the_derived_file():
    """master 2f67b01e: 6000 -> 9222 GWh/an, every horizon.

    2026-09-08: 9222 -> 6222, on the reading that Valbiom's 9222 already
    included the imports `solid biomass transported` counts separately, so the
    domestic potential was 9222 - max(imports) = 9222 - 3000.

    2026-09-09 (`dc364b75`, "solving and documenting biomass infeasibility"):
    back to **9222**. The subtraction was withdrawn — see
    `docs/renewable-potentials.md` — and the double-count it was guarding
    against is now handled by the import cap itself, which ICEDD set to 0 for
    the central scenario in `4a4116aa`. With no imports there is nothing to
    subtract, and the two live values are consistent for the first time:
    domestic 9222, imported 0.

    `>=` on the year set, not `==`: the file also carries the 5-year grid's
    2035/2045 rows (`config/config.walloon_5y.yaml`), which a 10-year run ignores.
    """
    rows = _rows(POTENTIALS, bus="BEWAL", technology="solid biomass", parameter="p_nom")
    assert {r["year"] for r in rows} >= {"2025", "2030", "2040", "2050"}
    assert {r["value"] for r in rows} == {"9222"}


def test_the_import_cap_that_binds_is_managed_by_the_master_csv():
    managed = _rows(
        MASTER, pypsa_wal_target="potential:BEWAL:solid biomass transported:e_sum_max"
    )
    assert managed, "the only binding import cap must not be an unmanaged orphan"
    assert {r["status"] for r in managed} == {"active"}
    # ICEDD `4a4116aa` (2026-09-10): "pellet import for wallonia set to 0.0
    # according to the hypotheses for the 'central scenario' -> no solid biomass
    # imports". The trajectory this test used to pin (2000 / 2250 / 3000 GWh/a)
    # was the pre-central-scenario assumption. What still matters — and is what
    # this test exists for — is that the cap remains MANAGED by the master table
    # rather than drifting into an unmanaged file, so assert the shape and that
    # every horizon carries the same decided value.
    values = {float(r["value"]) for r in managed}
    assert len(values) == 1, (
        f"the import cap must be one decided trajectory, got {sorted(values)}"
    )
    assert values == {0.0}, (
        "central-scenario hypothesis is no solid biomass imports for Wallonia; "
        f"master CSV now says {sorted(values)}"
    )


def test_the_disabled_import_store_no_longer_claims_to_be_applied():
    """`sector.solid_biomass_import.enable` is false, so the row must not be active."""
    stale = _rows(MASTER, pypsa_wal_target="potential:BEWAL:solid biomass import:e_nom")
    assert not stale, "a target pointing at a component the config never builds"


def test_the_two_caps_are_not_both_live():
    """The whole defect was two caps on one flow. Exactly one may be active."""
    live = [
        r for r in _rows(MASTER)
        if r["pypsa_wal_target"].startswith("potential:BEWAL:solid biomass")
        and "transported" in r["pypsa_wal_target"] or
        r["pypsa_wal_target"] == "potential:BEWAL:solid biomass import:e_nom"
    ]
    targets = {r["pypsa_wal_target"] for r in live if r["status"] == "active"}
    assert targets == {"potential:BEWAL:solid biomass transported:e_sum_max"}
