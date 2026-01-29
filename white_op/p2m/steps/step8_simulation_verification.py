"""
Step 8: Generate Numerical Netlist

Based on the white-box optimization results from Step 7, extract design variables, generate parameterized netlists and testbenches for HSPICE, and execute simulation verification.
"""

import os
import re
import subprocess
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from p2m.pipeline import CircuitAnalysisPipeline

from core import load_prompt_from_file
from core.logger import get_logger


def step8_generate_numerical_netlist(
    pipeline: 'CircuitAnalysisPipeline',
    optimization_results: Dict = None
) -> Dict:
    """Step 8: Generate parameterized netlist (improved version: intelligent extraction + direct file operations)"""
    # Step logger: console only shows WARNING and above, reduce detailed output
    import logging
    logger = get_logger(
        name='step8', 
        module=__name__,
        console=True,
        file=True,
        level=logging.DEBUG,  # File saves all levels
        console_level=logging.WARNING  # Console only shows WARNING and ERROR, reduce output
    )
    
    # Update counters (consistent with other steps)
    pipeline.global_step_count += 1
    pipeline.step_count += 1
    
    step_name = "simulation_verification"
    # Detailed step information changed to DEBUG level to reduce console output
    logger.debug("\n" + "="*60)
    logger.debug(f"Step 8: {step_name}")
    logger.debug("="*60)
    logger.debug(f"[Step {pipeline.step_count}] {step_name}")
    logger.debug(f"[Global Step {pipeline.global_step_count}] [Iteration {pipeline.iteration_count + 1}]")
    logger.debug("-" * 50)
    # Keep only key information at INFO level
    logger.info(f"Step 8: {step_name} (Iteration {pipeline.iteration_count + 1})")
    
    # Build step description (for saving files)
    step_description = """# Step 8: Generate Numerical Netlist

Based on the white-box optimization results from Step 7, extract design variables, generate parameterized netlists and testbenches for HSPICE, and execute simulation verification.

Main tasks:
1. Intelligently extract design variables from optimization results
2. Generate .param parameter file
3. Generate netlist template and testbench
4. Execute HSPICE simulation and verify performance metrics
"""
    
    if not optimization_results or not optimization_results.get('success', False):
        logger.error("❌ Step 7 optimization failed, cannot generate parameterized netlist")
        error_response = "Step 7 optimization failed, cannot obtain design variables"
        error_file = pipeline.save_response(step_name, error_response, step_description, is_full=False)
        return {
            'success': False,
            'step': step_name,
            'step_number': 8,  # Step 8: Generate Numerical Netlist
            'error': error_response,
            'saved_file': error_file
        }
    
    execution_results = optimization_results.get('execution_results', [])
    if not execution_results:
        logger.error("❌ Step 7 execution results not found")
        error_response = "Step 7 execution results not found"
        error_file = pipeline.save_response(step_name, error_response, step_description, is_full=False)
        return {
            'success': False,
            'step': step_name,
            'step_number': 8,  # Step 8: Generate Numerical Netlist
            'error': error_response,
            'saved_file': error_file
        }
    
    # 1. Intelligently extract design variables (using LLM)
    logger.debug("🔍 Intelligently extracting design variables...")
    design_vars = _intelligent_extract_design_variables(pipeline, execution_results[0])
    if not design_vars:
        logger.error("❌ Failed to extract design variables")
        error_response = "Failed to extract design variables from optimization results"
        error_file = pipeline.save_response(step_name, error_response, step_description, is_full=False)
        return {
            'success': False,
            'step': step_name,
            'step_number': 8,  # Step 8: Generate Numerical Netlist
            'error': error_response,
            'saved_file': error_file
        }
    
    # 2. Directly generate files (pipeline script processing)
    logger.info("📝 Generating parameter file...")
    param_file = _generate_param_file_direct(pipeline, design_vars)
    
    logger.info("📝 Generating performance metrics file...")
    perf_file = _generate_performance_file_direct(pipeline, execution_results[0])
    
    logger.info("📝 Copying netlist template...")
    template_file = _copy_netlist_template_direct(pipeline)
    
    logger.info("📝 Generating final testbench...")
    testbench_file = _generate_testbench_direct(pipeline)
    
    # 3. Execute HSPICE simulation
    logger.info("🔬 Executing HSPICE simulation...")
    sim_results = _execute_hspice_simulation_direct(
        pipeline, testbench_file, param_file, template_file, execution_results[0]
    )
    
    # Determine if simulation is successful
    is_success = False
    if sim_results:
        # If returned dict contains 'success' field, directly judge
        if 'success' in sim_results:
            is_success = sim_results.get('success', False)
        # If contains 'gain' field, indicates successful result (old format)
        elif 'gain' in sim_results:
            is_success = True
    
    if is_success:
        # Simulation successful
        logger.debug("✅ HSPICE simulation completed")
        
        # Generate comprehensive response content, including all key information
        response_content = f"""# Step 8: Generate Numerical Netlist - Execution Complete

## Design Variable Parameters
```spice
{_format_param_content(design_vars)}
```

## Performance Metrics
{pipeline._extract_optimization_performance(execution_results[0] if execution_results else '')}

## HSPICE Simulation Results
- **Gain**: {sim_results['gain']:.2f} dB
- **Bandwidth**: {sim_results['ugf']/1e6:.2f} MHz  
- **Phase Margin**: {sim_results['phase_margin']:.2f}°
- **Power**: {sim_results['power']*1e6:.2f} μW
- **FoM**: {sim_results['fom']:.2f}

## Generated Files
- Parameter file: {os.path.basename(param_file)}
- Netlist template: {os.path.basename(template_file)}
- Testbench: {os.path.basename(testbench_file)}
- Performance metrics: {os.path.basename(perf_file)}

## Simulation Verification Status
✅ HSPICE simulation completed successfully, all performance metrics obtained
"""
        
        # Save response to clean file (consistent with other steps)
        clean_file = pipeline.save_response(step_name, response_content, step_description, is_full=False)
        # step8 has no thinking content, so full and clean content are the same
        full_file = pipeline.save_response(step_name, response_content, step_description, is_full=True)
        
        logger.info(f"✓ {step_name} completed")
        
        # Ensure sim_results contains sim_dir (if not already)
        if sim_results and 'sim_dir' not in sim_results:
            sim_dir = f"{pipeline.config.output_dir}/simulation_verification"
            sim_results['sim_dir'] = sim_dir
        
        return {
            'success': True,
            'step': step_name,
            'step_number': 8,  # Step 8: Generate Numerical Netlist
            'response': response_content,
            'saved_file': clean_file,
            'full_file': full_file,
            'param_file': param_file,
            'perf_file': perf_file,
            'template_file': template_file,
            'testbench_file': testbench_file,
            'simulation_results': sim_results
        }
    
    # Simulation failed: read lis file and analyze with LLM
    logger.error("❌ HSPICE simulation failed, analyzing error log...")
    
    # Extract error information
    lis_content = ""
    stderr = ""
    returncode = None
    if isinstance(sim_results, dict):
        lis_content = sim_results.get('lis_content', '')
        stderr = sim_results.get('stderr', '')
        returncode = sim_results.get('returncode')
    
    # If lis_content is empty, try to read file directly
    if not lis_content:
        sim_dir = f"{pipeline.config.output_dir}/simulation_verification"
        lis_file = os.path.join(sim_dir, "testbench.lis")
        if os.path.exists(lis_file):
            try:
                with open(lis_file, 'r', encoding='utf-8', errors='ignore') as f:
                    lis_content = f.read()
                logger.error(f"📄 Error log file read: {lis_file}")
            except Exception as e:
                logger.error(f"⚠️ Failed to read lis file: {e}")
    
    # Use LLM to analyze failure reason
    failure_analysis_result = _analyze_simulation_failure(
        pipeline,
        lis_content=lis_content,
        stderr=stderr,
        returncode=returncode,
        netlist=pipeline.original_netlist
    )
    
    # Build detailed error response
    response_content = f"""# Step 8: Generate Numerical Netlist - Simulation Failed

## Error Information
HSPICE simulation execution failed, unable to obtain performance data.

## Intelligent Error Analysis

### Failure Cause Analysis
{failure_analysis_result.get('failure_analysis', 'Unable to analyze')}

### Error Location
{failure_analysis_result.get('error_location', 'Unknown')}

### Suggested Fix Methods
{failure_analysis_result.get('suggested_fix', 'No suggestions')}

## Generated Files
- Parameter file: {os.path.basename(param_file)}
- Netlist template: {os.path.basename(template_file)}
- Testbench: {os.path.basename(testbench_file)}
- Performance metrics: {os.path.basename(perf_file)}

## Simulation Verification Status
❌ HSPICE simulation failed, please fix according to the above analysis
"""
    
    # Save response to clean file (consistent with other steps)
    clean_file = pipeline.save_response(step_name, response_content, step_description, is_full=False)
    # step8 has no thinking content, so full and clean content are the same
    full_file = pipeline.save_response(step_name, response_content, step_description, is_full=True)
    
    logger.debug(f"✗ {step_name} failed")
    
    return {
        'success': False,
        'step': step_name,
        'step_number': 8,  # Step 8: Generate Numerical Netlist
        'response': response_content,
        'saved_file': clean_file,
        'full_file': full_file,
            'error': 'HSPICE simulation failed',
        'failure_analysis': failure_analysis_result,
        'lis_content': lis_content[:5000] if lis_content else ''  # Save partial lis content for later use
    }


