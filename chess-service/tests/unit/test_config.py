import pytest
from chess.config import (
    get_database_url,
    get_integration_database_url,
    reset_settings_cache,
)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.mark.unit
def test_missing_database_url_fails_fast(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
        get_database_url()


@pytest.mark.unit
def test_test_database_url_falls_back_to_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://main")
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)

    assert get_integration_database_url() == "postgresql+psycopg://main"


@pytest.mark.unit
def test_test_database_url_overrides_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://main")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+psycopg://test")

    assert get_integration_database_url() == "postgresql+psycopg://test"
