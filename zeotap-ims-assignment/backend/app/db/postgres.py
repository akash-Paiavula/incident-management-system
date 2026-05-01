"""
PostgreSQL Layer — Source of Truth (Work Items + RCA)
======================================================
Stores structured Incidents and RCA records with transactional guarantees.
All state transitions write here first — this is the authoritative store.

Current implementation: in-memory dict simulation (drop-in replacement ready).
Production upgrade: swap with asyncpg + SQLAlchemy Core for full ACID transactions.

Tables (simulated):
  incidents  — one row per Work Item
  rca        — one row per RCA, FK → incidents.incident_id
"""

import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ── In-memory stores (simulate PostgreSQL tables) ─────────────────────────────
_incidents: dict[str, dict] = {}
_rca:       dict[str, dict] = {}


# ── Incidents table ───────────────────────────────────────────────────────────

async def upsert_incident(incident_data: dict) -> bool:
    """
    Insert or update an incident row.
    Equivalent to: INSERT INTO incidents ... ON CONFLICT (incident_id) DO UPDATE SET ...
    Transactional: if this raises, the caller retries via worker.py back-off.
    """
    try:
        incident_id = incident_data["incident_id"]
        incident_data["_updated_at"] = datetime.utcnow().isoformat()
        _incidents[incident_id] = incident_data
        logger.debug(f"[POSTGRES] Upserted incident {incident_id}")
        return True
    except Exception as exc:
        logger.error(f"[POSTGRES] Failed to upsert incident: {exc}")
        raise  # let the retry wrapper in worker.py handle it


async def get_incident(incident_id: str) -> Optional[dict]:
    """SELECT * FROM incidents WHERE incident_id = $1"""
    return _incidents.get(incident_id)


async def get_all_incidents() -> list[dict]:
    """SELECT * FROM incidents ORDER BY created_at DESC"""
    return sorted(
        _incidents.values(),
        key=lambda i: i.get("created_at", ""),
        reverse=True
    )


async def update_incident_status(incident_id: str, new_status: str) -> bool:
    """
    Atomic status update.
    Equivalent to: UPDATE incidents SET status=$1, _updated_at=$2 WHERE incident_id=$3
    """
    if incident_id not in _incidents:
        return False
    _incidents[incident_id]["status"] = new_status
    _incidents[incident_id]["_updated_at"] = datetime.utcnow().isoformat()
    return True


async def update_incident_mttr(incident_id: str, mttr_seconds: int) -> bool:
    """Write MTTR back to the incident row after RCA submission."""
    if incident_id not in _incidents:
        return False
    _incidents[incident_id]["mttr_seconds"] = mttr_seconds
    _incidents[incident_id]["rca_submitted"] = True
    return True


# ── RCA table ─────────────────────────────────────────────────────────────────

async def insert_rca(rca_data: dict) -> bool:
    """
    Insert an RCA record.
    Equivalent to: INSERT INTO rca (...) VALUES (...)
    Transactional — raises on failure so worker.py retries.
    """
    try:
        incident_id = rca_data["incident_id"]
        rca_data["_submitted_at"] = datetime.utcnow().isoformat()
        _rca[incident_id] = rca_data
        logger.debug(f"[POSTGRES] Inserted RCA for incident {incident_id}")
        return True
    except Exception as exc:
        logger.error(f"[POSTGRES] Failed to insert RCA: {exc}")
        raise


async def get_rca(incident_id: str) -> Optional[dict]:
    """SELECT * FROM rca WHERE incident_id = $1"""
    return _rca.get(incident_id)


async def rca_exists(incident_id: str) -> bool:
    """SELECT EXISTS(SELECT 1 FROM rca WHERE incident_id = $1)"""
    return incident_id in _rca


def get_store_stats() -> dict:
    return {
        "total_incidents": len(_incidents),
        "total_rca_records": len(_rca),
        "closed_incidents": sum(1 for i in _incidents.values() if i.get("status") == "CLOSED"),
    }