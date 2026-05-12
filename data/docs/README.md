# AI Assistant Demo Repository v2

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Java 17+](https://img.shields.io/badge/java-17+-orange.svg)](https://www.oracle.com/java/)

## Overview

A **production-grade hybrid architecture** demonstration project showcasing modern software engineering practices with polyglot microservices, event-driven design, and asynchronous processing patterns.

### Key Features

✅ **Hybrid Architecture**: REST API + Event-Driven Processing  
✅ **Polyglot Microservices**: Python + Java services  
✅ **Async Processing**: SQS-style queue-based workflows  
✅ **Batch Comparison Engine**: High-performance diff computation  
✅ **Infrastructure as Code**: Terraform deployment automation  
✅ **Comprehensive Testing**: Unit, integration, and E2E tests  

---

## Architecture

### System Components

```
┌────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                          │
│              (Web/Mobile/API Clients)                    │
└──────────────────────┬─────────────────────────────────┘
                       │ HTTPS
                       ▼
┌────────────────────────────────────────────────────────┐
│                    API GATEWAY                           │
│              Python (Flask/FastAPI)                      │
│         POST /process | GET /status/{id}                │
└──────────────────────┬─────────────────────────────────┘
                       │ Publish Event
                       ▼
┌────────────────────────────────────────────────────────┐
│                 MESSAGE QUEUE LAYER                       │
│              SQS-Style Event Bus                         │
│   [Ingestion] [Processing] [Comparison] [Notification]   │
└──────────────────────┬─────────────────────────────────┘
                       │ Consume
                       ▼
┌────────────────────────────────────────────────────────┐
│                 PROCESSING LAYER                          │
│   ┌─────────────────┐   ┌─────────────────┐       │
│   │ Python Workers  │   │  Java Workers   │       │
│   │ (Orchestration) │   │ (Diff Engine)  │       │
│   └─────────────────┘   └─────────────────┘       │
└──────────────────────┬─────────────────────────────────┘
                       │ Store
                       ▼
┌────────────────────────────────────────────────────────┐
│                  STORAGE LAYER                            │
│   [Redis Cache] [PostgreSQL] [S3 Object Storage]         │
└────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|------------|
| **API** | Python 3.9+ (Flask/FastAPI) |
| **Workers** | Python + Java 17 |
| **Queue** | SQS-compatible message broker |
| **Cache** | Redis 7+ |
| **Database** | PostgreSQL 14+ |
| **Storage** | S3-compatible object storage |
| **IaC** | Terraform 1.5+ |
| **Testing** | pytest, JUnit 5 |

---

## Quick Start

### Prerequisites

- **Python** 3.9 or higher
- **Java** 17 or higher
- **Docker** & Docker Compose (for local development)
- **Terraform** 1.5+ (for infrastructure)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/ai-assistant-demo-v2.git
cd ai-assistant-demo-v2

# Set up Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Build Java service
cd java-service
./mvnw clean install
cd ..

# Start local infrastructure (Redis, PostgreSQL, Queue)
docker-compose up -d

# Run database migrations
python scripts/migrate.py

# Start the API server
python src/main.py
```

### Running Tests

```bash
# Python tests
pytest tests/ -v --cov=src

# Java tests
cd java-service
./mvnw test
```

---

## Project Structure

```
.
├── src/                      # Python source code
│   ├── api.py                # REST API endpoints
│   ├── ingestion.py          # File ingestion logic
│   ├── processor.py          # Async job processor
│   ├── comparator.py         # Comparison engine
│   ├── storage.py            # Storage abstraction
│   └── utils/                # Utility modules
│       ├── diff_utils.py     # Diff algorithms
│       └── normalization.py  # Data normalization
├── java-service/             # Java microservice
│   └── src/main/java/
│       └── com/example/
│           ├── App.java
│           └── controller/
├── tests/                    # Test suites
│   ├── test_ingestion.py
│   └── test_comparator.py
├── infra/                    # Infrastructure as Code
│   └── terraform/
│       ├── main.tf
│       └── variables.tf
├── config/                   # Configuration files
│   ├── settings.yaml
│   └── logging.yaml
├── data/                     # Sample data
│   ├── sample_input_1.json
│   └── sample_input_2.json
├── docs/                     # Documentation
│   ├── architecture/
│   └── docs/
├── docker-compose.yml        # Local dev environment
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

---

## API Documentation

### Submit File for Processing

```http
POST /process
Content-Type: application/json

{
  "file_id": "abc123",
  "location": "s3://bucket/path/to/file.json"
}
```

**Response:**
```json
{
  "job_id": "job-uuid-1234",
  "status": "submitted",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Check Job Status

```http
GET /status/{job_id}
```

**Response:**
```json
{
  "job_id": "job-uuid-1234",
  "status": "completed",
  "result": {
    "match": false,
    "differences": [...]
  }
}
```

See [API Contracts](docs/api-contracts.md) for complete API documentation.

---

## Key Concepts

### Async Processing Flow

1. **Client** submits file via REST API
2. **API Gateway** validates request and publishes to ingestion queue
3. **Ingestion Worker** downloads file and publishes to processing queue
4. **Processing Worker** normalizes data and publishes to comparison queue
5. **Comparison Worker** (Java) performs high-performance diff
6. **Storage Layer** persists results
7. **Client** polls for results via `/status/{job_id}`

### Data Normalization

Before comparison, all data undergoes normalization:
- Whitespace trimming and standardization
- Numeric precision normalization
- String encoding standardization
- Structural canonicalization

See [Architecture Decisions](DECISIONS.md) for rationale.

---

## Deployment

### Local Development

```bash
docker-compose up -d
python src/main.py
```

### Production (AWS)

```bash
cd infra/terraform
terraform init
terraform plan
terraform apply
```

See [Infrastructure Documentation](infra/README.md) for details.

---

## Documentation

- **[Architecture Overview](ARCHITECTURE.md)** - System architecture and design
- **[Architecture Decisions](DECISIONS.md)** - ADRs and design rationale
- **[Roadmap](ROADMAP.md)** - Feature roadmap and versioning
- **[System Overview](docs/system-overview.md)** - Detailed system documentation
- **[API Contracts](docs/api-contracts.md)** - API specifications
- **[Data Model](architecture/data-model.md)** - Database schema and entities

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 for Python code
- Follow Google Java Style Guide for Java code
- Write tests for new features
- Update documentation as needed
- Ensure all tests pass before submitting PR

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Support

For questions or issues:
- **GitHub Issues**: [Create an issue](https://github.com/your-org/ai-assistant-demo-v2/issues)
- **Email**: support@your-org.com
- **Slack**: #ai-assistant-demo

---

## Acknowledgments

- Built with modern software engineering best practices
- Inspired by industry-standard microservices patterns
- Leverages open-source technologies and frameworks

---

**Version**: 2.0.0  
**Last Updated**: 2024-Q4  
**Status**: 🟢 Active Development
