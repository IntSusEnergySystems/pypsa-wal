Walloon Specific Changes
========================

The Walloon workflow includes several changes to the default PyPSA-Eur:

* **Nuclear capacity expansion**: The `electricity.extendable_nuclear_links` is added to the 
  Walloon configuration in ``config/config.walloon.yaml`` to allow new nuclear capacity 
  to be built as extendable links, for the nodes and horizons specified. Additionally, 
  planned nuclear power plants can be added to ``data/custom_powerplants.csv``. 
* **Custom potentials for BEWAL.** The Walloon configuration uses custom potentials 
  for various energy resources, defined in  ``data/walloon/custom_potentials.csv``. 
  These potentials set maximum limits for solid biomass (imported, transported, and local production)
  in terms of annual energy (GWh/an). There are also maximum potentials for onshore wind, solar PV, 
  and rooftop solar PV in the BEWAL region, defined in MW. These custom potentials are activated
  via the `electricity.walloon_potentials` parameter in the Walloon configuration 
  ``config/config.walloon.yaml``.
* **Custom cost data.** The Walloon configuration uses updated cost assumptions 
  for specified fuels and technologies. These custom values are provided in 
  ``data/walloon/custom_costs.csv`` and activated via the `costs.custom_cost_fn` 
  parameter in the Walloon configuration ``config/config.walloon.yaml``. 
* **Custom power plants retirements.** The Walloon (BEWAL) nuclear power plant, Tihange, 
  is now defined in ``data/custom_powerplants.csv`` with as 3 separate units
  (Tihange 1/2/3) to allow the plant to retire its capacity incrementally. 
  The workflow filters out those rows by the current planning horizon so a unit 
  automatically disappears once its retirement year is passed. 
* **Nuclear retrofit limit.** The ``electricity.retrofit_nuclear_once`` config option limits nuclear retrofits 
  to a single occurrence across horizons to avoid repeated retrofits.
* **Single nuclear representation.** Removed duplication of nuclear representation in 
  model -- before they were represented as both generators and links, now only as links.
* **No new BEWAL nuclear before 2040 and configurable new builds.** ``config/config.walloon.yaml`` 
  contains a Walloon override under ``electricity.extendable_carriers`` that allows nuclear to be
  extendable only for specific planning horizons (e.g. 2040 and 2050). The planning horizon and 
  the carrier list can be configured as needed.
* **Flexible and inflexible EV demand.** Land transport EV electricity demand is split in two: flexible and inflexible, 
  so that only the share of the fleet that offers demand-side flexibility can be shifted in time. The flexible
  share, set by `sector.bev_dsm_availability`, stays on the ``<node> EV battery`` bus as the
  ``land transport EV`` load and remains dispatchable through the ``BEV charger`` link and the DSM store.
  The remaining share is added as a separate fixed load, ``land transport EV inflexible``, which follows
  an observed charging profile instead and is moved to the ``<node> low voltage`` bus when the
  distribution grid is enabled. The split conserves each node's annual energy. 
  This is enabled via the `sector.bev_natural_charging_split` parameter.
* **Charging profiles for the inflexible EV demand.** The profile of the inflexible share is built for each
  planning horizon from ``data/walloon/elia_natural_charging_daily_profile_utc0.csv``, selected via the
  `sector.bev_natural_charging_profile_fn` parameter. The file holds one daily profile per charging
  behaviour and per data year, and the `sector.local_bev_dsm` parameter gives the weight of each behaviour
  in a given planning horizon (the weights have to sum to 1). Because the data years do not match the
  modelled horizons, the data year closest to the planning horizon is used.
* **Year-dependent BEV parameters.** `sector.bev_dsm_availability`, `sector.bev_avail_max`,
  `sector.bev_avail_mean`, `sector.bev_avail_min` and `sector.local_bev_dsm` can be given per planning
  horizon, so that each modelled planning horizon has its own assumption. `sector.bev_avail_min` is a new
  config parameter that sets a floor on the plugged-in availability profile, instead of only warning when 
  the profile goes negative.

With these adjustments the Walloon run retires the Tihange power plant incrementally 
at their scheduled dates, removes duplicate representation of nuclear, and only allows
new Belgian nuclear capacity when the config explicitly enables it.
