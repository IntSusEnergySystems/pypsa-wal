# Renewable capacity limits: decisions and justification

**Decided 2026-08-27.** Supersedes the ad-hoc `agg_p_nom_minmax` overrides that
produced a flat 6 500 MW Walloon onshore-wind trajectory and an infeasible 2050
horizon in [`logs/2026-08-26_scen_demande_haute_2010_1h.md`](logs/2026-08-26_scen_demande_haute_2010_1h.md).

This scenario is a **techno-economic optimum**, not a simulation of stated
policy. The limits below exist to keep that optimum inside what is physically
and industrially achievable — not to prescribe the answer.

---

## 1. Three limits, three different jobs

| Limit | Encodes | Where it comes from | Written in a CSV? |
|---|---|---|---|
| **Land / sea potential** | what the resource could physically host | **calculated** by atlite, per node and technology | no — only where the calculation is unusable (§2) |
| **Max growth rate** | how fast an industry can actually build | **calculated** from IRENA annual statistics × a multiplier | no — only the multiplier |
| **2030 corridor** | near-term commitments already in motion | national targets | yes — this is the only routine override |

The previous design confused these. A *policy minimum* was being used to repair
a broken *potential maximum*, and once a minimum has to exceed a maximum the LP
is empty — which is exactly how the 2050 horizon was lost.

**Design rule: minimise stored overrides.** Potentials and growth caps are
computed at run time. The CSV carries only the 2025 base year, the 2030
corridor, and the offshore potentials of §2.

## 2. Offshore potential comes from marine spatial plans, not atlite

PyPSA-Eur's offshore potential is unusable in the southern North Sea. It returns
**less than the capacity already standing**:

| node | atlite potential | installed 2024 |
|---|---:|---:|
| BE (BEVLG) | 689 MW | **2 262 MW** |
| NL | 4 504 MW | **4 748 MW** |
| DE | 5 154 MW | **9 215 MW** |

