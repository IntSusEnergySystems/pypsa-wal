#!/usr/bin/env python3
"""Apply config/input_parameters_for_models.csv to the pypsa-wal input files.

The shared TIMES/PyPSA table is authoritative for the parameters it covers
(see common_parameters.md). This script mostly **patches values in place** in
the files the workflow already reads, so the hand-written structure, sources
and comments of those files survive and ``git diff`` shows exactly what the
shared table changed.

Exception: ``data/walloon/discount_rates.csv`` (and any
``discount_rates_<variant>.csv``) is **generated wholesale** from the
``hurdle:*`` rows plus ``config/hurdle_rate_mapping.csv`` — it is still
committed, but row count may change when the technology universe moves.

    config/input_parameters_for_models.csv        (authoritative values)
                │
                ├─► data/walloon/custom_costs.csv          cost:<tech>:<param>
                ├─► data/walloon/custom_potentials.csv     potential:<bus>:<tech>:<attr>
                ├─► data/walloon/ntc_<year>.csv            ntc:<A>-<B>
                ├─► data/walloon/agg_p_nom_minmax_demande_haute.csv
                │                                          agg:<country>:<carrier>:<min|max>
                ├─► data/walloon/discount_rates.csv        hurdle:<sector>  [generated]
                └─► config/config.walloon.yaml             config:budget_national
                                                           + costs.social_discountrate (from CSV)
                                                           fill_values stay at PyPSA defaults

Failsafe (patched files only): a patch may only rewrite the ``value`` cell of
an existing row. If the row count or the row keys change, or a row would have
to be added or removed, the run aborts and reports what needs a manual edit
instead.

Modes:
    --check   validate the master CSV and verify the input files are in sync
    --report  summarise the master CSV
    --write   patch / generate the input files (use --dry-run to preview)
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
DEFAULT_CONFIG = ROOT / "config" / "config.default.yaml"
COSTS_FILE = ROOT / "data" / "walloon" / "custom_costs.csv"
POTENTIALS_FILE = ROOT / "data" / "walloon" / "custom_potentials.csv"
# TIMES-aligned nuclear (and other) country/carrier caps for scen_demande_haute.
# Other scenarios keep their own agg files; this patch does not touch them --
# which is why the decimal-shift typos of 2026-08-26 were in the *unmanaged*
# base/corrige files. Proposed fix (not implemented): per-scenario override files
# layered on the master table, see docs/scenario-handling-proposal.md.
AGG_FILE = ROOT / "data" / "walloon" / "agg_p_nom_minmax_demande_haute.csv"
NTC_GLOB = "ntc_*.csv"
COST_ARCHIVE_GLOB = "costs_*.csv"
COST_TABLE_RENAMES = {"solar-utility single-axis tracking": "solar-hsat"}
COST_TABLE_CLONES = {"waste": "waste CHP"}
HURDLE_MAPPING_FILE = ROOT / "config" / "hurdle_rate_mapping.csv"
DISCOUNT_RATES_FILE = ROOT / "data" / "walloon" / "discount_rates.csv"
# TIMES-WAL ~TFM_INS NCAP_DRATE process groups, one hurdle:<sector> row each.
# Mapping to the Pset_Set names lives in config/hurdle_rate_mapping.csv
# (times_pset_set column) and in docs/discount-rates.md.
HURDLE_SECTORS = (
    "supply",  # SUP-processes
    "power",  # ELC-PUB
    "chp",  # ALL-CHP
    "pv",  # ALL-PV
    "transport",  # TRA-processes
    "industry",  # IND-process / IND-processNE
    "tertiary",  # COM-processes
    "agriculture",  # AGR-processes
    "residential",  # RSD-processes
    "residential_reno",  # RSD-RENO — config target, no cost-table technology
    "tertiary_reno",  # COM-RENO — config target, no cost-table technology
)
VARIANT_NAME_RE = re.compile(r"^[a-z0-9_]+$")
COST_CONFIG_FILES = (WALLOON_CONFIG,)

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
    soft_errors: list[str] = field(default_factory=list)
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


def _parse_agg_header(lines: list[str]) -> list[tuple[str, str]]:
    """Year/bound pairs from the three-line header of an agg_p_nom_minmax CSV."""
    if len(lines) < 3:
        raise ValueError("agg file shorter than 3 header lines")
    years = lines[0].split(",")[2:]
    bounds = lines[1].split(",")[2:]
    if len(years) != len(bounds):
        raise ValueError(
            f"agg header year/bound length mismatch {len(years)} vs {len(bounds)}"
        )
    return list(zip(years, bounds))


def patch_agg_p_nom(
    df: pd.DataFrame,
    horizons: tuple[int, ...],
    dry_run: bool,
    path: Path | None = None,
) -> Patch:
    """Patch BE/BEWAL nuclear (etc.) caps in the demande-haute agg file.

    Target shape: ``agg:<country>:<carrier>:<min|max>``. Only *explicit* CSV
    anchor years are written (``Target.anchors``), so 2025/2030 stay empty
    when the table has no row for them — ``expand_years`` would otherwise
    hold-forward the first cap onto the legacy-fleet horizons. Extra dest
    columns such as 2035/2045 are patched when the table anchors them.
    """
    path = path or AGG_FILE
    patch = Patch(path=path)
    targets = collect_targets(df, "agg", horizons, nparts=3)
    if not targets:
        return patch
    if not path.exists():
        patch.errors.append(f"{path.name}: missing, cannot apply agg: targets")
        return patch

    raw = path.read_text()
    newline = "\r\n" if "\r\n" in raw[:4096] else "\n"
    lines = raw.splitlines()
    try:
        columns = _parse_agg_header(lines)
    except ValueError as exc:
        patch.errors.append(f"{path.name}: {exc}")
        return patch
    patch.rows = max(len(lines) - 3, 0)

    col_index: dict[tuple[str, str], int] = {}
    for i, (year, bound) in enumerate(columns):
        col_index[(str(year), bound)] = i

    # country,carrier -> line index in `lines`
    row_at: dict[tuple[str, str], int] = {}
    for i, line in enumerate(lines[3:], start=3):
        parts = line.split(",")
        if len(parts) < 2:
            continue
        row_at[(parts[0], parts[1])] = i

    seen: set[tuple[str, ...]] = set()
    for key, tgt in sorted(targets.items()):
        country, carrier, bound = key
        if bound not in ("min", "max"):
            patch.errors.append(
                f"{path.name}: agg:{tgt.label} bound must be min or max, not {bound!r}"
            )
            continue
        if not units_compatible(tgt.unit, "MW"):
            patch.errors.append(
                f"{path.name}: unit mismatch for agg:{tgt.label}: master CSV "
                f"{tgt.unit!r} vs file MW_e — scales differ, refusing to patch"
            )
            continue
        loc = (country, carrier)
        if loc not in row_at:
            patch.errors.append(
                f"{path.name}: no {country},{carrier} row for active target "
                f"agg:{tgt.label} — add it to the file or set status=none"
            )
            continue
        seen.add(key)
        patch.managed += 1
        li = row_at[loc]
        cells = lines[li].split(",")
        # pad so index+value cells cover every header column
        need = 2 + len(columns)
        if len(cells) < need:
            cells.extend([""] * (need - len(cells)))
        for year, val in sorted(tgt.anchors.items()):
            idx = col_index.get((str(year), bound))
            if idx is None:
                patch.errors.append(
                    f"{path.name}: no {year}/{bound} column for agg:{tgt.label}"
                )
                continue
            new = fmt_value(val)
            old = cells[2 + idx]
            if old and same_value(old, val):
                continue
            patch.changes.append(
                f"{country} {carrier} {year} {bound}: "
                f"{old or '(empty)'} -> {new} MW"
            )
            cells[2 + idx] = new
        lines[li] = ",".join(cells)

    if not dry_run and patch.ok and patch.changes:
        path.write_text(newline.join(lines) + newline)
    return patch


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


def patch_walloon_config(
    budget: dict[int, dict[str, float]], dry_run: bool, config: Path = WALLOON_CONFIG
) -> Patch:
    """Rewrite the `budget_national:` block of a config file in place."""
    patch = Patch(path=config)
    text = config.read_text()
    # The block runs from `budget_national:` to the next top-level key.
    m = re.search(r"^budget_national:\n(?:[ \t].*\n|\n)*", text, flags=re.MULTILINE)
    if not m:
        patch.errors.append(f"{config.name}: no `budget_national:` block found")
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
        config.write_text(text[: m.start()] + new + trailing + text[m.end() :])
    return patch


# --------------------------------------------------------------------------- #
# discount / hurdle rates (generated file)
# --------------------------------------------------------------------------- #
def _default_max_hours() -> dict:
    """electricity.max_hours from config.default.yaml (walloon config omits it)."""
    cfg = yaml.safe_load(DEFAULT_CONFIG.read_text())
    return dict(cfg["electricity"]["max_hours"])


def pypsa_default_discount_rate() -> float:
    """Financial discount-rate fill from config.default.yaml (PyPSA default, 0.07)."""
    cfg = yaml.safe_load(DEFAULT_CONFIG.read_text())
    return float(cfg["costs"]["fill_values"]["discount rate"])


def pypsa_default_social_discountrate() -> float:
    """Social discount rate from config.default.yaml (PyPSA default, 0.02)."""
    cfg = yaml.safe_load(DEFAULT_CONFIG.read_text())
    return float(cfg["costs"]["social_discountrate"])


def _store_lookup_keys() -> set[str]:
    """Top-level keys of STORE_LOOKUP without importing add_electricity (heavy)."""
    text = (ROOT / "scripts" / "add_electricity.py").read_text()
    m = re.search(r"^STORE_LOOKUP\s*=\s*\{(.*?)^\}", text, flags=re.M | re.S)
    if not m:
        raise RuntimeError("STORE_LOOKUP not found in scripts/add_electricity.py")
    # Only top-level entries (value is a dict); skip nested "store"/"bicharger"/…
    return set(re.findall(r'^\s*"([^"]+)"\s*:\s*\{', m.group(1), flags=re.M))


def cost_table_technologies(meta: dict) -> set[str]:
    """Every technology key the processed cost table will contain.

    Mirrors the transformations in process_cost_data.py — keep in sync; test T1
    cross-checks against a real processed CSV when one exists.
    """
    archive = ROOT / meta["technology_data"]["archive_dir"]
    techs: set[str] = set()
    for path in sorted(archive.glob(COST_ARCHIVE_GLOB)):
        techs |= set(pd.read_csv(path)["technology"].dropna().unique())

    # custom_costs.csv may add technologies (process_cost_data.py:62-64)
    techs |= set(_read_str(COSTS_FILE)["technology"]) - {"all"}

    for old, new in COST_TABLE_RENAMES.items():
        techs.discard(old)
        techs.add(new)
    techs |= set(COST_TABLE_CLONES)

    cfg = yaml.safe_load(WALLOON_CONFIG.read_text())
    max_hours = cfg.get("electricity", {}).get("max_hours") or _default_max_hours()
    techs |= {k for k in max_hours if k in _store_lookup_keys()}
    return techs


@dataclass
class HurdleResolution:
    rates: dict[str, dict[int, float]]  # technology -> {horizon: rate}
    sectors: dict[str, str]  # technology -> sector (or "none" / "fallback")
    unmapped: list[str]  # in universe, absent from mapping
    unknown_sector: list[str]  # mapping names a sector with no rate
    stale: list[str]  # mapping row for tech not in universe
    fallback: dict[int, float]


def hurdle_variants(
    df: pd.DataFrame, horizons: tuple[int, ...]
) -> dict[str | None, dict[str, Target]]:
    """Sector rates per variant. Key None is the base; a variant inherits any
    sector it does not override."""
    base = collect_targets(df, "hurdle", horizons, nparts=1)  # hurdle:<sector>
    out: dict[str | None, dict[str, Target]] = {
        None: {k[0]: v for k, v in base.items()}
    }
    for (variant, sector), tgt in collect_targets(
        df, "hurdle", horizons, nparts=2  # hurdle:<var>:<sector>
    ).items():
        out.setdefault(variant, dict(out[None]))[sector] = tgt
    return out


def variant_path(variant: str | None) -> Path:
    return (
        DISCOUNT_RATES_FILE
        if variant is None
        else DISCOUNT_RATES_FILE.with_name(f"discount_rates_{variant}.csv")
    )


def resolve_hurdle_rates(
    df: pd.DataFrame,
    meta: dict,
    horizons: tuple[int, ...],
    sector_rates: dict[str, Target],
) -> HurdleResolution:
    """Resolve per-technology rates for one variant's sector_rates map."""
    per_tech = {
        k[0]: t
        for k, t in collect_targets(df, "cost", horizons, nparts=2).items()
        if k[1] == "discount rate"
    }
    # Unmapped techs fall back to the PyPSA default fill (config.default.yaml),
    # not a TIMES-negotiated rate — that lives only in hurdle:<sector> rows.
    fb = pypsa_default_discount_rate()
    fallback = {h: fb for h in horizons}

    mapping = pd.read_csv(HURDLE_MAPPING_FILE, dtype=str, keep_default_na=False)
    universe = cost_table_technologies(meta)
    mapped = set(mapping["technology"])

    unmapped = sorted(universe - mapped)
    stale = sorted(mapped - universe)

    rates: dict[str, dict[int, float]] = {}
    sectors: dict[str, str] = {}
    unknown_sector: list[str] = []

    for _, row in mapping.iterrows():
        tech = row["technology"]
        sector = row["hurdle_sector"]
        if tech not in universe:
            continue
        if sector == "none":
            sectors[tech] = "none"
            continue
        if tech in per_tech:
            rates[tech] = dict(per_tech[tech].values)
            sectors[tech] = f"override/{sector}"
            continue
        tgt = sector_rates.get(sector)
        if tgt is None:
            unknown_sector.append(tech)
            sectors[tech] = sector
            continue
        rates[tech] = dict(tgt.values)
        sectors[tech] = sector

    # Unmapped technologies get the PyPSA default (soft error); still emit a row.
    for tech in unmapped:
        rates[tech] = dict(fallback)
        sectors[tech] = "fallback"

    # Per-tech overrides for technologies not in the mapping still apply.
    for tech, tgt in per_tech.items():
        if tech in rates:
            continue
        if tech not in universe:
            continue
        rates[tech] = dict(tgt.values)
        sectors[tech] = "override"

    return HurdleResolution(
        rates=rates,
        sectors=sectors,
        unmapped=unmapped,
        unknown_sector=sorted(unknown_sector),
        stale=stale,
        fallback=fallback,
    )


