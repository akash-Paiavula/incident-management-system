from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict


class SignalSchema(BaseModel):
    component_id: str = Field(..., example="RDBMS_PRIMARY_01")
    component_type: str = Field(..., example="RDBMS")
    severity: str = Field(..., example="P0")
    message: str = Field(..., example="Database connection timeout")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict] = Field(default={})