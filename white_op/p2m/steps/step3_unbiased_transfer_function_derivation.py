"""
Step 3: Solve Transfer Function

Solve unbiased transfer function.
"""

import os
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..pipeline import CircuitAnalysisPipeline

from core import PromptFileNotFoundError


def step3_solve_transfer_function(pipeline: 'CircuitAnalysisPipeline') -> Dict:
    """
    Step 3: Unbiased solving (v9 version: read prompt from file)
    
    Args:
        pipeline: CircuitAnalysisPipeline instance
    
    Returns:
        Step execution result dictionary
    """
    # Load prompt template from file
    from core import load_prompt_from_file
    prompt_file = os.path.join(pipeline.prompts_dir, "step3_unbiased_transfer_function_derivation.md")
    prompt = load_prompt_from_file(prompt_file)
    
    if not prompt:
        raise PromptFileNotFoundError(prompt_file, step_name="unbiased_transfer_function_derivation")
    
    return pipeline.execute_step("unbiased_transfer_function_derivation", prompt, "raw_hs")
