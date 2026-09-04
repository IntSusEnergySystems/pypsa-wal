# Solve log — scen_demande_haute @ 2010, 1h (TIMES vd v2, rooftop split)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-09-04 → (in progress) |
| Operator | Muse agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml` + overlay `config/scenarios.walloon.yaml`; on NIC5 also `cluster/config_cluster.yaml` |
| Code version | `development_plan` (rooftop split, share on from 2030, item 9 on, caps 2668/1560) |
| Outcome | in progress |

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
| Data retrieval / network build (prepare) | local | full rebuild from the new vd (demands, heat targets, 2025 brownfield with the split) |
| LP solve | NIC5 | 16 cpus/task, 100 GB, `SOLVE_RUNTIME=1440` |
| Post-processing (CSVs, plots) | local | `nic5.sh postprocess` after pull |
| HTML report (pypsa2html) | local | via postprocess |
| Explorer CSV extraction (ClimAct) | local | `nic5.sh publish` (extract + S3) |

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (launch → results verified) | in progress |
| Prepare (network build) | |
| Push to cluster | |
| Queue wait (cluster) | |
| Solve 2025 / 2030 / 2040 / 2050 | |
| Pull results | |
| Post-processing + plots | |
| pypsa2html report | |
| ClimAct extraction | |

vd v1 → v2 deltas (same extractor): rooftop share 71.36/85.81 → **70.83/80.10 %**
(2030/2050; v2 has no 2025 row); industry CC 4365/5077/**5140/4842** kt
(2045/2050 +20/+16 kt); nuclear trajectory unchanged (2045 0.5+0.25,
2050 1+1 GW; v2 adds 1 MW GEN3 in 2040 — noise).

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size (rows / cols / nonzeros) | |
| Peak RAM per solve | |
| Peak RAM local phases | |
| Disk footprint | |

## 7. Results

| Horizon | Status | Objective (EUR/a or model units) |
|---|---|---|
| 2025 | | |
| 2030 | | |
| 2040 | | |
| 2050 | | |

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | |
| Scenario folder on S3 | |
| Explorer display label | `demande-haute-2010-1h` |
| Explorer CSVs | |
| TIMES vd staged | `scen_central_demande_haute_v2_260903_0309.vd` |
| Verified in Explorer dropdown | |

## 9. Issues encountered and fixes

## 10. Follow-ups / pending

## 11. Critical review

Not yet. Filled after a successful solve against
[`../run-review-checklist.md`](../run-review-checklist.md).
