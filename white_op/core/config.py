"""
Configuration module (config).

Defines PipelineConfig and DesignRequirements.
These classes specify runtime parameters and design requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import logging

from .utils import generate_output_dir


def _default_design_requirements():
    """Helper to lazily create DesignRequirements (avoids forward-reference issues)."""
    # This function is not called during PipelineConfig class definition; only at instantiation time.
    # DesignRequirements is already defined then, but we still access via module dict due to forward refs.
    import sys
    current_module = sys.modules[__name__]
    return current_module.DesignRequirements()


@dataclass
class PipelineConfig:
    """Pipeline configuration."""
    
    # API configuration (placeholders; override via CLI or env/config)
    base_url: str = "http://YOUR_API_SERVER:PORT/v1"
    api_key: str = "YOUR_API_KEY"
    model: str = "YOUR_MODEL_NAME" #recommended: gemini-3-pro-preview
    temperature: float = 1  # default temperature 1
    
    # Output
    output_dir: str = field(default_factory=lambda: generate_output_dir())  # Unique timestamped directory
    enable_python_execution: bool = True  # Whether Python execution is allowed
    netlist_path: Optional[str] = None  # Netlist path (used by result formatter to infer circuit type)
    gmid_map_base: Optional[str] = None  # Base path of gmid_map tool (optional; can be set via CLI/env)
    
    # HSPICE (local execution only; remote execution support removed)
    # Use a placeholder here; users must set their own HSPICE path in local config or via env
    hspice_path: str = "/path/to/your/hspice"
    hspice_timeout: int = 120  # Timeout in seconds
    hspice_remote_enabled: bool = False  # Legacy flag, kept for backward compatibility (no effect)
    
    # Retry/feedback loop
    full_pipeline_max_iterations: int = 5  # Max iterations for full pipeline
    error_threshold: float = 0.1  # Error threshold (e.g., 10%)
    
    # Context management
    enable_thinking_separation: bool = True  # Enable reasoning/thinking separation
    max_context_tokens: int = 100000  # Estimated max context tokens
    
    # Performance logger
    logger: Optional[logging.Logger] = None  # Performance logger instance
    
    # Logging
    log_global_level: int = logging.INFO  # Global level
    log_console_level: int = logging.INFO  # Console level
    log_file_level: int = logging.DEBUG  # File level
    log_enable_console: bool = True  # Enable console logging
    log_enable_file: bool = True  # Enable file logging
    
    # Token stats
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    
    # Prompt files
    prompts_dir: str = "prompts"  # Prompt directory
    
    # P2M stage
    p2m_max_iterations: int = 5  # Max internal P2M iterations
    
    # Circuit data collection
    enable_circuit_data_collection: bool = True
    circuit_data_save_dir: Optional[str] = None  # Default under output_dir
    
    # API retry
    api_timeout: int = 300  # Seconds
    api_max_retries: int = 3
    api_retry_backoff_base: float = 1.0
    api_retry_backoff_max: float = 60.0
    api_retry_enabled: bool = True

    # Design requirements configuration (using string type annotation and lazy creation)
    design_requirements: 'DesignRequirements' = field(default_factory=_default_design_requirements)  # Design requirements (performance boundaries)


@dataclass
class DesignRequirements:
    """Design requirements"""
    
    gain_min_db: float = 60.0
    gbw_min_mhz: float = 0.5
    pm_min_deg: float = 45.0
    pm_max_deg: float = 90.0
    pm_ideal_deg: float = 60.0
    power_max_uw: float = 250.0
    
    def check_constraints(self, gain: float, gbw: float, pm: float, power: float) -> dict:
        """
        Check if design constraints are satisfied
        
        Args:
            gain: Gain (dB)
            gbw: Gain bandwidth product (MHz)
            pm: Phase margin (degrees)
            power: Power consumption (μW)
        
        Returns:
            dict: Contains satisfaction status for each constraint
                - gain_ok: Whether gain is satisfied
                - gbw_ok: Whether GBW is satisfied
                - pm_ok: Whether phase margin is satisfied
                - power_ok: Whether power consumption is satisfied
                - all_ok: Whether all constraints are satisfied
        """
        return {
            'gain_ok': gain >= self.gain_min_db,
            'gbw_ok': gbw >= self.gbw_min_mhz,
            'pm_ok': self.pm_min_deg <= pm <= self.pm_max_deg,
            'power_ok': power <= self.power_max_uw,
            'all_ok': (
                gain >= self.gain_min_db and
                gbw >= self.gbw_min_mhz and
                self.pm_min_deg <= pm <= self.pm_max_deg and
                power <= self.power_max_uw
            )
        }
    
    @classmethod
    def from_config(cls, config: 'PipelineConfig' = None) -> 'DesignRequirements':
        """
        Create design requirements from PipelineConfig
        
        Currently uses default values, can be extracted from config in the future
        
        Args:
            config: PipelineConfig instance (optional)
        
        Returns:
            DesignRequirements instance
        """
        return cls()
