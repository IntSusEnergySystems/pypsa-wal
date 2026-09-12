# September 2026 cabinet batch — scenarios and run recipe

**Prepared:** 2026-09-12 · **Deadline:** consolidated results Monday morning,
cabinet presentation Wednesday · **Status:** repository ready, nothing launched.

ICEDD delivered eight TIMES exports on 2026-09-12 to
`s3://intervectoriel/test/scenarios/times_20260911_*`. This document defines the
fourteen PyPSA runs built on them, the recipe for running them in parallel so
that the work they share is done once and the work that differs cannot
interfere, and the monitoring that watches them.

Everything here is reproducible from the tree: no number below was typed by
hand into a config.

---

## 1. What is being run

Fourteen scenarios. Thirteen are weather year 2010 and run as one batch;
`scen_central_2013` is the same central case on 2013 weather and runs
separately (§5).

| # | Scenario | TIMES `.vd` (`times_20260911_*`) | PyPSA-side delta vs central | Runnable |
|---|---|---|---|---|
| 1 | `scen_central` | `scen_central_v01_260911_1109` | — (reference) | **yes** |
| 2 | `scen_taxshift` | `scen_sensibilite_taxshift_260911_1109` | none | **yes** |
| 3 | `scen_taxshift_plus` | `scen_sensibilite_taxshift_plus_260911_1109` | none | **yes** |
| 4 | `scen_biomethane_industrie` | `scen_sensibilite_biomethane_industrie_v01_260911_1109` | none | **yes** |
| 5 | `scen_realiste_nets` | `scen_sensibilite_realiste_nets_v01_260911_1109` | 2030 RES caps + 2030 CO₂ | **yes**, see §6.1 |
| 6 | `scen_realiste_nobnd30` | `scen_sensibilite_realiste_nobnd30_260911_1109` | identical to #5 | **yes**, see §6.1 |
| 7 | `scen_retardnucleaire` | `scen_sensibilite_retardnucleaire_260911_1109` | nuclear pinned to LTO | **yes**, see §6.2 |
| 8–13 | `scen_nuctip_{9500,7500,6500,6000,5500,4500}` | `scen_sensibilite_nofixnuc_v01_260911_1109` | nuclear CAPEX + free capacity | **yes** |
| 14 | `scen_central_2013` | `scen_central_v01_260911_1109` | weather year 2013 | **yes**, separate run (§5) |

All eight `.vd` files are downloaded, symlinked into `data/walloon/`, and
`pytest test -k times_scenario_inputs` passes. **Nothing is blocked on ICEDD.**

### 1.1 Scenarios 2–4 — "no PyPSA-side difference"

ICEDD: *"Ces scénarios ne comportent aucune différence côté PyPSA par rapport au
scénario central."* That is true of the **assumptions**, and it is why these
three have no `config/scenarios/*.csv` override file and point at the central
`custom_costs.csv` / `custom_potentials.csv` / `agg_p_nom_minmax_demande_haute.csv`.

It is **not** true of the softlink values, which are TIMES *outputs* fed back
into PyPSA. Those are extracted per scenario (§3).

### 1.2 Scenarios 5–6 — realistic 2030 potentials

ICEDD's `config/scen_realiste.csv` carries three changes, applied to **both**
scenarios. ICEDD: *"Les deux ne diffèrent que par le maintien ou non en 2030
d'une contrainte sur les émissions pour ce qui est concerné par l'ETS. La
contrainte globale est retirée pour 2030 dans ces 2 scénarios, donc du côté
PyPSA cela reste identique."*

So #5 and #6 are **identical PyPSA configurations** differing only in the
demands their `.vd` carries. Both get:

| what | value | where |
|---|---|---|
| `agg:BEWAL:solar-all:max` @2030 | 3 310 MW (ICEDD wrote 3 474 — see below) | `config/scenarios/scen_realiste_*.csv` |
| `agg:BEWAL:onwind:max` @2030 | 2 366 MW (ICEDD wrote 2 203 — see below) | same |
| `agg:BEWAL:solar-all:min` @2030 | **dropped** (was 6 500) | same |
| `agg:BEWAL:onwind:min` @2030 | **dropped** (was 3 000) | same |
| 2030 CO₂ cap, Belgium only | lifted to 1.0 (= 1990 level) | `config/scenarios.walloon.yaml` |

