# Solve log — scen_demande_haute @ 2010, 1h (run-review fixes)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-08-26 16:58 → 2026-08-27 02:53 |
| Operator | Cursor agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml`; on NIC5 also `cluster/config_cluster.yaml` (overlay last, **one** `--configfile` flag) |
| Code version | pypsa-wal `fix/run-review-20260825` `759e5e50` + uncommitted working-tree: `cluster/nic5.sh` (configfile merge), `scripts/solve_network.py` (CCL min clip), `test/test_myopic_potentials.py`. TIMES_PyPSA `main` `a48b774` |
| Outcome | **success**: 4/4 horizons optimal; CSVs/plots; pypsa2html 83 pages; Explorer 49/3/1 on S3. First 2050 attempt infeasible (CCL min vs land-use); rerun optimal after min-clip. Critical review **§11**. |

## 2. Goal of the run

Full 1h / 2010 re-solve of `scen_demande_haute` on the branch that addresses
the 25 Aug review findings
([`2026-08-25_scen_demande_haute_2010_1h.md`](2026-08-25_scen_demande_haute_2010_1h.md)
§11): myopic generator-max CCL, Nemo NTC, aviation out of national CO₂,
transmission `vopt` + NTC ceilings, Walloon gas floor moved to `CCGT-all`,
cluster pull/overlay/extract faults. Same TIMES vd, weather year, resolution
and option B′ as that run. Question: do the 9 FAILs and the pathological 2050
Walloon carbon price go away, and does the chain stay feasible.

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_demande_haute_v01_260727_fix_nuc_2807.vd` |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` |
| Snapshots | 2010-01-01 → 2011-01-01, **8760** hourly, weight 1.0 |
| Sector time resolution | `1h` |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi barrier (`Method 2`), **16** threads / **1 TB** from `cluster/config_cluster.yaml` (overlay last, one argparse flag). `BarConvTol 1e-5`, `Crossover 0`. `UNMET_SCALE=1e6`. |
| Key scenario overrides | `retrofit_nuclear_once: false`; agg caps `agg_p_nom_minmax_demande_haute.csv`; option B′ heat-profile pinning; `conventional.inflexible_nuclear.enable: true`; `electricity.transmission_limit: vopt`; aviation excluded from national CO₂; `agg:BEWAL:CCGT-all:min` gas floor |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval / network build (prepare) | local (`pcbureau`) | `LOCAL_CORES=4`; TMPDIR `/sylvain/mount/pypsa-wal-data/tmp`. Previous 25 Aug resources wiped — physics/NTC/CO₂/CCL/vopt changed. |
| LP solve | NIC5 `hmem` | partition `hmem`, 16 cpus/task, 1 TB, `SOLVE_RUNTIME=1440` min. Jobs 11076140 / 11076179+11076318 / 11076239+11076787 / 11076308 (infeas) then 11076860. |
| Post-processing (CSVs, plots) | local | 8/8 at 02:33, `LOCAL_CORES=2 SKIP_S3_UPLOAD=1` |
| HTML report (pypsa2html) | local | 83 pages, 0 failed, 133 s. Config: `/sylvain/git/pypsa2html/config/pypsa-wal.yaml` |
| Explorer CSV extraction (ClimAct) | local | env `datapypsa`, extractor `/sylvain/mount/pypsa-wal-data/climact-extraction/climact-pypsa-eur_results_extraction-88d352b59aa4`, template `config_extraction_OET.yaml`. Swap on (`/dev/sdb2` 100 GB). ~4 min. |

Previous `results/walloon/scen_demande_haute` archived to
`/sylvain/mount/pypsa-wal-data/archive/walloon-20260825`.
`results/walloon` remains a symlink onto the mount (`nic5.sh pull -K`).

Pre-flight: 50 then 11 unit tests (myopic potentials, NTC, national CO₂,
transmission carry-forward, EV charging, CCL min-clip) passed.
`build_common_parameters.py --check` PASSED (conda env).

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (launch → S3 verified) | **~10 h** (16:58 → 02:53). Includes 2050 infeasible + CCL-min fix + 2030/2040 identical rebuilds. |
| Prepare (network build) | **42 min** (16:58–17:40), 134/134, 4 cores |
| Push to cluster | **34 s** (17:40:57–17:41:31) |
| Queue wait (cluster) | short after each DAG (hmem idle) |
| Solve 2025 | barrier 185 iter / 2436 s (40.6 min). Job 11076140. **optimal 3.68241121e+11** |
| Solve 2030 | barrier 186 iter / 3292 s (54.9 min). Jobs 11076179 / 11076318 identical. **optimal 3.82695583e+11** |
| Solve 2040 | barrier 255 iter / 5177 s (86.3 min). Jobs 11076239 / 11076787 identical. **optimal 3.29663985e+11** |
| Solve 2050 | first attempt **infeasible** (11076308, ~5 min). Rerun barrier 234 iter / 5864 s (97.7 min), job 11076860. **optimal 3.38430834e+11** |
| Solve chain last finish | **02:10** 27 Aug |
| Pull results | **02:30**; `results/walloon` stayed a symlink onto `/sylvain/mount` |
| Post-processing + plots | **~3 min** (02:30:33–02:33:48), 8/8 |
| pypsa2html report | **133 s**, 83 pages, 0 failed (02:36–02:39) |
| ClimAct extraction | **~4 min** (02:40:37–02:44:53), 49/3/1 staged |
| S3 upload | **35 s** (02:53:27), after unsetting a leaked `SKIP_S3_UPLOAD=1` |

### 5.1 vs 25 Aug 1h (`master` `d0e2ba28`)

Same weather year, cutout, snapshots, `1h`, TIMES vd, option B′. This tree
adds CCL generator-max `include_existing`, aviation out of national CO₂,
`vopt` + NTC ceilings, Nemo 1000 MW, BEL includes Wallonia, TYNDP NTC,
`CCGT-all` gas floor, cluster pull `-K`.

| Horizon | this 1h, `fix/run-review-20260825` | 25 Aug 1h, `master` |
|---|---|---|
| 2025 | **3.682e11** (40.6 min, 16 threads) | 3.833e11 (38.4 min, 12 threads) |
| 2030 | **3.827e11** (54.9 min) | 3.891e11 (70.3 min) |
| 2040 | **3.297e11** (86.3 min) | 3.207e11 (99.5 min) |
| 2050 | **3.384e11** (97.7 min; after infeas rerun) | 3.177e11 (69.3 min) |

2025–2030 slightly cheaper (−4 / −2 %). 2040/2050 higher (+3 / +7 %).
Capping Walloon onwind at 6.5 GW (was 12.4 GW in 2050) raises late-horizon
cost; aviation leaving the national cap works the other way on the dual.
16 threads vs 12; peak RAM 32–38 GB vs 28–37 GB.

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size 2025 | 31.08 M rows × 14.66 M cols × 75.0 M nnz (presolved 7.50 M × 10.39 M × 40.8 M) |
| LP size 2030 | 39.59 M rows × 19.19 M cols × 95.1 M nnz (presolved 7.89 M × 14.70 M × 53.4 M) |
| LP size 2040 | 42.84 M rows × 21.14 M cols × 103.0 M nnz (presolved 7.92 M × 16.38 M × 59.2 M) |
| LP size 2050 | 43.79 M rows × 21.82 M cols × 104.7 M nnz (presolved 7.89 M × 16.93 M × 60.2 M) |
| Peak RAM per solve (python-side MEM log) | 2025: **32.2 GB** · 2030: **36.7 GB** · 2040: **37.7 GB** · 2050: **38.1 GB** |
| Peak RAM local phases | prepare: 4 cores. Extract: swap on, ~4 min, no freeze. Review `--full` after extract, not paired. |
| Disk footprint | resources ~936 MB · results 1.8 GB (networks 1.3 GB) on `/sylvain/mount` |

Gurobi used **16 threads** (solver log: `using up to 16 threads`). Overlay
actually won this time.

## 7. Results

| Horizon | Status | Objective (EUR/a) |
|---|---|---|
| 2025 | **optimal** | 3.68241121e+11 |
| 2030 | **optimal** | 3.82695583e+11 |
| 2040 | **optimal** | 3.29663985e+11 |
| 2050 | **optimal** | 3.38430834e+11 |

Sanity checks (`instructions.md` / checklist level 2), recomputed live:

- **Heat-profile fidelity:** 2025 / 2030 / 2050 match to solver tolerance.
  **2040** relaxes **0.46 TWh_th** of biomass-boiler profile onto the heat-pump
  absorber (rural 0.213 + urban 0.247) — known CO₂-cap vs TIMES biomass floor
  ([`heat-softlink.md`](../heat-softlink.md) §4.2). Total |annual gap|
  **0.920 TWh**, all in that 2040 pair. Same as 25 Aug.
- **EV grid draw vs TIMES `electricity road`:** 2025 0.934 / 2030 3.393 /
  2040 11.099 / 2050 16.770 TWh, **−0.0 %** every horizon.
- **BEWAL heat-pump capacity (MW_th):** 2025 **1366** → 2030 **1452** →
  2040 **2525** → 2050 **3238** (does not fall). Delivered decentral heat
  **2.20 → 3.06 → 6.07 → 7.89 TWh_th**.

Local result folders:

- Networks: `results/walloon/scen_demande_haute/networks/`
- CSVs / plots: `results/walloon/scen_demande_haute/{csvs,graphs,graphics,maps}/`
- HTML report: `results/walloon/scen_demande_haute/html/index.html` (91 html files)

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | `s3://intervectoriel/test/pypsa_raw_results/20260827_walloon_scen_demande_haute/` (4 networks present) |
| Scenario folder on S3 | `s3://intervectoriel/test/scenarios/times-pypsa__demande-haute-2010-1h__20260827/` |
| Explorer display label | `demande-haute-2010-1h (times-pypsa) - 27/08/2026` |
| Explorer CSVs | **49** in `pypsa/`, **3** in `strategy/` — verified on S3 |
| TIMES vd staged | yes — 1 file in `times/` |
| Verified in Explorer dropdown | S3 layout verified (49/3/1). **Visual check pending** — open https://explorer.test.wallonie.climact.com/ and **Clear cache** if the 27/08/2026 label does not appear |

