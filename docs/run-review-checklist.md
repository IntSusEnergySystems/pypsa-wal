# Critical review of a PyPSA-Wal run

A run that solves to optimality is not a run that is *right*. Gurobi will happily
return `Optimal objective` for a model whose base year is uncalibrated, whose
Walloon wind potential is exceeded twofold, whose aggregate caps bind on the wrong
variable, and whose district-heating system exists to feed a direct-air-capture
plant. Every one of those was found in the first run this checklist was applied to
(see [`logs/2026-08-18_scen_demande_haute_2010_1h.md`](logs/2026-08-18_scen_demande_haute_2010_1h.md) §11).

This file is the **procedure**. It is ordered so that the cheap checks that
invalidate everything downstream come first: if the run is the wrong vintage, or
the soft-link transferred the wrong quantity, there is no point reading capacities.

Companion script: [`scripts/walloon_scripts/review_run.py`](../scripts/walloon_scripts/review_run.py)
automates the mechanical checks (levels 0–4) and prints a pass/fail table. It reads
`results/<prefix>/<scenario>/` — networks *and* CSVs — and needs no solver.

```bash
python scripts/walloon_scripts/review_run.py results/walloon/scen_demande_haute
python scripts/walloon_scripts/review_run.py results/walloon/scen_demande_haute --full   # + slow network checks
```

Everything the script cannot decide — "is 14 GW of Walloon onshore wind
plausible?" — is in levels 5–8 and needs a human. **The review lives in section 11
of the run's own solve log**, `docs/logs/YYYY-MM-DD_<scenario>_<tags>.md`, so that
provenance, timings, issues and review stay in one file. If the run was never
logged, create the log from [`logs/_TEMPLATE_solve_log.md`](logs/_TEMPLATE_solve_log.md)
and fill what can be recovered — `run.json`, `configs/`, `logs/*_solver.log`,
`logs/*_memory.log`, `benchmarks/` — marking the rest `unknown`.

**Golden rule.** Every number in this model has a *unit* and a *port*. Most
apparent anomalies are one of: a link `p_nom` quoted at `bus0` instead of `bus1`,
a thermal MW read as electric, an annual-energy `e_sum_max` read as MW, or a
reversed link (heat pumps — see 4.4). Check the port before reporting a finding.

---

## Level 0 — Provenance: is this the run you think it is?

Cheapest checks, and the ones that most often invalidate a whole afternoon.

- [ ] **`run.json`** (S3 uploads only) — read `git_commit`, `git_branch`,
      `configfile`, `uploaded_at`. Confirm the commit is an ancestor of the code
      you are reasoning about: `git merge-base --is-ancestor <commit> HEAD`.
- [ ] **The config actually used** is `results/<run>/configs/config.base_s_adm___<year>.yaml`,
      not `config/config.walloon.yaml`. Diff the two:
      ```bash
      diff results/<run>/configs/config.<prefix>_<scenario>.yaml config/config.walloon.yaml
      ```
      A published run built from an older config is *not* a run of the current
      model. Grep the effective config for the keys that have changed recently —
      today that means `heat_stock_age_profile`, `bev_natural_charging_split`,
      `local_bev_dsm`, `retrofit_nuclear_once`, `agg_p_nom_limits.file`,
      `resolution_sector`.
- [ ] **All four horizon configs identical apart from `planning_horizons`.**
      ```bash
      for y in 2030 2040 2050; do diff results/<run>/configs/config.base_s_adm___2025.yaml \
        results/<run>/configs/config.base_s_adm___${y}.yaml; done
      ```
      Anything else means the chain was rebuilt mid-run against a changed config.
- [ ] **Weather year and cutout agree** — `snapshots.start/end` and
      `atlite.default_cutout` must name the same year. A mismatch is a run that
      succeeds and is wrong.
- [ ] **Temporal resolution** — `clustering.temporal.resolution_sector`. A 6 h run
      and a 1 h run are not comparable (see 8.2: BEWAL 2025 onshore wind moved
      2.4 GW → 6.8 GW between the two).
