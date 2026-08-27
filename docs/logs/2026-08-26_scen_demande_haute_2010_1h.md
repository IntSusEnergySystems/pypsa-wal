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
2050 dual, the water-pits capacity (25.8 GW), or 2025 capacities as
“today”. **Root causes and recommended fixes for the flat onshore wind, the
water pits, the 2050 carbon price, and a new finding on neighbour offshore
wind: §11.14.**

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
a result**; it is `e_nom_opt / etpr` on a 628 GWh_th store (§11.14 B), i.e.
**23 × Walloon urban-central peak heat demand (1 105 MW_th)**.

**Hydrogen.** Electrolysis **0 / 0.2 / 0.2 / 0.3 MW**. H2 pipeline (nodal)
28 / 134 / 605 / **663 MW** (25 Aug 2050 was 2 029). Transit, not production.
H2 bus residual 0.00 TWh.

**Gas.** BEWAL gas-bus gross 53 / 63 / 50 / 20 TWh. 2025/2030 above the
~35–40 TWh “today” figure; 2050 is a deep cut.

**Zero-cost capacities (2050, do not plot):** urban central water pits
25 754, electricity distribution grid 9 496, gas pipeline 7 500, BEV charger
4 194, battery discharger 2 738, …

> **Correction 2026-08-27.** The water-pits number is *not* a free-variable
> degeneracy — see [§11.14 B](#1114-recommendations-added-2026-08-27). The
> charger/discharger `p_nom` is pinned by `TES_energy_to_power_ratio` to
> `e_nom / 22.5`, and the store pays 99–116 EUR/MWh (62.4 MEUR/yr in
> Wallonia). The defect is the **unbounded store** (`e_nom_max = inf`).

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
   **25.8 GW**, BEV charger, distribution grid, battery discharger. For the
   pits, neither the 25.8 GW_th *nor* the 628 GWh_th behind it is publishable:
   that is 10.5 million m³ of pit, **52 × the largest ever built** (Vojens, DK,
   0.20 Mm³) — see §11.14 B.
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
onwind is 6.5 GW every year. Remaining +201 MW is 2025 solar-all only, and it
is **traced** (§11.14 E1): a data conflict, not a constraint bug — the 2025
agg cap (3 887) is 201 MW *below* the PV the model already has standing
(2 286 non-extendable + a 1 802 brownfield `p_nom_min` floor = 4 088), and
`add_CCL_constraints` correctly raises the cap to the floor rather than going
infeasible. **Do:** raise the 2025 `solar-all` anchors, or correct the
existing-capacity input. Footnote 2025 BE PV as 12.8 vs 12.6 GW meanwhile.

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

**R8 — 2050 `tes_se` Sankey FAIL (−0.187 TWh) with 25.8 GW water pits.**
Buses still close. The pits are a **priced but unbounded** seasonal store, not
a zero-cost degeneracy (§11.14 B). **Do:** drop water pits from published
charts; Sankey TES node is not trustworthy this vintage; add an `e_nom_max`.

**R9 — Coal-for-industry +8 / +13 % in 2025/2030; 2040/2050 electric-load vs
TIMES −0.8 / −0.9 %.** Unchanged known items.

**R10 — Cluster pull `-K` kept the results symlink.** 25 Aug R2 closed.
`SKIP_S3_UPLOAD=1` leaking into upload is a new ops footgun.

### 11.12 Follow-up actions

Recommendations with diagnosis and proposed fixes: **§11.14**.

1. Commit `cluster/nic5.sh` (one `--configfile` flag) and
   `scripts/solve_network.py` + `test/test_myopic_potentials.py` (CCL min
   clip) so `run.json` matches the solve. Reviewed in §11.14 F.
2. ~~Trace the 201 MW 2025 `solar-all` overshoot.~~ **Closed** — §11.14 E1.
   It is a data conflict (2025 agg cap below the installed base), not a
   constraint bug. Remaining action: raise the 2025 `solar-all` anchors or
   correct the installed-capacity input.
3. Visual check of Explorer dropdown for `demande-haute-2010-1h (times-pypsa)
   - 27/08/2026`.
4. Unset `SKIP_S3_UPLOAD` before `nic5.sh upload` (or have the script ignore
   it on the upload verb).
5. 2040 solid-biomass conflict remains a parameter decision
   (`none:solid_biomass_2040_conflict`).
6. Water pits — **§11.14 B**. Add an `e_nom_max` to
   `urban central water pits`; the MW figure is a consequence of the
   unbounded store, not a free variable. Do not plot meanwhile.

**Before the next production run** (ordered by how much they change results):

7. Audit `offwind-*` `p_nom_max` on the NL and DE nodes — 4.5 and 5.1 GW in
   2050 against 50 and 70 GW targets (**§11.14 D**). Likely an
   availability-matrix / clustering problem, not a CSV value. This is the
   largest single distortion in the 2050 European system and the root cause of
   the 2050 infeasibility.
8. Give `BEWAL,onwind,p_nom_max` a rising trajectory and set
   `sector.max_growth.onwind` (**§11.14 A**). Without a build-rate cap every
   RES trajectory will keep jumping to its ceiling in horizon 1.
9. Decide whether option B′ or the 5 %-of-1990 Walloon cap wins in 2050
   (**§11.14 C**). The pinned heat mix alone is 86 % of the cap. Promote the
   `times_heat_profiles` warning to a hard error above ~70 %.
10. Record Belgium's zero CO₂ sequestration potential as an explicit scenario
    choice, or give it a value (**§11.14 C2**). All three Belgian nodes have
    `e_nom_max = 0` and the nearest sink (NL) is 100 % full.
11. Add the min-clip `logger.warning` (**§11.14 E2**) and mirror the aviation
    exclusion in `diagnose_binding_constraints.py` (**E3**).

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

### 11.14 Recommendations (added 2026-08-27)

Reviewed against the solved networks pulled from
`s3://intervectoriel/test/pypsa_raw_results/20260827_walloon_scen_demande_haute/`
(1.7 GB, all four horizons), `review_run.py --full` (**161 PASS · 26 INFO ·
20 WARN · 3 FAIL**) and `diagnose_binding_constraints.py` on 2050.

The three items the review flags as unacceptable — flat onshore wind,
zero-cost pit storage, a 1 272 EUR/t carbon price — share a property worth
stating plainly: **the constraint code is now doing exactly what it was fixed
to do. What is left is scenario data that disagrees with itself.** None of the
four recommendations below is a code fix to the CCL, NTC or CO₂ machinery.

---

#### A. Onshore wind is flat at 6 500 MW because a **2030** potential is applied to 2050

Not a residual myopic bug. `p_nom_opt` by vintage, BEWAL onwind:

| Horizon | extendable vintage `p_nom_max` | built | fleet | what set the ceiling |
|---|---:|---:|---:|---|
| 2025 | **4 795.8** | 4 795.8 | **6 500** | 6 500 − 1 704 standing (2000–2020) |
| 2030 | 9.9 | 9.8 | **6 500** | = onwind-2000 retiring |
| 2040 | 489.8 | 489.8 | **6 500** | = onwind-2005 + 2010 retiring |
| 2050 | 1 204.5 | 1 204.5 | **6 500** | = onwind-2015 + 2020 retiring |

The optimiser takes the *entire* remaining potential in the first horizon
(+4 796 MW in 2025), after which every later vintage can only replace what
retires. Hence 0 MW/yr growth and a flat 13–15 TWh at CF 23–26 %.

Two independent data defects:

1. **A 2030 figure used for all horizons.** All four rows of
   `data/walloon/custom_potentials.csv` read
   `BEWAL,onwind,p_nom_max,6500,MW,<year>` and the provenance column says
   *"ce qui est plausible d'atteindre en 2030 comme capacité et des projets à
   l'étude"* (PNEC Wallon / EDORA). That is a **2030 deployment expectation**,
   not a 2050 technical potential, and it is the same number in 2050.
2. **No build-rate limit.** Nothing stops horizon 1 from exhausting a
   multi-decade resource in one step. 4 796 MW in a single year against a
   historical Walloon build rate of ~100–150 MW/yr.

**Recommended:**

- Give `BEWAL,onwind,p_nom_max` a **rising trajectory** — 2030 on the PNEC/EDORA
  6 500, then a genuine technical potential for 2040/2050 (the land-eligibility
  raster, or an EDORA/ELIA long-run figure). Until that number exists, an
  explicit placeholder with a source is better than silently reusing 2030.
- Add a **build-rate cap**. `add_max_growth` already exists in
  `scripts/solve_network.py:348` and is driven by
  `sector.max_growth.<carrier>`; it is unset for `onwind`. A ceiling of
  ~300–400 MW/yr would make the 2025 jump impossible and force a trajectory.
  This is the single highest-value change for the *shape* of every RES result.
- Until both are in, publish 6 500 MW only as **"the model's capped
  potential, reached in the first horizon"** — never as a 2050 projection, and
  never as a 2025 capacity (§11.10 item 2).

> **Implemented 2026-08-27** — see
> [`docs/renewable-potentials-analysis.md`](../renewable-potentials-analysis.md)
> §4b. The fix is not a rising *technical* potential but the separation of two
> things that had been conflated: 6 500 MW stays in `custom_potentials.csv` as
> the time-invariant PNEC/EDORA **technical** potential, and a new
> **deployment ceiling** in `agg_p_nom_minmax_*.csv` carries the trajectory —
> BEWAL onwind 2 359 (2025, historical, `min = max`) → 3 000 (2030) → 4 200
> (2040) → 5 400 (2050), each step at ≈ 120-130 MW/yr, i.e. Wallonia's own
> fastest observed five-year build rate. 2025 is now pinned to the historical
> fleet for every node and carrier, so the base year is a calibration and the
> 4 796 MW single-year jump is impossible. `sector.max_growth.onwind` is
> therefore *not* needed: the ceiling trajectory does the same work with
> sourced numbers rather than a rate parameter.

#### B. Water pits: an **unbounded store**, not a zero-cost degeneracy

The review (§11.6, §11.10 item 3, R8) calls the 25 754 MW a zero-capital-cost
artefact. That framing is wrong and it points at the wrong fix. Measured on
the 2050 network:

| quantity | BEWAL 2050 | note |
|---|---:|---|
| pit store `e_nom_opt` | **628 269 MWh_th** | `e_nom_max = inf`, all 4 vintages |
| charger = discharger `p_nom_opt` | **25 754 MW_th** | exactly `e_nom_opt / etpr` |
| `energy to power ratio` (etpr) | 22.5 / 22.5 / 30 / 150 h | by vintage |
| store `capital_cost` | 99.3–116.2 EUR/MWh/a | **not zero** — 62.4 MEUR/yr |
| urban-central heat demand | peak **1 105 MW_th**, 2 693 GWh_th/yr | |
| throughput / full cycles | 1 382 GWh_th, **2.5 cycles/yr** | seasonal |

`add_TES_energy_to_power_ratio_constraints` ([solve_network.py:1063](../../scripts/solve_network.py))
imposes `Store-e_nom − etpr · Link-p_nom == 0` — an **equality**, and it *is*
enforced (`e_nom_opt / p_nom_opt = 22.5` to 4 significant figures on every node).
So the power rating is not a free variable at all; it is a rigid function of
the store. The chain is:

> `e_nom_max = inf` → a 628 GWh_th store is optimal → the 22.5 h equality
> *forces* 25.8 GW_th of charger/discharger → and because the charger costs
> nothing, that forcing is never penalised.

628 GWh_th is ≈ **10.5 million m³** of water pit at 60 kWh/m³, against 0.20
Mm³ for the largest ever built (Vojens, Denmark) — **52 ×**. It is also 23 ×
Walloon peak DH demand and 85 days of average demand.

**Recommended, in order:**

1. **Bound the store.** Give `urban central water pits` an `e_nom_max` per
   node. Pit storage is land- and geology-limited; a defensible proxy is
   ≤ 2–4 weeks of that node's urban-central heat demand (≈ 100–200 GWh_th for
   BEWAL), or an explicit site list. This single bound removes the artefact.
