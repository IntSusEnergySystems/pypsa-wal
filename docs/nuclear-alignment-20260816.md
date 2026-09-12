# Nuclear alignment with the TIMES vd — scen_demande_haute

**Date:** 2026-08-17 (capacity alignment); 2026-08-25 (must-run / §6); 2026-09-12 (uranium fuel price / §7)
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
6. **Availability CSV is 0.883 for BE, not 1.0 — but until 2026-08-25 it
   did not bind on the solved network.** `data/nuclear_p_max_pu.csv` is
   country-specific (BE 0.883, FR 0.616, GB 0.684, NL 0.901). It is applied
   to **Generators** in `attach_conventional_generators`. Sector-coupling
   then deletes those generators (`pypsa_eur.Generator` does not keep
   `nuclear`) and rebuilds nuclear as **Links**, which inherit PyPSA's
   default `p_max_pu = 1`, `p_min_pu = 0`. The 23.2 TWh/a figure quoted
   here assumed the 0.883 cap; the Aug-14/Aug-17 solves could dispatch
   nuclear at 100 % of nameplate. See §6 for the fix.
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

## 5b. Superseded 2026-09-01: Flanders keeps 3 GW in 2050 (item 10)

The §5 expectation of "2050 BEVLG ≈ 0" is **no longer the design**. The meeting
of 1 September 2026 asked for a symmetric siting policy — 1 GW retrofit + 2 GW
new build in Flanders, mirroring Wallonia — so the trajectory is now:

| Horizon | BEWAL | BEVLG | BE total | authority |
|---|---:|---:|---:|---|
| 2035 / 2040 | 1 030 | 1 000 | 2 030 | the `.vd` (Tihange 3 LTO + Doel 4) |
| 2045 | 1 750 | 1 000 | 2 750 | siting policy: Doel 4 kept so a 2045 solve can still retrofit it |
| 2050 | 3 000 | 3 000 | **6 000** | siting policy, **not** TIMES alignment — the `.vd` has Flanders at 0 by 2045 and doubles to 6 GW Belgium-wide here |

This is a **siting policy, not a TIMES alignment**, and every affected row in
`config/input_parameters_for_models.csv` says so in its `note`. Two mechanical
points that cost a run when they were missed:

- The `BEVLG` rows for 2035/2040/2045 had to be written explicitly. Adding
  `BEVLG` to the caps file aliases that bus out of the `BE` remainder, so a
  2050-only `BEVLG` row would leave Flanders unconstrained in the earlier
  horizons. (This was the *intended* behaviour of the region-row mechanism; the
  *unintended* one it also triggered is
  [`renewable-potentials.md`](renewable-potentials.md) §9.1.)
- The `BE` totals were raised to 2 750 / 6 000 so the `BEVLG` floors are still
  feasible after the CCL remainder subtraction.

Verified on the 2026-09-07 production run: 2 030 MW_e Belgium-wide in 2030 and
2040 (BEWAL 1 030 + BEVLG 1 000), 3 000 + 3 000 MW_e in 2050, every aggregate
row inside its corridor.

**Reminder for reading results:** nuclear links have `bus0` on the EU uranium
bus, so **Walloon nuclear appears nowhere in BEWAL's rows of
`nodal_capacities.csv` / `nodal_costs.csv`** — the whole fleet is booked to
`EU`. Recompute grouped on `bus1`, in MW_e (`p_nom × efficiency`).

## 6. Operational inflexibility (2026-08-25)

**Trigger:** nuclear should be must-run (legacy *and* new-build), not a
flexible thermal plant that can ramp to zero.

### 6.1 What the availability factor actually is

Not 100 %. `conventional.nuclear.p_max_pu` points at
`data/nuclear_p_max_pu.csv` (a flat country factor, no intra-year
profile):

| country | `p_max_pu` |
|---|---:|
| BE | 0.883 |
| NL | 0.901 |
| DE | 0.926 |
| FR | 0.616 |
| GB | 0.684 |
| LU | *not in the CSV* → 1.0 |