def _rates_frame(resolution: HurdleResolution) -> pd.DataFrame:
    """Build the discount_rates.csv body from a resolution (sorted by tech)."""
    rows: list[dict[str, str]] = []
    for tech in sorted(resolution.rates):
        sector = resolution.sectors.get(tech, "")
        if sector == "none":
            continue
        values = resolution.rates[tech]
        if sector.startswith("override"):
            banner = "master CSV cost:<tech>:discount rate override"
        elif sector == "fallback":
            banner = "fallback (unmapped; PyPSA default fill_values discount rate)"
        else:
            banner = f"TIMES hurdle: {sector}"
        constant = all(abs(v - next(iter(values.values()))) < 1e-9 for v in values.values())
        if constant:
            horizons_iter: list[tuple[str, float]] = [
                ("all", next(iter(values.values())))
            ]
        else:
            horizons_iter = [(str(y), values[y]) for y in sorted(values)]
        for ph, val in horizons_iter:
            rows.append(
                {
                    "planning_horizon": ph,
                    "technology": tech,
                    "parameter": "discount rate",
                    "value": fmt_value(val),
                    "unit": "per unit",
                    "source": "input_parameters_for_models.csv",
                    "further_description": banner,
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "planning_horizon",
            "technology",
            "parameter",
            "value",
            "unit",
            "source",
            "further_description",
        ],
    )


