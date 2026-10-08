# Biogas in PyPSA-WAL

How biogas enters the model, where each number comes from, what the "sustainable" and
"unsustainable" labels mean, and whether they fit Belgium. Written 2026-10-01 from the
1 Oct central (`results/walloon/scen_central`) and the code on `development_plan`.
Batch-log context: [`logs/2026-09-30_cabinet_batch_20260930_2010_1h.md`](logs/2026-09-30_cabinet_batch_20260930_2010_1h.md)
§11.8 and R1.

> **Update — 6 Oct 2026: the Walloon cap now holds in every horizon (§3.2).** ICEDD's TIMES
> bound on new digesters, which TIMES had read for 2040 and 2050 only, applies from 2025;
> the PyPSA row is that bound **plus** TIMES's existing biogas and landfill gas, and it caps
> the sustainable and the forced generator **together**. 1.02 / 2.15 / 3.36 / 4.67 / 5.80 /
> 6.93 TWh in 2025 … 2050. Sections 3.1, 4.4, 6 and 7 are amended accordingly.

---

## 1. Summary

* **PyPSA-Eur has two biogas generators per node, and they deliver the same gas.** They sit
  on the same bus, cost the same, go through the same upgrader and carry the same carbon
  treatment. They differ only in where the quantity comes from and in whether the model
  must use it (§2).
* **"Unsustainable biogas" is today's production, phased out by 2040.**
  * It is a **forced** quantity (`e_sum_min = e_sum_max`).
  * It is Eurostat's 2019 Belgian biogas production, × 1 in 2025, × 0.66 in 2030, 0 from 2040.
  * It is split between the three Belgian nodes by their share of the *total* biomass
    potential (§4).
* **"Sustainable biogas" is a future resource, phased in by 2040.** Upstream it is the JRC
  ENSPRESO potential of manure and sewage sludge only. In Wallonia it is overwritten by the
  Walloon cap (§3).
* **The Walloon cap bounds total Walloon biogas in every horizon** (6 Oct 2026, §3.2):
  * ICEDD's TIMES bound on new digesters (`BWBIOGAZ100`), the ICEDD–Valbiom figure of 2040 /
    2050 (§3.1) extended to 2025–2035, plus TIMES's existing biogas and landfill gas;
  * 1.02 / 2.15 / 3.36 / 4.67 / 6.93 TWh in 2025 / 30 / 35 / 40 / 50;
  * applied to the sustainable and the forced "unsustainable" generator together.
  * Until 6 Oct the 2025 / 2030 cap was the Valbiom 8.3 TWh, read as loose. It was not: with
    the cost fix the 4 Oct central burnt all of it in 2030, against TIMES's 2.1 TWh.
* **The label does not describe Belgian feedstock** (§5). Belgian biogas comes mostly from
  agro-food residues, manure and crop residues. Energy crops are a minor share: in Wallonia,
  10.6 % of the tonnage in 2024 and 1 % of the "current mix" in the 2021 Gas.be study.
  "Unsustainable" is a phase-out convention, not a statement about these digesters.
* **The forced Walloon figure is too high and the Flemish one too low** (§6):
  * PyPSA gives Wallonia 1.45 TWh and Flanders 1.13 TWh in 2025;
  * the regional sources say about 0.9 TWh for Wallonia and about 2 TWh for Flanders;
  * TIMES has 0.99 TWh for Wallonia.
* **Six items are listed in §7.** The cost double count (item 5) moved results. It is fixed
  in the inputs from 1 Oct 2026 (§8.1) and needs a re-solve. The cap question (item 6) is
  settled.
* **TIMES prices feedstock and digester separately** (§8.2). Its Walloon feedstock costs
  ≈ 25–43 €/MWh of biogas (TIMES units ≈ EUR2021) and rises with energy crops.

---

## 2. How biogas is represented

```
 BEWAL biogas                  (generator, carrier "biogas")               optional, ≤ e_sum_max
 BEWAL biogas unsustainable    (generator, carrier "unsustainable biogas") forced, = e_sum_min = e_sum_max
            │  both 78.81 €/MWh (technology-data `biogas` fuel)
            ▼
       BEWAL biogas  (bus) ──── BEWAL biogas to gas (link: digester + upgrading capex, VOM)
                                     ├─► BEWAL gas
                                     └─► co2 atmosphere: −0.198 t/MWh (biogenic credit)
```

