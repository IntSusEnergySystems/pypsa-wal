#!/usr/bin/env python3
"""Refresh monetary rows in config/input_parameters_for_models.csv to EUR2025.

Implements common_parameters.md §4.3 (PyPSA-origin from technology-data pin)
and §4.4 (retag Revue de littérature / TIMES units; no value rescale).

Usage:
    python scripts/refresh_common_parameters_currency.py [--dry-run]
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "config" / "input_parameters_for_models.csv"
META_PATH = ROOT / "config" / "common_parameters_meta.yaml"

# §4.2 name map (extend explicitly; never guess). None = skip.
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
    # Explicit extension: CSV label vs cost-file key / parameter (see §3.9).
    "Uranium cost": "nuclear",
}

# Parameter name in CSV → parameter name in costs_<year>.csv
PARAM_MAP: dict[str, str] = {
    "investment": "investment",
    "FOM": "FOM",
    "VOM": "VOM",
    "lifetime": "lifetime",
    "efficiency": "efficiency",
    "price": "fuel",  # Uranium cost only today
}

# Spot-checks use a PyPSA-origin monetary parameter (onwind investment is
# Revue de littérature / stakeholder override, so check VOM instead).
SPOT_CHECKS = [
    ("CCGT", "investment"),
    ("OCGT", "investment"),
    ("onwind", "VOM"),
    ("electrolysis", "investment"),
    ("HVDC inverter pair", "investment"),
]


def load_meta() -> dict:
    if META_PATH.exists():
        with open(META_PATH) as f:
            return yaml.safe_load(f) or {}
    return {
        "EUR_REF": 2025,
        "technology_data": {"tag": "v0.14.0", "eur_year": 2025},
    }


def costs_dir(meta: dict) -> Path:
    tag = meta["technology_data"]["tag"]
    return ROOT / "data" / "costs" / "archive" / tag


def eur2025_unit(unit: str) -> str:
    """Replace a leading EUR in the cost-file unit by EUR2025 (§4.3 unit rule)."""
    u = str(unit).strip()
    if u.startswith("EUR2025"):
        return u
    if u.startswith("EUR"):
        return "EUR2025" + u[3:]
    return u


def resolve_tech_key(name: str) -> tuple[str | None, str]:
    """Return (cost_file_key_or_None_if_skip, status)."""
    if name in TECH_NAME_MAP:
        key = TECH_NAME_MAP[name]
        return key, ("skip" if key is None else "mapped")
    return name, "exact"


def refresh_pypsa_rows(df: pd.DataFrame, meta: dict) -> tuple[pd.DataFrame, dict]:
    archive = costs_dir(meta)
    tag = meta["technology_data"]["tag"]
    eur_ref = int(meta["EUR_REF"])

    costs_by_year: dict[int, pd.DataFrame] = {}
    for y in (2030, 2040, 2050):
        path = archive / f"costs_{y}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing cost archive file: {path}")
        costs_by_year[y] = pd.read_csv(path)

    candidates = (
        (df["data_origin_choice"] == "PyPSA")
        & df["units"].astype(str).str.contains("EUR", na=False)
        & df["parameter"].notna()
        & (df["parameter"].astype(str).str.len() > 0)
        & df["year"].isin([2030, 2040, 2050])
    )

    updated = skipped = errors = 0
    skip_list: list[str] = []
    error_list: list[str] = []

    out = df.copy()
    for idx in out.index[candidates]:
        row = out.loc[idx]
        raw_name = row["technology_name_pypsa"]
        param_csv = str(row["parameter"]).strip()
        year = int(row["year"])

        # Empty pypsa name = placeholder row (e.g. CCGT/OCGT with capture) — skip.
        if pd.isna(raw_name) or str(raw_name).strip() == "" or str(raw_name).strip().lower() == "nan":
            skipped += 1
            skip_list.append(f"<empty name>/{param_csv}/{year} (no technology_name_pypsa)")
            continue

        tech_label = str(raw_name).strip()
        key, how = resolve_tech_key(tech_label)
        if key is None:
            skipped += 1
            skip_list.append(f"{tech_label}/{param_csv}/{year} ({how})")
            continue

        if param_csv not in PARAM_MAP:
            errors += 1
            error_list.append(
                f"{tech_label}/{param_csv}/{year}: unknown parameter (not in PARAM_MAP)"
            )
            continue
        param = PARAM_MAP[param_csv]

        costs = costs_by_year[year]
        matches = costs[
            (costs["technology"] == key) & (costs["parameter"] == param)
        ]
        if len(matches) != 1:
            errors += 1
            error_list.append(
                f"{tech_label}->{key}/{param}/{year}: {len(matches)} matches"
            )
            continue

        m = matches.iloc[0]
        value = m["value"]
        if pd.isna(value) or (isinstance(value, float) and math.isnan(value)):
            errors += 1
            error_list.append(f"{tech_label}/{param}/{year}: NaN value in cost file")
            continue

        unit_src = str(m["unit"])
        further = m["further description"]
        further_s = "" if pd.isna(further) else str(further).strip()
        desc = f"technology-data {tag}"
        if further_s:
            desc = f"{desc}; {further_s}"

        out.at[idx, "value"] = float(value)
        out.at[idx, "units"] = eur2025_unit(unit_src)
        out.at[idx, "year_currency"] = eur_ref
        out.at[idx, "source"] = m["source"] if not pd.isna(m["source"]) else ""
        out.at[idx, "description_complementaire"] = desc
        updated += 1

    # Clear stale audit columns (§4.3 step 7)
    if "pypsa_wal_value" in out.columns:
        out["pypsa_wal_value"] = pd.NA
    if "pypsa_wal_location" in out.columns:
        out["pypsa_wal_location"] = pd.NA

    stats = {
        "candidates": int(candidates.sum()),
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "skip_list": skip_list,
        "error_list": error_list,
        "tag": tag,
        "eur_ref": eur_ref,
        "archive": str(archive),
    }
    return out, stats


def retag_non_pypsa(df: pd.DataFrame, eur_ref: int) -> tuple[pd.DataFrame, int]:
    """§4.4: rewrite EUR → EUR2025 and set year_currency; do not change value."""
    mask = df["data_origin_choice"].isin(["Revue de littérature", "TIMES"]) & df[
        "units"
    ].astype(str).str.contains("EUR", na=False)
    out = df.copy()
    n = 0
    for idx in out.index[mask]:
        units = str(out.at[idx, "units"])
        if units.startswith("EUR") and not units.startswith("EUR2025"):
            # Preserve any suffix after EUR (e.g. EUR/MWh_th, EUR/MWH_H2_PCI)
            out.at[idx, "units"] = f"EUR{eur_ref}" + units[3:]
        elif "EUR" in units and f"EUR{eur_ref}" not in units:
            # Defensive: replace bare EUR token once at start of currency fragment
            out.at[idx, "units"] = units.replace("EUR", f"EUR{eur_ref}", 1)
        out.at[idx, "year_currency"] = eur_ref
        n += 1
    return out, n


def run_checks(df: pd.DataFrame, stats: dict, meta: dict) -> list[str]:
    fails: list[str] = []
    eur_ref = stats["eur_ref"]
    tag = stats["tag"]
    archive = Path(stats["archive"])

    if stats["updated"] + stats["skipped"] + stats["errors"] != stats["candidates"]:
        fails.append(
            f"count mismatch: updated+skipped+errors="
            f"{stats['updated']+stats['skipped']+stats['errors']} "
            f"!= candidates={stats['candidates']}"
        )
    if stats["errors"] != 0:
        fails.append(f"#errors must be 0; got {stats['errors']}: {stats['error_list']}")

    # Updated-row currency checks: rows whose description starts with technology-data tag
    refreshed = df["description_complementaire"].astype(str).str.startswith(
        f"technology-data {tag}"
    ) & (df["data_origin_choice"] == "PyPSA")
    # More reliable: year_currency==eur_ref and units start with EUR2025 among former candidates
    # Use: PyPSA + EUR in units + year in horizons + not skipped techs
    skip_names = {k for k, v in TECH_NAME_MAP.items() if v is None}
    has_name = df["technology_name_pypsa"].notna() & (
        df["technology_name_pypsa"].astype(str).str.strip().str.len() > 0
    ) & ~df["technology_name_pypsa"].astype(str).str.strip().str.lower().eq("nan")
    monetary_pypsa = (
        (df["data_origin_choice"] == "PyPSA")
        & df["units"].astype(str).str.contains("EUR", na=False)
        & df["year"].isin([2030, 2040, 2050])
        & has_name
        & ~df["technology_name_pypsa"].isin(skip_names)
        & df["parameter"].notna()
        & (df["parameter"].astype(str).str.len() > 0)
    )
    sub = df.loc[monetary_pypsa]
    bad_yc = sub[sub["year_currency"] != eur_ref]
    if len(bad_yc):
        fails.append(f"{len(bad_yc)} updated rows without year_currency={eur_ref}")
    bad_u = sub[~sub["units"].astype(str).str.startswith(f"EUR{eur_ref}")]
    if len(bad_u):
        fails.append(
            f"{len(bad_u)} updated rows whose units do not start with EUR{eur_ref}: "
            + ", ".join(
                f"{r.technology_name_pypsa}/{r.parameter}/{int(r.year)}:{r.units}"
                for r in bad_u.head(5).itertuples()
            )
        )
    if sub["value"].isna().any():
        fails.append("NaN value in an updated monetary PyPSA row")

    # Spot-checks vs cost file
    costs_2030 = pd.read_csv(archive / "costs_2030.csv")
    for tech, param in SPOT_CHECKS:
        csv_rows = df[
            (df["technology_name_pypsa"] == tech)
            & (df["parameter"] == param)
            & (df["year"] == 2030)
            & (df["data_origin_choice"] == "PyPSA")
        ]
        cost_rows = costs_2030[
            (costs_2030["technology"] == tech) & (costs_2030["parameter"] == param)
        ]
        if len(csv_rows) != 1 or len(cost_rows) != 1:
            fails.append(
                f"spot-check {tech}/{param}/2030: csv={len(csv_rows)} cost={len(cost_rows)}"
            )
            continue
        v_csv = float(csv_rows.iloc[0]["value"])
        v_cost = float(cost_rows.iloc[0]["value"])
        # ≥4 significant figures
        if v_cost == 0:
            ok = v_csv == 0
        else:
            ok = abs(v_csv - v_cost) / abs(v_cost) < 5e-4
        if not ok:
            fails.append(
                f"spot-check {tech}/{param}/2030: csv={v_csv} != cost={v_cost}"
            )

    # §4.4: non-PyPSA monetary units
    mask = df["data_origin_choice"].isin(["Revue de littérature", "TIMES"]) & df[
        "units"
    ].astype(str).str.contains("EUR", na=False)
    for r in df.loc[mask].itertuples():
        if not str(r.units).startswith(f"EUR{eur_ref}"):
            fails.append(
                f"§4.4 unit not retagged: {r.technology_name_pypsa}/{r.parameter}/{r.year} -> {r.units}"
            )
        if r.year_currency != eur_ref:
            fails.append(
                f"§4.4 year_currency: {r.technology_name_pypsa}/{r.parameter}/{r.year} -> {r.year_currency}"
            )

    return fails


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and validate but do not write the CSV",
    )
    args = parser.parse_args()

    meta = load_meta()
    df = pd.read_csv(CSV_PATH)
    df, stats = refresh_pypsa_rows(df, meta)
    df, n_retag = retag_non_pypsa(df, int(meta["EUR_REF"]))

    print(f"technology-data pin: {stats['tag']} @ {stats['archive']}")
    print(
        f"§4.3 candidates={stats['candidates']} updated={stats['updated']} "
        f"skipped={stats['skipped']} errors={stats['errors']}"
    )
    if stats["skip_list"]:
        print("skipped:")
        for s in sorted(set(stats["skip_list"])):
            print(f"  - {s}")
    if stats["error_list"]:
        print("errors:")
        for e in stats["error_list"]:
            print(f"  - {e}")
    print(f"§4.4 retagged (units/year_currency only): {n_retag}")

    fails = run_checks(df, stats, meta)
    if fails:
        print("CHECKS FAILED:")
        for f in fails:
            print(f"  ✗ {f}")
        return 1

    print("CHECKS PASSED")
    if args.dry_run:
        print("dry-run: CSV not written")
        return 0

    df.to_csv(CSV_PATH, index=False)
    print(f"wrote {CSV_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
