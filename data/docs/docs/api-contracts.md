# API Contracts

## Overview

This document defines the REST API contracts for the AI Assistant Demo system. All endpoints follow RESTful principles and return JSON responses.

---

## Base URL

```
Development: http://localhost:8000/api/v1
Staging:     https://staging-api.ai-assistant-demo.com/api/v1
Production:  https://api.ai-assistant-demo.com/api/v1
```

---

## Authentication

### JWT Bearer Token (Production)

```http
Authorization: Bearer <jwt_token>
```

### API Key (Alternative)

```http
X-API-Key: <api_key>
```

**Note**: Authentication is disabled in development mode.

---

## Endpoints

### 1. Submit File for Processing

**Endpoint**: `POST /process`

**Description**: Submit a file for asynchronous processing and comparison.

#### Request

```http
POST /api/v1/process
Content-Type: application/json
Authorization: Bearer <token>

{
  "file_id": "abc123",
  "location": "s3://bucket/path/to/file.json",
  "metadata": {
    "source_system": "system_a",
    "environment": "production"
  },
  "options": {
    "normalization": true,
    "comparison_algorithm": "structural"
  }
}
```

#### Request Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_id` | string | Yes | Unique identifier for the file |
| `location` | string | Yes | S3 URI or local path to the file |
| `metadata` | object | No | Additional metadata about the file |
| `metadata.source_system` | string | No | Source system identifier |
| `metadata.environment` | string | No | Environment (dev, staging, prod) |
| `options` | object | No | Processing options |
| `options.normalization` | boolean | No | Enable data normalization (default: true) |
| `options.comparison_algorithm` | string | No | Algorithm: `structural` or `semantic` |

#### Response (Success)

```http
HTTP/1.1 202 Accepted
Content-Type: application/json

{
  "job_id": "job-uuid-1234-5678-90ab-cdef",
  "status": "submitted",
  "file_id": "abc123",
  "location": "s3://bucket/path/to/file.json",
  "submitted_at": "2024-01-15T10:30:00Z",
  "estimated_completion": "2024-01-15T10:35:00Z",
  "_links": {
    "self": "/api/v1/process",
    "status": "/api/v1/status/job-uuid-1234-5678-90ab-cdef"
  }
}
```

#### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | string | Unique job identifier for tracking |
| `status` | string | Job status: `submitted`, `processing`, `completed`, `failed` |
| `file_id` | string | Original file identifier |
| `location` | string | File location |
| `submitted_at` | string (ISO 8601) | Job submission timestamp |
| `estimated_completion` | string (ISO 8601) | Estimated completion time |
| `_links` | object | HATEOAS links |

#### Error Responses

**400 Bad Request**
```json
{
  "error": "validation_error",
  "message": "Invalid file_id format",
  "details": {
    "field": "file_id",
    "constraint": "must be alphanumeric"
  }
}
```

**401 Unauthorized**
```json
{
  "error": "unauthorized",
  "message": "Invalid or expired token"
}
```

**413 Payload Too Large**
```json
{
  "error": "file_too_large",
  "message": "File size exceeds maximum allowed (100MB)",
  "max_size": 104857600
}
```

**429 Too Many Requests**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded",
  "retry_after": 60
}
```

---

### 2. Get Job Status

**Endpoint**: `GET /status/{job_id}`

**Description**: Retrieve the current status and results of a processing job.

#### Request

```http
GET /api/v1/status/job-uuid-1234-5678-90ab-cdef
Authorization: Bearer <token>
```

#### Response (Processing)

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "job_id": "job-uuid-1234-5678-90ab-cdef",
  "status": "processing",
  "file_id": "abc123",
  "submitted_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:15Z",
  "progress": {
    "current_step": "normalization",
    "total_steps": 4,
    "completed_steps": 2,
    "percentage": 50
  },
  "_links": {
    "self": "/api/v1/status/job-uuid-1234-5678-90ab-cdef"
  }
}
```

