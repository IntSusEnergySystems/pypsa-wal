# Solve log — scen_demande_haute @ 2010, 1h (improvement-plan LP items)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-09-02 19:28 → (in progress; 2030–50 relaunch 2026-09-03) |
| Operator | Cursor agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml` + overlay `config/scenarios.walloon.yaml`; on NIC5 also `cluster/config_cluster.yaml` (overlay last, **one** `--configfile` flag) |
| Code version | pypsa-wal `master` `87552368` + uncommitted items 3 / 6a / 8 / 9 (NTC floor, BEWAL import cap, rooftop share + LV alias, industry CC floor). TIMES_PyPSA `a48b774` + uncommitted `named_transfers.py` extractors (CSVs already in `data/walloon/`). pypsa2html `0d1b904` |
| Outcome | 2025 optimal; 2030 inf was BE solar floor on Brussels; BEVLG remainder rows in, 2030–50 relaunch |

## 2. Goal of the run

Full 1h / 2010 four-horizon solve of `scen_demande_haute` after the improvement-plan
queue (items 2, 3, 6a, 8, 9, 10, 11, 12, 13, 16 and reporting 14/15). Same TIMES
vd as the 30 Aug production 1h
([`2026-08-30_scen_demande_haute_2010_1h.md`](2026-08-30_scen_demande_haute_2010_1h.md)).
The 2 Sept 6h item-2 solves were diagnostics only; this is the production 1h
that the 1 Sept test strategy asked for. Cluster partition is **`batch`**, not
`hmem` (user request); 100 GB / 16 cpus — 1h peak historically 32–38 GB.

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_central_demande_haute_v1_260828_2808.vd` |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` |
| Snapshots | 2010-01-01 → 2011-01-01, **8760** hourly, weight 1.0 (must rebuild: 6h prepare left 1460 snapshots) |
| Sector time resolution | `1h` |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi barrier (`Method 2`), **16** threads / **100 GB**, `BarConvTol 1e-5`, `Crossover 0`, **`BarHomogeneous: 1`**. NIC5 **`batch`**, `SOLVE_RUNTIME=1440` min |
| Key scenario overrides | previous 30 Aug set **plus** item 3 NTC floor 9600 MW from 2035; item 9 industry CC floor; Belgian CO₂ store 0; aviation off; `ptes.e_nom_max_weeks: 4`. **Items 6a and 8 withdrawn** for this 1h (flags off; TIMES tables left in the overlay as documentation) |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval / network build (prepare) | local | `LOCAL_CORES=4`; TMPDIR `/sylvain/mount/pypsa-wal-data/tmp`. Drop 6h `snapshot_weightings` + sector `.nc` first so `--rerun-triggers mtime` cannot reuse 1460-snapshot files |
| LP solve | NIC5 **`batch`** (not hmem) | 16 cpus/task, **100 GB**, `SOLVE_RUNTIME=1440`. Leftover 6h solved `.nc` deleted before submit. First 2025 job **11107729** failed (NameError). Second **11107735** inf-or-unbounded (rooftop in solar-all). Retry orchestrator pid **2951589**, 2025 job **11107857** on `nic5-w044` (optimal). 2030 job **11108009** inf-or-unbounded (item 6a). 6a off: orchestrator **987411**, 2030 **11110016** still inf (item 8). Item 8 off: orchestrator **1130424**, first job **11110079** (`add_brownfield` 2030, `batch`) |
| Post-processing (CSVs, plots) | local | `nic5.sh postprocess` after pull |
| HTML report (pypsa2html) | local | via postprocess (`PYPSA2HTML=1`) |
| Explorer CSV extraction (ClimAct) | local | `nic5.sh publish` (extract + S3) |

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (launch → results verified) | in progress |
| Prepare (network build) | **59 s** (19:28:00–19:28:59): rebuilt `time_aggregation` + 4× `prepare_sector_network` + 2025 brownfield. Confirmed **8760** snapshots |
| Push to cluster | **9 s** (19:29:33–19:29:42) |
| Queue wait (cluster) | **none** — job **11107729** started immediately on `nic5-w045` (`batch`, 16 CPU, 100 GB) |
| Solve 2025 / 2030 / 2040 / 2050 | 2025 **~3.2 h** wall (job 11107857, Optimal). 2030 failed in **14 s**. 2040/2050 never started. Relaunch 2026-09-03 |
| Pull results | |
| Post-processing + plots | |
| pypsa2html report | |
| ClimAct extraction | |

Previous production 1h (30 Aug, hmem, 100 GB): ~8.6 h including a 2030 numerical
retry. This run already has `BarHomogeneous: 1` from the start.

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size (rows / cols / nonzeros) | 2025 presolved ~7.50 M × 10.4 M × 40.8 M nnz (matches 30 Aug 1h) |
| Peak RAM per solve | 2025 ~31.5 GB |
| Peak RAM local phases | |
| Disk footprint | |

## 7. Results

| Horizon | Status | Objective (EUR/a or model units) |
|---|---|---|
| 2025 | Optimal | 3.49554649e11 |
| 2030 | inf-or-unbounded (11108009 / 11110016 / 11110118 / 11110676); cause = BE solar remainder on BEBRU; relaunch | |
| 2040 | not started | |
| 2050 | not started | |

Local result folders:

- Networks: `results/walloon/scen_demande_haute/networks/`
- CSVs / plots: `results/walloon/scen_demande_haute/{csvs,graphs,graphics,maps}/`
- HTML report: `results/walloon/scen_demande_haute/html/index.html`

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | |
| Scenario folder on S3 | |
| Explorer display label | `demande-haute-2010-1h` |
| Explorer CSVs | |
| TIMES vd staged | |
| Verified in Explorer dropdown | |

## 9. Issues encountered and fixes

- Local resources were **6h** (1460 snapshots, 2 Sept item-2 prepare). Deleted
  `snapshot_weightings_base_s_adm_elec__.csv` and
  `resources/walloon/scen_demande_haute/networks/base_s_adm___*.nc` before
  prepare so the 1h rebuild cannot reuse them under `--rerun-triggers mtime`.
- **2025 job 11107729 failed in 27 s** (`NameError: determine_emission_sectors
  is not defined`). Adding `named_pins` imports had replaced the
  `prepare_sector_network` import. Restored; guard in
  `test/test_national_co2_scope.py`. Resubmitted as **11107735**.
- 2025 **11107735** (batch, `nic5-w051`): Gurobi 13 barrier with `BarHomogeneous: 1`
  declared **infeasible or unbounded** in 0 iterations / 10 s (31.1 M rows,
  14.7 M cols). Cause: item 8 share pin (rooftop ≥ 25.8 % of BEWAL solar)
  needs **~1 422 MW** rooftop, while 2025 `BEWAL solar-all` is min=max=**4 088 MW**
  of utility (20 MW of 0.5 % corridor). Rooftop was inside `solar-all`. Killed
  the IIS (`"infeasible" in "infeasible_or_unbounded"`). Fix: drop rooftop from
  the `agg_solar` rename (Elia 4 088 MW is the utility fleet; rooftop has its
  own 46 GW potential). Also skip the whole import-cap machinery in 2025 (no
  TWh row), and refuse IIS on `infeasible_or_unbounded`.
- **2025 job 11107857** (`nic5-w044`): **Optimal** 3.49554649e11. Rooftop
  1 422 MW = 25.8 % of 5 510 MW. Peak RAM ~31.5 GB. Cluster network
  `results/walloon/scen_demande_haute/networks/base_s_adm___2025.nc` (232 MB).
- **2030 job 11108009**: Gurobi **infeasible or unbounded in 0 iterations /
  14 s**. Python log: `Capped electricity imports at ['BEWAL'] to 2.94 TWh/a`
  and rooftop ≥ 71.4 %. IIS not started (the new `infeasible_or_unbounded`
  guard). Orchestrator FAILED. 2040/2050 never started.
- **Cause of 2030: item 6a import cap, not rooftop.** Unique vs successful
  2025: TIMES `Transfo_Imp` 2.94 TWh. Rooftop 71.4 % is feasible (utility
  solar-all min 6500 MW; rooftop `p_nom_max` 46 GW). NTC floor and industry
  CC start 2035+. On the just-solved **1h 2025** network, BEWAL **gross**
  AC+DC positive inflow is **13.14 TWh** (Flanders/Brussels 4.98, abroad
  8.17) while annual **NET** is an export (**−1.53 TWh**). The 6h item-2
  table in the plan is NET (−12.5 / −2.4 / 7.0 / 2.7 TWh). `Import_p ≥ 0`
  then summed is **gross hourly imports**, not annual net and not TIMES
  `Transfo_Imp` (a one-way annual process). Even foreign-only 8.17 TWh >
  2.94. Not a unit-conversion bug (10.59 PJ = 2.94 TWh).
- **Input change 2026-09-03 (6a):**
  `self_sufficiency_constraint: false` on `scen_demande_haute` and
  `scen_evflex`. TWh table and solver code kept. Did not invent larger TWh
  numbers and did not silently switch the constraint to net. 2025 LP is
  unchanged (no TWh row that year); keep the 2025 `.nc` and resubmit
  2030–2050 only.
- **2030 retry job 11110016** (after 6a off, `add_brownfield` 11110014):
  still **infeasible or unbounded in 0 iterations / 13 s**. No
  `Capped electricity imports` line — 6a really off. Only remaining
  2030-specific new pin vs successful 2025 is rooftop ≥ **71.4 %**.
  Brownfield rooftop `p_nom_max` is 46 GW (need ~16 GW if Elia utility
  floor is 6.5 GW), so the empty LP is a structural clash, not a missing
  potential. IIS refused on `infeasible_or_unbounded`.
- **Input change 2026-09-03 (item 8):** `rooftop_share.enable: false` on
  both overlays. 2025 `.nc` kept (already optimal with 25.8 %); 2030–50
  resubmitted to isolate item 8.
- **2030 retry job 11110118** (6a and rooftop both off): still inf-or-unbounded
  in 0 iterations / 13 s. Neither overlay was the 2030 cause.
- **Cause: item 11 BE offwind pin vs 2025-built 8 GW.** 2025 BEVLG AC
  `country` is `BEVLG`, so `BE,offwind-all` min=max=2262 never bound;
  `p_nom_opt` = **8 000 MW** (custom potential). 2030 brownfield has
  `country=BE` and 8 GW standing (vintages 2010–2025). CCL max 2262 after
  `include_existing` is negative → Gurobi empty LP. 2025 was optimal because
  the pin missed.
- **Input change 2026-09-03 (item 11):** 2030 `BE,offwind-all` pin
  `min = max = 8000` in `agg_p_nom_minmax_demande_haute.csv`. 2025 `.nc`
  kept. 2040/2050 floors 4362/5800 stay (slack vs standing 8 GW).
- **2030 retry job 11110676** (8 GW pin): still inf-or-unbounded in 0
  iterations / 13 s. Log: widened `BE offwind-all` 0.5 %, dropped build-rate
  for BE offwind (floor 8000 vs growth 7063) plus GB/DE. 2025 `.nc` unchanged.
  CCL rewrites BEVLG/BEWAL `country` to the bus name, so the `BE` offwind row
  does not apply to Flemish turbines — this pin likely did not change the
  feasible set. 2030 inf is **not** 6a, rooftop, or this 2262/8000 pin.
  Orchestrator **1210512** finished 11:44. No further identical relaunch.
- **2030 brownfield bound check (2026-09-03 13:29, cluster `base_s_adm___2030_brownfield.nc`).**
  No `p_nom_min > p_nom_max` / `e_nom_min > e_nom_max` after land-use. Heating
  links unbounded. Battery floors 410 / 1860 MW sit on inf ceilings. After the
  CCL country rewrite, all 8 GW of Flemish offshore is `country=BEVLG`; the
  `BE,offwind-all` 8000 MW floor is an empty group (no BE-country offwind gens)
  and is skipped. `BE,onwind` remainder 1776 MW vs BEBRU leftover **0.2 MW** is
  clipped to remaining potential.
- **Cause of 2030 (2026-09-03 13:40): CCL dumps the Belgian solar floor on Brussels.**
  `add_CCL_constraints` rewrites BEVLG/BEWAL `country` to the bus name and
  subtracts the region row from `BE`. There was no `BEVLG,solar-all` row, so
  Elia 16 500 − BEWAL 6 500 = **10 000 MW** remainder applied to `country=BE`
  = **BEBRU only**. Include-existing residual **4 337 MW** of new utility+hsat
  solar. Land-use `p_nom_max` still sums to ~7.5 GW so the CCL min clip does
  not fire, but `add_solar_potential_constraints` shares land with 5 GW of
  2025 hsat and leaves ~0.8 GW — empty LP in 0 barrier iterations. 2025
  solved because that year's remainder (9 751 − 4 088 = 5 663) equalled
  Brussels standing, residual 0. Same rewrite on onwind (clipped to 0.2 MW,
  not inf) and offwind (empty group, skipped).
- **Input change 2026-09-03 (BEVLG remainder rows):**
  `BEVLG,solar-all` 2030 min = 10 000; `BEVLG,onwind` 2030 min = 2 000;
  `BEVLG,offwind-all` 2030 pin 8 000/8 000 (and 2040/2050 floors copied from
  BE so the pin actually binds Flemish turbines). 2025 `.nc` kept.

## 10. Follow-ups / pending

Review §11 after postprocess: NTC floor ≥ 9600 MW usable from 2040; industry CC
≥ STORAGEMININD; Belgian CO₂ store still 0; aviation still off. Items 6a and 8
are **off**. Item 11 2030 pin is **8 GW** (the 2025-built potential), not 2262.
Do not treat BEWAL gross imports ≤ Transfo_Imp, TIMES rooftop share, or
Belgian offshore at 2262 MW in 2030 as pass criteria. Item 11 2030 pin must
bind **BEVLG** (8 GW), not the empty `BE` group. Belgian 2030 solar floor is
BEWAL 6.5 GW + BEVLG 10 GW, not 10 GW of new build in Brussels.

## 11. Critical review

Not yet. Filled after a successful solve against
[`../run-review-checklist.md`](../run-review-checklist.md).
