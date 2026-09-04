# Improvement plan — status 2026-09-03

Live worklist for the Walloon model. Items 1–10 come from the **27 Aug**
meeting, 11–17 from **1 Sept**.

**This revision is a code review and the fix pass that followed it.**
Everything committed between `7b67b712` and `93bdf848` here, plus pypsa2html
`9454be9`, was read back against the plan; nine defects were found (B1–B9) and
eight are now fixed and guarded. Verdicts come from the committed code and
data, the TIMES vd and the `resources/` CSVs — *not* from a finished solve: the
1h production run is still unfinished
([log](logs/2026-09-02_scen_demande_haute_2010_1h.md): 2025 optimal, 2030
inf-or-unbounded on five successive submissions, all five misdiagnosed).
**B8 is the one that remains — the chain has to be re-solved from 2025.**

**Reference run.** [`2026-08-30 scen_demande_haute @ 2010, 1h`](logs/2026-08-30_scen_demande_haute_2010_1h.md)
— 4/4 optimal, reviewed (§11), published as `demande-haute-2010-1h`. Every
"today" number below is from that run.

**Evidence kept in git, not here.** Long 27 Aug option tables:
`git show ae753bb3:docs/temporary_improvement_plans.md`. Item-11 press review
and Annick's per-process CO₂ table:
`git show 93bdf848:docs/temporary_improvement_plans.md`.

**Test strategy (1 Sept), and its cost.** Each item shipped a pytest guard and
no solve was run between items. Those guards checked that a constant reaches
the LP; none checked that the constraint is *satisfiable*, and the queue
produced three misattributed infeasibility diagnoses in a row (see B1). The
guards added in this pass are written the other way round — each one is
verified to **fail** on the code it replaces, and several solve a toy LP rather
than inspecting a coefficient. That is still not a substitute for a
one-horizon solve before a new binding constraint is trusted.

Companion docs: [ccs_alignment](ccs_alignment.md) ·
[co2-sequestration](co2-sequestration-20260829.md) ·
[gas-storage](gas-storage-20260829.md) ·
[nuclear-alignment](nuclear-alignment-20260816.md) ·
[renewable-potentials](renewable-potentials.md) ·
[network-representation](network-representation-analysis.md) ·
[heat-softlink](heat-softlink.md) · [discount-rates](discount-rates.md) ·
[run-review-checklist](run-review-checklist.md)

---

## Status

| # | Item | State | Where |
|---|---|---|---|
| 1 | No gas storage in Wallonia; Loenhout 8.2 TWh | **done** | `2aea1b01`, `46c2f485`; run §11.1b |
| 2 | Belgian CO₂ sink = documented 0, geology ramp, `BarHomogeneous` | **done** | `80f3d279`; [log](logs/2026-09-02_scen_demande_haute_2010_6h_co2sinks_be0.md) |
| 3 | Boucle du Hainaut NTC floor (9 600 MW usable, 2035+) | **done** | `ntc_floors.csv`; applied after `set_transmission_limit` **and** `carry_forward_built_grid` in both `prepare_sector_network` and `add_brownfield`. First model horizon affected is 2040 |
| 4 | Biogas 4.0 / 6.9 TWh | **done**, source still owed | `907433a6`; 17d |
| 5 · 7 | Flanders P2H / heat demand plot bugs | **done** | pypsa2html `0d1b904` |
| 6a | BEWAL 10 TWh import cap | expression **fixed**, flag still off — TWh values owed | **B6** |
| 6b | Nuclear primary-energy toggle | **done** — `uranium` / `electricity`, validated; both panel titles state the convention | pypsa2html `9454be9` |
| 8 | TIMES rooftop share | **done 4 Sept** — base-year fleet split 1.77 GW rooftop / 0.9 GW ground (Elia/ICEDD); share on from 2030 | **B5** (fixed) |
| 9 | Industry-CC floor (STORAGEMININD) | **done** — reachable once the inventory is gross | **B3** (fixed) |
| 10 | Flanders nuclear (BEVLG 3 GW, BE 6 GW in 2050) | **done as specified**, but it triggered **B1** | `87552368` |
| 11 | Belgian offshore retimed | **done** — 2025/2030 pinned at 2 262, floors 4 362 / 5 800 | **B2** (fixed) |
| 12 | Process emissions from TIMES | **done** — load is now gross (emitted + captured) | **B4** (fixed) |
| 13 | Aviation toggle (default off) | **done** — both sides key off `national_include_aviation` | `solve_network.py` |
| 14 | Power-to-gas split | **done** — electrolysis / methanation / Fischer-Tropsch are separate groups in costs, capacities, dispatch and map | pypsa2html `9454be9` |
| 15 | CCS in installed capacities | **done** — `CCS capacities (fuel input)`, GW of fuel input; `CCGT CC` deliberately left with CCGT | pypsa2html `9454be9` |
| 16 | Water pits `e_nom_max` | **done** (4 weeks ≈ 99 GWh_th BEWAL 2030); per-vintage caveat **B9** | `ptes_bounds.py` |
| 17 | Carry-overs (coal soft-link, DE onwind corridor, Sankey WARNs, biogas citation) | open, unchanged | below |
| — | RES envelope + 2025 historical pin (precondition of 6) | **done for BEWAL and the neighbours; the Flemish half is no longer enforced** | **B1** |
| — | Collapsed-corridor `tolerance` column | **done** | `dbca25df` |

