"""
Mock Failure Simulation Script
================================
Simulates a realistic production incident scenario:
  1. RDBMS_PRIMARY_01 outage — 5 rapid signals (debounce → 1 Work Item)
  2. MCP_HOST_02 failure — 3 signals (new Work Item after debounce window expires)
  3. Full lifecycle: OPEN → INVESTIGATING → RESOLVED → (RCA submitted) → CLOSED
  4. Demonstrates rejection of CLOSED transition without RCA

Usage:
  python scripts/mock_failure.py

Prerequisites:
  pip install requests
  Backend must be running at http://localhost:8000
"""

import time
import requests

BASE_URL = "http://localhost:8000"


def post_signal(component_id, component_type, severity, message, metadata=None):
    payload = {
        "component_id": component_id,
        "component_type": component_type,
        "severity": severity,
        "message": message,
        "metadata": metadata or {}
    }
    r = requests.post(f"{BASE_URL}/signals/", json=payload)
    return r.json()


def transition(incident_id, new_status):
    r = requests.patch(
        f"{BASE_URL}/incidents/{incident_id}/status",
        json={"status": new_status}
    )
    return r.json()


def submit_rca(incident_id, start, end, category, fix, prevention):
    payload = {
        "incident_start": start,
        "incident_end": end,
        "root_cause_category": category,
        "fix_applied": fix,
        "prevention_steps": prevention
    }
    r = requests.post(f"{BASE_URL}/rca/{incident_id}", json=payload)
    return r.json()


def get_incidents():
    return requests.get(f"{BASE_URL}/incidents/").json()


def separator(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


if __name__ == "__main__":
    separator("PHASE 1: RDBMS Outage — 5 Rapid Signals")

    rdbms_incident_id = None
    for i in range(5):
        result = post_signal(
            component_id="RDBMS_PRIMARY_01",
            component_type="RDBMS",
            severity="P0",
            message="Database connection timeout — max connections exceeded",
            metadata={"host": "db-primary-01.prod", "error_code": "53300", "attempt": i + 1}
        )
        print(f"  Signal {i+1}: incident_created={result.get('result', {}).get('incident_created')} "
              f"| debounced={result.get('result', {}).get('debounced')}")
        if result.get("result", {}).get("incident_id"):
            rdbms_incident_id = result["result"]["incident_id"]
        time.sleep(0.5)

    print(f"\n  ✅ RDBMS Incident ID: {rdbms_incident_id}")
    print("  5 signals collapsed into 1 Work Item (debounce working)")

    separator("PHASE 2: Waiting 12s for debounce window to expire...")
    for i in range(12, 0, -1):
        print(f"  {i}s remaining...", end="\r")
        time.sleep(1)
    print("  Debounce window expired.               ")

    separator("PHASE 3: MCP Host Failure — 3 Signals")

    mcp_incident_id = None
    for i in range(3):
        result = post_signal(
            component_id="MCP_HOST_02",
            component_type="MCP_HOST",
            severity="P0",
            message="MCP host unresponsive — health check failed",
            metadata={"host": "mcp-02.prod", "last_heartbeat_ago_sec": 90 + i * 10}
        )
        print(f"  Signal {i+1}: incident_created={result.get('result', {}).get('incident_created')}")
        if result.get("result", {}).get("incident_id"):
            mcp_incident_id = result["result"]["incident_id"]
        time.sleep(0.3)

    print(f"\n  ✅ MCP Incident ID: {mcp_incident_id}")

    separator("PHASE 4: Lifecycle — RDBMS Incident")

    print("\n  Transitioning RDBMS: OPEN → INVESTIGATING")
    r = transition(rdbms_incident_id, "INVESTIGATING")
    print(f"  Result: {r.get('message')}")
    time.sleep(1)

    print("  Transitioning RDBMS: INVESTIGATING → RESOLVED")
    r = transition(rdbms_incident_id, "RESOLVED")
    print(f"  Result: {r.get('message')}")
    time.sleep(1)

    print("\n  Attempting RESOLVED → CLOSED without RCA (should be rejected)...")
    r = transition(rdbms_incident_id, "CLOSED")
    print(f"  Result: {r.get('detail', r.get('message', r))}")

    separator("PHASE 5: Submitting RCA for RDBMS Incident")

    rca_result = submit_rca(
        incident_id=rdbms_incident_id,
        start="2026-04-30T10:00:00",
        end="2026-04-30T11:30:00",
        category="Database",
        fix="Restarted PostgreSQL service. Increased max_connections from 100 to 500. Deployed PgBouncer as connection pooler.",
        prevention="Added CloudWatch alarm for connection saturation at 80%. Enabled automatic failover to read replica. Added connection pool monitoring dashboard."
    )
    print(f"  RCA submitted: {rca_result.get('message')}")
    if "rca" in rca_result:
        mttr_min = rca_result["rca"].get("mttr_seconds", 0) // 60
        print(f"  MTTR: {mttr_min} minutes")

    separator("PHASE 6: Closing RDBMS Incident (RCA now present)")

    r = transition(rdbms_incident_id, "CLOSED")
    print(f"  Result: {r.get('message')}")
    incident = requests.get(f"{BASE_URL}/incidents/{rdbms_incident_id}").json()
    print(f"  Final status: {incident.get('status')}")

    separator("PHASE 7: Attempt to close MCP incident without RCA")

    r = transition(mcp_incident_id, "INVESTIGATING")
    print(f"  MCP OPEN → INVESTIGATING: {r.get('message')}")
    r = transition(mcp_incident_id, "RESOLVED")
    print(f"  MCP INVESTIGATING → RESOLVED: {r.get('message')}")
    r = transition(mcp_incident_id, "CLOSED")
    print(f"  MCP RESOLVED → CLOSED (no RCA): {r.get('detail', '❌ Rejected as expected')}")

    separator("FINAL STATE")

    all_incidents = get_incidents()["incidents"]
    for inc in all_incidents:
        print(f"  [{inc['status']:15s}] {inc['component_id']:25s} | signals={inc['signal_count']} | RCA={inc['rca_submitted']}")

    print("\n✅ Mock failure simulation complete.\n")