def _write_generated(path: Path, frame: pd.DataFrame) -> None:
    """Wholesale write of a generated CSV (row count may change)."""
    nl = _newline(path) if path.exists() else "\n"
    frame.to_csv(path, index=False, lineterminator=nl)


def _frame_csv_text(frame: pd.DataFrame, newline: str = "\n") -> str:
    return frame.to_csv(index=False, lineterminator=newline)


def _validate_hurdle_prerequisites(
    df: pd.DataFrame, horizons: tuple[int, ...]
) -> list[str]:
    """Hard-error checks that block any discount_rates write."""
    hard: list[str] = []

    try:
        fb = pypsa_default_discount_rate()
    except (KeyError, TypeError, ValueError) as exc:
        hard.append(
            f"{DEFAULT_CONFIG.relative_to(ROOT)}: cannot read "
            f"costs.fill_values.'discount rate' (PyPSA fallback): {exc}"
        )
        fb = None
    else:
        if not (0.0 <= fb < 0.30):
            hard.append(
                f"{DEFAULT_CONFIG.relative_to(ROOT)}: costs.fill_values."
                f"'discount rate'={fb} outside 0 ≤ r < 0.30"
            )

    if COSTS_FILE.exists():
        costs = _read_str(COSTS_FILE)
        if (costs["parameter"] == "discount rate").any():
            hard.append(
                f"{COSTS_FILE.relative_to(ROOT)}: contains a 'discount rate' row — "
                "per-technology rates must live only in discount_rates.csv "
                "(remove the custom_costs row)"
            )

    if not HURDLE_MAPPING_FILE.exists():
        hard.append(f"missing mapping file: {HURDLE_MAPPING_FILE.relative_to(ROOT)}")
        return hard

    mapping = pd.read_csv(HURDLE_MAPPING_FILE, dtype=str, keep_default_na=False)
    if mapping["technology"].duplicated().any():
        dups = sorted(mapping.loc[mapping["technology"].duplicated(), "technology"].unique())
        hard.append(
            f"{HURDLE_MAPPING_FILE.relative_to(ROOT)}: duplicate technology row(s): "
            + ", ".join(dups)
        )

    allowed = set(HURDLE_SECTORS) | {"none"}
    bad_sector = sorted(
        {s for s in mapping["hurdle_sector"] if s not in allowed}
    )
    if bad_sector:
        hard.append(
            f"{HURDLE_MAPPING_FILE.relative_to(ROOT)}: invalid hurdle_sector "
            f"(not in {'|'.join(sorted(allowed))}): {', '.join(bad_sector)}"
        )

    variants = hurdle_variants(df, horizons)
    base_sectors = variants[None]
    for sector, tgt in base_sectors.items():
        if sector not in HURDLE_SECTORS:
            hard.append(f"hurdle:{sector}: sector not in {HURDLE_SECTORS}")
            continue
        for y, r in tgt.values.items():
            if not (0.0 <= r < 0.30):
                hard.append(
                    f"hurdle:{sector} @ {y}: rate {r} outside 0 ≤ r < 0.30 "
                    "(did you mean a fraction, e.g. 0.075 not 7.5?)"
                )

    for variant, sectors in variants.items():
        if variant is None:
            continue
        if not VARIANT_NAME_RE.fullmatch(variant):
            hard.append(
                f"hurdle variant {variant!r}: name must match [a-z0-9_]+ "
                "(it becomes part of the filename)"
            )
        for sector, tgt in sectors.items():
            if sector not in HURDLE_SECTORS:
                hard.append(
                    f"hurdle:{variant}:{sector}: sector not in {HURDLE_SECTORS}"
                )
            for y, r in tgt.values.items():
                if not (0.0 <= r < 0.30):
                    hard.append(
                        f"hurdle:{variant}:{sector} @ {y}: rate {r} outside "
                        "0 ≤ r < 0.30"
                    )

    # Mapping names a sector that has no active hurdle rate in the base.
    used = set(mapping["hurdle_sector"]) - {"none"}
    missing_rates = sorted(used - set(base_sectors))
    if missing_rates:
        hard.append(
            "mapping names hurdle_sector(s) with no active hurdle:<sector> row: "
            + ", ".join(missing_rates)
        )

    return hard


