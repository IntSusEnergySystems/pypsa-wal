# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Guards for the 5-year planning grid (``config/config.walloon_5y.yaml``).

Two things have to stay true at once, and they pull against each other:

* the overlay really does move the model onto
  ``[2025, 2030, 2035, 2040, 2045, 2050]``, with every horizon-keyed config key
  and every managed input file covering the two new horizons; and
* the shipped 10-year grid is **untouched** — same horizons, same
  ``budget_national``, same results prefix, same values in every artefact.

The second is the easy one to break: adding 2035/2045 rows to a shared data file
must stay inert for a run that does not solve those years. See
``docs/five_year_periods.md``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

import scripts.build_common_parameters as bcp

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / "config" / "config.default.yaml"
BASE = ROOT / "config" / "config.walloon.yaml"
OVERLAY = ROOT / "config" / "config.walloon_5y.yaml"

H10 = (2025, 2030, 2040, 2050)
H5 = (2025, 2030, 2035, 2040, 2045, 2050)
NEW = (2035, 2045)


@pytest.fixture(scope="module")
def base_cfg() -> dict:
    return yaml.safe_load(BASE.read_text())


@pytest.fixture(scope="module")
def merged_cfg() -> dict:
    cfg = yaml.safe_load(BASE.read_text())
    bcp._deep_update(cfg, yaml.safe_load(OVERLAY.read_text()))
    return cfg


@pytest.fixture(scope="module")
def full_cfg() -> dict:
    """What snakemake actually runs: defaults, then the config, then the overlay."""
    cfg: dict = {}
    for path in (DEFAULTS, BASE, OVERLAY):
        bcp._deep_update(cfg, yaml.safe_load(path.read_text()))
    return cfg


# --------------------------------------------------------------------------- #
# the 10-year grid must not move
# --------------------------------------------------------------------------- #
def test_base_config_still_ten_year(base_cfg):
    """The shipped config keeps its four horizons — the overlay is opt-in."""
    assert tuple(base_cfg["scenario"]["planning_horizons"]) == H10
    assert sorted(base_cfg["budget_national"]) == list(H10)
    assert base_cfg["run"]["prefix"] == "walloon"


def test_overlay_does_not_write_into_the_base_config():
    """`--config base overlay` patches budget_national into the overlay only."""
    bcp.ACTIVE_CONFIGS = (BASE, OVERLAY)
    try:
        assert bcp.budget_config() == OVERLAY
        assert bcp.cost_config_files() == (BASE,)
    finally:
        bcp.ACTIVE_CONFIGS = (bcp.WALLOON_CONFIG,)


def test_out_of_horizon_rows_are_inert_for_the_ten_year_run():
    """The 2035/2045 rows must not make the shipped grid fail or change a value."""
    patch = bcp.patch_potentials(bcp.load_master(), H10, dry_run=True)
    assert patch.errors == [], patch.errors
    assert patch.changes == [], patch.changes
    # 28 managed rows (14 groups) are skipped as out-of-horizon; the other 12
    # (6 unmanaged groups: co2/gas storage, process emissions, biomass import)
    # never reach that branch — they are reported as unmanaged first.
    out_of_horizon = [n for n in patch.notes if "outside this run's horizons" in n]
    assert len(out_of_horizon) == 28, out_of_horizon
    touched = [n for n in patch.notes if "@2035" in n or "@2045" in n]
    assert len(touched) == 40, f"expected all 40 new rows accounted for, got {len(touched)}"


def test_a_year_no_config_solves_is_still_an_error(tmp_path, monkeypatch):
    """Tolerating 2035/2045 must not tolerate a typo.

    `--check` prints notes only under `-v`, so if every out-of-horizon row were
    demoted to a note, a stray `2036` would pass the check in silence.
    """
    rows = pd.read_csv(bcp.POTENTIALS_FILE)
    typo = rows[(rows["technology"] == "onwind") & (rows["year"] == 2040)].copy()
    typo["year"] = 2036
    bad = tmp_path / "custom_potentials.csv"
    pd.concat([rows, typo]).to_csv(bad, index=False)

    monkeypatch.setattr(bcp, "POTENTIALS_FILE", bad)
    patch = bcp.patch_potentials(bcp.load_master(), H10, dry_run=True)
    assert any("2036" in e for e in patch.errors), patch.errors


