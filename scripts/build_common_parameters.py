#!/usr/bin/env python3
"""Apply config/input_parameters_for_models.csv to the pypsa-wal input files.

The shared TIMES/PyPSA table is authoritative for the parameters it covers
(see common_parameters.md). This script does not *generate* input files: it
**patches values in place** in the files the workflow already reads, so the
hand-written structure, sources and comments of those files survive and
`git diff` shows exactly what the shared table changed.

    config/input_parameters_for_models.csv        (authoritative values)
                │
                ├─► data/walloon/custom_costs.csv          cost:<tech>:<param>
                ├─► data/walloon/custom_potentials.csv     potential:<bus>:<tech>:<attr>
                ├─► data/walloon/ntc_<year>.csv            ntc:<A>-<B>
                └─► config/config.walloon.yaml             config:budget_national

Failsafe: a patch may only rewrite the ``value`` cell of an existing row. If the
row count or the row keys change, or a row would have to be added or removed,
the run aborts and reports what needs a manual edit instead.

Modes:
    --check   validate the master CSV and verify the input files are in sync
    --report  summarise the master CSV
    --write   patch the input files (use --dry-run to preview)
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "config" / "input_parameters_for_models.csv"
META_PATH = ROOT / "config" / "common_parameters_meta.yaml"
WALLOON_CONFIG = ROOT / "config" / "config.walloon.yaml"
COSTS_FILE = ROOT / "data" / "walloon" / "custom_costs.csv"
POTENTIALS_FILE = ROOT / "data" / "walloon" / "custom_potentials.csv"
NTC_GLOB = "ntc_*.csv"

BUDGET_REGIONS = ("BEBRU", "BEVLG", "BEWAL", "DE", "FR", "GB", "NL", "LU")

ISO2_TO_ISO3 = {
    "BE": "BEL",
    "DE": "DEU",
    "FR": "FRA",
    "NL": "NLD",
    "LU": "LUX",
    "UK": "GBR",
    "GB": "GBR",
}

ALLOWED_STATUS = {"active", "pending", "none"}
ALLOWED_YEAR_RULE = {"all", "hold", "interp"}

# Unit tokens that change the numeric scale. process_cost_data.py multiplies by
# 1e3 for "/kW" and BEWAL_potentials.py by 1e3 for "GW"/"GWh", so a mismatch
# between the master CSV and the input file silently misscales a value.
SCALE_TOKENS = ("GWh", "MWh", "kWh", "GW", "MW", "kW")


# --------------------------------------------------------------------------- #
# master table
# --------------------------------------------------------------------------- #
def load_meta() -> dict:
    return yaml.safe_load(META_PATH.read_text())


def load_master() -> pd.DataFrame:
    return pd.read_csv(CSV_PATH)


def planning_horizons() -> tuple[int, ...]:
    """Planning horizons of the Walloon run — the horizons artefacts must cover."""
    cfg = yaml.safe_load(WALLOON_CONFIG.read_text())
    return tuple(int(y) for y in cfg["scenario"]["planning_horizons"])


def active_rows(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["status"] == "active"]


def monetary_mask(df: pd.DataFrame) -> pd.Series:
    return df["units"].astype(str).str.contains("EUR", na=False) & df["value"].notna()


def expand_years(
    year_rule: str, anchors: dict[int, float], horizons: tuple[int, ...]
) -> dict[int, float]:
    """Expand sparse anchor years onto every planning horizon."""
    if not anchors:
        return {}
    rule = (year_rule or "hold").lower()
    xs = sorted(anchors)
    out: dict[int, float] = {}
    for h in horizons:
        if h in anchors:
            out[h] = float(anchors[h])
        elif rule == "all":
            out[h] = float(anchors[xs[0]])
        elif rule == "interp":
            if h <= xs[0]:
                out[h] = float(anchors[xs[0]])
            elif h >= xs[-1]:
                out[h] = float(anchors[xs[-1]])
            else:
                lo = max(y for y in xs if y <= h)
                hi = min(y for y in xs if y >= h)
                t = (h - lo) / (hi - lo)
                out[h] = float(anchors[lo]) * (1 - t) + float(anchors[hi]) * t
        else:  # hold: nearest earlier anchor, else the first one
            prev = [y for y in xs if y <= h]
            out[h] = float(anchors[prev[-1]] if prev else anchors[xs[0]])
    return out


@dataclass
class Target:
    """One `pypsa_wal_target` of the master CSV, expanded onto every horizon."""

    key: tuple[str, ...]
    values: dict[int, float]
    anchors: dict[int, float]
    unit: str
    origin: str
    year_rule: str

    @property
    def constant(self) -> bool:
        vals = list(self.values.values())
        return all(abs(v - vals[0]) < 1e-9 for v in vals)

    @property
    def label(self) -> str:
        return ":".join(self.key)


def collect_targets(
    df: pd.DataFrame, prefix: str, horizons: tuple[int, ...], nparts: int | None = None
) -> dict[tuple[str, ...], Target]:
    """Group active rows by `pypsa_wal_target` and expand their anchors."""
    act = active_rows(df)
    sel = act[act["pypsa_wal_target"].astype(str).str.startswith(f"{prefix}:")]
    out: dict[tuple[str, ...], Target] = {}
    for tgt, g in sel.groupby("pypsa_wal_target"):
        parts = str(tgt).split(":")[1:]
        if nparts is not None and len(parts) != nparts:
            continue
        anchors: dict[int, float] = {}
        unit = ""
        rule = "hold"
        for _, r in g.iterrows():
            if pd.isna(r["value"]):
                continue
            if pd.isna(r["year"]):
                # yearless row: the same value applies to every horizon
                anchors.update({h: float(r["value"]) for h in horizons})
            else:
                anchors[int(r["year"])] = float(r["value"])
            if pd.notna(r["units"]):
                unit = str(r["units"])
            if pd.notna(r.get("year_rule")):
                rule = str(r["year_rule"])
        if not anchors:
            continue
        key = tuple(parts)
        out[key] = Target(
            key=key,
            values=expand_years(rule, anchors, horizons),
            anchors=anchors,
            unit=unit,
            origin=str(g["data_origin_choice"].iloc[0]),
            year_rule=rule,
        )
    return out


# --------------------------------------------------------------------------- #
# value / unit helpers
# --------------------------------------------------------------------------- #
def scale_token(unit: str) -> str | None:
    """Return the energy/power token that fixes the numeric scale of a unit."""
    u = str(unit)
    for tok in SCALE_TOKENS:
        if tok in u:
            return tok
    return None


def units_compatible(csv_unit: str, file_unit: str) -> bool:
    a, b = scale_token(csv_unit), scale_token(file_unit)
    return a is None or b is None or a == b


def fmt_value(v: float) -> str:
    if float(v).is_integer():
        return str(int(v))
    return f"{v:.10g}"


def same_value(cell: str, v: float) -> bool:
    try:
        return abs(float(cell) - v) < 1e-9
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------- #
# patching
# --------------------------------------------------------------------------- #
@dataclass
class Patch:
    path: Path
    changes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    managed: int = 0
    rows: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def _read_str(path: Path) -> pd.DataFrame:
    """Read a CSV keeping every cell verbatim, so unpatched cells never change."""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _newline(path: Path) -> str:
    """The file's own line ending, so a patch does not rewrite every line."""
    with path.open("rb") as f:
        return "\r\n" if b"\r\n" in f.read(4096) else "\n"


