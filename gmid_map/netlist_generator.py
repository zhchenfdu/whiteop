# Author: jialinlu
# generate transistor-level circuit netlists with parsered behavioral opamp model

import os
import time
import numpy as np
import matplotlib
import csv
import re
from collections import OrderedDict

matplotlib.use('agg')
import matplotlib.pyplot as plt

from gm_lib import *
import pandas as pd

"""global variables"""
lmin = 1.8e-7  # tsmcrf018
lmax = 5.001e-7  # tsmcrf018
wmin = 1.5e-06  # tsmcrf018
wmax = 8.001e-06  # tsmcrf018
node_vin = 'net_vin'
node_vo = 'net_vo'
node_1 = 'net_1'
node_2 = 'net_2'
gnd = '0'
model_sections = ['tt', 'tt_3v', 'tt_na', 'tt_3vna', 'tt_m', 'tt_3m', 'tt_bip', 'tt_bip3', 'dio', 'dio3', 'dio_dnw',
                  'tt_res', 'tt_mim', 'tt_rfmos', 'tt_rfmos33', 'tt_rfmim', 'tt_rfind', 'tt_rfmvar', 'tt_rfjvar',
                  'tt_rfres_sa', 'tt_rfres_rpo', 'tt_rfres_hri', 'tt_rfesd', 'tt_bbmvar']

model_path = "/path/to/model_path/like/rf018.scs" #replace with your own model path

""" build gmid LUT and calculate W/L """
nmos_lut_path = '/path/to/lut/nmos2v/' #replace with your own lut path
pmos_lut_path = '/path/to/lut/pmos2v/' #replace with your own lut path

# L is 200 points sampled from [0.18u, 2u], because the PDK used is tsmc18rf
L_list = [1.8e-07, 2.17142857142857e-07, 2.54285714285714e-07, 2.91428571428571e-07, 3.28571428571429e-07,
          3.65714285714286e-07, 4.02857142857143e-07, 4.4e-07, 4.77142857142857e-07, 5.14285714285714e-07,
          5.51428571428571e-07, 5.88571428571429e-07, 6.25714285714286e-07, 6.62857142857143e-07, 7e-07,
          7.37142857142857e-07, 7.74285714285714e-07, 8.11428571428572e-07, 8.48571428571429e-07, 8.85714285714286e-07,
          9.22857142857143e-07, 9.6e-07, 9.97142857142857e-07, 1.03428571428571e-06, 1.07142857142857e-06,
          1.10857142857143e-06, 1.14571428571429e-06, 1.18285714285714e-06, 1.22e-06, 1.25714285714286e-06,
          1.29428571428571e-06, 1.33142857142857e-06, 1.36857142857143e-06, 1.40571428571429e-06, 1.44285714285714e-06,
          1.48e-06, 1.51714285714286e-06, 1.55428571428571e-06, 1.59142857142857e-06, 1.62857142857143e-06,
          1.66571428571429e-06, 1.70285714285714e-06, 1.74e-06, 1.77714285714286e-06, 1.81428571428572e-06,
          1.85142857142857e-06, 1.88857142857143e-06, 1.92571428571429e-06, 1.96285714285714e-06, 2e-06]


# load data and build LUT
def replace_col(df, new_col_names, value_names):
    new_df = df
    col_names = df.columns.values
    i_col = 0
    i_new_col = 0
    while i_col < len(col_names):
        new_df.rename(columns={col_names[i_col]: str(new_col_names[i_new_col]) + value_names[0]}, inplace=True)
        new_df.rename(columns={col_names[i_col + 1]: str(new_col_names[i_new_col]) + value_names[1]}, inplace=True)
        i_col += 2
        i_new_col += 1
    return new_df


def read_lut(filename, negative=False):
    # Build index dictionary from raw CSV LUT file
    index_dict = {}

    with open(filename, 'r') as file:
        reader = csv.reader(file)

        # Read header row
        header = next(reader)

        # Iterate over data rows
        for row in reader:
            # Iterate over paired A/B values
            for i in range(0, len(header), 2):
                l_str = header[i]  # String containing L value
                pattern = r'"L"\s+([\d.e+-]+)'
                match = re.search(pattern, l_str)
                l_value = float(match.group(1))

                # If this L value is not in the index dict yet, create a sub-dictionary
                if l_value not in index_dict:
                    index_dict[l_value] = {}

                a_value = float(row[i])      # A value
                b_value = float(row[i + 1])  # B value
                if negative:
                    b_value = -b_value

                # Store A/B pair into nested index dictionary
                index_dict[l_value][a_value] = b_value

    # Sort keys of nested dictionary for deterministic ordering
    sorted_dict = OrderedDict(sorted(index_dict.items()))
    return sorted_dict


def build_lut(nmos_path, pmos_path):
    # read raw data    
    # nmos
    ft_n = read_lut(nmos_path + 'ftn_200.csv')
    # ft_nmos = replace_col(ft_nmos, L_list, ['_gmid', '_ft'])
    ro_n = read_lut(nmos_path + 'ron_200.csv')
    # ro_nmos = replace_col(ro_nmos, L_list, ['_gmid', '_gmro'])
    idw_n = read_lut(nmos_path + 'idwn_200.csv')
    # idw_nmos = replace_col(idw_nmos, L_list, ['_gmid', '_idw'])
    # pmos
    ft_p = read_lut(pmos_path + 'ftp_200.csv')
    # ft_pmos = replace_col(ft_pmos, L_list, ['_gmid', '_ft'])
    ro_p = read_lut(pmos_path + 'rop_200.csv')
    # ro_pmos = replace_col(ro_pmos, L_list, ['_gmid', '_gmro'])
    idw_p = read_lut(pmos_path + 'idwp_200.csv', negative=True)
    # idw_pmos = replace_col(idw_pmos, L_list, ['_gmid', '_idw'])
    '''
    # make column -> L while row(index) -> VGS
    # nmos
    gmid_n = ft_nmos[str(L_list[0]) + '_gmid'].values.tolist()
    ft_n_dict = {}
    ro_n_dict = {}
    idw_n_dict = {}
    for l in L_list:
        ft_n_dict.update({l: pd.Series(ft_nmos[str(l) + '_ft'].values.tolist(), index=gmid_n)})
        ro_n_dict.update({l: pd.Series(ro_nmos[str(l) + '_gmro'].values.tolist(), index=gmid_n)})
        idw_n_dict.update({l: pd.Series(idw_nmos[str(l) + '_idw'].values.tolist(), index=gmid_n)})
    ft_n = pd.DataFrame(ft_n_dict)
    ro_n = pd.DataFrame(ro_n_dict)
    idw_n = pd.DataFrame(idw_n_dict)
    # pmos
    gmid_p = ft_pmos[str(L_list[0]) + '_gmid'].values.tolist()
    ft_p_dict = {}
    ro_p_dict = {}
    idw_p_dict = {}
    for l in L_list:
        ft_p_dict.update({l: pd.Series(ft_pmos[str(l) + '_ft'].values.tolist(), index=gmid_p)})
        ro_p_dict.update({l: pd.Series(ro_pmos[str(l) + '_gmro'].values.tolist(), index=gmid_p)})
        idw_p_dict.update({l: -pd.Series(idw_pmos[str(l) + '_idw'].values.tolist(), index=gmid_p)})
    ft_p = pd.DataFrame(ft_p_dict)
    ro_p = pd.DataFrame(ro_p_dict)
    idw_p = pd.DataFrame(idw_p_dict)
    '''
    return ft_n, ro_n, idw_n, ft_p, ro_p, idw_p


""" generate netlist/netlist4opt/netlistOut/script4simulation """


def get_time():
    times = time.time()
    local_times = time.localtime(times)
    local_time_asctimes = time.asctime(local_times)
    return local_time_asctimes


def map_unit(unit):
    if unit == 'M':
        times = 1e6
    elif unit == 'K':
        times = 1e3
    elif unit == 'm':
        times = 1e-3
    elif unit == 'u':
        times = 1e-6
    elif unit == 'n':
        times = 1e-9
    elif unit == 'p':
        times = 1e-12
    elif unit == 'f':
        times = 1e-15
    else:
        print('[Error] unknown unit !')
    return times


