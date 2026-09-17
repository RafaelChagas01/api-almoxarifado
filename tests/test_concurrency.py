import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.models import Role

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="precisa de PostgreSQL (roda no CI)")


def test_simultaneous_exits_never_go_negative(client, auth_headers, product):
    # 10 em estoque, duas saidas de 7 ao mesmo tempo: so uma pode passar
    headers = auth_headers[Role.operator]

    def exit_seven():
        return client.post(f"/products/{product.id}/movements", json={"type": "exit", "quantity": 7}, headers=headers).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(lambda _: exit_seven(), range(2)))

    assert results == [201, 409]
    assert client.get(f"/products/{product.id}", headers=headers).json()["quantity"] == 3