def _write(path: Path, frame: pd.DataFrame, before: pd.DataFrame, patch: Patch) -> None:
    """Write `frame` back, refusing anything but in-place value edits."""
    if len(frame) != len(before):
        patch.errors.append(
            f"{path.name}: row count changed {len(before)} -> {len(frame)} "
            "(patching may only rewrite existing rows)"
        )
        return
    if list(frame.columns) != list(before.columns):
        patch.errors.append(f"{path.name}: column layout changed")
        return
    frame.to_csv(path, index=False, lineterminator=_newline(path))


def patch_costs(df: pd.DataFrame, horizons: tuple[int, ...], dry_run: bool) -> Patch:
    """Patch data/walloon/custom_costs.csv from `cost:<tech>:<param>` targets."""
    patch = Patch(path=COSTS_FILE)
    targets = collect_targets(df, "cost", horizons, nparts=2)
    frame = _read_str(COSTS_FILE)
    before = frame.copy()
    patch.rows = len(frame)

    seen: set[tuple[str, ...]] = set()
    for i, row in frame.iterrows():
        key = (row["technology"], row["parameter"])
        tgt = targets.get(key)
        if tgt is None:
            patch.notes.append(
                f"unmanaged row: {row['planning_horizon']}/{key[0]}/{key[1]} "
                "(no active target in the master CSV)"
            )
            continue
        seen.add(key)
        patch.managed += 1

        if not units_compatible(tgt.unit, row["unit"]):
            patch.errors.append(
                f"{COSTS_FILE.name}: unit mismatch for {tgt.label}: master CSV "
                f"{tgt.unit!r} vs file {row['unit']!r} — scales differ, refusing to patch"
            )
            continue

        ph = row["planning_horizon"]
        if ph == "all":
            if not tgt.constant:
                patch.errors.append(
                    f"{COSTS_FILE.name}: row 'all,{key[0]},{key[1]}' cannot hold "
                    f"{tgt.label}, whose master-CSV value varies by horizon "
                    f"({ {y: fmt_value(v) for y, v in tgt.values.items()} }). "
                    "Split it into one row per planning horizon."
                )
                continue
            new = next(iter(tgt.values.values()))
        else:
            try:
                new = tgt.values[int(ph)]
            except (KeyError, ValueError):
                patch.errors.append(
                    f"{COSTS_FILE.name}: row {ph}/{key[0]}/{key[1]} has a planning "
                    f"horizon outside {horizons}"
                )
                continue

        if same_value(row["value"], new):
            continue
        patch.changes.append(
            f"{ph:>4} {key[0]}/{key[1]}: {row['value']} -> {fmt_value(new)} {row['unit']}"
        )
        frame.at[i, "value"] = fmt_value(new)

    # A genuine Walloon override with no row here would be silently dropped.
    # PyPSA-origin targets need no row: their value *is* the technology-data value.
    for key, tgt in sorted(targets.items()):
        if key in seen or tgt.origin == "PyPSA":
            continue
        patch.errors.append(
            f"{COSTS_FILE.name}: no row for active target cost:{tgt.label} "
            f"(origin {tgt.origin}) — add it to the file or set status=none"
        )

    if not dry_run and patch.ok and patch.changes:
        _write(COSTS_FILE, frame, before, patch)
    return patch


