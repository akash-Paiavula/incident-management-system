# Mission-Critical Incident Management System (IMS)

> **Zeotap Infrastructure / SRE Intern Assignment**  
> Candidate: Akash | Submission: May 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Tech Stack Choices & Rationale](#tech-stack-choices--rationale)
4. [Design Patterns Used](#design-patterns-used)
5. [Feature Checklist](#feature-checklist)
6. [How Backpressure is Handled](#how-backpressure-is-handled)
7. [API Reference](#api-reference)
8. [Setup Instructions (Docker Compose)](#setup-instructions-docker-compose)
9. [Sample Data / Mock Failure Script](#sample-data--mock-failure-script)
10. [Unit Tests (RCA Validation)](#unit-tests-rca-validation)
11. [Observability & Metrics](#observability--metrics)
12. [Bonus Features](#bonus-features)
13. [Prompts & Spec Files](#prompts--spec-files)

---

## Overview

The IMS is a real-time, in-memory Incident Management System built to simulate a production SRE workflow. It ingests high-throughput error signals from distributed system components (RDBMS, Cache, MCP Hosts, Async Queues, NoSQL, APIs), applies debounce logic to group related signals into a single Work Item (Incident), and provides a rich React dashboard for tracking the full incident lifecycle — from `OPEN` to `CLOSED` with mandatory Root Cause Analysis (RCA).

Key capabilities:
- Signal ingestion with 10-second debounce window per component
- State-machine-enforced lifecycle transitions (OPEN → INVESTIGATING → RESOLVED → CLOSED)
- Mandatory RCA before `CLOSED` transition is allowed
- Automatic MTTR calculation from RCA timestamps
- Live React dashboard with signal drill-down, RCA form, and status transitions
- Throughput metrics logged every 5 seconds to console
- `/health` endpoint for liveness checks

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
│   React SPA (Vite)  ─── axios ───►  FastAPI REST Backend        │
│   Port 5173                          Port 8000                  │
└────────────────────────────────────┬────────────────────────────┘
                                     │
                         ┌───────────▼───────────┐
                         │    FastAPI App         │
                         │  ┌─────────────────┐  │
                         │  │  Rate Limiting   │  │  (Planned: SlowAPI)
                         │  │  Middleware      │  │
                         │  └────────┬────────┘  │
                         │           │            │
                         │  ┌────────▼────────┐  │
                         │  │  Signal Routes   │  │  POST /signals/
                         │  └────────┬────────┘  │
                         │           │            │
                         │  ┌────────▼────────┐  │
                         │  │ Debounce Service │  │  10s window / component
                         │  │  (Producer)      │  │
                         │  └──┬───────────┬──┘  │
                         │     │           │      │
              ┌──────────▼──┐  │    ┌──────▼───┐ │
              │  Incidents   │  │    │ Raw       │ │
              │  Dict (SoT)  │  │    │ Signals   │ │
              │  (in-memory) │  │    │ Dict(NoSQL│ │
              └──────┬───────┘  │    │ sim.)     │ │
                     │          │    └──────┬────┘ │
              ┌──────▼───────┐  │           │      │
              │ State Machine │  │    ┌──────▼────┐ │
              │  OPEN →       │  │    │ RCA Records│ │
              │  INVESTIGATING│  │    │  Dict     │ │
              │  → RESOLVED  │  │    └───────────┘ │
              │  → CLOSED    │  │                  │
              └──────────────┘  │                  │
                         │      │                  │
                         │  ┌───▼────────────┐     │
                         │  │ Metrics Service │     │
                         │  │ (5s throughput  │     │
                         │  │  logging)       │     │
                         │  └────────────────┘     │
                         └───────────────────────── ┘
                                     │
                         ┌───────────▼───────────┐
                         │   /health   /metrics   │
                         └───────────────────────┘

  Data Separation (Simulated):
  ┌──────────────┬───────────────────────────────────────────────┐
  │ Data Lake    │ raw_signals dict — every raw signal payload   │
  │ (NoSQL sim.) │ queryable per incident_id                     │
  ├──────────────┼───────────────────────────────────────────────┤
  │ Source of    │ incidents dict — structured Work Items +      │
  │ Truth (RDBMS)│ RCA records (transactional writes)            │
  ├──────────────┼───────────────────────────────────────────────┤
  │ Hot-path     │ active_debounce dict — real-time component    │
  │ Cache (Redis)│ window tracking (in-memory Redis simulation)  │
  └──────────────┴───────────────────────────────────────────────┘
```

---

## Tech Stack Choices & Rationale

| Layer | Choice | Rationale |
|---|---|---|
| **Backend framework** | FastAPI (Python 3.11) | Native async support, Pydantic validation, auto OpenAPI docs, excellent performance |
| **Signal ingestion protocol** | HTTP REST (POST JSON) | Universal compatibility, easy to mock; can be upgraded to WebSocket/Kafka for true 10k/s prod |
| **In-memory store** | Python dicts (simulated partitions) | Zero-latency reads, no external dependency for MVP; mirrors Redis/Mongo behavior |
| **State management** | State Pattern via `state_machine.py` | Explicit, testable transition table; rejects invalid sequences at the service layer |
| **Alert differentiation** | Strategy Pattern via `alert_strategy.py` | Pluggable — swap P0 vs P2 logic without modifying caller code |
| **Frontend** | React 18 + Vite | Fast HMR, small bundle, JSX component model ideal for live-updating dashboard |
| **HTTP client** | Axios | Promise-based, interceptor support for future auth/retry |
| **Metrics logging** | Python `threading.Thread` (daemon) | Non-blocking background loop; logs Signals/sec every 5s to stdout |
| **Containerisation** | Docker + Docker Compose | Single-command `docker compose up` spins both services |

### Production Upgrade Path
For true 10,000 signals/sec the in-memory store would be replaced with:
- **MongoDB** (raw signals / NoSQL data lake)
- **PostgreSQL** (incidents / RCA / transactional SoT)
- **Redis** (hot-path dashboard state + debounce window locks)
- **Kafka/NATS** (async ingestion queue with backpressure)

---

## Design Patterns Used

### 1. State Pattern — `backend/app/services/state_machine.py`

Manages the incident lifecycle. The `VALID_TRANSITIONS` dict is the state graph; `validate_status_transition()` enforces it. Invalid transitions (e.g. `OPEN → CLOSED`) return an error before any mutation occurs.

```
OPEN ──► INVESTIGATING ──► RESOLVED ──► CLOSED
                                         ▲
                           (requires RCA before this step)
```

### 2. Strategy Pattern — `backend/app/services/alert_strategy.py`

Different component types trigger different alert priorities:

| Component Type | Priority |
|---|---|
| RDBMS | P0 — Critical |
| MCP_HOST | P0 — Critical |
| CACHE | P2 — Warning |
| ASYNC_QUEUE | P1 — High |
| API | P1 — High |
| NOSQL | P1 — High |

The `AlertStrategy` base class allows future strategies (PagerDuty, Slack, OpsGenie) to be plugged in without changing the signal ingestion code.

### 3. Producer / Consumer — Debounce Service

`process_signal()` acts as the Producer: it receives signals and either creates a new Work Item or links the signal to an existing debounce window. The debounce window (10s per `component_id`) prevents signal storms from creating duplicate incidents.

---

## Feature Checklist

| Requirement | Status |
|---|---|
| Signal ingestion API (POST /signals/) | ✅ |
| Debounce: 100 signals → 1 Work Item (10s) | ✅ |
| Raw signals stored separately (NoSQL sim.) | ✅ |
| Work Items stored in Source of Truth | ✅ |
| State transitions with State Pattern | ✅ |
| Alert priority with Strategy Pattern | ✅ |
| Mandatory RCA before CLOSED | ✅ |
| MTTR auto-calculation | ✅ |
| Throughput metrics every 5s | ✅ |
| /health endpoint | ✅ |
| React Live Feed dashboard | ✅ |
| Incident detail with raw signals | ✅ |
| RCA form (start/end, category, fix, prevention) | ✅ |
| Docker + Docker Compose | ✅ |
| Sample failure simulation script | ✅ |
| Unit tests for RCA validation | ✅ |
| CORS configured | ✅ |
| OpenAPI docs (auto) at /docs | ✅ |

---

## How Backpressure is Handled

### Current Implementation (In-Memory MVP)

Since all state is in Python dicts (in-process), backpressure is handled implicitly:

1. **Debounce Window** — The primary backpressure mechanism. Signals arriving within 10 seconds for the same `component_id` are collapsed into one Incident. A burst of 1,000 signals for `RDBMS_PRIMARY_01` in 10 seconds produces exactly **1 Work Item** with 1,000 linked signal payloads. This prevents both downstream alert fatigue and unbounded dict growth for incidents.

2. **In-Process Dict Writes** — Python dict operations are O(1) and near-zero latency (nanoseconds), so they cannot block or crash under any realistic write rate in a single-process setup. The system will not crash if a hypothetical persistence layer is slow, because persistence is decoupled from the ingestion path.

3. **Metrics Daemon Thread** — The 5-second metrics logger runs in a daemon thread. It is non-blocking and does not slow the ingestion path even under high load.

### Production Backpressure Strategy

In a production setup handling 10,000 signals/sec, the following would be implemented:

```
Producers → [Kafka Topic: raw-signals] → Consumer Group (workers)
                  │
           Bounded buffer
           (kafka retention)
                  │
           [Debounce Worker]
                  │
           MongoDB (raw signals)
           PostgreSQL (incidents)
           Redis (debounce window)
```

- **Kafka** provides a bounded, durable buffer. If the DB is slow, Kafka absorbs the burst without crashing the ingestion API.
- **Redis** holds the debounce window state (TTL-keyed per `component_id`), surviving worker restarts.
- **Rate limiter** (e.g., `slowapi` token-bucket) on the ingestion HTTP endpoint prevents a single bad client from saturating the API.
- **Worker retry loop** with exponential back-off handles transient DB write failures.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Root health ping |
| `GET` | `/health` | Liveness check |
| `GET` | `/metrics` | Signal throughput + incident counts |
| `POST` | `/signals/` | Ingest a new signal |
| `GET` | `/incidents/` | List all incidents |
| `GET` | `/incidents/{id}` | Get incident + raw signals + RCA |
| `PATCH` | `/incidents/{id}/status` | Transition incident state |
| `POST` | `/rca/{incident_id}` | Submit RCA record |
| `GET` | `/rca/{incident_id}` | Retrieve RCA for incident |

Full interactive API docs available at `http://localhost:8000/docs` after startup.

### Signal Payload Example

```json
{
  "component_id": "RDBMS_PRIMARY_01",
  "component_type": "RDBMS",
  "severity": "P0",
  "message": "Database connection timeout",
  "timestamp": "2026-04-30T10:00:00",
  "metadata": {
    "host": "db-primary-01",
    "error_code": "ECONNREFUSED"
  }
}
```

### RCA Payload Example

```json
{
  "incident_start": "2026-04-30T10:00:00",
  "incident_end": "2026-04-30T11:30:00",
  "root_cause_category": "Database",
  "fix_applied": "Restarted PostgreSQL service and increased max_connections from 100 to 500",
  "prevention_steps": "Added PgBouncer connection pooler, enabled CloudWatch alarms for connection saturation"
}
```

---

## Setup Instructions (Docker Compose)

### Prerequisites

- Docker Desktop ≥ 24.x
- Docker Compose v2 (included with Docker Desktop)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/<your-username>/zeotap-ims-assignment.git
cd zeotap-ims-assignment

# Start both services
docker compose up --build

# Services:
#   Backend  → http://localhost:8000
#   Frontend → http://localhost:5173
#   API Docs → http://localhost:8000/docs
```

### Local Development (without Docker)

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### docker-compose.yml

```yaml
version: "3.9"
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    depends_on:
      - backend
```

---

## Sample Data / Mock Failure Script

The file `scripts/mock_failure.py` simulates an RDBMS outage followed by an MCP Host failure, then demonstrates the full lifecycle including RCA submission.

```bash
# Run the simulation (backend must be running)
cd scripts
python mock_failure.py
```

### What the script does:

1. Sends 5 RDBMS signals in rapid succession → 1 Work Item created (debounce), 4 linked
2. Waits 12 seconds (outside debounce window)
3. Sends 3 MCP_HOST signals → new Work Item created
4. Transitions RDBMS incident: OPEN → INVESTIGATING → RESOLVED
5. Submits RCA for RDBMS incident
6. Transitions RDBMS incident to CLOSED (now allowed — RCA present)
7. Attempts CLOSED without RCA on MCP incident → rejected with 400 error (demonstrates validation)

### Sample JSON (single RDBMS signal):

```json
{
  "component_id": "RDBMS_PRIMARY_01",
  "component_type": "RDBMS",
  "severity": "P0",
  "message": "Database connection timeout — max connections exceeded",
  "timestamp": "2026-04-30T10:00:00",
  "metadata": {
    "host": "db-primary-01.prod",
    "error_code": "53300",
    "db_engine": "postgresql"
  }
}
```

---

## Unit Tests (RCA Validation)

Tests are in `backend/app/tests/test_rca_validation.py`.

```bash
cd backend
pip install pytest
pytest app/tests/ -v
```

### Test Cases Covered:

| Test | Validates |
|---|---|
| `test_valid_rca` | A complete, well-formed RCA is accepted |
| `test_empty_root_cause` | Empty `root_cause_category` raises `ValidationError` |
| `test_empty_fix_applied` | Empty `fix_applied` raises `ValidationError` |
| `test_empty_prevention_steps` | Empty `prevention_steps` raises `ValidationError` |
| `test_end_before_start` | `incident_end ≤ incident_start` raises `ValidationError` |
| `test_end_equals_start` | `incident_end == incident_start` raises `ValidationError` |
| `test_whitespace_only_fields` | Whitespace-only strings are treated as empty |
| `test_close_without_rca` | Transition to CLOSED without RCA returns 400 |
| `test_invalid_state_transition` | OPEN → CLOSED skipping steps is rejected |

---

## Observability & Metrics

### Console Metrics (every 5 seconds)

```
[METRICS] Signals/sec: 42.80 | Total Signals: 214
[METRICS] Signals/sec: 0.00  | Total Signals: 214
```

### `/metrics` Endpoint

```json
{
  "total_signals_processed": 214,
  "total_incidents": 3,
  "active_incidents": 1,
  "closed_incidents": 2
}
```

### `/health` Endpoint

```json
{
  "status": "healthy",
  "service": "ims-backend"
}
```

---

## Bonus Features

- **OpenAPI / Swagger UI** — Auto-generated interactive docs at `/docs`
- **CORS correctly scoped** — Only `localhost:5173` (frontend origin) is whitelisted
- **Pydantic field validators** — Server-side enforcement of RCA completeness with descriptive error messages
- **Daemon metrics thread** — Zero overhead background logging; terminates automatically when the main process exits
- **Responsive UI** — Dashboard adapts to mobile viewport via CSS media queries
- **Signal drill-down** — Click any signal card in the UI to expand the full raw JSON payload
- **MTTR displayed in minutes** — Converted from seconds for human readability in the dashboard

---

## Prompts & Spec Files

All planning documents, architectural prompts, and AI-assisted design notes are checked in under `docs/prompts/`:

- `docs/prompts/01_architecture_plan.md` — Initial system design decisions
- `docs/prompts/02_backend_design.md` — FastAPI route and service layer planning
- `docs/prompts/03_frontend_design.md` — React component breakdown
- `docs/prompts/04_testing_strategy.md` — Test case design notes

---

## Repository Structure

```
zeotap-ims-assignment/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, CORS, routes, /health, /metrics
│   │   ├── routes/
│   │   │   ├── signal_routes.py     # POST /signals/
│   │   │   ├── incident_routes.py   # GET/PATCH /incidents/
│   │   │   └── rca_routes.py        # POST/GET /rca/
│   │   ├── services/
│   │   │   ├── debounce_service.py  # Core ingestion + debounce logic
│   │   │   ├── state_machine.py     # State Pattern: lifecycle transitions
│   │   │   ├── alert_strategy.py    # Strategy Pattern: priority mapping
│   │   │   └── metrics_service.py   # Background throughput logger
│   │   ├── schemas/
│   │   │   ├── signal_schema.py     # Pydantic signal model
│   │   │   └── rca_schema.py        # Pydantic RCA model with validators
│   │   └── tests/
│   │       └── test_rca_validation.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # Main dashboard component
│   │   ├── api/api.js               # Axios base client
│   │   ├── index.css                # Dark-mode SRE theme
│   │   └── main.jsx                 # React root
│   ├── Dockerfile
│   ├── index.html
│   └── package.json
├── scripts/
│   └── mock_failure.py              # RDBMS + MCP failure simulation
├── docs/
│   └── prompts/                     # Design notes and AI prompts used
├── docker-compose.yml
└── README.md                        # ← You are here
```
