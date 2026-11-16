from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CheckStock"
    database_url: str = (
        "postgresql+psycopg://checkstock:checkstock@localhost:5432/checkstock"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
