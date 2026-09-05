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
| Later runs on this tree | §12 (F5 + the 2050 net-zero probe, **infeasible**) and §13 (F7 + F8, **4/4 optimal**, `review_run.py` FAIL 0). The results tree and `csvs/` now hold **run 3**, not the run described in §5–§7. |

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

- **The energy Sankey's electricity-import arrow was a plug.**
  `_close_energy_graph` derived `imp -> elc_se` from the annual *net* balance of
  the electricity node, so the arrow was whatever closed that node. On BEWAL
  2050 it drew **17.236 TWh** of imports and **zero** exports, against a
  physical 10.0 in / 2.0 out — while this very run was solving a 10 TWh import
  cap, met exactly. The node balanced perfectly, so nothing warned.
  **Fix:** pypsa2html `5793e1a` (D20) reads trade from the model's own
  cross-border branches. The 2050 arrows are now 10.000 in / 1.992 out, and
  2040 is 6.470 — both on the cap to the third decimal.
  The mapping error the plug was absorbing is now **visible**:
  `graph_imbalances` reports `elc_se` short by 5.30 TWh (2040) and 9.23 TWh
  (2050). It traces to `elc_fe -> res` carrying both the specific-electricity
  code and a second family of heat-pump / electric-heater codes whose sum
  exceeds what the network withdraws. That is a taxonomy question for the
  code-set owner — logged, not papered over.

## 10. Follow-ups / pending

- Put `GRB_LICENSE_FILE` and `MPLBACKEND=Agg` into `instructions.md`'s local-run
  section (and ideally into `cluster/nic5.sh` / a launcher) so a non-interactive
  launch is reproducible.
- Re-check whether the 20260905 production report was affected by the
  `generate_html_report` race before citing any figure from it.
- 2013/6h numbers are **not** comparable with the 1h/2010 production run; this
  log is a mechanism check, not a result.
- **`elc_se` mapping hole (5.3 / 9.2 TWh in 2040 / 2050)** — now unhidden by
  pypsa2html D20. Needs the `elc_fe -> res` code set resolved with ClimAct
  before the energy Sankey is shown to anyone.
- **2050 net zero needs DAC or less aviation** (§12.1). `sector.dac: false`
  makes biomass the only carbon sink, ceiling ~127 Mt, against ~230 Mt of
  fossil combustion of which aviation kerosene is 106 Mt. Decide whether to
  enable DAC, revisit the exogenous aviation/HVC demand, or state plainly that
  the modelled system does not reach net zero by 2050.
- **F8(b) is a data-owner call** (§13). Walloon pellet imports were specified
  twice; `sector.solid_biomass_import` is now off and the Valbiom
  `solid biomass transported` row (2.0/2.0/2.25/3.0 TWh) is the single
  channel. Confirm with Valbiom/ICEDD, or flip it and zero the other row —
  never both.

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

*Superseded below:* F5 was closed the same afternoon (§12) and F7/F8 that
evening (§13). F2 remains open.

## 12. F5 — the CO₂ trajectories, and the net-zero probe that failed

Run 2 of this scenario tree, 14:16 → 14:35 CEST, same code except the CO₂
config. Two changes, one of which was a deliberate experiment.

**The fix.** `budget_national` now carries the same series as the system
`co2_budget` — 0.648 / 0.450 / 0.250 / 0.050 — instead of the slacker
0.648 / 0.648 / 0.450 / 0.050. Until now the global cap was always the tighter
of the two, so every national cap was inert after 2025 and the agreed Walloon
trajectory was never enforced. The `config:budget_national` anchors in
`config/input_parameters_for_models.csv` moved with it (64.8 @2025 / 45.0 @2030
/ 25.0 @2040 / 5.0 @2050), keeping `build_common_parameters.py --check` green;
the 2026-07-26 literature reading is preserved in that row's note. Full
reasoning in the F5 box of
[`2026-09-04_scen_demande_haute_2010_1h_v2`](2026-09-04_scen_demande_haute_2010_1h_v2.md).

