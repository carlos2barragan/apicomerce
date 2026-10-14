"""Conexión a base de datos y sesión de SQLAlchemy."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# Las nubes (Render, Railway, Heroku) entregan la URL como "postgresql://...".
# SQLAlchemy con psycopg v3 necesita el driver explícito: "postgresql+psycopg://".
database_url = settings.DATABASE_URL
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

# SQLite necesita este flag para usarse con FastAPI (múltiples hilos).
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}

engine = create_engine(database_url, connect_args=connect_args)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos."""


def get_db() -> Generator[Session, None, None]:
    """Dependencia que entrega una sesión de BD y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
