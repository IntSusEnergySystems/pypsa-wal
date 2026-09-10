# Solve log — scen_demande_haute, 2010, 1h, 5-year periods

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-09-08 19:18 CEST (first prepare) → 2026-09-09 ~20:05 UTC (solves done); postprocess/uploads/review through 2026-09-10 |
| Operator | Sylvain + agent (Muse Spark) |
| Run name (`run.name`) | `scen_demande_haute` — **first 5-year run: horizons 2025–2030–2035–2040–2045–2050. Not comparable to any 10-year run (see §11, R1).** |
| Run prefix (`run.prefix`) | `walloon_5y` → `results/walloon_5y/scen_demande_haute/` |
| Config file(s) | `config/config.walloon.yaml` + `config/config.walloon_5y.yaml` (+ `cluster/config_cluster.yaml` on NIC5). `HORIZONS` unset — derived (six horizons, verified). |
| Code version | pypsa-wal `eca9a289` (merge of `dc364b75` + origin `26314c53`) **plus uncommitted `rules/pypsa2html.smk` fix (§9)**; TIMES_PyPSA `c6f93e2` (local *and* cluster scratch, synced by rsync, §9); pypsa2html per report log |
| Outcome | success — 6/6 optimal, pulled, postprocessed, published (S3 + HTML) |

## 2. Goal of the run

First solve of a 5-year myopic chain at 1h — a different experiment from the
10-year grid, not a refinement (investment decisions compound twice as often;
cumulatives integrate over 30 instead of 35 years). Two commits on
`development_plan` since the 2026-09-07 production run: `50f95de0` (5y overlay)
and `de355403` (HORIZONS-from-config cluster fix). The run also carries the
same-day biomass revert `dc364b75` (9 222 back, §9).

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_central_demande_haute_v01_260907_0709.vd` (symlink → TIMES_PyPSA/data) |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5`; snapshots 2010-01-01 → 2011-01-01 |
| Sector time resolution | `1h` (8760 snapshots in every solved network) |
| Planning horizons / foresight | 2025–2030–2035–2040–2045–2050, myopic |
| Spatial clustering | `adm`, 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi barrier, 16 threads, no crossover (interior point) |
| Key scenario overrides | `agg_p_nom_minmax_demande_haute.csv`, solid biomass 9 222 + transported imports (§9), option B′ heat pinning (absorber heat pump, penalty 1000) |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Prepare (178 jobs) | local, 16 cores | retried over a Zenodo outage (§9); stalled `build_solar_thermal_profiles` killed once |
| LP solve | NIC5 `hmem`, 16 cpus/job, 1440 min limit | 6 solves + 5 brownfields, orchestrator pid 3483181 |
| Post-processing | local | `SNAKEMAKE_STORAGE_CACHED_HTTP_SKIP_REMOTE_CHECKS=1` (Zenodo still down, §9); `SKIP_S3_UPLOAD=1`, `HTML_PUBLISH=0` (explicit uploads §8) |
| HTML report (pypsa2html) | local | 82 pages, rebuilt after the 10y-content bug (§9) |
| Explorer CSV extraction (ClimAct) | local, env `datapypsa` | local-network mode (both S3 flags off, §9); 63 pypsa + 3 strategy CSVs + `.vd` |

Cluster specifics: solves ran on `nic5-w071` (2025 job `11131852`, 2030 `11131895`, 2035 `11132471`, 2040 `11135356`, 2045 `11136105`, 2050 `11137871`). Myopic chain, so no queue wait between horizons; 2025 started within minutes of submission.

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (first prepare → uploads done) | ~51 h, of which ~14 h was Zenodo-outage waiting |
| Prepare (network build, final pass) | ~2 h (178 steps; 41 min was the 10-year 105-job reference) |
| Push to cluster | minutes |
| Solve chain (6 barriers + handoffs) | ~11 h wall (barrier sums ≈ 10.1 h) |
| 2025 / 2030 / 2035 / 2040 / 2045 / 2050 (barrier it / s) | 222/3884, 324/7481, 260/6118, 206/5455, 331/8114, 195/5917 |
| Pull results (2.5 GB) | minutes |
| Post-processing + plots | ~15 min |
| pypsa2html report (rebuild) | 348 s, 82 pages |
| ClimAct extraction | ~75 min (6 × 8760 snapshots in pypsa 0.35) |

