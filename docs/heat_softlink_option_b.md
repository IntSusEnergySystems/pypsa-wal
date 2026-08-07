# The Walloon heating soft-link — option B′, reconstructed hourly profiles

**Status:** design + implementation log. **Started:** 2026-08-07. **Branch:**
`heat-softlink-option-b` (pypsa-wal and TIMES_PyPSA).

**Companion documents**
* [`times-heating-softlink-options.md`](times-heating-softlink-options.md) — the
  original analysis (why A and B were rejected, C recommended).
* [`heat_soft_linking.md`](heat_soft_linking.md) — what option C actually turned
  into once it met the real model, including the two things that went wrong.
* [`heat_softlink_option_comparison.md`](heat_softlink_option_comparison.md) —
  the head-to-head, written once both chains have run.

**Reference scenario:** `scen_demande_haute_v01_260727_fix_nuc_2807.vd`,
`config/config.times-pypsa.yaml`, 6 h sector snapshots.

---

## 0. Why we are doing this again

Option C works — the mix transfers, the chain completes, the numbers are in
`heat_soft_linking.md` §8.6 — but it needed four mechanisms that exist only to
stop it breaking:

| Mechanism | Why it had to exist |
|---|---|
| `share` vs `absolute` mode | absolute targets over-determine the LP and hand the ~4 % non-TIMES residual to the cheapest technology |
| `tolerance: 0.05` | an equality on six groups plus the heat balance is one equation too many |
| `zero_target: forbid` | `≥ 0` is vacuous, so a retired technology needs a *different* sense |
| `penalty: 1000` + one slack variable per group | the TIMES 2040 gas floor and PyPSA's Walloon CO₂ cap are jointly infeasible, and an infeasible sector LP triggers a Gurobi IIS that never returns |

and even then the answer is a *bound*, not the TIMES mix: four of six groups sit
exactly on their tolerance bound, biomass and resistive float above their floors
because the `≥` senses permit it, and the realised shares are 5 % away from TIMES
by construction.

Option B′ asks a different question. Instead of *bounding annual energies and
letting PyPSA choose the hours*, it **reconstructs the hourly heat profile of each
TIMES technology group and pins the dispatch to it**. The mix is then exactly
TIMES's, at every hour, on every bus, with no tolerance, no senses, no modes and
no zero-target special case — because a group whose TIMES share is zero simply
gets a zero profile.

The price is the hourly freedom to substitute between heating technologies. §2
argues that freedom is largely a modelling artefact, and measures what is left.

---

## 1. The design

### 1.1 What gets reconstructed

TIMES-WAL has no sub-annual heat representation at all (every heat commodity is
`ANNUAL` — `times-heating-softlink-options.md` §1.3). So there is no TIMES profile
to import. B′ builds one from what each model is actually good at:

* **TIMES supplies the composition** — `share_g`, the fraction of Walloon
  decentral appliance heat delivered by technology group *g*, already in
  `heating_targets_{year}.csv`.
* **PyPSA supplies the shape** — `L_b(t)`, the hourly heat load of bus *b*
  (atlite HDD × BDEW intraday, already rescaled to the TIMES annual total by
  `write_wallon_heat_demands`).

For every bus `b ∈ {rural, urban decentral}` of the node and every snapshot `t`:

```
solar thermal (the one group with a dispatch ceiling):

    rhs_solar,b(t) =  s_solar · E_b · a_b(t) / Σ_t w_t a_b(t)

everything else, on the residual:

    rhs_g,b(t)     =  s_g /(1 − s_solar) · ( L_b(t) − rhs_solar,b(t) )
```

with `E_b = Σ_t w_t L_b(t)` the bus's annual heat, `a_b(t)` the solar-thermal
collector availability (`p_max_pu`) and `w_t` the snapshot weighting.

Two identities hold **exactly**, and they are the whole point of writing it this
way:

```
Σ_g  rhs_g,b(t)   =  L_b(t)          for every b and every t   (hourly closure)
Σ_t  w_t rhs_g,b(t) =  s_g · E_b                                (annual shares)
```

The first makes the heat-bus balance close by construction, so nothing on the bus
has to absorb a mismatch. The second means the annual mix is TIMES's exactly —
not TIMES's ±5 %.

> **One nuance about "the mix is TIMES's at every hour".** It is, in the sense
> that every group's dispatch is a fixed multiple of a known profile. It is not,
> in the sense of "every group holds a constant *share* at every hour": solar
> thermal necessarily follows the sun, so its share swings between 0 at night and
> a few per cent at midday, and the other groups' shares move by the same small
> amount in the opposite direction (`s_g/(1−s_solar)` of the residual, a constant
> ratio *among themselves*). At a TIMES solar share of 0.3–0.5 % this is a
> sub-percentage-point effect, but the honest statement is *"each group's hourly
> dispatch is its TIMES share of the residual load"*, not *"each group's hourly
> share is constant"*.

### 1.2 The constraint

For every group except one (§1.3) and every decentral bus:

```
Σ_{c ∈ g,b}  κ_c · x_c(t)   +   (rhs_g,b(t) / E_g) · u_g   ==   rhs_g,b(t)

objective  +=  penalty · Σ_g u_g
```

* `κ_c` is the heat-injection coefficient, taken unchanged from option C
  (`+efficiency` for a boiler or resistive heater whose `bus1` is the heat bus,
  `−1` for the reversed heat-pump links whose `bus0` is the heat bus, `+1` for the
  solar-thermal `Generator`). Verified against the solved networks; see
  `heat_soft_linking.md` §3.4.
* the sum runs over **every vintage** of every carrier in the group, so the
  brownfield stock and the new build share the profile and no arbitrary vintage
  allocation is needed.
* `u_g ∈ [0, E_g]` is the annual heat, in MWh_th, that the group could **not**
  deliver. It is the only relaxation in the whole formulation, it is one scalar
  per group, and it is the diagnostic (§1.4).

### 1.3 The absorber

One group is deliberately **not** pinned. The heat-bus balance then determines it:

```
heat_abs,b(t) = L_b(t) − Σ_{g≠abs} heat_g,b(t)  (+ vent, DAC and net tank charge)
              = rhs_abs,b(t) + Σ_{g≠abs} (rhs_g,b(t)/E_g)·u_g  (+ the same terms)
```

so with `u = 0` it is pinned by arithmetic rather than by a row. This is not
cosmetic:

* it removes a linearly-redundant equality from the LP (the six pinned rows would
  sum to the bus balance minus the vent/DAC/storage terms), which is exactly the
  degeneracy a barrier solver handles worst;
* it leaves the heat vent, the DAC link and the water tanks with their degrees of
  freedom intact rather than forcing them to net zero, so B′ does not *forbid*
  decentral storage — it just gives it nothing to arbitrage (§2);
* it gives the relaxation somewhere physical to go: heat TIMES's fuel mix cannot
  supply is electrified instead, which is both the direction PyPSA prefers and a
  statement a reader can check.

**The absorber is the `heat pump` group by default.** It is the only group with
no fuel-supply or CO₂ limit upstream of it — a free `gas boiler` group would be
squeezed by the Walloon CO₂ cap and then could not close the residual, which is
the infeasibility we are trying to design out.

### 1.4 Feasibility, and where it can still fail

**On the heat bus, B′ cannot go infeasible.** `rhs` is a feasible point by
construction: every pinned technology is extendable with `p_nom_max = inf` and no
dispatch ceiling, except solar thermal, which is pinned to a multiple of its own
availability profile and therefore always attainable. This is a stronger statement
than option C could make, and it is structural rather than argued.

