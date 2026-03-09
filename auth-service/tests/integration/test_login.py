import uuid

import pytest


@pytest.mark.integration
def test_login_returns_tokens_for_valid_credentials(client):
    username = f"user_{uuid.uuid4().hex}"
    password = "test-password-123"

    create_response = client.post(
        "/create-user",
        data={
            "username": username,
            "password": password,
        },
    )
    assert create_response.status_code == 200

    login_response = client.post(
        "/token",
        data={
            "username": username,
            "password": password,
        },
    )

    assert login_response.status_code == 200
    body = login_response.json()

    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.integration
def test_login_returns_401_for_wrong_password(client):
    username = f"user_{uuid.uuid4().hex}"
    password = "correct-password-123"

    create_response = client.post(
        "/create-user",
        data={
            "username": username,
            "password": password,
        },
    )
    assert create_response.status_code == 200

    login_response = client.post(
        "/token",
        data={
            "username": username,
            "password": "wrong-password-123",
        },
    )

    assert login_response.status_code == 401
    assert login_response.json() == {"detail": "Invalid credentials"}


@pytest.mark.integration
def test_login_returns_401_for_nonexistent_user(client):
    login_response = client.post(
        "/token",
        data={
            "username": f"missing_{uuid.uuid4().hex}",
            "password": "any-password",
        },
    )

    assert login_response.status_code == 401
    assert login_response.json() == {"detail": "Invalid credentials"}