Runtime comparison (same 1h, same scenario, 10-year Sep-7 run): barrier totals
are comparable per horizon (2025 222 vs 211 it; 2030 324 vs 314 it — the stall
is gone). The chain is ~2× longer wall-clock because there are six horizons,
not because any horizon got harder; 2045 is the slowest (331 it / 8114 s).
Constraint set differs by the biomass revert (9 222, §9) and the two new
horizons — see §11.

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size | unknown (not recorded this run) |
| Peak RAM per solve | 2025: 32.6 GB, 2030: 34.7 GB (sacct MaxRSS); `logs/*_memory.log` peaks read 8–10 GB but under-report (2030 file peaks at 1 GB — logger coverage gap, see §10) |
| Peak RAM local phases | 8.6 GB RSS (ClimAct extraction); prepare not measured |
| Disk footprint | `resources/walloon_5y/` unknown; `results/walloon_5y/scen_demande_haute/` 2.5 GB + explorer 0.2 GB; S3 raw 3.0 GB |

## 7. Results

| Horizon | Status | Objective |
|---|---|---|
| 2025 | optimal | 3.48523277e+11 |
| 2030 | optimal | 3.64855902e+11 |
| 2035 | optimal | 2.22796865e+11 |
| 2040 | optimal | 2.47717786e+11 |
| 2045 | optimal | 1.70880013e+11 |
| 2050 | optimal | 2.30513287e+11 |

Local result folders: `results/walloon_5y/scen_demande_haute/{networks,csvs,graphs,html,explorer,logs,configs,heating_profiles}/`.
Effective configs verified identical across horizons apart from
`planning_horizons` (2 diff lines each). Budgets printed pre-barrier:
2.284/4.810/4.744/5.047/4.870/0.101 TWh against 11.222/11.222/11.347/11.472/11.847/12.222 TWh.

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | `s3://intervectoriel/test/pypsa_raw_results/20260909_walloon_5y_scen_demande_haute/` (3.0 GB) |
| Scenario folder on S3 | `s3://intervectoriel/test/scenarios/times-pypsa__demande-haute-5y-2010-1h__20260909/` |
| Explorer display label | `demande-haute-5y-2010-1h (times-pypsa) - 09/09/2026` (label extends the Sep-7 `demande-haute-2010-1h` with the 5y marker) |
| Explorer CSVs | 63 in `pypsa/` (7 per horizon-year incl. 2035/2045), 3 in `strategy/` |
| TIMES vd staged | yes — `explorer/times/scen_central_demande_haute_v01_260907_0709.vd` |
| HTML report | https://pypsa.squoilin.eu/scen_demande_haute_5y_20260909/ (200, 82 pypsa2html pages + TIMES Sankeys ×6 + indicators) |
| Verified in Explorer dropdown | no — not checked from here (same gap as Sep-7) |

## 9. Issues encountered and fixes

- **Zenodo outage blocked every Snakemake invocation (critical, worked around).**
  `zenodo.org/api` 504'd for ~14 h (records 4767098, 10820928); the
  cached-http plugin resolves `storage()` inputs at DAG-build, so prepare,
  solve submission and postprocess all died before running anything. A retry
  supervisor looped prepare until recovery. Postprocess ran under
  `SNAKEMAKE_STORAGE_CACHED_HTTP_SKIP_REMOTE_CHECKS=1` (the same-day
  `2ccd4e31` note; verified safe — all inputs on disk, outputs identical).
- **`build_solar_thermal_profiles` stalled 3 h (fixed by kill + retry).**
  16 dask workers at ~4 % CPU, no cutout reads for 10+ min, parent in
  `futex_wait` — against a 41-minute whole-prepare precedent (Aug-14 1h
  log). Killed the rule; snakemake resumed; the retry completed. Suspect:
  `distributed 2026.7.1` async-client handoff. No code change; see §10.
