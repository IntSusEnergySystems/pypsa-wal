# Production runs from the home computer (Pop!_OS, via NIC5)

Companion to [`run_from_office_computer.md`](run_from_office_computer.md). Same
division of labour — data preparation and post-processing here, every Gurobi
solve on NIC5 — but a different machine with **different failure modes**, and
they are the reason this file exists.

The September 2026 cabinet batch (14 scenarios, 1 h, overnight) ran here. The
model behaved: 51/52 networks solved, every one to `Optimal objective`, one
horizon lost to a numerical issue. **Everything that actually stopped work was
the workstation**, and every symptom pointed somewhere other than the cause. §4
is the part worth reading before a long run.

Batch record: [`docs/logs/2026-09-13_cabinet_batch_all14_2010_1h.md`](docs/logs/2026-09-13_cabinet_batch_all14_2010_1h.md).

---

## 1. Machine profile

| | |
|---|---|
| Host | `pop-os`, Pop!_OS with the **COSMIC** desktop |
| CPU / RAM | 24 cores / 124 GB |
| `/` | `/dev/nvme0n1p2`, **95 GB** — code, `/tmp`, `/var/log` |
| `/home` | `/dev/nvme0n1p4`, **3.5 TB**, ~1.9 TB free — repo, `resources/`, `results/`, cutouts |
| Repo | `/home/sylvain/svn/pypsa-wal` (no symlink redirection; unlike the office machine, everything heavy already sits on the big disk) |
| Network | home broadband — **up 17.7 Mbit/s, down 85 Mbit/s** (measured) |
| Cluster access | `sqvpn` → `gwceci.uliege.be` → `nic5` |

**The asymmetry that matters: `/home` is 37× bigger than `/`.** Results have
never come close to filling `/home`; `/` has filled twice in one day. Watch the
partition nobody thinks about.

## 2. Before any long run

```bash
./scripts/walloon_scripts/check_host_health.sh
```

Exit 0 healthy, 1 warning, 2 act now — so it drops straight into a monitoring
loop. `--fix` self-heals the two daemons that wedge (both user services, no sudo,
desktop survives).

**One-time, once per machine** — makes §4 harmless rather than merely diagnosable:

```bash
sudo ./scripts/walloon_scripts/harden_host_logging.sh
```

It caps the journal at 500 MB, tightens the journald rate limit, size-rotates
`/var/log/syslog` at 200 MB, and drops the specific message that floods. Fully
reversible with `--revert`.

## 3. Network — the uplink is the slow leg

Measured on the batch, and worth planning around:

| leg | rate | example |
|---|---|---|
| **up** | 17.7 Mbit/s (~2.2 MB/s) | first push 1.2 GB on the wire → 11 min |
| **down** | 85 Mbit/s (~10.7 MB/s) | ~14 GB of solved networks → ~30 min |
| S3 upload | ~2.2 MB/s (uplink-bound) | ~1.7 GB per scenario |

Three consequences:

- **Pull incrementally while the batch still solves.** rsync re-transfers
  anything whose size or mtime changed, so an early pull is safe and the final
  one takes minutes instead of an hour.
- **Never push a second full tree.** For the 2013 weather-year run, clone the
  tree *cluster-side* (`rsync` on BeeGFS) and push only its own resources —
  2.5 min instead of ~50 min of uplink.
- **The S3 upload saturates the uplink**, and while it runs `ssh nic5` fails with
  *"Connection timed out during banner exchange"*. That is contention, not a
  fault. Do not chase it; check the cluster between chunks, or upload last.

## 4. The workstation failure modes — read this before an overnight run

All three arrived on 2026-09-13. None was caused by the model. All three
masqueraded as something else.

### 4.1 The COSMIC portal floods syslog and fills `/`

**Symptoms, in the order you meet them:** `conda` and Snakemake fail with
ENOSPC; `ssh` to NIC5 times out *during banner exchange*; a post-processing rule
dies mid-write; the agent's own tooling stops working. Nothing says "disk".

