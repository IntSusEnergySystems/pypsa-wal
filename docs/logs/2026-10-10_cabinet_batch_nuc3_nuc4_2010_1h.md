# Cabinet batch — 3 GW / 4 GW nuclear scenarios (1 h, weather 2010)

**Status: PREPARED 2026-10-10, NOT LAUNCHED.** The PyPSA side is ready: code, scenario blocks,
generated data files and tests.

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

Not run. To be filled from the launch on, following the 6 Oct log's §5 runbook, adapted:
* central first, with full post-processing;
* then the other eight, split over two NIC5 clones (4 Oct pattern);
* archive the 6 Oct trees first.

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
