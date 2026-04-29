from datetime import datetime, timedelta
from uuid import uuid4

from app.services.state_machine import validate_status_transition
from app.services.metrics_service import increment_signal_count

DEBOUNCE_WINDOW_SECONDS = 10

active_debounce = {}
incidents = {}
raw_signals = {}
rca_records = {}


def process_signal(signal):
    increment_signal_count()

    component_id = signal.component_id
    now = datetime.utcnow()

    existing = active_debounce.get(component_id)

    if existing and now < existing["expires_at"]:
        incident_id = existing["incident_id"]

        raw_signals[incident_id].append(signal.model_dump())
        incidents[incident_id]["signal_count"] += 1

        return {
            "debounced": True,
            "incident_created": False,
            "incident_id": incident_id,
            "message": "Signal linked to existing incident"
        }

    incident_id = str(uuid4())

    incident = {
        "incident_id": incident_id,
        "component_id": signal.component_id,
        "component_type": signal.component_type,
        "severity": signal.severity,
        "status": "OPEN",
        "start_time": signal.timestamp,
        "created_at": now,
        "signal_count": 1,
        "rca_submitted": False,
        "mttr_seconds": None
    }

    incidents[incident_id] = incident
    raw_signals[incident_id] = [signal.model_dump()]

    active_debounce[component_id] = {
        "incident_id": incident_id,
        "expires_at": now + timedelta(seconds=DEBOUNCE_WINDOW_SECONDS)
    }

    return {
        "debounced": False,
        "incident_created": True,
        "incident_id": incident_id,
        "message": "New incident created"
    }


def get_all_incidents():
    return list(incidents.values())


def get_incident_by_id(incident_id: str):
    incident = incidents.get(incident_id)

    if not incident:
        return None

    return {
        **incident,
        "raw_signals": raw_signals.get(incident_id, []),
        "rca": rca_records.get(incident_id)
    }


def submit_rca_record(incident_id: str, rca):
    incident = incidents.get(incident_id)

    if not incident:
        return None, "Incident not found"

    mttr_seconds = int((rca.incident_end - rca.incident_start).total_seconds())

    rca_data = rca.model_dump()
    rca_data["incident_id"] = incident_id
    rca_data["mttr_seconds"] = mttr_seconds

    rca_records[incident_id] = rca_data

    incident["rca_submitted"] = True
    incident["mttr_seconds"] = mttr_seconds

    return rca_data, "RCA submitted successfully"


def has_complete_rca(incident_id: str):
    return incident_id in rca_records


def get_rca_by_incident_id(incident_id: str):
    return rca_records.get(incident_id)


def update_incident_status(incident_id: str, new_status: str):
    incident = incidents.get(incident_id)

    if not incident:
        return None, "Incident not found"

    new_status = new_status.upper()

    if new_status == "CLOSED" and not has_complete_rca(incident_id):
        return None, "Cannot close incident without complete RCA"

    is_valid, message = validate_status_transition(
        incident["status"],
        new_status
    )

    if not is_valid:
        return None, message

    incident["status"] = new_status

    return incident, "Incident status updated successfully"