# CCS alignment — TIMES-WAL vs PyPSA-WAL

**Date:** 2026-08-25 (CCGT-CC wiring); TIMES vs last-solve snapshot 2026-08-24
**TIMES run:** `data/walloon/scen_demande_haute_v01_260727_fix_nuc_2807.vd`
(the `scen_demande_haute` coupling file)
**PyPSA last solve:** [`logs/2026-08-22_scen_demande_haute_2010_1h.md`](logs/2026-08-22_scen_demande_haute_2010_1h.md)
(`results/walloon/scen_demande_haute/`, 1 h / weather year 2010) — **before**
`sector.ccgt_cc` and with DAC still on
**Earlier review of the same physics:** [`logs/2026-08-18_scen_demande_haute_2010_1h.md`](logs/2026-08-18_scen_demande_haute_2010_1h.md) §11 (R9–R10)
**Purpose:** (1) where carbon capture exists in each model, whether it is
switched on, and whether it ran; (2) whether a combined-cycle gas turbine with
post-combustion capture (CCGT-CC) can live in this fork, which parameters it
needs, how that compares to the Allam cycle, what other PyPSA projects already
do, and where the generic values wired on 2026-08-25 can be changed.
**Wired into:** `sector.ccgt_cc` (on in `config/config.walloon.yaml`, off in
`config/config.default.yaml`) → `scripts/prepare_sector_network.py`
(`add_ccgt_cc`). DAC is **off** in the same Walloon overlay (`sector.dac:
false`). TIMES lists `CO2DAC-01` but does not build it in this vd.

CCGT-CC in PyPSA is **new-build only**. Existing Walloon TGVs stay unabated.
Overnight EUR/kW_e is **not** a single TIMES/PyPSA cell yet — the Link is
composed from the CCGT row plus a DEA capture sheet. Fill
`config/input_parameters_for_models.csv` when both models agree a dedicated
figure; until then do not `--write` those placeholder rows.

The soft-link does **not** transfer power-plant or hydrogen-supply technology;
both models choose those independently. Where the menus differ, the solved
systems diverge even with identical demands.

---

## 0. TIMES vs PyPSA — bottom line

| Technology | TIMES-WAL (`scen_demande_haute`) | PyPSA-WAL (Walloon config, 2026-08-25) | Soft-link |
|---|---|---|---|
| **CCGT + CCS** | On. Flemalle + Seraing New (1.74 GW) retrofitted from **2035**, ~86 % capture. New-build post-combustion CCGT CCS is in the dictionary and **not built**. | **New-build** `sector.ccgt_cc: true`. Existing TGVs stay unabated. Closest other switch (`allam_cycle_gas`) is **off**. Shared-CSV costs are empty placeholders. Last solve (22 Aug) had no `CCGT CC`. | Power generation is not transferred. Heat export was patched so the CCS plant is not mistaken for a boiler. |
| **Biomass → H₂ + CCS** | Dictionary has `SBIOH2GCC01` (gasification + CC). **Absent from this vd** (not built). What *does* run is black-liquor gasification `BBLQH2G110` from 2035, with biogenic CO₂ out. | Option `sector.bioH2` **is** biomass→H₂ **with CCS** (there is no unabated twin). Default and Walloon overlay: **`false`**. Not in the last-run network. | Black liquor is deliberately **not** exported as `solid biomass`. `SBIOH2*` is unmapped. |
| **DAC** | Process `CO2DAC-01` exists; **not built** (duals only). | `sector.dac: false` (TIMES-aligned). Last solve still had `true`: unused until 2050, then a large plant (system 1.1 GW_e, 23.5 TWh_e). | Not transferred. |
| **CO₂ storage** | `STORAGEMINELC` + `STORAGEMININD` store ~7.1 Mt in 2050 (Wallonia-only model). | `co2_sequestration_potential` 0 / 20 / 90 / 125 Mt on the last-run years that bound. Last run **hits the cap exactly** every year it is non-zero. | Not transferred. |

The menus now overlap on **new-build** CCGT-CC, but TIMES uses **retrofit** from
2035 and PyPSA does not. They still do not share a used biomass-to-hydrogen+CCS
option. PyPSA’s CCS volume in the last solve is industrial biomass CC + DAC +
the sequestration cap, not power-plant CCS. DAC has since been turned off and
CCGT-CC turned on; there is no new solve yet.

### TIMES CCGT+CCS — retrofit, not new-build

Two families in the vd:

| Process | Role | In this vd |
|---|---|---|
| `ETSTP_CCGT-CCS_PostC_GAS_N` | New-build post-combustion CCGT CCS | Duals (`VAR_ActM`) only — **not built** |
| `ETSTP_CCGT_CCS_E12/E13_N` + `ETSTP_Retrofit_CCGT_CCS_E12/E13_N` | CCS on Flemalle (E12) and Seraing New (E13) | **Built from 2035** |

The two plants are 870 + 870 = **1 740 MW**. They run as unabated CCGT
(`ETSTP_TGV_GAS_New_E12/E13`) in 2025/2030, then the whole 1.74 GW is on the
CCS processes from 2035. Capacity split in every year 2035–2050:

| GW | E12 (Flemalle) | E13 (Seraing New) | sum |
|---|---:|---:|---:|
| `ETSTP_CCGT_CCS_*` | 0.100 | 0.222 | 0.322 |
| `ETSTP_Retrofit_CCGT_CCS_*` | 0.770 | 0.648 | 1.418 |
| **total** | 0.870 | 0.870 | **1.740** |

Only the **retrofit** processes capture. 2035 E12 retrofit: 1 347 kt `ELCCO2c`
(captured) vs 226 kt `ELCCO2N` (stack) → **capture fraction ≈ 86 %**. Electricity
out (`ELCHIG`) is 14.9 PJ (E12 retrofit) + 12.8 PJ (E13 retrofit) in 2035, still
~15 + 11 PJ in 2050 — they keep running.

`TIMES_PyPSA/data/techs/mapping_tech.csv` maps `ETSTP_CCGT-CCS_PostC_GAS_N` to an
**empty** PyPSA name.

Those 1 740 MW appear in PyPSA as **unabated** CCGT (the new `CCGT CC` link is
extendable new-build, not a retrofit of these units):

- `data/walloon/wal_2021_existing_capacities_2.csv`: Flemalle 2025, Seraing New
  2026, carrier `CCGT`
- `data/walloon/custom_potentials.csv`: `BEWAL CCGT p_nom_min = 1740 MW_el` at
  every horizon (re-imposed on the *new* vintage — see the 18 Aug log R3)

Last-run system CCGT (unabated, no `CCGT CC`): 100 / 101 / 65 / 51 GW nameplate;
82 / 80 / 47 / 20 TWh gas in. No `allam gas` carrier exists in that
`energy.csv`.

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
   unabated. TIMES retrofits Flemalle (E12) and Seraing New (E13) from 2035
   (§0). A PyPSA retrofit would be a second Link with `p_nom` tied to existing
   capacity, not done here. What stands in for it is the technology-neutral
   `CCGT-all` floor (§13.1): the adequacy requirement can be met with capture,
   so the model may reach a TIMES-like capacity mix through new-build. It does
   not reproduce a retrofit's economics — a retrofit reuses the existing power
   island and so is cheaper per kW than the greenfield CCGT-CC costed in §2.
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

Added 2026-08-26, moving the Walloon gas floor off unabated CCGT (§13.1):

| File | Change |
|---|---|
| `data/walloon/custom_potentials.csv` | dropped the four `BEWAL,CCGT,p_nom_min` rows |
| `data/walloon/agg_p_nom_minmax_*.csv` | added `BEWAL,CCGT-all` min = 1 740 at every horizon |
| `config/input_parameters_for_models.csv` | *Minimum CCGT installé* retargeted to `agg:BEWAL:CCGT-all:min` |
| `scripts/walloon_scripts/BEWAL_potentials.py` | `apply_link_p_nom_min` — floors are fleet-wide, not per-vintage |
| `test/test_common_parameters_agg.py` | `test_walloon_gas_floor_is_technology_neutral` |

No full Snakemake solve was run (too slow). Checks: `test/test_ccgt_cc.py` and
`test/test_config_schema.py`.

---

## 8. Direct air capture (DAC) — how to turn it on or off

TIMES lists process `CO2DAC-01` (solid amine DAC) in the dictionary; it is
**not built** in `scen_demande_haute` (duals only). Shared CSV rows for
*Captage direct du CO₂ dans l'air* are PyPSA-only. Earlier Walloon solves with DAC on used the urban-central heat
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

---

## 10. Biomass → hydrogen

### PyPSA — CCS-only, and switched off

`sector.bioH2` (default **`false`**) adds one link, named
`solid biomass to hydrogen CC`. Capture fraction `cc_fraction` is 0.9
(`config.default.yaml`). Capture CAPEX is borrowed from `biomass CHP capture`.
There is **no unabated** biomass-to-hydrogen link; the schema text is
*“transforming solid biomass into hydrogen with carbon capture.”*

