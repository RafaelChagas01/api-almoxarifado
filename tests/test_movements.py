from app.models import Role


def move(client, headers, product_id, **payload):
    return client.post(f"/products/{product_id}/movements", json=payload, headers=headers)


def test_entry_and_exit_update_balance(client, auth_headers, product):
    operator = auth_headers[Role.operator]
    assert move(client, operator, product.id, type="entry", quantity=15).json()["balance_after"] == 25
    exit_ = move(client, operator, product.id, type="exit", quantity=5, note="Linha 2")
    assert exit_.status_code == 201
    assert exit_.json()["balance_after"] == 20
    assert exit_.json()["user_name"] == "Operator"

    history = client.get(f"/products/{product.id}/movements", headers=auth_headers[Role.viewer]).json()
    assert [m["type"] for m in history] == ["exit", "entry"]


def test_exit_cannot_leave_negative_stock(client, auth_headers, product):
    response = move(client, auth_headers[Role.operator], product.id, type="exit", quantity=11)
    assert response.status_code == 409
    assert "10 available" in response.json()["detail"]
    assert client.get(f"/products/{product.id}", headers=auth_headers[Role.viewer]).json()["quantity"] == 10


def test_adjustment_sets_counted_value_and_requires_note(client, auth_headers, product):
    operator = auth_headers[Role.operator]
    assert move(client, operator, product.id, type="adjustment", quantity=7).status_code == 422
    response = move(client, operator, product.id, type="adjustment", quantity=7, note="Inventário de setembro")
    assert response.status_code == 201
    assert response.json()["balance_after"] == 7


def test_zero_or_negative_quantities_are_rejected(client, auth_headers, product):
    operator = auth_headers[Role.operator]
    assert move(client, operator, product.id, type="entry", quantity=0).status_code == 422
    assert move(client, operator, product.id, type="exit", quantity=-5).status_code == 422
    assert move(client, operator, product.id, type="entry", quantity=5, user_id=1).status_code == 422


def test_viewer_cannot_move_stock(client, auth_headers, product):
    assert move(client, auth_headers[Role.viewer], product.id, type="entry", quantity=1).status_code == 403


def test_inactive_or_missing_product(client, auth_headers, product):
    client.patch(f"/products/{product.id}", json={"is_active": False}, headers=auth_headers[Role.admin])
    assert move(client, auth_headers[Role.operator], product.id, type="entry", quantity=1).status_code == 409
    assert move(client, auth_headers[Role.operator], 9999, type="entry", quantity=1).status_code == 404


def test_reports(client, auth_headers, product):
    viewer = auth_headers[Role.viewer]
    low = client.get("/reports/low-stock", headers=viewer).json()
    assert low == [{"id": product.id, "sku": "PAR-M6-40", "name": "Parafuso M6", "unit": "un", "quantity": 10, "min_stock": 20, "missing": 10}]

    move(client, auth_headers[Role.operator], product.id, type="exit", quantity=10)
    summary = client.get("/reports/summary", headers=viewer).json()
    assert summary == {"active_products": 1, "below_minimum": 1, "out_of_stock": 1, "movements_last_7_days": 1}