`run.json`: `git_commit` `759e5e50b5ec67981480cf4e5e23f875ca50678a`, branch
`fix/run-review-20260825`, `uploaded_at` 2026-08-27T02:53:55+02:00.
That SHA does **not** include the two working-tree fixes (configfile merge,
CCL min clip); the cluster 2050 solve used the clipped `solve_network.py`.

## 9. Issues encountered and fixes

- Launched on `fix/run-review-20260825` (`759e5e50`), not `master`. The
  25 Aug run was `d0e2ba28`. This branch is the review-fix set (CCL, NTC,
  aviation/CO₂, vopt, CCGT-all floor, cluster pull `-K`, overlay order).
- System-python `build_common_parameters.py --check` crashed on pandas
  `lineterminator` (older pandas). Re-ran in `pypsa-eur` conda; CHECK PASSED.
- Dask `CommClosedError` heartbeat during `build_solar_thermal_profiles`
  (17:08). The rule finished and the DAG continued — shutdown noise, not a
  failed job. Same class as previous 1h prepares.
- **First `nic5.sh solve` failed immediately** (17:44, orchestrator pid
  1978160). `MissingRuleException: No rule to produce
  results/walloon/scen_demande_haute/networks/base_s_adm___2050.nc`. Cause:
  two separate `--configfile` flags; argparse `nargs="+"` keeps only the last
  flag, so Snakemake loaded `cluster/config_cluster.yaml` alone (the
  "overlay last" commit). Symptom in the log: `Config file(s)` listed the
  overlay + defaults, never `config.walloon.yaml`. Fix: one flag,
  `--configfile config/config.walloon.yaml cluster/config_cluster.yaml`, so
  both merge and the overlay still wins on `solving.mem_mb` / threads.
  Resubmitted after rsync of `cluster/nic5.sh`. **Still uncommitted.**
