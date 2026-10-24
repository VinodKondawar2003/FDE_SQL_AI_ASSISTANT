"""Browser-test harness only. No runtime flag enables this adapter."""

import tempfile
from pathlib import Path
import uvicorn
from backend.app.config import Settings
from backend.app.main import create_app
from backend.tests.fakes import ScriptedModel
from data.seed import seed

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        seed(root / "sample.db")
        settings = Settings(
            _env_file=None,
            state_dir=root / "state",
            sample_db=root / "sample.db",
            google_api_key="test-only-not-a-real-key",
            model_name="scripted-test-adapter",
            public_origin="http://127.0.0.1:8001",
            session_rate=100,
            ip_rate=200,
        )
        uvicorn.run(create_app(settings, ScriptedModel), host="127.0.0.1", port=8001, log_level="warning")
