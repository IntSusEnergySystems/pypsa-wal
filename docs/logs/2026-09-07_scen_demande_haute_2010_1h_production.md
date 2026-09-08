# Solve log — scen_demande_haute @ 2010, 1h (production, ICEDD 2026-09-07 export)

Second launch of 2026-09-07. The morning attempt on `8fbc39f3` stalled at 2030
(see [`2026-09-07_scen_demande_haute_2010_1h_stalled.md`](2026-09-07_scen_demande_haute_2010_1h_stalled.md)):
barrier sub-optimal after 402 iterations against the old
`scen_central_demande_haute_v2_260903_0309.vd`. Root cause per `d950d061` was not
numerics but a degenerate 2030 solid-biomass budget on the boundary. This run
solves the same code against ICEDD's new export, which freezes the Walloon
resource at its 2021 energy-balance level. All four horizons optimal.

## 1. Identification

| Field | Value |
|---|---|
| Date of run | 2026-09-07 19:14 (launch) → 2026-09-08 ~01:45 (solve done); recovery + review until ~04:30 |
| Operator | sylvain, assisted by opencode/Muse Spark |
| Run name / prefix | `scen_demande_haute` / `walloon` |
| Config files | `config/config.walloon.yaml` + `cluster/config_cluster.yaml` (16 CPUs, 100 GB, `BarHomogeneous: 1`) |
| Code version | `development_plan` `d950d061` ("Point the Walloon scenarios at ICEDD's 2026-09-07 TIMES export"); working tree clean at launch |
| Sibling checkouts | TIMES_PyPSA `3627a53` (edd); pypsa2html rebuilt from current checkout (trade fix `5793e1a` included, see 09-05 log addendum) |
| Outcome | **success 4/4**, after a pull/recovery incident documented in §9 (no solve re-run needed) |

## 2. Goal of the run

Production solve of `scen_demande_haute` (2010 weather year, 1h) on the
post-R1/R2/R4 code (`8fbc39f3`) with the `.vd` the stall diagnosis called for
(`d950d061`). Questions answered: does 2030 converge on the new export, is
R4's 2040 biomass-boiler relaxation gone, and do the R1/R2 transfer fixes
verify at ±0.00%.

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_central_demande_haute_v01_260907_0709.vd` (fetched from `s3://intervectoriel/test/scenarios/times_20260907/`, symlinked into `data/walloon/`) |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` (cached) |
| Snapshots | 2010-01-01 → 2011-01-01, 8760 h |
| Sector time resolution | `1h` |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi barrier, Method 2, BarConvTol 1e-5, BarHomogeneous 1, Crossover 0, Seed 123, 16 threads |
| Key scenario overrides | Tihange retrofit repeatable (`retrofit_nuclear_once: false`); agg caps `agg_p_nom_minmax_demande_haute.csv`; rooftop share on; industry CC floor on; self-sufficiency caps 2.94/6.47/10.0 TWh (2030/2040/2050); option B′ heat pinning, absorber = heat pump, penalty 1000 EUR/MWh_th |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Prepare (network build) | local, 16 cores | rebuilt demands + base networks against the new `.vd` (~20 min) |
| LP solve | NIC5 `hmem`, 16 CPUs/task, 100 GB | no queue wait either attempt (100 GB shares a mixed node instead of blocking a full one) |
| Post-processing (CSVs, plots) | local | re-ran after recovery (§9) |
| HTML report (pypsa2html) | local | 94 pages, re-published after recovery |
| Explorer CSV extraction (ClimAct) | local, env `datapypsa` | reads networks from S3 raw (`download_networks: True`); re-ran after recovery |

Solve jobs: 2025 `11126424`, 2030 brownfield `11126806` + solve `11126807`, 2040→2050 `11126807`→`11127558`, all on `nic5-w071`.
Pre-flight: `build_common_parameters --check` PASSED, full pytest 369 passed / 1 skipped (before first launch);
`pytest -k times_scenario_inputs` 2 passed after the `.vd` swap.

## 5. Timings

