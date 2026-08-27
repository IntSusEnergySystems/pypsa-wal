# Proposal: scenario variants as parameter-override files

> **Status: PROPOSED — not implemented.** Nothing in the tree behaves this way yet.
> Discussed 2026-08-27. Sequencing and effort in §7.

## 1. The problem

A scenario's hypotheses are currently spread across four places, with no single
file that answers *"what makes this scenario different?"*:

| where | what it carries today |
|---|---|
| `config/scenarios.walloon.yaml` | the `.vd` file, config-key overrides, and **paths to data files** |
| `data/walloon/agg_p_nom_minmax_<scen>.csv` | aggregate capacity limits, one whole file per scenario |
| `data/walloon/custom_potentials_<variant>.csv` | potentials, one whole file per variant |
| `config/input_parameters_for_models.csv` | everything else — but see below |

The last row is the real defect. That file presents itself as the shared
TIMES/PyPSA table, and `common_parameters.md` §2 documents it as such, but it is
**already silently specific to one scenario**:

```python
# scripts/build_common_parameters.py
AGG_FILE = ROOT / "data" / "walloon" / "agg_p_nom_minmax_demande_haute.csv"
```

with the docstring *"Other scenarios keep their own agg files; this patch does not
touch them."* Its nuclear rows cite `scen_demande_haute_v01_260727`.

So `scen_base` and `scen_corrige` have **unmanaged** input files, and that is
exactly where they rotted: the decimal-shift typos found on 2026-08-26 (NL
`33543`, GB `96158`, DE `65396`) were all in `base`/`corrige`. The managed
demande-haute file was clean. Direct evidence both that the management mechanism
works and that anything outside it degrades.

The symptom that prompted this: after the 2026-08-27 renewable-limits rewrite,
the three `agg_p_nom_minmax_*` files differ in **2 of 54 rows** — the nuclear
caps. The other 52 are duplicated three times with nothing checking them against
each other.

## 2. The proposal

Split the **registry** from the **values**.

`config/scenarios.walloon.yaml` stays the registry: one place listing every
scenario, its `.vd`, and where its assumptions live. Three lines per scenario.

```yaml
scen_base:
  sector:
    times_file: data/walloon/scen_base_251129_0112.vd
  run:
    parameter_overrides: config/scenarios/scen_base.csv
```

`config/scenarios/<scen>.csv` holds the values, in the **same schema** as
`input_parameters_for_models.csv`, listing only what the scenario changes:

```csv
type,...,parameter,year,value,units,source,...,pypsa_wal_target,year_rule,status
local_RES_potential,...,p_nom_min,2050.0,1340,MW,TIMES vd scen_base_251129,...,agg:BEWAL:nuclear-all:min,hold,active
```

`build_common_parameters.py --write --scenario scen_base` then layers that file
over the master and regenerates **that scenario's** outputs. `--check` verifies
every scenario, so drift becomes impossible rather than merely unlikely.

The per-scenario data files (`agg_p_nom_minmax_base.csv`,
`custom_potentials_imppel.csv`, …) survive as *generated artefacts*, still
committed and still read by PyPSA — but nobody edits them by hand, and the
file-swap overrides in the YAML disappear.

## 3. Why not put the values in the YAML directly

This was the first instinct, and the pattern already exists:

```yaml
scen_nuc11500:
  costs:
    overwrites:
      investment:
        nuclear: 11500000
```

Two reasons not to build on it.

**Upstream is retiring it.** `scripts/process_cost_data.py:176` warns when it
applies those overrides:

> `Config-based cost overwrites is deprecated. Use external file instead (by
> default 'data/custom_costs.csv').`

Extending a deprecated mechanism is how the divergences catalogued in
`common_parameters.md` §3 accumulated in the first place.

**It would cost the columns that make the table defensible.** The value of
`input_parameters_for_models.csv` is not its format — it is `source`,
`description_complementaire`, `note_complementaire`, `units`, `year_rule`,
`status`, the unit-compatibility checks, and above all `--check` proving the
generated inputs still match the table. YAML can express those as nested
mappings, but the validation and the round-trip guarantee would have to be
rebuilt. That guarantee is what caught the decimal-shift typos.

A secondary point: with values inline, eight scenarios × tens of overrides is a
long shared file and a merge-conflict hotspot, and a scenario's hypotheses become
a *block* rather than a *file*.

