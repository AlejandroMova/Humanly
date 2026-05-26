# examples/before/fastapi_main.py
# Original — good structure, missing comments on non-obvious decisions.

import logging
from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.middleware.audit import AuditMiddleware
from app.middleware.rate_limit import limiter
from app.routes import (
    admin_crops, alerts, analytics, cameras, crops, dashboard, events,
    jetsons, reports, tenants,
)
from app.socket.events import sio
from app.socket.positions import register_positions_ws
from app.tasks.scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO if settings.app_env != "production" else logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting NX Computing Platform API (env=%s)", settings.app_env)
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("APScheduler started (%d jobs)", len(scheduler.get_jobs()))

    yield

    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")
    from app.services.cache import close_redis
    await close_redis()
    from app.database import engine
    await engine.dispose()
    logger.info("Database connections closed")


app = FastAPI(
    title="NX Computing Platform API",
    description="Vision AI analytics and security platform — backend API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)

# ── Middleware ──────────────────────────────────────────────────────────────

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception handlers ──────────────────────────────────────────────────────

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Routes ──────────────────────────────────────────────────────────────────
# All routers declare their own /api/... prefix internally — do NOT pass
# `prefix="/api"` here or you'll get /api/api/... double-prefixing.

app.include_router(admin_crops.router)
app.include_router(events.router)
app.include_router(analytics.router)
app.include_router(crops.router)
app.include_router(cameras.router)
app.include_router(dashboard.router)
app.include_router(alerts.router)
app.include_router(jetsons.router)
app.include_router(reports.router)
app.include_router(tenants.router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}


# ── WebSocket ────────────────────────────────────────────────────────────────

register_positions_ws(app)

# ── OpenTelemetry ────────────────────────────────────────────────────────────

FastAPIInstrumentor.instrument_app(app)

# ── Socket.IO ASGI wrapper ──────────────────────────────────────────────────
# Socket.IO intercepts /socket.io/* and forwards everything else to FastAPI
# (including /ws/positions, registered above).

socket_app = socketio.ASGIApp(
    sio,
    other_asgi_app=app,
    static_files={},
)
