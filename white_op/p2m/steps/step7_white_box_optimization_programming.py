"""
Step 7: White-Box Optimization

Execute white-box optimization.
"""

import os
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..pipeline import CircuitAnalysisPipeline

from core import PromptFileNotFoundError


def step7_white_box_optimization(pipeline: 'CircuitAnalysisPipeline') -> Dict:
    """
    Step 7: White-box optimization (v9 version: read prompt from file)
    
    Args:
        pipeline: CircuitAnalysisPipeline instance
    
    Returns:
        Step execution result dictionary
    """
    # Load prompt from file
    from core import load_prompt_from_file
    prompt_file = os.path.join(pipeline.prompts_dir, "step7_white_box_optimization_programming.md")
    prompt = load_prompt_from_file(prompt_file)
    
    if not prompt:
        raise PromptFileNotFoundError(prompt_file, step_name="white_box_optimization_programming")

    return pipeline.execute_step("white_box_optimization_programming", prompt, None)