def patch_potentials(
    df: pd.DataFrame, horizons: tuple[int, ...], dry_run: bool
) -> Patch:
    """Patch data/walloon/custom_potentials.csv from `potential:...` targets."""
    patch = Patch(path=POTENTIALS_FILE)
    targets = collect_targets(df, "potential", horizons, nparts=3)
    # BEWAL_potentials.py matches `year` exactly; wildcard geographies are unresolved.
    targets = {k: v for k, v in targets.items() if "*" not in k[0]}
    frame = _read_str(POTENTIALS_FILE)
    before = frame.copy()
    patch.rows = len(frame)

    seen: set[tuple[str, ...]] = set()
    covered: dict[tuple[str, ...], set[int]] = {}
    for i, row in frame.iterrows():
        key = (row["bus"] or "BEWAL", row["technology"], row["parameter"])
        tgt = targets.get(key)
        if tgt is None:
            patch.notes.append(
                f"unmanaged row: {'/'.join(key)}@{row['year']} "
                "(no active target in the master CSV)"
            )
            continue
        seen.add(key)
        patch.managed += 1
        covered.setdefault(key, set()).add(int(row["year"]))

        if not units_compatible(tgt.unit, row["unit"]):
            patch.errors.append(
                f"{POTENTIALS_FILE.name}: unit mismatch for {tgt.label}: master CSV "
                f"{tgt.unit!r} vs file {row['unit']!r} — scales differ, refusing to patch"
            )
            continue

        year = int(row["year"])
        if year not in tgt.values:
            patch.errors.append(
                f"{POTENTIALS_FILE.name}: row {'/'.join(key)}@{year} has a planning "
                f"horizon outside {horizons}"
            )
            continue
        new = tgt.values[year]
        if same_value(row["value"], new):
            continue
        patch.changes.append(
            f"{year} {'/'.join(key)}: {row['value']} -> {fmt_value(new)} {row['unit']}"
        )
        frame.at[i, "value"] = fmt_value(new)

    for key, tgt in sorted(targets.items()):
        if key not in seen:
            patch.errors.append(
                f"{POTENTIALS_FILE.name}: no row for active target potential:{tgt.label}"
                " — add it to the file or set status=none"
            )
            continue
        missing = sorted(set(horizons) - covered[key])
        if missing:
            patch.errors.append(
                f"{POTENTIALS_FILE.name}: {tgt.label} has no row for {missing}. "
                "BEWAL_potentials.py matches the year exactly, so those horizons "
                "would silently keep the PyPSA-Eur default."
            )

    if not dry_run and patch.ok and patch.changes:
        _write(POTENTIALS_FILE, frame, before, patch)
    return patch


