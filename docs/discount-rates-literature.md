# Discount rates in the literature — critical review for PyPSA-Wal

Companion to [`discount-rates-analysis.md`](discount-rates-analysis.md). That note documents
**how** rates enter the workflow; this one reviews **what values** the scientific literature
and flagship reports actually support for the technologies we model.

| | |
|---|---|
| **Purpose** | Help ICEDD / Climact / modellers decide whether the sectoral hurdles in the shared CSV are defensible |
| **Not used by** | the Snakemake workflow, `build_common_parameters.py`, or any cost table |
| **Baseline rates reviewed** | production **7.5%**, industry **10%**, tertiary **11%**, residential **12%**, SDR **3.5%** (July 2026 TIMES↔PyPSA agreement) |
| **Status** | literature review only — does **not** change any CSV or config |

All rates below are **real** (inflation-adjusted) unless a source is explicitly marked nominal.
Where a source is silent on real vs nominal or pre-tax vs post-tax, that is noted.

---

## 1. Vocabulary — four rates that must not be conflated

| Type | What it measures | Typical EU range | Role in PyPSA-Wal / TIMES |
|---|---|---|---|
| **Private WACC / financial discount rate** | Cost of capital for a firm or project (debt + equity) | ~3–10% | Annualises overnight CAPEX → `capital_cost` |
| **Hurdle / subjective rate** | Decision rate in energy models; often WACC + perceived risk / barriers | ~7.5–17.5% | What our `hurdle:<sector>` rows encode |
| **Implicit discount rate (IDR)** | Rate that rationalises observed technology adoption; mixes barriers, liquidity, inattention | households often **10–40%+** | Diagnostic of the “energy-efficiency gap”; **not** a direct model input |
| **Social discount rate (SDR)** | Society's time preference for CBA / system-cost NPV | ~1–4% | `costs.social_discountrate` — myopic solves ignore it; used for present-value reporting |

**Critical modelling distinction** (Steinbach & Staniaszek 2015; Hermelink & de Jager /
eceee–Ecofys 2015; Schleich et al. 2016): packing behavioural barriers into a high
discount rate systematically biases optimisation models against capital-intensive
options. Prefer moderate financial rates plus **explicit constraints, soft costs, or
adoption curves** when the goal is social least-cost.

---

## 2. What we currently use

From `config/input_parameters_for_models.csv` / generated `data/walloon/discount_rates.csv`
(see analysis note §7):

| Token | Rate | TIMES sector | PyPSA assignment (≈307 techs) |
|---|---|---|---|
| `production` | **7.5%** | Electricity production, cogen, PV, upstream energy, **all transport** | ~260 techs: generation, storage, grids, DH, H₂/PtX, CO₂, vehicles, charging |
| `industry` | **10%** | Industry | 25 techs: industrial heat pumps, boilers, steel/cement, process CCS |
| `tertiary` | **11%** | Tertiary and agriculture | **0 techs today** (D2: no tertiary split in the cost table) |
| `residential` | **12%** | Residential | 12 techs: all `decentral *`, `micro CHP` |
| SDR | **3.5%** | Social | `costs.social_discountrate` |
| Fallback fill | **7%** | PyPSA default | Only unmapped techs |

Assignment rule (analysis §7): give each technology the rate of the **sector that owns
the investment decision**, not the sector it serves. TIMES treats utility PV, rooftop
PV, domestic batteries and district heating as **production**.

---

## 3. Cross-cutting findings from flagship sources

1. **Flat model rates vs empirical differentiation.** Most European energy-system models
   historically used a single financial rate of **5–8%**. PyPSA-Eur / technology-data
   default is **7%**; IEA/NEA *Projected Costs of Generating Electricity* (2020) uses a
   uniform **real 7%** (sensitivities 3% / 10%). Differentiating by investor sector —
   as we do — is closer to **PRIMES** practice than to classic PyPSA.

2. **Technology rank with offtake support** (Steffen 2020; Egli et al.; Polzin et al.
   2021; Fraunhofer ISE 2024): utility PV ≲ onshore wind < offshore wind < nuclear /
   FOAK clean tech. Country risk and revenue certainty often matter more than the
   technology label.

