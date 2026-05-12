"""Comparator Module - Advanced comparison engine for structured data.

Provides intelligent comparison capabilities:
- Structural comparison with deep diff analysis
- Semantic similarity detection
- Field-level change tracking
- Configurable comparison strategies

Author: Platform Team
Version: 2.0.0
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from difflib import SequenceMatcher

from utils.diff_utils import calculate_diff, generate_patch
from utils.normalization import normalize_data

# Configure logging
logger = logging.getLogger(__name__)


class ComparisonStrategy:
    """Base class for comparison strategies."""
    
    def compare(self, source: Any, target: Any) -> Dict[str, Any]:
        """Compare two data structures.
        
        Args:
            source: Source data
            target: Target data
            
        Returns:
            Comparison result with match status and differences
        """
        raise NotImplementedError("Subclasses must implement compare method")


class StructuralComparison(ComparisonStrategy):
    """Structural comparison strategy."""
    
    def compare(self, source: Any, target: Any) -> Dict[str, Any]:
        """Perform structural comparison.
        
        Args:
            source: Source data structure
            target: Target data structure
            
        Returns:
            Detailed comparison result
        """
        try:
            # Calculate structural differences
            differences = calculate_diff(source, target)
            
            # Determine match status
            is_match = len(differences) == 0
            
            # Calculate similarity score
            similarity = self._calculate_similarity(source, target)
            
            return {
                'match': is_match,
                'similarity_score': similarity,
                'differences': differences,
                'total_changes': len(differences),
                'comparison_type': 'structural'
            }
            
        except Exception as e:
            logger.error(f"Structural comparison failed: {str(e)}", exc_info=True)
            raise
    
    def _calculate_similarity(self, source: Any, target: Any) -> float:
        """Calculate similarity score between two structures.
        
        Args:
            source: Source data
            target: Target data
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        try:
            source_str = json.dumps(source, sort_keys=True)
            target_str = json.dumps(target, sort_keys=True)
            
            matcher = SequenceMatcher(None, source_str, target_str)
            return matcher.ratio()
            
        except Exception:
            return 0.0


class SemanticComparison(ComparisonStrategy):
    """Semantic comparison strategy."""
    
    def compare(self, source: Any, target: Any) -> Dict[str, Any]:
        """Perform semantic comparison.
        
        Args:
            source: Source data
            target: Target data
            
        Returns:
            Semantic comparison result
        """
        try:
            # Normalize data for semantic comparison
            normalized_source = normalize_data(source)
            normalized_target = normalize_data(target)
            
            # Compare normalized structures
            differences = calculate_diff(normalized_source, normalized_target)
            
            is_match = len(differences) == 0
            
            return {
                'match': is_match,
                'differences': differences,
                'total_changes': len(differences),
                'comparison_type': 'semantic'
            }
            
        except Exception as e:
            logger.error(f"Semantic comparison failed: {str(e)}", exc_info=True)
            raise


def compare(source: Any, target: Any, strategy: str = 'structural', 
            options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compare two data structures using specified strategy.
    
    Args:
        source: Source data structure
        target: Target data structure
        strategy: Comparison strategy ('structural' or 'semantic')
        options: Additional comparison options
        
    Returns:
        Comparison result with match status, differences, and metadata
        
    Raises:
        ValueError: If invalid strategy specified
    """
    try:
        logger.info(f"Starting comparison with strategy: {strategy}")
        
        # Select comparison strategy
        if strategy == 'structural':
            comparator = StructuralComparison()
        elif strategy == 'semantic':
            comparator = SemanticComparison()
        else:
            raise ValueError(f"Invalid comparison strategy: {strategy}")
        
        # Perform comparison
        start_time = datetime.utcnow()
        result = comparator.compare(source, target)
        end_time = datetime.utcnow()
        
        # Add metadata
        result['metadata'] = {
            'strategy': strategy,
            'started_at': start_time.isoformat() + 'Z',
            'completed_at': end_time.isoformat() + 'Z',
            'duration_ms': int((end_time - start_time).total_seconds() * 1000)
        }
        
        # Add options if provided
        if options:
            result['options'] = options
        
        logger.info(f"Comparison completed: match={result['match']}, "
                   f"changes={result.get('total_changes', 0)}")
        
        return result
        
    except Exception as e:
        logger.error(f"Comparison failed: {str(e)}", exc_info=True)
        raise


def compare_batch(comparisons: List[Dict[str, Any]], 
                  strategy: str = 'structural') -> List[Dict[str, Any]]:
    """Perform batch comparison of multiple data pairs.
    
    Args:
        comparisons: List of comparison requests, each with 'source' and 'target'
        strategy: Comparison strategy to use
        
    Returns:
        List of comparison results
    """
    results = []
    
    for idx, comparison in enumerate(comparisons):
        try:
            source = comparison.get('source')
            target = comparison.get('target')
            options = comparison.get('options')
            
            result = compare(source, target, strategy, options)
            result['index'] = idx
            results.append(result)
            
        except Exception as e:
            logger.error(f"Batch comparison failed for index {idx}: {str(e)}")
            results.append({
                'index': idx,
                'error': str(e),
                'match': False
            })
    
    return results
