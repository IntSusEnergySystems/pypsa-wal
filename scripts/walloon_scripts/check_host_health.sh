#!/bin/bash
# SPDX-License-Identifier: MIT
###############################################################################
# check_host_health.sh — workstation preflight/watchdog for long PyPSA-Wal runs
#
# Everything here exists because of one class of failure: the RUN was fine and
# the WORKSTATION was not. Twice on 2026-09-13 a wedged desktop session daemon
# took the machine down mid-run, and both times the symptoms pointed anywhere
# but the cause:
#
#   * `/var/log/syslog` grew to 54 GB, then again at 42 MB/s, filling `/`.
#     Symptoms: ENOSPC in conda, Snakemake and ssh; "Connection timed out during
#     banner exchange" to NIC5; post-processing killed mid-rule. Cause: the
#     COSMIC theme portal retrying a broken D-Bus pipe in a tight loop.
#   * `gcr-ssh-agent` spinning at 60-80 % CPU, so every `ssh` hung *after* key
#     exchange while querying the agent for a key.
#
# Neither is caused by the model, and `/home` (where results live) never ran
# short — it is always `/` that fills. Run this before a batch and from the
# monitoring loop.
#
#   ./scripts/walloon_scripts/check_host_health.sh            # one shot
#   ./scripts/walloon_scripts/check_host_health.sh --fix      # also self-heal
#   watch -n 300 ./scripts/walloon_scripts/check_host_health.sh
#
# Exit status: 0 healthy, 1 warning, 2 action needed now.
###############################################################################
set -uo pipefail

FIX=0
[ "${1:-}" = "--fix" ] && FIX=1

MIN_FREE_GB="${MIN_FREE_GB:-10}"      # abort a long run below this on either fs
MAX_LOG_KBPS="${MAX_LOG_KBPS:-100}"   # >100 KB/s into syslog is a flood
SAMPLE_SECONDS="${SAMPLE_SECONDS:-10}"

rc=0
ok()   { printf '  \033[0;32m[ ok ]\033[0m %s\n' "$*"; }
warn() { printf '  \033[1;33m[WARN]\033[0m %s\n' "$*"; [ $rc -lt 1 ] && rc=1; }
bad()  { printf '  \033[1;31m[ACT!]\033[0m %s\n' "$*"; rc=2; }

echo "host health $(date '+%Y-%m-%d %H:%M:%S')"

# --- 1. disk, BOTH filesystems -----------------------------------------------
# `/home` is the one everybody watches and the one that never fails.
for fs in / /home; do
    free_gb=$(df -BG --output=avail "$fs" 2>/dev/null | tail -1 | tr -dc '0-9')
    [ -z "$free_gb" ] && continue
    if [ "$free_gb" -lt "$MIN_FREE_GB" ]; then
        bad "$fs has ${free_gb}G free (< ${MIN_FREE_GB}G) — do not start a long run"
    else
        ok "$fs ${free_gb}G free"
    fi
done

# --- 2. runaway logging -------------------------------------------------------
# The failure mode is a log growing megabytes per second, not a big log.
if [ -r /var/log/syslog ]; then
    a=$(stat -c %s /var/log/syslog 2>/dev/null || echo 0)
    sleep "$SAMPLE_SECONDS"
    b=$(stat -c %s /var/log/syslog 2>/dev/null || echo 0)
    kbps=$(( (b - a) / 1024 / SAMPLE_SECONDS ))
    size_gb=$(( b / 1073741824 ))
    if [ "$kbps" -gt "$MAX_LOG_KBPS" ]; then
        bad "/var/log/syslog growing ${kbps} KB/s (${size_gb}G) — it will fill / "
        echo "         top emitters:"
        tail -c 400000 /var/log/syslog 2>/dev/null \
            | grep -oP '^\S+\s+\S+\s+\K\S+(?=:)' | sort | uniq -c | sort -rn \
            | head -3 | sed 's/^/           /'
    elif [ "$size_gb" -ge 5 ]; then
        warn "/var/log/syslog is ${size_gb}G but not growing — truncate it:"
        echo "           sudo truncate -s 0 /var/log/syslog   # not rm: rsyslog holds the fd"
    else
        ok "syslog quiet (${kbps} KB/s, ${size_gb}G)"
    fi
