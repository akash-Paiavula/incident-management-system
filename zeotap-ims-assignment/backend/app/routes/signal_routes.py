from fastapi import APIRouter
from app.schemas.signal_schema import SignalSchema
from app.services.debounce_service import process_signal

router = APIRouter()


@router.post("/")
async def ingest_signal(signal: SignalSchema):
    result = process_signal(signal)

    return {
        "message": "Signal processed successfully",
        "result": result
    }