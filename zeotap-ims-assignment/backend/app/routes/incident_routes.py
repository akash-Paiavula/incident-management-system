from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.debounce_service import (
    get_all_incidents,
    get_incident_by_id,
    update_incident_status
)

router = APIRouter()


class StatusUpdateRequest(BaseModel):
    status: str


@router.get("/")
def get_incidents():
    return {
        "incidents": get_all_incidents()
    }


@router.get("/{incident_id}")
def get_incident(incident_id: str):
    incident = get_incident_by_id(incident_id)

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    return incident


@router.patch("/{incident_id}/status")
def update_status(incident_id: str, request: StatusUpdateRequest):
    incident, message = update_incident_status(incident_id, request.status)

    if not incident:
        raise HTTPException(status_code=400, detail=message)

    return {
        "message": message,
        "incident": incident
    }