2. **Price the power side.** `central water pit charger` / `discharger` carry
   `investment = 0` in `costs_<year>_processed.csv` (inherited from
   technology-data, which puts the whole cost on the storage volume). With the
   E/P *equality* that makes seasonal storage cheaper than it is. Either put a
   heat-exchanger/pump cost on the charger, or relax the equality to
   `e_nom ≤ etpr · p_nom` so the model can build a big store with a small
   charger and the reported MW stops being fictitious.
3. **Check the etpr trajectory.** 22.5 h (2040/2050 vintages), 30 h (2030),
   **150 h** (2025) is a 6.7 × swing across horizons in what should be a
   technology constant. Worth confirming against technology-data before the
   next run — it changes how much power capacity each MWh of store drags in.
4. Meanwhile: exclude the pits from every capacity chart *and* from any
   "storage installed" total, not just the MW column.

#### C. The 2050 CO₂ price is the **pinned heat mix** meeting a 5 %-of-1990 cap with **four exhausted escape valves**

The aviation exclusion worked (2 740 → 1 272 EUR/t) but it treated a
symptom. The run's own solve log states the cause outright
(`logs/base_s_adm___2050_python.log:12-13`):

> `decentral heating CO2 (upper estimate) 1.432 Mt against the BEWAL cap of
> 1.667 Mt = 85.9 % of the whole node's budget.`
> `WARNING … The TIMES heating mix alone would use 86 % of the BEWAL CO2 budget.`