On an electricity-only network this derate is on the Generator. On the
sector-coupled network that pypsa-wal actually solves, nuclear is a Link
(`{node} nuclear-{year}`, `{node} nuclear-2025` for new-build,
`… retrofit` for LTO). Until this change those links had `p_max_pu = 1`
and `p_min_pu = 0`: fully flexible, 100 % available. That is why a
hardcoded 90 % floor would have been the wrong number — it would sit
*above* French (and British) availability and make the LP infeasible.

### 6.2 What was wired

`conventional.inflexible_nuclear` in `config/config.walloon.yaml`
(default **off** in `config.default.yaml`, so unmodified PyPSA-Eur is
unchanged):

```yaml
conventional:
  inflexible_nuclear:
    enable: true
    p_min_pu_margin: 0.10
```

`scripts/walloon_scripts/nuclear_helper.py` →
`apply_nuclear_inflexibility`, called at the end of
`add_existing_baseyear`, `add_brownfield` (after retrofits are added) and
`prepare_sector_network` (overnight). For every component whose carrier
starts with `nuclear`:

* `p_max_pu` ← the CSV value for the electricity-bus country (1.0 if the
  country is missing, e.g. LU)
* `p_min_pu` ← `max(0, p_max_pu − p_min_pu_margin)`

The 0.10 is **percentage points**, not 90 % of the capacity factor, and
is an expert-judgement operating band (must-run ≈ 10 pp below the
historical availability). BE therefore runs in [0.783, 0.883], FR in
[0.516, 0.616]. Electrical output is `p_min_pu × p_nom × efficiency`,
so the fraction applies to MW_e as well as to the link's thermal `p0`.

At 3 000 MW_e of Walloon nuclear this caps annual energy at
≈ 0.883 × 8 760 h ≈ 23.2 TWh (vs the vd's 24.44 TWh, same −5 % as in
§4 item 6) and floors it at ≈ 20.6 TWh if the plant sits on its must-run
all year.

### 6.3 How to restore the unconstrained formulation

Do **not** just delete the block. `add_brownfield` copies attributes
from the previous solved network; an absent key is a no-op and the
copied `p_min_pu` would survive. Set the flag to false and rebuild the
brownfield networks (Snakemake retriggers: `conventional` is a param of
`add_existing_baseyear` / `add_brownfield`, and the CSV is an input):

```yaml
conventional:
  inflexible_nuclear:
    enable: false
```

That writes `p_max_pu = 1`, `p_min_pu = 0` on every nuclear **link**
(the previous unconstrained defaults). Generators keep the CSV
`p_max_pu` from `add_electricity`; they are stripped before the sector
solve, so they do not affect results.

Changing `p_min_pu_margin` (or the CSV) likewise retriggers those two
rules. Do not hard-code a 90 % floor in the network: the next country
whose factor is below 0.90 would fail.

## 7. The uranium / nuclear fuel price (2026-09-12)

**Trigger:** R. Capart's remark that TIMES-WAL and PyPSA are not aligned on the
uranium price. The coherence table
(`config/input_parameters_for_models.csv`, rows `Prix de l'uranium`, 2030 /
2040 / 2050) carries **7.4536 EUR2025/MWh_th**, TIMES-WAL carries roughly half
that, and the shortlist circulated to stakeholders in 2025 carried
**3.4122 EUR2011 = 4.6497 EUR2025/MWh_th**. ICEDD has since decided to run
TIMES with the shortlist value and asked for a view on which is better founded.
This section is that view. **No value is changed by this note.**

### 7.1 Confirming the unit and what it costs in the model

Yes — the figure is per **thermal** MWh, and yes, the implied electrical fuel
cost is above 20 EUR/MWh. In pypsa-wal the chain is explicit and was verified
on a solved network (`results/walloon/scen_test_2013_6h/.../2050.nc`):

* `EU uranium` is a Generator with `marginal_cost = costs["uranium","fuel"]`
  = 7.4536 EUR/MWh_th (`prepare_sector_network.py:656`);
