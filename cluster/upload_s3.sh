#!/bin/bash
# SPDX-License-Identifier: MIT
###############################################################################
# upload_s3.sh — Publish post-processed PyPSA-Wal results to Intervectoriel S3
#
# Uploads the local results/ tree to the Wallonie Explorer bucket, following
# the layout already used on s3://intervectoriel/test/pypsa_raw_results/.
#
# Standalone:
#   ./cluster/upload_s3.sh              # upload to test/
#   ./cluster/upload_s3.sh --dry-run    # show what would be synced
#
# Environment overrides (also set in cluster/config.sh):
#   S3_ENV=test|prod          bucket prefix (default: test)
#   UPLOAD_ID=20260717_walloon-model   S3 folder name under pypsa_raw_results/
#   SCENARIO_ID=pypsa__walloon-model__20260717  Explorer scenario folder (optional)
#   UPLOAD_SKIP_NETWORKS=1    skip large .nc files (quick connectivity test)
#   SKIP_S3_UPLOAD=1          no-op (used by nic5.sh postprocess to opt out)
#
# Requires AWS CLI profile with write access (see instructions.md).
###############################################################################
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
# shellcheck source=config.sh
source "$HERE/config.sh"

DRY_RUN=0
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run|-n) DRY_RUN=1; shift ;;
        -h|--help)
            sed -n '2,22p' "$0"
            exit 0
            ;;
        *) die "unknown argument: $1 (try --help)" ;;
    esac
done

