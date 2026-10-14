# scen_central — import cap on the annual NET balance (NIC6, 1 h, weather 2010)

**Status (14 Oct 2026): DONE. 4/4 horizons optimal, landed, pypsa2html published (13 Oct 22:40); critical review written (§11, 14 Oct). Nothing committed. Only `scen_central` was re-run.**
Operator: Claude desktop agent, office computer, on S. Quoilin's instruction. Predecessor: [`2026-10-12_cabinet_batch_new_exports_2010_1h.md`](2026-10-12_cabinet_batch_new_exports_2010_1h.md).

## 1. Goal and change
The `self_sufficiency` import cap (2.94 / 6.47 / 10.0 TWh, 2030 / 40 / 50) bounded `Σ_t max(0, hourly net inflow)` (`Import_p ≥ net_total`, `Import_p ≥ 0`),
a gross-like quantity (2050 of the 7 Sept run: capped 10.0 TWh = 7.6 TWh annual net = 24.5 TWh gross inflow). TIMES bounds imports − exports.
* `scripts/solve_network.py::add_selfsufficiency_constraints`: new key `self_sufficiency.measure`, **default `net_annual`** (absolute mode): `Σ_t w_t · net_total ≤ cap`, no `Import_p`, same `GlobalConstraint-import_limit_<node>` name. `hourly_positive` restores the old behaviour (and the fraction mode always uses it).
* `scripts/walloon_scripts/review_run.py` 4.3b: reports the annual net balance against the cap (FAIL if above) and the hourly-positive figure beside it.
* `test/test_import_limit.py`: 15 cases (new: net offsets exports, hourly measure unchanged, unknown measure refused). `pytest test -q`: 736 passed, 1 skipped.
* No scenario block edited (the default applies to all scenarios; `test_s2_block_mirrors_s1` forbids editing only `scen_central`). **Every scenario re-run from now on gets the net cap**; `scen_demande_haute` and the 12 Oct trees were solved with the old measure.

## 2. Run
Resources unchanged (local prepare dry run: nothing to do). Old tree archived to `results/_archive_batch_20261012/scen_central` and `pypsa-wal-archive/batch_20261012/scen_central` (NIC6).
Push + `solve` on NIC6 (40 cores / 75 000 MB, Gurobi 32 threads, 6 h limit), 18:43 → ~22:25, **7 of 7 steps done**; solver logs show `measure=net_annual` and the three caps applied.
Objectives (`Optimal objective`): 2025 3.35336219e11 (identical to 12 Oct), 2030 3.72882496e11, 2040 2.63609969e11, 2050 2.84795332e11.
Landing: `postprocess` 11 steps, `ptx_report`, `review_run`, `check_heat_profile_fidelity` (largest residual 1.9e-6 TWh). pypsa2html 91 pages, 2 min, 3.6 GB.

## 3. Result against the 12 Oct central (same inputs, old measure)
BEWAL, TWh/a (recomputed from the networks: arriving flows, AC + DC, includes Flanders and Brussels):

| | 12 Oct net / hourly+ / exports | now net / hourly+ / exports | cap |
|---|---|---|---|
| 2030 | −1.09 / 2.94 / 4.03 | −0.74 / 3.32 / 4.06 | 2.94 (**not binding**, μ = 0) |
| 2040 | 4.89 / 6.47 / 1.58 | **6.47** / 11.44 / 4.97 | 6.47 (binding, μ −3.92 €/MWh) |
| 2050 | 6.48 / 10.00 / 3.52 | **10.00** / 14.34 / 4.34 | 10.00 (binding, μ −0.75 €/MWh) |

| BEWAL | year | Δ objective bn | Δ mean price | Δ CCGT MW | Δ CCGT CC MW | Δ ground PV MW | Δ battery MW | capture Mt |
|---|---|---:|---:|---:|---:|---:|---:|---|
| central | 2030 | −0.00 | −0.0 | −55 | 0 | 0 | 0 | 1.25 (1.30) |
| central | 2040 | −0.13 | −4.1 | +606 | −478 | 0 | −385 | 6.00 (6.00) |
| central | 2050 | +0.07 | −1.0 | +606 | −890 | −1 870 | −873 | 6.50 (7.03) |

Reading: the looser cap lets the model import ~1.6 TWh (2040) and ~3.5 TWh (2050) more net, and use the exports it did not dare to make; CCGT with CC disappears (0 MW, 0.00 Mt) in 2040 and 2050, plain CCGT +606 MW, 2050 ground PV −1.9 GW, batteries −0.4 / −0.9 GW. Objective moves by ≤ 0.13 bn.
`review_run.py`: 170 PASS / 15 WARN / 10 FAIL = the nine known foreign-nuclear rows (F11) + the `tes_se` standing-loss false positive (F10, 2050). Not done: no §11 critical review, no comparison with TIMES prices, the S2/other scenarios not re-run, no Explorer / S3 upload (not asked).

