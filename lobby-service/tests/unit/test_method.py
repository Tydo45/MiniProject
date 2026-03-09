import pytest

from lobby.routes.routes import health


@pytest.mark.unit
def test_health():
    response = health()
    assert response.get("status") == "ok"
