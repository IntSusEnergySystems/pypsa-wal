# Belgian utility-scale batteries: current fleet and path to 2030

**Date:** 2026-08-18
**Purpose:** document the Belgian grid-scale BESS inventory used as
`p_nom_min` floors on the three Belgian PyPSA nodes (`BEWAL`, `BEVLG`,
`BEBRU`), and the sources (English / French / Dutch).
**Wired into:** `config/input_parameters_for_models.csv` →
`data/walloon/custom_potentials.csv` → `scripts/walloon_scripts/BEWAL_potentials.py`
(charger / discharger `p_nom_min` and a 4-hour store `e_nom_min`).

These are **floors**, not caps. The optimiser may still build more. Home /
prosumer batteries and pumped hydro (Coo, Plate-Taille) are out of scope of
the utility `battery` carrier.

---

## 1. Recommended floors (MW, AC power)

| Node | 2025 (installed / in service by mid-2026) | 2030 (installed + committed) |
|---|---:|---:|
| **BEWAL** (Wallonia) | **286** | **410** |
| **BEVLG** (Flanders) | **250** | **1860** |
| **BEBRU** (Brussels) | **0** | **0** |
| **BE total** | **536** | **2270** |

2040 and 2050 **hold** the 2030 floor (the 2030 fleet is still within a
20–25 year lifetime; replacements keep the floor). The model can expand
above it.

**2030 total = 2.27 GW** is the Belgian NECP / PNEC figure for large-scale
storage (SolarPower Europe NECP review; JRC 2025 storage-targets note:
2.271 GW large-scale + 0.477 GW small-scale). It sits between Elia’s
AdeqFlex’25 **lower bound** (1.5 GW large-scale already existing or
CRM-contracted by 2028, plus ~0.7 GW from the 2025 CRM → ~2.2 GW) and the
AdeqFlex / FNA **BAT+ upper bound** (4.5 GW in 2030 from connection
studies — a potential, not a floor).

Duration of the identified parks is almost always **4 hours**. The script
therefore also sets `e_nom_min = 4 h × p_nom_min` on the utility store
(the PyPSA default `max_hours` for new batteries remains 6 h).

---

## 2. Bottom-up inventory

### 2.1 In service by mid-2026 (→ 2025 horizon)

| Project | Operator / owner | Municipality | Node | MW | MWh | COD | Sources |
|---|---|---|---|---:|---:|---|---|
| EStor-Lux | SRIW / AvH / CFE / …, Centrica opt. | Bastogne | BEWAL | 10 | 20 | Dec 2021 | EStor-Lux press PDF; Energy-Storage.News |
| Deux-Acren (DES) | Corsica Sole, Yuso opt. | Lessines (Deux-Acren) | BEWAL | 50 | 100 | Autumn 2022 | Corsica Sole; Electrek; Yuso |
| Ruien (Aquila / NKEE) | Aquila Clean Energy / Nippon Koei | Kluisbergen (Ruien) | BEVLG | 25 | 100 | 2023 | Energy-Storage.News; Co-operative News |
| Balen (Nyrstar) | Nala Renewables (Trafigura / IFM) | Balen | BEVLG | 25 | 100 | CRM 2025–26 (COD announced 2022) | Nala; Energy-Storage.News |
| Harmignies | Energy Solutions Group | Harmignies (Mons) | BEWAL | 76 | 300 | Sep 2025 | ESG / Enersynt LinkedIn; Yuso CRM note |
| Vilvoorde | ENGIE | Vilvoorde | BEVLG | 200 | 800 | 14 Nov 2025 (full) | ENGIE EN/FR press; pv magazine FR; ESS News |
| Navagne | Luminus | Visé / Lixhe (Navagne) | BEWAL | 150 | 600 | Jul 2026 | Luminus FR/NL pages; Luminus press (FR) |
| **Wallonia** | | | **BEWAL** | **286** | | | 10+50+76+150 |
| **Flanders** | | | **BEVLG** | **250** | | | 25+25+200 |
| **Brussels** | | | **BEBRU** | **0** | | | no TSO-connected park found |

Vilvoorde was commissioned in two 100 MW tranches (Sep then Nov 2025),
two months ahead of the original Jan 2026 date. Navagne is Wallonia’s
largest park and is in service as of July 2026 — included in the 2025
floor because that horizon is the model’s “current system” year.

### 2.2 Committed / under construction for 2027–2028 (→ 2030 floor)

