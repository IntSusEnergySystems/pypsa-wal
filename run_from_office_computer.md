# Production runs from the office computer (via NIC5)

This machine is a **thin client for modelling**: nothing heavy ever runs
locally. Data preparation runs here only because it needs internet; every
Gurobi solve runs on the NIC5 / CÉCI cluster. Keep it that way — the local
disks cannot take a solve, and a 1h myopic chain needs ~4.5 h × 16 cores
plus ~37 GB RAM per horizon.

## 1. Disk layout — where things may live

| Path | Device | Size / free | Role |
|---|---|---|---|
| `/` (incl. `/sylvain/git/…`) | `/dev/sda1` | 46 GB / ~16 GB | code only |
| `/home` | `/dev/sda5` | 64 GB / ~9 GB, 85 % used | almost full — write nothing big here |
| `/sylvain/mount` | **`/dev/sdb1`** | **1.7 TB / ~1.6 TB free** | **all heavy data** |

The repo lives at `/sylvain/git/pypsa-wal` (small disk), but every heavy
tree is redirected onto `/dev/sdb1` and **must stay that way**:

```
resources/walloon  -> /sylvain/mount/pypsa-wal-data/resources/walloon
results/walloon    -> /sylvain/mount/pypsa-wal-data/results/walloon
data/bundle        -> /sylvain/mount/pypsa-wal-data/data-bundle
data/cutout        -> /sylvain/mount/pypsa-wal-data/data-misc/cutout
```

Rules:

- Never replace these symlinks with real directories, never `rsync` without
  `-K/--keep-dirlinks` into `results/`, and never point `TMPDIR`,
  `XDG_CACHE_HOME`, Snakemake benchmarks, or ad-hoc outputs at `/`, `/home`
  or `/sylvain/git` directly.
- Before any long run: `df -h / /home` (abort if `/home` > 90 % or `/` >
  80 %) and `df -h /sylvain/mount` (needs tens of GB free; one scenario is
  ~1.3 GB of solved networks plus the 6.6 GB weather cutout, already cached).
- `./cluster/nic5.sh push` uses `-L/--copy-links`, so the cluster receives
  real files — the symlinks above are a local-only arrangement.

## 2. What runs where

| Step | Where | Command |
|---|---|---|
| `prepare` (un-solved networks, needs internet) | **local** | `./cluster/nic5.sh prepare` (~50 min, 16 cores) |
| `push` (rsync code + inputs to scratch) | local → NIC5 | `./cluster/nic5.sh push` |
| `solve` (myopic chain, 4 horizons) | **NIC5 only** | `./cluster/nic5.sh solve` |
| `pull` (solved `results/` back) | NIC5 → local | `./cluster/nic5.sh pull` |
| `postprocess` (touch + CSVs + plots + S3 upload) | **local** | `./cluster/nic5.sh postprocess` |
| `extract` + `upload`/`publish` (Explorer CSVs → S3) | local | `./cluster/nic5.sh publish` |
| pypsa2html report + `html_publish` | local (postprocess targets) | part of `postprocess` |

**Every local step that is not `prepare`/`push` (post-processing, extraction, review,
ad-hoc network reading) is heavy for this 15.9 GB machine: follow §7 (one at a time, capped).**

`./cluster/nic5.sh run` chains all of the above. NIC5 compute nodes have
**no internet**, so `prepare` must succeed locally first; Snakemake itself
runs on the NIC5 **login node** and submits each rule to Slurm.

Defaults live in `cluster/config.sh`: `CONFIGFILE=config/config.walloon.yaml`,
`RUN_NAME=scen_demande_haute`, `RUN_PREFIX=walloon`
(results in `results/walloon/scen_demande_haute/`). Override per command,
e.g. `RUN_NAME=scen_base ./cluster/nic5.sh solve`.

## 3. Memory and partitions — how not to queue forever

NIC5 node sizes (check live with `sinfo -o '%P %a %D %t %C %m'`):

| Partition | Nodes | RAM per node | Use for |
|---|---|---|---|
| `batch` (~70 nodes) | ~258 GB | **default for 1h solves** (80 GB request) |
| `hmem` (**3 nodes**) | **~1 TB** | fallback when `batch` has no node with 16 free cores |

