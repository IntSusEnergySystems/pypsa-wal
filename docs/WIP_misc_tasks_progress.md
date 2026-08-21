# WIP — misc tasks (2026-08-21)

Temporary tracker. **All items closed.** Delete this file once the branch is
reviewed; everything durable has been moved into the permanent notes.

Branch: `softlink-harmonisation` (pypsa-wal and TIMES_PyPSA). `master` untouched
in both.

## The seven original tasks

| # | Task | Status | Where it lives now |
|---|------|--------|--------------------|
| 1 | Discount rates on the TIMES `~TFM_INS` / `NCAP_DRATE` table | ✅ | [`discount-rates.md`](discount-rates.md) §3 |
| 2 | Consolidate the heat soft-linking notes | ✅ | [`heat-softlink.md`](heat-softlink.md) |
| 3 | Merge the two discount-rate notes | ✅ | [`discount-rates.md`](discount-rates.md) |
| 4 | Fewer heat pumps in 2030 than 2025 | ✅ diagnosed **and fixed** | [`heat-softlink.md`](heat-softlink.md) §5 |
| 5 | EV shares from TIMES | ✅ exported, documented, not wired | [`ev-charging-softlink.md`](ev-charging-softlink.md) §2 |
| 6 | Three BEV charging profiles | ✅ implemented (merged) + weights corrected | [`ev-charging-softlink.md`](ev-charging-softlink.md) §1, §3b |
| 7 | Check everything works | ✅ | below |

## The 13 open decisions — all resolved

| # | Was | Resolution |
|---|-----|-----------|
| 1 | Charger loss counted twice on `feat/bev-myopic` | **Fixed.** `add_EVs` scales the flexible branch down instead of grossing the inflexible one up. BEWAL 2030 grid draw 3.770 → **3.393 TWh**, exactly the TIMES figure. Regression test pins the direction. |
| 2 | Heating costs unreconciled with TIMES | **Measured.** TIMES prices decentral heating 1.3–5× cheaper in annuity terms, ~3× cheaper for gas *relative to* heat pumps. Five `status=pending` rows carry the ask for the VEDA `~FI_T` tables. [`heat-softlink.md`](heat-softlink.md) §5b |
| 3 | EV energy-vs-fleet share | **Documented + exported, deliberately not wired** (E1–E3). Waiting on the availability-profile work, as instructed. |
| 4 | 2030 heat-pump dip fix not chosen | **Option 2 implemented**: per-technology age profile derived from the TIMES 2021→2025 trajectory. Retiring tranche 334.4 → **83.3 MW_th**. |
| 5 | 2040 solid-biomass conflict | **Recorded** as `none:solid_biomass_2040_conflict` in the shared table. Needs an ICEDD/Valbiom decision, not a constraint. |
| 6 | Confirm the branch's non-BEV config changes | **Reverted** in `config.walloon.yaml` (legacy heat path, 6 h) with a comment saying why, so the next merge cannot undo it silently. |
| 7 | Provenance of the branch's Elia local profiles | **Still open — the one thing I could not resolve.** See below. |
| 8 | `COM-processes` reaches no technology | **Decided: no fix.** Effect measured at 4.1–6.8 % on services heating CAPEX, uniform in sign. [`discount-rates.md`](discount-rates.md) §4.3 |
| 9 | Cars and rooftop PV at 7.5 % | **Recorded** as `none:hurdle_assignment_tension`; the `car11` sensitivity is built and runnable. |
| 10 | District-heating supply mix | **Decided: stays out.** Checked — no geothermal potential exists for BEWAL, so nothing is instantiated. Recorded as `none:district_heating_supply_conflict`. |
| 11 | `local_bev_dsm` hard-indexed | **Fixed.** Holds the nearest earlier horizon with a warning, and validates the curve names. |
| 12 | `mapping_processes.csv` defects | **Fixed** in TIMES_PyPSA: 7 duplicate process codes dropped, `TCARGASEX14`'s description repaired, both guarded by tests. |
| 13 | Quantify the discount-rate change | **Closed.** `micro_chp: false` and zero micro/decentral CHP links in all four solved networks, so the two rates that moved are provably inert. |

**Plus one bug found during the merge that was on nobody's list:** `update_config`
merges dicts key by key, so the horizons a Walloon config did not list
(2020/2035/2045) silently inherited `config.default.yaml`'s
`bev_dsm_availability: 0.5`, `bev_avail_min: 0.0`, `bev_avail_max: 0.95` —
and `_helpers.get` returns those keys without warning. Both configs now list
every horizon, and a test fails on any future leak.

## Still open

**The provenance of the branch's Elia local charging curves.** The four
`sunny/cloudy × PV` columns in
`data/walloon/elia_natural_charging_daily_profile_utc0.csv` are genuinely
distinct, whereas the published AdeqFlex 2025 workbook collapses to two (tariff
and sky are inert there). So `a4fab1c6 add updated values from elia` came from a
later source, and nothing records which. **Ask the branch author for the
document, date and contact**, and note whether the updated curves are still a
winter-only illustration — [`ev-charging-softlink.md`](ev-charging-softlink.md)
§1.2, E8/E14. My extraction in `data/walloon/elia_adeqflex2025/` is the published
baseline for audit, not the input.

## Verification

| Check | Result |
|---|---|
| `pytest test/` (pypsa-wal) | **161 passed** |
| `pytest tests/` (TIMES_PyPSA), full `.vd` | **168 passed** |
| `build_common_parameters.py --check` | **CHECK PASSED** |
| every `config/config.*.yaml` against `ConfigSchema` | **6/6 OK** |
| default-leak check at used horizons, all configs | **clean** |
| `snakemake -n` on both Walloon configs | **DAG resolves** |
| `add_existing_baseyear` for 2025, real network | **ran; vintages verified** |
| `build_transport_demand` for 2030, real config | **ran; shape normalised** |
| charger-loss identity | **grid draw == TIMES to the digit** |

**Not verified: `prepare_sector_network`.** It fails on this machine because the
archived `resources/` tree is a **2013 weather year at 6 h** build while master's
configs now ask for **2010 at 1 h** — so `profile.loc[n.snapshots]` cannot align.
That is a stale-artefact problem, not a code problem, and a clean run elsewhere
will not hit it. Forcing those rules also deleted two intermediate networks from
the local (gitignored) `resources/` tree. **The archived `results/` are therefore
stale against this branch for three independent reasons: weather year,
resolution, and every change here.**

See the uncommitted `RUN_ME.md` for how to run it on a clean machine and what to
watch.
