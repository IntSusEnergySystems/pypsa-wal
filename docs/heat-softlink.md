# The Walloon heating soft-link — options, decision, implementation, results

How the TIMES-WAL residential/tertiary heating answer is transferred into
PyPSA-Wal: the mechanisms that were evaluated, the one that is live, what it
delivers, and what is still open.

**Status:** implemented and merged. Option **B′** (reconstructed hourly profiles)
is on in [`config/config.walloon.yaml`](../config/config.walloon.yaml);
option **C** (annual energy-mix constraints) stays in the tree behind its own
switch and is off. Both are off in
[`config/config.walloon.yaml`](../config/config.walloon.yaml).

**Reference scenario:** `scen_demande_haute_v01_260727_fix_nuc_2807.vd` (+ `.vdt`),
6 h snapshots, full myopic chain 2025 → 2050, all twelve solves `Optimal`.
Generated result tables:
[`heat_softlink_comparison_tables.md`](heat_softlink_comparison_tables.md).

| Section | |
|---|---|
| [§1](#1-the-problem) | why a mix transfer is needed at all |
| [§2](#2-the-four-mechanisms-and-why-b-won) | options A / B / B′ / C, and the decision |
| [§3](#3-what-is-implemented) | config, code, artefacts |
| [§4](#4-results) | fidelity, cost, capacity, fuels |
| [§5](#5-the-2030-heat-pump-dip-diagnosed) | why BEWAL heat-pump **capacity** falls 2025 → 2030, and the fix |
| [§5b](#5b-cost-reconciliation--times-prices-decentral-heating-135-cheaper) | TIMES vs PyPSA appliance costs, measured |
| [§6](#6-scope-district-heating-stays-out) | district heating is excluded, and why |
| [§7](#7-facts-that-are-easy-to-get-wrong) | units, availability factors, timeslices |
| [§8](#8-open-points) | what is unresolved |
| [§9](#9-operational-hazards) | failure modes that cost real time |

---

## 1. The problem

TIMES-WAL optimises the Walloon heating stock at a technological resolution PyPSA
cannot match (dwelling archetype, vintage, retrofit state). PyPSA-Wal has an
hourly resolution TIMES cannot match — every heat commodity in TIMES-WAL is
`ANNUAL`; only electricity is resolved sub-annually.

The legacy soft-link transferred only the **annual useful-heat totals** and let
PyPSA re-optimise the appliance fleet from scratch. It threw the TIMES answer
away: mean absolute share error **15.9–20.5 pp** over six technology groups, with
heat pumps overshooting by **+47 to +55 pp** in every horizon. In 2025 PyPSA
greenfielded ~2.5 GW_th of heat pumps and ran them at 5 000–7 600 equivalent
full-load hours as baseload, covering 55 % of Walloon heat, while leaving the
9.1 GW of inherited gas boilers at ~1 000 h.

Three harmonisations were built to close that gap. Two are mechanism-independent
and are **always on** in the coupled config:

* the **TIMES base-year appliance stock** replaces the EU-2012 population-scaled
  row of `existing_heating_distribution` for BEWAL (§3, §5);
* the **urban/rural split is frozen at the base year**, so the TIMES archetype
  labelling cannot drift dwellings between PyPSA buses (59 % rural in 2025 →
  37 % in 2050 if left free).

The third is the **mix transfer**, and that is what §2 decides.

---

## 2. The four mechanisms, and why B′ won

| | **A** — `p_nom_min` | **B** — static demands | **B′** — pinned hourly profile | **C** — annual energy constraint |
|---|---|---|---|---|
| What it does | TIMES capacities become minimum installed capacity | TIMES appliance consumption becomes exogenous demand; PyPSA stops modelling heat | TIMES share × PyPSA's own hourly heat-load shape → one profile per group; dispatch pinned to it | each group's annual heat ≥ (or ≤) its TIMES share of realised supply, ±5 % |
| Transfers the TIMES mix | **No** | Yes | Yes | Yes |
| Keeps PyPSA hourly flexibility | Yes | **No** | **No** | Yes |
| Needs TIMES sub-annual data | No | **Yes — does not exist** | No | No |
| Unit conversions | th→el (COP), th→fuel (η) | th→fuel, th→el | none | **none** |
| Depends on the urban/rural label artefact | Yes | Yes | No (sum over both buses) | No |
| CO₂ accounting stays correct | Yes | only if links kept | Yes | Yes |
| Cost distortion | **≈ +0.6 bn EUR/a of idle iron** | — | none by construction | dual-priced, visible |
| Verdict | **rejected** | **rejected** | **merged** | kept behind a switch |

**Why A was rejected.** The divergence is not a capacity problem. PyPSA already
holds a stock comparable to TIMES's and still electrifies. Forcing `p_nom_min`
adds ≈ 0.6 bn EUR/a of annualised capital (+59 % on the BEWAL heating bill)
**without moving a single MWh of the energy mix**.

**Why B was rejected.** There is no TIMES hourly heat profile to import. The
finest sub-annual signal in the model is a 120-timeslice shape on
`RSDELC`/`COMELC`, it is an exogenous input rather than a result, and the
timeslice→calendar mapping is not in the `.vd` at all.

**Why B′ over C.** Four reasons, in order:

1. **It transfers what it claims to transfer.** 0.00 pp mean share error in three
   horizons out of four, against option C's 0.85–1.92 pp with individual groups
   off by up to 144 % in relative terms.
2. **Fewer knobs.** Option C's result depends on `mode`, `tolerance`,
   `zero_target` and `slack_groups`. B′ depends on the TIMES shares and nothing
   else — unless the relaxation binds, in which case it says so, in TWh, in the
   group concerned.
3. **The flexibility it gives up is mostly not real.** Decentral thermal storage
   is **0.13 MWh** for the whole of decentral Wallonia in the 2050 network;
   decentral cycling is 0.03–0.08 % of decentral heat supplied, against
   27–157× more on the district-heating bus, **which B′ does not touch**. The
   decentral heat vent is exactly 0.000 TWh in all eight solves.
4. **It is checkable.** The exported profile *is* the constraint, and
   `check_heat_profile_fidelity.py` reconciles it against the solved network
   group by group, bus by bus, snapshot by snapshot.

**Against B′:** it costs **240–690 MEUR/a more than option C** (0.08–0.19 %), and
it makes Walloon heating electricity exogenous.

**The honest caveat.** If the next study is about heating *flexibility* rather
than the heating *mix*, this decision inverts — option C frees the hour, B′
assumes it away. Both mechanisms live behind one config block, so switching is a
one-line change.

---

## 3. What is implemented

### 3.1 Config

```yaml
sector:
  times_heat:
    node: BEWAL
    urban_rural_split: times_base_year   # times | times_base_year | pypsa
    base_year_capacities: true
    profile:            # option B′ — live
      enable: true
      absorber: heat pump    # the one group left unpinned; takes the bus residual
      penalty: 1000.0        # EUR/MWh_th undelivered; 0 = hard constraints
      free_groups: []
      export: true
    energy_mix:         # option C — off, kept for the flexibility question
      enable: false
      mode: share            # share | absolute
      tolerance: 0.05
      slack_groups: []
      zero_target: forbid    # forbid | free
      penalty: 1000.0
```

`profile.enable` and `energy_mix.enable` are **alternatives, not layers** —
enabling both raises. Deleting the whole `times_heat` block reproduces the
pre-2026-08 results exactly; every switch defaults to the legacy behaviour.

```bash
snakemake --configfile config/config.walloon.yaml --resources mem_mb=100000 --cores 12 -call
```

### 3.2 Where the code lives

Extraction in the library, model physics in the model.

| Piece | Where |
|---|---|
| Group definition (TIMES categories ↔ PyPSA carriers, senses, every arbitrary mapping + its justification) | `TIMES_PyPSA/data/heat_softlink_groups.csv` |
| Target and capacity extraction | `TIMES_PyPSA/times_pypsa/heat_softlink.py` |
| Wiring into the exports | `TIMES_PyPSA/times_pypsa/pipeline.py` (`export_horizon`, `export_all_horizons`, `export_coupling_dir`) |
| **B′** profile reconstruction, constraints, relaxation, pre-solve budget report, CSV export | [`scripts/walloon_scripts/times_heat_profiles.py`](../scripts/walloon_scripts/times_heat_profiles.py) |
| **C** constraints, urban/rural split, base-year stock substitution, option validation | [`scripts/walloon_scripts/times_heat_softlink.py`](../scripts/walloon_scripts/times_heat_softlink.py) |
| Solver hook (dispatches to whichever mechanism is on) | [`data/custom_extra_functionality.py`](../data/custom_extra_functionality.py) |
| Demand split | `scripts/prepare_sector_network.py::harmonise_residential_urban_rural_split` |
| Base-year stock | `scripts/build_existing_heating_distribution.py::maybe_apply_times_base_year_stock` |
| Snakemake I/O | `rules/build_sector.smk`, `rules/solve_myopic.smk`, `rules/common.smk` |
| Comparison driver + report | `scripts/walloon_scripts/run_heat_softlink_comparison.sh`, `scripts/walloon_scripts/compare_heat_softlink.py` |
| Tests | `TIMES_PyPSA/tests/test_heat_softlink.py` (20) · `test/test_times_heat_softlink.py` (37) · `test/test_times_heat_profiles.py` (30) |

### 3.3 Artefacts

```
resources/<run>/heating_targets_{year}.csv      # per group: scope, constrained,
                                               # pypsa_component, pypsa_carriers,
                                               # sense, TWh, PJ, share,
                                               # times_categories (provenance)
resources/<run>/heating_capacities_{year}.csv   # base-year stock, MW_th
results/<run>/heating_profiles/                 # B′ exported profiles
```

The `times_categories` provenance column is not decoration — it is how a reader
checks that the 23 TIMES child categories were each assigned exactly once.

### 3.4 The base-year stock substitution

BEWAL, MW thermal output. "PyPSA" is the EU-2012 dataset scaled by population;
"TIMES" is `VAR_Cap` 2025.

| Technology | PyPSA (EU 2012) | TIMES 2025 | change |
|---|---:|---:|---:|
| gas boiler | 9 139 | 12 323 | **+35 %** |
| oil boiler (incl. coal) | 6 670 | 5 817 | −13 % |
| biomass boiler | 1 384 | 1 833 | +32 % |
| resistive heater | 1 011 | 1 264 | +25 % |
| air heat pump | 54 | 936 | **+17×** |
| ground heat pump | 20 | 1.2 | −94 % |
| **total transferable** | **18 279** | **22 174** | **+21 %** |
| *not transferable: solar thermal* | — | *99* | PyPSA solar thermal is a `Generator` with no vintage structure |
| *not transferable: DH substations* | — | *265* | PyPSA serves the DH load directly from the bus |

**The heat-pump row is the point of the exercise** — it removes the base-year
free-capacity artefact that no amount of constraint work can reach. Feasibility
has 1.7× head-room: peak decentral heat demand is 10.31 GW_th against
≈ 17.65 GW_th of *dispatchable* thermal output. There is no `p_nom_min` anywhere —
the substitution changes what PyPSA **inherits**, never what it **must build**.

> **Upstream quirk worth knowing.** `add_existing_baseyear` sizes an inherited
> boiler as `p_nom = capacity / costs.efficiency` (a *modern* appliance: 0.975 gas,
> 0.900 oil) but gives the link the *stock-average* efficiency from
> `heating_efficiencies_*.csv` (0.742 gas, 0.654 oil). A "12.3 GW_th gas boiler
> stock" is therefore a 9.4 GW_th stock in the LP. PyPSA-Eur behaviour, unchanged
> here, and it applied identically to the EU-2012 row that was replaced.

---

## 4. Results

Full tables: [`heat_softlink_comparison_tables.md`](heat_softlink_comparison_tables.md)
(generated by `compare_heat_softlink.py` — do not edit by hand).

### 4.1 Mix fidelity — mean |share error| against TIMES, pp

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| legacy transfer | 15.88 | 20.54 | 17.51 | 16.91 |
| option C | 1.28 | 1.40 | 1.92 | 0.85 |
| **option B′** | **0.00** | **0.00** | **0.64** | **0.00** |

Worst group: legacy is always the heat pump (+47 to +55 pp); option C is the
resistive heater in 2030/2040 (+3.5 pp, i.e. **+81 % and +144 % relative**) —
once gas and oil sit on their `≥` floors and heat pumps on their `≤` cap,
resistive heat is the cheapest way to close the balance and nothing stops it.

B′'s total absolute annual gap over four horizons, six groups and two buses is
**0.923 TWh, all of it the single 2040 relaxation** below. 2025, 2030 and 2050 are
exact to solver tolerance.

### 4.2 The one thing B′ could not deliver

| 2040, TWh_th | pinned | realised | gap |
|---|---:|---:|---:|
| biomass boiler | 4.9396 | 4.4782 | **−0.4613** |
| heat pump (absorber) | 5.6042 | 6.0655 | **+0.4613** |
| gas / oil / resistive / solar | — | — | 0.00000 |

The pre-solve budget report predicted it before Gurobi was called: the
biomass-boiler profile alone claims ~70 % of what `BEWAL solid biomass` can
produce (8.25 TWh, shared with industry), against the EU solid-biomass limit.

> **This is the most useful output of the whole exercise, and it is not a
> soft-link defect: the TIMES 2040 Walloon heating mix needs more solid biomass
> than PyPSA's Wallonia can obtain.** It belongs in
> [`config/input_parameters_for_models.csv`](../config/input_parameters_for_models.csv),
> not in a constraint. Option C hits the same wall and reports 0.215 TWh_th
> because its `≥` floor asks for less (0.95 × the share of *realised* supply,
> against B′'s exact share of the *load*).

### 4.3 Cost

| horizon | legacy obj (bn) | option C Δ (MEUR) | option B′ Δ (MEUR) |
|---|---:|---:|---:|
| 2025 | 333.472 | +63.6 | +613.7 |
| 2030 | 357.506 | +844.2 | +1 531.0 |
| 2040 | 289.954 | +663.4 | +1 303.1 |
| 2050 | 281.953 | −420.5 | −179.2 |

Walloon CO₂ is **identical to the tonne** in all three variants (the national cap
binds). Gurobi runs `Crossover 0`, `BarConvTol 1e-5`, and the measured noise floor
on these objectives is **~190 MEUR** — do not read any difference smaller than
that. 2050 comes out negative for both because the constrained chains inherit a
different (cheaper) 2040 fleet.

### 4.4 Capacity follows energy

| 2050, MW_th | legacy | option C | option B′ |
|---|---:|---:|---:|
| decentral air heat pump (both buses) | 2 450 | 739 | 2 156 |
| decentral gas boiler | 1 092 | 3 000 | 2 603 |
| decentral oil boiler | 2 422 | 670 | **0** |
| **total decentral heat capacity** | 7 900 | 7 795 | **7 542** |
| *(memo: peak decentral heat load)* | | | *7 542* |

**B′'s decentral fleet comes out at exactly the peak load** — every technology is
sized for its own share of the peak and the shares sum to one. That matches "each
dwelling's appliance is sized for that dwelling's peak"; option C's answer is the
one a central planner with perfect substitution would build. Neither is wrong, but
only B′'s is checkable against the load. **This property is what §5 is about.**

---

## 5. The 2030 heat-pump dip, diagnosed

**Observation (raised 2026-08-21):** BEWAL holds *fewer* heat pumps in 2030 than
in 2025 in the archived run. Confirmed, and it is an accounting artefact, not an
economic signal.

`results/walloon/scen_demande_haute/csvs/nodal_capacities.csv`, BEWAL, MW_th:

| carrier | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| urban decentral air heat pump | **936.4** | **608.1** | 1 197.0 | 1 545.6 |
| rural air heat pump | 300.3 | 305.8 | 628.4 | 613.3 |
| rural ground heat pump | 82.3 | 226.2 | 418.5 | 712.8 |
| urban central air heat pump | 0.1 | 0.2 | 450.0 | 1 249.4 |
| **total** | **1 319.1** | **1 140.3** | 2 693.9 | 4 121.1 |

**Heat delivered rises monotonically over the same horizons** — 2.20 → 3.06 →
8.56 → 14.69 TWh_th. Only the capacity metric dips.

### 5.1 Mechanism

Two things combine, and neither is a bug in the soft-link.

**(a) A vintage retires between the two horizons.** `add_existing_baseyear` splits
the base-year stock over the grouping years that are still alive at the base year,
selected with `existing_capacities.default_heating_lifetime: 20`
(`config.default.yaml`): `{2010, 2015, 2019}`, in the ratios 5/14, 5/14, 4/14. The
asset is then given the **technology-data lifetime**, not the 20-year default —
and `decentral air-sourced heat pump` has a **lifetime of 18**. So the 2010
tranche, 5/14 = **35.7 % of the stock = 334.4 MW_th**, dies in 2028, i.e. between
the 2025 and 2030 horizons:

```
2025:  -2010 334.42 + -2015 334.42 + -2019 267.53 + -2025 0.01   = 936.4
2030:            —   + -2015 334.42 + -2019 267.53 + -2025 0.01
                                                   + -2030 6.15  = 608.1
```

**(b) Nothing forces a replacement, because the 2025 stock was never binding.**
Under B′ each group is sized for its share of the pinned peak (§4.4):

| BEWAL urban decentral air HP | 2025 | 2030 |
|---|---:|---:|
| installed, MW_th | 936.4 | 608.1 |
| peak flow used, MW_th | **438.6** | **608.1** |
| utilisation of installed capacity at peak | **47 %** | **100 %** |
| equivalent full-load hours | 1 264 | 2 700 |

So **2025 carries 498 MW_th of inherited overhang** — free, non-extendable, and
idle at peak — while **2030 is the first horizon in which the capacity is actually
determined by the model**, and it lands exactly on the pinned peak, topping up by
6.15 MW.

### 5.2 The fix, and what it changes

**Implemented (option 2 of the two candidates): a per-technology age profile for
the inherited heat-pump stock, derived from the TIMES trajectory itself.**

`existing_capacities.heat_stock_age_profile` is a new, optional config mapping
`{cost technology substring: {grouping_year: share}}`. Without it nothing changes;
with it, the named technologies get an explicit age distribution instead of the
linear one. Both Walloon configs set:

```yaml
existing_capacities:
  heat_stock_age_profile:
    air-sourced heat pump:
      2010: 0.089
      2015: 0.089
      2019: 0.822
```

**Where those numbers come from — TIMES, not an assumption.** The same `.vd` that
supplies the stock level also reports it in earlier years:

| Walloon air heat pump, MW_th | 2021 | 2025 | installed 2022–25 |
|---|---:|---:|---:|
| `VAR_Cap` via `heating_capacities()` | 231.6 | 929.4 | **697.8 = 75.1 %** |

Three quarters of the base-year fleet is younger than **every** available
grouping year, so it belongs in the newest live bin; the 231.6 MW_th that was
already standing in 2021 keeps the linear spread. That gives
`0.249 × {5/14, 5/14, 4/14}` plus `0.751` on 2019 — the three numbers above.

The contrast with the other technologies is the point: over the same 2021 → 2025
window the TIMES gas-boiler stock grew 30 %, biomass 4 %, while oil boilers and
resistive heaters **shrank** 20–25 %. A linear age spread is defensible for those
and demonstrably wrong for heat pumps, which is why the override is
per-technology rather than global.

**Verified** on the rebuilt `base_s_adm___2025_brownfield.nc`:

| BEWAL urban decentral air heat pump, MW_th | linear (before) | profile (after) |
|---|---:|---:|
| `-2010` vintage — dies 2028 | 334.4 | **83.3** |
| `-2015` vintage — dies 2033 | 334.4 | 83.3 |
| `-2019` vintage — dies 2037 | 267.5 | **769.7** |
| total inherited (unchanged) | 936.4 | 936.4 |
| **surviving into 2030** | **602.0** | **853.0** |

853 MW_th is above the 608 MW_th the pinned 2030 profile needs, so the 2030
capacity is inherited rather than rebuilt and **the total BEWAL heat-pump fleet
now rises across the 2025 → 2030 step** instead of falling. A small genuine
retirement remains — 83 MW_th of stock that really was installed around 2010 —
which is the physically correct behaviour rather than an artefact. *The 2030
figure itself needs the full myopic chain to confirm; only the 2025 vintage split
is measured above.*

**Two further notes:**

* **The profile applies to every node, not only BEWAL.** `add_existing_baseyear`
  adds the vintages vectorised over nodes, so a per-node profile would mean
  splitting that call. It is not worth it: European heat-pump sales grew by an
  order of magnitude over the same period, so a recent-weighted profile is closer
  to the truth everywhere than the linear default.
* **`grouping_years_heat` still stops at 2019**, so nothing can be dated later
  than that even though TIMES says most of the fleet is 2022+. The shares
  compensate for the level but not for the retirement *date*: the 2019 tranche
  dies in 2037 when the real 2023 vintage would live to 2041. Adding a 2024
  grouping year would fix that properly and is a one-line config change — but it
  shifts every technology's vintage structure, so it belongs in its own change
  with its own check.

**Reporting guidance is unchanged.** Under option B′ decentral capacity is a
restatement of the pinned peak, so heat **delivered** remains the informative
indicator; capacity alone still cannot be read as an electrification signal.

## 5b. Cost reconciliation — TIMES prices decentral heating 1.3–5× cheaper

Pinning PyPSA to the TIMES mix is only meaningful if the two models price the
appliances alike. They do not, and the gap is not uniform — which changes how the
whole exercise should be read.

**The comparison is annuity to annuity, and needs no assumption on either side.**
PyPSA's `capital_cost` *is* an annuity (`investment × annuity(lifetime, hurdle) +
investment × FOM`, EUR/MW/a). TIMES `Cost_Inv` turns out to be a **constant
annual payment stream over the asset's life**, not an overnight cost — verified on
the reference `.vd`, where `CHBALTH101` builds 0.0045 GW once in 2022 and then
pays 0.0469 MEUR/a in every period to 2040. So `Cost_Inv / VAR_Ncap` in a
process's **first** build period is its annuity in EUR/kW_th/a, directly
comparable, with no lifetime or discount rate assumed anywhere. Later periods are
unusable: their `Cost_Inv` carries earlier vintages' streams.

Reproduce with
[`scripts/walloon_scripts/compare_heat_costs.py`](../scripts/walloon_scripts/compare_heat_costs.py):

| EUR/kW_th/a | TIMES (weighted) | TIMES range | PyPSA | TIMES / PyPSA | processes |
|---|---:|---|---:|---:|---:|
| decentral gas boiler | 15.20 | 5.1–35.3 | 79.62 | **0.19** | 33 |
| decentral ground-sourced heat pump | 151.65 | 151.7 | 284.45 | 0.53 | 7 |
| biomass boiler | 95.80 | 22.0–143.2 | 166.80 | 0.57 | 26 |
| decentral air-sourced heat pump | 116.38 | 74.9–202.3 | 190.70 | **0.61** | 40 |
| decentral resistive heater | 15.37 | 7.2–16.6 | 20.56 | 0.75 | 19 |

*Solar thermal is excluded: PyPSA prices it per 1000 m² and TIMES per GW_th.*

**The level gap matters less than the relative one.** Against its own heat pumps,
**PyPSA's gas boiler is ~3× more expensive than TIMES's** (0.61 / 0.19). That is
exactly the direction needed to explain the legacy over-electrification of §1:
PyPSA saw gas as dear relative to heat pumps and built heat pumps. **So part of
the 47–55 pp heat-pump overshoot the soft-link removes was a parameter
inconsistency, not a structural one** — the constraint was papering over it.

Backing the annuities out at PyPSA's own annuity factor suggests roughly
113 EUR/kW_th overnight for a TIMES gas boiler against PyPSA's 396, and
~850 against 1135 for an air heat pump: consistent with **equipment-only versus
fully-installed** cost scopes rather than a disagreement about the same quantity.
That is a hypothesis, not a result — the overnight cost is **not in the `.vd`**
(`NCAP_COST` is an input), so confirming it needs the VEDA `~FI_T` heating cost
tables from ICEDD/Climact. **That request is now the action**, recorded as five
`status=pending` rows in
[`config/input_parameters_for_models.csv`](../config/input_parameters_for_models.csv)
under `none:heating_cost_reconciliation`.

Three caveats, all in the same direction:

* If TIMES capacity is `activity / 1314 h` rather than peak-sized (§7), its kW are
  fewer than PyPSA's for the same physical fleet, so its true EUR per *peak* kW is
  **lower still**. The finding is conservative.
* The `.vd` does not state its currency year; a 10–15 % inflation difference does
  not move a 5× ratio.
* `Cost_Inv` excludes `Cost_Fom`, which is reported separately, while PyPSA's
  `capital_cost` includes FOM. Removing PyPSA's FOM narrows gas from 0.19 to 0.29
  and the air heat pump from 0.61 to 0.75 — the *relative* distortion between them
  is unchanged.

**What this means for the live model.** Under option B′ the mix is pinned, so the
cost inconsistency **no longer changes what gets built** — it changes the reported
cost of building it. Two consequences:

1. The objective differences of §4.3 and the "what it costs PyPSA to accept the
   TIMES mix" number are inflated by whatever share of the gap is a genuine
   disagreement rather than a scope difference. Do not publish that number as a
   reconciliation cost until the `~FI_T` tables arrive.
2. Switching back to option C, or to the legacy transfer, would immediately
   re-expose the model to the distortion. That is now a documented reason to keep
   B′ rather than a preference.

---

## 6. Scope: district heating stays out

The DH *demand* is transferred exactly. The *supply* is not transferred at all,
and the two models do not share a technology vocabulary. 2050:

| Supply of Walloon district heat, 2050 | TIMES TWh_th | share | PyPSA TWh_th | share |
|---|---:|---:|---:|---:|
| Geothermal | **1.54** | **52 %** | **0** — never instantiated | — |
| Industrial waste heat ("chaleur fatale") | **0.61** | **21 %** | **0** — no such component | — |
| CHP + waste incineration + methanation waste heat | 0.79 | 27 % | 1.09 | 16 % |
| Air heat pump | 0 | — | **3.92** | **57 %** |
| Resistive heater | 0 | — | **1.89** | **27 %** |
| **Total supplied** | **2.94** | | **6.90** | |
| *of which serves the district-heat load* | *2.70* | | *2.69* | |
| *of which serves **DAC*** | *0* | | ***4.14*** | |

1. **PyPSA cannot represent 73 % of the TIMES 2050 DH supply.** Geothermal is
   gated behind `sector.heat_pump_sources.urban central: [air]`; industrial waste
   heat has no component; municipal-waste CHP is disabled.
2. **PyPSA's DH bus is not primarily a district-heating bus in 2050.** DAC
   withdraws 4.138 TWh_th — 154 % of the DH load — and is what sizes the 729 MW
   heat pump, the 1 531 MW resistive heater and the 7 303 MW / 181 GWh PTES.
3. **In 2040 PyPSA builds 1 103 MW of gas CHP** delivering 47 % of that year's DH
   load, at a moment when TIMES has retired nearly all its gas CHP.

Constraining this bus would cap DAC, would constrain Walloon power generation
through the welded CHP heat/power ratio (`add_chp_constraints` is dead code),
would double-count PTES re-injections, and could not express 73 % of the TIMES
answer anyway. **The prerequisite is modelling work, not constraint work:** a
geothermal heat source and an industrial-waste-heat link for BEWAL. Separate
decision, listed in §8.

The decentral buses, by contrast, are clean: no CHP (`micro_chp: false`),
negligible storage, DAC at 0.08 % of load. That is why the constraint is
well-posed there and only there.

---

## 7. Facts that are easy to get wrong

* **Heat-pump `p_nom` is MW _thermal_ in this code base, not MW electric.** The
  heat-pump links carry `p_min_pu = −COP/max(COP, 0.001) = −1` exactly, so
  `|p0| ≤ p_nom` with `p0` on the *heat* bus. `existing_heating_distribution` is
  likewise in MW thermal output. **The base-year substitution and both mix
  mechanisms therefore need no unit conversion at all.** Earlier analysis notes
  claimed a COP conversion was needed; that was wrong, and the correction is what
  made the stock substitution cheap.
* **A TIMES heating "capacity" is `activity / 1314 h`.** The 1 314 h availability
  factor is consistent across 25 process groups and 4 horizons, but the `.vd`
  carries results only — it is an **inference**, not a documented input. It does
  not affect the energy transfer; it does mean the base-year stock is roughly
  1.6–2.1× larger than a peak-consistent sizing. Harmless as an inherited stock,
  never used as a floor.
* **TIMES timeslices `S01…S10` are not in calendar order** (S05–S07 are summer by
  PV output, S01/S02/S09/S10 winter by heat-pump load), and the hour→slice
  assignment is not in the `.vd`. If sub-annual TIMES data is ever needed, the
  `G_YRFR` table must be requested from the VEDA model.
* **The urban/rural labels are a per-process labelling convention, not a TIMES
  result.** The pattern (legacy `100`/`N1` → rural, newer `N2`/`N4` → urban
  decentral) looks incidental. Both live mechanisms sum over the two buses so they
  do not depend on it; `urban_rural_split: times_base_year` freezes it for the
  demand split.
* **`retrofitting.retro_endogen` must stay `false`.** TIMES has already
  retrofitted the demand (18.5 PJ in 2050); a double count would now surface as an
  infeasibility rather than a quiet over-supply. (The renovation *discount* rate is
  set anyway — see [`discount-rates.md`](discount-rates.md) D6.)
* **The demand leak is fixed** (2026-08-01). 1.5 % (2025) to 8.6 % (2040) of
  Walloon appliance heat used to vanish: 18 heat-producing processes were absent
  from `mapping_processes.csv` and `CHSADUM-DEM` carried a label no heat rule
  lists. Now closed exactly (produced == exported) in all eight horizons, with
  three QA guards and a regression suite in `TIMES_PyPSA`.

---

## 8. Open points

Ordered by how much they block.

| # | Open point | Blocks |
|---|---|---|
| 1 | **Add a 2024 `grouping_years_heat` bin.** §5.2 fixed the *level* of the inherited heat-pump vintages but not their *date*: the newest bin is still 2019, so a fleet TIMES says was built in 2022–25 retires in 2037 rather than 2041. One config line, but it shifts every technology's vintage structure. | second-order capacity drift after 2035 |
| 2 | **Get the VEDA `~FI_T` heating cost tables from ICEDD/Climact.** §5b measured the gap — TIMES prices decentral heating 1.3–5× cheaper in annuity terms, and ~3× cheaper for gas *relative to* heat pumps — but only the annuity is in the `.vd`, so whether the gap is a scope difference (equipment vs installed) or a real disagreement cannot be settled without the input costs. Five `status=pending` rows now carry the ask. | publishing any reconciliation cost |
| 3 | **The 2040 solid-biomass conflict** (§4.2) — recorded in the shared table as `none:solid_biomass_2040_conflict`, `status=pending`. The TIMES 2040 heating mix asks for ~5.8 TWh of solid biomass at BEWAL against a 6 TWh/a local potential shared with industry. **Needs a decision with ICEDD/Valbiom:** either the Walloon potential is larger, or the TIMES biomass heating share is not attainable. Not a constraint problem. | 2040 fidelity |
| 4 | **`TimesHeatProfile-unmet` is not exported.** They are bare linopy variables, so PyPSA does not write them to the netCDF; they currently have to be reconstructed from realised dispatch by `check_heat_profile_fidelity.py`. Same gap for option C's slack and for option C's **per-group shadow prices**, which need `solving.options.store_model: true` plus a manual read and are that mechanism's single best output. | diagnostics |
| 5 | **Set `energy_mix.enable: false` explicitly in every config** rather than relying on the default, so the mutual-exclusion check never fires in someone else's run. | robustness |
| 6 | **District heating stays out of scope — decided 2026-08-21, pending an answer from ICEDD.** Checked: the geothermal direct-utilisation *profile* exists for BEWAL, but no geothermal *potential* does, so PyPSA instantiates no geothermal component at all (0 generators, 0 links in the solved 2050 network); industrial waste heat has no component either. Enabling them means inventing a Walloon resource on the strength of `RENGEO`, which appears in TIMES only from 2040. The ask is now recorded in the shared table as `none:district_heating_supply_conflict`. **Do not build it before the answer.** | reading BEWAL DH results as DH results |
| 7 | **Is the DAC-on-the-DH-bus result intended?** In 2050 DAC pulls 4.14 TWh_th from `BEWAL urban central heat`, more than the DH load. Legitimate CO₂-budget result, or an artefact of DAC having free access to a bus sized for buildings? **Not investigated.** | reading BEWAL DH results at all |
| 8 | **Should `add_chp_constraints` be revived?** A back-pressure CHP with no `c_v` operating region is a simplification nobody appears to have chosen deliberately. Fixing it changes power-sector results, so not a side-effect to slip into a heating PR. | §6, later |
| 9 | **Water heating is not transferred separately.** TIMES resolves it (`RW*`/`CW*`, a stable 13.1–13.4 % of useful heat) and PyPSA has the buses, but `write_wallon_heat_demands` rescales space and water on one factor. Second-order for the mix, first-order for a future storage study. | a storage study |
| 10 | **Confirm the 1 314 h availability factor and the urban/rural labelling intent** with the TIMES modellers (§7). Two questions, no code. | confidence, not results |

---

## 9. Operational hazards

These cost real time and are reproduced here so the next chain does not repeat
them. See also [`instructions.md`](../instructions.md).

| Hazard | What happens | Guard |
|---|---|---|
| **An infeasible sector LP hangs the whole chain.** `solve_network.py` reacts to `infeasible_or_unbounded` by calling `n.model.compute_infeasibilities()` — a Gurobi IIS over ~1.3 M rows. On the 2040 network Gurobi found infeasibility in 257 s then ran **13 h at ~0 % CPU** without finishing the IIS. | looks like a hung process, not a failure | soft constraints by default (`penalty: 1000.0`); the watchdog in `run_heat_softlink_comparison.sh` polls every `*_solver.log` for `Infeasible model`; **and** the pre-solve budget report, the only guard that fires *before* the solver |
| **Editing a constraint module does not invalidate solved networks.** `custom_extra_functionality` is a Snakemake *param*, and Snakemake does not follow what the hook imports. | the chain reports `Nothing to be done`, finishes in seconds, and the comparison driver re-archives the **previous** answer as the new one — the most dangerous failure here, because the numbers are plausible | `CUSTOM_EXTRA_FUNCTIONALITY_MODULES` in `rules/common.smk` declares them as *inputs* of `solve_sector_network_myopic`. Sanity check: a phase that completes far too fast, or two variants with identical objectives |
| **Switching git branch while a chain is solving.** Rule scripts are read from the working tree at execution time. | a mid-run `git checkout` silently changes the code half the horizons were solved with, and leaves no trace in the results | run every variant from **one** checkout, switching mechanism by config overlay. `run_heat_softlink_comparison.sh` is built this way |
| **Killing Snakemake leaves its children running.** | rule scripts and solvers at 0 % CPU, plus a stale `.snakemake/locks/` | `pkill -f 'snakemake .*config.times-pypsa'; pkill -f '\.snakemake/scripts/tmp'; pgrep -af 'snakemake\|gurobi' \|\| echo clean` |
| **`--configfile`, `--resources`, `--forcerun`, `--omit-from`, `--until` all take `nargs="+"`.** | a target written straight after them is swallowed; Snakemake then runs the whole `all` target, or tries to parse your `.nc` as YAML | put targets **first**: `snakemake <targets> --configfile … --cores 12` |
| **Gurobi falls back to its demo licence in non-interactive shells.** | `Model too large for size-limited license` — `~/.bashrc` is not read | `export GRB_LICENSE_FILE=$HOME/.gurobi/gurobi.lic` in every driver script |
| **A snapshot subsample with a stride that divides the snapshots per day.** | samples midnight only; solar `p_max_pu` is 0 everywhere and any solar constraint is trivially infeasible | use a stride coprime with the snapshots per day (13, not 12, at 6 h) |
| **A `until … sleep` watcher with no exit condition.** | spins forever when the watched job dies before writing its marker | bound every wait (`for _ in $(seq 1 180)`) *and* `kill -0 "$PID" \|\| break` |
