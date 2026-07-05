#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots 
import os
import shutil
from datetime import datetime
import plotly.express as px
from jinja2 import Template
import yaml
from scripts.plot_summary import rename_techs, preferred_order
from scripts.make_summary import assign_locations
from scripts.make_summary import assign_carriers
import pypsa
from functools import lru_cache
import json

paths = {
    "scen_base": "results/scen_base/networks/base_s_6___{year}.nc",
    "scen_corrige": "results/scen_corrige/networks/base_s_6___{year}.nc",
    "scen_suff": "results/scen_suff/networks/base_s_6___{year}.nc",
}

@lru_cache(maxsize=None)
def load_networks(year):
    year = int(year)
    return {
        scen: pypsa.Network(path.format(year=year))
        for scen, path in paths.items()
    }

def rename_techs_tyndp(tech):
    tech = rename_techs(tech)
    if tech in ["H2 Electrolysis", "methanation", 'methanolisation',"helmeth", "H2 liquefaction"]:
        return "power-to-gas"
    elif "H2 pipeline" in tech:
        return "H2 pipeline"
    elif tech in ["nuclear", "uranium"]:
        return "nuclear"
    elif tech in [ "battery charger", "battery discharger"]:
        return "battery storage"
    elif "solar" in tech:
        return "solar"
    elif tech == "Fischer-Tropsch":
        return "power-to-liquid"
    elif "offshore wind" in tech:
        return "offshore wind"
    elif tech in ["CO2 sequestration", "co2", "SMR CC", "process emissions CC","process emissions", "solid biomass for industry CC", "gas for industry CC"]:
         return "CCS"
    elif tech in ["biomass", "biomass boiler", "solid biomass", "solid biomass for industry"]:
         return "biomass"
    elif "load" in tech:
        return "load shedding"
    elif tech == "coal" or tech == "lignite":
          return "coal"
    else:
        return tech
    
def preprocess_emissions(df, code_to_label):
    
    df = df.rename(columns=code_to_label)

    df['Industry'] = df[
        ['Other energy industry', 'Industrial processes', 'Fuel usage - industry']
    ].sum(axis=1)

    df = df.drop(columns=[
        'Other energy industry',
        'Industrial processes',
        'Fuel usage - industry'
    ], errors='ignore')

    df = df.rename(columns={
        "Fuel combustion - agriculture": "Agriculture",
        "Fuel combustion - transport": "Transport",
        "Fuel combustion - aviation bunkers": "Aviation bunkers",
        "DAC": "DACCS",
        "Fuel combustion – inland waterways": "Inland waterways",
        "biogas": "Biogas",
        "Fuel combustion – residential and tertiary":
            "Residential and tertiary sectors"
    })

    df = df.loc[:, (df != 0).any(axis=0)]

    df['Total'] = df.sum(axis=1)

    cumulative = df.drop(columns='Total').cumsum()
    positive = cumulative.where(cumulative > 0, 0)
    negative = cumulative.where(cumulative < 0, 0)

    positive = positive.loc[:, (positive != 0).any()]
    negative = negative.loc[:, (negative != 0).any()]

    total = df['Total'].cumsum()

    return positive, negative, total

