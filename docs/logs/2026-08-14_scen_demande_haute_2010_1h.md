# Solve log — scen_demande_haute @ 2010, 1h

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-08-14 17:12 → 2026-08-15 00:50 (solve + postprocess); Explorer extraction 2026-08-16 |
| Operator | opencode agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `times-pypsa` |
| Config file(s) | `config/config.times-pypsa.yaml`; on NIC5 also `cluster/config_cluster.yaml` |
| Code version | pypsa-wal master `9e28e524` + this run's working-tree edits (all listed in §9; reviewed and committed on 2026-08-16) |
| Outcome | success (4/4 horizons optimal; full publication incl. Explorer CSVs) |

## 2. Goal of the run

First full pypsa-wal run of the latest TIMES "demande haute" scenario
(`scen_demande_haute_v01_260727_fix_nuc_2807.vd`, Jul 2026 TIMES re-run,
nuclear-aligned with the Elia/cabinet central path) at **1h sector time
resolution** and **2010 weather year** — up from the previous 6h / 2013-study
configuration — to capture hourly dynamics (EV charging shape, solar
coincidence, peaks). Local machine (16 GB RAM) cannot hold the LP, so the
solve was offloaded to NIC5 `hmem`.

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_demande_haute_v01_260727_fix_nuc_2807.vd` (from `s3://intervectoriel/test/scenarios/times_20260727/`) |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` (6.58 GB) |
| Snapshots | 2010-01-01 → 2011-01-01, 8760 hourly (verified in built networks) |
| Sector time resolution | `1h` (was 6h) |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi (barrier), 16 threads, `mem_mb=1000000` on cluster |
| Key scenario overrides | `retrofit_nuclear_once: false` (Tihange retrofit repeatable, 1 GW through 2050); agg caps `agg_p_nom_minmax_demande_haute.csv`; `bev_dsm_availability: 0.01` (Elia) |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval + network build (prepare) | local | 8 cores, `--rerun-incomplete`, caches + cutout + resources on `/sylvain/mount` (1.8 TB sdb1) |
| LP solve | NIC5 `hmem` | 16 cpus/task, ~1 TB mem, Slurm orchestrator on login node, `MAX_SLURM_JOBS=2` (chain is serial anyway) |
| Post-processing (CSVs, plots) | local | `-call all` equivalent, 8 cores, `--keep-going` |
| HTML report (pypsa2html) | local | pypsa2html @ `ed50fab` (pip `-e --no-deps`) |
| Explorer CSV extraction (ClimAct) | local | extractor from Nextcloud zip on `/sylvain/mount`, env `datapypsa` (pypsa 0.35.2) |

Cluster specifics: node `nic5-w071` for all solve jobs. Queue wait **< 1 min**
(hmem had 2 idle nodes; the 228 pending jobs were another user's, gated by
their group limit, and did not delay us).

Local storage layout — `/` and `/home` nearly full, so all large data lives on
`/sylvain/mount/pypsa-wal-data` (1.8 TB `/dev/sdb1`, SMART/dmesg
health-checked before use), reached from the repo via symlinks (no tracked
files moved):

| On `/sylvain/mount/pypsa-wal-data` | Repo symlink |
|---|---|
| `data-misc/cutout/archive/v1.0/europe-2010-sarah3-era5.nc` (6.58 GB) | — (workflow reads `data/cutout/…`; `cutouts/` also points there) |
| `resources/times-pypsa/` (run tree) | `resources/times-pypsa` |
| `results/times-pypsa/` (run tree) | `results/times-pypsa` |
| `data-bundle/`, `data-osm/`, `data-misc/ship_raster/` | `data/bundle`, `data/osm`, `data/ship_raster` |
| `smk/{storage,cache-pypsa-eur,source-cache}` | `.snakemake/storage`, `~/.cache/snakemake-pypsa-eur`, `~/.cache/snakemake` |

