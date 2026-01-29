# Author: jialinlu

from pydoc import stripid
import re
import pandas as pd
import numpy as np
import os

from hebo.design_space.design_space import DesignSpace
from hebo.optimizers.hebo import HEBO
from hebo.optimizers.general import GeneralBO
from pymoo.util.dominator import Dominator

from netlist_generator import get_time, generate_netlist, generate_netlist_opt_gmid, generate_simScript, wmax, wmin

""" about the unit """
# 1m = 1e-3, 1u = 1e-6, 1n = 1e-9, 1p = 1e-12, 1f = 1e-15
# 1M = 1e6,  1G = 1e9
# gm:S, gds:S, id:A, vgs:V
# W/L after calculation: m (meter)

""" useful functions for mapping and simulation """


def parse_param(param_path):
    param_dict = {}
    param_file = open(param_path, 'r')
    param_lines = param_file.readlines()
    for line in param_lines:
        line = line.strip()
        match = re.search(r'^\S+\s+(\S+)\s+\S+\s+(\S+)$', line)
        device_name = match.groups()[0]
        device_value = match.groups()[1]
        param_dict.update({device_name: float(device_value)})
    return param_dict


def macth_device(netlist_line):
    parasitic = 0
    line = netlist_line.strip()
    print(line)
    match1 = re.search(r'^([Gg][_]?\S+)\s+[(](\S+)\s+0\s+(\S+)\s+0[)]\s+(\S+)\s+(\S+)$', line)
    match2 = re.search(r'^([RrCc][_]?\S+)\s+[(](\S+)\s+(\S+)[)]\s+(\S+)\s+(\S+)$', line)
    if match1:
        device_name = match1.groups()[0]
        left_port = match1.groups()[2]  # pay attention to the port direction of vccs here
        right_port = match1.groups()[1]
        device_type = match1.groups()[3]
        device_exp = match1.groups()[4]
    elif match2:
        device_name = match2.groups()[0]
        left_port = match2.groups()[1]
        right_port = match2.groups()[2]
        device_type = match2.groups()[3]
        device_exp = match2.groups()[4]
    else:
        print('[Error] can not match any device !')
        raise ValueError(f'Cannot parse device from line: {line}')

    match_prs1 = re.search(r'^\S+prs*', device_name)
    match_prs2 = re.search(r'^\S+_0\d', device_name)
    match_prs3 = re.search(r'^\S+_L\d', device_name)
    if match_prs1 or match_prs2 or match_prs3:
        parasitic = 1

    return device_name, device_type, device_exp, left_port, right_port, parasitic


def cal_device_value(dev_exp, param_dic):
    match1 = re.search(r'^\S+=(\S+)[/](\S+)[*](\S+)$', dev_exp)
    match11 = re.search(r'^\S+=(\S+)[/](\d.\d+)[*](\S+)$', dev_exp)
    match2 = re.search(r'^\S+=(\S+)[*](\S+)$', dev_exp)
    match22 = re.search(r'^\S+=(\S+)([M,n,p])$', dev_exp)
    # match11 must be matched before match1
    if match11:
        value = param_dic[match1.groups()[0]] / eval(match1.groups()[1])
        times_unit = match1.groups()[2]
    elif match1:
        value = param_dic[match1.groups()[0]] / param_dic[match1.groups()[1]]
        times_unit = match1.groups()[2]
    elif match2:
        value = param_dic[match2.groups()[0]]
        times_unit = match2.groups()[1]
    elif match22:
        value = float(match22.groups()[0])
        times_unit = match22.groups()[1]
    else:
        print('[Error] device value parse failed1 !')

    match3 = re.search(r'^-(\d)([M,K,m,p,n])$', times_unit)
    match4 = re.search(r'^(\d)([M,K,m,p,n])$', times_unit)
    match5 = re.search(r'^([M,n,p])$', times_unit)
    print(match3, match4, match5)
    if match3:
        value = value * float(match3.groups()[0]) * -1
        unit = match3.groups()[1]
    elif match4:
        value = value * float(match4.groups()[0])
        unit = match4.groups()[1]
    elif match5:
        value = value
        unit = match5.groups()[0]
    else:
        print('[Error] device value parse failed2 !')

    return round(value, 12), unit
    # return value, unit


