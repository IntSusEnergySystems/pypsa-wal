# Central re-run — CO₂ route closed, ICEDD biogas cap in every horizon (1 h, weather 2010)

**Status: SOLVED and POST-PROCESSED 2026-10-06.**
* Run from the office computer ([`run_from_office_computer.md`](../../run_from_office_computer.md)),
  solves on NIC5 `batch`, 16:28 → 22:53. 4/4 horizons optimal, 0 numerical trouble.
* Pulled, post-processed (HTML built locally) and reviewed (§9–§11).
* **PUBLISHED 7 Oct 07:29–08:09** on Sylvain's request ("upload everything"), internal destinations
  only, dated **20261007** (§10.1). §11 is a first review by Claude, not yet read by Sylvain.

**Scope:** `scen_central` only. If it is accepted, the other scenarios are relaunched on the same
inputs (§6).

**Predecessor:** [`2026-10-04_cabinet_batch_20261002_2010_1h.md`](2026-10-04_cabinet_batch_20261002_2010_1h.md),
the 4–5 Oct batch. Its central is published as `scen_central_20261005`. This run uses **the same
TIMES export** and is published under a new date (§5 step 11).

---

## 0. What is different from the 5 Oct central (read first)

1. **The TIMES-priced CO₂ disposal route is closed in every horizon** (Sylvain, 6 Oct). Volume
   0 in 2025, 2030, 2035, 2040, 2045 and 2050. On 4 Oct it was open from 2035: 6 Mt at 71.8 €/t in
   2040 (unused) and 8 Mt at 63.8 €/t in 2050 (full). Walloon CO₂ now leaves by the endogenous
   pipeline route only, as on 1 Oct (§2.1).
2. **The Walloon biogas cap holds in every horizon, on total biogas** (ICEDD, A. Lempereur, 5 Oct).
   The cap is TIMES's bound on new digesters, which TIMES had read for 2040 and 2050 only, plus
   TIMES's existing biogas and landfill gas. The cap is 1.02 / 2.15 / 4.67 / 6.93 TWh in 2025 / 30
   / 40 / 50, against 8.3 / 8.3 / 4.0 / 6.9 on 4 Oct (§2.2).
3. **The forced "unsustainable" biogas now counts against the cap.** In 2025 it is clipped from
   1.45 to 1.02 TWh. This is a code change in `BEWAL_potentials.py` (§2.3).
4. **Transmission brownfield fix, commit `f6d0f7aa`** (pushed 6 Oct 01:21, pulled here). DC links
   now keep the capacity built in earlier horizons, and built transmission is no longer paid
   twice in the objective. Replayed on the 5 Oct networks, the double payment was 721 M€ in 2040
   and 807 M€ in 2050. It acts from 2030 on.
5. **2035/2045 rows of the generated input files fixed** (`build_common_parameters.py`, §2.4). No
   effect on this 10-year run. `scen_noccsccgt`'s copy had the route open and the power-CC caps at
   `inf` in 2035/2045.

**Consequence:** no horizon compares cleanly with the 5 Oct central. 2025 moves (forced biogas),
2030 moves a lot (biogas 9.2 → ≤ 2.15 TWh), and 2040/2050 move by the transmission fix and,
in 2050, by the route. Read every delta against §4.

---

## 1. The run

| | |
|---|---|
| scenario | `scen_central` (block unchanged in `config/scenarios.walloon.yaml`; the changes are in the central data files) |
| TIMES `.vd` | `times_20261002_scen_central_v01/scen_central_v01_261002_0210.vd`, **the same file** as on 4 Oct. Fetched, `data/walloon/` symlink present (64.3 MB) |
| soft-link side files | unchanged (`times_pv_rooftop_share_scen_central.csv`, `times_industrial_capture_scen_central.csv`, extracted from that `.vd` on 4 Oct) |
| weather / resolution | 2010 (`snapshots` 2010-01-01 → 2011-01-01, `europe-2010-sarah3-era5`), `resolution_sector: 1h` |
| horizons | 2025–2030–2040–2050, myopic |
| publication name | `scen_central` stamped with the upload date (`UPLOAD_DATE`). The Explorer folder will be `times-pypsa__scen_central-2010-1h__<YYYYMMDD>` and the HTML `https://pypsa.squoilin.eu/scen_central_<YYYYMMDD>/`. The `.vd` is staged as before. The `20261005` set stays online untouched |

---

## 2. Input changes

### 2.1 CO₂ route closed

| | 2025 | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|---:|---:|
| `BEWAL co2 disposal service e_nom_max`, kt, 4 Oct | 0 | 0 | 4 000 | 6 000 | 7 000 | 8 000 |
| **6 Oct, central and every scenario but the twin** | **0** | **0** | **0** | **0** | **0** | **0** |
| `scen_noccsccgt_route` (re-opened by override) | 0 | 0 | 4 000 | 6 000 | 7 000 | 8 000 |

* **Master CSV.** The five `CO2STG01` potential rows of `config/input_parameters_for_models.csv`
  are set to 0. 2045 interpolates to 0. TIMES-WAL's own bound (4 / 6 / 7 / 8 Mt) is kept in the
  note of each row.
* **Tariff rows unchanged.** `vom_downstream` and `vom_onshore` stay, inert at volume 0.
* **Code unchanged.** `apply_co2_disposal_service` logs `closed this horizon` and leaves the
  Belgian zero. `add_co2_disposal_own_capture` adds no row while the route is closed. Both paths
  were exercised by `scen_noccsccgt` on 4 Oct.
