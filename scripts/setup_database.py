"""Create application and checkpoint tables. Reads credentials only from environment."""

import asyncio
import sys
from backend.app.config import Settings
from backend.app.postgres import PostgresStore, checkpointer


async def setup(settings):
    await asyncio.to_thread(PostgresStore(settings).initialize)
    async with checkpointer(settings, setup=True):
        pass


if __name__ == "__main__":
    try:
        settings = Settings()
        if not settings.database_url or not settings.database_url_unpooled:
            raise ValueError("Missing database configuration")
        kwargs = {"loop_factory": asyncio.SelectorEventLoop} if sys.platform == "win32" else {}
        asyncio.run(setup(settings), **kwargs)
        print("PostgreSQL application and LangGraph tables are ready.")
    except Exception as exc:
        print(
            "Database setup failed ("
            + type(exc).__name__
            + "). Check DATABASE_URL and DATABASE_URL_UNPOOLED.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
