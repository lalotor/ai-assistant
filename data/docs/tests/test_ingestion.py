"""Test Suite for Ingestion Module.

Comprehensive test coverage for:
- File source implementations (S3, Local, HTTP)
- File validation and metadata extraction
- Ingestion pipeline and job management
- Error handling and edge cases

Author: Platform Team
Version: 2.0.0
"""

import pytest
import json
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime
from pathlib import Path
import sys
import os

# Add parent directory to path to import src modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ingestion import (
    ingest,
    ingest_file,
    validate_file,
    get_file_source,
    S3FileSource,
    LocalFileSource,
    HTTPFileSource,
    FileSource
)


class TestFileSource:
    """Test cases for FileSource base class."""
    
    def test_base_source_not_implemented(self):
        """Test that base FileSource raises NotImplementedError."""
        source = FileSource()
        
        with pytest.raises(NotImplementedError):
            source.retrieve('some-location')


class TestS3FileSource:
    """Test cases for S3FileSource."""
    
    def test_s3_retrieve_returns_bytes(self):
        """Test that S3 retrieve returns bytes."""
        source = S3FileSource()
        
        result = source.retrieve('s3://bucket/key')
        
        assert isinstance(result, bytes)
        assert len(result) > 0
    
    @patch('src.ingestion.logger')
    def test_s3_retrieve_logs_operation(self, mock_logger):
        """Test that S3 retrieve logs the operation."""
        source = S3FileSource()
        
        source.retrieve('s3://test-bucket/test-key')
        
        mock_logger.info.assert_called_once()
        assert 's3://test-bucket/test-key' in str(mock_logger.info.call_args)
    
    def test_s3_retrieve_returns_valid_json(self):
        """Test that S3 retrieve returns valid JSON data."""
        source = S3FileSource()
        
        result = source.retrieve('s3://bucket/key')
        data = json.loads(result)
        
        assert 'data' in data


class TestLocalFileSource:
    """Test cases for LocalFileSource."""
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data=b'{"test": "data"}')
    def test_local_retrieve_success(self, mock_file, mock_exists):
        """Test successful local file retrieval."""
        mock_exists.return_value = True
        source = LocalFileSource()
        
        result = source.retrieve('/path/to/file.json')
        
        assert isinstance(result, bytes)
        assert result == b'{"test": "data"}'
        mock_file.assert_called_once_with(Path('/path/to/file.json'), 'rb')
    
    @patch('pathlib.Path.exists')
    def test_local_retrieve_file_not_found(self, mock_exists):
        """Test local file retrieval with non-existent file."""
        mock_exists.return_value = False
        source = LocalFileSource()
        
        with pytest.raises(FileNotFoundError) as exc_info:
            source.retrieve('/path/to/missing.json')
        
        assert 'File not found' in str(exc_info.value)
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', side_effect=IOError('Read error'))
    def test_local_retrieve_read_error(self, mock_file, mock_exists):
        """Test local file retrieval with read error."""
        mock_exists.return_value = True
        source = LocalFileSource()
        
        with pytest.raises(IOError):
            source.retrieve('/path/to/file.json')
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test content')
    @patch('src.ingestion.logger')
    def test_local_retrieve_logs_operation(self, mock_logger, mock_file, mock_exists):
        """Test that local retrieve logs the operation."""
        mock_exists.return_value = True
        source = LocalFileSource()
        
        source.retrieve('/path/to/file.json')
        
        mock_logger.info.assert_called_once()


class TestHTTPFileSource:
    """Test cases for HTTPFileSource."""
    
    def test_http_retrieve_returns_bytes(self):
        """Test that HTTP retrieve returns bytes."""
        source = HTTPFileSource()
        
        result = source.retrieve('https://example.com/file.json')
        
        assert isinstance(result, bytes)
        assert len(result) > 0
    
    @patch('src.ingestion.logger')
    def test_http_retrieve_logs_operation(self, mock_logger):
        """Test that HTTP retrieve logs the operation."""
        source = HTTPFileSource()
        
        source.retrieve('https://example.com/file.json')
        
        mock_logger.info.assert_called_once()
        assert 'https://example.com/file.json' in str(mock_logger.info.call_args)


