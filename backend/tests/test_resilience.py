import asyncio
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.agent.model import Classification, GeminiModel, budget
from backend.app.config import Settings
from backend.app.errors import AppError
from backend.app.main import create_app
from backend.app.storage import Store
from backend.tests.fakes import ScriptedModel
from backend.tests.test_api import ORIGIN, conversation, login, message
from data.seed import seed


def settings_for(root):
    seed(root / "sample.db")
    return Settings(
        _env_file=None,
        state_dir=root / "state",
        sample_db=root / "sample.db",
        google_api_key="",
        model_name="",
        public_origin=ORIGIN,
    )


def test_overlapping_turns_are_rejected(tmp_path):
    class SlowModel(ScriptedModel):
        async def ask(self, *args, **kwargs):
            await asyncio.sleep(0.2)
            return await super().ask(*args, **kwargs)

    settings = settings_for(tmp_path)
    with TestClient(create_app(settings, SlowModel), base_url=ORIGIN) as client:
        login(client)
        cid = conversation(client)
        with ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(message, client, cid, "Show customers") for _ in range(2)]
            statuses = sorted(f.result().status_code for f in futures)
        assert statuses == [200, 409]


def test_stale_artifact_and_quota(tmp_path):
    settings = settings_for(tmp_path)
    with TestClient(create_app(settings, ScriptedModel), base_url=ORIGIN) as client:
        login(client)
        cid = conversation(client)
        aid = message(client, cid, "Show customers").json()["sql"]["artifact_id"]
        with client.app.state.store.db() as con:
            con.execute("UPDATE artifacts SET validator_version='old' WHERE id=?", (aid,))
        result = client.post(f"/api/v1/queries/{aid}/execute", json={"request_id": str(uuid4())})
        assert result.status_code == 409 and result.json()["error"]["code"] == "STALE_QUERY"
        client.app.state.store.charge("test-limit", 1)
        with pytest.raises(AppError) as exc:
            client.app.state.store.charge("test-limit", 1)
        assert exc.value.status == 429


def test_checkpoint_reconciles_incomplete_api_commit(tmp_path):
    settings = settings_for(tmp_path)
    rid = str(uuid4())
    with TestClient(create_app(settings, ScriptedModel), base_url=ORIGIN) as first:
        login(first)
        cid = conversation(first)
        original = message(first, cid, "Show customers", rid).json()
        cookies = dict(first.cookies)
        csrf = first.headers["x-csrf-token"]
        with first.app.state.store.db() as con:
            con.execute(
                "UPDATE turns SET status='processing',response=NULL WHERE id=?", (original["turn_id"],)
            )
    with TestClient(create_app(settings, ScriptedModel), base_url=ORIGIN) as second:
        second.cookies.update(cookies)
        second.headers.update({"origin": ORIGIN, "x-csrf-token": csrf})
        replay = message(second, cid, "Show customers", rid).json()
        assert replay == original


@pytest.mark.asyncio
async def test_provider_rate_error_is_specific_and_safe(tmp_path):
    class LimitedClient:
        def with_structured_output(self, *args, **kwargs):
            return self

        async def ainvoke(self, *args, **kwargs):
            raise RuntimeError("429 RESOURCE_EXHAUSTED confidential-provider-body")

    settings = Settings(_env_file=None, google_api_key="", model_name="")
    model = GeminiModel(settings, Store(tmp_path / "state.db"))
    model.client = LimitedClient()
    token = budget.set({"calls": 0})
    try:
        with pytest.raises(AppError) as exc:
            await model.ask("classify", Classification, {})
        assert exc.value.status == 429 and exc.value.code == "MODEL_RATE_LIMIT"
        assert "confidential" not in exc.value.message
    finally:
        budget.reset(token)


def test_explain_supplied_sql_preserves_query_without_generation(tmp_path):
    class ExplainOnlyModel(ScriptedModel):
        async def ask(self, prompt, schema, data):
            assert prompt == "explain", "Supplied SQL must not be regenerated or optimized."
            return await super().ask(prompt, schema, data)

    settings = settings_for(tmp_path)
    with TestClient(create_app(settings, ExplainOnlyModel), base_url=ORIGIN) as client:
        login(client)
        cid = conversation(client)
        result = message(
            client,
            cid,
            "Explain this SQL: SELECT o.order_id FROM orders o JOIN customers c ON o.customer_id=c.customer_id",
        ).json()
        assert result["status"] == "completed"
        assert result["intent"] == "explain_sql"
        assert "JOIN" in result["sql"]["text"]
        assert not result["optimization"]["rewrite_applied"]


@pytest.mark.asyncio
async def test_transient_provider_status_retries_once(tmp_path):
    class Unavailable(Exception):
        code = 503

    class RecoveringClient:
        calls = 0

        def with_structured_output(self, *args, **kwargs):
            return self

        async def ainvoke(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise Unavailable("temporary unavailable")
            return {"parsed": Classification(intent="generate", in_scope=True), "raw": None}

    settings = Settings(_env_file=None, google_api_key="", model_name="")
    model = GeminiModel(settings, Store(tmp_path / "state.db"))
    model.client = RecoveringClient()
    token = budget.set({"calls": 0})
    try:
        result = await model.ask("classify", Classification, {})
        assert result.intent == "generate"
        assert model.client.calls == 2
        assert budget.get()["calls"] == 2
    finally:
        budget.reset(token)