# ========== Helper Functions ==========

def _format_param_content(design_vars: Dict) -> str:
    """Format parameter content as SPICE format"""
    param_lines = []
    for param_name, param_value in design_vars.items():
        param_lines.append(f".param {param_name} = {param_value}")
    return "\n".join(param_lines)


# Note: The following methods remain in pipeline.py because they are used elsewhere:
# - _get_execution_log_string: Used by parse_simulation_results and _build_best_solution_detailed_summary
# - _extract_design_vars: Used by _build_best_solution_detailed_summary
# - _extract_optimization_performance: Used by _generate_performance_file_direct and step9
# step8 file calls these methods via pipeline parameter


def _intelligent_extract_design_variables(pipeline: 'CircuitAnalysisPipeline', execution_log) -> Dict:
    """Intelligently extract design variables (using LLM)
    
    Args:
        pipeline: CircuitAnalysisPipeline instance
        execution_log: Can be a string or dict (containing 'stdout' field)
    """
    # Create logger (helper functions need their own logger)
    import logging
    logger = get_logger(
        name='step8_helper',
        module=__name__,
        console=True,
        file=True,
        level=logging.DEBUG,
        console_level=logging.WARNING  # Helper function logs also only show WARNING and above on console
    )
    
    # Convert to string uniformly (via pipeline call)
    log_string = pipeline._get_execution_log_string(execution_log)
    
    # Read simplified prompt template from file
    prompt_file = os.path.join(pipeline.prompts_dir, "step8_simulation_verification.md")
    prompt_template = load_prompt_from_file(prompt_file)
    
    # Build complete prompt
    # Note: No longer using script to extract variable list, let LLM identify all variables that need to be defined from the original netlist
    prompt = f"""{prompt_template}

## Optimization Results
{log_string}

## Original Netlist
{pipeline.original_netlist}

Please analyze the above optimization results and original netlist, identify all variables in the original netlist that need to be defined (variables in single quotes), establish parameter mapping relationships, and output .param statements."""
    logger.info(prompt)
    try:
        # Call API for intelligent extraction
        messages = [{"role": "user", "content": prompt}]
        api_result = pipeline.call_api(messages)
        
        if api_result:
            clean_response, _ = api_result
            logger.info(clean_response)
            # First check if there is a param_error tag (indicating inability to determine all variables)
            param_error = pipeline.extract_tagged_content(clean_response, 'param_error')
            if param_error:
                logger.warning(f"⚠️ Warning: Step 8 detected missing variable issue")
                logger.error(f"   Error message: {param_error[:500]}")
                # Return None to let upper level handle error
                return None
            
            # Extract param tag content
            param_content = pipeline.extract_tagged_content(clean_response, 'param')
            if param_content:
                # Parse parameters into dictionary
                param_dict = {}
                for line in param_content.split('\n'):
                    if line.strip().startswith('.param'):
                        parts = line.strip().split('=')
                        if len(parts) == 2:
                            param_name = parts[0].replace('.param', '').strip()
                            param_value = parts[1].strip()
                            param_dict[param_name] = param_value
                
                # Secondary validation: Check if all required variables are included (as a safety check)
                # Note: Main flow is for LLM to identify variables from original netlist itself, this is just a secondary check
                netlist_vars = set(re.findall(r"'([A-Za-z_][A-Za-z0-9_]*)'", pipeline.original_netlist))
                missing_vars = netlist_vars - set(param_dict.keys())
                
                if missing_vars:
                    logger.warning(f"⚠️ Warning: Step 8 generated .param file missing the following variables: {missing_vars}")
                    logger.info(f"   These variables may use default values (please check the response for explanation)")
                    logger.info(f"   Or LLM may have missed some variables (please check the original netlist)")
                    # Still return partial results, allowing cases with default values
                    # If strict validation is needed, can return None
                
                return param_dict
        
        return None
    except Exception as e:
        logger.error(f"Intelligent extraction failed: {e}")
        return None


