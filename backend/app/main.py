import asyncio
import csv
import io
import logging
import secrets
import threading
import time
from contextlib import asynccontextmanager
from typing import Literal
from uuid import UUID

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel, ConfigDict, Field

from backend.app.agent.graph import Agent
from backend.app.agent.model import GeminiModel
from backend.app.config import Settings
from backend.app.errors import AppError
from backend.app.sql.catalog import Catalog
from backend.app.sql.service import SqlService, VALIDATOR_VERSION, digest
from backend.app.storage import Store

log = logging.getLogger("querycraft")
COOKIE = "querycraft_session"


class MessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    message: str = Field(min_length=1, max_length=8000)
    mode: Literal["auto", "generate", "optimize", "debug", "explain"] = "auto"


class ConversationInput(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=80)


class ExecuteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID


def failure(cid, tid, rid, error):
    return {
        "request_id": rid,
        "conversation_id": cid,
        "turn_id": tid,
        "status": "failed",
        "intent": "unknown",
        "message": error.message,
        "sql": None,
        "explanation": None,
        "diagnostics": [],
        "optimization": None,
        "clarification": None,
        "error": error.payload(),
        "meta": {"execution_available": False, "total_duration_ms": 0, "http_status": error.status},
    }


def csv_snapshot(result):
    output = io.StringIO(newline="")
    writer = csv.writer(output)

    def neutralize(value):
        if isinstance(value, str) and (
            value.startswith(("\t", "\r")) or value.lstrip().startswith(("=", "+", "-", "@"))
        ):
            return "'" + value
        return "" if value is None else value

    writer.writerow([neutralize(c["name"]) for c in result["columns"]])
    for row in result["rows"]:
        writer.writerow([neutralize(v) for v in row])
    return output.getvalue()