fi

# --- 3. wedged session daemons ------------------------------------------------
# Both of these are USER services: they can be restarted without sudo and
# without touching the desktop session.
check_spin() {  # name pattern, threshold %, how to fix
    local pat="$1" thr="$2" fixcmd="$3" pid cpu
    pid=$(pgrep -f "$pat" | head -1) || return 0
    [ -z "$pid" ] && return 0
    cpu=$(ps -o pcpu= -p "$pid" 2>/dev/null | tr -d ' ' | cut -d. -f1)
    [ -z "$cpu" ] && return 0
    if [ "$cpu" -ge "$thr" ]; then
        bad "$pat spinning at ${cpu}% (pid $pid)"
        if [ $FIX -eq 1 ] && [ -n "$fixcmd" ]; then
            echo "         fixing: $fixcmd"
            eval "$fixcmd" >/dev/null 2>&1 && echo "         restarted" || echo "         RESTART FAILED"
        else
            echo "         fix: $fixcmd"
        fi
    else
        ok "$pat ${cpu}%"
    fi
}

check_spin "gcr-ssh-agent" 40 \
    "systemctl --user restart gcr-ssh-agent.socket gcr-ssh-agent.service"
check_spin "rsyslogd" 60 \
    "sudo systemctl restart rsyslog && sudo journalctl --vacuum-size=200M"

# The portal is the root cause of the syslog floods. It reports "active" while
# wedged, so presence is not health — count its errors in the last MINUTE.
#
# Counting the tail of the FILE instead would cry wolf for as long as the old
# flood sits there: right after the 2026-09-13 fix, syslog had stopped growing
# entirely (0 KB/s) while its last 2000 lines were still 1356 portal errors from
# before the restart. Anchor on time, not on position.
last_min=$(date -d '1 minute ago' '+%Y-%m-%dT%H:%M' 2>/dev/null)
this_min=$(date '+%Y-%m-%dT%H:%M')
portal_err=$(tail -c 2000000 /var/log/syslog 2>/dev/null \
    | grep -F -e "$last_min" -e "$this_min" \
    | grep -c "cosmic::theme::portal")
if [ "${portal_err:-0}" -gt 50 ]; then
    bad "COSMIC theme portal erroring (${portal_err} errors in the last minute)"
    if [ $FIX -eq 1 ]; then
        echo "         restarting the portal (user service, no sudo, desktop survives)"
        systemctl --user restart org.freedesktop.impl.portal.desktop.cosmic.service \
            xdg-desktop-portal.service >/dev/null 2>&1 \
            && echo "         restarted" || echo "         RESTART FAILED"
    else
        echo "         fix: systemctl --user restart org.freedesktop.impl.portal.desktop.cosmic.service xdg-desktop-portal.service"
    fi
else
    ok "COSMIC portal quiet (${portal_err:-0} errors in the last minute)"
fi

# --- 4. VPN sanity ------------------------------------------------------------
# ProtonVPN silently takes the tunnel and does not route to the CECI gateway.
if nmcli -t -f NAME,TYPE connection show --active 2>/dev/null | grep -q '^sqvpn:vpn'; then
    tun=$(ip -br addr show tun0 2>/dev/null | awk '{print $3}')
    case "$tun" in
        10.8.0.*) ok "sqvpn up ($tun)" ;;
        "")       warn "sqvpn active but tun0 has no address" ;;
        *)        bad "tun0 is $tun — not the sqvpn 10.8.0.0/24 range; another VPN has the tunnel" ;;
    esac
elif nmcli -t -f NAME,TYPE connection show --active 2>/dev/null | grep -q ':vpn$'; then
    bad "a VPN is up but it is NOT sqvpn — NIC5 will be unreachable:"
    nmcli -t -f NAME,TYPE connection show --active 2>/dev/null | grep ':vpn$' | sed 's/^/           /'
else
    warn "no VPN active — NIC5 unreachable"
fi

echo "exit $rc"
exit $rc