3. **Observed European RES WACCs are often below our 7.5%.** IRENA *Renewable Power
   Generation Costs in 2024* (2025) assumes a regional Europe WACC of **~3.8%**.
   Fraunhofer ISE (2024, Germany, real @ 1.8% inflation): onshore wind **3.9%**,
   utility PV **3.5%**, small rooftop **3.2%**, offshore **6.0%**. IEA WEO/GEC (2024)
   supported solar/onshore **4–7%** real pre-tax; offshore **5–8%**. Our production
   hurdle is therefore **conservative relative to bankable European RES**, closer to
   IEA/NEA's flat 7% / merchant utility practice than to CfD-backed project finance.

4. **SDR ≠ private WACC.** Using 3.5% for CAPEX annualisation would understate private
   capital costs and over-build capital-intensive options relative to markets. Keeping
   hurdles (7.5–12%) separate from SDR (3.5%) is the right architecture.

5. **Interest-rate cycle.** Post-2022 rate rises pushed analytical WACCs up: IEA
   Renewable Market Update raised an illustrative WACC from **4.5% (2020–22)** to
   **5.5% (2023–24)** outside China; WEO/GEC OECD default plant WACC moved to **~9%
   real pre-tax** (2024 corrigendum). Fixed model hurdles should be revisited when
   macroeconomic conditions shift.

---

## 4. Social discount rate (SDR = 3.5%)

| Jurisdiction / source | Year | Rate | Basis |
|---|---|---|---|
| UK HM Treasury Green Book | 2003– | **3.5%** (yrs 1–30); declining thereafter | Social rate of time preference (Ramsey) |
| EU Better Regulation / IA guidance | ~2015 | **4%** real recommended | SRTP; long-horizon sensitivity lower |
| France Quinet (public investment) | 2013 | Risk-free **2.5%** (+ risk premium → **4.5%** average project) | Declining long-run structure |
| France Stratégie / Quinet climate updates | 2021–25 | Socioeconomic **~3.2%** | Down from older 4.5% |
| Netherlands Discount Rate Working Group | 2020 | Standard **2.25%** | Risk-weighted |
| Germany UBA Methodological Convention | ~2012–22 | **~3%** short; **~1–1.5%** long / climate | SRTP |
| EPBD cost-optimality (macro sensitivity) | 2012 / 2025 | Must include **3%** real | Macroeconomic calculation |
| ENTSO-E CBA guideline lineage | 2015+ | **4%** real | Pan-EU welfare NPV for infrastructure |
| Steinbach & Staniaszek (BPIE / Fraunhofer ISI) | 2015 | EU MS band **1–7%** | Review of practice |
| TIMES-Wal (Meurisse et al., *Energy Policy*) | 2022 | Ramsey **1.8%** (regional *g*) | Explicitly low planner rate; no hurdles |
| PATHS2050 / TIMES-BE (EnergyVille) | 2023 | **3%** | Social planning; sector hurdles disabled |
| Belgian climate modelling survey (climat.be) | ~2013 | TIMES social **2–4%**; PRIMES private higher | Notes normative weight of SDR |

**Ramsey rule:** \(r = \rho + \eta g\) (sometimes + catastrophe premium). UK Green Book:
\(\rho \approx 0.5\%\), catastrophe \(\approx 1\%\), \(\eta g \approx 2\%\) → **3.5%**.

**Verdict on our 3.5%:** Well supported. Matches UK STPR; sits in the middle of European
practice (NL 2.25% – EU IA 4%); consistent with the Belgian OLO-linked rationale stated
at project start. Slightly above current French socioeconomic **3.2%** and Belgian
TIMES-Wal academic **1.8%**; slightly below ENTSO-E CBA **4%**. Appropriate for
**system-cost / welfare** evaluation — never for agent CAPEX annualisation.

---

## 5. Production / energy supply (our rate: 7.5%)

### 5.1 Flagship and model assumptions

