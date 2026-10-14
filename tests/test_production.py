"""Tests de las capacidades de producción: health, métricas, caché y analítica."""

from app.models import User
from app.security import hash_password
from tests.conftest import TestingSessionLocal


def _create_admin_and_token(client) -> str:
    db = TestingSessionLocal()
    try:
        db.add(
            User(
                email="admin@test.com",
                hashed_password=hash_password("admin1234"),
                is_admin=True,
            )
        )
        db.commit()
    finally:
        db.close()
    r = client.post(
        "/auth/login", data={"username": "admin@test.com", "password": "admin1234"}
    )
    return r.json()["access_token"]


def test_liveness(client):
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


def test_readiness(client):
    r = client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_request_id_header(client):
    r = client.get("/")
    assert "X-Request-ID" in r.headers
    assert "X-Process-Time-ms" in r.headers


def test_metrics_exposed(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text


def test_products_are_cached(client):
    token = _create_admin_and_token(client)
    headers = {"Authorization": f"Bearer {token}"}
    client.post(
        "/products/",
        json={"name": "Producto Test", "price": "10.00", "stock": 5},
        headers=headers,
    )
    first = client.get("/products/").json()
    second = client.get("/products/").json()
    assert first == second
    assert len(first) == 1


def test_analytics_requires_auth(client):
    assert client.get("/analytics/summary").status_code == 401


def test_analytics_summary(client):
    token = _create_admin_and_token(client)
    r = client.get(
        "/analytics/summary", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "total_orders" in body
    assert "total_revenue" in body
    assert "top_products" in body
