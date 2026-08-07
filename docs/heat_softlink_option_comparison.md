# Which heating soft-link should go to `master`? — option C vs option B′

**Status:** decision document. **Date:** 2026-08-07.
**For review before merging one of the two branches.**

| | branch (both repos) | mechanism | design record |
|---|---|---|---|
| **option C** | `heat-softlink-option-c` | annual energy-mix constraint per technology group, with senses and a tolerance | [`heat_soft_linking.md`](heat_soft_linking.md) |
| **option B′** | `heat-softlink-option-b` | reconstructed hourly profile per group, dispatch pinned to it | [`heat_softlink_option_b.md`](heat_softlink_option_b.md) |

Both branches carry the **same** two other harmonisations — the TIMES base-year
appliance stock replacing the EU-2012 row, and the frozen urban/rural split — and
both leave district heating untouched. **The only thing being compared is how the
technology mix is transferred.** The `option-b` branch contains both mechanisms
(option C defaults to off) so the three chains below run from one checkout and
one set of built resources.

Reproduce everything here with:

```bash
bash scripts/walloon_scripts/run_heat_softlink_comparison.sh scen_demande_haute
```

```bash
python scripts/walloon_scripts/compare_heat_softlink.py scen_demande_haute
```

---

## 1. The one-paragraph difference

Both options take the same payload — the TIMES share of Walloon decentral heat
per technology group — and both leave `p_nom` endogenous. **Option C constrains
the year and frees the hour:** each group's annual heat must be at least (or at
most) its TIMES share of the realised supply, ±5 %, and PyPSA decides which hours
each technology runs in. **Option B′ constrains the hour and thereby the year:**
each group's dispatch is pinned to its TIMES share of the hourly heat load, so the
annual mix is TIMES's exactly and the hourly mix is constant.

Everything below follows from that single difference.

---

## 2. Mix fidelity — what each option actually delivers

*(tables from `compare_heat_softlink.py`; TABLES-PENDING)*

The structural expectation, before any numbers:

* **Option C cannot deliver the TIMES mix, by construction.** Its senses are `≥`
  on what TIMES keeps and `≤` on heat pumps, with a 5 % tolerance, so the best
  case is 5 % away and the groups that are not binding float wherever the
  economics put them. In the 2025 chain that showed up as the resistive heater at
  **8.77 %** against a TIMES **6.06 %** — a 2.7 pp, 45 % relative error on a group
  nothing was wrong with — while gas, oil, heat pump and solar sat exactly on
  their tolerance bounds.
* **Option B′ delivers it to machine precision.** Verified on the real 2025
  network per group, per bus and per snapshot: total absolute annual gap
  **0.00029 TWh** over six groups and two buses, all of it in the deliberately
  unpinned absorber.

---

## 3. What it costs — and how precisely that can be said

*(objective table; TABLES-PENDING)*

### 3.0 Read this before reading any objective difference

**The solver's own noise floor on these runs is ≈ 190 MEUR/a, ≈ 0.06 % of the
objective**, and it was measured rather than assumed.

`config.default.yaml` runs Gurobi with `Method 2` (barrier), **`Crossover 0`** and
**`BarConvTol 1e-5`**, so every reported objective is an interior point, not a
vertex. While fixing the absorber (`heat_softlink_option_b.md` §1.3), the same
2025 network was solved twice with the *only* difference being two extra
constraint blocks — a strict restriction, whose optimum cannot be lower:

| 2025, option B′ | reported objective |
|---|---:|
| absorber **unpinned** (fewer constraints) | 334.275 bn |
| absorber **pinned** (strictly more constraints) | **334.086 bn** |
| difference | **−189 MEUR (−0.057 %)** — the wrong sign |

A strict restriction cannot reduce the optimum, so at least one of those two
figures is ≥ 189 MEUR away from its true value. Nominal `BarConvTol 1e-5` would
suggest only 3.3 MEUR; the realised spread is ~57× that, which is what
crossover-free barrier on a 1.2 M-row degenerate LP looks like.

**Consequences for this document, and for `heat_soft_linking.md`:**

* an objective difference **below ~200 MEUR/a is not a result**. Option C's
  reported +64 MEUR/a against legacy in 2025 (`heat_soft_linking.md` §8.6) is in
  that band and should not be quoted;
* differences of several hundred MEUR are real in sign but not in magnitude;
* the **physical** comparisons — mix fidelity, fuel and CO₂, installed capacity —
  do not depend on the barrier's last digits and are what the recommendation
  rests on;
