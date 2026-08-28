# Gas storage — Wallonia, Loenhout, and the cushion-gas bug

**Archived 29 Aug 2026.** Started as item 1 of the 2026-08-27 meeting review
([temporary_improvement_plans.md](temporary_improvement_plans.md)); moved here
once it grew past a roadmap entry into a data correction with Europe-wide
reach. That file now carries a one-line pointer.

**Status: implemented and committed** (branch `fix/run-review-20260825`),
*not yet re-solved*. Every number below describes the state *before* these fixes.

**Vintage warning.** Two sets of solved networks are on this machine and they
are **not** interchangeable:

| Path | Date | Resolution | Coverage |
|---|---|---|---|
| `results/_diagnostics/20260826/base_s_adm___{2040,2050}.nc` | 26 Aug | 8 760 h (1 h) | 2040, 2050 only |
| `results/times-pypsa/scen_demande_haute/networks/*.nc` | **14 Aug** | 1 460 snapshots (6 h) | all four horizons |

`results/walloon/scen_demande_haute/networks/` — the path
[temporary_improvement_plans.md](temporary_improvement_plans.md) names as its
evidence — holds no networks locally. Numbers below are labelled **26 Aug**
where they come from the diagnostics pair and **14 Aug** otherwise. They differ
enough to matter: 2040 Walloon gas store is 447 GWh on 26 Aug against 184 GWh
on 14 Aug, and 2040 biogas dispatch is 1.45 TWh on 26 Aug against a binding
8.30 TWh on 14 Aug. Cost and potential tables are structural (cost data +
salt-cavern file), identical in both, and carry no label.

| Change | Commit | File |
|---|---|---|
| BEWAL gas Store pinned to `e_nom_max = 0` | `2aea1b01` | `BEWAL_potentials.py`, `custom_potentials_*.csv` |
| Storage read from working gas, not cushion gas | `46c2f485` | `build_gas_input_locations.py` |
| Zero-padded 0.98-quantile clip removed | `46c2f485` | `prepare_sector_network.py` |
| 7 unit tests | both | `test/test_gas_store_potential.py` |

**One-paragraph summary.** Wallonia had an unbounded endogenous gas store on a
node whose only two sites closed in 2012; it is now pinned to zero. Flanders
had Loenhout at 545 GWh instead of ~8.2 TWh, because PyPSA-Eur sized every
European store from the *cushion* gas column — the base inventory that never
leaves the reservoir — rather than *working* gas; both columns are in
SciGRID_gas. A second bug, an outlier clip whose threshold depended on how many
unrelated stores happened to exist at that line, is removed. Loenhout stays a
legacy `e_nom_min` floor: the model is forced to have it and free to decide
whether to cycle it.

---

### What the meeting asked

Confirm that the model has (or should have) gas storage in Wallonia, and what
the geological potential is.

### Evidence

Belgium’s only operating underground store is **Loenhout** (Fluxys, aquifer,
Antwerp province → **Flanders**): 7.6 TWh firm, 770 Mm³ useful working gas,
withdrawal 625 000 m³/h. It is a national buffer, not a Walloon asset.

Wallonia *had* two coal-mine stores, **Anderlues** and **Péronnes-lez-Binche**
(Distrigaz / Fluxys). Both were closed **1 November 2012** (AM 06/12/2012 and
MB 04/12/2012). ISSeP still monitors residual pressure; there is no reopening
plan and no salt-cavern geology. Residual volumes were ~120 Mm³ at Péronnes
historically — two orders of magnitude below Loenhout, and gone.

On the 26 Aug networks:

| Store | 2025 | 2030 | 2040 | 2050 | `e_nom_min` | `e_nom_max` |
|---|---:|---:|---:|---:|---:|---|
| **BEWAL gas Store** | 130 GWh | 203 | 82 | **0.06** | **0** | **inf** |
| BEVLG gas Store | 545 | 545 | 545 | 545 | **545 GWh** | inf |
| BEBRU gas Store | 17 | 30 | 8 | 0.02 | 0 | inf |

Flanders holds the only Belgian *existing* inventory (545 GWh floor from
SciGRID_gas / gas-input nodes — Loenhout, scaled). Wallonia’s 130–203 GWh is
an unconstrained endogenous store (`prepare_sector_network.py` copies
`gas_input_nodes["storage"]` which is 0 at BEWAL, then leaves `e_nom_max =
inf`). It is not a site. The model abandons it by 2050. There are no
charger/discharger links; the Store sits on the gas bus.