**Upstream of the heat bus it can, and in 2040 it will.** The failure mode is
known and quantified from the option-C chain: the Walloon CO₂ cap and the EU
solid-biomass limit both already bind in 2040 before any heat constraint exists,
and option C could only deliver 4.48 of the 4.69 TWh_th biomass floor. B′ asks for
the full `s_biomass · E` = **4.94 TWh_th**, i.e. ~0.46 TWh_th more than option C
managed. So the relaxation is not optional in 2040.

Three escape hatches, in increasing order of how much they give away:

| # | Knob | Effect |
|---|---|---|
| 1 | `penalty` (default **1000 EUR/MWh_th**) | the group relaxes *proportionally over the whole year* — "TIMES's biomass fleet is 5 % smaller than TIMES says" — and `u_g` reports how much. Set `0` for hard constraints and no relaxation variables at all. |
| 2 | `free_groups: [gas boiler, biomass boiler]` | those groups are not pinned; they pool with the absorber and split their combined residual freely. This is an option-C-style degree of freedom, restricted to the groups that need it. |
| 3 | `enable: false` | back to the legacy demand-only transfer. |

and one guard that is not a knob: a **pre-solve budget report** (§1.6) that prints
the fuel and CO₂ the pinned profiles imply, against the limits already in the
network, *before* Gurobi is called.

### 1.5 What B′ deliberately does not touch

* **District heating.** The urban-central bus keeps its full freedom, exactly as
  in option C and for the same four reasons (`heat_soft_linking.md` §7): DAC
  withdraws more heat than the DH load, CHP heat is welded to CHP electricity,
  the pit store re-injects, and 73 % of the TIMES 2050 DH supply has no PyPSA
  component. §2 shows this is also where *all* the real thermal-storage
  flexibility lives — 0.13 → 2.73 TWh_th cycled per year against 3–17 **GWh** on
  the decentral buses. Pinning it would destroy something real. Not pinned.
* **The base-year stock substitution** and the **urban/rural split
  harmonisation**. Both are independent of the constraint mechanism, both are
  already verified, and both stay exactly as option C left them.
* **Capacity.** `p_nom` remains endogenous everywhere. B′ pins dispatch, not iron;
  PyPSA still sizes each fleet on the peak of its own profile.

### 1.6 Diagnostics

Two artefacts, both cheap and both aimed at the failure modes that cost the most
time in option C:

* `heating_profiles_{year}.csv` — the reconstructed profiles, per bus and group,
  written next to the solve log. This is the "reconstructed time profile" the
  option is named after, and it is inspectable without re-running anything.
* a **pre-solve budget report** in the solve log: the annual fuel per carrier and
  the CO₂ the pinned profiles imply, against `co2_limit_per_country{node}` and the
  node's solid-biomass supply. A run that is going to be infeasible says so in the
  first seconds instead of after a 4 h barrier.

---

## 2. The flexibility question, measured

The objection to any B-family option is that it freezes hourly dispatch and so
throws away the flexibility that motivated coupling an hourly model in the first
place. That objection has to be answered with numbers, not intuition. All figures
below are read off the eight solved networks of the option-C comparison
(`results/_heat_softlink_comparison/{before,after}`), full 6 h resolution.

### 2.1 Decentral thermal storage is not merely small — it is absent

| TWh_th cycled per year | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| **decentral** water tanks (rural + urban decentral), option C | 0.0076 | 0.0107 | 0.0173 | 0.0174 |
| … as % of decentral heat supplied | 0.03 % | 0.04 % | 0.07 % | 0.08 % |
| **urban-central** storage (tanks + PTES) | 0.204 | 0.484 | 1.257 | 2.733 |
| ratio central : decentral | **27×** | **45×** | **73×** | **157×** |

The optimised size of the decentral stores says the same thing more bluntly: in
the 2050 network `BEWAL rural water tanks` is **0.131 MWh** and
`BEWAL urban decentral water tanks` **0.130 MWh** — 130 kWh of thermal storage for
the whole of decentral Wallonia. The decentral heat vent is **exactly 0.000 TWh**
in all eight solves and decentral DAC is 1 × 10⁻⁵ TWh.

