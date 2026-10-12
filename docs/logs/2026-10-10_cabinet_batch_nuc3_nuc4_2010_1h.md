# Cabinet batch — 3 GW / 4 GW nuclear scenarios (1 h, weather 2010)

**Status (11 Oct 2026): SOLVED on 10 Oct (40 of 40 horizons optimal, NIC5 + NIC6), pulled and post-processed 10–11 Oct, published
to the internal sites on 11 Oct (§9.4), critical review in §11. Read §11 before pointing anyone at the published pages.**

*Originally:* PREPARED 2026-10-10. The PyPSA side was ready: code, scenario blocks, generated data files and tests.

**Decisions of 10 Oct (S. Quoilin):**
* capture cap **on** in the central (§3);
* nuclear costs **kept** (9 500 €/kW, §4.3);
* S2 at **3 962 MW** in 2050 (§4.1);
* `scen_test_lowccs_ptx` **kept** in the batch.

**Launch decided on 10 Oct with the exports available now:**
* every scenario reads a 2 Oct export (`scen_realiste`: 30 Sep);
* the four new ones read their S1 counterpart's as a **placeholder** (§1);
* ICEDD's later exports go in scenario by scenario (§5b).

**Where and how:** 1 h, from the **office computer**, solves split between **NIC5 and NIC6**. The
runbook is **§5**.

**Process-emissions load corrected on 10 Oct** (§3.1): from 2035 it now holds the process CO₂ only;
the captured fuel CO₂ is gone. Local **6 h feasibility tests** are in §10.

The file is named after the preparation day. Rename it to the launch date if the solve starts later.

**Predecessor:** [`2026-10-06_scen_central_2010_1h_noroute_biogas.md`](2026-10-06_scen_central_2010_1h_noroute_biogas.md),
the 6 Oct central (route closed, ICEDD biogas cap). Its §11 R1 explains why CCGT CC sits at the margin
in 2040, which matters for §3.

---

## 0. What is different from the 6 Oct central (read first)

1. **The 4 GW family: three new scenarios.**
   * They are the 3 GW ones plus **Tihange 1** restarted from 2035, which is 2040 on the 10-year grid.
   * The restart is priced at the Tihange 3 extension cost.
   * It is a new code path, `electricity.nuclear_restart` (§4.1).
2. **New nuclear (EPR) lives 60 years, not 40**, in every scenario (§4.2).
   * In pypsa-wal this changes the annualised fixed cost only: −3.7 %, from 875 to 843 kEUR/MW_e/a.
   * The foreign existing fleets are protected from the side effect by
     `existing_capacities.fill_lifetime`.
3. **Cap on all CO₂ captured in Wallonia**, `sector.co2_capture_limit`, ON in the base config, so
   every scenario inherits it (§3).
   * TIMES's 2 / 6 / 8 Mt, with a 1 000 €/t overage valve.
   * The volumes are recorded in the convergence table as `config:sector.co2_capture_limit.kt`.
4. **`scen_noco2cap`** is new: the internal "pas de contrainte CO₂" sensitivity (§2, item 8).
5. **`run.name` holds the cabinet's 9 runs plus `scen_test_lowccs_ptx`** (§1).
   `scen_noccsccgt_route` is no longer run; its block stays in the scenarios file.
6. **`ptx_report.py` now also reports** total capture, the capture cap, its dual and the overage.

The cap is tested at 6 h on the central only (§10). The 4 GW restart has not been solved.

---

## 1. The scenarios

Cabinet's frame (A. Dubois, 7 Oct; confirmed 8 Oct): two scenarios **on an equal footing**, each
with two report sensitivities, plus four internal runs on S1 only.

| # | scenario | role | PyPSA delta vs `scen_central` | `.vd` it reads today | TIMES export needed |
|---|---|---|---|---|---|
| 1 | `scen_central` | **S1 3 GW**, report | — | `scen_central_v01_261002_0210.vd` | S1 central re-export (new lifetime / CCS settings) |
| 2 | `scen_biomethane_industrie` | S1 sensitivity, report | none (TIMES side only) | `…biomethane_industrie_v01_261002_0210.vd` | re-export |
| 3 | `scen_noccsccgt` | S1 sensitivity, report | BEWAL power CC (CCGT, gas CHP, biomass CHP) at 0 MW | `…central_noccsccgt_261002_0210.vd` | re-export |
| 4 | `scen_nuc4gw` | **S2 4 GW**, report | nuclear rows + Tihange 1 (§4.1), restart on | **placeholder** = #1's | **new** 4 GW central |
| 5 | `scen_nuc4gw_biomethane_industrie` | S2 sensitivity, report | as #4 | **placeholder** = #2's | **new** |
| 6 | `scen_nuc4gw_noccsccgt` | S2 sensitivity, report | as #4 + as #3 | **placeholder** = #3's | **new** |
| 7 | `scen_realiste` | internal | 2030 PV/wind caps, BE 2030 floors and caps lifted (unchanged) | `…realiste_260929_3009.vd` (30 Sep) | re-export |
| 8 | `scen_retardnucleaire` | internal | BEWAL nuclear = Tihange 3 only in 2045–2050 (unchanged) | `…retardnucleaire_261002_0210.vd` | re-export |
| 9 | `scen_noco2cap` | internal | Belgian national CO₂ caps lifted 2030–2050 (§2, item 8) | **placeholder** = #1's | **new** |
| 10 | `scen_test_lowccs_ptx` | test, not cabinet | central + lever D (net export ≤ 3 Mt from 2040, 500 €/t) + floor off; inherits the capture cap, which now binds in 2040 too | central's, by design | none (follows the central) |
| — | PEB A | internal | none on the PyPSA side (demand from TIMES) | — | **new**, ICEDD to build it; "en suspens" (cabinet, 8 Oct) |

**How to read the pairs:**

| difference | isolates |
|---|---|
| `scen_nuc4gw` − `scen_central` (and the two sensitivity pairs) | Tihange 1, alone: the new build is identical (§4.1) |
| `scen_noccsccgt` − `scen_central` | the ban on power-plant capture |
| `scen_biomethane_industrie` − `scen_central` | the TIMES biomethane allocation (PyPSA side identical) |

---

## 2. What the e-mails and the 8 Oct meeting decided

Sources:
* the "Statut avancement" thread (N. Bidoul 6 Oct; A. Dubois 7 and 8 Oct; J. Simon 6, 7 and 8 Oct);
* your notes of the 8 Oct meeting.

Nothing on these points has arrived since (inbox checked 10 Oct).

| # | item | decision | PyPSA implementation | status |
|---|---|---|---|---|
| 1 | Scenario frame | S1 3 GW and S2 4 GW, equal footing; each with "biométhane industrie" and "sans CCS sur CCGT" → 6 report runs | §1 | done |
| 2 | CCS on CCGT | "actif par défaut à partir de 2040" in both scenarios. The parameters must let it appear, and the lever used must be stated in the annex | Allowed in every horizon (unchanged). The 6 Oct central built 0.98 GW_e in 2040 unforced, **exactly at the margin** (6 Oct R1). Nothing forces it. See §3 for the conflict with the capture cap | **at risk**, §8 Q2 |
| 3 | Tihange 1 | Back in 2035 per the e-mails, 2036 per your notes; no capacity in 2030. Cost = Tihange 3 extension, 10 years renewable | `nuclear_restart`, `from_year: 2035` → offered in 2040 on the 10-year grid (both readings give 2040) | done |
| 4 | Reactor lifetime | Cabinet: 80 years (TIMES side, "en débat") | Your decision of 8 Oct: **new nuclear 60 years** in PyPSA | done (§4.2) |
| 5 | Nuclear cost | Cabinet: use the SPF figures (8 Oct). ICEDD prefers the current ones (J. Simon, 7 Oct) and is uneasy about it (8 Oct) | **Kept at 9 500 €/kW** (decision of 10 Oct). SPF values recorded in §4.3 | decided |
| 6 | CCS alignment | Your notes: "tout ce qui est capturé" 2 / 6 / 8 Mt (2030 / 40 / 50); PyPSA has no such limit | `sector.co2_capture_limit`, **ON** in the base config (decision of 10 Oct, §3) | decided; 6 h test §10 |
| 7 | Internal sensitivities | Réaliste 2030, retard nucléaire (Tihange 3 only in 2050), PEB A (suspended), no CO₂ constraint | Blocks 7–9 of §1 | done, except PEB A |
| 8 | "Pas de contrainte CO₂" | Lift the 2030 / 2040 / 2050 caps, keep ETS1 / ETS2 prices (Antoine: OK). Antoine also suggests the AEA fines | PyPSA has no exogenous ETS price (`co2_price_national: false`). The analogue is to keep the system-wide `co2_budget`, so Wallonia pays the endogenous European carbon price (6 Oct: 93 / 113 / 654 €/t), and lift the three Belgian national caps (to 1.0, as `scen_realiste` does for 2030). **Not TIMES's experiment in 2050**, where the system price is far above any ETS projection. AEA fines are not modelled | done; caveat in the block |
| 9 | Analytical questions | Explain the no-CCS result through production, not capacities; thermal storage 25 → 105 GWh; network-cost charts | Not batch inputs | — |

---

## 3. A cap on Walloon CO₂ capture: would it change much? Could it be infeasible?

### 3.1 The two models today

**TIMES-WAL, 2 Oct central** (`VAR_FOut` of `ELCCO2c` / `INDCO2c` into `CO2STOCK`, then
`CO2STG01`, RW), in Mt/a:

| | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|---:|
| industry (`STORAGEMININD`) | 0 | 2.54 | 4.15 | 5.15 | 5.12 |
| power (`STORAGEMINELC`, CCGT CCS retrofit) | 0 | 0 | 1.85 | 1.85 | 1.86 |
| **total stored** | **0** | 2.54 | **6.00** | 7.00 | **6.98** |
| `CO2STG01` bound | 0 | 4 | **6 (binding)** | 7 (binding) | 8 |

* The "2 / 6 / 8 Mt" of the meeting are the **bounds**, not TIMES's result.
* **The 2030 value of 2 Mt is new.** The bound was 0 in the 2 Oct export, so it presumably comes
  with ICEDD's next export. Confirm (§8 Q1).

**PyPSA, 6 Oct central** (`ptx_report.csv`, BEWAL capture by technology), in Mt/a:

| | 2030 | 2040 | 2050 |
|---|---:|---:|---:|
| process emissions CC | 1.28 | 5.16 | 4.86 |
| gas for industry CC | 0 | 1.65 | 0.53 |
| solid biomass for industry CC (BECCS) | 0 | 1.82 | 1.82 |
| CCGT CC | 0 | 1.94 | 0.76 |
| urban central gas CHP CC | 0 | 0 | 0.45 |
| **total** | **1.28** | **10.56** | **8.41** |
| against a 2 / 6 / 8 Mt cap | slack (−0.7) | **+4.56 (+76 %)** | +0.41 |

**Where the 2040 gap came from: process CO₂ (fixed on 10 Oct).**
* The PyPSA process-emissions load was **5.43 Mt** in 2040: the 3 Sep export's 357 kt emitted plus
  **all** 5 077 kt of `INDCO2c`. The CC link captures 95 % of it.
