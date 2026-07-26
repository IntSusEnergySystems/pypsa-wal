#!/usr/bin/env python3
"""Generate pypsa-wal artefacts from config/input_parameters_for_models.csv.

See common_parameters.md §5. Modes:

    --check   validate currency tagging and (once filled) targets vs committed artefacts
    --report  summarise master CSV vs technology-data pin; list open status rows
    --write   regenerate artefacts (not fully wired until pypsa_wal_target is filled)

Usage:
    python scripts/build_common_parameters.py --check
    python scripts/build_common_parameters.py --report
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "config" / "input_parameters_for_models.csv"
META_PATH = ROOT / "config" / "common_parameters_meta.yaml"

# Same map as scripts/refresh_common_parameters_currency.py (§4.2).
TECH_NAME_MAP: dict[str, str | None] = {
    "solar utility": "solar-utility",
    "solar rooftop": "solar-rooftop",
    "Nuclear (advanced)": "nuclear",
    "Eletricity distribution grid": "electricity distribution grid",
    "Battery storage (utility)": "battery storage",
    "e-methane": "methanation",
    "OCGT hydrogen": None,
    "CCGT hydrogen": None,
    "Nuclear (SMR)": None,
    "carbon sequestration": None,
    "Uranium cost": "nuclear",
}


def load_meta() -> dict:
    with open(META_PATH) as f:
        return yaml.safe_load(f)


def load_csv() -> pd.DataFrame:
    return pd.read_csv(CSV_PATH)


def monetary_mask(df: pd.DataFrame) -> pd.Series:
    return df["units"].astype(str).str.contains("EUR", na=False) & df["value"].notna()


def check_currency(df: pd.DataFrame, meta: dict) -> list[str]:
    """Assert every populated monetary unit embeds EUR_REF and year_currency matches."""
    eur_ref = int(meta["EUR_REF"])
    prefix = f"EUR{eur_ref}"
    fails: list[str] = []
    mon = df.loc[monetary_mask(df)]
    for r in mon.itertuples():
        units = str(r.units)
        if not units.startswith(prefix):
            fails.append(
                f"units: {r.technology_name_pypsa}/{r.parameter}/{r.year} -> {units}"
            )
        yc = r.year_currency
        if pd.isna(yc) or int(yc) != eur_ref:
            fails.append(
                f"year_currency: {r.technology_name_pypsa}/{r.parameter}/{r.year} -> {yc}"
            )
    # Pin exists
    archive = ROOT / meta["technology_data"]["archive_dir"]
    if not archive.is_dir():
        fails.append(f"technology-data archive missing: {archive}")
    tag = meta["technology_data"]["tag"]
    if archive.name != tag:
        fails.append(f"archive folder {archive.name} != meta tag {tag}")
    return fails


def check_targets_schema(df: pd.DataFrame) -> list[str]:
    """Validate pypsa_wal_target / year_rule / status when the columns exist."""
    fails: list[str] = []
    for col in ("pypsa_wal_target", "year_rule", "status"):
        if col not in df.columns:
            fails.append(f"missing column {col} (fill in migration step 4)")
    if fails:
        return fails

    allowed_status = {"active", "pending", "none"}
    allowed_year_rule = {"all", "hold", "interp"}
    bad_status = df[df["status"].notna() & ~df["status"].isin(allowed_status)]
    for r in bad_status.itertuples():
        fails.append(f"bad status {r.status!r} at row {r.Index}")
    bad_yr = df[df["year_rule"].notna() & ~df["year_rule"].isin(allowed_year_rule)]
    for r in bad_yr.itertuples():
        fails.append(f"bad year_rule {r.year_rule!r} at row {r.Index}")

    # Duplicate active targets
    active = df[df["status"] == "active"]
    if "pypsa_wal_target" in active.columns:
        dup = (
            active.dropna(subset=["pypsa_wal_target"])
            .groupby(["pypsa_wal_target", "year"])
            .size()
        )
        for (tgt, year), n in dup.items():
            if n > 1 and not str(tgt).startswith("none:"):
                fails.append(f"duplicate active target {tgt} @ {year} (n={n})")
    return fails


def report(df: pd.DataFrame, meta: dict) -> None:
    eur_ref = int(meta["EUR_REF"])
    tag = meta["technology_data"]["tag"]
    print(f"EUR_REF={eur_ref}  technology-data={tag}")
    print(f"rows={len(df)}")
    print("data_origin_choice:")
    print(df["data_origin_choice"].value_counts(dropna=False).to_string())
    mon = df.loc[monetary_mask(df)]
    print(f"populated monetary rows: {len(mon)}")
    print(
        f"  with {eur_ref} in units: "
        f"{mon['units'].astype(str).str.startswith(f'EUR{eur_ref}').sum()}"
    )
    empty_eur = df[
        df["units"].astype(str).str.contains("EUR", na=False) & df["value"].isna()
    ]
    print(f"empty-value EUR placeholders (skipped in §4.3): {len(empty_eur)}")

    if "status" in df.columns:
        print("status:")
        print(df["status"].value_counts(dropna=False).to_string())
    else:
        print("status / pypsa_wal_target / year_rule: columns not yet added")

    # Sample deltas vs archive for a few PyPSA investment rows
    archive = ROOT / meta["technology_data"]["archive_dir"]
    costs = pd.read_csv(archive / "costs_2030.csv")
    print("\nspot vs technology-data 2030 (PyPSA-origin investment):")
    for tech in ("CCGT", "OCGT", "electrolysis", "HVDC inverter pair"):
        csv_v = df[
            (df["technology_name_pypsa"] == tech)
            & (df["parameter"] == "investment")
            & (df["year"] == 2030)
            & (df["data_origin_choice"] == "PyPSA")
        ]
        cost_v = costs[(costs["technology"] == tech) & (costs["parameter"] == "investment")]
        if len(csv_v) == 1 and len(cost_v) == 1:
            a, b = float(csv_v.iloc[0]["value"]), float(cost_v.iloc[0]["value"])
            print(f"  {tech}: csv={a} archive={b} match={abs(a-b)<1e-6}")


def cmd_check(df: pd.DataFrame, meta: dict) -> int:
    fails = check_currency(df, meta)
    # Target schema is soft until columns exist: report but only fail currency for now
    target_fails = check_targets_schema(df)
    if any("missing column" in f for f in target_fails):
        print("NOTE: machine-readable columns not yet added (migration step 4):")
        for f in target_fails:
            print(f"  · {f}")
        target_fails = [f for f in target_fails if "missing column" not in f]
    fails.extend(target_fails)
    if fails:
        print("CHECK FAILED:")
        for f in fails:
            print(f"  ✗ {f}")
        return 1
    print("CHECK PASSED (currency + meta pin)")
    return 0


def cmd_write(_df: pd.DataFrame, _meta: dict) -> int:
    print(
        "--write is not enabled yet: fill pypsa_wal_target / year_rule / status "
        "(migration step 4) and resolve §3 modelling decisions first."
    )
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--report", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()

    meta = load_meta()
    df = load_csv()

    if args.check:
        return cmd_check(df, meta)
    if args.report:
        report(df, meta)
        return cmd_check(df, meta)
    if args.write:
        return cmd_write(df, meta)
    return 1


if __name__ == "__main__":
    sys.exit(main())