**Conclusion:** on the decentral buses there is no storage flexibility to lose.
The user's prior was right, and it is confirmed in both the free and the
constrained chains. The flexibility that must survive is the district-heating pit
store — and B′ does not touch the urban-central bus at all.

### 2.2 The hourly *mix* does move — and that is the thing worth arguing about

Energy-weighted mean absolute deviation of each group's hourly share from its own
annual share, aggregated (0 % = the mix is already constant, so B′ removes
nothing):

| | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| legacy transfer (`before`) | 27.3 % | 23.1 % | 19.0 % | 15.6 % |
| option C (`after`) | **34.6 %** | **27.9 %** | **26.2 %** | **31.6 %** |

So PyPSA does swap technologies hour by hour, and option C makes it swap *more* —
which is what an annual constraint does: it concentrates each technology into its
cheapest hours. B′ sets this to 0 % by construction.

**Is that a loss?** Two readings, and the honest answer needs both.

*Against B′:* a heat pump that can back off in the coldest, most expensive hours
and let a boiler cover the peak is a genuine system service — bivalent heating is
real, and this is exactly the kind of thing an hourly model exists to see.

*For B′:* the mechanism PyPSA uses to deliver it is not. On a single decentral
heat bus every Walloon dwelling shares one gas boiler, one oil boiler, one heat
pump and one resistive heater, and the model may re-allocate heat between them
freely at zero cost and with no regard for which dwelling owns which appliance.
A real dwelling stock cannot do that: a house with a gas boiler runs the gas
boiler whenever it needs heat. The 26–35 % hourly mix swing is therefore mostly a
**perfect-substitutability artefact of the single-bus representation**, and
holding the mix at the stock composition is *closer* to the physics than letting
it float.

What B′ genuinely gives up is narrower than "flexibility": it is the heat pumps'
ability to shift their electricity draw in time. With 130 kWh of decentral storage
that ability is currently worth approximately nothing — but it would matter in a
future study that gave Walloon dwellings real thermal storage or DSM, and that is
the case in which option C should be preferred. Recorded as arbitrage **A7**.

---

## 3. Arbitrages

Every judgement call, so it can be reviewed on its own. Numbered for reference
from the comparison document.