Reporting is complete: pypsa2html at `9454be9` passes 312 tests and
`config/pypsa2html.yaml` loads (`features.nuclear_primary` is now a real key).

---

## Bugs found, and what was done about them

### B1 — root cause: one `BEVLG` row detaches **every** `BE` row from Flanders

> **FIXED 3 Sept.** `add_CCL_constraints` no longer mutates `n.buses.country`.
> The group key is now carrier-aware — a component is booked to its region only
> when the caps file names that `(region, carrier)` pair, otherwise to its real
> country — so a `BE` row again covers all three Belgian nodes for every carrier
> no region row claims. Guard: `test/test_ccl_region_rows.py` (6 cases, 4 of
> which fail on the old code, including two end-to-end solves).

`add_CCL_constraints` collects `regions` from level 0 of the whole caps file
and rewrites `n.buses.country` for every bus whose *name* is in that set
(`n.buses.loc[region_buses, "country"] = region_buses`), then subtracts each
region row from its parent country row. The set is carrier- and
horizon-independent. Item 10 added the first-ever `BEVLG` row
(`BEVLG,nuclear-all`, `87552368`) — from that commit on, the Flemish AC bus has
`country = "BEVLG"`, so **every `BE,<carrier>` row stops covering Flanders** and
its remainder lands on Brussels, the only bus left with `country == "BE"`.

Consequences already realised:

- **2025 built 8 000 MW of Belgian offshore** (the full `BEVLG offwind`
  technical ceiling) because `BE,offwind-all 2025 min = max = 2262` grouped
  nothing. The 29 Aug network — same code, before the BEVLG row — has
  2 273 MW, so this is a regression of that commit, not a pre-existing state.
- **2030 was inf-or-unbounded five times.** Diagnoses 1–3 (item 6a, then item
  8, then the 2262 offshore pin) were all wrong; the cause was the Elia solar
  floor, 16 500 − 6 500 = 10 000 MW, applied to Brussels alone, which has
  ~0.8 GW of land left after 2025 hsat.
- **2025 Flemish solar and onwind are unconstrained too** and were never
  checked. `BE,solar-all` 9 751 and `BE,onwind` 3 337 are historical pins;
  their Flemish share is now unenforced in the base year (the growth cap only
  starts at the second horizon). Check `p_nom_opt` at BEVLG on the retained
  2025 network before anything else.

The patch applied on 3 Sept adds hand-computed `BEVLG` rows for **2030 only**
(`solar-all` 10 000, `onwind` 2 000, `offwind-all` 8 000). 2025 and 2040/2050
are untouched, so the same trap is one edit away.

