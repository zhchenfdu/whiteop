"""
Step 2: List Equations

List circuit equations based on netlist.
"""

import os
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..pipeline import CircuitAnalysisPipeline

from core import PromptFileNotFoundError


def step2_list_equations(pipeline: 'CircuitAnalysisPipeline') -> Dict:
    """
    Step 2: List equations (v9 version: read prompt from file)
    
    Args:
        pipeline: CircuitAnalysisPipeline instance
    
    Returns:
        Step execution result dictionary
    """
    # Load prompt template from file
    from core import load_prompt_from_file
    prompt_file = os.path.join(pipeline.prompts_dir, "step2_circuit_equation_formulation.md")
    prompt = load_prompt_from_file(prompt_file)
    
    if not prompt:
        raise PromptFileNotFoundError(prompt_file, step_name="circuit_equation_formulation")
    
    return pipeline.execute_step("circuit_equation_formulation", prompt, "raw_eq")
