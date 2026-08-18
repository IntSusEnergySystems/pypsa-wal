# Solve log — scen_demande_haute @ 2010, 6h (nuclear-alignment diagnostic)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-08-18 12:10 → 12:44 (prepare + solve + pull). Postprocess and Explorer publication **not** run. |
| Operator | Cursor agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `times-pypsa` |
| Config file(s) | `config/config.times-pypsa.yaml`; on NIC5 also `cluster/config_cluster.yaml` |
| Code version | pypsa-wal master `04fe13a5` + working-tree nuclear/CCL/heat-profile edits listed in §9 (not yet committed at solve time) |
| Outcome | **partial success**: 4/4 horizons optimal; nuclear trajectory verified; no postprocess, no S3, no Explorer CSVs |

## 2. Goal of the run

Diagnostic re-solve of the TIMES "demande haute" scenario at **6h** after a 1h
attempt stalled. Question: are the tight TIMES nuclear caps feasible, or is the
1h slowdown / "infeasible" scare caused by those caps?

Same vd and 2010 weather as
[`2026-08-14_scen_demande_haute_2010_1h.md`](2026-08-14_scen_demande_haute_2010_1h.md),
plus option B′ (TIMES heat-profile pinning, merged after that 1h run) and the
nuclear CCL/cap fixes. Standard barrier (`BarConvTol 1e-5`), no homogeneous
workaround.

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_demande_haute_v01_260727_fix_nuc_2807.vd` |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` |
| Snapshots | 2010-01-01 → 2011-01-01, **1460** sector snapshots, weight 6.0 |
| Sector time resolution | **`6h`** (config was 1h for the 14 Aug study; switched back for this diagnostic) |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi 13.0.2 barrier (`Method 2`), 12 threads, `BarConvTol 1e-5`, `Crossover 0`. **Not** BarHomogeneous. |
| Key scenario overrides | `retrofit_nuclear_once: false`; agg caps `agg_p_nom_minmax_demande_haute.csv` (TIMES nuclear trajectory); option B′ TIMES heat-profile pinning on BEWAL rural / urban decentral heat |

Nuclear caps in force (MW_e, total, `include_existing`; 2025/2030 empty = legacy fleet):

| Year | BEWAL [min, max] | BE [min, max] (= BEWAL + rest-of-BE) |
|---|---|---|
| 2035 / 2040 | 1000, 1030 | 2000, 2030 |
| 2045 | 1750, 1750 | 1750, 1750 |
| 2050 | 3000, 3000 | 3000, 3000 |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval / network build (prepare) | local (`pcbureau`) | 16 cores, `--rerun-incomplete`; time aggregation + sector networks only (12 jobs). Cutout already cached. |
| LP solve | NIC5 `hmem` | Slurm orchestrator on `nic5-login1`; `--jobs 2`; `solve_sector_network_myopic` 16 cpus/task, 12 Gurobi threads. Jobs 11031984 / 11031990 / 11031993 / 11032146. |
| Post-processing (CSVs, plots) | skipped | |
| HTML report (pypsa2html) | skipped | |
| Explorer CSV extraction (ClimAct) | skipped | |

Cluster specifics: queue wait **< 1 min** per horizon. A leftover **1h** solve
(job 11031180, 2040, homogeneous barrier, gap 1.52 after ~2 h) was killed before
this run so `hmem` was free.

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (prepare → networks pulled) | ~34 min (12:10 → 12:44) |
| Prepare (network build, 12 jobs) | **65 s** (12:10:52 → 12:11:57) |
| Push to cluster | ~1 min |
| Queue wait | < 1 min per job |
| Solve 2025 | barrier **189 s** (105 iter); Slurm job ~7 min (submitted → 12:19:43) |
| Solve 2030 | barrier **242 s** (101 iter); Slurm job ~6.5 min (→ 12:27:44) |
| Solve 2040 | barrier **237 s** (94 iter); Slurm job ~6.5 min (→ 12:35:45) |
| Solve 2050 | barrier **229 s** (92 iter); Slurm job ~6.5 min (→ 12:43:46) |
| Solve chain total (4 horizons + 3 brownfield, serial) | **31 min** (orchestrator 12:12:42 → 12:43:46) |
| Pull results | ~1 min (networks 237 MB) |
| Post-processing + plots | n/a |
| pypsa2html report | n/a |
| ClimAct extraction | n/a |