def get_gds(gm_name, circuit_data):
    gds = 0
    #print('circuit_data', circuit_data)
    gm_left_port = circuit_data.loc['left_port'][gm_name]
    gm_right_port = circuit_data.loc['right_port'][gm_name]
    inst_list = circuit_data.columns.values.tolist()
    for inst in inst_list:
        inst_type = circuit_data.loc['type'][inst]
        parasitic = circuit_data.loc['parasitic'][inst]
        left_port = circuit_data.loc['left_port'][inst]
        right_port = circuit_data.loc['right_port'][inst]
        # Match parasitic resistor connected to gm output node and ground
        # Remove dependency on device name containing node name (works for both naming conventions)
        if inst_type == 'resistor' and parasitic == 1 and left_port == gm_right_port and (right_port == '0' or right_port == 'vss'):
            unit = circuit_data.loc['unit'][inst]
            #print('unit', unit)
            times = map_unit(unit)
            ro = circuit_data.loc['value'][inst] * times
            #print('data', circuit_data.loc['value'][inst])
            #print(ro)
            gds = 1 / ro
            break
    if gds == 0:
        print('[Error] {} get gds failed!'.format(gm_name))
    return gds


def remove_invalid_device(inst_list, circuit_data):
    valid_device_list = []
    invalid_port = []
    for inst in inst_list:
        inst_type = circuit_data.loc['type'][inst]
        left_port = circuit_data.loc['left_port'][inst]
        right_port = circuit_data.loc['right_port'][inst]
        parasitic = circuit_data.loc['parasitic'][inst]
        if inst_type == 'capacitor' or inst_type == 'resistor':
            if parasitic == 0 and left_port == 'net_vin' and (not (right_port in ['net_1', 'net_2'])):
                invalid_port.append(right_port)
    invalid_port.append('net_vin')
    for inst in inst_list:
        inst_type = circuit_data.loc['type'][inst]
        left_port = circuit_data.loc['left_port'][inst]
        right_port = circuit_data.loc['right_port'][inst]
        parasitic = circuit_data.loc['parasitic'][inst]
        if inst_type == 'capacitor' or inst_type == 'resistor':
            if parasitic == 0 and (not (left_port in invalid_port)):
                valid_device_list.append(inst)
        else:
            valid_device_list.append(inst)
    return valid_device_list, invalid_port


def _get_gmid_target(param_gmid, gm_index, with_dict, is_nmos=True):
    """
    Helper to fetch gmid target value from param_gmid, supporting two naming schemes:
    - 'gmid_n_X' / 'gmid_p_X'
    - 'gmid_1_X' / 'gmid_2_X'
    """
    if not with_dict or param_gmid is None:
        return None
    # Safely get the first-row value using .iloc[0] (if available)
    if is_nmos:
        key_n = 'gmid_n_' + str(gm_index)
        key_1 = 'gmid_1_' + str(gm_index)
        if key_n in param_gmid.columns:
            return param_gmid[key_n].iloc[0] if len(param_gmid) > 0 else None
        elif key_1 in param_gmid.columns:
            return param_gmid[key_1].iloc[0] if len(param_gmid) > 0 else None
        else:
            return None
    else:
        key_p = 'gmid_p_' + str(gm_index)
        key_2 = 'gmid_2_' + str(gm_index)
        if key_p in param_gmid.columns:
            return param_gmid[key_p].iloc[0] if len(param_gmid) > 0 else None
        elif key_2 in param_gmid.columns:
            return param_gmid[key_2].iloc[0] if len(param_gmid) > 0 else None
        else:
            return None

