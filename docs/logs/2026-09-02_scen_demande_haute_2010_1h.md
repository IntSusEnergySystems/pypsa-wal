# Solve log — scen_demande_haute @ 2010, 1h (improvement-plan LP items)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-09-02 19:28 → 2026-09-03 22:06 (4/4 optimal), reviewed + published 2026-09-03 evening |
| Operator | Cursor agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml` + overlay `config/scenarios.walloon.yaml`; on NIC5 also `cluster/config_cluster.yaml` (overlay last, **one** `--configfile` flag) |
| Code version | pypsa-wal `master` `87552368` + uncommitted items 3 / 6a / 8 / 9 (NTC floor, BEWAL import cap, rooftop share + LV alias, industry CC floor). TIMES_PyPSA `a48b774` + uncommitted `named_transfers.py` extractors (CSVs already in `data/walloon/`). pypsa2html `0d1b904` |
| Outcome | **4/4 optimal** (349.6 / 356.2 / 285.6 / 268.2 bn). §11 review done: publishable for Walloon results with the 2025-rooftop caveat (F1); 2025-only and cross-vintage claims blocked until re-run |

## 2. Goal of the run

Full 1h / 2010 four-horizon solve of `scen_demande_haute` after the improvement-plan
queue (items 2, 3, 6a, 8, 9, 10, 11, 12, 13, 16 and reporting 14/15). Same TIMES
vd as the 30 Aug production 1h
([`2026-08-30_scen_demande_haute_2010_1h.md`](2026-08-30_scen_demande_haute_2010_1h.md)).
The 2 Sept 6h item-2 solves were diagnostics only; this is the production 1h
that the 1 Sept test strategy asked for. Cluster partition started on **`batch`**
(user request); 100 GB / 16 cpus — 1h peak historically 32–38 GB. **Switched to
`hmem` 2026-09-03 17:27** after the 2040 solve sat 2 h in `batch` PENDING
(Priority, Slurm ETA next day); same 100 GB / 16 cpus request (shares a mixed
hmem node).

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
| Solver + options | Gurobi barrier (`Method 2`), **16** threads / **100 GB**, `BarConvTol 1e-5`, `Crossover 0`, **`BarHomogeneous: 1`**. NIC5 `batch` → **`hmem` from 17:27 09-03**, `SOLVE_RUNTIME=1440` min |
| Key scenario overrides | previous 30 Aug set **plus** item 3 NTC floor 9600 MW from 2035; item 9 industry CC floor; Belgian CO₂ store 0; aviation off; `ptes.e_nom_max_weeks: 4`. **Items 6a and 8 withdrawn** for this 1h (flags off; TIMES tables left in the overlay as documentation) |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval / network build (prepare) | local | `LOCAL_CORES=4`; TMPDIR `/sylvain/mount/pypsa-wal-data/tmp`. Drop 6h `snapshot_weightings` + sector `.nc` first so `--rerun-triggers mtime` cannot reuse 1460-snapshot files |
| LP solve | NIC5 **`batch`** (not hmem) | 16 cpus/task, **100 GB**, `SOLVE_RUNTIME=1440`. Leftover 6h solved `.nc` deleted before submit. First 2025 job **11107729** failed (NameError). Second **11107735** inf-or-unbounded (rooftop in solar-all). Retry orchestrator pid **2951589**, 2025 job **11107857** on `nic5-w044` (optimal). 2030 job **11108009** inf-or-unbounded (item 6a). 6a off: orchestrator **987411**, 2030 **11110016** still inf (item 8). Item 8 off: orchestrator **1130424**, first job **11110079** (`add_brownfield` 2030, `batch`). **Relaunch 2026-09-03 13:43** (BEVLG remainder rows): orchestrator pid **1751807**, `add_brownfield` 2030 **11111821**, solve 2030 **11111832** (optimal), `add_brownfield` 2040 **11113559**, solve 2040 **11113578** — batch pending 2 h → **partition switch to `hmem` 17:27**: orchestrator pid **2550037**, solve 2040 **11114388** (infeasible after 79 barrier it — item 9, §9). **Item 9 off, relaunch 18:14**: orchestrator pid **2720176**, solve 2040 **11114459** (running, `nic5-w071`); 2050 chain follows |
| Post-processing (CSVs, plots) | local | `nic5.sh postprocess` after pull |
| HTML report (pypsa2html) | local | via postprocess (`PYPSA2HTML=1`) |
| Explorer CSV extraction (ClimAct) | local | `nic5.sh publish` (extract + S3) |

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (launch → results verified) | Sep 2 19:28 → Sep 3 22:06 solve-complete (≈27 h including 4 failed 2030 attempts, 2 h batch queue loss, the 2040 item-9 infeasibility + relaunch); postprocess + extraction + review the same evening. Pure solve time 2025 3.2 h + 2030 1.6 h + 2040 1.8 h + 2050 1.9 h ≈ **8.5 h** |
| Prepare (network build) | **59 s** (19:28:00–19:28:59): rebuilt `time_aggregation` + 4× `prepare_sector_network` + 2025 brownfield. Confirmed **8760** snapshots |
| Push to cluster | **9 s** (19:29:33–19:29:42) |
| Queue wait (cluster) | **none** — job **11107729** started immediately on `nic5-w045` (`batch`, 16 CPU, 100 GB) |
| Solve 2025 / 2030 / 2040 / 2050 | 2025 **~3.2 h** wall (job 11107857, Optimal). 2030: four inf attempts (14 s each, §9), then relaunch solve **11111832** Optimal in **1 h 34 min** (13:45:42 → 15:20:07, `batch`). 2040 `add_brownfield` 52 s; solve **11113578** pending 15:23 → 17:25 on `batch` (~2 h queue loss, Priority) → cancelled, **11114388** on `hmem` 17:31 → 18:01 **infeasible** (79 barrier it, item 9); **11114459** on `hmem` from 18:17 (item 9 off). 2050 follows |
| Pull results | 2 pulls failed rsync verification (see §9 — rsync **delta** path; `--whole-file` fixed); 1.34 GB networks + full tree clean by 22:30 |
| Post-processing + plots | `nic5.sh postprocess` 22:30–22:40 (touch, CSVs, plots, sankey, pypsa2html, S3) |
| pypsa2html report | in postprocess; published → `https://pypsa.squoilin.eu/scen_demande_haute_20260903/` (first rsync went to the legacy `/intervec/` path, which the server has 301'd away since the dedicated `pypsa` vhost of 1 Sept — republished to `/home/pypsa/public_html`; `html_publish` config fixed) |
| ClimAct extraction | 22:52 (re-run; extractor restored — see §9); `nic5.sh upload` 22:55 |

