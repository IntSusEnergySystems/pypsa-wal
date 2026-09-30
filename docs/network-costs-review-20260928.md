# Network costs in PyPSA-Wal: diagnosis, calibration and coupling with TIMES

**Scope:** electricity distribution, electricity transmission, gas distribution and
transmission, H₂ and CO₂ pipelines.

**Status:** implemented and solved. The calibration is part of the base configuration
(every scenario), and `scen_central` has been re-solved with it: 1 h resolution, weather
2010, NIC5. The run is documented in
[`logs/2026-09-29_scen_central_2010_1h_netcal.md`](logs/2026-09-29_scen_central_2010_1h_netcal.md).
Results are in §9.

**History:**
* 2026-09-28: diagnosis written in response to stakeholder feedback on the September
  cabinet deck ("Distribution / Transport / Nucléaire").
* 2026-09-29: calibration decided and implemented.

**Trigger.** The feedback compared the *Distribution* and *Transport* bars of the chart
« Coûts totaux du système wallon par segment » with the CWaPE-approved authorised
revenues of the Walloon DSOs:
* 981 M€ of DSO revenue in 2029, against a 0.4 bn€ bar;
* Elia's investment programme against the *Transport* bar.

It asked:
* whether gas was in the distribution bar;
* how distribution, transmission and gas networks are represented and costed, in PyPSA
  and in TIMES;
* how transmission costs are split between nodes.

This document records the answers, the calibration decisions taken to fix the current
three-node formulation, the data behind each decision, the implementation, and the link
with TIMES, which will report the effect of the scenarios on energy bills.

---

## 0. Summary

**What was wrong**
* **The *Distribution* bar mixed gas and electricity.** ClimAct's extraction added a gas
  slice computed from its own cost file.
* **The electricity distribution grid was valued at ⅓ of its regulated cost.** The
  existing grid was built "from scratch" in 2025 at an undocumented placeholder cost
  (668 €/kW, "TODO" in technology-data), sized at the regional coincident peak, with
  2 %/a of OPEX. The DSOs' operating costs alone are 4.7× that OPEX.
* **The *Transport* bar pooled the whole six-country grid** and split it by connected
  capacity, which doubled Wallonia's share. 31 % of it was CO₂ pipelines.
* **Transmission was far from the regulated benchmark:**
  * the internal Elia grid (380–36 kV) was absent;
  * system services were absent;
  * interconnectors were costed on centroid-to-centroid lengths;
  * a bug charged every HVDC converter twice from the second horizon on.
* **Gas distribution had no network.** Instead there was a charge on new gas boilers
  equal to the electricity distribution cost.
* **TIMES carries no network cost in its grid processes.** Its sectoral "Fuel Tech"
  mark-ups (e.g. 179.5 €/MWh on residential electricity) look like tariffs plus taxes.

**What was decided and implemented**

| network | decision | where |
|---|---|---|
| all | Split every network cost into the existing grid (L1), the increment (L2), non-capacity OPEX (L3) and add-ons (L4). L1 is calibrated on the **2025** regulated accounts. Only L2 and losses are endogenous | §2 |
| all | Annualise regulated network assets at **3.5 % real** (the regulated return), not the 7.5 % power-sector hurdle | §3 |
| electricity distribution | Increment at **620 €/kW** of regional peak, calibrated on the DSOs' transition capex 2026–30 | §4 |
| electricity distribution | **70 %** of industrial electricity moved to HV (TIMES split) | §4 |
| electricity distribution | Losses **5 %** (TIMES) | §4 |
| electricity distribution | **120 €/kWp** hosting charge on new rooftop PV | §4 |
| gas distribution | Existing grid as a fixed block (**282 M€**, CWaPE 2025). The boiler charge is reduced to its avoidable part (**factor 0.12**, ≈ 5 €/kW_th/a) | §5 |
| transmission | HVDC double-counting fixed | §6.2 |
| transmission | New AC branches at **450 → 372 €/MW/km** (ACER level, DEA learning shape) | §6.5 |
| transmission | ALEGrO at its project cost | §6.5 |
| transmission | Economies of scale on large CO₂ trunks | §6.5 |
| transmission | Regional reporting in a **direct** view (50/50 per branch) and a **tariff** view (Walloon share of Elia/Fluxys revenue) | §6.3 |
| TIMES | A harmonisation table checks volumes, prices, network revenue requirements against the mark-ups, and support needs, run after every solve | §8 |

§9 has the effect on the central scenario, §11 the open data requests, and §12 the
formulation improvements left for the multi-node phase.

---

## 1. Context and diagnosis

### 1.1 The cost chart and its two network bars

The chart is drawn by
[`plot_cost_segments.py`](../scripts/walloon_scripts/plot_cost_segments.py) from
ClimAct's extraction (`explorer/pypsa/costs_segments.csv`). Rebuilt to the euro for the
September cabinet central run (networks of 2026-09-15), BEWAL, M€/a:

| *Distribution* bar | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| electricity distribution link (PyPSA objective) | 250.7 | 320.4 | 520.8 | 683.5 |
| gas slice recomputed by the extraction | 64.6 | 54.3 | 46.7 | 26.8 |
| OPEX on the link | 0.2 | 0.5 | 0.8 | 1.3 |
| **bar** | **315.5** | **375.2** | **568.3** | **711.5** |

The gas slice does not come from the model. The extraction uses its own
`data/costs/CZ/costs_2025.csv`: 500 €/kW at 7 %, with a factor `nyears = 1/3` that has
no counterpart in PyPSA. The model itself charged 66.4 €/kW/a on new boilers only.

| *Transport* bar, BEWAL, CAPEX M€/a | ClimAct rule: 2025 / 2030 / 2040 / 2050 | 50/50 per branch: 2025 / 2030 / 2040 / 2050 |
|---|---|---|
| electricity (AC + DC) | 189.4 / 256.0 / 300.4 / 274.4 | 87.6 / 135.4 / 164.2 / 154.6 |
| methane pipelines | 41.7 / 41.7 / 41.7 / 42.5 | 13.8 / 13.8 / 13.9 / 14.6 |
| H₂ pipelines | 48.6 / 54.1 / 59.3 / 69.5 | 17.3 / 18.6 / 22.7 / 29.9 |
| CO₂ pipelines | 3.2 / 155.2 / 186.0 / 333.2 | 3.2 / 77.9 / 82.2 / 142.5 |
| **total** | **282.9 / 507.0 / 587.4 / 719.6** | **121.9 / 245.7 / 283.0 / 341.6** |

ClimAct's `distribute_transmission_costs` pools every branch of the six-country system
per carrier, then splits the pool by each node's share of connected capacity, ignoring
length. Wallonia thereby pays a share of FR–DE and GB–FR.

### 1.2 The regulated benchmarks

**Walloon electricity DSOs.** Five CWaPE decisions (Appendix A). M€ nominal:

| | 2025 | 2029 |
|---|---:|---:|
| authorised revenue | 896.3 | 981.3 |
| network core (OPEX + capital charges) | 677.9 | 735.3 |
| of which capital charges (depreciation + margins + corporate tax) | 390.5 | 432.3 |
| of which controllable OPEX | 287.4 | 303.0 |
| losses / PSO / road-use fee / smart meters / other | 87.0 / 45.0 / 43.8 / 22.9 / 19.8 | 80.6 / 47.5 / 48.4 / 57.0 / 12.6 |

**Investment is rising fast.** CWaPE opinion CD-25k27-CWaPE-0967 (Tableau 14) puts the
DSOs' gross investment at 302 M€/yr in 2020–24 and **662 M€/yr in 2026–30** (+119 %).
Tableau 15 splits the 3.3 bn€ of 2026–30 by driver:

| driver (CWaPE motivation codes) | M€ over 2026–30 |
|---|---:|
| transition: E1.1 load and peaks, E1.3 congestion, E1.4 voltage quality, government transition subsidy | **774** |
| new connections (E1.2.x) | 798 |
| renewal and compliance (E2.1–E2.6, E2.8, E1.5) | 1 136 |
| smart meters (E2.7) | 601 |

**Walloon gas DSOs.** ORES gaz + RESA gaz, CD-24c28-CWaPE-0890/0891:

* authorised revenue: 335.0 M€ in 2025, rising to 354.9 M€ in 2029;
* network core: 282.0 M€;
* RAB: 1 866 M€ at 1 January 2025;
* physical base (CD-26g30-CWaPE-0981): 801 102 meters, 17 426 GWh, 14 497 km of mains;
* gross capex: 117.4 M€ in 2025, and 104.6 M€/yr planned for 2027–31.

**Elia.** CREG (B)658E/85, Tableau 1bis:

* allowed revenue for all Belgian voltages: 970.7 / 1 552.1 / 1 706.4 / 1 876.0 M€ for
  2024–27;
* 2022 actual structure: grid capital 425 M€, controllable OPEX 389 M€, ancillary
  services 547 M€, interconnection income −422 M€;
* 6.4 bn€ investment programme for 2024–27.

The Walloon 30–70 kV plan is 691 M€ over 2026–30 (CD-26g30-CWaPE-1283). Elia realises
48 % of such plans on an 11-year average.

### 1.3 Why the model was low

Against the like-for-like electricity bar, 320 M€ in 2030, the regulated revenue is 3.1×
higher, and its network core 2.3×. The decomposition:

1. **OPEX.** The DSOs spend 303 M€; the model's 2 %/a FOM covers 64 M€. Much of the DSO
   OPEX scales with connections (meter, customer, IT), not with peak.
2. **Valuation of the existing grid.** The link starts at zero in 2025 and builds the
   whole grid at 668 €/kW of *regional coincident* peak. Its replacement value in the
   model, 2.5 bn€, is below the regulator's net book value of 3.8 bn€.
3. **Scope.** All industry electricity sat behind the DSO link, although about 70 % is
   drawn at HV. Meanwhile the 150/70/36 kV grid was neither transmission nor
   distribution in the model.
4. **No renewal** of ageing assets. Nothing retired before 2065.
5. **Items outside a system-cost model:** losses, PSO, road-use fee, smart meters.

The increment was low too, but by less. The model built 0.7 bn€ of new distribution
capacity to 2030, against 3.3 bn€ of planned DSO capex. Most of that capex, however, is
renewal and connections, not load growth.

### 1.4 How TIMES represents networks

**Grid processes carry losses only.** TIMES-WAL's grid processes (`EVTRANS_H-H`,
`EVTRANS_H-M`, `EVTRANS_M-L`, `EVTRANS_L-M`) have no cost or capacity in the `.vd`.
Their implied losses are 1.6 % (HV), 2.7 % (HV→MV) and 3.2 % (MV→LV).

**Delivery costs are volumetric mark-ups** on sectoral "Fuel Tech" processes, in
€₂₀₂₁/MWh, constant from 2025 to 2050:

| process | €₂₀₂₁/MWh |
|---|---:|
| `RSDELC00` residential electricity | 179.5 |
| `COMELC00` services electricity | 94.1 |
| `INDELC00` industry electricity | 24.6 |
| `AGRELC00` agriculture electricity | 91.7 |
| `RSDGMX00` residential gas | 33.8–57.6 |
| `COMGMX00` services gas | 13.2–37.0 |
| `INDGMX00` / `INDGAS00` industry gas | 6.6 |

TIMES's residential electricity price is its LV commodity marginal plus the mark-up. The
mark-ups sit in TIMES's objective and therefore steer its technology choices. Whether
they contain network tariffs, taxes or both is to be confirmed by ICEDD (§11).

---

## 2. Calibration principles

**1. Four cost layers per network.**

| layer | content | treatment | drives decisions? |
|---|---|---|---|
| **L1 — existing grid** | capital charges of the assets in service in 2025 | exogenous block, 2025 regulated accounts, constant in real terms | no |
| **L2 — increment** | reinforcement caused by the scenario: peak growth, PV hosting, new branches | endogenous: optimal capacity of the vintages built after the first horizon × annualised unit cost | **yes** |
| **L3 — non-capacity OPEX** | customer service, metering, IT, system operation | exogenous block; the per-connection part is indexed on the connection count | no |
| **L4 — losses, add-ons, transfers** | losses; PSO, road-use fee, smart meters, taxes, system services | losses endogenous through the link efficiency; the rest exogenous, for bills | losses only |

**2. Calibrate on 2025, validate on 2029.** The 2029 revenue already contains the capital
charges of the 2025–28 transition investments, which the model builds as L2.

**3. Two views of transmission** (§6.3):
* the **direct** view, the physical cost of the branches touching the region;
* the **tariff** view, what Walloon users pay under Elia's national postage stamp.

**4. Price base.**
* Model costs are real EUR2025, and CWaPE/CREG 2025 figures are nominal 2025 = EUR2025.
* 2029 figures are deflated at 2.4 %/a.
* TIMES is in MEUR21.

**5. The first-horizon vintage of the distribution link is the existing grid.** Its model
cost is reported as a memo line and replaced by L1. Its capacity still constrains the
dispatch, and its cost is a constant in the 2025 objective.

---

## 3. Financial parameters

| parameter | before | decided | basis | where |
|---|---|---|---|---|
| discount rate of regulated network assets | 7.5 % (TIMES power/supply hurdle) | **3.5 % real, pre-tax** | See note below | 17 rows `cost:<tech>:discount rate` in `config/input_parameters_for_models.csv`, generated into `data/walloon/discount_rates.csv` |
| lifetime | 40 y (electricity), 50 y (pipelines) | unchanged | regulatory depreciation 33–50 y | — |
| FOM | 2 % (distribution), 1.5 % (lines, DC, CH₄) | unchanged | DEA | — |

*Basis for the 3.5 %.* CWaPE's 2025–29 methodology allows **4.03 %** on the RAB after
corporate tax (CD-24c28-CWaPE-0890, Tableau 2). Margin plus tax is 5.37 % of the RAB,
pre-tax and nominal, i.e. about 3.3 % real. This equals `costs.social_discountrate` (3.5 %).

*Scope of the 3.5 %.* It applies to `electricity distribution grid`, `HVAC *`, `HVDC *`,
`CH4 (g) pipeline*`, `H2 (g) pipeline*`, `H2 pipeline` and `CO2 pipeline*`.
`electricity grid connection` is paid by the producer and keeps the power hurdle.

Annuity plus 2 % FOM falls from 9.94 % to **6.68 %** of the investment (40 y).
`build_common_parameters.py` handles these per-technology overrides in
`resolve_hurdle_rates`. Its `custom_costs.csv` patcher now skips them, since they
belong to `discount_rates.csv`.

---

## 4. Electricity distribution

### 4.1 Representation in PyPSA

`insert_electricity_distribution_grid` (`scripts/prepare_sector_network.py`) adds per AC
node a `<node> low voltage` bus and an extendable `electricity distribution grid` link
to it. Moved onto the LV bus are:
* the household, services, industry and agriculture electricity loads;
* EV charging;
* heat pumps, resistive heaters and micro-CHP;
* rooftop PV and home batteries.

**What sizes the link.** The link is sized at the hourly *regional coincident* net peak
behind it. In practice it never exports: a single hour in four horizons. Heat pumps are
almost fully coincident even locally: Consentec for E.ON uses simultaneity 1.0 at LV,
0.95 at MV/LV and 0.9 at MV. EV and PV effects, by contrast, are local.

**What stands behind the peak.** At the 2025 BEWAL peak (15 Sep networks, before the
industry split):

| | 2025 peak |
|---|---:|
| household and services | 1 721 MW |
| industry | 979 MW |
| resistive heating | 653 MW |
| heat pumps | 258 MW |
| rooftop PV | 0 |