- **2050 infeasible** (job 11076308, 21:20–21:25). Gurobi presolve:
  `Model is infeasible or unbounded`; IIS is 4 rows — NL `offwind-all`
  `agg_p_nom_min ≥ 1713 MW` vs remaining land-use `p_nom_max` of 21.7 + 0 +
  1141 = **1163 MW**. Cause: `include_existing` subtracts standing capacity
  from the TYNDP min but did not clip the residual to leftover potential.
  Heat-profile budget was a warning only (1.432 Mt / 1.667 Mt = 86 %). Fix:
  clip generator/link `agg_p_nom_min` residual to remaining `p_nom_max`
  (`scripts/solve_network.py`); regression
  `test_ccl_generator_min_never_exceeds_remaining_p_nom_max`. **Still
  uncommitted.** 2025–2040 networks `touch`ed on the cluster so the script
  mtime does not re-solve them for the clip itself. Snakemake then rebuilt
  2030/2040 anyway (mtime chain) — **identical objectives**. 2050
  resubmitted and solved.
- **Snakemake lock.** After stopping a mistaken 2030 rebuild, leftover orch
  pid `2744721` held `.snakemake/locks`. `kill -9` + `rm` locks, resubmitted
  2050 (job 11076860).
- **`SKIP_S3_UPLOAD=1` leaked** from postprocess into the same shell; first
  `nic5.sh upload` no-op’d. Unset and re-uploaded successfully at 02:53.

## 10. Follow-ups / pending

Critical review: **§11**. Visual Explorer dropdown check still pending (§8).

Operational:

1. Commit the two working-tree fixes (`nic5.sh` one `--configfile` flag;
   `solve_network.py` CCL min clip + test) so the next run’s `run.json`
   SHA actually contains them.
2. Visual check of Explorer dropdown for `demande-haute-2010-1h (times-pypsa)
   - 27/08/2026`.
3. Keep swap on for extract / `--full` review. Do not pair those two.
4. Next run’s level 0b previous SHAs are pypsa-wal `759e5e50` (plus the
   working-tree edits listed in §9) and TIMES_PyPSA `a48b774`.

## 11. Critical review

**Checked:** 2026-08-27, against [`docs/run-review-checklist.md`](../run-review-checklist.md)
(all eight levels) and `instructions.md`.
**Networks:** `results/walloon/scen_demande_haute/networks/base_s_adm___*.nc`
**Scripted half:** `PYTHONPATH=. python scripts/walloon_scripts/review_run.py … --full`
→ **161 PASS · 20 WARN · 3 FAIL** (exit 1). Raw output:
`cluster/logs/review_run_full.txt`.

**Verdict:** the review-fix branch did what it was launched to do. The nine
generator-max FAILs of 25 Aug are gone except a **201 MW 2025 solar-all**
overshoot. Walloon onshore wind sits on **6 500 MW** every horizon. Nemo is
**1 000 MW** before Nautilus. 2050 effective Walloon carbon price fell
**2 740 → 1 272 EUR/t** after aviation left the national cap — still not a
price forecast. 2050 first solve was infeasible (CCL min vs remaining
`p_nom_max`); the uncommitted clip made it feasible. Do **not** publish the
2050 dual, zero-capital-cost water pits (25.8 GW), or 2025 capacities as
“today”.

