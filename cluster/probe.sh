#!/bin/bash
# SPDX-License-Identifier: MIT
###############################################################################
# probe.sh - one-shot health probe of a multi-scenario NIC5 batch.
#
# Answers, in one screen, the only question that matters while a batch runs:
# *is every scenario still making progress, and if not, which one is stuck and
# why?*  Designed to be run on a timer (every 30 min) and diffed against the
# previous probe, so a scenario that has not moved between two probes is
# visible without reading any log by hand.
#
#   ./cluster/probe.sh              # print the table
#   ./cluster/probe.sh --save       # also append a line per scenario to the
#                                   # history file, and flag STALLED scenarios
#   ./cluster/probe.sh --json       # machine-readable, for a watcher
#
# STALLED means: the scenario has a RUNNING Slurm job, but neither its solver
# log nor its solved-network set has changed since the previous saved probe.
# That is the failure this batch is exposed to — Gurobi barrier grinding with
# no progress, a BeeGFS hiccup, or an orchestrator that died leaving jobs
# behind — and none of them make the job disappear from squeue.
#
# Reads cluster/config.sh, so it follows RUN_NAME / RUN_PREFIX / HORIZONS
# automatically and needs no arguments.
###############################################################################
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
# shellcheck source=config.sh
source "$HERE/config.sh"

HISTORY="${HISTORY:-$HERE/logs/probe_history.tsv}"
SAVE=0; JSON=0
for a in "$@"; do
    case "$a" in
        --save) SAVE=1 ;;
        --json) JSON=1 ;;
        -h|--help) sed -n '3,25p' "$0"; exit 0 ;;
        *) echo "unknown option: $a" >&2; exit 2 ;;
    esac
done

msg()  { printf '\033[1;34m[probe]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[probe] WARN:\033[0m %s\n' "$*"; }
bad()  { printf '\033[1;31m[probe] STALLED:\033[0m %s\n' "$*"; }

# shellcheck disable=SC2086
rssh() { ssh $SSH_OPTS -o ConnectTimeout=15 -o BatchMode=yes "$REMOTE" "$@"; }

NOW=$(date +%s)
STAMP=$(date '+%Y-%m-%d %H:%M:%S')
mkdir -p "$(dirname "$HISTORY")"

base="base_s_${CLUSTERS}_${OPTS}_${SECTOR_OPTS}"

# --- one remote round-trip for everything -----------------------------------
# Each probe is one ssh call: 13 scenarios x 4 horizons would otherwise be 52
# round-trips over the VPN, which is slower than the thing being measured.
RUN_DIRS=""
for s in $RUN_NAME; do RUN_DIRS+="${RUN_PREFIX:+${RUN_PREFIX}/}${s} "; done

# The remote side is a here-doc fed to `bash -s` with the three values it needs
# passed as positional arguments. Interpolating them into a quoted ssh command
# string instead needs four levels of escaping and silently breaks the moment a
# value contains a space — which RUN_DIRS always does.
remote=$(rssh 'bash -s' "$REMOTE_DIR" "$base" "$RUN_DIRS" "$HORIZONS" <<'REMOTE' 2>&1
set -uo pipefail
cd "$1" 2>/dev/null || exit 7
base="$2"; run_dirs="$3"; horizons="$4"
echo '###QUEUE'
squeue --me -h -o '%i|%T|%M|%N|%j|%R' 2>/dev/null
echo '###ORCH'
pgrep -fa 'bin/snakemake --configfile' 2>/dev/null | head -5
echo '###LOGS'
for d in $run_dirs; do
    for y in $horizons; do
        f="results/$d/logs/${base}_${y}_solver.log"
        [ -f "$f" ] || continue
        printf '%s|%s|%s|%s\n' "$d" "$y" "$(stat -c %Y "$f")" \
            "$(grep -Ec 'Optimal objective' "$f" 2>/dev/null | head -1)"
    done
done
echo '###NETS'
for d in $run_dirs; do
    n=$(ls "results/$d/networks/${base}"_*.nc 2>/dev/null | wc -l)
    echo "$d|$n"
done
echo '###TAIL'
tail -n 3 cluster/logs/orchestrate.log 2>/dev/null | tr '\n' '~'
REMOTE
)

rc=$?
if [ $rc -ne 0 ] || [ -z "$remote" ]; then
    bad "cannot reach $REMOTE (ssh rc=$rc). VPN down, or the login node is busy."
    echo "$remote" | head -3
    exit 1
fi

section() { awk -v s="###$1" -v e="###" '$0==s{f=1;next} f&&/^###/{exit} f' <<<"$remote"; }

queue=$(section QUEUE)
orch=$(section ORCH)
logs=$(section LOGS)
nets=$(section NETS)
tail3=$(section TAIL)

# `grep -c` on no match exits 1 AND prints 0, so `grep -c ... || echo 0`
# produces the two-line string "0\n0" and every later [ ] test on it dies with
# "integer expression expected". Count with grep -c inside a pipeline that
# cannot fail, and strip any newline.
count() { grep -c "$1" <<<"$2" | head -1 | tr -cd '0-9'; }
n_run=$(count '|RUNNING|' "$queue"); n_run=${n_run:-0}
n_pend=$(count '|PENDING|' "$queue"); n_pend=${n_pend:-0}
n_orch=$(grep -c '[^[:space:]]' <<<"$orch" | head -1 | tr -cd '0-9'); n_orch=${n_orch:-0}