**Also rejected: a `scenario` column in the master CSV.** Cheaper — no layering,
no new files, one git history — but it does not give "all the hypotheses of one
scenario in one place"; you would be filtering a 700-row table. It is the right
answer only if scenarios stay at two or three overrides each.

## 4. Semantics to fix before writing code

Ambiguity here is what turns a layering mechanism into a debugging problem.
Proposed answers, to be confirmed:

| question | proposed |
|---|---|
| Override key | composite `(pypsa_wal_target, year)` |
| Granularity | override replaces the **whole row**, not just `value`, so `source` and `note` travel with the deviation |
| Deleting a baseline row | an override row with `status: none` |
| Adding a row the baseline lacks | allowed |
| Chaining (scenario B inherits A) | **not allowed** — one flat level. Inheritance graphs are where this design usually goes wrong |
| Which outputs are per-scenario | `agg`, `potential`, and `config` targets. `ntc` is global (the grid does not depend on Walloon demand); `cost` and `hurdle` global unless a scenario genuinely varies them — `scen_nuc*` does, so `cost` probably needs it too |

## 5. New failure mode this introduces

Today's hazard is files drifting apart. Afterwards it is a **baseline improvement
silently masked by a stale override** — the RES envelope is improved in the
master, a scenario pins an old value, nobody notices.

Mitigation: `--report` must list, per scenario, every row it overrides and the
baseline value it replaced, so every delta is visible on demand. Worth building
at the same time, not later.

## 6. What it buys

- **One reviewable file per scenario**, with provenance per deviation.
- `diff config/scenarios/scen_A.csv config/scenarios/scen_B.csv` becomes a
  meaningful statement of what separates two scenarios. Not obtainable today.
- **Removes the duplication**, and with it the class of error that put four
  decimal-shift typos into the unmanaged files.
- **A net reduction in mechanisms.** The file-swap overrides go away —
  `scen_imppel` currently swaps an entire potentials file to change a few rows,
  which is exactly what the `scenarios.walloon.yaml` header warns against
  (*"Do not copy a cost file to vary one number"*).
- No dependence on a deprecated upstream path.

## 7. Effort and sequencing

**Effort: moderate, and it sits upstream of everything.** The layering itself is
small (~40 lines: read the override file, merge on the composite key, hand the
result to the existing `collect_targets`). The work is in making the outputs
scenario-aware: `build_common_parameters.py` has **seven hardcoded output paths**
and **six patch functions** (`patch_costs`, `patch_potentials`, `patch_ntc`,
`patch_agg_p_nom`, `patch_walloon_config`, `patch_discount_rates`), each writing
to a single fixed file. Plus `--check`/`--write` looping over scenarios, Snakemake
wiring, and tests. Budget a careful day, touching the script that generates every
input the model reads.

**Do it after the next production run, not before.** The renewable-limits rewrite
of 2026-08-27 has not been solved yet. Refactoring the input-generation layer at
the same time means two large changes in flight with no clean comparison point.
Run the current configuration first, confirm the limits behave, then refactor
against a known-good baseline.

**Scope it as a replacement, not an addition.** The success test: after the
refactor, `scenarios.walloon.yaml` contains only scenario names, their `.vd`, and
their override file. If it still carries data-file paths and `costs: overwrites:`
blocks, there are three mechanisms instead of one and the change was not worth
making.

## 8. Related open items

Two things worth folding in rather than fixing separately:

- **`scen_nuc11500` and `scen_nuc13500` point at `data/agg_p_nom_minmax.csv`** —
  the upstream *example* file (30 rows, `1e9` maxima). They therefore get no
  2025 pin and no 2030 corridor from
  [`renewable-potentials.md`](renewable-potentials.md). The build-rate limit
  still applies to them (it keys off the rate table, not the CSV), but they are
  otherwise unbounded.
- **`agg_p_nom_minmax_sensitivity.csv`** (used by `config.scen_corrige_test.yaml`)
  keys Belgium per region rather than parent + region, so it is a fourth
  structural variant. It should either be converted or retired.

And a question this proposal does not answer: **are `scen_base` and `scen_corrige`
still live?** Their `.vd` files are from 2025-11-29 and `docs/logs/` contains only
`scen_demande_haute` runs. If they are retired, deleting them is cheaper than
migrating them.
