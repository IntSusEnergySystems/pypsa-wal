# EV charging and EV shares — how the soft-link works, and what is still open

Land-transport electricity in PyPSA-Wal: the three charging profiles, where their
weights come from, how they stay consistent with Elia and TIMES, and the one
transfer that is still exogenous.

**Status:** the three-profile split is live, and so is the TIMES **fleet**
substitution — `p_nom`/`e_nom` scale on TIMES's BEV stock share and car count,
the load still on the energy ratio ([E1–E3](#5-decision-register), resolved).

| Section | |
|---|---|
| [§1](#1-what-the-model-does) | the mechanism, end to end |
| [§2](#2-energy-share-vs-fleet-share) | **energy share vs fleet share** — why they differ, and which drives what |
| [§3](#3-the-energy-identity) | why total EV grid draw equals the TIMES figure |
| [§4](#4-weighting-strategy) | **the three levels of weights, the rule for each, and `scen_evflex`** |
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
| `bev_dsm_availability` | 0.01 | 0.07 | 0.18 | 0.18 | `V1M+V2M`; 2040/2050 hold Elia's last year ([§4.3](#43-the-rule-pick-a-scenario-hold-the-year)) |
| `bev_avail_max` | 0.4 | 0.4 | 0.48 | 0.48 | availability table, 2026 vintage ≤ 2030, 2036 vintage ≥ 2035 |
| `bev_avail_mean` | 0.32 | 0.32 | 0.35 | 0.35 | (measured: 0.316 / 0.351) |
| `bev_avail_min` | 0.2 | 0.2 | 0.18 | 0.18 | (measured: 0.202 / 0.180) |

**Every horizon `config.default.yaml` lists must be listed here too.**
`update_config` merges dicts key by key, so an unlisted horizon silently inherits
the PyPSA-Eur default — `bev_dsm_availability: 0.5`, `bev_avail_min: 0.0` — and
`_helpers.get` returns that key without warning. `test_ev_charging.py` fails on
any leak, in a scenario overlay as well as in the base config: it checks the
merged result, because that is what a run sees.

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

## 2. Energy share vs fleet share

**Resolved (E1–E3).** One scalar was doing two jobs. `electric_share` at BEWAL is
the TIMES **energy** ratio `electricity road / total road`. That is the right
number for the load — it makes the EV grid draw equal the transferred demand
exactly ([§3](#3-the-energy-identity)) — and the wrong number for `p_nom` and
`e_nom`, which multiply a **vehicle count**. `add_EVs` now takes both:

| quantity | share used | why |
|---|---|---|
| `land transport EV` / `… inflexible` loads | `electric_share` — TIMES **energy** ratio | it is an energy flow; the identity in [§3](#3-the-energy-identity) depends on it |
| `BEV charger` / `V2G` `p_nom`, `EV battery` `e_nom` | `electric_share_fleet` — TIMES **BEV stock share, by count** | they multiply `number_cars`, a vehicle count |

`number_cars` at BEWAL is also TIMES's own, no longer the frozen
population-scaled 1 946 792.

### 2.1 How far apart the two shares are

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| `electricity road / total road` — the **load** | 0.034 | 0.142 | 0.559 | 0.830 |
| **TIMES car BEV stock share** (`VAR_Cap`) — `p_nom`/`e_nom` | **0.152** | **0.529** | **1.000** | **1.000** |
| TIMES car BEV activity share (`VAR_Act`) — see [§2.3](#23-by-count-not-by-km) | 0.136 | 0.500 | 1.000 | 1.000 |
| understatement, fleet ÷ energy | 4.47× | **3.72×** | 1.79× | 1.20× |
| Elia BE car BEV stock share — other nodes only | 0.15 | 0.35 | 0.81 | 1.00 |

The gap is not one effect but three, all measurable in the `.vd` (2030):

| step | share | factor |
|---|---:|---:|
| BEV share of cars, **by count** | 0.5294 | |
| BEV share of cars, **by km** | 0.4996 | ÷1.06 — BEVs drive slightly less than the average car |
| BEV share of **all road**, by km | 0.3689 | ÷1.35 — cars are 72 % of road km; LCVs (13.6 %), trucks (11.2 %) and buses are 0 % electric |
| electricity share of all road, **by energy** | 0.1423 | ÷2.59 — a BEV-km costs ~2.6× less final energy |

1.06 × 1.35 × 2.59 = **3.72**. So roughly one third is a boundary mismatch
(`number_cars` counts passenger cars, `total road` meters freight too) and two
thirds is drivetrain efficiency. It shrinks as the fleet electrifies: by 2050 only
the freight energy still in the denominator separates the two.

### 2.2 What it moves

Charger `p_nom` at BEWAL, MW, `number_cars × bev_charge_rate ×
electric_share_fleet × bev_dsm_availability` — the combined E1 + E3 effect, since
the car count changes too:

| horizon | before | after | | before (`scen_evflex`) | after |
|---|---:|---:|---:|---:|---:|
| 2025 | 7 | **29** | 3.9× | 22 | **86** |
| 2030 | 213 | **761** | 3.6× | 399 | **1 424** |
| 2040 | 2 155 | **4 201** | 2.0× | 4 250 | **8 286** |
| 2050 | 3 199 | **4 194** | 1.3× | 8 762 | **11 488** |

`e_nom` moves by the same factor (2030: 1 164 → 4 149 MWh). The **load does not
move at all**, which is the point — `test_split_draws_exactly_the_transferred_demand`
still holds.

> The relative correction is identical in both scenarios: `electric_share_fleet`
> and `bev_dsm_availability` are independent multipliers. What `scen_evflex`
> changes is the absolute MW at stake, in proportion to `bev_dsm_availability`.

### 2.3 By count, not by km

`road_transport_*_shares.csv` carries **both** `stock_share` (by count) and
`activity_share` (by driven km): 0.529 against 0.500 at 2030. The model uses
`stock_share`, because a charger rating and a battery capacity are per-**vehicle**
— you own the charger whether or not you drive. `activity_share` would be right
for a per-km quantity, and the two differ by only ~6 %, an order of magnitude less
than the 3.7× this substitution fixes. Switching is a one-word change in
`times_ev_fleet`.

### 2.4 The class boundary is immaterial if you are consistent

`EV_FLEET_CLASSES = ("cars",)`. Widening it to Elia's boundary (cars + light
commercial vehicles) moves the *share* a long way and the BEV *count* not at all,
because TIMES has ~0.1 kveh of electric vans:

| boundary | 2030 count | 2030 stock share | 2030 **BEV count** |
|---|---:|---:|---:|
| `cars` | 1 866 k | 0.5294 | **987.9 k** |
| `cars` + LCV | 2 175 k | 0.4543 | **988.0 k** |

Identical to four significant figures in every horizon. What matters is only that
the count and the share come from the **same** classes — `times_ev_fleet` reads
both from one class list, so they cannot diverge. `cars` is preferred because
`bev_energy` (60 kWh) and `bev_charge_rate` (11 kW) are passenger-car figures, and
widening the boundary would put a car-sized battery in every van.

### 2.5 What `TIMES_PyPSA` exports

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
make plausible and hard to make consistent. Two cases are generated:
**Current commitments** as the base ([§4.2](#42-never-hand-edit-one-of-the-two-keys))
and **High Flex, extrapolated** as the ambitious one
([§4.6](#46-the-extrapolated-high-flex-case-scen_evflex)).

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
python scripts/walloon_scripts/build_ev_charging_weights.py --scenario "Current commitments - High Flex" --extrapolate
```

It derives both blocks from one Elia cell and prints an audit that reproduces
Elia's absolute shares exactly. `test_ev_charging.py` fails if the two keys drift
onto different Elia scenarios, and — for the generated scenario overlay — if
either block stops matching the generator's output byte for byte.

Base case, **Current commitments**:

| horizon | Elia year | `bev_dsm_availability` | `local_bev_dsm.natural` | each of 4 home | `work` |
|---|---|---:|---:|---:|---:|
| 2025 | 2025 | 0.01 | 0.697 | 0.0498 | 0.104 |
| 2030 | 2030 | 0.07 | 0.505 | 0.0909 | 0.131 |
| 2040 | 2036 *(held)* | 0.18 | 0.329 | 0.1381 | 0.118 |
| 2050 | 2036 *(held)* | 0.18 | 0.329 | 0.1381 | 0.118 |

Flexibility-rich sensitivity, **Current commitments – High Flex**: market 0.030 /
0.131 / 0.280 / 0.280 with natural 0.691 / 0.465 / 0.236 / 0.236.

### 4.3 The rule: pick a scenario, hold the year

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

**The one sanctioned exception is `--extrapolate`**, used by `scen_evflex`
([§4.6](#46-the-extrapolated-high-flex-case-scen_evflex)). Clamping is right for
the base case, but it makes 2040 and 2050 say *nothing at all* about EV
flexibility, which is untenable for a scenario whose whole subject is how far it
could go. Extrapolating is allowed only when all three of these hold, and it is
the arithmetic — not the intent — that is being constrained:

1. **Saturating, not linear.** Straight-lining either fraction breaks inside the
   study horizon: High Flex's `V0` reaches zero by 2041 and Elia's `work`
   location share goes negative by 2049. A logistic against a ceiling cannot.
2. **Continuous with the data.** The path passes *exactly* through Elia's last
   observed value, and its slope is read from Elia's own last six years — not
   least-squares-fitted through the whole series, which would move 2036 itself.
3. **The ceiling is derived, or declared.** The steerable ceiling comes from the
   data; the market ceiling does not exist in the data, so it is named as an
   assumption and its sensitivity band is printed next to the result.

Extrapolating the **location** split still fails condition 3 — nothing bounds it
— so it is held even in the extrapolated case.

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
| BEV fleet and its growth | **yes** — `road_transport_*.csv` | drives what the shares are applied *to* ([§2](#2-energy-share-vs-fleet-share)) |
| road electricity demand | **yes** — `electricity road` | the total the profiles redistribute ([§3](#3-the-energy-identity)) |
| residential PV penetration | **yes** — `VAR_Cap` on the PV processes | should drive the with-PV weight ([§4.4](#44-level-3-where-elia-gives-nothing)) |
| daily weather | **no** — only electricity is sub-annual | PyPSA must supply the sky split |

**TIMES sets the magnitudes, Elia sets the shapes and the behavioural split, PyPSA
supplies the weather.** Every weight is placed according to which of the three
owns it. The sky and PV splits are the only places where that is not yet true.
### 4.6 The extrapolated High Flex case (`scen_evflex`)

An ambitious EV-flexibility scenario, added because clamping leaves the base case
saying nothing about 2040 and 2050 — the two horizons the study is actually
about. It is **Elia's most ambitious flexibility case, "Current commitments –
High Flex", through 2035, then extrapolated**. Defined in
[`config/scenarios.walloon.yaml`](../config/scenarios.walloon.yaml) as an overlay
on `scen_demande_haute`, differing from it in nothing but the two EV weight keys,
so a diff between the two runs *is* the EV-flexibility sensitivity.

```bash
python scripts/walloon_scripts/build_ev_charging_weights.py \
    --scenario "Current commitments - High Flex" --extrapolate
```

| horizon | basis | `bev_dsm_availability` (market) | natural abs | local abs | `local_bev_dsm.natural` | each of 4 home | `work` |
|---|---|---:|---:|---:|---:|---:|---:|
| 2025 | Elia 2025 | 0.030 | 0.670 | 0.300 | 0.6908 | 0.0508 | 0.1060 |
| 2030 | Elia 2030 | 0.131 | 0.404 | 0.465 | 0.4652 | 0.0983 | 0.1416 |
| 2035 | Elia 2035 | 0.270 | 0.190 | 0.540 | 0.2601 | 0.1496 | 0.1415 |
| 2040 | extrapolated | 0.355 | 0.153 | 0.492 | 0.2370 | 0.1571 | 0.1346 |
| 2045 | extrapolated | 0.433 | 0.150 | 0.417 | 0.2651 | 0.1513 | 0.1297 |
| 2050 | extrapolated | 0.493 | 0.150 | 0.357 | 0.2957 | 0.1450 | 0.1243 |

2035 and 2045 are not planning horizons; they are listed because an unlisted
horizon inherits the PyPSA-Eur default ([§1.2](#12-horizon-varying-parameters)).

#### What is extrapolated

Not the three mode shares directly — that would let them stop summing to 1 — but
the two quantities that are genuinely adoption curves, each continued as a
logistic that is **linear in log-odds against a ceiling**:

| fraction | 2030 | 2036 | ceiling | 2040 | 2050 |
|---|---:|---:|---:|---:|---:|
| steerable, `1 − V0` | 0.596 | 0.830 | **0.850** — derived | 0.847 | 0.850 |
| market *of* steerable, `(V1M+V2M) / (1 − V0)` | 0.220 | 0.337 | **0.700** — assumed | 0.419 | 0.580 |

`natural`, `local` and `market` are then rebuilt from the two, so they sum to 1
by construction exactly as Elia's own rows do. Each curve is anchored on Elia's
2036 value with the slope its 2030 → 2036 window implies, so **2036 is reproduced
exactly** and the path is continuous with the data.

**The steerable ceiling is derived from the data.** Elia states that no
flexibility is assumed from public charging, so public-charged energy is
unmanaged whatever the tariff or the aggregator does, and `1 − public` at Elia's
last year — **0.850** — bounds everything steerable. It is a genuine
interpretation, not a quotation: `ev_v0_location_shares.csv` gives the location
split *inside* `V0`, and using it as a share of *all* charging is the reading
already adopted in [§6](#6-remaining-work) work item 9. Two things corroborate it.
High Flex's own steerable share stops at 0.830 in 2036 — just under the ceiling,
never through it — which is what one would expect if Elia is applying the same
bound internally. And the shares Elia does publish inside `V0` decline for a
reason (company cars → private ownership) that has finished by 2036, so the
alternative — extrapolating the public share down and letting the ceiling drift
up — would be continuing a mechanism that has run out.

**The market ceiling is an assumption, and the only invented number here.**
Nothing in the Elia data pins how much of *steerable* charging ends up explicitly
market-steered (`V1M`) rather than locally optimised (`V1H`), and Elia's own
series is still rising when it ends. 0.70 says three tenths of steerable charging
stays on PV self-consumption and static-tariff timers — `V1H` by Elia's
definition however cheap wholesale power gets. It moves 2050 by about ±0.035:

| market ceiling | 2040 | 2045 | 2050 |
|---|---:|---:|---:|
| 0.60 | 0.348 | 0.412 | 0.455 |
| **0.70** | **0.355** | **0.433** | **0.493** |
| 0.80 | 0.359 | 0.448 | 0.523 |

The generator prints this band on every run, so the assumption cannot be read
without its sensitivity.

#### What is *not* extrapolated

The **location** split (levels 2 and 3): `work_of_local` holds at 0.176 from 2036
on. Its driver is the company-car → private-ownership shift, which completes
inside Elia's window (home charging 0.531 → 0.700), so there is no mechanism left
to continue — and a straight line puts the `work` share negative by 2049. Holding
it is also what keeps the public share, and therefore the steerable ceiling, at
one auditable value. The sky and PV splits stay 50/50 for the same reasons as the
base case ([§4.4](#44-level-3-where-elia-gives-nothing)).

`bev_avail_{max,mean,min}` are **unchanged**. They come from Elia's availability
table, which is a vintage of *plugged-in behaviour*, not a flexibility scenario —
the same 2036 vintage applies to every case.

> **`local_bev_dsm.natural` rises after 2040 — 0.237 → 0.265 → 0.296 — and that
> is correct.** It is renormalised over natural+local, and the market slice taken
> off the top grows faster than natural shrinks, so natural gains share of a
> shrinking remainder. The **absolute** natural share still falls monotonically,
> 0.153 → 0.150. Reading the trend off the config key is the mistake;
> `test_extrapolated_shares_are_monotone_in_absolute_terms` pins the absolute
> series instead.

#### What it changes downstream, and what to watch

`bev_dsm_availability` at 2050 goes **0.18 → 0.493**, so roughly half of Walloon
EV demand becomes dispatchable. Three consequences worth carrying:

* **`p_nom` and `e_nom` scale with it.** The `BEV charger` link and the EV-battery
  store are both sized on `bev_dsm_availability`, so both are ~2.7× the base case
  at 2050 — *on top of* the 3.7× understatement from the energy-vs-fleet share
  ([§2](#2-energy-share-vs-fleet-share)). The two compound; fixing E1 changes
  this scenario more than it changes the base case.
* **V2G stays `false` (E11), and matters more now.** V2G is sized on
  `bev_dsm_availability`. Against Elia's V2H+V2M of 0.00–0.02, switching it on was
  already far too generous at 0.18; at 0.493 it would be a different study.
* **The charger-loss regression gets louder.** The error in
  [§3](#3-the-energy-identity) scales with `bev_dsm_availability`, so the table's
  "+5.6 % at `dsm` = 0.5" row stops being hypothetical — it is the 2050 value.
  The guard is unchanged and still passes.

#### Guards

`test_ev_charging.py` discovers scenario overlays that override either weight key
and applies every base-config invariant to the **merged** config, which is what a
run actually sees. Four checks are specific to this scenario:

| test | what it pins |
|---|---|
| `test_evflex_block_is_exactly_what_the_generator_produces` | both keys equal the generator's output — a hand-edit is a test failure, not a silent inconsistency |
| `test_flexible_share_stays_under_the_public_charging_ceiling` | market share and steerable share stay under `1 − public`; work item 9, now enforced |
| `test_extrapolated_shares_are_monotone_in_absolute_terms` | the extrapolation does not invert the trend it continues |
| `test_evflex_differs_from_its_baseline_only_in_the_ev_weights` | `times_file`, nuclear and the aggregate caps are still `scen_demande_haute`'s, so the diff stays an EV diff |

The scenario mechanism has no inheritance, so `scen_evflex` **copies**
`scen_demande_haute`'s non-EV overrides. That last test is the only thing stopping
the two from drifting apart the next time the study `.vd` is updated.

---

## 5. Decision register

### Decided

| # | Question | Decision |
|---|---|---|
| **E4** | Where do the three-way mode shares come from? | **Elia.** TIMES has one `EV charger` process and no operation modes, so it cannot arbitrate the split at all. |
| **E5** | Which Elia scenario? | **"Current commitments"** as the base; **"High Flex"** as the flexibility-rich sensitivity, regenerated with one flag. Never a hand-tuned middle. |
| **E15** | Does the ambitious case hold 2036 or extrapolate it? | **Extrapolate**, in `scen_evflex` only. Holding makes 2040 and 2050 say nothing about the one thing that scenario exists to explore. Allowed because the continuation is saturating, exactly continuous with Elia's 2036 value, and its ceilings are derived (steerable) or declared with a sensitivity band (market). The location split is still held — nothing bounds it. The base case still holds. [§4.6](#46-the-extrapolated-high-flex-case-scen_evflex) |
| **E6** | How is the V1H with-PV / without-PV pair combined? | **50/50 for now**, documented as a lower bound on the with-PV share. The TIMES residential-PV route is the intended replacement ([§4.4](#44-level-3-where-elia-gives-nothing)) and stays on the work list. |
| **E7** | Is the local profile a fixed shape or a constrained freedom? | **Fixed exogenous shape.** It is what the data supports (a published curve), needs no new components, and is directly comparable with the natural profile. A second flexible bucket with a tighter window than V1M would invent a window Elia does not give. |
| **E9** | Does the natural profile stay pinned to one vintage? | **No** — the vintage closest to the planning horizon is used. |
| **E11** | V2G | **`false`.** Elia gives V2H+V2M at 0.00–0.02 of the fleet to 2036, while V2G is sized on `bev_dsm_availability` (the V1M+V2M total) — far too generous if switched on. |
| **E12** | The charger loss | **Scale the flexible load down** by `bev_charge_efficiency`, not the inflexible one up. Rejected: `bev_charge_efficiency: 1.0` (hides the charger from the LP) and re-metering the TIMES export at `VAR_FOut` (cleanest conceptually, but changes every downstream number). [§3](#3-the-energy-identity) |
| **E13** | The `work` weight inside the local profile | **Use the Elia-grounded `V0` home+work proxy**, which declines 0.343 → 0.176. A hand-set weight rising the other way was the only unsourced number in the block. |
| **E1** | Which TIMES share replaces the energy ratio for **fleet** quantities? | **`stock_share` (by count) for `p_nom`/`e_nom`, the energy ratio for the load.** Both are exported and they answer different questions: a charger rating is per vehicle, a load is an energy flow. `activity_share` is the documented alternative for a per-km quantity, and differs by only ~6 %. [§2](#2-energy-share-vs-fleet-share) |
| **E2** | Which vehicle classes feed the Walloon EV components? | **`cars`** — *not* cars + LDV as first recommended. The boundary turns out to be immaterial to the BEV count (987.9 vs 988.0 kveh at 2030), because TIMES has ~0 electric vans; so the tie-breaker is that `bev_energy` and `bev_charge_rate` are passenger-car figures. What matters is that the count and the share come from the same classes, which `times_ev_fleet` enforces by construction. [§2.4](#24-the-class-boundary-is-immaterial-if-you-are-consistent) |
| **E3** | Does TIMES also replace `number cars`? | **Yes**, at BEWAL only. The frozen 1 946 792 becomes 1 716 k → 1 866 k → 2 122 k → 2 118 k. It *falls* at 2025–2030, so it partly offsets E1: the combined charger correction is 3.6× at 2030, not 3.7×. |

### Open

| # | Question | Recommendation | Blocks |
|---|---|---|---|
| **E8** | Are the local curves still a **winter** illustration? True of the published workbook; unknown for the values in use ([§7](#7-reference-data)). | **Ask Elia**, then apply year-round with the caveat recorded. | largest remaining fidelity loss |
| **E10** | Replace the synthesised BEV availability *shape* with Elia's hourly table? | **Read the table** and interpolate 2026 → 2036. The min/mean/max already come from Elia; only the shape is still German traffic counts (`pkw.csv`). | flexible-charging realism |
| **E14** | Provenance of the local curves in use | **Record who, what document, what date next to the CSV.** | the only unsourced input in the EV chain |

E1–E3 landed together, as one substitution: the share and the count come from the
same TIMES export and the same vehicle classes, so wiring one without the others
would have produced a count/share mismatch rather than a fix. E10 (the
availability *shape*) is independent and still open.

---

## 6. Remaining work

**Fleet share (E1–E3) — done.** What it took, for reference:

| where | change |
|---|---|
| `rules/build_sector.smk` | `build_wallon_demands` gains `road_transport_{h}.csv` **and** `road_transport_{h}_shares.csv` as outputs; `prepare_sector_network` gains the shares file as an input; `transport_softlink_groups.csv` joins `times_mapping_files()` so editing a class definition invalidates the export |
| `scripts/build_wallon_demands.py` | passes `road_transport_path`; the pre-exported-bundle branch copies both files and errors clearly when an older bundle lacks them |
| `scripts/prepare_sector_network.py` | `times_ev_fleet()` reads the count and the BEV share from one class list; `add_land_transport` overrides `number_cars` and derives `electric_share_fleet` at BEWAL; `add_EVs` takes `electric_share_fleet` for `p_nom`/`e_nom` and keeps `electric_share` for the load |
| `config/config.walloon.yaml` | `land_transport_electric_share` now says in the config that it applies to the non-Walloon nodes only |
| `test/test_ev_charging.py` | the count/share boundary, the unknown-class error, and a source pin so `p_nom` cannot drift back onto the energy share |

Two runtime guards, both raising rather than warning — each means the two
extractions disagree, which is structural, not an approximation:

* the TIMES BEV **fleet** share must be ≥ the road-electricity **energy** share
  (it must be: a BEV converts more of its energy into km, and the energy
  denominator also carries freight the car count excludes);
* the ICE share must not go negative, i.e. road electricity + hydrogen must not
  exceed total road.

Still open here: `bev_avail_*` remain Elia's (E10), and the *other* nodes still
use one config share for both jobs — correct only insofar as
`land_transport_electric_share` is read as a fleet share, which is now stated in
the config.

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
9. ~~**Cap the flexible share** at `1 − public_share`.~~ **Done as a test**, not
   as a runtime cap: `test_flexible_share_stays_under_the_public_charging_ceiling`
   checks both the market share and the whole steerable share against `1 − public`
   at Elia's last year (0.850). Slack in the base case (0.18); the binding
   constraint on `scen_evflex`, whose steerable share saturates *on* it
   ([§4.6](#46-the-extrapolated-high-flex-case-scen_evflex)). A runtime cap would
   silently rewrite a config value, which is worse than failing.

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