`data/walloon/scen_demande_haute_v01_260727_fix_nuc_2807.vd` is a **real file**
(copy of `TIMES_PyPSA/data/…vd`) so the cluster push (`rsync -L`) transfers it.

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (prepare → S3 uploaded) | ~7 h 40 m (2026-08-14 17:12 → 00:50) |
| Prepare (network build, 105 jobs) | 41 min final pass; 1 h 22 m elapsed incl. 2 aborted attempts (disk-full, then Python 3.14 bug) |
| Push to cluster (2.1 GB) | ~5 min |
| Queue wait | < 1 min |
| Solve 2025 | Gurobi barrier 59 min; ~85 min total job (incl. build + write) |
| Solve 2030 | barrier 38 min; ~50 min total |
| Solve 2040 | barrier 47 min; ~65 min total |
| Solve 2050 | barrier 57 min; ~70 min total |
| Solve chain total (4 horizons serial) | 4 h 21 m (18:54 → 23:15) |
| Pull results (1.36 GB) | ~3 min |
| Post-processing + plots (79 jobs) | ~45 min (one aborted attempt) |
| pypsa2html report | 112 s (75 pages) |
| S3 upload (1.8 GB, 1737 files) | ~1 min |
| ClimAct extraction | ~5 min (after OOM retry, see §9) |

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size 2025 | 31.2 M rows × 14.8 M cols × 74.8 M nnz |
| LP size 2030 | 39.8 M rows × 19.4 M cols × 95.3 M nnz |
| LP size 2040 | 43.2 M rows × 21.4 M cols × 103.8 M nnz |
| LP size 2050 | 43.9 M rows × 21.9 M cols × 104.6 M nnz |
| Peak RAM per solve (python-side MEM log) | 2025: 28.8 GB · 2030: 33.9 GB · 2040: 36.5 GB · 2050: 37.6 GB (well under the 1 TB hmem request; ≫ the 15 GB local machine, hence the cluster) |
| Peak RAM local phases | ~1 GB × 8 parallel jobs (prepare); ClimAct extraction OOM'd once at 9.5 GB with 15 GB total and no swap |
| Disk footprint | resources: 937 MB · results: 1.9 GB (networks 1.36 GB) — on `/sylvain/mount/pypsa-wal-data` |

## 7. Results

| Horizon | Status | Objective |
|---|---|---|
| 2025 | optimal | 3.94454871e+11 |
| 2030 | optimal | 3.95242527e+11 |
| 2040 | optimal | 3.22336045e+11 |
| 2050 | optimal | 3.37531205e+11 |

Local result folders:

- Networks: `results/times-pypsa/scen_demande_haute/networks/base_s_adm___{2025,2030,2040,2050}.nc`
- CSVs / plots: `results/times-pypsa/scen_demande_haute/{csvs,graphs,graphics,maps}/`
- HTML report: `results/times-pypsa/scen_demande_haute/html/index.html` (75 pages, 0 failed)

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | `s3://intervectoriel/test/pypsa_raw_results/20260814_times-pypsa_scen_demande_haute/` (1737 files) |
| Scenario folder on S3 | `s3://intervectoriel/test/scenarios/times-pypsa__demande-haute-2010-1h__20260814/` |
| Explorer display label | `demande-haute-2010-1h (times-pypsa) - 14/08/2026` |
| Explorer CSVs | 49 in `pypsa/`, 3 in `strategy/` — extracted 2026-08-16 (ClimAct tool v6 tag, `datapypsa` env), verified on S3 |
| TIMES vd staged | yes — `explorer/times/scen_demande_haute_v01_260727_fix_nuc_2807.vd` |
| Verified in Explorer dropdown | S3 layout verified (49/3/1 files); visual check in the app pending — open https://explorer.test.wallonie.climact.com/ and "Clear cache" if the label `demande-haute-2010-1h (times-pypsa) - 14/08/2026` does not appear |

## 9. Issues encountered and fixes

All edits below were working-tree changes at run time (2026-08-14); they were
reviewed for quality/robustness/backward compatibility and committed on
2026-08-16 — generic fixes may still be worth upstreaming (see §10). In order
of appearance:

- **`envs/environment.yaml` invalid YAML** (over-indented `- pip:` block) —
  conda/micromamba refused the env file; re-indented.
- **Root disk full (46 GB `/`)** — Snakemake HTTP storage cache + ship raster
  filled `/`; redirected `.snakemake/storage`, `~/.cache/snakemake*`, cutout,
  data/bundle, resources, results to the 1.8 TB `/sylvain/mount` (health-checked,
  see below), freed `/` to 23 GB.
- **Python 3.14 `Enum.__init__` TypeError** in
  `scripts/definitions/heat_system.py` killed all
  `build_industrial_production_per_country_tomorrow` jobs — removed the no-op
  `__init__` override.
