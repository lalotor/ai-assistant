"""Storage Module - Data persistence and retrieval layer.

Provides storage capabilities:
- Job data persistence
- Result storage
- Query and retrieval operations
- In-memory and persistent storage backends

Author: Platform Team
Version: 2.0.0
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from pathlib import Path
import threading

# Configure logging
logger = logging.getLogger(__name__)

# In-memory storage (for demo purposes)
_jobs_store: Dict[str, Dict[str, Any]] = {}
_results_store: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


class StorageBackend:
    """Base class for storage backends."""
    
    def save(self, key: str, data: Dict[str, Any]) -> None:
        """Save data.
        
        Args:
            key: Data key
            data: Data to save
        """
        raise NotImplementedError("Subclasses must implement save method")
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data.
        
        Args:
            key: Data key
            
        Returns:
            Retrieved data or None
        """
        raise NotImplementedError("Subclasses must implement get method")
    
    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List data with optional filters.
        
        Args:
            filters: Query filters
            
        Returns:
            List of matching data
        """
        raise NotImplementedError("Subclasses must implement list method")
    
    def delete(self, key: str) -> bool:
        """Delete data.
        
        Args:
            key: Data key
            
        Returns:
            True if deleted, False if not found
        """
        raise NotImplementedError("Subclasses must implement delete method")


class InMemoryStorage(StorageBackend):
    """In-memory storage implementation."""
    
    def __init__(self):
        """Initialize in-memory storage."""
        self.data: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
    
    def save(self, key: str, data: Dict[str, Any]) -> None:
        """Save data to memory."""
        with self.lock:
            self.data[key] = data.copy()
            logger.debug(f"Saved data for key: {key}")
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from memory."""
        with self.lock:
            return self.data.get(key)
    
    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List data with optional filters."""
        with self.lock:
            items = list(self.data.values())
            
            if filters:
                filtered_items = []
                for item in items:
                    match = True
                    for key, value in filters.items():
                        if item.get(key) != value:
                            match = False
                            break
                    if match:
                        filtered_items.append(item)
                return filtered_items
            
            return items
    
    def delete(self, key: str) -> bool:
        """Delete data from memory."""
        with self.lock:
            if key in self.data:
                del self.data[key]
                logger.debug(f"Deleted data for key: {key}")
                return True
            return False


class FileStorage(StorageBackend):
    """File-based storage implementation."""
    
    def __init__(self, base_path: str = './data/storage'):
        """Initialize file storage.
        
        Args:
            base_path: Base directory for storage
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
    
    def _get_file_path(self, key: str) -> Path:
        """Get file path for key."""
        return self.base_path / f"{key}.json"
    
    def save(self, key: str, data: Dict[str, Any]) -> None:
        """Save data to file."""
        with self.lock:
            file_path = self._get_file_path(key)
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved data to file: {file_path}")
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve data from file."""
        with self.lock:
            file_path = self._get_file_path(key)
            if file_path.exists():
                with open(file_path, 'r') as f:
                    return json.load(f)
            return None
    
    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List data from files."""
        with self.lock:
            items = []
            for file_path in self.base_path.glob('*.json'):
                with open(file_path, 'r') as f:
                    item = json.load(f)
                    items.append(item)
            
            if filters:
                filtered_items = []
                for item in items:
                    match = True
                    for key, value in filters.items():
                        if item.get(key) != value:
                            match = False
                            break
                    if match:
                        filtered_items.append(item)
                return filtered_items
            
            return items
    
    def delete(self, key: str) -> bool:
        """Delete data file."""
        with self.lock:
            file_path = self._get_file_path(key)
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Deleted file: {file_path}")
                return True
            return False


# Global storage instances
_job_storage = InMemoryStorage()
_result_storage = InMemoryStorage()


def store_job(job: Dict[str, Any]) -> None:
    """Store job data.
    
    Args:
        job: Job data to store
    """
    try:
        job_id = job.get('job_id')
        if not job_id:
            raise ValueError("Job must have job_id")
        
        _job_storage.save(job_id, job)
        logger.info(f"Stored job: {job_id}")
        
    except Exception as e:
        logger.error(f"Failed to store job: {str(e)}", exc_info=True)
        raise


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve job data.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Job data or None if not found
    """
    try:
        return _job_storage.get(job_id)
        
    except Exception as e:
        logger.error(f"Failed to retrieve job {job_id}: {str(e)}", exc_info=True)
        return None


def update_job_status(job_id: str, status: str, 
                      updates: Optional[Dict[str, Any]] = None) -> None:
    """Update job status and additional fields.
    
    Args:
        job_id: Job identifier
        status: New status
        updates: Additional fields to update
    """
    try:
        job = get_job(job_id)
        
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        
        job['status'] = status
        job['updated_at'] = datetime.utcnow().isoformat() + 'Z'
        
        if updates:
            job.update(updates)
        
        store_job(job)
        logger.info(f"Updated job {job_id} status to {status}")
        
    except Exception as e:
        logger.error(f"Failed to update job status: {str(e)}", exc_info=True)
        raise


def list_jobs(status: Optional[str] = None, 
              limit: int = 20, 
              offset: int = 0) -> List[Dict[str, Any]]:
    """List jobs with optional filtering.
    
    Args:
        status: Filter by status
        limit: Maximum number of results
        offset: Pagination offset
        
    Returns:
        List of jobs
    """
    try:
        filters = {'status': status} if status else None
        jobs = _job_storage.list(filters)
        
        # Sort by submitted_at descending
        jobs.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)
        
        # Apply pagination
        return jobs[offset:offset + limit]
        
    except Exception as e:
        logger.error(f"Failed to list jobs: {str(e)}", exc_info=True)
        return []


def store_result(job_id: str, result: Dict[str, Any]) -> None:
    """Store processing result.
    
    Args:
        job_id: Job identifier
        result: Processing result
    """
    try:
        _result_storage.save(job_id, result)
        logger.info(f"Stored result for job: {job_id}")
        
    except Exception as e:
        logger.error(f"Failed to store result: {str(e)}", exc_info=True)
        raise


def get_result(job_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve processing result.
    
    Args:
        job_id: Job identifier
        
    Returns:
        Processing result or None if not found
    """
    try:
        return _result_storage.get(job_id)
        
    except Exception as e:
        logger.error(f"Failed to retrieve result for job {job_id}: {str(e)}", exc_info=True)
        return None


def save(result: Dict[str, Any]) -> None:
    """Simple save function for backward compatibility.
    
    Args:
        result: Result data to save
    """
    job_id = result.get('job_id')
    if job_id:
        store_result(job_id, result)
    else:
        logger.warning("Result missing job_id, cannot save")
