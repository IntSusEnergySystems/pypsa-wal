# Solve log — scen_demande_haute @ 2010, 1h (origin numerical fixes + TIMES 20260828)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-08-30 12:06 → 2026-08-30 20:40 |
| Operator | Cursor agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml` (weather year restored to **2010** after origin had switched it to 2013); on NIC5 also `cluster/config_cluster.yaml` (overlay last, **one** `--configfile` flag) |
| Code version | pypsa-wal `fix/run-review-20260825` `dbca25df` + uncommitted: weather year 2010 (origin `dbca25df` had 2013), `cluster/config_cluster.yaml` `mem_mb: 100000` (was 1 TB), `config/scenarios.walloon.yaml` comment pointing at `times_20260828`. TIMES_PyPSA `main` `a48b774` |
| Outcome | **success**: 4/4 horizons optimal; CSVs/plots. HTML / Explorer / S3 not run. Critical review **§11**. |

## 2. Goal of the run

Full 1h / 2010 re-solve of `scen_demande_haute` after pulling
`origin/fix/run-review-20260825` (`816be537` CO₂ geology + `dbca25df` numerical
fixes / sequestration revert). Same newest TIMES vd as the cancelled 29 Aug
attempt (`scen_central_demande_haute_v1_260828_2808.vd` from
`s3://intervectoriel/test/scenarios/times_20260828/`). Origin had flipped the
weather year to 2013 for those debug solves; this run puts 2010 back. Cluster
RAM request dropped from 1 TB to 100 GB so the job can start on a mixed `hmem`
node instead of waiting for a whole node.

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_central_demande_haute_v1_260828_2808.vd` |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` |
| Snapshots | 2010-01-01 → 2011-01-01, **8760** hourly, weight 1.0 |
| Sector time resolution | `1h` |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi barrier (`Method 2`), **16** threads / **100 GB**. `BarConvTol 1e-5`, `Crossover 0`. **`BarHomogeneous: 1` from 2030 retry onward** (2025 solved without it). |
| Key scenario overrides | `retrofit_nuclear_once: false`; agg caps `agg_p_nom_minmax_demande_haute.csv`; option B′ heat-profile pinning; `conventional.inflexible_nuclear.enable: true`; `electricity.transmission_limit: vopt`; aviation excluded from national CO₂; `agg:BEWAL:CCGT-all:min` gas floor |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval / network build (prepare) | local | `LOCAL_CORES=4`; TMPDIR `/sylvain/mount/pypsa-wal-data/tmp` (`/dev/sdb1`). `resources/` and `results/walloon` are already symlinks onto that disk. |
| LP solve | NIC5 `hmem` | 16 cpus/task, **100 GB** (not 1 TB), `SOLVE_RUNTIME=1440` min. 2025 job **11085822** started immediately on `nic5-w071` (shared with mhantro). |
| Post-processing (CSVs, plots) | local | 8/8 at 20:40, `nic5.sh postprocess`, TMPDIR on `/dev/sdb1` |
| HTML report (pypsa2html) | local | **83 pages**, 0 failed, 171 s. Config: `/sylvain/git/pypsa2html/config/pypsa-wal.yaml` |
| Explorer CSV extraction (ClimAct) | local | env `datapypsa`, extractor on `/sylvain/mount`, template `config_extraction_OET.yaml`. **49 / 3 / 1** staged. |

Previous incomplete 29 Aug cluster 2025 (suboptimal) and leftover 26 Aug 2030–2050 networks will be removed on the cluster before this solve so Snakemake cannot skip 2025.

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (launch → CSVs) | **~8.6 h** (12:06 → 20:40). Includes 2030 numerical abort + `BarHomogeneous` retry. |
| Prepare (network build) | **17 s** (12:03:36–12:03:53), nothing to be done — 29 Aug 2010/vd resources still valid |
| Push to cluster | **7 s** (12:03:53–12:04:00) |
| Queue wait (cluster) | **none** — 100 GB job 11085822 started on `nic5-w071` at 12:06 |
| Solve 2025 | job 11085822 **optimal 3.82349461e+11**, barrier 223 iter / 3831 s (63.8 min), peak RAM 32.0 GB, finished 13:19 |
| Solve 2030 | job 11085863 **failed** 14:23 (numerical trouble, 198 iter / 3555 s). Retry job 11085908 **optimal 3.63082928e+11**, homogeneous barrier 221 iter / 5235 s (87.3 min), peak RAM 36.4 GB, finished 16:11 |
| Solve 2040 | job 11086274 **optimal 2.88091748e+11**, homogeneous barrier 282 iter / 7884 s (131 min), peak RAM 37.3 GB, finished 18:35 |
| Solve 2050 | job 11087598 **optimal 2.90510770e+11**, homogeneous barrier 253 iter / 5796 s (96.6 min), peak RAM 38.0 GB, finished 20:25. Orchestrator **5 of 5**. |
| Pull results | **~20:26** — four networks on `/sylvain/mount` (symlink `results/walloon` kept) |
| Post-processing + plots | **~12 min** (20:28–20:40), 8/8 |
| pypsa2html report | **171 s**, 83 pages, 0 failed |
| ClimAct extraction | **~7 min**, 49/3/1 staged |
| S3 upload | **~31 s** |

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size (presolved rows / cols / nnz) | 2025 7.51 M / 10.4 M / 40.8 M · 2030 7.89 M / 14.7 M / 53.4 M · 2040 7.93 M / 16.4 M / 59.2 M · 2050 7.88 M / 17.0 M / 60.1 M |
| Peak RAM per solve | 2025 32.0 GB · 2030 36.4 GB · 2040 37.3 GB · 2050 38.0 GB (all well under 100 GB request) |
| Peak RAM local phases | postprocess + review on 15 GB + 100 GB swap (`/dev/sdb2`); TMPDIR on `/dev/sdb1` |
| Disk footprint | `results/walloon/scen_demande_haute` **1.3 GB** (networks 236 / 314 / 354 / 354 MB) |