In 2050, home batteries shave 1.4 GW off the peak.

### 4.2 Data

| item | value | source |
|---|---|---|
| authorised revenue 2025 / 2029 | 896.3 / 981.3 M€ | CWaPE decisions (Appendix A) |
| network core 2025 | 677.9 M€: capital 390.5, OPEX 287.4 | idem |
| RAB (derived) | 3.10 bn€ + 0.67 bn€ revaluation | margins ÷ 4.03 % |
| connections | 1.95 M EAN (2024), +1.0 %/yr | CWaPE 0967 §2.3.4 |
| energy withdrawn at distribution | 12.68 TWh (2024) | idem |
| gross capex 2020–24 / 2026–30 | 302 / 662 M€/yr | CWaPE 0967 Tableau 14 |
| transition capex 2026–30 | 774 M€ (903 incl. voltage harmonisation) | CWaPE 0967 Tableau 15 |
| TIMES HV / MV / LV split | industry 70 % at HV in every horizon; losses 2.7 % HV→MV, 3.2 % MV→LV | `scen_central_v01_260911_1109.vd` and `…260923_2_2309.vd` |
| sub-hourly peak | 15-min national peak 0.6 % above the hourly one | Elia open data `ods001`, 2024 (81.0 TWh) |

### 4.3 Decisions

| id | parameter | before | decided | method | implementation |
|---|---|---|---|---|---|
| E1 | existing-grid capital charges | implicit: 3.78 GW × 66.4 €/kW/a = 251 M€ | **390.5 M€/a**, constant real | CWaPE 2025 budgets | reporting, `network_cost_report.py` (L1) |
| E2 | existing-grid OPEX | 2 % FOM | **287.4 M€/a**: asset share 48 %; the per-connection part 52 % grows +1 %/yr with EAN | asset part = 1.5–2 % × replacement value (5.6–9.4 bn€, §4.4) | reporting (L3) |
| E3 | renewal of the existing grid | none | L1 held constant in real terms (renewal ≈ depreciation) | renewal and compliance capex 227 M€/yr vs depreciation 197 M€/yr | reporting |
| E4 | discount rate / lifetime | 7.5 % / 40 y | 3.5 % / 40 y | §3 | master CSV |
| E5 | incremental cost *c*<sub>inc</sub> | 668 €/kW (technology-data "TODO") | **620 €/kW (410–960)** → 41.4 €/kW/a | See note below | master CSV `cost:electricity distribution grid:investment` → `custom_costs.csv` |
| E6 | load behind the link | all industry on LV | **70 % of `industry electricity` on the transmission bus**, at every node | TIMES `VAR_FIn` on `ELCHIGG` vs `ELCMED` (5.8/8.3 TWh in 2025, 16.2/23.2 in 2050) | `split_industry_electricity` (config `sector.network_calibration.industry_hv_share: 0.70`) |
| E7 | distribution losses | 3 % | **5 %** (`efficiency_static: 0.95`) | TIMES: LV delivery 0.973 × 0.968, MV 0.973, weighted by 2025 volumes = 0.949. Check: 5 % × 14 TWh × ~120 €/MWh ≈ 84 M€ vs 87 M€ of DSO loss purchases | config `sector.transmission_efficiency` |
| E8 | PV hosting cost | 0 | **120 €/kWp** on *new* rooftop PV → +8.0 k€/MW/a | the PV share of E5 over 1.58 GWp of new rooftop PV 2025–30. Bounds 32 €/kWp (PV-specific capex) and 189 €/kW (DEA local reinforcement) | `add_rooftop_pv_hosting_cost` (`pv_hosting_investment: 120`) |
| E9 | local-vs-regional diversity | 1 | **1** | E5 is per kW of regional peak, so diversity is inside it; the sub-hourly effect is 0.6 % | — |
| E10 | flexibility credit of home batteries | 1 (implicit) | **1**, not activated | no data to set it below 1 | future work (§12) |
| E11 | regulated add-ons | absent | PSO, road-use fee, smart meters, other: 2025 budget, then 2029 deflated | CWaPE | reporting (L4), bills (§8) |

*Method for E5.* The 774 M€ of transition capex (CWaPE Tableau 15) is divided over the
model's 2025→30 BEWAL LV peak increase after E6 (0.94 GW). 25 % of the capex is
attributed to PV hosting (E8):

| PV share of the transition capex | *c*<sub>inc</sub> | *c*<sub>host</sub> |
|---:|---:|---:|
| 0 | 823 €/kW | 0 |
| **0.25 (decided)** | **618 €/kW** | **123 €/kWp** |
| 0.5 | 412 €/kW | 246 €/kWp |

The decided value, rounded to 620 €/kW, lands close to technology-data's 668 €/kW, whose
source field reads "TODO". That value is the undocumented 500 €/kW of PyPSA-Eur-Sec
indexed to 2025; the new one is calibrated. The literature range is 189 €/kW (DEA,
local reinforcement per new connection) to about $580–1 320/kW (US full
electrification).

### 4.4 Parameters without direct data

| parameter | method used | value | to be replaced by |
|---|---|---|---|
| PV share of transition capex | bracket 0–0.5. Only E1.4 and the ORES PV task force are PV-specific, while E1.1 mixes PV, EV and heat pumps | 0.25 | the DSOs' split of E1.1 (§11) |
| DSO coincident peak | model LV peak after E6 | 3.09 GW (2025) | Synergrid / ORES peak data |
| OPEX split, asset vs connection | FOM × replacement value | 48 % / 52 % | DSO cost accounting |
| replacement value | 1.5–2.5 × net book value (3.77 bn€) = 5.6–9.4 bn€. Its annuity at 3.5 %/40 y (262–440 M€) brackets the 390 M€ of capital charges | ≈ 7.5 bn€ | network length by voltage × unit costs |
| local diversity | embedded in E5 | 1 | smart-meter data (ORES digital twin) |

### 4.5 Validation

| id | check | target | result |
|---|---|---|---|
| V1 | reported 2025 cost, L1 + L3 | 678 M€ | by construction |
| V2 | new-build 2025→30, overnight | ≈ 0.77 bn€ | §9 |
| V3 | energy through the link, 2025 | ≈ 14–15.5 TWh (TIMES MV + LV 14.1 TWh; DSO withdrawals 12.7 TWh + compensated volumes + losses) | §9 |
| V4 | loss cost | ≈ 87 M€/a | §9 |
| V5 | 2030 reported cost vs the CWaPE 2029 core in real terms (≈ 680 M€₂₀₂₅) | ±10 % | §9 |

---

## 5. Gas distribution

### 5.1 Representation

There is no gas distribution network in the model. `insert_gas_distribution_costs` adds
`gas_distribution_grid_cost_factor` × the electricity distribution annuity to the capital
cost of new decentral gas boilers and micro-CHP. Existing boilers, industry and CHP carry
nothing.

Before the calibration (factor 1.0, i.e. 66.4 €/kW_th/a) this charge:
* followed boiler sales rather than the grid;
* reached 196 M€/a in 2040, while gas volumes collapse;
* vanished whenever boilers were not replaced.

TIMES charges gas delivery by volume (§1.4).

The literature treats gas distribution as a **fixed cost that persists until physical
decommissioning** and is recovered through tariffs that rise as volumes fall:
* Agora/BET/Rosin Büdenbender (2023): more than 90 % of the German grid is not needed by
  2045, and grid fees rise 9–16× by 2044;
* Ofgem RIIO-3 [S]: charges rising to 40 p/kWh by 2050.

### 5.2 Data

