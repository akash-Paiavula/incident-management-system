from fastapi import APIRouter, HTTPException
from app.schemas.rca_schema import RCASchema
from app.services.debounce_service import submit_rca_record, get_rca_by_incident_id

router = APIRouter()


@router.post("/{incident_id}")
def submit_rca(incident_id: str, rca: RCASchema):
    rca_data, message = submit_rca_record(incident_id, rca)

    if not rca_data:
        raise HTTPException(status_code=404, detail=message)

    return {
        "message": message,
        "rca": rca_data
    }


@router.get("/{incident_id}")
def get_rca(incident_id: str):
    rca = get_rca_by_incident_id(incident_id)

    if not rca:
        raise HTTPException(status_code=404, detail="RCA not found")

    return rca