def generate_netlist(pd_data, param_gmid=None, param_c=None, debug=None):
    if debug == None:
        debug = False
    # build LUT
    ft_n, ro_n, idw_n, ft_p, ro_p, idw_p = build_lut(nmos_lut_path, pmos_lut_path)
    L_list = list(ft_n.keys())
    Lb = 1e-6
    L_bias = L_list[np.argmin(np.abs(np.array(L_list) - Lb))]
    if not os.path.exists('./netlist'):
        os.makedirs('./netlist')
    # os.system('mkdir netlist')
    os.chdir('./netlist')
    netlist_header = open('./netlistHeader', 'w')
    netlist = open('./netlist', 'w')

    # write header
    netlist_header.writelines('// Automated generated for schematic mapping\n')
    netlist_header.writelines('// Generated for: spectre\n')
    local_time = get_time()
    netlist_header.writelines('// Generated on: {}\n'.format(local_time))
    netlist_header.writelines('simulator lang=spectre\n')
    netlist_header.writelines('global 0 vdd! vss!\n')
    netlist_header.writelines('// Header End \n')

    # write gm subckts
    netlist.writelines('// definition of subcircuit\n')
    inst_list = pd_data.columns.values.tolist()
    instance_list, invalid_port = remove_invalid_device(inst_list, pd_data)
    if debug:
        print('[Debug] Invalid RC port detected: {}'.format(invalid_port))
    gm_index = 0
    gm_dict = {}
    gmid_target_dict = {}
    c_target_dict = {}
    #gmid_target_dict.update({'gmid_n_bias': 5})
    #gmid_target_dict.update({'gmid_p_bias': 5})
    gmidTarget_n_bias = 10
    gmidTarget_p_bias = 10
    if param_gmid is None:
        #gmidTarget_n_bias = 5
        #gmidTarget_p_bias = 5
        with_dict = False
        gmid_target_dict.update({'intrinsic_gain_times':1.5})
        intrinsic_gain_times = 1.5
    else:
        #gmidTarget_n_bias = param_gmid['gmid_n_bias'][0]
        #gmidTarget_p_bias = param_gmid['gmid_p_bias'][0]
        with_dict = True
        # 如果param_gmid不包含'intrinsic_gain_times'，使用默认值1.5
        if 'intrinsic_gain_times' in param_gmid.columns:
            intrinsic_gain_times = param_gmid['intrinsic_gain_times'].iloc[0] if len(param_gmid) > 0 else 1.5
        else:
            intrinsic_gain_times = 1.5

    if param_c is None:
        #gmidTarget_n_bias = 5
        #gmidTarget_p_bias = 5
        with_dict_c = False
    else:
        #gmidTarget_n_bias = param_gmid['gmid_n_bias'][0]
        #gmidTarget_p_bias = param_gmid['gmid_p_bias'][0]
        with_dict_c = True
    # rev_mid = True
    for inst in instance_list:
        if pd_data.loc['type'][inst] == 'vccs':
            unit = pd_data.loc['unit'][inst]
            times = map_unit(unit)
            #print('inst', inst)
            
            gm_cal = pd_data.loc['value'][inst] * times
            #print('gm_cal', gm_cal)
            gds_cal = get_gds(inst, pd_data)
            #print('gds_cal', gds_cal)
            left_port = pd_data.loc['left_port'][inst]
            right_port = pd_data.loc['right_port'][inst]
                       
            #print('div', gm_cal/gds_cal)
            if left_port == node_vin:
                if gm_cal > 0:
                    gmidTarget_n = _get_gmid_target(param_gmid, gm_index, with_dict, is_nmos=True)
                    gmidTarget_p = _get_gmid_target(param_gmid, gm_index, with_dict, is_nmos=False)
                    if debug:
                        print('[Debug] gm_index={}, gmidTarget_n={}, gmidTarget_p={}'.format(
                            gm_index, gmidTarget_n, gmidTarget_p))
                    W4, L4, M4, W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0 = cal_positive_diff(
                        intrinsic_gain_times, gm_cal, gds_cal, ft_n, ro_n, idw_n, ft_p, ro_p, idw_p,
                        debug=debug, gmidTarget_n=gmidTarget_n, gmidTarget_p=gmidTarget_p,
                        gmidTarget_n_bias=gmidTarget_n_bias, L_bias=L_bias)
                    gm_name = get_gm_negative_diff(netlist, gm_index, W4, L4, M4, W3, L3, M3, W2, L2, M2,
                                                   W1, L1, M1, W0, L0, M0)
                else:
                    gmidTarget_n = _get_gmid_target(param_gmid, gm_index, with_dict, is_nmos=True)
                    gmidTarget_p = _get_gmid_target(param_gmid, gm_index, with_dict, is_nmos=False)
                    W4, L4, M4, W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0 = cal_positive_diff(
                        intrinsic_gain_times, -1 * gm_cal, gds_cal, ft_n, ro_n, idw_n, ft_p, ro_p, idw_p,
                        debug=None, gmidTarget_n=gmidTarget_n, gmidTarget_p=gmidTarget_p,
                        gmidTarget_n_bias=gmidTarget_n_bias, L_bias=L_bias)
                    gm_name = get_gm_positive_diff(netlist, gm_index, W4, L4, M4, W3, L3, M3, W2, L2, M2,
                                                   W1, L1, M1, W0, L0, M0)
                gm_dict.update({inst: gm_name})
                gmid_target_dict.update({'gmid_n_' + str(gm_index): 15})
                gmid_target_dict.update({'gmid_p_' + str(gm_index): 8})
                if debug:
                    print(
                        '[Debug] {} calculation finished, the corresponding gm_cal is {}, the gds_cal is {}'.format(
                            gm_name, gm_cal, gds_cal))
            else:
                if gm_cal > 0:
                    gmidTarget_p = _get_gmid_target(param_gmid, gm_index, with_dict, is_nmos=False)
                    W1, L1, M1, W0, L0, M0 = cal_positive_mid(intrinsic_gain_times, gm_cal, gds_cal, ft_n,
                                                              ro_n, idw_n, ft_p, ro_p, idw_p, debug=None,
                                                              gmidTarget_p=gmidTarget_p,
                                                              gmidTarget_n_bias=gmidTarget_n_bias, L_bias=L_bias)
                    gm_name = get_gm_positive_mid(netlist, gm_index, W1, L1, M1, W0, L0, M0)
                    gm_dict.update({inst: gm_name})
                    gmid_target_dict.update({'gmid_p_' + str(gm_index): 8})
                    if debug:
                        print(
                            '[Debug] {} calculation finished, the corresponding gm_cal is {}, the gds_cal is {}'.format(
                                gm_name, gm_cal, gds_cal))
                else:
                    gmidTarget_n = _get_gmid_target(param_gmid, gm_index, with_dict, is_nmos=True)
                    gmidTarget_p = _get_gmid_target(param_gmid, gm_index, with_dict, is_nmos=False)
                    W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0 = cal_negative_mid(intrinsic_gain_times,
                                                                                      -1 * gm_cal, gds_cal,
                                                                                      ft_n, ro_n, idw_n,
                                                                                      ft_p, ro_p, idw_p,
                                                                                      debug=None,
                                                                                      gmidTarget_n=gmidTarget_n,
                                                                                      gmidTarget_p=gmidTarget_p,
                                                                                      gmidTarget_p_bias=gmidTarget_p_bias,
                                                                                      L_bias=L_bias)
                    gm_name = get_gm_negative_mid(netlist, gm_index, W3, L3, M3, W2, L2, M2, W1, L1, M1, W0,
                                                  L0, M0)
                    gm_dict.update({inst: gm_name})
                    gmid_target_dict.update({'gmid_n_' + str(gm_index): 15})
                    gmid_target_dict.update({'gmid_p_' + str(gm_index): 8})
                    if debug:
                        print(
                            '[Debug] {} calculation finished, the corresponding gm_cal is {}, the gds_cal is {}'.format(
                                gm_name, gm_cal, gds_cal))
            gm_index += 1
        else:
            pass

    gmid_list_bias_n = list(ft_n[L_bias].keys())
    best_gmid_n = gmid_list_bias_n[np.argmin(np.abs(np.array(gmid_list_bias_n) - gmidTarget_n_bias))]
    best_idw_n = idw_n[L_bias][best_gmid_n]
    gmid_list_bias_p = list(ft_p[L_bias].keys())
    best_gmid_p = gmid_list_bias_p[np.argmin(np.abs(np.array(gmid_list_bias_p) - gmidTarget_n_bias))]
    best_idw_p = idw_p[L_bias][best_gmid_p]
    idn = 6e-6
    idp = 3e-6
    w_bias_n = idn / best_idw_n
    w_bias_p = idp / best_idw_p
    netlist.writelines('// End of subcircuit definition \n')
    netlist.writelines('\n')

    # set the differential input
    netlist.writelines('V1 (vdd! 0) vsource dc=1.8 type=dc\n')
    netlist.writelines('V0 (net_vip 0) vsource dc=900.0m mag=1 type=sine\n')
    netlist.writelines('C0 (net_vin 0) capacitor c=1F \n')
    netlist.writelines('L0 (net_vin {}) inductor l=1G \n'.format(node_vo))
    netlist.writelines('C1 (net_vo 0) capacitor c=10p \n')
    netlist.writelines('R0 (net_vo 0) resistor r=1000000 \n')
    netlist.writelines('ID0 (vdd! net_vb_n) isource dc={} type=dc\n'.format(idn))
    netlist.writelines('M0 (net_vb_n net_vb_n 0 0) nch l={} w={} m=1 \\ \n'.format(L_bias, w_bias_n))
    netlist.writelines(
        '        ad=({w2}*((4.8e-07+((1-1)*5.4e-07)/2+0)*(int((1+1)/2)-int(1/2))+(1/2)*5.4e-07*(int((1+2)/2)-int((1+1)/2)))+((0*0*((1-1)/2+1-0))*(int((1+1)/2)-int(1/2))+(0*0*int(1/2))*(int((1+2)/2)-int((1+1)/2))))/1 \\ \n        as=({w2}*((4.8e-07+((1-1)*5.4e-07)/2+0)*(int((1+1)/2)-int(1/2))+(4.8e-07+4.8e-07+(int(1/2)-1)*5.4e-07+0+0)*(int((1+2)/2)-int((1+1)/2)))+((0*0*((1-1)/2+1-0))*(int((1+1)/2)-int(1/2))+(0*0*(int(1/2)+1-0-0))*(int((1+2)/2)-int((1+1)/2))))/1 \\ \n        pd=(((4.8e-07+((1-1)*5.4e-07)/2+0)*(int((1+1)/2)-int(1/2))+(1/2)*5.4e-07*(int((1+2)/2)-int((1+1)/2)))*2+(((1+1)*(int((1+1)/2)-int(1/2))+(1+0)*(int((1+2)/2)-int((1+1)/2)))-((0*(((1+1)*(int((1+1)/2)-int(1/2))+(1+0)*(int((1+2)/2)-int((1+1)/2)))-0))*(int((1+1)/2)-int(1/2))+(0*((1+1)*(int((1+1)/2)-int(1/2))+(1+0)*(int((1+2)/2)-int((1+1)/2))))*(int((1+2)/2)-int((1+1)/2))))*{w2}+((0*((1-1)/2+1-0))*(int((1+1)/2)-int(1/2))+(0*int(1/2))*(int((1+2)/2)-int((1+1)/2)))*4)/1 \\ \n        ps=(((4.8e-07+((1-1)*5.4e-07)/2+0)*(int((1+1)/2)-int(1/2))+(4.8e-07+4.8e-07+(int(1/2)-1)*5.4e-07+0+0)*(int((1+2)/2)-int((1+1)/2)))*2+(((1+1)*(int((1+1)/2)-int(1/2))+(1+2)*(int((1+2)/2)-int((1+1)/2)))-((0*(((1+1)*(int((1+1)/2)-int(1/2))+(1+2)*(int((1+2)/2)-int((1+1)/2)))-0))*(int((1+1)/2)-int(1/2))+(0*(((1+1)*(int((1+1)/2)-int(1/2))+(1+2)*(int((1+2)/2)-int((1+1)/2)))-0-0))*(int((1+2)/2)-int((1+1)/2))))*{w2}+((0*((1-1)/2+1-0))*(int((1+1)/2)-int(1/2))+(0*(int(1/2)+1-0-0))*(int((1+2)/2)-int((1+1)/2)))*4)/1 \\ \n        nrd=(5.4e-07+2.7e-07*(1*2-2))/1/({w2}*2) \\ \n        nrs=(5.4e-07+2.7e-07*(1*2-2))/1/({w2}*2) \n'.format(
            w2=w_bias_n))
    netlist.writelines('M1 (net_vb_p net_vb_n 0 0) nch l={} w={} m=1 \\ \n'.format(L_bias, w_bias_n/idn*idp))
    netlist.writelines(
        '        ad=({w2}*((4.8e-07+((1-1)*5.4e-07)/2+0)*(int((1+1)/2)-int(1/2))+(1/2)*5.4e-07*(int((1+2)/2)-int((1+1)/2)))+((0*0*((1-1)/2+1-0))*(int((1+1)/2)-int(1/2))+(0*0*int(1/2))*(int((1+2)/2)-int((1+1)/2))))/1 \\ \n        as=({w2}*((4.8e-07+((1-1)*5.4e-07)/2+0)*(int((1+1)/2)-int(1/2))+(4.8e-07+4.8e-07+(int(1/2)-1)*5.4e-07+0+0)*(int((1+2)/2)-int((1+1)/2)))+((0*0*((1-1)/2+1-0))*(int((1+1)/2)-int(1/2))+(0*0*(int(1/2)+1-0-0))*(int((1+2)/2)-int((1+1)/2))))/1 \\ \n        pd=(((4.8e-07+((1-1)*5.4e-07)/2+0)*(int((1+1)/2)-int(1/2))+(1/2)*5.4e-07*(int((1+2)/2)-int((1+1)/2)))*2+(((1+1)*(int((1+1)/2)-int(1/2))+(1+0)*(int((1+2)/2)-int((1+1)/2)))-((0*(((1+1)*(int((1+1)/2)-int(1/2))+(1+0)*(int((1+2)/2)-int((1+1)/2)))-0))*(int((1+1)/2)-int(1/2))+(0*((1+1)*(int((1+1)/2)-int(1/2))+(1+0)*(int((1+2)/2)-int((1+1)/2))))*(int((1+2)/2)-int((1+1)/2))))*{w2}+((0*((1-1)/2+1-0))*(int((1+1)/2)-int(1/2))+(0*int(1/2))*(int((1+2)/2)-int((1+1)/2)))*4)/1 \\ \n        ps=(((4.8e-07+((1-1)*5.4e-07)/2+0)*(int((1+1)/2)-int(1/2))+(4.8e-07+4.8e-07+(int(1/2)-1)*5.4e-07+0+0)*(int((1+2)/2)-int((1+1)/2)))*2+(((1+1)*(int((1+1)/2)-int(1/2))+(1+2)*(int((1+2)/2)-int((1+1)/2)))-((0*(((1+1)*(int((1+1)/2)-int(1/2))+(1+2)*(int((1+2)/2)-int((1+1)/2)))-0))*(int((1+1)/2)-int(1/2))+(0*(((1+1)*(int((1+1)/2)-int(1/2))+(1+2)*(int((1+2)/2)-int((1+1)/2)))-0-0))*(int((1+2)/2)-int((1+1)/2))))*{w2}+((0*((1-1)/2+1-0))*(int((1+1)/2)-int(1/2))+(0*(int(1/2)+1-0-0))*(int((1+2)/2)-int((1+1)/2)))*4)/1 \\ \n        nrd=(5.4e-07+2.7e-07*(1*2-2))/1/({w2}*2) \\ \n        nrs=(5.4e-07+2.7e-07*(1*2-2))/1/({w2}*2) \n'.format(
            w2=w_bias_n))
    netlist.writelines('M2 (net_vb_p net_vb_p vdd! vdd!) pch l={} w={} m=1 \\ \n'.format(L_bias, w_bias_p))
    netlist.writelines(
        '        ad=({w2}*((4.8e-07+((1-1)*5.4e-07)/2+0)*(int((1+1)/2)-int(1/2))+(1/2)*5.4e-07*(int((1+2)/2)-int((1+1)/2)))+((0*0*((1-1)/2+1-0))*(int((1+1)/2)-int(1/2))+(0*0*int(1/2))*(int((1+2)/2)-int((1+1)/2))))/1 \\ \n        as=({w2}*((4.8e-07+((1-1)*5.4e-07)/2+0)*(int((1+1)/2)-int(1/2))+(4.8e-07+4.8e-07+(int(1/2)-1)*5.4e-07+0+0)*(int((1+2)/2)-int((1+1)/2)))+((0*0*((1-1)/2+1-0))*(int((1+1)/2)-int(1/2))+(0*0*(int(1/2)+1-0-0))*(int((1+2)/2)-int((1+1)/2))))/1 \\ \n        pd=(((4.8e-07+((1-1)*5.4e-07)/2+0)*(int((1+1)/2)-int(1/2))+(1/2)*5.4e-07*(int((1+2)/2)-int((1+1)/2)))*2+(((1+1)*(int((1+1)/2)-int(1/2))+(1+0)*(int((1+2)/2)-int((1+1)/2)))-((0*(((1+1)*(int((1+1)/2)-int(1/2))+(1+0)*(int((1+2)/2)-int((1+1)/2)))-0))*(int((1+1)/2)-int(1/2))+(0*((1+1)*(int((1+1)/2)-int(1/2))+(1+0)*(int((1+2)/2)-int((1+1)/2))))*(int((1+2)/2)-int((1+1)/2))))*{w2}+((0*((1-1)/2+1-0))*(int((1+1)/2)-int(1/2))+(0*int(1/2))*(int((1+2)/2)-int((1+1)/2)))*4)/1 \\ \n        ps=(((4.8e-07+((1-1)*5.4e-07)/2+0)*(int((1+1)/2)-int(1/2))+(4.8e-07+4.8e-07+(int(1/2)-1)*5.4e-07+0+0)*(int((1+2)/2)-int((1+1)/2)))*2+(((1+1)*(int((1+1)/2)-int(1/2))+(1+2)*(int((1+2)/2)-int((1+1)/2)))-((0*(((1+1)*(int((1+1)/2)-int(1/2))+(1+2)*(int((1+2)/2)-int((1+1)/2)))-0))*(int((1+1)/2)-int(1/2))+(0*(((1+1)*(int((1+1)/2)-int(1/2))+(1+2)*(int((1+2)/2)-int((1+1)/2)))-0-0))*(int((1+2)/2)-int((1+1)/2))))*{w2}+((0*((1-1)/2+1-0))*(int((1+1)/2)-int(1/2))+(0*(int(1/2)+1-0-0))*(int((1+2)/2)-int((1+1)/2)))*4)/1 \\ \n        nrd=(5.4e-07+2.7e-07*(1*2-2))/1/({w2}*2) \\ \n        nrs=(5.4e-07+2.7e-07*(1*2-2))/1/({w2}*2) \n'.format(
            w2=w_bias_p))

    # netlist.writelines('ID1 (net_vb_p 0) isource dc=10u type=dc\n')
    negative_input = 'net_vin'
    positive_input = 'net_vip'
    # write all instances
    capacitor_index = 2
    resistor_index = 1
    inst_index = 0
    for inst in instance_list:
        inst_type = pd_data.loc['type'][inst]
        left_port = pd_data.loc['left_port'][inst]
        right_port = pd_data.loc['right_port'][inst]
        inst_unit = pd_data.loc['unit'][inst]
        times = map_unit(inst_unit)
        inst_value = pd_data.loc['value'][inst]
        parasitic = pd_data.loc['parasitic'][inst]
        if inst_type == 'capacitor':
            if with_dict_c:
                inst_value = param_c['c_' + str(capacitor_index)].iloc[0] if len(param_c) > 0 else None
            else:
                c_target_dict.update({'c_' + str(capacitor_index): inst_value})
            netlist.writelines(
                'C{} ({} {}) capacitor c={}{}\n'.format(capacitor_index, left_port, right_port, inst_value, inst_unit))
            capacitor_index += 1
        elif inst_type == 'resistor':
            netlist.writelines(
                'R{} ({} {}) resistor r={}{}\n'.format(resistor_index, left_port, right_port, inst_value, inst_unit))
            resistor_index += 1
        elif inst_type == 'vccs':
            inst_name = gm_dict[inst]
            if left_port == node_vin:
                netlist.writelines(
                    'I{} (vdd! {} {} {} 0 net_vb_n) {}\n'.format(inst_index, negative_input, positive_input, right_port,
                                                                 inst_name))
            else:
                gm_cal = inst_value * times
                if gm_cal > 0:
                    netlist.writelines(
                        'I{} (vdd! {} {} 0 net_vb_n) {}\n'.format(inst_index, left_port, right_port, inst_name))
                else:
                    netlist.writelines(
                        'I{} (vdd! {} {} 0 net_vb_p) {}\n'.format(inst_index, left_port, right_port, inst_name))
            inst_index += 1
        else:
            pass
    netlist.writelines('\n')

    netlist_footer = open('./netlistFooter', 'w')
    netlist_footer.writelines('// Footer End')

    netlist_footer.close()
    netlist.close()
    netlist_footer.close()

    os.chdir('..')

    # generate Ocean script for simulation
    generate_simScript()
    return gmid_target_dict, c_target_dict


