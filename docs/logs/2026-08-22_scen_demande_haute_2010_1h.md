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

## 11. Critical review

**Checked:** 2026-08-23, against `instructions.md` (sanity checks, same-vintage
rule, operational-cost / biogas note) and the nuclear / battery notes.
**Networks:** `results/walloon/scen_demande_haute/networks/base_s_adm___*.nc`

**Verdict:** the solve is technically clean. The three post-run guards pass,
nuclear sits on the TIMES trajectory, and the battery floors bind then let go.
Do **not** read the 2030/2040 objective moves versus 18 Aug as an economic
trend: the two trees are different vintages, and the 8.3 TWh Walloon biogas
block is **off** in 2030 and 2040 here (on in the 18 Aug 1h run).

### 11.1 Same-vintage check (do this before any comparison)

`instructions.md`: *Only compare runs of the same vintage. Diff
`results/<run>/configs/config.base_s_adm___<year>.yaml` first.*

Weather year, cutout, snapshots, `1h`, TIMES vd, option B′, SDR 0.035, and the
nuclear agg file are the same as
[`2026-08-18_scen_demande_haute_2010_1h.md`](2026-08-18_scen_demande_haute_2010_1h.md).
The 2025 snapshots are **not** the same vintage. Material diffs:

| Key | this run (`walloon` / `softlink-harmonisation`) | 18 Aug 1h (`times-pypsa`) |
|---|---|---|
| `run.prefix` | `walloon` | `times-pypsa` |
| `sector.bev_dsm_availability` | Elia 0.010 / 0.070 / 0.180 / 0.180 | scalar **0.5** |
| `sector.bev_natural_charging_split` / `local_bev_dsm` | on (three-profile blend) | absent |
| `sector.v2g` | **false** | **true** |
| `existing_capacities.heat_stock_age_profile` | TIMES-derived (2010/2015/2019 = 0.089 / 0.089 / 0.822) | absent |
| `sector.retrofitting.interest_rate` | 0.12 (`RSD-RENO`) | 0.04 — inert while `retro_endogen: false` |
| `sector.land_transport_electric_share` | 0.15 / 0.35 / 0.81 / … | 0.05 / 0.20 / 0.70 / … |

§5.1 already says the objective gap is the EV-charging / TIMES-mapping work.
That is correct, and incomplete: V2G disappeared, the flexible EV share fell
from 50 % to Elia’s 1–18 %, and the heat-pump age profile is new.
Cross-scenario charts that put this folder next to the 18 Aug `times-pypsa`
tree will plot them as if they were the same model.

### 11.2 Post-run sanity checks

Recomputed from the live networks. All three match §7.

**Heat-profile fidelity (option B′).** 2025 / 2030 / 2050 match the pinned
profiles to solver tolerance. **2040** relaxes **0.46 TWh_th** of
biomass-boiler profile onto the heat-pump absorber (rural 0.213 + urban
0.247). Realised 2040 mix on the decentral buses:

| group | realised TWh_th | TIMES share × load | gap |
|---|---:|---:|---:|
| heat pump | 6.064 | 5.60 | **+0.46** |
| biomass boiler | 4.479 | 4.94 | **−0.46** |
| gas / oil / resistive / solar | — | — | 0 |

That is the known CO₂-cap vs TIMES biomass floor
([`heat-softlink.md`](../heat-softlink.md) §4.2), not a pinning bug. Total
|annual gap| 0.92 TWh, all in that pair.

**EV grid draw = TIMES `electricity road`.**

| Horizon | PyPSA TWh | TIMES TWh | Δ | of which flexible (grid) |
|---|---:|---:|---:|---:|
| 2025 | 0.934 | 0.934 | **−0.0 %** | 0.009 (1.0 %) |
| 2030 | 3.393 | 3.393 | **−0.0 %** | 0.238 (7.0 %) |
| 2040 | 11.099 | 11.099 | **−0.0 %** | 1.998 (18.0 %) |
| 2050 | 16.770 | 16.770 | **−0.0 %** | 3.019 (18.0 %) |

The flexible share is exactly `bev_dsm_availability`. No +11 % double-counted
charger loss, no +5.6 % flexible-only gross-up.

**Heat-pump capacity must not fall.** BEWAL heat-pump `p_nom_opt` (MW_th):
**1386 → 1471 → 2579 → 4299**. The 18 Aug 1h tree still has the dip the age
profile was written to kill (1398 → **1315** → 2841 → 4199). Delivered heat
(the electrification indicator under B′) rises **2.20 → 3.06 → 6.06 → 7.86
TWh_th**.

### 11.3 Operational costs — check biogas before reading a dip

