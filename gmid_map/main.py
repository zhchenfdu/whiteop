import os
cpu_lim = 1
os.environ['OMP_NUM_THREADS'] = str(cpu_lim)
os.environ['OPENBLAS_NUM_THREADS'] = str(cpu_lim)
os.environ['MKL_NUM_THREADS'] = str(cpu_lim)
os.environ['VECLIB_MAXIMUM_THREADS'] = str(cpu_lim)
os.environ['NUMEXPR_NUM_THREADS'] = str(cpu_lim)

import os
import argparse
from netlist_generator import *
from utils import *

work_dir = os.getcwd()

parser = argparse.ArgumentParser("Transistor-level circuit netlist mapping and simulation")
parser.add_argument('--TITLE', action='store_true', help='print title')
parser.add_argument('--MAP', action='store_true', help='map the circuit netlists')
parser.add_argument('--SIM', action='store_true', help='simulate the transistor-level circuit')
parser.add_argument('--SIMALL', action='store_true', help='simulate all the transistor-level circuits')
parser.add_argument('--OUT', action='store_true', help='generate the netlist out file for the layout negeration')
parser.add_argument('--REOPT1', action='store_true', help='re-optimizate the circuit on gm over id target')
#parser.add_argument('--REOPT2', action='store_true', help='re-optimizate the transistor-level circuit')
parser.add_argument('--Debug', action='store_true', help='output the debug information')
parser.add_argument('--opt_iter', type=int, default=30, help='re-optimization iteratons nums')
parser.add_argument('--lb_ratio', type=float, default=0.2, help='the lower bound ratio of optimization space')
parser.add_argument('--ub_ratio', type=float, default=5, help='the upper bound ratio of optimization space')
parser.add_argument('--sample_nums', type=int, default=15, help='the number of initial random samples (default: 15, excluding the initial mapping value)')
#parser.add_argument('--intrinsic_gain_times', type=float, default=2,
#                    help='the multiple of the intrinsic gain is taken while mapping a single mos in the gmid method')
parser.add_argument('--circuit_name', type=str, default='', help='the circuit to be mapped')
parser.add_argument('--input_circuit_dir', type=str, default='', 
                    help='direct path to circuit directory (overrides behavioral_model_path + circuit_name)')
parser.add_argument('--output_circuit_dir', type=str, default='', 
                    help='direct path to output circuit directory (overrides mapped_circuits/circuit_name)')
# Optimization target values
parser.add_argument('--gain_target', type=float, default=100.0, help='gain target value in dB (default: 100.0)')
parser.add_argument('--pm_lower', type=float, default=55.0, help='phase margin lower bound in deg (default: 55.0)')
parser.add_argument('--pm_upper', type=float, default=65.0, help='phase margin upper bound in deg (default: 65.0)')
parser.add_argument('--gbw_target', type=float, default=0.7, help='gain bandwidth product target in MHz (default: 0.7)')
parser.add_argument('--power_target', type=float, default=1000.0, help='power target value in uW (default: 1000.0)')
parser.add_argument('--c_load', type=float, default=10.0, help='load capacitance in pF (default: 10.0)')
args = parser.parse_args()

if args.TITLE:
    print(' /////////////////////////////////////////////')
    print(' ///    TRANSISTOR-LEVEL CIRCUIT MAPPING    ///')
    print(' /////////////////////////////////////////////')
    print(' Map behavioral-level opamp model to transistor-level netlist')
    print(' with gmid method.')
    print(' Testbench generation & simulation / gm-level optimization / size-level optimization')
    print(' can also be performed.')
    print(' Author: JialinLu, Fudan, EDA Lab.')
    print(' Version 1.0.\n')

# ig_time = args.intrinsic_gain_times

if args.Debug:
    Debug = True
    print('[Debug] using debug mod...')
else:
    Debug = False
    print('[Debug] using non-debug mod...')

behavioral_model_path = './example_white_box_param/'

