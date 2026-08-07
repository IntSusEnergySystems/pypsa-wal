#!/usr/bin/env bash
# Re-solve the Walloon myopic chain twice — legacy soft-link and option C — and
# archive both result trees so the heating soft-link can be compared before/after.
#
#   ./scripts/walloon_scripts/run_heat_softlink_comparison.sh [scenario]
#
# Writes results/_heat_softlink_comparison/{before,after}/ and a per-phase log.
# `before` is the legacy transfer (demand only); `after` is option C as configured
# in config/config.times-pypsa.yaml. Both use the *same* config file, so the only
# difference is the `sector.times_heat` overlay applied to the `before` phase.
#
# The script is idempotent per phase: delete the archive folder to force a redo.
# See docs/heat_soft_linking.md §8.6 for how the comparison is read.

set -euo pipefail

SCENARIO="${1:-scen_demande_haute}"
CONFIG="config/config.times-pypsa.yaml"
CORES="${CORES:-12}"
MEM_MB="${MEM_MB:-100000}"
HORIZONS=(2025 2030 2040 2050)

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

ARCHIVE="results/_heat_softlink_comparison"
LOGDIR="$ARCHIVE/logs"
mkdir -p "$LOGDIR"

# Gurobi reads GRB_LICENSE_FILE from ~/.bashrc, which a non-interactive shell
# does not source; without this the academic licence is invisible and gurobipy
# silently falls back to its size-limited demo licence.
export GRB_LICENSE_FILE="${GRB_LICENSE_FILE:-$HOME/.gurobi/gurobi.lic}"
# Plot rules abort with a Qt platform-plugin error on a headless session.
export MPLBACKEND=Agg

LEGACY_OVERLAY="$ARCHIVE/legacy_overlay.yaml"
cat > "$LEGACY_OVERLAY" <<'YAML'
# `before` phase: every heating soft-link switch back to its pre-2026-08 value.
sector:
  times_heat:
    node: BEWAL
    urban_rural_split: times
    base_year_capacities: false
    energy_mix:
      enable: false
      mode: share
      tolerance: 0.05
      slack_groups: []
      zero_target: forbid
YAML

targets() {
  for y in "${HORIZONS[@]}"; do
    printf 'results/times-pypsa/%s/networks/base_s_adm___%s.nc ' "$SCENARIO" "$y"
  done
}

WATCHDOG_PID=""

# An infeasible sector LP is not a normal failure in this workflow: after Gurobi
# reports `Infeasible model`, solve_network.py calls
# `n.model.compute_infeasibilities()`, which computes a Gurobi IIS over ~1.3 M
# rows and does not finish — one horizon then blocks the chain forever at ~0 %
# CPU. `sector.times_heat.energy_mix.penalty` makes the heat constraints soft so
# they cannot cause this, but any *other* infeasibility still can. The watchdog
# turns that silent hang into a fast, loud abort.
start_watchdog() {
  local phase="$1"
  stop_watchdog
  (
    while true; do
      for log in results/times-pypsa/"$SCENARIO"/logs/*_solver.log; do
        [[ -f "$log" ]] || continue
        if grep -q "Infeasible model" "$log" 2>/dev/null; then
          echo "WATCHDOG: infeasible model in $log — aborting $phase before the" \
               "IIS computation starts" >&2
          pkill -f "bin/snakemake results/times-pypsa" 2>/dev/null
          sleep 2
          pkill -9 -f "\.snakemake/scripts/tmp" 2>/dev/null
          exit 1
        fi
      done
      sleep 20
    done
  ) &
  WATCHDOG_PID=$!
}

stop_watchdog() {
  if [[ -n "$WATCHDOG_PID" ]]; then
    kill "$WATCHDOG_PID" 2>/dev/null || true
    WATCHDOG_PID=""
  fi
}

trap 'stop_watchdog' EXIT

run_phase() {
  local phase="$1"; shift
  local dest="$ARCHIVE/$phase"
  if [[ -d "$dest/networks" ]]; then
    echo "[$phase] already archived in $dest — skipping (delete it to redo)"
    return 0
  fi
  echo "[$phase] solving $SCENARIO, horizons ${HORIZONS[*]}"
  start_watchdog "$phase"
  # Two things about the command line, both learned the hard way:
  #  * Targets go FIRST. `--configfile`, `--resources`, `--forcerun`, `--until`
  #    and friends all take nargs="+" and swallow a target written after them,
  #    leaving no target at all so Snakemake runs the default `all` rule.
  #  * An overlay is an extra file on the SAME `--configfile` flag. Repeating the
  #    flag (`--configfile a --configfile b`) keeps only the last file, which
  #    drops `run.scenarios` and makes every scenario path unproducible
  #    ("No rule to produce results/times-pypsa/<scen>/networks/…").
  # shellcheck disable=SC2046
  snakemake $(targets) \
    --configfile "$CONFIG" "$@" \
    --resources mem_mb="$MEM_MB" \
    --cores "$CORES" \
    2>&1 | tee "$LOGDIR/$phase.log"

  stop_watchdog
  echo "[$phase] archiving to $dest"
  mkdir -p "$dest"
  rsync -a --delete \
    "results/times-pypsa/$SCENARIO/networks/" "$dest/networks/"
  for sub in logs configs csvs; do
    if [[ -d "results/times-pypsa/$SCENARIO/$sub" ]]; then
      rsync -a "results/times-pypsa/$SCENARIO/$sub/" "$dest/$sub/"
    fi
  done
  cp -f "resources/times-pypsa/$SCENARIO/existing_heating_distribution_base_s_adm_2025.csv" \
        "$dest/" 2>/dev/null || true
  echo "[$phase] done"
}

run_phase before "$LEGACY_OVERLAY"
run_phase after

echo "ALL_PHASES_DONE"
