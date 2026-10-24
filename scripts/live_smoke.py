"""Small real-provider smoke test. Never prints credentials."""

import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from backend.app.config import Settings
from backend.app.main import create_app


def main():
    with tempfile.TemporaryDirectory() as directory:
        settings = Settings(state_dir=Path(directory), session_rate=100, ip_rate=100)
        with TestClient(create_app(settings), base_url=settings.public_origin) as client:
            client.headers["origin"] = settings.public_origin
            session = client.post("/api/v1/session")
            client.headers["x-csrf-token"] = session.json()["csrf_token"]
            cid = client.post("/api/v1/conversations", json={}).json()["id"]
            for text in [
                "Show customer_id and first_name for all customers.",
                "Only those from California.",
                "Who won the FIFA World Cup?",
                "Employees hired after January 2024",
            ]:
                result = client.post(
                    f"/api/v1/conversations/{cid}/messages",
                    json={"request_id": str(uuid4()), "message": text},
                )
                body = result.json()
                print(
                    {
                        "question": text,
                        "http_status": result.status_code,
                        "status": body.get("status"),
                        "error": body.get("error"),
                    },
                    flush=True,
                )
                if body.get("sql"):
                    aid = body["sql"]["artifact_id"]
                    executed = client.post(
                        f"/api/v1/queries/{aid}/execute", json={"request_id": str(uuid4())}
                    )
                    print(
                        {
                            "execution": executed.status_code,
                            "rows": executed.json().get("returned_row_count"),
                            "sql": body["sql"]["text"],
                        },
                        flush=True,
                    )


if __name__ == "__main__":
    main()
