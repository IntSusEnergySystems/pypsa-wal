# Solve log — scen_demande_haute @ 2010, 1h (master + nuclear must-run)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-08-25 17:15 → 2026-08-26 12:15 (machine hung ~00:24–11:53; see §9) |
| Operator | Cursor agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml`; on NIC5 also `cluster/config_cluster.yaml` |
| Code version | pypsa-wal `master` `d0e2ba28`; TIMES_PyPSA `main` `a48b774` (editable sibling checkout; cluster TIMES_PyPSA rsynced to `/scratch/users/s/q/squoilin/TIMES_PyPSA`) |
| Outcome | **success**: 4/4 horizons optimal; CSVs/plots; pypsa2html 83 pages; Explorer 49/3/1 on S3. Overnight freeze was the ClimAct extract, not the solve. |

## 2. Goal of the run

Full 1h / 2010 production re-solve of `scen_demande_haute` after the post-22-Aug
work on both checkouts (nuclear must-run, CCGT with CCS, TIMES road-transport
soft-link, Sankey pages). Same TIMES vd, weather year, resolution, and option B′
as [`2026-08-22_scen_demande_haute_2010_1h.md`](2026-08-22_scen_demande_haute_2010_1h.md).
Question: does the myopic chain stay feasible and optimal with those changes.

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
| Solver + options | Gurobi barrier (`Method 2`), 12 threads from `config.walloon.yaml` (cluster overlay is merged *before* the study config). `BarConvTol 1e-5`, `Crossover 0`. `UNMET_SCALE=1e6`. |
| Key scenario overrides | `retrofit_nuclear_once: false`; agg caps `agg_p_nom_minmax_demande_haute.csv`; option B′ heat-profile pinning; `conventional.inflexible_nuclear.enable: true` (`p_min_pu_margin: 0.1`) |

`config_cluster.yaml` still says 16 threads / 1 TB, but `nic5.sh solve` passes
`config.walloon.yaml` *after* it, so `solving.mem_mb: 100000` and Gurobi
`threads: 12` win. Peak RSS 36.7 GB — 100 GB was enough.

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval / network build (prepare) | local (`pcbureau`) | `LOCAL_CORES=4`; TMPDIR / Dask scratch / `resources/` / `results/` on `/sylvain/mount`. Existing 32 GB swapfile on the mount was **off** for prepare (sudo needed a password). Cores capped instead of creating more swap. |
| LP solve | NIC5 `hmem`, node `nic5-w073` | 16 cpus/task, 100 GB, `SOLVE_RUNTIME=1440` min. Jobs 11069042 / 11070761 / 11071931 / 11071994 |
| Post-processing (CSVs, plots) | local | 8/8 at 23:55, `LOCAL_CORES=2 SKIP_S3_UPLOAD=1`, no swap |
| HTML report (pypsa2html) | local | 83 pages, 0 failed, 148 s. Config: `/sylvain/git/pypsa2html/config/pypsa-wal.yaml` (`results_dir: results/walloon/scen_demande_haute`) |
| Explorer CSV extraction (ClimAct) | local | env `datapypsa`, extractor on `/sylvain/mount/pypsa-wal-data/climact-extraction/climact-pypsa-eur_results_extraction-88d352b59aa4`, template `config_extraction_OET.yaml`. First attempt froze the box (§9); retry with 32 GB swap succeeded. |

Disk: previous `results/walloon` (1.8 GB) archived to
`/sylvain/mount/pypsa-wal-data/archive/walloon-20260822`. Fresh
`resources/walloon/scen_demande_haute` rebuilt (mtime-only rerun would miss
config/code changes such as nuclear must-run).

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (launch → S3 verified) | **~8 h productive** (17:15 → 23:55 on 25 Aug, then extract+upload 12:03–12:15 on 26 Aug). Wall-clock 17:15 → 12:15 includes an ~11.5 h hung machine. |
| Prepare (network build) | **43 min** (17:15–17:58), 134/134, 4 cores, no swap |
| Push to cluster | 32 s (18:16); TIMES_PyPSA rsynced to scratch (files 16:54) |
| Queue wait (cluster) | < 1 min after DAG (submitted 18:20) |
| Solve 2025 | barrier 168 iter / 2305 s (38.4 min). Job 11069042 |
| Solve 2030 | barrier 231 iter / 4219 s (70.3 min). Job 11070761 |
| Solve 2040 | barrier 288 iter / 5969 s (99.5 min). Job 11071931 |
| Solve 2050 | barrier 198 iter / 4160 s (69.3 min). Job 11071994 |
| Solve chain total | **~5 h 26 min** (orchestrator 18:20 → 23:46; 7/7 steps) |
| Pull results | **2 min** (23:48–23:50), 1.3 GB. **Side effect:** rsync replaced the `results/walloon` symlink with a real directory on `/` (§9) |
| Post-processing + plots | **3 min** (23:52–23:55), 8/8, `LOCAL_CORES=2 SKIP_S3_UPLOAD=1` |
| pypsa2html report | **148 s**, 83 pages, 0 failed |
| ClimAct extraction | **failed** 00:23–00:24 (swap off → hard freeze). **Retry** 12:03–12:15 (**~12 min**) with 32 GB swap on; 49/3/1 staged |
| S3 upload | **32 s** (12:15), raw + explorer + strategy + TIMES vd |

### 5.1 vs 22 Aug 1h (`walloon` / `softlink-harmonisation`)

Same weather year, cutout, snapshots, `1h`, TIMES vd, option B′, SDR, nuclear
agg file. This tree is **not** a same-physics sensitivity: it adds nuclear
must-run, CCGT+CCS, TIMES road-transport mapping, Sankey pages.

| Horizon | this 1h, `master` + must-run | 22 Aug 1h, `softlink-harmonisation` |
|---|---|---|
| 2025 | **3.833e11** (38.4 min barrier) | 3.488e11 (42.5 min) |
| 2030 | **3.891e11** (70.3 min) | 3.541e11 (75.6 min) |
| 2040 | **3.207e11** (99.5 min) | 3.077e11 (100.8 min) |
| 2050 | **3.177e11** (69.3 min) | 3.190e11 (56.4 min) |

2025/2030 objectives are ~+10 % (~34–35 bn EUR/a). That is larger than the
~190 MEUR noise floor and is the expected direction for nuclear must-run
(more nuclear online in those years). 2050 is within 0.4 %. No “Numerical
trouble”. Barrier times match the previous 1h class.

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size 2025 | 31.01 M rows × 14.64 M cols × 74.5 M nnz (presolved 7.37 M × 10.40 M × 40.4 M) |
| LP size 2030 | 39.52 M rows × 19.18 M cols × 94.6 M nnz (presolved 7.75 M × 14.72 M × 53.1 M) |
| LP size 2040 | 42.77 M rows × 21.12 M cols × 102.5 M nnz (presolved 7.77 M × 16.42 M × 58.8 M) |
| LP size 2050 | 43.72 M rows × 21.80 M cols × 104.2 M nnz (presolved 7.70 M × 16.97 M × 59.7 M) |
| Peak RAM per solve (python-side MEM log) | 2025: **27.5 GB** · 2030: **32.3 GB** · 2040: **35.6 GB** · 2050: **36.7 GB** |
| Peak RAM local phases | prepare: 4 cores, no swap. Extract retry: ~11 GB RAM + 2.5 GB of 32 GB swap. First extract (swap off) exhausted 15 GB RAM and hard-froze the box. |
| Disk footprint | resources ~936 MB · results 1.3 GB (networks 1.3 GB) on `/sylvain/mount` |

## 7. Results

| Horizon | Status | Objective (EUR/a) |
|---|---|---|
| 2025 | optimal | 3.83252421e+11 |
| 2030 | optimal | 3.89079471e+11 |
| 2040 | optimal | 3.20679540e+11 |
| 2050 | optimal | 3.17694162e+11 |

Sanity checks (`instructions.md` / checklist level 2), recomputed live:

- **Heat-profile fidelity:** 2025 / 2030 / 2050 match to solver tolerance.
  **2040** relaxes **0.46 TWh_th** of biomass-boiler profile onto the heat-pump
  absorber (rural 0.213 + urban 0.247) — known CO₂-cap vs TIMES biomass floor
  ([`heat-softlink.md`](../heat-softlink.md) §4.2), not a pinning bug. Total
  |annual gap| **0.920 TWh**, all in that 2040 pair. Same as 22 Aug.
- **EV grid draw vs TIMES `electricity road`:** 2025 0.934 / 2030 3.393 /
  2040 11.099 / 2050 16.770 TWh, **−0.0 %** every horizon.
- **BEWAL heat-pump capacity (MW_th):** 2025 **1366** → 2030 **1451** →
  2040 **2609** → 2050 **3316** (does not fall). 22 Aug was 1386 → 1471 →
  2579 → **4299**; the 2050 drop is almost entirely urban-central air HP
  (84 vs 1067 MW), not the decentral B′ fleet.

Local result folders:

- Networks: `results/walloon/scen_demande_haute/networks/base_s_adm___{2025,2030,2040,2050}.nc`
- CSVs / plots: `results/walloon/scen_demande_haute/{csvs,graphs,graphics,maps}/`
- HTML report: `results/walloon/scen_demande_haute/html/index.html` (91 html files counted)

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | `s3://intervectoriel/test/pypsa_raw_results/20260826_walloon_scen_demande_haute/` (4 networks present) |
| Scenario folder on S3 | `s3://intervectoriel/test/scenarios/times-pypsa__demande-haute-2010-1h__20260826/` |
| Explorer display label | `demande-haute-2010-1h (times-pypsa) - 26/08/2026` |
| Explorer CSVs | **49** in `pypsa/`, **3** in `strategy/` — verified on S3 (`aws s3 ls … \| wc -l`) |
| TIMES vd staged | yes — `explorer/times/scen_demande_haute_v01_260727_fix_nuc_2807.vd` |
| Verified in Explorer dropdown | S3 layout verified (49/3/1). Visual check pending — open https://explorer.test.wallonie.climact.com/ and **Clear cache** if the 26/08/2026 label does not appear |