def _validate_and_fix_param_values(pipeline: 'CircuitAnalysisPipeline', design_vars: Dict, logger) -> Dict:
    """Validate and fix parameter values in param file
    
    Main checks:
    1. Whether rprs values are reasonable (if rprs is a fixed value, calculate A value from G value, verify if A is in 40-80 range)
    2. Whether A values are in reasonable range (40-80)
    
    Args:
        pipeline: CircuitAnalysisPipeline instance
        design_vars: Parameter dictionary
        logger: logger instance
    
    Returns:
        Corrected parameter dictionary
    """
    import re
    
    # Extract all G values and rprs values
    g_values = {}
    rprs_values = {}
    a_values = {}
    
    # Match G parameters (e.g., g_net_vin_net_1, G_1, etc.)
    for param_name, param_value in design_vars.items():
        # Extract G value
        g_match = re.match(r'g[_]?(\d+|net_\w+|\w+)', param_name.lower())
        if g_match:
            try:
                g_val = float(param_value)
                g_values[param_name] = g_val
            except (ValueError, TypeError):
                pass
        
        # Extract rprs value
        if 'rprs' in param_name.lower():
            try:
                rprs_val = float(param_value)
                rprs_values[param_name] = rprs_val
            except (ValueError, TypeError):
                # If rprs is an expression (e.g., 'A_1/G_1'), skip validation
                pass
        
        # Extract A value (if exists)
        a_match = re.match(r'a[_]?(\d+|f\d+)', param_name.lower())
        if a_match:
            try:
                a_val = float(param_value)
                a_values[param_name] = a_val
            except (ValueError, TypeError):
                pass
    
    # Validate relationship between rprs and A
    # In netlist, rprs definition is usually 'A_i/G_i', so A = rprs * G
    # If rprs is a fixed value, need to verify if corresponding A value is reasonable
    for rprs_name, rprs_val in rprs_values.items():
        # Try to find corresponding G parameter
        # rprs_net_vin_net_1 corresponds to g_net_vin_net_1
        # rprs_1 corresponds to G_1 or g_1
        g_name = None
        g_val = None
        
        # Strategy 1: Directly replace rprs with g
        g_name_candidate1 = rprs_name.replace('rprs', 'g', 1)
        if g_name_candidate1 in g_values:
            g_name = g_name_candidate1
            g_val = g_values[g_name_candidate1]
        else:
            # Strategy 2: Try to match numbers or identifiers
            match = re.search(r'rprs[_]?(\d+|net_\w+|\w+)', rprs_name.lower())
            if match:
                suffix = match.group(1)
                # Try multiple possible G names
                for candidate in [f'g_{suffix}', f'g{suffix}', f'G_{suffix}', f'G{suffix}']:
                    if candidate in g_values:
                        g_name = candidate
                        g_val = g_values[candidate]
                        break
                    # Also try to find in design_vars (may have different case)
                    for key in design_vars.keys():
                        if key.lower() == candidate.lower():
                            try:
                                g_val = float(design_vars[key])
                                g_name = key
                                break
                            except (ValueError, TypeError):
                                pass
                    if g_name:
                        break
        
        if g_val is not None and g_val > 0:
            # Calculate A value: A = rprs * G
            # Note: G unit may be uS (microsiemens), need to convert to S
            # If G value is small (<1), may be in S unit; if G value is large (>1), may be in uS unit
            if g_val < 1:
                g_s = g_val  # Already in S unit
            else:
                g_s = g_val * 1e-6  # Convert from uS to S
            
            # rprs unit is Ohm, so A = rprs * G (S) = (Ohm) * (S) = dimensionless
            calculated_a = rprs_val * g_s
            
            # Verify if A value is in reasonable range (40-80)
            if calculated_a < 40 or calculated_a > 80:
                logger.warning(f"⚠️ Warning: Parameter {rprs_name} = {rprs_val}, corresponding G value {g_name} = {g_val}, calculated A value = {calculated_a:.2f}, exceeds reasonable range (40-80)")
                logger.warning(f"   Suggestion: Check if A value in optimization output is correct, or check if rprs calculation is correct")
                
                # If A value exceeds range, try to correct rprs value
                # Assume A value should be in 40-80 range, calculate reasonable rprs value
                if calculated_a > 80:
                    # A too large, reduce rprs
                    target_a = 80
                    corrected_rprs = target_a / g_s
                    logger.warning(f"   Correction suggestion: Set {rprs_name} to {corrected_rprs:.2f} (corresponding A={target_a})")
                elif calculated_a < 40:
                    # A too small, increase rprs
                    target_a = 40
                    corrected_rprs = target_a / g_s
                    logger.warning(f"   Correction suggestion: Set {rprs_name} to {corrected_rprs:.2f} (corresponding A={target_a})")
    
    # Validate directly defined A values
    for a_name, a_val in a_values.items():
        if a_val < 40 or a_val > 80:
            logger.warning(f"⚠️ Warning: Parameter {a_name} = {a_val}, exceeds reasonable range (40-80)")
    
    return design_vars


