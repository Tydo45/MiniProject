from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    test_database_url: str | None = Field(default=None, validation_alias="TEST_DATABASE_URL")

    # JWT
    secret_key: str = Field(default="", validation_alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", validation_alias="ALGORITHM")

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set")
    if not settings.secret_key:
        raise RuntimeError("SECRET_KEY is not set")
    return settings


def get_database_url() -> str:
    return get_settings().database_url


def get_environment_database_url() -> str:
    settings = get_settings()
    return settings.test_database_url or settings.database_url


def reset_settings_cache() -> None:
    get_settings.cache_clear()
