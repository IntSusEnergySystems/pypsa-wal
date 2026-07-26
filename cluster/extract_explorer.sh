#!/bin/bash
# SPDX-License-Identifier: MIT
###############################################################################
# extract_explorer.sh — Build the Wallonie Explorer CSVs for a solved run
#
# Drives the ClimAct extraction tool (EXTRACTOR_DIR, outside this repo) and
# stages its output into results/<run>/explorer/ so cluster/upload_s3.sh can
# publish it to s3://.../scenarios/<type>__<scenario>__YYYYMMDD/.
#
# Snakemake's own summary CSVs are NOT what the Explorer reads — see
# instructions.md § Publishing to Wallonie Explorer (S3).
#
#   ./cluster/extract_explorer.sh                 # extract + stage all scenarios
#   ./cluster/extract_explorer.sh --dry-run       # show what would run
#   ./cluster/extract_explorer.sh --skip-extract  # re-stage from existing output
#
# Handles both layouts: a single-run config (results/<RUN_NAME>/) and a
# run.prefix + run.scenarios config (results/<prefix>/<scenario>/), driven by
# RUN_PREFIX / EXPLORER_SCENARIOS in config.sh.
#
# The extractor's own config_extraction_*.yaml is treated as read-only: this
# script copies it to EXTRACTOR_GEN_CONFIG with a regenerated `run:` block and
# points the tool at the copy via EXTRACTION_CONFIG.
###############################################################################
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
# shellcheck source=config.sh
source "$HERE/config.sh"

msg()  { printf '\033[1;34m[extract]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[extract] WARNING:\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[extract] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

DRY_RUN=0
SKIP_EXTRACT=0
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run|-n)   DRY_RUN=1; shift ;;
        --skip-extract) SKIP_EXTRACT=1; shift ;;
        -h|--help) sed -n '2,23p' "$0"; exit 0 ;;
        *) die "unknown argument: $1 (try --help)" ;;
    esac
done

ST_DIR="$EXTRACTOR_DIR/analysis/graph_extraction_st/$EXTRACTOR_TAG"
STRATEGY_DIR="$EXTRACTOR_DIR/analysis/strategy/$EXTRACTOR_TAG"
RUN_NICKNAME="${UPLOAD_DATE}_${EXPLORER_TYPE}"

# --- preflight ---------------------------------------------------------------
[ -d "$EXTRACTOR_DIR" ] || die "EXTRACTOR_DIR not found: $EXTRACTOR_DIR (set it in cluster/config.sh)"
[ -f "$EXTRACTOR_DIR/$EXTRACTOR_BASE_CONFIG" ] \
    || die "template config not found: $EXTRACTOR_DIR/$EXTRACTOR_BASE_CONFIG"
[ -f "$EXTRACTOR_DIR/scripts/graph_extraction_main.py" ] \
    || die "not an extraction checkout: $EXTRACTOR_DIR"
conda env list | awk '{print $1}' | grep -qx "$EXTRACTOR_ENV" \
    || die "conda env '$EXTRACTOR_ENV' not found — see instructions.md (needs pypsa 0.35.x)"