- [ ] **The `.vd` named in `sector.times_file` is the one you meant**, and the
      scenario overlay in `config/scenarios.walloon.yaml` points at the matching
      `agg_p_nom_minmax_*.csv`.
- [ ] **Only compare runs of the same vintage.** Before any cross-scenario chart,
      diff the two `configs/` snapshots.

## Level 1 — Did the solve actually converge?

- [ ] `grep 'Optimal objective' results/<run>/logs/base_s_adm___*_solver.log` —
      four hits, one per horizon.
- [ ] **Crossover.** `grep -c Crossover` the solver log. `Crossover 0` (the current
      setting) means the returned point is interior, not a vertex: near-degenerate
      capacities and duals carry solver-tolerance noise. Do not read three
      significant figures off a barrier-without-crossover solution, and do not
      treat a 1 % capacity difference between two runs as a signal.
- [ ] **Numerical warnings.** `Warning: Model contains large bounds` / `large rhs`
      appear in every horizon of the current model (bounds range up to 5e10, RHS to
      1e9). They are tolerated, not benign — record them, and if a result looks
      structurally odd, re-solve that horizon with `NumericFocus 1` before
      believing it.
- [ ] `BarConvTol` — the current 1e-5 gives ~5 digits on the objective, far fewer
      on individual variables.
- [ ] Solve wall-clock and memory against the previous run of the same resolution
      (`logs/*_memory.log`). A 3× change means the LP changed shape.

## Level 2 — Soft-link fidelity: did TIMES transfer what it meant to?

These are the three original `instructions.md` checks, plus the ones the first
review added. They catch a soft-link that ran, succeeded, and transferred the
wrong thing. **Run them before reading any results.**

### 2.1 Heating profile fidelity

```bash
python scripts/walloon_scripts/check_heat_profile_fidelity.py <scenario> live
```

Every pinned group should match to solver tolerance; only the absorber may
deviate. This catches a wrong sign convention or a dropped vintage — both of which
give a perfectly feasible LP whose answer is silently *not* the TIMES mix. A 2040
shortfall of ~0.46 TWh_th on the biomass boiler is **expected**: the TIMES 2040 mix
needs more solid biomass than Wallonia has
([`heat-softlink.md`](heat-softlink.md) §4.2). Much more than that is new.

### 2.2 EV grid draw must equal the TIMES `electricity road` figure

The two EV load branches sit on opposite sides of the charger, so an error here is
a double-counted charger loss.

```python
import pandas as pd, pypsa
for y in (2025, 2030, 2040, 2050):
    n = pypsa.Network(f"results/walloon/<scenario>/networks/base_s_adm___{y}.nc")
    w, ld = n.snapshot_weightings.generators, n.loads
    sel = lambda c: ld.index[ld.index.str.startswith("BEWAL") & (ld.carrier == c)]
    eff = 0.9  # sector.bev_charge_efficiency
    grid = (n.loads_t.p_set[sel("land transport EV")].mul(w, axis=0).sum().sum() / eff
            + n.loads_t.p_set[sel("land transport EV inflexible")].mul(w, axis=0).sum().sum()) / 1e6
    times = pd.read_csv(f"resources/walloon/<scenario>/wallon_demands_{y}.csv",
                        index_col=0)["TWh"]["electricity road"]
    print(f"{y}: PyPSA {grid:.3f} TWh vs TIMES {times:.3f}  ({grid/times-1:+.1%})")
```

Expect **±0.1 %**. `+11 %` means the inflexible branch is being grossed up by
`bev_charge_efficiency` on top of TIMES's own 0.95 charger efficiency; `+5.6 %`
means only the flexible branch is
([`ev-charging-softlink.md`](ev-charging-softlink.md) §3). The error scales with
`bev_dsm_availability`, so a run with the PyPSA-Eur default 0.5 shows the full
+5.6 % while the Elia-derived 0.07–0.18 shows less — a small deviation is not
proof the mechanism is right.

### 2.3 Every other transferred carrier, not just EV

The EV identity is the one that is easy to get wrong, but the others are worth a
one-line check because they are free. For each horizon compare the BEWAL `Load`
components against `resources/<run>/wallon_demands_<year>.csv`:

