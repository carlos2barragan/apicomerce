"""Analítica de ventas.

Este endpoint es la base perfecta para un agente: son exactamente las
"tools" que un LLM llamaría para responder preguntas de negocio como
"¿cuánto vendí este mes?" o "¿qué producto reabastecer?".
"""

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_admin
from app.models import Order, OrderItem, Product, User
from app.schemas.common import ErrorResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/summary",
    summary="Resumen de ventas (solo admin)",
    description=(
        "Agregaciones SQL: número de órdenes, ingresos totales y top 5 de "
        "productos más vendidos. Es la base ideal para exponer *tools* a un "
        "agente LLM."
    ),
    responses={403: {"model": ErrorResponse, "description": "Se requiere rol de administrador"}},
)
def sales_summary(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> dict:
    total_orders = db.scalar(select(func.count(Order.id))) or 0
    total_revenue = db.scalar(select(func.coalesce(func.sum(Order.total), 0))) or Decimal(
        "0"
    )

    top_rows = db.execute(
        select(Product.name, func.sum(OrderItem.quantity).label("units"))
        .join(OrderItem, OrderItem.product_id == Product.id)
        .group_by(Product.id, Product.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
    ).all()

    return {
        "total_orders": int(total_orders),
        # Se serializa como string para no perder precisión (float redondea dinero).
        "total_revenue": str(total_revenue),
        "top_products": [
            {"name": name, "units_sold": int(units)} for name, units in top_rows
        ],
    }
