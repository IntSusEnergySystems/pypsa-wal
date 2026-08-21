# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""Tests for TIMES↔PyPSA hurdle-rate / discount-rate harmonisation.

Covers the guarantees in docs/discount-rates.md (T1–T21): mapping
completeness, master-CSV rates, generated discount_rates.csv sync, resolution
fallback/override rules, and prepare_costs() downstream behaviour.
"""

from __future__ import annotations

import copy
import difflib
import inspect
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest
import yaml
from snakemake.utils import update_config

import scripts.build_common_parameters as bcp
from scripts.add_electricity import calculate_annuity
from scripts.build_common_parameters import (
    DISCOUNT_RATES_FILE,
    HURDLE_MAPPING_FILE,
    HURDLE_SECTORS,
    cmd_check,
    collect_targets,
    cost_table_technologies,
    expand_years,
    hurdle_variants,
    load_master,
    load_meta,
    patch_discount_rates,
    planning_horizons,
    pypsa_default_discount_rate,
    resolve_hurdle_rates,
    variant_path,
)
from scripts.lib.validation.config.costs import CostsConfig
from scripts.process_cost_data import prepare_costs

ROOT = Path(__file__).resolve().parents[1]

# Documented inert set (8 storage aggregates + solar + waste clones).
NONE_TECHNOLOGIES = {
    "solar",
    "waste",
    "battery",
    "li-ion",
    "lfp",
    "vanadium",
    "lair",
    "pair",
    "iron-air",
    "H2",
}

STORAGE_AGGREGATES = {
    "battery",
    "li-ion",
    "lfp",
    "vanadium",
    "lair",
    "pair",
    "iron-air",
    "H2",
}

ARCHIVE_COSTS = ROOT / "data" / "costs" / "archive" / "v0.14.0" / "costs_2050.csv"
CUSTOM_COSTS = ROOT / "data" / "walloon" / "custom_costs.csv"
CONFIG_FILES = (
    ROOT / "config" / "config.walloon.yaml",
    ROOT / "config" / "config.times-pypsa.yaml",
)


@pytest.fixture
def repo_tmp_path():
    """Temp directory under the repo so Path.relative_to(ROOT) succeeds.

    ``patch_discount_rates`` builds error messages with
    ``path.relative_to(ROOT)``, so pytest's default ``tmp_path`` (under
    ``/tmp``) cannot host mapping / generated-rate fixtures.
    """
    base = ROOT / "test" / ".tmp"
    base.mkdir(exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix="discount_", dir=base))
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _costs_config() -> dict:
    """Merged default+walloon costs block (deep-merged fill_values)."""
    default = yaml.safe_load((ROOT / "config" / "config.default.yaml").read_text())
    walloon = yaml.safe_load((ROOT / "config" / "config.walloon.yaml").read_text())
    cfg = copy.deepcopy(default["costs"])
    update_config(cfg, walloon["costs"])
    return cfg


def _max_hours() -> dict:
    default = yaml.safe_load((ROOT / "config" / "config.default.yaml").read_text())
    return dict(default["electricity"]["max_hours"])


def _prepare_archive_costs(hurdle_rate_fn: Path | str | None = DISCOUNT_RATES_FILE):
    """Run prepare_costs() on the pinned v0.14.0 archive + Walloon custom costs."""
    costs = pd.read_csv(ARCHIVE_COSTS, index_col=["technology", "parameter"])
    return prepare_costs(
        costs,
        _costs_config(),
        max_hours=_max_hours(),
        nyears=1.0,
        custom_costs_fn=str(CUSTOM_COSTS),
        planning_horizon="2050",
        hurdle_rate_fn=None if hurdle_rate_fn is None else str(hurdle_rate_fn),
    )


def _master_fallback_rate() -> float:
    """PyPSA default fill — the fallback for unmapped technologies."""
    return pypsa_default_discount_rate()


# --------------------------------------------------------------------------- #
# Completeness
# --------------------------------------------------------------------------- #


def test_universe_matches_processed_costs():
    """T1: cost_table_technologies() matches every processed costs CSV index."""
    processed = sorted(ROOT.glob("resources/**/costs_*_processed.csv"))
    if not processed:
        pytest.skip("no resources/**/costs_*_processed.csv present")

    meta = load_meta()
    universe = cost_table_technologies(meta)
    for path in processed:
        index = set(pd.read_csv(path, index_col=0).index)
        if index != universe:
            only_csv = sorted(index - universe)
            only_fn = sorted(universe - index)
            pytest.fail(
                f"{path.relative_to(ROOT)} index disagrees with "
                f"cost_table_technologies(): "
                f"only in CSV={only_csv[:20]}{'…' if len(only_csv) > 20 else ''}; "
                f"only in universe={only_fn[:20]}{'…' if len(only_fn) > 20 else ''}. "
                "Keep cost_table_technologies() in sync with process_cost_data.py."
            )


def test_every_technology_is_mapped():
    """T2: every cost-table technology has a hurdle_rate_mapping.csv row."""
    meta = load_meta()
    universe = cost_table_technologies(meta)
    mapping = set(
        pd.read_csv(HURDLE_MAPPING_FILE, dtype=str, keep_default_na=False)["technology"]
    )
    missing = sorted(universe - mapping)
    if missing:
        pytest.fail(
            f"{len(missing)} technolog(ies) missing from "
            f"{HURDLE_MAPPING_FILE.relative_to(ROOT)}: {missing}. "
            "Add each with hurdle_sector in "
            f"{'|'.join(HURDLE_SECTORS)}|none, then run "
            "`python scripts/build_common_parameters.py --write`."
        )


def test_no_stale_mapping_rows():
    """T3: mapping has no rows for technologies outside the universe."""
    meta = load_meta()
    universe = cost_table_technologies(meta)
    mapping = set(
        pd.read_csv(HURDLE_MAPPING_FILE, dtype=str, keep_default_na=False)["technology"]
    )
    stale = sorted(mapping - universe)
    if stale:
        pytest.fail(
            f"{len(stale)} stale mapping row(s) in "
            f"{HURDLE_MAPPING_FILE.relative_to(ROOT)}: {stale}. "
            "Remove them, then run "
            "`python scripts/build_common_parameters.py --write`."
        )


def test_mapping_has_no_duplicates():
    """T4: technology column of the hurdle mapping is unique."""
    mapping = pd.read_csv(HURDLE_MAPPING_FILE, dtype=str, keep_default_na=False)
    dups = sorted(mapping.loc[mapping["technology"].duplicated(), "technology"].unique())
    if dups:
        pytest.fail(
            f"{HURDLE_MAPPING_FILE.relative_to(ROOT)} has duplicate technology "
            f"row(s): {dups}."
        )


def test_none_rows_are_justified():
    """T5: every none row has a note; the set equals the documented inert set."""
    mapping = pd.read_csv(HURDLE_MAPPING_FILE, dtype=str, keep_default_na=False)
    none_rows = mapping[mapping["hurdle_sector"] == "none"]
    blank_notes = sorted(
        none_rows.loc[none_rows["note"].str.strip() == "", "technology"]
    )
    if blank_notes:
        pytest.fail(
            f"hurdle_sector=none rows missing a note: {blank_notes}. "
            "Document why the rate is inert."
        )
    got = set(none_rows["technology"])
    if got != NONE_TECHNOLOGIES:
        pytest.fail(
            f"hurdle_sector=none set changed.\n"
            f"  unexpected: {sorted(got - NONE_TECHNOLOGIES)}\n"
            f"  missing:    {sorted(NONE_TECHNOLOGIES - got)}\n"
            "Update the mapping deliberately and adjust NONE_TECHNOLOGIES in "
            "test/test_discount_rates.py if the inert set really changed."
        )


# --------------------------------------------------------------------------- #
# Master CSV and rates
# --------------------------------------------------------------------------- #


def test_every_mapped_sector_has_a_rate():
    """T6: every sector used in the mapping has an active hurdle:<sector> row."""
    df = load_master()
    horizons = planning_horizons()
    mapping = pd.read_csv(HURDLE_MAPPING_FILE, dtype=str, keep_default_na=False)
    used = set(mapping["hurdle_sector"]) - {"none"}
    base = hurdle_variants(df, horizons)[None]
    missing = sorted(used - set(base))
    if missing:
        pytest.fail(
            f"mapping names hurdle_sector(s) with no active hurdle:<sector> "
            f"row in config/input_parameters_for_models.csv: {missing}. "
            "Add the rate row(s) with status=active."
        )
    for sector in HURDLE_SECTORS:
        if sector not in base:
            pytest.fail(
                f"missing active hurdle:{sector} row for planning horizons "
                f"{list(horizons)}."
            )


def test_rates_are_fractions():
    """T7: hurdle rates, SDR and PyPSA fallback are fractions 0 ≤ r < 0.30."""
    df = load_master()
    horizons = planning_horizons()
    act = df[df["status"] == "active"]
    targets = []
    for nparts in (1, 2):
        targets.extend(collect_targets(df, "hurdle", horizons, nparts=nparts).values())
    sdr = collect_targets(df, "config", horizons, nparts=1).get(
        ("costs.social_discountrate",)
    )
    if sdr is None:
        pytest.fail("missing active config:costs.social_discountrate row in master CSV.")
    targets.append(sdr)

    for tgt in targets:
        if tgt.unit != "per unit":
            pytest.fail(
                f"{tgt.label}: units={tgt.unit!r}, expected 'per unit'. "
                "Rates must be fractions (0.075), not percents (7.5)."
            )
        for y, r in tgt.values.items():
            if not (0.0 <= r < 0.30):
                pytest.fail(
                    f"{tgt.label} @ {y}: rate {r} outside 0 ≤ r < 0.30 "
                    "(did you mean a fraction, e.g. 0.075 not 7.5?)."
                )

    fb = pypsa_default_discount_rate()
    if not (0.0 <= fb < 0.30):
        pytest.fail(
            f"PyPSA default fill_values discount rate {fb} outside 0 ≤ r < 0.30."
        )

    rate_rows = act[act["parameter"] == "discount_rate"]
    bad = rate_rows[
        rate_rows["value"].notna()
        & ((rate_rows["value"] < 0) | (rate_rows["value"] >= 0.30))
    ]
    if len(bad):
        pytest.fail(
            "master CSV discount_rate row(s) outside 0 ≤ r < 0.30:\n"
            + bad[["pypsa_wal_target", "year", "value", "units"]].to_string()
        )


@pytest.mark.parametrize("config_path", CONFIG_FILES, ids=lambda p: p.name)
def test_configs_match_master_csv(config_path: Path):
    """T8: SDR synced from CSV; fill_values discount rate stays at PyPSA default."""
    df = load_master()
    horizons = planning_horizons()
    sdr = collect_targets(df, "config", horizons, nparts=1)[
        ("costs.social_discountrate",)
    ]
    sdr_v = float(next(iter(sdr.values.values())))
    fb_v = pypsa_default_discount_rate()

    cfg = yaml.safe_load(config_path.read_text())["costs"]
    if cfg.get("social_discountrate") != sdr_v:
        pytest.fail(
            f"{config_path.name}: costs.social_discountrate="
            f"{cfg.get('social_discountrate')} != master CSV {sdr_v}. "
            "Run `python scripts/build_common_parameters.py --write`."
        )
    # Walloon overlays must not override the PyPSA financial-rate fill.
    if "fill_values" in cfg and "discount rate" in (cfg.get("fill_values") or {}):
        got = cfg["fill_values"]["discount rate"]
        if float(got) != fb_v:
            pytest.fail(
                f"{config_path.name}: costs.fill_values.'discount rate'={got} "
                f"overrides the PyPSA default {fb_v}. Remove the override."
            )

    default = yaml.safe_load((ROOT / "config" / "config.default.yaml").read_text())
    merged = copy.deepcopy(default)
    update_config(merged, yaml.safe_load(config_path.read_text()))
    fill = merged["costs"]["fill_values"]
    for key in ("FOM", "VOM", "lifetime", "efficiency", "discount rate"):
        if key not in fill:
            pytest.fail(
                f"{config_path.name}: after snakemake update_config, fill_values "
                f"is missing {key!r} — partial override replaced the default "
                "block instead of deep-merging."
            )
    if fill["discount rate"] != fb_v:
        pytest.fail(
            f"{config_path.name}: merged fill_values.'discount rate'="
            f"{fill['discount rate']} != PyPSA default {fb_v}."
        )
    if merged["costs"]["social_discountrate"] != sdr_v:
        pytest.fail(
            f"{config_path.name}: merged social_discountrate="
            f"{merged['costs']['social_discountrate']} != master CSV {sdr_v}."
        )

    pydantic_costs = CostsConfig.model_validate(
        {"social_discountrate": sdr_v}
    )
    assert pydantic_costs.fill_values.discount_rate == fb_v
    assert pydantic_costs.social_discountrate == sdr_v


def test_no_discount_rate_in_custom_costs():
    """T9: custom_costs.csv must not carry a discount rate row (§10.4)."""
    costs = pd.read_csv(CUSTOM_COSTS, dtype=str, keep_default_na=False)
    hits = costs[costs["parameter"] == "discount rate"]
    if len(hits):
        pytest.fail(
            f"{CUSTOM_COSTS.relative_to(ROOT)} contains {len(hits)} "
            "'discount rate' row(s) — per-technology rates must live only in "
            "data/walloon/discount_rates.csv. Remove the custom_costs row(s)."
        )


@pytest.mark.parametrize(
    "variant",
    [None],  # extend when hurdle:<variant>:<sector> rows appear in the master CSV
    ids=["base"],
)
def test_generated_file_in_sync(variant, repo_tmp_path, monkeypatch):
    """T10: regenerating discount_rates.csv matches the committed file."""
    committed = variant_path(variant)
    assert committed.exists(), f"missing generated file {committed}"
    existing = committed.read_text()

    monkeypatch.setattr(bcp, "DISCOUNT_RATES_FILE", repo_tmp_path / "discount_rates.csv")
    patches = patch_discount_rates(
        load_master(), load_meta(), planning_horizons(), dry_run=False
    )
    hard = [e for p in patches for e in p.errors]
    if hard:
        pytest.fail(
            "patch_discount_rates hard-failed while regenerating:\n"
            + "\n".join(hard)
            + "\nRun `python scripts/build_common_parameters.py --check`."
        )

    generated_path = bcp.variant_path(variant)
    generated = generated_path.read_text()
    if existing != generated:
        diff = "".join(
            difflib.unified_diff(
                existing.splitlines(keepends=True),
                generated.splitlines(keepends=True),
                fromfile=f"{committed.relative_to(ROOT)} (committed)",
                tofile=f"{committed.relative_to(ROOT)} (generated)",
            )
        )
        print(f"\n{'=' * 80}\nDIFF: {committed}\n{'=' * 80}\n{diff}\n{'=' * 80}")
        pytest.fail(
            f"{committed.relative_to(ROOT)} is out of sync with the master CSV / "
            "mapping. Run `python scripts/build_common_parameters.py --write`. "
            "See diff above."
        )


def test_variants_cover_the_same_technologies():
    """T10b: every variant file covers exactly the same technology set as base."""
    df = load_master()
    horizons = planning_horizons()
    variants = hurdle_variants(df, horizons)
    base_techs = set(pd.read_csv(variant_path(None))["technology"])
    for variant in variants:
        path = variant_path(variant)
        if not path.exists():
            pytest.fail(
                f"missing variant file {path.relative_to(ROOT)}. "
                "Run `python scripts/build_common_parameters.py --write`."
            )
        techs = set(pd.read_csv(path)["technology"])
        if techs != base_techs:
            pytest.fail(
                f"{path.relative_to(ROOT)} technology set differs from base "
                f"discount_rates.csv.\n"
                f"  only in variant: {sorted(techs - base_techs)}\n"
                f"  only in base:    {sorted(base_techs - techs)}"
            )


def test_variant_inherits_unlisted_sectors():
    """T10c: a variant overriding one sector inherits the rest from the base."""
    df = load_master().copy()
    horizons = planning_horizons()
    # Synthetic variant: bump the ELC-PUB (power) sector only.
    template = df[df["pypsa_wal_target"] == "hurdle:power"].iloc[0].copy()
    template["pypsa_wal_target"] = "hurdle:highprod:power"
    template["value"] = 0.099
    template["status"] = "active"
    df = pd.concat([df, pd.DataFrame([template])], ignore_index=True)

    variants = hurdle_variants(df, horizons)
    assert None in variants and "highprod" in variants

    base = resolve_hurdle_rates(df, load_meta(), horizons, variants[None])
    high = resolve_hurdle_rates(df, load_meta(), horizons, variants["highprod"])

    # Power-mapped techs differ; others match.
    mapping = pd.read_csv(HURDLE_MAPPING_FILE, dtype=str, keep_default_na=False)
    power = set(mapping.loc[mapping["hurdle_sector"] == "power", "technology"])
    for tech, rates in base.rates.items():
        if tech in power:
            assert high.rates[tech] != rates
            assert all(abs(v - 0.099) < 1e-12 for v in high.rates[tech].values())
        else:
            assert high.rates[tech] == rates, tech


def test_scenario_hurdle_files_exist():
    """T10d: every costs.hurdle_rate_fn in configs/scenarios points at a real file."""
    paths: list[tuple[str, str]] = []
    for config_path in CONFIG_FILES:
        cfg = yaml.safe_load(config_path.read_text())
        fn = (cfg.get("costs") or {}).get("hurdle_rate_fn")
        if fn:
            paths.append((config_path.name, fn))

    scenarios = ROOT / "config" / "scenarios.walloon.yaml"
    if scenarios.exists():
        scen = yaml.safe_load(scenarios.read_text()) or {}
        for name, block in scen.items():
            if not isinstance(block, dict):
                continue
            fn = (block.get("costs") or {}).get("hurdle_rate_fn")
            if fn:
                paths.append((f"scenarios.walloon.yaml:{name}", fn))

    missing = [(src, fn) for src, fn in paths if not (ROOT / fn).exists()]
    if missing:
        pytest.fail(
            "costs.hurdle_rate_fn points at missing file(s):\n"
            + "\n".join(f"  - {src}: {fn}" for src, fn in missing)
            + "\nGenerate with `python scripts/build_common_parameters.py --write` "
            "or fix the path."
        )


# --------------------------------------------------------------------------- #
# Resolution logic
# --------------------------------------------------------------------------- #


def test_expected_rates_spot_check():
    """T11: prepare_costs() applies the agreed sector rates on the archive."""
    costs = _prepare_archive_costs()
    expected = {
        "onwind": 0.075,  # ELC-PUB
        "nuclear": 0.075,  # ELC-PUB
        "solar-rooftop": 0.075,  # ALL-PV, not RSD-processes
        "decentral CHP": 0.075,  # ALL-CHP, not RSD-processes
        "micro CHP": 0.075,  # ALL-CHP, not RSD-processes
        "central gas CHP": 0.075,  # ALL-CHP
        "Battery electric (passenger cars)": 0.075,  # TRA-processes
        "electrolysis": 0.075,  # SUP-processes
        "decentral air-sourced heat pump": 0.12,  # RSD-processes
        "industrial heat pump high temperature": 0.10,  # IND-process
        "electricity distribution grid": 0.075,  # ELC-PUB
    }
    bad = {
        tech: float(costs.at[tech, "discount rate"])
        for tech, rate in expected.items()
        if abs(float(costs.at[tech, "discount rate"]) - rate) > 1e-9
    }
    if bad:
        pytest.fail(
            "prepare_costs() discount rates disagree with the agreed mapping:\n"
            + "\n".join(
                f"  - {t}: got {got}, expected {expected[t]}" for t, got in bad.items()
            )
            + "\nCheck config/hurdle_rate_mapping.csv and "
            "`python scripts/build_common_parameters.py --write`."
        )


def test_pset_set_column_is_consistent():
    """T21: times_pset_set labels the sector one-to-one, and every group is used.

    The column is the audit trail back to the TIMES-WAL ``~TFM_INS`` table; a
    sector labelled with two different Pset_Sets (or an unlabelled non-``none``
    row) means the mapping and the TIMES table have drifted apart.
    """
    mapping = pd.read_csv(HURDLE_MAPPING_FILE, dtype=str, keep_default_na=False)
    if "times_pset_set" not in mapping.columns:
        pytest.fail(
            f"{HURDLE_MAPPING_FILE.relative_to(ROOT)} lost the times_pset_set "
            "column — it is the audit trail back to TIMES ~TFM_INS."
        )
    rated = mapping[mapping["hurdle_sector"] != "none"]
    blank = sorted(rated.loc[rated["times_pset_set"].str.strip() == "", "technology"])
    if blank:
        pytest.fail(f"rows with a sector but no times_pset_set: {blank}")
    ambiguous = {
        sector: sorted(g["times_pset_set"].unique())
        for sector, g in rated.groupby("hurdle_sector")
        if g["times_pset_set"].nunique() > 1
    }
    if ambiguous:
        pytest.fail(f"hurdle_sector mapped to several Pset_Sets: {ambiguous}")
    # The two config-only groups (RSD-RENO/COM-RENO) have no cost-table row;
    # every other sector must actually be used by at least one technology.
    config_only = {"residential_reno", "tertiary_reno"}
    # COM-processes and AGR-processes are deliberately empty — see D2/D4.
    empty_by_design = {"tertiary", "agriculture"}
    unused = set(HURDLE_SECTORS) - set(rated["hurdle_sector"])
    unexpected = unused - config_only - empty_by_design
    if unexpected:
        pytest.fail(
            f"hurdle sector(s) with no technology and no documented reason: "
            f"{sorted(unexpected)}."
        )


def test_unmapped_technology_gets_fallback(repo_tmp_path, monkeypatch):
    """T12: unmapped tech gets the fallback rate, soft-error, file still written."""
    df = load_master()
    meta = load_meta()
    horizons = planning_horizons()
    fallback = _master_fallback_rate()

    mapping = pd.read_csv(HURDLE_MAPPING_FILE, dtype=str, keep_default_na=False)
    assert "onwind" in set(mapping["technology"])
    mapping = mapping[mapping["technology"] != "onwind"]
    map_path = repo_tmp_path / "hurdle_rate_mapping.csv"
    mapping.to_csv(map_path, index=False)

    out_path = repo_tmp_path / "discount_rates.csv"
    out_path.write_text("SENTINEL\n")

    monkeypatch.setattr(bcp, "HURDLE_MAPPING_FILE", map_path)
    monkeypatch.setattr(bcp, "DISCOUNT_RATES_FILE", out_path)

    patches = patch_discount_rates(df, meta, horizons, dry_run=False)
    soft = [e for p in patches for e in p.soft_errors]
    hard = [e for p in patches for e in p.errors]
    if hard:
        pytest.fail(f"unexpected hard error(s): {hard}")
    if not soft or "onwind" not in "\n".join(soft):
        pytest.fail(
            "expected soft error naming unmapped 'onwind'; "
            f"got soft_errors={soft!r}."
        )
    # Soft errors make --write exit 1 while still writing.
    assert any(p.soft_errors for p in patches)

    text = out_path.read_text()
    if text == "SENTINEL\n":
        pytest.fail("discount_rates.csv was not written despite soft unmapped error.")
    rates = pd.read_csv(out_path)
    row = rates[rates["technology"] == "onwind"]
    if row.empty:
        pytest.fail("fallback row for onwind missing from written file.")
    assert abs(float(row.iloc[0]["value"]) - fallback) < 1e-9
    assert "fallback" in str(row.iloc[0]["further_description"]).lower()


def test_unknown_sector_is_hard_error(repo_tmp_path, monkeypatch):
    """T13: invalid hurdle_sector is a hard error; generated file unchanged."""
    df = load_master()
    meta = load_meta()
    horizons = planning_horizons()

    mapping = pd.read_csv(HURDLE_MAPPING_FILE, dtype=str, keep_default_na=False)
    mapping.loc[mapping["technology"] == "onwind", "hurdle_sector"] = "bogus"
    map_path = repo_tmp_path / "hurdle_rate_mapping.csv"
    mapping.to_csv(map_path, index=False)

    out_path = repo_tmp_path / "discount_rates.csv"
    sentinel = "SENTINEL-UNCHANGED\n"
    out_path.write_text(sentinel)

    monkeypatch.setattr(bcp, "HURDLE_MAPPING_FILE", map_path)
    monkeypatch.setattr(bcp, "DISCOUNT_RATES_FILE", out_path)

    patches = patch_discount_rates(df, meta, horizons, dry_run=False)
    hard = [e for p in patches for e in p.errors]
    if not hard or not any("bogus" in e for e in hard):
        pytest.fail(f"expected hard error mentioning 'bogus', got: {hard}")
    if out_path.read_text() != sentinel:
        pytest.fail(
            "discount_rates.csv was rewritten despite a hard unknown-sector error."
        )


def test_missing_fallback_row_is_hard_error(repo_tmp_path, monkeypatch):
    """T14: unreadable PyPSA default fill → hard error, nothing written."""
    bad_default = repo_tmp_path / "config.default.yaml"
    bad_default.write_text("costs:\n  fill_values: {}\n")
    monkeypatch.setattr(bcp, "DEFAULT_CONFIG", bad_default)

    out_path = repo_tmp_path / "discount_rates.csv"
    sentinel = "SENTINEL-UNCHANGED\n"
    out_path.write_text(sentinel)
    monkeypatch.setattr(bcp, "DISCOUNT_RATES_FILE", out_path)

    patches = patch_discount_rates(
        load_master(), load_meta(), planning_horizons(), dry_run=False
    )
    hard = [e for p in patches for e in p.errors]
    if not hard or not any(
        "fill_values" in e or "discount rate" in e or "fallback" in e.lower()
        for e in hard
    ):
        pytest.fail(
            f"expected hard error about missing PyPSA fill_values fallback, got: {hard}"
        )
    if out_path.read_text() != sentinel:
        pytest.fail("discount_rates.csv was written despite missing PyPSA fallback.")


def test_per_technology_override_wins():
    """T15: active cost:<tech>:discount rate beats the sector rate."""
    df = load_master().copy()
    horizons = planning_horizons()
    override = 0.042
    template = df[df["pypsa_wal_target"] == "hurdle:power"].iloc[0].copy()
    template["pypsa_wal_target"] = "cost:onwind:discount rate"
    template["parameter"] = "discount_rate"
    template["value"] = override
    template["year"] = float("nan")
    template["status"] = "active"
    template["data_origin_choice"] = "PyPSA"
    df = pd.concat([df, pd.DataFrame([template])], ignore_index=True)

    variants = hurdle_variants(df, horizons)
    resolution = resolve_hurdle_rates(df, load_meta(), horizons, variants[None])
    rates = resolution.rates["onwind"]
    if any(abs(v - override) > 1e-12 for v in rates.values()):
        pytest.fail(
            f"per-tech override lost: onwind rates={rates}, expected all {override}."
        )
    assert resolution.sectors["onwind"].startswith("override")


@pytest.mark.parametrize(
    "shape",
    ["yearless", "hold_forward"],
    ids=["yearless", "per-year-hold"],
)
def test_horizon_expansion(shape: str):
    """T16: yearless rows apply to all horizons; hold fills earlier years forward."""
    horizons = planning_horizons()
    assert horizons == (2025, 2030, 2040, 2050)

    if shape == "yearless":
        # collect_targets expands a NaN year to every horizon before expand_years.
        anchors = {h: 0.088 for h in horizons}
        got = expand_years("hold", anchors, horizons)
        assert got == {h: 0.088 for h in horizons}
    else:
        # Only a 2030 anchor: 2025 takes the first anchor; later years hold 2030.
        got = expand_years("hold", {2030: 0.091}, horizons)
        assert got[2025] == 0.091
        assert got[2030] == 0.091
        assert got[2040] == 0.091
        assert got[2050] == 0.091


# --------------------------------------------------------------------------- #
# Downstream behaviour
# --------------------------------------------------------------------------- #


def test_no_nan_discount_rate():
    """T17: after prepare_costs(), NaN discount rates only on storage aggregates."""
    costs = _prepare_archive_costs()
    nan_techs = set(costs.index[costs["discount rate"].isna()])
    if nan_techs != STORAGE_AGGREGATES:
        pytest.fail(
            "unexpected NaN discount rate set after prepare_costs().\n"
            f"  unexpected NaN: {sorted(nan_techs - STORAGE_AGGREGATES)}\n"
            f"  missing NaN:    {sorted(STORAGE_AGGREGATES - nan_techs)}\n"
            "Storage aggregates are created after the annuity and intentionally "
            "leave discount rate as NaN (§5.3)."
        )


def test_capital_cost_increases_with_rate():
    """T18: higher discount rate raises capital_cost for fixed lifetime/investment."""
    lifetime = 25.0
    investment = 1_000_000.0
    fom = 0.0
    low = (calculate_annuity(lifetime, 0.075) + fom / 100.0) * investment
    high = (calculate_annuity(lifetime, 0.12) + fom / 100.0) * investment
    if not (high > low):
        pytest.fail(
            f"capital_cost did not increase with rate: "
            f"at 0.075 → {low}, at 0.12 → {high}."
        )

    # Also smoke-check via prepare_costs on a real technology (onwind).
    costs_low = _prepare_archive_costs()
    # Build a one-off hurdle file with onwind at 0.12.
    hurdle = pd.read_csv(DISCOUNT_RATES_FILE)
    hurdle.loc[hurdle["technology"] == "onwind", "value"] = 0.12
    # Write beside the committed file under test/.tmp via a local path that
    # prepare_costs only reads — no relative_to(ROOT) involved.
    tmp = ROOT / "test" / ".tmp"
    tmp.mkdir(exist_ok=True)
    high_path = tmp / "discount_rates_high_onwind.csv"
    try:
        hurdle.to_csv(high_path, index=False)
        costs_high = _prepare_archive_costs(hurdle_rate_fn=high_path)
        if not (
            float(costs_high.at["onwind", "capital_cost"])
            > float(costs_low.at["onwind", "capital_cost"])
        ):
            pytest.fail(
                "onwind capital_cost did not rise when its hurdle rate rose "
                f"0.075 → 0.12 "
                f"({costs_low.at['onwind', 'capital_cost']} → "
                f"{costs_high.at['onwind', 'capital_cost']})."
            )
    finally:
        high_path.unlink(missing_ok=True)


def test_egs_uses_geothermal_rate():
    """T19: add_enhanced_geothermal reads costs.at[..., 'discount rate'], not fill_values."""
    import scripts.prepare_sector_network as psn

    source = inspect.getsource(psn.add_enhanced_geothermal)
    if 'costs.at["geothermal", "discount rate"]' not in source:
        pytest.fail(
            "add_enhanced_geothermal() no longer reads "
            "costs.at['geothermal', 'discount rate'] — EGS would ignore the "
            "hurdle-rate table (see docs/discount-rates.md §2.3)."
        )
    if 'costs.at["organic rankine cycle", "discount rate"]' not in source:
        pytest.fail(
            "add_enhanced_geothermal() no longer reads "
            "costs.at['organic rankine cycle', 'discount rate']."
        )
    # Must not reintroduce a fill_values discount-rate lookup for the annuity.
    if 'fill_values' in source and 'discount rate' in source:
        # Docstring may still mention fill_values; forbid a runtime lookup.
        runtime = "\n".join(
            line
            for line in source.splitlines()
            if not line.lstrip().startswith(("\"", "'", "#"))
            and '"""' not in line
            and "'''" not in line
        )
        # Strip the function docstring block more carefully.
        src_lines = source.splitlines()
        body_lines = []
        in_doc = False
        seen_def = False
        for line in src_lines:
            if line.startswith("def add_enhanced_geothermal"):
                seen_def = True
                continue
            if not seen_def:
                continue
            stripped = line.strip()
            if not in_doc and (stripped.startswith('"""') or stripped.startswith("'''")):
                in_doc = True
                if stripped.count('"""') == 2 or stripped.count("'''") == 2:
                    in_doc = False
                continue
            if in_doc:
                if '"""' in stripped or "'''" in stripped:
                    in_doc = False
                continue
            body_lines.append(line)
        body = "\n".join(body_lines)
        if "fill_values" in body and "discount rate" in body:
            pytest.fail(
                "add_enhanced_geothermal() body still looks up fill_values for "
                "a discount rate — it must use costs.at[..., 'discount rate']."
            )


def test_check_mode_passes():
    """T20: build_common_parameters --check exits 0 on a clean tree."""
    rc = cmd_check(load_master(), load_meta())
    if rc != 0:
        pytest.fail(
            "cmd_check() returned non-zero. "
            "Run `python scripts/build_common_parameters.py --check` and fix, "
            "or `--write` to re-sync generated files."
        )
