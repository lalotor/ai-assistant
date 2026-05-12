# System Architecture

## Overview

This system implements a **hybrid architecture** combining synchronous REST APIs with asynchronous event-driven processing to handle file ingestion, comparison, and analysis workflows at scale.

## Architecture Style

### Hybrid Architecture Pattern

The system employs a multi-paradigm architectural approach:

- **Synchronous Layer**: REST API for client-facing operations
- **Asynchronous Layer**: Queue-based processing for long-running tasks
- **Batch Processing**: Scheduled comparison jobs for bulk operations
- **Microservices**: Polyglot services (Python + Java) for specialized tasks

## Core Components

### 1. API Gateway Layer

**Technology**: Python (Flask/FastAPI)

- Exposes REST endpoints for file submission
- Handles authentication and request validation
- Returns job identifiers for async tracking
- Provides status polling endpoints

### 2. Async Processing Layer

**Technology**: SQS-style message queue (simulated)

- **Queue Types**:
  - `ingestion-queue`: File upload and validation jobs
  - `processing-queue`: Data transformation tasks
  - `comparison-queue`: Diff computation jobs
  - `notification-queue`: Result delivery events

- **Processing Model**:
  - Event-driven architecture
  - Decoupled producers and consumers
  - Retry logic with exponential backoff
  - Dead-letter queues for failed jobs

### 3. Batch Comparison Engine

**Technology**: Python + Java hybrid

- **Python Service**: Orchestration and normalization
- **Java Service**: High-performance structural diff computation
- **Batch Scheduler**: Cron-based or event-triggered
- **Optimization**: Parallel processing with worker pools

### 4. Storage Layer

**Technology**: Multi-tier storage strategy

- **Hot Storage**: Redis/In-memory cache for active jobs
- **Warm Storage**: PostgreSQL for metadata and results
- **Cold Storage**: S3-compatible object storage for raw files

## Architecture Diagram

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP POST /process
       ▼
┌─────────────────────────────────────┐
│         REST API Gateway            │
│      (Python Flask/FastAPI)         │
└──────┬──────────────────────────────┘
       │ Publish event
       ▼
┌─────────────────────────────────────┐
│      Message Queue (SQS-style)      │
│  ┌──────────┐  ┌──────────┐        │
│  │Ingestion │  │Processing│        │
│  │  Queue   │  │  Queue   │        │
│  └──────────┘  └──────────┘        │
└──────┬──────────────────────────────┘
       │ Consume events
       ▼
┌─────────────────────────────────────┐
│      Async Worker Pool              │
│  ┌──────────┐  ┌──────────┐        │
│  │ Python   │  │  Java    │        │
│  │ Workers  │  │ Workers  │        │
│  └──────────┘  └──────────┘        │
└──────┬──────────────────────────────┘
       │ Store results
       ▼
┌─────────────────────────────────────┐
│         Storage Layer               │
│  ┌──────┐ ┌──────┐ ┌──────┐        │
│  │Redis │ │ PG   │ │  S3  │        │
│  └──────┘ └──────┘ └──────┘        │
└─────────────────────────────────────┘
```

## Key Architectural Decisions

### 1. Async Processing Choice

**Decision**: Use queue-based async processing instead of synchronous request-response

**Rationale**:
- File processing can take minutes to hours
- Prevents HTTP timeout issues
- Enables horizontal scaling of workers
- Improves system resilience

### 2. Polyglot Microservices

**Decision**: Combine Python and Java services

**Rationale**:
- Python: Rapid development, rich ecosystem for data processing
- Java: High-performance diff algorithms, enterprise integration
- Best tool for each job

### 3. Normalization Before Diff

**Decision**: Normalize data before comparison

**Rationale**:
- Reduces false positives
- Handles format variations
- Improves diff accuracy
- See [DECISIONS.md](DECISIONS.md) for details

## Scalability Considerations

### Horizontal Scaling

- **API Layer**: Stateless, can scale behind load balancer
- **Workers**: Auto-scaling based on queue depth
- **Database**: Read replicas for query scaling

### Performance Optimization

- **Caching**: Redis for frequently accessed data
- **Batch Processing**: Group similar jobs for efficiency
- **Parallel Processing**: Multi-threaded workers

## Security Architecture

- **API Authentication**: JWT-based tokens
- **Queue Security**: IAM-based access control
- **Data Encryption**: At-rest and in-transit
- **Network Isolation**: VPC with private subnets

## Monitoring & Observability

- **Metrics**: Prometheus + Grafana
- **Logging**: Centralized logging (ELK stack)
- **Tracing**: Distributed tracing (Jaeger)
- **Alerting**: PagerDuty integration

## Technology Stack Summary

| Component | Technology |
|-----------|------------|
| API Gateway | Python (Flask/FastAPI) |
| Message Queue | SQS-compatible |
| Workers | Python + Java |
| Cache | Redis |
| Database | PostgreSQL |
| Object Storage | S3-compatible |
| Infrastructure | Terraform |
| Orchestration | Docker + Kubernetes (optional) |

## Related Documentation

- [High-Level Design](architecture/high-level-design.md)
- [Data Model](architecture/data-model.md)
- [Sequence Diagrams](architecture/sequence-diagram.md)
- [System Overview](docs/system-overview.md)
