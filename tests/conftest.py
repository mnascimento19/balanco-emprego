"""Fixture de banco para os testes.

Usa DATABASE_URL se existir (ex.: o Postgres do docker compose, ou o serviço do CI).
Senão tenta subir um Postgres embutido (pacote pixeltable-pgserver), só para dev local.
"""
import os
from pathlib import Path

import psycopg
import pytest

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def url_banco(tmp_path_factory):
    if os.environ.get("TEST_DATABASE_URL"):
        url = os.environ["TEST_DATABASE_URL"]
        # Os testes fazem DROP SCHEMA public CASCADE: nunca apontar para um banco real.
        if "test" not in url.rsplit("/", 1)[-1].split("?")[0]:
            raise RuntimeError("TEST_DATABASE_URL deve apontar para um banco com 'test' no nome.")
        yield url
        return
    import pixeltable_pgserver as pgserver

    srv = pgserver.get_server(tmp_path_factory.mktemp("pg"))
    yield srv.get_uri()
    srv.cleanup()


@pytest.fixture()
def conn(url_banco):
    with psycopg.connect(url_banco, autocommit=True) as c:
        c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
        for sql in sorted((RAIZ / "sql" / "schema").glob("*.sql")):
            c.execute(sql.read_text(encoding="utf-8"))
        yield c
