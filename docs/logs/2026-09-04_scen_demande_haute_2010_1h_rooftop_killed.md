# Solve log — scen_demande_haute @ 2010, 1h (rooftop-split attempt, KILLED)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-09-04 14:26 → 2026-09-04 ~19:00 (killed for the vd swap) |
| Operator | Muse agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml` + overlay `config/scenarios.walloon.yaml`; on NIC5 also `cluster/config_cluster.yaml` |
| Code version | `development_plan` `dbdd8cb0` (rooftop split, share on from 2030, item 9 on, caps 2668/1560) |
| Outcome | **killed**: 2025 optimal, 2030 aborted at barrier iter 265 (~1h50, converged to 8 digits but no `Optimal objective` line yet) |

## 2. Goal of the run

First 1h production attempt with the base-year PV fleet split (1 770 MW
rooftop + 898 MW ground at BEWAL 2025) and the TIMES rooftop share re-enabled
from 2030 on (plan B5). Superseded the same day by the new TIMES vd
(`scen_central_demande_haute_v2_260903_0309.vd`).

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_central_demande_haute_v1_260828_2808.vd` |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` |
| Snapshots | 2010-01-01 → 2011-01-01, 8760 hourly |
| Sector time resolution | `1h` |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi barrier (`Method 2`), 16 threads / 100 GB, `BarConvTol 1e-5`, `Crossover 0`, `BarHomogeneous: 1`; NIC5 `batch` (2025, moved by `scontrol` from `hmem`), `hmem` (2030) |
| Key scenario overrides | rooftop split 1770/898 + share on; item 9 on (B3/B4); 6a off; NTC floor 9600 from 2035 |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Prepare (local) | local | rebuilt the 2025 brownfield with the split: 983.1 (2020) + 786.9 (2015) = 1 770 MW rooftop on `BEWAL low voltage`; utility standing 516.1 MW |
| LP solve | NIC5 | orchestrator pid 2488539; 2025 job **11115732** (hmem → moved to batch by `scontrol`, ran immediately on `nic5-w070`); 2030 job **11116315** (hmem, `nic5-w072`, killed at 18:59) |

## 5. Timings

| Step | Duration |
|---|---|
| 2025 solve | ~2.5 h wall, Optimal **3.55859586e11** |
| 2030 solve | killed at iter 265 / 1h49 (primal 3.63557911e11, dual 3.63557904e11) |

## 6. Resource usage

| Metric | Value |
|---|---|
| Peak RAM per solve | unknown (job killed; not recorded) |

## 7. Results

| Horizon | Status | Objective |
|---|---|---|
| 2025 | Optimal (kept on disk, superseded by the vd swap) | 3.55859586e11 |
| 2030 | killed before `Optimal objective` | — |
| 2040 | never started | |
| 2050 | never started | |

## 8. Publication (Wallonie Explorer / S3)

n/a — run killed, nothing published.

## 9. Issues encountered and fixes

- hmem queue blocked again (16-CPU request vs backfill reservation; mhantro's
  31 higher-priority pending jobs). The pending 2025 job was moved to `batch`
  with `scontrol update ... Partition=batch` — running in 20 s, no
  orchestrator restart. 2030 later submitted to `hmem` started immediately.
- 2025 with the fleet split solves cleanly (~2.5 h): the split + total pin +
  71.4→70.8 % share machinery is LP-sound in the base year.
- 2030 with item 8 on (70.8–71.4 % share) converged to 8 digits in 265
  iterations; killed before the certificate, so no verdict on the share in
  2030 — the v2 run will answer it.

## 10. Follow-ups / pending

Superseded by the v2 run
([`2026-09-04_scen_demande_haute_2010_1h_v2.md`](2026-09-04_scen_demande_haute_2010_1h_v2.md)):
new vd, regenerated rooftop/capture CSVs, same constraint set.

## 11. Critical review

n/a — killed run, results superseded.
