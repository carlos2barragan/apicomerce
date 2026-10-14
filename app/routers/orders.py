"""Órdenes de compra del usuario autenticado."""

from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import get_current_user
from app.models import Order, OrderItem, Product, User
from app.notifications import send_order_confirmation
from app.schemas.order import OrderCreate, OrderRead

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Order:
    order = Order(user_id=current_user.id, status="pending", total=Decimal("0"))
    total = Decimal("0")

    for item in payload.items:
        product = db.get(Product, item.product_id)
        if not product or not product.is_active:
            raise HTTPException(
                status_code=404,
                detail=f"Producto {item.product_id} no encontrado",
            )
        if product.stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente para '{product.name}'",
            )

        product.stock -= item.quantity
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

    # El correo se envía DESPUÉS de responder al cliente (no bloquea la petición).
    background_tasks.add_task(
        send_order_confirmation, current_user.email, order.id, str(order.total)
    )
    return order


@router.get("/", response_model=list[OrderRead])
def list_my_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Order]:
    stmt = (
        select(Order)
        .where(Order.user_id == current_user.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    return list(db.scalars(stmt))


@router.get("/{order_id}", response_model=OrderRead)
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
