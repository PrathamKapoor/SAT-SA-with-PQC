"""Database engine behavior against an isolated, real PostgreSQL schema."""
from __future__ import annotations

import os
import threading
import uuid
from urllib.parse import quote

import pytest

from qsmlops.database.engine import SQLiteDatabaseEngine, create_engine


@pytest.fixture
def postgres_dsn():
    dsn = os.getenv("SATSA_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("set SATSA_TEST_POSTGRES_DSN for PostgreSQL integration tests")
    psycopg = pytest.importorskip("psycopg")
    from psycopg import sql

    schema = f"satsa_test_{uuid.uuid4().hex}"
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    try:
        separator = "&" if "?" in dsn else "?"
        yield f"{dsn}{separator}options={quote(f'-c search_path={schema}') }"
    finally:
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_sqlite_factory_still_selects_sqlite(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'local.db'}")
    assert isinstance(engine, SQLiteDatabaseEngine)
    engine.close()


def test_postgres_bound_values_and_quoted_question_marks(postgres_dsn):
    engine = create_engine(postgres_dsn)
    try:
        assert engine.dialect == "postgresql"
        engine.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, note TEXT NOT NULL)")
        engine.execute("INSERT INTO sample (id, note) VALUES (?, ?)", (1, "what?"))
        assert engine.query_one(
            "SELECT note, '?' AS marker FROM sample WHERE id=?", (1,)
        ) == {"note": "what?", "marker": "?"}
        assert engine.query_all("SELECT id FROM sample WHERE note=?", ("what?",)) == [{"id": 1}]
    finally:
        engine.close()


def test_postgres_nested_transaction_commits_and_rolls_back(postgres_dsn):
    engine = create_engine(postgres_dsn)
    try:
        engine.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
        with engine.transaction():
            engine.execute("INSERT INTO sample (id) VALUES (?)", (1,))
            with engine.transaction():
                engine.execute("INSERT INTO sample (id) VALUES (?)", (2,))
        assert engine.query_all("SELECT id FROM sample ORDER BY id") == [{"id": 1}, {"id": 2}]

        with pytest.raises(RuntimeError, match="abort"):
            with engine.transaction():
                engine.execute("INSERT INTO sample (id) VALUES (?)", (3,))
                with engine.transaction():
                    engine.execute("INSERT INTO sample (id) VALUES (?)", (4,))
                raise RuntimeError("abort")
        assert engine.query_all("SELECT id FROM sample ORDER BY id") == [{"id": 1}, {"id": 2}]
    finally:
        engine.close()


def test_postgres_transaction_connection_is_thread_local(postgres_dsn):
    engine = create_engine(postgres_dsn)
    try:
        engine.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
        observed = []
        errors = []

        def read_from_other_thread():
            try:
                observed.append(engine.query_one("SELECT COUNT(*) AS count FROM sample"))
            except Exception as exc:
                errors.append(exc)

        with engine.transaction():
            engine.execute("INSERT INTO sample (id) VALUES (?)", (1,))
            thread = threading.Thread(target=read_from_other_thread)
            thread.start()
            thread.join(timeout=5)
            assert not thread.is_alive(), "query must use another pooled connection"
        assert not errors
        assert observed == [{"count": 0}], "other connection must not see uncommitted data"
        assert engine.query_one("SELECT COUNT(*) AS count FROM sample") == {"count": 1}
    finally:
        engine.close()
