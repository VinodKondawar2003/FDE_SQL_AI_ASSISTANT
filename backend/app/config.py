from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    google_api_key: str = ""
    model_name: str = ""
    model_provider: str = "google_genai"
    public_origin: str = "http://localhost:8000"
    secure_cookies: bool = False
    state_dir: Path = Path(".runtime")
    sample_db: Path = Path("data/sample.db")
    frontend_dir: Path = Path("frontend/dist")
    daily_model_calls: int = 500
    query_timeout: float = 2.0
    turn_timeout: float = 45.0
    session_rate: int = 10
    execution_rate: int = 30
    ip_rate: int = 30
    global_concurrency: int = 4

    @property
    def model_ready(self) -> bool:
        return bool(self.google_api_key and self.model_name and self.model_provider == "google_genai")
