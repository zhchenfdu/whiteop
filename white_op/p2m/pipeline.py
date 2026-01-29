"""
P2M Analysis Pipeline

Contains CircuitAnalysisPipeline class, implements 9-step analysis flow.
"""

import os
import requests
import re
import sys
import time
import subprocess
import json
import socket
from typing import Dict, Optional, List, Tuple
from datetime import datetime

from core import (
    PipelineConfig, DesignRequirements, load_prompt_from_file, setup_logging, ExplorationHistory,
    P2MAnalysisError, PromptFileNotFoundError, PromptFormatError,
    APICallError, APITimeoutError,
    SimulationError, HSPICESimulationError, HSPICETimeoutError,
    CodeExecutionError, CodeExecutionTimeoutError,
)
from core.logger import get_logger
from p2m.steps import (
    step1_read_netlist,
    step2_list_equations,
    step3_solve_transfer_function,
    step4_substitute_simplify,
    step5_factorize_reduce,
    step6_functional_implementation,
    step7_white_box_optimization,
    step8_generate_numerical_netlist,
    step9_intelligent_comparison,
)

class CircuitAnalysisPipeline:
    """Multi-step circuit analysis pipeline (v9 version, prompt file separation mechanism)"""
    
    def __init__(self, config: PipelineConfig = None, design_requirements: DesignRequirements = None):
        self.config = config or PipelineConfig()
        # Design requirements: prioritize passed parameter, then config, finally default value
        # This maintains backward compatibility while supporting new configuration methods
        if design_requirements is not None:
            self.design_requirements = design_requirements
        else:
            self.design_requirements = self.config.design_requirements
        self.headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        # v10 improvement: Set global socket timeout to prevent DNS resolution and connection establishment blocking
        # Set connection timeout to 30 seconds to prevent DNS resolution and connection establishment blocking
        socket.setdefaulttimeout(30)
        
        # v8 new: Dual-track storage system
        self.messages = []  # Only store clean content (for API calls)
        self.full_history = []  # Full history (including thinking)
        self.thinking_cache = {}  # Separate cache for thinking content
        
        self.step_count = 0
        self.original_netlist = ""  # Save original netlist
        
        # v7 feedback mechanism related attributes
        self.iteration_count = 0  # Current iteration count
        self.lessons_learned = ""  # Accumulated lessons learned
        self.cached_steps = {}  # Cache stable step results
        self.retry_from_step = None  # Starting step for retry
        
        # Global step counter
        self.global_step_count = 0
        
        # API error information cache (for saving detailed error information to md files)
        self._last_api_error = None
        
        # Create output directory
        # Note: Only create when output_dir is set, avoid creating empty directories during import or testing
        # If output_dir is not set, it may be an instance created during testing or import, should not create directory
        if self.config.output_dir:
            os.makedirs(self.config.output_dir, exist_ok=True)
        
        # Initialize performance logger
        if self.config.logger is None:
            self.config.logger = setup_logging(self.config.output_dir)
        self.logger = self.config.logger
        
        # Create module logger (for replacing print)
        # Both console and file only show INFO and above levels, keep logs clean
        import logging
        self.module_logger = get_logger(
            name='pipeline', 
            module=__name__, 
            output_dir=self.config.output_dir,
            console=True,
            file=True,
            level=logging.INFO,  # File only saves INFO and above levels
            console_level=logging.INFO  # Console only shows INFO and above
        )
        self.module_logger.info(f"Output directory created: {self.config.output_dir}")
        
        self.logger.info("CircuitAnalysisPipeline initialization completed")
        
        # Create code execution subdirectory
        self.code_dir = f"{self.config.output_dir}/python_codes"
        os.makedirs(self.code_dir, exist_ok=True)
        
        # Create simulation directory
        self.sim_dir = f"{self.config.output_dir}/simulation_verification"
        os.makedirs(self.sim_dir, exist_ok=True)
        
        # v8 new: Create thinking storage directory
        self.thinking_dir = f"{self.config.output_dir}/thinking_processes"
        os.makedirs(self.thinking_dir, exist_ok=True)
        
        # v9 new: Set prompt file path
        self.prompts_dir = self.config.prompts_dir
        
        # Initialize system prompt
        self.init_system_prompt()
    
    def init_system_prompt(self):
        """Initialize system prompt (v9 version: read from file)"""
        system_prompt_file = os.path.join(self.prompts_dir, "system_prompt.md")
        system_prompt = load_prompt_from_file(system_prompt_file)
        
        if not system_prompt:
            raise PromptFileNotFoundError(system_prompt_file, step_name="system_prompt")
        
        self.messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # v8: Also maintain full history
        self.full_history.append({
            "role": "system",
            "content": system_prompt
        })
    
    def extract_thinking_content(self, full_response: str, raw_api_response: Dict = None) -> Tuple[str, str]:
        """
        v8 new: Separate thinking content and clean content
        
        Args:
            full_response: content field extracted from API response
            raw_api_response: Complete API response, used to extract reasoning_content
        
        Returns:
            (thinking_content, clean_content)
        """
        if not self.config.enable_thinking_separation:
            return "", full_response
        
        thinking_content = ""
        clean_content = full_response
        
        # Method 1: Extract thinking content from reasoning_content field in API response
        if raw_api_response and 'choices' in raw_api_response:
            choices = raw_api_response['choices']
            if len(choices) > 0 and 'message' in choices[0]:
                message = choices[0]['message']
                if 'reasoning_content' in message:
                    thinking_content = message['reasoning_content']
                    clean_content = message.get('content', full_response)
                    
                    self.module_logger.debug(f"[v8] Extracting thinking content from reasoning_content field")
                    self.module_logger.debug(f"[v8] Thinking content length: {len(thinking_content)} characters")
                    self.module_logger.debug(f"[v8] Clean content length: {len(clean_content)} characters")
                    self.module_logger.debug(f"[v8] Compression ratio: {len(clean_content)/(len(clean_content)+len(thinking_content))*100:.1f}%")
                    
                    return thinking_content, clean_content
        
        # Method 2: If reasoning_content is not in API response, try to find thinking tags in content
        thinking_pattern = r'<thinking>(.*?)</thinking>'
        thinking_match = re.search(thinking_pattern, full_response, re.DOTALL | re.IGNORECASE)
        
        if thinking_match:
            thinking_content = thinking_match.group(1).strip()
            # Remove thinking part, keep clean content
            clean_content = re.sub(thinking_pattern, '', full_response, flags=re.DOTALL | re.IGNORECASE)
            clean_content = clean_content.strip()
            
            self.module_logger.debug(f"[v8] Extracting thinking tag content from content")
            self.module_logger.debug(f"[v8] Thinking content length: {len(thinking_content)} characters")
            self.module_logger.debug(f"[v8] Clean content length: {len(clean_content)} characters")
            self.module_logger.debug(f"[v8] Compression ratio: {len(clean_content)/len(full_response)*100:.1f}%")
            
            return thinking_content, clean_content
        else:
            # Thinking content not found, treat all as clean content
            self.module_logger.debug(f"[v8] Thinking content not found, using full response")
            return "", full_response
    
    def save_thinking_content(self, step_name: str, thinking_content: str):
        """v8 new: Save thinking content to separate file"""
        if not thinking_content:
            return None
        
        filename = f"{self.thinking_dir}/iter{self.iteration_count + 1:02d}_step{self.step_count:02d}_global{self.global_step_count:02d}_{step_name}_thinking.md"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Thinking Process - Step {self.step_count}: {step_name}\n\n")
            f.write(f"**Generated Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Iteration Count**: {self.iteration_count + 1}\n\n")
            f.write("---\n\n")
            f.write("## Thinking Process\n\n")
            f.write(thinking_content)
            f.write("\n\n---\n\n")
        
        self.module_logger.debug(f"[v8] Thinking content saved to: {filename}")
        return filename
    
    def estimate_token_count(self) -> int:
        """v8 new: Estimate token count of current context"""
        total_chars = sum(len(str(msg['content'])) for msg in self.messages)
        # Rough estimate: average 1 token per 4 characters
        estimated_tokens = total_chars // 4
        return estimated_tokens
    
    def monitor_context_size(self) -> Dict:
        """v8 new: Monitor context size"""
        clean_chars = sum(len(str(msg['content'])) for msg in self.messages)
        full_chars = sum(len(str(msg['content'])) for msg in self.full_history)
        
        stats = {
            'message_count': len(self.messages),
            'clean_total_chars': clean_chars,
            'full_total_chars': full_chars,
            'estimated_clean_tokens': clean_chars // 4,
            'estimated_full_tokens': full_chars // 4,
            'compression_ratio': clean_chars / full_chars if full_chars > 0 else 1.0,
            'space_saved_percentage': (1 - clean_chars / full_chars) * 100 if full_chars > 0 else 0
        }
        
        self.module_logger.debug(f"[v8 Context Monitoring]")
        self.module_logger.debug(f"  Clean tokens: {stats['estimated_clean_tokens']:,}")
        self.module_logger.debug(f"  Full tokens: {stats['estimated_full_tokens']:,}")
        self.module_logger.debug(f"  Space saved: {stats['space_saved_percentage']:.1f}%")
        
        return stats
    
    def _should_retry(self, error: Exception, status_code: int = None, attempt: int = 0) -> bool:
        """
        Determine whether API call should be retried
        
        Args:
            error: Exception object
            status_code: HTTP status code (if any)
            attempt: Current retry count (starting from 0)
        
        Returns:
            True means should retry, False means should not retry
        """
        # If retry mechanism is disabled, do not retry
        if not self.config.api_retry_enabled:
            return False
        
        # If max retry count reached, do not retry
        if attempt >= self.config.api_max_retries:
            return False
        
        # Permanent errors (4xx, except 429, 408, 504): do not retry
        if status_code and 400 <= status_code < 500:
            # 429 (Too Many Requests) and 408 (Request Timeout) should retry
            if status_code in [429, 408]:
                return True
            # 504 (Gateway Timeout) should retry
            if status_code == 504:
                return True
            # Other 4xx errors are usually permanent, do not retry
            return False
        
        # Temporary errors (5xx): should retry
        if status_code and 500 <= status_code < 600:
            return True
        
        # Timeout errors: should retry
        if isinstance(error, requests.exceptions.Timeout):
            return True
        
        # Connection errors, proxy errors, etc.: should retry
        if isinstance(error, requests.exceptions.RequestException):
            # Exclude some exception types that should not retry
            if isinstance(error, requests.exceptions.HTTPError):
                # HTTPError has already been handled above via status_code
                return False
            return True
        
        # Other exceptions: default to no retry (conservative strategy)
        return False
    
    def _get_backoff_time(self, attempt: int) -> float:
        """
        Calculate exponential backoff time
        
        Args:
            attempt: Current retry count (starting from 0)
        
        Returns:
            Backoff time (seconds)
        """
        base_delay = self.config.api_retry_backoff_base
        max_delay = self.config.api_retry_backoff_max
        # Exponential backoff: base * 2^attempt
        delay = min(base_delay * (2 ** attempt), max_delay)
        return delay
    
    def _log_retry_attempt(self, attempt: int, error: Exception, backoff_time: float, status_code: int = None):
        """
        Log detailed information about retry attempt
        
        Args:
            attempt: Current retry count (starting from 0)
            error: Exception object
            backoff_time: Backoff time (seconds)
            status_code: HTTP status code (if any)
        """
        error_type = type(error).__name__
        error_msg = str(error)
        status_info = f", HTTP {status_code}" if status_code else ""
        
        self.module_logger.warning(
            f"🔄 API call failed, preparing to retry (attempt {attempt + 1}/{self.config.api_max_retries + 1}) "
            f"[Error: {error_type}{status_info}, Message: {error_msg[:100]}]"
        )
        self.module_logger.info(f"⏳ Waiting {backoff_time:.1f}s before retry...")
    
    def call_api(self, messages: List[Dict]) -> Optional[Tuple[str, str]]:
        """
        v10 improvement: Call API and return separated content, supports automatic retry
        
        Returns:
            (clean_content, full_content) or None (returns None on failure, error information via exception or logging)
        """
        url = f"{self.config.base_url}/chat/completions"
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": 32768,
        }
        
        # Retry statistics
        retry_stats = {
            'total_attempts': 0,
            'retry_count': 0,
            'total_duration': 0.0,
            'errors': []
        }
        
        # Retry loop
        for attempt in range(self.config.api_max_retries + 1):
            retry_stats['total_attempts'] = attempt + 1
            
            try:
                # Record request start time
                request_start = time.perf_counter()
                if attempt == 0:
                    self.module_logger.debug(f"🚀 Sending API request (call #{self.global_step_count})")
                else:
                    self.module_logger.debug(f"🔄 Retrying API request (retry #{attempt + 1})")
                
                # Send request
                # v10 improvement: Use tuple form timeout, separate connection timeout and read timeout
                # Connection timeout 30 seconds (quick detection of connection issues), read timeout 600 seconds (give enough time to process response)
                connect_timeout = 30  # Connection timeout 30 seconds
                read_timeout = self.config.api_timeout  # Read timeout 600 seconds
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=payload,
                    timeout=(connect_timeout, read_timeout)
                )
            
                # Record API call time
                request_duration = time.perf_counter() - request_start
                retry_stats['total_duration'] += request_duration
                
                # Handle HTTP status code
                if response.status_code == 200:
                    result = response.json()
                    
                    # Extract token usage information
                    prompt_tokens = 0
                    completion_tokens = 0
                    total_tokens = 0
                    
                    if 'usage' in result:
                        usage = result['usage']
                        prompt_tokens = usage.get('prompt_tokens', 0)
                        completion_tokens = usage.get('completion_tokens', 0)
                        total_tokens = usage.get('total_tokens', 0)
                        
                        # Update total token statistics
                        self.config.total_prompt_tokens += prompt_tokens
                        self.config.total_completion_tokens += completion_tokens
                        self.config.total_tokens += total_tokens
                    
                    try:
                        if 'choices' not in result:
                            error_msg = "API response missing 'choices' field"
                            self.module_logger.error(f"❌ {error_msg}")
                            self.module_logger.error(f"Full response: {json.dumps(result, indent=2, ensure_ascii=False)}")
                            # Save error information to instance variable for execute_step to use
                            self._last_api_error = {
                                'error_type': 'missing_field',
                                'error_message': error_msg,
                                'error_details': f"Full response: {json.dumps(result, indent=2, ensure_ascii=False)}"
                            }
                            return None
                        
                        if not result['choices'] or len(result['choices']) == 0:
                            error_msg = "API response 'choices' array is empty"
                            self.module_logger.error(f"❌ {error_msg}")
                            self.module_logger.error(f"Full response: {json.dumps(result, indent=2, ensure_ascii=False)}")
                            self._last_api_error = {
                                'error_type': 'empty_choices',
                                'error_message': error_msg,
                                'error_details': f"Full response: {json.dumps(result, indent=2, ensure_ascii=False)}"
                            }
                            return None
                        
                        choice = result['choices'][0]
                        if 'message' not in choice:
                            error_msg = "API response missing 'message' field"
                            self.module_logger.error(f"❌ {error_msg}")
                            self.module_logger.error(f"Choice content: {json.dumps(choice, indent=2, ensure_ascii=False)}")
                            self._last_api_error = {
                                'error_type': 'missing_message',
                                'error_message': error_msg,
                                'error_details': f"Choice content: {json.dumps(choice, indent=2, ensure_ascii=False)}"
                            }
                            return None
                        
                        message = choice['message']
                        if 'content' not in message:
                            error_msg = "API response missing 'content' field"
                            self.module_logger.error(f"❌ {error_msg}")
                            self.module_logger.error(f"Message content: {json.dumps(message, indent=2, ensure_ascii=False)}")
                            self._last_api_error = {
                                'error_type': 'missing_content',
                                'error_message': error_msg,
                                'error_details': f"Message content: {json.dumps(message, indent=2, ensure_ascii=False)}"
                            }
                            return None
                        
                        full_content = message['content']
                        
                        if full_content is None or not isinstance(full_content, str):
                            error_msg = "API response content is invalid"
                            self.module_logger.error(f"❌ {error_msg}")
                            self.module_logger.error(f"Content type: {type(full_content)}, value: {full_content}")
                            self._last_api_error = {
                                'error_type': 'invalid_content',
                                'error_message': error_msg,
                                'error_details': f"Content type: {type(full_content)}, value: {full_content}"
                            }
                            return None
                        
                        if len(full_content.strip()) == 0:
                            error_msg = "API response is empty"
                            self.module_logger.error(f"❌ {error_msg}")
                            self._last_api_error = {
                                'error_type': 'empty_content',
                                'error_message': error_msg,
                                'error_details': "Response content is empty string"
                            }
                            return None
                        
                        # Display API call results and token information
                        if attempt > 0:
                            self.module_logger.info(f"✅ API call successful (after {attempt} retries), elapsed: {request_duration:.3f}s")
                        else:
                            self.module_logger.info(f"✅ API call completed, elapsed: {request_duration:.3f}s")
                        self.module_logger.debug(f"📊 Token usage: Prompt={prompt_tokens}, Completion={completion_tokens}, Total={total_tokens}")
                        self.module_logger.debug(f"📈 Cumulative tokens: Prompt={self.config.total_prompt_tokens}, Completion={self.config.total_completion_tokens}, Total={self.config.total_tokens}")
                        
                        # v8: Separate thinking and clean content, pass complete API response
                        thinking_content, clean_content = self.extract_thinking_content(full_content, result)
                        
                        # Cache thinking content
                        if thinking_content:
                            cache_key = f"step_{self.global_step_count}"
                            self.thinking_cache[cache_key] = thinking_content
                        
                        # Build full content including thinking
                        if thinking_content:
                            full_content_with_thinking = f"<thinking>\n{thinking_content}\n</thinking>\n\n{clean_content}"
                        else:
                            full_content_with_thinking = full_content
                        
                        # Clear previous error information
                        self._last_api_error = None
                        return clean_content, full_content_with_thinking
                        
                    except Exception as e:
                        import traceback
                        error_msg = f"Exception occurred while parsing API response: {str(e)}"
                        error_traceback = traceback.format_exc()
                        self.module_logger.error(f"❌ {error_msg}", exc_info=True)
                        self._last_api_error = {
                            'error_type': 'parse_exception',
                            'error_message': error_msg,
                            'error_details': error_traceback
                        }
                        return None
                else:
                    # HTTP status code is not 200
                    status_code = response.status_code
                    error_msg = f"API call failed: HTTP {status_code}"
                    try:
                        error_text = response.text
                    except:
                        error_text = "Unable to read response content"
                    
                    # Determine whether should retry
                    http_error = requests.exceptions.HTTPError(f"{status_code}: {error_text}")
                    if self._should_retry(http_error, status_code=status_code, attempt=attempt):
                        # Should retry
                        retry_stats['retry_count'] += 1
                        retry_stats['errors'].append({
                            'attempt': attempt + 1,
                            'error_type': 'http_error',
                            'status_code': status_code,
                            'error_message': error_msg
                        })
                        backoff_time = self._get_backoff_time(attempt)
                        self._log_retry_attempt(attempt, http_error, backoff_time, status_code)
                        time.sleep(backoff_time)
                        continue
                    else:
                        # Should not retry (permanent error)
                        self.module_logger.error(f"❌ {error_msg}")
                        self.module_logger.error(f"Error response: {error_text}")
                        self.module_logger.error(f"Request URL: {url}")
                        self._last_api_error = {
                            'error_type': 'http_error',
                            'error_message': error_msg,
                            'error_details': f"""HTTP status code: {status_code}
Error response content: {error_text}
Request URL: {url}"""
                        }
                        return None
            
            except requests.exceptions.Timeout as e:
                # Timeout error
                if self._should_retry(e, attempt=attempt):
                    # Should retry
                    retry_stats['retry_count'] += 1
                    retry_stats['errors'].append({
                        'attempt': attempt + 1,
                        'error_type': 'timeout',
                        'error_message': str(e)
                    })
                    backoff_time = self._get_backoff_time(attempt)
                    self._log_retry_attempt(attempt, e, backoff_time)
                    time.sleep(backoff_time)
                    continue
                else:
                    # Max retry count reached
                    timeout_error = APITimeoutError(self.config.api_timeout)
                    error_msg = f"API call timeout (after {attempt} retries): {timeout_error}"
                    self.logger.error(f"API call timeout: {timeout_error}")
                    self.module_logger.error(f"❌ {error_msg}")
                    self.module_logger.error(f"Request URL: {url}")
                    self.module_logger.error(f"Connection timeout: 30s, Read timeout: {self.config.api_timeout}s")
                    self._last_api_error = {
                        'error_type': 'timeout',
                        'error_message': error_msg,
                        'error_details': f"""Request timeout (after {attempt} retries)
Request URL: {url}
Connection timeout: 30 seconds
Read timeout: {self.config.api_timeout} seconds
Error type: {type(timeout_error).__name__}"""
                    }
                    return None
            except requests.exceptions.RequestException as e:
                # Network request exception (connection error, proxy error, etc.)
                if self._should_retry(e, attempt=attempt):
                    # Should retry
                    retry_stats['retry_count'] += 1
                    retry_stats['errors'].append({
                        'attempt': attempt + 1,
                        'error_type': 'request_exception',
                        'error_message': str(e)
                    })
                    backoff_time = self._get_backoff_time(attempt)
                    self._log_retry_attempt(attempt, e, backoff_time)
                    time.sleep(backoff_time)
                    continue
                else:
                    # Max retry count reached
                    import traceback
                    error_msg = f"API request exception (after {attempt} retries): {str(e)}"
                    error_traceback = traceback.format_exc()
                    api_error = APICallError(str(e))
                    self.logger.error(f"API call failed: {api_error}")
                    self.module_logger.error(f"❌ {error_msg}", exc_info=True)
                    self.module_logger.error(f"Request URL: {url}")
                    self._last_api_error = {
                        'error_type': 'request_exception',
                        'error_message': error_msg,
                        'error_details': f"""Request exception details (after {attempt} retries):
Error type: {type(e).__name__}
Error message: {str(e)}
Full stack trace:
{error_traceback}
Request URL: {url}"""
                    }
                    return None
            except Exception as e:
                # Other unexpected exceptions (usually should not retry)
                import traceback
                error_msg = f"Unexpected exception: {str(e)}"
                error_traceback = traceback.format_exc()
                api_error = APICallError(str(e))
                self.logger.error(f"API call failed: {api_error}")
                self.module_logger.error(f"❌ {error_msg}", exc_info=True)
                self._last_api_error = {
                    'error_type': 'unexpected_exception',
                    'error_message': error_msg,
                    'error_details': f"""Unexpected exception:
Error type: {type(e).__name__}
Error message: {str(e)}
Full stack trace:
{error_traceback}"""
                }
                return None
        
        # If all retries failed, log statistics
        if retry_stats['retry_count'] > 0:
            self.module_logger.error(
                f"❌ API call finally failed (after {retry_stats['total_attempts']} attempts, "
                f"{retry_stats['retry_count']} retries, total elapsed: {retry_stats['total_duration']:.3f}s)"
            )
        
        return None
    
    def save_response(self, step_name: str, response: str, user_prompt: str, is_full: bool = True):
        """
        v8 improvement: Save response to file
        
        Args:
            is_full: True means save full response (including thinking), False means save clean response
        """
        suffix = "_full" if is_full else "_clean"
        filename = f"{self.config.output_dir}/iter{self.iteration_count + 1:02d}_step{self.step_count:02d}_global{self.global_step_count:02d}_{step_name}{suffix}.md"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Step {self.step_count}: {step_name}\n\n")
            f.write(f"**Generated Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Iteration Count**: {self.iteration_count + 1}\n\n")
            f.write(f"**Content Type**: {'Full Response (including thinking)' if is_full else 'Clean Response'}\n\n")
            f.write("---\n\n")
            
            f.write("## User Prompt\n\n")
            f.write("```text\n")
            f.write(user_prompt)
            f.write("\n```\n\n")
            
            f.write("## Model Response\n\n")
            f.write(response)
            f.write("\n\n")
            
            f.write("---\n\n")
            f.write(f"*File path: {filename}*\n")
        
        self.module_logger.debug(f"Response saved to: {filename}")
        return filename
    
    def extract_tagged_content(self, response: str, tag: str) -> Optional[str]:
        """Improved tagged content extraction (safe and fault-tolerant version)"""
        if not response or not tag:
            return None
        
        # First try to match complete closed tags (highest priority)
        closed_patterns = [
            f'<{tag}>(.*?)</{tag}>',
            f'<{tag}\\s*>(.*?)</{tag}>',
            f'<{tag}[^>]*>(.*?)</{tag}>',
        ]
        
        # Find all matching closed tags, select the last one (usually the newest)
        all_matches = []
        for pattern in closed_patterns:
            matches = re.findall(pattern, response, re.DOTALL | re.IGNORECASE)
            for match in matches:
                content = match.strip()
                if self._is_valid_content(content, tag):
                    all_matches.append(content)
        
        if all_matches:
            # Select the last matching content (usually the newest)
            content = all_matches[-1]
            self.module_logger.debug(f"✅ Found {len(all_matches)} closed <{tag}> tags, using the last one")
            return self._clean_content(content)
        
        # Only try unclosed tags if no closed tags found
        self.module_logger.debug(f"⚠️ No closed <{tag}> tags found, trying to match unclosed tags...")
        
        # Stricter unclosed tag matching
        unclosed_patterns = [
            f'<{tag}>(.*?)(?=\\n\\n|$)',  # Match to double newline or end of file
            f'<{tag}\\s*>(.*?)(?=\\n\\n|$)',
            f'<{tag}>(.*?)$',  # Match to end of file
            f'<{tag}\\s*>(.*?)$',
        ]
        
        for pattern in unclosed_patterns:
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                if self._is_valid_content(content, tag):
                    self.module_logger.debug(f"✅ Successfully matched unclosed <{tag}> tag")
                    return self._clean_content(content)
        
        self.module_logger.debug(f"Hint: No <{tag}> tag found")
        return None
    
    def _is_valid_content(self, content: str, tag: str) -> bool:
        """Validate if content is valid"""
        if not content or len(content.strip()) < 10:  # Content too short, may be invalid
            return False
        
        # Check if contains other main tags (may indicate matching error)
        if any(other_tag in content for other_tag in ['<engineering_decision>', '<comparison_analysis>']):
            return False
        
        # Check if starts or ends with separator line (may indicate matching error)
        if content.strip().startswith('---') or content.strip().endswith('---'):
            return False
        
        return True
    
    def _clean_content(self, content: str) -> str:
        """Clean content"""
        # Remove file path and timestamp
        content = re.sub(r'\*File path:.*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^---\s*$', '', content, flags=re.MULTILINE)
        
        # Remove excessive blank lines
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        
        return content.strip()
    
    def _validate_xml_structure(self, response: str):
        """Validate XML structure"""
        # Check for unclosed tags
        start_tags = re.findall(r'<(\w+)(?:\s[^>]*)?>', response)
        end_tags = re.findall(r'</(\w+)>', response)
        
        unclosed_tags = []
        for tag in start_tags:
            if tag not in end_tags:
                unclosed_tags.append(tag)
        
        if unclosed_tags:
            self.module_logger.warning(f"⚠️ Warning: Detected unclosed tags: {unclosed_tags}")
            self.module_logger.debug(f"📝 Suggestion: Please ensure all XML tags are properly closed")
    
    def _validate_parsed_content(self, comparison_analysis, engineering_decision, retry_details):
        """Validate parsed content"""
        if not comparison_analysis:
            self.module_logger.warning("⚠️ Warning: comparison_analysis content not found")
        
        if not engineering_decision:
            self.module_logger.warning("⚠️ Warning: engineering_decision content not found")
        
        if not retry_details:
            self.module_logger.debug("ℹ️ Info: retry_details content not found (decision may be ACCEPT)")
    
    def parse_decision(self, decision_content: str) -> str:
        """Parse decision result, prioritize <decision> tag (v8 improved version)"""
        if not decision_content:
            self.module_logger.debug(f"[Debug] Decision content is empty, using default RETRY (conservative strategy)")
            return "RETRY"
        
        # Prioritize using <decision> tag for parsing
        decision_tag_match = re.search(r'<decision>\s*([A-Z]+)\s*</decision>', decision_content, re.IGNORECASE)
        if decision_tag_match:
            decision = decision_tag_match.group(1).strip().upper()
            self.module_logger.debug(f"[Debug] Successfully parsed decision using <decision> tag: '{decision}'")
            return decision
        
        # If <decision> tag doesn't exist, use other formats as fallback
        decision_patterns = [
            r'\*\*Decision\*\*:\s*\*\*([A-Z]+)\*\*',  # **Decision**: **RETRY**
            r'\*\*Decision\*\*:\s*\[([A-Z]+)\]',      # **Decision**: [RETRY]
            r'\*\*Decision\*\*:\s*([A-Z]+)',         # **Decision**: RETRY
            r'Decision[：:]\s*\*\*([A-Z]+)\*\*',      # Decision: **RETRY**
            r'Decision[：:]\s*\[([A-Z]+)\]',          # Decision: [RETRY]
            r'Decision[：:]\s*([A-Z]+)',             # Decision: RETRY
            r'Decision Result[：:]\s*([A-Z]+)',      # Decision Result: RETRY
        ]
        
        for i, pattern in enumerate(decision_patterns):
            match = re.search(pattern, decision_content, re.IGNORECASE)
            if match:
                decision = match.group(1).strip().upper()
                self.module_logger.debug(f"[Debug] Successfully parsed decision using fallback pattern {i+1}: '{decision}'")
                return decision
        
        # If all patterns fail, try more lenient keyword search
        decision_content_upper = decision_content.upper()
        if "RETRY" in decision_content_upper and "ACCEPT" not in decision_content_upper:
            self.module_logger.debug(f"[Debug] Found RETRY through keyword search")
            return "RETRY"
        elif "ACCEPT" in decision_content_upper and "RETRY" not in decision_content_upper:
            self.module_logger.debug(f"[Debug] Found ACCEPT through keyword search")
            return "ACCEPT"
        elif "RETRY" in decision_content_upper and "ACCEPT" in decision_content_upper:
            # If both keywords are present, choose the one that appears first
            retry_pos = decision_content_upper.find("RETRY")
            accept_pos = decision_content_upper.find("ACCEPT")
            if retry_pos < accept_pos:
                self.module_logger.debug(f"[Debug] Found both RETRY and ACCEPT, choosing RETRY (appears first)")
                return "RETRY"
            else:
                self.module_logger.debug(f"[Debug] Found both RETRY and ACCEPT, choosing ACCEPT (appears first)")
                return "ACCEPT"
        
        # Final default should be RETRY, because ACCEPT requires explicit confirmation
        self.module_logger.debug(f"[Debug] Unable to parse decision, using default RETRY (conservative strategy)")
        self.module_logger.debug(f"[Debug] Decision content: '{decision_content[:200]}...'")
        return "RETRY"
    
    def extract_python_code(self, response: str) -> List[str]:
        """Extract Python code blocks from response"""
        pattern = r'```python\n(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        return matches
    
    def analyze_optimization_execution(self, execution_log: str) -> Dict:
        """Intelligently analyze optimization code execution results (simplified version)"""
        prompt = f"""Please analyze the following optimization code execution log and determine if optimization was successful.

Execution log:
{execution_log}

## Analysis Instructions

The optimization code outputs constraint verification with three possible statuses:
- **PASS**: Constraint is fully satisfied
- **BOUNDARY**: Constraint is within acceptable tolerance (1% relative error), acceptable
- **FAIL**: Constraint is violated beyond acceptable tolerance, not acceptable

## Judgment Criteria

1. **Code execution status**: Check if code executed without runtime errors (stderr should be empty or only contain warnings)

2. **Solver status**: Check multi-start success rate (>50% usually indicates solver is working correctly)

3. **Performance constraints** (MUST ALL PASS or BOUNDARY):
   - All performance constraints (Gain, GBW, PM, Power) must be PASS or BOUNDARY
   - Any FAIL status means the constraint is not satisfied

4. **Additional constraints** (Model Validity and Stability):
   - PASS or BOUNDARY: Acceptable
   - FAIL: Not acceptable (indicates severe violation)

5. **Overall judgment**:
   - SUCCESS if: (1) Code executed successfully, AND (2) All performance constraints are PASS or BOUNDARY, AND (3) No FAIL status in any constraint
   - FAIL if: (1) Code execution failed, OR (2) Any performance constraint has FAIL status, OR (3) Any constraint has FAIL status

## Important Notes

- BOUNDARY status is acceptable and should be treated as PASS
- Only FAIL status indicates a problem that should cause rejection
- Pay attention to the actual status strings (PASS, BOUNDARY, FAIL) in the constraint verification section

Please output in the following format:
<opt_flag>True/False</opt_flag>
<opt_details>
Specific analysis content, including:
1. Code execution status
2. Solver status (multi-start success rate)
3. Performance constraints check (list each constraint and its status)
4. Additional constraints check (list each constraint and its status)
5. Overall judgment and reasoning
</opt_details>"""

        try:
            # Call API for analysis
            analysis_messages = [
                {"role": "user", "content": prompt}
            ]
            
            api_result = self.call_api(analysis_messages)
            if api_result:
                clean_response, full_response = api_result
                
                # Extract opt_flag
                opt_flag_match = re.search(r'<opt_flag>(True|False)</opt_flag>', clean_response, re.IGNORECASE)
                opt_flag = opt_flag_match.group(1).lower() == 'true' if opt_flag_match else False
                
                # Extract opt_details
                opt_details_match = re.search(r'<opt_details>(.*?)</opt_details>', clean_response, re.DOTALL)
                opt_details = opt_details_match.group(1).strip() if opt_details_match else "Unable to extract analysis details"
                
                self.module_logger.info(f"[Intelligent Analysis] Optimization result: {'Success' if opt_flag else 'Failed'}")
                self.module_logger.debug(f"[Intelligent Analysis] Analysis details: {opt_details[:100]}...")
                
                return {
                    'success': opt_flag,
                    'details': opt_details,
                    'raw_response': clean_response
                }
            else:
                self.module_logger.warning("[Intelligent Analysis] API call failed, defaulting to failed")
                return {
                    'success': False,
                    'details': "API call failed, unable to analyze execution results",
                    'raw_response': ""
                }
                
        except Exception as e:
            self.module_logger.error(f"[Intelligent Analysis] Analysis process error: {e}", exc_info=True)
            return {
                'success': False,
                'details': f"Analysis process error: {str(e)}",
                'raw_response': ""
            }
    
    
    def extract_optimization_failure_info(self, step_result: Dict) -> str:
        """Extract optimization failure information"""
        failure_info = []
        
        # Extract failure information from step response
        response = step_result.get('response', '')
        
        # Check if it's an API call failure
        if 'error' in step_result:
            failure_info.append(f"API call failed: {step_result['error']}")
            return "\n\n".join(failure_info) if failure_info else "API call failed, unable to get specific failure information"
        
        # Extract error information
        if "ERROR: Optimization failed" in response:
            failure_info.append("Optimizer report: Optimization failed")
        
        if "Solution Not Found" in response:
            failure_info.append("Solver status: No feasible solution found")
        
        if "Unsuccessful with error code" in response:
            failure_info.append("Solver returned: Unsuccessful status")
        
        if "infeasibilities.txt" in response:
            failure_info.append("Solver generated infeasibility analysis file")
        
        # Extract detailed information from step execution results
        if 'execution_results' in step_result:
            for i, exec_result in enumerate(step_result['execution_results']):
                failure_info.append(f"Code execution result {i+1}:\n{exec_result}")
        
        # Extract information from step analysis file
        analysis_file = step_result.get('analysis_file')
        if analysis_file and os.path.exists(analysis_file):
            try:
                with open(analysis_file, 'r', encoding='utf-8') as f:
                    analysis_content = f.read()
                    failure_info.append(f"Optimization analysis report:\n{analysis_content}")
            except Exception as e:
                self.module_logger.debug(f"[Debug] Failed to read analysis file: {e}")
        
        return "\n\n".join(failure_info) if failure_info else "Optimization failed, but no specific failure information found"
    
    def execute_python_code(self, code: str, step_name: str) -> Optional[str]:
        """Execute Python code"""
        if not self.config.enable_python_execution:
            self.module_logger.debug("Python code execution is disabled")
            return None
        
        # Always use local execution
        code_file = f"{self.code_dir}/iter{self.iteration_count + 1:02d}_step{self.step_count:02d}_global{self.global_step_count:02d}_{step_name}.py"
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        self.module_logger.debug(f"Python code saved to: {code_file}")
        
        try:
            result = subprocess.run(
                [sys.executable, code_file],
                capture_output=True,
                text=True,
                timeout=900
            )
            
            output = f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
            
            output_file = f"{self.code_dir}/iter{self.iteration_count + 1:02d}_step{self.step_count:02d}_global{self.global_step_count:02d}_{step_name}_output.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(output)
            
            return output
            
        except subprocess.TimeoutExpired:
            timeout_error = CodeExecutionTimeoutError(900)
            self.logger.error(f"Code execution timeout: {timeout_error}")
            self.module_logger.error(f"❌ {timeout_error}")
            return "Code execution timeout (900 seconds)"
        except Exception as e:
            exec_error = CodeExecutionError(str(e))
            self.logger.error(f"Code execution failed: {exec_error}")
            self.module_logger.error(f"❌ {exec_error}")
            return f"Code execution error: {str(e)}"
    
    def execute_step(self, step_name: str, user_prompt: str, expected_tag: str = None) -> Dict:
        """
        v8 improvement: Execute single step, using dual-track storage
        """
        # Map step name to step number (1-9) - using English names from system_prompt.md
        STEP_NAME_TO_NUMBER = {
            'circuit_topology_interpretation': 1,
            'circuit_equation_formulation': 2,
            'unbiased_transfer_function_derivation': 3,
            'design_variable_substitution_and_simplification': 4,
            'pole_and_zero_extraction': 5,
            'pole_and_zero_positioning_and_metric_derivation': 6,
            'white_box_optimization_programming': 7,
            'simulation_verification': 8,
            'design_result_analysis_and_decision_making': 9,
        }
        
        # Get step number from step name
        step_number = STEP_NAME_TO_NUMBER.get(step_name, None)
        
        self.global_step_count += 1
        self.step_count += 1
        self.module_logger.info(f"[Step {self.step_count}] {step_name}")
        self.module_logger.info(f"[Global Step {self.global_step_count}] [Iteration {self.iteration_count + 1}]")
        
        # Log step start
        self.module_logger.info(f"📝 Starting step execution: {step_name} (Global Step {self.global_step_count})")
        
        # If there are lessons learned, inject into prompt
        if self.lessons_learned and self.iteration_count > 0:
            user_prompt = f"""{user_prompt}

## ⚠️ Important Reminder (Based on Lessons Learned from Previous Attempts):
{self.lessons_learned}

Please pay special attention to avoiding the problems that occurred before, and improve your analysis method based on these experiences."""
        
        # Add user message to history (clean version)
        self.messages.append({
            "role": "user",
            "content": user_prompt
        })
        
        # Also maintain full history
        self.full_history.append({
            "role": "user",
            "content": user_prompt
        })
        
        # v8: Monitor context size
        context_stats = self.monitor_context_size()
        
        # Check if compression is needed (optional, auto-compression not implemented yet)
        if context_stats['estimated_clean_tokens'] > self.config.max_context_tokens:
            self.module_logger.warning(f"⚠️ Warning: Context approaching limit ({context_stats['estimated_clean_tokens']} / {self.config.max_context_tokens} tokens)")
        
        # Call API
        self.module_logger.debug("Calling API...")
        api_result = self.call_api(self.messages)
        
        if api_result:
            clean_response, full_response = api_result
            
            # Save full response and clean response
            full_file = self.save_response(step_name, full_response, user_prompt, is_full=True)
            clean_file = self.save_response(step_name, clean_response, user_prompt, is_full=False)
            
            # Save thinking content separately
            thinking_content = self.thinking_cache.get(f"step_{self.global_step_count}", "")
            if thinking_content:
                self.save_thinking_content(step_name, thinking_content)
            
            # Add clean response to message history
            self.messages.append({
                "role": "assistant",
                "content": clean_response
            })
            
            # Add full response to full history
            self.full_history.append({
                "role": "assistant",
                "content": full_response
            })
            
            # Extract tagged content (from clean response)
            extracted_content = None
            if expected_tag:
                extracted_content = self.extract_tagged_content(clean_response, expected_tag)
            
            # Process Python code
            python_codes = []
            execution_results = []
            step_success = True  # Default success, only optimization step will be re-evaluated
            
            # Use step_number for robust step identification (step 7: White Box Optimization)
            if step_number == 7:
                python_codes = self.extract_python_code(clean_response)
                if python_codes:
                    self.module_logger.debug(f"Found {len(python_codes)} Python code segments")
                    for i, code in enumerate(python_codes):
                        self.module_logger.debug(f"Executing code segment {i+1}...")
                        execution_result = self.execute_python_code(code, f"{step_name}_code{i+1}")
                        if execution_result:
                            self.module_logger.debug(f"Execution result:\n{execution_result[:200]}...")
                            execution_results.append(execution_result)
                            
                            if execution_result:
                                # Intelligently analyze optimization execution results
                                self.module_logger.debug("Intelligently analyzing optimization execution results...")
                                analysis_result = self.analyze_optimization_execution(execution_result)
                                
                                # Update step success status
                                step_success = analysis_result['success']
                                
                                # Generate analysis report
                                analysis_content = f"""# Optimization Execution Result Analysis

## Intelligent Analysis Results
- **Execution Status**: {'Success' if analysis_result['success'] else 'Failed'}
- **Analysis Details**: {analysis_result['details']}

## Original Execution Log
```
{execution_result}
```

## Intelligent Analysis Raw Response
```
{analysis_result['raw_response']}
```"""
                                
                                analysis_file = f"{self.config.output_dir}/iter{self.iteration_count + 1:02d}_step{self.step_count:02d}_global{self.global_step_count:02d}_{step_name}_analysis.md"
                                with open(analysis_file, 'w', encoding='utf-8') as f:
                                    f.write(analysis_content)
                                self.module_logger.debug(f"Optimization analysis saved to: {analysis_file}")
                                
                                # Update step status based on analysis results
                                if not step_success:
                                    self.module_logger.warning(f"⚠️ Optimization execution failed, step marked as failed")
                                else:
                                    self.module_logger.info(f"✅ Optimization execution successful")
                                    
                                    # Note: Pole-zero extraction has been removed, now step 9's LLM directly extracts from files
                            else:
                                # Non-white-box optimization steps, maintain success status
                                step_success = True
                        else:
                            # Code execution failed
                            self.module_logger.warning(f"⚠️ Code execution failed, step marked as failed")
                            step_success = False
                else:
                    # No Python code found
                    self.module_logger.warning(f"⚠️ No Python code found, step marked as failed")
                    step_success = False
            
            # Note: Pole-zero extraction has been removed, now step 9's LLM directly extracts from files
            poles_zeros_from_all = None
            
            self.module_logger.info(f"✓ {step_name} completed")
            
            result_dict = {
                'success': step_success,
                'step': step_name,
                'step_number': step_number,  # Add step number (1-9) for robust step identification
                'response': clean_response,  # v8: Return clean version
                'full_response': full_response,  # v8 new: Full response
                'extracted': extracted_content,
                'saved_file': clean_file,  # Main file is clean version
                'full_file': full_file,  # v8 new: Full file path
                'python_codes': python_codes,
                'execution_results': execution_results
            }
            
            # New: If poles/zeros extracted, add to results
            if poles_zeros_from_all:
                result_dict['poles_zeros'] = poles_zeros_from_all
            
            return result_dict
        else:
            self.module_logger.error(f"✗ {step_name} failed")
            
            # Build detailed error information
            if self._last_api_error:
                # Use saved detailed error information
                error_type = self._last_api_error.get('error_type', 'unknown')
                error_message = self._last_api_error.get('error_message', 'API call failed')
                error_details = self._last_api_error.get('error_details', 'No detailed information')
                
                error_response = f"""## API Call Failed

### Error Type
{error_type}

### Error Message
{error_message}

### Detailed Error Information
```
{error_details}
```

### Note
The above is the underlying error information from the API call, which can be used for problem diagnosis and debugging."""
            else:
                # If no saved error information, use default message
                error_response = """## API Call Failed

### Error Message
API call failed, unable to get model response.

### Note
No detailed error information obtained, please check log files for more information."""
            
            # Save detailed error information to clean file
            error_file = self.save_response(step_name, error_response, user_prompt, is_full=False)
            
            # Clear error information cache
            self._last_api_error = None
            
            # Return error result with step_number
            return {
                'success': False,
                'step': step_name,
                'step_number': step_number,  # Add step number even for errors
                'response': error_response,
                'saved_file': error_file
            }
            
            return {
                'success': False,
                'step': step_name,
                'step_number': step_number,  # Add step number even for errors
                'error': 'API call failed',
                'response': error_response,
                'saved_file': error_file
            }
    
    # ========== Note: Wrapper methods for steps 1-9 have been removed, now directly call through p2m.steps module ==========
    # Implementation of steps 1-9 has been migrated to p2m/steps module, pipeline.py directly calls functions from steps module
    
    # ========== The following helper methods are used elsewhere in pipeline and need to be retained ==========
    # Note: Complete implementation of steps 8 and 9 has been migrated to p2m/steps module
    # These helper methods are used elsewhere in pipeline, so they need to be retained
    
    
    def _get_execution_log_string(self, execution_result) -> str:
        """Extract string content from execution_result (can be string or dict)
        
        Args:
            execution_result: Can be a string or dict (containing 'stdout' field)
        
        Returns:
            String content
        """
        if isinstance(execution_result, dict):
            # If it's a dict, extract stdout field
            return execution_result.get('stdout', '')
        elif isinstance(execution_result, str):
            # If it's a string, try to extract stdout part
            if 'stdout:' in execution_result:
                parts = execution_result.split('stderr:', 1)
                return parts[0].replace('stdout:', '').strip()
            else:
                return execution_result
        else:
            return str(execution_result) if execution_result else ''
    
    def _extract_design_vars(self, execution_result: Dict) -> Dict:
        """Extract design variables from optimization results
        
        Args:
            execution_result: Optimization execution result, can be a dict (containing 'stdout' field) or string
        
        Returns:
            Design variable dictionary, format: {'G1': value, 'G2': value, ...}
        """
        design_vars = {}
        
        try:
            # Convert to string uniformly
            stdout = self._get_execution_log_string(execution_result)
            if not stdout:
                return design_vars
            
            # Match patterns: G1:     1.00e-05 S (0.010 mS)
            # Or: G1:     {value:.2e} S
            patterns = {
                r'G1:\s*([\d.e+-]+)\s*S': 'G1',
                r'G2:\s*([\d.e+-]+)\s*S': 'G2',
                r'G3:\s*([\d.e+-]+)\s*S': 'G3',
                r'Gf:\s*([\d.e+-]+)\s*S': 'Gf',
                r'A1:\s*([\d.]+)': 'A1',
                r'A2:\s*([\d.]+)': 'A2',
                r'A3:\s*([\d.]+)': 'A3',
                r'Af:\s*([\d.]+)': 'Af',
                r'Cm:\s*([\d.e+-]+)\s*pF': 'Cm',
                r'Cm1:\s*([\d.e+-]+)\s*pF': 'Cm1',
                r'Cm2:\s*([\d.e+-]+)\s*pF': 'Cm2',
                r'Cf:\s*([\d.e+-]+)\s*pF': 'Cf',
                r'Rm:\s*([\d.e+-]+)\s*kΩ': 'Rm',
                r'Rm:\s*([\d.e+-]+)\s*kOhm': 'Rm',
                r'Rf:\s*([\d.e+-]+)\s*kΩ': 'Rf',
                r'Rf:\s*([\d.e+-]+)\s*kOhm': 'Rf',
                r'Rz:\s*([\d.e+-]+)\s*kΩ': 'Rz',
                r'Rz:\s*([\d.e+-]+)\s*kOhm': 'Rz',
            }
            
            for pattern, var_name in patterns.items():
                match = re.search(pattern, stdout)
                if match:
                    try:
                        value_str = match.group(1)
                        # Handle scientific notation
                        if 'e' in value_str.lower() or 'E' in value_str:
                            value = float(value_str)
                        else:
                            value = float(value_str)
                        design_vars[var_name] = value
                    except (ValueError, AttributeError):
                        pass
            
        except Exception as e:
            self.module_logger.warning(f"⚠️ Failed to extract design variables: {e}")
        
        return design_vars
    
    def _extract_optimization_performance(self, execution_log) -> str:
        """Extract performance metrics from execution log (directly use optimizer results, no recalculation)
        
        Args:
            execution_log: Can be a string or dict (containing 'stdout' field)
        """
        # Convert to string uniformly
        log_string = self._get_execution_log_string(execution_log)
        
        performance = []
        
        # Extract performance metrics - use more precise pattern matching
        # Note: Supports Power=, Power =, Power:, Power : formats, allows spaces before = and :
        perf_patterns = [
            (r'Gain\s*[=:]\s*([\d.]+)\s*dB', 'Gain', 'dB'),
            (r'GBW\s*[=:]\s*([\d.]+)\s*MHz', 'GBW', 'MHz'),
            (r'PM\s*[=:]\s*([\d.]+)\s*deg', 'Phase Margin', '°'),
            (r'Power\s*[=:]\s*([\d.]+)\s*(?:u|μ)W', 'Power', 'μW'),  # Supports both u and μ, supports = and : formats
            (r'FoM\s*[=:]\s*([\d.]+)', 'FoM', '')
        ]
        
        for pattern, name, unit in perf_patterns:
            match = re.search(pattern, log_string)
            if match:
                value = match.group(1)
                performance.append(f"- {name}: {value} {unit}")
        
        if not performance:
            return "Performance metrics not found"
        
        return "\n".join(performance)
    
    # Note: The following methods have been migrated to p2m/steps/step8_simulation_verification.py:
    # - _format_param_content
    # - _intelligent_extract_design_variables
    # - _generate_param_file_direct
    # - _generate_performance_file_direct
    # - _copy_netlist_template_direct
    # - _generate_testbench_direct
    # - _execute_hspice_simulation_direct
    # - _analyze_simulation_failure
    
    def _generate_param_files(self, response: str, optimization_results: Dict):
        """Generate .param file and performance metrics file"""
        # Extract design variable parameters
        design_vars = self.extract_tagged_content(response, 'design_variables')
        if design_vars:
            param_file = os.path.join(self.config.output_dir, f"iter{self.iteration_count + 1:02d}_step{self.step_count:02d}_global{self.global_step_count:02d}_simulation_verification.param")
            with open(param_file, 'w') as f:
                f.write(design_vars)
            self.module_logger.debug(f"Parameter file generated: {param_file}")
        else:
            self.module_logger.warning("⚠️ Design variable parameters not found, cannot generate .param file")
        
        # Extract performance metrics
        performance_metrics = self.extract_tagged_content(response, 'performance_metrics')
        if performance_metrics:
            perf_file = os.path.join(self.config.output_dir, f"iter{self.iteration_count + 1:02d}_step{self.step_count:02d}_global{self.global_step_count:02d}_simulation_verification_perf.txt")
            with open(perf_file, 'w') as f:
                f.write(performance_metrics)
            self.module_logger.debug(f"Performance metrics file generated: {perf_file}")
        else:
            self.module_logger.warning("⚠️ Performance metrics not found, cannot generate performance metrics file")
    
    def _copy_netlist_template(self):
        """Copy original netlist as template"""
        template_file = os.path.join(self.config.output_dir, f"iter{self.iteration_count + 1:02d}_step{self.step_count:02d}_global{self.global_step_count:02d}_simulation_verification.sp")
        with open(template_file, 'w') as f:
            f.write(self.original_netlist)
        self.module_logger.debug(f"Netlist template generated: {template_file}")
    
    def _generate_final_netlist(self):
        """Generate final merged netlist (referencing Atelier format)"""
        final_netlist = f""".title Project: Three-Stage Opamp
.inc 'opamp.sp'
.inc 'param'

xac vin_ac vo_ac gnd opamp
vin vin_ac 0 ac=1

.OPTIONS INGOLD=0
.option post=2
.op
.ac dec 100 1 1g
.print vdb(vo_ac)
.print vp(vo_ac)
.meas ac gain find vdb(vo_ac) at=1
.meas ac ugf when vdb(vo_ac)=0
.meas ac phase FIND vp(vo_ac) at=ugf
.pz v(vo_ac) vin
.TEMP 27
.end"""
        
        final_file = os.path.join(self.config.output_dir, f"iter{self.iteration_count + 1:02d}_step{self.step_count:02d}_global{self.global_step_count:02d}_simulation_verification_final.sp")
        with open(final_file, 'w') as f:
            f.write(final_netlist)
        self.module_logger.debug(f"Final netlist generated: {final_file}")
    
    
    def perform_hspice_simulation_from_response(self, response: str) -> Dict:
        """Extract netlist from LLM response and execute HSPICE simulation (v9 version: supports parameterized netlist)"""
        self.module_logger.info("="*60)
        self.module_logger.info("Executing HSPICE simulation verification")
        self.module_logger.info("="*60)
        
        # Check if final merged netlist has been generated
        final_netlist_file = os.path.join(self.config.output_dir, f"iter{self.iteration_count + 1:02d}_step{self.step_count:02d}_global{self.global_step_count:02d}_simulation_verification_final.sp")
        
        if os.path.exists(final_netlist_file):
            self.module_logger.info("✅ Found final merged netlist, using parameterized netlist for simulation")
            # Use final merged netlist for simulation
            testbench_file = os.path.join(self.sim_dir, "testbench.sp")
            with open(final_netlist_file, 'r') as f:
                final_content = f.read()
            with open(testbench_file, 'w') as f:
                f.write(final_content)
            self.module_logger.debug(f"Final netlist copied to: {testbench_file}")
            
            # Copy .param file to simulation directory
            param_file = os.path.join(self.config.output_dir, f"iter{self.iteration_count + 1:02d}_step{self.step_count:02d}_global{self.global_step_count:02d}_simulation_verification.param")
            if os.path.exists(param_file):
                sim_param_file = os.path.join(self.sim_dir, "param")
                with open(param_file, 'r') as f:
                    param_content = f.read()
                with open(sim_param_file, 'w') as f:
                    f.write(param_content)
                self.module_logger.debug(f"Parameter file copied to: {sim_param_file}")
            
            # Copy netlist template to simulation directory
            template_file = os.path.join(self.config.output_dir, f"iter{self.iteration_count + 1:02d}_step{self.step_count:02d}_global{self.global_step_count:02d}_simulation_verification.sp")
            if os.path.exists(template_file):
                sim_template_file = os.path.join(self.sim_dir, "opamp.sp")
                with open(template_file, 'r') as f:
                    template_content = f.read()
                with open(sim_template_file, 'w') as f:
                    f.write(template_content)
                self.module_logger.debug(f"Netlist template copied to: {sim_template_file}")
            
            # Read performance metrics file
            perf_file = os.path.join(self.config.output_dir, f"iter{self.iteration_count + 1:02d}_step{self.step_count:02d}_global{self.global_step_count:02d}_simulation_verification_perf.txt")
            expected_performance = None
            if os.path.exists(perf_file):
                with open(perf_file, 'r') as f:
                    expected_performance = f.read()
                expected_file = os.path.join(self.sim_dir, "expected_performance.txt")
                with open(expected_file, 'w') as f:
                    f.write(expected_performance)
                self.module_logger.debug(f"Performance metrics file copied to: {expected_file}")
        else:
            self.module_logger.warning("⚠️ Final merged netlist not found, attempting to extract traditional format netlist from LLM response")
            # Fallback to traditional method: extract netlist from LLM response
            opamp_match = re.search(r'<opamp>(.*?)</opamp>', response, re.DOTALL)
            testbench_match = re.search(r'<testbench>(.*?)</testbench>', response, re.DOTALL)
            performance_match = re.search(r'<expected_performance>(.*?)</expected_performance>',
                                         response, re.DOTALL)
            
            if not opamp_match or not testbench_match:
                self.module_logger.error("❌ Unable to extract netlist from LLM response")
                return None
            
            opamp_content = opamp_match.group(1).strip()
            testbench_content = testbench_match.group(1).strip()
            
            opamp_file = os.path.join(self.sim_dir, "opamp.sp")
            with open(opamp_file, 'w') as f:
                f.write(opamp_content)
            self.module_logger.debug(f"Subcircuit file generated: {opamp_file}")
            
            testbench_file = os.path.join(self.sim_dir, "testbench.sp")
            with open(testbench_file, 'w') as f:
                f.write(testbench_content)
            self.module_logger.debug(f"Testbench file generated: {testbench_file}")
            
            expected_performance = None
            if performance_match:
                expected_performance = performance_match.group(1).strip()
                expected_file = os.path.join(self.sim_dir, "expected_performance.txt")
                with open(expected_file, 'w') as f:
                    f.write(expected_performance)
        
        output_name = "testbench"  # Output file name (without path and extension)
        output_path = os.path.join(self.sim_dir, output_name)
        
        # Check if remote execution is enabled
        self.module_logger.info(f"🔍 Checking remote HSPICE config: hspice_remote_enabled={self.config.hspice_remote_enabled}")
        self.module_logger.info(f"🔍 Config object ID: {id(self.config)}")
        self.module_logger.info(f"🔍 Config type: {type(self.config.hspice_remote_enabled)}")
        self.module_logger.info(f"🔍 Config value: {repr(self.config.hspice_remote_enabled)}")
        if self.config.hspice_remote_enabled:
            # Remote execution mode
            self.module_logger.info("🌐 Using remote HSPICE execution mode")
            self.module_logger.info(f"   Remote server: {self.config.hspice_remote_user}@{self.config.hspice_remote_host}")
            self.module_logger.info(f"   Remote HSPICE path: {self.config.hspice_remote_path}")
            try:
                # NOTE: Remote HSPICE execution has been removed; this branch should be unreachable
                
                # Prepare input file list
                input_files = [testbench_file]
                self.module_logger.debug(f"Input files: {input_files}")
                
                # Prepare additional files (such as .param files and opamp.sp subcircuit files)
                additional_files = []
                sim_param_file = os.path.join(self.sim_dir, "param")
                if os.path.exists(sim_param_file):
                    additional_files.append(sim_param_file)
                    self.module_logger.debug(f"Adding parameter file: {sim_param_file}")
                sim_template_file = os.path.join(self.sim_dir, "opamp.sp")
                if os.path.exists(sim_template_file):
                    additional_files.append(sim_template_file)
                    self.module_logger.debug(f"Adding subcircuit file: {sim_template_file}")
                
                if additional_files:
                    self.module_logger.info(f"Will transfer {len(additional_files)} additional files to remote server")
                else:
                    self.module_logger.warning("⚠️ param or opamp.sp files not found, simulation may fail if testbench.sp requires these files")
                
                # Execute remote HSPICE simulation
                result_files = remote_executor.execute_remote(
                    input_files=input_files,
                    output_name=output_name,
                    local_output_dir=self.sim_dir,
                    additional_files=additional_files if additional_files else None
                )
                
                # Check if result files were successfully downloaded
                if '.ma0' not in result_files:
                    self.module_logger.warning("⚠️ Remote HSPICE execution completed, but .ma0 result file not found")
                    # Try to check error information in .lis file
                    if '.lis' in result_files:
                        with open(result_files['.lis'], 'r') as f:
                            content = f.read()
                            for line in content.split('\n'):
                                if 'error' in line.lower() or 'fatal' in line.lower():
                                    self.module_logger.error(f"Error message: {line.strip()}")
                    return None
                
                performance_file = result_files['.ma0']
                
            except HSPICETimeoutError as e:
                self.logger.error(f"HSPICE simulation timeout: {e}")
                self.module_logger.error(f"❌ {e}")
                return None
            except HSPICESimulationError as e:
                self.logger.error(f"HSPICE simulation failed: {e}")
                self.module_logger.error(f"❌ {e}")
                return None
            except Exception as e:
                sim_error = HSPICESimulationError(f"Error occurred during remote HSPICE execution: {str(e)}")
                self.logger.error(f"HSPICE simulation failed: {sim_error}")
                self.module_logger.error(f"❌ {sim_error}")
                self.module_logger.error(f"   Error details: {type(e).__name__}: {str(e)}")
                import traceback
                self.module_logger.debug(f"   Full stack trace: {traceback.format_exc()}")
                return None
        else:
            # Local execution mode (original logic)
            self.module_logger.info("💻 Using local HSPICE execution mode")
            self.module_logger.info(f"   Local HSPICE path: {self.config.hspice_path}")
            hspice_cmd = f"{self.config.hspice_path} -i {testbench_file} -o {output_path}"
            
            self.module_logger.debug(f"Executing HSPICE command: {hspice_cmd}")
            self.module_logger.debug(f"Timeout setting: {self.config.hspice_timeout} seconds")
            
            try:
                result = subprocess.run(
                    hspice_cmd, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    timeout=self.config.hspice_timeout
                )
                
                if result.returncode != 0:
                    self.module_logger.warning(f"⚠️ HSPICE return code: {result.returncode}")
                    if result.stderr:
                        self.module_logger.warning(f"HSPICE error output:\n{result.stderr[:500]}")
                    
                    lis_file = output_path + ".lis"
                    if os.path.exists(lis_file):
                        with open(lis_file, 'r') as f:
                            content = f.read()
                            for line in content.split('\n'):
                                if 'error' in line.lower() or 'fatal' in line.lower():
                                    self.module_logger.error(f"Error message: {line.strip()}")
            
            except subprocess.TimeoutExpired:
                timeout_error = HSPICETimeoutError(self.config.hspice_timeout)
                self.logger.error(f"HSPICE simulation timeout: {timeout_error}")
                self.module_logger.error(f"❌ {timeout_error}")
                return None
            except Exception as e:
                sim_error = HSPICESimulationError(str(e))
                self.logger.error(f"HSPICE simulation failed: {sim_error}")
                self.module_logger.error(f"❌ {sim_error}")
                return None
            
            performance_file = os.path.join(self.sim_dir, "testbench.ma0")
        results = self.parse_simulation_results(performance_file)
        
        if results:
            # Add expected performance information
            if expected_performance:
                results['expected_performance'] = expected_performance
            else:
                # If expected performance not extracted from netlist response, try to extract from optimization results in context
                results['expected_performance'] = "No expected performance provided (suggest extracting from step 7 optimization results)"
            
            self.generate_simulation_report(results)
        
        return results
    
    def parse_simulation_results(self, ma0_file: str, execution_log = None, sim_dir: str = None) -> Dict:
        """Parse HSPICE .ma0 file to get performance metrics
        
        Args:
            execution_log: Can be a string or dict (containing 'stdout' field), used to extract power consumption value
        """
        results = {
            'gain': 0,
            'ugf': 0,
            'phase_margin': 0,
            'power': 0,
            'fom': 0
        }
        
        self.module_logger.debug(f"Parsing simulation result file: {ma0_file}")
        
        try:
            with open(ma0_file, 'r') as f:
                lines = f.readlines()
            
            if len(lines) >= 5:
                line = lines[4].strip().split()
                if len(line) >= 3:
                    results['gain'] = self.convert_spice_value(line[0])
                    
                    if self.convert_spice_value(line[0]) > 0 and line[1] != "failed":
                        results['ugf'] = self.convert_spice_value(line[1])
                        phase = float(line[2])
                        
                        if phase < -90:
                            results['phase_margin'] = phase + 180
                        else:
                            results['phase_margin'] = phase
            
            # Simplify power calculation: directly use theoretical predicted value
            # Extract power consumption value from optimization results (if available)
            try:
                if execution_log:
                    # Convert to string uniformly
                    log_string = self._get_execution_log_string(execution_log)
                    # Try to extract power from optimization log
                    # Note: Optimization output may use Power=, Power =, Power:, Power : formats, need to support both u and μ units
                    # Match format: Power=32.58 uW, Power = 32.58 uW, Power: 32.58 μW, etc.
                    # Allow spaces between Power and = or :
                    power_match = re.search(r'Power\s*[=:]\s*([\d.]+)\s*(?:u|μ)W', log_string, re.UNICODE)
                    if power_match:
                        power_uw = float(power_match.group(1))
                        results['power'] = power_uw * 1e-6  # Convert to W
                        self.module_logger.debug(f"Using power value from optimization results: {power_uw:.2f} μW")
                    else:
                        # If match fails, try looser match pattern (may not have W, only u or μ)
                        power_match_loose = re.search(r'Power\s*[=:]\s*([\d.]+)\s*(?:u|μ)', log_string, re.UNICODE)
                        if power_match_loose:
                            power_uw = float(power_match_loose.group(1))
                            results['power'] = power_uw * 1e-6  # Convert to W
                            self.module_logger.debug(f"Using power value from optimization results (loose match): {power_uw:.2f} μW")
                        else:
                            # Use default value
                            results['power'] = 100e-6
                            self.module_logger.debug(f"Using default power value: 100.00 μW")
                            self.module_logger.warning(f"⚠️ Warning: Unable to extract power value from optimization log, please check format. Log snippet: {log_string[-500:]}")
                else:
                    # Use default value
                    results['power'] = 100e-6
                    self.module_logger.debug(f"Using default power value: 100.00 μW")
                    self.module_logger.warning(f"⚠️ Warning: execution_log is empty, unable to extract power value")
            except Exception as e:
                self.module_logger.warning(f"⚠️ Power extraction error: {e}")
                results['power'] = 100e-6
            
            if results['power'] > 0 and results['ugf'] > 0:
                results['fom'] = (results['ugf'] / 1e6) * 10 / (results['power'] * 1e3)
            
            # Note: Pole-zero parsing has been removed, now step 9's LLM directly extracts from .pz0 files
            
            self.module_logger.info(f"✅ Simulation results parsed successfully:")
            self.module_logger.info(f"  Gain: {results['gain']:.2f} dB")
            self.module_logger.info(f"  Bandwidth: {results['ugf']/1e6:.2f} MHz")
            self.module_logger.info(f"  Phase margin: {results['phase_margin']:.2f}°")
            self.module_logger.info(f"  Power: {results['power']*1e6:.2f} μW")
            self.module_logger.info(f"  FoM: {results['fom']:.2f}")
                
        except FileNotFoundError:
            self.module_logger.error(f"❌ Result file not found: {ma0_file}")
        except Exception as e:
            self.module_logger.error(f"❌ Result parsing error: {e}", exc_info=True)
        
        return results
    
    
    def convert_spice_value(self, s: str) -> float:
        """Convert SPICE numeric format"""
        try:
            s = str(s).strip()
            if s.endswith('x'):
                return float(s[:-1]) * 1e6
            elif s.endswith('u'):
                return float(s[:-1]) * 1e-6
            elif s.endswith('n'):
                return float(s[:-1]) * 1e-9
            elif s.endswith('p'):
                return float(s[:-1]) * 1e-12
            elif s.endswith('f'):
                return float(s[:-1]) * 1e-15
            elif s.endswith('m'):
                return float(s[:-1]) * 1e-3
            elif s.endswith('k'):
                return float(s[:-1]) * 1e3
            elif s.endswith('M'):
                return float(s[:-1]) * 1e6
            elif s.endswith('G'):
                return float(s[:-1]) * 1e9
            else:
                return float(s)
        except:
            return 0.0
    
    def generate_simulation_report(self, results: Dict):
        """Generate simulation verification report"""
        report_file = os.path.join(self.sim_dir, f"verification_report_iter{self.iteration_count + 1}.md")
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# HSPICE Simulation Verification Report\n\n")
            f.write(f"**Generation Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Simulation Directory**: `{self.sim_dir}`\n\n")
            f.write(f"**Iteration Count**: {self.iteration_count + 1}\n\n")
            
            f.write("## 1. Simulation Results\n\n")
            f.write("| Performance Metric | Value | Target Requirement | Status |\n")
            f.write("|---------------------|-------|---------------------|--------|\n")
            
            gain_status = "✅" if results['gain'] >= 60 else "❌"
            f.write(f"| Gain | {results['gain']:.2f} dB | ≥ 60 dB | {gain_status} |\n")
            
            ugf_status = "✅" if results['ugf'] >= 0.5e6 else "❌"
            f.write(f"| Bandwidth | {results['ugf']/1e6:.2f} MHz | ≥ 0.5 MHz | {ugf_status} |\n")
            
            pm_status = "✅" if 45 <= results['phase_margin'] <= 90 else "❌"
            f.write(f"| Phase Margin | {results['phase_margin']:.2f}° | 45°-90° | {pm_status} |\n")
            
            power_status = "✅" if results['power'] <= 250e-6 else "❌"
            f.write(f"| Power | {results['power']*1e6:.2f} μW | ≤ 250 μW | {power_status} |\n")
            
            f.write(f"| **FoM** | **{results['fom']:.2f}** | Maximize | - |\n")
            
            f.write("\n## 2. Verification Conclusion\n\n")
            
            constraints_met = []
            constraints_failed = []
            
            if results['gain'] >= 60:
                constraints_met.append(f"Gain ({results['gain']:.1f} dB)")
            else:
                constraints_failed.append(f"Gain ({results['gain']:.1f} dB < 60 dB)")
            
            if results['ugf'] >= 0.5e6:
                constraints_met.append(f"Bandwidth ({results['ugf']/1e6:.2f} MHz)")
            else:
                constraints_failed.append(f"Bandwidth ({results['ugf']/1e6:.2f} MHz < 0.5 MHz)")
            
            if 45 <= results['phase_margin'] <= 90:
                constraints_met.append(f"Phase Margin ({results['phase_margin']:.1f}°)")
            else:
                constraints_failed.append(f"Phase Margin ({results['phase_margin']:.1f}° out of 45-90°)")
            
            if results['power'] <= 250e-6:
                constraints_met.append(f"Power ({results['power']*1e6:.1f} μW)")
            else:
                constraints_failed.append(f"Power ({results['power']*1e6:.1f} μW > 250 μW)")
            
            if len(constraints_failed) == 0:
                f.write("### ✅ All Constraints Satisfied!\n\n")
            else:
                f.write(f"### ⚠️ Some Constraints Not Satisfied\n\n")
            
            if constraints_met:
                f.write("**Satisfied Constraints:**\n")
                for c in constraints_met:
                    f.write(f"- ✅ {c}\n")
            
            if constraints_failed:
                f.write("\n**Unsatisfied Constraints:**\n")
                for c in constraints_failed:
                    f.write(f"- ❌ {c}\n")
            
            f.write("\n## 3. Generated File List\n\n")
            f.write("- `opamp.sp` - Numerical op-amp subcircuit netlist\n")
            f.write("- `testbench.sp` - Testbench file\n")
            f.write("- `testbench.ma0` - HSPICE measurement results\n")
            f.write("- `testbench.lis` - HSPICE detailed output\n")
            f.write("- `verification_report.md` - This report\n")
            
        self.module_logger.debug(f"📊 Verification report generated: {report_file}")
        return report_file
    
    def save_pipeline_summary(self, results: List[Dict]):
        """Save pipeline execution summary (v8 enhanced)"""
        summary_file = f"{self.config.output_dir}/pipeline_summary.json"
        
        # v8 new: Calculate final context statistics
        final_stats = self.monitor_context_size()
        
        summary = {
            "execution_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "output_directory": self.config.output_dir,
            "model": self.config.model,
            "total_steps": len(results),
            "successful_steps": sum(1 for r in results if r['success']),
            "python_execution_enabled": self.config.enable_python_execution,
            "hspice_path": self.config.hspice_path,
            "total_iterations": self.iteration_count + 1,
            "max_iterations": self.config.full_pipeline_max_iterations,
            "error_threshold": self.config.error_threshold,
            "final_decision": "ACCEPT" if any("ACCEPT" in r.get('decision', '') for r in results) else "RETRY",
            # v8 new: Context management statistics
            "context_management": {
                "thinking_separation_enabled": self.config.enable_thinking_separation,
                "final_clean_tokens": final_stats['estimated_clean_tokens'],
                "final_full_tokens": final_stats['estimated_full_tokens'],
                "space_saved_percentage": final_stats['space_saved_percentage'],
                "thinking_cache_entries": len(self.thinking_cache)
            },
            "steps": []
        }
        
        for i, result in enumerate(results, 1):
            step_summary = {
                "step_number": i,
                "step_name": result['step'],
                "success": result['success'],
                "output_file": result.get('saved_file', None),
                "full_file": result.get('full_file', None),  # v8 new
                "has_extracted_content": result.get('extracted') is not None,
                "has_python_code": len(result.get('python_codes', [])) > 0
            }
            
            # Use step_number for robust step identification (step 8: Generate Numerical Netlist)
            if result.get('step_number') == 8 and 'simulation_results' in result:
                step_summary['simulation_completed'] = True
                step_summary['simulation_results'] = result['simulation_results']
            
            # Use step_number for robust step identification (step 9: Intelligent Comparison and Decision)
            if result.get('step_number') == 9:
                step_summary['comparison_completed'] = True
                step_summary['decision'] = result.get('decision', 'N/A')
                step_summary['retry_step'] = result.get('retry_step', None)
            
            summary["steps"].append(step_summary)
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        self.module_logger.debug(f"Pipeline summary saved to: {summary_file}")
    
    def generate_comprehensive_report(self, results: List[Dict]):
        """Generate comprehensive report (v8 enhanced version)"""
        report_file = f"{self.config.output_dir}/comprehensive_report.md"
        
        # Get final context statistics
        final_stats = self.monitor_context_size()
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# Circuit Analysis Pipeline Comprehensive Report (v8 Version)\n\n")
            f.write(f"**Generation Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Output Directory**: `{self.config.output_dir}`\n\n")
            f.write(f"**Model Used**: `{self.config.model}`\n\n")
            f.write(f"**HSPICE Path**: `{self.config.hspice_path}`\n\n")
            
            # v8 new: Context management information
            f.write("## Context Management (v8 New Feature)\n\n")
            f.write(f"- **Thinking Separation**: {'Enabled' if self.config.enable_thinking_separation else 'Disabled'}\n")
            f.write(f"- **Final Clean Tokens**: {final_stats['estimated_clean_tokens']:,}\n")
            f.write(f"- **Final Full Tokens**: {final_stats['estimated_full_tokens']:,}\n")
            f.write(f"- **Space Saved**: {final_stats['space_saved_percentage']:.1f}%\n")
            f.write(f"- **Thinking Cache Entries**: {len(self.thinking_cache)}\n")
            f.write(f"- **Max Context Limit**: {self.config.max_context_tokens:,} tokens\n")
            
            f.write("\n## Feedback Mechanism Configuration\n\n")
            f.write(f"- Max Iterations: {self.config.full_pipeline_max_iterations}\n")
            f.write(f"- Error Threshold: {self.config.error_threshold*100:.0f}%\n")
            f.write(f"- Actual Iterations: {self.iteration_count + 1}\n")
            
            f.write("\n## Execution Summary\n\n")
            f.write(f"- Total Steps: {len(results)}\n")
            f.write(f"- Successful Steps: {sum(1 for r in results if r['success'])}\n")
            f.write(f"- Failed Steps: {sum(1 for r in results if not r['success'])}\n")
            f.write(f"- Python Code Execution: {'Enabled' if self.config.enable_python_execution else 'Disabled'}\n")
            
            final_decision = "ACCEPT" if any("ACCEPT" in r.get('decision', '') for r in results) else "RETRY"
            f.write(f"- **Final Decision: {final_decision}**\n")
            
            for result in results:
                # Use step_number for robust step identification (step 8: Generate Numerical Netlist)
                if result.get('step_number') == 8 and result.get('simulation_success'):
                    f.write(f"- **HSPICE Simulation Verification: ✅ Completed**\n")
                    sim_results = result.get('simulation_results', {})
                    f.write(f"  - FoM: {sim_results.get('fom', 0):.2f}\n")
                    f.write(f"  - Gain: {sim_results.get('gain', 0):.2f} dB\n")
                    f.write(f"  - Bandwidth: {sim_results.get('ugf', 0)/1e6:.2f} MHz\n")
                    f.write(f"  - Phase Margin: {sim_results.get('phase_margin', 0):.2f}°\n")
                    f.write(f"  - Power: {sim_results.get('power', 0)*1e6:.2f} μW\n")
                    break
            
            has_comparison = any(r.get('step_number') == 9 for r in results)
            if has_comparison:
                f.write(f"- **Design Result Analysis and Decision-making: ✅ Completed**\n")
            
            if self.iteration_count > 0:
                f.write("\n## Iteration History\n\n")
                iter_count = 1
                for result in results:
                    # Use step_number for robust step identification (step 9: Intelligent Comparison and Decision)
                    if result.get('step_number') == 9:
                        f.write(f"### Iteration {iter_count}\n")
                        decision = result.get('decision', 'N/A')
                        retry_step = result.get('retry_step', None)
                        f.write(f"- Decision: {decision}\n")
                        if retry_step:
                            f.write(f"- Retry Start Step: {retry_step}\n")
                        iter_count += 1
            
            f.write("\n## Step Details\n\n")
            for i, result in enumerate(results, 1):
                status = "✅" if result['success'] else "❌"
                if result.get('saved_file'):
                    filename = os.path.basename(result['saved_file'])
                    f.write(f"{status} **Step {i}**: [{result['step']}](./{filename})")
                    
                    if result.get('python_codes'):
                        f.write(" 📝 *Contains Python Code*")
                    if result.get('simulation_success'):
                        f.write(" 🔬 *Simulation completed*")
                    # Use step_number for robust step identification (step 9: Intelligent Comparison and Decision)
                    if result.get('step_number') == 9:
                        f.write(" 📊🎯 *Design Result Analysis and Decision-making*")
                    f.write("\n")
                else:
                    f.write(f"{status} **Step {i}**: {result['step']} (no output file)\n")
            
            f.write(f"\n## Key Output Files\n\n")
            
            # v8 new: File organization description
            f.write(f"### File Organization Structure (v8)\n")
            f.write(f"- **Clean Response**: `*_clean.md` - Simplified version without thinking\n")
            f.write(f"- **Full Response**: `*_full.md` - Complete version with thinking\n")
            f.write(f"- **Thinking Content**: `thinking_processes/` - Separately stored thinking process\n")
            f.write(f"- **Python Code**: `python_codes/` - Generated and executed code\n")
            f.write(f"- **Simulation Files**: `simulation_verification/` - HSPICE related files\n\n")
            
            f.write(f"### Simulation Verification\n")
            f.write(f"- [HSPICE Simulation Report](./simulation_verification/verification_report_iter{self.iteration_count + 1}.md)\n")
            f.write(f"- [Numerical Netlist](./simulation_verification/opamp.sp)\n")
            f.write(f"- [Testbench](./simulation_verification/testbench.sp)\n")
            
            if has_comparison:
                f.write(f"\n### Design Result Analysis and Decision-making\n")
                for result in results:
                    # Use step_number for robust step identification (step 9: Design Result Analysis and Decision-making)
                    if result.get('step_number') == 9 and result.get('saved_file'):
                        filename = os.path.basename(result['saved_file'])
                        f.write(f"- [Design Result Analysis and Decision-making](./{filename})\n")
                        break
            
            f.write("\n## Notes\n\n")
            f.write("- This report contains LaTeX format mathematical formulas\n")
            f.write("- It is recommended to use a Markdown viewer that supports LaTeX rendering\n")
            f.write("- **v8 New Feature**: Implemented thinking content separation, significantly reducing context size\n")
            f.write("- Clean version is used for API calls, Full version preserves complete reasoning process\n")
            f.write("- Thinking content is stored separately for easy debugging and analysis\n")
            
            f.write("\n---\n")
            f.write("\n*This report is automatically generated by Circuit Analysis Pipeline v8*\n")
        
        self.module_logger.debug(f"Comprehensive report generated: {report_file}")
    
    def save_conversation_history(self):
        """Save conversation history (v8 version: save clean and full versions separately)"""
        # Save clean version
        clean_history_file = f"{self.config.output_dir}/conversation_history_clean.md"
        with open(clean_history_file, 'w', encoding='utf-8') as f:
            f.write("# Conversation History (Clean Version)\n\n")
            f.write(f"**Generation Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Total Iterations**: {self.iteration_count + 1}\n\n")
            f.write("**Note**: This version does not contain thinking content, used for API calls\n\n")
            f.write("---\n\n")
            
            for i, message in enumerate(self.messages):
                role = message['role']
                content = message['content']
                
                if role == 'system':
                    f.write("## System Prompt\n\n")
                elif role == 'user':
                    f.write(f"## User Input #{i}\n\n")
                elif role == 'assistant':
                    f.write(f"## Model Response #{i}\n\n")
                
                f.write(f"{content}\n\n")
                f.write("---\n\n")
        
        self.module_logger.debug(f"Clean conversation history saved to: {clean_history_file}")
        
        # Save full version
        full_history_file = f"{self.config.output_dir}/conversation_history_full.md"
        with open(full_history_file, 'w', encoding='utf-8') as f:
            f.write("# Conversation History (Full Version)\n\n")
            f.write(f"**Generation Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Total Iterations**: {self.iteration_count + 1}\n\n")
            f.write("**Note**: This version contains complete thinking content\n\n")
            f.write("---\n\n")
            
            for i, message in enumerate(self.full_history):
                role = message['role']
                content = message['content']
                
                if role == 'system':
                    f.write("## System Prompt\n\n")
                elif role == 'user':
                    f.write(f"## User Input #{i}\n\n")
                elif role == 'assistant':
                    f.write(f"## Model Response #{i}\n\n")
                
                f.write(f"{content}\n\n")
                f.write("---\n\n")
        
        self.module_logger.debug(f"Full conversation history saved to: {full_history_file}")
        
        return clean_history_file, full_history_file
    
    # run_full_pipeline method has been removed - the actual method used is run_p2m_chain()
    # This method was only used in example code, the actual call path uses run_p2m_chain()
    
    def _group_results_by_iteration(self, p2m_results: List[Dict]) -> Dict[int, List[Dict]]:
        """
        Group results by iteration
        
        Args:
            p2m_results: All P2M step results list
            
        Returns:
            {
                1: [result1, result2, ...],  # All results from iteration 1
                2: [result1, result2, ...],  # All results from iteration 2
                ...
            }
        """
        iterations = {}
        
        for result in p2m_results:
            iter_num = result.get('iteration', 1)  # If not marked, default to 1 (backward compatible)
            if iter_num not in iterations:
                iterations[iter_num] = []
            iterations[iter_num].append(result)
        
        return iterations
    
    def _evaluate_iteration_quality(self, iteration_results: List[Dict]) -> Dict:
        """
        Evaluate quality of a single iteration
        
        Args:
            iteration_results: All step results from a single iteration
            
        Returns:
            {
                'iteration': int,
                'quality_score': float,  # Quality score 0-100
                'step7_success': bool,
                'step8_success': bool,
                'step9_decision': str,  # 'ACCEPT' or 'RETRY' or None
                'has_performance': bool,
                'performance': Dict,  # Performance metrics (if available)
            }
        """
        quality_info = {
            'iteration': iteration_results[0].get('iteration', 1) if iteration_results else 1,
            'quality_score': 0.0,
            'step7_success': False,
            'step8_success': False,
            'step9_decision': None,
            'has_performance': False,
            'performance': {}
        }
        
        # Iterate through all results of this iteration
        for result in iteration_results:
            step_name = result.get('step', '')
            success = result.get('success', False)
            
            # Check step 7 (White Box Optimization) - use step_number for robust identification
            step_number = result.get('step_number')
            if step_number == 7:
                quality_info['step7_success'] = success
                if success:
                    quality_info['quality_score'] += 30  # Step 7 success gets 30 points
            
            # Check step 8 (Generate Numerical Netlist) - use step_number for robust identification
            if step_number == 8:
                quality_info['step8_success'] = success
                if success:
                    quality_info['quality_score'] += 30  # Step 8 success gets 30 points
                    # Extract performance metrics
                    sim_results = result.get('simulation_results', {})
                    if sim_results:
                        quality_info['has_performance'] = True
                        quality_info['performance'] = {
                            'gain': sim_results.get('gain', 0),
                            'ugf': sim_results.get('ugf', 0),
                            'phase_margin': sim_results.get('phase_margin', 0),
                            'power': sim_results.get('power', 0),
                            'fom': sim_results.get('fom', 0)
                        }
                        # Add points based on FoM (higher FoM, higher score, max 40 points)
                        fom = sim_results.get('fom', 0)
                        if fom > 0:
                            quality_info['quality_score'] += min(40, fom / 10)  # FoM/10, max 40 points
            
            # Check step 9 (Intelligent Comparison and Decision) - use step_number for robust identification
            if step_number == 9:
                decision = result.get('decision', '')
                if decision:
                    quality_info['step9_decision'] = decision.upper()
                    if 'ACCEPT' in decision.upper():
                        quality_info['quality_score'] += 100  # ACCEPT gets 100 points (highest priority)
        
        return quality_info
    
    def _select_best_iteration(self, p2m_results: List[Dict]) -> Optional[Dict]:
        """
        Select best iteration from all iterations
        
        Args:
            p2m_results: All P2M step results list
            
        Returns:
            {
                'iteration': int,
                'results': List[Dict],  # All step results from this iteration
                'quality_info': Dict,  # Quality evaluation information
            }
            Returns None if no iteration is found
        """
        # 1. Group by iteration
        iterations = self._group_results_by_iteration(p2m_results)
        
        if not iterations:
            return None
        
        # 2. Evaluate each iteration
        evaluated_iterations = []
        for iter_num, iter_results in iterations.items():
            quality_info = self._evaluate_iteration_quality(iter_results)
            evaluated_iterations.append({
                'iteration': iter_num,
                'results': iter_results,
                'quality_info': quality_info
            })
        
        # 3. Select best iteration
        # Priority: ACCEPT > (step7 success + step8 success) > step7 success > others
        best = None
        best_score = -1
        
        for iter_info in evaluated_iterations:
            quality = iter_info['quality_info']
            score = quality['quality_score']
            
            # Prioritize ACCEPT iterations
            if quality['step9_decision'] == 'ACCEPT':
                self.module_logger.info(f"✅ Selected iteration {iter_info['iteration']} as best iteration (decision: ACCEPT)")
                return iter_info
            
            # Next, select iterations where both step 7 and 8 succeeded (sorted by quality score)
            if quality['step7_success'] and quality['step8_success']:
                if score > best_score:
                    best = iter_info
                    best_score = score
            
            # Then select iterations where step 7 succeeded
            elif quality['step7_success']:
                if best is None or (not best['quality_info']['step8_success']):
                    if score > best_score:
                        best = iter_info
                        best_score = score
        
        # If best iteration found
        if best:
            self.module_logger.info(f"✅ Selected iteration {best['iteration']} as best iteration (quality score: {best_score:.1f})")
            return best
        
        # If all failed, return last iteration (at least has one result)
        if evaluated_iterations:
            last_iter = evaluated_iterations[-1]
            self.module_logger.warning(f"⚠️ All iterations failed, using last iteration {last_iter['iteration']} as reference")
            return last_iter
        
        return None
    
    def _select_best_iteration(self, p2m_results: List[Dict]) -> Optional[Dict]:
        """
        Select best iteration from all iterations
        
        Args:
            p2m_results: All P2M step results list
            
        Returns:
            {
                'iteration': int,
                'results': List[Dict],  # All step results from this iteration
                'quality_info': Dict,  # Quality evaluation information
            }
            Returns None if no iteration is found
        """
        # 1. Group by iteration
        iterations = self._group_results_by_iteration(p2m_results)
        
        if not iterations:
            return None
        
        # 2. Evaluate each iteration
        evaluated_iterations = []
        for iter_num, iter_results in iterations.items():
            quality_info = self._evaluate_iteration_quality(iter_results)
            evaluated_iterations.append({
                'iteration': iter_num,
                'results': iter_results,
                'quality_info': quality_info
            })
        
        # 3. Select best iteration
        # Priority: ACCEPT > (step7 success + step8 success) > step7 success > others
        best = None
        best_score = -1
        
        for iter_info in evaluated_iterations:
            quality = iter_info['quality_info']
            score = quality['quality_score']
            
            # Prioritize ACCEPT iterations
            if quality['step9_decision'] == 'ACCEPT':
                self.module_logger.info(f"✅ Selected iteration {iter_info['iteration']} as best iteration (decision: ACCEPT)")
                return iter_info
            
            # Next, select iterations where both step 7 and 8 succeeded (sorted by quality score)
            if quality['step7_success'] and quality['step8_success']:
                if score > best_score:
                    best = iter_info
                    best_score = score
            
            # Then select iterations where step 7 succeeded
            elif quality['step7_success']:
                if best is None or (not best['quality_info']['step8_success']):
                    if score > best_score:
                        best = iter_info
                        best_score = score
        
        # If best iteration found
        if best:
            self.module_logger.info(f"✅ Selected iteration {best['iteration']} as best iteration (quality score: {best_score:.1f})")
            return best
        
        # If all failed, return last iteration (at least has one result)
        if evaluated_iterations:
            last_iter = evaluated_iterations[-1]
            self.module_logger.warning(f"⚠️ All iterations failed, using last iteration {last_iter['iteration']} as reference")
            return last_iter
        
        return None
    
    def _run_p2m_core_with_iteration(self, netlist: str, output_dir: str, 
                                     max_iterations: int = None,
                                     enable_step9: bool = True,
                                     quiet_mode: bool = False) -> Dict:
        """
        Core P2M execution logic (with iteration mechanism and intelligent retry) - reference v3 implementation
        
        Args:
            netlist: Netlist content
            output_dir: Output directory (must be specified)
            max_iterations: Maximum iteration count (default uses config.full_pipeline_max_iterations)
            enable_step9: Whether to execute step 9 (decision mechanism)
            quiet_mode: Quiet mode (reduce log output)
        
        Returns:
            {
                'success': bool,
                'p2m_results': List[Dict],  # All step results
                'final_decision': str,  # 'ACCEPT' or 'RETRY' or None
                'satisfies_requirements': bool,  # Whether requirements are satisfied
                'iteration_count': int,  # Actual iteration count
            }
        """
        if max_iterations is None:
            max_iterations = self.config.full_pipeline_max_iterations
        
        # Save original instance state
        original_output_dir = self.config.output_dir
        original_netlist_backup = self.original_netlist
        original_iteration_count = self.iteration_count
        original_lessons_learned = self.lessons_learned
        original_cached_steps = self.cached_steps.copy()
        original_retry_from_step = self.retry_from_step
        original_messages = self.messages.copy()
        original_full_history = self.full_history.copy()
        original_step_count = self.step_count
        
        # Local state (isolated iteration state)
        local_state = {
            'iteration_count': 0,
            'lessons_learned': '',
            'cached_steps': {},
            'retry_from_step': None,
        }
        
        # Initialize context (start from system prompt, ensure complete independence)
        # If current context has system prompt, copy it; otherwise reload from file
        local_messages = []
        local_full_history = []
        if self.messages and len(self.messages) > 0 and self.messages[0].get('role') == 'system':
            # Copy system prompt
            local_messages.append(self.messages[0].copy())
            if self.full_history and len(self.full_history) > 0:
                local_full_history.append(self.full_history[0].copy())
            else:
                local_full_history.append(self.messages[0].copy())
        else:
            # If current context doesn't have system prompt, reload from file
            system_prompt_file = os.path.join(self.prompts_dir, "system_prompt.md")
            system_prompt = load_prompt_from_file(system_prompt_file)
            if system_prompt:
                local_messages.append({
                    "role": "system",
                    "content": system_prompt
                })
                local_full_history.append({
                    "role": "system",
                    "content": system_prompt
                })
            else:
                # If file doesn't exist, at least create an empty system prompt placeholder
                local_messages.append({
                    "role": "system",
                    "content": "You are a circuit analysis assistant."
                })
                local_full_history.append({
                    "role": "system",
                    "content": "You are a circuit analysis assistant."
                })
        
        results = []
        base_output_dir = output_dir
        
        try:
            # Temporarily replace instance state (for step execution)
            self.config.output_dir = base_output_dir
            self.original_netlist = netlist
            self.messages = local_messages
            self.full_history = local_full_history
            self.step_count = 0
            self.iteration_count = 0  # Temporarily set, will be updated in loop
            
            if not quiet_mode:
                self.module_logger.info(f"🚀 Starting P2M chain execution (supports internal iterations, max {max_iterations} times)")
            
            while local_state['iteration_count'] < max_iterations:
                local_state['iteration_count'] += 1
                current_iteration = local_state['iteration_count']
                
                if not quiet_mode:
                    self.module_logger.info("="*60)
                    self.module_logger.info(f"🔄 P2M Internal Iteration {current_iteration}/{max_iterations}")
                    self.module_logger.info("="*60)
                
                # Create iteration subdirectory
                iteration_dir = f"{base_output_dir}/iteration_{current_iteration:02d}"
                os.makedirs(iteration_dir, exist_ok=True)
                if not quiet_mode:
                    self.module_logger.debug(f"Iteration directory: {iteration_dir}")
                
                self.config.output_dir = iteration_dir
                self.iteration_count = current_iteration - 1  # step9 needs correct iteration count (starts from 0)
                self.thinking_dir = f"{iteration_dir}/thinking_processes"
                self.code_dir = f"{iteration_dir}/python_codes"
                self.sim_dir = f"{iteration_dir}/simulation_verification"
                os.makedirs(self.thinking_dir, exist_ok=True)
                os.makedirs(self.code_dir, exist_ok=True)
                os.makedirs(self.sim_dir, exist_ok=True)
                
                # Record current iteration start position (for marking iteration)
                iteration_start_index = len(results)
                
                # Intelligent retry logic: determine which step to start from
                start_step = 1 if current_iteration == 1 else (local_state['retry_from_step'] or 1)
                
                if local_state['iteration_count'] > 1 and start_step > 1:
                    if not quiet_mode:
                        self.module_logger.info(f"🔄 Retrying from step {start_step}, using cached results from steps 1-{start_step-1}")
                    # Restore context from cache
                    if f'step_{start_step-1}' in local_state['cached_steps']:
                        cached = local_state['cached_steps'][f'step_{start_step-1}']
                        self.messages = cached['messages'].copy()
                        self.full_history = cached['full_history'].copy()
                        self.step_count = cached['step_count']
                
                # If there are lessons learned, need to inject before each step execution (execute_step will handle automatically)
                if local_state['lessons_learned']:
                    # Temporarily set lessons_learned, execute_step will read it
                    self.lessons_learned = local_state['lessons_learned']
                
                # Execute each step (conditional execution, called through steps module)
                if start_step <= 1:
                    result1 = step1_read_netlist(self, netlist)
                    result1['iteration'] = current_iteration  # Add iteration marker
                    result1['iteration_step_index'] = len(results) - iteration_start_index
                    results.append(result1)
                    if not result1['success']:
                        if not quiet_mode:
                            self.module_logger.error("❌ P2M chain terminated: Step 1 failed")
                        break
                    local_state['cached_steps']['step_1'] = {
                        'messages': self.messages.copy(),
                        'full_history': self.full_history.copy(),
                        'step_count': self.step_count,
                        'global_step_count': self.global_step_count
                    }
                
                if start_step <= 2:
                    result2 = step2_list_equations(self)
                    result2['iteration'] = current_iteration  # Add iteration marker
                    result2['iteration_step_index'] = len(results) - iteration_start_index
                    results.append(result2)
                    if not result2['success']:
                        if not quiet_mode:
                            self.module_logger.error("❌ P2M chain terminated: Step 2 failed")
                        break
                    local_state['cached_steps']['step_2'] = {
                        'messages': self.messages.copy(),
                        'full_history': self.full_history.copy(),
                        'step_count': self.step_count,
                        'global_step_count': self.global_step_count
                    }
                
                if start_step <= 3:
                    result3 = step3_solve_transfer_function(self)
                    result3['iteration'] = current_iteration  # Add iteration marker
                    result3['iteration_step_index'] = len(results) - iteration_start_index
                    results.append(result3)
                    if not result3['success']:
                        if not quiet_mode:
                            self.module_logger.error("❌ P2M chain terminated: Step 3 failed")
                        break
                    local_state['cached_steps']['step_3'] = {
                        'messages': self.messages.copy(),
                        'full_history': self.full_history.copy(),
                        'step_count': self.step_count,
                        'global_step_count': self.global_step_count
                    }
                
                if start_step <= 4:
                    result4 = step4_substitute_simplify(self)
                    result4['iteration'] = current_iteration  # Add iteration marker
                    result4['iteration_step_index'] = len(results) - iteration_start_index
                    results.append(result4)
                    if not result4['success']:
                        if not quiet_mode:
                            self.module_logger.error("❌ P2M chain terminated: Step 4 failed")
                        break
                    local_state['cached_steps']['step_4'] = {
                        'messages': self.messages.copy(),
                        'full_history': self.full_history.copy(),
                        'step_count': self.step_count,
                        'global_step_count': self.global_step_count
                    }
                
                if start_step <= 5:
                    result5 = step5_factorize_reduce(self)
                    result5['iteration'] = current_iteration  # Add iteration marker
                    result5['iteration_step_index'] = len(results) - iteration_start_index
                    results.append(result5)
                    if not result5['success']:
                        if not quiet_mode:
                            self.module_logger.error("❌ P2M chain terminated: Step 5 failed")
                        break
                    local_state['cached_steps']['step_5'] = {
                        'messages': self.messages.copy(),
                        'full_history': self.full_history.copy(),
                        'step_count': self.step_count,
                        'global_step_count': self.global_step_count
                    }
                
                if start_step <= 6:
                    result6 = step6_functional_implementation(self)
                    result6['iteration'] = current_iteration  # Add iteration marker
                    result6['iteration_step_index'] = len(results) - iteration_start_index
                    results.append(result6)
                    if not result6['success']:
                        if not quiet_mode:
                            self.module_logger.error("❌ P2M chain terminated: Step 6 failed")
                        break
                    local_state['cached_steps']['step_6'] = {
                        'messages': self.messages.copy(),
                        'full_history': self.full_history.copy(),
                        'step_count': self.step_count,
                        'global_step_count': self.global_step_count
                    }
                
                # Handle step 7 and step 8 execution
                if start_step <= 7:
                    result7 = step7_white_box_optimization(self)
                    result7['iteration'] = current_iteration  # Add iteration marker
                    result7['iteration_step_index'] = len(results) - iteration_start_index
                    results.append(result7)
                    # Continue execution regardless of step 7 success or failure
                    local_state['cached_steps']['step_7'] = {
                        'messages': self.messages.copy(),
                        'full_history': self.full_history.copy(),
                        'step_count': self.step_count,
                        'global_step_count': self.global_step_count
                    }
                    
                    # Decide whether to continue based on step 7 results
                    if result7['success']:
                        # Optimization succeeded: execute step 8
                        if not quiet_mode:
                            self.module_logger.info("="*60)
                            self.module_logger.info("Step 8: Simulation Verification")
                            self.module_logger.info("="*60)
                        
                        result8 = step8_generate_numerical_netlist(self, optimization_results=result7)
                        result8['iteration'] = current_iteration  # Add iteration marker
                        result8['iteration_step_index'] = len(results) - iteration_start_index
                        results.append(result8)
                        
                        if result8['success']:
                            result8['simulation_success'] = True
                            if not quiet_mode:
                                self.module_logger.info("✅ Step 8 HSPICE simulation verification completed!")
                        else:
                            result8['simulation_success'] = False
                        
                        # Cache step 8 results (if retry needed)
                        local_state['cached_steps']['step_8'] = {
                            'messages': self.messages.copy(),
                            'full_history': self.full_history.copy(),
                            'step_count': self.step_count,
                            'global_step_count': self.global_step_count
                        }
                    else:
                        # Create virtual result8
                        result8 = {
                            'success': False,
                            'step': 'simulation_verification (skipped)',
                            'response': 'Skipping netlist generation due to white-box optimization failure',
                            'simulation_success': False,
                            'iteration': current_iteration,  # Add iteration marker
                            'iteration_step_index': len(results) - iteration_start_index
                        }
                        results.append(result8)
                elif start_step == 8:
                    # Retry from step 8: need to restore step 7 results from cache
                    if 'step_7' in local_state['cached_steps']:
                        # Restore step 7 context (if needed)
                        cached_step7 = local_state['cached_steps']['step_7']
                        # Note: Step 8 may need step 7 results, need to get from previous results
                        # Find result7 from previous iteration
                        result7 = None
                        for prev_result in results:
                            # Use step_number for robust step identification (step 7: White Box Optimization)
                            if prev_result.get('step_number') == 7:
                                result7 = prev_result
                                break
                        
                        if result7 and result7.get('success'):
                            # Have successful step 7 result, can execute step 8
                            if not quiet_mode:
                                self.module_logger.info("="*60)
                                self.module_logger.info("Step 8: Simulation Verification (retry from step 8)")
                                self.module_logger.info("="*60)
                            
                            result8 = step8_generate_numerical_netlist(self, optimization_results=result7)
                            result8['iteration'] = current_iteration  # Add iteration marker
                            result8['iteration_step_index'] = len(results) - iteration_start_index
                            results.append(result8)
                            
                            if result8['success']:
                                result8['simulation_success'] = True
                                if not quiet_mode:
                                    self.module_logger.info("✅ Step 8 HSPICE simulation verification completed!")
                            else:
                                result8['simulation_success'] = False
                            
                            # Cache step 8 results (if retry step 9 needed)
                            local_state['cached_steps']['step_8'] = {
                                'messages': self.messages.copy(),
                                'full_history': self.full_history.copy(),
                                'step_count': self.step_count,
                                'global_step_count': self.global_step_count
                            }
                        else:
                            # No valid step 7 result, create virtual result8
                            result8 = {
                                'success': False,
                                'step': 'simulation_verification (skipped)',
                                'response': 'Skipping netlist generation due to white-box optimization failure or unavailable results',
                                'simulation_success': False,
                                'iteration': current_iteration,  # Add iteration marker
                                'iteration_step_index': len(results) - iteration_start_index
                            }
                            results.append(result8)
                    else:
                        # No step 7 cache, create virtual result8
                        result8 = {
                            'success': False,
                            'step': 'simulation_verification (skipped)',
                            'response': 'Unable to find step 7 results, skipping netlist generation',
                            'simulation_success': False,
                            'iteration': current_iteration,  # Add iteration marker
                            'iteration_step_index': len(results) - iteration_start_index
                        }
                        results.append(result8)
                
                # Step 9: Design Result Analysis and Decision-making
                if enable_step9:
                    if not quiet_mode:
                        self.module_logger.info("="*60)
                        self.module_logger.info("Step 9: Design Result Analysis and Decision-making")
                        self.module_logger.info("="*60)
                    
                    # Ensure result7 is not None (if None, create virtual result7)
                    if result7 is None:
                        result7 = {
                            'success': False,
                            'step': 'white_box_optimization_programming (not found)',
                            'response': 'Unable to find step 7 results',
                            'execution_results': []
                        }
                    
                    if result7.get('success', False) and result8.get('success', False):
                        # Optimization succeeded and has simulation results
                        decision_result = step9_intelligent_comparison(
                            self,
                            sim_results=result8.get('simulation_results'), 
                            optimization_results=result7
                        )
                    elif result7.get('success', False) and not result8.get('success', False):
                        # Optimization succeeded but simulation failed
                        # Extract Step 8 failure information (including intelligent analysis results)
                        failure_analysis = result8.get('failure_analysis', {})
                        if failure_analysis:
                            # Use detailed results from intelligent analysis
                            step8_failure_info = f"""Step 8 failure reason: {result8.get('error', 'Unknown error')}

## Intelligent Error Analysis Results

### Failure Cause Analysis
{failure_analysis.get('failure_analysis', 'Unable to analyze')}

### Error Location
{failure_analysis.get('error_location', 'Unknown location')}

### Suggested Fix Methods
{failure_analysis.get('suggested_fix', 'No suggestions')}
"""
                        else:
                            # If no analysis results, use simple error message
                            step8_failure_info = f"Step 8 failure reason: {result8.get('error', 'Unknown error')}"
                        
                        decision_result = step9_intelligent_comparison(
                            self,
                            sim_results=None, 
                            optimization_failure_info=step8_failure_info,
                            optimization_results=result7
                        )
                    else:
                        # Optimization failed
                        optimization_failure_info = self.extract_optimization_failure_info(result7)
                        decision_result = step9_intelligent_comparison(
                            self,
                            sim_results=None, 
                            optimization_failure_info=optimization_failure_info,
                            optimization_results=result7
                        )
                    
                    decision_result['iteration'] = current_iteration  # Add iteration marker
                    decision_result['iteration_step_index'] = len(results) - iteration_start_index
                    results.append(decision_result)
                    
                    if not decision_result['success']:
                        if not quiet_mode:
                            self.module_logger.error("❌ Design Result Analysis and Decision-making failed, defaulting to accept result")
                        break
                    
                    # Check decision
                    decision = decision_result.get('decision', 'RETRY')
                    if "ACCEPT" in decision.upper():
                        if not quiet_mode:
                            self.module_logger.info("🎉 Optimization result accepted! P2M chain completed successfully!")
                        # Save complete context of P2M chain
                        p2m_messages = self.messages.copy()
                        p2m_full_history = self.full_history.copy()
                        # Select best iteration
                        best_iteration = self._select_best_iteration(results)
                        return {
                            'success': True,
                            'p2m_results': results,
                            'best_iteration': best_iteration,  # New: Best iteration information
                            'iterations': self._group_results_by_iteration(results),  # New: Results grouped by iteration
                            'final_decision': 'ACCEPT',
                            'satisfies_requirements': True,
                            'iteration_count': local_state['iteration_count'],
                            'p2m_messages': p2m_messages,
                            'p2m_full_history': p2m_full_history
                        }
                    
                    # Retry needed
                    if not quiet_mode:
                        self.module_logger.info(f"⚠️ Decision: Retry required")
                    local_state['retry_from_step'] = decision_result.get('retry_step', 4)
                    local_state['lessons_learned'] = decision_result.get('lessons_learned', '')
                    
                    if not quiet_mode:
                        self.module_logger.info(f"Will retry from step {local_state['retry_from_step']}")
                        if local_state['lessons_learned']:
                            self.module_logger.debug(f"Lessons learned recorded, will be applied in next iteration")
                
                # Check if maximum iterations reached
                if local_state['iteration_count'] >= max_iterations:
                    if not quiet_mode:
                        self.module_logger.warning(f"⚠️ Reached maximum iterations ({max_iterations}), P2M chain ended")
                    break
            
            # Iterations exhausted or early exit
            # Save complete context of P2M chain
            p2m_messages = self.messages.copy()
            p2m_full_history = self.full_history.copy()
            # Select best iteration
            best_iteration = self._select_best_iteration(results)
            return {
                'success': True,  # Technically successfully executed all steps
                'p2m_results': results,
                'best_iteration': best_iteration,  # New: Best iteration information
                'iterations': self._group_results_by_iteration(results),  # New: Results grouped by iteration
                'final_decision': 'RETRY' if enable_step9 else None,
                'satisfies_requirements': False,  # But requirements not satisfied
                'iteration_count': local_state['iteration_count'],
                'p2m_messages': p2m_messages,
                'p2m_full_history': p2m_full_history
            }
            
        finally:
            # Restore original instance state
            self.config.output_dir = original_output_dir
            self.original_netlist = original_netlist_backup
            self.iteration_count = original_iteration_count
            self.lessons_learned = original_lessons_learned
            self.cached_steps = original_cached_steps
            self.retry_from_step = original_retry_from_step
            self.messages = original_messages
            self.full_history = original_full_history
            self.step_count = original_step_count
    
    def run_p2m_chain(self, netlist: str, output_dir: str = None) -> Dict:
        """Run complete P2M chain (improved version: supports internal iterations and intelligent retry)"""
        # Save original output directory
        original_output_dir = self.config.output_dir
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        else:
            output_dir = self.config.output_dir
        
        try:
            # Call core method
            # Prefer p2m_max_iterations, if not exists fall back to full_pipeline_max_iterations (backward compatible)
            # Note: Since PipelineConfig is a dataclass, p2m_max_iterations attribute should always exist (default value 5)
            # But if it doesn't exist for some reason, using hasattr check is safer
            if hasattr(self.config, 'p2m_max_iterations'):
                p2m_iterations = self.config.p2m_max_iterations
            else:
                # Backward compatible: if attribute doesn't exist, use full_pipeline_max_iterations
                p2m_iterations = self.config.full_pipeline_max_iterations
            # Debug output: confirm actual iteration count used
            self.module_logger.debug(f"[Debug] P2M iteration count configuration check:")
            self.module_logger.debug(f"  - hasattr(p2m_max_iterations) = {hasattr(self.config, 'p2m_max_iterations')}")
            self.module_logger.debug(f"  - self.config.p2m_max_iterations = {getattr(self.config, 'p2m_max_iterations', 'N/A')}")
            self.module_logger.debug(f"  - self.config.full_pipeline_max_iterations = {self.config.full_pipeline_max_iterations}")
            self.module_logger.debug(f"  - Final iteration count used: {p2m_iterations}")
            core_result = self._run_p2m_core_with_iteration(
                netlist=netlist,
                output_dir=output_dir,
                max_iterations=p2m_iterations,
                enable_step9=True,  # P2M chain should execute step 9
                quiet_mode=False
            )
            
            # Convert return format (maintain backward compatibility)
            result = {
                'success': core_result['success'],
                'p2m_results': core_result['p2m_results'],
                'best_iteration': core_result.get('best_iteration'),  # New: Best iteration information
                'iterations': core_result.get('iterations'),  # New: Results grouped by iteration
                'final_decision': core_result.get('final_decision'),
                'satisfies_requirements': core_result.get('satisfies_requirements', False),
                'iteration_count': core_result.get('iteration_count', 0),
                'p2m_messages': core_result.get('p2m_messages', []),
                'p2m_full_history': core_result.get('p2m_full_history', [])
            }
            
            # Collect circuit data (if enabled)
            if self.config.enable_circuit_data_collection and core_result['success']:
                try:
                    # Get or create exploration_history
                    exploration_history = getattr(self, 'exploration_history', None)
                    if exploration_history is None:
                        # If not, create a new one and save to instance
                        exploration_history = ExplorationHistory()
                        self.exploration_history = exploration_history
                    
                    # Collect circuit data
                    # Try to get best iteration information
                    best_iteration_info = core_result.get('best_iteration')
                    if not best_iteration_info:
                        # If not, try to select from p2m_results
                        best_iteration_info = exploration_history._select_best_iteration_simple(
                            core_result['p2m_results']
                        )
                    
                    circuit_data = exploration_history.add_circuit_data(
                        netlist=netlist,
                        p2m_results=core_result['p2m_results'],
                        best_iteration_info=best_iteration_info,
                        config=self.config,
                        output_dir=output_dir,
                        iteration=core_result.get('iteration_count', 0)
                    )
                    self.module_logger.info(f"✅ Circuit data collected: {circuit_data.circuit_id[:8]}...")
                    
                    # If save directory configured, auto-save (only save current architecture data, avoid saving all data)
                    if self.config.circuit_data_save_dir:
                        exploration_history.save_all_circuit_data(self.config.circuit_data_save_dir, circuit_data.circuit_id)
                    elif output_dir:
                        exploration_history.save_all_circuit_data(output_dir, circuit_data.circuit_id)
                    
                except Exception as e:
                    # Data collection failure should not affect main process
                    self.module_logger.warning(f"⚠️ Circuit data collection failed (does not affect main process): {e}")
                    import traceback
                    traceback.print_exc()
            
            return result
        finally:
            # Restore original output directory
            self.config.output_dir = original_output_dir


# Example code has been removed - please use scripts/run_p2m_design.py as entry point
# run_full_pipeline method has been removed, the actual method used is run_p2m_chain()
