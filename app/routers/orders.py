"""Órdenes de compra del usuario autenticado."""

from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.cache import PRODUCTS_CACHE_PREFIX, cache
from app.database import get_db
from app.deps import get_current_user
from app.models import Order, OrderItem, Product, User
from app.notifications import send_order_confirmation
from app.schemas.common import ErrorResponse
from app.schemas.order import OrderCreate, OrderRead

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post(
    "/",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una orden",
    description=(
        "Crea una orden para el usuario autenticado, **descuenta el stock** de "
        "cada producto e invalida la caché. El correo de confirmación se envía "
        "en segundo plano (no bloquea la respuesta)."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Stock insuficiente"},
        404: {"model": ErrorResponse, "description": "Algún producto no existe"},
    },
)
def create_order(
    payload: OrderCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Order:
    order = Order(user_id=current_user.id, status="pending", total=Decimal("0"))
    total = Decimal("0")

    try:
        for item in payload.items:
            # Leemos el producto para conocer nombre y precio ANTES del update;
            # el descuento real se hace con un UPDATE condicional atómico.
            product = db.get(Product, item.product_id)
            if not product or not product.is_active:
                raise HTTPException(
                    status_code=404,
                    detail=f"Producto {item.product_id} no encontrado",
                )

            # Decremento atómico: la condición stock >= quantity se evalúa en la
            # propia sentencia SQL, así dos órdenes concurrentes no venden de más.
            result = db.execute(
                update(Product)
                .where(
                    Product.id == item.product_id,
                    Product.is_active.is_(True),
                    Product.stock >= item.quantity,
                )
                .values(stock=Product.stock - item.quantity)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount == 0:
                # El producto existe y está activo, pero no había stock suficiente.
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock insuficiente para '{product.name}'",
                )

            # El UPDATE no sincronizó el objeto en sesión; refrescamos el stock.
            db.expire(product, ["stock"])
            total += product.price * item.quantity
            order.items.append(
                OrderItem(
                    product_id=product.id,
                    quantity=item.quantity,
                    unit_price=product.price,
                )
            )

        order.total = total
        db.add(order)
        db.commit()
        db.refresh(order)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="No se pudo crear la orden"
        ) from exc

    # El stock cambió: invalidamos la caché de productos para no servir
    # listados con stock obsoleto.
    cache.delete_prefix(PRODUCTS_CACHE_PREFIX)

    # El correo se envía DESPUÉS de responder al cliente (no bloquea la petición).
    background_tasks.add_task(
        send_order_confirmation, current_user.email, order.id, str(order.total)
    )
    return order


@router.get(
    "/",
    response_model=list[OrderRead],
    summary="Listar mis órdenes",
    description="Devuelve las órdenes del usuario autenticado, más recientes primero.",
)
def list_my_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.user_id == current_user.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt))


@router.get(
    "/{order_id}",
    response_model=OrderRead,
    summary="Obtener una orden propia",
    responses={404: {"model": ErrorResponse, "description": "Orden no encontrada"}},
)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Order:
    stmt = (
        select(Order)
        .where(Order.id == order_id, Order.user_id == current_user.id)
        .options(selectinload(Order.items))
    )
    order = db.scalar(stmt)
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return order
