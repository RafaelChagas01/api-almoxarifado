from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./almoxarifado.db"
    jwt_secret: str = Field(min_length=32)
    access_token_minutes: int = Field(default=30, ge=5, le=240)
    login_attempts: int = 5
    login_window_seconds: int = 300

    @field_validator("database_url")
    @classmethod
    def use_psycopg3(cls, value: str) -> str:
        return normalize_database_url(value)


def normalize_database_url(value: str) -> str:
    # Supabase e Heroku entregam "postgres://"; o SQLAlchemy precisa do driver explicito
    for prefix in ("postgres://", "postgresql://"):
        if value.startswith(prefix):
            return "postgresql+psycopg://" + value[len(prefix) :]
    return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