Option B′ pins 7.13 TWh_th of **gas** boiler heat from TIMES. At 0.198 t/MWh
that is 1.432 Mt — leaving **0.235 Mt** of the 1.667 Mt cap for all of
transport, industry and power. The BEWAL CO₂ balance (aviation excluded, as
the constraint now does) closes *exactly* on the cap:

| gross emitters (Mt) | | removals (Mt) | |
|---|---:|---|---:|
| land transport oil | 0.828 | biogas to gas | **−1.643** |
| urban decentral gas boiler | 0.777 | solid biomass for industry CC | −0.732 |
| rural gas boiler | 0.655 | urban central solid biomass CHP CC | −0.011 |
| coal for industry | 0.612 | | |
| HVC to air | 0.559 | | |
| other (biomass import, agri oil, process CC, shipping, gas CC, CHP CC, CCGT CC) | 0.622 | | |
| **gross** | **4.053** | **removals** | **−2.386** |

Net **1.667 Mt = the cap**, binding, dual **−684.93 EUR/t**, on top of a
system `CO2Limit` dual of −587.28 → **1 272 EUR/t**. Wallonia is the *only*
region whose national cap binds meaningfully (BEVLG, DE, FR, GB, NL duals are
all 0.00; LU −71, BEBRU −0.9), despite every region getting the same
`budget_national: 0.05` factor.

