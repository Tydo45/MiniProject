import pytest
from fastapi.testclient import TestClient

from lobby.main import app

client = TestClient(app)


@pytest.mark.integration
def test_health(db_session):
    response = client.get("/health")

    print(db_session)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
