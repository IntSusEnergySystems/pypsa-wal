# CCS technology alignment — TIMES-WAL vs PyPSA-WAL

**Scope.** Which carbon-capture *technologies* exist in each model, whether they
are switched on, whether they ran, and how to change their parameters. The
disposal side — how much may be buried, where, at what cost, how it leaves
Wallonia, and how much the model actually captures — is in
[`co2-sequestration.md`](co2-sequestration.md).

**Dates.** CCGT-CC wiring 2026-08-25; TIMES vs last-solve snapshot 2026-08-24;
industrial capture chain 2026-09-08; last full review 2026-09-19.
**TIMES run:** `data/walloon/scen_demande_haute_v01_260727_fix_nuc_2807.vd`.
**PyPSA solves referenced:**
[`2026-08-22`](logs/2026-08-22_scen_demande_haute_2010_1h.md) (before
`sector.ccgt_cc`, DAC still on), the 2026-09-07 run for §11–§13, and
[`2026-09-13 cabinet batch`](logs/2026-09-13_cabinet_batch_all14_2010_1h.md).

**Two framing facts.** CCGT-CC in PyPSA is **new-build only**; existing Walloon
TGVs stay unabated, where TIMES retrofits them. And the soft-link does **not**
transfer power-plant or hydrogen-supply technology — both models choose those
independently, so where the menus differ the solved systems diverge even with
identical demands.

---

## 1. Technology menus side by side

| Technology | TIMES-WAL (`scen_demande_haute`) | PyPSA-WAL (Walloon config) | Transferred? |
|---|---|---|---|
| **CCGT + CCS** | On. Flémalle + Seraing New (1.74 GW) **retrofitted** from 2035, ~86 % capture. New-build post-combustion CCGT CCS is in the dictionary and **not built**. | **New-build** `sector.ccgt_cc: true`. Existing TGVs stay unabated. `allam_cycle_gas` is **off**. Shared-CSV cost cells still empty. | No — power generation is not transferred. Heat export was patched so the CCS plant is not mistaken for a boiler. |
| **Biomass → H₂ + CCS** | `SBIOH2GCC01` (gasification + CC) is in the dictionary, **absent from this vd**. What runs is black-liquor gasification `BBLQH2G110` from 2035, biogenic CO₂ out. | `sector.bioH2` is biomass→H₂ **with CCS** (no unabated twin). Default and Walloon overlay: **`false`**. | No. Black liquor is deliberately **not** exported as `solid biomass`; `SBIOH2*` is unmapped. |
| **DAC** | `CO2DAC-01` exists; **not built** (duals only). | `sector.dac: false` (TIMES-aligned, since 2026-08-25). | No. |
| **CO₂ storage** | `STORAGEMINELC` + `STORAGEMININD` ≈ 7.1 Mt in 2050 (Wallonia-only model) — an *injection* figure, not geology. | Geology ramp; Belgian `e_nom_max` **0** at all three nodes; export via `co2_network` to DE/NL/GB. | No. See [`co2-sequestration.md`](co2-sequestration.md). |

The menus overlap on **new-build** CCGT-CC, but TIMES uses **retrofit** from 2035
and PyPSA does not. They still do not share a *used* biomass-to-hydrogen+CCS
option.

**Where the capture lands differs too.** TIMES captures ~2× more on power; PyPSA
captures ~60 % more on industry and only reaches TIMES-like power capture in
2050. The totals agree (≈8 Mt vs 9.7–10.6 Mt); the split does not. Numbers in
[`co2-sequestration.md`](co2-sequestration.md) §6.3.

### 1.1 TIMES CCGT+CCS is a retrofit, not a new build

Two families in the vd:

| Process | Role | In this vd |
|---|---|---|
| `ETSTP_CCGT-CCS_PostC_GAS_N` | New-build post-combustion CCGT CCS | Duals (`VAR_ActM`) only — **not built** |
| `ETSTP_CCGT_CCS_E12/E13_N` + `ETSTP_Retrofit_CCGT_CCS_E12/E13_N` | CCS on Flémalle (E12) and Seraing New (E13) | **Built from 2035** |

The two plants are 870 + 870 = **1 740 MW**. They run as unabated CCGT in
2025/2030, then the whole 1.74 GW moves onto the CCS processes from 2035, split
0.322 GW `ETSTP_CCGT_CCS_*` / 1.418 GW `ETSTP_Retrofit_CCGT_CCS_*` in every year
2035–2050. Only the **retrofit** processes capture: the 2035 E12 retrofit gives
1 347 kt `ELCCO2c` (captured) against 226 kt `ELCCO2N` (stack) → **capture
fraction ≈ 86 %**. They keep running to 2050 (~15 + 11 PJ electricity out).

Those 1 740 MW appear in PyPSA as **unabated** CCGT
(`data/walloon/wal_2021_existing_capacities_2.csv`: Flémalle 2025, Seraing New
2026, carrier `CCGT`), with the adequacy floor now technology-neutral (§14 item 1).
`TIMES_PyPSA/data/techs/mapping_tech.csv` maps `ETSTP_CCGT-CCS_PostC_GAS_N` to an
**empty** PyPSA name.

---

## 2. CCGT-CC in PyPSA — what was implemented (2026-08-25)

Unabated CCGT was already a three-bus Link (gas → electricity, all CO₂ to `co2
atmosphere`). Capture adds a fourth bus. The code path is the one PyPSA-Eur
already uses for coal CCS, urban-central gas CHP CCS and methanol-CCGT CCS — it
was simply never offered on natural-gas CCGT.