def parse_behavioral_model(circuit, device_features, param_path, netlist_path):
    circuit_dict = {}
    param_dict = parse_param(param_path)
    netlist_file = open(netlist_path, 'r')
    netlist_lines = netlist_file.readlines()
    for netlist_line in netlist_lines[1:]:  # not include vsource
        device_name, device_type, device_exp, left_port, right_port, parasitic = macth_device(netlist_line)
        device_value, device_unit = cal_device_value(device_exp, param_dict)
        # # limit the size of non-parasitic resistors and capacitors
        # if parasitic!=1 and device_type=='capacitor':
        #     if device_value > 0.5:
        #         device_value = 0.5
        #     elif device_value < 0.03:
        #         device_value = 0.03
        #     else:
        #         pass
        # elif parasitic!=1 and device_type=='resistor':
        #     if device_value > 9.8:
        #         device_value = 10.4551
        #     else:
        #         pass
        # potential loss of performance
        # re-optimizing RC may make more sense
        # or modify the bound of RC during behavioral level optimization
        dev_features = [device_type, device_value, device_unit, left_port, right_port, parasitic, circuit]
        circuit_dict.update({device_name: pd.Series(dev_features, index=device_features)})
    return circuit_dict


def sim_and_getRes(circuit_name, gain_target=100.0, pm_lower=55.0, pm_upper=65.0, 
                   gbw_target=0.7, power_target=1000.0, c_load=10.0):
    """
    Simulate circuit and calculate optimization results.
    
    Args:
        circuit_name: Name of the circuit
        gain_target: Gain target value in dB (default: 100.0)
        pm_lower: Phase margin lower bound in deg (default: 55.0)
        pm_upper: Phase margin upper bound in deg (default: 65.0)
        gbw_target: Gain bandwidth product target in MHz (default: 0.7)
        power_target: Power target value in uW (default: 1000.0)
        c_load: Load capacitance in pF (default: 10.0)
    
    Returns:
        res: Array containing [goal, prb_constr0, prb_constr1_lower, prb_constr1_upper, prb_constr2, prb_constr3]
        physical_values: Dictionary containing physical values
    """
    # clear logs
    os.system('rm -rf err sim.* psf sim_results .cadence')
    os.system('rm -rf ~/CDS.log*')
    os.chdir('netlist')
    os.system('rm -rf artSimEnvLog input.scs runSimulation')
    os.chdir('..')
    print('[Info] simulating the circuit {} with spectre...'.format(circuit_name))
    # run simulation
    os.system('ocean -replay ./sim_opamp.ocn -log sim.log > err 2>&1')

    # get simulation results
    # set the optimization goal and constraints here
    # here we should sacrifice gain for margin

    '''   prb_constr0     gain      >= gain_target  dB    '''
    '''   prb_constr1_lower pm       >= pm_lower deg    '''
    '''   prb_constr1_upper pm       <= pm_upper deg    '''
    '''   prb_constr2     gbw       >= gbw_target MHz   '''
    '''   prb_constr3     power     <= power_target uW    '''
    '''   goal            fom_s     maximize     '''

    sim = os.path.exists('./sim.out')
    print('sim', sim)
    if sim == True:
        out = open('./sim.out', 'r')
        lines = out.readlines()
        stripped1 = lines[2].strip()
        match1 = re.search(r'^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$', stripped1)
        print('match1', match1)
        match2 = re.search(r'^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$', stripped1)
        print('match2', match2)
        match3 = re.search(r'^(\S+)\s+(\S+)\s+(\S+)$', stripped1)
        print('match3', match3)
        if match1 or match2 or match3:
            if match1:
                print('[Info] simulation successed!')
                gain = float(match1.groups()[0])
                pm = float(match1.groups()[1])
                gbw = float(match1.groups()[2]) / 1e6
                power = float(match1.groups()[3]) * 1e6
                ph = float(match1.groups()[4])
                if np.abs(ph) > 90:
                    pm = pm + 180
            elif match2:
                print('[Info] simulation fail on one metric!')
                gain = float(match2.groups()[0])
                pm = -180
                gbw = float(match2.groups()[1]) / 1e6
                power = float(match2.groups()[2]) * 1e6
            else:
                print('[Info] simulation fail on two metrics!')
                gain = float(match3.groups()[0])
                pm = -180
                gbw = -100
                power = float(match3.groups()[1]) * 1e6
            out.close()

            prb_constr0 = (-1 * gain + gain_target)/gain_target
            prb_constr1_lower = (-1 * pm + pm_lower)/pm_lower  # pm >= pm_lower
            prb_constr1_upper = (pm - pm_upper)/pm_upper        # pm <= pm_upper
            prb_constr2 = (-1 * gbw + gbw_target)/gbw_target
            prb_constr3 = (power - power_target)/power_target
            fom_s = gbw * c_load / (power * 1e-3)
            # 目标函数：只使用fom_s，移除PM惩罚项
            goal = -fom_s
            # print('[Info] gain={}db pm={}deg gbw={}MHz power={}uW'.format(gain, pm, gbw, power))
            print('[Info] FOMs={}'.format(fom_s))
        else:
            print('[Error] incomplete simulation!')
            gain = 0
            pm = 0
            gbw = 0
            power = 0
            fom_s = 0
            goal = np.inf  # (np.random.rand()+1)*100
            prb_constr0 = np.inf  # (np.random.rand()+1)*-10
            prb_constr1_lower = np.inf  # (np.random.rand()+1)*-10
            prb_constr1_upper = np.inf  # (np.random.rand()+1)*-10
            prb_constr2 = np.inf  # (np.random.rand()+1)*0.2
            prb_constr3 = np.inf  # (np.random.rand()+1)*50
    else:
        print('[Error] simulation failed!')
        gain = 0
        pm = 0
        gbw = 0
        power = 0
        fom_s = 0
        goal = np.inf  # (np.random.rand()+1)*100
        prb_constr0 = np.inf  # (np.random.rand()+1)*-10
        prb_constr1_lower = np.inf  # (np.random.rand()+1)*-10
        prb_constr1_upper = np.inf  # (np.random.rand()+1)*-10
        prb_constr2 = np.inf  # (np.random.rand()+1)*0.2
        prb_constr3 = np.inf  # (np.random.rand()+1)*50
    res = np.array([goal, prb_constr0, prb_constr1_lower, prb_constr1_upper, prb_constr2, prb_constr3]).reshape(1, -1)
    # 返回物理量值用于显示
    physical_values = {'gain': gain, 'pm': pm, 'gbw': gbw, 'power': power, 'fom_s': fom_s}

    return res, physical_values


