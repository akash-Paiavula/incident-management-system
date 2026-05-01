"""
Incident Model
==============
Defines the structured schema for a Work Item (Incident).
Acts as the Source of Truth record for the incident lifecycle.

In production this would map to a PostgreSQL table via SQLAlchemy ORM.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4


@dataclass
class Incident:
    component_id: str
    component_type: str
    severity: str

    incident_id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "OPEN"
    signal_count: int = 1
    rca_submitted: bool = False
    mttr_seconds: Optional[int] = None
    start_time: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "incident_id":    self.incident_id,
            "component_id":   self.component_id,
            "component_type": self.component_type,
            "severity":       self.severity,
            "status":         self.status,
            "signal_count":   self.signal_count,
            "rca_submitted":  self.rca_submitted,
            "mttr_seconds":   self.mttr_seconds,
            "start_time":     self.start_time.isoformat(),
            "created_at":     self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Incident":
        return cls(
            incident_id=data["incident_id"],
            component_id=data["component_id"],
            component_type=data["component_type"],
            severity=data["severity"],
            status=data.get("status", "OPEN"),
            signal_count=data.get("signal_count", 1),
            rca_submitted=data.get("rca_submitted", False),
            mttr_seconds=data.get("mttr_seconds"),
            start_time=datetime.fromisoformat(data["start_time"]) if isinstance(data.get("start_time"), str) else data.get("start_time", datetime.utcnow()),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.utcnow()),
        )