def Cumulative_emissions_sector(country):

    file = snakemake.input.sepia_config
    config = pd.read_excel(file, sheet_name="NODES", index_col=0)
    config = config[config['Type'] == 'GHG_SECTORS']
    code_to_label = config['Label'].to_dict()

    scenarios = {
        "scen_base": f"results/scen_base/country_csvs/ghg_sector_cum_{country}.csv",
        "scen_corrige": f"results/scen_corrige/country_csvs/ghg_sector_cum_{country}.csv",
        "scen_suff": f"results/scen_suff/country_csvs/ghg_sector_cum_{country}.csv",
    }

    n_scen = len(scenarios)

    fig = make_subplots(
        rows=1,
        cols=n_scen,
        subplot_titles=list(scenarios.keys())
    )

    colors = {
            "Agriculture": "#11875d",
            "Industry": "#fcc006",
            "Transport": "#c14a09",
            "Residential and tertiary sectors": "#9a0200",
            "Inland waterways": "#fd5956",
            "Aviation bunkers": "#f0833a",
            "BECCS": "#c5c9c7",
            "Biogas": "#32bf84",
            "Biomass": "#11875d",
            "DACCS": "#ffbacd",
            "Heat and power production ": "#01889f",
            "Land use and forestry": "#82cbb2",
            "GHG Agriculture": "#95d0fc"
        }

    for i, (scenario_name, path) in enumerate(scenarios.items(), start=1):

        df = pd.read_csv(path, index_col=0)

        positive, negative, total = preprocess_emissions(df, code_to_label)

        # Positive stack
        for col in positive.columns:
            fig.add_trace(
                go.Scatter(
                    x=positive.index,
                    y=positive[col],
                    mode='lines',
                    fill='tonexty',
                    name=col,
                    line=dict(color=colors.get(col, "#000000")),
                    stackgroup=f'positive_{i}',
                    legendgroup=col,
                    showlegend=(i == 1)
                ),
                row=1, col=i
            )

        # Negative stack
        for col in negative.columns:
            fig.add_trace(
                go.Scatter(
                    x=negative.index,
                    y=negative[col],
                    mode='lines',
                    fill='tonexty',
                    name=col,
                    line=dict(color=colors.get(col, "#000000")),
                    stackgroup=f'negative_{i}',
                    legendgroup=col,
                    showlegend=False
                ),
                row=1, col=i
            )

        # Total line
        fig.add_trace(
            go.Scatter(
                x=total.index,
                y=total,
                mode='lines',
                name="Total",
                line=dict(color='black', width=2),
                legendgroup="Total",
                showlegend=(i == 1)
            ),
            row=1, col=i
        )
    all_years = positive.index.tolist()
    tickvals = all_years
    ticktext = ["2025" if y == 2020 else str(y) for y in all_years]
    fig.update_layout(
        title="Cumulative Emissions by Sector",
        height=700,
        width=700 * n_scen,
        legend=dict(orientation="h", y=-0.2),
        template="plotly_white",
        xaxis=dict(tickvals=tickvals, ticktext=ticktext),
        xaxis2=dict(tickvals=tickvals, ticktext=ticktext) if n_scen > 1 else None)

    return fig

def preprocess_chartdata(path, column_map):

    df = pd.read_excel(
        path,
        sheet_name="Chart 30",
        index_col=0,
        skiprows=2
    )
    df.index = df.index.map(lambda x: 2025 if x == 2020 else x)
    df = df.drop(columns=["Ambient heat"], errors="ignore")
    df = df.rename(columns=column_map)
    df = df.groupby(df.columns, axis=1).sum()

    df.index = df.index.astype(int)
    
    new_index = range(df.index.min(), df.index.max() + 1)
    df = df.reindex(new_index)

    df = df.interpolate(method='spline', order=2)

    total = df.sum(axis=1)
    nonzero = df.loc[:, (df != 0).any(axis=0)]

    return df, total, nonzero

def spline_plot(country):

    column_map = {
        'EV': 'Electricity',
        'Methanol': 'Others',
        'Coal': 'Others',
        'Ammonia': 'Others',
        # 'Ambient heat': 'Others',
        'Solid biomass': 'Biomass',
        'Network gas': 'Gas',
        'Network heat / steam': 'Others'
    }

    scenarios = {
        "scen_base": f"results/scen_base/htmls/ChartData_{country}.xlsx",
        "scen_corrige": f"results/scen_corrige/htmls/ChartData_{country}.xlsx",
        "scen_suff": f"results/scen_suff/htmls/ChartData_{country}.xlsx",}

    tech_colors = config["plotting"]["tech_colors"]
    tech_colors.update({
        "Liquid fuels": "#c5c9c7",
        "Hydrogen": "#95d0fc",
        "Gas": "#fcc006",
        "Biomass": "#11875d",
        "Electricity": "#01889f",
        "Others": "#fd5956"
    })

    fig = go.Figure()

    # Use first scenario as stacked base (optional choice)
    first_name = list(scenarios.keys())[0]
    first_path = scenarios[first_name]

    df_base, total_base, nonzero_base = preprocess_chartdata(first_path, column_map)

    # --- STACKED AREA (base scenario only) ---
    for col in nonzero_base.columns:
        fig.add_trace(go.Scatter(
            x=nonzero_base.index,
            y=df_base[col],
            mode='lines',
            stackgroup='one',
            name=f"{first_name} - {col}",
            line=dict(color=tech_colors.get(col, 'gray'))
        ))

    # --- TOTAL LINES FOR ALL SCENARIOS ---
    for name, path in scenarios.items():

        df, total, _ = preprocess_chartdata(path, column_map)

        fig.add_trace(go.Scatter(
            x=total.index,
            y=total,
            mode='lines',
            name=f"{name} Total",
            line=dict(width=3, dash='dot')
        ))

    # --- BAU LINE (from reference only) ---
    ref_total = preprocess_chartdata(
        scenarios["scen_base"], column_map
    )[1]

    bau_value_2020 = ref_total.loc[2025]
    bau_line = [bau_value_2020] * len(ref_total.index)

    fig.add_trace(go.Scatter(
        x=ref_total.index,
        y=bau_line,
        mode='lines',
        name='scen_base (2025 level)',
        line=dict(color='black', width=2, dash='dash')
    ))

    fig.update_layout(
        title='Scenario Comparison',
        xaxis_title='Year',
        yaxis_title='TWh',
        hovermode='x unified',
        template='plotly_white',
        height=600,
        width=1200
    )
    

    return fig