| Level | Verdict |
|---|---|
| 0 provenance | **pass** (`759e5e50` + working-tree clip/configfile; configs identical except horizon) |
| 0b commit intent | **pass** (table in §11.1b; CCL max, Nemo, aviation scope, vopt/NTC, CCGT-all floor all visible) |
| 1 solve | **pass with caveats** (Crossover 0; large bounds/rhs; 2050 needed a second job) |
| 2 TIMES soft link | **pass with caveats** (coal +8/+13 % in 2025/2030, known; 2040/2050 electric-load −0.8/−0.9 %) |
| 3 accounting identities | **pass with caveats** (buses close; 2050 `tes_se` Sankey FAIL; other Sankey WARNs are known mapping holes) |
| 4 constraint compliance | **pass with caveats** (onwind/nuclear/Nemo/CCGT-all OK; 2025 solar-all +201 MW; 2050 BE-FR usable 67 % of grown cap) |
| 5 realism | **pass with caveats** (2025 is an optimisation; solar-hsat +794 MW/yr 2025→2030; PV all utility-scale; no Walloon DAC; water pits degenerate) |
| 6 prices / costs | **pass with caveats** (biogas mostly off until 2050; 2050 BEWAL CO₂ dual still not a price) |
| 7 TIMES consistency | **pass** (nuclear trajectory; heat mix pinned except the known 2040 biomass/HP swap; 2050 CCGT CC 463 MW_e inside the 1 740 floor) |
| 8 robustness | **pass with caveats** (onwind now stable at 6.5 GW; H2 pipe / batteries / water pits still wander) |

### 11.1 Provenance (level 0)

`run.json` commit `759e5e50` is the branch HEAD. Effective configs
`results/walloon/scen_demande_haute/configs/config.base_s_adm___<year>.yaml`
are identical across horizons except `planning_horizons`. Weather year and
cutout agree (`2010-01-01` → `2011-01-01`, `europe-2010-sarah3-era5`).
`resolution_sector: 1h`. `sector.times_file` is the intended vd; scenario
overlay points at `agg_p_nom_minmax_demande_haute.csv`.
`heat_stock_age_profile`, `transmission_limit: vopt`,
`conventional.inflexible_nuclear.enable`, `sector.ccgt_cc: true` are in the
**effective** config. Solver log confirms **16 threads**.

Same-vintage comparison is **only** vs
[`2026-08-25_scen_demande_haute_2010_1h.md`](2026-08-25_scen_demande_haute_2010_1h.md)
(2010, 1h, B′, same vd, prefix `walloon`). 22 Aug is one vintage further back.

### 11.1b Commit intent (level 0b)

Previous production run: [`2026-08-25_scen_demande_haute_2010_1h.md`](2026-08-25_scen_demande_haute_2010_1h.md)
at pypsa-wal `d0e2ba28`, TIMES_PyPSA `a48b774`. This tree is `759e5e50` /
`a48b774` plus the two uncommitted fixes in §9.

**pypsa-wal `d0e2ba28..759e5e50`**

| Commit | Class | Intended behaviour | Observable on this tree | |
|---|---|---|---|---|
| `8d1d6e10` generator-max CCL `include_existing` | physics | Generator `max` caps **total** capacity, not the extendable tranche. | BEWAL onwind **6 500 / 6 500 / 6 500 / 6 500** vs `p_nom_max` 6 500 (was 6.9→12.4 GW). BE offwind-all 2.3 / 8.0 / 8.0 / 8.0 GW on the file max. 9 FAILs → 2 (2025 solar-all only). | **pass** |
| `644cefd9` aviation out of national CO₂ | physics | `kerosene for aviation` in `CO2Limit` only, not `co2_limit_per_country*`. | 2050 effective BEWAL price **1 272 EUR/t** (587 system + 685 national) vs 2 740. `CO2Limit` still binds (dual 587). Heat budget 1.432 / 1.667 Mt. | **pass** |
| `cdc16924` transmission `vopt` + NTC ceiling | physics | Grid may grow; usable flow ≤ NTC. | Internal BEWAL–BEVLG `s_nom` 3.6 → 13.2 → 14.4 GW; **usable stays ~3.6 GW**. Cross-border usable = 100 % of NTC except 2050 BE–FR 67 %. | **pass** |
| `d86d6ca3` gas floor on `CCGT-all` | physics | 1 740 MW_e floor can be unabated **or** `CCGT CC`. | BEWAL 1740 / 1741 / 1785 / **1740** MW_e. 2050 split **1277 CCGT + 463 CCGT CC**. Floor no longer stacks 1 740 four times (was 3.4→5.6 GW). | **pass** |
| `bea83bde` cluster pull `-K` / overlay / extract | postprocess | Pull keeps the results symlink; overlay last; extract guards. | `results/walloon` still a symlink after pull. Overlay last needed the extra argparse fix (next row). Extract 49/3/1. | **pass** |
| `a87471e5` Nemo 1000 MW before Nautilus | physics | BE–GB usable = 1 000 MW in 2025/2030. | 2025/2030: cap 1 000, usable **1 000 (100 %)** (was 1 700). 2040 2 400 / 2050 3 800 after Nautilus. | **pass** |
| `d0b9e2ee` BEL includes Wallonia | physics | An NTC row `BEL` also constrains BEWAL corridors. | Internal usable ~3.6 GW through 2030 (`10494636`). Cross-border NTC checks all `ok`. | **pass** |
| `d1cd086b` TYNDP/Elia NTC ceilings | physics | Belgian NTC from TYNDP 2024 + published projects. | ALEGrO 1 000; BE–FR 3 550 / 3 550 / 4 550 / 7 300; BE–NL 3 400 → 8 600. | **pass** |
| `10494636` WAL–VLG today’s capacity through 2030 | physics | BEWAL–BEVLG stays ~today until 2030. | cap 3 600 MW in 2025/2030, then 13 200 / 14 400; usable 3 566–3 600 all years. | **pass** |
| `759e5e50` NTC AC/DC no corridor duplication | physics | One NTC per corridor, not double-counted AC+DC. | review_run NTC table: one row per border, usable ≤ cap. | **pass** |
| `33bd925c` binding-constraint diagnostic | review tooling | Extra debug helper. | n/a (not required on the network) | n/a |
| `7b67b712` 25 Aug log + review | docs | Log of the previous run. | n/a | n/a |

