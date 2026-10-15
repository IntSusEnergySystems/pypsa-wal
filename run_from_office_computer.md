# Production runs from the office computer (via NIC5)

This machine is a **thin client for modelling**: nothing heavy ever runs
locally. Data preparation runs here only because it needs internet; every
Gurobi solve runs on the NIC5 / CÉCI cluster. Keep it that way — the local
disks cannot take a solve, and a 1h myopic chain needs ~4.5 h × 16 cores
plus ~37 GB RAM per horizon.

## 1. Disk layout — where things may live

*(Layout as of 10 Oct 2026, after the repo moved to the big disk.)*

| Path | Device | Size / free | Role |
|---|---|---|---|
| `/` | `/dev/sda1` | 46 GB / ~15 GB, 67 % used | OS **and `$HOME` (`/sylvain`)**: `~/.cache` (~2 GB), `~/.conda`, shell history. Nothing big may go here |
| `/home` | `/dev/sda5` | 64 GB / ~29 GB, 53 % used | legacy accounts only. **Nothing of ours lives here any more** (the old conda, `/home/anaconda`, is gone) |
| `/sylvain/mount` | **`/dev/sdb1`** (ext4) | **300 GB / ~182 GB free** | **code and all heavy data**. The mount point is root-owned: write only under `git/` and `pypsa-wal-data/` |

Do not confuse the 300 GB partition with the whole disk. `/dev/sdb` is 1.8 TB, but
`sdb2` is the 100 GB swap and `sdb3` (1.4 TB btrfs, `/srv/labothap`) is the lab server's
and not readable from here. **The old "1.7 TB free" no longer applies.**

**Where things are:**

| What | Path |
|---|---|
| repo | `/sylvain/mount/git/pypsa-wal` (`/sylvain/git` is a symlink to `/sylvain/mount/git`) |
| sibling checkouts (editable installs) | `/sylvain/mount/git/TIMES_PyPSA`, `/sylvain/mount/git/pypsa2html` |
| conda (Miniforge) + `pypsa-eur` env | `/sylvain/mount/pypsa-wal-data/miniforge3` (rebuilt 10 Oct; package cache `…/conda-pkgs`) |
| heavy data | `/sylvain/mount/pypsa-wal-data/` (results, resources, bundle, cutout, TIMES `.vd`, scripts, archives) |

The repo is now on the big disk itself, but the heavy trees stay redirected into
`pypsa-wal-data/` through the same symlinks as before, and **must stay that way**
(they keep the repo small and `push` copies them with `-L`):

```
resources/walloon  -> /sylvain/mount/pypsa-wal-data/resources/walloon
results/walloon    -> /sylvain/mount/pypsa-wal-data/results/walloon
data/bundle        -> /sylvain/mount/pypsa-wal-data/data-bundle
data/cutout        -> /sylvain/mount/pypsa-wal-data/data-misc/cutout
```

Rules:

- Never replace these symlinks with real directories, never `rsync` without
  `-K/--keep-dirlinks` into `results/`.
- **`$HOME` is on `/`.** Anything that defaults to `~/.cache`, `/tmp` or `~/.conda` fills the
  15 GB. For every long local job export `TMPDIR`, `XDG_CACHE_HOME` and `PIP_CACHE_DIR` under
  `/sylvain/mount/pypsa-wal-data/tmp/` (the env build script of 10 Oct does), and never put
  Snakemake benchmarks or ad-hoc outputs in `/tmp`, `~` or `/home`.
- **The `pypsa-eur` env is not on `PATH`** (`~/.bashrc` still points at the deleted
  `/home/anaconda`). Start every local command with
  `export PATH=/sylvain/mount/pypsa-wal-data/miniforge3/bin:$PATH`; `nic5.sh`'s default
  `LOCAL_RUN="conda run --no-capture-output -n pypsa-eur"` and the `smk_lowmem.sh` wrapper need it.
- Before any long run: `df -h / /home /sylvain/mount`. **Abort if `/` > 80 %, `/home` > 90 %, or
  `/sylvain/mount` has less than 40 GB free.** On 10 Oct the 182 GB held: results 41 GB, ClimAct
  analysis 17 GB, ClimAct extraction 9 GB, cutout (inside `data-misc`) 6.7 GB, archive 5 GB,
  resources 4 GB, the env ~10 GB. A ten-scenario batch adds ~13 GB of solved networks (1.3 GB each)
  plus CSVs, HTML and the explorer staging; move old trees to `results/_archive_*` (same disk,
  instant) rather than leaving them in `results/`, which `pull` syncs.
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

