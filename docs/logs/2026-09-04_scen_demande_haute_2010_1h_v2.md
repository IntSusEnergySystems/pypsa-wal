# Solve log — scen_demande_haute @ 2010, 1h (TIMES vd v2, rooftop split)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-09-04 19:04 → 2026-09-05 02:00 (4/4 optimal) |
| Operator | Muse agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml` + overlay `config/scenarios.walloon.yaml`; on NIC5 also `cluster/config_cluster.yaml` |
| Code version | `development_plan` `c68d1474` (vd v2 swap, regenerated transfers, rooftop split, share on, item 9 on) |
| Outcome | **4/4 optimal** |

## 2. Goal of the run

Full 1h / 2010 four-horizon solve of `scen_demande_haute` on the new TIMES vd
(`scen_central_demande_haute_v2_260903_0309.vd`, received 2026-09-04 via S3),
with the rooftop fix: 2025 fleet split 1.77 GW rooftop / 0.9 GW ground,
TIMES share imposed from 2030 on (70.8 % 2030, 80.1 % 2050 on the new vd),
item 9 on (B3/B4). Follows the killed rooftop attempt on vd v1
([`2026-09-04_scen_demande_haute_2010_1h_rooftop_killed.md`](2026-09-04_scen_demande_haute_2010_1h_rooftop_killed.md)).

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_central_demande_haute_v2_260903_0309.vd` |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` |
| Snapshots | 2010-01-01 → 2011-01-01, 8760 hourly, weight 1.0 |
| Sector time resolution | `1h` |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi barrier (`Method 2`), 16 threads / 100 GB, `BarConvTol 1e-5`, `Crossover 0`, `BarHomogeneous: 1`; NIC5 `hmem` (fall back to `batch` per job if Priority-blocked) |
| Key scenario overrides | rooftop split 1770/898 + share on (2030+); industry CC floor on (STORAGEMININD v2: 4365/5077/5140/4842 kt); 6a off; NTC floor 9600 from 2035; Belgian CO₂ store 0; aviation off |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval / network build (prepare) | local | 30 steps, full rebuild from the new vd; split applied (983.1 + 786.9 = 1 770 MW rooftop) |
| LP solve | NIC5 **`hmem`** (16 cpus/task, 100 GB) | orchestrator pid 3646416, zero queue wait; 2025 job 11116832, 2030 11117043, 2040 11117446, 2050 11117809 |
| Post-processing (CSVs, plots) | local | `nic5.sh postprocess` 08:05–08:2x, 11/11 steps |
| HTML report (pypsa2html) | local | via postprocess → `https://pypsa.squoilin.eu/scen_demande_haute_20260905/` (200) |
| Explorer CSV extraction (ClimAct) | local | `nic5.sh extract` 08:26 (49 pypsa + 3 strategy + vd); stale v1 `.vd` removed from `explorer/times/` before upload |

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (launch → results verified) | 2026-09-04 19:04 → 2026-09-05 02:00 solve-complete (~7 h); postprocessing the same morning |
| Prepare (network build) | 30 steps from the new vd (demands, heat targets, 2025 brownfield) |
| Push to cluster | ~1 min |
| Queue wait (cluster) | none (hmem had room) |
| Solve 2025 | **1 h 14** wall, Optimal **3.55890314e11** |
| Solve 2030 | **2 h 14** wall, Optimal **3.63618342e11** |
| Solve 2040 | **1 h 41** wall, Optimal **2.91120598e11** |
| Solve 2050 | **1 h 31** wall, Optimal **2.68575853e11** |
| Pull results | rsync `--whole-file` (delta path corrupts, as on 3 Sept), md5-verified |
| Post-processing + plots | `nic5.sh postprocess` (touch, CSVs, plots, sankey, pypsa2html, S3) |
| pypsa2html report | in postprocess |
| ClimAct extraction | 49 pypsa + 3 strategy + `.vd`, 08:26 |

