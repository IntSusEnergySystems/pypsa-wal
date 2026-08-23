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
- **Critical review done 2026-08-22 — see §11.** Eleven findings, five of them
  constraint violations. Until they are addressed, the published Explorer
  scenario `times-pypsa__demande-haute-2010-1h__20260818` is **provisional**.

## 11. Critical review

Reviewed 2026-08-22 by working through
[`docs/run-review-checklist.md`](../run-review-checklist.md) against the tree pulled
back from `s3://intervectoriel/test/pypsa_raw_results/20260818_times-pypsa_scen_demande_haute/`
(2.2 GB, 1206 objects). Reproduce the mechanical half with:

```bash
python scripts/walloon_scripts/review_run.py results/times-pypsa/scen_demande_haute
```

**87 PASS · 39 WARN · 13 FAIL.** Verdict per level:

| Level | Verdict |
|---|---|
| 0 provenance | **pass with caveats** — pre-merge config, see R0 |
| 1 solve | pass — see §7; `Crossover 0` caveat below |
| 2 TIMES soft link | **fail** on EV (R5); everything else ≤0.2 % |
| 3 accounting identities | pass — every bus balances to <1e-4 TWh |
| 4 constraint compliance | **fail** — R1, R2, R3, R4, R8 |
| 5 realism | **pass with caveats** — R7, R10 |
| 6 prices / costs | pass with reporting caveats — R11 |
| 7 TIMES consistency | pass — nuclear trajectory exact, demands tight |
| 8 robustness | **fail** — R12 |

### R0 — This is not a run of the current model

`905a3da0` + working-tree `resolution_sector: 1h` predates the 2026-08-21 merge
(`8b5a7135`) and in particular predates:

- `aafa0445` "Stop over-ageing the inherited heat-pump stock" → the effective
  config has **no `existing_capacities.heat_stock_age_profile`** (→ R6);
- `097c98e9`/`3060538a` → **no `bev_natural_charging_split`, no `local_bev_dsm`**;
  `sector.bev_dsm_availability` is the PyPSA-Eur default scalar `0.5` (→ R5);
- the `times-pypsa` → `walloon` prefix rename.

Everything else in level 0 passes: the four per-horizon config snapshots differ
only in `planning_horizons`, and snapshots year = cutout year = 2010.

Two solve caveats that apply to every number below: `Crossover 0` returns an
interior point, so individual capacities and duals carry solver-tolerance noise
(a ~1 % difference between runs is not signal); and Gurobi warns
`Model contains large bounds` (range to 5e10) / `large rhs` (to 1e9) in every
horizon. `lv_limit` is not binding in any horizon (μ = 0).

### R1 — Aggregate capacity maxima cap only the new tranche, so they reset every horizon

`scripts/solve_network.py::add_CCL_constraints`, `include_existing: true` branch:
`rhs_max` for **generators** is never reduced by `rhs_cst` (existing capacity),
although the `min` branch and the *link* `max` branch both are. Under myopic
foresight, previously built capacity is non-extendable at the next horizon, so a
`max` written for the total becomes "up to `max` of *new* capacity per horizon".

Belgian offshore wind, cap 8 000 MW from 2030:

| | 2025 | 2030 | 2040 | 2050 |
|---|---|---|---|---|
| BE `offwind-all` total, MW | 2 300 | **10 300** | **15 262** | **21 196** |
| of which extendable | 38 | **8 000** ← exactly the cap | 5 158 | **8 000** ← exactly the cap |
| cap (`agg_p_nom_minmax_demande_haute.csv`) | 2 300 | 8 000 | 8 000 | 8 000 |

The extendable tranche sitting *exactly* on the cap in 2030 and 2050 is the
signature. Belgium ends with **21.2 GW of offshore wind** — against 2.26 GW
installed, a national 2030 target of 5.8 GW, and a Princess Elisabeth zone sized
at 3.15–3.5 GW. There is no Belgian sea area for it. Offshore wind supplies
61.8 TWh (2040) and ~85 TWh (2050) of Belgian electricity in this run, so this
single defect drives the whole Belgian generation mix.

Failing the same check for a different reason (the pin simply was not met):
`BE solar-all` 2025 min = max = 12 600 MW → **13 626 MW**; `BEWAL solar-all` 2025
min = max = 3 887 MW → **4 089 MW**.

*Fix:* subtract `rhs_cst` from `rhs_max` in the generator branch, mirroring the
link branch; add a regression test asserting `p_nom_opt.sum() <= max` per
`(region, carrier, horizon)`.

