# CCGT with carbon capture in PyPSA-Wal

**Date:** 2026-08-25
**Purpose:** record whether a combined-cycle gas turbine with post-combustion
capture (CCGT-CC) can live in this fork, which parameters it needs, how that
compares to the Allam cycle, what other PyPSA projects already do, and where
the generic values wired on 2026-08-25 can be changed.
**Wired into:** `sector.ccgt_cc` (on in `config/config.walloon.yaml`, off in
`config/config.default.yaml`) → `scripts/prepare_sector_network.py`
(`add_ccgt_cc`). DAC is **off** in the same Walloon overlay (`sector.dac:
false`) because TIMES does not have it.

This is **new-build only**. Existing Walloon TGVs stay unabated. Overnight
EUR/kW_e is **not** a single TIMES/PyPSA cell yet — the Link is composed from
the CCGT row plus a DEA capture sheet. Fill
`config/input_parameters_for_models.csv` when both models agree a dedicated
figure; until then do not `--write` those placeholder rows.

---

## 1. Is it possible?

Yes, and the code path is the same one PyPSA-Eur already uses for coal CCS,
urban-central gas CHP CCS, and methanol-CCGT CCS. Unabated CCGT is already a
three-bus Link (gas → electricity, all CO₂ to `co2 atmosphere`). Capture adds a
fourth bus to the stored-CO₂ network.

It was **not** a config switch before this change. The shared TIMES/PyPSA table
already had empty rows for *Centrale à cycle combiné avec captage et stockage
de CO₂*, with the note that PyPSA does not treat CCS as part of a gas turbine.
That note is now outdated: the technology is wired, still on generic costs.

Do not confuse `sector.ccgt_cc` with `sector.methanol.methanol_to_power.ccgt_cc`.
The methanol flag is a **methanol-fired** CCGT with capture and stays `false`.

Two other gas-CCS options were already in the tree:

| Option | What it is | Switch |
|---|---|---|
| Urban central **gas CHP CC** | CCGT-like CHP + amine capture, heat to district heating | on whenever `sector.chp.enable` (default) |
| **Allam cycle** (oxy-fuel, ~98 % capture) | integrated CCS gas plant | `sector.allam_cycle_gas` (default **false**) |

CO₂ transport, storage and a sequestration cap are already in the Walloon run.
Captured CO₂ from CCGT-CC uses that stack. **DAC is off** in Wallonia
(`sector.dac: false`) — it is on in `config.default.yaml` (PyPSA-Eur default)
and was taking more 2050 district heat than buildings in earlier solves. See
§8.

---

## 2. Typical techno-economics (CCGT-CC vs Allam)

Order-of-magnitude, LHV, ~EUR2025, 2030-ish. Unabated CCGT is the baseline
both options sit on. These numbers guided the generic implementation; they are
**not** the solver inputs (those are composed from the cost table, §4).

