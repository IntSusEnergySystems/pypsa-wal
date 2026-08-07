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
(option C defaults to off) so all three chains below run from one checkout and one
set of built resources; enabling both at once raises.

All numbers: `scen_demande_haute`, 6 h snapshots, full myopic chain 2025 → 2050,
every `extra_functionality` constraint including the national CO₂ budgets, Gurobi
barrier. **All twelve solves are `Optimal`.** Reproduce with:

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
annual mix is TIMES's exactly and the hourly mix is (almost) constant.

Everything below follows from that single difference.

---

## 2. Mix fidelity — what each option actually delivers

The headline measure is the **mean absolute error of the realised share against
the TIMES share**, in percentage points, over the six technology groups. It is
the only fidelity number the two mechanisms can be compared on: option C reports
its slack against its own *tolerance bound*, option B′ against its *profile*, and
those bounds are not the same thing — the realised share against TIMES is.

| mean \|share error\|, pp | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| legacy transfer | 15.88 | 20.54 | 17.51 | 16.91 |
| option C | 1.28 | 1.40 | 1.92 | 0.85 |
| **option B′** | **0.00** | **0.00** | **0.64** | **0.00** |

| worst group, pp | 2025 | 2030 | 2040 | 2050 |
|---|---|---|---|---|
| legacy | heat pump +47.6 | heat pump +55.4 | heat pump +49.8 | heat pump +47.2 |
| option C | gas −2.8 | resistive +3.6 | resistive +3.5 | heat pump +1.9 |
| **option B′** | **0.00** | **0.00** | biomass −1.9 | **0.00** |

Two structural points behind those numbers:

* **Option C cannot deliver the TIMES mix, by construction.** Its senses are `≥`
  on what TIMES keeps and `≤` on heat pumps, with a 5 % tolerance, so a binding
  group lands 5 % away and a non-binding one floats wherever the economics put it.
  The **resistive heater is the group it misses most** in 2030 and 2040 (+3.5 to
  +3.6 pp, i.e. **+81 % and +144 % in relative terms**): once gas and oil sit on
  their floors and heat pumps on their cap, resistive heat is the cheapest way to
  close the balance and nothing stops it.
* **Option B′ delivers it to solver tolerance — wherever Wallonia physically
  can.** Verified per group, per bus and per snapshot against the exported
  profiles (`check_heat_profile_fidelity.py`): total absolute annual gap over all
  four horizons, six groups and two buses is **0.923 TWh, and every last MWh of it
  is the single 2040 relaxation below.** 2025, 2030 and 2050 are exact.

### 2.1 The one thing B′ could not deliver, and how it says so

| 2040, TWh_th | pinned | realised | gap |
|---|---:|---:|---:|
| biomass boiler | 4.9396 | 4.4782 | **−0.4613** |
| heat pump (absorber) | 5.6042 | 6.0655 | **+0.4613** |
| gas / oil / resistive / solar | — | — | 0.00000 |

The relaxation is a single scalar, it lands only on the group that hit a physical
limit, and the absorber picks up exactly the same quantity — the two agree to five
decimals on each of the two buses *independently*. The pre-solve budget report
predicted it before Gurobi was called:

```
biomass boiler profile needs ~5.777 TWh of solid biomass at BEWAL solid biomass,
whose own supply caps at 8.250 TWh (imports excepted) and is shared with
solid biomass for industry, solid biomass for industry CC
WARNING The biomass-boiler profile alone claims 70 % of the solid biomass
BEWAL solid biomass can produce […] Expect the profile to relax
```

> **B′ relaxes *more* than option C in 2040 (0.461 vs 0.215 TWh_th), and that is
> not a defect.** Option C's `≥` floor is 0.95 × its TIMES share of the *realised*
> supply; B′ asks for the exact share of the *load*, which is a larger number.
> Both hit the same wall — the EU solid-biomass limit plus BEWAL's own 8.25 TWh
> supply with industry on the same bus — and both report the shortfall. B′ asks
> for more, so it reports more. **The finding is the same either way, and it is
> the most useful output of the whole exercise: the TIMES 2040 Walloon heating mix
> needs more solid biomass than PyPSA's Wallonia can obtain.** That belongs in
> `config/input_parameters_for_models.csv`, not in a constraint.

---

## 3. What it costs — and how precisely that can be said

### 3.0 Read this before reading any objective difference

**The solver's own noise floor on these runs is ≈ 190 MEUR/a, ≈ 0.06 % of the
objective**, and it was measured rather than assumed.

`config.default.yaml` runs Gurobi with `Method 2` (barrier), **`Crossover 0`** and
**`BarConvTol 1e-5`**, so every reported objective is an interior point, not a
vertex. While fixing the absorber ([`heat_softlink_option_b.md`](heat_softlink_option_b.md)
§1.3), the same 2025 network was solved twice with the *only* difference being two
extra constraint blocks — a strict restriction, whose optimum cannot be lower:

| 2025, option B′ | reported objective |
|---|---:|
| absorber **unpinned** (fewer constraints) | 334.275 bn |
| absorber **pinned** (strictly more constraints) | **334.086 bn** |
| difference | **−189 MEUR (−0.057 %)** — the wrong sign |

A strict restriction cannot reduce the optimum, so at least one of those figures
is ≥ 189 MEUR from its true value. Nominal `BarConvTol 1e-5` would suggest only
3.3 MEUR; the realised spread is ~57× that, which is what crossover-free barrier
on a 1.2 M-row degenerate LP looks like.

**Consequences, including for [`heat_soft_linking.md`](heat_soft_linking.md):**

* an objective difference **below ~200 MEUR/a is not a result**. Option C's
  +63.6 MEUR/a against legacy in 2025 (`heat_soft_linking.md` §8.6) is in that
  band and should not be quoted;
* differences of several hundred MEUR are real in sign but not in magnitude;
* the **physical** comparisons — mix fidelity, fuel, CO₂, capacity — do not depend
  on the barrier's last digits, and the recommendation rests on those;
* for a precise cost of each mechanism, re-run both with `crossover: 1`. That is
  expensive on this model and was not done here.

### 3.1 The objectives

| bn EUR/a | legacy | option C | option B′ | C − legacy | **B′ − C** |
|---|---:|---:|---:|---:|---:|
| 2025 | 333.472 | 333.536 | 334.086 | +64 MEUR *(noise)* | **+550 MEUR** |
| 2030 | 357.506 | 358.350 | 359.037 | +844 MEUR | **+687 MEUR** |
| 2040 | 289.954 | 290.617 | 291.257 | +663 MEUR | **+640 MEUR** |
| 2050 | 281.953 | 281.532 | 281.773 | −421 MEUR | **+241 MEUR** |

**B′ − C is the clean comparison** — same stock, same split, same everything but
the mechanism — and it is positive in every horizon and above the noise floor in
three of four: **imposing the TIMES mix hour by hour rather than year by year
costs a further 240–690 MEUR/a, i.e. 0.08–0.19 % of the system objective.**

(The `C − legacy` and `B′ − legacy` columns mix three switches at once, because
the legacy phase also reverts the base-year stock and the urban/rural split; that
is why 2050 comes out negative for both. `heat_soft_linking.md` §8.6 makes the
same point.)

### 3.2 Walloon CO₂ is identical in all three, to the tonne

21.982 / 15.456 / 8.587 / 1.717 Mt in every horizon and every variant. The
per-country cap binds in all of them, so **neither mix mechanism changes how much
Wallonia emits — only what emits it**, displacing emissions from elsewhere in the
Walloon system into heating. Worth stating plainly, because "impose the TIMES
fossil heating mix" sounds like it should raise emissions and does not.

---

## 4. Robustness and readability

| | option C | option B′ |
|---|---|---|
| concepts a reviewer must hold | `share`/`absolute` mode, `tolerance`, per-group `sense`, `zero_target`, `slack_groups`, `penalty` — **6** | `absorber`, `penalty`, `free_groups` — **3**, and only the first is normally touched |
| a technology TIMES has retired | needs `zero_target: forbid`, a *different sense* from every other group | its share is 0, so its profile is 0. In 2050 B′ ends with **0.0 MW of decentral oil boiler**, option C with 353 MW and 0.01 TWh of output |
| the ~4 % of the decentral load with no TIMES appliance behind it | forced the `share` mode; `absolute` mode hands it all to the cheapest technology | pro rata by construction, no mode to choose |
| over-determination of the LP | real risk — six equalities plus the heat balance is one equation too many, which is *why* the tolerance exists | impossible: the profiles sum to the load exactly, and the relaxation cancels when summed over the groups |
| perverse incentive | `share` mode's denominator is the *realised* supply, so over-producing and venting technically relaxes the heat-pump cap (~20× loss-making, and the realised vent is 0.000 TWh — but it has to be argued) | none: the right-hand side is exogenous |
| feasibility on the heat bus | **argued**, and the original argument was wrong — 2040 proved it | **structural**: the profile is itself a feasible point |
| feasibility upstream (CO₂, biomass) | one slack variable per group, priced | one scalar per group, priced — *same* mechanism, needed for the same reason |
| what a reader can inspect | the log line, plus a shadow price if `store_model` is on | `heating_profiles/*.csv` — **the constraint itself**, plottable, diffable, and checkable against the result with one script |
| LP size added | 6 rows | ≈ 17 500 rows at 6 h (≈ 105 000 at 1 h) — 1.4 % of a 1.2 M-row presolved model |
| **barrier time** (mean over the four horizons) | **158 s** | **154 s** | 