**Working tree (not in `run.json` SHA)**

| Edit | Class | Intended behaviour | Observable | |
|---|---|---|---|---|
| `cluster/nic5.sh` one `--configfile` flag | ops | Walloon config **and** cluster overlay both load. | First solve: `MissingRuleException`. After fix: 16 threads, 1h DAG, all four horizons. | **pass** (uncommitted) |
| `solve_network.py` clip CCL min to remaining `p_nom_max` | physics | `agg_p_nom_min` cannot exceed leftover land-use. | 2050 job 11076308 infeasible (NL offwind min 1713 vs 1163 leftover). Job 11076860 optimal. Test added. | **pass** (uncommitted) |

**TIMES_PyPSA:** no commits since `a48b774`. **pypsa2html:** no new commits
since the 25 Aug review (`649a1e4` / `3cb1f4d` / `2f2f617` already on that
tree). Nine TIMES Sankey pages present.

### 11.2 Solve (level 1)

Four `Optimal objective`. `Crossover 0`, `BarConvTol 1e-5`, **16** threads.
`Numerical trouble`: **0**. 2050 job 11076308 was **infeasible** (presolve /
IIS, §9), not numerical trouble; the rerun is the published point.
Conditioning warnings: 2025/2030 large bounds + large rhs; 2040/2050 large
bounds (up to 6e10). Interior solution: do not read three significant
figures off a capacity.

Peak RAM 32.2 → 38.1 GB, same class as 25 Aug (27.5 → 36.7 GB). Barrier
times similar except 2050 longer (97 vs 69 min) on a tighter feasible set.

### 11.3 Soft-link fidelity (level 2)

**Heat-profile (option B′).** 2025 / 2030 / 2050 match. 2040 realised mix on
the decentral buses:

| group | realised TWh_th | TIMES share × load | gap |
|---|---:|---:|---|
| heat pump | 6.064 | 5.60 | **+0.46** |
| biomass boiler | 4.479 | 4.94 | **−0.46** |
| gas / oil / resistive / solar | — | — | 0 |

Rural 0.213 + urban-decentral 0.247 TWh_th. Same pair as 25 Aug / 22 Aug.

**EV grid draw = TIMES `electricity road`.**

| Horizon | PyPSA TWh | TIMES TWh | Δ | of which flexible (grid) |
|---|---:|---:|---|---:|
| 2025 | 0.934 | 0.934 | **−0.0 %** | 0.008 (smart) + 0.924 natural |
| 2030 | 3.393 | 3.393 | **−0.0 %** | 0.214 + 3.155 |
| 2040 | 11.099 | 11.099 | **−0.0 %** | 1.798 + 9.101 |
| 2050 | 16.770 | 16.770 | **−0.0 %** | 2.717 + 13.751 |

Flexible share matches `bev_dsm_availability`. BEV Sankey node closes
(smart + natural in = EV demand out; V2G 0).

**Other transferred carriers.** Industry electricity / methane / naphtha /
solid biomass / kerosene all within ±0.22 %. **Coal for industry** +8.4 %
(2025) / +12.5 % (2030) — same known discrepancy; 2040/2050 within ±0.25 %.
Total BEWAL electric load vs TIMES: −0.05 / −0.31 / **−0.81** / **−0.91 %**.
2040/2050 miss the ±0.5 % band; EV identity still holds.

**Heat-pump capacity must not fall.** BEWAL `p_nom_opt` (MW_th):
**1366 → 1452 → 2525 → 3238**. Delivered decentral heat
**2.20 → 3.06 → 6.07 → 7.89 TWh_th**. Under B′ the MW_th path restates the
pinned peak; use delivered heat as the electrification indicator.

### 11.4 Accounting (level 3)

Every requested BEWAL bus (`AC`, `low voltage`, `EV battery`, `H2`, `gas`,
`solid biomass`, `biogas`, three heat buses) residuals **0.0000 TWh**.
Belgium-wide AC+LV residual 0.00 % of 215 / 251 / 342 / 428 TWh gross.
`e_sum_max` respected: biogas 0 / 0 / 1.45 / **8.30** of 8.30 TWh; solid
biomass 0 / 3.59 / **8.25 (binds)** / 0 TWh. Cyclic stores including EV
battery close.

Sankey WARNs (`pac_fe` −0.147 TWh every year, `vap_se`, `enc_pe` solid-biomass
`prod` on a regional node) are the known mapping holes. BEV is **ok**.

**FAIL:** 2050 `tes_se` in 1.652 out 1.465, gap **−0.187 TWh**. Bus-level
urban-central heat still closes. The hole tracks the degenerate
zero-cost water-pits charger/discharger (**25 754 MW**). Treat as a Sankey
mapping + degeneracy issue, not a failed energy balance.