| Project | Operator | Municipality | Node | MW | MWh | COD | Sources |
|---|---|---|---|---:|---:|---|---|
| Auvelais | Energy Solutions Group, Centrica opt. | Sambreville | BEWAL | 76 | 304 | Q1 2027 | Centrica; SPIE (FR); Loyens & Loeff |
| Gramme Storage 1 | Kallima / SOCOFE / SFPIM / WE | Tihange (Huy) | BEWAL | 50 | 100 | H1 2027 | Centrica (EN) |
| Kallo | ENGIE | Kallo | BEVLG | 100 | 400 | 2027 | ENGIE; Enerdata |
| Drogenbos | ENGIE / NHOA Energy | Drogenbos | BEVLG | 80 | 320 | Sep 2027 | ENGIE (May 2026); Enerdata |
| Ruien (Storm) | Storm / Eneco opt. | Kluisbergen | BEVLG | 200 | 800 | Autumn 2027 | Storm EN/NL; Sweco; Energy-Storage.News |
| Langerlo | Storm / Eneco opt. | Genk | BEVLG | 100 | 400 | Summer 2027 | Storm; Sweco |
| Zeebrugge | Storm | Zeebrugge | BEVLG | 100 | 400 | RTB (≤2030) | Storm |
| Volta (Geel) | HybriX Energy / Alfen | Geel | BEVLG | 35 | 140 | End 2027 | Alfen (EN), CRM |
| Franklin (Massenhoven) | HybriX Energy / Alfen | Massenhoven | BEVLG | 35 | 140 | End 2027 | Alfen (EN), CRM |
| Harelbeke | Aspiravi | Harelbeke | BEVLG | 60 | 240 | Under construction | Aspiravi EN/NL |
| Ruien co-op (2 h) | Aspiravi / Ecopower / BeauVent / NKEE | Kluisbergen | BEVLG | 75 | 150 | Autumn 2027 | Co-operative News (the 25 MW 4 h block is the existing Aquila park, not added again) |
| Green Turtle | GIGA Storage (InfraVia) | Dilsen-Stokkem (Rotem) | BEVLG | 700 | 2800 | 2028 | GIGA Storage; VRT NWS (NL); ESS News |
| **Wallonia additions** | | | | **126** | | | 76+50 |
| **Flanders additions** | | | | **1585** | | | 100+80+200+100+100+35+35+60+75+700 |

Identified 2030 fleet: BEWAL 286+126 = **412 MW** (modelled **410**),
BEVLG 250+1585 = **1835 MW**. The **25 MW** gap to the NECP 2.27 GW
total is booked on Flanders as unnamed CRM / Eneco / Luminus Ringvaart
volume (BEVLG **1860**).

Not in the floor (announced but no FID or only a connection request):

- ENGIE Vilvoorde third tranche (+100 MW / 400 MWh), decision “early 2026”.
- ENGIE Belgium target of **500 MW** by 2030 (already 380 MW with
  Vilvoorde+Kallo+Drogenbos).
- Luminus Ringvaart (Ghent) — “in preparation”, MW not published.
- ORES Walloon connection interest of ~**600 MW** (plan d’adaptation
  2026–2030) — requests, not commissioned projects.
- AdeqFlex BAT+ 4.5 GW — connection-study potential, not a commitment.

---

## 3. Official / system-operator views (to 2030)

### Elia Adequacy & Flexibility 2026–2036 (Jun 2025)

- **1.5 GW** large-scale batteries by 2028 in every storyline:
  “existing + contracted in CRM auctions” (AdeqFlex’25 slides).
- That 1.5 GW **does not** include the extra **~0.7 GW** contracted in
  the 2025 CRM, nor later auctions (FNA public consultation, Jul 2026).
- Small-scale / prosumer batteries (not the utility carrier):
  0.6 GW (2024) → 0.8–1.4 GW (2030) → 1.0–2.6 GW (2036), depending on
  Constrained Transition / Current Commitments / Prosumer Power
  (Solar Magazine NL summary of AdeqFlex).
- BAT+ / connection-study **potential**: **4.5 GW** in 2030 and
  **5.7 GW** in 2035 (FNA). Elia presents this as an upper bound, not a
  forecast.

### Elia CRM (capacity market)

Batteries dominate **new-build** awards.

- Over the first rounds: ~**1.1 GW** new-build BESS selected by winter
  2028–29 (Levassort / CRM 2024).
- Oct 2025 triple auction (Y-1 2026–27, Y-2 2027–28, Y-4 2029–30):
  ~**1.6 GW** cumulative new-build BESS contracted by 2029/30
  (Timera Energy; ESS News).
- Y-4 2029–30: **179 MW derated / 525 MW nominal** of new batteries,
  11 projects (Elia EN/NL press, 30 Oct 2025).
- Named CRM winners (Yuso): Aspiravi Harelbeke, HybriX, Ruien Energy
  Storage 2&3, Auvelais, Gramme, Harmignies, Electrabel, Eneco.

CRM volumes are **derated**. 4-hour batteries currently derate at
roughly 35–50 %; the table above uses **nominal MW** from project
press, not derated CRM MW.

### Elia Summer Outlook 2026

Installed batteries (large + small) are ~**500 MW** above the SO2025
scenario: +365 MW large-scale, +130 MW small-scale, driven by CRM
delivery. That order of magnitude matches the 2025 floor (536 MW
utility-scale) plus residential growth.

### NECP / PNEC (federal)