Mechanics:

- The partition is set **explicitly**, not inferred from the memory request:
  `SOLVE_PARTITION` in `cluster/config.sh` (default **`batch`** since the
  12 Sep cabinet batch), passed as `--default-resources slurm_partition=…`
  by `nic5.sh solve`. Override per command: `SOLVE_PARTITION=hmem ./cluster/nic5.sh solve`.
- The memory request is `solving.mem_mb` in `cluster/config_cluster.yaml`
  (**80000**), with `solving.cpus` = Gurobi `threads` = **16** (keep the three
  in sync). `SOLVE_RUNTIME` = **720** min; the NumericFocus fallback of
  13 Sep took 7.5 h on one horizon, still inside it.
- Measured 1h peaks: 20–31 GB (24 Sep), 31–35 GB (29 Sep). 80 GB is ample
  and fits a shared `batch` node. The 13 Sep batch ran 13 chains on `batch`,
  all RUNNING within four minutes; on `hmem` it would have run one or two at a
  time.
- **Which partition:** read `sinfo` before every `solve`. On 29 Sep `batch` had no
  node with 16 free cores after 15:30 and the chain moved to `hmem` mid-run.
  Requesting the full ~1 TB of `hmem` forces an exclusive node — never do that.
- (Superseded, kept for history: until 12 Sep this section said `hmem` was
  mandatory at 100 GB. The measured peaks above are why that changed.)

Before submitting, look at the free spots (also wrapped by
`./cluster/nic5.sh status`):

```bash
ssh nic5 "sinfo -p batch,hmem -o '%P %a %D %t %C %m'"
ssh nic5 "squeue -p hmem -h -o '%T' | sort | uniq -c"          # by state
ssh nic5 "squeue -p hmem -h -o '%u' | sort | uniq -c | sort -rn | head"  # by user
ssh nic5 "squeue --me --format='%.18i %.10P %.26j %.8T %.10M %R'"
```

Reading the queue: a triple-digit PENDING count dominated by **one user**
with reason `AssocGrpJobsLimit`/`AssocGrpQos` is a per-user cap, **not**
real contention — it does not block our job. What matters is `sinfo`:
`idle` nodes, or `mix` nodes whose free memory covers our 100 GB. If all 3
hmem nodes are `alloc` with no free memory, wait before submitting (or ask
the team) rather than stacking another pending 1 TB request.

## 4. Launch order (agent behaviour)

1. **Launch the long pole first.** Start `./cluster/nic5.sh prepare`
   detached immediately (`setsid nohup … &`, log in `cluster/logs/`); run
   all verification **in parallel**, never sequentially before it.
2. Verify while `prepare` runs: branch clean + up-to-date, weather block
   (`snapshots.*` + `atlite.default_cutout` all say **2010** — mixed years
   silently pair one year's demand with another year's wind/sun),
   `resolution_sector: 1h`, single `run.name`, `.vd` symlink target exists,
   `python scripts/build_common_parameters.py --check` passes, and local
   `results/` are not newer than HEAD (stale solves from before the latest
   fix commits must be re-run, not shipped).
3. Chain without asking: `push` → `solve` as soon as `prepare` reports
   `N of N steps (100%) done`.
4. **Several groups of runs in parallel need one NIC5 directory each.** Two
   orchestrators cannot share a directory. Clone the second one on the cluster
   side (`rsync -a` with *anchored* excludes: `/results`, `/tmp`, `/.cache`,
   `/cluster/logs`, `/.snakemake/locks`, `/.snakemake/incomplete`), then
   `REMOTE_DIR=<clone> ./cluster/nic5.sh push`.
   * Keep `resources/` in the clone when the runs share the run prefix. Without
     it, `push` resends every prepared tree over the office uplink.
   * Archive old trees on NIC5 **outside** `results/`: `pull` syncs all of
     `results/`, and only `results/walloon` is a symlink onto `/sylvain/mount`.
   * A scenario name new to this machine prepares its whole per-scenario chain,
     ~100 jobs. An existing tree needs ~45 after a new `.vd`.
   * Worked example: `docs/logs/2026-09-30_cabinet_batch_20260930_2010_1h.md` §5.