**What was done.** `ccl_country()` builds the group key from
`(bus location, carrier)` against the caps index, falling back to the bus's own
country; the remainder subtraction is unchanged. The bus table is left alone,
so solved networks keep real ISO codes (`BEWAL` was being exported as country
`BEWAL`, which the commented-out reset was supposed to prevent). Parent codes
are resolved by `_parent_country()`, which reads the other buses at the same
location so an already-rewritten network from an older run still resolves.
**Still to do by hand:** the 2025 network built under the old behaviour is
stale — see B8.

### B2 — item 11 is inverted: 2030 offshore is pinned at 8 GW, not 2 262 MW

> **FIXED 3 Sept.** `BE,offwind-all` is `min = max = 2262` in 2025 **and**
> 2030, floor 4 362 in 2040, 5 800 in 2050 — the item as written. The three
> hand-split `BEVLG` rows (offwind 8 000, solar 10 000, onwind 2 000) are gone;
> with B1 fixed the `BE` row does that arithmetic itself. Edited in
> `config/input_parameters_for_models.csv` (the agg CSVs are generated) and
> re-synced. `check_res_envelope.py` now polices `BEVLG`/`BEBRU` rows too and
> rejects a resurrected 8 GW row. **The 2025 network must be re-solved before
> 2030 can run — see B8.**

`agg_p_nom_minmax_demande_haute.csv` now carries `BE,offwind-all` and
`BEVLG,offwind-all` **2030 min = max = 8 000 MW**, and the 2040/2050 floors
(4 362 / 5 800) sit *below* that, so they are slack. The meeting asked for the
opposite — "pas de nouvelles installations prévues entre maintenant et 2030" —
and the item's own action table says `min = max = 2 262`. The 8 GW pin is a
work-around for B1 (2030 brownfield inherited the 8 GW that 2025 built), not a
decision; it makes 2030 look *better* than the published run instead of worse,
which is the exact opposite of what the item warned would happen.

**What was done.** Values restored as above. Both guards that certified the
artefact are repaired: `test_be_offwind_2030_is_the_standing_fleet` asserts
2 262 (its name is true again) and a new `test_no_hand_split_bevlg_res_rows`
keeps the national targets undivided. `check_res_envelope.py` gained
`POLICED = MODELLED + (BEVLG, BEBRU)`, so region rows obey the same
"no stored max after 2025, no stored min after 2030" design; completeness is
still only asked of `MODELLED`, because a region inherits its parent's row.

### B3 — item 9: the industry-CC floor cannot be met (2040 and 2050 infeasible)

> **FIXED 3 Sept, via B4.** With the gross inventory the floor is reachable
> from process capture alone (5 434 × 0.95 = 5 162 ≥ 5 077 kt in 2040;
> 5 108 × 0.95 = 4 853 ≥ 4 826 in 2050), which is how TIMES builds it, and
> biomass/gas CC add ~3.5 Mt of further headroom. The floor itself is
> unchanged. Guard: `test_industry_cc_floor.py::test_floor_fits_the_process_inventory`
> reads both CSVs and fails on the old values.

The floor is `4 365 / 5 077 / 5 120 / 4 826 kt` (2035/40/45/50) on BEWAL
`process emissions CC` + `solid biomass for industry CC` + `gas for industry
CC`. Port mapping and units in `named_pins.py` are correct. The volumes are
not reachable: capture is bounded by the industrial demand those links serve
(`resources/.../industrial_energy_demand_base_s_adm_<y>.csv`), at
`capture_rate = 0.95`, CO₂ intensity 0.3667 (biomass) / 0.198 (gas) t/MWh and
link efficiency 0.9.

