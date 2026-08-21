# EV shares and charging profiles — TIMES harmonisation and the three-profile split

**Status:** the three-profile split and the horizon-varying Elia parameters are
**implemented on `origin/feat/bev-myopic`** (30 commits, 2026-08-17 → 2026-08-21,
0 behind master). The TIMES **fleet** export is implemented in `TIMES_PyPSA` and
is **not wired**. Two defects found in the branch need a decision before it is
merged.

**Date:** 2026-08-21, revised the same day after reviewing `feat/bev-myopic`.

| | |
|---|---|
| **Done on the branch** | three-profile split (natural + 4 local + work), horizon-varying `bev_dsm_availability` and `bev_avail_*`, per-horizon natural-charging vintage, UTC timezone fix, `config.walloon.yaml`/`config.walloon.yaml` aligned, config schema + validation |
| **Still open** | the energy-vs-fleet share defect ([§2](#2-the-energy-vs-fleet-share-defect-still-open)); the double-counted charger loss the branch introduces ([§3](#3-two-defects-in-the-branch)); the Elia hourly availability table ([§5](#5-decisions-still-needed) E10) |

| Section | |
|---|---|
| [§1](#1-what-the-branch-changed) | what `feat/bev-myopic` does, and how it compares to the Elia data |
| [§2](#2-the-energy-vs-fleet-share-defect-still-open) | the one thing the branch does not fix |
| [§3](#3-two-defects-in-the-branch) | the charger-loss double count and the hard-indexed weights |
| [§4](#4-merging-with-the-2026-08-21-doc--discount-rate-work) | the single merge conflict |
| [§5](#5-decisions-still-needed) | what is left to decide |
| [§6](#6-changes-still-needed-in-pypsa-wal) | the remaining work list |

---

## 1. What the branch changed

### 1.1 Three profiles, delivered as a weighted blend

`build_elia_transport_shape` → `build_natural_charging_shape`. The new
`data/walloon/elia_natural_charging_daily_profile_utc0.csv` carries **six**
24-hour columns per vintage (2026, 2036) instead of one:

| column | Elia mode | notes |
|---|---|---|
| `natural` | V0 aggregate | **identical to the published workbook**, shifted −2 h (see §1.3) |
| `sunny_PV`, `sunny_noPV`, `cloudy_PV`, `cloudy_noPV` | V1H home, local | **four distinct shapes** — richer than the published workbook (§1.2) |
| `work` | V1H work | matches the workbook's Work column |

`sector.local_bev_dsm` gives the weights per horizon, asserted to sum to 1:

| horizon | `natural` | 4 × home local | `work` | local total |
|---|---:|---:|---:|---:|
| 2025 | 0.70 | 4 × 0.05 | 0.10 | 0.30 |
| 2030 (and 2035) | 0.50 | 4 × 0.05 | 0.30 | 0.50 |
| 2040 (and 2045, 2050) | 0.40 | 4 × 0.075 | 0.30 | 0.60 |

**These reproduce Elia's operation-mode shares, renormalised to exclude the
market modes** — which is the right construction, because V1M/V2M are handled
separately by `bev_dsm_availability`:

| | Elia V0 | Elia V1H+V2H | V0 renormalised | branch `natural` |
|---|---:|---:|---:|---:|
| 2025 | 0.69 | 0.30 | 0.70 | **0.70** ✓ |
| 2030 | 0.47 | 0.46 | 0.505 | **0.50** ✓ |
| 2036 | 0.27 | 0.55 | 0.329 | 0.40 (2040+) — a judgement call, not Elia |

The four home variants are weighted **equally**, i.e. 50/50 with-PV/without-PV
and 50/50 sunny/cloudy. That is the documented fallback for decision E6.

`bev_natural_charging_split: false` restores the PyPSA-Eur default (all EV demand
dispatchable on the EV-battery bus) — a clean escape hatch.

> **One structural note.** The three profiles live in the *data* and the
> *weights*, but the network still gets **two** loads: one flexible, and one
> inflexible carrying the blended natural+local shape. Physically that is
> equivalent — both are exogenous shapes — so nothing is lost except the ability
> to *report* natural and local separately. Splitting them into two loads later
> is a reporting change, not a modelling one.

### 1.2 The branch's local profiles are newer than the published workbook

In `AdeqFlex2025_AssumptionsWorkbook.xlsx` the V1H home block is crossed tariff ×
sky × PV — eight columns that contain only **two** distinct shapes (with PV /
without PV); tariff and sky are inert. The branch's four columns are genuinely
distinct (hour 0: `sunny_PV` 0.029 vs `cloudy_PV` 0.059), so
`a4fab1c6 add updated values from elia` came from a source **later than the
public workbook**. My extraction in
[`data/walloon/elia_adeqflex2025/`](../data/walloon/elia_adeqflex2025) is the
*published* version and should be treated as the audit baseline, not the input.

**Action:** record the provenance of the updated values (who at Elia, which
document, what date) next to the CSV. It is currently the only unsourced input in
the EV chain.

### 1.3 A real bug fixed: the profile was in the wrong timezone

`elia_natural_charging_daily_profile.csv` (local time) is renamed `_local.csv`
and superseded by `_utc0.csv`, shifted **−2 hours**. Snapshots are UTC
(`get_snapshots(..., tz="UTC")`), so the old profile put the Walloon evening
charging peak two hours early — through every horizon of every run to date. The
shift is exact: `utc[h] == local[h − 2]` for all 24 hours, both vintages.
`bev_dsm_restriction_time` moved 17 → 7 in the same pass, with a timezone note.

### 1.4 Horizon-varying parameters, sourced from Elia

`bev_dsm_availability` and `bev_avail_{max,mean,min}` become dicts, and the
config schema (`scripts/lib/validation/config/sector.py`) plus
`config/schema.default.json` were regenerated to match:

| | 2025 | 2030 | 2040 | 2050 | source |
|---|---:|---:|---:|---:|---|
| `bev_dsm_availability` | 0.01 | 0.07 | 0.21 | 0.28 | Elia V1M+V2M, "Current commitments" — **exact** for 2025/2030; 2040/2050 extrapolate past Elia's 2036 (0.18) |
| `bev_avail_max` | 0.4 | 0.4 | 0.48 | 0.48 | Elia availability table, 2026 vintage → 2025/2030, 2036 vintage → 2040+ |
| `bev_avail_mean` | 0.32 | 0.32 | 0.35 | 0.35 | (measured: 0.316 / 0.351) |
| `bev_avail_min` | 0.2 | 0.2 | 0.18 | 0.18 | (measured: 0.202 / 0.180) |

`build_natural_charging_shape` now picks the vintage **closest to the planning
horizon** instead of the hard-coded 2026 — decision E9, resolved.

### 1.5 The two configs are aligned

`config/config.walloon.yaml` now carries the full EV block. **This closes the
finding I flagged as most urgent**: the coupled study no longer silently inherits
`bev_dsm_availability: 0.5` and `v2g: true` from `config.default.yaml`. The four
`scen_*` configs and `config.default.yaml` got the block too.

What that changes, BEV charger `p_nom` at BEWAL:

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| archived run (`0.5` default × energy share) | 364 | 1 520 | 5 985 | 8 887 MW |
| branch (Elia dict × energy share) | **7** | **213** | **2 514** | **4 977** MW |

So the archived 2026-08-14 results are not comparable with anything the branch
produces: the flexible EV fleet shrinks by 3–50× depending on horizon. Any
re-run must be a full re-run.

### 1.6 Scope creep to check before merging

Three changes on the branch are **not** about BEV and look like they arrived with
`d07f35bf Merge branch 'master' into feat/bev-myopic`:

* `config.walloon.yaml`: `resolution_sector: 6h` → **`1h`**;
* `config.walloon.yaml`: `times_heat.urban_rural_split: times` → `times_base_year`
  and `base_year_capacities: false` → **`true`**, i.e. it leaves the legacy heat
  path that master deliberately keeps it on ("Left on the legacy path here;
  `config.walloon.yaml` enables it");
* `config.walloon.yaml`: `budget_national` regenerated, and
  `build_common_parameters.py` extended so `--write` patches **both** cost
  configs' `budget_national` block, not just `config.walloon.yaml`. This one is a
  genuine improvement and orthogonal to everything else.

The first two change what `config.walloon.yaml` means. **Confirm they are
intended** rather than merge fallout.

---

## 2. The energy-vs-fleet share defect (still open)

The branch adds `land_transport_electric_share` to the Walloon config —
0.15 / 0.35 / 0.81 / 1.0 — which are **Elia's Belgian passenger-car BEV+PHEV
stock shares** (sheet 2.2: 0.147 in 2025, 0.337 in 2030), extrapolated. Good
numbers. But `add_land_transport`'s `times_demand` branch is **unchanged**, so
for the Walloon node they are ignored: `electric_share[BEWAL]` is still
`electricity road / total road`, an **energy** ratio. The new config values apply
only to BEVLG, BEBRU, DE, FR, GB, NL and LU.

That leaves the config reading as if a fleet share were in use while the node the
study is about uses something else — and the underlying error unchanged:

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| `electricity road / total road` — used for BEWAL | 0.034 | 0.142 | 0.559 | 0.830 |
| Elia BE car BEV stock share — now in the config, unused at BEWAL | 0.15 | 0.35 | 0.81 | 1.00 |
| **TIMES car BEV stock share** (`VAR_Cap`) | **0.152** | **0.529** | **1.000** | **1.000** |
| TIMES car BEV activity share (`VAR_Act`) | 0.136 | 0.500 | 1.000 | 1.000 |

The energy ratio is the **right** number for the load and the **wrong** number
for `p_nom` and `e_nom`, which scale on `number_cars × electric_share`. With the
branch's own `bev_dsm_availability`, correcting the share alone moves BEWAL's
2030 charger from **213 MW to 793 MW**.

Note how well Elia and TIMES agree on the *fleet* (0.15 vs 0.152 in 2025;
0.35 vs 0.53 in 2030 is the one real gap) — which is the argument for taking the
share from TIMES for BEWAL and leaving Elia's values for the other nodes.

**`number cars` is still frozen** at 1 946 792 for every horizon; TIMES has
1 716 k → 1 866 k → 2 118 k, a 21 % rise.

`TIMES_PyPSA` exports all of this: `times_pypsa/transport_softlink.py` +
`data/transport_softlink_groups.csv`, written as `road_transport_{year}.csv` and
`..._shares.csv` by `export_all_horizons` and into every `export-coupling`
bundle, opt-in in `export_horizon`. 15 tests, green on the toy fixture and the
full `.vd`. Design points: the selector is the unit pair `000VEH`/`BVKM` (not the
`Aggregation Level 2` label, which also covers the `PJA` fuel technologies); the
vehicle class comes from the process **description**, never the code prefix
(fourteen `TCARGASEX1x` codes are trucks and vans); `VAR_Cap` only, never
`VAR_Cap + VAR_Ncap`; PHEV and HEV map to `ice` because PyPSA has no PHEV
component.

TIMES 2030 stock, thousand vehicles:

| class | BEV | PHEV | HEV | ICE | BEV stock share |
|---|---:|---:|---:|---:|---:|
| cars | 987.9 | 5.8 | 15.0 | 857.2 | **52.9 %** |
| light commercial vehicles | 0.1 | — | 158.7 | 150.0 | 0.0 % |
| heavy duty trucks | 0.0 | — | 5.1 | 33.3 | 0.0 % |
| buses | — | — | 0.4 | 6.9 | 0.0 % |
| two and three wheelers | 198.3 | — | — | 215.5 | 47.9 % |

> The two/three-wheeler share is dominated by **electric bicycles**. Not mopeds.

---

## 3. Two defects in the branch

### 3.1 The charger loss is now counted twice — 11 % too much electricity

`add_EVs` gained one line:

```python
profile_inflexible /= options["bev_charge_efficiency"]   # 0.9
```

The intent is defensible: the flexible load sits on the EV-battery bus behind the
BEV charger link (which applies 0.9), while the inflexible load sits directly on
the AC bus, so without the division the two branches represent different things.

**But TIMES already models the charger loss, and `electricity road` is metered
upstream of it.** In `scen_demande_haute`:

| TIMES process | VAR_FIn 2030 | VAR_FOut 2030 | ratio |
|---|---:|---:|---:|
| `TCHARGHOMN01` Home EV charger | 3.380 PJ | 3.211 PJ | **0.95** |
| `TCHARGWRKN01` EV charging at home | 8.223 PJ | 7.812 PJ | **0.95** |

`extraction_rules.csv` measures `electricity road` at `fuel_input` / `VAR_FIN` of
those processes — i.e. **grid-side, before the 0.95**. Their VAR_FIn sums to
11.60 PJ against the exported 12.215 PJ (3.393 TWh), so ~95 % of the transferred
figure is charger input.

Applying PyPSA's 0.9 on top therefore double-counts:

| BEWAL road-transport grid draw, 2030 | TWh | vs TIMES 3.393 |
|---|---:|---:|
| before this branch | 3.419 | +0.8 % |
| **with `/= bev_charge_efficiency`** | **3.770** | **+11.1 %** |

The error scales with `bev_dsm_availability`, because before the change only the
flexible slice passed through the charger. At the 2030 value of 0.07 it was
rounding (+0.8 %); at the `config.default.yaml` 0.5 the archived run actually
carried **+5.6 %** at every horizon (measured on
`results/walloon/scen_demande_haute/`); with the branch's line it becomes
+11.1 % regardless of `dsm`, because the whole load is affected. **The coupled Walloon
transport electricity demand is 11 % above the TIMES answer the soft-link exists
to transfer.**

Three ways out, and one of them has to be chosen:
1. **Drop the division** and instead scale the *flexible* load by 0.9 before
   attaching it, so both branches draw exactly their share of the TIMES figure.
   Preserves the transfer, keeps the two branches consistent.
2. **Set `bev_charge_efficiency: 1.0`** for the coupled configs, on the grounds
   that TIMES has already applied 0.95 and PyPSA should not model the loss twice.
   One config line, but it hides the charger from the LP entirely.
3. **Re-meter the TIMES export** at the charger's `VAR_FOut` instead of
   `VAR_FIn`, so `electricity road` becomes battery-side and PyPSA's 0.9 is the
   only charger loss. Cleanest conceptually, changes a `TIMES_PyPSA` extraction
   rule and every downstream number.

Recommendation: **(1)**. It is local to `add_EVs`, keeps both models' physics
visible, and needs no re-export. Either way, add a test asserting that total EV
grid draw at the Walloon node equals `electricity road` to within the charger
efficiency — the absence of that guard is why this went unnoticed.

### 3.2 `local_bev_dsm` is hard-indexed by horizon

```python
weights = charging_weights[investment_year]
```

Every other year-dependent option on the branch goes through `_helpers.get()`,
which holds or interpolates. This one raises `KeyError` on any horizon absent
from the dict. It works today — every config's `local_bev_dsm` covers its own
`planning_horizons`, and I checked all six — but `config.walloon.yaml` lists only
2025/2030/2040/2050 while `config.walloon.yaml` and the rest also carry
2035/2045. Adding 2035 to a Walloon run would crash in `build_transport_demand`.
**Use `get()`, or validate the coverage against `planning_horizons`.**

---

## 3b. Strategy: how to weight all the Elia profiles consistently

**The problem.** There are six profile columns, two config keys and one TIMES
model, and the weights are easy to make *plausible* and hard to make
*consistent*. The branch's 2025 and 2030 weights reproduce Elia almost exactly;
its 2040 and 2050 weights do not, because the two config keys were extrapolated
independently.

### 3b.1 Three levels, and the rule for each

| level | what it weights | source | rule |
|---|---|---|---|
| **1 — flexibility mode** | natural / local / market | `ev_operation_mode_shares.csv` | all three from **one (scenario, year) cell**, or they cannot be consistent |
| **2 — inside natural** | home / work / public | `ev_v0_location_shares.csv` | rebuild per horizon; Elia's `natural` column *is* this weighted sum |
| **3 — inside local** | work vs home; sky × PV | **not published by Elia** | needs a model-side input — §3b.4 |

The reason level 1 is delicate is that pypsa-wal splits one Elia row across two
config keys with different denominators:

* `sector.bev_dsm_availability` = the **market** share of the whole fleet;
* `sector.local_bev_dsm` = natural vs local **renormalised over those two only**,
  because `split_transport_demand` applies it to what is left after the market
  slice.

So `natural_abs = local_bev_dsm.natural × (1 − bev_dsm_availability)`, and it is
that product — not the config number — that must equal Elia's `V0`.

### 3b.2 What the branch's weights imply, against Elia

| horizon | branch natural | branch local | branch market | Elia natural | Elia local | Elia market |
|---|---:|---:|---:|---:|---:|---:|
| 2025 | 0.693 | 0.297 | 0.010 | 0.69 | 0.30 | 0.01 |
| 2030 | 0.465 | 0.465 | 0.070 | 0.47 | 0.46 | 0.07 |
| 2040 | 0.316 | 0.474 | **0.210** | 0.27 | 0.55 | 0.18 |
| 2050 | **0.288** | **0.432** | **0.280** | **0.17** | **0.55** | **0.28** |

All shares of the whole fleet. 2025 and 2030 are right. **2040 and 2050 pair the
market share of a *more* flexible Elia case with the natural/local split of a
*less* flexible one**: 0.28 in 2050 is exactly Elia's **High Flex 2036** market
share, but High Flex 2036 has natural at 0.17, not 0.288. Natural ends up **+69 %**
and local **−21 %** against the case the market share was taken from.

### 3b.3 The rule: pick a scenario, hold the year, never extrapolate

1. **Name the Elia scenario** and read all three modes from it. Extra flexibility
   comes from the **scenario axis**, which Elia publishes, not from extending a
   year.
2. **Map horizons onto Elia years, holding the last one.** Elia stops at 2036;
   2040 and 2050 both take 2036. A behavioural adoption curve extended 14 years
   past its source is worse than its last observed point, and holding it is
   auditable.
3. **Renormalise natural/local over themselves** before writing `local_bev_dsm`.

[`scripts/walloon_scripts/build_ev_charging_weights.py`](../scripts/walloon_scripts/build_ev_charging_weights.py)
does this and prints a consistency audit that reproduces Elia's absolute shares
exactly. Base case, **Current commitments**:

| horizon | Elia year | `bev_dsm_availability` | `local_bev_dsm.natural` | each of 4 home | `work` |
|---|---|---:|---:|---:|---:|
| 2025 | 2025 | 0.01 | 0.697 | 0.0498 | 0.104 |
| 2030 | 2030 | 0.07 | 0.505 | 0.0909 | 0.131 |
| 2040 | 2036 *(held)* | **0.18** | **0.329** | 0.1381 | 0.118 |
| 2050 | 2036 *(held)* | **0.18** | **0.329** | 0.1381 | 0.118 |

Sensitivity, **Current commitments – High Flex** — this is where a
flexibility-rich 2050 should come from:

| horizon | Elia year | `bev_dsm_availability` | `local_bev_dsm.natural` |
|---|---|---:|---:|
| 2025 | 2025 | 0.030 | 0.691 |
| 2030 | 2030 | 0.131 | 0.465 |
| 2040 | 2036 *(held)* | **0.280** | **0.236** |
| 2050 | 2036 *(held)* | **0.280** | **0.236** |

**Minimum change to the branch:** if the 0.21/0.28 market trajectory is kept
because the study wants that much 2050 flexibility, then `local_bev_dsm.natural`
must come down to **0.236** for 2040 and 2050, not stay at 0.40. Keeping both is
the one combination that matches no Elia case at all.

### 3b.4 Level 3, where Elia gives nothing

**Work vs home.** Elia publishes no location split for `V1H`. The only
Elia-grounded proxy is the **`V0` location split restricted to home + work**,
since Elia explicitly assumes no flexibility from public charging:

| | 2025 | 2030 | 2036 |
|---|---:|---:|---:|
| work / (home + work) | 0.343 | 0.265 | **0.176** |
| branch `work` weight, as a share of local | 0.333 | 0.600 | 0.500 |

The proxy **declines** — Elia has home charging rising 0.53 → 0.70 as private EV
ownership displaces company cars — while the branch's rises. 2025 agrees; 2030
and later do not. The counter-argument is real (workplace *smart* charging is a
different thing from workplace *natural* charging, and it is tariff-driven rather
than plug-in-driven), but it is an assumption, and right now it is the only
unsourced weight in the block. **Use the proxy, or document the reasoning for
departing from it.**

**With PV vs without PV.** This is the one place where TIMES should drive the
weight, and it does not yet. The right quantity is the share of *EV-owning
dwellings* that have rooftop PV. Neither model has it directly, but both have
dwelling-level PV penetration, and TIMES has it exogenously per horizon:

* **Recommended:** export residential PV capacity per horizon from TIMES
  (`times_pypsa` already reads `VAR_Cap`; the `PV residential`/`ALL-PV` processes
  are in the same table as the vehicle fleet), divide by dwellings, and use that
  as the with-PV weight. It keeps the split on the TIMES trajectory, which is the
  point of the coupling, and it is the same export mechanism as
  `road_transport_*.csv`.
* **Do not** use PyPSA's own endogenous `solar-rooftop` capacity: it is a model
  output, so the weight would depend on the solution it feeds.
* **Interim:** 50/50, as the branch has, noting that EV owners are richer than
  average and more likely to own PV, so 50 % is a lower bound on the with-PV
  share.

**Sunny vs cloudy.** A fixed weight is the wrong instrument: PyPSA already knows
which days are sunny. The physically correct treatment is to **select the curve
per day** from the model's own rooftop-PV availability — above/below the median
daily capacity factor at that node — instead of blending two shapes that never
occur simultaneously. Concretely: pass `profile_adm_solar.nc` (or the rooftop
`p_max_pu`) into `build_transport_demand`, compute a daily sunny/cloudy mask, and
build the local shape on the snapshot index rather than by tiling a weekly
profile. That turns `build_natural_charging_shape` from day-invariant to
day-varying, which is why it is a separate change and not part of the weight fix.
**Interim:** 50/50, which is what the equal home weights above give.

### 3b.5 Where TIMES constrains this, and where it does not

| quantity | TIMES has it? | consequence |
|---|---|---|
| natural / local / market split | **no** — one `EV charger` process, no operation modes | must come from Elia; TIMES cannot arbitrate |
| BEV fleet and its growth | **yes** — `road_transport_*.csv` | drives what the shares are applied *to* (§2) |
| road electricity demand | **yes** — `electricity road` | the total the profiles redistribute; must stay matched (§3.1) |
| residential PV penetration | **yes** — `VAR_Cap` on the PV processes | should drive the with-PV weight, §3b.4 |
| daily weather | **no** — only electricity is sub-annual | PyPSA must supply the sky split |

So the division of labour is: **TIMES sets the magnitudes, Elia sets the shapes
and the behavioural split, PyPSA supplies the weather.** Every weight above is
placed according to which of the three owns it. The one place the current
implementation departs from that is the sky and PV split, which is why §3b.4 is
the next piece of work rather than a nicety.

---

## 4. Merging with the 2026-08-21 doc + discount-rate work

`git merge-tree` between the two: **one conflict, in `config/config.walloon.yaml`
only**, and it is entirely comments plus the heat settings of §1.6 — no EV lines,
no discount-rate lines. `config.walloon.yaml`,
`scripts/build_common_parameters.py`, `scripts/prepare_sector_network.py` and
`rules/build_sector.smk` all auto-merge, including the `HURDLE_SECTORS` change
against their `patch_walloon_config` change.

Resolution: take the branch's `times_heat` block, then re-apply the doc renames
(`heat_soft_linking.md` / `heat_softlink_option_b.md` → `heat-softlink.md`) and
keep the `retrofitting: interest_rate: 0.12` block. The branch still references
the four deleted heat notes in comments; they need the same sweep.

---

## 5. Decisions still needed

Resolved by the branch: **E4** (Elia supplies the split), **E5** (Current
commitments, with Elia's own values), **E6** (equal weights on the four home
variants), **E7** (fixed exogenous shape), **E9** (vintage per horizon).

| # | Decision | Options | Recommendation |
|---|---|---|---|
| **E12** | **The charger-loss double count** (§3.1) | drop the division / `bev_charge_efficiency: 1.0` / re-meter TIMES at `VAR_FOut` | **drop the division and scale the flexible load by 0.9.** Blocks merging the branch. |
| **E1** | Which TIMES share replaces the energy ratio for **fleet** quantities? | `stock_share` / `activity_share` / keep the energy ratio | **`stock_share` for `p_nom`/`e_nom`, energy ratio for the load.** They answer different questions and both are exported. |
| **E2** | Which vehicle classes feed the Walloon EV components? | cars only / cars + LDV (Elia's boundary) / all road | **cars + LDV**, to match the Elia shares that set the split — needs E3 for the van count. |
| **E3** | Does TIMES also replace `number cars`? | keep the frozen 1.947 M / take TIMES `stock_kveh` | **take TIMES.** Same export, Walloon rather than population-scaled, removes a 21 % drift. Changes every horizon. |
| **E8** | The local profiles are a **winter** illustration in the published workbook — is that still true of the updated values? | apply year-round / heating season only / rebuild from the model's own PV profile | **ask Elia**, then apply year-round with the caveat recorded. Largest remaining fidelity loss, and §1.2 means it cannot be checked from the public workbook. |
| **E10** | Replace the synthesised BEV availability *shape* with Elia's hourly table? | keep `pkw.csv` scaled between the Elia min/mean/max / read `ev_availability.csv` | **read the table.** The branch already uses Elia's min/mean/max per vintage, so only the shape is still German traffic counts. Interpolate 2026 → 2036. |
| **E11** | V2G | `false` in the Walloon config on the branch | **keep `false`.** Elia gives V2H+V2M at 0.00–0.02 of the fleet to 2036, and the branch now sizes V2G on `bev_dsm_availability`, which is the V1M+V2M total — too generous if switched on. |
| **E13** | The `work` weight rises 0.10 → 0.30 while Elia's V0 workplace share *falls* 0.277 → 0.15 | keep / align with the location shares / source it | **document the reasoning.** V1H workplace smart charging and V0 workplace charging are different concepts, so the divergence may be right — but it is currently the only unsourced weight in the block. |
| **E14** | Provenance of the updated local profiles (§1.2) | — | **record who/what/when next to the CSV**, and keep the published-workbook extraction as the audit baseline. |

---

## 6. Changes still needed in pypsa-wal

**Before merging `feat/bev-myopic`**

1. **Fix the charger-loss double count** (E12 / §3.1) and add the grid-draw guard.
2. **Use `get()` for `local_bev_dsm`** (§3.2).
3. **Confirm the non-BEV changes** to `config.walloon.yaml` — `1h` resolution and
   the option-B′ heat path (§1.6).
4. **Record the provenance** of the updated Elia local profiles (E14).
5. **Sweep the four deleted heat-note references** out of the branch's config
   comments (§4).

**Then — the fleet share**

6. **New Snakemake artefact.** `rule build_wallon_demands` already calls
   `export_horizon`; add `road_transport=resources("road_transport_{planning_horizons}.csv")`
   as an output and pass `road_transport_path`. The pre-exported-bundle branch of
   `build_wallon_demands.py` needs the matching `shutil.copy2` and a clear error
   when an older bundle lacks the file — mirror how `heating_targets` handles it.
   **And add `transport_softlink_groups.csv` to `times_mapping_files()` in
   `rules/build_sector.smk`** at the same time, or editing the group definition
   will leave stale `road_transport_*.csv` on disk and Snakemake will reuse it
   silently — the exact failure that hid the 2026 Walloon heat leak. It is
   deliberately *absent* from that list today, because no rule reads it yet.
7. **Split `electric_share` into two variables** in `add_land_transport` /
   `add_EVs`: `electric_share_energy` (the load) and `electric_share_fleet` (the
   `p_nom`/`e_nom` scaling). A rename plus one new read — the arithmetic does not
   change. Also make the `times_demand` branch stop silently ignoring
   `land_transport_electric_share` at BEWAL, or say in the config that it does.
8. **Optionally replace `number cars`** (E3) for the Walloon node, the way
   `base_year_capacities` replaces one row of `existing_heating_distribution`.
9. **Guards.** The fleet share must be ≥ the energy share in every horizon (it
   must be, by efficiency); the three engine shares must sum to 1.

**Reporting (optional, low risk)**

10. **Split the blended inflexible load into `natural` and `local` carriers** so
    the three profiles are visible in the summaries and the explorer. Needs a new
    carrier plus its colour and nice-name entries in `config.default.yaml`.
    Physically a no-op (§1.1).
11. **Cap the flexible share** at `1 − public_share` (0.192 in 2025 → 0.150 in
    2036): Elia assumes no flexibility from public charging, so
    `bev_dsm_availability` cannot legitimately exceed that. Not binding at the
    branch's values (max 0.28), so this is a guard, not a fix.

---

## 7. Reference data

Extracted from the **published** `AdeqFlex2025_AssumptionsWorkbook.xlsx`, sheet
`3.3. DSR end-user`, by
[`scripts/walloon_scripts/extract_elia_adeqflex_ev.py`](../scripts/walloon_scripts/extract_elia_adeqflex_ev.py)
into [`data/walloon/elia_adeqflex2025/`](../data/walloon/elia_adeqflex2025). This
is the audit baseline for the branch's inputs, not the inputs themselves (§1.2).
The workbook is **not** in the repository.

| file | content |
|---|---|
| `ev_operation_mode_shares.csv` | V0 / V1H / V2H / V1M / V2M share and absolute kveh of the EV fleet, 2023–2036, 5 Elia scenarios |
| `ev_v0_location_shares.csv` | home / work / public split **inside** V0, 2025–2036 |
| `ev_daily_profiles.csv` | 24-hour profiles: V0 (home, work, public, aggregate-2026, aggregate-2036) and V1H/V2H (8 home variants + work) |
| `ev_availability.csv` | plugged-in share available to V1M/V2M, 24 hours, 2026 and 2036 |

Facts worth keeping:

* **The V0 aggregate is reconstructible.** It is the location-weighted sum of
  home/work/public, matching to ≤ 0.0006 per hour — so any intermediate year can
  be built from `ev_v0_location_shares.csv` rather than snapped to a vintage.
* **V1M/V2M profiles are Elia model *outputs*, not inputs.** Flexible charging
  must stay endogenous, which is what PyPSA does. What Elia supplies there is the
  **availability** (E10).
* **"No flexibility is assumed from public charging"** — the availability profile
  covers home and work only (item 11 above).
* **Elia counts a PHEV as half a BEV** and covers cars + LDVs together; TIMES
  counts vehicles per class. The denominators cannot be mixed without a
  conversion.
* The workbook rounds every profile to 3 decimals, so a daily profile sums to
  0.995–1.003. Normalise before use — `build_natural_charging_shape` does.

### A latent data-quality issue in `TIMES_PyPSA`

`data/mapping_processes.csv` has **seven duplicated process codes** (three
`TCARGMX*` cars, three `THDTGMX*` LNG trucks, `TCHARGHOMSMARTN01`), each
appearing once as a vehicle (`000VEH`) and once as a fuel technology (`PJA`).
`prepare_annual_values` merges on `process_code`, so any of them turning non-zero
would **duplicate its rows** in every extraction. All seven are zero in the
reference `.vd` — but LNG trucks are a plausible future. Separately,
`TCARGASEX14`'s `Description` was overwritten with the string
`TCHARGHOMSMARTN01`, so it matches no vehicle class and is dropped with a
warning. Both should be fixed in `mapping_processes.csv`.

---

## 8. Related

* [`heat-softlink.md`](heat-softlink.md) — the same soft-link pattern for heating,
  including the base-year-stock substitution that E3 imitates.
* [`discount-rates.md`](discount-rates.md) §6.2 — TIMES prices all road transport
  at 7.5 %, the other half of the EV-vs-heat-pump comparison.
* `TIMES_PyPSA/times_pypsa/transport_softlink.py` — the fleet export.