**Cause:** the COSMIC theme portal loses its D-Bus connection and retries in a
tight loop with no backoff, at ~1 000 messages/second:

```
cosmic-session[…]: ERROR cosmic::theme::portal > Failed to get the contrast
                   Portal(ZBus(InputOutput(Os { code: 32, BrokenPipe })))
```

`/var/log/syslog` reached **54 GB in a day**; after a reboot it did it again at
**42 MB/s**, which eats 24 GB of free root in ten minutes.

**Diagnose:**

```bash
df -h / /home                                   # / is the one that is full
ls -lSh /var/log | head -3                      # syslog enormous?
journalctl --since "30 seconds ago" | grep -c cosmic-session   # >10000 = looping
```

**Recover:**

```bash
sudo truncate -s 0 /var/log/syslog     # NOT rm — rsyslog holds the fd open
sudo systemctl restart rsyslog && sudo journalctl --vacuum-size=200M
```

**Stop the loop.** Two levels, and the distinction cost real time to learn:

```bash
# (a) restarts the portal SERVER. Silences the syslog file, but the loop keeps
#     running — cosmic-session holds a stale connection and only retries the
#     call, never reconnects. Rate-limiting hides it while rsyslogd burns 115 % CPU.
systemctl --user restart org.freedesktop.impl.portal.desktop.cosmic.service \
                         xdg-desktop-portal.service

# (b) the only real fix: restart the CLIENT, i.e. cosmic-session — log out and
#     back in, or reboot.
```

**What does not work**, so nobody tries it twice: killing `cosmic-launcher` (it
is supervised and respawns instantly), and killing the run (the flood continued
at full rate with every Snakemake process dead — that is how the model was ruled
out).

**Prevention:** `harden_host_logging.sh` (§2). With the journal capped and the
message dropped, the same loop becomes a CPU annoyance instead of a stopped run.

### 4.2 `gcr-ssh-agent` wedges and every `ssh` hangs

**Symptom:** `ssh nic5` completes TCP *and* key exchange, then hangs forever.
`ssh -vv` stops right after `kex:`. Survives a VPN bounce and a disk fix, which
is what makes it confusing.

**Cause:** `gcr-ssh-agent` (GNOME keyring) spinning at 60–80 % CPU. `ssh` asks it
for a key and never gets an answer.

```bash
ps -o pcpu=,etimes= -p $(pgrep -f gcr-ssh-agent | head -1)
systemctl --user restart gcr-ssh-agent.socket gcr-ssh-agent.service   # no sudo
```

Workaround while wedged: `env -u SSH_AUTH_SOCK ssh nic5 …`.

It wedges *together with* the portal, because both are session D-Bus clients —
which is why two unrelated-looking failures arrive in the same minute.

### 4.3 ProtonVPN silently steals the tunnel

**Symptom:** identical to 4.2 — `ssh nic5` times out — and it persists after
restarting the agent.

**Cause:** bouncing `sqvpn` let `be-31.protonvpn.udp` take `tun0`. ProtonVPN does
not route to the CÉCI gateway. `nmcli` cheerfully reports "a VPN is active".

```bash
nmcli -t -f NAME,TYPE connection show --active | grep vpn   # must say sqvpn
ip -br addr show tun0                                       # must be 10.8.0.2/24
nmcli connection down be-31.protonvpn.udp && nmcli connection up sqvpn
```

**`10.96.x` on `tun0` means ProtonVPN has it.** `check_host_health.sh` asserts
the address, not just that "a VPN is up".

### 4.4 `generate_html_report` OOMs the machine at `--cores 8`

**Symptom:** several `Error in rule generate_html_report` at once, whose
`pypsa2html.log` files simply *stop mid-write* with no exception — and your
desktop session disappears at the same moment.

**Cause:** each report job loads four solved networks and builds Plotly pages —
**~28 GB RSS**. `--cores 8` runs eight of them concurrently: 224 GB against
124 GB. The kernel OOM-killer takes the report jobs *and* whatever else is large,
which on this machine means the desktop.

