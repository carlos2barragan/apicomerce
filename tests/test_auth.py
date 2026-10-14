"""Tests de autenticación: el flujo que más se rompe en producción."""


def test_health(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_and_login(client):
    r = client.post(
        "/auth/register",
        json={"email": "test@demo.com", "password": "secret123", "full_name": "Test"},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "test@demo.com"
    assert "hashed_password" not in r.json()

    r = client.post(
        "/auth/login", data={"username": "test@demo.com", "password": "secret123"}
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "test@demo.com"


def test_register_duplicate_email(client):
    payload = {"email": "dup@demo.com", "password": "secret123"}
    assert client.post("/auth/register", json=payload).status_code == 201
    assert client.post("/auth/register", json=payload).status_code == 400


def test_login_wrong_password(client):
    client.post("/auth/register", json={"email": "t2@demo.com", "password": "secret123"})
    r = client.post(
        "/auth/login", data={"username": "t2@demo.com", "password": "wrong"}
    )
    assert r.status_code == 401


def test_me_without_token(client):
    assert client.get("/auth/me").status_code == 401