def generate_netlist_opt_gmid(intrinsic_gain_times, pd_data, param_gmid, debug=None):
    if debug == None:
        debug = False

    # build LUT
    gm_n, gds_n, id_n, gm_p, gds_p, id_p = build_lut(nmos_lut_path, pmos_lut_path)

    os.system('rm -rf netlist')
    os.system('mkdir netlist')
    os.chdir('./netlist')
    netlist_header = open('./netlistHeader', 'w')
    netlist = open('./netlist', 'w')

    # write header
    netlist_header.writelines('// Automated generated for schematic mapping\n')
    netlist_header.writelines('// Generated for: spectre\n')
    local_time = get_time()
    netlist_header.writelines('// Generated on: {}\n'.format(local_time))
    netlist_header.writelines('simulator lang=spectre\n')
    netlist_header.writelines('global 0 vdd! vss!\n')
    netlist_header.writelines('// Header End \n')

    # write gm subckts
    netlist.writelines('// definition of subcircuit\n')
    inst_list = pd_data.columns.values.tolist()
    instance_list, invalid_port = remove_invalid_device(inst_list, pd_data)
    if debug:
        print('[Debug] Invalid RC port detected: {}'.format(invalid_port))
    gm_index = 0
    gm_dict = {}
    for inst in instance_list:
        if pd_data.loc['type'][inst] == 'vccs':
            unit = pd_data.loc['unit'][inst]
            times = map_unit(unit)
            gm_cal = pd_data.loc['value'][inst] * times
            gds_cal = get_gds(inst, pd_data)
            left_port = pd_data.loc['left_port'][inst]
            if left_port == node_vin:
                if gm_cal > 0:
                    gmidTarget_1 = param_gmid['gmid_1_' + str(gm_index)][0]
                    gmidTarget_2 = param_gmid['gmid_2_' + str(gm_index)][0]
                    if debug:
                        print('[Debug] new gmidTarget_1 and gmidTarget_2 are {}, {}'.format(gmidTarget_1, gmidTarget_2))
                    W5, L5, M5, W4, L4, M4, W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0 = cal_positive_diff(
                        intrinsic_gain_times, gm_cal, gds_cal, gm_n, gds_n, id_n, gm_p, gds_p, id_p, debug=debug,
                        gmid_target_1=gmidTarget_1, gmid_target_2=gmidTarget_2)
                    gm_name = get_gm_positive_diff(netlist, gm_index, W5, L5, M5, W4, L4, M4, W3, L3, M3, W2, L2, M2,
                                                   W1, L1, M1, W0, L0, M0)
                    gm_dict.update({inst: gm_name})
                    if debug:
                        print(
                            '[Debug] {} calculation finished, the corresponding gm_cal is {}, the gds_cal is {}'.format(
                                gm_name, gm_cal, gds_cal))
                else:
                    gmidTarget_1 = param_gmid['gmid_1_' + str(gm_index)][0]
                    gmidTarget_2 = param_gmid['gmid_2_' + str(gm_index)][0]
                    if debug:
                        print('[Debug] new gmidTarget_1 and gmidTarget_2 are {}, {}'.format(gmidTarget_1, gmidTarget_2))
                    W5, L5, M5, W4, L4, M4, W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0 = cal_negative_diff(
                        intrinsic_gain_times, -1 * gm_cal, gds_cal, gm_n, gds_n, id_n, gm_p, gds_p, id_p, debug=debug,
                        gmid_target_1=gmidTarget_1, gmid_target_2=gmidTarget_2)
                    gm_name = get_gm_negative_diff(netlist, gm_index, W5, L5, M5, W4, L4, M4, W3, L3, M3, W2, L2, M2,
                                                   W1, L1, M1, W0, L0, M0)
                    gm_dict.update({inst: gm_name})
                    if debug:
                        print(
                            '[Debug] {} calculation finished, the corresponding gm_cal is {}, the gds_cal is {}'.format(
                                gm_name, gm_cal, gds_cal))
            else:
                if gm_cal > 0:
                    gmidTarget_1 = param_gmid['gmid_1_' + str(gm_index)][0]
                    gmidTarget_2 = param_gmid['gmid_2_' + str(gm_index)][0]
                    if debug:
                        print('[Debug] new gmidTarget_1 and gmidTarget_2 are {}, {}'.format(gmidTarget_1, gmidTarget_2))
                    W2, L2, M2, W1, L1, M1, W0, L0, M0 = cal_positive_mid(intrinsic_gain_times, gm_cal, gds_cal, gm_n,
                                                                          gds_n, id_n, gm_p, gds_p, id_p, debug=debug,
                                                                          gmid_target_1=gmidTarget_1,
                                                                          gmid_target_2=gmidTarget_2)
                    gm_name = get_gm_positive_mid(netlist, gm_index, W2, L2, M2, W1, L1, M1, W0, L0, M0)
                    gm_dict.update({inst: gm_name})
                    if debug:
                        print(
                            '[Debug] {} calculation finished, the corresponding gm_cal is {}, the gds_cal is {}'.format(
                                gm_name, gm_cal, gds_cal))
                else:
                    gmidTarget_1 = param_gmid['gmid_1_' + str(gm_index)][0]
                    gmidTarget_2 = param_gmid['gmid_2_' + str(gm_index)][0]
                    if debug:
                        print('[Debug] new gmidTarget_1 and gmidTarget_2 are {}, {}'.format(gmidTarget_1, gmidTarget_2))
                    W4, L4, M4, W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0 = cal_negative_mid(intrinsic_gain_times,
                                                                                                  -1 * gm_cal, gds_cal,
                                                                                                  gm_n, gds_n, id_n,
                                                                                                  gm_p, gds_p, id_p,
                                                                                                  debug=debug,
                                                                                                  gmid_target_1=gmidTarget_1,
                                                                                                  gmid_target_2=gmidTarget_2)
                    gm_name = get_gm_negative_mid(netlist, gm_index, W4, L4, M4, W3, L3, M3, W2, L2, M2, W1, L1, M1, W0,
                                                  L0, M0)
                    gm_dict.update({inst: gm_name})
                    if debug:
                        print(
                            '[Debug] {} calculation finished, the corresponding gm_cal is {}, the gds_cal is {}'.format(
                                gm_name, gm_cal, gds_cal))
            gm_index += 1
        else:
            pass
    netlist.writelines('// End of subcircuit definition \n')
    netlist.writelines('\n')

    # set the differential input
    negative_input = node_vin
    positive_input = 'net_vip'
    netlist.writelines('V0 ({} 0) vsource dc=900.0m mag=1 type=sine\n'.format(positive_input))
    netlist.writelines('V1 (vdd! 0) vsource dc=1.8 type=dc\n')
    netlist.writelines('C0 (net_vin 0) capacitor c=1F \n')
    netlist.writelines('L0 (net_vin {}) inductor l=1G \n'.format(node_vo))
    netlist.writelines('C1 (net_vo 0) capacitor c=10.0p \n')
    netlist.writelines('ID0 (vdd! net_vb_n) isource dc=1u type=dc\n')
    netlist.writelines('ID1 (net_vb_p 0) isource dc=1u type=dc\n')

    # write all instances
    capacitor_index = 2
    resistor_index = 0
    inst_index = 0
    for inst in instance_list:
        inst_type = pd_data.loc['type'][inst]
        left_port = pd_data.loc['left_port'][inst]
        right_port = pd_data.loc['right_port'][inst]
        inst_unit = pd_data.loc['unit'][inst]
        times = map_unit(inst_unit)
        inst_value = pd_data.loc['value'][inst]
        parasitic = pd_data.loc['parasitic'][inst]
        if inst_type == 'capacitor':
            netlist.writelines(
                'C{} ({} {}) capacitor c={}{}\n'.format(capacitor_index, left_port, right_port, inst_value, inst_unit))
            capacitor_index += 1
        elif inst_type == 'resistor':
            netlist.writelines(
                'R{} ({} {}) resistor r={}{}\n'.format(resistor_index, left_port, right_port, inst_value, inst_unit))
            resistor_index += 1
        elif inst_type == 'vccs':
            inst_name = gm_dict[inst]
            if left_port == node_vin:
                netlist.writelines(
                    'I{} (vdd! {} {} {} 0 net_vb_n) {}\n'.format(inst_index, negative_input, positive_input, right_port,
                                                                 inst_name))
            else:
                gm_cal = inst_value * times
                if gm_cal > 0:
                    netlist.writelines(
                        'I{} (vdd! {} {} 0 net_vb_n) {}\n'.format(inst_index, left_port, right_port, inst_name))
                else:
                    netlist.writelines(
                        'I{} (vdd! {} {} 0 net_vb_p) {}\n'.format(inst_index, left_port, right_port, inst_name))
            inst_index += 1
        else:
            pass
    netlist.writelines('\n')

    netlist_footer = open('./netlistFooter', 'w')
    netlist_footer.writelines('// Footer End')

    netlist_footer.close()
    netlist.close()
    netlist_footer.close()

    os.chdir('..')

    # generate Ocean script for simulation
    generate_simScript()


