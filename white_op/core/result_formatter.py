"""
Result formatting utilities.

Extract/compute performance metrics, format outputs, and save reports to files.
Also supports param conversion (HSPICE -> Spectre) and file/folder copying.
"""

import os
import json
import shutil
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .config import DesignRequirements, PipelineConfig


class ResultFormatter:
    """Result formatter."""
    
    # Circuit type -> source directory mapping (suffixes removed)
    CIRCUIT_DIR_MAPPING = {
        'SMC': '10pF_10MOhm_SMC',
        'SMCNR': '10pF_10MOhm_SMCNR',
        'NMC': '10pF_10MOhm_NMC',
        'NMCNR': '10pF_10MOhm_NMCNR',
        'MNMC': '10pF_10MOhm_MNMC',
        'NMCF': '10pF_10MOhm_NMCF',
        'NGCC': '10pF_10MOhm_NGCC',
        'DFCFC': '10pF_10MOhm_DFCFC',
        'MZC': '10pF_10MOhm_MZC',
    }
    
    # Variable mapping (HSPICE var name -> Spectre var name)
    PARAM_MAPPING = {
        'DFCFC': [
            ('G_1', 'g_net_vin_net_1'),
            ('A_1', 'rprs_net_vin_net_1'),
            ('G_2', 'g_net_1_net_2'),
            ('A_2', 'rprs_net_1_net_2'),
            ('G_3', 'g_net_2_net_vo'),
            ('A_3', 'rprs_net_2_net_vo'),
            ('C_m1', 'c_net_1_net_vo'),
            ('G_f2', 'g_net_1_net_vo'),
            ('A_f2', 'rprs_net_1_net_vo'),
            ('G_f4', 'g_net_2_net_3'),
            ('A_f4', 'rprs_net_2_net_3'),
            ('C_m2', 'c_net_2_net_3'),
        ],
        'SMC': [
            ('G_1', 'g_net_vin_net_1'),
            ('A_1', 'rprs_net_vin_net_1'),
            ('G_2', 'g_net_1_net_vo'),
            ('A_2', 'rprs_net_1_net_vo'),
            ('C_m', 'c_net_1_net_vo'),
        ],
        'NMC': [
            ('G_1', 'g_net_vin_net_1'),
            ('A_1', 'rprs_net_vin_net_1'),
            ('G_2', 'g_net_1_net_2'),
            ('A_2', 'rprs_net_1_net_2'),
            ('G_3', 'g_net_2_net_vo'),
            ('A_3', 'rprs_net_2_net_vo'),
            ('C_m1', 'c_net_1_net_vo'),
            ('C_m2', 'c_net_2_net_vo'),
        ],
        'MNMC': [
            ('G_1', 'g_net_vin_net_1'),
            ('A_1', 'rprs_net_vin_net_1'),
            ('G_2', 'g_net_1_net_2'),
            ('A_2', 'rprs_net_1_net_2'),
            ('G_3', 'g_net_2_net_vo'),
            ('A_3', 'rprs_net_2_net_vo'),
            ('C_m1', 'c_net_1_net_vo'),
            ('C_m2', 'c_net_2_net_vo'),
            ('G_f', 'g_net_vin_net_2'),
            ('A_f', 'rprs_net_vin_net_2'),
        ],
        'NMCNR': [
            ('G_1', 'g_net_vin_net_1'),
            ('A_1', 'rprs_net_vin_net_1'),
            ('G_2', 'g_net_1_net_2'),
            ('A_2', 'rprs_net_1_net_2'),
            ('G_3', 'g_net_2_net_vo'),
            ('A_3', 'rprs_net_2_net_vo'),
            ('C_m1', 'c_net_1_net_1_vo'),
            ('R_m', 'r_net_1_vo_net_vo'),
            ('C_m2', 'c_net_2_net_1_vo'),
        ],
        'NMCF': [
            ('G_1', 'g_net_vin_net_1'),
            ('A_1', 'rprs_net_vin_net_1'),
            ('G_2', 'g_net_1_net_2'),
            ('A_2', 'rprs_net_1_net_2'),
            ('G_3', 'g_net_2_net_vo'),
            ('A_3', 'rprs_net_2_net_vo'),
            ('C_m1', 'c_net_1_net_vo'),
            ('C_m2', 'c_net_2_net_vo'),
            ('G_f2', 'g_net_1_net_vo'),
            ('A_f2', 'rprs_net_1_net_vo'),
        ],
        'NGCC': [
            ('G_1', 'g_net_vin_net_1'),
            ('A_1', 'rprs_net_vin_net_1'),
            ('G_2', 'g_net_1_net_2'),
            ('A_2', 'rprs_net_1_net_2'),
            ('G_3', 'g_net_2_net_vo'),
            ('A_3', 'rprs_net_2_net_vo'),
            ('C_m1', 'c_net_1_net_vo'),
            ('C_m2', 'c_net_2_net_vo'),
            ('G_f1', 'g_net_vin_net_vo'),
            ('A_f1', 'rprs_net_vin_net_vo'),
            ('G_f2', 'g_net_1_net_vo'),
            ('A_f2', 'rprs_net_1_net_vo'),
        ],
        'SMCNR': [
            ('G_1', 'g_net_vin_net_1'),
            ('A_1', 'rprs_net_vin_net_1'),
            ('G_2', 'g_net_1_net_vo'),
            ('A_2', 'rprs_net_1_net_vo'),
            ('R_m', 'r_net_1_net_1_vo'),
            ('C_m', 'c_net_1_vo_net_vo'),
        ],
        'MZC': [
            ('G_1', 'g_net_vin_net_1'),
            ('A_1', 'rprs_net_vin_net_1'),
            ('G_2', 'g_net_1_net_vo'),
            ('A_2', 'rprs_net_1_net_vo'),
            ('C_m', 'c_net_1_net_vo'),
            ('G_f', 'g_net_vin_net_vo'),
            ('A_f', 'rprs_net_vin_net_vo'),
        ],
    }
    
    def __init__(self, output_dir: str, design_req: DesignRequirements, config: Optional[PipelineConfig] = None):
        """
        Initialize the result formatter.
        
        Args:
            output_dir: output directory
            design_req: design requirements
            config: optional config object (used to access netlist_path/output_dir)
        """
        self.output_dir = output_dir
        self.design_req = design_req
        self.config = config
        # Resolve gmid_map base path (may come from config/env, with a safe default)
        self.gmid_map_base = self._resolve_gmid_map_base()
        os.makedirs(output_dir, exist_ok=True)

    def _resolve_gmid_map_base(self) -> str:
        """
        Resolve the base path of gmid_map tool.

        Priority:
        1) PipelineConfig.gmid_map_base (if provided)
        2) Environment variable GMID_MAP_BASE
        3) Auto-detected path relative to this file:
           <repo_root>/gmid_map (assuming current file is white_op/core/result_formatter.py)
        """
        # 1) Config value (if available)
        if self.config and getattr(self.config, "gmid_map_base", None):
            return os.path.abspath(self.config.gmid_map_base)

        # 2) Environment variable
        env_base = os.environ.get("GMID_MAP_BASE")
        if env_base:
            return os.path.abspath(env_base)

        # 3) Fallback: relative to repository layout
        # result_formatter.py is in white_op/core/, repo root is two levels up
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        default_base = os.path.join(repo_root, "gmid_map")
        return os.path.abspath(default_base)
    
    def format_results(self, p2m_results: Dict) -> str:
        """
        Format P2M results into a text report.
        
        Args:
            p2m_results: P2M result dict
            
        Returns:
            str: formatted text report
        """
        report = []
        report.append("=" * 80)
        report.append("P2M Parameter Design - Final Results")
        report.append("=" * 80)
        report.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Experiment info
        report.append("## Experiment Info")
        report.append("")
        if self.config and hasattr(self.config, 'netlist_path') and self.config.netlist_path:
            report.append(f"- Netlist: {self.config.netlist_path}")
        else:
            report.append("- Netlist: N/A")
        
        iteration_count = p2m_results.get('iteration_count', 0)
        report.append(f"- Total iterations: {iteration_count}")
        
        total_time_minutes = p2m_results.get('total_time_minutes', None)
        if total_time_minutes is not None:
            report.append(f"- Total runtime: {total_time_minutes:.2f} minutes")
        report.append("")
        
        # Best iteration info
        best_iteration = p2m_results.get('best_iteration')
        if best_iteration:
            report.append("## Best Iteration")
            report.append("")
            report.append(f"- Iteration id: {best_iteration.get('iteration', 'N/A')}")
            
            quality_info = best_iteration.get('quality_info', {})
            step9_decision = quality_info.get('step9_decision', 'N/A')
            report.append(f"- Decision: {step9_decision}")
            report.append("")
            
            # Performance comparison
            report.append("## Performance Comparison")
            report.append("")
            
            # Simulated performance
            has_performance = quality_info.get('has_performance', False)
            if has_performance:
                perf = quality_info.get('performance', {})
                report.append("### Simulation Results")
                report.append("")
                
                gain = perf.get('gain', 0)
                gbw = perf.get('ugf', 0) / 1e6  # Hz -> MHz
                pm = perf.get('phase_margin', 0)
                power = perf.get('power', 0) * 1e6  # W -> μW
                fom = perf.get('fom', 0)
                
                # Check constraints
                constraints = self.design_req.check_constraints(
                    gain, gbw, pm, power
                )
                
                report.append(f"- FoM: {fom:.2f}")
                report.append(f"- Gain: {gain:.2f} dB (spec: > {self.design_req.gain_min_db} dB) {'✅' if constraints['gain_ok'] else '❌'}")
                report.append(f"- GBW: {gbw:.2f} MHz (spec: > {self.design_req.gbw_min_mhz} MHz) {'✅' if constraints['gbw_ok'] else '❌'}")
                report.append(f"- Phase Margin: {pm:.2f}° (spec: {self.design_req.pm_min_deg}° - {self.design_req.pm_max_deg}°) {'✅' if constraints['pm_ok'] else '❌'}")
                report.append(f"- Power: {power:.2f} μW (spec: < {self.design_req.power_max_uw} μW) {'✅' if constraints['power_ok'] else '❌'}")
                report.append("")
                
                # Expected performance (if available)
                expected_perf = quality_info.get('expected_performance')
                if expected_perf:
                    report.append("### Expected Performance (White-box Optimization)")
                    report.append("")
                    # expected_perf may be a dict or a string
                    if isinstance(expected_perf, dict):
                        exp_gain = expected_perf.get('gain', 0)
                        exp_gbw = expected_perf.get('ugf', 0) / 1e6
                        exp_pm = expected_perf.get('phase_margin', 0)
                        exp_power = expected_perf.get('power', 0) * 1e6
                        exp_fom = expected_perf.get('fom', 0)
                        report.append(f"- FoM: {exp_fom:.2f}")
                        report.append(f"- Gain: {exp_gain:.2f} dB")
                        report.append(f"- GBW: {exp_gbw:.2f} MHz")
                        report.append(f"- Phase Margin: {exp_pm:.2f}°")
                        report.append(f"- Power: {exp_power:.2f} μW")
                    else:
                        # If it's a string, display it as-is
                        report.append(expected_perf)
                    report.append("")
            else:
                report.append("### Simulation Results")
                report.append("")
                report.append("- No performance data")
                report.append("")
        
        # Best parameters (from param file)
        report.append("## Best Parameters")
        report.append("")
        if best_iteration:
            iter_num = best_iteration.get('iteration', 0)
            param_file = os.path.join(self.output_dir, f"iteration_{iter_num:02d}", "param")
            if os.path.exists(param_file):
                try:
                    with open(param_file, 'r', encoding='utf-8') as f:
                        param_lines = f.readlines()
                        for line in param_lines:
                            line = line.strip()
                            if line and not line.startswith('*'):
                                report.append(line)
                except Exception as e:
                    report.append(f"Failed to read param file: {e}")
            else:
                report.append("Param file does not exist")
        else:
            report.append("No best iteration info")
        report.append("")
        
        return "\n".join(report)
    
    def save_results(self, p2m_results: Dict, filename: str = "final_results.txt"):
        """
        Save P2M results to files.
        
        Args:
            p2m_results: P2M result dict
            filename: output filename
        """
        # Save text report
        report = self.format_results(p2m_results)
        report_file = os.path.join(self.output_dir, filename)
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        # Save full results as JSON
        json_file = os.path.join(self.output_dir, filename.replace('.txt', '.json'))
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(p2m_results, f, indent=2, ensure_ascii=False, default=str)
        
        # Generate param file and copy circuit folders
        try:
            # 1. Copy circuit folder to example_white_box_param
            target_circuit_dir = self._copy_circuit_folder_to_example()
            
            # 2. Read and convert param file
            spectre_param_file = self._convert_and_save_param_file(p2m_results)
            
            # 3. Copy converted param file into the new folder
            if spectre_param_file and target_circuit_dir:
                self._copy_param_to_circuit_folder(spectre_param_file, target_circuit_dir)
        except Exception as e:
            print(f"Warning: failed while processing param file and copying folders: {e}")
            import traceback
            traceback.print_exc()
            # Do not block the main flow; continue
        
        # Run post-processing workflow
        try:
            self._post_optimization_workflow(p2m_results)
        except Exception as e:
            print(f"Warning: post-processing workflow failed: {e}")
            import traceback
            traceback.print_exc()
            # Do not block the main flow; continue
        
        return report_file, json_file
    
    def _get_circuit_type(self) -> Optional[str]:
        """
        Infer circuit type from netlist_path.

        Returns:
            Circuit type string, or None if not recognized.
        """
        if not self.config:
            return None
        
        # Try to get netlist_path from config
        netlist_path = getattr(self.config, 'netlist_path', None)
        if not netlist_path:
            # If netlist_path is missing, infer from output_dir name (if it includes circuit type)
            output_dir_name = os.path.basename(self.output_dir)
            # Check for known circuit types
            for circuit_type in self.CIRCUIT_DIR_MAPPING.keys():
                if circuit_type in output_dir_name.upper():
                    return circuit_type
            return None
        
        netlist_basename = os.path.basename(netlist_path)
        circuit_type = os.path.splitext(netlist_basename)[0].upper()
        
        if circuit_type in self.CIRCUIT_DIR_MAPPING:
            return circuit_type
        return None
    
    def _get_source_circuit_dir_name(self, circuit_type: str) -> Optional[str]:
        """
        Map circuit type to the source folder name under the example directory.

        Args:
            circuit_type: circuit type

        Returns:
            Source folder name, or None if not available.
        """
        return self.CIRCUIT_DIR_MAPPING.get(circuit_type)
    
    def _get_target_circuit_dir_name(self) -> Optional[str]:
        """
        Extract directory name from output_dir and append '_spectre'.

        Returns:
            Target folder name, or None if unavailable.
        """
        if not self.output_dir:
            return None
        
        # Extract base directory name (without path)
        dir_name = os.path.basename(self.output_dir)
        return f"{dir_name}_spectre"
    
    def _get_param_mapping(self, circuit_type: str) -> Optional[List[Tuple[str, str]]]:
        """
        Return mapping pairs for a given circuit type.

        Args:
            circuit_type: circuit type

        Returns:
            List of mapping pairs, or None if not available.
        """
        return self.PARAM_MAPPING.get(circuit_type)
    
    def _calculate_param_value(self, hspice_var_name: str, hspice_value: float) -> float:
        """
        Convert parameter values (unit conversion).

        Args:
            hspice_var_name: HSPICE variable name (e.g., G_1, A_1, C_m1, R_m)
            hspice_value: HSPICE variable value

        Returns:
            Converted value in Spectre-friendly units.
        """
        if hspice_var_name.startswith('A_'):
            # A_*: unchanged
            return hspice_value
        elif hspice_var_name.startswith('G_'):
            # G_*: convert S -> mS (x1000)
            # HSPICE: G_1 = 15.9187e-6 (S) -> Spectre: g_net_vin_net_1 = 0.0159187 (mS)
            return hspice_value * 1000.0
        elif hspice_var_name.startswith('C_'):
            # C_*: convert F -> pF (x1e12)
            # HSPICE: C_m1 = 1.0000e-12 (F) -> Spectre: c_net_1_net_vo = 1 (pF)
            return hspice_value * 1e12
        elif hspice_var_name == 'R_m':
            # R_m: convert Ohm -> MOhm (/1e6)
            # HSPICE: R_m = 1e6 (Ohm) -> Spectre: r_net_1_vo_net_vo = 1 (MOhm)
            return hspice_value / 1e6
        else:
            # Others: unchanged
            return hspice_value
    
    def _read_hspice_param_file(self, param_file: str) -> Dict[str, float]:
        """
        Read an HSPICE-format param file and parse values.

        Args:
            param_file: path to param file

        Returns:
            Dict {var_name: value}
        """
        params = {}
        if not os.path.exists(param_file):
            return params
        
        try:
            with open(param_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('*'):
                        continue
                    
                    # Match `.param VAR_NAME = VALUE`
                    match = re.match(r'\.param\s+(\w+)\s*=\s*(.+)', line)
                    if match:
                        var_name = match.group(1)
                        value_str = match.group(2).strip()
                        # Parse numeric value (supports scientific notation)
                        try:
                            # Use eval to parse (safe here because we only handle numeric tokens)
                            value = float(eval(value_str))
                            params[var_name] = value
                        except:
                            pass
        except Exception as e:
            print(f"Warning: failed to read param file: {e}")
        
        return params
    
    def _convert_and_save_param_file(self, p2m_results: Dict) -> Optional[str]:
        """
        Read the best-iteration param file, convert to Spectre format, and save.

        Args:
            p2m_results: P2M result dict

        Returns:
            Path to the saved Spectre param file, or None on failure.
        """
        best_iteration = p2m_results.get('best_iteration')
        if not best_iteration:
            print("Warning: no best iteration info; skipping param conversion")
            return None
        
        iter_num = best_iteration.get('iteration', 0)
        if iter_num == 0:
            print("Warning: invalid iteration id; skipping param conversion")
            return None
        
        # Read HSPICE-format param file
        hspice_param_file = os.path.join(self.output_dir, f"iteration_{iter_num:02d}", "param")
        if not os.path.exists(hspice_param_file):
            print(f"Warning: param file does not exist: {hspice_param_file}")
            return None
        
        hspice_params = self._read_hspice_param_file(hspice_param_file)
        if not hspice_params:
            print("Warning: could not parse any parameters from param file; skipping conversion")
            return None
        
        # Determine circuit type and mapping
        circuit_type = self._get_circuit_type()
        if not circuit_type:
            print("Warning: could not determine circuit type; skipping param conversion")
            return None
        
        mapping = self._get_param_mapping(circuit_type)
        if not mapping:
            print(f"Warning: no param mapping for circuit type {circuit_type}; skipping param conversion")
            return None
        
        # Build Spectre-format param file content
        param_lines = []
        for hspice_var_name, spectre_var_name in mapping:
            if hspice_var_name not in hspice_params:
                print(f"Warning: HSPICE variable {hspice_var_name} not found; skipping")
                continue
            
            hspice_value = hspice_params[hspice_var_name]
            spectre_value = self._calculate_param_value(hspice_var_name, hspice_value)
            param_lines.append(f".param {spectre_var_name} = {spectre_value}")
        
        if not param_lines:
            print("Warning: no valid parameters to generate; skipping param conversion")
            return None
        
        # Save Spectre-format param file
        param_content = "\n".join(param_lines) + "\n"
        
        # Save into experiment directory
        spectre_param_file = os.path.join(self.output_dir, "param_spectre")
        param_file = os.path.join(self.output_dir, "param")  # Also save as `param` for copying
        
        try:
            with open(spectre_param_file, 'w', encoding='utf-8') as f:
                f.write(param_content)
            with open(param_file, 'w', encoding='utf-8') as f:
                f.write(param_content)
            print(f"Generated Spectre-format param file: {param_file}")
            return param_file
        except Exception as e:
            print(f"Error: failed to generate param file: {e}")
            return None
    
    def _copy_circuit_folder_to_example(self) -> Optional[str]:
        """
        Copy the entire circuit folder to example_white_box_param.

        Returns:
            Target folder path, or None on failure.
        """
        circuit_type = self._get_circuit_type()
        if not circuit_type:
            print("Warning: could not determine circuit type; skipping folder copy")
            return None
        
        source_dir_name = self._get_source_circuit_dir_name(circuit_type)
        if not source_dir_name:
            print(f"Warning: no source folder for circuit type {circuit_type}; skipping folder copy")
            return None
        
        target_dir_name = self._get_target_circuit_dir_name()
        if not target_dir_name:
            print("Warning: could not compute target folder name; skipping folder copy")
            return None
        
        source_path = os.path.join(self.gmid_map_base, "spectre_netlist_template", source_dir_name)
        target_path = os.path.join(self.gmid_map_base, "example_white_box_param", target_dir_name)
        
        if not os.path.exists(source_path):
            print(f"Error: source folder does not exist: {source_path}")
            return None
        
        # Ensure target parent exists
        target_parent = os.path.dirname(target_path)
        try:
            os.makedirs(target_parent, exist_ok=True)
        except Exception as e:
            print(f"Warning: failed to create target parent directory: {e}")
            return None
        
        # If target exists, remove it first
        if os.path.exists(target_path):
            try:
                shutil.rmtree(target_path)
            except Exception as e:
                print(f"Warning: failed to remove existing target directory: {e}")
                return None
        
        # Copy folder
        try:
            shutil.copytree(source_path, target_path)
            print(f"Copied circuit folder to: {target_path}")
            return target_path
        except Exception as e:
            print(f"Error: failed to copy folder: {e}")
            return None
    
    def _copy_param_to_circuit_folder(self, param_file: str, target_circuit_dir: str) -> bool:
        """
        Copy the param file into the new folder at circuit/param.

        Args:
            param_file: path to param file
            target_circuit_dir: target circuit folder path

        Returns:
            True if succeeded, otherwise False.
        """
        if not param_file or not os.path.exists(param_file):
            print("Warning: param file does not exist; skipping copy")
            return False
        
        target_param_file = os.path.join(target_circuit_dir, "circuit", "param")
        
        # Ensure target directory exists
        target_param_dir = os.path.dirname(target_param_file)
        try:
            os.makedirs(target_param_dir, exist_ok=True)
        except Exception as e:
            print(f"Warning: failed to create target directory: {e}")
            return False
        
        # Copy file
        try:
            shutil.copy2(param_file, target_param_file)
            print(f"Copied param file to: {target_param_file}")
            return True
        except Exception as e:
            print(f"Error: failed to copy param file: {e}")
            return False
    
    def _post_optimization_workflow(self, p2m_results: Dict) -> None:
        """
        Run post-processing workflow.

        Args:
            p2m_results: P2M result dict
        """
        print("\n" + "="*80)
        print("Running post-processing workflow")
        print("="*80)
        
        try:
            # 1. Copy best iteration simulation_verification to bl_hspice
            self._copy_best_iteration_to_bl_hspice(p2m_results)
            
            # 2. Copy Spectre template to bl_spectre
            self._copy_spectre_template_to_bl_spectre()
            
            # 3. Copy param file into bl_spectre/circuit/
            self._copy_param_to_bl_spectre()
            
            # 4. Run gmid_map mapping
            self._run_gmid_mapping()
            
            # 5. Generate summary report
            self._generate_summary_report(p2m_results)
            
            print("Post-processing workflow completed")
        except Exception as e:
            print(f"Warning: post-processing workflow failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _copy_best_iteration_to_bl_hspice(self, p2m_results: Dict) -> None:
        """
        Copy best iteration's simulation_verification to experiment directory as bl_hspice.

        Args:
            p2m_results: P2M result dict
        """
        try:
            best_iteration = p2m_results.get('best_iteration')
            if not best_iteration:
                print("Warning: no best iteration info; skipping copy of best-iteration folder")
                return
            
            iter_num = best_iteration.get('iteration', None)
            if iter_num is None:
                print("Warning: could not determine best iteration id; skipping copy of best-iteration folder")
                return
            
            # Build source and target paths
            source_path = os.path.join(self.output_dir, f"iteration_{iter_num:02d}", "simulation_verification")
            target_path = os.path.join(self.output_dir, "bl_hspice")
            
            if not os.path.exists(source_path):
                print(f"Warning: best-iteration folder does not exist: {source_path}")
                return
            
            # If target exists, remove it first
            if os.path.exists(target_path):
                try:
                    shutil.rmtree(target_path)
                except Exception as e:
                    print(f"Warning: failed to remove existing target directory: {e}")
                    return
            
            # Copy folder
            shutil.copytree(source_path, target_path)
            print(f"Copied best-iteration folder (iteration_{iter_num:02d}/simulation_verification) to: {target_path}")
        except Exception as e:
            print(f"Warning: failed to copy best-iteration folder: {e}")
    
    def _copy_spectre_template_to_bl_spectre(self) -> None:
        """
        Copy the corresponding Spectre template into the experiment directory as bl_spectre.
        """
        try:
            circuit_type = self._get_circuit_type()
            if not circuit_type:
                print("Warning: could not determine circuit type; skipping Spectre template copy")
                return
            
            source_dir_name = self._get_source_circuit_dir_name(circuit_type)
            if not source_dir_name:
                print(f"Warning: no source folder for circuit type {circuit_type}; skipping Spectre template copy")
                return
            
            # Build source and target paths
            source_path = os.path.join(self.gmid_map_base, "spectre_netlist_template", source_dir_name)
            target_path = os.path.join(self.output_dir, "bl_spectre")
            
            if not os.path.exists(source_path):
                print(f"Warning: Spectre template folder does not exist: {source_path}")
                return
            
            # If target exists, remove it first
            if os.path.exists(target_path):
                try:
                    shutil.rmtree(target_path)
                except Exception as e:
                    print(f"Warning: failed to remove existing target directory: {e}")
                    return
            
            # Copy folder
            shutil.copytree(source_path, target_path)
            print(f"Copied Spectre template to: {target_path}")
        except Exception as e:
            print(f"Warning: failed to copy Spectre template: {e}")
    
    def _copy_param_to_bl_spectre(self) -> None:
        """
        Copy the generated Spectre-format param file into bl_spectre/circuit/.
        """
        try:
            param_file = os.path.join(self.output_dir, "param")
            target_param_file = os.path.join(self.output_dir, "bl_spectre", "circuit", "param")
            
            if not os.path.exists(param_file):
                print(f"Warning: param file does not exist: {param_file}")
                return
            
            # Ensure target directory exists
            target_param_dir = os.path.dirname(target_param_file)
            os.makedirs(target_param_dir, exist_ok=True)
            
            # Copy file
            shutil.copy2(param_file, target_param_file)
            print(f"Copied param file to: {target_param_file}")
        except Exception as e:
            print(f"Warning: failed to copy param file to bl_spectre: {e}")
    
    def _run_gmid_mapping(self) -> None:
        """
        Run gmid_map tool for mapping.
        """
        try:
            import subprocess
            
            # Use absolute paths to avoid resolution issues when running under gmid_map directory
            bl_spectre_path = os.path.abspath(os.path.join(self.output_dir, "bl_spectre"))
            tl_spectre_path = os.path.abspath(os.path.join(self.output_dir, "tl_spectre"))
            
            if not os.path.exists(bl_spectre_path):
                print(f"Warning: bl_spectre directory does not exist: {bl_spectre_path}")
                return
            
            # Build path to gmid_map/main.py (absolute path)
            gmid_map_main = os.path.abspath(os.path.join(self.gmid_map_base, "main.py"))
            if not os.path.exists(gmid_map_main):
                print(f"Warning: gmid_map/main.py does not exist: {gmid_map_main}")
                return
            
            # Build command (absolute paths)
            # Include --TITLE, --MAP, --SIM, --OUT and design requirement args
            # NOTE: run via bash to source EDA env script first
            # Users should set their own EDA environment script path here or via environment variable
            eda_bash_path = os.environ.get("EDA_BASH_PATH", "/path/to/eda.bash")
            python_cmd = (
                f"python3 {gmid_map_main} "
                f"--TITLE "
                f"--input_circuit_dir {bl_spectre_path} "
                f"--output_circuit_dir {tl_spectre_path} "
                f"--MAP --SIM --OUT "
                f"--gain_target {self.design_req.gain_min_db} "
                f"--pm_lower {self.design_req.pm_min_deg} "
                f"--pm_upper {self.design_req.pm_max_deg} "
                f"--gbw_target {self.design_req.gbw_min_mhz} "
                f"--power_target {self.design_req.power_max_uw} "
                f"--c_load 10.0"
            )
            
            # Run via bash -c: source EDA env, then execute python command
            cmd = [
                "bash", "-c",
                f"source {eda_bash_path} && cd {self.gmid_map_base} && {python_cmd}"
            ]
            
            print("[Info] Running gmid_map for mapping, simulation, and output generation...")
            print(f"[Info] Input dir: {bl_spectre_path}")
            print(f"[Info] Output dir: {tl_spectre_path}")
            print(f"[Info] Specs: gain>={self.design_req.gain_min_db}dB, "
                  f"pm={self.design_req.pm_min_deg}°-{self.design_req.pm_max_deg}°, "
                  f"gbw>={self.design_req.gbw_min_mhz}MHz, power<={self.design_req.power_max_uw}μW")
            
            # Run inside gmid_map directory
            original_dir = os.getcwd()
            try:
                os.chdir(self.gmid_map_base)
                result = subprocess.run(
                    cmd,
                    cwd=self.gmid_map_base,
                    capture_output=True,
                    text=True,
                    timeout=3600  # 1 hour timeout
                )
                
                if result.returncode == 0:
                    print("gmid_map completed")
                    if os.path.exists(tl_spectre_path):
                        print(f"Mapping output saved to: {tl_spectre_path}")
                    else:
                        print(f"Warning: mapping output directory does not exist: {tl_spectre_path}")
                else:
                    print(f"Warning: gmid_map failed, return code: {result.returncode}")
                    if result.stdout:
                        print(f"[Output] {result.stdout}")
                    if result.stderr:
                        print(f"[Error] {result.stderr}")
            finally:
                os.chdir(original_dir)
                
        except subprocess.TimeoutExpired:
            print("Warning: gmid_map timed out")
        except Exception as e:
            print(f"Warning: failed to run gmid_map: {e}")
            import traceback
            traceback.print_exc()
    
    def _generate_summary_report(self, p2m_results: Dict) -> None:
        """
        Generate a summary report file.

        Args:
            p2m_results: P2M result dict
        """
        try:
            report_file = os.path.join(self.output_dir, "optimization_summary.txt")
            
            report = []
            report.append("=" * 80)
            report.append("Optimization Summary Report")
            report.append("=" * 80)
            report.append(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("")
            
            # Behavioral-level optimization results
            report.append("## Behavioral-level Optimization Results")
            report.append("")
            
            best_iteration = p2m_results.get('best_iteration')
            if best_iteration:
                quality_info = best_iteration.get('quality_info', {})
                has_performance = quality_info.get('has_performance', False)
                
                if has_performance:
                    perf = quality_info.get('performance', {})
                    # Extract behavioral-level metrics
                    bl_gain = perf.get('gain', 0)
                    bl_gbw = perf.get('ugf', 0) / 1e6  # Convert to MHz
                    bl_pm = perf.get('phase_margin', 0)
                    bl_power = perf.get('power', 0) * 1e6  # Convert to μW
                    bl_fom = perf.get('fom', 0)
                    
                    # Extract optimal parameters (from param file)
                    iter_num = best_iteration.get('iteration', 0)
                    best_params = {}
                    if iter_num > 0:
                        param_file = os.path.join(self.output_dir, f"iteration_{iter_num:02d}", "param")
                        if os.path.exists(param_file):
                            best_params = self._read_hspice_param_file(param_file)
                    
                    # Extract optimization statistics
                    iteration_count = p2m_results.get('iteration_count', 0)
                    total_time_minutes = p2m_results.get('total_time_minutes', None)
                    
                    report.append("Performance Metrics:")
                    report.append(f"  - FoM: {bl_fom:.2f}")
                    report.append(f"  - Gain: {bl_gain:.2f} dB")
                    report.append(f"  - GBW: {bl_gbw:.2f} MHz")
                    report.append(f"  - Phase Margin: {bl_pm:.2f}°")
                    report.append(f"  - Power: {bl_power:.2f} μW")
                    report.append("")
                    
                    report.append("Optimization Statistics:")
                    report.append(f"  - Best Iteration: {iter_num}")
                    report.append(f"  - Total Iterations: {iteration_count}")
                    if total_time_minutes is not None:
                        report.append(f"  - Total Time: {total_time_minutes:.2f} minutes")
                    report.append("")
                    
                    if best_params:
                        report.append("Optimal Parameters:")
                        for param_name, param_value in sorted(best_params.items()):
                            report.append(f"  {param_name} = {param_value}")
                        report.append("")
                else:
                    report.append("⚠️  No performance data available")
                    report.append("")
            else:
                report.append("⚠️  No best iteration information")
                report.append("")
            
            # Transistor-level mapping results
            report.append("## Transistor-level Mapping Results")
            report.append("")
            tl_spectre_path = os.path.join(self.output_dir, "tl_spectre")
            sim_out_path = os.path.join(tl_spectre_path, "sim.out")
            
            if os.path.exists(sim_out_path):
                try:
                    # Read sim.out file
                    with open(sim_out_path, 'r') as f:
                        lines = f.readlines()
                    
                    # Find data line (usually line 3, skip empty lines)
                    data_line = None
                    for line in lines:
                        stripped = line.strip()
                        if stripped and not stripped.startswith('#'):
                            # Check if contains numbers (likely data line)
                            parts = stripped.split()
                            if len(parts) >= 4:
                                try:
                                    # Try to parse as floats
                                    float(parts[0])
                                    float(parts[1])
                                    float(parts[2])
                                    float(parts[3])
                                    data_line = stripped
                                    break
                                except ValueError:
                                    continue
                    
                    if data_line:
                        parts = data_line.split()
                        # First 4 fields: gain (dB), pm (deg), gbw (Hz), power (W)
                        tl_gain = float(parts[0])
                        tl_pm = float(parts[1])
                        tl_gbw_hz = float(parts[2])
                        tl_power_w = float(parts[3])
                        
                        # Unit conversion
                        tl_gbw = tl_gbw_hz / 1e6  # Hz -> MHz
                        tl_power = tl_power_w * 1e6  # W -> μW
                        
                        # Calculate FoM (using default c_load=10.0 pF)
                        c_load = 10.0  # pF
                        tl_fom = tl_gbw * c_load / (tl_power * 1e-3)  # Formula: gbw * c_load / (power * 1e-3)
                        
                        report.append("Performance Metrics:")
                        report.append(f"  - FoM: {tl_fom:.2f}")
                        report.append(f"  - Gain: {tl_gain:.2f} dB")
                        report.append(f"  - GBW: {tl_gbw:.2f} MHz")
                        report.append(f"  - Phase Margin: {tl_pm:.2f}°")
                        report.append(f"  - Power: {tl_power:.2f} μW")
                    else:
                        report.append("⚠️  Failed to parse sim.out file")
                except Exception as e:
                    report.append(f"⚠️  Failed to read transistor-level results: {e}")
            else:
                report.append("⚠️  Transistor-level simulation results not found")
                report.append(f"    (Expected file: {sim_out_path})")
            report.append("")
            
            # File path information
            report.append("## File Path Information")
            report.append("")
            report.append(f"Experiment Directory: {self.output_dir}")
            report.append(f"Behavioral-level HSPICE Results: {os.path.join(self.output_dir, 'bl_hspice')}")
            report.append(f"Behavioral-level Spectre Results: {os.path.join(self.output_dir, 'bl_spectre')}")
            report.append(f"Transistor-level Spectre Results: {os.path.join(self.output_dir, 'tl_spectre')}")
            report.append("")
            
            # Write to file
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(report))
            
            print(f"✅ Summary report generated: {report_file}")
        except Exception as e:
            print(f"⚠️  Warning: Failed to generate summary report: {e}")
            import traceback
            traceback.print_exc()