| # | Choice | Alternative rejected | Why |
|---|---|---|---|
| **A1** | Pin the mix **hourly**, at the TIMES annual share, on each bus separately | pin only the annual energy (that is option C) | the whole point of B′; per-bus rather than summed over both buses stops the model sorting heat pumps onto the rural bus (where ground-source is available) and gas onto urban decentral, which would be a spurious spatial result driven by the urban/rural labelling artefact |
| **A2** | The shape is **PyPSA's own heat load profile**, identical for every group | a per-technology shape | TIMES has no sub-annual heat data whatsoever, so any per-technology shape would be invented. The one exception is forced by physics — see A3 |
| **A3** | **Solar thermal follows its own `p_max_pu`**, and the other groups share the *residual* `L_b(t) − rhs_solar,b(t)` | give solar the load shape like everything else | a load-shaped solar profile peaks in January when the collector delivers nothing: instantly and trivially infeasible. Checked on the 2050 network: `min_t (L_b(t) − rhs_solar,b(t)) = +218 MW`, so the residual is always positive |
| **A4** | The TIMES shares are applied to the **whole decentral load**, including the ~4 % that is cooking fuel, tertiary other-energy and re-bussed agriculture heat | apply the TIMES absolute energies and leave the residual free | identical to option C's `share` mode and for the same reason (`heat_soft_linking.md` §3.1): absolute targets hand that residual to whichever technology is cheapest and corrupt the mix. Keeping the convention also makes B and C directly comparable |
| **A5** | **One group (the heat pump) is left unpinned** and absorbs the bus residual | pin all six | removes a linearly-redundant equality, keeps vent/DAC/storage degrees of freedom, and gives the relaxation a physical destination. Heat pumps because they are the only group with no fuel or CO₂ limit upstream |
| **A6** | Relaxation is **one scalar per group**, spread over the year in proportion to the profile, priced at 1000 EUR/MWh_th | per-snapshot slack; or hard constraints only | a per-snapshot slack is 2 × 6 × T variables and would let the model relax exactly in the expensive hours — i.e. re-create the substitution freedom B′ exists to remove. A scalar says "TIMES's biomass fleet is 5 % smaller than TIMES says", which is a statement about the fleet, not about a Tuesday. Hard constraints are still available (`penalty: 0`) and are correct when you *want* the run to stop on a disagreement |
| **A7** | District heating keeps its full hourly freedom | pin it too | §2.1: 27–157× more storage cycling than the decentral buses, and the four structural objections of `heat_soft_linking.md` §7 are unchanged. If the DH supply mix is ever transferred it should be with option C's annual constraint, not with a pinned profile |
| **A8** | Option C's code stays in the branch, defaulting to **off**, and enabling both at once raises | delete option C from the B branch | the comparison in §5 needs `legacy` / `option C` / `option B′` from one checkout and one set of built resources. Branch-switching mid-chain is how stale `resources/` gets mixed into a comparison |
| **A9** | Profiles are computed at solve time from the network, not in a separate build rule | a `build_heating_profiles` rule writing a CSV | everything needed (`loads_t.p_set`, the solar `p_max_pu`, the snapshot weightings) is already in the network at `extra_functionality` time, and a separate rule would have to reproduce the load *after* `write_wallon_heat_demands` rescaled it. The profiles are still exported to CSV for inspection — as an output, not an input |
| **A10** | One mix for both buses, not a per-bus TIMES mix | give `rural` the TIMES residential-rural mix and `urban decentral` the rest | the TIMES rural/urban split is a per-process labelling convention, not a TIMES result (`times-heating-softlink-options.md` §1.2(d)). Using it per bus would re-import exactly the artefact both options were designed to cancel |

---

## 4. Implementation pathway

Milestones, with status. **This section is updated as work lands.**

| # | Milestone | Status |
|---|---|---|
| M0 | Branches: `heat-softlink-option-c` (current tree committed) and `heat-softlink-option-b` from it, in both repos; `master`/`main` untouched | ✅ 2026-08-07 |
| M1 | Evidence: flexibility audit (§2), network census, payload check | ✅ 2026-08-07 |
| M2 | Design document (this file) | ✅ 2026-08-07 |
| M3 | `times_heat_profiles.py`: profile reconstruction + constraints + relaxation + CSV export | ✅ 2026-08-07 |
| M4 | Pre-solve budget report and the infeasibility guards (§1.6, §6) | ✅ 2026-08-07 |
| M5 | Tests: closure, shares, sign conventions, solar feasibility, vintages, relaxation, absorber — `test/test_times_heat_profiles.py`, **30 passed**; option C's 42 and the library's 151 still green | ✅ 2026-08-07 |
| M6 | Single-horizon 2025 solve at full resolution, all constraints | ✅ 2026-08-07, §5.1 |
| M7 | Full myopic chain 2025 → 2050 | ☐ |
| M8 | Comparison document, B′ vs C vs legacy | ☐ |
| M9 | Push both branches | ☐ |

### What landed, and where

| Piece | File | New / changed |
|---|---|---|
| Profile reconstruction, constraints, relaxation, budget report, CSV export | `scripts/walloon_scripts/times_heat_profiles.py` | **new**, ~470 lines |
| `profile` option block, validation, mutual exclusion with `energy_mix` | `scripts/walloon_scripts/times_heat_softlink.py` | changed (additive) |
| Dispatch to whichever mechanism is on | `data/custom_extra_functionality.py` | changed |
| `heating_profiles` declared output (shadow-safe) | `rules/solve_myopic.smk` | changed |
| Config blocks | `config/config.times-pypsa.yaml` (B′ **on**, C off), `config/config.walloon.yaml` (both off) | changed |
| Three-phase driver: `before` / `after` / `option_b`, one overlay each | `scripts/walloon_scripts/run_heat_softlink_comparison.sh` | changed |
| Three-way report + the hourly-flexibility table | `scripts/walloon_scripts/compare_heat_softlink.py` | changed |
| Tests | `test/test_times_heat_profiles.py` | **new**, 30 tests |

