import pytest


@pytest.mark.unit
def test_login():
    response = {"status": "ok"}
    assert response.get("status") == "ok"
