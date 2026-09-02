# Solve log — scen_demande_haute @ 2010, 6h (item 2: nodal CO₂ sinks)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-09-02 14:03 → 15:00 |
| Operator | Cursor agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_demande_haute` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml` + `cluster/config_cluster.yaml` on NIC5 |
| Code version | working tree on `master` at `b43ad14e` plus item-2 edits (not committed) |
| Outcome | **success** — 4/4 optimal. No Northern-Lights export needed. |

## 2. Goal of the run

Cheap 6h four-horizon solve of improvement-plan item 2: restore the per-node
CO₂StoP geology ramp (`816be537`, reverted `dbca25df` after a 2040 numerical
abort) **with** `BarHomogeneous: 1`, and give Belgium a documented domestic
`e_nom_max` (BEWAL 7.1 Mt/a from TIMES; BEVLG/BEBRU 0). No Northern-Lights
export link. Question: does 2040 converge, and does capture become eligible
in Wallonia?

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
| Key scenario overrides | geology ramp 0/0/60 then 1000; `max_size` 2.5 Gt; BEWAL CO₂ store 7.1 Mt/a |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Prepare | local | 6 jobs (time aggregation + 4 horizons + 2025 brownfield), ~1.5 min after a store-name fix |
| LP solve | NIC5 **`batch`** (`nic5-w015`) | 16 cpus, 100 GB, wall 480 min. Not hmem. |
| Post-processing | skipped | cheap feasibility solve |
| HTML / Explorer | skipped | |

Queue wait was short (idle batch nodes). 2040 complementarity plateaued around iter 200–260 then still returned Optimal.

## 5. Timings

| Step | Duration |
|---|---|
| Prepare (network build) | ~1.5 min (second pass; first pass missed the vintaged store name) |
| Push to cluster | ~20 s |
| Queue wait | seconds |
| Solve 2025 | 157 iter / **325 s**, objective 3.51811468e+11 |
| Solve 2030 | 110 iter / **358 s**, objective 3.59036691e+11 |
| Solve 2040 | 265 iter / **792 s**, objective 2.87796077e+11 |
| Solve 2050 | 144 iter / **405 s**, objective 2.66799313e+11 |
| Full solve chain | ~41 min (14:19 → 15:00) |
| Pull | ~20 s (rsync checksum false-negatives on the mount; forced re-pull of the four `.nc`) |

Vs the 30 Aug 1h failure: 2040 aborted after ~30–60 min with *"Numerical trouble / consider BarHomogeneous"*. This 6h 2040 finished in 13 min with that flag on.

## 6. Resource usage

| Metric | Value |
|---|---|
| Snapshots | 1460 (6h) |
| Peak RAM per solve | **~8 GB** (`memory.log` MEM max ~8.1 GB on 2040) — 100 GB request was ample on a 252 GB batch node |
| Disk | ~43–67 MB per solved 6h network |

## 7. Results

| Horizon | Status | Objective (EUR/a) | `co2_sequestration_limit` dual | seq. used |
|---|---|---:|---:|---:|
| 2025 | optimal | 3.51811468e+11 | **431 EUR/t** (cap 0 binds) | 0 Mt |
| 2030 | optimal | 3.59036691e+11 | 4.3 EUR/t (cap 60 binds) | 60 Mt |
| 2040 | optimal | 2.87796077e+11 | **0** (1000 backstop slack) | 181 Mt |
| 2050 | optimal | 2.66799313e+11 | **0** | 369 Mt |

Belgian `co2 sequestered` `e_nom_max` / `e_nom_opt` (Mt):

| | 2025 max / opt | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| BEWAL | 7.1 / **0** | 7.1 used | 7.1 used | 7.1 used |
| BEVLG | 0 / 0 | 0 | 0 | 0 |
| BEBRU | 0 / 0 | 0 | 0 | 0 |

Wallonia’s 7.1 Mt/a store **binds from 2030**. The pooled EU scalar stops binding from 2040 (the geology ramp did its job). GB/DE/NL absorb the rest.

BEWAL `CCGT CC`: **0 / 0 / 0 / 1 195 MW_e**. Capture is eligible; 2040 still does not build the plant (the plan’s prediction: then the gap is the missing retrofit, not the sink). 2050 does build ~1.2 GW_e.

## 8. Issues and fixes

1. First `add_existing_baseyear` pass did not apply the Belgian cap: brownfield vintages the store to `BEWAL co2 sequestered-2025`. `apply_co2_store_cap` now matches on carrier+bus. Re-prepared 2025 brownfield before push.
2. 2040 printed `Warning: Model contains large bounds` and complementarity sat near 1e-3 for ~50 iterations; with `BarHomogeneous: 1` it still declared Optimal. No export fallback.
3. `nic5.sh pull` discarded the four `.nc` (rsync checksum vs the results mount). Forced a second rsync of those files.

## 9. Working-tree edits at launch

Geology ramp + Belgian store caps + `BarHomogeneous` + 6h + NIC5 `batch`. Not committed.

## 10. Publication

Not this run (cheap feasibility solve). No S3, no Explorer, no HTML.

## 11. Critical review

Not a production 1h review. Directional checks for item 2 only:

- Belgian `e_nom_max` is a stated CSV value, not a fillna. **Pass.**
- 2040 converges with the geology ramp + `BarHomogeneous`. **Pass.**
- Walloon sink is used (7.1 Mt from 2030). **Pass.**
- 2040 CCGT-CC still 0 MW — as the plan warned, do not pin TIMES 1 740 MW until this is understood as a retrofit gap (item 2 / 9). **Noted.**