* every `<node> nuclear-<vintage>` Link draws from that bus with
  `efficiency = 0.326` and `marginal_cost = efficiency × VOM` = 0.326 × 4.459
  = **1.4945 EUR/MWh_th** (`add_existing_baseyear.py:436`), i.e. 4.459
  EUR/MWh_e of variable O&M.

So fuel and O&M are **not** double-counted, and the short-run marginal cost of
nuclear electricity in the current setup is

| term | EUR2025/MWh_th | EUR2025/MWh_e |
|---|---:|---:|
| uranium (`uranium:fuel`) | 7.4536 | **22.86** |
| variable O&M (`nuclear:VOM`) | 1.4945 | 4.46 |
| **total SRMC** | 8.948 | **27.32** |

Fixed O&M is separate again: `nuclear FOM` 1.27 %/yr on 9 500 EUR/kW =
**120.7 EUR/kW-yr**. Any "fuel" figure adopted here must therefore be a
**fuel-cycle** cost only (front end ± back end) — not an all-in operating cost —
or O&M is counted twice.

### 7.2 The scope trap: "fuel cost" means three different things

This is the main reason published figures span a factor of five.

1. **Front-end fuel cycle only** — uranium ore, conversion, enrichment,
   fabrication. This is the WNA/EIA/NEI convention and the physically
   reconstructible one.
2. **Full fuel cycle** — front end plus back end (interim storage, disposal,
   spent-fuel levy). NEA 2013 puts the back end at roughly half of the total
   fuel-cycle cost.
3. **Merit-order "fuel price"** — market and network models (TYNDP, PLEXOS/
   Antares setups) sometimes load variable O&M and waste levies into a single
   nuclear "fuel price" so the dispatch order is right with one parameter.
   Values in this convention are systematically the highest, and they are the
   ones that will double-count against a model that already carries a VOM —
   which pypsa-wal does.

Every modern techno-economic source reports fuel and O&M separately:
INL 2024 gives fixed O&M 126–216 USD2022/kW-yr and variable O&M
1.9–3.4 USD2022/MWh_e *alongside* its fuel figure; MIT CANES 2024 gives
O&M 12–14 USD/MWh_e alongside 9 USD/MWh_e of fuel; NEI/EUCG report the US
fleet's 2023 actuals as fuel 5.32 + operations 19.38 + capital 7.06 USD/MWh_e.

### 7.3 What the market actually costs today

The World Nuclear Association's worked example (September 2021, 45 GWd/t
burn-up, 1 kg of UO₂ fuel = 1 080 MWh_th) is the standard reconstruction:
8.9 kg U₃O₈ + 7.5 kgU of conversion + 7.3 SWU + fabrication. Re-pricing that
same recipe at the September 2026 market (UxC/TradeTech: U₃O₈ 89.60 USD/lb
spot, 96 USD/lb long-term — an 18-year high; conversion 53–62 USD/kgU;
enrichment 181 USD/SWU long-term, 215 USD/SWU spot):

| priced at | USD/kg fuel | EUR2025/MWh_th | EUR2025/MWh_e |
|---|---:|---:|---:|
| WNA original (Sept 2021, U₃O₈ ≈ 43 USD/lb) | 1 663 | 1.55 | 4.75 |
| Sept 2026 **long-term** contract prices | ≈ 3 950 | **3.16** | 9.68 |
| Sept 2026 **spot** prices | ≈ 4 140 | 3.31 | 10.14 |

Front-end only. Adding a back end at the NEA's order of magnitude (≈ 4
EUR2025/MWh_e for direct disposal at 3 % discount) puts the **full fuel cycle
at today's prices around 4.3–4.5 EUR2025/MWh_th**. This is the single most
important number in this section: the front end has roughly doubled since the
2021 vintage that most catalogues still quote, which is exactly why the
coherence table's figure "felt" too high against older references and yet the
shortlist's figure is *not* too low against current ones.