def generate_simScript():
    script = open('./sim_opamp.ocn', 'w')
    script.writelines('simulator( \'spectre )\n')
    script.writelines('design(	 \"./netlist/netlist\")\n')
    script.writelines('resultsDir( \"./sim_results\" )\n')
    script.writelines('modelFile( \n')
    for section in model_sections:
        script.writelines('    \'(\"{}\" "{}")\n'.format(model_path, section))
    script.writelines(')\n')
    script.writelines('analysis(\'dc ?saveOppoint t  )\n')  # perform dc simulation
    script.writelines('analysis(\'ac ?start \"1\"  ?stop \"10G\"  ?dec \"100\"  )\n')  # perform ac simulation
    script.writelines('envOption(	\'analysisOrder  list(\"dc\" \"ac\") )\n')
    script.writelines('option( ?categ \'turboOpts        \'uniMode  \"APS\")\n')
    script.writelines('saveOption( \'save \"all\" )\n')
    script.writelines('temp( 27 )\n')
    script.writelines('run()\n')
    script.writelines('gain = value(db(vfreq(\'ac \"{}\")) 1)\n'.format(node_vo))
    script.writelines('pm = phaseMargin(VF(\"{}\"))\n'.format(node_vo))
    script.writelines('gbw = cross(db(vfreq(\'ac \"{}\")) 0 1 \"either\" nil nil)\n'.format(
        node_vo))  # script.writelines('gbw = unityGainFreq(db(vfreq(\'ac \"{}\")))\n'.format(node_vo))
    script.writelines('pw = abs(OP("V1" "pwr"))\n')
    script.writelines('ph = phaseDegUnwrapped(value(VF(\"{}\") 1))\n'.format(node_vo))
    # write out simulation results && exit
    script.writelines(
        'ocnPrint(?output \"./sim.out\", ?precision 16 ?width 20 ?numberNotation \'scientific gain pm gbw pw ph)\n')
    script.writelines('exit\n')