| Source | Year | Rate(s) | Notes |
|---|---|---|---|
| IEA/NEA *Projected Costs of Generating Electricity* | 2020 | Uniform **7%** real (3% / 10% sens.) | All technologies and countries |
| IEA WEO / Global Energy and Climate Model | 2024 | OECD default **~9%** real pre-tax; supported PV/onshore **4–7%**; offshore **5–8%** | Differentiated by support regime |
| IRENA RPGC | 2025 (data 2024) | Europe regional WACC **~3.8%** | Used in LCOE; country-risk driven |
| PRIMES / EU Reference Scenario 2016 | 2016 | Grids / FiT RES / public transport **7.5%**; competitive supply **8.5%**; immature-tech premium **+1–3%** | Exact match to our production token for regulated / FiT cases |
| PRIMES (earlier IA materials, eceee 2015) | ~2014 | Power generation **9%** | Pre-REF2016 |
| PyPSA-Eur / technology-data | ongoing | Fill **7%**; eight decentral / rooftop rows **4%** (Palzer) | Default we override |
| DiaCore / Ecofys | 2016 (data ~2014) | Onshore wind WACC **~3.5–4.5% (DE)** to **~12% (GR)**; Belgium among the **low** group | Interview-based project finance |

### 5.2 Technology-specific private WACCs (indicative)

| Technology | Literature cluster (real) | Key sources | Vs our 7.5% |
|---|---|---|---|
| Utility solar PV (supported) | **2.5–6%** | Fraunhofer 3.5%; IEA 4–7%; IRENA Europe ~3.8% | **Our rate high** vs bankable RES |
| Onshore wind (supported) | **3.5–7%** | Fraunhofer 3.9%; IEA 4–7%; DiaCore DE 3.5–4.5% | **Our rate high** / upper end |
| Offshore wind | **5–8%** | Fraunhofer 6.0%; IEA 5–8% | **Aligned** |
| Gas CCGT / OCGT | **6–9%** | Fraunhofer CCGT 6.4%; IEA default ~8–9% | **Aligned** |
| Nuclear new build | **7–10%+** (or **3–5%** if RAB/CfD de-risked) | Fraunhofer 7.8%; IEA/NEA extreme sensitivity at 3/7/10% | **Aligned** as merchant; low if public risk-share |
| Biomass / biogas CHP | **4–8%** | Fraunhofer biogas/biomass 4.2% | **Our rate mid–high** |
| Hydro / PHS | **~6–8%** (thin EU tables) | Modelled like other utility assets | **Aligned** |
| Utility-scale batteries (merchant) | **7–10%** (contracted ~5–7%) | Market commentary; IEA Observatory | **Aligned** for merchant |
| Home / PV-coupled batteries (DE-type finance) | **~2–4%** in LCOE studies | Fraunhofer PV+battery packages 2.2–2.5% | **Our 7.5% high** vs subsidised household finance; **low** vs behavioural hurdles |
| Transmission / distribution (regulatory) | **~3–6%** allowed return | ACER 2023; CREG CAPM for Elia (TSR floor 1.68%, β 0.69) | **Our 7.5% high** vs regulated RAB |
| TYNDP CBA (social) | **4%** | ENTSO-E | SDR territory, not private |
| District heating (municipal) | Often **very low** (cost-recovery) | DK municipal / Kommunekredit examples | Commercial DH higher / heterogeneous |
| Electrolysers / PtX / synfuels | **~6–10%** | Agora LCOH ~7%; IEA H₂ Review capital sensitivity; EU Observatory LCOH **6%** | **Aligned** |
| CCS (capture / T&S) | Often **~8%** (sens. 6–10%) | ZEP-style European TEAs | **Slightly low** at 7.5%; PRIMES immature premium would add 1–3 pp |
| DAC | Base **5–8%**; FOAK **10–15%** | Fasihi et al. 2019 (7%); various TEAs | **Aligned** for NOAK; low for FOAK |

**Fraunhofer ISE (2024) snapshot — real WACC, Germany:**

| Tech | Real WACC | Debt/equity | Equity return |
|---|---|---|---|
| PV rooftop small | 3.2% | 80/20 | 5.0% |
| PV utility / large rooftop | 3.5% | 80/20 | 6.5% |
| Onshore wind | 3.9% | 80/20 | 7.0% |
| Biogas / solid biomass | 4.2% | 80/20 | 8.0% |
| Offshore wind | 6.0% | 70/30 | 10.0% |
| CCGT / GT | 6.4% | 60/40 | 10.0% |
| Lignite / hard coal | 6.8% | 60/40 | 11.0% |
| H₂ CCGT / GT | 6.9% | 60/40 | 11.3% |
| Fuel cell / nuclear | 7.8% | 60/40 | 12.0% |