def scenario_costs(country):
    costs = [
    ("scen_base", f"results/scen_base/country_csvs/{country}_costs.csv"),
    ("scen_corrige", f"results/scen_corrige/country_csvs/{country}_costs.csv"),
    ("scen_suff", f"results/scen_suff/country_csvs/{country}_costs.csv"),]
    
    total_costs = {}
    for name, file_path in costs:
      # Read the CSV file
      df = pd.read_csv(file_path)
      df = df[['tech','2020', '2030', '2040', '2050']]
      df['Total'] = df[['2020','2030', '2040', '2050']].sum(axis=1)
      df = df[['tech', 'Total']]
      df['Total'] = df['Total'] / 4
      df = df.rename(columns={'Total': name})
      # Store the processed dataframe in the dictionary
      total_costs[name] = df
    
    combined_df = list(total_costs.values())[0]
    for df in list(total_costs.values())[1:]:
     combined_df = pd.merge(combined_df, df, on='tech', how='outer')
     combined_df = combined_df.fillna(0)
     combined_df = combined_df.set_index('tech')
    
    unit='Euros/year'
    if country == "EU":
     title_country = "6 Countries"
    else:
     title_country = country
    title=f'Average Costs Per Year Comparison For {title_country}'
    tech_colors = snakemake.params.plotting["tech_colors"]
    
    fig = go.Figure()
    df_transposed = combined_df.T

    for tech in df_transposed.columns:
      y = df_transposed[tech]
      color = tech_colors.get(tech, 'lightgrey')
      fig.add_trace(go.Bar(
        x=df_transposed.index,
        y=y.where(y > 0, 0),
        name=tech,
        marker_color=color
    ))
      fig.add_trace(go.Bar(
        x=df_transposed.index,
        y=y.where(y < 0, 0),
        name=tech,
        marker_color=color,
        showlegend=False
    ))
    layout_common = dict(
    title=title,
    barmode='relative',  # Changed from 'stack'
    yaxis=dict(title=unit, title_font=dict(size=15), tickfont=dict(size=15)),
    xaxis=dict(tickfont=dict(size=15)),
    legend=dict(font=dict(size=15)),
    hovermode='y'
)
    fig.update_layout(height=1000, width=1000,**layout_common)
    fig.update_layout(hovermode='y')

    return fig

