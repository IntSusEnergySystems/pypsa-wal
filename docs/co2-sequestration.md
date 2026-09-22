# CO₂ capture volumes, transport and sequestration in PyPSA-WAL

**Scope.** Everything on the *disposal* side of carbon capture: how much CO₂ the
model may bury and where, what that costs, how it leaves Wallonia, how much the
model actually captures and why, and what to change to make that credible.
Companion file [`ccs_alignment.md`](ccs_alignment.md) covers the capture
*technologies* themselves (CCGT-CC, DAC, biomass→H₂, the industrial capture
floor) and their alignment with TIMES-WAL.

**Status.** Configuration current as of 2026-09-02 (4/4 optimal). Review of §§4–8
performed 2026-09-19 against the cabinet batch
([`logs/2026-09-13_cabinet_batch_all14_2010_1h.md`](logs/2026-09-13_cabinet_batch_all14_2010_1h.md)).
All figures in §§4–8 were recomputed directly from the solved networks
`results/walloon/scen_central/networks/base_s_adm___{2025,2030,2040,2050}.nc`
(pypsa 1.2.1), cross-checked against `scen_realiste_nets` / `scen_realiste_nobnd30`
and against the TIMES indicator CSVs under `results/walloon/<scen>/html/indicators/`.
Claims are tagged **[V]** verified by direct computation, **[I]** inferred by
arithmetic. **§10.3 added 2026-09-22**: whether a sequestration-price or gas-price
lever can produce a low-CCS pathway, measured on the duals of `scen_central` and on
all 16 solved networks on disk.

---

## 1. Summary

**The limit.** Two independent layers limit sequestration, and their config keys
differ by one word (§2). The pooled global cap
(`sector.co2_sequestration_potential`) is an unsourced whole-Europe scalar
applied without a country dimension to a six-country model; it used to bind in
every horizon at up to 360 EUR/t. Since 2026-08-29 it is demoted to a deployment
ramp (0 / 0 / 60, then a non-binding 1000) and the per-node CO₂StoP store — the
layer that actually encodes geology — does the limiting: GB 100, DE 79.1, NL 9.1,
**all Belgian nodes 0** Mt/a (§3).

**The result.** Four findings from the 2026-09-19 review, all verified:

1. **Walloon emissions are not an economic outcome — they are the cap.** The
   BEWAL cap binds to floating point in all four horizons, slack `−0` kt
   throughout, and capture is the adjustment variable that closes the balance.
   By 2050 the model captures **6.3× the entire Walloon emissions allowance**
   (§4.1).
2. **Walloon gas use rises to 2040** (+16 % 2030, +15 % 2040 vs 2025). Unabated
   CCGT is Wallonia's single largest emitter in 2040 — larger than aviation. The
   system decarbonises by capturing, not by burning less (§4.2).
3. **Disposal is under-priced, but not by the parameter.** The LP pays
   86.5 / 57.7 / 78.1 EUR/t in 2030/2040/2050 — the 30 EUR/t parameter plus a
   geological scarcity rent. The residual gap against a realistic
   transport-and-storage chain is confined to 2040. What *is* badly wrong is a
   **per-vintage application of the geological ceiling**: German storage sized
   for 79 Mt/a is drained at 209 Mt/a by 2050 (§5).
4. **Carbon recycling is structurally absent** — zero electrolysis and zero
   Fischer-Tropsch, in every horizon, system-wide (§8). One root cause — cheap
   gas, under-priced carbon disposal, and the cheapest renewables suppressed by a
   soft-link pin — produces both symptoms: runaway CCS *and* no power-to-fuel.
5. **No price lever can produce a low-CCS pathway** (§10.3, added 2026-09-22). A
   sequestration levy passes into the shadow carbon price at **1.00–1.12 : 1** and
   changes the capture volume by **zero** — 82 EUR/t would add ~500–550 MEUR/a of
   Walloon disposal cost for no emissions change. The gas price cannot reach
   **71 % (2040) / 58 % (2050)** of the capture at all, because that share is
   process and biogenic carbon. What *has* moved capture in a solved run is
   **nuclear capex** (−26 % total, −59 % power at 2050 across `scen_nuctip_*`);
   what would move it by construction is the **quantity** lever D.

**What to do,** in order, because the levers are not interchangeable and two of
them double-count if applied together: fix the per-vintage ceiling bug, fix
`threshold_capacity`, then re-measure before touching any cost parameter; then a
net CO₂ export cap; then the rooftop-pin sensitivity; then any 2040 target
change. Full plan in §10, **levers for a low-CCS variant in §10.3**, test sequence
in §11.

---

## 2. How the model limits sequestration — two layers

### 2.1 Layer A — one pooled global constraint

`sector.co2_sequestration_potential` (Mt CO₂/a, per investment period) becomes a
single `GlobalConstraint` in
[`add_co2_sequestration_limit()`](../scripts/solve_network.py:253):

```python
n.add("GlobalConstraint", names, sense=">=", constant=-limit * 1e6,
      type="operational_limit", carrier_attribute="co2 sequestered", ...)
```

with `limit = get(limit_dict, year) * nyears`. One constraint, `carrier_attribute`
only — **no country dimension and no scaling by how many countries are
modelled**. Upstream gets away with this because upstream models ~33 countries.
This model has six: BE (three nodes), DE, FR, GB, LU, NL.

### 2.2 Layer B — per-node store capacity from CO₂StoP

`sector.regional_co2_sequestration_potential` drives
[`build_clustered_co2_sequestration_potentials.py`](../scripts/build_clustered_co2_sequestration_potentials.py),
consumed in
[`prepare_sector_network.py:829`](../scripts/prepare_sector_network.py:829):

```python
e_nom_max = (e_nom_max.reindex(spatial.co2.locations)
             .fillna(0.0).clip(upper=max_size * 1e3).mul(1e6) / years_of_storage)
```

The clustered file has **three rows** — GB 54 580 Mt, DE 1 979 Mt, NL 227 Mt.
BEWAL, BEVLG, BEBRU, FR and LU are *absent* and get `fillna(0.0)`. They are
missing because `include_onshore: false` restricts the overlay to **offshore**
regions and Belgium's North Sea EEZ carries no CO₂StoP site clearing `min_size`.
That `fillna` has since been replaced by an explicit, sourced zero (§3.2).

### 2.3 Units gotcha

The two size keys are in **different units, in the same dict**, upstream:

| key | compared against | unit |
|---|---|---|
| `min_size: 3` | `gdf[attr].sum(axis=1)` and the regional total, both in Mt | **Mt** |
| `max_size: 25` | the same series, but via `max_size * 1e3` | **Gt** |

The comment shipped with the original commit said "Gt" for both and carried a
literal `TODO research suitable value` on `max_size`. Worth remembering before
anyone "fixes" `min_size: 3` thinking it means 3 Gt.

### 2.4 Provenance of the upstream global number

All three commits are in this repository's history (it carries the full upstream
history). None cites a source; none has a release note.

