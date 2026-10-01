# Biogas in PyPSA-WAL

How biogas enters the model, where each number comes from, what the "sustainable" and
"unsustainable" labels mean, and whether they fit Belgium. Written 2026-10-01 from the
1 Oct central (`results/walloon/scen_central`) and the code on `development_plan`.
Batch-log context: [`logs/2026-09-30_cabinet_batch_20260930_2010_1h.md`](logs/2026-09-30_cabinet_batch_20260930_2010_1h.md)
§11.8 and R1.

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
  ENSPRESO potential of manure and sewage sludge only. In Wallonia it is overwritten: the
  Valbiom 8.3 TWh in 2025–2030, then 4.0 / 6.9 TWh in 2040 / 2050 (§3).
* **The Walloon 2040 / 2050 figures are a cap agreed between ICEDD and Valbiom** and applied
  to both TIMES and PyPSA (confirmed 1 Oct 2026, §3.1).
  * They bound **total** Walloon biogas, sustainable and unsustainable together.
  * The 2025 / 2030 Valbiom 8.3 TWh is a loose ceiling. Production in those years is
    roughly known and will not come near it.
* **The label does not describe Belgian feedstock** (§5). Belgian biogas comes mostly from
  agro-food residues, manure and crop residues. Energy crops are a minor share: in Wallonia,
  10.6 % of the tonnage in 2024 and 1 % of the "current mix" in the 2021 Gas.be study.
  "Unsustainable" is a phase-out convention, not a statement about these digesters.
* **The forced Walloon figure is too high and the Flemish one too low** (§6):
  * PyPSA gives Wallonia 1.45 TWh and Flanders 1.13 TWh in 2025;
  * the regional sources say about 0.9 TWh for Wallonia and about 2 TWh for Flanders;
  * TIMES has 0.99 TWh for Wallonia.
* **Six items are listed in §7.** Only one of them moves results today: the cost double
  count. The cap question (item 6) is settled.

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
| `BEWAL biogas` cap | 8 300 | 8 300 | 6 150 | **4 000** | 5 450 | **6 900** |
| source | Valbiom | Valbiom | interpolated | ICEDD–Valbiom cap | interpolated | ICEDD–Valbiom cap |

### 3.1 What the 2040 / 2050 figures are (decision of 1 Oct 2026)

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

### 4.4 The Walloon override does not touch it

* For biogas, `update_BEWAL_potentials` rewrites only the sustainable generator.
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
| **ICEDD–Valbiom cap on the total** (both models, §3.1) | 8.3 (loose) | 8.3 (loose) | **4.0** | **6.9** |

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
* With the cost double count of §7 item 5 removed, a new 2040 chain costs about 60 €/MWh,
  i.e. break-even, and PyPSA would sit near the 4.0 TWh cap that TIMES reaches.

---

## 7. Defects and open items

| # | defect | effect today | fix |
|---|---|---|---|
| 1 | Forced volume split by **total biomass potential**, not by biogas production | Wallonia +0.5 TWh, Flanders −0.9 TWh in 2025 (§6) | per-node override from regional data: TIMES 0.99 / 2.18 TWh, or Valbiom observed ≈ 0.9 TWh |
| 2 | Eurostat year frozen at **2019** for every horizon | −10 % against 2023 for Belgium | minor; follows from 1 once overridden |
| 3 | The label implies crops; Belgian inputs are mostly residues (§5) | reading only: "unsustainable" must not be reported as crop biogas | document; report it as "existing production" |
| 4 | Valbiom cap **plus** forced volume in 2025–2030 (§4.4) | none: the 2025 / 2030 ceiling is loose by design (§3.1); from 2040 the forced part is 0 and the cap covers the total | none needed. Optional tidy-up: apply the cap to the sum of both generators |
| 5 | **Cost double count**: generator at the all-in 78.81 €/MWh `biogas` fuel, and digester capex again on `biogas to gas` | biogas uneconomic until 2050; Walloon gas mix 2040 (R1) | one cost row: feedstock-only `biogas manure` fuel (25.16 €/MWh) with the capex on the link, or the all-in fuel with the upgrading capex only. Test at 6 h |
| 6 | ~~2040 / 2050 caps read as TIMES output~~ **Settled 1 Oct 2026:** an ICEDD–Valbiom cap on total biogas, common to TIMES and PyPSA (§3.1) | 2040 cap not reached in PyPSA (nothing used, item 5); the 2050 cap binds at a 125 €/MWh rent, as it binds in TIMES | none: keep as is |

Item 5 is the one that changes published numbers. Item 1 matters for the 2025–2030
Walloon gas balance and for any biogas figure reported per region.

---

## 8. Where to look

* Code:
  * `scripts/build_biomass_potentials.py` (`add_unsustainable_potentials`);
  * `scripts/prepare_sector_network.py` (`add_biomass`, `biogas to gas`);
  * `scripts/walloon_scripts/BEWAL_potentials.py` (`update_BEWAL_potentials`).
* Config: `biomass.classes`, `share_unsustainable_use_retained`,
  `share_sustainable_potential_available` (effective values in
  `results/<run>/configs/config.base_s_adm___<year>.yaml`).
* Data: `data/walloon/custom_potentials.csv` rows `BEWAL,biogas`;
  `config/input_parameters_for_models.csv` rows 280–283;
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
