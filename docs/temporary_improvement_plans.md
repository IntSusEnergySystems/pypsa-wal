# Temporary improvement plans — meeting 2026-08-27

Roadmap from the results review of
[`scen_demande_haute` @ 2010, 1h](logs/2026-08-26_scen_demande_haute_2010_1h.md)
(solved 26–27 Aug, published as Explorer `demande-haute-2010-1h (times-pypsa) - 27/08/2026`).
Each item is the meeting note, then evidence from that run (and the 25 Aug archive
where the meeting compared “previous”), then options and a recommended next step.

**How to use this file.** The *Recommended* row is the proposed default for the
next production solve. *Do not* treat every option as queued work — several are
mutually exclusive, and two (Flanders nuclear, electricity import cap) change
the meaning of the TIMES soft-link. Decide those two before touching the rest.

**Evidence vintage.** Networks
`results/walloon/scen_demande_haute/networks/base_s_adm___*.nc`.
Comparison archive `/sylvain/mount/pypsa-wal-data/archive/walloon-20260825`.
Companion notes: [ccs_alignment.md](ccs_alignment.md),
[nuclear-alignment-20260816.md](nuclear-alignment-20260816.md),
[network-representation-analysis.md](network-representation-analysis.md),
[heat-softlink.md](heat-softlink.md),
[renewable-potentials.md](renewable-potentials.md),
[discount-rates.md](discount-rates.md).

| # | Item | Kind | Severity | Recommended default |
|---|---|---|---|---|
| 1 | Gas storage in Wallonia | data | medium | Pin BEWAL `e_nom_max = 0`; keep Loenhout on BEVLG |
| 2 | CCGT-CC only in 2050 | physics / TIMES | high | Do **not** hard-pin 2040; first give BE a CO₂ sink |
| 3 | No WAL grid expansion 2025→2030 | already correct | low | Keep the freeze; decide if Boucle du Hainaut is a *floor* in 2040 |
| 4 | Biogas 6.9 / 4 TWh | data | medium | Confirm with ICEDD: 6.9 is not in the vd |
| 5 | Flanders P2H falling | expected | low | Document; not a bug |
| 6 | Energy independence dropped | physics | **high** | Diagnose after neighbour-offshore fix; import cap is a scenario choice |
| 7 | Flanders heat demand rising | expected / Explorer | medium | Total heat *falls*; DH is what rises — check the chart |
| 8 | No rooftop PV | physics | high | Impose TIMES rooftop *energy* share at BEWAL |
| 9 | BECCS → DAC / industry CC | physics / TIMES | high | Pin industry-CC volumes; do **not** turn DAC back on |
| 10 | 3 GW nuclear min in Flanders 2050 | scenario | **high** | New overlay, not the TIMES-aligned base — decide 3 vs 6 GW Belgium |

---

## 1. Gas storage in Wallonia — is there any? What potential?

### What the meeting asked

Confirm that the model has (or should have) gas storage in Wallonia, and what
the geological potential is.

### Evidence

Belgium’s only operating underground store is **Loenhout** (Fluxys, aquifer,
Antwerp province → **Flanders**): 7.6 TWh firm, 770 Mm³ useful working gas,
withdrawal 625 000 m³/h. It is a national buffer, not a Walloon asset.

Wallonia *had* two coal-mine stores, **Anderlues** and **Péronnes-lez-Binche**
(Distrigaz / Fluxys). Both were closed **1 November 2012** (AM 06/12/2012 and
MB 04/12/2012). ISSeP still monitors residual pressure; there is no reopening
plan and no salt-cavern geology. Residual volumes were ~120 Mm³ at Péronnes
historically — two orders of magnitude below Loenhout, and gone.

On the 26 Aug networks:

| Store | 2025 | 2030 | 2040 | 2050 | `e_nom_min` | `e_nom_max` |
|---|---:|---:|---:|---:|---:|---|
| **BEWAL gas Store** | 130 GWh | 203 | 82 | **0.06** | **0** | **inf** |
| BEVLG gas Store | 545 | 545 | 545 | 545 | **545 GWh** | inf |
| BEBRU gas Store | 17 | 30 | 8 | 0.02 | 0 | inf |

Flanders holds the only Belgian *existing* inventory (545 GWh floor from
SciGRID_gas / gas-input nodes — Loenhout, scaled). Wallonia’s 130–203 GWh is
an unconstrained endogenous store (`prepare_sector_network.py` copies
`gas_input_nodes["storage"]` which is 0 at BEWAL, then leaves `e_nom_max =
inf`). It is not a site. The model abandons it by 2050. There are no
charger/discharger links; the Store sits on the gas bus.

See also the water-pits analogue in the solve log §11.14 B: an unbounded store
is not a result.

### Options

| | What | Effect |
|---|---|---|
| **A. Pin Wallonia to zero** (recommended) | `e_nom_max = 0` (and `e_nom_min = 0`) on `BEWAL gas Store` | Matches geology. Flanders keeps Loenhout. Seasonal gas flexibility in Wallonia then comes from the pipeline (already 7.5 GW, zero capital_cost — a separate issue). |
| **B. Leave it free** | status quo | 2025/2030 “Walloon storage” of 0.1–0.2 TWh will be plotted as if it were a site. |
| **C. Hypothetical new store** | explicit `e_nom_max` with a source (none exists today) | Only if a policy study asks “what if Wallonia reopened mines / built a cavern”. Not this scenario. |
| **D. Give Loenhout its real 7.6 TWh** | raise BEVLG `e_nom_min` from 545 GWh to ~7 600 GWh | The 545 GWh floor looks like a unit/scaling miss against Fluxys’s 7.6 TWh. Worth a one-line audit of `gas_input_nodes["storage"]` (MWh vs GWh vs the 0.98-quantile clip at line 2127 of `prepare_sector_network.py`). Independent of Wallonia. |