def patch_ntc(df: pd.DataFrame, horizons: tuple[int, ...], dry_run: bool) -> list[Patch]:
    """Patch NTC_MW of every data/walloon/ntc_<year>.csv from `ntc:<A>-<B>` targets."""
    raw = collect_targets(df, "ntc", horizons, nparts=1)
    targets: dict[tuple[str, str], Target] = {}
    for (pair,), tgt in raw.items():
        m = re.fullmatch(r"([A-Za-z]{2,3})-([A-Za-z]{2,3})", pair)
        if not m:
            continue
        a, b = (ISO2_TO_ISO3.get(g.upper(), g.upper()) for g in m.groups())
        targets[(a, b)] = tgt

    patches: list[Patch] = []
    for path in sorted((ROOT / "data" / "walloon").glob(NTC_GLOB)):
        year = int(re.search(r"(\d{4})", path.name).group(1))
        patch = Patch(path=path)
        frame = _read_str(path)
        before = frame.copy()
        patch.rows = len(frame)

        for (a, b), tgt in sorted(targets.items()):
            mask = (frame["source_country_code"] == a) & (
                frame["target_country_code"] == b
            )
            if not mask.any():
                patch.errors.append(
                    f"{path.name}: no {a}->{b} row for active target ntc:{tgt.label} "
                    "— add it to the file or set status=none"
                )
                continue
            patch.managed += int(mask.sum())
            # `ntc_2035.csv` etc. are not planning horizons of the Walloon run;
            # expand the anchors onto them with the row's own year_rule.
            values = (
                tgt.values
                if year in tgt.values
                else expand_years(tgt.year_rule, tgt.values, (year,))
            )
            new = values[year]
            for i in frame.index[mask]:
                if same_value(frame.at[i, "NTC_MW"], new):
                    continue
                patch.changes.append(
                    f"{a}->{b}: {frame.at[i, 'NTC_MW']} -> {fmt_value(new)} MW"
                )
                frame.at[i, "NTC_MW"] = fmt_value(new)

        if not dry_run and patch.ok and patch.changes:
            _write(path, frame, before, patch)
        patches.append(patch)
    return patches


# --------------------------------------------------------------------------- #
# config:budget_national
# --------------------------------------------------------------------------- #
def build_budget_national(
    df: pd.DataFrame, horizons: tuple[int, ...]
) -> dict[int, dict[str, float]]:
    """CO2 trajectory as `budget_national`. The CSV stores %, the config a fraction."""
    act = active_rows(df)
    rows = act[act["pypsa_wal_target"] == "config:budget_national"]
    anchors: dict[int, float] = {}
    rule = "interp"
    for _, r in rows.iterrows():
        if pd.isna(r["value"]) or pd.isna(r["year"]):
            continue
        anchors[int(r["year"])] = float(r["value"]) / 100.0
        if pd.notna(r.get("year_rule")):
            rule = str(r["year_rule"])
    return {
        y: {reg: round(frac, 6) for reg in BUDGET_REGIONS}
        for y, frac in sorted(expand_years(rule, anchors, horizons).items())
    }


def render_budget_block(budget: dict[int, dict[str, float]]) -> str:
    lines = ["budget_national:"]
    for year, regions in budget.items():
        lines.append(f"  {year}:")
        lines.extend(f"    {reg}: {frac}" for reg, frac in regions.items())
    return "\n".join(lines) + "\n"


def patch_walloon_config(budget: dict[int, dict[str, float]], dry_run: bool) -> Patch:
    """Rewrite the `budget_national:` block of config.walloon.yaml in place."""
    patch = Patch(path=WALLOON_CONFIG)
    text = WALLOON_CONFIG.read_text()
    # The block runs from `budget_national:` to the next top-level key.
    m = re.search(r"^budget_national:\n(?:[ \t].*\n|\n)*", text, flags=re.MULTILINE)
    if not m:
        patch.errors.append(f"{WALLOON_CONFIG.name}: no `budget_national:` block found")
        return patch
    if not budget:
        patch.errors.append("master CSV has no active config:budget_national anchors")
        return patch

    old = m.group(0)
    new = render_budget_block(budget)
    trailing = "\n" if old.endswith("\n\n") else ""
    if old == new + trailing:
        patch.notes.append("budget_national already in sync")
        return patch

    patch.changes.append(
        "budget_national: "
        + ", ".join(f"{y}={next(iter(r.values()))}" for y, r in budget.items())
    )
    if not dry_run:
        WALLOON_CONFIG.write_text(text[: m.start()] + new + trailing + text[m.end() :])
    return patch


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #
def check_currency(df: pd.DataFrame, meta: dict) -> list[str]:
    eur_ref = int(meta["EUR_REF"])
    prefix = f"EUR{eur_ref}"
    fails: list[str] = []
    for r in df.loc[monetary_mask(df)].itertuples():
        if not str(r.units).startswith(prefix):
            fails.append(
                f"units: {r.technology_name_pypsa}/{r.parameter}/{r.year} -> {r.units}"
            )
        if pd.isna(r.year_currency) or int(r.year_currency) != eur_ref:
            fails.append(
                f"year_currency: {r.technology_name_pypsa}/{r.parameter}/{r.year}"
                f" -> {r.year_currency}"
            )
    archive = ROOT / meta["technology_data"]["archive_dir"]
    tag = meta["technology_data"]["tag"]
    if not archive.is_dir():
        fails.append(f"technology-data archive missing: {archive}")
    elif archive.name != tag:
        fails.append(f"archive folder {archive.name} != meta tag {tag}")
    return fails


