from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    test_database_url: str | None = Field(default=None, validation_alias="TEST_DATABASE_URL")

    model_config = SettingsConfigDict(extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()

    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set")

    return settings


def get_database_url() -> str:
    return get_settings().database_url


def get_integration_database_url() -> str:
    settings = get_settings()
    return settings.test_database_url or settings.database_url


def reset_settings_cache() -> None:
    get_settings.cache_clear()
