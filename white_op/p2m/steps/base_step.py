"""
Step Base Class (base_step)

Defines common interfaces and helper methods for all P2M steps.
"""

from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ..pipeline import CircuitAnalysisPipeline


class BaseStep:
    """Step base class"""
    
    def __init__(self, pipeline: 'CircuitAnalysisPipeline'):
        """
        Initialize step
        
        Args:
            pipeline: CircuitAnalysisPipeline instance, provides execute_step and other methods
        """
        self.pipeline = pipeline
    
    def execute(self, *args, **kwargs) -> Dict:
        """
        Execute step (must be implemented by subclasses)
        
        Returns:
            Step execution result dictionary
        """
        raise NotImplementedError("Subclass must implement execute method")


def step_function(pipeline: 'CircuitAnalysisPipeline', *args, **kwargs) -> Dict:
    """
    Step function interface (for functional steps)
    
    All step functions should follow this signature:
    - First parameter is pipeline instance
    - Other parameters as needed by the step
    
    Args:
        pipeline: CircuitAnalysisPipeline instance
        *args, **kwargs: Step-specific parameters
    
    Returns:
        Step execution result dictionary
    """
    raise NotImplementedError("Step function must be implemented")