```
14:25:59 Out of memory: Killed process (claude-desktop)
14:26:00 Out of memory: Killed process (python3.13)  anon-rss: 28 GB
```

**Confirm** — there is no trace of this in the Snakemake log, only in the kernel's:

```bash
journalctl --since "-1h" | grep -i "out of memory"
```

**Fix — cap it explicitly.** `make_summary` is light and can still run 8-wide;
only the report rule needs bounding:

```bash
--cores 8 --resources mem_mb=90000 --set-resources generate_html_report:mem_mb=30000
```

That allows **3 concurrent** report jobs (84 GB), leaving ~40 GB for the desktop.
Measured: memory stayed above 26 GB free for the whole run, zero OOM events,
where the unbounded version had gone to zero.

The same applies to `generate_html_report_all_scenarios` (the combined report),
which loads every scenario in turn.

### 4.5 Killed Snakemake leaves a child writing the same output

A foreground timeout kills the parent; the `pypsa2html` child keeps writing
`results/walloon/index.html`. Starting a new run then gives two writers on one
file. Run long reports detached:

```bash
TMPDIR=$PWD/tmp nohup snakemake --configfile config/config.walloon.yaml \
    --cores 4 results/walloon/index.html > tmp/combined_report.log 2>&1 &
```

If it happens: kill the child, delete the partial output, clear
`.snakemake/locks/`, and re-run with `--rerun-incomplete` (Snakemake marks the
half-written file incomplete and refuses to proceed otherwise).

## 5. Monitoring a long run from here

Every 30 minutes, four things — and note that **`cluster/probe.sh` does not work
on a Snakemake-submitted batch** (it reports `0/4` and `STOPPED-PARTIAL` for
scenarios that have solved networks, because Snakemake names Slurm jobs with
UUIDs). Until it is fixed, enumerate the scenario list explicitly:

```bash
# 1. host
./scripts/walloon_scripts/check_host_health.sh

# 2. progress — enumerate scenarios; a glob over results/walloon/* also catches
#    retired trees (scen_demande_haute, scen_test_2013_6h) and reports them as
#    this batch's progress
ssh nic5 'cd /scratch/ulg/thermlab/squoilin/pypsa-wal;
  for s in scen_central scen_taxshift …; do
    printf "%-28s %s/4\n" "$s" "$(ls results/walloon/$s/networks/base_s_adm___20*.nc 2>/dev/null | wc -l)"
  done'

# 3. failures that --keep-going hides: the queue drains normally and nothing
#    reports an error until the whole batch finishes
ssh nic5 'grep -l "Numerical trouble\|INFEASIBLE" \
  /scratch/.../results/walloon/*/logs/*_solver.log'

# 4. stalls: a solver log that has not moved in >25 min while its job runs.
#    Exclude scenarios already at 4/4 — a finished scenario also has a static log.
```

## 6. Local disk hygiene during a run

- `TMPDIR=$PWD/tmp` for anything long. The repo is on `/home`; the default
  `/tmp` is on the 95 GB root.
- `tmp/` accumulates linopy `*.lp` dumps (9.4 GB seen). It is excluded from the
  push, but clear it locally between batches.
- The pull brings ~1.3 GB of solved networks per scenario. Thirteen scenarios plus
  reports is ~15 GB — nothing on `/home`, but never redirect it to `/`.

---

**Related:** [`instructions.md`](instructions.md) (operational guide),
[`run_from_office_computer.md`](run_from_office_computer.md) (the other machine),
[`docs/logs/2026-09-13_cabinet_batch_all14_2010_1h.md`](docs/logs/2026-09-13_cabinet_batch_all14_2010_1h.md)
(the batch these lessons come from, §15 and §16),
[`docs/run-review-checklist.md`](docs/run-review-checklist.md) (is the run
*right*, not just finished).
