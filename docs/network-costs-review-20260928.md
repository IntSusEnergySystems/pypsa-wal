# Network costs in the central scenario — distribution, transmission, gas

**Date:** 2026-09-28
**Trigger:** stakeholder e-mail feedback on the central scenario and the September 2026
cabinet deck (sections "Distribution", "Transport", "Nucléaire"). It compares the
*Distribution* and *Transport* bars of the chart
*« Coûts totaux du système wallon par segment »*
([`docs/figures/cost_segments.md`](figures/cost_segments.md), drawn by
[`plot_cost_segments.py`](../scripts/walloon_scripts/plot_cost_segments.py)) with the
CWaPE-approved authorised revenues of the Walloon DSOs.
**Runs examined:** `results/walloon/scen_central` (TIMES
`scen_central_v01_260911_1109.vd`, 1 h, weather 2010, networks of 2026-09-15) and
`results/walloon/scen_retardnucleaire`.
**Scope:** networks only — electricity distribution, electricity transmission, gas
distribution and transmission, H₂ and CO₂ pipelines. Nuclear is out of scope (3 GW in
2050 is kept until the meeting with the cabinet).
**Status:** analysis, proposals and calibration plan. The calibration plan (§6) and the
TIMES bill harmonisation (§7) were added on 2026-09-29. No model code or input was
changed. One code bug found in passing (§4.1.4) is filed as a separate task.

Every number in this note is reproducible from the solved networks, the ClimAct
extraction output (`explorer/pypsa/costs_segments.csv`) and the five CWaPE decisions;
see the appendix.

---

## 0. Short answers

| Question raised | Short answer | § |
|---|---|---|
| Does the *Distribution* bar combine gas and electricity? | **Yes.** In 2030 the 0.375 bn€ bar is 0.320 bn€ of electricity distribution plus 0.054 bn€ of gas distribution. The like-for-like comparison with the CWaPE electricity figures is therefore **0.32 bn€**, and the gap is larger than the one computed in the feedback: ×3.1 on the total authorised revenue, ×2.3 on its network core. | 1.1, 2.2 |
| Is the gas distribution grid represented? How? | **Not as a network.** PyPSA adds a fixed €/kW charge to the capital cost of *new* decentral gas boilers and micro-CHP. Existing boilers, industry and CHP pay nothing, and the charge disappears when boilers are not replaced. The gas slice in the bar is not even that charge: the ClimAct extraction recomputes it with another cost file and a factor ⅓. | 3.1 |
| How is distribution approximated in PyPSA? A capacity cost added to production assets? Is OPEX included? | A **capacity cost, but not attached to production**. It is a separate asset between the transmission node and a "low voltage" bus. It is sized endogenously at the hourly, region-wide coincident peak of everything connected at LV, at **66.4 €/kW/a** (668 €/kW, 40 y, 7.5 %, plus 2 %/a FOM). The only OPEX is that 2 %/a FOM, about 20 % of the annual cost. Grid-connection costs of wind and utility PV (187 €/kW) *are* added to production assets and are booked in *Production*. | 2.1 |
| How does TIMES approximate distribution? Does the gap come from missing reinforcement for electrification? | TIMES-WAL has four grid processes (HV, HV→MV, MV→LV, LV→MV) that carry **losses only**: no capacity and no cost appear in the solution dump. Grid costs seem to enter TIMES as **volumetric €/MWh mark-ups** on its sectoral "Fuel Tech" processes (residential electricity 179.5 €/MWh, services 94.1, industry 24.6). These look like end-user network tariffs plus taxes, to be confirmed with ICEDD. In PyPSA, the level gap comes mainly from the *existing* grid: its valuation, and OPEX. The increment is low as well: 0.7 bn€ of new distribution capacity to 2030, against 3.3 bn€ of DSO capex planned for 2026–30, which also covers renewal and connections. | 5, 2.2, 2.3 |
| Are the chart and the central-vs-delayed-nuclear difference interpretable? | We agree the chart must not be presented as a *total* system cost. It holds PyPSA costs only, TIMES's demand-side costs are missing, and the two scenarios use different TIMES runs. The networks, however, are **not** what drives the 2050 difference: they account for 0.07 of the 1.29 bn€/a gap. | 5.3 |
| Transmission: how are CAPEX and OPEX approximated? | Replacement-value annuities of the **inter-node** branches only: 3 Belgian regions plus one node per neighbouring country, at Danish Energy Agency 2025 unit costs, on centroid-to-centroid lengths × 1.25. OPEX is a 1.5 %/a FOM. There are no system services and no internal 380/220/150/70 kV grid. One bug double-counts HVDC converters from 2030 on. | 4.1 |
| Transmission: how are costs split between nodes? | Three different rules coexist. The optimisation needs none. `make_summary` splits each branch 50/50 between its ends. The ClimAct extraction behind the chart **pools every branch of the 6-country system** and redistributes the pool by each node's share of connected capacity. That rule gives Wallonia **2.1×** its 50/50 share (507 vs 246 M€ in 2030), and 31 % of the Walloon *Transport* bar is CO₂ pipelines. | 4.2 |
| How should the costs be recalibrated in the current model? | Split every network into the **existing grid** (sunk, calibrated on 2025 regulated accounts: 678 M€ electricity distribution, 282 M€ gas distribution, Walloon share of Elia and Fluxys revenue) and the **increment** (endogenous). For the increment, the calibrated unit cost is 620 €/kW for electricity distribution, plus 120 €/kWp for PV hosting, annualised at a regulated 3.5 % real. HV industry comes off the LV bus, losses rise to 5 %, and the gas-boiler charge drops to its avoidable part (factor ≈ 0.1). The recalibrated Walloon distribution cost is ≈ 0.73 bn€ in 2030 instead of 0.32 bn€. Most of the change is a reporting layer that needs no re-solve. | 6 |
| How is PyPSA kept consistent with the bills TIMES will report? | Through a bill identity with five components: energy, network, taxes, support levies and fixed charges. PyPSA provides the zonal energy price, the network revenue requirements and the support needs. TIMES provides the volumes and taxes. A reconciliation identity requires the TIMES mark-ups to recover the calibrated network costs. The first gap to resolve is the wholesale price level (PyPSA 109 vs TIMES 69 €/MWh in 2030). | 7 |

The rest of the note explains these answers and proposes, for each network, what to
change **now** (3 Belgian nodes, same scenario) and what to prepare for the **multi-node**
Belgium of the next phase (§8). §6 turns the proposals into a parameter-by-parameter
**calibration plan** for the current formulation. §7 defines how PyPSA's network and
price outputs are **harmonised with TIMES**, which will report the effect of the
scenarios on electricity and gas bills.

---

## 1. What the two bars contain

Both bars are rebuilt here to the euro from the solved networks. The rebuild uses the
same rules as the ClimAct extraction (`graph_extraction_transform.py` in
`climact-pypsa-eur_results_extraction`), so the figures below are exactly those of the
chart.

### 1.1 *Distribution* (BEWAL, M€/a, `scen_central`)

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| Electricity distribution link, capital (PyPSA objective) | 250.7 | 320.4 | 520.8 | 683.5 |
| Gas distribution, as recomputed by the ClimAct extraction | 64.6 | 54.3 | 46.7 | 26.8 |
| OPEX (marginal cost on the link) | 0.2 | 0.5 | 0.8 | 1.3 |
| **Bar in the chart** | **315.5** | **375.2** | **568.3** | **711.5** |
| *memo:* gas-grid charge actually in the PyPSA objective (§3.1) | 113.3 | 126.5 | 195.9 | 112.4 |

The gas slice is **not** the gas-grid charge the model optimised against. The extraction
subtracts from boilers a charge built from its own cost file, `data/costs/CZ/costs_2025.csv`,
at 500 €/kW, a 7 % fill rate and a factor `nyears = 1/3`: 15.8 €/kW/a for boilers built
from 2025 and 3.3 €/kW/a for older ones. The model itself charges 66.4 €/kW/a, on
boilers built from 2025 only. The remaining ~72 M€ (2030) of the model's gas-grid charge
therefore stays inside *Production*. The ⅓ has no counterpart in the model and looks
like a leftover of another study's setup; raise it with ClimAct.

### 1.2 *Transport* (BEWAL, CAPEX, M€/a, `scen_central`)

| carrier | ClimAct rule, 2025 / 2030 / 2040 / 2050 | 50/50 per branch, 2025 / 2030 / 2040 / 2050 |
|---|---|---|
| Electricity (AC lines + DC links) | 189.4 / 256.0 / 300.4 / 274.4 | 87.6 / 135.4 / 164.2 / 154.6 |
| Methane pipelines | 41.7 / 41.7 / 41.7 / 42.5 | 13.8 / 13.8 / 13.9 / 14.6 |
| H₂ pipelines | 48.6 / 54.1 / 59.3 / 69.5 | 17.3 / 18.6 / 22.7 / 29.9 |
| CO₂ pipelines | 3.2 / 155.2 / 186.0 / 333.2 | 3.2 / 77.9 / 82.2 / 142.5 |
| **Total** (= bar in the chart, left) | **282.9 / 507.0 / 587.4 / 719.6** | **121.9 / 245.7 / 283.0 / 341.6** |

The right-hand column equals `csvs/nodal_costs.csv` (50/50 split in `make_summary`
since 2026-09-15). The electricity row on the right still contains the double-counted
DC converter of §4.1.4. Corrected, it reads 87.6 / 105.2 / 136.8 / 129.1.

The docstring of `plot_cost_segments.py` says the extraction books a branch "wholly to
whichever of the two region codes sorts first". The code does something else: lines get
location `EU`, and `distribute_transmission_costs` pools every *Transmission* row per
carrier across all eight nodes, then splits the pool by capacity share (§4.2). The
docstring should be corrected.

---

## 2. Electricity distribution

### 2.1 How PyPSA represents it

`insert_electricity_distribution_grid` (`scripts/prepare_sector_network.py`) adds, per
AC node, a bus `<node> low voltage` and an extendable link
`<node> electricity distribution grid` from the transmission bus to it. The following are
moved onto the LV bus:

* every electricity load whose carrier contains `electric`: household and services
  electricity, **industry electricity**, agriculture;
* inflexible EV charging, BEV chargers and V2G;
* heat pumps, resistive heaters, micro-CHP;
* rooftop PV and home batteries (utility PV and onshore wind stay on the transmission
  bus).

**What sizes the link.** The link capacity is the highest hourly *net* flow from the
transmission node to the LV bus over the year: the coincident peak of all LV-connected
demand, net of LV generation and storage at that hour. In every horizon of `scen_central`
the optimum sits exactly at that peak. The flow practically never reverses at the
regional level (a single hour in four horizons, 169 MW in 2040), so rooftop-PV export
plays no role in the sizing:

| BEWAL | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| capacity (GW) | 3.78 | 4.83 | 7.84 | 10.30 |
| of which built in the horizon (GW) | 3.78 | 1.05 | 3.02 | 2.45 |
| energy through the link (TWh) | 21.5 | 27.7 | 47.5 | 61.6 |
| peak hour | 1 Dec 17:00 | 1 Dec 17:00 | 1 Dec 14:00 | 10 Feb 05:00 |
| annual cost (M€) | 250.7 | 320.4 | 520.8 | 683.5 |

What stands behind the peak (MW at the peak hour):

| BEWAL LV bus | 2025 | 2030 | 2050 |
|---|---:|---:|---:|
| household + services electricity | 1 721 | 1 974 | 2 485 |
| industry electricity | 979 | 1 136 | 2 656 |
| inflexible EV charging | 14 | 479 | 1 671 |
| heat pumps | 258 | 674 | 4 290 |
| resistive heaters | 653 | 457 | 241 |
| home batteries (discharge) | — | −77 | −1 396 |
| rooftop PV | 0 | 0 | 0 |