| Maximum BEWAL capture, all demand routed through CC | 2040 | 2050 |
|---|---:|---:|
| solid biomass for industry (7.62 / 6.98 TWh) | 2.95 | 2.70 |
| gas for industry (5.56 / 3.85 TWh) | 1.16 | 0.80 |
| process emissions, at the item-12 load (0.357 / 0.282 Mt) | 0.34 | 0.27 |
| **ceiling (Mt/a)** | **4.45** | **3.77** |
| **floor demanded by item 9 (Mt/a)** | **5.08** | **4.83** |

Short by 0.6 Mt in 2040 and 1.1 Mt in 2050, even with 100 % of Walloon
industrial gas *and* biomass routed through capture — this alone would have
failed the run at 2040. Fixing B4 removes the gap; the table above is the
*before* state, kept as the reason the guard exists.

Also label the consequence wherever this is published: Belgian `co2
sequestered` `e_nom_max` is 0 (item 2), so a ~5 Mt/a capture floor at BEWAL is
a ~5 Mt/a **CO₂ export** to DE/NL/GB over `CO2 pipeline`.

### B4 — item 12 puts a *net-of-capture* TIMES figure on a *gross* PyPSA load

> **FIXED 3 Sept.** The BEWAL `process emissions` Load is now `INDCO2P +
> INDCO2c`: 4 411.62 / 3 946.10 / **5 433.90** / **5 108.04** kt for
> 2025/30/40/50 (2025 and 2030 are unchanged — no CC process runs before 2035).
> Guards: `test_process_emissions_load.py::test_load_is_gross_not_the_atmosphere_residual`
> and the B3 headroom check.

`custom_potentials.csv` sets the BEWAL `process emissions` Load to
`VAR_Comnet` of `INDCO2P` — 4 411.62 / 3 946.10 / 357.01 / 281.64 kt. That
commodity is process CO₂ **emitted to the atmosphere**. TIMES routes the
captured part to a *different* commodity, `INDCO2c`, produced by the CC process
variants (`ICMPRDCC_02`, `ILMQLMPRCC02`, `IGFFLATOXYCC01`, `IGHHOLLOWOXYCC01`,
`IGHOTOCC01`) and consumed by `STORAGEMININD`. In PyPSA the load is the input
to the process-emissions bus, *before* `process emissions CC` takes its share,
so the gross figure is what belongs there:

| kt/a | 2025 | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|---:|---:|
| emitted `INDCO2P` (used today) | 4 411.6 | 3 946.1 | 964.4 | 357.0 | 327.5 | 281.6 |
| captured `INDCO2c` = `STORAGEMININD` | 0 | 0 | 4 364.6 | 5 076.9 | 5 120.0 | 4 826.4 |
| **gross = what the load should be** | **4 411.6** | **3 946.1** | **5 329.0** | **5 433.9** | **5 447.5** | **5 108.0** |

2025/2030 are therefore right and 2040/2050 are 15–18× too low. With the gross
load, item 9's floor becomes feasible almost entirely from process capture
(5 434 × 0.95 = 5.16 Mt ≥ 5.08 in 2040; 5 108 × 0.95 = 4.85 ≥ 4.83 in 2050) —
i.e. it reproduces TIMES's own structure instead of forcing capture onto the
fuel chain. It also restores a Walloon process inventory of the right order:
PyPSA-Eur's own default is ~2.0 Mt in every horizon, so TIMES is ~2.7× higher,
not 5–6× lower.

Two "attentions" of the original item are still unanswered and should be
recorded when this is redone: (i) `INDCO2N` (6.0 → 0.4 Mt) is the *combustion*
CO₂ of the same industrial processes and is correctly excluded, but nobody has
checked it against the industrial energy PyPSA imports; (ii) part of `INDCO2c`
comes from oxy-fuel glass/cement units and may mix process with combustion
carbon — the split needs ICEDD.

### B5 — item 8 took rooftop out of `solar-all`, which unpins 2025 PV