It costs 1 272 EUR/t because **every escape valve is at its limit at once**:

| escape valve | state in 2050 | dual |
|---|---|---:|
| Walloon biogas | **8 300 of 8 300 GWh — 100 % of `e_sum_max`** | (marginal cost 78.8) |
| solid biomass | `biomass limit` binding, 330.9 TWh | **−475.62** |
| CO₂ sequestration | `co2_sequestration_limit` binding | **+360.44** |
| Belgian CO₂ storage | **`e_nom_max = 0` for BEWAL, BEVLG, BEBRU** (also FR, LU) | — |
| NL storage (nearest sink) | 9.095 of 9.095 Mt — **100 % full**, 2040 *and* 2050 | — |

So Wallonia must abate to 5 % of 1990 while its heat mix is fixed exogenously,
its entire biogas potential is already consumed, biomass is rationed
system-wide, it owns no CO₂ storage, and the nearest sink is full. The dual is
the price of an over-determined system, not a carbon price.

**Recommended:**

1. **Make the heat pinning and the CO₂ cap mutually consistent, or say which
   one wins.** These are two exogenous inputs asserting incompatible things
   about 2050 Wallonia. Options, best first:
   - relax option B′ in 2050 only (let the model choose the heat mix once the
     cap is this tight) and report the TIMES mix as a *comparison*, not a
     constraint;
   - or keep B′ and raise the 2050 Walloon cap to what the pinned mix admits;
   - or keep both and **stop reporting the dual entirely** for 2050.
     The `times_heat_profiles` warning already predicts this — promote it to a
     hard error when the pinned mix exceeds ~70 % of the node cap, so the
     conflict is caught before an 8-hour solve.