### Recommended

**A**, plus the **D** audit. Implementation: a Walloon overlay in
`add_gas_network` / `BEWAL_potentials.py` (same pattern as other BEWAL
`e_nom_max`), or a row in `custom_potentials.csv` if stores are patched there.
Do not publish BEWAL gas-store capacity from this vintage.

---

## 2. CCGT-CC appears only in 2050 — impose the TIMES capacity in 2040?

### What the meeting asked

TIMES has CCGT with capture from the 2030s. PyPSA only builds it in 2050.
Should we force the TIMES capacity in 2040?

### Evidence

TIMES-WAL ([ccs_alignment.md](ccs_alignment.md) §0): Flémalle (E12) + Seraing
New (E13) = **1 740 MW_e**, unabated in 2025/2030, **fully on CCS from 2035**
(retrofit, ~86 % capture). New-build post-combustion CCGT-CCS is in the
dictionary and **not built**. 2040 and 2050 both carry the 1.74 GW retrofit.

PyPSA 26 Aug (MW_e = `p_nom_opt × η`):

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| BEWAL CCGT (unabated) | 1 740 | 1 741 | 1 785 | 1 277 |
| BEWAL **CCGT CC** | 0.0 | 0.2 | **0.2** | **463** |
| BEVLG CCGT CC | 0.0 | 0.2 | 0.2 | 0.2 |

Confirmed: material CCGT-CC **only in 2050**, only in Wallonia, and only
**463 MW_e** inside the 1 740 `CCGT-all` floor — not a TIMES retrofit of
Flémalle + Seraing. The floor is technology-neutral since 26 Aug
([ccs_alignment.md](ccs_alignment.md) §13.1); the model *may* meet it with
capture and mostly does not until 2050.

Why 2040 does not build capture, despite a 243 EUR/t effective CO₂ price
(break-even vs unabated CCGT ≈ 103 EUR/t at 4 000 FLH):

1. **Myopic brownfield.** 2040 inherits 1 740 MW of *unabated* CCGT that
   already satisfies the floor. Building capture means paying a second power
   island; TIMES pays only the absorber.
2. **No retrofit link.** PyPSA `CCGT CC` is greenfield
   ([ccs_alignment.md](ccs_alignment.md) §6.2).
3. **Nowhere to put the CO₂.** All three Belgian nodes have
   `co2 sequestered` `e_nom_max = 0`; NL’s store is **100 % full in 2040 and
   2050** (solve log §11.14 C). 2050 still finds a German/British sink for
   0.41 Mt from Walloon CCGT-CC; 2040’s European sequestration cap is tighter
   (90 vs 125 Mt).
4. **Pinned heat already eats the Walloon cap.** Option B′ claims 86 % of the
   2050 BEWAL budget before power CCS is asked to help.

Forcing 1.74 GW of CCGT-CC in 2040 without a CO₂ sink is likely infeasible or
will dump captured CO₂ into an already-binding European store at a huge dual.

### Options

| | What | Effect |
|---|---|---|
| **A. Hard-pin TIMES capacity in 2040** | `agg:BEWAL:CCGT CC:min = 1740` from 2040 (and keep the `CCGT-all` floor, or replace it) | Reproduces TIMES *MW*. Ignores retrofit economics. Needs a CO₂ export/storage assumption or the LP will struggle. Still not a retrofit of the existing TGVs. |
| **B. Retrofit link** (correct TIMES analogue) | Second Link per existing CCGT, `p_nom` tied to standing capacity, cheaper than greenfield (power island reused) | Matches TIMES physically. Non-trivial code (new carrier, brownfield carry-forward, tests). Best long-term, not a next-run patch. |
| **C. Give Belgium a CO₂ sink first** (recommended sequencing) | Documented `e_nom_max` on BEWAL/BEVLG/BEBRU, or a priced export to NL/NO (solve log §11.14 C2) | Makes capture *eligible* in 2040. Then look at whether the model builds it. If it still does not, the gap is the missing retrofit, not the sink. |
| **D. Leave 2040 free, footnote the gap** | status quo | Honest: PyPSA new-build CCS ≠ TIMES retrofit from 2035. Do not plot 2040 CCGT-CC as 0 for policy. |

### Recommended

**C then D**, not A. Imposing TIMES MW in 2040 without storage papers over the
cause. If the next ICEDD meeting wants the TIMES *outcome* in the published
charts regardless, A is a scenario overlay (`scen_ccgtcc_times`) on top of C,
not a silent change to the base. B is a later physics ticket.

Do not publish 2050’s 463 MW_e as “the TIMES retrofit of Flémalle + Seraing”
(solve log §11.10 item 8).

---

## 3. No transmission expansion in Wallonia 2030 vs 2025 — any current plans?

### What the meeting asked

The internal grid does not grow between 2025 and 2030. Is that because there
are no plans, or because the model is frozen?

### Evidence

Live network, AC line `2` (BEVLG ↔ BEWAL), `s_max_pu = 0.7`:

| Horizon | `s_nom` (MW) | `s_nom_max` (MW) | **usable** (MW) | Net flow (TWh, + = VLG→WAL) |
|---|---:|---:|---:|---:|
| 2025 | 5 094 | 5 143 | **3 566** | −9.9 (WAL exports) |
| 2030 | 5 094 | 5 143 | **3 566** | −5.6 |
| 2040 | 5 094 | 18 857 | **3 566** | +2.7 |
| 2050 | 5 094 | 20 571 | **3 600** | +3.1 |

**No expansion 2025→2030**, by design.
[network-representation-analysis.md](network-representation-analysis.md) §3.1.1:
Wallonia–Flanders stays at the clustered base through 2030 because **Boucle du
Hainaut** (Avelgem–Courcelles, 6 GW, 380 kV) slipped from the original 2029–30
FDP date to **2032–2033**. The step is in the 2040 NTC file (3 600 → 13 200 MW
usable ceiling).

Online check (Elia project page; Conseil d’État Oct 2025; final environmental
report filed March 2026): commissioning still **2032–2033**. Ventilus is the
Flanders twin (Princess Elisabeth Zone infeed), not a Walloon internal line.
There is **no** other 380 kV WAL–VLG project with a 2030 date.

The 2040 *ceiling* opens; the optimiser **does not build**. Flows in 2040/2050
are ~3 TWh/year across a 3.6 GW usable path (load factor ~10 %). Boucle du
Hainaut is available and unused — a committed-project vs optional-expansion
question, not a 2030 one.

Usable stays ~3.6 GW in 2040 even with `s_nom_max` at 18.9 GW because the NTC
is the *flow* ceiling under `vopt` (solve log §11.5, R7). Report usable
capacity, not `s_nom_opt`. Cross-border NTC (ALEGrO, Nemo, BE–FR, BE–NL) *does*
grow on the published-project schedule.

### Options

| | What | Effect |
|---|---|---|
| **A. Keep 2025–2030 freeze** (recommended) | already implemented (`ntc_2030.csv` BEWAL–BEVLG = 3 600) | Matches Elia. Nothing to do for 2030. |
| **B. Force Boucle du Hainaut in 2040** | `s_nom_min` (or NTC as floor) on BEWAL–BEVLG from 2040 = 3 600 + 6 000 | Treats the line as committed infrastructure. Changes 2040/2050 congestion rent and WAL↔VLG prices. Justified if the publication should show the line *in* the grid, not merely *allowed*. |
| **C. Let 2030 expand** | raise 2030 NTC | Contradicts the delayed permit. Do not. |

### Recommended

**A** is already right. Add **B** as an explicit decision for the next
parameter round: “is Boucle du Hainaut in the 2040 *grid* or only in the 2040
*option set*?” Until then, do not read the unused 2040 ceiling as “the model
rejects Boucle du Hainaut” — it rejects paying for thermal capacity it cannot
use above the NTC.

---

## 4. Decrease biogas to 6.9 TWh in 2050 (4 TWh in 2040)

### What the meeting asked

Cut the Walloon biogas potential from the current 8.3 TWh (flat) to **6.9 TWh
in 2050** and **4 TWh in 2040**.

### Evidence

PyPSA today: `potential:BEWAL:biogas:p_nom = 8300` GWh/an, **every** horizon
(Valbiom; `custom_potentials.csv` / master CSV). Dispatch on this run:

| Horizon | Cap | Dispatch |
|---|---:|---:|
| 2025 | 8.30 TWh | 0 (off) + 1.45 unsustainable |
| 2030 | 8.30 | ~0 + 0.93 unsustainable |
| 2040 | 8.30 | **1.45** |
| 2050 | 8.30 | **8.30 (binds)** |

The 8.3 TWh block is all-or-nothing at 78.8 EUR/MWh (~654 MEUR/a) and is one
of the four exhausted 2050 CO₂ escape valves (solve log §11.14 C). Cutting it
**raises** the 2050 Walloon carbon dual unless something else gives.

TIMES vd `scen_demande_haute` (upgrading `BWSUPGZH100`, region RW):

| Year | Upgraded biogas |
|---|---|
| 2030 | **0.90 TWh** |
| 2040 | **7.67 TWh** |
| 2050 | **8.07 TWh** |

TIMES *uses* ~8 TWh from 2040, not 4. The 6.9 / 4 figures are **not** in the
vd, `aggregation.md`, or `common_parameters.md`. They appear only in this
meeting list.

Where 8.3 comes from: Green Gas Platform / Valbiom realistic injectable
potential, Belgium 15.6 TWh_PCS, **53 % Wallonia → 8.3 TWh**. ICEDD
alternatives in the tree already use **7.7 TWh** (`custom_potentials_alternatif.csv`)
and **7.8 TWh** (`custom_potentials_imppel.csv`), still flat. CWaPE/ICEDD
*Avenir du gaz* discusses an **8 TWh** TIMES sub-scenario.

Possible readings of “6.9”:

- HHV→LHV on 8.3 (~0.9 × 8.3 ≈ 7.5, not 6.9).
- A more conservative *deployment* than the Valbiom *potential*.
- A different cadastre vintage.

4 TWh in 2040 is a **deployment trajectory**, not a potential: TIMES already
runs 7.7 TWh in 2040. Imposing 4 TWh would *diverge* from TIMES, not align.

### Options