* if a precise cost of each mechanism is ever needed, re-run the two variants with
  `crossover: 1`. That is expensive on this model and was not done here.

### 3.1 The objectives

2025, same stock, same split, same everything except the mechanism:

| | objective | vs legacy |
|---|---:|---:|
| legacy (demand-only transfer) | 333.472 bn | — |
| option C | 333.536 bn | +64 MEUR/a — **below the noise floor** |
| **option B′** | **334.086 bn** | **+614 MEUR/a (+0.18 %)** — ~3× the noise floor |

So the defensible statement is: **option B′ costs a few hundred MEUR/a more than
either the legacy transfer or option C, and option C's own cost against the legacy
transfer cannot be resolved by these runs at all.** That difference is the price of
the hourly freedom option C keeps and option B′ removes; §5 argues about whether
that freedom is real.

---

## 4. Robustness and readability

| | option C | option B′ |
|---|---|---|
| concepts a reviewer must hold | `share`/`absolute` mode, `tolerance`, per-group `sense`, `zero_target`, `slack_groups`, `penalty` — **6** | `absorber`, `penalty`, `free_groups` — **3**, and only the first is normally touched |
| a technology TIMES has retired | needs `zero_target: forbid`, a *different sense* from every other group | its share is 0, so its profile is 0 — no special case |
| the ~4 % of the decentral load with no TIMES appliance behind it (cooking fuel, tertiary other-energy, re-bussed agriculture heat) | forced the `share` mode; `absolute` mode hands it all to the cheapest technology | pro-rata by construction, no mode to choose |
| over-determination of the LP | real risk — six equalities plus the heat balance is one equation too many, which is *why* the tolerance exists | impossible: the profiles sum to the load exactly, and the absorber is left to the bus balance rather than given a row |
| perverse incentive | `share` mode's denominator is the *realised* supply, so over-producing and venting technically relaxes the heat-pump cap (shown ~20× loss-making, and the realised vent is 0.000 TWh — but it is a thing that has to be argued) | none: the right-hand side is exogenous |
| feasibility on the heat bus | **argued**, and the original argument was wrong — the 2040 horizon proved it | **structural**: the profile is itself a feasible point, since every pinned technology is extendable with no dispatch ceiling and solar thermal is pinned to a multiple of its own availability |
| feasibility upstream (CO₂ cap, biomass limit) | one slack variable per group, priced | one scalar per group, priced — *same* mechanism, and needed for the same reason |
| what a reader can inspect | the log line, plus a shadow price if `store_model` is on | `heating_profiles/*.csv` — **the constraint itself**, plottable, diffable |
| LP size added | 6 rows | ≈ 14 600 rows at 6 h (≈ 87 600 at 1 h) — 1 % of a 1.3 M-row model |

**Neither option escapes the penalty.** That is worth stating plainly, because
removing the ad-hoc feel of option C's slack was part of the motivation for
trying B′. The Walloon CO₂ cap and the EU solid-biomass limit bind *upstream of
the heat bus* in 2040, and no formulation of a heat-mix transfer can create CO₂
headroom or biomass. What B′ changes is that the penalty is the *only* soft edge
left, instead of one of five.

---

## 5. The flexibility argument — the real decision

This is where the choice actually lies, and it cannot be settled by the objective
alone.

### 5.1 The flexibility that exists, measured

From the eight solved networks of the option-C comparison
(`docs/heat_softlink_option_b.md` §2):

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| decentral water tanks cycled, TWh_th | 0.008 | 0.011 | 0.017 | 0.017 |
| … as % of decentral heat supplied | 0.03 % | 0.04 % | 0.07 % | 0.08 % |
| **district-heating store cycled, TWh_th** | **0.204** | **0.484** | **1.257** | **2.733** |
| hourly mix deviation under option C | 34.6 % | 27.9 % | 26.2 % | 31.6 % |

Three conclusions:

1. **Decentral thermal storage does not exist in this model.** The optimised 2050
   water tanks are 0.131 MWh (rural) and 0.130 MWh (urban decentral) — 130 kWh for
   the whole of decentral Wallonia. Option B′ takes nothing here, and it leaves
   even that to the absorber (verified: the absorber is the only group that
   deviates from its profile, by ±25 MW within the horizon and 0.0003 TWh over it).