* Both generators are added in `add_biomass`, [`scripts/prepare_sector_network.py:4815`](../scripts/prepare_sector_network.py).
* The biogas bus has one outlet, the `biogas to gas` upgrader. It carries
  `biogas upgrading` capex and, in this build, the digester investment too (§7, item 5).
* **There is no carbon distinction between the two.** Both receive the same biogenic credit
  on upgrading. "Unsustainable" carries no CO₂ penalty and no extra cost.

---

## 3. The "sustainable" generator

**Upstream definition.** The JRC ENSPRESO potential, scenario `ENS_Med`, classes
`biomass.classes.biogas`:
* `Manure solid, liquid`;
* `Sludge`.

Agro-food industry residues, bio-waste and energy crops are **not** in that list.
Municipal waste is a separate class (`municipal solid waste`).

It is scaled by `share_sustainable_potential_available`:

| | 2025 | 2030 | 2035 | 2040+ |
|---|---:|---:|---:|---:|
| share of the JRC potential available | 0 | 0.33 | 0.66 | 1 |

**Walloon override.** `update_BEWAL_potentials`
([`scripts/walloon_scripts/BEWAL_potentials.py:405`](../scripts/walloon_scripts/BEWAL_potentials.py))
sets the BEWAL sustainable generator from `data/walloon/custom_potentials.csv` (GWh/an):

| | 2025 | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|---:|---:|
| Walloon cap, since 6 Oct 2026 (§3.2) | **1 019** | **2 145** | **3 363** | **4 667** | 5 800 | **6 933** |
| *until 6 Oct 2026* | *8 300* | *8 300* | *6 150* | *4 000* | *5 450* | *6 900* |
| source (since 6 Oct) | ICEDD | ICEDD | ICEDD | ICEDD–Valbiom | interpolated | ICEDD–Valbiom |

The cap is on the *total*, so `update_BEWAL_potentials` gives the sustainable generator what
the forced one leaves (§4.4).

### 3.1 What the 2040 / 2050 figures are (decision of 1 Oct 2026; amended 6 Oct, §3.2)

* **A cap, not a result.** 4.0 TWh in 2040 and 6.9 TWh in 2050 come out of a discussion
  between ICEDD and Valbiom, and **both models apply them**: TIMES and PyPSA.
  * The batch log (§11.8) read them as TIMES's own output. That reading is withdrawn.
  * TIMES produces exactly 4.000 TWh in 2040 and 6.93 TWh in 2050 in the 30 Sep central
    export because the cap **binds in TIMES**.
  * The 7.67 / 8.07 TWh quoted in earlier notes came from an older `.vd`. Most likely it
    predates the cap in TIMES; this was not checked.
* **Scope: total Walloon biogas.** The cap is a maximum on sustainable and unsustainable
  biogas together.
  * In PyPSA it sits on the sustainable generator only (§4.4).
  * That is equivalent from 2040, where the unsustainable generator is 0.
* **2025 / 2030 keep the Valbiom 8.3 TWh as a loose ceiling.**
  * Production in those years is roughly known: about 0.9 TWh observed, TIMES 0.99 / 2.18
    TWh (§6).
  * It will not approach 8.3 TWh, so the non-monotonic series (8.3 → 4.0 → 6.9) does not
    constrain anything before 2040.
* **Recorded in** `config/input_parameters_for_models.csv` rows 280–283 and
  `data/walloon/custom_potentials.csv` rows `BEWAL,biogas`.

### 3.2 Every horizon, and the existing biogas on top (decision of 6 Oct 2026)

**ICEDD's message** (A. Lempereur, 5 Oct 2026): her bound on the new-digester process
`BWBIOGAZ100` (`~TFM_INS`, `BNDACT UP`, region RW, PJ) had been read for 2040 and 2050 only.
She aligns the earlier years on TIMES's results and adds 2035:

| PJ | 2022 | 2025 | 2030 | 2035 | 2040 | 2050 |
|---|---:|---:|---:|---:|---:|---:|
| `BNDACT UP BWBIOGAZ100` | 0 | 1.00 | **5.15** | 9.62 | 14.40 | 22.64 |