| Step | Duration |
|---|---|
| Total launch → solve done | ~6.5 h (19:14 → ~01:45) |
| Prepare (network build) | ~20 min (incremental: demands + 4 base networks) |
| Push to cluster | ~2 min |
| Queue wait | ~0 (both attempts) |
| Solve 2025 | 211→**247 it / 3892 s** barrier (~1h05 job); objective 3.48432903e11 |
| Solve 2030 | **314 it / 7809 s** barrier (~2h10; ~3h job with model gen); objective 3.64865569e11 |
| Solve 2040 | **244 it / 4733 s** barrier (~1h20 job); objective 2.88615231e11 |
| Solve 2050 | **199 it / 3971 s** barrier (~1h05 job); objective 2.67249208e11 |
| Pull results | minutes (but failed verification — see §9) |
| Post-processing + plots | ~5 min (re-ran 03:2x after recovery) |
| pypsa2html report | ~1 min (94 pages) |
| ClimAct extraction | ~25 min |

Runtime comparison (same 1h resolution, same scenario): the morning attempt's
2030 never converged (402 it / 6237 s → sub-optimal); on the new `.vd` 2030
converges in 314 it / 7809 s with residual 4.75 vs 1.38e5 at the old stall
point. 2025/2040/2050 barrier times are in line with the 09-06 run. No
constraint set changed between the two 09-07 attempts — only the `.vd`.

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size (2030) | 39,421,163 rows / 19,115,120 cols / 94,905,710 nonzeros; presolved 7,887,015 × 14,638,834 |
| Peak RAM per solve | 22.4 / 28.2 / 29.8 / 29.9 GB (2025 → 2050, `logs/*_memory.log`) — well inside the 100 GB request |
| Disk footprint | remote `results/walloon/scen_demande_haute/` 1.34 GB; local tree 2.29 GB (with derivatives + explorer) |

## 7. Results

| Horizon | Status | Objective |
|---|---|---|
| 2025 | optimal | 3.48432903e11 |
| 2030 | optimal | 3.64865569e11 |
| 2040 | optimal | 2.88615231e11 |
| 2050 | optimal | 2.67249208e11 |

Local result folders: `results/walloon/scen_demande_haute/{networks,csvs,graphs,html,explorer,logs,configs,heating_profiles}/`.
Effective configs verified identical across horizons apart from
`planning_horizons`; all four name the new `.vd`.

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | `s3://intervectoriel/test/pypsa_raw_results/20260908_walloon_scen_demande_haute/` (re-uploaded with true networks after recovery) |
| Scenario folder on S3 | `s3://intervectoriel/test/scenarios/times-pypsa__demande-haute-2010-1h__20260908/` |
| Explorer CSVs | 49 in `pypsa/`, 3 in `strategy/` (re-extracted from corrected raw) |
| TIMES vd staged | yes — only `scen_central_demande_haute_v01_260907_0709.vd` (stale `v2_260903` removed locally and from S3) |
| HTML report | https://pypsa.squoilin.eu/scen_demande_haute_20260908/ (rebuilt 03:47 with pypsa2html `2c40825`, 95 pages, same folder overwritten) |
| Verified in Explorer dropdown | no — not checked from here |

## 9. Issues encountered and fixes

