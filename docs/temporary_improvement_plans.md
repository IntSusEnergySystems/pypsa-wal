# Improvement plan — status 2026-09-01

Live worklist for the Walloon model. Two meetings feed it: **27 Aug** (items
1–10) and **1 Sept** (items 11–17, plus decisions on 3, 6, 8 and 10).

**What this file is.** The queue and its points of attention — not the evidence.
Per-item dossiers live in the companion docs; the long 27 Aug evidence version
of this file (full option tables per item) is preserved at
`git show ae753bb3:docs/temporary_improvement_plans.md`.

**Reference run.** [`2026-08-30 scen_demande_haute @ 2010, 1h`](logs/2026-08-30_scen_demande_haute_2010_1h.md)
— 4/4 optimal, critically reviewed (§11), published as Explorer
`demande-haute-2010-1h` (30/08) and
[HTML](https://pypsa.squoilin.eu/intervec/scen_demande_haute_20260830/). New
TIMES vd `scen_central_demande_haute_v1_260828_2808.vd`. Every "today" number
below is from that run's §11.

**Test strategy (agreed 1 Sept).** There is no time for a production solve
between individual improvements. So:

1. every item ships a **pytest guard** in `test/` (`python -m pytest test/ -q`);
2. items that change the LP also get a **cheap solve** — one horizon, or all
   four at `resolution_sector: 6h` — only to prove feasibility and direction;
3. **one final full 1h / 2010 four-horizon run** at the end, with a §11 review.

Accept the consequence up front: after ~10 simultaneous changes, attribution in
that final run is weak. Each item below therefore states **what it should move**,
so the final review can check the sum rather than guess.

Companion docs: [ccs_alignment](ccs_alignment.md) ·
[co2-sequestration](co2-sequestration-20260829.md) ·
[gas-storage](gas-storage-20260829.md) ·
[nuclear-alignment](nuclear-alignment-20260816.md) ·
[renewable-potentials](renewable-potentials.md) ·
[network-representation](network-representation-analysis.md) ·
[heat-softlink](heat-softlink.md) · [discount-rates](discount-rates.md) ·
[run-review-checklist](run-review-checklist.md)

---

## Done since 27 Aug

| # | Item | What was done | Confirmed by |
|---|---|---|---|
| 1 | Gas storage in Wallonia | Wallonia has none (Anderlues/Péronnes closed 2012, no salt caverns) → `BEWAL gas Store` `e_nom_max = 0`; Loenhout corrected 545 GWh → **8.2 TWh** *working* gas as a legacy floor | `2aea1b01`, `46c2f485` · run §11.1b, R3: **0 GWh** BEWAL, 8.18 TWh BEVLG · [dossier](gas-storage-20260829.md) |
| 4 | Biogas 4.0 / 6.9 TWh | Caps applied as instructed (2040 **4.0**, 2050 **6.9**; 2025/30 keep Valbiom 8.3). Master-CSV row split per year; `--check` passes | `907433a6` · run: used 0 / 0 / **0.22** / **6.90** — 2050 binds, 2040 slack. **Source still owed by ICEDD** (see 17d) |
| 5 | Flanders P2H "falling" | Plot bug: the panel added MW_th (heat pumps are reversed links) to MW_e (resistive). Restated on the heat side, retitled "Power-to-heat (thermal)". Trend itself is real (renovation + decentral→DH shift) | pypsa2html `0d1b904`, `c4220d71` |
| 7 | Flanders heat demand "rising" | Plot bug, sign-inverting: `_DEMAND_CODES` whitelist was missing `demandheatc`, dropping **71 %** of Flemish heat (urban-decentral). Truth: Flanders −18 %, Wallonia −17 % 2025→2050. Fixed + tripwire for unclaimed demand codes | pypsa2html `0d1b904`, `c4220d71`; report rebuilt (82 pages) and published |
| 3 | No WAL grid expansion 2025→2030 | Answered, no code: Boucle du Hainaut slipped to **2032–33** (Conseil d'État Oct 2025, final environmental report Mar 2026), so the freeze is correct. Only the 2040 question remains → item 3 below | run §11.5: BEWAL–BEVLG usable **3 566 MW** all horizons |
| — | RES envelope + 2025 pin | Not a numbered item but the precondition for item 6: 2025 = historical fleet, later horizons ≤ 2 × record build rate, then land. BEWAL onwind **2 371 / 4 870 / 6 500 / 6 500 MW**. Neighbour offshore fixed (DE 30 / NL 12 / GB 42.6 GW in 2030; 70 / 50 / 80 in 2050) | `96fd920e`, `bab60ed6` · run §11.5, R1 · [dossier](renewable-potentials.md) |
| — | Collapsed-corridor tolerance | `min == max` on an aggregate is a difference of near-equal large numbers; a per-row `tolerance` column (0.5 %) makes 2025 certifiable. `review_run.py` reads the same column — the 18 "overshoots" were the script | `dbca25df` · run R7 |
| (2) | CO₂ sequestration geology + Belgian sink | Geology ramp + `BarHomogeneous`. Belgian `e_nom_max` **0** at BEWAL/BEVLG/BEBRU (no demonstrated CO2StoP site; TIMES 7.1 Mt was an injection figure, not geology). Capture exports via `co2_network` to DE/NL/GB. 6h re-solve 4/4 optimal; Belgian stores unused; seq. in DE/NL/GB | `docs/logs/2026-09-02_scen_demande_haute_2010_6h_co2sinks_be0.md` · [dossier](co2-sequestration-20260829.md) |

Also from the run: 2050 effective Walloon CO₂ **1 272 → 547 EUR/t** with the
*national* cap no longer binding; 2040 heat-profile gap 0.46 → **0.01 TWh** on
the new vd; `CCGT CC` now **~0 MW_e in every horizon** (26 Aug built 463 in
2050).

---

## Open — LP and data

### Item 2 — Give Belgium *usable* CO₂ storage: domestic store or priced export

**Done on the 6h re-solve** ([log](logs/2026-09-02_scen_demande_haute_2010_6h_co2sinks_be0.md)). Geology ramp + `BarHomogeneous: 1`. Belgian `e_nom_max` **0** at BEWAL/BEVLG/BEBRU (no demonstrated CO2StoP site; TIMES 7.1 withdrawn). Capture exports on existing `CO2 pipeline` links to DE/NL/GB. 4/4 optimal; Belgian stores unused; NL geology binds. No Northern-Lights link. Guard: `test/test_co2_store_potential.py`. Full 1h confirmation waits for the final run.

`co2 sequestered` `e_nom_max = 0` at BEWAL/BEVLG/BEBRU *was* a `fillna(0.0)` on a
missing CO₂StoP row, not a documented choice (the overlay is offshore-only and
no Belgian EEZ site clears `min_size`). TIMES stores **7.1 Mt in Wallonia**;
PyPSA stored 0 in Belgium and filled NL to 100 %. Document an `e_nom_max` per
Belgian node, **or** — closer to reality — an explicit priced export route. The
export route is **not** taken in this pass.

- **Attention — the pipe is not the problem.** `sector.co2_network: true` already
  gives extendable, **unbounded** `CO2 pipeline` links between neighbouring
  `co2 stored` buses (BE→GB is 495–802 km of sea at 242–333 kEUR/MW, `p_nom_max
  = inf`, no permitting), and the model uses them: the 26 Aug 2050 Walloon
  CCGT-CC shipped its 0.41 Mt to a German/British sink. If anything, export is
  modelled **too** generously. Norway is not in the model (BE/FR/GB/NL/DE/LU),
  so a Northern-Lights-style route has to be an explicit priced link, not a
  pipeline.
- **Attention — the binding constraint has no geography.**
  `sector.co2_sequestration_potential` is **one** pooled `GlobalConstraint` on
  the `co2 sequestered` carrier for the whole network — no country dimension —
  and it binds in all four horizons after the revert (431 / 73 / 125 / 342
  EUR/t). A Belgian store or a new pipeline adds **zero** headroom to it. Fix
  that layer first or nothing downstream is interpretable. The 2040 failure of
  the geology ramp was the exact error `BarHomogeneous: 1` fixes, and the cluster
  overlay has carried that flag since 30 Aug — retry the ramp *with* the flag
  before concluding anything.
- **Attention.** Do **not** hard-pin the TIMES 1 740 MW of CCGT-CC in 2040
  before storage is usable. PyPSA `CCGT CC` is greenfield, not the
  Flémalle/Seraing retrofit TIMES runs, and its capture split is fixed by
  construction (`efficiency3 = co2 × capture_rate` onto `co2 stored`), so
  dispatching it forces ~2.3–2.5 Mt/a — ~3 % of the entire 90 Mt/a 2040 pooled
  cap — into a constraint that is already at 100 %. With `co2_vent: false` the
  only outlets are sequestration, a pipeline to someone else's sink, or
  synthetic-fuel feedstock (FT / Sabatier / methanolisation take `co2 stored`).
  A **capacity** floor would therefore not fail outright — it would build the
  plant and idle it, or reprice carbon system-wide through the pooled dual.
  Either way the published number would be an artefact of the pin.
  If ICEDD wants the TIMES *outcome* in the charts anyway, it is a named overlay
  (`scen_ccgtcc_times`), not a change to the base.
- **Test.** `test/` guard on the Belgian `e_nom_max` being a stated value, not a
  fillna. Then a 2040-only solve.
- **Expect.** Capture becomes *eligible* in 2040. If it still is not built, the
  gap is the missing retrofit link, not the sink.

### Item 6a — Electricity independence: the TIMES 10 TWh import cap

TIMES caps Walloon electricity imports at **10 TWh in 2050** (`Transfo_Imp`,
36 PJ; 6.47 in 2040, 2.94 in 2030). PyPSA has only NTC *power* ceilings. Decided
1 Sept: **align on TIMES.**

- **Reuse, don't rebuild.** `add_selfsufficiency_constraints` already exists in
  `scripts/solve_network.py` (gated by `self_sufficiency.self_sufficiency_constraint:
  false`) with an `Import_p` variable per bus and `import_positive_*` linking it
  to line/link net flows. It needs two changes: an **absolute TWh** right-hand
  side instead of `(1 - level) × local_energy`, and scoping to **BEWAL** instead
  of every region.
- **Attention.** Grouped by location, BEWAL "imports" include flows **from
  Flanders and Brussels**. That is arguably the right TIMES analogue (RW imports
  from everything outside RW), but it must be written on the chart — it is not
  "imports from abroad".
- **Attention.** Measure before imposing. The 30 Aug §11 has **no net-import
  table**, so the post-envelope, post-neighbour-offshore import level is
  unknown; 26 Aug was 30.8 TWh Belgium / 18.0 TWh BEWAL in 2050 on an
  under-built European offshore fleet that has since been fixed. Run the import
  measurement on the 30 Aug networks first — the cap may bind far less than
  feared.
- **Attention.** Do **not** put a 10 TWh cap on *Belgium* — TIMES's figure is
  Wallonia-only; Belgium-wide it is an autarky scenario.
- **Test.** `test/test_import_limit.py` on a toy network (cap respected, cap
  slack, correct sign for exports). Then a 2050-only solve.
- **Expect.** Forces local generation, storage or load shifting in 2050;
  interacts strongly with 10 (Flanders nuclear) and 11 (offshore 2030).

### Item 10 — Nuclear in Flanders 2050: 1 GW retrofit + 2 GW new (decided)

Symmetric with Wallonia (whose 3 000 MW is retrofit #2 ≈1 030 + new ≈1 970).
So **BEVLG 2050 = 3 000** and **BE 2050 = 6 000** MW_e.

- **Attention — order of edits.** `add_CCL_constraints` subtracts the region row
  from the parent country row. Setting BEVLG `min = 3000` while `BE` is still
  `min = max = 3000` is **infeasible**. Raise the BE row first, in the same edit.
- **Attention — the retrofit leg.** A Flemish *retrofit* in 2050 requires the
  2040 Doel 4 unit (1 000 MW) to carry forward and be retrofittable a second
  time; `retrofit_nuclear_once: false` already permits the repeat, but brownfield
  must be rebuilt from 2040. The 0.01 MW placeholder plants must stay above any
  authored zero cap (already guarded).
- **Attention — labelling.** The vd puts *all* new Belgian nuclear in Wallonia
  and Flanders at 0 by 2045. This doubles the vd's new build to 6 GW Belgium. It
  was instructed, so it goes in the base run — but it is a **siting policy, not
  TIMES alignment**, and must be labelled that way wherever it is published.
- **Route.** Master CSV `agg:BEVLG:nuclear-all:min/max` + `agg:BE:nuclear-all:*`,
  `--write`, keep the `tolerance` cell.
- **Test.** Extend the nuclear/CCL guards: BE ≥ Σ regions in every horizon.
- **Expect.** ~20–23 TWh of extra must-run in Flanders (BE band
  `p_min_pu = 0.783`) → 2050 imports down, Belgian prices down, cost up. Largest
  independence lever after the onwind cap.

### Item 11 — Offshore 2030 is forced too high (new)

`data/walloon/agg_p_nom_minmax_*.csv` carries `BE offwind-all` **2030 min =
5 800 MW** — a *floor*, tagged `NECP-BE-2030` (2.26 GW standing + 3.5 GW Princess
Elisabeth Zone). It is also the **only** offshore floor in the file: 2035–2050 are
blank. So the model is obliged to commission the entire PEZ by 2030 and free
thereafter — the opposite of the real schedule.

**Press review (FR / NL / EN, 1 Sept 2026) — nothing new can be online by 2030.**

| Date | Fact |
|---|---|
| Jul 2025 | PEZ-1 tender **withdrawn** (legal, calendar and financial framework judged unworkable) |
| Feb 2025 | Elia **postpones the island's HVDC contracts** (price escalation; island budget 3.6 → 7–8 bn EUR) — reported as a ~3-year slip for that phase, which carries **PEZ III (1.4 GW)** and Nautilus (GB, "from 2032") |
| Feb / May 2026 | Relaunch misses the promised deadline; ~2 years lost; delay costed at **~400 MEUR by 2030** (EnergyVille, via Agoria) |
| 18 Jul 2026 | New framework approved: two-sided CfD, no strike-price cap, construction window **48 → 60 months**, bid prep ≥ 6 months + fixed 5-month evaluation. Still needs Council of State + EC state-aid clearance; relaunch planned **late Sept / early Oct 2026** |
| — | Island phase 1 (**MOG II**) must be operational by **1 Oct 2031**; HVAC phase (contracted, caissons all placed by Mar 2026) serves PEZ I + II only |
| — | Government's own framing is now security of supply "**from 2035**"; PATHS2050 asks for the zone operational **by 2035**; commentators state the park "will no longer contribute in time" to the 2030 EU 42.5 % target, with supply-security concerns **2030–2032** |

Arithmetic from the framework's own parameters: relaunch late 2026 → bids mid
2027 → award ~late 2027 → up to 60 months construction, and no export before the
island exists (1 Oct 2031). **First PEZ-I power 2031–2032 at the earliest**, full
700 MW ~2032–33; PEZ II later; PEZ III behind the postponed HVDC.

- **Action.** Move the floor and pin 2030 to the standing fleet:

  | `BE offwind-all` | 2030 | 2040 | 2050 |
  |---|---:|---:|---:|
  | now | min **5 800** | — | — |
  | proposed | min = max **2 262** | min **4 362** (2 262 + PEZ I + II, the contracted HVAC) | min **5 800** (full zone) |

  Maxima beyond 2030 stay with the envelope (land 8 000 MW). Retag the row
  `NECP-BE-2030 (retimed 2026-09, press review)`.
- **Attention.** Cutting the **max** does nothing — 5 800 is the *min*. Pinning
  `min = max` in 2030 is what actually implements "no new installations before
  2030"; the 0.5 % `tolerance` column keeps that corridor solvable.
- **Attention.** Do **not** put the full 5 800 in 2040 as a floor: PEZ III
  (1.4 GW) depends on an HVDC decision that has slipped ~3 years and is not
  contracted. 4 362 MW is the committed-infrastructure reading.
- **Attention.** Same "policy target used as a floor" pattern to re-check on the
  neighbours (NL 12 GW, FR 3.6, GB 50 → clipped to 42.6 by the growth cap).
- **Test.** `test/test_res_envelope.py` case: no offshore floor above the
  standing fleet in the first future horizon.
- **Expect.** ~3.5 GW of cheap Belgian offshore removed from 2030 → higher 2030
  Belgian prices, more imports, worse 2030 independence, and a 2030 CO₂ dual that
  can only rise. This is the item most likely to make 2030 look *worse* than the
  published run — say so before publishing, and note it also pushes 2030 gas
  generation up.
- **Sources.** [tender withdrawn (Jul 2025)](https://www.offshorewind.biz/2025/07/01/belgium-delays-tender-for-offshore-wind-farm-in-princess-elisabeth-zone-until-2026/) ·
  [new framework, 1 Oct 2031 (Jul 2026)](https://www.offshorewind.biz/2026/07/24/belgium-approves-new-tender-framework-for-first-princess-elisabeth-zone-offshore-wind-site/) ·
  [construction 48→60 months, bid/evaluation windows](https://www.loyensloeff.com/insights/news--events/news/belgium-offshore-wind-tender-amendment-and-ventilus-permit-push/) ·
  [Elia postpones HVDC, ~3-year slip](https://www.elia.be/nl/pers/2025/02/20250204_elia-temporarily-postpones-signing-hvdc-contracts-for-princess-elisabeth-island) ·
  [RTBF: retard, PEZ 1 = 700 MW / PEZ 2 = 1 400 MW](https://www.rtbf.be/article/eolien-offshore-l-extension-de-la-capacite-belge-a-pris-du-retard-11727009) ·
  [La Libre: ~400 MEUR pour les ménages](https://www.lalibre.be/dernieres-depeches/2026/05/12/le-retard-dans-leolien-offshore-coutera-des-centaines-de-millions-aux-menages-TAHEAHNJEJEB3LZPNF2CKPFQ5E/) ·
  [misses the 2030 EU target, supply concerns 2030–32](https://gasoutlook.com/analysis/surging-costs-cloud-outlook-for-belgian-princess-elisabeth-wind-island/) ·
  [relaunch late Sept/early Oct 2026](https://www.indegazette.be/nieuwe-regels-brengen-eerste-windpark-in-prinses-elisabethzone-dichterbij/) ·
  [government: supply "from 2035"](https://www.seatalk.be/techniek-innovatie/2026/04/20/belgie-zet-offshorewind-in-prinses-elisabeth-zone-opnieuw-in-beweging/)

### Item 12 — Process emissions vs TIMES (new)

Annick's table (below) is **Walloon process CO₂ emitted to the atmosphere**
(ktonnes), not capture — that is item 9. Check the figures are recoverable in
the vd, then align PyPSA's `process emissions` load on them.

- **Attention.** PyPSA process emissions are pure PyPSA-Eur: a national
  industrial-production total spread by an industrial distribution key, never
  soft-linked. So a mismatch is expected, and fixing it means adding a transfer
  (a `process emissions` load override at BEWAL), not tuning a coefficient.
- **Attention.** TIMES separates fossil `INDCO2` from **biogenic `INDCO2b`**
  (0.38 Mt by 2050 from black-liquor gasification). Only the fossil part belongs
  on the PyPSA `process emissions` load; adding the biogenic part would
  double-charge carbon the biomass chain already credits.
- **Attention — process vs combustion.** Are these rows exclusively the
  process itself, or do they also include fuel combustion? Only the process
  part belongs on `process emissions`; combustion CO₂ is already on the fuel
  chain (`gas for industry`, biomass, …). Mixing them double-counts.
- **Attention — energy vs emissions.** Check the inventory against the
  industrial energy PyPSA already imports, so transferred energy consumption
  and transferred process emissions describe the same activity.
- **Attention.** 2021 is not a model horizon — state the convention used to
  bring it to 2025. The figures are now in this file; still commit the original
  excel under `data/walloon/` with its provenance.
- **Test.** `test_times_scenario_inputs.py`-style guard: BEWAL process emissions
  within a stated tolerance of the vd figure per horizon.
- **Expect.** Directly moves the Walloon CO₂ balance and hence the 547 EUR/t
  dual and `process emissions CC` (26 Aug: 238 MW, 1.98 Mt in 2050). Do this
  *before* pinning capture (item 9), otherwise the pin sits on the wrong
  inventory.

**CO₂ process émis à l'atmosphère** (ktonnes). `VAR_Comnet` is the total;
`VAR_FOut` is by TIMES process. Blank = no value in that year.

| Process | 2021 | 2022 | 2025 | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `VAR_Comnet` (total) | 4417.22 | 4415.32 | 4411.62 | 3946.10 | 964.37 | 357.01 | 327.51 | 281.64 |
| `IAMSTDPRO00` Standard Production.00 | 459.36 | 444.05 | 398.11 | | | | | |
| `IAMSTDPRO01` Standard Production.01 | | 15.31 | 61.25 | | | | | |
| `IBKSTDPRO00` bricks standard | 21.55 | 20.83 | 18.68 | 15.08 | 11.49 | 7.90 | 4.31 | 0.72 |
| `IBKSTDPRO01` bricks standard.01 | | 0.72 | 2.87 | 6.46 | 10.06 | 13.65 | 17.24 | 20.83 |
| `ICESTDPRO00` Ceramics standard | 23.73 | 22.94 | 20.57 | 16.61 | 12.66 | 8.70 | 4.75 | 0.79 |
| `ICESTDPRO01` Ceramics standard.01 | | 0.79 | 3.16 | 7.12 | 11.08 | 15.03 | 18.99 | 22.94 |
| `ICHDEMAND00` Other Chemicals.00 | 61.49 | 61.49 | 61.49 | 61.49 | 63.80 | 66.11 | 68.41 | 70.72 |
| `ICMDRYPRD00` cement dry.00 | 2145.04 | 2073.54 | 1859.04 | 1501.53 | 579.18 | | | |
| `ICMDRYPRD10` cement dry.01 | | 134.46 | 348.97 | 643.51 | | | | |
| `ICMWETPRD00` cement wet.00 | 536.26 | 473.30 | 473.30 | 536.26 | | | | |
| `IGFFLATGL00` Glass Flat.00 | 116.35 | 112.47 | 100.84 | 81.45 | 62.05 | 42.66 | 23.27 | 3.88 |
| `IGFFLATGL01` glass production.01 | | 7.20 | 18.83 | 38.23 | 38.23 | 38.23 | 36.90 | 19.39 |
| `IGHHOLLOW00` Glass Hollow.00 | 29.58 | 28.59 | 25.63 | 20.70 | 15.78 | 10.85 | 5.92 | 0.99 |
| `IGHHOLLOW01` glass production.01 | | 0.99 | 3.94 | 8.87 | 8.87 | 8.87 | 8.87 | 8.69 |
| `IGHRECYCL00` Glass Recycling.00 | 36.97 | 35.74 | 32.04 | 25.88 | 19.72 | 13.56 | 7.39 | 1.23 |
| `IISFINPRO00` steel finishing.00 | 125.99 | 125.99 | 125.99 | | | | | |
| `IISFINPRO01` steel finishing.01 | | 5.48 | 5.48 | | | | | |
| `IISFINPRO02` | | | | 131.46 | 131.46 | 131.46 | 131.46 | 131.46 |
| `ILMQLMPRO00` Quick Lime.00 | 860.89 | 851.42 | 851.42 | | | | | |
| `ILMQLMPRO01` Quick Lime.11 | | | | 851.42 | | | | |

### Item 13 — Aviation back in the Walloon CO₂ accounting, as a yaml toggle (new)

The meeting reads the 30 Aug CO₂ constraint as "less tight" and asks to
re-integrate aviation, removed in `644cefd9`, behind a config switch. The switch 
remains deactivated for now to avoid infeasibilities.

- **Attention — why it was removed.** Not a preference: kerosene is drawn from
  the single `EU oil` bus, whose Fischer-Tropsch / biomass-to-liquid negative CO₂
  sits at location `EU` and is **dropped** by national attribution, while the
  withdrawing aviation link sits in Wallonia and pays full fossil intensity.
  Wallonia paid for carbon the synthetic pathway had already removed. The
  aviation term alone was **2.23 Mt against a 1.717 Mt cap** — unsatisfiable
  from a sector the model cannot abate locally.
- **Attention — the right-hand side.** The agreed trajectory in
  `config/input_parameters_for_models.csv` is defined *"hors aviation
  internationale & UTCATF"*. Putting aviation back on the LHS without switching
  the RHS to a with-aviation baseline makes the cap contradict its own target.
  A toggle must move **both sides**, as `644cefd9` did in reverse.
- **Attention — why the dual fell.** The 1 272 → 547 EUR/t drop is *not* the
  aviation exclusion (already present on 26 Aug). It is the new TIMES heat mix +
  RES envelope + biogas 6.9. The system `CO2Limit` still binds, so aviation is
  **not** free today — it is priced globally instead of nationally.
- **Do.** Ship the toggle next to the other national-CO₂ keys
  (`co2_budget_national_include_aviation`, default **false**). It is a small
  change: both sides already key off the same two constants in
  `solve_network.py` (`AVIATION_CARRIER` on the LHS, `AVIATION_SECTORS` in the
  baseline), so one flag can move them together. Keep the default off until oil
  is nodal (per-node synthetic-fuel balances). Extend
  `test/test_national_co2_scope.py` to both settings.
- **Expect.** Likely infeasible in 2050 even with both sides moved: the RHS is
  5 % of a 1990 baseline, so aviation adds a few tens of kt to the cap and
  ~2.2 Mt to the left-hand side — a 95 % target applied to the one sector that
  has not decarbonised. That outcome *is* the answer to the meeting's question;
  get it from a 2050-only solve, not from the final run.

### Item 9 — Industry CC / BECCS volumes (carried, blocked on 2)

PyPSA already runs generic industry capture (26 Aug, 2050: 0.73 Mt biomass-CC
+ 1.98 Mt process-CC + 0.79 gas); TIMES has **4.8 Mt** of named industrial
capture (chemicals, lime, glass; `STORAGEMININD` in the vd). Pin the PyPSA
*capture* volumes to TIMES — **not** DAC, which TIMES does not build and which
ate the Walloon DH bus when it was on.

This is a different LP object from item 12: 12 sets how much process CO₂ is
**produced**; 9 sets how much of it (plus fuel-CC / BECCS) is **captured**.
Do 12 first so the inventory is TIMES-aligned; confirm the 4.8 Mt is in the
current vd. The LP pin itself stays blocked until item 2 gives Belgium a sink
— otherwise the pin just exports CO₂.

- **Test.** Guard that BEWAL industrial CC (biomass-CC + process-CC + gas-CC)
  matches the vd `STORAGEMININD` volume per horizon, once the sink exists.
- **Expect.** Capture becomes a transferred TIMES outcome rather than a PyPSA
  residual. Moves the Walloon CO₂ dual and the industry-CC capacities item 15
  will plot.

### Item 3 — Boucle du Hainaut: NTC floor from 2035

The 2040 NTC ceiling opens to 13.2 GW usable and the optimiser **does not
build**: flows stay ~3 TWh/yr on a 3.566 GW usable path. The line is planned
for 2033 and is now treated as *committed infrastructure* — an `s_nom_min` /
NTC floor from **2035**. **Attention:** `lines.type` is non-empty in this
network, so `set_transmission_limit` rebuilds `s_nom_min` from the conductor
type and can silently override an NTC-derated `s_nom` — check the realised
`s_nom` after any floor edit.

### Item 8 — Rooftop PV

Decision: transfer the TIMES rooftop share (TIMES 2050 is
~77 % rooftop; PyPSA builds ~0 MW because rooftop is 920 vs 526 EUR/kW
overnight). Add this with a config switch (and a chart toggle if the split
should be visible). One small bug to solve first: `BEWAL low voltage` maps to
country `BE`, so any future rooftop build counts against the **Belgian**
`solar-all` cap ([renewable-potentials §7.3](renewable-potentials.md)). Repair
that alias before any rooftop floor.

---

## Open — reporting (pypsa2html)

### Item 14 — Split the power-to-gas bucket (new)

"Power-to-gas is zero while there is some Fischer-Tropsch." Show
**Electrolysis / Fischer-Tropsch / Methanation** as separate series instead of
one bucket. Today `tech_groups.csv` maps `H2 Electrolysis` + `methanation` +
`helmeth` + `H2 liquefaction` → `power-to-gas`, and `Fischer-Tropsch` →
`power-to-liquid`, in three different sections (`costs`, `capacities`,
`dispatch`) that must be edited consistently.

- **Attention — the physics behind the odd chart.** Walloon **electrolysis is
  ~0 MW** while the H2 pipeline carries **3.9 → 5.3 GW** of transit. Any
  Fischer-Tropsch therefore runs on **imported** H₂. Splitting the series will
  make that visible, which is the point — but it also means the FT bar is not
  Walloon power-to-liquid. Label it, and check the H₂ import is intended.
- **Test.** pypsa2html unit test that each of the three carriers reaches its own
  series and that the group total is unchanged.

### Item 15 — BECCS in installed capacities (new)

The `capacities` section of `tech_groups.csv` has **no CC/CCS rows at all** —
`solid biomass for industry CC`, `gas for industry CC`, `process emissions CC`,
`CCGT CC`, gas CHP CC and `SMR CC` appear only in `dispatch`. Add a `CCS` (or
`BECCS`) capacity group.

- **Attention.** Those links are rated on the **fuel input** (MW of biomass or
  gas), not MW_e and not MtCO₂. State the unit in the panel title, exactly as the
  power-to-heat fix did — a mixed-unit stack is the bug items 5/7 already cost
  us once.

### Item 6b — Independence chart: two accounting switches (new)

Primary energy gets **no new constraint**; the chart gets options.

- **Nuclear toggle.** Today `indicators.py` treats uranium as an import (fuel is
  not mined here) and books reactor thermal losses, so nuclear *reduces* primary
  independence; the electricity indicator already counts nuclear kWh as domestic.
  Add a switch between "energy contained in the uranium" (current) and
  "electricity produced".

---

## Carried from the 30 Aug run review

### Item 16 — Water pits `e_nom_max` is `inf` (publication blocker)

2050 urban-central water pits: charger/discharger **29 773 MW**, store
689 GWh_th, `capital_cost = 0`. Open since 26 Aug (§11.14 B). Bound
`e_nom_max`. Until then the number must not be plotted (run §11.10 item 3); the
2050 `tes_se` Sankey FAIL (−0.193 TWh) sits on the same bus.

### Item 17 — Smaller carry-overs

- **a. Coal for industry** soft-link gap +10 / +14 / **+37** / +23 % (worse on
  the new vd, 2040) — accounting, not a solve failure.
- **b. DE 2030 onwind 115 GW** is a collapsed corridor (target above the growth
  cap) and still sets the 2030 European price signal. Decide: accept, or let the
  growth cap win.
- **c. `enc_pe` / `pac_fe` / `vap_se` Sankey WARNs** — known mapping holes.
- **d. Biogas 4.0 / 6.9 TWh citation** still owed by ICEDD. The vd runs 7.67 /
  8.07 TWh, so this is a deliberate **divergence** from TIMES: do not publish it
  as TIMES-consistent until the source arrives, and ask at the same time whether
  2025/2030 should come down from 8.3 (the cap is currently non-monotonic).

---

## Sequencing

Cheap and independent first, so the expensive final run carries as few unknowns
as possible.

```
step 0 — measure, no change
  └─ net electricity imports per region on the 30 Aug networks (§11 never
     reported them; needed before 6a's cap value can be judged)

reporting only — no solve needed, do now
  ├─ 14  power-to-gas split (Electrolysis / FT / methanation)
  ├─ 15  BECCS/CCS in installed capacities
  └─ 6b  independence toggles (nuclear accounting, 50 % offshore)

data / caps — pytest guard each, no solve
  ├─ 11  BE offshore: pin 2030 at 2 262, move the PEZ to 2040/2050
  ├─ 10  BEVLG 3 000 + BE 6 000 nuclear (BE row first!)
  ├─ 12  process-emission load from the vd  ← Annick's table is in the item
  ├─  3  Boucle du Hainaut: NTC floor from 2035
  └─ 16  water pits e_nom_max

LP code — pytest guard + one cheap solve each
  ├─ 6a  BEWAL 10 TWh import cap   ← measure 30 Aug imports first
  ├─  8  rooftop share (after the LV country-alias bug)
  ├─ 13  aviation toggle (default off)
  └─ 2   Belgian CO₂ sink (+ retry the geology ramp with BarHomogeneous)
              │
              └─ 9  industry-CC pin, only once 2 is in (and 12 has run)

final full run: 1h / 2010 / four horizons + §11 review

no code, decide in a meeting
  ├─ 17b DE 2030 onwind corridor: accept 115 GW or let growth win?
  └─ 17d biogas citation, owed by ICEDD
```

Interactions to keep in mind when reading that final run: items **6a, 10, 11**
all move 2050 independence, in opposite directions (nuclear helps, the offshore
cut hurts, the cap forces); items **2, 9, 12, 13** all move the Walloon CO₂ dual.
If the sum is unreadable, the fallback is a 6h solve with 10 and 11 only.

Still not comparable across vintages: total system cost (gas-store floors),
2025 capacities (now a historical pin), onwind (2 371/4 870/6 500 vs the old
flat 6 500 or 12.4 GW).

---

## Meeting notes, verbatim

Kept for traceability.

### 27 August

- vérifier qu'il y a bien du stockage de gaz en wallonie? potentiel?
- CCGT-CC apparait seulement en 2050 => impose the TIMES capacity in 2040?
- no transmission expansion in WAL in 2030 vs 2025? no current plans (review online)
- decrease biogas to 6.9 TWh in 2050 (4 TWh in 2040)
- power-to-heat decreases in flanders: why? to be checked
- energy independance has dropped from the previous run
    => to be checked (model issue?)
    => impose an energy edependance constraint on electricity? TIMES imposes max 10 TWh imports in 2050
- heat demand increases a lot in flander, stable in wallonia. Why?
- no rooftop PV in pypsa => align with TIMES?
       couts de transport
       imposer la part en toiture venant de TIMES?
- BECCS activé dans TIMES (biomass for industry process with CC)
    => activer DAC à un niveau équivalent?
    => nouveau process industriel qui capture le CO2?
- il faut ajouter 3 GW de minimum de nucléaire en flande en 2050 (symétrique avec wallonie)

### 1 September

- power-to-gas is zero while there is a bit of fischer tropsch
   => to be updated, in that broad category, differentiate into Electrolysis, Fischer Tropsh, Methanation
- Vérifier process émissions par rapport à times
   Annick a fourni un excel qui détaille le valeurs de 2021 en wallonie
   Vérifier si on retrouve bien ces valeurs de CO2 dans le fichier VD et intégrer cela aux process emissions de pypsa
- contrainte indépendance énergétique
    Electricité: On s'aligne sur TIMES => max 10 TWh?
    Pour l'énergie primaire, on ne fait rien, mais on ajoute un toggle au graphique pour changer la comptabilité nucléaire (Energie electrique produite vs Eenrgie contenue dans l'uranium)
    Inclure 50% de l'offshore belge dans la comptabilité (il s'agit d'une compétence fédérale qu'on suppose répercutée équitablement entre la wallonie et la flandre)
- diminuer l'offshore 2030
    Pas de nouvelles installations prévues entre maintenant et 2030 => contrainte!
    faire une revue des articcles de presse => ou en est la construction en 2025? Que'est-ce qui est dans le pipeline? Quelle est la date de mise en service pour les nouvelles enchètes prévues en 2027?
- Ajouter nucléaire en flandre en 2050 (même chose qu'en wallonie: 1GW de retrofit, 2GW de new nuclear)
- Pour le moment, il n'y pas de rooftop => reprendre le rooftop de times
- ajouter beccs dans les capacités installées dans pypsa2html
- Aviation:
   The co2 contraint seems less tight in the last run
   => try to re-integrate aviation in the CO2 accounting of wallonia (was removed in a previous commit). It should be a simple option in the yaml file to include it or not
