"""Small real-provider smoke test. Never prints credentials."""

import asyncio
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from backend.app.config import Settings
from backend.app.main import create_app


def main():
    with tempfile.TemporaryDirectory() as directory:
        settings = Settings(state_dir=Path(directory), session_rate=100, ip_rate=100)
        origin = settings.public_origin or "http://localhost:8000"
        options = {"loop_factory": asyncio.SelectorEventLoop} if sys.platform == "win32" else {}
        with TestClient(create_app(settings), base_url=origin, backend_options=options) as client:
            client.headers["origin"] = origin
            session = client.post("/api/v1/session")
            assert session.status_code in (200, 201), session.status_code
            client.headers["x-csrf-token"] = session.json()["csrf_token"]
            created = client.post("/api/v1/conversations", json={})
            assert created.status_code == 201, created.status_code
            cid = created.json()["id"]
            try:
                for question, expected, rows in [
                    ("Show customer_id and first_name for all customers.", "completed", 80),
                    ("Only those from California.", "completed", 40),
                    ("Who won the FIFA World Cup?", "refused", None),
                    ("Employees hired after January 2024", "clarification_required", None),
                ]:
                    result = client.post(
                        f"/api/v1/conversations/{cid}/messages",
                        json={"request_id": str(uuid4()), "message": question},
                    )
                    body = result.json()
                    print(
                        {
                            "question": question,
                            "http_status": result.status_code,
                            "status": body.get("status"),
                        },
                        flush=True,
                    )
                    assert result.status_code == 200, result.status_code
                    assert body.get("status") == expected, body.get("status")
                    if rows is not None:
                        aid = body["sql"]["artifact_id"]
                        executed = client.post(
                            f"/api/v1/queries/{aid}/execute", json={"request_id": str(uuid4())}
                        )
                        assert executed.status_code == 200, executed.status_code
                        count = executed.json().get("returned_row_count")
                        print({"execution": executed.status_code, "rows": count}, flush=True)
                        assert count == rows, count
            finally:
                assert client.delete(f"/api/v1/conversations/{cid}").status_code == 204
    print("Live smoke passed.")


if __name__ == "__main__":
    main()