# --------------------------------------------------------------------------- #
# the 5-year grid must be complete
# --------------------------------------------------------------------------- #
def test_overlay_selects_six_horizons(merged_cfg):
    assert tuple(merged_cfg["scenario"]["planning_horizons"]) == H5


def test_overlay_uses_a_separate_results_tree(merged_cfg):
    """Networks are named base_s_adm___<year>.nc, so the trees must not collide."""
    assert merged_cfg["run"]["prefix"] == "walloon_5y"


def test_grouping_years_power_covers_2045(merged_cfg):
    """Without 2045 a vintage built then is binned into a neighbouring group."""
    groups = merged_cfg["existing_capacities"]["grouping_years_power"]
    assert set(H5).issubset(groups)
    assert groups == sorted(groups)


def test_every_horizon_keyed_config_key_covers_the_new_horizons(full_cfg):
    """A horizon a dict does not list silently inherits the PyPSA-Eur default.

    ``update_config`` merges key by key, so a missing 2035 is not an error — it
    is a value quietly reverting to upstream. This walks the **fully merged**
    config, defaults included, because that is what actually runs: three keys
    would otherwise have inherited upstream values at 2035/2045 rather than
    being absent, which no "is the key present?" check can see.
    """
    gaps: list[str] = []

    def walk(node, path=""):
        if isinstance(node, dict):
            years = {k for k in node if isinstance(k, int) and 1990 < k < 2101}
            # only dicts that are actually keyed on planning horizons
            if len(years) >= 2 and years & set(H10):
                missing = [h for h in H5 if h not in years]
                # 2025 is the base year: transmission_limit_myopic legitimately
                # starts at 2030 in both grids.
                missing = [h for h in missing if not (h == 2025 and 2030 in years)]
                if missing:
                    gaps.append(f"{path or '<root>'} missing {missing}")
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(full_cfg)
    assert not gaps, "horizon-keyed config keys with no 2035/2045:\n  " + "\n  ".join(gaps)


#: Keys where `config.default.yaml` itself carries a 2035/2045 entry, so the gap
#: walk above cannot see them: the horizon is *present*, it just holds the
#: upstream value instead of the Walloon one. Each entry is
#: ``path -> (what upstream would leak, what the overlay must produce)``.
SILENT_INHERITANCE = {
    "co2_budget": ({2035: 0.25, 2045: 0.05}, {2035: 0.350, 2045: 0.150}),
    "electricity.transmission_limit_myopic": (
        {2035: "v1.05", 2045: "v1.05"}, {2035: "vopt", 2045: "vopt"},
    ),
    "sector.land_transport_electric_share": (
        {2035: 0.45, 2045: 0.85}, {2035: 0.58, 2045: 0.905},
    ),
    "sector.land_transport_ice_share": (
        {2035: 0.55, 2045: 0.15}, {2035: 0.42, 2045: 0.095},
    ),
}


def _dig(cfg: dict, path: str):
    for part in path.split("."):
        cfg = cfg[part]
    return cfg


@pytest.mark.parametrize("path", sorted(SILENT_INHERITANCE))
def test_does_not_inherit_the_pypsa_eur_default_at_the_new_horizons(path):
    """The sharpest edge of the whole 5-year change.

    `config.default.yaml` ships these keys with entries for all seven of its own
    horizons, and snakemake merges dicts key by key — so `config.walloon.yaml`'s
    four entries do *not* replace them, they merge into them. A six-horizon run
    without the overlay would silently run on the **upstream** value at 2035 and
    2045, with nothing in the config or the logs to say so:

    * `co2_budget` 0.25 / 0.05 — *tighter* than the Walloon 0.35 / 0.15, and in
      disagreement with `budget_national`;
    * `transmission_limit_myopic` `v1.05` — the Walloon config deliberately uses
      `vopt`, because a volume cap made every branch non-extendable and left the
      2050 solve carrying 12.3 bn EUR/a of congestion rent;
    * the two land-transport shares — a slower EV adoption path than Wallonia's.

    Asserting the leak as well as the fix means this fails if upstream ever
    changes its defaults, rather than silently agreeing with them.
    """
    leak, want = SILENT_INHERITANCE[path]

    without = yaml.safe_load(DEFAULTS.read_text())
    bcp._deep_update(without, yaml.safe_load(BASE.read_text()))
    got_leak = {y: _dig(without, path)[y] for y in NEW}
    assert got_leak == leak, (
        f"upstream default for {path} changed; re-derive the overlay", got_leak
    )

    with_overlay = dict(without)
    bcp._deep_update(with_overlay, yaml.safe_load(OVERLAY.read_text()))
    got = {y: _dig(with_overlay, path)[y] for y in NEW}
    assert got == pytest.approx(want), path


