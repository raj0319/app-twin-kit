"""Exercise generated routes, transactions and relationships with an isolated database."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from engine.generate import generate

EXAMPLE = Path(__file__).resolve().parents[1] / "fixtures/example-uas.json"


@pytest.mark.skipif(
    not os.environ.get("TWIN_TEST_DATABASE_URL"), reason="isolated PostgreSQL test URL required"
)
def test_generated_postgres_app(tmp_path):
    database_url = os.environ["TWIN_TEST_DATABASE_URL"]
    from sqlalchemy.engine import make_url

    database = make_url(database_url)
    assert database.host in {"localhost", "127.0.0.1", "::1"}
    assert database.database.startswith("app_twin_fixture"), "disposable database required"
    generate(EXAMPLE, tmp_path)
    backend = tmp_path / "backend"
    env = {**os.environ, "DATABASE_URL": database_url, "TWIN_API_TOKEN": "fixture-only-token"}
    env.pop("DATABASE_URL_FILE", None)
    env.pop("TWIN_API_TOKEN_FILE", None)
    args = [sys.executable, "-m", "alembic"]
    subprocess.run([*args, "upgrade", "head"], cwd=backend, env=env, check=True)
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
from fastapi.testclient import TestClient
from main import app

with TestClient(app) as client:
    assert client.get('/api/health').json() == {'status': 'ok'}
    assert client.get('/api/customer').status_code == 401
    token = {'Authorization': 'Bearer fixture-only-token'}
    customer = client.post('/api/customer', json={'name': 'ZZTEST CUSTOMER'}, headers=token)
    assert customer.status_code == 201, customer.text
    payload = {'customer_id': customer.json()['id'], 'code': 'ZZTEST_API', 'quantity': 3, 'unit_price': 11}
    invalid = client.post('/api/order_entry', json={**payload, 'quantity': 0}, headers=token)
    assert invalid.status_code == 422 and invalid.json()['detail'][0]['rule'] == 'min'
    assert client.post('/api/order_entry', json={**payload, 'customer_id': -1}, headers=token).status_code == 409
    assert client.post('/api/order_entry/preview', json=payload, headers=token).json()['total'] == 33
    assert client.get('/api/order_entry', headers=token).json() == []
    order = client.post('/api/order_entry', json=payload, headers=token)
    assert order.status_code == 201 and order.json()['total'] == 33, order.text
    assert client.post('/api/order_entry', json=payload, headers=token).status_code == 409
    assert client.get('/api/order_entry?limit=1', headers=token).json() == [order.json()]
    assert client.get('/api/order_entry?limit=1&offset=1', headers=token).json() == []
""",
        ],
        cwd=backend,
        env=env,
        check=True,
    )
    subprocess.run([*args, "downgrade", "base"], cwd=backend, env=env, check=True)