def _generate_param_file_direct(pipeline: 'CircuitAnalysisPipeline', design_vars: Dict) -> str:
    """Directly generate parameter file (pipeline script processing)"""
    # Create logger (helper functions need their own logger)
    import logging
    logger = get_logger(
        name='step8_helper',
        module=__name__,
        console=True,
        file=True,
        level=logging.DEBUG,
        console_level=logging.WARNING  # Helper function logs also only show WARNING and above on console
    )
    
    # Validate and fix parameter values
    design_vars = _validate_and_fix_param_values(pipeline, design_vars, logger)
    
    param_file = os.path.join(pipeline.config.output_dir, "param")
    
    with open(param_file, 'w') as f:
        for param_name, param_value in design_vars.items():
            f.write(f".param {param_name} = {param_value}\n")
    
    logger.debug(f"Parameter file generated: {param_file}")  # Changed to DEBUG level to reduce console output
    return param_file


def _generate_performance_file_direct(pipeline: 'CircuitAnalysisPipeline', execution_log) -> str:
    """Directly generate performance metrics file (pipeline script processing)
    
    Args:
        pipeline: CircuitAnalysisPipeline instance
        execution_log: Can be a string or dict (containing 'stdout' field)
    """
    # Create logger (helper functions need their own logger)
    import logging
    logger = get_logger(
        name='step8_helper',
        module=__name__,
        console=True,
        file=True,
        level=logging.DEBUG,
        console_level=logging.WARNING  # Helper function logs also only show WARNING and above on console
    )
    
    perf_file = os.path.join(
        pipeline.config.output_dir,
        f"iter{pipeline.iteration_count + 1:02d}_step{pipeline.step_count:02d}_global{pipeline.global_step_count:02d}_generate_numerical_netlist_perf.txt"
    )
    
    # Extract performance metrics (via pipeline call)
    performance_text = pipeline._extract_optimization_performance(execution_log)
    
    with open(perf_file, 'w') as f:
        f.write("Performance metrics based on Step 7 optimization results:\n")
        f.write(performance_text)
        f.write("\n\nTarget requirements:\n")
        f.write("- Gain: > 60 dB\n")
        f.write("- Bandwidth: > 0.5 MHz\n")
        f.write("- Phase margin: 55-65° (ideal: 60°)\n")
        f.write("- Power: < 250 μW\n")
    
    logger.debug(f"Performance metrics file generated: {perf_file}")  # Changed to DEBUG level to reduce console output
    return perf_file