**Verdict on production 7.5%:**
- **Well aligned** with PRIMES regulated/FiT supply (**7.5%**), IEA/NEA flat LCOE
  practice (**7%**), and PyPSA default (**7%**).
- **Conservative (high)** relative to observed European WACCs for supported utility PV
  and onshore wind (**~3.5–6%**), and relative to regulated grid returns (**~3–6%**).
- **Reasonable** for a single production bucket that also covers offshore, gas, nuclear,
  merchant storage, H₂/PtX and CCS — a flat 7.5% averages a heterogeneous risk set.
- Sensitivity worth running: a **lowrate** variant at ~4–5% for mature RES (closer to
  IRENA/Fraunhofer) vs keeping 7.5% for FOAK / merchant.

---

## 6. Industry (our rate: 10%)

| Source | Year | Rate | Type | Notes |
|---|---|---|---|---|
| PRIMES REF2016 / REF2020 | 2016 / 2021 | Energy-intensive **7.5%**; non-EI **9%** | Firm WACC | Our 10% is slightly above non-EI |
| PRIMES IA materials (eceee 2015) | ~2014 | Industry **12%** | Subjective | Older, higher |
| Early PRIMES overviews (climat.be) | n.d. | Heavy industry **10–12%** | WACC | Matches our token |
| Steinbach & Staniaszek | 2015 | Commercial / industrial **6–15%** | Financial | Across EU studies |
| France Stratégie (*Investissements bas carbone*) | 2024 | Firm WACC **6.5–9.5%**, median **~8%** | WACC | Below our 10% |
| IEA cost of capital (clean transitions) | 2021–24 | Industry **4–15%** | Cost of capital | Wide band |
| García-Gusano et al. (*RSER*) | 2016 | Use tech hurdles separately from SDR ≤4–5% | Method | TIMES recommendation |

**Verdict on industry 10%:** Plausible as a **blended** industry hurdle between PRIMES
energy-intensive (**7.5%**) and older IA industry (**12%**). Slightly high vs recent
French firm WACC surveys (~8%) and vs PRIMES EI. Defensible if Walloon industry is
treated as mixed EI/non-EI with project risk on electrification and CCS (PRIMES
immature-tech premium **+1–3%**). A split EI **8%** / non-EI **10–11%** would track
PRIMES REF more closely if ever needed.

---

## 7. Tertiary / services (our rate: 11% — unused in mapping today)

| Source | Year | Rate | Type | Notes |
|---|---|---|---|---|
| PRIMES REF2016 / REF2020 | 2016 / 2021 | Services **11%** | Firm WACC | **Exact match** |
| PRIMES IA (eceee 2015) | ~2014 | Tertiary **12% → 11% → 10%** with EED | Subjective | Declining with EE policy |
| Early PRIMES | n.d. | Services **11–14%** | WACC | Broader band |
| Steinbach review | 2015 | Commercial **6–15%** | Financial | — |
| France Stratégie | 2024 | Firm median **~8%** | WACC | Pure WACC below PRIMES services |

**Verdict on tertiary 11%:** Directly aligned with PRIMES REF services. Slightly above
pure corporate WACC surveys, consistent with treating SMEs / services as higher-risk
than heavy industry. Keeping the token defined (even with zero mapped techs) preserves
TIMES fidelity and enables a future residential/tertiary split (decision D2).

---

## 8. Residential / decentral heat (our rate: 12%)

### 8.1 Model hurdles vs financial cost of capital