**`TIMES_PyPSA` needs no change for option B′.** `heating_targets_{year}.csv` already
carries the `share` column, which is the entire payload B′ consumes; the
`heat-softlink-option-b` branch there is identical to `heat-softlink-option-c` and
exists so the two model branches each have a matching library branch to pin
against.

### Step-by-step (M3–M5)

1. **`scripts/walloon_scripts/times_heat_profiles.py`** — new module, importing the
   pieces of `times_heat_softlink.py` that are mechanism-independent
   (`decentral_heat_buses`, `heat_injection_terms`, `load_heat_targets`,
   `times_heat_options`). New code:
   * `decentral_heat_load(n, buses)` → per-bus hourly load (handles the *static*
     `BEWAL agriculture heat` load, which is not in `loads_t.p_set`);
   * `solar_availability(n, bus)` → the collector `p_max_pu`, asserted identical
     across vintages;
   * `reconstruct_profiles(...)` → the `rhs_g,b(t)` frame, with the two closure
     identities asserted, not hoped for;
   * `add_times_heat_profile_constraints(n, snapshots, snakemake)` → the linopy
     rows, the relaxation variables and the log lines.
2. **`data/custom_extra_functionality.py`** — dispatch to whichever mechanism is
   enabled; raise if both are.
3. **Config** — a `sector.times_heat.profile` block, defaulting to off, in
   `config.times-pypsa.yaml` and `config.walloon.yaml`.
4. **Tests** — `test/test_times_heat_profiles.py`, mirroring the structure of
   `test/test_times_heat_softlink.py` (which stays green: option C is untouched).

---

## 5. Verification log

### 5.1 Full 2025 solve — the authoritative check

`config/config.times-pypsa.yaml` with `profile.enable: true`, 6 h resolution, all
six countries, **every** `extra_functionality` constraint including the national
CO₂ budgets, Gurobi barrier. `Optimal`, objective **334.275 bn**.

**The pre-solve budget report fired as designed** (from the solve log):

```
TIMES heat profiles: 5 of 6 groups pinned on
  ['BEWAL rural heat', 'BEWAL urban decentral heat']
  (absorber 'heat pump', penalty 1000 EUR/MWh_th):
  solar thermal 0.1347 TWh (0.48%), heat pump 2.2032 TWh (7.93%, absorber),
  gas boiler 15.2674 TWh (54.94%), oil boiler 5.9993 TWh (21.59%),
  biomass boiler 2.5014 TWh (9.00%), resistive heater 1.6855 TWh (6.06%)
TIMES heat profile budget: biomass boiler: 2.501 TWh_th -> 2.978-3.333 TWh of
  solid biomass; gas boiler: 15.267 TWh_th -> 15.659-20.578 TWh of gas,
  4.074 Mt CO2; oil boiler: 5.999 TWh_th -> 6.666-9.179 TWh of oil, 2.360 Mt CO2
  decentral heating CO2 (upper estimate) 6.434 Mt against the BEWAL cap of
  21.982 Mt = 29.3 % of the whole node's budget.
```

Every realised share equals the TIMES share to the digit printed — 7.93 / 54.94 /
21.59 / 9.00 / 6.06 / 0.48 % — because they are shares of the profile, not of a
tolerance bound.

**Profile fidelity, checked per group, per bus, per snapshot** against the
exported `heating_profiles/base_s_adm___2025.csv`
(`scripts/walloon_scripts/check_heat_profile_fidelity.py`):