## 4. Published (internal)
https://pypsa.squoilin.eu/scen_central_20261013/ — hub, pypsa2html report and Sankey all HTTP 200 (the 20261012 page stays online for comparison). S3 and Explorer: **not** uploaded.

**14 Oct update, same URL (overwritten).** The pypsa2html report was rebuilt and re-uploaded with the district-heating pages added to *Heat supply* (year view, thermal store through the year, heat by electricity price, "is electric heat worth building?", the last being the R8 test as a chart) and the *Capacities by technology* power-to-heat panel split into heat pumps and resistive heaters. pypsa2html changes are uncommitted in `../pypsa2html` (D25 of its `docs/DESIGN_DECISIONS.md`). Solved networks and numbers unchanged.

## 11. Critical review

**Reviewed by / date:** Claude desktop agent (Sonnet 5.5) for S. Quoilin, 14 Oct 2026. Scripted half: `review_run.py`, `check_heat_profile_fidelity.py`, `ptx_report.csv`.
Judgement half: BEWAL electricity balances recomputed from the solved networks of **both** trees (this run and `results/_archive_batch_20261012/scen_central`) and set against the TIMES `.vd`
(`scen_central_v1_3gw_261009_0910.vd`, region RW) and the indicator CSVs of `html/indicators/`.

**Headline counts:** 170 PASS · 30 INFO · 15 WARN · 10 FAIL (the nine known foreign-nuclear rows, F11 of the 10 Oct log, plus the `tes_se` standing-loss false positive of 2050, F10).

**This run is a controlled experiment.** Against the 12 Oct central it differs by **one thing**: the measure of the import cap. Same `.vd`, same resources, same code otherwise, same cluster, same
solver settings, the `configs/` snapshots are byte-identical (see R3). So every difference below, apart from solver noise (~1e-6 on the objective, 2025 is identical to 8 digits), is caused by that change.

| Level | Verdict |
|---|---|
| 0 provenance | pass with caveat (R3: the config snapshot does not record the cap measure) |
| 0b commit intent | pass |
| 1 solve | pass |
| 2 TIMES soft link | pass with caveats: transferred demands match to 0.00 TWh; heating electricity is +2.4 TWh above TIMES in 2050 because PyPSA computes it (R5) |
| 3 accounting identities | pass |
| 4 constraint compliance | pass (4.3b: the cap binds exactly in 2040 and 2050; foreign-nuclear FAILs are the known F11) |
| 5 realism | pass with caveats (build rates, R6) |
| 6 prices / costs | pass with caveats (one 8 592 EUR/MWh hour in 2040, R4) |
| 7 TIMES consistency | **caveats, the main part of this review** (R1, R2: gas-CCS and PV differ structurally from TIMES) |
| 8 robustness | caveats: CCGT CC and 2050 ground PV are weakly determined (R1, R2) |

### Commit intent (level 0b)

Previous production log: [`2026-10-12_cabinet_batch_new_exports_2010_1h.md`](2026-10-12_cabinet_batch_new_exports_2010_1h.md), HEAD `c31a96f1` + uncommitted edits. **No commit since**; TIMES_PyPSA (`c6f93e2`) and pypsa2html (`c306378`) unchanged.
The only physics change is uncommitted:

| change | class | intended behaviour | observable in this tree | |
|---|---|---|---|---|
| `add_selfsufficiency_constraints`: `measure: net_annual` (default) | physics | cap bounds imports − exports over the year; no `Import_p` | `import_limit_BEWAL` binds on the **net balance**: 6.47 TWh (2040), 10.00 TWh (2050), μ −3.92 / −0.75 EUR/MWh; the hourly-positive figure is 11.44 / 14.34 TWh, i.e. above the cap, as it must be; solver log: `measure=net_annual`, "annual net balance, imports - exports" | pass |
| 2030 cap 2.94 TWh | | slack if the net balance is lower | net balance −0.74 TWh, μ = 0: **the 2030 cap is inactive**, not binding as in the old run | pass, noted |
| `review_run.py` 4.3b, `extract_times_softlink_values.py` comment, tests | review tooling / docs | | 4.3b now prints both quantities | pass |

### Findings

**R1. CCGT with CC has disappeared; the cause is the cap measure, and it widens the gap to TIMES.**
*Observed* (BEWAL; MW_e, TWh): 2040 `CCGT CC` 273 MW_e / 1.55 TWh / 5 676 full-load hours → **0**; 2050 512 MW_e / 1.25 TWh / 2 447 h → **0**. `urban central gas CHP CC` 2050 451 → 370 MW_e (1.20 → 0.94 TWh).
Plain CCGT 2040 +358 MW_e (1 998 → 2 356), gas CHP +176 MW_e; the 2050 gas fleet is the same unabated one (1.81 → 1.68 TWh).

