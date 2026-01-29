"""
Data models module (data_models)

Contains CircuitData and ExplorationHistory classes.
These classes define the core data structures of the system.
"""

import os
import re
import json
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple
from datetime import datetime

from .config import DesignRequirements
from .utils import hash_netlist
from .exceptions import DataValidationError
from .logger import get_logger

# Create module logger
logger = get_logger(name='data_models', module=__name__)


@dataclass
class CircuitData:
    """Complete circuit data structure"""
    
    # Basic information
    circuit_id: str  # Unique identifier (based on netlist hash)
    netlist: str  # Original netlist
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Design requirements
    design_requirements: DesignRequirements = field(default_factory=DesignRequirements)
    
    # P2M analysis results
    circuit_equations: Optional[str] = None  # Step 2: Circuit equations
    raw_transfer_function: Optional[str] = None  # Step 3: Unbiased transfer function
    intermediate_transfer_function: Optional[str] = None  # Step 4: Substituted and simplified transfer function (real_hs)
    reduced_transfer_function: Optional[str] = None  # Step 5: Reduced transfer function
    extra_constraints_ab: Optional[str] = None  # Step 5: Additional constraints A and B
    extra_constraints_cd: Optional[str] = None  # Step 6: Additional constraints C and D
    zero_pole_expressions: Optional[str] = None  # Step 6: Zero-pole expressions
    
    # White-box optimization
    white_box_formulas: Optional[str] = None  # Step 6: White-box formulas (cooked_formula)
    optimization_code_file: Optional[str] = None  # Code file path
    optimization_design_vars: Optional[Dict] = None  # Design variable values (extracted from step 8 <param> tags)
    
    # White-box predicted performance (structured data extracted from optimization_results stdout)
    whitebox_predicted_performance: Optional[Dict] = None
    # Format: {'whitebox_gain': float, 'whitebox_gbw': float, 'whitebox_pm': float, 'whitebox_power': float}
    # Units: gain (dB), gbw (Hz), pm (degrees), power (W) - consistent with SI units
    
    # Simulation verification
    simulation_results: Optional[Dict] = None  # Step 8: Simulation results
    
    # Comprehensive scoring (auto-calculated when both white-box predictions and simulation results exist)
    comprehensive_score: Optional[float] = None  # Score = score1 × score2
    prediction_accuracy_score: Optional[float] = None  # Score1 (white-box prediction accuracy)
    constraint_satisfaction_score: Optional[float] = None  # Score2 (constraint satisfaction)
    
    # Circuit validity (auto-calculated based on constraint_satisfaction_score > 1.0)
    is_valid: Optional[bool] = None  # True means all constraints satisfied (score2 > 1.0), False means not satisfied
    
    # White-box black-box comparison
    whitebox_blackbox_comparison: Optional[str] = None  # Step 9: White-box vs simulation comparison analysis (raw text content)
    # Format: string containing complete comparison_analysis text content
    
    # Note: performance field has been removed, please use simulation_results field
    
    # Metadata
    p2m_iteration: Optional[int] = None  # P2M internal iteration count (best iteration number, kept for compatibility)
    optimization_iteration: Optional[int] = None  # Architecture exploration iteration count
    
    # Complete reasoning chain (new: only save key fields)
    complete_reasoning_chain: List[Dict] = field(default_factory=list)
    # Format: ordered by step, each element contains:
    # {
    #   'step': 'List Equations',
    #   'step_number': 2,
    #   'iteration': 1,  # Which iteration this comes from
    #   'key_content': '...',  # Key field (tagged content)
    #   'key_content_type': 'raw_eq',  # Key field type
    #   'saved_file': '...',  # File path (for accessing full context)
    #   'success': True
    # }
    
    # Reasoning chain metadata (new)
    reasoning_chain_metadata: Dict = field(default_factory=dict)
    # Format:
    # {
    #   'best_iteration': 4,  # Best iteration number
    #   'retry_from_step': 6,  # Which step to retry from (1 if no retry)
    #   'chain_composition': {
    #     'steps_1_to_5': {'iteration': 1, 'source': 'first_complete_iteration'},
    #     'steps_6_to_9': {'iteration': 4, 'source': 'best_iteration'}
    #   },
    #   'total_iterations': 4,  # Total iteration count
    #   'input_info': {  # Input information reference (new)
    #     'netlist_hash': '6ee863074ee16f5454ece63db483a5b0',
    #     'design_requirements': {
    #       'gain_min_db': 60.0,
    #       'gbw_min_mhz': 0.5,
    #       'pm_min_deg': 45.0,
    #       'pm_max_deg': 90.0,
    #       'pm_ideal_deg': 60.0,
    #       'power_max_uw': 250.0
    #     }
    #   }
    # }
    
    # File paths (for quick access, only save files for complete chain)
    output_dir: Optional[str] = None  # Output directory
    step_files: Dict[str, str] = field(default_factory=dict)  # {step_name: file_path}
    
    def to_dict(self) -> Dict:
        """Convert to dict (for serialization)"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, DesignRequirements):
                result[key] = value.__dict__
            elif isinstance(value, dict):
                result[key] = value
            elif isinstance(value, list):
                # Handle complete_reasoning_chain, remove _original_result (temporary reference, not serialized)
                if key == 'complete_reasoning_chain':
                    cleaned_chain = []
                    for item in value:
                        cleaned_item = {k: v for k, v in item.items() if k != '_original_result'}
                        cleaned_chain.append(cleaned_item)
                    result[key] = cleaned_chain
                else:
                    result[key] = value
            else:
                result[key] = value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CircuitData':
        """Create from dict (for deserialization)"""
        # Handle datetime
        if 'timestamp' in data and isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        
        # Handle DesignRequirements
        if 'design_requirements' in data and isinstance(data['design_requirements'], dict):
            data['design_requirements'] = DesignRequirements(**data['design_requirements'])
        
        return cls(**data)
    
    def save_to_file(self, filepath: str):
        """Save to JSON file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    

