<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: MIT
-->

# Running the Walloon model on 5-year planning periods

Going from `[2025, 2030, 2040, 2050]` to
`[2025, 2030, 2035, 2040, 2045, 2050]`.

> **Status: implemented, 2026-09-08.** The 5-year grid is an *overlay*,
> [`config/config.walloon_5y.yaml`](../config/config.walloon_5y.yaml), merged on
> top of the shipped config the same way `cluster/config_cluster.yaml` is. The
> 10-year grid is unchanged — same horizons, same `budget_national`, same
> `results/walloon/` tree, same value in every artefact — and
> [`test/test_five_year_overlay.py`](../test/test_five_year_overlay.py) fails if
> either half of that stops being true. Jump to [§6](#6-running-it).
>
> Nothing has been *solved* on six horizons yet. See §4 and §6 step 4.

**The assessment below was written before the work and three of its findings did
not survive contact:**

| roadmap said | actually |
|---|---|
| 28 missing rows in `custom_potentials.csv` | **40**. `--check` only sees *managed* rows; six more groups (`co2 storage` ×3, `gas storage`, `process emissions`, `solid biomass import`) have no master-CSV target, so the check is silent about them. |
| the 28 rows must be added to `input_parameters_for_models.csv` | **None were.** 12 of the 14 managed targets are flat or yearless, so `expand_years` already produces the right 2035/2045 value; the other two only needed their `year_rule` flipped `hold` → `interp`. |
| that file is CRLF | It is **LF** (677 LF, 0 CRLF). |
| `grouping_years_power` is the only config gap | **Six** horizon-keyed config keys lacked 2035/2045 — see §3.1. |

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

## 1. The blocker — missing rows in `custom_potentials.csv` *(resolved)*

> **Resolved: 40 rows added (20 groups × 2 horizons), none of them in the master
> CSV.** The count below is 28 because `--check` only reports *managed* rows.
> Six further groups — `co2 storage/e_nom_max` on all three Belgian buses,
> `gas storage/e_nom_max`, `process emissions/p_set` and
> `solid biomass import/e_nom` — carry a per-horizon row with **no active target
> in the master CSV**, so `patch_potentials()` logs them as "unmanaged" and the
> check says nothing at all about their missing horizons. Those were the
> dangerous ones, precisely because nothing flags them.
>
> How each was filled:
>
> | group | 2035 / 2045 | why |
> |---|---|---|
> | 14 flat or yearless targets | copy | `expand_years` already returns the flat value; the rows just had to exist |
> | `BE{WAL,VLG,BRU}/battery/p_nom_min` | 410 / 1860 / 0 | flat from 2030 on |
> | `co2 storage`, `gas storage` | 0 | zero in every horizon |
> | `solid biomass import/e_nom` | 4000 / 4500 | hold; the row is inert (`sector.solid_biomass_import.enable: false`) |
> | **`process emissions/p_set`** | **5329.0 / 5447.5** | **not a judgement call** — TIMES-derived, and all six horizons are already published in [`ccs_alignment.md`](ccs_alignment.md) §14.1 |
> | `biogas/p_nom` | 6150 / 5450 | modeller's decision, 2026-09-08: linear interpolation |
> | `solid biomass transported/e_sum_max` | 2125 / 2625 | modeller's decision, 2026-09-08: linear interpolation |
>
> The last two were implemented by flipping their `year_rule` from `hold` to
> `interp` on the rows that already exist. Because every existing anchor sits
> exactly on a 10-year horizon, `interp` returns the anchor unchanged there — so
> the 10-year values did not move, and **no row was added to the ICEDD-shared
> master CSV**. `test_five_year_overlay.py::test_interpolated_trajectories` pins
> both halves of that.

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
errors precisely so that nobody assumes `--write` handled them. The rows were
therefore inserted into
[`custom_potentials.csv`](../data/walloon/custom_potentials.csv) directly, each
one copying the source and description of the horizon it follows, and `--write`
then confirmed every managed value.

The file has multi-line quoted records, so it is edited at **record** level
(`csv.reader` → insert → `csv.writer`), never by line. A read/write round-trip of
that file is byte-identical, which is what makes the insertion safe to automate.

`config/input_parameters_for_models.csv` is shared with ICEDD, so it is edited
byte-preserving — one line rewritten, the other 673 untouched. It is **LF**, not
CRLF as an earlier draft of this document claimed. A spreadsheet round-trip of it
is destructive: on 2026-09-08 one turned 161 of its 363 semicolons into unquoted
commas and shifted the columns of 142 rows, taking `--check` from `CHECK PASSED`
to 266 errors. Open it with a text editor, or re-import it with the delimiter and
quoting set explicitly.

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

## 3. Two smaller fixes *(both done)*

### 3.1 Six horizon-keyed config keys, not one

`grouping_years_power` had 2035 but **not 2045** — `add_existing_baseyear` /
`add_brownfield` bin each vintage into these groups, so capacity built in 2045
would be attributed to a neighbouring group and retire up to five years off.

It was not the only gap. A walk over every year-keyed dict in the config found
**six** keys that a six-horizon run would leave incomplete — and an incomplete
one does not raise: `update_config` merges key by key, so a horizon the dict does
not list **silently falls back to the PyPSA-Eur default**.

> **Four of the six would not have been *absent* — they would have been
> *wrong*.** `config/config.default.yaml` ships its own entries for 2035 and
> 2045, so `config.walloon.yaml`'s four entries do not replace them, they merge
> into them. A six-horizon run without the overlay would have run on the
> **upstream** value at the two new horizons, and no "is the key present?" check
> can see that:
>
> | key | inherited at 2035 / 2045 | Walloon value | consequence |
> |---|---|---|---|
> | `co2_budget` | **0.25 / 0.05** | 0.35 / 0.15 | *tighter* than intended — 2035 carries 2040's cap, 2045 carries 2050's — and disagrees with `budget_national`. Infeasible, or a far more expensive system, with nothing pointing at the cause. |
> | `electricity.transmission_limit_myopic` | **`v1.05`** | `vopt` | a volume cap in exactly those two horizons. The Walloon config uses `vopt` deliberately: a volume cap left every branch non-extendable and the 2050 solve carrying 12.3 bn EUR/a of congestion rent (see the comment at `config.walloon.yaml:128`). |
> | `sector.land_transport_electric_share` | **0.45 / 0.85** | 0.58 / 0.905 | a slower EV adoption path than Wallonia's, on the non-TIMES nodes. |
> | `sector.land_transport_ice_share` | **0.55 / 0.15** | 0.42 / 0.095 | ″ |
>
> `test_five_year_overlay.py::test_does_not_inherit_the_pypsa_eur_default_at_the_new_horizons`
> asserts **both the leak and the fix** for each of the four, so it also fails if
> upstream ever changes its defaults rather than silently agreeing with them.
> Two further tests check that `co2_budget` and `budget_national` agree, and that
> the two land-transport shares still sum to 1 at every horizon.
>
> The lesson generalises: when a horizon set changes, walk every year-keyed dict
> in the **fully merged** config — defaults included — and compare *values*, not
> just presence.

| key | had | filled with | rule |
|---|---|---|---|
| `existing_capacities.grouping_years_power` | no 2045 | 2045 | the grid itself |
| `electricity.extendable_carriers.extendable_nuclear_links` | 2025/30/40/50 | 2035 = `[FR, GB, NL, LU]`, 2045 = `+[BEWAL, BEBRU, BEVLG]` | hold previous; matches the scenario's "2035/2040 … no new build" note, and the agg caps pin capacity either way |
| `electricity.transmission_limit_myopic` | 2030/40/50 | `vopt` | same as every other horizon |
| `sector.land_transport_electric_share` | 2020/25/30/40/50 | 0.58 / 0.905 | linear — a smooth adoption curve |
| `sector.land_transport_ice_share` | ″ | 0.42 / 0.095 | complement of the above |
| `co2_budget` | 2025/30/40/50 | 0.350 / 0.150 | linear, matching `budget_national`'s own `interp` rule |

The EV keys (`bev_dsm_availability`, `local_bev_dsm`, `bev_avail_*`) and
`co2_sequestration_potential` already covered all six —
`build_ev_charging_weights.py` generates them on
`DEFAULT_HORIZONS = (2020, …, 2050)`.

`transmission_limit_myopic` still has no 2025 entry, in **both** grids: 2025 is
the base year and makes no expansion decision. That asymmetry predates this work
and `test_five_year_overlay.py` whitelists it explicitly rather than silently.

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

**Done — all three now derive the list from the run.**

| file | how |
|---|---|
| `review_run.py` | `discover_horizons(run)` — the `scenario.planning_horizons` recorded **inside** a config snapshot, falling back to the years present on disk. `--horizons` overrides. |
| `check_heat_profile_fidelity.py` | `horizons_from(networks)` — the years present in a `networks/` directory. |
| `compare_heat_softlink.py` | `comparison_horizons(phases)` — the **intersection** across the compared archives, since a table row needs the same year in every phase. Its two print loops now iterate the collected data rather than a constant. |

`HORIZONS` survives in each file as a documented fallback for a tree that holds
neither configs nor networks, and nothing else reads it.

The old "expected 4 config snapshots, found 6" warning is gone. `review_run.py`
instead **prints the horizon set it is reviewing against** and warns about any
horizon with no config snapshot — so a 4-vs-6 mix-up is visible in the report
rather than inferred from a count.

**Reading the config, not the filenames, is load-bearing.** Discovering horizons
from what is on disk would make a *stalled* chain look complete: the 2026-09-07
run died after 2030 and its tree holds exactly two of everything, so a
filename-based review would have reported two horizons, passed, and said nothing
about the four missing solves. Each per-horizon snapshot records the **full**
`scenario.planning_horizons` list, so the run is reviewed against what it was
configured to solve. Verified against that tree:

```
[ info ] planning horizons this run is reviewed against: [2025, 2030, 2040, 2050]
[ WARN ] no per-horizon config snapshot for [2040, 2050]
```

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

## 6. Running it

Steps 1–7 of the original checklist are done and committed. What remains is
step 8: **nothing has been solved on six horizons yet.**

### Run the 5-year grid

```bash
snakemake --configfile config/config.walloon.yaml config/config.walloon_5y.yaml --cores 12 --resources mem_mb=100000 -call
```

Both files, in that order — the second is an overlay, not a replacement. Results
land in `results/walloon_5y/<scenario>/`, so the 10-year tree is untouched and the
two can coexist.

On NIC5:

```bash
CONFIGFILE="config/config.walloon.yaml config/config.walloon_5y.yaml" RUN_PREFIX=walloon_5y ./cluster/nic5.sh run
```

### Keep the artefacts in sync

`--config` takes the same two files and validates every managed artefact against
the six-horizon set. It writes `budget_national` to the **last** file given, so
the base config is never rewritten:

```bash
python scripts/build_common_parameters.py --config config/config.walloon.yaml config/config.walloon_5y.yaml --check
```

Plain `--check` (no `--config`) still validates the 10-year grid, unchanged. Both
must pass; `test_five_year_overlay.py` runs the equivalent assertions in CI.

### Before committing a long queue slot

1. **Solve at 6h first.** A 5-year chain has never been solved on this model, and
   6h costs about an hour to learn whether 2035 and 2045 are feasible at all.
   Set `clustering.temporal.resolution_sector: 6h`.
2. **Read the biomass budget report for 2035 and 2045.** The 2026-09-07 stall
   happened because 2030's solid-biomass budget landed almost exactly on its cap.
   Two interpolated horizons are two new chances to land on a boundary between
   horizons that are known to be feasible. `times_heat_profiles.py` prints the
   margin before the solve starts — see §4.
3. **Build the HTML report from the six solved networks.** pypsa2html is
   horizon-agnostic by construction and its unit tests parametrise on
   `(2025, 2035, 2045)`, but no report has ever been built from six solved
   networks because none existed. See §5, and its caveat about cumulative totals.
4. **Fill in a solve log**, as for any run:
   `docs/logs/YYYY-MM-DD_<scenario>_5y_<tags>.md`.

### One number to revisit

`BEWAL/biogas/p_nom` at 2035/2045 is linear interpolation between 2040 and 2050
values whose own source is recorded as *"ICEDD meeting 2026-08-27 — SOURCE TO BE
PROVIDED"*, and which the `.vd` itself contradicts (7.67 / 8.07 TWh against 4.0 /
6.9). Interpolating an unsourced number does not make it sourced. When ICEDD
supplies the trajectory, change the four anchors in the master CSV and re-run
`--write`; the interpolated horizons follow automatically.