A four-bus extendable Link per node, carrier `CCGT CC`:

```
gas  --(η_net)-->                        electricity
     --(CO2 × (1 − capture_rate))-->     co2 atmosphere
     --(CO2 × capture_rate)-->           co2 stored
```

Algebra, identical to current PyPSA-Eur `coal_cc`:

```
η_net         = CCGT.efficiency − (electricity-input + compression-electricity-input) × gas.CO2 intensity
capital_cost  = CCGT.efficiency × CCGT.capital_cost + capture.capital_cost × gas.CO2 intensity
marginal_cost = CCGT.efficiency × CCGT.VOM
efficiency2   = gas.CO2 intensity × (1 − capture_rate)     # to atmosphere
efficiency3   = gas.CO2 intensity × capture_rate           # to stored
```

`p_nom` is on the **fuel** bus (PyPSA Link convention); electrical capacity is
`p_nom × efficiency`. Capture sheet: **`biomass CHP capture`** (DEA 401.a, small
CHP), the same row coal CCS and gas CHP CCS already use in this fork. Capture
rate **0.95**, electricity+compression **0.095 MWh/tCO₂**. Steam for the amine
reboiler is **not** subtracted from η — the same omission as PyPSA-Eur coal/MeOH
CCS, so the modelled plant is a few points too efficient (§6 item 1).

Enabled in the Walloon overlay only; `config.default.yaml` stays `false`.
Existing brownfield CCGTs are unchanged. With `agg_ccgt: true`, **CCGT CC counts
toward `CCGT-all`**, so the 1 740 MW BEWAL floor can be met with capture plants —
a modelling choice, not a physical constraint (§14 item 1).

Do not confuse `sector.ccgt_cc` with `sector.methanol.methanol_to_power.ccgt_cc`,
which is a **methanol-fired** CCGT with capture and stays `false`.

---

## 3. Techno-economics: CCGT-CC vs Allam

Order-of-magnitude, LHV, ~EUR2025, 2030-ish. These guided the implementation;
they are **not** the solver inputs, which are composed from the cost table (§2).

| | **Unabated CCGT** | **CCGT + post-combustion CC** | **Allam (oxy-fuel sCO₂)** |
|---|---|---|---|
| What it is | Standard combined cycle | Same plant + amine scrubber on the stack | New cycle: combusts gas in O₂, working fluid is CO₂ |
| Capture rate | 0 | **90–95 %** | **97–100 %** (PyPSA hard-codes **98 %**) |
| Residual CO₂ | ~330 g/kWh_e | ~20–40 g/kWh_e | ~0–10 g/kWh_e |
| Net electrical efficiency | **58–63 %** (this repo 58–60 %) | **50–56 %** (~7–10 pp penalty; reboiler steam is most of it) | **50–56 %** independent studies; vendor claims ~59 %; PyPSA **60 %** (optimistic) |
| Overnight investment | **~1 100 EUR/kW_e** (DEA / this repo) | **~1 700–2 200 EUR/kW_e** (~+60–100 %); NETL ~2× the unabated plant | **Wide: ~1 000–2 500 EUR/kW_e**. PyPSA **1 886** (own guess). PoliMi 2024: **2 490 €/kW**, ~20 % *below* their NGCC+CCS benchmark |
| FOM | ~3.3 %/yr of CAPEX | Plant ~3.3 % + capture ~3 % | Not in technology-data; expect similar or higher (ASU + sCO₂ kit) |
| VOM | ~5.3–5.6 EUR/MWh_e | Plant VOM **plus** ~3 EUR/tCO₂ solvent (~+1 EUR/MWh_e) | PyPSA **2.5 EUR/MWh_e** (TODO, likely low) |
| Lifetime | 25 yr (DEA) | 25 yr plant; capture train similar | PyPSA **30 yr** (assumption) |
| Flexibility | Excellent (minutes, ~30 % min load) | Capture train **slows ramps**; scrubber can be bypassed | **ASU is slow** (hours); part-load weakly demonstrated |
| Retrofit existing TGVs | — | **Yes** (steam extraction + absorber) | **No** — different machine |
| TRL | 9 | Capture **7–8** | **~6–7** (La Porte demo; no commercial plant running) |
| In pypsa-wal | Default, inside the 1 740 MW floor | **On** (`sector.ccgt_cc: true`) | Coded, **off**. Costs marked TODO |

Rough emissions (gas 0.198 tCO₂/MWh_th): unabated at 59 % → 336 g/kWh; 95 %
capture at 52 % net → ~19 g/kWh; Allam 98 % at 54 % → ~7 g/kWh.

**How to read this.** On paper they are close: ~50–56 % net, ~1.8–2.5 kEUR/kW.
Allam's advantage is higher capture and no amine/steam-cycle integration, not a
free efficiency win, and PyPSA's Allam row (60 %, 1 886 EUR/kW) is friendlier to
Allam than the recent engineering literature. CCGT-CC is the conservative option:
same turbines, retrofit possible later, capture can in reality be switched off
(not yet in the LP). **Do not treat a CCGT-CC vs Allam solve as a fair contest
until the Allam cost row is replaced.**