| | **Unabated CCGT** | **CCGT + post-combustion CC** | **Allam (oxy-fuel sCO₂)** |
|---|---|---|---|
| What it is | Standard combined cycle | Same plant + amine scrubber on the stack | New cycle: combusts gas in O₂, working fluid is CO₂ |
| Capture rate | 0 | **90–95 %** | **97–100 %** (PyPSA hard-codes **98 %**) |
| Residual CO₂ | ~330 g/kWh_e | ~20–40 g/kWh_e | ~0–10 g/kWh_e |
| Net electrical efficiency | **58–63 %** (this repo 58–60 %) | **50–56 %** (~7–10 pp penalty; steam to the reboiler is most of it) | **50–56 %** independent studies; vendor claims ~59 %; PyPSA **60 %** (optimistic) |
| Overnight investment | **~1 100 EUR/kW_e** (DEA / this repo) | **~1 700–2 200 EUR/kW_e** (~+60–100 %). NETL ~2× the unabated plant | **Wide: ~1 000–2 500 EUR/kW_e**. PyPSA **1 886** (own guess). PoliMi 2024 sizing: **2 490 €/kW**, ~20 % *below* their NGCC+CCS benchmark |
| FOM | ~3.3 %/year of CAPEX | Plant ~3.3 % + capture ~3 % | Not in technology-data; expect similar or a bit higher (ASU + sCO₂ kit) |
| VOM | ~5.3–5.6 EUR/MWh_e | Plant VOM **plus** ~3 EUR/tCO₂ solvent (~+1 EUR/MWh_e) | PyPSA **2.5 EUR/MWh_e** (TODO, likely low). ASU power is in the efficiency, not VOM |
| Lifetime | 25 years (DEA) | 25 years plant; capture train similar | PyPSA **30 years** (assumption) |
| CO₂ delivered | none | ~atmospheric then compressed | Already dense / near pipeline spec |
| Flexibility | Excellent (minutes, ~30 % min load) | Capture train **slows ramps**; can bypass the scrubber | **ASU is slow** (hours). O₂ storage can help. Part-load weakly demonstrated |
| Retrofit existing TGVs | — | **Yes** (steam extraction + absorber) | **No** — different machine |
| TRL / commercial | 9 | Capture **7–8** (amine commercial; few full-scale gas plants) | **~6–7** (La Porte demo; first commercial plants not running yet) |
| In pypsa-wal | Default, with 1 740 MW BEWAL floor | **On** (`sector.ccgt_cc: true`) | Coded, **off**. Costs marked TODO |

Rough emissions (gas 0.198 tCO₂/MWh_th): unabated at 59 % → 336 g/kWh; 95 %
capture at 52 % net → ~19 g/kWh; Allam 98 % at 54 % → ~7 g/kWh.

**How to read this.** On paper they are close: ~50–56 % net, ~1.8–2.5 kEUR/kW.
Allam’s advantage is higher capture and no amine/steam-cycle integration, not a
free efficiency win. PyPSA’s Allam row (60 % and 1 886 EUR/kW) is friendlier to
Allam than the recent engineering literature.

CCGT-CC is the conservative option: same turbines, retrofit possible later,
capture can be switched off in reality (not yet in the LP). Allam only pays if
you need near-zero stack emissions and accept FOAK risk and poor flexibility.

Sources: DEA technology-data v0.14.0 (this repo’s pin); NETL Fossil Energy
Baseline Rev. 4a (NGCC ± 90/95 % Cansolv); IEAGHG *CO₂ Capture at Gas Fired
Power Plants*; Scaccabarozzi et al. 2024 *Fuel* (Allam 48.7–56.1 %, 2490 €/kW);
PyPSA `technology-data` Allam row (own assumption, TODO).

---

## 3. Has this been done before?

Yes in neighbouring PyPSA stacks; **not** as a first-class natural-gas CCGT in
upstream PyPSA-Eur (checked against `master` `prepare_sector_network.py`,
2026-08-25).

