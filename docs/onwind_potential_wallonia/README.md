# The technical potential for onshore wind in Wallonia

**[onwind_potential_wallonia.pdf](onwind_potential_wallonia.pdf)** — land-eligibility
and siting analysis of Walloon onshore wind against the Region's own regulatory
instruments, and what it implies for `potential:BEWAL:onwind:p_nom_max`.

Produced by [`workflow_onwind_wal/`](../../workflow_onwind_wal/):

```bash
cd workflow_onwind_wal && snakemake -c4 report
```

**No PyPSA-Wal input has been modified.** This is the evidence base for that
decision, not the decision.

## Scope

The **administrative Walloon Region** (16 905 km²), not the model's `BEWAL`
node. The node covers 89.6 % of the Region — western Hainaut falls on the
Flemish side of the Voronoi partition — and is out of scope here; §1.4 of the
report states the difference and its consequences.

## Headline

Reference turbine NREL 2020ATB 4 MW (tip 185 m), 5 D between any two machines.

| | Wallonia (administrative) |
|---|---:|
| eligible land, all implemented constraints | 420 km² (2.5 %) |
| free allocation — *land-and-wake bound*, the quantity BREGILAB reports | 11 460 MW |
| + parks of four, then smaller groups only on the land left | 11 084 MW |
| + open horizon, 130° within 4 km of each village — **gross reference** | **8 172 MW** |
| **central estimate** (+ residual allowance for birds and partial constraints) | **6 252 MW** |
| credible range | 4 576 – 8 172 MW |
| *if the recommended 4 / 6 km inter-distance were applied as a rule* | 6 316 / 4 892 MW gross |
| PyPSA-Eur default land analysis (area × 3 MW/km²) | 19 079 MW |
| BREGILAB / VITO Dynamic Energy Atlas, gross | 11 400 MW |
| BREGILAB's own rules applied to open data | 25 087 MW |
| cap in the model today | 6 500 MW |
| standing fleet, end 2024 | 1 528 MW |

## What the answer depends on

The Cadre de référence is a circular *à valeur indicative* and the plan de
secteur admits derogations for wind farms (CoDT D.IV.11), so the rules that shape
the answer are mostly policy. Each is priced on the gross reference (§7):

| one change from the reference | gross MW | Δ |
|---|---:|---:|
| no agricultural corridor (derogation route) | 10 772 | +32 % |
| every coniferous stand, no distance to a main axis | 10 988 | +34 % |
| the whole forest zone, broad-leaved stands included | 14 024 | +72 % |
| no open-horizon rule | 11 084 | +36 % |
| parks of at least four, without the exception above 3.2 MW | 6 480 | −21 % |
| inter-distance 4 km between parks, motorways exempt | 6 316 | −23 % |
| inter-distance 6 km between parks, motorways exempt | 4 892 | −40 % |
| 2013 habitat setback (4 × tip height) | 6 408 | −22 % |
| corridor lifted and every coniferous stand, horizon kept | 13 368 | +64 % |
| 6 km inter-distance and parks of four without exception | 4 336 | −47 % |

## The rules, as the texts state them

| rule | reference | basis |
|---|---|---|
| distance between machines | 5 D (750 m) | nearest-neighbour distance of a 5D×7D array; BREGILAB's rule; the fleet sits at 4.3 D |
| park | ≥ 4 machines first, then smaller groups only on the land left; 1.5 km linkage; no radius or centre separation | Cadre 2024 §3.1, including the exception above 3.2 MW where it does not reduce the zone's potential |
| open horizon | 130° free within 4 km of each village | Cadre 2024 §3.4 §3; 6 of 880 affected villages breach it today |
| inter-distance | **sensitivity only** | Cadre 2024 §3.4 §3: 4 km (short views) to 6 km (long views) "recommandée et peut être réduite", not along motorways, measured between nearest masts; 53 % of standing farms are closer than 4 km to another |
| agricultural corridor | 1.5 km from a PIC or a zone d'activité économique | CoDT R.II.36-2; a PIC is a motorway, a 2×2 regional road, a railway or a waterway (R.II.21-1) — not every plan-de-secteur road |
| setbacks | 500 m + H/2 from habitat zones; 400 m from dwellings outside the economic zones | Cadre 2024 §3.2 §2 |