Sources: DEA technology-data v0.14.0 (this repo's pin); NETL Fossil Energy
Baseline Rev. 4a (NGCC ± 90/95 % Cansolv); IEAGHG *CO₂ Capture at Gas Fired Power
Plants*; Scaccabarozzi et al. 2024 *Fuel* (Allam 48.7–56.1 %, 2 490 €/kW).

---

## 4. Prior art

Done in neighbouring PyPSA stacks; **not** as a first-class natural-gas CCGT in
upstream PyPSA-Eur (checked against `master`, 2026-08-25).

| Where | What they did | Relation to this implementation |
|---|---|---|
| [PyPSA carbon-management example](https://docs.pypsa.org/stable/examples/biomass-synthetic-fuels-carbon-management/) | `OCGT+CCS` Link: η = 0.4, 90 % to `co2 stored`, 10 % to atmosphere | Same four-bus idea; toy numbers |
| PyPSA-Eur | Capture on CHP, coal, industry, SMR, methanol-CCGT, Allam — not on gas CCGT. [PR #2161](https://github.com/PyPSA/pypsa-eur/pull/2161) adds an electricity penalty on coal CC and MeOH CCGT CC | **The pattern copied** — upstream `coal_cc` algebra, *with* the penalty |
| This fork's `coal_cc` | Same buses, but **no** electricity penalty | Behind upstream; not followed |
| [PyPSA-USA](https://pypsa-usa.readthedocs.io/en/latest/config-configuration.html) | `CCGT-95CCS` as an extendable Generator (NREL ATB) | Different: no CO₂ buses, not sector-coupled |
| [Open-TYNDP](https://github.com/open-energy-transition/open-tyndp) | `Gas CCGT CCS` as a Link, TYNDP cost set | Same component type, different costs |
| Older technology-data `add_costs_ccs()` | +600 EUR/kW and ×0.9 efficiency on gas CHP (DIW) | Not used here |

Post-processing already anticipated the carrier
(`scripts/walloon_scripts/calculate_costs.py` maps `CCGT CC` → `CCGT+CCS`); the
old test `"cc" in "ccgt"`, true for **every** CCGT, is fixed.

---

## 5. Where to change the parameters

Nothing is a dedicated `CCGT CC` cost row. Change the **ingredients**.

| What you want to change | Where | Notes |
|---|---|---|
| **Turn the technology off** | `config/config.walloon.yaml` → `sector.ccgt_cc: false` | `config.default.yaml` is already false |
| **CCGT CAPEX / FOM / VOM / lifetime / η** | `config/input_parameters_for_models.csv` rows `cost:CCGT:*`, then `python scripts/build_common_parameters.py --write`; **or** `costs.overwrites` in a scenario overlay; **or** `data/walloon/custom_costs.csv` | Already the shared TIMES/PyPSA CCGT |
| **Capture rate, capture CAPEX, electricity demand** | technology-data rows for the capture sheet, currently **`biomass CHP capture`** | From the pinned archive `data/costs/archive/v0.14.0`. Overwrite with `costs.overwrites` / `custom_costs.csv` (`capture_rate`, `investment`, `electricity-input`, `compression-electricity-input`) |
| **Which DEA capture sheet** | `CCGT_CC_CAPTURE_TECH` in `scripts/prepare_sector_network.py` | `"biomass CHP capture"` (401.a, small) or `"biomass boiler capture"` (401.b, large — better CCGT scale). Must exist in the cost table |
| **Steam-cycle efficiency penalty** | `ccgt_cc_link_params()` in `scripts/prepare_sector_network.py` | Not modelled. Typical add-on: −7 pp on `efficiency` (IEAGHG) |
| **Capture VOM (EUR/tCO₂)** | same function, `marginal_cost` | Not added (upstream `coal_cc` does not). ~+0.6 EUR/MWh_th if you include `CO2 intensity × capture_rate × capture.VOM` |
| **Hurdle rate** | already on the `CCGT` and `biomass CHP capture` rows (`data/walloon/discount_rates.csv`) | Link CAPEX is annualised from those two techs; no extra mapping needed |
| **Dedicated overnight EUR/kW_e** | empty cells in `input_parameters_for_models.csv` (*Centrale à cycle combiné avec captage…*) | Fill + give them a `pypsa_wal_target` once both models agree a figure. Until then the composed formula is authoritative — **do not `--write` those placeholder rows** |
| **Whether CCS counts toward the 1 740 MW floor** | `scripts/solve_network.py` `{"CCGT": "CCGT-all", "CCGT CC": "CCGT-all"}` | Drop `"CCGT CC"` to keep the floor on unabated CCGT only |
| **Plot colour / label** | `config/plotting.default.yaml` `tech_colors` / `nice_names` | Carrier name is `CCGT CC` |
| **Config schema** | `scripts/lib/validation/config/sector.py` Field `ccgt_cc`, then `pixi run generate-config` if you add keys | |
| **DAC on/off** | `config/config.walloon.yaml` → `sector.dac` | `false` to match TIMES. See §7 |

Gas CO₂ intensity (0.198 t/MWh_th) is the `gas` cost-table row. Changing it moves
residual emissions, capture sizing and the electricity penalty together.

---

## 6. Known gaps

1. **Steam penalty omitted.** Auxiliary electricity is ~2 pp; amine regeneration
   steam is the rest (~7 pp in IEAGHG; DEA notes dilute GT flue gas costs 10–15 %
   extra energy vs high-CO₂ flue gas). Gas CHP CC in this codebase dumps that heat
   onto district heating; a condensing CCGT cannot.
2. **No retrofit.** Saint-Ghislain, Amercoeur, Marcinelle, Seraing and Flémalle
   stay unabated, where TIMES retrofits E12/E13 from 2035 (§1.1). A PyPSA retrofit
   would be a second Link with `p_nom` tied to existing capacity — not done. What
   stands in for it is the technology-neutral `CCGT-all` floor (§14 item 1): the
   adequacy requirement can be met with capture, so the model may reach a
   TIMES-like capacity mix through new-build. It does **not** reproduce a
   retrofit's economics — a retrofit reuses the existing power island and is
   cheaper per kW than the greenfield plant costed in §3.
3. **No part-load or minimum-load behaviour** specific to the capture train.
4. **The shared CCGT-CCS cost cell is still empty**, so the two models will
   diverge on overnight cost until it is filled and `--write`n.
5. **Allam costs remain TODO** in technology-data.
6. **Process capture carries no energy penalty at all** [V].
   `BEWAL process emissions CC` has three ports — process emissions in,
   `co2 atmosphere` slip, `co2 stored` — and no electricity or heat input;
   [`prepare_sector_network.py:5981`](../scripts/prepare_sector_network.py:5981)
   reads only `capital_cost`, `capture_rate` and `lifetime` from `cement capture`
   under the comment `# assume enough local waste heat for CC`. The DEA rows for
   `electricity-input` (0.020) and `compression-electricity-input` (0.075
   MWh_e/tCO₂) are in `costs_*.csv` and go unread — **0.095 MWh_e/t, worth
   8.8–9.5 EUR/t**, on the largest and most price-invariant capture block in the
   model (≈5.0 Mt/a at 2040, ±1.6 % across all 16 solved scenarios). This is item 1
   above seen on the *process* side rather than the power side. See
   [`co2-sequestration.md`](co2-sequestration.md) §10.3.3.

---

## 7. Direct air capture

TIMES lists `CO2DAC-01` (solid amine DAC) in the dictionary but does **not build
it** in `scen_demande_haute` (duals only). Earlier Walloon solves with DAC on used
the urban-central heat bus as a free heat source: in 2050 more district heat went
to DAC than to buildings
([`2026-08-18`](logs/2026-08-18_scen_demande_haute_2010_1h.md), `heat-softlink.md`).
From 2026-08-25 the Walloon overlay **turns DAC off** so the two menus agree.

`add_dac` in `scripts/prepare_sector_network.py` runs only when `options["dac"]`
is true; nothing else instantiates DAC (not even `add_existing_baseyear`). Cost
rows stay in the table, unused.

| Goal | Where | Effect |
|---|---|---|
| **Off in Wallonia (current, TIMES-aligned)** | `config/config.walloon.yaml` → `sector.dac: false` | Overrides `config.default.yaml`; this is what `--configfile config/config.walloon.yaml` uses |
| **On in Wallonia** | same key → `true` | Restores PyPSA-Eur DAC on heat buses. Cost data already present (`cost:direct air capture:*`) |
| **PyPSA-Eur / non-Walloon default** | `config/config.default.yaml` → `sector.dac: true` | Leave this — changing it affects every config that does not override |
| **One scenario only** | `config/scenarios.walloon.yaml` under that scenario's `sector:` block | Applied **after** `config.walloon.yaml`. No scenario currently sets it |
| **Pydantic default** | `scripts/lib/validation/config/sector.py` Field `dac` (default `True`) | Schema source of truth. Do not flip for a Walloon-only choice |

`config.scen_suff.yaml` already had `dac: false`; `config.scen_base.yaml` and
`config.scen_corrige.yaml` still have `true`. Those are resolved snapshots, not
the Walloon Snakemake overlay.

Turning DAC off does **not** disable other carbon management: CCGT-CC, gas CHP CC,
SMR CC, industry capture, the CO₂ network and the sequestration limits stay as
configured. Plot colours and the `"co2 Store": "DAC"` label in
`scripts/_helpers.py` are leftover names for the stored-CO₂ carrier, not the DAC
plant.

**DAC is also the documented fix for the 2050 net-zero infeasibility** (§14
item 5) — it is the only technology in the model that moves *atmospheric* carbon
onto `co2 stored`. Turning it back on is therefore a trade-off between menu
alignment with TIMES and reachability of a net-zero 2050.

---

## 8. Biomass → hydrogen

### PyPSA — CCS-only, and switched off

`sector.bioH2` (default **`false`**) adds one link, `solid biomass to hydrogen
CC`, capture fraction `cc_fraction` 0.9, capture CAPEX borrowed from `biomass CHP
capture`. There is **no unabated** twin. `config.walloon.yaml` does not override
it, so the Walloon study inherits `false` and the link is not in the LP.

Related biomass conversion switches, also **off**: `biosng`, `biosng_cc`,
`biomass_to_liquid_cc`, `biogas_upgrading_cc`, `methanol.biomass_to_methanol_cc`.
Unabated `biomass_to_liquid` and `biomass-to-methanol` are on but ran at noise
level in the 22 Aug solve.

### TIMES — the CCS variant exists but is not chosen; black liquor is what runs

| Process | Description | In this vd |
|---|---|---|
| `SBIOH2GCC01` | Biomass gasification + carbon capture, medium, central | **Absent** |
| `SBIOH2GC01` / `SBIOH2GD01` / `SBIOH2RC01` | Gasification without capture, small decentral, steam reforming | **Absent** |
| `BBLQH2G110` | Black-liquor gasification → H₂ | **Used from 2035** |

`SBIOH2GCC01` is the TIMES analogue of PyPSA `bioH2`; it is in `mapping_tech.csv`
with an empty PyPSA name and this scenario does not invest in it.

`BBLQH2G110` is a pulp-mill closed loop (`INDBLQ` in, `SYNH2CT` + biogenic
`INDCO2b` out):

| | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|
| Capacity (GW) | 0.009 | 0.063 | 0.101 | 0.101 |
| Black liquor in (PJ) | 0.45 | 1.79 | 3.13 | **3.99** |
| H₂ out `SYNH2CT` (PJ) | 0.26 | 1.06 | 1.85 | **2.36** |
| Biogenic CO₂ `INDCO2b` (kt) | 42 | 170 | 298 | **380** |

PyPSA cannot source that residue: the extraction rule for `solid biomass`
**excludes** black liquor on purpose, so PyPSA is not charged a forestry potential
for a mill residue. Even the biomass-H₂ path TIMES *does* use therefore has no
PyPSA twin.

---

## 9. The rest of the PyPSA CCS menu

Switches as inherited by `config.walloon.yaml`, with what they did in the last
solve before `ccgt_cc` existed (22 Aug, DAC still on; system-wide figures from
`results/walloon/scen_demande_haute/csvs/{energy,capacities}.csv`).

| Option | Config | 2025 → 2050 in that solve |
|---|---|---|
| Direct air capture | `dac: true` then; **`false` now** | 0.02 → **1 105 MW**; 0.2 GWh → **23.5 TWh** electricity. BEWAL 2050: 6.14 TWh_th + 2.41 TWh_e → 4.39 Mt captured (2.6× the Walloon 2050 cap) |
| SMR + CCS | `SMR_cc: true` | **< 1 MW**, < 0.4 GWh — unused. Unabated SMR keeps ~14.5 GW |
| Allam cycle | `allam_cycle_gas: false` | Not in the network |
| Coal + CCS | `coal_cc: false` | Off |
| Methanol CCGT + CC | `methanol.methanol_to_power.ccgt_cc: false` | Off |
| BioSNG ± CC | `biosng` / `biosng_cc: false` | Off |
| Biomass-to-liquid + CC | `biomass_to_liquid_cc: false` | Off |
| Biogas upgrading + CC | `biogas_upgrading_cc: false` | Off |
| Biomass → methanol + CC | `methanol.biomass_to_methanol_cc: false` | Off |
| Urban-central **biomass CHP CC** | always added when `chp.enable` | **< 0.2 MW**, ~25 MWh — unused |
| Urban-central **gas CHP CC** | same | Noise until 2050 (**3.4 GW**, 0.53 TWh) |
| **Solid biomass for industry CC** | always added | The one industrial BECCS that binds: 0.2 MW → **36.9 GW**; 0.1 GWh → **32.3 TWh**. See §13 |
| Gas for industry CC | always added | 0.3 MW → **10.4 GW**; 0.1 GWh → **8.9 TWh** |
| Process-emissions CC | always added | 0.8 → 7.8 GW, **energy 0** (built, not used) — the Load has since been corrected, §11.1 |
| CO₂ network | `co2_network: true` | Pipeline capacity 0.25 → 7.1 GW |
| Sequestration limit | see [`co2-sequestration.md`](co2-sequestration.md) | Was a pooled European cap that bound in every horizon; the limiter is now the per-node CO₂StoP store (GB 100 / DE 79 / NL 9 Mt/a, **BE 0**) |

`cc_fraction: 0.9` is the capture rate on SMR CC and `bioH2`. Biomass CHP and
industry CC use the technology-data `capture_rate` of `biomass CHP capture` or
`cement capture`.

---

## 10. Soft-linking: what is and is not transferred

The TIMES→PyPSA transfer is final-energy **demand**, plus the heating mix and the
EV fleet. Electricity *generation* and hydrogen *supply* are re-optimised in
PyPSA. Consequences:

1. **CCGT+CCS activity is not exported**, and should not be — no extraction rule
   reads `ELCHIG` from power plants.
2. The heating payload used to pick up `Thermal Public - Retrofitting CCGT CCS`
   via a `thermal` regex (1 740 MW of power plant counted as heat stock).
   Selection is now an explicit label list
   (`TIMES_PyPSA/times_pypsa/heat_softlink.py`).
3. **`SBIOH2GCC01` is unmapped**; even if TIMES built it, PyPSA would not see it
   as a demand.
4. **Black liquor → H₂ is excluded** from `solid biomass` (§8).

The pipeline is consistent with "PyPSA chooses the supply mix". It is **not** yet
consistent with "both models may use the same CCS plants": TIMES retrofits CCGT
from 2035 and runs black-liquor H₂ from 2035; PyPSA has new-build CCGT-CC and
keeps `bioH2` off.

---

## 11. The Walloon industrial capture chain

Retired here on 2026-09-08 from the 27 Aug / 1 Sept meeting worklist
(`docs/temporary_improvement_plans.md`, deleted; recoverable with
`git show 64d084c4:docs/temporary_improvement_plans.md`). Item and B-numbers cited
in the code refer to that worklist and are kept as labels.

### 11.1 The process-emissions Load is **gross**, not the atmosphere residual (item 12 / B4)

TIMES splits process CO₂ into two commodities: `INDCO2P`, emitted to the
atmosphere, and `INDCO2c`, produced by the CC process variants (`ICMPRDCC_02`,
`ILMQLMPRCC02`, `IGFFLATOXYCC01`, `IGHHOLLOWOXYCC01`, `IGHOTOCC01`) and consumed
by `STORAGEMININD`. In PyPSA the Load is the input to the process-emissions bus,
**upstream** of `process emissions CC`, so the gross figure is what belongs there.

| kt/a | 2025 | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|---:|---:|
| emitted `INDCO2P` | 4 411.6 | 3 946.1 | 964.4 | 357.0 | 327.5 | 281.6 |
| captured `INDCO2c` = `STORAGEMININD` | 0 | 0 | 4 364.6 | 5 076.9 | 5 120.0 | 4 826.4 |
| **gross = the BEWAL Load** | **4 411.6** | **3 946.1** | **5 329.0** | **5 433.9** | **5 447.5** | **5 108.0** |

Using the emitted figure alone made 2040/2050 15–18× too low and put the §11.2
floor out of reach. The gross load also restores a Walloon process inventory of
the right order — PyPSA-Eur's own default is ~2.0 Mt in every horizon, so TIMES is
~2.7× higher, not 5–6× lower. Guard: `test/test_process_emissions_load.py`.

**Two checks still outstanding.** (i) `INDCO2N` (6.0 → 0.4 Mt) is the *combustion*
CO₂ of the same industrial processes and is correctly excluded, but it has never
been checked against the industrial energy PyPSA imports. (ii) Part of `INDCO2c`
comes from oxy-fuel glass and cement units and may mix process with combustion
carbon; that split has to be settled on the TIMES side before the Load is final
([`co2-sequestration.md`](co2-sequestration.md) §12 item 7).

### 11.2 The capture floor (item 9 / B3)

`sector.industry_cc_floor` imposes TIMES's `STORAGEMININD` as a minimum on BEWAL
`process emissions CC` + `solid biomass for industry CC` + `gas for industry CC`,
from `data/walloon/times_industrial_capture.csv` (4 365 / 5 077 / 5 120 / 4 826 kt
in 2035/40/45/50). Port mapping and units are in `named_pins.py`.

The floor is only reachable **because** the inventory is gross: process capture
alone gives 5 434 × 0.95 = 5 162 ≥ 5 077 kt in 2040 and 5 108 × 0.95 = 4 853 ≥
4 826 in 2050, which is how TIMES builds it; biomass and gas CC add ~3.5 Mt of
headroom. Against the *net* inventory the ceiling was 4.45 Mt in 2040 and 3.77 in
2050 even with 100 % of Walloon industrial gas and biomass routed through capture
— short by 0.6 and 1.1 Mt, and it failed the run at 2040. Guard:
`test/test_industry_cc_floor.py::test_floor_fits_the_process_inventory`.

> Like the PV rooftop share, this CSV is extracted from the `.vd` **by hand and is
> not a declared output of any rule**. Re-extract it whenever `sector.times_file`
> changes.

### 11.3 What the 2026-09-07 run captured

| Mt/a at BEWAL | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| `process emissions CC` | 2.162 | 3.602 | 5.052 | 4.856 |
| `solid biomass for industry CC` | — | 1.658 | 1.853 | 1.419 |
| `gas for industry CC` | — | 0.876 | 1.260 | 0.820 |
| `CCGT CC` | — | — | 0.638 | 1.123 |
| `urban central gas CHP CC` | — | — | — | 1.370 |
| **total** | **2.162** | **6.136** | **8.802** | **9.588** |

The floor is met with headroom (8.17 Mt of the three floored carriers in 2040
against 5.08; 7.09 against 4.83 in 2050) — and it stays slack in the later cabinet
batch too, so **the floor is not what drives the capture volume**
([`co2-sequestration.md`](co2-sequestration.md) §10.2).

---

## 12. Capture gating on power and CHP plants

**Built 2026-09-05, shipped OFF, and it stays off.**
`sector.power_plant_cc_from_year` is `null` in `config/config.walloon.yaml` and
the `config:sector.power_plant_cc_from_year` row in
`config/input_parameters_for_models.csv` is `status: pending`, so the option is
inert and no published result depends on it.

When enabled, capture fitted to *power and CHP plants* is unavailable in every
horizon before the configured year — `CCGT CC`, `urban central gas CHP CC`,
`urban central solid biomass CHP CC`, `waste CHP CC`, `coal CC` and the Allam
cycle get `p_nom_max = 0` (`scripts/walloon_scripts/power_plant_cc.py`). To
enable, flip the row to `status: active` and run
`build_common_parameters.py --write`; that is an LP change and needs its own run
and log. Guard: `test/test_power_plant_cc.py`.

**Industrial capture is deliberately excluded** — `process emissions CC`,
`solid biomass for industry CC`, `gas for industry CC` and `SMR CC` are what
§11.2's floor is built from, and gating them would contradict it.

**Effect on results: none.** The 2026-09-07 run builds no power-plant CC before
2040 anyway (`CCGT CC` 0 / 0 / 327 / 882 MW_e; `urban central gas CHP CC` only in
2050), so the option guards a counterfactual. Note the tension with the 27 Aug
meeting item *"CCGT-CC apparaît seulement en 2050 ⇒ impose the TIMES capacity in
2040?"*, which asks to **add** CCGT CC in 2040: this option permits that and does
not address it.

---

## 13. The 2050 biomass corner: industrial capture eats the whole European resource

Measured on the 2026-09-07 run and confirmed in **all 14** scenarios of the
cabinet batch. The EU-wide `biomass limit` binds in every horizon at −47.4 /
−38.5 / −30.5 / **−1 086.8** EUR/MWh (−1 087 to −1 308 across the batch), and
every solid-biomass bus prices at 1 104–1 133 EUR/MWh in 2050.

The mechanism is exact. In 2050 the entire 330.92 TWh potential goes to one place
— exogenous industrial solid-biomass demand of 303.19 TWh — split 277.36 TWh
through `solid biomass for industry CC` (η 0.90) and 53.56 TWh through the plain
link (η 1.00). One extra MWh of biomass therefore lets **9 MWh** of that demand
switch from the η 1.0 link to the η 0.9 CC link, each capturing ~0.35 tCO₂ at a
407 EUR/t global dual ≈ 1.3 kEUR. The dual is a real LP property, not solver
noise.

Consequences, all reporting-relevant:

- Nothing is left for CHP, boilers, biomass-to-liquid or biomass-to-methanol — in
  2040 those still took 62 TWh.
- **~27.7 TWh of the European potential (8 %) is burned as the CC parasitic loss**
  (the 10 % efficiency penalty on 277 TWh) to earn the credit.
- The **option-B′ absorber penalty of 1 000 EUR/MWh_th is now below the fuel's
  shadow price**, so the solver pays the penalty and drops the pin — that is the
  2050 rural / urban-decentral biomass-boiler relaxation. Any future 2050 pin on a
  scarce fuel will be bought out the same way; see
  [`heat-softlink.md`](heat-softlink.md) §9.
- 61.9 TWh of *regional* `e_sum_max` sits unused (FR 43.0, DE 11.4, BEWAL 4.45 +
  3.00 transported) because the EU aggregate binds first. **A slack Walloon
  biomass row in 2050 is not a Walloon result** — the split across regions is
  degenerate.
- The whole picture rests on `sector.solid_biomass_import: false`. With no import
  channel and an inelastic industrial demand, the price of the marginal MWh has no
  anchor.

**Check this dual before trusting any 2050 solve.** Making capture more expensive
changes *which* technology captures, not whether biomass binds.

---

## 14. Open decisions

1. **CCGT retrofit vs new-build — decided 2026-08-26: the floor is
   technology-neutral.** The 1 740 MW_e Walloon floor moved from
   `potential:BEWAL:CCGT:p_nom_min` (a floor on *unabated* CCGT, written onto the
   new vintage of `custom_potentials.csv`) to `agg:BEWAL:CCGT-all:min` in
   `agg_p_nom_minmax_*.csv`. Because `agg_ccgt` folds `CCGT` and `CCGT CC` into
   `CCGT-all`, the adequacy requirement no longer picks the technology.

   Why it had to change: under the old floor
   ([`2026-08-25`](logs/2026-08-25_scen_demande_haute_2010_1h.md)) 1 740 MW_e of
   *unabated* CCGT was forced into Wallonia at every horizon — 5 640 MW_e of fleet
   by 2050 — leaving no residual demand for capture, so Wallonia built **0 MW of
   CCGT CC** while Germany built 8 465 MW_e and Brussels 1 116 MW_e. The
   technology was not uneconomic: break-even against unabated CCGT was ~103
   EUR/tCO₂ at 4 000 full-load hours, against a global CO₂ dual of 625 EUR/t. It
   was crowded out by the mandate.

   This is still not a retrofit (§6 item 2): `CCGT CC` is new-build only, so a
   technology-neutral floor is an exogenous stand-in. It reproduces the TIMES
   *outcome* — captured gas capacity meeting the adequacy requirement — without
   hard-coding it, and it lets the solve say whether capture is worth it.
2. **`sector.bioH2`.** Turning it on would give PyPSA biomass→H₂ **with CCS
   only**, which matches `SBIOH2GCC01` (unused in this TIMES scenario) and does
   **not** match `BBLQH2G110` (the path TIMES actually runs). Enabling it without
   a black-liquor supply leaves the mill loop on the TIMES side only.
3. **DAC.** Off in the Walloon overlay since 2026-08-25 so the menus match. Under
   option B′ with DAC on, the Walloon district-heat expansion largely fed DAC —
   a PyPSA outcome, not a transferred TIMES choice. But see item 5.
4. **CCGT-CC costs.** The composed formula (§2) is authoritative until the shared
   CSV cell is filled. Until then the two models' CCGT-CCS costs are not
   comparable.
5. **Net zero in 2050 needs DAC or less aviation.** With `co2_budget` 2050 set to
   **0.000** the model is **infeasible** — a clean Gurobi primal certificate, with
   a control solve at 0.050 on the identical 2040 inheritance coming back
   feasible, so the cap was the sole cause. The reason is structural: with
   `sector.dac: false` every sink is biogenic and capped at ~127 Mt (336.9 TWh of
   biomass × 0.348 tCO₂/MWh, plus ~9.5 Mt of biogas), against ~230 Mt of realised
   fossil combustion of which **aviation kerosene alone is 106 Mt**. A tonne of
   biogenic carbon can be sequestered *or* displace a tonne of fossil fuel, never
   both — now verified in the price domain, so **Fischer-Tropsch kerosene does not
   help** ([`co2-sequestration.md`](co2-sequestration.md) §8.4). `co2_budget` 2050
   stays at 0.050. **Enable DAC, revisit the exogenous aviation / HVC demand, or
   state that the modelled system does not reach net zero by 2050** — this is not
   a cap that can be tightened.

---

## 15. Recommendations to align the two models

Technology side only; the disposal-side plan is in
[`co2-sequestration.md`](co2-sequestration.md) §10 and §12.

1. **Give PyPSA a CCGT-CC retrofit option, or label the stand-in.** TIMES
   retrofits 1.74 GW from 2035 at ~86 % capture; PyPSA can only build greenfield
   CCGT-CC, which is more expensive per kW (§6 item 2). The technology-neutral
   `CCGT-all` floor reproduces the *outcome* but not the *economics*. Either add a
   retrofit Link with `p_nom` tied to existing capacity, or label every CCGT-CC
   cost comparison as greenfield-vs-retrofit.
2. **Fill the shared CCGT-CCS cost row.** `input_parameters_for_models.csv`
   (*Centrale à cycle combiné avec captage et stockage de CO₂*) is still empty, so
   the two models cannot be compared on this technology at all (§5, §6 item 4).
3. **Decide one capture-rate convention.** PyPSA uses 0.95 on `CCGT CC` (from
   `biomass CHP capture`); TIMES uses ~0.86 on the E12/E13 retrofits. Both are
   defensible; they should not differ by accident.
4. **Add the reboiler steam penalty, or state its absence in every result**
   (~7 pp on η, §6 item 1). It makes PyPSA's CCGT-CC systematically cheaper per MWh
   than both the literature and the TIMES retrofit.
5. **Replace the Allam cost row before Allam is ever compared with CCGT-CC**
   (§3). At 60 % efficiency and 1 886 EUR/kW it is friendlier than the engineering
   literature, which is why the option is currently off.
6. **Reconcile the power-vs-industry capture split, not the total**
   ([`co2-sequestration.md`](co2-sequestration.md) §6.3). The totals already agree
   to ~20 %; TIMES puts ~2× more on power and PyPSA ~60 % more on industry. That
   is a difference in *where the capture infrastructure goes*, not in ambition,
   and it is the one worth resolving.
7. **Settle the oxy-fuel process/combustion split** on the TIMES side (§11.1): it
   changes the gross `process emissions` Load PyPSA receives and hence the
   reachability of the §11.2 floor.
8. **Decide whether DAC stays off.** It is off purely for menu alignment, but it
   is also the only technology that can close the 2050 net-zero gap (§7, §14
   item 5). If net zero is a deliverable, the alignment argument loses.

---

## 16. Files touched

Implementation, 2026-08-25:

| File | Change |
|---|---|
| `scripts/prepare_sector_network.py` | `CCGT_CC_CAPTURE_TECH`, `ccgt_cc_link_params`, `add_ccgt_cc`; called when `sector.ccgt_cc` |
| `scripts/lib/validation/config/sector.py` | `ccgt_cc` Field |
| `config/config.default.yaml` | `ccgt_cc: false` (DAC stays the PyPSA-Eur default `true`) |
| `config/config.walloon.yaml` | `ccgt_cc: true`, **`dac: false`** |
| `config/schema.default.json`, `config/schema.json` | schema for the new key |
| `config/plotting.default.yaml` | colour + nice name |
| `scripts/solve_network.py` | `CCGT CC` in the `agg_ccgt` rename |
| `scripts/walloon_scripts/review_run.py` | `LINK_AGG` |
| `scripts/walloon_scripts/calculate_costs.py` | CCS bucket no longer matches every CCGT |
| `config/input_parameters_for_models.csv` | placeholder notes point here |
| `test/test_ccgt_cc.py` | algebra, four-bus wiring, cost-row guard, categorise |

Technology-neutral gas floor, 2026-08-26 (§14 item 1):

| File | Change |
|---|---|
| `data/walloon/custom_potentials.csv` | dropped the four `BEWAL,CCGT,p_nom_min` rows |
| `data/walloon/agg_p_nom_minmax_*.csv` | added `BEWAL,CCGT-all` min = 1 740 at every horizon |
| `config/input_parameters_for_models.csv` | *Minimum CCGT installé* retargeted to `agg:BEWAL:CCGT-all:min` |
| `scripts/walloon_scripts/BEWAL_potentials.py` | `apply_link_p_nom_min` — floors are fleet-wide, not per-vintage |
| `test/test_common_parameters_agg.py` | `test_walloon_gas_floor_is_technology_neutral` |

No full Snakemake solve accompanied either change. Checks: `test/test_ccgt_cc.py`,
`test/test_config_schema.py`.

---

## 17. Reporting (pypsa2html)

pypsa2html is a general-purpose library, so `CCGT CC` is **not** hardcoded.
PyPSA-Eur names capture siblings `{tech} CC` and the reporter treats that suffix
as a convention (pypsa2html `docs/DESIGN_DECISIONS.md` D17).

| Chart | What you get when the network has `CCGT CC` |
|---|---|
| Capacities (stacked) | Own bar, colour `#c44c3a` |
| Capacities (faceted) | Extra series on the CCGT panel |
| Costs / map | Grouped with fossil power (any name containing `CCGT`) |
| Electricity Sankey | Generation and losses fold onto the existing gas-power codes (`proelcgaz`, `lossgas`) |
| Carbon Sankey | Residual stack emissions fold onto `emmccgt`; captured CO₂ is `emmccgtcc` (gas → stored); sequestration includes the stored port either way |

To wire a *new* `{fuel} CC` plant into the carbon Sankey captured-CO₂ edge, add
one `carrier_flows_carbon.csv` row (`{tech} CC_2` → a code) and one
`processes_carbon.csv` edge to `stm`. Residual emissions and energy flows inherit
from the parent automatically. Do not add `if carrier == "CCGT CC"` in Python.
