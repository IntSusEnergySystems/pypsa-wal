# Solve log — scen_demande_haute @ 2010, 6h (item 2: Belgian stores = 0)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-09-02 15:48 → 16:34 |
| Operator | Cursor agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml` + `cluster/config_cluster.yaml` on NIC5 |
| Code version | working tree on `master` at `b43ad14e` plus item-2 edits (Belgian `e_nom_max` = 0; not committed) |
| Outcome | **success** — 4/4 optimal. No Northern-Lights export. Capture leaves Belgium on existing `CO2 pipeline` links to DE/NL/GB. |

## 2. Goal of the run

Re-solve item 2 after withdrawing the TIMES 7.1 Mt/a Walloon sink. That figure
is an injection volume, not demonstrated geology. All three Belgian nodes have
a documented `e_nom_max = 0` (`custom_potentials.csv`). Captured CO₂ must go
to CO2StoP countries (DE/NL/GB) on the existing `co2_network`. Same geology
ramp + `BarHomogeneous` as the 14:03 6h run.

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/scen_central_demande_haute_v1_260828_2808.vd` |
| Weather year / cutout | 2010, `europe-2010-sarah3-era5` |
| Snapshots | 2010-01-01 → 2011-01-01, **1460** sector snapshots (6h) |
| Sector time resolution | **`6h`** |
| Planning horizons / foresight | 2025–2030–2040–2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | BE FR GB NL DE LU |
| Solver + options | Gurobi barrier, 16 threads, `BarHomogeneous: 1` |
| Belgian CO₂ stores | BEWAL/BEVLG/BEBRU **0 Mt/a** (documented; not fillna, not TIMES 7.1) |
| Export | existing `CO2 pipeline` to DE/NL/GB; no Northern Lights |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Prepare | local | rebuilt 2025 brownfield only (~1 min); 6h sector networks reused |
| LP solve | NIC5 **`batch`** (`nic5-w039` / `w041`) | 16 cpus, 100 GB, wall 480 min. Not hmem. |
| Post-processing | skipped | cheap feasibility solve |
| HTML / Explorer | skipped | |

Previous solved `.nc` on the cluster were deleted so `--rerun-triggers mtime` could not skip them.

## 5. Timings

| Step | Duration |
|---|---|
| Prepare (2025 brownfield) | ~1 min |
| Push + drop stale solves | ~44 s |
| Queue wait | ~8 min DAG + first Slurm dispatch |
| Solve 2025 | 113 iter / **258 s**, objective 3.51811474e+11 |
| Solve 2030 | 180 iter / **458 s**, objective 3.59087309e+11 |
| Solve 2040 | 147 iter / **391 s**, objective 2.87813093e+11 |
| Solve 2050 | 133 iter / **372 s**, objective 2.66718630e+11 |
| Full solve chain | ~44 min (15:50 → 16:34) |
| Pull | rsync checksum-discarded 2040/2050 on the results mount; forced `--inplace` re-pull of the four `.nc` |

2040 (the 30 Aug abort) was faster than the 7.1-sink 6h run (391 s vs 792 s) and still Optimal with `BarHomogeneous`.

## 6. Resource usage

| Metric | Value |
|---|---|
| Snapshots | 1460 (6h) |
| Peak RAM per solve | **~9 GB** (2040 MEM max 8.96 GB) — 100 GB request was ample on a 252 GB batch node |
| Disk | ~44–69 MB per solved 6h network |

## 7. Results

| Horizon | Status | Objective (EUR/a) | `co2_sequestration_limit` dual | seq. used |
|---|---|---:|---:|---:|
| 2025 | optimal | 3.51811474e+11 | **431 EUR/t** (cap 0 binds) | 0 Mt |
| 2030 | optimal | 3.59087309e+11 | 4.2 EUR/t (cap 60 binds) | 60 Mt |
| 2040 | optimal | 2.87813093e+11 | **0** (1000 backstop slack) | 180 Mt |
| 2050 | optimal | 2.66718630e+11 | **0** | 368 Mt |

Belgian `co2 sequestered` `e_nom_max` / `e_nom_opt` (Mt):

| | 2025 max / opt | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| BEWAL | **0 / 0** | 0 / 0 | 0 / 0 | 0 / 0 |
| BEVLG | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| BEBRU | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

Sequestration sits in the CO2StoP countries (store `e_nom_opt`, Mt):

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| DE | 0 | 39.2 | 118.4 | 197.5 |
| NL | 0 | 9.1 (binds) | 18.2 (binds) | 27.3 (binds) |
| GB | 0 | 11.7 | 43.3 | 143.3 |

Belgian export on existing pipelines (not a new Norway link): 2030 builds `BEWAL → DE` and `BEVLG → NL`; 2050 adds large `BEVLG → NL/GB/FR` capacity (FR is transit; FR/LU stores stay 0).

Vs the 14:03 run with BEWAL 7.1: 2030/2040/2050 objectives move only slightly (3.59037e11 → 3.59087e11; 2.87796e11 → 2.87813e11; 2.66799e11 → 2.66719e11). Pooled-cap behaviour is unchanged (binds 2025/2030, slack from 2040).

BEWAL `CCGT CC`: **0 / 0 / 0 / 51 MW_e** (was 0 / 0 / 0 / 1 195 MW_e with the 7.1 Mt sink). Capture remains eligible via export; the local store was what made the large 2050 CCGT-CC build cheap.

## 8. Issues and fixes

1. TIMES 7.1 Mt/a withdrawn; `apply_co2_store_cap` treats a documented 0 as a fleet ban (inherited vintages included). Guard: `test/test_co2_store_potential.py` (10 passed).
2. 2040 still prints `Warning: Model contains large bounds`; with `BarHomogeneous: 1` it declared Optimal. No export fallback.
3. `nic5.sh pull` discarded 2040/2050 `.nc` (rsync checksum vs the results mount). Forced `--inplace` re-pull.

## 9. Working-tree edits at launch

Geology ramp + Belgian store = 0 + `BarHomogeneous` + 6h + NIC5 `batch`. Not committed. Study config restored to 1h / hmem after this run.

## 10. Publication

Not this run (cheap feasibility solve). No S3, no Explorer, no HTML.

## 11. Critical review

Not a production 1h review. Directional checks for the zero-sink correction only:

- Belgian `e_nom_max` is a stated CSV 0, not a fillna and not TIMES 7.1. **Pass.**
- No Belgian `e_nom_opt`. **Pass.**
- Sequestration is in DE/NL/GB; NL geology binds. **Pass.**
- 2040 converges. **Pass.**
- 2050 Walloon CCGT-CC drops from 1.2 GW_e to 51 MW_e without a local sink. **Noted.**