2. **The district-heating pit store is 27–157× larger and neither option touches
   it.** The urban-central bus keeps its full freedom in both. This was the
   explicit requirement, and it is met by both branches.
3. **What option B′ does remove is the hourly substitution between heating
   technologies**, and it is not small: under option C the mix swings by 26–35 %
   around its own annual average.

### 5.2 Is that swing a flexibility or an artefact?

**The case that it is real.** Bivalent heating exists. A dwelling with a heat pump
*and* a gas boiler genuinely does back off the heat pump on the coldest, most
expensive hours, and letting the model see that is precisely why an hourly model
is coupled to an annual one. Option C sees it; option B′ cannot.

**The case that it is an artefact.** On a single decentral heat bus, every
Walloon dwelling shares one gas boiler, one oil boiler, one heat pump and one
resistive heater, and the model may re-allocate heat between them at zero cost
with no regard for which dwelling owns which appliance. A real stock cannot do
that: a house with a gas boiler runs the gas boiler. The 26–35 % swing is
therefore mostly **perfect substitutability across a heterogeneous stock the
model does not resolve** — and the fact that it *grows* when option C's annual
constraint is imposed (from 15.6–27.3 % to 26.2–34.6 %) is a tell: the constraint
is being satisfied by concentrating each technology into its cheapest hours,
which is exactly the behaviour a dwelling stock cannot perform.

The same argument applies to the electricity side. Under option C the Walloon
heat-pump fleet can dodge scarcity hours; under B′ its draw is
`heat demand / COP(t)`, which is what an inflexible heat pump without storage
actually does. **B′'s electricity load shape is the more physically defensible
one** — but it is also *exogenous*, so the power system no longer co-optimises
with heating, and that is a genuine loss of coupling.

### 5.3 When each answer is right

| If the study is about… | prefer |
|---|---|
| **the Walloon fuel mix, emissions and the appliance transition** — i.e. what the TIMES coupling exists to transfer | **option B′**: it delivers TIMES's answer exactly and the result cannot be tuned by five knobs |
| **heating flexibility, hybrid heat pumps, thermal DSM, or the value of decentral storage** | **option C**: B′ assumes the answer away |
| **what it costs PyPSA to accept the TIMES mix** (the reconciliation dialogue) | **option C**: its per-group shadow prices are exactly that number, and B′ has no equivalent |
| **a result someone outside the project has to check** | **option B′**: the constraint is a CSV of MW per group per hour |

---

## 6. Recommendation

**Merge option B′, and keep option C's code in the tree behind its switch.**

Three reasons, in order:

1. **It transfers what it claims to transfer.** Option C delivers a 5 %-tolerance
   bound with two groups floating free of it; B′ delivers the TIMES mix. For a
   soft-link whose entire purpose is "TIMES decides what serves Walloon heat",
   that is the difference between doing the job and approximating it.
2. **Fewer places for the answer to come from a knob.** Option C's result depends
   on `mode`, `tolerance`, `zero_target` and `slack_groups`; B′'s depends on the
   TIMES shares and nothing else, unless the relaxation binds — in which case it
   says so, in TWh.
3. **The flexibility it gives up is mostly not real**, and the part that is real
   (district-heating storage) it does not touch.

Against that: it costs ~12× more in objective terms, and it makes Walloon heating
electricity exogenous. Both are consequences of the same decision, both are
visible in the tables above, and neither is hidden.

**The honest caveat.** If the next study is about heating flexibility rather than
the heating mix, this recommendation inverts. Keeping both mechanisms behind one
config block — which is what the `option-b` branch already does — costs nothing
and makes that switch a one-line change rather than a revert.

### If option B′ is merged, do these next

1. Delete `docs/heat_softlink_option_comparison.md`'s "pending" markers and keep
   this file as the decision record.
2. Set `sector.times_heat.energy_mix.enable: false` explicitly in every config
   rather than relying on the default, so the mutual-exclusion check never fires
   in a run someone else launches.
3. Export the `TimesHeatProfile-unmet` values to a post-solve CSV. They are bare
   linopy variables, so PyPSA does not write them to the netCDF and they currently
   have to be reconstructed from the realised dispatch
   (`check_heat_profile_fidelity.py` does this). The same gap exists for option
   C's slack.
4. Re-run at 1 h resolution before publishing. Nothing in either mechanism depends
   on the snapshot resolution, but the LP-size difference (6 vs ~87 600 rows) has
   only been measured at 6 h.
