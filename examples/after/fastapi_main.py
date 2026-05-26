"""
NX Computing Platform — FastAPI application factory.

Registers middleware, routes, exception handlers, WebSocket endpoints,
and the background task scheduler. Wrapped by Socket.IO at the bottom —
the actual ASGI entrypoint is `socket_app`, not `app` directly.

Startup and shutdown are managed via the `lifespan` context manager,
which is the FastAPI-recommended alternative to deprecated on_event hooks.
"""

import logging
from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

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
    """Manage startup and graceful shutdown of background services.

    Startup: initialize the APScheduler job queue before accepting requests.
    Shutdown: stop the scheduler without waiting for running jobs to finish
    (wait=False avoids blocking the process during rolling deploys), then
    close Redis and database connections in dependency order.
    """
    logger.info("Starting NX Computing Platform API (env=%s)", settings.app_env)

    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("APScheduler started (%d jobs)", len(scheduler.get_jobs()))

    yield

    # wait=False — don't block shutdown waiting for in-flight scheduled jobs.
    # Jobs are idempotent and will re-run on the next cycle after restart.
    scheduler.shutdown(wait=False)
    logger.info("APScheduler stopped")

    # Deferred imports — these modules initialize connection pools on import.
    # Importing them here (post-yield) ensures pools are only closed after the
    # app has fully started, avoiding teardown-before-startup race conditions.
    from app.services.cache import close_redis
    from app.database import engine

    await close_redis()
    await engine.dispose()
    logger.info("Redis and database connections closed")


app = FastAPI(
    title="NX Computing Platform API",
    description="Vision AI analytics and security platform — backend API",
    version="2.0.0",
    lifespan=lifespan,
    # Docs are disabled in production to avoid exposing the API schema publicly.
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)


# ── Middleware ────────────────────────────────────────────────────────────────
# FastAPI applies middleware in reverse registration order — the last one added
# runs first on incoming requests. Current execution order on a request:
#   CORS → AuditMiddleware → SlowAPI (rate limiting) → route handler
#
# CORS must run first so preflight OPTIONS requests are answered before any
# authentication or rate limiting logic touches them.

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


# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Logs the full traceback for internal visibility while returning a safe
    # generic message to the client — avoids leaking implementation details.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Routes ────────────────────────────────────────────────────────────────────
# All routers declare their own /api/... prefix internally — do NOT add
# prefix="/api" here or routes will double-prefix to /api/api/...

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
    """Liveness probe — used by the load balancer to verify the process is up."""
    return {"status": "ok"}


# ── WebSocket ─────────────────────────────────────────────────────────────────

register_positions_ws(app)


# ── Observability ─────────────────────────────────────────────────────────────
# Instruments all routes automatically with OpenTelemetry spans.
# Must be called after all routes are registered to capture them all.

FastAPIInstrumentor.instrument_app(app)


# ── ASGI entrypoint ───────────────────────────────────────────────────────────
# Socket.IO wraps the FastAPI app so it can intercept /socket.io/* traffic.
# Everything else (REST routes, /ws/positions, /health) is forwarded to `app`.
# Deploy this module's `socket_app`, not `app`, as the ASGI entrypoint.

socket_app = socketio.ASGIApp(
    sio,
    other_asgi_app=app,
    static_files={},
)