### 11.5 Model constraints (level 4)

**Nuclear (links, MW_e = `p_nom_opt × efficiency`, grouped on `bus1`).**

| Horizon | BEWAL | BEVLG | vs [`nuclear-alignment-20260816.md`](../nuclear-alignment-20260816.md) |
|---|---:|---:|---|
| 2025 | 1 992 (TH1+TH3) | 1 890 | match |
| 2030 | 1 030 (TH3) | 1 000 (Doel 4) | match |
| 2040 | 1 030 retrofit, no new | 1 000 retrofit, no new | LTO caps |
| 2050 | **3 000** | **0.1** placeholder | all new build in Wallonia |

Must-run band BE [0.783, 0.883]. BEWAL CF **87.1 / 86.2 / 86.4 / 86.5 %**.
2050 output 22.73 TWh at 3 000 MW_e.

**Utility batteries** (charger `p_nom_opt` vs
[`belgium-batteries-20260818.md`](../belgium-batteries-20260818.md) floors).

| Horizon | BEWAL MW (floor) | BEVLG MW (floor) | BEBRU MW (floor 0) |
|---|---|---|---|
| 2025 | **286** (286) | **250** (250) | 0.2 (0) |
| 2030 | **410** (410) | **1 860** (1 860) | 4.7 (0) |
| 2040 | 1 547 (410) | 4 622 (1 860) | 139 (0) |
| 2050 | 2 683 (410) | 9 965 (1 860) | 1 455 (0) |

2025/2030 sit on the floor. 2040/2050 expand (25 Aug had 2040 BEWAL still on
the floor at 410). Home-battery charger is a different carrier
(6 / 116 / 218 / 426 MW).

**Aggregate / Walloon potentials.** Generator-max myopic reset is **fixed
for onwind and offwind**. Remaining FAILs:

- 2025 BE `solar-all` 12 801 vs max 12 600 (extendable 7 348) — **+201 MW**
- 2025 BEWAL `solar-all` 4 088 vs max 3 887 (extendable 1 802) — **+201 MW**

This is not the old diagnostic (extendable tranche **equals** the cap while
total exceeds). 2030–2050 solar-all and all onwind/offwind/nuclear rows pass.
Rooftop stays ~0 against a 46 GW potential.

**CCGT-all floor.** 1 740 MW_e binds as a **fleet** (unabated + CC). 2050
Wallonia actually builds **463 MW_e `CCGT CC`**. Unabated no longer stacks
1 740 × 4 horizons.

**NTC.** ALEGrO 1 000 MW every year through 2030, then 2 000 / 3 200.
**Nemo 1 000 MW** in 2025/2030 (file = usable). 2040 2 400 / 2050 3 800.
AC usable is the NTC, not 0.7 × `s_nom`, because NTC is written as the
usable ceiling under `vopt`. 2050 BE–FR usable 4 905 of cap 7 300 (67 %) —
grown `s_nom` above the NTC.

**CO₂.** Effective Walloon price `|mu(CO2Limit)| + |mu(co2_limit_per_countryBEWAL)|`:

| Horizon | system | BEWAL national | **effective EUR/t** | sequestration dual |
|---|---:|---:|---:|---:|
| 2025 | 42 | 271 | **313** | 374 (binds, limit 0) |
| 2030 | 201 | ~0 | **201** | 113 (binds) |
| 2040 | 243 | ~0 | **243** | 139 (binds) |
| 2050 | 587 | 685 | **1 272** | 360 (binds) |

2025 is still a decarbonised counterfactual (313 EUR/t). 2050 **1 272** is
about half of 25 Aug’s 2 740 — aviation exclusion did its job — and is still
not a carbon-price forecast: the 1.667 Mt national cap plus pinned heat
leaves little slack. `CO2Limit` binds, so kerosene is not free. Sequestration
limit binds every horizon.

### 11.6 Realism (level 5)

**2025 is an optimisation.** BEWAL onwind **6 500 MW** vs historical
~1.5–2 GW — now at the potential cap, not above it. Neighbours in 2025:
DE onwind 63.6 GW, FR 23.1, NL 30.4, GB 41.6. Say so in any “today” chart.

**Build rates (BEWAL).** onwind **0 MW/yr** (already at 6.5 GW in 2025).
solar-hsat **+794 MW/yr** 2025→2030 (0 → 3 970) against historical PV
~200–300 MWp/yr. Flag, do not defend as a plan.

**PV split.** ~0 MW `solar rooftop`. **Total PV** 4.1 → 8.1 → 9.7 → 12.0 GW.
Report the sum. 2040 `solar` drops 4 088 → 2 786 while hsat rises — substitution.

**Capacity factors** (BEWAL): onwind 24.6 / 23.3 / 25.2 / 25.8 % (window
18–32 / 22–27). PV 11.0–11.1 %, hsat 12.9 %. Nuclear **87.1 / 86.2 / 86.4 /
86.5 %**. RoR 26.3 %. Heat-pump effective COP
**2.42 / 2.39 / 2.46 / 2.53**.

**District heating.** Urban-central heat *gross* 0.9 / 2.7 / 2.9 / 4.3 TWh
against rural+urban-decentral ~28 → 21 TWh. **DAC in Wallonia: 0 links / 0 MW
all horizons.** Urban-central air HP **0 / 1 / 1 / 5 MW** (25 Aug 2050 was
84 MW; 22 Aug 1 067 MW) — degenerate DH, not an electrification forecast.
Water-pits charger/discharger **25 754 MW** with `capital_cost = 0` — **not
a result**.