## Calibration

Everything is tested against the **652 turbines standing in Wallonia**
(OpenStreetMap).

- **Constraint set.** Every layer is avoided by the fleet. Conditional on the
  other layers, the plan-de-secteur landscape perimeters (0.04), the
  aeronautical rings (0.12), the slope criterion (0.15) and the ADESA inventory
  (0.25) are strongly avoided; the infrastructure distances least (0.61).
- **Zoning.** 79 % of the fleet stands where the zoning admits a turbine with
  the CoDT's PIC network: about one machine in five was permitted by derogation
  or before the present code.
- **Farm geometry.** Measured between nearest masts, 53 % of the 134 farms have
  a neighbour closer than 4 km (39 % of those not along a motorway); only 34 %
  of the machines stand within 1 km of a motorway.
- **Layouts.** Every placed layout is checked against its own rules by an
  independent implementation; the run fails if one is broken.

## Files

| | |
|---|---|
| `onwind_potential_wallonia.tex` | the report; every number comes from `generated/macros.tex` |
| `generated/` | LaTeX macros and table fragments, written by the workflow |
| `figures/` | copies of `workflow_onwind_wal/results/figures/`, for standalone compilation |

Do not edit `generated/` or `figures/` by hand — re-run the workflow.

## What is an allowance rather than geometry

Two families remain unrepresentable and carry a documented, bracketed
allowance: the DEMNA priority-bird zones (10 %, 0–20 %) and the method's
*partial* constraints (15 %, 0–30 %). The skeyes and Defence red zones are not
published and are not represented at all; they are the most likely reason
BREGILAB's published figure is less than half of what its own rules give on open
data. See §8 and §11.

## Next: the commune level — data audit and roadmap (8 October 2026)

**The question.** For each commune, the work must produce:

- the eligible area under the rules above;
- the potential (machines, MW);
- what already stands;
- the densities (MW/km², kW per inhabitant), for installed and potential capacity;
- an approximation of the grid capacity still available (Elia);
- a commune dashboard carrying every map and element of the regional one;
- the data of the SPW *carte dynamique solaire et éolien*.

**The principle: compute for the Region, attribute to the communes.** The
constraint set, the placement and the "Et si… ?" states stay those of the
regional study. Each eligible cell and each placed mast is attributed to the
commune it lies in, so commune figures add up exactly to the regional ones. A
placement run commune by commune would be wrong for two reasons: it would cut
parks at every boundary, and the open-horizon rule looks at villages on the
other side of the boundary.

### Data audit

Samples fetched on 8 Oct 2026 are in `workflow_onwind_wal/data/communes_probe/`
(gitignored, with a `PROVENANCE.md`).