- **Biomass cap 6 222 would have broken four horizons (reverted to 9 222).**
  Pre-solve replication (heating_targets shares × PyPSA heat load, industry
  /0.9, caps from custom_potentials) showed 2030–2045 short 1.6–2.2 TWh
  (30–40 % forced boiler relaxation) and 2025 at +5 %. One-line master-CSV
  revert + `--write` (exactly 6 rows) + `--check` passed. Calibration: every
  live budget line matched the prediction to 3 decimals. Full analysis in
  [`renewable-potentials.md`](../renewable-potentials.md) §9.6.
- **Cluster TIMES_PyPSA was a stale branch (fixed by rsync).**
  Scratch checkout on `softlink-harmonisation` @ `5f49de5` lacked
  `indicator_page_names`; the solve orchestrator died at DAG parse (nothing
  submitted). No GitHub access from nic5, so the local tree (@ `c6f93e2`)
  was rsync'd over (`.vd` excluded); two pre-existing cluster-side `.md`
  edits preserved. `git log` on scratch now matches local.
- **pypsa2html reported the 10-year tree into the 5y folder (rule fix, uncommitted).**
  `rules/pypsa2html.smk` only injected the scenario when the name was absent
  from `config/pypsa2html.yaml` — `scen_demande_haute` is listed (10y path),
  so 82 pages of 4-horizon content landed in `walloon_5y/` (incl. the
  byte-identical 57-node Sankey warning). Fix: always override the requested
  scenario's `results_dir` with the rule's tree (label preserved). Stale
  pages deleted, rebuilt: 6 horizons discovered, 0 failed. **Not committed**
  per instruction; see §10.
- **Explorer template missing + S3-first defaults (worked around).**
  `config_extraction_walloon.yaml` absent from the extractor archive;
  restored from the last generated copy. Flipped `download_networks` and
  `upload_results` to False (local read, review before publish). The
  `times_file_for()` helper in `extract_explorer.sh` breaks on multi-file
  `CONFIGFILE` (passed as one string) — the `.vd` was staged by hand; see §10.
- **Pull rsync verification errors on the 10-year tree (no harm).**
  A failed early pull attempt logged checksum failures under `results/walloon/`;
  updates were discarded, destination unchanged. The 5y pull verified clean
  (all six `.nc` open, 8760 snapshots, solved dispatch).

## 10. Follow-ups / pending

What remains: commit or drop the uncommitted `rules/pypsa2html.smk` fix (plus a
regression test asserting the reported tree — e.g. horizons detected — so the
next overlay fails loudly); fix `times_file_for()` for multi-file CONFIGFILE;
investigate the 2030/2035 scarcity price spikes (§11 R4); check the Explorer
dropdown entry (with Clear cache); resolve the `logs/*_memory.log` coverage gap
(2030 reads 1 GB against 34.7 GB sacct); watch whether
`build_solar_thermal_profiles` stalls again (distributed version?); confirm the
2045/2050 BE nuclear remainder against the `.vd` trajectory (R5).

## 11. Critical review

**Reviewed by / date:** agent review 2026-09-10 against
[`../run-review-checklist.md`](../run-review-checklist.md), evidence from the
solved networks (not only summaries).

**Headline counts:** `235 PASS · 44 INFO · 20 WARN · 0 FAIL` from
`PYTHONPATH=. python scripts/walloon_scripts/review_run.py results/walloon_5y/scen_demande_haute`.

| Level | Verdict |
|---|---|
| 0 provenance | pass |
| 0b commit intent | pass with caveats (biomass commit half-reverted — intended, §9) |
| 1 solve | pass |
| 2 TIMES soft link | pass |
| 3 accounting identities | pass with caveats (known mapping holes, no FAIL) |
| 4 constraint compliance | pass with notes (2050 biomass degenerate allocation — expected) |
| 5 realism | pass with findings (build rates R2, PV split + 2035 dip R7) |
| 6 prices / costs | pass with findings (scarcity spikes R4) |
| 7 TIMES consistency | pass with notes (nuclear remainder R5) |
| 8 robustness | pass with caveats (first-of-kind: no vintage to compare against) |

### Commit intent (level 0b)

Previous production log: `docs/logs/2026-09-07_scen_demande_haute_2010_1h_production.md`
(Sep-7 10-year run). pypsa-wal `d950d061..eca9a289`:

| commit | class | intended behaviour → observable in this tree | verdict |
|---|---|---|---|
| 2bbd2863 review + cleaning | review tooling | no model change | n/a |
| 13ccefa9 TIMES indicators | postprocess | indicator pages + CSVs in `html/indicators/` (2035/2045 columns present) | pass |
| 50f95de0 5-year overlay | config | six horizons prepared, solved, reported (6 `.nc`, 6 sankey sets, 6 budget lines) | pass |
| 50f95de0 biomass 9222→6222 | config | **reverted same day** (`dc364b75`): customs read 9222 ×6, solved dispatch respects it (R3) | pass (as reverted) |
| de355403 HORIZONS from config | tooling | six targets prepared with `HORIZONS` unset; stale 4-horizon value would have silently published 4/6 | pass |
| 2ccd4e31 Zenodo docs | docs | n/a (its env var drove postprocess — operational, §9) | n/a |
| 26314c53 indicator code | postprocess | new `build_times_indicators.py` produced the indicator tree without errors | pass |
| dc364b75 biomass revert + §9.6 | config/docs | 9222 in customs; §9.6 documents the analysis | pass |
| eca9a289 merge | — | clean, tree builds | n/a |
| uncommitted `rules/pypsa2html.smk` | postprocess | 6 horizons discovered in `.../walloon_5y/...` (was: 10y content) | pass (uncommitted — §10) |
| TIMES_PyPSA `c6f93e2` (local == scratch) | lib | indicator pages, sankeys ×6, `indicator_page_names` import on both sides | pass |

`.vd` unchanged since Sep-7, so the hand-extracted side files
(`times_pv_rooftop_share.csv`, `times_industrial_capture.csv`) need no refresh.

### Findings

**R1 — Never compare this run's cumulatives with a 10-year run's. (blocks publication wording, not the run)**
`cumulative_costs.csv` integrates with horizon-gap weights (last inherits the
previous gap): 30 years here vs 35 on the 10-year grid, a ~14 % shift with no
physical meaning. Same for any horizon-weighted chart. Per-horizon figures are
unaffected. This is the single most likely misreading of the published report.

**R2 — 2025→2030 build rates exceed demonstrated history.**
BEWAL onshore wind +482 MW/yr (1 568 → 3 977 MW) against ~100–150 historical;
solar rooftop +567 MW/yr (1 770 → 4 604) against ~200–300; rooftop stays hot
to 2040 (+402 MW/yr). Either the myopic 2030 corridor or the cost ranking —
defend or constrain before citing 2030 capacity additions.

**R3 — Biomass: reverted cap holds with shrinking headroom.**
Solved BEWAL fuel use vs supply: 7.56/11.22, 9.97/11.22, 10.27/11.35,
10.56/11.47, 10.39/11.85, 4.75/12.22 TWh. Industry CC takes a fixed
~5.0–5.6 TWh from 2030 on; the boiler pin (soft) owns the residual. Margins
+1.4/+1.1/+0.8/+1.4 have Sep-7 precedent (2040 solved at +0.8), but 2040's
+0.84 is the thinnest margin ever solved — any demand-side revision lands
there first. 2050's `biomass limit` dual is −1 221 EUR/MWh: per checklist
4.4 the 2050 regional biomass split is a degenerate allocation, not a result.

**R4 — Scarcity price spikes in 2030 (1 369) and 2035 (8 726 EUR/MWh).**
BEWAL means 89–166, p95 ≤ 234, zero sub-zero hours in every horizon — then one
hour at 1 369 (2030) and one at 8 726 (2035). 2040/2045/2050 peak below 305.
Single-hour spikes in a single-weather-year run are adequacy events, not price
forecasts — but confirm they are load-shedding-free tight hours and not a
constraint artefact before quoting any price duration curve.

**R5 — Nuclear trajectory matches in BEWAL; BE remainder to confirm.**
BEWAL link MW_e: 1992 / 1030 / 1030 / 1030 / 1750 / 3000 — the 2035/2040
1 030 (Tihange 3 LTO), 2045 1 750 and 2050 3 000 all-BEWAL steps are as
aligned. BE-wide totals (3 882 / 2 030 ×3 / 2 750 / 6 000) imply ~1 000 MW in
BEVLG through 2045 (Doel 4) and ~3 000 MW outside BEWAL in 2050 — check
against the `.vd` trajectory in `nuclear-alignment-20260816.md` rather than
assuming.