`run.json`: `git_commit` `d0e2ba2804ae5ce2e74ddd2cbd5a3c0b87646d0b`, branch
`master`, `uploaded_at` 2026-08-26T12:15:05+02:00.

## 9. Issues encountered and fixes

- **No extra root swap this run (by request).** Last 1h prepare thrashed to
  9.8 GB swap on 15 GB RAM. The 32 GB file `/sylvain/mount/swapfile` already
  exists (root-owned). For prepare we left it unused and capped cores.
- **`results/walloon` was a real directory on `/` before prepare (~1.8 GB).**
  Moved to the mount archive and re-symlinked.
- **2040 heat-profile budget** (pre-solve): decentral heating CO₂ 2.664 Mt vs
  BEWAL cap 15.456 Mt (17.2 %).
- **2050 heat-profile budget** (pre-solve): decentral heating CO₂ 1.432 Mt vs
  BEWAL cap 1.717 Mt (**83.4 %** of the node budget). Tight; 2050 still solved.
- **Workstation freeze 26 Aug ~00:24 — caused by this workflow.**

  After postprocess + html, `./cluster/nic5.sh extract` started at **00:23**
  (`datapypsa`, template `config_extraction_OET.yaml`). Last extract log line
  **00:24**: `Transforming data` (four 1h networks already loaded in pypsa
  0.35). Previous-boot journal ends **00:21:28** (PackageKit quit); no OOM
  line was flushed. `last` records the previous graphical session as
  **crash**; reboot **26 Aug 11:53** (machine found hung; no syslog for ~11 h).

  **Cause:** ClimAct extraction on a **15 GB RAM** box with **swap OFF**. The
  22 Aug extract of the same scenario needed ~11 GB RAM **plus ~10 GB swap**.
  Without swap this hard-froze the kernel. This is **not** a Gurobi /
  infeasibility / nuclear-must-run issue: all four horizons were already
  `Optimal objective`, CSVs and html were already written.

  Explorer CSVs were **not** produced by the first attempt
  (`results/.../explorer/` empty; no
  `times-pypsa__demande-haute-2010-1h__20260826` under the extractor
  `analysis/graph_extraction_st/v6/`). Partial `graph_data/v6/…20260826/`
  png/csvs from 00:24 were left behind.

  **Fix after reboot:** `pkexec swapon /sylvain/mount/swapfile` (32 GB).
  `nic5.sh pull` had replaced the `results/walloon` **symlink** with a real
  tree on `/` (~1.3 GB). That tree was moved back onto
  `/sylvain/mount/pypsa-wal-data/results/walloon` and re-symlinked at 12:02.
  Extract restarted 12:03 with `OMP/MKL/JOBLIB_NUM_THREADS=1`; a competing
  `review_run.py --full` was killed so the two would not OOM together.
  Retry finished ~12:15, **~12 min**, ~11 GB RAM + 2.5 GB swap.

  **Rule for the next run:** enable the mount swapfile **before** extract (and
  before any other 1h-network Python on this box). Never run extract and
  `review_run.py` at the same time. Do not create a new swapfile.