**The two dropped floors are an addition to ICEDD's file, and they are
mandatory.** ICEDD's three rows assume the 2030 Walloon PV/wind floors are gone
from the master table — they removed them in `ee19e962`. That removal was
reverted (the central scenario keeps its floors; the projects behind them are in
the pipeline), so without an explicit per-scenario drop the realiste runs would
carry min 6 500 / max 3 474 MW: an **empty corridor**, and an infeasible 2030.

#### The two caps were corrected: ICEDD swapped the PV and wind increments

ICEDD knows the Walloon pipeline better than we do, so their numbers are taken
over ours unless there is a clear problem in the computation. There is one, and
it is arithmetic rather than judgement.

Their method is the PyPSA 2025 calibrated Walloon fleet plus the 2025 → 2030
increment of their own *"on fige l'évolution du PV et de l'éolien"* table. That
table gives:

| | 2025 | 2030 | increment |
|---|---:|---:|---:|
| onshore wind | 1 640 MW | 2 446 MW | **+806** |
| PV | 2 441 MWc | 3 083 MWc | **+642** |

Their file implies the opposite pairing — PV +806 and wind +643 — against the
PyPSA 2025 pins of 2 668 MW PV and 1 560 MW wind:

```
ICEDD  solar-all  2668 + 806 = 3474     <- wind's increment
ICEDD  onwind     1560 + 643 = 2203     <- PV's increment
```

The wind figure matches to the unit (806) and the PV one to within the table's
own rounding (642 vs 643, since the yearly increments sum to 3 084 against a
stated 3 083). Ratio-rebasing instead of adding would give 2 327 / 3 370 and
matches neither file, so that is not what they did. Giving each technology its
own increment:

```
onwind     1560 + 806 = 2366 MW
solar-all  2668 + 642 = 3310 MW
```

which is what the two override files now carry, with the full reasoning in each
row's `note_complementaire`. **Confirm with ICEDD.** Reverting is one value in
each file plus `build_common_parameters.py --write --all-scenarios`.

**Why the CO₂ relaxation is two keys, not one.** `co2_budget_national` is true
and the national caps carry the same series as the system cap (F5, 2026-09-05),
so relaxing `co2_budget` alone changes nothing — every country still faces 0.45
at 2030. Both move. Only the three Belgian regions are freed; DE/FR/GB/NL/LU
keep their own 0.45 national cap, so this stays a Belgian policy sensitivity
rather than a European one.

### 1.3 Scenario 7 — new nuclear deferred to 2055

From Julien Pestiaux's brief: *"L'installation de nouvelles capacités nucléaires
est désactivée, seule la prolongation du parc existant restant possible."*

Walloon nuclear is pinned to the Tihange 3 long-term operation (1 000 MW)
through 2050, min = max. Flanders is untouched. The BE parent row is the sum —
see §6.2 for why that is not optional.

| horizon | BEWAL | BEVLG (unchanged) | BE (= sum) |
|---|---|---|---|
| 2035 | 1 000 / 1 030 | 1 000 / 1 000 | 2 000 / 2 030 |
| 2040 | 1 000 / 1 030 | 1 000 / 1 000 | 2 000 / 2 030 |
| 2045 | 1 000 / 1 000 | 1 000 / 1 000 | 2 000 / 2 000 |
| 2050 | 1 000 / 1 000 | 3 000 / 3 000 | 4 000 / 4 000 |

### 1.4 Scenarios 8–13 — the nuclear CAPEX tipping point

The question: *with Walloon nuclear capacity left to the optimiser, how low must
the investment cost of new nuclear go before 2 GW of new capacity appears — 3 GW
in total with the prolonged plant?*