**Cost.** The model uses technology-data v0.14.0 `electricity distribution grid`:
investment **667.9 €/kW**, lifetime 40 y, FOM 2 %/a. The source field of that row
literally reads *"TODO, from old pypsa cost assumptions"*. The value is the old,
undocumented 500 €/kW of PyPSA-Eur-Sec, indexed from 2015 to 2025 prices
(667.9 / 500 = 1.336, §2.4); it is not new evidence. The discount rate is 7.5 %, the TIMES hurdle
rate for the power sector (`data/walloon/discount_rates.csv`). The annualised cost is
0.0794 × 667.9 + 0.02 × 667.9 = **66.4 €/kW/a**. `custom_costs.csv` does not override it.

**OPEX.** The only OPEX is the 2 %/a FOM inside that capital cost: 13.4 €/kW/a, i.e.
64 M€ of the 320 M€ in 2030. There are no customer-, metering- or IT-related costs. The
3 % static loss on the link (`efficiency = 0.97`) is energy that has to be generated or
imported; its cost is therefore booked under *Production* / *Imports*, not *Distribution*.

**Existing grid.** The link starts at **zero** in 2025 and is built from scratch.
The 2025 vintage (3.78 GW) is the whole existing Walloon distribution grid, priced as
new but sized to the region-wide coincident peak. Later horizons only add increments.
With a 40-year lifetime nothing retires before 2065, so the renewal of today's ageing
grid is not represented either.

**Not a production cost.** The distribution link is not added to generators. What *is*
added to production assets is `electricity grid connection`, 187 €/kW (18.6 €/kW/a),
on the capital cost of onshore wind and utility PV. It is booked in *Production* and is
worth 63 M€/a for the Walloon units built in 2030 alone.

### 2.2 The CWaPE benchmark

The 2029 budgets of the five decisions (Tableau 4 for ORES, Tableau 8 for the others),
grouped by nature. M€, nominal 2029:

| family | ORES | RESA | AIESH | AIEG | REW | **total** |
|---|---:|---:|---:|---:|---:|---:|
| controllable OPEX (excluding PSO) | 208.8 | 81.8 | 4.6 | 4.3 | 3.5 | **303.0** |
| depreciation ("charges liées aux immobilisations") | 161.0 | 41.7 | 3.3 | 2.2 | 3.8 | **211.8** |
| fair margin on the RAB (excluding revaluation gains) | 116.8 | 37.8 | 2.5 | 2.2 | 2.3 | **161.7** |
| margin on revaluation gains ("PV de réévaluation") | 11.3 | 2.5 | 0.2 | 0.1 | 0.2 | **14.2** |
| corporate tax on the margin | 33.4 | 8.8 | 0.8 | 0.8 | 0.8 | **44.6** |
| *network core (sum of the five rows above)* | *531.2* | *172.5* | *11.3* | *9.6* | *10.6* | ***735.3*** |
| network losses (energy purchases) | 58.7 | 17.9 | 1.8 | 1.5 | 0.6 | 80.6 |
| public service obligations (PSO) | 30.2 | 14.6 | 1.1 | 0.6 | 1.0 | 47.5 |
| road-use fee ("redevance de voirie") | 34.7 | 11.8 | 0.6 | 0.7 | 0.4 | 48.4 |
| smart meters | 43.7 | 11.6 | 0.4 | 0.7 | 0.5 | 57.0 |
| other (transit, FeReSO, pensions, ONSSAPL, taxes) | 0.7 | 10.3 | 0.8 | 0.8 | 0.0 | 12.6 |
| **authorised revenue 2029** | **699.3** | **238.8** | **16.1** | **13.9** | **13.2** | **981.3** |

Against the like-for-like electricity figure of 320 M€ (2030):

| comparison | CWaPE (M€) | ratio |
|---|---:|---:|
| total authorised revenue | 981 | 3.1 |
| total minus losses, PSO, road fee and smart meters (the rule in the feedback) | 748 | 2.3 |
| network core: OPEX plus capital charges | 735 | 2.3 |
| capital charges only (depreciation + margins + tax), vs the model's pure annuity of 256 M€ | 432 | 1.7 |
| controllable OPEX, vs the model's FOM of 64 M€ | 303 | **4.7** |

Two conventions blur the comparison slightly. CWaPE figures are nominal 2029 euros
(about 8 % above 2025 euros at 2 %/a). The regulated revenue reflects historic-cost
accounting, including revaluation gains that are being amortised, while PyPSA uses a
replacement-cost annuity. Neither effect comes close to explaining a factor of 2–3.

**The revenue is also about to rise.** CWaPE's opinion on the 2026–2030 adaptation plans
(CD-25k27-CWaPE-0967, Tableau 14) reports average annual gross DSO investment of
**302 M€/yr in 2020–24 and 662 M€/yr in 2026–30 (+119 %)**: ORES 229 → 534, RESA
61 → 113 M€/yr. The stated driver is mostly "évolution prévisible de la consommation
et pointes de charges", i.e. PV, EVs and heat pumps. The model's new-build over the
same stretch is 1.05 GW × 668 €/kW = **0.70 bn€** overnight, against 3.3 bn€ of
planned DSO capex. The planned capex also covers renewal of ageing assets and new
connections, which the model does not represent (§2.3).

The 2029 figures above already include the 2025 revisions (smart meters, and the ORES
subsidy reallocation of CD-25d03-CWaPE-1056). We found no public CWaPE decision on the
ORES revision request mentioned in the feedback as of September 2026. ORES's 2026–30
adaptation plan reportedly flags a capex overrun of about 418 M€ on 2025–29 from
contractor prices; that figure comes from a research summary and has not been
re-checked here.

### 2.3 Why the model is low: decomposing the gap

1. **OPEX is the largest single gap.** The DSOs' controllable OPEX (303 M€) is 41 % of
   the network core. Much of it is driven by the number of connections, not by peak
   load: meter reading, customer service, IT, field staff. A 2 %/a FOM on a
   capacity-based asset captures 64 M€ of it.
2. **The unit investment cost is a placeholder.** 668 €/kW of coincident peak has no
   documented source. Divided by the 2025 regional peak, the network core of 735 M€
   corresponds to **195 €/kW/a** (263 €/kW/a if HV-connected industry is taken off the
   peak), 3–4× the 66.4 €/kW/a in the model. §2.4 compares this with the literature.
3. **Coincident vs local peak.** A single regional LV bus at 1 h resolution sees the most
   diversified peak possible. Real MV/LV assets are sized on local, 15-minute,
   non-coincident peaks with N-1 redundancy on MV. ORES's revision of 14 March 2025
   (CD-25d03-CWaPE-1056) is a case in point: 180 km of LV reinforcement targeted at
   **PV inverter tripping**, a
   local over-voltage problem that a regional node, where rooftop PV never exports,
   cannot see.
4. **Scope effects in both directions.**
   * *Overstatement.* All industry electricity sits on the LV bus: 979 MW of the 2025
     peak and 2.7 GW in 2050. Most of it is connected to Elia (30–150 kV) or directly to
     MV, and does not use the DSO grid the model is charging it for. TIMES
     distinguishes the voltage levels (§5.1): in 2025, 20.6 TWh leave its HV grid, of
     which 14.4 TWh reach MV and 11.0 TWh LV, against 21.5 TWh through the PyPSA link.
   * *Understatement.* The 150/70/36 kV grid (Elia's "réseau de transport local" in
     Wallonia) is neither in the transmission representation nor in the distribution
     cost (§4.1).
5. **No renewal.** The existing grid never retires in the model, whereas renewal of
   ageing assets is a structural part of DSO capex. CWaPE lists age-based LV conversion
   (3×230 V → 3N400 V at 25 and 50 years), replacement of pre-1980 LV cables and of
   pre-1960 overhead lines among the planned measures (opinion 0967, §2.4.3).
6. **Items outside a system-cost model.** Losses (80.6 M€) are counted in the model as
   energy, not as grid cost. PSO, the road-use fee and smart meters (153 M€) are
   transfers or non-network activities and have no reason to appear in a
   technology-rich cost model, other than in an explicitly labelled "regulated add-on"
   line.

Point 4 matters for the *increments*, not just the level. The model's distribution
growth to 2050 (3.8 → 10.3 GW, +433 M€/a) is driven by heat pumps, inflexible EV
charging and industry electrification; the industry share of that growth is
misallocated.

### 2.4 Literature and other models

Items marked [S] were seen in secondary sources or abstracts only; everything else was
read in the primary source.

**The PyPSA-Eur value has no source.**

* **Origin.** technology-data's `inputs/costs_PyPSA.csv` carries "electricity
  distribution grid, investment, 500, EUR/kW, TODO". The PyPSA-Eur-Sec documentation
  repeats "currently assumed to be 500 Eur/kW" without a reference. We found no link to
  a published study.