> **FIXED 4 Sept (fleet split).** `solar rooftop` is back in `rename_solar`
> (option i, 3 Sept) and the base-year fleet is now split:
> `electricity.baseyear_pv_split` relabels **1 770 MW** of the standing
> vintages (newest first) as non-extendable `solar rooftop` on
> `BEWAL low voltage` (`data/walloon/baseyear_pv_split.csv`), next to the
> 2 668 MW `solar-all` 2025 pin (Energy Balance for Wallonia 2025) that
> `--write` now carries. 2025 is therefore differentiated by *capacity*
> (rooftop >= 1 770 hard, ground <= 898 via the total pin), and item 8's
> TIMES share is enabled from 2030 on (71.4 % 2030, 85.8 % 2050). Guards:
> `test_baseyear_pv_split.py` (5 cases, including CSV/pin consistency);
> `test_rooftop_share.py` still covers the share.

To make 2025 solvable, `rename_solar` no longer maps `solar rooftop` into
`solar-all`. The Elia numbers in the caps file (BE 9 751, BEWAL 4 088 MW in
2025; BE 16 500, BEWAL 6 500 in 2030) are **total** PV — `res_build_rates.csv`
derives the regional split from exactly that total. With rooftop outside the
group, the historical pin bounds utility+hsat only, and the retained 2025
network has **5 510 MW** of Walloon PV (4 088 utility + 1 422 rooftop) against a
4 088 MW pin. The same reasoning applies to the 2030 Elia floors.

The LV country alias (`alias_low_voltage_countries`) is correct but currently
inert: with rooftop out of `solar-all` and no `solar rooftop` row anywhere, no
constraint groups it.

**What was done, and what is still owed.** Option (i): the group is total PV
again. That restores the base-year pin but does **not** revive item 8 — a
share of total capacity cannot be imposed on a year pinned to a fleet PyPSA
labels entirely `solar`, while TIMES has 0.5 GW rooftop + 1.4 GW utility in
2025. **Owed:** either split the historical fleet between rooftop and utility
(a data question for ICEDD/Elia), or restate item 8 as a share of *new build*.
The 2030 clash is now Elia's 6.5 GW **total** PV floor for Wallonia against
TIMES's 7.3 GW total (5.2 rooftop + 2.1 utility) — smaller than it looked, but
still a number the meeting has to pick.

### B6 — item 6a measures the wrong quantity, three times over

> **FIXED 3 Sept (the expression; the number is still owed).** One constraint
> over AC and DC together, both legs of every DC pair, physical flows. Point 1
> is **withdrawn**: `Transfo_Imp` is itself a one-way annual flow, so the
> hourly-positive-part formulation is the right analogue — the earlier 6h
> *net* table was the wrong yardstick, not the constraint. The flag stays off
> until the TWh values are re-measured on a solved 1h network with the
> corrected expression. Guards: `test_import_limit.py` (7 cases; two of them
> fail when either defect is put back).

`add_selfsufficiency_constraints` is off in both overlays and should stay off
until the values are settled. As written, `Import_p` was not comparable with
TIMES `Transfo_Imp`:

1. ~~Gross hourly, not annual net.~~ **Not a defect.** `Import_p ≥ 0` summed
   over 8 760 h is the one-way annual inflow, which is what TIMES's
   `Transfo_Imp` process measures too. What was wrong is the *yardstick* used
   to size it: the step-0 table (−12.5 / −2.4 / 7.0 / 2.7 TWh) is annual
   **net** on 6h files. The 2025 1h network is a net exporter (−1.53 TWh) and
   still takes in ~13 TWh one-way (8.2 from abroad), so 2.94 TWh for 2030 is
   the number to re-examine, not the formulation.
2. **`max`, not sum.** The lower bound is added once per component type
   (`import_positive_Line`, `import_positive_Link`), so the variable is
   `≥ max(AC net, DC net)`, never their sum. BEWAL has both.
3. **DC imports are invisible.** The link selection drops every `…-reversed`
   leg, but with lossy bidirectional links the import direction *is* the
   reversed leg. BEWAL's only DC border is ALEGrO
   (`relation/8193755-320-DC`, 1 000 MW to DE): the cap sees the export leg
   only, so imports from Germany never enter the sum.