See also the water-pits analogue in the solve log §11.14 B: an unbounded store
is not a result.

### Options

| | What | Effect |
|---|---|---|
| **A. Pin Wallonia to zero** (recommended) | `e_nom_max = 0` (and `e_nom_min = 0`) on `BEWAL gas Store` | Matches geology. Flanders keeps Loenhout. Seasonal gas flexibility in Wallonia then comes from the pipeline (already 7.5 GW, zero capital_cost — a separate issue). |
| **B. Leave it free** | status quo | 2025/2030 “Walloon storage” of 0.1–0.2 TWh will be plotted as if it were a site. |
| **C. Hypothetical new store** | explicit `e_nom_max` with a source (none exists today) | Only if a policy study asks “what if Wallonia reopened mines / built a cavern”. Not this scenario. |
| **D. Give Loenhout its real 7.6 TWh** | raise BEVLG `e_nom_min` from 545 GWh to ~7 600 GWh | The 545 GWh floor looks like a unit/scaling miss against Fluxys’s 7.6 TWh. Worth a one-line audit of `gas_input_nodes["storage"]` (MWh vs GWh vs the 0.98-quantile clip at line 2127 of `prepare_sector_network.py`). Independent of Wallonia. |

### Recommended

**A**, plus the **D** audit.

### Implemented — 28 Aug 2026

**A is done.** `BEWAL gas Store` is pinned to `e_nom_max = 0` at every horizon,
through the existing `custom_potentials.csv` overlay rather than a new code
path.

| Change | File |
|---|---|
| `apply_gas_store_cap(n, bus, attr, value)` — writes `e_nom`/`e_nom_min`/`e_nom_max` on `{bus} gas Store` | [`scripts/walloon_scripts/BEWAL_potentials.py`](../scripts/walloon_scripts/BEWAL_potentials.py) |
| `technology: gas storage` branch dispatching to it | same, + [`BEWAL_potentials_overnight.py`](../scripts/walloon_scripts/BEWAL_potentials_overnight.py) (overnight foresight) |
| 4 rows `BEWAL,gas storage,e_nom_max,0,MWh,<year>` | `data/walloon/custom_potentials{,_alternatif,_alternatif_biolow,_imppel}.csv` |
| 5 unit tests | [`test/test_gas_store_potential.py`](../test/test_gas_store_potential.py) |

Three implementation points worth recording:

1. **Per-horizon rows are required, not redundant.** The gas Store carries
   `lifetime = inf`, so `add_brownfield` removes it from the previous network
   (`n_p.remove(c.name, c.df.index[c.df.lifetime == np.inf])`) and
   `prepare_sector_network` rebuilds it unconstrained at each horizon. A single
   2025 row would leave 2030–2050 free. The cap therefore rides the myopic hook
   already in place — `update_BEWAL_potentials` in `add_existing_baseyear.py`
   (2025) and `add_brownfield.py` (2030/2040/2050).
2. **`e_nom_max` also pulls down `e_nom_min`/`e_nom`.** At BEWAL the floor is
   already 0, so this is inert today; it exists so that pinning a bus that *did*
   inherit a SciGRID floor cannot silently produce `e_nom_min > e_nom_max`, an
   infeasible LP rather than a rejected cap.
3. **The technology label is `gas storage`, not `gas`.** `gas` is a live
   *generator* carrier, so it would be captured by the generator branch of
   `update_BEWAL_potentials` before reaching the store.

The rows were added to all four `custom_potentials_*.csv` variants: the closure
of Anderlues and Péronnes is geology, not a scenario assumption. They are
*unmanaged rows* for `build_common_parameters.py` (no `potential:BEWAL:gas
storage:e_nom_max` target in the master CSV) — deliberate: a hard zero from
Belgian mining history is not a negotiated TIMES/PyPSA parameter.
`--check` still passes.

**Verification** (no full workflow — a solve is hours):

- `update_BEWAL_potentials` replayed against the four solved **14 Aug** networks
  (the only vintage with all four horizons on disk):
  `BEWAL gas Store e_nom_max` `inf → 0` at 2025/2030/2040/2050, while
  `BEVLG gas Store` keeps `e_nom_min = 545 280 MWh` and `e_nom_max = inf`.
- 5 new unit tests, including an LP smoke test: a two-bus toy network with a
  winter price spread builds a Walloon store when uncapped, and with the cap
  solves to `status == "ok"` with `e_nom_opt = 0` — the gas bus balances from
  the pipeline, so removing the store does not make the region infeasible.