def check_schema(df: pd.DataFrame) -> list[str]:
    fails = [
        f"missing column {col}"
        for col in ("pypsa_wal_target", "year_rule", "status")
        if col not in df.columns
    ]
    if fails:
        return fails
    for r in df[df["status"].notna() & ~df["status"].isin(ALLOWED_STATUS)].itertuples():
        fails.append(f"bad status {r.status!r} at row {r.Index}")
    for r in df[
        df["year_rule"].notna() & ~df["year_rule"].isin(ALLOWED_YEAR_RULE)
    ].itertuples():
        fails.append(f"bad year_rule {r.year_rule!r} at row {r.Index}")

    act = active_rows(df).dropna(subset=["pypsa_wal_target"])
    dup = act.groupby(["pypsa_wal_target", "year"], dropna=False).size()
    for (tgt, year), n in dup.items():
        if n > 1 and not str(tgt).startswith("none:"):
            fails.append(f"duplicate active target {tgt} @ {year} (n={n})")
    return fails


def check_smr(df: pd.DataFrame) -> list[str]:
    """§3.3: cost-file key `SMR` is steam methane reforming, not a nuclear SMR."""
    fails = []
    if COSTS_FILE.exists() and (_read_str(COSTS_FILE)["technology"] == "SMR").any():
        fails.append(f"{COSTS_FILE.name} contains technology=SMR (see §3.3)")
    bad = active_rows(df)["pypsa_wal_target"].astype(str) == "cost:SMR:investment"
    if bad.any():
        fails.append("master CSV has an active cost:SMR:* target (see §3.3)")
    return fails


def check_archive_drift(df: pd.DataFrame, meta: dict) -> list[str]:
    """PyPSA-origin targets with no override row must still match technology-data.

    Such a row is not written anywhere: pypsa-wal gets the value straight from
    the pinned technology-data archive. If the archive moves away from the
    negotiated figure, TIMES and PyPSA silently disagree.
    """
    horizons = planning_horizons()
    targets = collect_targets(df, "cost", horizons, nparts=2)
    overrides = _read_str(COSTS_FILE)
    have = set(zip(overrides["technology"], overrides["parameter"]))
    archive = ROOT / meta["technology_data"]["archive_dir"]
    warnings: list[str] = []
    for year in horizons:
        path = archive / f"costs_{year}.csv"
        if not path.exists():
            continue
        base = pd.read_csv(path).set_index(["technology", "parameter"])["value"]
        base = base[~base.index.duplicated()]
        for key, tgt in sorted(targets.items()):
            # Only compare years the table actually anchors: a held-forward value
            # is not a claim about that horizon.
            if key in have or tgt.origin != "PyPSA" or key not in base.index:
                continue
            if year not in tgt.anchors:
                continue
            want, got = tgt.values[year], float(base.loc[key])
            if abs(want - got) > max(1e-6, 1e-4 * abs(want)):
                warnings.append(
                    f"{tgt.label} @ {year}: master CSV {want:g} vs "
                    f"technology-data {meta['technology_data']['tag']} {got:g}"
                )
    return warnings


# --------------------------------------------------------------------------- #
# modes
# --------------------------------------------------------------------------- #
def report_patch(patch: Patch, verbose: bool) -> None:
    rel = patch.path.relative_to(ROOT)
    state = "FAIL" if patch.errors else ("update" if patch.changes else "in sync")
    print(f"  {rel}  [{state}]  rows={patch.rows} managed={patch.managed}")
    for c in patch.changes:
        print(f"      ~ {c}")
    for e in patch.errors:
        print(f"      ✗ {e}")
    if verbose:
        for n in patch.notes:
            print(f"      · {n}")