### 7.4 Summary table — all sources normalised to EUR2025/MWh_th

Normalisation: η = 0.326 (the `nuclear` efficiency actually used, from Lazard's
10.45 MMBtu/MWh_e heat rate); 1 MWh_th = 3.6 GJ; Eurostat HICP EEA chain from
`config/common_parameters_meta.yaml` (2011→2025 ×1.3627, 2021→2025 ×1.2219,
2022→2025 ×1.1190, 2023→2025 ×1.0517); USD→EUR at the source year's average.

| # | Source / scenario | Scope | As published | **EUR2025/MWh_th** | EUR2025/MWh_e |
|---|---|---|---|---:|---:|
| 1 | **pypsa-wal today** — technology-data v0.14.0 `uranium:fuel`, cited to ENTSO-E TYNDP 2024 + EIA 2022 | merit-order "fuel" | 7.4536 EUR2025/MWh_th | **7.45** | 22.86 |
| 2 | **ICEDD shortlist 2025** (IEA 2011 vintage) — the value TIMES runs use | fuel | 3.4122 EUR2011/MWh_th | **4.65** | 14.26 |
| 3 | TIMES-WAL as coded before the shortlist decision | fuel | ≈ half of row 1 | ≈ 3.7 | ≈ 11.4 |
| 4 | ENTSO-E TYNDP 2020, published table (flat 2020–2040) | merit-order "fuel" | 0.47 EUR/GJ | ≈ 2.1 | ≈ 6.5 |
| 5 | WNA worked example, Sept 2021 | front end | 0.46 ¢/kWh_e | 1.55 | 4.75 |
| 6 | WNA recipe re-priced, Sept 2026 long-term market | front end | 3.66 USD/MWh_th | 3.16 | 9.68 |
| 7 | Lazard LCOE+ v17/v18 (2024–2025) | fuel | 0.85 USD/MMBtu (range 0.64–1.06) | 2.75 | 8.44 |
| 8 | NEI / EUCG, US fleet **actuals** 2023 | fuel incl. waste fee | 5.32 USD2023/MWh_e | 1.69 | 5.18 |
| 9 | NEA 2013 back-end study, 3 % discount, large fleet | **full** fuel cycle | ≈ 13 % of 60 USD2010/MWh_e | 2.68 | 8.23 |
| 10 | MIT CANES 2024, AP1000 (BOAK and NOAK alike) | fuel | 9 USD2024/MWh_e | 2.79 | 8.54 |
| 11 | **IEA-ETSAP E03 2026 update** *(explicitly "for TIMES modelling")*, from INL/RPT-24-77048 — large reactors, advanced → conservative | fuel | 9.1 / 10.3 / 11.3 USD2022/MWh_e | **3.15 / 3.57 / 3.91** | 9.67 / 10.94 / 12.00 |
| 12 | idem, SMRs, advanced → conservative | fuel | 10.0 / 11.0 / 12.1 USD2022/MWh_e | 3.46 / 3.81 / 4.19 | 10.62 / 11.68 / 12.85 |
| 13 | IAMs — REMIND, MESSAGEix-GLOBIOM | endogenous | no exogenous price: shadow price of a graded uranium extraction curve | *(low; not directly comparable)* | — |

Row 13 deserves a sentence rather than a number. IAMs do **not** carry an
exogenous uranium price at all: REMIND derives primary-fuel costs as the shadow
price of the primary-energy balance, and MESSAGEix-GLOBIOM resolves uranium
through graded resource/extraction cost curves (GEA lineage, benchmarked
against crustal and known-conventional-resource supply curves), with an
explicit fuel-cycle and reprocessing representation. Because the sub-130 USD/kgU
resource category is large relative to any plausible IAM nuclear build-out, the
resulting uranium shadow price stays near the bottom of the range above for
essentially all of the century in mitigation scenarios. **IAMs are therefore
not a useful anchor for choosing a number here** — they are evidence that the
fuel term is not a binding economic driver, which is the opposite of what a
7.45 EUR/MWh_th assumption implies.

