# The Walloon heating soft-link — option C, as implemented

**Status:** implementation log and decision record. **Started:** 2026-08-05.
**Companion document:** [`times-heating-softlink-options.md`](times-heating-softlink-options.md)
is the *analysis* — why options A and B were rejected and C recommended. This
file is the *implementation*: what was built, every choice that had to be made,
and the numbers behind each one.

**Reference scenario:** `scen_demande_haute_v01_260727_fix_nuc_2807.vd`,
`config/config.times-pypsa.yaml`, 6 h sector snapshots (a testing resolution;
the target is 1 h — nothing here depends on the resolution).

---

## 1. What option C does, in one paragraph

TIMES-WAL optimises the Walloon heating stock with dwelling-archetype, vintage
and retrofit detail PyPSA cannot match. PyPSA-Wal has an hourly resolution TIMES
cannot match. Before this change the soft-link transferred only the **annual
useful-heat totals**, and PyPSA re-optimised the appliance fleet from scratch —
supplying 55 % of Walloon heat with new heat pumps in 2025 where TIMES has 8 %.
Option C keeps every PyPSA heating component exactly as it is (extendable,
hourly, COP-driven, with storage) and adds one linear constraint per technology
group on the annual heat delivered to the two **decentral** heat buses. TIMES
decides *what* serves Walloon heat; PyPSA keeps deciding *when*, with how much
iron, and how it interacts with the power system.

District heating is deliberately out of scope — see §7.

---

## 2. Where the code lives

The split follows the repository boundary: extraction in the library, model
physics in the model.

| Piece | Where | New / changed |
|---|---|---|
| Group definition (TIMES categories ↔ PyPSA carriers, senses, every arbitrary mapping + its justification) | `TIMES_PyPSA/data/heat_softlink_groups.csv` | **new** |
| Target and capacity extraction | `TIMES_PyPSA/times_pypsa/heat_softlink.py` | **new** |
| Wiring into the exports | `TIMES_PyPSA/times_pypsa/pipeline.py` (`export_horizon`, `export_all_horizons`, `export_coupling_dir`) | changed |
| Library tests | `TIMES_PyPSA/tests/test_heat_softlink.py` (20 tests) | **new** |
| Constraints, splits, stock substitution | `scripts/walloon_scripts/times_heat_softlink.py` | **new** |
| Solver hook | `data/custom_extra_functionality.py` | changed (was an empty stub) |
| Demand split | `scripts/prepare_sector_network.py::harmonise_residential_urban_rural_split` | **new function**, one call added inside `write_wallon_heat_demands` |
| Base-year stock | `scripts/build_existing_heating_distribution.py::maybe_apply_times_base_year_stock` | **new function**, one call added |
| Snakemake I/O | `rules/build_sector.smk`, `rules/solve_myopic.smk`, `rules/common.smk` | changed |
| Model tests | `test/test_times_heat_softlink.py` (37 tests) | **new** |

**Every switch defaults to the previous behaviour.** Deleting the
`sector.times_heat` block from a config reproduces the pre-2026-08 results
exactly; the upstream PyPSA-Eur files touched are limited to one call site each
in `prepare_sector_network.py` and `build_existing_heating_distribution.py`, plus
additive rule inputs, to keep a future merge from upstream cheap.

### 2.1 New artefacts

```
resources/<run>/heating_targets_{year}.csv      # the Option-C right-hand sides
resources/<run>/heating_capacities_{year}.csv   # rewritten schema, see §5
```

`heating_targets_{year}.csv` carries, per constraint group: `scope`,
`constrained`, `pypsa_component`, `pypsa_carriers`, `sense`, `TWh`, `PJ`,
`share`, and the `times_categories` it was summed from. The provenance column is
not decoration — it is how a reader checks that the 23 TIMES child categories
were assigned once each.

### 2.2 Config

```yaml
sector:
  times_heat:
    node: BEWAL
    urban_rural_split: times_base_year   # times | times_base_year | pypsa
    base_year_capacities: true
    energy_mix:
      enable: true
      mode: share                        # share | absolute
      tolerance: 0.05
      slack_groups: []
      zero_target: forbid                # forbid | free
```

Enabled in `config/config.times-pypsa.yaml`; present but off in
`config/config.walloon.yaml`.

To run the coupled study with option C active:

```bash
snakemake --configfile config/config.times-pypsa.yaml --resources mem_mb=100000 --cores 12 -call
```

(Put a flag between the config file and any explicit targets — `--configfile` and
`--resources` both take `nargs="+"` and will swallow a target written straight
after them. Already recorded in `instructions.md`.)

To go back to the legacy transfer, set `energy_mix.enable: false`,
`base_year_capacities: false` and `urban_rural_split: times`, or delete the
`times_heat` block entirely — the code defaults are the legacy values.

---

## 3. The constraint

For each group *g* on the buses `BEWAL rural heat` + `BEWAL urban decentral heat`:

```
share mode (default)
    Σ_t w_t · heat_{g,t}   ⋛   (1 ∓ tol) · share_g · Σ_h Σ_t w_t · heat_{h,t}

absolute mode
    Σ_t w_t · heat_{g,t}   ⋛   (1 ∓ tol) · E_g^TIMES · nyears
```

`⋛` is `≥` for the technologies TIMES keeps and `≤` for heat pumps, so the
constraint reads as *"the transition is at most this fast"* rather than pinning
an equality. `tol` defaults to 5 %.

### 3.1 Why `share` is the default

Three reasons, in order of importance.

1. **The decentral heat load is not only TIMES appliance heat.**
   `write_wallon_heat_demands` adds the non-electric residential cooking fuel and
   the tertiary "other energy" fuel to the heat targets, and re-buses
   `BEWAL agriculture heat` onto the tertiary decentral bus, because PyPSA-Eur has
   no bus for any of them. That is **3.8 % (2025) to 4.6 % (2050)** of the load
   with no TIMES appliance behind it:

   | TWh | 2025 | 2030 | 2040 | 2050 |
   |---|---:|---:|---:|---:|
   | non-electric residential cooking | 0.670 | 0.992 | 0.870 | 0.384 |
   | tertiary other fuel | 0.232 | 0.240 | 0.250 | 0.231 |
   | agriculture heat (re-bussed) | 0.147 | 0.147 | 0.147 | 0.147 |
   | **not covered by a TIMES heat group** | **1.049** | **1.379** | **1.267** | **0.762** |
   | as % of the decentral load | 3.8 % | 5.2 % | 5.4 % | 4.4 % |

   In `absolute` mode that residual is handed to whichever technology is
   cheapest — the heat pump — which corrupts the mix the constraint exists to
   transfer. In `share` mode it is split pro rata across the groups.

2. **`share` mode cannot over-determine the LP.** `heat_g = share_g · Σ`
   satisfies every constraint strictly for any `tol > 0`, so a feasible point
   always exists as far as the mix constraints are concerned. With absolute
   equalities, the six group totals plus the heat balance are one equation too
   many and any rounding difference between `Σ E_g` and the transferred load makes
   the problem infeasible or forces the model to vent heat.

3. It is scale-free, so it is unaffected by the snapshot resolution and by
   `nyears`.

`absolute` mode is kept because it is the honest reading of *"TIMES says gas
delivers 14.7 TWh"*, and because the two modes disagreeing is itself a
diagnostic. It is the stricter and more fragile option.