Previous production 1h (30 Aug, hmem, 100 GB): ~8.6 h including a 2030 numerical
retry. This run already has `BarHomogeneous: 1` from the start.

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size (rows / cols / nonzeros) | 2025 presolved ~7.50 M × 10.4 M × 40.8 M nnz (matches 30 Aug 1h) |
| Peak RAM per solve | 2025 ~31.5 GB; 2030 **37.3 GB** (sacct `11111832.0` MaxRSS 37 260 808 KB; memory.log peak 35.7 GB); 2040 attempt-1 39.8 GB |
| Peak RAM local phases | |
| Disk footprint | |

## 7. Results

| Horizon | Status | Objective (EUR/a or model units) |
|---|---|---|
| 2025 | Optimal | 3.49554649e11 |
| 2030 | **Optimal** (relaunch job 11111832, 2026-09-03 15:20) | **3.56171070e11** |
| 2040 | **Optimal** (job 11114459, 2026-09-03 20:03, item 9 off; first attempt 11114388 infeasible — §9) | **2.85619695e11** |
| 2050 | **Optimal** (job 11114523, 2026-09-03 22:06) | **2.68246878e11** |

Local result folders:

- Networks: `results/walloon/scen_demande_haute/networks/`
- CSVs / plots: `results/walloon/scen_demande_haute/{csvs,graphs,graphics,maps}/`
- HTML report: `results/walloon/scen_demande_haute/html/index.html`

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | `s3://intervectoriel/test/pypsa_raw_results/20260903_walloon_scen_demande_haute/` |
| Scenario folder on S3 | `s3://intervectoriel/test/scenarios/times-pypsa__demande-haute-2010-1h__20260903/` (test env) |
| Explorer display label | `demande-haute-2010-1h` |
| Explorer CSVs | 49 pypsa + 3 strategy + `.vd`, extracted 22:52 from this run's networks |
| TIMES vd staged | `scen_central_demande_haute_v1_260828_2808.vd` |
| Verified in Explorer dropdown | not yet (test env; verify before promoting) |

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
- **Relaunch 2026-09-03 13:43 (orchestrator pid 1751807) — 2030 now solves.**
  `add_brownfield` 11111821 (~2 min), solve **11111832 Optimal
  3.56171070e11** in 1 h 34 min, peak 37.3 GB — the CCL-solar-remainder-on-
  BEBRU diagnosis was the 2030 cause. 2040 `add_brownfield` 11113559 (52 s)
  then solve **11113578** submitted 15:23; **pending (Priority)** on `batch`
  (16 CPU / 100 GB; 705 CPUs idle but long higher-priority queue; Slurm ETA
  2026-09-04 ~17:51, pessimistic). 2050 follows in the same orchestrator.
  Note for 2040/2050 review: the BEVLG remainder rows also apply there —
  check the 2040 `solar-all`/`onwind` minima against Brussels/Flemish
  standing capacity before reading capacities.
