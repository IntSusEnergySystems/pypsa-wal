# EV charging and EV shares — how the soft-link works, and what is still open

Land-transport electricity in PyPSA-Wal: the three charging profiles, where their
weights come from, how they stay consistent with Elia and TIMES, and the one
transfer that is still exogenous.

**Status:** the three-profile split is live. The TIMES **fleet** export exists in
`TIMES_PyPSA` and is deliberately **not wired** — see [E1–E3](#5-decision-register).

| Section | |
|---|---|
| [§1](#1-what-the-model-does) | the mechanism, end to end |
| [§2](#2-the-energy-vs-fleet-share-gap) | the transfer that is still wrong, and by how much |
| [§3](#3-the-energy-identity) | why total EV grid draw equals the TIMES figure |
| [§4](#4-weighting-strategy) | **the three levels of weights, and the rule for each** |
| [§5](#5-decision-register) | E1–E14, decided and open |
| [§6](#6-remaining-work) | what is left to build |
| [§7](#7-reference-data) | the Elia tables, and facts worth keeping |

---

## 1. What the model does

### 1.1 Two loads, three profiles

| Load carrier | Bus | Shape |
|---|---|---|
| `land transport EV` | `<node> EV battery` | driving profile × `bev_dsm_availability` × `bev_charge_efficiency` — dispatchable through the `BEV charger` link and the DSM store |
| `land transport EV inflexible` | `<node>` (→ `<node> low voltage` with the distribution grid) | the remainder, on a **weighted blend** of Elia's charging curves |

`sector.bev_natural_charging_split: false` switches the whole mechanism off and
puts all EV demand on the EV-battery bus (PyPSA-Eur default).

`data/walloon/elia_natural_charging_daily_profile_utc0.csv` holds six 24 h curves
per data vintage (2026, 2036):

| column | Elia mode | what it is |
|---|---|---|
| `natural` | `V0` | charge as soon as plugged in |
| `sunny_PV`, `sunny_noPV`, `cloudy_PV`, `cloudy_noPV` | `V1H`/`V2H` home | shifted by regional tariff and PV self-consumption |
| `work` | `V1H` work | workplace smart charging |

`sector.local_bev_dsm` weights them per horizon; the weights must sum to 1 and
`build_natural_charging_shape` asserts it. The vintage closest to the planning
horizon is used. Output:
`resources/<run>/natural_charging_shape_s_{clusters}_{planning_horizons}.csv`.

> **Three profiles, two loads.** The three live in the data and the weights, but
> the network gets one flexible load and one inflexible load carrying the blended
> natural+local shape. Physically equivalent — both are exogenous shapes — so the
> only thing lost is the ability to *report* natural and local separately.
> Splitting them is a reporting change, not a modelling one
> ([§6](#6-remaining-work)).

### 1.2 Horizon-varying parameters

`bev_dsm_availability` and `bev_avail_{max,mean,min}` are dicts keyed by planning
horizon, all from Elia AdeqFlex 2025 "Current commitments":

| | 2025 | 2030 | 2040 | 2050 | source |
|---|---:|---:|---:|---:|---|
| `bev_dsm_availability` | 0.01 | 0.07 | 0.18 | 0.18 | `V1M+V2M`; 2040/2050 hold Elia's last year ([§4.3](#43-the-rule-pick-a-scenario-hold-the-year-never-extrapolate)) |
| `bev_avail_max` | 0.4 | 0.4 | 0.48 | 0.48 | availability table, 2026 vintage ≤ 2030, 2036 vintage ≥ 2035 |
| `bev_avail_mean` | 0.32 | 0.32 | 0.35 | 0.35 | (measured: 0.316 / 0.351) |
| `bev_avail_min` | 0.2 | 0.2 | 0.18 | 0.18 | (measured: 0.202 / 0.180) |

**Every horizon `config.default.yaml` lists must be listed here too.**
`update_config` merges dicts key by key, so an unlisted horizon silently inherits
the PyPSA-Eur default — `bev_dsm_availability: 0.5`, `bev_avail_min: 0.0` — and
`_helpers.get` returns that key without warning. `test_ev_charging.py` fails on
any leak.

`local_bev_dsm` is resolved differently from the scalars: `_helpers.get`
interpolates between neighbouring keys, which cannot work on dicts, so
`build_natural_charging_shape` holds the **nearest earlier horizon** and logs a
warning instead. It also checks that every named curve is a column of the profile
CSV. A horizon earlier than every entry raises.

### 1.3 The profile is in UTC

`elia_natural_charging_daily_profile_utc0.csv` is the Elia data shifted **−2 h**
from Belgian local time, because snapshots are UTC
(`get_snapshots(..., tz="UTC")`). `_local.csv` keeps the original as received —
`natural` column only — and the workflow does not read it.

---

## 2. The energy-vs-fleet share gap

**This is the one part of the EV transfer that is still wrong.**

At BEWAL, `electric_share` is the TIMES **energy** ratio
`electricity road / total road`. That is the right number for the load and the
wrong number for `p_nom` and `e_nom`, which scale on
`number_cars × electric_share` — a fleet quantity. A BEV turns ~3.5× more of its
energy into km than an ICE, so the two diverge:

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| `electricity road / total road` — used at BEWAL | 0.034 | 0.142 | 0.559 | 0.830 |
| Elia BE car BEV stock share — in the config, **ignored at BEWAL** | 0.15 | 0.35 | 0.81 | 1.00 |
| **TIMES car BEV stock share** (`VAR_Cap`) | **0.152** | **0.529** | **1.000** | **1.000** |
| TIMES car BEV activity share (`VAR_Act`) | 0.136 | 0.500 | 1.000 | 1.000 |

`add_land_transport`'s `times_demand` branch overrides the config for the Walloon
node, so `land_transport_electric_share` applies only to BEVLG, BEBRU, DE, FR, GB,
NL and LU. The config therefore reads as if a fleet share were in use while the
node the study is about uses something else.

Correcting the share alone moves BEWAL's 2030 BEV charger from **213 MW to
793 MW**. Elia and TIMES agree closely on the fleet (0.15 vs 0.152 in 2025), which
is the argument for taking BEWAL's share from TIMES and leaving Elia's for the
other nodes.

**`number cars` is also frozen** at 1 946 792 for every horizon; TIMES has
1 716 k → 1 866 k → 2 118 k, a 21 % rise.

### 2.1 What `TIMES_PyPSA` exports

`times_pypsa/transport_softlink.py` + `data/transport_softlink_groups.csv`, as
`road_transport_{year}.csv` and `..._shares.csv`, from `export_all_horizons` and
every `export-coupling` bundle (opt-in in `export_horizon`). 15 tests.

Three things that had to be right:

* **The selector is the unit pair `000VEH`/`BVKM`**, not the
  `Aggregation Level 2` label — `Cars` and `Road Freight` each label both the
  vehicle processes and the `PJA`/`PJ` fuel technologies feeding them.
* **The vehicle class comes from the process description**, never the code prefix:
  fourteen `TCARGASEX1x` codes are heavy-duty trucks and vans.
* **`VAR_Cap` only, never `VAR_Cap + VAR_Ncap`** — the same double count the
  heating soft-link had to undo.

PHEV and HEV map to `ice`: PyPSA-Wal has no plug-in-hybrid component, and a PHEV
split across the EV-battery and oil buses would need its own utility factor. Elia
instead counts a PHEV as half a BEV — the two conventions must not be mixed.

TIMES 2030 stock, thousand vehicles:

| class | BEV | PHEV | HEV | ICE | BEV stock share |
|---|---:|---:|---:|---:|---:|
| cars | 987.9 | 5.8 | 15.0 | 857.2 | **52.9 %** |
| light commercial vehicles | 0.1 | — | 158.7 | 150.0 | 0.0 % |
| heavy duty trucks | 0.0 | — | 5.1 | 33.3 | 0.0 % |
| buses | — | — | 0.4 | 6.9 | 0.0 % |
| two and three wheelers | 198.3 | — | — | 215.5 | 47.9 % |

> The two/three-wheeler share is dominated by **electric bicycles**, not mopeds.

---

## 3. The energy identity

**Total Walloon EV grid draw equals the TIMES `electricity road` figure**, and a
test pins it.

The two load branches sit on opposite sides of the charger: the flexible one is on
the EV-battery bus behind the `BEV charger` link (which applies
`bev_charge_efficiency`), the inflexible one is on the AC bus. They have to be put
on a common footing, and the direction matters.

**TIMES already models the charger loss.** `TCHARGHOMN01` and `TCHARGWRKN01` both
run at `VAR_FOut/VAR_FIn = 0.95`, and `extraction_rules.csv` measures
`electricity road` at `fuel_input`/`VAR_FIN` — **upstream** of it. Their `VAR_FIn`
is ~95 % of the exported figure. So `add_EVs` scales the **flexible** load *down*
by `bev_charge_efficiency`; grossing the inflexible one *up* instead would apply
PyPSA's 0.9 on top of TIMES's 0.95 and count the loss twice.

Measured on the 2030 shape: grid draw **3.393 TWh** against TIMES's **3.393**.
The error scales with `bev_dsm_availability`, so the number identifies the code:

| grid draw vs TIMES | which code |
|---|---|
| **±0.1 %** | correct |
| **+5.6 %** | only the flexible branch grossed up, at `dsm = 0.5` |
| **+11 %** | the inflexible branch grossed up (whole load, any `dsm`) |

The runnable check is in [`instructions.md`](../instructions.md); the guard is
`test_ev_charging.py::test_split_draws_exactly_the_transferred_demand`.

---

## 4. Weighting strategy

Six profile columns, two config keys, one TIMES model. The weights are easy to
make plausible and hard to make consistent.

### 4.1 Three levels, and who owns each

| level | what it weights | source | rule |
|---|---|---|---|
| **1 — flexibility mode** | natural / local / market | `ev_operation_mode_shares.csv` | all three from **one (scenario, year) cell** |
| **2 — inside natural** | home / work / public | `ev_v0_location_shares.csv` | Elia's `natural` column *is* this weighted sum |
| **3 — inside local** | work vs home; sky × PV | **Elia publishes nothing** | needs a model-side input — [§4.4](#44-level-3-where-elia-gives-nothing) |

Level 1 is delicate because pypsa-wal splits one Elia row across two config keys
with **different denominators**:

* `bev_dsm_availability` = the **market** share of the whole fleet;
* `local_bev_dsm` = natural vs local **renormalised over those two only**, because
  `split_transport_demand` applies it to what is left after the market slice.

So `natural_abs = local_bev_dsm.natural × (1 − bev_dsm_availability)` is what must
equal Elia's `V0` — not the config number.

### 4.2 Never hand-edit one of the two keys

```bash
python scripts/walloon_scripts/build_ev_charging_weights.py
python scripts/walloon_scripts/build_ev_charging_weights.py --scenario "Current commitments - High Flex"
```

It derives both blocks from one Elia cell and prints an audit that reproduces
Elia's absolute shares exactly. `test_ev_charging.py` fails if the two keys drift
onto different Elia scenarios.

Base case, **Current commitments**:

| horizon | Elia year | `bev_dsm_availability` | `local_bev_dsm.natural` | each of 4 home | `work` |
|---|---|---:|---:|---:|---:|
| 2025 | 2025 | 0.01 | 0.697 | 0.0498 | 0.104 |
| 2030 | 2030 | 0.07 | 0.505 | 0.0909 | 0.131 |
| 2040 | 2036 *(held)* | 0.18 | 0.329 | 0.1381 | 0.118 |
| 2050 | 2036 *(held)* | 0.18 | 0.329 | 0.1381 | 0.118 |

Flexibility-rich sensitivity, **Current commitments – High Flex**: market 0.030 /
0.131 / 0.280 / 0.280 with natural 0.691 / 0.465 / 0.236 / 0.236.

### 4.3 The rule: pick a scenario, hold the year, never extrapolate

1. **Name the Elia scenario** and read all three modes from it. Extra flexibility
   comes from the **scenario axis**, which Elia publishes — not from inventing a
   year.
2. **Map horizons onto Elia years, clamping to its range** (2023–2036). 2040 and
   2050 both take 2036. A behavioural adoption curve extended 14 years past its
   source is worse than its last observed point, and clamping is auditable.
3. **Renormalise natural/local over themselves** before writing `local_bev_dsm`.

> **The failure this prevents.** Pairing the market share of one Elia case with
> the natural/local split of another describes no real scenario. A 0.28 market
> share is Elia's High Flex 2036, whose `V0` is 0.17 — pairing it with a `natural`
> of 0.40 puts the absolute natural share at 0.288, **+69 %** against the case the
> market share came from, and local **−21 %**.

### 4.4 Level 3, where Elia gives nothing

**Work vs home.** Elia publishes no location split for `V1H`. The only
Elia-grounded proxy is the **`V0` split restricted to home + work**, since Elia
explicitly assumes no flexibility from public charging: 0.343 (2025) → 0.265
(2030) → 0.176 (2036). It **declines**, because Elia has home charging rising
0.53 → 0.70 as private ownership displaces company cars. The generator uses it.
The counter-argument is real — workplace *smart* charging is tariff-driven, not
plug-in-driven, so it need not track workplace *natural* charging — but a
departure has to be argued, not assumed.

**With PV vs without PV.** This is where TIMES should drive the weight and does
not yet. The right quantity is the share of *EV-owning dwellings* with rooftop PV.

* **Recommended:** export residential PV capacity per horizon from TIMES
  (`VAR_Cap` on the PV processes, the same table as the vehicle fleet), divide by
  dwellings, use that as the with-PV weight. Same export mechanism as
  `road_transport_*.csv`, and it keeps the split on the TIMES trajectory.
* **Do not** use PyPSA's endogenous `solar-rooftop` capacity: it is a model
  output, so the weight would depend on the solution it feeds.
* **Current:** 50/50 — EV owners are richer than average and more likely to own
  PV, so 50 % is a lower bound on the with-PV share.

**Sunny vs cloudy.** A fixed weight is the wrong instrument: PyPSA already knows
which days are sunny. The correct treatment selects the curve **per day** from the
model's own rooftop-PV availability (above/below the median daily capacity factor
at that node) instead of blending two shapes that never occur together.
Concretely: pass the solar profile into `build_transport_demand`, compute a daily
sunny/cloudy mask, and build the local shape on the snapshot index rather than by
tiling a weekly profile. That turns `build_natural_charging_shape` from
day-invariant to day-varying, which is why it is separate work. **Current:**
50/50.

### 4.5 Where TIMES constrains this, and where it does not

| quantity | TIMES has it? | consequence |
|---|---|---|
| natural / local / market split | **no** — one `EV charger` process, no operation modes | must come from Elia; TIMES cannot arbitrate |
| BEV fleet and its growth | **yes** — `road_transport_*.csv` | drives what the shares are applied *to* ([§2](#2-the-energy-vs-fleet-share-gap)) |
| road electricity demand | **yes** — `electricity road` | the total the profiles redistribute ([§3](#3-the-energy-identity)) |
| residential PV penetration | **yes** — `VAR_Cap` on the PV processes | should drive the with-PV weight ([§4.4](#44-level-3-where-elia-gives-nothing)) |
| daily weather | **no** — only electricity is sub-annual | PyPSA must supply the sky split |

**TIMES sets the magnitudes, Elia sets the shapes and the behavioural split, PyPSA
supplies the weather.** Every weight is placed according to which of the three
owns it. The sky and PV splits are the only places where that is not yet true.

---

## 5. Decision register

### Decided

| # | Question | Decision |
|---|---|---|
| **E4** | Where do the three-way mode shares come from? | **Elia.** TIMES has one `EV charger` process and no operation modes, so it cannot arbitrate the split at all. |
| **E5** | Which Elia scenario? | **"Current commitments"** as the base; **"High Flex"** as the flexibility-rich sensitivity, regenerated with one flag. Never a hand-tuned middle. |
| **E6** | How is the V1H with-PV / without-PV pair combined? | **50/50 for now**, documented as a lower bound on the with-PV share. The TIMES residential-PV route is the intended replacement ([§4.4](#44-level-3-where-elia-gives-nothing)) and stays on the work list. |
| **E7** | Is the local profile a fixed shape or a constrained freedom? | **Fixed exogenous shape.** It is what the data supports (a published curve), needs no new components, and is directly comparable with the natural profile. A second flexible bucket with a tighter window than V1M would invent a window Elia does not give. |
| **E9** | Does the natural profile stay pinned to one vintage? | **No** — the vintage closest to the planning horizon is used. |
| **E11** | V2G | **`false`.** Elia gives V2H+V2M at 0.00–0.02 of the fleet to 2036, while V2G is sized on `bev_dsm_availability` (the V1M+V2M total) — far too generous if switched on. |
| **E12** | The charger loss | **Scale the flexible load down** by `bev_charge_efficiency`, not the inflexible one up. Rejected: `bev_charge_efficiency: 1.0` (hides the charger from the LP) and re-metering the TIMES export at `VAR_FOut` (cleanest conceptually, but changes every downstream number). [§3](#3-the-energy-identity) |
| **E13** | The `work` weight inside the local profile | **Use the Elia-grounded `V0` home+work proxy**, which declines 0.343 → 0.176. A hand-set weight rising the other way was the only unsourced number in the block. |

### Open

| # | Question | Recommendation | Blocks |
|---|---|---|---|
| **E1** | Which TIMES share replaces the energy ratio for **fleet** quantities? | **`stock_share` for `p_nom`/`e_nom`, energy ratio for the load.** They answer different questions and both are exported. | the flexible EV fleet is understated 3.7× in 2030 |
| **E2** | Which vehicle classes feed the Walloon EV components? | **cars + LDV**, matching Elia's boundary — needs E3 for the van count. | E1 |
| **E3** | Does TIMES also replace `number cars`? | **Yes.** Same export, Walloon rather than population-scaled, removes a 21 % drift. Changes every horizon. | E1 |
| **E8** | Are the local curves still a **winter** illustration? True of the published workbook; unknown for the values in use ([§7](#7-reference-data)). | **Ask Elia**, then apply year-round with the caveat recorded. | largest remaining fidelity loss |
| **E10** | Replace the synthesised BEV availability *shape* with Elia's hourly table? | **Read the table** and interpolate 2026 → 2036. The min/mean/max already come from Elia; only the shape is still German traffic counts (`pkw.csv`). | flexible-charging realism |
| **E14** | Provenance of the local curves in use | **Record who, what document, what date next to the CSV.** | the only unsourced input in the EV chain |

E1–E3 are held deliberately: the fleet wiring waits on the availability-profile
work of E10, so that both land together.

---

## 6. Remaining work

**Fleet share (E1–E3)**

1. **New Snakemake artefact.** `rule build_wallon_demands` already calls
   `export_horizon`; add
   `road_transport=resources("road_transport_{planning_horizons}.csv")` as an
   output and pass `road_transport_path`. The pre-exported-bundle branch of
   `build_wallon_demands.py` needs the matching `shutil.copy2` and a clear error
   when an older bundle lacks the file — mirror `heating_targets`. **And add
   `transport_softlink_groups.csv` to `times_mapping_files()` in
   `rules/build_sector.smk`** at the same time, or editing the group definition
   leaves stale `road_transport_*.csv` on disk and Snakemake reuses it silently.
   It is deliberately absent from that list today, because no rule reads it yet.
2. **Split `electric_share` in two** in `add_land_transport` / `add_EVs`:
   `electric_share_energy` for the load, `electric_share_fleet` for the
   `p_nom`/`e_nom` scaling. A rename plus one new read — the arithmetic does not
   change. Also make the `times_demand` branch stop silently ignoring
   `land_transport_electric_share` at BEWAL, or say in the config that it does.
3. **Optionally replace `number cars`** for the Walloon node, the way
   `base_year_capacities` replaces one row of `existing_heating_distribution`.
4. **Guards.** The fleet share must be ≥ the energy share in every horizon (it
   must be, by efficiency); the three engine shares must sum to 1.

**Profiles (E6, E8, E10)**

5. **Read Elia's hourly availability table** into `bev_availability_profile`
   instead of scaling `pkw.csv`, interpolating 2026 → 2036.
6. **Export residential PV from TIMES** and use it as the with-PV weight.
7. **Select sunny/cloudy per day** from the model's own solar availability
   ([§4.4](#44-level-3-where-elia-gives-nothing)).

**Reporting (optional)**

8. **Split the blended inflexible load into `natural` and `local` carriers** so
   the three profiles are visible in the summaries and the explorer. Needs a new
   carrier plus colour and nice-name entries in `config.default.yaml`. Physically
   a no-op.
9. **Cap the flexible share** at `1 − public_share` (0.192 in 2025 → 0.150 in
   2036): Elia assumes no flexibility from public charging, so
   `bev_dsm_availability` cannot legitimately exceed it. Not binding at current
   values, so this is a guard, not a fix.

---

## 7. Reference data

**The curves in use are not the published workbook.**
`elia_natural_charging_daily_profile_utc0.csv` carries four genuinely distinct
`sunny/cloudy × PV` home curves (hour 0: `sunny_PV` 0.029 vs `cloudy_PV` 0.059).
In the published `AdeqFlex2025_AssumptionsWorkbook.xlsx` the same block is crossed
tariff × sky × PV but contains only **two** distinct shapes — tariff and sky are
inert there. So the values in use came from a later Elia source, and nothing
records which (**E14**). The `natural` column *does* match the published workbook
exactly, shifted −2 h.

The extraction of the **published** workbook, sheet `3.3. DSR end-user`, is the
audit baseline — not the input. Reproduce with
[`scripts/walloon_scripts/extract_elia_adeqflex_ev.py`](../scripts/walloon_scripts/extract_elia_adeqflex_ev.py)
into [`data/walloon/elia_adeqflex2025/`](../data/walloon/elia_adeqflex2025). The
workbook itself is **not** in the repository.

| file | content |
|---|---|
| `ev_operation_mode_shares.csv` | V0 / V1H / V2H / V1M / V2M share and absolute kveh of the EV fleet, 2023–2036, 5 Elia scenarios |
| `ev_v0_location_shares.csv` | home / work / public split **inside** V0, 2025–2036 |
| `ev_daily_profiles.csv` | 24 h profiles: V0 (home, work, public, aggregate-2026, aggregate-2036) and V1H/V2H (8 home variants + work) |
| `ev_availability.csv` | plugged-in share available to V1M/V2M, 24 h, 2026 and 2036 |

Facts worth keeping:

* **The V0 aggregate is reconstructible** — it is the location-weighted sum of
  home/work/public, matching to ≤ 0.0006 per hour. Any intermediate year can be
  built from the shares rather than snapped to a vintage.
* **V1M/V2M profiles are Elia model *outputs*, not inputs.** Flexible charging
  must stay endogenous, which is what PyPSA does. What Elia supplies there is the
  **availability** (E10).
* **"No flexibility is assumed from public charging"** — the availability profile
  covers home and work only (work item 9).
* **Elia counts a PHEV as half a BEV** and covers cars + LDVs together; TIMES
  counts vehicles per class. The denominators cannot be mixed without a
  conversion.
* The workbook rounds every profile to 3 decimals, so a daily profile sums to
  0.995–1.003. Normalise before use — `build_natural_charging_shape` does.

### A caution about `AllProcesses.csv`

`TIMES_PyPSA/data/AllProcesses.csv` has 18 duplicated `Name` entries and is
missing 93 codes that `mapping_processes.csv` carries, 20+ of which do have data
in the reference `.vd` — so "absent from `AllProcesses`" is **not** evidence that a
mapping row is spurious. It was, however, enough to adjudicate the seven
duplicated process codes in `mapping_processes.csv` (now fixed and guarded by
`test_no_duplicate_process_codes`), because each duplicate pair had exactly one row
whose units matched. Worth knowing before treating it as an authority again.

---

## 8. Related

* [`heat-softlink.md`](heat-softlink.md) — the same soft-link pattern for heating,
  including the base-year-stock substitution that E3 imitates.
* [`discount-rates.md`](discount-rates.md) §6.2 — TIMES prices all road transport
  at 7.5 %, the other half of the EV-vs-heat-pump comparison.
* `TIMES_PyPSA/times_pypsa/transport_softlink.py` — the fleet export.
