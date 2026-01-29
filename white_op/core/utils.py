"""
Utility functions (utils).

Common helpers:
- generate_output_dir: create a unique timestamped output directory
- load_prompt_from_file: load a prompt template from disk
- hash_netlist: compute a stable hash for a netlist (normalized)
- extract_performance_from_result: extract performance metrics from pipeline results
"""

import os
import hashlib
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def generate_output_dir(base_name: str = "pipeline_outputs", experiments_dir: str = "experiments", topology_suffix: Optional[str] = None) -> str:
    """
    Create a unique output directory based on current time.

    The directory will be created under `experiments/` for unified experiment management.

    Args:
        base_name: base directory name, default "pipeline_outputs"
        experiments_dir: experiments directory, default "experiments"
        topology_suffix: optional topology suffix appended to the directory name

    Returns:
        A formatted directory path, e.g.
        - "experiments/pipeline_outputs_20251112_153045" (no suffix)
        - "experiments/pipeline_outputs_20251112_153045_DFCFC" (with suffix)
    """
    # Ensure experiments directory exists
    if not os.path.exists(experiments_dir):
        os.makedirs(experiments_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"{base_name}_{timestamp}"
    
    # Append topology suffix if provided
    if topology_suffix:
        dir_name = f"{dir_name}_{topology_suffix}"
    
    return os.path.join(experiments_dir, dir_name)


def load_prompt_from_file(prompt_file: str) -> str:
    """
    Load prompt content from file.

    Args:
        prompt_file: prompt file path

    Returns:
        File content; returns an empty string if file is missing or unreadable.
    """
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Prompt file not found: {prompt_file}")
        return ""
    except Exception as e:
        logger.error(f"Failed to read prompt file {prompt_file}: {e}")
        return ""


def hash_netlist(netlist: str) -> str:
    """
    Compute a stable hash for a netlist (used for de-duplication).

    Unified implementation (merged from earlier demo variants).

    Args:
        netlist: netlist content

    Returns:
        MD5 hash of the normalized netlist
    """
    # Normalize netlist (remove whitespace differences and comments)
    normalized = '\n'.join(
        line.strip() for line in netlist.split('\n') 
        if line.strip() and not line.strip().startswith('*')
    )
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def extract_performance_from_result(result: Dict) -> Optional[Dict]:
    """
    Extract performance metrics from P2M results.

    Unified implementation (extracted from earlier demo variants).

    Args:
        result: P2M result dict, may include:
            - best_iteration
            - p2m_results

    Returns:
        Dict containing gain, ugf, phase_margin, power, fom; returns None if unavailable.
    """
    # Method 1: from best_iteration
    best_iteration = result.get('best_iteration')
    if best_iteration and 'results' in best_iteration:
        for step_result in best_iteration['results']:
            sim_results = step_result.get('simulation_results', {})
            if sim_results:
                return {
                    'gain': sim_results.get('gain', 0),
                    'ugf': sim_results.get('ugf', 0),
                    'phase_margin': sim_results.get('phase_margin', 0),
                    'power': sim_results.get('power', 0),
                    'fom': sim_results.get('fom', 0)
                }
    
    # Method 2: from p2m_results (backward compatible)
    p2m_results = result.get('p2m_results', [])
    for step_result in p2m_results:
        sim_results = step_result.get('simulation_results', {})
        if sim_results:
            return {
                'gain': sim_results.get('gain', 0),
                'ugf': sim_results.get('ugf', 0),
                'phase_margin': sim_results.get('phase_margin', 0),
                'power': sim_results.get('power', 0),
                'fom': sim_results.get('fom', 0)
            }
    
    return None