* Interpolation option 5 (interpolate, extrapolate forward), so 2045 = 18.52 PJ.
* 2030 sits a little above a straight line, consistent with the +1.1 PJ the energy balances
  show between 2021 and 2024.
* **The bound excludes the base-year production**, "environ 2.7 PJ en plus".

**The PyPSA row is the bound plus TIMES's existing production.** The existing part is read
from the 2 Oct central (`scen_central_v01_261002_0210.vd`, `VAR_Act`, RW):

| PJ | 2022 | 2025 | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `MINBIOGAS` (existing digesters) | 2.232 | 2.232 | 2.232 | 2.232 | 2.232 | 2.232 | 2.232 |
| `MINCETGAS` (landfill gas, declining) | 0.492 | 0.435 | 0.341 | 0.256 | 0.170 | 0.128 | 0.085 |
| **PyPSA cap** = bound + existing, PJ | | 3.668 | 7.723 | 12.108 | 16.802 | 20.880 | 24.957 |
| **PyPSA cap, GWh** | | **1 019** | **2 145** | **3 363** | **4 667** | 5 800 | **6 933** |
| TIMES total produced, 2 Oct central, GWh | 757 | 987 | 2 132 | 3 321 | 4 667 | 5 800 | 6 933 |

* The base-year 2.72 PJ is Annick's 2.7. Taking TIMES's own declining landfill gas instead
  of a flat 2.7 PJ makes the cap equal TIMES's total exactly where the bound binds (2040–2050)
  and costs 0.01–0.11 TWh against the flat figure.
* **2040 moves from 4.0 to 4.67 TWh.** The 1 Oct figure was the new-digester bound alone,
  0.67 TWh below TIMES's total (§8.2). 2050 moves from 6.90 to 6.93 TWh.
* **Applied to the total.** The forced generator counts against the cap; where it alone
  exceeds it (2025: 1.45 against 1.02 TWh) it is clipped (§4.4).
* Master CSV `potential:BEWAL:biogas:p_nom`, anchors 2025 / 30 / 35 / 40 / 50, `interp`.
  Tests: `test/test_bewal_biogas_cap.py`.

**Neighbours keep the JRC definition.** BEVLG, for instance, has 2.36 TWh in 2030 and
7.11 TWh in 2040. "Sustainable biogas" therefore means different things in Wallonia and
next door.

---

## 4. The "unsustainable" generator

### 4.1 The formula

`add_unsustainable_potentials` and `_calc_unsustainable_potential`,
[`scripts/build_biomass_potentials.py:21`](../scripts/build_biomass_potentials.py) and `:248`:

```
unsustainable biogas[node] = Eurostat PPRD R5300 [country, year]
                           × (JRC total potential of node, all classes / JRC total potential of country)
                           × share_unsustainable_use_retained[horizon]
```

* **Volume.** Eurostat primary production (`nrg_bal = PPRD`), product `R5300 Biogases`. This
  covers landfill gas, sewage-sludge gas and other digesters.
* **Year.** `max(min(latest_year, horizon), 1990)`. `latest_year` is 2019 because GB is in
  the country list (2021 otherwise), so **2019 is used for every horizon**. Belgium 2019:
  **2.711 TWh** (`resources/eurostat_energy_balances.csv`; 2.85 in 2021, 3.03 in 2023).
* **Regional key.** The node's share of the country's total JRC potential across *all*
  biomass classes, i.e. mostly forestry and agricultural residues. It has nothing to do with
  where biogas is produced.
* **Phase-out.** `share_unsustainable_use_retained` = 1 / 0.66 / 0.33 / 0 for
  2025 / 2030 / 2035 / 2040+.
* **The docstring and the code disagree.** The docstring says "the difference between the
  data of JRC and Eurostat is assumed to be unsustainable". The code takes the **whole**
  Eurostat production, with no subtraction.

### 4.2 The numbers in the 1 Oct central

TWh, all used, since the generator is forced:

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| BEWAL | **1.452** (53.5 %) | **0.927** (51.8 %) | 0 | 0 |
| BEVLG | 1.134 | 0.773 | 0 | 0 |
| BEBRU | 0.126 | 0.089 | 0 | 0 |
| Belgium | 2.712 | 1.789 | 0 | 0 |