The cause is a single parameter: `capacity_per_sqkm: 2` MW/km², set deliberately
upstream ([PR #280](https://github.com/PyPSA/pypsa-eur/pull/280),
[issue #210](https://github.com/PyPSA/pypsa-eur/issues/210)) as a conservative
*deployment* prior, haircutting the ~10 MW/km² technical density of its own cited
reference. The offshore regions and exclusions are fine — BEVLG covers the full
3 492 km² Belgian EEZ, and the eligible area that survives is the same order as
what national plans actually designate.

That prior is reasonable for continental scenario exploration, where the model
picks sites out of an ocean. It fails for a Belgium-focused study, because for
these three countries the question it hedges — *how much of the sea gets
developed?* — is already answered by policy. Belgium's Princess Elisabeth Zone
alone is **285 km² designated for 3 500 MW** (12.3 MW/km²), on 83 % of the area
atlite deems eligible in the entire Belgian EEZ.

**Decision.** Override offshore `p_nom_max` per coastal node from national
marine spatial plans, in `custom_potentials.csv`. Leave PyPSA-Eur's global
`capacity_per_sqkm` untouched — raising it would give GB 586 GW and FR 184 GW,
no more meaningful than 2 MW/km² was.

| node | offshore potential | source |
|---|---:|---|
| BEVLG | 8 000 | Belgian NECP 5.8 GW + PEZ repowering headroom (a *potential*; on the delivery date of that 5.8 GW see §4.2) |
| DE | 70 000 | WindSeeG (30 GW 2030 / 40 GW 2035 / 70 GW 2045) |
| NL | 50 000 | North Sea Wind Energy Infrastructure Plan, Jul 2025 |
| GB | 80 000 | Clean Power 2030 trajectory extended |
| FR | 45 000 | PPE3 / SNBC long-run |

These replace four *undocumented* `BEVLG,offwind,p_nom_max,inf` rows that carried
no source at all.

Onshore and solar potentials are **left as PyPSA-Eur calculates them**. They are
ordinary technical potentials — 3.0× Germany's 2045 ambition, 24× France's PPE3
target — which is what a technical potential should look like. The only local
overrides are Wallonia's, where PNEC-PACE / EDORA data is better than the raster:
`BEWAL onwind 6 500`, `BEWAL solar 13 000`, `BEWAL solar rooftop 46 000` MW.

## 3. Growth rate: 2 × the IRENA annual record

`add_existing_baseyear.py` already reads `pm.data.IRENASTAT()` and computes
annual capacity additions per country and technology (`df.diff(axis=1)`), then
discards the annual resolution by binning into five-year vintages. The workflow
re-uses that same series to derive the build-rate limit — same source, no new
data, and it covers Belgium (which `powerplants.csv` does not: 0 % coverage for
Belgian wind and solar).

**Decision.** The limit is `2 × the single best annual addition observed
2000-2024`, applied as a ceiling on new build per horizon:

```
fleet(horizon) ≤ fleet(previous horizon) + 2 × record_annual × years_elapsed
```

Rationale for each choice:

- **Absolute MW/yr, not a growth fraction.** A relative rule cannot start a ramp
  from near-zero (French offshore at 1 486 MW would need ~25 %/yr for 25 years to
  reach 45 GW) and gives absurd allowances at the top (10 %/yr on 400 GW of German
  solar is 40 GW/yr). For mature onshore and solar markets the binding constraint
  is land, permitting and social acceptance, which does not scale with the fleet.
- **Single best year, not a multi-year average.** Five-year averages blend
  ramp-up with collapse years — Germany's 2019 crash sits inside its 2016-20
  window — and understate what the industry has demonstrated. Record year is the
  honest measure of demonstrated capability.
- **Multiplier 2 ×.** Chosen to keep this run comparable with the previous one
  rather than from first principles. It puts German 2050 onshore wind at 308 GW
  against the 365 GW the unconstrained run built — a real but modest tightening.
  It is a **configuration parameter**, and it is the one number in this document
  that is a judgement call rather than a measurement. Sensitivity-test it.

Observed records (MW/yr, IRENASTAT 2000-2024):

| | onwind | solar | offwind |
|---|---:|---:|---:|
| DE | 4 891 (2017) | 15 061 (2024) | 2 289 (2015) |
| FR | 1 933 (2017) | 4 129 (2024) | 986 (2023) |
| GB | 1 764 (2017) | 4 073 (2015) | 2 672 (2022) |
| NL | 998 (2021) | 3 918 (2023) | 1 502 (2020) |
| BE | 355 (2022) | 1 571 (2023) | 706 (2020) |
| LU | 56 (2016) | 129 (2024) | — |

IRENASTAT is country-level, so the Belgian rate is apportioned to BEWAL by its
share of existing capacity — the same apportionment `add_existing_baseyear`
already uses. Walloon onshore is 70.7 % of the Belgian fleet, giving 251 MW/yr.

## 4. The 2030 corridor

2030 is five years out. Most of what will stand then is already permitted,
tendered or under construction, so leaving it to the optimiser produces a
counterfactual rather than a forecast.

**Decision** (revised 30 Aug 2026 — see §4.1). For every node and technology:

```
min(2030) = min( land potential , national target )
max(2030) = min( land potential , growth cap )   … unless that would put the
                                                   ceiling at or below the floor,
                                                   in which case the growth cap
                                                   is dropped for that group
```

The floor is never clipped down to the growth cap. Where a national target is
reachable the target is the floor and the growth cap is a real ceiling above it;
where the target needs more than the industry has ever built, the target still
stands and the growth cap is discarded with a warning naming the group and both
numbers, leaving land use as the binding ceiling.

### 4.1 Why the floor is no longer clipped to the growth cap

The rule used to read `min(2030) = min(land, growth, target)`, so that the floor
could never exceed the ceiling. That is feasible by construction, but where the
target exceeds the growth cap it makes both bounds the *same number* and the
corridor collapses to a point. At 2030 that happened to two groups at once:

| group | stated floor | 2 × record × 5 yr | overshoot |
|---|---:|---:|---:|
| `GB offwind-all` | 34 008 MW | 26 720 MW | +27 % |
| `DE onwind` | 57 169 MW | 48 910 MW | +17 % |

The 2030 barrier then failed twice with `Numerical trouble encountered` and
*"Model may be infeasible or unbounded"*, dual infeasibility pinned at
`4.19e-04` for 200 iterations (269 iter / 3940 s, then 201 / 2424 s). With the
growth limit switched off entirely the same model solved in 169 iterations
(3.69148007e+11); with the precedence rule above it solved in 213 iterations at
**3.69265168e+11**, within +0.03 % — so the discarded ceilings were doing no
economic work, only creating a degenerate equality.

The warning is the point. "This 2030 target needs more than twice the best year
the industry has ever had" is a finding about the scenario; silently reconciling
the two numbers hid it.

### 4.2 The Belgian 2030 offshore floor is not deliverable

**Reviewed 2026-09-01** (FR / NL / EN press review, at the request of the 1 Sept
meeting). `BE offwind-all` carries **2030 min = 5 800 MW**, tagged
`NECP-BE-2030` — 2 262 MW standing plus the 3.5 GW Princess Elisabeth Zone
(PEZ I 700 + PEZ II 1 400 + PEZ III 1 400 MW). It is also the **only** offshore
floor in the caps file: 2035–2050 are blank. The model is therefore obliged to
commission the whole zone by 2030 and free to add nothing afterwards — the
inverse of the actual schedule.

What the sources say:

- **Feb 2025** — Elia postpones signing the island's **HVDC** contracts (island
  budget 3.6 → 7–8 bn EUR); reported as a ~3-year slip for that phase, which is
  the one carrying **PEZ III** and Nautilus ("from 2032"). The contracted HVAC
  phase serves PEZ I + II only.
- **Jul 2025** — the PEZ-1 tender is **withdrawn**: legal, calendar and financial
  framework judged unworkable.
- **Feb / May 2026** — relaunch misses the promised deadline; ~2 years lost;
  the delay is costed at ~400 MEUR by 2030 (EnergyVille, via Agoria).
- **18 Jul 2026** — new framework approved (two-sided CfD, no strike-price cap,
  construction window **48 → 60 months**, bid preparation ≥ 6 months plus a fixed
  5-month evaluation). Still awaiting Council of State review and EC state-aid
  clearance; relaunch planned late Sept / early Oct 2026.
- Island phase 1 (**MOG II**) must be operational by **1 Oct 2031** — no wind
  farm can export before its grid connection exists.
- The government now frames security of supply as "from 2035"; PATHS2050 asks for
  the zone operational by 2035; commentary states the park "will no longer
  contribute in time" to the 2030 EU 42.5 % target, with supply-security concerns
  in 2030–2032.

Arithmetic on the framework's own parameters — relaunch late 2026 → bids mid
2027 → award ~late 2027 → up to 60 months of construction, gated by the island in
Oct 2031 — puts **first PEZ-I power in 2031–2032 at the earliest**, the full
700 MW around 2032–33, PEZ II after that and PEZ III behind the postponed HVDC.
**No new Belgian offshore capacity can be online in 2030.**

Proposed retiming (not yet implemented; improvement-plan item 11):

| `BE offwind-all` | 2030 | 2040 | 2050 |
|---|---:|---:|---:|
| now | min **5 800** | — | — |
| proposed | min = max **2 262** (standing fleet) | min **4 362** (+ PEZ I + II, the contracted HVAC) | min **5 800** (full zone) |

Points of attention:

- 5 800 is a **min**, not a max — lowering a ceiling changes nothing. Pinning
  `min = max` at 2030 is what implements "no new installations before 2030", and
  the 0.5 % `tolerance` of §5.1 keeps that collapsed corridor solvable.
- Do **not** put the full 5 800 into 2040 as a floor: PEZ III depends on an HVDC
  decision that has slipped ~3 years and is not contracted. 4 362 MW is the
  committed-infrastructure reading.
- The §2 ceiling (BEVLG `p_nom_max` = 8 000 MW) is unaffected — it is a *sea
  potential*; this finding is about *timing*. And the same "policy target used as
  a floor" pattern is worth re-checking on the neighbours (NL 12 000, FR 3 600,
  GB 50 000 → clipped to 42 636 by growth).
- Removing ~3.5 GW of cheap offshore will make **2030 look worse**: higher
  Belgian prices, more imports, more gas, a higher 2030 CO₂ dual.

Sources:
[tender withdrawn (Jul 2025)](https://www.offshorewind.biz/2025/07/01/belgium-delays-tender-for-offshore-wind-farm-in-princess-elisabeth-zone-until-2026/) ·
[new framework and 1 Oct 2031 (Jul 2026)](https://www.offshorewind.biz/2026/07/24/belgium-approves-new-tender-framework-for-first-princess-elisabeth-zone-offshore-wind-site/) ·
[construction 48 → 60 months, bid and evaluation windows](https://www.loyensloeff.com/insights/news--events/news/belgium-offshore-wind-tender-amendment-and-ventilus-permit-push/) ·
[amended plan, PEZ 1 = 700 MW](https://www.rivieramm.com/news-content-hub/belgium-amends-plan-for-princess-elisabeth-zone-offshore-wind-tender-89460) ·
[Elia postpones the HVDC contracts](https://www.elia.be/nl/pers/2025/02/20250204_elia-temporarily-postpones-signing-hvdc-contracts-for-princess-elisabeth-island) ·
[RTBF: le retard, PEZ 1 / PEZ 2 capacities](https://www.rtbf.be/article/eolien-offshore-l-extension-de-la-capacite-belge-a-pris-du-retard-11727009) ·
[La Libre: ~400 MEUR pour les ménages](https://www.lalibre.be/dernieres-depeches/2026/05/12/le-retard-dans-leolien-offshore-coutera-des-centaines-de-millions-aux-menages-TAHEAHNJEJEB3LZPNF2CKPFQ5E/) ·
[La Libre: pas lancé ce trimestre (Feb 2026)](https://www.lalibre.be/belgique/politique-belge/2026/02/26/lappel-doffres-pour-la-zone-princesse-elisabeth-ne-sera-pas-lance-ce-trimestre-UGY7F3SOSZGF7DS2H66O2EDCKI/) ·
[Vandenbulcke: tender misses the deadline](https://www.flows.be/offshore/2026/02/vandenbulcke-tender-prinses-elisabeth-eiland-mist-beloofde-deadline/) ·
[island cost, missed 2030 EU target, 2030–32 supply concerns](https://gasoutlook.com/analysis/surging-costs-cloud-outlook-for-belgian-princess-elisabeth-wind-island/) ·
[relaunch late Sept / early Oct 2026](https://www.indegazette.be/nieuwe-regels-brengen-eerste-windpark-in-prinses-elisabethzone-dichterbij/) ·
[government: supply "from 2035"](https://www.seatalk.be/techniek-innovatie/2026/04/20/belgie-zet-offshorewind-in-prinses-elisabeth-zone-opnieuw-in-beweging/) ·
[industry doubts the realisation](https://www.lavenir.net/actu/2026/01/26/par-eolien-offshore-princesse-elisabeth-les-cooperatives-citoyennes-craignent-lexclusion-lindustrie-doute-de-sa-realisation-7FOLBRB5RBFSHJSZU6JU7PV3XA/)

## 5. 2040 and 2050

**Decision.** No policy limits at all. Both bounds are calculated:

```
max(horizon) = min( land potential , growth cap )
no minimum
```

Beyond 2030 stated policy is weak evidence anyway — PPE3 stops at 2035, the
Netherlands cut its 2040 offshore target from 50 to 30-40 GW in July 2025, and
Britain has nothing legislated past 2030. Using extrapolated policy as a hard
ceiling would assume the answer; a technical potential plus a demonstrated build
rate does not.

The base year is the one exception in the other direction: **2025 is pinned to
the historical fleet** (`min = max`), so it is a calibration, not an
optimisation. Without it the model built 4 796 MW of Walloon onshore wind in a
single year. That pin needs a width — see §5.1.

### 5.1 A pinned corridor needs a stated width

`min == max` on an aggregate is an equality on a *sum* of extendable capacities,
and with `include_existing` both constraints subtract the same standing fleet.
The residual right-hand side is then a difference of near-equal large numbers:
for `BE offwind-all` at 2025 the cap is 2 262 MW against 2 261.8 MW standing, so
the model is asked to drive a sum of variables whose own bounds add to 16 000 MW
onto **0.20 MW**, from both sides. On 29 Aug the 2025 barrier stopped 3.4 % above
its own dual bound and Gurobi reported `Sub-optimal termination`.

Eighteen of the twenty two-sided groups in the 2025 column are pinned this way,
so this is the normal case, not an edge case.

**Decision.** The caps files carry a `tolerance` column giving a *relative*
corridor width per (country, carrier) row; `solve_network.corridor_tolerance`
reads it and the ceiling of a collapsed corridor is lifted to
`min × (1 + tolerance)`. The width is data because it is a statement about how
precisely a given source pins that row's fleet — not a property of the code or
the solver. A blank cell, or a caps file without the column (upstream's
`data/agg_p_nom_minmax.csv`), keeps the exact equality.

Currently every collapsed row carries **0.005**, i.e. half a percent, which is
well inside the accuracy of the capacity statistics the caps come from. At the
stock solver settings this turned the 2025 solve from `Sub-optimal termination`
(212 iter / 1985 s, 3.4 % gap) into `Optimal objective 3.51964349e+11`
(235 iter / 1895 s) — no slower, and certified. `review_run.py` reads the same
column when it checks aggregate maxima, so a fleet sitting inside
`max × (1 + tolerance)` is a pass, not an overshoot.

The same width applies to corridors that collapse while the right-hand sides are
being built rather than in the file: at 2040 `BE nuclear-all` collapses on both
the generator and the link path and is widened by its own row's value.

## 6. What this produces

### 2030 — the corridor

| node | carrier | 2025 | rate MW/yr | growth cap | land | **max** | binds | target | **min** |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|
| BE | onwind | 3 337 | 355 | 6 887 | 10 976 | **6 887** | growth | 5 000 | **5 000** |
| BE | solar-all | 9 751 | 1 571 | 25 458 | 136 591 | **25 458** | growth | 16 500 | **16 500** |
| BE | offwind-all | 2 262 | 706 | 9 325 | 8 000 | **8 000** | land | 5 800 | **5 800** |
| BEWAL | onwind | 2 359 | 251 | 4 869 | 6 500 | **4 869** | growth | 3 000 | **3 000** |
| BEWAL | solar-all | 4 088 | 658 | 10 673 | 13 000 | **10 673** | growth | 6 500 | **6 500** |
| DE | onwind | 63 608 | 4 891 | 112 518 | 487 837 | **112 518** | growth | 115 000 | **112 518** ⚠ |
| DE | solar-all | 89 829 | 15 061 | 240 439 | 1 249 280 | **240 439** | growth | 215 000 | **215 000** |
| DE | offwind-all | 9 215 | 2 289 | 32 105 | 70 000 | **32 105** | growth | 30 000 | **30 000** |
| FR | onwind | 23 105 | 1 933 | 42 433 | 968 581 | **42 433** | growth | 31 000 | **31 000** |
| FR | solar-all | 21 521 | 4 129 | 62 811 | 1 811 328 | **62 811** | growth | 48 000 | **48 000** |
| FR | offwind-all | 1 486 | 986 | 11 343 | 45 000 | **11 343** | growth | 3 600 | **3 600** |
| GB | onwind | 16 230 | 1 764 | 33 870 | 438 656 | **33 870** | growth | 29 000 | **29 000** |
| GB | solar-all | 17 879 | 4 073 | 58 609 | 980 997 | **58 609** | growth | 47 000 | **47 000** |
| GB | offwind-all | 15 916 | 2 672 | 42 636 | 80 000 | **42 636** | growth | 50 000 | **42 636** ⚠ |
| NL | onwind | 6 987 | 998 | 16 963 | 46 852 | **16 963** | growth | 10 000 | **10 000** |
| NL | solar-all | 24 035 | 3 918 | 63 217 | 170 144 | **63 217** | growth | 30 000 | **30 000** |
| NL | offwind-all | 4 748 | 1 502 | 19 773 | 50 000 | **19 773** | growth | 12 000 | **12 000** |
| LU | onwind | 227 | 56 | 786 | 2 253 | **786** | growth | 453 | **453** |
| LU | solar-all | 524 | 129 | 1 814 | 7 017 | **1 814** | growth | 1 236 | **1 236** |

⚠ **Two corridors collapse to a point**, where the national target is *above*
what 2 × the record allows: German onshore wind (target 115 000, cap 112 518) and
British offshore wind (target 50 000, cap 42 636). Those two are pinned at
maximum growth with no optimiser freedom in 2030. See §7.

The growth cap binds nearly everywhere in 2030 — land binds only for Belgian
offshore. That is the expected shape five years out: the constraint is how fast
you can build, not whether there is room.

The `BE offwind-all` **min of 5 800** in that table is now known to be
undeliverable — nothing new can be commissioned in Belgian waters by 2030
(§4.2). The row is unchanged in the shipped caps file; the retiming is
improvement-plan item 11.

### 2050 — the envelope

| node | carrier | growth cap | land | **max** | binds |
|---|---|---:|---:|---:|---|
| BE | onwind | 21 087 | 10 976 | **10 976** | land |
| BE | solar-all | 88 286 | 136 591 | **88 286** | growth |
| BE | offwind-all | 37 577 | 8 000 | **8 000** | land |
| BEWAL | onwind | 14 907 | 6 500 | **6 500** | land |
| BEWAL | solar-all | 37 013 | 13 000 | **13 000** | land |
| DE | onwind | 308 158 | 487 837 | **308 158** | growth |
| DE | solar-all | 842 879 | 1 249 280 | **842 879** | growth |
| DE | offwind-all | 123 665 | 70 000 | **70 000** | land |
| FR | onwind | 119 744 | 968 581 | **119 744** | growth |
| FR | solar-all | 227 969 | 1 811 328 | **227 969** | growth |
| FR | offwind-all | 50 771 | 45 000 | **45 000** | land |
| GB | onwind | 104 430 | 438 656 | **104 430** | growth |
| GB | solar-all | 221 529 | 980 997 | **221 529** | growth |
| GB | offwind-all | 149 516 | 80 000 | **80 000** | land |
| NL | onwind | 56 869 | 46 852 | **46 852** | land |
| NL | solar-all | 219 944 | 170 144 | **170 144** | land |
| LU | onwind | 3 022 | 2 253 | **2 253** | land |
| LU | solar-all | 6 974 | 7 017 | **6 974** | growth |

The two limits divide the work cleanly:

- **Offshore is land-bound everywhere** — the §2 marine-spatial-plan ceilings are
  the operative limit, which is the intent.
- **Onshore and solar are growth-bound in the large countries** (DE, FR, GB) and
  land-bound in the small, dense ones (BE, BEWAL, NL, LU). Also the intent:
  France is not short of farmland, it is short of decades.
- **Wallonia reaches its PNEC/EDORA ceilings** — 6 500 MW onshore and 13 000 MW
  ground-mounted solar — but now on a trajectory (2 359 → 4 869 → … → 6 500)
  instead of jumping to the ceiling in 2025.

Relative to the 26 Aug run, the neighbours tighten substantially: German onshore
wind 365 018 → 308 158 MW, British 181 886 → 104 430, French 145 412 → 119 744,
Dutch 46 852 → 46 852 (unchanged, already at the land bound). The 2050 CO₂ dual,
import prices and congestion rent all move with that.

## 7. Open questions

3. **`BEWAL low voltage` maps to country `BE`**, so Walloon rooftop PV is governed
   by the Belgian cap rather than the Walloon one. There is commented-out
   aliasing code in `add_CCL_constraints` intended to fix exactly this. Worth
   repairing before any Walloon rooftop question is asked of the model — and note
   that rooftop currently comes out at 0 MW for cost reasons (19 % dearer per MW
   than ground-mounted), not because of any cap.
4. **The Belgian 2030 offshore floor (5 800 MW) is not deliverable** — see
   §4.2. Pin 2030 to the standing 2 262 MW and move the Princess Elisabeth Zone
   to the 2040 / 2050 floors. **Not implemented** (improvement-plan item 11).
5. **The envelope is duplicated across three `agg_p_nom_minmax_*` files** that now
   differ in only 2 of 54 rows (the nuclear caps). Nothing checks them against
   each other, and `build_common_parameters.py` manages only the demande-haute
   one. Proposed fix — scenario values as override files layered on the master
   table — in [`scenario-handling-proposal.md`](scenario-handling-proposal.md).
   **Not implemented.**

## 8. Files

| File | Role |
|---|---|
| `config/input_parameters_for_models.csv` | the assumptions of record — 2025 base year and 2030 corridor floor, with `source` and `note` per row. 57 rows, down from 152 once the ceilings became calculated. |
| `data/walloon/agg_p_nom_minmax_<scenario>.csv` | generated from the above by `scripts/build_common_parameters.py --write`. Three values per row: 2025 min, 2025 max, 2030 min — plus a hand-maintained `tolerance` column, the per-row corridor width of §5.1. |
| `data/walloon/custom_potentials.csv` | offshore per-node ceilings (§2) and the Walloon PNEC/EDORA potentials |
| `data/walloon/res_build_rates.csv` | IRENA annual records, generated by `scripts/walloon_scripts/build_res_build_rates.py --network <2025 net>`. Committed rather than fetched at solve time: `add_CCL_constraints` runs on the cluster, where IRENASTAT has neither internet nor a cache. Refresh when IRENA publishes. |
| `config/config.walloon.yaml` | `solving.agg_p_nom_limits.growth_multiplier` (2.0) and `build_rates_file` |
| `scripts/solve_network.py` | `res_growth_allowance()` and its use in both branches of `add_CCL_constraints`; the floor-over-ceiling precedence of §4.1; `corridor_tolerance()` / `widen_collapsed_corridors()` / `_widen_against()` for §5.1 |
| `test/test_corridor_tolerance.py` | guards §4.1 and §5.1, including regressions pinned to the shipped caps file |
| `scripts/walloon_scripts/check_res_envelope.py` | validates the stored overrides against this design; `test/test_res_envelope.py` runs it over every scenario |

### Reproducing the inputs

```bash
python scripts/walloon_scripts/build_res_build_rates.py \
    --network resources/<prefix>/<run>/networks/base_s_adm___2025.nc
python scripts/build_common_parameters.py --check
python scripts/walloon_scripts/check_res_envelope.py \
    data/walloon/agg_p_nom_minmax_demande_haute.csv
```
