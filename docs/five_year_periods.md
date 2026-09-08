<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: MIT
-->

# Running the Walloon model on 5-year planning periods

What it takes to go from `[2025, 2030, 2040, 2050]` to
`[2025, 2030, 2035, 2040, 2045, 2050]`.

**Status as of 2026-09-08 (`d950d061`): one blocker, two smaller fixes, and a
runtime cost. Nothing is unknown — the repo's own checks enumerate the work.**

Assessed by setting `scenario.planning_horizons` in
[`config/config.walloon.yaml`](../config/config.walloon.yaml) to the six-horizon
list and running

```bash
python scripts/build_common_parameters.py --check
```

`planning_horizons()` in
[`build_common_parameters.py`](../scripts/build_common_parameters.py) reads that
key, so the check re-validates every managed artefact against the new horizon set
without touching anything else. Revert the key afterwards — the assessment is
read-only, but the config is not.

---

## 1. The blocker — 28 missing rows in `custom_potentials.csv`

`--check` fails with **14 errors**, all the same shape:

```
✗ custom_potentials.csv: BEWAL:solar:p_nom_max has no row for [2035, 2045].
  BEWAL_potentials.py matches the year exactly, so those horizons would
  silently keep the PyPSA-Eur default.
```

That warning is the whole problem.
[`BEWAL_potentials.py`](../scripts/walloon_scripts/BEWAL_potentials.py) selects
rows with `.query("year == @planning_horizons")` — an **exact** match, no
interpolation, no forward fill. A horizon with no row is not an error at runtime:
the potential simply never applies and the node silently falls back to whatever
PyPSA-Eur computed from its own land-eligibility layers. On a six-horizon run,
**the Walloon potentials would apply in four horizons and not in the other two**,
which is far worse than not applying them at all — the trajectory would jump
around with no visible cause.

The 14 targets, with their present values:

| target | 2025 | 2030 | 2040 | 2050 | shape |
|---|---:|---:|---:|---:|---|
| BEBRU/battery/p_nom_min | 0 | 0 | 0 | 0 | flat |
| BEVLG/battery/p_nom_min | 250 | 1860 | 1860 | 1860 | trajectory |
| BEVLG/offwind/p_nom_max | 8000 | 8000 | 8000 | 8000 | flat |
| BEWAL/battery/p_nom_min | 286 | 410 | 410 | 410 | trajectory |
| BEWAL/biogas/p_nom | 8300 | 8300 | 4000 | 6900 | **trajectory** |
| BEWAL/onwind/p_nom_max | 6500 | 6500 | 6500 | 6500 | flat |
| BEWAL/solar/p_nom_max | 13000 | 13000 | 13000 | 13000 | flat |
| BEWAL/solar rooftop/p_nom_max | 46000 | 46000 | 46000 | 46000 | flat |
| BEWAL/solid biomass/p_nom | 9222 | 9222 | 9222 | 9222 | flat |
| BEWAL/solid biomass transported/e_sum_max | 2000 | 2000 | 2250 | 3000 | trajectory |
| DE/offwind/p_nom_max | 70000 | 70000 | 70000 | 70000 | flat |
| FR/offwind/p_nom_max | 45000 | 45000 | 45000 | 45000 | flat |
| GB/offwind/p_nom_max | 80000 | 80000 | 80000 | 80000 | flat |
| NL/offwind/p_nom_max | 50000 | 50000 | 50000 | 50000 | flat |

**10 of 14 are flat**, so their 2035 and 2045 rows are a copy — mechanical, no
judgement. Four carry a trajectory and need a value chosen:

* the two battery floors are flat from 2030 on, so 2035/2045 follow trivially;
* `solid biomass transported` is monotone (2000 → 2250 → 3000) and interpolates
  cleanly to 2125 @2035 and 2625 @2045 — but see
  [the stalled-run log](logs/2026-09-07_scen_demande_haute_2010_1h_stalled.md),
  follow-up 4: whether this cap should exist at all is an open question with
  ICEDD, and adding two more rows to it should not pre-empt that;
* **`BEWAL/biogas/p_nom` is not monotone** (8300 → 8300 → 4000 → 6900). Nothing
  can be inferred from the neighbours; 2035 and 2045 are a modeller's call.