| When | Commit | Value | Justification given |
|---|---|---|---|
| 9 Dec 2020 | `3ff669b0` | `200` flat | inline comment `#MtCO2/a sequestration potential for Europe`. Nothing else. |
| 20 Aug 2024 | `dcc84dfb` | `0/0/50/100/200/200/200` | none. Shipped indented one level too deep and un-nested the same day by `5fb89068`. The release note for [PyPSA/pypsa-eur#1228](https://github.com/PyPSA/pypsa-eur/pull/1228) documents the *mechanism*, not the values. |
| 11 Jul 2025 | `e43746df` | `0/0/40/100/180/250/250` | none. A release-housekeeping commit that also touched CI and `conf.py`. **No entry anywhere in `doc/release_notes.rst`.** |

Documentation coverage is nil: the schema description
([`config/schema.default.json:4670`](../config/schema.default.json:4670)) is
*"The potential of sequestering CO2 in Europe per year and investment period."* —
no unit, no default, no source, unlike its neighbours `co2_sequestration_cost`
and `co2_sequestration_lifetime` — and there is no `configtables` entry and
nothing in `doc/sector.rst`.

**The one real justification, and what it is.** The 200 Mt/a ancestor is
explained in the papers that use it: ~153 Mt/a of European industrial **process**
emissions after industrial transformation, plus ~47 Mt/a of headroom for negative
emissions. That answers *"how much would we need to bury?"*, not *"how much can
be buried?"* It is a demand-side sizing convention, not geology, and it does not
cover the later 40/100/180/250 ramp, which post-dates it.

**What it did here.** With the Walloon overlay halving the series, the pooled cap
bound in **every** horizon of the 26 Aug run — duals 374 / 113 / 139 / **360**
EUR/t at 2025/2030/2040/2050 — while the geological layer had ~1 088 Mt/a of
unused headroom across GB, DE and NL. It is also the true content of the claim
that "2040's European sequestration cap is tighter than 2050's (90 vs 125 Mt)":
that is this constraint, not a physical fact about 2040.

---

## 3. Current configuration

### 3.1 The global series is a deployment ramp, not a potential

Of the two ways out — re-derive the global cap for the modelled subset, or drop
it to a non-binding value and let CO₂StoP do the limiting — **the second was
chosen** (2026-08-29): it removes an arbitrary number instead of replacing it
with a differently arbitrary one, and puts the geological limit in the layer that
actually models geology, per node, where the CO₂ network has to reach it and pay
for it. Two holes had to be patched at the same time: CO₂StoP is static geology
with no time dimension (a pure layer-B model would bury 188 Mt in 2025, when the
six modelled countries inject approximately nothing), and the 25 Gt clip
annualised over 25 years gives **GB alone 1 000 Mt/a**, 20× the UK's own
>50 Mt/a-by-2035 target.

`config/config.walloon.yaml`:

```yaml
  co2_sequestration_potential:
    2020: 0
    2025: 0
    2030: 60
    2035: 1000
    2040: 1000
    2045: 1000
    2050: 1000
  regional_co2_sequestration_potential:
    max_size: 2.5
```

| year | Mt/a | basis |
|---|---:|---|
| 2020, 2025 | 0 | No CO₂ storage in operation in BE, DE, FR, GB, LU or NL. Northern Lights, the one European site injecting at scale, is Norwegian and outside the model. |
| 2030 | 60 | EU Net-Zero Industry Act: **50 Mt/a of EU injection capacity by 2030**, concentrated in North Sea projects mostly inside the modelled set (Porthos, Aramis, German offshore) — take ~35. Plus the UK's **20–30 Mt/a by 2030** target — take ~25. |
| 2035 onward | 1000 | Non-binding backstop, ~5× what the stores allow. It exists only so that flipping `regional_co2_sequestration_potential.enable: false` (which sets every `e_nom_max` to `inf`) cannot silently produce an unlimited sink. |

`regional_co2_sequestration_potential` is a **partial** override — Snakemake
deep-merges configfiles, so `enable`, `attribute`, `include_onshore`, `min_size`
and `years_of_storage` still come from `config.default.yaml`. Verified by merging
both files and printing the result.

### 3.2 Resulting per-node ceilings

| node | Mt/a before | Mt/a after |
|---|---:|---:|
| GB | 1 000 | **100** |
| DE | 79.1 | 79.1 |
| NL | 9.09 | 9.09 |
| BEWAL / BEVLG / BEBRU / FR / LU | 0 | 0 |
| **total** | **1 088** | **188** |

**The Belgian zero is documented, not a `fillna`.**
`data/walloon/custom_potentials.csv` carries explicit
`co2 storage, e_nom_max, 0, Mt/a` rows for BEWAL, BEVLG and BEBRU in all four
horizons, each with its own source line: no Belgian site clears CO₂StoP's
`min_size`; the Campine basin is not quantified for this study; Brussels has no
geology. The TIMES-WAL figure of 7.1 Mt (`STORAGEMINELC` 2.3 + `STORAGEMININD`
4.8 in 2050) is an **injection** figure, not a geological potential, and was
withdrawn as a source. Guard: `test/test_co2_store_potential.py`.

**Is 188 Mt/a for six countries too generous?** Against a "share of Europe"
heuristic, yes — six countries are roughly a third of EU+UK emissions, so a share
of the 200 Mt/a convention would be ~70 Mt/a. That heuristic is the wrong test,
and rejecting it is the point: GB and DE hold most of North-West Europe's
offshore storage, so a subset containing both **should** hold more than its
population share. The binding question is the injection *rate*, and 100 Mt/a for
GB in 2050 is 2× the UK's own 2035 target — generous, defensible, and no longer
absurd.

### 3.3 Known residual weaknesses of the configuration

1. **2030 is permissive.** 60 Mt/a is defensible, but the model also has to reach
   it through the CO₂ network, so effective 2030 storage is whatever capture
   economics allow below that. If a solve builds implausible 2030 CCS, this
   number — not the geology — is the dial.
2. **`years_of_storage: 25` is untouched** and is upstream's arbitrary
   stock→rate conversion. It does real work here (it is what turns DE's 1 979 Mt
   into 79 Mt/a) and deserves its own look.
3. **Upstream is still unsourced.** `config.default.yaml` keeps 40/100/180/250
   for anyone running a non-Walloon config. Not changed on purpose: it is the
   PyPSA-Eur default and changing it would affect every config that does not
   override.
4. **`config.scen_base.yaml`, `config.scen_corrige.yaml`, `config.scen_suff.yaml`
   are not touched.** They are resolved snapshots, not the Walloon Snakemake
   overlay, and still carry the old halved series.
5. **Every `CO2 pipeline … -> GB` link is freely extendable** with
   `p_nom_max = inf`, when no such pipeline exists or is planned. A real
   modelling artefact of `co2_network: true`, worth bounding.

### 3.4 Reverting

Put back `co2_sequestration_potential: 0 / 0 / 20 / 50 / 90 / 125 / 125` and
delete the `regional_co2_sequestration_potential:` block (which restores
`max_size: 25` from `config.default.yaml`, i.e. GB back to 1 000 Mt/a).

---

## 4. What the model actually does

### 4.1 The Walloon cap binds exactly, in every horizon [V]

Measured BEWAL atmosphere emissions excluding aviation equal
`co2_limit_per_countryBEWAL` to floating point in all four horizons:

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| BEWAL cap (kt) | 21,602 | 15,001 | 8,334 | 1,667 |
| Realised, ex-aviation (kt) | 21,602 | 15,001 | 8,334 | 1,667 |
| **slack (kt)** | **0** | **0** | **0** | **0** |
| aviation, excluded from the cap (kt) | 2,145 | 2,169 | 2,212 | 2,230 |
| CO₂ captured at BEWAL (kt) | 855 | 6,564 | 9,696 | 10,563 |
| BEWAL gas use (TWh) | 39.3 | **45.7** | **45.1** | 31.1 |

Wallonia's modelled emissions are therefore **not an economic outcome — they are
the cap**. The model never over-achieves, in any horizon. By 2050 it captures
**6.3× its entire emissions allowance**.

### 4.2 Gas use rises, then barely falls [V]

BEWAL gas consumption is +16 % in 2030 and still +15 % in 2040 against 2025; only
2050 falls (−21 %). The 2040 carrier split shows why:

| BEWAL 2040, gas in | TWh | atmosphere (kt) |
|---|---:|---:|
| **CCGT (unabated)** | **19.8** | **3,917** |
| gas for industry CC | 7.7 | 149 |
| CCGT CC | 7.7 | 76 |
| urban decentral gas boiler | 3.5 | 700 |
| rural gas boiler | 3.5 | 698 |

**Unabated CCGT is Wallonia's single largest emitter in 2040** — larger than
aviation — burning 2.6× more gas than the capture-fitted CCGT. The system
decarbonises by capturing, not by burning less.

### 4.3 Wallonia is a CO₂ transit corridor, not only an exporter [V]

Because the Walloon sink is zero, every tonne captured in Wallonia leaves it by
`CO2 pipeline`: 2.2 / 6.1 / 8.8 / 9.6 Mt a year to DE, FR and LU — 41 % of the
whole BEWAL national CO₂ cap in 2030 and 106 % of it in 2040. **Label this
wherever capture is published**: it is the largest physical assumption under the
Walloon decarbonisation path, and it is an assumption about Germany, not about
Wallonia.

But the flow is not only Walloon. 2040 flows on `BEWAL co2 stored` (kt/a):

```
OUT  BEWAL→DE-2030 16,163 | BEWAL→DE-2025  238 | BEWAL→FR-2040 −793 | BEWAL→LU-2025 −830   Σ 14,778
IN   BEVLG→BEWAL-2030 5,343 | BEBRU→BEWAL-2030 333 | BEVLG→BEWAL-2025 −594               Σ  5,082
NET  9,696  ==  BEWAL capture
```

Of the 16.16 Mt/a crossing to Germany, **only 9.70 Mt is Walloon**; 5.68 Mt is
Flemish and Brussels CO₂ in transit. `CO2 pipeline BEWAL -> DE-2030` runs at its
fixed `p_nom` of 1,845 t/h in **all 8,760 hours**. This is decisive for the export
cap design (§10.2): a cap on the physical pipe would throttle Flanders, which has
no alternative CO₂ route in the topology.

### 4.4 The CO₂ network is the electricity network [V]

`create_network_topology`
([`prepare_sector_network.py:375-427`](../scripts/prepare_sector_network.py:375))
builds the CO₂ graph from the existing AC lines and DC links, so the export route
is the ALEGrO Belgium–Germany HVDC corridor (280.85 km, `underwater_fraction` 0)
priced with the **onshore** pipeline row. There is **no liquefaction, no shipping
and no terminal anywhere in the model**. Flanders, which has Antwerp, ships its
CO₂ *inland* to Wallonia and thence to Germany. The pipeline carries no route,
permit, tariff or acceptance constraint.

### 4.5 German and Dutch storage is saturated [V]

`DE co2 sequestered` sits at `e_nom_opt == e_nom_max` (79.1 Mt) in 2040; NL
likewise (9.1 Mt); GB has headroom (45.6 of 100). Belgian nodes are 0 in every
horizon. Per-vintage accumulation makes this worse than it looks — see §5.2.

---

## 5. What disposal actually costs

### 5.1 The LP pays the parameter *plus* a scarcity rent [V]

The 30 EUR/t `co2_sequestration_cost` parameter is only the floor; the
**geological scarcity rent** of the binding DE/NL stores stacks on top. Read the
bus marginal price, never the config value. Measured on `BEWAL co2 stored`:

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| **What the LP actually pays (EUR/t)** | **392.9** | **86.5** | **57.7** | **78.1** |
| of which store parameter | 30 | 30 | 30 | 30 |
| of which DE/NL scarcity rent | 425.5 | 49.1 | 21.7 | 42.3 |
| of which BEWAL→DE pipeline | −62.6 | 7.4 | 6.0 | 5.8 |
| reference transport-and-storage chain (EUR/t) | — | — | **82** | **74** |

Against a realistic reference chain (onshore collection plus a ship-or-pay
downstream tariff), the gap is therefore **confined to 2040** (57.7 vs 82,
−30 %); **2050 already exceeds it** (78.1 vs 74). A flat 82 EUR/t would
*overshoot* 2050.

The units are sound: the `co2 sequestered` store has no outflow and is
non-cyclic, so `e_nom_opt` equals annual tonnes and 30 EUR/t is genuinely a
per-tonne-per-year flow cost, dimensionally comparable to a ship-or-pay tariff.

### 5.2 Two structural under-pricings

Both are worth more than the parameter.

1. **Myopic capital amnesia [V].**
   [`add_brownfield.py:71-116`](../scripts/add_brownfield.py:71) carries prior
   store vintages forward non-extendable, so their capital lands in
   `objective_constant` and never enters the optimisation. The *average* charged
   cost falls **30 → 20.7 → 14.8 EUR/t** across 2030/2040/2050. CCS gets
   progressively free along the pathway.

2. **The geological ceiling is applied per vintage, not to the total [V].**
   [`prepare_sector_network.py:831-855`](../scripts/prepare_sector_network.py:831)
   writes the CO₂StoP annual ceiling onto *each* horizon's new store vintage,
   while `add_brownfield` accumulates them on the same bus:

   | node | installed 2040 | installed 2050 | single-vintage ceiling | 2050 overshoot |
   |---|---:|---:|---:|---:|
   | DE | 130.1 | **209.2** | 79.1 | **2.64×** |
   | NL | 18.2 | **27.3** | 9.1 | **3.00×** |
   | GB | 45.6 | **145.6** | 100.0 | 1.46× |

   The `co2_sequestration_limit` backstop is deliberately slack (1 000 Mt from
   2035, §3.1), so nothing catches this. **A reservoir sized for 79 Mt/a is being
   drained at 209 Mt/a.** Fixing it raises the scarcity rent — and therefore the
   Walloon disposal price — *endogenously*, without touching
   `co2_sequestration_cost` and with a far better justification than picking a
   tariff. **Fix this before, or instead of, the cost parameter; doing both
   double-counts.**

   **Fixed 2026-09-22** — `scripts/walloon_scripts/sequestration_bounds.py`,
   called from `add_brownfield`. Mechanism and ordering constraint in §10.4.

---

## 6. Emission targets: TIMES vs PyPSA

### 6.1 The two models use different 1990 references

The same headline percentage means different tonnages. PyPSA's reference is
recoverable from the solved cap; TIMES's is inferred from two independent points
of its own stated slope, and the two inferences agree to 0.8 % [I]:

| | kt |
|---|---:|
| PyPSA BEWAL 1990 reference `co2_totals_adm`, national sectors | **33,337** [V] |
| TIMES-WAL implied by −55 % @2030 | 45,780 [I] |
| TIMES-WAL implied by −95 % @2050 | 45,421 [I] |
| **TIMES-WAL reference (mean)** | **≈45,600** [I] |
| **PyPSA reference vs TIMES** | **−26.9 %** |

PyPSA's reference is a **population split of the Belgian 1990 inventory applied
uniformly to every sector** (`resources/walloon-model/co2_totals_adm_*.csv`:
BEBRU/BEVLG/BEWAL ≈ 10 / 58 / 32 % in *every* column). That is not Wallonia's
1990 profile — Wallonia carried the Belgian steel industry, so its industrial
share was well above its population share. International navigation (4.3 Mt of
population-split maritime bunkers allocated to a landlocked region) *is* excluded
from the cap, along with aviation and waste; the remaining nine sectors sum to
exactly the 33,337 kt above.

**This has to be settled before any "−X % for Wallonia" number is published.**
A −90 % 2040 target means **3,334 kt** on PyPSA's reference — a 60 % cut from the
current 8,334 — versus **4,560 kt** on TIMES's. Quoting a single percentage
across both models would be indefensible.

### 6.2 Trajectories, each against its own reference

| | PyPSA kt | % of its 1990 | TIMES kt | % of its 1990 | PyPSA − TIMES |
|---|---:|---:|---:|---:|---:|
| 2025 | 21,602 | 64.8 % | 23,856 | 52.3 % | −2,254 |
| 2030 | 15,002 | 45.0 % | 20,601 | 45.2 % | −5,599 |
| **2040** | **8,334** | **25.0 %** | **6,191** | **13.6 %** | **+2,143** |
| 2050 | 1,667 | 5.0 % | 2,271 | 5.0 % | −604 |

### 6.3 Capture volumes, both models (kt/a)

| | 2035 | 2040 | 2045 | 2050 |
|---|---:|---:|---:|---:|
| TIMES-WAL total | 7,692 | 8,298 | 8,272 | 7,825 |
| — of which electricity | 3,517 | 3,195 | 3,105 | 2,973 |
| — of which industry | 4,175 | 5,103 | 5,167 | 4,852 |
| PyPSA-WAL BEWAL total | — | 9,696 | — | 10,563 |
| — of which power/CHP (`CCGT CC`, `gas CHP CC`) | — | 1,440 | — | 3,707 |
| — of which industry (3 CC carriers) | — | 8,256 | — | 6,855 |

1. **The two models agree on the magnitude of CCS** (≈8 Mt TIMES vs 9.7–10.6 Mt
   PyPSA). Heavy capture is **not** a PyPSA artefact — TIMES captures 74–78 % of
   its gross electricity+industry CO₂ by 2050. Presenting CCS as a PyPSA
   modelling quirk would be wrong.
2. **They disagree on where.** TIMES captures ~2× more on *power* (it retrofits
   Flémalle + Seraing, 1.74 GW, from 2035 — see
   [`ccs_alignment.md`](ccs_alignment.md) §1); PyPSA captures ~60 % more on
   *industry* and only reaches TIMES-like power capture in 2050. The split, not
   the total, is the real divergence.

### 6.4 2040 is where the models part company — and the reason is instrument design

TIMES reaches **−86.4 %** at 2040 unforced, driven by its exogenous carbon price.
PyPSA stops at exactly **−75.0 %**, because a cap is a ceiling and cheap
compliance makes the cheapest feasible point *the cap itself*.

So the claim that "the model never goes beyond −75 % in 2040 because nothing
obliges it to" is **true of PyPSA and false of TIMES**: TIMES's own indicator
CSVs put 2040 at 6,191 kt = −86.4 %, only 3.6 points short of −90 %. The two
models sit in very different places relative to a 2040 target, and the gap is an
artefact of cap-versus-price, not of ambition. In PyPSA-WAL
`co2_price_national: false` and the cap *is* the instrument — it does 100 % of the
work and the model never over-achieves. **Any TIMES-side conclusion about
"bound versus price" must be re-derived on the PyPSA side before it is quoted as
a joint finding.**

---

## 7. What is actually blocking abatement

### 7.1 The Walloon carbon price is a stack, not a single dual [V]

`co2_limit_per_countryBEWAL` is stacked *on top of* the global `CO2Limit` over the
same emissions, so a Walloon emitter pays both. Reading the national increment
alone as "the carbon price" is a mistake this review made once:

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| global `CO2Limit` μ | 76.8 | 95.0 | 119.1 | 466.5 |
| BEWAL national μ | 378.7 | 91.4 | 22.3 | 11.3 |
| **effective BEWAL carbon price** | **455.5** | **186.4** | **141.3** | **477.8** |

The Walloon marginal abatement cost is **highest in 2050**, not lowest. A small
national increment means Wallonia's marginal option is priced close to Europe's,
not that abatement is cheap.

### 7.2 Cheap non-CCS abatement is *not* exhausted — solar is throttled by a soft-link pin [V]

2040 extendable vintages at BEWAL:

| | `p_nom_opt` | `p_nom_max` | used |
|---|---:|---:|---:|
| `BEWAL 0 solar rooftop-2040` | 5,351 MW | 43,442 MW | **12.3 %** |
| `BEWAL 0 solar-hsat-2040` | 2,269 MW | 37,842 MW | **6.0 %** |
| `BEWAL 0 solar-2040` | 0.0 MW | 12,618 MW | **0 %** |

Build-rate is not binding either (5,549 MW of slack against the
`res_build_rates.csv` allowance). What binds is the **TIMES rooftop-share pin**
(`named_pins.add_rooftop_share_constraint`), to six decimals: realised share
0.690491 (2040) and 0.705985 (2050), equal to the TIMES targets exactly.

`solar-hsat` earns **+4,790 EUR/MW/a** yet stops at 6 % of potential, because each
MW of it drags 2.23 MW of rooftop (margin **−4,978 EUR/MW/a**) along. The bundle
needs only about **+5.6 EUR/t** of carbon price to clear. Onshore wind *is* at its
6,500 MW ceiling, and gas boilers (7.1 TWh, 1,398 kt in 2040) face heat pumps with
`p_nom_max = inf` — a second uncapped margin.

**Consequence:** tightening the cap would move **solar first, heat pumps second,
capture third**. But the model's cheapest decarbonisation option is currently
suppressed by a *TIMES composition assumption*, not by Walloon physics, so a 2040
result would partly be measuring the rooftop pin. **The pin deserves its own
sensitivity run before any 2040 target is set** (§10, lever E).

> **Resolved 2026-09-22, and not by a sensitivity run.** The share pin was
> replaced by an absolute rooftop *floor* and `solar-hsat` was removed, so the
> bundle described above no longer exists: rooftop is pinned to the TIMES
> capacity and ground-mounted PV is free. Every number in this section is a
> measurement of the **superseded** configuration and must not be quoted as
> current. §10.4.

### 7.3 What can and cannot cause infeasibility [V]

**Changing a cost coefficient cannot make an LP infeasible** — the feasible region
depends on the constraint matrix and RHS only. Raising CCS cost is safe by
construction. *Tightening the cap* is what can fail, and this model has no escape
hatches: `co2_vent: false`, `load_shedding: false`, DAC absent, Walloon storage 0,
and `import_limit_BEWAL` binding at 6.47 TWh (μ = −9.04 EUR/MWh).

### 7.4 Why the marginal Walloon investment is CCGT-CC and not more PV + battery [V]

A natural reading of §4.2 is that the model "prefers" a gas-plus-capture pathway
to a solar-plus-storage one. It does not prefer either: **in an LP optimum every
extendable asset that is built earns exactly its annualised capex**, so nothing
built is more profitable than anything else built. The real question is what
stops *more* PV + battery, and the duals answer it in three parts.

**Everything built sits at 100.0 %.** Realised margin against annualised capex
for the BEWAL extendable vintages — note the stacked carbon price of §7.1 must be
used, because the national cap does **not** price through the `co2 atmosphere`
bus and omitting it makes gas look 25 % more profitable than it is:

| BEWAL vintage | built | margin ÷ capex |
|---|---:|---:|
| `CCGT-2040` (unabated) | 3 225 MW_gas | **100.0 %** |
| `CCGT CC-2040` | 1 239 MW_gas | **100.0 %** |
| `CCGT-2050` (unabated) | **0** | builds nothing new |
| `CCGT CC-2050` | 2 521 MW_gas | **100.0 %** |

So CCGT-CC is simply the marginal capacity investment. By 2050 unabated CCGT is
no longer built at all: at a stacked carbon price of **477.8 EUR/t** it carries
**157.68 EUR/MWh_e** of carbon cost against CCGT-CC's **33.43** (8.14 residual
emission + 25.29 disposal). Note CCGT-CC is *not* paid to capture — it pays
25.29 EUR/MWh_e to dispose; it simply pays far less than an unabated plant pays
to emit. At 2040 the gap is much narrower (47.43 vs 21.46) and both technologies
coexist at the margin.

