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
arithmetic.

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

**What to do,** in order, because the levers are not interchangeable and two of
them double-count if applied together: fix the per-vintage ceiling bug, fix
`threshold_capacity`, then re-measure before touching any cost parameter; then a
net CO₂ export cap; then the rooftop-pin sensitivity; then any 2040 target
change. Full plan in §9, test sequence in §10.

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
cap design (§9.2): a cap on the physical pipe would throttle Flanders, which has
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
sensitivity run before any 2040 target is set** (§9, lever E).

### 7.3 What can and cannot cause infeasibility [V]

**Changing a cost coefficient cannot make an LP infeasible** — the feasible region
depends on the constraint matrix and RHS only. Raising CCS cost is safe by
construction. *Tightening the cap* is what can fail, and this model has no escape
hatches: `co2_vent: false`, `load_shedding: false`, DAC absent, Walloon storage 0,
and `import_limit_BEWAL` binding at 6.47 TWh (μ = −9.04 EUR/MWh).

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
plus cheaper hydrogen, §9 lever G) or **every published Walloon 2050 figure must
state that aviation is exogenously fossil.**

### 8.5 Fossil carbon is unpriced at extraction [V]

`EU oil primary` carries **no** carbon charge; CO₂ is booked only at combustion,
**identically for fossil and synthetic oil**. This is the structural reason
behind §8.4 point 3: synthetic oil can never earn a carbon premium at the `EU
oil` bus, no matter how the carbon price moves. Short of separate
fossil/synthetic oil accounting (a code change) or a mandate, power-to-liquids
cannot win on price in this model's structure.

### 8.6 Fixing CCS economics does **not** unlock power-to-fuel [V]

`SMR CC` efficiency3 0.1782 ÷ η 0.69 = **0.2583 tCO₂/MWh_H2**, so moving
`co2_sequestration_cost` 30 → 82 adds **+13.4 EUR/MWh_H2**. The consequence
splits three ways:

- **2040: exactly zero effect.** λ_H2 is set by *unabated* SMR, which pays no
  sequestration cost at all. Raising the cost moves λ_H2 by **0.00** and
  electrolysis recovery does not budge; it only pushes SMR CC further out of the
  money (GB recovery 91.6 % → 12.8 %).
- **2050, hydrogen: largely yes.** SMR CC is marginal, so the full +13.4 passes
  through. Electrolyser capex recovery: FR 77.6 → **101.3 %** (enters), GB 74.6 →
  **97.0 %**, DE 72.6 → 92.5 %, BEWAL 62.3 → 82.7 %. Expect *marginal* entry in
  FR/GB, not a wholesale switch.
- **2050, power-to-liquids: strictly worse.** FT needs 1.326 MWh_H2 per MWh_oil,
  so its cost rises +17.8 EUR/MWh_oil while its CO₂ credit rises only +13.4 →
  **net −4.4**. GB FT recovery falls 14.5 % → 9.4 %. SMR CC buries 0.343 tCO₂ per
  MWh_oil-equivalent of hydrogen but FT only recycles 0.257, so **FT is a
  structural net loser under a sequestration levy.**

**CCS pricing and power-to-fuel therefore need separate levers, and a
sequestration levy actively works against synthetic liquids.**

### 8.7 One root cause, two symptoms

Walloon wind is at its ceiling and solar is pinned (§7.2), the electricity import
cap binds, so power stays at ~100 EUR/MWh; electrolysis is uneconomic; hydrogen
comes from cheap gas; the resulting CO₂ is disposed of at a rent-suppressed price
(§5); and the cap is met by capture. **Cheap gas plus under-priced carbon disposal
plus suppressed cheap renewables produces both runaway CCS *and* zero
power-to-fuel.**

This also **partly de-risks the export cap** (§9.2). The worry was that capping
exports removes the only valve, since Wallonia has no domestic sink. There is a
second, entirely unused valve — but §8.6 shows it does not open at 2040, so the
export cap must still ship with its overage tranche.

---

## 9. Recommended changes, in order

**Order matters: the levers are not interchangeable, and two of them
double-count if applied together.**

