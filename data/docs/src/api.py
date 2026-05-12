"""API Module - REST API endpoints for file processing.

Provides Flask-based REST API for:
- File submission and processing
- Job status tracking
- Job listing and filtering
- Health checks

Author: Platform Team
Version: 2.0.0
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import uuid
import logging
from typing import Dict, Any, Optional

from ingestion import ingest_file
from storage import store_job, get_job, list_jobs

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False


def validate_request(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate incoming request data.
    
    Args:
        data: Request payload
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ['file_id', 'location']
    
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    # Validate file_id format
    if not isinstance(data['file_id'], str) or len(data['file_id']) == 0:
        return False, "Invalid file_id format"
    
    # Validate location format
    if not isinstance(data['location'], str) or len(data['location']) == 0:
        return False, "Invalid location format"
    
    return True, None


@app.route('/api/v1/process', methods=['POST'])
def process_file():
    """Submit file for processing.
    
    Request Body:
        {
            "file_id": "abc123",
            "location": "s3://bucket/file.json",
            "metadata": {...},
            "options": {...}
        }
    
    Returns:
        202 Accepted with job details
        400 Bad Request if validation fails
    """
    try:
        # Parse request
        data = request.get_json()
        
        # Validate request
        is_valid, error_message = validate_request(data)
        if not is_valid:
            logger.warning(f"Validation failed: {error_message}")
            return jsonify({
                'error': 'validation_error',
                'message': error_message
            }), 400
        
        # Create job
        job_id = str(uuid.uuid4())
        submitted_at = datetime.utcnow()
        estimated_completion = submitted_at + timedelta(minutes=5)
        
        job = {
            'job_id': job_id,
            'file_id': data['file_id'],
            'location': data['location'],
            'status': 'submitted',
            'submitted_at': submitted_at.isoformat() + 'Z',
            'estimated_completion': estimated_completion.isoformat() + 'Z',
            'metadata': data.get('metadata', {}),
            'options': data.get('options', {
                'normalization': True,
                'comparison_algorithm': 'structural'
            })
        }
        
        # Store job
        store_job(job)
        
        # Trigger ingestion
        ingest_file(job)
        
        logger.info(f"Job created: {job_id}")
        
        # Return response
        return jsonify({
            'job_id': job_id,
            'status': 'submitted',
            'file_id': data['file_id'],
            'location': data['location'],
            'submitted_at': job['submitted_at'],
            'estimated_completion': job['estimated_completion'],
            '_links': {
                'self': '/api/v1/process',
                'status': f"/api/v1/status/{job_id}"
            }
        }), 202
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'internal_error',
            'message': 'An error occurred processing your request'
        }), 500


@app.route('/api/v1/status/<job_id>', methods=['GET'])
def get_status(job_id: str):
    """Get job status and results.
    
    Args:
        job_id: Job identifier
        
    Returns:
        200 OK with job details
        404 Not Found if job doesn't exist
    """
    try:
        job = get_job(job_id)
        
        if not job:
            return jsonify({
                'error': 'job_not_found',
                'message': f"Job with ID '{job_id}' not found"
            }), 404
        
        response = {
            'job_id': job['job_id'],
            'status': job['status'],
            'file_id': job['file_id'],
            'submitted_at': job['submitted_at'],
            '_links': {
                'self': f"/api/v1/status/{job_id}"
            }
        }
        
        # Add status-specific fields
        if job['status'] == 'completed':
            response['completed_at'] = job.get('completed_at')
            response['result'] = job.get('result', {})
        elif job['status'] == 'failed':
            response['failed_at'] = job.get('failed_at')
            response['error'] = job.get('error', {})
        elif job['status'] == 'processing':
            response['started_at'] = job.get('started_at')
            response['progress'] = job.get('progress', {})
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(f"Error retrieving job status: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'internal_error',
            'message': 'An error occurred retrieving job status'
        }), 500


@app.route('/api/v1/jobs', methods=['GET'])
def get_jobs():
    """List jobs with optional filtering.
    
    Query Parameters:
        status: Filter by status
        limit: Number of results (default: 20)
        offset: Pagination offset (default: 0)
        
    Returns:
        200 OK with job list
    """
    try:
        # Parse query parameters
        status = request.args.get('status')
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
        
        # Get jobs
        jobs = list_jobs(status=status, limit=limit, offset=offset)
        
        return jsonify({
            'total': len(jobs),
            'limit': limit,
            'offset': offset,
            'jobs': jobs,
            '_links': {
                'self': f"/api/v1/jobs?limit={limit}&offset={offset}",
                'next': f"/api/v1/jobs?limit={limit}&offset={offset + limit}"
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'internal_error',
            'message': 'An error occurred listing jobs'
        }), 500


@app.route('/api/v1/health', methods=['GET'])
def health():
    """Health check endpoint.
    
    Returns:
        200 OK with health status
    """
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'version': '2.0.0',
        'service': 'ai-assistant-demo-api'
    }), 200


if __name__ == '__main__':
    # Development server
    app.run(host='0.0.0.0', port=8000, debug=True)
