# Solve log — scen_demande_haute @ 2010, 1h (softlink-harmonisation)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-08-22 03:56 → 12:06 |
| Operator | Cursor agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml`; on NIC5 also `cluster/config_cluster.yaml` |
| Code version | pypsa-wal `softlink-harmonisation` `5371edfd`; TIMES_PyPSA `softlink-harmonisation` `5f49de5` (both checkouts; cluster TIMES_PyPSA rsynced to the editable install path) |
| Outcome | **success**: 4/4 horizons optimal; CSVs/plots; pypsa2html 75 pages; Explorer CSVs on S3 |

## 2. Goal of the run

First full 1h / 2010 production run of the `softlink-harmonisation` branch
(pypsa-wal **and** TIMES_PyPSA), after the config consolidation to
`config.walloon.yaml` + prefix `walloon`. Same TIMES vd and weather year as
the 18 Aug 1h run, which still used prefix `times-pypsa` and
`config.times-pypsa.yaml`. Full postprocess + Wallonie Explorer / S3
publication.

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_demande_haute_v01_260727_fix_nuc_2807.vd` |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` |
| Snapshots | 2010-01-01 → 2010-12-31, **8760** hourly, weight 1.0 |
| Sector time resolution | `1h` |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi barrier (`Method 2`), **12 threads** (from `config.walloon.yaml`), Slurm **16 CPU / 100 GB** on `hmem`. `BarConvTol 1e-5`, `Crossover 0`. `UNMET_SCALE=1e6`. |
| Key scenario overrides | `retrofit_nuclear_once: false`; agg caps `agg_p_nom_minmax_demande_haute.csv`; option B′ heat-profile pinning |

`config_cluster.yaml` still says 16 threads / 1 TB, but `nic5.sh solve` passes
`config.walloon.yaml` *after* it, so `solving.mem_mb: 100000` and Gurobi
`threads: 12` win. Peak RSS was 35 GB — 100 GB was enough.

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval / network build (prepare) | local (`pcbureau`) | first attempt 8 cores, killed; restart `--cores 4` + 2 atlite threads. `resources/walloon` and `results/walloon` on `/sylvain/mount` |
| LP solve | NIC5 `hmem`, node `nic5-w071` (2050 also `nic5-w071`) | 16 cpus/task, 100 GB, `SOLVE_RUNTIME=1440` min. Jobs 11054829 / 11054849 / 11054903 / 11055013 |
| Post-processing (CSVs, plots) | local | `SKIP_S3_UPLOAD=1 LOCAL_CORES=4`; 7/7 steps |
| HTML report (pypsa2html) | local | 75 pages, 0 failed, 175 s. pypsa2html `config/pypsa-wal.yaml` results_dir pointed at `results/walloon/` for this run |
| Explorer CSV extraction (ClimAct) | local | extractor on `/sylvain/mount/…/climact-extraction/…`, template `config_extraction_OET.yaml`, env `datapypsa` |

Cluster specifics: queue wait **< 2 min** (2 idle `hmem` nodes; rcrits pending jobs were `AssocGrpJobsLimit` and did not block us).

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (launch → S3 verified) | **8 h 10 min** (03:56 → 12:06) |
| Prepare (network build) | first pass ~40 min then killed (thrash); restart 04:37–05:32 (**55 min**, 100/100). Elapsed from launch ≈ 1 h 36 min |
| Push to cluster | 19 s (05:33) |
| Queue wait (cluster) | < 2 min |
| Solve 2025 | barrier 214 iter / 2552 s (42.5 min). Job 11054829 |
| Solve 2030 | barrier 243 iter / 4536 s (75.6 min). Job 11054849 |
| Solve 2040 | barrier 293 iter / 6045 s (100.8 min). Job 11054903 |
| Solve 2050 | barrier 166 iter / 3384 s (56.4 min). Job 11055013 |
| Solve chain total | **5 h 25 min** (orchestrator 05:34 → 10:59; 7/7 steps) |
| Pull results | 17 s (1.3 GB networks) |
| Post-processing + plots | **26 min** (11:04–11:31); 7/7. Four parallel `make_summary` on 15 GB swapped |
| pypsa2html report | **175 s**, 75 pages, 0 failed |
| ClimAct extraction | **~29 min** (11:36–12:05 including S3); ~10 GB swap, no OOM |
| S3 upload | included in publish; raw + explorer |

### 5.1 vs 18 Aug 1h + B′ (`times-pypsa` prefix)

| Horizon | this 1h, `walloon` / softlink-harmonisation | 18 Aug 1h + B′ |
|---|---|---|
| 2025 | 3.488e11 (42.5 min barrier) | 3.563e11 (41.5 min) |
| 2030 | 3.541e11 (75.6 min) | 3.851e11 (58.3 min) |
| 2040 | 3.077e11 (100.8 min) | 2.988e11 (65.0 min) |
| 2050 | 3.190e11 (56.4 min) | 3.067e11 (59.1 min) |

Same weather year / resolution / option B′. Objectives differ because this
branch carries the EV-charging / TIMES-mapping work. 2030 and 2040 barrier
were slower; 2025/2050 matched the previous 1h class. No “Numerical trouble”.

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size 2025 | 31.15 M rows × 14.71 M cols × 75.0 M nnz (presolved 7.41 M × 10.47 M × 40.8 M) |
| LP size 2030 | 39.80 M rows × 19.32 M cols × 95.6 M nnz (presolved 7.79 M × 14.86 M × 53.8 M) |
| LP size 2040 | 43.19 M rows × 21.33 M cols × 104.0 M nnz (presolved 7.77 M × 16.63 M × 59.9 M) |
| LP size 2050 | 43.86 M rows × 21.87 M cols × 104.7 M nnz (presolved 7.72 M × 17.04 M × 60.1 M) |
| Peak RAM per solve (python-side MEM log) | 2025: 27.3 GB · 2030: 34.8 GB · 2040: 35.2 GB · 2050: 35.2 GB |
| Peak RAM local phases | prepare atlite thrash 9.8 GB swap; make_summary 4× parallel ~12 GB + 8 GB swap; extractor ~11 GB + 10 GB swap |
| Disk footprint | resources ~936 MB · results 1.8 GB (networks 1.3 GB) on `/sylvain/mount` |

## 7. Results

| Horizon | Status | Objective |
|---|---|---|
| 2025 | optimal | 3.48844692e+11 |
| 2030 | optimal | 3.54146478e+11 |
| 2040 | optimal | 3.07697222e+11 |
| 2050 | optimal | 3.18972569e+11 |

Sanity checks (instructions.md):

- **Heat-profile fidelity:** 2025 / 2030 / 2050 match to solver tolerance. **2040**
  relaxes 0.46 TWh_th of biomass-boiler profile onto the heat-pump absorber
  (rural 0.213 + urban 0.247) — known CO₂-cap vs TIMES biomass floor, not a
  pinning bug. Total |annual gap| 0.920 TWh, all in that 2040 pair.
- **EV grid draw vs TIMES `electricity road`:** 2025 0.934 / 2030 3.393 /
  2040 11.099 / 2050 16.770 TWh, **−0.0 %** every horizon.
- **BEWAL heat-pump capacity (MW_th):** 2025 1386 → 2030 1471 → 2040 2579 →
  2050 4299 (does not fall).

Local result folders:

- Networks: `results/walloon/scen_demande_haute/networks/base_s_adm___{2025,2030,2040,2050}.nc`
- CSVs / plots: `results/walloon/scen_demande_haute/{csvs,graphs}/`
- HTML report: `results/walloon/scen_demande_haute/html/index.html` (75 pages, 0 failed); site entry `results/walloon/index.html`

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | `s3://intervectoriel/test/pypsa_raw_results/20260822_walloon_scen_demande_haute/` (4 networks present) |
| Scenario folder on S3 | `s3://intervectoriel/test/scenarios/times-pypsa__demande-haute-2010-1h__20260822/` |
| Explorer display label | `demande-haute-2010-1h (times-pypsa) - 22/08/2026` |
| Explorer CSVs | **49** in `pypsa/`, **3** in `strategy/` — verified on S3 |
| TIMES vd staged | yes — `explorer/times/scen_demande_haute_v01_260727_fix_nuc_2807.vd` |
| Verified in Explorer dropdown | S3 layout verified (49/3/1). Visual check pending — open https://explorer.test.wallonie.climact.com/ and **Clear cache** if the 22/08/2026 label does not appear (distinct from the 18 Aug folder) |

