"""Environment variable validation module.

Validates required environment variables on application startup to ensure
all necessary configuration is present before the application runs.
"""

import os
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import structlog


@dataclass
class EnvVarConfig:
    """Configuration for an environment variable."""
    name: str
    required: bool = True
    default: Optional[str] = None
    description: str = ""
    allowed_values: Optional[List[str]] = None
    validator: Optional[callable] = None


class EnvValidationError(Exception):
    """Raised when environment variable validation fails."""
    pass


class EnvironmentValidator:
    """Validates environment variables on application startup."""
    
    # Define all environment variables with their validation rules
    ENV_VARS = [
        EnvVarConfig(
            name="OPENAI_API_KEY",
            required=True,
            description="OpenAI API key for LLM operations",
            validator=lambda x: len(x) > 20 and x.startswith("sk-")
        ),
        EnvVarConfig(
            name="LOG_LEVEL",
            required=False,
            default="INFO",
            description="Logging level",
            allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        ),
        EnvVarConfig(
            name="JSON_LOGS",
            required=False,
            default="false",
            description="Enable JSON formatted logs",
            allowed_values=["true", "false"]
        ),
        EnvVarConfig(
            name="LOG_FILE_PATH",
            required=False,
            default="logs/app.log",
            description="Path to the log file"
        ),
        EnvVarConfig(
            name="ENABLE_FILE_LOGGING",
            required=False,
            default="false",
            description="Enable file-based logging",
            allowed_values=["true", "false"]
        ),
        EnvVarConfig(
            name="EMBEDDING_PROVIDER",
            required=False,
            default="openai",
            description="Provider for embedding generation",
            allowed_values=["openai"]
        ),
        EnvVarConfig(
            name="VECTOR_STORE_PATH",
            required=False,
            default="data/vector_store",
            description="Path to the vector store directory"
        ),
        EnvVarConfig(
            name="SIMILARITY_THRESHOLD",
            required=False,
            default="1.2",
            description="Similarity threshold for vector store retrieval (L2 distance)"
        ),
        EnvVarConfig(
            name="SLOW_EXECUTION_THRESHOLD",
            required=False,
            default="10000",
            description="Threshold in milliseconds for slow execution detection"
        ),
        EnvVarConfig(
            name="QUESTION_TIMEOUT",
            required=False,
            default="60",
            description="Timeout in seconds for processing a question"
        ),
    ]
    
    def __init__(self, strict_mode: bool = True):
        """Initialize the validator.
        
        Args:
            strict_mode: If True, exit on validation errors. If False, log warnings.
        """
        self.strict_mode = strict_mode
        self.logger = structlog.get_logger(__name__)
        self.validation_errors: List[str] = []
        self.validation_warnings: List[str] = []
    
    def validate_all(self) -> Dict[str, Any]:
        """Validate all environment variables.
        
        Returns:
            Dict of validated environment variables with their values.
            
        Raises:
            EnvValidationError: If validation fails in strict mode.
        """
        validated_vars = {}
        
        for env_config in self.ENV_VARS:
            try:
                value = self._validate_single(env_config)
                validated_vars[env_config.name] = value
            except EnvValidationError as e:
                if self.strict_mode:
                    self.validation_errors.append(str(e))
                else:
                    self.validation_warnings.append(str(e))
        
        # Report results
        if self.validation_errors:
            error_msg = "Environment validation failed:\n" + "\n".join(
                f"  - {err}" for err in self.validation_errors
            )
            self.logger.error(
                "env_validation_failed",
                errors=self.validation_errors,
                error_count=len(self.validation_errors)
            )
            if self.strict_mode:
                self.logger.error("env_validation_fatal", message=error_msg)
                sys.exit(1)
        
        if self.validation_warnings:
            self.logger.warning(
                "env_validation_warnings",
                warnings=self.validation_warnings,
                warning_count=len(self.validation_warnings)
            )
        
        if not self.validation_errors and not self.validation_warnings:
            self.logger.debug(
                "env_validation_successful",
                validated_count=len(validated_vars)
            )
        
        return validated_vars
    
    def _validate_single(self, config: EnvVarConfig) -> Optional[str]:
        """Validate a single environment variable.
        
        Args:
            config: Environment variable configuration.
            
        Returns:
            The validated value (or default if applicable).
            
        Raises:
            EnvValidationError: If validation fails.
        """
        value = os.getenv(config.name)
        
        # Check if required variable is missing
        if value is None or value.strip() == "":
            if config.required:
                raise EnvValidationError(
                    f"{config.name} is required but not set. {config.description}"
                )
            else:
                # Use default value
                value = config.default
                if value is not None:
                    self.logger.debug(
                        "env_var_using_default",
                        var_name=config.name,
                        default_value=value
                    )
        
        # Validate against allowed values
        if value and config.allowed_values:
            if value not in config.allowed_values:
                raise EnvValidationError(
                    f"{config.name}='{value}' is invalid. "
                    f"Allowed values: {', '.join(config.allowed_values)}"
                )
        
        # Run custom validator  
        if value and config.validator:
            try:
                if not config.validator(value):
                    raise EnvValidationError(
                        f"{config.name}='{value}' failed custom validation. "
                        f"{config.description}"
                    )
            except Exception as e:
                raise EnvValidationError(
                    f"{config.name} validation error: {str(e)}"
                )
        
        return value
    
    def _should_redact(self, var_name: str, redact_patterns: List[str]) -> bool:
        """Check if a variable name matches any redaction pattern.
        
        Args:
            var_name: The environment variable name to check.
            redact_patterns: List of patterns (supports wildcards like *API_KEY).
            
        Returns:
            True if the variable should be redacted.
        """
        for pattern in redact_patterns:
            # Convert wildcard pattern to simple matching
            if pattern.startswith("*") and not pattern.endswith("*"):
                # Suffix pattern like *_KEY matches anything ending with _KEY
                suffix = pattern[1:]
                if var_name.endswith(suffix):
                    return True
            elif pattern.endswith("*") and not pattern.startswith("*"):
                # Prefix pattern like PASSWORD* matches anything starting with PASSWORD
                prefix = pattern[:-1]
                if var_name.startswith(prefix):
                    return True
            elif "*" in pattern:
                # Pattern with wildcards in middle or multiple wildcards
                parts = pattern.split("*")

                # Check if all non-empty parts appear in order
                pos = 0
                match = True
                for part in parts:
                    if part:  # Skip empty parts from consecutive *
                        idx = var_name.find(part, pos)
                        if idx == -1:
                            match = False
                            break
                        pos = idx + len(part)
                if match:
                    return True
            else:
                # Exact match
                if var_name == pattern:
                    return True
        return False
    
    def _redact_value(self, value: str) -> str:
        """Redact a sensitive value completely.
        
        Args:
            value: The value to redact.
            
        Returns:
            Fully redacted string (no partial value shown).
        """
        if not value:
            return "***REDACTED***"
        # Always return fully redacted value for sensitive data
        return "***REDACTED***"
    
    def print_env_summary(self, validated_vars: Dict[str, Any], redact_patterns: Optional[List[str]] = None) -> None:
        """Print a summary of environment configuration.
        
        Args:
            validated_vars: Dictionary of validated environment variables.
            redact_patterns: List of patterns for variables to redact (e.g., ['*API_KEY', '*SECRET', 'PASSWORD*']).
                           If None, defaults to ['*_KEY', '*_SECRET', '*_TOKEN', 'PASSWORD*'].
        """
        # Default redaction patterns
        if redact_patterns is None:
            redact_patterns = ['*_KEY', '*_SECRET', '*_TOKEN', 'PASSWORD*']
        
        self.logger.debug(
            "env_config_summary_start", 
            header="Environment Configuration Summary"
        )

        for config in self.ENV_VARS:
            value = validated_vars.get(config.name)
            
            # Mask sensitive values based on patterns
            display_value = value
            if self._should_redact(config.name, redact_patterns):
                if value:
                    display_value = self._redact_value(value)
            
            status = "set" if value else "not_set"
            source = "env" if os.getenv(config.name) else "default"
            
            self.logger.debug(
                "env_var_status",
                var_name=config.name,
                value=display_value or "NOT SET",
                status=status,
                source=source
            )
        
        self.logger.debug(
            "env_config_summary_end", 
            total_vars=len(self.ENV_VARS)
        )


def validate_environment(strict_mode: bool = True, verbose: bool = True, redact_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
    """Convenience function to validate environment variables.
    
    Args:
        strict_mode: If True, exit on validation errors.
        verbose: If True, print environment summary.
        redact_patterns: List of patterns for variables to redact in summary (e.g., ['*API_KEY', '*SECRET']).
                        If None, uses default patterns: ['*_KEY', '*_SECRET', '*_TOKEN', 'PASSWORD*'].
        
    Returns:
        Dict of validated environment variables.
    """
    validator = EnvironmentValidator(strict_mode=strict_mode)
    validated_vars = validator.validate_all()
    
    if verbose:
        validator.print_env_summary(validated_vars, redact_patterns=redact_patterns)
    
    return validated_vars
