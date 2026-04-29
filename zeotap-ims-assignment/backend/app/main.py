from fastapi import FastAPI

from app.routes import signal_routes, incident_routes, rca_routes
from app.services.metrics_service import get_total_signals
from app.services.debounce_service import get_all_incidents
from app.services.metrics_service import start_metrics_logger

app = FastAPI(
    title="Mission-Critical Incident Management System",
    version="1.0.0",
    description="High-throughput Incident Management System for SRE workflows"
)

app.include_router(signal_routes.router, prefix="/signals", tags=["Signals"])
app.include_router(incident_routes.router, prefix="/incidents", tags=["Incidents"])
app.include_router(rca_routes.router, prefix="/rca", tags=["RCA"])


@app.get("/")
def root():
    return {"message": "IMS Backend is running"}


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "ims-backend"
    }


@app.get("/metrics")
def metrics():
    incidents = get_all_incidents()

    return {
        "total_signals_processed": get_total_signals(),
        "total_incidents": len(incidents),
        "active_incidents": len([
            incident for incident in incidents
            if incident["status"] != "CLOSED"
        ]),
        "closed_incidents": len([
            incident for incident in incidents
            if incident["status"] == "CLOSED"
        ])
    }

@app.on_event("startup")
def start_background_metrics():
    start_metrics_logger()