4. **Flows are inflated.** Lines use `Line-s / s_max_pu` (+43 %, `s_max_pu`
   is 0.7 everywhere) and links `Link-p / efficiency`. For an energy cap the
   physical flow is what counts (`p × efficiency` arriving at `bus1`).

**Still owed.** Re-measure `Import_p` on a solved 1h network with the corrected
expression, then choose the TWh values with the meeting — TIMES's 2.94 / 6.47 /
10 may simply not be transferable to an hourly model that trades with Flanders.
Keep the label "BEWAL imports include Flanders and Brussels" on any chart.

### B7 — generated files are out of sync; two tests fail

> **FIXED 3 Sept.** `python -m pytest test/ -q` is now **293 passed, 0 failed**.
> `--check` reports `CHECK PASSED`. Three values reached the model:
> `onwind` 30 → **25** y, `solar-rooftop` 40 → **25** y, `solar-utility`
> 40 → **25** y — a real change to annuities and myopic retirement that had
> been sitting inert since `788cc75a`.

`python -m pytest test/ -q` → **2 failed, 283 passed** before the fix:

- `test_discount_rates.py::test_check_mode_passes`. `build_common_parameters.py
  --check` reports 43 problems. The important one: master commit `788cc75a`
  set PV and onwind `lifetime` to 25 years in
  `config/input_parameters_for_models.csv`, but `data/walloon/custom_costs.csv`
  was never regenerated and still says 30 / 40 / 40 years — **the lifetime
  change is not in the model**. The rest are missing `units` /
  `year_currency` on the rows added by `4459a96c` (central gas CHP, central
  solid biomass CHP, SMR, H2 (l) storage tank). **Done:** all 20 offending
  rows are TIMES-side reference documentation — `status` blank,
  `pypsa_wal_target` blank, read by nothing — so `check_currency` is now scoped
  to rows that actually carry a `pypsa_wal_target`, and `--check` lists the
  others as a note. Their source currency (EUR2010/2012/2013) is left as
  recorded rather than silently retagged EUR2025. **If the team wants them
  usable they still need a currency decision** — either rebase the values or
  follow the `common_parameters.md` §4.4 "retag only" convention.
- `test_config_schema.py::test_config_default_yaml_in_sync`. Item 16 added
  `sector.district_heating.ptes.e_nom_max_weeks` to `config.default.yaml` but
  not to the `ptes` default in `scripts/lib/validation/config/sector.py`.
  **Done:** the key is in the schema (documented in the field description) and
  `config.default.yaml` / `schema.default.json` are regenerated.

### B8 — the myopic chain is not internally consistent

> **OPEN — this is the one item that needs a run, not an edit.** Every code and
> data fix above is in, but the 2025 network on the cluster was solved under
> the old grouping and carries 8 GW of Belgian offshore against a pin that is
> now 2 262 MW. **Do not restart at 2030.** Delete the solved networks and run
> the chain from 2025. As a diagnostic aid, `add_CCL_constraints` now logs
> `"<country> <carrier> at <year>: the standing fleet already exceeds the
> aggregate cap by N MW"` — the condition Gurobi reports as
> "infeasible or unbounded in 0 barrier iterations" with no IIS, and which was
> blamed on three different items in turn.

The 2025 `.nc` has been kept across four input changes and is the brownfield
base for 2030–2050. It was solved with: the rooftop share pin **on** (1 422 MW,
25.8 %), no `BEVLG` remainder rows, and 8 GW of Belgian offshore. 2030–2050 are
being solved with rooftop **off**, 6a **off** and the BEVLG rows **in**. After
B1/B2/B5 are settled, 2025 has to be re-solved; a chain whose base year obeys a
different constraint set than the later horizons cannot be reviewed as one run.

### B9 — minor: `ptes.e_nom_max_weeks` binds a vintage, not the fleet

