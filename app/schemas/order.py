from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=10_000)


class OrderCreate(BaseModel):
    items: list[OrderItemCreate] = Field(min_length=1, max_length=50)

    @field_validator("items")
    @classmethod
    def _reject_duplicate_products(
        cls, items: list[OrderItemCreate]
    ) -> list[OrderItemCreate]:
        """Un producto no puede repetirse: cada línea debe ser única."""
        product_ids = [item.product_id for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("No se permiten productos duplicados en la orden")
        return items

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"items": [{"product_id": 1, "quantity": 2}, {"product_id": 3, "quantity": 1}]}
        }
    )


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity: int
    unit_price: Decimal


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: str
    total: Decimal
    created_at: datetime
    items: list[OrderItemRead]
