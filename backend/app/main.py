import json
import logging
import secrets
import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.api.v1.auth_routes import router as auth_router
from app.api.v1.routes import router as router_v1
from app.api.v1.workspace_routes import router as workspace_router
from app.core.config import settings
from app.core.database import check_database

REQUESTS = Counter(
    "causora_http_requests_total",
    "HTTP requests handled by Causora",
    ("method", "route", "status"),
)
LATENCY = Histogram(
    "causora_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ("method", "route"),
)
logger = logging.getLogger("causora.http")
logging.basicConfig(level=settings.log_level.upper())


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = secrets.token_hex(12)
        request.state.request_id = request_id
        started = time.perf_counter()
        route_name = "unmatched"
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            route = request.scope.get("route")
            route_name = getattr(route, "path", "unmatched")
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            elapsed = time.perf_counter() - started
            if request.url.path != "/metrics":
                REQUESTS.labels(request.method, route_name, str(status_code)).inc()
                LATENCY.labels(request.method, route_name).observe(elapsed)
            logger.info(
                json.dumps(
                    {
                        "event": "http.request",
                        "request_id": request_id,
                        "method": request.method,
                        "route": route_name,
                        "status": status_code,
                        "duration_ms": round(elapsed * 1000, 2),
                    },
                    separators=(",", ":"),
                )
            )


app = FastAPI(
    title=settings.service_name,
    version="0.2.0",
    description="Explainable configuration change impact analysis",
)
app.add_middleware(RequestObservabilityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router_v1, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(workspace_router, prefix=settings.api_prefix)


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready() -> dict[str, str]:
    try:
        check_database()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Storage is not ready.") from exc
    return {"status": "ready", "storage": "connected"}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Request metadata is logged without query strings, bodies, credentials, or config values.