grep -q 'EXTRACTION_CONFIG' "$EXTRACTOR_DIR/scripts/graph_extraction_main.py" \
    || die "$EXTRACTOR_DIR/scripts/graph_extraction_main.py does not honour EXTRACTION_CONFIG —
       patch main() to: load_config_extraction(os.environ.get(\"EXTRACTION_CONFIG\", \"config_extraction_OET.yaml\"))"
python3 -c 'import yaml' 2>/dev/null || die "python3 lacks PyYAML — needed to read the run config"

# Each scenario needs solved networks and the config snapshot the extractor reads.
while IFS=$'\t' read -r scen label results_dir upload_id scenario_id; do
    [ -d "$REPO/$results_dir" ] || die "no results tree for '$scen': $results_dir"
    [ -f "$REPO/$results_dir/configs/$EXTRACTOR_CONFIG_FILE" ] \
        || die "missing $results_dir/configs/$EXTRACTOR_CONFIG_FILE (solve did not complete?)"
    n=$(find "$REPO/$results_dir/networks" -name '*.nc' 2>/dev/null | wc -l)
    [ "$n" -gt 0 ] || die "no solved networks under $results_dir/networks/"
    msg "$scen → label '$label' ($n networks), scenario folder $scenario_id"
done < <(explorer_targets)

# --- 1. symlink each results tree into the extractor -------------------------
mkdir -p "$EXTRACTOR_DIR/results"
while IFS=$'\t' read -r scen label results_dir upload_id scenario_id; do
    if [ "$DRY_RUN" -eq 1 ]; then
        msg "(dry-run) ln -sfn $REPO/$results_dir $EXTRACTOR_DIR/results/$upload_id"
    else
        ln -sfn "$REPO/$results_dir" "$EXTRACTOR_DIR/results/$upload_id"
    fi
done < <(explorer_targets)

# --- 2. regenerate the `run:` block into EXTRACTOR_GEN_CONFIG ----------------
# Built as text and spliced in with awk: the block starts at "    run:" and ends
# at the next key indented by exactly four spaces (e.g. "    reference:").
RUN_BLOCK=$(while IFS=$'\t' read -r scen label results_dir upload_id scenario_id; do
    printf '        "%s":\n' "$upload_id"
    printf '          scenario_nickname: "%s"\n' "$label"
    printf '          run_nickname: "%s"\n' "$RUN_NICKNAME"
    printf '          config_file: "%s"\n' "$EXTRACTOR_CONFIG_FILE"
done < <(explorer_targets))

GEN="$EXTRACTOR_DIR/$EXTRACTOR_GEN_CONFIG"
if [ "$DRY_RUN" -eq 1 ]; then
    msg "(dry-run) would write $GEN with run: block:"
    printf '%s\n' "$RUN_BLOCK"
else
    awk -v block="$RUN_BLOCK" '
        /^    run:/     { print "    run:"; print block; inrun=1; next }
        inrun && /^    [^ ]/ { inrun=0 }
        !inrun          { print }
    ' "$EXTRACTOR_DIR/$EXTRACTOR_BASE_CONFIG" > "$GEN"
    grep -q '^    run:' "$GEN" || die "failed to splice run: block into $GEN"
    msg "Wrote $EXTRACTOR_GEN_CONFIG (template: $EXTRACTOR_BASE_CONFIG, left untouched)"
fi

# --- 3. run the extractor once for all scenarios -----------------------------
LOG="$HERE/logs/extract_explorer.log"
mkdir -p "$HERE/logs"
if [ "$DRY_RUN" -eq 1 ]; then
    msg "(dry-run) would run the extractor in env '$EXTRACTOR_ENV' with EXTRACTION_CONFIG=$EXTRACTOR_GEN_CONFIG"
elif [ "$SKIP_EXTRACT" -eq 1 ]; then
    msg "--skip-extract — re-staging from the existing extractor output"
else
    msg "Running ClimAct extraction (env: $EXTRACTOR_ENV, log: $LOG)"
    ( cd "$EXTRACTOR_DIR" && PYTHONPATH=. EXTRACTION_CONFIG="$EXTRACTOR_GEN_CONFIG" MPLBACKEND=Agg \
        conda run --no-capture-output -n "$EXTRACTOR_ENV" python -m scripts.graph_extraction_main ) \
        2>&1 | tee "$LOG"
fi

# --- 4. stage CSVs + the scenario's own TIMES .vd into explorer/ -------------
times_file_for() {
    # sector.times_file for one scenario: the scenarios file overrides the base
    # config, mirroring how Snakemake merges them.
    local scen="$1"
    python3 - "$REPO" "$CONFIGFILE" "$scen" <<'PY'
import sys, pathlib, yaml
repo, configfile, scen = sys.argv[1:4]
base = yaml.safe_load(open(pathlib.Path(repo, configfile), encoding="utf-8")) or {}
vd = (base.get("sector") or {}).get("times_file")
sfile = ((base.get("run") or {}).get("scenarios") or {}).get("file")
if sfile:
    p = pathlib.Path(repo, sfile)
    if p.exists():
        scens = yaml.safe_load(open(p, encoding="utf-8")) or {}
        over = ((scens.get(scen) or {}).get("sector") or {}).get("times_file")
        if over:
            vd = over
print(vd or "")
PY
}

while IFS=$'\t' read -r scen label results_dir upload_id scenario_id; do
    L="${EXPLORER_TYPE}__${label}__${UPLOAD_DATE}"
    D="$REPO/$results_dir/explorer"
    if [ "$DRY_RUN" -eq 1 ]; then
        msg "(dry-run) stage $ST_DIR/$L → $results_dir/explorer/pypsa"
        continue
    fi
    [ -d "$ST_DIR/$L" ] || die "extractor produced no $ST_DIR/$L (check $LOG)"
    mkdir -p "$D/pypsa" "$D/strategy" "$D/times"
    cp "$ST_DIR/$L/"*.csv "$D/pypsa/"
    if [ -d "$STRATEGY_DIR/$L" ]; then
        cp "$STRATEGY_DIR/$L/"*.csv "$D/strategy/"
    else
        warn "no strategy output for $L"
    fi
    vd=$(times_file_for "$scen")
    if [ -n "$vd" ] && [ -f "$REPO/$vd" ]; then
        cp -L "$REPO/$vd" "$D/times/$(basename "$vd")"
    else
        warn "no sector.times_file for '$scen' — the Explorer TIMES tab will be empty"
    fi
    msg "Staged $scen: pypsa=$(ls "$D/pypsa" | wc -l) strategy=$(ls "$D/strategy" | wc -l) times=$(ls "$D/times" | wc -l)"
done < <(explorer_targets)

if [ "$DRY_RUN" -eq 1 ]; then
    msg "Dry run complete (nothing written)."
else
    msg "Extraction complete. Publish with: ./cluster/nic5.sh publish (or upload)"
fi