**Part 1 — solar is capped administratively, not out-competed.** Free-dispatch
capex recovery at BEWAL 2050, with curtailment measured at **0.0 %** so realised
equals free dispatch:

| | `p_nom_opt` | `p_nom_max` | recovery | reading |
|---|---:|---:|---:|---|
| `solar-hsat` | 3 753 MW | 35 586 MW | **101.3 %** | wants to build — held back |
| `solar rooftop` | 9 012 MW | 39 073 MW | **94.1 %** | forced above its economic level |
| `solar` (utility) | 0 MW | 13 000 MW | 97.6 % | not built |
| `onwind` | 6 500 MW | at ceiling | 105.5 % | wants to build — no potential left |

A recovery above 100 % on an asset with resource headroom is the signature of a
*binding side constraint*, and here it is the TIMES rooftop-share pin (§7.2):
rooftop ≥ 0.705985 × solar-all forces **2.401 MW of rooftop per MW of hsat**.

| | EUR/MW/a | 2040 | 2050 |
|---|---|---:|---:|
| hsat net margin | alone | +4 790 | +800 |
| rooftop net margin × k | k = 2.231 / 2.401 | −11 107 | −8 185 |
| **bundle** | | **−6 317** | **−7 385** |

The bundle is the only thing the optimiser may buy, and it loses money. **Remove
the pin and Walloon solar expands before any more gas-with-capture is built.**

**Part 2 — cannibalisation.** Even unpinned, solar's revenue per MWh is poor
because it produces when prices are low. Capture price against a time-weighted
mean of **92.95 EUR/MWh** (2050):

| | capture price | % of mean |
|---|---:|---:|
| `solar-hsat` | 54.48 | **58.6 %** |
| `solar rooftop` | 56.33 | **60.6 %** |
| `onwind` | 70.40 | 75.7 % |
| **`CCGT CC`** | **143.89** | **154.8 %** |
| `CCGT` (brownfield peaker) | 232.05 | 249.6 % |

CCGT-CC earns **2.6× more per MWh than solar** on the same bus. The price
duration explains it: p1 = 2, p10 = 5 EUR/MWh — deep midday troughs solar itself
creates — against 1 399 hours above 150 and **zero hours above 300**. There is no
scarcity-price spike to monetise; it is a broad winter premium.

**Part 3 — the battery is already at its optimal size, and cannot grow into the
role.** Perfect-foresight price-taker arbitrage against the 2050 BEWAL price
series, per MW of charge/discharge, η_rt 0.960:

| duration | arbitrage value | capex | recovery |
|---:|---:|---:|---:|
| 2 h | 21 961 | 29 391 | 74.7 % |
| 4 h | 42 539 | 46 372 | 91.7 % |
| **8 h** | **80 227** | **80 335** | **99.9 %** |
| 12 h | 111 108 | 114 298 | 97.2 % |
| 24 h | 165 815 | 216 187 | 76.7 % |
| 168 h (1 week) | 341 121 | 1 438 851 | 23.7 % |
| 720 h (1 month) | 398 071 | 6 125 729 | 6.5 % |
| 2 190 h (1 season) | 413 117 | 18 607 089 | 2.2 % |

The optimum is **8 h at 99.9 %**, and the solve independently built **9.0 h**
(6 517 MWh on 724 MW). Arbitrage value **saturates at ~413 kEUR/MW/a** however
much energy is added — the price series contains no more spread to harvest —
while capex rises linearly. Seasonal storage is **45× away from paying**.

**Why that matters: the gap CCGT-CC fills is seasonal, and a battery shifts hours,
not months.**

| BEWAL 2050 | winter (Nov–Feb) | summer (May–Aug) |
|---|---:|---:|
| solar capacity factor | **3.7 %** | **17.4 %** (4.67×) |
| `CCGT CC` capacity factor | **70.5 %** | 46.3 % |
| λ_el, EUR/MWh | **143.9** | 69.8 |

Walloon solar delivers **10.5 % of its annual output in the four months carrying
2.1× the summer price**. `CCGT CC` delivers 4.41 of its 9.17 TWh in exactly those
months. Replacing that winter block with stored summer solar would need **411×
the installed Walloon battery energy** (4.41 TWh against 10.7 GWh across every
vintage).

**Summary.** CCGT-CC wins the marginal slot because (i) at a 477.8 EUR/t stacked
carbon price it is the cheapest *firm winter* MWh once capture cuts its carbon
bill from 157.68 to 33.43 EUR/MWh_e; (ii) its competitor on energy is pinned by a
soft-link assumption rather than by cost; and (iii) the storage that would let
solar compete on firmness is at its economic optimum at 8–9 h and is two orders of
magnitude short of the seasonal duration required. **Only (ii) is a modelling
choice** — (i) and (iii) are the physics of Walloon insolation and a high carbon
price. That makes the rooftop-pin sensitivity (§10, lever E) the single most
informative test of this result.

---

## 8. Carbon recycling: power-to-fuel and synthetic kerosene

### 8.1 Nothing is built, anywhere, in any horizon [V]

System-wide, not just at BEWAL:

| route | 2030 | 2040 | 2050 | in Wallonia |
|---|---:|---:|---:|---|
| **H2 Electrolysis** | **0 MW** | **0 MW** | **0 MW** | 0 |
| **Fischer-Tropsch** | **0 MW** | **0 MW** | **0 MW** | 0 |
| methanolisation | 9.4 TWh | 5.9 TWh | 24.4 TWh | **0** |
| Sabatier | 0.66 TWh | 0.66 TWh | 0 | 0 |
| biomass-to-methanol | 0 | 15.3 TWh | 0 | 0 |

Both `H2 Electrolysis` and `Fischer-Tropsch` are **present and extendable** (8
extendable links per horizon) — the optimiser builds zero of each, everywhere,
always. This is an economic verdict, not a config exclusion.

**All hydrogen is reformed fossil gas** [V]: 2040 `SMR` 76.0 TWh (unabated); 2050
`SMR CC` 111.9 TWh. The methanol that *is* produced runs on that fossil hydrogen —
a gas-to-fuel route, not a power-to-fuel route. **Wallonia has zero power-to-fuel
capacity of any kind in any horizon.**

### 8.2 Why electrolysis is never built [V]

The proximate cause is the price spread: 2040 BEWAL electricity **99.52** EUR/MWh
against gas **32.20** EUR/MWh — 3.1:1, against an electrolyser at 65.3 %
efficiency. Reduced-cost test against the solved duals (validated: `GB SMR
CC-2050` comes out 0.08 % from break-even, exactly as the marginal built asset
should):

| | BEWAL | GB | DE | FR |
|---|---:|---:|---:|---:|
| **2040** capex recovery at free dispatch | 29.6 % | 42.8 % | 46.8 % | 35.7 % |
| **2040** Δλ_el needed (EUR/MWh) | **−52.7** | −35.3 | −37.3 | −37.6 |
| **2050** capex recovery | 62.3 % | 74.6 % | 72.6 % | 77.6 % |
| **2050** Δλ_el needed (EUR/MWh) | **−16.5** | −10.6 | −12.7 | −8.9 |

2040 needs Walloon power to fall **53 %** (99.5 → 46.8 EUR/MWh); 2050 needs only
−18 %. Optimal chosen utilisation is 1,804–2,555 h (2040) and 3,379–3,896 h
(2050), so even a 4,000 FLH assumption flatters the electrolyser. Break-even gas
price in 2040 is ~102 EUR/MWh against 32.20 — a **3.2× gas price**.

**Where the H₂ price comes from matters more than its level.** In 2040 λ_H2 is
set by the **sunk, unabated `GB SMR-2025` fleet** (operating margin
+0.03 EUR/MWh, i.e. zero rent). In 2050 it is set by `GB SMR CC-2050` at full
cost. And the 76 TWh of 2040 SMR hydrogen sits in **DE and GB — precisely the two
countries whose national CO₂ cap is slack** (duals −0.0 and +1e-8). SMR therefore
pays the global 119.06 EUR/t, not the 141.3 a Walloon emitter faces.

### 8.3 Why Fischer-Tropsch is never built [V]

An intuition that FT competes with sequestration for carbon, and therefore bears
the CO₂ shadow price as an opportunity cost, is **false**. λ(`co2 stored`) is
*negative* everywhere — it is a disposal cost, not a resource rent:

| λ(co2 stored), EUR/t | GB | DE | BEWAL | FR |
|---|---:|---:|---:|---:|
| 2040 | −30.10 | −51.68 | −57.65 | −68.14 |
| 2050 | −50.53 | −72.35 | −78.15 | −88.58 |

**FT is *paid* 7.7–22.8 EUR/MWh_oil to take carbon away.** The carbon accounting
is symmetric (§8.4), so no net carbon term appears either way.

**The real blocker is the value of the output.** `EU oil primary` is an
extendable generator at 63.44 (2040) / 80.13 (2050) EUR/MWh, giving λ(`EU oil`) =
68.46 / 90.80. FT's delivered cost is ~119 (GB 2040) and ~116–118 (2050):

> **In GB 2050 the hydrogen input alone (108.6 EUR/MWh_oil) exceeds the entire
> output value (90.80).** That is the blocker in one line.

Free-dispatch capex recovery is **0.0 % in 2040 everywhere**, 12–40 % in 2050. Oil
would have to reach ~110–120 EUR/MWh — and that understates it, because a higher
oil price pulls λ_H2 up too.

**`min_part_load_fischer_tropsch: 0.5` is not inert.** It is written as `p_min_pu`
on an *extendable* Link with no unit commitment anywhere in the network
(`n.links.committable.sum() == 0`, verified), so it is a pure LP must-run:
`p_t ≥ 0.5·p_nom` in **every** snapshot. It does not make FT unbuildable, but it
forces production through negative-margin hours:

| gross margin, EUR/MW_H2/yr | free dispatch | with `p_min_pu = 0.5` |
|---|---:|---:|
| GB 2040 | +14,285 | **−24,745** |
| BEWAL 2050 | +25,287 | **−543** |
| GB 2050 | +20,408 | **−8,712** |
| FR 2050 | +56,111 | +37,983 |

Outside France this wipes out **100 %+ of FT's entire gross margin**. It is a
unit-commitment proxy misapplied to a capacity-expansion LP: second-order against
the cost gap, but a genuine artefact and a one-key fix.

### 8.4 The e-kerosene route **does** exist — via Fischer-Tropsch [V]

It is sometimes stated that this model has "no route to synthetic kerosene at
all". **That is not correct**, and the distinction matters for what to fix. The
route is instantiated and extendable in every horizon; it is simply never used.
Verified wiring in `base_s_adm___2050.nc`:

```
                     Fischer-Tropsch                  kerosene for aviation
   BEWAL H2  ────────────────────────►  EU oil  ────────────────────────►  kerosene ──► Load
                    │ bus2                               │ bus2
                    ▼                                    ▼
             BEWAL co2 stored                      co2 atmosphere
          −0.2571 tCO₂ per MWh_oil              +0.2571 tCO₂ per MWh_oil
```