## 5.1 Why 6h, not 1h (runtime)

The 14 Aug 1h run
([log](2026-08-14_scen_demande_haute_2010_1h.md)) finished in **~45–70 min
barrier per horizon** with **standard** barrier. That code (`9e28e524`) did
**not** include option B′.

Option B′ pins TIMES heat profiles with one equality per (group × bus ×
snapshot): roughly **17k extra rows at 6h** vs **~105k at 1h**. After it was
merged, 1h became hostile:

| Attempt | Resolution | Barrier | Outcome |
|---|---|---|---|
| 14 Aug 2026 | 1h, **no** option B′ | standard, `BarConvTol 1e-5` | 4/4 optimal, 38–59 min barrier, ~4.5 h chain |
| 16–18 Aug (interrupted) | 1h, **with** option B′ + nuclear caps | standard | “Numerical trouble” (2025, twice around iter 240) |
| same, workaround | 1h + B′ | homogeneous, `BarConvTol 1e-2` | 2025/2030 finished at 1 % gap (2030 obj `3.81e11` — the “infeasible / IIS” report was a **false alarm**); 2040 still gap 1.52 after ~2 h (killed). Homogeneous tail on 2030 was ~0.08 gap-decades/hour → tens of hours to 1e-5. |
| **this run** | **6h**, with B′ + nuclear caps | standard, `BarConvTol 1e-5` | 4/4 optimal, **~4 min barrier / horizon**, 31 min chain |

So the 1h slowness is **option B′ × hourly snapshots**, not the nuclear caps.
The same caps + option B′ + standard barrier are easy at 6h. A later 1h retry
should keep the nuclear/CCL fixes and treat hourly option B′ as the solver
problem (homogeneous / NumericFocus / constraint scaling), not loosen the caps.

LP size at 6h is ~6× smaller than the 14 Aug 1h LPs (those were 31–44 M rows
before presolve). Peak RAM here is ~7 GB vs ~37 GB at 1h.

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size 2025 | 5.22 M rows × 2.46 M cols × 12.6 M nnz (presolved 1.24 M × 1.77 M × 6.86 M) |
| LP size 2030 | 6.66 M rows × 3.23 M cols × 16.0 M nnz (presolved 1.31 M × 2.51 M × 9.03 M) |
| LP size 2040 | 7.22 M rows × 3.57 M cols × 17.4 M nnz (presolved 1.30 M × 2.81 M × 10.0 M) |
| LP size 2050 | 7.33 M rows × 3.66 M cols × 17.5 M nnz (presolved 1.29 M × 2.87 M × 10.1 M) |
| Peak RAM per solve (python-side MEM log) | 2025: 6.4 GB · 2030: 7.1 GB · 2040: 7.4 GB · 2050: 7.5 GB |
| Peak RAM local phases | prepare: modest (16 cores, ~1 min) |
| Disk footprint | networks 237 MB under `results/times-pypsa/scen_demande_haute/networks/` |

Gurobi warned about large RHS/bounds (same class of warning as at 1h) but
standard barrier had **no** “Numerical trouble” at 6h.

## 7. Results

| Horizon | Status | Objective |
|---|---|---|
| 2025 | optimal | 3.52563974e+11 |
| 2030 | optimal | 3.79251859e+11 |
| 2040 | optimal | 2.93696845e+11 |
| 2050 | optimal | 3.04128324e+11 |

