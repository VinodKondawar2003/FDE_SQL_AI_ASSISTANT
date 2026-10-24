"""Local server with the event loop required by psycopg on Windows."""

import asyncio
import sys

import uvicorn


def main():
    config = uvicorn.Config("backend.app.main:app", host="127.0.0.1", port=8000, proxy_headers=False)
    kwargs = {"loop_factory": asyncio.SelectorEventLoop} if sys.platform == "win32" else {}
    asyncio.run(uvicorn.Server(config).serve(), **kwargs)


if __name__ == "__main__":
    main()