*Why.* The old measure charged every hour with a positive net inflow and gave no credit for exporting in another hour. A tight cap on that quantity made energy imported when it is cheap very costly:
2040 shadow price of the cap **−59.5 EUR/MWh**, annual net import only **4.89 TWh**, 2 893 hours above 150 EUR/MWh in the BEWAL price (mean 132.3 EUR/MWh). With the net measure the same 6.47 TWh can be imported in cheap hours and compensated by 5.0 TWh of exports,
and the cap only costs **−3.9 EUR/MWh**; the price duration flattens (hours above 150 EUR/MWh: 2 893 → 654, mean 132.3 → **98.4**). The evidence for the CC plant in particular:

| 2040, BEWAL | old measure | net measure |
|---|---|---|
| shadow price of the import cap, EUR/MWh | −59.5 | −3.9 |
| BEWAL national CO2 cap dual, EUR/t | −140.9 | −30.8 |
| capture cap (6 Mt) dual, EUR/t | −117.9 | −18.7 |
| effective carbon value in BEWAL (`CO2Limit` + national cap), EUR/t | 252 | 142 |
| mean BEWAL price in the hours the CC plant ran, EUR/MWh | 166 (5 717 h) | – |
| net import / gross inflow / exports, TWh | 4.89 / 6.47 / 1.58 | 6.47 / 11.44 / 4.97 |
| capture, Mt: process / biomass / **gas-for-industry CC** / CCGT CC | 3.67 / 1.82 / 0 / **0.51** | 3.68 / 1.82 / **0.51** / 0 |

* In 2040 the capture cap (6 Mt) binds in both runs. **The same 0.51 Mt/a of capture capacity moved from the power plant to industrial gas CC.** The CC plant won that slot only while electricity was scarce.
* Back-of-envelope with the solved shadow prices (not a re-solve): a CCGT CC avoids 0.329 t CO2/MWh_e; at the capture and storage shadow prices of each run the margin is ≈ 30 EUR/MWh_e (old) against ≈ 26 (new), while its capital adder over a CCGT is 71.5 k EUR/MW_th/yr, i.e.
  22 EUR/MWh_e at 5.7 kh and 37 at 3.4 kh. It paid at 5.7 kh in the old run (break-even ≈ 4.5 kh); with the new, flatter prices and the lower carbon value the break-even is ≈ 5.2 kh. A thin margin disappears first.
* 2050: the carbon value is the same in both runs (`CO2Limit` −653 / −651 EUR/t, national cap and capture cap slack in both), so it is not a carbon-price effect. In the hours above 200 EUR/MWh (2 188 → 2 261 h) the net import rises **3.45 → 5.14 TWh (+1.69)**, which is the CC energy it replaces
  (1.25 + 0.26 TWh of CHP CC); the 2040 plant that existed in the old run (273 MW_e) is also missing from the inherited fleet (myopic chain).
