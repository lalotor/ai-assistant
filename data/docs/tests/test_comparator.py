"""Test Suite for Comparator Module.

Comprehensive test coverage for:
- Structural comparison strategy
- Semantic comparison strategy
- Batch comparison operations
- Error handling and edge cases

Author: Platform Team
Version: 2.0.0
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.comparator import (
    compare,
    compare_batch,
    StructuralComparison,
    SemanticComparison,
    ComparisonStrategy
)


class TestStructuralComparison:
    """Test cases for StructuralComparison strategy."""
    
    def test_identical_structures_match(self):
        """Test that identical structures return a match."""
        source = {"name": "John", "age": 30, "city": "NYC"}
        target = {"name": "John", "age": 30, "city": "NYC"}
        
        comparator = StructuralComparison()
        result = comparator.compare(source, target)
        
        assert result['match'] is True
        assert result['similarity_score'] == 1.0
        assert result['total_changes'] == 0
        assert result['comparison_type'] == 'structural'
    
    def test_different_structures_no_match(self):
        """Test that different structures return no match."""
        source = {"name": "John", "age": 30}
        target = {"name": "Jane", "age": 25}
        
        comparator = StructuralComparison()
        result = comparator.compare(source, target)
        
        assert result['match'] is False
        assert result['total_changes'] > 0
        assert 0.0 <= result['similarity_score'] <= 1.0
    
    def test_nested_structures_comparison(self):
        """Test comparison of nested data structures."""
        source = {
            "user": {"name": "John", "address": {"city": "NYC"}},
            "items": [1, 2, 3]
        }
        target = {
            "user": {"name": "John", "address": {"city": "LA"}},
            "items": [1, 2, 3]
        }
        
        comparator = StructuralComparison()
        result = comparator.compare(source, target)
        
        assert result['match'] is False
        assert result['total_changes'] > 0
    
    def test_similarity_score_calculation(self):
        """Test similarity score calculation accuracy."""
        source = {"a": 1, "b": 2, "c": 3}
        target = {"a": 1, "b": 2, "c": 4}
        
        comparator = StructuralComparison()
        result = comparator.compare(source, target)
        
        assert 0.5 < result['similarity_score'] < 1.0
    
    @patch('src.comparator.calculate_diff')
    def test_comparison_with_diff_calculation_error(self, mock_diff):
        """Test error handling when diff calculation fails."""
        mock_diff.side_effect = Exception("Diff calculation error")
        
        source = {"key": "value"}
        target = {"key": "other"}
        
        comparator = StructuralComparison()
        
        with pytest.raises(Exception) as exc_info:
            comparator.compare(source, target)
        
        assert "Diff calculation error" in str(exc_info.value)


class TestSemanticComparison:
    """Test cases for SemanticComparison strategy."""
    
    @patch('src.comparator.normalize_data')
    @patch('src.comparator.calculate_diff')
    def test_semantic_comparison_with_normalization(self, mock_diff, mock_normalize):
        """Test semantic comparison applies normalization."""
        source = {"NAME": "John", "Age": "30"}
        target = {"name": "john", "age": 30}
        
        mock_normalize.side_effect = lambda x: x
        mock_diff.return_value = []
        
        comparator = SemanticComparison()
        result = comparator.compare(source, target)
        
        assert mock_normalize.call_count == 2
        assert result['match'] is True
        assert result['comparison_type'] == 'semantic'
    
    @patch('src.comparator.normalize_data')
    @patch('src.comparator.calculate_diff')
    def test_semantic_comparison_detects_differences(self, mock_diff, mock_normalize):
        """Test semantic comparison detects differences after normalization."""
        source = {"name": "John"}
        target = {"name": "Jane"}
        
        mock_normalize.side_effect = lambda x: x
        mock_diff.return_value = [{'field': 'name', 'old': 'John', 'new': 'Jane'}]
        
        comparator = SemanticComparison()
        result = comparator.compare(source, target)
        
        assert result['match'] is False
        assert result['total_changes'] == 1
    
    @patch('src.comparator.normalize_data')
    def test_semantic_comparison_error_handling(self, mock_normalize):
        """Test error handling in semantic comparison."""
        mock_normalize.side_effect = Exception("Normalization error")
        
        source = {"key": "value"}
        target = {"key": "other"}
        
        comparator = SemanticComparison()
        
        with pytest.raises(Exception) as exc_info:
            comparator.compare(source, target)
        
        assert "Normalization error" in str(exc_info.value)


class TestCompareFunction:
    """Test cases for main compare function."""
    
    @patch('src.comparator.StructuralComparison')
    def test_compare_with_structural_strategy(self, mock_structural):
        """Test compare function with structural strategy."""
        mock_instance = MagicMock()
        mock_instance.compare.return_value = {
            'match': True,
            'total_changes': 0
        }
        mock_structural.return_value = mock_instance
        
        source = {"key": "value"}
        target = {"key": "value"}
        
        result = compare(source, target, strategy='structural')
        
        assert 'metadata' in result
        assert result['metadata']['strategy'] == 'structural'
        assert 'started_at' in result['metadata']
        assert 'completed_at' in result['metadata']
        assert 'duration_ms' in result['metadata']
    
    @patch('src.comparator.SemanticComparison')
    def test_compare_with_semantic_strategy(self, mock_semantic):
        """Test compare function with semantic strategy."""
        mock_instance = MagicMock()
        mock_instance.compare.return_value = {
            'match': True,
            'total_changes': 0
        }
        mock_semantic.return_value = mock_instance
        
        source = {"key": "value"}
        target = {"key": "value"}
        
        result = compare(source, target, strategy='semantic')
        
        assert result['metadata']['strategy'] == 'semantic'
    
    def test_compare_with_invalid_strategy(self):
        """Test error handling for invalid strategy."""
        source = {"key": "value"}
        target = {"key": "value"}
        
        with pytest.raises(ValueError) as exc_info:
            compare(source, target, strategy='invalid')
        
        assert "Invalid comparison strategy" in str(exc_info.value)
    
    @patch('src.comparator.StructuralComparison')
    def test_compare_with_options(self, mock_structural):
        """Test compare function includes options in result."""
        mock_instance = MagicMock()
        mock_instance.compare.return_value = {
            'match': True,
            'total_changes': 0
        }
        mock_structural.return_value = mock_instance
        
        source = {"key": "value"}
        target = {"key": "value"}
        options = {'ignore_case': True, 'threshold': 0.8}
        
        result = compare(source, target, options=options)
        
        assert 'options' in result
        assert result['options'] == options
    
    @patch('src.comparator.StructuralComparison')
    def test_compare_logs_results(self, mock_structural):
        """Test that compare function logs comparison results."""
        mock_instance = MagicMock()
        mock_instance.compare.return_value = {
            'match': False,
            'total_changes': 3
        }
        mock_structural.return_value = mock_instance
        
        source = {"key": "value1"}
        target = {"key": "value2"}
        
        with patch('src.comparator.logger') as mock_logger:
            result = compare(source, target)
            
            assert mock_logger.info.called
            assert result['match'] is False


class TestCompareBatch:
    """Test cases for batch comparison operations."""
    
    @patch('src.comparator.compare')
    def test_batch_comparison_success(self, mock_compare):
        """Test successful batch comparison."""
        mock_compare.side_effect = [
            {'match': True, 'total_changes': 0},
            {'match': False, 'total_changes': 2}
        ]
        
        comparisons = [
            {'source': {'a': 1}, 'target': {'a': 1}},
            {'source': {'a': 1}, 'target': {'a': 2}}
        ]
        
        results = compare_batch(comparisons)
        
        assert len(results) == 2
        assert results[0]['index'] == 0
        assert results[0]['match'] is True
        assert results[1]['index'] == 1
        assert results[1]['match'] is False
    
    @patch('src.comparator.compare')
    def test_batch_comparison_with_options(self, mock_compare):
        """Test batch comparison passes options correctly."""
        mock_compare.return_value = {'match': True, 'total_changes': 0}
        
        comparisons = [
            {
                'source': {'a': 1},
                'target': {'a': 1},
                'options': {'threshold': 0.9}
            }
        ]
        
        results = compare_batch(comparisons, strategy='semantic')
        
        assert len(results) == 1
        mock_compare.assert_called_once()
    
    @patch('src.comparator.compare')
    def test_batch_comparison_error_handling(self, mock_compare):
        """Test batch comparison handles individual comparison errors."""
        mock_compare.side_effect = [
            {'match': True, 'total_changes': 0},
            Exception("Comparison failed")
        ]
        
        comparisons = [
            {'source': {'a': 1}, 'target': {'a': 1}},
            {'source': {'a': 1}, 'target': {'a': 2}}
        ]
        
        results = compare_batch(comparisons)
        
        assert len(results) == 2
        assert results[0]['match'] is True
        assert results[1]['match'] is False
        assert 'error' in results[1]
        assert results[1]['index'] == 1
    
    @patch('src.comparator.compare')
    def test_batch_comparison_empty_list(self, mock_compare):
        """Test batch comparison with empty list."""
        comparisons = []
        
        results = compare_batch(comparisons)
        
        assert len(results) == 0
        mock_compare.assert_not_called()


class TestComparisonStrategy:
    """Test cases for ComparisonStrategy base class."""
    
    def test_base_strategy_not_implemented(self):
        """Test that base strategy raises NotImplementedError."""
        strategy = ComparisonStrategy()
        
        with pytest.raises(NotImplementedError):
            strategy.compare({}, {})


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_compare_empty_structures(self):
        """Test comparison of empty structures."""
        source = {}
        target = {}
        
        result = compare(source, target)
        
        assert result['match'] is True
        assert result['total_changes'] == 0
    
    def test_compare_none_values(self):
        """Test comparison with None values."""
        source = {'key': None}
        target = {'key': None}
        
        result = compare(source, target)
        
        assert result['match'] is True
    
    def test_compare_large_structures(self):
        """Test comparison of large data structures."""
        source = {f'key_{i}': i for i in range(1000)}
        target = {f'key_{i}': i for i in range(1000)}
        
        result = compare(source, target)
        
        assert result['match'] is True
        assert 'duration_ms' in result['metadata']
    
    def test_compare_mixed_types(self):
        """Test comparison with mixed data types."""
        source = {
            'string': 'text',
            'number': 42,
            'float': 3.14,
            'boolean': True,
            'list': [1, 2, 3],
            'nested': {'a': 1}
        }
        target = source.copy()
        
        result = compare(source, target)
        
        assert result['match'] is True