def generate_netlist_lvs(pd_data, debug=None):
    # for lvs, we must generate cdl format netlist here
    if debug==None:
        debug = False
    intrinsic_gain_times = 1.5
    gmidTarget_n_bias = 10
    gmidTarget_p_bias = 10
    # build LUT
    ft_n, ro_n, idw_n, ft_p, ro_p, idw_p = build_lut(nmos_lut_path, pmos_lut_path)
    L_list = list(ft_n.keys())
    Lb = 1e-6
    L_bias = L_list[np.argmin(np.abs(np.array(L_list) - Lb))]
    netlist = open('./netlist_lvs', 'w')
    circuit_name = pd_data.loc['circuit_name'][0]
    local_time = get_time()

    netlist.writelines('****************************************************************************\n')
    netlist.writelines('* auCdl Netlist:\n')
    netlist.writelines('* \n')
    netlist.writelines('* Library Name: OPAMP\n')
    netlist.writelines('* Top Cell Name: OPAMP_{}\n'.format(circuit_name.upper()))
    netlist.writelines('* View Name: schematic\n')
    netlist.writelines('* Netlisted on: {}\n'.format(local_time))
    netlist.writelines('****************************************************************************\n')
    netlist.writelines('*.BIPOLAR\n*.RESI = 2000\n*.RESVAL\n*.CAPVAL\n*.DIOPERI\n*.DIOAREA\n*.EQUATION\n*.SCALE METER\n*.MEGA\n')
    netlist.writelines('\n')
    netlist.writelines('\n')

    # write gm subckts
    inst_list = pd_data.columns.values.tolist()
    instance_list, invalid_port = remove_invalid_device(inst_list, pd_data)
    if debug:
        print('[Debug] Invalid RC port detected: {}'.format(invalid_port))
    gm_index = 0

    netlist.writelines('****************************************************************************\n')
    netlist.writelines('* Library Name: OPAMP\n')
    netlist.writelines('* Cell Name: OPAMP_{}\n'.format(circuit_name.upper()))
    netlist.writelines('* View Name: schematic\n')
    netlist.writelines('****************************************************************************\n')
    netlist.writelines('.SUBCKT OPAMP_{} VDD GND NET_VIP NET_VIN NET_VO NET_VB_N NET_VB_P\n'.format(circuit_name.upper()))

    # set the differential input
    negative_input = 'NET_VIN'
    positive_input = 'NET_VIP'

    # write all instances
    capacitor_index = 2
    resistor_index  = 0
    inst_index      = 0
    for inst in instance_list:
        inst_type = pd_data.loc['type'][inst]
        left_port = pd_data.loc['left_port'][inst].upper()
        right_port = pd_data.loc['right_port'][inst].upper()
        inst_unit = pd_data.loc['unit'][inst]
        inst_value = pd_data.loc['value'][inst]
        parasitic = pd_data.loc['parasitic'][inst]
        if inst_type == 'capacitor':
            if (left_port == '0') or (left_port =='vss'):
                left_port = 'GND'
            if (right_port == '0') or (right_port =='vss'):
                right_port = 'GND'
            if left_port == 'vdd!':
                left_port = 'VDD'
            if right_port == 'vdd!':
                right_port = 'VDD'
            l, w, c_new = get_cap_size(inst_value, inst_unit, left_port, right_port)
            netlist.writelines('C_{} {} {} {}{} m=1 $.MODEL=M5\n'.format(capacitor_index, left_port, right_port, inst_value, inst_unit))
            capacitor_index += 1
        elif inst_type == 'resistor':
            if (left_port == '0') or (left_port =='vss'):
                left_port = 'GND'
            if (right_port == '0') or (right_port =='vss'):
                right_port = 'GND'
            if left_port == 'vdd!':
                left_port = 'VDD'
            if right_port == 'vdd!':
                right_port = 'VDD'
            l, w, seg, r_new = get_res_size(inst_value, inst_unit)
            netlist.writelines('R_{} {} {} {}{} m=1 $.MODEL=LR\n'.format(resistor_index, left_port, right_port, inst_value, inst_unit))
            resistor_index += 1
        elif inst_type == 'vccs':
            times = map_unit(inst_unit)
            gm_cal = pd_data.loc['value'][inst] * times
            gds_cal = get_gds(inst, pd_data)
            if left_port == 'NET_VIN':
                if gm_cal > 0:
                    W4, L4, M4, W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0 = cal_positive_diff(
                        intrinsic_gain_times, gm_cal, gds_cal, ft_n, ro_n, idw_n, ft_p, ro_p, idw_p,
                        debug=None, gmidTarget_n=None, gmidTarget_p=None,
                        gmidTarget_n_bias=gmidTarget_n_bias, L_bias=L_bias)
                    gm_name = get_gm_negative_diff_lvs(netlist, gm_index, 'VDD', negative_input, positive_input, right_port, 'GND', 'NET_VB_N', W4, L4, M4, W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0)
                else:
                    W4, L4, M4, W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0 = cal_positive_diff(
                        intrinsic_gain_times, -1 * gm_cal, gds_cal, ft_n, ro_n, idw_n, ft_p, ro_p, idw_p,
                        debug=None, gmidTarget_n=None, gmidTarget_p=None,
                        gmidTarget_n_bias=gmidTarget_n_bias, L_bias=L_bias)
                    gm_name = get_gm_positive_diff_lvs(netlist, gm_index, 'VDD', negative_input, positive_input, right_port, 'GND', 'NET_VB_N', W4, L4, M4, W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0)
            else:
                if gm_cal > 0:
                    W1, L1, M1, W0, L0, M0 = cal_positive_mid(intrinsic_gain_times, gm_cal, gds_cal, ft_n,
                                                              ro_n, idw_n, ft_p, ro_p, idw_p, debug=None,
                                                              gmidTarget_p=None,
                                                              gmidTarget_n_bias=gmidTarget_n_bias, L_bias=L_bias)
                    gm_name = get_gm_negative_mid_lvs(netlist, gm_index, 'VDD', left_port, right_port, 'GND', 'NET_VB_N', W1, L1, M1, W0, L0, M0)
                else:
                    W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0 = cal_negative_mid(intrinsic_gain_times,
                                                                                      -1 * gm_cal, gds_cal,
                                                                                      ft_n, ro_n, idw_n,
                                                                                      ft_p, ro_p, idw_p,
                                                                                      debug=None,
                                                                                      gmidTarget_n=None,
                                                                                      gmidTarget_p=None,
                                                                                      gmidTarget_p_bias=gmidTarget_p_bias,
                                                                                      L_bias=L_bias)
                    gm_name = get_gm_positive_mid_lvs(netlist, gm_index, 'VDD', left_port, right_port, 'GND', 'NET_VB_P', W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0)
            gm_index += 1
        else:
            pass
    netlist.writelines('.ENDS\n')
    netlist.writelines('\n')
    netlist.writelines('\n')