| Where | What they did | Similar to this implementation? |
|---|---|---|
| [PyPSA carbon-management example](https://docs.pypsa.org/stable/examples/biomass-synthetic-fuels-carbon-management/) | Canonical `OCGT+CCS` Link: η=0.4, 90 % to `co2 stored`, 10 % to atmosphere | Same four-bus idea; toy numbers |
| PyPSA-Eur | Capture on **CHP, coal, industry, SMR, methanol-CCGT, Allam** — not on gas CCGT. [PR #2161](https://github.com/PyPSA/pypsa-eur/pull/2161) adds an electricity penalty on coal CC and MeOH CCGT CC | **This is the pattern copied:** `coal_cc` / methanol `ccgt_cc` algebra (plant CAPEX × η + capture CAPEX × CO₂ intensity; net η minus electricity + compression) |
| This fork’s `coal_cc` | Same buses, but **no** electricity penalty (behind upstream) | We followed **upstream** coal_cc (with the penalty), not this fork’s older coal_cc |
| [PyPSA-USA](https://pypsa-usa.readthedocs.io/en/latest/config-configuration.html) | `CCGT-95CCS` as an extendable **Generator** (NREL ATB, 95 % capture, reduced `co2_emissions`) | Different: no CO₂ buses, not sector-coupled |
| [Open-TYNDP](https://github.com/open-energy-transition/open-tyndp) | Distinct TYNDP tech `Gas CCGT CCS` / `gas-ccgt-ccs` as a Link | Same component type; TYNDP cost set, not DEA |
| Older technology-data `add_costs_ccs()` | +600 EUR/kW and ×0.9 efficiency on gas CHP (DIW) | Not used here |

This repo already anticipated the carrier in post-processing
(`scripts/walloon_scripts/calculate_costs.py` maps `CCGT CC` → `CCGT+CCS`).
The old test `"cc" in "ccgt"` was true for **every** CCGT; that is fixed.

---

## 4. What was implemented (2026-08-25)

A four-bus extendable Link per node, carrier `CCGT CC`:

```
gas  --(η_net)-->  electricity
     --(CO2 × (1 − capture_rate))-->  co2 atmosphere
     --(CO2 × capture_rate)-->         co2 stored
```

Algebra (identical to current PyPSA-Eur `coal_cc`):

```
η_net        = CCGT.efficiency − (electricity-input + compression-electricity-input) × gas.CO2 intensity
capital_cost = CCGT.efficiency × CCGT.capital_cost + capture.capital_cost × gas.CO2 intensity
marginal_cost= CCGT.efficiency × CCGT.VOM
efficiency2  = gas.CO2 intensity × (1 − capture_rate)     # to atmosphere
efficiency3  = gas.CO2 intensity × capture_rate           # to stored
```

`p_nom` is on the **fuel** bus (PyPSA Link convention). Electrical capacity is
`p_nom × efficiency`.

Capture sheet (generic): **`biomass CHP capture`** (DEA 401.a, small CHP), the
same row coal CCS and gas CHP CCS already use in this fork. Capture rate **0.95**,
electricity+compression **0.095 MWh/tCO₂**. Steam for the amine reboiler is
**not** subtracted from η — same omission as PyPSA-Eur coal/MeOH CCS. Literature
puts that steam penalty at ~7 pp on a condensing CCGT; the modelled plant is
therefore a bit too efficient. See §6.

Existing brownfield CCGTs are unchanged. With `agg_ccgt: true`, **CCGT CC counts
toward `CCGT-all`**, so the 1 740 MW BEWAL `p_nom_min` can be met with CCS
plants. That is a modelling choice, not a physical constraint.

Enabled in the Walloon overlay only. `config.default.yaml` stays `false` so
non-Walloon configs do not change.

---

## 5. Where to change the parameters

Nothing is a dedicated `CCGT CC` cost row. Change the **ingredients**.

| What you want to change | Where | Notes |
|---|---|---|
| **Turn the technology off** | `config/config.walloon.yaml` → `sector.ccgt_cc: false` | Default in `config.default.yaml` is already false |
| **CCGT CAPEX / FOM / VOM / lifetime / η** | `config/input_parameters_for_models.csv` rows `cost:CCGT:*`, then `python scripts/build_common_parameters.py --write` **or** `costs.overwrites` in a scenario overlay **or** `data/walloon/custom_costs.csv` | Already the shared TIMES/PyPSA CCGT |
| **Capture rate, capture CAPEX, electricity demand** | technology-data rows for the capture sheet, currently **`biomass CHP capture`** | Comes from the pinned archive `data/costs/archive/v0.14.0`. Overwrite with `costs.overwrites` / `custom_costs.csv` (`capture_rate`, `investment`, `electricity-input`, `compression-electricity-input`) |
| **Which DEA capture sheet** | `CCGT_CC_CAPTURE_TECH` in `scripts/prepare_sector_network.py` | `"biomass CHP capture"` (401.a, small) or `"biomass boiler capture"` (401.b, large — better CCGT scale). Must exist in the cost table |
| **Steam-cycle efficiency penalty** | `ccgt_cc_link_params()` in `scripts/prepare_sector_network.py` | Not modelled. A typical add-on is −7 pp on `efficiency` (IEAGHG) or `− heat-input × CO2 intensity × (some kWh_e/kWh_th)` |
| **Capture VOM (EUR/tCO₂)** | same function, `marginal_cost` | Not added (PyPSA-Eur coal_cc does not add it). ~+0.6 EUR/MWh_th if you include `CO2 intensity × capture_rate × capture.VOM` |
| **Hurdle rate** | already on the `CCGT` and `biomass CHP capture` rows (`data/walloon/discount_rates.csv`) | Link CAPEX is annualised from those two techs; no extra mapping needed |
| **Dedicated overnight EUR/kW_e** | empty cells in `input_parameters_for_models.csv` (*Centrale à cycle combiné avec captage…*) | Fill + give them a `pypsa_wal_target` when TIMES agrees; until then the composed formula is authoritative |
| **Whether CCS counts toward the 1 740 MW floor** | `scripts/solve_network.py` `{"CCGT": "CCGT-all", "CCGT CC": "CCGT-all"}` | Drop `"CCGT CC"` from the rename to keep the floor on unabated CCGT only |
| **Plot colour / label** | `config/plotting.default.yaml` `tech_colors` / `nice_names` | Carrier name is `CCGT CC` |
| **Config schema** | `scripts/lib/validation/config/sector.py` Field `ccgt_cc`, then `pixi run generate-config` if you add more keys | |
| **DAC on/off** | `config/config.walloon.yaml` → `sector.dac` | `false` to match TIMES. Default yaml stays `true`. See §8 |

Gas CO₂ intensity (0.198 t/MWh_th) is the `gas` cost-table row. Changing it
moves residual emissions, capture sizing and the electricity penalty together.

---

## 6. Known gaps

1. **Steam penalty omitted.** Auxiliary electricity is ~2 pp. Amine regeneration
   steam is the rest (~7 pp in IEAGHG; DEA says dilute GT flue gas is 10–15 %
   extra energy vs high-CO₂ flue gas). Gas CHP CC in this codebase dumps that
   heat onto district heating; a condensing CCGT cannot.
2. **No retrofit.** Saint-Ghislain, Amercoeur, Marcinelle, Seraing, Flémalle stay
   unabated. A retrofit would be a second Link with `p_nom` tied to existing
   capacity, not done here.
3. **No part-load / minimum-load** specific to the capture train.
4. **TIMES cost cell still empty.** PyPSA and TIMES will diverge on CCGT-CCS
   overnight cost until that row is filled and `--write`n.
5. **Allam costs remain TODO** in technology-data. Do not treat a CCGT-CC vs
   Allam solve as a fair contest until that row is replaced.

---

## 7. Files touched

| File | Change |
|---|---|
| `scripts/prepare_sector_network.py` | `CCGT_CC_CAPTURE_TECH`, `ccgt_cc_link_params`, `add_ccgt_cc`; called when `sector.ccgt_cc` |
| `scripts/lib/validation/config/sector.py` | `ccgt_cc` Field |
| `config/config.default.yaml` | `ccgt_cc: false` (DAC stays the PyPSA-Eur default `true`) |
| `config/config.walloon.yaml` | `ccgt_cc: true`, **`dac: false`** |
| `config/schema.default.json`, `config/schema.json` | schema for the new key |
| `config/plotting.default.yaml` | colour + nice name |
| `scripts/solve_network.py` | `CCGT CC` in `agg_ccgt` rename |
| `scripts/walloon_scripts/review_run.py` | `LINK_AGG` |
| `scripts/walloon_scripts/calculate_costs.py` | CCS bucket no longer matches every CCGT |
| `config/input_parameters_for_models.csv` | placeholder notes point here |
| `test/test_ccgt_cc.py` | algebra, four-bus wiring, cost-row guard, categorise |

No full Snakemake solve was run (too slow). Checks: `test/test_ccgt_cc.py` and
`test/test_config_schema.py`.

---

## 8. Direct air capture (DAC) — how to turn it on or off

TIMES does not have a DAC process (no matching name in the Walloon `.vd`
files; the shared CSV rows for *Captage direct du CO₂ dans l'air* are
PyPSA-only). Earlier Walloon solves with DAC on used the urban-central heat
bus as a free heat source for capture: in 2050 more district heat went to DAC
than to buildings (`docs/logs/2026-08-18_scen_demande_haute_2010_1h.md`,
`docs/heat-softlink.md`). From 2026-08-25 the Walloon overlay **turns DAC
off** so the two models agree on the technology set.

The switch already existed. `add_dac` in `scripts/prepare_sector_network.py`
runs only when `options["dac"]` is true. It adds an extendable four-bus Link
(electricity + heat → CO₂ from atmosphere to `co2 stored`) on urban-central
and services urban-decentral heat buses. Nothing else instantiates DAC
(not `add_existing_baseyear`). Cost rows stay in the table unused.

### Toggle

| Goal | Where | Effect |
|---|---|---|
| **Off in Wallonia (current, TIMES-aligned)** | `config/config.walloon.yaml` → `sector.dac: false` | Overrides `config.default.yaml`. This is what `snakemake --configfile config/config.walloon.yaml` uses. |
| **On in Wallonia** | same key → `true` | Restores PyPSA-Eur DAC on heat buses. Cost data are already there (`cost:direct air capture:*` in the shared CSV). |
| **PyPSA-Eur / non-Walloon default** | `config/config.default.yaml` → `sector.dac: true` | Leave this. Changing it would affect every config that does not override. |
| **One scenario only** | `config/scenarios.walloon.yaml` under that scenario’s `sector:` block | Scenario overlay is applied **after** `config.walloon.yaml`, so `dac: true` here would turn DAC back on for that run only. No scenario currently sets it. |
| **Pydantic default** | `scripts/lib/validation/config/sector.py` Field `dac` (default `True`) | Schema / `config.default.yaml` source of truth. Do not flip this for a Walloon-only choice. |

`config.scen_suff.yaml` already had `dac: false`; `config.scen_base.yaml` and
`config.scen_corrige.yaml` still have `true`. Those files are not the Walloon
Snakemake overlay.

Turning DAC off does **not** disable other carbon management: CCGT-CC, gas
CHP CC, SMR CC, industry capture, the CO₂ network and the sequestration cap
stay as configured. Plot colours and the `"co2 Store": "DAC"` label in
`scripts/_helpers.py` are leftover names for the stored-CO₂ carrier, not the
DAC plant.

---

## 9. Reporting (pypsa2html)

pypsa2html is a general-purpose library, so `CCGT CC` is **not** hardcoded as
a technology. PyPSA-Eur names capture siblings `{tech} CC`; the reporter
treats that suffix as a convention (pypsa2html `docs/DESIGN_DECISIONS.md` D17).

| Chart | What you get when the network has `CCGT CC` |
|---|---|
| Capacities (stacked) | Own bar, colour `#c44c3a` |
| Capacities (faceted) | Extra series on the CCGT panel |
| Costs / map | Grouped with fossil power (any name containing `CCGT`) |
| Electricity Sankey | Generation and losses fold onto the existing gas-power codes (`proelcgaz`, `lossgas`) |
| Carbon Sankey | Residual stack emissions fold onto `emmccgt`. Captured CO₂ is `emmccgtcc` (gas → stored). Sequestration includes the stored port either way. |

To wire a *new* `{fuel} CC` plant into the carbon Sankey captured-CO₂ edge,
add one `carrier_flows_carbon.csv` row (`{tech} CC_2` → a code) and one
`processes_carbon.csv` edge to `stm`. Residual emissions and energy flows
inherit from the parent automatically. Do not add `if carrier == "CCGT CC"`
in Python.
