# Architecture Decision Records (ADR)

## Overview

This document captures key architectural decisions made during the design and implementation of the system. Each decision is documented with context, options considered, and rationale.

---

## ADR-001: Asynchronous Processing Architecture

**Status**: ✅ Accepted

**Date**: 2024-Q4

**Context**

The system needs to process large files and perform complex comparisons that can take significant time (minutes to hours). Initial synchronous API design led to:
- HTTP timeout issues (30-60 second limits)
- Poor user experience with long-running requests
- Difficulty scaling processing capacity
- Resource contention under load

**Decision**

Implement **queue-based asynchronous processing** using an SQS-style message queue architecture.

**Options Considered**

1. **Synchronous REST API** (rejected)
   - ✗ HTTP timeouts for long operations
   - ✗ Poor scalability
   - ✓ Simple implementation

2. **WebSocket Streaming** (rejected)
   - ✓ Real-time updates
   - ✗ Complex client implementation
   - ✗ Connection management overhead

3. **Queue-Based Async** (selected)
   - ✓ Decouples API from processing
   - ✓ Horizontal scaling of workers
   - ✓ Built-in retry mechanisms
   - ✓ Industry-standard pattern
   - ✗ Slightly more complex architecture

**Rationale**

- **Scalability**: Workers can scale independently based on queue depth
- **Resilience**: Failed jobs can be retried automatically
- **User Experience**: Immediate job submission with async status polling
- **Resource Efficiency**: Better resource utilization with worker pools
- **Industry Standard**: Well-understood pattern with mature tooling

**Consequences**

- ✅ System can handle long-running operations gracefully
- ✅ Improved scalability and resilience
- ✅ Better separation of concerns
- ⚠️ Requires queue infrastructure (SQS, RabbitMQ, etc.)
- ⚠️ Clients must implement polling or webhooks for results
- ⚠️ Increased operational complexity

**Implementation Details**

```python
# API submits job to queue
def process_file(file_id):
    job_id = generate_job_id()
    queue.publish('ingestion-queue', {
        'job_id': job_id,
        'file_id': file_id,
        'timestamp': now()
    })
    return {'job_id': job_id, 'status': 'submitted'}

# Worker processes job asynchronously
def worker():
    while True:
        job = queue.consume('ingestion-queue')
        process_job(job)
        queue.ack(job)
```

---

## ADR-002: Data Normalization Before Comparison

**Status**: ✅ Accepted

**Date**: 2024-Q4

**Context**

When comparing outputs from two different systems, we encountered:
- **Format Variations**: Different whitespace, line endings, encoding
- **Semantic Equivalence**: Same data in different representations (e.g., `1.0` vs `1.00`)
- **False Positives**: Trivial differences flagged as significant
- **Inconsistent Results**: Same logical data marked as different

**Decision**

Implement **mandatory normalization step** before performing diff operations.

**Options Considered**

1. **Raw Comparison** (rejected)
   - ✓ Simple implementation
   - ✓ Preserves exact differences
   - ✗ High false positive rate
   - ✗ Noise in diff results

2. **Configurable Normalization** (rejected)
   - ✓ Flexible for different use cases
   - ✗ Complex configuration management
   - ✗ Inconsistent results across jobs

3. **Mandatory Normalization** (selected)
   - ✓ Consistent, predictable results
   - ✓ Reduces false positives
   - ✓ Focuses on semantic differences
   - ✗ May hide some edge cases

**Rationale**

- **Accuracy**: Focus on meaningful differences, not formatting
- **Consistency**: Same normalization rules applied to all comparisons
- **User Experience**: Cleaner diff output with less noise
- **Semantic Focus**: Compare intent, not representation

**Normalization Rules**

1. **Whitespace Normalization**
   - Trim leading/trailing whitespace
   - Normalize multiple spaces to single space
   - Standardize line endings (LF)

2. **Numeric Normalization**
   - Convert to standard precision (e.g., 2 decimal places)
   - Handle scientific notation
   - Normalize `1.0` ≈ `1.00`

3. **String Normalization**
   - Case normalization (configurable)
   - Unicode normalization (NFC)
   - Remove BOM markers

4. **Structural Normalization**
   - Sort object keys (for JSON)
   - Canonical formatting
   - Remove comments (if applicable)

**Consequences**

- ✅ Significantly reduced false positives (>80% reduction)
- ✅ More meaningful diff results
- ✅ Consistent comparison behavior
- ⚠️ May miss some edge cases where formatting matters
- ⚠️ Additional processing overhead (~10-15%)
- ⚠️ Need to document normalization rules clearly

**Implementation**

```python
def normalize(data):
    """Apply normalization rules before comparison."""
    data = normalize_whitespace(data)
    data = normalize_numbers(data)
    data = normalize_strings(data)
    data = normalize_structure(data)
    return data

def compare(system_a_output, system_b_output):
    """Compare outputs with normalization."""
    normalized_a = normalize(system_a_output)
    normalized_b = normalize(system_b_output)
    return diff(normalized_a, normalized_b)
```

---

## ADR-003: Polyglot Microservices (Python + Java)

**Status**: ✅ Accepted

**Date**: 2024-Q4

**Context**

Different components have different performance and ecosystem requirements:
- API and orchestration benefit from Python's rapid development
- Diff algorithms require high-performance computation
- Need to integrate with existing Java enterprise systems

**Decision**

Implement a **polyglot architecture** with Python for orchestration and Java for compute-intensive tasks.

**Rationale**

- **Best Tool for the Job**: Use each language's strengths
- **Performance**: Java for CPU-intensive diff computation
- **Productivity**: Python for rapid API development
- **Integration**: Java for enterprise system connectivity

**Consequences**

- ✅ Optimal performance for each component
- ✅ Leverage best libraries in each ecosystem
- ⚠️ Increased operational complexity
- ⚠️ Multiple deployment pipelines
- ⚠️ Team skill requirements

---

## ADR-004: Structural Diff First, Semantic Diff Later

**Status**: ✅ Accepted (Phase 1)

**Date**: 2024-Q4

**Context**

Two types of diff are needed:
- **Structural Diff**: Line-by-line, character-level differences
- **Semantic Diff**: Meaning-based differences (e.g., code refactoring)

**Decision**

Implement **structural diff in Phase 1**, defer semantic diff to Phase 2.

**Rationale**

- Structural diff provides immediate value
- Semantic diff requires ML/NLP capabilities
- Phased approach reduces initial complexity
- Can validate architecture with simpler implementation

**Consequences**

- ✅ Faster time to market
- ✅ Simpler initial implementation
- ⚠️ Limited to syntactic differences initially
- 🔄 Semantic diff planned for v2.0

---

## Decision Log Summary

| ADR | Decision | Status | Impact |
|-----|----------|--------|--------|
| ADR-001 | Async Processing | ✅ Accepted | High |
| ADR-002 | Normalization Before Diff | ✅ Accepted | High |
| ADR-003 | Polyglot Services | ✅ Accepted | Medium |
| ADR-004 | Structural Diff First | ✅ Accepted | Medium |

---

## Future Decisions

### Under Consideration

- **ADR-005**: Kubernetes vs. Serverless deployment
- **ADR-006**: GraphQL vs. REST for API v2
- **ADR-007**: Event sourcing for audit trail

### Deferred

- Real-time WebSocket notifications
- ML-based semantic diff
- Multi-region deployment

---

## References

- [Architecture Overview](ARCHITECTURE.md)
- [System Design](architecture/high-level-design.md)
- [Implementation Details](docs/system-overview.md)
