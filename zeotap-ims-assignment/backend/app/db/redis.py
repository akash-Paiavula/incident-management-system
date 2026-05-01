"""
Redis Layer — Hot-Path Cache + Debounce Window
===============================================
Two responsibilities:
  1. Debounce window: TTL-keyed locks per component_id (prevents signal storms
     from creating duplicate incidents within the 10-second window)
  2. Dashboard cache: stores the real-time incident summary so the UI never
     hits PostgreSQL on every 5-second poll refresh

Current implementation: in-memory dict simulation with TTL tracking.
Production upgrade: replace with aioredis client — same async API, zero refactor.

Key patterns:
  debounce:{component_id}  →  incident_id (TTL = 10s)
  dashboard:state          →  serialised incident summary list
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Any

logger = logging.getLogger(__name__)

# ── In-memory store (simulates Redis key-value store with TTL) ────────────────
_store:      dict[str, Any]      = {}
_expiry_map: dict[str, datetime] = {}

_lock = asyncio.Lock()  # protects concurrent debounce window writes


def _is_expired(key: str) -> bool:
    expiry = _expiry_map.get(key)
    if expiry is None:
        return False
    return datetime.utcnow() > expiry


async def set(key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
    """
    SET key value [EX ttl_seconds]
    Thread-safe via asyncio.Lock for debounce window keys.
    """
    async with _lock:
        _store[key] = value
        if ttl_seconds:
            _expiry_map[key] = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        elif key in _expiry_map:
            del _expiry_map[key]
    return True


async def get(key: str) -> Optional[Any]:
    """GET key — returns None if key missing or expired (simulates Redis TTL)."""
    if key not in _store:
        return None
    if _is_expired(key):
        await delete(key)
        return None
    return _store[key]


async def delete(key: str) -> bool:
    """DEL key"""
    async with _lock:
        _store.pop(key, None)
        _expiry_map.pop(key, None)
    return True


async def exists(key: str) -> bool:
    """EXISTS key"""
    if key not in _store:
        return False
    if _is_expired(key):
        await delete(key)
        return False
    return True


async def ttl(key: str) -> Optional[int]:
    """TTL key — returns remaining seconds, or None if no expiry / missing."""
    if not await exists(key):
        return None
    expiry = _expiry_map.get(key)
    if not expiry:
        return None
    remaining = (expiry - datetime.utcnow()).total_seconds()
    return max(0, int(remaining))


# ── Debounce helpers ──────────────────────────────────────────────────────────

DEBOUNCE_PREFIX = "debounce:"
DEBOUNCE_TTL    = 10  # seconds


async def set_debounce(component_id: str, incident_id: str) -> bool:
    """Lock a component_id to an incident for the debounce window."""
    return await set(f"{DEBOUNCE_PREFIX}{component_id}", incident_id, ttl_seconds=DEBOUNCE_TTL)


async def get_debounce(component_id: str) -> Optional[str]:
    """Return the active incident_id for a component, or None if window expired."""
    return await get(f"{DEBOUNCE_PREFIX}{component_id}")


async def clear_debounce(component_id: str) -> bool:
    return await delete(f"{DEBOUNCE_PREFIX}{component_id}")


# ── Dashboard cache helpers ───────────────────────────────────────────────────

DASHBOARD_KEY     = "dashboard:state"
DASHBOARD_TTL     = 4  # seconds — slightly under the 5s UI poll interval


async def set_dashboard_cache(incident_list: list) -> bool:
    """Cache the full serialised incident list for fast UI reads."""
    return await set(DASHBOARD_KEY, incident_list, ttl_seconds=DASHBOARD_TTL)


async def get_dashboard_cache() -> Optional[list]:
    """Return cached incident list, or None if stale (triggers DB read)."""
    return await get(DASHBOARD_KEY)


async def invalidate_dashboard_cache() -> bool:
    """Call after any status transition or RCA submission."""
    return await delete(DASHBOARD_KEY)


def get_store_stats() -> dict:
    active_keys = [k for k in _store if not _is_expired(k)]
    debounce_keys = [k for k in active_keys if k.startswith(DEBOUNCE_PREFIX)]
    return {
        "active_keys":       len(active_keys),
        "active_debounces":  len(debounce_keys),
        "dashboard_cached":  DASHBOARD_KEY in _store and not _is_expired(DASHBOARD_KEY),
    }