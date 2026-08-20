# Solve log — <run name / scenario>

> Fill one copy of this file per solve run and save it as
> `docs/logs/YYYY-MM-DD_<scenario>_<tags>.md` (date = day the solve was
> launched). Delete this banner and any section that genuinely does not apply
> ("n/a" is also an answer); keep unknowns as "unknown" rather than deleting
> the field — future readers need to know what was *not* recorded.

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | YYYY-MM-DD HH:MM → YYYY-MM-DD HH:MM |
| Operator | who launched / monitored it |
| Run name (`run.name`) | e.g. `scen_demande_haute` |
| Run prefix (`run.prefix`) | e.g. `times-pypsa` (empty for single-run config) |
| Config file(s) | e.g. `config/config.times-pypsa.yaml` (+ `cluster/config_cluster.yaml` on NIC5) |
| Code version | git commit of pypsa-wal (+ reference to the run's working-tree edits, listed in §9 below) |
| Outcome | success / partial (what is missing) / failed |

## 2. Goal of the run

One short paragraph: why this run exists, what question it answers, what
changed relative to the previous run of the same scenario (new TIMES vd? new
weather year? resolution? cost assumption?).

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd file) | `data/walloon/<file>.vd` |
| Weather year / cutout | e.g. 2010, `europe-2010-sarah3-era5` |
| Snapshots | e.g. 2010-01-01 → 2011-01-01, 8760 h |
| Sector time resolution | e.g. `1h` |
| Planning horizons / foresight | e.g. 2025–2030–2040–2050, myopic |
| Spatial clustering | e.g. `custom_busmap_BE` (`adm`), 3-node Belgium |
| Countries | e.g. BE FR GB NL DE LU |
| Solver + options | e.g. Gurobi barrier, 16 threads |
| Key scenario overrides | e.g. nuclear retrofit repeatable, agg caps file |

## 4. Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Data retrieval / network build (prepare) | local / NIC5 | cores used, snakemake flags |
| LP solve | local / NIC5 `hmem` | partition, cpus per task, mem requested |
| Post-processing (CSVs, plots) | local / NIC5 | |
| HTML report (pypsa2html) | local | |
| Explorer CSV extraction (ClimAct) | local | env `datapypsa` |

Cluster specifics (if used): node name(s), queue wait time (time between
submission and job start), anything noteworthy about the queue state.

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (launch → results verified) | |
| Prepare (network build) | |
| Push to cluster | |
| Queue wait (cluster) | |
| Solve 2025 / 2030 / 2040 / 2050 | one line per horizon; Gurobi time + total job time |
| Pull results | |
| Post-processing + plots | |
| pypsa2html report | |
| ClimAct extraction | |

If this run’s **resolution or constraint set** differs from the previous run of
the same scenario (1h vs 6h, option B′ on/off, tighter caps, …), add a short
runtime/feasibility comparison here or in §9. Do not leave it as tribal
knowledge — see
[`2026-08-18_scen_demande_haute_2010_6h.md`](2026-08-18_scen_demande_haute_2010_6h.md)
§5.1 for the expected level of detail.

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size (rows / cols / nonzeros) | per horizon if it varies |
| Peak RAM per solve | from `logs/*_memory.log` (MEM column max) |
| Peak RAM local phases | if observed |
| Disk footprint | resources/ and results/ sizes |

## 7. Results

| Horizon | Status | Objective (EUR/a or model units) |
|---|---|---|
| 2025 | optimal | |
| 2030 | optimal | |
| 2040 | optimal | |
| 2050 | optimal | |

Local result folders:

- Networks: `results/<prefix>/<scenario>/networks/`
- CSVs / plots: `results/<prefix>/<scenario>/{csvs,graphs,graphics,maps}/`
- HTML report: `results/<prefix>/<scenario>/html/index.html`

## 8. Publication (Wallonie Explorer / S3)

| Item | Value |
|---|---|
| Raw results on S3 | `s3://intervectoriel/test/pypsa_raw_results/<UPLOAD_ID>/` |
| Scenario folder on S3 | `s3://intervectoriel/test/scenarios/<type>__<label>__YYYYMMDD>/` |
| Explorer display label | `<label> (<type>) - DD/MM/YYYY` |
| Explorer CSVs | 49 in `pypsa/`, 3 in `strategy/` (verify with `aws s3 ls … \| wc -l`) |
| TIMES vd staged | yes/no — `explorer/times/<file>.vd` |
| Verified in Explorer dropdown | yes/no (+ "Clear cache" needed?) |

## 9. Issues encountered and fixes

Bulleted list: symptom → cause → fix (and where documented, e.g. the run's
§9, cluster notes). Include aborted attempts (OOM, quota, crashes) — they are the
most useful part of the log for the next run.

## 10. Follow-ups / pending

What remains to be done or watched: known limitations triggered by this run,
comparisons to make, things to backport or commit.