### 4.3 It also forces an upgrader

The BEWAL `biogas to gas` capacity built in 2025 is **166 MW**, and 1.452 TWh / 8 760 h =
165.7 MW. The forced volume therefore makes the 2025 solve build exactly the upgrader it
needs, run at 100 % load. That plant is the "existing 166 MW" that carries into 2030–2050
(batch log §11.8).

### 4.4 The Walloon override and the forced volume

> **Since 6 Oct 2026** the biogas cap bounds the two generators together.
> `update_BEWAL_potentials` gives the sustainable generator `cap − forced`, and clips the
> forced generator (`p_nom`, `e_sum_min`, `e_sum_max`) to the cap where it exceeds it. In
> 2025 the forced 1.45 TWh becomes 1.02 TWh, TIMES's level. In 2030 the split is 0.93 forced
> + up to 1.22 optional. The bullets below describe the behaviour until then.

* For biogas, `update_BEWAL_potentials` rewrote only the sustainable generator.
* The F8 fix of 5 Sep 2026, which books "potential − upstream" on the unsustainable
  generator, applies to `solid biomass` only.
* So in 2025–2030 the Walloon biogas bus can take the Valbiom 8.3 TWh **plus** the forced
  1.45 / 0.93 TWh.
* This is harmless. Under the 1 Oct decision (§3.1), the 2025 / 2030 ceiling is loose by
  design, and total use (forced plus optional) stays far below it.
* From 2040 the forced part is 0, so the cap on the sustainable generator is the cap on
  the total, as agreed.

---

## 5. Is today's Belgian biogas "unsustainable", i.e. from crops? (web check, 1 Oct 2026)

**No.** Energy crops are a minority input in both regions.

| source | scope | what it says |
|---|---|---|
| Valbiom *Panorama de la biométhanisation en Wallonie* 2024 edition, via Renouvelle | Wallonia, 2024, 84 units, 1 149 760 t of inputs | **by tonnage**: agro-food waste 54.5 %, livestock effluents 21.2 %, energy crops **10.6 %**, other ≈ 14 % |
| Gas.be *Deep Dive Study for Biomethane in Belgium*, WP4 (Climact/Valbiom), 2021 | "Case 1, current situation", by region | Wallonia: agricultural residues 41 % (agricultural + industrial residues 64 %), manure 35 %, dedicated crops **1 %**. Flanders: manure 49 %, residues 46 %, dedicated crops **5 %** |
| same study | the future "realistic" potential (Case 2) | dedicated crops rise to 43 % (Wallonia) and 19 % (Flanders). Maize silage stays on existing surfaces; the growth is in CIVE (intermediate crops) and extra grassland |
| IEA Bioenergy, *Country Report Belgium* 2024 | Belgium | biogas about 10–11 PJ (≈ 2.8–3.0 TWh), stable since 2015, mostly in CHP; biomethane from "municipal and agricultural residues (food, animal, park and garden waste)" |

**Reading:**
* **By mass, crops are about a tenth of Walloon inputs.** By energy the share is higher,
  because maize silage yields several times more methane per tonne than slurry, but it
  stays a minority. The Valbiom panorama gives tonnage, not energy.
* **Most of today's Walloon input is agro-food residue.** It is neither in the JRC
  "sustainable biogas" classes (manure, sludge) nor in what PyPSA calls unsustainable. In
  upstream PyPSA-Eur it simply disappears after 2040.
* **The convention suits Germany better than Belgium.** Dedicated crops are still widely
  used in Germany and the UK (Sia Partners, *European Biomethane Benchmark* 2023).
* **Rule of thumb:** read "unsustainable biogas" as **"today's biogas, kept for calibration
  and phased out on a fixed calendar"**, not as crop biogas.

---

## 6. Against observation and TIMES

Walloon biogas, TWh of raw biogas:

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| observed, Valbiom 2024 (≈ 279 GWh_e / 0.40 + 168 GWh injected; see note) | ≈ 0.9 | | | |
| TIMES, 30 Sep central (methanisation + landfill) | 0.99 | 2.18 | 4.67 | 6.93 |
| PyPSA, forced "unsustainable" | **1.45** | 0.93 | 0 | 0 |
| PyPSA, optional "sustainable", used | 0 | 0 | **0** | 6.90 (on its cap) |
| PyPSA, total used | 1.45 | 0.93 | **0** | 6.90 |
| **Walloon cap on the total** (§3.2, since 6 Oct; was 8.3 / 8.3 / 4.0 / 6.9) | **1.02** | **2.15** | **4.67** | **6.93** |