def test_the_two_co2_trajectories_agree():
    """`co2_budget` and `budget_national` must not tell the solver two stories."""
    full = yaml.safe_load(DEFAULTS.read_text())
    for path in (BASE, OVERLAY):
        bcp._deep_update(full, yaml.safe_load(path.read_text()))
    for year in NEW:
        assert set(full["budget_national"][year].values()) == {full["co2_budget"][year]}, year


def test_land_transport_shares_still_sum_to_one():
    """The overlay interpolates both halves; they have to remain complementary."""
    full = yaml.safe_load(DEFAULTS.read_text())
    for path in (BASE, OVERLAY):
        bcp._deep_update(full, yaml.safe_load(path.read_text()))
    for year in H5:
        total = (full["sector"]["land_transport_electric_share"][year]
                 + full["sector"]["land_transport_ice_share"][year])
        assert total == pytest.approx(1.0), (year, total)


def test_potentials_cover_every_five_year_horizon():
    """BEWAL_potentials.py matches the year exactly — a gap is a silent default."""
    patch = bcp.patch_potentials(bcp.load_master(), H5, dry_run=True)
    assert patch.errors == [], patch.errors
    assert patch.changes == [], "custom_potentials.csv out of sync: " + str(patch.changes)


def test_every_per_horizon_potential_group_has_the_new_rows():
    """Unmanaged groups too — `--check` cannot see those, so pin them here."""
    df = pd.read_csv(ROOT / "data" / "walloon" / "custom_potentials.csv")
    df["bus"] = df["bus"].fillna("BEWAL")
    incomplete = []
    for key, grp in df.groupby(["bus", "technology", "parameter"]):
        years = set(grp["year"].astype(int))
        # single-year rows (waste heat, deep geothermal) are not per-horizon
        if not set(H10).issubset(years):
            continue
        if missing := sorted(set(H5) - years):
            incomplete.append(f"{'/'.join(key)} missing {missing}")
    assert not incomplete, "\n  ".join(incomplete)


def test_ntc_and_agg_files_exist_for_the_new_horizons():
    for year in NEW:
        assert (ROOT / "data" / "walloon" / f"ntc_{year}.csv").is_file()
    agg = pd.read_csv(
        ROOT / "data" / "walloon" / "agg_p_nom_minmax_demande_haute.csv",
        header=[0, 1],
        index_col=[0, 1],
    )
    have = {str(c[0]) for c in agg.columns}
    assert {str(y) for y in NEW}.issubset(have), have


@pytest.mark.parametrize("target,expected", [
    ("potential:BEWAL:biogas:p_nom", {2035: 6150.0, 2045: 5450.0}),
    ("potential:BEWAL:solid biomass transported:e_sum_max", {2035: 2125.0, 2045: 2625.0}),
])
def test_interpolated_trajectories(target, expected):
    """The two modeller's calls of docs/five_year_periods.md S1, and their rule.

    `year_rule: interp` reproduces them from the existing anchors, which is why
    no extra rows were added to the ICEDD-shared master CSV. The 10-year values
    are anchors, so they are unchanged by the rule.
    """
    key = tuple(target.split(":")[1:])
    df = bcp.load_master()

    five = bcp.collect_targets(df, "potential", H5, nparts=3)[key]
    assert five.year_rule == "interp"
    for year, value in expected.items():
        assert five.values[year] == pytest.approx(value)

    ten = bcp.collect_targets(df, "potential", H10, nparts=3)[key]
    assert ten.values == {h: five.values[h] for h in H10}


def test_process_emissions_match_the_times_extraction():
    """2035/2045 are published in docs/ccs_alignment.md, not a modeller's guess."""
    df = pd.read_csv(ROOT / "data" / "walloon" / "custom_potentials.csv")
    rows = df[(df["technology"] == "process emissions") & (df["parameter"] == "p_set")]
    got = dict(zip(rows["year"].astype(int), rows["value"].astype(float)))
    assert got[2035] == pytest.approx(5329.0)
    assert got[2045] == pytest.approx(5447.5)