`config.walloon.yaml` does not override `bioH2`, so the Walloon study inherits
`false`. The last-run `energy.csv` link-carrier list has no
`solid biomass to hydrogen`. The process cannot have been used: it is not in
the LP.

Related biomass conversion switches, also **off**: `biosng`, `biosng_cc`,
`biomass_to_liquid_cc`, `biogas_upgrading_cc`,
`methanol.biomass_to_methanol_cc`. Unabated `biomass_to_liquid` and
`biomass-to-methanol` are on but ran at noise level in the last solve
(≤ 0.3 MW / ≤ 0.3 GWh until methanol 3.7 MW in 2050).

### TIMES — CCS variant exists, not chosen; black liquor is what runs

| Process | Description | In this vd |
|---|---|---|
| `SBIOH2GCC01` | Biomass gasification + carbon capture, medium, central | **Absent** |
| `SBIOH2GC01` | Same without capture | **Absent** |
| `SBIOH2GD01` | Small decentral gasification | **Absent** |
| `SBIOH2RC01` | Biomass steam reforming | **Absent** |
| `BBLQH2G110` | Black-liquor gasification → H₂ | **Used from 2035** |

`SBIOH2GCC01` is the TIMES analogue of PyPSA `bioH2`. It is in
`AllProcesses.csv` / `mapping_tech.csv` with an empty PyPSA name, and this
scenario does not invest in it.

`BBLQH2G110` is a pulp-mill closed loop (`INDBLQ` in, `SYNH2CT` + biogenic
`INDCO2b` out):

| | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|
| Capacity (GW) | 0.009 | 0.063 | 0.101 | 0.101 |
| Black liquor in (PJ) | 0.45 | 1.79 | 3.13 | **3.99** |
| H₂ out `SYNH2CT` (PJ) | 0.26 | 1.06 | 1.85 | **2.36** |
| Biogenic CO₂ `INDCO2b` (kt) | 42 | 170 | 298 | **380** |

PyPSA cannot source that residue from the wood potential. The extraction rule
for `solid biomass` **excludes** black liquor on purpose
([TIMES_PyPSA README](../../TIMES_PyPSA/README.md) / `aggregation.md`). So even
the biomass-H₂ path TIMES *does* use is not a PyPSA demand and has no PyPSA
twin.

---

## 11. Other CCS on the PyPSA side (last solve, 22 Aug)

Switches as inherited by `config.walloon.yaml` from `config.default.yaml` at
the time of the last solve (DAC was still on; `ccgt_cc` did not exist yet).
Figures are **system-wide** from
`results/walloon/scen_demande_haute/csvs/{energy,capacities}.csv`
(energy in MWh of the link; capacity in MW of the link, or t for the CO₂ store).

| Option | Config (last solve) | Last run 2025 → 2050 |
|---|---|---|
| Direct air capture | `dac: true` then; **`false` now** | Capacity 0.02 → **1 105 MW**; electricity 0.2 GWh → **23.5 TWh**. 18 Aug BEWAL review: 6.14 TWh_th heat + 2.41 TWh_e → 4.39 Mt captured (2.6× the Walloon 2050 cap). |
| SMR + CCS | `SMR_cc: true` | Capacity **< 1 MW**; energy < 0.4 GWh — unused. Unabated SMR keeps ~14.5 GW and runs 5.3 → 0.08 TWh. |
| SMR (no CCS) | `SMR: true` | See above. |
| Allam cycle (gas CCS power) | `allam_cycle_gas: false` | Not in the network. |
| Coal + CCS | `coal_cc: false` | Off. |
| Methanol CCGT + CC | `methanol.methanol_to_power.ccgt_cc: false` | Off. |
| BioSNG ± CC | `biosng` / `biosng_cc: false` | Off. |
| Biomass-to-liquid + CC | `biomass_to_liquid_cc: false` | Off. |
| Biogas upgrading + CC | `biogas_upgrading_cc: false` | Off. |
| Biomass → methanol + CC | `methanol.biomass_to_methanol_cc: false` | Off. |
| Urban-central **biomass CHP CC** | always added when `chp.enable` (not `scen_suff`) | Capacity **< 0.2 MW**; energy ~25 MWh — unused. Unabated biomass CHP is large until 2050 (43 → 0.3 GW). |
| Urban-central **gas CHP CC** | same | Noise until 2050 (**3.4 GW**, 0.53 TWh). |
| **Solid biomass for industry CC** | always added | The one industrial BECCS that binds: 0.2 MW → **36.9 GW**; energy 0.1 GWh → **32.3 TWh**. |
| Gas for industry CC | always added | 0.3 MW → **10.4 GW**; 0.1 GWh → **8.9 TWh**. |
| Process-emissions CC | always added | Capacity 0.8 → 7.8 GW, **energy 0** (built, not used). |
| CO₂ network | `co2_network: true` | Pipeline capacity 0.25 → 7.1 GW; pipeline *energy* 0. |
| Sequestration cap | Walloon overlay: 0 / 0 / **20** / 90 / 125 Mt (half the PyPSA-Eur default) | Store `co2 sequestered`: **0, 20, 90, 125 Mt** — the cap, every year. Dual binds (18 Aug R9). |