vd v1 → v2 deltas (same extractor): rooftop share 71.36/85.81 → **70.83/80.10 %**
(2030/2050; v2 has no 2025 row); industry CC 4365/5077/**5140/4842** kt
(2045/2050 +20/+16 kt); nuclear trajectory unchanged (2045 0.5+0.25,
2050 1+1 GW; v2 adds 1 MW GEN3 in 2040 — noise).

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size (rows / cols / nonzeros) | |
| Peak RAM per solve | 2025 **30.6 GB** · 2030 **35.3 GB** · 2040 **37.0 GB** · 2050 **36.5 GB** (sacct MaxRSS; all well under the 100 GB request) |
| Peak RAM local phases | |
| Disk footprint | |

## 7. Results

| Horizon | Status | Objective (EUR/a or model units) |
|---|---|---|
| 2025 | **Optimal** (~1h14 wall) | **3.55890314e11** |
| 2030 | **Optimal** (~2h14 wall) | **3.63618342e11** |
| 2040 | **Optimal** (~1h41 wall) | **2.91120598e11** |
| 2050 | **Optimal** (~1h31 wall) | **2.68575853e11** |

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | `s3://intervectoriel/test/pypsa_raw_results/20260905_walloon_scen_demande_haute/` (full tree, 4 networks, fresh explorer) |
| Scenario folder on S3 | `s3://intervectoriel/test/scenarios/times-pypsa__demande-haute-2010-1h__20260905/` (49 pypsa + 3 strategy + v2 `.vd`; stale v1 `.vd` deleted) |
| Explorer display label | `demande-haute-2010-1h` |
| Explorer CSVs | extracted 08:26 from this run's networks |
| TIMES vd staged | `scen_central_demande_haute_v2_260903_0309.vd` |
| Verified in Explorer dropdown | not yet (test env; verify before promoting) |

## 9. Issues encountered and fixes

- **Post-run finding (review): 2025 overshot the tightened pins.**
  `review_run.py` failed 4 aggregate checks, all 2025: BEWAL solar-all
  4 088 vs pin 2 668, BEWAL onwind 2 349 vs 1 560, BE/solar-all 11 207 vs
  9 751, BE/onwind 4 135 vs 3 337. Root cause, found by reproducing
  `add_CCL_constraints` standalone (the CCL itself is sound — it writes a
  382 MW ceiling and the toy LP lands exactly on the pin): the 2025
  *extendable candidates* entered the solve with `p_nom_min` from the
  IRENASTAT current-year share (BEWAL solar 1 802 MW = the 2021–2024 diffs
  binned into grouping-year 2025; onwind 655 MW; same pattern in every
  country), and the max branch can only clip its ceiling *up* to a forced
  floor. The assignment exists "for the year 2020"; with a 2025 base year
  it double-counts against pins that already encode the full fleet.
  **Fix (post-run, in tree):** `electricity.baseyear_reconcile_forced_build`
  scales `DateIn`-into-base-year rows down to the pin headroom
  (`scripts/walloon_scripts/baseyear_forced_build.py`, guarded by
  `test_baseyear_forced_build.py` — 5 cases). Rebuilt brownfield:
  solar-2025 floor 381.9 MW (= 2 668 − 2 286), onwind-2025 floor 0.
  Remaining data conflict (not code): BEWAL onwind standing (1 694 MW
  IRENASTAT) exceeds the 1 560 MW Energy-Balance pin by ~134 MW — flagged
  by the CCL warning and the guard; needs the fleet-source decision, the LP
  stays feasible via the clip. The BE-group FAILs are the same forced-floor
  mechanism on BEVLG/BEBRU candidates (documented §4.1 myopic-reset class).
  **Not re-run**: the fix is prepare-level only (no LP shape change beyond
  the intended pins); next production run carries it.

## 10. Follow-ups / pending

- Re-run with the base-year reconciliation fix before any cross-vintage or
  2025-capacity claim (this run's 2025 new-build is overstated by the forced
  IRENA share: +1 420 MW utility solar, +655 MW onwind at BEWAL).
- BEWAL onwind 2025 pin (1 560 MW) vs standing fleet (1 694 MW IRENASTAT):
  reconcile the sources (Energy Balance preliminary vs IRENASTAT).
- §11 critical review not done (postprocessing only, per instruction).

## 11. Critical review

Not yet. Filled after a successful solve against
[`../run-review-checklist.md`](../run-review-checklist.md).