| need | source | access | finding |
|---|---|---|---|
| commune boundaries | Géoportail `LIMITES/LIMITES_ADMINISTRATIVES`, layer 3 | REST, CC BY | 261 communes as of 1 Jan 2025. Bastogne and Bertogne merged (82003 + 82005 → 82039); older sources still have 262 |
| population | Statbel `TF_SOC_POP_STRUCT_2026` (1 Jan 2026) | open-data zip, 2.6 MB | ok |
| installed wind and PV, by commune | SPW Énergie *carte dynamique* (built by 3E; the page is an iframe on `zealous-nobel-aa39f4.netlify.app`) | the app's own static CSVs, keyed by NIS code, no login | Monthly MW per commune since 2015 for wind and PV; the realtime files split PV < / > 10 kVA. Also monthly production, inhabitants and areas. **Wind has been frozen at 1 436.2 MW (107 communes) since January 2025**, although the FAQ promises six-monthly updates. **Production is modelled, not metered**: ERA5 wind, an average power curve and the commune's capacity, scaled on Elia. The endpoint is undocumented, so cache it with the retrieval date |
| regional total, today | Elia open data `ods031` | API | Monitored onshore wind in Wallonia on 7 Oct 2026: 1 515.8 MW DSO-connected + 156.2 MW Elia-connected = **1 672 MW** |
| regional total, end 2025 | EDORA press release, 20 Jan 2026 (data collected with Energie Commune) | press | 1 661 MW on 625 machines; 36 machines and 133 MW added in 2025 |
| mast positions | OpenStreetMap | Overpass | 648 machines in BE-WAL. Rated power is tagged on ≈ 330: 557 carry the key, but 225 of them only say `yes`. 162 carry the model, 97 a `start_date` |
| grid, ≥ 30 kV | Elia hosting-capacity map, "Export all map data" (`griddata.elia.be/eliabecontrols.prod/interface/HostingCapacityMap/v2/download`) | xlsx, 116 kB, no login, outside the Cloudflare check that guards www.elia.be | Per substation, with lon/lat: the additional MW for load, production, PV, wind and battery, at 0, 5, 10 and 20 % curtailment, for 2027 and 2031. 152 Walloon substations in 2027. Wind at 0 % is zero at 30 of them and ≥ 20 MW at 26. Capacities hold **one location at a time and are not additive**; they are capped by voltage level and cover projects < 300 MW |
| grid, HV/MV transformers (where DSO-connected wind lands) | Elia, *Capacités d'injection indicatives en Région wallonne* (AGW of 10 Nov 2016, art. 29; "cahier vert CWaPE") | xlsx on www.elia.be, **behind a Cloudflare check: download by hand**. The March 2024 version, recovered from the Wayback Machine, gives the format | Per planning point (174): Gperm, Gperm,rest, Gflex and Gflex,rest, yearly for 2021–2031. No coordinates: 117 points match a substation code of the export above, and the other 57 (55 substations) have to be located on OSM substations |
| grid, congestion zones | Elia `ods183` | API | 10 operational zones for all of Belgium: too coarse, not used |
| grid, MV feeders | ORES, RESA | — | no public machine-readable capacity: **not available** |
| other layers | Géoportail `ENERGIE/THERM_INS_PROD_ELC_RENOUV_2021` (MW and % by technology per commune, 2021); `FAUNE_FLORE/COMP_EOL` (734 compensation parcels, each with its park's name) | REST | a 2021 cross-check, and park names |
| project pipeline (permits, appeals) | APERe (*Facilitateur éolien*) | not open | not available |

**First cross-check: OSM masts against SPW MW, commune by commune.** The two
correlate at r = 0.86, and 92 communes appear in both. The mismatches cut both
ways:

- **15 communes have SPW MW but no OSM mast** (11 MW in total). These are small
  machines, or a park the SPW books to the neighbouring commune.
- **22 communes have OSM masts but no SPW MW** (67 machines). These are parks
  built after the January 2025 freeze, or the same boundary effect.

The sources complement each other. OSM says where the masts stand. The SPW says
what was declared, in which commune, and when.

### How the sources are combined

**Installed capacity**

- Masts come from OSM, refreshed with their tags. Each is attributed to the
  commune it stands in.
- Rated power per mast is taken from the first source available:
  1. the OSM tag;
  2. a model-to-rating table;
  3. the park's MW from the SPW series, when the commune holds a single park;
  4. the fleet median, flagged.
- Commissioning year comes from the SPW monthly series (the month a commune's MW
  steps up), then from OSM `start_date`.
- The regional sum must fall within ±3 % of Elia's monitored capacity and of
  EDORA's figure.
- Each commune gets a flag: agree, SPW only, OSM only, or implausible MW per
  mast. The ≈ 40 flagged communes are reviewed by hand.
- A park that straddles two communes is split by mast. The SPW attribution stays
  alongside as a check column.

**Open horizon of each village**

- For each of the 2 261 settlements: the largest arc of horizon free of masts
  within 4 km, against the Cadre's 130°. Attributed to the commune it lies in,
  with the masts of neighbouring communes counted.
- `validate_fleet` already computes this arc for every settlement (880 have a
  mast within 4 km; 6 are below 130° today) but keeps only percentiles. The
  per-settlement values just need to be written out, then recomputed on the
  reconciled fleet.
- Settlements are habitat-zone centroids without names: label them with the
  nearest OSM `place`.

**Grid capacity**

- **There are two connection routes.**
  - A typical farm (< 25 MW) connects to the DSO's MV network, behind an Elia
    HV/MV transformer. The relevant capacity is that transformer's Gperm,rest,
    plus Gflex,rest.
  - A larger farm connects to Elia at ≥ 30 kV. The export's wind capacity at 0 %
    and 5 % curtailment applies.
- **Communes are linked to transformers by Voronoi cells**, which stand in for
  the MV supply areas. For each commune the table lists:
  - the transformers whose cell covers it;
  - their capacities;
  - how many communes share each transformer.
- **Commune values are never summed.** The regional ranking alone uses an
  additive "fair share": each substation's capacity split in proportion to the
  potential lying in its cell. It is labelled as a convention.

**Potential**

- **Area.** Eligible km² per commune, and the km² each rule family removes (the
  funnel), for every land variant, from the dashboard's 100 m attribution maps.
- **Machines and MW** per commune, for all 36 states, by attributing the placed
  masts.
- **Remaining potential, with the standing fleet in place.** This is the number
  communes will ask for, and it is not gross minus installed: about one standing
  machine in five sits where the zoning would not admit it today. The placement
  already accepts `preplaced` machines, with their spacing, park membership and
  horizon arcs (`placement_lib.grow_parks`). Seeding it with the reconciled
  fleet gives the capacity each commune can still host.
- **The residual allowance is not geographic** (× 0.765, range 0.56–1).
  Communes get the gross figure and the range. No central figure is presented as
  local.
- **Small communes are lumpy**: one park makes the difference between 0 and
  20 MW. Two companion values smooth this:
  - an area-based value: eligible km² × the regional effective density of
    19.6 MW/km²;
  - a min–max over 10 placement orders.

### Roadmap

Difficulty: L low, M medium, H high. Chance: the probability of delivering the
item as described. Effort is in working days, agent work plus review.

| # | task | difficulty | chance | effort | compute |
|---|---|---|---|---|---|
| 0 | Rebuild the `T185_NREL4` exclusion layers and settlements, which the interrupted run of 23 Sep deleted, and check the headline is unchanged | L | 95 % | 0.5 d | local, ≈ 15 min |
| 1 | Communes (2025), Statbel population 2026 and areas; a commune raster on the dashboard's 100 m grid | L | 99 % | 0.5 d | local, minutes |
| 2 | Ingest the SPW map CSVs with their provenance: wind and PV history 2015–2026, modelled production, inhabitants. Map the 262 communes onto the 261 | L | 95 % | 0.5 d | local |
| 3 | Per-commune funnel (km² per family) and potential (machines, MW, GWh) for the 36 states. Keep the per-step positions that `infographic_data` currently discards | L–M | 95 % | 1 d | local, minutes |
| 4 | Installed fleet: refresh OSM with tags, build the rating table, reconcile with SPW, Elia and EDORA, flag, then review the flagged communes by hand. Write out the free horizon of each settlement against the reconciled fleet | M | 85 % | 1.5 d + 2–3 h review | local |
| 5 | Remaining potential with the fleet preplaced, for the 36 states, plus the 10-order stability check | M | 85 % | 1 d | local, ≈ 1 h |
| 6 | Grid. Inputs: the hosting-capacity export and the current cahier vert (downloaded by hand). Locate the 174 planning points (117 automatically, 57 by OSM name and a check). Build the Voronoi cells, the per-commune table and a flag for communes where the grid binds before the land | M | 80 % | 1.5 d | local |
| 7 | Statistics and regional ranking: MW/km² and kW per inhabitant (installed, potential, remaining), share of land eligible, production per inhabitant | L | 95 % | 0.5 d | local |
| 8 | Commune dashboard, in French. A commune selector and the URL `#commune=<NIS>`. The regional steps and "Et si… ?" cropped to the commune at 100 m, with the fleet and the substations. Panels for installed history, statistics, grid and PV context. A regional choropleth and a sortable table | M–H | 80 % | 3 d | local |
| 9 | Exports: a two-page PDF and a PNG per commune (Playwright, 261 × ≈ 5 s), then publication | M | 85 % | 0.5–1 d | local, ≈ 30 min |
| 10 | Checks (commune sums equal the regional figures for every state; flags) and a report annex | L | 95 % | 1 d | local |

**Total: ≈ 11–12 working days.** The order is:

1. tasks 0–2;
2. tasks 3 and 4;
3. tasks 5 and 6;
4. task 7;
5. tasks 8 and 9;
6. task 10.

Tasks 3 to 7 produce the tables on their own; the dashboard (8–9) only reads
them.

**NIC6 is not needed.** According to the 23 Sep logs, the whole regional
pipeline runs here in under an hour:

| step | runtime |
|---|---|
| exclusion layers | ≈ 13 min per turbine class |
| placement | ≈ 10 s |
| sensitivity | ≈ 30 s |
| dashboard data | ≈ 70 s |

The commune work adds the attribution (seconds), 36 preplaced placements
(minutes), 360 placements for the stability check (≈ 1 h) and the exports
(≈ 30 min). All of it fits on this machine's 24 cores and 124 GB. NIC6 would not
help:

- its compute nodes have no internet access, which every retrieval step needs;
- its memory is capped at 1.9 GB per core.

It would only pay off for a Monte Carlo over thousands of placements, which is
not planned.

**Out of the roadmap, and why**

- **The remaining capacity of the MV feeders** (ORES, RESA, AIEG, AIESH, REW).
  It is not published. The commune figure can only be the Elia transformer's,
  which is an upper bound.
- **A connectable MW per commune.** Elia's capacities hold "one location at a
  time" and are shared by every commune behind a substation. The result is an
  indication shown with its sharing, never a quota.
- **Projects in the pipeline (permits, appeals).** There is no open data; APERe
  holds the list. It can be added if SPW Énergie or APERe provide it.
- **Metered production per commune.** It does not exist publicly. The SPW map's
  figures are modelled and are shown as such.
- **Commune-specific orthophoto vignettes.** They would be technically easy, but
  two things rule them out:
  - the SPW orthophotos fall under the viewing-service conditions, not CC BY;
  - rings drawn on a named village go against the infographic plan (§8.3).

  The regional vignettes are reused instead.

**Deliverables**

1. `communes_onwind.csv` and a GeoPackage, one row per commune (261 rows):
   - areas, population, eligible km² per family;
   - potential per state (machines, MW, GWh, gross and range);
   - remaining potential with the fleet in place;
   - installed capacity (SPW January 2025, OSM 2026, reconciled);
   - statistics;
   - grid (substations, Gperm,rest, wind at 0 and 5 %, sharing);
   - flags.
2. `fleet_reconciled.gpkg`: the masts, their rating, park, commune and
   commissioning year, and the source of each value; and a settlement layer
   with each village's free horizon.
3. `substations_capacity.gpkg`: the 174 planning points and the 152 HV
   substations, with their capacities and their Voronoi cells.
4. The commune dashboard in French, published like the regional one, with the
   regional map and ranking.
5. 261 commune sheets (PDF and PNG).
6. A report annex on method, cross-checks and limits, and a one-page note
   listing the data still missing, for SPW Énergie, Elia and the DSOs.

**Decisions needed**

1. Download the current cahier vert from elia.be in a browser, or ask Elia or
   the CWaPE for it.
2. Choose the headline per commune: the remaining potential (recommended) or the
   gross one.
3. Choose the audience. Commune figures are politically sensitive: review them
   internally first, then publish.