`instructions.md`: forced *unsustainable* biomass only in 2025/2030; the 8.3
TWh Walloon biogas block at 78.8 EUR/MWh is all-or-nothing (~654 MEUR/a); in
2040 the CO₂ shadow can sit within ~1 EUR/MWh of break-even.

**Forced unsustainable (BEWAL, equality).**

| Horizon | unsust. biogas | unsust. solid | unsust. bioliquids | **sum MEUR/a** |
|---|---:|---:|---:|---:|
| 2025 | 1.45 TWh / 114 | 6.00 TWh / 116 | 2.84 TWh / 421 | **651** |
| 2030 | 0.93 TWh / 73 | 0.65 TWh / 12 | 1.81 TWh / 317 | **402** |
| 2040 / 2050 | carriers gone | | | 0 |

2025 matches the ~656 MEUR note. 2030 is below ~451 because unsustainable
*solid* biomass is not fully taken (0.65 of 3.2 TWh available) — the CO₂ cap
is already biting.

**The 8.3 TWh biogas block flipped.** BEWAL `biogas` generator is always
8.3 GW nameplate at 78.82 EUR/MWh. Dispatch:

| Horizon | this run | 18 Aug 1h | CO₂ shadow this / 18 Aug (EUR/t) |
|---|---|---|---|
| 2025 | **off** (~0 TWh) | off | ~0 / ~0 |
| 2030 | **off** (~0 TWh) | **on** 8.30 TWh / 654 MEUR | **176** / 197 |
| 2040 | **off** (0.13 TWh / 10 MEUR) | **on** 8.30 TWh / 654 MEUR | **197** / 205 |
| 2050 | **on** 8.30 TWh / 654 MEUR | on | 503 / 493 |

Fossil gas at ~40 EUR/MWh plus ~0.2 tCO₂/MWh × the system CO₂ shadow is
75 EUR/MWh at 176 EUR/t and 79 EUR/MWh at 197 EUR/t — on top of the 78.8
biogas price. 2030 is clearly below the knife-edge; 2040 is on it and landed
**off**. That is why 2040 here is **not** the “implausibly cheap” case
(objective *higher* than 18 Aug). The 18 Aug 2030/2040 numbers include
654 MEUR of biogas opex this run does not.

Do not read 2030’s −31 bn EUR objective versus 18 Aug as “the system got
cheaper.” Most of that is the vintage change in §11.1; the biogas flip is
only 0.65 bn and goes the other way (this run *saves* the 654 MEUR).

### 11.4 Nuclear — aligned

`p_nom_opt × efficiency`, MW_e. Do not read `p_nom` on extendable plant after
`Crossover 0`.

| Horizon | BEWAL | BEVLG | vs [`nuclear-alignment-20260816.md`](../nuclear-alignment-20260816.md) |
|---|---:|---:|---|
| 2025 | 1 992 (TH1+TH3) | 1 890 (Doel 1+4) | match |
| 2030 | 1 030 (TH3) | 1 000 (Doel 4) | match |
| 2040 | 1 030 retrofit, no new | 1 000 retrofit, no new | LTO caps |
| 2050 | **3 000** (1 030 retrofit + 1 970 new) | **0.05** placeholder | all new build in Wallonia |

Bit-identical siting to the 18 Aug 1h and 6h diagnostics. The CCL
max-on-links fix is holding.

### 11.5 Utility batteries — floors bind, then the model builds

Floors from [`belgium-batteries-20260818.md`](../belgium-batteries-20260818.md)
(charger `p_nom_min`, 4 h store).

| Horizon | BEWAL MW (floor) | BEVLG MW (floor) | BEBRU MW (floor 0) |
|---|---|---|---|
| 2025 | **286** (286) | **250** (250) | 0.2 (0) |
| 2030 | **410** (410) | **1 860** (1 860) | 0.3 (0) |
| 2040 | 945 (410) | 1 930 (1 860) | **350** (0) |
| 2050 | 1 755 (410) | **8 000** (1 860) | 1 048 (0) |

2025/2030 sit on the floor to the MW. From 2040 the optimiser expands, and
Flanders + Brussels take most of it. 2050 BEVLG at 8 GW is a model outcome,
not a committed park — treat it as “the LP wants more than the NECP 2.27 GW
floor,” not as a forecast. Home batteries stay small except BEWAL 2040/2050
(444 / 555 MW), which is the three-profile EV / local-flex stack, not the
utility carrier.

### 11.6 Heat mix (BEWAL decentral, TWh_th)