2. **Give Belgium a CO₂ storage entry or an explicit export route with a
   price.** `e_nom_max = 0` for all three Belgian nodes plus FR and LU, with
   NL 100 % full, means Walloon CCS is a hostage to German and British
   geology. Whether or not Belgium gets domestic storage, this should be a
   *documented scenario choice*, not a silent zero. It is currently one of the
   largest single drivers of the 2050 price.
3. **Re-check the two big unabated residuals** before anyone quotes the cap as
   binding: `coal for industry` 0.612 Mt (37 % of the cap) in 2050 — the
   soft-link is known to overstate coal by 8–13 % in 2025/2030 (R9), and
   nobody has checked 2050; and `HVC to air` 0.559 Mt, which is governed by
   `HVC_environment_sequestration_fraction: 0.0`.
4. Keep §11.10 item 1 as it stands. 1 272 EUR/t is a cap diagnostic.

#### D. **New finding — neighbour offshore wind is an order of magnitude too small**

This is why 2050 was infeasible in the first place, and it is not in the
review. 2050 fleets and remaining potential (MW):

| node | offwind fleet | potential left | onwind fleet | reality check (offshore) |
|---|---:|---:|---:|---|
| **NL** | **4 504** | 0 (exhausted) | 46 852 | 4.7 GW today, **50 GW** 2040 target |
| **DE** | **5 097** | 2 769 | **365 018** | 9.2 GW today, **70 GW** 2045 (WindSeeG) |
| GB | 76 842 | 101 090 | 181 886 | 15 GW today, 50+ GW 2030 |
| FR | 27 778 | 18 141 | 145 412 | 1.5 GW today, ~18 GW 2035 |
| BEVLG | 8 000 | 0 (at the agg cap) | 4 252 | 2.3 GW today, 8 GW — **plausible** |

The Netherlands ends 2050 with **4.5 GW** of offshore wind and Germany with
**5.1 GW**, roughly **11 × and 14 × below** their legislated targets, while the
same countries carry **365 GW** (DE) and 182 GW (GB) of *onshore* wind — far
above any credible land-constrained figure. The model substitutes onshore wind
and solar for offshore wind it is not allowed to build.

That matters for a Walloon study because these are the nodes that set Belgian
import prices and the European CO₂ dual. A neighbour fleet with the wrong
technology mix has the wrong winter capacity factor, which propagates straight
into Belgian scarcity hours, the 587 EUR/t system dual, and the 11 571 MEUR of
congestion rent.

It is also the direct cause of R3: NL's TYNDP `agg_p_nom_min` of 5 054 MW
exceeded the remaining land-use `p_nom_max` of 1 163 MW, which made 2050
infeasible until the min was clipped. **Both numbers are wrong** — the real NL
2050 figure is ~50 GW — so the clip papers over a data error rather than
resolving it.

**Audit done 2026-08-27** — full write-up in
[`docs/renewable-potentials-analysis.md`](../renewable-potentials-analysis.md).
It is an **input** problem, not a clustering one, and it explains the whole
history of potential-pinning in this repo. Read off `profile_adm_*.nc`:

| bus | model offshore `p_nom_max` | installed 2024 | target | eligible km² | % of EEZ |
|---|---:|---:|---:|---:|---:|
| **BEVLG** | **689** | **2 262** | 8 000 | 345 | 10 % |
| **NL** | **4 504** | **4 700** | 50 000 | 2 252 | 4 % |
| **DE** | **5 154** | **9 200** | 70 000 | 2 577 | 6 % |
| FR | 45 905 | 1 500 | 18 000 | 22 953 | 6 % |
| GB | 146 515 | 15 000 | 50 000 | 73 258 | 10 % |