def create_app(settings=None, model_factory=None):
    settings = settings or Settings()
    active = set()
    active_models = set()

    @asynccontextmanager
    async def lifespan(app):
        settings.state_dir.mkdir(parents=True, exist_ok=True)
        app.state.settings = settings
        app.state.store = store = Store(settings.state_dir / "app.db")
        app.state.catalog = catalog = Catalog(settings.sample_db)
        app.state.sql = SqlService(catalog, settings.query_timeout)
        async with AsyncSqliteSaver.from_conn_string(str(settings.state_dir / "checkpoints.db")) as saver:
            await saver.setup()
            app.state.saver = saver
            model = model_factory(settings, store) if model_factory else GeminiModel(settings, store)
            app.state.agent = agent = Agent(model, app.state.sql, saver)
            # Resolve checkpoint-before-API-commit crashes without duplicating completed model work.
            for turn in store.pending():
                state = await agent.graph.aget_state({"configurable": {"thread_id": turn["conversation_id"]}})
                completed = state.values.get("response") or {}
                if completed.get("turn_id") == turn["id"]:
                    store.complete(turn["id"], completed, VALIDATOR_VERSION)
                else:
                    error = AppError(
                        "INTERRUPTED",
                        "The server restarted during this response. Send the request again.",
                        503,
                        True,
                    )
                    store.complete(
                        turn["id"],
                        failure(turn["conversation_id"], turn["id"], turn["request_id"], error),
                        VALIDATOR_VERSION,
                    )

            async def cleanup():
                while True:
                    for cid in store.cleanup():
                        await saver.adelete_thread(cid)
                    await asyncio.sleep(600)

            cleanup_task = asyncio.create_task(cleanup())
            try:
                yield
            finally:
                cleanup_task.cancel()
                try:
                    await cleanup_task
                except asyncio.CancelledError:
                    pass

    app = FastAPI(title="Querycraft SQL Assistant", version="1.0.0", lifespan=lifespan)

    @app.exception_handler(AppError)
    async def app_error(request, error):
        return JSONResponse(
            {"error": error.payload()},
            status_code=error.status,
            headers={"Retry-After": "60"} if error.status == 429 else None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Pydantic errors can echo user input. Return field locations only.
        return JSONResponse(
            {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "Check the submitted fields.",
                    "retryable": False,
                },
                "fields": [".".join(str(v) for v in e["loc"]) for e in error.errors()],
            },
            status_code=422,
        )

    @app.middleware("http")
    async def boundary(request, call_next):
        started = time.monotonic()
        if request.url.path.startswith("/api/"):
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 32768:
                    return JSONResponse(
                        {
                            "error": {
                                "code": "BODY_TOO_LARGE",
                                "message": "The request is too large.",
                                "retryable": False,
                            }
                        },
                        status_code=413,
                    )
            request._body = bytes(body)
            if (
                request.method in {"POST", "DELETE", "PUT", "PATCH"}
                and request.headers.get("origin") != settings.public_origin
            ):
                return JSONResponse(
                    {
                        "error": {
                            "code": "ORIGIN_DENIED",
                            "message": "This request origin is not allowed.",
                            "retryable": False,
                        }
                    },
                    status_code=403,
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if settings.secure_cookies:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        log.info(
            "http method=%s route=%s status=%s duration_ms=%d",
            request.method,
            request.scope.get("route").path if request.scope.get("route") else "unmatched",
            response.status_code,
            (time.monotonic() - started) * 1000,
        )
        return response

    async def session(request: Request):
        return request.app.state.store.session(request.cookies.get(COOKIE))

    async def mutation(request: Request, current=Depends(session)):
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), current["csrf"]):
            raise AppError("CSRF_DENIED", "Refresh the page before retrying this action.", 403)
        return current

    def session_response(current):
        return {
            "csrf_token": current["csrf"],
            "expires_at": current["expires"],
            "model_configured": settings.model_ready,
            "model": settings.model_name if settings.model_ready else None,
        }

    @app.post("/api/v1/session")
    async def new_session(request: Request):
        store = request.app.state.store
        try:
            current = store.session(request.cookies.get(COOKIE))
            return session_response(current)
        except AppError:
            store.charge("session-create:" + str(request.client.host), 60)
            token, current = store.create_session()
            response = JSONResponse(session_response(current), status_code=201)
            response.set_cookie(
                COOKIE,
                token,
                httponly=True,
                samesite="lax",
                secure=settings.secure_cookies,
                max_age=7 * 86400,
            )
            return response

    @app.get("/api/v1/session")
    async def get_session(current=Depends(session)):
        return session_response(current)

    @app.get("/api/v1/health/live")
    async def live():
        return {"status": "ok"}

    @app.get("/api/v1/health/ready")
    async def ready(request: Request):
        with request.app.state.store.db() as con:
            con.execute("SELECT 1")
        return JSONResponse(
            {
                "status": "ready" if settings.model_ready else "configuration_required",
                "schema_version": request.app.state.catalog.version,
                "model_configured": settings.model_ready,
            },
            status_code=200 if settings.model_ready else 503,
        )

    @app.get("/api/v1/schema")
    async def schema(request: Request, current=Depends(session)):
        return request.app.state.catalog.as_dict()

    @app.post("/api/v1/conversations", status_code=201)
    async def create_conversation(data: ConversationInput, request: Request, current=Depends(mutation)):
        request.app.state.store.charge("conversation:" + current["id"], 30)
        return request.app.state.store.create_conversation(current["id"], data.title)

    @app.get("/api/v1/conversations")
    async def list_conversations(
        request: Request,
        cursor: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=50),
        current=Depends(session),
    ):
        return request.app.state.store.conversations(current["id"], cursor, limit)

    @app.get("/api/v1/conversations/{cid}")
    async def get_conversation(
        cid: UUID,
        request: Request,
        cursor: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=50),
        current=Depends(session),
    ):
        store = request.app.state.store
        return {
            **store.conversation(str(cid), current["id"]),
            "turns": store.history(str(cid), cursor, limit),
        }

    @app.delete("/api/v1/conversations/{cid}", status_code=204)
    async def delete_conversation(cid: UUID, request: Request, current=Depends(mutation)):
        cid = str(cid)
        store = request.app.state.store
        store.conversation(cid, current["id"])
        if cid in active:
            raise AppError("TURN_BUSY", "Wait for the current operation to finish.", 409, True)
        active.add(cid)
        try:
            await request.app.state.saver.adelete_thread(cid)
            store.delete(cid, current["id"])
        finally:
            active.discard(cid)
        return Response(status_code=204)

    @app.post("/api/v1/conversations/{cid}/messages")
    async def messages(cid: UUID, data: MessageInput, request: Request, current=Depends(mutation)):
        cid, rid = str(cid), str(data.request_id)
        store = request.app.state.store
        store.conversation(cid, current["id"])
        if not data.message.strip():
            raise AppError("EMPTY_MESSAGE", "Enter a question or SQL query.", 422)
        if cid in active:
            raise AppError("TURN_BUSY", "Wait for the current operation to finish.", 409, True)
        if len(active_models) >= settings.global_concurrency:
            raise AppError("BUSY", "The assistant is busy. Please retry shortly.", 429, True)
        tid, replay = store.begin_turn(cid, rid, data.message, data.mode)
        if replay is not None:
            return JSONResponse(replay, status_code=replay.get("meta", {}).get("http_status", 200))
        active.add(cid)
        active_models.add(cid)
        try:
            store.charge("messages:" + current["id"], settings.session_rate)
            store.charge("model-ip:" + str(request.client.host), settings.ip_rate)
            history = [
                {"user": t["message"], "assistant": (t["response"] or {}).get("message", "")}
                for t in store.history(cid, limit=10)["items"]
                if t["id"] != tid
            ]
            response = await asyncio.wait_for(
                request.app.state.agent.run(cid, tid, rid, data.message, data.mode, history),
                timeout=settings.turn_timeout,
            )
        except asyncio.CancelledError:
            store.complete(
                tid,
                failure(cid, tid, rid, AppError("CANCELLED", "The response was interrupted.", 503, True)),
                VALIDATOR_VERSION,
            )
            raise
        except TimeoutError:
            response = failure(
                cid, tid, rid, AppError("TURN_TIMEOUT", "The response timed out. Please retry.", 504, True)
            )
        except AppError as exc:
            response = failure(cid, tid, rid, exc)
        except Exception:
            log.error("turn_failed turn_id=%s", tid)
            response = failure(
                cid, tid, rid, AppError("INTERNAL_ERROR", "The response could not be completed.", 500, True)
            )
        finally:
            active.discard(cid)
            active_models.discard(cid)
        store.complete(tid, response, VALIDATOR_VERSION)
        return JSONResponse(response, status_code=response.get("meta", {}).get("http_status", 200))

    def artifact(request, aid, current):
        row = request.app.state.store.artifact(str(aid), current["id"])
        if (
            row["schema_version"] != request.app.state.catalog.version
            or row["validator_version"] != VALIDATOR_VERSION
        ):
            raise AppError(
                "STALE_QUERY", "The database or validator changed. Generate this query again.", 409
            )
        if digest(row["sql"]) != row["hash"]:
            raise AppError("INVALID_ARTIFACT", "This query cannot be verified. Generate it again.", 409)
        return row

    @app.post("/api/v1/queries/{aid}/execute")
    async def execute(aid: UUID, data: ExecuteInput, request: Request, current=Depends(mutation)):
        row = artifact(request, aid, current)
        cid, store = row["conversation_id"], request.app.state.store
        replay = store.previous_execution(str(aid), str(data.request_id))
        if replay:
            return replay
        if cid in active:
            raise AppError("TURN_BUSY", "Wait for the current operation to finish.", 409, True)
        store.charge("execute:" + current["id"], settings.execution_rate)
        active.add(cid)
        cancel = threading.Event()
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(request.app.state.sql.execute, row["sql"], cancel),
                timeout=settings.query_timeout + 1,
            )
            return store.save_execution(str(aid), str(data.request_id), result)
        except TimeoutError:
            raise AppError("QUERY_TIMEOUT", "The query exceeded its execution budget.", 504, True)
        finally:
            cancel.set()
            active.discard(cid)

    @app.get("/api/v1/queries/{aid}/plan")
    async def plan(aid: UUID, request: Request, current=Depends(session)):
        row = artifact(request, aid, current)
        request.app.state.store.charge("plan:" + current["id"], settings.execution_rate)
        return await asyncio.to_thread(request.app.state.sql.plan, row["sql"])

    @app.get("/api/v1/queries/{aid}/download")
    async def download_sql(aid: UUID, request: Request, current=Depends(session)):
        row = artifact(request, aid, current)
        final = await asyncio.to_thread(request.app.state.sql.validate, row["sql"])
        return Response(
            final + ";\n",
            media_type="application/sql",
            headers={"Content-Disposition": 'attachment; filename="query.sql"'},
        )

    @app.get("/api/v1/executions/{eid}/download")
    async def download_csv(eid: UUID, request: Request, current=Depends(session)):
        result = request.app.state.store.execution(str(eid), current["id"])
        return Response(
            csv_snapshot(result),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="results.csv"'},
        )

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "DELETE", "PUT", "PATCH"])
    async def missing_api(path: str):
        raise AppError("NOT_FOUND", "This API endpoint does not exist.", 404)

    if settings.frontend_dir.exists():
        app.mount("/assets", StaticFiles(directory=settings.frontend_dir / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def frontend(path: str):
            return FileResponse(settings.frontend_dir / "index.html")
    else:

        @app.get("/", include_in_schema=False)
        async def unbuilt():
            return JSONResponse(
                {"message": "Build the frontend with npm run build in frontend/."}, status_code=503
            )

    return app


app = create_app()
