#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar  2 11:18:59 2026

@author: umair
"""

import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import fsolve
from scripts.nW_BE_demand_model_sub_functions import *

# Define the time horizon: [2019, 2025, 2030, 2035, 2040, 2045, 2050]
years = generate_target_years(2019)
# Define population size
population_dict = pd.Series([11_431_406, 11_816_102, 12_023_862, 12_186_730, 12_347_171, 12_490_658, 12_600_911], index=years)
# Define the number of households
households_dict = pd.Series([4_948_398, 5_199_667, 5_355_123, 5_489_927, 5_609_698, 5_702_818, 5_770_867], index=years)
# #### Conversion parameters
ktoe_to_GWh = 11.63
kgoe_to_kWh = 11.63
kgh2_to_kWh = 120/3.6
kgLNG_to_kWh= 45.1/3.6
J_to_kWh    = 1/3.6e+6
# #### Physical constants
cp_h2o  = 4184*J_to_kWh # kWh/kg/K
rho_h2o = 0.99906 # kg/l

def transport():
    # Inputs - Define Sufficiency Scenario Data (SUF)
    ref_PM_spe = 182.65651e+9/population_dict[2019] # [pkm/person]
    # Inputs - Define Sufficiency Scenario Data (SUF)
    pro_PM_spe = -0.10
    # Outputs - Sufficiency Scenario Data (SUF)
    SUF_data = {"PM intensity [pkm/person]": linear_growth(2019, ref_PM_spe, 
                                                       2050, ref_PM_spe*(1+pro_PM_spe), years)}
    df_SUF = pd.DataFrame(SUF_data, index=years)
    df_SUF["population [person]"] = df_SUF.index.map(population_dict)
    df_SUF["PM total [Gpkm]"] = df_SUF["PM intensity [pkm/person]"]*df_SUF["population [person]"]*1e-9

    # Inputs - Define Sufficiency Scenario Data (SUF)
    ref_FT_spe = 80.17566e+9/population_dict[2019] # [tkm/person]
    # Inputs - Define Sufficiency Scenario Data (SUF)
    pro_FT_spe = -0.10
    # Outputs - Sufficiency Scenario Data (SUF)
    df_SUF["FT intensity [tkm/person]"] = linear_growth(2019, ref_FT_spe, 
                                                    2050, ref_FT_spe*(1+pro_FT_spe), years)
    df_SUF["FT total [Gtkm]"] = df_SUF["FT intensity [tkm/person]"]*df_SUF["population [person]"]*1e-9

    # Inputs - Modal Repartition [Gpkm] for reference year (2019)
    ref_PM_mod_abs = {
    'pedestrian':           3.00000, # From Belgian Federal Public Service for Mobility and Transport
    'bicycle':              7.00000, # From Belgian Federal Public Service for Mobility and Transport
    'two-wheeler':          1.75208, # From JRC-IDEES
    'tram&metro':           1.47211, # From JRC-IDEES
    'bus&coach':           13.68139, # From JRC-IDEES
    'car':                107.44465, # From JRC-IDEES
    'train-conventional':  10.43600, # From JRC-IDEES
    'train-high speed':     1.56400, # From JRC-IDEES
    'plane-intra EU':      15.59146, # From JRC-IDEES
    'plane-extra EU':      20.71483, # From JRC-IDEES
    }
    ref_PM_abs = sum(ref_PM_mod_abs.values())
    if abs((ref_PM_abs-df_SUF["PM total [Gpkm]"][2019])/df_SUF["PM total [Gpkm]"][2019]*100) > 1e-5: 
     print("Entry values in 'ref_PM_mod_abs' are not correct!")
    # Outputs - Modal Shares [%] and Modal Repartition [pkm/person] for reference year (2019)
    ref_PM_mod_rel = {k: v/ref_PM_abs*100                            for k, v in ref_PM_mod_abs.items()} # [%]
    ref_PM_mod_spe = {k: v/df_SUF["population [person]"][2019]*1e+9 for k, v in ref_PM_mod_abs.items()} # [pkm/person]

    # Inputs - Define Sufficiency Scenario Data (SUF)
    pro_PM_spe_avi_lng = -0.40
    # Outputs - Sufficiency Scenario Data (SUF)
    trg_PM_mod_spe = {'plane-extra EU':   (1+pro_PM_spe_avi_lng)*ref_PM_mod_spe['plane-extra EU']} # [pkm/person]
    trg_PM_mod_abs = {'plane-extra EU':      trg_PM_mod_spe['plane-extra EU']*df_SUF["population [person]"][2050]*1e-9} # [Gpkm]
    trg_PM_mod_rel = {'plane-extra EU':      trg_PM_mod_spe['plane-extra EU']/df_SUF["PM intensity [pkm/person]"][2050]*100} # [%]

    # Calculation of reductions in mobility intensity
    dlt_PM_spe_avi_lng = pro_PM_spe_avi_lng*ref_PM_mod_spe['plane-extra EU'] # [pkm/person]
    dlt_PM_spe         = pro_PM_spe        *ref_PM_spe                       # [pkm/person]
    rem_dlt_PM_rel     = 1 - dlt_PM_spe_avi_lng/dlt_PM_spe                   # [-]
    rem_dlt_PM_abs     = rem_dlt_PM_rel        *dlt_PM_spe                   # [pkm/person]
    red_PM_rel      = (1+rem_dlt_PM_abs/(ref_PM_spe-ref_PM_mod_spe['plane-extra EU'])) # [-]
    trg_PM_mod_spe_ped     = red_PM_rel*ref_PM_mod_spe['pedestrian']         # [pkm/person]
    trg_PM_mod_spe_bic     = red_PM_rel*ref_PM_mod_spe['bicycle']            # [pkm/person]
    trg_PM_mod_spe_mot     = red_PM_rel*ref_PM_mod_spe['two-wheeler']        # [pkm/person]
    trg_PM_mod_spe_car     = red_PM_rel*ref_PM_mod_spe['car']                # [pkm/person]
    trg_PM_mod_spe_bus_cch = red_PM_rel*ref_PM_mod_spe['bus&coach']          # [pkm/person]
    trg_PM_mod_spe_trm_met = red_PM_rel*ref_PM_mod_spe['tram&metro']         # [pkm/person]
    trg_PM_mod_spe_trn_cnv = red_PM_rel*ref_PM_mod_spe['train-conventional'] # [pkm/person]
    trg_PM_mod_spe_trn_spd = red_PM_rel*ref_PM_mod_spe['train-high speed']   # [pkm/person]
    trg_PM_mod_spe_avi_srt = red_PM_rel*ref_PM_mod_spe['plane-intra EU']     # [pkm/person]
    sum_PM_gen = trg_PM_mod_spe_ped     + trg_PM_mod_spe_bic
    sum_PM_rod = trg_PM_mod_spe_mot     + trg_PM_mod_spe_car     + trg_PM_mod_spe_bus_cch
    sum_PM_ral = trg_PM_mod_spe_trm_met + trg_PM_mod_spe_trn_cnv + trg_PM_mod_spe_trn_spd
    sum_PM_avi = trg_PM_mod_spe_avi_srt
    sum_PM_tot = sum_PM_gen + sum_PM_rod + sum_PM_ral + sum_PM_avi
    if abs((sum_PM_tot + trg_PM_mod_spe['plane-extra EU']-df_SUF["PM intensity [pkm/person]"][2050])/df_SUF["PM intensity [pkm/person]"][2050]*100) > 1e-5: 
     print("There is an error in forecasting the 2050 mobility intensity!")
    # Inputs - Define Sufficiency Scenario Data (SUF)
    pro_PM_spe_avi_srt            = -0.50
    sft_PM_rel_avi_srt_to_trn_cnv = +0.25
    sft_PM_rel_avi_srt_to_trn_spd = +0.20
    sft_PM_rel_avi_srt_to_cch     = +0.05
    if abs(pro_PM_spe_avi_srt+sft_PM_rel_avi_srt_to_trn_cnv+sft_PM_rel_avi_srt_to_trn_spd+sft_PM_rel_avi_srt_to_cch) > 1e-15: 
     print("There is an error in the modal shift for the 2050 intra-Europe flights!")
    # Outputs - Sufficiency Scenario Data (SUF)
    trg_PM_mod_spe['plane-intra EU'] = (1+pro_PM_spe_avi_srt)*trg_PM_mod_spe_avi_srt # [pkm/person]
    trg_PM_mod_abs['plane-intra EU'] = trg_PM_mod_spe['plane-intra EU']*df_SUF["population [person]"][2050]*1e-9 # [Gpkm]
    trg_PM_mod_rel['plane-intra EU'] = trg_PM_mod_spe['plane-intra EU']/df_SUF["PM intensity [pkm/person]"][2050]*100 # [%]
    # Modal shit - Report to other modes
    sft_PM_abs_avi_srt_to_trn_cnv = sft_PM_rel_avi_srt_to_trn_cnv*trg_PM_mod_spe_avi_srt
    sft_PM_abs_avi_srt_to_trn_spd = sft_PM_rel_avi_srt_to_trn_spd*trg_PM_mod_spe_avi_srt
    sft_PM_abs_avi_srt_to_cch     = sft_PM_rel_avi_srt_to_cch    *trg_PM_mod_spe_avi_srt
    # Inputs - Define Sufficiency Scenario Data (SUF)
    pro_PM_spe_car            = -0.30
    sft_PM_rel_car_to_bus     = +0.10
    sft_PM_rel_car_to_trn_cnv = +0.08
    sft_PM_rel_car_to_byc     = +0.07
    sft_PM_rel_car_to_trm_met = +0.03
    sft_PM_rel_car_to_mot     = +0.01
    sft_PM_rel_car_to_ped     = +0.01
    # Outputs - Sufficiency Scenario Data (SUF)
    trg_PM_mod_spe['car'] = (1+pro_PM_spe_car)*trg_PM_mod_spe_car # [pkm/person]
    trg_PM_mod_abs['car'] = trg_PM_mod_spe['car']*df_SUF["population [person]"][2050]*1e-9 # [Gpkm]
    trg_PM_mod_rel['car'] = trg_PM_mod_spe['car']/df_SUF["PM intensity [pkm/person]"][2050]*100 # [%]
    # Modal shit - Report to other modes
    sft_PM_abs_car_to_bus     = sft_PM_rel_car_to_bus    *trg_PM_mod_spe_car
    sft_PM_abs_car_to_trn_cnv = sft_PM_rel_car_to_trn_cnv*trg_PM_mod_spe_car
    sft_PM_abs_car_to_bic     = sft_PM_rel_car_to_byc    *trg_PM_mod_spe_car
    sft_PM_abs_car_to_trm_met = sft_PM_rel_car_to_trm_met*trg_PM_mod_spe_car
    sft_PM_abs_car_to_mot     = sft_PM_rel_car_to_mot    *trg_PM_mod_spe_car
    sft_PM_abs_car_to_ped     = sft_PM_rel_car_to_ped    *trg_PM_mod_spe_car

    # Outputs - Sufficiency Scenario Data (SUF)
    trg_PM_mod_spe['train-conventional'] = trg_PM_mod_spe_trn_cnv+sft_PM_abs_avi_srt_to_trn_cnv+sft_PM_abs_car_to_trn_cnv # [pkm/person]
    trg_PM_mod_abs['train-conventional'] = trg_PM_mod_spe['train-conventional']*df_SUF["population [person]"][2050]*1e-9 # [Gpkm]
    trg_PM_mod_rel['train-conventional'] = trg_PM_mod_spe['train-conventional']/df_SUF["PM intensity [pkm/person]"][2050]*100 # [%]
    trg_PM_mod_spe['train-high speed']   = trg_PM_mod_spe_trn_spd+sft_PM_abs_avi_srt_to_trn_spd # [pkm/person]
    trg_PM_mod_abs['train-high speed']   = trg_PM_mod_spe['train-high speed']  *df_SUF["population [person]"][2050]*1e-9 # [Gpkm]
    trg_PM_mod_rel['train-high speed']   = trg_PM_mod_spe['train-high speed']  /df_SUF["PM intensity [pkm/person]"][2050]*100 # [%]

    # Outputs - Sufficiency Scenario Data (SUF)
    trg_PM_mod_spe['pedestrian'] = trg_PM_mod_spe_ped+sft_PM_abs_car_to_ped # [pkm/person]
    trg_PM_mod_abs['pedestrian'] = trg_PM_mod_spe['pedestrian']*df_SUF["population [person]"][2050]*1e-9 # [Gpkm]
    trg_PM_mod_rel['pedestrian'] = trg_PM_mod_spe['pedestrian']/df_SUF["PM intensity [pkm/person]"][2050]*100 # [%]
    trg_PM_mod_spe['bicycle']    = trg_PM_mod_spe_bic+sft_PM_abs_car_to_bic # [pkm/person]
    trg_PM_mod_abs['bicycle']    = trg_PM_mod_spe['bicycle']  *df_SUF["population [person]"][2050]*1e-9 # [Gpkm]
    trg_PM_mod_rel['bicycle']    = trg_PM_mod_spe['bicycle']  /df_SUF["PM intensity [pkm/person]"][2050]*100 # [%]

    # Outputs - Sufficiency Scenario Data (SUF)
    trg_PM_mod_spe['tram&metro'] = trg_PM_mod_spe_trm_met+sft_PM_abs_car_to_trm_met # [pkm/person]
    trg_PM_mod_abs['tram&metro'] = trg_PM_mod_spe['tram&metro']*df_SUF["population [person]"][2050]*1e-9 # [Gpkm]
    trg_PM_mod_rel['tram&metro'] = trg_PM_mod_spe['tram&metro']/df_SUF["PM intensity [pkm/person]"][2050]*100 # [%]

    # Outputs - Sufficiency Scenario Data (SUF)
    trg_PM_mod_spe['bus&coach'] = trg_PM_mod_spe_bus_cch+sft_PM_abs_avi_srt_to_cch+sft_PM_abs_car_to_bus # [pkm/person]
    trg_PM_mod_abs['bus&coach'] = trg_PM_mod_spe['bus&coach']*df_SUF["population [person]"][2050]*1e-9 # [Gpkm]
    trg_PM_mod_rel['bus&coach'] = trg_PM_mod_spe['bus&coach']/df_SUF["PM intensity [pkm/person]"][2050]*100 # [%]

    # Outputs - Sufficiency Scenario Data (SUF)
    trg_PM_mod_spe['two-wheeler'] = trg_PM_mod_spe_mot+sft_PM_abs_car_to_mot # [pkm/person]
    trg_PM_mod_abs['two-wheeler'] = trg_PM_mod_spe['two-wheeler']*df_SUF["population [person]"][2050]*1e-9 # [Gpkm]
    trg_PM_mod_rel['two-wheeler'] = trg_PM_mod_spe['two-wheeler']/df_SUF["PM intensity [pkm/person]"][2050]*100 # [%]

    # Processing - Modal Shares (in %)
    modes_PM = {
    'pedestrian':         linear_growth(2019,ref_PM_mod_rel['pedestrian'],
                                        2050,trg_PM_mod_rel['pedestrian'],        years),
    'bicycle':            linear_growth(2019,ref_PM_mod_rel['bicycle'],
                                        2050,trg_PM_mod_rel['bicycle'],           years),
    'two-wheeler':        linear_growth(2019,ref_PM_mod_rel['two-wheeler'],
                                        2050,trg_PM_mod_rel['two-wheeler'],       years),
    'tram&metro':         linear_growth(2019,ref_PM_mod_rel['tram&metro'],
                                        2050,trg_PM_mod_rel['tram&metro'],        years),
    'bus&coach':          linear_growth(2019,ref_PM_mod_rel['bus&coach'],
                                        2050,trg_PM_mod_rel['bus&coach'],         years),
    'car':                linear_growth(2019,ref_PM_mod_rel['car'],
                                        2050,trg_PM_mod_rel['car'],               years),
    'train-conventional': linear_growth(2019,ref_PM_mod_rel['train-conventional'],
                                        2050,trg_PM_mod_rel['train-conventional'],years),
    'train-high speed':   linear_growth(2019,ref_PM_mod_rel['train-high speed'],
                                        2050,trg_PM_mod_rel['train-high speed'],  years),
    'plane-intra EU':     linear_growth(2019,ref_PM_mod_rel['plane-intra EU'],
                                        2050,trg_PM_mod_rel['plane-intra EU'],    years),
    'plane-extra EU':     linear_growth(2019,ref_PM_mod_rel['plane-extra EU'],
                                        2050,trg_PM_mod_rel['plane-extra EU'],    years),
    }
    # Processing - Modal Shares DataFrame
    df_PM_MOD = pd.DataFrame(modes_PM, index=years)
    df_PM_MOD = df_PM_MOD.round(4).transpose()
    # Processing - Global DataFrame
    df_PM_GPKM = pd.DataFrame({year: df_SUF["PM total [Gpkm]"][year]*df_PM_MOD[year]*1e-2 for year in years}, index=df_PM_MOD.index).round(6)
    df_PM_PKMP = pd.DataFrame({year: df_PM_GPKM[year]*1e+9/population_dict[year]          for year in years}, index=df_PM_MOD.index).round(3)
    arrays_PM  =[np.repeat(df_PM_MOD.index, 3), ['% of total', 'pkm/person', 'Gpkm'] * len(df_PM_MOD)]
    mi_PM      = pd.MultiIndex.from_arrays(arrays_PM, names=['Mode', 'Unit'])
    data_PM_rows  = []
    for mode in df_PM_MOD.index:
      data_PM_rows.append(df_PM_MOD .loc[mode].values)  # modal percentages
      data_PM_rows.append(df_PM_PKMP.loc[mode].values)  # pkm per person
      data_PM_rows.append(df_PM_GPKM.loc[mode].values)  # Gpkm values
    data_PM = np.vstack(data_PM_rows)
    df_PM   = pd.DataFrame(data_PM, index=mi_PM, columns=years)

    # Inputs - Define Sufficiency Scenario Data (SUF)
    sta_PM_bic = 25 # [%]
    end_PM_bic = 80 # [%]
    mid_PM_bic = 2040
    # Outputs - Sufficiency Scenario Data (SUF)
    carriers_PM_bic = {
    'electrical':                 linear_with_middle_point(2019, sta_PM_bic, mid_PM_bic, end_PM_bic, 2050, end_PM_bic, years), # [%]
    'mechanical': [100-x for x in linear_with_middle_point(2019, sta_PM_bic, mid_PM_bic, end_PM_bic, 2050, end_PM_bic, years)] # [%]
    }
    df_PM_bic = pd.DataFrame(carriers_PM_bic, index=years).T.round(3)

    # Inputs - Define Sufficiency Scenario Data (SUF)
    sta_PM_mot = 100 # [%]
    end_PM_mot =  15 # [%]
    # Outputs - Sufficiency Scenario Data (SUF)
    carriers_PM_mot = {
    'liquid-gasoline':             linear_growth(2019, sta_PM_mot, 2050, end_PM_mot, years),  # [%]
    'electrical':  [100-x for x in linear_growth(2019, sta_PM_mot, 2050, end_PM_mot, years)], # [%]
    }
    df_PM_mot = pd.DataFrame(carriers_PM_mot, index=years).T.round(3)

    # Inputs - Define Sufficiency Scenario Data (SUF)
    sta_PM_trm_met = 100 # [%]
    end_PM_trm_met = 100 # [%]
    # Outputs - Sufficiency Scenario Data (SUF)
    carriers_PM_trm_met = {
    'electrical':  linear_growth(2019, sta_PM_trm_met, 2050, end_PM_trm_met, years), # [%]
    }
    df_PM_trm_met = pd.DataFrame(carriers_PM_trm_met, index=years).T.round(3)

    # Inputs - Define Sufficiency Scenario Data (SUF)
    sta_PM_bus_cch_lfd   = 99.27 # [%]
    end_PM_bus_cch_lfd   =  3.00 # [%]
    sta_PM_bus_cch_lfg   =  0.25 # [%]
    end_PM_bus_cch_lfg   =  0.00 # [%]
    sta_PM_bus_cch_h2    =  0.00 # [%]
    end_PM_bus_cch_h2    =  5.00 # [%]
    sta_PM_bus_cch_cng   =  0.09 # [%]
    end_PM_bus_cch_cng   =  2.00 # [%]
    slope_f_PM_bus_cch   =  0.9
    # Outputs - Sufficiency Scenario Data (SUF)
    carriers_bus = {
    'liquid-diesel':    s_curve_growth(2019, sta_PM_bus_cch_lfd, 2050, end_PM_bus_cch_lfd, years, slope_f_PM_bus_cch),  # [%]
    'liquid-gasoline':  s_curve_growth(2019, sta_PM_bus_cch_lfg, 2050, end_PM_bus_cch_lfg, years, slope_f_PM_bus_cch),  # [%]
    'hydrogen':         s_curve_growth(2019, sta_PM_bus_cch_h2,  2050, end_PM_bus_cch_h2,  years, slope_f_PM_bus_cch),  # [%]
    'gas-NG':           s_curve_growth(2019, sta_PM_bus_cch_cng, 2050, end_PM_bus_cch_cng, years, slope_f_PM_bus_cch),  # [%]
    'electrical':  [100-w-x-y-z for w, x, y, z in zip(*[s_curve_growth(2019, sta_PM_bus_cch_lfd, 2050, end_PM_bus_cch_lfd, years, slope_f_PM_bus_cch),
                                                        s_curve_growth(2019, sta_PM_bus_cch_lfg, 2050, end_PM_bus_cch_lfg, years, slope_f_PM_bus_cch),
                                                        s_curve_growth(2019, sta_PM_bus_cch_h2,  2050, end_PM_bus_cch_h2,  years, slope_f_PM_bus_cch),
                                                        s_curve_growth(2019, sta_PM_bus_cch_cng, 2050, end_PM_bus_cch_cng, years, slope_f_PM_bus_cch)])], # [%]
    }
    df_PM_bus_cch = pd.DataFrame(carriers_bus, index=years).T.round(3)

    # Inputs - Define Sufficiency Scenario Data (SUF)
    sta_PM_car_lfd   = 63.25 # [%]
    end_PM_car_lfd   =  1.50 # [%]
    mid_PM_car_lfd   =  2040
    sta_PM_car_lfg   = 35.00 # [%]
    end_PM_car_lfg   =  1.50 # [%]
    sta_PM_car_lpg   =  0.69 # [%]
    end_PM_car_lpg   =  0.00 # [%]
    sta_PM_car_phv   =  0.53 # [%]
    end_PM_car_phv   =  0.00 # [%]
    mid_PM_car_phv   =  6.00 # [%]
    sta_PM_car_cng   =  0.29 # [%]
    end_PM_car_cng   =  1.50 # [%]
    # Outputs - Sufficiency Scenario Data (SUF)
    carriers_PM_car = {
    'liquid-diesel':                 linear_with_middle_point(2019, sta_PM_car_lfd, mid_PM_car_lfd, end_PM_car_lfd, 2050, end_PM_car_lfd,                years),    # [%]
    'liquid-gasoline':  [x-y for x, y in zip(*[s_curve_growth(2019, sta_PM_car_lfd +sta_PM_car_lfg,                 2050, end_PM_car_lfd+end_PM_car_lfg, years,0.8),
                                     linear_with_middle_point(2019, sta_PM_car_lfd, mid_PM_car_lfd, end_PM_car_lfd, 2050, end_PM_car_lfd,                years)])], # [%]
    'gas-LPG':                                  linear_growth(2019, sta_PM_car_lpg,                                 2050, end_PM_car_lpg,                years),    # [%]
    'gas-NG':                                   linear_growth(2019, sta_PM_car_cng,                                 2050, end_PM_car_cng,                years),    # [%]
    'hybrid-plug-in':              b_curve_with_control_value(2019, sta_PM_car_phv, 2030, mid_PM_car_phv,           2050, end_PM_car_phv,                years,1.5),# [%]
    'electrical':  [100-w-x-y-z for w, x, y, z in zip(*[s_curve_growth(2019, sta_PM_car_lfd+sta_PM_car_lfg,         2050, end_PM_car_lfd+end_PM_car_lfg, years,slope_f_PM_bus_cch),
                                                         linear_growth(2019, sta_PM_car_lpg,                        2050, end_PM_car_lpg,                years),
                                                         linear_growth(2019, sta_PM_car_cng,                        2050, end_PM_car_cng,                years),
                                            b_curve_with_control_value(2019, sta_PM_car_phv, 2030, mid_PM_car_phv,  2050, end_PM_car_phv,                years,1.5)])], # [%]
    }
    df_PM_car = pd.DataFrame(carriers_PM_car, index=years).T.round(3)

    # Inputs - Define Sufficiency Scenario Data (SUF)
    sta_PM_trn_cnv = 4.39 # [%]
    end_PM_trn_cnv = 0.00 # [%]
    mid_PM_trn_cnv = 2035 # [%]
    # Outputs - Sufficiency Scenario Data (SUF)
    carriers_PM_trn_cnv = {
    'liquid-diesel':               linear_with_middle_point(2019, sta_PM_trn_cnv, mid_PM_trn_cnv, end_PM_trn_cnv, 2050, end_PM_trn_cnv, years),  # [%]
    'electrical':  [100-x for x in linear_with_middle_point(2019, sta_PM_trn_cnv, mid_PM_trn_cnv, end_PM_trn_cnv, 2050, end_PM_trn_cnv, years)], # [%]
    }
    carriers_PM_trn_spd = {
    'electrical':  linear_growth(2019, 100, 2050, 100, years), # [%]
    }
    df_PM_trn_cnv = pd.DataFrame(carriers_PM_trn_cnv, index=years).T.round(3)
    df_PM_trn_spd = pd.DataFrame(carriers_PM_trn_spd, index=years).T.round(3)

    # Inputs - Define Sufficiency Scenario Data (SUF)
    sta_PM_avi_srt  = 0 # [%]
    end_PM_avi_srt  = 5 # [%]
    mid_PM_avi_srt  = 2045
    # Outputs - Sufficiency Scenario Data (SUF)
    carriers_PM_avi_srt = {
    'hydrogen':                         linear_with_middle_point(2019, sta_PM_avi_srt, mid_PM_avi_srt, sta_PM_avi_srt, 2050, end_PM_avi_srt, years),  # [%]
    'liquid-kerosene':  [100-x for x in linear_with_middle_point(2019, sta_PM_avi_srt, mid_PM_avi_srt, sta_PM_avi_srt, 2050, end_PM_avi_srt, years)], # [%]
    }
    carriers_PM_avi_lng = {
    'liquid-kerosene':  linear_growth(2019, 100, 2050, 100, years), # [%]
    }
    df_PM_avi_srt = pd.DataFrame(carriers_PM_avi_srt, index=years).T.round(3)
    df_PM_avi_lng = pd.DataFrame(carriers_PM_avi_lng, index=years).T.round(3)

    # Processing - Carriers Shares (in %)
    df_PM_ped = pd.DataFrame({'human': [100] * len(years)}, index=years).T
    df_PM_carriers = {
    'pedestrian':         df_PM_ped,
    'bicycle':            df_PM_bic,
    'two-wheeler':        df_PM_mot,
    'tram&metro':         df_PM_trm_met,
    'bus&coach':          df_PM_bus_cch,
    'car':                df_PM_car,
    'train-conventional': df_PM_trn_cnv,
    'train-high speed':   df_PM_trn_spd,
    'plane-intra EU':     df_PM_avi_srt,
    'plane-extra EU':     df_PM_avi_lng,
    }
    rows = []
    for mode, df in df_PM_carriers.items():
      temp = df.copy()
      temp['Mode'] = mode
      temp['Powertrain'] = temp.index
      temp = temp.reset_index(drop=True)
      rows.append(temp)
    df_PM_carrier = pd.concat(rows, ignore_index=True)

    # ===== Bicycle =====
    # -> Projections of efficiency and occupancy
    cons_fuel_PM_bic = pd.DataFrame({
    'electrical':  linear_growth(2019, 1.00/100, 2050, 1.00/100, years),  # [kWh/km] -> sta = https://ecoquery.ecoinvent.org/3.11/cutoff/dataset/7742/documentation, end = nW-BE
    'mechanical':  linear_growth(2019, 0.00/100, 2050, 0.00/100, years),  # [kWh/km] -> sta = nW-BE
    }, index=years).T
    occupancy_PM_bic = pd.DataFrame({
    'electrical':  linear_growth(2019, 1,        2050, 1,        years),  # [p] -> sta = nW-BE, end = nW-BE
    'mechanical':  linear_growth(2019, 1,        2050, 1,        years),  # [p] -> sta = nW-BE, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_PM_bic_TWh = df_PM_carrier[df_PM_carrier['Mode'] == 'bicycle'].copy()
    df_PM_bic_TWh[years] *= df_PM_GPKM.loc['bicycle', years].values/100 # Gpkm
    df_PM_bic_TWh = df_PM_bic_TWh.set_index('Powertrain') # Gpkm
    df_PM_bic_TWh[years] *= cons_fuel_PM_bic[years]/occupancy_PM_bic[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_PM_bic_TWh)
    df_PM_bic_TWh.loc[new_index, years] = df_PM_bic_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_PM_bic_TWh.columns: df_PM_bic_TWh = df_PM_bic_TWh.reset_index()
    df_PM_bic_TWh = df_PM_bic_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_PM_bic_TWh.index[-1]
    df_PM_bic_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_PM_bic_TWh.loc[last_row_index, 'Mode'] = 'bicycle'
    df_PM_bic_TWh = df_PM_bic_TWh[['Mode','Powertrain'] + years]
    df_PM_bic_TWh = df_PM_bic_TWh.round(3)

    # ===== Two-wheeler =====
    # -> Settings
    redu_fuel_PM_mot = 0.95
    # -> Projections of efficiency and occupancy
    cons_fuel_PM_mot = pd.DataFrame({
    'liquid-gasoline': linear_growth(2019, 3.52/100*kgoe_to_kWh, 2050, 3.52/100*kgoe_to_kWh*redu_fuel_PM_mot, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    'electrical':      linear_growth(2019, 6.00/100,             2050, 6.00/100,                            years),  # [kWh/km] -> sta = 10.1088/1757-899X/1306/1/012032, end = nW-BE
    }, index=years).T
    occupancy_PM_mot = pd.DataFrame({
    'liquid-gasoline': linear_growth(2019, 1.151, 2050, 1.151, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    'electrical':      linear_growth(2019, 1.151, 2050, 1.151, years),  # [p] -> sta = nW-BE, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_PM_mot_TWh = df_PM_carrier[df_PM_carrier['Mode'] == 'two-wheeler'].copy()
    df_PM_mot_TWh[years] *= df_PM_GPKM.loc['two-wheeler', years].values/100 # Gpkm
    df_PM_mot_TWh = df_PM_mot_TWh.set_index('Powertrain') # Gpkm
    df_PM_mot_TWh[years] *= cons_fuel_PM_mot[years]/occupancy_PM_mot[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_PM_mot_TWh)
    df_PM_mot_TWh.loc[new_index, years] = df_PM_mot_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_PM_mot_TWh.columns: df_PM_mot_TWh = df_PM_mot_TWh.reset_index()
    df_PM_mot_TWh = df_PM_mot_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_PM_mot_TWh.index[-1]
    df_PM_mot_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_PM_mot_TWh.loc[last_row_index, 'Mode'] = 'two-wheeler'
    df_PM_mot_TWh = df_PM_mot_TWh[['Mode','Powertrain'] + years]
    df_PM_mot_TWh = df_PM_mot_TWh.round(3)

    # ===== Tram and metro =====
    # -> Settings
    redu_fuel_PM_trm_met = 0.95
    occu_trgt_PM_trm_met = 1.20
    # -> Projections of efficiency and occupancy
    cons_fuel_PM_trm_met = pd.DataFrame({
    'electrical':      linear_growth(2019, 39.141/100*kgoe_to_kWh, 2050, 39.141/100*kgoe_to_kWh*redu_fuel_PM_trm_met, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    occupancy_PM_trm_met = pd.DataFrame({
    'electrical':      linear_growth(2019, 81.938,                 2050,                 81.938*occu_trgt_PM_trm_met, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_PM_trm_met_TWh = df_PM_carrier[df_PM_carrier['Mode'] == 'tram&metro'].copy()
    df_PM_trm_met_TWh[years] *= df_PM_GPKM.loc['tram&metro', years].values/100 # Gpkm
    df_PM_trm_met_TWh = df_PM_trm_met_TWh.set_index('Powertrain') # Gpkm
    df_PM_trm_met_TWh[years] *= cons_fuel_PM_trm_met[years]/occupancy_PM_trm_met[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_PM_trm_met_TWh)
    df_PM_trm_met_TWh.loc[new_index, years] = df_PM_trm_met_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_PM_trm_met_TWh.columns: df_PM_trm_met_TWh = df_PM_trm_met_TWh.reset_index()
    df_PM_trm_met_TWh = df_PM_trm_met_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_PM_trm_met_TWh.index[-1]
    df_PM_trm_met_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_PM_trm_met_TWh.loc[last_row_index, 'Mode'] = 'tram&metro'
    df_PM_trm_met_TWh = df_PM_trm_met_TWh[['Mode','Powertrain'] + years]
    df_PM_trm_met_TWh = df_PM_trm_met_TWh.round(3)

    # ===== Bus and coach =====
    # -> Settings
    redu_fuel_PM_bus_cch = 0.95
    occu_trgt_PM_bus_cch = 1.20
    # -> Projections of efficiency and occupancy
    cons_fuel_PM_bus_cch = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019, 59.773/100*kgoe_to_kWh, 2050, 59.773/100*kgoe_to_kWh*redu_fuel_PM_bus_cch, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    'liquid-gasoline': linear_growth(2019, 18.065/100*kgoe_to_kWh, 2050, 18.065/100*kgoe_to_kWh*redu_fuel_PM_bus_cch, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    'hydrogen':        linear_growth(2019,  8.000/100*kgh2_to_kWh, 2050,  8.000/100*kgh2_to_kWh*redu_fuel_PM_bus_cch, years),  # [kWh/km] -> sta = https://doi.org/10.1016/j.ijhydene.2024.11.460, end = nW-BE
    'gas-NG':          linear_growth(2019, 64.939/100*kgoe_to_kWh, 2050, 64.939/100*kgoe_to_kWh*redu_fuel_PM_bus_cch, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
   #'electrical':      linear_growth(2019, 26.331/100*kgoe_to_kWh, 2050, 26.331/100*kgoe_to_kWh*redu_fuel_PM_bus_cch, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    'electrical':      linear_growth(2019,  2.0,                   2050,  2.0                  *redu_fuel_PM_bus_cch, years),  # [kWh/km] -> sta = https://doi.org/10.1016/j.treng.2023.100223, end = nW-BE
    }, index=years).T
    # Solaris Urbino 18 Hydrogen (city bus): 8.53kg/100km (51.2kg/600km, total tanks are 2.142m³​, 51.2kg at 350 bar and 15°C)
    # Irizar i6S Efficient Hydrogen (coach):  NA kg/100km (NA kg/1000km)
    # Daimler-Setra H2 Coach (coach):        5.75kg/100km (46.0kg/800km, total tanks are m³​, 46.0kg at  bar and °C)
    occupancy_PM_bus_cch = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019, 21.845, 2050, 21.845*occu_trgt_PM_bus_cch, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    'liquid-gasoline': linear_growth(2019,  8.369, 2050,  8.369*occu_trgt_PM_bus_cch, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    'hydrogen':        linear_growth(2019, 21.845, 2050, 21.845*occu_trgt_PM_bus_cch, years),  # [p] -> sta = nW-BE,     end = nW-BE
    'gas-NG':          linear_growth(2019, 21.845, 2050, 21.845*occu_trgt_PM_bus_cch, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    'electrical':      linear_growth(2019, 21.845, 2050, 21.845*occu_trgt_PM_bus_cch, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_PM_bus_cch_TWh = df_PM_carrier[df_PM_carrier['Mode'] == 'bus&coach'].copy()
    df_PM_bus_cch_TWh[years] *= df_PM_GPKM.loc['bus&coach', years].values/100 # Gpkm
    df_PM_bus_cch_TWh = df_PM_bus_cch_TWh.set_index('Powertrain') # Gpkm
    df_PM_bus_cch_TWh[years] *= cons_fuel_PM_bus_cch[years]/occupancy_PM_bus_cch[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_PM_bus_cch_TWh)
    df_PM_bus_cch_TWh.loc[new_index, years] = df_PM_bus_cch_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_PM_bus_cch_TWh.columns: df_PM_bus_cch_TWh = df_PM_bus_cch_TWh.reset_index()
    df_PM_bus_cch_TWh = df_PM_bus_cch_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_PM_bus_cch_TWh.index[-1]
    df_PM_bus_cch_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_PM_bus_cch_TWh.loc[last_row_index, 'Mode'] = 'bus&coach'
    df_PM_bus_cch_TWh = df_PM_bus_cch_TWh[['Mode','Powertrain'] + years]
    df_PM_bus_cch_TWh = df_PM_bus_cch_TWh.round(3)

    # ===== Passenger Car =====
    # -> Settings
    share_elec_plug_in = 0.50
    redu_fuel_PM_car = 0.75
    occu_trgt_PM_car = 2.0
    # -> Projections of efficiency and occupancy
    cons_fuel_PM_car = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019, 5.523/100*kgoe_to_kWh, 2050, 5.523/100*kgoe_to_kWh*redu_fuel_PM_car, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    'liquid-gasoline': linear_growth(2019, 5.798/100*kgoe_to_kWh, 2050, 5.798/100*kgoe_to_kWh*redu_fuel_PM_car, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    'gas-LPG':         linear_growth(2019, 7.477/100*kgoe_to_kWh, 2050, 7.477/100*kgoe_to_kWh*redu_fuel_PM_car, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    'gas-NG':          linear_growth(2019, 9.107/100*kgoe_to_kWh, 2050, 9.107/100*kgoe_to_kWh*redu_fuel_PM_car, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    'hybrid-plug-in':  linear_growth(2019, 3.735/100*kgoe_to_kWh, 2050, 3.735/100*kgoe_to_kWh*redu_fuel_PM_car, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    'electrical':      linear_growth(2019, 1.818/100*kgoe_to_kWh, 2050, 1.818/100*kgoe_to_kWh*redu_fuel_PM_car, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    occupancy_PM_car = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019, 1.242, 2050, occu_trgt_PM_car, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    'liquid-gasoline': linear_growth(2019, 1.188, 2050, occu_trgt_PM_car, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    'gas-LPG':         linear_growth(2019, 1.184, 2050, occu_trgt_PM_car, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    'gas-NG':          linear_growth(2019, 1.184, 2050, occu_trgt_PM_car, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    'hybrid-plug-in':  linear_growth(2019, 1.194, 2050, occu_trgt_PM_car, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    'electrical':      linear_growth(2019, 1.099, 2050, occu_trgt_PM_car, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_PM_car_TWh = df_PM_carrier[df_PM_carrier['Mode'] == 'car'].copy()
    df_PM_car_TWh[years] *= df_PM_GPKM.loc['car', years].values/100 # Gpkm
    df_PM_car_TWh = df_PM_car_TWh.set_index('Powertrain') # Gpkm
    df_PM_car_TWh[years] *= cons_fuel_PM_car[years]/occupancy_PM_car[years] # TWh
    # -> Disaggregate hybrid plug-in
    df_PM_car_TWh.loc['electrical',      years] += df_PM_car_TWh.loc['hybrid-plug-in', years] *    share_elec_plug_in
    df_PM_car_TWh.loc['liquid-gasoline', years] += df_PM_car_TWh.loc['hybrid-plug-in', years] * (1-share_elec_plug_in)
    df_PM_car_TWh = df_PM_car_TWh.drop('hybrid-plug-in')
    # -> Make total for sanity check
    new_index = len(df_PM_car_TWh)
    df_PM_car_TWh.loc[new_index, years] = df_PM_car_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_PM_car_TWh.columns: df_PM_car_TWh = df_PM_car_TWh.reset_index()
    df_PM_car_TWh = df_PM_car_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_PM_car_TWh.index[-1]
    df_PM_car_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_PM_car_TWh.loc[last_row_index, 'Mode'] = 'car'
    df_PM_car_TWh = df_PM_car_TWh[['Mode','Powertrain'] + years]
    df_PM_car_TWh = df_PM_car_TWh.round(3)

    # ===== Train (conventional) =====
    # -> Settings
    redu_fuel_PM_trn_cnv = 0.90
    occu_trgt_PM_trn_cnv = 1.20
    # -> Projections of efficiency and occupancy
    cons_fuel_PM_trn_cnv = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019, 201.155/100*kgoe_to_kWh, 2050, 201.155/100*kgoe_to_kWh,                     years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    'electrical':      linear_growth(2019, 115.233/100*kgoe_to_kWh, 2050, 115.233/100*kgoe_to_kWh*redu_fuel_PM_trn_cnv, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    occupancy_PM_trn_cnv = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019,  82.898,                 2050,                  82.898*occu_trgt_PM_trn_cnv, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    'electrical':      linear_growth(2019, 131.549,                 2050,                 131.549*occu_trgt_PM_trn_cnv, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_PM_trn_cnv_TWh = df_PM_carrier[df_PM_carrier['Mode'] == 'train-conventional'].copy()
    df_PM_trn_cnv_TWh[years] *= df_PM_GPKM.loc['train-conventional', years].values/100 # Gpkm
    df_PM_trn_cnv_TWh = df_PM_trn_cnv_TWh.set_index('Powertrain') # Gpkm
    df_PM_trn_cnv_TWh[years] *= cons_fuel_PM_trn_cnv[years]/occupancy_PM_trn_cnv[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_PM_trn_cnv_TWh)
    df_PM_trn_cnv_TWh.loc[new_index, years] = df_PM_trn_cnv_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_PM_trn_cnv_TWh.columns: df_PM_trn_cnv_TWh = df_PM_trn_cnv_TWh.reset_index()
    df_PM_trn_cnv_TWh = df_PM_trn_cnv_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_PM_trn_cnv_TWh.index[-1]
    df_PM_trn_cnv_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_PM_trn_cnv_TWh.loc[last_row_index, 'Mode'] = 'train-conventional'
    df_PM_trn_cnv_TWh = df_PM_trn_cnv_TWh[['Mode','Powertrain'] + years]
    df_PM_trn_cnv_TWh = df_PM_trn_cnv_TWh.round(3)

    # ===== Train (high speed) =====
    # -> Settings
    redu_fuel_PM_trn_spd = 0.90
    occu_trgt_PM_trn_spd = 1.05
    # -> Projections of efficiency and occupancy
    cons_fuel_PM_trn_spd = pd.DataFrame({
    'electrical':      linear_growth(2019, 213.694/100*kgoe_to_kWh, 2050, 213.694/100*kgoe_to_kWh*redu_fuel_PM_trn_spd, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    occupancy_PM_trn_spd = pd.DataFrame({
    'electrical':      linear_growth(2019, 302.477,                 2050,                 302.477*occu_trgt_PM_trn_spd, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_PM_trn_spd_TWh = df_PM_carrier[df_PM_carrier['Mode'] == 'train-high speed'].copy()
    df_PM_trn_spd_TWh[years] *= df_PM_GPKM.loc['train-high speed', years].values/100 # Gpkm
    df_PM_trn_spd_TWh = df_PM_trn_spd_TWh.set_index('Powertrain') # Gpkm
    df_PM_trn_spd_TWh[years] *= cons_fuel_PM_trn_spd[years]/occupancy_PM_trn_spd[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_PM_trn_spd_TWh)
    df_PM_trn_spd_TWh.loc[new_index, years] = df_PM_trn_spd_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_PM_trn_spd_TWh.columns: df_PM_trn_spd_TWh = df_PM_trn_spd_TWh.reset_index()
    df_PM_trn_spd_TWh = df_PM_trn_spd_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_PM_trn_spd_TWh.index[-1]
    df_PM_trn_spd_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_PM_trn_spd_TWh.loc[last_row_index, 'Mode'] = 'train-high speed'
    df_PM_trn_spd_TWh = df_PM_trn_spd_TWh[['Mode','Powertrain'] + years]
    df_PM_trn_spd_TWh = df_PM_trn_spd_TWh.round(3)

    # ===== Aviation (intra EU) =====
    # -> Settings
    redu_fuel_PM_avi_intra = 1.05 # + 9.4% from 2000 to 2023 (from 578.8 kgoe/100km to 633.0 kgoe/100km)
    occu_trgt_PM_avi_intra = 1.25 # +49.5% from 2000 to 2023 (from 87.5p to 130.8p)
    # -> Projections of efficiency and occupancy
    cons_fuel_PM_avi_intra = pd.DataFrame({
    'hydrogen':        linear_growth(2019, 130.000/100*kgh2_to_kWh, 2050, 130.000/100*kgh2_to_kWh,                       years),  # [kWh/km] -> sta = Airbus Zero-E, end = nW-BE
    'liquid-kerosene': linear_growth(2019, 593.771/100*kgoe_to_kWh, 2050, 593.771/100*kgoe_to_kWh*redu_fuel_PM_avi_intra, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    occupancy_PM_avi_intra = pd.DataFrame({
    'hydrogen':        linear_growth(2019, 100.000,                 2050,                 100.000,                       years),  # [p] -> sta = Airbus Zero-E, end = nW-BE
    'liquid-kerosene': linear_growth(2019, 121.927,                 2050,                 121.927*occu_trgt_PM_avi_intra, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_PM_avi_srt_TWh = df_PM_carrier[df_PM_carrier['Mode'] == 'plane-intra EU'].copy()
    df_PM_avi_srt_TWh[years] *= df_PM_GPKM.loc['plane-intra EU', years].values/100 # Gpkm
    df_PM_avi_srt_TWh = df_PM_avi_srt_TWh.set_index('Powertrain') # Gpkm
    df_PM_avi_srt_TWh[years] *= cons_fuel_PM_avi_intra[years]/occupancy_PM_avi_intra[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_PM_avi_srt_TWh)
    df_PM_avi_srt_TWh.loc[new_index, years] = df_PM_avi_srt_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_PM_avi_srt_TWh.columns: df_PM_avi_srt_TWh = df_PM_avi_srt_TWh.reset_index()
    df_PM_avi_srt_TWh = df_PM_avi_srt_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_PM_avi_srt_TWh.index[-1]
    df_PM_avi_srt_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_PM_avi_srt_TWh.loc[last_row_index, 'Mode'] = 'plane-intra EU'
    df_PM_avi_srt_TWh = df_PM_avi_srt_TWh[['Mode','Powertrain'] + years]
    df_PM_avi_srt_TWh = df_PM_avi_srt_TWh.round(3)

    # ===== Aviation (extra EU) =====
    # -> Settings
    redu_fuel_PM_avi_extra = 0.84 # -32.8% from 2000 to 2023 (from 937.0 kgoe/100km to 629.5 kgoe/100km)
    occu_trgt_PM_avi_extra = 1.17 # +33.7% from 2000 to 2023 (from 154.0p to 205.5p)
    # -> Projections of efficiency and occupancy
    cons_fuel_PM_avi_extra = pd.DataFrame({
    'liquid-kerosene': linear_growth(2019, 578.489/100*kgoe_to_kWh, 2050, 578.489/100*kgoe_to_kWh*redu_fuel_PM_avi_extra, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    occupancy_PM_avi_extra = pd.DataFrame({
    'liquid-kerosene': linear_growth(2019, 187.817,                 2050,                 187.817*occu_trgt_PM_avi_extra, years),  # [p] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_PM_avi_lng_TWh = df_PM_carrier[df_PM_carrier['Mode'] == 'plane-extra EU'].copy()
    df_PM_avi_lng_TWh[years] *= df_PM_GPKM.loc['plane-extra EU', years].values/100 # Gpkm
    df_PM_avi_lng_TWh = df_PM_avi_lng_TWh.set_index('Powertrain') # Gpkm
    df_PM_avi_lng_TWh[years] *= cons_fuel_PM_avi_extra[years]/occupancy_PM_avi_extra[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_PM_avi_lng_TWh)
    df_PM_avi_lng_TWh.loc[new_index, years] = df_PM_avi_lng_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_PM_avi_lng_TWh.columns: df_PM_avi_lng_TWh = df_PM_avi_lng_TWh.reset_index()
    df_PM_avi_lng_TWh = df_PM_avi_lng_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_PM_avi_lng_TWh.index[-1]
    df_PM_avi_lng_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_PM_avi_lng_TWh.loc[last_row_index, 'Mode'] = 'plane-extra EU'
    df_PM_avi_lng_TWh = df_PM_avi_lng_TWh[['Mode','Powertrain'] + years]
    df_PM_avi_lng_TWh = df_PM_avi_lng_TWh.round(3)

    df_PM_TWh_lst = [df_PM_bic_TWh, 
                 df_PM_mot_TWh, 
                 df_PM_trm_met_TWh, 
                 df_PM_bus_cch_TWh, 
                 df_PM_car_TWh, 
                 df_PM_trn_cnv_TWh, 
                 df_PM_trn_spd_TWh, 
                 df_PM_avi_srt_TWh, 
                 df_PM_avi_lng_TWh
    ]
    df_PM_TWh_all = pd.concat(df_PM_TWh_lst, ignore_index=True)
    df_PM_TWh_flt = df_PM_TWh_all[~df_PM_TWh_all['Powertrain'].isin(['TOTAL', 'mechanical'])].copy()
    df_PM_TWh_agr = df_PM_TWh_flt.groupby('Powertrain').sum(numeric_only=True)
    custom_order = [
    'electrical', 
    'liquid-gasoline', 
    'liquid-diesel', 
    'liquid-kerosene', 
    'gas-NG', 
    'gas-LPG', 
    'hydrogen'
    ]
    df_PM_TWh_agr = df_PM_TWh_agr.reindex(custom_order)

    # Inputs - Modal Repartition [Gtkm] for reference year (2019)
    ref_FT_mod_abs = {
    'truck-light commercial':  1.09462, # From JRC-IDEES
    'truck-heavy duty':       52.43700, # From JRC-IDEES
    'train':                  14.70000, # From JRC-IDEES
    'plane-intra EU':          0.27957, # From JRC-IDEES
    'plane-extra EU':          3.70473, # From JRC-IDEES
    'navigation-coastal':      0.19274, # From JRC-IDEES
    'navigation-inland':       7.76700, # From JRC-IDEES
    }
    ref_FT_abs = sum(ref_FT_mod_abs.values())
    if abs((ref_FT_abs-df_SUF["FT total [Gtkm]"][2019])/df_SUF["FT total [Gtkm]"][2019]*100) > 1e-5: 
     print("Entry values in 'ref_FT_mod_abs' are not correct!")
    # Outputs - Modal Shares [%] and Modal Repartition [tkm/person] for reference year (2019)
    ref_FT_mod_rel = {k: v/ref_FT_abs*100                            for k, v in ref_FT_mod_abs.items()} # [%]
    ref_FT_mod_spe = {k: v/df_SUF["population [person]"][2019]*1e+9 for k, v in ref_FT_mod_abs.items()} # [tkm/person]

    # Inputs - Define Sufficiency Scenario Data (SUF)
    pro_FT_spe_trk_hvy = -0.25
    # Outputs - Sufficiency Scenario Data (SUF)
    trg_FT_mod_spe = {'truck-heavy duty':   (1+pro_FT_spe_trk_hvy)*(1+pro_FT_spe)*ref_FT_mod_spe['truck-heavy duty']} # [tkm/person]
    trg_FT_mod_abs = {'truck-heavy duty':      trg_FT_mod_spe['truck-heavy duty']*df_SUF["population [person]"][2050]*1e-9} # [Gtkm]
    trg_FT_mod_rel = {'truck-heavy duty':      trg_FT_mod_spe['truck-heavy duty']/df_SUF["FT intensity [tkm/person]"][2050]*100} # [%]

    # Inputs - Define Sufficiency Scenario Data (SUF)
    sft_FT_rel_trk_hvy_to_trn     = +0.15
    sft_FT_rel_trk_hvy_to_nav_ild = +0.10
    if abs(pro_FT_spe_trk_hvy+sft_FT_rel_trk_hvy_to_trn+sft_FT_rel_trk_hvy_to_nav_ild) > 1e-15: 
     print("There is an error in the modal shift for the 2050 heavy duty trucking!")
    # Modal shit - Report to other modes
    sft_FT_abs_trk_hvy_to_trn     = sft_FT_rel_trk_hvy_to_trn    *(1+pro_FT_spe)*ref_FT_mod_spe['truck-heavy duty']
    sft_FT_abs_trk_hvy_to_nav_ild = sft_FT_rel_trk_hvy_to_nav_ild*(1+pro_FT_spe)*ref_FT_mod_spe['truck-heavy duty']

    # Outputs - Sufficiency Scenario Data (SUF)
    trg_FT_mod_spe['truck-light commercial'] = (1+pro_FT_spe)*ref_FT_mod_spe['truck-light commercial'] # [tkm/person]
    trg_FT_mod_abs['truck-light commercial'] =                trg_FT_mod_spe['truck-light commercial']*df_SUF["population [person]"][2050]*1e-9 # [Gtkm]
    trg_FT_mod_rel['truck-light commercial'] =                trg_FT_mod_spe['truck-light commercial']/df_SUF["FT intensity [tkm/person]"][2050]*100 # [%]

    # Outputs - Sufficiency Scenario Data (SUF)
    trg_FT_mod_spe['train'] = (1+pro_FT_spe)*ref_FT_mod_spe['train']+sft_FT_abs_trk_hvy_to_trn # [tkm/person]
    trg_FT_mod_abs['train'] =                trg_FT_mod_spe['train']*df_SUF["population [person]"][2050]*1e-9 # [Gtkm]
    trg_FT_mod_rel['train'] =                trg_FT_mod_spe['train']/df_SUF["FT intensity [tkm/person]"][2050]*100 # [%]

    # Outputs - Sufficiency Scenario Data (SUF)
    trg_FT_mod_spe['navigation-inland'] = (1+pro_FT_spe)*ref_FT_mod_spe['navigation-inland']+sft_FT_abs_trk_hvy_to_nav_ild # [tkm/person]
    trg_FT_mod_abs['navigation-inland'] =                trg_FT_mod_spe['navigation-inland']*df_SUF["population [person]"][2050]*1e-9 # [Gtkm]
    trg_FT_mod_rel['navigation-inland'] =                trg_FT_mod_spe['navigation-inland']/df_SUF["FT intensity [tkm/person]"][2050]*100 # [%]

    # Outputs - Sufficiency Scenario Data (SUF)
    trg_FT_mod_spe['navigation-coastal'] = (1+pro_FT_spe)*ref_FT_mod_spe['navigation-coastal'] # [tkm/person]
    trg_FT_mod_abs['navigation-coastal'] =                trg_FT_mod_spe['navigation-coastal']*df_SUF["population [person]"][2050]*1e-9 # [Gtkm]
    trg_FT_mod_rel['navigation-coastal'] =                trg_FT_mod_spe['navigation-coastal']/df_SUF["FT intensity [tkm/person]"][2050]*100 # [%]

    # Outputs - Sufficiency Scenario Data (SUF)
    trg_FT_mod_spe['plane-intra EU'] = (1+pro_FT_spe)*ref_FT_mod_spe['plane-intra EU'] # [tkm/person]
    trg_FT_mod_abs['plane-intra EU'] =                trg_FT_mod_spe['plane-intra EU']*df_SUF["population [person]"][2050]*1e-9 # [Gtkm]
    trg_FT_mod_rel['plane-intra EU'] =                trg_FT_mod_spe['plane-intra EU']/df_SUF["FT intensity [tkm/person]"][2050]*100 # [%]
    trg_FT_mod_spe['plane-extra EU'] = (1+pro_FT_spe)*ref_FT_mod_spe['plane-extra EU'] # [tkm/person]
    trg_FT_mod_abs['plane-extra EU'] =                trg_FT_mod_spe['plane-extra EU']*df_SUF["population [person]"][2050]*1e-9 # [Gtkm]
    trg_FT_mod_rel['plane-extra EU'] =                trg_FT_mod_spe['plane-extra EU']/df_SUF["FT intensity [tkm/person]"][2050]*100 # [%]

    # Processing - Modal Shares (in %)
    modes_FT = {
    'train':         	      linear_growth(2019,ref_FT_mod_rel['train'],
                                            2050,trg_FT_mod_rel['train'],                 years),
    'navigation-coastal':     linear_growth(2019,ref_FT_mod_rel['navigation-coastal'],
                                            2050,trg_FT_mod_rel['navigation-coastal'],    years),
    'navigation-inland':      linear_growth(2019,ref_FT_mod_rel['navigation-inland'],
                                            2050,trg_FT_mod_rel['navigation-inland'],     years),
    'truck-light commercial': linear_growth(2019,ref_FT_mod_rel['truck-light commercial'],
                                            2050,trg_FT_mod_rel['truck-light commercial'],years),
    'truck-heavy duty':       linear_growth(2019,ref_FT_mod_rel['truck-heavy duty'],
                                            2050,trg_FT_mod_rel['truck-heavy duty'],      years),
    'plane-intra EU':         linear_growth(2019,ref_FT_mod_rel['plane-intra EU'],
                                            2050,trg_FT_mod_rel['plane-intra EU'],        years),
    'plane-extra EU':         linear_growth(2019,ref_FT_mod_rel['plane-extra EU'],
                                            2050,trg_FT_mod_rel['plane-extra EU'],        years),
    }
    # Processing - Modal Shares DataFrame
    df_FT_MOD = pd.DataFrame(modes_FT, index=years)
    df_FT_MOD = df_FT_MOD.round(4).transpose()
    # Processing - Global DataFrame
    df_FT_GTKM = pd.DataFrame({year: df_SUF["FT total [Gtkm]"][year]*df_FT_MOD[year]*1e-2 for year in years}, index=df_FT_MOD.index).round(6)
    df_FT_TKMP = pd.DataFrame({year: df_FT_GTKM[year]*1e+9/population_dict[year]          for year in years}, index=df_FT_MOD.index).round(3)
    arrays_FT  =[np.repeat(df_FT_MOD.index, 3), ['% of total', 'tkm/person', 'Gtkm'] * len(df_FT_MOD)]
    mi_FT      = pd.MultiIndex.from_arrays(arrays_FT, names=['Mode', 'Unit'])
    data_FT_rows  = []
    for mode in df_FT_MOD.index:
      data_FT_rows.append(df_FT_MOD .loc[mode].values)  # modal percentages
      data_FT_rows.append(df_FT_TKMP.loc[mode].values)  # tkm per person
      data_FT_rows.append(df_FT_GTKM.loc[mode].values)  # Gtkm values
    data_FT = np.vstack(data_FT_rows)
    df_FT   = pd.DataFrame(data_FT, index=mi_FT, columns=years)

    # Inputs - Define Sufficiency Scenario Data (SUF)
    sta_FT_trk_hvy_ele   =  0.00 # [%]
    end_FT_trk_hvy_ele   = 90.00 # [%]
    sta_FT_trk_hvy_h2    =  0.00 # [%]
    end_FT_trk_hvy_h2    =  5.00 # [%]
    sta_FT_trk_hvy_cng   =  0.00 # [%]
    end_FT_trk_hvy_cng   =  2.00 # [%]
    slope_f_FT_trk_hvy   =  0.9
    # Outputs - Sufficiency Scenario Data (SUF)
    carriers_trk_hvy = {
    'electrical':          s_curve_growth(2019, sta_FT_trk_hvy_ele,                          2050, end_FT_trk_hvy_ele, years, slope_f_FT_trk_hvy),  # [%]
    'hydrogen':  linear_with_middle_point(2019, sta_FT_trk_hvy_h2, 2035, sta_FT_trk_hvy_h2,  2050, end_FT_trk_hvy_h2,  years),                      # [%]
    'gas-NG':              s_curve_growth(2019, sta_FT_trk_hvy_cng,                          2050, end_FT_trk_hvy_cng, years, slope_f_FT_trk_hvy),  # [%]
    'liquid-diesel':  [100-x-y-z for x, y, z in zip(*[s_curve_growth(2019, sta_FT_trk_hvy_ele,                          2050, end_FT_trk_hvy_ele, years, slope_f_FT_trk_hvy),
                                            linear_with_middle_point(2019, sta_FT_trk_hvy_h2, 2035, sta_FT_trk_hvy_h2,  2050, end_FT_trk_hvy_h2,  years),
                                                      s_curve_growth(2019, sta_FT_trk_hvy_cng,                          2050, end_FT_trk_hvy_cng, years, slope_f_FT_trk_hvy)])], # [%]
    }
    df_FT_trk_hvy = pd.DataFrame(carriers_trk_hvy, index=years).T.round(3)

    # Inputs - Define Sufficiency Scenario Data (SUF)
    sta_FT_trk_lgt_lfd   = 96.38# [%]
    end_FT_trk_lgt_lfd   =  1.50 # [%]
    sta_FT_trk_lgt_lfg   =  2.80 # [%]
    end_FT_trk_lgt_lfg   =  1.50 # [%]
    sta_FT_trk_lgt_lpg   =  0.42 # [%]
    end_FT_trk_lgt_lpg   =  0.00 # [%]
    sta_FT_trk_lgt_cng   =  0.27 # [%]
    end_FT_trk_lgt_cng   =  1.50 # [%]
    slope_f_FT_trk_lgt   =  0.9
    # Outputs - Sufficiency Scenario Data (SUF)
    carriers_trk_lgt = {
    'liquid-diesel':    s_curve_growth(2019, sta_FT_trk_lgt_lfd, 2050, end_FT_trk_lgt_lfd, years, slope_f_FT_trk_lgt),  # [%]
    'liquid-gasoline':  s_curve_growth(2019, sta_FT_trk_lgt_lfg, 2050, end_FT_trk_lgt_lfg, years, slope_f_FT_trk_lgt),  # [%]
    'gas-LPG':          s_curve_growth(2019, sta_FT_trk_lgt_lpg, 2050, end_FT_trk_lgt_lpg, years, slope_f_FT_trk_lgt),  # [%]
    'gas-NG':           s_curve_growth(2019, sta_FT_trk_lgt_cng, 2050, end_FT_trk_lgt_cng, years, slope_f_FT_trk_lgt),  # [%]
    'electrical':  [100-w-x-y-z for w, x, y, z in zip(*[s_curve_growth(2019, sta_FT_trk_lgt_lfd, 2050, end_FT_trk_lgt_lfd, years, slope_f_FT_trk_lgt),
                                                        s_curve_growth(2019, sta_FT_trk_lgt_lfg, 2050, end_FT_trk_lgt_lfg, years, slope_f_FT_trk_lgt),
                                                        s_curve_growth(2019, sta_FT_trk_lgt_lpg, 2050, end_FT_trk_lgt_lpg, years, slope_f_FT_trk_lgt),
                                                        s_curve_growth(2019, sta_FT_trk_lgt_cng, 2050, end_FT_trk_lgt_cng, years, slope_f_FT_trk_lgt)])], # [%]
    }
    df_FT_trk_lgt = pd.DataFrame(carriers_trk_lgt, index=years).T.round(3)

    # Inputs - Define Sufficiency Scenario Data (SUF)
    sta_FT_trn = 14.65 # [%]
    end_FT_trn =  5.00 # [%]
    # Outputs - Sufficiency Scenario Data (SUF)
    carriers_FT_trn = {
    'liquid-diesel':               linear_growth(2019, sta_FT_trn, 2050, end_FT_trn, years),  # [%]
    'electrical':  [100-x for x in linear_growth(2019, sta_FT_trn, 2050, end_FT_trn, years)], # [%]
    }
    df_FT_trn = pd.DataFrame(carriers_FT_trn, index=years).T.round(3)

    # Inputs - Define Sufficiency Scenario Data (SUF)
    sta_FT_avi_srt  = 0 # [%]
    end_FT_avi_srt  = 5 # [%]
    mid_FT_avi_srt  = 2045
    # Outputs - Sufficiency Scenario Data (SUF)
    carriers_FT_avi_srt = {
    'hydrogen':                         linear_with_middle_point(2019, sta_FT_avi_srt, mid_FT_avi_srt, sta_FT_avi_srt, 2050, end_FT_avi_srt, years),  # [%]
    'liquid-kerosene':  [100-x for x in linear_with_middle_point(2019, sta_FT_avi_srt, mid_FT_avi_srt, sta_FT_avi_srt, 2050, end_FT_avi_srt, years)], # [%]
    }
    carriers_FT_avi_lng = {
    'liquid-kerosene':  linear_growth(2019, 100, 2050, 100, years), # [%]
    }
    df_FT_avi_srt = pd.DataFrame(carriers_FT_avi_srt, index=years).T.round(3)
    df_FT_avi_lng = pd.DataFrame(carriers_FT_avi_lng, index=years).T.round(3)

    # Inputs - Define Sufficiency Scenario Data (SUF)
    sta_FT_nav_lfa   =  0.00 # [%]
    end_FT_nav_lfa   = 17.50 # [%]
    sta_FT_nav_h2    =  0.00 # [%]
    end_FT_nav_h2    =  7.50 # [%]
    sta_FT_nav_lfm   =  0.00 # [%]
    end_FT_nav_lfm   = 35.00 # [%]
    mid_y = 2035
    # Outputs - Sufficiency Scenario Data (SUF)
    carriers_nav = {
    'ammonia':          linear_with_middle_point(2019, sta_FT_nav_lfa, mid_y, sta_FT_nav_lfa, 2050, end_FT_nav_lfa, years),  # [%]
    'hydrogen':         linear_with_middle_point(2019, sta_FT_nav_h2,  mid_y, sta_FT_nav_h2,  2050, end_FT_nav_h2,  years),  # [%]
    'methanol':         linear_with_middle_point(2019, sta_FT_nav_lfm, mid_y, sta_FT_nav_lfm, 2050, end_FT_nav_lfm, years),  # [%]
    'liquid-diesel': [100-x-y-z for x, y, z in zip(*[linear_with_middle_point(2019, sta_FT_nav_lfa, mid_y, sta_FT_nav_lfa, 2050, end_FT_nav_lfa, years),
                                                     linear_with_middle_point(2019, sta_FT_nav_h2,  mid_y, sta_FT_nav_h2,  2050, end_FT_nav_h2,  years),
                                                     linear_with_middle_point(2019, sta_FT_nav_lfm, mid_y, sta_FT_nav_lfm, 2050, end_FT_nav_lfm, years)])], # [%]
    }
    df_FT_nav = pd.DataFrame(carriers_nav, index=years).T.round(3)

    # Processing - Carriers Shares (in %)
    df_FT_carriers = {
	'train':                  df_FT_trn,
	'navigation-coastal':     df_FT_nav,
    'navigation-inland':      df_FT_nav,
    'truck-light commercial': df_FT_trk_lgt,
    'truck-heavy duty':       df_FT_trk_hvy,
    'plane-intra EU':         df_FT_avi_srt,
    'plane-extra EU':         df_FT_avi_lng,
    }
    rows = []
    for mode, df in df_FT_carriers.items():
      temp = df.copy()
      temp['Mode'] = mode
      temp['Powertrain'] = temp.index
      temp = temp.reset_index(drop=True)
      rows.append(temp)
    df_FT_carrier = pd.concat(rows, ignore_index=True)

    # ===== Train =====
    # -> Settings
    redu_fuel_FT_trn = 0.90
    pyld_trgt_FT_trn = 1.00
    # -> Projections of efficiency and payload
    cons_fuel_FT_trn = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019, 536.484/100*kgoe_to_kWh, 2050, 536.484/100*kgoe_to_kWh,                  years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    'electrical':      linear_growth(2019, 190.096/100*kgoe_to_kWh, 2050, 190.096/100*kgoe_to_kWh*redu_fuel_FT_trn, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    payload_FT_trn = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019, 770.099,                 2050, 770.099                *pyld_trgt_FT_trn, years),  # [t] -> sta = JRC-IDEES, end = nW-BE
    'electrical':      linear_growth(2019, 732.106,                 2050, 732.106                *pyld_trgt_FT_trn, years),  # [t] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_FT_trn_TWh = df_FT_carrier[df_FT_carrier['Mode'] == 'train'].copy()
    df_FT_trn_TWh[years] *= df_FT_GTKM.loc['train', years].values/100 # Gtkm
    df_FT_trn_TWh = df_FT_trn_TWh.set_index('Powertrain') # Gtkm
    df_FT_trn_TWh[years] *= cons_fuel_FT_trn[years]/payload_FT_trn[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_FT_trn_TWh)
    df_FT_trn_TWh.loc[new_index, years] = df_FT_trn_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_FT_trn_TWh.columns: df_FT_trn_TWh = df_FT_trn_TWh.reset_index()
    df_FT_trn_TWh = df_FT_trn_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_FT_trn_TWh.index[-1]
    df_FT_trn_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_FT_trn_TWh.loc[last_row_index, 'Mode'] = 'train'
    df_FT_trn_TWh = df_FT_trn_TWh[['Mode','Powertrain'] + years]
    df_FT_trn_TWh = df_FT_trn_TWh.round(3)

    # ===== Coastal Navigation =====
    # -> Settings
    redu_fuel_FT_nav_cst = 1.00
    pyld_trgt_FT_nav_cst = 1.00
    # -> Projections of efficiency and payload
    cons_fuel_FT_nav_cst = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019, 12355.078/100*kgoe_to_kWh, 2050, 12355.078/100*kgoe_to_kWh,                      years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
	'hydrogen':        linear_growth(2019, 12355.078/100*kgoe_to_kWh, 2050, 12355.078/100*kgoe_to_kWh*redu_fuel_FT_nav_cst, years),  # [kWh/km] -> sta = nW-BE, end = nW-BE
    'methanol':        linear_growth(2019, 12355.078/100*kgoe_to_kWh, 2050, 12355.078/100*kgoe_to_kWh*redu_fuel_FT_nav_cst, years),  # [kWh/km] -> sta = nW-BE, end = nW-BE
    'ammonia':         linear_growth(2019, 12355.078/100*kgoe_to_kWh, 2050, 12355.078/100*kgoe_to_kWh*redu_fuel_FT_nav_cst, years),  # [kWh/km] -> sta = nW-BE, end = nW-BE
    }, index=years).T
    # Ammonia and methanol are also ICE, so we assume same efficiency.
    # Hydrogen could be ICE and FC: following [10], hydrogen blends could be burned in ICE
    payload_FT_nav_cst = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019, 3108.677, 2050, 3108.677*pyld_trgt_FT_nav_cst, years),  # [t] -> sta = JRC-IDEES, end = nW-BE
    'hydrogen':        linear_growth(2019, 3108.677, 2050, 3108.677*pyld_trgt_FT_nav_cst, years),  # [t] -> sta = nW-BE, end = nW-BE
    'methanol':        linear_growth(2019, 3108.677, 2050, 3108.677*pyld_trgt_FT_nav_cst, years),  # [t] -> sta = nW-BE, end = nW-BE
    'ammonia':         linear_growth(2019, 3108.677, 2050, 3108.677*pyld_trgt_FT_nav_cst, years),  # [t] -> sta = nW-BE, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_FT_nav_cst_TWh = df_FT_carrier[df_FT_carrier['Mode'] == 'navigation-coastal'].copy()
    df_FT_nav_cst_TWh[years] *= df_FT_GTKM.loc['navigation-coastal', years].values/100 # Gtkm
    df_FT_nav_cst_TWh = df_FT_nav_cst_TWh.set_index('Powertrain') # Gtkm
    df_FT_nav_cst_TWh[years] *= cons_fuel_FT_nav_cst[years]/payload_FT_nav_cst[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_FT_nav_cst_TWh)
    df_FT_nav_cst_TWh.loc[new_index, years] = df_FT_nav_cst_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_FT_nav_cst_TWh.columns: df_FT_nav_cst_TWh = df_FT_nav_cst_TWh.reset_index()
    df_FT_nav_cst_TWh = df_FT_nav_cst_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_FT_nav_cst_TWh.index[-1]
    df_FT_nav_cst_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_FT_nav_cst_TWh.loc[last_row_index, 'Mode'] = 'navigation-coastal'
    df_FT_nav_cst_TWh = df_FT_nav_cst_TWh[['Mode','Powertrain'] + years]
    df_FT_nav_cst_TWh = df_FT_nav_cst_TWh.round(3)

    # ===== Inland Navigation =====
    # -> Settings
    redu_fuel_FT_nav_ild = 1.00
    pyld_trgt_FT_nav_ild = 1.00
    # -> Projections of efficiency and payload
    cons_fuel_FT_nav_ild = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019, 1079.015/100*kgoe_to_kWh, 2050, 1079.015/100*kgoe_to_kWh,                      years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
	'hydrogen':        linear_growth(2019, 1079.015/100*kgoe_to_kWh, 2050, 1079.015/100*kgoe_to_kWh*redu_fuel_FT_nav_ild, years),  # [kWh/km] -> sta = nW-BE, end = nW-BE
    'methanol':        linear_growth(2019, 1079.015/100*kgoe_to_kWh, 2050, 1079.015/100*kgoe_to_kWh*redu_fuel_FT_nav_ild, years),  # [kWh/km] -> sta = nW-BE, end = nW-BE
    'ammonia':         linear_growth(2019, 1079.015/100*kgoe_to_kWh, 2050, 1079.015/100*kgoe_to_kWh*redu_fuel_FT_nav_ild, years),  # [kWh/km] -> sta = nW-BE, end = nW-BE
    }, index=years).T
    # Ammonia and methanol are also ICE, so we assume same efficiency.
    # Hydrogen could be ICE and FC: following [10], hydrogen blends could be burned in ICE
    payload_FT_nav_ild = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019, 617.310, 2050, 617.310*pyld_trgt_FT_nav_ild, years),  # [t] -> sta = JRC-IDEES, end = nW-BE
    'hydrogen':        linear_growth(2019, 617.310, 2050, 617.310*pyld_trgt_FT_nav_ild, years),  # [t] -> sta = nW-BE, end = nW-BE
    'methanol':        linear_growth(2019, 617.310, 2050, 617.310*pyld_trgt_FT_nav_ild, years),  # [t] -> sta = nW-BE, end = nW-BE
    'ammonia':         linear_growth(2019, 617.310, 2050, 617.310*pyld_trgt_FT_nav_ild, years),  # [t] -> sta = nW-BE, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_FT_nav_ild_TWh = df_FT_carrier[df_FT_carrier['Mode'] == 'navigation-inland'].copy()
    df_FT_nav_ild_TWh[years] *= df_FT_GTKM.loc['navigation-inland', years].values/100 # Gtkm
    df_FT_nav_ild_TWh = df_FT_nav_ild_TWh.set_index('Powertrain') # Gtkm
    df_FT_nav_ild_TWh[years] *= cons_fuel_FT_nav_ild[years]/payload_FT_nav_ild[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_FT_nav_ild_TWh)
    df_FT_nav_ild_TWh.loc[new_index, years] = df_FT_nav_ild_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_FT_nav_ild_TWh.columns: df_FT_nav_ild_TWh = df_FT_nav_ild_TWh.reset_index()
    df_FT_nav_ild_TWh = df_FT_nav_ild_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_FT_nav_ild_TWh.index[-1]
    df_FT_nav_ild_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_FT_nav_ild_TWh.loc[last_row_index, 'Mode'] = 'navigation-inland'
    df_FT_nav_ild_TWh = df_FT_nav_ild_TWh[['Mode','Powertrain'] + years]
    df_FT_nav_ild_TWh = df_FT_nav_ild_TWh.round(3)

    # ===== Light Commercial Trucks =====
    # -> Settings
    redu_fuel_FT_trk_lgt = 0.90
    pyld_trgt_FT_trk_lgt = 1.05
    # -> Projections of efficiency and payload
    cons_fuel_FT_trk_lgt = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019,  9.099/100*kgoe_to_kWh, 2050,  9.099/100*kgoe_to_kWh*redu_fuel_FT_trk_lgt, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
	'liquid-gasoline': linear_growth(2019,  8.203/100*kgoe_to_kWh, 2050,  8.203/100*kgoe_to_kWh*redu_fuel_FT_trk_lgt, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    'electrical':      linear_growth(2019,  1.996/100*kgoe_to_kWh, 2050,  1.996/100*kgoe_to_kWh*redu_fuel_FT_trk_lgt, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
	'gas-LPG':         linear_growth(2019, 12.830/100*kgoe_to_kWh, 2050, 12.830/100*kgoe_to_kWh*redu_fuel_FT_trk_lgt, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
	'gas-NG':          linear_growth(2019, 12.876/100*kgoe_to_kWh, 2050, 12.876/100*kgoe_to_kWh*redu_fuel_FT_trk_lgt, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    payload_FT_trk_lgt = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019, 0.095,                  2050,                  0.095*pyld_trgt_FT_trk_lgt, years),  # [t] -> sta = JRC-IDEES, end = nW-BE
	'liquid-gasoline': linear_growth(2019, 0.071,                  2050,                  0.071*pyld_trgt_FT_trk_lgt, years),  # [t] -> sta = JRC-IDEES, end = nW-BE
    'electrical':      linear_growth(2019, 0.072,                  2050,                  0.072*pyld_trgt_FT_trk_lgt, years),  # [t] -> sta = JRC-IDEES, end = nW-BE
	'gas-LPG':         linear_growth(2019, 0.073,                  2050,                  0.073*pyld_trgt_FT_trk_lgt, years),  # [t] -> sta = JRC-IDEES, end = nW-BE
	'gas-NG':          linear_growth(2019, 0.073,                  2050,                  0.073*pyld_trgt_FT_trk_lgt, years),  # [t] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_FT_trk_lgt_TWh = df_FT_carrier[df_FT_carrier['Mode'] == 'truck-light commercial'].copy()
    df_FT_trk_lgt_TWh[years] *= df_FT_GTKM.loc['truck-light commercial', years].values/100 # GTKM
    df_FT_trk_lgt_TWh = df_FT_trk_lgt_TWh.set_index('Powertrain') # GTKM
    df_FT_trk_lgt_TWh[years] *= cons_fuel_FT_trk_lgt[years]/payload_FT_trk_lgt[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_FT_trk_lgt_TWh)
    df_FT_trk_lgt_TWh.loc[new_index, years] = df_FT_trk_lgt_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_FT_trk_lgt_TWh.columns: df_FT_trk_lgt_TWh = df_FT_trk_lgt_TWh.reset_index()
    df_FT_trk_lgt_TWh = df_FT_trk_lgt_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_FT_trk_lgt_TWh.index[-1]
    df_FT_trk_lgt_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_FT_trk_lgt_TWh.loc[last_row_index, 'Mode'] = 'truck-light commercial'
    df_FT_trk_lgt_TWh = df_FT_trk_lgt_TWh[['Mode','Powertrain'] + years]
    df_FT_trk_lgt_TWh = df_FT_trk_lgt_TWh.round(3)

    # ===== Heavy Duty Trucks =====
    # -> Settings
    redu_fuel_FT_trk_hvy = 0.95
    pyld_trgt_FT_trk_hvy = 1.05
    # -> Projections of efficiency and payload
    cons_fuel_FT_trk_hvy = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019, 49.763/100*kgoe_to_kWh, 2050, 49.763/100*kgoe_to_kWh,                      years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    'electrical':      linear_growth(2019,130.000/100,             2050,130.000/100            *redu_fuel_FT_trk_hvy, years),  # [kWh/km] -> sta = nW-BE, end = nW-BE
	'hydrogen':        linear_growth(2019,  8.400/100*kgh2_to_kWh, 2050,  8.400/100*kgh2_to_kWh*redu_fuel_FT_trk_hvy, years),  # [kWh/km] -> sta = nW-BE, end = nW-BE
	'gas-NG':          linear_growth(2019, 25.000/100*kgLNG_to_kWh,2050, 25.000/100*kgLNG_to_kWh*redu_fuel_FT_trk_hvy,years),  # [kWh/km] -> sta = nW-BE, end = nW-BE
    }, index=years).T
    # Renault E-Tech T 780 (semitrailer): 130 kWh/100km (780kWh for 600km)
    # Renault E-Tech T 585 (semitrailer): 127 kWh/100km (585kWh for 460km)
    # MAN eTGX             (semitrailer):  96 kWh/100km (480kWh for 500km)
    # Mercedes eACTROS 600 (semitrailer): 124 kWh/100km (621kWh for 500km)
    # Zepp Europa          (semitrailer):  8.4 kg/100km (58.8kg for 700km)
    # Volvo FH Aero LNG    (semitrailer): 22.5 kg/100km (225kg for 1000km) 
    payload_FT_trk_hvy = pd.DataFrame({
    'liquid-diesel':   linear_growth(2019, 12.654,           2050,           12.654*pyld_trgt_FT_trk_hvy, years),  # [t] -> sta = JRC-IDEES, end = nW-BE
    'electrical':      linear_growth(2019, 12.654,           2050,           12.654*pyld_trgt_FT_trk_hvy, years),  # [t] -> sta = nW-BE, end = nW-BE
	'hydrogen':        linear_growth(2019, 12.654,           2050,           12.654*pyld_trgt_FT_trk_hvy, years),  # [t] -> sta = nW-BE, end = nW-BE
	'gas-NG':          linear_growth(2019, 12.654,           2050,           12.654*pyld_trgt_FT_trk_hvy, years),  # [t] -> sta = nW-BE, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_FT_trk_hvy_TWh = df_FT_carrier[df_FT_carrier['Mode'] == 'truck-heavy duty'].copy()
    df_FT_trk_hvy_TWh[years] *= df_FT_GTKM.loc['truck-heavy duty', years].values/100 # Gtkm
    df_FT_trk_hvy_TWh = df_FT_trk_hvy_TWh.set_index('Powertrain') # Gtkm
    df_FT_trk_hvy_TWh[years] *= cons_fuel_FT_trk_hvy[years]/payload_FT_trk_hvy[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_FT_trk_hvy_TWh)
    df_FT_trk_hvy_TWh.loc[new_index, years] = df_FT_trk_hvy_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_FT_trk_hvy_TWh.columns: df_FT_trk_hvy_TWh = df_FT_trk_hvy_TWh.reset_index()
    df_FT_trk_hvy_TWh = df_FT_trk_hvy_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_FT_trk_hvy_TWh.index[-1]
    df_FT_trk_hvy_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_FT_trk_hvy_TWh.loc[last_row_index, 'Mode'] = 'truck-heavy duty'
    df_FT_trk_hvy_TWh = df_FT_trk_hvy_TWh[['Mode','Powertrain'] + years]
    df_FT_trk_hvy_TWh = df_FT_trk_hvy_TWh.round(3)

    # ===== Aviation (intra EU) =====
    # -> Settings
    redu_fuel_FT_avi_intra = 1.00 
    pyld_trgt_FT_avi_intra = 1.00 
    # -> Projections of efficiency and payload
    cons_fuel_FT_avi_intra = pd.DataFrame({
    'hydrogen':        linear_growth(2019, 130.000/100*kgh2_to_kWh, 2050, 130.000/100*kgh2_to_kWh,                        years),  # [kWh/km] -> sta = nW-BE, end = nW-BE
    'liquid-kerosene': linear_growth(2019, 665.675/100*kgoe_to_kWh, 2050, 665.675/100*kgoe_to_kWh*redu_fuel_FT_avi_intra, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    payload_FT_avi_intra = pd.DataFrame({
    'hydrogen':        linear_growth(2019, 100.000/121.927*25.200, 2050,  100.000/121.927*25.200,                        years),  # [t] -> sta = nW-BE, end = nW-BE
    'liquid-kerosene': linear_growth(2019,                 25.200, 2050,                  25.200*pyld_trgt_FT_avi_intra, years),  # [t] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    # Payload of Airbus Zero-E is scaled from passenger aviation data
    # -> Conversion to TWh
    df_FT_avi_srt_TWh = df_FT_carrier[df_FT_carrier['Mode'] == 'plane-intra EU'].copy()
    df_FT_avi_srt_TWh[years] *= df_FT_GTKM.loc['plane-intra EU', years].values/100 # Gtkm
    df_FT_avi_srt_TWh = df_FT_avi_srt_TWh.set_index('Powertrain') # Gtkm
    df_FT_avi_srt_TWh[years] *= cons_fuel_FT_avi_intra[years]/payload_FT_avi_intra[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_FT_avi_srt_TWh)
    df_FT_avi_srt_TWh.loc[new_index, years] = df_FT_avi_srt_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_FT_avi_srt_TWh.columns: df_FT_avi_srt_TWh = df_FT_avi_srt_TWh.reset_index()
    df_FT_avi_srt_TWh = df_FT_avi_srt_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_FT_avi_srt_TWh.index[-1]
    df_FT_avi_srt_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_FT_avi_srt_TWh.loc[last_row_index, 'Mode'] = 'plane-intra EU'
    df_FT_avi_srt_TWh = df_FT_avi_srt_TWh[['Mode','Powertrain'] + years]
    df_FT_avi_srt_TWh = df_FT_avi_srt_TWh.round(3)

    # ===== Aviation (extra EU) =====
    # -> Settings
    redu_fuel_FT_avi_extra = 1.00 
    pyld_trgt_FT_avi_extra = 1.00
    # -> Projections of efficiency and payload
    cons_fuel_FT_avi_extra = pd.DataFrame({
    'liquid-kerosene': linear_growth(2019, 618.493/100*kgoe_to_kWh, 2050, 618.493/100*kgoe_to_kWh*redu_fuel_FT_avi_extra, years),  # [kWh/km] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    payload_FT_avi_extra = pd.DataFrame({
    'liquid-kerosene': linear_growth(2019,  98.258,                 2050,                  98.258*pyld_trgt_FT_avi_extra, years),  # [t] -> sta = JRC-IDEES, end = nW-BE
    }, index=years).T
    # -> Conversion to TWh
    df_FT_avi_lng_TWh = df_FT_carrier[df_FT_carrier['Mode'] == 'plane-extra EU'].copy()
    df_FT_avi_lng_TWh[years] *= df_FT_GTKM.loc['plane-extra EU', years].values/100 # Gtkm
    df_FT_avi_lng_TWh = df_FT_avi_lng_TWh.set_index('Powertrain') # Gtkm
    df_FT_avi_lng_TWh[years] *= cons_fuel_FT_avi_extra[years]/payload_FT_avi_extra[years] # TWh
    # -> Make total for sanity check
    new_index = len(df_FT_avi_lng_TWh)
    df_FT_avi_lng_TWh.loc[new_index, years] = df_FT_avi_lng_TWh[years].sum()
    # -> Clean and process
    if 'Powertrain' not in df_FT_avi_lng_TWh.columns: df_FT_avi_lng_TWh = df_FT_avi_lng_TWh.reset_index()
    df_FT_avi_lng_TWh = df_FT_avi_lng_TWh.rename(columns={'index': 'Powertrain'})
    last_row_index = df_FT_avi_lng_TWh.index[-1]
    df_FT_avi_lng_TWh.loc[last_row_index, 'Powertrain'] = 'TOTAL'
    df_FT_avi_lng_TWh.loc[last_row_index, 'Mode'] = 'plane-extra EU'
    df_FT_avi_lng_TWh = df_FT_avi_lng_TWh[['Mode','Powertrain'] + years]
    df_FT_avi_lng_TWh = df_FT_avi_lng_TWh.round(3)

    df_FT_TWh_lst = [df_FT_trn_TWh, 
                 df_FT_nav_ild_TWh, 
                 df_FT_nav_cst_TWh, 
                 df_FT_trk_hvy_TWh, 
                 df_FT_trk_lgt_TWh, 
                 df_FT_avi_srt_TWh, 
                 df_FT_avi_lng_TWh
    ]
    df_FT_TWh_all = pd.concat(df_FT_TWh_lst, ignore_index=True)
    df_FT_TWh_flt = df_FT_TWh_all[~df_FT_TWh_all['Powertrain'].isin(['TOTAL'])].copy()
    df_FT_TWh_agr = df_FT_TWh_flt.groupby('Powertrain').sum(numeric_only=True)
    custom_order = [
    'electrical', 
    'liquid-gasoline', 
    'liquid-diesel', 
    'liquid-kerosene', 
    'gas-NG', 
    'gas-LPG', 
    'hydrogen',
	'methanol',
	'ammonia',
    ]
    df_FT_TWh_agr = df_FT_TWh_agr.reindex(custom_order)

    # Aggregate global demand data
    custom_order = [
    'population [person]', 
    'PM intensity [pkm/person]', 
    'PM total [Gpkm]',
    'FT intensity [tkm/person]', 
    'FT total [Gtkm]',
    ]
    df_SUF = df_SUF.T.reindex(custom_order)
    # Aggregate global energy data
    df_transport_TWh_tot = df_PM_TWh_agr.add(df_FT_TWh_agr, fill_value=0)

    df_transport_TWh_tot.loc[ len(df_transport_TWh_tot)] = df_transport_TWh_tot.sum(numeric_only=True)
    df_transport_TWh_tot = df_transport_TWh_tot.rename(index={9: 'TOTAL'})

    # Optional: Re-apply your custom order to the final total
    custom_order = [
    'electrical', 
    'liquid-gasoline', 'liquid-diesel', 'liquid-kerosene', 
    'gas-NG', 'gas-LPG', 
    'hydrogen', 'methanol', 'ammonia',
    'TOTAL'
      ]
    df_transport_TWh_tot = df_transport_TWh_tot.reindex(custom_order)
    df_transport_TWh_tot

    return {
        "mobility": df_PM_TWh_all,
        "freight": df_FT_TWh_all,
    } 

def res_ter():
    # Inputs - Define Sufficiency Scenario Data (SUF)
    ref_RS_sur_tot = 625235.722685535*1e+3
    ref_RS_sur_spe = ref_RS_sur_tot/population_dict[2019] # [m²/person]
    ref_RS_sur_hld = ref_RS_sur_tot/households_dict[2019] # [m²/household]

    # Inputs - Define Sufficiency Scenario Data (SUF)
    pro_RS_sur_spe = -0.10
    # Outputs - Sufficiency Scenario Data (SUF)
    SUF_data = {"RS specific surface [m²/person]": linear_growth(2019, ref_RS_sur_spe, 
                                                             2050, ref_RS_sur_spe*(1+pro_RS_sur_spe), years)}
    df_SUF = pd.DataFrame(SUF_data, index=years)
    df_SUF["population [person]"]                 = df_SUF.index.map(population_dict)
    df_SUF["households [household]"]              = df_SUF.index.map(households_dict)
    df_SUF["households [person]"]                 = df_SUF["population [person]"]            /df_SUF["households [household]"]
    df_SUF["RS total surface [Mm²]"]              = df_SUF["RS specific surface [m²/person]"]*df_SUF["population [person]"]*1e-6
    df_SUF["RS household surface [m²/household]"] = df_SUF["RS total surface [Mm²]"]*1e+6    /df_SUF["households [household]"]

    # Inputs - Define Sufficiency Scenario Data (SUF)
    ref_TS_sur_tot = 227073.149760375*1e+3
    ref_TS_sur_spe = ref_TS_sur_tot/population_dict[2019] # [m²/person]

    # Inputs - Define Sufficiency Scenario Data (SUF)
    pro_TS_sur_spe = -0.10
    # Outputs - Sufficiency Scenario Data (SUF)
    df_SUF["TS specific surface [m²/person]"] = linear_growth(2019, ref_TS_sur_spe, 
                                                          2050, ref_TS_sur_spe*(1+pro_TS_sur_spe), years)
    df_SUF["TS total surface [Mm²]"] = df_SUF["TS specific surface [m²/person]"]*df_SUF["population [person]"]*1e-6

    # Processing - Sectors
    df_BD_macro = {
    'Demographic':   df_SUF[["population [person]","households [household]","households [person]"]].T,
    'Residential':   df_SUF[["RS total surface [Mm²]","RS household surface [m²/household]","RS specific surface [m²/person]"]].T,
    'Tertiary':      df_SUF[["TS total surface [Mm²]","TS specific surface [m²/person]"]].T,}
    rows = []
    for sector, df in df_BD_macro.items():
      temp = df.copy()
      temp['Sector'] = sector
      temp['Parameter'] = temp.index
      temp = temp.reset_index(drop=True)
      rows.append(temp)
    df_BD_macro = pd.concat(rows, ignore_index=True)

    # Inputs - Repartition of the thermal energy services (TES) in residential buildings for the reference year (2019)
    ref_RS_tes_sht = 3664.049*ktoe_to_GWh*1e+6/ref_RS_sur_tot # [kWh/m²]
    ref_RS_tes_scl =   23.455*ktoe_to_GWh*1e+6/ref_RS_sur_tot # [kWh/m²]
    ref_RS_tes_shw =  663.435*ktoe_to_GWh*1e+6/df_SUF["population [person]"][2019] # [kWh/person]
    ref_RS_tes_cok =   96.395*ktoe_to_GWh*1e+6/df_SUF["households [household]"][2019] # [kWh/household]

    acc_RS_tes_sht_ren = 2
    cur_RS_tes_sht_ren = -0.458 # kWh/m²/year
    trg_RS_tes_sht     = ref_RS_tes_sht + acc_RS_tes_sht_ren*cur_RS_tes_sht_ren*(2050-2019) # [kWh/m²]

    d_cons_temp = 0.07
    d_temp = 2
    suf_RS_tes_sht = 1-d_temp*d_cons_temp

    acc_RS_tes_scl_ren = 1
    cur_RS_tes_scl_ren = 0.035 # kWh/m²/year
    trg_RS_tes_scl     = ref_RS_tes_scl + acc_RS_tes_scl_ren*cur_RS_tes_scl_ren*(2050-2019) # [kWh/m²]

    # Inputs - Define Sufficiency Scenario Data (SUF)
    shower_duration    = 5 # [min]
    shower_flow_rate   = 7 # [l/min]
    shower_temperature = 38 # [°C]
    shower_energy      = shower_duration*shower_flow_rate*rho_h2o*cp_h2o*(shower_temperature-15) # [kWh/shower]
    others_volume      = 10 # [l]
    others_temperature = 60 # [°C]
    others_energy      = others_volume*rho_h2o*cp_h2o*(others_temperature-15) # [kWh]
    # Outputs - Sufficiency Scenario Data (SUF)
    trg_RS_tes_shw     = (shower_energy+others_energy)*365
    pro_RS_tes_shw     = (trg_RS_tes_shw-ref_RS_tes_shw)/ref_RS_tes_shw

    # Inputs - Define Sufficiency Scenario Data (SUF)
    pro_RS_tes_cok     = 0.15
    ref_RS_tes_cok_gas = (3.846+21.957)/96.395 # ktoe_gas/ktoe_tot (from JRC-IDEES)
    trg_RS_tes_cok_gas = 0.02
    # Outputs - Sufficiency Scenario Data (SUF)
    trg_RS_tes_cok = (1+pro_RS_tes_cok)*ref_RS_tes_cok # kWh/person
    share_cook_gas = linear_growth(2019,  ref_RS_tes_cok_gas,
                               2050,  trg_RS_tes_cok_gas,years) # [%]
    share_cook_ele = linear_growth(2019,1-ref_RS_tes_cok_gas,
                               2050,1-trg_RS_tes_cok_gas,years) # [%]

    ref_RS_tes_dhn = 10.823/(3664.049+663.435) # [%] 2019 reference share of district heating network in Belgium from JRC-IDEES
    trg_RS_tes_dhn = 0.15                      # [%] 2050 target    share of district heating network in Belgium from nW-BE
    share_heat_dhn = linear_growth(2019,  ref_RS_tes_dhn,
                               2050,  trg_RS_tes_dhn,years) # [%]
    share_heat_ihs = linear_growth(2019,1-ref_RS_tes_dhn,
                               2050,1-trg_RS_tes_dhn,years) # [%]

    # Inputs - Repartition of the electrical energy services (EES) in residential buildings for the reference year (2019)
    ref_RS_ees_frg = 209.814*ktoe_to_GWh*1e+6/df_SUF["households [household]"][2019] # [kWh/household]
    ref_RS_ees_wsh =  64.045*ktoe_to_GWh*1e+6/df_SUF["households [household]"][2019] # [kWh/household]
    ref_RS_ees_dry =  73.446*ktoe_to_GWh*1e+6/df_SUF["households [household]"][2019] # [kWh/household]
    ref_RS_ees_dsh =  59.199*ktoe_to_GWh*1e+6/df_SUF["households [household]"][2019] # [kWh/household]
    ref_RS_ees_tvm = 257.507*ktoe_to_GWh*1e+6/df_SUF["households [household]"][2019] # [kWh/household]
    ref_RS_ees_ict =  96.860*ktoe_to_GWh*1e+6/df_SUF["households [household]"][2019] # [kWh/household]
    ref_RS_ees_lgt = 139.889*ktoe_to_GWh*1e+6/df_SUF["households [household]"][2019] # [kWh/household]
    ref_RS_ees_oth =  97.004*ktoe_to_GWh*1e+6/df_SUF["households [household]"][2019] # [kWh/household]
    
    trg_RS_ees_frg = 150 # [kWh/household]
    yea_RS_ees_frg = 2040
    trg_RS_ees_wsh = 90 # [kWh/household]
    yea_RS_ees_wsh = 2030
    trg_RS_ees_dry = 80 # [kWh/household]
    yea_RS_ees_dry = 2040
    trg_RS_ees_dsh =  150 # [kWh/household]
    yea_RS_ees_dsh = 2050
    trg_RS_ees_tvm = (1-0.3)*ref_RS_ees_tvm # [kWh/household]
    yea_RS_ees_tvm = 2050
    trg_RS_ees_ict = ref_RS_ees_ict # [kWh/household]
    yea_RS_ees_ict = 2019
    # **Lighting**
    trg_RS_ees_lgt = 130 # [kWh/household]
    yea_RS_ees_lgt = 2035
    trg_RS_ees_oth = ref_RS_ees_oth # [kWh/household]
    yea_RS_ees_oth = 2019

    # Residential Sector - Thermal Energy Services
    tes_RS_tot = {
    'space heating':      linear_growth(2019,ref_RS_tes_sht               *df_SUF["RS total surface [Mm²]"][2019]*1e-3,
                                        2050,trg_RS_tes_sht*suf_RS_tes_sht*df_SUF["RS total surface [Mm²]"][2050]*1e-3,years), # [TWh] kWh/m² * m²
    'space cooling':      linear_growth(2019,ref_RS_tes_scl               *df_SUF["RS total surface [Mm²]"][2019]*1e-3,
                                        2050,trg_RS_tes_scl               *df_SUF["RS total surface [Mm²]"][2050]*1e-3,years), # [TWh] kWh/m² * m²
    'sanitary hot water': linear_growth(2019,ref_RS_tes_shw               *df_SUF["population [person]"]   [2019]*1e-9,
                                        2050,trg_RS_tes_shw               *df_SUF["population [person]"]   [2050]*1e-9,years), # [TWh] kWh/person * person 
    'cooking':            linear_growth(2019,ref_RS_tes_cok               *df_SUF["households [household]"][2019]*1e-9,
                                        2050,trg_RS_tes_cok               *df_SUF["households [household]"][2050]*1e-9,years), # [TWh] kWh/household * household
    }

    # Residential Sector - Electrical Energy Services
    ees_RS_tot = {
    'refrigeration':      linear_with_middle_point(2019,ref_RS_ees_frg*df_SUF["households [household]"][2019]          *1e-9, 
                                         yea_RS_ees_frg,trg_RS_ees_frg*df_SUF["households [household]"][yea_RS_ees_frg]*1e-9, 
                                                   2050,trg_RS_ees_frg*df_SUF["households [household]"][2050]          *1e-9, years), # [TWh] kWh/household * household
    'washing machines':   linear_with_middle_point(2019,ref_RS_ees_wsh*df_SUF["households [household]"][2019]          *1e-9, 
                                         yea_RS_ees_wsh,trg_RS_ees_wsh*df_SUF["households [household]"][yea_RS_ees_wsh]*1e-9, 
                                                   2050,trg_RS_ees_wsh*df_SUF["households [household]"][2050]          *1e-9, years), # [TWh] kWh/household * household
    'laundry dryers':     linear_with_middle_point(2019,ref_RS_ees_dry*df_SUF["households [household]"][2019]          *1e-9, 
                                         yea_RS_ees_dry,trg_RS_ees_dry*df_SUF["households [household]"][yea_RS_ees_dry]*1e-9, 
                                                   2050,trg_RS_ees_dry*df_SUF["households [household]"][2050]          *1e-9, years), # [TWh] kWh/household * household
    'dishwashers':        linear_with_middle_point(2019,ref_RS_ees_dsh*df_SUF["households [household]"][2019]          *1e-9, 
                                         yea_RS_ees_dsh,trg_RS_ees_dsh*df_SUF["households [household]"][yea_RS_ees_dsh]*1e-9, 
                                                   2050,trg_RS_ees_dsh*df_SUF["households [household]"][2050]          *1e-9, years), # [TWh] kWh/household * household
    'TV and multimedia':  linear_with_middle_point(2019,ref_RS_ees_tvm*df_SUF["households [household]"][2019]          *1e-9, 
                                         yea_RS_ees_tvm,trg_RS_ees_tvm*df_SUF["households [household]"][yea_RS_ees_tvm]*1e-9, 
                                                   2050,trg_RS_ees_tvm*df_SUF["households [household]"][2050]          *1e-9, years), # [TWh] kWh/household * household
    'ICT':                linear_with_middle_point(2019,ref_RS_ees_ict*df_SUF["households [household]"][2019]          *1e-9, 
                                         yea_RS_ees_ict,trg_RS_ees_ict*df_SUF["households [household]"][yea_RS_ees_ict]*1e-9, 
                                                   2050,trg_RS_ees_ict*df_SUF["households [household]"][2050]          *1e-9, years), # [TWh] kWh/household * household
    'light':              linear_with_middle_point(2019,ref_RS_ees_lgt*df_SUF["households [household]"][2019]          *1e-9, 
                                         yea_RS_ees_lgt,trg_RS_ees_lgt*df_SUF["households [household]"][yea_RS_ees_lgt]*1e-9, 
                                                   2050,trg_RS_ees_lgt*df_SUF["households [household]"][2050]          *1e-9, years), # [TWh] kWh/household * household
    'others':             linear_with_middle_point(2019,ref_RS_ees_oth*df_SUF["households [household]"][2019]          *1e-9, 
                                         yea_RS_ees_oth,trg_RS_ees_oth*df_SUF["households [household]"][yea_RS_ees_oth]*1e-9, 
                                                   2050,trg_RS_ees_oth*df_SUF["households [household]"][2050]          *1e-9, years), # [TWh] kWh/household * household
    }

    # End-Use Demand: thermal and electical
    tes_RS_tot['heat_ihs']   = [(x+y)*z for x,y,z in zip(tes_RS_tot['space heating'], tes_RS_tot['sanitary hot water'], share_heat_ihs)]
    tes_RS_tot['heat_dhn']   = [(x+y)*z for x,y,z in zip(tes_RS_tot['space heating'], tes_RS_tot['sanitary hot water'], share_heat_dhn)]
    tes_RS_tot['cooking_ng'] = [ x*y    for x,y   in zip(tes_RS_tot['cooking'],                                         share_cook_gas)]
    tes_RS_tot['cooking_el'] = [ x*y    for x,y   in zip(tes_RS_tot['cooking'],                                         share_cook_ele)]
    df_tes_RS_tot = pd.DataFrame(tes_RS_tot, index=years) # [TWh]
    df_ees_RS_tot = pd.DataFrame(ees_RS_tot, index=years) # [TWh]
    # End-Use Demand: carrier distribution
    df_eud_RS_tot_car = {
    'heat-ihs':    df_tes_RS_tot[["heat_ihs"]].T,
    'heat-dhn':    df_tes_RS_tot[["heat_dhn"]].T,
    'cold':        df_tes_RS_tot[["space cooling"]].T,
    'electricity': pd.concat([df_tes_RS_tot[["cooking_el"]], df_ees_RS_tot], axis=1).T,
    'fuel-gas':    df_tes_RS_tot[["cooking_ng"]].T,
    }
    rows = []
    for carrier, df in df_eud_RS_tot_car.items():
      temp = df.copy()
      temp['Carrier'] = carrier
      temp['Activity'] = temp.index
      temp = temp.reset_index(drop=True)
      rows.append(temp)
    df_eud_RS_tot_car = pd.concat(rows, ignore_index=True)
    # Carriers distribution - aggregated per carrier
    df_eud_RS_tot_cln = df_eud_RS_tot_car.groupby('Carrier')[years].sum()
    df_eud_RS_tot_cln = df_eud_RS_tot_cln.reset_index()
    # Carriers distribution - normalisations
    divider_series = df_SUF["households [household]"]
    divider_series.index = divider_series.index.astype(float)
    df_eud_RS_hsd_car = (df_eud_RS_tot_car[years].div(divider_series, axis=1))*1e+9
    df_eud_RS_hsd_car[['Carrier', 'Activity']] = df_eud_RS_tot_car[['Carrier', 'Activity']]

    # Inputs - Repartition of the thermal energy services (TES) in tertiary buildings for the reference year (2019)
    ref_TS_tes_sht = 1862.949*ktoe_to_GWh*1e+6/ref_TS_sur_tot # [kWh/m²]
    ref_TS_tes_scl =  336.272*ktoe_to_GWh*1e+6/ref_TS_sur_tot # [kWh/m²]
    ref_TS_tes_shw =  299.836*ktoe_to_GWh*1e+6/population_dict[2019] # [kWh/person]
    ref_TS_tes_cat =  284.204*ktoe_to_GWh*1e+6/population_dict[2019] # [kWh/person]
    acc_TS_tes_sht_ren = 5
    cur_TS_tes_sht_ren = -0.154 # kWh/m²/year
    trg_TS_tes_sht     = ref_TS_tes_sht + acc_TS_tes_sht_ren*cur_TS_tes_sht_ren*(2050-2019) # [kWh/m²]
    d_cons_temp = 0.07
    d_temp = 1
    suf_TS_tes_sht = 1-d_temp*d_cons_temp
    acc_TS_tes_scl_ren = 1/3
    cur_TS_tes_scl_ren = 0.743 # kWh/m²/year
    trg_TS_tes_scl     = ref_TS_tes_scl + acc_TS_tes_scl_ren*cur_TS_tes_scl_ren*(2050-2019) # [kWh/m²]

    # Inputs - Define Sufficiency Scenario Data (SUF)
    pro_TS_tes_shw     = 0.00
    # Outputs - Sufficiency Scenario Data (SUF)
    trg_TS_tes_shw     = (1+pro_TS_tes_shw)*ref_TS_tes_shw # kWh/person

    # Inputs - Define Sufficiency Scenario Data (SUF)
    pro_TS_tes_cat     = 0.20
    ref_TS_tes_cat_gas = (8.421+106.309)/284.204 # ktoe_gas/ktoe_tot (from JRC-IDEES)
    trg_TS_tes_cat_gas = 0.050
    ref_TS_tes_cat_bio =          1.603 /284.204 # ktoe_bio/ktoe_tot (from JRC-IDEES)
    trg_TS_tes_cat_bio = ref_TS_tes_cat_bio
    # Outputs - Sufficiency Scenario Data (SUF)
    trg_TS_tes_cat     = (1+pro_TS_tes_cat)*ref_TS_tes_cat # kWh/person
    share_ctrg_gas = linear_growth(2019,  ref_TS_tes_cat_gas,
                               2050,  trg_TS_tes_cat_gas,years) # [%]
    share_ctrg_bio = linear_growth(2019,  ref_TS_tes_cat_bio,
                               2050,  trg_TS_tes_cat_bio,years) # [%]
    share_ctrg_ele = linear_growth(2019,1-ref_TS_tes_cat_gas-ref_TS_tes_cat_bio,
                               2050,1-trg_TS_tes_cat_gas-trg_TS_tes_cat_bio,years) # [%]

    ref_TS_tes_dhn = (46.381+5.984)/(1862.949+299.836) # [%] 2019 reference share of district heating network in Belgium from JRC-IDEES
    trg_TS_tes_dhn = 0.15                              # [%] 2050 target    share of district heating network in Belgium from nW-BE
    share_heat_dhn = linear_growth(2019,  ref_TS_tes_dhn,
                               2050,  trg_TS_tes_dhn,years) # [%]
    share_heat_ihs = linear_growth(2019,1-ref_TS_tes_dhn,
                               2050,1-trg_TS_tes_dhn,years) # [%]

    # Inputs - Repartition of the electrical energy services (EES) in tertiary buildings for the reference year (2019)
    ref_TS_ees_vnt =  71.632*ktoe_to_GWh*1e+6/df_SUF["population [person]"][2019] # [kWh/person]
    ref_TS_ees_slt =  77.819*ktoe_to_GWh*1e+6/df_SUF["population [person]"][2019] # [kWh/person]
    ref_TS_ees_blt = 297.768*ktoe_to_GWh*1e+6/df_SUF["population [person]"][2019] # [kWh/person]
    ref_TS_ees_frg = 179.674*ktoe_to_GWh*1e+6/df_SUF["population [person]"][2019] # [kWh/person]
    ref_TS_ees_msc = 176.613*ktoe_to_GWh*1e+6/df_SUF["population [person]"][2019] # [kWh/person]
    ref_TS_ees_ict = 248.983*ktoe_to_GWh*1e+6/df_SUF["population [person]"][2019] # [kWh/person]
    trg_TS_ees_vnt = ref_TS_ees_vnt # [kWh/person]
    # **Street lighting**
    trg_TS_ees_slt = ref_TS_ees_slt-0.476*(2050-2019) # [kWh/person]
    # **Building lighting**
    trg_TS_ees_blt = 150 # [kWh/person]
    # **Commercialrefrigeration**
    pro_TS_ees_frg = -0.15
    trg_TS_ees_frg = (1+pro_TS_ees_frg)*ref_TS_ees_frg # [kWh/person]
    # **Miscellaneous building technologies**
    trg_TS_ees_msc = ref_TS_ees_msc # [kWh/person]
    # **ICT and multimedia** 
    pro_TS_ees_ict = 0.10
    trg_TS_ees_ict = (1+pro_TS_ees_ict)*ref_TS_ees_ict # [kWh/person]

    # Tertiary Sector - Thermal Energy Services
    tes_TS_tot = {
    'space heating':      linear_growth(2019,ref_TS_tes_sht               *df_SUF["TS total surface [Mm²]"][2019]*1e-3,
                                        2050,trg_TS_tes_sht*suf_TS_tes_sht*df_SUF["TS total surface [Mm²]"][2050]*1e-3,years), # [TWh] kWh/m² * m²
    'space cooling':      linear_growth(2019,ref_TS_tes_scl               *df_SUF["TS total surface [Mm²]"][2019]*1e-3,
                                        2050,trg_TS_tes_scl               *df_SUF["TS total surface [Mm²]"][2050]*1e-3,years), # [TWh] kWh/m² * m²
    'sanitary hot water': linear_growth(2019,ref_TS_tes_shw               *df_SUF["population [person]"]   [2019]*1e-9,
                                        2050,trg_TS_tes_shw               *df_SUF["population [person]"]   [2050]*1e-9,years), # [TWh] kWh/person * person 
    'catering':           linear_growth(2019,ref_TS_tes_cat               *df_SUF["population [person]"]   [2019]*1e-9,
                                        2050,trg_TS_tes_cat               *df_SUF["population [person]"]   [2019]*1e-9,years), # [TWh] kWh/person * person
    }

    # Tertiary Sector - Electrical Energy Services
    ees_TS_tot = {
    'ventilation':        linear_growth(2019,           ref_TS_ees_vnt*df_SUF["population [person]"][2019]          *1e-9, 
                                        2050,           trg_TS_ees_vnt*df_SUF["population [person]"][2050]          *1e-9, years), # [TWh] kWh/person * person
    'street lighting':    linear_growth(2019,           ref_TS_ees_slt*df_SUF["population [person]"][2019]          *1e-9, 
                                        2050,           trg_TS_ees_slt*df_SUF["population [person]"][2050]          *1e-9, years), # [TWh] kWh/person * person
    'building lighting':  linear_growth(2019,           ref_TS_ees_blt*df_SUF["population [person]"][2019]          *1e-9, 
                                        2050,           trg_TS_ees_blt*df_SUF["population [person]"][2050]          *1e-9, years), # [TWh] kWh/person * person
    'refrigeration':      linear_growth(2019,           ref_TS_ees_frg*df_SUF["population [person]"][2019]          *1e-9, 
                                        2050,           trg_TS_ees_frg*df_SUF["population [person]"][2050]          *1e-9, years), # [TWh] kWh/person * person
    'miscellaneous':      linear_growth(2019,           ref_TS_ees_msc*df_SUF["population [person]"][2019]          *1e-9, 
                                        2050,           trg_TS_ees_msc*df_SUF["population [person]"][2050]          *1e-9, years), # [TWh] kWh/person * person
    'ICT':                linear_growth(2019,           ref_TS_ees_ict*df_SUF["population [person]"][2019]          *1e-9, 
                                        2050,           trg_TS_ees_ict*df_SUF["population [person]"][2050]          *1e-9, years), # [TWh] kWh/person * person
    }

    # End-Use Demand: thermal and electical
    tes_TS_tot['heat_ihs']   = [(x+y)*z for x,y,z in zip(tes_TS_tot['space heating'], tes_TS_tot['sanitary hot water'], share_heat_ihs)]
    tes_TS_tot['heat_dhn']   = [(x+y)*z for x,y,z in zip(tes_TS_tot['space heating'], tes_TS_tot['sanitary hot water'], share_heat_dhn)]
    tes_TS_tot['cooking_ng'] = [ x*y    for x,y   in zip(tes_TS_tot['catering'],                                        share_ctrg_gas)]
    tes_TS_tot['cooking_bm'] = [ x*y    for x,y   in zip(tes_TS_tot['catering'],                                        share_ctrg_bio)]
    tes_TS_tot['cooking_el'] = [ x*y    for x,y   in zip(tes_TS_tot['catering'],                                        share_ctrg_ele)]
    df_tes_TS_tot = pd.DataFrame(tes_TS_tot, index=years) # [TWh]
    df_ees_TS_tot = pd.DataFrame(ees_TS_tot, index=years) # [TWh]
    # End-Use Demand: carrier distribution
    df_eud_TS_tot_car = {
    'heat-ihs':    df_tes_TS_tot[["heat_ihs"]].T,
    'heat-dhn':    df_tes_TS_tot[["heat_dhn"]].T,
    'cold':        df_tes_TS_tot[["space cooling"]].T,
    'electricity': pd.concat([df_tes_TS_tot[["cooking_el"]], df_ees_TS_tot], axis=1).T,
    'fuel-gas':    df_tes_TS_tot[["cooking_ng"]].T,
	'fuel-bio':    df_tes_TS_tot[["cooking_bm"]].T,
    }
    rows = []
    for carrier, df in df_eud_TS_tot_car.items():
      temp = df.copy()
      temp['Carrier'] = carrier
      temp['Activity'] = temp.index
      temp = temp.reset_index(drop=True)
      rows.append(temp)
    df_eud_TS_tot_car = pd.concat(rows, ignore_index=True)
    # Carriers distribution - aggregated per carrier
    df_eud_TS_tot_cln = df_eud_TS_tot_car.groupby('Carrier')[years].sum()
    df_eud_TS_tot_cln = df_eud_TS_tot_cln.reset_index()
    # Carriers distribution - normalisations
    divider_series = df_SUF["population [person]"]
    divider_series.index = divider_series.index.astype(float)
    df_eud_TS_hsd_car = (df_eud_TS_tot_car[years].div(divider_series, axis=1))*1e+9
    df_eud_TS_hsd_car[['Carrier', 'Activity']] = df_eud_TS_tot_car[['Carrier', 'Activity']]

    # Aggregate global demand data
    df_eud_BS_tot_cln = pd.concat([df_eud_RS_tot_cln, df_eud_TS_tot_cln])
    df_eud_BS_tot_fin = df_eud_BS_tot_cln.groupby('Carrier').sum().reset_index()
    df_eud_BS_tot_fin.loc[ len(df_eud_BS_tot_fin)] = df_eud_BS_tot_fin.sum(numeric_only=True)
    df_eud_BS_tot_fin.iloc[-1, df_eud_BS_tot_fin.columns.get_loc('Carrier')] = 'TOTAL'
    df_eud_BS_tot_fin = df_eud_BS_tot_fin.set_index('Carrier')
    custom_order = [
    'heat-dhn', 
    'heat-ihs', 
    'cold', 
    'electricity', 
    'fuel-gas', 
    'fuel-bio', 
    'TOTAL'
    ]
    df_eud_BS_tot_fin = df_eud_BS_tot_fin.reindex([c for c in custom_order if c in df_eud_BS_tot_fin.index])
    df_eud_BS_tot_fin

    return {
        "residential thermal": df_tes_RS_tot,
        "residential elec": df_ees_RS_tot,
        "tertiary thermal": df_tes_TS_tot,
        "tertiary elec": df_ees_TS_tot,
    }


if __name__ == "__main__":
    if "snakemake" not in globals():
        from scripts._helpers import mock_snakemake

        snakemake = mock_snakemake(
            "update_nW_BE",
            clusters=48,
            planning_horizons=2030,
        )

    config = snakemake.config
    params = snakemake.params.energy
    suff_demand = config.get("sector", {}).get("suff_demand", False)
    year=snakemake.params.energy_totals_year
    country = 'BE'
    planning_horizon = int(snakemake.wildcards.planning_horizons)
    energy_totals = pd.read_csv(snakemake.input.energy_totals, index_col=0)
    if suff_demand:
        clever_totals = pd.read_csv(snakemake.input.clever_Transport, index_col=0)
        results = transport()

        def split_powertrains(df):
            def prep(filter_mask, aggregate=False):
                out = (
                    df[filter_mask]
                    .drop(columns="Powertrain")
                    .set_index("Mode")
                )
                return out.groupby("Mode").sum() if aggregate else out

            return {
                "total": prep(df["Powertrain"] == "TOTAL"),
                "elec": prep(df["Powertrain"] == "electrical"),
                "hyd": prep(df["Powertrain"] == "hydrogen"),
                "oil": prep(
                    ~df["Powertrain"].isin(["TOTAL", "electrical", "hydrogen"]),
                    aggregate=True,
                ),
            }

        mobility = split_powertrains(results["mobility"])
        freight  = split_powertrains(results["freight"])

        df_mobility_total = mobility["total"]
        df_mobility_elec  = mobility["elec"]
        df_mobility_hyd   = mobility["hyd"]
        df_mobility_oil   = mobility["oil"]

        df_freight_total  = freight["total"]
        df_freight_elec   = freight["elec"]
        df_freight_hyd    = freight["hyd"]
        df_freight_oil    = freight["oil"]

        df_transport_total = pd.concat([df_mobility_total, df_freight_total]).groupby(level=0).sum()
        df_transport_elec = pd.concat([df_mobility_elec, df_freight_elec]).groupby(level=0).sum()
        df_transport_hyd = pd.concat([df_mobility_hyd, df_freight_hyd]).groupby(level=0).sum()
        mapping = {
            "bicycle": "total road",
            "bus&coach": "total road",
            "car": "total road",
            "truck-heavy duty": "total road",
            "truck-light commercial": "total road",
            "two-wheeler": "total road",

            "navigation-coastal": "navigation",
            "navigation-inland": "navigation",

            "plane-extra EU": "aviation",
            "plane-intra EU": "aviation",

            "train": "total train",
            "train-conventional": "total train",
            "train-high speed": "total train",
            "tram&metro": "total train",
        }
        df_transport_total.index = df_transport_total.index.to_series().replace(mapping)
        df_transport_total = df_transport_total.groupby(level=0).sum()
        df_transport_elec.index = df_transport_elec.index.to_series().replace(mapping)
        df_transport_elec = df_transport_elec.groupby(level=0).sum()
        df_transport_hyd.index = df_transport_hyd.index.to_series().replace(mapping)
        df_transport_hyd = df_transport_hyd.groupby(level=0).sum()
        
        energy_totals.loc[(energy_totals.index == country) & (energy_totals["year"] == year),"total road"] = df_transport_total.loc["total road", planning_horizon]
        energy_totals.loc[(energy_totals.index == country) & (energy_totals["year"] == year),"electricity road"] = df_transport_elec.loc["total road", planning_horizon]
        energy_totals.loc[(energy_totals.index == country) & (energy_totals["year"] == year),"total rail"] = df_transport_total.loc["total train", planning_horizon]
        energy_totals.loc[(energy_totals.index == country) & (energy_totals["year"] == year),"electricity rail"] = df_transport_elec.loc["total train", planning_horizon]
        energy_totals.loc[(energy_totals.index == country) & (energy_totals["year"] == year),"total international aviation"] = df_transport_total.loc["aviation", planning_horizon]
        energy_totals.loc[(energy_totals.index == country) & (energy_totals["year"] == year),"total domestic navigation"] = df_transport_total.loc["navigation", planning_horizon]

        
        clever_totals.loc[country, "Total_Road"] = df_transport_total.loc["total road", planning_horizon]
        clever_totals.loc[country, "Electricity_Road"] = df_transport_elec.loc["total road", planning_horizon]
        clever_totals.loc[country, "hydrogen_road"] = df_transport_hyd.loc["total road", planning_horizon]
        
        demands = res_ter()
        residential_heat = demands["residential thermal"]
        residential_elec = demands["residential elec"].sum(axis=1).to_frame(name="residential electricity").T
        tertiary_heat = demands["tertiary thermal"]
        tertiary_elec = demands["tertiary elec"].sum(axis=1).to_frame(name="tertiary electricity").T

        residential_heat['residential space heating'] = (
            residential_heat['space heating'] +
            residential_heat['cooking'] +
            residential_heat['space cooling']
        )
        tertiary_heat['tertiary space heating'] = (
            tertiary_heat['space heating'] +
            tertiary_heat['catering'] +
            tertiary_heat['space cooling']
        )
        energy_totals.loc[(energy_totals.index == country) & (energy_totals["year"] == year),"total residential space"] = residential_heat.loc[planning_horizon, "residential space heating"]
        energy_totals.loc[(energy_totals.index == country) & (energy_totals["year"] == year),"total residential water"] = residential_heat.loc[planning_horizon, "sanitary hot water"]
        energy_totals.loc[(energy_totals.index == country) & (energy_totals["year"] == year),"distributed heat residential"] = residential_heat.loc[planning_horizon, "heat_dhn"]
        energy_totals.loc[(energy_totals.index == country) & (energy_totals["year"] == year),"electricity residential"] = residential_elec.loc["residential electricity", planning_horizon]

        energy_totals.loc[(energy_totals.index == country) & (energy_totals["year"] == year),"total services space"] = tertiary_heat.loc[planning_horizon, "tertiary space heating"]
        energy_totals.loc[(energy_totals.index == country) & (energy_totals["year"] == year),"total services water"] = tertiary_heat.loc[planning_horizon, "sanitary hot water"]
        energy_totals.loc[(energy_totals.index == country) & (energy_totals["year"] == year),"distributed heat services"] = tertiary_heat.loc[planning_horizon, "heat_dhn"]
        energy_totals.loc[(energy_totals.index == country) & (energy_totals["year"] == year),"electricity services"] = tertiary_elec.loc["tertiary electricity", planning_horizon]
        
        energy_totals.to_csv(snakemake.output.energy_name)
        clever_totals.to_csv(snakemake.output.clever_name)
    else:
        energy_totals.to_csv(snakemake.output.energy_name)
        pd.DataFrame(index=["BE"]).to_csv(snakemake.output.clever_name)