- Full suite `pytest test/` — 222 passed.
- `python scripts/build_common_parameters.py --check` — CHECK PASSED.
- `snakemake --configfile config/config.walloon.yaml -n` — DAG builds.

Expected effect on the next solve: 0.13–0.20 TWh of phantom Walloon seasonal
inventory disappears in 2025/2030 (2050 was already abandoning it at 0.06 GWh).
Walloon seasonal gas flexibility then comes only from the pipeline — 7.5 GW at
zero `capital_cost`, which remains a separate open issue.

### **D** implemented — 29 Aug 2026: cushion gas → working gas

The 545 GWh floor was never a `MWh`/`GWh` or quantile mistake. The *column* was
wrong. `build_gas_input_locations.py` read

```python
sto["capacity"] = sto["max_cushionGas_M_m3"] * mcm_to_gwh   # 11.36 GWh/Mm³
```

**Cushion gas** is the base inventory that stays in the reservoir permanently.
It is not storage capacity at all. SciGRID_gas carries both columns for every
one of its 203 sites, with no missing values:

| Loenhout (the only Belgian site, POINT 4.699/51.391) | Mm³ | → GWh |
|---|---:|---:|
| `max_cushionGas_M_m3` — what was read | 48.0 | **545** |
| `max_workingGas_M_m3` — the storable volume | 719.9 | **8 178** |

8 178 GWh matches Fluxys's 7.6 TWh. **Changed to `max_workingGas_M_m3`.**

The earlier note in this file said the bias was uniform enough to leave alone.
That was wrong. Cushion gas is not a scaled-down proxy — the two are not even
proportional, because the cushion/working ratio is set by reservoir type.
Aquifer stores (Loenhout) need little cushion; depleted fields (NL, GB, PL)
need a great deal:

| node | cushion (was) | working (now) | factor |
|---|---:|---:|---:|
| **BEVLG** | 545 GWh | **8 178 GWh** | **×15.0** |
| DE | 264 496 | 320 084 | ×1.21 |
| FR | 177 711 | 116 392 | ×0.65 |
| NL | 456 976 | 103 615 | ×0.23 |
| GB | 142 500 | 50 729 | ×0.36 |

In aggregate the countries in scope go from 1 708 TWh of cushion to 1 406 TWh
of working gas — the old numbers were 22 % too *high* overall while Belgium,
the single worst-hit node in the dataset, was 15× too low. No scale factor
could have repaired that; only the column swap does.

### Second bug: the 0.98-quantile clip (removed)

`prepare_sector_network.py` then ran

```python
e_nom.clip(upper=e_nom.quantile(0.98), inplace=True)  # limit extremely large storage
```

on a series `reindex`ed to **`n.stores.index` and padded with zeros**. The clip
level is therefore decided by how many *unrelated* stores happen to exist at
that point in the script, which is neither documented nor stable:

| stores in the network when the line runs | clip level | effect |
|---|---:|---|
| 37 (where `add_gas_network` actually sits) | 318 TWh | clipped NL 457 → 318 |
| 281 (what the network ends with) | **0 GWh** | **every gas-storage floor in Europe erased** |

Only five of those 37 entries are non-zero, so the "98th percentile" is a
percentile of padding. It happened to produce a plausible number for the
cushion data by coincidence. On working gas the same line would cut **Germany —
the largest genuine store in Europe — from 320 to 173 TWh**.

**Removed.** The values are now physical, so an outlier guard is guarding
against nothing, and the one it had was index-dependent. An `INFO` line now
logs the resulting floors each run (`Existing gas storage floors (TWh_LHV)`),
which is the check that the clip was pretending to be.

### What this does and does not decide

Loenhout is legacy plant, in service through 2050, so it enters as an
`e_nom_min` floor exactly as before — the model is **forced to have it** and
**free to decide whether to cycle it**. Nothing about dispatch is pinned.

**Caveat to carry into the next solve — the objective moves.** `capital_cost`
in PyPSA applies to the whole `e_nom_opt`, including the part forced by
`e_nom_min` (verified: an extendable store with `e_nom_min = e_nom_max = 1000`
and `capital_cost = 10` returns `objective = 10 000`, `objective_constant = 0`).
So every floor is charged a **greenfield annuity of 23.92 EUR/MWh/a** (Danish
Energy Agency underground storage, 297 EUR/kWh over 100 y) against stores that
were built decades ago:

| node | Δ capex |
|---|---:|
| BEVLG | **+183 MEUR/a** |
| DE | +1 330 |
| FR | −1 467 |
| GB | −2 195 |
| NL | −5 137 |
| **net** | **−7 287 MEUR/a** |

The net is a ~7.3 BEUR/a *reduction* in reported European system cost, almost
all of it NL's phantom 214 TWh disappearing. This does **not** change any
dispatch decision — for a forced floor the term is effectively constant — but
it does mean **total system cost is not comparable with runs before this
change**. Charging sunk assets a greenfield annuity is a pre-existing PyPSA-Eur
convention affecting every `e_nom_min` floor in the model; correcting it is a
separate modelling decision, not part of this data fix.

### Why this matters more than "one number" — the P2G seasonal loop

Raised in review: with methanation available, large seasonal methane storage is
how a system carries summer renewables into winter. The model does implement
that loop (`sector.methanation: true`, H₂ + CO₂ → CH₄ at η = 0.8, `p_min_pu =
0.3`, waste heat to DH), and it is not idle — **26 Aug 2040 Sabatier is
3 700 MW consuming 9.86 TWh of H₂** across the model.

The store cycle counts show the model using gas storage seasonally wherever it
has enough of it, and thrashing where it does not:

| gas store (**26 Aug**) | size | cycles/yr 2040 | cycles/yr 2050 |
|---|---:|---:|---:|
| DE | 264 TWh | 0.52 | **0.98** — seasonal fill/drain |
| FR | 178 TWh | 0.02 | 0.33 |
| GB | 143 TWh | 0.32 | 0.27 |
| NL | 318 TWh | 0.10 | 0.16 |
| **BEVLG** | **545 GWh** | **20.2** | **11.8** |
| BEWAL | 447 / 0.6 GWh | 43.5 | 516 |

Belgium's 12–20 cycles/year was the *symptom* of a store 15× too small to do a
seasonal job, not evidence that Belgium had no seasonal need. The Walloon
store's 43–516 cycles/year is the same signal on a store that should not exist
at all.

And Belgium had no fallback. It has **no salt caverns**
(`build_salt_cavern_potentials`: DE/FR/GB/NL only), so its `H2 Store` costs
**2 912 EUR/MWh/a against 120** at cavern nodes. 2050 H₂ storage built
(**26 Aug**): DE 4.01, GB 3.70, NL 3.24, FR 2.09 TWh — **Belgium 0.0000 TWh**
across all three nodes. Both seasonal routes were
shut: methane by this data bug, hydrogen by real geology. Loenhout's true
8.2 TWh is Belgium's only large seasonal store, which is why this correction is
not cosmetic.

Expect the fix to bite hardest in **2030/2040**, when Sabatier is actually
running (9.86 TWh of H₂ in 2040). In 2050 Sabatier collapses to
0.1 MW — **not** for lack of CO₂ (110 Mt captured against 125 Mt of
sequestration) but because permanent sequestration outbids methanation for the
same molecules under the carbon budget. That competition belongs with item 9;
it is the reason the 2050 gas bus is pure fossil at a flat 36.35 EUR/MWh and
therefore has nothing seasonal to store.

### Verification

- `build_gas_input_locations` re-run against the live SciGRID/GEM data with the
  existing `base_s_adm` regions: BEVLG storage 545 → 8 178 GWh, other nodes as
  tabled above.
- 7 unit tests in [`test/test_gas_store_potential.py`](../test/test_gas_store_potential.py),
  two of them new: the builder reads the working-gas column, and cushion/working
  are shown to be non-proportional (ratio inverts between an aquifer and a
  depleted field) so that nobody "fixes" this later with a scale factor.
- Full suite, `build_common_parameters.py --check`, and the snakemake DAG all pass.

**Not done:** the sunk-capex convention above, and the `H2 Store` /
salt-cavern asymmetry, which is real geology rather than a bug.

---

## Appendix — H₂ storage by node (asked in review, 29 Aug)

Context for "Belgium has no seasonal fallback". Vintages labelled per table;
unaffected by the gas-storage commits. Cost and potential figures are
structural and identical across vintages.

### Price — two technologies, ~24× apart

The node either has salt caverns or it does not; there is no middle option.

