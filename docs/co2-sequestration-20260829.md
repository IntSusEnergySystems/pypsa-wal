# CO₂ sequestration limits — where the number comes from, and what replaced it

**Written 29 Aug 2026.** Follows recommendation 2 of the
[`scen_demande_haute` @ 2010, 1 h solve log](logs/2026-08-26_scen_demande_haute_2010_1h.md)
§11.14 C and item 2 of [temporary_improvement_plans.md](temporary_improvement_plans.md)
("give Belgium a CO₂ sink first"). Companion to
[ccs_alignment.md](ccs_alignment.md), which describes the CCS *technologies*;
this file is about the *limit* on how much of their output can be buried.

> ## Status: REVERTED on 30 Aug 2026
>
> The change described below was implemented in `config/config.walloon.yaml` on
> 29 Aug and **never solved**. When it was first run, on 30 Aug, the 2040 horizon
> failed with `Numerical trouble encountered` / *"Model may be infeasible or
> unbounded"*. The config is back to the pooled global cap; the analysis in this
> file stands, and the underlying criticism of the number is still valid, but the
> replacement does not work as written. See [§9](#9-why-it-was-reverted).
>
> Every number describing model behaviour below is from the 26 Aug run, i.e.
> *before* this change and before the revert.

**One-paragraph summary.** The binding constraint on carbon capture in every
horizon of the 26 Aug run was `co2_sequestration_limit`, a single pooled
ceiling over the whole network taken from
`sector.co2_sequestration_potential`. That number is an unsourced whole-Europe
scalar that PyPSA-Eur has changed twice without ever citing a source or writing
a release note, and the Walloon overlay halved it again with no rationale
beyond a `* 0.5` in a comment. It is not a geological potential; the only
published justification for its ancestor (200 Mt/a) sizes it from *European
process emissions*, which is a demand argument, not a supply one. Applying a
Europe-sized number to a six-country model made it bind at **360 EUR/t**. It is
now demoted to a deployment ramp for 2025/2030 and a non-binding backstop after
that, and the per-node CO₂StoP store — the layer that actually encodes geology —
does the limiting. Belgium's zero is **unchanged and still an open item**; this
change makes the constraint that was masking it go away, it does not give
Wallonia a sink.

| Change | File | Status |
|---|---|---|
| Global cap → deployment ramp (0/0/60) then non-binding (1000) | `config/config.walloon.yaml` | **reverted 30 Aug** |
| `regional_co2_sequestration_potential.max_size` 25 → 2.5 Gt | `config/config.walloon.yaml` | **reverted 30 Aug** |
| This write-up | `docs/co2-sequestration-20260829.md` | kept, with §9 added |

---

## 1. What the model actually contains — two independent layers

They are easy to confuse because their config keys differ by one word.

### Layer A — one pooled global constraint

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

### Layer B — per-node store capacity from CO₂StoP

`sector.regional_co2_sequestration_potential` drives
[`build_clustered_co2_sequestration_potentials.py`](../scripts/build_clustered_co2_sequestration_potentials.py),
whose output is consumed in
[`prepare_sector_network.py:829`](../scripts/prepare_sector_network.py:829):

```python
e_nom_max = (e_nom_max.reindex(spatial.co2.locations)
             .fillna(0.0).clip(upper=max_size * 1e3).mul(1e6) / years_of_storage)
```

The clustered file for the 26 Aug run
(`resources/*/scen_demande_haute/co2_sequestration_potential_base_s_adm.csv`,
byte-identical to the `walloon-model` copy) has **three rows**:

| node | CO₂StoP Mt | after clip | ÷ 25 y → Mt/a |
|---|---:|---:|---:|
| GB | 54 580 | 25 000 (old) | **1 000** |
| DE | 1 979 | 1 979 | 79.1 |
| NL | 227 | 227 | 9.09 |
| BEWAL, BEVLG, BEBRU, FR, LU | *absent* | `fillna(0.0)` | **0** |

Belgium's zero is a `fillna` on a missing row, not a decision. It is missing
because `include_onshore: false` restricts the overlay to **offshore** regions
and Belgium's North Sea EEZ carries no CO₂StoP site clearing `min_size`.

### Units gotcha in that block

The two size keys are in **different units**, in the same dict, upstream:

| key | compared against | unit |
|---|---|---|
| `min_size: 3` | `gdf[attr].sum(axis=1)` and the regional total, both in Mt | **Mt** |
| `max_size: 25` | the same series, but via `max_size * 1e3` | **Gt** |

The comment shipped with the original commit said "Gt" for both and carried a
literal `TODO research suitable value` on `max_size`; current
`config.default.yaml` has dropped the comments and kept the values. Worth
remembering before anyone "fixes" `min_size: 3` thinking it means 3 Gt.

---

## 2. Provenance of the upstream number

All commits below are in this repository's history (it carries the full
upstream history).

