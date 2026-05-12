"""Normalization Module - Data normalization and standardization utilities.

Provides normalization capabilities:
- Data type standardization
- Field name normalization
- Value formatting
- Schema alignment

Author: Platform Team
Version: 2.0.0
"""

import logging
from typing import Any, Dict, List, Optional, Union
import re
from datetime import datetime
from decimal import Decimal
import json

# Configure logging
logger = logging.getLogger(__name__)


class NormalizationConfig:
    """Normalization configuration."""
    
    def __init__(self):
        """Initialize normalization configuration."""
        self.lowercase_keys = True
        self.trim_strings = True
        self.remove_null_values = False
        self.sort_keys = True
        self.normalize_dates = True
        self.normalize_numbers = True


def normalize_data(data: Any, config: Optional[NormalizationConfig] = None) -> Any:
    """Normalize data structure.
    
    Args:
        data: Data to normalize
        config: Normalization configuration
        
    Returns:
        Normalized data
    """
    try:
        if config is None:
            config = NormalizationConfig()
        
        logger.debug("Starting data normalization")
        
        # Handle different data types
        if isinstance(data, dict):
            return _normalize_dict(data, config)
        elif isinstance(data, list):
            return _normalize_list(data, config)
        elif isinstance(data, str):
            return _normalize_string(data, config)
        elif isinstance(data, (int, float, Decimal)):
            return _normalize_number(data, config)
        else:
            return data
            
    except Exception as e:
        logger.error(f"Normalization failed: {str(e)}", exc_info=True)
        raise


def _normalize_dict(data: Dict, config: NormalizationConfig) -> Dict:
    """Normalize dictionary.
    
    Args:
        data: Dictionary to normalize
        config: Normalization configuration
        
    Returns:
        Normalized dictionary
    """
    result = {}
    
    for key, value in data.items():
        # Normalize key
        normalized_key = _normalize_key(key, config)
        
        # Normalize value
        normalized_value = normalize_data(value, config)
        
        # Skip null values if configured
        if config.remove_null_values and normalized_value is None:
            continue
        
        result[normalized_key] = normalized_value
    
    # Sort keys if configured
    if config.sort_keys:
        result = dict(sorted(result.items()))
    
    return result


def _normalize_list(data: List, config: NormalizationConfig) -> List:
    """Normalize list.
    
    Args:
        data: List to normalize
        config: Normalization configuration
        
    Returns:
        Normalized list
    """
    return [normalize_data(item, config) for item in data]


def _normalize_key(key: str, config: NormalizationConfig) -> str:
    """Normalize dictionary key.
    
    Args:
        key: Key to normalize
        config: Normalization configuration
        
    Returns:
        Normalized key
    """
    normalized = key
    
    # Convert to lowercase
    if config.lowercase_keys:
        normalized = normalized.lower()
    
    # Trim whitespace
    if config.trim_strings:
        normalized = normalized.strip()
    
    # Replace special characters with underscores
    normalized = re.sub(r'[^a-z0-9_]', '_', normalized)
    
    # Remove consecutive underscores
    normalized = re.sub(r'_+', '_', normalized)
    
    # Remove leading/trailing underscores
    normalized = normalized.strip('_')
    
    return normalized


def _normalize_string(data: str, config: NormalizationConfig) -> str:
    """Normalize string value.
    
    Args:
        data: String to normalize
        config: Normalization configuration
        
    Returns:
        Normalized string
    """
    normalized = data
    
    # Trim whitespace
    if config.trim_strings:
        normalized = normalized.strip()
    
    # Try to normalize as date
    if config.normalize_dates:
        date_value = _try_parse_date(normalized)
        if date_value:
            return date_value
    
    return normalized


def _normalize_number(data: Union[int, float, Decimal], 
                      config: NormalizationConfig) -> Union[int, float]:
    """Normalize numeric value.
    
    Args:
        data: Number to normalize
        config: Normalization configuration
        
    Returns:
        Normalized number
    """
    if not config.normalize_numbers:
        return data
    
    # Convert Decimal to float
    if isinstance(data, Decimal):
        return float(data)
    
    # Round floats to reasonable precision
    if isinstance(data, float):
        return round(data, 10)
    
    return data


def _try_parse_date(value: str) -> Optional[str]:
    """Try to parse and normalize date string.
    
    Args:
        value: String that might be a date
        
    Returns:
        Normalized ISO date string or None
    """
    try:
        # Common date formats
        formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%Y/%m/%d'
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.isoformat() + 'Z'
            except ValueError:
                continue
        
        return None
        
    except Exception:
        return None


def normalize_schema(data: Any, schema: Dict[str, Any]) -> Any:
    """Normalize data according to schema.
    
    Args:
        data: Data to normalize
        schema: Schema definition
        
    Returns:
        Schema-normalized data
    """
    try:
        if not isinstance(data, dict) or not isinstance(schema, dict):
            return data
        
        result = {}
        
        for field, field_schema in schema.items():
            if field in data:
                value = data[field]
                field_type = field_schema.get('type')
                
                # Type conversion
                if field_type == 'string':
                    result[field] = str(value)
                elif field_type == 'integer':
                    result[field] = int(value)
                elif field_type == 'number':
                    result[field] = float(value)
                elif field_type == 'boolean':
                    result[field] = bool(value)
                elif field_type == 'array':
                    result[field] = list(value) if not isinstance(value, list) else value
                elif field_type == 'object':
                    result[field] = dict(value) if not isinstance(value, dict) else value
                else:
                    result[field] = value
            elif field_schema.get('required', False):
                # Add default value for required fields
                result[field] = field_schema.get('default')
        
        return result
        
    except Exception as e:
        logger.error(f"Schema normalization failed: {str(e)}", exc_info=True)
        raise


def normalize(x: Any) -> Any:
    """Simple normalize function for backward compatibility.
    
    Args:
        x: Data to normalize
        
    Returns:
        Normalized data
    """
    return normalize_data(x)
