"""Ingestion Module - File ingestion and validation pipeline.

Provides file ingestion capabilities:
- Multi-source file retrieval (S3, local, HTTP)
- File validation and format detection
- Metadata extraction
- Async job creation and tracking

Author: Platform Team
Version: 2.0.0
"""

import logging
import uuid
import json
from typing import Dict, Any, Optional
from datetime import datetime
import os
from pathlib import Path

from storage import store_job, update_job_status
from processor import process_job

# Configure logging
logger = logging.getLogger(__name__)


class FileSource:
    """Base class for file sources."""
    
    def retrieve(self, location: str) -> bytes:
        """Retrieve file content from source.
        
        Args:
            location: File location identifier
            
        Returns:
            File content as bytes
        """
        raise NotImplementedError("Subclasses must implement retrieve method")


class S3FileSource(FileSource):
    """S3 file source implementation."""
    
    def retrieve(self, location: str) -> bytes:
        """Retrieve file from S3.
        
        Args:
            location: S3 URI (s3://bucket/key)
            
        Returns:
            File content
        """
        try:
            logger.info(f"Retrieving file from S3: {location}")
            # TODO: Implement actual S3 retrieval using boto3
            # For now, return mock data
            return b'{"data": "sample"}'
            
        except Exception as e:
            logger.error(f"S3 retrieval failed: {str(e)}", exc_info=True)
            raise


class LocalFileSource(FileSource):
    """Local filesystem source implementation."""
    
    def retrieve(self, location: str) -> bytes:
        """Retrieve file from local filesystem.
        
        Args:
            location: File path
            
        Returns:
            File content
        """
        try:
            logger.info(f"Retrieving file from local filesystem: {location}")
            
            file_path = Path(location)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {location}")
            
            with open(file_path, 'rb') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Local file retrieval failed: {str(e)}", exc_info=True)
            raise


class HTTPFileSource(FileSource):
    """HTTP file source implementation."""
    
    def retrieve(self, location: str) -> bytes:
        """Retrieve file from HTTP endpoint.
        
        Args:
            location: HTTP URL
            
        Returns:
            File content
        """
        try:
            logger.info(f"Retrieving file from HTTP: {location}")
            # TODO: Implement actual HTTP retrieval using requests
            # For now, return mock data
            return b'{"data": "sample"}'
            
        except Exception as e:
            logger.error(f"HTTP retrieval failed: {str(e)}", exc_info=True)
            raise


def get_file_source(location: str) -> FileSource:
    """Get appropriate file source based on location.
    
    Args:
        location: File location identifier
        
    Returns:
        FileSource instance
    """
    if location.startswith('s3://'):
        return S3FileSource()
    elif location.startswith('http://') or location.startswith('https://'):
        return HTTPFileSource()
    else:
        return LocalFileSource()


def validate_file(content: bytes, file_id: str) -> Dict[str, Any]:
    """Validate file content and extract metadata.
    
    Args:
        content: File content
        file_id: File identifier
        
    Returns:
        Validation result with metadata
    """
    try:
        # Detect file format
        try:
            data = json.loads(content)
            file_format = 'json'
            is_valid = True
        except json.JSONDecodeError:
            file_format = 'unknown'
            is_valid = False
        
        # Extract metadata
        metadata = {
            'file_id': file_id,
            'format': file_format,
            'size_bytes': len(content),
            'is_valid': is_valid,
            'validated_at': datetime.utcnow().isoformat() + 'Z'
        }
        
        if is_valid:
            metadata['record_count'] = len(data) if isinstance(data, list) else 1
        
        return metadata
        
    except Exception as e:
        logger.error(f"File validation failed: {str(e)}", exc_info=True)
        return {
            'file_id': file_id,
            'is_valid': False,
            'error': str(e)
        }


def ingest_file(job: Dict[str, Any]) -> str:
    """Ingest file and create processing job.
    
    Args:
        job: Job details containing file_id, location, and options
        
    Returns:
        Job ID
        
    Raises:
        ValueError: If job data is invalid
        FileNotFoundError: If file cannot be retrieved
    """
    try:
        job_id = job.get('job_id')
        file_id = job.get('file_id')
        location = job.get('location')
        
        logger.info(f"Starting ingestion for job {job_id}, file {file_id}")
        
        # Update job status to ingesting
        update_job_status(job_id, 'ingesting', {
            'started_at': datetime.utcnow().isoformat() + 'Z'
        })
        
        # Retrieve file
        file_source = get_file_source(location)
        content = file_source.retrieve(location)
        
        # Validate file
        validation_result = validate_file(content, file_id)
        
        if not validation_result.get('is_valid'):
            error_msg = f"File validation failed: {validation_result.get('error', 'Unknown error')}"
            logger.error(error_msg)
            update_job_status(job_id, 'failed', {
                'error': error_msg,
                'failed_at': datetime.utcnow().isoformat() + 'Z'
            })
            raise ValueError(error_msg)
        
        # Update job with file metadata
        update_job_status(job_id, 'ingested', {
            'ingested_at': datetime.utcnow().isoformat() + 'Z',
            'file_metadata': validation_result,
            'content': content.decode('utf-8')
        })
        
        # Trigger processing
        process_job(job_id)
        
        logger.info(f"Ingestion completed for job {job_id}")
        
        return job_id
        
    except Exception as e:
        logger.error(f"Ingestion failed for job {job_id}: {str(e)}", exc_info=True)
        update_job_status(job_id, 'failed', {
            'error': str(e),
            'failed_at': datetime.utcnow().isoformat() + 'Z'
        })
        raise


def ingest(file_id: str, location: str = None, 
          options: Optional[Dict[str, Any]] = None) -> str:
    """Simple ingestion function for backward compatibility.
    
    Args:
        file_id: File identifier
        location: File location (optional)
        options: Ingestion options (optional)
        
    Returns:
        Job ID
    """
    job_id = str(uuid.uuid4())
    
    job = {
        'job_id': job_id,
        'file_id': file_id,
        'location': location or f"s3://default-bucket/{file_id}",
        'status': 'submitted',
        'submitted_at': datetime.utcnow().isoformat() + 'Z',
        'options': options or {}
    }
    
    store_job(job)
    
    return ingest_file(job)