`Fischer-Tropsch` (24 links, 8 extendable per horizon) delivers into the single
`EU oil` bus, and `kerosene for aviation` draws from that same bus. So building
FT *does* decarbonise aviation in this model's accounting. Three facts explain why
it delivers nothing, and only the third is a genuine structural gap:

1. **Economics, not availability.** FT is never built (§8.3), so `EU oil` is fed
   by `oil refining` alone — 1 250 TWh in 2040, 618 TWh in 2050, 100 % fossil,
   with `Fischer-Tropsch` and `biomass to liquid` both at 0.000 TWh [V].
2. **The carbon terms cancel exactly.** FT draws **0.2571 tCO₂/MWh_oil** from
   `co2 stored` and combustion returns exactly **0.2571 tCO₂/MWh_oil** to the
   atmosphere. A tonne of carbon can be **buried *or* recycled into fuel, never
   both** — both give the same −1 t. This is the price-side expression of the
   2050 net-zero result: with `sector.dac: false` the only non-fossil carbon
   entering `co2 stored` is biogenic and capped at ~127 Mt, against ~230 Mt of
   realised fossil combustion of which **aviation kerosene alone is 106 Mt**.
   Building FT does not change that arithmetic, so **it cannot close the net-zero
   gap; only DAC or lower exogenous aviation demand can.**
3. **There is no synthetic-fuel *product*.** `EU oil` is one pooled bus, so a
   synthetic MWh is indistinguishable from a fossil one. There is consequently no
   place to attach an e-SAF blending mandate and no way for synthetic oil to earn
   a price premium. **This is the real missing piece** — not the FT route.

`methanol_to_kerosene: false` (`config.default.yaml:970`) and `electrobiofuels:
false` (`config.walloon.yaml:617`, vs `true` upstream) remove **additional**
routes, not the only one. Flipping them on is cheap but should not be expected to
produce a result: methanol-to-kerosene also eats hydrogen and methanol costs
85.9 / 107.4 EUR/MWh against oil at 68.5 / 90.8; electrobiofuels is futile while
the `biomass limit` dual is −1,223 EUR/MWh in 2050 — the same dual that holds
`biomass to liquid` at 0 MW on all 24 links.

**Reporting consequence.** Aviation is currently exogenously fossil: BEWAL
aviation kerosene is 8.60 TWh / **2,212 kt** in 2040 (system-wide 106.14 Mt), the
demand is an exogenous `Load` identical in 2040 and 2050 with no demand response,
and in 2050 aviation is **67 % of all remaining oil demand** (412.9 of
617.8 TWh). Either the model gains a usable synthetic-kerosene route (a mandate
plus cheaper hydrogen, §10 lever G) or **every published Walloon 2050 figure must
state that aviation is exogenously fossil.**

### 8.5 Fossil carbon is unpriced at extraction [V]

`EU oil primary` carries **no** carbon charge; CO₂ is booked only at combustion,
**identically for fossil and synthetic oil**. This is the structural reason
behind §8.4 point 3: synthetic oil can never earn a carbon premium at the `EU
oil` bus, no matter how the carbon price moves. Short of separate
fossil/synthetic oil accounting (a code change) or a mandate, power-to-liquids
cannot win on price in this model's structure.

### 8.6 What a sequestration levy does to hydrogen, and to Fischer-Tropsch [V]

A levy on `co2_sequestration_cost` reaches Fischer-Tropsch through **two opposite
channels**, and which one dominates depends entirely on **which technology is
marginal on the `H2` bus**. Getting that wrong inverts the conclusion, so the
regimes are separated here. Every figure below is reproducible with
`scripts/walloon_scripts/levy_h2_ft_sensitivity.py` (validated: it returns the
§8.2 electrolyser recoveries and dispatch hours exactly).

**The mechanism.** `SMR CC` efficiency3 0.1782 ÷ η 0.69 = **0.2583 tCO₂/MWh_H2**.
While SMR CC sets λ_H2, a levy Δ raises hydrogen by 0.2583 Δ. FT needs
1.326 MWh_H2 per MWh_oil, so its input cost rises 0.3425 Δ per MWh_oil, while its
carbon credit — it draws 0.2571 tCO₂/MWh_oil off `co2 stored` (§8.4) — rises only
0.2571 Δ. **SMR CC buries more carbon per MWh_oil-equivalent than FT recycles, and
that gap is the whole effect.** But it only exists while SMR CC is marginal.

| regime | what sets λ_H2 | λ_H2 per EUR/t | FT margin per EUR/t |
|---|---|---:|---:|
| **2040, any levy** | sunk unabated `GB SMR-2025` | **0.0000** | **+0.2571** EUR/MWh_oil |
| **2050, ≤ 79 EUR/t** | `SMR CC` at full cost | +0.2583 | **−0.0854** EUR/MWh_oil |
| **2050, > 79 EUR/t** | `H2 Electrolysis` (capped) | **0.0000** | **+0.2571** EUR/MWh_oil |

**2040 — the levy is inert on hydrogen and mildly *helps* FT.** λ_H2 is set by a
sunk, unabated SMR fleet that sequesters nothing, so the pass-through is exactly
zero and **electrolyser recovery is frozen at 29.6 / 35.7 / 42.8 / 46.8 %
(BEWAL / FR / GB / DE) at every levy from 30 to 230 EUR/t** — verified, the
numbers do not move at all. What the levy does do at 2040 is push `SMR CC`
further out of the money (GB recovery 91.6 % → 12.8 % at 82 EUR/t), which changes
nothing because SMR CC is not the price-setter. FT's credit does still rise, so
FT recovery goes 0.0 % → 4.7 % (FR) at 82 EUR/t and 12.6 % at 100. The
*direction* is positive; the magnitude is irrelevant. (An earlier reading of
"exactly zero effect at 2040" is right about hydrogen and wrong about FT.)

**2050 below ~79 EUR/t — SMR CC marginal, FT gets worse.** Electrolyser capex
recovery: FR 77.6 → **101.3 %**, GB 74.6 → **97.0 %**, DE 72.6 → 92.5 %, BEWAL
62.3 → 82.7 % at 82 EUR/t. FT falls: GB 14.5 → 9.4 %, BEWAL 17.9 → 13.2 %.

**2050 above ~79 EUR/t — electrolysis becomes marginal and the sign flips.** This
is what the levy was supposed to achieve, and it is self-limiting: once green
hydrogen is the marginal supplier, λ_H2 **stops tracking the levy** and is capped
at the electrolytic cost. Crossover levies, i.e. where each node's electrolyser
reaches 100 % capex recovery:

| node | crossover `co2_sequestration_cost` | λ_H2 at crossover |
|---|---:|---:|
| **FR** | **79.2 EUR/t** | 95.78 EUR/MWh |
| GB | 88.4 EUR/t | 96.98 EUR/MWh |
| DE | 100.0 EUR/t | 104.40 EUR/MWh |
| BEWAL | 121.6 EUR/t | 109.65 EUR/MWh |

FR crosses first, and the H2 pipeline network carries that cap to the other nodes
— the 2050 graph is connected (FR↔BEWAL 759 MW, FR↔GB 11.5 GW on the 2025
vintage, DE↔GB 5.4 GW), though only up to those capacities, so a thin link can
let a nodal price separate above the cap. **The 82 EUR/t figure under discussion
sits just past that crossover**, so
extrapolating the regime-A slope to 82 is not valid: FT's worst point is at
~79 EUR/t, not at the top of the range. Above it FT's input cost is frozen while
its carbon credit keeps rising, at **+0.2571 EUR/MWh_oil per EUR/t**:

| `co2_sequestration_cost` | FT BEWAL | FT FR | FT GB | FT DE | regime |
|---:|---:|---:|---:|---:|---|
| 30 | 17.9 % | 39.8 % | 14.5 % | 12.0 % | A |
| 60 | 14.9 % | 35.5 % | 11.5 % | 9.3 % | A |
| **79** | **13.4 %** | **33.3 %** | **9.6 %** | **7.9 %** | A — the minimum |
| 82 | 14.0 % | 34.2 % | 10.4 % | 8.5 % | B |
| 100 | 19.7 % | 42.1 % | 15.9 % | 13.7 % | B |
| 180 | 84.6 % | 116.8 % | 77.7 % | 75.9 % | B |

**It still is not enough to build FT.** Break-even arrives only at **165 EUR/t
(FR), 194 (BEWAL), 200 (GB), 202 (DE)** — 2–2.5× the figure under discussion, and
that is a partial-equilibrium extrapolation holding λ_oil and the scarcity rent
fixed. Nothing here changes §10.1's ranking.

**Two caveats on the regime-B result.**

1. **The model has no green/grey hydrogen distinction.** There is one `H2` bus
   per node, and FT pays λ_H2 whatever produced it. "Run FT on green hydrogen" is
   therefore not a choice the optimiser can make — it is a *consequence* of which
   technology happens to set λ_H2. This is the same structural gap as the pooled
   `EU oil` bus in §8.4: with no separate product there is no way to mandate,
   certify or reward a green input, in either direction of the chain.
2. **The scarcity rent moves too, but the exposure is bounded [V].** If
   electrolysis displaces SMR CC, the sequestration demand it was creating
   disappears and the DE/NL rent inside λ(`co2 stored`) — 42.3 of BEWAL's
   78.1 EUR/t in 2050 (§5.1) — softens, which would claw back part of FT's
   credit. The exposure is small: SMR CC is only **28.9 of 382.1 Mt/a (7.6 %)** of
   the 2050 flow onto `co2 stored`, against urban central gas CHP CC 142.5,
   `solid biomass for industry CC` 96.6, `process emissions CC` 56.4, `CCGT CC`
   41.3 and `gas for industry CC` 21.8. The rent would soften, not collapse. A
   re-solve is still required to confirm — this is a reduced-cost argument, not a
   solved result.

**Revised conclusion.** CCS pricing and power-to-fuel still need separate levers.
But "a sequestration levy works against synthetic liquids" holds only in a narrow
band — 30 to ~79 EUR/t at 2050 — and is **false at 2040 and false above the
crossover**. In every regime the levy is a weak, slow and indirect lever for
power-to-fuel; electrolyser capex and a synthetic-fuel mandate remain the only
ones with the right magnitude (§10.1).

### 8.7 One root cause, two symptoms

Walloon wind is at its ceiling and solar is pinned (§7.2), the electricity import
cap binds, so power stays at ~100 EUR/MWh; electrolysis is uneconomic; hydrogen
comes from cheap gas; the resulting CO₂ is disposed of at a rent-suppressed price
(§5); and the cap is met by capture. **Cheap gas plus under-priced carbon disposal
plus suppressed cheap renewables produces both runaway CCS *and* zero
power-to-fuel.**

This also **partly de-risks the export cap** (§10.2). The worry was that capping
exports removes the only valve, since Wallonia has no domestic sink. There is a
second, entirely unused valve — but §8.6 shows it does not open at 2040, so the
export cap must still ship with its overage tranche.

---

## 9. How far can the system-wide CO₂ cap be tightened?

`co2_budget` 2050 is **0.050** — 5 % of 1990, which is not an ambitious
end-point. A 2026-09-05 test at **0.000** returned a clean Gurobi primal
infeasibility certificate, with a control solve at 0.050 on the identical 2040
inheritance coming back feasible. This section establishes *why*, how much
headroom actually exists between the two, and — because the question naturally
arises — whether a tighter system cap could pull the power-to-fuel route into the
money by displacing fossil carbon imports. **It pushes in that direction but is
unlikely to be sufficient, and it does not move the feasibility wall at all.**

### 9.1 The two caps do not cover the same emissions [V]

The asymmetry is deliberate and is the reason the question is worth asking at
all:

| | system `CO2Limit` | national `co2_limit_per_country<ct>` |
|---|---|---|
| constraint type | `co2_atmosphere` — the whole `co2 atmosphere` store | a filtered emissions expression per region |
| aviation on the LHS | **included** | **excluded** |
| aviation in the 1990 RHS | **included** (`domestic aviation` + `international aviation`, `prepare_sector_network.py:246`) | **excluded** (`co2_budget_national_include_aviation: false`) |
| international navigation | excluded from the RHS (commented out upstream) | excluded |
| 1990 reference | **2 271 Mt** across the six countries | BEWAL 33 337 kt (§6.1) |
| 2050 value | 0.050 → **113.5 Mt**, μ = **466.5 EUR/t** | 0.050 → BEWAL 1 667 kt, μ = 11.3 EUR/t |

Aviation is out of the national caps on both sides because the authoritative
trajectory is defined *hors aviation internationale*, because international
bunkers are memo items outside national inventories and outside the Effort
Sharing Regulation, and because kerosene is drawn from the single `EU oil` bus
and cannot be attributed to a region without error. It stays in the system cap,
"where the carbon balance does close"
([`solve_network.py:1923`](../scripts/solve_network.py:1923)).

So the intuition is right on its premise: **the 106 Mt of aviation CO₂ is inside
the system cap and nowhere else.** Tightening `co2_budget` is the only instrument
in the model that puts any pressure on it at all.

### 9.2 Where the 113.5 Mt actually sits [V]

2050 flows on `co2 atmosphere`, system-wide (Mt/a; the total equals the cap to
floating point, so the system cap binds exactly, like every national one):

| emitting | Mt/a | | removing | Mt/a |
|---|---:|---|---|---:|
| **kerosene for aviation** | **106.16** | | **`solid biomass for industry CC`** | **96.61** |
| urban decentral gas boiler | 41.32 | | *(biogas-to-gas 34.17 is the biogenic* | |
| **HVC to air** | **34.69** | | *offset for methane burned elsewhere,* | |
| rural gas boiler | 9.32 | | *not a removal)* | |
| oil refining (process) | 8.46 | | | |
| urban central gas CHP CC (residual) | 7.50 | | | |
| agriculture machinery oil | 5.43 | | | |
| CCGT (unabated) | 5.08 | | | |
| 12 further carriers, each < 5 | 26.3 | | | |
| **gross** | **244.3** | | **genuine negative emissions** | **96.6** |

