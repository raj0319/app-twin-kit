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


@pytest.mark.skipif(
    not os.environ.get("TWIN_TEST_DATABASE_URL"), reason="isolated PostgreSQL test URL required"
)
def test_schema_evolution_and_roles(tmp_path):
    import json

    database_url = os.environ["TWIN_TEST_DATABASE_URL"]
    from sqlalchemy.engine import make_url

    assert make_url(database_url).database.startswith("app_twin_fixture"), "disposable database required"
    app = tmp_path / "app"
    generate(EXAMPLE, app)
    backend = app / "backend"
    roles = json.dumps({"clerk": "clerk-fixture-token", "manager": "manager-fixture-token"})
    env = {
        **os.environ,
        "DATABASE_URL": database_url,
        "TWIN_API_TOKEN": "fixture-only-token",
        "TWIN_ROLE_TOKENS": roles,
    }
    for key in ("DATABASE_URL_FILE", "TWIN_API_TOKEN_FILE", "TWIN_ROLE_TOKENS_FILE"):
        env.pop(key, None)
    alembic = [sys.executable, "-m", "alembic"]

    def client(script):
        prefix = "from fastapi.testclient import TestClient\nfrom main import app\nclient = TestClient(app)\n"
        subprocess.run([sys.executable, "-c", prefix + script], cwd=backend, env=env, check=True)

    subprocess.run([*alembic, "upgrade", "head"], cwd=backend, env=env, check=True)
    try:
        client(
            "token = {'Authorization': 'Bearer fixture-only-token'}\n"
            "assert client.post('/api/customer', json={'name': 'ZZTEST OLD'}, headers=token).status_code == 201\n"
        )
        spec = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        customer = next(entity for entity in spec["entities"] if entity["id"] == "customer")
        customer["fields"]["region"] = "text"
        customer["permissions"] = {"read": ["clerk", "manager"], "create": ["manager"]}
        spec["entities"].append(
            {
                "id": "supplier",
                "title": "Suppliers",
                "fields": {"name": "text"},
                "evidence_ids": customer["evidence_ids"],
                "unique": ["name"],
            }
        )
        evolved = tmp_path / "evolved.json"
        evolved.write_text(json.dumps(spec), encoding="utf-8")
        result = generate(evolved, app, evolve=True)
        assert [step["op"] for step in result["evolution"]["steps"]] == ["add_column", "create_table"]
        assert (backend / "migrations/versions/0002_evolve.py").is_file()
        subprocess.run([*alembic, "upgrade", "head"], cwd=backend, env=env, check=True)
        client(
            "clerk = {'Authorization': 'Bearer clerk-fixture-token'}\n"
            "manager = {'Authorization': 'Bearer manager-fixture-token'}\n"
            "shared = {'Authorization': 'Bearer fixture-only-token'}\n"
            "assert client.get('/api/customer').status_code == 401\n"
            "assert client.get('/api/customer', headers=shared).status_code == 401\n"
            "rows = client.get('/api/customer', headers=clerk).json()\n"
            "assert rows[-1]['name'] == 'ZZTEST OLD' and rows[-1]['region'] == '', rows\n"
            "assert client.post('/api/customer', json={'name': 'ZZTEST NEW', 'region': 'N'}, headers=clerk).status_code == 403\n"
            "assert client.post('/api/customer', json={'name': 'ZZTEST NEW', 'region': 'N'}, headers=manager).status_code == 201\n"
            "assert client.post('/api/supplier', json={'name': 'ZZTEST SUP'}, headers=shared).status_code == 201\n"
        )
        removed = json.loads(evolved.read_text(encoding="utf-8"))
        next(e for e in removed["entities"] if e["id"] == "customer")["fields"].pop("region")
        evolved.write_text(json.dumps(removed), encoding="utf-8")
        with pytest.raises(ValueError, match="drop"):
            generate(evolved, app, evolve=True)
    finally:
        subprocess.run([*alembic, "downgrade", "base"], cwd=backend, env=env, check=True)