| group | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| heat pump | 2.20 | 3.06 | 6.06 | 7.86 |
| gas boiler | 15.27 | 16.05 | 12.58 | 7.13 |
| oil boiler | 6.00 | 2.88 | 0.38 | 0.00 |
| biomass boiler | 2.50 | 3.45 | 4.48 | 3.37 |
| resistive heater | 1.69 | 1.18 | 0.59 | 2.29 |
| solar thermal | 0.14 | 0.12 | 0.08 | 0.07 |
| **total** | **27.79** | **26.74** | **24.17** | **20.73** |

Shares match TIMES except the 2040 biomass/HP swap. Oil is gone by 2050.
Resistive heat *rises* in 2050 (2.29 TWh, 11 % — TIMES asks for that).
Capacity under B′ is a restatement of the pinned peak; do not use the
1386→4299 MW_th path as the electrification story.

### 11.7 Objectives and prices — what is comparable

Gurobi LP objective (EUR/a). Noise floor with `Crossover 0` / `BarConvTol
1e-5` is ~190 MEUR ([`heat-softlink.md`](../heat-softlink.md) §4.3).

| Horizon | this 1h | 18 Aug 1h + B′ | 18 Aug 6h + B′ | 14 Aug 1h, no B′ |
|---|---:|---:|---:|---:|
| 2025 | 3.488e11 | 3.563e11 | 3.526e11 | 3.945e11 |
| 2030 | 3.541e11 | 3.851e11 | 3.793e11 | 3.952e11 |
| 2040 | 3.077e11 | 2.988e11 | 2.937e11 | 3.223e11 |
| 2050 | 3.190e11 | 3.067e11 | 3.041e11 | 3.375e11 |

Versus 18 Aug 1h: 2025 −7.5 bn, 2030 −31.0 bn, 2040 +8.9 bn, 2050 +12.3 bn.
All larger than the noise floor; **none** is a same-vintage sensitivity.

System mean electricity price (EUR/MWh): 92.7 → 98.6 → 98.5 → 115.4. 2030 is
14 EUR/MWh *below* the 18 Aug 1h (112.7) — same vintage warning. CO₂ shadow:
~0 → 176 → 197 → 503 EUR/t (system `CO2Limit`). Walloon national cap duals
stay small after 2025 (BEWAL 6.8 / 26.7 / 80.0 EUR/t).

`csvs/costs.csv` “total costs” (563 / 560 / 526 / 587 bn) is **not** the
Gurobi objective: it annualises existing capital. Use the solver log for
optimality, the CSV for composition.

### 11.8 What this run actually answered

The goal in §2 was “first full 1h / 2010 production run of
`softlink-harmonisation` after the `config.walloon.yaml` consolidation.” That
succeeded:

- 4/4 optimal, standard barrier, no “Numerical trouble.”
- Soft-link guards green; heat-pump age profile does what §5 of
  `heat-softlink.md` said it would.
- EV energy identity holds at every horizon.
- Nuclear and battery floors are where the notes say they should be.
- Published: raw + Explorer 49/3/1 on S3
  (`times-pypsa__demande-haute-2010-1h__20260822`). Visual dropdown check
  still pending (§10).

It did **not** answer “how did demande-haute change since 18 Aug under
otherwise identical physics.” That needs a re-solve of this branch with the
18 Aug EV/V2G keys, or the reverse.

### 11.9 Residual issues (from §9–§10, still true)

1. **`nic5.sh solve` applies `config.walloon.yaml` after
   `config_cluster.yaml`**, so 1h jobs got 12 threads / 100 GB instead of
   16 / 1 TB. Peak RSS 35 GB — fine this time; invert the overlay order
   before the LP grows.
2. Local prepare on a 15 GB box must cap atlite rules at 2 threads
   (`build_solar_thermal_profiles` is `threads: 16`).
3. Explorer test-site visual check not done.
4. Working-tree / pypsa2html `results_dir` edits from this run were not
   committed (per request at solve time).
5. 2040 solid-biomass conflict remains a parameter decision
   (`none:solid_biomass_2040_conflict`), not a constraint bug.

### 11.10 How the numbers were read

- Networks and
  `results/walloon/scen_demande_haute/configs/config.base_s_adm___2025.yaml`
  vs the 18 Aug snapshot under `results/times-pypsa/…`.
- Heat mix via `scripts/walloon_scripts/compare_heat_softlink.py` helpers
  (`heat_injection_terms`: HP is reversed, boilers use `η · p0`).
- Nuclear as `p_nom_opt × efficiency`. Batteries as `battery charger`
  `p_nom_opt` (not `home battery`).
- Biogas / unsustainable from BEWAL `generators_t.p` × snapshot weights, not
  from system-wide `energy.csv`.