| PyPSA load carrier (bus) | TIMES row | tolerance |
|---|---|---|
| `industry electricity` (low voltage) | `electricity` | ±0.1 % |
| `gas for industry` | `methane` | ±0.1 % |
| `naphtha for industry` | `naphtha` | ±0.1 % |
| `solid biomass for industry` | `solid biomass` | ±0.1 % |
| `kerosene for aviation` | `total domestic aviation` + `total international aviation` | ±0.1 % |
| `land transport oil` (+ `land transport fuel cell`) | `total road` − `electricity road` | ±0.1 % |
| `coal for industry` | `coal` + `coke` | **check** — was +8 % (2025) / +12 % (2030) in the first reviewed run |
| sum of all electric loads | sum of all TIMES electricity rows | ±0.5 % |

- [ ] Total BEWAL electric load vs total TIMES electricity within ±0.5 %.
- [ ] No carrier off by more than its tolerance; investigate any that is.

### 2.4 Heat-pump capacity must not fall across a horizon step

```python
import pypsa
for y in (2025, 2030, 2040, 2050):
    n = pypsa.Network(f"results/walloon/<scenario>/networks/base_s_adm___{y}.nc")
    l = n.links
    hp = l[l.bus1.map(n.buses.location).eq("BEWAL") | l.bus0.map(n.buses.location).eq("BEWAL")]
    hp = hp[hp.carrier.str.contains("heat pump", na=False)]
    print(y, "BEWAL heat pumps, MW_th:", round(hp.p_nom_opt.sum(), 1))
```

A fall between 2025 and 2030 means `existing_capacities.heat_stock_age_profile` is
missing from the config in use, so a third of the inherited fleet retires in 2028
([`heat-softlink.md`](heat-softlink.md) §5). **Caveat:** under option B′ decentral
capacity is a restatement of the pinned peak, so a fall can also be a pinned-profile
artefact — read heat **delivered** as the electrification indicator, not capacity,
and check `heat_stock_age_profile` in the effective config before concluding.

## Level 3 — Do the numbers add up? (accounting identities)

None of these should ever fail. If one does, stop: something is structurally wrong
and every downstream number is suspect.

- [ ] **Every bus balances.** For each BEWAL bus carrier, the sum of generator
      dispatch, storage, store, load, link ports and line flows over the year is
      zero to within ~1e-3 TWh. `review_run.py` does this for
      `AC`, `low voltage`, `EV battery`, and under `--full` also `H2`, `gas`,
      `solid biomass`, `biogas`, and each heat bus.
      *Traverse every link port* (`bus0`…`bus4`, `p0`…`p4`) — links with `bus2`/`bus3`
      (CHP, DAC, CC units) will not balance otherwise.
- [ ] **Belgium-wide electricity balance closes** (three nodes, `AC` + `low voltage`)
      to <0.5 % of gross supply. A residual larger than that usually means an
      `efficiency2`/`efficiency3` port was missed.
- [ ] **Cross-border flows are consistent**: net BEWAL import computed from
      `lines_t.p0` equals the value implied by the closed AC balance.
- [ ] **DC links are counted once.** OSM-derived DC interconnectors are split into
      a forward and a `-reversed` link; net flow is `p0(fwd) − p0(rev)`, and
      capacity is *not* the sum of the two `p_nom`.
- [ ] **`e_sum_max` is respected** for the annual-energy generators
      (`biogas`, `solid biomass`, `solid biomass transported`). Their `p_nom` is a
      rate, not the annual potential — never read `p_nom` as TWh/yr even though the
      custom-potentials file is written in GWh/an.
- [ ] **Store SoC returns to its start** over the year (cyclic stores), or the
      annual net store flow is zero. Include the **EV-battery** bus — it is a
      cyclic Store like any other, and `review_run.py` checks it with the AC /
      low-voltage buses (not only under `--full`).