**Neither option escapes the penalty**, and that is worth saying plainly because
removing the ad-hoc feel of option C's slack was part of the motivation for
trying B′. The Walloon CO₂ cap and the EU solid-biomass limit bind *upstream of
the heat bus*, and no formulation of a heat-mix transfer can create CO₂ headroom
or biomass. What B′ changes is that the penalty is the *only* soft edge left
instead of one of five, and that it fires in one horizon out of four rather than
being the thing that keeps the mix inside a tolerance band.

**The extra rows cost nothing measurable.** 17 500 equality rows sounds like a
lot next to 6, but they also *remove* degrees of freedom, and the barrier times
came out within noise of each other (option C 159/181/149/143 s, option B′
131/142/166/147 s). Runtime is not an argument either way.

---

## 5. The flexibility argument — the real decision

This is where the choice actually lies, and the objective alone cannot settle it.

### 5.1 What the three variants actually do with the hours

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| **hourly mix deviation** (energy-weighted mean \|hourly share − annual share\|, aggregated) | | | | |
| legacy | 27.3 % | 23.1 % | 19.0 % | 15.6 % |
| option C | **34.6 %** | **27.9 %** | **26.2 %** | **31.6 %** |
| option B′ | **0.8 %** | **0.7 %** | **0.5 %** | **0.6 %** |
| **decentral water tanks cycled, TWh_th** | | | | |
| legacy | 0.0032 | 0.0050 | 0.0071 | 0.0091 |
| option C | 0.0076 | 0.0107 | 0.0173 | 0.0174 |
| option B′ | 0.0046 | 0.0057 | 0.0050 | 0.0073 |
| **district-heating store cycled, TWh_th** | | | | |
| legacy | 0.131 | 0.481 | 0.869 | 2.125 |
| option C | 0.204 | 0.484 | 1.257 | 2.733 |
| **option B′** | **0.408** | **0.837** | **1.145** | **2.829** |

Four readings:

1. **Option C does not merely keep the hourly freedom, it uses more of it than the
   free model does** (26–35 % against 16–27 %). An annual constraint is satisfied
   most cheaply by concentrating each technology into its own cheapest hours,
   which is the opposite of what a dwelling stock can do.
2. **B′ sets it to ~0.6 %, not 0.** The residue is solar thermal following the
   sun while the other groups share the residual — a documented and unavoidable
   consequence of solar being the one group with a dispatch ceiling.
3. **Decentral storage is a rounding error in all three variants** (0.003–0.017
   TWh_th, on stores the model sizes at **0.13 MWh** for the whole of decentral
   Wallonia). B′'s residue is a degenerate simultaneous charge/discharge at zero
   state of charge, which moves no energy. There was nothing here to lose.
4. **The district-heating store works *harder* under B′, not less** — 0.408 vs
   0.204 TWh_th in 2025, 0.837 vs 0.484 in 2030. Making decentral heating
   inflexible does not remove flexibility from the system; it moves the burden to
   where the flexibility physically is, which is the pit store neither option
   touches. That is the opposite of the feared outcome.

### 5.2 Is the hourly swing a flexibility or an artefact?

**The case that it is real.** Bivalent heating exists. A dwelling with a heat pump
*and* a gas boiler genuinely does back off the heat pump on the coldest, most
expensive hours, and letting the model see that is why an hourly model is coupled
to an annual one at all. Option C sees it; option B′ cannot.

**The case that it is an artefact.** On a single decentral heat bus, every Walloon
dwelling shares one gas boiler, one oil boiler, one heat pump and one resistive
heater, and the model may re-allocate heat between them at zero cost with no
regard for which dwelling owns which appliance. A real stock cannot do that: a
house with a gas boiler runs the gas boiler. The 26–35 % swing is therefore mostly
**perfect substitutability across a heterogeneous stock the model does not
resolve** — and the fact that it *grows* when option C's constraint is imposed is
the tell.

The same argument runs on the electricity side. Under option C the Walloon
heat-pump fleet can dodge scarcity hours; under B′ its draw is
`heat demand / COP(t)`, which is what an inflexible heat pump without storage
actually does. **B′'s electricity load shape is the more physically defensible
one** — but it is also *exogenous*, so heating no longer co-optimises with the
power system, and that is a real loss of coupling.

### 5.3 A structural consequence nobody asked for: capacity follows energy

| 2050, MW_th | legacy | option C | option B′ |
|---|---:|---:|---:|
| decentral air heat pump (both buses) | 2 450 | 739 | 2 156 |
| decentral gas boiler | 1 092 | 3 000 | 2 603 |
| decentral oil boiler | 2 422 | 670 | **0** |
| **total decentral heat capacity** | 7 900 | 7 795 | **7 542** |
| *(memo: peak decentral heat load)* | | | *7 542* |