def patch_discount_rates(
    df: pd.DataFrame, meta: dict, horizons: tuple[int, ...], dry_run: bool
) -> list[Patch]:
    """Validate, generate, and optionally write discount_rates.csv (+ variants)."""
    hard = _validate_hurdle_prerequisites(df, horizons)
    variants = hurdle_variants(df, horizons)
    patches: list[Patch] = []

    # One Patch per variant file; hard prerequisites attach to the base path.
    if hard:
        patch = Patch(path=DISCOUNT_RATES_FILE)
        patch.errors.extend(hard)
        patches.append(patch)
        return patches

    soft_shared: list[str] = []
    for variant, sector_rates in variants.items():
        path = variant_path(variant)
        patch = Patch(path=path)
        resolution = resolve_hurdle_rates(df, meta, horizons, sector_rates)

        if resolution.unknown_sector:
            patch.errors.append(
                f"{path.relative_to(ROOT)}: mapping names sector(s) with no "
                f"active rate for: {', '.join(resolution.unknown_sector)}"
            )

        # Soft: unmapped → still write fallback rows, but fail the run.
        if resolution.unmapped:
            fb = next(iter(resolution.fallback.values())) if resolution.fallback else float("nan")
            msg = (
                f"{path.relative_to(ROOT)}: {len(resolution.unmapped)} technology(ies) "
                f"have no row in {HURDLE_MAPPING_FILE.relative_to(ROOT)} — the fallback "
                f"rate {fmt_value(fb)} was written for them:\n"
                + "\n".join(f"  - {t}" for t in resolution.unmapped)
                + "\nAdd each to config/hurdle_rate_mapping.csv with one of "
                f"{'|'.join(HURDLE_SECTORS)}, or hurdle_sector=none "
                "if a rate is inert."
            )
            soft_shared.append(msg)
            patch.notes.append(msg)

        if resolution.stale:
            msg = (
                f"{path.relative_to(ROOT)}: {len(resolution.stale)} mapping row(s) "
                f"for technolog(ies) not in the cost-table universe:\n"
                + "\n".join(f"  - {t}" for t in resolution.stale)
                + "\nRemove them from config/hurdle_rate_mapping.csv or fix the name."
            )
            soft_shared.append(msg)
            patch.notes.append(msg)

        if patch.errors:
            patches.append(patch)
            continue

        frame = _rates_frame(resolution)
        patch.rows = len(frame)
        patch.managed = len(frame)

        # Sector counts for the report.
        counts: dict[str, int] = {}
        for tech, sector in resolution.sectors.items():
            if sector == "none" or tech not in resolution.rates:
                if sector == "none":
                    counts["none"] = counts.get("none", 0) + 1
                continue
            key = sector.split("/")[-1] if sector.startswith("override/") else sector
            counts[key] = counts.get(key, 0) + 1
        patch.notes.append(
            "sector counts: "
            + ", ".join(f"{k}={counts[k]}" for k in sorted(counts))
        )

        expected = _frame_csv_text(frame)
        if path.exists():
            current = path.read_text()
            # Normalise line endings for comparison.
            cur_norm = current.replace("\r\n", "\n")
            exp_norm = expected.replace("\r\n", "\n")
            if cur_norm != exp_norm:
                patch.changes.append(
                    f"regenerated content differs from committed file "
                    f"({len(frame)} row(s))"
                )
        else:
            patch.changes.append(f"file missing — would write {len(frame)} row(s)")

        if not dry_run and patch.ok:
            _write_generated(path, frame)
            # After a successful write, clear "out of sync" changes for write mode
            # reporting: still record that we wrote.
            if patch.changes:
                patch.changes = [f"wrote {len(frame)} row(s)"]

        patches.append(patch)

    # Soft errors are attached once (same list for every variant); surface on
    # the base patch so --check / --write exit 1 without blocking the write.
    if soft_shared and patches:
        seen: set[str] = set()
        for msg in soft_shared:
            key = msg.split(": ", 1)[-1]
            if key in seen:
                continue
            seen.add(key)
            patches[0].soft_errors.append(msg)

    return patches