- [ ] **Energy-Sankey transformation nodes balance.** Open the pypsa2html energy
      Sankey (BEWAL). Every intermediate node (Electricity grid, BEV, hydrogen,
      district heat, …) must have inflow ≈ outflow. Sources (`prod` / imports)
      and sinks (demand sectors, losses, exports) are allowed to be one-sided.
      `review_run.py` recomputes the graph when pypsa2html is installed and
      **FAILs** a hole on BEV / stationary battery / TES (no trade residual to
      hide behind). Other unbalanced transformation nodes currently **WARN**
      (solid-biomass `prod` on a regional node, DAC, district heat — known
      mapping holes, not this bug).
      *The BEV node is the one that has already bitten:* with
      `bev_natural_charging_split`, both EV loads are booked as demand leaving
      BEV, but only the charger Link feeds that node. The inflexible load sits
      on the AC bus. The report must draw **Smart charging** (charger) *and*
      **Natural charging** (the inflexible load) as inflows. A BEV node with
      more going out than in is that inflow missing — not a solve failure; the
      EV-battery bus still closes. On the 2026-08-18 run the hole was exactly
      the natural-charging volume (0.47 TWh in 2025, 8.4 TWh in 2050).


## Level 4 — Were the model's own constraints respected?

The traps here are all the same shape: a limit that was *meant* for the total is
applied to the **extendable tranche only**, so under myopic foresight it resets at
every horizon.

### 4.1 Aggregate capacity limits (`agg_p_nom_minmax_<scenario>.csv`)

- [ ] For every `(region, carrier)` row with a `max`, compare the limit against
      **total** `p_nom_opt` (extendable **+** non-extendable), not against the
      extendable tranche.
- [ ] **Known defect** — in `scripts/solve_network.py::add_CCL_constraints`, the
      `include_existing` branch subtracts existing capacity from the RHS for
      *minima* (generators and links) and for *link maxima*, but **not for
      generator maxima** (`rhs_max` is never reduced by `rhs_cst`). Consequence:
      a generator `max` caps only what is newly built in that horizon. Diagnostic:
      if the extendable tranche equals the cap **exactly** while the total exceeds
      it, this is the cause.
- [ ] Nuclear and CCGT limits are on **links** and are expressed in **MW_e**, i.e.
      `p_nom * efficiency`, grouped on `bus1`. Compare like with like.
- [ ] Sanity-read the limits file itself before trusting the results — it is
      hand-maintained and hand-maintained files carry typos. Plot each row across
      2025→2050 and look for a value 10× out of line with its neighbours
      (see 8.1: `GB, offwind-all` 2040 min = 96 158 MW between 7 432 and 9 651).
- [ ] Remember `min`/`max` are interleaved column pairs per year. A value in a
      `min` column is a **floor**, and a floor applied per vintage adds new capacity
      at every horizon (see 8.1: BEWAL `CCGT p_nom_min = 1740 MW_e` re-imposed four
      times).

### 4.2 Walloon potentials (`data/walloon/custom_potentials.csv`)

- [ ] `onwind p_nom_max = 6 500 MW`, `solar p_nom_max = 13 000 MW`,
      `solar rooftop p_nom_max = 46 000 MW` — check against **total** BEWAL
      `p_nom_opt` per horizon, summed over all vintages. Same per-vintage trap as 4.1.
- [ ] `solid biomass p_nom = 6 000 GWh/an` and `biogas p_nom = 8 300 GWh/an` are
      annual-energy limits: compare against `generators_t.p` summed over the year,
      not against `p_nom`.
- [ ] **Imported biomass is specified twice** — `solid biomass import e_nom`
      (4 000/4 000/4 500/6 000 GWh) and `solid biomass transported e_sum_max`
      (2 000/2 000/2 250/3 000 GWh), both described as "pellets imported for
      Wallonia". Check whether the run uses both (the first reviewed run imported
      6.75 TWh in 2040 against a documented 2.25 TWh potential) and decide which is
      the intended cap.
- [ ] `CCGT p_nom_min = 1740 MW_el` and the `battery p_nom_min` floors — confirm
      they bind once, not once per horizon.

### 4.3 Interconnection / NTC

- [ ] Compare the solved `s_nom_opt` (AC) and `p_nom_opt` (DC) per border against
      `data/walloon/ntc_<year>.csv` (`BEL` rows). They are **not** currently equal —
      see 8.1.