## 7. Results

| Horizon | Status | Objective (EUR/a or model units) |
|---|---|---|
| 2025 | optimal | 3.82349461e+11 |
| 2030 | optimal | 3.63082928e+11 |
| 2040 | optimal | 2.88091748e+11 |
| 2050 | optimal | 2.90510770e+11 |

Local result folders:

- Networks: `results/walloon/scen_demande_haute/networks/`
- CSVs / plots: `results/walloon/scen_demande_haute/{csvs,graphs,graphics,maps}/`
- HTML report: `results/walloon/scen_demande_haute/html/index.html`

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | `s3://intervectoriel/test/pypsa_raw_results/20260830_walloon_scen_demande_haute/` |
| Scenario folder on S3 | `s3://intervectoriel/test/scenarios/times-pypsa__demande-haute-2010-1h__20260830/` |
| Explorer display label | `demande-haute-2010-1h` |
| Explorer CSVs | 49 pypsa + 3 strategy |
| TIMES vd staged | `scen_central_demande_haute_v1_260828_2808.vd` |
| Verified in Explorer dropdown | open [explorer.test](https://explorer.test.wallonie.climact.com/) and pick `demande-haute-2010-1h` dated 30/08/2026 |

## 9. Issues encountered and fixes

- Origin `dbca25df` set weather year to **2013**. Restored 2010 snapshots + cutout before prepare (user request; 2010 cutout already on `/dev/sdb1`).
- 1 TB `hmem` request sat behind rcrits/mhantro yesterday (10 h `Resources`, then 2030 cancelled). This run requests **100 GB**.
- Local `/` (`/dev/sda1`) is 46 GB / 17 GB free. All bulky I/O goes to `/dev/sdb1` (`/sylvain/mount`): `resources/`, `results/walloon`, cutout, TMPDIR.
- First `nic5.sh solve` (12:04) aborted immediately: `IncompleteFilesException` on leftover 2030 `configs/` + `heating_profiles/` from the cancelled 29 Aug run. Stopped the driver before pull. Added `--rerun-incomplete` to `nic5.sh solve` (prepare already had it). Cleared stale cluster networks/configs/profiles/incomplete markers.
- Second submit (12:05) hit `LockException` from yesterday's leftover `.snakemake/locks` (29 Aug 02:18). Unlocked on the login node (`snakemake --unlock`) and resubmitted.
- 2030 job 11085863 (13:21–14:23) aborted: Gurobi barrier "Numerical trouble encountered / Model may be infeasible or unbounded. Consider using BarHomogeneous". Status `warning` / condition `other`; solve_network correctly refused to export. Peak RAM 36.0 GB. Set `BarHomogeneous: 1` in `cluster/config_cluster.yaml` and resubmitted (2025 kept).

## 10. Follow-ups / pending

Critical review **§11** (2026-08-30 evening). HTML, ClimAct extract and S3
upload done the same night.

- pypsa2html report rebuilt (83 pages) with sibling `0d1b904`.
- `review_run.py` now reads the agg `tolerance` column (same contract as
  `solve_network.corridor_tolerance`). The 18 FAILs on this vintage were the
  script, not the model.
- Water-pits `e_nom_max` is still `inf` (26 Aug §11.14 B, still open).
- Commit the working-tree weather-year restore, 100 GB / `BarHomogeneous`
  overlay, and `--rerun-incomplete` on `nic5.sh solve`.

## 11. Critical review

**Checked:** 2026-08-30, against [`docs/run-review-checklist.md`](../run-review-checklist.md)
(all eight levels).
**Networks:** `results/walloon/scen_demande_haute/networks/base_s_adm___*.nc`
**Scripted half:** `PYTHONPATH=. python scripts/walloon_scripts/review_run.py … --full`
→ **156 PASS · 26 INFO · 22 WARN · 23 FAIL** (exit 1). Raw output:
`cluster/logs/review_run_full_20260830.txt`. After the human reading in
§11.1–11.5, **22 of those FAILs are tooling** (18× the 0.5 % *data* corridor
that `review_run.py` did not yet apply — fixed after this review; 3×
`BarHomogeneous` only on 2030–2050; 1× stale 2030 solver log from the failed
first job). The remaining real FAIL is 2050 `tes_se` Sankey (−0.193 TWh),
same class as 26 Aug. The 0.5 % width lives in the caps file, not in the
model code ([`renewable-potentials.md`](../renewable-potentials.md) §5.1).

**Verdict:** the run did what it was launched to do. 2025 Walloon onshore
wind is **2 371 MW** (historical, not 6 500). The 2030 fleet sits on the
growth envelope (**4 870 MW**) and 2040/2050 on the land cap (**6 500 MW**).
The phantom Walloon gas store is gone; Loenhout is **8.18 TWh** working gas.
2050 biogas binds at **6.90 TWh** (new cap). 2050 effective Walloon carbon
price fell **1 272 → 547 EUR/t** and the national cap no longer binds. Do
**not** publish the 2050 water-pits charger (29.8 GW), 2025 capacities as
“today”, or the 2050 dual as a price forecast.

Comparison vintage:
[`2026-08-26_scen_demande_haute_2010_1h.md`](2026-08-26_scen_demande_haute_2010_1h.md)
(2010, 1h, B′, **old** vd `scen_demande_haute_v01_260727_fix_nuc_2807.vd`).
This tree adds the RES envelope, gas-store fixes, biogas 4.0/6.9 TWh, a new
TIMES vd, 0.5 % corridor tolerance, and `BarHomogeneous` from 2030.

| Level | Verdict |
|---|---|
| 0 provenance | **pass** (`dbca25df` + working-tree 2010 / 100 GB / `BarHomogeneous`; configs identical except horizon + that flag) |
| 0b commit intent | **pass** (table in §11.1b; RES envelope, gas store, working gas, biogas cap all visible) |
| 1 solve | **pass with caveats** (Crossover 0; large bounds/rhs; 2030 needed `BarHomogeneous`) |
| 2 TIMES soft link | **pass with caveats** (EV identity exact; 2040 heat gap now 0.01 TWh; coal +10/+14/+37/+23 %) |
| 3 accounting identities | **pass with caveats** (buses close; 2050 `tes_se` Sankey FAIL; other Sankey WARNs are known mapping holes) |
| 4 constraint compliance | **pass** (2025 agg “overshoots” are the 0.5 % corridor; nuclear / Nemo / onwind envelope / biogas cap hold) |
| 5 realism | **pass with caveats** (2025 is now a capacity calibration but still a CO₂ optimisation; onwind +500 MW/yr 2025→2030; water pits unbounded; DE 2030 onwind 115 GW) |
| 6 prices / costs | **pass with caveats** (2025 mean 166 EUR/MWh; 2050 has 37 h > 500; biogas binds only in 2050) |
| 7 TIMES consistency | **pass** (nuclear trajectory; heat mix pinned; 2050 biogas 6.9 TWh is a deliberate PyPSA/TIMES split) |
| 8 robustness | **pass with caveats** (onwind now a trajectory, not a flat 6.5 GW; H2 pipe / batteries / CCGT-CC / pits still wander vs 26 Aug) |

### 11.1 Provenance (level 0)

No `run.json` (local tree, S3 skipped). Effective configs
`results/walloon/scen_demande_haute/configs/config.base_s_adm___<year>.yaml`
are identical across horizons except `planning_horizons` and
`BarHomogeneous: 1` on 2030/2040/2050 (2025 solved before that overlay).
Weather year and cutout agree (`2010-01-01` → `2011-01-01`,
`europe-2010-sarah3-era5`). `resolution_sector: 1h`.
`sector.times_file` is the intended
`scen_central_demande_haute_v1_260828_2808.vd`; scenario overlay points at
`agg_p_nom_minmax_demande_haute.csv`.
`heat_stock_age_profile`, `transmission_limit: vopt`,
`conventional.inflexible_nuclear.enable`, `sector.ccgt_cc: true`,
`sector.dac: false` are in the **effective** config. Solver logs confirm
**16 threads**. `co2_sequestration_potential` is the **reverted** EU scalar
(0 / 20 / 90 / 125 Mt), not the 29 Aug geology ramp (`816be537` then
`dbca25df`).

`review_run.py` FAILed the three later configs for `BarHomogeneous`. That is
not a mid-run rebuild against a changed model — it is the 2030 retry
overlay.

The local 2030 solver log first pulled was the **failed** job 11085863
(14:23). The successful log (job 11085908, 16:06,
`Optimal objective 3.63082928e+11`, `BarHomogeneous 1`) was copied from the
cluster during this review; the failed original is at
`/sylvain/mount/pypsa-wal-data/tmp/base_s_adm___2030_solver.FAILED_first.log`.

### 11.1b Commit intent (level 0b)

Previous production run:
[`2026-08-26_scen_demande_haute_2010_1h.md`](2026-08-26_scen_demande_haute_2010_1h.md)
at pypsa-wal `759e5e50`, TIMES_PyPSA `a48b774`. This tree is `dbca25df` /
`a48b774` plus the working-tree weather / RAM / `BarHomogeneous` edits in §9.

**pypsa-wal `759e5e50..dbca25df`**

| Commit | Class | Intended behaviour | Observable on this tree | |
|---|---|---|---|---|
| `bab60ed6` CCL min-clip + one `--configfile` | physics / ops | `agg_p_nom_min` cannot exceed leftover land-use; walloon + cluster overlay both load. | 2050 feasible on first attempt (26 Aug needed a clip rerun). 16 threads, 1h DAG, all four horizons. | **pass** |
| `96fd920e` RES envelope + 2025 pin | physics | 2025 = historical fleet; later years grow at ≤ 2× record, then land. BEWAL onwind 2 359 → 4 869 → 6 500. | BEWAL onwind **2 371 / 4 870 / 6 500 / 6 500**. 2025 solar-all 4 109 vs pin 4 088 (+0.5 % corridor). NL/GB 2025 onwind 7.0 / 16.3 GW (were 30 / 42). | **pass** |
| `fc7e3678` / `3199efae` improvement-plan notes | docs | n/a | n/a | n/a |
| `2aea1b01` no Walloon gas store | physics | `BEWAL gas Store` `e_nom_max = 0` every horizon. | **0 / 0 / 0 / 0 GWh**. | **pass** |
| `46c2f485` working gas, drop quantile clip | physics | Loenhout = Fluxys working gas (~8.2 TWh), not 545 GWh cushion. | BEVLG **8.23 / 8.18 / 8.18 / 8.18 TWh**, `e_nom_max = inf`. | **pass** |
| `6cdb085d` archive gas-storage write-up | docs | n/a | n/a | n/a |
| `907433a6` biogas 4.0 / 6.9 TWh | config | `e_sum_max` 8.3 / 8.3 / 4.0 / 6.9; 2050 loses the old 8.3 bind. | Used 0.00 / 0.00 / 0.22 / **6.90** of those caps. 2050 binds. | **pass** |
| `c4220d71` items 5 and 7 were pypsa2html bugs | postprocess | Heat charts need a rebuilt report (`pypsa2html` `0d1b904`). | No `html/` on this tree. | **n/a** (pending rebuild) |
| `816be537` geology limits sequestration | physics | Reverted by the next commit. | n/a on this tree | n/a |
| `dbca25df` corridor 0.5 % + sequestration revert + weather 2013 | physics | Collapsed 2025 min=max corridors get a 0.5 % gap; EU sequestration scalar restored; snapshots 2013. | 2025 totals = cap × 1.005 (BEWAL onwind 2 371 vs 2 359). Sequestration dual binds every year (431 / 73 / 125 / 342 EUR/t). Weather **overridden to 2010** in the working tree — see next row. | **pass** (weather restored) |

**Working tree (not in `dbca25df`)**

| Edit | Class | Intended behaviour | Observable | |
|---|---|---|---|---|
| `config.walloon.yaml` snapshots/cutout 2010 | config | Production weather year, not the 2013 debug flip. | Effective config `2010-01-01` / `europe-2010-sarah3-era5`. | **pass** |
| `cluster/config_cluster.yaml` 100 GB + `BarHomogeneous: 1` | ops / solver | Start on a mixed `hmem` node; 2030+ homogeneous barrier. | Queue wait **none**. 2030 first job aborted; retry optimal. Peak RAM 32–38 GB. | **pass** |
| `cluster/nic5.sh` `--rerun-incomplete` | ops | Stale incomplete files do not abort the DAG. | First submit still needed a manual clear; later submits ran. | **pass** |
| `scenarios.walloon.yaml` comment → `times_20260828` | docs | The vd **path** is already in HEAD. | Effective `times_file` is the 28 Aug vd. | **pass** |

**TIMES_PyPSA:** no commits since `a48b774`. **pypsa2html:** `0d1b904`
(heat accounting) is on the sibling checkout; this run has no HTML report.

### 11.2 Solve (level 1)

Four `Optimal objective` (2030 after replacing the stale failed log).
`Crossover 0`, `BarConvTol 1e-5`, **16** threads. 2025: default barrier,
223 iter / 63.8 min. 2030 first job: numerical trouble at iter 198; retry
with `BarHomogeneous` 221 iter / 87.3 min. 2040 131 min, 2050 97 min.
Conditioning warnings: 2025/2030 large bounds + large rhs; 2040/2050 large
bounds (up to 6e10). Interior solution: do not read three significant
figures off a capacity.

Peak RAM 32.0 → 38.0 GB, same class as 26 Aug (32.2 → 38.1 GB). 100 GB
request was enough; 1 TB is not needed at 1h.

Objectives vs 26 Aug: 2025 **+4 %** (382 vs 368 bn), 2030 **−5 %**, 2040
**−13 %**, 2050 **−14 %**. 2025 is more expensive because the historical
fleet replaces a 6.5 GW wind counterfactual; later years are cheaper on a
cleaner RES trajectory and a looser 2050 national CO₂ dual.

### 11.3 Soft-link fidelity (level 2)

**Heat-profile (option B′).** 2025 / 2030 / 2050 match to solver tolerance.
2040 realised mix on the decentral buses:

| group | realised TWh_th | TIMES share × load | gap |
|---|---:|---:|---|
| heat pump | 13.324 | 13.313 | **+0.011** |
| biomass boiler | 4.456 | 4.467 | **−0.011** |
| gas / oil / resistive / solar | — | — | 0 |

Rural 0.005 + urban-decentral 0.005 TWh_th. The old 0.46 TWh 2040 biomass
shortfall is **gone**: the new vd asks for ~4.47 TWh_th of biomass boilers
(was 4.94) and **13.3 TWh_th** of heat pumps (was 5.6).

**EV grid draw = TIMES `electricity road`.**

| Horizon | PyPSA TWh | TIMES TWh | Δ | of which flexible (grid) |
|---|---:|---:|---|---:|
| 2025 | 0.936 | 0.936 | **−0.0 %** | 0.008 smart + 0.927 natural |
| 2030 | 4.916 | 4.916 | **−0.0 %** | 0.310 + 4.572 |
| 2040 | 12.619 | 12.619 | **−0.0 %** | 2.044 + 10.348 |
| 2050 | 16.922 | 16.922 | **−0.0 %** | 2.741 + 13.876 |

New vd is more electrified on the road than 26 Aug (2030 4.92 vs 3.39 TWh).
Flexible share matches `bev_dsm_availability`. BEV Sankey node closes.

**Other transferred carriers.** Industry electricity / methane / naphtha /
solid biomass / kerosene all within ±0.2 %. **Coal for industry** +10.1 %
(2025) / +14.1 % (2030) / **+36.7 %** (2040) / +22.8 % (2050) — known
discrepancy, worse in 2040/2050 on the new vd. Total BEWAL electric load vs
TIMES: −0.04 / −0.32 / **−0.81** / **−0.99 %**. 2040/2050 still miss the
±0.5 % band; EV identity still holds.

**Heat-pump capacity must not fall.** BEWAL `p_nom_opt` (MW_th):
**1 595 → 1 681 → 5 548 → 8 389** (26 Aug 1 366 → 1 452 → 2 525 → 3 238).
Delivered decentral heat **2.48 → 3.34 → 13.32 → 20.40 TWh_th**. Under B′
the MW_th path restates the pinned peak; use delivered heat as the
electrification indicator. The 2040/2050 jump is the new TIMES mix, not a
PyPSA build-rate.

### 11.4 Accounting (level 3)

Every requested BEWAL bus (`AC`, `low voltage`, `EV battery`, `H2`, `gas`,
`solid biomass`, `biogas`, three heat buses) residuals **0.0000 TWh**.
Belgium-wide AC+LV residual 0.00 % of 203 / 248 / 351 / 416 TWh gross.
`e_sum_max` respected: biogas 0.00 / 0.00 / 0.22 / **6.90 of 6.90 TWh**;
solid biomass 0 / 6.00 / **8.25 (binds)** / 1.83 TWh. Cyclic stores
including EV battery close.

Sankey: BEV node closes all years. 2050 `tes_se` **FAIL −0.193 TWh** (26 Aug
−0.187) with 29.8 GW water pits. `enc_pe` / `pac_fe` / `vap_se` WARNs are
the known mapping holes.

### 11.5 Model constraints (level 4)

**Nuclear (links, MW_e = `p_nom_opt × efficiency`, grouped on `bus1`).**

| Horizon | BEWAL | BEVLG | vs alignment note |
|---|---:|---:|---|
| 2025 | 1 992 (TH1+TH3) | 1 890 | match |
| 2030 | 1 030 (TH3) | 1 000 (Doel 4) | match |
| 2040 | 1 030 retrofit, no new | 1 000 retrofit, no new | LTO caps |
| 2050 | **3 000** | **0.05** placeholder | all new build in Wallonia |

Must-run band BE `p_min_pu = 0.783`. BEWAL CF **88.3 / 86.3 / 86.3 / 86.3 %**.
2050 output 22.67 TWh at 3 000 MW_e.

**Onwind envelope (`96fd920e`).**

| Horizon | BEWAL MW | what binds |
|---|---:|---|
| 2025 | **2 371** | historical 2 359 + 0.5 % corridor |
| 2030 | **4 870** | 2 × record growth (4 869) |
| 2040 | **6 500** | PNEC/EDORA land cap |
| 2050 | **6 500** | same |

The 26 Aug flat 6 500 MW every year is gone. 2025 solar-all **4 109 vs
4 088** is the same corridor, **not** the old +201 MW floor-vs-cap conflict.

`review_run.py` reported 18 aggregate-max FAILs in 2025. Every one is
**cap × 1.005**, i.e. inside the `tolerance` column of the caps file. The
script has since been taught that column; they were never a model defect.

**Utility batteries** (charger `p_nom_opt`).

| Horizon | BEWAL MW (floor) | note vs 26 Aug |
|---|---|---|
| 2025 | **286** (286) | floor |
| 2030 | **410** (410) | floor |
| 2040 | 1 217 (410) | 26 Aug 1 547 |
| 2050 | 1 317 (410) | 26 Aug 2 683 |

**CCGT-all floor.** 1 740 MW_e binds as a fleet in 2025/2030
(**1 740 / 1 740 / 2 427 / 1 919** MW_e unabated). `CCGT CC` is **~0 MW_e**
every year (26 Aug 2050 built 463). Unabated no longer stacks 1 740 × 4.

**NTC.** ALEGrO 1 000 MW through 2030, then 2 000 / 3 200. **Nemo 1 000 MW**
in 2025/2030. 2040 2 400 / 2050 3 800. 2050 BE–FR usable 4 892 of cap 7 300
(**67 %**) — same as 26 Aug. Internal BEWAL–BEVLG usable stays **3 566 MW**.

**CO₂.** Effective Walloon price `|mu(CO2Limit)| + |mu(co2_limit_per_countryBEWAL)|`:

| Horizon | system | BEWAL national | **effective EUR/t** | sequestration dual |
|---|---:|---:|---:|---:|
| 2025 | 68 | 339 | **407** | 431 (binds, limit 0) |
| 2030 | 161 | ~0 | **161** | 73 (binds) |
| 2040 | 229 | ~0 | **229** | 125 (binds) |
| 2050 | 547 | ~0 | **547** | 342 (binds) |

2025 is still a decarbonised counterfactual on the *price* (407 EUR/t) even
though capacities are now historical. 2050 **547** is less than half of
26 Aug’s 1 272 — the national cap **does not bind**. `CO2Limit` still binds,
so kerosene is not free. Sequestration limit binds every horizon (EU scalar
restored). `biomass limit <= 0` in 2025 still bans sustainable biomass.

### 11.6 Realism (level 5)

**2025 is a capacity calibration, not a price calibration.** BEWAL onwind
**2 371 MW** matches the historical pin (~2.4 GW), not the 6.5 GW of 26 Aug.
Neighbours in 2025 are now pinned too: DE onwind 63.9 GW, FR 23.2, NL 7.0,
GB 16.3 (26 Aug NL/GB were 30.4 / 41.6). Say so in any “today” chart: the
*capacities* are 2025, the *dispatch and prices* are not (CO₂ dual 407 EUR/t,
mean AC price 166 EUR/MWh, 3 126 h above 200).

**Build rates (BEWAL).** onwind **+500 MW/yr** 2025→2030 (2 371 → 4 870)
against historical ~100–150 MW/yr and a documented fastest-five-year of
~120–130. The 4 869 MW 2030 cap *is* 2 × that record over ten years
(2020–2030), so the five-year step from a 2025 pin is twice as steep. Flag,
do not defend as a plan. solar-hsat **+478 / +529 MW/yr** 2025→2030→2040
(20 → 2 413 → 7 699) against historical PV ~200–300 MWp/yr.

**Neighbours.** DE onwind 63.9 → **115 GW** in 2030 (+10.2 GW/yr vs a
~5 GW/yr record). That is the collapsed corridor `96fd920e` already flagged
(target 115 GW above the 112.5 GW growth cap). It still sets the 2030
European price signal.

**PV split.** ~0 MW `solar rooftop`. **Total PV** 4.1 → 6.5 → 10.5 → 11.8 GW
(`solar` + `solar-hsat`). Report the sum. 2040 `solar` drops 4 088 → 2 785
while hsat rises — substitution.

**Capacity factors** (BEWAL): onwind 26.3 / 23.2 / 24.2 / 25.6 % (window
18–32). PV 11.0–11.1 %, hsat 12.8–12.9 %. Nuclear **88.3 / 86.3 / 86.3 /
86.3 %**. RoR 26.3 %. Heat-pump effective COP **2.49 / 2.42 / 2.48 / 2.60**.

**District heating.** Urban-central *load* 0.25 / 1.29 / 1.54 / 2.96 TWh
against rural+urban-decentral ~27 → 23 TWh. DH share **0.9 / 4.6 / 5.7 /
11.2 %** of Walloon heat. **DAC in Wallonia: 0 links / 0 MW all horizons.**

**Hydrogen.** Electrolysis **~0 MW**. H2 pipeline (nodal, bus0)
**3 918 / 4 544 / 4 590 / 5 291 MW** (26 Aug 2050 was 663). Transit, not
production. H2 bus residual 0.00 TWh. Report as a range vs 26 Aug, not a
point.

**Gas.** BEWAL gas-bus gross 59 / 62 / 47 / 18 TWh. 2025/2030 above the
~35–40 TWh “today” figure; 2050 is a deep cut. Walloon store **0 GWh**.

**Water pits (2050).** charger/discharger **29 773 MW**, store **689 GWh_th**,
`e_nom_max = inf`. Same unbounded-store artefact as 26 Aug §11.14 B
(then 25 754 MW / 628 GWh_th). **Not a result.** 2025 pits are now modest
(54 MW / 8 GWh_th).

### 11.7 Prices, costs, duals (level 6)

**BEWAL AC marginal prices** (EUR/MWh, from the network — not
`metrics.csv`’s system mean):

| Horizon | mean | median | p05 | p95 | h ≤ 0 | h > 200 | h > 500 | min | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025 | 165.7 | 168.0 | 93.9 | 225.3 | 0 | 3 126 | 0 | 1.59 | 320 |
| 2030 | 97.9 | 119.6 | 1.6 | 178.9 | 0 | 169 | 0 | 0.02 | 293 |
| 2040 | 115.3 | 137.6 | 1.6 | 232.3 | 0 | 1 219 | 0 | 0.04 | 347 |
| 2050 | 127.1 | 80.9 | 1.7 | 337.1 | 0 | 2 454 | **37** | 0.06 | 510 |

No hour ≤ 0. 2050 is the first vintage with hours above 500 EUR/MWh (37 h,
max 510). 2025 has **no cheap surplus hours** (p05 94 EUR/MWh) — the
historical fleet plus a 407 EUR/t CO₂ dual. System mean in `metrics.csv`
(134.7 → 96.4 → 108.9 → 118.2) is **not** the BEWAL nodal mean.

**Curtailment** (system `curtailment.csv`, TWh): onwind 0.02 / 2.45 / 3.98 /
2.51. BEWAL onwind CF 23–26 % with a 6.5 GW late-horizon cap is not a
curtailment crisis.

**`costs.csv` / `metrics.csv` “total costs”** 595 / 563 / 523 / 572 bn EUR
include non-extendable capital. Gurobi objectives 382 / 363 / 288 / 291 bn
do not. Use the solver log for optimality, the CSV for composition. Nodal
cost rows miss Walloon nuclear (`bus0` = EU).

**Biogas / unsustainable.** Forced unsustainable (BEWAL), 2025/2030:

| Horizon | unsust. biogas | unsust. solid | unsust. bioliquids |
|---|---:|---:|---:|
| 2025 | 1.45 TWh | 6.00 TWh | 2.84 TWh |
| 2030 | 0.93 TWh | 0.30 TWh | 1.81 TWh |
| 2040 / 2050 | gone | | |

The biogas block:

| Horizon | this run | 26 Aug | cap | effective BEWAL CO₂ (EUR/t) |
|---|---|---|---:|---:|
| 2025 | **off** (0 TWh) | off | 8.3 | 407 |
| 2030 | **off** (0 TWh) | off | 8.3 | 161 |
| 2040 | **0.22 TWh** | 1.45 TWh | **4.0** | 229 |
| 2050 | **on** 6.90 TWh | 8.30 TWh | **6.9** | 547 |

Do not read 2040’s lower objective vs 2025 as “the system got cheaper”
without the 2025-calibration and biogas lines. Vintage labels: 2050 new
nuclear can still be named `BEWAL nuclear-2025`. Do not group by
`build_year`.

### 11.8 TIMES consistency (level 7)

Nuclear follows the agg file derived from the vd (§11.5). Heat mix under B′
matches TIMES; the old 2040 biomass/HP swap is now 0.01 TWh. Biogas 6.9 TWh
in 2050 is a **deliberate** PyPSA/TIMES split (`907433a6`; TIMES vd still
has ~8.1 TWh) — do not publish it as TIMES-consistent until the ICEDD
citation arrives. Electricity generation mix is free to differ; Walloon
onwind is now **5.5 → 9.9 → 13.8 → 14.6 TWh** on the envelope (26 Aug was
14.0 → 14.7 TWh at a flat 6.5 GW). 2050 `CCGT CC` is **0 MW_e** this
vintage. CO₂ caps are the PyPSA per-country file with aviation **out** of
the national LHS/RHS.

New vd vs 26 Aug on the transferred demands: 2030 EV **+45 %** (4.92 vs
3.39 TWh); 2040/2050 decentral HP **+119 % / +159 %**. Those are TIMES
inputs, not PyPSA findings.

### 11.9 Robustness (level 8)

Same weather year, cutout, `1h`, option B′ as 26 Aug; **new vd** plus the
physics in §11.1b. Indicators that moved by more than ~20 % and must be
reported as a **range**, not a point:

| Indicator (BEWAL) | this run | 26 Aug | note |
|---|---|---|---|
| 2025 onwind MW | **2 371** | 6 500 | RES envelope; do not mix in a chart |
| 2030 onwind MW | **4 870** | 6 500 | growth cap |
| 2050 onwind MW | 6 500 | 6 500 | land; now reached in 2040, not 2025 |
| 2050 effective CO₂ EUR/t | **547** | 1 272 | national cap slack |
| 2050 CCGT CC MW_e | **~0** | 463 | same floor, different build |
| 2050 battery charger MW | 1 317 | 2 683 | expansion vs floor either way |
| 2050 H2 pipeline MW | 5 291 | 663 | transit either way; electrolysis ~0 |
| 2050 water pits MW | **29 773** | 25 754 | unbounded store; not a result |
| 2050 decentral HP TWh_th | **20.4** | 7.9 | new TIMES mix |
| 2025/2050 objective | +4 % / −14 % | — | calibration + envelope + vd |

Zero-capital-cost links, `solar` vs `solar-hsat`, and anything whose dual is
~0 will wander. Weather year is **2010 only**. Resolution is 1h.

### 11.10 Numbers that must not be published as-is

1. **2050 BEWAL carbon price 547 EUR/t** (or the 547 system dual alone).
   Better than 1 272, still a cap diagnostic, not a price forecast.
2. **2025 prices / dispatch as “today”** — capacities are pinned; the CO₂
   dual is 407 EUR/t and the mean AC price is 166 EUR/MWh.
3. **Any `capital_cost = 0` capacity**, especially urban-central water pits
   **29.8 GW** / 689 GWh_th. Same defect as 26 Aug §11.14 B.
4. **2050 heat-pump 8 389 MW_th** as an electrification *forecast*. Delivered
   decentral heat 20.4 TWh_th is the B′ restatement of the new TIMES mix.
5. **`metrics.csv` total costs** as the Gurobi objective; **`nodal_*` nuclear
   rows** as Walloon nuclear.
6. **`tes_se` Sankey 2050** as an energy-balance failure of the solve.
7. **2050 biogas 6.9 TWh** as TIMES-consistent (citation still owed).
8. **DE 2030 onshore 115 GW** as a forecast — it is the collapsed
   target-above-growth corridor.

Onshore wind at **2 371 / 4 870 / 6 500 / 6 500 MW** *may* be published as
the model’s envelope (historical → 2× record → land). 26 Aug’s flat 6.5 GW
and 25 Aug’s 12.4 GW must not be mixed into the same chart.

### 11.11 Findings (ranked by whether they change a headline)

**R1 — The RES envelope did what `96fd920e` said.** 2025 Walloon onwind is
the historical fleet; 2030 sits on 4 870 MW; 2040/2050 on 6 500. The +201 MW
2025 solar-all FAIL of 26 Aug is gone (replaced by the 0.5 % corridor).
**Do:** keep publishing the trajectory with the “2× record / land” labels;
do not sell +500 MW/yr 2025–2030 as a plan.

**R2 — 2050 Walloon effective CO₂ fell 1 272 → 547 EUR/t and the national
cap no longer binds.** Aviation exclusion was already on the 26 Aug tree;
this drop is the new TIMES heat mix plus the envelope plus biogas 6.9.
`CO2Limit` still binds. **Do:** still do not publish the dual as a price.

**R3 — Phantom Walloon gas store is gone; Loenhout is 8.18 TWh.** Item 1 of
the improvement plan is visible on the network.

**R4 — 2040 heat-profile shortfall is now 0.01 TWh.** The 0.46 TWh biomass
gap was a TIMES-mix vs Walloon-biomass conflict; the new vd asks for more
HP and less biomass. **Do:** keep running `check_heat_profile_fidelity.py`
on every new vd.

**R5 — Water pits still unbounded.** 29.8 GW / 689 GWh_th in 2050. 26 Aug
§11.14 B is **not done**. **Do:** `e_nom_max` on `urban central water pits`.

**R6 — Coal-for-industry +10 / +14 / +37 / +23 %.** Worse on the new vd,
especially 2040. Still a soft-link accounting item, not a solve failure.

**R7 — `review_run.py` FAILed the 0.5 % *data* corridor.** 18 false FAILs.
The width is in the caps file (`tolerance` column), not hardcoded in
`solve_network`. **Done** after this review: the script now reads the same
column as `corridor_tolerance`.

**R8 — 2030 needed `BarHomogeneous`.** 2025 default barrier was fine. Keep
the flag on the cluster overlay; it is not a physics change.

**R9 — Nemo is 1 000 MW; ALEGrO is 1 000 MW.** Unchanged. 2050 BE–FR usable
67 % of grown cap, same as 26 Aug.

**R10 — Cluster 100 GB started immediately.** Peak 38 GB. 1 TB is not
required at 1h on this model.

### 11.12 Follow-up actions

1. Commit the working-tree 2010 weather restore, 100 GB / `BarHomogeneous`
   overlay, and `nic5.sh --rerun-incomplete`.
2. ~~Teach `review_run.py` the agg `tolerance` column (R7).~~ **Done.**
3. Water pits `e_nom_max` — still 26 Aug §11.14 B (R5).
4. ~~Rebuild pypsa2html before any heat-chart deliverable (`0d1b904`).~~ **Done** (83 pages).
5. 2040/2050 coal-for-industry gap (R6) — still open.
6. ICEDD citation for 4.0 / 6.9 TWh biogas, or stop claiming TIMES
   consistency on that carrier.
7. ~~HTML / ClimAct / S3 if this vintage is to be published.~~ **Done** —
   Explorer folder `times-pypsa__demande-haute-2010-1h__20260830`.
8. DE 2030 onwind 115 GW collapsed corridor — already documented in
   [`renewable-potentials.md`](../renewable-potentials.md) §7; decide
   whether the 2030 European price signal is acceptable.

### 11.13 How the numbers were read

- `review_run.py --full` (levels 0–4 + cheap 5–6) and live networks.
  Successful 2030 solver log pulled from NIC5 after the script had already
  read the failed first-job log.
- Heat mix via `check_heat_profile_fidelity.py scen_demande_haute live`
  (`results/_heat_softlink_comparison/profile_fidelity_live.csv`).
- Nuclear as `p_nom_opt × efficiency` on `bus1`. Batteries as
  `battery charger` `p_nom_opt` (not `home battery`).
- Biogas / unsustainable from BEWAL `generators_t.p` × snapshot weights, not
  from system-wide `energy.csv`.
- H2 pipeline from `nodal_capacities.csv` (bus0).
- Comparison vintage: 26 Aug log + this tree’s CSVs
  (`results/walloon/scen_demande_haute/csvs/`).
