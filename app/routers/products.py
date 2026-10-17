"""CRUD de productos. Escritura restringida a administradores.

Incluye caché de lecturas: la primera petición calcula y guarda en caché;
las siguientes (dentro del TTL) responden desde ahí. Las escrituras
invalidan la caché para no servir datos obsoletos.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache import PRODUCTS_CACHE_PREFIX, cache
from app.config import settings
from app.database import get_db
from app.deps import get_current_admin
from app.models import Product, User
from app.schemas.common import ErrorResponse
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])

_CACHE_PREFIX = PRODUCTS_CACHE_PREFIX


@router.get(
    "/",
    response_model=list[ProductRead],
    summary="Listar productos",
    description=(
        "Devuelve productos activos, paginados y con búsqueda opcional por "
        "nombre. Las lecturas se **cachean** (Redis o memoria) durante "
        "`CACHE_TTL_SECONDS`. Las escrituras invalidan la caché."
    ),
)
def list_products(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    q: str | None = Query(None, description="Buscar por nombre"),
):
    cache_key = f"{_CACHE_PREFIX}list:{skip}:{limit}:{q or ''}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    stmt = select(Product).where(Product.is_active.is_(True))
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    stmt = stmt.offset(skip).limit(limit)
    products = list(db.scalars(stmt))

    result = [
        ProductRead.model_validate(p).model_dump(mode="json") for p in products
    ]
    cache.set(cache_key, result, ttl=settings.CACHE_TTL_SECONDS)
    return result


@router.get(
    "/{product_id}",
    response_model=ProductRead,
    summary="Obtener un producto",
    responses={404: {"model": ErrorResponse, "description": "Producto no encontrado"}},
)
def get_product(product_id: int, db: Session = Depends(get_db)) -> Product:
    product = db.get(Product, product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product


@router.post(
    "/",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un producto (solo admin)",
    description="Requiere rol de administrador. Al crear, invalida la caché de listados.",
    responses={403: {"model": ErrorResponse, "description": "Se requiere rol de administrador"}},
)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> Product:
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    cache.delete_prefix(_CACHE_PREFIX)  # invalida listados cacheados
    return product


@router.patch(
    "/{product_id}",
    response_model=ProductRead,
    summary="Actualizar un producto (solo admin)",
    description="Actualización parcial: solo los campos enviados se modifican.",
    responses={
        403: {"model": ErrorResponse, "description": "Se requiere rol de administrador"},
        404: {"model": ErrorResponse, "description": "Producto no encontrado"},
    },
)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> Product:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    cache.delete_prefix(_CACHE_PREFIX)
    return product


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un producto (solo admin)",
    description=(
        "**Borrado lógico**: en vez de borrar la fila, marca `is_active=False`, "
        "para no romper el histórico de órdenes."
    ),
    responses={
        403: {"model": ErrorResponse, "description": "Se requiere rol de administrador"},
        404: {"model": ErrorResponse, "description": "Producto no encontrado"},
    },
)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> None:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    product.is_active = False  # soft delete: no borramos el histórico
    db.commit()
    cache.delete_prefix(_CACHE_PREFIX)