| | What | Effect |
|---|---|---|
| **A. Wait for ICEDD to source 6.9 / 4** (recommended) | do not change the CSV until the number has a citation | Avoids a silent TIMES break. |
| **B. Potential = 6.9 TWh all years** | one cell in the master CSV, `--write` | 2050 still binds; 2040 dispatch (1.45) is unaffected. Small 2050 CO₂ impact. |
| **C. Trajectory 4 (2040) / 6.9 (2050)** | year-varying `potential:BEWAL:biogas:p_nom` | 2040 cap becomes 4 TWh (currently 1.45 used — still slack). 2050 loses 1.4 TWh of a binding CO₂ valve → dual up. TIMES 2040 is 7.7, so this is a **PyPSA-only** conservative path. |
| **D. Align the *shape* with TIMES, keep ~8 TWh in 2050** | 0.9 / 7.7 / 8.1 TWh caps | Makes 2040 use biogas when TIMES does. Opposite of the meeting’s 4 TWh. |

`--write` currently forbids a `planning_horizon: all` row from holding a
year-varying value (`instructions.md`). C or D needs split rows in the master
CSV (the failsafe will say so).

### Recommended

**A.** Ask ICEDD whether 6.9/4 is (i) a new Valbiom/LHV figure, (ii) a
deployment ceiling below potential, or (iii) a mix-up with another scenario.
If (ii), implement **C** as a named sensitivity, not the demande-haute
default, and expect a higher 2050 BEWAL CO₂ dual. If the goal is TIMES
alignment, **D** is the move, not a cut.

Until then, keep 8.3 and keep checking biogas dispatch before reading 2040
opex dips (`instructions.md` operational-cost note).

---

## 5. Power-to-heat decreases in Flanders — why?

### What the meeting asked

P2H in Flanders falls across horizons. Is that a bug?

### Evidence

Flanders is **not** heat-soft-linked. Only `times_heat.node: BEWAL` is
overwritten; BEVLG follows PyPSA-Eur (JRC/Eurostat × population, EU-2012
stock). Option B′ pins Wallonia and leaves Flanders free.

| BEVLG | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| HP fleet (MW_th) | 7 132 | 7 113 | 7 003 | 7 317 |
| Resistive (MW_e) | 3 054 | 2 680 | 1 789 | 1 509 |
| **P2H electricity (TWh_e)** | **18.0** | **17.3** | **15.7** | **15.5** |
| P2H heat (TWh_th) | 41.6 | 39.8 | 36.9 | 37.3 |
| of which urban-central HP heat | 4.6 | 4.3 | 3.9 | **8.9** |

| BEWAL (for contrast) | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| **P2H electricity (TWh_e)** | **3.2** | **3.2** | **3.7** | **7.4** |
| HP fleet (MW_th) | 1 366 | 1 452 | 2 525 | 3 238 |

Flanders P2H electricity **falls 18 → 15.5 TWh_e**. Wallonia **rises**
3.2 → 7.4 (TIMES electrification under B′).

Drivers in Flanders, not a solver bug:

1. **Renovation.** Total Flemish building heat load 56.7 → 47.1 TWh_th
   (−17 %). Less heat to serve.
2. **Fuel substitution, not a P2H collapse.** Urban-decentral air HP heat
   31.5 → 23.5 TWh_th; urban-decentral resistive 1 943 → 350 MW. Meanwhile
   **urban-central air HP** jumps 641 → 1 575 MW_th in 2050 (heat 3.8 →
   7.4 TWh). P2H *moves into DH*, which Explorer may plot as a different
   carrier.
3. **Asymmetric coupling.** Wallonia cannot re-optimise the mix; Flanders
   can, and PyPSA-Eur’s default is “build DH + central HP”, not “keep
   decentral HP”.

### Options

| | What | Effect |
|---|---|---|
| **A. Document and leave** (recommended) | footnote on every Flanders heat chart | Correct. The drop is renovation + DH shift. |
| **B. Apply a TIMES-like mix to Flanders** | needs a Flemish TIMES (does not exist) or a copied Walloon mix | Would make Flanders look like Wallonia. Not evidence-based. |
| **C. Freeze Flanders DH share** | cap `urban central heat` load growth | Stops the 2.5 → 15 TWh DH explosion (item 7) and the P2H relocation. A scenario choice about *Flemish* policy, not a Walloon soft-link. |

### Recommended

**A**, and look at **C** together with item 7. Do not “fix” Flanders P2H to
rise in lockstep with Wallonia — that would be manufacturing TIMES-like
electrification in a region TIMES does not model.

---

## 6. Energy independence has dropped — model issue? TIMES 10 TWh import cap?

### What the meeting asked

Independence is worse than the previous published run. Is the model broken?
Should PyPSA impose TIMES’s **max 10 TWh electricity imports in 2050**?

### Evidence

TIMES (vd, region **RW only**): `Transfo_Imp` activity **36.000 PJ = 10.000 TWh**
in 2050 (6.47 TWh in 2040, 2.94 TWh in 2030). Encoded as the solved import
adaptor `ELCIMP` → `ELCHIG` (`IMPELCHIG` + `IMPELCOFFWINBE`). There is no
equivalent annual-energy constraint in PyPSA — only NTC *power* ceilings.

Net electricity import, this run vs 25 Aug archive (positive = importer):

| | BE 26 Aug | BE 25 Aug | BEWAL 26 Aug | BEWAL 25 Aug |
|---|---:|---:|---:|---:|
| 2025 | +21.4 | +13.7 | **−11.0** (exporter) | −11.0 |
| 2030 | +6.1 | +2.8 | −5.8 | −10.1 |
| 2040 | +19.9 | +7.1 | +8.2 | +0.6 |
| **2050** | **+30.8** | **+5.8** | **+18.0** | **+6.9** |