| item | value | source |
|---|---|---|
| authorised revenue 2025 | 335.0 M€: ORES 218.5 + RESA 116.5 | CD-24c28-CWaPE-0890/0891 |
| network core 2025 | 282.0 M€: capital 193.1, OPEX 88.9 | idem |
| road-use fee / PSO / other | 25.8 / 22.7 / 4.6 M€ | idem |
| RAB 1 Jan 2025 | 1 866 M€ + 0.33 bn€ revaluation; return 4.03 % | idem, Tableau 2 |
| meters / energy / mains | 801 102 / 17 426 GWh / 14 497 km | CD-26g30-CWaPE-0981, Tableau 2 |
| capex 2025 / planned 2027–31 | 117.4 / 104.6 M€/yr, against 92.2 M€/yr of depreciation | idem, §4.1 |
| decommissioning per connection | 930 (seal) – 1 750 € (remove) | Verbraucherzentrale NRW survey [S] |

### 5.3 Decisions

| id | parameter | before | decided | implementation |
|---|---|---|---|---|
| GD1 | existing gas grid (L1 + L3) | absent | **282.0 M€/a**, constant real (*keep* pathway: capex ≈ depreciation, RAB roughly flat) | reporting |
| GD2 | avoidable cost per customer | 66.4 €/kW_th/a (factor 1.0) | **≈ 5 €/kW_th/a** (factor **0.12**) | config `sector.gas_distribution_grid_cost_factor` |
| GD3 | scope of GD2 | new decentral boilers, micro-CHP | unchanged; existing boilers are sunk | — |
| GD4 | decommissioning | absent | 1 340 €/connection (midpoint); **not applied yet**, because TIMES provides no disconnection series | calibration table |
| GD5 | tariff per MWh | flat TIMES mark-up | GD1 ÷ distributed volume (the death-spiral indicator) | `bill_harmonisation.py` (§8) |
| GD6 | losses | absent | absent (negligible in cost) | — |

*Method for GD2.* Controllable OPEX is 111 €/meter/yr, about half of it
customer-driven; adding the meter annuity gives 50–110 €/meter/yr. Divided by the
16.2 kW_th of BEWAL boiler capacity per meter, that is 3–7 €/kW_th/a. Against the
recalibrated 41.4 €/kW/a annuity, the factor is 0.12.

The ClimAct gas slice is no longer used. The calibrated *Distribution* segment carries
GD1, and `plot_cost_segments.py` puts the slice back into the boilers it was taken from.

### 5.4 Validation

* **Level.** GD1 + GD4 against the CWaPE core. This holds by construction for 2025.
* **Tariff trajectory.** Checked against the TIMES residential and services gas volumes
  (§9). With a flat core block, the per-MWh network cost rises as volumes fall.

---

## 6. Transmission: electricity, methane, H₂ and CO₂

### 6.1 Representation and unit costs

Only the **inter-node** branches are costed:
* 3 Belgian regions plus one node per neighbouring country;
* existing and new capacity alike, at replacement-value annuities;
* lengths are centroid distances × 1.25.

The internal 380/220/150/70/36 kV grid disappears in the clustering. OPEX is a 1.5 %/a
FOM. Losses are physical (AC loss linearisation; DC 2 % + 2.3 %/1000 km). There are no
reserves, redispatch or other system services.

| unit cost | before | decided | source |
|---|---|---|---|
| HVAC overhead, 2030 / 2040 / 2050 | 750 / 680 / 620 €/MW/km (DEA) | **450 / 408 / 372 €/MW/km** | See note below |
| HVDC converter pair | 640 → 540 €/kW | unchanged | ACER 0.21 M€/MW is ambiguous between per station and per pair |
| H₂ pipeline | 382 €/MW/km (EHB 2021) | unchanged | EHB 2022 is cheaper for large pipes but dearer per MW for the 0.1–1.7 GW pipes the model builds. A linear cost cannot follow the size class |
| CO₂ pipeline | 2 672 €/(t/h)/km (DEA 12″) | economies of scale on large trunks (TR12) | JRC 0.62–0.89 M€/km |

*Basis for the HVAC value.* ACER UIC 2026 gives a median of 1.18 M€/km for a 400 kV
double circuit, i.e. about 350 €/MW/km, plus substations. The 2040/2050 values follow
technology-data's DEA learning shape. DEA is kept as the high sensitivity.

### 6.2 HVDC converter double-counting (fixed)

**The mechanism.** `lossy_bidirectional_links` gives every DC link a zero-length
`-reversed` twin with `capital_cost = 0`. `add_brownfield` then re-runs
`set_transmission_limit` for each horizon after the first, and `set_transmission_costs`
re-priced every `carrier == "DC"` link, twins included, at the converter-pair annuity.

**The size.** It added, system-wide in 2030 / 2040 / 2050:

| Central run | Added cost (M€/a) |
|---|---|
| 15 September | 616 / 508 / 523, of which ALEGrO's twin was 60 / 55 / 51 |
| 24 September | 713 / 774 / 856 |

It also doubled the converter part of any DC expansion. On the recalibrated run it is 0 in
every horizon (§9).

**The fix.** `set_transmission_costs` skips links flagged `reversed` or named
`*-reversed`. Four regression tests in `test/test_network_calibration.py` fail on the old
code.

### 6.3 Allocation between nodes: direct and tariff views

The optimisation has one system cost and needs no allocation. For regional reporting,
two views are produced side by side by `network_cost_report.py`:

* **Direct.** The branches touching BEWAL, 50/50 between their two ends, at model cost,
  with the capacity existing in 2025 separated from the increment. This is the physical
  view, which the multi-node model will refine.
* **Tariff.** The Belgian regulated revenue (Elia 1 552 M€ in 2025; Fluxys) plus the
  Belgian branch increments, times Wallonia's share of Belgian offtake that horizon.
  Belgian increments count internal branches at 100 % and cross-border ones at 50 %.
  This is what Walloon users pay: Elia's tariffs are a national postage stamp per
  voltage level. It is also the input for bills (§8).

ClimAct's capacity-pooled rule is no longer used for Walloon figures.

### 6.4 Data

* **Elia.** Revenue and structure as in §1.2.
* **Offtake shares.** Wallonia's share of Belgian electricity offtake comes from the
  model's withdrawals: about 23 % in 2025, 25 % in 2030 and 36 % in 2050 on the
  15 September run. TIMES's 21.0 TWh into the Walloon HV grid, against Elia's 81.0 TWh
  of 2024 load, gives 26 %.
* **Fluxys.** The approved revenue is confidential (CREG (B)656G/50). The pre-decision
  indicative value is 317 M€ for 2025 [research summary, not re-checked].
* **ALEGrO.** 94 km HVDC Lixhe–Oberzier, about 1 000 MW, **490–550 M€₂₀₁₅** plus 35–45 M€
  of Belgian AC reinforcements (ENTSO-E TYNDP 2016, project 92 sheet).
* **CO₂ trunk sizes.** From the 24 September central run.

### 6.5 Decisions

| id | parameter | before | decided | implementation |
|---|---|---|---|---|
| TR1 | existing grid, tariff view (L1 + L3) | inter-node branches at replacement annuity | **Elia 2025 revenue × Walloon offtake share**; model branches existing in 2025 are left out of this view | `network_cost_report.py` |
| TR2 | new AC branch cost | DEA | **450 / 408 / 372 €/MW/km** | master CSV → `custom_costs.csv` (per horizon) |
| TR3 | HTLS on existing corridors | — | not differentiated: one cost per branch in the current formulation | §12 |
| TR4 | HVDC converter | DEA | unchanged | — |
| TR5 | per-branch project costs | centroid length × unit cost | **ALEGrO corridor (BEWAL–DE DC) at 692.6 k€/MW**. The 520 M€₂₀₁₅ midpoint is inflated × 1.332 (EU27 HICP 2016–20, then `factor_2020_to_2025`). It also prices the second BE–DE HVDC. Other projects have no public cost | `data/walloon/transmission_cost_overrides.csv`, rows `investment`, set in `prepare_sector_network` and re-set in `add_brownfield` |
| TR6 | reversed-DC legs | converter cost from 2030 | **0** | §6.2 |
| TR7 | lengths, `s_max_pu` | centroid × 1.25; 0.7 | unchanged: they drive impedance, losses and the NTC gross-up | — |
| TR8 | system services | absent | inside the Elia revenue of TR1 (the 2025 budget breakdown is confidential) | — |
| TR9 | interconnection income | not reported | inside the Elia revenue (net). The model's Belgian share of cross-border congestion rent is reported for comparison | `bill_harmonisation.py` |
| TR10 | methane transmission, tariff view | SciGRID pipelines at replacement annuity | **Fluxys 317 M€ × Walloon gas offtake share** | `network_cost_report.py` |
| TR11 | H₂ pipelines | EHB 2021 | unchanged (§6.1) | — |
| TR12 | CO₂ pipelines | linear DEA cost | See note below | overrides CSV, rows `capital_cost_factor`, generated by `build_co2_trunk_overrides.py`, applied once per vintage |
| TR13 | discount rate | 7.5 % | 3.5 % (§3) | master CSV |

