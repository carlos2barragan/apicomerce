"""Middlewares: contexto de petición (logs + métricas) y rate limiting."""

import logging
import time
import uuid

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.cache import cache
from app.config import settings
from app.metrics import REQUEST_COUNT, REQUEST_LATENCY

logger = logging.getLogger("app.request")

# Rutas que no deben contar para el rate limit (health checks, métricas).
_EXEMPT_PREFIXES = ("/health", "/metrics")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Asigna un id único a cada petición, mide su duración y la registra."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            REQUEST_COUNT.labels(request.method, request.url.path, "500").inc()
            logger.exception(
                "%s %s -> 500 (%.1f ms)",
                request.method,
                request.url.path,
                duration_ms,
                extra={"request_id": request_id},
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        REQUEST_COUNT.labels(
            request.method, request.url.path, str(response.status_code)
        ).inc()
        REQUEST_LATENCY.labels(request.method, request.url.path).observe(
            duration_ms / 1000
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-ms"] = f"{duration_ms:.1f}"
        logger.info(
            "%s %s -> %s (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={"request_id": request_id},
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Límite de peticiones por IP usando una ventana fija de 1 minuto.

    Patrón de 'fixed window': cuenta peticiones por minuto en la caché.
    En producción se suele usar un algoritmo de 'sliding window' o token bucket.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(_EXEMPT_PREFIXES):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{client_ip}"
        count = cache.incr(key, ttl=60)

        if count > settings.RATE_LIMIT_PER_MINUTE:
            return JSONResponse(
                status_code=429,
                content={"detail": "Demasiadas peticiones. Intenta en un minuto."},
                headers={"Retry-After": "60"},
            )

        return await call_next(request)