**Hydrogen.** Electrolysis **0 / 0.2 / 0.2 / 0.3 MW**. H2 pipeline (nodal)
28 / 134 / 605 / **663 MW** (25 Aug 2050 was 2 029). Transit, not production.
H2 bus residual 0.00 TWh.

**Gas.** BEWAL gas-bus gross 53 / 63 / 50 / 20 TWh. 2025/2030 above the
~35–40 TWh “today” figure; 2050 is a deep cut.

**Zero-cost capacities (2050, do not plot):** urban central water pits
25 754, electricity distribution grid 9 496, gas pipeline 7 500, BEV charger
4 194, battery discharger 2 738, …

### 11.7 Prices, costs, duals (level 6)

**BEWAL AC marginal prices** (EUR/MWh, from the network — not
`metrics.csv`’s system mean):

| Horizon | mean | median | p05 | p95 | h ≤ 0 | h > 200 | h > 500 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025 | 109.8 | 95.9 | 1.6 | 203.8 | 0 | 575 | 0 | 0.02 | 341 |
| 2030 | 109.9 | 135.6 | 1.6 | 213.3 | 0 | 642 | 0 | 0.03 | 348 |
| 2040 | 121.0 | 144.2 | 1.7 | 250.3 | 0 | 1 394 | 0 | 0.05 | 287 |
| 2050 | 139.5 | 83.2 | 1.7 | 361.7 | 0 | 2 820 | 0 | 0.06 | 475 |

No hour ≤ 0, no hour > 500. 2050 has 2 820 h above 200 EUR/MWh (25 Aug:
2 180). System mean in `metrics.csv` (96.1 → 107.0 → 115.0 → 126.2) is
**not** the BEWAL nodal mean.

**Curtailment (BEWAL, % of available):** onwind **6.6 / 11.2 / 4.2 / 1.9 %**
(25 Aug 2050 was 12 % at 12.4 GW — less wind, less curtailment). Solar ~0–0.3 %.

**`costs.csv` / `metrics.csv` “total costs”** 581 / 593 / 562 / 615 bn EUR
include non-extendable capital. Gurobi objectives 368 / 383 / 330 / 338 bn
do not. Use the solver log for optimality, the CSV for composition. Nodal
cost rows miss Walloon nuclear (`bus0` = EU).

**Biogas / unsustainable.** Forced unsustainable (BEWAL), 2025/2030:

| Horizon | unsust. biogas | unsust. solid | unsust. bioliquids |
|---|---:|---:|---:|
| 2025 | 1.45 TWh | 6.00 TWh | 2.84 TWh |
| 2030 | 0.93 TWh | 3.09 TWh | 1.81 TWh |
| 2040 / 2050 | gone | | |

The 8.3 TWh biogas block:

| Horizon | this run | 25 Aug | effective BEWAL CO₂ (EUR/t) |
|---|---|---|---:|
| 2025 | **off** (0 TWh) | off | 313 |
| 2030 | **off** (~0 TWh) | off | 201 |
| 2040 | **1.45 TWh** | 1.45 TWh | 243 |
| 2050 | **on** 8.30 TWh | on | 1272 |

Do not read 2040’s lower objective vs 2025/2030 as “the system got cheaper”
without this line. Vintage labels: 2050 new nuclear can still be named
`BEWAL nuclear-2025`. Do not group by `build_year`.

### 11.8 TIMES consistency (level 7)

Nuclear follows the agg file derived from the vd (§11.5). Heat mix under B′
matches TIMES except the known 2040 biomass/HP swap. Biogas 8.3 TWh is a
PyPSA annual-energy potential, used in full only in 2050. Electricity
generation mix is free to differ; Walloon onwind is now **14.0 → 14.7 TWh**
at a 6.5 GW cap (25 Aug went to 25 TWh by exceeding the cap). 2050 Walloon
`CCGT CC` 463 MW_e is a PyPSA new-build outcome inside the TIMES-aligned
gas floor — still not a TIMES retrofit of Flémalle + Seraing. CO₂ caps are
the PyPSA per-country file with aviation **out** of the national LHS/RHS.

### 11.9 Robustness (level 8)

Same vintage as 25 Aug except the review-fix physics. Indicators that moved
by more than ~20 % and must be reported as a **range**, not a point:

| Indicator (BEWAL) | this run | 25 Aug | note |
|---|---|---|---|
| 2050 onwind MW | **6 500** | 12 395 | CCL max fix; do not mix the two in a chart |
| 2050 effective CO₂ EUR/t | **1 272** | 2 740 | aviation out of national cap |
| 2050 CCGT / CCGT CC MW_e | 1 277 / **463** | ~5 640 unabated / ~0 | `CCGT-all` floor |
| Nemo 2025/2030 MW | **1 000** | 1 700 | NTC file |
| 2040 battery charger MW | 1 547 | 410 (floor) | expansion vs floor |
| 2050 battery charger MW | 2 683 | 3 041 | same class |
| 2050 H2 pipeline MW | 663 | 2 029 | transit either way; electrolysis ~0 |
| 2050 water pits MW | **25 754** | 1 118 | zero capital_cost; not a result |
| 2050 urban central air HP MW | 5 | 84 | still degenerate |
| 2025/2050 objective | −4 % / +7 % | — | onwind cap + aviation + vopt |

