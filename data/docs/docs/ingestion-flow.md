# Ingestion Flow

## Overview

The **Ingestion Flow** handles the complete lifecycle of file submission, validation, and processing initiation. It serves as the entry point for all data processing operations in the system.

---

## Architecture

### Flow Diagram

```
Client Request
      ↓
[API Gateway]
      ↓
[Request Validation]
      ↓
[Job Creation]
      ↓
[Queue Publication] → Ingestion Queue
      ↓
[Response to Client]
      ↓
[Async Processing]
```

---

## Ingestion Stages

### Stage 1: API Request

**Endpoint**: `POST /api/v1/process`

```python
from flask import Flask, request, jsonify
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)

@app.route('/api/v1/process', methods=['POST'])
def process_file():
    """Handle file processing request."""
    
    # Parse request body
    data = request.get_json()
    
    # Validate request
    validation_result = validate_request(data)
    if not validation_result.is_valid:
        return jsonify({
            'error': 'validation_error',
            'message': validation_result.error_message,
            'details': validation_result.details
        }), 400
    
    # Create job
    job = create_job(data)
    
    # Publish to ingestion queue
    publish_to_queue('ingestion-queue', job)
    
    # Return response
    return jsonify({
        'job_id': job['job_id'],
        'status': 'submitted',
        'file_id': data['file_id'],
        'location': data['location'],
        'submitted_at': job['submitted_at'],
        'estimated_completion': job['estimated_completion'],
        '_links': {
            'self': '/api/v1/process',
            'status': f"/api/v1/status/{job['job_id']}"
        }
    }), 202
```

---

### Stage 2: Request Validation

#### Validation Rules

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any
import re

@dataclass
class ValidationResult:
    is_valid: bool
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class RequestValidator:
    """Validate incoming file processing requests."""
    
    def validate_request(self, data: dict) -> ValidationResult:
        """Validate complete request."""
        
        # Required fields
        if not self._validate_required_fields(data):
            return ValidationResult(
                is_valid=False,
                error_message="Missing required fields",
                details={'required': ['file_id', 'location']}
            )
        
        # File ID format
        if not self._validate_file_id(data['file_id']):
            return ValidationResult(
                is_valid=False,
                error_message="Invalid file_id format",
                details={'constraint': 'must be alphanumeric'}
            )
        
        # Location format
        if not self._validate_location(data['location']):
            return ValidationResult(
                is_valid=False,
                error_message="Invalid location format",
                details={'constraint': 'must be valid S3 URI or file path'}
            )
        
        # File size (if provided)
        if 'file_size' in data:
            if not self._validate_file_size(data['file_size']):
                return ValidationResult(
                    is_valid=False,
                    error_message="File size exceeds maximum allowed (100MB)",
                    details={'max_size': 104857600}
                )
        
        return ValidationResult(is_valid=True)
    
    def _validate_required_fields(self, data: dict) -> bool:
        """Check required fields are present."""
        required = ['file_id', 'location']
        return all(field in data for field in required)
    
    def _validate_file_id(self, file_id: str) -> bool:
        """Validate file ID format."""
        pattern = r'^[a-zA-Z0-9_-]+$'
        return bool(re.match(pattern, file_id))
    
    def _validate_location(self, location: str) -> bool:
        """Validate file location format."""
        # S3 URI pattern
        s3_pattern = r'^s3://[a-z0-9][a-z0-9.-]*[a-z0-9]/.*$'
        # Local file path pattern
        file_pattern = r'^(/[^/]+)+/?$'
        
        return bool(re.match(s3_pattern, location) or 
                   re.match(file_pattern, location))
    
    def _validate_file_size(self, file_size: int) -> bool:
        """Validate file size is within limits."""
        MAX_FILE_SIZE = 104857600  # 100MB
        return 0 < file_size <= MAX_FILE_SIZE
```

---

### Stage 3: Job Creation

```python
import uuid
from datetime import datetime, timedelta

