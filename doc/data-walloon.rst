Walloon-specific Data
=====================

* ``data/walloon/be.json`` - shapes of the Belgian sub-regions, used to build the custom Belgian busmap and to assign power
  plants to sub-regions. Read by the ``build_custom_BE_busmap`` rule and
  ``scripts/walloon_scripts/custom_clustering.py`` when `clustering.mode` is ``custom_busmap_BE``.
* ``data/walloon/custom_costs.csv`` – custom cost assumptions used by the Walloon configuration. Data provided by ICEDD.
* ``data/walloon/wal_2021_existing_capacities_2.csv`` - this contains data on existing generators in Wallonia; data provided by ICEDD.
* ``data/custom_powerplants.csv`` – custom power plant modified to include the Walloon (BEWAL) nuclear power plant Tihange as 3 
   separate units for incremental retirement. Doel nuclear power plant in Flanders is also split into multiple generators for incremental
   retirement. Retirement data provided by ICEDD.
* ``data/walloon/custom_potentials.csv`` - custom potentials for the BEWAL region. The file is activated via the `electricity.walloon_potentials` config parameter.
  The potentials include:
  - solid biomass import: maximum amount of biomass that can be imported to BEWAL from outside of the model area (non-Europe) (GWh/an)
  - solid biomass transported: maximum amount of biomass that can be transported from other nodes in the model to BEWAL (GWh/an)
  - solid biomass: maximum amount of local production of solid biomass in BEWAL region (GWh/an)
  - onwind, solar, solar rooftop: maximum potentials for onshore wind, solar PV and rooftop solar PV in BEWAL region (MW)
* ``data/walloon/custom_potentials_imppel.csv``, ``data/walloon/custom_potentials_alternatif.csv``,
  ``data/walloon/custom_potentials_alternatif_biolow.csv`` - per-scenario variants of ``custom_potentials.csv`` for the BEWAL region. 
  The files mostly only differ in the biomass and biogas rows (solid biomass, solid biomass import, solid biomass transported, biogas). 
* ``data/walloon/ntc_2025.csv``, ``data/walloon/ntc_2030.csv``, ``data/walloon/ntc_2035.csv``, ``data/walloon/ntc_2040.csv``,
  ``data/walloon/ntc_2045.csv``, ``data/walloon/ntc_2050.csv`` -
  net transfer capacities (NTCs) between European countries for each planning horizon (MW). The BE interconnection values are based on consultations 
  with ELIA. All other values are from other projects.
* ``data/agg_p_nom_minmax.csv`` - minimum and maximum nominal capacities for aggregated generators at the country or bus level.
  The file is used in the activated via the `solving.agg_p_nom_limits.file` parameter.
  Most values are from TYNDP 2022. Solar-all values for BE and BEWAL are provided by Climact, based on the ELIA ADEXFLEX.
* ``data/walloon/agg_p_nom_minmax_base.csv``, ``data/walloon/agg_p_nom_minmax_corrige.csv``,
  ``data/walloon/agg_p_nom_minmax_sensitivity.csv``, ``data/walloon/agg_p_nom_minmax_demande_haute.csv`` - per-scenario versions of
  ``data/agg_p_nom_minmax.csv``.
* ``data/walloon/discount_rates.csv`` - financial discount (hurdle) rates per technology, in per unit. Activated via the
  `costs.hurdle_rate_fn` parameter. This file is generated in full by ``scripts/build_common_parameters.py --write`` from the
  ``hurdle:*`` rows of ``config/input_parameters_for_models.csv`` and ``config/hurdle_rate_mapping.csv``, so it should not be
  edited by hand. The same script also patches values into ``data/walloon/custom_costs.csv``,
  ``data/walloon/custom_potentials.csv``, every ``data/walloon/ntc_*.csv`` and
  ``data/walloon/agg_p_nom_minmax_demande_haute.csv``; see ``common_parameters.md``.
* ``data/walloon/households.csv`` - number of households per country, in thousands, with a source for each country. Used in
  postprocessing by ``scripts/walloon_scripts/calculate_prices.py`` to express system costs per household.
* ``data/walloon/elia_natural_charging_daily_profile_utc0.csv`` - daily EV charging profiles provided by ELIA, used to shape the
  inflexible share of EV demand. There is one value per hour of the day (0-23) for each data year (2026 and 2036), and one column
  per charging behaviour: ``natural`` for charging that is not managed at all, and ``sunny_PV``, ``sunny_noPV``, ``cloudy_PV``,
  ``cloudy_noPV`` and ``work`` for local demand-side management (sunny or cloudy day, household with or without rooftop PV, and
  charging at work). 
* ``data/walloon/elia_natural_charging_daily_profile_local.csv`` - the original profiles received from ELIA, in Belgian local
  time and with the ``natural`` column only. Kept for reference; the workflow does not read it.
* ``data/walloon/*.vd`` - TIMES output files, one per TIMES scenario, activated when `times_demand: true` and specified by 
  the `sector.times_file` parameter. These are not tracked in the repository (about 75 MB each) and have to be copied in
  separately.