### 3b. NIC6 (first used 10 Oct 2026)

NIC6 is the successor of NIC5 (NIC5's nodes are to be merged into it, and **NIC5 storage is not
migrated**: copy what you still need). `REMOTE=nic6 ./cluster/nic5.sh <command>` targets it;
`cluster/config.sh` switches the solver overlay, core counts and Gurobi module on `REMOTE`.

| | NIC5 | NIC6 |
|---|---|---|
| partitions | `batch`, `hmem` | `batch` only |
| memory | by request (80 GB for a 1 h solve) | **1 900 MB per allocated core, a hard limit at submit**: memory is bought with cores |
| solve | 16 cores, 80 GB (`config_cluster.yaml`) | **32 cores, 60 GB** (`config_cluster_nic6.yaml`; Gurobi threads = 32) |
| `add_brownfield` | 1 core, 16 GB | **9 cores**, 16 GB (`LIGHT_CPUS`) |
| user limits | | 384 CPUs, 200 running jobs (QOS `normal`): five 32-core chains = 160 |
| scratch | `/scratch/ulg/thermlab/squoilin` | **same path string, different filesystem** (BeeGFS, empty at first) |
| job record | `cluster/.last_jobs_nic5` | `cluster/.last_jobs_nic6` |

**One-time local access (done 10 Oct):**
* `~/.ssh/config` had no `nic6` alias on this machine. Added a block like `nic5`'s (Hostname
  `nic6.uliege.be`, key `id_rsa.ceci`, `ProxyJump gwceci`, `ForwardX11 no`); backup
  `~/.ssh/config.bak-2026-10-10`.
* First connection: the host key was accepted after checking its ED25519 fingerprint against the one in
  `~/llm/env-nic6-ceci.md` (`SHA256:JwI+dSeRS8pq…`).

**One-time cluster setup — what had to change in the scripts (10 Oct):**
1. `nic5.sh setup` rsynced `envs/environment.yaml` into a directory that does not exist on a fresh
   cluster. It now creates `$REMOTE_DIR/envs`.
2. **The env must be a pinned copy of NIC5's, not a fresh build of `envs/environment.yaml`.** A fresh
   build on 10 Oct gave pypsa 1.3.0, linopy 0.9.1 and pandas 3.0.6; every NIC5 solve so far ran
   pypsa 1.2.1, linopy 0.6.1, gurobipy 13.0.2, pandas 2.3.3, snakemake 9.25.1.
   `envs/pypsa-eur_nic5_explicit.txt` is `conda list --explicit` of the NIC5 env; `cluster_setup.sh`
   builds from it when present (plus `pip install --no-deps snakemake==9.25.1`), and `nic5.sh setup`
   ships it. **The local env is built from the same file**, so the three environments agree. If NIC5
   goes away, keep this file: it is the only record of the validated package set.
3. Gurobi: the module `releases/2025b Gurobi/13.0.1-GCCcore-14.3.0` provides the licence;
   `setup` copies it to `~/gurobi.lic`. The licence file names **`TokenServer nic5.uliege.be`**: if
   NIC5 is decommissioned, check that NIC6 still gets a token.

**Checks that cost nothing and should be repeated before a NIC6 submit:**

```bash
ssh nic6 'sbatch --test-only --account=ceci --partition=batch --cpus-per-task=32 --mem=60000 --time=720 --wrap=true'
ssh nic6 'sbatch --test-only --account=ceci --partition=batch --cpus-per-task=9  --mem=16000 --time=120 --wrap=true'
```

The NIC5 shapes (16 cores × 80 GB, 1 core × 16 GB) are rejected at submit. Any rule that is
re-planned on NIC6 with the default 1 core × 16 GB therefore fails there (not on NIC5): after a push,
dry-run the solve targets on the cluster and check that only `add_brownfield` and
`solve_sector_network_myopic` are listed.

**A busy cluster: time limits decide whether a job starts (10 Oct, 16:00).** `cmd_solve` gave every rule
the 12 h `SOLVE_RUNTIME`. On a crowded NIC6 (all 12 nodes in use, other users with hundreds of queued
cores) the 9-core `add_brownfield` jobs, which take 15 s, were quoted a start **the next day**
(`squeue … %S`), and the next 32-core solves too, although 224 cores were idle: the backfill scheduler
only places jobs that fit a hole in time. Lowering the limit of the pending job fixed it at once:

```bash
ssh nic6 "scontrol update JobId=<id> TimeLimit=00:30:00"        # a user may lower, not raise, a limit
```

* `config.sh` now sets `LIGHT_RUNTIME=30` (minutes) for `add_brownfield` on both clusters, and
  `SOLVE_RUNTIME=360` on NIC6 only (a horizon takes 1.3–1.6 h there). NIC5 solves keep 12 h: one
  horizon once took 7.5 h (NumericFocus fallback).
* An orchestrator launched **before** that change keeps the old limits. For the 10 Oct batch a small loop
  on each login node (`cluster/shorten_light_jobs.sh`, runs while the orchestrator lives) lowers pending
  light jobs to 30 min (NIC6 also pending 32-core solves to 6 h).
* **Memory on NIC6.** With 32 Gurobi threads a 1 h solve peaks around 40-47 GiB (2025) and **49-50 GiB (2030)**,
  against a 58.6 GiB request; NIC5 at 16 threads stays near 29 GiB. The memory of a pending job can be raised
  without more cores: `scontrol update JobId=<id> MinMemoryNode=75000` (checked against 1.9 GB per core at submit
  only; `sacct` then shows `cpu=32,mem=75000M`). Running jobs cannot be changed. For the next NIC6 batch put
  `solving.mem_mb: 75000` in `cluster/config_cluster_nic6.yaml` and keep `cpus` = `threads` = 32, if the submit
  check allows it; otherwise `cpus: 40` and `threads: 32`.
* If a job is pending with a start time of tomorrow, look at `squeue --me --format='%i %T %C %l %r %S'`
  first, before blaming the partition.

**12-13 Oct batch (8 runs, NIC6 + NIC5), what it settled.**
* **NIC6 memory: 75 000 MB is required, not optional.** With 32 Gurobi threads the 24 NIC6 solves peaked at 50-59.0 GiB (`MaxRSS` of the `.0` step); seven were above 56 GiB and one at 59.0, i.e. above the old 58.6 GiB request.
  `cluster/config_cluster_nic6.yaml` now asks `cpus: 40`, `mem_mb: 75000` (40 x 1 900 MB passes the submit check) and keeps Gurobi `threads: 32`; the solve script does not read `snakemake.threads`. Worst solve: 81 % of the request.