Updated Belgian NECP: **1.305 GW** pumped hydro, **2.271 GW**
large-scale batteries, **0.477 GW** small-scale batteries by 2030
(SolarPower Europe NECP tracker; JRC “Energy Storage Targets in
National Energy and Network Planning”). The 2030 floor is aligned on
the large-scale figure.

The older Interfederal Energy Pact “3.5 GW storage + 2 GW demand
flexibility by 2030” was **not** taken up as a binding national target
(Commission SWD on the first NECP).

### Regional notes

- **Wallonia (FR):** ORES plan d’adaptation 2026–2030 records ~600 MW
  of high-power battery connection interest on TransHT by April 2025
  (+228 % in a year). Navagne is the flagship operational park;
  Auvelais and Gramme are the next committed TSO-connected units.
- **Flanders (NL):** almost all multi-hundred-MW parks sit here
  (Vilvoorde, Ruien, Langerlo, Green Turtle, Zeebrugge, Kallo,
  Drogenbos). VRT NWS (Jul 2026) on Green Turtle: 700 MW / 2.8 GWh,
  construction from Sep 2026, COD 2028, “vermogen van een kleine
  kernreactor”.
- **Brussels:** no utility-scale TSO-connected BESS identified.
  Drogenbos is Flemish territory, on the regional border.

---

## 4. Sources by language

### English

- ENGIE, “ENGIE’s battery storage project in Vilvoorde fully commissioned”, 14 Nov 2025.
- ENGIE Group newsroom, Vilvoorde construction start (200 MW / 800 MWh).
- Elia, Adequacy & Flexibility study 2026–2036 (27 Jun 2025) and slides.
- Elia, “CRM auction results published…”, 30 Oct 2025.
- Elia, Flexibility Needs Assessment (public consultation, 24 Jul 2026).
- Energy-Storage.News / ESS News: Ruien 25 MW, Vilvoorde, CRM, Storm, Green Turtle.
- Alfen, HybriX 2 × 35 MW (Geel, Massenhoven), 10 Dec 2025.
- Storm, Ruien / Langerlo / Zeebrugge project pages.
- GIGA Storage, Green Turtle financial close, 10 Jul 2026.
- Centrica Energy: Auvelais 76 MW / 304 MWh; Gramme 50 MW / 100 MWh.
- Yuso, “Belgium’s 2025 CRM Auctions”; Deux-Acren operating note.
- SolarPower Europe NECP tracker; JRC 2025 storage-targets assessment.
- Timera Energy, “BESS continues to dominate new build capacity in Belgian CRM”.

### French

- ENGIE Belgium, « Le parc de batteries d’ENGIE à Vilvoorde est désormais entièrement opérationnel ».
- pv magazine France, « Engie veut déjà étendre son BESS de Vilvoorde à 300 MW / 1200 MWh », 21 Nov 2025.
- Luminus, « Parc de batteries de Navagne » and press « Première pierre… » (150 MW, Visé).
- SPIE Belgium, parc d’Auvelais (76 MVA / 304 MWh, Sambreville).
- ORES, *Plan d’adaptation électricité 2026–2030* (consultation), §1.2.6 stockage.
- PNEC belge (projet d’actualisation / contributions régionales).

### Dutch

- Elia, « Resultaten CRM-veilingen gepubliceerd… », 30 Oct 2025.
- Luminus, « Batterijpark Navagne » (150 MW / 600 MWh).
- Storm, « Storm haalt 330 miljoen euro op… » (Ruien 200 MW, Langerlo 100 MW).
- Aspiravi, projectpagina Harelbeke (60 MW / 240 MWh, in opbouw).
- VRT NWS, « Bouw grootste Belgische batterijpark ooit kan starten » (Green Turtle, Dilsen-Stokkem), 10 Jul 2026.
- Solar Magazine NL, AdeqFlex summary (1.5 GW grootschalig; 2.5–4.1 GW totaal in 2036).

---

## 5. How this is applied in pypsa-wal

Utility batteries are **Stores + charger/discharger Links**
(`electricity.extendable_carriers.Store: [battery, H2]`), one set per
node, not `StorageUnit`s.

| Artefact | Role |
|---|---|
| `config/input_parameters_for_models.csv` | Authoritative `p_nom_min` (MW) per node and year. Targets `potential:BEWAL:battery:p_nom_min` (and BEVLG, BEBRU). `year_rule=hold`. |
| `python scripts/build_common_parameters.py --write` | Patches `data/walloon/custom_potentials.csv`. |
| `scripts/walloon_scripts/BEWAL_potentials.py` | For `technology=battery`, sets charger and discharger `p_nom_min` at that bus. Other vintages already on the bus are subtracted so the floor is on the **fleet**, not stacked on new-build. Store `e_nom_min = 4 × residual MW`. Home batteries on the LV bus are ignored. |

A `p_nom_min` of 0 on BEBRU is intentional: the node has a battery
asset (every clustered bus does) but no forced utility capacity.

Small-scale residential batteries stay on the separate `home battery`
carrier and are **not** included in these floors.
