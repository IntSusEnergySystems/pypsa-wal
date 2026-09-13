# Cabinet batch — recipe and run log (September 2026, 14 scenarios, 1 h)

**Run window:** 2026-09-12 18:48 → 2026-09-13 (2010 batch complete 07:39).
**Supersedes** `docs/runs-20260912-cabinet-batch.md` (the pre-run recipe), merged
into this file and deleted on 2026-09-13 so that one document carries both *how to
run a batch* and *what happened when we did*.

Companion: `docs/logs/2026-09-13_scen_central_cabinet_batch_2010_1h.md` — the
central scenario's own solve log, which carries the §11 critical review of the
results. This file is the **batch-level** record.

> **Reading this to plan a new batch?** Parts I–II are the recipe. Part III is
> what actually happened, and §16 is the list of things to fix *before* you run
> again — read that first, it is short and every item cost real time.

---
---

# Part I — What is being run

## 1. The fourteen scenarios

Thirteen are weather year 2010 and run as one batch; `scen_central_2013` is the
same central case on 2013 weather and runs separately (§6).

| # | Scenario | TIMES `.vd` (`times_20260911_*`) | PyPSA-side delta vs central |
|---|---|---|---|
| 1 | `scen_central` | `scen_central_v01_260911_1109` | — (reference) |
| 2 | `scen_taxshift` | `scen_sensibilite_taxshift_260911_1109` | none |
| 3 | `scen_taxshift_plus` | `scen_sensibilite_taxshift_plus_260911_1109` | none |
| 4 | `scen_biomethane_industrie` | `scen_sensibilite_biomethane_industrie_v01_260911_1109` | none |
| 5 | `scen_realiste_nets` | `scen_sensibilite_realiste_nets_v01_260911_1109` | 2030 RES caps + 2030 CO₂ (§7.1) |
| 6 | `scen_realiste_nobnd30` | `scen_sensibilite_realiste_nobnd30_260911_1109` | identical to #5 (§7.1) |
| 7 | `scen_retardnucleaire` | `scen_sensibilite_retardnucleaire_260911_1109` | nuclear pinned to LTO (§7.2) |
| 8–13 | `scen_nuctip_{9500,7500,6500,6000,5500,4500}` | `scen_sensibilite_nofixnuc_v01_260911_1109` | nuclear CAPEX + free capacity |
| 14 | `scen_central_2013` | `scen_central_v01_260911_1109` | weather year 2013, separate run (§6) |

TIMES exports delivered by ICEDD 2026-09-12 to
`s3://intervectoriel/test/scenarios/times_20260911_*` (uploaded 09:47–10:02),
eight `.vd` files, 605 MB. Symlinked into `data/walloon/`;
`pytest test -k times_scenario_inputs` is the one-second check that a machine can
run.

Everything below is reproducible from the tree: no number was typed by hand into
a config.

### 1.1 Scenarios 2–4 — "no PyPSA-side difference"

ICEDD: *"Ces scénarios ne comportent aucune différence côté PyPSA par rapport au
scénario central."* True of the **assumptions**, which is why these three have no
`config/scenarios/*.csv` override file and point at the central
`custom_costs.csv` / `custom_potentials.csv` / `agg_p_nom_minmax_demande_haute.csv`.

**Not** true of the softlink values, which are TIMES *outputs* fed back into
PyPSA. Those are extracted per scenario (§4).

### 1.2 Scenarios 5–6 — realistic 2030 potentials

ICEDD's `config/scen_realiste.csv` carries three changes, applied to **both**.
ICEDD: *"Les deux ne diffèrent que par le maintien ou non en 2030 d'une
contrainte sur les émissions pour ce qui est concerné par l'ETS. La contrainte
globale est retirée pour 2030 dans ces 2 scénarios, donc du côté PyPSA cela reste
identique."*

So #5 and #6 are **identical PyPSA configurations** differing only in the demands
their `.vd` carries. (That property is what made the §14.1 diagnosis possible.)
Both get:

| what | value | where |
|---|---|---|
| `agg:BEWAL:solar-all:max` @2030 | 3 310 MW (ICEDD wrote 3 474 — see below) | `config/scenarios/scen_realiste_*.csv` |
| `agg:BEWAL:onwind:max` @2030 | 2 366 MW (ICEDD wrote 2 203 — see below) | same |
| `agg:BEWAL:solar-all:min` @2030 | **dropped** (was 6 500) | same |
| `agg:BEWAL:onwind:min` @2030 | **dropped** | same |
| `agg:BE:solar-all:min` @2030 | **dropped** (was 16 500) | same |
| `agg:BE:onwind:min` @2030 | **dropped** (was 5 000) | same |
| 2030 CO₂ cap, Belgium only | lifted to 1.0 (= 1990 level) | `config/scenarios.walloon.yaml` |

**The two dropped floors are an addition to ICEDD's file, and they are
mandatory.** ICEDD's three rows assume the 2030 Walloon PV/wind floors are gone
from the master table — they removed them in `ee19e962`. That removal was
reverted (`c337f36a`; the central scenario keeps its floors, the projects behind
them are in the pipeline), so without an explicit per-scenario drop the realiste
runs would carry min 6 500 / max 3 474 MW: an **empty corridor**, and an
infeasible 2030. Gate B (§13) confirmed the drop works.

#### The two caps were corrected: ICEDD swapped the PV and wind increments

ICEDD knows the Walloon pipeline better than we do, so their numbers are taken
over ours unless there is a clear problem in the computation. There is one, and
it is arithmetic rather than judgement.

Their method is the PyPSA 2025 calibrated Walloon fleet plus the 2025 → 2030
increment of their own *"on fige l'évolution du PV et de l'éolien"* table:

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
row's `note_complementaire`. **Confirm with ICEDD** (open item 2). Reverting is
one value in each file plus `build_common_parameters.py --write --all-scenarios`.

**Why the CO₂ relaxation is two keys, not one.** `co2_budget_national` is true
and the national caps carry the same series as the system cap (F5, 2026-09-05),
so relaxing `co2_budget` alone changes nothing — every country still faces 0.45
at 2030. Both move. Only the three Belgian regions are freed; DE/FR/GB/NL/LU keep
their own 0.45 national cap, so this stays a Belgian policy sensitivity rather
than a European one. Verified at launch: `budget_national` 2030 = 1.0 for
BEBRU/BEVLG/BEWAL, 0.45 for DE/FR/GB/NL/LU, no other year touched.

### 1.3 Scenario 7 — new nuclear deferred to 2055

From Julien Pestiaux's brief: *"L'installation de nouvelles capacités nucléaires
est désactivée, seule la prolongation du parc existant restant possible."*

Walloon nuclear is pinned to the Tihange 3 long-term operation (1 000 MW) through
2050, min = max. Flanders untouched. The BE parent row is the sum — §7.2 explains
why that is not optional.

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

ICEDD's `nofixnuc` export is the TIMES run intended for this (*"Le nofixnuc est
celui destiné à faire les itérations sur le point de bascule du coût nucléaire du
côté PyPSA"*), so all six points use it.

Each point changes three things, generated by
`scripts/walloon_scripts/make_nuclear_sweep.py`:

1. `cost:nuclear:investment` = the swept value (central: 9 500 EUR2025/kW_e).
2. `agg:BEWAL:nuclear-all:min` relaxed to 1 000 MW (the LTO) at 2045 and 2050.
   **The max stays at the central value** (1 750 / 3 000 MW), so the sweep asks
   whether the optimiser *fills the envelope the central scenario imposes* —
   which is the question, and matches "max capacity = imposed capacity in the
   current model". On the 10-year grid only the 2050 relaxation is active (2045
   is not a horizon, and 2040 is already min 1 000 / max 1 030), so the sweep's
   answer comes entirely from 2050.
3. `agg:BE:nuclear-all:min` lowered by the same amount (§7.2).

9 500 is included so the sweep carries its own reference point: same free
capacity, unchanged cost. Six points in parallel cost the same wall-clock as one,
so a sweep beats a bisection here.

**The bracket is centred on 6 000**, where earlier analyses put the break-even:
6 500 / 6 000 / 5 500 resolve the crossing, 7 500 and 4 500 are the outer points
that should sit either side of it. 4 500 rather than a lower floor because a value
far below any credible EPC estimate only shows that the model *can* be made to
build nuclear, which is not in doubt.

**Read the result as:** the tipping point lies between the cheapest point that
builds nothing and the most expensive that builds 2 GW. If 4 500 EUR/kW still
builds nothing, or 9 500 already builds 2 GW, the bracket is wrong — widen it in
the next round rather than interpolating outside it.

> **The sweep's objective values are NOT comparable across points.** The swept
> `cost:nuclear:investment` also reprices the annuitised **existing** Tihange LTO
> fleet, so cross-point cost differences are an artefact — visible already at
> 2025, where capacity is pinned yet the objective still moves monotonically with
> the swept value (4500: 3.5704e11 · 5500: 3.6073e11 · 6000: 3.6218e11 · 7500:
> 3.6514e11). The **capacity** reading is valid; the **cost** reading is not.
> See §11 F4 of the central solve log.
>
> For the same reason the six points are **not scenarios in the HTML report, and
> are excluded from the ClimAct extraction and from the S3 scenario upload**
> (decision 2026-09-13): they are six points of one parametric sweep, and six
> near-identical dashboard entries would bury the seven that differ.
>
> They *are* in the report, as a **sensitivity section**. Each entry in
> `config/pypsa2html.yaml` carries a `sensitivity: {sweep: nuclear_capex, value: N}`
> marker, which gives it no pages, no scenario-dropdown entry and no place in the
> cross-scenario overview, and feeds the `nuclear_capex` block under
> `sensitivities:`. That draws the curve on a shared **Sensitivity analyses**
> page: Walloon (and Belgian) nuclear capacity against the swept cost, one line
> per horizon. The declared metric is capacity only — no cost metric — precisely
> because the objective values are not comparable. See `instructions.md`,
> "Sensitivity analyses (parameter sweeps)", and pypsa2html D22.

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

They were hand-extracted once from the central export. Extract them per scenario
instead:

```bash
python scripts/walloon_scripts/extract_times_softlink_values.py \
    data/walloon/<scenario>.vd --scenario <name> --write
```

Validated: `--self-test` reproduces all five values in the tree **exactly**
against `scen_central_demande_haute_v2_260903_0309.vd`, the export they came
from.

What the extraction shows:

* **`Transfo_Imp` is identical in all eight exports** (2.94 / 6.47 / 10.00 TWh at
  2030 / 2040 / 2050). It is a binding bound in TIMES, not a free output, so the
  same `self_sufficiency` block is correct everywhere — repeated deliberately, and
  pinned by `test/test_cabinet_batch.py`. The central run confirmed it binds at
  exactly those values at every horizon.
* **Rooftop share and capture floor differ materially.** 2030 rooftop share: 0.651
  central, 0.704 taxshift, 0.347 realiste. Reusing the central files would have
  turned each sensitivity into a hybrid of itself and the central case.
* The **7 Sept vs 3 Sept** exports already disagreed: the last production run took
  its demands from `..._0907` while its rooftop share and capture floor came from
  `..._0903` (0.6 pp and 2.2 % apart). Small, pre-existing, now impossible.

### 3.1 The realiste rooftop pin is dropped at 2030 — on purpose

TIMES splits Walloon PV into **plant** processes (`ERNW_PV-*`) and **demand-side**
ones (`RSDPVELC`, `COMPVELC`, `INDPVELC`, `AGRPVELC`). The documented convention
counts plant only. At realiste 2030 TIMES builds almost no plant PV (0.13 GW roof
+ 0.25 GW ground) while 2.2 GW of behind-the-meter PV stays on the roofs, so the
two conventions give **0.347 and 0.903** — 56 pp apart, and PyPSA's pin applies to
the *whole* BEWAL solar fleet.

Pinning 0.347 would force roughly two thirds of Walloon 2030 PV to be
ground-mounted. The 2030 row is therefore removed from the two realiste rooftop
files (`lookup_year_value` returns `None` and the pin is simply not added that
horizon); 2035–2050 keep the plant-only convention used everywhere, so
cross-scenario comparison is unaffected. The extractor prints a warning whenever
the conventions diverge by more than 5 pp.

---
---

# Part II — The recipe

## 4. Before anything

```bash
python scripts/build_common_parameters.py --check --all-scenarios
pytest test -k "times_scenario_inputs or cabinet_batch" -q
df -h / /home        # BOTH partitions — see §15 E1
```

`CHECK PASSED` is the one-command proof that every scenario's generated inputs
match the table they claim to come from. The `df` is not optional: this batch was
stopped mid-post-processing by the *root* partition filling, not `/home`.

Also worth the 30 seconds, because it is the trap that costs most (§7.2):

```bash
for f in data/walloon/agg_p_nom_minmax_scen_*.csv; do
  echo "$f: $(grep -c '^BEVLG' "$f") BEVLG rows"
  diff <(grep '^BEVLG' data/walloon/agg_p_nom_minmax_demande_haute.csv) \
       <(grep '^BEVLG' "$f") > /dev/null && echo "  identical to central" || echo "  *** DIFFERS ***"
done
```

## 5. Run it

### 5.1 Preprocess locally — the shared work is done once

```bash
CONFIGFILE=config/config.walloon.yaml ./cluster/nic5.sh prepare
```

`run.shared_resources.policy: base` (in `config/config.walloon.yaml`) builds the
weather- and geography-derived resources **once** for all thirteen scenarios.
Measured on the dry-run DAG, and confirmed at launch:

| rule | jobs with sharing | without |
|---|---|---|
| `build_renewable_profiles` | **6** | 78 |
| `determine_availability_matrix` | **6** | 78 |
| `base_network`, `cluster_network`, `build_solar_thermal_profiles`, `build_electricity_demand_base`, `build_BE_powerplants` | **1** each | 13 each |
| `build_wallon_demands`, `process_cost_data`, `prepare_sector_network` | 52 (= 13 × 4) | 52 |

The renewable profiles alone are ~23 of the ~43 benchmarked preprocessing minutes,
so this is the difference between paying them once and thirteen times.

**No large download happens.** Both cutouts (2010 and 2013, 6.6 GB each) are in
`data/cutout/archive/v1.0/`; the eight `.vd` files are fetched. Verify with a dry
run that **zero `retrieve_*` rules appear** — if one does, stop and move that step
to a better-connected machine.