`cc_fraction: 0.9` is the capture rate on SMR CC and on `bioH2`. Biomass CHP /
industry CC use the technology-data `capture_rate` of `biomass CHP capture` or
`cement capture`.

TIMES storage in the same vd: `STORAGEMINELC` 2.3 Mt + `STORAGEMININD` 4.8 Mt
in 2050 (**~7.1 Mt**, Wallonia only). TIMES DAC (`CO2DAC-01`) is not built.

---

## 12. Soft-linking

The TIMES→PyPSA transfer is final-energy **demand** (plus the heating mix and
the EV fleet). Electricity *generation* and hydrogen *supply* are re-optimised
in PyPSA. Consequences:

1. **CCGT+CCS activity is not exported** and should not be. No extraction rule
   reads `ELCHIG` from power plants.
2. The heating payload used to pick up `Thermal Public - Retrofitting CCGT CCS`
   via a `thermal` regex (1 740 MW of power plant counted as heat stock).
   Selection is now an explicit label list
   (`TIMES_PyPSA/times_pypsa/heat_softlink.py`).
3. **`SBIOH2GCC01` is unmapped**; even if TIMES built it, PyPSA would not see
   it as a demand.
4. **Black liquor → H₂ is excluded** from `solid biomass` so PyPSA does not
   charge a forestry potential for a mill residue.

The pipeline is consistent with “PyPSA chooses the supply mix.” It is **not**
yet consistent with “both models may use the same CCS plants”: TIMES retrofits
CCGT from 2035 and runs black-liquor H₂ from 2035; PyPSA now has new-build
CCGT-CC (unsolved) and keeps `bioH2` off.

---

## 13. Open decisions

1. ~~**CCGT retrofit vs new-build.**~~ **Decided 2026-08-26: the floor is
   technology-neutral.** The 1 740 MW_e Walloon floor moved from
   `potential:BEWAL:CCGT:p_nom_min` (a floor on *unabated* CCGT, written onto
   the new vintage of `custom_potentials.csv`) to `agg:BEWAL:CCGT-all:min` in
   `agg_p_nom_minmax_*.csv`. Because `agg_ccgt` folds `CCGT` and `CCGT CC` into
   `CCGT-all`, the adequacy requirement no longer picks the technology.

   Why it had to change: in the 2050 solve of
   `docs/logs/2026-08-25_scen_demande_haute_2010_1h.md` the old floor forced
   1 740 MW_e of unabated CCGT into Wallonia *at every horizon* — 5 640 MW_e of
   fleet by 2050 — and left no residual demand for capture, so Wallonia built
   **0 MW of CCGT CC** while Germany built 8 465 MW_e and Brussels 1 116 MW_e.
   The technology was not uneconomic: its break-even against unabated CCGT is
   about 103 EUR/tCO2 at 4 000 full-load hours, against a global CO2 dual of
   625 EUR/t. It was crowded out by the mandate.

   This is still not a retrofit (§6.2): PyPSA's `CCGT CC` is new-build only, so
   a technology-neutral floor is an exogenous stand-in. It reproduces TIMES'
   *outcome* — captured gas capacity meeting the adequacy requirement — without
   hard-coding it, and it lets the solve say whether capture is worth it.
2. **`sector.bioH2`.** Turning it on would give PyPSA biomass→H₂ **with CCS
   only**, which matches `SBIOH2GCC01` (unused in this TIMES scenario) and does
   **not** match `BBLQH2G110` (the path TIMES actually runs). Enabling it
   without a black-liquor supply still leaves the mill loop on the TIMES side
   only.
3. **Sequestration cap.** PyPSA’s European 125 Mt cap binds and therefore
   writes every CCS/DAC number. TIMES-WAL stores ~7 Mt in Wallonia. The two
   figures are not comparable without a Belgium/Europe split on the PyPSA side.
4. **DAC.** Off in the Walloon overlay as of 2026-08-25 so the menus match
   (TIMES does not build `CO2DAC-01`). Under option B′ with DAC on, the Walloon
   district-heat expansion largely fed DAC (18 Aug R10). That was a PyPSA
   outcome, not a transferred TIMES choice.