2050 Belgium **31 TWh** vs TIMES **10 TWh** (and vs 25 Aug **6 TWh**, which
happened to sit under the TIMES cap). Wallonia flips from exporter to
**+18 TWh** importer. ClimAct `strategy_metrics` “Exports” for Wallonia:
11 / 6 / **0** / **0** TWh.

This is **not** a failed constraint — there is none. It is a changed
optimum. Same TIMES vd, weather year, resolution, option B′. What moved
between 25 Aug and 26 Aug (solve log §11.1b):

| Change | Direction on independence |
|---|---|
| Walloon onwind **12.4 → 6.5 GW** (CCL max fix) | **−11 TWh** local wind at CF ~25 %. Largest single hit. |
| `vopt` + grown NTC | More *ability* to import (BE–FR 7.3 GW, BE–NL 8.6, Nemo 3.8). |
| Neighbour offshore **an order of magnitude too small** (NL 4.5 GW, DE 5.1 vs 50/70 GW targets) while neighbour onshore is huge | Distorts import prices. §11.14 D; a fix is already in `renewable-potentials.md` but **not in this solve**. |
| Aviation out of national CO₂; `CCGT-all` floor | Second-order on the power balance. |
| All new nuclear in Wallonia, Flanders **0 GW** in 2050 | Flanders is the big load; it has no 2050 nuclear. Item 10. |

So: independence dropped because the model **stopped overbuilding Walloon
wind** and **was allowed to use the interconnectors**, on a European system
whose offshore fleet is still wrong. The 25 Aug “independent” 2050 was the
one that illegally sat at 12.4 GW of Walloon onshore.

PyPSA 2050 BE import 31 TWh is **Wallonia+Flanders+Brussels from five
neighbours**. TIMES 10 TWh is **Wallonia from a stylised rest-of-world**.
They are not the same quantity. A 10 TWh cap copied onto Belgian *or*
Walloon annual net import is a new policy, not a soft-link.

### Options

| | What | Effect |
|---|---|---|
| **A. Re-solve after neighbour-offshore + onwind trajectory** (recommended first) | already specified in [renewable-potentials.md](renewable-potentials.md); needs a full `resources/` wipe | Neighbours get real offshore; Walloon onwind follows 2.4→6.5 GW instead of jumping. Independence will move. Measure *then*. |
| **B. Walloon annual import cap = 10 TWh** | extra functionality, `sum(BEWAL AC net import) ≤ 10 TWh` in 2050 | Closest TIMES analogue (RW). Will force local generation or cut load-meeting via Flanders. Interacts with item 10 (Flanders nuclear) and the onwind cap. |
| **C. Belgian annual import cap = 10 TWh** | same, on BE | Much tighter than TIMES (TIMES is Wallonia-only). 10 TWh for all of Belgium is a political autarky scenario. Name it as such. |
| **D. Keep free trade, report the number** | status quo after A | Honest European-market result. TIMES 10 TWh stays a TIMES figure, plotted next to PyPSA, not imposed. |

### Recommended

**A, then D**, with B as a **named sensitivity** (`scen_autarky_wal` or similar)
if the Explorer needs a TIMES-comparable independence chart. Do not put C on
the demande-haute default — it would say “Belgium as a whole may not import
more than Wallonia-TIMES imports”, which is a different country.

Until A is solved, do not publish 2050 Belgian imports as a policy result
(solve log §11.14 D.5: every 2050 European quantity is conditional on the
under-built offshore fleet).

---

## 7. Heat demand increases a lot in Flanders, stable in Wallonia — why?

### What the meeting asked

Flemish heat demand shoots up; Walloon heat is flat. Bug?

### Evidence

Annual **building** heat *load* (rural + urban decentral + urban central):

| TWh_th | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| **BEWAL total** | 28.1 | 27.8 | 25.9 | **23.3** |
| BEWAL urban central (DH) | 0.46 | 1.22 | 1.90 | 2.69 |
| **BEVLG total** | 56.7 | 57.0 | 53.7 | **47.1** |
| BEVLG urban central (DH) | **2.5** | **5.2** | **9.9** | **15.0** |

**The sum falls in both regions** (renovation). What *explodes* is **Flemish
district heating** (×6). Walloon DH only ×6 as well in relative terms but
from a TIMES-sized base (0.46 TWh — TIMES has almost no DH).

Why the two regions are not comparable ([heat-softlink.md](heat-softlink.md),
[times_data_extraction.md](../times_data_extraction.md)):

- **BEWAL** useful-heat totals *and* the appliance mix come from TIMES
  (`write_wallon_heat_demands`, option B′). DH stays out of the mix transfer
  on purpose ([heat-softlink.md](heat-softlink.md) §6).
- **BEVLG** is stock-standard PyPSA-Eur: population-weighted JRC/Eurostat
  energy totals, EU-2012 heating distribution, endogenous DH expansion.
  Nothing in TIMES-WAL describes Flanders.

If the meeting looked at an Explorer DH chart, or at urban-central heat, the
Flanders “increase” is real in the model and **not** a TIMES transfer error.
If they looked at *total* heat, the chart is misread — both fall.

A leftover confusion from 18 Aug: with DAC on, Walloon urban-central heat was
sized for DAC (6 TWh_th to the capture plant). DAC is now off; that artefact
is gone. Flanders never had that mechanism.