*Method for TR12.* Each corridor's capital cost is multiplied by (Q/300 t/h)<sup>−0.4</sup>,
the six-tenths rule, where Q is the corridor size in the 24 September central run. The
factor is capped at 1, so small pipes keep the DEA cost. Eight corridors are affected:

| corridor | factor |
|---|---:|
| BEVLG–BEWAL | 0.53 |
| BEVLG–FR | 0.87 |
| BEVLG–GB | 0.46 |
| BEVLG–NL | 0.56 |
| BEWAL–DE | 0.60 |
| BEWAL–LU | 0.82 |
| DE–FR | 0.32 |
| FR–GB | 0.31 |

### 6.6 Validation

| id | check | target |
|---|---|---|
| TV1 | tariff view vs Elia revenue × offtake share | by construction for 2025 |
| TV2 | model congestion rent vs Elia interconnection income | 0.42 bn€ (2022 actual); model 0.6–1.0 bn€ Belgian share — §9 |
| TV3 | cost of the committed projects built through the NTC floors | no public project costs yet |
| TV4 | reversed DC legs carry no cost | 0 in every horizon (§9) |

---

## 7. Implementation

| component | file | notes |
|---|---|---|
| HVDC twin fix | `scripts/add_electricity.py` (`set_transmission_costs`) | global |
| calibration hooks | `scripts/walloon_scripts/network_calibration.py` | `split_industry_electricity`, `add_rooftop_pv_hosting_cost`, `apply_transmission_cost_overrides`, `co2_scale_factor` |
| hook calls | `scripts/prepare_sector_network.py` (end of `insert_electricity_distribution_grid`; before export), `scripts/add_brownfield.py` (after `set_transmission_limit`, `investment` rows only) | no-ops without `sector.network_calibration` |
| rule inputs | `rules/build_sector.smk` (`prepare_sector_network`), `rules/solve_myopic.smk` (`add_brownfield`): `transmission_cost_overrides` | so that editing the table re-runs the chain |
| unit costs and rates | `config/input_parameters_for_models.csv` → `data/walloon/custom_costs.csv`, `data/walloon/discount_rates.csv` | `python scripts/build_common_parameters.py --write` / `--check` |
| switches | `config/config.walloon.yaml` → `sector.transmission_efficiency`, `sector.gas_distribution_grid_cost_factor`, `sector.network_calibration` | base config: every scenario |
| per-corridor overrides | `data/walloon/transmission_cost_overrides.csv`; CO₂ rows from `scripts/walloon_scripts/build_co2_trunk_overrides.py <reference run>` | ALEGrO row hand-maintained with its source |
| exogenous layers | `data/walloon/network_cost_calibration.csv`, generated by `scripts/walloon_scripts/build_network_cost_calibration.py` from the per-DSO budgets it transcribes | do not hand-edit |
| reporting | `scripts/walloon_scripts/network_cost_report.py <run>` → `csvs/network_costs_calibrated.csv`, `csvs/network_cost_segments.csv` | layers × views × horizons |
| chart | `plot_cost_segments.py --network-costs calibrated` (default) | puts the ClimAct gas slice back into *Production*; takes the PV hosting and boiler charges out of it |
| TIMES harmonisation | `scripts/walloon_scripts/bill_harmonisation.py <run>` → `csvs/bill_harmonisation.csv` | §8 |
| tests | `test/test_network_calibration.py` (15 tests); `test/test_discount_rates.py` updated | the twin tests fail on the old code |

After a solve:

```bash
python scripts/walloon_scripts/network_cost_report.py results/walloon/<scenario>
python scripts/walloon_scripts/bill_harmonisation.py results/walloon/<scenario>
python scripts/walloon_scripts/plot_cost_segments.py --runs results/walloon/<scenario> ...
```

---

## 8. Coupling with TIMES for bill reporting

TIMES reports the effect of the scenarios on the electricity and gas bills of different
users. The two models therefore have to agree on every bill component.

### 8.1 The bill identity

For each user type *u*, carrier *e* and year:

> **Bill**<sub>u,e</sub> = V<sub>u,e</sub> × ( p<sup>energy</sup> + t<sup>network</sup> + τ + σ ) + F<sub>u,e</sub>, plus VAT

The terms:
* **V**: billed volume, net of self-consumption;
* **p<sup>energy</sup>**: commodity price seen by the user's profile;
* **t<sup>network</sup>**: distribution plus transmission tariff;
* **τ**: taxes and levies;
* **σ**: support levies;
* **F**: fixed charge per connection.

Suggested user types:
* electricity: LV residential (with and without heat pump or EV), LV prosumer, LV
  services, MV business, HV industry;
* gas: residential, services, industry on distribution, industry on transmission.

**Division of labour.**
* **PyPSA supplies the system side:** the zonal energy price, the network revenue
  requirements (L1–L4, §2–§6) and the support needs.
* **TIMES supplies the demand side:** volumes by user type, connections and
  self-consumption, plus the taxes. It also reports the bills.

### 8.2 The harmonisation table

`bill_harmonisation.py` writes one row per variable and horizon, with the PyPSA value,
the TIMES value and the relative gap.

| group | variables | PyPSA side | TIMES side | tolerance |
|---|---|---|---|---|
| A volumes | electricity behind the distribution link; electricity at HV | link inflow; loads on the AC bus (after E6) | `VAR_FIn` on `ELCMED`+`ELCLOW`, and on `ELCHIGG`+`ELCHIG` | ±2 % |
| B prices | wholesale electricity (time average and load weighted); LV–HV spread; gas; ETS1 | **Belgian zonal price**, the LV-inflow-weighted average of the three HV nodes; `BEWAL gas`; `CO2Limit` dual | `EQ_CombalM` on `ELCHIG`, `ELCLOW`, `GASNAT` (unweighted mean over timeslices) | ±10 % |
| C networks | revenue requirement and €/MWh for electricity distribution, transmission (tariff view) and gas | `network_costs_calibrated.csv` | — | — |
| C mark-ups | each "Fuel Tech" mark-up against the network €/MWh; the residual is taxes, levies and support | idem | `Cost_Act / VAR_Act` | — |
| C reconciliation | network revenue required vs mark-ups collected (electricity, gas) | L1–L4 | Σ `Cost_Act` | — |
| S support | cost minus market revenue of Belgian generation, per carrier | solved network | — | — |

**Two price conventions matter.**
* **Use HV-bus prices, not the Walloon nodal price.** The nodal price contains the
  import-cap dual (−18.5 €/MWh in 2030 on the 15 Sep run) and internal congestion, which
  a zonal market does not have.
* **Use the HV price plus the network tariff, not the LV-bus price.** The LV-bus price
  already contains the distribution capacity rent, about 15–18 €/MWh, which recovers the
  distribution annuity. Adding a tariff on top would count the grid twice.

### 8.3 Procedure

