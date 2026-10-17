"""Punto de entrada de la aplicación FastAPI."""

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (registra los modelos en Base)
from app.config import settings
from app.database import Base, engine, get_db
from app.logging_config import setup_logging
from app.metrics import metrics_response
from app.middleware import RateLimitMiddleware, RequestContextMiddleware
from app.routers import analytics, auth, orders, products
from app.schemas.common import ErrorResponse, HealthResponse

setup_logging(settings.LOG_LEVEL)

# Crea las tablas si no existen (en producción se usan migraciones/Alembic).
Base.metadata.create_all(bind=engine)

DESCRIPTION = """
API REST de **ecommerce** construida con FastAPI: autenticación JWT, CRUD de
productos, órdenes, caché, rate limiting, observabilidad y analítica.

### Autenticación
1. Crea una cuenta en `POST /auth/register` (o usa el admin de demo:
   `admin@demo.com` / `admin1234`).
2. Inicia sesión en `POST /auth/login` (form-urlencoded con `username` y
   `password`). Copia el `access_token`.
3. Pulsa **Authorize** arriba y pega el token (solo el valor, sin "Bearer") para
   probar las rutas protegidas.

### Panel web
La interfaz visual está en **[/ui](/ui)**.

### Producción
Health checks en `/health/live` y `/health/ready`; métricas Prometheus en
`/metrics`.
"""

tags_metadata = [
    {"name": "auth", "description": "Registro, login y usuario autenticado."},
    {"name": "products", "description": "CRUD de productos (escritura solo admin)."},
    {"name": "orders", "description": "Órdenes del usuario autenticado."},
    {"name": "analytics", "description": "Agregaciones de ventas (solo admin)."},
    {"name": "health", "description": "Salud del servicio y métricas."},
]

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=DESCRIPTION,
    openapi_tags=tags_metadata,
    contact={"name": "Portafolio backend", "url": "https://fastapi.tiangolo.com"},
    license_info={"name": "MIT"},
)

# El orden importa: el último middleware añadido es el más externo.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    # La auth es Bearer token (header), no cookies: no necesitamos credenciales.
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(analytics.router)

# Panel web (frontend estático) servido por la misma API en /ui.
# Basta con abrir http://127.0.0.1:8000/ui/ para ver los datos.
_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/ui", StaticFiles(directory=_frontend_dir, html=True), name="ui")


@app.get(
    "/",
    tags=["health"],
    response_model=HealthResponse,
    summary="Raíz / información de la app",
)
def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get(
    "/health/live",
    tags=["health"],
    response_model=HealthResponse,
    summary="Liveness probe",
    description="¿El proceso está vivo? (Kubernetes: livenessProbe).",
)
def liveness() -> dict:
    return {"status": "alive"}


@app.get(
    "/health/ready",
    tags=["health"],
    response_model=HealthResponse,
    summary="Readiness probe",
    description="¿Puede atender tráfico? Verifica la conexión a la base de datos.",
    responses={503: {"model": ErrorResponse, "description": "Base de datos no disponible"}},
)
def readiness(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="base de datos no disponible") from exc
    return {"status": "ready"}


@app.get(
    "/metrics",
    tags=["health"],
    summary="Métricas Prometheus",
    description="Contadores e histogramas de peticiones en formato Prometheus.",
    responses={200: {"content": {"text/plain": {}}}},
)
def metrics():
    return metrics_response()
