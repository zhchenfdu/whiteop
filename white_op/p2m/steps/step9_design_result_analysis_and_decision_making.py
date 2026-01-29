"""
Step 9: Design Result Analysis and Decision-making

Compare and analyze white-box optimization results and HSPICE simulation results, make engineering decisions (ACCEPT or RETRY).
"""

import os
import re
import glob
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from p2m.pipeline import CircuitAnalysisPipeline

from core import load_prompt_from_file, PromptFileNotFoundError
from core.logger import get_logger


def step9_intelligent_comparison(
    pipeline: 'CircuitAnalysisPipeline',
    sim_results: Dict = None,
    optimization_failure_info: str = None,
    optimization_results: Dict = None
) -> Dict:
    """Step 9: Design Result Analysis and Decision-making (v10: file context passing, let LLM extract zero-pole by itself)"""
    # Step logger: console only shows WARNING and above, reduce detailed output
    import logging
    logger = get_logger(
        name='step9', 
        module=__name__,
        console=True,
        file=True,
        level=logging.DEBUG,  # File saves all levels
        console_level=logging.WARNING  # Console only shows WARNING and ERROR, reduce output
    )
    
    if sim_results is not None:
        # Optimization successful case: analyze based on HSPICE simulation results
        expected_perf = sim_results.get('expected_performance', 'No expected performance provided')
        
        # If no expected performance in HSPICE results, try to extract from optimization results
        if expected_perf == 'No expected performance provided' and optimization_results:
            expected_perf = _extract_expected_performance_from_optimization(pipeline, optimization_results)
        
        # New: Read related files as context (let LLM extract zero-pole by itself)
        optimization_file_content = ""
        simulation_pz0_content = ""
        
        # 1. Read white-box optimization results file (prefer code output file, smaller and more precise)
        if optimization_results and optimization_results.get('success', False):
            # Strategy 1: Try to read optimization code output file first (smaller, contains only execution results)
            optimization_output_file = None
            code_dir = f"{pipeline.config.output_dir}/python_codes"
            
            # Method 1: Try to infer output file path from saved file path
            saved_file = optimization_results.get('saved_file') or optimization_results.get('full_file')
            if saved_file:
                # Extract iteration and step information from saved file path
                # Example: .../iter01_step07_global07_white_box_optimization_programming_clean.md
                match = re.search(r'iter(\d+)_step(\d+)_global(\d+)_', saved_file)
                if match:
                    iter_num = match.group(1)
                    step_num = match.group(2)
                    global_num = match.group(3)
                    
                    # Try multiple possible filenames (because there may be multiple code segments)
                    for code_num in range(1, 10):  # Try up to 10 code segments
                        # Try English filename variants
                        for step_name_variant in ["white_box_optimization", "white_box_optimization_programming"]:
                            possible_file = os.path.join(
                                code_dir,
                                f"iter{iter_num}_step{step_num}_global{global_num}_{step_name_variant}_code{code_num}_output.txt"
                            )
                            if os.path.exists(possible_file):
                                optimization_output_file = possible_file
                                break
                        if optimization_output_file:
                            break
            
            # Method 2: If method 1 fails, try using current iteration information
            if not optimization_output_file:
                # Try multiple possible filenames (because there may be multiple code segments)
                for code_num in range(1, 10):  # Try up to 10 code segments
                    # Try different step number formats (step 7 may be step07 or step7)
                    for step_str in [f"step{pipeline.step_count:02d}", f"step{pipeline.step_count}", "step07", "step7"]:
                        for global_str in [f"global{pipeline.global_step_count:02d}", f"global{pipeline.global_step_count}", "global07", "global7"]:
                            # Try English filename variants
                            for step_name_variant in ["white_box_optimization", "white_box_optimization_programming"]:
                                possible_file = os.path.join(
                                    code_dir,
                                    f"iter{pipeline.iteration_count + 1:02d}_{step_str}_{global_str}_{step_name_variant}_code{code_num}_output.txt"
                                )
                                if os.path.exists(possible_file):
                                    optimization_output_file = possible_file
                                    break
                            if optimization_output_file:
                                break
                        if optimization_output_file:
                            break
                    if optimization_output_file:
                        break
            
            # Method 3: If both methods fail, try to find all matching files
            if not optimization_output_file and os.path.exists(code_dir):
                # Try English filename pattern
                pattern = os.path.join(code_dir, f"iter{pipeline.iteration_count + 1:02d}_*white_box_optimization*_output.txt")
                matching_files = glob.glob(pattern)
                
                if matching_files:
                    # Sort by modification time, use the latest
                    matching_files.sort(key=os.path.getmtime, reverse=True)
                    optimization_output_file = matching_files[0]
                    if len(matching_files) > 1:
                        logger.warning(f"⚠️ Found multiple matching output files, using the latest: {os.path.basename(optimization_output_file)}")
            
            # If optimization code output file is found, use it
            if optimization_output_file and os.path.exists(optimization_output_file):
                try:
                    with open(optimization_output_file, 'r', encoding='utf-8') as f:
                        optimization_file_content = f.read()
                    file_size = len(optimization_file_content)
                    logger.info(f"✅ Read optimization code output file: {os.path.basename(optimization_output_file)} ({file_size} chars)")
                except Exception as e:
                    logger.error(f"⚠️ Failed to read optimization code output file: {e}")
                    # Fall back to full response file
                    optimization_output_file = None
            
            # Strategy 2: If optimization code output file is not found, fall back to full response file
            # But extract only key parts to avoid including large example code
            if not optimization_output_file:
                optimization_file = saved_file
                if optimization_file and os.path.exists(optimization_file):
                    try:
                        with open(optimization_file, 'r', encoding='utf-8') as f:
                            full_content = f.read()
                        file_size = len(full_content)
                        
                        # Extract key parts from full response file (optimization results)
                        optimization_file_content = _extract_optimization_results_from_full_response(full_content)
                        extracted_size = len(optimization_file_content)
                        
                        logger.info(f"✅ Read white-box optimization full response file: {os.path.basename(optimization_file)} ({file_size} chars)")
                        logger.info(f"✅ Extracted key parts: {extracted_size} chars (compression ratio: {100*(1-extracted_size/max(file_size,1)):.1f}%)")
                        if file_size > 50000:  # Warn if file is larger than 50KB
                            logger.warning(f"⚠️ Note: Full response file is large, extracted key parts, recommend using optimization code output file")
                    except Exception as e:
                        logger.error(f"⚠️ Failed to read white-box optimization result file: {e}")
                        optimization_file_content = f"File read failed: {str(e)}"
                else:
                    logger.warning(f"⚠️ Warning: White-box optimization result file not found")
                    optimization_file_content = "White-box optimization result file not found"
        elif optimization_results:
            # optimization_results exists but success=False, indicating optimization failed
            logger.error(f"⚠️ Optimization failed, skipping optimization result file reading")
            optimization_file_content = "Optimization failed, unable to read optimization result file"
        else:
            optimization_file_content = "Optimization results not provided"
        
        # 2. Read simulation zero-pole file
        sim_dir = sim_results.get('sim_dir') or f"{pipeline.config.output_dir}/simulation_verification"
        pz0_file = os.path.join(sim_dir, "testbench.pz0")
        if os.path.exists(pz0_file):
            try:
                with open(pz0_file, 'r', encoding='utf-8') as f:
                    simulation_pz0_content = f.read()
                logger.info(f"✅ Read simulation zero-pole file: {pz0_file}")
            except Exception as e:
                logger.error(f"⚠️ Failed to read simulation zero-pole file: {e}")
                simulation_pz0_content = f"File read failed: {str(e)}"
        else:
            logger.warning(f"⚠️ Warning: Simulation zero-pole file not found: {pz0_file}")
            simulation_pz0_content = f"Simulation zero-pole file not found: {pz0_file}"
        
        # Load prompt template from file
        prompt_file = os.path.join(pipeline.prompts_dir, "step9_design_result_analysis_and_decision_making.md")
        prompt_template = load_prompt_from_file(prompt_file)
        
        if not prompt_template:
            raise PromptFileNotFoundError(prompt_file, step_name="design_result_analysis_and_decision_making")
        
        # Format prompt, replace placeholders (keep original formatting for other placeholders)
        prompt = prompt_template.format(
            expected_perf=expected_perf,
            gain=sim_results['gain'],
            ugf_mhz=sim_results['ugf']/1e6,
            phase_margin=sim_results['phase_margin'],
            power_uw=sim_results['power']*1e6,
            fom=sim_results['fom'],
            current_iteration=pipeline.iteration_count + 1,
            max_iterations=pipeline.config.full_pipeline_max_iterations,
            error_threshold_percent=pipeline.config.error_threshold * 100,
            optimization_file_content=optimization_file_content,
            simulation_pz0_content=simulation_pz0_content
        )
    
    # Choose different step names and processing based on situation
    if sim_results is not None:
        # Optimization successful case: analyze based on HSPICE simulation results
        step_name = "design_result_analysis_and_decision_making"
        result = pipeline.execute_step(step_name, prompt, None)
    else:
        # Optimization failed case: analyze based on failure information
        step_name = "design_result_analysis_and_decision_making"
        
        # Load prompt template from file
        prompt_file = os.path.join(pipeline.prompts_dir, "step9_design_result_analysis_and_decision_making_failure.md")
        prompt_template = load_prompt_from_file(prompt_file)
        
        if not prompt_template:
            raise PromptFileNotFoundError(prompt_file, step_name="design_result_analysis_and_decision_making")
        
        # Format prompt, replace placeholders
        failure_prompt = prompt_template.format(
            optimization_failure_info=optimization_failure_info,
            current_iteration=pipeline.iteration_count + 1,
            max_iterations=pipeline.config.full_pipeline_max_iterations
        )
        
        result = pipeline.execute_step(step_name, failure_prompt, None)
    
    if result['success']:
        response = result['response']
        
        # Add validation before parsing
        pipeline._validate_xml_structure(response)
        
        # Use new extract_tagged_content function to parse each part
        comparison_analysis = pipeline.extract_tagged_content(response, 'comparison_analysis')
        engineering_decision = pipeline.extract_tagged_content(response, 'engineering_decision')
        retry_details = pipeline.extract_tagged_content(response, 'retry_details')
        
        # Add validation after parsing
        pipeline._validate_parsed_content(comparison_analysis, engineering_decision, retry_details)
        
        # Use robust decision parsing method
        decision = pipeline.parse_decision(engineering_decision)
        
        retry_step = None
        lessons_learned = ""
        root_cause = ""
        
        if "RETRY" in decision.upper():
            # Strategy 1: Search for <return_step_id> in the entire response first (because retry_details may be unclosed causing incomplete extraction)
            return_step_match = re.search(r'<return_step_id>\s*(\d+)\s*</return_step_id>', response, re.IGNORECASE)
            if return_step_match:
                step_num = int(return_step_match.group(1))
                retry_step = max(4, min(8, step_num))  # Allow retry steps 4-8 (including step 8)
                logger.debug(f"  [Debug] Found <return_step_id> tag in full response, parsed retry step: {retry_step}")
            elif retry_details:
                # Strategy 2: Search in extracted retry_details
                return_step_match = re.search(r'<return_step_id>\s*(\d+)\s*</return_step_id>', retry_details, re.IGNORECASE)
                if return_step_match:
                    step_num = int(return_step_match.group(1))
                    retry_step = max(4, min(8, step_num))  # Allow retry steps 4-8 (including step 8)
                    logger.debug(f"  [Debug] Found <return_step_id> tag in retry_details, parsed retry step: {retry_step}")
                else:
                    # Strategy 3: Use fallback mode (Markdown format)
                    retry_step_match = re.search(r'\*\*Retry Starting Step\*\*:\s*(?:\[(\d+)\]|(\d+))', retry_details, re.IGNORECASE)
                    if retry_step_match:
                        step_num = int(retry_step_match.group(1) or retry_step_match.group(2))
                        retry_step = max(4, min(8, step_num))  # Allow retry steps 4-8 (including step 8)
                        logger.debug(f"  [Debug] Successfully parsed retry step using Markdown format fallback: {retry_step}")
                    else:
                        # Strategy 4: Search in full response using Markdown format
                        retry_step_match = re.search(r'\*\*Retry Starting Step\*\*:\s*(?:\[(\d+)\]|(\d+))', response, re.IGNORECASE)
                        if retry_step_match:
                            step_num = int(retry_step_match.group(1) or retry_step_match.group(2))
                            retry_step = max(4, min(8, step_num))  # Allow retry steps 4-8 (including step 8)
                            logger.debug(f"  [Debug] Successfully parsed retry step using Markdown format fallback in full response: {retry_step}")
                        else:
                            logger.error(f"  [Debug] Failed to parse retry step, using default: 4")
                            retry_step = 4
            else:
                # retry_details is empty, try searching all formats in the entire response
                # Strategy 1: Search for <return_step_id> in the entire response
                return_step_match = re.search(r'<return_step_id>\s*(\d+)\s*</return_step_id>', response, re.IGNORECASE)
                if return_step_match:
                    step_num = int(return_step_match.group(1))
                    retry_step = max(4, min(8, step_num))  # Allow retry steps 4-8 (including step 8)
                    logger.debug(f"  [Debug] retry_details is empty, but found <return_step_id> tag in full response, parsed retry step: {retry_step}")
                else:
                    # Strategy 2: Search in full response using Markdown format
                    retry_step_match = re.search(r'\*\*Retry Starting Step\*\*:\s*(?:\[(\d+)\]|(\d+))', response, re.IGNORECASE)
                    if retry_step_match:
                        step_num = int(retry_step_match.group(1) or retry_step_match.group(2))
                        retry_step = max(4, min(8, step_num))  # Allow retry steps 4-8 (including step 8)
                        logger.debug(f"  [Debug] retry_details is empty, but successfully parsed retry step using Markdown format in full response: {retry_step}")
                    else:
                        logger.debug(f"  [Debug] retry_details is empty and unable to parse retry step, using default: 4")
                        retry_step = 4
            
            lessons_match = re.search(r'\*\*Lessons Learned\*\*:(.*?)(?=\*\*Root Cause Analysis\*\*|$)', retry_details, re.DOTALL | re.IGNORECASE)
            if lessons_match:
                lessons_learned = lessons_match.group(1).strip()
            
            root_cause_match = re.search(r'\*\*Root Cause Analysis\*\*:(.*?)$', retry_details, re.DOTALL | re.IGNORECASE)
            if root_cause_match:
                root_cause = root_cause_match.group(1).strip()
                lessons_learned = f"{lessons_learned}\n\nRoot Cause Analysis:\n{root_cause}"
        
        result['decision'] = decision
        result['retry_step'] = retry_step
        result['lessons_learned'] = lessons_learned
        result['root_cause'] = root_cause
        result['comparison_analysis'] = comparison_analysis
    
    return result


