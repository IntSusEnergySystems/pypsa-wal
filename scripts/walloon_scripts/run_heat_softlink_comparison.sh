#!/usr/bin/env bash
# Re-solve the Walloon myopic chain once per heating soft-link mechanism and
# archive each result tree so they can be compared.
#
#   ./scripts/walloon_scripts/run_heat_softlink_comparison.sh [scenario] [phase...]
#
# Phases, each written to results/_heat_softlink_comparison/<phase>/ :
#
#   before     the legacy transfer — annual heat demand only, PyPSA re-optimises
#              the appliance fleet from scratch
#   after      option C — annual energy-mix constraints (docs/heat_soft_linking.md)
#   option_b   option B' — reconstructed hourly profiles, pinned dispatch
#              (docs/heat_softlink_option_b.md)
#
# All three use the SAME config file; each phase differs only by the
# `sector.times_heat` overlay written below, so nothing but the mechanism moves.
# `before` and `after` keep their historical names because
# scripts/walloon_scripts/compare_heat_softlink.py reads them.
#
# The script is idempotent per phase: delete the archive folder to force a redo.
# With no phase argument it runs all three, in order.

set -euo pipefail

SCENARIO="${1:-scen_demande_haute}"
shift || true
PHASES=("$@")
[[ ${#PHASES[@]} -eq 0 ]] && PHASES=(before after option_b)
CONFIG="config/config.walloon.yaml"
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

# One overlay per phase, so every phase's configuration is written down rather
# than implied by whatever the checked-in config happens to say today.
LEGACY_OVERLAY="$ARCHIVE/legacy_overlay.yaml"
cat > "$LEGACY_OVERLAY" <<'YAML'
# `before` phase: every heating soft-link switch back to its pre-2026-08 value.
sector:
  times_heat:
    node: BEWAL
    urban_rural_split: times
    base_year_capacities: false
    profile:
      enable: false
    energy_mix:
      enable: false
      mode: share
      tolerance: 0.05
      slack_groups: []
      zero_target: forbid
YAML

OPTION_C_OVERLAY="$ARCHIVE/option_c_overlay.yaml"
cat > "$OPTION_C_OVERLAY" <<'YAML'
# `after` phase: option C — annual energy-mix constraints. The stock and split
# harmonisations are shared with option B', so only the mechanism differs.
sector:
  times_heat:
    node: BEWAL
    urban_rural_split: times_base_year
    base_year_capacities: true
    profile:
      enable: false
    energy_mix:
      enable: true
      mode: share
      tolerance: 0.05
      slack_groups: []
      zero_target: forbid
      penalty: 1000.0
YAML

OPTION_B_OVERLAY="$ARCHIVE/option_b_overlay.yaml"
cat > "$OPTION_B_OVERLAY" <<'YAML'
# `option_b` phase: option B' — reconstructed hourly profiles, pinned dispatch.
sector:
  times_heat:
    node: BEWAL
    urban_rural_split: times_base_year
    base_year_capacities: true
    energy_mix:
      enable: false
    profile:
      enable: true
      absorber: heat pump
      penalty: 1000.0
      free_groups: []
      export: true
YAML

overlay_for() {
  case "$1" in
    before)   echo "$LEGACY_OVERLAY" ;;
    after)    echo "$OPTION_C_OVERLAY" ;;
    option_b) echo "$OPTION_B_OVERLAY" ;;
    *) echo "unknown phase: $1" >&2; exit 2 ;;
  esac
}

targets() {
  for y in "${HORIZONS[@]}"; do
    printf 'results/walloon/%s/networks/base_s_adm___%s.nc ' "$SCENARIO" "$y"
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
      for log in results/walloon/"$SCENARIO"/logs/*_solver.log; do
        [[ -f "$log" ]] || continue
        if grep -q "Infeasible model" "$log" 2>/dev/null; then
          echo "WATCHDOG: infeasible model in $log — aborting $phase before the" \
               "IIS computation starts" >&2
          pkill -f "bin/snakemake results/walloon" 2>/dev/null
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
  #    ("No rule to produce results/walloon/<scen>/networks/…").
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
    "results/walloon/$SCENARIO/networks/" "$dest/networks/"
  for sub in logs configs csvs; do
    if [[ -d "results/walloon/$SCENARIO/$sub" ]]; then
      rsync -a "results/walloon/$SCENARIO/$sub/" "$dest/$sub/"
    fi
  done
  cp -f "resources/walloon/$SCENARIO/existing_heating_distribution_base_s_adm_2025.csv" \
        "$dest/" 2>/dev/null || true
  if [[ -d "results/walloon/$SCENARIO/heating_profiles" ]]; then
    rsync -a "results/walloon/$SCENARIO/heating_profiles/" "$dest/heating_profiles/"
  fi
  echo "[$phase] done"
}

for phase in "${PHASES[@]}"; do
  run_phase "$phase" "$(overlay_for "$phase")"
done

echo "ALL_PHASES_DONE"