msg()  { printf '\033[1;34m[upload]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[upload] WARNING:\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[upload] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }

RESULTS_DIR="$REPO/results/${RUN_NAME}"
UPLOAD_DATE="${UPLOAD_DATE:-$(date +%Y%m%d)}"
UPLOAD_ID="${UPLOAD_ID:-${UPLOAD_DATE}_${RUN_NAME}}"
SCENARIO_ID="${SCENARIO_ID:-pypsa__${RUN_NAME}__${UPLOAD_DATE}}"
EXPLORER_SRC="${EXPLORER_SRC:-$RESULTS_DIR/explorer/pypsa}"
EXPLORER_STRATEGY_SRC="${EXPLORER_STRATEGY_SRC:-$RESULTS_DIR/explorer/strategy}"
EXPLORER_TIMES_SRC="${EXPLORER_TIMES_SRC:-$RESULTS_DIR/explorer/times}"

aws_cmd() {
    export PATH="${HOME}/.local/bin:${PATH}"
    export AWS_PROFILE="${AWS_PROFILE}"
    aws --region "$AWS_REGION" "$@"
}

write_run_json() {
    local dest="$1"
    mkdir -p "$(dirname "$dest")"
    local git_commit git_branch
    git_commit="$(git -C "$REPO" rev-parse HEAD 2>/dev/null || echo unknown)"
    git_branch="$(git -C "$REPO" symbolic-ref --short HEAD 2>/dev/null || echo unknown)"
    cat >"$dest" <<EOF
{
  "run_name": "${RUN_NAME}",
  "upload_id": "${UPLOAD_ID}",
  "scenario_id": "${SCENARIO_ID}",
  "uploaded_at": "$(date -Is)",
  "configfile": "${CONFIGFILE}",
  "git_commit": "${git_commit}",
  "git_branch": "${git_branch}",
  "horizons": "$(echo "$HORIZONS" | tr ' ' ',')",
  "s3_env": "${S3_ENV}",
  "s3_bucket": "${S3_BUCKET}",
  "s3_raw_prefix": "${S3_ENV}/pypsa_raw_results/${UPLOAD_ID}/",
  "s3_scenario_prefix": "${S3_ENV}/scenarios/${SCENARIO_ID}/pypsa/"
}
EOF
}

snapshot_config() {
    local cfg_dir="$RESULTS_DIR/configs"
    mkdir -p "$cfg_dir"
    if [ -f "$REPO/$CONFIGFILE" ]; then
        cp "$REPO/$CONFIGFILE" "$cfg_dir/config.${RUN_NAME}.yaml"
    fi
}

sync_results() {
    local src="$1" dest="$2"
    local -a extra=()
    extra+=(--exclude ".DS_Store" --exclude "*/.DS_Store")
    if [ "${UPLOAD_SKIP_NETWORKS:-0}" = "1" ]; then
        extra+=(--exclude "networks/*.nc")
        warn "UPLOAD_SKIP_NETWORKS=1 — .nc network files will not be uploaded"
    fi
    if [ "$DRY_RUN" -eq 1 ]; then
        extra+=(--dryrun)
    fi
    msg "Sync $src → s3://${S3_BUCKET}/${dest}"
    aws_cmd s3 sync "$src" "s3://${S3_BUCKET}/${dest}" "${extra[@]}"
}

cmd_upload() {
    if [ "${SKIP_S3_UPLOAD:-0}" = "1" ]; then
        msg "SKIP_S3_UPLOAD=1 — upload skipped"
        return 0
    fi

    [ -d "$RESULTS_DIR" ] || die "results directory not found: $RESULTS_DIR"

    if ! command -v aws >/dev/null 2>&1; then
        die "aws CLI not found — install it and ensure ~/.local/bin is on PATH"
    fi

    msg "Checking AWS credentials (profile: $AWS_PROFILE)"
    if ! aws_cmd sts get-caller-identity >/dev/null 2>&1; then
        die "AWS credentials failed — configure profile '$AWS_PROFILE' (see instructions.md)"
    fi

    snapshot_config
    write_run_json "$RESULTS_DIR/run.json"

    local raw_dest="${S3_ENV}/pypsa_raw_results/${UPLOAD_ID}/"
    sync_results "$RESULTS_DIR/" "$raw_dest"

    if [ -d "$EXPLORER_SRC" ] && [ -n "$(find "$EXPLORER_SRC" -maxdepth 1 -type f -name '*.csv' -print -quit 2>/dev/null)" ]; then
        local scenario_dest="${S3_ENV}/scenarios/${SCENARIO_ID}/pypsa/"
        sync_results "$EXPLORER_SRC/" "$scenario_dest"
        msg "Explorer CSVs uploaded to s3://${S3_BUCKET}/${scenario_dest}"
    else
        warn "No Explorer CSV export at $EXPLORER_SRC — only raw results uploaded."
        warn "To appear in the Wallonie Explorer scenario list, export CSVs there first."
        warn "See instructions.md § Publishing to Wallonie Explorer."
    fi

    if [ -d "$EXPLORER_STRATEGY_SRC" ] && [ -n "$(find "$EXPLORER_STRATEGY_SRC" -maxdepth 1 -type f -name '*.csv' -print -quit 2>/dev/null)" ]; then
        local strategy_dest="${S3_ENV}/scenarios/${SCENARIO_ID}/strategy/"
        sync_results "$EXPLORER_STRATEGY_SRC/" "$strategy_dest"
        msg "Strategy CSVs uploaded to s3://${S3_BUCKET}/${strategy_dest}"
    fi

    if [ -d "$EXPLORER_TIMES_SRC" ] && [ -n "$(find "$EXPLORER_TIMES_SRC" -maxdepth 1 -type f -name '*.vd' -print -quit 2>/dev/null)" ]; then
        local times_dest="${S3_ENV}/scenarios/${SCENARIO_ID}/times/"
        sync_results "$EXPLORER_TIMES_SRC/" "$times_dest"
        msg "TIMES .vd uploaded to s3://${S3_BUCKET}/${times_dest}"
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        msg "Dry run complete (no files transferred)."
    else
        msg "Upload complete."
        msg "  raw results : s3://${S3_BUCKET}/${raw_dest}"
        msg "  explorer URL: https://explorer.test.wallonie.climact.com/ (test env)"
    fi
}

cmd_upload