- **`nic5.sh pull` destroys the results symlink.** rsync of cluster
  `results/walloon/` writes a real directory on `/`. Re-symlink onto the mount
  after every pull, or teach `pull` to rsync into the mount target.

## 10. Follow-ups / pending

Critical review: **§11**. Visual Explorer dropdown check still pending (§8).

Operational:

1. Keep `/sylvain/mount/swapfile` **on** whenever extract / `--full` review /
   `make_summary` run locally.
2. After `nic5.sh pull`, confirm `results/walloon` is still a symlink onto
   `/sylvain/mount`.
3. Invert `nic5.sh solve` overlay order so `config_cluster.yaml` wins on
   threads / `mem_mb` before the 1h LP grows (same residual as 22 Aug).
4. Known CCL generator-max myopic reset (checklist §4.1) is still open — the
   9 FAILs below are that defect, not this run’s physics.
5. Next run’s level 0b previous SHAs are pypsa-wal `d0e2ba28` and
   TIMES_PyPSA `a48b774`.

## 11. Critical review

**Checked:** 2026-08-26, against [`docs/run-review-checklist.md`](../run-review-checklist.md)
(all eight levels) and `instructions.md` (same-vintage rule, biogas /
operational-cost note).
**Networks:** `results/walloon/scen_demande_haute/networks/base_s_adm___*.nc`
**Scripted half:** `python scripts/walloon_scripts/review_run.py … --full`
→ **127 PASS · 47 WARN · 9 FAIL** (exit 1). Raw output:
`cluster/logs/review_run_full.txt`.

**Verdict:** the solve is technically clean (4/4 optimal, buses close, soft-link
guards green, nuclear on the TIMES trajectory, battery floors bind then let
go). The nine FAILs are the **known myopic CCL / `p_nom_max` reset**
(checklist §4.1–4.2), same class as 22 Aug. Do **not** publish the 2050
Walloon carbon price, the 2050 urban-central heat-pump MW, zero-capital-cost
links, or Walloon onshore wind above 6.5 GW as forecasts.