def preprocessing_netlist(circuit_name, debug):
    postLayout_netlist = open('./opamp_' + circuit_name + '.pex.netlist', 'r')
    print('[Info] performing netlist preprocessing...')
    processed_netlist = open('./post_netlist', 'w')
    lines = postLayout_netlist.readlines()
    for line in lines:
        stripped = line.strip()
        match = re.search(r'^ends\s+(\S+)$', stripped)
        if match:
            wrong_name = match.groups()[0]
            right_name = "opamp_" + circuit_name
            line = re.sub(wrong_name, right_name, line)
            if debug:
                print('[Debug] find wrong model name \'{}\' in netlist'.format(wrong_name))
                print('[Debug] replaced with \'{}\''.format(right_name))
            processed_netlist.writelines(line)
        else:
            processed_netlist.writelines(line)
    processed_netlist.close()
    postLayout_netlist.close()


def postLayout_sim(circuit_name, parasitic_path, debug=False):
    # setup
    os.system('rm -rf postLayout_sim')
    os.system('mkdir postLayout_sim')
    os.chdir('postLayout_sim')
    generate_simScript()
    os.system('mkdir netlist')
    os.chdir('./netlist')
    # copy post layout parasitic file
    os.system('cp {}/OPAMP_{}.pex.netlist* ./'.format(parasitic_path, circuit_name.upper()))
    # preprocessing_netlist(circuit_name, debug)
    # write header
    netlist_header = open('./netlistHeader', 'w')
    netlist_header.writelines('// Automated generated for post layout simulation\n')
    netlist_header.writelines('// Generated for: spectre\n')
    local_time = get_time()
    netlist_header.writelines('// Generated on: {}\n'.format(local_time))
    netlist_header.writelines('simulator lang=spectre\n')
    netlist_header.writelines('global vdd gnd\n')
    netlist_header.writelines('// Header End \n')
    netlist_header.close()
    # write footer
    netlist_footer = open('./netlistFooter', 'w')
    netlist_footer.writelines('// Footer End')
    netlist_footer.close()
    # write netlist
    netlist = open('./netlist', 'w')
    netlist.writelines('include "OPAMP_{}.pex.netlist"\n'.format(circuit_name.upper()))
    # netlist.writelines('include "post_netlist"\n'.format(circuit_name))
    netlist.writelines('ID0 (vdd net_vb_n) isource dc=1u type=dc \n')
    netlist.writelines('ID1 (net_vb_p gnd) isource dc=1u type=dc \n')
    netlist.writelines('V0 (net_vip gnd) vsource dc=900.0m mag=1 type=sine\n')
    netlist.writelines('V1 (vdd gnd) vsource dc=1.8 type=dc\n')
    netlist.writelines('C0 (net_vin gnd) capacitor c=1F \n')
    netlist.writelines('L0 (net_vin net_vo) inductor l=1G \n')
    netlist.writelines('C1 (net_vo gnd) capacitor c=10.0p \n')
    netlist.writelines('X0 (gnd vdd net_vo net_vb_n net_vip net_vin net_vb_p) OPAMP_{}\n'.format(circuit_name.upper()))
    netlist.close()
    # os.system('chmod u+x *')
    os.chdir('..')

    # clear logs
    os.system('rm -rf ~/CDS.log*')
    # run simulation
    print('[Info] simulating the circuit {} with spectre...'.format(circuit_name))
    os.system('ocean -replay ./sim_opamp.ocn -log sim.log > err 2>&1')

    sim = os.path.exists('./sim.out')
    if sim == True:
        out = open('./sim.out', 'r')
        lines = out.readlines()
        stripped1 = lines[2].strip()
        print(stripped1)
        match1 = re.search(r'^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$', stripped1)
        print('match1', match1)
        match2 = re.search(r'^(\S+)\s+(\S+)\s+(\S+)$', stripped1)
        print('match2', match2)
        match3 = re.search(r'^(\S+)\s+(\S+)$', stripped1)
        print('match3', match3)
        if match1:
            print('[Info] simulation successed!')
            gain = float(match1.groups()[0])
            pm = float(match1.groups()[1])
            gbw = float(match1.groups()[2]) / 1e6
            power = float(match1.groups()[3]) * 1e6
            out.close()
            print('[Info] gain={}db pm={}deg gbw={}MHz power={}uW'.format(gain, pm, gbw, power))
            os.chdir('..')
            return gain, pm, gbw, power
        elif match2:
            print('[Info] simulation fail on one metric!')
            gain = float(match1.groups()[0])
            pm = 0
            gbw = float(match1.groups()[1]) / 1e6
            power = float(match1.groups()[2]) * 1e6
            out.close()
            print('[Info] gain={}db pm={}deg gbw={}MHz power={}uW'.format(gain, pm, gbw, power))
            os.chdir('..')
            return gain, pm, gbw, power
        elif match3:
            print('[Info] simulation fail on one metric!')
            gain = float(match1.groups()[0])
            pm = 0
            gbw = 0
            power = float(match1.groups()[1]) * 1e6
            out.close()
            print('[Info] gain={}db pm={}deg gbw={}MHz power={}uW'.format(gain, pm, gbw, power))
            os.chdir('..')
            return gain, pm, gbw, power
        else:
            print('[Error] incomplete simulation!')
            os.chdir('..')
            return 0.1, 0.1, 0.1, 2000
    else:
        print('[Error] simulation failed!')
        os.chdir('..')
        return 0.1, 0.1, 0.1, 2000


