"""Persistent application state and cross-instance coordination for Vercel."""

import hashlib
import time
from contextlib import asynccontextmanager, contextmanager

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from backend.app.errors import AppError
from backend.app.storage import Store, SCHEMA


class Connection:
    """Adapt placeholders only in our fixed application-storage statements.

    User-generated SQL never passes through this adapter.
    """

    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, parameters=None):
        if statement == "BEGIN IMMEDIATE":
            # Match SQLite's serialized write transaction for read/modify/write quotas.
            return self.connection.execute("SELECT pg_advisory_xact_lock(743920, 0)")
        return self.connection.execute(statement.replace("?", "%s"), parameters)


class PostgresStore(Store):
    distributed = True

    def __init__(self, settings):
        self.settings = settings

    @contextmanager
    def db(self):
        try:
            with psycopg.connect(
                self.settings.database_url.get_secret_value(),
                connect_timeout=10,
                prepare_threshold=None,
                row_factory=dict_row,
            ) as con:
                con.execute(
                    sql.SQL("SET LOCAL search_path TO {}").format(
                        sql.Identifier(self.settings.database_schema)
                    )
                )
                con.execute("SET LOCAL statement_timeout = '10000'")
                yield Connection(con)
        except psycopg.Error:
            # Driver errors may contain hostnames or credentials; do not expose them.
            raise AppError(
                "STORAGE_UNAVAILABLE",
                "Conversation storage is temporarily unavailable. Please retry.",
                503,
                True,
            ) from None

    def initialize(self):
        with psycopg.connect(
            self.settings.database_url_unpooled.get_secret_value(), connect_timeout=10
        ) as con:
            con.execute("SELECT pg_advisory_xact_lock(743920, 1)")
            con.execute(
                sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                    sql.Identifier(self.settings.database_schema)
                )
            )
            con.execute(
                sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(self.settings.database_schema))
            )
            for statement in SCHEMA.replace("REAL", "DOUBLE PRECISION").split(";"):
                if statement.strip():
                    con.execute(statement)

    def claim_cleanup(self):
        now = time.time()
        with self.db() as con:
            return (
                con.execute(
                    "INSERT INTO quotas VALUES ('maintenance',1,?) "
                    "ON CONFLICT(bucket) DO UPDATE SET expires=excluded.expires "
                    "WHERE quotas.expires <= ? RETURNING bucket",
                    (now + 600, now),
                ).fetchone()
                is not None
            )

    def pending(self, cid=None):
        with self.db() as con:
            if cid is None:
                # A new instance must never interrupt work running in another instance.
                return []
            return [
                dict(r)
                for r in con.execute(
                    "SELECT * FROM turns WHERE conversation_id=? AND status='processing'", (cid,)
                )
            ]


class Operations:
    """One operation per conversation; global model slots shared across instances."""

    def __init__(self, settings):
        self.settings = settings
        self.active = set()
        self.models = set()

    @asynccontextmanager
    async def hold(self, cid, model=False):
        if not self.settings.database_url:
            if cid in self.active:
                raise AppError("TURN_BUSY", "Wait for the current operation to finish.", 409, True)
            if model and len(self.models) >= self.settings.global_concurrency:
                raise AppError("BUSY", "The assistant is busy. Please retry shortly.", 429, True)
            self.active.add(cid)
            if model:
                self.models.add(cid)
            try:
                yield
            finally:
                self.active.discard(cid)
                self.models.discard(cid)
            return

        # Session advisory locks require a direct connection, not a transaction pooler.
        # Closing the connection also releases locks after worker cancellation/crash.
        key = int.from_bytes(hashlib.blake2b(cid.encode(), digest_size=8).digest(), "big", signed=True)
        try:
            async with await psycopg.AsyncConnection.connect(
                self.settings.database_url_unpooled.get_secret_value(),
                autocommit=True,
                connect_timeout=10,
                prepare_threshold=None,
            ) as con:
                cur = await con.execute("SELECT pg_try_advisory_lock(%s)", (key,))
                if not (await cur.fetchone())[0]:
                    raise AppError("TURN_BUSY", "Wait for the current operation to finish.", 409, True)
                if model:
                    acquired = False
                    for slot in range(self.settings.global_concurrency):
                        cur = await con.execute("SELECT pg_try_advisory_lock(743921, %s)", (slot,))
                        if (await cur.fetchone())[0]:
                            acquired = True
                            break
                    if not acquired:
                        raise AppError("BUSY", "The assistant is busy. Please retry shortly.", 429, True)
                yield
        except psycopg.Error:
            raise AppError(
                "STORAGE_UNAVAILABLE",
                "Conversation storage is temporarily unavailable. Please retry.",
                503,
                True,
            ) from None


@asynccontextmanager
async def checkpointer(settings, setup=False):
    if not settings.database_url:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        async with AsyncSqliteSaver.from_conn_string(str(settings.state_dir / "checkpoints.db")) as saver:
            await saver.setup()
            yield saver
        return

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg_pool import AsyncConnectionPool

    async with AsyncConnectionPool(
        settings.database_url_unpooled.get_secret_value(),
        min_size=0,
        max_size=4,
        timeout=10,
        max_idle=60,
        max_lifetime=300,
        kwargs={
            "autocommit": True,
            "prepare_threshold": None,
            "row_factory": dict_row,
            "connect_timeout": 10,
            "options": "-c search_path=" + settings.database_schema,
        },
        check=AsyncConnectionPool.check_connection,
        open=False,
    ) as pool:
        saver = AsyncPostgresSaver(pool)
        if setup:
            await saver.setup()
        yield saver