Belgium's modelled offshore potential is **less than a third of what it has
already built**. Three compounding causes: `capacity_per_sqkm: 2` against a
real Belgian build density of ~9.5 MW/km²; the `offwind-ac`
`max_shore_distance: 30 km` / `offwind-dc` `min_shore_distance: 30 km` split,
which strands the Princess Elisabeth Zone (~45 km out) in a DC band whose
availability matrix finds **0.00** eligible cells for BEVLG; and
`natura`/`ship_threshold` exclusions that bite hardest in the busiest sea in
the world.

**Corrected 2026-08-27.** An earlier version of this paragraph also said the
onshore potential was "45.5 % of German land area against a 2 % legal
designation target". That comparison was invalid — eligible land carries
3 MW/km² in the model while Germany's *designated* land carries 22–36 MW/km²,
so the two fractions are not comparable. Like for like: 2 % of German land at
the observed density is ~159 GW, Germany's own 2045 ambition is 160 GW, and the
model's potential is 488 GW — **3.0x, not 23x**. Onshore the potential is a
normal technical potential; what was missing was a **deployment ceiling**, which
is why DE absorbed the shortfall at 365 GW (2.3x its 2045 ambition).

**Recommended:**

1. **`capacity_per_sqkm: 2 → 8` for `offwind-ac/dc/float`.** One line, well
   sourced, fixes Belgium outright (689 → ~2 760 MW).
2. **Give offshore its area back** — point offshore potential at designated
   marine wind zones rather than depth/distance/shipping rasters; at minimum
   widen the AC/DC shore bands so the Belgian zone is reachable.
3. **Bound neighbour `onwind`/`solar`** with a land-availability factor or an
   agg `max` row from TYNDP/national law.
4. Do **not** raise the neighbour offshore `min`s further while the `max` is
   broken — that is what caused this run's 2050 infeasibility, and each
   increase pushes the floor closer to the ceiling it is fighting.
5. Until 1–3 land, treat every 2050 European quantity — system CO₂ dual,
   import prices, congestion rent — as **conditional on an under-built
   offshore fleet**, and say so in §11.10. The neighbour `offwind-all` mins
   must stay meanwhile, but as *documented workarounds*, not policy targets.
6. Separately, and unrelated to potentials: the **`BEBRU` bus region is
   1 676 km², 10.35 × the administrative Brussels region (162 km²), while the
   `BEWAL` bus region is 15 150 km², 10 % *smaller* than Wallonia** (≈ 1 750 km²
   short). The three sum to Belgium correctly, so no area is lost — but Walloon
   land, and the wind and solar potential on it, is being credited to the
   Brussels node. That is a `custom_busmap_BE` question and deserves its own
   look; it is what produced the "861 % of Brussels" figure in the first version
   of this section.

> **Implemented 2026-08-27 (items 3-5; 1-2 partly).** Every modelled node now
> has a sourced `max` for `onwind`, `offwind-all` and `solar-all` at every
> horizon, and a `min` at 2025/2030 only — full table and citations in
> [`docs/renewable-potentials-analysis.md`](../renewable-potentials-analysis.md)
> §4b, assumptions in `config/input_parameters_for_models.csv` (172 rows with
> `source`/`description`/`note`), propagated by `build_common_parameters.py`
> (`managed=43`, was 5).
>
> The offshore raster is **bypassed, not fixed**: `custom_potentials.csv` now
> carries a documented per-node offshore ceiling (BEVLG 8 000, DE 70 000,
> FR 45 000, GB 80 000, NL 50 000 MW) replacing four *undocumented*
> `BEVLG,offwind,p_nom_max,inf` rows. Items 1-2 of this list — the
> `capacity_per_sqkm` correction and pointing offshore potential at designated
> marine wind zones — remain open.
>
> The 2030 minima are deliberately **not** the national targets. Using the
> targets as floors demands 2.5-4.9x each node's fastest observed build rate
> (DE onwind 3.6x, DE offshore 4.6x, GB offshore 4.9x), and these countries are
> officially projected to miss them. The rule is
> `min(2030) = min(target, 2025 fleet + 5 yr x 1.5 x peak observed rate)`, with
> the target kept as the `max`. Enforced by
> `scripts/walloon_scripts/check_res_envelope.py` and
> `test/test_res_envelope.py`.
>
> **Expect the neighbours to change a lot.** Measured against the new envelope
> this run's 2050 fleet breaks 51 caps: DE onwind 365 018 → max 180 000, GB
> onwind 181 886 → 35 000, FR onwind 145 412 → 45 000, FR solar 175 907 →
> 120 000, NL onwind 46 852 → 14 000, LU onwind 2 253 → 700. The 2050 CO₂ dual,
> import prices and congestion rent all move with that. **`resources/` and
> `results/` must be rebuilt from scratch** — an mtime-only rerun would carry
> the old fleet forward through `add_brownfield`.