* A full NIC6 (other users' multi-day jobs, 22 of 2 304 cores idle) still started all six 40-core solves within 50 minutes, with a 6 h limit and 30 min `add_brownfield` jobs.
* Speed: NIC6 about 2x NIC5 on the same LP (2025: 81 min vs 186 min; later horizons 28-50 min vs 53-102 min). Objectives of the identical LPs agree to 1e-6.
* `cmd_postprocess` runs `network_cost_report.py` / `bill_harmonisation.py` through `$LOCAL_PYTHON` (never `$LOCAL_RUN`) and dies if a CSV is missing: the `smk_lowmem.sh` wrapper can now stay in `LOCAL_RUN`.
* Publication with the new pypsa2html: 91 pages in 2 min, 3.4 GB peak; a whole scenario (ClimAct extraction, plot, S3, report, hub, rsync) about 10 min. The desktop app still crashed twice (SIGILL, 12 Oct 17:03 and 13 Oct 05:47) when an ad-hoc script ran beside an extraction: keep to one step at a time.
* Driver scripts of the batch: `/sylvain/mount/pypsa-wal-data/batch_20261012_scripts/` (`prepare.sh`, `land_all_b2.sh`, `publish_batch_b2.sh`, `probe_both_b2.sh`, `sacct_table.py`).

**Open points:** `$HOME` holds ~284 k files (Miniforge) against the stated 200 k quota; nothing was
refused so far, but `conda clean --all` is run after every env build to keep it down.
Because the two clusters use 16 and 32 Gurobi threads, a pair split across them (S1 on NIC5, S2 on NIC6)
differs in solver path as well as in inputs; see the batch log's run record.

**Measured on the 10 Oct batch (read 11 Oct, `sacct` `MaxRSS` of the solve step):**
* **NIC6, 32 threads, 60 000 MB: peaks 48.6-58.0 GiB = 83-99 % of the 58.6 GiB request** (five of 20 solves at 98-99 %).
  Nothing was killed, but there is no headroom. For the next NIC6 batch set `solving.mem_mb: 75000` in
  `cluster/config_cluster_nic6.yaml` (the `scontrol` bump of 10 Oct reached only two solves). NIC5 at 16 threads: 28.6-33.0 GiB of 80 GB.
* NIC6 solves a horizon in 28-40 min (2025: 77-135 min) against 59-106 min (2025: 122-222 min) on NIC5.
* **Cross-cluster comparability is fine:** on LPs that are identical by construction (2025 and 2030 of an S1/S2 pair) the objective agrees
  to ~1e-6 and no generator, link or storage-unit capacity differs by more than 15 MW. A pair split across NIC5 and NIC6 can be compared.
* After a `pull`, copy each cluster's `cluster/logs/orchestrate.log` under its own name (both clusters write the same file name locally).

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
| **pypsa2html, new library (`c306378`, 12 Oct), one scenario, caches bounded to 4** (`batch_20261012_scripts/html_lowmem_gc.py <s> 4`) | **3.1-3.8 GB, 2.3 min** (see the 12 Oct paragraph below) |

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

**pypsa2html, 11 Oct (supersedes the 7.8 GB figure above for the 10 Oct pypsa2html, `5e8fc7d`).** With the newer pages the report was
**OOM-killed at 10.5 GB** (`html_lowmem.py` with caches bounded to 2, and again with caches bounded to 1). The cache size is not what
drives it: the `Network` objects pypsa2html evicts hold reference cycles and are freed only when Python's cycle collector runs, so RSS climbs in a
sawtooth from ~6.6 to over 10 GB between collections. `batch_20261010_scripts/html_lowmem_gc.py` adds a daemon thread that runs
`gc.collect()` and `malloc_trim(0)` every 2 s (pypsa2html itself untouched) and bounds the cache to 1: **peak about 5-6 GB**, similar run time.
Use it instead of the stock rule on this machine until pypsa2html frees its networks itself.

**pypsa2html, 12 Oct (supersedes the 11 Oct paragraph and the "bounded to 2" figures above: 2 min per scenario, 3-4 GB).**
pypsa2html `c306378` (12 Oct) frees evicted networks (a forced collection on eviction, and the per-horizon node resolver holds its network by weak
reference), so the gc thread is no longer what keeps the memory down. The cache bound was kept at 2 by habit and it was then the whole cost:
a scenario report reads the four horizons in the same cycle (2025, 2030, 2040, 2050, over and over) for every page and region, and an LRU cache
of 2 against a cycle of 4 **never hits**. Every page reloaded its networks from disk.

| `scen_central`, 1 h, 4 horizons | caches bounded to 2 | caches bounded to **4** |
|---|---|---|
| network loads (`networks: loading` in `logs/pypsa2html.log`) | **656** (~3 s each) | **4** |
| report build (`build_site`) | **1 996 s (33 min)** | **145 s (2.4 min)** |
| peak RSS (`capped.sh`, cgroup) | 3.2 GB | 3.7-3.8 GB |
| pages written / sections skipped / failed | 91 / 40 / 0 | 91 / 40 / 0 |

The other nine scenarios of the 10 Oct batch, all at cache 4: build 134-142 s, peak 3.1-3.8 GB, 4 loads each. One whole publication
(build, hub, banner, rsync, S3 re-sync) takes about 4 min per scenario, so the nine scenarios took 36 min (18:13-18:49) where the cache-2 pace was
about 35 min *per scenario* for the build alone: **about 14x faster on the report, and the batch is no longer the long step.**

* **Use 4 on this machine** (`html_lowmem_gc.py <scenario> 4`, and `model.network_cache_size: 4` in `config/pypsa2html.yaml`). With the new library the
  report fits the 9.5 GB cap three times over; the old advice (1 or 2) only applies to pypsa2html before 12 Oct.
* The cache must be **at least the number of planning horizons** (4 here). Bound it below that and the build becomes I/O bound again with no memory gain
  worth having: watch `grep -c 'networks: loading' results/walloon/<s>/logs/pypsa2html.log`, which should be about the horizon count, not hundreds.
* **Output is unchanged.** `scen_central` rebuilt at cache 4 against the cache-2 build: 91 files, same names; after removing random element ids and
  timestamps, 81 are byte-identical, and in the 10 dispatch pages the traces are the same set but come in a different order (the series order is not
  deterministic between two builds, it is not caused by the cache).
* The new library also writes `html/pypsa/summaries/<scenario>/summary.{csv,json}` per scenario and builds a **comparison report from those summaries only**
  (no network is opened): `pypsa2html compare --config config/pypsa2html.yaml <summary.json of each run> --reference scen_central`, 112 s, 0.2 GB, output in
  `results/walloon/compare/` (23 pages, 21 MB). It was published to `https://pypsa.squoilin.eu/compare_20261010/` with the same key and host as the scenario
  folders (`rsync -a --delete` of `results/walloon/compare/` into `/home/pypsa/public_html/compare_20261010/`).
  Pass the `summary.json` paths: with `results/walloon/<s>` it reports "missing summary" because the summaries sit under `html/pypsa/summaries/<s>/`.
  The comparison draws all ten runs side by side, including the internal ones (`scen_realiste`, `scen_noco2cap`, `scen_test_lowccs_ptx`) and the S2 runs whose
  TIMES side is a placeholder: the banner of the scenario hubs does not appear on it.
* `config/pypsa2html.yaml`: `landing.page` and `output.pages` now say `key_figures` (the old `overview` still loads, with a warning, and is moved to the
  comparison report); a `compare:` block sets the reference run and `results/walloon/compare`.
* Driver: `/sylvain/mount/pypsa-wal-data/batch_20261012_scripts/publish_batch.sh B [scenarios]` (copy of the 10 Oct one, cache 4, same pinned date so the
  published folders are replaced). `cleanup-metadata` reports "metadata not present" after a rebuild: harmless, the driver treats it as non-fatal.

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

### 7.5 The publication chain on this machine (lessons of 11 Oct 2026)

* **Drivers** for a whole batch live in `/sylvain/mount/pypsa-wal-data/batch_20261010_scripts/`: `publish_batch.sh A` (ClimAct extraction,
  cost-segment plot, S3 upload) and `B` (pypsa2html with bounded caches, Sankeys and indicators, hub, banner, rsync to pypsa.squoilin.eu,
  S3 re-sync), `netcost_all.sh`, `run_locked.sh`. Every heavy step takes the same `flock` (`pypsa-wal-data/tmp/land.lock`) and runs in
  `cluster/capped.sh` with a cap of `min(budget, available - 2 GB)`, so a driver and an ad-hoc analysis can never overlap.
* **The extractor env `datapypsa` is rebuilt** (11 Oct) with the documented `conda create`; re-extracting the archived 6 Oct central
  reproduced the published 7 Oct Explorer set byte for byte (49/49 pypsa and 3/3 strategy CSVs). Extraction: 6-10 min, 7.6 GB peak.
* **`PATH` order matters:** `nic5.sh extract` needs a system `python3` with PyYAML; the miniforge base `python3` has none. Put
  `/sylvain/mount/pypsa-wal-data/miniforge3/bin` **last** in drivers (`conda`, `aws` still resolve).
* **`nic5.sh postprocess` runs `network_cost_report.py` and `bill_harmonisation.py` through `$LOCAL_RUN`.** With `LOCAL_RUN` set to a
  Snakemake-only wrapper (`smk_lowmem.sh`) they fail with a warning and the CSVs are silently missing (all ten trees of 10 Oct). Run them
  directly, and check `ls results/walloon/<s>/csvs | grep -c -E 'network_cost|bill_harm'` = 3 before pypsa2html and the cost-segment plot.
* **`pkill -f <pattern>` inside an agent shell command matches that command's own text and kills the shell:** kill by PID.
* **Do not read many files while a heavy step starts.** Swap is on `/dev/sdb2`, the same spindle as `/sylvain/mount`; after an
  extraction pushed ~1.7 GB of desktop pages into swap, a `git diff --stat` over `data/` and the next step's start both sat in
  uninterruptible I/O wait for minutes (random reads, ~140 IOPS, 95 % util). It clears by itself once the pages are back.
* The agent's `AskUserQuestion` blocks the whole turn: a permission question put while a long run is idle can cost hours. Ask early,
  and keep detached drivers running meanwhile.

Reference for everything above: `instructions.md` (operational guide),
`cluster/config.sh` (defaults), `cluster/config_cluster.yaml` (solve
resources), `docs/run-review-checklist.md` (is the run *right*, not just
finished), `cluster/capped.sh` (memory-capped local steps).