> **FIXED 3 Sept.** `apply_ptes_fleet_cap()` runs in `add_brownfield` after the
> earlier vintages are in: inherited `e_nom` is subtracted and the residual is
> written on the extendable Store, so four weeks is a ceiling on the standing
> fleet. Guard: three cases in `test_ptes_e_nom_max.py`.

Water-pit stores are vintaged by `add_brownfield` (`… water pits-2025`,
`-2030`, …) and each new extendable vintage gets its own 4-week ceiling, so the
standing fleet can reach 4 weeks × horizons. The 2030 value is right
(BEWAL 1.29 TWh_th DH → 99 GWh_th), so this only matters in 2050. Same pattern
as the caps that used to bind the extendable tranche only.

---

## Still open — no code, decide in a meeting

- **17a. Coal for industry** soft-link gap +10 / +14 / **+37** / +23 % —
  accounting, not a solve failure.
- **17b. DE 2030 onwind 115 GW** is a collapsed corridor (target above the
  growth cap) and still sets the 2030 European price signal. Accept, or let the
  growth cap win?
- **17c. `enc_pe` / `pac_fe` / `vap_se` Sankey WARNs** — known mapping holes.
- **17d. Biogas 4.0 / 6.9 TWh citation** still owed by ICEDD. The vd runs
  7.67 / 8.07 TWh, so this is a deliberate divergence from TIMES: do not
  publish it as TIMES-consistent. Ask at the same time whether 2025/2030 should
  come down from 8.3 (the cap is non-monotonic today).
- **6a / 8** need a decision, not only a fix: which import metric, and what
  `solar-all` means (B5, B6).

---

## Order of work

Everything below the line is done and guarded; `python -m pytest test/ -q` is
**300 passed**, `build_common_parameters.py --check` is `CHECK PASSED`, and
`check_res_envelope.py` is `OK`.

```
done  B1  carrier-aware CCL grouping; bus countries no longer mutated
      B4  process-emissions load = gross (emitted + captured)
      B3  item-9 floor now reachable; headroom guard across both CSVs
      B2  item 11 back to 2 262 MW; hand-split BEVLG rows removed
      B7  --check passes; PV/onwind lifetime 25 y finally reaches the model
      B5  rooftop back inside solar-all; LV alias deleted
      B6  one import constraint, both DC legs, physical flows
      B9  water-pit ceiling applies to the fleet
─────────────────────────────────────────────────────────────────────────────
next  B8  re-solve 2025 → 2030 → 2040 → 2050 from scratch, then a §11 review
```

**Still owed, and each needs a decision rather than an edit:**

- **B6 / item 6a.** Re-measure `Import_p` on a solved 1h network with the
  corrected expression, then pick the TWh values. TIMES's 2.94 / 6.47 / 10 may
  not be transferable to an hourly model that trades with Flanders.
- **B7 leftover.** The 20 JRC/ETRI reference rows keep their source currency and
  reach nothing. If they are ever to be used, they need rebasing or the
  `common_parameters.md` §4.4 "retag only" treatment.
- **Housekeeping.** `diag2030.sh`, `diag2040.sh`, `diag2040b.sh`,
  `run_20260829.sh`, `solve2025.sh` are still tracked at the repository root.

**What the next run should show, relative to the last published one.** 2025
Belgian offshore back at ~2 262 MW (was 8 000); 2025 Walloon PV back at the
4 088 MW pin (was 5 510); 2030 Belgian offshore pinned, so 2030 prices, imports
and the CO₂ dual all rise; Walloon process emissions 15–18× higher in 2040/2050
with ~5 Mt/a captured and exported; shorter PV and onwind lifetimes raising
annuities everywhere.

Interactions to keep in mind when reading the final run: items **6a, 10, 11**
all move 2050 independence in opposite directions; items **2, 9, 12, 13** all
move the Walloon CO₂ dual. If the sum is unreadable, fall back to a 6h solve
with 10 and 11 only.

Still not comparable across vintages: total system cost (gas-store floors),
2025 capacities (historical pin), onwind (2 371/4 870/6 500 vs the old flat
6 500 or 12.4 GW).

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