**Option B′'s decentral fleet comes out at exactly the peak load, 7 542 MW_th** —
because every technology is sized for its own share of the peak and the shares sum
to one. Option C can instead run a small biomass boiler flat and cover the peak
with a big gas boiler, which is why its fleet is 250 MW larger and differently
composed. B′'s answer is the one that matches "each dwelling's appliance is sized
for that dwelling's peak"; option C's is the one a central planner with perfect
substitution would build. Neither is wrong, but they are different claims and only
B′'s is checkable against the load.

### 5.4 When each answer is right

| If the study is about… | prefer |
|---|---|
| **the Walloon fuel mix, emissions and the appliance transition** — what the TIMES coupling exists to transfer | **option B′**: it delivers TIMES's answer exactly and the result cannot be tuned by five knobs |
| **heating flexibility, hybrid heat pumps, thermal DSM, the value of decentral storage** | **option C**: B′ assumes the answer away |
| **what it costs PyPSA to accept the TIMES mix** (the reconciliation dialogue) | **option C**: its per-group shadow prices are exactly that number, and B′ has no equivalent |
| **a result someone outside the project has to check** | **option B′**: the constraint is a CSV of MW per group per hour, and one script compares it against the solved network |

---

## 6. Recommendation

**Merge option B′, and keep option C's code in the tree behind its switch.**

Four reasons, in order:

1. **It transfers what it claims to transfer.** 0.00 pp mean share error in three
   horizons out of four, against option C's 0.85–1.92 pp with individual groups
   off by up to 144 % in relative terms. For a soft-link whose entire purpose is
   "TIMES decides what serves Walloon heat", that is the difference between doing
   the job and approximating it.
2. **Fewer places for the answer to come from a knob.** Option C's result depends
   on `mode`, `tolerance`, `zero_target` and `slack_groups`; B′'s depends on the
   TIMES shares and nothing else — unless the relaxation binds, in which case it
   says so, in TWh, in the group concerned.
3. **The flexibility it gives up is mostly not real, and the part that is real it
   does not touch.** Decentral storage is 0.13 MWh; the district-heating pit store
   is untouched and in fact works *harder* under B′.
4. **It is checkable.** The exported profile *is* the constraint, and
   `check_heat_profile_fidelity.py` reconciles it against the solved network group
   by group, bus by bus, snapshot by snapshot. Option C's equivalent has to be
   reconstructed from tolerance bounds.

Against that: **it costs 240–690 MEUR/a more than option C (0.08–0.19 %)**, and it
makes Walloon heating electricity exogenous. Both are consequences of the same
decision, both are in the tables above, and neither is hidden.

**The honest caveat.** If the next study is about heating flexibility rather than
the heating mix, this recommendation inverts. Keeping both mechanisms behind one
config block — which is what the `option-b` branch already does — costs nothing
and makes that switch a one-line change rather than a revert.

### If option C is merged instead, do these next

1. **Backport the Snakemake fix.** `heat-softlink-option-c` does not have the
   `CUSTOM_EXTRA_FUNCTIONALITY_MODULES` input of `rules/common.smk`, so editing
   `times_heat_softlink.py` there leaves every solved network looking up to date
   and a comparison run silently re-archives the previous answer. It cost an hour
   here and it produces plausible numbers, which is the worst kind of failure.
2. **Fix the resistive-heater drift.** It is the group option C misses by the most
   in 2030 and 2040 (+3.5 pp, +81 % and +144 % relative), because once gas and oil
   sit on their `≥` floors and heat pumps on their `≤` cap, resistive heat is the
   cheapest way to close the balance and nothing stops it. A two-sided band on that
   group would cost nothing.
3. **Export the per-group shadow prices.** They are option C's single best output
   and they currently need `solving.options.store_model: true` plus a manual read.

### If option B′ is merged, do these next

1. Set `sector.times_heat.energy_mix.enable: false` explicitly in every config
   rather than relying on the default, so the mutual-exclusion check never fires
   in a run someone else launches.
2. Export the `TimesHeatProfile-unmet` values to a post-solve CSV. They are bare
   linopy variables, so PyPSA does not write them to the netCDF and they currently
   have to be reconstructed from the realised dispatch
   (`check_heat_profile_fidelity.py` does this). The same gap exists for option
   C's slack.
3. Re-run at 1 h resolution before publishing. Nothing in either mechanism depends
   on the snapshot resolution, but the LP-size difference (6 vs ~105 000 rows) has
   only been measured at 6 h, where it was free.
4. Take the 2040 biomass finding (§2.1) to the shared-assumptions table. It is a
   statement about the two models' resource envelopes, not about the soft-link.