# ========== Helper Functions ==========

def _extract_optimization_results_from_full_response(full_content: str) -> str:
    """
    Extract key parts (optimization results) from full response file, avoiding large example code
    
    Strategy:
    1. First extract "Model Response" section (contains actual optimization results)
    2. If not found, extract section containing "OPTIMIZATION RESULTS"
    3. If still not found, limit file size, return only the last part (usually optimization results are at the end)
    """
    # Strategy 1: Extract "Model Response" section (English)
    model_response_patterns = [
        r'## Model Response\s*\n(.*?)(?=\n---|\n\*file path|$)',
        r'## Response\s*\n(.*?)(?=\n---|\n\*file path|$)',
    ]
    
    for pattern in model_response_patterns:
        match = re.search(pattern, full_content, re.DOTALL | re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            # Further extraction: only keep parts containing optimization results (skip example code)
            # Find sections containing "OPTIMIZATION RESULTS"
            results_patterns = [
                r'(.*?OPTIMIZATION RESULTS.*?)(?=```|$|##)',
                r'(.*?OPTIMAL.*?)(?=```|$|##)',
            ]
            for result_pattern in results_patterns:
                result_match = re.search(result_pattern, extracted, re.DOTALL | re.IGNORECASE)
                if result_match:
                    return result_match.group(1).strip()
            # If optimization results section not found, return entire model response (but limit size)
            if len(extracted) > 20000:
                # If too long, return only last 20000 characters (usually optimization results are at the end)
                return extracted[-20000:]
            return extracted
    
    # Strategy 2: Directly find sections containing "OPTIMIZATION RESULTS"
    results_patterns = [
        r'(.*?OPTIMIZATION RESULTS.*?)(?=```|$|##)',
        r'(.*?OPTIMAL.*?DESIGN.*?VARIABLES.*?)(?=```|$|##)',
    ]
    
    for pattern in results_patterns:
        match = re.search(pattern, full_content, re.DOTALL | re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            if len(extracted) > 20000:
                return extracted[-20000:]
            return extracted
    
    # Strategy 3: If all fail, limit file size, return only the last part
    # Usually optimization results are at the end of file, example code is in the middle
    max_size = 20000  # Return at most 20KB
    if len(full_content) > max_size:
        # Return last part, but skip obvious example code parts
        # Find content before last "```python", or directly return last max_size characters
        last_python_block = full_content.rfind('```python')
        if last_python_block > 0:
            # Return content after last python code block
            after_code = full_content[last_python_block:].split('```', 2)
            if len(after_code) >= 3:
                # Skip code block, return content after it
                remaining = after_code[2]
                if len(remaining) > max_size:
                    return remaining[-max_size:]
                return remaining
        # If code block not found, directly return last max_size characters
        return full_content[-max_size:]
    
    return full_content


def _extract_expected_performance_from_optimization(
    pipeline: 'CircuitAnalysisPipeline',
    optimization_results: Dict
) -> str:
    """Extract expected performance from optimization results"""
    if not optimization_results or not optimization_results.get('success', False):
        return "Optimization failed, unable to provide expected performance"
    
    execution_results = optimization_results.get('execution_results', [])
    if not execution_results:
        return "Optimization execution results not found"
    
    # Extract performance metrics from execution log (via pipeline call)
    performance_text = pipeline._extract_optimization_performance(execution_results[0])
    
    if performance_text == "Performance metrics not found":
        return "Unable to extract performance metrics from optimization results"
    
    return f"""Expected performance based on Step 7 white-box optimization results:
{performance_text}

**Note**: These are predicted values based on the white-box model and need to be compared and verified with HSPICE simulation results."""
