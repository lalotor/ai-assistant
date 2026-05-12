# Data Model Architecture

## Overview

This document defines the core data models used throughout the system. The architecture follows a normalized relational design with clear entity relationships and data integrity constraints.

## Core Entities

### 1. Job Entity

**Purpose**: Represents a processing job submitted to the system for data ingestion, comparison, or transformation.

**Schema**:

```json
{
  "job_id": "string (UUID)",
  "job_type": "enum (INGESTION, COMPARISON, TRANSFORMATION)",
  "status": "enum (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)",
  "priority": "integer (1-10)",
  "created_at": "timestamp",
  "updated_at": "timestamp",
  "started_at": "timestamp (nullable)",
  "completed_at": "timestamp (nullable)",
  "created_by": "string (user_id)",
  "configuration": "json (job-specific config)",
  "metadata": {
    "source": "string",
    "tags": "array<string>",
    "retry_count": "integer",
    "max_retries": "integer"
  }
}
```

**Relationships**:
- One Job → Many Results (1:N)
- One Job → Many File Metadata (1:N)

**Indexes**:
- Primary: `job_id`
- Secondary: `status`, `created_at`, `job_type`
- Composite: `(status, priority, created_at)` for queue optimization

**Constraints**:
- `job_id` must be unique UUID v4
- `status` transitions must follow state machine rules
- `priority` range: 1 (lowest) to 10 (highest)
- `completed_at` must be >= `started_at`

---

### 2. Result Entity

**Purpose**: Stores the output and execution details of a completed or failed job.

**Schema**:

```json
{
  "result_id": "string (UUID)",
  "job_id": "string (UUID, foreign key)",
  "status": "enum (SUCCESS, PARTIAL_SUCCESS, FAILURE)",
  "execution_time_ms": "integer",
  "output_data": "json (result payload)",
  "error_details": {
    "error_code": "string (nullable)",
    "error_message": "string (nullable)",
    "stack_trace": "text (nullable)",
    "failed_step": "string (nullable)"
  },
  "metrics": {
    "records_processed": "integer",
    "records_failed": "integer",
    "data_size_bytes": "long",
    "cpu_usage_percent": "float",
    "memory_usage_mb": "float"
  },
  "created_at": "timestamp",
  "checksum": "string (SHA-256)"
}
```

**Relationships**:
- Many Results → One Job (N:1)

**Indexes**:
- Primary: `result_id`
- Foreign Key: `job_id`
- Secondary: `status`, `created_at`

**Constraints**:
- `job_id` must reference valid Job entity
- `execution_time_ms` must be non-negative
- `checksum` calculated on `output_data` for integrity verification
- Cascade delete when parent Job is deleted

---

### 3. File Metadata Entity

**Purpose**: Tracks files associated with jobs, including input files, output artifacts, and intermediate processing files.

**Schema**:

```json
{
  "file_id": "string (UUID)",
  "job_id": "string (UUID, foreign key)",
  "file_name": "string",
  "file_path": "string (storage URI)",
  "file_type": "enum (INPUT, OUTPUT, INTERMEDIATE, LOG)",
  "mime_type": "string",
  "file_size_bytes": "long",
  "checksum": "string (SHA-256)",
  "storage_location": "enum (S3, LOCAL, GCS, AZURE_BLOB)",
  "encryption_status": "enum (NONE, AT_REST, IN_TRANSIT, BOTH)",
  "compression": "enum (NONE, GZIP, BZIP2, LZ4)",
  "uploaded_at": "timestamp",
  "expires_at": "timestamp (nullable)",
  "metadata": {
    "content_hash": "string",
    "encoding": "string",
    "version": "integer",
    "tags": "array<string>"
  }
}
```

**Relationships**:
- Many File Metadata → One Job (N:1)

**Indexes**:
- Primary: `file_id`
- Foreign Key: `job_id`
- Secondary: `file_type`, `uploaded_at`, `storage_location`
- Composite: `(job_id, file_type)` for efficient job file queries