class TestGetFileSource:
    """Test cases for get_file_source function."""
    
    def test_get_s3_source(self):
        """Test getting S3 file source."""
        source = get_file_source('s3://bucket/key')
        
        assert isinstance(source, S3FileSource)
    
    def test_get_http_source(self):
        """Test getting HTTP file source."""
        source = get_file_source('https://example.com/file.json')
        
        assert isinstance(source, HTTPFileSource)
    
    def test_get_https_source(self):
        """Test getting HTTPS file source."""
        source = get_file_source('https://example.com/file.json')
        
        assert isinstance(source, HTTPFileSource)
    
    def test_get_local_source(self):
        """Test getting local file source."""
        source = get_file_source('/path/to/file.json')
        
        assert isinstance(source, LocalFileSource)
    
    def test_get_local_source_relative_path(self):
        """Test getting local file source with relative path."""
        source = get_file_source('data/file.json')
        
        assert isinstance(source, LocalFileSource)


class TestValidateFile:
    """Test cases for validate_file function."""
    
    def test_validate_json_file_success(self):
        """Test successful JSON file validation."""
        content = b'{"name": "John", "age": 30}'
        file_id = 'test-file-123'
        
        result = validate_file(content, file_id)
        
        assert result['file_id'] == file_id
        assert result['format'] == 'json'
        assert result['is_valid'] is True
        assert result['size_bytes'] == len(content)
        assert 'validated_at' in result
    
    def test_validate_json_array(self):
        """Test validation of JSON array."""
        content = b'[{"id": 1}, {"id": 2}, {"id": 3}]'
        file_id = 'test-array'
        
        result = validate_file(content, file_id)
        
        assert result['is_valid'] is True
        assert result['record_count'] == 3
    
    def test_validate_json_object(self):
        """Test validation of single JSON object."""
        content = b'{"id": 1, "data": "test"}'
        file_id = 'test-object'
        
        result = validate_file(content, file_id)
        
        assert result['is_valid'] is True
        assert result['record_count'] == 1
    
    def test_validate_invalid_json(self):
        """Test validation of invalid JSON."""
        content = b'invalid json content'
        file_id = 'test-invalid'
        
        result = validate_file(content, file_id)
        
        assert result['file_id'] == file_id
        assert result['format'] == 'unknown'
        assert result['is_valid'] is False
    
    def test_validate_empty_content(self):
        """Test validation of empty content."""
        content = b''
        file_id = 'test-empty'
        
        result = validate_file(content, file_id)
        
        assert result['is_valid'] is False
        assert result['size_bytes'] == 0
    
    def test_validate_file_metadata_structure(self):
        """Test that validation result has correct metadata structure."""
        content = b'{"test": true}'
        file_id = 'test-metadata'
        
        result = validate_file(content, file_id)
        
        assert 'file_id' in result
        assert 'format' in result
        assert 'size_bytes' in result
        assert 'is_valid' in result
        assert 'validated_at' in result


class TestIngestFile:
    """Test cases for ingest_file function."""
    
    @patch('src.ingestion.process_job')
    @patch('src.ingestion.update_job_status')
    @patch('src.ingestion.get_file_source')
    def test_ingest_file_success(self, mock_get_source, mock_update_status, mock_process):
        """Test successful file ingestion."""
        # Setup mocks
        mock_source = MagicMock()
        mock_source.retrieve.return_value = b'{"data": "test"}'
        mock_get_source.return_value = mock_source
        
        job = {
            'job_id': 'job-123',
            'file_id': 'file-456',
            'location': 's3://bucket/key'
        }
        
        result = ingest_file(job)
        
        assert result == 'job-123'
        assert mock_update_status.call_count >= 2
        mock_process.assert_called_once_with('job-123')
    
    @patch('src.ingestion.update_job_status')
    @patch('src.ingestion.get_file_source')
    def test_ingest_file_validation_failure(self, mock_get_source, mock_update_status):
        """Test ingestion with file validation failure."""
        mock_source = MagicMock()
        mock_source.retrieve.return_value = b'invalid content'
        mock_get_source.return_value = mock_source
        
        job = {
            'job_id': 'job-123',
            'file_id': 'file-456',
            'location': 's3://bucket/key'
        }
        
        with pytest.raises(ValueError) as exc_info:
            ingest_file(job)
        
        assert 'File validation failed' in str(exc_info.value)
        # Verify failed status was set
        failed_call = [call for call in mock_update_status.call_args_list 
                      if call[0][1] == 'failed']
        assert len(failed_call) > 0
    
    @patch('src.ingestion.update_job_status')
    @patch('src.ingestion.get_file_source')
    def test_ingest_file_retrieval_error(self, mock_get_source, mock_update_status):
        """Test ingestion with file retrieval error."""
        mock_source = MagicMock()
        mock_source.retrieve.side_effect = Exception('Retrieval failed')
        mock_get_source.return_value = mock_source
        
        job = {
            'job_id': 'job-123',
            'file_id': 'file-456',
            'location': 's3://bucket/key'
        }
        
        with pytest.raises(Exception) as exc_info:
            ingest_file(job)
        
        assert 'Retrieval failed' in str(exc_info.value)
    
    @patch('src.ingestion.process_job')
    @patch('src.ingestion.update_job_status')
    @patch('src.ingestion.get_file_source')
    @patch('src.ingestion.logger')
    def test_ingest_file_logs_operations(self, mock_logger, mock_get_source, 
                                         mock_update_status, mock_process):
        """Test that ingestion logs operations."""
        mock_source = MagicMock()
        mock_source.retrieve.return_value = b'{"data": "test"}'
        mock_get_source.return_value = mock_source
        
        job = {
            'job_id': 'job-123',
            'file_id': 'file-456',
            'location': 's3://bucket/key'
        }
        
        ingest_file(job)
        
        assert mock_logger.info.call_count >= 2


