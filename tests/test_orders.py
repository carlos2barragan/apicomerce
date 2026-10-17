"""Tests de órdenes: descuento de stock, errores y aislamiento entre usuarios."""

from decimal import Decimal

from app.models import User
from app.security import hash_password
from tests.conftest import TestingSessionLocal


def _admin_headers(client) -> dict:
    """Crea un admin y devuelve sus headers de autorización."""
    db = TestingSessionLocal()
    try:
        db.add(
            User(
                email="admin@orders.test",
                hashed_password=hash_password("admin1234"),
                is_admin=True,
            )
        )
        db.commit()
    finally:
        db.close()
    r = client.post(
        "/auth/login",
        data={"username": "admin@orders.test", "password": "admin1234"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _register_and_login(client, email: str) -> dict:
    client.post("/auth/register", json={"email": email, "password": "secret123"})
    r = client.post(
        "/auth/login", data={"username": email, "password": "secret123"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_product(client, admin_headers: dict, **overrides) -> int:
    payload = {"name": "Producto", "price": "10.00", "stock": 5}
    payload.update(overrides)
    r = client.post("/products/", json=payload, headers=admin_headers)
    assert r.status_code == 201
    return r.json()["id"]


def test_create_order_discounts_stock(client):
    admin = _admin_headers(client)
    product_id = _create_product(client, admin, stock=5)
    user = _register_and_login(client, "buyer@test.com")

    r = client.post(
        "/orders/",
        json={"items": [{"product_id": product_id, "quantity": 2}]},
        headers=user,
    )
    assert r.status_code == 201
    body = r.json()
    assert Decimal(body["total"]) == Decimal("20.00")
    assert body["items"][0]["quantity"] == 2

    product = client.get(f"/products/{product_id}").json()
    assert product["stock"] == 3


def test_create_order_insufficient_stock(client):
    admin = _admin_headers(client)
    product_id = _create_product(client, admin, stock=1)
    user = _register_and_login(client, "buyer@test.com")

    r = client.post(
        "/orders/",
        json={"items": [{"product_id": product_id, "quantity": 5}]},
        headers=user,
    )
    assert r.status_code == 400

    # El stock no debe haberse tocado.
    assert client.get(f"/products/{product_id}").json()["stock"] == 1


def test_create_order_unknown_product(client):
    user = _register_and_login(client, "buyer@test.com")
    r = client.post(
        "/orders/",
        json={"items": [{"product_id": 9999, "quantity": 1}]},
        headers=user,
    )
    assert r.status_code == 404


def test_create_order_inactive_product(client):
    admin = _admin_headers(client)
    product_id = _create_product(client, admin, stock=5)
    assert client.delete(f"/products/{product_id}", headers=admin).status_code == 204
    user = _register_and_login(client, "buyer@test.com")

    r = client.post(
        "/orders/",
        json={"items": [{"product_id": product_id, "quantity": 1}]},
        headers=user,
    )
    assert r.status_code == 404


def test_create_order_rejects_duplicate_products(client):
    admin = _admin_headers(client)
    product_id = _create_product(client, admin, stock=5)
    user = _register_and_login(client, "buyer@test.com")

    r = client.post(
        "/orders/",
        json={
            "items": [
                {"product_id": product_id, "quantity": 1},
                {"product_id": product_id, "quantity": 1},
            ]
        },
        headers=user,
    )
    assert r.status_code == 422


def test_create_order_invalidates_products_cache(client):
    admin = _admin_headers(client)
    product_id = _create_product(client, admin, stock=5)
    client.get("/products/")  # prime the cache
    user = _register_and_login(client, "buyer@test.com")

    client.post(
        "/orders/",
        json={"items": [{"product_id": product_id, "quantity": 1}]},
        headers=user,
    )

    listing = client.get("/products/").json()
    assert listing[0]["stock"] == 4


def test_user_cannot_read_other_users_order(client):
    admin = _admin_headers(client)
    product_id = _create_product(client, admin, stock=5)
    owner = _register_and_login(client, "owner@test.com")
    other = _register_and_login(client, "other@test.com")

    order_id = client.post(
        "/orders/",
        json={"items": [{"product_id": product_id, "quantity": 1}]},
        headers=owner,
    ).json()["id"]

    assert client.get(f"/orders/{order_id}", headers=owner).status_code == 200
    assert client.get(f"/orders/{order_id}", headers=other).status_code == 404


def test_list_my_orders_pagination(client):
    admin = _admin_headers(client)
    product_id = _create_product(client, admin, stock=100)
    user = _register_and_login(client, "buyer@test.com")

    for _ in range(3):
        client.post(
            "/orders/",
            json={"items": [{"product_id": product_id, "quantity": 1}]},
            headers=user,
        )

    assert len(client.get("/orders/?limit=2", headers=user).json()) == 2
    assert len(client.get("/orders/?skip=2&limit=2", headers=user).json()) == 1
