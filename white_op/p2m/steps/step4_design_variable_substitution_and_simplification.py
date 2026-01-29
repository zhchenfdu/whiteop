"""
Step 4: Substitute and Simplify

Substitute and simplify transfer function.
"""

import os
from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..pipeline import CircuitAnalysisPipeline

from core import PromptFileNotFoundError


def step4_substitute_simplify(pipeline: 'CircuitAnalysisPipeline') -> Dict:
    """
    Step 4: Substitute and simplify (v9 version: read prompt from file)
    
    Args:
        pipeline: CircuitAnalysisPipeline instance
    
    Returns:
        Step execution result dictionary
    """
    # Load prompt template from file
    from core import load_prompt_from_file
    prompt_file = os.path.join(pipeline.prompts_dir, "step4_design_variable_substitution_and_simplification.md")
    prompt = load_prompt_from_file(prompt_file)
    
    if not prompt:
        raise PromptFileNotFoundError(prompt_file, step_name="design_variable_substitution_and_simplification")
    
    return pipeline.execute_step("design_variable_substitution_and_simplification", prompt, "real_hs")