- **Pull failed end-to-end verification; stale tree published (critical, recovered).**
  Symptom: after a green solve, local networks/configs did not match the
  cluster (md5 mismatch, old `.vd` string in local configs, different
  objective 3.638e11 vs 3.6487e11 for 2030). Cause: every large solve output
  failed rsync verification (`failed verification -- update discarded`, exit
  code 23) — first pull at 01:46 raced the freshly finished 2050 outputs on
  BeeGFS, and the re-pull hours later still failed the same way, so it is not
  (only) a race: rsync's **delta-transfer** path mis-verifies on this
  link/filesystem while `scp` and single-file rsync verify cleanly. The
  `|| msg "(no results dir yet)"` fallback in `cmd_pull` then let the driver
  continue onto postprocess, which built CSVs/graphs/HTML from the stale Sep-6
  files, uploaded them to S3 raw, and the extractor (which reads S3 raw)
  propagated the staleness into the Explorer CSVs. Fix: re-transferred the 16
  failing files (4 networks + 4 configs + 4 python logs + 4 benchmarks) with
  `rsync --whole-file`, md5-verified all four networks against the cluster,
  re-ran standard pull (clean), touched the networks (the true files carry
  older remote mtimes than the stale derivatives, so Snakemake said "nothing
  to be done"), re-ran postprocess (CSVs/graphs/HTML rebuilt 03:23–03:26),
  re-uploaded raw, re-extracted, re-uploaded scenarios, removed the stale
  `.vd` from the scenario folder, re-published HTML. Lesson: a pull whose
  rsync exits non-zero must abort the driver, and the four networks should be
  md5-checked against the cluster before postprocess (see §11 follow-ups).
- **First review (163→140 PASS) was run against the stale files and is void.**
  The `review_run_20260908.log` findings (coal +9.8%, EV −1%, 2040 biomass
  relaxation) describe the Sep-6 model, not this run. Re-ran everything on
  the true tree (`review_run_20260908_true.log`); only the second review
  counts. Nothing derived before ~03:00 Sep 8 (CSVs, HTML `…_20260907`,
  first Explorer upload) may be cited.
- **Extractor preconditions evaporated.** `EXTRACTOR_BASE_CONFIG` defaults to
  `config_extraction_walloon.yaml`, which does not exist in the extractor
  checkout (prior runs overrode it with `config_extraction_OET.yaml`); the
  `EXTRACTION_CONFIG` patch to `graph_extraction_main.py` was gone
  (re-applied exactly as `extract_explorer.sh`'s guard prescribes, plus
  `import os`); the extractor needs `AWS_PROFILE=intervectoriel` in the
  environment (it reads networks from S3 raw and uploads strategy CSVs to
  S3) but `extract_explorer.sh` does not export it. All three are follow-ups
  in §11 — the next extraction hits the same walls otherwise.

## 10. Follow-ups / pending

Covered by the review follow-ups table in §11 (F1–F3 are ops/tooling, F4–F7
modelling/reporting). Plus: verify this run in the Explorer dropdown.

## 11. Critical review

**Reviewed by / date:** opencode/Muse Spark, 2026-09-08 ~03:00–04:30 CEST, on
the recovered true tree; human judgement calls (levels 5–8) are marked where
the author should confirm.

**Headline counts:** `163 PASS · 30 INFO · 15 WARN · 0 FAIL` from
`review_run.py results/walloon/scen_demande_haute`
(`cluster/logs/review_run_20260908_true.log`). Heat fidelity:
`check_heat_profile_fidelity.py scen_demande_haute live` — total |gap| 0.172
TWh over all (year, group, bus); worst single group 2050 biomass boiler rural
−0.04578 TWh of 0.04578 pinned.

| Level | Verdict |
|---|---|
| 0 provenance | pass |
| 0b commit intent | pass |
| 1 solve | pass with caveats (Crossover 0 interior; conditioning warnings tolerated) |
| 2 TIMES soft link | pass with caveats (only 2050 biomass micro-pins relaxed, 0.086 TWh @ 86 MEUR) |
| 3 accounting identities | pass (Sankey holes are mapping holes, see F3) |
| 4 constraint compliance | pass |
| 5 realism | pass with caveats (build rates F4; CFs/COPs all in range) |
| 6 prices / costs | pass with caveats (conventions + 2050 CO₂ price, see F5) |
| 7 TIMES consistency | pass with caveats (import cap binds exactly; see notes) |
| 8 robustness | caveats (single weather year; interior-solution noise) |

### Commit intent (level 0b)

Previous production log: `docs/logs/2026-09-05_scen_demande_haute_2010_1h_production.md`
at SHA `0f9ce604`. `git log 0f9ce604..d950d061`:

| Commit | Class | Intended behaviour | Observable in this tree | Verdict |
|---|---|---|---|---|
| `7099524b` | docs only (two .md files) | none | n/a | n/a |
| `72c9bef2` power-plant CC option, shipped OFF | physics/config | no result change; `power_plant_cc_from_year: null` | effective config carries `power_plant_cc_from_year: None`; CC available all horizons | pass |
| `2f67b01e` ICEDD solid-biomass potential (master CSV) | config/data | synced potentials | `build_common_parameters --check` PASSED; 2030/2040 BEWAL `e_sum_max` fully used (4.824/8.250 TWh) | pass |
| `25680656` merge | meta | — | n/a | n/a |
| `8fbc39f3` R1 coke→coal factor | physics | coal load == TIMES | coal for industry 3.706/3.141/1.019/1.819 TWh, all ±0.00% vs TIMES | pass |
| `8fbc39f3` R2 EV/rail | physics | EV grid draw within 0.02% | 0.895/4.842/12.586/16.918 TWh, all −0.00% vs TIMES | pass |
| `8fbc39f3` R4 relaxation reporting | review tooling | `report_relaxed_profiles` lines + review 2.5 | present in all four python logs (e.g. 2050: biomass boiler 0.0860/0.0860 TWh, 100%, 86 MEUR); review 2.5 WARN matches | pass |
| `d950d061` new `.vd` | config | 2030 converges; 2040 relaxation gone | 2030 optimal in 314 it; 2040 pins fully delivered (0.0000 relaxed); `times_file` string correct in all four effective configs | pass |

TIMES_PyPSA at `3627a53` (previous SHA unknown — the 09-05 log does not record
it, so cross-checkout drift since then cannot be ruled in or out); pypsa2html carries the trade fix (`5793e1a`), verified live
by 4.3b: 2050 one-way inflow reads exactly 10.00/10.00 TWh.

### Findings

**F1 — pull verification failure; stale tree briefly published (ops, headline for process, not for numbers).**
Covered in §9. No headline number in this log comes from the stale files; every
figure below was re-derived after the md5-verified re-pull. The defect is in
the tooling (`cmd_pull` tolerates rsync exit 23; delta-transfer mis-verifies on
this path), not the model.

**F2 — extractor preconditions are tribal knowledge (ops).** §9, third bullet.
Until fixed, the working invocation is
`AWS_PROFILE=intervectoriel EXTRACTOR_BASE_CONFIG=config_extraction_OET.yaml ./cluster/nic5.sh extract`.

**F3 — Sankey mapping holes, not solve defects (reporting).**
`enc_pe` (primary energy) is one-sided in all horizons (out 7.5/9.4/10.0/4.3
TWh, in 0 — the inflow is not mapped); 2025 `elc_se` −0.618 and `vap_se`
−0.090 TWh. Same family as the pypsa2html trade artefact fixed upstream: the
buses balance (level 3 all ok, BEV node closes with smart + natural inflows in
2040/2050), the report graph does not. Do not cite `enc_pe` throughput; the
electricity-node shortfall noted in the 09-05 addendum (~9 TWh, 2050) is the
same hole seen from the other side.

**F4 — build rates above historical (judgement call).**
BEWAL onwind 2025→2030 +482 MW/yr (1,568 → 3,977 MW) against ~100–150 MW/yr
historical; rooftop PV +567 MW/yr to 2030 and +618 MW/yr to 2040 against
~200–300 MWp/yr. The optimiser is allowed to build fast; any chart or text
presenting these steps must say they exceed the historical pace severalfold.
Author to confirm whether a growth limiter (`limit_max_growth`, currently off)
should be engaged.

**F5 — CO₂ prices: non-monotonic, 2050 entirely national (read carefully).**
Effective BEWAL price (|global| + |national|): 433 / 196 / 141 / **407** EUR/t
(2025/30/40/50); in 2050 the global dual is 0.0, so the full 407 is the
national cap. 2025's 433 sits on a base year that is already a decarbonised
counterfactual (sequestration cap 0 binding, biomass limit ≤ 0 binding), not a
calibration — per checklist 4.4/5.1, do not present 2025 duals as observed
prices. Aviation exclusion behaves as designed (no unsatisfiable-cap blowout);
still open: explicit confirmation that the global `CO2Limit` binds in every
horizon (the only thing pricing kerosene now).

**F6 — 2050 biomass micro-pins relaxed (expected, tiny).**
Biomass boiler rural/urban-decentral 0.0458/0.0402 TWh pinned, 0 delivered, 86
MEUR penalty; heat-pump absorber took it and every aggregate closes. The fuel
simply is not there (EU `biomass limit` binds, 2050 mu −1,087). R4's 2040
relaxation is gone as predicted — 2025/2030/2040 delivered 100.0% of every pin.

**F7 — local/cluster pypsa skew (process).**
Solved networks are pypsa 1.2.1 (cluster env), local env is 1.2.4 — review
import warnings only, no defect observed. Consider pinning the cluster env to
the same pypsa as `pixi.lock`/local to remove a silent vintage difference.

### What passed cleanly

- Provenance: commit, branch, 1h, 2010 weather/cutout agreement, four configs
  identical apart from horizons, correct `.vd` string.
- Transfer fidelity: every TIMES carrier in every horizon at ±0.00%, including
  EV (±0.00% all years — R2), coal (±0.00% — R1), heat-pump trajectory rising
  (1.49 → 3.35 → 14.71 → 19.46 TWh_th, COP 2.42–2.52), decentral heat closes to
  1e-6 TWh.
- Balances: all BEWAL buses ~0.00%; BEV node closes with both smart- and
  natural-charging inflows; EV-battery cyclic.
- Caps and potentials: all 22 agg rows within corridor; onwind ≤ 6,500 MW
  (binds 2040/2050), rooftop ≤ 46,000 MW; solid-biomass `e_sum_max` fully used
  2030 (4.824/4.824) and 2040 (8.250/8.250), slack in 2050 (6.377/9.000).
- NTCs: usable == cap on every BE border; Nemo 1,000 MW; internal BEWAL links
  uncongested (0% hours at limit except BE-GB 79–95%).
- Import cap 6a binds exactly: 2.94 / 6.47 / 10.00 TWh one-way inflow, marginal
  values −9.02 / −13.63 / −2.97 EUR/MWh.
- CFs all in range (onwind ~26%, PV ~11%, hsat ~13%, ror 26%).

### Numbers that must not be published as-is

- Zero-capital-cost capacities (distribution grid 9,944 MW, gas pipelines,
  BEV charger 4,194 MW, water-pit/battery chargers, H2 pipeline 2,128 MW,
  …) — degenerate variables, not results.
- Any capacity at three significant figures — Crossover 0 interior solutions
  carry ~1% tolerance noise; 1% deltas between runs are not signal.
- 2025 capacities/prices as "today" — 2025 is an optimisation under 2025 caps,
  not a calibration (5.1, F5).
- `costs.csv`/`nodal_costs.csv` totals without stating the convention
  (non-extendable capital included; existing nuclear annuitised at new-build
  cost) — they exceed the Gurobi objective by construction (~2.67e11 vs
  ~5–6e11 scale).
- Walloon nuclear capacity/cost from BEWAL nodal rows — unattributed by
  `bus0`; recompute grouped on `bus1`.
- The `enc_pe` Sankey throughput and any 2050 electricity-node residual (F3).
- Build-rate charts without the historical-pace caption (F4).

### Review follow-ups

| # | Action | Owner |
|---|---|---|
| 1 | `cmd_pull` must abort (not warn-continue) on rsync exit ≠ 0; md5-check the four solved networks against the cluster before postprocess | ops/code |
| 2 | Retry the standard pull without `--whole-file` on the next run to see whether the delta-verification failure recurs (file a CECI/BeeGFS note if it does); consider making `--whole-file` the default for `*.nc` | ops |
| 3 | Fix extractor preconditions: ship the walloon template or correct the `EXTRACTOR_BASE_CONFIG` default; export `AWS_PROFILE` in `extract_explorer.sh`; record the `EXTRACTION_CONFIG` patch where the next operator finds it | ops/code |
| 4 | Confirm global `CO2Limit` binds every horizon (kerosene pricing after the aviation exclusion) | modeller |
| 5 | Decide on `limit_max_growth` given F4 build rates | modeller |
| 6 | Check the 8.3 TWh biogas block dispatch before reading any 2040 cost dip as a trend (checklist 6) | reviewer |
| 7 | Verify this run in the Explorer dropdown; delete nothing else under the 20260908 prefixes | operator |
| 8 | Add regression tests for F1 (pull-verify) and F3 (Sankey-node closure on `enc_pe`/`elc_se`) so the next run fails loudly | code |