- **Partition switch to `hmem` 2026-09-03 17:27 (user request, ASAP).** The
  2040 solve (11113578) had sat in `batch` PENDING (Priority) for 2 h with a
  Slurm ETA of 2026-09-04 ~17:51 — 705 CPUs idle but a long higher-priority
  queue; `hmem` had an idle 64-CPU node and its 155-job backlog blocked on
  AssocGrpJobsLimit. `nic5.sh stop` cancelled the job but **did not kill the
  setsid'd orchestrator** (pkill pattern missed it; SIGTERM by pid worked).
  First `hmem` relaunch died on a **stale `.snakemake/locks` LockException**
  from the killed orchestrator (the known rm-locks-once-nothing-runs fix);
  second relaunch (pid 2550037) built a 3-job DAG — 2025/2030 solves and 2040
  brownfield correctly skipped (mtime triggers, no re-push) — and solve 2040
  **11114388** started on `nic5-w071` within 2 min. Same 100 GB / 16 cpus /
  BarHomogeneous settings; `cluster/config_cluster.yaml` untouched.
- **2040 solve 11114388 infeasible after 79 barrier iterations (18:01, 27 min,
  peak 39.8 GB) — cause: item 9 industry-CC floor is structurally
  unsatisfiable.** Not the 0-iteration empty LP of the 2030 saga: the barrier
  actually optimised and concluded "Infeasible model". Static proof on the
  2040 brownfield: the floor constrains captured mass over `process
  emissions CC` (eff2) + `solid biomass for industry CC` (eff3) + `gas for
  industry CC` (eff3) at BEWAL, whose fuel-side outputs land on buses with
  **fixed TIMES-transferred demands** — so maximum capturable = 357 kt
  process × 0.95 + 7.62 TWh biomass × 0.3484 + 5.56 TWh gas × 0.1881 =
  **3 361 kt < 5 077 kt floor**. 2050 likewise: 281.64 × 0.95 + 6.98 × 0.3484
  + 3.85 × 0.1881 = **3 424 kt < 4 826 kt**. TIMES `STORAGEMININD` must be
  fed by capture sources PyPSA does not carry at BEWAL (feedstock gas, SMR
  CC, CCGT-CC, or a larger industry). Items 9 and 12 are inconsistent as a
  pair — exactly the "do 12 first, 9 sits on the wrong inventory" risk.
  Incidental finding: the four **base** networks still carry pre-item-12
  process-emission loads (~2 Mt; `industrial_energy_demand_*.csv` not
  regenerated), but `BEWAL_potentials` re-applies `custom_potentials.csv` per
  year at solve time — verified: solved 2025/2030 carry 4 412 / 3 946 kt, and
  the 2040 brownfield 357 kt. The stale CSVs are cosmetic but should be
  regenerated.
- **Input change 2026-09-03 evening (item 9):** `industry_cc_floor.enable:
  false` on `scen_demande_haute` and `scen_evflex` (same pattern as 6a/8 —
  code, CSV and `test_industry_cc_floor.py` (3 passed) stay; overlay off).
  Did not rescale the floor to the capturable maximum (that would be
  inventing a number). Orchestrator pid **2720176**, solve 2040 **11114459**
  on `hmem`; 2050 solves without the floor too. Review consequence: industry
  capture in 2040/2050 is a PyPSA residual, **not** TIMES-aligned.

## 10. Follow-ups / pending

**§11 review done (2026-09-03)** — verdict and the five findings there,
headlined by F1 (80.2 GW phantom French rooftop in 2025, frozen into the
chain) and F2 (2025 Flanders unconstrained). Re-run needed after the F1/F2
fixes before cross-vintage claims.