def _copy_netlist_template_direct(pipeline: 'CircuitAnalysisPipeline') -> str:
    """Directly copy netlist template (pipeline script processing)"""
    # Create logger (helper functions need their own logger)
    import logging
    logger = get_logger(
        name='step8_helper',
        module=__name__,
        console=True,
        file=True,
        level=logging.DEBUG,
        console_level=logging.WARNING  # Helper function logs also only show WARNING and above on console
    )
    
    template_file = os.path.join(
        pipeline.config.output_dir,
        f"iter{pipeline.iteration_count + 1:02d}_step{pipeline.step_count:02d}_global{pipeline.global_step_count:02d}_generate_numerical_netlist.sp"
    )
    
    with open(template_file, 'w') as f:
        f.write(pipeline.original_netlist)
    
    logger.debug(f"Netlist template generated: {template_file}")  # Changed to DEBUG level to reduce console output
    return template_file


def _generate_testbench_direct(pipeline: 'CircuitAnalysisPipeline') -> str:
    """Directly generate testbench file (pipeline script processing)"""
    # Create logger (helper functions need their own logger)
    import logging
    logger = get_logger(
        name='step8_helper',
        module=__name__,
        console=True,
        file=True,
        level=logging.DEBUG,
        console_level=logging.WARNING  # Helper function logs also only show WARNING and above on console
    )
    
    testbench_file = os.path.join(
        pipeline.config.output_dir,
        f"iter{pipeline.iteration_count + 1:02d}_step{pipeline.step_count:02d}_global{pipeline.global_step_count:02d}_generate_numerical_netlist_final.sp"
    )
    
    # Fixed testbench template
    testbench_content = f""".title Project: Three-Stage Opamp
.inc 'opamp.sp'
.inc 'param'

xac vin_ac vo_ac gnd opamp
vin vin_ac 0 ac=1

.OPTIONS INGOLD=0
.option post=2
.op
.ac dec 100 1 1g
.print vdb(vo_ac)
.print vp(vo_ac)
.meas ac gain find vdb(vo_ac) at=1
.meas ac ugf when vdb(vo_ac)=0
.meas ac phase FIND vp(vo_ac) at=ugf
.pz v(vo_ac) vin
.TEMP 27
.end"""
    
    with open(testbench_file, 'w') as f:
        f.write(testbench_content)
    
    logger.debug(f"Testbench file generated: {testbench_file}")  # Changed to DEBUG level to reduce console output
    return testbench_file