* **Critique upstream.** PyPSA-Eur issue
  [#1760](https://github.com/PyPSA/pypsa-eur/issues/1760) points out that reusing it for
  gas boilers makes two thirds of a gas boiler's cost a grid charge.
* **A cheaper alternative now exists.** technology-data master adds
  `distribution grid reinforcement` at **188.6 €/kW** (2025 €), from DEA *Technology
  Data for el and DH*, v17 p. 15, "Cost of grid expansion". That figure covers only the
  local grid and substation strengthening caused by one new generator or large consumer.

**Incremental reinforcement cost per kW does not converge.**

| source | scope | value |
|---|---|---|
| DEA via technology-data | local grid + substation, per new connection | 189 €/kW |
| PyPSA-Eur / technology-data | "distribution grid", all LV peak | 668 €/kW (66 €/kW/a) |
| Priyadarshan et al., [arXiv:2410.04540](https://arxiv.org/abs/2410.04540) (2024) [S] | US residential full electrification, 600 GW of reinforcement for $350–790 bn | ≈ $580–1 320/kW |
| Turk, Schittekatte et al., *Energy Journal* 2025 [S] | US distribution LRMC used for tariff design | $50–150/kW (probably per year) |
| Navigant for Agora (2019) [S] | Germany LV+MV, EV integration | 1.5–2.1 bn€/yr to 2050 |

Our 668 €/kW sits inside that range. The problem is less the unit value than what it is
applied to: *all* LV coincident peak, the existing grid included, with a 2 % OPEX.

**How other models handle the existing grid.**

* **PRIMES** (E3M 2018 model description) computes grid costs by grid type on a
  regulated asset base that "includes capital costs of old infrastructure, cost of new
  investment and operating/maintenance costs". It recovers them through tariffs per
  voltage level. That is the D2 + D3 split proposed in §2.5.
* **Energy Transition Model** (Quintel, [network docs](https://docs.energytransitionmodel.com/main/network/)):
  * Layers are LV, LV/MV, MV, MV/HV and HV.
  * The used capacity of each layer is its hourly net peak, compared with *present*
    capacity minus a spare margin.
  * Only the excess is priced, in discrete steps: 200 kW at LV (about 100 households),
    2 MW at MV, 20 MW at HV.
* **TIMES-WAL** carries no grid cost in its grid processes (§5.1). We found no
  per-voltage grid cost in JRC-EU-TIMES or TIMES-PanEU in this pass.

**Aggregate benchmarks.**

* **Eurelectric, *Grids for Speed* (2024), EU27 + NO.** Distribution investment has to rise from €33 bn/yr (2019–23) to
  **€67 bn/yr over 2025–2050**, split LV 44 %, MV 41 %, HV 15 %. Anticipatory investment
  plus grid-friendly flexibility cuts it by about 18 %. Per inhabitant this is
  ≈ 150 €/yr, which would be about 0.55 bn€/yr of *investment* for Wallonia; the CWaPE
  plans (0.66 bn€/yr, §2.2) are of the same order.
* **IEA,
  [*Electricity Grids and Secure Energy Transitions*](https://www.iea.org/reports/electricity-grids-and-secure-energy-transitions)
  (2023).** Global grid investment has to nearly double, to over USD 600 bn/yr by 2030.
* **EU Grid Action Plan, COM(2023) 757** [S]. It cites €584 bn of grid investment this
  decade and notes that about 40 % of distribution grids are over 40 years old.

**Methodological points.**

* **Coincidence.** Consentec for E.ON, *Netz-Stresstest* (*et* 12/2020), uses
  heat-pump simultaneity factors of **1.0 at LV, 0.95 at MV/LV substations and 0.9 at
  MV** on a cold winter peak. Heat pumps are therefore almost fully coincident even
  locally, and the regional hourly peak captures them reasonably. EV charging and PV
  export are different: they are local, controllable or reversed flows, which a single
  regional LV bus understates or misses entirely.
* **Hourly vs 15-min peaks.** We found no source quantifying the gap; ETM also works on
  hourly peaks. Treat this as an unquantified bias, not a correction factor.
* **Pricing the existing grid at new-build cost** from the first year raises total cost.
  It also makes every kW of LV peak equally expensive, overstating the value of
  peak-shaving where headroom exists. Böttcher et al. (RWTH IAEW,
  [arXiv:2310.11853](https://arxiv.org/abs/2310.11853), 2023) represent each voltage
  level by stepwise expansion regions and note that linearisation "partially
  underestimates the grid costs".
* **Network types.** Pudjianto et al. (*Energy Policy* 2013) [S] and Böttcher et al.
  both separate rural, urban and mixed network types. A single BEWAL value blends rural
  Luxembourg-province MV/LV with the urban grids of Liège and Charleroi.

### 2.5 Proposals

**Now, with three Belgian nodes, same scenario**

| # | change | where | needs a re-solve? |
|---|---|---|---|
| D1 | Report electricity distribution alone, straight from the network (`nodal_costs.csv`), never mixed with gas | reporting | no |
| D2 | Add an explicit, **labelled "existing distribution grid" block**, calibrated on the **2025** CWaPE network core (678 M€; not 2029, which already contains the 2025–28 transition investments), with a renewal rule. It is sunk and exogenous, so it changes no decision but makes totals comparable with regulated revenues (§6.3, E1–E3) | reporting, or a non-extendable 2025 vintage | no (reporting) |
| D3 | Price only the **increment** above the 2025 peak, at the unit cost calibrated on the DSOs' transition capex: **620 €/kW (410–960)**, plus a PV hosting charge of 120 €/kWp (§6.3, E5 and E8). The literature brackets it between 189 €/kW (DEA local reinforcement) and about 1 000 €/kW (US full-electrification estimates); sensitivities go through `adjustments.sector.factor.Link.electricity distribution grid.capital_cost`. Replace the central value once CWaPE/ORES give the demand / PV split of the 2026–30 capex (§9, item 6) | master CSV, scenario overlay | yes |
| D4 | Take HV-connected industry off the LV bus, using TIMES's own split of HV / MV / LV deliveries (§5.1) | `insert_electricity_distribution_grid` (a few lines) | yes |
| D5 | Align distribution losses with TIMES (1.6 % HV, 2.7 % HV→MV, 3.2 % MV→LV, instead of a flat 3 %) | config `transmission_efficiency` | yes |
| D6 | Model DSO OPEX as a fixed block, mostly per connection, rather than 2 %/a of a capacity asset | reporting | no |

The `adjustments` factor also rescales the 2025 vintage, i.e. the existing grid. For a
sensitivity, read the effect on the 2030–2050 *increments* and on the decisions; the
reported level of the existing grid should come from D2, not from this factor.

Calibrated values, estimation methods and implementation for D1–D6 are in §6.3 (E1–E11).

D1, D2 and D6 alone bring the reported Walloon distribution cost to the level of the
regulated revenue without touching the optimisation. D3–D5 change the *decisions*
(how much flexibility, where heat pumps and EVs are worth it), and are therefore the
ones to discuss with TIMES first.

**Next phase, multi-node Belgium**

* One LV bus per node with a node-specific cost, calibrated per DSO area: ORES and RESA
  publish their authorised revenue separately, and the literature separates rural,
  urban and mixed network types (§2.4).
* A two-tier MV / LV representation, so that MV-connected industry and utility PV use
  only the MV tier and rooftop PV export can congest the LV tier.
* Peak coincidence handled explicitly: either sub-hourly peaks via a coincidence factor,
  or an exogenous hosting-capacity cap per node
  ([`network-representation-analysis.md`](network-representation-analysis.md) §9).

---

## 3. Gas networks

### 3.1 Gas distribution: how it is represented

**PyPSA.** There is no gas distribution network. `insert_gas_distribution_costs` adds
`gas_distribution_grid_cost_factor` (1.0) × the *electricity* distribution cost
(66.4 €/kW/a) to the capital cost of every extendable decentral gas boiler and micro-CHP.
Existing boilers, added by `add_existing_baseyear`, keep their plain boiler cost.
Consequences:

| BEWAL | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| decentral gas boilers, all vintages (GW_th) | 13.0 | 9.2 | 3.0 | 1.7 |
| of which built from 2025 (GW_th) | 1.7 | 1.9 | 3.0 | 1.7 |
| gas-grid charge in the model (M€/a) | 113 | 127 | 196 | 112 |
| gas slice in the chart (ClimAct, M€/a) | 65 | 54 | 47 | 27 |

* **The charge follows new boilers, not the grid.** In 2025, 87 % of the gas-boiler
  fleet pays nothing. In 2040 the charge peaks (196 M€) while gas volumes collapse. In
  2050 it is 112 M€ for 1.7 GW of boilers, about 66 €/kW, i.e. the equivalent of a full
  distribution grid per kW of boiler.
* **Industry, services' non-boiler uses and CHP pay no distribution cost at all.**
* **The fixed cost of the existing grid is absent**, and so are the choices that
  actually matter for Wallonia after 2030: keep, repurpose (biomethane, H₂) or
  decommission, and the rising cost per remaining customer. When a household leaves gas,
  the model avoids the 66 €/kW/a charge of a new boiler, a charge its old boiler never
  carried. The real saving is close to zero until the street is decommissioned.
* Losses, pressure levels, the number of connections and decommissioning costs are not
  represented.

**TIMES.** TIMES-WAL charges gas delivery by volume on its sectoral "Fuel Tech"
processes: residential 33.8 €/MWh in 2025, 53.4 in 2030, 56.2 in 2040 and 33.8 in 2050;
services 13.2–35.7; industry 6.6 €/MWh (§5.2). The profile over time suggests the
mark-up includes taxes or carbon levies, not only network tariffs.

### 3.2 Gas transmission, H₂ and CO₂

* **Methane transmission.** `gas_network: true`. The existing Fluxys pipelines between
  the 8 nodes are non-extendable, with capital cost from technology-data
  `CH4 (g) pipeline` (110 €/MW/km, 50 y, FOM 1.5 %); a small extendable
  `gas pipeline new` is built on BEWAL–LU. The cost of these existing pipelines is sunk
  and a constant in the objective, but it is reported as an annuity of their replacement
  value (13.8 M€/a for BEWAL at 50/50, 41.7 M€ under the ClimAct rule).
* **H₂.** New-build pipelines only (382 €/MW/km); retrofitting is off
  (`H2_retrofit: false`). 18.6 M€/a for BEWAL at 50/50 in 2030.
* **CO₂.** Endogenous pipelines, 2 672 €/(t/h)/km, carrying the CO₂ captured in
  Wallonia towards storage ([`ccs_alignment.md`](ccs_alignment.md)). They are the
  largest Walloon transmission item by 2050: 142.5 M€/a at 50/50 and 333 M€/a under the
  ClimAct rule. They are not a "grid" in the sense of the feedback and should be
  reported on their own line.

### 3.3 Literature and benchmarks

**Walloon gas DSOs.** CWaPE decisions CD-24c28-CWaPE-0890 (ORES gas) and -0891 (RESA
gas), authorised revenue, M€ nominal:

| | 2025 | 2026 | 2027 | 2028 | 2029 |
|---|---:|---:|---:|---:|---:|
| ORES gas | 218.5 | 222.2 | 226.2 | 230.7 | 235.3 |
| RESA gas | 116.5 | 117.4 | 117.0 | 118.2 | 119.6 |
| **total** | **335.0** | **339.6** | **343.2** | **348.9** | **354.9** |

The 2029 composition is:

* ORES: controllable 142.1 M€, of which capital-related 71.6; road-use fee 18.3; fair
  margin 61.1 (49.8 on the RAB).
* RESA: controllable 70.7 M€ (capital-related 27.3); road-use fee 8.6; margin 31.3.

The physical base at the end of 2025 (CWaPE opinion CD-26g30-CWaPE-0981, Tableau 2) is
**801 102 meters, 17 426 GWh distributed and 14 497 km of mains**. That puts the
existing gas distribution grid at about **420 € per meter per year, or 19 €/MWh**. More
than half of it is capital charges and margin on a RAB that does not shrink when
volumes do.

Set against the model:

* **Level.** 0.34 bn€/a regulated, against a gas-grid charge of 0.11–0.20 bn€/a in the
  model and 0.03–0.06 bn€/a in the chart.
* **Shape.** The regulated cost is flat to rising to 2029. The model's charge follows
  new boiler sales. The ClimAct slice declines with the boiler fleet.

The ICEDD study for CWaPE on the future of gas (final report 27/03/2025, published
2026) frames the question the model cannot answer today. It runs scenarios of 0–18 TWh
of residual gas in 2050, with a central case around 10 TWh, and depreciation periods of
33–50 years with an explicit stranded-asset risk. Only the 0 TWh case decommissions the
whole network. These study figures come from our research summary and have not been
re-checked here.

**How the literature treats gas distribution.** It treats it as a **fixed cost that
persists until physical decommissioning**, recovered through tariffs whose €/MWh rises
as volumes fall. Both of our models miss that. PyPSA drops the cost as soon as boilers
are not replaced; TIMES keeps a flat €/MWh mark-up, so there is no "death spiral".
Items marked [S] were seen in secondary sources only.

* **Germany.** Agora Energiewende with BET and Rosin Büdenbender,
  [*Ein neuer Ordnungsrahmen für Erdgasverteilnetze*](https://www.agora-energiewende.de/publikationen/ein-neuer-ordnungsrahmen-fuer-erdgasverteilnetze)
  (April 2023), finds that:
  * more than 90 % of the gas distribution grid is not needed by 2045;
  * grid fees rise 9–16× by 2044 if the fixed cost base is spread over falling volumes;
  * up to 10 bn€ is stranded, out of a residual value of 20–60 bn€ (10–20 % of
    replacement cost).
  
  Planned decommissioning with a bonus scheme saves up to 5 bn€/a.
* **United Kingdom** [S]. Ofgem's RIIO-3 finance annex, as summarised by
  [Regen](https://www.regen.co.uk/insights/who-will-pay-for-gas-network-decline-and-decommissioning),
  projects per-kWh charges that could reach 10 p/kWh by 2040 and 40 p/kWh by 2050. It
  puts the gas distribution RAV at £26 bn, with about £3 bn unrecovered by 2050 under
  45-year asset lives.
* **Decommissioning cost per connection** [S]. A survey of 115 DSOs in North
  Rhine-Westphalia (Verbraucherzentrale NRW) gives about 930 € to seal a house
  connection and 1 750 € to remove it, with a range of 100–4 000 €. We found no robust
  €/km figure.
* **Regulation.** Directive (EU) 2024/1788, Art. 57 [S; check the text], requires gas
  DSOs to draw up network decommissioning plans when falling demand calls for it. It
  makes an approved plan a prerequisite for refusing or cutting connections, and it had
  to be transposed by August 2026.

  The [CEER note on stranded assets in distribution networks](https://www.ceer.eu/wp-content/uploads/2024/04/C19-DS-55-07_CEER-note-on-stranded-assets-in-distribution-networks-II.pdf)
  (2020) lists accelerated depreciation, revaluation, cost-of-capital adjustment and
  compensation outside tariffs as the tools available.
* **PyPSA-Eur itself.** The gas distribution charge on boilers and micro-CHP was
  introduced in PyPSA-Eur-Sec v0.3.0 (September 2020). We found no justification for
  `gas_distribution_grid_cost_factor: 1.0`, i.e. for pricing a kW of gas boiler like a
  kW of electricity distribution.

**H₂ and CO₂ pipelines.**

* **H₂.** The model uses the 2021 European Hydrogen Backbone cost (382 €/MW/km new,
  163 repurposed). The [EHB 2022 update](https://ehb.eu/files/downloads/ehb-report-220428-17h00-interactive-1.pdf)
  is lower, at 2.8 M€/km new and 0.5 M€/km repurposed for a large 48″ pipe, i.e. about
  215 and 38 €/MW/km. That makes the model's H₂ network conservative by a factor of
  about 1.5–4.
* **CO₂.** The model's cost (Danish Energy Agency, 12″, 120–500 t/h) is **linear in
  capacity**. It matches ZEP estimates at small scale but ignores economies of scale on
  trunks: a 1 800 t/h line such as BEWAL–DE in 2030 comes out at about 4.9 M€/km. The
  JRC puts the EU network at 0.6–0.9 M€/km on average (Tumara et al. 2024,
  [doi:10.2760/582433](https://publications.jrc.ec.europa.eu/repository/bitstream/JRC136709/JRC136709_01.pdf)).
  The CO₂ line of the *Transport* bar is therefore probably overstated as well as
  misallocated (§4.2).
* **Belgian context.** The Walloon capture projects listed by the JRC are Anthemis
  (Antoing, 0.8 Mt/a), GO4ZERO (Obourg, 1.3 Mt/a) and LEILAC (Lixhe). Fluxys c-grid is
  the designated CO₂ network operator for Wallonia and Flanders. It has proposed
  corridors for Tournai, Mons–Charleroi, Namur and Liège, but has published no cost
  figures yet.

### 3.4 Proposals

**Now**

| # | change | needs a re-solve? |
|---|---|---|
| G1 | Report gas distribution on its own line, computed from the model's own charge (or from G2), not recomputed with the extractor's cost file | no |
| G2 | Replace the per-boiler charge by (a) a **fixed existing-grid block** calibrated on the CWaPE gas authorised revenues (0.34 bn€/a, §3.3), following an explicit decommissioning pathway, and (b) a small per-kW charge representing only what is avoidable when one customer leaves: connection, meter, and a share of LV mains O&M | yes for (b) |
| G3 | Put methane transmission, H₂ and CO₂ pipelines on separate lines of the *Transport* bar | no |
| G4 | Update the H₂ pipeline cost to EHB 2022, and give CO₂ pipelines a scale-dependent cost (piecewise by diameter class) instead of the linear DEA value | yes |

Calibrated values, estimation methods and implementation for G1–G4 are in §6.4
(GD1–GD6) and §6.5 (TR10–TR12).

**Next phase.** A gas decommissioning trajectory by zone (urban mains kept for biomethane
and H₂, rural mains decommissioned) only makes sense with more than one Walloon node, and
should be designed jointly with TIMES so that both models see the same cost per
remaining customer.

---

## 4. Electricity transmission

### 4.1 CAPEX and OPEX

#### 4.1.1 What is costed

Only the branches **between** the model's nodes: BEVLG–BEWAL, BEBRU–BEWAL, BEWAL–FR,
BEWAL–LU and ALEGrO (BEWAL–DE, DC). The whole internal Elia grid of each region
(380/220/150 kV and the 70/36 kV local transmission grid) disappears in the clustering
into three Belgian nodes, and so do substations and transformers.

| Walloon branch (2030) | type | capacity (MW) | modelled length (km) | annual cost (M€) |
|---|---|---:|---:|---:|
| BEVLG–BEWAL | AC | 5 094 | 110 | 39.8 |
| BEBRU–BEWAL | AC | 3 396 | 96 | 23.1 |
| BEWAL–FR | AC | 2 433 | 400 | 69.0 |
| BEWAL–LU | AC | 343 | 90 | 2.2 |
| BEWAL–DE (ALEGrO) | DC | 1 000 | 281 | 76.4 (+60.4 double-counted, §4.1.4) |

#### 4.1.2 Unit costs

From technology-data v0.14.0, i.e. Danish Energy Agency, *Technology Data for Energy
Transport*, July 2025. Annuity at 7.5 % over 40 y plus FOM:

| item | investment 2025 → 2050 | FOM | annual cost 2030 |
|---|---|---:|---:|
| HVAC overhead | 750 → 620 €/MW/km | 1.5 % | 70.8 €/MW/km/a |
| HVDC overhead | 600 → 500 €/MW/km | 1.5 % | 56.6 €/MW/km/a |
| HVDC submarine | 3 220 → 2 680 €/MW/km | 2.5 % | 336 €/MW/km/a |
| HVDC converter pair | 640 → 540 €/kW | 1.5 % | 60.4 €/kW/a |

* **Lengths are centroid-to-centroid distances × 1.25.** With one node per neighbouring
  country, BEWAL–FR is 400 km and ALEGrO 281 km, against a real route of about 90 km
  (§4.3).
  An interconnector is therefore also paying for a notional share of the neighbour's
  internal grid. For AC lines, whose cost is purely per km, that convention drives the
  whole cost. For ALEGrO the converter pair dominates, so the modelled length inflates
  its annual cost by about 17 %.
* **The cost applies to nominal thermal rating.** With `s_max_pu = 0.7`, a usable MW of
  AC capacity costs 1/0.7 = 1.43× the unit cost.
* **Existing branches carry the same annuity as new ones** in the reports, although their
  cost is sunk. The reported *Transport* cost is therefore a replacement-value annuity of
  the whole inter-node grid, not what Elia recovers in tariffs.
* **Minor inconsistency.** In the first horizon the lines are costed with the 2050 unit
  cost (620 €/MW/km, from `costs.year: 2050` in `add_electricity`), then re-costed per
  horizon from 2030.

#### 4.1.3 OPEX

The FOM above is the only OPEX. AC losses are modelled physically
(`transmission_losses: 2`) and DC losses as 2 % plus 2.3 %/1000 km; their cost is energy
booked in production and imports. The model has no reserves, redispatch, black-start or
other system services, and no levies. These are a large part of Elia's tariff (§4.3).

#### 4.1.4 Bug: HVDC converters counted twice from 2030 on

`lossy_bidirectional_links` splits each DC link into a forward leg and a zero-length
`-reversed` twin with `capital_cost = 0`. `add_brownfield` then re-runs
`set_transmission_limit` for every horizon after the first, and `set_transmission_costs`
re-prices every `carrier == "DC"` link, twins included. With zero length, each twin gets
exactly the converter-pair annuity.

In `scen_central` this adds 616 / 509 / 523 M€/a system-wide in 2030 / 2040 / 2050, and
60.4 M€/a on ALEGrO alone in 2030. Because the twin's capacity is tied to the forward
leg, the **cost of expanding DC borders** in 2040/2050 is overstated as well. That is a
plausible cause of the under-build recorded in
[`network-representation-analysis.md`](network-representation-analysis.md) §3.1.2:
BE–GB at 41 % and BE–DE at 47 % of their NTC ceiling while at their limit half of the
time. It is filed as a separate task. The fix is a one-line exclusion of
`reversed == True` links and needs a re-solve.

### 4.2 Allocation between nodes

| rule | where | effect for Wallonia, 2030 |
|---|---|---|
| none: the objective is one system cost | `solve_network` | — |
| each branch 50/50 between its two ends; before 2026-09-15 100 % to `bus0` | `make_summary` → `csvs/nodal_costs.csv` | 245.7 M€ (105.2 for electricity once §4.1.4 is corrected) |
| **pool per carrier over the whole 6-country system, split by each node's share of connected capacity** (MW, both ends for bidirectional branches, origin only for one-way pipelines, length ignored) | ClimAct extraction → chart | **507.0 M€** |

Under the ClimAct rule Wallonia pays a share of FR–DE, GB–FR, NL–DE and every other
corridor of the modelled system, and pays it by MW regardless of length. It carries
6.9 % of the system's AC+DC cost under that rule, against 3.6 % under a 50/50 split of
the branches it actually touches. Neither rule matches how the network is paid for:
Elia's tariffs are a **national postage stamp**, identical across Belgium for a given
connection voltage.

**Recommendation.** For regional cost reporting, use two numbers side by side:

1. **Direct cost** of the branches touching the region, 50/50 (`nodal_costs.csv`). This
   is physically interpretable and is what the multi-node model will refine.
2. **Tariff-consistent cost**: the Belgian transmission cost, ideally Elia's allowed
   revenue (§4.3), times Wallonia's share of Belgian offtake. This is what Walloon users
   actually pay.

Stop using the capacity-pooled rule for regional figures.

### 4.3 Benchmarks

**Elia's allowed revenue (Belgium, all voltages ≥ 30 kV).** CREG decision (B)658E/85
of 9 Nov 2023, Tableau 1bis, M€ nominal:

| 2022 (actual) | 2024 | 2025 | 2026 | 2027 |
|---:|---:|---:|---:|---:|
| 925.3 | 970.7 | 1 552.1 | 1 706.4 | 1 876.0 |

The budget breakdown is confidential. The 2022 actuals show what a transmission
revenue is made of:

* depreciation 197.5 M€
* controllable costs 388.7 M€
* ancillary services: use 284.1 M€ and reservations (R1/R2/R3) 262.7 M€
* net fair margin 116.7 M€
* corporate tax 42.4 M€
* interconnection and congestion income −422.0 M€

The 2024–27 tariff is built on a **6.4 bn€ investment programme**. The same decision
notes 2 bn€ for 2016–19 and 1.5 bn€ for 2020–23.

**Walloon local transmission (30–70 kV).** CWaPE's decision on Elia's 2026–2036
adaptation plan (CD-26g30-CWaPE-1283, 30/07/2026) covers **691 M€ of investment over
2026–30**. The same decision notes that Elia realises 107.4 M€/yr (78 % of what it
announces), and only 48 % of its announced local-transmission budget on an 11-year
average. None of this grid is in the model.

**Interconnector reality check.** ALEGrO is about 90 km of HVDC cable, Lixhe–Oberzier,
1 GW, commissioned in 2020, at roughly 0.5 bn€. The model has it at 281 km, at 76 M€/a
(0.81 bn€ overnight equivalent), before the double-counting of §4.1.4. These ALEGrO
figures come from the ENTSO-E TYNDP 2016 project sheet (project 92), as reported by our
research summary, and have not been re-checked here.

**Order of magnitude of the gap.** A tariff-consistent Walloon share, Elia's 2027
revenue × about 25 % of Belgian offtake (the BEWAL share of electricity withdrawals in
the 2030 network; 23 % in 2025), is **≈ 0.45–0.5 bn€/a**. The model's direct
electricity transmission cost for BEWAL is 0.105 bn€/a (2030, 50/50, corrected for
§4.1.4). The factor of about 4.5 is not
a like-for-like error, for three reasons:

* Elia's revenue contains system services and offshore costs, and is net of congestion
  income.
* The model contains none of the internal grid.
* The model's interconnectors are over-long.

Still, it shows that the *Transport* bar compares even worse with the regulated
benchmark than *Distribution* does. The pooled ClimAct rule only happened to land
closer, at 0.26 bn€ for electricity.

**Unit costs are not the problem.** ACER, *Unit Investment Cost indicators* (April
2026, commissioned projects, HICP-adjusted), gives the following medians:

| asset | ACER median | ACER mean |
|---|---:|---:|
| 400 kV overhead line, 1 circuit | 0.52 M€/km | 0.60 |
| 400 kV overhead line, 2 circuits | 1.18 M€/km | 1.46 (max 4.87) |
| 220 kV underground cable, 1 circuit | 2.08 M€/km | — |
| HVDC converter | 0.21 M€/MW | — |

ACER also finds costs rising about 6 %/yr above inflation since 2018.

At roughly 1.8 GVA per 380 kV circuit, the double-circuit median is about 330 €/MW/km,
less than half the DEA 750 €/MW/km in the model. ACER's line figures exclude
substations, so the comparison is indicative only. On converters, if the ACER figure
is per station, a pair costs about 420 €/kW against the model's 640 €/kW.

The model's per-km costs are therefore on the high side of observed projects.
Advanced conductors (HTLS reconductoring) are reported to roughly double capacity on an
existing right-of-way at a third to a half of new-build cost [S: Chojkiewicz et al.,
PNAS 2024]. That matters for the 2040/2050 HTLS headroom in the NTC tables.

The gap with Elia's revenue is a matter of **scope**:

* the internal grid, 380 kV down to 36 kV, is missing;
* substations and transformers are missing;
* system services (reserves, redispatch) are missing;
* offshore costs are missing.

On top of that, interconnector lengths are inflated by the one-node-per-country
convention, which the multi-node model will correct.

### 4.4 Proposals

**Now**

| # | change | needs a re-solve? |
|---|---|---|
| T1 | Fix the reversed-DC costing (§4.1.4) | yes |
| T2 | Split *Transport* into electricity / methane / H₂ / CO₂, and use the 50/50 direct cost plus the tariff-consistent cost (§4.2) instead of the pooled rule | no |
| T3 | Add a labelled **"Elia grid not represented"** block for the internal 380–36 kV grid and system services, calibrated on the CREG-approved revenue × the Walloon share of offtake | no |
| T4 | For the committed projects of the NTC tables (Boucle du Hainaut, Lonny–Achêne–Gramme, the second BE–DE HVDC, Nautilus), use project costs and real route lengths instead of centroid distance × DEA unit cost | yes |

Calibrated values, estimation methods and implementation for T1–T4 are in §6.5
(TR1–TR13).

**Next phase.** With 10–20 Belgian nodes, internal corridors become explicit lines with
real lengths, and the 150 kV and 70/36 kV levels can be added for Belgium only
([`network-representation-analysis.md`](network-representation-analysis.md) §8). The
Walloon transmission cost then becomes a sum over Walloon branches plus 50/50 of the
cross-border ones. The postage-stamp figure should stay as the tariff view.

---

## 5. The TIMES side

### 5.1 Grid processes: losses only

`EVTRANS_H-H` (HV grid), `EVTRANS_H-M` (HV→MV and grid), `EVTRANS_M-L` (MV→LV and
grid) and `EVTRANS_L-M` (LV→MV, unused) carry flows. They have no `Cost_Inv`,
`Cost_Fom`, `Cost_Act`, `VAR_Cap` or `VAR_Ncap` rows in the solution dump. The `.vd` only
writes non-zero attributes, so either these processes have no cost in TIMES-WAL, or
their cost is booked elsewhere. `scen_central_v01_260911_1109.vd`, TWh:

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| into the HV grid | 20.97 | 24.35 | 42.59 | 56.24 |
| HV → MV | 14.43 | 16.71 | 28.19 | 38.06 |
| MV → LV | 11.00 | 12.67 | 20.82 | 28.76 |
| implied losses | 1.6 % HV, 2.7 % HV→MV, 3.2 % MV→LV | | | |

LV deliveries grow 2.6× between 2025 and 2050. That is the electrification the feedback
refers to. Its cost is endogenous in PyPSA (§2.1) but not, it seems, in TIMES.

### 5.2 Delivery mark-ups on "Fuel Tech" processes

TIMES-WAL puts `Cost_Act` on its sectoral fuel-technology processes. Divided by activity,
in €₂₀₂₁/MWh (the model currency is `MEUR21`):

| process | 2025 | 2030 | 2040 | 2050 | M€ in 2050 |
|---|---:|---:|---:|---:|---:|
| `RSDELC00` residential electricity | 179.5 | 179.5 | 179.5 | 179.5 | 1 171 |
| `COMELC00` services electricity | 94.1 | 94.1 | 94.1 | 94.1 | 1 219 |
| `INDELC00` industry electricity | 24.6 | 24.6 | 24.6 | 24.6 | 571 |
| `AGRELC00` agriculture electricity | 91.7 | 91.7 | 91.7 | 91.7 | 6 |
| `RSDGMX00` residential gas | 33.8 | 53.4 | 56.2 | 33.8 | 118 |
| `COMGMX00` services gas | 13.2 | 32.8 | 35.7 | 13.2 | 27 |
| `INDGAS00` / `INDGMX00` industry gas | 6.6 | 6.6 | 6.6 | 6.6 | 20 |
| `RSDOIL00` residential oil | 27.0 | 54.2 | 92.8 | — | — |

Electricity mark-ups reach 1.7 bn€/a in 2025 and 3.0 bn€/a in 2050. The residential
179.5 €/MWh is close to the non-energy part of a Walloon household bill: distribution,
transmission, levies and excise, excluding VAT. The rising oil and gas mark-ups look like
a carbon levy (ETS2). **This is our reading of the data and has to be confirmed with
ICEDD**, because the consequences differ:

* If the mark-ups contain network tariffs, TIMES already carries a **volumetric**
  distribution cost. It grows with kWh, not with peak, and adding PyPSA's distribution
  cost on top would double-count.
* If they contain taxes, they are transfers. They must be excluded from any system-cost
  comparison, but they still drive TIMES's technology choice. At 179.5 €/MWh for
  electricity against 33.8 €/MWh for gas, residential electrification is heavily
  penalised in TIMES, and that mix is what PyPSA pins its heating to (option B′,
  [`heat-softlink.md`](heat-softlink.md)).

### 5.3 What the cost chart can and cannot say

The chart is a PyPSA-only view of supply-side, storage and network costs. It omits the
demand-side costs that live in TIMES (vehicles, appliances, renovation), and it uses a
different TIMES run for each scenario (`scen_retardnucleaire` reads
`scen_sensibilite_retardnucleaire_260911_1109.vd`). We therefore agree it should not be
shown as a total system cost, nor used to compare scenarios, until the TIMES costs are
added on a consistent perimeter.

Networks are not what drives the 2050 central-vs-delayed-nuclear gap: *Transport* moves
by 30 M€ and *Distribution* by 36 M€, 5 % of the 1.29 bn€/a difference. Correcting the
network *levels* as proposed here moves both scenarios by about the same amount.

---

## 6. Calibration plan for the current formulation

This section turns §2–§5 into a parameter-by-parameter plan for the model as it stands:
three Belgian nodes, one LV bus per node, inter-node branches only. Every value is
derived from the data gathered for this note. Where a parameter cannot be observed
directly, §6.6 gives the estimation method and the data that should eventually replace
it. Changes that go beyond parameters and small code hooks are left to §8.

### 6.1 Principles

**1. Four cost layers per network.**

| layer | content | treatment in the current formulation | drives decisions? |
|---|---|---|---|
| **L1 — existing grid** | capital charges of the assets in service in the base year | exogenous block, calibrated on the 2025 regulated accounts, evolved with a renewal rule | no |
| **L2 — increment** | reinforcement caused by the scenario: peak growth, PV, new branches | endogenous: optimal capacity × annualised unit cost | **yes** |
| **L3 — non-capacity OPEX** | customer service, metering, IT, system operation | exogenous block, per connection or per MWh | no |
| **L4 — losses, add-ons, transfers** | losses; PSO, road-use fee, smart meters, taxes, system services | losses endogenous through the link efficiency; everything else exogenous and used for bills only (§7) | losses only |

**2. Calibrate on 2025, validate on 2029.** The 2029 authorised revenue already contains
the capital charges of the 2025–28 transition investments, which the model builds itself
as L2. Calibrating L1 on 2029 would count them twice. 2029 is kept as an out-of-sample
check (V5 in §6.3).

**3. Only L2 and the losses need a re-solve.** L1, L3 and L4 are reporting layers and can
be added to the existing September runs.

**4. Price base.** CWaPE and CREG figures are nominal. PyPSA costs are real EUR2025
(master CSV) and TIMES costs are MEUR21. Deflate regulatory figures with the Belgian
HICP, and state the base in every table.

**5. One financial convention for regulated networks** (§6.2).

### 6.2 Financial parameters common to all networks

| parameter | current | calibrated | range | basis | where |
|---|---|---|---|---|---|
| discount rate of network assets *r*<sub>net</sub> | 7.5 % (TIMES power/supply hurdle) | **3.5 % real, pre-tax** | 3.3–5 %; keep 7.5 % as a sensitivity | See note below | new `hurdle:networks` row in `input_parameters_for_models.csv`, mapped in `config/hurdle_rate_mapping.csv` (see note), then `build_common_parameters.py --write` |
| lifetime | 40 y (electricity), 50 y (pipelines) | unchanged | 40–50 y | regulatory depreciation periods of 33–50 y for gas assets (ICEDD gas study, research summary) | — |
| FOM of new network assets | 2 % (distribution), 1.5 % (lines, DC, CH₄) | unchanged | 1.5–2 % | DEA; asset-related share of DSO OPEX (E2 below) | — |

*Basis for r*<sub>net</sub>. The CWaPE 2025–29 methodology allows **4.03 %** on the RAB
after corporate tax. Fair margin plus tax is 5.37 % of the RAB, pre-tax and nominal,
i.e. about 3.3 % real at 2 % inflation. That equals the config's
`social_discountrate: 0.035`.

*Mapping.* The new row applies to `electricity distribution grid`,
`electricity grid connection`, `HVAC *`, `HVDC *`, `CH4 (g) pipeline*`,
`H2 (g) pipeline*` and `CO2 pipeline*`.

Annuity plus 2 % FOM falls from **9.94 % to 6.68 %** of the investment (40 y), i.e.
−33 %; it is 6.26 % at 50 y. This is a shared parameter. It has to be agreed with ICEDD
even though TIMES has no network investment today, because §7 uses it to turn network
investment into tariffs.

### 6.3 Electricity distribution

**Calibration targets.** 2025 budgets of the five CWaPE decisions (Tableau 4 / 8,
*Budget 2025* column), M€ nominal:

| item | 2025 | note |
|---|---:|---|
| authorised revenue | 896.3 | |
| network core (L1 + L3) | **677.9** | OPEX 287.4 + depreciation 197.2 + margins 151.8 + corporate tax 41.5 |
| of which capital charges (L1) | **390.5** | depreciation + margins + tax |
| of which OPEX (L3 and asset maintenance) | 287.4 | |
| losses | 87.0 | energy purchases |
| road-use fee / smart meters | 43.8 / 22.9 | L4 |
| RAB (derived) | ≈ 3.10 bn€ + 0.67 bn€ revaluation | margins ÷ 4.03 % |
| electricity EAN (2024) | 1.95 M | CWaPE opinion 0967, §2.3.4 |
| energy withdrawn at distribution (2024) | 12.68 TWh | same, excluding compensated volumes |

Unit values of the network core: 348 €/EAN/yr, 53.5 €/MWh, and 219 €/kW/a of the 2025
LV peak after E6 (3.09 GW).

**Parameters.**

| id | parameter | current | calibrated central (range) | data and method | implementation | re-solve |
|---|---|---|---|---|---|---|
| E1 | existing-grid capital charges | implicit: 3.78 GW × 66.4 = 251 M€ | **390.5 M€** (2025) | CWaPE 2025 budgets (above) | reporting block. Optionally overwrite the capital cost of the carried-forward 2025 vintage in `add_brownfield`; it is sunk, so decisions are unaffected | no |
| E2 | existing-grid OPEX | 2 % FOM ≈ 50 M€ | **287 M€**: asset-related 85–190, per connection 100–200 (50–100 €/EAN/yr) | asset part = 1.5–2 % × replacement value (§6.6); the remainder is per EAN | reporting block; per-EAN part indexed on the EAN count (+1 %/yr, CWaPE) | no |
| E3 | evolution of E1 (renewal) | none: nothing retires before 2065 | held **constant in real terms**; sensitivity +1 %/yr real | Renewal and compliance capex 2026–30 is 227 M€/yr against depreciation of 197 M€/yr, i.e. renewal ≈ depreciation plus catch-up. *Grids for Speed*: about 27 % of distribution capex is replacement [S] | reporting block | no |
| E4 | discount rate / lifetime | 7.5 % / 40 y | 3.5 % / 40 y (§6.2) | — | master CSV | yes |
| E5 | incremental reinforcement cost *c*<sub>inc</sub> | 668 €/kW | **620 €/kW (410–960)** | See note below | `cost:electricity distribution grid:investment` in the master CSV; `adjustments` factor for the range | yes |
| E6 | load behind the link | all industry electricity on LV | move **70 %** of `industry electricity` to the transmission bus | TIMES draws 5.8 of 8.3 TWh of industrial electricity at HV in 2025, 6.8 of 9.7 in 2030 and 16.2 of 23.2 in 2050 (`VAR_FIn` on `ELCHIGG` vs `ELCMED`) | a few lines in `insert_electricity_distribution_grid`: split the load with a per-horizon share read from the TIMES export | yes |
| E7 | distribution losses | 3 % static | **5 %** (`efficiency_static: 0.95`) | TIMES: HV→MV 2.7 % and MV→LV 3.2 %. Weighting LV (0.942) and MV (0.973) deliveries by 2025 volumes gives 0.949. Cross-check: 5 % × 14 TWh × ~120 €/MWh ≈ 84 M€, against 87 M€ of DSO loss purchases | `sector.transmission_efficiency.electricity distribution grid` | yes |
| E8 | PV hosting cost *c*<sub>host</sub> | 0: at a regional node rooftop PV never congests the grid | **120 €/kWp (0–250)** | the PV share of E5's transition capex, over new rooftop PV 2025–30 (1.58 GWp). Bounds: DEA local reinforcement per new generator (189 €/kW) and PV-specific capex (E1.4 + ORES LV task force ≈ 50 M€ → 32 €/kWp) | adder on the `solar rooftop` capital cost (two lines after rooftop PV is added, or a custom-cost row) | yes |
| E9 | local-vs-regional diversity *k*<sub>div</sub> | 1 | **keep 1** | E5 is expressed per kW of *regional* coincident peak, so diversity is already inside it. The sub-hourly effect is +0.6 % at national level: Elia 2024, max 15-min 13 282 MW vs max hourly 13 206 MW | if ever needed, `p_max_pu = 1/k_div` on the link | — |
| E10 | flexibility credit φ | 1 (implicit) | 1 central, **0.5 as a sensitivity** | home batteries shave 1.4 GW off the 2050 regional peak, a credit local grids may not see. *Grids for Speed*: flexibility −18 % of investment; Priyadarshan et al.: DSM up to −¾ [S] | one constraint per snapshot in `extra_functionality`: `p_nom_dist ≥ flow(t) + (1−φ)·home-battery discharge(t)` | yes |
| E11 | regulated add-ons | absent | PSO 48, road fee 44, smart meters 23 → 57 (2029), other 13 M€ | CWaPE | bill module only (§7) | no |

*Basis for E5.* CWaPE opinion 0967, Tableau 15, puts **transition-driven capex at
774 M€ over 2026–30**:

* E1.1 "évolution prévisible de la consommation et pointes de charge": 649 M€
* E1.3 congestion: 1 M€
* E1.4 voltage quality: 35 M€
* the Walloon government's transition subsidy: 88 M€

Adding E2.4 voltage harmonisation (129 M€) gives 903 M€. The model's LV peak increase
over 2025–30, after E6, is 0.94 GW. The PV-driven share *s*<sub>PV</sub> of that capex
is unknown (§6.6), so the result is a table (below). With E2.4 the upper value is
961 €/kW. The calibrated value is close to the current 668 €/kW.

**Splitting E5 between demand and PV (E8).**

| PV share of transition capex | *c*<sub>inc</sub> (€/kW of LV peak) | *c*<sub>host</sub> (€/kWp) |
|---:|---:|---:|
| 0 | 823 | 0 |
| **0.25 (central)** | **618** | **123** |
| 0.5 | 412 | 246 |

**Validation checks after calibration.**

| id | check | target |
|---|---|---|
| V1 | reported 2025 distribution cost, L1 + L3 | 678 M€ (CWaPE core 2025) |
| V2 | model new-build 2025→30, overnight | ≈ 0.77 bn€ (transition capex), ± the flexibility effect |
| V3 | energy through the link, 2025 | ≈ 14–15.5 TWh. After E6 the link carries 15.5 TWh, against TIMES MV + LV consumption of 14.1 TWh and DSO withdrawals of 12.7 TWh (plus compensated volumes and losses) |
| V4 | loss cost | ≈ 87 M€/a |
| V5 | 2030 reported cost vs the CWaPE 2029 core | within ±10 % in real terms (735 M€ nominal ≈ 680 M€₂₀₂₅) |

**What the calibration does to the Walloon distribution cost.** Illustrative, *not
re-solved*. It combines the existing block, the increments at 620 €/kW and PV hosting
at 120 €/kWp, at 3.5 %/40 y plus 2 % FOM, on the peaks of the current networks with E6
applied. M€₂₀₂₅/a:

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| current model (distribution link) | 251 | 320 | 521 | 684 |
| LV peak after E6 (GW) | 3.09 | 4.03 | 6.35 | 8.44 |
| rooftop PV (GWp) | 1.77 | 3.35 | 7.91 | 9.01 |
| L1 + L3 existing grid | 678 | 678 | 678 | 678 |
| L2 demand increment | — | 39 | 135 | 221 |
| L2 PV hosting | — | 13 | 49 | 58 |
| **recalibrated total** | **678** | **729** | **862** | **957** |

The recalibrated 2030 figure sits within 7 % of the CWaPE 2029 core in real terms. Most
of the correction is L1 + L3, which changes no decision. The decision-relevant part (L2)
actually becomes *smaller* than the model's current increments: 52 vs 70 M€ in 2030, and
279 vs 433 M€ in 2050. Three effects combine: the lower discount rate, HV industry
leaving the LV bus, and a calibrated *c*<sub>inc</sub> close to today's value. Only the
new PV hosting charge adds to it. A re-solve with these values will therefore not make
flexibility more attractive on distribution grounds; if anything, slightly less.

### 6.4 Gas distribution

**Calibration targets.** 2025 budgets of CD-24c28-CWaPE-0890 (ORES gas) and -0891 (RESA
gas), M€ nominal:

| item | 2025 | note |
|---|---:|---|
| authorised revenue | 335.0 | ORES 218.5 + RESA 116.5 |
| network core (L1 + L3) | **282.0** | OPEX 88.9 + depreciation 92.2 + margins 81.9 + tax 19.0 |
| road-use fee / PSO / other | 25.8 / 22.7 / 4.5 | L4 |
| RAB | 1 866 M€ + ≈ 0.33 bn€ revaluation | 1 288 + 578 at 1 Jan 2025, from the decisions |
| gross capex | 117.4 M€ (2025); 104.6 M€/yr planned 2027–31 | CWaPE 0981 |
| meters / energy / mains (end 2025) | 801 102 / 17 426 GWh / 14 497 km | CWaPE 0981, Tableau 2 |

Unit values of the core: **352 €/meter/yr, 16.2 €/MWh** (19.2 €/MWh on the total).

**Parameters.**

| id | parameter | current | calibrated central (range) | data and method | implementation | re-solve |
|---|---|---|---|---|---|---|
| GD1 | existing gas-grid block (L1 + L3) | absent (0.03–0.06 bn€ slice in the chart) | **282 M€** (2025) | RAB rule: RAB(t+1) = RAB(t) + capex(t) − depreciation(t), with capex from a decommissioning pathway. Two pathways: *keep*, where capex continues at the 2027–31 plan (≈ 105 M€/yr against 92 M€/yr of depreciation) and the RAB stays roughly flat; and *managed decommissioning*, capex limited to mains kept and depreciation accelerated as the regulator allows. OPEX is split per km of mains in service and per meter | reporting block, per pathway | no |
| GD2 | avoidable cost per customer, i.e. the per-boiler charge | 66.4 €/kW_th/a (`gas_distribution_grid_cost_factor: 1.0`) | **5 €/kW_th/a (3–7)**, which is factor **0.075** today or **0.12** after E4/E5 | controllable OPEX of 111 €/meter/yr, about half of it customer-driven, plus the meter annuity gives 50–110 €/meter/yr; divided by the 16.2 kW_th of BEWAL boiler per meter | config `sector.gas_distribution_grid_cost_factor` (scenario overlay); recompute the factor whenever the electricity distribution cost changes | yes |
| GD3 | scope of GD2 | new decentral boilers and micro-CHP | unchanged | existing boilers are sunk; industry and CHP carry their network share in GD1 | — | — |
| GD4 | decommissioning cost | absent | **930–1 750 € per connection** (seal vs remove) [S]; mains sealed and left in place | NRW survey of 115 DSOs; number of disconnections from the TIMES dwelling stock | reporting block | no |
| GD5 | tariff per MWh (for bills) | flat TIMES mark-up | GD1 ÷ distributed volume | A flat core block over TIMES residential and services volumes (`RSDGMX00` + `COMGMX00`: 15.9 / 15.6 / 8.3 / 5.5 TWh in 2025/30/40/50) gives **18 / 18 / 34 / 51 €/MWh** | §7 | no |
| GD6 | distribution losses | absent | leave absent | negligible in cost | — | — |

The ClimAct gas slice must be recomputed from GD1–GD2, or dropped: its CZ cost file and
⅓ factor match neither the model nor the regulator (§1.1). Industrial gas needs a
distribution/transmission split before GD5 can be applied to it. CWaPE distributes
17.4 TWh (2025), against 15.9 TWh of residential and services gas in TIMES plus part of
industry (§9, item 10).

### 6.5 Transmission: electricity, methane, H₂ and CO₂

**Calibration targets (electricity).**

* **Elia allowed revenue** (Belgium): 1 552 M€ in 2025 and 1 876 M€ in 2027.
* **2022 structure:** grid capital 425 M€ (46 %), controllable OPEX 389 M€ (42 %),
  ancillary services 547 M€ (59 %), interconnection income −422 M€ (−46 %).
* **Investment:** 6.4 bn€ over 2024–27 for Belgium; 691 M€ over 2026–30 for Walloon
  30–70 kV, with a 48 % historical realisation rate.
* **Walloon share of Belgian offtake:** 22.7 % (2025), 25.4 % (2030) and 36 % (2050) in
  the model. TIMES gives 26 % for 2025: 21.0 TWh into the Walloon HV grid against the
  81.0 TWh of Belgian load Elia measured in 2024.

**Parameters.**

| id | parameter | current | calibrated central (range) | data and method | implementation | re-solve |
|---|---|---|---|---|---|---|
| TR1 | existing grid, tariff view (L1 + L3) | existing inter-node branches at replacement annuity (88 M€ for BEWAL at 50/50, 2025) | **Walloon share × Elia allowed revenue**: 350–400 M€ (2025), 450–490 M€ (2027); model branches existing in 2025 set to 0 in this view | CREG B658E/85 × offtake share. Split system services and interconnection income out once Elia's yearly breakdown is obtained (§9, item 8) | reporting block | no |
| TR2 | new AC branch cost | 750 → 620 €/MW/km (DEA) | **450 €/MW/km (350–750)** | ACER UIC 2026: 400 kV double circuit, median 1.18 M€/km ÷ ~3.4 GW ≈ 350, plus a substation share. DEA is kept as the high case | master CSV `cost:HVAC overhead:investment` | yes |
| TR3 | capacity added by HTLS on existing corridors | same as new build | **⅓–½ of TR2** (150–225 €/MW/km) [S] | Chojkiewicz et al., PNAS 2024. Applies to the 2040/2050 HTLS headroom of the NTC tables (BEWAL–BEVLG 13.2 → 14.4 GW, BE–FR) | per-branch override (TR5) | yes |
| TR4 | HVDC converter pair | 640 → 540 €/kW | **420–640 €/kW** | ACER UIC 2026: 0.21 M€/MW per converter | master CSV | yes |
| TR5 | per-branch project costs | centroid length × unit cost | ALEGrO ≈ 90 km, ≈ 0.5 bn€₂₀₁₅ [research summary]; Boucle du Hainaut, second BE–DE HVDC and Nautilus from Elia/TYNDP project data | project table | `data/walloon/transmission_cost_overrides.csv`, applied after every `set_transmission_costs` call (`prepare_network`, `add_brownfield`) | yes |
| TR6 | reversed-DC legs | charged the converter pair from 2030 | 0 | bug, §4.1.4 | fix in `set_transmission_costs` (task filed) | yes |
| TR7 | lengths, `s_max_pu` | centroid × 1.25; 0.7 | **unchanged** | they drive impedance, losses and the NTC gross-up; costs are corrected through TR5 instead | — | — |
| TR8 | system services | absent | **≈ 6.7 €/MWh of offtake** (2022: 547 M€ / 81 TWh; a crisis year) | replace with Elia's 2023–25 actuals | reporting block (endogenous reserves are future work) | no |
| TR9 | interconnection income | not reported | model: Belgian share (50 %) of cross-border congestion rent, 1.04 / 0.77 / 0.63 / 0.72 bn€ in 2025/30/40/50, vs Elia's actual 0.42 bn€ (2022) | the model probably overstates it (no flow-based coupling, coarse nodes); check against Elia's 2023–25 actuals before using it as an offset | reporting | no |
| TR10 | methane transmission (Fluxys), tariff view | SciGRID pipelines at replacement annuity | **Walloon share of gas offtake** (33 % in 2025 → 38 % in 2050, model) **× Fluxys regulated revenue**: ≈ 100–125 M€/yr on the pre-decision indicative 309–330 M€/yr [research summary; approved values confidential]. Existing pipelines set to 0 in this view | CREG / Fluxys | reporting block | no |
| TR11 | H₂ pipelines | EHB 2021: 382 / 163 €/MW/km (new / repurposed) | **EHB 2022**: ≈ 215 / 38 €/MW/km for large pipes; smaller size classes from EHB 2022 tables | EHB 2022 | master CSV | yes |
| TR12 | CO₂ pipelines | linear, 2 672 €/(t/h)/km | **scale-dependent**. Fit C ∝ Q<sup>0.6</sup> through the DEA point (12″, ≈ 300 t/h, 0.80 M€/km) and linearise per link at the capacity found in a first run (iterate once). BEWAL–DE at 1 845 t/h: 2.4 M€/km, i.e. 1 290 €/(t/h)/km (−52 %) | JRC network average 0.62–0.89 M€/km. The 0.6 exponent is an engineering rule of thumb, to be checked against the JRC size classes | per-link override (TR5 file) | yes |
| TR13 | discount rate / lifetime | 7.5 % / 40–50 y | 3.5 % (§6.2) | — | master CSV | yes |

**Validation checks.**

| id | check | target |
|---|---|---|
| TV1 | TR1 + model increments, Walloon tariff view | Elia allowed revenue × offtake share, per year |
| TV2 | model congestion rent (TR9) | Elia interconnection income, 2023–25 actuals |
| TV3 | cost of committed projects built through the NTC floors | project costs (TR5) |
| TV4 | 50/50 direct Walloon cost after TR6 | 88 / 105 / 137 / 129 M€ (§1.2) before TR2–TR5 |

### 6.6 Parameters without direct data, and how they are estimated

| parameter | why it is missing | provisional method | provisional value | replace with |
|---|---|---|---|---|
| PV share *s*<sub>PV</sub> of transition capex | CWaPE groups PV, EV and heat pumps under E1.1 | bracket 0–0.5. Central 0.25: only E1.4 and the ORES task force are PV-specific, while E1.1 explicitly mixes the three | 0.25 | the DSOs' split of E1.1 (§9, item 6) |
| DSO (MV + LV) coincident peak | not published | model LV peak after E6 | 3.1 GW (2025) | Synergrid / ORES peak data (§9, item 4) |
| DSO OPEX split, asset vs customer | not published | asset part = FOM (1.5–2 %) × replacement value | 85–190 / 100–200 M€ | DSO cost accounting |
| replacement value of the DSO grid | not published | 1.5–2.5 × net book value (3.77 bn€) = 5.6–9.4 bn€. Cross-check: its annuity at 3.5 %/40 y (262–440 M€) brackets the 390 M€ of capital charges | ≈ 7.5 bn€ | network length by voltage × unit costs (CWaPE 0967, Tableau 19) |
| local vs regional diversity | no Walloon data | embedded in *c*<sub>inc</sub> | *k*<sub>div</sub> = 1 | smart-meter data (ORES digital twin, CD-25d03-CWaPE-1056 §6.2.2) |
| sub-hourly peak | — | Elia 2024: 15-min vs hourly peak | +0.6 %, ignored | — |
| flexibility credit φ | no data | sensitivity | 1 / 0.5 | DSO flexibility programmes |
| Walloon share of Belgian offtake | Elia does not publish by region | model withdrawals; TIMES HV input ÷ Elia load | 23–26 % (2025) | SPW / Elia regional balance |
| Elia revenue breakdown 2024–27 | confidential in the decision | 2022 actual shares | — | Elia annual reports, CREG ex-post decisions |
| Fluxys allowed revenue | confidential | pre-decision indicative figures | 309–330 M€/yr | CREG / Fluxys |
| gas decommissioning cost per km | not found | seal and leave in place; per-connection cost only | 930–1 750 €/connection | ICEDD–CWaPE gas study; DSO data |

### 6.7 Implementation sequence

| step | content | effort | re-solve |
|---|---|---|---|
| 0 | fix the reversed-DC costing (TR6), with its unit test | S | yes, next run |
| 1 | reporting layer: a script (e.g. `scripts/walloon_scripts/network_cost_report.py`) reads the solved networks and a calibration table `data/walloon/network_cost_calibration.csv`, then writes `csvs/network_costs_calibrated.csv` split into L1–L4 per network. The table holds E1–E3, E11, GD1, GD4, TR1, TR8–TR10 with sources. The cabinet chart's *Distribution* and *Transport* segments are then drawn from this file instead of the ClimAct extraction | M | no |
| 2 | parameters and hooks: master CSV (E4/TR13, E5, TR2, TR4, TR11); config (E7, GD2); hooks (E6 industry split, E8 PV adder, TR5 overrides, optional E10 constraint) | M | one 6 h test, then one 1 h chain |
| 3 | validation V1–V5 and TV1–TV4, written into section 11 of the run's solve log | S | — |
| 4 | TIMES harmonisation (§7) | M–L | — |

Step 1 alone answers the stakeholder's comparison, since it changes the *level* and not
the decisions. Step 2 changes results, so it follows the usual run-review procedure.

### 6.8 Improving the formulation later

These go beyond calibration and belong with the multi-node work (§8):

* the existing grid as vintaged, non-extendable age cohorts, so that renewal becomes
  endogenous;
* a two-tier MV / LV representation with separate unit costs, and HV industry on its
  own bus;
* node-specific costs per DSO area;
* a reverse-flow hosting constraint instead of the PV adder;
* endogenous reserves;
* gas distribution as a bus per zone, with a fixed cost and a decommissioning decision;
* piecewise-linear pipeline costs for economies of scale.

---

## 7. Harmonisation with TIMES for bill reporting

TIMES will report the effect of the scenarios on the electricity and gas bills of
different users. PyPSA and TIMES must therefore agree on every bill component, or the
bills will not be reproducible from the scenarios they claim to describe.

### 7.1 The bill identity

For each user type *u*, energy carrier *e* and year *t*:

> **Bill**<sub>u,e</sub> = V<sub>u,e</sub> × ( p<sup>energy</sup><sub>u,e</sub> + t<sup>network</sup><sub>u,e</sub> + τ<sub>u,e</sub> + σ<sub>u,e</sub> ) + F<sub>u,e</sub>, plus VAT

where:

* V is the billed volume, net of self-consumption;
* p<sup>energy</sup> is the commodity price seen by that user's consumption profile;
* t<sup>network</sup> is the distribution and transmission tariff (volumetric and/or
  capacity);
* τ is taxes and regulatory levies (excise, federal contribution, regional PSO);
* σ is the support-scheme levies (green certificates, offshore and nuclear support,
  CRM);
* F is the fixed charge per connection.

Suggested user types:

* electricity:
  * LV residential, with and without a heat pump, with and without an EV
  * LV prosumer with PV
  * LV services
  * MV business
  * HV industry
* gas:
  * residential
  * services
  * industry on distribution
  * industry on transmission

**Division of labour.** PyPSA supplies the system side: prices, network revenue
requirements and support needs. TIMES supplies the demand side (volumes by user type,
connections, self-consumption) and the exogenous taxes, and reports the bills. The check
is that TIMES's own mark-ups reproduce what PyPSA's system implies.

### 7.2 Variables to include in the harmonisation analysis

**A. Volumes and structure.**

| id | variable | PyPSA | TIMES | check |
|---|---|---|---|---|
| A1 | electricity by sector and voltage level | loads on the LV / HV buses after E6 | `VAR_FIn` of `ELCLOW` / `ELCMED` / `ELCHIGG` by RSD / COM / IND / TRA / AGR | equal by construction; ±2 % |
| A2 | gas by sector and grid level | gas-bus withdrawals by carrier | `RSDGMX00`, `COMGMX00`, `INDGMX00`, `INDGAS00` | distribution / transmission split against CWaPE (17.4 TWh distributed in 2025) |
| A3 | self-consumed PV | not represented: rooftop PV simply feeds the LV bus | `ERNW_PV-RES_Homes` output to `RSDELC` vs `ELCLOW` | define billed volumes consistently |
| A4 | connections by user type | — | dwelling and heating-system stock | 1.95 M electricity EAN and 0.80 M gas meters today; gas disconnections drive GD4 and GD5 |
| A5 | peaks by user type (for capacity tariffs) | hourly load by component at the LV peak hour (table in §2.1) | `EQ_Peak` (`ELCForPeak`) | contribution to peak per user type |

**B. Energy component.**

B1 — wholesale electricity price. Use the **Belgian zonal price**: the load-weighted
average of the BEWAL / BEVLG / BEBRU *HV-bus* marginal prices. Do **not** use:

* the Walloon nodal price, which contains the import-cap dual (−18.5 €/MWh in 2030)
  and internal congestion;
* the LV-bus price, which contains the distribution capacity rent (~15 €/MWh) and
  would double-count the network tariff.

Compare it with TIMES's `EQ_CombalM` on `ELCHIG` / `ELCHIGG` per timeslice
(M€/PJ × 3.6 = €/MWh).

| €/MWh | 2025 | 2030 | 2050 |
|---|---:|---:|---:|
| PyPSA BE zonal time average | 169 | 109 | 91 |
| TIMES `ELCHIG`, unweighted mean of 120 timeslices | 104 | 69 | 62 |

**This gap is the first thing to resolve.** Weight TIMES by timeslice duration
(`G_YRFR`, to request), then compare price formation.

B2 — profile-weighted price per user type. PyPSA: hourly price × user profile (Synergrid
SLPs, or the model's heat-pump and EV profiles). In 2030 at BEWAL LV:

* residential/services 131 €/MWh
* inflexible EV 127 €/MWh
* industry 127 €/MWh

These LV prices must have the ~15 €/MWh capacity rent removed. TIMES: timeslice price ×
sector consumption per timeslice.

B3 — gas wholesale. PyPSA BEWAL gas bus: 37.7 / 37.6 / 32.2 / 26.9 €/MWh
(2025/30/40/50). TIMES `GASNAT` marginal: 33.2 / 30.8 / – / 22.2 €/MWh. Fuel prices come
from the shared master CSV and must match.

B4 — carbon prices.

* **ETS1.** The dual of PyPSA's EU `CO2Limit` is 77 / 95 / 119 / 467 €/t; compare with
  the TIMES ETS price.
* **ETS2** (buildings and road) is not in PyPSA. TIMES's rising oil and gas mark-ups
  suggest TIMES has it. Gas and oil bills must take it from a single harmonised
  assumption.
* The **national CO₂-limit duals** (BEWAL 379 €/t in 2025) are policy shadow prices, not
  bill components. The CO₂ duals stack, so read bus marginal prices rather than
  configured values.

B5 — supplier margin, imbalance and CRM cost. Exogenous, and the same in both models.

**C. Network component.**

C1 — electricity distribution revenue requirement:
R<sub>dist</sub>(t) = L1 + L3 (E1–E3) + L2 (E5, E8) + loss cost (E7 × p<sup>energy</sup>)
+ add-ons (E11). Allocate it to user types with the CWaPE 2025–29 tariff structure
(voltage level, and the fixed / capacity / volumetric shares).

C2 — electricity transmission revenue requirement:
R<sub>trans</sub>(t) = TR1 + L2 increments + system services (TR8) − interconnection
income (TR9). Allocate it with Elia's national tariffs per voltage level.

C3 — gas distribution revenue requirement: R<sub>gas,dist</sub>(t) = GD1 + GD4, per
pathway. The €/MWh trajectory (GD5) is the death-spiral indicator for gas users.

C4 — gas transmission: TR10.

C5 — the **reconciliation identity**. For each network and year,
Σ<sub>u</sub> t<sup>network</sup><sub>u</sub> × V<sub>u</sub>(TIMES) = R<sub>network</sub>(PyPSA-calibrated).
The TIMES mark-ups (`RSDELC00` 179.5 €/MWh, `COMELC00` 94.1, `INDELC00` 24.6, and the gas
equivalents) sit on top of the commodity price. They must therefore equal
t<sup>network</sup> + τ + σ for the corresponding user type, with the fixed charges F
converted to €/MWh. The
mark-ups are constant from 2025 to 2050, while R and V are not. So they should be
**recomputed from C1–C4 plus τ and σ and handed back to ICEDD as TIMES inputs**, then
the check repeated once.

**D. Support schemes.**

S1 — missing money from PyPSA: annualised cost minus market revenue per technology.
Belgian nuclear: 0.46 bn€/a in 2030 and 1.06 bn€/a in 2050. Utility PV: 0.11 bn€/a in
2030; rooftop PV: 0.05–0.06 bn€/a. These gaps are exactly where policy constraints bind:
capacity floors (`agg_p_nom_min`), CCL, the import cap, NTC floors. Their duals × capacity
give the same answer. They are funded by levies, σ.

S2 — TIMES support schemes: to be listed by ICEDD, if any.

**E. Financial and accounting conventions.**

| id | item | rule |
|---|---|---|
| FC-a | price base | TIMES MEUR21 vs PyPSA EUR2025: one HICP conversion, stated in every bill table |
| FC-b | nominal vs real | tariffs are nominal, the models are real; report bills in real terms with an explicit inflation assumption |
| FC-c | annualisation of network capex | regulated WACC (§6.2) in both models' reporting, not technology hurdle rates |
| FC-d | depreciation | regulatory lives for tariffs; technical lives for system cost |

**F. Time and space.**

F1 — TIMES has 120 electricity timeslices, PyPSA 8 760 h. Map PyPSA hours onto the
TIMES timeslices (definitions and durations to request) and compare price and load per
timeslice.

F2 — perimeter. Demands are the whole of Wallonia; the BEWAL node excludes western
Hainaut; prices should be zonal (Belgium).

### 7.3 Procedure

1. After each PyPSA run, a harmonisation script produces one table per scenario and year.
   It holds A1–F2 (all groups) with the TIMES values read from the same `.vd`, the difference, and a
   pass / fail against tolerances: ±2 % volumes, ±10 % prices, ±5 % revenue
   reconciliation. A possible name is `scripts/walloon_scripts/bill_harmonisation.py`,
   built on the `.vd` readers of `times_pypsa`.
2. PyPSA's outputs are turned into tariffs and levies per user type: R<sub>network</sub>
   (C1–C4), σ (S1) and p<sup>energy</sup> (B1–B2).
3. These are compared with TIMES's mark-ups and commodity prices.
4. The recomputed mark-ups are sent to ICEDD for the next TIMES run.
5. Plan one iteration. The mark-ups change TIMES's technology choice (§5.2), which feeds
   back into PyPSA's demands. A second pass is needed only if volumes then move by more
   than the tolerances.

Data needed from ICEDD for this: timeslice durations (`G_YRFR`), the content of the
mark-ups, the user-type definitions for bills, connection counts, self-consumption, and
the tax and VAT assumptions (§9).

---

## 8. Towards a multi-node Belgium

What changes in the next phase, and what can be prepared now:

| network | today (3 BE nodes) | multi-node target | preparation now |
|---|---|---|---|
| electricity transmission | 5 Walloon inter-node branches, centroid lengths, no internal grid | 380/220/150 kV explicit for Belgium, real lengths, 70/36 kV as a proxy layer | Elia grid data request; project cost table (T4) |
| electricity distribution | 1 LV bus, placeholder cost, starts at 0 | LV (± MV) bus per node, cost per DSO area, existing grid as a sunk block, hosting-capacity caps | CWaPE revenue per DSO (done here), peak per DSO area from Synergrid/ORES |
| gas distribution | per-boiler charge on new boilers | fixed block per zone plus decommissioning pathway | CWaPE gas revenues; ORES/RESA mains length and connection counts |
| gas / H₂ / CO₂ transmission | SciGRID_gas between regions; new-build H₂; endogenous CO₂ | Fluxys topology per node; H₂ retrofit option; CO₂ corridors per industrial site | Fluxys H₂ and CO₂ project data |
| cost allocation | three rules (§4.2) | sum over regional branches + 50/50 cross-border, plus the tariff view | adopt the two-number reporting now |

The regional perimeter also changes. The current BEWAL node leaves 2 191 km² of western
Hainaut in BEVLG, while the CWaPE revenues cover the whole Region. For distribution the
comparison above still holds, because BEWAL's electricity demand is the TIMES demand of
the whole Region. For transmission it does not: some Walloon branches are booked to
Flanders.

---

## 9. Open questions and data requests

**ICEDD (TIMES-WAL)**

1. What do the `Cost_Act` mark-ups on `RSDELC00`, `COMELC00`, `INDELC00` and the gas
   "Fuel Tech" processes contain: network tariffs, excise, levies, ETS2? What are their
   sources and base years?
2. Do `EVTRANS_*` carry any cost or capacity in the VEDA workbooks that does not show in
   the `.vd`?
3. Is the HV / MV / LV split of final demand usable as the PyPSA load split (D4, E6)?

**CWaPE / DSOs**

4. The 2029 peak and distributed energy per DSO, split MV/LV, to turn the revenue into
   €/kW and €/MWh on the right denominator.
5. The ORES revision request currently under review: amount, investment programme and
   horizon. No public decision was found as of September 2026.
6. The split of the 2026–30 capex (662 M€/yr) between renewal, connections, smart
   meters and capacity reinforcement for PV / EV / heat pumps. Only the last is what
   the model's increment should be compared with.
7. Gas: mains length and connections per zone or municipality, to build a
   decommissioning pathway (G2).

**Elia / CREG**

8. The 2024–27 budget breakdown of the allowed revenue, which is confidential in the
   published decision. It is needed to split grid, system services and levies, and to
   isolate federal from local transmission. Wallonia's share of offtake is also
   needed. Together these calibrate T3.

**ClimAct**

9. The origin of the `nyears = 1/3` factor and of the CZ cost file in the gas slice
   (§1.1), and whether the capacity-pooled transmission rule can be replaced by the 50/50
   one (§4.2).

**ICEDD: calibration and bills (§6–§7)**

10. Gas by grid level: which share of `INDGMX00` / `INDGAS00` is on the distribution grid
    and which is on the Fluxys grid. Needed for GD5 and A2.
11. For the bill harmonisation:
    * the timeslice durations (`G_YRFR`), to weight the `EQ_CombalM` prices (B1);
    * the user types TIMES will report bills for;
    * PV self-consumption by user type (A3);
    * the connection counts and gas disconnections (A4, GD4);
    * the ETS2 price and the excise, levy and VAT assumptions (B4, τ);
    * any support schemes in TIMES (S2).

---

## Appendix — reproduction

CWaPE figures: Tableau 4 of CD-25d03-CWaPE-1056 (ORES, revision of 14/03/2025) and
Tableau 8 of the RESA (CD-25b20-CWaPE-1043), REW (-1038), AIESH (-1037) and AIEG (-1036)
decisions, *Budget 2029* column.

<details>
<summary>Model-side decomposition (pypsa-eur env, ~1 min)</summary>

```python
import pypsa
ann = lambda n, r: r / (1 - (1 + r) ** -n)
CL_NEW = (ann(40, .07) + .02) * 500e3 / 3   # ClimAct gas slice, boilers built >= 2025
CL_OLD = 500e3 * .02 / 3                   # ClimAct gas slice, older boilers
for y in [2025, 2030, 2040, 2050]:
    n = pypsa.Network(f"results/walloon/scen_central/networks/base_s_adm___{y}.nc")
    L = n.links
    d = L[(L.carrier == "electricity distribution grid") & (L.bus0 == "BEWAL")]
    g = L[((L.carrier.str.contains("gas boiler") & ~L.carrier.str.contains("urban central"))
           | L.carrier.str.contains("micro gas")) & L.index.str.startswith("BEWAL")]
    new = g.build_year >= 2025
    print(y,
          "dist GW", d.p_nom_opt.sum() / 1e3,
          "dist M€", (d.p_nom_opt * d.capital_cost).sum() / 1e6,
          "gas model M€", g[new].p_nom_opt.sum() * d.capital_cost.iloc[0] / 1e6,
          "gas ClimAct M€", (g[new].p_nom_opt.sum() * CL_NEW + g[~new].p_nom_opt.sum() * CL_OLD) / 1e6)
    rev = L[(L.carrier == "DC") & L.index.str.endswith("-reversed")]
    print("   reversed-DC capex M€", (rev.p_nom_opt * rev.capital_cost).sum() / 1e6)
```

</details>

TIMES figures: `Cost_Act` / `VAR_Act` and `VAR_FIn` / `VAR_FOut` summed per process and
period from `scen_central_v01_260911_1109.vd` (PJ ÷ 3.6 = TWh).

Calibration and harmonisation inputs (§6–§7):

* **Electricity DSO 2025 budgets.** *Budget 2025* column of the same five decisions.
  Aggregated as in §2.2: network core = controllable OPEX (excluding PSO) + depreciation
  + both fair margins + corporate tax.
* **DSO capex by driver.** [CWaPE CD-25k27-CWaPE-0967](https://www.cwape.be/sites/default/files/cwape-documents/CD-25k27-CWaPE-0967-Avis%20plans%20d'adaptation%20GRD%20%C3%A9lectricit%C3%A9%202026-2030.pdf),
  Tableau 15 by motivation code and Tableau 14 by DSO. EAN count and energy withdrawn
  from §2.3.4 of the same opinion.
* **Gas DSO budgets and RAB.** CD-24c28-CWaPE-0890 (ORES gas, Tableau 1) and -0891
  (RESA gas).
* **Gas network statistics and capex.** [CD-26g30-CWaPE-0981](https://www.cwape.be/documents-recents/grd-de-gaz-avis-concernant-les-plans-dinvestissement-2027-2031),
  Tableau 2 and §4.1.
* **Elia revenue.** [CREG (B)658E/85](https://www.creg.be/sites/default/files/assets/Publications/Decisions/B658E85FR.pdf),
  Tableau 1bis. Walloon 30–70 kV plan:
  [CD-26g30-CWaPE-1283](https://www.cwape.be/sites/default/files/cwape-documents/CD-26g30-CWaPE-1283-D%C3%A9cision%20plan%20adaptation%20Elia%202026-2036_ANONYMIS%C3%89E%20pour%20site.pdf).
* **Belgian load, 15-min.** Elia open data `ods001`, 2024 (81.0 TWh; max 15-min
  13 282 MW vs max hourly 13 206 MW).
* **TIMES.** Voltage split and commodity marginals from `VAR_FIn` on `ELCHIGG` / `ELCMED`
  / `ELCLOW` per sector-prefix, and `EQ_CombalM` (M€/PJ).
* **PyPSA.**
  * prices: `buses_t.marginal_price` at the HV, LV and gas buses;
  * congestion rents: price difference × flow on the Belgian branches (50 % of
    cross-border rent booked to Belgium);
  * funding gaps: generation × nodal price minus capital and variable cost, per
    carrier, for Belgian buses.