### Options

| | What | Effect |
|---|---|---|
| **A. Label the charts** (recommended, immediate) | “Flanders heat is PyPSA-Eur default; Wallonia is TIMES.” Split total vs DH. | Stops the misreading. |
| **B. Cap Flemish DH** | exogenous DH share or `urban central heat` load trajectory | Policy choice. Use if the publication should not show 15 TWh of Flemish DH in 2050 with no Flemish TIMES behind it. |
| **C. Soft-link a Flemish heat mix** | needs data that does not exist in this vd | Out of scope until a Belgian TIMES or a Flemish study is coupled. |

### Recommended

**A** now. **B** if Explorer users keep reading Flemish DH as a forecast.
Do not try to make Flemish *total* heat “rise” — it does not.

---

## 8. No rooftop PV in PyPSA — align with TIMES?

Meeting sub-notes: *coûts de transport*; *imposer la part en toiture venant de TIMES*.

### What the meeting asked

TIMES is mostly rooftop; PyPSA builds none. Should we cost the grid properly,
and/or force the TIMES rooftop share?

### Evidence

TIMES 2050 (RW, `VAR_Act`):

| Process | TWh |
|---|---:|
| `ERNW_PV-GreenField_SOL_N` (utility) | 4.30 |
| `ERNW_PV-Buildings_SOL_N` (rooftop commercial) | 10.57 |
| `ERNW_PV-RES_Homes_SOL_N` (rooftop residential) | 4.70 |
| **Rooftop share** | **~15.3 / 19.8 TWh ≈ 77 %** |

PyPSA 26 Aug, BEWAL `p_nom_opt`:

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| `solar rooftop` | **0.05** | 0.52 | 0.61 | **0.63 MW** |
| `solar` | 4 088 | 4 088 | 2 786 | 5 038 |
| `solar-hsat` | 0 | 3 970 | 6 915 | 6 916 |
| **total PV** | 4.1 GW | 8.1 | 9.7 | **12.0 GW** |

Rooftop potential is **46 GW** (Énergie Commune). Not a cap problem.
[renewable-potentials.md](renewable-potentials.md) §7: rooftop is 0 MW
“for cost reasons (19 % dearer per MW than ground-mounted)”. Annualised
`capital_cost` 2025: rooftop **84 628** > hsat 79 188 > utility **71 898**
EUR/MW/year. Overnight: rooftop **920** vs utility **526** vs hsat
**560 €/kW_e** (`custom_costs.csv`). Hurdle rates are the same 7.5 %
(`ALL-PV`, [discount-rates.md](discount-rates.md) D5) — not the driver.

Generation is **not** soft-linked ([ccs_alignment.md](ccs_alignment.md) §12).
TIMES rooftop share is never transferred.

**Transport / distribution costs.** Rooftop sits on `BEWAL low voltage`;
utility/hsat on the transmission bus. The distribution link is extendable at
**~529 €/kW** ([network-representation-analysis.md](network-representation-analysis.md)
§5, §9). In principle rooftop avoids that link for energy consumed behind the
meter. In practice:

- HP / EV already force distribution expansion (9.5 GW of zero-capital-cost
  distribution in 2050 — solve log §11.6), so the “saved” grid is often
  already paid for.
- The CAPEX gap (920 − 526 = **394 €/kW**) is similar to the distribution
  overnight cost. Even crediting rooftop with a *full* avoided grid still
  does not clearly beat utility, and surplus rooftop *uses* the link the
  other way (export).
- The distribution link is a single copper plate per node, not a hosting-capacity
  map, so there is no “export-limited suburb where rooftop is worthless” nor
  “self-consumption zone where it is gold”. Item 9 of the network note is the
  proper long-term fix; it will not, by itself, produce 77 % rooftop.

A second, smaller bug: `BEWAL low voltage` maps to country `BE`, so a future
rooftop build would count against the **Belgian** `solar-all` cap, not the
Walloon one ([renewable-potentials.md](renewable-potentials.md) §7.3). Harmless
while rooftop is 0; repair before imposing a floor.

### Options

| | What | Effect |
|---|---|---|
| **A. Impose TIMES rooftop *energy* share at BEWAL** (recommended) | annual constraint: rooftop generation ≥ 77 % of BEWAL PV (or ≥ TIMES TWh) | Gets the published mix right. Lets the model still choose total MW. Needs the LV-country alias fix first. |
| **B. Impose TIMES rooftop *capacity*** | `p_nom_min` on `solar rooftop` from vd `VAR_Cap` | Heavier. Capacity ≠ energy (rooftop CF is lower). |
| **C. Only fix costs / grid** | cut rooftop CAPEX, or credit avoided distribution, or DSO hosting map | Will not reach 77 % with a 75 % overnight gap. Worth doing as realism, not as the alignment tool. |
| **D. Leave at 0, report total PV** | current review practice | Honest about the cost table; misleading vs TIMES and vs real Walloon PV (overwhelmingly rooftop today). |

### Recommended

**A** as the alignment mechanism (config switch under `sector.times_pv` or a
one-off extra-functionality constraint, BEWAL only). **C** in parallel so the
constraint is not fighting a 400 €/kW lie — at least document that TIMES and
PyPSA do not share a rooftop overnight cost (920 vs whatever TIMES uses).
Repair the LV country alias before A, otherwise the Belgian `solar-all` cap
will clip Walloon roofs.

