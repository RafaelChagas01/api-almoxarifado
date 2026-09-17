import pytest

from app.models import Role


def test_admin_creates_product_and_sku_is_normalized(client, auth_headers):
    response = client.post(
        "/products", json={"sku": " cabo-pp-2x15 ", "name": "Cabo PP 2 x 1,5 mm", "unit": "m", "min_stock": 50}, headers=auth_headers[Role.admin]
    )
    assert response.status_code == 201
    assert response.json()["sku"] == "CABO-PP-2X15"
    assert response.json()["quantity"] == 0


def test_duplicate_sku_returns_409(client, auth_headers, product):
    response = client.post("/products", json={"sku": "PAR-M6-40", "name": "Outro", "unit": "un"}, headers=auth_headers[Role.admin])
    assert response.status_code == 409


@pytest.mark.parametrize("role", [Role.operator, Role.viewer])
def test_only_admin_creates_or_edits(client, auth_headers, product, role):
    headers = auth_headers[role]
    assert client.post("/products", json={"sku": "NOVO-1", "name": "Novo", "unit": "un"}, headers=headers).status_code == 403
    assert client.patch(f"/products/{product.id}", json={"name": "Mudou"}, headers=headers).status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"sku": "OK-123", "name": "Produto", "unit": "un", "quantity": 999},
        {"sku": "OK-123", "name": "Produto", "unit": "un", "is_admin": True},
        {"sku": "a", "name": "Produto", "unit": "un"},
        {"sku": "OK-123", "name": "P", "unit": "un"},
        {"sku": "OK-123", "name": "Produto", "unit": "tonelada"},
        {"sku": "OK-123", "name": "Produto", "unit": "un", "min_stock": -1},
        {"sku": "'; drop table products;--", "name": "Produto", "unit": "un"},
    ],
)
def test_invalid_or_extra_fields_are_rejected(client, auth_headers, payload):
    response = client.post("/products", json=payload, headers=auth_headers[Role.admin])
    assert response.status_code == 422
    assert "999" not in response.text


def test_update_cannot_change_quantity(client, auth_headers, product):
    response = client.patch(f"/products/{product.id}", json={"quantity": 1000}, headers=auth_headers[Role.admin])
    assert response.status_code == 422
    assert client.get(f"/products/{product.id}", headers=auth_headers[Role.viewer]).json()["quantity"] == 10


def test_list_with_search_filter_and_pagination(client, auth_headers):
    admin = auth_headers[Role.admin]
    for i in range(25):
        client.post("/products", json={"sku": f"ITEM-{i:03}", "name": f"Item {i:03}", "unit": "un", "min_stock": i}, headers=admin)

    page = client.get("/products?page=2&page_size=10", headers=auth_headers[Role.viewer]).json()
    assert page["total"] == 25 and len(page["items"]) == 10 and page["items"][0]["sku"] == "ITEM-010"

    found = client.get("/products?search=item-02", headers=auth_headers[Role.viewer]).json()
    assert found["total"] == 5

    below = client.get("/products?below_minimum=true", headers=auth_headers[Role.viewer]).json()
    assert below["total"] == 24

    assert client.get("/products?page_size=1000", headers=auth_headers[Role.viewer]).status_code == 422


def test_inactive_products_are_hidden_by_default(client, auth_headers, product):
    client.patch(f"/products/{product.id}", json={"is_active": False}, headers=auth_headers[Role.admin])
    viewer = auth_headers[Role.viewer]
    assert client.get("/products", headers=viewer).json()["total"] == 0
    assert client.get("/products?include_inactive=true", headers=viewer).json()["total"] == 1