def create_job(request_data: dict) -> dict:
    """Create a new processing job."""
    
    job_id = str(uuid.uuid4())
    submitted_at = datetime.utcnow()
    
    # Estimate completion time (5 minutes default)
    estimated_completion = submitted_at + timedelta(minutes=5)
    
    job = {
        'job_id': job_id,
        'file_id': request_data['file_id'],
        'location': request_data['location'],
        'status': 'submitted',
        'submitted_at': submitted_at.isoformat() + 'Z',
        'estimated_completion': estimated_completion.isoformat() + 'Z',
        'metadata': request_data.get('metadata', {}),
        'options': request_data.get('options', {
            'normalization': True,
            'comparison_algorithm': 'structural'
        }),
        'retry_count': 0,
        'created_by': get_current_user(),
        'priority': request_data.get('priority', 'normal')
    }
    
    # Store job in database
    store_job(job)
    
    return job

def store_job(job: dict):
    """Persist job to database."""
    from sqlalchemy import create_engine, Table, MetaData
    
    engine = create_engine(config.database_url)
    metadata = MetaData()
    jobs_table = Table('jobs', metadata, autoload_with=engine)
    
    with engine.connect() as conn:
        conn.execute(jobs_table.insert().values(
            job_id=job['job_id'],
            file_id=job['file_id'],
            location=job['location'],
            status=job['status'],
            submitted_at=job['submitted_at'],
            metadata=json.dumps(job['metadata']),
            options=json.dumps(job['options'])
        ))
        conn.commit()
```

---

### Stage 4: Queue Publication

```python
import boto3
import json

def publish_to_queue(queue_name: str, job: dict):
    """Publish job to ingestion queue."""
    
    # Get queue URL
    queue_url = get_queue_url(queue_name)
    
    # Prepare message
    message = {
        'job_id': job['job_id'],
        'file_id': job['file_id'],
        'location': job['location'],
        'submitted_at': job['submitted_at'],
        'options': job['options'],
        'retry_count': 0
    }
    
    # Publish to SQS
    sqs = boto3.client('sqs')
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message),
        MessageAttributes={
            'JobId': {
                'StringValue': job['job_id'],
                'DataType': 'String'
            },
            'Priority': {
                'StringValue': job.get('priority', 'normal'),
                'DataType': 'String'
            },
            'Timestamp': {
                'StringValue': job['submitted_at'],
                'DataType': 'String'
            }
        }
    )
    
    # Log publication
    logger.info(f"Published job {job['job_id']} to {queue_name}", extra={
        'job_id': job['job_id'],
        'queue': queue_name,
        'message_id': response['MessageId']
    })
    
    return response['MessageId']
```

---

### Stage 5: Async Worker Processing

```python
class IngestionWorker:
    """Worker for processing ingestion queue messages."""
    
    def __init__(self, queue_name='ingestion-queue'):
        self.queue_name = queue_name
        self.sqs = boto3.client('sqs')
        self.s3 = boto3.client('s3')
    
    def process_message(self, message: dict):
        """Process a single ingestion message."""
        
        job_id = message['job_id']
        location = message['location']
        
        try:
            # Update job status
            update_job_status(job_id, 'processing')
            
            # Download file
            file_content = self.download_file(location)
            
            # Validate file format
            self.validate_file_format(file_content)
            
            # Extract metadata
            metadata = self.extract_metadata(file_content)
            
            # Publish to processing queue
            processing_message = {
                'job_id': job_id,
                'file_content': file_content,
                'metadata': metadata,
                'options': message['options']
            }
            publish_to_queue('processing-queue', processing_message)
            
            # Update job status
            update_job_status(job_id, 'ingested')
            
            logger.info(f"Successfully ingested job {job_id}")
            
        except Exception as e:
            logger.error(f"Ingestion failed for job {job_id}: {str(e)}")
            update_job_status(job_id, 'failed', error=str(e))
            raise
    
    def download_file(self, location: str) -> str:
        """Download file from S3 or local storage."""
        
        if location.startswith('s3://'):
            # Parse S3 URI
            bucket, key = parse_s3_uri(location)
            
            # Download from S3
            response = self.s3.get_object(Bucket=bucket, Key=key)
            content = response['Body'].read().decode('utf-8')
            
            logger.info(f"Downloaded file from S3: {location}")
            return content
        
        else:
            # Read local file
            with open(location, 'r') as f:
                content = f.read()
            
            logger.info(f"Read local file: {location}")
            return content
    
    def validate_file_format(self, content: str):
        """Validate file format (JSON, XML, CSV, etc.)."""
        
        try:
            # Try parsing as JSON
            json.loads(content)
            logger.info("File format validated: JSON")
        except json.JSONDecodeError:
            raise ValueError("Invalid file format: must be valid JSON")
    
    def extract_metadata(self, content: str) -> dict:
        """Extract metadata from file content."""
        
        data = json.loads(content)
        
        metadata = {
            'file_size': len(content),
            'field_count': count_fields(data),
            'schema_version': data.get('metadata', {}).get('schema_version'),
            'source_system': data.get('metadata', {}).get('source_system'),
            'extracted_at': datetime.utcnow().isoformat() + 'Z'
        }
        
        return metadata