| When | Commit | Value | Stated justification |
|---|---|---|---|
| 9 Dec 2020 | `3ff669b0` (T. Brown) | `200` flat | inline comment `#MtCO2/a sequestration potential for Europe`. Nothing else. |
| 20 Aug 2024 | `dcc84dfb` (lisazeyen, "update config") | `0/0/50/100/200/200/200` | none. Shipped indented one level too deep, inside `regional_co2_sequestration_potential`; un-nested the same day by `5fb89068` ("right intend for co2 seq potential"). Release note for [PyPSA/pypsa-eur#1228](https://github.com/PyPSA/pypsa-eur/pull/1228) documents the *mechanism* ("Add option to specify carbon sequestration potentials per investment period"), not the values. |
| 11 Jul 2025 | `e43746df` (F. Neumann, **"prepare release v2025.07.0 (#1753)"**) | `0/0/40/100/180/250/250` | none. A release-housekeeping commit that also touched CI and `conf.py`. **No entry anywhere in `doc/release_notes.rst`** for the change. |

`git blame -L 946,953 config/config.default.yaml` shows the split directly: the
2030, 2040, 2045 and 2050 values are `e43746df`, the rest `5fb89068`.

**Documentation coverage today.** [`doc/configuration.rst:609`](../doc/configuration.rst:609)
renders the `sector` block from the JSON schema; the schema's entire
description ([`config/schema.default.json:4670`](../config/schema.default.json:4670))
is *"The potential of sequestering CO2 in Europe per year and investment
period."* — no unit, no default, no source, unlike its neighbours
`co2_sequestration_cost` and `co2_sequestration_lifetime`. There is no
`configtables` entry and nothing in `doc/sector.rst` or `doc/supply_demand.rst`.
The sibling regional option was flagged *"The defaults are preliminary and will
be validated the next release"* in the v0.8.0 notes
([`doc/release_notes.rst:2929`](../doc/release_notes.rst:2929)); no follow-up
note ever appeared.

**The one real justification, and what it is.** The 200 Mt/a ancestor is
explained in the papers that use it — [Neumann et al., *H₂ and CO₂ network
strategies for the European energy system*, Nature Energy
(2025)](https://www.nature.com/articles/s41560-025-01752-6) and its
[preprint](https://arxiv.org/html/2407.18653v2): ~153 Mt/a of European
industrial **process** emissions after industrial transformation, plus ~47 Mt/a
of headroom for negative emissions. That answers *"how much would we need to
bury?"*, not *"how much can be buried?"* It is a demand-side sizing convention,
it is not geology, and it does not cover the current 40/100/180/250 ramp, which
post-dates it.

---

## 3. What it did to the 26 Aug run

From the [solve log](logs/2026-08-26_scen_demande_haute_2010_1h.md) §11.5 and
§11.14 C:

| horizon | Walloon overlay cap | dual | note |
|---|---:|---:|---|
| 2025 | 0 | 374 EUR/t | binds; limit is zero |
| 2030 | 20 | 113 EUR/t | binds |
| 2040 | 90 | 139 EUR/t | binds |
| 2050 | 125 | **360 EUR/t** | binds |

Binding in **every** horizon, and one of the largest single contributors to the
1 272 EUR/t effective Walloon carbon price in 2050. Meanwhile the geological
layer had ~1 088 Mt/a of unused headroom across GB, DE and NL: the pooled cap,
not the geology, was the limiter — and it was set by a number sized for a
continent.

It also distorts the CCGT-CC question. `temporary_improvement_plans.md` item 2
reason 3 — *"2040's European sequestration cap is tighter (90 vs 125 Mt)"* — is
this constraint, not a physical fact about 2040.

---

## 4. The decision

Two ways out were on the table:

- **A.** Re-derive the global cap for the modelled subset, the way Neumann et al.
  derived 200 Mt/a for Europe — i.e. from this subset's process emissions.
- **B.** Drop the global cap to a non-binding value and let the CO₂StoP
  `e_nom_max` layer do the limiting.

**B was chosen** (29 Aug, on instruction). It removes an arbitrary number
instead of replacing it with a differently arbitrary one, and it puts the
geological limit in the layer that actually models geology, per node, where the
CO₂ network has to reach it and pay for it.

B taken literally has two holes, and both are patched here rather than left to
surface in the next solve:

1. **CO₂StoP is static geology with no time dimension.** A pure layer-B model
   would let 2025 bury 188 Mt when the six modelled countries inject
   approximately nothing today. The global series is therefore *kept*, but only
   as a **deployment ramp** — relabelled, not re-derived as a potential.
2. **The 25 Gt clip makes GB a carbon dump.** `max_size: 25` (Gt) annualised
   over 25 years is **1 000 Mt/a for GB alone** — 20× the UK's own
   >50 Mt/a-by-2035 target. Handing that to a model with a 1 272 EUR/t shadow
   price would have produced a worse artefact than the one being removed.

---

## 5. What is now in `config/config.walloon.yaml`

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

`regional_co2_sequestration_potential` is a **partial** override — Snakemake
deep-merges configfiles, so `enable`, `attribute`, `include_onshore`,
`min_size` and `years_of_storage` still come from `config.default.yaml`. (Same
pattern as the existing `retrofitting: interest_rate` override.) Verified by
merging both files and printing the result.

**Global series — sourced, and labelled for what it is.**

| year | Mt/a | basis |
|---|---:|---|
| 2020, 2025 | 0 | No CO₂ storage in operation in BE, DE, FR, GB, LU or NL. Northern Lights, the one European site injecting at scale, is Norwegian and outside the model. |
| 2030 | 60 | EU Net-Zero Industry Act: **50 Mt/a of EU injection capacity by 2030**, concentrated in North Sea projects that are mostly inside the modelled set (Porthos, Aramis, German offshore) — take ~35. Plus the UK's **20–30 Mt/a by 2030** target — take ~25. |
| 2035 onward | 1000 | Non-binding backstop, ~5× what the stores allow. It exists only so that flipping `regional_co2_sequestration_potential.enable: false` (which sets every `e_nom_max` to `inf`) cannot silently produce an unlimited sink. |

**Resulting per-node ceilings** (unchanged for DE and NL; GB clipped harder):

| node | Mt/a before | Mt/a after |
|---|---:|---:|
| GB | 1 000 | **100** |
| DE | 79.1 | 79.1 |
| NL | 9.09 | 9.09 |
| BEWAL / BEVLG / BEBRU / FR / LU | 0 | 0 |
| **total** | **1 088** | **188** |

**Is 188 Mt/a for six countries too generous?** Against a "share of Europe"
heuristic, yes — six countries are roughly a third of EU+UK emissions, so a
share of the 200 Mt/a Europe convention would be ~70 Mt/a. That heuristic is
the wrong test, and rejecting it is the point of option B: GB and DE hold most
of North-West Europe's offshore storage, so a subset containing both **should**
hold more than its population share. The binding question is the injection
*rate*, and 100 Mt/a for GB in 2050 is 2× the UK's own 2035 target — generous,
defensible, and no longer absurd.

---

## 6. What this does **not** fix

1. **Belgium still has zero storage.** `e_nom_max = 0` for BEWAL, BEVLG and
   BEBRU (and FR, LU) is untouched. It remains a `fillna(0.0)` on a missing
   CO₂StoP row rather than a documented scenario choice. Item 2 option C of
   [temporary_improvement_plans.md](temporary_improvement_plans.md) — a
   documented Belgian `e_nom_max`, or a priced CO₂ export route to NL/NO — is
   **still open and still the more important of the two**. What this change
   does is remove the constraint that was masking it: Walloon CCS is now
   limited by "Belgium owns no sink and must pay to ship CO₂ to DE/GB", which
   is a real, arguable statement, instead of by a continental scalar.
2. **2030 is still permissive.** 60 Mt/a is a defensible ceiling but the model
   also has to reach it through the CO₂ network, so effective 2030 storage will
   be whatever capture economics allow below that. If the next solve builds
   implausible 2030 CCS, this number — not the geology — is the dial.
3. **`years_of_storage: 25` is untouched** and is upstream's arbitrary
   stock→rate conversion. It is doing real work here (it is what turns DE's
   1 979 Mt into 79 Mt/a) and deserves its own look.
4. **Upstream is still unsourced.** `config/config.default.yaml` keeps
   40/100/180/250 for anyone running a non-Walloon config. Not changed on
   purpose: it is the PyPSA-Eur default and changing it would affect every
   config that does not override, exactly as with `dac`
   ([ccs_alignment.md](ccs_alignment.md) §8).
5. **`config.scen_base.yaml`, `config.scen_corrige.yaml`, `config.scen_suff.yaml`
   are not touched.** They are resolved snapshots, not the Walloon Snakemake
   overlay, and they still carry the halved series.

---

## 7. Verification

- Merged `config.default.yaml` + `config.walloon.yaml` the way Snakemake does
  and confirmed the partial `regional_co2_sequestration_potential` override
  keeps the other five keys, and that the resulting per-node ceilings are
  GB 100 / DE 79.15 / NL 9.09 Mt/a, total 188.2.
- `snakemake --configfile config/config.walloon.yaml -n` — DAG builds, config
  validation passes, and `build_clustered_co2_sequestration_potentials` is in
  the job list, so the `max_size` change will propagate on the next run.

## 8. Expected effect on the next solve

Directional, not predicted:

- `co2_sequestration_limit` should stop binding from 2035 onward; its dual
  (360 EUR/t in 2050) should go to zero and the 2050 effective Walloon CO₂
  price should fall by roughly that much.
- 2025 is unaffected — the cap is still 0, and its 374 EUR/t dual is now
  correctly read as "no storage exists yet", not as a modelling artefact.
- CCGT-CC in 2040 becomes eligible on the sink side. If it still does not
  build, item 2's diagnosis narrows to the missing retrofit link and the
  Belgian zero, which is exactly the discrimination that item asked for.
- Watch GB: it now absorbs whatever the subset captures, at 100 Mt/a. If GB
  runs to 100 Mt/a in 2050 the binding constraint has simply moved, and
  `max_size` is the next thing to argue about.

## 9. Reverting

One line each. To restore the previous behaviour exactly, put back

```yaml
  co2_sequestration_potential:
    2020: 0
    2025: 0
    2030: 20
    2035: 50
    2040: 90
    2045: 125
    2050: 125
```

and delete the `regional_co2_sequestration_potential:` block (which restores
`max_size: 25` from `config.default.yaml`, i.e. GB back to 1 000 Mt/a).

---

## Sources

- [PyPSA-Eur release notes](https://pypsa-eur.readthedocs.io/en/latest/release_notes.html)
  and [configuration docs](https://pypsa-eur.readthedocs.io/en/latest/configuration.html)
- [PyPSA/pypsa-eur#1228](https://github.com/PyPSA/pypsa-eur/pull/1228) — per-period sequestration potentials
- [Neumann et al. (2025), *H₂ and CO₂ network strategies for the European energy system*, Nature Energy](https://www.nature.com/articles/s41560-025-01752-6) — the 200 Mt/a rationale
- [arXiv:2407.18653](https://arxiv.org/html/2407.18653v2) — preprint of the above
- [CO₂StoP, European CO₂ storage database](https://setis.ec.europa.eu/european-co2-storage-database_en) — the layer-B data
- [EU Net-Zero Industry Act: 50 Mt/a CO₂ injection capacity by 2030](https://www.newcivilengineer.com/latest/eu-targets-50m-tonnes-per-year-of-co2-storage-by-2030-12-02-2024/)
- [UK CCUS targets: 20–30 Mt/a by 2030, >50 Mt/a by 2035 (CCSA)](https://www.ccsassociation.org/news/government-commits-to-establishing-carbon-capture-and-storage-industry/)
- [North Sea Transition Authority — UK Continental Shelf storage capacity](https://www.nstauthority.co.uk/the-move-to-net-zero/ccs/)

---

## 9. Why it was reverted

Written 30 Aug 2026, after the first attempt to solve the change.

### 9.1 What happened

The 2040 horizon would not converge. Gurobi ran the barrier to completion and
returned `Numerical trouble encountered`, with the message *"Model may be
infeasible or unbounded. Consider using the homogeneous algorithm"*. Dual
infeasibility parked at `4.19e-04` and complementarity plateaued instead of
falling. 2025 and 2030 were unaffected — consistent with the change, whose 2025
value is unaltered (0) and whose 2030 value moves only 20 → 60.

### 9.2 The cap value is not a threshold

The obvious reading — that lifting the cap forces the optimiser to reach GB's
100 Mt of storage over the `CO2 pipeline … -> GB` links, which are extendable
with `p_nom_max = inf` across 495–802 km of sea at 242–333 kEUR/MW — predicts a
clean threshold at DE + NL = 88.2 Mt/a. It is wrong. Holding everything else
fixed and varying only `sector.co2_sequestration_potential` at 2040:

| cap | outcome |
|---:|---|
| 85 Mt/a | **FAIL** — 252 iter / 3086 s |
| 90 Mt/a | optimal — 263 iter / 3650 s, objective 3.12850428e+11 |
| 100 Mt/a | **FAIL** — 191 iter / 2360 s |
| 1000 Mt/a | **FAIL** — 288 iter / 3754 s |

A structural threshold cannot be non-monotone. The cap value perturbs a model
that is numerically fragile at 2040; 90 Mt/a is simply the point that happens to
land well, and it is the value this file's predecessor already carried.

`max_size` is exonerated separately: at a 90 Mt/a cap, `max_size` 2.5 and 25 give
byte-identical results — same objective to nine figures, same 263 iterations,
same 4506.89 work units. With a binding global cap below GB's ceiling the
regional clip never binds, so that half of the commit changes nothing.

### 9.3 What is still true

* The criticism of `sector.co2_sequestration_potential` in §§1–8 stands: it is an
  unsourced whole-Europe scalar, upstream changed it twice without a release
  note, the `* 0.5` is justified only by a comment, and it binds at up to
  360 EUR/t. Improvement-plan item 2 stays open.
* The cap is not decorative. At 90 Mt/a it binds at **100 %** utilisation with a
  shadow price of **68.6 EUR/t**, and the 2040 vintage splits DE 51.15 / NL 9.09
  (saturated) / GB 0.70 Mt against ceilings of 79.15 / 9.09 / 100.
* Belgium's `e_nom_max = 0` is still a `fillna(0.0)` on a missing CO2StoP row
  rather than a documented choice — item 2.C, untouched by any of this.
* Every `CO2 pipeline … -> GB` link being freely extendable with
  `p_nom_max = inf`, when no such pipeline exists or is planned, is a real
  modelling artefact of PyPSA-Eur's `co2_network: true`. It is not what broke
  2040, but it is worth bounding.

### 9.4 What a second attempt would need

Not another cap value — the table above rules that out. Either bound the CO₂
transport layer so the relaxed problem is well posed, or establish why the 2040
model is fragile in the first place, which is a separate investigation. Sourced
anchors for a deployment ramp, if one is wanted later: EU Net-Zero Industry Act
50 Mt/a by 2030 (binding); Industrial Carbon Management Strategy ambition
~250 Mt/a EEA-wide by 2040; 250 Mt/a stored EU-wide by 2050 in the 2040
climate-target communication; UK 20–30 Mt/a by 2030 (conceded unachievable in
Dec 2024), ">50 Mt/a by 2035", up to 170 Mt/a by 2050 as ambition against
scenario figures nearer 30/40/60 Mt/a at 2035/2040/2050; 18.7 Mt/a past FID
Europe-wide today.
