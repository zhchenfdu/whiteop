"""
Step 5: Factorize and Reduce

Factorize and reduce transfer function.
"""

import os
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..pipeline import CircuitAnalysisPipeline

from core import PromptFileNotFoundError


def step5_factorize_reduce(pipeline: 'CircuitAnalysisPipeline') -> Dict:
    """
    Step 5: Factorize and reduce (v9 version: read prompt from file)
    
    Args:
        pipeline: CircuitAnalysisPipeline instance
    
    Returns:
        Step execution result dictionary
    """
    # Load prompt template from file
    from core import load_prompt_from_file
    prompt_file = os.path.join(pipeline.prompts_dir, "step5_pole_and_zero_extraction.md")
    prompt = load_prompt_from_file(prompt_file)
    
    if not prompt:
        raise PromptFileNotFoundError(prompt_file, step_name="pole_and_zero_extraction")
    
    return pipeline.execute_step("pole_and_zero_extraction", prompt, "cooked_hs")