*Note:* the observed row is an estimate. It converts Valbiom's 279 GWh of electricity at a
40 % CHP electrical efficiency (the ratio the Gas.be study uses for Flanders: 2 TWh of biogas
→ 0.8 TWh_e) and adds the 168 GWh of injected biomethane. It omits flared gas, and landfill
or sewage gas outside the Valbiom panorama.

Belgium, 2019–2023: Eurostat 2.71–3.03 TWh, IEA ≈ 2.8–3.0 TWh. Of this, about **2 TWh is in
Flanders** (the biogas input of existing Flemish CHPs, Gas.be 2021). The population/biomass
key puts **1.45 TWh in Wallonia and 1.13 TWh in Flanders**, about 0.5 TWh too much and
0.9 TWh too little respectively.

**Trajectory:**
* TIMES grows Walloon biogas steadily: 1.0 → 2.2 → 4.7 → 6.9 TWh. In 2040 and 2050 it sits on the common cap: methanisation alone is 4.000 TWh in 2040, and the total is 6.93 TWh in 2050.
* PyPSA burns the forced amount, then **nothing in 2040**, then its full cap in 2050.
* The 2040 zero is economic. At a 139 €/t CO₂ price a MWh of biogas is worth 59.8 €/MWh and
  costs at least 84.4 (batch log §11.8).
* With the cost double count of §7 item 5 removed (done 1 Oct, §8.1), a new 2040 chain costs
  about 60 €/MWh, i.e. break-even. PyPSA should then sit near the 4.0 TWh cap that TIMES reaches.
  This is not re-solved yet.

---

## 7. Defects and open items

| # | defect | effect today | fix |
|---|---|---|---|
| 1 | Forced volume split by **total biomass potential**, not by biogas production | Wallonia +0.5 TWh, Flanders −0.9 TWh in 2025 (§6) | per-node override from regional data: TIMES 0.99 / 2.18 TWh, or Valbiom observed ≈ 0.9 TWh |
| 2 | Eurostat year frozen at **2019** for every horizon | −10 % against 2023 for Belgium | minor; follows from 1 once overridden |
| 3 | The label implies crops; Belgian inputs are mostly residues (§5) | reading only: "unsustainable" must not be reported as crop biogas | document; report it as "existing production" |
| 4 | ~~Valbiom cap **plus** forced volume in 2025–2030 (§4.4)~~ **Fixed 6 Oct 2026** | the 8.3 TWh "loose" ceiling was used in full in 2030 once biogas was cheap (4 Oct central), forced volume on top | cap on the sum of both generators, forced volume clipped to the cap (§3.2, §4.4) |
| 5 | ~~**Cost double count**: generator at the all-in 78.81 €/MWh `biogas` fuel, and digester capex again on `biogas to gas`~~ **Fixed 1 Oct 2026** (§8.1) | biogas uneconomic until 2050; Walloon gas mix 2040 (R1). Every run solved before the fix carries it | `cost:biogas:fuel` = feedstock-only `biogas manure` fuel (25.16–25.33 €/MWh). The Valbiom digester and upgrading capex stay on the link. **Not yet solved:** a 6 h test, then the next central |
| 6 | ~~2040 / 2050 caps read as TIMES output~~ **Settled 1 Oct 2026:** an ICEDD–Valbiom cap on total biogas, common to TIMES and PyPSA (§3.1). **Extended to every horizon on 6 Oct, with the existing biogas added (§3.2)** | 2040 cap not reached in PyPSA (nothing used, item 5); the 2050 cap binds at a 125 €/MWh rent, as it binds in TIMES | none: keep as is |

Item 5 was the one that changed published numbers. It is fixed in the inputs from 1 Oct
2026; every run solved before that date carries it. Item 1 matters for the 2025–2030
Walloon gas balance and for any biogas figure reported per region.

---

## 8. Biogas costs: the double count, its fix, and what TIMES assumes