### R2 — The Walloon onshore-wind potential is exceeded by 2.2×

`data/walloon/custom_potentials.csv` sets `BEWAL onwind p_nom_max = 6 500 MW`
for every horizon (PNEC wallon + EDORA: 2 700 MW for the 6.2 TWh WAM objective +
3.8 GW additional potential to 2050).

| | 2025 | 2030 | 2040 | 2050 |
|---|---|---|---|---|
| BEWAL `onwind`, MW | **6 784** | **8 660** | **8 744** | **14 039** |
| of which extendable | 5 080 | 1 886 | 573 | **6 500** ← exactly the cap |
| `p_nom_max` | 6 500 | 6 500 | 6 500 | 6 500 |

Same mechanism as R1, this time through the per-vintage `p_nom_max` rather than
the CCL constraint. 14 GW in Wallonia is ~4 700 turbines of 3 MW against ~1.4 GW
installed today, and the model's own reference document caps the technical
potential at 6.5 GW. Implied build rates **+375 MW/yr** (2025→2030) and
**+530 MW/yr** (2040→2050) against Walloon historical additions of ~100–150 MW/yr.

*Fix:* reduce the extendable generator's `p_nom_max` by inherited capacity in
`add_brownfield`, or express the potential as an `agg_p_nom_minmax` row once R1
is fixed.

### R3 — Walloon CCGT floor is re-imposed at every horizon

`custom_potentials.csv` sets `BEWAL CCGT p_nom_min = 1 740 MW_el`. In all four
horizons the *extendable* tranche is exactly 1 740 MW_e, so 1 740 MW_e of **new**
CCGT is forced at each step on top of what already exists:

| BEWAL CCGT (MW_e) | 2025 | 2030 | 2040 | 2050 |
|---|---|---|---|---|
| total | 3 392 | 5 132 | **6 060** | 5 640 |
| forced new | 1 740 | 1 740 | 1 740 | 1 740 |

Wallonia's actual gas fleet is ~0.9–1.0 GW_e (Amercoeur + Seraing). The model has
6.1 GW_e in 2040, running at 1 000–1 150 full-load hours — a peaker fleet that
exists mostly because the floor forces it. +600 MW/yr of new Walloon CCGT over
2025–2030 corresponds to no announced project.

Same shape, benign here: the `battery p_nom_min` floors (BEWAL 286/410 MW) bind
exactly in 2025 and 2030.

*Decide:* was 1 740 MW_e a floor on the *total* Walloon gas fleet or on new build?
Either way it should be applied once — and 1 740 MW_e is itself ~1.8× the existing
fleet, with no source recorded in the CSV.

### R4 — `GB, offwind-all` 2040 minimum is a 10× typo, and it binds

`agg_p_nom_minmax_demande_haute.csv`, row `GB, offwind-all`, `min` series:

```
2025: 0   2030: 5 246   2035: 7 431.5   2040: 96 158   2045: 9 651   2050: 9 651
```

96 158 between 7 431 and 9 651 is a decimal shift of 9 615.8. **The 2040 result is
exactly 96 158 MW** — it binds, because 2040 is a planning horizon. GB then carries
133 671 MW into 2050. That distorts the 2040/2050 North-Sea price signal and
therefore Belgian imports (BE net import from GB peaks at 9.3 TWh in 2040).

The same shift appears in `NL, offwind-all` at 2035 (33 543 vs ~3 354) and 2045
(50 543 vs ~5 054); those land on non-horizons and are harmless *in this scenario
only*.

### R5 — Walloon EV grid draw is 5.56 % above the TIMES `electricity road` figure

Every horizon, exactly +5.56 %: the documented "charger loss counted on the
flexible branch only" symptom ([`ev-charging-softlink.md`](../ev-charging-softlink.md) §3).

| | 2025 | 2030 | 2040 | 2050 |
|---|---|---|---|---|
| PyPSA grid draw, TWh | 0.985 | 3.581 | 11.716 | 17.702 |
| TIMES `electricity road`, TWh | 0.934 | 3.393 | 11.099 | 16.770 |
| error | +0.051 | +0.188 | +0.617 | **+0.932** |

Maximum possible error, because this run uses `bev_dsm_availability: 0.5` (50/50
split). Fixed on HEAD; recorded so the published 2050 Walloon electricity demand
is known to be ~0.9 TWh too high.