class ExplorationHistory:
    """Exploration history (V3: Enhanced version, includes complete circuit data)"""
    
    def __init__(self):
        self.topologies = {}  # {netlist_hash: topology_info}
        self.circuit_data = {}  # {netlist_hash: CircuitData}  # New: complete circuit data
        self.modification_attempts = []  # Modification attempt records
    
    # Note: _hash_netlist method has been removed, now using core.utils.hash_netlist unified implementation
    
    def add_topology(self, netlist: str, p2m_results: List[Dict], metadata: Dict = None):
        """Add explored topology"""
        netlist_hash = hash_netlist(netlist)
        self.topologies[netlist_hash] = {
            'netlist': netlist,
            'performance': self._extract_performance(p2m_results),
            'situation': self._classify_situation(p2m_results),
            'metadata': metadata or {}
        }
    
    def is_explored(self, netlist: str) -> bool:
        """Check if topology has been explored"""
        return hash_netlist(netlist) in self.topologies
    
    def _extract_performance(self, p2m_results: List[Dict]) -> Dict:
        """Extract performance metrics from P2M results"""
        performance = {}
        
        # Extract from step 8 (generate numerical netlist) simulation results
        for result in p2m_results:
            # Use step_number for robust step identification (step 8: Simulation Verification)
            if result.get('step_number') == 8 or 'simulation_verification' in result.get('step', ''):
                sim_results = result.get('simulation_results', {})
                if sim_results:
                    performance = {
                        'gain': sim_results.get('gain', 0),
                        'ugf': sim_results.get('ugf', 0),
                        'phase_margin': sim_results.get('phase_margin', 0),
                        'power': sim_results.get('power', 0),
                        'fom': sim_results.get('fom', 0)
                    }
                    break
        
        return performance
    
    def add_circuit_data(self, netlist: str, 
                        p2m_results: List[Dict] = None,  # All steps from all iterations (for concatenation)
                        best_iteration_info: Dict = None,  # Best iteration info (required)
                        config: 'PipelineConfig' = None,
                        output_dir: str = None,
                        iteration: int = None,  # Backward compatible: P2M internal iteration count
                        optimization_iteration: int = None) -> CircuitData:
        """Add complete circuit data (simplified version: only maintain optimal complete reasoning chain)
        
        Args:
            netlist: Netlist content
            p2m_results: All P2M step results (for concatenation, can be omitted if best_iteration_info contains complete info)
            best_iteration_info: Best iteration info, contains:
                - 'iteration': Iteration number
                - 'results': All step results for this iteration
                - 'retry_from_step': Which step to retry from (if any)
                - 'quality_info': Quality assessment info
            config: Pipeline config
            output_dir: Output directory
            iteration: P2M internal iteration count (backward compatible, used if best_iteration_info is None)
            optimization_iteration: Architecture exploration iteration count
        
        Returns:
            CircuitData object (only contains complete reasoning chain)
        """
        netlist_hash = hash_netlist(netlist)
        
        # Backward compatible: if no best_iteration_info, try to build from p2m_results
        if best_iteration_info is None:
            if p2m_results:
                logger.warning("⚠️ Warning: best_iteration_info not provided, attempting to auto-select best iteration")
                # Try to select best iteration
                best_iter = self._select_best_iteration_simple(p2m_results)
                if best_iter:
                    best_iteration_info = best_iter
                else:
                    # If cannot select, use all results as complete chain (backward compatible)
                    logger.warning("⚠️ Cannot select best iteration, using all results as complete chain")
                    best_iteration_info = {
                        'iteration': iteration or 1,
                        'results': p2m_results,
                        'retry_from_step': 1
                    }
            else:
                raise DataValidationError(
                    "best_iteration_info/p2m_results",
                    None,
                    reason="Must provide best_iteration_info or p2m_results"
                )
        
        # 1. Build complete reasoning chain
        complete_chain, chain_metadata = self._build_complete_reasoning_chain(
            best_iteration_info, p2m_results
        )
        
        # 1.1 Add input info reference to metadata
        design_requirements = DesignRequirements.from_config(config) if config else DesignRequirements()
        chain_metadata['input_info'] = {
            'netlist_hash': netlist_hash,
            'design_requirements': {
                'gain_min_db': design_requirements.gain_min_db,
                'gbw_min_mhz': design_requirements.gbw_min_mhz,
                'pm_min_deg': design_requirements.pm_min_deg,
                'pm_max_deg': design_requirements.pm_max_deg,
                'pm_ideal_deg': design_requirements.pm_ideal_deg,
                'power_max_uw': design_requirements.power_max_uw
            }
        }
        
        # 2. Build CircuitData
        circuit_data = CircuitData(
            circuit_id=netlist_hash,
            netlist=netlist,
            design_requirements=design_requirements,
            output_dir=output_dir,
            p2m_iteration=best_iteration_info.get('iteration', iteration),
            optimization_iteration=optimization_iteration,
            complete_reasoning_chain=complete_chain,
            reasoning_chain_metadata=chain_metadata
        )
        
        # 3. Extract key data from complete reasoning chain
        self._extract_circuit_data_from_chain(circuit_data, complete_chain, output_dir)
        
        # 4. Store
        self.circuit_data[netlist_hash] = circuit_data
        
        # 5. Also update topologies (maintain backward compatibility)
        # Use complete chain to build p2m_results for topologies
        p2m_results_for_topology = complete_chain if complete_chain else (p2m_results or [])
        self.add_topology(netlist, p2m_results_for_topology, metadata={
            'circuit_id': netlist_hash,
            'has_full_data': True
        })
        
        return circuit_data
    
    def _group_results_by_iteration(self, p2m_results: List[Dict]) -> Dict[int, List[Dict]]:
        """Group results by iteration (ExplorationHistory class method)"""
        iterations = {}
        for result in p2m_results:
            iter_num = result.get('iteration', 1)  # If not marked, default to 1 (backward compatible)
            if iter_num not in iterations:
                iterations[iter_num] = []
            iterations[iter_num].append(result)
        return iterations
    
    def _select_best_iteration_simple(self, p2m_results: List[Dict]) -> Optional[Dict]:
        """Simple selection of best iteration (for backward compatibility)"""
        # Group by iteration
        iterations = self._group_results_by_iteration(p2m_results)
        if not iterations:
            return None
        
        # Select last iteration (usually the best)
        last_iter_num = max(iterations.keys())
        return {
            'iteration': last_iter_num,
            'results': iterations[last_iter_num],
            'retry_from_step': 1
        }
    
    def _get_step_number(self, step_name: str) -> int:
        """Extract step number from step name"""
        step_mapping = {
            'circuit_topology_interpretation': 1,
            'circuit_equation_formulation': 2,
            'unbiased_transfer_function_derivation': 3,
            'design_variable_substitution_and_simplification': 4,
            'pole_and_zero_extraction': 5,
            'pole_and_zero_positioning_and_metric_derivation': 6,
            'white_box_optimization_programming': 7,
            'simulation_verification': 8,
            'design_result_analysis_and_decision_making': 9,
        }
        for name, num in step_mapping.items():
            if name in step_name:
                return num
        return 0
    
    def _infer_retry_step(self, results: List[Dict]) -> Optional[int]:
        """Infer retry start step from results"""
        step_numbers = [self._get_step_number(r.get('step', '')) for r in results]
        step_numbers = [s for s in step_numbers if s > 0]
        if not step_numbers:
            return None
        min_step = min(step_numbers)
        return min_step if min_step > 1 else None
    
    def _find_first_complete_iteration(self, all_p2m_results: List[Dict], retry_from_step: int) -> Optional[int]:
        """Find first complete iteration containing steps 1 to retry_from_step-1"""
        if not all_p2m_results:
            return None
        
        iterations = self._group_results_by_iteration(all_p2m_results)
        
        for iter_num in sorted(iterations.keys()):
            iter_results = iterations[iter_num]
            step_numbers = [self._get_step_number(r.get('step', '')) for r in iter_results]
            step_numbers = [s for s in step_numbers if s > 0]
            
            # Check if contains steps 1 to retry_from_step-1
            required_steps = set(range(1, retry_from_step))
            if required_steps.issubset(set(step_numbers)):
                return iter_num
        
        return None
    
    def _normalize_chain_steps(self, results: List[Dict]) -> List[Dict]:
        """Normalize chain steps, ensure ordered by step number"""
        normalized = []
        for result in results:
            step_num = self._get_step_number(result.get('step', ''))
            if step_num > 0:
                normalized.append(result)
        normalized.sort(key=lambda x: self._get_step_number(x.get('step', '')))
        return normalized
    
    def _count_total_iterations(self, all_p2m_results: List[Dict]) -> int:
        """Count total iterations"""
        if not all_p2m_results:
            return 1
        iterations = set()
        for result in all_p2m_results:
            iter_num = result.get('iteration', 1)
            iterations.add(iter_num)
        return len(iterations)
    
    def _extract_key_content(self, result: Dict) -> Tuple[Optional[str], Optional[str]]:
        """Extract key field from step
        
        Args:
            result: Step result dict
        
        Returns:
            (key_content, key_content_type)
            - key_content: Key field content
            - key_content_type: Key field type (e.g., 'raw_eq', 'cooked_formula', etc.)
        """
        step_name = result.get('step', '')
        response = result.get('clean_response', result.get('response', ''))
        extracted = result.get('extracted', '')
        
        # Step 2: Extract raw_eq
        step_number = result.get('step_number')
        if step_number == 2 or 'circuit_equation_formulation' in step_name or 'step2' in step_name.lower() or 'list_equations' in step_name.lower():
            key_content = self._extract_tagged_content(response, 'raw_eq')
            return key_content or extracted, 'raw_eq'
        
        # Step 3: Extract raw_hs
        elif step_number == 3 or 'unbiased_transfer_function_derivation' in step_name or 'step3' in step_name.lower() or 'solve_transfer' in step_name.lower():
            key_content = self._extract_tagged_content(response, 'raw_hs')
            return key_content or extracted, 'raw_hs'
        
        # Step 4: Extract real_hs
        elif step_number == 4 or 'design_variable_substitution_and_simplification' in step_name or 'step4' in step_name.lower() or 'substitute' in step_name.lower():
            key_content = self._extract_tagged_content(response, 'real_hs')
            return key_content or extracted, 'real_hs'
        
        # Step 5: Extract cooked_hs and extra_cons
        elif step_number == 5 or 'pole_and_zero_extraction' in step_name or 'step5' in step_name.lower() or 'factorize' in step_name.lower():
            cooked_hs = self._extract_tagged_content(response, 'cooked_hs')
            extra_cons = self._extract_tagged_content(response, 'extra_cons')
            if cooked_hs and extra_cons:
                key_content = f"{cooked_hs}\n\n{extra_cons}"
            else:
                key_content = cooked_hs or extra_cons
            return key_content or extracted, 'cooked_hs'
        
        # Step 6: Extract cooked_formula, zps, extra_cons
        elif step_number == 6 or 'pole_and_zero_positioning_and_metric_derivation' in step_name or 'step6' in step_name.lower() or 'functional' in step_name.lower():
            cooked_formula = self._extract_tagged_content(response, 'cooked_formula')
            zps = self._extract_tagged_content(response, 'zps')
            extra_cons = self._extract_tagged_content(response, 'extra_cons')
            parts = []
            if cooked_formula:
                parts.append(cooked_formula)
            if zps:
                parts.append(zps)
            if extra_cons:
                parts.append(extra_cons)
            key_content = '\n\n'.join(parts) if parts else None
            return key_content, 'cooked_formula'
        
        # Step 7: Extract optimization code and result summary
        elif step_number == 7 or 'white_box_optimization_programming' in step_name or 'step7' in step_name.lower() or 'white_box' in step_name.lower():
            code_files = result.get('python_codes', [])
            execution_results = result.get('execution_results', [])
            parts = []
            if code_files:
                parts.append(f"Code file: {code_files[0]}")
            if execution_results:
                # Safely extract stdout: handle both string and dict cases
                exec_result = execution_results[0]
                if isinstance(exec_result, dict):
                    stdout = exec_result.get('stdout', '')
                elif isinstance(exec_result, str):
                    # If it's a string, try to extract stdout part
                    if 'stdout:' in exec_result:
                        parts_split = exec_result.split('stderr:', 1)
                        stdout = parts_split[0].replace('stdout:', '').strip()
                    else:
                        stdout = exec_result
                else:
                    stdout = str(exec_result) if exec_result else ''
                
                # Extract key information (optimization result summary)
                if stdout and 'OPTIMIZATION RESULTS' in stdout:
                    # Extract result summary part
                    lines = stdout.split('\n')
                    summary_lines = []
                    in_summary = False
                    for line in lines:
                        if 'OPTIMIZATION RESULTS' in line:
                            in_summary = True
                        if in_summary:
                            summary_lines.append(line)
                            if line.strip() == '=' * 40:
                                if len(summary_lines) > 1:
                                    break
                    parts.append('\n'.join(summary_lines) if summary_lines else stdout[:500])
            key_content = '\n\n'.join(parts) if parts else None
            return key_content, 'optimization'
        
        # Step 8: Extract simulation results
        elif step_number == 8 or 'simulation_verification' in step_name or 'step8' in step_name.lower() or 'generate_numerical' in step_name.lower():
            sim_results = result.get('simulation_results', {})
            if sim_results:
                key_content = f"Gain: {sim_results.get('gain', 0):.2f} dB\n"
                key_content += f"GBW: {sim_results.get('ugf', 0)/1e6:.2f} MHz\n"
                key_content += f"PM: {sim_results.get('phase_margin', 0):.2f} deg\n"
                key_content += f"Power: {sim_results.get('power', 0)*1e6:.2f} uW\n"
                key_content += f"FoM: {sim_results.get('fom', 0):.2f}"
                return key_content, 'simulation_results'
            return None, 'simulation_results'
        
        # Step 9: Extract decision results
        elif step_number == 9 or 'design_result_analysis_and_decision_making' in step_name or 'step9' in step_name.lower():
            decision = result.get('decision', '')
            comparison = result.get('comparison_analysis', '')
            
            # If result doesn't have comparison_analysis, try to extract from response
            if not comparison and response:
                comparison = self._extract_tagged_content(response, 'comparison_analysis')
            
            if decision or comparison:
                # Don't truncate comparison_analysis, keep full content (will read full content from saved_file later)
                key_content = f"Decision: {decision}\n\n{comparison if comparison else ''}"
                return key_content, 'decision'
            return None, 'decision'
        
        # Step 1: Read netlist (no key field, can save as empty or circuit structure description)
        elif step_number == 1 or 'circuit_topology_interpretation' in step_name or 'step1' in step_name.lower():
            return None, 'circuit_structure'
        
        return None, None
    
    def _build_complete_reasoning_chain(self, 
                                        best_iteration_info: Dict,
                                        all_p2m_results: List[Dict] = None) -> Tuple[List[Dict], Dict]:
        """Build complete reasoning chain (only save key fields)
        
        Args:
            best_iteration_info: Best iteration information
            all_p2m_results: All steps from all iterations (can be omitted if best_iteration_info contains complete information)
        
        Returns:
            (complete_chain, chain_metadata)
            - complete_chain: Complete reasoning chain (steps 1-9, in order, only key fields)
            - chain_metadata: Chain metadata
        """
        best_iter = best_iteration_info['iteration']
        best_results = best_iteration_info['results']
        retry_from_step = best_iteration_info.get('retry_from_step', None)
        
        # If no retry information, try to infer from best_results
        if not retry_from_step:
            retry_from_step = self._infer_retry_step(best_results)
        
        # If no retry (starting from step 1), directly return best iteration results
        if not retry_from_step or retry_from_step == 1:
            complete_chain = self._build_chain_from_results(best_results)
            chain_metadata = {
                'best_iteration': best_iter,
                'retry_from_step': 1,
                'chain_composition': {
                    'steps_1_to_9': {'iteration': best_iter, 'source': 'best_iteration'}
                },
                'total_iterations': self._count_total_iterations(all_p2m_results) if all_p2m_results else 1
            }
            return complete_chain, chain_metadata
        
        # If there is retry, need to concatenate
        # Steps 1 to retry_from_step-1: from first complete iteration
        # Steps retry_from_step to 9: from best iteration
        
        # Find first complete iteration (contains steps 1 to retry_from_step-1)
        first_complete_iter = self._find_first_complete_iteration(
            all_p2m_results, retry_from_step
        )
        
        if not first_complete_iter:
            # If complete iteration not found, use best iteration results (may be incomplete)
            logger.warning(f"⚠️ Warning: Unable to find complete iteration containing steps 1-{retry_from_step-1}, using best iteration results")
            complete_chain = self._build_chain_from_results(best_results)
            chain_metadata = {
                'best_iteration': best_iter,
                'retry_from_step': retry_from_step,
                'chain_composition': {
                    'steps_1_to_9': {'iteration': best_iter, 'source': 'best_iteration_incomplete'}
                },
                'total_iterations': self._count_total_iterations(all_p2m_results) if all_p2m_results else 1
            }
            return complete_chain, chain_metadata
        
        # Concatenate: earlier steps from first complete iteration, later steps from best iteration
        complete_chain = []
        
        # Steps 1 to retry_from_step-1: from first complete iteration
        first_iter_results = [r for r in all_p2m_results if r.get('iteration') == first_complete_iter]
        for result in first_iter_results:
            step_num = self._get_step_number(result.get('step', ''))
            if 1 <= step_num < retry_from_step:
                chain_item = self._build_chain_item(result, first_complete_iter)
                if chain_item:
                    complete_chain.append(chain_item)
        
        # Steps retry_from_step to 9: from best iteration
        for result in best_results:
            step_num = self._get_step_number(result.get('step', ''))
            if step_num >= retry_from_step:
                chain_item = self._build_chain_item(result, best_iter)
                if chain_item:
                    complete_chain.append(chain_item)
        
        # Sort by step number
        complete_chain.sort(key=lambda x: x.get('step_number', 0))
        
        # Build metadata
        chain_metadata = {
            'best_iteration': best_iter,
            'retry_from_step': retry_from_step,
            'chain_composition': {
                f'steps_1_to_{retry_from_step-1}': {
                    'iteration': first_complete_iter,
                    'source': 'first_complete_iteration'
                },
                f'steps_{retry_from_step}_to_9': {
                    'iteration': best_iter,
                    'source': 'best_iteration'
                }
            },
            'total_iterations': self._count_total_iterations(all_p2m_results) if all_p2m_results else 1
        }
        
        return complete_chain, chain_metadata
    
    def _build_chain_from_results(self, results: List[Dict]) -> List[Dict]:
        """Build reasoning chain from results list"""
        chain = []
        for result in results:
            chain_item = self._build_chain_item(result, result.get('iteration', 1))
            if chain_item:
                chain.append(chain_item)
        # Sort by step number
        chain.sort(key=lambda x: x.get('step_number', 0))
        return chain
    
    def _build_chain_item(self, result: Dict, iteration: int) -> Optional[Dict]:
        """Build single chain item (only key fields, but keep original result reference for extraction)"""
        step_name = result.get('step', '')
        step_number = self._get_step_number(step_name)
        
        if step_number == 0:
            return None  # Skip unrecognized steps
        
        # Extract key fields
        key_content, key_content_type = self._extract_key_content(result)
        
        # Handle file path
        saved_file = result.get('saved_file', '')
        
        chain_item = {
            'step': step_name,
            'step_number': step_number,
            'iteration': iteration,
            'key_content': key_content,
            'key_content_type': key_content_type,
            'saved_file': saved_file,
            'success': result.get('success', True),
            '_original_result': result  # Keep original result reference for extracting execution_results and simulation_results
        }
        
        return chain_item
    
    def _extract_circuit_data_from_chain(self, circuit_data: CircuitData, 
                                        complete_chain: List[Dict],
                                        output_dir: str = None):
        """Extract circuit data from complete reasoning chain (only process key fields)"""
        for chain_item in complete_chain:
            try:
                step_name = chain_item.get('step', '')
                saved_file = chain_item.get('saved_file', '')
                key_content = chain_item.get('key_content', '')
                
                # Save file path (use relative path)
                if saved_file and output_dir:
                    try:
                        rel_path = os.path.relpath(saved_file, output_dir)
                        circuit_data.step_files[step_name] = rel_path
                    except:
                        circuit_data.step_files[step_name] = saved_file
                elif saved_file:
                    circuit_data.step_files[step_name] = saved_file
                
                # Extract data from key fields (use key_content instead of response)
                step_number = chain_item.get('step_number')
                # Step 2: Circuit equations
                if step_number == 2 or 'circuit_equation_formulation' in step_name or 'step2' in step_name.lower() or 'list_equations' in step_name.lower():
                    circuit_data.circuit_equations = key_content
                
                # Step 3: Unbiased transfer function
                elif step_number == 3 or 'unbiased_transfer_function_derivation' in step_name or 'step3' in step_name.lower() or 'solve_transfer' in step_name.lower():
                    circuit_data.raw_transfer_function = key_content
                
                # Step 4: Substituted and simplified transfer function
                elif step_number == 4 or 'design_variable_substitution_and_simplification' in step_name or 'step4' in step_name.lower() or 'substitute' in step_name.lower():
                    circuit_data.intermediate_transfer_function = key_content
                
                # Step 5: Reduced transfer function and extra constraints A, B
                # Note: Prefer extracting from _original_result's response (contains complete XML tags)
                elif step_number == 5 or 'pole_and_zero_extraction' in step_name or 'step5' in step_name.lower() or 'factorize' in step_name.lower():
                    # Prefer extracting from _original_result's response
                    original_result = chain_item.get('_original_result', {})
                    response = original_result.get('clean_response', original_result.get('response', '')) if original_result else ''
                    
                    # If response doesn't exist or is empty, fallback to reading from saved file
                    if not response or not response.strip():
                        saved_file = chain_item.get('saved_file', '')
                        if saved_file and output_dir:
                            # Build full path
                            if os.path.isabs(saved_file):
                                file_path = saved_file
                            else:
                                candidate_paths = [saved_file]
                                if output_dir not in saved_file:
                                    candidate_paths.append(os.path.join(output_dir, saved_file))
                                
                                file_path = None
                                for path in candidate_paths:
                                    if os.path.exists(path):
                                        file_path = path
                                        break
                                
                                if not file_path:
                                    file_path = saved_file
                            
                            try:
                                if os.path.exists(file_path):
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        response = f.read()
                            except Exception as e:
                                logger.warning(f"Step 5 unable to read from file: {e}")
                                response = ''
                    
                    # If response exists, extract XML tags from response
                    if response:
                        import re
                        # Extract cooked_hs (use last match)
                        cooked_hs_pattern = r'<cooked_hs>(.*?)</cooked_hs>'
                        cooked_hs_matches = list(re.finditer(cooked_hs_pattern, response, re.DOTALL | re.IGNORECASE))
                        if cooked_hs_matches:
                            last_match = cooked_hs_matches[-1]
                            cooked_hs_content = last_match.group(1).strip()
                            if cooked_hs_content and cooked_hs_content != '`and`' and len(cooked_hs_content) > 10:
                                circuit_data.reduced_transfer_function = cooked_hs_content
                        
                        # Extract extra_cons (use last match)
                        extra_cons_pattern = r'<extra_cons>(.*?)</extra_cons>'
                        extra_cons_matches = list(re.finditer(extra_cons_pattern, response, re.DOTALL | re.IGNORECASE))
                        if extra_cons_matches:
                            last_match = extra_cons_matches[-1]
                            extra_cons_content = last_match.group(1).strip()
                            if extra_cons_content and extra_cons_content != '`and`' and len(extra_cons_content) >= 10:
                                # Check if contains constraint A or B (does not contain C or D)
                                has_constraint_c = (re.search(r'\*\*C\d+', extra_cons_content) or 
                                                  'Constraint C' in extra_cons_content or
                                                  'C1' in extra_cons_content or 'C2' in extra_cons_content)
                                has_constraint_d = (re.search(r'\*\*D\d+', extra_cons_content) or 
                                                  'Constraint D' in extra_cons_content or
                                                  'D1' in extra_cons_content or 'D2' in extra_cons_content)
                                
                                if not has_constraint_c and not has_constraint_d:
                                    circuit_data.extra_constraints_ab = extra_cons_content
                    else:
                        # Fallback: If response doesn't exist, try to extract from key_content (though may not have tags)
                        if key_content:
                            # key_content may contain cooked_hs and extra_cons, need to separate
                            # Try to separate (simple handling: if contains extra_cons tag, separate)
                            if '<extra_cons>' in key_content:
                                parts = key_content.split('\n\n', 1)
                                if len(parts) >= 2:
                                    circuit_data.reduced_transfer_function = parts[0]
                                    circuit_data.extra_constraints_ab = parts[1]
                                else:
                                    circuit_data.reduced_transfer_function = key_content
                            else:
                                circuit_data.reduced_transfer_function = key_content
                
                # Step 6: White-box formulas, extra constraints C, D, zero-pole
                # Note: Prefer extracting from _original_result's response (contains complete XML tags)
                elif step_number == 6 or 'pole_and_zero_positioning_and_metric_derivation' in step_name or 'step6' in step_name.lower() or 'functional' in step_name.lower():
                    # Prefer extracting from _original_result's response
                    original_result = chain_item.get('_original_result', {})
                    response = original_result.get('clean_response', original_result.get('response', '')) if original_result else ''
                    
                    # If response doesn't exist or is empty, fallback to reading from saved file
                    if not response or not response.strip():
                        saved_file = chain_item.get('saved_file', '')
                        if saved_file and output_dir:
                            # Build full path
                            if os.path.isabs(saved_file):
                                file_path = saved_file
                            else:
                                # Try multiple paths
                                candidate_paths = [saved_file]
                                if output_dir not in saved_file:
                                    candidate_paths.append(os.path.join(output_dir, saved_file))
                                
                                file_path = None
                                for path in candidate_paths:
                                    if os.path.exists(path):
                                        file_path = path
                                        break
                                
                                if not file_path:
                                    file_path = saved_file
                            
                            try:
                                if os.path.exists(file_path):
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        response = f.read()
                            except Exception as e:
                                logger.warning(f"Step 6 unable to read from file: {e}")
                                response = ''
                    
                    # If response exists, extract XML tags from response
                    if response:
                        import re
                        # Extract cooked_formula
                        cooked_formula_pattern = r'<cooked_formula>(.*?)</cooked_formula>'
                        cooked_formula_matches = list(re.finditer(cooked_formula_pattern, response, re.DOTALL | re.IGNORECASE))
                        if cooked_formula_matches:
                            last_match = cooked_formula_matches[-1]
                            cooked_formula_content = last_match.group(1).strip()
                            if cooked_formula_content and cooked_formula_content != '`and`' and len(cooked_formula_content) > 10:
                                circuit_data.white_box_formulas = cooked_formula_content
                        
                        # Extract zps (use last match)
                        zps_pattern = r'<zps>(.*?)</zps>'
                        zps_matches = list(re.finditer(zps_pattern, response, re.DOTALL | re.IGNORECASE))
                        if zps_matches:
                            last_zps_match = zps_matches[-1]
                            zps_content = last_zps_match.group(1).strip()
                            if zps_content and zps_content != '`and`' and len(zps_content) > 10:
                                circuit_data.zero_pole_expressions = zps_content
                        
                        # Extract extra_cons (use last match)
                        extra_cons_pattern = r'<extra_cons>(.*?)</extra_cons>'
                        extra_cons_matches = list(re.finditer(extra_cons_pattern, response, re.DOTALL | re.IGNORECASE))
                        if extra_cons_matches:
                            last_extra_cons_match = extra_cons_matches[-1]
                            extra_cons_content = last_extra_cons_match.group(1).strip()
                            if extra_cons_content and extra_cons_content != '`and`' and len(extra_cons_content) >= 10:
                                # Check if contains constraint C or D
                                has_constraint_c = (re.search(r'\*\*C\d+', extra_cons_content) or 
                                                  'Constraint C' in extra_cons_content or
                                                  'C1' in extra_cons_content or 'C2' in extra_cons_content)
                                has_constraint_d = (re.search(r'\*\*D\d+', extra_cons_content) or 
                                                  'Constraint D' in extra_cons_content or
                                                  'D1' in extra_cons_content or 'D2' in extra_cons_content)
                                
                                if has_constraint_c or has_constraint_d:
                                    circuit_data.extra_constraints_cd = extra_cons_content
                                else:
                                    if not circuit_data.extra_constraints_ab:
                                        circuit_data.extra_constraints_ab = extra_cons_content
                    else:
                        # Fallback: If response doesn't exist, try to extract from key_content (though may not have tags)
                        if key_content:
                            import re
                            # Try to extract XML tags from key_content
                            zps_pattern = r'<zps>(.*?)</zps>'
                            zps_matches = list(re.finditer(zps_pattern, key_content, re.DOTALL | re.IGNORECASE))
                            if zps_matches:
                                last_zps_match = zps_matches[-1]
                                zps_content = last_zps_match.group(1).strip()
                                if zps_content and zps_content != '`and`' and len(zps_content) > 10:
                                    circuit_data.zero_pole_expressions = zps_content
                            
                            extra_cons_pattern = r'<extra_cons>(.*?)</extra_cons>'
                            extra_cons_matches = list(re.finditer(extra_cons_pattern, key_content, re.DOTALL | re.IGNORECASE))
                            if extra_cons_matches:
                                last_extra_cons_match = extra_cons_matches[-1]
                                extra_cons_content = last_extra_cons_match.group(1).strip()
                                if extra_cons_content and extra_cons_content != '`and`' and len(extra_cons_content) >= 10:
                                    has_constraint_c = (re.search(r'\*\*C\d+', extra_cons_content) or 
                                                      'C1' in extra_cons_content or 'C2' in extra_cons_content)
                                    has_constraint_d = (re.search(r'\*\*D\d+', extra_cons_content) or 
                                                      'D1' in extra_cons_content or 'D2' in extra_cons_content)
                                    if has_constraint_c or has_constraint_d:
                                        circuit_data.extra_constraints_cd = extra_cons_content
                                    else:
                                        if not circuit_data.extra_constraints_ab:
                                            circuit_data.extra_constraints_ab = extra_cons_content
                
                # Step 7: Optimization code and results
                elif step_number == 7 or 'white_box_optimization_programming' in step_name or 'step7' in step_name.lower() or 'white_box' in step_name.lower():
                    # Extract complete information from original result
                    original_result = chain_item.get('_original_result', {})
                    execution_results = original_result.get('execution_results', [])
                    if execution_results and len(execution_results) > 0:
                        execution_result = execution_results[0]
                        
                        # Note: Design variables are now extracted from step 8's param file, no longer from step 7's stdout
                        # Do not extract design variables here, wait for step 8 to process
                        
                        # Extract white-box predicted performance values (parse from execution_result's stdout)
                        from core.circuit_scoring import _get_execution_log_string
                        log_string = _get_execution_log_string(execution_result)
                        
                        if log_string:
                            whitebox_perf = {}
                            perf_patterns = [
                                (r'Gain:\s*([\d.]+)\s*dB', 'whitebox_gain'),
                                (r'GBW:\s*([\d.]+)\s*MHz', 'whitebox_gbw'),  # Convert to Hz
                                (r'PM:\s*([\d.]+)\s*deg', 'whitebox_pm'),
                                (r'Power:\s*([\d.]+)\s*(?:u|μ)W', 'whitebox_power'),  # Convert to W
                            ]
                            for pattern, key in perf_patterns:
                                match = re.search(pattern, log_string)
                                if match:
                                    try:
                                        value = float(match.group(1))
                                        # Unit conversion: MHz -> Hz, μW -> W
                                        if key == 'whitebox_gbw':
                                            value = value * 1e6  # MHz to Hz
                                        elif key == 'whitebox_power':
                                            value = value * 1e-6  # μW to W
                                        whitebox_perf[key] = value
                                    except (ValueError, AttributeError):
                                        pass
                            
                            if whitebox_perf:
                                circuit_data.whitebox_predicted_performance = whitebox_perf
                    
                    # Find code file
                    code_files = original_result.get('python_codes', [])
                    if code_files and len(code_files) > 0:
                        circuit_data.optimization_code_file = code_files[0]
                # Step 8: Simulation results
                elif step_number == 8 or 'simulation_verification' in step_name or 'step8' in step_name.lower() or 'generate_numerical' in step_name.lower():
                    # Extract complete information from original result
                    original_result = chain_item.get('_original_result', {})
                    circuit_data.simulation_results = original_result.get('simulation_results', {})
                    
                    # Extract design variables from param file
                    if not circuit_data.optimization_design_vars:
                        # Try to find param file from sim_dir in simulation_results
                        sim_dir = circuit_data.simulation_results.get('sim_dir', '') if circuit_data.simulation_results else ''
                        if sim_dir:
                            # Try two possible locations
                            param_file_paths = [
                                os.path.join(sim_dir, 'param'),
                                os.path.join(sim_dir, '..', 'param'),  # param in iteration directory
                            ]
                            for param_path in param_file_paths:
                                if os.path.exists(param_path):
                                    circuit_data.optimization_design_vars = self._extract_design_vars_from_param_file(param_path)
                                    if circuit_data.optimization_design_vars:
                                        logger.debug(f"Successfully extracted design variables from param file: {param_path}")
                                        break
                        
                        # If still not found, try to infer from output_dir and iteration information
                        if not circuit_data.optimization_design_vars and output_dir:
                            # Get iteration information from chain_item
                            iteration = chain_item.get('iteration', 1)
                            param_file_paths = [
                                os.path.join(output_dir, f'iteration_{iteration:02d}', 'simulation_verification', 'param'),
                                os.path.join(output_dir, f'iteration_{iteration:02d}', 'param'),
                            ]
                            for param_path in param_file_paths:
                                if os.path.exists(param_path):
                                    circuit_data.optimization_design_vars = self._extract_design_vars_from_param_file(param_path)
                                    if circuit_data.optimization_design_vars:
                                        logger.debug(f"Successfully extracted design variables from param file: {param_path}")
                                        break
                    
                    # Note: performance field has been removed, directly use simulation_results
                    # If both white-box predicted values and simulation results exist, automatically calculate scores
                    if circuit_data.whitebox_predicted_performance and circuit_data.simulation_results:
                        from core.circuit_scoring import calculate_comprehensive_score
                        try:
                            score_dict = calculate_comprehensive_score(circuit_data, circuit_data.design_requirements)
                            circuit_data.comprehensive_score = score_dict['comprehensive_score']
                            circuit_data.prediction_accuracy_score = score_dict['score1']
                            circuit_data.constraint_satisfaction_score = score_dict['score2']
                            # Automatically set is_valid: score2 > 1.0 means all constraints are satisfied
                            circuit_data.is_valid = (circuit_data.constraint_satisfaction_score is not None and 
                                                     circuit_data.constraint_satisfaction_score > 1.0)
                        except Exception as e:
                            logger.warning(f"Failed to calculate comprehensive score: {e}")
                            circuit_data.is_valid = False
                
                # Step 9: Design result analysis and decision-making (extract complete comparison_analysis)
                elif step_number == 9 or 'design_result_analysis_and_decision_making' in step_name or 'step9' in step_name.lower() or 'intelligent_comparison' in step_name.lower():
                    comparison_analysis = ''
                    
                    # Method 1: Extract from _original_result's response (preferred method, contains complete XML tags)
                    original_result = chain_item.get('_original_result', {})
                    response = original_result.get('clean_response', original_result.get('response', '')) if original_result else ''
                    
                    # If response doesn't exist or is empty, fallback to reading from saved file
                    if not response or not response.strip():
                        saved_file = chain_item.get('saved_file', '')
                        if saved_file and output_dir:
                            # Build full path
                            if os.path.isabs(saved_file):
                                file_path = saved_file
                            else:
                                candidate_paths = [saved_file]
                                if output_dir not in saved_file:
                                    candidate_paths.append(os.path.join(output_dir, saved_file))
                                
                                file_path = None
                                for path in candidate_paths:
                                    if os.path.exists(path):
                                        file_path = path
                                        break
                                
                                if not file_path:
                                    file_path = saved_file
                            
                            try:
                                if os.path.exists(file_path):
                                    with open(file_path, 'r', encoding='utf-8') as f:
                                        response = f.read()
                            except Exception as e:
                                logger.warning(f"Step 9 unable to read from file: {e}")
                                response = ''
                    
                    if response:
                        import re
                        # Extract <comparison_analysis> tag content (use last match)
                        comp_pattern = r'<comparison_analysis>(.*?)</comparison_analysis>'
                        comp_matches = list(re.finditer(comp_pattern, response, re.DOTALL | re.IGNORECASE))
                        if comp_matches:
                            last_match = comp_matches[-1]
                            comparison_analysis = last_match.group(1).strip()
                            # Verify content is not empty or just an example (like "...")
                            if not comparison_analysis or comparison_analysis == '...' or len(comparison_analysis) < 50:
                                if len(comp_matches) > 1:
                                    second_last_match = comp_matches[-2]
                                    comparison_analysis = second_last_match.group(1).strip()
                                else:
                                    comparison_analysis = ''
                        else:
                            # If no XML tags, try to extract from "### Comparison Analysis" section
                            comp_section_pattern = r'###\s*Comparison Analysis\s*\n(.*?)(?=###|</comparison_analysis>|$)'
                            comp_section_match = re.search(comp_section_pattern, response, re.DOTALL)
                            if comp_section_match:
                                comparison_analysis = comp_section_match.group(1).strip()
                    
                    # Method 2: If method 1 fails, extract from _original_result's comparison_analysis field
                    if not comparison_analysis and original_result:
                        comparison_analysis = original_result.get('comparison_analysis', '')
                    
                    if comparison_analysis:
                        # Directly save original text content
                        circuit_data.whitebox_blackbox_comparison = comparison_analysis
                        logger.debug(f"Step 9 successfully extracted comparison_analysis: {len(comparison_analysis)} characters")
                
            except Exception as e:
                # Log error but don't interrupt
                logger.error(f"⚠️ Failed to extract step data {step_name}: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    def _extract_tagged_content(self, text: str, tag: str) -> Optional[str]:
        """Extract tagged content (e.g., <cooked_formula>...</cooked_formula>)"""
        if not text or not tag:
            return None
        
        pattern = f'<{tag}>(.*?)</{tag}>'
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            content = match.group(1).strip()
            # Clean content
            content = re.sub(r'^\s*\n+', '', content)  # Remove leading empty lines
            content = re.sub(r'\n+\s*$', '', content)  # Remove trailing empty lines
            return content if content else None
        return None
    
    def _extract_design_vars_from_param_file(self, param_file_path: str) -> Dict:
        """Extract design variables from param file
        
        Args:
            param_file_path: Param file path
            
        Returns:
            Design variable dictionary, format: {'G_1': value, 'G_2': value, ...}
        """
        design_vars = {}
        
        if not param_file_path or not os.path.exists(param_file_path):
            return design_vars
        
        try:
            with open(param_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Parse format: .param variable_name = value
                    # Example: .param G_1 = 10.00e-6
                    if line.startswith('.param'):
                        # Remove .param prefix
                        content = line[6:].strip()
                        # Split variable name and value
                        if '=' in content:
                            parts = content.split('=', 1)
                            var_name = parts[0].strip()
                            value_str = parts[1].strip()
                            
                            try:
                                # Handle scientific notation (e.g., 10.00e-6) and regular numbers
                                value = float(value_str)
                                design_vars[var_name] = value
                            except (ValueError, AttributeError):
                                logger.warning(f"Unable to parse value in param file: {var_name} = {value_str}")
                                pass
        except Exception as e:
            logger.error(f"⚠️ Failed to extract design variables from param file: {e}")
        
        return design_vars
    
    def _extract_design_vars(self, execution_result) -> Dict:
        """Extract design variables from optimization results (deprecated, kept for compatibility)
        
        Note: This method is no longer used, design variables are now extracted from param files.
        This method is kept only for backward compatibility.
        
        Args:
            execution_result: Can be a dict (containing 'stdout' field) or string
        """
        # This method is deprecated, return empty dict
        return {}
    
    def _parse_comparison_analysis(self, comparison_analysis: str) -> str:
        """
        Parse comparison analysis content (deprecated, now directly returns original text)
        
        Args:
            comparison_analysis: Complete comparison_analysis text
        
        Returns:
            Original text content
        """
        # This method is deprecated, directly return original text
        return comparison_analysis
    
    def get_circuit_data(self, netlist: str) -> Optional[CircuitData]:
        """Get complete circuit data"""
        netlist_hash = hash_netlist(netlist)
        return self.circuit_data.get(netlist_hash)
    
    def get_all_circuit_data(self) -> List[CircuitData]:
        """Get all circuit data"""
        return list(self.circuit_data.values())
    
    def get_circuit_by_performance(self, min_fom: float = None, 
                                   min_gain: float = None,
                                   min_pm: float = None) -> List[CircuitData]:
        """Filter circuits by performance metrics"""
        results = []
        for circuit_data in self.circuit_data.values():
            perf = circuit_data.simulation_results or {}
            if min_fom and perf.get('fom', 0) < min_fom:
                continue
            if min_gain and perf.get('gain', 0) < min_gain:
                continue
            if min_pm and perf.get('phase_margin', 0) < min_pm:
                continue
            results.append(circuit_data)
        return results
    
    def get_circuit_by_score(self, min_score: float = None,
                             design_requirements: 'DesignRequirements' = None) -> List[CircuitData]:
        """
        Filter circuits by comprehensive score
        
        Args:
            min_score: Minimum comprehensive score
            design_requirements: Design requirements object (required, for calculating comprehensive score)
        
        Returns:
            List of CircuitData objects meeting score requirements, sorted by comprehensive score in descending order
        """
        if not design_requirements:
            # If design_requirements not provided, fall back to filtering by FOM
            return self.get_circuit_by_performance(min_fom=min_score)
        
        from core.circuit_scoring import calculate_comprehensive_score
        
        results = []
        for circuit_data in self.circuit_data.values():
            try:
                score_dict = calculate_comprehensive_score(circuit_data, design_requirements)
                score = score_dict['comprehensive_score']
                if min_score is None or score >= min_score:
                    results.append((circuit_data, score))
            except Exception:
                # If calculation fails, skip this circuit
                continue
        
        # Sort by comprehensive score in descending order
        results.sort(key=lambda x: x[1], reverse=True)
        return [circuit_data for circuit_data, _ in results]
    
    def save_all_circuit_data(self, output_dir: str, circuit_id: str = None):
        """Save circuit data to JSON file
        
        Args:
            output_dir: Output directory
            circuit_id: If provided, only save the specified circuit_id; otherwise save all data (backward compatibility)
        """
        data_dir = os.path.join(output_dir, 'circuit_data')
        os.makedirs(data_dir, exist_ok=True)
        
        if circuit_id:
            # Only save the specified circuit_id
            if circuit_id in self.circuit_data:
                try:
                    filepath = os.path.join(data_dir, f"{circuit_id}.json")
                    self.circuit_data[circuit_id].save_to_file(filepath)
                    logger.info(f"✅ Saved circuit data {circuit_id[:8]}... to {data_dir}")
                except Exception as e:
                    logger.error(f"⚠️ Failed to save circuit data {circuit_id[:8]}...: {e}")
            else:
                logger.warning(f"⚠️ Circuit data {circuit_id[:8]}... does not exist, skipping save")
        else:
            # Save all data (backward compatibility)
            saved_count = 0
            for netlist_hash, circuit_data in self.circuit_data.items():
                try:
                    filepath = os.path.join(data_dir, f"{netlist_hash}.json")
                    circuit_data.save_to_file(filepath)
                    saved_count += 1
                except Exception as e:
                    logger.error(f"⚠️ Failed to save circuit data {netlist_hash}: {e}")
            
            logger.info(f"✅ Saved {saved_count}/{len(self.circuit_data)} circuit data to {data_dir}")
    
    def load_all_circuit_data(self, data_dir: str):
        """Load all circuit data from JSON files"""
        if not os.path.exists(data_dir):
            logger.warning(f"⚠️ Circuit data directory does not exist: {data_dir}")
            return
        
        loaded_count = 0
        for filename in os.listdir(data_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(data_dir, filename)
                try:
                    circuit_data = CircuitData.load_from_file(filepath)
                    self.circuit_data[circuit_data.circuit_id] = circuit_data
                    loaded_count += 1
                except Exception as e:
                    logger.error(f"⚠️ Failed to load circuit data {filename}: {e}")
        
        logger.info(f"✅ Loaded {loaded_count} circuit data")
    
    def _classify_situation(self, p2m_results: List[Dict]) -> str:
        """Classify situation from P2M results"""
        step7_success = False
        step8_success = False
        
        for result in p2m_results:
            # Use step_number for robust step identification
            if result.get('step_number') == 7 or 'white_box_optimization_programming' in result.get('step', ''):
                step7_success = result.get('success', False)
            if result.get('step_number') == 8 or 'simulation_verification' in result.get('step', ''):
                step8_success = result.get('success', False)
        
        if not step7_success:
            return "Situation 2"
        elif step7_success and not step8_success:
            return "Situation 1-c"
        else:
            # Need to judge consistency (simplified handling, default to 1-a)
            return "Situation 1-a or 1-b"
    
    def get_history_summary(self, max_entries: int = 5) -> str:
        """Generate history summary (for passing to M2P chain)"""
        if not self.topologies:
            return "No exploration history"
        
        summary_lines = ["## Exploration History Summary\n"]
        
        # Get recent exploration records
        recent_entries = list(self.topologies.values())[-max_entries:]
        
        for i, entry in enumerate(recent_entries, 1):
            summary_lines.append(f"\n### Exploration Record {i}")
            summary_lines.append(f"- **Situation Classification**: {entry['situation']}")
            perf = entry['performance']
            if perf:
                summary_lines.append(f"- **Performance Metrics**:")
                summary_lines.append(f"  - FoM: {perf.get('fom', 0):.2f}")
                summary_lines.append(f"  - Gain: {perf.get('gain', 0):.2f} dB")
                summary_lines.append(f"  - Bandwidth: {perf.get('ugf', 0)/1e6:.2f} MHz")
        
        return "\n".join(summary_lines)