**The experiment.** `co2_budget` 2050 was set to **0.000** — net zero for the
modelled system — while `budget_national` 2050 stayed at the agreed 5 %. Each
country may still emit 5 % gross; the system as a whole may not.

| Horizon | Status | Objective | vs. run 1 |
|---|---|---|---|
| 2025 | Optimal | 3.31393538e+11 | identical (2025 caps unchanged) |
| 2030 | Optimal | 3.45394874e+11 | **+0.75 %** |
| 2040 | Optimal | 2.74047557e+11 | **−0.47 %** |
| 2050 | **Infeasible** | — | (2.46155486e+11) |

2030 is the price of the fix: 2.6 bn EUR/a to make the national caps bite.
2040 is *cheaper* despite its own cap tightening from 0.450 to 0.250 — the
myopic path effect, since the tighter 2030 solve builds clean capacity that
2040 inherits. The 2040 national caps now shift 8.8 Mt more into BECCS
(58.07 → 66.84 Mt captured) at an unchanged 567.67 Mt global cap.

### 12.1 Why 2050 net zero is infeasible — and it is not the solver

Gurobi's homogeneous barrier returned a primal-infeasibility certificate after
100 iterations / 176 s: primal residual pinned at 6e+06 while the objective ran
away to 4e+19, ending `Infeasible model`. Not a numerical abort — `Crossover 0`
and `BarHomogeneous 1` were already on.

**Control.** The 2050 brownfield network was re-solved with `CO2Limit` put back
to 113.53 Mt and *nothing else changed* — same inherited 2040 fleet, same
national caps, same import cap. It converged to **2.46589868e+11** (+0.18 % on
run 1, which is the changed 2040 inheritance). So the cap is the sole cause;
the new 2040 build is not.

**The mechanism is structural.** From run 1's 2050 network, the atmosphere
balance is:

| | Mt/a |
|---|---:|
| gross emissions | 235.1 |
| — of which kerosene for aviation | **106.2** |
| — HVC to air | 34.8 |
| — urban decentral + rural gas boilers | 32.5 |
| — urban central gas CHP (±CC) | 15.7 |
| — CCGT (±CC) | 9.7 |
| — oil refining | 8.6 |
| sinks: solid biomass for industry CC | −112.1 |
| sinks: biogas to gas | −9.5 |
| **net** | **113.5** = the cap, binding at −377.3 EUR/t |

The sink ceiling is the biogenic carbon itself: 336.9 TWh of solid biomass
(330.9 domestic-limit + 6.0 import) × 0.348365 tCO₂/MWh ≈ **117 Mt**, plus
~9.5 Mt from biogas ≈ **127 Mt**. Run 1 already captured 112.1 of the 117 —
96 % of the ceiling — and `biomass limit` binds at −926.7 EUR/MWh.

**Synthetic kerosene does not help.** Fischer-Tropsch and biomass-to-liquid are
both present and extendable (built at 0 GW). But FT draws its carbon from
`co2 stored`, which is the same biogenic carbon: a tonne can be sequestered
(−1 t) *or* displace a tonne of fossil fuel (−1 t), never both. Net zero
therefore reduces to **fossil combustion ≤ ~127 Mt** against ~230 Mt realised.
With `sector.dac: false` there is no sink that is not biomass, so the system
would have to halve fossil combustion across six countries from the 2040 fleet
it inherits. It cannot.

`co2_budget` 2050 is back at **0.050**. Net zero is a DAC question or an
aviation/HVC demand question, not a cap question — and it is the sharpest
result this verification run produced.

## 13. F7 and F8 — the base-year fleet and the Walloon biomass

Run 3 of this scenario tree, **15:00:35 → 15:24:09 CEST (23m34s, 111 jobs,
4/4 optimal, zero failed rules)**. Same command, same environment exports as §4.
`co2_budget` 2050 is back at 0.050 (§12.1); `budget_national` keeps the F5
series. On top of that, F7 and F8.