""" circuit re-optimization after mapping to transistor-level """


def set_param_bound(lb_ratio, ub_ratio, param_dict):
    # tuning the W of specific mos only
    space_list = []
    for key in param_dict.keys():
        initial_value = param_dict[key]
        lb = initial_value * lb_ratio
        if lb < wmin:
            lb = wmin
        ub = initial_value * ub_ratio
        space_list.append({'name': key, 'type': 'num', 'lb': lb, 'ub': ub})
    opt_space = DesignSpace().parse(space_list)
    return opt_space


def set_gmidTarget_bound(gmidTarget_dict, debug=None):
    if debug == None:
        debug = False
    # tuning the W of specific mos only
    space_list = []
    for key in gmidTarget_dict.keys():
        initial_value = gmidTarget_dict[key]  # 获取初始值
        
        if key[0] == 'i':
            # 基于初始值设置范围，但限制在合理区间[1, 2]
            lb = max(1.0, 0.5 * initial_value)
            ub = min(2.0, 1.5 * initial_value)
            # 确保初始值在范围内
            if initial_value < lb:
                lb = max(1.0, initial_value * 0.9)
            if initial_value > ub:
                ub = min(2.0, initial_value * 1.1)
        elif key[5] == 'p' or key[5] == '2':  # pmos格式（'gmid_p_X' 或 'gmid_2_X'）
            # 基于初始值设置范围
            lb = max(3.0, 0.5 * initial_value)
            ub = min(15.0, 1.5 * initial_value)
            # 确保初始值在范围内
            if initial_value < lb:
                lb = max(3.0, initial_value * 0.9)
            if initial_value > ub:
                ub = min(15.0, initial_value * 1.1)
        elif key[5] == 'n' or key[5] == '1':  # nmos格式（'gmid_n_X' 或 'gmid_1_X'）
            # 基于初始值设置范围
            lb = max(3.0, 0.5 * initial_value)
            ub = min(20.0, 1.5 * initial_value)
            # 确保初始值在范围内
            if initial_value < lb:
                lb = max(3.0, initial_value * 0.9)
            if initial_value > ub:
                ub = min(20.0, initial_value * 1.1)
        else:
            print(key)
            # print(key[5])
            raise ValueError('wrong key: {}'.format(key))
        space_list.append({'name': key, 'type': 'num', 'lb': lb, 'ub': ub})
    opt_space = DesignSpace().parse(space_list)
    if debug:
        var_names = opt_space.numeric_names
        print('[Debug] {} gm/id parameters to be optimized:'.format(len(var_names)))
        print('[Debug]    {}'.format(var_names))
    return opt_space