First run is a full build (~45 min on 16 cores) because the shared files move from
`resources/walloon/<scen>/` to `resources/`. Keep `LOCAL_CORES=16`: memory, not
cores, is the binding constraint for the 52 concurrent `prepare_sector_network`
jobs.

### 5.2 Push and solve — one orchestrator, thirteen chains

```bash
./cluster/nic5.sh push
./cluster/nic5.sh solve
```

`cluster/config.sh` derives the scenario list from `run.name`, so both commands
cover all thirteen with no arguments. One Snakemake orchestrator on the login node
submits up to `MAX_SLURM_JOBS=16` Slurm jobs.

**Why the parallelism is across scenarios, not inside one.** Myopic foresight
chains 2025 → 2030 → 2040 → 2050 through `add_brownfield`, so a scenario is
strictly sequential: one solve job at a time. Thirteen scenarios give thirteen
concurrent solves, and `MAX_SLURM_JOBS` below the batch size serialises the batch
for no reason.

**Why `batch` and not `hmem`.** `hmem` is three nodes and was fully allocated when
checked on 2026-09-12 (3/0/0/3). `batch` is 70 nodes × 64 cores × 252 GB with a
2-day limit and had **2 601 idle cores** on the same check. The 1 h solve never
needed `hmem`: peak RSS is ~30 GB against 80 GB requested. **Confirmed at launch — all 13 were RUNNING within four minutes, zero
queueing.** On `hmem` the batch would have run one or two at a time.

### 5.3 Pull and post-process locally

```bash
./cluster/nic5.sh pull
RUN_NAME="<one scenario>" ./cluster/nic5.sh postprocess   # do ONE first, see §16.5
./cluster/nic5.sh postprocess                             # then the rest
python scripts/walloon_scripts/fix_scenario_report_index.py --all
```

Then the ClimAct extraction and the S3 upload — **excluding the nuclear sweep**
(§1.4):

```bash
SCENS="scen_central scen_taxshift scen_taxshift_plus scen_biomethane_industrie \
scen_realiste_nets scen_realiste_nobnd30 scen_retardnucleaire"
RUN_NAME="$SCENS" ./cluster/nic5.sh publish      # = extract + upload
```

`publish` is outward-facing. Use `SKIP_S3_UPLOAD=1 HTML_PUBLISH=0` on the
post-process while results are still under review, then publish deliberately.

### 5.4 The report is additive

Per scenario, `generate_html_report` writes
`results/walloon/<scen>/html/pypsa/index.html`. The cross-scenario report is
separate and **skips scenarios that are not solved yet**:

```bash
TMPDIR=$PWD/tmp nohup snakemake --configfile config/config.walloon.yaml \
    --cores 4 results/walloon/index.html > tmp/combined_report.log 2>&1 &
```

Re-run it whenever a scenario lands; each run covers everything finished so far.
Before this change it aborted on the first missing tree, so a combined report
could only ever be built once, at the very end. Unsolved scenarios in
`config/pypsa2html.yaml` are logged as skipped, not treated as an error.

**Run it detached.** It takes ~15 min; a foreground timeout kills the parent and
leaves a `pypsa2html` child writing the same output (§15 E3).

### 5.5 Data transit — what actually crosses the VPN

**Preprocessing runs here, not on NIC5.** `nic5.sh prepare` is a local Snakemake
call; the cluster only ever runs the myopic solve chain (`add_brownfield` →
`solve_sector_network_myopic`). Post-processing, the ClimAct extraction and the
HTML report are local too. So the cluster never reads a `.vd`, a cutout or a cost
table — it reads un-solved networks and writes solved ones.

Planned scope vs what was actually measured on the night:

| leg | planned scope | measured rate | measured volume / time |
|---|---|---|---|
| **up**, first push | ≈ 6.8 GB (trimmed from 20.9) | 17.7 Mbit/s | **1.2 GB on the wire, 11 min** |
| up, 2013 resources | — | " | 936 MB, 2.5 min |
| up, later pushes | tens of MB | " | rsync deltas |
| **down**, pull | ≈ 17 GB | **85 Mbit/s** | ≈ 14 GB over five incremental pulls, ≈ 30 min |
| S3 upload | — | ~2.2 MiB/s | ~1.7 GiB per scenario |

The uplink is ~5× slower than the downlink, so **up** is the leg to optimise.
Three trims got the push scope from 20.9 GB to 6.8 GB:

* **`tmp/` is excluded** — 9.4 GB of leftover linopy `*.lp` dumps, and it is the
  exact directory `REMOTE_ENV` points the cluster's `TMPDIR` at, so pushing it
  both wasted the uplink and littered a directory the solve writes to.
* **`PUSH_EXCLUDES`** (cluster/config.sh) drops stale `resources/` trees from other
  run prefixes (`times-pypsa` 2.7 GB, `walloon-model` 0.9 GB, the 2013 6 h smoke
  test 0.9 GB) and the `.vd` files no active scenario names. `push` uses `-L`, so
  every symlink arrives as a real file — 15 `.vd` symlinks were 1.1 GB of transit
  for 605 MB of need. Clear the variable to send everything.
* **`-z` on the push, deliberately off the pull.** The push carries GB of
  geojson/csv that deflate well (`--skip-compress` for `.nc`/`.tif`); what comes
  back is netCDF4, already zlib-compressed — a measured sample gzips to 97.6 % of
  its size, so compressing the pull burns CPU for ~2 %.

Two further practices, learned on this run:

* **Pull incrementally while the batch is still solving.** rsync re-transfers
  anything whose size or mtime changed, so an early pull is safe and the final one
  takes minutes rather than an hour. The 17 GB is otherwise irreducible:
  `solving.options.store_model` is already `false`, and the solved networks are
  what every local post-processing step reads.
* **The S3 upload saturates the uplink.** While it runs, `ssh` to NIC5 times out
  during banner exchange. Not a fault — do not chase it; check the cluster between
  chunks, or upload after the cluster work is done.

---

## 6. The 2013 weather year — a separate invocation, deliberately

```bash
CONFIGFILE="config/config.walloon.yaml config/config.weather2013.yaml" \
RUN_PREFIX=walloon_2013 RUN_NAME=scen_central_2013 ./cluster/nic5.sh prepare
```

**It cannot join the 2010 batch.** The shared set contains the cutout-derived
files (`profile_*`, `availability_matrix_*`, `solar_thermal_*`,
`electricity_demand_base_s.nc`) and their names carry no year. A 2013 scenario in
the same invocation would overwrite the 2010 profiles, the next 2010 job would
write them back, and both trees would be wrong with every timestamp looking fresh.
`config/config.weather2013.yaml` sets `shared_resources.policy: false` and its own
`run.prefix`, so the run is fully self-contained. The price is one complete
preprocessing pass, which is the right price for a different weather year.

Verified on this run: the 2013 tree's profiles span 2013-01-01 → 2013-12-31 (8760
h) and the shared 2010 profiles were untouched. The pass took **14 min**, not the
~45 expected, because the 2010 batch had already warmed the cutout page cache.

**Solving it concurrently needs a second cluster directory.** Two Snakemake
orchestrators cannot share one working directory's lock. Clone BeeGFS-side so it
costs no WAN transfer, then push only the 2013 resources:

```bash
ssh nic5 'rsync -a --exclude "/results" --exclude "/tmp" --exclude "/.cache" \
    --exclude "/.snakemake/locks" --exclude "/resources/walloon/" \
    /scratch/.../pypsa-wal/ /scratch/.../pypsa-wal-2013/'

REMOTE_DIR=/scratch/.../pypsa-wal-2013 \
CONFIGFILE="config/config.walloon.yaml config/config.weather2013.yaml" \
RUN_PREFIX=walloon_2013 RUN_NAME=scen_central_2013 MAX_SLURM_JOBS=2 \
  ./cluster/nic5.sh push && ... ./cluster/nic5.sh solve
```

**Anchor the rsync excludes with a leading `/`.** Unanchored patterns match at
every depth: `--exclude tmp --exclude results --exclude .cache` silently stripped
nested directories all through the clone, leaving 12 911 of 15 536 files.

**`du` on BeeGFS lies.** A complete clone read as 1.2 GB against a 12.15 GB source
because `du` reports allocated blocks. Compare **file counts** and
`find -printf '%s'` totals instead — both matched exactly once the excludes were
fixed.

---

## 7. Traps

### 7.1 Parent rows in `agg_p_nom_limits`

`add_CCL_constraints` groups by `(location, carrier)`, and `BE` is a parent row
over BEVLG + BEWAL + BEBRU. **A cap put on BEWAL alone is undone by the parent.**
The single most expensive trap in the batch; handled in both places it occurs.

**Nuclear** (§1.3, §1.4): the BE floor moves by the same amount as the BEWAL
floor, Flanders untouched. Without it the 2050 BE floor of 6 000 MW = 3 000 BEVLG
+ 3 000 BEWAL would re-impose the full Walloon build through the parent and the
sweep would come out flat — "nuclear is always built" — for a reason that has
nothing to do with cost. Verified before launch: BEWAL 2050 min 3 000 → 1 000 and
BE 2050 min 6 000 → 4 000 = 3 000 BEVLG + 1 000 BEWAL, so the 2 GW of freedom is
real.

**Realistic potentials**: the Belgian 2030 floors are **dropped**, not lowered.

| carrier | BE floor @2030 | BEWAL capped at | would have been left for Flanders + Brussels | they have today |
|---|---:|---:|---:|---:|
| `solar-all` | ~~16 500 MW~~ | 3 310 MW | ≥ 13 000 MW | ~7 100 MW |
| `onwind` | ~~5 000 MW~~ | 2 366 MW | ≥ 2 800 MW | ~1 780 MW |

Held, the national floor would not have lowered the Belgian 2030 target at all —
it would have **transferred the whole Walloon shortfall to Flanders**, +84 % of
Flemish PV in five years. That contradicts the scenario's own premise, which is
that the 2030 targets are *not* reached. Dropping rather than re-deriving a lower
value also avoids inventing a Flemish trajectory that neither ICEDD nor Elia
published.

The **2025 base-year pins survive** (`BE onwind` 3 337, `BE solar-all` 9 751,
min = max): those are the calibration, not a target. The central scenario keeps
its 2030 floors — `test_central_keeps_the_belgian_2030_floor` pins that the drop
is scoped to the realiste pair.

### 7.2 Why Flanders is never touched

The instruction for the nuclear sensitivities is explicit: Wallonia only,
surrounding nodes unchanged. Every BE parent-row change above is arithmetic — BE
is redefined as the sum of its unchanged Flemish part and its changed Walloon
part. `BEVLG` rows are byte-identical to the central scenario in every generated
file. Re-check after any regeneration with the loop in §4.

### 7.3 `lines.type` is non-empty here

`set_transmission_limit` rebuilds `s_nom_min` from the conductor type and silently
overrides NTC-derated `s_nom`. Unchanged by this batch, but it bites every run —
see the standing note.

### 7.4 Never open `input_parameters_for_models.csv` in a spreadsheet

One save shifted 142 rows' columns. It is LF, not CRLF. The same applies to every
`config/scenarios/*.csv`, which share its schema.

### 7.5 Tooling traps met on this run

* **`results/walloon/*` globs catch retired scenarios.** `scen_demande_haute` and
  `scen_test_2013_6h` still hold solved networks from earlier runs, and a loose
  glob reports them as this batch's progress — it produced one false "gate reached"
  during monitoring. Enumerate the scenario list explicitly.
* **`review_run.py` needs `PYTHONPATH`** set to the repo root, or it dies on
  `ModuleNotFoundError: No module named 'scripts'`.
* **`CONFIGFILE` must be word-split, never quoted.** It may name several files in
  `--configfile A B` order — that is how the 2013 weather year and the 5-year grid
  run. Quoting it as one path is what broke `extract_explorer.sh` (§14.5).

---

## 8. Launch order and gates

The original plan was serial gates: central 2025+2030 (~4 h), then
`scen_realiste_nets` 2030, then the rest. **On this run all 13 were launched
together instead**, because the gate information arrives at the same wall-clock
moment either way: a systemic failure surfaces in the 2025 horizon of every
scenario ~1 h in, completed horizons are kept, and idle cluster cores make a
parallel failure cost nothing but free CPU. The gates exist to avoid wasting an
*unattended* night; with 30-minute monitoring they can be read in flight. That
choice bought ~4 h and cost nothing.

So treat them as **checkpoints, not barriers**:

| gate | what it proves | when it landed |
|---|---|---|
| **A — 2025** | shared-resources change, regenerated cost table (ICEDD's inflated fuel prices), new per-scenario softlink files | first optimum 23:33 (~1 h05 after launch); all 13 by 01:09 |
| **B — 2030** | the realiste pair's rewritten constraint set is feasible — Walloon caps below the old floors, both Belgian floors dropped, CO₂ lifted to 1.0 | first optimum 01:05 |

Both passed. No scenario was ever infeasible or unbounded.

---

## 9. Monitoring

```bash
./cluster/probe.sh --save     # table + append to cluster/logs/probe_history.tsv
```

> **`probe.sh` did not work on this batch and must be fixed before the next one
> (§16.1).** It reported `0/4` and `STOPPED-PARTIAL` for scenarios with
> demonstrably solved networks, and a blank Slurm column throughout: Snakemake
> names its jobs with UUIDs, so no job maps to a scenario and every scenario reads
> as "has networks but no job". **It would not have detected the one real
> failure.** Monitoring fell back to a direct file-count matrix over one ssh
> round-trip, enumerating the scenario list explicitly.

What a working monitor must report, every 30 minutes:

| check | why |
|---|---|
| networks solved / 4 and `Optimal objective` count, **per scenario, enumerated** | the only reliable progress signal |
| age of the newest solver log | a scenario whose log has not moved in >25 min while its job runs is stuck — but a *finished* scenario also has a static log, so exclude 4/4 rows or it false-positives |
| **`grep -l "Numerical trouble\|INFEASIBLE" results/*/logs/*_solver.log`** | `--keep-going` hides a failed horizon: the queue drains normally and nothing reports an error until the whole batch ends (§16.3) |
| `df -h / /home` | both partitions (§15 E1) |
| VPN is `sqvpn`, `tun0` = 10.8.0.2/24 | not ProtonVPN (§15 E2) |

What to do on each signal:

| signal | action |
|---|---|
| barrier residual flat for >1 h | it is not going to converge. `BarHomogeneous: 1` and `crossover: 0` are **already set** in this repo, so the next escalation is `cluster/config_numericfocus.yaml` (§14.1) — and the real fix is §16.6 |
| networks but no job | read `cluster/logs/orchestrate.log`; usually OOM or walltime. Completed horizons are kept, so `nic5.sh solve` resumes |
| no orchestrator | `./cluster/nic5.sh solve` again — it resumes rather than restarts |
| a scenario reaches 4/4 | pull and post-process it alone; the report is additive (§5.4), so results can go out while the rest still runs |

---

## 10. Deliverables and provenance

Per scenario: `results/walloon/<scen>/{networks,csvs,graphs,html,explorer,logs,configs}/`.

For anything that leaves the team, fill a solve log from
`docs/logs/_TEMPLATE_solve_log.md` — **including section 11**, the critical review
(`docs/run-review-checklist.md`). Sections 1–10 say the run finished; section 11
says whether it is right. For a batch, one log per *group* is enough (central,
realiste pair, nuclear sweep) provided section 11 names every scenario it covers.

Provenance to record beyond the template:

* TIMES exports: `s3://intervectoriel/test/scenarios/times_20260911_*`, uploaded
  2026-09-12 09:47–10:02.
* The 2030 Walloon PV/wind floors (6 500 / 3 000 MW) were removed by ICEDD in
  `ee19e962` and **restored** in `c337f36a` for the central case; they are dropped
  per-scenario for the realiste pair only.
* ICEDD's fuel prices arrived at source vintage and were inflated to EUR2025 by
  the method of `common_parameters.md` §4.4 (`de96e610`). Coal 10.92 EUR2021 →
  13.3431; gas 30.345/26.01/21.675 → 37.0786/31.7816/26.4847; oil
  46.4475/51.9119/65.5729 → 56.7542/63.4312/80.1235; uranium 3.4122 EUR2011 →
  4.6497, which is the value `docs/nuclear-alignment-20260816.md` §7 derived
  independently.

---

## 11. The 2030 floors against the Plan Air Climat Énergie

Asked 2026-09-12. The PACE 2030 (adopted 21 March 2023) states its renewable
targets as **annual production**, not capacity, so the honest comparison is in
GWh; the MW column is a conversion at the model's own BEWAL yield for weather 2010
(`resources/.../profile_adm_*.nc`): **2 302 full-load hours** for onshore wind,
**952 h** for non-tracking PV.

| PACE 2030 target | value | source |
|---|---|---|
| onshore wind | **6 200 GWh/a** | raised from the 4 600 GWh of the 2019 PACE, to match the −55 % GHG objective |
| photovoltaic | **5 100 GWh/a ≈ 6 GWc** | PACE 2030 |

| | wind MW | wind GWh | vs PACE | PV MW | PV GWh | vs PACE |
|---|---:|---:|---:|---:|---:|---:|
| PACE 2030 (implied) | 2 693 | 6 200 | — | 5 357 | 5 100 | — |
| *former central floor* | *3 000* | *6 906* | *+11 %* | *6 500* | *6 188* | *+21 %* |
| **central floor (min 2030), since 2026-09-12** | **2 248** | 5 175 | −17 % | **3 145** | 2 994 | −41 % |
| realiste cap (max 2030) | 2 366 | 5 447 | −12 % | 3 310 | 3 151 | −38 % |

**The 2030 floor is now deliberately non-binding.** It is the realistic 2030 cap
minus 5 %, kept only so a number remains on record. The optimiser is expected to
clear it in every scenario without the constraint ever being active, so the 2030
Walloon PV and wind fleets become a model outcome rather than an assumption.
**Confirmed:** the central run built 3 977 MW of wind at 2030, clearing its own
2 248 MW floor by 77 %.

That replaced two floors *above* the PACE: wind 3 000 MW (+11 % in production
terms) and PV 6 500 MW (+21 %). The PV one was never a PACE reading at all — that
row is sourced `Climact on Elia ADEXFLEX, Walloon share`, and the two anchors had
never been reconciled. **Both published anchors are now recorded in the
`note_complementaire` of their own row** in
`config/input_parameters_for_models.csv`, with the PACE production target, the
implied MW at the model's yield, and the build rate each demands — so the
comparison survives without the value steering the run.

The Belgian parent floors (`agg:BE:onwind:min` 5 000 MW, `agg:BE:solar-all:min`
16 500 MW) are **unchanged**: they are the national anchors and still bind on the
Belgian total. Lowering the Walloon floor only stops dictating how that total is
split.

Note the MW column for PV is basis-dependent and the GWh one is not: PACE's own
5 100 GWh / 6 GWc implies **850 h** against the model's 952 h, so part of the gap
is a yield/DC-AC convention rather than a difference in ambition. Read the GWh
comparison.

### 11.1 What each trajectory demands of the build rate

This is the part that decides whether "réaliste" deserves its name.

| | wind MW/yr 2026-30 | PV MW/yr 2026-30 |
|---|---:|---:|
| PACE 2030 | 227 | 538 |
| *former central floor* | *288* | *766* |
| central floor (now) | 138 | **95** |
| realiste cap | 161 | **128** |
| *observed in Wallonia* | *~100–190 (2023–24)* | *~100 MWc added in 2025* |
| **central run's actual 2025→2030 build** | **482** | **~315** |

Wallonia installed about **100 MWc of PV in 2025** against the 500–600 MWc/yr the
PACE needs. The former floor asked for **766 MW/yr — roughly 7.7× the current
rate** — sustained for five years, which is why it was replaced. The floor now in
force asks 95 MW/yr, slightly less than the region is already doing, which is
exactly what makes it inactive.

So the realiste sensitivity is not a pessimistic variant of the PACE: it is the
observed build rate extrapolated, and it lands 38 % below the PACE on PV. **That
is the finding to carry into the presentation — the gap between the central
scenario and the realiste one is mostly a statement about deployment rates, not
about costs or technology.** The central run sharpens it: left free, the optimiser
chose 482 MW/yr of wind, ~3× anything Wallonia has achieved.

---
---

# Part III — What this batch actually did

## 12. Identification

| | |
|---|---|
| Batch | 13 × weather-2010 scenarios + `scen_central_2013` |
| Window | 2026-09-12 18:48 → 2026-09-13 07:39 (2010 batch) |
| Config | `config/config.walloon.yaml` (+ `config/config.weather2013.yaml` for #14) |
| Resolution | 1 h, myopic 2025 / 2030 / 2040 / 2050 |
| Cluster | NIC5 `batch`, 16 cpus / 80 GB per solve, Gurobi 13.0.2 (token licence, `nic5-login1`) |
| Branch | `development_plan` |

## 13. Outcome

| | |
|---|---|
| Networks solved | **51 / 52** (2010) + **4 / 4** (2013) |
| Solved to `Optimal objective` | **every one of them** |
| Infeasible / unbounded | **none, anywhere** |
| Failed | `scen_realiste_nobnd30` @2050 — *Numerical trouble encountered* (§14.1) |

Central-case objectives: 2025 `3.667019e+11` · 2030 `3.758719e+11` · 2040
`2.799588e+11` · 2050 `2.639852e+11`. The critical review of the results
(PASS 191 / INFO 31 / WARN 14 / **FAIL 0**) is in the central solve log.

### 13.1 Timings

| phase | wall-clock |
|---|---|
| preflight + local preprocessing (13 scenarios) | 18:48 → 22:18, including two bug fixes (§14.2, §14.3) |
| push | 11 min |
| solve, 13 chains in parallel | 22:30 → 07:39 (**≈ 9 h**) |
| `scen_central` alone (4 horizons) | 6 h04 — 312/292/243/251 barrier iterations |
| 2013 prepare (local) | 14 min |
| 2013 solve (concurrent, separate remote dir) | 23:01 → ~07:40 |
| pull (5 incremental) + post-process | ~45 min total |

Thirteen scenarios in series would have been ≈ 85 h.

Peak RSS (central) 22.4 / 28.3 / 29.8 / 29.9 GB against 80 GB requested —
identical to the 2026-09-07 run, so the request is right and `hmem` is
unnecessary.

## 14. Issues encountered

### 14.1 `scen_realiste_nobnd30` @2050 — numerical trouble (the one solve failure)

```
iter 24-33: primal residual FLAT at 7.42e+12, complementarity 4.47e+10,
            objective oscillating ~8.72e+15   (other scenarios reach 2.6e+11)
Barrier performed 33 iterations in 869.75 seconds
Numerical trouble encountered
```

`BarHomogeneous: 1` was already set in both configs and crossover is already 0, so
the standing remedy was in force and insufficient. A scan of all 52 solver logs
found this horizon and **no other**; its sister `scen_realiste_nets` solved 2050
normally.

Escalation: `cluster/config_numericfocus.yaml` (`NumericFocus: 3`, `ScaleFlag: 2`),
relaunched as Slurm job 11155390. It converged where the first attempt sat flat —
residual `5.20e+09 → 5.23e+07` over iterations 19→42 — at ~6.7× the cost per
iteration (~147 s against ~22 s).

#### Root cause — two factors, diagnosed 2026-09-13

**NumericFocus treats the symptom. The cause is one config line.**

**Factor A, the enabler.** `config/config.walloon.yaml:243` sets
`threshold_capacity: 0`, overriding PyPSA-Eur's default of `10`
(`config/config.default.yaml:621`). `scripts/add_brownfield.py:107` prunes with
`c.df[f"{attr}_nom_opt"] < capacity_threshold` — and **nothing is ever `< 0`**, so
the filter never fires. Every numerically-zero optimal capacity is therefore
frozen into the next horizon as a fixed, non-extendable asset, and they
accumulate: 388 sub-10 MW components at 2025 → 745 at 2030 → **1 278 at 2040**
(986 links, 157 generators, 135 stores), the smallest at **1.126e-08 MW**. Against
`e_nom_max` values of 1e+09 that is a bound spread of ~17 orders of magnitude —
exactly the `large bounds, large rhs` warning Gurobi issues at every horizon of
every scenario.

What those assets are worth: **94.29 MW of links + 22.86 MW of generators +
17.67 MWh of stores, against a fleet of 258 GW / 502 GW.** Physically 1.5×10⁻⁵ %;
numerically, the whole problem.

**Factor B, the trigger.** 2050 sits on a structural corner, and this scenario is
the batch's extreme point on both stressed axes:

* European solid biomass is **100.0000 % consumed** — 330 920 985 MWh used of a
  330 921 000 MWh cap, i.e. **15 MWh of slack**, shadow price −1267 EUR/MWh
  against −27.9 at 2040.
* The CO₂ cap binds at −471.6 EUR/t, **`dac: false`**, and `coal for industry` has
  no capture variant — so the only negative-emissions route is BECCS on the
  exhausted biomass.
* `scen_realiste_nobnd30` needs **+905 GWh** more industry biomass than its sister
  (into 15 MWh of slack) and **+444 ktCO₂/a** more exogenous fossil demand. Across
  all 14 scenarios it ranks #1 on fossil CO₂ (1 336 kt) and #1 on industry
  biomass (5.00 TWh); `scen_realiste_nets` ranks 13th and 12th.

Neither factor alone explains it: the corner is common to all 14, and *nets
actually carries more denormals* (962 below 1e-3 MW against 917) yet solved. The
corner makes the LP near-degenerate with huge duals; the 17-order bound spread
removes the headroom to resolve them.

**All 13 other scenarios sit on the same corner** — 2050 biomass duals run −1087
to −1308 EUR/MWh, with `scen_nuctip_4500` (−1307.9) actually closer to the edge
than nobnd30. Any modest demand perturbation could tip another one.

Remedy: §16.6. **Not applied to this batch** — restoring the threshold changes
results at every horizon and would need a full re-run from 2025.

### 14.2 `TypeError: Object of type function is not JSON serializable`

`cluster_network` and `simplify_network` did
`aggregation_strategies.get("buses", dict())`, which **aliases**
`config["clustering"]["aggregation_strategies"]` because `buses: {}` has existed in
`config.default.yaml` since the Pydantic merge (`8b064878`, January). `setdefault`
then wrote two lambdas into the live config, and `n.meta = dict(snakemake.config, …)`
could not serialise it on export. Latent for eight months; exposed because
`shared_resources.policy: base` changed which rules run unscoped. Fixed by copying
instead of aliasing, in both scripts.

### 14.3 EV fleet-share guard rejected every scenario at 2025

```
ValueError: TIMES 2025 BEV fleet share 0.0028 is below the road-electricity
energy share 0.0036. ... One of the two extractions is wrong.
```

**The guard's premise had a gap.** It compares a **car-only** count share against
an **all-road** energy share. Its message accounts for the energy *denominator*
carrying freight the car count excludes, but not for the energy *numerator*
carrying every non-car electric class. TIMES gives Wallonia ~199 kveh of two- and
three-wheelers, **48 % electric already in 2025** — byte-identical in the 7 and 11
Sept exports — doing **2.9× the electric km of cars**. Once cars electrify they
are noise; in a year where cars are barely electrified they dominate
`electricity road` and the inequality legitimately reverses.

Car share of electric road km, 11 Sept exports:

| horizon | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| cars as share of electric road km | **0.255** | 0.959 | 0.973 | 0.967 |

**Fix.** The check is gated on its own premise rather than asserted
unconditionally (`CAR_DOMINATED_ROAD_ELECTRICITY = 0.80`,
`scripts/prepare_sector_network.py`): cars ≥ 80 % of electric road km → **hard
error**, exactly as before (2030/2040/2050); below it → **loud warning** naming
both shares (2025 only).

**What is and is not affected.** The 2025 EV **load** is untouched: it is built
from the TIMES *energy* ratio and reproduces the transferred `electricity road`
exactly — the central review confirmed 0.103 vs 0.103 TWh. Only the 2025 charger
`p_nom` and battery `e_nom`, which multiply the car *count*, inherit the
questionable fleet. **Do not read 2025 EV flexibility from this batch** until open
item 7 is settled.

### 14.4 Every per-scenario HTML report opened on a 404

`config/pypsa2html.yaml` has one `landing.scenario: scen_central`, correct for the
combined report, applied verbatim by pypsa2html to per-scenario ones — so 12 of 13
indexes redirected to a page that exists only in the central tree. Fixed by
`scripts/walloon_scripts/fix_scenario_report_index.py` (idempotent, corrects the
generated artefact, leaves pypsa2html and the combined report alone). Found by
post-processing **one** scenario before the rest — see §16.5.

### 14.5 `extract_explorer.sh` died after a successful 2013 extraction

`times_file_for()` passed `"$CONFIGFILE"` **quoted** as a single path while every
other use site word-splits it, so the 2013 run — which needs two config files —
died with
`FileNotFoundError: '.../config.walloon.yaml config/config.weather2013.yaml'`
*after* writing all 49 CSVs. The scenario's TIMES `.vd` was therefore never staged
into its explorer bundle. The six 2010 scenarios were unaffected (single config).
Fixed to word-split and merge in Snakemake's order.

### 14.6 `cluster/probe.sh` does not work on a Snakemake-submitted batch

See the box in §9. Fix is §16.1.

## 15. Workstation environment incidents

Three desktop-level faults, none caused by the run, each masquerading as something
else. **No results were at risk** — `results/` is on `/home`, which never went
below 1.9 TB free.

| # | Symptom seen | Actual cause | Fix |
|---|---|---|---|
| E1 | `ENOSPC` everywhere: conda, Snakemake, the agent's own tooling; post-processing killed mid-run | `/` 100 % full — `/var/log/syslog` at **54 GB** in one day (previous rotation 74 MB), the Pop!_OS COSMIC theme portal retrying a broken D-Bus pipe in a tight loop at ~1.8 MB/s | `sudo truncate -s 0 /var/log/syslog` — **not `rm`**, rsyslog holds the fd. Recovered 51 GB. See instructions.md, "Disk preflight" |
| E2 | `ssh nic5` → *Connection timed out during banner exchange*, surviving a VPN bounce and the disk fix | Two overlapping causes: (a) bouncing `sqvpn` let **ProtonVPN** take the tunnel — it does not route to the CÉCI gateway; (b) `gcr-ssh-agent` spinning at 64 % CPU, so `ssh` hung querying it for a key | (a) `nmcli connection down be-31.protonvpn.udp && nmcli connection up sqvpn`, then check `ip -br addr show tun0` reads **10.8.0.2/24**; (b) `env -u SSH_AUTH_SOCK ssh …` as a workaround. A reboot cleared both |
| E3 | A killed Snakemake left a `pypsa2html` child writing `results/walloon/index.html` | The zombie pattern instructions.md documents. Two writers on one output would have corrupted it | Kill the child, delete the partial output, clear `.snakemake/locks/`. Run long reports detached (§5.4) |

E1 and E2(b) are probably one fault: both the COSMIC portal and `gcr-ssh-agent`
are user-session D-Bus clients stuck retrying a broken session bus, which is why
two unrelated-looking things failed together. **A logout or reboot clears both.**

A separate, benign cause of the same ssh symptom: **the S3 upload saturates the
uplink** (§5.5).

## 16. What must change before the next batch

| # | Action | Why |
|---|---|---|
| 1 | **Fix `cluster/probe.sh`** — match jobs via `.snakemake/slurm_logs/rule_*/<scenario>_*/` rather than Slurm job names, fix the network count, and skip 4/4 rows in the stall check | It is the designated stall detector and it detected nothing. The one real failure was found by reading solver logs by hand |
| 2 | **Add a disk preflight and a mid-run disk check** for `/` **and** `/home`, abort below ~10 GB | A long unattended run on a machine with a filling root partition dies at an arbitrary point with confusing symptoms |
| 3 | **Scan solver logs for `Numerical trouble` / `INFEASIBLE` during monitoring**, not only at the end | `--keep-going` hides a failed horizon: the queue drains normally and nothing reports an error until the batch finishes |
| 4 | Keep `cluster/config_numericfocus.yaml` as the documented second-line remedy | `BarHomogeneous` alone was not enough |
| 5 | Post-process **one** scenario before the rest | It cost 3.5 min and caught §14.4, which would otherwise have hit all 13 reports |
| 6 | **Set `threshold_capacity` to a small non-zero value** — `0.1` MW rather than PyPSA-Eur's `10`, and check the ~257 components between 1e-3 and 10 MW first | The root cause of §14.1. `0` makes the prune a no-op, so solver noise is frozen into the brownfield fleet and compounds each horizon. `0.1` clears the ~917 sub-1e-3 MW components while keeping anything ≥ 100 kW, which matters on a small Walloon node where `10` could prune real plant. **Requires a full re-run from 2025**, so it is a between-batches change |
| 7 | Consider `dac: true`, or admitting a small high-cost unsustainable-biomass tranche | 2050 is priced off a resource with 4.5×10⁻⁸ relative slack. That is a corner solution, not a defensible marginal price, regardless of numerics. Modelling decision — needs ICEDD (the comment records DAC was disabled to match TIMES) |
| 8 | Fix the missing 2050 per-horizon config snapshot | Level-0 provenance item (central review F5) |

Cheap pre-run detectors for the §14.1 failure mode, all seconds and no solve:

1. Count `p_nom_opt`/`e_nom_opt` in `(0, 10)` on the previous horizon's solved
   networks. More than a few hundred means the brownfield threshold is not working.
2. Rank scenarios by the `solid biomass` row of `wallon_demands_2050.csv`; anything
   above the central case's 4.127 TWh is in the danger zone.
3. Rank by exogenous fossil CO₂ (`methane × 0.198 + coal × 0.3361`).
4. After each horizon, read `global_constraints_mu["biomass limit"]`. A jump from
   ~−28 at 2040 to ~−1300 at 2050 is the corner announcing itself.

## 16b. Nuclear is invisible in every per-node chart — reporting artefact, not a model error

Found 2026-09-13 while investigating a result that looked wrong: in the
pypsa2html "Annual costs" chart, **`scen_retardnucleaire` is ~900 M€/a more
expensive at 2050 than the central case** — the opposite of what a nuclear
break-even well below 9 500 EUR/kW implies.

**The model is right; the chart cannot show what matters.** Nuclear is a `Link`
from `EU uranium` → `BEWAL`, and PyPSA-Eur's summary attributes Link costs and
capacities to **`bus0`**. For nuclear that is `EU uranium`, so every euro and
every MW of *Walloon* nuclear is booked to the `EU` pseudo-node. The BEWAL chart
therefore shows the **replacement spending** while the **avoided nuclear cost is
invisible**.

2050, `scen_retardnucleaire` − `scen_central`:

| bucket | central | retard | Δ |
|---|---:|---:|---:|
| **BEWAL, all carriers** ← the chart | 8.153 B | 9.063 B | **+910 M€** |
| `EU` node: **nuclear** (capital + marginal) | 79.491 B | 77.690 B | **−1 801 M€** |
| `EU` node: other | 70.170 B | 69.705 B | −465 M€ |
| all other nodes | 364.001 B | 365.243 B | +1 242 M€ |
| **SYSTEM TOTAL** | **521.814 B** | **521.701 B** | **−113 M€** |

The BEWAL +910 M€ is solar rooftop +317, CCGT CC +309, solar-hsat +213,
battery +101, against −35 distribution grid and −31 CO₂ pipeline.

**Two conclusions, and they are different things.**

1. **The break-even holds.** System-wide, dropping 2 GW of Walloon nuclear is
   *cheaper* (−113 M€/a; the summed objective agrees at −0.034 %). Nuclear at
   9 500 EUR/kW is uneconomic, as the earlier analysis said.
2. **But only marginally**, and that part is a real result rather than an
   artefact: 1 801 M€ of nuclear avoided buys only 113 M€ of net saving, because
   replacement costs +910 M€ in Wallonia and +1 242 M€ in the neighbours. The
   2050 system has almost no substitution room — Walloon wind is **at** its
   6 500 MW potential ceiling, European solid biomass is **100.0000 %** consumed,
   and the import cap binds at exactly 10 TWh (§14.1, and F1/F3 of the central
   review). Removing firm low-carbon capacity from a system against that many
   ceilings costs nearly what the capacity cost.

**Scope of the artefact.** Every per-node cost and capacity chart in the report
is blind to nuclear — including the six-point CAPEX sweep, whose whole subject is
Walloon nuclear. Read the sweep from the networks, not the report.
`review_run.py` is unaffected: it reads the networks directly, which is why it
correctly reported 3 000 MW_e of BEWAL nuclear at 2050 (central) against
1 005 MW_e (retardnucleaire).

### 16b.1 How much Walloon cost is hidden, and which carriers

The rule: **any Walloon technology whose input fuel comes from an EU-level bus has
its cost booked to `EU`**, because the statistics resolve Links by `bus0`.
Measured on `scen_central` (M€/a):

| horizon | reported BEWAL | **hidden** | nuclear | oil boilers | true BEWAL | understated |
|---|---:|---:|---:|---:|---:|---:|
| 2025 | 5 263 | **2 093** | 1 812 | 281 | 7 356 | **28 %** |
| 2030 | 5 491 | **1 145** | 937 | 208 | 6 637 | **17 %** |
| 2040 | 7 055 | **407** | 329 | 78 | 7 462 | **5.5 %** |
| 2050 | 8 153 | **2 122** | 2 122 | ~0 | 10 275 | **26 %** |

Only two carriers matter: **nuclear** (`bus0 = EU uranium`) at every horizon, and
**rural / urban-decentral oil boilers** (`bus0 = EU oil`), which fade as heating
decarbonises. The other eleven EU-sourced carriers at BEWAL (kerosene, coal for
industry, naphtha, methanol, shipping oil, ammonia cracker, …) are **below
0.1 M€/a** — near-zero-cost delivery links whose fuel cost sits on the EU fuel bus.

Note the U-shape: worst at 2025 (legacy nuclear + oil heating) and 2050 (3 GW of
new nuclear); 2040 is the cleanest horizon. **The Walloon cost chart is missing a
quarter of the cost in two of the four horizons**, not a rounding error.

*Not quantified, and a judgement call rather than a bug:* the `EU` node also
carries real European-level cost (fuel production, H₂, shipping — 70.2 bn/a at
2050) of which Wallonia consumes a share. Whether a "Walloon cost" should include
an imputed share of that is an accounting decision. The table above is strictly
the cost of **plant that physically sits in Wallonia**.

### 16b.2 Where the fix belongs

Narrower than it first appears. `assign_locations()` in `scripts/make_summary.py`
**already computes the right answer** — verified: after calling it, the nuclear
links carry `location` ∈ {BEWAL: 2, BEVLG: 2, GB: 2, DE/FR/LU/NL: 1}. The problem
is that

```python
n.statistics.capex(groupby=["location", "carrier"])
```

**ignores that column** and re-derives the location from `bus0`, collapsing every
nuclear link to `EU`. `assign_locations` is therefore effectively dead code for
branch components, and the same applies to
`calculate_nodal_capacities` (`n.statistics.optimal_capacity`) — which is why
nuclear *capacity* is also reported at `EU` (274 726 MW_th system-wide) rather
than at BEWAL.

Fix in how the statistics call is made — pass the precomputed grouper, or group
these carriers by `bus1` — rather than by patching the artefacts afterwards.
Best landed in the pypsa2html work rather than retrofitted.

Until then, **do not present any per-node cost or capacity chart involving
nuclear** without stating what it omits.

## 17. Publication

Post-processing ran with `SKIP_S3_UPLOAD=1 HTML_PUBLISH=0` throughout the batch —
open item 7 was unresolved and publication is outward-facing. Published
deliberately afterwards, for the **seven non-sweep scenarios only** (§1.4):
`scen_central`, `scen_taxshift`, `scen_taxshift_plus`, `scen_biomethane_industrie`,
`scen_realiste_nets`, `scen_retardnucleaire`, `scen_central_2013`, with
`scen_realiste_nobnd30` joining once its 2050 lands.

The six `scen_nuctip_*` are **not** extracted and **not** uploaded as scenario
trees, and they are **not** scenarios in the combined report. They appear in it
only as the *Sensitivity analyses* page — one curve, built from their solved
networks, inside every published scenario's `html/pypsa/` folder (§1.4).

## 18. Open items

| # | Item | Who | Blocking? |
|---|---|---|---|
| 1 | Sludge is inside the BEWAL `solid biomass` pool (renewable-potentials.md §9.7). PyPSA cannot keep sludge and wood apart on one bus, so the optimiser may burn in boilers what TIMES sends to industry and power. Confirm, or drop `BIOSLU` from the industry extraction. **The central review found the sharp end of this**: at 2050 both TIMES biomass-boiler heat pins are 100 % undelivered (1.599 TWh_th) because the pool is priced by its scarcest use | ICEDD | no |
| 2 | **Confirm the swapped-increment correction** (§1.2): 2 366 MW wind / 3 310 MW PV instead of ICEDD's 2 203 / 3 474 | ICEDD | no — one value per file to revert |
| 3 | Confirm the currency year of the DG CLIMA "recommended parameters for reporting GHG projections in 2025" fuel prices. ICEDD tagged them EUR2021 and that is what the EUR2025 inflation assumes; the parameter file is not publicly fetchable. The uranium row needs no confirmation — its source note says "Based on IEA 2011 data" and the inflated value (4.6497) reproduces `docs/nuclear-alignment-20260816.md` §7 exactly | ICEDD | no — reversible in one commit |
| 4 | Nuclear sweep bracket: widen downwards if 4 500 EUR/kW still builds nothing | — | after the first results |
| 5 | PV 2030 floor is 6 500 MW from Elia AdeqFlex, 21 % above the PACE's 5 100 GWh, and was never reconciled with it (§11) | Sylvain / cabinet | no |
| 6 | `scen_base`, `scen_corrige`, `scen_nuc11500`, `scen_nuc13500`, `scen_imppel`, `scen_data` are from Nov–Dec 2025 and unmanaged. Retire or migrate to an override file | Sylvain | no |
| 7 | **The 2025 Walloon BEV car fleet collapsed 52× between the 7 and 11 Sept exports** (248 880 → 4 757 cars; road electricity 0.895 → 0.103 TWh). Neither figure is credible — Wallonia's real 2025 BEV stock is in the tens of thousands, so 248 880 looks like a Belgium-wide total applied to the region and 4 757 is ~10× too low. Confirm which is right and re-export 2025 if needed (§14.3) | ICEDD | no — 2025 only, and the EV *load* is exact either way |
| 8 | Walloon onshore wind sits **at its 6 500 MW potential ceiling at both 2040 and 2050**, so the post-2030 wind fleet is an assumption, not a result. A sensitivity on that potential would be more informative than any cost sensitivity in this batch (central review F1) | Sylvain | no |
