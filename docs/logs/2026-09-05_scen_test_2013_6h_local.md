# Solve log — scen_test_2013_6h (local 6h verification run)

## 1. Identification

| Field | Value |
|---|---|
| Date of run (start → end) | 2026-09-05 12:57 → 13:15 CEST (18m19s, third attempt — see §9) |
| Operator | Claude agent (supervised by sylvain) |
| Run name (`run.name`) | `scen_test_2013_6h` |
| Run prefix (`run.prefix`) | `walloon` |
| Config file(s) | `config/config.walloon.yaml` + `config/config.test6h.yaml` + overlay `scen_test_2013_6h` in `config/scenarios.walloon.yaml` |
| Code version | pypsa-wal `development_plan` @ `f948c56b` + the two workflow fixes in §9. pypsa2html @ `83a59b0`. |
| Outcome | **4/4 optimal.** Verification run, not decision-grade: 2013 weather and 6h resolution. |

## 2. Goal of the run

Verify, end to end and cheaply, the four changes made after the review of
[`20260905_walloon_scen_demande_haute`](2026-09-04_scen_demande_haute_2010_1h_v2.md):

1. **Cost learning** — every Walloon `investment` override now follows
   technology-data's own rate instead of sitting flat (F1, `ecbe3215`).
2. **Import cap (item 6a) on** — and, above all, *feasible* (F3, `f948c56b`).
3. **PV split in the capacity charts** (F1 reporting half, pypsa2html `83a59b0`).
4. **Base-year forced-build reconciliation** (`0def1c0a`), which had never been
   in a solved run.

2013 weather because that is the cutout cached locally, so no 6.6 GB download
and no renewable-profile rebuild; 6h so the whole thing costs ~18 minutes.
Everything else mirrors `scen_demande_haute`, under a run name that cannot
overwrite the production tree.

## 3. Main parameters

| Parameter | Value |
|---|---|
| Scenario (TIMES vd) | `scen_central_demande_haute_v2_260903_0309.vd` (same as production; symlinked from the downloaded S3 tree) |
| Weather year / cutout | 2013, `europe-2013-sarah3-era5` (cached, no download) |
| Snapshots | 2013-01-01 → 2014-01-01 |
| Sector time resolution | `6h` |
| Planning horizons / foresight | 2025 – 2030 – 2040 – 2050, myopic |
| Spatial clustering | `custom_busmap_BE` (`adm`), 3-node Belgium |
| Solver | Gurobi barrier, `Crossover 0`, `BarHomogeneous 1`, 12 threads |
| Key overrides | **item 6a ON** (2.94 / 6.47 / 10.0 TWh); rooftop share on; industry CC floor on; `retrofit_nuclear_once: false`; `html_publish.enable: false` |

## 4. Execution — where and how

Everything local, no cluster, no S3. `--cores 16`, `mem_mb=100000`.

```bash
export GRB_LICENSE_FILE=/home/sylvain/.gurobi/gurobi.lic MPLBACKEND=Agg
snakemake --configfile config/config.walloon.yaml config/config.test6h.yaml \
          --cores 16 --resources mem_mb=100000 -call
```

Both exports are load-bearing — see §9.

## 5. Timings

| Step | Duration |
|---|---|
| Total workflow (third attempt) | **18m19s** (12:57:00 → 13:15:19), 87 jobs |
| Solve 2025 | barrier 165.3 s, 115 iterations |
| Solve 2030 | barrier 273.2 s, 140 iterations |
| Solve 2040 | barrier 286.2 s, 152 iterations |
| Solve 2050 | barrier 190.9 s, 104 iterations |

Comparable to the 2026-09-03 6h smoke test (42m47s), which built the scenario
tree from scratch; here the weather-derived artefacts were cached.

## 6. Resource usage

| Metric | Value |
|---|---|
| LP size (2050) | 7 254 381 rows · 3 615 764 columns · 17 413 462 nonzeros |
| Peak RAM per solve | 7.8 / 9.0 / 8.8 / 8.7 GB (2025/2030/2040/2050) |

## 7. Results

| Horizon | Status | Objective |
|---|---|---|
| 2025 | Optimal | 3.31393538e+11 |
| 2030 | Optimal | 3.42817415e+11 |
| 2040 | Optimal | 2.75334111e+11 |
| 2050 | Optimal | 2.46155486e+11 |

## 8. Publication

None. No S3 upload, no public HTML (`html_publish.enable: false`). Report built
locally at `results/walloon/scen_test_2013_6h/html/`.

## 9. Issues encountered and fixes

Three failures, **none of them in the model** — two environment traps and one
latent workflow bug that the review would otherwise have blamed on the model.

- **Attempt 1 (12:33, died in 90 s): Gurobi fell back to its size-limited
  licence.** `GurobiError: Model too large for size-limited license`.
  `GRB_LICENSE_FILE` is exported from `~/.bashrc`, which a non-interactive
  shell does not source, so `gurobipy` used its built-in 2 000-variable
  restricted licence. The real licence is valid (academic, expires
  2026-10-17). **Fix:** export it before launching. This will bite any
  non-desktop launch — cron, CI, an agent shell, `ssh` without a login shell.
- **Attempt 2 (12:44, died after the 2025 solve): every `plot_*` rule
  aborted.** `qt.qpa.plugin: Could not find the Qt platform plugin "wayland" /
  "xcb"` → `SIGABRT`, 12 rules in one minute. `matplotlibrc` set no backend, so
  matplotlib chose an interactive Qt backend because `DISPLAY` was set, and no
  Qt platform plugin was reachable. **Fix in tree:** `backend: Agg` in
  `matplotlibrc`. The workflow writes every figure to a file and shows none, so
  an interactive backend is never wanted.