1. After each PyPSA run: run `network_cost_report.py`, then `bill_harmonisation.py`.
2. Read the gaps. At the time of writing, three are structural:
   * the wholesale price level (§9);
   * the mark-ups, constant 2025–2050, while network revenue requirements and volumes
     are not;
   * the residential electricity mark-up, far above the network €/MWh; the residual is
     taxes and levies if the mark-up holds them.
3. Hand the recomputed network tariffs per user type (C) and support levies (S) to ICEDD
   as TIMES inputs, replacing the constant mark-ups.
4. Re-run TIMES, then PyPSA once. The mark-ups steer TIMES's technology choice, which
   feeds back into PyPSA's demands.

Data needed from ICEDD:
* timeslice durations (`G_YRFR`);
* the content of the mark-ups;
* the user types for bills;
* connection counts;
* self-consumption;
* the ETS2, excise, levy and VAT assumptions;
* any support schemes;
* industrial gas by grid level.

### 8.4 What the cost chart can and cannot say

The chart is a PyPSA-only view of supply, storage and network costs. It omits TIMES's
demand-side costs (vehicles, appliances, renovation). Each scenario also has its own
TIMES run. It is therefore not a total system cost, and cannot compare scenarios, until
the TIMES costs are added on a consistent perimeter.

In the September batch, networks explained 5 % of the 2050 gap between central and
delayed-nuclear.

---

## 9. Results of the recalibrated central run

`scen_central`, weather 2010, 1 h, TIMES `scen_central_v01_260923_2_2309.vd`. The run was
solved on NIC5 on 2026-09-29 and all four horizons are optimal. The solve log is
[`logs/2026-09-29_scen_central_2010_1h_netcal.md`](logs/2026-09-29_scen_central_2010_1h_netcal.md).
The reference is the 24 September central run (same TIMES file), reported with the same
scripts.

### 9.1 What the comparison can attribute

The run also carries `bbc9450e`, the nuclear seed threshold, committed the same morning.
That commit keeps the FR/GB `nuclear-2025` investment options alive after 2025:

| Nuclear (GW_e) | 2030 | 2040 | 2050 |
|---|---|---|---|
| France, this run | 61.8 | 62.9 | 62.9 |
| France, 24 Sep | 13.1 | 6.2 | 0 |
| GB, this run | 5.5 | 13.2 | 13.2 |
| GB, 24 Sep | 4.7 | 3.4 | 3.4 |

BEWAL and BEVLG also reach 3 GW each in 2050. This state matches the 15 September batch
behind the cabinet deck. The 24 September run is the outlier: its 10 MW cleanup had
deleted the foreign options.

This decides what the comparison can attribute:
* **2025 is a clean before/after.** The nuclear fleet is identical, and a separate solve
  without the seeds gives the same objective to 1e-6.
* **2030–2050 mix the calibration with a different European nuclear fleet.** The 2030
  Belgian price (192.6 → 124.6 €/MWh) and the ETS1 dual (186.7 → 93.9 €/t) follow the
  French nuclear, not the networks.
* **The network-local quantities of 2030–2050 are only indicative.** They are given below
  as such.

### 9.2 Validation

| id | check | target | result |
|---|---|---|---|
| V1 | reported 2025 cost, L1 + L3 | 678 M€ | 677.9 M€ (by construction) |
| V2 | new-build 2025→30, overnight | ≈ 0.77 bn€ | **0.64 bn€** (1 028 MW × 620 €/kW), −17 % |
| V3 | energy through the link, 2025 | 14–15.5 TWh | **15.4 TWh** (24 Sep: 20.8 TWh before the HV split) |
| V4 | loss cost, 2025 | ≈ 87 M€/a | **81.9 M€/a** (CWaPE 2025: 87.0) |
| V5 | 2030 reported cost, L1 + L2 + L3, vs the CWaPE 2029 core in real terms | 680 M€ ± 10 % | **728 M€**, +7 % |
| — | electricity distribution revenue requirement, 2025, all layers | CWaPE 896.3 M€ | 891.2 M€, −0.6 % |
| GD | gas distribution level and tariff trajectory | 282.0 M€ | by construction. The network cost per MWh of residential + services gas rises 25.8 → 28.3 → 53.7 → 70.7 €/MWh as volumes fall |
| TV1 | tariff view, 2025 | Elia × offtake share | 394.4 M€ = 1 552.1 × 25.4 % (by construction) |
| TV2 | Belgian half of the cross-border congestion rent | Elia 0.42 bn€ (2022) | 0.11 / 0.83 / 0.62 / 1.58 bn€/a in 2025 / 30 / 40 / 50. 2022 was the crisis year, so 2025 has no comparable reference |
| TV3 | cost of the committed projects built through the NTC floors | — | no public project costs |
| TV4 | reversed DC legs carry no cost | 0 | **0 in every horizon** (24 Sep: 713 / 774 / 856 M€/a in 2030 / 40 / 50) |

V2 is 17 % low. The model adds 1.03 GW of Walloon distribution capacity in 2025–2030, while
the DSOs' plan implies about 1.24 GW at 620 €/kW. A higher PV share of the capex (§4.4) or a
diversity factor below 1 would close part of that gap. Both need the DSOs' split of E1.1
(§11).

### 9.3 The two network bars

`network_cost_report.py` gives the Walloon segments, which `plot_cost_segments.py
--network-costs calibrated` draws (M€₂₀₂₅/a).

**Distribution**

| *Distribution* | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| electricity: existing grid L1 | 390.5 | 390.5 | 390.5 | 390.5 |
| electricity: reinforcement L2 | 0 | 42.6 | 135.3 | 202.7 |
| electricity: OPEX L3 | 287.4 | 295.0 | 311.4 | 329.6 |
| electricity: smart meters | 22.9 | 51.8 | 51.8 | 51.8 |
| electricity: rooftop-PV hosting | 0 | 20.2 | 76.1 | 90.4 |
| gas: existing grid + OPEX (GD1) | 282.0 | 282.0 | 282.0 | 282.0 |
| **segment** | **982.8** | **1 082.1** | **1 247.1** | **1 347.0** |
| *September chart (15 Sep networks), for reference* | *315.5* | *375.2* | *568.3* | *711.5* |

Losses are reported next to the segment and are not added to it: 81.9 / 142.7 / 178.7 /
296.5 M€/a. They sit in *Production/Imports*. The same holds for PSO, the road-use fee and
the other regulated items (99–109 M€/a): they are part of the tariff, not of the network
bar.

**Transport**

| *Transport* | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| electricity, tariff view: Elia × offtake share | 394.4 | 417.7 | 529.5 | 549.1 |
| electricity, tariff view: Belgian increments × share | 0 | 0 | 52.8 | 95.2 |
| methane, tariff view: Fluxys × gas share | 69.2 | 94.5 | 109.2 | 102.4 |
| H₂ pipelines, direct 50/50 | 0 | 13.4 | 13.4 | 14.3 |
| CO₂ pipelines, direct 50/50 | 0 | 34.0 | 35.2 | 39.2 |
| **segment** | **463.7** | **559.6** | **740.1** | **800.2** |
| *September chart (ClimAct rule), for reference* | *282.9* | *507.0* | *587.4* | *719.6* |

**The Walloon electricity offtake share** is 25.4 / 26.9 / 34.1 / 35.4 %. For comparison,
the direct view of the electricity branches touching BEWAL gives 43.3 / 47.8 / 83.1 /
106.8 M€/a (existing plus increment).

**The redrawn chart.** It was drawn from this run's ClimAct extraction, run locally on
2026-09-29 and not uploaded, with `plot_cost_segments.py --network-costs calibrated`:
[`figures/netcal_20260929/cost_segments.png`](figures/netcal_20260929/cost_segments.png) (FR),
[`cost_segments_en.png`](figures/netcal_20260929/cost_segments_en.png) (EN).
* Total Walloon system cost: 11.6 / 10.8 / 11.2 / 14.0 bn€/a.
* Distribution: 1.0 / 1.1 / 1.2 / 1.3 bn€/a, against 0.3–0.7 in September.
* Transport: 0.5 / 0.6 / 0.7 / 0.8 bn€/a.