### 8.1 The double count (checked and fixed 1 Oct 2026)

**The evidence that it is a mistake:**

1. **Where the 78.81 €/MWh comes from.** technology-data's `biogas, fuel` row is 59
   EUR2015/MWh, "JRC and Zappa, from old pypsa cost assumptions" (`inputs/costs_PyPSA.csv`).
   * It is a price of biogas as a product.
   * Its sibling in the same old file, `solid biomass, fuel` (25.2), is a raw-fuel price.
     Biogas has no raw form, so its "fuel" price must include the digestion.
2. **PyPSA-Eur's own history** (in this repo's git log):
   * 2020–2023 (`651a7ff6`, `bea8194b`): `biogas to gas` carried only the
     `biogas upgrading` capex. The 59 €/MWh was then the whole production cost.
   * PR #615, Jan 2024 (`f81886e4`, "biogas upgrading CC"): the link gained
     `costs.at["biogas", "fixed"]`, i.e. the DEA sheet 81 *biogas plant* (the digester).
     The fuel price was not changed. From then on the digester was paid twice.
   * technology-data already has a feedstock-only row for this structure: `biogas manure`,
     JRC ENSPRESO MINBIOGAS1.
3. **The level is out of range.** Full chain at 90 % load in 2030:

   | €/MWh of biomethane | feedstock | digester | upgrading | total |
   |---|---:|---:|---:|---:|
   | PyPSA before the fix | 78.8 | 28.6 | 12.8 | **120** |
   | PyPSA after the fix | 25.2 | 28.6 | 12.8 | **67** |
   | BIP Europe 2023, real plants ≥ 3 MW | | | | **54–91** |
   | IEA (2020), Europe average | | | | ≈ 50 (USD 16/MBtu) |
   | TIMES, 30 Sep central, marginal (manure) route (§8.2) | 29.9 | 14.1 + 4.1 VOM + 2.5 heat | 10.2 | **61** TIMES units ≈ **74** EUR2025 |

4. **TIMES prices feedstock and digester separately** (§8.2). Its 2030 marginal biogas price
   equals the sum of those parts.

**The fix**, in the master CSV (`cost:biogas:fuel`, 4 rows, origin "Revue de littérature",
`interp`), written to `data/walloon/custom_costs.csv`:

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| `biogas` fuel, EUR2025/MWh_th, before | 78.81 | 78.81 | 78.81 | 78.81 |
| after (= technology-data `biogas manure`) | 25.16 | 25.23 | 25.24 | 25.33 |
| digester capital cost, €/MW/a (unchanged) | 259 222 | 225 523 | 217 746 | 204 785 |

* **Verified** with `prepare_costs` on the four horizons. `build_common_parameters.py --check`
  passes, and `custom_costs.csv` is 72 / 72 managed. `test_cost_learning.py`,
  `test_five_year_overlay.py` and `test_common_parameters_agg.py` pass.
* **It applies to every node** and to the forced `unsustainable biogas` generator. The
  forced volume does not move; only its constant cost in the objective falls.
* **Not solved yet.** Every run up to and including the 1 Oct batch carries the double count.

### 8.2 What TIMES assumes (30 Sep central, `scen_central_v01_260929_3009.vd`)

`input_parameters_for_models.csv`, the convergence table, has **no TIMES biogas cost**.
It holds only the Valbiom digester and upgrading capex, with an empty TIMES column. The
`.vd` holds the solved chain. It is a solution dump, so these numbers are what TIMES
*used*, read back from costs and flows, not its input sheets.

```
MINBIOEFF / IMPBIOEFF (effluents)  ─┐
MINBIOCUL (crops)                  ─┤                    ┌─► BIOGAS ── BWSUPGZH100 (upgrading) ──► BIOGZH
MINBIOSLUH, MINBIOBOU (sludges)    ─┼─► BWBIOGAZ100 ─────┤
SUPHET (heat, 4.7 % of output)     ─┘   (digester)       │
MINBIOGAS (existing, 0.62 TWh, ~free) ───────────────────┤
MINCETGAS (landfill gas, free)    ───────────────────────┘
```