def scenario_investment_costs(country):
    costs = [
    ("scen_base", f"results/scen_base/country_csvs/{country}_investment costs.csv"),
    ("scen_corrige", f"results/scen_corrige/country_csvs/{country}_investment costs.csv"),
    ("scen_suff", f"results/scen_suff/country_csvs/{country}_investment costs.csv"),]
    
    investment_costs = {}
    
    for name, file_path in costs:
      # Read the CSV file
      df = pd.read_csv(file_path)
      df = df[['tech','2020', '2030', '2040', '2050']]
      df['Total'] = df[['2020','2030', '2040', '2050']].sum(axis=1)
      df = df[['tech', 'Total']]
      df['Total'] = df['Total'] / 4
      df = df.rename(columns={'Total': name})
      # Store the processed dataframe in the dictionary
      investment_costs[name] = df
    
    combined_df = list(investment_costs.values())[0]
    for df in list(investment_costs.values())[1:]:
     combined_df = pd.merge(combined_df, df, on='tech', how='outer')
     combined_df = combined_df.fillna(0)
     combined_df = combined_df.set_index('tech')
    
    unit='Euros/year'
    if country == "EU":
     title_country = "6 Countries"
    else:
     title_country = country
    title=f'Average Investment Costs Per Year Comparison For {title_country}'
    tech_colors = snakemake.params.plotting["tech_colors"]
    
    fig = go.Figure()
    df_transposed = combined_df.T

    for tech in df_transposed.columns:
        fig.add_trace(go.Bar(x=df_transposed.index, y=df_transposed[tech], name=tech, marker_color=tech_colors.get(tech, 'lightgrey')))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', name='Euro reference value = 2020', marker=dict(color='rgba(0,0,0,0)')))
    # Configure layout and labels
    layout_common = dict(
    title=title,
    barmode='relative',  # Changed from 'stack'
    yaxis=dict(title=unit, title_font=dict(size=15), tickfont=dict(size=15)),
    xaxis=dict(tickfont=dict(size=15)),
    legend=dict(font=dict(size=15)),
    hovermode='y'
)
    fig.update_layout(height=1000, width=1000,**layout_common)
    fig.update_layout(hovermode='y')
    
    return fig

#%%
def scenario_capacities(country):
    capacities = [
    ("scen_base", f"results/scen_base/country_csvs/{country}_capacities.csv"),
    ("scen_corrige", f"results/scen_corrige/country_csvs/{country}_capacities.csv"),
    ("scen_suff", f"results/scen_suff/country_csvs/{country}_capacities.csv"),]
    
    groups = [
        ["solar"],
        ["onshore wind", "offshore wind"],
        ["power-to-heat"],
        ["power-to-gas"],
        ["transmission lines"],
        ["power-to-liquid"],
        ["CCGT"],
        ["CHP"],
    ]
    
    groupss = [
        ["solar"],
        ["onshore wind", "offshore wind"],
        ["power-to-heat"],
        ["power-to-gas"],
        ["transmission lines"],
        ["power-to-liquid"],
        ["CCGT"],
        ["nuclear"],
    ]

    value = groups if country != "EU" else groupss

    years = ["2025","2030", "2040", "2050"]
    unit = "[GW]"
    tech_colors = snakemake.params.plotting["tech_colors"]

    # --- Read scenario data ---
    scenario_data = {}
    for scenario, path in capacities:
        df = pd.read_csv(path)
        df.columns = df.columns.map(lambda x: '2025' if x == '2020' else x)
        df = df.set_index("tech")[years]
        scenario_data[scenario] = df

    # --- Create subplot grid ---
    fig = make_subplots(
        rows=len(value),
        cols = len(years),
        subplot_titles=years,
        shared_yaxes="rows",
        vertical_spacing=0.04,
        horizontal_spacing=0.04
    )

    # --- Plot ---
    for row_idx, tech_group in enumerate(value, start=1):
        for col_idx, year in enumerate(years, start=1):
            for scenario, df in scenario_data.items():
                for tech in tech_group:
                    if tech not in df.index:
                        continue

                    fig.add_trace(
                        go.Bar(
                            x=[scenario],
                            y=[df.loc[tech, year] / 1000],  # MW → GW
                            name=tech,
                            marker_color=tech_colors.get(tech, "grey"),
                            showlegend=(row_idx == 1)
                        ),
                        row=row_idx,
                        col=col_idx
                    )

        # Label each row (group name)
        fig.update_yaxes(
            title_text=", ".join(tech_group),
            row=row_idx,
            col=1
        )

    # --- Layout ---
    fig.update_layout(
        barmode="stack",
        height=250 * len(value),
        width=1600,
        title="Installed Capacities",
        legend_title="Technology"
    )
    fig.update_layout(showlegend=False)
    fig.add_annotation(
    text=unit,
    x=-0.07,
    y=0.5,
    xref="paper",
    yref="paper",
    showarrow=False,
    textangle=-90,
    font=dict(size=14)
)
    fig.update_layout(showlegend=False)
    fig.update_xaxes(tickangle=45)

    return fig