**Constraints**:
- `job_id` must reference valid Job entity
- `file_size_bytes` must be non-negative
- `checksum` must be valid SHA-256 hash
- `file_path` must be unique within storage location
- Soft delete with retention policy (90 days default)

---

## Entity Relationship Diagram

```
┌─────────────────┐
│      Job        │
│─────────────────│
│ job_id (PK)     │
│ job_type        │
│ status          │
│ priority        │
│ created_at      │
│ configuration   │
└────────┬────────┘
         │
         │ 1:N
         │
    ┌────┴─────────────────────┐
    │                          │
    │                          │
┌───▼──────────┐      ┌────────▼──────────┐
│   Result     │      │  File Metadata    │
│──────────────│      │───────────────────│
│ result_id(PK)│      │ file_id (PK)      │
│ job_id (FK)  │      │ job_id (FK)       │
│ status       │      │ file_name         │
│ output_data  │      │ file_path         │
│ metrics      │      │ file_type         │
└──────────────┘      │ storage_location  │
                      └───────────────────┘
```

---

## Data Flow

1. **Job Creation**: Client creates Job entity with configuration
2. **File Upload**: Input files create File Metadata entities linked to Job
3. **Processing**: Job status transitions trigger processing pipeline
4. **Result Generation**: Processing creates Result entity with output data
5. **Output Storage**: Output files create additional File Metadata entities
6. **Cleanup**: Expired files removed based on retention policy

---

## Storage Considerations

### Database Strategy
- **Primary Database**: PostgreSQL 14+ for ACID compliance
- **Read Replicas**: For analytics and reporting queries
- **Partitioning**: Jobs and Results partitioned by `created_at` (monthly)
- **Archival**: Records older than 1 year moved to cold storage

### File Storage Strategy
- **Hot Storage**: S3 Standard for active jobs (0-30 days)
- **Warm Storage**: S3 Infrequent Access for recent completed jobs (30-90 days)
- **Cold Storage**: S3 Glacier for archived jobs (90+ days)
- **Lifecycle Policies**: Automatic transition based on `expires_at`

---

## Data Integrity & Validation

### Validation Rules
1. All timestamps must be in UTC
2. All UUIDs must be version 4
3. File checksums verified on upload and download
4. JSON schemas validated against predefined contracts
5. Foreign key constraints enforced at database level

### Audit Trail
- All entity changes logged to audit table
- Includes: entity_type, entity_id, action, user_id, timestamp, changes
- Retention: 7 years for compliance

---

## Performance Optimization

### Caching Strategy
- **Job Status**: Redis cache with 30-second TTL
- **File Metadata**: Cache frequently accessed file paths
- **Results**: Cache recent results for 5 minutes

### Query Optimization
- Use prepared statements for common queries
- Batch inserts for bulk operations
- Connection pooling (min: 10, max: 50)
- Query timeout: 30 seconds

---

## Security & Compliance

### Data Protection
- **Encryption at Rest**: AES-256 for all stored data
- **Encryption in Transit**: TLS 1.3 for all data transfers
- **PII Handling**: Sensitive fields encrypted with separate key
- **Access Control**: Row-level security based on user permissions

### Compliance
- **GDPR**: Right to deletion implemented via soft delete
- **Data Residency**: Region-specific storage locations
- **Retention Policies**: Configurable per entity type

---

## Migration & Versioning

### Schema Versioning
- Use Flyway/Liquibase for database migrations
- Version format: `V{major}.{minor}.{patch}__{description}.sql`
- Backward compatibility maintained for 2 major versions

### Data Migration
- Zero-downtime migrations using blue-green deployment
- Rollback scripts for all migrations
- Testing on staging environment required

---

## Future Considerations

1. **Event Sourcing**: Consider event store for complete audit trail
2. **Time-Series Data**: Separate metrics storage for performance data
3. **Graph Database**: For complex relationship queries
4. **Data Lake**: Integration with analytics platform for ML/AI workloads

---

**Last Updated**: 2026-05-05  
**Version**: 1.0.0  
**Owner**: Architecture Team
