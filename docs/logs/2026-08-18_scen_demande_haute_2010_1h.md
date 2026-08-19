# Solve log — scen_demande_haute @ 2010, 1h (option B′ + nuclear alignment)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-08-18 15:11 → 20:13 (prepare + solve + pull + CSVs); publication 2026-08-19 04:37–04:52 (html + ClimAct extract + S3 + Nextcloud copy). |
| Operator | Cursor agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `times-pypsa` |
| Config file(s) | `config/config.times-pypsa.yaml`; on NIC5 also `cluster/config_cluster.yaml` |
| Code version | pypsa-wal `905a3da0` + working-tree `resolution_sector: 6h → 1h` |
| Outcome | **success**: 4/4 horizons optimal; CSVs/plots; pypsa2html 75 pages; Explorer CSVs on S3; HTML copied to Nextcloud. |

## 2. Goal of the run

1h re-solve of TIMES "demande haute" after the 6h nuclear-alignment diagnostic
([log](2026-08-18_scen_demande_haute_2010_6h.md)). Same vd, 2010 weather, option B′
heat-profile pinning, nuclear CCL/caps, battery `p_nom_min` floors, and
`UNMET_SCALE=1e6`. Question: does standard barrier (`BarConvTol 1e-5`) finish at
hourly resolution now that unmet-variable scaling is in place, or does 1h × B′
still need homogeneous / NumericFocus?

Answer: **standard barrier is enough.** No “Numerical trouble”, no homogeneous
workaround, all four horizons optimal in ~4 h 43 min of cluster wall-clock.

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_demande_haute_v01_260727_fix_nuc_2807.vd` |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` |
| Snapshots | 2010-01-01 → 2011-01-01, **8760** sector snapshots, weight 1.0 |
| Sector time resolution | **`1h`** (was 6h for the 18 Aug diagnostic) |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi 13 barrier (`Method 2`), 16 threads on NIC5, `BarConvTol 1e-5`, `Crossover 0`. **Not** BarHomogeneous. `UNMET_SCALE=1e6`. |
| Key scenario overrides | `retrofit_nuclear_once: false`; agg caps `agg_p_nom_minmax_demande_haute.csv`; option B′ TIMES heat-profile pinning; battery `p_nom_min` floors |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval / network build (prepare) | local (`pcbureau`) | 16 cores, default rerun triggers (so the 6h→1h param change rebuilds). 6 jobs: time aggregation + 4 sector networks + 2025 brownfield. |
| LP solve | NIC5 `hmem`, node `nic5-w073` for all four solves | Slurm orchestrator pid 2519397 on `nic5-login1`; `--jobs 2`; 16 cpus/task, 12–16 Gurobi threads. Jobs 11034398 / 11034494 / 11034751 / 11034810 (solves) and 11034491 / 11034749 / 11034807 (brownfield). |
| Post-processing (CSVs, plots) | local after pull | 7 jobs, ~4 min on 18 Aug; `SKIP_S3_UPLOAD=1` then |
| HTML report (pypsa2html) | local | 75 pages, 0 failed, 136 s (19 Aug 04:37–04:40) |
| Explorer CSV extraction (ClimAct) | local | unpacked zip on `/sylvain/mount/pypsa-wal-data/climact-extraction/…`, env `datapypsa` (pypsa 0.35.2), ~10 min |

Cluster specifics: queue wait **< 1 min** per horizon (one idle `hmem` node; 216 pending jobs were another user’s `AssocGrpJobsLimit` and did not block us).

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (prepare → networks pulled) | ~5 h (15:11 → 20:08) |
| Prepare (network build, 6 jobs) | **53 s** (15:11:47 → 15:12:40) |
| Push to cluster | 8 s (incremental) |
| Queue wait | < 1 min per job |
| Solve 2025 | barrier **2487 s / 41.5 min** (207 iter); Slurm job ~50 min (→ 16:05:42) |
| Solve 2030 | barrier **3498 s / 58.3 min** (183 iter); Slurm job ~81 min (→ 17:28:46) |
| Solve 2040 | barrier **3897 s / 65.0 min** (190 iter); Slurm job ~75 min (→ 18:45:51) |
| Solve 2050 | barrier **3547 s / 59.1 min** (186 iter); Slurm job ~70 min (→ 19:56:54) |
| Solve chain total (4 horizons + 3 brownfield, serial) | **4 h 43 min** (orchestrator 15:13:45 → 19:56:54) |
| Pull results | 32 s (networks 1.31 GB) |
| Post-processing + plots | **4 min** (18 Aug 20:09:49 → 20:13:43); 7/7 steps |
| pypsa2html report | **136 s**, 75 pages, 0 failed (19 Aug 04:37–04:40) |
| ClimAct extraction | **~10 min** (04:41–04:51); ~6 GB swap, no OOM |
| S3 upload | **43 s** (04:51–04:52) |

