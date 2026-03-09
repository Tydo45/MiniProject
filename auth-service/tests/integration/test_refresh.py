import uuid

import jwt
import pytest

from auth.config import get_settings


@pytest.mark.integration
def test_refresh_returns_new_tokens_for_valid_refresh_token(client):
    username = f"user_{uuid.uuid4().hex}"
    password = "refresh-password-123"

    create_response = client.post(
        "/create-user",
        data={
            "username": username,
            "password": password,
        },
    )
    assert create_response.status_code == 200

    original_refresh_token = create_response.json()["refresh_token"]

    refresh_response = client.post(
        "/refresh",
        json={"refresh_token": original_refresh_token},
    )

    assert refresh_response.status_code == 200
    body = refresh_response.json()

    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"

    assert body["access_token"] != ""
    assert body["refresh_token"] != ""


@pytest.mark.integration
def test_refresh_returns_401_for_invalid_token(client):
    response = client.post(
        "/refresh",
        json={"refresh_token": "not-a-valid-jwt"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh token"}


@pytest.mark.integration
def test_refresh_returns_401_when_sub_missing(client):
    settings = get_settings()
    token = jwt.encode(
        {"typ": "refresh"},
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    response = client.post(
        "/refresh",
        json={"refresh_token": token},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh token"}


@pytest.mark.integration
def test_refresh_returns_401_when_token_type_is_not_refresh(client):
    settings = get_settings()
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "typ": "access"},
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    response = client.post(
        "/refresh",
        json={"refresh_token": token},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid refresh token"}