| group | pinned TWh | realised TWh | annual gap TWh | peak \|gap\| MW | as % of profile peak |
|---|---:|---:|---:|---:|---:|
| gas boiler | 15.2674 | 15.2674 | −0.0000 | 0.0009 | 0.00002 % |
| oil boiler | 5.9993 | 5.9993 | −0.0000 | 0.0001 | 0.00001 % |
| biomass boiler | 2.5014 | 2.5014 | 0.0000 | 0.0000 | 0 % |
| resistive heater | 1.6855 | 1.6855 | −0.0000 | 0.0001 | 0.00001 % |
| solar thermal | 0.1347 | 0.1347 | −0.0000 | 0.0000 | 0 % |
| **heat pump** *(absorber)* | 2.2032 | 2.2035 | **+0.0003** | **24.7** | **3.0 %** |

Total absolute annual gap over all six groups and both buses: **0.00029 TWh**.

Two things this establishes and no unit test could:

1. **The sign conventions, carrier selection and vintage aggregation are right on
   the real network.** A wrong sign, a dropped vintage or a mis-matched carrier
   all produce a feasible LP whose answer is quietly not the TIMES mix; here the
   realised dispatch reproduces the pinned profile to solver tolerance.
2. **The absorber behaves exactly as §1.3 predicts.** It is the only group that
   deviates, it deviates by ±25 MW within the horizon (3 % of its own peak) and
   by +0.0003 TWh over it — that is the decentral water tank being used, and it
   nets out annually. Every *pinned* group is exact.

**No relaxation was needed in 2025**: every group delivered its full profile, so
`TimesHeatProfile-unmet` is zero throughout.

---

## 6. Operational hazards carried over from the option-C run

These cost real time in the option-C work and are reproduced here so the B′ chain
does not repeat them. Full versions in
[`instructions.md`](../instructions.md) and `heat_soft_linking.md` §8.7.

| Hazard | What happens | Guard |
|---|---|---|
| **An infeasible sector LP hangs the whole chain.** `solve_network.py:2031` reacts to `infeasible_or_unbounded` by calling `n.model.compute_infeasibilities()` — a Gurobi IIS over ~1.3 M rows. On the 2040 network Gurobi found infeasibility in 257 s and then ran **13 h at ~0 % CPU** without finishing the IIS. | looks like a hung process, not a failure | soft constraints by default (§1.4); the watchdog in `run_heat_softlink_comparison.sh` polls every `*_solver.log` for `Infeasible model` and kills the chain; **and** the pre-solve budget report, which is the only guard that fires *before* the solver |
| **Killing Snakemake leaves its children running.** | rule scripts and solver processes at 0 % CPU, plus a stale `.snakemake/locks/` | `pkill -f 'snakemake .*config.times-pypsa'; pkill -f '\.snakemake/scripts/tmp'; pgrep -af 'snakemake\|gurobi' \|\| echo clean` |
| **A `until … sleep` watcher with no exit condition.** | spins forever when the watched job dies before writing its marker — the "dormant agent" failure | bound every wait (`for _ in $(seq 1 180)`) *and* `kill -0 "$PID" \|\| break` |
| **`--configfile`, `--resources`, `--forcerun`, `--omit-from`, `--until` all take `nargs="+"`.** | a target written straight after them is swallowed; Snakemake then silently runs the whole `all` target, or tries to parse your `.nc` as YAML | put targets **first**: `snakemake <targets> --configfile … --cores 12` |
| **Gurobi falls back to its demo licence in non-interactive shells.** | `Model too large for size-limited license` — `~/.bashrc` is not read | `export GRB_LICENSE_FILE=$HOME/.gurobi/gurobi.lic` in every driver script |
| **A snapshot subsample with a stride that divides the snapshots per day.** | samples midnight only; solar `p_max_pu` is 0 everywhere and any solar constraint is trivially infeasible | use a stride coprime with the snapshots per day (13, not 12, at 6 h) |