### 5.1 1h vs 6h vs the stalled 1h attempt

| Attempt | Resolution | Barrier | Outcome |
|---|---|---|---|
| 14 Aug 2026 | 1h, **no** option B′ | standard, `BarConvTol 1e-5` | 4/4 optimal, 38–59 min barrier, ~4.5 h chain |
| 16–18 Aug (interrupted) | 1h, **with** B′ + nuclear caps | standard, **before** `UNMET_SCALE=1e6` | “Numerical trouble” (2025, twice around iter 240) |
| same, workaround | 1h + B′ | homogeneous, `BarConvTol 1e-2` | 2025/2030 at 1 % gap; 2040 still gap 1.52 after ~2 h (killed) |
| 18 Aug morning | **6h**, with B′ + nuclear caps + `UNMET_SCALE` | standard, `BarConvTol 1e-5` | 4/4 optimal, **~4 min barrier / horizon**, 31 min chain |
| **this run** | **1h**, with B′ + nuclear caps + `UNMET_SCALE` | standard, `BarConvTol 1e-5` | 4/4 optimal, **42–65 min barrier / horizon**, 4 h 43 min chain |

So the 16–18 Aug 1h hostility was the **unscaled unmet variables** (spreading
coefficients ~1e-6), not option B′ × hourly snapshots as such, and not the
nuclear caps. With `UNMET_SCALE=1e6` the 1h LPs behave like the 14 Aug 1h run
(same size class, same ~1 h/horizon). Homogeneous barrier / NumericFocus / loose
`BarConvTol` are not needed.

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size 2025 | 31.29 M rows × 14.78 M cols × 75.3 M nnz (presolved 7.41 M × 10.54 M × 41.0 M) |
| LP size 2030 | 39.94 M rows × 19.39 M cols × 95.9 M nnz (presolved 7.79 M × 14.93 M × 54.0 M) |
| LP size 2040 | 43.33 M rows × 21.40 M cols × 104.2 M nnz (presolved 7.77 M × 16.70 M × 60.0 M) |
| LP size 2050 | 44.00 M rows × 21.94 M cols × 105.0 M nnz (presolved 7.72 M × 17.11 M × 60.2 M) |
| Peak RAM per solve (python-side MEM log) | 2025: 27.9 GB · 2030: 33.8 GB · 2040: 36.0 GB · 2050: 34.7 GB |
| Peak RAM local phases | prepare: modest (16 cores, ~1 min) |
| Disk footprint | networks 1.31 GB under `results/times-pypsa/scen_demande_haute/networks/` |

Gurobi warned about large RHS/bounds (same class as 6h and 14 Aug 1h) but
standard barrier had **no** “Numerical trouble”.

## 7. Results

| Horizon | Status | Objective |
|---|---|---|
| 2025 | optimal | 3.56342980e+11 |
| 2030 | optimal | 3.85104761e+11 |
| 2040 | optimal | 2.98771070e+11 |
| 2050 | optimal | 3.06724072e+11 |

Objectives vs the 6h diagnostic (same physics, coarser time) and vs 14 Aug 1h
(no option B′):

| Horizon | this 1h + B′ | 18 Aug 6h + B′ | 14 Aug 1h, no B′ |
|---|---|---|---|
| 2025 | 3.563e11 | 3.526e11 | 3.945e11 |
| 2030 | 3.851e11 | 3.793e11 | 3.952e11 |
| 2040 | 2.988e11 | 2.937e11 | 3.223e11 |
| 2050 | 3.067e11 | 3.041e11 | 3.375e11 |

1h with B′ sits close to 6h with B′ (1h slightly higher — less temporal
aggregation). Both are well below the 14 Aug 1h-without-B′ objectives.

Nuclear siting (`p_nom_opt × efficiency`, MW_e). **Do not read `p_nom` on
extendable plant** after barrier with `crossover: 0`.

