from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings
from app.models import Role
from tests.conftest import PASSWORD


def test_login_and_me(client, users):
    response = client.post("/auth/token", data={"username": "OPERATOR@teste.dev ", "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["role"] == "operator"
    assert "password_hash" not in me.json()


def test_same_error_for_wrong_password_and_unknown_email(client, users):
    wrong = client.post("/auth/token", data={"username": "admin@teste.dev", "password": "errada-123456"})
    unknown = client.post("/auth/token", data={"username": "ninguem@teste.dev", "password": "errada-123456"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_login_is_blocked_after_repeated_failures(client, users):
    for _ in range(5):
        client.post("/auth/token", data={"username": "admin@teste.dev", "password": "errada-123456"})
    blocked = client.post("/auth/token", data={"username": "admin@teste.dev", "password": PASSWORD})
    assert blocked.status_code == 429


def test_rejects_missing_tampered_and_expired_tokens(client, users, auth_headers):
    assert client.get("/auth/me").status_code == 401

    token = auth_headers[Role.viewer]["Authorization"].split()[1]
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token[:-3]}abc"}).status_code == 401

    forged = jwt.encode(
        {"sub": str(users[Role.admin].id), "exp": datetime.now(UTC) + timedelta(hours=1)}, "outro-segredo-qualquer-com-32-chars!!", algorithm="HS256"
    )
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401

    expired = jwt.encode(
        {"sub": str(users[Role.admin].id), "exp": datetime.now(UTC) - timedelta(minutes=1)}, get_settings().jwt_secret, algorithm="HS256"
    )
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_deactivated_user_loses_access_immediately(client, users, auth_headers):
    viewer_id = users[Role.viewer].id
    response = client.patch(f"/users/{viewer_id}", json={"is_active": False}, headers=auth_headers[Role.admin])
    assert response.status_code == 200
    assert client.get("/auth/me", headers=auth_headers[Role.viewer]).status_code == 401


def test_security_headers(client):
    response = client.get("/docs")
    assert response.headers["x-frame-options"] == "DENY"
    assert "cdn.jsdelivr.net" in response.headers["content-security-policy"]
    api = client.get("/auth/me")
    assert api.headers["content-security-policy"].startswith("default-src 'none'")
