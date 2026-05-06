"""Diff Utils Module - Utilities for calculating differences between data structures.

Provides diff calculation capabilities:
- Deep object comparison
- Field-level change detection
- Patch generation
- Change type classification

Author: Platform Team
Version: 2.0.0
"""

import logging
from typing import Any, List, Dict, Optional, Union
import json
from copy import deepcopy

# Configure logging
logger = logging.getLogger(__name__)


class ChangeType:
    """Change type constants."""
    ADDED = 'added'
    REMOVED = 'removed'
    MODIFIED = 'modified'
    UNCHANGED = 'unchanged'


def calculate_diff(source: Any, target: Any, path: str = '') -> List[Dict[str, Any]]:
    """Calculate differences between two data structures.
    
    Args:
        source: Source data structure
        target: Target data structure
        path: Current path in the structure (for nested objects)
        
    Returns:
        List of differences with path, type, and values
    """
    differences = []
    
    try:
        # Handle None cases
        if source is None and target is None:
            return differences
        
        if source is None:
            differences.append({
                'path': path or '/',
                'type': ChangeType.ADDED,
                'old_value': None,
                'new_value': target
            })
            return differences
        
        if target is None:
            differences.append({
                'path': path or '/',
                'type': ChangeType.REMOVED,
                'old_value': source,
                'new_value': None
            })
            return differences
        
        # Handle type mismatch
        if type(source) != type(target):
            differences.append({
                'path': path or '/',
                'type': ChangeType.MODIFIED,
                'old_value': source,
                'new_value': target,
                'old_type': type(source).__name__,
                'new_type': type(target).__name__
            })
            return differences
        
        # Handle dictionaries
        if isinstance(source, dict):
            differences.extend(_diff_dict(source, target, path))
        
        # Handle lists
        elif isinstance(source, list):
            differences.extend(_diff_list(source, target, path))
        
        # Handle primitive types
        else:
            if source != target:
                differences.append({
                    'path': path or '/',
                    'type': ChangeType.MODIFIED,
                    'old_value': source,
                    'new_value': target
                })
        
        return differences
        
    except Exception as e:
        logger.error(f"Error calculating diff: {str(e)}", exc_info=True)
        raise


def _diff_dict(source: Dict, target: Dict, path: str) -> List[Dict[str, Any]]:
    """Calculate differences between two dictionaries.
    
    Args:
        source: Source dictionary
        target: Target dictionary
        path: Current path
        
    Returns:
        List of differences
    """
    differences = []
    
    # Get all keys
    all_keys = set(source.keys()) | set(target.keys())
    
    for key in all_keys:
        current_path = f"{path}.{key}" if path else key
        
        # Key removed
        if key in source and key not in target:
            differences.append({
                'path': current_path,
                'type': ChangeType.REMOVED,
                'old_value': source[key],
                'new_value': None
            })
        
        # Key added
        elif key not in source and key in target:
            differences.append({
                'path': current_path,
                'type': ChangeType.ADDED,
                'old_value': None,
                'new_value': target[key]
            })
        
        # Key exists in both
        else:
            differences.extend(calculate_diff(source[key], target[key], current_path))
    
    return differences


def _diff_list(source: List, target: List, path: str) -> List[Dict[str, Any]]:
    """Calculate differences between two lists.
    
    Args:
        source: Source list
        target: Target list
        path: Current path
        
    Returns:
        List of differences
    """
    differences = []
    
    max_len = max(len(source), len(target))
    
    for i in range(max_len):
        current_path = f"{path}[{i}]"
        
        # Item removed
        if i < len(source) and i >= len(target):
            differences.append({
                'path': current_path,
                'type': ChangeType.REMOVED,
                'old_value': source[i],
                'new_value': None
            })
        
        # Item added
        elif i >= len(source) and i < len(target):
            differences.append({
                'path': current_path,
                'type': ChangeType.ADDED,
                'old_value': None,
                'new_value': target[i]
            })
        
        # Item exists in both
        else:
            differences.extend(calculate_diff(source[i], target[i], current_path))
    
    return differences


def generate_patch(differences: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate patch from differences.
    
    Args:
        differences: List of differences
        
    Returns:
        Patch object with operations
    """
    try:
        operations = []
        
        for diff in differences:
            operation = {
                'op': _get_patch_operation(diff['type']),
                'path': diff['path'],
                'value': diff.get('new_value')
            }
            
            # Add old value for replace operations
            if diff['type'] == ChangeType.MODIFIED:
                operation['old_value'] = diff.get('old_value')
            
            operations.append(operation)
        
        return {
            'operations': operations,
            'total_operations': len(operations)
        }
        
    except Exception as e:
        logger.error(f"Error generating patch: {str(e)}", exc_info=True)
        raise


def _get_patch_operation(change_type: str) -> str:
    """Get patch operation from change type.
    
    Args:
        change_type: Change type
        
    Returns:
        Patch operation
    """
    mapping = {
        ChangeType.ADDED: 'add',
        ChangeType.REMOVED: 'remove',
        ChangeType.MODIFIED: 'replace'
    }
    return mapping.get(change_type, 'unknown')


def apply_patch(data: Any, patch: Dict[str, Any]) -> Any:
    """Apply patch to data structure.
    
    Args:
        data: Original data
        patch: Patch to apply
        
    Returns:
        Patched data
    """
    try:
        result = deepcopy(data)
        
        for operation in patch.get('operations', []):
            op = operation.get('op')
            path = operation.get('path')
            value = operation.get('value')
            
            if op == 'add' or op == 'replace':
                _set_value_at_path(result, path, value)
            elif op == 'remove':
                _remove_value_at_path(result, path)
        
        return result
        
    except Exception as e:
        logger.error(f"Error applying patch: {str(e)}", exc_info=True)
        raise


def _set_value_at_path(data: Any, path: str, value: Any) -> None:
    """Set value at specified path.
    
    Args:
        data: Data structure
        path: Path to set
        value: Value to set
    """
    # Simple implementation - can be enhanced for complex paths
    parts = path.split('.')
    current = data
    
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    
    current[parts[-1]] = value


def _remove_value_at_path(data: Any, path: str) -> None:
    """Remove value at specified path.
    
    Args:
        data: Data structure
        path: Path to remove
    """
    # Simple implementation - can be enhanced for complex paths
    parts = path.split('.')
    current = data
    
    for part in parts[:-1]:
        if part not in current:
            return
        current = current[part]
    
    if parts[-1] in current:
        del current[parts[-1]]


def diff(a: Any, b: Any) -> List[Dict[str, Any]]:
    """Simple diff function for backward compatibility.
    
    Args:
        a: First data structure
        b: Second data structure
        
    Returns:
        List of differences
    """
    return calculate_diff(a, b)