| Level | Verdict |
|---|---|
| 0 provenance | **pass** |
| 0b commit intent | **pass** (table in §11.1b; nuclear must-run, CCGT CC, TIMES fleet/road, Sankey pages all visible) |
| 1 solve | **pass with caveats** (Crossover 0; large bounds/rhs every horizon) |
| 2 TIMES soft link | **pass with caveats** (coal +8/+13 % in 2025/2030, known; 2040/2050 electric-load −0.8/−0.9 %) |
| 3 accounting identities | **pass** (bus balances and BEV Sankey close; other Sankey WARNs are known mapping holes) |
| 4 constraint compliance | **pass with caveats** (nuclear OK; generator-max CCL / onwind potential FAILs are the known myopic defect; NTC usable ≠ file) |
| 5 realism | **pass with caveats** (2025 is an optimisation not a calibration; onwind 2040→2050 +530 MW/yr; PV all utility-scale; no Walloon DAC) |
| 6 prices / costs | **pass with caveats** (biogas mostly off until 2050; 2050 BEWAL CO₂ dual is not a price) |
| 7 TIMES consistency | **pass** (nuclear trajectory; heat mix pinned except the known 2040 biomass/HP swap; biogas 8.3 TWh on only in 2050) |
| 8 robustness | **pass with caveats** (same vintage as 22 Aug except must-run / CCS / road-transport; several capacities swing >20 %) |

### 11.1 Provenance (level 0)

`run.json` commit `d0e2ba28` is an ancestor of current `master` HEAD (same
commit). Effective configs
`results/walloon/scen_demande_haute/configs/config.base_s_adm___<year>.yaml`
are identical across horizons except `planning_horizons`. Weather year and
cutout agree (`2010-01-01` → `2011-01-01`, `europe-2010-sarah3-era5`).
`resolution_sector: 1h`. `sector.times_file` is the intended vd; scenario
overlay points at `agg_p_nom_minmax_demande_haute.csv`.
`heat_stock_age_profile`, `bev_natural_charging_split`, `local_bev_dsm`,
`retrofit_nuclear_once: false`, `conventional.inflexible_nuclear.enable: true`
are all in the **effective** config.

Same-vintage comparison is **only** vs
[`2026-08-22_scen_demande_haute_2010_1h.md`](2026-08-22_scen_demande_haute_2010_1h.md)
(2010, 1h, B′, same vd, prefix `walloon`). 18 Aug is a different vintage
(prefix `times-pypsa`, V2G on, `bev_dsm_availability` 0.5).

### 11.1b Commit intent (level 0b)

Previous production run: [`2026-08-22_scen_demande_haute_2010_1h.md`](2026-08-22_scen_demande_haute_2010_1h.md)
at pypsa-wal `5371edfd`, TIMES_PyPSA `5f49de5`. This tree is `d0e2ba28` /
`a48b774`. Procedure: [`run-review-checklist.md`](../run-review-checklist.md)
level 0b.

**pypsa-wal `5371edfd..d0e2ba28`**

| Commit | Class | Intended behaviour | Observable on this tree | |
|---|---|---|---|---|
| `00a0336e` EV charging weights / TIMES fleet | physics | Walloon BEV charger `p_nom` and EV-battery `e_nom` scale on TIMES **stock share by count**, not the energy ratio; load still on `electricity road`. Neighbours keep Elia `land_transport_electric_share`. `scen_evflex` is a *different* scenario. | `road_transport_*_shares.csv` present. Cars 2025: stock_share **0.152** vs activity_share 0.136. EV grid draw = TIMES electricity road **−0.0 %**. Flexible share is base Elia 1 / 7 / 18 / 18 %, **not** High Flex. | **pass** |
| `1597579a` TIMES Sankey export | postprocess | Nine `times_sankey_*.html` pages in the scenario `html/` (index + custom/mapping × 4 years). | All nine present (`times_sankey_index.html`, `times_sankey_{custom,mapping}_{2025,2030,2040,2050}.html`). | **pass** |
| `33c24a36` CCGT with CCS | physics | New-build extendable `CCGT CC` links; existing TGVs stay unabated; TIMES new-build CCGT-CCS is duals-only in Wallonia. | Carrier exists. BEWAL `p_nom_opt` ≈ 0 all years. 2050 **BEBRU 1 920 MW** and **DE 14.6 GW** prove the option is live. Unabated BEWAL CCGT still carries the 1 740 MW_e floor. | **pass** |
| `506106f5` nuclear must-run | physics | `p_max_pu` from the country CSV, `p_min_pu = p_max_pu − 0.10`. BE band [0.783, 0.883]; FR [0.516, 0.616]. Annual energy inside that band. | Static on every nuclear link: BE 0.783/0.883, FR 0.516/0.616, GB 0.584/0.684, LU 0.900/1.000. BEWAL CF 87.3 / 86.2 / 85.9 / 85.9 % (inside the band). 2050 output 22.57 TWh vs floor 20.6 / cap 23.2 TWh at 3 000 MW_e. | **pass** |
| `d0e2ba28` CCS notes | docs | Alignment note only. | n/a | n/a |
| `ede97573` Sankey node review | review tooling | `review_run.py` FAILs a hole on the BEV node. | BEV node closes (smart + natural in = demand out) every horizon. | **pass** |
| `e44277b6` `6edc0cc5` `9024502b` `15df21c2` | docs / CI | Cleanup, pixi README, failing CI removed. | n/a | n/a |
| merge / log commits `5fb88438`…`3bc3e0c2` | docs | 22 Aug log + review template. | n/a | n/a |

**TIMES_PyPSA `5f49de5..a48b774`**

| Commit | Class | Intended behaviour | Observable | |
|---|---|---|---|---|
| `05f1595` road-transport soft-link | physics | `export_horizon` always writes road-transport; fleet quantities from **stock** (`000VEH`), same `vehicle_class` for count and share. | `resources/…/road_transport_{year}.csv` and `_shares.csv` for all four horizons. EV energy identity holds. | **pass** |
| `a48b774` `sankey-pages` | postprocess | Interactive TIMES Sankeys (custom + mapping) per horizon. | Same nine HTML files as `1597579a`. | **pass** |