def generate_netlistOut(pd_data):
    intrinsic_gain_times = 1.5
    all_param_dict = {}
    gmid_target_dict = {}
    ft_n, ro_n, idw_n, ft_p, ro_p, idw_p = build_lut(nmos_lut_path, pmos_lut_path)
    L_list = list(ft_n.keys())
    Lb = 1e-6
    L_bias = L_list[np.argmin(np.abs(np.array(L_list) - Lb))]
    #gm_n, gds_n, id_n, gm_p, gds_p, id_p = build_lut(nmos_lut_path, pmos_lut_path)
    inst_list = pd_data.columns.values.tolist()
    instance_list, invalid_port = remove_invalid_device(inst_list, pd_data)
    gm_index = 0
    os.system('mkdir netlist_Out')
    os.chdir('./netlist_Out')

    circuit_name = pd_data.loc['circuit_name'][0]

    manualcons_file = open('manualcons','w') # constraint file
    M_index = 1 # match groups
    S_index = 1 # symmetry groups
    P_index = 1 # proximity groups

    netlistOut = open('netlistout','w') # netlistout file
    netlistOut.writelines('lib_name: OPAMP\n')
    netlistOut.writelines('cell_name: OPAMP_{}\n'.format(circuit_name.upper()))
    netlistOut.writelines('pins: ["VDD", "GND", "NET_VIP", "NET_VIN", "NET_VO", "NET_VB_N", "NET_VB_P"]\n')
    netlistOut.writelines('instances:\n')

    netlistOut_file = open('netlistout.simp','w') # netlistout.simp file
    netlistOut_file.writelines('cell_name: OPAMP_{}\n'.format(circuit_name.upper()))
    netlistOut_file.writelines('instances:\n')

    # set the differential input
    negative_input = 'NET_VIN'
    positive_input = 'NET_VIP'

    gmidTarget_n_bias = 10
    gmidTarget_p_bias = 10

    # write all instances
    capacitor_index = 2
    resistor_index  = 0
    gm_index        = 0
    r_list          = []
    c_list          = []
    for inst in instance_list:
        inst_type = pd_data.loc['type'][inst]
        left_port = pd_data.loc['left_port'][inst].upper()
        right_port = pd_data.loc['right_port'][inst].upper()
        inst_unit = pd_data.loc['unit'][inst]
        inst_value = pd_data.loc['value'][inst]
        parasitic = pd_data.loc['parasitic'][inst]
        if inst_type == 'capacitor':
            c_list.append('C_' + str(capacitor_index))
            gen_c_out(netlistOut, netlistOut_file, 'C_' + str(capacitor_index), left_port, right_port, inst_value,
                      inst_unit)
            capacitor_index += 1
        elif inst_type == 'resistor':
            r_list.append('R_' + str(resistor_index))
            gen_r_out(netlistOut, netlistOut_file, 'R_' + str(resistor_index), left_port, right_port, inst_value,
                      inst_unit)
            resistor_index += 1
        elif inst_type == 'vccs':
            times = map_unit(inst_unit)
            gm_cal = pd_data.loc['value'][inst] * times
            gds_cal = get_gds(inst, pd_data)
            if left_port == 'NET_VIN':
                if gm_cal > 0:
                    W4, L4, M4, W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0 = cal_positive_diff(
                        intrinsic_gain_times, gm_cal, gds_cal, ft_n, ro_n, idw_n, ft_p, ro_p, idw_p,
                        debug=None, gmidTarget_n=None, gmidTarget_p=None,
                        gmidTarget_n_bias=gmidTarget_n_bias, L_bias=L_bias)
                    gen_negative_diff_out(circuit_name, all_param_dict, M_index, S_index, manualcons_file, netlistOut,
                                          netlistOut_file, gm_index, "vdd!", negative_input, positive_input, right_port,
                                          'vss', 'NET_VB_N', W4, L4, M4, W3, L3, M3, W2, L2, M2, W1, L1, M1,
                                          W0, L0, M0)                  
                else:
                    W4, L4, M4, W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0 = cal_positive_diff(
                        intrinsic_gain_times, -1 * gm_cal, gds_cal, ft_n, ro_n, idw_n, ft_p, ro_p, idw_p,
                        debug=None, gmidTarget_n=None, gmidTarget_p=None,
                        gmidTarget_n_bias=gmidTarget_n_bias, L_bias=L_bias)
                    gen_positive_diff_out(circuit_name, all_param_dict, M_index, S_index, manualcons_file, netlistOut,
                                          netlistOut_file, gm_index, 'vdd!', negative_input, positive_input, right_port,
                                          'vss', 'NET_VB_N', W4, L4, M4, W3, L3, M3, W2, L2, M2, W1, L1, M1,
                                          W0, L0, M0)
                gmid_target_dict.update({'gmid_1_' + str(gm_index): 15})
                gmid_target_dict.update({'gmid_2_' + str(gm_index): 8})
                M_index += 2
                S_index += 1
            else:
                if gm_cal > 0:
                    W1, L1, M1, W0, L0, M0 = cal_positive_mid(intrinsic_gain_times, gm_cal, gds_cal, ft_n,
                                                              ro_n, idw_n, ft_p, ro_p, idw_p, debug=None,
                                                              gmidTarget_p=None,
                                                              gmidTarget_n_bias=gmidTarget_n_bias, L_bias=L_bias)
                    gen_negative_mid_out(circuit_name, all_param_dict, M_index, S_index, manualcons_file, netlistOut,
                                         netlistOut_file, gm_index, 'vdd!', left_port, right_port, 'vss', 'NET_VB_N',
                                         W1, L1, M1, W0, L0, M0)
                    
                    S_index += 1
                else:
                    W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0 = cal_negative_mid(intrinsic_gain_times,
                                                                                      -1 * gm_cal, gds_cal,
                                                                                      ft_n, ro_n, idw_n,
                                                                                      ft_p, ro_p, idw_p,
                                                                                      debug=None,
                                                                                      gmidTarget_n=None,
                                                                                      gmidTarget_p=None,
                                                                                      gmidTarget_p_bias=gmidTarget_p_bias,
                                                                                      L_bias=L_bias)
                    gen_positive_mid_out(circuit_name, all_param_dict, M_index, S_index, manualcons_file, netlistOut,
                                         netlistOut_file, gm_index, 'vdd!', left_port, right_port, 'vss', 'NET_VB_P',
                                         W3, L3, M3, W2, L2, M2, W1, L1, M1, W0, L0, M0)
                    M_index += 2
                    S_index += 1
                gmid_target_dict.update({'gmid_1_' + str(gm_index): 15})
                gmid_target_dict.update({'gmid_2_' + str(gm_index): 8})
            gm_index += 1
        else:
            pass

    netlistOut_file.writelines('lib_name: OPAMP\n')
    netlistOut_file.writelines('pins:\n- VDD\n- GND\n- NET_VIP\n- NET_VIN\n- NET_VO\n- NET_VB_N\n- NET_VB_P\n')

    pins_list = ['PIN0', 'PIN1', 'PIN2', 'PIN3', 'PIN4', 'PIN5', 'PIN6']
    for pin in pins_list:
        netlistOut.writelines('  {}:\n'.format(pin))
        netlistOut.writelines('    lib_name: basic\n')
        netlistOut.writelines('    cell_name: iopin\n')
        netlistOut.writelines('    instpins: {}\n')
        netlistOut.writelines('    master_prop:\n')
        netlistOut.writelines('    inst_prop:\n')

    S = 1
    manualcons_file.writelines('M{} '.format(M_index))
    while S < S_index:
        manualcons_file.writelines('S{} '.format(S))
        S += 1
    manualcons_file.writelines('\n')
    manualcons_file.writelines('M{} '.format(M_index + 1))
    for r in r_list:
        manualcons_file.writelines('OPAMP_{}_{} '.format(circuit_name.upper(), r))
    for c in c_list:
        manualcons_file.writelines('OPAMP_{}_{} '.format(circuit_name.upper(), c))
    manualcons_file.writelines('\n')
    manualcons_file.writelines('S{} M{} M{} \n'.format(S_index, M_index, M_index + 1))

    netlistOut.close()
    netlistOut_file.close()
    manualcons_file.close()

    generate_netlist_lvs(pd_data, debug=None)  # netlist file for lvs

    return all_param_dict, gmid_target_dict