**Net 113.5 Mt = the cap, μ = 466.5 EUR/t.**

### 9.3 The wall is arithmetic, and it is reached well above zero [V]

**Negative emissions have essentially no headroom.** The only genuine sink is
`solid biomass for industry CC`, and the EU-wide `biomass limit` already binds at
330.92 TWh with a dual of **−1 223 EUR/MWh** (§11 standing traps). Of that,
279.54 TWh already goes through the CC link and 51.38 TWh through the plain one.
Routing *everything* through CC is not possible: at η 0.90 it would deliver
297.8 TWh against an exogenous industrial demand of 303.2 TWh. So realised BECCS
of 96.6 Mt is within a few per cent of the structural maximum, and **`sector.dac:
false` means nothing else in the network can move carbon out of the atmosphere —
verified: no link anywhere has `co2 atmosphere` as `bus0`.**

**Two exogenous demands alone exceed that ceiling:**

| | Mt/a | why it cannot fall |
|---|---:|---|
| kerosene for aviation | 106.16 | exogenous `Load`, identical in 2040 and 2050, no demand response (§8.4) |
| HVC to air | 34.69 | exogenous HVC demand; the non-sequestered share oxidises by construction |
| **sum** | **140.85** | against a **96.6 Mt** sink ceiling |

**Net zero is therefore infeasible by at least ~44 Mt (1.9 % of 1990) even if
every other fossil emission in the model were driven to zero.** That is a bound
from two inelastic loads and one binding resource, not a solver artefact, and it
explains the 0.000 certificate exactly.

**What *is* reachable.** The elastic block is real and large:

| | Mt/a | how reducible |
|---|---:|---|
| gas + oil boilers (4 carriers) | 54.90 | heat pumps have `p_nom_max = inf` (§7.2) |
| unabated CCGT + gas CHP | 8.10 | fit capture, or displace |
| land transport oil + industrial coal | 1.49 | switchable |
| **fully displaceable** | **64.49** | |
| residual slip from the CC fleet | 18.54 | only by capture rate or less fuel |
| refinery process, shipping, agriculture, industrial methanol | 20.45 | refinery falls only if oil demand does, and aviation holds it up |

Removing the fully displaceable block takes gross emissions from 244.3 to
179.8 Mt; clawing back roughly half the CC slip reaches ~170.8. Against the
96.6 Mt sink that is a floor of **~75–83 Mt, i.e. 3.3–3.7 % of 1990** — real
headroom below the current 5.0 %, but nowhere near zero. Two caveats: most of the
heating block is held by TIMES heating pins rather than by economics, and pins
get bought out rather than met when the shadow price exceeds the penalty (§11
standing traps), so part of any gain may be paid for rather than delivered.

**A tighter system cap would bite first where the cheap abatement is.** The
national caps are slack at DE (μ ≈ 2e-10), FR (−7.8e-10), GB (2.7e-10), NL
(−8.2e-10), BEVLG and BEBRU; only BEWAL (11.3) and LU (2.4) bind. Tightening
`co2_budget` therefore loads the countries with headroom, which is the opposite
of tightening `budget_national` — and, per §7.2, the first thing it would move is
Walloon solar, not capture.

### 9.4 Does FT relieve the cap by avoiding fossil carbon imports? [V]

The intuition is that the model imports a great deal of fossil carbon even in
2050, that FT avoids those imports, and that this should therefore buy room under
the cap. **The first two statements are correct; the third holds only under one
specific condition, and the condition is the whole story.**

**The governing identity.** Fossil carbon that enters the system ends up either
in the atmosphere or in geological storage, and biogenic carbon is a wash unless
it is permanently buried. So

> **net emissions = fossil carbon extracted − carbon permanently sequestered.**

FT reduces the first term by 0.2571 t per MWh_oil it supplies — exactly the
avoided import. But its carbon comes off `co2 stored`, so it reduces the **second
term by the same 0.2571 t**: that tonne is no longer buried. The two cancel.
Worked through on the actual 2050 figures, routing the entire biogenic pool into
aviation kerosene:

| | aviation emissions | BECCS buried | net aviation block |
|---|---:|---:|---:|
| today: fossil kerosene, biogenic carbon buried | +106.16 | −96.61 | **+9.55 Mt** |
| FT supplies 375.8 of 412.9 TWh from that same carbon | +9.55 (residual fossil) | 0 | **+9.55 Mt** |

Identical. This is the "sequestered *or* displace, never both" identity of §8.4
seen from the import side, and it holds with DAC enabled too — DAC helps by
enlarging the sink, not by making FT abate.

**The exception, and it is a real one.** The cancellation assumes the tonne FT
takes would otherwise have been buried. If the **sink is capacity-bound** and the
room FT frees is refilled by other capture, then the cut in fossil extraction
stands alone and FT abates the full 0.2571 t/MWh_oil. The model is in exactly
that regime — DE and NL stores sit at `e_nom_opt == e_nom_max` and λ(`co2
stored`) carries a scarcity rent (§5.1) — and **the LP already pays FT for it**:

| | BEWAL | FR | GB | DE |
|---|---:|---:|---:|---:|
| λ(`co2 stored`), EUR/t | 78.15 | 88.58 | 50.53 | 72.35 |
| **FT carbon revenue, EUR/MWh_oil** | **20.09** | **22.77** | **12.99** | **18.60** |

That revenue is material — 12–23 EUR/MWh_oil against an oil price of 90.80 — and
it *is* the avoided-import value, correctly computed in general equilibrium. It
is **78 EUR/t rather than the 466.5 EUR/t carbon price** because relieving the
sink by one tonne is worth only what the next capture option costs to fill the
room, and that option is expensive. Were the sink genuinely desperate, the rent
would approach the carbon price and FT's revenue with it.

There is one further, smaller term: FT delivers straight into `EU oil` and
bypasses `oil refining`, avoiding **0.0137 t/MWh_oil** of refinery process
emissions (`efficiency2 = 0.0130`, η 0.9494) — 8.46 Mt/a at 100 % substitution of
2050 oil demand. It is the only route by which the *carbon price itself* reaches
FT, and it is visible in the duals: λ(`EU oil`) = 84.40 + 6.39 = **90.79**
predicted against **90.80** observed (2040: 66.82 + 1.63 = 68.45 vs 68.46).

**So why is FT still not built?** Not for want of carbon revenue. Per MWh_oil at
BEWAL 2050: revenue 90.80 (oil) + 20.09 (carbon) + 1.99 (waste heat) = **112.88**
against a variable cost of **116.87** (hydrogen 114.05 + VOM 2.82) — already
negative before a **46.78 EUR/MWh_oil** annualised capex at 4 000 h. The binding
problem is the hydrogen price, not the carbon value.

**What this means for the cap.** Tightening `co2_budget` *does* push in FT's
favour, through the sink: more capture is demanded, storage gets scarcer, the
rent rises, FT is paid more. Two quantifications:

- FT break-even needs λ(`co2 stored`) ≈ **165 (FR) to 202 (DE) EUR/t**, i.e.
  2.1–2.6× today's 78.15 — the rent would have to go from 42.3 to roughly
  130–170 EUR/t.
- **The system is sitting almost exactly on the tipping point identified in
  §8.6.** BEWAL's disposal cost is 78.15 EUR/t; FR electrolysis becomes the
  marginal hydrogen supplier at **79.2 EUR/t**. Below that, a rising disposal
  cost *hurts* FT (SMR CC passes it into λ_H2 faster than FT gains it back);
  above it, λ_H2 is capped and FT gains the full +0.2571 EUR/MWh_oil per EUR/t.
  Any further sink scarcity — from a tighter cap, from lever A, or from the cost
  parameter — flips the sign of FT's response.

**But it does not move the feasibility wall.** The 140.85-vs-96.6 bound of §9.3
is derived from the identity above and is insensitive to FT: the table at the top
of this section shows the aviation block at +9.55 Mt either way. FT is a route to
**substitute** for sequestration, not to add to it. Reaching net zero still
requires enlarging the sink (`sector.dac: true`, `solid_biomass_import`) or
reducing the exogenous aviation/HVC demand.

**Net judgement.** A tighter system cap is worth testing on its own merits — it
is the only instrument that touches aviation at all, it loads the countries whose
national caps are slack, and it does push FT in the right direction once the
disposal cost clears ~79 EUR/t. It will not decarbonise aviation, and it will hit
the wall somewhere around 3.3–3.7 % of 1990. Whether the sink rent can reach
165–202 EUR/t before that wall is an empirical question that only a solve can
answer — which is what §9.5 is for, and the answer is most informative when run
*after* lever A, since fixing the per-vintage ceiling cuts storage from 382 to
188 Mt/a and is by itself the largest available increase in sink scarcity.

### 9.5 Suggested test ladder

Cheap to run, and each step is informative on its own. Fold into the §11
sequence after step 2, since the sink price is what sets the whole picture.

| step | `co2_budget` 2050 | Mt | what it tests |
|---|---|---:|---|
| a | 0.040 | 90.8 | Comfortably above the estimated floor. Does the elastic block move? Expect solar (§7.2), heat pumps, then capture. Watch the 2050 biomass dual — already −1 223 EUR/MWh. |
| b | 0.035 | 79.5 | Inside the estimated 75–83 Mt floor band. Expect a large objective jump and heating pins starting to be bought out; run `report_relaxed_profiles()`. |
| c | 0.030 | 68.1 | Below the estimate. Expected to fail or to relax pins wholesale. A *feasible* result means the elastic block is larger than §9.3 allows — worth knowing either way. |
| d | 0.000 with `sector.dac: true` | 0 | The clean structural test: net zero is unreachable only because the sink pool is capped, and DAC is the one technology that lifts that cap. It re-opens the district-heat competition documented in [`ccs_alignment.md`](ccs_alignment.md) §7, so it is a menu-alignment decision as well as a feasibility one. |

Keep `budget_national` 2050 at 0.050 throughout so the system cap is the only
thing moving — otherwise a failure is not attributable.

---

## 10. Recommended changes, in order

**Order matters: the levers are not interchangeable, and two of them
double-count if applied together.**

> **Implementation status — 2026-09-22.** **A** and **B** are implemented, and
> **E** was implemented in a stronger form than this section proposed: instead
> of a *sensitivity* on the rooftop-share pin, the share pin was **replaced** by
> an absolute rooftop-capacity floor and `solar-hsat` was removed. See §10.4.
> **C**, **D**, **F**, **G**, **H** are unchanged and untouched — in particular
> C must stay out until A has been re-measured, or the two double-count.

| # | change | why it sits here |
|---|---|---|
| **A** ✅ | **Fix the per-vintage sequestration ceiling** (§5.2) | A genuine bug, defensible without picking a tariff, and it raises the disposal price *endogenously*. Everything else is measured against this. **Done 2026-09-22**, §10.4. |
| **B** ✅ | **Fix `threshold_capacity: 0 → 10`** | Known numerical time bomb: ~1,278 near-zero components by 2040, 17-order bound spread, already tipped `scen_realiste_nobnd30` 2050 into genuine numerical failure. Requires a full chain re-run from 2025 anyway — do it now, not after. **Done 2026-09-22**, §10.4. |
| **C** ✗ | **Year-dependent `co2_sequestration_cost`** | Only *after* A, and re-measured: the residual gap may be small (§5.1). Values net of the pipeline leg already charged: 87 / 75 / 71 / 67 for 2035/40/45/50 (= all-in reference − 7.4). **Re-measured after A on 2026-09-22 (§10.4): the realised price is 88.8 EUR/t at 2040 and 319.1 at 2050 — above both these values and above the reference chain, so C would now *lower* the price. Do not apply; confirm at 1 h first.** |
| **D** | **Net CO₂ export cap at BEWAL** | The honest representation of "this infrastructure must be built and agreed with another country" (§4.3, §4.4). Design in §10.2. |
| **E** ✅ | **Rooftop-share pin sensitivity** | §7.2 — the cheapest abatement margin is currently set by a soft-link assumption. Needed before any 2040 target is credible. **Superseded 2026-09-22**: rather than measure the pin, it was replaced by an absolute rooftop floor and `solar-hsat` was dropped, so the bundle that throttled PV no longer exists. §10.4. |
| **F** | **A tighter 2040 target, as a variant** | Last. Depends on A–E to mean anything, and on settling the 1990 reference (§6.1). Not in the central scenario until then. |
| **G** | **Power-to-fuel** | Separate track — CCS levers deliver **nothing at 2040**, and at 2050 they are self-limiting: once the levy makes electrolysis marginal (~79 EUR/t) λ_H2 stops responding, and FT break-even still needs 165–202 EUR/t (§8.6). Ranked below. |
| **H** | **A low-CCS variant** | Asked 2026-09-22, answered in **§10.3**. Neither the sequestration price nor the gas price can deliver it — the first is absorbed 1:1 by the carbon dual, the second cannot reach 58–71 % of the capture. Use D + nuclear capex + the rooftop-pin release, and read C as a *cost* sensitivity. |

### 10.1 Levers for G, ranked by magnitude actually delivered [V]

Gap to close, in EUR/MW_el/yr of unrecovered electrolyser capex: 2040 BEWAL
137,752 / GB 111,849; 2050 BEWAL 61,500 / GB 41,443 / FR 36,476.