**pypsa2html (since 22 Aug)**

| Commit | Class | Intended behaviour | Observable | |
|---|---|---|---|---|
| `649a1e4` BEV smart vs natural | report | Sankey BEV node shows both inflows. | review_run: smart 0.008 / 0.214 / 1.798 / 2.717 TWh + natural 0.924 / 3.155 / 9.101 / 13.751; gap −0.000. | **pass** |
| `2f2f617` carbon capture in charts | report | `CCGT CC` is plottable, not dropped. | Carrier in the network and in `nodal_capacities.csv`. | **pass** |
| `3cb1f4d` `a3cfb8a` | report | Self-sufficiency plot; nested aggregates / EV detection. | Not re-derived here (html built, 0 failed pages). | n/a |

Nothing in this list is absent or inverted. The 2025/2030 **+10 %** objective vs 22 Aug is the must-run commit showing up in the LP, not a vintage mix-up.

### 11.2 Solve (level 1)

Four `Optimal objective`. `Crossover 0`, `BarConvTol 1e-5`, 12 threads.
`Numerical trouble` / `Infeasible`: **0**. Conditioning warnings: 2025 large
bounds + large rhs; 2030 large rhs; 2040/2050 large bounds. Bounds range up
to 6e10 in 2050. Interior solution: do not read three significant figures off
a capacity.

Peak RAM 27.5 → 36.7 GB, same class as 22 Aug (27.3 → 35.2 GB).

### 11.3 Soft-link fidelity (level 2)

**Heat-profile (option B′).** 2025 / 2030 / 2050 match. 2040 realised mix on
the decentral buses:

| group | realised TWh_th | TIMES share × load | gap |
|---|---:|---:|---|
| heat pump | 6.064 | 5.60 | **+0.46** |
| biomass boiler | 4.479 | 4.94 | **−0.46** |
| gas / oil / resistive / solar | — | — | 0 |

Rural 0.213 + urban-decentral 0.247 TWh_th. Same pair as 22 Aug.

**EV grid draw = TIMES `electricity road`.**

| Horizon | PyPSA TWh | TIMES TWh | Δ | of which flexible (grid) |
|---|---:|---:|---|---:|
| 2025 | 0.934 | 0.934 | **−0.0 %** | 0.008 (smart) + 0.924 natural |
| 2030 | 3.393 | 3.393 | **−0.0 %** | 0.214 + 3.155 |
| 2040 | 11.099 | 11.099 | **−0.0 %** | 1.798 + 9.101 |
| 2050 | 16.770 | 16.770 | **−0.0 %** | 2.717 + 13.751 |

Flexible share matches `bev_dsm_availability`. No +11 % double-counted
charger loss, no +5.6 % flexible-only gross-up. BEV Sankey node closes
(smart + natural in = EV demand out; V2G 0).

**Other transferred carriers.** Industry electricity / methane / naphtha /
solid biomass / kerosene all within ±0.22 %. **Coal for industry** +8.4 %
(2025) / +12.5 % (2030) — same known discrepancy as the first reviewed run;
2040/2050 within ±0.25 %. Total BEWAL electric load vs TIMES: −0.05 / −0.31 /
**−0.81** / **−0.91 %**. 2040/2050 miss the ±0.5 % band; EV identity still
holds, so the gap is other electric loads (heat pumps / DH / industry
distribution), not the road-transport mapping.

**Heat-pump capacity must not fall.** BEWAL `p_nom_opt` (MW_th):
**1366 → 1451 → 2609 → 3316**. `heat_stock_age_profile` is in the effective
config. Delivered decentral heat (the electrification indicator under B′)
rises **2.20 → 3.06 → 6.06 → 7.86 TWh_th** — same path as 22 Aug. Capacity
under B′ restates the pinned peak; do not use the MW_th path as the
electrification story. The 2050 MW drop vs 22 Aug is urban-central air HP
(§11.5 / R6), not a 2025→2030 retirement dip.

### 11.4 Accounting (level 3)

Every requested BEWAL bus (`AC`, `low voltage`, `EV battery`, `H2`, `gas`,
`solid biomass`, `biogas`, three heat buses) residuals **0.0000 TWh**.
Belgium-wide AC+LV residual 0.00 % of 215 / 253 / 339 / 441 TWh gross.
`e_sum_max` respected: biogas 0 / 0 / 1.45 / **8.30** of 8.30 TWh; solid
biomass 0 / 6.00 / **8.25 (binds)** / 6.13 TWh. Cyclic stores including EV
battery close.

Sankey WARNs (`pac_fe` −0.147 TWh every year, `vap_se`, `enc_pe` solid-biomass
`prod` on a regional node) are the known mapping holes, not this solve. BEV
is the node that has already bitten; it is **ok** on this tree.

### 11.5 Model constraints (level 4)

**Nuclear (links, MW_e = `p_nom_opt × efficiency`, grouped on `bus1`).**