| | technology | overnight 2025 → 2050 | lifetime | FOM | annuity 2050 |
|---|---|---|---|---|---|
| DE, FR, GB, NL | `hydrogen storage underground` | 3.34 → **1.60 EUR/kWh** | 100 y | 0 % | **120 EUR/MWh/a** |
| BEWAL, BEVLG, BEBRU, LU | `hydrogen storage tank type 1 incl. compressor` | 68.13 → **28.08 EUR/kWh** | 27.5–30 y | 1.9 % | **2 912 EUR/MWh/a** |

The overnight gap is 17.5×; the annuity gap widens to **24.2×** on the cavern's
100-year life and zero FOM. Annualised `capital_cost` (EUR/MWh/a):

| node | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| DE / FR / GB / NL | 251 | 201 | 151 | **120** |
| BEWAL / BEVLG / BEBRU / LU | 6 655 | 5 753 | 3 731 | **2 912** |

### Potential

From `salt_cavern_potentials_s_adm.csv`. `sector.hydrogen_underground_storage_locations`
is `[onshore, nearshore]`, so **offshore is excluded by configuration** — and it
is the majority of the resource:

| node | nearshore | offshore *(excluded)* | onshore | used | after >2 TWh filter + 1000 TWh clip |
|---|---:|---:|---:|---:|---:|
| DE | 1 563 | *9 267* | 1 852 | 3 415 | **1 000** ← clipped |
| GB | 441 | *2 920* | 0 | 441 | **441** |
| FR | — | — | 260 | 260 | **260** |
| NL | 50 | *3 585* | 112 | 162 | **162** |
| BEWAL, BEVLG, BEBRU, LU | — | — | — | — | **∞** (tank; no geological limit) |

Belgium and Luxembourg have no rows in the file at all. Their `e_nom_max` is
infinite — the constraint is purely price.

### Size actually built (TWh)

**26 Aug** (the two horizons that exist at that vintage):

| node | 2040 | 2050 |
|---|---:|---:|
| DE | 0.0001 | **4.01** |
| GB | 0.132 | **3.70** |
| NL | 0.194 | **3.24** |
| FR | 0.0004 | **2.09** |
| BEWAL / BEVLG / BEBRU / LU | 0.0000 | **0.0000** |

**14 Aug**, for the shape across all four horizons — treat as indicative only:

| node | 2025 | 2030 | 2040 | 2050 |
|---|---:|---:|---:|---:|
| GB | 0 | 0.030 | 0.136 | 4.92 |
| DE | 0 | 0 | 0 | 2.85 |
| NL | 0 | 0.077 | 0.077 | 2.29 |
| FR | 0 | 0.001 | 0.001 | 1.67 |
| BEWAL / BEVLG / BEBRU / LU | 0 | ~0 | ~0 | ~0.0000002 |

Belgium's three nodes together hold under 1 MWh across all four vintages.
Utilisation against potential is low everywhere — GB uses 0.8 % of its 441 TWh,
DE 0.4 % of 1 000 TWh — so caps are nowhere near binding. **Price separates the
nodes, not geology; geology only decides which price you get.**

### Latent issue: myopic vintage headroom

Each horizon adds a **new vintage store carrying the full geological
`e_nom_max`**, with earlier vintages persisting as non-extendable and nothing
subtracted. By 2050 Germany has four stores each capped at 1 000 TWh — 4 000 TWh
of cumulative headroom against a 3 415 TWh (pre-clip) geological potential.

Same myopic double-counting pattern as the onwind bug documented in
[`test/test_myopic_potentials.py`](../test/test_myopic_potentials.py). For H₂
stores it is **latent, not active** — nothing is remotely near its cap — so it
does not affect this run. Worth revisiting if H₂ storage ever becomes binding.

---

## Open items not addressed here

| | What | Why left |
|---|---|---|
| Sunk-capex convention | every `e_nom_min` floor pays a greenfield annuity | Pre-existing PyPSA-Eur behaviour across all technologies; a modelling decision, not a data fix. |
| H₂ tank vs cavern asymmetry | Belgium pays 24× for H₂ storage | Real geology, not a bug. |
| Offshore salt caverns excluded | 9 267 TWh in DE alone sits unused | Deliberate config choice; revisit only with a reason. |
| Walloon gas pipeline | 7.5 GW at zero `capital_cost` | Separate issue; it is what supplies Walloon seasonal flexibility now that the store is gone. |
| Sabatier vs sequestration | they compete for the same CO₂ in 2050 | Belongs with item 9 of the meeting review (industrial CC). |