| lever | what it delivers | where |
|---|---|---|
| **Electrolyser capex** — the only price lever with enough magnitude at 2040 | Break-even needs **−50 to −70 %** at 2040, **−17 to −38 %** at 2050 | `data/walloon/custom_costs*.csv`, `electrolysis` investment row. No code change. |
| **A mandated e-SAF / synthetic-fuel share** | The only lever with enough magnitude at 2040, and the one that addresses §8.4 point 3. **No config key exists anywhere.** | Small code change — a Link branch in `BEWAL_potentials.py` or a `solve_network.py` constraint, same pattern as the 1,740 MW CCGT floor |
| **Cheaper electricity** | Needs −35 to −53 EUR/MWh (2040). Relaxing the import cap fully buys only **17–19 %** of that (dual −9.04). BEWAL onwind is pinned at 6,500 MW with a **+22,366 EUR/MW/yr** capacity rent in 2040 — the ceiling binds hard. **Nuclear is the only lever of the right order.** | `custom_potentials.csv` (`onwind`), import cap (TIMES softlink), `scen_nuctip_*` |
| **CCS cost 30 → 82** | **0 % of the gap at 2040** (λ_H2 is set by unabated SMR and does not move at any levy); 54 % (BEWAL) to >100 % (FR) at 2050, where it is also self-capping — FR electrolysis becomes marginal at 79.2 EUR/t and λ_H2 stops rising. FT: −4 pp up to 79 EUR/t, then +, break-even 165–202 EUR/t (§8.6). | `sector.co2_sequestration_cost` — one key |
| **`min_part_load_fischer_tropsch: 0`** | Restores 100 %+ of FT's 2050 gross margin. Still only 14–18 % of capex, but removes a genuine artefact for one key. | `config.default.yaml:980` |
| **`sector.dac: true`** | Prerequisite for genuinely carbon-negative synfuel — the only technology moving atmospheric carbon onto `co2 stored`, and the documented fix for the 2050 net-zero infeasibility (§8.4 point 2). | `config.walloon.yaml` |
| **`methanol_to_kerosene` / `electrobiofuels`** | **Near-zero effect** (§8.4). Cheap to flip; do not expect a result. | `config.default.yaml:970`, `config.walloon.yaml:617` |
| **Price carbon at oil extraction** | Addresses §8.5 at the root. Deepest, most invasive. | `prepare_sector_network.py` — separate fossil/synthetic oil buses |

### 10.2 Design of D — cap the *net* outflow, not the pipe

Three options were considered; only one is correct:

- *Cap the physical `BEWAL → DE` pipe* — **reject**. It carries 5.68 Mt/a of
  Flemish and Brussels transit, and BEVLG has no alternative CO₂ route in the
  topology (§4.3). A 6 Mt cap would collapse Flemish capture and silently turn
  this into a Flemish scenario. The pipe is also bidirectional, so a `p_nom` cap
  throttles imports symmetrically.
- *Cap Walloon-origin capture* — works numerically today but requires enumerating
  every capture carrier, a list that goes stale silently.
- **Cap the net cross-border outflow of the `BEWAL co2 stored` bus** —
  **recommended**. Transit cancels identically (a Flemish tonne enters + and
  leaves −), it is carrier-list-proof because it is a bus balance, signed link
  flows handle bidirectionality, and the cap is in annual tonnes so the hourly
  shape stays free.

**Make it a soft ship-or-pay tranche, not a hard wall.** Ship-or-pay is
economically a subscription plus punitive overage; modelling it that way is both
more faithful *and* structurally incapable of causing infeasibility. Sketch
(`scripts/walloon_scripts/named_pins.py`, wired in `solve_network.py` beside the
`industry_cc_floor` block, config under `sector.co2_export_limit`, default off):

```
Σ_h w_h [ Σ_{bus0 = BEWAL co2 stored} p − Σ_{bus1 = BEWAL co2 stored} p ] − overage ≤ cap
objective += overage_price × overage
```

Register a `GlobalConstraint` row alongside it so the dual survives into the
solved `.nc` — otherwise the cap leaves no trace for `review_run.py`, a bug
already documented for `add_selfsufficiency_constraints`.

**Lower bounds on the cap [V].** `industry_cc_floor` is a hard inequality, active
only at 2040 and 2050 on the default grid, and process emissions are a fixed
injection whose only outlets are atmosphere or capture, giving
`captured ≥ P − cap_BEWAL`:

| horizon | cc floor (kt) | P − cap (kt) | **min feasible export (kt)** | t/h |
|---|---:|---:|---:|---:|
| 2035¹ | 4,175 | −6,339 | **4,175** | 477 |
| 2040 | 5,103 | −2,900 | **5,103** | 583 |
| 2045¹ | 5,167 | +447 | **5,167** | 590 |
| 2050 | 4,852 | +3,441 | **4,852** | 554 |

¹ only on the `config.walloon_5y.yaml` overlay. Suggested starting caps at
floor × 1.15: **5,900 (2040) / 5,600 (2050)** kt/a, against the model's own
unconstrained 9,696 / 10,563. The subscribed volume itself is an input the
modelling cannot supply — it has to come from the transport-and-storage
assumption (§12 item 2).

> **These are "infeasible *below* this by construction" bounds, not sufficient
> conditions.** At 2050 a 5,600 kt cap removes ~4,960 kt of capture that must be
> replaced by gross abatement under a 1,667 kt cap. That may well be infeasible.
> **This is exactly why the cap must ship with the overage valve.**

Note that `industry_cc_floor` is currently **slack by 3,153 kt (2040) and
2,004 kt (2050)** [V] — the model chooses 62 % more industrial capture than it is
forced to, so the floor is not what drives today's result and removing it would
change nothing. It still bounds the cap design.

### 10.3 A low-CCS scenario: which levers move capture, and which cannot [V]

**The question.** The model reaches for capture everywhere — gas power, industrial
heat, process emissions — rather than for renewables or e-fuels, and a variant
with materially less CCS is wanted. *Would raising the sequestration price or the
gas price deliver it?* Measured on the 16 solved networks on disk and on the duals
of `scen_central`: **no, neither — and for two different reasons.** The
sequestration price is absorbed almost exactly by the shadow carbon price and
changes the capture volume by nothing; the gas price cannot reach 58–71 % of the
capture at all. The levers that do work are **quantity** levers and **capacity**
levers, not price levers.

One framing correction first. For **aviation and non-energy the model is not
choosing CCS over e-fuels** — it has no choice to make. Walloon kerosene
(8.60 TWh / 2,212 kt in 2040, 8.67 TWh / 2,230 kt in 2050) and `HVC to air`
(4.09 / 2.17 TWh) are exogenous `Load`s, never captured, and aviation sits outside
the national cap entirely (§9.1). The CCS-versus-e-fuel competition is real only
through the §8.4 / §9.4 identity — a tonne is buried **or** recycled into fuel,
never both — and it is settled against e-fuels by the hydrogen price, not by the
disposal price (§8.6). What follows is therefore about the capture that does
exist: power, industrial heat and process emissions.

#### 10.3.1 The sequestration price passes through into the carbon price ~1:1 [V]

The BEWAL cap binds to floating point in every horizon (§4.1) and capture is the
variable that closes it. So a levy Δ on `co2_sequestration_cost` does not make the
model capture less — it makes the model *pay more for the same capture*, because
the cap forces the shadow carbon price up until capture is back in the money. The
pass-through is the ratio of tonnes captured to tonnes avoided on the marginal
route:

| route | t captured | t avoided | **d(P_CO₂)/d(levy)** |
|---|---:|---:|---:|
| `CCGT CC` vs `CCGT` | 0.3297 | 0.3182 | **1.036** |
| `urban central gas CHP CC` vs `urban central gas CHP` | 0.4696 | 0.4467 | **1.051** |
| `gas for industry CC` vs `gas for industry` | 0.2090 | 0.1870 | **1.118** |
| `solid biomass for industry CC` (BECCS) | 0.3871 | 0.3871 | **1.000** |
| `process emissions CC` (capture or emit) | — | — | **1.000** |

Above 1.0 because a CC unit still emits its residual, so the carbon price has to
rise slightly *more* than the levy to restore indifference; exactly 1.0 where
capture and emission are the only two outlets. Reproduce with
`scripts/walloon_scripts/ccs_lever_sensitivity.py`. **The quantity response
is zero and the cost response is the full levy:**

| levy on top of 30 EUR/t | extra BEWAL disposal bill | change in Walloon emissions |
|---:|---:|---|
| +20 | 194 (2040) / 211 (2050) MEUR/a | **none — the cap binds** |
| +52 (i.e. the 82 EUR/t under discussion) | 504 / 549 MEUR/a | **none** |
| +100 | 970 / 1,056 MEUR/a | **none** |
| +150 | 1,454 / 1,584 MEUR/a | **none** |

This is visible directly in the reduced costs. Free-dispatch capex recovery of the
extendable BEWAL vintages, **with** the national shadow charge that does not price
through `co2 atmosphere` (validated: it returns exactly 100.0 % on every built
vintage, which is the LP-optimum signature):

| 2040, levy +Δ | 0 | +5 | +10 | +20 | +50 | +100 |
|---|---:|---:|---:|---:|---:|---:|
| `CCGT CC` | **100.0** | 96.2 | 92.4 | 85.0 | 63.7 | 38.1 |
| `CCGT` (unabated) | **100.0** | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| `gas for industry CC` | **100.0** | 89.3 | 78.5 | 57.1 | 0.5 | 0.0 |
| `process emissions CC` | **100.0** | 89.3 | 78.5 | 57.1 | 0.0 | 0.0 |
| `solid biomass for industry CC` | **100.0** | 89.3 | 78.5 | 57.1 | 0.0 | 0.0 |

At 2040 **every** Walloon capture route sits exactly at the margin — 100.0 %
across the board — so in *partial* equilibrium even a 5 EUR/t levy tips all of
them. That is precisely why it cannot happen: dropping industrial capture would
put ~8.3 Mt back into a cap with 8,334 kt of total headroom, and the elastic
non-capture block is nowhere near that size (§9.3). The carbon price rises
instead. 2050 is the opposite regime and equally immovable — `CCGT CC` is at
100.0 % against unabated `CCGT` at **13.0 %**, and a +300 EUR/t levy still leaves
CC ahead (16.4 % vs 13.0 %); at matched duty the crossover is **+300.7 EUR/t for
`CCGT CC`, +285.9 for gas CHP CC and +263.2 for `gas for industry CC`**, i.e. a
`co2_sequestration_cost` near **300 EUR/t**.

> **The instrument, not the parameter, is what neutralises the levy.**
> `co2_price_national: false`, so the cap does 100 % of the work (§6.4) and every
> euro added to disposal comes straight back out of the carbon dual. Under an
> **exogenous carbon price** — the TIMES instrument — the same levy would cut
> capture, because the price would not move to absorb it. `add_co2price_country()`
> ([`solve_network.py:2101`](../scripts/solve_network.py:2101)) is implemented and
> wired at [line 2226](../scripts/solve_network.py:2226), but **no `price_national`
> block exists in any config**, so `co2_price_national: true` would raise a
> `KeyError` today. Adding that block is the smallest change that would make every
> price lever in this document behave the way intuition expects.

#### 10.3.2 The gas price cannot reach most of the capture [V]

Two separate channels, both weak.

**Channel 1 — the capture decision.** The gas price touches CC-versus-unabated
only through the capture energy penalty: `CCGT CC` needs 1/0.5706 = 1.7525 MWh_gas
per MWh_e against `CCGT`'s 1/0.59 = 1.6949, a difference of **0.0576 MWh_gas per
MWh_e**, i.e. 3.4 % of the fuel bill. The resulting slope is
**−0.0576 (2040) / −0.0539 (2050) EUR/MWh_e per EUR/MWh_th**:

| | gas price that erases the CC advantage | vs the assumed gas price |
|---|---:|---:|
| 2040 | **83 EUR/MWh_th** | 32.20 → **2.6×** |
| 2050 | **1,831 EUR/MWh_th** | 26.92 → **68×** |

**Channel 2 — the gas volume.** Blocked, because nothing on the BEWAL supply side
has usable headroom: `onwind` is at its 6,500 MW aggregate ceiling, `solar-hsat`
uses 8.4 % (2040) / 10.5 % (2050) of its potential and `solar` utility 3.0 % / 0 %
but both are held by the TIMES rooftop-share pin (§7.2), `import_limit_BEWAL`
binds with a dual of **−9.04 (2040) / −3.09 (2050)** EUR/MWh, and the battery is at
its 8–9 h economic optimum (§7.4). A gas price rise therefore raises λ_el — the
`CCGT CC` short-run marginal cost is 83.57 (2040) / 85.28 (2050) EUR/MWh_e, inside
the price distribution's main body — and leaves the physical mix where it was.

**And most of the capture is not gas at all.** By origin:

| | 2040 | 2050 |
|---|---:|---:|
| `process emissions CC` | 5,028 | 4,765 |
| `solid biomass for industry CC` (BECCS) | 1,853 | 1,359 |
| **gas price cannot touch** | **6,881 kt = 71 %** | **6,124 kt = 58 %** |
| `CCGT CC` + gas CHP CC + `gas for industry CC` | 2,815 kt = 29 % | 4,440 kt = 42 % |
| **total** | **9,696** | **10,563** |

Verified in the sweep: gas prices from +0 to +100 EUR/MWh_th leave
`process emissions CC` and `solid biomass for industry CC` recovery **identical to
four significant figures** — 100.0 % / 100.0 % at 2040 and 100.0 % / 54.8 % at 2050.
Flat, not merely flattish: neither route touches the gas bus.

**The natural experiment on disk agrees.** `run20260908` / `scen_demande_haute`
carry the pre-2026-09-05 gas trajectory — λ_gas **38.60** (2040) and **36.68**
(2050) against `scen_central`'s 32.20 / 26.92, i.e. **+20 % / +36 %**. Capture
falls 9,696 → 8,802 kt (2040) and 10,563 → 9,588 kt (2050): **−9 % both times**,
and confounded with the demand change in that scenario. Direction correct,
magnitude an order below what "a different pathway" means.

Worth recording as an assumption in its own right: the gas price **declines**
across the horizon — 37.08 / 37.08 / 31.78 / 26.48 EUR/MWh_th at 2025/2030/2040/2050
(`data/walloon/custom_costs*.csv`, sourced to the CLIMA.A GHG-projection
parameters). A −29 % real gas price by 2050 is itself a push toward the gas-plus-capture
pathway, and it is one number, in one row, that a sensitivity can flip.

