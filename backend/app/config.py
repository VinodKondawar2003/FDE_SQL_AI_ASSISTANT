from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    google_api_key: str = ""
    model_name: str = ""
    model_provider: str = "google_genai"
    public_origin: str = ""
    database_url: SecretStr = SecretStr("")
    database_url_unpooled: SecretStr = SecretStr("")
    database_schema: str = Field(default="querycraft", pattern=r"^[a-z][a-z0-9_]{0,62}$")
    vercel: bool = False
    vercel_url: str = ""
    vercel_project_production_url: str = ""
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

    @model_validator(mode="after")
    def deployment_settings(self):
        if self.database_url and not self.database_url_unpooled:
            raise ValueError(
                "DATABASE_URL_UNPOOLED is required with DATABASE_URL for persistent checkpoints and locks."
            )
        if self.vercel:
            if not self.database_url:
                raise ValueError(
                    "Vercel requires DATABASE_URL and DATABASE_URL_UNPOOLED; local storage is not persistent."
                )
            self.secure_cookies = True
        return self

    @property
    def allowed_origins(self):
        origins = {self.public_origin.rstrip("/")} if self.public_origin else set()
        if self.vercel:
            for hostname in (self.vercel_url, self.vercel_project_production_url):
                if hostname:
                    origins.add("https://" + hostname)
        elif not origins:
            origins.add("http://localhost:8000")
        return origins