if args.SIMALL:
    all_circuits = os.listdir(r'./behavior_level_opamp')
    all_good_circuits = []
    print(
        '[Info] Simulating all {} circuits that found under path: {}'.format(len(all_circuits), behavioral_model_path))

"""input: the results optimized by date22's method"""
def get_subdirectories(dir):
    items = os.listdir(dir)
    directories = [item for item in items if os.path.isdir(os.path.join(dir, item))]
    return directories

# Handle input_circuit_dir parameter
input_circuit_dir = None
circuit_name = None
if args.input_circuit_dir:
    # Direct circuit directory path provided
    input_circuit_dir = os.path.abspath(args.input_circuit_dir)
    circuit_name = os.path.basename(input_circuit_dir)
    selected_circuits_list = [circuit_name]
    # Override behavioral_model_path for this circuit
    behavioral_model_path = os.path.dirname(input_circuit_dir) + '/'
    if not behavioral_model_path.endswith('/'):
        behavioral_model_path += '/'
elif args.SIMALL:
    selected_circuits_list = all_circuits
elif args.circuit_name:
    selected_circuits_list = [args.circuit_name]
else:
    selected_circuits_list = get_subdirectories(behavioral_model_path)
print(selected_circuits_list)

circuit_data_dict = {}
device_features = ['type', 'value', 'unit', 'left_port', 'right_port', 'parasitic', 'circuit_name']

for circuit in selected_circuits_list:
    # If input_circuit_dir is provided, use it directly
    if input_circuit_dir and circuit == circuit_name:
        param_path = os.path.join(input_circuit_dir, 'circuit', 'param')
        netlist_path = os.path.join(input_circuit_dir, 'circuit', 'netlist', 'netlist')
    else:
        param_path = behavioral_model_path + circuit + '/circuit/param'
        netlist_path = behavioral_model_path + circuit + '/circuit/netlist/netlist'
    circuit_dict = parse_behavioral_model(circuit, device_features, param_path, netlist_path)
    circuit_data = pd.DataFrame(circuit_dict)
    inst_list = circuit_data.columns.values.tolist()
    # print('circuit_data', circuit_data)
    # for inst in inst_list:
    #     print(inst+': '+str(circuit_data.loc['value'][inst])+' '+circuit_data.loc['unit'][inst])
    circuit_data_dict.update({circuit: circuit_data})

os.chdir(work_dir)

"""mapping all selected circuits and generate netlists"""
map_circuits_list = selected_circuits_list
# selected_circuits_list = ['4ygYTM', 'CMJRbs', 'Uf8gGW']
# if args.SIMALL:
#    map_circuits_list = all_circuits
circuit_gmidTarget_dict = {}
circuit_cTarget_dict = {}
failed_circuits_map = []
if args.MAP:
    for circuit in map_circuits_list:
        try:
            circuit_data = circuit_data_dict[circuit]
            print('[Info] performing transistor circuit netlist mapping of {}...'.format(circuit))
            
            # Handle output_circuit_dir parameter
            if args.output_circuit_dir:
                output_circuit_dir = os.path.abspath(args.output_circuit_dir)
                # Ensure parent directory exists
                output_parent = os.path.dirname(output_circuit_dir)
                if output_parent and not os.path.exists(output_parent):
                    os.makedirs(output_parent, exist_ok=True)
                # Remove existing output directory if it exists
                if os.path.exists(output_circuit_dir):
                    import shutil
                    shutil.rmtree(output_circuit_dir)
                os.makedirs(output_circuit_dir, exist_ok=True)
                os.chdir(output_circuit_dir)
            else:
                if not os.path.exists('mapped_circuits'):
                    os.makedirs('mapped_circuits')
                os.chdir('./mapped_circuits/')
                os.system('rm -rf ./{}'.format(circuit))
                os.system('mkdir {}'.format(circuit))
                os.chdir('./{}'.format(circuit))
            
            gmid_target_dict, c_target_dict = generate_netlist(circuit_data, param_gmid=None, param_c=None, debug=Debug)
            circuit_gmidTarget_dict.update({circuit: gmid_target_dict})
            circuit_cTarget_dict.update({circuit: c_target_dict})
            os.chdir(work_dir)
            print('[Success] circuit {} mapping completed successfully.'.format(circuit))
        except Exception as e:
            os.chdir(work_dir)
            failed_circuits_map.append(circuit)
            print('[Error] circuit {} mapping failed: {}'.format(circuit, str(e)))
            import traceback
            if Debug:
                traceback.print_exc()
            continue
    print('[Info] all behavioral models are mapping to schematic netlists!')
    if failed_circuits_map:
        print('[Warning] {} circuits failed during mapping: {}'.format(len(failed_circuits_map), failed_circuits_map))
    else:
        print('[Info] all circuits mapped successfully!')