* **TIMES keeps ≈ 1.0 GW (`VAR_Cap`) of CCGT-CCS (a retrofit of existing plants, [`ccs_alignment.md`](../ccs_alignment.md) §1.1) running baseload: 5.68 TWh (2040) and 5.61 TWh (2050).** PyPSA has no retrofit option and now builds none: its CCS gas is 0 TWh against 5.7 TWh in TIMES (the old run had 1.6 / 1.3).
  F1 of the 10 Oct review (the cabinet's "CCS on CCGT from 2040" is not met) is therefore worse, not better, and CCGT CC is a **marginal technology that flips with an unrelated constraint** (earlier vintages: 0 → 3.14 → 0.57 GW, checklist 8).
* Not done: no re-solve with CC forced to isolate the break-even, the figures above are read off duals.

**R2. Solar is lower than before in 2050 and still above TIMES; the balance explains both.**
Ground PV (`solar`): 2040 **6.39 GW / 6.20 TWh, unchanged**; 2050 **13.00 GW → 11.13 GW**, 12.54 → 10.80 TWh (rooftop is a TIMES floor and does not move: 11.10 / 11.98 GW, 10.7 / 11.6 TWh). The old 13.00 GW was the potential cap (`p_nom_max` 13 000 MW), so it was not an optimum; 11.13 GW is the first interior value.
BEWAL electricity balance, TWh/a (TIMES: indicator tables and `.vd`; "on-site PV" = TIMES demand-side PV, counted with rooftop; PyPSA flows are at the BEWAL AC + low-voltage buses; every column closes to < 1e-3 TWh):

**2050**

| TWh/a | TIMES | PyPSA 12 Oct (old cap) | PyPSA now (net cap) | now − TIMES |
|---|---:|---:|---:|---:|
| Nuclear | 23.01 | 22.46 | 22.34 | −0.67 |
| Onshore wind | 13.59 | 13.97 | 14.15 | +0.56 |
| **PV ground** | 4.18 | 12.54 | 10.80 | **+6.62** |
| PV rooftop (+ on-site PV in TIMES) | 12.54 | 11.56 | 11.62 | −0.92 |
| Hydro run-of-river / other RES | 0.49 | 0.29 | 0.29 | −0.20 |
| Gas CCGT **with CCS** | 5.61 | 1.25 | 0.00 | −5.61 |
| Gas CCGT unabated, OCGT | 0.37 | 1.81 | 1.68 | +1.31 |
| CHP / cogeneration, waste | 0.91 | 1.32 | 1.15 | +0.24 |
| **Domestic production** | 60.70 | 65.20 | 62.03 | +1.33 |
| Net imports (imports − exports) | 10.00 | 6.48 | 10.00 | 0.00 |
| **Supply total** | 70.70 | 71.68 | 72.03 | +1.33 |
| Industry | 24.54 | 24.39 | 24.39 | −0.16 |
| Buildings + services, **soft-linked** (appliances, cooking, data centres, cooling) | 19.06 | 19.06 | 19.06 | 0.00 |
| Buildings + services, **heating** (heat pumps, electric heaters, district heat) | 5.17 | 7.23 | 7.61 | **+2.44** (R5) |
| Transport (EV + rail) | 17.87 | 17.88 | 17.88 | +0.01 |
| Agriculture (+ PyPSA's electric machinery 0.27) | 0.06 | 0.34 | 0.34 | +0.27 |
| **Final consumption** | 66.70 | 68.88 | 69.26 | +2.56 |
| Pumped hydro net loss | 0.30 | 0.25 | 0.25 | −0.05 |
| Batteries net loss | 0 | 0.38 | 0.32 | +0.32 |
| Electrolysis / PtX at BEWAL | 0.11 | 0.03 | 0.03 | −0.08 |
| Distribution-grid losses (TIMES: residual of all losses) | 3.59 | 2.14 | 2.16 | −1.43 |

**2040**

| TWh/a | TIMES | PyPSA 12 Oct | PyPSA now | now − TIMES |
|---|---:|---:|---:|---:|
| Nuclear | 7.41 | 7.90 | 7.87 | +0.46 |
| Onshore wind | 13.74 | 14.59 | 14.95 | +1.21 |
| **PV ground** | 4.24 | 6.20 | 6.20 | **+1.96** |
| PV rooftop (+ on-site PV in TIMES) | 12.24 | 10.71 | 10.77 | −1.47 |
| Hydro / other RES | 0.49 | 0.29 | 0.29 | −0.20 |
| Gas CCGT **with CCS** | 5.68 | 1.55 | 0.00 | −5.68 |
| Gas CCGT unabated, OCGT | 3.87 | 8.58 | 8.14 | +4.27 |
| CHP / cogeneration, waste | 0.96 | 0.50 | 1.00 | +0.04 |
| **Domestic production** | 48.63 | 50.33 | 49.22 | +0.59 |
| Net imports | 6.47 | 4.89 | 6.47 | 0.00 |
| Industry | 18.48 | 18.13 | 18.13 | −0.35 |
| Buildings + services, soft-linked | 15.70 | 15.70 | 15.70 | 0.00 |
| Buildings + services, **heating** | 4.39 | 5.61 | 6.00 | **+1.61** (R5) |
| Transport (EV + rail) | 13.31 | 13.31 | 13.31 | 0.00 |
| Agriculture (+ electric machinery 0.27) | 0.06 | 0.34 | 0.34 | +0.27 |
| **Final consumption** | 51.95 | 53.09 | 53.47 | +1.53 |
| PHS + batteries + PtX + grid losses | 3.15 | 2.14 | 2.21 | −0.94 |

(2030, for completeness, with the same method: PyPSA gas 9.0 TWh against TIMES 2.9 + 3.4 TWh of cogeneration and PyPSA industry 7.76 against TIMES 10.70. The difference is TIMES's **industrial cogeneration** (2.94 TWh "Mix"),
which is produced and consumed on site and is not in the PyPSA boundary on either side; it is 0.4 TWh from 2040, hence the −0.35 / −0.16 TWh industry differences above.)

*Why solar went down (2050, old → now).* Net imports **+3.52 TWh** (6.48 → 10.00: Flanders +1.2, ALEGrO +1.3, Brussels +0.7, FR/LU +0.3) replace domestic production **−3.17 TWh**: ground PV −1.74, CCGT CC −1.25, CHP CC −0.26, other gas −0.04 (CCGT −0.13, CHP without CC +0.09), nuclear −0.12, wind +0.18, rooftop +0.06;
the remaining 0.35 TWh is heating electricity (+0.38: district-heating resistive heater +0.30, heat pumps +0.08). Battery discharge falls 9.08 → 7.78 TWh (−1.3). The imports arrive at both ends of the price scale: +2.4 TWh in hours below 150 EUR/MWh (what the PV used to supply) and +1.7 TWh above 200 (what the CC used to supply).
The cap's dual in 2050 is only **−0.75 EUR/MWh**: ground PV and an extra TWh of import cost the same at the margin, so the 11–13 GW of ground PV is a **flat optimum** (see "do not publish").

*Why solar is still above TIMES (2050).* TIMES has the same ground-PV ceiling (13 GW, `PAR_CapUP`) and uses 4.27 GW, so the potential is not what separates them. The +5.70 TWh of PV (22.42 against 16.72) is the sum of the structural differences of the balance:

| bridge, 2050, TWh/a | |
|---|---:|
| gas: TIMES's 5.61 TWh CCGT-CCS has no counterpart in PyPSA (−5.61), PyPSA runs 1.31 TWh more unabated gas and 0.24 more CHP | +4.06 |
| nuclear: 22.34 against 23.01 | +0.67 |
| onshore wind: +0.56 against TIMES | −0.56 |
| hydro / other RES | +0.20 |
| final consumption +2.56 (heating electricity +2.44, PyPSA's electric agricultural machinery +0.27, TIMES's on-site industrial CHP −0.16, everything soft-linked 0.00) | +2.56 |
| batteries +0.32, PHS −0.05, PtX −0.08 | +0.19 |
| grid losses: PyPSA 2.16 against TIMES's residual 3.59 | −1.43 |
| imports | 0.00 |
| **PV above TIMES** | **+5.70** |

So the surplus PV is, first, the CCS-gas energy PyPSA does not have (R1), then a higher consumption (heating electricity, R5: PyPSA computes it from the TIMES heat, it is not transferred), then storage losses TIMES does not have; a lower loss term partly offsets. In 2040 the same reading gives +0.49 TWh of PV (ground +1.96, rooftop −1.47):
the production totals agree to 0.6 TWh, PyPSA has 4.3 TWh more unabated gas and 5.7 TWh less CCS gas than TIMES, and 1.5 TWh more demand.
Not checked: whether the PV investment cost in the TIMES export equals the shared CSV (325–357 EUR/kW in 2040–50); if TIMES's ground PV is dearer, that is a second reason (R-follow-up 4).

**R3. The cap measure is not in the effective config, and "imports" are not what the word says.**
(a) `configs/config.base_s_adm___2050.yaml` is byte-identical between the old-measure run (12 Oct) and this one; the measure is a code default and the only trace is the solver log line `measure=net_annual`. Level 0 would pass two runs of different physics.
(b) The net cap lets Wallonia import 11.4 / 14.3 TWh (2040 / 2050) and **re-export 5.0 / 4.3 TWh**; TIMES has no export in 2040 (`ELCEXP` flows are 0). 6.14 TWh of its 6.47 TWh of 2040 imports is **Belgian offshore wind** (`IMPELCOFFWINBE`), and in the PyPSA 2050 run
**+6.4 TWh of the 10.0 TWh net import comes from Flanders** (ALEGrO 1.8, FR 1.2, LU 0.7, Brussels −0.2); in 2040 Wallonia imports 10.5 TWh from DC/FR/LU and sends 4.0 TWh to Flanders and Brussels. The cap is what was asked for; the label "import" needs "net, intra-Belgian included".
(c) 2030: the cap is slack (net −0.74 TWh).

**R4. One scarcity hour at 8 592 EUR/MWh in 2040** (7 025 in the old run); 61 hours above 500 EUR/MWh in both. 2050 maximum 350 EUR/MWh. BEWAL mean price 98.4 / 111.5 EUR/MWh (2040 / 50; 132.3 / 120.6 before) is the shadow price of a model with no load shedding: not comparable with TIMES's.

**R5. Buildings and services electricity is +2.44 TWh above TIMES in 2050 (+1.61 in 2040, +0.59 in 2030). None of it is a transferred demand: all of it is heating electricity, which PyPSA computes from the TIMES heat.**

*Correction of the first version of this review.* It gave +2.99 / +2.15 / +1.09 TWh. That comparison left the **rail** electricity (0.56 / 0.53 / 0.51 TWh in 2050 / 2040 / 2030), which PyPSA keeps in its `electricity` load and TIMES books under transport,
on the buildings side. With rail on the transport side the transport rows agree to 0.01 TWh and the buildings gap is the one above; the totals of the balances did not change.

*What is transferred matches to the last digit.* The BEWAL `electricity` load of the solved network is 19.617 TWh (2050) = TIMES `total electricity residential` 4.111 + `residential cooking electricity` 0.881 + `total electricity services` 14.065
(appliances, lighting, cooling, 6.87 TWh of data centres, electric cooking; electric heating is excluded from these rows by design) + `electricity rail` 0.559. Difference 0.000 in 2030, 2040 and 2050. The district-heating **demand** is transferred too: 2.133 TWh_th
= TIMES residential 1.595 + services 0.538. TIMES's own indicator tables (residential 8.826 + tertiary 15.398 = 24.224 TWh) minus those non-heat rows leave **5.166 TWh**, and the heat pumps and electric heaters of the `.vd`, process by process, consume 5.166 TWh:
two independent routes to the same number. So the whole gap sits in the conversion of heat into electricity.

| 2050, TWh_el (heat delivered, TWh_th; COP) | TIMES | PyPSA now | difference | share |
|---|---:|---:|---:|---:|
| Decentral heat pumps | 4.66 (13.79; 2.96) | 6.08 (15.37; 2.53) | +1.42 | 58 % |
| Decentral resistive heaters | 0.50 (0.50) | 0.58 (0.52) | +0.07 | 3 % |
| **District heating**: electric heater / heat pump | **0** | **0.95** (0.94) | **+0.95** | **39 %** |
| **Heating electricity** | **5.17** | **7.61** | **+2.44** | |
| Soft-linked non-heat | 19.06 | 19.06 | 0.00 | |
| **Buildings + services** | 24.22 | 26.66 | **+2.44** | |

Why, in order of size (2050; the same terms for 2040 and 2030 are in the last table):

1. **District heating, +0.95 TWh (39 %): the one place where PyPSA chooses the technology.** The DH demand is imported, the DH supply is not. TIMES supplies its district heat from **geothermal (1.54 TWh_th), industrial waste heat (0.67) and CHP / waste-incineration heat (0.65), with no electricity input** (checked in the `.vd`:
   `RENGEO` and `INDHWT` feed the heat exchangers, `ELCHET` comes from the CHP and the waste turbine). PyPSA has no geothermal and no waste-heat component ([`heat-softlink.md`](../heat-softlink.md) §6 and open point 6, a question to ICEDD that is still pending), so its optimiser covers the 2.13 TWh_th
   with gas CHP (1.25 TWh_th, 1.04 of it with CC) and a **resistive heater (0.94 TWh_th, 0.95 TWh_el)**, with a water-pit store in between (net −0.06); a heat pump is available and is not chosen (R8). The 12 Oct run had 0.65 TWh_el; the +0.30 TWh_el goes with the relaxed import cap (BEWAL mean price 120.6 → 111.5 EUR/MWh, CC CHP 451 → 370 MW_e and its heat 1.33 → 1.04 TWh_th, R1), not with any change of the TIMES input.
2. **Heat-pump COP, +0.79 TWh (32 %).** For the same heat PyPSA's heat pumps draw more electricity: **2.53 TWh_th per TWh_el** against TIMES's **2.96** (the TIMES annual process efficiencies are 2.88 for urban decentral, 3.75 rural, 3.04 commercial). PyPSA computes the COP hour by hour from the 2010 temperatures with a 55 °C sink
   (`heat_pump_sink_T_individual_heating`): the time-mean of the BEWAL profile is 2.58 (air) and 3.45 (ground), but the pinned heat is delivered in the cold hours, so the heat-weighted values in the solved network are **2.17 (urban air), 1.95 (rural air), 3.30 (rural ground)**, and the decentral COP does not improve between 2040 and 2050.
   This is the largest term in 2030 and 2040 (+0.33 of +0.59 and +0.99 of +1.61).
3. **Extra heat on the heat pump, +0.63 TWh (26 %): PyPSA's heat pumps deliver 15.37 TWh_th, TIMES's 13.79.** Of the +1.58 TWh_th, **1.31 is the 2050 biomass-boiler shortfall** (level 2.5 WARN: the pinned biomass boilers deliver 66.5 % less than pinned because the EU `biomass limit` costs 987 EUR/MWh); the heat pump is the absorber and takes it:
   **+0.52 TWh_el**. The other 0.27 TWh_th (+0.11 TWh_el) is a boundary effect: PyPSA's decentral heat load (22.74 TWh_th) is 0.57 TWh_th larger than TIMES's appliance heat (22.17) because it also carries the non-electric cooking fuel (0.18), the tertiary "other fuel" (0.24) and the agricultural heat (0.15),
   which TIMES serves with fuels outside its heating processes and PyPSA serves with the pinned mix (61.8 % heat pump), less 0.08 TWh_th of mapping difference.
4. **Decentral resistive heaters, +0.07 TWh (3 %):** PyPSA's efficiency is 0.90 (TIMES 1.00) on 0.52 TWh_th.

| TWh_el, PyPSA now − TIMES | 2030 | 2040 | 2050 |
|---|---:|---:|---:|
| District heating (resistive heater) | +0.18 | +0.45 | +0.95 |
| Heat-pump COP (2.41 / 2.35 / 2.53 against 3.14 / 2.96 / 2.96) | +0.33 | +0.99 | +0.79 |
| Extra heat on the heat pump: biomass shortfall absorbed | 0.00 | 0.00 | +0.52 |
| Extra heat on the heat pump: the rest (boundary of the heat load) | +0.07 | +0.11 | +0.11 |
| Decentral resistive heaters | +0.01 | +0.06 | +0.07 |
| **Buildings + services, total** | **+0.59** | **+1.61** | **+2.44** |

*What it means.* This is the design of the soft link (the heat and the mix are TIMES's, the efficiency of each technology is PyPSA's, the district-heating supply is free), not an input error. Two of the terms depend on something PyPSA lacks: the DH options (+0.95) and the solid-biomass potential the pinned mix asks for (+0.52); closing them would reduce the gap by up to 1.5 of the 2.4 TWh (the optimiser may still choose electricity).
The COP term (+0.79) is a convention difference; this review did not check which of the two values is closer to a real 2050 Walloon fleet. The 12 Oct run (old cap) had +2.06 TWh in 2050 (district heating 0.65, heat pumps +1.34, resistive +0.07), so the cap change moved this term by +0.38.

**R6. Build rates (level 5.2), same in both runs.** Ground PV 6.4 → 11.1 GW over 2040–2050 (+470 MW/yr) against a Walloon history of 200–300 MWp/yr for all PV; onshore wind 3.97 → 6.5 GW over 2030–2040 (+250 MW/yr, cap-bound; history 100–150 MW/yr).
Capacity factors pass (onshore 25–26 %, PV 11.0–11.1 %). Not new, listed for completeness.

**R7. The old run was not at an optimum in 2050 ground PV and 2040 H2 fuel cell:** 13.0 GW (potential cap) and 174 MW of H2 fuel cell (0.78 TWh) existed only under the tight cap.

**R8. No heat pump supplies district heating. It is available, and in 2050 it misses by 19 %.** (`BEWAL urban central`: 2.13 TWh_th, peak 876 MW, mean 244 MW, load factor 0.28.)

*It is not excluded.* `sector.heat_pump_sources.urban central: [air]`; the link `BEWAL urban central air heat pump-<year>` exists in every horizon, is extendable with no upper bound, and has an hourly COP of 2.4–5.3 in 2050 (time-mean 2.87 / 3.08 / 3.32 in 2030 / 2040 / 2050). DAC is off (`dac: false`), so the district-heat bus serves the district-heat demand only.
(In the reference run of [`heat-softlink.md`](../heat-softlink.md) §6 (Aug 2026, DAC on) a 729 MW heat pump existed because DAC drew 4.14 TWh_th from this bus, 154 % of the district-heat load; without that load the heat pump no longer pays.)

*Why it is not built.* A link is built when the margin it earns over the year exceeds its annualised capital cost. With the solved prices, per MW_th and year:
margin = Σ_t (heat price − electricity price × electricity per MWh_th − VOM), positive hours only. The resistive heater is the control: its margin equals its capital cost to 0.1 % in every horizon (it is built at the margin), so the method holds.

| EUR/MW_th/yr | 2030 | 2040 | 2050 |
|---|---:|---:|---:|
| heat pump: operating margin (hours with a positive margin) | 34 023 (2 570) | 66 828 (4 742) | 85 787 (4 415) |
| heat pump: annualised capital cost (1 144 EUR/kW_th, 7.5 %, 25 years, flat in the cost table) | 105 281 | 105 281 | 105 281 |
| **margin / capital** | **0.32** | **0.63** | **0.81** |
| resistive heater: margin = capital cost | 9 224 | 9 158 | 9 091 |

The heat pump costs **11.6 times** a resistive heater per MW_th. The 12 Oct run had 79.7 k EUR in 2050 (0.76): the relaxed cap moved it 6 k EUR closer, not across.

*Where the margin is earned (2050).*

| hours with a heat price of | hours | mean heat price | mean electricity price | mean COP | share of the annual margin | heat supplied by CHP / resistive / water pits (GWh) |
|---|---:|---:|---:|---:|---:|---|
| ≤ 5 EUR/MWh_th | 3 896 | 1.9 | 61 | 3.8 | 3 % | 65 / 577 / −347 (it charges) |
| 5–20 | 1 896 | 10.4 | 75 | 3.3 | 6.5 % | 59 / 229 / +146 |
| 20–80 | 329 | 39.8 | 289 | 3.0 | 0.6 % | 121 / 0 / −4 |
| **> 80** | **2 639** | **108.2** | **226** | **2.7** | **90 %** | **1 004 / 136 / +147** |

* In two thirds of the year (5 792 h) district heat is nearly free: the resistive heater (1 081 MW_th, 970 h at an average 9.7 EUR/MWh_el, 0.94 TWh_th, 19 EUR/MWh_th) turns surplus electricity into heat and fills the water pits. A heat pump of the same size would save 6.2 MEUR/yr of electricity and cost about 103 MEUR/yr more.
* The heat pump earns 77 of its 86 k EUR in the **2 639 winter hours** (November–March; 60 % of the annual DH load), when the heat price is 108 EUR/MWh_th. But electricity is dear then too (226 EUR/MWh_el; the CHP CC runs in 1 964 of these hours) and the COP is at its lowest (2.7), so the margin is 29 EUR/MWh_th, and 78 % of the heat is already supplied by the CHP as a co-product of electricity.

*What would flip it* (estimates with the margins held fixed; a finite heat pump would earn less than the first MW): an investment of **≤ 932 EUR/kW_th** in 2050 (−19 %; 726 in 2040, 370 in 2030) or a discount rate of **≤ 5.2 %** instead of the 7.5 % of the TIMES supply hurdle. A decision 19 % from its threshold is weakly determined, like the CCGT CC of R1.
TIMES has no electric district heating either (R5): the question is only which non-TIMES option PyPSA picks for the heat that geothermal and waste heat supply in TIMES. Not checked: whether 1 144 EUR/kW_th (the DEA 3 MW air-source unit, flat 2030–2050) represents a district-heating-scale unit.

### What passed cleanly

* 4/4 horizons optimal, `Crossover 0`, no numerical-trouble or infeasibility line; the 2025 objective is identical to the 12 Oct run to 8 digits (the cap is off in 2025), 2030 differs by 4e-7 (relative).
* Peak `MaxRSS` 56.9 GiB (2050 solve) of the 73.2 GiB request (78 %); solve times 94 / 45 / 36 / 35 min.
* Every electricity balance recomputed here closes to < 1e-3 TWh in both trees; TIMES's own supply − use closes to the rounding of the indicator tables.
* `import_limit_BEWAL`: binding to three decimals in 2040 and 2050 on the **net** balance; constant and dual survive in the `.nc`.
* Soft-linked electricity demands (industry 24.39, transport EV 17.31 TWh in 2050) match TIMES to ±0.5 %; capacity factors; heat load closes to 2e-6 TWh.
* The 2040 national and capture caps still bind (national dual −30.8, capture 6.00 Mt); 2050 does not bind either, as before.

### Numbers that must not be published as-is

* **`CCGT CC` capacity or tonnage (any horizon)**, and any sentence about CCS on gas power: 0 here, 0.5 GW / 1.6 TWh before, 1.0 GW / 5.7 TWh in TIMES; it flips with the import-cap measure.
* **2050 ground PV (11.1 GW) as a forecast:** a flat optimum (import dual −0.75 EUR/MWh) that was 13.0 GW (cap) a day earlier; TIMES has 4.3 GW. Quote the range or the PV total with the rooftop floor.
* **"Wallonia imports 10 TWh"** without "net, Flanders and Brussels included, with 4.3 TWh re-exported"; and the 2030 cap, which is slack.
* BEWAL 2040 maximum price (8 592 EUR/MWh) and the mean BEWAL price next to TIMES's; the 2025 horizon (not a calibration); objectives of the two myopic paths at the ±0.1 bn level (F13 of the 10 Oct review).
* Any comparison of this tree with a tree solved before 13 Oct (including `scen_demande_haute`) without naming the cap measure.
* Walloon buildings electricity next to TIMES's without splitting the heating part: the soft-linked part is identical by construction, the heating part is PyPSA's own conversion (+2.4 TWh in 2050, R5), and rail electricity sits on opposite sides of the two models' buildings/transport split.

### Review follow-ups

| # | Action | Owner |
|---|---|---|
| 1 | Write the measure into the effective config: `self_sufficiency.measure: net_annual` in the base overlay and every scenario block (and extend `test_s2_block_mirrors_s1` and a level-0 check of `review_run.py` to read it), so two runs of different physics never have the same `configs/` | code |
| 2 | Decide how CCS on gas power is represented (TIMES: retrofit of 1.0 GW at 5.6 kh; PyPSA: new build only, now 0): a retrofit option, or a floor like the industrial capture, or accept and say so; re-read F1 of the 10 Oct review | modeller |
| 3 | Decide whether the cap should count intra-Belgian flows and whether re-exports are allowed (TIMES: none in 2040); an alternative is to cap gross inflow from outside Belgium only | modeller |
| 4 | Compare the PV greenfield investment cost in the `.vd` (`Cost_Inv`) with the shared CSV (325–357 EUR/kW) | data |
| 5 | Close what can be closed of the +2.44 TWh heating-electricity gap (R5): district-heating supply options PyPSA lacks (TIMES: geothermal 1.54, industrial waste heat 0.67 TWh_th; the pending ICEDD question) = 0.95; the 2050 biomass-boiler shortfall (EU biomass limit) = 0.52; and compare the heat-pump COP conventions (TIMES 2.96 annual process efficiency, PyPSA 2.53 heat-weighted hourly) = 0.79 | modeller / data |
| 6 | Re-run the other scenarios with the net cap only after 1 and 2 are settled; S1/S2 pairs must use the same measure | ops |
| 7 | Optional isolation test: re-solve 2040 with `CCGT CC` forced to 270 MW_e to read its true cost under the net cap | ops |
| 8 | Check the central heat-pump cost against a district-heating-scale figure and its learning (DEA 3 MW, 1 144 EUR/kW_th flat 2030–2050) and the 7.5 % hurdle: the 2050 decision is a 19 % near miss (R8) | data |