**R6 — 2050 biomass micro-pins relax (0.086 TWh_th, precedent F6).**
Fidelity: every group in every horizon matches to solver tolerance except the
2050 biomass boiler (0.045 + 0.041 TWh_th pinned, ~0 delivered), exactly
absorbed by the heat-pump absorber (+0.086). Same numbers as Sep-7: the EU
biomass limit prices the pin out. Benign and expected — but it is a second
witness (with R3's −1 221 dual) that 2050 biomass is constraint-determined.

**R7 — Walloon PV dips 2030→2035 (−351 MW): a retirement cliff, not a policy.**
Total BEWAL PV (MW): 2 681 / 6 500 / **6 149** / 11 116 / 11 813 / 13 866, and
the whole dip is fixed-tilt `solar` 897 → 546 while rooftop (4 604) and hsat
(999) sit exactly flat. Vintage ledger: 2030 holds 2025:382 + 2015:164 +
2010:351; in 2035 the 2010 vintage is gone — the 25-year PV lifetime (§7.9)
retires it on 1 January — and no vintage of any sub-carrier is added. The
energy is absorbed in the margin: BEWAL total load falls 105.4 → 101.4 TWh
2030→35 and the region stays a net AC exporter (−3.0 → −2.2 TWh; importer
again in 2040 at +3.2 when the next build wave lands). Two artefacts colour
the picture and must not be published raw: (a) fixed-tilt is never rebuilt
anywhere in the chain (→ 0 by 2050) while rooftop/hsat take all growth — the
cost-ranking artefact of checklist 5.3, report total PV; (b) six myopic steps
make build waves lumpier than four — a 10-year run would show 2030→40 as one
smoother step, which is the "different experiment, not a refinement" warning
from §2 playing out in the capacity chart.

### What passed cleanly

Provenance (configs identical but for horizons; 2010/cutout/1h/`.vd` as
specified); 6/6 optimal with healthy barrier tails (no repeat of the 402-it
stall); EV identity ±0.00 % all horizons; heat-pump capacity rises monotonically
(1 280 → 8 003 MW_th, age profile present); heat fidelity otherwise exact;
capacity factors onwind ~25–26 %, PV ~10–11 %; biogas block off until 2050
(6.9 TWh then — the all-or-nothing block of checklist 6, watch the dip
narrative); `e_sum_max` respected on all annual-energy generators;
cross-scenario code paths (Sankeys ×6, indicators, extraction, uploads) all
handled six horizons except the two fixed en route (§9).

### Numbers that must not be published as-is

5y/10y cumulative comparisons (R1); 2050 regional biomass split (R3);
zero-capital-cost capacities (review list: distribution grid, gas pipelines,
BEV charger, H2 pipeline, water pits, home/battery dischargers — degenerate);
PV sub-carrier splits without the total (checklist 5.3); any price duration
claim resting on the R4 single hours; BE nuclear beyond BEWAL (R5); the 2035
PV dip (R7 — retirement cliff, not decommissioning).

### Review follow-ups

| # | Action | Owner |
|---|---|---|
| 1 | Commit or drop the uncommitted `rules/pypsa2html.smk` fix + regression test on reported horizons | code |
| 2 | Fix `times_file_for()` for multi-file CONFIGFILE in `extract_explorer.sh` | code |
| 3 | Confirm R4 spikes are tight hours, not artefacts | modeller |
| 4 | Confirm R5 BE nuclear remainder vs `.vd` trajectory | modeller |
| 5 | Check the Explorer dropdown entry (Clear cache if needed) | ops |
| 6 | Resolve `logs/*_memory.log` under-reporting (2030: 1 GB vs 34.7 GB sacct) | ops |
| 7 | Defend or constrain the R2 2025→2030 build rates | modeller |
| 8 | Confirm the R7 2035 "coast" needs no capacity (net exporter: done) and whether the exact-25y retirement cliff distorts the 2035 signal | modeller |