### 7.5 Row 1 does not reconcile with its own stated sources

Three independent checks say the coherence table's 7.4536 is an outlier, not a
newer and better estimate:

* **Against the physics.** EIA's own 2022 datum — the source the cell cites —
  is a weighted-average purchase price of **39.08 USD/lb U₃O₈** by US civilian
  reactors. Run through the standard fuel-cycle recipe with 2022 conversion,
  SWU and fabrication prices, that yields ≈ 1.5 EUR2025/MWh_th, not 7.45.
* **Against TYNDP's own published table.** 7.4536 EUR2025/MWh_th = 6.10
  EUR2021/MWh_th = **1.694 EUR2021/GJ**. TYNDP 2020's published nuclear price
  is **0.47 EUR/GJ**, flat from 2020 to 2040 — a factor 3.6 apart.
* **The factor is suspiciously exactly 3.6.** `0.47 × 3.6 × 3.6 × 1.2219 =
  7.443`, which reproduces 7.4536 to within 0.14 % (exactly, for a source value
  of 0.4707 EUR/GJ). The row's own `further description` reads *"3.6 GJ/MWh"*.
  The most parsimonious reading is that the **GJ→MWh conversion was applied
  twice** in the upstream catalogue, and that the intended value is
  `7.4536 / 3.6 = ` **2.07 EUR2025/MWh_th** (6.35 EUR2025/MWh_e) — which lands
  squarely inside the cluster of rows 4–10.

