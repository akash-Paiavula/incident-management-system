# Architecture Plan

## Goal
Build a resilient, in-memory Incident Management System that can handle high-throughput
signal ingestion, debounce duplicate signals, enforce a strict incident lifecycle,
and present a live SRE dashboard.

## Key Decisions

### 1. Framework — FastAPI over Flask/Django
- Native `async def` support throughout
- Pydantic v2 built-in for schema validation and field-level validators
- Auto OpenAPI docs at `/docs` with zero extra configuration
- `slowapi` integrates natively for rate limiting

### 2. In-Memory First, DB-Shaped
Rather than wiring real databases (which would require Docker services for Mongo,
Postgres, Redis and inflate setup complexity), we simulate the three data stores
as Python dicts with async interfaces that mirror the production DB APIs exactly:
- `db/mongo.py`    → raw signal payloads (NoSQL / data lake)
- `db/postgres.py` → incidents + RCA (relational / SoT)
- `db/redis.py`    → debounce window + dashboard cache (TTL key-value)

Swapping any of these for a real client requires changing only that one file.

### 3. Backpressure — Bounded asyncio.Queue
The ingestion route enqueues signals into a bounded `asyncio.Queue(maxsize=50_000)`.
If the queue is full, `put_nowait()` raises `QueueFull` → the route returns 429.
The background worker drains the queue independently with retry + exponential back-off.
This means the HTTP API never blocks on slow processing.

### 4. Debounce Window — Redis TTL simulation
`active_debounce[component_id]` stores `{incident_id, expires_at}`.
Any signal for the same component within 10 seconds links to the existing incident.
After 10 seconds the window expires and a new signal creates a new incident.
Protected by `asyncio.Lock` to prevent race conditions on concurrent writes.

### 5. State Machine — explicit transition table
`VALID_TRANSITIONS` dict maps each state to its allowed successors.
An extra guard checks for RCA presence before allowing CLOSED.
This makes invalid transitions impossible at the service layer, not just the UI.

### 6. Alert Strategy — pluggable
`AlertStrategy` ABC allows new notification channels (PagerDuty, Slack, OpsGenie)
to be added without touching the ingestion route.
Component → priority mapping is a single dict lookup.

## Data Flow

```
POST /signals/
  │
  ├─► enqueue_signal() → asyncio.Queue
  │
  └─► Worker drains queue
          │
          ├─► db/redis.py  : check/set debounce window (TTL 10s)
          ├─► db/postgres.py: upsert incident (SoT)
          └─► db/mongo.py  : append raw signal payload (data lake)
```