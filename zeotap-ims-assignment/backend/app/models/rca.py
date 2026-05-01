"""
RCA Model
=========
Defines the structured schema for a Root Cause Analysis record.
Linked 1-to-1 with an Incident. Required before CLOSED transition.

In production this would map to a PostgreSQL table via SQLAlchemy ORM.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RCA:
    incident_id: str
    incident_start: datetime
    incident_end: datetime
    root_cause_category: str
    fix_applied: str
    prevention_steps: str
    mttr_seconds: int
    submitted_at: datetime = None

    def __post_init__(self):
        if self.submitted_at is None:
            self.submitted_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "incident_id":          self.incident_id,
            "incident_start":       self.incident_start.isoformat(),
            "incident_end":         self.incident_end.isoformat(),
            "root_cause_category":  self.root_cause_category,
            "fix_applied":          self.fix_applied,
            "prevention_steps":     self.prevention_steps,
            "mttr_seconds":         self.mttr_seconds,
            "submitted_at":         self.submitted_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RCA":
        return cls(
            incident_id=data["incident_id"],
            incident_start=datetime.fromisoformat(data["incident_start"]),
            incident_end=datetime.fromisoformat(data["incident_end"]),
            root_cause_category=data["root_cause_category"],
            fix_applied=data["fix_applied"],
            prevention_steps=data["prevention_steps"],
            mttr_seconds=data["mttr_seconds"],
            submitted_at=datetime.fromisoformat(data["submitted_at"]) if data.get("submitted_at") else None,
        )

    @property
    def mttr_minutes(self) -> int:
        return self.mttr_seconds // 60