def _costs_block_span(text: str) -> tuple[int, int] | None:
    """Return [start, end) of the top-level `costs:` block in a YAML file."""
    m = re.search(r"^costs:\n(?:[ \t].*\n|\n)*", text, flags=re.MULTILINE)
    if not m:
        return None
    return m.start(), m.end()


def _patch_yaml_scalar(
    text: str, block: tuple[int, int], pattern: str, new_value: str, key_hint: str
) -> tuple[str, str | None, str | None]:
    """Rewrite one scalar inside a YAML block. Returns (text, change, error).

    ``pattern`` must have group 1 = line prefix through the colon/space and
    group 2 = the value token to replace.
    """
    start, end = block
    body = text[start:end]
    m = re.search(pattern, body, flags=re.MULTILINE)
    if not m:
        return text, None, f"missing key {key_hint}"
    old = m.group(0)
    rebuilt = old[: m.start(2) - m.start()] + new_value + old[m.end(2) - m.start() :]
    if rebuilt == old:
        return text, None, None
    new_body = body[: m.start()] + rebuilt + body[m.end() :]
    return (
        text[:start] + new_body + text[end:],
        f"{key_hint}: {m.group(2)} -> {new_value}",
        None,
    )


def _insert_social_discountrate(text: str, span: tuple[int, int], sdr: str) -> str:
    """Insert ``social_discountrate:`` into the costs block (after hurdle_rate_fn)."""
    start, end = span
    body = text[start:end]
    line = f"  social_discountrate: {sdr}\n"
    m = re.search(r"^[ \t]*hurdle_rate_fn:[^\n]*\n", body, flags=re.MULTILINE)
    if m:
        body = body[: m.end()] + line + body[m.end() :]
    else:
        # After the `costs:` line.
        nl = body.find("\n")
        body = body[: nl + 1] + line + body[nl + 1 :]
    return text[:start] + body + text[end:]