- [ ] Remember `s_max_pu = 0.7` on AC lines. Usable AC capacity is 70 % of `s_nom`,
      so an NTC written into `s_nom` is delivered as 0.7 × NTC. DC links have no
      such derate, so an NTC written into `p_nom` is delivered in full. Decide which
      convention `set_NTCs.py` is supposed to implement and check that the *usable*
      capacity matches the NTC.
- [ ] Hours at the limit per border, and the max hourly flow in each direction.
      A border that never saturates is either genuinely uncongested or not
      connected the way you think.
- [ ] Annual net import/export per border and for Belgium as a whole. Compare with
      Elia's historical balance: a model that makes Belgium a structural 14 TWh
      net importer or exporter needs a reason.
- [ ] Nemo Link and ALEGrO by name: Nemo is **1 000 MW**, ALEGrO is **1 000 MW**.
      Any other number in the solved network is an assumption that must be written
      down.

### 4.4 CO₂

- [ ] Realised emissions vs each `co2_limit_per_country*` constraint, and vs the
      system `CO2Limit`.
- [ ] **Both bind simultaneously.** The per-country caps sum to exactly the global
      cap, so the *effective* carbon price in Wallonia is
      `|mu(CO2Limit)| + |mu(co2_limit_per_countryBEWAL)|`, not either alone. Report
      the sum. In the first reviewed run this was 618 / 380 / 573 EUR/t in
      2030/2040/2050 — non-monotonic, and far above any plausible ETS path.
- [ ] The 2025 shadow prices. If the 2025 national caps bind at several hundred
      EUR/t, the "base year" is a deeply decarbonised counterfactual, not a
      calibration of the real 2025 system (see 5.1).
- [ ] `co2_sequestration_limit` — is it binding? If yes, sequestration is set by the
      cap, not by economics, and every CCS/DAC number is a restatement of the cap.
- [ ] `biomass limit` and `unsustainable biomass limit`. Note the 2025
      `biomass limit` is `<= 0` — sustainable solid biomass is *banned* Europe-wide
      in 2025 and all biomass must be "unsustainable". Read 2025 biomass numbers
      with that in mind.

## Level 5 — Is it realistic for Wallonia?

This is the part that needs judgement. Compare against the project's own agreed
references first (`config/input_parameters_for_models.csv`,
[`common_parameters.md`](../common_parameters.md), and the sources cited in
`custom_potentials.csv`: PNEC wallon, EDORA, Valbiom, Cluster TWEED, Énergie
Commune), then against external statistics (SPW Énergie *Bilan énergétique*,
APERe/Énergie Commune observatories, Elia, CWaPE, FEBEG).

### 5.1 The 2025 horizon is an optimisation, not a calibration

2025 is a planning horizon like any other: the model is free to build whatever is
economic "by 2025", subject to the 2025 CO₂ caps. It therefore does **not**
reproduce the observed 2025 system, and any chart that presents it as "today" is
misleading.

- [ ] Compare 2025 `p_nom_opt` against observed installed capacity for **every**
      technology and **every** node, not just BEWAL. Record the ratio.
- [ ] If any 2025 capacity exceeds observation by more than ~20 %, say so
      explicitly in the review note and in any figure caption.
- [ ] Cross-check the neighbours too — FR/GB/NL/DE 2025 capacities feed the price
      signal that drives every Walloon investment decision.

### 5.2 Build rates

Convert every capacity step into MW/year and compare with what has actually been
built.

- [ ] BEWAL onshore wind: historical additions are ~100–150 MW/yr. Anything above
      ~300 MW/yr sustained is a claim that needs defending.
- [ ] BEWAL PV: historical additions ~200–300 MWp/yr.
- [ ] Any technology going 0 → multi-GW within one horizon step.
- [ ] Neighbours: a step like DE onshore wind +67 GW over 2025–2030 (13 GW/yr
      against a ~5 GW/yr record) invalidates the European price signal.

### 5.3 Technology substitution artefacts

- [ ] `solar` vs `solar-hsat` vs `solar rooftop`. If the model puts essentially all
      Walloon PV on one sub-carrier and zero on the others, that is a cost-ranking
      artefact, not a forecast — Walloon PV is overwhelmingly rooftop today. Report
      **total PV** and flag the split.
