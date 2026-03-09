import uuid

import pytest
from pwdlib import PasswordHash
from sqlalchemy import select

from auth.models import User


@pytest.mark.integration
def test_create_user_creates_new_user_and_returns_tokens(client, db_session):
    username = f"user_{uuid.uuid4().hex}"
    password = "new-user-password-123"

    response = client.post(
        "/create-user",
        data={
            "username": username,
            "password": password,
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"

    stmt = select(User).where(User.username == username)
    created_user = db_session.execute(stmt).scalar_one_or_none()

    assert created_user is not None
    assert created_user.username == username
    assert created_user.pass_hash != password


@pytest.mark.integration
def test_create_user_returns_409_for_duplicate_username(client):
    username = f"user_{uuid.uuid4().hex}"
    password = "duplicate-password-123"

    first_response = client.post(
        "/create-user",
        data={
            "username": username,
            "password": password,
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/create-user",
        data={
            "username": username,
            "password": password,
        },
    )

    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "Username already in use."}


@pytest.mark.integration
def test_create_user_creates_user_and_returns_tokens(client, db_session):
    username = f"user_{uuid.uuid4().hex}"
    password = "new-user-password-123"

    response = client.post(
        "/create-user",
        data={
            "username": username,
            "password": password,
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"

    stmt = select(User).where(User.username == username)
    created_user = db_session.execute(stmt).scalar_one_or_none()

    password_hash = PasswordHash.recommended()

    assert created_user is not None
    assert created_user.username == username
    assert created_user.pass_hash != password
    assert password_hash.verify(password, created_user.pass_hash)


@pytest.mark.integration
def test_create_user_duplicate_username_returns_409_and_does_not_create_second_user(
    client,
    db_session,
):
    username = f"user_{uuid.uuid4().hex}"
    password = "duplicate-password-123"

    first_response = client.post(
        "/create-user",
        data={
            "username": username,
            "password": password,
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/create-user",
        data={
            "username": username,
            "password": password,
        },
    )

    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "Username already in use."}

    stmt = select(User).where(User.username == username)
    users = db_session.execute(stmt).scalars().all()

    assert len(users) == 1