* Part of `INDCO2c` is **fuel** CO₂ that the cement kilns and oxy-fuel furnaces capture, booked as
  a negative `INDCO2N` (1.38 Mt of 4.15 in the 2 Oct central's 2040, mostly biogenic).
  * In PyPSA that CO₂ comes from the industrial fuel demand and its capture from
    `solid biomass / gas for industry CC`.
  * So it was counted twice: 1.2–1.6 Mt/a of phantom fossil process CO₂ from 2035.
* **Corrected load** (2 Oct central; the same to 0.3 % in every 2 Oct export):

  | kt/a | 2025 | 2030 | 2035 | 2040 | 2045 | 2050 |
  |---|---:|---:|---:|---:|---:|---:|
  | load | 4 412 | 3 946 | 3 873 | 3 875 | 3 884 | 3 880 |

  * Derivation and guards: `docs/ccs_alignment.md` §11.1,
    `extract_times_softlink_values.process_emissions_breakdown`,
    `test_process_emissions_load.py`.
* **Process capture now tops out at 0.95 × 3 875 = 3.68 Mt in 2040.** That leaves 2.3 Mt under
  the 6 Mt cap for BECCS, industrial fuel CC and CCGT CC, against 0.8 Mt before.

### 3.2 What a 2 / 6 / 8 Mt cap would do (expectations, not solved)

**2030: nothing.** PyPSA captures 1.28 Mt, under the cap.

**2040: a large change.** (Written before the 10 Oct load correction; §10 has both 6 h tests.)
* **About 4.6 Mt of capture must go.**
  * Process CC (5.16 Mt) is the cheapest tonne to keep: its alternative is venting a fixed load.
    That leaves about 0.8 Mt for every other capture route (2.3 Mt after the correction).
  * **CCGT CC (1.94 Mt) and gas-for-industry CC (1.65 Mt) go first.** BECCS (1.82 Mt) competes for
    the rest.
* **The tonnes must be abated another way**, under a Walloon cap of 6.84 Mt that already binds
  (dual −19.5 €/t), with the import cap (6.47 TWh) and no DAC or vent.
* **Nearest analogue: the 5 Oct lever-D test** (net export ≤ 3 Mt; 4 Oct batch log §12).
  * In 2040: Walloon cap dual −251 €/t, objective +1.07 bn€, CCGT CC 0, ground PV 6.5 GW, batteries
    3.6 GW.
  * Its 4 Mt of local fuel synthesis would **not** relieve a capture cap, because local use counts
    as capture. So expect a dual of the same order or higher.
* **Direct conflict with the cabinet's request (item 2).** With the cap, CCS on CCGT is the first
  thing the model drops in 2040. TIMES keeps 1.85 Mt of power CCS under the same 6 Mt only because
  its industrial capture is 1 Mt lower (§3.1).

**2050: small in tonnes, not in value.**
* About −0.4 Mt.
* The national cap is slack, so a tonne is worth the system CO₂ price (654 €/t). Order of
  magnitude: 0.1–0.3 bn€ on the objective; the plant mix barely moves.

### 3.3 Feasibility

* **Hard cap.** Not guaranteed in 2040. The cap stacks on three other hard limits:
  * the Walloon 6.84 Mt cap;
  * the import cap;
  * a fixed process-emissions load whose only outlets are venting or capture.

  A hard infeasible LP does not stop: it **hangs** in the IIS (instructions.md, Troubleshooting).
* **As shipped:** `overage_price: 1000` €/t. Tonnes above the cap are allowed at that price, so the
  row **cannot make the LP infeasible**. A non-zero overage in a solved network means the cap binds
  harder than the valve.
  * The valve must be above every carbon price where the cap should bind. 654 €/t is the system
    CO₂ dual in 2050, so lever D's 500 €/t would simply be paid there.
* **Floor above cap.** The TIMES industrial capture floor is a subset of what the cap counts.
  * Central floor 4.15 / 5.12 Mt, noccsccgt 5.16 / 5.36 Mt (2040 / 2050): all below 6 / 8 Mt.
  * The solve raises an error before Gurobi if a floor ever exceeds the cap.
* **The re-exports may move both numbers.** Check floor ≤ cap again once they land (§5b step 4).

### 3.4 Decision (10 Oct): on, in the central configuration

The cap is `enable: true` in `config/config.walloon.yaml`, so **every scenario inherits it**,
including `scen_test_lowccs_ptx`.
* Each sensitivity therefore stays a one-change delta on the central.
* `test_co2_capture_limit.py` fails if a batch block opts out.
* A scenario can still opt out with `sector: co2_capture_limit: enable: false`. It is a solve-time
  key, so no re-prepare is needed.

**Convergence table.** The volumes are recorded in `config/input_parameters_for_models.csv` as
`config:sector.co2_capture_limit.kt`: 2 000 / 4 000 / 6 000 / 7 000 / 8 000 kt for
2030 / 35 / 40 / 45 / 50, origin TIMES.
* `build_common_parameters.py` does not patch a per-horizon mapping.
* The same test keeps config and table equal.

**Still recommended:**
* tell the cabinet that CCS on CCGT in 2040 now depends on what fits under the cap (§3.2, §10).
* The process-emissions load was corrected on 10 Oct (§3.1).

**Implementation:**
* `named_pins.add_co2_capture_limit` counts every capture port into `BEWAL co2 stored` (industry,
  power, CHP, SMR CC, DAC), whatever happens to the CO₂ next.
* It shares `captured_co2_expr` with the disposal-route guard; that function was refactored out of
  `add_co2_disposal_own_capture` and behaves the same.
* Dual: GlobalConstraint `co2_capture_limit_BEWAL`.
* Tests: `test/test_co2_capture_limit.py` (9).

---

## 4. Nuclear

### 4.1 S2 = S1 + Tihange 1

**Why code was needed.** Tihange 1 (962 MW_e, `wal_2021_existing_capacities_2.csv`) retires in the
2025 step, so its link no longer exists in 2040. `retrofit_retired_nuclear` only extends a plant in
the step where it retires, so it cannot restart Tihange 1. Without new code the 2 GW floor would be
filled by **new build at 9 500 €/kW**.

**`nuclear_helper.restart_retired_nuclear`**, called in `add_brownfield` after the retrofit:
* adds one extendable `nuclear` link, `BEWAL nuclear Tihange 1 restart`, capped at 962 MW_e;
* offers it **once**, in the first horizon ≥ `from_year` (2040 here; 2035 on the 5-year grid);
* prices it on the `nuclear retrofit` cost row: 1 800 €/kW over 10 years, i.e. Tihange 3's;
* after 10 years the ordinary retrofit renews it, exactly like Tihange 3
  (`retrofit_nuclear_once: false`).

It is on in the three S2 blocks only. Tests: `test/test_nuclear_restart.py` (9) and
`test_cabinet_batch.py`.

**Pins** (`scripts/walloon_scripts/make_nuc4gw_scenarios.py`): every BEWAL `nuclear-all` row from 2035
is the central's plus 962 MW, and the BE parent row moves by the same amount. Flanders is untouched.

| BEWAL, MW_e, min / max | 2035 | 2040 | 2045 | 2050 |
|---|---|---|---|---|
| S1 `scen_central` | 1000 / 1030 | 1000 / 1030 | 1750 / 1750 | 3000 / 3000 |
| **S2 `scen_nuc4gw`** | 1962 / 1992 | 1962 / 1992 | 2712 / 2712 | **3962 / 3962** |

* The 2040 corridor is met by Tihange 3 retrofit (1 030) plus Tihange 1 restart (962) = 1 992.
* The new build is S1's (about 1.97 GW in 2050), so **S2 − S1 is Tihange 1 alone**.
* "4 GW" is the cabinet's label for "Tihange 1 + Tihange 3 + 2 GW new". If the cabinet wants exactly
  4 000 MW in 2050 (38 MW more new build), that is one argument (§6).

### 4.2 New nuclear at 60 years

* **Master CSV.** `cost:nuclear:lifetime` goes 40 → 60 (2030 / 40 / 50). The origin was switched off
  `PyPSA`, otherwise `--write` would ignore the row (memory: PyPSA-origin rows are silently
  ignored). Propagated by `--write --all-scenarios` to `custom_costs.csv` and all 15 copies: one
  value each, nothing else.
* **Effect.** Capacities are pinned, so only the annualised fixed cost moves:
  9.5 M€/MW × (annuity 7.94 % → 7.60 %) + 1.27 % FOM = **875 → 843 kEUR/MW_e/a**.
  * Retirement does not change: the new-build seeds already close in 2084.
* **Side effect neutralised.** `add_existing_baseyear` fills a missing closing date with
  `costs.lifetime`. 64 of the 80 foreign reactors have none, so they would have lived 20 years
  longer.
  * The new key `existing_capacities.fill_lifetime: {nuclear: 40}` keeps them exactly as before.
  * In code: `add_power_capacities_installed_before_baseyear(fill_lifetime=…)`.

### 4.3 The SPF costs the cabinet asks for

Source: SPF Economie, *Étude prospective multi-vecteurs …, Partie I : méthodologie* (February 2026),
Table A1.5 on p. 56. Currency year not stated on that page.

| | SPF CAPEX, M€/MW | SPF FOM, M€/MW/a | SPF VOM, €/MWh | pypsa-wal today |
|---|---:|---:|---:|---|
| new nuclear | **8.00** | **0.175** | 1.1 | 9.50; FOM 1.27 % = 0.121; VOM 4.46 |
| prolongation (LTO) | 0.79 | 0.175 | 1.1 | 1.80; FOM 1.27 % of 1.8 = 0.023 |
| SMR | 9.00 | 0.21 | 1.32 | not modelled |

**Annualised at 7.5 %:**

| | pypsa-wal today | SPF | change |
|---|---:|---:|---:|
| new nuclear, 60 years | 843 kEUR/MW/a | 783 | −7 % |
| LTO, 10 years | 285 | 290 | about equal |

* The lower SPF capex is mostly offset by its higher fixed O&M.
* **Capacities are pinned in every scenario, so the nuclear cost moves the total cost and the
  reported LCOE, not the mix or the electricity price.** That point could help the discussion with
  the cabinet.
* **If adopted:**
  * `cost:nuclear:investment` 9 500 → 8 000 and `cost:nuclear:FOM` 1.27 → 2.19 %/a (= 0.175 / 8.0),
    rows for 2030 / 40 / 50;
  * the FOM row is `PyPSA`-origin: switch the origin and add a `custom_costs.csv` row;
  * optionally the `nuclear retrofit` rows;
  * then `--write --all-scenarios` and `--check`.

---

## 5. Runbook: office computer, 1 h, NIC5 + NIC6

**Read first:** [`run_from_office_computer.md`](../../run_from_office_computer.md), §1–§7 (disk
layout, one heavy local step at a time, capped). Repo at `/sylvain/git/pypsa-wal`. Nothing here was
run from the home workstation except the two 6 h tests of §10.

### 5.0 The split

| cluster | scenarios (`RUN_NAME`) | why |
|---|---|---|
| **NIC5** `/scratch/ulg/thermlab/squoilin/pypsa-wal` | `scen_central scen_biomethane_industrie scen_noccsccgt scen_realiste scen_retardnucleaire` | the S1 family on the proven path; the central goes here |
| **NIC6** same path string, **different filesystem** | `scen_nuc4gw scen_nuc4gw_biomethane_industrie scen_nuc4gw_noccsccgt scen_noco2cap scen_test_lowccs_ptx` | first pypsa-wal run on NIC6 |

Set the two lists once in the shell:

```bash
export S_NIC5="scen_central scen_biomethane_industrie scen_noccsccgt scen_realiste scen_retardnucleaire"
export S_NIC6="scen_nuc4gw scen_nuc4gw_biomethane_industrie scen_nuc4gw_noccsccgt scen_noco2cap scen_test_lowccs_ptx"
```

**NIC6 differences, handled by `REMOTE=nic6`** (`cluster/config.sh`, new on 10 Oct):
* `batch` only, and a hard limit of 1 900 MB per core at submit.
  * Solve: 32 cores × 60 GB (`cluster/config_cluster_nic6.yaml`).
  * `add_brownfield`: 9 cores for its 16 GB.
* Gurobi comes from the module `releases/2025b Gurobi/13.0.1-GCCcore-14.3.0`.
* Separate job record (`cluster/.last_jobs_nic6`).
* Untested end to end; NIC5 is unchanged.

**Fallback if NIC6 fails at setup or submit:** run its five on NIC5 in a second directory (the
4 Oct clone pattern, guide §4 item 4), e.g.
`REMOTE_DIR=/scratch/ulg/thermlab/squoilin/pypsa-wal-sens2`.

### 5.1 Before anything (office computer)

1. **Code.**
   * Sylvain commits and pushes this work; then `git pull` on the office computer.
   * `git status -sb` must be clean and equal to `origin`.
   * Run `git -C ../TIMES_PyPSA log --oneline -1` to note the soft-link code version.
2. **Access.**
   * On campus no VPN is needed; off campus use `sqvpn`, **not** Proton (`check_host_health.sh` flags it).
   * `ssh nic5 hostname` and `ssh nic6 hostname` must both answer.
3. **Host.**
   * `./scripts/walloon_scripts/check_host_health.sh`.
   * `df -h / /home /sylvain/mount`: abort lines in the guide §1.
4. **Inputs.** The exports must resolve, and the parameter check and tests must pass:

   ```bash
   python -m pytest test -q -k times_scenario_inputs
   python scripts/build_common_parameters.py --check --all-scenarios     # CHECK PASSED
   python -m pytest test -q                                              # 733 passed on 10 Oct
   ```

   The exports are the four `*_261002_0210.vd` plus `scen_sensibilite_realiste_260929_3009.vd`; the
   office computer already had them on 6 Oct.

### 5.2 Archive the previous trees (office computer and NIC5)

Five of the S1 scenarios and the PtX test have 4–6 Oct trees. Move them out of `results/`, because
`pull` syncs `results/`:

```bash
A=/sylvain/mount/pypsa-wal-data/results/_archive_pre20261010; mkdir -p $A
for s in $S_NIC5 scen_test_lowccs_ptx; do [ -e results/walloon/$s ] && mv results/walloon/$s $A/; done
ssh nic5 "cd /scratch/ulg/thermlab/squoilin && mkdir -p pypsa-wal-archive/pre20261010 && \
  for s in $S_NIC5 scen_test_lowccs_ptx; do [ -e pypsa-wal/results/walloon/\$s ] && mv pypsa-wal/results/walloon/\$s pypsa-wal-archive/pre20261010/; done"
```

NIC6 has nothing to archive.

### 5.3 Prepare all ten locally (detached, low-memory wrapper)

```bash
DRY_RUN=1 ./cluster/nic5.sh prepare 2>&1 | tail -30        # job count; no retrieve_*, cutout or renewable-profile rule
setsid nohup env LOCAL_RUN=/sylvain/mount/pypsa-wal-data/batch_20261006_scripts/smk_lowmem.sh \
    ./cluster/nic5.sh prepare > cluster/logs/prepare_batch_20261010.out 2>&1 < /dev/null &
```

* `RUN_NAME` defaults to the ten names of `run.name`.
* **Job counts.** The four new names prepare their whole chain (about 100 jobs each). Existing trees
  rebuild from the changed cost and potential files: about 45 jobs.
* **Duration.** Expect about 1 h at `mem_mb=20000`; the 4 Oct sensitivities took 25 min for five.
* Wait for `N of N steps (100%) done`.
* **Check, in `logs/walloon/<s>/add_existing_baseyear_base_s_adm___2025.log`:**
  `Process-emissions load at BEWAL: 4411.62 kt/a`.
* **The later horizons are set by `add_brownfield`, which runs on the cluster** (§5.7).

### 5.4 NIC6 one-time setup (only the first time; 30–60 min)

```bash
REMOTE=nic6 ./cluster/nic5.sh setup
```

* It installs Miniforge and the `pypsa-eur` env in the NIC6 `$HOME`, and copies the Gurobi module
  licence to `~/gurobi.lic`.
* **It must end with `gurobi licence : OK`.**
* **If the licence step warns,** copy the licence by hand:

  ```bash
  ssh nic6 'module load releases/2025b Gurobi/13.0.1-GCCcore-14.3.0 && cp "$GRB_LICENSE_FILE" ~/gurobi.lic'
  ```

* **Check the Slurm account:**

  ```bash
  ssh nic6 'sacctmgr -nP show assoc user=$USER format=account'
  ```

  It must list `ceci`. Otherwise `export SLURM_ACCOUNT=<account>` for every NIC6 command.
* **File quota:** `ssh nic6 'quota -s'`. `$HOME` allows 200 k files and the env is large.

### 5.5 Push

```bash
RUN_NAME="$S_NIC5" ./cluster/nic5.sh push
REMOTE=nic6 RUN_NAME="$S_NIC6" ./cluster/nic5.sh push
```

* `push` sends code, `data/` and **all** of `resources/` whatever `RUN_NAME` says.
* **The first NIC6 push is the whole tree**, several GB over the office uplink. Start it as soon
  as 5.3 is done.
* **Before solving,** check that the `.vd` include in `PUSH_EXCLUDES` (`*_261002_0210.vd` + the
  30 Sep réaliste file) matches what the blocks read. It does today.

### 5.6 Solve

```bash
ssh nic5 "sinfo -p batch,hmem -o '%P %a %D %t %C %m'"
RUN_NAME="$S_NIC5" ./cluster/nic5.sh solve
ssh nic6 "sinfo -o '%P %a %D %t %C %m'"
REMOTE=nic6 RUN_NAME="$S_NIC6" ./cluster/nic5.sh solve
```

**Within 5 minutes:**
* `./cluster/nic5.sh status` and `REMOTE=nic6 ./cluster/nic5.sh status`;
* on NIC6, `ssh nic6 "squeue --me"` must show 2025 solves **RUNNING with 32 CPUs**;
* NIC6's `cluster/logs/orchestrate.log` must contain no `sbatch` error. A memory-per-core or account
  error shows up there, not as a pending job.

**Expected duration.**
* NIC5 `batch` (16 cores): about 6.5 h per chain. 2025 takes 2.6–3.9 h, then about 1 h per
  horizon; the five chains run in parallel.
* NIC6: unknown. It has 32 Zen 5 threads.

### 5.7 What to check while it runs (probes per the guide §5)

| horizon | where | expect |
|---|---|---|
| every one | `results/walloon/<s>/logs/*_solver.log` | `Optimal objective`, no `Infeasible`, no `Numerical trouble` |
| 2030 / 40 / 50 | `results/walloon/<s>/logs/*_python.log` | `Capped BEWAL CO2 capture at 2000 / 6000 / 8000 kt/a, overage at 1000 EUR/t` |
| 2030 / 40 / 50 | `logs/walloon/<s>/add_brownfield_base_s_adm___<y>.log` (cluster) | `Process-emissions load at BEWAL: 3946.10 / 3875.28 / 3880.12 kt/a`. **5433.90 / 5108.04 means the old file travelled: stop** |
| 2040 / 50 | `*_python.log` | `Pinned BEWAL industry CC capture to ≥ 4145.3 / 5119.6 kt/a` (central; floor ≤ cap, or the solve aborts before Gurobi) |
| 2040, S2 family only | `logs/walloon/<s>/add_brownfield_*2040*.log` | `Offering the restart of Tihange 1 at BEWAL in 2040: up to 962 MW_e, nuclear retrofit cost` |
| 2050, S2 family only | `logs/walloon/<s>/add_brownfield_*2050*.log` | retrofit offer for `BEWAL nuclear Tihange 1 restart` |

### 5.8 Pull, post-process, review (office computer)

```bash
RUN_NAME="$S_NIC5" ./cluster/nic5.sh pull
REMOTE=nic6 RUN_NAME="$S_NIC6" ./cluster/nic5.sh pull
```

**Landing checks per scenario** (guide §6): 4 networks and 4 `Optimal objective`. Then, one at a
time and capped:

```bash
SKIP_S3_UPLOAD=1 HTML_PUBLISH=0 LOCAL_CORES=4 RUN_NAME=<s> cluster/capped.sh 14G post -- ./cluster/nic5.sh postprocess
PYTHONPATH=. python scripts/walloon_scripts/ptx_report.py results/walloon/<s> --out results/walloon/<s>/csvs/ptx_report.csv
PYTHONPATH=. python scripts/walloon_scripts/review_run.py results/walloon/<s>
```

**In `ptx_report.csv`, BEWAL CO₂:**
* `capture total` ≤ `capture cap`;
* `capture overage` = 0. A non-zero overage means the cap binds harder than 1 000 €/t; report it.
* S2: BEWAL nuclear 1 992 MW in 2040 (Tihange 3 1 030 + Tihange 1 962) and 3 962 MW in 2050.

**pypsa2html:** uncomment the batch entries in `config/pypsa2html.yaml` as their trees land (same
vintage only).

**Record:** fill §9 of this log (run record) and §11 (review).

**Publication:** only after the review and Sylvain's go. The S2 and noco2cap pages must say that
their TIMES side is still the S1 export.

---

## 5b. Swapping in ICEDD's new exports (later, scenario by scenario)

Per scenario, in this order:

1. **Fetch.** `aws s3 ls s3://intervectoriel/test/scenarios/` (`AWS_PROFILE=intervectoriel`). Copy
   the `.vd` to `../TIMES_PyPSA/data/` and symlink it into `data/walloon/` keeping its mtime
   (`touch -h -r`; memory: stale benchmarks).
2. **Pre-checks** (memory: check ICEDD exports before a batch):
   * same 2025 base as the new central, row for row (4 Oct log §2.2 method);
   * the folder really holds a `.vd`.
3. **Side files.**
   * `python scripts/walloon_scripts/extract_times_softlink_values.py data/walloon/<vd> --scenario <name> --write`.
   * For the S2 and noco2cap scenarios this creates their own `times_pv_rooftop_share_<name>.csv`
     and `times_industrial_capture_<name>.csv`.
   * Point the block at them, set `times_file`, and delete the `PLACEHOLDER` comment.
   * Check `limit_twh` against the extractor's `Transfo_Imp` output.
4. **Checks in the new export:**
   * Tihange 1 in TIMES S2 (`VAR_Cap`, RW: 962 MW from 2035?);
   * the `CO2STG01` bound (2 Mt in 2030?);
   * capture floor ≤ cap if the cap is on;
   * the process-emissions load (§3.1).
5. **Tests.** Update `BATCH_VD` and remove the scenario from `PLACEHOLDER_OF` in
   `test/test_cabinet_batch.py`. `scen_test_lowccs_ptx` follows the central's export and side files,
   so swap it together with `scen_central`; do the same for the 6 h twin `scen_central_6h`.
6. **Push filter.** Update the `.vd` include pattern of `PUSH_EXCLUDES` in `cluster/config.sh`
   (today `*_261002_0210.vd` + the 30 Sep réaliste file).
7. **Pre-flight.**
   * `python scripts/build_common_parameters.py --check --all-scenarios`;
   * `pytest test -q`;
   * `DRY_RUN=1 RUN_NAME=… nic5.sh prepare`.

---

## 6. Parameters that can still change, and where

| parameter | value now | where | after changing it |
|---|---|---|---|
| Capture cap on/off | **on** (base, inherited by all) | `sector.co2_capture_limit.enable` (base, or `false` in a scenario block) | solve-time key, no re-prepare |
| Capture cap volumes | 2 000 / 6 000 / 8 000 kt (2035 4 000, 2045 7 000) | `sector.co2_capture_limit.kt` **and** the convergence table rows `config:sector.co2_capture_limit.kt` (test keeps them equal) | — |
| Capture overage valve | 1 000 €/t | `sector.co2_capture_limit.overage_price` (null = hard) | — |
| Tihange 1 capacity in the pins | +962 MW | `make_nuc4gw_scenarios.py --t1-mw X` | then `build_common_parameters.py --write --all-scenarios` |
| S2 exactly 4 000 MW in 2050 | 3 962 | edit `nuclear_rows()` or the two 2050 rows of the generated override, and the test | `--write --all-scenarios` |
| Tihange 1 restart year / cost / size | 2035 / `nuclear retrofit` / 962 | `electricity.nuclear_restart.plants.Tihange 1` | prepare-time key: re-prepare (`add_brownfield`) |
| New-nuclear lifetime | 60 years | master CSV `cost:nuclear:lifetime` | `--write --all-scenarios` |
| Foreign closing-date fill | 40 years | `existing_capacities.fill_lifetime` | re-prepare from 2025 |
| Nuclear CAPEX / FOM | 9 500 €/kW / 1.27 % | master CSV `cost:nuclear:investment` / `:FOM` (§4.3) | `--write --all-scenarios` |
| Extension cost (Tihange 1 and 3) | 1 800 €/kW, 10 years | master CSV `cost:nuclear retrofit:*` | `--write --all-scenarios` |
| Belgian caps in `scen_noco2cap` | 1.0 (lifted) | its `budget_national` block | — |
| Batch composition | 10 runs (9 cabinet + PtX test) | `run.name` (single source for `cluster/config.sh`) | update `BATCH` in the test |

---

## 7. Pre-flight checks (done 2026-10-10, home workstation)

| check | result |
|---|---|
| tree | branch `development_plan` at `f3a2a27d`; all changes **uncommitted** (§9.x) |
| `pytest test -q` | **733 passed** (639 before today's changes) |
| `build_common_parameters.py --check --all-scenarios` (10-year grid) | **CHECK PASSED**, 15 overlays |
| the same with `config.walloon_5y.yaml` | fails on `budget_national` only: the **pre-existing** missing BEWAL 2040 = 15 % row, already noted on 6 Oct. Not touched |
| merged configs | `update_config` of the 4 new blocks gives the intended restart flag, files, caps and fill lifetime |
| `snakemake -n` | the DAG builds for `scen_nuc4gw`, `scen_nuc4gw_noccsccgt` and `scen_noco2cap` (328 jobs on this workstation, whose resources are stale; prepare on the office computer as usual) |
| S3 | no export newer than `times_20261002_*` |
| 6 h / 1 h solve of the new paths | capture cap: **6 h central solved, feasible** (§10). Tihange 1 restart: toy LPs and one real 2040 network only; not solved |

---

## 8. Open questions

Settled on 10 Oct: capture cap on; nuclear cost kept; S2 at 3 962 MW; PtX test kept.

1. **Capture cap (§3), what remains.**
   * a. Confirm the 2030 bound of 2 Mt with ICEDD (0 in the 2 Oct export; it was the convergence
     sheet's earlier `CO2STG01` 2030 anchor).
   * b. ~~Re-extract the process-emissions load~~ **Done 10 Oct** (§3.1). It needs no change when
     the new exports land unless the breakdown printed by the extractor moves.
2. **CCS on CCGT "actif par défaut".** Without the cap it appeared unforced, at the margin. With the
   cap on, it must fit in the room process capture leaves under 6 Mt in 2040 (about 0.8 Mt, §3.2).
   S2, with more nuclear, may lose it altogether.
   * If it must appear, the explicit lever is a `p_nom_min` floor on BEWAL `CCGT CC`; the cabinet
     asked for the lever to be documented.
   * The two corrections of 6 Oct R1 (steam-cycle penalty, onshore collection) would push it out.
     Do not mix them into this batch without a decision.
3. **`scen_noco2cap`:** is the endogenous European carbon price an acceptable stand-in for "maintien
   des ETS"? The alternative is a `price_national` block at TIMES's ETS1 / ETS2 trajectories, which
   needs the system cap reworked. Model the AEA fines?
4. **ICEDD:** the export list of §1 (6 re-exports + 4 new), the Tihange 1 profile in TIMES, and the
   2 574 kt question carried over from 4 Oct.

---

## 9. Run record

### 9.0 Launch of 10 Oct (office computer, Claude desktop agent)

**Status: SOLVING since 14:22 on 10 Oct.** The split of §5.0 was kept: 5 chains on NIC5, 5 on NIC6.
Launch HEAD: `4f2a5d21` plus the uncommitted script changes of §9.1 (list in
`/sylvain/mount/pypsa-wal-data/batch_20261010_scripts/batch_20261010_head_at_launch.txt`).
TIMES_PyPSA at launch: `c6f93e2` (main, equal to origin).

| step | when | result |
|---|---|---|
| access | 13:20 | `ssh nic5` OK. **`ssh nic6` did not resolve: no alias on this machine** (§9.1 item 1) |
| NIC6 setup | 13:22–13:35 | needed three fixes, §9.1 items 2–4; licence check OK |
| local env | 13:25–13:33 | **the local conda no longer existed** (§9.1 item 5); rebuilt, pinned |
| tests | 13:35 | `pytest test -q`: 732 passed, 1 skipped (733 on 10 Oct at home); `--check --all-scenarios` passed |
| archive | 13:38 | 6 stale trees to `results/_archive_pre20261010` (local) and `pypsa-wal-archive/pre20261010` (NIC5) |
| `prepare`, all ten | 13:39–14:16 | **472 jobs, 37 min, exit 0, cgroup peak 7.5 GB** (8 GB cap). `Process-emissions load at BEWAL: 4411.62 kt/a` in all ten `add_existing_baseyear` 2025 logs |
| push | 14:17–14:18 | NIC5 and NIC6 in parallel, 1 min (the bulk went in a pre-push, 13:27–13:40); sizes and mtimes verified against local |
| cluster dry run | 14:20 | both clusters: **35 jobs = 20 solves + 15 `add_brownfield`**, nothing else |
| `solve` | 14:22 | NIC5: pid 1438193, 16 cores / 80 GB; NIC6: pid 140181, 32 cores / 60 GB |

### 9.1 What had to be fixed to run on NIC6 and on this machine

1. **`~/.ssh/config` had no `nic6` alias** here. Added (backup `~/.ssh/config.bak-2026-10-10`); the host key
   was accepted after matching the fingerprint in `~/llm/env-nic6-ceci.md`.
2. **`nic5.sh setup` failed on a fresh cluster**: `rsync … envs/environment.yaml` into a directory that
   did not exist. It now creates `$REMOTE_DIR/envs`.
3. **The NIC6 env differed from NIC5's.** A fresh `conda env create` gave pypsa 1.3.0 / linopy 0.9.1 /
   pandas 3.0.6 (NIC5: 1.2.1 / 0.6.1 / 2.3.3; gurobipy 13.0.3 vs 13.0.2). Rebuilt from
   `envs/pypsa-eur_nic5_explicit.txt` (new file: `conda list --explicit` of the NIC5 env), which
   `cluster_setup.sh` now uses when present. Same on the local env.
4. **`snakemake -n` died on NIC6 with `ModuleNotFoundError: times_pypsa`.** The DAG planner imports it
   (`rules/build_sector.smk`, input function of `build_wallon_demands`), so the setup comment
   "the solve chain does not import times_pypsa" was wrong for planning. NIC5 has it as an editable install
   of a scratch copy of `TIMES_PyPSA`. `setup` now ships `TIMES_PyPSA` (sources only) next to the repo and
   installs it editable, no deps.
5. **The local conda was gone** (`/home/anaconda` removed in the disk reorganisation; nothing on `PATH`,
   no `snakemake` anywhere). With Sylvain's approval: Miniforge 26.7.2 installed to
   `/sylvain/mount/pypsa-wal-data/miniforge3` (installer sha256 matched the GitHub release digest), env
   `pypsa-eur` built from the lock of item 3, plus `pip install --no-deps` of `snakemake==9.25.1` and the
   editable `TIMES_PyPSA` and `pypsa2html`. `~/.bashrc` was **not** touched: use
   `export PATH=/sylvain/mount/pypsa-wal-data/miniforge3/bin:$PATH`.
6. NIC6 job shapes checked with `sbatch --test-only`: 32 cores × 60 GB and 9 cores × 16 GB pass; the NIC5
   shapes (16 × 80 GB, 1 × 16 GB) are rejected at submit (1 900 MB per core).

7. **Pending forever on a busy NIC6 (16:00).** All rules ran with the 12 h limit; the 15-second
   `add_brownfield` jobs and the next 32-core solves were quoted a start the next day while 224 cores were
   idle. `scontrol update JobId=… TimeLimit=…` on the pending jobs started them within a backfill cycle.
   `config.sh` now defaults `LIGHT_RUNTIME=30` (both clusters) and `SOLVE_RUNTIME=360` (NIC6). The running
   orchestrators keep the old limits, so a loop per login node (`cluster/shorten_light_jobs.sh`) lowers
   pending light jobs (and NIC6 solves) while they live.

8. **NIC6 memory headroom (16:26). Superseded by §9.2 / §11 F9: the final `MaxRSS` peaks reached 58.0 GiB (99 % of the request).** With 32 Gurobi threads the peaks were 39-46.6 GiB in 2025 and, in 2030,
   **49.2 GiB (`scen_nuc4gw`) and 50.4 GiB (`scen_nuc4gw_biomethane_industrie`)**, against the 60 000 MB (58.6 GiB)
   request; `scen_nuc4gw_noccsccgt` stayed at 41.7 GiB. NIC5 at 16 threads peaks at 29 GiB. On NIC5's history 2040 is
   about 6 % above 2030, which leaves 5 GiB of margin: probably enough, not safely. A user can raise the memory of a
   PENDING job: `scontrol update JobId=<id> MinMemoryNode=75000`. The job still gets 32 cores (the 1.9 GB-per-core rule is
   checked at submit only); `AllocTRES` showed `cpu=32,mem=75000M`. The NIC6 loop (`cluster/shorten_light_jobs.sh`)
   does it for `scen_nuc4gw`, `scen_nuc4gw_biomethane_industrie` and `scen_test_lowccs_ptx` at 2040 and 2050 (the 2030
   solves had already started with 60 GB: **a running job cannot be changed**). A first attempt with `NumCPUs=40` pended 30 minutes
   and started within 2 minutes once put back at 32 cores, so ask for memory only; 75 GB at 32 cores started without extra wait. If a NIC6 job is OOM-killed anyway (`sacct`
   `OUT_OF_MEMORY`), resubmit it with Gurobi `threads: 16` (about 30 GiB, and the same solver path as NIC5).

**First results.** NIC6 2025 solves: 1 h 17 min (`scen_nuc4gw_noccsccgt`) to 1 h 37 min (`scen_nuc4gw`), 473–676
barrier iterations, no crossover, peak 41.5–43.7 GB of the 60 GB. NIC5 (16 cores) is 2.6 h or more for the same
horizon. 2025 optima of the two identical-by-construction models differ by 2e-7 (3.35331481e11 vs 3.35331537e11).

**Comparability caveat.** The S1 family solves on NIC5 with 16 Gurobi threads, the S2 family on NIC6 with 32.
Same LP, same package versions, but a different barrier path: where the optimum is nearly degenerate (CCGT
CC at the margin in 2040, §8 Q2) a difference between a pair split across clusters can be a solver-path
difference, not the Tihange 1 effect. The central reference for the S2 pairs is therefore only as clean as
that. If a pair looks odd, re-solve one horizon of the S1 scenario on NIC6 before interpreting it.

### 9.2 Outcome of the solves (read from `sacct` and the solver logs, 11 Oct)

**40 of 40 horizons optimal, 35 of 35 jobs COMPLETED on each cluster, no failed, cancelled or OOM-killed job.**
Both orchestrators ended with `35 of 35 steps (100%) done`
(`cluster/logs/orchestrate_nic{5,6}_final_20261010.log`; the plain `orchestrate.log` is overwritten by every `pull`).
Barrier iterations 181–720, `Crossover 0` everywhere.

| scenario | cluster | 2025 / 2030 / 2040 / 2050, min | chain, min | done |
|---|---|---|---:|---|
| `scen_nuc4gw_noccsccgt` | NIC6 | 77 / 34 / 35 / 33 | 179 | 17:51 |
| `scen_nuc4gw_biomethane_industrie` | NIC6 | 90 / 36 / 35 / 31 | 192 | 17:52 |
| `scen_nuc4gw` | NIC6 | 97 / 36 / 32 / 28 | 193 | 17:46 |
| `scen_test_lowccs_ptx` | NIC6 | 107 / 35 / 33 / 40 | 215 | 18:04 |
| `scen_noco2cap` | NIC6 | 135 / 37 / 37 / 40 | 249 | 18:41 |
| `scen_noccsccgt` | NIC5 | 122 / 69 / 70 / 66 | 327 | 20:02 |
| `scen_biomethane_industrie` | NIC5 | 131 / 73 / 62 / 63 | 329 | 20:01 |
| `scen_retardnucleaire` | NIC5 | 177 / 60 / 70 / 68 | 375 | 20:46 |
| `scen_realiste` | NIC5 | 169 / 106 / 61 / 67 | 403 | 21:13 |
| `scen_central` | NIC5 | 222 / 97 / 71 / 59 | 449 | 21:59 |

* **Wall clock, 14:22 → 21:59 (7 h 37 min).** The five NIC6 chains took 3.0–4.2 h, the five NIC5 chains 5.5–7.5 h
  (queue waits included). Later horizons: 28–40 min on NIC6 (32 threads) against 59–106 min on NIC5 (16 threads).
* **Peak memory (`MaxRSS` of the solve step).**
  * NIC5, 16 threads: **28.6–33.0 GiB, 37–42 % of the 80 GB request** (2030 is the largest horizon).
  * NIC6, 32 threads: **48.6–58.0 GiB, 83–99 % of the 58.6 GiB request.** Five solves were at 98–99 %
    (58.0 GiB on `scen_nuc4gw` 2030 and `scen_test_lowccs_ptx` 2030, 57.8 on `scen_nuc4gw_noccsccgt` 2040).
    The probes quoted in §9.1 item 8 (up to 50 GB) understated it. Nothing was killed, but there is **no
    headroom**: see §11 F9.
* **Process-emissions load and new code paths (runbook §5.7), all ten trees.**
  * `Process-emissions load at BEWAL` 3 946.10 / 3 875.28 / 3 880.12 kt/a in the 2030 / 2040 / 2050 `add_brownfield` logs
    (not 5 433.90 / 5 108.04).
  * `Capped BEWAL CO2 capture at 2000 / 6000 / 8000 kt/a, overage at 1000 EUR/t` in every horizon's `*_python.log`.
  * `Pinned BEWAL industry CC capture to ≥ 4145.3 / 5119.6 kt/a` (2040 / 2050) in every tree but `scen_test_lowccs_ptx`, whose floor is off by design.
  * `Offering the restart of Tihange 1 at BEWAL in 2040: up to 962 MW_e, nuclear retrofit cost (285095 EUR/MW_e/a, 10 years)` in the three S2 trees, in no other.

### 9.3 Landing and post-processing (10–11 Oct)

* **NIC6 family** (5 trees): pulled and post-processed 17:47–18:47 by the earlier session (`land_one.sh` / `land_two.sh`,
  `/sylvain/mount/pypsa-wal-data/batch_20261010_scripts/`). **NIC5 family** (5 trees): pulled and post-processed
  22:49–23:11 on 10 Oct, about 4 min per tree.
* Per tree, strictly one heavy step at a time, each in `cluster/capped.sh` (no swap): `pull` (1 min, 1.3 GB), local
  `postprocess` (touch, CSVs, plots; peak 3.5–4.1 GB), `ptx_report.py` (3.1–3.6 GB), `review_run.py` (5.2–5.8 GB),
  `check_heat_profile_fidelity.py` (3.1–3.6 GB). No step approached its cap.
* **Not done at landing, done in §9.4:** pypsa2html, TIMES Sankeys and indicators, HTML publication, S3 upload, Explorer extraction.
* **A silent failure, found on 11 Oct.** The landing's `postprocess` runs `network_cost_report.py` and `bill_harmonisation.py`
  through `$LOCAL_RUN`. `LOCAL_RUN` was the Snakemake-only wrapper `smk_lowmem.sh` (it does `shift; … snakemake …`), so the
  step ran `snakemake … network_cost_report.py` and failed with only a warning (`post_<s>.out`). **None of the ten trees had
  `network_costs_calibrated.csv`, `network_cost_segments.csv` or `bill_harmonisation.csv`**; the cost-segment plot died on it.
  Run for all ten on 11 Oct (`netcost_all.sh`, §9.4). The 6 Oct driver ran these two scripts directly, which is why the
  6 Oct tree has them. **Fix to make:** `cmd_postprocess` must not route plain Python through a Snakemake wrapper (§11 F10).

### 9.4 Publication of 11 Oct (office computer, Claude desktop agent)

**Policy** (Sylvain, 5 Oct): the pypsa.squoilin.eu pages and the *test* Explorer are internal; only agreed final scenarios go to the official Explorer.
Everything here goes to S3 `test/`, `https://pypsa.squoilin.eu` and the test Explorer. **Date stamp pinned to 20261010** (the batch day) for all
folders although the work ran 10 Oct 23:00 → 11 Oct. Drivers and scripts: `/sylvain/mount/pypsa-wal-data/batch_20261010_scripts/`
(`publish_batch.sh A|B`, `netcost_all.sh`, `html_lowmem_gc.py`, `add_banner.py`, `pub_record.sh`); logs `cluster/logs/publish_*_20261010.log`,
`publish_batch_20261011*.out`, `ram_publish_20261011.tsv` (one line per minute: available RAM, swap, disk).

| time (11 Oct) | step | result |
|---|---|---|
| 09:00 | state read | both orchestrators 35/35, five NIC5 trees not yet pulled |
| 09:01–09:05 | **`datapypsa` env rebuilt** (the ClimAct extractor's env, lost with the old conda; Sylvain approved) | pypsa 0.35.2, pandas 2.2.3, dask 2026.8.0; 4.0 GB peak |
| 09:05–09:14 | **validation**: re-extraction of the archived 6 Oct central | **49/49 pypsa CSVs and 3/3 strategy CSVs byte-identical** to the published 7 Oct set (7.5 GB peak) |
| 09:16–10:25 | **Phase A**: ClimAct extraction, S3 upload (raw tree + Explorer sets), one scenario at a time | ten extractions of 6–7 min (7.6 GB peak, under a 10 GB cap); every Explorer set **53 files, none empty** (49 pypsa + 3 strategy + 1 `.vd`) |
| 09:27–10:20 | `network_cost_report.py` + `bill_harmonisation.py` for the ten trees (§9.3) | 30/30 files, peaks 2.7–4.2 GB |
| 10:25–10:33 | Phase B, first attempt | **pypsa2html OOM-killed** at the 10.5 GB cap (anonymous RSS 10.6 GB): see issue 3 below |
| 10:40–11:23 | `scen_central` report rebuilt with `html_lowmem_gc.py` | 91 pages, exit 0, **peak 5.4 GB**, 43 min |
| 11:23–18:55 | Phase B for the ten: pypsa2html, Sankeys, indicators, hub, banner, rsync to pypsa.squoilin.eu, S3 re-sync | **all ten live**, HTTP 200 on hub / report / Sankey; 91 pages each, 38–53 min per scenario, peak 5.3–5.4 GB |

**Memory discipline.** Every heavy step ran under `cluster/capped.sh` (cgroup, no swap) and the shared `flock`, so nothing overlapped:
extraction 7.5–7.6 GB, `network_cost_report` 3.2–4.2 GB, pypsa2html 5.4 GB. The 10.5 GB cap did what it is for: the OOM kill (issue 3)
hit the step, not the desktop. Swap used by the desktop rose from 1.3 GB (10 Oct) to ~2.9 GB after the first extractions and drifted to 3.7 GB by 19:00.
**Measured floor of `MemAvailable` over the whole publication (09:14–18:55, `ram_publish_20261011.tsv`): 2.6 GB, during the pypsa2html attempt that was OOM-killed; 7.0 GB or more in Phase B. No new desktop core dump** (`coredumpctl`: last entry is `xapp-sn-watcher` of 10 Oct 22:42, before this session's work).

**Issues of the publication, and what was done.**
1. **`datapypsa` gone** (above). Rebuilt with the documented command; validated byte for byte before use.
2. **First launch failed in 20 s for all ten**: `nic5.sh extract` needs a system `python3` with PyYAML, and the driver had the miniforge `bin` first on
   `PATH` (its base python3 has none). Fixed by putting miniforge last; the first driver was killed by PID, nothing had run.
3. **pypsa2html was OOM-killed twice** (cache bound 2, then 1) at 10.5 GB, where the 6 Oct build had peaked at 7.8 GB. The 10 Oct pypsa2html writes
   more pages, and the `Network` objects it evicts hold reference cycles that are freed only when the cycle collector runs, so RSS saw-tooths
   from 6.6 to over 10 GB. Fix, in a wrapper only (pypsa2html untouched): `html_lowmem_gc.py` = cache 1 + a daemon thread running
   `gc.collect()` and `malloc_trim(0)` every 2 s. Peak 5.4 GB, same run time.
4. **`plot_cost_segments.py`** failed until the network-cost CSVs existed (§9.3); it writes one git-ignored `docs/figures/cost_segments.*`
   (overwritten per run), so it is not part of the publication and was not re-run for a scenario set.
5. **A disk stall** while a plot step started right after an extraction: swap (`/dev/sdb2`) and `/sylvain/mount` share one spindle, and a
   `git diff --stat` I ran at the same moment kept both in uninterruptible wait for ~3 min (95 % util, ~140 IOPS). Cleared by itself; the diff was
   my mistake, not the driver's.
6. **A permission question blocked the turn for ~10 h** (the `datapypsa` rebuild needed approval, asked at 23:15, answered at 09:00). The landing of the five
   NIC5 trees had finished at 23:11; nothing was lost, but the publication started 10 h later than it could have.

**Hub banners.** The hub page of `scen_nuc4gw`, `scen_nuc4gw_biomethane_industrie`, `scen_nuc4gw_noccsccgt` and `scen_noco2cap` says that the TIMES side is the
S1 placeholder; `scen_test_lowccs_ptx` says TEST; `scen_realiste` says internal / older TIMES base (`add_banner.py`, inserted after the hub is built and before the rsync).
The Explorer labels of the first four end in `-times-placeholder`.

**Final state (measured 11 Oct 18:55 with `pub_record.sh`: `curl` HEAD on the three pages, `aws s3 ls`).** All ten scenarios published, **0 failures**.
Each pypsa2html report is 91 pages (40 sections skipped for lack of data, 0 failed), built in 38–53 min at a 5.3–5.4 GB peak; Phase B total 11:23 → 18:55.
Raw trees now hold the HTML (124 files) and the three network-cost CSVs.

| scenario | pypsa.squoilin.eu (hub / pypsa / Sankey) | raw results on S3 `test/pypsa_raw_results/` | Explorer folder `test/scenarios/` |
|---|---|---|---|
| `scen_central` | [https://pypsa.squoilin.eu/scen_central_20261010/](https://pypsa.squoilin.eu/scen_central_20261010/) (200 / 200 / 200) | 329 files, 1.34 GB (124 html) | `times-pypsa__scen_central-2010-1h__20261010` (53 files, 0 empty) |
| `scen_nuc4gw` | [https://pypsa.squoilin.eu/scen_nuc4gw_20261010/](https://pypsa.squoilin.eu/scen_nuc4gw_20261010/) (200 / 200 / 200) | 329 files, 1.34 GB (124 html) | `times-pypsa__scen_nuc4gw-2010-1h-times-placeholder__20261010` (53 files, 0 empty) |
| `scen_biomethane_industrie` | [https://pypsa.squoilin.eu/scen_biomethane_industrie_20261010/](https://pypsa.squoilin.eu/scen_biomethane_industrie_20261010/) (200 / 200 / 200) | 329 files, 1.34 GB (124 html) | `times-pypsa__scen_biomethane_industrie-2010-1h__20261010` (53 files, 0 empty) |
| `scen_nuc4gw_biomethane_industrie` | [https://pypsa.squoilin.eu/scen_nuc4gw_biomethane_industrie_20261010/](https://pypsa.squoilin.eu/scen_nuc4gw_biomethane_industrie_20261010/) (200 / 200 / 200) | 329 files, 1.34 GB (124 html) | `times-pypsa__scen_nuc4gw_biomethane_industrie-2010-1h-times-placeholder__20261010` (53 files, 0 empty) |
| `scen_noccsccgt` | [https://pypsa.squoilin.eu/scen_noccsccgt_20261010/](https://pypsa.squoilin.eu/scen_noccsccgt_20261010/) (200 / 200 / 200) | 329 files, 1.34 GB (124 html) | `times-pypsa__scen_noccsccgt-2010-1h__20261010` (53 files, 0 empty) |
| `scen_nuc4gw_noccsccgt` | [https://pypsa.squoilin.eu/scen_nuc4gw_noccsccgt_20261010/](https://pypsa.squoilin.eu/scen_nuc4gw_noccsccgt_20261010/) (200 / 200 / 200) | 329 files, 1.33 GB (124 html) | `times-pypsa__scen_nuc4gw_noccsccgt-2010-1h-times-placeholder__20261010` (53 files, 0 empty) |
| `scen_retardnucleaire` | [https://pypsa.squoilin.eu/scen_retardnucleaire_20261010/](https://pypsa.squoilin.eu/scen_retardnucleaire_20261010/) (200 / 200 / 200) | 329 files, 1.35 GB (124 html) | `times-pypsa__scen_retardnucleaire-2010-1h__20261010` (53 files, 0 empty) |
| `scen_realiste` | [https://pypsa.squoilin.eu/scen_realiste_20261010/](https://pypsa.squoilin.eu/scen_realiste_20261010/) (200 / 200 / 200) | 329 files, 1.35 GB (124 html) | `times-pypsa__scen_realiste-2010-1h__20261010` (53 files, 0 empty) |
| `scen_noco2cap` | [https://pypsa.squoilin.eu/scen_noco2cap_20261010/](https://pypsa.squoilin.eu/scen_noco2cap_20261010/) (200 / 200 / 200) | 329 files, 1.33 GB (124 html) | `times-pypsa__scen_noco2cap-2010-1h-times-placeholder__20261010` (53 files, 0 empty) |
| `scen_test_lowccs_ptx` | [https://pypsa.squoilin.eu/scen_test_lowccs_ptx_20261010/](https://pypsa.squoilin.eu/scen_test_lowccs_ptx_20261010/) (200 / 200 / 200) | 329 files, 1.35 GB (124 html) | `times-pypsa__scen_test_lowccs_ptx-2010-1h__20261010` (53 files, 0 empty) |

* Explorer test site: https://explorer.test.wallonie.climact.com/ (click **Clear cache** if a scenario is missing). **Not verified in the dropdown** (no browser session used here).
* Internal only (policy of 5 Oct); nothing was sent to `prod/`.
* The four `-times-placeholder` labels and the hub banners must be replaced when ICEDD's exports land (§11.6 item 4).


### 9.x Files changed on 2026-10-10 (uncommitted)

| file | change |
|---|---|
| `scripts/walloon_scripts/nuclear_helper.py` | `restart_options`, `restart_retired_nuclear` |
| `scripts/add_brownfield.py` | calls the restart; loads the cost table once |
| `scripts/add_existing_baseyear.py` | `fill_lifetime` for missing closing dates |
| `scripts/walloon_scripts/named_pins.py` | `captured_co2_expr` (refactored out of the own-capture guard), `add_co2_capture_limit` |
| `scripts/solve_network.py` | wires the capture cap; floor-above-cap check |
| `scripts/walloon_scripts/ptx_report.py` | capture total, cap, dual and overage |
| `scripts/walloon_scripts/make_nuc4gw_scenarios.py` | new generator of the three S2 override tables |
| `config/config.walloon.yaml` | `run.name`; `electricity.nuclear_restart`; `sector.co2_capture_limit`; `existing_capacities.fill_lifetime` |
| `config/scenarios.walloon.yaml` | blocks `scen_nuc4gw`, `scen_nuc4gw_biomethane_industrie`, `scen_nuc4gw_noccsccgt`, `scen_noco2cap` |
| `config/input_parameters_for_models.csv` | `cost:nuclear:lifetime` 40 → 60 (3 rows); 5 new rows `config:sector.co2_capture_limit.kt` (2030–2050) |
| `config/scenarios/scen_nuc4gw*.csv` (3) | generated |
| `data/walloon/custom_costs*.csv` (13 changed + 3 new), `custom_potentials_scen_nuc4gw*.csv`, `agg_p_nom_minmax_scen_nuc4gw*.csv` | `--write --all-scenarios` |
| `test/test_co2_capture_limit.py`, `test/test_nuclear_restart.py` (new), `test/test_cabinet_batch.py` | guards (cap on and equal to the convergence table, no batch opt-out, 10-run batch) |
| `test/test_lowccs_ptx_scenario.py` | "not in the cabinet batch" replaced by "runs last with the batch, labelled TEST in the report" |
| `data/walloon/custom_potentials.csv` (+ every scenario copy via `--write --all-scenarios`) | BEWAL `process emissions` load: gross process CO₂ only (3 875 kt in 2040, was 5 434), §3.1 |
| `scripts/walloon_scripts/extract_times_softlink_values.py` | `process_emissions_breakdown` / `process_emissions_gross_kt`, printed for every export |
| `test/test_process_emissions_load.py`, `test/test_industry_cc_floor.py`, `test/test_five_year_overlay.py` | the new definition; check against the central `.vd`; floor reachable with the fuel CC links |
| `docs/ccs_alignment.md` | §11.1 / §11.2 / §15 item 7: the oxy-fuel split settled |
| `cluster/config.sh`, `cluster/nic5.sh`, `cluster/cluster_setup.sh`, `cluster/config_cluster_nic6.yaml` (new) | `REMOTE=nic6`: 32-core / 60 GB solves, 9-core `add_brownfield`, Gurobi module licence, per-cluster job record; NIC5 unchanged |
| `config/pypsa2html.yaml` | the four new scenarios pre-registered, commented out |
| `results/walloon/scen_central_6h` | the 30 Sep 6 h tree and the first 10 Oct test moved to `results/_archive_pre20261010/` |

**Changed on 11 Oct (uncommitted, same checkout):**

| file | change |
|---|---|
| `config/pypsa2html.yaml` | the nine scenarios of this batch registered again (the 10 Oct vintage); `scen_realiste` label "(internal)"; taxshift pair, `realiste_nets` / `nobnd30` and the route twin stay out (backup `…/batch_20261010_scripts/pypsa2html.yaml.before_20261011`) |
| `run_from_office_computer.md` | §3b: measured NIC6 memory and speed, cross-cluster noise; §7: pypsa2html OOM and the gc fix; new §7.5, the publication chain on this machine |
| `docs/logs/2026-10-10_cabinet_batch_nuc3_nuc4_2010_1h.md` | status, §9.2–§9.4, §11 |
| `results/walloon/<s>/csvs/{network_costs_calibrated,network_cost_segments,bill_harmonisation}.csv`, `html/` | produced for the ten trees (not in git) |

---

## 10. 6 h feasibility tests of the capture cap (local, 10 Oct)

Feasibility only. Not batch results, and not comparable with any 1 h run.

**Setup.**
* `scen_central_6h` = `scen_central` at 6 h, on the 2 Oct central export.
* Home workstation, `--cores 12 --resources mem_mb=100000`, targeting the 2050 network.
* Driver in the session scratchpad; logs `cluster/logs/test6h_central_20261010{,_t2}.log`.
* Test 1's tree is in `results/_archive_pre20261010/scen_central_6h_test1_oldprocessload`.

| | test 1, 11:18 → 11:37 | test 2, 12:14 → 12:29 |
|---|---|---|
| inputs | cap on, nuclear 60 years, **old** process load (5 434 kt in 2040) | the same + **corrected** process load (3 875 kt, §3.1) |
| solves | 4 / 4 optimal | 4 / 4 optimal |
| overage | 0 in every horizon | 0 in every horizon |
| 2040 capture, Mt (cap 6) | **6.00**: process 5.15, biomass-for-industry 0.85 | **6.00**: process 3.67, biomass-for-industry 1.82, gas-for-industry 0.50, CCGT CC 0.01 |
| 2040 cap dual / BEWAL national dual, €/t | −259 / −268 | **−113 / −136** |
| 2050 capture, Mt (cap 8, slack) | 7.24; CCGT CC 0.41, gas CHP CC 0.59 | 6.77; CCGT CC 0.18, gas CHP CC 0.57 |
| 2030 | 1.35 Mt, cap slack | the same |

**Reading:**
* **The cap and the industry floor are jointly feasible.** In test 2 the floor of 4 145 kt is met
  by process + fuel CC (5.99 Mt).
* **The load correction halves the 2040 carbon rent.**
* **The room it frees goes to industrial BECCS and gas CC, not to CCGT CC.** CCGT CC stays at
  about 0 in 2040 at 6 h. What CCS on CCGT looks like at 1 h is for the batch to tell (§8 Q2).

---

## 11. Critical review (11 Oct 2026)

**Scope.** All ten trees, read after landing, following [`docs/run-review-checklist.md`](../run-review-checklist.md).
Evidence: `review_run.py` and `check_heat_profile_fidelity.py` on every tree (`cluster/logs/review_<s>.out`,
`heatfid_<s>.out`; the same script on the archived 6 Oct central as a differential, `review_archived_central_20261006.out`),
`ptx_report.csv`, `metrics.csv`, `nodal_capacities.csv`, `nodal_energy_balance.csv`, the effective `configs/`, the cluster
`sacct` records, and five networks (BEWAL nuclear links of `scen_nuc4gw` and `scen_central`, 2040 and 2050).
**Not done:** no re-solve, no resolution sensitivity (level 8), no cross-scenario pypsa2html report, no TIMES-side check of
the S2 exports (they do not exist yet); level 7 is limited to what `review_run.py` compares.

**Reading guide.** The S1 family and `scen_realiste` solved on NIC5 (16 Gurobi threads); the S2 family, `scen_noco2cap` and
`scen_test_lowccs_ptx` on NIC6 (32 threads). F8 shows that this does not matter for the comparisons below.

### 11.1 Provenance (level 0): pass with caveats

* **Code.** pypsa-wal `4f2a5d21` (all the physics of this batch is committed in it; five commits since the 6 Oct central's
  `f6d0f7aa`) plus the uncommitted cluster scripts of §9.1; TIMES_PyPSA `c6f93e2`; pypsa2html `5e8fc7d`. Environment: the pinned NIC5
  lock on all three machines (pypsa 1.2.1, linopy 0.6.1, gurobipy 13.0.2).
* **Effective configs** (`configs/config.base_s_adm___<year>.yaml`): the four horizons of each tree identical apart from
  `planning_horizons`; weather 2010 (snapshots 2010-01-01 → 2011-01-01 and cutout `europe-2010-sarah3-era5`), 1 h,
  `co2_capture_limit.enable: true`, `fill_lifetime: {nuclear: 40}` in all ten. Diffing each NIC5/NIC6 pair gives only the
  scenario's own keys plus `cpus 16 → 32`, `mem_mb 80000 → 60000` and Gurobi `threads 16 → 32`; `scen_noco2cap` differs from the
  central by the three `budget_national` blocks (2030 / 2040 / 2050: 0.45 / 0.25 (BEWAL 0.15) / 0.05 → 1.0 for BEBRU, BEVLG and BEWAL); `scen_test_lowccs_ptx` by the lever-D
  export cap (3 000 kt, 500 €/t) and the industrial floor switched off.
* **TIMES side (`sector.times_file`).**

  | scenario | `.vd` read | status |
  |---|---|---|
  | `scen_central`, `scen_noco2cap`, `scen_test_lowccs_ptx`, `scen_nuc4gw` | `scen_central_v01_261002_0210.vd` | real for the central and the PtX test (by design); **placeholder** for `scen_nuc4gw` and `scen_noco2cap` |
  | `scen_biomethane_industrie`, `scen_nuc4gw_biomethane_industrie` | `scen_sensibilite_biomethane_industrie_v01_261002_0210.vd` | placeholder for the S2 one |
  | `scen_noccsccgt`, `scen_nuc4gw_noccsccgt` | `scen_sensibilite_central_noccsccgt_261002_0210.vd` | placeholder for the S2 one |
  | `scen_retardnucleaire` | `scen_sensibilite_retardnucleaire_261002_0210.vd` | real (2 Oct export) |
  | `scen_realiste` | `scen_sensibilite_realiste_260929_3009.vd` | **30 Sep export**, older TIMES base; its 2025 is not row-identical to the central's |

  The four placeholders carry S1's demand, industrial capture floor (4 145 / 5 120 kt in 2040 / 2050, seen in their `*_python.log`),
  TIMES Sankeys and indicators. The published hub pages of those four say so (banner, §9.4); the Explorer labels end in
  `-times-placeholder`.

### 11.2 Commit intent (level 0b): pass

Previous production run: the 6 Oct central (`f6d0f7aa`). Every mechanism that changed since, with the observable in these trees:

| mechanism (commit `4f2a5d21`) | what it claimed | observable here | verdict |
|---|---|---|---|
| Capture cap `sector.co2_capture_limit` | BEWAL capture ≤ 2 000 / 6 000 / 8 000 kt, overage valve 1 000 €/t | `Capped BEWAL CO2 capture at …` in every horizon of every `*_python.log`; capture total ≤ cap in 30 of 30 scenario-horizons, **overage 0 in all**; the cap binds in 2040 in 8 of 10 trees (dual −17 to −207 €/t), in 2050 only in `scen_retardnucleaire` (8.00 Mt, −85 €/t) | pass |
| Corrected process-CO₂ load | 3 946 / 3 875 / 3 880 kt, not 5 434 / 5 108 | `Process-emissions load at BEWAL: 3946.10 / 3875.28 / 3880.12` in all ten `add_brownfield` logs; process capture 3.67–3.75 Mt in 2040 / 2050 (0.95 × 3 875 = 3.68) | pass |
| Tihange 1 restart (`electricity.nuclear_restart`) | one extendable link, ≤ 962 MW_e, offered once in 2040, priced as the Tihange 3 extension | offer line only in the three S2 logs; link `BEWAL nuclear Tihange 1 restart` has p_nom 2 951 MW_th = **962 MW_e**, capital cost 92 941 €/MW_th/a = **285 095 €/MW_e/a**, 10 years, capacity factor **87.1 %** (7.34 TWh_e in 2040), renewed in 2050 as a retrofit; BEWAL nuclear **1 992 / 3 962 MW_e** (S1: 1 030 / 3 000) | pass |
| New nuclear 60 years | annuity 875 → 843 kEUR/MW_e/a | `BEWAL nuclear-2025`: capital cost 274 677 €/MW_th/a = **842.6 kEUR/MW_e/a** | pass |
| `existing_capacities.fill_lifetime` | foreign reactors keep their 40 years | the foreign-nuclear rows of `review_run.py` are **identical** to the archived 6 Oct central (NL 515 vs 485 MW, GB 8 664 vs 5 900 and 4 690 vs 2 800, FR 59 758 vs 54 000) | pass |
| `scen_noco2cap` | national caps lifted 2030–2050, system budget kept | caps 1.0 in the config; national-cap dual 0 in 2030 / 2040 / 2050; system CO₂ dual kept (−99 / −118 / −664 €/t) | pass |
| NIC6 route (32 threads, 60 GB, Gurobi 13.0.1 module) | same model, different machine | identical-by-construction LPs agree to ~1e-6 on the objective and ≤ 15 MW on any generator, link or storage-unit capacity (F8) | pass |

### 11.3 Verdict per level

| level | verdict | note |
|---|---|---|
| 0 provenance | pass with caveats | four placeholder TIMES sides; `scen_realiste` on the 30 Sep base |
| 0b commit intent | pass | §11.2 |
| 1 solve | pass, one operational warning | 40 of 40 optimal, `Crossover 0`, "large bounds / rhs" warnings as always; **NIC6 memory at 83–99 % of the request** (F9) |
| 2 soft link | pass, pre-existing caveat | EV, industry, aviation and every transferred carrier match TIMES to ±0.00 %; heat load closes to 3e-6 TWh; 2050 biomass-boiler under-delivery (F11) |
| 3 accounting | pass | all balances close to 0.00 %; one false positive (F10) |
| 4 constraints | pass with caveats | aggregate nuclear caps met (BEWAL 1 992 / 3 962 MW_e in S2); import cap binds in every horizon; foreign-nuclear FAILs unchanged since 6 Oct (F11); **2040 is decided by stacked binding constraints** (F4) |
| 5 realism | pass with caveats | capacity factors in range; build rates above history (F12) |
| 6 prices and costs | partial | objective and `total costs` disagree in sign for some pairs (F2); not a reading of observed prices |
| 7 TIMES consistency | limited | S2 and `noco2cap` have no TIMES counterpart yet; PyPSA price about 2× TIMES in three horizons (F14) |
| 8 robustness | partial | 6 Oct → 10 Oct (F3) and cross-cluster noise (F8) done; resolution sensitivity not |

### 11.4 Findings, ranked by whether they change a headline number

Headline numbers, BEWAL (`cluster`: NIC5 = 16 threads, NIC6 = 32):

**2040** (BEWAL; capacities MW as in `nodal_capacities.csv`; duals EUR/t; price EUR/MWh)

| scenario | cluster | capture Mt (cap) | CCGT CC Mt | capture-cap dual | national-cap dual | price mean | CCGT | CCGT CC | battery disch. | ground PV | objective bn |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `central` | NIC5 | 6.00 (6) | 0.51 | -118 | -141 | 94.8 | 3,441 | 478 | 2,934 | 6,495 | 263.74 |
| `nuc4gw` | NIC6 | 6.00 (6) | 0.00 | -17 | -29 | 90.2 | 3,369 | 0 | 2,270 | 6,387 | 263.39 |
| `biomethane_industrie` | NIC5 | 6.00 (6) | 0.51 | -118 | -141 | 94.8 | 3,437 | 479 | 2,937 | 6,394 | 263.74 |
| `nuc4gw_biomethane_industrie` | NIC6 | 6.00 (6) | 0.00 | -17 | -29 | 90.2 | 3,368 | 0 | 2,270 | 6,285 | 263.39 |
| `noccsccgt` | NIC5 | 6.00 (6) | 0.00 | -120 | -144 | 95.0 | 4,074 | 0 | 2,939 | 6,748 | 263.78 |
| `nuc4gw_noccsccgt` | NIC6 | 6.00 (6) | 0.00 | -18 | -30 | 90.3 | 3,399 | 0 | 2,312 | 6,748 | 263.42 |
| `retardnucleaire` | NIC5 | 6.00 (6) | 0.54 | -117 | -140 | 94.8 | 3,382 | 505 | 2,965 | 7,463 | 263.73 |
| `realiste` | NIC5 | 6.00 (6) | 0.30 | -207 | -237 | 99.9 | 3,779 | 277 | 2,364 | 4,063 | 278.34 |
| `noco2cap` | NIC6 | 5.56 (6) | 0.00 | -0 | -0 | 90.1 | 7,322 | 0 | 418 | 1,510 | 266.22 |
| `test_lowccs_ptx` | NIC6 | 5.49 (6) | 0.00 | -0 | -229 | 98.4 | 3,782 | 0 | 3,520 | 6,495 | 264.30 |

**2050** (BEWAL; capacities MW as in `nodal_capacities.csv`; duals EUR/t; price EUR/MWh)

| scenario | cluster | capture Mt (cap) | CCGT CC Mt | capture-cap dual | national-cap dual | price mean | CCGT | CCGT CC | battery disch. | ground PV | objective bn |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `central` | NIC5 | 6.98 (8) | 0.41 | -0 | -0 | 106.9 | 2,550 | 884 | 5,653 | 13,000 | 284.76 |
| `nuc4gw` | NIC6 | 6.66 (8) | 0.23 | -0 | -0 | 105.5 | 2,478 | 511 | 3,531 | 6,808 | 285.08 |
| `biomethane_industrie` | NIC5 | 7.14 (8) | 0.28 | -0 | -0 | 106.8 | 2,545 | 622 | 5,452 | 13,000 | 284.70 |
| `nuc4gw_biomethane_industrie` | NIC6 | 6.95 (8) | 0.23 | -0 | -0 | 105.4 | 2,477 | 512 | 3,166 | 5,982 | 285.03 |
| `noccsccgt` | NIC5 | 6.13 (8) | 0.00 | -0 | -0 | 107.4 | 3,183 | 0 | 6,286 | 13,000 | 283.81 |
| `nuc4gw_noccsccgt` | NIC6 | 6.13 (8) | 0.00 | -0 | -0 | 105.7 | 2,973 | 0 | 4,162 | 6,824 | 284.12 |
| `retardnucleaire` | NIC5 | 8.00 (8) | 2.35 | -85 | -0 | 112.2 | 2,491 | 4,207 | 8,328 | 13,000 | 283.76 |
| `realiste` | NIC5 | 7.34 (8) | 0.12 | -0 | -0 | 106.2 | 2,888 | 277 | 5,377 | 13,000 | 283.47 |
| `noco2cap` | NIC6 | 6.60 (8) | 0.00 | -0 | -0 | 106.5 | 6,431 | 0 | 5,316 | 12,199 | 283.51 |
| `test_lowccs_ptx` | NIC6 | 6.87 (8) | 0.26 | -0 | -0 | 107.2 | 2,890 | 553 | 5,729 | 13,000 | 284.28 |

**F1. CCS on CCGT "actif par défaut à partir de 2040" (§2 item 2) is not what the model delivers, and in S2 it is absent.**
* 2040 CCGT CC: 0.51 Mt (478 MW_e) in the S1 central and its biomethane twin, 0.54 Mt in `retardnucleaire`, 0.30 in `realiste`, **0 in every S2
  run, in both `noccsccgt` runs (by construction), in `noco2cap` and in the PtX test.** TIMES S1 keeps 1.85 Mt of power CCS in 2040.
* The central's 0.51 Mt and the S2 runs' 0.51 Mt of *gas-for-industry* CC are the **same tonnes taken by a different route**: with the
  cap at 6 Mt both fill it to 6.00 (process 3.67 + biomass-for-industry 1.82 + one 0.51 Mt route). The choice between the two is a
  margin flip, and its price signal is small: the capture-cap dual falls from −118 to −17 €/t between S1 and S2 (F2).
* Why PyPSA gives the room to something else: with the 4 145 kt floor met by 5.49 Mt of industrial capture, PyPSA's industry already
  uses 1.3 Mt more of the 6 Mt than TIMES's (4.15 Mt), which is what TIMES leaves for power.
* **To act on:** §8 Q2 stands. If the cabinet needs CCGT CC in S2, the lever is an explicit `p_nom_min` on BEWAL `CCGT CC` in 2040, stated
  in the annex; the alternative is to cap industrial capture at TIMES's tonnage instead of only flooring it. Do not present the
  S1 0.51 Mt as a result: it is the marginal route.

**F2. Tihange 1 (S2 − S1) relaxes the Walloon CO₂ constraints, and its electricity goes to export and to ground PV, not to the Walloon bill.**

| | 2040 S1 → S2 | 2050 S1 → S2 |
|---|---|---|
| BEWAL nuclear, TWh_e | 7.90 → 15.19 (+7.29) | 22.45 → 29.50 (+7.05) |
| BEWAL gas power (CCGT + CC), TWh_e | 9.27 → 7.02 (−2.25) | 3.05 → 1.91 (−1.14) |
| net BE balance on the BEWAL AC line, TWh (negative = export) | +0.16 → −3.54 (**+3.7 TWh more export**) | +5.87 → +6.30 |
| ground PV, MW (output TWh) | 6 495 → 6 387 (6.30 → 6.19) | **13 000 → 6 808** (12.54 → 6.61, −5.9) |
| battery discharger, MW | 2 934 → 2 270 | 5 653 → 3 531 |
| national CO₂ cap dual, €/t | **−141 → −29** | 0 → 0 |
| capture-cap dual, €/t | −118 → −17 | – |
| electricity import cap, shadow price €/MWh (net import TWh) | −59.5 (+4.88) → −8.1 (+0.86) | −17.2 → −1.3 |
| mean electricity price, €/MWh | 94.8 → 90.2 | 106.9 → 105.5 |

* In 2050 the central sits on the 13 GW ground-PV potential: any extra firm supply displaces PV (962 MW of nuclear ≈ 6 GW of PV at CF 11 %).
* **Objective and `total costs` disagree.** Objective: −0.35 bn in 2040, +0.32 bn in 2050; `total costs` (`metrics.csv`, which prices existing
  assets): −0.35 and −0.48 bn. The restart link alone costs 285 095 €/MW_e/a × 962 MW = 0.274 bn/a. Do not quote either as "the cost of
  Tihange 1", and not at all for 2040 (F5).

**F3. The 6 Oct central's 2040 numbers are superseded: the capture cap and the corrected load moved them.** New central vs the archived one
(same TIMES export, both on NIC5):

| 2040, BEWAL | 6 Oct central | 10 Oct central | change |
|---|---:|---:|---|
| CCGT CC, MW (Mt captured) | 1 713 (1.94) | 478 (0.51) | −72 % |
| gas-for-industry CC, MW | 1 001 | 0 | |
| ground PV, MW | 4 653 | 6 495 | +1 842 |
| battery discharger, MW | 1 320 | 2 934 | +1 613 |
| national CO₂ cap dual, €/t (effective BEWAL price) | −19.5 (132) | **−140.6 (252)** | 7× (1.9×) |
| mean electricity price, €/MWh | 90.5 | 94.8 | +4.3 |
| objective, bn EUR | 264.33 | 263.74 | −0.59 |

2025 and 2030 capacities are identical, so the model change acts from 2040. The 2025 objective moved by +0.05 bn
(335.28 → 335.33), which is above the solver tolerance and has not been traced.
**The 7 Oct publication (6 Oct central) shows the old 2040 picture; the new pages are dated 20261010.**

**F4. 2040 is decided by stacked hard constraints, not by cost.** In the S1 central four constraints bind at once in 2040:
the Walloon national CO₂ cap (−141 €/t), the 6 Mt capture cap (−118 €/t), the electricity import cap (−59.5 €/MWh, 6.47 TWh
one-way) and the biomass limit (−27.9). The S2 runs relax the first three by 5×, 7× and 7×. Any 2040 comparison between scenarios
(PV, batteries, CCGT CC, price) mostly measures which of these constraints a change relieves. Read the duals next to every 2040 number.

**F5. 2040 biogas toggles between scenarios and contaminates cost and price comparisons.** BEWAL biogas used in 2040: 4.67 TWh
(`e_sum_max`) in every NIC5 run and the PtX test; **2.15 TWh in the three S2 runs; 1.02 TWh in `noco2cap`.** The effective Walloon CO₂ price
(252 → 139 €/t in S2) crosses the block's break-even (instructions.md, "reading operational costs"). Part of the S2 2040 price and
objective drop is the block, not Tihange 1.

**F6. `scen_noco2cap`: without the Belgian national caps Wallonia turns to gas, and the central's 2040 PV and battery build disappears.**
* 2030: no capture at all (process CC 0 against 1.28 Mt) and objective −1.7 bn.
* 2040: CCGT 7 322 MW (3 441) and 18.5 TWh of gas power (9.3), ground PV 1 510 MW (6 495), battery 418 MW (2 934), mean price 90.1 (94.8).
  So the central's 2040 PV and storage are a response to the national cap.
* The system CO₂ price is kept (−99 / −118 / −664 €/t), so this is **not TIMES's "pas de contrainte CO₂"** run (§2 item 8, caveat unchanged);
  the AEA fines are not modelled.

**F7. `scen_realiste`.** 2030 uncapped (CO₂ dual 0, price 74.9 against 100 €/MWh), objective −8.3 bn in 2030 and **+14.6 bn in 2040**
(inherited 2030 gas build, then the 2040 caps bite: national dual −237 €/t, capture dual −207 €/t). Heat-pin gap 3.77 TWh_th, 3× the others.
Older TIMES base. Internal only.

**F8. Cross-cluster comparability holds (a positive finding that closes the §9.1 caveat).** For the S1/S2 pairs, 2025 and 2030 are the
same LP. Their objectives agree to ≤ 1e-6 (335.3315 vs 335.3315; 372.8779 vs 372.8779). Of 727 components (stores and the EU primary-supply rows excluded) 0–17 differ by
more than 1 MW and **none by more than 15 MW** (largest: GB offshore wind, 14 MW, 2030). The excluded rows are degenerate: `oil primary` at the EU bus
differs by 0.1 % and the fuel stores by tens of MWh. Two independent pairs (central / biomethane against their S2 twins) show the same S2 pattern. The S2 − S1
differences above (hundreds of MW to GW, duals ×5–7) are therefore model effects. The same holds for `noco2cap` and the PtX test against the central.

**F9. NIC6 memory has no headroom.** `MaxRSS` of the 20 NIC6 solves: 48.6–58.0 GiB, **83–99 % of the 58.6 GiB request**; five solves at
98–99 % (58.0 GiB on `scen_nuc4gw` 2030 and the PtX test 2030). NIC5 at 16 threads: 28.6–33.0 GiB of 80 GB. Nothing was killed, but the
next scenario with a slightly larger LP would be. The 75 GB bump of §9.1 item 8 reached two solves only (`scen_nuc4gw` and `scen_nuc4gw_biomethane_industrie`, 2040; they peaked at 53.6 and 55.2 GiB).
**Before the next NIC6 batch:** `solving.mem_mb: 75000` in `cluster/config_cluster_nic6.yaml` (keep `cpus` = `threads` = 32 if
`sbatch --test-only` accepts it; otherwise `cpus: 40`, `threads: 32`).

**F10. Tooling findings.**
* **Silent failure of the network-cost step at landing** (§9.3): all ten trees lacked `network_costs_calibrated.csv`,
  `network_cost_segments.csv` and `bill_harmonisation.csv` until run on 11 Oct. `cmd_postprocess` sends plain Python through `$LOCAL_RUN`.
  It must call `conda run … python …` directly and `die` (not `warn`) when the files are missing.
* `review_run.py` raises a **false FAIL on `tes_se`** in four trees (`nuc4gw`, `nuc4gw_biomethane_industrie`, `noccsccgt`,
  `nuc4gw_noccsccgt`): in 1.02–1.27 TWh, out 0.97–1.19 TWh, gap −0.058 to −0.081 TWh = 5.7–6.3 % of throughput. That is the thermal store's
  standing loss; the check treats any gap above 0.05 TWh and 2 % on a storage node as a mapping hole (the central stays just under it).
  Exempt storage losses, or compare against the store's `standing_loss`.
* `review_run.py` exits 1 whenever a FAIL exists, which `conda run` prints as an `ERROR` line; harmless, but it hid a real failure on 10 Oct
  only because everyone had learned to ignore it. A "known failures" list (F11) would make a *new* FAIL visible.
* `cluster/probe.sh` cannot map the UUID-named Slurm jobs of snakemake-executor-slurm 2.7 to scenarios; the session wrote `probe_both.sh`.
* `pull` overwrites the local `cluster/logs/orchestrate.log` with whichever cluster was pulled last: copy each under its own name.

**F11. Pre-existing and unchanged since 6 Oct (not caused by this batch).**
* **Foreign-nuclear aggregate FAILs (9 in every tree, 10 with F10):** NL 515 vs 485 MW (2025, 2030), GB 8 664 vs 5 900 (2025) and 4 690 vs
  2 800 MW (2030), FR 59 758 vs 54 000 MW (2050), and four DE rows of "0 vs 0". Same numbers in the archived 6 Oct central
  (`review_run.py` 170 / 30 / 14 / 9). Cause: `add_CCL_constraints` does not subtract existing capacity from the generator `max` (checklist §4.1).
  They change no Walloon number but they sit in every review.
* **2050 biomass-boiler under-delivery** (pinned heat not delivered, the heat pump absorbs it): 1.19 TWh_th in the central, 1.28 in `nuc4gw`,
  0.08 in `retardnucleaire`, 3.77 in `realiste` (undelivered share 8–84 %). Heat load still closes to 3e-6 TWh.

**F12. Build rates above history (same warnings as before).** BEWAL onwind +480 MW/yr 2025 → 2030; ground PV +548 MW/yr 2030 → 2040;
rooftop PV +596 and +628 MW/yr; zero-capital-cost capacities in 2050 (distribution grid 7.8 GW, gas pipeline 7.5 GW, BEV charger 4.2 GW, …)
are not results.

**F13. Do not read ±1 bn between scenarios.** `noccsccgt` is 0.95 bn *cheaper* than the central in 2050 although it has fewer options: the
myopic path (different 2040 build) and a different TIMES export (its own capture floors) differ. Objectives are annual system costs of
different myopic paths, not comparable at the 0.3 % level.

**F14. PyPSA's wholesale price is about twice TIMES's in three of four horizons (level 7; `csvs/bill_harmonisation.csv`, run on 11 Oct).**
BE zonal time-average price, PyPSA vs TIMES, `scen_central`: 2025 105.1 vs 51.3 €/MWh (+105 %), 2030 118.3 vs 67.0 (+77 %),
2040 106.5 vs 96.9 (+10 %, the only pass), 2050 112.5 vs 60.6 (+86 %). Gas 17–22 % above TIMES in every horizon. 18–19 of the 20 rows
are `GAP` in every tree I opened (`scen_central`, `scen_nuc4gw`). TIMES averages its own timeslices; PyPSA prices 8 760 hours with a CO₂ dual
of 77–653 €/t. The 2040 agreement is a consequence of F4 (the stacked constraints raise PyPSA's 2040 price), not of better agreement.
Any bill or price quoted from PyPSA next to TIMES needs this table and the "bills use the Belgian zonal HV price" rule of instructions.md.

### 11.5 Numbers that must not be published as-is

| number | why |
|---|---|
| any 2040 CCGT CC / "CCS on CCGT" tonnage or capacity | marginal route, flips between S1 and S2 with a 17 €/t price signal (F1); the cabinet's "active by default" is not met in S2 |
| a cost, a price delta or a CO₂ price for "Tihange 1" | objective and `total costs` disagree in sign in 2050; the 2040 delta contains the biogas toggle and three relaxed constraints (F2, F4, F5) |
| the S2 trio's and `noco2cap`'s TIMES-side figures (demand, Sankeys, indicators, industrial floor) | S1's export, a placeholder until ICEDD delivers (§11.1) |
| `noco2cap` as "TIMES without CO₂ constraint" | system price kept, endogenous; AEA fines not modelled (F6) |
| the 7 Oct pages and any 2040 figure from the 6 Oct central | superseded by the capture cap and the corrected load (F3) |
| 2025 horizon values | an optimisation of the base year, not a calibration (checklist §5.1) |
| 2050 ground PV in S1 (13 000 MW) | it is the potential cap, not an optimum |
| the 2050 Walloon heat mix by technology | biomass boilers under-delivered by 8–84 % (F11) |
| any PyPSA electricity price or bill set beside TIMES's | about 2× TIMES in 2025, 2030 and 2050 (F14) |
| `scen_realiste` anything | older TIMES base, 2030 uncapped by design |

### 11.6 Follow-up actions

1. **NIC6 memory** to 75 000 MB before the next NIC6 batch (F9).
2. **Fix `cmd_postprocess`** (plain Python off the Snakemake wrapper; fail on missing network-cost files) and add a guard test (F10).
3. **`review_run.py`:** exempt `tes_se` standing losses; add a known-failures list for the nine foreign-nuclear rows; avoid the misleading
   non-zero exit (F10, F11).
4. **ICEDD:** the S2 exports (3 + `noco2cap`), the Tihange 1 profile and the 2030 `CO2STG01` bound of 2 Mt (§8 Q1a, Q4); then §5b swaps the
   placeholders and these four pages and Explorer sets are replaced.
5. **Cabinet / Sylvain:** the CCS-on-CCGT lever (F1) and whether the endogenous system CO₂ price is an acceptable "maintien des ETS" (§8 Q3).
6. Trace the +0.05 bn 2025 objective shift between the 6 and 10 Oct centrals (F3); it is above solver tolerance.
7. Build the **cross-scenario pypsa2html report** (S1 vs S2 on one page) once the exports land; the per-scenario pages built today do not
   compare scenarios.
8. Keep `datapypsa` (§9.4) and the publication drivers (`/sylvain/mount/pypsa-wal-data/batch_20261010_scripts/`) for the next batch.