5. Changing weather year or resolution invalidates `resources/` and
   Snakemake will not always notice (`KeyError` on the snapshot index deep
   in `prepare_sector_network`): `rm -rf resources/walloon/<scenario>` and
   rebuild.

## 5. Probes — every 30 minutes, on explicit request

The agent driving the run (opencode) has **no autonomous execution between
messages**: it cannot wake itself up, run a probe, or advance the pipeline
unprompted. Every status check and every pipeline step happens because
someone asked for it in chat. (Cursor's background agents on this same
machine did support unattended follow-up; opencode does not — Sep 2026.)
Do not rely on "the next probe is armed" assurances; ask `status?` instead.

*Exception (4–5 Oct 2026):* the Claude desktop agent can arm `Monitor` loops that report
back on their own (a state watcher every 5 min, a probe every ~25 min). They expire after
~30 min and **die with the session**, so re-arm them, and never treat a silent monitor as a
healthy run: check `squeue` yourself after any crash (§7.3).

Each `status?` collects the same four signals:

```bash
# queue + orchestrator
./cluster/nic5.sh status
# or directly:
ssh nic5 "squeue --me --format='%.18i %.10P %.26j %.8T %.10M %R'"
ssh nic5 "tail -5 /scratch/ulg/thermlab/squoilin/pypsa-wal/cluster/logs/orchestrate.log"
# live solve progress (job id from the orchestrator log):
ssh nic5 "tail -5 /scratch/users/s/q/squoilin/pypsa-wal/.snakemake/slurm_logs/rule_solve_sector_network_myopic/<run>_adm___<year>/<jobid>.log"
```

What “healthy” looks like per horizon (~1 h each, ~4.5 h chain):

- Job state `RUNNING` (`PD` with reason `Resources` for >30 min on `hmem`
  means reconsider the memory request, §3).
- Gurobi log: barrier iterations advancing, primal/dual residuals and the
  gap shrinking monotonically (e.g. `6.9e+05 → 4.5e+05` over a few
  iterations). `Numerical trouble` / stall of the gap over hundreds of
  seconds = investigate (cf. `BarHomogeneous: 1` note in
  `cluster/config_cluster.yaml`).
- `grep -c 'Optimal objective' results/walloon/<scenario>/logs/*_solver.log`
  grows 1 → 4 as horizons complete.

If a horizon fails: read the `.log` in the slurm_logs directory above and
`cluster/logs/orchestrate.log`, fix, and re-`solve` (Snakemake resumes the
chain; never `--forcerun` a solve rule). To abort: `./cluster/nic5.sh stop`,
then verify with `pgrep -af 'snakemake|gurobi'` locally and `squeue --me`
remotely, and clear stale `.snakemake/locks/*.lock` only once nothing runs.

## 6. Landing the run

1. `./cluster/nic5.sh pull`, then verify: orchestrator log ends with
   `N of N steps (100%) done`, four
   `results/walloon/<scenario>/networks/base_s_adm___*.nc` present,
   `grep 'Optimal objective' results/walloon/<scenario>/logs/*_solver.log`
   hits 4/4.
2. `./cluster/nic5.sh postprocess` (touches solves, rebuilds CSVs/plots,
   pypsa2html pages, TIMES Sankeys, publishes HTML, uploads to S3 `test/`
   by default — `SKIP_S3_UPLOAD=1` to skip).
3. `./cluster/nic5.sh publish` for the Wallonie Explorer (extract + upload),
   and confirm the `pypsa.squoilin.eu` URL sentinel
   (`results/…/logs/html_published.url`).
4. **Solve log is mandatory** (`instructions.md` § Logs): copy
   `docs/logs/_TEMPLATE_solve_log.md` to
   `docs/logs/YYYY-MM-DD_<scenario>_<tags>.md`, fill §§1–10, and fill §11
   (critical review per `docs/run-review-checklist.md`, incl. the scripted
   checks `PYTHONPATH=. python scripts/walloon_scripts/review_run.py
   results/walloon/<scenario>` and `check_heat_profile_fidelity.py`) before
   any result leaves the team. A run without its log is not finished.

