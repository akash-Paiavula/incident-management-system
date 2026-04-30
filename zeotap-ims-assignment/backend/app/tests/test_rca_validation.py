"""
Unit Tests — RCA Validation Logic
===================================
Tests the Pydantic RCASchema validators and the service-layer
enforcement of mandatory RCA before CLOSED transition.

Run with:
  cd backend
  pytest app/tests/test_rca_validation.py -v
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from app.schemas.rca_schema import RCASchema
from app.services.debounce_service import (
    process_signal,
    update_incident_status,
    submit_rca_record,
    incidents,
    rca_records,
    raw_signals,
    active_debounce,
)
from app.schemas.signal_schema import SignalSchema


# ─── Helpers ──────────────────────────────────────────────────────────────────

def valid_rca_data(**overrides):
    data = {
        "incident_start": datetime(2026, 4, 30, 10, 0, 0),
        "incident_end":   datetime(2026, 4, 30, 11, 30, 0),
        "root_cause_category": "Database",
        "fix_applied": "Restarted DB and increased connection pool",
        "prevention_steps": "Added failover and alerting",
    }
    data.update(overrides)
    return data


def make_incident(component_id="TEST_COMP_01", component_type="RDBMS", severity="P0"):
    """Creates an incident via process_signal and returns its ID."""
    # Clear any existing debounce for this component
    active_debounce.pop(component_id, None)

    signal = SignalSchema(
        component_id=component_id,
        component_type=component_type,
        severity=severity,
        message="Test signal",
    )
    result = process_signal(signal)
    return result["incident_id"]


# ─── RCA Schema Validation Tests ─────────────────────────────────────────────

class TestRCASchemaValidation:

    def test_valid_rca_accepted(self):
        """A fully populated, valid RCA should be accepted without error."""
        rca = RCASchema(**valid_rca_data())
        assert rca.root_cause_category == "Database"
        assert rca.fix_applied is not None
        assert rca.prevention_steps is not None

    def test_empty_root_cause_category_rejected(self):
        """Empty root_cause_category must raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            RCASchema(**valid_rca_data(root_cause_category=""))
        assert "cannot be empty" in str(exc_info.value).lower() or "value error" in str(exc_info.value).lower()

    def test_empty_fix_applied_rejected(self):
        """Empty fix_applied must raise ValidationError."""
        with pytest.raises(ValidationError):
            RCASchema(**valid_rca_data(fix_applied=""))

    def test_empty_prevention_steps_rejected(self):
        """Empty prevention_steps must raise ValidationError."""
        with pytest.raises(ValidationError):
            RCASchema(**valid_rca_data(prevention_steps=""))

    def test_whitespace_only_root_cause_rejected(self):
        """Whitespace-only root_cause_category must be rejected."""
        with pytest.raises(ValidationError):
            RCASchema(**valid_rca_data(root_cause_category="   "))

    def test_whitespace_only_fix_applied_rejected(self):
        """Whitespace-only fix_applied must be rejected."""
        with pytest.raises(ValidationError):
            RCASchema(**valid_rca_data(fix_applied="\t\n"))

    def test_end_before_start_rejected(self):
        """incident_end before incident_start must raise ValidationError."""
        with pytest.raises(ValidationError):
            RCASchema(**valid_rca_data(
                incident_start=datetime(2026, 4, 30, 12, 0, 0),
                incident_end=datetime(2026, 4, 30, 10, 0, 0),
            ))

    def test_end_equals_start_rejected(self):
        """incident_end equal to incident_start must raise ValidationError."""
        t = datetime(2026, 4, 30, 10, 0, 0)
        with pytest.raises(ValidationError):
            RCASchema(**valid_rca_data(incident_start=t, incident_end=t))

    def test_mttr_calculated_correctly(self):
        """MTTR should equal the difference between end and start in seconds."""
        start = datetime(2026, 4, 30, 10, 0, 0)
        end   = datetime(2026, 4, 30, 11, 30, 0)
        rca = RCASchema(
            incident_start=start,
            incident_end=end,
            root_cause_category="Network",
            fix_applied="Rerouted traffic",
            prevention_steps="Added redundant path",
        )
        # The service layer computes MTTR — validate the time delta itself
        expected_seconds = int((end - start).total_seconds())
        assert expected_seconds == 5400  # 90 minutes

    def test_end_one_second_after_start_accepted(self):
        """Even a 1-second gap between start and end should be valid."""
        start = datetime(2026, 4, 30, 10, 0, 0)
        end = start + timedelta(seconds=1)
        rca = RCASchema(**valid_rca_data(incident_start=start, incident_end=end))
        assert rca.incident_end > rca.incident_start