```

---

## Error Handling

### Error Types

| Error Type | HTTP Code | Description | Recovery |
|------------|-----------|-------------|----------|
| `validation_error` | 400 | Invalid request format | Client fix required |
| `file_not_found` | 404 | File location invalid | Check file path |
| `file_too_large` | 413 | File exceeds size limit | Reduce file size |
| `rate_limit_exceeded` | 429 | Too many requests | Retry after delay |
| `processing_error` | 500 | Internal processing failure | Automatic retry |

### Retry Strategy

```python
def handle_ingestion_error(job_id: str, error: Exception, retry_count: int):
    """Handle ingestion errors with retry logic."""
    
    MAX_RETRIES = 3
    
    if retry_count < MAX_RETRIES:
        # Exponential backoff
        delay = 2 ** retry_count  # 1s, 2s, 4s
        
        logger.warning(
            f"Ingestion failed for job {job_id}, retrying in {delay}s",
            extra={'retry_count': retry_count, 'error': str(error)}
        )
        
        # Re-publish with incremented retry count
        time.sleep(delay)
        republish_with_retry(job_id, retry_count + 1)
    
    else:
        # Max retries exceeded, move to DLQ
        logger.error(
            f"Ingestion failed permanently for job {job_id}",
            extra={'retry_count': retry_count, 'error': str(error)}
        )
        
        move_to_dead_letter_queue(job_id, error)
        update_job_status(job_id, 'failed', error=str(error))
```

---

## Monitoring

### Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
ingestion_requests_total = Counter(
    'ingestion_requests_total',
    'Total ingestion requests',
    ['status']
)

ingestion_duration_seconds = Histogram(
    'ingestion_duration_seconds',
    'Ingestion processing duration'
)

ingestion_queue_depth = Gauge(
    'ingestion_queue_depth',
    'Current ingestion queue depth'
)

# Track metrics
@ingestion_duration_seconds.time()
def process_ingestion(job):
    try:
        # Process ingestion
        result = ingest_file(job)
        ingestion_requests_total.labels(status='success').inc()
        return result
    except Exception as e:
        ingestion_requests_total.labels(status='error').inc()
        raise
```

---

## Configuration

```yaml
ingestion:
  # File settings
  max_file_size: 104857600  # 100MB
  allowed_formats:
    - json
    - xml
    - csv
  
  # Queue settings
  queue_name: ingestion-queue
  batch_size: 10
  visibility_timeout: 300  # 5 minutes
  
  # Worker settings
  worker_count: 4
  max_retries: 3
  retry_delay: 60  # seconds
  
  # Storage settings
  storage_type: s3  # s3, local
  s3_bucket: ai-assistant-demo-files
```

---

## Related Documentation

- [API Contracts](api-contracts.md) - API specifications
- [Async Processing](async-processing.md) - Queue architecture
- [System Overview](system-overview.md) - Complete system flow