### Why `--write` does not fix it

`patch_potentials()` iterates over the rows **already present in the file** and
updates their `value`. It never inserts a row. Missing horizons are reported as
errors precisely so that nobody assumes `--write` handled them. The 28 rows have
to be added to
[`config/input_parameters_for_models.csv`](../config/input_parameters_for_models.csv)
— the authoritative source — and then pushed out with `--write`.

Note that file is **CRLF** and shared with ICEDD; edit it byte-preserving or the
next merge conflicts on all 673 lines.

---

## 2. What already works

Verified, not assumed:

| item | state |
|---|---|
| **TIMES data** | The soft link exports 2035 and 2045 cleanly. `export_horizon()` was run for both on `scen_central_demande_haute_v01_260907_0709.vd` and produced full `wallon_demands`, `heating_targets`, `heating_capacities` and `road_transport` files. |
| **NTCs** | `data/walloon/ntc_2035.csv` and `ntc_2045.csv` are present and in sync (226 rows, 5 managed each). |
| **Aggregate capacity caps** | `agg_p_nom_minmax_demande_haute.csv` already carries `2035` and `2045` min/max column pairs. |
| **National CO2 budget** | `budget_national` is `year_rule: interp`, so `--check` computes 2035 = 0.35 and 2045 = 0.15 by itself and `--write` fills them in. No manual work. |
| **Discount rates / costs** | `discount_rates{,_car11}.csv` and `custom_costs.csv` are horizon-independent — in sync in both configurations. |
| **Heat vintage grouping** | `grouping_years_heat` ends at 2019 (historical stock only), so planning horizons do not touch it. |

---

## 3. Two smaller fixes

### 3.1 `grouping_years_power` has no 2045

```yaml
# config/config.walloon.yaml:174
grouping_years_power: [1920, …, 2020, 2025, 2030, 2035, 2040, 2050]
```

2035 is there, **2045 is not**. `add_existing_baseyear` / `add_brownfield` bin
each vintage into these groups, so capacity built in 2045 would be attributed to
a neighbouring year and its retirement date would be wrong by up to five years.
One-line fix; do it in the same change as the potentials.

### 3.2 Three diagnostics hard-code the four horizons

| file | line |
|---|---|
| [`scripts/walloon_scripts/review_run.py`](../scripts/walloon_scripts/review_run.py) | 43 |
| [`scripts/walloon_scripts/check_heat_profile_fidelity.py`](../scripts/walloon_scripts/check_heat_profile_fidelity.py) | 43 |
| [`scripts/walloon_scripts/compare_heat_softlink.py`](../scripts/walloon_scripts/compare_heat_softlink.py) | 58 |

All three carry `HORIZONS = (2025, 2030, 2040, 2050)`. These are reporting-only —
they cannot corrupt a solve — but on a six-horizon run they would review four
horizons and **silently skip 2035 and 2045**, and `review_run.py` would in
addition warn that it found six config snapshots where it expected four. A run
that looks reviewed but is not is exactly the failure mode
[`docs/run-review-checklist.md`](run-review-checklist.md) exists to prevent.

Derive the list from the run instead of pinning it. `build_ev_charging_weights.py`
already gets this right (`DEFAULT_HORIZONS = (2020, 2025, 2030, 2035, 2040, 2045,
2050)`), so there is a pattern to follow.

---

## 4. Runtime cost

Six horizons instead of four: **6 solves and 5 brownfield steps** rather than 4
and 3. On the 2026-09-07/08 production run at 1h resolution the four barriers
took 3892 + 7809 + 4733 + ~5500 s ≈ 6.1 h; six comparable horizons put the chain
at **roughly 9 h of barrier**, plus ~40 min of local prepare and the postprocess.

Size the cluster request accordingly — `cluster/config.sh` currently asks for
1440 min, which still covers it, but the memory profile is per-horizon and the
later horizons are the larger LPs (2050 reached 43.5 M rows / 21.7 M cols at
29.9 GB peak).

Two things to watch that are not just "more of the same":

* **Myopic drift.** Six myopic steps compound investment decisions twice as often
  as four. A capacity that was marginal in 2040 gets two chances to be locked in
  rather than one; do not read a 5-year trajectory as a refinement of the 10-year
  one.
