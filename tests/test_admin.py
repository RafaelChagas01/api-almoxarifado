import pytest

from app.models import Role, User
from tests.conftest import PASSWORD


def test_admin_creates_user_with_hashed_password(client, auth_headers, session_factory):
    response = client.post(
        "/users",
        json={"email": "Nova@Empresa.com", "name": "Nova Pessoa", "password": "senha-forte-2026", "role": "operator"},
        headers=auth_headers[Role.admin],
    )
    assert response.status_code == 201
    assert response.json()["email"] == "nova@empresa.com"
    assert "password" not in response.text

    with session_factory() as db:
        stored = db.query(User).filter_by(email="nova@empresa.com").one()
        assert stored.password_hash.startswith("$argon2")

    login = client.post("/auth/token", data={"username": "nova@empresa.com", "password": "senha-forte-2026"})
    assert login.status_code == 200


def test_weak_password_and_duplicate_email(client, auth_headers):
    admin = auth_headers[Role.admin]
    assert client.post("/users", json={"email": "a@b.com", "name": "Curta", "password": "123"}, headers=admin).status_code == 422
    assert client.post("/users", json={"email": "admin@teste.dev", "name": "Duplicado", "password": PASSWORD}, headers=admin).status_code == 409


@pytest.mark.parametrize("path", ["/users", "/audit-logs"])
def test_admin_routes_are_forbidden_for_others(client, auth_headers, path):
    assert client.get(path, headers=auth_headers[Role.operator]).status_code == 403
    assert client.get(path, headers=auth_headers[Role.viewer]).status_code == 403


def test_admin_cannot_lock_themselves_out(client, auth_headers, users):
    response = client.patch(f"/users/{users[Role.admin].id}", json={"role": "viewer"}, headers=auth_headers[Role.admin])
    assert response.status_code == 400


def test_audit_log_records_who_did_what(client, auth_headers, product, users):
    client.post(f"/products/{product.id}/movements", json={"type": "exit", "quantity": 4}, headers=auth_headers[Role.operator])
    client.patch(f"/products/{product.id}", json={"min_stock": 30}, headers=auth_headers[Role.admin])
    client.post("/auth/token", data={"username": "operator@teste.dev", "password": "errada-errada"})

    logs = client.get("/audit-logs", headers=auth_headers[Role.admin]).json()
    actions = [log["action"] for log in logs]
    assert actions[:3] == ["auth.login_failed", "product.update", "movement.exit"]

    movement = logs[2]
    assert movement["user_id"] == users[Role.operator].id
    assert movement["details"]["before"] == 10 and movement["details"]["after"] == 6
    assert logs[1]["details"] == {"before": {"min_stock": 20}, "after": {"min_stock": 30}}
    assert "errada" not in str(logs[0]["details"])
