# TIMES scenario indicators in the results report

One filterable **Indicateurs** table plus four trajectory pages — final energy
demand, greenhouse-gas emissions, heat production and the power fleet — written
into `html/indicators/` beside the Sankeys in `html/times/` and the pypsa2html
report in `html/pypsa/`. The hub at `html/index.html` links all three sections.

**Status:** implemented. Enabled in
[`config/config.walloon.yaml`](../config/config.walloon.yaml) under
`sector.times_indicators`. The extraction and rendering live in the sibling
[`TIMES_PyPSA`](https://github.com/IntSusEnergySystems/TIMES_PyPSA) repository
(`times_pypsa.indicators` / `times_pypsa.indicator_pages`); this repo only wires
the Snakemake I/O. **The definitions, and where they differ from the figures
ICEDD published in December 2025, are in
[`TIMES_PyPSA/INDICATORS.md`](../../TIMES_PyPSA/INDICATORS.md)** — read that
before quoting a number.

---

## 1. What it produces

`results/walloon/<scenario>/html/indicators/` gains five pages, an index, a
DirectoryIndex copy of it, and one CSV per chart:

```
times_indicators_index.html        ← start here
times_indicators_catalogue.html    ← Indicateurs [TIMES]  (filterable table)
times_indicators_demand.html       ← Consommation d'énergie [TIMES]
times_indicators_emissions.html    ← Émissions de CO2 [TIMES]
times_indicators_heat.html         ← Production de chaleur [TIMES]
times_indicators_power.html        ← Production et capacité électriques [TIMES]
index.html                         ← copy of the index, for a bare indicators/ URL
times_indicator_*.csv              ← the table behind each chart
times_indicator_catalogue.csv      ← every series, tidy
```

The four charted pages are a stacked bar per planning horizon with the total
drawn on top, next to the table it was built from; they are self-contained apart
from the same Plotly CDN script the Sankeys use, and cross-link to each other.

**`times_indicators_catalogue.html`** is the entry point: every series on one
page, filterable on four facets (catégorie / indicateur / vecteur /
technologies) with a keyword box, sortable columns, a sparkline and a Δ% column.
It mirrors the shape of the Explorer's *Indicateurs* page — deliberately, so the
two read alike — but not its contents: that page is built from the PyPSA
extraction, this one from the `.vd`. Its sparklines are inline SVG rather than
Plotly, so the page loads no chart library at all. Every row is a leaf series,
so a filtered selection can be summed; the one exception the page flags is
aviation kerosene, which is a demand series but not part of a sector's final
energy.

The CSVs are a deliverable in their own right: they are the tables the report
text quotes, in the same shape (`Total` row first, one column per horizon).
Turn them off with `sector.times_indicators.write_csv: false`.

## 2. What the numbers are

**Not the PyPSA solve.** These come from the same `sector.times_file` `.vd` that
`build_wallon_demands` extracts the demands from — they describe the TIMES
*input* to the soft link. Reading them next to the PyPSA report is the point: a
demand that looks wrong downstream can be traced to the trajectory it came from.

| Page | Metered on | Unit |
|---|---|---|
| Demand | `VAR_FIn` on the sector-owned carrier (`RSDGMX`, `INDELC`, …), attributed to the sector of the consuming process | GWh |
| Emissions | per-process `CO2N + CO2P + 28·CH4 + 265·N2O`, biogenic excluded, capture shown separately | ktCO2eq |
| Heat | `VAR_FOut` of the heating device, so a heat pump shows heat and not electricity | GWh |
| Power | electricity onto any bus (grid voltages **and** the sector carriers, because industrial CHP never reaches a grid bus) | GWh / GW |

Three consequences worth knowing before reading a chart:

- **Home EV charging is in Transport, not Residential.** It draws `RSDELC` but
  the charger is a transport process, and the table follows the process.
- **Cogeneration fuel is split.** Only the heat-allocated share is charged to the
  sector; the rest belongs to generation.
- **Aviation kerosene is shown but not summed** into the transport total — it is
  an international bunker. On the transport chart it is the hatched grey bar
  *beside* the stack, so the stacked height is what the total line says.

## 3. Configuration

```yaml
sector:
  times_indicators:
    enable: true
    write_csv: true
```

Read at **parse** time, like `sector.times_sankey`: the rule's outputs are one
file per indicator group, so the list has to exist before the DAG is built. That
means the block must **not** be moved into a scenario overlay. `times_file` may
vary per scenario (it is a rule input, resolved per `{run}`).

There is no horizon setting. **The pages chart every model year in the `.vd`** —
2021, 2022, 2025, 2030, 2035, 2040, 2045, 2050 for the Walloon scenarios — not
`scenario.planning_horizons`. These are the TIMES trajectory, and drawing only
the four years PyPSA steps through dropped 2021, the calibrated base year every
number in [`INDICATORS.md`](../../TIMES_PyPSA/INDICATORS.md) is reconciled
against, and left holes at 2035 and 2045. Nothing downstream reads the pages, so
the two year lists have no reason to agree, and the rule needs no parse-time
overlay cross-check (unlike `build_times_sankey`, whose file names carry years).

The rule is skipped, with a warning and no other effect on the workflow, when
`sector.times_file` is unset or `times_pypsa` is not importable
(`pip install -e ../TIMES_PyPSA`).

## 4. Wiring

| Piece | Where |
|---|---|
| Parse-time gate + rule | [`rules/postprocess.smk`](../rules/postprocess.smk), `_times_indicators_settings` / `build_times_indicators` |
| Script | [`scripts/build_times_indicators.py`](../scripts/build_times_indicators.py) |
| Hub page, third section | [`rules/publish_html.smk`](../rules/publish_html.smk), `write_html_hub` |
| `rule all` target | [`Snakefile`](../Snakefile), `times_indicator_targets()` |

Rule inputs include the three `indicator_*.csv` rule tables plus
`mapping_processes.csv` and `AllCommodities.csv`, so editing a mapping
invalidates the pages. Without that, Snakemake keeps serving the chart the old
mapping drew — the same failure mode that kept the 2026 Walloon heat leak in the
solved networks after it had been fixed upstream (see
[`docs/heat-softlink.md`](heat-softlink.md) §10.6).

Build just the pages:

```bash
snakemake --configfile config/config.walloon.yaml --cores 1 \
  results/walloon/scen_demande_haute/html/indicators/times_indicators_index.html
```

Or outside the workflow, straight from a `.vd`:

```bash
times-pypsa indicators --vd data/walloon/<scenario>.vd --out-dir /tmp/indicators \
  --scenario-label "demande haute"
```

## 5. Publishing

`publish_html` rsyncs the whole `html/` folder, so the indicators go up with the
rest to `https://pypsa.squoilin.eu/<scenario>_<YYYYMMDD>/`. Note that the rsync
uses `--delete`: publishing from a results folder that has not built
`html/pypsa/` will **remove** the PyPSA report from an existing remote folder.
To add the indicators to an already-published run without rebuilding the rest,
sync the subfolder on its own and update `index.html` by hand.