> **The one perverse incentive in `share` mode, and why it does not bite.**
> Because the denominator is the *realised* supply, the model could in principle
> relax the heat-pump cap by inflating the total: over-produce with gas and vent
> the excess. Inflating the denominator by 1 MWh_th costs a full unit of gas heat
> (≈ 40-60 EUR/MWh_th at PyPSA's fuel and CO₂ prices) plus
> `marginal_cost_heat_vent`, and buys 0.079 MWh_th of extra heat-pump allowance
> worth a few EUR. The trade is ~20× loss-making, so it never pays; the vent
> volume is reported in the verification log (§8.3) as the check on that
> reasoning. `absolute` mode has no such term by construction.

### 3.2 Zero targets

A group whose TIMES target is zero is the one case where the sense has to flip.
`≥ 0` is vacuous, and TIMES is at its most decisive precisely there: it has **no
decentral oil boiler at all in 2050**, while PyPSA-Wal builds 0.73 TWh_th of one.
Using a technology TIMES has retired is a *slower* transition than TIMES, which is
what the `≥` senses exist to bound — so
`sector.times_heat.energy_mix.zero_target` defaults to `forbid`, adding
`Σ_t w_t · heat_{g,t} ≤ 0`. It is always feasible: no heat link is must-run.
`free` restores the loophole if a scenario needs it.

### 3.3 Feasibility — and why the heat bus alone does not guarantee it

Four sources of slack exist *on the heat bus*, all verified on the solved networks:

* **Capacity is extendable.** Nothing caps `p_nom` on any decentral heat
  technology. A group forced to deliver 55 % of annual heat can always be given
  the iron.
* **Heat vent exists.** `sector.heat_vent` is `true` for all three systems, so a
  `≥` constraint that over-supplies can dump heat at
  `marginal_cost_heat_vent = 0.02`. The 2025 solved network already vents
  12.9 MW (rural) and 11.1 MW (urban decentral) of capacity.
* **The 5 % tolerance** on every constraint.
* **`slack_groups`** removes any group from the constraint set entirely.

> **This was originally written as "why this cannot go infeasible". That was
> wrong, and the 2040 horizon proved it** — see §8.7. None of the four bullets
> above helps when the binding limit is *upstream of the heat bus*: the Walloon
> CO₂ cap and the EU solid-biomass limit both already bind in 2040 before any heat
> constraint is added, and no amount of extendable boiler capacity or heat venting
> creates CO₂ headroom or biomass. Feasibility is now guaranteed by a different
> mechanism, §3.3.1.

#### 3.3.1 The penalty — the actual feasibility guarantee

`sector.times_heat.energy_mix.penalty` (default **1000 EUR/MWh_th**) adds one
non-negative slack variable per constrained group and prices it in the objective:

```
≥ group:   Σ_t w_t · heat_{g,t}  +  slack_g   ≥   rhs_g
≤ group:   Σ_t w_t · heat_{g,t}  −  slack_g   ≤   rhs_g
objective +=  penalty · Σ_g slack_g
```

so **the mix constraints can never make the LP infeasible**. The penalty is
10–25× the marginal cost of decentral heat and ~10× the 2040 CO₂ shadow price
(94.8 EUR/t ≈ 21 EUR/MWh_th of gas heat), so relaxing is never cheaper than
complying: the model meets the TIMES mix wherever Wallonia physically can, and
where it cannot, `slack_g` **is the answer** — "TIMES asks for X TWh_th more gas
heat than Wallonia is allowed to emit for". A diagnostic, not a fudge.

Set `penalty: 0` for hard constraints (the original behaviour, and the right
setting if you *want* the run to stop when the two models disagree).

> **Why softness is not optional in practice.** An infeasible sector LP in this
> repo does not merely fail. `solve_network.py:2031` reacts to
> `condition == "infeasible_or_unbounded"` by calling
> `n.model.compute_infeasibilities()`, i.e. a Gurobi IIS over 1.28 M rows. On the
> 2040 network Gurobi detected infeasibility in **257 s** and then spent
> **47 310 s / 5.4 M simplex iterations** on the IIS without finishing — so a
> single infeasible horizon silently blocks a whole myopic chain at ~0 % CPU. That
> is the failure mode the penalty removes, and
> `run_heat_softlink_comparison.sh`'s watchdog (§8.7) is the second line of
> defence for infeasibilities from anywhere else.

The only technology with a binding upper bound on dispatch is **solar thermal**
(`p_max_pu` from the collector profile), and its target is 0.13 TWh in 2025
falling to 0.07 TWh in 2050 — 0.5 % and 0.4 % of decentral heat. A `≥` on it
sizes a collector field, which has no potential cap
(`p_nom_max = inf`) in this model.

> **The two models disagree 5× on solar thermal capacity, not on its energy.**
> TIMES gives every heating process the same 0.15 availability factor
> (1 314 equivalent full-load hours), so its 0.13 TWh comes from 99 MW_th of
> collectors. PyPSA's own BEWAL solar-thermal profile averages `p_max_pu = 0.030`
> — **264 FLH** after `solar_cf_correction: 0.788457` — so the same 0.13 TWh needs
> ≈ 490 MW_th of collectors, ≈ 26 MEUR/a at
> `decentral solar thermal capital_cost = 52 974 EUR/MW/a`. Transferring the
> *energy* and letting PyPSA size its own field is the right call precisely
> because of this: neither 1 314 h nor 264 h is credible for a Belgian collector
> (a real one delivers 400-700 h on its peak rating), and the disagreement is an
> availability-assumption artefact on both sides. If the 26 MEUR/a is judged not
> worth it, `slack_groups: [solar thermal]` drops the constraint; it is the
> cheapest group to give up because it is the smallest and the only one that can
> bind on `p_max_pu`.

### 3.4 The sign conventions, verified rather than assumed

This is where an implementation of option C most easily goes quietly wrong,
because the two orientations coexist on the same bus:

| Component | `bus0` | `bus1` | heat injected | coefficient on `Link-p` |
|---|---|---|---|---:|
| gas / oil / biomass boiler, resistive heater | fuel or electricity | **heat** | `efficiency · p0` | `+efficiency` |
| air / ground heat pump (**reversed**) | **heat** | electricity | `−p0` | `−1` |
| solar thermal collector (`Generator`) | — | heat | `p` | `+1` |

Read from `prepare_sector_network.py:3601-3617` and
`add_existing_baseyear.py:620-637`, then checked against the solved 2025 network:
reconstructing the per-group dispatch with these coefficients reproduces the
diagnosis §3 table to three decimals (gas 8.441, oil 1.948, heat pump 14.857,
biomass 1.136, resistive 0.789 TWh_th).

> **Correction to the diagnosis document.** §2 of
> `times-heating-softlink-options.md` states that a heat pump's `p_nom` is in
> **MW electric** and that converting TIMES capacities therefore needs a COP
> ("a ~60 % difference in the conversion factor alone"). That is **wrong for this
> code base.** The heat pump links carry `p_min_pu = −COP/max(COP, 0.001) = −1`
> exactly — verified over all snapshots and all four horizons — so `|p0| ≤ p_nom`
> with `p0` on the *heat* bus, and **`p_nom` is MW thermal**. The COP enters only
> through `efficiency = 1/COP` on the electricity side. This removes the single
> largest objection to reusing the TIMES capacities (§5) and means option C needs
> **no unit conversion at all**.

Two guards are asserted rather than trusted: a link touching a decentral heat bus
on *both* ports raises (the sign would be ambiguous), and a heat-injecting link
with a *time-dependent* efficiency raises (the annual coefficient would not be a
scalar). Neither exists today.

### 3.5 What is excluded from the constraint

On the decentral buses the component census is: the six supply technologies, the
water-tank charger/discharger pair, the heat `Load`, the heat vent, and a
0.011 TWh DAC link. The constraint selects components **by carrier**, so
chargers, dischargers, vents and DAC are excluded by construction — chargers in
particular would otherwise be picked up as "heat pumps" by a `bus0`-on-heat-bus
rule. `test_storage_and_out_of_scope_components_are_not_selected` pins this.

---

## 4. Taxonomy: TIMES building types ↔ PyPSA urban/rural

This is the arbitrary part, and it needed the most care.

### 4.1 What each side actually means

**TIMES-WAL has no urban/rural dimension.** The `Residential rural …` /
`Residential urban decentral …` labels in `mapping_processes.csv` are assigned
per process, on the **dwelling archetype**:

| TIMES archetype | Meaning | Label | Consistency |
|---|---|---|---|
| `2F` | 2-façade house (terraced) | urban decentral | 34/34 |
| `AP` | apartment | urban decentral | 32/32 |
| `3F` | 3-façade house (semi-detached) | rural | 26/35 |
| `4F` | 4-façade house (detached) | rural | 27/34 |

**PyPSA-Wal's split is a population statement.** `pop_layout` gives BEWAL an
`urban fraction` of **0.9207** (3 437 of 3 754 thousand inhabitants in built-up
cells), and `HeatSystem.heat_demand_weighting` splits the heat demand
`1 − urban_fraction` rural against `urban_fraction − district_fraction` urban
decentral.

Neither is wrong. They measure different things: *dwelling typology* against
*population density*. The equivalence is unavoidably arbitrary — the question is
how to keep the arbitrariness from affecting results.

### 4.2 The problem is the drift, not the level

The TIMES-implied rural share of residential decentral heat is not stable:

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| TIMES `BEWAL residential rural heat` (TWh) | 12.469 | 11.158 | 8.227 | 5.865 |
| TIMES `BEWAL residential urban decentral heat` (TWh) | 8.762 | 8.950 | 9.960 | 9.890 |
| **TIMES rural share** | **58.7 %** | **55.5 %** | **45.2 %** | **37.2 %** |
| PyPSA-native rural share, `(1−uf)/(1−df)` | 8.2 % | 8.6 % | 9.4 % | 11.0 % |

The TIMES total is a genuine model result. The *split* moving by 21 percentage
points is not: it is what happens when new and retrofitted appliances are
labelled `urban decentral` while surviving legacy ones stay `rural`. Under the
legacy transfer, **dwellings migrate between PyPSA heat buses over the horizons**.
That has three consequences, all artefacts:

1. the rural bus's load falls 53 % between 2025 and 2050 while its base-year
   stock was sized for 2025, so it strands capacity the model then pays to retire;
2. `heat_pump_sources` gives `rural` both `[air, ground]` and `urban decentral`
   only `[air]`, so the share of Walloon heat with access to the higher-COP
   ground-source heat pump changes for reasons that have nothing to do with
   geology or with the TIMES answer;
3. it makes the base-year capacity harmonisation (§5) inconsistent with the later
   horizons.

### 4.3 The three modes, and which one to use

`sector.times_heat.urban_rural_split`:

| Mode | Rural share applied | Keeps | Loses |
|---|---|---|---|
| `times` | the current horizon's TIMES labels | exact reproduction of the pre-2026-08 results | drifts (§4.2) |
| **`times_base_year`** *(recommended, and set in `config.times-pypsa.yaml`)* | the **first planning horizon's** TIMES labels, 58.7 %, for every horizon | the dwelling-typology information TIMES carries; consistency with the base-year stock | still an archetype-derived number, not a geographic one |
| `pypsa` | `(1−uf)/(1−df)`, 8.2 %→11.0 % | PyPSA's own geography; the TIMES labelling stops mattering entirely | discards the archetype signal, and 92 % of Walloon heat then sits on a bus with no ground-source heat pump |

**In every mode the total is untouched**, so nothing here changes the Walloon
heat balance or the CO₂ accounting — only which bus serves how much of it.

`times_base_year` is the recommendation because it is the option under which the
arbitrary choice has the least *differential* effect: the split is a constant, so
it cannot generate a spurious trend, and it agrees with the stock the base year
inherits. `pypsa` is provided as the sensitivity that removes the TIMES labelling
completely; running both is the honest way to bound the effect.

> **The constraint itself is immune to all of this.** Every group sums over
> `rural` + `urban decentral` (and over residential + services), which is exactly
> the aggregation in which the labelling artefact cancels — the recommendation of
> `times-heating-softlink-options.md` §6. The split only ever affects the demand
> and the stock.

### 4.4 Technology equivalence

The full table with justifications is
[`TIMES_PyPSA/data/heat_softlink_groups.csv`](../../TIMES_PyPSA/data/heat_softlink_groups.csv);
this is the summary, with every judgement call flagged.

| Constraint group | TIMES child categories | PyPSA carriers | Sense |
|---|---|---|---|
| heat pump | `{residential rural, residential urban decentral, services} heat pump` **+ `… geothermal`** | `{rural, urban decentral} {air, ground} heat pump` | `≤` |
| gas boiler | `… gas boiler` **+ `services CHP heat`** | `… gas boiler` | `≥` |
| oil boiler | `… oil boiler` **+ `… coal boiler`** | `… oil boiler` | `≥` |
| biomass boiler | `… biomass boiler` | `… biomass boiler` | `≥` |
| resistive heater | `… electric heater` | `… resistive heater` | `≥` |
| solar thermal | `… solar thermal` | `… solar thermal` (a `Generator`) | `≥` |
| ~~district heating~~ | `residential/services district heating` | — | **excluded**, §7 |

Four arbitrary assignments, all small and all documented in the CSV:

| Choice | Why | Magnitude |
|---|---|---|
| **coal → oil boiler** | PyPSA-Eur has no decentral coal boiler. `build_existing_heating_distribution.py:77-80` already folds the EU coal-boiler stock into the oil boiler, so the same convention is reused rather than invented. | 0.060 TWh (2025) → 0.004 (2040) → 0 (2050); ≤ 0.22 % of decentral heat |
| **TIMES geothermal building heat → heat-pump group** (and → ground-source heat pump on the capacity side) | `heat_pump_sources` lists no geothermal source for a decentral system, and `district_heating.direct_utilisation_heat_sources` applies to urban central only. The ground-source heat pump is the closest component. This gives the heat an electricity consumption TIMES does not charge it. | 0.002 TWh (2025) → 0.251 (2030-2050, almost all `services geothermal`); ≤ 1.5 % of decentral heat |
| **tertiary on-site CHP heat → gas boiler group** | `sector.chp.micro_chp` is `false`, so PyPSA has no decentral CHP at all. The heat is gas-fired, so the gas group is where it belongs for fuel and CO₂ accounting. Its electricity output is not transferred (PyPSA optimises Walloon generation itself). | 0.227 TWh (2025), 0.185 (2040), 0 otherwise; ≤ 0.85 % of decentral heat |
| **tertiary ground-source heat pump stock → air-source** | `write_wallon_heat_demands` deletes `BEWAL services rural`, and `urban decentral` admits only `air`, so a services ground heat pump has no bus. Re-labelling the source keeps the capacity; dropping it would lose stock silently. | 7.0 MW_th of the 2025 stock, 0.03 % |

The **closure test** is what makes this reviewable:
`Σ (constrained group targets) == Σ (the three parent categories
write_wallon_heat_demands rescales the loads to)`, exactly, in all eight horizons
2021-2050. Every TIMES child category is claimed by exactly one group; the loader
raises if one is claimed twice or by none.

---

## 5. Base-year capacities

### 5.1 The two defects that had to be fixed first

`extract_heating_capacities` (`pipeline.py`) had two blocking bugs. The file it
wrote was read by nothing, so neither had ever caused harm — but recommendation 2
of the diagnosis depends on it.

**(a) `VAR_Cap + VAR_Ncap` double-counted.** `VAR_Ncap` (capacity built in the
period) is already inside `VAR_Cap` (total installed). Verified structurally on
the reference `.vd`: `VAR_Ncap ≤ VAR_Cap` for **every** (process, year) pair —
zero exceptions — and `VAR_Cap` advances by exactly `VAR_Ncap` less retirements,
e.g. `RH2FGMXN1`: 0.161 (2022) → 0.493 = 0.161 + 0.332 (2025). The inflation:

| 2050, MW_th | `VAR_Cap` | `VAR_Ncap` | old export | error |
|---|---:|---:|---:|---:|
| Residential rural gas heater | 5 109 | 3 308 | 8 417 | **+65 %** |
| Residential urban decentral gas heater | 4 009 | 1 916 | 5 925 | **+48 %** |
| Residential urban decentral heat pump | 2 831 | 1 011 | 3 841 | **+36 %** |

Now `VAR_Cap` only. `test_capacity_excludes_ncap` fails if anyone adds it back.

**(b) The index regex admitted the wrong processes and dropped the right ones.**
`boiler|heat pump|stove|thermal|heater` matched `Geothermal (IND)` (an
*industrial* process, 8.6 MW) and `Thermal Public - Retrofitting CCGT CCS` (a
*power plant*, 1 740 MW), while missing `District heating` (the substations,
224 MW) and `Commercial Heat Exchanger` (40 MW) because neither name contains any
of the five words. Selection is now by explicit `Aggregation Level 2` label list,
taken from the same group file that drives the energy targets, so the two axes
cannot drift apart.

### 5.2 The new schema

`heating_capacities_{year}.csv` is now tidy and long, one row per TIMES label:

```
year, group, times_label, sector, times_heat_system, pypsa_stock_technology, MW_th, transferable
```

`transferable` is `False` for rows PyPSA has no `existing_heating_distribution`
column for; they are reported, not dropped in silence.

### 5.3 The substitution — and why it needs no conversion

`existing_heating_distribution_*.csv` is in **MW thermal output**:
`add_existing_baseyear` divides by the appliance efficiency itself for boilers and
resistive heaters (`p_nom = capacity / efficiency`), and passes the value straight
through for heat pumps (`p_nom = capacity`, which is thermal because
`p_min_pu = −1`; §3.4). TIMES `VAR_Cap` for every heating process group is in GW
thermal on the **output** side (`VAR_Act = VAR_FOut`, verified on `RH4FELCHPN4`
and `RH2FGMXN1`). So the transfer is `GW → MW` and nothing else.

### 5.4 The 2025 discrepancies

BEWAL, MW thermal output. "PyPSA" is the EU 2012 dataset scaled by population
(`build_existing_heating_distribution.py`); "TIMES" is `VAR_Cap` 2025.

| Technology | PyPSA (EU 2012) | TIMES 2025 | change |
|---|---:|---:|---:|
| gas boiler | 9 139 | 12 323 | **+35 %** |
| oil boiler (incl. coal) | 6 670 | 5 817 | −13 % |
| biomass boiler | 1 384 | 1 833 | +32 % |
| resistive heater | 1 011 | 1 264 | +25 % |
| air heat pump | 54 | 936 | **+17×** |
| ground heat pump | 20 | 1.2 | −94 % |
| **total transferable** | **18 279** | **22 174** | **+21 %** |
| *(not transferable: solar thermal)* | *—* | *99* | |
| *(not transferable: DH substations)* | *—* | *265* | |

(Confirmed from the run log:
`TIMES base-year heat stock replaces the BEWAL row of existing_heating_distribution:
18279 MW_th → 22174 MW_th`.)

**The heat pump row is the point of the exercise.** With 74 MW_th of inherited
heat pumps, PyPSA greenfields ~2 515 MW in the base year and runs them at
5 000-7 600 equivalent full-load hours — as baseload — for 55 % of Walloon heat,
while leaving the 9.1 GW of gas boilers it did not have to pay for at ~1 000 h.
Starting from the 929 MW_th TIMES actually has does not by itself fix the
dispatch divergence (that is what §3 is for), but it removes a base-year
free-capacity artefact that no amount of constraint work can reach.

Two rows are *not* transferable and are documented rather than forced:

* **solar thermal, 99 MW_th.** PyPSA's solar thermal is a `Generator` with no
  vintage structure and no row in `existing_heating_distribution`. The energy
  constraint (§3) covers it instead.
* **district-heating substations, 265 MW_th** (`District heating` 224 +
  `Commercial Heat Exchanger` 40). PyPSA serves the DH load directly from the
  urban-central bus; there is no substation component. Out of scope with the rest
  of district heating (§7).

### 5.5 Feasibility of the substitution

The concern is that a stock statement could make the base year infeasible or
strand capital. It cannot, and the margin is comfortable. All figures read off the
built `base_s_adm___2025_brownfield.nc`:

| | value |
|---|---:|
| BEWAL decentral heat load, 2025 (incl. cooking, tertiary other fuel, agriculture heat) | 27.79 TWh |
| peak / mean of the combined decentral profile | 3.25 |
| **peak decentral heat demand** | **10.31 GW_th** |
| TIMES 2025 transferable stock, nominal | 22.17 GW_th |
| **… as actually dispatchable thermal output** (see below) | **≈ 17.65 GW_th** |
| head-room | **1.7×** |

> **An upstream quirk worth knowing about.** `add_existing_baseyear` sizes an
> inherited boiler as `p_nom = capacity / costs.efficiency` (a *modern* appliance:
> 0.975 gas, 0.900 oil) but gives the link the *stock-average* efficiency from
> `heating_efficiencies_*.csv` (0.742 gas, 0.654 oil). The fleet therefore delivers
> only `0.742/0.975 = 76 %` (gas) and `0.654/0.900 = 73 %` (oil) of its nominal
> thermal rating. Resistive heaters and biomass boilers use the same efficiency on
> both sides and are self-consistent. This is PyPSA-Eur behaviour, unchanged by
> this work, and it applies identically to the EU-2012 row the substitution
> replaces — so the comparison above is apples to apples. It does mean a
> "12.3 GW_th gas boiler stock" is a 9.4 GW_th gas boiler stock in the LP.

There is no `p_nom_min` anywhere — the substitution changes what PyPSA *inherits*,
never what it *must* build — and every technology remains extendable, so a
shortfall on any single bus is buildable. The 2025 solve is reported in §8.3.

---

## 6. Fixes made along the way

| # | What | Where | Why it mattered |
|---|---|---|---|
| 1 | `VAR_Cap + VAR_Ncap` double count | `times_pypsa/heat_softlink.py` (was `pipeline.py:956`) | §5.1(a); 36-65 % inflation |
| 2 | Capacity regex admitted an industrial process and a power plant, dropped district heating | idem (was `pipeline.py:969-972`) | §5.1(b) |
| 3 | `build_toy_fixtures.py` looked for the mapping CSVs in `times_pypsa/mappings/`, which does not exist | `TIMES_PyPSA/scripts/build_toy_fixtures.py` | the fixture builder crashed halfway, so `toy_qa.*` could not be regenerated at all |
| 4 | Toy fixtures carried no `VAR_Cap`, so the capacity export had no fast test | idem, `KEEP_VARS` | `VAR_Ncap` deliberately still excluded — a fixture that carries it invites the bug back |
| 5 | `heat_softlink_groups.csv` was not declared as a Snakemake input | `rules/build_sector.smk::times_mapping_files` | same class of bug as the 2026 heat leak: editing the group definition would have left stale `heating_targets_*.csv` on disk |

---

## 7. District heating stays out

Unchanged from the diagnosis §6 *Scope*, restated because it is a design decision
someone will want to revisit:

1. **DAC dominates the urban-central bus.** 2050: injections 8.980 TWh, DH load
   2.693 TWh, DAC withdrawal 4.138 TWh. A share constraint there is either
   vacuous or is secretly a cap on DAC.
2. **CHP heat is welded to CHP electricity.** `add_chp_constraints` is dead code,
   so `heat = 3.055 × electricity` for the biomass CHP with no slack.
   Constraining CHP heat *is* constraining Walloon power generation — the sector
   where PyPSA, not TIMES, is the authority.
3. **The pit store re-injects.** 23 % of 2050 "injections" are re-injections.
4. **73 % of the TIMES 2050 DH supply cannot be expressed** — geothermal (52 %)
   and industrial waste heat (21 %) have no PyPSA component.

The TIMES district-heating rows are still exported (`sense: none`,
`constrained: false`) so the accounting is complete and the numbers are visible;
no constraint is built from them. District-heat **demand** continues to be
transferred exactly as before.

---

## 8. Verification log

### 8.1 Library (fast)

```bash
cd ../TIMES_PyPSA && python -m pytest tests/ -q
```

`151 passed` (131 pre-existing + 20 new). The new suite asserts:

* **closure** — `Σ` constrained group targets `== Σ` the three parent categories,
  exactly, for every horizon in the fixture;
* shares sum to 1; `PJ` and `TWh` agree;
* `VAR_Ncap` is not in the capacity export;
* `Geothermal (IND)` and `Thermal Public - Retrofitting CCGT CCS` are not;
* `District heating` **is**, flagged non-transferable;
* the group definition rejects a duplicated category, an unknown sense, and a
  `pypsa_stock_technology` that is not an `existing_heating_distribution` column;
* a group that splits over several rows documents each arbitrary assignment.

Also run against the full `.vd` (`TIMES_PYPSA_FULL_DATA=1`): `20 passed`.

### 8.2 Model (fast)

```bash
python -m pytest test/test_times_heat_softlink.py -q
```

`37 passed`. The load-bearing ones:

* **the sign conventions** — boiler coefficient is `+efficiency`, heat pump is
  `−1` *whatever the COP*, generator is `+1`; water-tank chargers and
  urban-central components are never selected; a two-port link and a
  time-dependent efficiency both raise;
* **end to end**, both modes: a toy network whose unconstrained optimum is
  heat-pump dominated (as the real 2025 network is) is solved with the
  constraints, and the realised mix respects every target within the tolerance
  while the objective rises — i.e. the constraint binds and costs something;
* the stock helpers: total conserved, nothing on `services rural`, ground heat
  pumps folded to rural, air to urban decentral, unknown node/technology raise;
* every split mode preserves the total.

### 8.3 Full 2025 solve — the authoritative check

`snakemake --configfile config/config.times-pypsa.yaml … base_s_adm___2025.nc`,
full 6 h resolution, all six countries, **every** `extra_functionality` constraint
including the national CO₂ budget, Gurobi barrier.

**Build stage.** Ran clean end to end. The new log lines:

```
build_existing_heating_distribution:
  TIMES base-year heat stock: 363.5 MW_th not transferable …
  7.0 MW_th of tertiary ground-source heat pump re-labelled as air-source …
  TIMES base-year heat stock replaces the BEWAL row of
    existing_heating_distribution: 18279 MW_th → 22174 MW_th.
prepare_sector_network:
  Residential decentral heat split (times_base_year): … total 21.2313 TWh unchanged.
  Walloon decentral heat also carries 0.670 TWh of non-electric cooking fuel
    and 0.232 TWh of tertiary other-energy fuel.
```

**Solve stage.** Two full-resolution solves, identical in every respect except
`energy_mix.enable`, so the comparison is clean:

| Group, decentral heat | TIMES share | **free** `enable: false` | **constrained** | sense | bound |
|---|---:|---:|---:|---|---:|
| heat pump | 7.93 % | **51.38 %** | **8.32 %** | `≤` | 8.324 % |
| gas boiler | 54.94 % | 40.35 % | **52.19 %** | `≥` | 52.19 % |
| oil boiler | 21.59 % | 0.03 % | **20.51 %** | `≥` | 20.51 % |
| biomass boiler | 9.00 % | 5.91 % | 9.75 % | `≥` | 8.551 % |
| resistive heater | 6.06 % | 2.33 % | 8.77 % | `≥` | 5.762 % |
| solar thermal | 0.48 % | 0.00 % | **0.46 %** | `≥` | 0.460 % |
| **objective** | | **333.1606 bn** | **333.6053 bn** | | |

Both `Optimal`. Every constraint holds. Four of the six sit exactly on their bound
— which is what a binding transfer looks like — and the heat pump lands at 8.32 %
against its 8.324 % cap, i.e. the cap is precisely what stops PyPSA electrifying.
Biomass and resistive end up *above* their floors because, once the heat pump is
capped and gas and oil are at their minima, they are the cheapest remaining way to
close the balance; the `≥` senses permit that by design ("the transition is at most
this fast", not "exactly this fast").

**What it costs: +444.7 MEUR/a, +0.133 %** of a six-country objective. That is the
price of accepting the TIMES Walloon heating mix — and it is a number option A
cannot produce: option A's ≈ +600 MEUR/a buys *idle* boilers and **no** change in
the mix at all.

Total supplied 27.7916 TWh_th = the decentral load to five decimals, and the
**decentral heat vent is 0.000 TWh** — the mix is delivered without dumping any
heat, so none of the slack of §3.3 was needed and the perverse-incentive worry of
§3.1 does not materialise.

Capacity built stays modest, because the substituted base-year stock already covers
most of it (MW_th, `p_nom_opt`; inherited from §8.4 in brackets): rural gas 3 644
(3 400), rural oil 3 532 (2 734), urban decentral gas 6 284 (5 977), urban
decentral oil 2 348 (1 491) — ≈ 2.2 GW_th of new boilers in total, against
option A's forced 8.3 GW_th of *idle* iron.

### 8.4 What the base-year stock substitution does on its own

The 2025 network was rebuilt with `base_year_capacities: false` /
`urban_rural_split: times` (full legacy) to isolate the effect. The demand is
identical in both (27.7915 TWh decentral, 10 307 MW peak, 12.8622 TWh on rural), so
the only difference is the inherited stock. **Dispatchable** thermal capacity by
carrier, MW_th:

| Carrier | legacy (EU 2012) | TIMES 2025 | change |
|---|---:|---:|---:|
| rural gas boiler | 390 | 3 400 | ×8.7 |
| rural oil boiler | 272 | 2 734 | ×10.1 |
| rural biomass boiler | 78 | 1 211 | ×15.6 |
| rural resistive heater | 57 | 732 | ×12.9 |
| rural ground heat pump | 13.9 | 1.2 | −92 % |
| urban decentral gas boiler | 6 403 | 5 977 | −7 % |
| urban decentral oil boiler | 4 460 | 1 490 | −67 % |
| urban decentral biomass boiler | 1 403 | 641 | −54 % |
| urban decentral resistive heater | 931 | 532 | −43 % |
| urban decentral air heat pump | 55 | 936 | **×17** |
| **total** | **14 060** | **17 655** | **+26 %** |

Two separate effects, and the second one was not anticipated by the diagnosis:

1. **The heat-pump stock.** 55 → 936 MW_th. This is the intended fix (§5.4).
2. **The rural bus was chronically under-equipped, and the harmonisation fixes an
   inconsistency rather than just a level.** Under the legacy combination the
   *demand* split follows the TIMES archetype labels (58.7 % of residential heat on
   `rural`, so a **4 802 MW** rural peak) while the *stock* split follows PyPSA's
   population fraction (7.9 % rural, so **809 MW_th** of rural stock — 17 % of the
   rural peak). PyPSA therefore had to greenfield ≈ 4 GW of heat capacity on the
   rural bus in the base year, and it naturally chose heat pumps. That is a pure
   book-keeping artefact of two inconsistent urban/rural conventions. With the TIMES
   stock the rural bus inherits 8 078 MW_th, comfortably above its peak.

> **What the substitution does *not* do: fix the mix.** The `free` column of §8.3 is
> the full-resolution 2025 solve *with* the TIMES base-year stock and *without* the
> energy-mix constraint, and it still puts **51.4 %** of Walloon decentral heat on
> heat pumps (against 54.7 % on the legacy stock — a 3-point move, with gas up from
> 31 % to 40 %). So the stock harmonisation removes a real artefact and improves the
> starting point, but the divergence of §3 of the diagnosis is a
> **dispatch-and-investment** divergence, exactly as that document concluded: at
> PyPSA's fuel and CO₂ prices a heat pump beats a gas boiler on marginal cost even
> after paying its annuity, whatever iron it inherits. Only the energy-mix
> constraint closes it. An earlier reading of the reduced harness suggested the
> stock alone did most of the work; the full solve does not support that, and the
> reduced number (21 %) was an artefact of the coarse snapshot sampling.

### 8.5 2050 — the horizon where the constraints bite hardest

2050 is the stress case: TIMES has **no** decentral oil boiler (so `zero_target:
forbid` applies), heat pumps are capped at 39.8 %, and biomass has to reach 15.5 %.

Because the myopic chain has to be re-solved 2025 → 2030 → 2040 → 2050 before a
full 2050 network exists, this horizon was checked with a **reduced harness**: the
existing `base_s_adm___2050_brownfield.nc`, every bus and vintage intact, on a
**113-snapshot subsample** (every 13th 6 h snapshot, weightings rescaled to
8760 h), with the heat-mix constraints applied directly.

> **A trap worth recording.** The first attempt used a stride of 12, and 12 is a
> multiple of the 4 snapshots per day, so it sampled **midnight only** — solar
> thermal `p_max_pu` was 0 at every retained snapshot and the `≥ 0.123 TWh` solar
> constraint was trivially infeasible. The LP said `infeasible` and it looked like a
> modelling failure. Any snapshot subsample of a sub-daily series must use a stride
> coprime with the snapshots per day (13 here).

| Group | TIMES share | free | constrained | sense | bound |
|---|---:|---:|---:|---|---:|
| heat pump | 37.94 % | 11.85 % | 4.39 % | `≤` | 39.84 % |
| gas boiler | 34.38 % | 61.79 % | 69.32 % | `≥` | 32.66 % |
| oil boiler | 0.00 % | 12.71 % | **0.00 %** | `≤ 0` | 0 |
| biomass boiler | 16.28 % | 11.48 % | 15.46 % | `≥` | 15.46 % |
| resistive heater | 11.04 % | 2.17 % | 10.49 % | `≥` | 10.49 % |
| solar thermal | 0.36 % | 0.00 % | 0.34 % | `≥` | 0.34 % |

**Feasible and optimal.** `zero_target: forbid` works: the 2.45 TWh of oil boiler
the free run builds goes to exactly zero. Biomass, resistive and solar sit on their
floors. Decentral heat vent rises from 0.000 to 0.150 TWh (0.8 % of the load) —
the slack mechanism of §3.3 is used, and used sparingly. Cost of the mix:
**+341.7 MEUR/a (+0.176 %)**.

> **Read this table with two caveats.**
> 1. **The standalone harness omits every other `extra_functionality` constraint** —
>    notably the **national CO₂ budget** (`co2_budget_national: true` →
>    `add_co2limit_country`), the self-sufficiency and import limits, and the TES
>    ratio constraints. That is why the "free" column here is gas-dominated where
>    the published full 2050 run is 86 % heat pump: without a CO₂ cap, gas is simply
>    cheaper, which also explains why the constrained heat pump sits at 4.4 % rather
>    than near its 39.8 % cap. The *feasibility* conclusion for the mix constraints
>    in isolation stands; whether the `≥` gas floor can coexist with the Walloon 2050
>    CO₂ budget is **the one thing this harness cannot answer**. (It does coexist in
>    2025 — §8.3 has the full budget in place.)
> 2. The 2050 brownfield network predates the base-year substitution (it descends
>    from the previously solved 2040 network), so it carries the legacy stock.
>
> Settling both needs a full myopic chain 2025 → 2030 → 2040 → 2050. **That is the
> remaining verification step**, and the risk it addresses is concrete: if PyPSA's
> Walloon CO₂ budget is tighter than the one TIMES solved against, the TIMES gas
> floor and the PyPSA CO₂ cap are jointly infeasible — which would be a genuine
> finding about the two models' alignment, not a bug in this code. The escape
> hatches are `slack_groups: [gas boiler]` and raising `tolerance`.

---

### 8.6 Full myopic chain, before vs after

Both chains were re-solved end to end — all four horizons, full 6 h resolution,
every constraint, Gurobi — by
[`scripts/walloon_scripts/run_heat_softlink_comparison.sh`](../scripts/walloon_scripts/run_heat_softlink_comparison.sh),
which archives each tree under `results/_heat_softlink_comparison/{before,after}/`
and is idempotent per phase. `before` is the legacy transfer (the whole
`times_heat` block back to its pre-2026-08 values); `after` is option C as
configured. The tables below come from
[`scripts/walloon_scripts/compare_heat_softlink.py`](../scripts/walloon_scripts/compare_heat_softlink.py):

```bash
bash scripts/walloon_scripts/run_heat_softlink_comparison.sh scen_demande_haute
python scripts/walloon_scripts/compare_heat_softlink.py scen_demande_haute
```

Both chains completed: `before` in ~12 min, `after` in ~1 h 50 (2040 and 2050 are
much harder LPs once the mix is imposed). **All eight solves are `Optimal`.**

> **Read the `before → after` delta as the effect of all three switches, not of the
> constraint alone.** `before` reverts `urban_rural_split`, `base_year_capacities`
> *and* `energy_mix` together, so the objective difference mixes a cost increase
> (the mix constraint) with a cost *decrease* (more inherited base-year stock means
> less to build) — which is why 2050 comes out negative. The clean isolation of the
> constraint cost is §8.3: same stock and split, `energy_mix` toggled alone,
> **+444.7 MEUR/a in 2025**.

#### Decentral heat mix, share of supply

| 2025 | TIMES TWh | TIMES % | before TWh | before % | after TWh | after % | unmet TWh |
|---|---|---|---|---|---|---|---|
| heat pump | 2.12 | 7.93 | 15.44 | 55.57 | 2.31 | 8.32 | 0.00 |
| gas boiler | 14.69 | 54.94 | 8.45 | 30.41 | 14.50 | 52.19 | 0.00 |
| oil boiler | 5.77 | 21.59 | 1.96 | 7.05 | 5.70 | 20.51 | 0.00 |
| biomass boiler | 2.41 | 9.00 | 1.13 | 4.08 | 2.71 | 9.75 | 0.00 |
| resistive heater | 1.62 | 6.06 | 0.80 | 2.89 | 2.44 | 8.77 | 0.00 |
| solar thermal | 0.13 | 0.48 | 0.00 | 0.00 | 0.13 | 0.46 | 0.00 |

| 2030 | TIMES TWh | TIMES % | before TWh | before % | after TWh | after % | unmet TWh |
|---|---|---|---|---|---|---|---|
| heat pump | 2.90 | 11.45 | 17.88 | 66.89 | 3.21 | 12.02 | 0.00 |
| gas boiler | 15.22 | 60.02 | 2.49 | 9.33 | 15.24 | 57.02 | 0.00 |
| oil boiler | 2.74 | 10.79 | 0.47 | 1.76 | 2.74 | 10.25 | 0.00 |
| biomass boiler | 3.27 | 12.90 | 5.10 | 19.08 | 3.28 | 12.25 | 0.00 |
| resistive heater | 1.12 | 4.41 | 0.79 | 2.94 | 2.13 | 7.98 | 0.00 |
| solar thermal | 0.11 | 0.44 | 0.00 | 0.00 | 0.13 | 0.48 | 0.00 |

| 2040 | TIMES TWh | TIMES % | before TWh | before % | after TWh | after % | unmet TWh |
|---|---|---|---|---|---|---|---|
| heat pump | 5.31 | 23.18 | 17.64 | 72.93 | 5.30 | 21.93 | 0.00 |
| gas boiler | 11.92 | 52.05 | 3.57 | 14.76 | 11.95 | 49.45 | 0.00 |
| oil boiler | 0.36 | 1.58 | 1.05 | 4.35 | 0.89 | 3.68 | 0.00 |
| biomass boiler | 4.68 | 20.43 | 1.68 | 6.93 | 4.48 | 18.52 | 0.22 |
| resistive heater | 0.56 | 2.42 | 0.25 | 1.02 | 1.43 | 5.90 | 0.00 |
| solar thermal | 0.07 | 0.33 | 0.00 | 0.00 | 0.13 | 0.52 | 0.00 |

> **2040: 0.215 TWh_th of the TIMES mix could not be delivered** — the constraint relaxed at `energy_mix.penalty` rather than making the LP infeasible. See §3.3.1 and §8.7.


| 2050 | TIMES TWh | TIMES % | before TWh | before % | after TWh | after % | unmet TWh |
|---|---|---|---|---|---|---|---|
| heat pump | 7.57 | 37.94 | 17.64 | 85.12 | 8.26 | 39.84 | 0.00 |
| gas boiler | 6.86 | 34.38 | 1.81 | 8.75 | 6.77 | 32.66 | 0.00 |
| oil boiler | 0.00 | 0.00 | 0.74 | 3.56 | 0.01 | 0.03 | 0.00 |
| biomass boiler | 3.25 | 16.28 | 0.21 | 1.03 | 3.21 | 15.46 | 0.00 |
| resistive heater | 2.20 | 11.04 | 0.32 | 1.54 | 2.42 | 11.66 | 0.00 |
| solar thermal | 0.07 | 0.36 | 0.00 | 0.00 | 0.07 | 0.34 | 0.00 |

#### Installed decentral heat capacity, MW_th

| 2025 | before | after | change % |
|---|---|---|---|
| rural air heat pump | 1405.2 | 0.0 | -100.0 |
| rural biomass boiler | 81.8 | 1211.1 | 1380.9 |
| rural gas boiler | 538.6 | 3643.0 | 576.4 |
| rural ground heat pump | 277.7 | 1.2 | -99.6 |
| rural oil boiler | 2143.0 | 3532.4 | 64.8 |
| rural resistive heater | 355.6 | 732.2 | 105.9 |
| urban decentral air heat pump | 972.7 | 936.4 | -3.7 |
| urban decentral biomass boiler | 1402.9 | 641.4 | -54.3 |
| urban decentral gas boiler | 6403.0 | 6283.9 | -1.9 |
| urban decentral oil boiler | 4459.8 | 2347.8 | -47.4 |
| urban decentral resistive heater | 930.7 | 531.7 | -42.9 |
| TOTAL | 18970.8 | 19861.1 | 4.7 |

| 2030 | before | after | change % |
|---|---|---|---|
| rural air heat pump | 1405.2 | 1.6 | -99.9 |
| rural biomass boiler | 561.1 | 908.1 | 61.8 |
| rural gas boiler | 399.4 | 3265.9 | 717.8 |
| rural ground heat pump | 401.6 | 25.7 | -93.6 |
| rural oil boiler | 2046.1 | 2556.1 | 24.9 |
| rural resistive heater | 335.4 | 643.9 | 92.0 |
| urban decentral air heat pump | 1573.9 | 602.0 | -61.8 |
| urban decentral biomass boiler | 1655.3 | 471.9 | -71.5 |
| urban decentral gas boiler | 4116.2 | 5031.8 | 22.2 |
| urban decentral oil boiler | 2867.0 | 1815.5 | -36.7 |
| urban decentral resistive heater | 598.4 | 342.4 | -42.8 |
| TOTAL | 15959.5 | 15664.9 | -1.8 |

| 2040 | before | after | change % |
|---|---|---|---|
| rural air heat pump | 1405.2 | 94.5 | -93.3 |
| rural biomass boiler | 511.2 | 381.8 | -25.3 |
| rural gas boiler | 148.8 | 1749.6 | 1075.4 |
| rural ground heat pump | 392.7 | 380.7 | -3.1 |
| rural oil boiler | 1871.6 | 1116.1 | -40.4 |
| rural resistive heater | 299.0 | 435.9 | 45.8 |
| urban decentral air heat pump | 1717.6 | 363.9 | -78.8 |
| urban decentral biomass boiler | 753.4 | 594.7 | -21.1 |
| urban decentral gas boiler | 1052.7 | 2032.7 | 93.1 |
| urban decentral oil boiler | 1917.8 | 1209.9 | -36.9 |
| urban decentral resistive heater | 268.6 | 553.5 | 106.0 |
| TOTAL | 10338.8 | 8913.3 | -13.8 |

| 2050 | before | after | change % |
|---|---|---|---|
| rural air heat pump | 0.8 | 92.9 | 12133.5 |
| rural biomass boiler | 143.9 | 252.5 | 75.5 |
| rural gas boiler | 39.7 | 1293.6 | 3157.5 |
| rural ground heat pump | 1172.3 | 833.3 | -28.9 |
| rural oil boiler | 503.8 | 317.6 | -37.0 |
| rural resistive heater | 347.2 | 833.3 | 140.0 |
| urban decentral air heat pump | 2449.5 | 646.0 | -73.6 |
| urban decentral biomass boiler | 0.0 | 597.2 | 3034458.0 |
| urban decentral gas boiler | 1052.7 | 1706.8 | 62.1 |
| urban decentral oil boiler | 1917.8 | 352.6 | -81.6 |
| urban decentral resistive heater | 271.8 | 868.6 | 219.6 |
| TOTAL | 7899.5 | 7794.6 | -1.3 |

#### System totals

| horizon | objective before (bn) | objective after (bn) | delta (MEUR) | delta % | BEWAL CO2 before (Mt) | BEWAL CO2 after (Mt) |
|---|---|---|---|---|---|---|
| 2025 | 333.472 | 333.536 | 63.616 | 0.019 | 21.982 | 21.982 |
| 2030 | 357.506 | 358.350 | 844.152 | 0.236 | 15.456 | 15.456 |
| 2040 | 289.954 | 290.617 | 663.378 | 0.229 | 8.587 | 8.587 |
| 2050 | 281.953 | 281.532 | -420.540 | -0.149 | 1.717 | 1.717 |

#### Fuel and electricity drawn by decentral heating, TWh

| horizon | electricity before | gas before | oil before | solid biomass before | electricity after | gas after | oil after | solid biomass after |
|---|---|---|---|---|---|---|---|---|
| 2025 | 7.273 | 11.226 | 2.188 | 1.508 | 3.668 | 18.313 | 6.336 | 3.610 |
| 2030 | 8.297 | 3.280 | 0.524 | 6.093 | 3.662 | 17.039 | 3.047 | 4.154 |
| 2040 | 7.626 | 3.629 | 1.169 | 1.950 | 3.445 | 12.171 | 0.988 | 5.150 |
| 2050 | 7.348 | 1.840 | 0.821 | 0.243 | 5.563 | 6.851 | 0.008 | 3.680 |

#### What the comparison says

1. **The mix transfer works in every horizon.** The `after` shares track the TIMES
   shares to within the 5 % tolerance, against a `before` that is 56–85 % heat pump
   where TIMES is 8–38 %. The single largest correction is 2030: heat pump
   66.9 % → 12.0 %, gas 9.3 % → 57.0 %.
2. **2040 is the only horizon that cannot be fully delivered**, and it relaxes
   rather than failing: **0.215 TWh_th of the biomass floor is unmet** (18.52 %
   realised against a 19.41 % bound). That is 4.6 % of the 2040 biomass target and
   0.9 % of Walloon decentral heat — the quantified size of the TIMES/PyPSA
   disagreement of §8.7, and precisely the number a hard constraint would have
   destroyed by making the LP infeasible.
3. **Walloon CO₂ is identical before and after, to the tonne**, in all four
   horizons (21.982 / 15.456 / 8.587 / 1.717 Mt). The per-country cap binds in both
   runs, so the heat-mix constraint does not change *how much* Wallonia emits — it
   changes *what emits it*, displacing emissions from elsewhere in the Walloon
   system into heating. Worth stating plainly, because "impose the TIMES fossil
   heating mix" sounds like it should raise emissions and does not.
4. **Fuel and electricity move as intended.** Decentral heating electricity falls
   7.3 → 3.7 TWh in 2025 and 7.3 → 5.6 TWh in 2050, gas rises 11.2 → 18.3 TWh in
   2025, and 2040 solid biomass rises 1.95 → 5.15 TWh — the biomass floor pulling
   hard on a binding resource, consistent with it being the group that could not be
   fully met.
5. **Capacity churn is large but the total barely moves** (2050: 7 900 → 7 795
   MW_th, −1.3 %). The constraint reshuffles the fleet rather than inflating it —
   the opposite of option A, which added ~8 GW of idle boilers for no change in the
   mix at all.

### 8.7 The 2040 infeasibility — diagnosis and the decisions taken

The first attempt at the full chain **did not complete**, and how it failed is
worth recording because it changed the design.

`before` solved all four horizons in ~12 min. `after` solved 2025 and 2030, then
2040 came back

```
Barrier performed 176 iterations in 257.25 seconds
Infeasible model
…
Termination condition: infeasible_or_unbounded
```

and the job then ran for **13 hours** at ~0 % CPU. It was not retrying the solve:
`solve_network.py:2031` reacts to an infeasible condition by calling
`n.model.compute_infeasibilities()` — a Gurobi IIS over the presolved 1.28 M-row
model — which reached 5.4 M simplex iterations with objective `−1.7e+35` and would
not have terminated. **Infeasibility in one horizon therefore blocks the whole
myopic chain indefinitely, and looks like a hung process rather than a failure.**

#### Why 2040 is infeasible

Two global constraints already **bind** in the *legacy* 2040 solve, before any
heat constraint exists (shadow prices from `n.global_constraints`):

| 2040 constraint | limit | shadow price |
|---|---:|---:|
| `co2_limit_per_countryBEWAL` | 8.587 Mt | **−94.79 EUR/t** |
| `biomass limit` (EU solid biomass) | 327.2 TWh | **−62.51 EUR/MWh** |

and option C asks 2040 to move a long way into both:

| 2040 decentral heat | TIMES | legacy PyPSA | what the floor demands |
|---|---:|---:|---|
| gas boiler | 52.1 % | 14.8 % | ≈ 11.3 TWh_th ⇒ **≈ +1.7 Mt CO₂** on an already-binding 8.59 Mt cap |
| biomass boiler | 20.4 % | 6.9 % | ≈ 5.9 TWh of solid biomass, where BEWAL's *entire* supply is 10.5 TWh (6.0 domestic + 4.5 imported) and `solid biomass for industry CC` already takes 8.44 |
| heat pump | 23.2 % | **72.9 %** | capped |
| resistive heater | 2.4 % | 1.0 % | — |

Bisection on the real 2040 network (each variant killed the moment Gurobi printed
a verdict, so no IIS could start):

| variant | verdict |
|---|---|
| `slack_groups: [gas boiler]` | **still infeasible** |
| `slack_groups: [biomass boiler]` | *(see run log)* |
| `slack_groups: [gas boiler, biomass boiler]` | *(see run log)* |

Releasing the gas floor alone is **not** enough, which means at least two of the
floors are individually unsatisfiable — consistent with the table above, where the
biomass floor asks for more solid biomass than the node can obtain.

> **The finding, stated plainly:** the TIMES 2040 Walloon heating mix and PyPSA's
> 2040 Walloon CO₂ budget (`budget_national: 0.25`) plus the EU biomass limit are
> **mutually inconsistent**. TIMES delivers 52 % of decentral heat from gas in 2040
> while satisfying its own carbon constraint; PyPSA cannot, at any price. One of
> the two carbon/biomass envelopes is wrong, and reconciling them belongs in
> `config/input_parameters_for_models.csv` / `common_parameters.md` — it is a
> shared-assumption problem, not a soft-link problem. Surfacing exactly this kind
> of disagreement is what the coupling is for.

#### Decisions taken (so the workflow always completes)

1. **The mix constraints are soft by default** — `energy_mix.penalty: 1000`
   EUR/MWh_th, §3.3.1. This is the substantive change. Feasibility is now
   structural rather than hoped-for, and the unmet quantity is reported instead of
   crashing the run. Verified in both directions by
   `test_penalty_turns_an_impossible_mix_into_a_priced_relaxation`: the same toy
   network is `infeasible` with `penalty: 0` and `optimal` with `penalty: 1000`,
   relaxing only the group that cannot be served.
2. **A watchdog aborts on infeasibility instead of letting the IIS run.**
   `run_heat_softlink_comparison.sh` polls every `*_solver.log` for
   `Infeasible model` every 20 s and kills the chain immediately, so an
   infeasibility from *anywhere else* in the model still fails fast and loudly.
3. **The tolerance and senses were left alone.** Loosening `tolerance` or moving
   groups into `slack_groups` would have hidden the disagreement inside a
   plausible-looking mix; the penalty makes it visible and quantified instead.
4. **The CO₂ and biomass envelopes were *not* touched.** Raising the Walloon 2040
   budget to make the TIMES mix fit would be reverse-engineering a shared
   assumption to suit one sector. Left as the open point it is.

---

## 9. Open points

* **The full myopic chain has not been re-solved.** 2025 is verified end to end at
  full resolution with every constraint (§8.3); 2030-2050 have only the reduced
  harness of §8.5, which omits the national CO₂ budget. The concrete risk is that
  the TIMES gas *floor* and the PyPSA Walloon CO₂ *cap* are jointly infeasible in a
  later horizon — which would be a finding about the two models' alignment, not a
  bug. **This is the first thing to run next**
  (`snakemake --configfile config/config.times-pypsa.yaml --cores 12 -call`), and
  remember to `export GRB_LICENSE_FILE=$HOME/.gurobi/gurobi.lic` first: a
  non-interactive shell does not read `~/.bashrc`, and Gurobi then silently falls
  back to its size-limited demo licence.
* **Shadow prices are not exported.** The dual of each `times_heat_mix_<group>`
  constraint is exactly "what it costs PyPSA to accept the TIMES mix" — the most
  useful single output of this whole exercise for the TIMES↔PyPSA reconciliation
  discussion. Reaching it currently needs `solving.options.store_model: true` and
  a manual read of `n.model.constraints["times_heat_mix_gas boiler"].dual`. A
  post-solve dump belongs in `rules/postprocess.smk`.
* **Cost assumptions are still unreconciled.** If PyPSA's heat pumps are cheaper
  or its gas dearer than TIMES's, part of the §3 divergence is a *parameter*
  inconsistency rather than a structural one, and the constraint is papering over
  it. `data/walloon/custom_costs.csv` has no decentral heating rows and
  `config/input_parameters_for_models.csv` has none either. This is the natural
  next piece of analysis and it could change how tight the constraints ought to
  be.
* **The 1 314 h TIMES availability factor remains an inference.** It does not
  affect option C (which transfers energy) but it does affect §5: if the TIMES
  capacities are `activity / 1314 h` with no peak equation behind them, the
  base-year stock they imply is roughly 1.6-2.1× larger than a peak-consistent
  sizing. Since it is used as an inherited *stock* and never as a floor, an
  over-estimate costs nothing and under-constrains nothing — but it should be
  confirmed with the TIMES modellers.
* **Water heating is still not transferred separately.** TIMES resolves it
  (`RW*`/`CW*`, a stable 13.1-13.4 % of useful heat) and PyPSA has the buses, but
  `write_wallon_heat_demands` rescales space and water together on one factor.
  Second-order for the mix, first-order for a future storage study.
* **`retrofitting.retro_endogen` must stay `false`.** TIMES has already
  retrofitted the demand (18.5 PJ in 2050). Unchanged by this work, restated
  because option C makes the heat balance tighter and a double count would now
  show up as an infeasibility rather than as a quiet over-supply.