* **`scen_noccsccgt_route`** gets three override rows (2035 / 40 / 50 at TIMES's volumes, `interp`),
  so it stays what it was on 4 Oct: noccsccgt + the TIMES route.
* **`scen_noccsccgt`'s** own route rows now equal the central's ("metadata only" in `--report`).

### 2.2 Biogas: ICEDD's bound in every horizon, plus the existing biogas

ICEDD's message (A. Lempereur, 5 Oct; screenshot from Sylvain). The `~TFM_INS` row `BNDACT UP
BWBIOGAZ100`, region RW, PJ: 2022 0, 2025 1.00, 2030 5.15, 2035 9.62, 2040 14.40, 2050 22.64.
Interpolation option 5.
* Her constraint "was read for 2040 and 2050, not before". She now aligns the earlier years on
  TIMES's results; before her last changes TIMES did not exceed 2 PJ there.
* The energy balances show +1.1 PJ between 2021 and 2024, so 5.15 PJ in 2030 sits a little
  above a straight line.
* **The bound excludes the base-year production, "environ 2.7 PJ en plus".**

**Derivation.** The PyPSA cap is the bound plus TIMES's existing biogas (`MINBIOGAS`) and
landfill gas (`MINCETGAS`), both read from the 2 Oct central `.vd` (`VAR_Act`, RW):

| PJ (GWh in the last rows) | 2025 | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|---:|---:|
| ICEDD bound on new digesters | 1.00 | 5.15 | 9.62 | 14.40 | (18.52) | 22.64 |
| `MINBIOGAS` + `MINCETGAS` (2.72 in 2022) | 2.668 | 2.573 | 2.488 | 2.402 | 2.360 | 2.317 |
| **PyPSA cap on total biogas, GWh** | **1 019** | **2 145** | **3 363** | **4 667** | 5 800 (interp.) | **6 933** |
| *4 Oct cap, GWh* | *8 300* | *8 300* | *6 150* | *4 000* | *5 450* | *6 900* |
| TIMES produced, 2 Oct central, GWh | 987 | 2 132 | 3 321 | 4 667 | 5 800 | 6 933 |

* TIMES's 2 Oct central sits at or just under the new caps, as ICEDD intended ("s'aligner sur
  les résultats").
* **The 2040 and 2050 values move too.** 4.0 → 4.67 TWh in 2040, 6.90 → 6.93 in 2050.
  * The 1 Oct 2040 figure was the new-digester bound alone. `docs/biogas.md` §8.2 had flagged
    that it sat 0.67 TWh below TIMES's total; ICEDD's "2.7 PJ en plus" settles it.
  * **Question 1 of §7** asks Sylvain to confirm.
* **Why TIMES's own existing biogas and not a flat 2.7 PJ.** The cap then equals TIMES's total
  exactly where the bound binds (2040–2050). A flat 2.7 PJ would add 0.01–0.11 TWh.
* This closes F4 of the 4 Oct review (2030 biogas 8.3 + 0.9 TWh in PyPSA against 2.2 in TIMES).

### 2.3 Code: the cap applies to the total

`update_BEWAL_potentials` (biogas branch):
* the sustainable generator gets `cap − forced`;
* the forced `BEWAL biogas unsustainable` generator is clipped (`p_nom`, `e_sum_min`, `e_sum_max`)
  where it exceeds the cap;
* one log line per horizon: `BEWAL biogas cap on the total: … TWh = … forced + … optional`.

Expected split, from the prepared `biomass_potentials_s_adm_<y>.csv`:

| TWh | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| forced (Eurostat 2019 × biomass key × phase-out) before → after | 1.452 → **1.019** | 0.927 | 0 | 0 |
| optional (sustainable) ceiling | 0 | 1.218 | 4.667 | 6.933 |

The forced generator is absent from 2040, and the cap then sits on the sustainable one alone.

### 2.4 `build_common_parameters.py`: 2035/2045 rows

* **The bug.** `patch_potentials` expanded targets on the run's own grid only. A 10-year
  `--write` therefore left the 2035/2045 rows of every generated potentials file as seeded from
  the central. `scen_noccsccgt` had the route open (4 000 / 7 000 kt) and `CCGT CC`, gas CHP CC and
  biomass CHP CC at `inf` in 2035/2045, while they were closed in the four solved years.
* **The fix.** Targets are now expanded over every horizon of every
  `config/config.walloon*.yaml`. A 10-year `--write` / `--check` then keeps those rows in sync.
  `expand_years` depends on the anchors only, so no 10-year value moves. A year that no config
  solves is still an error.
* **This is the guard behind "closed in 2035 and 2045 too".** `test_cabinet_batch.py` now checks
  all six years in every generated copy.

### 2.5 Files

| file | change |
|---|---|
| `config/input_parameters_for_models.csv` | route rows → 0 (5 rows); biogas rows → §2.2 (4 rows changed, 2035 anchor added) |
| `config/scenarios/scen_noccsccgt_route.csv` | +3 rows re-opening the route |
| `data/walloon/custom_potentials.csv` + 12 `custom_potentials_scen_*.csv` | regenerated (`--write --all-scenarios`); biogas and route `source`/`further_description` cells updated by hand in the central file, copies re-seeded |
| `scripts/walloon_scripts/BEWAL_potentials.py` | §2.3 |
| `scripts/build_common_parameters.py` | §2.4 |
| `test/test_bewal_biogas_cap.py` (new) | cap on the total, clipping, no forced generator, master CSV = bound + existing, generated files |
| `test/test_cabinet_batch.py` | route closed in the central and every copy, all six years; the twin re-opens it |
| `test/test_five_year_overlay.py` | 10-year write patches 2035/2045 (regression test of §2.4); biogas 2035/2045 values |
| `config/config.walloon.yaml`, `config/scenarios.walloon.yaml` | comments only (route, twin, noccsccgt, central) |
| `docs/biogas.md` (§1, §3, new §3.2, §4.4, §6, §7, §8.2), `docs/co2-sequestration.md` (update note) | documentation |

Nothing is committed. Helper scripts for this run are in
`/sylvain/mount/pypsa-wal-data/batch_20261006_scripts/`: the CSV edit (`edit_master_20261006.py`),
`smk_lowmem.sh` and `probe_central.sh`.

---

## 3. Pre-flight checks (done 2026-10-06, office computer)

| check | result |
|---|---|
| branch | `development_plan` fast-forwarded to `origin` = `f6d0f7aa`; the changes of §2.5 are uncommitted on top |
| `build_common_parameters.py --check --all-scenarios` (10-year grid) | **CHECK PASSED** |
| same check with `config/config.walloon_5y.yaml` | every input file in sync. **One pre-existing item**: the 5-year overlay's `budget_national` lacks the BEWAL 2040 = 15 % row of 4 Oct. Untouched: 4 Oct §4.1 says "revisit before any 5-year run" |
| per-file tabulation | route 0 in all six years in the central and 11 copies, 0 / 0 / 4 000 / 6 000 / 7 000 / 8 000 in the twin; biogas 1 019 / 2 145 / 3 363 / 4 667 / 5 800 / 6 933 everywhere |
| `pytest test` | **638 passed, 1 skipped** (2 min 24) |
| `DRY_RUN=1 RUN_NAME=scen_central nic5.sh prepare` | **5 jobs**: `prepare_sector_network` × 4 and `add_existing_baseyear` × 1, all triggered by `custom_potentials.csv`. No `retrieve_*`, cutout or renewable-profile rule. `add_brownfield` 2030+ runs on NIC5 |
| weather / resolution / `run.name` | 2010 everywhere, `1h`, `run.name` = the six batch scenarios (left as is; this run uses `RUN_NAME=scen_central`) |
| disk | `/` **83 %** (7.5 GB free): **above the 80 % abort threshold** (§5 step 1); `/home` 87 %; `/sylvain/mount` 6 % |
| RAM | 9.8 GB available with the desktop baseline |

### 3.1 Can the new biogas cap make a horizon infeasible? (checked before launch, 6 Oct)

**No.**
* **What biogas is forced into.** Biogas enters only two components: the optional and the forced
  BEWAL generators. Its only outlet is the `biogas to gas` upgrader, which is extendable.
  * No solve-time constraint references biogas (`solve_network.py`, `named_pins.py`, add-brownfield
    and base-year code).
  * Existing biogas power plants do not draw on the biogas bus.
  * The electricity import cap (`self_sufficiency`) counts AC/DC flows only, so more gas imports
    cannot bind it.
* **Forced volume against the cap.** `e_sum_min` is clipped to the cap together with `e_sum_max`,
  so the two can never cross (`test_bewal_biogas_cap.py`).
* **Hard CO₂ caps.** Constraint table of the 5 Oct central, read lazily from the NetCDF files:

  | | 2025 | 2030 | 2040 | 2050 |
  |---|---|---|---|---|
  | BEWAL national cap, Mt (dual €/t) | none (system cap only, −77) | 20.52 (**−77.9**) | 6.84 (−18.9) | 2.28 (0) |
  | BEWAL biogas used, 5 Oct, TWh | 1.45 forced | 8.30 + 0.93 forced | 4.00 | 6.90 |
  | BEWAL biogas used, **1 Oct** central, TWh | 1.45 forced | **0.93 forced only** | 0 | 6.90 |
  | new ceiling, TWh | 1.02 | 2.15 | 4.67 | 6.93 |

  * **2030 is the tight year.** The cap binds and about 7 TWh of biogas leaves (≈ +1.4 Mt). The
    1 Oct central met the **same 20.52 Mt cap with only 0.93 TWh** of biogas (dual −95.5 €/t).
    Since then the must-runs went, the rooftop floor rose and the 2 Oct export lowered demand,
    all of which relax 2030. So 2030 is feasible, with an expected dual between −78 and −95 €/t.
  * **2040 and 2050 ceilings only rise** (+0.67 and +0.03 TWh).
  * **The route closure has been solved before.** The 1 Oct central and the 4 Oct
    `scen_noccsccgt` both ran with the same caps and no route.
  * **2025** loses 0.43 TWh of forced biogas, about 0.09 Mt against a system cap of 1 471 Mt with
    every lever open.

**Why `/` grew** (71 % on 4 Oct): desktop applications, not the model. `~/.config/Cursor` 4.1 GB,
`~/.local/share/opencode` 2.0 GB (written today), `~/.cache` 1.8 GB (puppeteer 0.6, mozilla 0.7,
pip 0.3), Trash 0.6 GB, two Claude core dumps of 5 Oct 0.3 GB. The repo is 4.2 GB, of which
`data/` 3.1 GB (two old real `.vd` files, 155 MB). Nothing was deleted.

---

## 4. Expectations (hypotheses to check against the solve)

* **2025.** Forced Walloon biogas 1.45 → 1.02 TWh (TIMES 0.99): about 0.43 TWh more fossil gas.
  * The objective should stay within a few hundred M€ of 335 285.
  * The transmission fix does not act in the first horizon.
  * The 2025 upgrader built for the forced volume shrinks from 166 MW to about 116 MW, and this
    carries into later horizons.
* **2030. The large move.** The biogas ceiling is 2.15 TWh, against the 9.2 TWh run on 4 Oct.
  * About 7 TWh of 25 €/MWh biomethane is replaced, mostly by imported gas.
  * That is roughly +1.4 Mt of fossil CO₂ at the 0.198 t/MWh credit.
  * Check whether the BEWAL 2030 national cap (20.52 Mt) binds and what its dual does.
  * Biogas should sit on its cap (cheap at 25 €/MWh feedstock).
* **2040.**
  * Biogas cap 4.0 → 4.67 TWh. The 4 Oct central sat on 4.0, so expect 4.67.
  * The route was unused in 2040 on 4 Oct (endogenous price 47.6 €/t, below 71.8), so its
    closure should change nothing directly.
  * The transmission fix removes the ~0.72 bn€ re-payment and keeps DC floors. BEWAL–DE
    (ALEGrO corridor) stays at its 2040 build.
  * The BEWAL 2040 cap (6.84 Mt) was binding at −18.9 €/t; watch the dual.
  * CCGT CC returned in 2040 on 4 Oct (1.39 GW) **without** the route. It should survive here
    unless the 2030 path changes the economics.
* **2050. The route matters here.** Without its 8 Mt at 63.8 €/t, every Walloon tonne leaves by
  pipeline at the endogenous price (−332 €/t at `BEWAL co2 stored` on 4 Oct).
  * Expect power capture to recede: CCGT CC 1.9 TWh_e and CHP CC 1.0 → about 0. The 1 Oct central
    had none.
  * Expect more PV and storage, close to the 1 Oct "solar + storage" picture.
  * The TIMES industrial capture floor (5.12 Mt) still forces capture, so the CO₂ must still be
    exported.
  * Objective, order of magnitude: + ~2 bn€ for the disposal price, against noccsccgt −
    noccsccgt_route = +2.1 bn€ on 4 Oct. Minus ~0.8 bn€ for the transmission fix.
  * The `co2_disposal_own_capture_BEWAL` row must be absent in every horizon.
* **No new feasibility risk is identified.** The 4 Oct noccsccgt ran with the route closed and
  the same 2040 cap. The 2030 biogas cut leaves gas, PV and imports as levers.
* **Not pre-tested at 6 h.** No local 6 h chain was run.

---

## 5. Runbook (central only) — do NOT start before Sylvain's go

Per [`run_from_office_computer.md`](../../run_from_office_computer.md). One heavy local step at a
time. Drivers and logs off the scratchpad.

1. **Disk.** `/` is at 83 %, above the 80 % abort line. Free ≥ 2 GB, or accept it explicitly:
   * the run itself writes almost nothing to `/` (resources and results live on `/sylvain/mount`);
   * candidates: empty the Trash (0.6 GB), `~/.cache/puppeteer` (0.6 GB), `~/.cache/pip` (0.3 GB);
   * then re-check: `df -h / /home /sylvain/mount`.
2. **Commit** the changes of §2.5 (Sylvain), push, and check `git status -sb` is clean and equal
   to `origin`. Re-run `python scripts/build_common_parameters.py --check --all-scenarios` if
   anything changed since §3.
3. **Archive the 5 Oct central** on both sides (same disk locally, nothing is copied):

   ```bash
   mkdir -p /sylvain/mount/pypsa-wal-data/results/_archive_pre20261006
   mv results/walloon/scen_central /sylvain/mount/pypsa-wal-data/results/_archive_pre20261006/
   ssh nic5 "cd /scratch/ulg/thermlab/squoilin && mkdir -p pypsa-wal-archive/pre20261006 && mv pypsa-wal/results/walloon/scen_central pypsa-wal-archive/pre20261006/"
   ```

4. **Prepare, detached** (~6 min; 5 jobs per the dry run, plus whatever the commit adds):

   ```bash
   setsid nohup env RUN_NAME=scen_central LOCAL_RUN=/sylvain/mount/pypsa-wal-data/batch_20261006_scripts/smk_lowmem.sh \
       ./cluster/nic5.sh prepare > cluster/logs/prepare_central_20261006.out 2>&1 < /dev/null &
   ```

   * Check the `.out` 30 s later.
   * Wait for `5 of 5 steps (100%) done`.
   * Then check the 2025 log `logs/walloon/scen_central/add_existing_baseyear_base_s_adm___2025.log`
     for two lines: `CO2 disposal service at BEWAL: closed this horizon.` and
     `BEWAL biogas cap on the total: 1.019 TWh = 1.019 forced (unsustainable) + 0.000 optional.`
5. **Partition and push:**
   * `ssh nic5 "sinfo -p batch,hmem -o '%P %a %D %t %C %m'"`;
   * then `RUN_NAME=scen_central ./cluster/nic5.sh push`.
6. **Solve:** `RUN_NAME=scen_central ./cluster/nic5.sh solve` (`batch`, 16 CPUs, 80 GB, 12 h).
   Expected chain ≈ 6.5 h: 2025 ≈ 3.1 h, then ≈ 1 h per horizon.
7. **Probes:** `/sylvain/mount/pypsa-wal-data/batch_20261006_scripts/probe_central.sh`.
   * It shows the queue, the orchestrator tail, the optimal / trouble counts and the route lines
     of the NIC5 `add_brownfield` logs.
   * The route must read `closed this horizon` in **all four** horizons.
8. **Pull and verify:** `RUN_NAME=scen_central ./cluster/nic5.sh pull`, then check:
   * 4 networks;
   * `grep -c 'Optimal objective' results/walloon/scen_central/logs/*_solver.log` totals 4;
   * the biogas line in each horizon's log.
9. **Post-process, capped, local pages only:**

   ```bash
   SKIP_S3_UPLOAD=1 HTML_PUBLISH=0 LOCAL_CORES=4 RUN_NAME=scen_central cluster/capped.sh 14G post -- ./cluster/nic5.sh postprocess
   ```

10. **Review, one script at a time, capped:**
    * scripts: `review_run.py` (8G), `check_heat_profile_fidelity.py`, `ptx_report.py`,
      `network_cost_report.py`, `bill_harmonisation.py`;
    * write §9–§11 here, with the expectations of §4 checked one by one.
11. **Publication: only after the review and Sylvain's go.**
    * Set `UPLOAD_DATE=<YYYYMMDD>`; it defaults to the day of upload and must not be `20261005`.
    * Then run `HTML_PUBLISH=1 SKIP_S3_UPLOAD=1 … nic5.sh postprocess`, `nic5.sh extract` (capped
      10G) and `nic5.sh upload`, with `RUN_NAME=scen_central`.
    * Verify with `run_from_office_computer.md` §7.4: 53 files, none empty, HTTP 200.

---

## 6. For the follow-up relaunch of the other scenarios

The data files are already regenerated for every scenario (`--write --all-scenarios`). What each
one gets:

| scenario | route | biogas cap | note |
|---|---|---|---|
| `scen_noccsccgt` | closed, all six years (2035/2045 now too) | new | noccsccgt − central is the power-CC ban again (plus its own `.vd`) |
| `scen_noccsccgt_route` | **open** at TIMES's volumes (explicit override) | new | = noccsccgt + route. It no longer brackets the central; keep, drop, or replace by "central + route" (§7 item 2) |
| `scen_retardnucleaire`, `scen_biomethane_industrie`, `scen_realiste` | closed (inherited) | new | — |
| `scen_test_lowccs_ptx` | closed (reads the central files) | new | its lever-D export cap counted the route; now pipelines only |

The transmission fix `f6d0f7aa` applies to all of them. `run.name` already lists the six batch
scenarios. The 4 Oct NIC5 clone `pypsa-wal-sens2` can take them again after an archive of its
trees (4 Oct §9.8 pattern).

---

## 7. Open questions

1. **Sylvain: the biogas 2040/2050 values.** I applied ICEDD's "+2.7 PJ" consistently, so 2040 goes
   4.0 → 4.67 TWh and 2050 6.90 → 6.93 TWh. The alternative keeps 4.0 in 2040 (new digesters
   only), but that is inconsistent with the other years. Confirm before the launch.
2. **Sylvain: `scen_noccsccgt_route` in the next batch?** It now means "noccsccgt + route". A
   "central + route" twin would show what closing the route costs; it is the 5 Oct central plus the
   biogas and transmission changes.
3. **Sylvain: `/` at 83 %** (§5 step 1).
4. **ICEDD (FYI):** PyPSA's cap uses TIMES's own existing biogas (2.67 → 2.32 PJ, with landfill gas
   declining), not a flat 2.7 PJ. Worth one line in the reply to Annick.
5. **Carried over from 4 Oct** (§8 there): 2 574 kt; `CO2STG01` 2035 bound (moot while the route is
   closed); Tihange 3 / retardnucleaire new build; réaliste re-export; `Hgt_COST_storage_CO2`
   export (moot while the route is closed).

---

## 9. Run record

### 9.1 Identification

| Field | Value |
|---|---|
| Date of run | 2026-10-06 16:26 (prepare) → 23:41 (last post-processing); solves 16:28 → 22:53 (CEST) |
| Operator | Sylvain Quoilin (decisions, go); driven by Claude (Opus 5.5) from the office computer, probes every 20 min |
| Run name / prefix | `scen_central` / `walloon` (`RUN_NAME=scen_central`; `run.name` still lists the six batch scenarios) |
| Config file(s) | `config/config.walloon.yaml` + `config/scenarios.walloon.yaml` (+ `cluster/config_cluster.yaml` on NIC5) |
| Code version | pypsa-wal `f6d0f7aa` + the **uncommitted** working tree of §2.5 (saved as `batch_20261006_scripts/worktree_at_launch.patch`); TIMES_PyPSA and pypsa2html unchanged (`c6f93e2`, `1b8f662`) |
| Outcome | **success**: 4/4 optimal, 0 numerical trouble; post-processing complete (11/11 rules, HTML via a bounded-memory rebuild, §10.2 I1); not published |

### 9.2 Goal

Re-run the central on the same 2 Oct TIMES export with three changes:
* the CO₂ disposal route closed in every horizon;
* ICEDD's biogas cap applied to total biogas in every horizon (§2.2);
* the transmission brownfield fix `f6d0f7aa`.

If accepted, relaunch the sensitivities on the same inputs (§6).

### 9.3 Main parameters

As 4 Oct §9.3 (2010 weather, `europe-2010-sarah3-era5`, 8 760 h, `1h`, 2025–2030–2040–2050
myopic, `adm`, BE FR GB NL DE LU, Gurobi barrier 16 threads, `crossover 0`, `BarConvTol 1e-5`,
`BarHomogeneous 1`, BEWAL caps 20.52 / 6.84 / 2.28 Mt). Differences: route volume 0 everywhere;
biogas caps of §2.2; TIMES `.vd` unchanged (`scen_central_v01_261002_0210.vd`).

### 9.4 Execution — where and how

| Phase | Where | Notes |
|---|---|---|
| Prepare | office computer | `nic5.sh prepare` with `LOCAL_RUN=smk_lowmem.sh` (`--resources mem_mb=20000`); 5 jobs, 35 s |
| Push | office → NIC5 `pypsa-wal` | verified on the cluster copy (§9.x) |
| LP solve | NIC5 `batch` | 16 CPUs, 80 GB, 12 h; every job RUNNING within about a minute; nodes w034, w058, w001, w015 |
| Pull | NIC5 → office | `nic5.sh pull` per tree, 876 MB |
| Post-processing | office | `post_central.sh`: each step in `cluster/capped.sh`, cap = min(budget, available − 2 GB), strictly sequential. Summaries, CSVs, plots, TIMES Sankeys and indicators via `nic5.sh postprocess` (`HTML_PUBLISH=0 SKIP_S3_UPLOAD=1`, 4 cores) |
| HTML (pypsa2html) | office | OOM-killed inside its 10 GB cgroup in `postprocess`; rebuilt alone by `html_lowmem.py` (network caches bounded to 2, central only), then `write_html_hub` alone (§10.2 I1–I2) |
| Review scripts | office | `network_cost_report.py`, `bill_harmonisation.py`, `review_run.py`, `check_heat_profile_fidelity.py`, `ptx_report.py`, `keys_20261006.py`; logs `cluster/logs/*_scen_central_20261006.*` |
| Publication | not run | awaits Sylvain's go |

### 9.5 Timings

| step | duration |
|---|---|
| prepare / push | 35 s / < 1 min |
| solve 2025 | 570 it, 9 457 s = **2.6 h** (5 Oct: 717 it, 3.1 h) |
| solve 2030 / 2040 / 2050 | 216 it, 1.07 h / about 200 it, 0.97 h / 204 it, about 0.95 h. The 2050 dual residual was 3 orders of magnitude slow early, then caught up by it. 170 |
| whole chain | 16:28 → 22:53 = **6.4 h** (5 Oct: 6.4 h) |
| pull | < 1 min |
| `postprocess` (without HTML) | 7 min (22:54 → 23:01) |
| review scripts | 2 min (23:01 → 23:03) |
| pypsa2html, bounded | 36 min (23:05 → 23:41), 81 pages |

### 9.6 Resource usage

* NIC5: 80 GB requested; peak in `*_memory.log` not read this time (4 Oct: 33.8 GB).
* Office computer, cgroup peaks:
  * `postprocess` up to the HTML rule: 9.7 GB (killed at the 9.98 GB cap in pypsa2html);
  * pypsa2html bounded: **7.8 GB**;
  * review: 4.6 GB;
  * network costs: 3 GB;
  * PtX: 3 GB;
  * bill: 2.7 GB;
  * heat fidelity: 2 GB;
  * key figures: 1.7 GB.
* Available RAM never fell below 6.5 GB. `/` stayed at 83 %, `/sylvain/mount` 6 → 11 %.

### 9.7 Results (BEWAL unless stated; Δ against the 5 Oct central)

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| objective, M€ | 335 278 (−7) | 374 491 (−76) | 264 333 (**−1 017**) | 285 199 (**+1 467**) |
| biogas used, TWh (cap) | 1.019 forced (1.019) | 0.927 + 1.218 (2.145) | **2.145** (4.667) | 6.933 (6.933) |
| *5 Oct biogas, TWh* | *1.452* | *9.23* | *4.00* | *6.90* |
| route flow, Mt | 0 | 0 | 0 (5 Oct: 0) | **0** (5 Oct: 8.0) |
| BEWAL `co2 stored` price, €/t | −37.5 | −119.6 | −47.2 (−47.6) | −340.2 (−332.0) |
| system CO₂ price / BEWAL cap dual, €/t | −77.5 / – | −93.2 / **−84.5** (−77.9) | −112.7 / −19.5 (−18.9) | −653.6 / 0 (−645 / 0) |
| BEWAL capture, Mt | 0 | 1.28 (process) | **10.57** (10.3) | 8.42 (8.4) |
| of which CCGT CC / gas CHP CC | – | – | 1.94 / 0 (1.58 / 0) | 0.76 / 0.45 (0.63 / 0.46) |
| CCGT CC, GW_e (vintage) / TWh_e | – | – | 0.98 (2040) / 5.89 (0.79 / 4.78) | 0.98 (2040) / 2.30 (0.79 / 1.92) |
| unabated CCGT, TWh_e | 8.36 | 9.04 | 9.44 (10.8) | 1.81 (2.1) |
| ground PV / rooftop / onwind, GW | 0.91 / 1.77 / 1.57 | 0.91 / 4.75 / 3.97 | 4.65 / 11.03 / 6.5 (4.38 / – / 6.5) | 13.0 / 12.14 / 6.5 (13.0 / 12.1 / 6.5) |
| battery dischargers, GW | 0.29 | 0.42 | 1.32 (1.16) | 5.17 (5.33) |
| FT + methanolisation in BEWAL, TWh | 0 | 0 | 0 | 0 |
| storage in CO2StoP sites, Mt (DE / GB / NL) | – | 50.9 / – / 9.1 | 79.2 / 100 / 9.1 | 79.2 / 100 / 9.1 |
| `biomass limit` dual, €/MWh | | | −28.1 | **−987.9** |

Key figures from `keys_20261006.py` (log `cluster/logs/keys_scen_central_20261006.log`) and
`ptx_report.csv`; 5 Oct values from 4 Oct §9.7 and the archived networks.

### 9.x Chronology (office computer, 6 Oct 2026; clock = CEST)

* **Provenance.** Launched on HEAD `f6d0f7aa` **plus the uncommitted working tree of §2.5**,
  saved to `/sylvain/mount/pypsa-wal-data/batch_20261006_scripts/worktree_at_launch.patch` (with
  `HEAD_at_launch.txt` and a copy of the new test and of this log).
* **Archives.**
  * local `results/walloon/scen_central` → `/sylvain/mount/pypsa-wal-data/results/_archive_pre20261006/`;
  * NIC5 `pypsa-wal/results/walloon/scen_central` → `pypsa-wal-archive/pre20261006/`;
  * the NIC5 `logs/walloon/scen_central/` still holds the 4 Oct rule logs until overwritten; the
    probe filters on mtime.
* **Disk at launch.** `/` was at 83 %, above the runbook's 80 % line. Sylvain was told and
  launched anyway: the run writes to `/sylvain/mount`.
* **16:26–16:27 prepare.** `RUN_NAME=scen_central`, `LOCAL_RUN=smk_lowmem.sh`, 5 of 5 steps.
  * `prepare_sector_network` took 12 s per horizon. The networks are 9 MB compressed but complete
    (8 760 snapshots, 257 buses).
  * 2025 log: `BEWAL biogas cap on the total: 1.019 TWh = 1.019 forced (unsustainable) + 0.000
    optional.` and `CO2 disposal service at BEWAL: closed this horizon.`
* **Push.** The cluster copy shows the new biogas and route rows in all six years, both code
  changes and the fresh prepared networks.
* **16:28 solve.** `sinfo`: 5 `batch` nodes with ≥ 16 idle cores and ≥ 90 GB free. Orchestrator
  pid 2071782; job 11287791 (2025) RUNNING on nic5-w034 within about a minute.
* Probes every 20 min: `probe_central.sh`.
* **2025** (job 11287791, nic5-w034): 16:29 → 19:07. **Optimal 3.35278059e11**, 570 barrier
  iterations, 9 457 s (5 Oct: 717 it, 3.08 h, 3.35285e11). Slow but monotone tail, no trouble.
* **2030** (job 11288560, nic5-w058): about 19:16 → 20:21. **Optimal 3.74491094e11**, 216 it.
  * Log: `BEWAL biogas cap on the total: 2.145 TWh = 0.927 forced (unsustainable) + 1.218 optional.`
    and the route closed.
  * The objective is −76 M€ against 5 Oct (3.74567e11). It is not like-for-like: the
    transmission fix acts from 2030.
* **2040** (job 11288704, nic5-w001): 20:29 → about 21:33. **Optimal 2.64333337e11**, about 200 it.
  * The route is closed. There is no biogas split line, because no forced generator exists from
    2040.
  * −1.02 bn€ against 5 Oct (2.65350e11).
* **2050** (job 11288849, nic5-w015): from 21:46.
  * The dual residual started about 3 orders of magnitude above the 5 Oct 2050 at the same
    iteration (39 vs 1.2e-2 at it. 80).
  * It fell monotonically and had caught up by iteration 170 (1.6e-3).
  * It. 204 at 22:43, primal = dual = 2.85199e11 (5 Oct: 2.83732e11).
* **22:51 2050 optimal: 2.85199407e11.** Orchestrator `7 of 7 steps (100%) done` at 22:53, no
  error; 0 numerical-trouble messages in all four solver logs.
* **22:53 pull** (`RUN_NAME=scen_central nic5.sh pull`): 4 networks (217–241 MB), 876 MB in total.
* **Network checks** (lazy NetCDF read):

  | | 2025 | 2030 | 2040 | 2050 |
  |---|---:|---:|---:|---:|
  | BEWAL biogas, forced: cap / used, TWh | 1.019 / 1.019 | 0.927 / 0.927 | — | — |
  | BEWAL biogas, optional: cap / used, TWh | 0 / 0 | 1.218 / 1.218 | 4.667 / **2.145** | 6.933 / 6.933 |
  | BEWAL `co2 sequestered` capacity, Mt | 0 | 0 | 0 | 0 |
  | `co2_disposal_own_capture_BEWAL` row | absent | absent | absent | absent |
  | BEWAL national cap dual, €/t | (no cap) | **−84.5** | −19.5 | 0 |

  * **2040 uses 2.145 TWh of its 4.667 TWh cap**, exactly what the upgraders built in 2030 can
    deliver: no new biogas chain is built in 2040. TIMES runs 4.67 TWh.
  * The 2030 dual falls inside the −78 … −95 €/t range expected in §3.1.
* **22:54 post-processing started** (`post_central.sh`, detached; capped at available − 2 GB).
* **22:3x: the Claude session restarted** and the monitors were lost. It was not a crash of the
  machine: no reboot, no `claude-desktop` core dump, 12 GB available. NIC5 was untouched (§7.3
  check at 22:43).

## 10. Publication, issues and follow-ups

### 10.1 Publication (7 Oct 2026, 07:29 → 08:09, `UPLOAD_DATE=20261007`)

Driver `batch_20261006_scripts/publish_central.sh`, strictly sequential, each step capped; log
`cluster/logs/publish_scen_central_20261007.log`.
* **Destinations:** internal pages and the **test** Explorer only, Sylvain's policy of 5 Oct. The
  official Wal Explorer (`prod/`) was not touched.
* **The 20261005 sets stay online** unchanged.

| step | result |
|---|---|
| HTML: `postprocess` with `HTML_PUBLISH=1` | the standard `generate_html_report` rule with the **fixed pypsa2html** (`network_cache_size: 2`, central only), **8.0 GB peak**, exit 0. **https://pypsa.squoilin.eu/scen_central_20261007/**: hub and `pypsa/index.html` HTTP 200 |
| Explorer extraction (`nic5.sh extract`) | exit 0, 8.1 GB peak, `Extraction complete` |
| cost-segment plot | exit 0 |
| S3 upload (`nic5.sh upload`) | Explorer folder `test/scenarios/times-pypsa__scen_central-2010-1h__20261007/`: **53 files, 0 empty**, with the `.vd` (`times/scen_central_v01_261002_0210.vd`, 64.3 MB). Raw results `test/pypsa_raw_results/20261007_walloon_scen_central/`: 318 files. The 1 empty file is `logs/make_cumulative_costs.log`, empty by nature and identical on 5 Oct |

**Before pointing anyone at the pages, read §11.** In particular:
* R1: the route reading;
* R2: 2040 biogas;
* R4: no deltas against 5 Oct.

The page carries the central alone, with no comparison against the 4 Oct sensitivities (I2).
Explorer dropdown: not verified.

### 10.2 Issues and fixes

| # | symptom → cause | fix |
|---|---|---|
| I1 | `postprocess`: 9 of 11 rules done, `generate_html_report` **OOM-killed inside its 9.98 GB cgroup** (exit 143; journal `oom-kill`). The desktop was untouched. Cause: pypsa2html's process-wide `_PATH_CACHE` (limit 24) keeps every loaded network resident whatever `model.network_cache_size` says, so four 1 h networks plus other scenarios' networks ≈ 10 GB | `html_lowmem.py` (in `batch_20261006_scripts/`) reproduces the rule with both caches bounded to 2: **7.8 GB peak, 36 min, 81 pages, same file list as 5 Oct**. Then `snakemake --cleanup-metadata` on the report and `write_html_hub` alone (dry run first: 1 job) |
| I2 | **The single-scenario report also loads every scenario of `config/pypsa2html.yaml` that has a tree on disk** (`charts/scenario.py:scenario_contexts`). The trees there are the **4 Oct** sensitivities (route open, no transmission fix, old biogas cap), so the central's comparison charts would have drawn them as comparable | the bounded rebuild keeps **only `scen_central`** (the policy stated in `config/pypsa2html.yaml`: other vintages stay out until re-run). Re-enable the comparison when the sensitivities are re-run |
| I3 | about 22:35 the Claude session restarted and the probe monitors were lost | §7.3 check at 22:43: no reboot, no `claude-desktop` core dump, 12 GB available; NIC5 untouched; monitors re-armed |
| I4 | `/` at 83 % (abort line 80 %) | launched on Sylvain's go; the run wrote nothing measurable to `/` |
| I5 | `review_run.py` exits 1 | normal: it returns 1 whenever FAILs exist (the 9 standing corridor rows) |
| I6 | the probe's first version showed the 4 Oct `add_brownfield` route lines (old logs still on NIC5) | the probe filters on mtime (`-newermt 2026-10-06 16:20`) |

### 10.3 Follow-ups

1. **Commit** §2.5 and the new test (Sylvain); the log itself was committed on 7 Oct. The run's
   provenance is `f6d0f7aa` + patch.
2. ~~Decide on publication~~ (done 7 Oct, §10.1). Relaunch the sensitivities (§6):
   `scen_noccsccgt_route` is still open (§7 item 2). Re-enable each one in `config/pypsa2html.yaml`
   once it is re-run.
3. ~~**pypsa2html** (separate repo): make `_PATH_CACHE` honour `network_cache_size`~~ **Done
   7 Oct (uncommitted in `/sylvain/git/pypsa2html`).**
   * `networks.py`: the process-wide cache is the only owner of loaded networks, and
     `NetworkCache` is an index into it. `set_path_cache_max()` is applied by `build_site` from
     `model.network_cache_size` and restored afterwards; null keeps 24.
   * Tests: `tests/test_network_cache.py`, 7 tests; the suite gives 409 passed.
   * pypsa-wal `config/pypsa2html.yaml`: `network_cache_size: 2`; the five 4 Oct sensitivities
     are commented out (other vintage, I2).
4. Add the measured peaks (pypsa2html bounded 7.8 GB, unbounded > 10 GB) to
   `run_from_office_computer.md` §7 *(done 6 Oct: measured-peaks table and the pypsa2html note below it)*.
5. The review findings below (R1–R6) and their follow-ups.

## 11. Critical review

Following [`../run-review-checklist.md`](../run-review-checklist.md), on the solved tree
`results/walloon/scen_central` (6 Oct). Scripted half first, then the judgement levels by hand:

```bash
PYTHONPATH=. python scripts/walloon_scripts/review_run.py results/walloon/scen_central
python scripts/walloon_scripts/check_heat_profile_fidelity.py scen_central live
PYTHONPATH=. python scripts/walloon_scripts/ptx_report.py results/walloon/scen_central --out results/walloon/scen_central/csvs/ptx_report.csv
```

Logs `cluster/logs/{review,heatfid,ptx,keys,netcost}_scen_central_20261006.log`. The CCGT CC
analysis of R1 is in `cluster/logs/ccgtcc_{2040,swap,levers}_20261007.log`; its scripts
(`ccgtcc_2040.py`, `ccgtcc_swap.py`, prices in `ccgtcc_2040_prices*.pkl`) are in
`/sylvain/mount/pypsa-wal-data/batch_20261006_scripts/`.

**Reviewed by / date:** Claude (Opus 5.5), 2026-10-06 23:50 (scripted levels) and 2026-10-07
(judgement levels, R1 analysis). **Not yet read by Sylvain.**

**Headline counts:** `170 PASS · 14 WARN · 9 FAIL` (+ 30 INFO) from `review_run.py`. These are the
same counts and the same WARN/FAIL kinds as the 5 Oct central.

| Level | Verdict |
|---|---|
| 0 provenance | **pass with a caveat.** Solved on `f6d0f7aa` + the uncommitted working tree of §2.5 (saved as `worktree_at_launch.patch`); `.vd` `scen_central_v01_261002_0210` in all four `configs/`; potentials file on NIC5 checked before the solve. HTML published with pypsa2html `1b8f662` + an uncommitted cache fix (reporting only) |
| 0b commit intent | **pass**, table below |
| 1 solve | **pass.** 4/4 optimal, barrier, crossover 0, 0 numerical-trouble messages; Gurobi conditioning WARN in every horizon (as always). 2050 dual residual slow early, caught up by it. 170 |
| 2 TIMES soft link | **pass with the standing caveat.** Rooftop floor met (4 749 MW in 2030); import cap binding (2.94 / 6.47 / 10.0 TWh, dual −0.1 / −6.3 / −5.9 €/MWh). Heat: 2 groups < 98 % delivered (1.17 TWh_th), both 2050 biomass boilers (64.7 % undelivered), the biomass corner of R6 |
| 3 accounting identities | **pass.** WARN `enc_pe` 7.2 / 9.7 / 10.1 / 5.7 TWh, the usual primary-energy bookkeeping artefact; heat load closes to 2.4e-6 TWh |
| 4 constraint compliance | **pass.** BEWAL caps: 2030 binding (−84.5 €/t), 2040 binding (−19.5), 2050 slack. Biogas caps exactly as designed (1.019 / 2.145 / 4.667 / 6.933 TWh). Route closed in all four horizons (no `co2 sequestered` capacity at BEWAL, no own-capture row). The 9 FAILs are the standing non-Walloon nuclear-corridor rows (NL 515 vs 485; GB 8 664 vs 5 900 and 4 690 vs 2 800; FR 59 758 vs 54 000; DE `max 0` × 4), identical to 30 Sep / 4 Oct |
| 5 realism | **pass with caveats.** Build-rate WARNs as before (onwind +480 MW/a 2025→30, ground PV +835 MW/a 2040→50, rooftop +596 / +628 MW/a). **CCGT CC carries no steam-cycle penalty** (η 0.571 against 0.59 for a new CCGT, literature about −7 pp): R1 |
| 6 prices / costs | **pass.** Effective BEWAL CO₂ price 178 / 132 / 654 €/t (2030 / 40 / 50); `BEWAL co2 stored` −120 / −47 / −340 €/t; `biomass limit` −28 / **−988 €/MWh** (2040 / 2050). New CCGT CC and new CCGT both recover exactly 100 % of capex in 2040 (consistent LP). 18 bill-harmonisation gaps beyond tolerance (as on 5 Oct) |
| 7 TIMES consistency | **mixed.** Power capture 2040: 0.98 GW_e / 1.94 Mt against TIMES's 1.02 GW CCGT CCS retrofit / 1.86 Mt, close (R1). Biogas 2025 / 2030 / 2050 on TIMES's level, **2040 at 2.15 against 4.67 TWh** (R3). Disposal 47 €/t in 2040 against TIMES's 71.8 €/t chain and 109 €/t `CO2STOCK` shadow price (R1) |
| 8 robustness | **weak.** CCGT CC sits exactly at the margin (R1); the deltas against 5 Oct mix three input changes (R5); no ablation or 6 h check of this run |

### Commit intent (level 0b)

Previous production log: [`2026-10-04_cabinet_batch_20261002_2010_1h.md`](2026-10-04_cabinet_batch_20261002_2010_1h.md)
at SHA `eb67828d`. `git log eb67828d..f6d0f7aa`, plus the uncommitted working tree. TIMES_PyPSA is
unchanged (`c6f93e2`); pypsa2html is `1b8f662` + an uncommitted fix (reporting only).

| commit | class | intended behaviour | observable in this tree | result |
|---|---|---|---|---|
| `a81ab6e7` log of the 4 Oct batch | docs | — | — | n/a |
| `f6d0f7aa` DC carry-forward + no re-payment of built transmission | physics | DC links keep earlier builds; carried capacity becomes existing capacity | every DC link's `p_nom` = `p_nom_min` = previous horizon's `p_nom_opt` (e.g. `relation/2127794` 2 000 → 2 800 → 2 800 → 2 800; `8185487` 1 000 → 1 000 → 2 400 → 2 400). On 5 Oct they restarted at today's grid each horizon (`relation/10377412` 1 400 → 1 000 → 1 400). Objective −1.0 bn€ in 2040, consistent with the commit's −0.72 bn€ replay plus the biogas effect | **pass** |
| working tree: route closed (§2.1) | config | volume 0 in every horizon, 2035/2045 rows included | `closed this horizon` in the four logs; no capacity; no own-capture row | **pass** |
| working tree: biogas cap on the total (§2.2–2.3) | physics / config | ICEDD bound + existing biogas, forced + optional together | network `e_sum_max` and the log line exactly so; forced 2025 clipped 1.452 → 1.019 TWh | **pass** |
| working tree: 2035/2045 rows (§2.4) | tooling | 10-year write keeps 5-year rows in sync | `--check` on both grids; regression test | **pass** (not observable in a 10-year solve) |
| pypsa2html fix (uncommitted, 7 Oct) | reporting | `network_cache_size` bounds RAM process-wide | `generate_html_report` 8.0 GB peak in `postprocess` (OOM-killed at 10 GB before) | **pass** (no effect on results) |

### Findings

#### R1. CCGT with capture enters the 2040 mix as the cheapest way to meet the 15 % Walloon cap, and only because disposal is cheap and the steam-cycle penalty is missing

**What was observed.**

| BEWAL, 2040 | 1 Oct central (30 Sep batch) | 5 Oct central | **6 Oct central** | TIMES-WAL 2 Oct |
|---|---:|---:|---:|---:|
| CCGT CC built, GW_e (2040 vintage) | **0** | 0.79 | **0.98** | 1.02 (retrofit) |
| CCGT CC output, TWh_e / load factor | 0 | 4.78 / 0.69 | 5.89 / 0.69 | |
| captured on CCGT, Mt | 0 | 1.58 | 1.94 | 1.86 |
| new unabated CCGT 2040, GW_e | 3.19 | 1.58 | 1.32 | |
| capex recovery of new CCGT CC at the run's prices | **94 %** | 100 % | 100 % | |

* **A 2040 investment that keeps running.** The 2050 CCGT CC output (2.30 TWh_e) is this 2040
  vintage still running; nothing is built in 2050 (R2).
* **Earlier history.** The 13 Sep central also built CCGT CC in 2040 (0.71 GW as reported in the
  4 Oct log §7.1). The 30 Sep batch lost it; it is not re-analysed here.

**How the plant pays for itself.** Both new CCGT CC and new unabated CCGT recover exactly 100 % of
their capex from their 2040 energy margin. That is the LP's optimality condition, checked port by
port; there is no capacity payment. Per MW of gas input per year, 6 Oct:

| kEUR/MW_th/a | electricity | − fuel | − CO₂ emitted | − disposal | − VOM | = margin | capex | hours run | price when running |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CCGT CC | 425.9 | 194.5 | 7.9 | 53.7 | 19.5 | **150.3** | 150.3 | 6 014 | 124 €/MWh |
| unabated CCGT | 337.6 | 135.8 | 109.4 | 0 | 13.5 | **78.8** | 78.8 | 4 179 | 137 €/MWh |

The two compete for the same new Walloon dispatchable capacity: 2.3–2.4 GW_e of new gas on
5/6 Oct (CCGT + CCGT CC), against 3.2 GW_e of new unabated CCGT on 1 Oct.

**The decisive quantity is the spread: the Walloon CO₂ price minus the disposal price.**
* The Walloon CO₂ price is the system price plus the Walloon cap dual.
* An unabated MWh pays the Walloon CO₂ price on 0.34 t, through the electricity price that
  Walloon gas sets.
* A captured MWh pays the disposal price on 0.33 t instead.

| 2040, €/t | system CO₂ | + Walloon dual | − disposal (`BEWAL co2 stored`) | = **spread** | CCGT CC |
|---|---:|---:|---:|---:|---|
| 1 Oct | 131.6 | 7.3 | 63.0 | **75.9** | 94 %, not built |
| 5 Oct | 113.1 | 18.9 | 47.6 | 84.4 | built |
| 6 Oct | 112.7 | 19.5 | 47.2 | **85.1** | built (at the margin) |

* **Break-even.** One €/t of spread is worth 0.75 % of CCGT CC capex (1 131 t captured per MW_th
  and year). So the break-even spread is about **84 €/t**. On 1 Oct the spread was 8 €/t short.

**Why it did not appear at the end of September.**
* **The cap.** The 1 Oct central had the BEWAL 2040 cap at 25 % of 1990 (11.4 Mt), almost slack:
  dual −7.3 €/t.
* **Breakdown of the change from 1 Oct to 5 Oct (+8.5 €/t of spread):**
  * Walloon dual **+11.6 €/t**: the cap went from 25 % to 15 % (6.84 Mt, TIMES's own 2040
    tonnage), decided 4 Oct;
  * system CO₂ price −18.5 €/t;
  * disposal price −15.4 €/t.
* **Why the last two cancel.** The six-country storage ceilings bind in 2040 (DE 79.2, GB 100,
  NL 9.1 Mt). The disposal price is mostly a storage scarcity rent, and it fell with the system
  CO₂ price. Net −3.1 €/t.
* **What moved the system price** (the biogas cost fix applied Europe-wide, PtX must-runs removed,
  2 Oct export) is not attributed.
* **So the 15 % cap is the driver**, as 4 Oct F3 said, but through the spread.
* **Price swaps confirm it:**
  * the disposal price alone moves the 6 Oct plant from 100 % to 88 % (with 1 Oct's) and the
    1 Oct plant from 94 % to 106 % (with 6 Oct's);
  * the electricity prices move the other way (1 Oct's carbon price was higher);
  * gas price and the residual-emission terms change recovery by 1 % or less.
* **5 Oct → 6 Oct (+0.18 GW_e).** 2040 biogas fell from 4.0 to 2.15 TWh (R3). That is about
  0.37 Mt less biogenic credit against the Walloon cap, the dual rose by 0.6 €/t, and more
  capture followed.

**CCGT CC is the marginal Walloon abatement option in 2040, and by a wide margin.**
* **Its cost sets the dual.** The 19.5 €/t Walloon dual is CCGT CC's own cost premium.
* **Without power-plant capture the dual is −75.2 €/t** (4 Oct `scen_noccsccgt`, 2040: system
  113.2, disposal 46.6, spread 141.9 €/t). At those prices the same plant recovers **144 %**.
* **Consequence.** A lever that only nudges CCGT CC's cost will shrink it and raise the Walloon
  dual, not remove it. With a binding cap the true outcome lies between the two price sets.

**What it should be: two parameters that favour CCGT CC and are not defensible as they stand.**
1. **The steam-cycle penalty is not modelled.**
   * `ccgt_cc_link_params()` takes the DEA `biomass CHP capture` sheet but charges only its
     electricity and compression inputs (0.023 + 0.075 MWh/t), not its **0.66 MWh_th/t
     heat-input**. That heat is the reboiler steam, which in a CCGT comes out of the steam cycle.
   * PyPSA: η 0.571 against 0.590 for a new CCGT (−1.9 pp). IEAGHG: about −7 pp (≈ 58 → 51 %).
   * Already listed as "Not modelled. Typical add-on: −7 pp" in `docs/ccs_alignment.md`
     (steam-cycle row).
2. **Walloon onshore collection is not charged on pipeline exports.**
   * TIMES charges every Walloon tonne 13.8 €/t for collection and the backbone
     (`STORAGEMININD` / `STORAGEMINELC`). PyPSA charges it only on the TIMES route, now closed.
   * PyPSA's 2040 disposal price (47 €/t) is below TIMES's full chain (71.8 €/t) and TIMES's own
     `CO2STOCK` shadow price (109 €/t).
   * The 22 Sep decision to drop lever C (year-dependent `co2_sequestration_cost`, now 30 €/t)
     rested on a 2040 price of 88.8 €/t. At 1 h that premise has reversed (47 €/t).

**Levers other than the ban.** Free-dispatch capex recovery of the 6 Oct CCGT CC. Price-taking,
single-year estimates, bracketing the equilibrium between the central's prices and the no-CC
prices:

| lever | at 6 Oct prices | at no-CC prices (4 Oct noccsccgt) | reading |
|---|---:|---:|---|
| none (as modelled) | 100 % | 144 % | |
| steam-cycle penalty −7 pp (η 0.501) | 67 % | 102 % | CC much smaller, maybe not zero |
| steam-cycle penalty −4 pp | 81 % | 120 % | shrinks |
| onshore collection +13.8 €/t on captured Walloon CO₂ | 90 % | 132 % | shrinks |
| disposal at TIMES's full chain, 71.8 €/t | 82 % | 123 % | shrinks |
| disposal at TIMES's 2040 `CO2STOCK` shadow, 109 €/t | 58 % | 96 % | likely out |
| capex +25 % (e.g. a CCS risk premium) | 80 % | 115 % | shrinks |
| capture rate 0.90 instead of 0.95 | 97 % | | marginal |
| **−7 pp and +13.8 €/t together** | **57 %** | **92 %** | **out even at the no-CC dual** |
| BEWAL 2040 cap looser | | | out when the Walloon dual falls below **≈ 18.5 €/t** (at 6 Oct system and disposal prices): back to 25 % (1 Oct: no CC), or roughly a cap raised by the 1.94 Mt CCGT CC removes (≈ 8.8 Mt, ≈ 19 %); not solved |
| relax the electricity import cap / add other firm Walloon capacity | | | fewer CCGT CC hours (load factor now 0.69) and a lower dual; not quantified |

**Why it matters and what to do.**
* **Keeping CCGT CC out has a cost.** It means meeting the 15 % cap with the next-best options at
  a Walloon dual of about 75 €/t. In 2040 that is what `scen_noccsccgt` already shows.
* **The present result is TIMES-consistent.** TIMES-WAL builds 1.02 GW of CCGT CCS retrofit with
  1.86 Mt/a from 2040.
* **The two corrections stand on their own merits, not as levers.** Recommended:
  * model the steam-cycle penalty in `ccgt_cc_link_params()` (derived from the sheet's
    heat-input, or the −7 pp of `docs/ccs_alignment.md`), with a regression test;
  * charge the 13.8 €/t onshore leg on all captured Walloon CO₂, after ICEDD confirms the scope of
    `STORAGEMININD` / `STORAGEMINELC`;
  * then re-run (6 h first) and see whether CCGT CC survives at the corrected costs.
* **Until then,** quote the 2040 CCGT CC as "the marginal abatement option at a 15 % cap, on
  optimistic capture-energy and disposal costs".

#### R2. Closing the route changes the 2050 bill, not the plant mix: +1.47 bn€, no loss of power capture

* **Observed.** 2050 objective +1.47 bn€ against 5 Oct. CCGT CC 0.76 Mt (5 Oct 0.63) and gas CHP CC
  0.45 Mt (0.46) are still captured; nothing new is built in 2050.
* **Why.** On 5 Oct the 8 Mt route was full (8.0 of 8). The marginal Walloon tonne already left by
  pipeline at the endogenous price (−332 €/t); without the route, all 8.4 Mt do, and that price
  barely moves (−340 €/t).
  * The 8 Mt lose a rent of about 270 €/t, about 2.2 bn€; the transmission fix gives back about
    0.8 bn€.
  * The 2040 capture plant (R1) keeps running in 2050 because its capex is sunk (myopic): 654 €/t
    avoided against 340 €/t disposal.
* **What it should be.** §4 expected power capture to recede in 2050; that was wrong. The route
  would change decisions only where it has spare room.
* **What to do.** Present the route as a 2 bn€/a disposal-cost question in 2050, not a technology
  question.

#### R3. 2040 biogas is 2.15 TWh: half the 4.67 TWh cap and half of TIMES

* **Observed.** 2.145 TWh in 2040, exactly what the upgraders built in 2030 can deliver; no new
  biogas chain in 2040. On 5 Oct, 2040 ran 4.0 TWh only because 2030 had built about 1 GW of
  upgraders for the old 8.3 TWh.
* **Why.** At an effective 132 €/t, a new chain (about 64 €/MWh of biomethane, `docs/biogas.md`
  §8.3) does not beat gas plus carbon. TIMES sits on its bound with a scarcity rent.
* **What it should be.** Closer to TIMES's 4.67 TWh if TIMES's 2040 carbon value is right.
  * It feeds R1: 1.85 TWh less biogas means 0.37 Mt more Walloon abatement and more CCGT CC.
* **What to do.** Ask ICEDD which drives TIMES's 2040 biogas: its ETS price trajectory or its
  chain cost.

#### R4. The 2030 cost of the biogas cut is hidden in the objective delta

* **Observed.**
  * 2030 biogas 9.2 → 2.15 TWh.
  * BEWAL 2030 dual −77.9 → −84.5 €/t; effective Walloon price 178 €/t.
  * Yet the 2030 objective is −76 M€ against 5 Oct, because the transmission fix acts from 2030.
* **What to do.** Do not read the 2030 cost of the biogas cap from this run (R5).

#### R5. The deltas against 5 Oct mix three changes

* **Observed.** The route acts in 2050, biogas in 2025–2050 and the transmission fix in 2030–2050;
  no ablation.
* **What to do.** Quote levels, not deltas against 5 Oct, except the price-based readings of R1
  and R2. If an attribution is wanted, run the "central + route" twin (§7 item 2) and a
  biogas-only ablation.

#### R6. Standing items (unchanged)

* **The 2050 biomass corner.** `biomass limit` −988 €/MWh; biomass boilers 64.7 % undelivered.
  Every 2050 biomass quantity is a degenerate allocation (4 Oct F7).
* **The `enc_pe` artefact**, the 9 corridor FAILs and the 18 bill-harmonisation gaps.
* **CO₂ storage.** The six-country ceilings bind in 2040 and 2050 (DE 79.2, GB 100, NL 9.1 Mt).
  This is the source of the disposal rent in R1 and R2.

### What passed cleanly

* 4/4 optimal, 0 trouble; 6.4 h chain on `batch`, no resubmission.
* Route closed everywhere; biogas caps exactly as designed, including the clipped 2025 forced
  volume.
* The transmission fix behaves as its commit claims.
* 2030 feasibility as argued in §3.1 (dual −84.5 €/t, inside the predicted −78 … −95).
* Rooftop floor, import cap and the 2040 Walloon cap all met.
* Both new gas technologies recover exactly 100 % of capex: no hidden capacity payment.
* No new WARN/FAIL kind against 5 Oct.
* Locally, memory never fell below 6.5 GB available; nothing crashed.

### Numbers that must not be published as-is

The pages are online for internal use (§10.1). Before pointing anyone at them:

* **The 2040 CCGT CC capacity and capture as a robust result** (R1). It sits exactly at the
  margin and rests on a missing steam-cycle penalty and on a disposal price below TIMES's chain.
* **Any delta against the 5 Oct central** (R5).
* **2040 biogas as a policy result** without R3's caveat: it is set by the 2030 investment.
* **Every 2050 biomass quantity** (R6).
* **`bill_harmonisation` figures** before reading the 18 gaps.

### Review follow-ups

| # | Action | Owner |
|---|---|---|
| 1 | Decide how to treat 2040 CCGT CC: accept it as TIMES-consistent, or correct its costs first (R1) | modeller |
| 2 | Model the CCGT CC steam-cycle penalty in `ccgt_cc_link_params()` (sheet heat-input or −7 pp), with a regression test | code |
| 3 | Charge the 13.8 €/t Walloon onshore collection on all captured Walloon CO₂; confirm the scope of `STORAGEMININD` / `STORAGEMINELC` with ICEDD | data / modeller |
| 4 | 6 h ablations on the central: +penalty, +onshore leg, both, 2040 cap at 19 % and 25 %. Report CCGT CC, the Walloon 2040 dual and the 2040 objective | ops |
| 5 | Re-open lever C at 1 h: the 2040 disposal price is 47 €/t, below the 72–82 €/t chain (`docs/co2-sequestration.md` §10.4) | modeller |
| 6 | Ask ICEDD about 2040 biogas, TIMES 4.67 vs PyPSA 2.15 TWh (R3) | modeller |
| 7 | "Central + route" twin, if the route effect must be attributed (R5) | modeller / ops |
| 8 | Standing: 2050 biomass corner, bill gaps, corridor FAILs (R6) | data |