| Horizon | Objective | vs. run 1 | vs. run 2 (F5 only) |
|---|---|---:|---:|
| 2025 | 3.31681512e+11 | +0.087 % | +0.087 % |
| 2030 | 3.45681582e+11 | +0.83 % | +0.083 % |
| 2040 | 2.77791268e+11 | +0.89 % | +1.37 % |
| 2050 | 2.51682282e+11 | +2.25 % | — (run 2 was infeasible) |

Barrier 150 / 141 / 123 / 110 iterations in 226 / 309 / 231 / 225 s; peak RAM
8.2 / 8.6 / 8.6 / 8.3 GB; 2050 LP 7 245 620 rows · 3 611 383 columns ·
17 394 482 nonzeros. Every number moves the same way and by the same order of
magnitude: each fix removes an over-allocation, so the system gets slightly
more expensive without restructuring.

**`review_run.py`: PASS 156 · INFO 26 · WARN 24 · FAIL 0** — against
**PASS 154 · INFO 26 · WARN 23 · FAIL 2** in run 1. The last two FAILs are
closed.

### 13.1 F7 — the standing fleet, and a dependency that was never declared

All **14** of the 2025 aggregate pin checks are now `ok`, across all six
countries:

| 2025 | total MW | pin | extendable tranche | corridor (+0.5 %) |
|---|---:|---:|---:|---:|
| BEWAL onwind | 1 568 | 1 560 | 8 | 1 568 |
| BE onwind | 3 354 | 3 337 | 1 091 | 3 354 |
| BEWAL solar-all | 2 681 | 2 668 | 395 | 2 681 |
| BE solar-all | 9 800 | 9 751 | 4 347 | 9 800 |

The two FAILs were **one** finding. `add_CCL_constraints` subtracts a region
row from its parent, so the `BE` onwind row covers only BEBRU + BEVLG at
3 337 − 1 560 = 1 777 MW, and those two land on 1 785.9 — inside the corridor.
The entire BE overshoot was the BEWAL residue seen from the parent row.

That residue was never a Walloon measurement. `add_existing_renewables`
distributes **one IRENASTAT country total** with
`fraction = p_nom_max / p_nom_max.sum()` — in proportion to *remaining land
potential*, not to where the turbines stand. Wallonia has the most free land in
Belgium, so it was handed the largest slice of the Belgian onshore fleet. Every
other country's 2025 onwind pin is already "the model's own fleet"
(powerplantmatching + `custom_powerplants.csv`); BEWAL was the only row sourced
independently — the Walloon Energy Balance — which is precisely why it was the
only row that broke.

`electricity.baseyear_reconcile_forced_build.scale_standing_fleet` (new,
default **false**) scales the standing vintages onto the pin once the forced
tranche is already at zero. It fired on exactly one node in the whole run:

```
WARNING  scaling the standing BEWAL onwind fleet by 0.9207 (1694 MW -> 1560 MW)
         to meet the measured pin. The 134 MW excess is the IRENASTAT country
         total split by land potential, not a regional observation.
INFO     scaling FR offwind-ac 2025 additions by 1.000 ...
INFO     scaling FR / GB / NL solar 2025 additions by 1.000 ...
```

Scaling is pro rata across the 2005/2010/2015/2020 bins, so the vintage mix —
and therefore the retirement schedule that drives the 2050 cliff in F1 — is
preserved.

**Second defect, found while fixing the first.** Neither the flag nor the caps
file was declared on `rule add_existing_baseyear`: the script read both straight
from `snakemake.config`, so flipping the switch or editing a pin would have left
the brownfield network stale and the change silently inert. This run only picked
the fix up because `prepare_sector_network` re-ran for other reasons. The flag
is now a `param` and the caps file an `input`. Same family as the
`generate_html_report` race in §9 — an undeclared dependency that is invisible
on a fresh tree and only misleads on a *re-run*.

### 13.2 F8 — the domestic potential was counted twice, and so were the imports