The subtitle ("September 2026 cabinet batch") is the script's fixed text and should be
edited before any slide use.

### 9.4 Effect on the optimisation

**2025 (clean comparison)**
* **System cost.** It falls by 10.4 bn€/a (−1.8 %, capex + opex of the six countries). The
  cause is the 3.5 % annuity on existing network assets, above all the distribution grid
  (66.4 → 41.4 k€/MW/a).
* **Distribution.** The BEWAL distribution link shrinks from 3.69 to 3.10 GW and its inflow
  from 20.8 to 15.4 TWh. That is E6: 70 % of industrial electricity moved to HV.
* **Gas boilers.** BEWAL gas boilers rise by 0.8 GW_th (8.66 → 9.46), from the lower
  avoidable grid charge (GD2).
* **Congestion rent.** Unchanged, at 0.11 bn€/a.

**2030–2050 (indicative, see §9.1)**

| BEWAL / BE | 2030 | 2040 | 2050 |
|---|---|---|---|
| distribution link (GW) | 4.13 (4.31) | 6.36 (7.72) | 7.99 (9.49) |
| rooftop PV (GW) | 4.29 (4.29) | 10.47 (10.47) | 11.27 (18.87) |
| batteries incl. home (GW) | 0.49 (2.59) | 2.10 (3.11) | 6.39 (8.98) |
| AC expansion touching BE (GW) | 0 (0.03) | 1.77 (1.89) | 7.31 (6.22) |
| H₂ pipelines touching BE (GW) | 7.8 (11.4) | 8.8 (11.8) | 13.3 (19.0) |
| CO₂ pipelines touching BE (kt/h) | 4.05 (2.33) | 6.49 (4.48) | 8.41 (7.09) |

24 September values are in brackets.

These directions match the decisions:
* **Batteries.** Fewer batteries in 2030, because cheaper distribution capacity makes
  battery peak-shaving worth less. 2030 is the least confounded of these horizons.
* **Rooftop PV.** Less rooftop PV above the TIMES floor in 2050, from the 120 €/kWp hosting
  charge. 2040 is still at the floor.
* **H₂ and CO₂ pipelines.** Fewer H₂ pipelines, and larger CO₂ trunks from the economies of
  scale (TR12).

Separating these effects from the nuclear change needs a calibration-only chain, which was
not run (§12).

### 9.5 TIMES harmonisation (`csvs/bill_harmonisation.csv`)

`bill_harmonisation.py` flags 18 gaps beyond tolerance. The main ones:

| variable | PyPSA 2025 / 2030 / 2040 / 2050 | TIMES | reading |
|---|---|---|---|
| electricity behind the distribution link (TWh) | 15.4 / 20.2 / 33.0 / 43.3 | 13.9 / 16.1 / 27.4 / 36.9 | +11 to +25 %. The 5 % losses explain part. The rest is LV load outside TIMES's `ELCMED` + `ELCLOW` rows, still to be mapped |
| electricity at HV (TWh) | 5.6 / 6.5 / 13.3 / 16.5 | 6.5 / 8.1 / 15.0 / 18.0 | −8 to −20 %. The 70 % share (E6) is slightly low |
| wholesale electricity, time average (€/MWh) | 105.4 / 124.6 / 97.6 / 111.0 | 80.2 / 67.2 / 96.8 / 61.1 (`ELCHIG`) | the structural gap of §8.3. TIMES has no timeslice weights (`G_YRFR`) |
| wholesale gas (€/MWh) | 38.7 / 37.5 / 32.2 / 26.8 | 33.2 / 30.8 / 26.6 / 22.2 | +17 to +21 % |
| LV − HV price spread (€/MWh) | 14.4 / 16.3 / 14.1 / 15.2 | 6.3 / 5.3 / 7.6 / 4.8 | PyPSA's spread is the distribution rent plus losses |
| network cost per MWh of MV + LV electricity | 64.3 / 64.8 / 45.3 / 39.6 | residential mark-up 179.5, services 94.1 (constant) | the residential residual of 96–128 €/MWh is taxes and levies, if the mark-up holds them |
| network cost per MWh of residential + services gas | 25.8 / 28.3 / 53.7 / 70.7 | residential mark-up 33.8 / 53.4 / 57.6 / 33.8 | TIMES's mark-up falls back in 2050, while the network cost per MWh keeps rising |
| electricity: revenue required against mark-ups collected (M€/a) | 1 286 / 1 459 / 1 825 / 2 104 | 1 656 / 1 592 / 2 317 / 2 908 | the mark-ups collect 9–38 % more than the networks need |
| gas: revenue required against mark-ups collected (M€/a) | 404 / 430 / 444 / 438 | 555 / 855 / 467 / 199 | in 2050 the mark-ups collect less than half the fixed gas grid |
| support: Belgian nuclear, cost minus market revenue (M€/a) | 1 064 / 230 / −534 / 109 | — | the 2025 support need (24 Sep: 927) |

These are the inputs of step 3 of §8.3: network tariffs per user type and support levies
for ICEDD.

---

## 10. Literature and benchmarks

[S] marks values seen in secondary sources or abstracts only.

**Distribution cost per kW**

