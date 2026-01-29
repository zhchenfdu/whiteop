"""
Core module (core).

Provides shared configuration, data models, utilities, and logging.
These modules are depended on by the rest of the project.
"""

# Import configuration classes
from .config import PipelineConfig, DesignRequirements

# Import result formatter
from .result_formatter import ResultFormatter

# Import data models
from .data_models import CircuitData, ExplorationHistory

# Import utility functions
from .utils import (
    generate_output_dir,
    load_prompt_from_file,
    hash_netlist,
    extract_performance_from_result
)

# Import circuit scoring functions
from .circuit_scoring import (
    extract_whitebox_performance,
    calculate_prediction_accuracy_score,
    calculate_constraint_satisfaction_score,
    calculate_comprehensive_score
)

# Import logging system
from .logger import (
    setup_logging,
    StreamToLogger,
    LoggerManager,
    ThreadSafeLogger,
    get_logger,
    get_parallel_task_logger
)

# Import exception classes
from .exceptions import (
    # Base exception classes
    PipelineError,
    # P2M related exceptions
    P2MAnalysisError,
    PromptFileNotFoundError,
    PromptFormatError,
    StepExecutionError,
    APICallError,
    APITimeoutError,
    # Configuration related exceptions
    ConfigurationError,
    ConfigFileNotFoundError,
    InvalidConfigError,
    # Data model related exceptions
    DataModelError,
    DataValidationError,
    DataExtractionError,
    # Simulation related exceptions
    SimulationError,
    HSPICESimulationError,
    HSPICETimeoutError,
    CodeExecutionError,
    CodeExecutionTimeoutError,
)

__version__ = "1.0.0"

__all__ = [
    # Configuration classes
    'PipelineConfig',
    'DesignRequirements',
    # Result formatter
    'ResultFormatter',
    # Data models
    'CircuitData',
    'ExplorationHistory',
    # Utility functions
    'generate_output_dir',
    'load_prompt_from_file',
    'hash_netlist',
    'extract_performance_from_result',
    # Circuit scoring functions
    'extract_whitebox_performance',
    'calculate_prediction_accuracy_score',
    'calculate_constraint_satisfaction_score',
    'calculate_comprehensive_score',
    # Logging system
    'setup_logging',
    'StreamToLogger',
    'LoggerManager',
    'ThreadSafeLogger',
    'get_logger',
    'get_parallel_task_logger',
    # Exception classes
    'PipelineError',
    'P2MAnalysisError',
    'PromptFileNotFoundError',
    'PromptFormatError',
    'StepExecutionError',
    'APICallError',
    'APITimeoutError',
    'ConfigurationError',
    'ConfigFileNotFoundError',
    'InvalidConfigError',
    'DataModelError',
    'DataValidationError',
    'DataExtractionError',
    'SimulationError',
    'HSPICESimulationError',
    'HSPICETimeoutError',
    'CodeExecutionError',
    'CodeExecutionTimeoutError',
]