def cmd_check(df: pd.DataFrame, meta: dict, verbose: bool = False) -> int:
    fails = check_currency(df, meta) + check_schema(df) + check_smr(df)
    if fails:
        print("master CSV:")
        for f in fails:
            print(f"  ✗ {f}")

    horizons = planning_horizons()
    patches = [
        patch_costs(df, horizons, dry_run=True),
        patch_potentials(df, horizons, dry_run=True),
        *patch_ntc(df, horizons, dry_run=True),
        patch_walloon_config(build_budget_national(df, horizons), dry_run=True),
    ]
    print(f"input files (planning horizons {list(horizons)}):")
    for p in patches:
        report_patch(p, verbose)
        fails.extend(p.errors)
        fails.extend(f"{p.path.name} out of sync: {c}" for c in p.changes)

    drift = check_archive_drift(df, meta)
    if drift:
        print("technology-data drift (PyPSA-origin rows with no override):")
        for d in drift:
            print(f"      ! {d}")

    if fails:
        print(f"\nCHECK FAILED ({len(fails)} problem(s)) — run --write to re-sync")
        return 1
    print("\nCHECK PASSED")
    return 0


def cmd_write(df: pd.DataFrame, meta: dict, dry_run: bool, verbose: bool) -> int:
    fails = check_currency(df, meta) + check_schema(df)
    if fails:
        print("Refusing to write, master CSV is invalid:")
        for f in fails:
            print(f"  ✗ {f}")
        return 1

    horizons = planning_horizons()
    print(f"{'DRY RUN — ' if dry_run else ''}patching for horizons {list(horizons)}:")
    patches = [
        patch_costs(df, horizons, dry_run),
        patch_potentials(df, horizons, dry_run),
        *patch_ntc(df, horizons, dry_run),
        patch_walloon_config(build_budget_national(df, horizons), dry_run),
    ]
    for p in patches:
        report_patch(p, verbose)

    broken = [p for p in patches if not p.ok]
    if broken:
        print(
            f"\nFAILED: {sum(len(p.errors) for p in broken)} problem(s) in "
            f"{len(broken)} file(s). Nothing was written for those files."
        )
        return 1

    n = sum(len(p.changes) for p in patches)
    print(f"\n{'Would patch' if dry_run else 'Patched'} {n} value(s).")
    if not dry_run:
        print("Review with: git diff data/walloon config/config.walloon.yaml")
    return 0


def cmd_report(df: pd.DataFrame, meta: dict, verbose: bool) -> int:
    horizons = planning_horizons()
    print(
        f"EUR_REF={meta['EUR_REF']}  "
        f"technology-data={meta['technology_data']['tag']}  "
        f"horizons={list(horizons)}  rows={len(df)}"
    )
    print("\nstatus:")
    print(df["status"].value_counts(dropna=False).to_string())
    print("\ndata_origin_choice:")
    print(df["data_origin_choice"].value_counts(dropna=False).to_string())
    mon = df.loc[monetary_mask(df)]
    print(f"\nmonetary rows: {len(mon)} (all EUR{meta['EUR_REF']})")
    print("\nactive target families:")
    act = active_rows(df)
    print(
        act["pypsa_wal_target"].astype(str).str.split(":").str[0]
        .value_counts()
        .to_string()
    )
    for prefix, nparts in (("cost", 2), ("potential", 3), ("ntc", 1)):
        targets = collect_targets(df, prefix, horizons, nparts=nparts)
        by_origin: dict[str, int] = {}
        for t in targets.values():
            by_origin[t.origin] = by_origin.get(t.origin, 0) + 1
        print(f"\n{prefix}: {len(targets)} distinct targets  {by_origin}")
    return cmd_check(df, meta, verbose)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="validate CSV + file sync")
    mode.add_argument("--report", action="store_true", help="summarise the master CSV")
    mode.add_argument("--write", action="store_true", help="patch the input files")
    parser.add_argument(
        "--dry-run", action="store_true", help="with --write: preview, change nothing"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="also list unmanaged rows"
    )
    args = parser.parse_args()

    meta, df = load_meta(), load_master()
    if args.check:
        return cmd_check(df, meta, args.verbose)
    if args.report:
        return cmd_report(df, meta, args.verbose)
    return cmd_write(df, meta, args.dry_run, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