| # | change | why it sits here |
|---|---|---|
| **A** | **Fix the per-vintage sequestration ceiling** (§5.2) | A genuine bug, defensible without picking a tariff, and it raises the disposal price *endogenously*. Everything else is measured against this. |
| **B** | **Fix `threshold_capacity: 0 → 10`** | Known numerical time bomb: ~1,278 near-zero components by 2040, 17-order bound spread, already tipped `scen_realiste_nobnd30` 2050 into genuine numerical failure. Requires a full chain re-run from 2025 anyway — do it now, not after. |
| **C** | **Year-dependent `co2_sequestration_cost`** | Only *after* A, and re-measured: the residual gap may be small (§5.1). Values net of the pipeline leg already charged: 87 / 75 / 71 / 67 for 2035/40/45/50 (= all-in reference − 7.4). |
| **D** | **Net CO₂ export cap at BEWAL** | The honest representation of "this infrastructure must be built and agreed with another country" (§4.3, §4.4). Design in §9.2. |
| **E** | **Rooftop-share pin sensitivity** | §7.2 — the cheapest abatement margin is currently set by a soft-link assumption. Needed before any 2040 target is credible. |
| **F** | **A tighter 2040 target, as a variant** | Last. Depends on A–E to mean anything, and on settling the 1990 reference (§6.1). Not in the central scenario until then. |
| **G** | **Power-to-fuel** | Separate track — CCS levers deliver **nothing** at 2040 and *hurt* synthetic liquids (§8.6). Ranked below. |

### 9.1 Levers for G, ranked by magnitude actually delivered [V]

Gap to close, in EUR/MW_el/yr of unrecovered electrolyser capex: 2040 BEWAL
137,752 / GB 111,849; 2050 BEWAL 61,500 / GB 41,443 / FR 36,476.

| lever | what it delivers | where |
|---|---|---|
| **Electrolyser capex** — the only price lever with enough magnitude at 2040 | Break-even needs **−50 to −70 %** at 2040, **−17 to −38 %** at 2050 | `data/walloon/custom_costs*.csv`, `electrolysis` investment row. No code change. |
| **A mandated e-SAF / synthetic-fuel share** | The only lever with enough magnitude at 2040, and the one that addresses §8.4 point 3. **No config key exists anywhere.** | Small code change — a Link branch in `BEWAL_potentials.py` or a `solve_network.py` constraint, same pattern as the 1,740 MW CCGT floor |
| **Cheaper electricity** | Needs −35 to −53 EUR/MWh (2040). Relaxing the import cap fully buys only **17–19 %** of that (dual −9.04). BEWAL onwind is pinned at 6,500 MW with a **+22,366 EUR/MW/yr** capacity rent in 2040 — the ceiling binds hard. **Nuclear is the only lever of the right order.** | `custom_potentials.csv` (`onwind`), import cap (TIMES softlink), `scen_nuctip_*` |
| **CCS cost 30 → 82** | **0 % of the gap at 2040**; 54 % (BEWAL) to >100 % (FR) at 2050. Costs FT ~5 pp. | `sector.co2_sequestration_cost` — one key |
| **`min_part_load_fischer_tropsch: 0`** | Restores 100 %+ of FT's 2050 gross margin. Still only 14–18 % of capex, but removes a genuine artefact for one key. | `config.default.yaml:980` |
| **`sector.dac: true`** | Prerequisite for genuinely carbon-negative synfuel — the only technology moving atmospheric carbon onto `co2 stored`, and the documented fix for the 2050 net-zero infeasibility (§8.4 point 2). | `config.walloon.yaml` |
| **`methanol_to_kerosene` / `electrobiofuels`** | **Near-zero effect** (§8.4). Cheap to flip; do not expect a result. | `config.default.yaml:970`, `config.walloon.yaml:617` |
| **Price carbon at oil extraction** | Addresses §8.5 at the root. Deepest, most invasive. | `prepare_sector_network.py` — separate fossil/synthetic oil buses |

### 9.2 Design of D — cap the *net* outflow, not the pipe

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
assumption (§11 item 2).

> **These are "infeasible *below* this by construction" bounds, not sufficient
> conditions.** At 2050 a 5,600 kt cap removes ~4,960 kt of capture that must be
> replaced by gross abatement under a 1,667 kt cap. That may well be infeasible.
> **This is exactly why the cap must ship with the overage valve.**

Note that `industry_cc_floor` is currently **slack by 3,153 kt (2040) and
2,004 kt (2050)** [V] — the model chooses 62 % more industrial capture than it is
forced to, so the floor is not what drives today's result and removing it would
change nothing. It still bounds the cap design.

---

## 10. Staged test sequence

Drawn from the catalogue of every infeasibility this model has hit since August
(logs `2026-08-14` → `2026-09-15`, `docs/renewable-potentials.md` §9.6–9.7, and
§12 below). Run at **6 h** on **`scen_central`**, full myopic chain, one change
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

## 11. Points to align with TIMES

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

## 12. History: the 2026-08-30 revert and what it taught

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