**Everything else in the soft link is tight.** Industry electricity, methane,
naphtha, solid biomass, kerosene and road oil all match TIMES to ≤0.2 %, and total
BEWAL electric demand matches to −0.05 / −0.22 / −0.34 / −0.41 %. One exception to
investigate: **`coal for industry` is +8.4 % (2025) and +12.5 % (2030)** above
TIMES `coal` + `coke` (4.018 vs 3.706; 3.845 vs 3.417); 2040 and 2050 match.
Possibly a coke-oven conversion factor applied only in the early years.

Heat-profile fidelity was already checked in §10 and is fine (2040's 0.46 TWh_th
biomass-boiler relaxation is the known CO₂-cap vs TIMES biomass floor).

### R6 — Heat-pump capacity falls 2025 → 2030

1 398 → 1 315 MW at BEWAL (`urban decentral air heat pump` 936 → 685 MW). Exactly
the failure mode in [`heat-softlink.md`](../heat-softlink.md) §5, consistent with
`heat_stock_age_profile` being absent from this vintage's config (R0). Fixed on
HEAD by `aafa0445`. The heat side is otherwise healthy: effective COP 2.40–2.53,
heat delivered rising monotonically.

### R7 — The 2025 horizon is a decarbonised counterfactual, not the observed system

2025 is a planning horizon like any other, and its per-country CO₂ caps bind hard
— BEWAL μ = −339 EUR/t, BEVLG −356, FR −340, NL −337, while the system-wide
`CO2Limit` is slack. The model builds its way to a 2025 that does not exist:

| 2025 | model | observed order of magnitude |
|---|---|---|
| BE onshore wind | 11.8 GW | ~3.5 GW |
| BE VRE generation | 51 TWh | ~21 TWh |
| BE gas-fired generation | 7.4 TWh | ~20 TWh |
| BE heat-pump electricity | 14.4 TWh | ~1–2 TWh |
| BEWAL onshore wind | 6.8 GW | ~1.4 GW |
| BE nuclear generation | 31.5 TWh | ~34 TWh ✓ |
| BE offshore wind | 2.3 GW | 2.26 GW ✓ |
| BE PV | 13.6 GW | ~11.6 GWp |

The two rows that match are the two pinned by a constraint. **No 2025 chart from
this run should be presented as "today".**

### R8 — Interconnection capacity does not reproduce `ntc_<year>.csv`

`set_NTCs.py` writes the NTC into `s_nom`/`p_nom`, but AC lines then carry
`s_max_pu = 0.7` while DC links do not:

| border | NTC file | network nominal | usable | usable / NTC |
|---|---|---|---|---|
| BE–DE (ALEGrO) 2025 | 1 000 | 1 000 | 1 000 | 100 % |
| BE–FR 2025 | 4 000 | 4 150 | 2 905 | 73 % |
| **BE–GB (Nemo) 2025** | **1 000** | **1 700** | **1 700** | **170 %** |
| BE–LU 2025 | 300 | 240 | 168 | 56 % |
| BE–NL 2025 | 3 400 | 3 400 | 2 380 | 70 % |
| BE–FR 2050 | 6 000 | 5 150 | 3 605 | 60 % |
| BE–NL 2050 | 6 000 | 4 700 | 3 290 | 55 % |
| BE–LU 2050 | 1 000 | 590 | 413 | 41 % |

Two separate problems: AC borders deliver 41–73 % of their stated NTC (worst in
2050, where the NTC file grows and the network does not), and Nemo Link is
modelled at **1 700 MW against its real and file rating of 1 000 MW**, rising to
2 400 MW in 2040/2050 — the model imports a net 7.5 TWh from GB across it in 2025.

Flows themselves look sound: no line exceeds its limit, ALEGrO saturates in both
directions, and Belgium is a net importer of 13.9 / 10.0 / 10.3 / 7.8 TWh.

*Decide:* should `ntc_<year>.csv` be the *usable* capacity (divide by `s_max_pu`
when writing `s_nom`) or the thermal rating? Then make `set_NTCs.py` hit it, and
handle DC links explicitly (split into forward + `-reversed`, so `p_nom` must not
be summed).

### R9 — Both the global and the national CO₂ caps bind, so the carbon price is their sum

The per-country caps sum to *exactly* the system `CO2Limit` in 2030, 2040 and
2050. Both bind, so the effective marginal abatement cost in Wallonia is
`|μ(CO2Limit)| + |μ(BEWAL)|`:

| | 2025 | 2030 | 2040 | 2050 |
|---|---|---|---|---|
| global μ, EUR/t | 0 | 197 | 205 | 493 |
| BEWAL μ, EUR/t | 339 | 421 | 176 | 81 |
| **effective, EUR/t** | **339** | **618** | **380** | **573** |

Non-monotonic and far above any plausible ETS path. Whether the redundant global
cap is intended or accidental, it must be stated: every technology choice in this
run is made against a ~600 EUR/t carbon price in 2030.

Related duals: `co2_sequestration_limit` binds in every horizon (so all CCS/DAC
volumes restate the cap, not economics), and the European `biomass limit` binds at
**−230 EUR/MWh in 2050**, which is what pushes biomass out of Wallonia (R10).

### R10 — Structural results that are probably artefacts

Not bugs; results that would mislead if published without the caveat.

**Wallonia becomes a synthetic-fuel hub on imported hydrogen.** BEWAL H₂ balance:

| TWh | 2025 | 2030 | 2040 | 2050 |
|---|---|---|---|---|
| H₂ imported by pipeline | 0.04 | 0.07 | 17.17 | 22.04 |
| H₂ re-exported | 0.01 | 0.05 | 16.49 | 7.20 |
| H₂ → Fischer-Tropsch | 0.00 | 0.00 | 0.00 | **13.72** |
| H₂ electrolysis in BEWAL | 0.00 | 0.00 | 0.00 | **0.00** |

6.8 GW of H₂ pipeline and 1.9 GW of Fischer-Tropsch with *zero* Walloon
electrolysis — and not robust (R12).

**The Walloon district-heating system in 2050 mostly feeds direct air capture.**
DH share of Walloon heat rises 1.6 % → 11.6 % (TIMES-driven, so a scenario
assumption), but the heat goes 2.69 TWh_th to buildings and **6.14 TWh_th to DAC**,
which also draws 2.41 TWh_e and captures **4.39 Mt CO₂ — 2.6× the entire Walloon
2050 CO₂ cap of 1.72 Mt**. That is why BEWAL builds 966 MW of urban-central heat
pumps, 1.6 GW of urban resistive heaters and a 4.6 GW water-pit charger.

**Walloon domestic biomass is unused in 2050 while 6 TWh of pellets are imported.**
`gen:solid biomass` at BEWAL = 0.0 TWh in 2050 (9.0 TWh of `e_sum_max` available at
17.3 EUR/MWh) while `solid biomass import` delivers 6.0 TWh — domestic biomass
counts against the binding European `biomass limit` and imports do not. Legitimate
optimisation, terrible headline.

**Imported biomass is specified twice** in `custom_potentials.csv` — `solid biomass
import e_nom` (4/4/4.5/6 TWh) and `solid biomass transported e_sum_max`
(2/2/2.25/3 TWh), both described as "pellets imported for Wallonia". The run uses
both, so 2040 imports total 6.75 TWh against a documented Valbiom potential of
2.25 TWh. Confirm which is the intended cap.

**All Walloon PV migrates to `solar-hsat`.** Fixed-tilt `solar` 4 088 → 1 MW,
`solar-hsat` 0 → 11 292 MW, `solar rooftop` ≈ 0 in every horizon, although Walloon
PV is overwhelmingly residential rooftop today. Report *total* PV; the split is a
cost-ranking artefact and +917 MW/yr of tracking PV over 2025–2030 is not a
deployment forecast.

**In 2025 the European `biomass limit` is `<= 0`** — sustainable solid biomass is
banned Europe-wide and all 6 TWh of Walloon biomass use is booked as
"unsustainable" against a forced equality of 365.9 TWh system-wide.

### R11 — Reporting traps in the summary CSVs

- **`nodal_capacities.csv` / `nodal_costs.csv` attribute conversion links by
  `bus0`.** `nuclear` links have `bus0` on the EU uranium bus, so **Walloon nuclear
  appears nowhere in BEWAL's rows** — neither the 1 992 MW_e of 2025 capacity nor
  its 1 743 MEUR/yr of annualised capital. Recompute from the network on `bus1`
  (as §7 above does).
- **Heat pumps are reversed links** (`bus0` = heat bus, `bus1` = electricity,
  `efficiency = 1/COP`, `p ∈ [−p_nom, 0]`; `prepare_sector_network.py:3728`). Their
  `p_nom_opt` is **MW_th, not MW_el**, and any hand-written balance assuming
  `bus0` = electricity will silently drop or mis-sign them. `nodal_energy_balance.csv`
  handles them correctly.