## 7. Local memory budget — how not to crash the desktop

**What happened.** On 5 Oct 2026 the Claude desktop app died twice while heavy local steps
ran (08:05 at the end of an extraction/publication sequence, 15:14 as a review script started
right after a post-processing); a third time on 1 Oct 08:54. Every time the signature is the
same and **is not in the kernel log**:

```bash
coredumpctl list --no-pager | tail -5        # SIGILL in /usr/lib/claude-desktop/claude-desktop
journalctl -b 0 -k | grep -i -E "oom|killed process"      # empty: it is not the kernel OOM killer
```

SIGILL is how Chromium/Electron aborts on a failed allocation. This is a **diagnosis by
elimination, not a proof**: the application aborts itself, so no kernel line says "memory".
What is certain is the budget below, and that the swap makes it worse.

**The budget** (15.9 GB RAM):

| Consumer | Resident |
|---|---|
| desktop baseline: Claude desktop ~1.9 GB, Cursor ~1.9 GB, opencode ~0.7 GB, Firefox ~0.6 GB, agents ~0.6 GB | **4–4.5 GB** |
| free for a heavy step | **~11 GB** |
| **swap: 100 GB on a spinning disk (`/dev/sdb2`)** | *not* extra memory: a step that spills there stalls the whole machine |

**Measured peaks** (cgroup `memory.peak`, one 1 h four-horizon tree, 5 Oct):

| Step | Peak |
|---|---|
| `nic5.sh prepare` (with `--resources mem_mb=20000`) | 5–6 GB |
| `nic5.sh postprocess`, pypsa2html report (with the `mem_mb=14000` cap) | 9–13 GB |
| **`nic5.sh extract` (ClimAct extraction)** | **8.5 GB** |
| `review_run.py` | 4.7 GB |
| `ptx_report.py` | 3.1 GB |
| `network_cost_report.py`, `bill_harmonisation.py`, `check_heat_profile_fidelity.py` | 2–3 GB (not separately measured) |
| one network loaded in `python` for an ad-hoc look | 2–3 GB |
| pypsa2html alone, **network caches bounded to 2** (`batch_20261006_scripts/html_lowmem.py`, 6 Oct) | **7.8 GB** (36 min) |
| pypsa2html inside `postprocess`, unbounded (6 Oct, other scenario trees on disk) | **> 10 GB**: OOM-killed in a 10 GB cap |

**pypsa2html (6–7 Oct).**
* **Fixed in pypsa2html on 7 Oct:** `model.network_cache_size` is now a real process-wide bound.
  `config/pypsa2html.yaml` sets it to **2** for this machine, so the normal
  `generate_html_report` rule fits: about 7.8 GB, about 36 min per scenario.
* The single-scenario rule still reads every scenario of `config/pypsa2html.yaml` whose tree is
  on disk. **List only scenarios of the same vintage there.**
* **With an older pypsa2html (before the fix):**
  * The process-wide `_PATH_CACHE` kept every network whatever the setting, so `postprocess` was
    OOM-killed in `generate_html_report`.
  * Workaround: `batch_20261006_scripts/html_lowmem.py <scenario> 2`, then
    `snakemake --cleanup-metadata <…/html/pypsa/index.html>`.
  * Then build the `write_html_hub` target alone. Dry-run it first: it must show 1 job.
  * Do not re-run `postprocess` after that: its `--touch` makes the report stale and rebuilds it.

### 7.1 Rules

1. **One heavy step at a time. Never two.** Extraction (8.5 GB) plus a review script
   (4.7 GB) plus the desktop baseline is 17 GB: more than the RAM. Drivers must run steps
   strictly in sequence, with no `&` between heavy steps.