class TestIngest:
    """Test cases for ingest function."""
    
    @patch('src.ingestion.ingest_file')
    @patch('src.ingestion.store_job')
    def test_ingest_creates_job(self, mock_store, mock_ingest_file):
        """Test that ingest creates and stores a job."""
        mock_ingest_file.return_value = 'job-123'
        
        result = ingest('file-456', location='s3://bucket/key')
        
        assert mock_store.called
        assert mock_ingest_file.called
        assert isinstance(result, str)
    
    @patch('src.ingestion.ingest_file')
    @patch('src.ingestion.store_job')
    def test_ingest_with_options(self, mock_store, mock_ingest_file):
        """Test ingest with custom options."""
        mock_ingest_file.return_value = 'job-123'
        options = {'priority': 'high', 'retry': 3}
        
        result = ingest('file-456', options=options)
        
        # Verify job was stored with options
        stored_job = mock_store.call_args[0][0]
        assert stored_job['options'] == options
    
    @patch('src.ingestion.ingest_file')
    @patch('src.ingestion.store_job')
    def test_ingest_default_location(self, mock_store, mock_ingest_file):
        """Test ingest uses default location when not provided."""
        mock_ingest_file.return_value = 'job-123'
        
        ingest('file-456')
        
        stored_job = mock_store.call_args[0][0]
        assert 's3://default-bucket/file-456' in stored_job['location']
    
    @patch('src.ingestion.ingest_file')
    @patch('src.ingestion.store_job')
    def test_ingest_generates_unique_job_id(self, mock_store, mock_ingest_file):
        """Test that ingest generates unique job IDs."""
        mock_ingest_file.return_value = 'job-123'
        
        ingest('file-1')
        job_id_1 = mock_store.call_args[0][0]['job_id']
        
        ingest('file-2')
        job_id_2 = mock_store.call_args[0][0]['job_id']
        
        assert job_id_1 != job_id_2
    
    @patch('src.ingestion.ingest_file')
    @patch('src.ingestion.store_job')
    def test_ingest_job_structure(self, mock_store, mock_ingest_file):
        """Test that created job has correct structure."""
        mock_ingest_file.return_value = 'job-123'
        
        ingest('file-456', location='s3://bucket/key')
        
        stored_job = mock_store.call_args[0][0]
        assert 'job_id' in stored_job
        assert 'file_id' in stored_job
        assert 'location' in stored_job
        assert 'status' in stored_job
        assert 'submitted_at' in stored_job
        assert stored_job['status'] == 'submitted'


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_validate_large_json_file(self):
        """Test validation of large JSON file."""
        large_data = [{"id": i, "data": f"item_{i}"} for i in range(10000)]
        content = json.dumps(large_data).encode('utf-8')
        
        result = validate_file(content, 'large-file')
        
        assert result['is_valid'] is True
        assert result['record_count'] == 10000
    
    def test_validate_special_characters(self):
        """Test validation with special characters."""
        content = b'{"text": "\u00e9\u00e0\u00fc"}'
        
        result = validate_file(content, 'special-chars')
        
        assert result['is_valid'] is True
    
    @patch('src.ingestion.get_file_source')
    def test_ingest_with_unicode_file_id(self, mock_get_source):
        """Test ingestion with unicode characters in file ID."""
        mock_source = MagicMock()
        mock_source.retrieve.return_value = b'{"data": "test"}'
        mock_get_source.return_value = mock_source
        
        file_id = 'file_测试_123'
        
        with patch('src.ingestion.store_job'), \
             patch('src.ingestion.ingest_file') as mock_ingest:
            mock_ingest.return_value = 'job-123'
            result = ingest(file_id)
            
            assert isinstance(result, str)
