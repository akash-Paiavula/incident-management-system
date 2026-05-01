from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.routes import signal_routes, incident_routes, rca_routes
from app.services.metrics_service import get_total_signals, start_metrics_logger
from app.services.debounce_service import get_all_incidents
from app.services.worker import start_worker, stop_worker, queue_size
from app.services.debounce_service import process_signal
from app.db.redis import get_store_stats as redis_stats
from app.db.mongo import get_store_stats as mongo_stats
from app.db.postgres import get_store_stats as pg_stats

# ── Rate limiter (token bucket: 500 requests/min per IP on ingestion) ─────────
limiter = Limiter(key_func=get_remote_address, default_limits=["500/minute"])

app = FastAPI(
    title="Mission-Critical Incident Management System",
    version="1.0.0",
    description="High-throughput Incident Management System for SRE workflows"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signal_routes.router,   prefix="/signals",   tags=["Signals"])
app.include_router(incident_routes.router, prefix="/incidents", tags=["Incidents"])
app.include_router(rca_routes.router,      prefix="/rca",       tags=["RCA"])


@app.get("/")
def root():
    return {"message": "IMS Backend is running"}


@app.get("/health")
def health_check():
    return {
        "status":  "healthy",
        "service": "ims-backend"
    }


@app.get("/metrics")
def metrics():
    incidents = get_all_incidents()
    return {
        "total_signals_processed": get_total_signals(),
        "signal_queue_depth":      queue_size(),
        "total_incidents":         len(incidents),
        "active_incidents":        len([i for i in incidents if i["status"] != "CLOSED"]),
        "closed_incidents":        len([i for i in incidents if i["status"] == "CLOSED"]),
        "stores": {
            "redis":    redis_stats(),
            "mongo":    mongo_stats(),
            "postgres": pg_stats(),
        }
    }


@app.on_event("startup")
async def startup():
    start_metrics_logger()
    start_worker(process_signal)


@app.on_event("shutdown")
async def shutdown():
    await stop_worker()