| Horizon | BEWAL | BEVLG | vs [`nuclear-alignment-20260816.md`](../nuclear-alignment-20260816.md) |
|---|---:|---:|---|
| 2025 | 1 992 (TH1+TH3) | 1 890 (Doel 1+4) | match |
| 2030 | 1 030 (TH3) | 1 000 (Doel 4) | match |
| 2040 | 1 030 retrofit, no new | 1 000 retrofit, no new | LTO caps |
| 2050 | **3 000** | **0.1** placeholder | all new build in Wallonia |

CCL max-on-links is holding. Nuclear does **not** appear in BEWAL rows of
`nodal_capacities.csv` (`bus0` = EU uranium). Recompute from the network.

**Utility batteries** (charger `p_nom_opt` vs
[`belgium-batteries-20260818.md`](../belgium-batteries-20260818.md) floors).

| Horizon | BEWAL MW (floor) | BEVLG MW (floor) | BEBRU MW (floor 0) |
|---|---|---|---|
| 2025 | **286** (286) | **250** (250) | 0.1 (0) |
| 2030 | **410** (410) | **1 860** (1 860) | 0.2 (0) |
| 2040 | **410** (410) | 3 432 (1 860) | 428 (0) |
| 2050 | 3 041 (410) | **8 070** (1 860) | 767 (0) |

2025/2030 sit on the floor to the MW. 2040 BEWAL stays on the floor (22 Aug
had already expanded to 945). 2050 BEWAL 3.0 GW and BEVLG 8.1 GW are model
outcomes, not a committed park. Home-battery charger is a different carrier
(1 / 6 / 196 / 425 MW).

**Aggregate / Walloon potentials — known myopic reset (the 9 FAILs).**
Generator `max` caps the **extendable tranche** only. Diagnostic: 2050 BE
offwind-all total 18 574 MW vs max 8 000 with extendable tranche **exactly**
8 000; 2050 BEWAL onwind 12 395 vs `p_nom_max` 6 500 with extendable
**exactly** 6 500. Solar rooftop stays ~0 against a 46 GW potential. CCGT
`p_nom_min` 1 740 MW_e is re-imposed on the new vintage every horizon
(3 392 → 5 132 → 6 060 → 5 640 MW_e total). Limits-file typos GB/NL
offwind-all 2040/2045 min still present.

**NTC.** ALEGrO (BE–DE) 2025/2030/2040: 1 000 MW nominal = file = usable.
Nemo (BE–GB) 2025/2030: file 1 000, network **1 700** usable (**170 %**) —
same as 18 Aug R8; the link is not named `Nemo` in the network. AC borders
deliver ~0.7 × NTC because of `s_max_pu = 0.7`. 2050 several borders undershoot
the grown NTC file.

**CO₂.** Per-country caps sum to the global cap, so the **effective** Walloon
price is `|mu(CO2Limit)| + |mu(co2_limit_per_countryBEWAL)|`:

| Horizon | system | BEWAL national | **effective EUR/t** | sequestration dual |
|---|---:|---:|---:|---:|
| 2025 | ~0 | 340 | **340** | 339 (binds, limit 0) |
| 2030 | 195 | 6.7 | **201** | 106 (binds) |
| 2040 | 216 | 17.6 | **233** | 113 (binds) |
| 2050 | 625 | **2 114** | **2 740** | 329 (binds) |

2025 “base year” already has a 340 EUR/t national shadow — it is a
decarbonised counterfactual, not a calibration of real 2025. 2050 BEWAL
2 740 EUR/t is the cap (1.717 Mt) plus pinned heat plus nuclear must-run;
**not a carbon-price forecast**. `biomass limit <= 0` in 2025 (sustainable
solid biomass banned Europe-wide); all 2025 biomass is unsustainable.
Sequestration limit binds every horizon, so CCS/DAC volumes (where they exist)
are a restatement of the cap.

### 11.6 Realism (level 5)

**2025 is an optimisation.** BEWAL onwind 6 906 MW vs a 6 500 MW potential
and vs ~historical ~1.5–2 GW. Neighbours in 2025: DE onwind 63.6 GW, FR 28.5,
NL 30.3, GB 32.3 — they set the price signal. Say so in any “today” chart.

**Build rates (BEWAL).** onwind 2040→2050 **+530 MW/yr** (7 100 → 12 395)
against historical ~100–150 MW/yr. solar-hsat +443 / +444 MW/yr over
2025–2040 against historical PV ~200–300 MWp/yr. Flag, do not defend as a
plan.

**PV split.** Walloon PV is overwhelmingly rooftop today; the model puts
~0 MW on `solar rooftop` and splits the rest between `solar` and `solar-hsat`.
**Total PV** 4.1 → 6.3 → 9.4 → 12.0 GW. 2050 `solar` 5 330 vs 22 Aug 8 MW, and
`solar-hsat` 6 662 vs 11 285 — substitution artefact (level 8). Report the
sum.

**Capacity factors** (BEWAL): onwind 24.8 / 23.9 / 24.0 / 23.1 % (window
22–27 / script 18–32). PV 11.0–11.1 %, hsat 12.9 %. BE offshore 46.2–46.3 %
(window 40–50). Nuclear **87.3 / 86.2 / 85.9 / 85.9 %** (window 80–92) — the
must-run is doing what it says. RoR 26.3 %. Heat-pump effective COP
**2.40 / 2.36 / 2.45 / 2.53** (heat out / elec in, all BEWAL HPs including
central). 2025/2030 sit just under the 2.5–3.5 checklist band; not a profile
error.