#### 10.3.3 Half the Walloon capture is structurally immovable [V]

Across **all 16 solved networks on disk** — spanning nuclear costs 4,500–9,500
EUR/kW, taxshift, biomethane, high demand, the 2013 weather year and both réaliste
variants — `process emissions CC` sits in a **±1.6 % band**:

| | range across 16 runs | spread |
|---|---|---:|
| `process emissions CC` 2040 | 5,020 – 5,179 kt | **±1.6 %** |
| `process emissions CC` 2050 | 4,760 – 4,916 kt | **±1.6 %** |
| industrial capture total 2040 | 6,214 – 8,568 kt | ±16 % |
| **power capture 2040** | 638 – 1,949 kt | **±51 %** |
| **power capture 2050** | 2,327 – 5,736 kt | **±42 %** |

The reason is structural, not economic: the process-emissions `Load` is exogenous
and has exactly two outlets, atmosphere or capture. The model prices the choice
itself, and the dual on `BEWAL process emissions` **is** the all-in capture cost:

| per tonne of process CO₂ handled | 2040 | 2050 |
|---|---:|---:|
| capture capex (387,724 / 317,229 EUR/MW at 8,760 h) | 44.26 | 36.21 |
| residual 5 % emitted × stacked carbon price | 7.07 | 23.33 |
| 95 % captured × disposal price | 54.77 | 74.24 |
| **= λ(`BEWAL process emissions`), verified** | **106.10** | **134.35** |
| **cost of emitting instead** | **141.33** | **477.81** |

A 1.3× margin at 2040 and 3.6× at 2050. Capture switches off only at a disposal
price of **94.7 (2040) / 439.7 (2050) EUR/t** — and even then the cap would force
it back (§10.3.1). `industry_cc_floor` then puts a hard floor of 5,103 / 4,852 kt
under it anyway. **Only power capture is elastic, and across the 16 runs it is
7.2–23.9 % of total capture at 2040 and 23.6–44.0 % at 2050** (`scen_central`:
14.9 % / 35.1 %). Any low-CCS scenario has to be honest about this: the industrial
half is a property of the transferred TIMES industrial demand, not an economic
choice the optimiser is making.

> **Process capture carries no energy penalty at all, and the data to give it one
> is already on disk.** [V] Verified port-by-port: `BEWAL process emissions CC` has
> exactly three ports — `bus0` process emissions, `bus1` `co2 atmosphere` (the
> slip), `bus2` `BEWAL co2 stored`. No electricity, no heat. Its entire charge is
> the 44.26 / 36.21 EUR/t of capex above. The fuel routes at least carry the
> penalty implicitly as an efficiency derate (`CCGT CC` 0.5812 against `CCGT` 0.60
> on the 2050 vintage; industrial CC links η 0.90 against 1.00); this one carries
> nothing.
>
> [`prepare_sector_network.py:5981`](../scripts/prepare_sector_network.py:5981)
> says why, in one comment: `# assume enough local waste heat for CC`. Only
> `capital_cost`, `capture_rate` and `lifetime` are read from the `cement capture`
> block. But `data/costs/archive/v0.14.0/costs_2040.csv` also carries, from the
> same Danish Energy Agency sheet *401.c Post comb - Cement kiln*:
>
> | row | value |
> |---|---:|
> | `electricity-input` | 0.020 MWh_e/tCO₂ |
> | `compression-electricity-input` | 0.075 MWh_e/tCO₂ |
> | `heat-input` | 0.66 MWh_th/tCO₂ |
> | `heat-output` | 1.48 MWh_th/tCO₂ |
>
> The **heat** omission is defensible — the DEA unit rejects more low-grade heat
> than its reboiler draws, which is what the upstream comment is claiming. The
> **electricity** is not covered by that argument: **0.095 MWh_e/tCO₂ is simply
> absent**, worth **8.8–9.5 EUR/t** at λ_el 93–100 EUR/MWh, i.e. **+20 to +26 % on
> the capex charge** of the largest and most invariant capture block in the model.
> Not a pathway-changer on its own, and §10.3.1's pass-through would absorb much of
> it — but it is sourced, one-sided, and it also *adds Walloon electricity demand*,
> tightening the same corner that blocks electrolysis (§8.7). **Worth wiring
> before any capture-cost conclusion is published**; whether 0.66 MWh_th/t of free
> waste heat really exists across the Walloon cement/lime/glass mix
> ([`ccs_alignment.md`](ccs_alignment.md) §11) is a separate question for ICEDD.

#### 10.3.4 What *does* move capture — solved evidence [V]

The `scen_nuctip_*` family varies **nuclear investment cost** (not capacity) and is
internally comparable — same TIMES file `scen_sensibilite_nofixnuc`, one parameter
changed:

| `nuclear` EUR/kW | nuclear built (MW_e) | 2050 power capture | 2050 total capture |
|---:|---:|---:|---:|
| 4,500 | **3,000** | **2,358 kt** | **9,697 kt** |
| 5,500 | 2,144 | 4,428 | 11,809 |
| 6,000 | 1,030 | 5,736 | 13,116 |
| 6,500 | 1,030 | 5,666 | 13,021 |
| 7,500 | 1,030 | 5,530 | 12,823 |
| 9,500 | 1,030 | 5,524 | 12,822 |

Cheap nuclear cuts **power capture by 59 % and total capture by 26 %** — by a wide
margin the largest effect any lever has produced in a solved run, and the tipping
point sits between 5,500 and 6,000 EUR/kW. It is also the only lever tested that
substitutes a *firm winter* MWh, which is the slot §7.4 identifies as the one
CCGT-CC actually wins. (Not comparable against `scen_central` directly — different
TIMES file — so read the family internally.)

#### 10.3.5 Ranked levers for a low-CCS variant

| lever | effect on BEWAL capture | evidence | status |
|---|---|---|---|
| **Net CO₂ export cap (lever D)** | direct and by construction — Wallonia has no domestic sink, so every captured tonne must cross a border | §10.2 design; floors 5,103 / 4,852 kt | **designed, not implemented** |
| **Nuclear capex 6,000 → 4,500 EUR/kW** | **−26 % total, −59 % power** at 2050 | solved, `scen_nuctip_*` | available today, one CSV row |
| **Remove the TIMES rooftop-share pin (lever E)** | frees 40–43 TWh/a of `solar-hsat` potential now at 8–11 % use; solar moves before capture (§7.2) | reduced cost §7.2/§7.4 | one config key, one run |
| **Exogenous carbon price instead of the cap** | makes every price lever below actually bite | `add_co2price_country` exists | **`price_national` config block missing** |
| **Relax `import_limit_BEWAL`** | dual −9.04 (2040) / −3.09 (2050); §10.1 puts it at 17–19 % of the electrolyser gap | solved duals | TIMES soft-link decision |
| **Wire the missing capture electricity** | +8.8–9.5 EUR/t on process capture (+20–26 % of its capex charge), and it aims at the block nothing else reaches | DEA rows already in `costs_*.csv`, unread by [`prepare_sector_network.py:5981`](../scripts/prepare_sector_network.py:5981) | **untested; small code change** |
| Gas price +20 % / +36 % | **−9 %**, confounded | `run20260908` vs `scen_central` | weak |
| `co2_sequestration_cost` 30 → 82 | **0 % quantity change**; +504–549 MEUR/a | pass-through 1.00–1.12 | **rejected as a CCS lever** |
| Fix the per-vintage ceiling (lever A) | raises the rent endogenously — but the same pass-through applies, so expect price, not quantity | §5.2 | still do it: it is a bug |

**Recommendation.** A price lever cannot produce a low-CCS pathway while the cap
binds; it produces an expensive CCS pathway. The instrument that delivers one *by
construction* is **lever D, the net CO₂ export cap of §10.2** — because "less CCS"
in Wallonia physically means "less CO₂ leaves Wallonia", and that is exactly what
D constrains. Pair it with **cheap nuclear** (the one demonstrated substitute for
the firm winter MWh) and **the rooftop-pin release** (the cheapest abatement,
currently blocked by an assumption rather than by cost), and read the levy and the
gas price as *cost* sensitivities rather than *pathway* levers.

Two cautions carried over. D at the §10.2 starting caps (5,900 / 5,600 kt) removes
roughly 3,800 / 5,000 kt of capture that must be replaced by gross abatement under
a cap that already binds exactly — **the overage valve is mandatory, not optional**.
And such a scenario should be published as *"what a transport-and-storage
constraint costs"*, not as an equally good pathway: on this model's own
arithmetic it is strictly more expensive, and §6.3 records that TIMES-WAL reaches
a similar ≈8 Mt of capture independently. **Heavy CCS is not a PyPSA artefact; its
*price* in this model is.**

### 10.4 What was implemented on 2026-09-22

Four changes, landed together and tested together as a package at 6 h on
`scen_central_6h` (a dedicated run name, so the 1 h cabinet batch in
`results/walloon/scen_central` is not overwritten). This deviates from §11's
one-change-per-step ladder and the deviation is recorded in that run's solve
log; the reason is that all four require a full myopic chain re-run from 2025
anyway, and two of them (the PV pair) are one change seen from two sides.

**1 — Rooftop *share* → rooftop *floor* (lever E, stronger than proposed).**
`sector.rooftop_share` is gone; `sector.rooftop_floor` reads the `rooftop_gw`
column of the same `data/walloon/times_pv_rooftop_share*.csv` files and floors
the whole BEWAL `solar rooftop` fleet — every vintage, standing and extendable —
at the TIMES capacity. The old key now **raises** in `extra_functionality`
rather than being silently ignored, because dropping the TIMES PV alignment
without a trace is exactly the failure mode this soft-link keeps producing.

This is a stronger statement than the share pin, not a weaker one. The share
fixed the *composition* of Walloon PV without fixing its *size*; the floor fixes
the size of the roof tranche, which is the thing TIMES actually decides, and
leaves the ground-mounted tranche entirely to the optimiser. For `scen_central`
the floor is 4.29 / 10.47 / 11.27 GW at 2030 / 2040 / 2050 — against the 5.35 GW
of rooftop the 2040 solve built under the share pin (§7.2), so it roughly
**doubles** 2040 Walloon rooftop PV. Feasibility was checked against all three
bounds before launching: the BEWAL `solar-all` agg row has no maximum from 2030
on, `solar rooftop` has 46 GW of `p_nom_max` (`custom_potentials.csv`), and the
CCL build rate allows 6.6 GW per 5-year and 13.2 GW per 10-year period against
requirements of 2.5 / 6.2 / 0.8 GW.

The two réaliste scenarios keep their deliberately missing 2030 row, so they
still get no 2030 floor — for the same reason as before (TIMES puts that year's
Walloon PV behind the meter, so the plant-only figure does not describe the
fleet the constraint applies to).

**2 — `solar-hsat` removed.** Only ground-mounted `solar` and `solar rooftop`
remain. Wallonia's ground-mounted potential is agrivoltaics plus industrial
brownfield — 13 GW, sourced in `custom_potentials.csv` — and the Walloon
sources behind it size and price fixed-tilt plant; `solar-hsat` was a second,
unsourced ground-mounted technology carrying its own 37.8 GW land-availability
potential. Keeping both also switched on `add_solar_potential_constraints`,
which traded one against the other through the ratio of their
`capacity_per_sqkm` — an upstream land-use assumption nobody on this project
had reviewed. `solve_network` builds that constraint only when `solar-hsat` is
in **both** carrier lists, so removing it from the lists is what removes the
trade-off.

Together, 1 and 2 dismantle the bundle §7.2 measured: there is no longer a
carrier that has to drag 2.23 MW of rooftop along per MW of itself.

**3 — Lever A, the per-vintage sequestration ceiling.**
`scripts/walloon_scripts/sequestration_bounds.py`, called from `add_brownfield`
after the vintages are carried forward and **before** `update_BEWAL_potentials`
— the Belgian documented zeros do the same arithmetic for BEWAL/BEVLG/BEBRU and
must have the last word, or the residual would be netted twice. The ceiling is
read from the extendable vintage (the only one still carrying the CO2StoP
figure), inherited vintages are subtracted, and the residual is written on this
horizon's Store. Same shape as the PTES fleet cap (item 16) and as
`apply_co2_store_cap`; this generalises it to every node, which is where DE, NL
and GB live.

Measured on the 1 h `scen_central` networks already on disk, before the change:
fleet 209.20 Mt/a at DE against a 79.147 Mt/a ceiling, 27.28 vs 9.095 at NL,
145.59 vs 100.0 at GB — reproducing §5.2 exactly. Note the fix cannot undo a
previous horizon's build: it caps each horizon's *addition* so the fleet never
exceeds the ceiling going forward, which is the correct myopic behaviour.

**4 — Lever B, `threshold_capacity: 0 → 10`.** The PyPSA-Eur default restored.
Note this also filters the base-year existing-capacity bins in
`add_existing_baseyear`, which is why it may only be changed with a full chain
re-run from 2025, never mid-chain.

**Regression tests.** `test/test_rooftop_floor.py` (replacing
`test_rooftop_share.py`), `test/test_sequestration_fleet_cap.py`,
`test/test_no_solar_hsat.py`.

#### Measured outcome, 6 h, `scen_central_6h` [V]

4/4 optimal; `review_run.py` 161 PASS · 31 INFO · 16 WARN · 0 FAIL. Full record
in [`logs/2026-09-22_scen_central_6h_pvfloor_leverAB.md`](logs/2026-09-22_scen_central_6h_pvfloor_leverAB.md).
**Every number below is 6 h with four simultaneous changes: it is not comparable
to the 1 h batch and no lever can be attributed on its own.**