- [ ] Capacity that *falls* across horizons without being replaced by the same
      carrier (e.g. `solar` 4 088 → 1 MW) is retirement plus substitution; make sure
      the chart does not read as "Wallonia loses its PV".

### 5.4 Capacity factors and full-load hours

Every one of these is a cheap lie-detector.

| Technology | Expected |
|---|---|
| BEWAL onshore wind | 22–27 % |
| BEWAL PV (fixed / hsat) | 10–13 % |
| BE offshore wind | 40–50 % |
| Nuclear | 80–92 % |
| Run-of-river | ~25 % |
| Heat pump effective COP (heat out / elec in) | 2.5–3.5 |

- [ ] Anything outside the range is either a profile error or a capacity that is
      not what its name says.
- [ ] Dispatchable plant FLH: a CCGT fleet at 800–1 100 h is a peaker fleet, not a
      baseload one — check that the narrative matches.

### 5.5 Sector plausibility

- [ ] **District heating.** Walloon DH is ~1–2 % of heat demand today. Check the DH
      share per horizon, and check **where the DH heat goes** — in the first
      reviewed run 6.1 TWh_th of 2050 Walloon DH heat went to DAC and only 2.7 TWh_th
      to buildings.
- [ ] **DAC / CCS in Wallonia.** Compare captured CO₂ against the Walloon CO₂ cap.
      Capturing 2.6× the region's entire emission budget is a modelling outcome,
      not a plan.
- [ ] **Hydrogen.** If BEWAL has GW of `H2 pipeline` and ~0 `H2 Electrolysis`, the
      region is a transit corridor. Check the H2 bus balance (in / out / consumed)
      before describing Wallonia as a hydrogen producer.
- [ ] **Fischer-Tropsch / synthetic fuels.** Check whether the capacity is stable
      across run vintages before reporting it (see 8.2).
- [ ] **Gas.** Total Walloon methane withdrawals vs Walloon gas consumption
      (~35–40 TWh today).
- [ ] **Zero-cost capacities.** `urban central water pits charger`,
      `water tanks charger/discharger`, `home battery charger` and similar have
      `capital_cost = 0` in PyPSA-Eur. Their `p_nom_opt` is a degenerate variable —
      it is not a capacity result and must not be plotted as one. Diagnostic:
      it swings wildly between run vintages (209 → 4 604 MW here, 8 169 MW in
      another vintage of the same scenario).

## Level 6 — Prices, costs and duals

- [ ] Mean, median, p05, p95 of the BEWAL `AC` marginal price per horizon. The
      price embeds the CO₂ shadow prices, so it is not comparable with an observed
      day-ahead price unless you say so.
- [ ] Hours at ≤ 0 EUR/MWh and hours above 200/500/1000. A system with 30 TWh of
      Walloon wind and no hour below ~1.6 EUR/MWh, and no hour above ~430, has
      neither surplus-driven collapse nor scarcity pricing — say why.
- [ ] Curtailment per VRE carrier (% of available). 5–15 % is normal at high
      penetration; 0 % or 40 % both need explaining.
- [ ] **`costs.csv` / `nodal_costs.csv` include non-extendable capital**
      (`p_nom_opt * capital_cost` for every component), while the Gurobi objective
      does not. That is why `metrics.csv → total costs` (≈5.7e11) differs from
      `Optimal objective` (≈3.6e11). Existing Tihange units are annuitised at full
      new-build cost (≈875 EUR/kW_e/yr, ≈1.7 GEUR/yr in 2025). Decide which
      convention the deliverable uses and state it.
- [ ] **Nodal attribution follows `bus0`.** `nuclear` links have `bus0` on the EU
      uranium bus, so **Walloon nuclear capacity and cost do not appear in BEWAL's
      rows of `nodal_capacities.csv` / `nodal_costs.csv`**. Same for anything else
      whose input bus is `EU`. Recompute from the network, grouped on `bus1`.
