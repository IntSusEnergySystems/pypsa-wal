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
| `batch` (~70 nodes) | ~258 GB | 6h test solves only |
| `hmem` (**3 nodes**) | **~1 TB** | **all 1h production solves (mandatory)** |

Mechanics:

- The partition is set **explicitly**, not inferred from the memory request:
  `SOLVE_PARTITION` in `cluster/config.sh` (default `hmem`), passed as
  `--default-resources slurm_partition=…` by `nic5.sh solve`.
- The memory request is `solving.mem_mb` in `cluster/config_cluster.yaml`
  (production: **100000** ≈ 100 GB), with `solving.cpus` = Gurobi
  `threads` = **16** (keep the three in sync). `SOLVE_RUNTIME` = 1440 min.
- Observed 1h peak is ~37 GB per solve. 100 GB leaves headroom **and still
  fits a shared (`mix`) hmem node**, so the job starts fast. Requesting the
  full ~1 TB forces an **exclusive node** on a 3-node partition — expect a
  long `Resources` wait whenever anyone else holds a node.
- Never send a 1h solve to `batch`: the LP spikes during Gurobi model
  generation and will OOM or crawl. (`batch` at ~100 GB is fine for 6h
  development tests only.)

Before submitting, look at the free spots (also wrapped by
`./cluster/nic5.sh status`):

```bash
ssh nic5 "sinfo -p hmem -o '%P %a %D %t %C %m'"
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
4. Changing weather year or resolution invalidates `resources/` and
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

Reference for everything above: `instructions.md` (operational guide),
`cluster/config.sh` (defaults), `cluster/config_cluster.yaml` (solve
resources), `docs/run-review-checklist.md` (is the run *right*, not just
finished).