def set_cTarget_bound(lb_ratio, ub_ratio, cTarget_dict, debug=None):
    if debug == None:
        debug = False
    # tuning the W of specific mos only
    space_list = []
    for key in cTarget_dict.keys():
        if key[0] == 'c':
            initial_value = cTarget_dict[key]
            lb = lb_ratio * initial_value
            ub = ub_ratio * initial_value
        else:
            print(key)
            raise ValueError('wrong key: {}'.format(key))
        space_list.append({'name': key, 'type': 'num', 'lb': lb, 'ub': ub})
    opt_space = DesignSpace().parse(space_list)
    if debug:
        var_names = opt_space.numeric_names
        print('[Debug] {} c parameters to be optimized:'.format(len(var_names)))
        print('[Debug]    {}'.format(var_names))
    return opt_space


def function_wrapper(work_dir, circuit_name, x, circuit_data,
                     gain_target=100.0, pm_lower=55.0, pm_upper=65.0,
                     gbw_target=0.7, power_target=1000.0, c_load=10.0):
    os.chdir(work_dir)
    os.chdir('./mapped_circuits/{}'.format(circuit_name))
    generate_netlist_opt(circuit_data, x)
    res, physical_values = sim_and_getRes(circuit_name, gain_target, pm_lower, pm_upper,
                                          gbw_target, power_target, c_load)
    return res, physical_values