"""run transistor-level simulation"""
sim_circuits_list = selected_circuits_list
# selected_circuits_list = ['4ygYTM', 'CMJRbs', 'Uf8gGW']
# if args.SIMALL:
#    sim_circuits_list = all_circuits

satisfied_circuits = []
failed_circuits_sim = []
if args.SIM:
    for circuit in sim_circuits_list:
        try:
            print('[Info] performing transistor circuit simulation of {}...'.format(circuit))
            # Handle output_circuit_dir parameter
            if args.output_circuit_dir:
                # Use the output_circuit_dir directly (circuit files are already there from MAP)
                sim_circuit_dir = os.path.abspath(args.output_circuit_dir)
            else:
                # Use default mapped_circuits directory
                sim_circuit_dir = os.path.join(work_dir, 'mapped_circuits', circuit)
            
            if not os.path.exists(sim_circuit_dir):
                print('[Warning] circuit {} directory not found, skipping simulation.'.format(circuit))
                print('[Warning] Expected directory: {}'.format(sim_circuit_dir))
                failed_circuits_sim.append(circuit)
                continue
            os.chdir(sim_circuit_dir)
            # gain_init, pm_init, gbw_init, power_init = sim_only(circuit)
            # print('[Info] the initial simulation results are:')
            # print('       gain={}, pm={}, gbw={}, power={}'.format(gain_init, pm_init, gbw_init, power_init))
            res_init, physical_values_init = sim_and_getRes(circuit, args.gain_target, args.pm_lower, 
                                                             args.pm_upper, args.gbw_target, 
                                                             args.power_target, args.c_load)
            os.chdir(work_dir)
            constr0_current = res_init[0][1]
            constr1_lower_current = res_init[0][2]
            constr1_upper_current = res_init[0][3]
            constr2_current = res_init[0][4]
            constr3_current = res_init[0][5]
            if constr0_current <= 0 and constr1_lower_current <= 0 and constr1_upper_current <= 0 and constr2_current <= 0 and constr3_current <= 0:
                print('[Success] the initial mapping circuit is satisfied with the constraints!')
                satisfied_circuits.append(circuit)
                # all_good_circuits.append(circuit)
            else:
                print('[Info] the initial mapping circuit is not satisfied with the constraints...')
                reopt = True
            print('[Info] best_foms={:.3f}, best_gain={:.3f}dB, best_pm={:.3f}deg, best_gbw={:.3f}MHz, best_power={:.3f}uW'.format(
                physical_values_init['fom_s'], physical_values_init['gain'], physical_values_init['pm'], 
                physical_values_init['gbw'], physical_values_init['power']))
        except Exception as e:
            os.chdir(work_dir)
            failed_circuits_sim.append(circuit)
            print('[Error] circuit {} simulation failed: {}'.format(circuit, str(e)))
            import traceback
            if Debug:
                traceback.print_exc()
            continue
    print('[Info] all circuit simulations finished!')
    print('[Info] which satisfies the initial constraints are: {}'.format(satisfied_circuits))
    if failed_circuits_sim:
        print('[Warning] {} circuits failed during simulation: {}'.format(len(failed_circuits_sim), failed_circuits_sim))

