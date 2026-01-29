"""
Step 1: Read Netlist

Read circuit information from netlist file.
"""

import os
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..pipeline import CircuitAnalysisPipeline
    from core import load_prompt_from_file

from core import PromptFileNotFoundError, PromptFormatError


def step1_read_netlist(pipeline: 'CircuitAnalysisPipeline', netlist: str) -> Dict:
    """
    Step 1: Read netlist (v9 version: read prompt from file)
    
    Args:
        pipeline: CircuitAnalysisPipeline instance
        netlist: Netlist content
    
    Returns:
        Step execution result dictionary
    """
    # Save original netlist
    pipeline.original_netlist = netlist
    
    # Load prompt template from file
    from core import load_prompt_from_file
    prompt_file = os.path.join(pipeline.prompts_dir, "step1_circuit_topology_interpretation.md")
    prompt_template = load_prompt_from_file(prompt_file)
    
    if not prompt_template:
        raise PromptFileNotFoundError(prompt_file, step_name="circuit_topology_interpretation")
    
    # Format prompt, replace placeholders
    try:
        prompt = prompt_template.format(netlist_content=netlist)
    except (KeyError, ValueError) as e:
        raise PromptFormatError("circuit_topology_interpretation", e, prompt_file=prompt_file)
    
    return pipeline.execute_step("circuit_topology_interpretation", prompt, "description")