def function_wrapper_gmid(work_dir, circuit_name, x_gmid, circuit_data, debug,
                          gain_target=100.0, pm_lower=55.0, pm_upper=65.0,
                          gbw_target=0.7, power_target=1000.0, c_load=10.0):
    """
    Wrapper function for gmid optimization.
    
    Args:
        work_dir: Working directory
        circuit_name: Name of the circuit
        x_gmid: gmid parameter values (DataFrame)
        circuit_data: Circuit data
        debug: Debug flag
        gain_target: Gain target value in dB
        pm_lower: Phase margin lower bound in deg
        pm_upper: Phase margin upper bound in deg
        gbw_target: Gain bandwidth product target in MHz
        power_target: Power target value in uW
        c_load: Load capacitance in pF
    
    Returns:
        res: Optimization results
        physical_values: Physical values dictionary
    """
    os.chdir(work_dir)
    os.chdir('./mapped_circuits/{}'.format(circuit_name))
    generate_netlist(circuit_data, x_gmid, None, debug)
    res, physical_values = sim_and_getRes(circuit_name, gain_target, pm_lower, pm_upper,
                                          gbw_target, power_target, c_load)
    return res, physical_values


def function_wrapper_c(work_dir, circuit_name, x_gmid, x_c, circuit_data, debug,
                       gain_target=100.0, pm_lower=55.0, pm_upper=65.0,
                       gbw_target=0.7, power_target=1000.0, c_load=10.0):
    os.chdir(work_dir)
    os.chdir('./mapped_circuits/{}'.format(circuit_name))
    generate_netlist(circuit_data, x_gmid, x_c, debug)
    res, physical_values = sim_and_getRes(circuit_name, gain_target, pm_lower, pm_upper,
                                          gbw_target, power_target, c_load)
    return res, physical_values


def extract_pf(points: np.ndarray) -> np.ndarray:
    dom_matrix = Dominator().calc_domination_matrix(points, None)
    is_optimal = (dom_matrix >= 0).all(axis=1)
    return points[is_optimal]


def get_best(current_best_x, current_best_y, x_new, y_new):
    goal_current = -1 * current_best_y[0][0]
    constr0_current = current_best_y[0][1]
    constr1_lower_current = current_best_y[0][2]
    constr1_upper_current = current_best_y[0][3]
    constr2_current = current_best_y[0][4]
    constr3_current = current_best_y[0][5]

    goal_new = -1 * y_new[0][0]
    constr0_new = y_new[0][1]
    constr1_lower_new = y_new[0][2]
    constr1_upper_new = y_new[0][3]
    constr2_new = y_new[0][4]
    constr3_new = y_new[0][5]

    if constr0_current <= 0 and constr1_lower_current <= 0 and constr1_upper_current <= 0 and constr2_current <= 0 and constr3_current <= 0:
        if constr0_new <= 0 and constr1_lower_new <= 0 and constr1_upper_new <= 0 and constr2_new <= 0 and constr3_new <= 0:
            if goal_new >= goal_current:
                best_x = x_new
                best_y = y_new
                # update = 1
            else:
                best_x = current_best_x
                best_y = current_best_y
                # update = 0
        else:
            best_x = current_best_x
            best_y = current_best_y
            # update = 0
    else:
        if constr0_new <= 0 and constr1_lower_new <= 0 and constr1_upper_new <= 0 and constr2_new <= 0 and constr3_new <= 0:
            best_x = x_new
            best_y = y_new
            # update = 1
        else:
            if max(constr0_new, 0) + max(constr1_lower_new, 0) + max(constr1_upper_new, 0) + max(constr2_new, 0) + max(constr3_new, 0) < max(
                    constr0_current, 0) + max(constr1_lower_current, 0) + max(constr1_upper_current, 0) + max(constr2_current, 0) + max(constr3_current, 0):
                best_x = x_new
                best_y = y_new
                # update = 1
            else:
                best_x = current_best_x
                best_y = current_best_y
                # update = 0

    # return best_x, best_y, update
    return best_x, best_y


if __name__ == '__main__':
    """check parser"""
