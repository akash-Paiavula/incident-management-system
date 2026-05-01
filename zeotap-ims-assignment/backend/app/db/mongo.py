"""
MongoDB Layer — Raw Signal Store (Data Lake / NoSQL Sink)
==========================================================
Stores high-volume raw signal payloads — the audit log for every signal.
Designed to be queryable by incident_id.

Current implementation: in-memory dict simulation (drop-in replacement ready).
Production upgrade: swap _store with a real Motor (async MongoDB) client.

Collection schema:
  {
    incident_id: str   (partition key)
    signals:     list  (array of raw signal dicts)
  }
"""

import logging
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ── In-memory store (simulates MongoDB collection) ────────────────────────────
# In production: replace with Motor AsyncIOMotorClient
_store: dict[str, list] = {}


async def insert_signal(incident_id: str, signal_data: dict) -> bool:
    """
    Append a raw signal payload to the incident's signal array.
    Equivalent to: db.raw_signals.updateOne(
        { incident_id }, { $push: { signals: signal_data } }, { upsert: true }
    )
    """
    try:
        signal_data["_stored_at"] = datetime.utcnow().isoformat()
        if incident_id not in _store:
            _store[incident_id] = []
        _store[incident_id].append(signal_data)
        return True
    except Exception as exc:
        logger.error(f"[MONGO] Failed to insert signal for {incident_id}: {exc}")
        return False


async def get_signals_by_incident(incident_id: str) -> List[dict]:
    """
    Retrieve all raw signals linked to an incident.
    Equivalent to: db.raw_signals.findOne({ incident_id })
    """
    return _store.get(incident_id, [])


async def count_signals(incident_id: str) -> int:
    """Return the number of signals linked to an incident."""
    return len(_store.get(incident_id, []))


async def delete_signals(incident_id: str) -> bool:
    """Remove all signals for an incident (e.g. on data retention sweep)."""
    if incident_id in _store:
        del _store[incident_id]
        return True
    return False


def get_store_stats() -> dict:
    """Return storage stats for the /metrics endpoint."""
    total_signals = sum(len(v) for v in _store.values())
    return {
        "incidents_tracked": len(_store),
        "total_raw_signals":  total_signals,
    }