"""Opt-in integration tests against a real PostgreSQL server, in a disposable schema."""

import asyncio
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql as pgsql

from backend.app.config import Settings
from backend.app.errors import AppError
from backend.app.main import create_app
from backend.app.postgres import PostgresStore
from backend.tests.fakes import ScriptedModel
from backend.tests.test_api import ORIGIN, conversation, login, message
from data.seed import seed
from scripts.setup_database import setup

pytestmark = pytest.mark.skipif(os.getenv("RUN_POSTGRES_TESTS") != "1", reason="Opt-in real PostgreSQL tests")


@pytest.fixture(scope="module")
def pg_settings(tmp_path_factory):
    root = tmp_path_factory.mktemp("postgres")
    seed(root / "sample.db")
    settings = Settings(
        sample_db=root / "sample.db",
        state_dir=root / "unused",
        database_schema="qc_test_" + uuid4().hex,
        public_origin=ORIGIN,
        secure_cookies=False,
        vercel=False,
        session_rate=1000,
        ip_rate=1000,
        global_concurrency=4,
    )
    if not settings.database_url:
        pytest.fail("Configure the two database URLs before opting into PostgreSQL tests.")
    kwargs = {"loop_factory": asyncio.SelectorEventLoop} if sys.platform == "win32" else {}
    asyncio.run(setup(settings), **kwargs)
    yield settings
    # Only the randomly generated schema owned by this fixture is removed.
    assert settings.database_schema.startswith("qc_test_")
    with psycopg.connect(settings.database_url_unpooled.get_secret_value()) as con:
        con.execute(pgsql.SQL("DROP SCHEMA {} CASCADE").format(pgsql.Identifier(settings.database_schema)))


def client_for(settings, model=ScriptedModel):
    options = {"loop_factory": asyncio.SelectorEventLoop} if sys.platform == "win32" else {}
    return TestClient(create_app(settings, model), base_url=ORIGIN, backend_options=options)


def copy_session(source, target):
    target.cookies.update(dict(source.cookies))
    target.headers.update({"origin": ORIGIN, "x-csrf-token": source.headers["x-csrf-token"]})


def test_persistence_followup_exports_and_isolation(pg_settings):
    with client_for(pg_settings) as first:
        login(first)
        cid = conversation(first)
        initial = message(first, cid, "Only California")
        assert initial.status_code == 200 and initial.json()["status"] == "completed"
        # A separate API instance uses the same durable history/checkpoints.
        with client_for(pg_settings) as second:
            copy_session(first, second)
            result = message(second, cid, "Sort by last name").json()
            assert result["status"] == "completed"
            assert "'CA'" in result["sql"]["text"] and "ORDER BY" in result["sql"]["text"]
            aid = result["sql"]["artifact_id"]
            request = {"request_id": str(uuid4())}
            executed = second.post(f"/api/v1/queries/{aid}/execute", json=request)
            assert executed.status_code == 200
            assert executed.json()["returned_row_count"] == 40
            assert second.post(f"/api/v1/queries/{aid}/execute", json=request).json() == executed.json()
            eid = executed.json()["execution_id"]
            assert len(second.get(f"/api/v1/executions/{eid}/download").text.splitlines()) == 41
            assert second.get(f"/api/v1/queries/{aid}/plan").status_code == 200
            second.cookies.clear()
            login(second)
            assert second.get(f"/api/v1/conversations/{cid}").status_code == 404
            assert second.get(f"/api/v1/executions/{eid}/download").status_code == 404
        assert first.delete(f"/api/v1/conversations/{cid}").status_code == 204
        assert first.get(f"/api/v1/queries/{aid}/download").status_code == 404


def test_cross_instance_lock_and_cold_start(pg_settings):
    started, release = threading.Event(), threading.Event()

    class WaitingModel(ScriptedModel):
        async def ask(self, *args, **kwargs):
            started.set()
            await asyncio.to_thread(release.wait, 15)
            return await super().ask(*args, **kwargs)

    with client_for(pg_settings, WaitingModel) as first:
        login(first)
        cid = conversation(first)
        with ThreadPoolExecutor(1) as executor:
            future = executor.submit(message, first, cid, "Show customers")
            try:
                assert started.wait(15)
                # Starting another instance must not mark the first's turn interrupted.
                with client_for(pg_settings) as second:
                    copy_session(first, second)
                    duplicate = message(second, cid, "Only California")
                    assert duplicate.status_code == 409
                    assert second.delete(f"/api/v1/conversations/{cid}").status_code == 409
                    history = second.get(f"/api/v1/conversations/{cid}").json()
                    assert history["turns"]["items"][-1]["status"] == "processing"
            finally:
                release.set()
            assert future.result(timeout=30).json()["status"] == "completed"


def test_postgres_quota_is_atomic(pg_settings):
    bucket = "test-quota-" + uuid4().hex

    def consume(_):
        try:
            PostgresStore(pg_settings).charge(bucket, 2)
            return True
        except AppError as exc:
            assert exc.code == "RATE_LIMIT"
            return False

    with ThreadPoolExecutor(6) as executor:
        assert sum(executor.map(consume, range(6))) == 2


def test_checkpoint_recovery_is_idempotent(pg_settings):
    rid = str(uuid4())
    with client_for(pg_settings) as first:
        login(first)
        cid = conversation(first)
        original = message(first, cid, "Only California", rid).json()
        assert original["status"] == "completed"
        with first.app.state.store.db() as con:
            con.execute(
                "UPDATE turns SET status='processing',response=NULL WHERE id=?", (original["turn_id"],)
            )
        with client_for(pg_settings) as second:
            copy_session(first, second)
            assert message(second, cid, "Only California", rid).json() == original
            assert "'CA'" in message(second, cid, "Sort by last name").json()["sql"]["text"]