**Units.** TIMES costs are in M€ and energy in PJ, so M€/PJ = €/GJ.
* TIMES's currency for these rows is not in the `.vd`.
* Its gas import cost reproduces CLIMA.A's **EUR2021** gas prices to the decimal: 30.345 /
  26.01 €/MWh in 2030 / 2040. The figures below are therefore read as ≈ EUR2021 (×1.222 →
  EUR2025). **To confirm with ICEDD.**
* The feedstock commodities are not in energy units. The digester turns one unit of
  effluents into 1.026 PJ of biogas and one unit of crops into 3.31 PJ. That fits Mt of
  fresh matter (≈ 28 and 92 m³ CH₄/t), which would make the feedstock costs €/t.

**Feedstock unit costs** (flow cost ÷ flow) and their cost per MWh of biogas:

| route | cost per feedstock unit | biogas per unit (PJ) | €/MWh of biogas (TIMES units) |
|---|---:|---:|---:|
| domestic effluents `MINBIOEFF` | 8.52 | 1.026 | **29.9** |
| imported effluents `IMPBIOEFF` | 0.90 → 1.33 | 1.026 | 3.2 → 4.7 |
| crops `MINBIOCUL` (from 2040) | 48.3 | 3.31 | **52.5** |
| sludge `MINBIOSLUH` (from 2035) | 11.11 | ≈ 1.02 | 39.3 |
| `MINBIOBOU` (from 2035) | 15.47 | ≈ 1.02 | 54.7 |
| existing biogas `MINBIOGAS`, landfill `MINCETGAS` | ≈ 0 | — | ≈ 0 |

**The chain, per MWh of new biogas** (TIMES units):

| | 2025 | 2030 | 2035 | 2040 | 2050 |
|---|---:|---:|---:|---:|---:|
| feedstock, mix average | 3.2 | 25.4 | 30.2 | 37.9 | 43.2 |
| digester capex (1 766 /kW lump sum, 110.9 /kW/a annuity, 90 % load, no FOM) | 14.1 | 14.1 | 14.1 | 14.1 | 14.1 |
| digester VOM | 4.1 | 4.1 | 4.1 | 4.1 | 4.1 |
| digester heat (4.7 % × `SUPHET` price) | 2.1 | 2.5 | 2.8 | 2.8 | 3.5 |
| **raw biogas** | 23.5 | 46.1 | 51.2 | 58.9 | 64.9 |
| upgrading (254 /kW lump sum; VOM 8.5) | 10.2 | 10.2 | 10.2 | 10.2 | 10.2 |
| **biomethane** | 33.7 | 56.3 | 61.4 | 69.1 | 75.1 |
| ≈ EUR2025 (×1.222) | 41 | 69 | 75 | 84 | 92 |

**Prices** (`EQ_CombalM`, €/MWh, TIMES units):

| | 2025 | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|---:|---:|
| `BIOGAS` | 40.0 | **50.5** | 70.1 | **192.5** | 160.0 | 120.7 |
| `BIOGZH` (biomethane) | 50.2 | 60.7 | 80.3 | 202.7 | 170.2 | 130.9 |

* **2030 validates the decomposition.** The domestic-effluent route costs
  29.9 + 14.1 + 4.1 + 2.5 = **50.6 €/MWh**, and the marginal `BIOGAS` price is **50.5**.
* **2040–2050 carry a scarcity rent.** The methanisation bound binds: `BWBIOGAZ100` reduced
  cost is −33.0 / −24.0 / −12.9 €/GJ in 2040 / 2045 / 2050.

**Where the cap sits in TIMES.** There is no user constraint on biogas. The bound is on
the activity of the new digester, `BWBIOGAZ100`:
* **2040:** 14.400 PJ = **4.000 TWh**.
* **2045:** 5.144 TWh.
* **2050:** 6.289 TWh.
* 2045 is exactly midway between 2040 and 2050.
* Existing biogas (0.62 TWh) and landfill gas come **on top**. Total TIMES biogas is
  therefore 4.67 TWh in 2040 and 6.93 TWh in 2050.

In PyPSA, the same 4.0 / 6.9 TWh caps *all* Walloon biogas, because the forced part is 0
from 2040. **So in 2040 PyPSA's cap is 0.67 TWh tighter than TIMES's total.** 2050 matches
(6.9 against 6.93). This is worth a word with ICEDD: §3.1 records the cap as a maximum on
the total. *(Answered 5 Oct 2026: the bound excludes the base-year production; the PyPSA cap
is now bound + existing, 4.67 / 6.93 TWh, §3.2.)*