- **Cutout path**: workflow expects `data/cutout/archive/v1.0/…nc`, not
  `cutouts/` — moved the downloaded file, cleared `.snakemake/incomplete`.
- **Stale Snakemake locks** after killing the disk-full run — removed
  `.snakemake/locks/*` (documented failure mode in instructions.md).
- **NIC5 home file-quota full (209k/210k files)** — `conda clean -a` freed
  15k files; snakemake upgraded 9.21.1 → 9.25.1 via pip (scratch-cached).
  `cluster/cluster_setup.sh` was also edited to strip the local
  `-e ../TIMES_PyPSA` pip section into a temp yaml (no sibling checkout on
  NIC5; the solve chain does not import it).
- **`WildcardError: No values given for wildcard 'run'` on cluster only** —
  bisected to `--runtime-source-cache-path` in `cmd_solve` (forces source
  provisioning of *all* rules incl. unused SEPIA rules with unbindable `{run}`
  log paths); flag removed, `XDG_CACHE_HOME` already covers the cache.
- **`nic5.sh` ignored `RUN_PREFIX`** — all target builders hard-coded
  `results/<RUN_NAME>/`; added `RUN_DIR_REL` (also fixed `--copy-links` push
  so symlinked inputs arrive as real files on the cluster). `cmd_prepare`
  gained `--rerun-incomplete` (resume after disk-full crash).
- **Local postprocess SIGTERM** on `plot_balance_timeseries` (no kernel OOM
  for that pid; likely agent shell timeout) — plain relaunch with
  `--keep-going` completed 79/79.
- **sdb1 health check before use** (known bad-block history): SMART clean,
  no dmesg errors — verdict OK (root script, not committed).
- **ClimAct extractor from Nextcloud zip**: (a) `graph_extraction_main.py`
  lacked the `EXTRACTION_CONFIG` env-var patch — re-applied (one line + `import
  os`); (b) template `config_extraction_OET.yaml` (the de-facto Walloon
  template inside the zip, despite the name) had `download_networks: True` /
  `upload_results: True` — flipped to False/False to read the local symlink
  and keep upload in `upload_s3.sh`; (c) **first run OOM-killed** at 9.5 GB
  (15 GB machine, no swap) — fixed by adding 32 GB swap on `/sylvain/mount`
  (`/tmp/opencode/make_swap.sh`, root, active until reboot); retry used
  ~3 GB swap and completed in ~12 min.

Other deliberate edits for this run (not failures, also committed):

- `config/config.times-pypsa.yaml`: added `snapshots` **and**
  `atlite.default_cutout` for 2010 (both must change together — 2013 default
  otherwise), `resolution_sector: 6h → 1h`.
- `cluster/config.sh`: defaults set to `CONFIGFILE=config.times-pypsa.yaml`,
  `RUN_NAME=scen_demande_haute`, `RUN_PREFIX=times-pypsa`,
  `EXPLORER_SCENARIOS="scen_demande_haute:demande-haute-2010-1h"` (label
  carries the 2010+1h tag), `SOLVE_RUNTIME: 360 → 1440` min.
- pypsa2html clone, `config/pypsa-wal.yaml`: `root:` repointed from
  `/home/sylvain/svn/pypsa-wal` (old workstation) to `/sylvain/git/pypsa-wal`.

## 10. Follow-ups / pending

- Visual check in the Explorer test-site dropdown (Clear cache if needed),
  label `demande-haute-2010-1h (times-pypsa) - 14/08/2026`.
- 6h vs 1h comparison (this run vs `times-pypsa__demande-haute__20260814`
  uploaded from the svn workstation) — same vd, different resolution/weather
  year; check evening-peak understatement documented in instructions.md
  (2026-only Elia charging shape).
- Port the generic fixes upstream where they originate (`heat_system.py` →
  PyPSA-Eur; `environment.yaml` pip-indentation lesson for any repo carrying
  that block) — they are not run-specific.
- SEPIA `prepare_sepia` `{run}`-in-log-path latent bug (harmless once
  `--runtime-source-cache-path` is gone, but worth fixing properly).
- Swap file (32 GB, `/sylvain/mount/swapfile`) is now a permanent machine
  change — note for future heavy local phases.
