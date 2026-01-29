"""
Unified exception definitions.

All project-specific exceptions inherit from PipelineError, providing
consistent formatting and optional context/original-error attachment.

Exception hierarchy:
    PipelineError
    ├── P2MAnalysisError
    │   ├── PromptFileNotFoundError
    │   ├── PromptFormatError
    │   ├── StepExecutionError
    │   └── APICallError
    │       └── APITimeoutError
    ├── ConfigurationError
    │   ├── ConfigFileNotFoundError
    │   └── InvalidConfigError
    ├── DataModelError
    │   ├── DataValidationError
    │   └── DataExtractionError
    └── SimulationError
        ├── HSPICESimulationError
        │   └── HSPICETimeoutError
        └── CodeExecutionError
            └── CodeExecutionTimeoutError
"""

from typing import Dict, Optional, Any


class PipelineError(Exception):
    """Base exception class for the project.

    Provides consistent formatting with optional context and an original wrapped error.

    Attributes:
        message: error message
        context: context dict
        original_error: wrapped original exception (optional)
    """
    def __init__(self, message: str, context: Optional[Dict] = None, original_error: Optional[Exception] = None):
        """
        Args:
            message: Error message
            context: Error context information (optional)
            original_error: Original exception (if wrapping another exception)
        """
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.original_error = original_error
    
    def __str__(self):
        """Format error message with optional context and original error."""
        base_msg = self.message
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            base_msg = f"{base_msg} (context: {context_str})"
        if self.original_error:
            base_msg = f"{base_msg} (original_error: {self.original_error})"
        return base_msg


# ========== P2M Analysis Related Exceptions ==========

class P2MAnalysisError(PipelineError):
    """P2M analysis errors."""
    pass


class PromptFileNotFoundError(P2MAnalysisError):
    """Raised when a prompt file cannot be found.

    Args:
        prompt_file: prompt file path
        step_name: optional step name
    """
    def __init__(self, prompt_file: str, step_name: Optional[str] = None):
        if step_name:
            message = f"Prompt file not found for step {step_name}: {prompt_file}"
        else:
            message = f"Prompt file not found: {prompt_file}"
        super().__init__(message, context={'prompt_file': prompt_file, 'step_name': step_name})


class PromptFormatError(P2MAnalysisError):
    """Raised when prompt formatting fails (usually KeyError/ValueError).

    Args:
        step_name: step name
        format_error: original formatting exception
        prompt_file: optional prompt file path
    """
    def __init__(self, step_name: str, format_error: Exception, prompt_file: Optional[str] = None):
        message = f"Prompt formatting failed for step {step_name}: {format_error}"
        super().__init__(
            message, 
            context={'step_name': step_name, 'prompt_file': prompt_file},
            original_error=format_error
        )


class StepExecutionError(P2MAnalysisError):
    """Raised when a P2M step fails.

    Args:
        step_name: step name
        error_message: error message
        step_result: optional step result dict
    """
    def __init__(self, step_name: str, error_message: str, step_result: Optional[Dict] = None):
        message = f"Step execution failed ({step_name}): {error_message}"
        super().__init__(message, context={'step_name': step_name, 'step_result': step_result})


class APICallError(P2MAnalysisError):
    """Raised when an API call fails.

    Args:
        error_message: error message
        status_code: optional HTTP status code
        response_text: optional response body
    """
    def __init__(self, error_message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        message = f"API call failed: {error_message}"
        super().__init__(
            message, 
            context={'status_code': status_code, 'response_text': response_text}
        )


class APITimeoutError(APICallError):
    """Raised when an API request times out.
    
    Args:
        timeout_seconds: optional timeout seconds
    """
    def __init__(self, timeout_seconds: Optional[int] = None):
        if timeout_seconds:
            message = f"API request timed out ({timeout_seconds}s)"
        else:
            message = "API request timed out"
        # NOTE: APICallError.__init__ doesn't accept a context param directly in this usage.
        super(APICallError, self).__init__(message, context={'timeout_seconds': timeout_seconds})


# ========== Configuration Related Exceptions ==========

class ConfigurationError(PipelineError):
    """Configuration-related errors."""
    pass


class ConfigFileNotFoundError(ConfigurationError):
    """Raised when a configuration file cannot be found.

    Args:
        config_file: config file path
    """
    def __init__(self, config_file: str):
        message = f"Config file not found: {config_file}"
        super().__init__(message, context={'config_file': config_file})


class InvalidConfigError(ConfigurationError):
    """Raised when a configuration value is invalid.

    Args:
        config_key: config key
        config_value: config value
        reason: optional reason
    """
    def __init__(self, config_key: str, config_value: Any, reason: Optional[str] = None):
        message = f"Invalid config: {config_key}={config_value}"
        if reason:
            message = f"{message} ({reason})"
        super().__init__(message, context={'config_key': config_key, 'config_value': config_value})


# ========== Data Model Related Exceptions ==========

class DataModelError(PipelineError):
    """Data model errors."""
    pass


class DataValidationError(DataModelError):
    """Raised when data validation fails.

    Args:
        field_name: field name
        field_value: field value
        reason: optional reason
    """
    def __init__(self, field_name: str, field_value: Any, reason: Optional[str] = None):
        message = f"Data validation failed: {field_name}={field_value}"
        if reason:
            message = f"{message} ({reason})"
        super().__init__(message, context={'field_name': field_name, 'field_value': field_value})


class DataExtractionError(DataModelError):
    """Raised when data extraction fails.

    Args:
        extraction_target: extraction target
        error_message: error message
    """
    def __init__(self, extraction_target: str, error_message: str):
        message = f"Data extraction failed ({extraction_target}): {error_message}"
        super().__init__(message, context={'extraction_target': extraction_target})


# ========== Simulation Related Exceptions ==========

class SimulationError(PipelineError):
    """Simulation-related errors."""
    pass


class HSPICESimulationError(SimulationError):
    """Raised when an HSPICE simulation fails.

    Args:
        error_message: error message
        hspice_output: optional HSPICE output
        return_code: optional return code
    """
    def __init__(self, error_message: str, hspice_output: Optional[str] = None, return_code: Optional[int] = None):
        message = f"HSPICE simulation failed: {error_message}"
        super().__init__(
            message, 
            context={'hspice_output': hspice_output, 'return_code': return_code}
        )


class HSPICETimeoutError(HSPICESimulationError):
    """Raised when an HSPICE simulation times out.

    Args:
        timeout_seconds: timeout in seconds
    """
    def __init__(self, timeout_seconds: int):
        message = f"HSPICE simulation timed out ({timeout_seconds}s)"
        # Directly call PipelineError.__init__ since HSPICESimulationError already handled context.
        PipelineError.__init__(self, message, context={'timeout_seconds': timeout_seconds})


class CodeExecutionError(SimulationError):
    """Raised when code execution fails.

    Args:
        error_message: error message
        code_snippet: optional code snippet
        execution_output: optional execution output
    """
    def __init__(self, error_message: str, code_snippet: Optional[str] = None, execution_output: Optional[str] = None):
        message = f"Code execution failed: {error_message}"
        super().__init__(
            message, 
            context={'code_snippet': code_snippet, 'execution_output': execution_output}
        )


class CodeExecutionTimeoutError(CodeExecutionError):
    """Raised when code execution times out.

    Args:
        timeout_seconds: timeout in seconds
    """
    def __init__(self, timeout_seconds: int):
        message = f"Code execution timed out ({timeout_seconds}s)"
        # Directly call PipelineError.__init__ since CodeExecutionError already handled context.
        PipelineError.__init__(self, message, context={'timeout_seconds': timeout_seconds})

