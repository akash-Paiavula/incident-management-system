"""
Incident Schema
===============
Pydantic response schema for Incident API endpoints.
Separate from the internal Incident dataclass model —
this controls exactly what gets serialised in API responses.
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class IncidentResponse(BaseModel):
    incident_id: str
    component_id: str
    component_type: str
    severity: str
    status: str
    signal_count: int
    rca_submitted: bool
    mttr_seconds: Optional[int] = None
    start_time: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StatusUpdateRequest(BaseModel):
    status: str