Review §11 after postprocess: NTC floor ≥ 9600 MW usable from 2040; Belgian CO₂
store still 0; aviation still off. **Items 6a, 8 and 9 are off.** Industry
capture is a PyPSA residual, not TIMES `STORAGEMININD` (max capturable from the
transferred fuel mix is 3 361 / 3 424 kt in 2040/2050 vs the 5 077 / 4 826 kt
floors — item 9 needs a consistent feed basis before it can pin anything).
Item 11 2030 pin is **8 GW** (the 2025-built potential), not 2262.
Do not treat BEWAL gross imports ≤ Transfo_Imp, TIMES rooftop share, Belgian
offshore at 2262 MW in 2030, or industry CC = STORAGEMININD as pass criteria.
Item 11 2030 pin must bind **BEVLG** (8 GW), not the empty `BE` group. Belgian
2030 solar floor is BEWAL 6.5 GW + BEVLG 10 GW, not 10 GW of new build in
Brussels. Also regenerate `industrial_energy_demand_*.csv` (stale ~2 Mt
process-emission rows; overridden at solve time, cosmetic).

## 11. Critical review

Reviewed 2026-09-03 late evening, against [`../run-review-checklist.md`](../run-review-checklist.md).
`review_run.py`: PASS 144 / INFO 26 / WARN 22 / FAIL 12. All 12 FAILs are
explained below (3 config-diff = the documented mid-run withdrawals; 9 = the
2025 rooftop/BEVLG finding F1).

### 11.0 Provenance — pass

`run.json`: commit `93bdf848` on `development_plan` (merge of master
`788cc75a` cost-CSV updates + `28870714` items 3/6a/8/9 + `87552368` items
10/11/12/13/16; TIMES_PyPSA `a48b774` + uncommitted extractors, now committed
as `3627a53`; pypsa2html `0d1b904` + items 14/15). Weather year 2010 with
matching cutout, `resolution_sector: 1h`, 8 760 snapshots — verified.

The horizon configs differ beyond `planning_horizons` in exactly three keys,
all documented in §9: `rooftop_share.enable` (true for the 2025 solve — it
solved with 25.8 % — false from 2030 on), `industry_cc_floor.enable` (true in
the 2025/2030 snapshots but a **no-op**: no floor row before 2035) and
`self_sufficiency_constraint` (true in 2025, no TWh row that year → no-op).
No solved horizon was affected by a flag that was flipped after it.

### 11.1 Commit intent (level 0b) — pass, one unintended side effect (→ F1)

Previous production log: 30 Aug (`dbca25df`). Commits since:

| Commit | Claimed | Observable in this run | Verdict |
|---|---|---|---|
| `80f3d279` item 2: Belgian CO₂ sink 0, geology ramp | Belgian stores 0, export route via pipelines | 2025 sequestration limit 0 (binding at 429.98); no Belgian `co2 stored` store built; NL/DE/GB geology carries capture | pass |
| `87552368` item 11: offshore retimed | 2030 pin 8 GW standing, 2040/2050 floors 4 362/5 800 | 2030 BE **and** BEVLG offwind = 8 000 (pin); 2040/2050 floors slack vs standing | pass |
| `87552368` item 10: Flanders nuclear | BEVLG 1 000 (2040) / 3 000 (2050), BE raised first | 2040 BE 2 030 = BEWAL 1 030 + BEVLG 1 000; 2050 BE 6 000 = 3 000 + 3 000 (MW_e) | pass |
| `87552368` item 12: process-emissions load | VAR_Comnet 4 412 / 3 946 / 357 / 282 kt | Solved networks carry exactly those loads (verified on all four `.nc`) | pass |
| `87552368` item 13: aviation toggle off | National cap excludes aviation both sides | `co2_budget_national_include_aviation: false` in all four config snapshots | pass |
| `87552368` item 16: water pits ≤ 4 weeks | e_nom_max bounded | 2050 charger/discharger 2 740 MW (was 29 773 on 26 Aug); store within the 4-week bound | pass |
| `28870714` item 3: NTC floor 9 600 from 2035 | usable BEWAL–BEVLG ≥ 9 600 from 2040 | 2040 **and** 2050 usable = exactly 9 600 MW (floor binds; ceilings 13.2/14.4 slack) | pass |
| `28870714` item 8: rooftop share | ≥ 25.8 % BEWAL 2025 (when on) | 2025 rooftop 1 422 MW = 25.8 % of 5 510 MW solar-all; off 2030+ | pass |
| `28870714` items 6a/9 | withdrawn for this run (§9) | no `Capped electricity imports` line; no industry-CC pin line in 2040/2050 logs | pass |
| `788cc75a`/`4459a96c`/`93bdf848` master merge: shared cost CSV (PV/onwind lifetime 25 a, year_currency fills) | shared TIMES/PyPSA parameters | `build_common_parameters.py --check` clean pre-run; values in cost tables | pass (no dedicated network observable) |
| TIMES_PyPSA `3627a53` named transfers | STORAGEMININD / rooftop-share extractors | `times_industrial_capture.csv`, `times_pv_rooftop_share.csv` present and read by the pins | pass |
| pypsa2html items 14/15 | Electrolysis/FT/Methanation split; CCS capacity panel | All three series + "CCS capacities (fuel input)" panel in every capacities page | pass |