*Lever A lands on this document's own projection.* 2050 fleet: DE 209.20 →
**79.147**, GB 145.59 → **100.000**, NL 27.28 → **9.095** Mt/a, each exactly its
ceiling; total 382.07 → **188.24**. §9.4 projected "382 to 188 Mt/a"
arithmetically before the fix existed.

*Lever B does what it was for.* Carried-forward non-extendable vintages with
0 < capacity < 10: **0** at 2030/2040/2050 (3 at 2025, from the separate
`add_existing_baseyear` path), against "~1 278 near-zero components by 2040".
Bound spread 5.0e6 / 5.4e6 / 8.9e7 / 3.7e7 — inside §11's `< ~1e9` gate in every
horizon. Note the count of *optimised* values below 10 MW is still ~460 per
horizon and always will be: `threshold_capacity` governs only what is frozen
into the next horizon, not what the LP returns.

*The rooftop floor binds at 2030 and 2040 but not at 2050.* Rooftop 4 290 /
10 470 / 22 329 MW against floors of 4 290 / 10 470 / 11 269. At 2050 the LP
builds **twice** the TIMES floor unprompted: with ground-mounted PV no longer
tied to it by a ratio, rooftop wins on its own economics (behind the
distribution grid, and `add_electricity_grid_connection` does not charge it).
Ground-mounted settles at 4 976 / 6 647 / 6 579 MW against a 13 GW potential —
so it is *not* at its cap either, and the §7.2 bundle is genuinely gone.

**Two findings that change what to do next.**

1. **The binding constraint moved onto `growth_multiplier`.** New BEWAL
   solar-all build is at **exactly 100.0 %** of the CCL build-rate allowance in
   2030 (6 585 of 6 585 MW) and 2050 (13 170 of 13 170 MW); 69.5 % at 2040.
   Before this change PV had 5 549 MW of slack there (§7.2). So in two of three
   horizons Walloon PV is now set by `growth_multiplier: 2.0`, which
   `config.walloon.yaml` calls "the one number here that is not a measurement,
   so sensitivity-test it". That sensitivity is now owed — it has inherited the
   role lever E was meant to play.

2. **Lever C is no longer warranted, and would now push the price the wrong
   way.** `BEWAL co2 stored` price (this document's own metric): **88.8 EUR/t at
   2040, 319.1 at 2050**, against the 75 / 67 lever C would set and the 82 / 74
   reference chain of §5.1. Lever A raises the endogenous price past both.
   2025 and 2030 (398.6 / 330.9) are set by the *pooled* deployment ramp — μ =
   463.6 and 293.4 on `co2_sequestration_limit` — not by geology, so they say
   nothing about lever A; at 2040/2050 that dual is 0 and the per-node rent is
   what remains. **Repeat at 1 h before dropping C formally.**

---

## 11. Staged test sequence

Drawn from the catalogue of every infeasibility this model has hit since August
(logs `2026-08-14` → `2026-09-15`, `docs/renewable-potentials.md` §9.6–9.7, and
§13 below). Run at **6 h** on **`scen_central`**, full myopic chain, one change
per step, so a failure at step *k* is attributable to change *k*.

| # | under test | gate |
|---|---|---|
| 0 | none — 6 h baseline | 4/4 optimal. Record objective, capture, net export, BEWAL slack + μ. **Only legitimate comparator — never compare 6 h against the 1 h results.** |
| 1 | **B** `threshold_capacity` | 4/4 optimal; bound spread < ~1e9 (was 1e17); objective within 0.5 % of #0 — a larger move means it deleted something real, bisect with `t=1`. No new "standing fleet exceeds cap" warnings. |
| 1b | same, 1 h, 2025 only | within 0.2 % of archived 1 h 2025 — confirms the base year is unchanged in substance. |
| 2 | **A** storage ceiling | 4/4 optimal. DE/NL installed ≤ ceiling. **Re-measure `BEWAL co2 stored` price — this is the number that decides whether C is still needed.** |
| 3 | **C** cost, if still warranted | Objective rises; capture falls at 2040/2050; BEWAL cap still binds exactly. `get()` must log no "investment key not found". |
| 4 | **D** non-binding (`kt: 20000`) | Constraint present, **dual = 0**, objective identical to #3 to ~1e-6. Proves the expression is signed correctly. |
| 5 | **D** transit sign test (2040 `kt: 12000`) | **Dual must be 0.** Net export 9,696 < 12,000 but *gross* 14,778 > 12,000. **A non-zero dual means you wrote a gross constraint and are throttling Flanders.** Single most important test. |
| 6 | **D** binding hard (2040 `kt: 6000`) | Optimal, dual < 0, net export ≈ 6,000. **Cross-check BEVLG capture, flow and μ are unchanged vs #3** — if BEVLG moves, the design is mis-implemented. |
| 7 | **D** below the floor (2040 `kt: 4000`, overage 250) | **Must solve**, with overage > 0. Proves the valve works. If infeasible, the objective term is not wired. |
| 8 | chosen settings, 1 h | Production. `review_run.py --full`, solve log, §11 review. |

**Standing traps to re-check at every step** (each has already bitten once):

- **The 2050 biomass corner** — the EU-wide `biomass limit` binds in *all 14*
  scenarios at −1,087 to −1,308 EUR/MWh
  ([`ccs_alignment.md`](ccs_alignment.md) §13). Making capture more expensive
  changes *which* technology captures, not whether biomass binds. Check the dual
  before trusting any 2050 solve.
- **Empty corridors** — never edit a floor and a ceiling in separate commits.
  This exact mistake produced min > max in the réaliste 2030 corridor, caught only
  pre-launch.
- **Silent relaxation** — a TIMES pin can be bought out rather than met when the
  fuel's shadow price exceeds the penalty (2040 biomass boiler, 88 % undelivered,
  reported *optimal*). Run `report_relaxed_profiles()`.
- **Net zero is structurally unreachable** with `dac: false` (§8.4). Do not drift
  toward it; 2050 stays at 0.050.
- **`industry_cc_floor` reachability** — re-verify after any CCS-economics change
  that the maximum capturable from the transferred gross fuel mix still clears the
  floor.
- Numerics: keep `BarHomogeneous`; escalate to `NumericFocus: 3, ScaleFlag: 2` on
  numerical trouble, as `scen_realiste_nobnd30` 2050 required.

**On folding this into the réaliste scenarios:** the réaliste variants relax the
2030 Belgian CO₂ budget to 1.0, which makes the 2030 carbon price **zero** and
2030 capture **zero** [V]. A CCS-cost or export-cap change will therefore produce
**no 2030 signal at all** in those scenarios — do not read that as robustness.
From 2040 they are within a few per cent of `scen_central`, so they are a
reasonable host for the package, but `scen_realiste_nobnd30` is the scenario that
already failed numerically at 2050 and sits closest to the shared corner. **Land
the package in `scen_central` first; port to réaliste only after step 8 passes.**

---

## 12. Points to align with TIMES

Model-to-model reconciliation still outstanding. Each is a decision that changes
published numbers, not a research question.

1. **Settle the 1990 reference** (§6.1). PyPSA uses 33,337 kt from a uniform
   population split; TIMES implies ≈45,600 kt. They differ by 27 %, so the same
   "−X %" is a different tonnage in each model. Either PyPSA adopts the TIMES
   reference, or every published percentage is labelled with its denominator.
   **PyPSA's population split is the weaker of the two** — 1990 Wallonia carried
   the Belgian steel industry, so a uniform per-sector split understates its
   industrial base. This is a candidate TIMES→PyPSA transfer.
2. **Decide the transport-and-storage chain and put it in the repository.** The
   onshore leg needs itemising: collection only, or collection plus trunk to the
   regional border? The model already charges 7.4 EUR/t for a 280 km trunk, so if
   the onshore figure is collection-only no subtraction is warranted and the C
   values become 94/82/78/74 rather than 87/75/71/67. Whatever is agreed must
   land in `config/input_parameters_for_models.csv` as sourced anchors before it
   is defensible in a deliverable, and **should be recomputed independently before
   adoption**. The subscribed volume (Mt/a) for lever D is part of the same
   decision.
3. **Decide whether the TIMES rooftop-share trajectory is a constraint or an
   outcome** (§7.2). It is the binding limit on Walloon solar and therefore on the
   whole marginal-abatement stack. If it is a TIMES *result* rather than a Walloon
   policy, pinning PyPSA to it imports an assumption with large consequences and
   the pin should become a sensitivity, not a hard constraint.
4. **Reconcile the CO₂ transport chains.** `data/walloon/discount_rates.csv:22`
   carries a TIMES `CO2 liquefaction` technology; PyPSA has none (§4.4) and pipes
   CO₂ to Germany along an electricity corridor. If TIMES prices liquefaction and
   shipping and PyPSA prices an onshore pipe, the two models' CCS costs are not
   comparable and should not be presented side by side until one is adjusted.
5. **Reconcile where carbon is priced.** PyPSA charges CO₂ only at combustion,
   identically for fossil and synthetic oil (§8.5). If TIMES prices carbon at
   fossil extraction, the two models' synthetic-fuel economics are structurally
   different and the soft-link is transferring a demand whose supply-side
   incentives disagree.
6. **Decide the aviation convention** (§8.4). PyPSA aviation is exogenously
   fossil: an unresponsive `Load`, 2,212 kt/a at BEWAL, 67 % of all remaining 2050
   oil demand. Either the model gains a usable synthetic-kerosene route (lever G:
   a mandate plus cheaper hydrogen, since the FT route exists but is uneconomic)
   or every published Walloon 2050 figure states that aviation is exogenously
   fossil. Silence on this is not an option; it is also the unresolved half of the
   2050 net-zero infeasibility.
7. **Split oxy-fuel process carbon.** Part of the TIMES captured industrial
   stream comes from oxy-fuel glass and cement units and may mix process with
   combustion carbon; the split affects the `process emissions` Load that PyPSA
   receives ([`ccs_alignment.md`](ccs_alignment.md) §11.1).

---

## 13. History: the 2026-08-30 revert and what it taught

The layer-A change of §3.1 was made on 2026-08-29, **reverted on 2026-08-30**, and
**restored on 2026-09-02** with `BarHomogeneous: 1` (4/4 optimal —
[`2026-09-02 6h BE=0`](logs/2026-09-02_scen_demande_haute_2010_6h_co2sinks_be0.md);
an earlier 6 h run with BEWAL at the withdrawn TIMES 7.1 Mt is
[here](logs/2026-09-02_scen_demande_haute_2010_6h_co2sinks.md)).

**What happened.** The 2040 horizon would not converge. Gurobi ran the barrier to
completion and returned `Numerical trouble encountered` — *"Model may be
infeasible or unbounded. Consider using the homogeneous algorithm"*. Dual
infeasibility parked at `4.19e-04`; complementarity plateaued instead of falling.

**The cap value is not a threshold.** The obvious reading — that lifting the cap
forces the optimiser to reach GB's storage over extendable `CO2 pipeline … -> GB`
links across 495–802 km of sea — predicts a clean threshold at DE + NL =
88.2 Mt/a. Holding everything else fixed and varying only the 2040 cap:

| cap | outcome |
|---:|---|
| 85 Mt/a | **FAIL** — 252 iter / 3086 s |
| 90 Mt/a | optimal — 263 iter / 3650 s, objective 3.12850428e+11 |
| 100 Mt/a | **FAIL** — 191 iter / 2360 s |
| 1000 Mt/a | **FAIL** — 288 iter / 3754 s |

A structural threshold cannot be non-monotone. The cap value merely perturbs a
model that is numerically fragile at 2040; `BarHomogeneous` is the actual fix.

`max_size` was exonerated separately: at a 90 Mt/a cap, `max_size` 2.5 and 25 give
byte-identical results — same objective to nine figures, same 263 iterations, same
4506.89 work units. With a binding global cap below GB's ceiling the regional clip
never binds.

**Lesson worth keeping:** two independent things moved in one commit (the cap
value and `max_size`), and the failure was attributed to the wrong one until they
were separated. Decompose bundled switches before trusting a combined result.

---

## Sources

- [PyPSA-Eur release notes](https://pypsa-eur.readthedocs.io/en/latest/release_notes.html)
  and [configuration docs](https://pypsa-eur.readthedocs.io/en/latest/configuration.html)
- [PyPSA/pypsa-eur#1228](https://github.com/PyPSA/pypsa-eur/pull/1228) — per-period sequestration potentials
- [Neumann et al. (2025), *H₂ and CO₂ network strategies for the European energy system*, Nature Energy](https://www.nature.com/articles/s41560-025-01752-6)
  and its [preprint](https://arxiv.org/html/2407.18653v2) — the 200 Mt/a rationale
- [CO₂StoP, European CO₂ storage database](https://setis.ec.europa.eu/european-co2-storage-database_en) — the layer-B data
- [EU Net-Zero Industry Act: 50 Mt/a CO₂ injection capacity by 2030](https://www.newcivilengineer.com/latest/eu-targets-50m-tonnes-per-year-of-co2-storage-by-2030-12-02-2024/)
- [UK CCUS targets: 20–30 Mt/a by 2030, >50 Mt/a by 2035 (CCSA)](https://www.ccsassociation.org/news/government-commits-to-establishing-carbon-capture-and-storage-industry/)
- [North Sea Transition Authority — UK Continental Shelf storage capacity](https://www.nstauthority.co.uk/the-move-to-net-zero/ccs/)

Further sourced anchors for a deployment ramp, if one is wanted later: Industrial
Carbon Management Strategy ambition ~250 Mt/a EEA-wide by 2040; 250 Mt/a stored
EU-wide by 2050 in the 2040 climate-target communication; UK 20–30 Mt/a by 2030
(conceded unachievable in Dec 2024), ">50 Mt/a by 2035", up to 170 Mt/a by 2050 as
ambition against scenario figures nearer 30/40/60 Mt/a at 2035/2040/2050;
18.7 Mt/a past FID Europe-wide today.
