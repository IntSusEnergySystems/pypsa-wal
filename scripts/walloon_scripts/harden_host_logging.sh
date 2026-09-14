#!/bin/bash
# SPDX-License-Identifier: MIT
###############################################################################
# harden_host_logging.sh — one-time, root: make it impossible for a runaway
# desktop daemon to fill `/` and stop a run.
#
# WHY. On 2026-09-13 the COSMIC theme portal lost its D-Bus connection and
# retried in a tight loop with no backoff, emitting ~1 000 messages/second.
# Twice in one day that filled the 95 GB root partition — 54 GB of
# /var/log/syslog the first time, then 31 GB at 42 MB/s after a reboot. Every
# tool failed at once and none of them blamed the disk: conda and Snakemake with
# ENOSPC, `ssh` with "Connection timed out during banner exchange",
# post-processing killed mid-rule. `/home`, where results live, never dropped
# below 1.9 TB.
#
# The bug is in the desktop, is not triggered by the model, and will recur. This
# script does not fix COSMIC; it makes the blast radius zero.
#
#   sudo ./scripts/walloon_scripts/harden_host_logging.sh          # apply
#   sudo ./scripts/walloon_scripts/harden_host_logging.sh --revert # undo
#
# Idempotent. Every change is one dropped-in file, so --revert is a clean delete.
###############################################################################
set -euo pipefail

RSYSLOG_DROP=/etc/rsyslog.d/10-drop-cosmic-portal-spam.conf
JOURNALD_CAP=/etc/systemd/journald.conf.d/10-cap-and-ratelimit.conf
LOGROTATE_CAP=/etc/logrotate.d/rsyslog-size-cap

[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }

if [ "${1:-}" = "--revert" ]; then
    rm -f "$RSYSLOG_DROP" "$JOURNALD_CAP" "$LOGROTATE_CAP"
    systemctl restart systemd-journald rsyslog
    echo "reverted; journald and rsyslog restarted"
    exit 0
fi

# --- 1. drop the spam at the syslog daemon -----------------------------------
# Cheapest and most specific: these messages carry no information after the
# first one. Everything else still logs normally.
cat > "$RSYSLOG_DROP" <<'EOF'
# PyPSA-Wal host hardening. The COSMIC theme portal retries a broken D-Bus pipe
# in a tight loop and can emit ~1000 msg/s indefinitely, filling / and taking
# down long model runs. The message is identical every time.
# See run_from_home_computer.md.
:msg, contains, "cosmic::theme::portal" stop
EOF

# --- 2. cap the journal and tighten its rate limit ---------------------------
# The flood also lands in the journal, and rsyslog's imjournal then spins at
# ~115 % CPU grinding through the backlog long after the log itself is quiet.
# The stock RateLimitBurst=10000/30s is far too loose against 32 500/30 s.
mkdir -p "$(dirname "$JOURNALD_CAP")"
cat > "$JOURNALD_CAP" <<'EOF'
[Journal]
# Hard ceiling: the journal can never eat the root partition.
SystemMaxUse=500M
SystemKeepFree=5G
# A loop this fast is never worth logging in full.
RateLimitIntervalSec=30s
RateLimitBurst=500
EOF

# --- 3. size-cap syslog itself ------------------------------------------------
# Daily rotation is useless against a log that grows 42 MB/s: it reached 54 GB
# between two rotations. Rotate on SIZE as well.
cat > "$LOGROTATE_CAP" <<'EOF'
# PyPSA-Wal host hardening: rotate on size, not only daily, so no single log can
# fill /. See run_from_home_computer.md.
/var/log/syslog
{
    size 200M
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
EOF

systemctl restart systemd-journald
systemctl restart rsyslog

echo "applied:"
printf '  %s\n' "$RSYSLOG_DROP" "$JOURNALD_CAP" "$LOGROTATE_CAP"
echo
echo "verify:"
echo "  journalctl --disk-usage"
echo "  ./scripts/walloon_scripts/check_host_health.sh"
