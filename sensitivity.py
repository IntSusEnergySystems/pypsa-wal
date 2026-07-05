#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 20:46:07 2026

@author: umair
"""

import pypsa
import pandas as pd

countries = ["BEBRU","BEVLG","BEWAL","DE","FR","GB","LU","NL"]
scenarios = {
    "scen_corrige_overnight","scen_corrige_90","scen_corrige_85",
    "scen_corrige_80","scen_corrige_75","scen_corrige_70",
    "scen_corrige_65","scen_corrige_60","scen_corrige_55",
    "scen_corrige_50","scen_corrige_45","scen_corrige_40",
    "scen_corrige_35","scen_corrige_30","scen_corrige_25",
    "scen_corrige_baseline",
}
rows_price = []

for country in countries:
    for scenario in scenarios:
        n = pypsa.Network(f"/home/umair/pypsa-wal/results/{scenario}/networks/base_s_adm___2050.nc")
        co2 = n.global_constraints["mu"].round(2)
        
        co2_price = abs(co2.loc[f"co2_limit_per_country{country}"])
        
        rows_price.append({
            "country": country,
            "scenario": scenario,
            "co2_price": co2_price
        })

df_price = pd.DataFrame(rows_price)

#%%
rows_limit = []

for country in countries:
    for scenario in scenarios:
        n = pypsa.Network(f"/home/umair/pypsa-wal/results/{scenario}/networks/base_s_adm___2050.nc")
        co2_budget = n.global_constraints["constant"]/1e6
        
        co2_limit = co2_budget.loc[f"co2_limit_per_country{country}"]
        
        rows_limit.append({
            "country": country,
            "scenario": scenario,
            "co2_limit": co2_limit
        })

df_limit = pd.DataFrame(rows_limit)

#%%

tech_map = {
    'offwind-ac': 'Offshore Wind',
    'offwind-dc': 'Offshore Wind',
    'offwind-float': 'Offshore Wind',
    'onwind': 'Onshore Wind',
    'solar': 'Solar PV',
    'solar rooftop': 'Solar PV',
    'solar-hsat': 'Solar PV',
    'PHS': 'Hydro',
    'hydro': 'Hydro',
    'ror': 'Hydro',
    'AC': 'Grid Infrastructure',
    'DC': 'Grid Infrastructure',
    'H2 pipeline': 'Grid Infrastructure',
    'electricity distribution grid': 'Grid Infrastructure',
    'gas pipeline': 'Grid Infrastructure',
    'gas pipeline new': 'Grid Infrastructure',
    'CO2 pipeline': 'Grid Infrastructure',
    'rural air heat pump': 'Heat Pumps',
    'rural ground heat pump': 'Heat Pumps',
    'urban decentral air heat pump': 'Heat Pumps',
    'urban central air heat pump': 'Heat Pumps',
    'urban decentral water tanks discharger': 'TES',
    'urban decentral water tanks charger': 'TES',
    'urban decentral water tanks': 'TES',
    'urban decentral heat vent': 'TES',
    'rural heat vent': 'TES',
    'urban central water tanks discharger': 'TES',
    'urban central water tanks charger': 'TES',
    'urban central water tanks': 'TES',
    'urban central water pits discharger': 'TES',
    'urban central water pits charger': 'TES',
    'urban central water pits':'TES',
    'urban central heat vent': 'TES',
    'rural water tanks discharger':'TES',
    'rural water tanks charger':'TES',
    'rural water tanks':'TES',
    'CCGT': 'Gas-fired Powerplants',
    'OCGT': 'Gas-fired Powerplants',
    'H2 Electrolysis': 'Hydrogen Production',
    'SMR': 'Hydrogen Production',
    'SMR CC': 'Hydrogen Production',
    'H2 Store': 'Hydrogen Production',
    'Fischer-Tropsch': 'Synthetic Fuels',
    'Haber-Bosch': 'Synthetic Fuels',
    'Sabatier': 'Synthetic Fuels',
    'biomass to liquid': 'Synthetic Fuels',
    'biomass-to-methanol': 'Synthetic Fuels',
    'methanolisation': 'Synthetic Fuels',
    'rural biomass boiler': 'Boilers',
    'rural gas boiler': 'Boilers',
    'urban central gas boiler': 'Boilers',
    'urban decentral biomass boiler': 'Boilers',
    'urban decentral gas boiler': 'Boilers',
    'urban decentral solar thermal': 'Solar Thermal',
    'urban central solar thermal': 'Solar Thermal',
    'rural solar thermal': 'Solar Thermal',
    'urban central solid biomass CHP CC': 'CHP',
    'urban central solid biomass CHP': 'CHP',
    'urban central gas CHP CC': 'CHP',
    'urban central gas CHP': 'CHP',
    'urban decentral resistive heater': 'Electric Heating',
    'urban central resistive heater': 'Electric Heating',
    'rural resistive heater': 'Electric Heating',
    'BEV charger': 'Battery Storage',
    'EV battery': 'Battery Storage',
    'battery': 'Battery Storage',
    'battery charger': 'Battery Storage',
    'battery discharger': 'Battery Storage',
    'home battery': 'Battery Storage',
    'home battery charger': 'Battery Storage',
    'home battery discharger': 'Battery Storage',
    'DAC': 'CCS',
    'co2 sequestered': 'CCS',
    'co2 stored': 'CCS',
    'process emissions CC': 'CCS',
    'process emissions': 'CCS',
    'biogas': 'Fuels',
    'biogas to gas': 'Fuels',
    'unsustainable biogas': 'Fuels',
    'unsustainable bioliquids': 'Fuels',
    'unsustainable solid biomass': 'Fuels',
    'gas': 'Fuels',
    'gas for industry': 'Fuels',
    'gas for industry CC': 'Fuels',
    'non-sequestered HVC': 'Fuels',
    'solid biomass': 'Fuels',
    'solid biomass for industry': 'Fuels',
    'solid biomass for industry CC': 'Fuels',
    'HVC to air': 'Fuels',
    'V2G': 'Other Generation',
    'H2 Fuel Cell': 'Other Generation',
    'H2 turbine': 'Other Generation',
    'nuclear': 'Nuclear'
}
rows_costs = []
for country in countries:
 for scenario in scenarios:
    df = pd.read_csv(f"/home/umair/pypsa-wal/results/{scenario}/csvs/nodal_costs.csv", index_col=2)
    df = df.iloc[:, 2:]
    df = df.iloc[3:, :]
    df = df.rename(columns={'Unnamed: 3': 'tech', 'adm': 'costs'})
    df = df[df.index == country]
    df = df.groupby('tech').sum().reset_index()
    df['tech'] = df['tech'].map(tech_map).fillna(df['tech'])
    df = df.groupby('tech').sum().reset_index()
    for _, row in df.iterrows():
            rows_costs.append({
                "country": country,
                "scenario": scenario,
                "tech": row["tech"],
                "costs": row["costs"]/ 1e9
            })
            
df_costs = pd.DataFrame(rows_costs)

#%%
scenario_order = [
    "scen_corrige_baseline","scen_corrige_25","scen_corrige_30",
    "scen_corrige_35","scen_corrige_40","scen_corrige_45",
    "scen_corrige_50","scen_corrige_55","scen_corrige_60",
    "scen_corrige_65","scen_corrige_70","scen_corrige_75",
    "scen_corrige_80","scen_corrige_85","scen_corrige_90",
    "scen_corrige_overnight"
]

color_map = {
    'Offshore Wind': '#6895dd',
    'Onshore Wind': '#235ebc',
    'Solar PV': '#f9d002',
    'Hydro': '#298c81',
    'Grid Infrastructure': '#110d63',
    'Heat Pumps': '#2fb537',
    'TES': '#d96f4c',
    'Gas-fired Powerplants': '#ff8c00',
    'Hydrogen Production': '#bf13a0',
    'Synthetic Fuels': '#46caf0',
    'Boilers': '#ffb07c',
    'Solar Thermal': '#fdb915',
    'CHP': '#8d5e56',
    'Electric Heating': '#d8f9b8',
    'Battery Storage': '#11875d',
    'CCS': '#ff5270',
    'Fuels': '#c9c9c9',
    'Other Generation': '#9a0200',
    'Nuclear': 'purple'
}
df_all = df_costs.merge(df_price, on=["country", "scenario"])
df_all = df_all.merge(df_limit, on=["country", "scenario"])

import matplotlib.pyplot as plt

for country in countries:

    df_c = df_all[df_all["country"] == country].copy()

    # enforce correct scenario order
    df_c["scenario"] = pd.Categorical(
        df_c["scenario"],
        categories=scenario_order,
        ordered=True
    )
    df_c = df_c.sort_values("scenario")

    x = (
        df_c[["scenario", "co2_price"]]
        .drop_duplicates()
        .set_index("scenario")
        .loc[scenario_order]["co2_price"]
    )

    co2_limit = (
        df_c[["scenario", "co2_limit"]]
        .drop_duplicates()
        .set_index("scenario")
        .loc[scenario_order]["co2_limit"]
    )

    df_pivot = df_c.pivot_table(
        index="scenario",
        columns="tech",
        values="costs",
        aggfunc="sum"
    ).fillna(0)

    df_pivot = df_pivot.loc[scenario_order]

    #topdownn stack
    total_cost = df_pivot.sum(axis=1)

    
    df_rev = df_pivot[df_pivot.columns[::-1]]

    # cumulative sum
    cum = df_rev.cumsum(axis=1)

    fig, ax1 = plt.subplots(figsize=(10, 6))

    ax1.plot(x, co2_limit, color="white", linewidth=2)
    ax1.set_ylabel("CO2 limit [Mt]")
    ax1.set_xlabel("CO2 price [€/tCO2]")
    ax1.grid(True, which='both', linestyle='--', linewidth=0.7, alpha=0.7)
    ax2 = ax1.twinx()

    ax2.stackplot(
    x,
    df_pivot.T.values,
    labels=df_pivot.columns,
    colors=[color_map.get(tech, "#333333") for tech in df_pivot.columns]
)

    ax2.set_ylabel("System costs [Billion Euros] ")

    ax2.invert_yaxis()

    ax2.legend(
    loc="upper left",
    bbox_to_anchor=(1.05, 1),
    fontsize=8
)

    plt.title(f"{country}")
    plt.tight_layout()
    plt.show()