def storage_capacities(country):
    capacities = [
    ("scen_base", f"results/scen_base/country_csvs/{country}_storage_capacities.csv"),
    ("scen_corrige", f"results/scen_corrige/country_csvs/{country}_storage_capacities.csv"),
    ("scen_suff", f"results/scen_suff/country_csvs/{country}_storage_capacities.csv"),]
    groups = [
        ["Grid-scale battery"],
        ["Thermal Energy Storage"],
        ["Gas storage"]
    ]

    value = groups

    years = ["2025","2030", "2040", "2050"]
    unit = "[GWh]"
    tech_colors = snakemake.params.plotting["tech_colors"]

    # --- Read scenario data ---
    scenario_data = {}
    for scenario, path in capacities:
        df = pd.read_csv(path)
        df.columns = df.columns.map(lambda x: '2025' if x == '2020' else x)
        df = df.set_index("tech")[years]
        scenario_data[scenario] = df

    # --- Create subplot grid ---
    fig = make_subplots(
        rows=len(value),
        cols = len(years),
        subplot_titles=years,
        shared_yaxes="rows",
        vertical_spacing=0.04,
        horizontal_spacing=0.04
    )

    # --- Plot ---
    for row_idx, tech_group in enumerate(value, start=1):
        for col_idx, year in enumerate(years, start=1):
            for scenario, df in scenario_data.items():
                for tech in tech_group:
                    if tech not in df.index:
                        continue

                    fig.add_trace(
                        go.Bar(
                            x=[scenario],
                            y=[df.loc[tech, year] / 1000],  # MW → GW
                            name=tech,
                            marker_color=tech_colors.get(tech, "grey"),
                            showlegend=(row_idx == 1)
                        ),
                        row=row_idx,
                        col=col_idx
                    )

        # Label each row (group name)
        fig.update_yaxes(
            title_text=", ".join(tech_group),
            row=row_idx,
            col=1
        )

    # --- Layout ---
    fig.update_layout(
        barmode="stack",
        height=300 * len(value),
        width=1200,
        title="Installed Capacities",
        legend_title="Technology"
    )
    fig.update_layout(showlegend=False)
    fig.add_annotation(
    text=unit,
    x=-0.07,
    y=0.5,
    xref="paper",
    yref="paper",
    showarrow=False,
    textangle=-90,
    font=dict(size=14)
)
    fig.update_xaxes(tickangle=45)

    return fig

def carbon_capture_techs(country):

    # --- Scenario files ---
    scenarios = {
        "scen_base": f"results/scen_base/sepia/inputs{country}.xlsx",
        "scen_corrige": f"results/scen_corrige/sepia/inputs{country}.xlsx",
        "scen_suff": f"results/scen_suff/sepia/inputs{country}.xlsx",
    }

    rename_dict = {
        'emmprocessccst': 'CC',
        'emmdac': 'CC(DAC)',
        'emmindbeccs': 'CC',
        'emmbmchpcc': 'CC',
        'emmbiogasatcc': 'CC',
        'emmgasccx': 'CC',
        'emmseq': 'CCS',
        'emmfischer': 'CCU',
        'emmmet': 'CCU',
        'emmsaba': 'CCU',
        'emmsmrcc': 'CC',
        'emmbmsngccca': 'CC',
        'emmgaschpatmcc': 'CC',
        'emmewastestm': 'CC',
        'emmbmliqcc': 'CC',
    }

    color_palette = {
        'CC': '#9a0200',
        'CC(DAC)': '#ffbacd',
        'CCS': '#c14a09',
        'CCU': '#fd5956',
    }

    # --- Load and preprocess all scenarios ---
    carbon_dfs = {}
    for name, path in scenarios.items():
        df = pd.read_excel(path, sheet_name="Inputs_co2", index_col=2)

        # Remove unnecessary columns
        drop_cols = ['label', 'source'] + [col for col in df.columns if col != '2050']
        df.drop(columns=drop_cols, inplace=True, errors='ignore')

        # Rename indices
        df.rename(index=rename_dict, inplace=True)
        df = df[df.index.isin(rename_dict.values())]
        df = df.groupby(level=0).sum()

        # Rename column to scenario name
        df.rename(columns={'2050': name}, inplace=True)
        carbon_dfs[name] = df

    # --- Combine all scenarios ---
    carbon_combined = pd.concat(carbon_dfs.values(), axis=1)
    carbon_combined.fillna(0, inplace=True)
    carbon_combined = carbon_combined.round(1)

    # Reorder rows
    desired_order = ['CCU', 'CC', 'CC(DAC)', 'CCS']
    carbon_combined = carbon_combined.reindex(desired_order)

    # --- Plot ---
    num_pies = len(carbon_combined.columns)
    fig = make_subplots(
        rows=1, 
        cols=1 + num_pies,
        column_widths=[0.5] + [0.5/num_pies]*num_pies,
        specs=[[{"type": "bar"}]+[{"type": "pie"}]*num_pies],
        horizontal_spacing=0.01
    )

    # Bar for all scenarios together
    for category in carbon_combined.index:
        fig.add_trace(
            go.Bar(
                name=category,
                x=carbon_combined.columns,
                y=carbon_combined.loc[category],
                marker_color=color_palette[category],
                width=0.15
            ),
            row=1, col=1
        )

    # Pie charts per scenario
    for idx, column in enumerate(carbon_combined.columns, start=2):
        filtered_values = carbon_combined[column][carbon_combined[column] > 0]
        filtered_labels = filtered_values.index
        filtered_colors = [color_palette[cat] for cat in filtered_labels]

        fig.add_trace(
            go.Pie(
                labels=filtered_labels,
                values=filtered_values,
                marker=dict(colors=filtered_colors),
                name=column,
                textinfo="label+percent",
                hole=0.3,
                scalegroup='group1',
                showlegend=False,
            ),
            row=1, col=idx
        )

    # Layout
    fig.update_layout(
        yaxis_title="Mtons CO2 eq/year",
        plot_bgcolor='white',
        height=800, width=1400,
        title=f"Required carbon capture capacities for {country} in 2050",
        legend=dict(font=dict(size=15))
    )

    return fig