Zero-capital-cost links, `solar` vs `solar-hsat`, and anything whose dual is
~0 will wander. Weather year is **2010 only**. Resolution is 1h.

### 11.10 Numbers that must not be published as-is

1. **2050 BEWAL carbon price 1 272 EUR/t** (or the 685 national dual alone).
   Better than 2 740, still a cap diagnostic on ~1.67 Mt with pinned heat.
2. **2025 capacities as “today”** — onwind 6.5 GW, CO₂ dual 313 EUR/t.
3. **Any `capital_cost = 0` capacity**, especially urban-central water pits
   **25.8 GW**, BEV charger, distribution grid, battery discharger.
4. **2050 urban-central air heat pump 5 MW** (and the 3 238 MW_th HP total
   if used as an electrification forecast). Decentral delivered heat 7.89
   TWh_th is the B′ indicator.
5. **`metrics.csv` total costs** as the Gurobi objective; **`nodal_*` nuclear
   rows** as Walloon nuclear.
6. **2025 solar-all 12.8 GW** as if it respected the 12.6 GW cap (+201 MW).
7. **`tes_se` Sankey 2050** as an energy-balance failure of the solve.
8. **BEWAL 2050 `CCGT CC` 463 MW_e** as a TIMES retrofit of existing TGVs.
   PyPSA only has *new-build* CCGT-CC.

Onshore wind at **6.5 GW** *may* be published as the model’s capped
potential; 25 Aug’s 12.4 GW must not.

### 11.11 Findings (ranked by whether they change a headline)

**R1 — Generator-max CCL `include_existing` worked.** 9 FAILs → 2. Walloon
onwind is 6.5 GW every year. Remaining +201 MW is 2025 solar-all only.
**Do:** investigate the 201 MW (existing-count vs `solar-all` membership);
until then footnote 2025 BE PV as 12.8 vs 12.6 GW.

**R2 — Aviation out of national CO₂ halved the 2050 Walloon dual
(2 740 → 1 272 EUR/t).** `CO2Limit` still binds. **Do:** still do not
publish the dual as a price.

**R3 — 2050 was infeasible until CCL mins were clipped to remaining
`p_nom_max`.** NL offwind TYNDP min 1713 MW vs 1163 MW leftover land-use.
The clip is **uncommitted**. **Do:** commit `solve_network.py` + test before
the next cluster solve.

**R4 — Two `--configfile` flags dropped the walloon config.** Overlay-last
loaded overlay-only. **Do:** commit the single-flag `nic5.sh` fix.

**R5 — Nemo is 1 000 MW; ALEGrO is 1 000 MW.** 18 Aug / 25 Aug R7/R8 closed.

**R6 — `CCGT-all` floor is technology-neutral and binds once.** 2050 Wallonia
builds 463 MW_e CCGT-CC inside 1 740. Unabated no longer stacks per vintage.

**R7 — `vopt` grew internal `s_nom`; NTC kept usable ~3.6 GW WAL–VLG.**
Report usable capacity, not `s_nom_opt`.

**R8 — 2050 `tes_se` Sankey FAIL (−0.187 TWh) with 25.8 GW zero-cost water
pits.** Buses still close. **Do:** drop water pits from published charts;
Sankey TES node is not trustworthy this vintage.

**R9 — Coal-for-industry +8 / +13 % in 2025/2030; 2040/2050 electric-load vs
TIMES −0.8 / −0.9 %.** Unchanged known items.

**R10 — Cluster pull `-K` kept the results symlink.** 25 Aug R2 closed.
`SKIP_S3_UPLOAD=1` leaking into upload is a new ops footgun.

### 11.12 Follow-up actions

1. Commit `cluster/nic5.sh` (one `--configfile` flag) and
   `scripts/solve_network.py` + `test/test_myopic_potentials.py` (CCL min
   clip) so `run.json` matches the solve.
2. Trace the 201 MW 2025 `solar-all` overshoot.
3. Visual check of Explorer dropdown for `demande-haute-2010-1h (times-pypsa)
   - 27/08/2026`.
4. Unset `SKIP_S3_UPLOAD` before `nic5.sh upload` (or have the script ignore
   it on the upload verb).
5. 2040 solid-biomass conflict remains a parameter decision
   (`none:solid_biomass_2040_conflict`).
6. Water-pits / TES Sankey degeneracy — still open; do not plot.

### 11.13 How the numbers were read

- `review_run.py --full` (levels 0–4 + cheap 5–6) and live networks.
- Heat mix via `check_heat_profile_fidelity.py scen_demande_haute live`
  (`results/_heat_softlink_comparison/profile_fidelity_live.csv`).
- Nuclear as `p_nom_opt × efficiency` on `bus1`. Batteries as
  `battery charger` `p_nom_opt` (not `home battery`).
- Biogas / unsustainable from BEWAL `generators_t.p` × snapshot weights, not
  from system-wide `energy.csv`.
- H2 pipeline from `nodal_capacities.csv` (bus0), not the sum of
  forward+reversed links.
- Comparison vintage: archive
  `/sylvain/mount/pypsa-wal-data/archive/walloon-20260825`.