### 8.3 PyPSA against TIMES after the fix

| €/MWh of biomethane, 90 % load | 2030 | 2040 | 2050 |
|---|---:|---:|---:|
| PyPSA after the fix (EUR2025) | 67 | 64 | 61 |
| TIMES, mix average (≈ EUR2025) | 69 | 84 | 92 |
| TIMES, manure route (≈ EUR2025) | 74 | 74 | 75 |

* **The two models now agree in 2030.** From 2040 TIMES is dearer, for two reasons:
  * its feedstock moves to energy crops (52.5 €/MWh of biogas);
  * PyPSA's digester learns (1 548 → 1 223 €2025/kW) while TIMES's stays at 1 766 /kW.
* **The capex is structured differently.** TIMES charges no digester FOM. PyPSA charges the
  DEA's 7.8 %/a on top of a lower capex. The annualised digester costs are ≈ 111 /kW/a in
  TIMES and 205–259 €2025/kW/a in PyPSA.
* **Open choice:** keep ENSPRESO's Europe-wide 25 €/MWh, or use TIMES's Walloon feedstock
  cost. The latter needs ICEDD to confirm units and currency, and probably a BEWAL-only
  override, since `custom_costs` applies to every node (`common_parameters.md` §8, still open).

Scripts: the extraction is reproducible with pandas on the `.vd` (`comment="*"`, the nine
VEDA columns), from attributes `Cost_Flo`, `Cost_Inv`, `Cost_Act`, `Cap_New`
(`LUMPINV` / `INSTCAP`), `VAR_FIn`, `VAR_FOut`, `VAR_Act`, `VAR_ActM` and `EQ_CombalM`.

---

## 9. Where to look

* Code:
  * `scripts/build_biomass_potentials.py` (`add_unsustainable_potentials`);
  * `scripts/prepare_sector_network.py` (`add_biomass`, `biogas to gas`);
  * `scripts/walloon_scripts/BEWAL_potentials.py` (`update_BEWAL_potentials`).
* Config: `biomass.classes`, `share_unsustainable_use_retained`,
  `share_sustainable_potential_available` (effective values in
  `results/<run>/configs/config.base_s_adm___<year>.yaml`).
* Data: `data/walloon/custom_potentials.csv` rows `BEWAL,biogas`;
  `config/input_parameters_for_models.csv`, target `potential:BEWAL:biogas:p_nom` (five anchors);
  `resources/<run>/biomass_potentials_s_adm_<year>.csv`.
* Related docs:
  * [`renewable-potentials.md`](renewable-potentials.md) §9.5;
  * [`co2-sequestration.md`](co2-sequestration.md), for the biogenic credit and the `biomass limit`;
  * batch log §11.8 and R1.

## Sources

* Valbiom, *Panorama de la biométhanisation en Wallonie*, 2024 edition:
  https://www.valbiom.be/sites/default/files/tool/file/lay-panorama-biometh-2024-ecran-v3_0.pdf
  (figures read through Renouvelle, *Biométhanisation en Wallonie : une hausse historique en
  2024*: https://www.renouvelle.be/fr/biomethanisation-en-wallonie-une-hausse-historique-en-2024/)
* Gas.be / Climact, *Deep Dive Study for Biomethane in Belgium*, WP4 Externalities, Sept 2021:
  https://a.storyblok.com/f/174880/x/8c26c4176d/20210927-climat-deep-dive-study-for-biomethane-in-belgium.pdf
* IEA Bioenergy, *Implementation of bioenergy in Belgium*, Country Report 2024:
  https://www.ieabioenergy.com/wp-content/uploads/2024/12/CountryReport2024_Belgium_final.pdf
* Sia Partners, *European Biomethane Benchmark*, Dec 2023:
  https://www.sia-partners.com/system/files/document_download/file/2023-12/Sia%20Partners_Benchmark_Europe_Biomethane.pdf
* Eurostat energy balances, `nrg_bal = PPRD`, `siec = R5300`, as processed in
  `resources/eurostat_energy_balances.csv`.