"""generate the netlist out file for all the selected circuits"""
out_circuits_list = selected_circuits_list
# selected_circuits_list = ['4ygYTM', 'CMJRbs', 'Uf8gGW']
if args.SIMALL:
    out_circuits_list = all_circuits
if args.OUT:
    circuit_param_dict = {}
    circuit_gmidTarget_dict = {}
    failed_circuits_out = []
    for circuit in out_circuits_list:
        try:
            circuit_data = circuit_data_dict[circuit]
            print('[Info] genarating the netlist out file of {}...'.format(circuit))
            # Handle output_circuit_dir parameter
            if args.output_circuit_dir:
                # Use the output_circuit_dir directly (circuit files are already there from MAP)
                out_circuit_dir = os.path.abspath(args.output_circuit_dir)
            else:
                # Use default mapped_circuits directory
                out_circuit_dir = os.path.join(work_dir, 'mapped_circuits', circuit)
            
            if not os.path.exists(out_circuit_dir):
                print('[Warning] circuit {} directory not found, skipping netlist out generation.'.format(circuit))
                print('[Warning] Expected directory: {}'.format(out_circuit_dir))
                failed_circuits_out.append(circuit)
                continue
            os.chdir(out_circuit_dir)
            all_param_dict, gmid_target_dict = generate_netlistOut(circuit_data)
            circuit_param_dict.update({circuit: all_param_dict})
            circuit_gmidTarget_dict.update({circuit: gmid_target_dict})
            # print(all_param_dict)
            os.chdir(work_dir)
            print('[Success] circuit {} netlist out file generation completed successfully.'.format(circuit))
        except Exception as e:
            os.chdir(work_dir)
            failed_circuits_out.append(circuit)
            print('[Error] circuit {} netlist out file generation failed: {}'.format(circuit, str(e)))
            import traceback
            if Debug:
                traceback.print_exc()
            continue
    print('[Info] all the netlist out files generation finished!')
    if failed_circuits_out:
        print('[Warning] {} circuits failed during netlist out generation: {}'.format(len(failed_circuits_out), failed_circuits_out))
    else:
        print('[Info] all circuits netlist out files generated successfully!')