#### Response (Completed)

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "job_id": "job-uuid-1234-5678-90ab-cdef",
  "status": "completed",
  "file_id": "abc123",
  "submitted_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:15Z",
  "completed_at": "2024-01-15T10:32:45Z",
  "duration_ms": 150000,
  "result": {
    "match": false,
    "similarity_score": 0.92,
    "differences": [
      {
        "path": "data.amount",
        "type": "value_change",
        "old_value": 100,
        "new_value": 105,
        "severity": "medium"
      },
      {
        "path": "data.shipping.method",
        "type": "value_change",
        "old_value": "standard",
        "new_value": "express",
        "severity": "low"
      }
    ],
    "statistics": {
      "total_fields": 25,
      "changed_fields": 2,
      "added_fields": 0,
      "removed_fields": 0
    }
  },
  "_links": {
    "self": "/api/v1/status/job-uuid-1234-5678-90ab-cdef",
    "download_report": "/api/v1/reports/job-uuid-1234-5678-90ab-cdef"
  }
}
```

#### Response (Failed)

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "job_id": "job-uuid-1234-5678-90ab-cdef",
  "status": "failed",
  "file_id": "abc123",
  "submitted_at": "2024-01-15T10:30:00Z",
  "failed_at": "2024-01-15T10:31:00Z",
  "error": {
    "code": "processing_error",
    "message": "Failed to parse JSON file",
    "details": "Unexpected token at line 15"
  },
  "_links": {
    "self": "/api/v1/status/job-uuid-1234-5678-90ab-cdef",
    "retry": "/api/v1/process"
  }
}
```

#### Error Responses

**404 Not Found**
```json
{
  "error": "job_not_found",
  "message": "Job with ID 'job-uuid-1234' not found"
}
```

---

### 3. List Jobs

**Endpoint**: `GET /jobs`

**Description**: List all jobs with optional filtering.

#### Request

```http
GET /api/v1/jobs?status=completed&limit=10&offset=0
Authorization: Bearer <token>
```

#### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `status` | string | No | Filter by status: `submitted`, `processing`, `completed`, `failed` |
| `file_id` | string | No | Filter by file ID |
| `limit` | integer | No | Number of results (default: 20, max: 100) |
| `offset` | integer | No | Pagination offset (default: 0) |
| `sort` | string | No | Sort field: `submitted_at`, `completed_at` (default: `-submitted_at`) |

#### Response

```json
{
  "total": 150,
  "limit": 10,
  "offset": 0,
  "jobs": [
    {
      "job_id": "job-uuid-1",
      "status": "completed",
      "file_id": "abc123",
      "submitted_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T10:32:45Z"
    }
  ],
  "_links": {
    "self": "/api/v1/jobs?limit=10&offset=0",
    "next": "/api/v1/jobs?limit=10&offset=10"
  }
}
```

---

### 4. Health Check

**Endpoint**: `GET /health`

**Description**: Check system health and dependencies.

#### Request

```http
GET /api/v1/health
```

#### Response

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "2.0.0",
  "checks": {
    "database": {
      "status": "up",
      "response_time_ms": 5
    },
    "cache": {
      "status": "up",
      "response_time_ms": 2
    },
    "queue": {
      "status": "up",
      "depth": 15
    },
    "storage": {
      "status": "up"
    }
  }
}
```

---

## Common Response Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 202 | Accepted | Job submitted successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 413 | Payload Too Large | File size exceeds limit |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Service temporarily unavailable |

---

## Rate Limiting

- **Default**: 60 requests per minute per API key
- **Burst**: 10 requests
- **Headers**:
  - `X-RateLimit-Limit`: Maximum requests per window
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Time when limit resets (Unix timestamp)

---

## Pagination

List endpoints support pagination:

```
GET /api/v1/jobs?limit=20&offset=0
```

- `limit`: Number of results (default: 20, max: 100)
- `offset`: Number of results to skip

---

## Error Response Format

All errors follow a consistent format:

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {},
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req-uuid-1234"
}
```

---

## Versioning

API versioning is handled via URL path:

- **Current**: `/api/v1`
- **Future**: `/api/v2` (planned)

---

## Related Documentation

- [System Overview](system-overview.md)
- [Async Processing](async-processing.md)
- [Comparison Engine](comparison-engine.md)
