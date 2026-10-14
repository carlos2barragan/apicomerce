"""Métricas de Prometheus.

Expuestas en /metrics, en formato que Prometheus puede leer.
Los 3 tipos que usarás el 99% del tiempo:
- Counter:   solo sube (peticiones totales, errores).
- Histogram: distribuciones (latencia, tamaño).
- Gauge:     sube y baja (conexiones activas, en cola).
"""

from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total de peticiones HTTP",
    ["method", "path", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Duración de las peticiones HTTP en segundos",
    ["method", "path"],
)


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
