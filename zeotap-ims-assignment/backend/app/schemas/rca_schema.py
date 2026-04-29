from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class RCASchema(BaseModel):
    incident_start: datetime = Field(..., example="2026-04-29T15:09:31")
    incident_end: datetime = Field(..., example="2026-04-29T15:30:31")
    root_cause_category: str = Field(..., example="Database")
    fix_applied: str = Field(..., example="Restarted DB and increased connection pool")
    prevention_steps: str = Field(..., example="Added failover and alerting")

    @field_validator("root_cause_category", "fix_applied", "prevention_steps")
    @classmethod
    def not_empty(cls, value):
        if not value or not value.strip():
            raise ValueError("Field cannot be empty")
        return value

    @field_validator("incident_end")
    @classmethod
    def end_after_start(cls, value, info):
        incident_start = info.data.get("incident_start")
        if incident_start and value <= incident_start:
            raise ValueError("incident_end must be after incident_start")
        return value