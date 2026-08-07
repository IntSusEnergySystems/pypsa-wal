# Soft-linking the Walloon heating system: TIMES → PyPSA

**Status:** analysis. **Issue 1 (the demand leak) is FIXED as of 2026-08-01** —
see §8. **Option C is IMPLEMENTED as of 2026-08-05**, together with issues 2 and 3
(the capacity double count and the index filter) and the base-year capacity
harmonisation of recommendation 2 — see
**[`heat_soft_linking.md`](heat_soft_linking.md)** for what was built, every
modelling choice that had to be made, and the verification log. This file remains
the *analysis*; that one is the *implementation record*.

> **One factual correction from the implementation.** §2 and §4 of this document
> state that a heat pump's `p_nom` is in **MW electric**, so transferring TIMES
> capacities would need a COP ("a ~60 % difference in the conversion factor
> alone"). That is wrong for this code base: the heat-pump links carry
> `p_min_pu = −COP/max(COP, 0.001) = −1` exactly, so `|p0| ≤ p_nom` with `p0` on
> the *heat* bus and **`p_nom` is MW thermal**. `existing_heating_distribution` is
> likewise in MW thermal output. Option C and the base-year stock substitution
> therefore need **no unit conversion at all**. Details in
> [`heat_soft_linking.md`](heat_soft_linking.md) §3.4 and §5.3.

**Date:** 2026-07-31, leak fix appended 2026-08-01, implementation note 2026-08-05
**Reference scenario:** `scen_demande_haute_v01_260727_fix_nuc_2807.vd` (+ `.vdt`),
solved networks in `results/times-pypsa/scen_demande_haute/`.

---

## 0. The question

TIMES-WAL optimises the residential/tertiary heating stock with a technological
resolution PyPSA cannot match (dwelling archetype, vintage, retrofit state).
PyPSA-Wal has an hourly resolution TIMES cannot match. Today the soft-link
transfers only the **annual useful-heat totals**, and PyPSA then re-optimises the
appliance fleet from scratch — throwing away the TIMES answer and replacing it
with a coarser one.

Two candidate remedies were put on the table:

* **Option A** — pass the TIMES appliance **capacities** to PyPSA as minimum
  installed capacities.
* **Option B** — pass the TIMES appliance **consumption** (final energy per
  carrier) as static demands, so PyPSA stops optimising heating altogether.

This document evaluates both against the actual data, and adds a third option
that emerged from the evidence.

### Summary of findings

| | |
|---|---|
| **Option A does not do what it is meant to do.** | The divergence between TIMES and PyPSA is *not* a capacity problem. In 2025 PyPSA already holds 9.1 GW of legacy gas boilers and 6.7 GW of oil boilers for BEWAL — comparable to the TIMES stock — and still supplies 55 % of Walloon heat with newly built heat pumps. Forcing `p_nom_min` adds idle iron and ≈ 0.6 bn EUR/a of annualised capital (+59 % on the BEWAL heating bill) **without moving a single MWh of the energy mix**. |
| **Option B in its literal form is not supported by the TIMES data.** | TIMES-WAL resolves *only electricity* sub-annually. Every heat commodity, and every non-electric fuel flow into a heating appliance, is `ANNUAL`. There are no TIMES hourly heat profiles to "rebuild": the finest signal available is a 120-timeslice shape on `RSDELC`/`COMELC`, it is an exogenous input rather than a model result, and the timeslice→calendar mapping is not in the `.vd` at all. |
| **A third option is the right one.** | Keep the PyPSA heat links and their hourly physics, and impose the TIMES **annual heat output per technology** as a linear constraint in `custom_extra_functionality`. This transfers exactly the quantity TIMES actually optimised (the appliance energy mix), keeps everything PyPSA is better at (peak sizing, temperature-dependent COP, storage, interaction with the power system), and sidesteps every unit and taxonomy mismatch that sinks Option A. |
| **CHP, district heating and storage constrain the *scope*, not the choice.** | The decentral heat buses are clean — no CHP (`micro_chp: false`), negligible storage and DAC — so the constraint is well-posed there. The **urban-central bus is not**: DAC withdraws 154 % of the DH load in 2050, PTES re-injects 23 % of all injections, CHP heat is welded to CHP electricity (`add_chp_constraints` is dead code), and 73 % of TIMES's own DH supply (geothermal + industrial waste heat) has no PyPSA component. **Option C therefore stops at the decentral buses; district heating keeps its demand-only transfer.** §2.5, §3.1, §6 *Scope*. |
| ~~**The existing demand soft-link leaks, and that must be fixed first.**~~ **FIXED 2026-08-01.** | Closing the TIMES heat balance exposed that **1.5 % (2025) to 8.6 % (2040) of Walloon appliance heat never reached PyPSA** — 18 heating processes carried no `Aggregation Level 2` label and `CHSADUM-DEM` carried one no rule listed, so no extraction rule matched them and their output vanished. Now closed exactly (produced == exported) in all eight horizons, with three new QA guards and a regression suite. Details in §1.1, §8 issue 1 and §10. |

**Recommendation: Option C (annual energy-mix constraints), with the TIMES
capacities reused for a different and genuinely useful purpose — replacing
PyPSA's base-year heating stock for BEWAL.** Rationale in §7.

---

## 1. How heating is actually represented in TIMES-WAL

Everything in this section was read directly from the `.vd` and cross-checked
against `mapping_processes.csv` / `mapping_commodities.csv`.

### 1.1 The chain

```
RDW_R_4Fac  ──(VAR_FIn)──  RH4F  ──(VAR_FOut)──  ┬─ RH4FGMXN1   (gas heater)
"Buildings: built area"    "space heating        ├─ RH4FOIL100  (oil heater)
 = exogenous useful-heat    for 4f houses"       ├─ RH4FELCHPN4 (air heat pump)
   service demand           [PJ, ANNUAL]         ├─ RH4FELCN1   (electric radiator)
                                                 ├─ RH4FLOG100 / RH4FPEL100 (biomass)
                                                 └─ Retrofit-S_R_4Fac1958 …  ← "negawatts"
```

The service demand is carried by **archetype-specific heat commodities**:

| Prefix | Meaning | Archetypes |
|---|---|---|
| `RH**` | residential **space** heat | `2F`, `3F`, `4F` (2/3/4-façade houses), `AP` (apartments); `RHN**` = new dwellings |
| `RW**` | residential **hot water** | same archetypes, `RWN**` = new |
| `CH**` | tertiary **space** heat | `BA`, `BP`, `CO`, `CS`, `EN`, `SA` (building types) |
| `CW**` | tertiary **hot water** | same |

**Worked verification — `RH4F`, 2040 (PJ):**

```
PRODUCTION (VAR_FOut)                    CONSUMPTION (VAR_FIn)
  Residential rural gas heater   … )       RDW_R_4Fac  ("Buildings: built area")  22.8046
  Residential rural oil heater  0.6303
  Residential rural electric …  0.6128
  Retrofitting improvements     0.5221 + 0.3055 + 0.2365
  … 13 processes in total
  TOTAL OUT                    22.8046     TOTAL IN                              22.8046
```

The balance closes exactly. Two structural facts fall out of it:

1. **The useful-heat service demand is exogenous and constant.** `RH4F` = 22.8046 PJ
   in 2025, 2030, 2040 *and* 2050. Same for every other heat commodity. Total
   residential + tertiary useful heat is 98.6 → 100.1 PJ across the four
   horizons, of which hot water (`RW*`/`CW*`) is a stable 13.1–13.4 %.
2. **Retrofitting is modelled as a supply-side "negawatt" process.** The
   `Retrofit-*` processes consume a dummy commodity (`Dum-Retrofit-S_R_4Fac2005`)
   and produce real heat. TIMES chooses how much retrofit to buy; the appliances
   supply the remainder.

So the number pypsa-wal receives today as
`BEWAL residential urban decentral heat` is **appliance output = service demand
minus TIMES retrofit** — except that it does not close:

| PJ | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| Useful-heat service demand (all archetypes, = `VAR_FIn` of the `Building*` drivers) | 98.63 | 98.73 | 99.52 | 100.06 |
| − TIMES retrofit ("negawatts") | −1.49 | −3.56 | −10.22 | −18.49 |
| = appliance heat output that *should* be soft-linked | 97.14 | 95.17 | 89.31 | 81.57 |
| **− actually exported** (3 decentral heat + 2 district-heating categories) | **95.70** | **91.97** | **81.63** | **76.29** |
| **= LEAK** | **1.44** | **3.20** | **7.68** | **5.28** |
| leak as % of appliance heat | 1.5 % | 3.4 % | **8.6 %** | **6.5 %** |

**This was a defect in the soft-link**, independent of which option is chosen.
**Fixed 2026-08-01** — see §8 issue 1 and §10. Measured on the useful-heat
`VAR_FOut` balance, the leak was 2.23 / 3.70 / 7.68 / 5.28 PJ (the 2025 and 2030
figures exceed the table above by the tertiary CHP heat and geothermal that the
"service demand − retrofit" line did not account for separately). After the fix,
`Σ VAR_FOut(Heat) == Σ exported` **exactly** in all eight horizons 2021–2050.

Effect on the demands PyPSA receives (`wallon_demands_*.csv`, PJ):

| Category | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| `BEWAL residential urban decentral heat` | +0.74 | +1.39 | **+4.55** | **+4.39** |
| `BEWAL residential rural heat` | +0.68 | +1.40 | +1.56 | — |
| `BEWAL services urban decentral heat` | +0.82 | +0.90 | +1.57 | +0.89 |
| **total transferred building heat** | **+2.23** | **+3.70** | **+7.68** | **+5.28** |
| | +2.3 % | +4.0 % | **+9.4 %** | **+6.9 %** |

Almost all of it lands on `residential urban decentral biomass boiler`
(+4.48 PJ in 2040, +4.39 PJ in 2050 — `RH2FPELN2`, a pellet boiler), which is a
material change to the Walloon **biomass** balance PyPSA must source from its wood
potential. §9 flagged this as the thing to confirm before adding the labels; it
is now confirmed and applied.

The retrofit accounting is *consistent* with the PyPSA side, because `retrofitting.retro_endogen`
is `false` in `config.default.yaml` and is not overridden. Had it been `true`,
PyPSA would have retrofitted an already-retrofitted demand. Worth a comment in
the config so nobody turns it on by accident.

### 1.2 What a TIMES heating "capacity" is — and is not

`VAR_Cap` for every one of the 25 heating process groups is in **GW**, and the
process activity is the **heat output** (`VAR_Act = VAR_FOut`, verified on
`RH4FELCHPN4` and `RH2FGMXN1`). So TIMES capacities are MW **thermal, output
side**. That much is convenient. The rest is not:

**(a) There is no peak constraint on heat.** `EQ_Peak` exists in the `.vd` for
exactly one commodity — `ELCForPeak`. Heat has no reserve-margin equation.

**(b) Capacity is a fixed-availability by-product of annual activity.** Dividing
heat output by capacity gives the equivalent full-load hours:

| Group | FLH 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| Residential rural electric heater | 1314 | 1314 | 1314 | 1314 |
| Residential urban decentral heat pump | 1273 | 1148 | 1315 | 1314 |
| Residential rural coal heater | 1314 | 1311 | 1314 | — |
| Commercial solar thermal | 1314 | 1314 | 1314 | 1314 |
| District heating | 1314 | 1314 | 1314 | 1314 |
| Residential rural gas heater | 1153 | 1217 | 1309 | **852** |
| Residential urban decentral gas heater | 1195 | 1186 | 1305 | **629** |

1314 h = 8760 × 0.15. A single availability factor, applied uniformly to solar
thermal, coal furnaces, district heating and heat pumps alike. Where FLH is
*below* 1314 (declining technologies, 2050 gas) the capacity is instead the
surviving legacy vintage stock. So:

> **TIMES capacity = max(annual heat output / 1314 h, surviving vintage stock).**
> It is never a peak-driven quantity.

PyPSA's BEWAL heat load, by contrast, has peak/mean = 3.2 and FLH = 2721 h
(2050, 6 h snapshots). A capacity sized for the actual peak is therefore
**≈ 2100/1314 ≈ 1.6–2.1× smaller** than the TIMES number. Handing TIMES
capacities to PyPSA as a floor means over-sizing by roughly a factor of two.

> *Inference, not verified from source:* the 1314 h reflects an `AFA = 0.15`
> availability parameter in the TIMES-WAL template. The `.vd` does not carry
> parameters, only results. Worth confirming with the TIMES modellers, because
> it determines whether the capacities mean anything physical at all.

**(c) The current export double-counts.** `extract_heating_capacities`
(`TIMES_PyPSA/times_pypsa/pipeline.py:936-975`) sums `VAR_Cap` **and**
`VAR_Ncap`. `VAR_Ncap` (new capacity in the period) is already inside `VAR_Cap`:

| 2050, MW | VAR_Cap | VAR_Ncap | exported |
|---|---:|---:|---:|
| Residential rural gas heater | 5 102 | 3 308 | **8 410** (+65 %) |
| Residential urban decentral gas heater | 4 004 | 1 916 | **5 920** (+48 %) |
| Residential urban decentral heat pump | 2 831 | 1 011 | **3 841** (+36 %) |

The same function's index filter (`boiler|heat pump|stove|thermal|heater`) also
lets `Geothermal (IND)` (an *industrial* process) and
`Thermal Public - Retrofitting CCGT CCS` (a *power plant*, 1 740 MW) into
`heating_capacities_*.csv`, while dropping `District heating`. The file is
currently consumed by nothing, so this has never caused harm — but it is a
blocking defect for any option that uses it.

**(d) The urban/rural split is an artefact of a hand-made mapping.** TIMES-WAL
has no urban/rural dimension. The `Residential rural …` / `Residential urban
decentral …` labels are assigned per process in `mapping_processes.csv`, and the
assignment is not systematic — within the *same* 3F archetype:

```
RH3FGMX100   Rsd.Space Heat.Dwelling.3F.GMX.00.Furnace.   → Residential rural gas heater
RH3FPELN2    Pellets Boiler.HeatHotwater New-RH3F-New2    → Residential urban decentral biomass heater
RH3FELCHPN4  Air heat pump with electric boiler-RH3F-New4 → Residential urban decentral Heat pump
RH3FLPGN2    LPG boiler-RH3F-New2                         → Residential urban decentral OIL heater  ← mislabelled
```

Legacy (`100`, `N1`) processes tend to land in "rural", newer (`N2`, `N4`) ones
in "urban decentral". So a per-(urban/rural × technology) capacity or energy
target inherits a labelling convention, not a TIMES result. **Any constraint
should be imposed on the sum over rural + urban decentral**, where the artefact
cancels.

### 1.3 Temporal resolution — the decisive fact for Option B

TIMES-WAL has 130 timeslices: `S01…S10` (10 typical periods) × `Q01…Q12`
(12 intra-day blocks), plus the 10 season aggregates. That looks promising until
you ask *which variables use them*:

| Variable | rows at `ANNUAL` | rows at `SxxQyy` |
|---|---:|---:|
| `VAR_FIn` into heating appliances | 889 | 51 840 |
| `VAR_FOut` from heating appliances | 8 417 | **0** |

and the 51 840 slice-resolved input rows are **entirely** `RSDELC` and `COMELC`:

| carrier into heating appliances | ANNUAL rows | slice rows |
|---|---:|---:|
| `RSDELC`, `COMELC` (electricity) | 0 | 30 240 / 21 600 |
| `RSDGMX`, `COMGMX` (network gas) | 139 / 134 | 0 |
| `RSDOIL`, `RSDPEL`, `RSDLOG`, `RSDHET`, `COMSOL`, … | 12–68 | 0 |

Consistent with `mapping_processes.csv`, where **every** heating process has
`Time slice level = ANNUAL`.

So:

* **There is no TIMES heat profile.** The heat commodities (`RH*`, `RW*`, `CH*`,
  `CW*`) are annual balances. TIMES-WAL never sees a winter heat peak.
* The only sub-annual signal is the electricity draw of the electric appliances,
  and it is an **exogenous shape** (a `COM_FR`-style input), not an optimisation
  result. Evidence: normalised seasonal shares of `RSDELC`/`COMELC`, 2040 —

  | season | heat pumps | electric heaters | cooking | resid. other | data centres |
  |---|---:|---:|---:|---:|---:|
  | S06 (summer) | 5.8 % | 2.0 % | 10.2 % | 9.8 % | 9.5 % |
  | S09 (winter) | 16.7 % | 18.9 % | 14.2 % | 14.5 % | 14.1 % |
  | max/min ratio | 2.9 | 9.4 | 2.8 | 2.7 | 2.8 |

  `cooking`, `residential other` and `data centres` share one common default
  shape to three significant figures. Only the electric-heating processes get a
  seasonal shape of their own, and even the heat-pump aggregate is diluted to a
  ratio of 2.9 because it mixes space heating with (near-flat) heat-pump water
  heaters. PyPSA's own HDD profile puts **4.5–4.9 % of annual heat in June–August**;
  no TIMES shape is remotely that sharp.
* **The slice→calendar mapping is not in the `.vd`.** Neither the timeslice
  durations (`G_YRFR`) nor the assignment of the 8760 hours to `S01…S10` are
  exported. Grepping both repos confirms nothing of the sort has ever been
  parsed. Reconstructing an hourly profile from TIMES would require obtaining
  the timeslice definition from the VEDA model itself.

### 1.4 The Option-B payload, for reference

Final energy into building heating appliances, by carrier (PJ):

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| `RSDGMX` residential network gas | 39.97 | 45.78 | 38.94 | 26.01 |
| `RSDOIL` residential oil | 23.11 | 10.90 | 1.44 | — |
| `COMGMX` tertiary network gas | 15.35 | 12.52 | 5.39 | — |
| `RSDELC` residential electricity | 7.66 | 5.65 | 5.43 | 8.73 |
| `COMELC` tertiary electricity | 1.31 | 2.04 | 3.15 | 8.79 |
| `RSDLOG`+`RSDPEL`+`COMPEL`+`COMCPS`+`COMBGS` wood logs, pellets, chips, biogas | 9.15 | 10.99 | 12.73 | 8.13 |
| `RSDHET` + `COMHET` district heat delivered | 1.69 | 4.42 | 6.88 | 9.73 |
| `RSDCOA` coal, `RSDSOL`/`COMSOL` solar, `RSDLPG`, `*GEO` | 0.85 | 0.67 | 0.39 | 0.26 |
| **Total final energy** | **99.08** | **92.96** | **74.36** | **61.64** |
| *(memo: useful heat delivered)* | *95.70* | *91.97* | *81.63* | *76.29* |

---

### 1.5 District heating, CHP and thermal storage in TIMES-WAL

This is a *different* chain from the decentral appliances of §1.1, and it behaves
differently enough to change the scope of the recommendation (§6.4).

```
ECHPP_* gas CHPs ─┐
ETSTP_TVC_WST_E11 ├→ ELCHET ─┐
(waste incinerator)│  "Heat   │
CO2CTOMETHELC     ─┘  from CHP"│
(methanation waste heat)       │      RSDHET00/01/02   RSDHET   RH2FHETN1
                               ├────→ COMHET00      ─→ COMHET ─→ CH*LTH101 ─→ RH*/CH*
industrial waste heat ─ INDHWT ┤      "Fuel Tech N            (substations,   (useful
("chaleur fatale")             │       – Heat"                  η = 1.00)      heat)
geothermal ─────────── RENGEO ─┘       η ≈ 0.92
                                       (network loss)
```

**Supply mix of Walloon district heat in TIMES (PJ into the network):**

| | 2025 | 2030 | 2040 | 2050 | 2050 share |
|---|---:|---:|---:|---:|---:|
| `RENGEO` geothermal | — | — | 2.96 | **5.53** | **52 %** |
| `ELCHET` CHP + waste incineration + methanation waste heat | 0.78 | 0.95 | 1.96 | 2.83 | 27 % |
| `INDHWT` industrial waste heat ("chaleur fatale") | 1.02 | 3.87 | 2.52 | 2.21 | 21 % |
| **Total into network** | 1.80 | 4.82 | 7.45 | 10.57 | |
| **Delivered (`RSDHET`+`COMHET`)** | 1.69 | 4.42 | 6.88 | 9.73 | |
| implied network efficiency | 94 % | 92 % | 92 % | 92 % | |

District heating grows from **1.7 % to 12.7 %** of Walloon building heat over the
horizons — the fastest-moving part of the TIMES heating answer.

**The TIMES CHP fleet is small, fully public, and entirely dedicated to district
heat.** Five processes, all `ECHPP_*`/`ETSTP_*` (public power); 100 % of their
heat output is `ELCHET`. Heat/power ratios are **fixed** (back-pressure), constant
across horizons:

| Process | heat/power | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|---:|
| `ETSTP_TVC_WST_E11` waste incinerator (municipal waste + sludge) | 0.39 | 0.53 | 0.71 | 0.71 | 0.71 |
| `ECHPP_COM_GAS_E04` existing gas CHP | 1.43 | 0.37 | 0.37 | — | — |
| `ECHPP_COM_BGS_E05` biogas CHP | 0.75 | 0.13 | 0.13 | — | — |
| `ECHPP_MOT_GAS_E04` gas engine CHP | 0.63 | 0.04 | 0.03 | — | — |
| `ECHPP_CCGT-CHP_GAS_N` new CCGT CHP | 0.84 | — | — | 0.44 | — |
| `CO2CTOMETHELC` methanation waste heat (*not* a CHP) | — | — | — | 1.11 | 2.41 |

CHPs supply **2.6 % of Walloon electricity in 2025, falling to 0.9 % in 2050**.
By 2050 the only real CHP left is the waste incinerator; the rest of `ELCHET` is
power-to-methane waste heat. Industrial CHPs (`CHPIND*`) exist but their heat
(`IBOHTH`) never leaves industry — verified: no `CHPIND*` process produces
`ELCHET`.

**TIMES-WAL has no thermal storage, and structurally cannot have any.** The only
storage processes in the model are pumped hydro, CO₂ storage, EV batteries and
hydrogen tanks. Since every heat commodity is `ANNUAL` (§1.3), a heat store has
nothing to arbitrage.

Two further notes:

* The `~1314 h` availability finding of §1.2(b) covers the **appliance** groups,
  including the district-heating *substations*. The upstream delivery techs
  `RSDHET00/01/02` / `COMHET00` run at **~3 020 h** instead, so they are sized on
  a different (also exogenous) availability.
* **The soft-link exports district-heating *demand* only.** `wallon_demands_*.csv`
  carries `residential district heating` and `services district heating` — the
  delivered heat. Nothing about the supply mix (geothermal / waste heat / CHP)
  crosses to PyPSA, which therefore invents its own.

---

## 2. How heating is represented in PyPSA-Wal

Established by direct inspection of `scripts/prepare_sector_network.py`,
`add_existing_baseyear.py`, `add_brownfield.py` and the solved networks.

* **Buses.** `add_heat` creates 5 heat systems per node, but
  `cluster_heat_buses: true` (default, not overridden) strips the
  `residential `/`services ` prefix. The solved BEWAL network has exactly three
  heat buses: `BEWAL rural heat`, `BEWAL urban decentral heat`,
  `BEWAL urban central heat`. **The residential/services distinction does not
  survive into the optimisation.** `write_wallon_heat_demands` additionally
  deletes the whole `BEWAL services rural` sub-system, so `BEWAL rural heat` is
  residential-only for Wallonia.
* **Supply technologies** (all `p_nom_extendable`, none carrying any `p_nom_min`):
  air/ground heat pumps, resistive heaters, gas boilers, oil boilers, biomass
  boilers, solar thermal collectors, water tanks. Micro-CHP and endogenous
  retrofitting are off.
* **Units differ per technology**, which matters for any capacity transfer:

  | PyPSA component | bus0 → bus1 | `p_nom` is in |
  |---|---|---|
  | heat pump Link (reversed: `p_max_pu=0`, `p_min_pu=−COP`) | heat → electricity | **MW electric** |
  | resistive heater Link | electricity → heat | **MW electric** |
  | gas / oil / biomass boiler Link | fuel → heat | **MW fuel input** |
  | solar thermal Generator | — → heat | MW thermal |

  TIMES gives MW **thermal output** for all of them. Converting a heat pump
  requires a COP, and PyPSA's COP is hourly (`time_dep_hp_cop: true`) — a heat
  pump is sized on the *cold-hour* COP (~2.2), not on the TIMES annual average
  (2.6–3.6). This is a ~60 % difference in the conversion factor alone.
* **Existing stock** comes from `build_existing_heating_distribution.py`, i.e.
  the EC 2012 heating/cooling deployment dataset distributed by population —
  **not** from TIMES. `heating_capacities_*.csv` is written every horizon and
  read by nothing.
* **Demand.** `write_wallon_heat_demands` rescales `n.loads_t.p_set` for the
  three BEWAL heat loads by a single scalar so the annual total matches TIMES.
  The hourly shape (atlite HDD × BDEW intraday, minus
  `reduce_space_heat_exogenously_factor`) is preserved. Space and water are
  rescaled together by one factor, so the TIMES space/water split (water is
  13.1–13.4 % of TIMES useful heat in every horizon) is not transferred.
* **No mechanism to constrain heating capacity exists.** `add_CCL_constraints`
  supports Links but groups them by `bus1`'s country — which for heat pumps and
  micro-CHP is the *electricity* bus (and the ` low voltage` bus once the
  distribution grid is inserted). `data/custom_extra_functionality.py` is an
  empty stub.

### 2.5 CHP, district heating and thermal storage in PyPSA-Wal

**CHP.** Two carriers on the urban-central bus, each a single multi-output Link:
`urban central gas CHP` (bus0 gas, bus1 AC, bus2 heat, bus3 CO₂; `efficiency2 =
efficiency / c_b`) and `urban central solid biomass CHP` (bus0 solid biomass,
bus1 AC, bus2 heat, no CO₂ bus; `efficiency2 = efficiency-heat` — `c_b` is not
used), plus `CC` variants. **Micro-CHP is off** (`micro_chp: false`), so there is
no CHP on the decentral buses at all.

> **The CHP heat/power ratio is hard-wired, not an operating region.**
> `add_chp_constraints` exists at `scripts/solve_network.py:1151` and is
> **never called** — verified: the only occurrence of the name in the whole repo
> is its own `def`. It is also written against the legacy two-link formulation
> (`n.links.index.str.contains("electric")`), which cannot match the current
> single multi-output links, so calling it would be a no-op. `c_v` and
> `p_nom_ratio` are read by nothing.
>
> Consequence: heat and electricity move in lockstep. The realised annual
> heat/electricity ratio equals the design ratio `efficiency2/efficiency` to five
> decimals in every horizon: **1.00 for gas CHP, 3.055 for solid biomass CHP,
> 3.600 for biomass CHP CC.**

> **Solid-biomass CHP does not conserve energy.** `efficiency` (0.2652) +
> `efficiency-heat` (0.8294) = **1.0946** MWh out per MWh of solid biomass in
> (2050; 1.0944 in 2025). Read straight from
> `resources/…/costs_2050_processed.csv`. This is inherited from the pinned
> technology-data archive — `data/walloon/custom_costs.csv` contains no CHP row
> and neither does `config/input_parameters_for_models.csv`, so the TIMES and
> PyPSA CHP assumptions have never been reconciled. It matters here because a
> constraint written in MWh_th on the heat bus carries a 9.4 % bias when
> translated back to fuel.

**District heating.** `build_district_heat_share.py` gives BEWAL a district
fraction of 0.0374 → 0.0772 → 0.1568 → 0.2762 (2050 = the `potential: 0.3`
ceiling at `progress = 1.0`). The urban-central Load is built with a ×1.15
`district_heating_loss` uplift — **which `write_wallon_heat_demands` then scales
away**, because it multiplies the whole profile by a single factor to hit the
TIMES annual total. Verified: the BEWAL DH Load equals the TIMES delivered
district heat to five decimals in all four horizons (0.46129 / 1.21866 / 1.90300
/ 2.69347 TWh). So for BEWAL the DH share and loss machinery shape only the
*hourly profile*; the annual level is 100 % TIMES-driven. That is a good
property — but it also means **neither model charges anyone for the distribution
loss**: TIMES's own 8 % sits upstream in `RSDHET0x`, PyPSA's 15 % is scaled out.

**What can supply the BEWAL DH bus:** air heat pump, resistive heater, gas
boiler, oil boiler, solar thermal, gas CHP (+CC), solid biomass CHP (+CC), and
six waste-heat ports (Fischer-Tropsch, Sabatier, Haber-Bosch, methanolisation,
electrolysis, fuel cell — all ≤ 0.002 TWh). **Not present**: geothermal, ATES,
river water (the `limited_heat_sources` block only runs for sources listed in
`heat_pump_sources.urban central`, which is `[air]`), waste CHP
(`municipal_solid_waste: false`), and any industrial waste-heat link. Zero
components matching `geothermal|aquifer|river` exist in any of the four networks.

**Thermal storage.** Water tanks on all three heat systems; water pits (PTES)
urban-central only, both enabled; ATES and heat DSM off. Charger and discharger
are **separate Links of opposite orientation** on the same heat bus, both η = 1,
standing loss ≈ 7.8e-5 /h. In 2050 the BEWAL pits reach 7 303 MW / 181 GWh.

---

## 3. The divergence, quantified

Decentral heat supply for BEWAL (rural + urban decentral, excluding district
heating), TIMES appliance output vs. PyPSA solved dispatch:

**2025**

| Technology | TIMES TWh_th | share | PyPSA TWh_th | share |
|---|---:|---:|---:|---:|
| Gas boiler | 14.46 | 55.4 % | 8.44 | 31.1 % |
| Oil boiler | 5.71 | 21.9 % | 1.95 | 7.2 % |
| Heat pump | 2.12 | 8.1 % | **14.86** | **54.7 %** |
| Biomass boiler | 2.01 | 7.7 % | 1.14 | 4.2 % |
| Electric resistive | 1.62 | 6.2 % | 0.79 | 2.9 % |
| Solar thermal / coal / geo | 0.19 | 0.7 % | — | — |
| **Total** | **26.12** | | **27.17** | |

**2050**

| Technology | TIMES TWh_th | share | PyPSA TWh_th | share |
|---|---:|---:|---:|---:|
| Heat pump | 7.33 | 39.6 % | **16.53** | **85.8 %** |
| Gas boiler | 6.86 | 37.1 % | 1.49 | 7.7 % |
| Electric resistive / stove | 2.20 | 11.9 % | 0.30 | 1.6 % |
| Biomass boiler | 2.03 | 11.0 % | 0.21 | 1.1 % |
| Oil boiler | — | — | 0.73 | 3.8 % |
| Solar thermal | 0.07 | 0.4 % | — | — |
| **Total** | **18.50** | | **19.27** | |

The **base year is the tell**. In 2025, PyPSA's own brownfield routine gives
BEWAL an existing stock of 9 139 MW gas boilers, 6 670 MW oil boilers,
1 384 MW biomass, 1 011 MW resistive and 74 MW heat pumps — a stock whose
*composition* is broadly consistent with TIMES (TIMES 2025: 12 323 MW gas,
5 772 MW oil, 1 533 MW biomass, 1 263 MW electric, 929 MW heat pumps). PyPSA
then **builds 2 515 MW_el of new heat pumps in the base year** (against 69 MW_el
of inherited stock) and runs them at **5 000–7 600 equivalent full-load hours** —
i.e. as baseload — for 55 % of Walloon heat. The inherited gas boilers, which it
did not have to pay for, are left at 1 054 h (urban decentral) and the oil
boilers at 916 h.

> The divergence is a **dispatch-and-investment** divergence, not a capacity
> divergence. PyPSA has the boilers. It chooses not to use them, because at the
> PyPSA fuel and CO₂ prices a heat pump beats a gas boiler on marginal cost even
> after paying its annuity.

That single observation determines the assessment of Option A.

### 3.1 District heating — a structural mismatch, not a mix difference

The DH *demand* is transferred exactly (§2.5). The *supply* is not transferred at
all, and the two models do not even share a technology vocabulary. 2050:

| Supply of Walloon district heat, 2050 | TIMES TWh_th | share | PyPSA TWh_th | share |
|---|---:|---:|---:|---:|
| Geothermal | **1.54** | **52 %** | **0** — never instantiated | — |
| Industrial waste heat ("chaleur fatale") | **0.61** | **21 %** | **0** — no such component | — |
| CHP + waste incineration + methanation waste heat | 0.79 | 27 % | 1.09 | 16 % |
| Air heat pump | 0 | — | **3.92** | **57 %** |
| Resistive heater | 0 | — | **1.89** | **27 %** |
| Gas / oil boiler, solar thermal, electrolysis & FT waste heat | 0 | — | 0.00 | 0 % |
| **Total supplied** | **2.94** | | **6.90** | |
| *of which serves the district-heat load* | *2.70* | | *2.69* | |
| *of which serves **DAC*** | *0* | | ***4.14*** | |

Three things to take from this:

1. **PyPSA cannot represent 73 % of the TIMES 2050 DH supply.** Geothermal is
   gated behind `sector.heat_pump_sources.urban central`, which is `[air]`;
   industrial waste heat has no component at all; municipal-waste CHP is disabled.
2. **PyPSA's DH bus is not primarily a district-heating bus in 2050.** DAC
   withdraws 4.138 TWh_th — 154 % of the DH load — and is what sizes the 729 MW
   heat pump, the 1 531 MW resistive heater and the 7 303 MW / 181 GWh PTES.
3. **In 2040 PyPSA builds 1 103 MW of gas CHP** delivering 0.897 TWh_th, i.e.
   47 % of that year's DH load, at a moment when TIMES has retired nearly all its
   gas CHP. This is the same electrify-vs-gas disagreement as §3, running in the
   opposite direction.

---

## 4. Option A — TIMES capacities as `p_nom_min`

### What it would do

Set `p_nom_min` on the BEWAL heating Links/Generators equal to the TIMES
capacity per technology, per horizon (with `add_brownfield` carrying previous
vintages forward, so the floor must be applied net of surviving assets).

### Assessment

**It does not transfer the energy mix.** A capacity floor is not binding on
dispatch. PyPSA would install the boilers, pay for them, and continue to run
heat pumps — §3 shows it already does exactly this with 9 GW of gas boilers it
did not have to pay for. The one quantity the modellers care about (the fuel mix
of Walloon heating) is untouched.

**It is expensive.** TIMES 2050 gas-heater capacity is 9 106 MW_th ⇒ 9 198 MW of
`p_nom` at PyPSA's 0.99 boiler efficiency, against a PyPSA optimum of 915 MW.
The forced 8 283 MW at `capital_cost = 72 155 EUR/MW/a` costs

> **≈ 0.60 bn EUR/a of annualised capital on idle boilers**, against a total
> BEWAL heating-technology cost of 1.01 bn EUR/a in 2050 — a **+59 %** distortion
> of the heating bill, for zero change in emissions or fuel use.

**The capacities are the wrong number anyway.** From §1.2: they are
`activity / 1314 h`, with no peak equation behind them, so they exceed a
peak-consistent sizing by ~1.6–2.1×; the current export additionally
double-counts `VAR_Cap + VAR_Ncap` (+36 % to +65 %); and it contains two
non-building-heat rows.

**Three taxonomy mismatches have no clean resolution.**

| TIMES has | PyPSA has |
|---|---|
| residential vs. commercial appliances, separately | one merged bus set (`cluster_heat_buses`) — no services/residential split survives |
| urban/rural from a hand-made, internally inconsistent process label | urban decentral / rural driven by `urban_fraction` |
| MW thermal output, for all technologies | MW electric (heat pumps, resistive), MW fuel (boilers), MW thermal (solar) |

Converting heat-pump MW_th → MW_el needs a COP, and the right COP (PyPSA's cold-hour
value ~2.2) is not the TIMES annual average (2.6–3.6).

**Implementation cost is nonetheless low**, and this is the option's only real
merit: the `p_nom_min` column already exists on every component, and either
`custom_extra_functionality` or a small extension of
`walloon_scripts/BEWAL_potentials.py` could write it.

### Verdict

**Reject as a mix-transfer mechanism.** It is cheap to build and fails at the
stated goal while inflating cost. See §7 for the one place TIMES capacities
*are* worth using.

---

## 5. Option B — TIMES consumption as static demand

### What it would do

Freeze the Walloon heating system: replace the endogenous heat supply by fixed
hourly demands derived from the TIMES final energy per carrier (§1.4).

### The blocking problem

**There are no TIMES hourly heat profiles to rebuild** (§1.3). To be precise
about what is and is not available:

| What Option B needs | What TIMES-WAL has |
|---|---|
| hourly heat output per appliance | annual only — every heat commodity is `ANNUAL` |
| hourly fuel input per appliance | annual only for gas/oil/biomass/district heat |
| hourly electricity input per appliance | 120 timeslices — but an **exogenous input shape**, and diluted (space + water mixed) |
| slice → calendar hour mapping | **not in the `.vd` at all** |

So the literal proposal — "rebuild the hourly time profiles of the TIMES
appliances, aggregate them, pass them over" — cannot be executed from the `.vd`.
It would need the TIMES timeslice definition from VEDA, and even then would
deliver a 120-step exogenous shape that is demonstrably coarser than the atlite
HDD profile PyPSA already computes (winter/summer ratio 2.9 vs. PyPSA's
~4.9 % of annual heat in Jun–Aug).

### The defensible variant — B′

Use the TIMES **annual** final energy per carrier, and shape it with **PyPSA's
own** hourly heat profile (divided by the hourly COP for the heat-pump share).
That is implementable. But then two objections remain:

1. **Static loads on fuel buses break CO₂ accounting.** In PyPSA-Eur a gas
   boiler emits via `bus2 = co2 atmosphere` on the *Link*. A `Load` on the gas
   bus emits nothing. The correct implementation is therefore not "replace by
   Loads" but "keep the Links and fix their dispatch"
   (`p_min_pu = p_max_pu = profile`, `p_nom` fixed) — which is Option C with an
   hourly equality instead of an annual one.
2. **It throws away the flexibility that motivated the coupling.** Fixing hourly
   dispatch removes thermal storage, heat-pump load shifting, and any response of
   Walloon heating to the power system. The heat pumps become an inflexible
   electricity load with a shape PyPSA imposed on itself. Given that "PyPSA has
   a much better time resolution, which we should take profit of" is the premise
   of the exercise, freezing the hourly dispatch is self-defeating.

### Verdict

**Reject in the literal form** (data does not exist). **B′ is feasible but
strictly dominated by Option C**, which achieves the same mix transfer while
keeping the hourly degrees of freedom.

---

## 6. Option C — TIMES annual energy mix as a constraint *(recommended)*

### What it would do

Keep every PyPSA heating component exactly as it is — extendable, hourly,
COP-driven, with storage. Add one linear constraint per technology group in
`custom_extra_functionality`:

```
Σ_t  w_t · (heat injected into BEWAL heat buses by technology g at t)  =  E_g^TIMES
```

where `E_g^TIMES` is the TIMES annual heat *output* of group `g` (already
exported today, per technology, in `wallon_demands_*.csv` — the 23 child
categories such as `residential rural gas boiler`, `services heat pump`, …).

Groups should be defined on the **sum of rural + urban decentral**, which
cancels the labelling artefact of §1.2(d), and on the technology axis only,
which is the axis PyPSA can actually represent after `cluster_heat_buses`:

| Constraint group | TIMES categories summed | PyPSA carriers |
|---|---|---|
| gas boiler | `residential {rural,urban decentral} gas boiler` + `services gas boiler` | `{rural,urban decentral} gas boiler` |
| oil boiler | … `oil boiler` | `{rural,urban decentral} oil boiler` |
| biomass boiler | … `biomass boiler` | `{rural,urban decentral} biomass boiler` |
| heat pump | … `heat pump` + `… geothermal` | `{rural,urban decentral} {air,ground} heat pump` |
| resistive | … `electric heater` + `services electric heater` | `{rural,urban decentral} resistive heater` |
| solar thermal | … `solar thermal` | `{rural,urban decentral} solar thermal collector` |
| ~~district heating~~ | `residential district heating` + `services district heating` | **excluded** — demand-only transfer, see *Scope* below |

### Scope: the constraint must stop at the decentral heat buses

The obvious extension — apply the same constraint on `BEWAL urban central heat`
so district heating gets the TIMES supply mix too — is **not well-posed**. Four
independent reasons, all verified in §2.5 / §3.1:

1. **DAC dominates the bus.** 2050: injections 8.980 TWh, DH load 2.693 TWh, DAC
   withdrawal 4.138 TWh. Any constraint phrased as "technology *g* supplies share
   α of district heat" is either vacuous or is secretly a cap on DAC — a
   decarbonisation lever that has nothing to do with the heating soft-link.
2. **CHP heat is rigidly welded to CHP electricity.** Because
   `add_chp_constraints` is dead code, `heat = 3.055 × electricity` for the
   biomass CHP with no slack. Constraining CHP heat to a TIMES value *is* a
   constraint on Walloon power generation — pushing the heating soft-link into
   the sector where PyPSA, not TIMES, is the authority. That inverts the whole
   rationale for the coupling.
3. **Storage re-injects.** Chargers and dischargers are separate Links on the
   same bus; in 2050 the pits cycle 2.144 in / 2.079 out, so 23 % of all
   "injections" are re-injections of heat already counted once.
4. **The TIMES answer is not expressible.** 73 % of TIMES's 2050 DH supply
   (geothermal + industrial waste heat) has no PyPSA component to constrain.

None of these apply to the decentral buses. Verified component census of
`BEWAL rural heat` and `BEWAL urban decentral heat`, all horizons — the *only*
things touching them are:

```
supply : {air,ground} heat pump, gas boiler, oil boiler, biomass boiler,
         resistive heater, solar thermal collector          ← constrain these
storage: water tanks charger/discharger  (net ≈ 0; 0.006 TWh gross in 2050)
sinks  : the heat Load, heat vent (~1e-5 TWh), DAC (0.011 TWh on urban decentral)
```

No CHP, no PTES, no waste heat, and DAC is 0.08 % of the load. So the constraint
should be written as

```
Σ_t w_t · heat_g,t  ⋛  E_g^TIMES        for g ∈ {heat pump, gas boiler, oil boiler,
                                                 biomass boiler, resistive, solar thermal}
```

summed over `rural + urban decentral`, **excluding** `*water tanks charger`,
`*water tanks discharger` and `*heat vent`. The right-hand sides sum to the
decentral heat load to within the cooking-fuel and agriculture-heat additions
already made by `write_wallon_heat_demands` (0.62 TWh in 2050), which is why the
slack/inequality treatment below matters.

District heating keeps its present treatment: **demand transferred, supply left
to PyPSA**, with the caveat recorded that the two models disagree structurally
about what supplies it (§3.1, §8 issues 8–10).

### Why this is the right quantity to transfer

TIMES's genuine added value is the **choice of appliance**, made with dwelling
archetype, retrofit state and vintage detail PyPSA does not have. That choice
expresses itself as an *energy* split, not a capacity split — and, as §1.2 shows,
the TIMES capacities are a mechanical by-product of the energy anyway
(`activity / 1314 h`). Constraining the energy transfers the information; the
capacities then fall out of PyPSA's own peak-consistent sizing.

Conversely, PyPSA's genuine added value is *when* each appliance runs, at what
COP, with what storage, against what electricity price. Option C leaves all of
that free.

### Assessment

**Robustness.** High. It constrains exactly the quantity TIMES optimised, with
no unit conversion (both sides are MWh thermal delivered to the heat bus), no
dependence on the urban/rural artefact, no dependence on the 1314 h availability
assumption, and no dependence on the residential/services split that
`cluster_heat_buses` destroys.

**Implementation difficulty.** Moderate — the highest of the three, but bounded.
`custom_extra_functionality` is an empty stub and receives `(n, snapshots,
snakemake)`, so it has the network and the config. The constraint is a weighted
sum over `n.model.variables["Link-p"]` for a carrier subset — a dozen lines with
`linopy`. The work is in the plumbing:

* a new `heating_targets_{year}.csv` (or an extra column in `wallon_demands`)
* wiring it as an input to `solve_sector_network_myopic` in
  `rules/solve_myopic.smk` (and to `add_brownfield`, which currently runs before)
* handling the heat-pump reversed-link sign convention (heat injection is
  `−p0`, `bus0` is the heat bus)
* handling solar thermal, which is a Generator, not a Link
* an `include_existing`-style treatment: previous-vintage links are
  non-extendable but still dispatch, so their output counts toward the target

**Risks and how to manage them.**

* *Over-determination.* Six equalities plus the heat balance over-constrain the
  system if the TIMES totals do not sum exactly to the TIMES heat demand PyPSA
  was given. They should — both come from the same extraction — but rounding,
  the `services other fuel` / `residential cooking` additions in
  `write_wallon_heat_demands`, and the agriculture-heat re-bussing all inject
  small mismatches. **Mitigation:** constrain *shares* of the realised heat
  supply rather than absolute energies, or leave one technology (the largest)
  unconstrained as the slack.
* *Infeasibility at peak.* Not expected: capacities stay extendable, and a
  technology forced to deliver 37 % of annual heat can always be given enough
  `p_nom`. But an equality on a technology whose `p_max_pu` is bounded (solar
  thermal) can be infeasible. **Mitigation:** inequality (`≥` for the fuels
  TIMES keeps, `≤` for heat pumps) instead of equality, which also reads more
  honestly as "TIMES says the transition is at most this fast".
* *Shadow prices become the diagnostic.* The dual of each constraint is exactly
  "what it costs PyPSA to accept the TIMES mix". That is a genuinely useful
  output for the TIMES↔PyPSA reconciliation discussion, and neither A nor B
  produces it.

**Quality of the resulting soft-link.** Best of the three. TIMES determines *what*
serves Walloon heat; PyPSA determines *when*, *how much iron*, and *how it
interacts with the power system*. Neither model is asked to do the other's job.

### Verdict

**Recommended.**

---

## 7. Comparison and recommendation

| | **A** — `p_nom_min` | **B′** — fixed hourly dispatch | **C** — annual energy constraint |
|---|---|---|---|
| Transfers the TIMES appliance mix | **No** | Yes | Yes |
| Keeps PyPSA hourly flexibility | Yes | **No** | Yes |
| Needs TIMES sub-annual data | No | Yes (**does not exist**) | No |
| Unit conversions required | th→el (COP), th→fuel (η) | th→fuel, th→el | **none** |
| Depends on urban/rural label artefact | Yes | Yes | No (sum over both) |
| Depends on the 1314 h assumption | **Yes** | No | No |
| Survives `cluster_heat_buses` | Partly | Partly | Yes |
| CO₂ accounting stays correct | Yes | Only if links are kept | Yes |
| Cost distortion | **≈ +0.6 bn EUR/a** | none by construction | dual-priced, visible |
| Implementation effort | Low | High | **Moderate** |
| Produces a reconciliation diagnostic | No | No | **Yes (shadow prices)** |
| Safe on the **decentral** heat buses | — | — | **Yes** (no CHP, storage ≈ 0, DAC 0.08 % of load) |
| Safe on the **district-heating** bus | No (same CHP/DAC problems) | No | **No** — excluded by design (§6 *Scope*) |

### Recommendation

1. **Adopt Option C** as the heating soft-link mechanism, with **inequality**
   constraints in the first implementation (`≥` on the fuel-based technologies,
   `≤` on heat pumps) and a slack technology, then tighten to equalities once the
   balance is shown to close.

2. **Reuse the TIMES capacities for the base year only.** §3 shows PyPSA's
   2025 stock composition is broadly right but its *vintage structure* lets it
   greenfield 2.5 GW of heat pumps in the base year. Replacing
   `build_existing_heating_distribution`'s BEWAL row with the TIMES 2025
   capacities (corrected — see §8) is the one use of `heating_capacities_*.csv`
   that is both defensible and already flagged as the "one remaining unconsumed
   soft-link output" in `times_data_extraction.md`. It is a *stock* statement,
   which is exactly what a capacity number is good for, and it does not pretend
   to constrain the future.

3. **Do not pursue Option B.** Record in the docs why: TIMES-WAL has no
   sub-annual heat representation, so there is nothing to import.

4. **Scope Option C to the decentral heat buses.** District heating keeps its
   present demand-only transfer. Extending the constraint to
   `BEWAL urban central heat` would cap DAC, would constrain Walloon power
   generation through the welded CHP ratio, would double-count PTES
   re-injections, and could not express 73 % of the TIMES answer anyway (§6
   *Scope*, §3.1). If the DH supply mix is judged important enough to reconcile,
   the prerequisite is **modelling work, not constraint work**: enable a
   geothermal heat source and add an industrial-waste-heat link for BEWAL, then
   revisit. That is a separate decision, listed as an open point in §9.

---

## 8. Prerequisites — data-quality fixes that block any option

| # | Issue | Where | Impact |
|---|---|---|---|
| ~~**1**~~ | ~~**1.5–8.6 % of Walloon appliance heat never reaches PyPSA**~~ **FIXED 2026-08-01** (§10). Cause confirmed and closed: **18 processes producing a `Heat` commodity were absent from `mapping_processes.csv`** (missing rows, not empty cells), plus `CHSADUM-DEM` labelled `other demand` — a label no heat rule lists. 15 of the 18 *were* in `AllProcesses.csv`, i.e. the mapping file simply lagged the `.vd`. Two of them (`RHN3FLOGN2`, `CHENELC201`) are non-zero **only in 2045** and were invisible to a 2025/2030/2040/2050 spot check. | `TIMES_PyPSA/data/mapping_processes.csv`, `extraction_rules.csv` | **was** the current demand soft-link and every option below; now closed, with CI guards |
| 2 | `VAR_Cap + VAR_Ncap` double-counts installed capacity by 36–65 % | `TIMES_PyPSA/times_pypsa/pipeline.py:956` | any capacity use (Option A, recommendation 2) |
| 3 | Index filter `boiler\|heat pump\|stove\|thermal\|heater` admits `Geothermal (IND)` and `Thermal Public - Retrofitting CCGT CCS`, drops `District heating` | same file, `:969-972` | same |
| 4 | `RH3FLPGN2` (an LPG boiler) is labelled `Residential urban decentral oil heater` | `TIMES_PyPSA/data/mapping_processes.csv` | mis-assigns fuel in any mix constraint |
| 5 | The `commercial other` / "40 % understated services heat" caveat in `extraction_rules.csv` is **stale** for this `.vd` — no `commercial other` process outputs a heat commodity, and `Commercial electrical stove` now carries the 5.42 PJ | `TIMES_PyPSA/data/extraction_rules.csv`, `aggregation.md` | misleading documentation |
| 6 | TIMES water heating is 13.1–13.4 % of useful heat and is not transferred separately; `write_wallon_heat_demands` rescales space + water with one factor | `scripts/prepare_sector_network.py:3948-3953` | second-order, but TIMES has the split (`RW*`/`CW*`) and PyPSA has the buses |
| 7 | `retrofitting.retro_endogen` must stay `false`, otherwise PyPSA retrofits a demand TIMES has already retrofitted (18.5 PJ in 2050) | `config/config.default.yaml:820` | silent double count if ever enabled |
| **8** | **`add_chp_constraints` is dead code.** Defined at `solve_network.py:1151`, called from nowhere (verified: the only occurrence of the name in the repo is its own `def`), and written against the legacy two-link CHP formulation so it could not match the current multi-output links even if wired in. `c_v` and `p_nom_ratio` are read by nothing. Every PyPSA CHP is therefore a rigid back-pressure unit. It also has a latent `NameError` (`rhs` undefined at `:1202` when `electric_fix` is empty). | `scripts/solve_network.py:1151-1202` | not a blocker for the recommended scope, but it is why the DH bus cannot be constrained, and it silently removes CHP flexibility everywhere in the model |
| **9** | **Solid-biomass CHP creates energy**: `efficiency` 0.2652 + `efficiency-heat` 0.8294 = **1.0946**. Inherited from the pinned technology-data archive; no override in `data/walloon/custom_costs.csv` and no row in `config/input_parameters_for_models.csv`, so the TIMES and PyPSA CHP assumptions have never been reconciled. | `resources/<run>/costs_<y>_processed.csv` | biases any MWh-based energy accounting on the DH bus by ~9 %; should at minimum be added to the shared-parameter table |
| 10 | **The district-heating distribution loss is charged to nobody.** PyPSA builds the DH load with a ×1.15 uplift, then `write_wallon_heat_demands` rescales the profile to the TIMES *delivered* heat, cancelling it; TIMES's own ~8 % loss sits upstream in `RSDHET0x` and is not exported. ~0.4 TWh unaccounted in 2050. | `scripts/prepare_sector_network.py:3149` vs `:3957-3961` | second-order; fix by targeting TIMES's network *input* rather than its output |
| 11 | TIMES's 2050 DH supply is 52 % geothermal + 21 % industrial waste heat; PyPSA-Wal can instantiate neither (`heat_pump_sources.urban central: [air]`, no industrial-waste-heat link, `municipal_solid_waste: false`) | `config/config.default.yaml:706-708`, `:952` | blocks any future DH *supply* soft-link; harmless for the recommended scope |

### Issue 1 in detail — the 16 unmapped heat producers (PJ)

| Process | 2025 | 2030 | 2040 | 2050 | in `AllProcesses.csv`? |
|---|---:|---:|---:|---:|---|
| `RH2FPELN2` (pellet boiler, 2F space heat) | — | — | 2.957 | **4.391** | yes |
| `RW4FPELN3` (pellet water heater) | 0.677 | 1.401 | 1.307 | — | **no** |
| `RW2FPELN3` | 0.478 | 0.912 | 0.912 | — | **no** |
| `RWAPPELN3` | 0.264 | 0.481 | 0.481 | — | **no** |
| `CHBAGEO101` / `CHBPGEO101` / `CHCOGEO101` / `CHENGEO101` (tertiary geothermal) | — | 0.903 | 0.903 | 0.545 | yes |
| `CWSAGEO101` / `CWNBAGEO101` / `CWNENGEO101` | — | — | — | 0.341 | yes |
| `RHN{2F,4F,AP}LOGN2`, `RHN3FGMXN2`, `RWN2FGMXN3` (outputs land on `RWN*`) | — | — | 0.457 | — | yes / no |
| **Total unmapped** | **1.42** | **3.70** | **7.02** | **5.28** | |
| *(memo: leak measured from the balance)* | *1.44* | *3.20* | *7.68* | *5.28* | |

The two rows agree in 2025 and 2050 and differ by 0.5–0.7 PJ in 2030/2040. The
residue is `CHSADUM-DEM` ("Commercial dummy tech from CHP heat to CH", 0.82 PJ in
2025 / 0.67 PJ in 2040), labelled `other demand` and read by no rule either —
plus `RHN3FLOGN2` and `CHENELC201`, non-zero only in 2045. All are now mapped.

For context, **1 013 of the processes appearing in this `.vd` have no row in
`mapping_processes.csv`** at all. Most are emissions/dummy processes that never
carry energy — but the heat leak showed the assumption was not safe, so the check
now runs across all sectors (§10). Building heat is clean; **industry and the
power sector are not** (see §10, *what the new checks still report*).

---

## 9. Open points and things I could not resolve

* **The 1314 h availability factor is an inference.** It is consistent across 25
  process groups and 4 horizons, but the `.vd` carries results only. Confirm
  `AFA`/`AF` for the residential and commercial heating templates with the TIMES
  modellers — if it is a placeholder rather than a considered value, that is
  itself worth reporting back, and it would settle whether TIMES capacities have
  any physical meaning.
* **The timeslice definition is outside the `.vd`.** `S01…S10` are not in
  calendar order (S05–S07 are summer by PV output, S01/S02/S09/S10 winter by
  heat-pump load). If a future need for TIMES sub-annual data arises, the
  `G_YRFR` table and the hour→slice assignment must be requested from the VEDA
  model. Not needed for Option C.
* **Why the urban/rural labels were assigned as they were.** The pattern
  (legacy `100`/`N1` → rural, newer `N2`/`N4` → urban decentral) looks incidental
  rather than intentional. Worth one question to whoever wrote
  `mapping_processes.csv` before building anything that depends on the split —
  the recommendation in §6 avoids depending on it, deliberately.
* **Whether the unlabelled processes of §8 issue 1 are an oversight or a
  deliberate exclusion.** They look like an oversight — `RH2FPELN2` is a plain
  pellet boiler sitting next to `RH2FPELN3`, which *is* labelled — but confirm
  before adding labels, because 4.4 PJ moving into `residential urban decentral
  biomass boiler` changes the biomass balance PyPSA has to source from its wood
  potential.
* **Is the DAC-on-the-district-heating-bus result intended?** In 2050 DAC pulls
  4.14 TWh_th from `BEWAL urban central heat` — more than the district-heat load
  — and is what justifies the 7 303 MW / 181 GWh pit store and most of the
  729 MW heat pump. That may be a legitimate result of the CO₂ budget, or an
  artefact of DAC having free access to a bus sized for buildings. Either way it
  should be understood before anyone reads the BEWAL district-heating results as
  a district-heating answer. **Not investigated here.**
* **Whether to reconcile the district-heating supply mix at all.** Doing so is a
  modelling decision, not a soft-linking one: it needs a geothermal heat source
  and an industrial-waste-heat link for BEWAL (§8 issue 11). The prior question
  is whether TIMES's 52 %-geothermal 2050 district heat is a considered Walloon
  resource assessment or a modelling placeholder — `RENGEO` appears from 2040
  only and grows to 5.53 PJ. **Ask the TIMES modellers before building anything.**
* **Should `add_chp_constraints` be revived?** Independently of the soft-link, a
  back-pressure CHP with no `c_v` operating region is a modelling simplification
  nobody appears to have chosen deliberately (§8 issue 8). Fixing it would give
  the DH bus enough freedom that a supply-mix constraint might become well-posed
  later — but it changes power-sector results, so it is not a side-effect to slip
  into a heating PR.
* **Not investigated:** whether the TIMES *cost* assumptions for heating
  appliances match `data/walloon/custom_costs.csv`. If PyPSA's heat pumps are
  cheaper or its gas more expensive than TIMES's, part of the §3 divergence is a
  parameter inconsistency rather than a structural one, and should be fixed in
  `config/input_parameters_for_models.csv` *before* constraining the mix. This is
  the natural next piece of analysis, and it could change how tight the Option-C
  constraints ought to be. The CHP parameters (§8 issue 9) are in the same
  situation and are not in the shared table at all.

---

## 10. The demand leak — fixed 2026-08-01

Issue 1 of §8 is closed. This section records what was wrong, **why the QA tool
did not catch it**, and what now guards against a repeat. All changes are in the
`TIMES_PyPSA` repository; pypsa-wal reads them through the editable install.

### 10.1 What was wrong

| # | Defect | Energy |
|---|---|---:|
| 1 | 18 processes producing a building `Heat` commodity had **no row** in `mapping_processes.csv`, so `process_agg` was blank and no rule could match them | up to 7.02 PJ (2040) |
| 2 | `CHSADUM-DEM` — the heat leg of the on-site tertiary gas CHP (`CHSAGMXCHPN01_N` → `CHSADUM` → `CHSA`) — carried `other demand`, which no heat rule lists | 0.82 PJ (2025), 0.66 PJ (2040) |
| 3 | `CHBAGEO100` carried `Commercial gas boiler`; `GEO` is geothermal and its four `CH*GEO100` siblings were all `commercial Geothermal` | 0.0002 PJ (label correctness) |

Labels were assigned from the convention already implicit in the file, which is
systematic on the archetype axis (§1.2(d) called the urban/rural split an
artefact; it is at least a *consistent* artefact):

> **2F and AP → `urban decentral` (34/34 and 32/32); 3F and 4F → `rural`
> (26/35 and 27/34).** Fuel → technology: `PEL`/`LOG` → biomass, `GMX` → gas,
> `GEO` → geothermal, `SOL` → solar thermal, `ELC` → electric, `ELCHPN` → heat
> pump, `OIL` → oil, `COA` → coal.

Every added process either matches its own sibling exactly or follows this rule.
The two genuinely ambiguous cases (`RHN4FLOGN2` 0.20 PJ, `RHN3FGMXN2` 0.06 PJ)
went with the archetype and are individually negligible.

`CHSADUM-DEM` got a new label `Commercial CHP heat` and a new child rule
`services CHP heat` under `BEWAL services urban decentral heat`. Its gas input is
not exported, so measuring the useful-heat output is consistent with every other
appliance rule and cannot double-count.

### 10.2 Why the QA tool reported it clean

This is the more important half. **Every QA check in the library was
rule-relative** — it compared the extraction rules against themselves, never
against the `.vd`:

| Check | Compares | Why it was blind |
|---|---|---|
| `export_reconciliation` | *tagged* ↔ *coloured* | both downstream of tagging; a flow no rule matched is in **neither** column. It reported `Residential 26.273 / 26.273, gap −1e−13` while 7.7 % of residential heat was missing |
| `parent_child_sum_checks` | rule total ↔ Σ rule totals | a process in neither the parent nor any child list sums to zero on **both** sides. All four rows read `ok=True` |
| `qa_coverage_gap` | unmatched `VAR_FIn`, demand sectors, `process_type == DMD` | every heat rule is `measure_at = service_output`, i.e. **`VAR_FOut`** — the wrong axis entirely. All 18 processes are `PRE`, not `DMD` |
| `double_count_matrix` | rule key ↔ rule key | only detects energy matched **twice**, never zero times |

Two further amplifiers:

* **The sector filter dropped the worst cases.** `qa_coverage_gap` requires
  `sector ∈ {RSD,COM,IND,TRA,AGR}`, but a process absent from
  `mapping_processes.csv` has *no sector*. `RW2FPELN3`, `RW4FPELN3`, `RWAPPELN3`
  and `RWN2FGMXN3` were excluded by the very filter meant to focus the check.
* **The surviving traces were framed as noise.** The `_all` variant *did* contain
  the smoking-gun rows (blank `process_agg`: `RSD, ⌀, Wood Pellets…, PRE, 0.89
  TWh`), but it was written to CSV and never rendered; the HTML said *"Most of
  this is legitimately excluded downstream consumption"* and the visible table's
  top row was a 21.65 TWh structural non-export. The reader is trained to skim it.

### 10.3 Why the Sankey did not show it either

It *was* drawn — as **14 grey ribbons landing on `Buildings: built area`** in
2040, among 25 correctly coloured siblings (largest: `Pellets
Boiler.HeatHotwater New-RH2F-New2`, 2.32 PJ; then `RW4FPELN3` 1.02, `RW2FPELN3`
0.71, `other demand` 0.52). Four reasons the eye slid past them:

1. **Grey is the diagram's default and correct state.** The entire upstream
   supply chain is grey, so an omission at a demand node is visually identical to
   ordinary context. Colour encoded *export status*, not *correctness*.
2. **Four ribbons carried no label at all** — just a raw TIMES code
   (`RW4FPELN3`) — because the process was in neither mapping CSV, so there was
   no description to render. An unlabelled node reads as plumbing.
3. The others carried **raw TIMES descriptions** rather than the friendly
   aggregate names, so they did not look like siblings of the coloured appliances.
4. Each was 0.2–2 % of the diagram, and **no number anywhere summed the grey
   inflows to a demand node.** The eye does not integrate 14 thin ribbons.

### 10.4 What now guards it

Three new checks, all comparing the rules against the `.vd`, all run over
**every** year in the report (the leak peaked in 2040, and two processes were
non-zero only in 2045 — a latest-year headline would have missed both):

| Guard | What it asserts | Artefact |
|---|---|---|
| `unmapped_process_report` | no process carrying energy has a blank `Aggregation Level 2`; splits `missing_row` from `blank_label` | `qa_unmapped_processes_{year}.csv` |
| `service_output_coverage` / `_gap` | for every carrier declared by a `service_output` rule, Σ produced == Σ exported, keyed on the **commodity's** sector (an unmapped process has none) | `qa_service_output_{coverage,gap}_{year}.csv` |
| `flag_leak_suspects` | a grey Sankey ribbon whose siblings into the same node on the same commodity *are* soft-linked is drawn **orange** | the Sankeys themselves |

Both tabular checks are **scoped to the carriers the rules actually claim to
transfer as a service output** (`Heat`, discovered automatically from the
`carrier` column). Unscoped, the coverage check reported ~280 PJ of by-design
exclusions and the Sankey flag painted 541 ribbons orange — re-creating exactly
the cry-wolf problem that made the old coverage-gap table unreadable.

They feed a red/amber **Extraction integrity** block placed *above* the Sankeys
and above every rule-by-rule table, and grade the headline verdict:
a service-output gap is `DEFECTIVE`; an unmapped process alone is
`PARTIALLY ADEQUATE`.

Regression suite: `TIMES_PyPSA/tests/test_service_output_closure.py` (16 tests).
Four of them fail on the pre-fix mappings and pass after, so they are real
guards, not documentation. The data-only tests pin all 18 process labels by code,
so a future mapping rewrite that drops one fails loudly.
### 10.5 Full audit of the remaining unmapped processes (2026-08-01)

The new `unmapped_process_report` surfaced 34 further processes in
`scen_demande_haute` with no `Aggregation Level 2` label. **Every one was checked
individually. None of them is a soft-link leak.** The governing principle is that
the soft-link transfers TIMES **demands**, not TIMES **generation**:

| Group | n | Why it is not a leak |
|---|---:|---|
| Industry fuel consumers (`ICOSTM*`, `IQRMCH*`, `IBOHTH*`, `ISGHTH*`, …) | 28 | Every industry fuel rule is `fuel_input` measured at the **fuel-tech gateway** (`Fuel Tech - Electricity (IND)` → `INDELC`, etc.). Downstream consumers are excluded *by design* — exporting them too would double-count. Verified: the gateway's own input is 44–100 % exported in every case. |
| Power generation (`ETSTP_NUC-LWR-SM_NUC_N`, 137 PJ in 2050) | 1 | PyPSA optimises Walloon generation itself; no rule exports TIMES electricity supply. |
| H₂ production (`SELCH2EC02`, `SELCH2PEM01`) | 2 | The `hydrogen` rule measures the **delivery** tech's output, one hop downstream. |
| Methanation waste heat (`CO2CTOMETHELC`) | 1 | Feeds `ELCHET` → district heating, whose *delivered* heat is exported at the substation. |
| Primary resource (`MINRENMINGEO`) | 1 | Upstream of geothermal appliances whose output is exported. |

> An earlier note in this file guessed the industry rows were "probably a smaller
> industrial analogue of the heat leak". **That guess was wrong**, and the
> gateway-metering check above is what disproves it.

They were nonetheless **labelled**, because an unmapped process draws an
anonymous Sankey node named after its raw TIMES code — and the Sankey is the
primary human check on the soft-link. Every label reuses an existing node, so
nothing was multiplied. The result is a large simplification, not a growth:

| Sankey level | 2050 nodes | 2050 links |
|---|---|---|
| `Aggregation Level 2` | 131 → **109** | 933 → **698** |
| `custom` | 82 → **72** | 183 → **165** |
| `sankey_overview` | 22 → **13** | 82 → **57** |

**Every exported category is bit-identical before and after** — verified for all
eight horizons. Labelling changed what the diagram draws, nothing that PyPSA reads.

#### Two mislabels found while choosing the labels

* **`ETSTP_NUC-LWR-GEN3_NUC_N` (Generation III reactor) read `Gas power plants`.**
  In 2050 that node contained *nothing but* the nuclear reactor — the Sankey has
  been drawing ~137 PJ of new nuclear as gas generation. Both new-build nuclear
  processes now carry `Nuclear power plants` (the only added node; `custom` and
  `sankey_overview` stay `Power plants`, so the two coarser views are unchanged).
* **`SELCH2EC01` (large alkaline electrolyser) sat in `Fuel Tech - H2`**, which is
  the **road** H₂ delivery group and *is* read by the `total road` rule — whose
  commodity scope is carrier-**or**-code and includes `Electricity`. A grid-fed
  electrolyser there has its electricity exported as road transport fuel. It
  contributes 0 PJ in the reference scenario, so the correction is provably
  zero-impact here, but it was live for any scenario building that unit. H₂
  *producers* now sit on `SUP_PRE_PJ_GW` / `H2 production`; `Fuel Tech - H2` holds
  only the delivery/storage chain.

### 10.6 The other scenarios were not clean — swept and fixed

`scen_demande_haute` is only one of the scenarios in
[`config/scenarios.walloon.yaml`](../config/scenarios.walloon.yaml). Sweeping
**every** `.vd` in `TIMES_PyPSA/data/` found 32 more unmapped processes and real
service-output gaps in three other scenarios. All are now labelled from their own
siblings; the export effect per scenario:

| Scenario | service gap before → after | export changes |
|---|---|---|
| `scen_demande_haute` | 0 → 0 | **none** (already clean) |
| `scen_corrige` | 0 → 0 | none (label only) |
| `scen_base` | 0.51 → 0 PJ | services heat +0.17…+0.21 PJ; `retro` +0.49 PJ (2050) |
| `scen_base_coherence` | 0.31 → 0 PJ | services geothermal +0.30 PJ; **`total road` +1.5…+4.0 PJ** |
| `scen_alternatif` | **2.78 → 0 PJ** | **residential biomass +2.10 PJ**, services geothermal +0.67 PJ |

After this, **all nine local `.vd` files report zero unmapped processes and zero
service-output gap in every horizon.**

The `total road` movement in `scen_base_coherence` is the one change with a
modelling consequence: `TRAGH2C02_I` / `TRALH2C02` are genuine road-H₂ delivery
techs whose mapped siblings were already exported, so including them is
consistent — but it does raise a soft-linked transport demand.

### 10.7 Open — a third blind-spot class

**14.1 PJ of imported road hydrogen is still not exported** (`scen_base_coherence`,
2050). `TRAGH2C02_I` delivers road H₂ from `IMPH2` (imported hydrogen), but
`imported hydrogen` is not in the `total road` rule's carrier list, so only the
compression electricity is picked up. The synthetic route (`SYNH2CT`) *is* listed,
so the two routes are metered asymmetrically.

This is a **third** defect class, and neither new check covers it:

| Blind spot | Caught by |
|---|---|
| process not in `mapping_processes.csv` | `unmapped_process_report` ✅ |
| service output no rule measures | `service_output_coverage` ✅ |
| **`fuel_input` rule whose carrier list omits a carrier its own process group consumes** | **nothing** ❌ |

A prototype check for it (compare each rule's matched process group against the
carriers it actually consumes) was written and **rejected**: it is swamped by
correctly-excluded CO₂ commodities and by rules that deliberately span a
multi-fuel process group, so it would cry wolf exactly like the old coverage-gap
table. Fixing the specific case means adding `imported hydrogen` to the
`total road` carrier list — a modelling decision, not a mapping fix, and it only
affects a scenario that is not currently run. **Left open deliberately.**

### 10.8 Operational: Snakemake now rebuilds on a mapping change

`rules/build_sector.smk::build_wallon_demands` declared only `times_file` as an
input, so editing a mapping did **not** invalidate `wallon_demands_*.csv` and
Snakemake reused stale demands. Fixed: `times_mapping_files()` now declares
`mapping_processes.csv`, `mapping_commodities.csv` and `extraction_rules.csv`,
resolved from `sector.times_mappings_dir` or the installed `times_pypsa`. Verified
— after the mapping change Snakemake reports

```
reason: Updated input files: …/mapping_processes.csv, …/extraction_rules.csv
```

and rebuilds all four horizons by itself.

> **Not a bug:** an earlier note here reported
> `snakemake --configfile … <target>` failing with *"Config file must be given as
> JSON or YAML with keys at top level"*. `--configfile` takes `nargs="+"`, so
> targets written immediately after it are swallowed as extra config files. Put
> `--cores` (or any flag) between the config file and the targets. Recorded in
> [`instructions.md`](../instructions.md) troubleshooting.