This last point is a strong hypothesis, not a verified fact: it rests on
TYNDP 2024 having kept TYNDP 2020's nuclear price, which I could not confirm
because the cited `Prices.zip` is not readable through a web fetch. It is worth
five minutes with that file before the next parameter round, and worth an
upstream issue on `PyPSA/technology-data` if it holds. The same check on the
`coal` row does *not* show the pattern (1.78 EUR2021/GJ vs TYNDP 2020's 3.12),
so this is specific to the nuclear row, not a systematic archive problem.

### 7.6 Recommendation

**Adopt the shortlist value, 4.6497 EUR2025/MWh_th, flat over 2030–2050 — i.e.
align pypsa-wal down onto TIMES rather than TIMES up onto pypsa-wal.**

Reasons, in order of weight:

1. **7.4536 is outside every independent estimate**, by a factor 1.9 against
   the highest of them (row 12, the conservative SMR case) and by a factor 4–5
   against the observational ones (rows 5, 8). It also fails to reconcile with
   the two sources it cites (§7.5). It should not be defended in front of the
   cabinet.
2. **4.65 is inside the range, at its upper edge.** It sits just above the
   IEA-ETSAP/INL band of 3.15–4.19 EUR2025/MWh_th — the band produced by the
   one source in this list that was written *for TIMES models* — and just above
   the ≈ 4.3–4.5 that today's long-term uranium and SWU prices give for a full
   front-end-plus-back-end cycle (§7.3). Being at the upper edge is the right
   place for a 2030–2050 assumption made in a market at an 18-year price high,
   with enrichment capacity the acknowledged bottleneck.
3. **Its 2011 vintage is not the problem people assume.** Inflation-corrected,
   4.65 EUR2025 happens to coincide with what the 2026 market and the 2024
   INL/MIT literature give. The shortlist is old but not wrong; row 1 is recent
   but not right.
4. **Soft-link consistency is the point of the exercise.** TIMES runs are going
   out with 4.6497. A 60 % higher uranium price on the PyPSA side would show up
   as a divergence in system cost and in nuclear's contribution to the Walloon
   electricity price that has nothing to do with any modelling difference worth
   reporting.

Consequences if adopted, for the record:

| | current | recommended |
|---|---:|---:|
| `uranium:fuel` | 7.4536 EUR2025/MWh_th | 4.6497 EUR2025/MWh_th |
| fuel cost of nuclear electricity | 22.86 EUR/MWh_e | 14.26 EUR/MWh_e |
| SRMC incl. `nuclear:VOM` (4.459) | **27.32 EUR/MWh_e** | **18.72 EUR/MWh_e** |
| Walloon nuclear fuel bill, 2050 (≈ 23.2 TWh_e, §6.2) | ≈ 530 M EUR/yr | ≈ 331 M EUR/yr |

So the change is worth about **−200 M EUR/yr on the Walloon fleet alone** in
2050, and roughly double that Belgium-wide once Flanders' 3 GW (§5b) is
counted. That is a material line in any system-cost or LCOE comparison with
TIMES.

**Sensitivity to carry, if a range is wanted:** low 2.1 (TYNDP-style bare fuel
price, row 4 / §7.5 corrected value), central 4.65, high 7.45 (the current
value, retained as the upper bound rather than as the reference).

**Where the change would go** (not applied here):
`config/input_parameters_for_models.csv`, the three `Prix de l'uranium` rows —
`value` 7.4536 → 4.6497, `source`/`description_complementaire` retagged to the
shortlist and to this note, `data_origin_choice` `PyPSA` →
`Revue de littérature`, `note_complementaire` recording that the row now
overrides technology-data v0.14.0 — then
`python scripts/build_common_parameters.py --write`. Note that
`cost:nuclear:fuel` is the PyPSA target, but the value that actually reaches
the network is `costs["uranium","fuel"]` (§7.1): check that
`data/walloon/custom_costs.csv` ends up carrying a `uranium / fuel` row and not
only a `nuclear / fuel` one, or the override will be silently inert.

**One caveat to state alongside the recommendation.** Because nuclear is
must-run (§6) and its capacity is pinned by the CCL corridors (§3.2, §5b), the
uranium price in pypsa-wal is mostly an **accounting** parameter: it moves
total system cost and the reported cost of Walloon electricity, but it changes
dispatch only within the narrow `[p_min_pu, p_max_pu]` band and in the hours
where nuclear sets the price. Do not expect the re-run to redistribute
capacity. This also means the change is cheap to make and safe to make late.

**Sources.**
[World Nuclear Association — Economics of Nuclear Power](https://world-nuclear.org/information-library/economic-aspects/economics-of-nuclear-power) ·
[IEA-ETSAP E03 2026 update — Nuclear Power in TIMES Modelling](https://iea-etsap.org/wp-content/uploads/2026/05/32.-IEA-ETSAP-2026-eTech-Brief-E03-2026-Update-Nuclear-Power-in-TIMES-Modelling.pdf) ·
[NEI — Nuclear Costs in Context](https://www.nei.org/resources/reports-briefs/nuclear-costs-in-context) ·
[Lazard LCOE+ June 2024](https://www.lazard.com/media/xemfey0k/lazards-lcoeplus-june-2024-_vf.pdf) ·
[NEA (2013) — The Economics of the Back End of the Nuclear Fuel Cycle](https://www.oecd-nea.org/upload/docs/application/pdf/2019-12/7061-ebenfc-execsum.pdf) ·
[ENTSO-E/ENTSOG TYNDP 2020 — Fuel Commodities and Carbon Prices](https://2020.entsos-tyndp-scenarios.eu/fuel-commodities-and-carbon-prices/) ·
[ENTSOs TYNDP 2024 Scenarios — downloads](https://2024.entsos-tyndp-scenarios.eu/download/) ·
[EIA — Uranium Marketing Annual Report](https://www.eia.gov/uranium/marketing/) ·
[UxC — Nuclear Fuel Price Indicators](https://www.uxc.com/p/price) ·
[MESSAGEix-GLOBIOM — nuclear resources](https://docs.messageix.org/projects/models/en/stable/global/energy/resource/nuclear.html) ·
[IAMC documentation — Uranium and other fissile resources, MESSAGE-GLOBIOM](https://www.iamcdocumentation.eu/index.php/Uranium_and_other_fissile_resources_-_MESSAGE-GLOBIOM)