def patch_costs_scalars(
    df: pd.DataFrame, horizons: tuple[int, ...], dry_run: bool
) -> list[Patch]:
    """Sync ``costs.social_discountrate`` from the master CSV into the walloon config.

    ``fill_values`` (including the financial discount-rate fallback) stay at the
    PyPSA defaults in ``config.default.yaml`` — the walloon overlay must not override
    them. TIMES-negotiated financial rates live only in ``discount_rates.csv``.
    """
    sdr_tgt = collect_targets(df, "config", horizons, nparts=1).get(
        ("costs.social_discountrate",)
    )
    pypsa_fb = pypsa_default_discount_rate()

    patches: list[Patch] = []
    for path in COST_CONFIG_FILES:
        patch = Patch(path=path)
        text = path.read_text()
        span = _costs_block_span(text)
        if span is None:
            patch.errors.append(f"{path.name}: no top-level `costs:` block found")
            patches.append(patch)
            continue

        block = text[span[0] : span[1]]
        if "hurdle_rate_fn:" not in block:
            patch.errors.append(
                f"{path.name}: costs block is missing hurdle_rate_fn — add:\n"
                "  hurdle_rate_fn: data/walloon/discount_rates.csv"
            )

        # Walloon overlays must not override the PyPSA fill_values discount rate.
        cfg = yaml.safe_load(text)
        ov = (cfg.get("costs") or {}).get("fill_values") or {}
        if "discount rate" in ov and float(ov["discount rate"]) != pypsa_fb:
            patch.errors.append(
                f"{path.name}: costs.fill_values.'discount rate'="
                f"{ov['discount rate']} overrides the PyPSA default {pypsa_fb}. "
                "Remove the override — unmapped technologies use the PyPSA fill, "
                "and TIMES hurdles live in data/walloon/discount_rates.csv."
            )

        if sdr_tgt is None:
            patch.errors.append(
                "master CSV has no active config:costs.social_discountrate row"
            )
        elif not sdr_tgt.constant:
            patch.errors.append(
                "config:costs.social_discountrate varies by horizon; "
                "the YAML scalar can only hold a single value"
            )
        else:
            sdr = fmt_value(next(iter(sdr_tgt.values.values())))
            text2, change, err = _patch_yaml_scalar(
                text,
                span,
                r"^([ \t]*social_discountrate:\s*)([^\s#]+)",
                sdr,
                "costs.social_discountrate",
            )
            if err:
                text = _insert_social_discountrate(text, span, sdr)
                span = _costs_block_span(text) or span
                patch.changes.append(f"costs.social_discountrate: (inserted) {sdr}")
            else:
                text = text2
                span = _costs_block_span(text) or span
                if change:
                    patch.changes.append(change)
                else:
                    patch.notes.append("social_discountrate already in sync")

        if not dry_run and patch.ok and patch.changes:
            path.write_text(text)
        patches.append(patch)
    return patches


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
    if patch.errors:
        state = "FAIL"
    elif patch.soft_errors:
        state = "WARN"
    elif patch.changes:
        state = "update"
    else:
        state = "in sync"
    print(f"  {rel}  [{state}]  rows={patch.rows} managed={patch.managed}")
    for c in patch.changes:
        print(f"      ~ {c}")
    for e in patch.errors:
        print(f"      ✗ {e}")
    for e in patch.soft_errors:
        print(f"      ! {e}")
    if verbose:
        for n in patch.notes:
            print(f"      · {n}")
    elif any(n.startswith("sector counts:") for n in patch.notes):
        for n in patch.notes:
            if n.startswith("sector counts:"):
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
        patch_agg_p_nom(df, horizons, dry_run=True),
        *[
            patch_walloon_config(build_budget_national(df, horizons), True, cfg)
            for cfg in COST_CONFIG_FILES
        ],
        *patch_costs_scalars(df, horizons, dry_run=True),
        *patch_discount_rates(df, meta, horizons, dry_run=True),
    ]
    print(f"input files (planning horizons {list(horizons)}):")
    for p in patches:
        report_patch(p, verbose)
        fails.extend(p.errors)
        fails.extend(p.soft_errors)
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
        patch_agg_p_nom(df, horizons, dry_run),
        *[
            patch_walloon_config(build_budget_national(df, horizons), dry_run, cfg)
            for cfg in COST_CONFIG_FILES
        ],
        *patch_costs_scalars(df, horizons, dry_run),
        *patch_discount_rates(df, meta, horizons, dry_run),
    ]
    for p in patches:
        report_patch(p, verbose)

    broken = [p for p in patches if not p.ok]
    soft = [p for p in patches if p.soft_errors]
    if broken:
        print(
            f"\nFAILED: {sum(len(p.errors) for p in broken)} problem(s) in "
            f"{len(broken)} file(s). Nothing was written for those files."
        )
        return 1

    n = sum(len(p.changes) for p in patches)
    print(f"\n{'Would patch' if dry_run else 'Patched'} {n} value(s).")
    if soft:
        n_soft = sum(len(p.soft_errors) for p in soft)
        print(
            f"WARNING: {n_soft} soft error(s) — discount_rates written with "
            "fallback where needed; fix mapping and re-run."
        )
        return 1
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
    for prefix, nparts in (
        ("cost", 2),
        ("potential", 3),
        ("ntc", 1),
        ("agg", 3),
        ("hurdle", 1),
    ):
        targets = collect_targets(df, prefix, horizons, nparts=nparts)
        by_origin: dict[str, int] = {}
        for t in targets.values():
            by_origin[t.origin] = by_origin.get(t.origin, 0) + 1
        print(f"\n{prefix}: {len(targets)} distinct targets  {by_origin}")

    # Hurdle mapping sector counts (technology universe).
    if HURDLE_MAPPING_FILE.exists():
        mapping = pd.read_csv(HURDLE_MAPPING_FILE, dtype=str, keep_default_na=False)
        print("\nhurdle mapping sector counts:")
        print(mapping["hurdle_sector"].value_counts().to_string())
        universe = cost_table_technologies(meta)
        print(
            f"\ncost-table universe: {len(universe)} technologies  "
            f"mapping: {len(mapping)} row(s)"
        )

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