ICEDD's `nofixnuc` export is the TIMES run intended for this
(*"Le nofixnuc est celui destiné à faire les itérations sur le point de bascule
du coût nucléaire du côté PyPSA"*), so all six points use it.

Each point changes three things, generated by
`scripts/walloon_scripts/make_nuclear_sweep.py`:

1. `cost:nuclear:investment` = the swept value (central: 9 500 EUR2025/kW_e).
2. `agg:BEWAL:nuclear-all:min` relaxed to 1 000 MW (the LTO) at 2045 and 2050.
   **The max stays at the central value** (1 750 / 3 000 MW), so the sweep asks
   whether the optimiser *fills the envelope the central scenario imposes* —
   which is the question, and matches "max capacity = imposed capacity in the
   current model".
3. `agg:BE:nuclear-all:min` lowered by the same amount (§6.2).

9 500 is included so the sweep carries its own reference point: same free
capacity, unchanged cost. Six points in parallel cost the same wall-clock as
one, so a sweep beats a bisection here.

**The bracket is centred on 6 000**, where earlier analyses put the break-even:
6 500 / 6 000 / 5 500 resolve the crossing, 7 500 and 4 500 are the outer points
that should sit either side of it. 4 500 rather than a lower floor because a
value far below any credible EPC estimate only shows that the model *can* be
made to build nuclear, which is not in doubt.

**Read the result as:** the tipping point lies between the cheapest point that
builds nothing and the most expensive that builds 2 GW. If 4 500 EUR/kW still
builds nothing, or 9 500 already builds 2 GW, the bracket is wrong — widen it in
the next round rather than interpolating outside it.

---

## 2. Where a scenario's assumptions live

One mechanism, implemented 2026-09-12 (`docs/scenario-handling-proposal.md` §2):

```
config/input_parameters_for_models.csv        the central table
        +
config/scenarios/<name>.csv                   only what this scenario changes
        │  build_common_parameters.py --write --all-scenarios
        ▼
data/walloon/custom_costs_<name>.csv
data/walloon/custom_potentials_<name>.csv
data/walloon/agg_p_nom_minmax_<name>.csv      selected by the scenario block
```

Override rows use the master's schema, keyed on `(pypsa_wal_target, year)`, and
replace the **whole row** so the source and the note travel with the deviation.
`status: none` deletes a row **and blanks the cell** in the generated file.
Additions are allowed. One flat level — a scenario layers over the master, never
over another scenario.

`--check --all-scenarios` verifies every scenario is in sync; `--check --scenario X`
lists each override next to the baseline value it replaced, which is what makes a
stale override visible instead of silent.

A scenario with no override file uses the central files. **Never hand-edit a
generated file.**

`config:` targets (`co2_budget`, `budget_national`, sector scalars) are *not*
per-scenario files — `config/config.walloon.yaml` is shared. Put those in the
scenario's block in `config/scenarios.walloon.yaml`; an override file containing
one is refused with a message rather than silently ignored.

---

## 3. TIMES outputs are per scenario — do not inherit them

Three settings are TIMES *outputs* softlinked back into PyPSA:

| setting | TIMES quantity |
|---|---|
| `self_sufficiency.limit_twh` | `VAR_Act` of `Transfo_Imp` (one-way annual Walloon inflow) |
| `sector.rooftop_share` | `VAR_Cap` of the `ERNW_PV-*` plant processes |
| `sector.industry_cc_floor` | `VAR_FOut` of `CO2STOCK` at `STORAGEMININD` |

They were hand-extracted once from the central export. Extract them per
scenario instead:

```bash
python scripts/walloon_scripts/extract_times_softlink_values.py \
    data/walloon/<scenario>.vd --scenario <name> --write
```

Validated: `--self-test` reproduces all five values currently in the tree
**exactly** against `scen_central_demande_haute_v2_260903_0309.vd`, the export
they came from.

What the extraction shows:

* **`Transfo_Imp` is identical in all eight exports** (2.94 / 6.47 / 10.00 TWh at
  2030 / 2040 / 2050). It is a binding bound in TIMES, not a free output, so the
  same `self_sufficiency` block is correct everywhere — repeated deliberately,
  and pinned by `test/test_cabinet_batch.py`.
* **Rooftop share and capture floor differ materially.** 2030 rooftop share:
  0.651 central, 0.704 taxshift, 0.347 realiste. Reusing the central files would
  have turned each sensitivity into a hybrid of itself and the central case.
* The **7 Sept vs 3 Sept** exports already disagreed: the last production run
  took its demands from `..._0907` while its rooftop share and capture floor came
  from `..._0903` (0.6 pp and 2.2 % apart). Small, pre-existing, now impossible.

### 3.1 The realiste rooftop pin is dropped at 2030 — on purpose

TIMES splits Walloon PV into **plant** processes (`ERNW_PV-*`) and
**demand-side** ones (`RSDPVELC`, `COMPVELC`, `INDPVELC`, `AGRPVELC`). The
documented convention counts plant only. At realiste 2030 TIMES builds almost no
plant PV (0.13 GW roof + 0.25 GW ground) while 2.2 GW of behind-the-meter PV
stays on the roofs, so the two conventions give **0.347 and 0.903** — 56 pp
apart, and PyPSA's pin is applied to the *whole* BEWAL solar fleet.

Pinning 0.347 would force roughly two thirds of Walloon 2030 PV to be
ground-mounted. The 2030 row is therefore removed from the two realiste rooftop
files (`lookup_year_value` returns `None` and the pin is simply not added that
horizon); 2035–2050 keep the plant-only convention used everywhere, so
cross-scenario comparison is unaffected. The extractor prints this warning
whenever the conventions diverge by more than 5 pp.

---

## 4. The recipe — thirteen scenarios in parallel

### 4.0 Before anything

```bash
python scripts/build_common_parameters.py --check --all-scenarios
```

Must print `CHECK PASSED`. It is the one-command proof that every scenario's
generated inputs match the table they claim to come from.

```bash
pytest test -k "times_scenario_inputs or cabinet_batch" -q
```

### 4.1 Preprocess locally — the shared work is done once

```bash
CONFIGFILE=config/config.walloon.yaml ./cluster/nic5.sh prepare
```

`run.shared_resources.policy: base` (set in `config/config.walloon.yaml`) builds
the weather- and geography-derived resources **once** for all thirteen
scenarios. Measured on the dry-run DAG:

| rule | jobs with sharing | without |
|---|---|---|
| `build_renewable_profiles` | **6** | 78 |
| `determine_availability_matrix` | **6** | 78 |
| `base_network`, `cluster_network`, `build_solar_thermal_profiles`, `build_electricity_demand_base`, `build_BE_powerplants` | **1** each | 13 each |
| `build_wallon_demands`, `process_cost_data`, `prepare_sector_network` | 52 (= 13 × 4) | 52 |

The renewable profiles alone are ~23 of the ~43 benchmarked preprocessing
minutes, so this is the difference between paying them once and thirteen times.

**No large download happens.** Both cutouts (2010 and 2013, 6.6 GB each) are
already in `data/cutout/archive/v1.0/`. The eight `.vd` files (605 MB total) are
already fetched. If a rule ever tries to retrieve a bundle, stop and move that
step to a better-connected machine — do not let it run here.

First run is a full build (~45 min on 16 cores) because the shared files move
from `resources/walloon/<scen>/` to `resources/`. Every scenario after the first
pays only its per-run part.

### 4.2 Push and solve — one orchestrator, thirteen chains

```bash
./cluster/nic5.sh push
./cluster/nic5.sh solve
```

`cluster/config.sh` derives the scenario list from `run.name` in the config, so
both commands cover all thirteen with no extra arguments. One Snakemake
orchestrator on the login node submits up to `MAX_SLURM_JOBS=16` Slurm jobs at a
time.

**Why the parallelism is across scenarios, not inside one.** Myopic foresight
chains 2025 → 2030 → 2040 → 2050 through `add_brownfield`, so a scenario is
strictly sequential: one solve job at a time. Thirteen scenarios therefore give
thirteen concurrent solves, and `MAX_SLURM_JOBS` below the batch size serialises
the batch for no reason.

**Why `batch` and not `hmem`.** `hmem` is three nodes and was fully allocated
when checked on 2026-09-12. `batch` is 70 nodes × 64 cores × 252 GB with a 2-day
limit and had 2 601 idle cores. The 1 h solve never needed `hmem`: measured peak
RSS on the 2026-09-07 production run was 22.4 / 28.2 / 29.8 / 29.9 GB, against
the 80 GB now requested.

Expected wall-clock, from the 2026-09-07 run (≈6.5 h for one scenario's four
horizons: 1 h05 + 3 h + 1 h20 + 1 h05):

* thirteen scenarios in parallel ≈ **7–9 h** including queue and stragglers;
* the same thirteen in series ≈ 85 h. That is the whole point.

**Jobs that differ cannot interfere.** Each scenario writes only
`resources/walloon/<scen>/` and `results/walloon/<scen>/`. The shared
`resources/` files are inputs to every scenario and outputs of none of them once
built — they are produced before any solve starts, by rules that no scenario
parameterises (verified: nothing a scenario overrides feeds a shared file).

### 4.2b Data transit — what actually crosses the VPN

**Preprocessing runs here, not on NIC5.** `nic5.sh prepare` is a local Snakemake
call; the cluster only ever runs the myopic solve chain (`add_brownfield` →
`solve_sector_network_myopic`). Post-processing, the ClimAct extraction and the
HTML report are local too. So the cluster never reads a `.vd`, a cutout or a
cost table — it reads un-solved networks and writes solved ones.

| leg | volume | what it is |
|---|---:|---|
| **up**, first push | **≈ 7 GB** scope, less on the wire | `data/` (3.8 GB, ~1.5 GB already there), shared `resources/` (857 MB), 13 × un-solved networks and per-run resources (156 MB each ≈ 2.0 GB), 8 `.vd` (605 MB) |
| **up**, later pushes | tens of MB | rsync deltas: edited configs and scripts |
| **down**, pull | **≈ 17 GB** | 13 × ~1.3 GB of solved networks (229–363 MB per horizon at 1 h) |
| | **≈ 24 GB total** | |

Three things were trimmed on 2026-09-12 to get there, because the workstation
uplink is the slow leg:

* **`tmp/` is excluded** — 9.4 GB of leftover linopy `*.lp` dumps, and it is the
  exact directory `REMOTE_ENV` points the cluster's `TMPDIR` at, so pushing it
  both wasted the uplink and littered a directory the solve writes to.
* **`PUSH_EXCLUDES`** (cluster/config.sh) drops stale `resources/` trees from
  other run prefixes (`times-pypsa` 2.7 GB, `walloon-model` 0.9 GB, the 2013 6 h
  smoke test 0.9 GB) and the seven `.vd` files no active scenario names. `push`
  uses `-L`, so every symlink arrives as a real file — 15 `.vd` symlinks were
  1.1 GB of transit for 605 MB of need.
* Together: push scope **20.9 GB → 6.8 GB**. Clear `PUSH_EXCLUDES` to send
  everything.

**`-z` is on the push and deliberately off the pull.** The push carries GB of
geojson/csv that deflate well (with `--skip-compress` for `.nc`/`.tif`); what
comes back is netCDF4, already zlib-compressed internally — a measured sample
gzips to **97.6 %** of its size, so compressing the pull would burn CPU on both
ends for ~2 %.

The 17 GB pull is irreducible: `solving.options.store_model` is already `false`,
and the solved networks are what every local post-processing step reads. On a
slow link, pull **per scenario as it finishes** (the combined report is additive,
§4.4) rather than waiting for all thirteen.

### 4.3 Pull and post-process locally

```bash
./cluster/nic5.sh pull
./cluster/nic5.sh postprocess     # loops over all thirteen
```

Then the ClimAct extraction and the S3 upload:

```bash
./cluster/nic5.sh publish         # extract + upload, per scenario
```

### 4.4 The report is additive

Per scenario, `generate_html_report` writes
`results/walloon/<scen>/html/pypsa/index.html`. The cross-scenario report is
separate and now **skips scenarios that are not solved yet**:

```bash
snakemake --configfile config/config.walloon.yaml \
          --cores 4 results/walloon/index.html
```

Re-run it whenever a scenario lands; each run covers everything finished so far.
Before this change it aborted on the first missing tree, so a combined report
could only ever be built once, at the very end. All twenty-two scenarios the
project knows about are listed in `config/pypsa2html.yaml`; the unsolved ones are
logged as skipped, not treated as an error.

---

## 5. The 2013 weather year — a separate invocation, deliberately

```bash
snakemake --configfile config/config.walloon.yaml config/config.weather2013.yaml \
          --cores 16 -- results/walloon_2013/scen_central_2013/networks/base_s_adm___2050.nc
```

or through the cluster:

```bash
CONFIGFILE="config/config.walloon.yaml config/config.weather2013.yaml" \
RUN_PREFIX=walloon_2013 RUN_NAME=scen_central_2013 ./cluster/nic5.sh run
```

**It cannot join the 2010 batch.** The shared set contains the cutout-derived
files (`profile_*`, `availability_matrix_*`, `solar_thermal_*`,
`electricity_demand_base_s.nc`) and their names carry no year. A 2013 scenario in
the same invocation would overwrite the 2010 profiles, the next 2010 job would
write them back, and both trees would be wrong with every timestamp looking
fresh. `config/config.weather2013.yaml` sets `shared_resources.policy: false` and
its own `run.prefix`, so the run is fully self-contained. The price is one
complete preprocessing pass (~45 min), which is the right price for a different
weather year.

The 2013 cutout is already on disk. No download.

---

## 6. Traps that this batch walks into

### 6.1 Parent rows in `agg_p_nom_limits` — **open question for ICEDD**

`add_CCL_constraints` groups by `(location, carrier)`, and `BE` is a parent row
over BEVLG + BEWAL + BEBRU. A cap put on BEWAL alone is undone by the parent.

For the **nuclear** scenarios this is handled: the BE floor moves by the same
amount as the BEWAL floor, Flanders untouched (§1.3, §1.4). Without it the
2050 BE floor of 6 000 MW = 3 000 BEVLG + 3 000 BEWAL would re-impose the full
Walloon build through the parent and the sweep would come out flat — "nuclear is
always built" — for a reason that has nothing to do with its cost.

For the **realiste** scenarios it is **not** handled, because it is a scenario
definition question rather than a mechanical one:

| carrier | BE floor @2030 | BEWAL now capped at | left for Flanders + Brussels | they have today |
|---|---|---|---|---|
| `solar-all` | 16 500 MW | 3 474 MW | ≥ 13 026 MW | ~7 083 MW |
| `onwind` | 5 000 MW | 2 203 MW | ≥ 2 797 MW | ~1 777 MW |

Cutting Walloon 2030 PV to a realistic level while holding the Belgian national
floor at the PNEC target pushes the entire shortfall onto Flanders: +84 % of
Flemish PV in five years. If "réaliste" means the 2030 targets are not reachable,
the BE floor should fall by the Walloon shortfall — 16 500 → 13 474 and
5 000 → 4 203.

`add_CCL_constraints` clips a floor at run time to
`min(remaining land potential, growth allowance)`, so this may self-limit rather
than go infeasible — but the clip is computed from generator `p_nom_max`, not
from the agg cap, so it cannot see the new BEWAL ceiling. **Solve
`scen_realiste_nets` at 2030 first and check feasibility before launching the
other twelve** (§7). Ask ICEDD which reading they intend; the fix is two rows in
`config/scenarios/scen_realiste_*.csv` and one `--write`.

### 6.2 Why Flanders is never touched

The instruction for the nuclear sensitivities is explicit: Wallonia only,
surrounding nodes unchanged. Every BE parent-row change above is arithmetic —
BE is redefined as the sum of its unchanged Flemish part and its changed Walloon
part. `BEVLG` rows are byte-identical to the central scenario in every generated
file. That is worth re-checking after any regeneration:

```bash
for f in data/walloon/agg_p_nom_minmax_scen_*.csv; do
  echo "$f: $(grep -c '^BEVLG' "$f") BEVLG rows"
  diff <(grep '^BEVLG' data/walloon/agg_p_nom_minmax_demande_haute.csv) \
       <(grep '^BEVLG' "$f") > /dev/null && echo "  identical to central" || echo "  *** DIFFERS ***"
done
```

### 6.3 `lines.type` is non-empty here

`set_transmission_limit` rebuilds `s_nom_min` from the conductor type and
silently overrides NTC-derated `s_nom`. Unchanged by this batch, but it bites
every run — see the standing note.

### 6.4 Never open `input_parameters_for_models.csv` in a spreadsheet

One save shifted 142 rows' columns. It is LF, not CRLF. The same now applies to
every `config/scenarios/*.csv`, which share its schema.

---

## 7. Suggested launch order

Not all at once. Two gates, each cheap, each catching a class of failure that
would otherwise waste a night:

1. **`scen_central`, 2025 + 2030 only.** Proves the shared-resources change, the
   regenerated cost table (ICEDD's inflated fuel prices) and the new softlink
   files produce a feasible, optimal network. ~4 h.
2. **`scen_realiste_nets`, 2030 only.** The one scenario whose constraint set
   could be empty (§6.1). ~3 h, and it can run concurrently with gate 1.
3. **Everything else**, once both return `Optimal objective`.

Gates 1 and 2 together are one evening; the batch then runs overnight.

---

## 8. Monitoring

```bash
./cluster/probe.sh            # table
./cluster/probe.sh --save     # table + append to cluster/logs/probe_history.tsv
./cluster/probe.sh --json     # machine-readable
```

One ssh round-trip for the whole batch (52 log files would otherwise be 52
round-trips over the VPN). Output is one line per scenario: solved networks out
of four, `Optimal objective` count, Slurm state, age of the newest solver log,
and a state.

**`--save` is what makes it a monitor rather than a snapshot.** A scenario is
`STALLED` when it has a RUNNING Slurm job but neither its solver log nor its
network set has moved since the previous saved probe. That is the failure this
batch is exposed to — a barrier grinding without progress, a BeeGFS hiccup, an
orchestrator that died leaving jobs behind — and none of them remove the job from
`squeue`. It also reports `STOPPED-PARTIAL` (networks but no job: the solve died)
and a missing orchestrator while the batch is unfinished.

Probe **every 30 minutes** with `--save`. Exit status is 3 if anything is
stalled, so it drives an alert directly.

What to do on each signal:

| signal | action |
|---|---|
| `STALLED` | `ssh nic5 tail -50 <results>/logs/*_solver.log`; a barrier with a flat residual for >1 h is not going to converge — cancel that horizon and re-solve it with `BarHomogeneous: 1` already set, or `crossover: 0` |
| `STOPPED-PARTIAL` | read `cluster/logs/orchestrate.log`; usually OOM or walltime. Completed horizons are kept, so `nic5.sh solve` resumes |
| no orchestrator | `./cluster/nic5.sh solve` again — it resumes rather than restarts |
| `DONE` for a scenario | pull and post-process it alone; the combined report is additive (§4.4), so results can go out while the rest still runs |

---

## 9. Deliverables and provenance

Per scenario: `results/walloon/<scen>/{networks,csvs,graphs,html,explorer,logs,configs}/`.

For anything that leaves the team, fill a solve log from
`docs/logs/_TEMPLATE_solve_log.md` — **including section 11**, the critical
review (`docs/run-review-checklist.md`). Sections 1–10 say the run finished;
section 11 says whether it is right. For a batch, one log per *group* is enough
(central, realiste pair, nuclear sweep) provided section 11 names every scenario
it covers.

Provenance to record for this batch, beyond the template:

* TIMES exports: `s3://intervectoriel/test/scenarios/times_20260911_*`,
  uploaded 2026-09-12 09:47–10:02.
* The 2030 Walloon PV/wind floors (6 500 / 3 000 MW) were removed by ICEDD in
  `ee19e962` and **restored** in `c337f36a` for the central case; they are
  dropped per-scenario for the realiste pair only.
* ICEDD's fuel prices arrived at source vintage and were inflated to EUR2025 by
  the method of `common_parameters.md` §4.4 (`de96e610`). Coal 10.92 EUR2021 →
  13.3431; gas 30.345/26.01/21.675 → 37.0786/31.7816/26.4847; oil
  46.4475/51.9119/65.5729 → 56.7542/63.4312/80.1235; uranium 3.4122 EUR2011 →
  4.6497, which is the value `docs/nuclear-alignment-20260816.md` §7 derived
  independently.

---

## 10. Open items

| # | Item | Who | Blocking? |
|---|---|---|---|
| 1 | BE parent floors in the realiste scenarios (§6.1) — hold at PNEC, or lower by the Walloon shortfall? | ICEDD | no, but gate 2 may force it |
| 2 | **Confirm the swapped-increment correction** (§1.2): 2 366 MW wind / 3 310 MW PV instead of ICEDD's 2 203 / 3 474 | ICEDD | no — one value per file to revert |
| 3 | Confirm the currency year of the DG CLIMA "recommended parameters for reporting GHG projections in 2025" fuel prices. ICEDD tagged them EUR2021 and that is what the EUR2025 inflation assumes; the parameter file is not publicly fetchable, so it could not be checked here. The uranium row needs no confirmation — its own source note says "Based on IEA 2011 data" and the inflated value (4.6497) reproduces `docs/nuclear-alignment-20260816.md` §7 exactly | ICEDD | no — reversible in one commit |
| 4 | Nuclear sweep bracket: widen downwards if 4 500 EUR/kW still builds nothing | — | after the first results |
| 5 | `scen_base`, `scen_corrige`, `scen_nuc11500`, `scen_nuc13500`, `scen_imppel`, `scen_data` are from Nov–Dec 2025 and unmanaged. Retire or migrate to an override file | Sylvain | no |
