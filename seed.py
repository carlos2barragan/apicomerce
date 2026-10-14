"""Script para poblar la base de datos con datos de prueba.

Uso:
    python seed.py
"""

from decimal import Decimal

from sqlalchemy import select

from app import models  # noqa: F401
from app.database import Base, SessionLocal, engine
from app.models import Product, User
from app.security import hash_password


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.scalar(select(User).where(User.email == "admin@demo.com")):
            db.add(
                User(
                    email="admin@demo.com",
                    full_name="Administrador",
                    hashed_password=hash_password("admin1234"),
                    is_admin=True,
                )
            )
            print("Usuario admin creado: admin@demo.com / admin1234")

        if db.scalar(select(Product).limit(1)) is None:
            db.add_all(
                [
                    Product(
                        name="Laptop 14\"",
                        description="Laptop para desarrollo",
                        price=Decimal("2500.00"),
                        stock=10,
                    ),
                    Product(
                        name="Mouse inalámbrico",
                        description="Mouse ergonómico",
                        price=Decimal("80.00"),
                        stock=50,
                    ),
                    Product(
                        name="Teclado mecánico",
                        description="Teclado con switches azules",
                        price=Decimal("150.00"),
                        stock=30,
                    ),
                ]
            )
            print("Productos de ejemplo creados")

        db.commit()
        print("Seed completado correctamente.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