Do not apply A to Flanders: TIMES has no Flemish rooftop share.

---

## 9. BECCS is on in TIMES — activate DAC, or a new industrial capture process?

### What the meeting asked

TIMES runs biomass-for-industry with carbon capture. PyPSA does not show an
equivalent. Turn DAC on at a similar volume? Or add an industrial process?

### Evidence

TIMES 2050 industrial capture (`INDCO2c`), several processes, **~4.8 Mt**:
chemicals `ICMPRC20/21` (1.71 + 1.64 Mt), lime `ILMQLMPRCC02` (0.78), glass
oxyfuel, etc. Food-process CC is in the dictionary but captures ~0.
**DAC (`CO2DAC-01`) is not built** (duals only). Storage
`STORAGEMINELC + STORAGEMININD` ≈ **7.1 Mt** in Wallonia
([ccs_alignment.md](ccs_alignment.md) §0, §11).

PyPSA 26 Aug, BEWAL, `sector.dac: false`:

| Process | 2050 | CO₂ stored |
|---|---|---:|
| `solid biomass for industry CC` | **240 MW**, 2.10 TWh biomass in, 1.89 TWh to industry | **0.73 Mt** |
| `gas for industry CC` | 481 MW, 4.21 TWh | 0.79 Mt |
| `process emissions CC` | 238 MW | **1.98 Mt** |
| urban central gas CHP CC | 1 048 MW | 0.44 Mt |
| CCGT CC | 463 MW_e | 0.41 Mt |
| **DAC** | **0 links** | 0 |

Industry CC **is already in the LP** and **does run in 2050**. It is a
generic biomass-industry link, not TIMES’s chemicals/lime/glass set, and the
volume (0.73 Mt biomass-CC) is below TIMES’s 4.8 Mt industrial total. Earlier
solves with DAC **on** built a 1.1 GW_e plant, 23.5 TWh_e, **4.39 Mt**
captured at BEWAL — 2.6× the Walloon cap — by pulling more district heat than
buildings used ([ccs_alignment.md](ccs_alignment.md) §8, 18 Aug R10). That is
why DAC was turned off on 25 Aug: to match TIMES’s technology *set*, after it
had eaten the DH bus.

Belgian `co2 sequestered` `e_nom_max = 0` still applies. TIMES stores 7.1 Mt
*in Wallonia*; PyPSA stores 0 in Belgium and fills NL. Volume alignment
without a Belgian sink just moves the CO₂ across the border.

### Options

| | What | Effect |
|---|---|---|
| **A. Turn DAC back on, cap it at TIMES-not-built (= 0)** | pointless | TIMES does not build DAC. |
| **B. Turn DAC on at ~4 Mt** (meeting’s “equivalent level”) | restores the 18 Aug artefact unless DAC is **forbidden** from the DH bus (electricity-only or waste-heat-only) | Closes the *tonnage* gap with a technology TIMES rejected. Do not, unless the study is a DAC sensitivity. |
| **C. Pin industrial CC energy/CO₂ to TIMES** (recommended) | extra-functionality floors on `solid biomass for industry CC` + `process emissions CC` (or a new chemicals-CC link) to ~4.8 Mt in 2050 | Aligns the *industrial* BECCS TIMES actually runs. Needs the Belgian (or priced-export) sink from item 2.C. |
| **D. New labelled industrial processes** | chemicals / lime / glass CC as separate Links | Better TIMES mapping, more engineering. Only if C’s generic pin is too coarse for Explorer. |
| **E. Enable `sector.bioH2`** | biomass → H₂ + CCS | Matches TIMES process `SBIOH2GCC01`, which this vd **does not use**. TIMES’s actual bio-H₂ is black liquor (`BBLQH2G110`), deliberately not exported. Skip. |

### Recommended

**C**, after item 2.C (Belgian CO₂ sink). **Not DAC.** If Explorer needs a
named “industry CCS” series, D is a follow-up. Keep `sector.dac: false` on
demande-haute; a `scen_dac` overlay exists as a one-line scenario switch
([ccs_alignment.md](ccs_alignment.md) §8) for a dedicated study.

Until C, the honest sentence is: “PyPSA has generic industry CC and used it
for 0.73 Mt biomass-CC + 1.98 Mt process-CC in 2050; TIMES has 4.8 Mt of
named industrial capture and 7.1 Mt of Walloon storage PyPSA does not have.”

---

## 10. Add a 3 GW nuclear minimum in Flanders in 2050 (symmetric with Wallonia)

### What the meeting asked

Flanders should have a **3 GW floor in 2050**, symmetric with Wallonia.

### Evidence

Current agg file (`agg_p_nom_minmax_demande_haute.csv`), from
[nuclear-alignment-20260816.md](nuclear-alignment-20260816.md) §3.2 / §4.1:

| 2050 | min | max |
|---|---:|---:|
| BEWAL `nuclear-all` | **3 000** | **3 000** |
| BE `nuclear-all` | **3 000** | **3 000** |
| rest-of-BE after subtraction (BEVLG+BEBRU) | **0** | **0** |

Solved 2050: BEWAL **3 000 MW_e**, BEVLG **0.05 MW_e**. This is doing exactly
what the 16 Aug note decided: *all new nuclear in Wallonia, Flanders to zero
by 2045*, because that is what the Walloon TIMES vd contains. The same note
records the email caveat: *“in reality one large unit might be sited in
Flanders”* — left aside because a BE-wide siting assumption is not in the vd.