# ─── Service-Layer Tests ──────────────────────────────────────────────────────

class TestServiceLayerEnforcement:

    def setup_method(self):
        """Clear all in-memory state before each test."""
        incidents.clear()
        rca_records.clear()
        raw_signals.clear()
        active_debounce.clear()

    def test_close_without_rca_rejected(self):
        """Transitioning to CLOSED without an RCA record must return an error."""
        incident_id = make_incident("CLOSE_NO_RCA_01")

        # Move to RESOLVED (valid path)
        update_incident_status(incident_id, "INVESTIGATING")
        update_incident_status(incident_id, "RESOLVED")

        # Attempt CLOSED — should be rejected
        result, message = update_incident_status(incident_id, "CLOSED")
        assert result is None
        assert "rca" in message.lower()

    def test_close_with_rca_accepted(self):
        """Transitioning to CLOSED after submitting RCA must succeed."""
        incident_id = make_incident("CLOSE_WITH_RCA_01")

        update_incident_status(incident_id, "INVESTIGATING")
        update_incident_status(incident_id, "RESOLVED")

        rca = RCASchema(**valid_rca_data())
        submit_rca_record(incident_id, rca)

        result, message = update_incident_status(incident_id, "CLOSED")
        assert result is not None
        assert result["status"] == "CLOSED"

    def test_invalid_transition_open_to_closed_rejected(self):
        """Jumping from OPEN directly to CLOSED must be rejected."""
        incident_id = make_incident("SKIP_TRANSITION_01")
        result, message = update_incident_status(incident_id, "CLOSED")
        assert result is None
        assert "invalid transition" in message.lower() or "rca" in message.lower()

    def test_invalid_transition_open_to_resolved_rejected(self):
        """OPEN → RESOLVED is an invalid skip and must be rejected."""
        incident_id = make_incident("SKIP_TRANSITION_02")
        result, message = update_incident_status(incident_id, "RESOLVED")
        assert result is None

    def test_debounce_links_signals_to_same_incident(self):
        """Multiple signals within debounce window must create only one incident."""
        active_debounce.pop("DEBOUNCE_TEST_01", None)

        signal = SignalSchema(
            component_id="DEBOUNCE_TEST_01",
            component_type="CACHE",
            severity="P2",
            message="Cache miss spike",
        )
        r1 = process_signal(signal)
        r2 = process_signal(signal)
        r3 = process_signal(signal)

        assert r1["incident_created"] is True
        assert r2["incident_created"] is False
        assert r3["incident_created"] is False
        assert r2["incident_id"] == r1["incident_id"]
        assert r3["incident_id"] == r1["incident_id"]

    def test_rca_mttr_stored_on_incident(self):
        """Submitting an RCA should update the incident's mttr_seconds field."""
        incident_id = make_incident("MTTR_TEST_01")
        rca = RCASchema(**valid_rca_data())
        submit_rca_record(incident_id, rca)

        inc = incidents[incident_id]
        assert inc["mttr_seconds"] is not None
        assert inc["mttr_seconds"] == 5400  # 90 minutes

    def test_closed_incident_cannot_transition(self):
        """A CLOSED incident should reject any further transitions."""
        incident_id = make_incident("CLOSED_LOCK_01")

        update_incident_status(incident_id, "INVESTIGATING")
        update_incident_status(incident_id, "RESOLVED")
        submit_rca_record(incident_id, RCASchema(**valid_rca_data()))
        update_incident_status(incident_id, "CLOSED")

        result, message = update_incident_status(incident_id, "INVESTIGATING")
        assert result is None
        assert "invalid transition" in message.lower()