- **The HTML report was built from the *previous* run's summary CSVs.**
  `generate_html_report` declared only the networks as inputs, but pypsa2html
  reads `csvs/` too and caches each file on first use. Snakemake was therefore
  free to start the report alongside `make_global_summary`; the report read the
  3 Sept tables, cached them, and wrote pages at 13:14:51 whose file timestamps
  looked fresh. The BEWAL capacity page showed **4 088 MW of ground PV and zero
  rooftop** — the 3 Sept fleet — while `csvs/nodal_capacities.csv` on disk was
  correct. **Fix in tree:** the summary CSVs are now declared inputs of
  `generate_html_report` (`rules/pypsa2html.smk`). Rebuilt; the page now matches
  the networks exactly.

  This one is worth keeping in mind for **published** runs: on a fresh scenario
  tree there is nothing stale to read and the bug is invisible, so it only
  appears when a scenario is re-run — which is every production re-run.

## 10. Follow-ups / pending

- Put `GRB_LICENSE_FILE` and `MPLBACKEND=Agg` into `instructions.md`'s local-run
  section (and ideally into `cluster/nic5.sh` / a launcher) so a non-interactive
  launch is reproducible.
- Re-check whether the 20260905 production report was affected by the
  `generate_html_report` race before citing any figure from it.
- 2013/6h numbers are **not** comparable with the 1h/2010 production run; this
  log is a mechanism check, not a result.

## 11. Critical review

Verification only — this run exists to check mechanisms, not to produce Walloon
results. `review_run.py`: **PASS 154 · INFO 26 · WARN 23 · FAIL 2**.

### The four changes under test

| Change | Observable | |
|---|---|---|
| **Cost learning** (`ecbe3215`) | new-vintage `capital_cost` 2025→2050: `solar` −27.6 %, `solar-hsat` −25.6 %, `solar rooftop` −38.3 %, `onwind` −9.9 %. Every one fell; on the 20260905 run every one rose | pass |
| **Import cap** (`f948c56b`) | `import_limit_BEWAL` present in all three capped horizons with its dual. 2030 2.90 vs 2.94 TWh (slack); **2040 6.47 vs 6.47, binding, mu −6.50 EUR/MWh**; **2050 10.00 vs 10.00, binding, mu −5.39 EUR/MWh**. `review_run.py` 4.3b recomputes the inflow independently and agrees | pass |
| — feasibility | **4/4 optimal.** The predicted failure mode (2050 CO₂ × import cap) did not materialise, and the shadow price is only ~5–7 EUR/MWh, so the cut was cheap rather than painful | pass |
| **PV split** (pypsa2html `83a59b0`) | BEWAL capacity page carries three series — ground 0.90/0.90/0.38/0.00, rooftop 1.77/4.60/8.09/15.01, tracking 0.01/1.00/1.96/1.94 GW — plus `solar thermal` separately; the CF chart keeps one folded `Solar` bar | pass (after the §9 fix) |
| **Base-year reconciliation** (`0def1c0a`) | BEWAL 2025 solar-all is **2 681 MW** against the 2 668 MW pin (inside the 0.5 % corridor) instead of 4 088 MW, and BEWAL/solar-all no longer FAILs. The 2025 ground/rooftop split is the intended 898 / 1 770 MW | pass |

### What the cost fix does to F1

Walloon PV now **grows monotonically** instead of collapsing:

| BEWAL, MW | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| `solar` (ground) | 898 | 897 | 382 | 0 |
| `solar-hsat` | 13 | 999 | 1 957 | 1 944 |
| `solar rooftop` | 1 770 | 4 604 | 8 090 | **15 012** |
| **total** | **2 681** | **6 500** | **10 429** | **16 956** |
| 20260905 run (1h/2010) | 4 088 | 7 945 | 8 035 | **6 554** |
| TIMES vd | — | 6 898 | 15 419 | 17 375 |

2050 lands within **2.4 %** of the TIMES total, and the rooftop share reaches
88.5 % against a pin of 80.1 % — i.e. the item-8 constraint has stopped binding
and rooftop is now built because it is economic. That is exactly what the F1
decision box predicted would happen once rooftop PV fell to ~60 EUR/MWh.

**Caveat, and it matters:** three things changed at once (costs, import cap,
weather year/resolution), so this is not a clean attribution to the cost fix.
The direction is unambiguous; the magnitude is not transferable to 1h/2010.

### The two remaining FAILs

Both are 2025 onshore wind, and both are the **documented data conflict**, not a
code defect: BEWAL onwind total 1 694 MW vs the 1 560 MW pin, and BE onwind
3 480 vs 3 337. The extendable tranche is **0** — the reconciliation clipped
everything it could — so the residue is the standing IRENASTAT fleet exceeding
the Energy-Balance pin by ~134 MW. This needs the fleet-source decision recorded
in §10 of the production log, not more code.

The four 2025 aggregate FAILs of the 20260905 run are therefore down to two, and
the two that remain are data.

### Not verified here

F5 (CO₂ trajectory), F8 (solid biomass) and F2 (European VRE decay) are
unchanged and still open. The 23 WARNs are the familiar set — `coal for
industry` above TIMES (+10 to +37 %, the carry-over in item 17), the `enc_pe`
solid-biomass source node (F8), `pac_fe`/`vap_se` Sankey mapping holes, and
Gurobi conditioning warnings in all four horizons.