def energy_independence(country):
    with open(snakemake.input.shape) as f:
        europe_geojson = json.load(f)

    scenarios = {
        "scen_base": "results/scen_base/country_csvs",
        "scen_corrige": "results/scen_corrige/country_csvs",
        "scen_suff": "results/scen_suff/country_csvs"
    }

    country_names = [f["properties"]["name"] for f in europe_geojson["features"]]
    visible_countries = {country: 1}  
    z_vals = [visible_countries.get(name, 0) for name in country_names]

    # Carrier colors
    carrier_colors = {
        'Natural gas': '#f0833a',
        'Petroleum': '#c5c9c7',
        'Electricity': '#01889f',
        'Coal': '#9a0200',
        'Hydrogen': '#95d0fc',
        'Solid biomass': '#11875d',
        'Ammonia': '#fddc5c',
        'Methanol': '#82cbb2',
        'Uranium': '#ffbacd',
        'Local production': 'black',
        'Net imports': 'whitesmoke'
    }

    base_cols = {
        'imp_gaz_pe': 'Natural gas',
        'imp_pet_pe': 'Petroleum',
        'imp_elc_se': 'Electricity',
        'imp_cms_pe': 'Coal',
        'imp_hyd_se': 'Hydrogen',
        'imp_enc_pe': 'Solid biomass',
        'imp_amm_fe': 'Ammonia',
        'ura_pe_elc_se': 'Uranium',
        'imp_met_fe': 'Methanol'
    }

    # --- Load 2050 data ---
    data = {}
    for scen_name, folder in scenarios.items():
        imports = pd.read_csv(f"{folder}/total_imports_{country}.csv", index_col=0).clip(lower=0)
        local = pd.read_csv(f"{folder}/local_product_{country}.csv", index_col=0).clip(lower=0)

        imports.rename(columns={k: v for k, v in base_cols.items()}, inplace=True)
        year_2050 = 2050
        imports_2050 = imports.loc[year_2050] if year_2050 in imports.index else imports.iloc[-1]
        local_2050 = local.loc[year_2050] if year_2050 in local.index else local.iloc[-1]

        data[scen_name] = {
            "imports_2050": imports_2050,
            "local_2050": local_2050.sum()
        }

    num_scenarios = len(data)

    # --- Create subplots ---
    fig = make_subplots(
        rows=2, cols=num_scenarios + 1,
        specs=[[{"type": "choropleth", "rowspan": 2}] + [{"type": "domain"}]*num_scenarios,
               [None] + [{"type": "domain"}]*num_scenarios],
        column_widths=[0.3] + [0.7/num_scenarios]*num_scenarios,
        row_heights=[0.5, 0.5],
        horizontal_spacing=0.01,
        vertical_spacing=0.05
    )

    # --- Choropleth ---
    fig.add_trace(go.Choropleth(
        geojson=europe_geojson,
        locations=country_names,
        z=z_vals,
        featureidkey="properties.name",
        colorscale=[[0, "whitesmoke"], [1, "black"]],
        zmin=0,
        zmax=1,
        showscale=False,
        marker_line_color='gray'
    ), row=1, col=1)

    fig.update_geos(
        scope="europe",
        center=dict(lat=50.85, lon=4.35),
        projection_scale=5,
        showland=True,
        landcolor="whitesmoke",
        showcountries=True
    )

    # --- Add pies ---
    col_idx = 2
    for scen_name, scen_data in data.items():
        # Row 1: Imports by carrier
        imports_filtered = scen_data["imports_2050"][scen_data["imports_2050"] > 0]
        labels = imports_filtered.index
        values = imports_filtered.values
        colors = [carrier_colors[label] for label in labels]

        fig.add_trace(go.Pie(
            labels=labels,
            values=values,
            hole=0.5,
            name=f"{scen_name} imports 2050",
            scalegroup=f"group_imports_{scen_name}",
            marker=dict(colors=colors)
        ), row=1, col=col_idx)

        # Row 2: Net imports vs Local production
        fig.add_trace(go.Pie(
            labels=["Net imports", "Local production"],
            values=[imports_filtered.sum(), scen_data["local_2050"]],
            hole=0.5,
            name=f"{scen_name} total 2050",
            scalegroup=f"group_total_{scen_name}",
            marker=dict(colors=[carrier_colors["Net imports"], carrier_colors["Local production"]])
        ), row=2, col=col_idx)

        # --- Add scenario title above column ---
        fig.add_annotation(
            text=scen_name,
            x=(col_idx - 1) / (num_scenarios + 1) + 0.5/(num_scenarios + 1),
            y=1.05,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=15, color="black"),
            align="center"
        )

        col_idx += 1

    fig.update_layout(
        height=700, width=1600,
        title=f"{country} energy independence in 2050",
        legend=dict(font=dict(size=15))
    )

    return fig

    