* **The biomass boundary.** The 2026-09-07 stall happened because 2030's
  solid-biomass budget landed almost exactly on its cap. Interpolated horizons
  create two new opportunities to land on a boundary between the horizons that
  are known to be feasible. The pre-solve budget report in
  [`times_heat_profiles.py`](../scripts/walloon_scripts/times_heat_profiles.py)
  prints the margin before the solve starts — read it for 2035 and 2045 before
  committing to a long queue slot.

---

## 5. pypsa2html — ready, with one caveat

Checked against `pypsa2html` `2c40825`. **No work required.** The report layer was
deliberately built horizon-agnostic — its docstrings say so explicitly
(`year_columns`: *"Replaces the `['2020','2030','2040','2050']` literals that
appeared in ~20 places and made 2035/2045 structurally impossible"*) — and the
claim holds up when exercised:

| mechanism | verdict |
|---|---|
| `discover_horizons()` | regex is `(\d{4})` against `model.network_pattern`; any 4-digit year is picked up, and `model.planning_horizons: null` in `config/pypsa-wal.yaml` means "discover from disk". |
| `ctx.year_columns` | derived from the discovered horizons. Returned the right 6 labels for `(2025, 2030, 2035, 2040, 2045, 2050)`. |
| `ctx.horizon_weights()` | weight = gap to the next horizon, last inherits the previous gap. Six horizons → `[5, 5, 5, 5, 5, 5]`. See the caveat below. |
| `_interpolate_to()` | puts the packaged `domestic_{gas,oil}_production.csv` tables (quoted 2020/2030/2040/2050) onto any horizon by index interpolation. A 2020→2050 series of 100/120/110/100 gives 115 @2035 and 105 @2045. |
| positional indexing | only `horizons[0]` (default network) and `horizons[-1]` (`costs_<last>_processed.csv`). Both correct for any horizon set. |
| chart layout | the single `make_subplots` facets by *technology group*, never by year; bars sit on a categorical x axis, so six bars need no change. Sankey years come from the data index, dispatch pages iterate `ctx.horizons`. |
| tests | `tests/test_tables.py` already parametrises on `(2025, 2035, 2045)`. 360 tests pass. |

**Caveat — cumulative totals are not comparable across horizon grids.** Because
the last horizon inherits the previous gap, the weights sum to a different span:

| grid | weights | span |
|---|---|---|
| `2025, 2030, 2040, 2050` | 5, 10, 10, 10 | **35 years** (2025–2060) |
| `2025, 2030, 2035, 2040, 2045, 2050` | 5, 5, 5, 5, 5, 5 | **30 years** (2025–2055) |

Every cumulative chart — cumulative cost, cumulative emissions, the CO2 budget
comparison — therefore integrates over 35 years today and would integrate over
30 on a 5-year grid. A ~14 % shift with no physical meaning. This is not a
pypsa2html defect (gap-to-next is the right rule for a myopic step); it is a
property of the tail convention. **Do not put a 10-year and a 5-year run's
cumulative figures in the same table** without restating both on a common span.

The one thing not verified: no report has ever been *built* from six solved
networks, because none exist. Everything above is unit-level. Build the HTML at
6h resolution before trusting a 1h run's pages.

---

## 6. Checklist

1. Add 28 rows (14 targets × 2035, 2045) to
   `config/input_parameters_for_models.csv`, preserving CRLF. Ten are copies;
   `BEWAL/biogas/p_nom` needs a modeller's decision.
2. Add `2045` to `grouping_years_power`.
3. Set `scenario.planning_horizons` to the six-horizon list.
4. `python scripts/build_common_parameters.py --write` — fills `budget_national`
   2035/2045 and pushes the new potential rows into `custom_potentials.csv`.
5. `python scripts/build_common_parameters.py --check` must print `CHECK PASSED`.
6. De-hard-code `HORIZONS` in the three diagnostics (§3.2).
7. `pytest test` — note `test_discount_rates.py:691` asserts the four-horizon
   tuple and will need updating; it is the only test that pins the horizon set.
8. Run at 6h first. A 5-year run has never been solved on this model, and 6h
   costs an hour to learn whether 2035 and 2045 are feasible at all.
