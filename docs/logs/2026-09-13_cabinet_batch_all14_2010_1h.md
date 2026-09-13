# Batch log — September 2026 cabinet batch, all 14 scenarios

Companion to `docs/runs-20260912-cabinet-batch.md` (the recipe) and
`docs/logs/2026-09-13_scen_central_cabinet_batch_2010_1h.md` (the central
scenario's own log, which carries the §11 critical review).

**This file is the batch-level record**: what ran, what it cost, what broke, and
what has to change before the next one.

## 1. Identification

| | |
|---|---|
| Batch | 13 × weather-2010 scenarios + `scen_central_2013` |
| Window | 2026-09-12 18:48 → 2026-09-13 08:30 CEST |
| Config | `config/config.walloon.yaml` (+ `config/config.weather2013.yaml` for #14) |
| TIMES exports | `times_20260911_*`, eight `.vd` files, 605 MB |
| Resolution | 1 h, myopic 2025 / 2030 / 2040 / 2050 |
| Cluster | NIC5 `batch`, 16 cpus / 80 GB per solve, Gurobi 13.0.2 (token licence) |
| Branch | `development_plan` |

## 2. Outcome

| | |
|---|---|
| Networks solved | **51 / 52** (2010 batch) + **4 / 4** (2013) |
| Solved to `Optimal objective` | **every one of them** |
| Scenarios fully post-processed | **12 / 13** |
| Failed | `scen_realiste_nobnd30` @2050 — Gurobi *Numerical trouble encountered* (§5.1) |
| Infeasible / unbounded | **none, anywhere** |

Gate results, the two the recipe §7 asks for:

* **Gate A — 2025 across all 13:** first optimum 23:33, all 13 by 01:09. Proves the
  shared-resources change, the regenerated cost table and the per-scenario
  softlink files.
* **Gate B — 2030:** first optimum 01:05. The realiste pair, which carries the
  most-rewritten 2030 constraint set (Walloon caps below the old floors, both
  Belgian floors dropped, CO₂ lifted to 1.0), is **feasible** — the empty-corridor
  infeasibility that §1.2 warns about did not occur.

## 3. Timings

| phase | wall-clock |
|---|---|
| preflight + local preprocessing (13 scenarios) | 18:48 → 22:18 (incl. two bug fixes, §5.2/§5.3) |
| push | 11 min |
| solve, 13 chains in parallel | 22:30 → 07:39 (**≈ 9 h**) |
| `scen_central` alone (4 horizons) | 6 h04 |
| 2013 prepare (local) | 14 min |
| 2013 solve (concurrent, separate remote dir) | 23:01 → ~07:40 |
| pull (5 incremental) + post-process | ~45 min total |

Thirteen scenarios in series would have been ≈ 85 h. **All 13 were RUNNING within
four minutes of launch with zero queueing**, which settles the `batch`-over-`hmem`
question in `cluster/config.sh` — `hmem`'s three nodes would have serialised it.

Peak RSS (central) 22.4 / 28.3 / 29.8 / 29.9 GB against 80 GB requested — identical
to the 2026-09-07 run.

## 4. Data transit

The workstation uplink is the slow leg; both rates measured on the night.

| leg | rate | volume | time |
|---|---|---:|---:|
| push (batch) | 17.7 Mbit/s | 1.2 GB on the wire (6.8 GB scope) | 11 min |
| push (2013 resources) | " | 936 MB | 2.5 min |
| pull | **85 Mbit/s** | ≈ 14 GB over five incremental pulls | ≈ 30 min |

Two choices that kept this small, both worth repeating:

* **Pull incrementally while the batch is still solving.** rsync re-transfers
  anything whose size or mtime changed, so an early pull is safe and the final one
  becomes minutes rather than an hour.
* **Clone the tree cluster-side for the 2013 run** (`rsync` on BeeGFS, then push
  only `resources/walloon_2013`). A second full push would have cost ~50 min of
  uplink; this cost 2.5 min. See §6 for the trap in doing so.

## 5. Issues

### 5.1 `scen_realiste_nobnd30` @2050 — numerical trouble (the one failure)

```
iter 24-33: primal residual flat at 7.42e+12, complementarity 4.47e+10,
            objective oscillating ~8.72e+15  (the other scenarios reach 2.6e+11)
Barrier performed 33 iterations in 869.75 seconds
Numerical trouble encountered
```

`BarHomogeneous: 1` was **already set** (both configs) and crossover is already 0,
so the remedy `docs/runs-20260912-cabinet-batch.md` §8 prescribes was in force and
insufficient. Isolated: a scan of all 52 solver logs found this horizon and no
other, and its sister `scen_realiste_nets` solved 2050 normally — conditioning,
not a bad constraint set. Gurobi warns `large bounds, large rhs` at every horizon
of every scenario, so the barrier has little numerical headroom to begin with.

Escalation added: `cluster/config_numericfocus.yaml` (`NumericFocus: 3`,
`ScaleFlag: 2`). Retry launched 07:41 as Slurm job **11155390** on `nic5-w007`;
parameters confirmed applied via the python log
(`BarHomogeneous: 1 / NumericFocus: 3 / ScaleFlag: 2`).

**It is working.** Where the failed attempt sat with a flat residual, the retry
descends steadily:

| | primal residual | complementarity |
|---|---:|---:|
| failed attempt, iter 24-33 | 7.42e+12 **flat** | 4.47e+10 flat |
| retry, iter 19 → 24 | 5.20e+09 → **1.18e+09** | 1.42e+06 → **2.13e+05** |

Cost of the harder numerics: ~147 s/iteration against ~22 s for the other
scenarios, so it is ~6.7× slower. Job walltime is 12 h (`SOLVE_RUNTIME=720`), of
which ~1 h20 was used at 09:05, so it has ample headroom.

**Status at the 2026-09-13 09:05 handoff: still running, 3/4 networks.**
Record the objective here when it lands.

`--keep-going` meant the batch carried on, so this failure was invisible in the
queue and surfaced only because the solver logs were scanned directly. See §7.

### 5.2 `TypeError: Object of type function is not JSON serializable`

`cluster_network` and `simplify_network` did
`aggregation_strategies.get("buses", dict())`, which **aliases**
`config["clustering"]["aggregation_strategies"]` because `buses: {}` has existed in
`config.default.yaml` since the Pydantic merge (`8b064878`, January). `setdefault`
then wrote two lambdas into the live config, and `n.meta = dict(snakemake.config, …)`
could not serialise it on export. Latent for eight months; exposed now because
`run.shared_resources.policy: base` changed which rules run unscoped.
Fixed by copying instead of aliasing, in both scripts.

### 5.3 EV fleet-share guard rejected every scenario at 2025

See `docs/runs-20260912-cabinet-batch.md` §12 and open item 7. The guard compared a
car-only count share against an all-road energy share; Wallonia's ~199 kveh of
two/three-wheelers (48 % electric in 2025) dominate the numerator. Now gated on its
own premise (`CAR_DOMINATED_ROAD_ELECTRICITY = 0.80`): hard error at 2030/2040/2050
(96–97 % car-dominated), warning at 2025 (25.5 %).

**Still open:** the 2025 Walloon BEV car fleet fell 52× between the 7 and 11 Sept
exports (248 880 → 4 757). Neither figure matches reality. ICEDD must confirm.

### 5.4 Every per-scenario HTML report opened on a 404

`config/pypsa2html.yaml` has one `landing.scenario: scen_central`, correct for the
combined report, applied verbatim by pypsa2html to per-scenario ones — so 12 of 13
indexes redirected to a page that exists only in the central tree. Fixed by
`scripts/walloon_scripts/fix_scenario_report_index.py` (idempotent, corrects the
generated artefact, leaves pypsa2html and the combined report alone).

### 5.5 `cluster/probe.sh` does not work on a Snakemake-submitted batch

The batch's designated monitor reported `0/4` and `STOPPED-PARTIAL` for scenarios
with demonstrably solved networks, and a blank Slurm column throughout: Snakemake
names its jobs with UUIDs, so no job maps to a scenario and every scenario reads as
"has networks but no job". Monitoring fell back to a direct file-count matrix over
one ssh round-trip. **`probe.sh` would not have detected the §5.1 failure.**

### 5.6 The workstation root filesystem filled, killing post-processing

At ~08:30 `/` hit 100 % (90 GB of 95 GB). Cause was **not** the run:
`/var/log/syslog` had reached **54 GB** in one day (previous rotation: 74 MB),
~10 000 of every 20 000 lines being

```
cosmic-session[…]: ERROR cosmic::theme::portal > Failed to get the contrast
                   Portal(ZBus(InputOutput(Os { code: 32, BrokenPipe })))
```

— the Pop!_OS COSMIC theme portal retrying a broken D-Bus connection in a tight
loop with no backoff, at ~1.8 MB/s. Results were never at risk (`results/` is on
`/home`, 1.9 TB free) and the post-process had already completed for all 12
finished scenarios, but ssh, conda and the agent's own tooling all failed with
ENOSPC until space was reclaimed. Prevention: §7.

## 6. Traps met that the recipe did not list

* **Two Snakemake orchestrators cannot share a working directory.** The 2013 run
  needs its own tree on the cluster (`pypsa-wal-2013`), or it must wait for the
  batch to finish. Cloning BeeGFS-side costs no WAN transfer.
* **`rsync --exclude` patterns without a leading `/` match at every depth.**
  `--exclude tmp --exclude results --exclude .cache` silently stripped nested
  directories throughout the clone. Anchor them: `--exclude "/tmp"`.
* **`du` on BeeGFS reports allocated blocks, not apparent size.** A complete clone
  read as 1.2 GB against a 12.15 GB source. Compare file counts and
  `find -printf '%s'` totals instead; both matched exactly.
* **`results/walloon/*` globs catch retired scenarios.** `scen_demande_haute` and
  `scen_test_2013_6h` still hold solved networks from earlier runs, and a loose
  glob reports them as this batch's progress — it produced one false "gate
  reached" during monitoring. Enumerate the scenario list explicitly.
* **`review_run.py` needs `PYTHONPATH` set** to the repo root or it dies on
  `ModuleNotFoundError: No module named 'scripts'`.

## 7. What must change before the next batch

| # | Action | Why |
|---|---|---|
| 1 | **Fix `cluster/probe.sh`** (§5.5) — match jobs via `.snakemake/slurm_logs/rule_*/<scenario>_*/` rather than Slurm job names, and fix the network count | It is the designated stall detector and it detected nothing. The one real failure was found by reading solver logs by hand |
| 2 | **Add a disk preflight and a mid-run disk check** (§5.6): abort if `/` or `/home` is below ~10 GB, and include both in the monitoring loop | A long unattended run on a machine with a filling root partition dies at an arbitrary point, with confusing symptoms (ssh timeouts, ENOSPC in unrelated tools) |
| 3 | **Scan solver logs for `Numerical trouble`/`INFEASIBLE` as part of monitoring**, not only at the end | `--keep-going` hides a failed horizon: the queue drains normally and nothing reports an error until the whole batch finishes |
| 4 | Promote `cluster/config_numericfocus.yaml` to the documented second-line remedy in the recipe's §8 table | `BarHomogeneous` alone was not enough |
| 5 | Run the post-process on **one** scenario before the other twelve | It cost 3.5 min and caught §5.4, which would otherwise have hit all 13 reports |
| 6 | Fix the missing 2050 per-horizon config snapshot (central §11 F5) | Level-0 provenance item |

## 8. Publication

**Nothing published.** Post-processing ran with `SKIP_S3_UPLOAD=1 HTML_PUBLISH=0`
throughout: open item 7 (§5.3) is unresolved and publication is outward-facing.
Local `csvs/`, `graphs/` and `html/pypsa/` are complete for 12 scenarios.

To publish once cleared: `RUN_NAME="<scenarios>" ./cluster/nic5.sh publish`.

## 9. Workstation environment incidents (2026-09-13 morning)

Three unrelated desktop-level faults hit within the same hour and between them
stopped all work. **None touched the results** — `results/` is on `/home` — but
each masqueraded as something else, so they are recorded with their real symptoms.

| # | Symptom seen | Actual cause | Fix |
|---|---|---|---|
| E1 | `ENOSPC` everywhere: conda, Snakemake, even the agent's own tooling; post-processing killed mid-run | `/` 100 % full — `/var/log/syslog` at **54 GB**, the COSMIC theme portal retrying a broken D-Bus pipe in a tight loop (~1.8 MB/s). Nothing to do with the run | `sudo truncate -s 0 /var/log/syslog` (not `rm` — rsyslog holds the fd). Recovered 51 GB. See instructions.md, "Disk preflight" |
| E2 | `ssh nic5` → *Connection timed out during banner exchange*. Survived a VPN bounce and the disk fix | Two overlapping problems: (a) bouncing `sqvpn` let **ProtonVPN** (`be-31.protonvpn.udp`) take the tunnel — it does not route to the CÉCI gateway; (b) `gcr-ssh-agent` spinning at 64 % CPU, so `ssh` hung querying it for a key | (a) `nmcli connection down be-31.protonvpn.udp && nmcli connection up sqvpn` — check `ip -br addr show tun0` reads **10.8.0.2/24**, not 10.96.x; (b) workaround `env -u SSH_AUTH_SOCK ssh …`, which works reliably |
| E3 | A killed Snakemake left a `pypsa2html` child writing `results/walloon/index.html` | The zombie pattern instructions.md already documents. Two writers on one output would have corrupted it | Killed the child, deleted the partial `index.html`, cleared `.snakemake/locks/` |

E1 and E2(b) are probably one fault: both the COSMIC portal and `gcr-ssh-agent`
are user-session D-Bus clients stuck retrying a broken session bus. **A logout or
reboot clears both**, which is why the session was restarted at the handoff.

## 10. Status at handoff — 2026-09-13 09:05, before workstation reboot

Nothing was running locally when the machine was rebooted; the cluster job is
unaffected by a local reboot.

| item | state |
|---|---|
| 2010 batch networks, solved + pulled | **51 / 52**, every one `Optimal objective` |
| scenarios post-processed (csvs/graphs/html) | **12 / 13** |
| `scen_central_2013` | **4/4 solved, pulled and post-processed** (15 CSVs) |
| `scen_central` critical review | **done** — `docs/logs/2026-09-13_scen_central_cabinet_batch_2010_1h.md` |
| `scen_realiste_nobnd30` @2050 | **running on NIC5**, job 11155390, converging (§5.1) |
| combined report `results/walloon/index.html` | **not built** — killed mid-write, partial file deleted |
| published to S3 / Explorer | **no** — deliberately (§8) |

### Resume checklist

```bash
# 1. VPN — confirm it is sqvpn, not ProtonVPN (E2)
nmcli -t -f NAME,TYPE connection show --active | grep vpn     # expect sqvpn
ip -br addr show tun0                                          # expect 10.8.0.2/24

# 2. Disk — both partitions (E1)
df -h / /home

# 3. Is the retry done?  (drop `env -u SSH_AUTH_SOCK` if the agent is healthy)
env -u SSH_AUTH_SOCK ssh nic5 \
  'cd /scratch/ulg/thermlab/squoilin/pypsa-wal;
   ls results/walloon/scen_realiste_nobnd30/networks/;
   grep -h "Optimal objective" results/walloon/scen_realiste_nobnd30/logs/*2050_solver.log'
```

Then, in order:

1. If the retry finished: `./cluster/nic5.sh pull`, then
   `RUN_NAME=scen_realiste_nobnd30 SKIP_S3_UPLOAD=1 HTML_PUBLISH=0 ./cluster/nic5.sh postprocess`,
   then `python scripts/walloon_scripts/fix_scenario_report_index.py --all`.
   If it failed again, widen to `Method: 1` or relax `BarConvTol` rather than
   re-running the same settings.
2. Rebuild the combined report — **allow ~15 min, it is slow**, and run it
   detached so a foreground timeout cannot orphan a child again (E3):
   ```bash
   TMPDIR=$PWD/tmp nohup snakemake --configfile config/config.walloon.yaml \
       --cores 4 results/walloon/index.html > tmp/combined_report.log 2>&1 &
   ```
3. Write the remaining solve logs: realiste pair, nuclear sweep, 2013.
4. Decide on publication (§8) — blocked on open item 7, the 2025 BEV fleet.
5. Act on §7 items 1–6 before the next batch.