| Source | Year | Rate | Type | Notes |
|---|---|---|---|---|
| PRIMES REF2016 / REF2020 | 2016 / 2021 | Household renovation + heating **12%** (14.75% without EE policies); appliances **9.5%** | Subjective hurdle | **Exact match** to our residential rate under EE policies |
| PRIMES IA / EUCO | ~2014–17 | Households **17.5% → 14.75% → 12% → 10%** | Subjective | Policy intensity lowers the rate |
| Steinbach & Staniaszek | 2015 | Recommend household **3–6%** (market capital cost); critique PRIMES for packing barriers into the rate | Financial | Barriers → behavioural models, not \(r\) |
| France Stratégie | 2024 | Households **3–13%**, median **~10%** | Heterogeneous hurdle | Income distribution |
| IEA | 2021–24 | Buildings end-use **5–25%** | Cost of capital | Households → corporates |
| technology-data / Palzer | ongoing | Eight decentral / rooftop techs at **4%** | Model | What we **override** to 12% |

### 8.2 Implicit / behavioural rates (consumer studies)

| Source | Year | Rate | Type | Notes |
|---|---|---|---|---|
| Haq & Weiss (JRC) | 2018 | **19 ± 17%** (median ± ½ IQR) | Implicit | Meta-review of efficient energy & transport durables |
| Schleich et al. (*Energy Policy*) | 2016 | Framework: preferences + biases + barriers | Method | Warn against treating IDR as a single lever |
| Classic EE-gap literature (Train and successors) | 1985+ | Observed IDRs often **>>** market rates | Implicit | Still the reference magnitudes |

**Verdict on residential 12%:**
- Strongly supported as a **PRIMES-style decision hurdle** for heating/renovation under
  EE policies — that is the closest peer to our TIMES sectoral design.
- **Not** a pure household financing WACC (Steinbach would use **3–6%**; Fraunhofer
  rooftop finance is even lower).
- **Not** a full behavioural IDR (empirical medians often **~15–30%+**).
- Our 12% is best read as a **middle, policy-adjusted hurdle**. Raising decentral heat
  from technology-data's **4%** to **12%** is a large, intentional shift that favours
  OPEX over CAPEX in buildings — quantify impacts before publishing (analysis §14).

---

## 9. Transport — the main assignment tension

Our mapping puts **all** vehicles and charging infrastructure in `production` at
**7.5%**. Literature splits by agent:

| Segment | PRIMES REF2016 / 2020 | Older PRIMES IA | Our mapping | Assessment |
|---|---|---|---|---|
| Public transport (buses, rail) | **7.5%** (advanced **8.5%**) | **8%** | 7.5% | **Supported** |
| Business freight / HGV / aviation / maritime | **9.5%** | Trucks **12%** | 7.5% | **Somewhat low** |
| Charging / refuelling infrastructure | **8.5%** (REF2020) | — | 7.5% | **Slightly low**, close |
| **Private passenger cars** | **11%** | **17.5%** | **7.5%** | **Materially low** for household adoption |

JRC Haq & Weiss (2018) find high implicit rates for efficient **transport** durables
alongside energy durables (**19 ± 17%**).

**Implication:** Leaving passenger cars at 7.5% while residential heat pumps are at 12%
**favours vehicle electrification over building electrification** for purely
discount-rate reasons. That is defensible only if transport CAPEX is interpreted as
**fleet / operator** investment (leasing, company cars, logistics), not household
purchase. PRIMES puts household cars with individuals (~11%), not with power utilities.

---

## 10. Rooftop PV and home batteries — agent vs technology

| Framing | Rate logic | Literature |
|---|---|---|
| Utility / merchant / FiT-supported PV | Supply WACC **~7.5–8.5%** (our production) | PRIMES supply tables |
| Household rooftop + battery as **prosumer** self-consumption | Residential hurdle **~10–12%** (or higher IDR) | Same agent as heat pumps; FR HH median ~10% |
| Engineering LCOE with household / cooperative finance | Sometimes **lower** WACC than large plants | Fraunhofer: small rooftop **3.2%** real; PV+battery packages **2.2–2.5%** |

**Practical implication:** Mapping rooftop PV and home batteries to **production 7.5%**
while heat pumps are at **residential 12%** systematically favours behind-the-meter
electricity assets over thermal EE in the optimisation. If the household is the
decision-maker for both, consistency argues for **residential**. If rooftop is treated
as a generation asset with power-sector financing (the TIMES supply convention),
**production** is coherent — but that assumption should stay explicit.

---

## 11. Building retrofit interest rate (out of scope, but literature-relevant)

`sector.retrofitting.interest_rate` remains at **4%** (analysis D4) — a separate lever
outside the hurdle file. Literature:

| Perspective | Typical rate | Sources |
|---|---|---|
| Social / cost-optimality macro | **3–4%** | EPBD Delegated Reg.; UK/FR SDR practice |
| PRIMES household renovation hurdle | **12%** (14.75% without EE) | REF2016 / REF2020 |
| Financial household cost of capital | **3–6%** | Steinbach 2015 |

Keeping retrofit at 4% while decentral heat is at 12% **favours envelope renovation
relative to heat-pump CAPEX** inside the model. Harmonising retrofit to the residential
hurdle would be a separate, high-impact change — tracked outside this review.

---

## 12. How the literature supports or challenges our set

| Our rate | Supports | Challenges |
|---|---|---|
| **Production 7.5%** | PRIMES grids/FiT/public transport **7.5%**; competitive supply **8.5%**; IEA/NEA flat **7%**; PyPSA **7%** | Bankable EU RES often **3.5–6%**; regulated grids **3–6%**; IRENA Europe **~3.8%** |
| **Industry 10%** | Older PRIMES industry **12%**; heavy-industry band **10–12%**; IEA up to **15%** | PRIMES EI **7.5%** / non-EI **9%**; FR firm median **~8%** |
| **Tertiary 11%** | **Exact PRIMES services rate** | Pure WACC surveys ~**8%**; unused in mapping today |
| **Residential 12%** | **Exact PRIMES renovation/heating** (with EE policies) | Financial HH **3–6%** (Steinbach); IDRs often **15–30%+**; FR median **~10%**; overrides tech-data **4%** |
| **SDR 3.5%** | UK Green Book; mid EU band; BE social practice ~3–4% | FR now **~3.2%**; NL **2.25%**; climate-ethics arguments for **1–2%**; TIMES-Wal academic **1.8%** |

**Overall reading:** the ladder is best interpreted as a **PRIMES-compatible private
decision / hurdle schedule** for TIMES↔PyPSA harmonisation — not as pure engineering
WACCs and not as full behavioural IDRs. That is a coherent modelling choice. The largest
internal tensions are **assignment**, not the four headline numbers:

1. All transport at 7.5% (especially household cars).
2. Rooftop PV / home batteries at production while decentral heat is at residential.
3. Retrofit interest still at 4% while residential heat is at 12%.
4. A single production rate for both CfD-backed RES (~4%) and FOAK PtX/CCS (~8–10%).

---

## 13. Recommendations for modellers (no workflow changes)

These are decision aids, not implementation tasks.

1. **Keep the architecture.** Sectoral hurdles (7.5–12%) + separate SDR (3.5%) matches
   best practice and PRIMES REF. Do not collapse them.

2. **Treat 7.5 / 10 / 11 / 12 as a PRIMES-style reference, not market WACC.** Document
   that production 7.5% is intentionally above observed European RES project finance.

3. **Priority sensitivity variants** (via `hurdle:<variant>:<sector>` — analysis §10.5):
   - `lowrate`: all sectors near SDR / social (~3.5%) — social-planner counterfactual.
   - `market_res`: production ~4–5% (IRENA/Fraunhofer cluster) for mature RES impact.
   - `resid09` or `resid15`: residential 9% vs 15% — bound the heat-pump vs gas-boiler
     trade-off.
   - Optionally a transport split: cars ~11%, fleets/public ~7.5–9.5%.

4. **Revisit assignments before changing rates:**
   - Passenger cars → nearer residential / PRIMES 11% if household purchase is intended.
   - Rooftop PV / home batteries → residential if prosumer logic; keep production if
     TIMES supply convention is intentional (document which).
   - Grids → could sit below 7.5% (regulatory 3–6%) if ever split from generation.

5. **Do not use high hurdles as a barrier model.** Prefer capacity constraints,
   soft-cost mark-ups, or exogenous uptake for renovation pace and permitting
   (analysis §6 administrative barriers).

6. **Real, pre-tax convention.** Confirm that TIMES and PyPSA interpret the shared
   fractions the same way (real vs nominal; tax). Mixing invalidates LCOE/annuity
   comparisons. Fraunhofer's 2024 real rates assume **1.8%** inflation — our hurdles
   should be read as **real** to stay comparable with PRIMES REF.