def create_combined_scenario_chart_country(country, output_folder='results/scenario_results/'):
    # Create output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    # Create combined HTML
    combined_html = "<html><head><Scenario Results</title></head><body>"
    #load the html plot flags
    with open(snakemake.input.plots_html, 'r') as file:
     plots = yaml.safe_load(file)
    scenario_plots = plots.get("Scenario_plots", {})
    display_country = "6 Countries" if country == "EU" else country
    if scenario_plots["Cummulative Emissions"] == True:
     emm_chart = Cumulative_emissions_sector(country)
     combined_html += f"<div><h2>{display_country} - Cumulative Emissions</h2>{emm_chart.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
     
    if scenario_plots["Comparison Energy"] == True:
     comm_chart = spline_plot(country)
     combined_html += f"<div><h2>{display_country} - Energy Consumption Comparison</h2>{comm_chart.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
    # Create bar chart
    if scenario_plots["Annual Costs"] == True:
     bar_chart = scenario_costs(country)
     combined_html += f"<div><h2>{display_country} - Annual Costs</h2>{bar_chart.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
    
    if scenario_plots["Annual Investment Costs"] == True:
     bar_chart_investment = scenario_investment_costs(country)
     combined_html += f"<div><h2>{display_country} - Annual Investment Costs</h2>{bar_chart_investment.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
    
    # Create capacities chart
    if scenario_plots["Capacities"] == True:
     capacities_chart = scenario_capacities(country)
     combined_html += f"<div><h2>{display_country} - Capacities</h2>{capacities_chart.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
    
    # Create storage capacities chart
    if scenario_plots["Storage Capacities"] == True:
     storage_capacities_chart = storage_capacities(country)
     combined_html += f"<div><h2>{display_country} -  Storage Capacities</h2>{storage_capacities_chart.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
     
     if scenario_plots["CC Capacities"] == True:
      cc_capacities_chart = carbon_capture_techs(country)
      combined_html += f"<div><h2>{display_country} - Required Carbon Capture Capacities</h2>{cc_capacities_chart.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
     
     if country != "EU":
      if scenario_plots["Energy Independence"] == True:
       energy_ind_chart = energy_independence(country)
       combined_html += f"<div><h2>{country} - Energy Independence</h2>{energy_ind_chart.to_html(full_html=False, include_plotlyjs='cdn')}</div>"

    combined_html += "</body></html>"
    table_of_contents_content = ""
    main_content = ''
    # Create the content for the "Table of Contents" and "Main" sections
    if scenario_plots["Cummulative Emissions"] == True:
     table_of_contents_content += f"<a href='#{display_country} - Cumulative Emissions'>Cumulative Emissions</a><br>"
    if scenario_plots["Comparison Energy"] == True:
     table_of_contents_content += f"<a href='#{display_country} - Energy Consumption Comparison'>Energy Consumption Comparison</a><br>"
    if scenario_plots["Annual Costs"] == True:
     table_of_contents_content += f"<a href='#{display_country} - Annual Costs'>Annual Costs</a><br>"
    if scenario_plots["Annual Investment Costs"] == True:
     table_of_contents_content += f"<a href='#{display_country} - Annual Investment Costs'>Annual Investment Costs</a><br>"
    if scenario_plots["Capacities"] == True:
     table_of_contents_content += f"<a href='#{display_country} - Capacities'>Capacities</a><br>"
    if scenario_plots["Storage Capacities"] == True:
     table_of_contents_content += f"<a href='#{display_country} - Storage Capacities'>Storage Capacities</a><br>"
    if scenario_plots["CC Capacities"] == True:
     table_of_contents_content += f"<a href='#{display_country} - Required Carbon Capture Capacities'>Carbon Capture Capacities</a><br>"
    if country != "EU":
     if scenario_plots["Energy Independence"] == True:
      table_of_contents_content += f"<a href='#{country} - Energy Independence'>Energy Independence</a><br>"

    # Add more links for other plots
    if scenario_plots["Cummulative Emissions"] == True:
     main_content += f"<div id='{display_country} - Cumulative Emissions'><h2>{display_country} - Cumulative Emissions</h2>{emm_chart.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
    if scenario_plots["Comparison Energy"] == True:
     main_content += f"<div id='{display_country} - Energy Consumption Comparison'><h2>{display_country} - Energy Consumption Comparison</h2>{comm_chart.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
    if scenario_plots["Annual Costs"] == True:
     main_content += f"<div id='{display_country} - Annual Costs'><h2>{display_country} - Annual Costs</h2>{bar_chart.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
    if scenario_plots["Annual Investment Costs"] == True:
     main_content += f"<div id='{display_country} - Annual Investment Costs'><h2>{display_country} - Annual Investment Costs</h2>{bar_chart_investment.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
    if scenario_plots["Capacities"] == True:
     main_content += f"<div id='{display_country} - Capacities'><h2>{display_country} - Capacities</h2>{capacities_chart.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
    if scenario_plots["Storage Capacities"] == True:
     main_content += f"<div id='{display_country} - Storage Capacities'><h2>{display_country} - Storage Capacities</h2>{storage_capacities_chart.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
    if scenario_plots["CC Capacities"] == True:
     main_content += f"<div id='{display_country} - Required Carbon Capture Capacities'><h2>{display_country} - Required Carbon Capture Capacities</h2>{cc_capacities_chart.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
    if country != "EU":
     if scenario_plots["Energy Independence"] == True:
      main_content += f"<div id='{country} - Energy Independence'><h2>{country} - Energy Independence</h2>{energy_ind_chart.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
    
    template_path =  snakemake.input.template
    with open(template_path, "r") as template_file:
        template_content = template_file.read()
        template = Template(template_content)
        
    rendered_html = template.render(
    title=f"{country} - Combined Plots",
    country=country,
    TABLE_OF_CONTENTS=table_of_contents_content,
    MAIN=main_content,)
    
    combined_file_path = os.path.join(output_folder, f"{country}_combined_scenario_chart.html")
    with open(combined_file_path, "w") as combined_file:
     combined_file.write(rendered_html)
     




if __name__ == "__main__":
    if "snakemake" not in globals():
        #from _helpers import mock_snakemake

        #snakemake = mock_snakemake("prepare_scenarios")
        import pickle
        with open("snakemake_dump.pkl", "rb") as f:
            snakemake = pickle.load(f)

        
    total_country = 'EU'
    countries = ['BEBRU', 'BEVLG', 'BEWAL', 'DE', 'FR', 'NL', 'GB', 'LU'] 
    countries.append(total_country) 
    config = snakemake.config
    for country in countries:
        create_combined_scenario_chart_country(country)
        
    
 