2. **Wrap every heavy local step in `cluster/capped.sh`.** It runs the step in its own cgroup
   with a hard cap and **no swap**, so a runaway step is killed alone (exit 137) instead of
   dragging the desktop into swap. It prints the real peak at the end.

   ```bash
   RUN_NAME=scen_central cluster/capped.sh 10G extract -- ./cluster/nic5.sh extract
   PYTHONPATH=. cluster/capped.sh 8G review -- conda run --no-capture-output -n pypsa-eur \
       python scripts/walloon_scripts/review_run.py results/walloon/scen_central
   SKIP_S3_UPLOAD=1 HTML_PUBLISH=0 LOCAL_CORES=4 cluster/capped.sh 14G post -- \
       ./cluster/nic5.sh postprocess
   ```

   Suggested caps: extraction 10G, pypsa2html / postprocess 14G, review 8G, ad-hoc network
   reading 6G. Tested 5 Oct: a 900 MB allocation in a 300 MB scope is killed with exit 137 and
   the swap does not move.
3. **Check before you start**: `free -m` column *available* must be at least the step's peak
   plus 3 GB. If not, close Cursor and Firefox (3 GB between them) before an extraction or a
   post-processing; do not start the step on a hope.
4. **Keep the number of resident helpers small.** No second agent session, no second editor,
   no browser tabs of the published reports while a heavy step runs.
5. **`nic5.sh extract` refuses to run while `review_run.py` runs, and without swap** (it
   checks `SwapTotal`). Do not bypass it with `NIC5_ALLOW_NO_SWAP=1`; use the cap instead.

### 7.2 Drivers and scratch files must survive a crash

The agent's scratchpad (`/tmp/claude-…/scratchpad`) is **wiped when the session restarts**.
On 5 Oct a publication driver kept there silently did nothing after the crash
(`nohup: failed to run command … No such file or directory`) and 30 minutes were lost.

* Keep every driver, wrapper and helper under `/sylvain/mount/pypsa-wal-data/<batch>_scripts/`
  (this batch: `batch_20261004_scripts/`), never in `/tmp` or the scratchpad.
* Start long local jobs with `setsid nohup <script> > cluster/logs/<name>.out 2>&1 < /dev/null &`
  and give every step a log in `cluster/logs/`.
* Make a driver print one line per step (`### HH:MM step`, `exit=N`) and a final marker
  (`ALL_..._DONE`). After a crash the last marker tells where it stopped.
* **A launch is not a success until its first output line exists**: check the `.out` file
  30 seconds later.

### 7.3 What to do first when the app dies

1. `uptime; who -b; free -m; coredumpctl list --no-pager | tail -3`: did the machine reboot,
   or only the app?
2. `pgrep -af 'snakemake|gurobi|extract|upload|publish_seq|post_seq|test_all'`: did the
   detached drivers survive? `setsid` jobs do; the agent's monitors do not.
3. **The cluster side is untouched by a local crash.** Slurm jobs and the orchestrator run on
   the NIC5 login node:
   `ssh nic5 "squeue --me -h; ps -u \$USER -o pid,etime,cmd | grep snakemake | grep -v grep"`.
4. Check the last marker of each driver in `cluster/logs/*.out` and re-run only the missing
   steps. `postprocess` and `extract` are idempotent; `upload` overwrites the same S3 keys.
5. Re-arm the monitors (they have no memory of the previous session).

### 7.4 Verifying an interrupted publication

```bash
export AWS_PROFILE=intervectoriel
for s in <scenarios>; do
  aws s3 ls s3://intervectoriel/test/scenarios/times-pypsa__${s}-2010-1h__$(date +%Y%m%d)/ --recursive \
    | awk -v s=$s '{n++; if($3==0)z++} END{print s": "n" files, "z+0" empty"}'   # expect 53, 0
  curl -s -o /dev/null -w "$s %{http_code}\n" https://pypsa.squoilin.eu/${s}_$(date +%Y%m%d)/pypsa/index.html
done
```

A half-written Explorer set looks valid on S3 (the extraction is not atomic). 53 files, none
empty, and the log of the extraction ending with `Extraction complete` are the checks; if in
doubt, re-run `extract` (about 4 min per scenario) and `upload`.

Reference for everything above: `instructions.md` (operational guide),
`cluster/config.sh` (defaults), `cluster/config_cluster.yaml` (solve
resources), `docs/run-review-checklist.md` (is the run *right*, not just
finished), `cluster/capped.sh` (memory-capped local steps).
