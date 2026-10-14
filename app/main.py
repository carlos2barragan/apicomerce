"""Punto de entrada de la aplicación FastAPI."""

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (registra los modelos en Base)
from app.config import settings
from app.database import Base, engine, get_db
from app.logging_config import setup_logging
from app.metrics import metrics_response
from app.middleware import RateLimitMiddleware, RequestContextMiddleware
from app.routers import analytics, auth, orders, products

setup_logging(settings.LOG_LEVEL)

# Crea las tablas si no existen (en producción se usan migraciones/Alembic).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="API de ecommerce para practicar backend profesional.",
)

# El orden importa: el último middleware añadido es el más externo.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(analytics.router)


@app.get("/", tags=["health"])
def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/health/live", tags=["health"])
def liveness() -> dict:
    """¿El proceso está vivo? (Kubernetes: livenessProbe)."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"])
def readiness(db: Session = Depends(get_db)) -> dict:
    """¿Puede atender tráfico? Verifica la conexión a la base de datos."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="base de datos no disponible") from exc
    return {"status": "ready"}


@app.get("/metrics", tags=["health"])
def metrics():
    """Métricas en formato Prometheus."""
    return metrics_response()
