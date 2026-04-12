"""Structured logging configuration using structlog for Email Handler LangGraph.

This module provides centralized logging configuration with:
- Structured JSON logging for production observability
- Pretty console output for development
- Correlation ID tracking for request tracing
- Context processors for timestamps, log levels, and agent-specific metadata
- Configurable log levels via environment variables
"""

import logging
import sys
import os
from typing import Any
from pathlib import Path
import structlog
from structlog.types import EventDict, Processor

def add_correlation_id(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add correlation ID to log entries for request tracing.
    
    The correlation ID can be set via bind_contextvars and will persist
    across all log entries within the same execution context.
    """
    # Correlation ID should be bound via structlog.contextvars.bind_contextvars()
    # This processor ensures it's included in every log entry
    return event_dict


def add_agent_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add agent-specific context to log entries.
    
    Useful for tracking which agent (classifier, responder, supervisor)
    generated the log entry.
    """
    # Agent context should be bound when entering agent functions
    return event_dict


def configure_logging(
    log_level: str | None = None,
    json_logs: bool | None = None,
    include_stdlib: bool = True,
    log_file_path: str | None = None,
    enable_file_logging: bool | None = None
) -> None:
    """Configure structlog with appropriate processors and formatters.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                  Defaults to INFO, or LOG_LEVEL env var if set.
        json_logs: Whether to output JSON logs (True) or pretty console logs (False).
                  Defaults to False for development, or JSON_LOGS env var if set.
        include_stdlib: Whether to configure standard library logging integration.
        log_file_path: Path to the log file. Defaults to 'logs/app.log' or LOG_FILE_PATH env var.
        enable_file_logging: Whether to enable file logging. Defaults to False or ENABLE_FILE_LOGGING env var.
    
    Environment Variables:
        LOG_LEVEL: Set the logging level (default: INFO)
        JSON_LOGS: Set to 'true' for JSON output, 'false' for console (default: false)
        LOG_FILE_PATH: Path to the log file (default: logs/app.log)
        ENABLE_FILE_LOGGING: Set to 'true' to enable file logging (default: false)
    
    Example:
        >>> configure_logging(log_level="DEBUG", json_logs=False, log_file_path="logs/app.log", enable_file_logging=True)
        >>> logger = structlog.get_logger()
        >>> logger.info("email_classified", intent="billing", urgency="critical")
    """
    # Determine log level from parameter, env var, or default
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Determine output format from parameter, env var, or default
    if json_logs is None:
        json_logs = os.getenv("JSON_LOGS", "false").lower() == "true"
    
    # Determine file logging settings
    if enable_file_logging is None:
        enable_file_logging = os.getenv("ENABLE_FILE_LOGGING", "false").lower() == "true"
    
    if log_file_path is None:
        log_file_path = os.getenv("LOG_FILE_PATH", "logs/app.log")
    
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level, logging.INFO)
    
    # Configure standard library logging if requested
    if include_stdlib:
        # Create handlers list
        handlers = [logging.StreamHandler(sys.stdout)]
        
        # Add file handler if file logging is enabled
        if enable_file_logging:
            # Create log directory if it doesn't exist
            log_path = Path(log_file_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Add file handler with rotation support
            file_handler = logging.FileHandler(
                filename=log_file_path,
                mode='a',
                encoding='utf-8'
            )
            handlers.append(file_handler)
        
        logging.basicConfig(
            format="%(message)s",
            handlers=handlers,
            level=numeric_level,
        )
    
    # Define shared processors for all configurations
    shared_processors: list[Processor] = [
        # Add correlation ID and agent context
        structlog.contextvars.merge_contextvars,
        add_correlation_id,
        add_agent_context,
        
        # Add log level and timestamp (GMT-5 timezone)
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        
        # Stack info and exception formatting
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    
    # Choose renderer based on output format
    if json_logs:
        # Production: JSON output for log aggregation systems
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ]
    else:
        # Development: Pretty console output with colors
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a configured structlog logger instance.
    
    Args:
        name: Optional logger name (typically __name__ of the module)
    
    Returns:
        Configured structlog BoundLogger instance
    
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("processing_email", email_id="email_123", sender="user@example.com")
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


# Auto-configure on import with sensible defaults
# This can be overridden by calling configure_logging() explicitly
configure_logging()