**Unintended side effect** (not a commit-intent failure — the commits did what
they said): removing rooftop from `solar-all` (item-8 fix) uncappped rooftop
*Europe-wide* → F1 below.

### 11.2 Level verdicts

| Level | Verdict |
|---|---|
| 0 provenance | **pass** |
| 0b commit intent | **pass** (F1 side effect recorded) |
| 1 convergence | **pass** (4/4 optimal; `Crossover 0` interior points; known large-bounds/rhs warnings all horizons) |
| 2 soft-link fidelity | **pass** (EV identity ±0.00 % all horizons; every carrier within tolerance except the known coal gap +10/+14/+37/+23 % = item 17a; heat-profile total gap 0.144 TWh, 2040 worst −0.005 TWh vs the 0.46 TWh expected-documented) |
| 3 accounting | **pass** (every checked bus 0.00 % residual; BE AC+LV closes to <0.01 % on 229–400 TWh gross; biogas/solid-biomass e_sum respected; BEV Sankey node closes) |
| 4 constraint compliance | **pass with caveats** — nuclear/offwind/NTC/ptes pins hold exactly; the 9 aggregate FAILs are all 2025 and all F1/F2 below |
| 5 realism | **pass with caveats** (CFs and COPs all in range: onwind 22.9–25.3 %, solar 8.7–12.9 %, COP 2.39–2.52; build rates onwind 350 MW/yr and hsat ~500 MW/yr exceed Walloon history but are the envelope's authored 2×-record allowance; F1 is the big caveat) |
| 6 prices/costs | **pass with caveats** (effective BEWAL CO₂ 427 / 104 / 128 / 426 EUR/t; 2025 still a decarbonised counterfactual; biogas block runs only in 2050 (6.90/6.90) — 2040 (0 of 4.0) sits at the flip; 2050 EU biomass dual −1 053 EUR/t is very tight) |
| 7 TIMES consistency | **pass with caveats** (nuclear, heat mix, demands aligned; **industry CC is a PyPSA residual, not STORAGEMININD** — item 9 withdrawn, §9; biogas 0/0/0/6.9 vs vd 7.67/8.07 = item 17d divergence unchanged) |
| 8 robustness | objectives vs 30 Aug: 2025 −8.6 % (349.6 vs 382.3 bn — the F1 rooftop bubble makes the European 2025 system cheaper), 2030/2040/2050 not comparable (same bubble in brownfield + items 2/3/10/11/12); treat cross-vintage deltas as F1-dominated until re-run |

### 11.3 Findings

**F1 (headline) — 80.2 GW of phantom French rooftop PV built in 2025, frozen
into all later horizons.** Removing rooftop from the `solar-all` CCL group
(item-8 fix, needed for the Elia utility pin) left `solar rooftop` an
uncapped carrier with a 125 GW potential in France. At the 2025 effective CO₂
price (427 EUR/t) filling it was rational: FR rooftop 80 157 MW + GB 5 668 +
DE 5 511 + NL 3 577 + LU 1 039 ≈ **97 GW Europe-wide**, utility solar
correctly pinned at its 21.5 GW cap. The myopic chain carries it as sunk
capacity through 2050 (verified: identical rooftop totals in 2030/2040/2050).
It depresses neighbour prices (BEWAL mean 85/102/101 EUR/MWh in 2030/40/50)
and shapes every import/investment decision. The 30 Aug run did not have this
(rooftop was inside solar-all; FR 2025 solar ≈ its 21.5 GW cap). The 2025
aggregate FAILs for BE/DE/FR/GB/LU/NL solar-all and BEWAL solar-all (5 510 vs
4 088: the checker counts the intended 1 422 MW rooftop pin against a
utility-only cap) are all this finding. *Fix direction:* scope the rooftop
exclusion to BEWAL (or add rooftop to the envelope/growth caps), add a
regression test, re-run.

**F2 — 2025 Flanders was unconstrained (known §9, now quantified).** The BE
rows never bind BEVLG/BEWAL in the 2025 base network (country rewrite), so
2025 Flanders free-built 8 000 MW offwind (vs 2 262 standing), 4 252 MW
onwind and 11 061 MW solar (5 015 utility + 6 046 hsat). The 8 GW offwind was
accepted as the 2030 pin's standing fleet (§9); the onwind/solar free-build
is the same mechanism. 2025 is neither a capacity nor a price calibration
for Flanders; it feeds the chain as brownfield.

**F3 — item 9 withdrawal (documented §9).** Industry CC capture in 2040/2050
is a PyPSA residual (≤ 3.4 GW capturable from the transferred fuel mix); the
TIMES 5.08/4.83 Mt floors are unsatisfiable in PyPSA as soft-linked. Do not
plot industry CC as TIMES-aligned.

**F4 — 2050 biomass scarcity.** EU `biomass limit` dual −1 053 EUR/t in 2050
(2040: −61). The B′ biomass-boiler profile (2050: only 0.06 TWh pinned)
relaxes entirely to the heat-pump absorber (fidelity table: 100 % gap on that
group, +0.06 TWh absorbed — within the 1 000 EUR/MWh slack, total |gap| all
years/groups 0.144 TWh). Not a bug; note when reading 2050 heat numbers.

**F5 — stale `industrial_energy_demand_*.csv`** still carry ~2 Mt
process-emission rows; overridden at solve time by `custom_potentials.csv`
(verified on solved networks). Cosmetic; regenerate (§10).

### 11.4 Numbers that must not be published as-is

1. **2025 neighbour capacities** (FR 80.2 GW rooftop etc.) and any 2025
   price/import/CO₂-dual — F1/F2 artefacts, not a 2025 system.
2. **Cross-vintage comparisons vs 30 Aug** for price- or import-dependent
   indicators — the 97 GW rooftop bubble is in this vintage's brownfield only.
3. **Industry CC volumes** as TIMES `STORAGEMININD` — F3.
4. Usual degenerate set: water-pits charger/discharger `p_nom` (2 740 MW at
   capital_cost 0 — the *store* bound is now meaningful, the chargers are
   not), `electricity distribution grid`, `gas pipeline`, `BEV charger`
   zero-capital rows; BEWAL 2050 rooftop 1 422 MW (an inherited pin, not a
   forecast).
5. 2040 system cost dip: biogas block (4.0 TWh) ran at 0 — the known
   all-or-nothing flip (instructions.md), do not read as a trend.

### 11.5 Follow-up actions

1. **F1 fix**: rooftop back under a cap outside BEWAL's utility pin +
   `test/` regression (a neighbour-solar-all check on 2025 totals including
   rooftop); re-run 1h before any cross-vintage claim. Blocks nothing else.
2. **F2 fix**: BEVLG 2025 rows (historical Flanders fleet) in
   `agg_p_nom_minmax_demande_haute.csv`; the CCL country-rewrite defect
   itself (BE rows grouping only BEBRU in the base year) deserves its own
   issue — it is the same mechanism that caused three §9 relaunches.
3. Regenerate `industrial_energy_demand_*.csv` (F5).
4. Item 9 feed basis: STORAGEMININD vs transferred fuel mix — needs a TIMES
   decision (bigger industry transfer, or include SMR/CCGT-CC capture in the
   floor) before the pin can ever be on.
5. Items 6a (gross-vs-annual semantics) and 8 (Elia floor vs TIMES mix)
   remain open with code + tests in place, overlays off (§9/§10).

**Overall verdict: solved, reviewed, publishable for Walloon capacity/heat/
nuclear/offshore results with the F1 caveat stated wherever 2025 context or
import/price indicators appear; 2025-only and cross-vintage claims blocked
until F1 is fixed and re-run.**