Nuclear siting (`p_nom_opt × efficiency`, MW_e). **Do not read `p_nom` on
extendable plant** after barrier with `crossover: 0` — it stays at the pre-solve
placeholder, so 2040/2050 look like zero nuclear if you only inspect `p_nom`.

| Horizon | BEWAL | BEVLG | Notes |
|---|---|---|---|
| 2025 | 1 992 MW | 1 890 MW | legacy fleet (no CCL) |
| 2030 | 1 030 MW (TH3) | 1 000 MW (Doel 4) | |
| 2040 | 1 030 MW retrofit, no new | 1 000 MW retrofit, no new | matches 1.03 / 1.00 GW LTO caps |
| 2050 | **3 000 MW** (1 030 retrofit + 1 970 new) | **~0** (placeholder) | all new nuclear in Wallonia |

That matches `docs/nuclear-alignment-20260816.md`.

Local result folders:

- Networks: `results/times-pypsa/scen_demande_haute/networks/base_s_adm___{2025,2030,2040,2050}.nc`
- Solver logs: `results/times-pypsa/scen_demande_haute/logs/`
- CSVs / plots / HTML: **not produced**

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | not uploaded |
| Scenario folder on S3 | n/a |
| Explorer display label | n/a |
| Explorer CSVs | n/a |
| TIMES vd staged | n/a |
| Verified in Explorer dropdown | n/a |

This was a feasibility / nuclear-alignment diagnostic, not a publication run.

## 9. Issues encountered and fixes

- **Leftover 1h job 11031180** (2040, homogeneous barrier) still running when
  this session started. Killed (`scancel` + orchestrator) before the 6h
  diagnostic. `nic5.sh stop` can leave the login-node orchestrator alive — kill
  the pid in `cluster/logs/orchestrate.pid` as well.
- **False “2030 infeasible / IIS”** on the interrupted 1h chain: 2030 at 1h had
  actually finished (`Optimal objective 3.81e11`) with BarHomogeneous and
  `BarConvTol=0.01`. Status `other` / IIS hunting was a misread of a slow but
  converging solve.
- **CCL max on links** (`scripts/solve_network.py`): maxima were wrongly applied
  with the min RHS. Fixed to use `max` minus existing, and clip so a cap cannot
  bind below `p_nom_min`. Without this the tight 2040/2050 nuclear caps are
  ill-posed.
- **Refuse to export non-optimal networks** (same file): prevents a poisoned
  myopic chain after termination `other`.
- **`UNMET_SCALE = 1e6`** in `scripts/walloon_scripts/times_heat_profiles.py`
  (TWh unmet vars). Mathematically equivalent rescale; tests updated.
- **1h solver workarounds reverted** for this run: `BarHomogeneous`,
  `BarConvTol: 1e-2`, `gurobi-numeric-focus`, `mem_mb: 800000`. Not needed at
  6h; they were masking option B′ at 1h, not a nuclear issue.
- **`p_nom` vs `p_nom_opt`**: after `crossover: 0`, extendable nuclear `p_nom`
  stays at the placeholder. Verification must use `p_nom_opt`.

## 10. Follow-ups / pending

- Postprocess / pypsa2html / S3 / Explorer for this 6h network if it should be
  published (not done).
- 1h retry: keep nuclear + CCL fixes; change the option B′ / hourly solver
  strategy rather than the caps. Expect standard barrier trouble unless that is
  addressed.
- Nuclear numbers now also live in `config/input_parameters_for_models.csv`
  (`agg:BEWAL:nuclear-all:*` / `agg:BE:nuclear-all:*`) and are pushed by
  `scripts/build_common_parameters.py --write` (wired after this solve; the run
  itself used the agg CSV directly).
- Commit the working-tree nuclear/CCL/heat-profile edits when ready.
- Config is still `resolution_sector: 6h` in `config.times-pypsa.yaml` after
  this diagnostic — switch back to 1h explicitly before any hourly retry.