**(a) A real code bug.** Measured on the run-1 networks, not inferred: BEWAL
2025 carried `solid biomass` 6.00 TWh **and** `unsustainable solid biomass`
6.00 TWh; 2030 carried 6.00 + 3.18. `update_BEWAL_potentials` wrote the
remainder `potential − upstream` onto the unsustainable generator — correct —
then overwrote the sustainable one with the **full** `potential`, so BEWAL
entered every solve with `2 × potential − upstream` against a 6.0 TWh Valbiom
row. The sustainable leg now keeps its upstream value, so the two sum to the
Valbiom total exactly. The same block also grew the Europe-wide
`unsustainable biomass limit` by the new remainder without removing BEWAL's
previous contribution; it now swaps them.

The 2025 split becomes 0.0 sustainable + 6.0 unsustainable, which is the right
answer rather than an artefact: the Europe-wide 2025 `biomass limit` is `<= 0`,
so sustainable solid biomass is banned that year (checklist §4.4) and all
Walloon biomass *must* be unsustainable.

**(b) A data decision.** `solid biomass import` (store + link, e_nom
4.0/4.0/4.5/6.0 TWh) and `solid biomass transported` (e_sum_max
2.0/2.0/2.25/3.0 TWh) are two estimates of the same physical flow — imported
pellets for Wallonia — and 2040 used **both**. `sector.solid_biomass_import` is
now **false**; the Valbiom row is the single channel.

Total Walloon solid biomass consumed:

| TWh | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| run 1 (generators + import links) | 7.74 | 9.63 | **12.75** | 6.55 |
| run 3 | **6.00** | **8.00** | **8.25** | 6.39 |
| documented envelope | 8.00 | 8.00 | 8.25 | 9.00 |

2030 and 2040 now sit exactly on the documented cap; 2050 has slack. The
`enc_pe` Sankey source-node WARN falls from 7.738 / 10.074 / 12.750 / 5.830 to
**6.000 / 7.311 / 8.250 / 5.830** — inside the envelope in every horizon. Zero
`solid biomass import` links remain in any network.

### 13.3 What the F5 fix did once the caps could bite

The point of F5 was to make the national caps mean something. They now do:

| BEWAL `co2_limit_per_country` dual, EUR/t | 2030 | 2040 | 2050 |
|---|---:|---:|---:|
| run 1 | −0.0 | −0.0 | −0.0 |
| run 3 | **−63.9** | **−29.2** | −0.0 |

2050 stays slack because both caps are 5 % there and the global one binds first
(−377.3 EUR/t). `biomass limit` duals move to −37.7 / −51.9 / **−982.0**
EUR/MWh and `import_limit_BEWAL` to −0.69 / −10.68 / −3.49 EUR/MWh — the 2040
import cap is now roughly twice as painful as in run 1, which is what removing
4.5 TWh of Walloon pellets should do.

### 13.4 Caveat

Three things changed at once again (CO₂ trajectory, base-year fleet, biomass),
so **no single number here is attributable to one fix**. The directions are
unambiguous and each was verified in isolation by unit test; the magnitudes are
not transferable to 1h/2010. The BEWAL capacity mix moved materially — 2040
`solar-hsat` 1 957 → 2 984 MW, rooftop 8 090 → 11 640 MW; 2050 rooftop
15 012 → 12 885 MW and onwind 6 500 → 6 196 MW — and that is a joint effect,
not a biomass result.

### 13.5 Still open after this run

- **F2** (European VRE decay after 2030) — untouched.
- **2050 net zero** — §12.1: needs DAC or a smaller aviation/HVC demand.
- **F8(b) needs the data owner's sign-off.** Keeping the other pellet channel
  instead would give BEWAL 10.0 / 10.0 / 10.5 / 12.0 TWh rather than
  8.0 / 8.0 / 8.25 / 9.0. Only one may be active.
- The 24 WARNs are the familiar set: `coal for industry` above TIMES
  (+9.8 to +36.7 %, item 17), the `elc_se` mapping hole (§9, now 7.7 / 9.6 TWh),
  `pac_fe` / `vap_se` / `enc_pe` Sankey nodes, BEWAL electric load −0.8 to
  −1.0 % against TIMES, VRE build-rate warnings, and Gurobi conditioning
  warnings in all four horizons.