- **`costs.csv` includes non-extendable capital**, the objective does not — hence
  `metrics.csv → total costs` ≈ 5.7e11 vs the §7 objectives ≈ 3.6e11. Existing
  Tihange units are annuitised at full new-build cost (~875 EUR/kW_e/yr); the
  10-year LTO retrofit is correctly priced lower (285 EUR/kW_e/yr).
- **Vintage labels are wrong for late-horizon nuclear.** The ~2 GW_e of new Walloon
  nuclear built at 2050 is the component `BEWAL nuclear-2025` with
  `build_year = 2025`. Do not group by `build_year`.
- **Zero-capital-cost capacities are degenerate**: `urban central water pits
  charger` (4 604 MW), `V2G`, `BEV charger`, `gas pipeline`, all chargers /
  dischargers. Not results; do not plot.

### R12 — Robustness across run vintages

BEWAL capacity, MW, same scenario:

| 2025 | this run (1h) | local `times-pypsa` | local `walloon-model` |
|---|---|---|---|
| onwind | **6 784** | **2 359** | **2 349** |
| CCGT (link `p_nom`) | 5 951 | 5 951 | 2 898 |
| battery charger | 286 | 0 | 0 |

| 2050 | this run (1h) | local `times-pypsa` | local `walloon-model` |
|---|---|---|---|
| onwind | 14 039 | 9 714 | 2 423 |
| solar-hsat | 11 292 | 8 931 | 0 |
| H2 pipeline | 6 841 | 1 628 | 3 204 |
| Fischer-Tropsch | **1 872** | **1** | **96** |
| urban central water pits charger | 4 604 | 8 169 | 5 935 |

The 2025 Walloon onshore-wind result moves by **2.9×** between vintages. Some of
that is the battery/nuclear changes in `905a3da0` and some is temporal resolution,
but a base-year capacity has no business moving by 3× — diagnose before publishing.
`Fischer-Tropsch` and `H2 pipeline` are not stable enough to report at all.

### What passed cleanly

- **All accounting identities.** Every BEWAL bus (`AC`, `low voltage`, `H2`, `gas`,
  `solid biomass`, `biogas`, all three heat buses) and the Belgium-wide AC + LV
  balance close to <1e-4 TWh on 40–450 TWh of gross flow (36/36 balances).
- **Annual-energy potentials respected**: Walloon biogas exactly 8.300 TWh from
  2030 (its full potential, every year), solid biomass within `e_sum_max`.
- **Capacity factors all plausible**: BEWAL onshore wind 23–26 %, PV 10.5–12.9 %,
  run-of-river 26 %, BE offshore 46 %, nuclear 70–92 %, heat pumps COP 2.4–2.5.
- **Nuclear follows the intended trajectory** — see §7; matches
  [`nuclear-alignment-20260816.md`](../nuclear-alignment-20260816.md) exactly.
- **Curtailment sane**: Walloon onshore wind 0.5 / 12.2 / 7.2 / 5.3 %.
- **Prices**: BEWAL mean 92–113 EUR/MWh, no negative hours, no scarcity spikes
  above 430 EUR/MWh — consistent with a capacity-rich, CO₂-constrained system.

### Review follow-ups

| # | Action | Owner |
|---|---|---|
| 1 | Fix `rhs_max` for generators in `add_CCL_constraints` (R1) + regression test | code |
| 2 | Make the Walloon `p_nom_max` apply across vintages (R2) | code |
| 3 | Decide and fix the `BEWAL CCGT p_nom_min` semantics; record its source (R3) | modeller |
| 4 | Correct the `GB`/`NL` `offwind-all` typos in `agg_p_nom_minmax_*.csv` (R4) | data |
| 5 | Decide the NTC convention, make `set_NTCs.py` reproduce it, fix Nemo at 1 000 MW (R8) | modeller + code |
| 6 | Resolve the duplicated imported-biomass potential (R10) | data |
| 7 | Investigate `coal for industry` +8 %/+12 % in 2025/2030 (R5) | code |
| 8 | Diagnose the 2.9× swing in BEWAL 2025 onshore wind between vintages (R12) | modeller |
| 9 | Decide whether the redundant global CO₂ cap should be removed (R9) | modeller |
| 10 | Re-run and re-publish from HEAD, then re-run this checklist | ops |
| 11 | Until then, treat the Explorer scenario `times-pypsa__demande-haute-2010-1h__20260818` as **provisional** | ops |