| Horizon | BEWAL | BEVLG | Notes |
|---|---|---|---|
| 2025 | 1 992 MW | 1 890 MW | legacy fleet (TH1 962 + TH3 1 030; Doel 890 + Doel 4 1 000) |
| 2030 | 1 030 MW (TH3) | 1 000 MW (Doel 4) | |
| 2040 | 1 030 MW retrofit, no new | 1 000 MW retrofit, no new | matches 1.03 / 1.00 GW LTO caps |
| 2050 | **3 000 MW** (1 030 retrofit + 1 970 new) | **~0** (placeholder) | all new nuclear in Wallonia |

That matches `docs/nuclear-alignment-20260816.md` and the 6h diagnostic.

Local result folders:

- Networks: `results/times-pypsa/scen_demande_haute/networks/base_s_adm___{2025,2030,2040,2050}.nc`
- Solver logs: `results/times-pypsa/scen_demande_haute/logs/`
- Heating profiles: `results/times-pypsa/scen_demande_haute/heating_profiles/`
- CSVs / plots: `results/times-pypsa/scen_demande_haute/{csvs,graphs}/` (rebuilt 20:13)
- HTML report: `results/times-pypsa/scen_demande_haute/html/index.html` (75 pages, 0 failed); site entry `results/times-pypsa/index.html`
- Nextcloud copy: `/sylvain/Nextcloud/pypsa-wal/20260818_scen_demande_haute_2010-1h/` (Nextcloud client running)

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | `s3://intervectoriel/test/pypsa_raw_results/20260818_times-pypsa_scen_demande_haute/` (1206 files, html included) |
| Scenario folder on S3 | `s3://intervectoriel/test/scenarios/times-pypsa__demande-haute-2010-1h__20260818/` |
| Explorer display label | `demande-haute-2010-1h (times-pypsa) - 18/08/2026` |
| Explorer CSVs | 49 in `pypsa/`, 3 in `strategy/` — verified on S3 |
| TIMES vd staged | yes — `explorer/times/scen_demande_haute_v01_260727_fix_nuc_2807.vd` |
| Verified in Explorer dropdown | S3 layout verified (49/3/1); visual check pending — open https://explorer.test.wallonie.climact.com/ and **Clear cache** if the 18/08/2026 label does not appear (distinct from the 14 Aug folder) |

## 9. Issues encountered and fixes

- **None during this chain.** Prepare, push, queue, four solves, pull all
  succeeded on the first attempt.
- **`UNMET_SCALE=1e6` already in `times_heat_profiles.py`** was the 17 Aug fix
  for 1h “Numerical trouble”. This run is the confirmation that it was
  sufficient; no NumericFocus / BarHomogeneous / loose `BarConvTol` required.
- **Prepare used default rerun triggers**, not `nic5.sh prepare` (`--rerun-triggers
  mtime`). The 6h→1h change is a config *param*; mtime-only would have skipped
  time aggregation.
- **Leftover 6h solved networks on the cluster** were deleted before `solve` so
  Snakemake could not treat the same output path as done.
- **ClimAct extractor** is the Nextcloud zip unpacked at
  `/sylvain/mount/pypsa-wal-data/climact-extraction/climact-pypsa-eur_results_extraction-88d352b59aa4`
  (no `$HOME/svn/…` checkout). Template is `config_extraction_OET.yaml`;
  `EXTRACTOR_BASE_CONFIG` was set accordingly. `EXTRACTION_CONFIG` patch and
  `download_networks`/`upload_results: False` already present from 16 Aug.
- **Extractor used ~6 GB swap** on the 15 GB machine; finished without OOM.

## 10. Follow-ups / pending

- Visual check in the Explorer test-site dropdown (Clear cache if needed),
  label `demande-haute-2010-1h (times-pypsa) - 18/08/2026`.
- Heat-profile fidelity (`check_heat_profile_fidelity.py scen_demande_haute live`):
  2025 / 2030 / 2050 match to solver tolerance (peak gap < 0.001 MW). **2040**
  relaxes 0.46 TWh_th of biomass-boiler profile onto the heat-pump absorber
  (rural 0.214 + urban 0.248) — the known CO₂-cap vs TIMES biomass floor, not a
  pinning bug. Total |annual gap| 0.925 TWh, all in that 2040 pair.
- Config is now `resolution_sector: 1h` in `config.times-pypsa.yaml`.
- Commit the 1h config switch when ready (everything else was already in
  `905a3da0`).
