# 🇪🇸 SPAIN-REC — Agentic Tourism Recommendation System

An intelligent, agentic AI system that delivers hyper-personalised visit recommendations to tourists who have already experienced Spain. Built as a production-grade reference implementation of multi-agent AI architecture.

## Architecture Overview

SPAIN-REC combines three persistence layers, a streaming backbone, and a multi-agent AI pipeline:

```
[ Synthetic Data Generator ]
           |
    -------+-------
    |               |
    v               v
[ Kafka ]      [ PostgreSQL ]     <- Bronze: raw events + seed data
    |
    v
[ Data Processor ]                <- Silver: Pydantic v2 validated
    |
  --+--
  |     |
  v     v
[Neo4j] [Qdrant/Pinecone]         <- Gold: graph + vector store
```

**Agent topology (LangGraph orchestrated):**

```
[ Orchestrator ]  <-  LangGraph StateGraph
   /     |     \
  v      v      v
[Profile] [Cohort] [Destination]  <-  Specialist agents
   \      |      /
    v     v     v
  [ Recommendation Synthesiser ]  <-  CrewAI crew
           |
    [ HITL Review Node ]          <-  Human approval gate
           |
    [ Notification Agent ]
           |
    [ FastAPI Endpoint ]
```

## Technology Stack

| Layer | Technology | Licence |
|-------|-----------|---------|
| Streaming | Apache Kafka | Apache 2.0 |
| Orchestration | LangGraph | MIT |
| Agent Framework | LangChain | MIT |
| Multi-Agent | CrewAI | MIT |
| Workflow Automation | n8n | Sustainable Use |
| Graph DB | Neo4j Community | GPL-3.0 |
| Vector Store (local) | Qdrant | Apache 2.0 |
| Vector Store (cloud) | Pinecone | Free tier |
| Relational DB | PostgreSQL | PostgreSQL Licence |
| Schema Migrations | Alembic | MIT |
| REST API | FastAPI | MIT |
| Data Validation | Pydantic v2 | MIT |
| LLM Inference | Groq API | Free tier |
| Embeddings | HuggingFace | Apache 2.0 |
| Synthetic Data | Faker | MIT |
| Observability | LangSmith | Free tier |
| Testing | pytest + pytest-asyncio | MIT |

## Prerequisites

- Docker Desktop (Windows) or Docker Engine (Linux)
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- `make` (Linux native; Windows via Git Bash or WSL)
- Git + GitHub Personal Access Token (PAT) with `repo` scope

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/mgalanme/spain-rec.git
cd spain-rec
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your API keys:
# GROQ_API_KEY, LANGSMITH_API_KEY, PINECONE_API_KEY, HF_TOKEN
```

### 3. Create Python environment

```bash
make setup
source .venv-langchain/bin/activate   # Linux / Git Bash
# Windows PowerShell: .venv-langchain\Scripts\activate
```

### 4. Start infrastructure

```bash
make start        # Core services: Kafka, Neo4j, PostgreSQL, Qdrant
make start-full   # Full stack: adds n8n and Redis
```

### 5. Verify connectivity

```bash
python3 scripts/verify_connections.py
```

Expected output:

```
Testing Neo4j...      Neo4j OK
Testing PostgreSQL... PostgreSQL OK
Testing Qdrant...     Qdrant OK - 0 collections
Testing Kafka...      Kafka OK - 0 topics
All connections OK
```

### 6. Run database migrations

```bash
make migrate
```

### 7. Generate synthetic data

```bash
make seed
```

### 8. Run the recommendation pipeline

```bash
make recommend
```

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make setup` | Create virtual environments and install dependencies |
| `make start` | Start core infrastructure (Kafka, Neo4j, PostgreSQL, Qdrant) |
| `make start-full` | Start full stack (adds n8n, Redis) |
| `make stop` | Stop all services |
| `make restart` | Stop and restart core profile |
| `make migrate` | Run Alembic migrations against PostgreSQL |
| `make seed` | Run synthetic data generator |
| `make ingest` | Run Kafka consumers to populate graph and vector store |
| `make recommend` | Trigger a sample recommendation cycle |
| `make test` | Run pytest suite |
| `make lint` | Run ruff linter |
| `make clean` | Stop containers and remove volumes (destructive) |