- [ ] Operational costs across horizons are lumpy by construction. Forced
      *unsustainable* biomass exists only in 2025/2030 (~656 and ~451 MEUR/yr) and
      its carriers are absent later; the 8.3 TWh Walloon biogas block at
      78.8 EUR/MWh is all-or-nothing and worth 654 MEUR/yr when it runs. In 2040 the
      CO₂ shadow price can sit within ~1 EUR/MWh of its break-even, so the block
      flips between otherwise similar scenarios and 2040 can look implausibly cheap.
      **Check `biogas` dispatch before reading a dip as an economic trend.**
- [ ] Vintage labels. New capacity added at a late horizon can inherit an early
      `build_year` (2 GW_e of 2050 nuclear is named `BEWAL nuclear-2025` with
      `build_year 2025`). Do not group results by `build_year` without checking.

## Level 7 — Consistency with TIMES

The soft-link guarantees the *demands* match (level 2). Everything downstream is
free to diverge, and some divergence is expected — TIMES and PyPSA optimise
different things. The question is whether the divergence is explicable.

- [ ] **Nuclear** must follow the `agg_p_nom_minmax_<scenario>.csv` trajectory that
      was derived from the `.vd`
      ([`nuclear-alignment-20260816.md`](nuclear-alignment-20260816.md)): 2 030 MW_e
      Belgium-wide in 2035/2040 (Tihange 3 LTO 1 030 + Doel 4 1 000), 1 750 MW_e all
      in BEWAL in 2045, 3 000 MW_e all in BEWAL in 2050. Check MW_e, not link `p_nom`.
- [ ] **Heat mix.** Compare PyPSA heat delivered per technology against the TIMES
      shares in `resources/<run>/heating_targets_<year>.csv`. Under option B′ these
      are pinned and should match; under option C they are targets and will not.
- [ ] **Biomass and biogas volumes** used in PyPSA vs the TIMES `.vd`.
- [ ] **Electricity generation mix** — TIMES and PyPSA will differ, but a factor of
      two on any carrier is worth a sentence.
- [ ] **CO₂ trajectory** — the PyPSA per-country caps against the TIMES emission
      path.
- [ ] Where they diverge, say *why* in the review note: different foresight
      (myopic vs perfect), different spatial resolution, PyPSA's European system
      boundary vs TIMES's Walloon one, or an actual inconsistency in the shared
      parameters (`config/input_parameters_for_models.csv`).

## Level 8 — Robustness

A number that moves by 3× between two runs of the same scenario is not a result.

- [ ] **Re-run comparison.** Put the same indicator from every available vintage of
      the scenario side by side (`results/*/<scenario>/csvs/nodal_capacities.csv`).
      Anything that is not stable to ~±20 % should be reported with its range, not
      as a point value.
- [ ] **Resolution sensitivity.** 6 h vs 1 h. Storage, peaking plant and
      curtailment are the expected movers; base-year VRE capacity is not, and if it
      moves, that is the finding.
- [ ] **Degenerate variables.** Zero-capital-cost links, near-identical
      technologies (`solar` vs `solar-hsat`), and anything whose dual is ~0 will
      wander between solves. Identify them once and mark them "not a result" in the
      reporting.
- [ ] **Weather year.** The model runs one year (2010). Any statement about
      adequacy, storage sizing or curtailment is conditional on it.

---

## Reporting the review

Append **section 11** to the run's solve log, `docs/logs/YYYY-MM-DD_<scenario>_<tags>.md`
(create it from [`logs/_TEMPLATE_solve_log.md`](logs/_TEMPLATE_solve_log.md) if the
run was never logged), and add a one-line pointer to it from section 10. Cover:

1. **Provenance** — only what differs from what sections 1 and 3 of the log already
   record: the commit the run *actually* came from, the config it was built with,
   and which HEAD features it predates.
2. **Verdict** per level: pass / pass-with-caveats / fail.
3. **Findings**, each as: what was observed (with the number), what it should be,
   why it happens, and what to do. Rank by whether it changes a headline number.
4. **Numbers that must not be published as-is**, with the reason.
5. **Follow-up actions**, as issues or TODOs.

Findings that turn out to be model defects belong in the code, not only in the
review: add a regression test under `test/` so the next run fails loudly.
