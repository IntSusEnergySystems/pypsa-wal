#!/bin/bash
# SPDX-License-Identifier: MIT
###############################################################################
# run_headless.sh — run a local Snakemake/plotting job with the desktop fully
# isolated, so it can neither touch nor be touched by the session.
#
#   ./scripts/walloon_scripts/run_headless.sh <logfile> <snakemake args...>
#
# WHY. Two independent reasons, and only the second was ever proven:
#
#  1. A wedged COSMIC theme portal floods syslog and fills `/`
#     (run_from_home_computer.md §4.1). That flood was measured to be INDEPENDENT
#     of the model — it continued at full rate with every Snakemake process
#     killed — so this script does not prevent it. What it does is remove any
#     doubt in the other direction: a job that never opens a GUI toolkit cannot
#     contribute to it, so the next occurrence needs no re-diagnosis.
#
#  2. The repo has a standing history of plot rules crash-looping on the Qt
#     backend (instructions.md, "Long runs in the background"). The postprocess
#     inherits DISPLAY=:1, GDK_BACKEND=wayland and QT_QPA_PLATFORM="wayland;xcb"
#     and sets no MPLBACKEND, so matplotlib is free to pick a GUI backend inside
#     a batch job. `Agg` + `offscreen` makes that impossible.
#
# Also: TMPDIR onto /home (the repo disk, 3.5 TB) instead of the default /tmp on
# the 95 GB root, and `setsid nohup` so a foreground timeout cannot orphan a
# child that keeps writing the same output (run_from_home_computer.md §4.5).
###############################################################################
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG="${1:?usage: run_headless.sh <logfile> <snakemake args...>}"
shift

mkdir -p "$REPO/tmp" "$(dirname "$LOG")"

cd "$REPO"

# Headless plotting, no desktop contact whatsoever.
export MPLBACKEND=Agg
export QT_QPA_PLATFORM=offscreen
unset DISPLAY WAYLAND_DISPLAY GDK_BACKEND QT_QPA_PLATFORMTHEME XDG_SESSION_TYPE

# Keep scratch off the root partition.
export TMPDIR="$REPO/tmp"
export XDG_CACHE_HOME="$REPO/tmp/.cache"
mkdir -p "$XDG_CACHE_HOME"

# Do not let a Zenodo outage block a job that needs no network.
#
# `snakemake-storage-plugin-cached-http` resolves every `storage()` input at
# DAG-BUILD time, so a fully cached tree still makes the metadata call and a
# Zenodo 504 blocks the whole invocation — prepare, solve submission and
# postprocess alike. Two records gate this workflow: 4767098 (SciGRID_gas) and
# 10820928 (synthetic electricity demand). Seen again 2026-09-13, stalling a
# pure post-processing run that reads nothing remote.
#
# This script exists for LOCAL post-processing and plotting, which never needs
# fresh remote data, so trusting the disk is right here. It is deliberately not
# in `profiles/default/`: it also disables freshness checks for data.pypsa.org
# and storage.googleapis.com, so an upstream republish would go unnoticed.
# Set SKIP_REMOTE_CHECKS=0 to opt out. See instructions.md, "When Zenodo is down".
if [ "${SKIP_REMOTE_CHECKS:-1}" = "1" ]; then
    export SNAKEMAKE_STORAGE_CACHED_HTTP_SKIP_REMOTE_CHECKS=1
    echo "[headless] SNAKEMAKE_STORAGE_CACHED_HTTP_SKIP_REMOTE_CHECKS=1 (trusting cached data; set SKIP_REMOTE_CHECKS=0 to disable)"
fi

echo "[headless] MPLBACKEND=$MPLBACKEND QT_QPA_PLATFORM=$QT_QPA_PLATFORM TMPDIR=$TMPDIR"
echo "[headless] log: $LOG"
echo "[headless] snakemake $*"

setsid nohup conda run --no-capture-output -n pypsa-eur \
    snakemake "$@" > "$LOG" 2>&1 &
pid=$!
echo "[headless] pid $pid (detached; it survives this shell)"
echo "$pid" > "$REPO/tmp/headless.pid"