| source | scope | value |
|---|---|---|
| DEA via technology-data (`distribution grid reinforcement`) | local grid and substation per new connection | 189 €/kW |
| PyPSA-Eur / technology-data | "distribution grid", all LV peak | 668 €/kW (500 €/kW₂₀₁₅, "TODO") |
| Priyadarshan et al., [arXiv:2410.04540](https://arxiv.org/abs/2410.04540) [S] | US residential electrification | ≈ $580–1 320/kW |
| Turk, Schittekatte et al., *Energy Journal* 2025 [S] | US distribution LRMC | $50–150/kW (probably per year) |
| this calibration | Walloon transition capex ÷ model peak increase | 410–960 €/kW, 620 decided |

**How other models treat the existing grid**
* **PRIMES** (E3M 2018) computes network costs on a RAB of old plus new assets,
  recovered through tariffs by voltage. That is the L1 + L2 split used here.
* **The Energy Transition Model** prices only capacity above the present one, per layer,
  in discrete steps.
* **Böttcher et al.** ([arXiv:2310.11853](https://arxiv.org/abs/2310.11853)) use stepwise
  expansion regions per voltage level.
* **PyPSA-Eur issue [#1760](https://github.com/PyPSA/pypsa-eur/issues/1760)** flags the
  reuse of the electricity grid cost for gas boilers.

**Aggregates**
* **Eurelectric, *Grids for Speed* (2024).** EU distribution investment rises from
  €33 bn/yr to **€67 bn/yr** in 2025–2050 (LV 44 %, MV 41 %, HV 15 %; flexibility
  −18 %). That is about 150 €/inhabitant/yr, or ≈ 0.55 bn€/yr for Wallonia, the same
  order as the CWaPE plans (0.66 bn€/yr).
* **IEA (2023).** Grid investment has to double to over USD 600 bn/yr by 2030.
* **EU Grid Action Plan [S].** About 40 % of distribution grids are over 40 years old.

**Transmission unit costs** (ACER UIC, April 2026; medians)

| asset | cost |
|---|---:|
| 400 kV overhead line, 1 circuit | 0.52 M€/km |
| 400 kV overhead line, 2 circuits | 1.18 M€/km |
| 220 kV underground cable | 2.08 M€/km |
| HVDC converter | 0.21 M€/MW |

ACER also finds costs rising 6 %/yr above inflation since 2018. HTLS reconductoring is
reported at ⅓–½ of new-build cost [S: Chojkiewicz et al., PNAS 2024].

**Gas and pipelines**
* Agora/BET/Rosin Büdenbender (2023), Ofgem RIIO-3 [S] and the
  [CEER note](https://www.ceer.eu/wp-content/uploads/2024/04/C19-DS-55-07_CEER-note-on-stranded-assets-in-distribution-networks-II.pdf)
  on stranded assets, as in §5.
* Directive (EU) 2024/1788, Art. 57 [S]: decommissioning plans.
* **H₂.** [EHB 2022](https://ehb.eu/files/downloads/ehb-report-220428-17h00-interactive-1.pdf):
  2.8 / 0.5 M€/km for large new / repurposed pipes.
* **CO₂.** JRC (Tumara et al. 2024,
  [doi:10.2760/582433](https://publications.jrc.ec.europa.eu/repository/bitstream/JRC136709/JRC136709_01.pdf)):
  0.62–0.89 M€/km average. Walloon capture projects: Anthemis (0.8 Mt/a), GO4ZERO
  (1.3 Mt/a), LEILAC.

---

## 11. Open questions and data requests

**ICEDD (TIMES-WAL)**

1. The content of the `Cost_Act` mark-ups (network tariffs, excise, levies, ETS2) and
   their sources.
2. Whether `EVTRANS_*` carry any cost or capacity in the VEDA workbooks.
3. Industrial gas by grid level (distribution vs Fluxys).
4. For bills:
   * timeslice durations (`G_YRFR`);
   * user types;
   * PV self-consumption;
   * connection counts and gas disconnections;
   * ETS2, excise, levy and VAT assumptions;
   * support schemes.

**CWaPE / DSOs**

5. The coincident peak and energy per DSO, split MV/LV.
6. The split of E1.1 (load and peaks) between PV, EVs and heat pumps. This replaces the
   25 % assumption of E5/E8.
7. The ORES revision request under review. No public decision had been found as of
   September 2026.
8. Gas mains and connections per zone, for a decommissioning pathway.

**Elia / CREG / Fluxys**

9. The 2024–27 budget breakdown of Elia's revenue (grid, services, levies, federal vs
   local) and Wallonia's share of offtake.
10. Project costs for Boucle du Hainaut, the second BE–DE HVDC and Nautilus.
11. Fluxys's approved revenue.

**ClimAct**

12. The origin of `nyears = 1/3` in the gas slice, and whether the capacity-pooled
    transmission rule can be dropped from the extraction.

---

## 12. Future work

The calibration fixes the *level* and the *marginal signals* within the current
formulation. The following need formulation changes, mostly with the multi-node Belgium.

**Electricity distribution**
* **Nodes and voltage levels.** One LV (and MV) bus per node, with costs per DSO area
  (ORES, RESA) and per network type (urban, rural). A two-tier MV / LV representation,
  so that MV industry and utility PV use only the MV tier.
* **The existing grid as vintaged, non-extendable cohorts** from the DSO asset-age
  distribution, so that renewal becomes endogenous instead of a constant block.
* **A reverse-flow hosting-capacity constraint** per node, replacing the PV adder (E8).
* **A flexibility credit (E10)**, so that behind-the-meter storage and smart charging
  shave local rather than regional peaks, if DSO data support it.

**Transmission**
* **Explicit 380/220/150 kV lines** for Belgium with real lengths; 70/36 kV as a proxy
  layer.
* **Project costs** for every committed project.
* **HTLS as a separate, cheaper expansion option** on existing corridors (TR3).
* **Endogenous reserves**, so system services leave the exogenous block.
* **Regional cost** as the sum over regional branches plus 50/50 cross-border, with the
  tariff view kept for bills.

**Gas and pipelines**
* **A gas distribution bus per zone** with a fixed cost and a decommissioning decision:
  keep for biomethane or H₂, or seal. This needs a TIMES disconnection series and
  per-zone mains data.
* **Piecewise-linear pipeline costs** (H₂, CO₂) for economies of scale, instead of the
  one-step linearisation of TR12.
* **An H₂ retrofit option** once Fluxys's plan frees methane pipes.

**TIMES coupling**
* Automate the §8.3 loop: PyPSA network tariffs and support levies handed to TIMES as
  mark-ups, with the bills reported on the harmonised components.
* Add TIMES's demand-side costs to the cost chart on a common perimeter.
* Map the LV loads that fall outside TIMES's `ELCMED` + `ELCLOW` rows, so that group A
  closes to within the losses (§9.5).

**Attribution and scenario hygiene**
* **A calibration-only chain.** Today's code with `sector.network_calibration`, the
  distribution efficiency, the boiler factor and the Calibration cost rows reverted.
  §9.1 needs it to separate the 2030–2050 network effects from the nuclear change of
  `bbc9450e`. That is about 4 h on NIC5.
* **Foreign nuclear — done differently (2026-09-30).** The 49 GW French "rebuild" by 2030
  was forced by `legacy-unreviewed` floors in the caps file, not chosen. It is replaced by
  a corridor pinned to the national plans. See
  [`logs/2026-09-30_cabinet_batch_20260930_2010_1h.md`](logs/2026-09-30_cabinet_batch_20260930_2010_1h.md)
  §3. The 2030 Belgian price and the ETS1 dual will move with it, so any
  calibration-only attribution has to be run on the new corridor.
* **The distribution increment is 17 % low (V2).** Revisit the PV share of the transition
  capex and the diversity factor once the DSOs' split of E1.1 is available.

---

## Appendix A — CWaPE budgets by DSO (M€ nominal)

**Electricity, 2029** (Tableau 4 for ORES, Tableau 8 for the others):

| family | ORES | RESA | AIESH | AIEG | REW | total |
|---|---:|---:|---:|---:|---:|---:|
| controllable OPEX (excl. PSO) | 208.8 | 81.8 | 4.6 | 4.3 | 3.5 | 303.0 |
| depreciation | 161.0 | 41.7 | 3.3 | 2.2 | 3.8 | 211.8 |
| fair margin on RAB | 116.8 | 37.8 | 2.5 | 2.2 | 2.3 | 161.7 |
| margin on revaluation gains | 11.3 | 2.5 | 0.2 | 0.1 | 0.2 | 14.2 |
| corporate tax on the margin | 33.4 | 8.8 | 0.8 | 0.8 | 0.8 | 44.6 |
| losses | 58.7 | 17.9 | 1.8 | 1.5 | 0.6 | 80.6 |
| PSO | 30.2 | 14.6 | 1.1 | 0.6 | 1.0 | 47.5 |
| road-use fee | 34.7 | 11.8 | 0.6 | 0.7 | 0.4 | 48.4 |
| smart meters | 43.7 | 11.6 | 0.4 | 0.7 | 0.5 | 57.0 |
| other | 0.7 | 10.3 | 0.8 | 0.8 | 0.0 | 12.6 |
| **authorised revenue** | **699.3** | **238.8** | **16.1** | **13.9** | **13.2** | **981.3** |

The 2025 values and the gas budgets are transcribed in
`scripts/walloon_scripts/build_network_cost_calibration.py`, which checks each DSO's sum.

Decisions:
* ORES: CD-25d03-CWaPE-1056 (revision of 14/03/2025);
* RESA: CD-25b20-CWaPE-1043;
* REW, AIESH, AIEG: decisions of 30/01/2025 (-1038, -1037, -1036);
* gas: CD-24c28-CWaPE-0890 (ORES), -0891 (RESA).

## Appendix B — Reproduction

```bash
python scripts/walloon_scripts/build_network_cost_calibration.py        # exogenous layers
python scripts/walloon_scripts/build_co2_trunk_overrides.py results/_archive/scen_central_20260924_vd260923
python scripts/build_common_parameters.py --write && python scripts/build_common_parameters.py --check
python -m pytest test/test_network_calibration.py test/test_discount_rates.py -q
```

The diagnosis figures of §1.1 come from the 15 September networks, archived under
`results/_archive/scen_central_20260915_vd260911/`. The baseline for §9 is the
24 September run, under `results/_archive/scen_central_20260924_vd260923/`.