# re-optimizate the circuit on gm over id target
reOpt1_circuits_list = selected_circuits_list
# selected_circuits_list = ['4ygYTM', 'CMJRbs', 'Uf8gGW']
# if args.SIMALL:
#    reOpt1_circuits_list = all_circuits
opt_satisfied_circuits = []
failed_circuits_reopt = []
if args.REOPT1:
    for circuit in reOpt1_circuits_list:
        try:
            circuit_data = circuit_data_dict[circuit]
            print('[Info] re-optimizating the circuit {} on gmOverId...'.format(circuit))
            if circuit not in circuit_gmidTarget_dict:
                print('[Warning] circuit {} not found in gmidTarget_dict, skipping re-optimization.'.format(circuit))
                failed_circuits_reopt.append(circuit)
                continue
            init_gmid_target = circuit_gmidTarget_dict[circuit]
            #opt_space = set_gmidTarget_bound(args.lb_ratio, args.ub_ratio, init_gmid_target, debug=Debug)
            opt_space = set_gmidTarget_bound(init_gmid_target, debug=Debug)

            # 将初始值字典转换为DataFrame格式（按照优化空间的变量顺序）
            var_names = opt_space.numeric_names
            init_x_dict = {key: init_gmid_target[key] for key in var_names if key in init_gmid_target}
            init_x_df = pd.DataFrame([init_x_dict])
            
            # 评估初始值的性能
            print('[Info] evaluating initial mapping values...')
            init_y, init_physical = function_wrapper_gmid(work_dir, circuit, init_x_df, circuit_data, Debug,
                                                          args.gain_target, args.pm_lower, args.pm_upper,
                                                          args.gbw_target, args.power_target, args.c_load)
            if Debug:
                print('[Debug] init_x_df: {}'.format(init_x_df))
                print('[Debug] init_y: {}'.format(init_y))
            
            # 初始化best_x和best_y为初始值
            best_x = init_x_df
            best_y = init_y
            best_physical = init_physical
            
            # Create Bayesian optimizer
            reOpt = GeneralBO(opt_space, num_obj=1, num_constr=5, rand_sample=args.sample_nums)
            
            # Generate and evaluate random initial samples
            init_sample_nums = args.sample_nums
            print('[Info] generating {} initial random samples...'.format(init_sample_nums))
            
            # Method 1: try DesignSpace.sample() if available
            try:
                init_samples = opt_space.sample(init_sample_nums)
            except (AttributeError, TypeError):
                # Method 2: manually generate uniform random samples
                var_names = opt_space.numeric_names
                init_samples_dict = {}
                # Try to get bounds from opt_space.paras
                try:
                    for var_name in var_names:
                        var_info = next(item for item in opt_space.paras if item['name'] == var_name)
                        lb = var_info['lb']
                        ub = var_info['ub']
                        init_samples_dict[var_name] = np.random.uniform(lb, ub, init_sample_nums)
                except (AttributeError, StopIteration):
                    # Method 3: if bounds are unavailable, sample around initial values
                    print('[Warning] cannot get bounds from opt_space, using initial-value ranges for sampling')
                    for var_name in var_names:
                        if var_name in init_gmid_target:
                            init_val = init_gmid_target[var_name]
                            # Use [0.5 * init_val, 1.5 * init_val] as sampling range
                            lb = init_val * 0.5
                            ub = init_val * 1.5
                            init_samples_dict[var_name] = np.random.uniform(lb, ub, init_sample_nums)
                        else:
                            # If variable has no initial value, fall back to a default range
                            init_samples_dict[var_name] = np.random.uniform(1.0, 20.0, init_sample_nums)
                init_samples = pd.DataFrame(init_samples_dict)
            
            # Batch-evaluate all initial samples
            print('[Info] evaluating {} initial random samples...'.format(init_sample_nums))
            # Debug: print first few samples to verify they are different
            if Debug:
                print('[Debug] First 3 sample points:')
                for debug_idx in range(min(3, init_sample_nums)):
                    debug_sample = init_samples.iloc[[debug_idx]]
                    print('[Debug] Sample {}: {}'.format(debug_idx + 1, debug_sample.to_dict('records')[0]))
            init_samples_y_list = []
            init_samples_physical_list = []
            for idx in range(init_sample_nums):
                sample_x = init_samples.iloc[[idx]]
                if Debug:
                    print('[Debug] Evaluating sample {}/{} with params: {}'.format(
                        idx + 1, init_sample_nums, sample_x.to_dict('records')[0]))
                sample_y, sample_physical = function_wrapper_gmid(work_dir, circuit, sample_x, circuit_data, Debug,
                                                                  args.gain_target, args.pm_lower, args.pm_upper,
                                                                  args.gbw_target, args.power_target, args.c_load)
                init_samples_y_list.append(sample_y)
                init_samples_physical_list.append(sample_physical)
                print('[Info] initial sample {}/{}: foms={:.3f}, gain={:.3f}dB, pm={:.3f}deg, gbw={:.3f}MHz, power={:.3f}uW'.format(
                    idx + 1, init_sample_nums, sample_physical['fom_s'], sample_physical['gain'], 
                    sample_physical['pm'], sample_physical['gbw'], sample_physical['power']))
                # Update best objective and corresponding physical values
                best_y_old = best_y.copy()
                best_x, best_y = get_best(best_x, best_y, sample_x, sample_y)
                if not np.array_equal(best_y, best_y_old):
                    best_physical = sample_physical
            
            # Observe all initial samples in the optimizer
            print('[Info] observing all initial samples to optimizer...')
            # First observe the initial mapped point
            reOpt.observe(init_x_df, init_y)
            # 再 observe 所有随机采样点
            for idx in range(init_sample_nums):
                reOpt.observe(init_samples.iloc[[idx]], init_samples_y_list[idx])
            
            print('[Info] {} initial samples observed (1 initial mapping + {} random samples)'.format(
                init_sample_nums + 1, init_sample_nums))
            print('[Info] best initial: foms={:.3f}, gain={:.3f}dB, pm={:.3f}deg, gbw={:.3f}MHz, power={:.3f}uW'.format(
                best_physical['fom_s'], best_physical['gain'], best_physical['pm'], 
                best_physical['gbw'], best_physical['power']))
            print('[Info] starting optimization iterations...')
            
            for i in range(args.opt_iter):
                x_new = reOpt.suggest(n_suggestions=1)
                if Debug:
                    print('[Debug] iter {} x_new (optimizer suggestion):'.format(i + 1))
                    print('[Debug] {}'.format(x_new))
                    print('[Debug] x_new columns: {}'.format(list(x_new.columns)))
                    print('[Debug] x_new values: {}'.format(x_new.to_dict('records')[0] if len(x_new) > 0 else 'empty'))
                y_new, physical_values_new = function_wrapper_gmid(work_dir, circuit, x_new, circuit_data, Debug,
                                                                   args.gain_target, args.pm_lower, args.pm_upper,
                                                                   args.gbw_target, args.power_target, args.c_load)
                if Debug:
                    print('[Debug] y_new: {}'.format(y_new))
                print('[Info] iter {} new solution: foms={:.3f}, gain={:.3f}dB, pm={:.3f}deg, gbw={:.3f}MHz, power={:.3f}uW'.format(
                    i + 1, physical_values_new['fom_s'], physical_values_new['gain'], physical_values_new['pm'], 
                    physical_values_new['gbw'], physical_values_new['power']))
                reOpt.observe(x_new, y_new)
                best_y_old = best_y.copy()
                best_x, best_y = get_best(best_x, best_y, x_new, y_new)
                # 更新物理量值：如果best_y更新了（不等于best_y_old），则更新best_physical
                if not np.array_equal(best_y, best_y_old):
                    best_physical = physical_values_new
                if Debug:
                    print('[Info] current best_x: {}'.format(best_x))
                print('[Info] iter {}: best_foms={:.3f}, best_gain={:.3f}dB, best_pm={:.3f}deg, best_gbw={:.3f}MHz, best_power={:.3f}uW'.format(
                    i + 1, best_physical['fom_s'], best_physical['gain'], best_physical['pm'], 
                    best_physical['gbw'], best_physical['power']))
                best_res = str(best_y[0][0]) + ' ' + str(best_y[0][1]) + ' ' + str(best_y[0][2]) + ' ' + str(
                    best_y[0][3]) + ' ' + str(best_y[0][4]) + ' ' + str(best_y[0][5]) + '\n'
                os.system('echo \'{}\' >> best_preSim_res.txt'.format(best_res))

            if best_y[0][1]<=0 and best_y[0][2]<=0 and best_y[0][3]<=0 and best_y[0][4]<=0 and best_y[0][5]<=0:
                print('[Info] gmOverId {} re-optimization success!'.format(circuit))
                print('[Info] re-genarating the netlist out file of {}...'.format(circuit))
                generate_netlist(circuit_data, best_x)
                opt_satisfied_circuits.append(circuit)
                # if args.SIMALL:
                #    all_good_circuits.append(circuit)
            else:
                print('[Info] gmOverId {} re-optimization fail...'.format(circuit))
            os.chdir(work_dir)
        except Exception as e:
            os.chdir(work_dir)
            failed_circuits_reopt.append(circuit)
            print('[Error] circuit {} re-optimization failed: {}'.format(circuit, str(e)))
            import traceback
            if Debug:
                traceback.print_exc()
            continue
    print('[Info] all circuits\' gmOverId re-optimization finished!')
    print('[Info] which satisfies the initial constraints are: {}'.format(opt_satisfied_circuits))
    if failed_circuits_reopt:
        print('[Warning] {} circuits failed during re-optimization: {}'.format(len(failed_circuits_reopt), failed_circuits_reopt))
