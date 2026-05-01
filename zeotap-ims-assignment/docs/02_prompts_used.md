# Prompts & AI Assistance Log

This file documents all AI tool usage during the development of this assignment,
as required by the submission guidelines ("open-book test — free to use any GPT tool").

---

## Tool Used
Claude (Anthropic) — claude.ai

---

## Prompts Used

### 1. Initial architecture design
> "I have an engineering assignment to build a Mission-Critical Incident Management System.
> It needs to handle 10,000 signals/sec, debounce signals per component within 10 seconds,
> manage a OPEN→INVESTIGATING→RESOLVED→CLOSED lifecycle with mandatory RCA, and provide
> a React dashboard. What tech stack and architecture would you recommend for a Python backend?"

**Output used:** Tech stack decision (FastAPI + React + Vite), three-dict data separation
strategy, asyncio.Queue for backpressure, State + Strategy pattern recommendations.

---

### 2. Backend service layer design
> "Help me design the debounce service, state machine, and alert strategy for the IMS backend.
> Use the State pattern for lifecycle and Strategy pattern for alert priority."

**Output used:** `state_machine.py` VALID_TRANSITIONS structure, `alert_strategy.py`
ABC + concrete strategy classes, `debounce_service.py` core logic.

---

### 3. Frontend dashboard design
> "Build a production-quality React SRE dashboard with dark mode, live polling every 5 seconds,
> incident list with severity badges, signal drill-down, RCA form with validation, and
> state transition buttons. Use CSS custom properties for theming."

**Output used:** `App.jsx` component structure, `index.css` design token system,
`useInterval` custom hook, toast notification system.

---

### 4. Missing file completion
> "Review my IMS project codebase. Several files are empty:
> alert_strategy.py, worker.py, db/mongo.py, db/postgres.py, db/redis.py,
> models/incident.py, models/rca.py, schemas/incident_schema.py.
> Generate complete implementations for all of them."

**Output used:** All 8 files listed above, plus updated `main.py` with `slowapi`
rate limiting and worker startup/shutdown lifecycle hooks.

---

### 5. Testing and documentation
> "Generate 15 unit tests for the RCA validation logic covering schema validation,
> service-layer enforcement, debounce behaviour, and state transitions.
> Also generate a comprehensive README with architecture diagram, setup instructions,
> backpressure explanation, and API reference."

**Output used:** `test_rca_validation.py` (15 tests), `README.md`, `mock_failure.py`,
`docker-compose.yml`.

---

## What was built manually (not AI-generated)
- Initial project structure and folder layout
- FastAPI route wiring (`signal_routes.py`, `incident_routes.py`, `rca_routes.py`)
- Pydantic schemas (`signal_schema.py`, `rca_schema.py`)
- Frontend component layout decisions and UX flow
- Docker configuration (`backend/Dockerfile`, `frontend/Dockerfile`)
- Integration testing (running `docker compose up` and verifying end-to-end flow)