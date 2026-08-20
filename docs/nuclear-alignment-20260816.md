# Nuclear alignment with the TIMES vd — scen_demande_haute

**Date:** 2026-08-17
**Scenario:** `scen_demande_haute` (`config/config.times-pypsa.yaml` +
`config/scenarios.walloon.yaml`)
**TIMES run:** `scen_demande_haute_v01_260727_fix_nuc_2807.vd`
(s3://intervectoriel/test/scenarios/times_20260727/, R. Capart email 2026-07-28)
**Trigger:** the 2026-08-14 solve
([log](logs/2026-08-14_scen_demande_haute_2010_1h.md)) ran with a nuclear
fleet *not* aligned with this vd. This note extracts the vd trajectory, shows
the misalignment, and records the fixes and the choices made.

---

## 1. What the vd says (extracted 2026-08-17, `VAR_Cap`/`VAR_Ncap`/`VAR_FOut`)

TIMES-WAL represents nuclear as: `ELCNUC00` (Tihange 1+2+3 heat output, PJ),
converted by `ENUC_Thiange` (η ≈ 0.336, so its `VAR_FOut` ≈ Tihange
electricity) until 2035, then by `ETSTP_Tihange_retrofit_N`; plus two new-build
processes `ETSTP_NUC-LWR-SM_NUC_N` (SMR) and `ETSTP_NUC-LWR-GEN3_NUC_N`
(large Gen3). Wallonia only — Flanders is not in the Walloon TIMES model.

| GW_el | 2021 | 2025 | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Tihange (existing → retrofit) | 3.145 | 2.075 | 1.113 | 1.113 | 1.045 | 1.045 | 1.045 |
| SMR new (cumulative) | — | — | — | — | — | 0.25 | 1.0 |
| large Gen3 new (cumulative) | — | — | — | — | — | 0.5 | 1.0 |
| **total** | 3.145 | 2.075 | 1.113 | 1.113 | 1.045 | **1.795** | **3.045** |

`VAR_Ncap`: retrofit 1.045 invested at 2040 and **again** at 2050 (the repeat
Raphaël describes — vd writes the 2045 reinvestment into the 2050 period);
SMR 0.25 (2045) + 0.75 (2050); Gen3 0.5 (2045) + 0.5 (2050). Output 2050:
8.24 + 8.32 + 7.88 = 24.44 TWh (≈ 7 900–8 320 FLH per unit).

## 2. What PyPSA solved on 2026-08-14 (MW_el = link `p_nom` × 0.326)

| Horizon | BEWAL | BEVLG | BE total | vd expectation (BEWAL) |
|---|---:|---:|---:|---:|
| 2025 | 1 992 (TH1 962 + TH3 1 030) | 1 890 | 3 882 | 2 075 ✓ (vintage mix differs, total close) |
| 2030 | 1 030 (TH3) | 1 000 (Doel 4) | 2 030 | 1 113 ✓ (+ Doel 4, correct BE-wide) |
| 2040 | 1 030 (retrofit #1 full) | 1 000 (retrofit full) | 2 030 | 1 045 + Doel 4 LTO ✓ |
| 2050 | 1 030 (retrofit #2 full), **new build 0** | retrofit #2 1 000 + **new 1 000** | 3 030 | **3 045 — all in BEWAL** ✗ |

Two defects:

1. **New nuclear went to Flanders, not Wallonia.** The agg caps file left
   `BEWAL nuclear-all` as a range [1 000, 3 000] with the BE total fixed at
   3 000, so the LP sited the 2 GW of new build in BEVLG while keeping the
   Doel 4 retrofit alive — the exact opposite of the vd (new build in
   Wallonia, Doel 4 retired after 2045, Flanders at 0 by 2050).
2. **The link maxima never applied.** `add_CCL_constraints`
   (`scripts/solve_network.py`) computed `maximum_links` from `rhs_links` —
   a leftover of the *minimum* computation — so every nuclear/CCGT link cap
   in the file was silently enforced as a second minimum (or nothing). That
   is why BE could land at 3 030 with a 3 000 cap on the books. The bug is
   invisible in 2025/2030 (those columns carry no link maxima) and only the
   BE nuclear rows ever carried authored link maxima, so no other scenario
   result is affected retroactively.

## 3. Fixes (2026-08-17)

### 3.1 `scripts/solve_network.py` — `add_CCL_constraints`

* The links maximum now uses the `max` column, mirroring the min branch:
  `rhs_max_links − existing_non-extendable`, i.e. the cap applies to the
  **total** capacity (extendable + existing), as the min already did.
* A cap can never bind below the variable lower bounds — brownfield links
  carry `p_nom_min > 0` (the 0.01 MW_e placeholder "New" plants and retrofit
  links at 0.1 MW_u) — so the effective cap is raised to the group's
  `Σ p_nom_min × efficiency` when the authored value would sit below it.
  Without this guard, the "rest-of-Belgium = 0 GW in 2050" cap would make
  the LP infeasible by 0.05 MW_e. Generator maxima keep their historical
  (upstream pypsa-eur) semantics of *not* subtracting existing capacity;
  only the link path was corrected.
* Non-BE nuclear rows in the caps file carry **minima only** (re-checked:
  every non-BE `nuclear-all` max cell is empty), so this fix changes no
  foreign-country result: FR/GB/NL 2030–2050 all sat exactly on their minima
  in the Aug-14 solve and remain feasible under the corrected maximum.

### 3.2 `data/walloon/agg_p_nom_minmax_demande_haute.csv` — nuclear rows

Caps in MW_e on the **total** per region. Authored in
`config/input_parameters_for_models.csv` (`agg:BEWAL:nuclear-all:*` /
`agg:BE:nuclear-all:*`) and pushed into this file by
`scripts/build_common_parameters.py --write`. The BE row is authored as
`BEWAL + rest-of-BE` because `add_CCL_constraints` subtracts a region row
from its parent country row, leaving the BE row to constrain BEVLG+BEBRU:

| year | BEWAL [min, max] | rest-of-BE after subtraction | BE authored |
|---|---|---|---|
| 2035 | [1000, 1030] | [1000, 1000] | [2000, 2030] |
| 2040 | [1000, 1030] | [1000, 1000] | [2000, 2030] |
| 2045 | [1750, 1750] | [0, 0] | [1750, 1750] |
| 2050 | [3000, 3000] | [0, 0] | [3000, 3000] |

Reading: 2035/2040 = the LTO state (Tihange 3 retrofit 1.03 GW in Wallonia +
Doel 4 1.0 GW in Flanders, no new build anywhere); 2045 = vd's 1.75 GW
(Tihange 1.0 + SMR 0.25 + large 0.5) **all in Wallonia**, Doel 4 retired;
2050 = vd's 3.0 GW (Tihange 1.0 second retrofit + SMR 1.0 + large 1.0) all in
Wallonia. 2025/2030 stay empty — the legacy fleet already reproduces the vd.

## 4. Choices made (and their justifications)

1. **All new nuclear in Wallonia, Flanders to zero by 2045.** The Walloon
   TIMES vd attributes the 2045/2050 new builds to Wallonia (that is what
   "aligning with the vd" means for this soft-link). The email itself notes
   that in reality one large unit might be sited in Flanders — a BE-wide
   free siting would need an Elia-side assumption the vd does not contain.
   Chosen: follow the vd exactly.
2. **One new-build technology, not SMR vs Gen3.** PyPSA has a single
   `nuclear` carrier at 9 500 EUR/kW_e (`data/walloon/custom_costs.csv`);
   no SMR-specific investment cost exists in the common parameter table.
   The 1 GW + 1 GW 2050 new build is therefore costed uniformly. If an SMR
   cost is agreed later, the SMR share (1.0 of the 2.0 GW new build) can be
   split out.
3. **Tihange capacity 1 030 MW_e in PyPSA vs 1.045 GW in TIMES.** Plant-data
   vintage rounding (TH3 1 030 gross in `wal_2021_existing_capacities_2.csv`
   vs vd's 1.045). Consequence: 2050 BEWAL = 3 000 instead of 3 045 MW
   (−1.5 %). Accepted; recorded here.
4. **Second retrofit at the same cost as the first** (1 800 EUR/kW, 10 y —
   `nuclear retrofit` in `custom_costs.csv`). The email flags that the vd
   itself reuses the one-shot LTO cost for the 2045 reinvestment ("les coûts
   sont peut-être plus grands pour prolonger au-delà"). PyPSA mirrors the vd
   simplification so the two models stay comparable; flagged for the next
   parameter round.
5. **2045 is not a solved horizon** (myopic chain 2025–2030–2040–2050). The
   2045 caps column is inert in this chain but is authored so a future 2045
   run inherits the correct intermediate state (new build 720 MW = 1 750 −
   1 030 existing retrofit).
6. **Availability stays 0.883 flat** (`data/nuclear_p_max_pu.csv`). At
   3 000 MW_e this yields ≈ 23.2 TWh/a vs the vd's 24.44 TWh (FLH 7 900–
   8 320 h). ≈ −5 % energy at the aligned capacity; not material for the
   capacity alignment itself.
7. **Re-solve scope: 2040 and 2050 only.** 2025/2030 carry no nuclear caps
   and no link maxima, and the corrected maximum leaves their optima
   feasible and optimal (verified numerically against the solved networks:
   every non-BE group sits exactly on its *minimum*). Re-solving them would
   reproduce the same .nc.

## 5. Verification of the re-solve (to fill after the run)

| check | expected |
|---|---|
| 2040 BEWAL nuclear | = 1 030 MW_e (retrofit #1 full), no new build |
| 2040 BEVLG nuclear | = 1 000 MW_e (Doel 4 retrofit), no new build |
| 2050 BEWAL nuclear | = 3 000 MW_e (retrofit #2 1 030 + new ≈ 1 970) |
| 2050 BEVLG+BEBRU nuclear | ≈ 0 (placeholders only, ≤ 0.1 MW_e) |
| 2050 FR/GB/NL | unchanged vs Aug-14 (mins binding as before) |
| objectives 2025/2030 | bit-identical networks reused, not re-solved |