def _execute_hspice_simulation_direct(
    pipeline: 'CircuitAnalysisPipeline',
    testbench_file: str,
    param_file: str,
    template_file: str,
    execution_log = None
) -> Dict:
    """Directly execute HSPICE simulation (pipeline script processing)
    
    Note: This function now checks configuration, if remote execution is enabled, it will use remote HSPICE executor.
    Otherwise use local HSPICE execution.
    
    Args:
        pipeline: CircuitAnalysisPipeline instance
        testbench_file: Testbench file path
        param_file: Parameter file path
        template_file: Netlist template file path
        execution_log: Can be a string or dict (containing 'stdout' field), used to extract power consumption value
    """
    # Create logger (helper functions need their own logger)
    import logging
    logger = get_logger(
        name='step8_helper',
        module=__name__,
        console=True,
        file=True,
        level=logging.DEBUG,
        console_level=logging.WARNING  # Helper function logs also only show WARNING and above on console
    )
    # Create simulation directory
    sim_dir = f"{pipeline.config.output_dir}/simulation_verification"
    os.makedirs(sim_dir, exist_ok=True)
    
    # Copy files to simulation directory
    sim_testbench = os.path.join(sim_dir, "testbench.sp")
    sim_param = os.path.join(sim_dir, "param")
    sim_opamp = os.path.join(sim_dir, "opamp.sp")
    
    # Copy testbench
    with open(testbench_file, 'r') as f:
        testbench_content = f.read()
    with open(sim_testbench, 'w') as f:
        f.write(testbench_content)
    
    # Copy parameter file
    with open(param_file, 'r') as f:
        param_content = f.read()
    with open(sim_param, 'w') as f:
        f.write(param_content)
    
    # Copy netlist template
    with open(template_file, 'r') as f:
        template_content = f.read()
    with open(sim_opamp, 'w') as f:
        f.write(template_content)
    
    # Check if remote execution is enabled
    logger.info(f"🔍 Checking remote HSPICE configuration: hspice_remote_enabled={pipeline.config.hspice_remote_enabled}")
    
    if pipeline.config.hspice_remote_enabled:
        # Use remote HSPICE execution (via pipeline method)
        logger.info("🌐 Using remote HSPICE execution mode")
        print("🌐 Using remote HSPICE execution mode")  # Force output to console
        try:
            from core import RemoteHspiceExecutor
            from core.exceptions import HSPICETimeoutError, HSPICESimulationError
            
            # Create remote executor
            remote_executor = RemoteHspiceExecutor(pipeline.config, logger=logger)
            
            # Prepare input file list
            input_files = [sim_testbench]
            
            # Prepare additional files
            additional_files = []
            if os.path.exists(sim_param):
                additional_files.append(sim_param)
            if os.path.exists(sim_opamp):
                additional_files.append(sim_opamp)
            
            # Execute remote HSPICE simulation
            result_files = remote_executor.execute_remote(
                input_files=input_files,
                output_name="testbench",
                local_output_dir=sim_dir,
                additional_files=additional_files if additional_files else None
            )
            
            # Check result files
            logger.info(f"📦 Files returned from remote execution: {list(result_files.keys())}")
            performance_file = os.path.join(sim_dir, "testbench.ma0")
            
            if '.ma0' in result_files:
                performance_file = result_files['.ma0']
                logger.info(f"✅ Found .ma0 file: {performance_file}")
                if os.path.exists(performance_file):
                    logger.info(f"✅ .ma0 file exists, starting parsing...")
                    try:
                        sim_results = pipeline.parse_simulation_results(performance_file, execution_log, sim_dir)
                        if sim_results:
                            sim_results['success'] = True
                            sim_results['sim_dir'] = sim_dir
                            logger.info(f"✅ Simulation results parsed successfully: gain={sim_results.get('gain', 'N/A')} dB")
                            return sim_results
                        else:
                            logger.warning("⚠️ parse_simulation_results returned None")
                    except Exception as e:
                        logger.error(f"❌ Failed to parse .ma0 file: {e}")
                        import traceback
                        logger.error(f"Full stack trace: {traceback.format_exc()}")
                else:
                    logger.error(f"❌ .ma0 file does not exist: {performance_file}")
            else:
                logger.warning("⚠️ .ma0 file not found in files returned from remote execution")
            
            # If no .ma0 file, try to read .lis file to get error information
            lis_file = os.path.join(sim_dir, "testbench.lis")
            lis_content = ""
            if '.lis' in result_files:
                lis_file = result_files['.lis']
                logger.info(f"📄 Found .lis file: {lis_file}")
            if os.path.exists(lis_file):
                try:
                    with open(lis_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lis_content = f.read()
                    logger.error(f"📄 Error log file read: {lis_file} ({len(lis_content)} characters)")
                    # Output first 500 characters for debugging
                    logger.error(f"Error log preview: {lis_content[:500]}")
                except Exception as e:
                    logger.error(f"⚠️ Failed to read lis file: {e}")
            else:
                logger.warning(f"⚠️ .lis file does not exist: {lis_file}")
            
            logger.error(f"❌ Remote HSPICE execution completed, but .ma0 result file not found")
            return {
                'success': False,
                'error': 'Remote HSPICE execution completed, but .ma0 result file not found',
                'lis_content': lis_content[:10000] if lis_content else '',
                'lis_file': lis_file,
                'sim_dir': sim_dir,
                'result_files_keys': list(result_files.keys()) if result_files else []
            }
            
        except HSPICETimeoutError as e:
            logger.error(f"❌ Remote HSPICE simulation timeout: {e}")
            return {
                'success': False,
                'error': f'Remote HSPICE simulation timeout: {str(e)}',
                'lis_content': '',
                'lis_file': '',
                'sim_dir': sim_dir
            }
        except HSPICESimulationError as e:
            logger.error(f"❌ Remote HSPICE simulation failed: {e}")
            # Try to read lis file
            lis_file = os.path.join(sim_dir, "testbench.lis")
            lis_content = ""
            if os.path.exists(lis_file):
                try:
                    with open(lis_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lis_content = f.read()
                except Exception:
                    pass
            return {
                'success': False,
                'error': f'Remote HSPICE simulation failed: {str(e)}',
                'lis_content': lis_content[:10000] if lis_content else '',
                'lis_file': lis_file,
                'sim_dir': sim_dir
            }
        except Exception as e:
            logger.error(f"❌ Error occurred during remote HSPICE execution: {e}")
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"Full stack trace: {error_traceback}")
            # Also output to console (even if console_level is WARNING)
            print(f"❌ Remote HSPICE execution error: {e}")
            print(f"Full stack trace: {error_traceback}")
            return {
                'success': False,
                'error': f'Remote HSPICE execution error: {str(e)}',
                'error_traceback': error_traceback,
                'lis_content': '',
                'lis_file': '',
                'sim_dir': sim_dir
            }
    else:
        # Local execution mode (original logic)
        logger.info("💻 Using local HSPICE execution mode")
        # Execute HSPICE simulation
        output_name = os.path.join(sim_dir, "testbench")
        hspice_cmd = f"{pipeline.config.hspice_path} -i {sim_testbench} -o {output_name}"
        
        logger.info(f"Executing HSPICE command: {hspice_cmd}")
        
        try:
            result = subprocess.run(
                hspice_cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=pipeline.config.hspice_timeout
            )
            
            if result.returncode != 0:
                logger.warning(f"⚠️ HSPICE return code: {result.returncode}")
                if result.stderr:
                    logger.error(f"HSPICE error output:\n{result.stderr[:500]}")
                
                # Read testbench.lis file to get detailed error information
                lis_file = output_name + ".lis"
                lis_content = ""
                if os.path.exists(lis_file):
                    try:
                        with open(lis_file, 'r', encoding='utf-8', errors='ignore') as f:
                            lis_content = f.read()
                        logger.error(f"📄 Error log file read: {lis_file} ({len(lis_content)} characters)")
                    except Exception as e:
                        logger.error(f"⚠️ Failed to read lis file: {e}")
                
                return {
                    'success': False,
                    'error': 'HSPICE simulation failed',
                    'returncode': result.returncode,
                    'stderr': result.stderr[:2000] if result.stderr else '',
                    'lis_content': lis_content[:10000] if lis_content else '',  # Limit length to avoid too long
                    'lis_file': lis_file,
                    'sim_dir': sim_dir  # Save sim_dir even if failed
                }
            
            # Parse simulation results
            performance_file = os.path.join(sim_dir, "testbench.ma0")
            if os.path.exists(performance_file):
                sim_results = pipeline.parse_simulation_results(performance_file, execution_log, sim_dir)
                # When successful, returned result contains gain and other fields, but not success field
                # Mark as successful for subsequent judgment
                sim_results['success'] = True
                # New: Save simulation directory path for Step 9 use
                sim_results['sim_dir'] = sim_dir
                return sim_results
            else:
                logger.error("❌ Simulation result file not found")
                # Even without .ma0 file, try to read lis file to get error information
                lis_file = output_name + ".lis"
                lis_content = ""
                if os.path.exists(lis_file):
                    try:
                        with open(lis_file, 'r', encoding='utf-8', errors='ignore') as f:
                            lis_content = f.read()
                        logger.info(f"📄 Log file read: {lis_file} ({len(lis_content)} characters)")
                    except Exception as e:
                        logger.error(f"⚠️ Failed to read lis file: {e}")
                
                return {
                    'success': False,
                    'error': 'Simulation result file not found',
                    'lis_content': lis_content[:10000] if lis_content else '',
                    'lis_file': lis_file,
                    'sim_dir': sim_dir  # Save sim_dir even if failed
                }
                
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Simulation timeout ({pipeline.config.hspice_timeout} seconds)")
            # Try to read lis file
            lis_file = output_name + ".lis"
            lis_content = ""
            if os.path.exists(lis_file):
                try:
                    with open(lis_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lis_content = f.read()
                except Exception:
                    pass
            return {
                'success': False,
                'error': f'Simulation timeout ({pipeline.config.hspice_timeout} seconds)',
                'lis_content': lis_content[:10000] if lis_content else '',
                'lis_file': lis_file,
                'sim_dir': sim_dir  # Save sim_dir even if failed
            }
        except Exception as e:
            logger.error(f"❌ Simulation execution error: {e}")
            return {
                'success': False,
                'error': f'Simulation execution error: {str(e)}',
                'lis_content': '',
                'lis_file': '',
                'sim_dir': sim_dir  # Save sim_dir even if failed
            }


def _analyze_simulation_failure(
    pipeline: 'CircuitAnalysisPipeline',
    lis_content: str,
    stderr: str = "",
    returncode: int = None,
    netlist: str = None
) -> Dict:
    """
    Use LLM to analyze simulation failure reasons (extract error information from testbench.lis file)
    
    Args:
        pipeline: CircuitAnalysisPipeline instance
        lis_content: Content of testbench.lis file
        stderr: HSPICE standard error output
        returncode: HSPICE return code
        netlist: Original netlist (optional, for context)
    
    Returns:
        {
            'failure_analysis': str,  # Failure cause analysis
            'error_location': str,  # Error location (which step/which line)
            'suggested_fix': str,  # Suggested fix methods
            'raw_response': str  # Raw response
        }
    """
    # Create logger (helper functions need their own logger)
    import logging
    logger = get_logger(
        name='step8_helper',
        module=__name__,
        console=True,
        file=True,
        level=logging.DEBUG,
        console_level=logging.WARNING  # Helper function logs also only show WARNING and above on console
    )
    
    if not lis_content:
        return {
            'failure_analysis': 'Unable to read simulation error log',
            'error_location': 'Unknown',
            'suggested_fix': 'Please check HSPICE simulation environment and configuration',
            'raw_response': ''
        }
    
    # Extract key error information (first 5000 characters, usually contains the most important errors)
    error_excerpt = lis_content[:5000]
    
    # If lis file is too long, also extract last 2000 characters (may contain summary information)
    if len(lis_content) > 5000:
        error_excerpt += "\n\n... [middle content omitted] ...\n\n" + lis_content[-2000:]
    
    # Build extra information section (avoid using backslashes in f-string expressions)
    extra_info_lines = []
    if returncode is not None:
        extra_info_lines.append(f"**Return Code**: {returncode}")
    if stderr:
        extra_info_lines.append(f"**Standard Error**: {stderr[:1000]}")
    if netlist:
        netlist_excerpt = netlist[:2000]
        extra_info_lines.append(f"**Original Netlist**:\n```spice\n{netlist_excerpt}\n```")
    
    extra_info = "\n".join(extra_info_lines) if extra_info_lines else ""
    
    prompt = f"""Please analyze the following HSPICE simulation failure error log, determine which step went wrong, and provide fix suggestions.

## HSPICE Error Log (testbench.lis)

```text
{error_excerpt}
```

## Extra Information
{extra_info}

Please output analysis results in the following format:

<failure_analysis>
Detailed failure cause analysis, including:
1. Main error type (syntax error, parameter error, convergence issue, etc.)
2. Specific error information
3. Possible causes
</failure_analysis>

<error_location>
Error occurrence location, for example:
- Which step went wrong (Step 7 optimization, Step 8 netlist generation, etc.)
- Which line or component in the netlist
- Specific error location description
</error_location>

<suggested_fix>
Suggested fix methods, including:
1. Places that need modification
2. Specific fix steps
3. Possible parameter adjustments needed
</suggested_fix>"""

    try:
        messages = [{"role": "user", "content": prompt}]
        api_result = pipeline.call_api(messages)
        
        if api_result:
            clean_response, _ = api_result
            
            # Extract analysis results
            failure_analysis = pipeline.extract_tagged_content(clean_response, 'failure_analysis')
            error_location = pipeline.extract_tagged_content(clean_response, 'error_location')
            suggested_fix = pipeline.extract_tagged_content(clean_response, 'suggested_fix')
            
            return {
                'failure_analysis': failure_analysis or 'Unable to extract failure analysis',
                'error_location': error_location or 'Unknown location',
                'suggested_fix': suggested_fix or 'No suggestions',
                'raw_response': clean_response
            }
        else:
            return {
                'failure_analysis': 'API call failed, unable to analyze error',
                'error_location': 'Unknown',
                'suggested_fix': 'Please manually check error log',
                'raw_response': ''
            }
    except Exception as e:
        logger.error(f"❌ Error occurred while analyzing simulation failure: {e}")
        return {
            'failure_analysis': f'Error in analysis process: {str(e)}',
            'error_location': 'Unknown',
            'suggested_fix': 'Please manually check error log',
            'raw_response': ''
        }
