# TIMES Sankey diagrams in the results report

One interactive Sankey per planning horizon, at two aggregation levels, written
into the scenario's own `html/` folder next to the
[pypsa2html report](../instructions.md#html-report-pypsa2html).

**Status:** implemented. Enabled in
[`config/config.walloon.yaml`](../config/config.walloon.yaml) under
`sector.times_sankey`. Rendering lives in the sibling
[`TIMES_PyPSA`](https://github.com/IntSusEnergySystems/TIMES_PyPSA) repository
(`times_pypsa.sankey_pages`); this repo only wires the Snakemake I/O.

---

## 1. What it produces

For the default Walloon horizons and levels, `results/walloon/<scenario>/html/`
gains nine files:

```
times_sankey_index.html            ← year x level table, start here
times_sankey_custom_2025.html      ← the readable working level
times_sankey_custom_2030.html
times_sankey_custom_2040.html
times_sankey_custom_2050.html
times_sankey_mapping_2025.html     ← the extraction level (Aggregation Level 2)
times_sankey_mapping_2030.html
times_sankey_mapping_2040.html
times_sankey_mapping_2050.html
```

Each page is self-contained apart from the Plotly CDN script, carries a netting
toggle, cross-links to the other year and the other level, and states its TIMES
source `.vd`, aggregation level, unit and generation time in the footer.

The two levels are the two that matter (see
[`TIMES_PyPSA/aggregation.md`](../../TIMES_PyPSA/aggregation.md)):

| File token | `--agg-level` | What it is |
|---|---|---|
| `custom` | `custom` | Export-touching `Aggregation Level 2` labels kept, everything else collapsed into readable context buckets (~45 nodes). **The view to read the system on.** |
| `mapping` | `Aggregation Level 2` | The grain the process mapping and `extraction_rules.csv` filter on, i.e. the flows exactly as the soft-link extraction sees them. Hundreds of nodes — for tracing one flow, not for reading the system. |

**These diagrams describe the TIMES input, not the PyPSA solve.** They come from
the same `sector.times_file` that `build_wallon_demands` extracts the demands
from, which is the point of shipping them with the PyPSA report: links exported
to pypsa-wal are coloured by PyPSA sector, so a demand that looks wrong
downstream can be traced back to the TIMES flow it came from — and a flow that
should have been exported but is grey is the soft-link gap itself.

## 2. Configuration

```yaml
sector:
  times_file: data/walloon/scen_base_coherence_3110.vd
  times_sankey:
    enable: true
    levels:
    - custom
    - Aggregation Level 2
    units: twh
    threshold: null      # minimum ribbon in `units`; null keeps every flow
```

`levels` accepts any aggregation level shared by the two mapping CSVs
(`custom`, `Aggregation Level 2`, `sankey_overview`, `Sector`, `L2`); a typo
fails immediately with the available list rather than after the `.vd` parse.

**This block is read at parse time and must not be scenario-varied.** The rule's
outputs are one file per (horizon × level), so the list has to exist before the
DAG is built — `config` at that moment is the merged config *before* scenario
overlays. `times_file` may vary per scenario (it is a rule input, resolved per
`{run}` through `config_provider`); `times_sankey` may not, and neither may
`scenario.planning_horizons` — the script raises if a run's horizons differ from
the ones its file names were built for, rather than writing a page labelled with
the wrong year.

## 3. Running it

Part of `rule all`, so a full workflow run produces it. On its own:

```bash
snakemake --configfile config/config.walloon.yaml --cores 1 \
  results/walloon/scen_demande_haute/html/times_sankey_index.html
```

It needs no solved network — only the `.vd` and the mapping CSVs — so it can be
built before a solve to check the TIMES side first. `./cluster/nic5.sh
postprocess` builds it too (`TIMES_SANKEY=0` to skip). Cost for four horizons ×
two levels: **~9 s, ~0.9 GB** (`results/<run>/benchmarks/build_times_sankey`).

Outside Snakemake, the same pages come from the CLI:

```bash
times-pypsa sankey-pages \
  --vd data/walloon/scen_demande_haute_v01_260727_fix_nuc_2807.vd \
  --out-dir results/walloon/scen_demande_haute/html \
  --years 2025,2030,2040,2050 \
  --scenario-label scen_demande_haute
```

## 4. Robustness

Everything here is designed to be inert when it cannot work, and loud when it is
wrong:

| Situation | Behaviour |
|---|---|
| `times_pypsa` not installed | Rule is never defined, `rule all` gains no target, one warning at parse time. The rest of the workflow is unaffected. |
| `sector.times_file` unset | Same, with a warning naming the missing key. |
| `sector.times_sankey.enable: false` | Same, silently — the intended off switch. |
| Mapping CSV edited | The same `times_mapping_files` input as `build_wallon_demands`, so a label fix invalidates the diagrams too. Without this the report would keep showing a flow the way the *old* mapping saw it — the 2026 heat-leak failure mode of `heat-softlink.md` §10.6. |
| A horizon absent from the `.vd` | The page is still written and says "no data"; the index flags it and the log warns. A declared output that silently did not appear would fail the rule instead of showing the gap. |
| Mistyped aggregation level | `ValueError` listing the available levels, before the `.vd` is even read. |
| `scenario.planning_horizons` overridden per scenario | `ValueError` naming both lists and how to resolve it. |

## 5. Why a separate rule, not part of `build_wallon_demands`

`build_wallon_demands` writes into `resources/`, which the
`run.shared_resources` policy may share between runs; the diagrams belong to one
scenario's `results/` tree. Keeping them apart also means the report can be
rebuilt (new labels, another level, different unit) without invalidating the
demand CSVs and therefore the solved networks.

## 6. Why one job for all pages

`export_sankey_pages` parses the `.vd` once and tags each year's flows once,
then renders every level from that. A rule per (horizon × level) would re-parse
the same 900 k-line file eight times. The index is written **last**, after every
page, which is why the cluster script can use it as the single sentinel target
for the whole set.