## 9. Issues encountered and fixes

Working-tree only (not committed), in order:

- **`resources/walloon` and `results/walloon`** symlinked onto
  `/sylvain/mount/pypsa-wal-data` because `/` has 17 GB free (1h results ≈ 2 GB).
- **Prepare thrashing (04:00–04:27).** `build_solar_thermal_profiles` is
  `threads: 16` and spawns that many Dask workers; with `--cores 8` that is 8
  workers on a 15 GB box plus the 6.6 GB cutout. Swap hit 9.8 GB, Dask workers
  died with `CommClosedError` / TCP timeouts. Killed the group, restarted
  prepare at `--cores 4 --set-threads build_solar_thermal_profiles=2
  build_renewable_profiles=2` (`nic5.sh prepare` defaults unchanged). 34/134
  jobs had finished; `--rerun-incomplete` resumed.
- **Cluster mem/threads override.** `nic5.sh solve` passes
  `config.walloon.yaml` last, so the intended `config_cluster.yaml` 1 TB / 16
  Gurobi threads became 100 GB / 12 threads. Peak 35 GB, so it was fine; if a
  future 1h LP grows, pass `--set-resources solve_sector_network_myopic:mem_mb=1000000`
  and keep Gurobi threads in the cluster overlay *after* the study config, or
  drop `solving.mem_mb` from `config.walloon.yaml`.
- **pypsa2html** `config/pypsa-wal.yaml` still listed `results/times-pypsa/`;
  switched `results_dir` / `output.dir` to `results/walloon/` for this run
  (edit lives in the pypsa2html checkout, not committed here).
- ClimAct extractor path is the Nextcloud zip on `/sylvain/mount`, template
  `config_extraction_OET.yaml` (no `$HOME/svn/…` checkout). `EXTRACTOR_DIR` /
  `EXTRACTOR_BASE_CONFIG` exported for `nic5.sh publish`. Strategy-metrics
  “Not Present” warnings are the usual ClimAct catalogue vs Walloon-tech gap,
  same class as previous 1h runs.

## 10. Follow-ups / pending

- Visual check in the Explorer test-site dropdown (Clear cache if needed),
  label `demande-haute-2010-1h (times-pypsa) - 22/08/2026`.
- Consider making `nic5.sh solve` apply `config_cluster.yaml` *after* the
  study config so 1h jobs actually get 16 threads / 1 TB when requested.
- Local prepare on a 15 GB box should cap atlite rules at 2 threads; not
  committed (run-specific).
- Nothing from this run was committed, per request.