n_horizons=$(wc -w <<<"$HORIZONS")
stalled=(); done_all=(); failed=()

if [ "$JSON" = 0 ]; then
    msg "$STAMP  host=$REMOTE  partition=$SOLVE_PARTITION"
    msg "orchestrator(s)=$n_orch  slurm running=$n_run pending=$n_pend"
    printf '\n%-28s %5s %9s %8s %10s  %s\n' \
        SCENARIO NETS/4 OPTIMAL SLURM "LOG AGE" STATE
    printf '%s\n' "--------------------------------------------------------------------------------"
fi

json_rows=""
for scen in $RUN_NAME; do
    d="${RUN_PREFIX:+${RUN_PREFIX}/}${scen}"

    n_nc=$(awk -F'|' -v k="$d" '$1==k{print $2}' <<<"$nets"); n_nc=${n_nc:-0}
    n_opt=$(awk -F'|' -v k="$d" '$1==k{s+=$4} END{print s+0}' <<<"$logs")
    newest=$(awk -F'|' -v k="$d" '$1==k && $3>m {m=$3} END{print m+0}' <<<"$logs")
    age=$(( newest > 0 ? (NOW - newest) : -1 ))

    # Slurm state for this scenario: job names carry the rule and wildcards.
    sl=$(grep -E "\|[^|]*${scen}[^|]*\|" <<<"$queue" | awk -F'|' '{print $2}' | head -1)
    [ -z "$sl" ] && sl="-"

    prev=$(awk -F'\t' -v k="$scen" '$2==k{p=$0} END{print p}' "$HISTORY" 2>/dev/null)
    prev_nc=$(awk -F'\t' '{print $3}' <<<"$prev"); prev_nc=${prev_nc:-0}
    prev_newest=$(awk -F'\t' '{print $6}' <<<"$prev"); prev_newest=${prev_newest:-0}

    if [ "$n_nc" -ge "$n_horizons" ]; then
        state="DONE"; done_all+=("$scen")
    elif [ "$sl" = "RUNNING" ]; then
        if [ -n "$prev" ] && [ "$n_nc" = "$prev_nc" ] && [ "$newest" = "$prev_newest" ] \
           && [ "$newest" -gt 0 ]; then
            state="STALLED"; stalled+=("$scen")
        else
            state="running"
        fi
    elif [ "$sl" = "PENDING" ]; then
        state="queued"
    elif [ "$n_nc" -gt 0 ]; then
        state="STOPPED-PARTIAL"; failed+=("$scen")
    else
        state="not started"
    fi

    if [ "$JSON" = 1 ]; then
        json_rows+="{\"scenario\":\"$scen\",\"networks\":$n_nc,\"optimal\":$n_opt,"
        json_rows+="\"slurm\":\"$sl\",\"log_age_s\":$age,\"state\":\"$state\"},"
    else
        if [ "$age" -lt 0 ]; then human="-"
        elif [ "$age" -lt 3600 ]; then human="$((age/60))m"
        else human="$((age/3600))h$(( (age%3600)/60 ))m"; fi
        printf '%-28s %5s %9s %8s %10s  %s\n' \
            "$scen" "$n_nc/$n_horizons" "$n_opt" "$sl" "$human" "$state"
    fi

    [ "$SAVE" = 1 ] && printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$NOW" "$scen" "$n_nc" "$n_opt" "$sl" "$newest" "$state" >> "$HISTORY"
done

if [ "$JSON" = 1 ]; then
    printf '{"stamp":"%s","running":%s,"pending":%s,"orchestrators":%s,"scenarios":[%s]}\n' \
        "$STAMP" "$n_run" "$n_pend" "$n_orch" "${json_rows%,}"
    exit 0
fi

echo
[ ${#done_all[@]} -gt 0 ] && msg "finished: ${done_all[*]}"
for s in "${failed[@]}"; do
    warn "$s has networks but no Slurm job — solve died or was cancelled. Check:"
    warn "    ssh $REMOTE tail -50 $REMOTE_DIR/cluster/logs/orchestrate.log"
done
for s in "${stalled[@]}"; do
    bad "$s: RUNNING but nothing moved since the last probe."
    bad "    ssh $REMOTE 'tail -20 $REMOTE_DIR/results/${RUN_PREFIX:+${RUN_PREFIX}/}$s/logs/${base}_*_solver.log'"
done

# An orchestrator that is gone while scenarios are unfinished is the one
# failure that stops the whole batch rather than one scenario. Only meaningful
# once the batch has actually been launched — before `nic5.sh solve` there is
# nothing to orchestrate and the absence is not news.
started=$(( n_run + n_pend + ${#done_all[@]} + ${#failed[@]} ))
if [ "$n_orch" -eq 0 ] && [ "$started" -gt 0 ] \
   && [ ${#done_all[@]} -lt "$(wc -w <<<"$RUN_NAME")" ]; then
    bad "no snakemake orchestrator alive and the batch is unfinished."
    bad "    resume with: ./cluster/nic5.sh solve   (completed horizons are kept)"
fi

[ -n "$tail3" ] && { echo; msg "orchestrate.log tail:"; tr '~' '\n' <<<"$tail3" | sed 's/^/    /'; }

[ ${#stalled[@]} -gt 0 ] && exit 3
exit 0
