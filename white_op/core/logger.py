"""
Logging utilities (logger).

Provides unified logging helpers:
- LoggerManager: global logger manager (singleton)
- ThreadSafeLogger: thread-safe logger wrapper
- get_logger: factory to obtain a module logger
- get_parallel_task_logger: logger for parallel tasks
- setup_logging: backward-compatible logging setup
- StreamToLogger: redirect print output to logging
"""

import os
import sys
import logging
import threading
import inspect
from typing import Optional, Dict
from logging.handlers import RotatingFileHandler


class StreamToLogger:
    """Redirect print output to logging."""
    
    def __init__(self, logger, log_level=logging.INFO):
        """
        Initialize StreamToLogger
        
        Args:
            logger: logging.Logger instance
            log_level: Log level
        """
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        """Write to buffer"""
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        """Flush buffer (empty implementation)"""
        pass


class LoggerManager:
    """Global logger manager (singleton)."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(LoggerManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize LoggerManager"""
        if self._initialized:
            return
        
        self.loggers: Dict[str, logging.Logger] = {}  # Logger registry
        self.global_level = logging.INFO  # Global log level
        self.console_level = logging.INFO  # Console log level
        self.file_level = logging.DEBUG  # File log level
        self.global_output_dir: Optional[str] = None  # Global output directory
        self.lock = threading.Lock()  # Thread lock
        self._initialized = True
    
    @classmethod
    def get_instance(cls) -> 'LoggerManager':
        """Get LoggerManager singleton"""
        return cls()
    
    def setup_global_logging(self, 
                            output_dir: str,
                            global_level: int = logging.INFO,
                            console_level: int = logging.INFO,
                            file_level: int = logging.DEBUG):
        """
        Setup global logging configuration
        
        Args:
            output_dir: Global output directory
            global_level: Global log level
            console_level: Console log level
            file_level: File log level
        """
        with self.lock:
            self.global_output_dir = output_dir
            self.global_level = global_level
            self.console_level = console_level
            self.file_level = file_level
            
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
    
    def get_logger(self, 
                   name: str,
                   output_dir: Optional[str] = None,
                   console: bool = True,
                   file: bool = True,
                   level: Optional[int] = None,
                   log_file: Optional[str] = None,
                   console_level: Optional[int] = None) -> logging.Logger:
        """
        Get or create logger
        
        Args:
            name: Logger name (e.g., 'architecture_search.search_engine')
            output_dir: Log file output directory (optional, defaults to global output directory)
            console: Whether to output to console
            file: Whether to output to file
            level: Log level (optional, uses global level)
            log_file: Log file name (optional, defaults to '{name}.log')
            console_level: Console log level (optional, defaults to global console level)
        
        Returns:
            logging.Logger instance
        """
        with self.lock:
            # If logger already exists, check if file handler needs to be updated
            if name in self.loggers:
                logger = self.loggers[name]
                
                # Check if file handler already exists
                has_file_handler = any(isinstance(h, RotatingFileHandler) for h in logger.handlers)
                
                # If file output is needed but no file handler exists, and output_dir is set, add file handler
                if file and not has_file_handler:
                    if output_dir is None:
                        output_dir = self.global_output_dir
                    
                    if output_dir:
                        os.makedirs(output_dir, exist_ok=True)
                        
                        if log_file is None:
                            log_file = f"{name.replace('.', '_')}.log"
                        
                        log_path = os.path.join(output_dir, log_file)
                        
                        # Use RotatingFileHandler to support log rotation
                        file_handler = RotatingFileHandler(
                            log_path,
                            maxBytes=10*1024*1024,  # 10MB
                            backupCount=5,
                            encoding='utf-8'
                        )
                        file_handler.setLevel(self.file_level)
                        
                        # File format (detailed)
                        file_formatter = logging.Formatter(
                            '%(asctime)s.%(msecs)03d [%(levelname)8s] [%(name)s] [%(threadName)s] %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S'
                        )
                        file_handler.setFormatter(file_formatter)
                        logger.addHandler(file_handler)
                
                return logger
            
            # Create new logger
            logger = logging.getLogger(name)
            
            # Set log level
            if level is None:
                level = self.global_level
            logger.setLevel(level)
            
            # Clear existing handlers (avoid duplicates)
            logger.handlers.clear()
            
            # Console handler
            if console:
                console_handler = logging.StreamHandler(sys.stdout)
                # If console_level is specified, use it; otherwise use global console level
                console_level_to_use = console_level if console_level is not None else self.console_level
                console_handler.setLevel(console_level_to_use)
                
                # Console format (concise)
                console_formatter = logging.Formatter(
                    '[%(asctime)s] [%(levelname)8s] [%(name)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                console_handler.setFormatter(console_formatter)
                logger.addHandler(console_handler)
            
            # File handler
            if file:
                if output_dir is None:
                    output_dir = self.global_output_dir
                
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                    
                    if log_file is None:
                        log_file = f"{name.replace('.', '_')}.log"
                    
                    log_path = os.path.join(output_dir, log_file)
                    
                    # Use RotatingFileHandler to support log rotation
                    file_handler = RotatingFileHandler(
                        log_path,
                        maxBytes=10*1024*1024,  # 10MB
                        backupCount=5,
                        encoding='utf-8'
                    )
                    file_handler.setLevel(self.file_level)
                    
                    # File format (detailed)
                    file_formatter = logging.Formatter(
                        '%(asctime)s.%(msecs)03d [%(levelname)8s] [%(name)s] [%(threadName)s] %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S'
                    )
                    file_handler.setFormatter(file_formatter)
                    logger.addHandler(file_handler)
            
            # Register logger
            self.loggers[name] = logger
            
            return logger


class ThreadSafeLogger:
    """Thread-safe Logger wrapper"""
    
    def __init__(self, logger: logging.Logger):
        """
        Initialize ThreadSafeLogger
        
        Args:
            logger: logging.Logger instance
        """
        self.logger = logger
        self.lock = threading.Lock()
    
    def debug(self, msg, *args, **kwargs):
        """Thread-safe debug output"""
        with self.lock:
            self.logger.debug(msg, *args, **kwargs)
    
    def info(self, msg, *args, **kwargs):
        """Thread-safe info output"""
        with self.lock:
            self.logger.info(msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        """Thread-safe warning output"""
        with self.lock:
            self.logger.warning(msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        """Thread-safe error output"""
        with self.lock:
            self.logger.error(msg, *args, **kwargs)
    
    def critical(self, msg, *args, **kwargs):
        """Thread-safe critical output"""
        with self.lock:
            self.logger.critical(msg, *args, **kwargs)
    
    def exception(self, msg, *args, **kwargs):
        """Thread-safe exception output (automatically includes exception stack trace)"""
        with self.lock:
            self.logger.exception(msg, *args, **kwargs)
    
    def log(self, level, msg, *args, **kwargs):
        """Thread-safe log output"""
        with self.lock:
            self.logger.log(level, msg, *args, **kwargs)


def get_logger(name: str = None,
               module: str = None,
               output_dir: str = None,
               console: bool = True,
               file: bool = True,
               level: int = None,
               thread_safe: bool = True,
               console_level: int = None) -> logging.Logger:
    """
    Factory function to get module logger
    
    Automatically infers module path and creates or retrieves logger instance.
    
        Args:
            name: Logger name (e.g., 'pipeline'), if not provided, inferred from module name
            module: Module path (e.g., 'p2m.pipeline'), if not provided, inferred from call stack
        output_dir: Log file output directory (optional)
        console: Whether to output to console
        file: Whether to output to file
        level: Log level (optional, uses global level)
        thread_safe: Whether to return thread-safe Logger wrapper (default True)
        console_level: Console log level (optional, defaults to global console level)
    
    Returns:
        logging.Logger or ThreadSafeLogger instance
    """
    # Automatically infer module path
    if module is None:
        # Infer module path from call stack
        frame = inspect.currentframe()
        try:
            # Find caller up the stack
            caller_frame = frame.f_back
            if caller_frame:
                module = caller_frame.f_globals.get('__name__', 'unknown')
            else:
                module = 'unknown'
        finally:
            del frame
    
    # Create logger name
    if name:
        logger_name = f"{module}.{name}" if module != 'unknown' else name
    else:
        # Extract name from module path
        if '.' in module:
            logger_name = module
        else:
            logger_name = f"{module}.{module}"
    
    # Get logger from LoggerManager
    manager = LoggerManager.get_instance()
    logger = manager.get_logger(
        logger_name,
        output_dir=output_dir,
        console=console,
        file=file,
        level=level,
        console_level=console_level
    )
    
    # Return thread-safe Logger wrapper or original Logger
    if thread_safe:
        return ThreadSafeLogger(logger)
    else:
        return logger


def get_parallel_task_logger(run_id: int,
                             architecture_id: str,
                             output_dir: str,
                             console: bool = True,
                             file: bool = True,
                             console_level: int = logging.WARNING) -> logging.Logger:
    """
    Get parallel task logger
    
    Create independent logger for each parallel task, logs saved to task output directory.
    
    Args:
        run_id: Run ID (0-4)
        architecture_id: Architecture identifier
        output_dir: Task output directory
        console: Whether to output to console (default True, but only shows WARNING and above levels to reduce output)
        file: Whether to output to file (default True, saves all levels)
        console_level: Console log level (default WARNING, only shows warnings and errors)
    
    Returns:
        Independent logger instance, logs saved to output_dir/task.log
    """
    logger_name = f"parallel_task.run_{run_id:02d}.arch_{architecture_id}"
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Create independent logger (not using LoggerManager to avoid conflicts)
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Prevent log propagation to parent logger
    logger.propagate = False
    
    # Console handler (only shows WARNING and above levels to reduce detailed output)
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)  # Default WARNING, only shows warnings and errors
        
        # Console format (concise, includes run_id)
        console_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)8s] [Run %(run_id)02d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # File handler (saves all levels)
    if file:
        log_file = os.path.join(output_dir, "task.log")
        
        # Use RotatingFileHandler to support log rotation
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=3,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # File format (detailed, includes run_id and thread information)
        file_formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d [%(levelname)8s] [Run %(run_id)02d] [%(threadName)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Create custom Formatter to support run_id
    class RunIdFormatter(logging.Formatter):
        def __init__(self, fmt, datefmt, run_id):
            super().__init__(fmt, datefmt)
            self.run_id = run_id
        
        def format(self, record):
            record.run_id = self.run_id
            return super().format(record)
    
    # Update formatter for all handlers
    for handler in logger.handlers:
        old_formatter = handler.formatter
        if old_formatter:
            fmt = old_formatter._fmt if hasattr(old_formatter, '_fmt') else '%(message)s'
            datefmt = old_formatter.datefmt if hasattr(old_formatter, 'datefmt') else None
            handler.setFormatter(RunIdFormatter(fmt, datefmt, run_id))
    
    # Return thread-safe Logger wrapper
    return ThreadSafeLogger(logger)


def setup_logging(output_dir: str, 
                  global_level: int = logging.INFO,
                  console_level: int = logging.INFO,
                  file_level: int = logging.DEBUG) -> logging.Logger:
    """
    Setup logging configuration (backward compatibility function)
    
    This function maintains backward compatibility while setting global logging configuration.
    
    Args:
        output_dir: Output directory, log files will be saved under this directory
        global_level: Global log level
        console_level: Console log level
        file_level: File log level
    
    Returns:
        Configured Logger instance (pipeline_performance logger)
    """
    # Setup global logging configuration
    manager = LoggerManager.get_instance()
    manager.setup_global_logging(
        output_dir=output_dir,
        global_level=global_level,
        console_level=console_level,
        file_level=file_level
    )
    
    # Create pipeline_performance logger (backward compatibility)
    log_file = os.path.join(output_dir, "pipeline_performance.log")
    
    # Create logger
    logger = logging.getLogger('pipeline_performance')
    logger.setLevel(global_level)
    
    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create file handler
    file_handler = RotatingFileHandler(log_file, 
                                      maxBytes=10*1024*1024,  # 10MB
                                      backupCount=5,
                                      encoding='utf-8')
    file_handler.setLevel(file_level)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