Adding a 3 GW Flanders *minimum* is therefore **not a bugfix**. It is a
new Belgian siting policy. Two readings:

| Reading | 2050 Belgium | Meaning |
|---|---|---|
| **Symmetric floors on top of TIMES** | Wallonia 3 + Flanders 3 = **6 GW** | Doubles the vd’s new-build. Needs `BE nuclear-all` max raised to ≥ 6 000. |
| **Split the TIMES 3 GW** | Wallonia ~1.5 + Flanders ~1.5, or 1+2, still **3 GW** Belgium | Matches the email (“one large unit in Flanders”) without doubling. Breaks “follow the vd exactly”. |

Must-run ([nuclear-alignment-20260816.md](nuclear-alignment-20260816.md) §6)
would apply to the new Flemish units: BE band [0.783, 0.883] → ~20–23 TWh
from an extra 3 GW, which **helps item 6** (independence) and Flanders’s
missing 2050 firm capacity.

`add_CCL_constraints` subtracts the region row from the parent country row.
A BEVLG (or rest-of-BE) min of 3 000 with a BE max of 3 000 is **infeasible**.
The BE row must move first.

### Options

| | What | Effect |
|---|---|---|
| **A. New scenario overlay, 3+3 GW** | `scen_nuc_be_6gw`: BEWAL min=max=3000, BEVLG (or BE−BEWAL) min=max=3000, BE min=max=6000 | Clean. Demande-haute stays TIMES-aligned. Explorer can switch. Cost, grid, independence all move. |
| **B. New overlay, split 3 GW** | e.g. BEWAL 2000 + BEVLG 1000, BE = 3000 | Matches the email, not the meeting’s “3 GW in Flanders”. Confirm siting with Elia/ICEDD. |
| **C. Change demande-haute itself** | edit the agg file in place | Silently abandons the 16 Aug TIMES alignment. Do not, unless the vd is re-issued. |
| **D. Free siting, BE total = 3 GW** | drop the regional max, keep BE = 3000 | The 14 Aug bug that put new build in Flanders. The LP will likely put it there again (load, grid). Only if “PyPSA chooses the site” is the new rule. |

### Recommended

**Do not silently edit demande-haute.** Pick A or B in the next ICEDD slot,
as a **named overlay**, and say which Belgium (3 vs 6 GW) is the published
central case.

If the meeting’s wording is taken literally (“3 GW minimum in Flanders,
symmetric with Wallonia”), that is **A = 6 GW Belgium**. That is a different
scenario from the vd and should be labelled as such. It would also be the
single largest independence lever after the onwind cap (item 6).

Implementation path (once decided): master CSV `agg:BEVLG:nuclear-all:min/max`
and `agg:BE:nuclear-all:*`, `--write`, plus a scenario block in
`config/scenarios.walloon.yaml`. The 0.1 MW placeholder plants must stay
above any authored *zero* cap (already guarded in `add_CCL_constraints`).
Rebuild brownfield from 2040 (2030 still has Doel 4).

---

## Sequencing for the next solves

Items 3 and 5 need no code. Item 7 is a labelling/DH-cap decision. The rest
stack:

```
already in tree, not in this solve
  └─ renewable-potentials.md (neighbour offshore, Walloon onwind trajectory)
        │
        ▼
next production solve  ←  measure independence again (item 6.A)
        │
        ├─ item 1  gas store e_nom_max = 0 at BEWAL (+ Loenhout audit)
        ├─ item 8  LV country alias + TIMES rooftop energy share at BEWAL
        ├─ item 2.C / 9.C  Belgian CO₂ sink, then industry-CC pin
        │     (not DAC; not 2040 CCGT-CC floor until the sink exists)
        └─ item 4  only after ICEDD sources 6.9 / 4
        │
        ▼
scenario overlays, not the base
        ├─ item 10  Flanders nuclear (3+3 vs split-3) 
        ├─ item 6.B  Walloon 10 TWh import cap
        ├─ item 2.A  TIMES CCGT-CC MW in 2040 (after sink)
        └─ item 7.B / 5.C  Flemish DH cap
```

**Do not combine the Flanders-nuclear overlay, the 10 TWh import cap, and the
biogas cut in the first re-solve.** Each one moves 2050 independence and the
CO₂ dual; together they will be unreadable. The neighbour-offshore rebuild is
the one change that is already decided and that this run’s 31 TWh import
figure is not comparable without.

---

## Original meeting notes

Kept for traceability.

- vérifier qu'il y a bien du stockage de gaz en wallonie? potentiel?
- CCGT-CC apparait seulement en 2050 => impose the TIMES capacity in 2040?
- no transmission expansion in WAL in 2030 vs 2025? no current plans (review online)
- decrease biogas to 6.9 TWh in 2050 (4 TWh in 2040)
- power-to-heat decreases in flanders: why? to be checked
- energy independance has dropped from the previous run
    => to be checked (model issue?)
    => impose an energy edependance constraint on electricity? TIMES imposes max 10 TWh imports in 2050
- heat demand increases a lot in flander, stable in wallonia. Why?
- no rooftop PV in pypsa => align with TIMES?
       couts de transport
       imposer la part en toiture venant de TIMES?
- BECCS activé dans TIMES (biomass for industry process with CC)
    => activer DAC à un niveau équivalent?
    => nouveau process industriel qui capture le CO2?
- il faut ajouter 3 GW de minimum de nucléaire en flande en 2050 (symétrique avec wallonie)