## Infrastructure Services

| Service | Port | UI |
|---------|------|----|
| Kafka | 9092 | - |
| Neo4j | 7474 / 7687 | http://localhost:7474 |
| PostgreSQL | 5432 | - |
| Qdrant | 6333 | http://localhost:6333/dashboard |
| FastAPI | 8000 | http://localhost:8000/docs |
| n8n | 5678 | http://localhost:5678 |

## Windows Notes

Claude Code CLI runs natively on Windows. However, `make` targets require a Unix-like shell. Use **Git Bash** or **WSL** to run `make` commands. Both invocation paths are supported.

## Project Structure

```
spain-rec/
├── .github/workflows/     # CI actions (lint, test)
├── docs/
│   ├── adr/               # Architecture Decision Records
│   └── diagrams/          # Architecture diagrams
├── docker/
│   └── docker-compose.yml # All services with profiles
├── data/
│   └── generator/         # Synthetic data generator
├── src/
│   ├── pipeline/          # Kafka producers, consumers, Silver processor
│   ├── graph/             # Neo4j models and Cypher queries
│   ├── vector/            # Vector store abstraction (Qdrant/Pinecone)
│   ├── db/                # PostgreSQL models, Alembic migrations
│   ├── agents/            # LangGraph orchestrator and specialist agents
│   ├── crew/              # CrewAI synthesiser crew
│   └── api/               # FastAPI application
├── tests/
│   ├── unit/
│   └── integration/
├── n8n/workflows/         # Exported n8n workflow JSON files
├── Makefile
├── pyproject.toml
├── .env.example
└── README.md
```

## Developer Tooling

### Claude Code

```bash
# Generate a new LangGraph node
claude "Implement a LangGraph node that queries Neo4j for tourist visit history
        and returns a Pydantic v2 TouristProfile model"

# Scaffold a CrewAI agent
claude "Create a CrewAI agent for cultural context analysis with tools for
        querying the destinations-index in Qdrant"
```

### Claude Cowork

Used for collaborative review of generated code, architecture decisions, and documentation directly from the desktop.

## Known Configuration Notes

- Neo4j requires `NEO4J_PLUGINS=["apoc"]` in Docker environment — already set in `docker-compose.yml`
- Use `enhanced_schema=False` in `Neo4jGraph` constructor to avoid schema inference overhead
- Groq free tier limits vary by model — consult [Groq documentation](https://console.groq.com/docs/rate-limits)
- `llama3` (Ollama) does not support function calling — use `llama3.1` or later
- GitHub authentication requires a PAT over HTTPS, not a web password

## Licence

MIT — see [LICENSE](LICENSE)

---

*Maintained by Martin Galan — Enterprise Architect | Data Architect | AI Architect*

## Running the Pipeline

### CLI mode (with interactive HITL)

```bash
source .venv-langchain/bin/activate

# Random tourist
PYTHONPATH=. python3 src/agents/run.py

# Specific tourist
PYTHONPATH=. python3 src/agents/run.py <tourist_id>
```

### API mode (auto-approve, no HITL prompt)

```bash
# Start the API server
PYTHONPATH=. uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# In a second terminal:

# Trigger a recommendation
curl -s -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{}'

# Poll status
curl -s http://localhost:8000/recommend/status/<run_id>

# List tourists
curl -s "http://localhost:8000/tourists?limit=5"

# List destinations
curl -s http://localhost:8000/destinations
```

Interactive API docs available at: http://localhost:8000/docs

### Data pipeline

```bash
# Generate synthetic data (seeds PostgreSQL + publishes to Kafka)
PYTHONPATH=. python3 data/generator/generate.py

# Ingest into Neo4j and Qdrant
PYTHONPATH=. python3 src/pipeline/ingest.py

# Verify all connections
python3 scripts/verify_connections.py
```
