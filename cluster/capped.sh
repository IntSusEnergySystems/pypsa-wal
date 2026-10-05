#!/bin/bash
# Run one heavy LOCAL step in its own cgroup scope with a hard memory cap and NO swap.
#
#   cluster/capped.sh <limit, e.g. 10G> <label> -- <command ...>
#   RUN_NAME=scen_central cluster/capped.sh 10G extract -- ./cluster/nic5.sh extract
#
# Why: the office computer has 15.9 GB of RAM, ~4.5 GB of it taken by the desktop and the
# agents, and its 100 GB swap is a spinning disk. A step that grows past RAM does not fail, it
# swaps, the desktop stalls and the Claude desktop app aborts (SIGILL in `coredumpctl list`).
# With MemorySwapMax=0 the step alone is killed at the cap (exit 137) and nothing else is touched.
# Prints the cgroup peak at the end: `CAPPED label=... exit=... peak_GB=...`.
# See run_from_office_computer.md section 7.
lim=$1; label=$2; shift 3
unit="capped-${label}-$$"
systemd-run --user --scope -q --unit="$unit" -p MemoryHigh="$lim" -p MemoryMax="$lim" -p MemorySwapMax=0 -- "$@" &
pid=$!
cg=/sys/fs/cgroup/user.slice/user-$(id -u).slice/user@$(id -u).service/app.slice/$unit.scope
peak=0
while kill -0 "$pid" 2>/dev/null; do
  if [ -r "$cg/memory.peak" ]; then v=$(cat "$cg/memory.peak" 2>/dev/null); [ -n "$v" ] && peak=$v; fi
  sleep 2
done
wait "$pid"; rc=$?
echo "CAPPED label=$label limit=$lim exit=$rc peak_GB=$(awk -v p="$peak" 'BEGIN{printf "%.1f", p/1073741824}')"
exit "$rc"