if __name__ == '__main__':
    """check simulation script generation"""
    # generate_simScript()

    """check the size cal"""
    # gm_n, gds_n, id_n, gm_p, gds_p, id_p = build_lut(nmos_lut_path, pmos_lut_path)

    # W5, L5, W4, L4, W3, L3, W2, L2, W1, L1, W0, L0 = cal_positive_diff(gm_cal, gds_cal, gm_n, gds_n, id_n, gm_p, gds_p, id_p)
    # print(W5, L5, W4, L4, W3, L3, W2, L2, W1, L1, W0, L0)
    # W2, L2, W1, L1, W0, L0 = cal_positive_mid(gm_cal, gds_cal, gm_n, gds_n, id_n, gm_p, gds_p, id_p)
    # print(W2, L2, W1, L1, W0, L0)
    # W5, L5, W4, L4, W3, L3, W2, L2, W1, L1, W0, L0 = cal_negative_diff(gm_cal, gds_cal, gm_n, gds_n, id_n, gm_p, gds_p, id_p)
    # print(W5, L5, W4, L4, W3, L3, W2, L2, W1, L1, W0, L0)
    # W4, L4, W3, L3, W2, L2, W1, L1, W0, L0 = cal_negative_mid(gm_cal, gds_cal, gm_n, gds_n, id_n, gm_p, gds_p, id_p)
    # print(W4, L4, W3, L3, W2, L2, W1, L1, W0, L0)

    """check the LUT building"""
    # gm_n, gds_n, id_n, gm_p, gds_p, id_p = build_lut(nmos_lut_path, pmos_lut_path)

    """check the raw data"""
    gm_nmos = pd.read_csv(nmos_lut_path + 'gm.csv')
    gm_nmos = replace_col(gm_nmos, L_list, ['_vgs', '_gm'])
    ro_nmos = pd.read_csv(nmos_lut_path + 'ro.csv')
    ro_nmos = replace_col(ro_nmos, L_list, ['_vgs', '_ro'])
    id_nmos = pd.read_csv(nmos_lut_path + 'id.csv')
    id_nmos = replace_col(id_nmos, L_list, ['_vgs', '_id'])

    gm_pmos = pd.read_csv(nmos_lut_path + 'gm.csv')
    gm_pmos = replace_col(gm_pmos, L_list, ['_vgs', '_gm'])
    ro_pmos = pd.read_csv(nmos_lut_path + 'ro.csv')
    ro_pmos = replace_col(ro_pmos, L_list, ['_vgs', '_ro'])
    id_pmos = pd.read_csv(nmos_lut_path + 'id.csv')
    id_pmos = replace_col(id_pmos, L_list, ['_vgs', '_id'])

    L_test = [1.8e-07, 2.07437185929648e-07, 4.08643216080402e-07, 6.0070351758794e-07, 8.01909547738694e-07,
              1.00311557788945e-06, 1.2043216080402e-06, 1.40552763819095e-06, 1.6067336683417e-06,
              1.80793969849245e-06, 2e-06]

    fig = plt.figure()
    for l in L_test:
        gm = gm_nmos[str(l) + '_gm'].values.tolist()
        ro = ro_nmos[str(l) + '_ro'].values.tolist()
        id = id_nmos[str(l) + '_id'].values.tolist()
        plt.xticks([1e-11, 1e-10, 1e-9, 1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3])
        plt.plot(id, list(np.array(gm) / np.array(id)))
        plt.xscale('log')
    plt.savefig('./id.png')

    fig = plt.figure()
    for l in L_test:
        gm = gm_nmos[str(l) + '_gm'].values.tolist()
        ro = ro_nmos[str(l) + '_ro'].values.tolist()
        id = id_nmos[str(l) + '_id'].values.tolist()
        plt.plot(list(np.array(gm) / np.array(id)), list(np.array(gm) / np.array(ro)))
    plt.savefig('./gm_gds.png')

    fig = plt.figure()
    for l in L_list:
        vgs = gm_nmos[str(l) + '_vgs'].values.tolist()
        gm = gm_nmos[str(l) + '_gm'].values.tolist()
        plt.plot(vgs, gm)
    plt.xlabel('VGS(V)')
    plt.ylabel('gm(S)')
    plt.savefig('./gm.png')

    fig = plt.figure()
    for l in L_list:
        vgs = ro_nmos[str(l) + '_vgs'].values.tolist()
        ro = ro_nmos[str(l) + '_ro'].values.tolist()
        plt.plot(vgs, ro)
    plt.xlabel('VGS(V)')
    plt.ylabel('ro(S)')
    plt.savefig('./ro.png')

    fig = plt.figure()
    for l in L_list:
        vgs = id_nmos[str(l) + '_vgs'].values.tolist()
        id = id_nmos[str(l) + '_id'].values.tolist()
        plt.plot(vgs, id)
    plt.xlabel('VGS(V)')
    plt.ylabel('id(A)')
    plt.savefig('./id.png')