#### E. Smaller items

1. **2025 `solar-all` +201 MW is closed** (follow-up #2). Mechanism, exactly:
   non-extendable Walloon PV 2 286.1 MW + a brownfield `p_nom_min` floor of
   1 802.2 MW on `BEWAL 0 solar-2025` = 4 088.3 MW, against an agg 2025 max of
   3 887. `add_CCL_constraints` clips the max rhs up to the floor
   (`lower_bounds_gens`, added in `8d1d6e10`) instead of going infeasible —
   which is the right behaviour. The **data** is what disagrees: the 2025 cap
   is below the installed base. Fix the anchor (or the installed-capacity
   input), not the code. Same +201 MW appears in the BE row because BEWAL is
   subtracted from its parent.
2. **The CCL min-clip should log what it weakened.** NL offwind ends 2050 at
   4 504 MW against a 5 054 MW TYNDP floor — the floor is **missed by 550 MW
   (11 %) silently**. Add a `logger.warning` naming each clipped group and the
   shortfall, so a scenario cannot quietly under-deliver a policy minimum.
   The clip itself is correct and should be committed as-is.
3. **`diagnose_binding_constraints.py` still counts aviation** in its §3 BEWAL
   CO₂ decomposition, so it prints "net 3.897 Mt" against a 1.667 Mt cap and
   looks like a violation. It should reuse
   `solve_network.national_co2_expression`'s exclusion list
   (`AVIATION_CARRIER`) so the table matches the constraint it is explaining.
   3.897 − 2.230 = 1.667 = the cap.
4. **`solar rooftop` is 0 MW in all four horizons** against a 46 GW potential,
   while 6.9 GW of `solar-hsat` (single-axis tracking) is built — a technology
   with essentially no Walloon deployment. Real Walloon PV is overwhelmingly
   rooftop. If rooftop is to stay at zero, that is a cost-assumption finding
   worth stating; if not, it needs a floor or a cost correction.

#### F. Review of the two changes that made the run possible

| change | verdict |
|---|---|
| `cluster/nic5.sh` — one `--configfile` flag | **Correct, and my 26 Aug review missed it.** I verified that later files override earlier ones, which is true *within* one flag, but not that argparse `nargs="+"` makes a second `--configfile` **replace** rather than extend. `bea83bde` therefore introduced a regression that only surfaced at launch. The one-flag form is what Snakemake documents. |
| `scripts/solve_network.py` — clip agg `min` residual to remaining `p_nom_max` | **Correct and necessary.** It is the required companion to un-gating `add_land_use_constraint` in `8d1d6e10`: land-use lowers `p_nom_max`, and nothing previously stopped the TYNDP min from demanding more than the leftover. `.replace(np.inf, np.nan)` after the groupby leaves a group unclipped if any member is unbounded — the safe direction. Ordering is right (land-use runs in `prepare_network`, before `extra_functionality`). Two notes: it needs the log line in E2, and it treats a data conflict (D) as a feasibility problem. |

Both should be committed before the next solve so `run.json` describes the code
that actually ran (follow-up #1).