7. **Macro update cycle.** After large shifts in Belgian OLO / ECB rates, re-benchmark
   production against DiaCore-style or IRENA country WACCs and SDR against the OLO
   rationale that justified 3.5%.

---

## 14. Key primary sources

### Flagship reports and official guidance
- IEA / OECD NEA, *Projected Costs of Generating Electricity*, 2020 (uniform real 7%).
- IEA, World Energy Outlook / Global Energy and Climate Model documentation, 2024
  (differentiated pre-tax WACCs; OECD default ~9%).
- IRENA, *Renewable Power Generation Costs in 2024*, 2025 (Europe WACC ~3.8%).
- IRENA, *The Cost of Financing for Renewable Power*, 2023 (survey CoC by region/tech).
- European Commission, *EU Reference Scenario 2016* and *2020* (PRIMES discount-rate
  tables by sector).
- eceee / Ecofys (Hermelink & de Jager), *Evaluating our future*, 2015 (critique of
  high PRIMES rates in IAs).
- ENTSO-E CBA guideline lineage (social discount **4%** real for infrastructure NPV).
- HM Treasury, *The Green Book* (STPR **3.5%**).
- France Stratégie / Quinet reports (risk-free 2.5%; socioeconomic updates ~3.2%).
- CREG tariff methodology 2024–2027 for Elia (CAPM; OLO-linked risk-free rate).

### Scientific / technical literature
- Steinbach, J. & Staniaszek, D. (2015), *Discount rates in energy system analysis*,
  BPIE / Fraunhofer ISI.
- Schleich, J. et al. (2016), *Energy Policy* — implicit discount rates and the EE gap.
- Haq, G. & Weiss, M. (2018), JRC — consumer discount rates for efficient durables
  (19 ± 17%).
- Steffen, B. (2020), *Energy Economics* — estimating WACC for renewable energy.
- Polzin, F. et al. (2021) and related DiaCore / Ecofys (2016) country–technology WACC
  datasets.
- Fraunhofer ISE, *Levelized Cost of Electricity — Renewable Energy Technologies*, 2024
  (technology-specific real WACCs for Germany).
- García-Gusano, D. et al. (2016), *Renewable and Sustainable Energy Reviews* — discount
  rates in energy system optimisation.
- Meurisse et al. (2022), *Energy Policy* — TIMES-Wal; Ramsey SDR 1.8%, no hurdles.
- PATHS2050 / EnergyVille TIMES-BE documentation (social 3%).

### Model / project context
- [`discount-rates-analysis.md`](discount-rates-analysis.md) — workflow, decisions D1–D6,
  mapping rules.
- `config/input_parameters_for_models.csv` — authoritative hurdle / SDR values.
- `config/hurdle_rate_mapping.csv` — technology → sector assignment.
- PyPSA / technology-data default fill **0.07**; Palzer **0.04** for eight decentral /
  rooftop rows (overridden by the hurdle file).

---

## 15. One-page cheat sheet

| Bucket | Our rate | Literature centre of gravity | One-line judgement |
|---|---|---|---|
| SDR | 3.5% | EU/UK/BE social practice ~2–4% | **Keep** |
| Production | 7.5% | PRIMES supply 7.5–8.5%; bankable RES 3.5–6%; IEA flat 7% | **Keep as PRIMES-style hurdle**; high vs market RES |
| Industry | 10% | PRIMES EI 7.5% / non-EI 9%; surveys ~8%; older IA 12% | **Keep** as blend; slightly high for EI |
| Tertiary | 11% | PRIMES services 11% | **Keep** (even unused) |
| Residential | 12% | PRIMES renovation/heating 12%; financial HH 3–6%; IDR 15–30%+ | **Keep as decision hurdle**; not pure WACC |
| Transport @ 7.5% | — | Cars 11% (PRIMES); fleets 7.5–9.5% | **Revisit assignment** for household cars |
| Rooftop / home battery @ 7.5% | — | Agent-dependent (3–12%) | **Document** supply vs prosumer convention |
| Retrofit interest 4% | — | Social ~3%; PRIMES renovation 12% | **Separate decision** (D4); inconsistent with residential 12% |