**District heating.** Urban-central heat *load* 0.46 / 1.22 / 1.90 / 2.69
TWh_th against rural+urban-decentral 27.6 → 20.6 TWh — DH share ~1.6 % in
2025 rising to ~12 % in 2050, not the 6.1 TWh-to-DAC outcome of the first
reviewed run. **DAC in Wallonia: 0 links / 0 MW all horizons.** Urban-central
water-pits charger 460 → 1 121 MW has `capital_cost = 0` — **not a result**.

**Hydrogen.** Electrolysis **0 / 0 / 0 / 0.8 MW**. H2 pipeline (nodal, do not
sum forward+reversed) 4 / 6 / 93 / **2 029 MW**. Wallonia is a **transit
corridor** in 2050, not a producer. H2 bus residual 0.00 TWh.

**Gas.** BEWAL gas-bus gross 48.9 / 57.8 / 49.2 / 12.7 TWh. 2025/2030 above
the ~35–40 TWh “today” figure; 2050 is a deep cut.

**Zero-cost capacities (2050, do not plot):** electricity distribution grid
9 496, gas pipeline 7 500, BEV charger 4 194, battery discharger 3 104,
urban central water pits 1 118, H2 pipeline 1 075, …

### 11.7 Prices, costs, duals (level 6)

**BEWAL AC marginal prices** (EUR/MWh, from the network — not
`metrics.csv`’s system mean):

| Horizon | mean | median | p05 | p95 | h ≤ 0 | h > 200 | h > 500 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025 | 103.2 | 86.0 | 1.6 | 185.9 | 0 | 144 | 0 | 0.03 | 308 |
| 2030 | 102.4 | 133.3 | 1.6 | 181.9 | 0 | 200 | 0 | 0.03 | 280 |
| 2040 | 106.7 | 136.2 | 1.7 | 204.7 | 0 | 541 | 0 | 0.03 | 277 |
| 2050 | 126.1 | 79.6 | 1.7 | 387.8 | 0 | 2 180 | 0 | 0.04 | 482 |

No hour ≤ 0, no hour > 500. 2050 has 2 180 h above 200 EUR/MWh — scarcity
pricing appears once the 1.717 Mt cap binds. System mean in `metrics.csv`
(94.9 → 103.6 → 103.4 → 118.7) is **not** the BEWAL nodal mean. The price
embeds the CO₂ duals; it is not an observed day-ahead price.

**Curtailment (BEWAL, % of available):** onwind 5.6 / 9.0 / 8.7 / **12.0 %**;
solar ~0–0.6 %; solar-hsat ~0. Normal at this penetration.

**`costs.csv` / `metrics.csv` “total costs”** 598 / 606 / 556 / 603 bn EUR
include non-extendable capital. Gurobi objectives 383 / 389 / 321 / 318 bn
do not. Existing Tihange units are annuitised at full new-build cost in the
CSV. Use the solver log for optimality, the CSV for composition. Nodal cost
rows miss Walloon nuclear (`bus0` = EU).

**Biogas / unsustainable — check before reading a dip.**

Forced unsustainable (BEWAL; carriers gone after 2030), volumes identical to
22 Aug:

| Horizon | unsust. biogas | unsust. solid | unsust. bioliquids |
|---|---:|---:|---:|
| 2025 | 1.45 TWh | 6.00 TWh | 2.84 TWh |
| 2030 | 0.93 TWh | 0.66 TWh | 1.81 TWh |
| 2040 / 2050 | gone | | |

The 8.3 TWh biogas block at 78.82 EUR/MWh (nameplate always 8.3 GW):

| Horizon | this run | 22 Aug | effective BEWAL CO₂ (EUR/t) |
|---|---|---|---:|
| 2025 | **off** (0 TWh) | off | 340 |
| 2030 | **off** (0 TWh) | off | 201 |
| 2040 | **1.45 TWh / 114 MEUR** | 0.13 TWh | 233 |
| 2050 | **on** 8.30 TWh / 654 MEUR | on | 2740 |

2040 is on the knife-edge and this run takes a sliver; 2050 takes the whole
block (654 MEUR/a). Do not read 2040’s lower objective vs 2025/2030 as “the
system got cheaper” without this line.

Vintage labels: 2050 new nuclear is still named `BEWAL nuclear-2025`. Do not
group by `build_year`.

### 11.8 TIMES consistency (level 7)

Nuclear follows the agg file derived from the vd (§11.5). Heat mix under B′
matches TIMES except the known 2040 biomass/HP swap. Biogas 8.3 TWh is a
PyPSA annual-energy potential, used in full only in 2050; TIMES may show a
different biogas path — the divergence is foresight + European system
boundary, not a dropped transfer. Electricity generation mix is free to
differ; Walloon onwind 15.0 → 25.1 TWh is a PyPSA outcome above the 6.5 GW
potential (level 4). CO₂ caps are the PyPSA per-country file, not the TIMES
emission path restated.

### 11.9 Robustness (level 8)

Same vintage as 22 Aug except nuclear must-run / CCS / road-transport / Sankey.
Indicators that moved by more than ~20 % and must be reported as a **range**,
not a point:

| Indicator (BEWAL) | this run | 22 Aug | note |
|---|---|---|---|
| 2050 urban central air HP MW | 84 | 1 067 | degenerate DH; drives the 3316 vs 4299 total HP |
| 2050 `solar` vs `solar-hsat` MW | 5 330 / 6 662 | 8 / 11 285 | substitution; total PV similar (12.0 vs 11.3 GW) |
| 2040 battery charger MW | 410 (floor) | 945 | floor vs expansion |
| 2050 battery charger MW | 3 041 | 1 755 | LP wants more storage |
| 2050 H2 pipeline MW | 2 029 | 2 945 | transit corridor either way; electrolysis ~0 |
| 2025/2030 objective | +10 % | — | must-run, not a weather/resolution effect |

Zero-capital-cost links, `solar` vs `solar-hsat`, and anything whose dual is
~0 will wander. Weather year is **2010 only**; adequacy / storage / curtailment
statements are conditional on it. Resolution is 1h; do not compare to a 6h
tree without saying so.

### 11.10 Numbers that must not be published as-is

1. **2050 BEWAL carbon price 2 740 EUR/t** (or the 2 114 national dual alone).
   It is `|mu_system| + |mu_BEWAL|` on a 1.717 Mt cap with pinned heat.
2. **Walloon onshore wind 6.9 → 12.4 GW.** Exceeds `p_nom_max` 6 500 because
   of the myopic generator-max defect. 2040→2050 +530 MW/yr is not a buildable
   rate.
3. **2050 urban-central air heat pump 84 MW** (and the 3 316 MW_th HP total
   if used as an electrification forecast). Decentral delivered heat 7.86
   TWh_th is the B′ indicator.
4. **Any `capital_cost = 0` capacity** (water pits, BEV charger, distribution
   grid, battery discharger, …).
5. **`metrics.csv` total costs** as the Gurobi objective; **`nodal_*` nuclear
   rows** as Walloon nuclear.
6. **Nemo Link as 1 700 MW** without saying the NTC file is 1 000 MW.
7. **2025 capacities as “today”.**
8. **BEBRU 2050 `CCGT CC` 1 920 MW** (and DE 14.6 GW) as a TIMES-aligned
   CCS retrofit. PyPSA only has *new-build* CCGT-CC; TIMES Wallonia retrofits
   Flemalle + Seraing from 2035. Wallonia itself built ~0.

### 11.11 Findings (ranked by whether they change a headline)

**R1 — Overnight crash was the ClimAct extract, not the solve.** 15 GB RAM,
swap off, four 1h networks in `Transforming data`. Same step on 22 Aug needed
~10 GB swap. Documented in §9. Networks / CSVs / html were already good.
**Do:** `swapon` the mount file before extract; never pair extract with
`--full` review.

**R2 — `nic5.sh pull` materialises `results/walloon` on `/`.** 1.3 GB on a 46
GB root disk. **Do:** re-symlink after pull, or rsync into the mount target.

**R3 — Myopic generator-max CCL / `p_nom_max` still reset every horizon.**
9 FAILs, same mechanism as 22 Aug. Nuclear (link max) is **not** affected.
**Do:** subtract existing from generator `rhs_max` in `add_CCL_constraints`;
add a regression test. Until then, cap Walloon onwind charts at 6.5 GW or
show the extendable tranche separately.

**R4 — 2050 Walloon CO₂ dual is pathological (2 740 EUR/t effective).**
Pre-solve heat budget already used 83 % of the 1.717 Mt node cap. Must-run
nuclear + B′ pinning leave almost no slack. **Do:** treat 2050 BEWAL prices
and duals as cap diagnostics, not market results.

**R5 — Nuclear must-run is in the solve and shows up in CF and objective.**
Nuclear CF 86–87 %. 2025/2030 objectives +10 % vs 22 Aug, the years with
the most nuclear online. Trajectory still matches the TIMES agg file.

**R6 — 2050 heat-pump MW is not comparable to 22 Aug.** Decentral B′ heat is
the same 7.86 TWh_th; urban-central air HP collapsed 1 067 → 84 MW.
Zero-cost DH plant (water pits) remains degenerate.

**R7 — Nemo still 1 700 MW vs NTC 1 000; ALEGrO is 1 000.** Unchanged from
18 Aug. AC usable = 0.7 × NTC.

**R8 — Coal-for-industry soft-link +8 / +13 % in 2025/2030.** Known; not a
new mapping bug. 2040/2050 electric-load vs TIMES (−0.8 / −0.9 %) is new
relative to the ±0.5 % band — investigate if a publication quotes total
electricity demand.

### 11.12 Follow-up actions

1. Enable `/sylvain/mount/swapfile` before every local extract / `--full`
   review (ops; this run).
2. Stop `nic5.sh pull` from replacing the results symlink (code).
3. Fix generator-max CCL `include_existing` (code + `test/`; already on the
   books as checklist §4.1).
4. Nemo 1 000 MW / NTC convention (code; 18 Aug R8, still open).
5. Visual check of Explorer dropdown for `demande-haute-2010-1h (times-pypsa)
   - 26/08/2026` (ops).
6. Invert cluster overlay order so 16 threads / 1 TB win (ops/code).
7. 2040 solid-biomass conflict remains a parameter decision
   (`none:solid_biomass_2040_conflict`), not a constraint bug.

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
  `/sylvain/mount/pypsa-wal-data/archive/walloon-20260822`.
