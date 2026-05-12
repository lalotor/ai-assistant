# Asynchronous Processing

## Overview

The AI Assistant Demo system implements **queue-based asynchronous processing** to handle long-running file processing and comparison operations. This architecture decouples API requests from processing logic, enabling horizontal scaling and improved resilience.

---

## Architecture Pattern

### Event-Driven Design

The system uses an **event-driven architecture** with message queues:

```
[API] → [Queue] → [Workers] → [Storage]
```

### Benefits

✅ **Scalability**: Workers scale independently based on queue depth  
✅ **Resilience**: Failed jobs automatically retry  
✅ **Decoupling**: API and processing logic are independent  
✅ **Performance**: Non-blocking API responses  
✅ **Observability**: Queue metrics provide system health insights  

---

## Queue Architecture

### Queue Types

The system uses **four specialized queues**:

#### 1. Ingestion Queue
**Purpose**: File upload and validation

```python
{
  "queue_name": "ingestion-queue",
  "message": {
    "job_id": "job-uuid-1234",
    "file_id": "abc123",
    "location": "s3://bucket/file.json",
    "submitted_at": "2024-01-15T10:30:00Z"
  }
}
```

**Processing Steps**:
1. Download file from storage
2. Validate file format and size
3. Extract metadata
4. Publish to processing queue

#### 2. Processing Queue
**Purpose**: Data transformation and normalization

```python
{
  "queue_name": "processing-queue",
  "message": {
    "job_id": "job-uuid-1234",
    "file_id": "abc123",
    "raw_data": {...},
    "options": {
      "normalization": true
    }
  }
}
```

**Processing Steps**:
1. Parse file content
2. Apply normalization rules
3. Validate data schema
4. Publish to comparison queue

#### 3. Comparison Queue
**Purpose**: Diff computation

```python
{
  "queue_name": "comparison-queue",
  "message": {
    "job_id": "job-uuid-1234",
    "system_a_data": {...},
    "system_b_data": {...},
    "algorithm": "structural"
  }
}
```

**Processing Steps**:
1. Load comparison data
2. Execute diff algorithm (Java service)
3. Generate diff report
4. Publish to notification queue

#### 4. Notification Queue
**Purpose**: Result delivery

```python
{
  "queue_name": "notification-queue",
  "message": {
    "job_id": "job-uuid-1234",
    "status": "completed",
    "result": {...},
    "completed_at": "2024-01-15T10:32:45Z"
  }
}
```

**Processing Steps**:
1. Store results in database
2. Update job status
3. Send notifications (email, webhook)
4. Clean up temporary data

---

## Message Queue Implementation

### SQS-Style Queue (Production)

For production deployments, the system uses **AWS SQS** or compatible message brokers:

```python
import boto3

# Initialize SQS client
sqs = boto3.client('sqs', region_name='us-east-1')

# Publish message
def publish_message(queue_name, message):
    queue_url = get_queue_url(queue_name)
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message),
        MessageAttributes={
            'JobId': {
                'StringValue': message['job_id'],
                'DataType': 'String'
            },
            'Priority': {
                'StringValue': 'normal',
                'DataType': 'String'
            }
        }
    )
    return response['MessageId']

# Consume messages
def consume_messages(queue_name, max_messages=10):
    queue_url = get_queue_url(queue_name)
    response = sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=20,  # Long polling
        VisibilityTimeout=300  # 5 minutes
    )
    return response.get('Messages', [])

# Delete message after processing
def delete_message(queue_name, receipt_handle):
    queue_url = get_queue_url(queue_name)
    sqs.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle
    )
```

### In-Memory Queue (Development)

For local development, a **simulated in-memory queue** is used:

```python
import queue
import threading

class InMemoryQueue:
    def __init__(self):
        self.queues = {
            'ingestion-queue': queue.Queue(),
            'processing-queue': queue.Queue(),
            'comparison-queue': queue.Queue(),
            'notification-queue': queue.Queue()
        }
    
    def publish(self, queue_name, message):
        """Publish message to queue."""
        self.queues[queue_name].put(message)
    
    def consume(self, queue_name, timeout=1):
        """Consume message from queue."""
        try:
            return self.queues[queue_name].get(timeout=timeout)
        except queue.Empty:
            return None
    
    def ack(self, queue_name, message):
        """Acknowledge message processing."""
        self.queues[queue_name].task_done()
```

---

## Worker Pool Architecture

### Worker Design

Each queue has a dedicated **worker pool**:

```python
import multiprocessing
from concurrent.futures import ThreadPoolExecutor

class Worker:
    def __init__(self, queue_name, handler, num_workers=4):
        self.queue_name = queue_name
        self.handler = handler
        self.num_workers = num_workers
        self.executor = ThreadPoolExecutor(max_workers=num_workers)
        self.running = False
    
    def start(self):
        """Start worker pool."""
        self.running = True
        for _ in range(self.num_workers):
            self.executor.submit(self._worker_loop)
    
    def _worker_loop(self):
        """Worker main loop."""
        while self.running:
            message = queue_service.consume(self.queue_name)
            if message:
                try:
                    self.handler(message)
                    queue_service.ack(self.queue_name, message)
                except Exception as e:
                    logger.error(f"Worker error: {e}")
                    self._handle_error(message, e)
    
    def _handle_error(self, message, error):
        """Handle processing errors."""
        retry_count = message.get('retry_count', 0)
        if retry_count < 3:
            # Retry with exponential backoff
            message['retry_count'] = retry_count + 1
            delay = 2 ** retry_count  # 1s, 2s, 4s
            time.sleep(delay)
            queue_service.publish(self.queue_name, message)
        else:
            # Move to dead-letter queue
            queue_service.publish('dead-letter-queue', {
                'original_message': message,
                'error': str(error),
                'failed_at': datetime.utcnow().isoformat()
            })
    
    def stop(self):
        """Stop worker pool gracefully."""
        self.running = False
        self.executor.shutdown(wait=True)
```

---

## Processing Flow

### End-to-End Flow

```
1. Client submits file via POST /process
   ↓
2. API validates request and publishes to ingestion-queue
   ↓
3. Ingestion worker downloads file and publishes to processing-queue
   ↓
4. Processing worker normalizes data and publishes to comparison-queue
   ↓
5. Comparison worker (Java) computes diff and publishes to notification-queue
   ↓
6. Notification worker stores results and updates job status
   ↓
7. Client polls GET /status/{job_id} for results
```

### Sequence Diagram

```
Client          API         Queue       Worker      Storage
  |             |            |           |           |
  |--POST------>|            |           |           |
  |             |--publish-->|           |           |
  |<--202-------|            |           |           |
  |             |            |           |           |
  |             |            |<--poll----|           |
  |             |            |--message->|           |
  |             |            |           |--process->|
  |             |            |           |<--save----|           |
  |             |            |<--ack-----|           |
  |             |            |           |           |
  |--GET------->|            |           |           |
  |             |------------|-----------|---------->|
  |             |<-----------|-----------|-----------|           |
  |<--200-------|            |           |           |
```

---

## Error Handling

### Retry Strategy

**Exponential Backoff**:
- Retry 1: 1 second delay
- Retry 2: 2 seconds delay
- Retry 3: 4 seconds delay
- After 3 retries: Move to dead-letter queue

### Dead-Letter Queue

Failed messages are moved to a **dead-letter queue** for manual investigation:

```python
{
  "original_message": {...},
  "error": "JSONDecodeError: Expecting value: line 1 column 1",
  "failed_at": "2024-01-15T10:31:00Z",
  "retry_count": 3
}
```

---

## Monitoring & Metrics

### Queue Metrics

- **Queue Depth**: Number of messages waiting
- **Processing Rate**: Messages processed per second
- **Error Rate**: Failed messages percentage
- **Latency**: Time from publish to completion

### CloudWatch Metrics (AWS)

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

# Publish custom metric
cloudwatch.put_metric_data(
    Namespace='AIAssistantDemo',
    MetricData=[
        {
            'MetricName': 'QueueDepth',
            'Value': queue_depth,
            'Unit': 'Count',
            'Dimensions': [
                {'Name': 'QueueName', 'Value': 'ingestion-queue'}
            ]
        }
    ]
)
```

---

## Configuration

### Queue Settings

```yaml
queue:
  type: sqs  # sqs, rabbitmq, redis, memory
  
  sqs:
    region: us-east-1
    queues:
      ingestion: ai-assistant-ingestion-queue
      processing: ai-assistant-processing-queue
      comparison: ai-assistant-comparison-queue
      notification: ai-assistant-notification-queue
  
  processing:
    batch_size: 10
    wait_time: 20  # Long polling (seconds)
    visibility_timeout: 300  # 5 minutes
    max_retries: 3
    retry_delay: 60  # seconds
```

---

## Best Practices

### 1. Idempotency

Ensure message handlers are **idempotent** (can be safely retried):

```python
def process_message(message):
    job_id = message['job_id']
    
    # Check if already processed
    if is_already_processed(job_id):
        logger.info(f"Job {job_id} already processed, skipping")
        return
    
    # Process message
    result = do_processing(message)
    
    # Mark as processed
    mark_as_processed(job_id, result)
```

### 2. Message Deduplication

Use **message deduplication** to prevent duplicate processing:

```python
# SQS FIFO queue with deduplication
sqs.send_message(
    QueueUrl=queue_url,
    MessageBody=json.dumps(message),
    MessageDeduplicationId=message['job_id'],
    MessageGroupId='default'
)
```

### 3. Graceful Shutdown

Handle **graceful shutdown** to avoid data loss:

```python
import signal

def signal_handler(sig, frame):
    logger.info("Shutting down gracefully...")
    worker.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

---

## Related Documentation

- [Architecture Overview](../ARCHITECTURE.md)
- [Ingestion Flow](ingestion-flow.md)
- [Comparison Engine](comparison-engine.md)
- [System Overview](system-overview.md)
