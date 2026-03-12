import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import lobby.auth as auth_module


@pytest.fixture
def fake_settings():
    return SimpleNamespace(
        secret_key="6bWlSEJiktuKfgeeo4bd9CfgjhlNKj4HvI+GCy0QUjs=", # FAKE SECRET NOT PROD
        algorithm="HS256",
    )


@pytest.fixture
def user_id():
    return uuid.uuid4()


@pytest.fixture
def patch_settings(monkeypatch, fake_settings):
    monkeypatch.setattr(auth_module, "get_settings", lambda: fake_settings)


def make_token(
    *,
    secret_key: str,
    algorithm: str,
    sub: str | None = None,
    exp: datetime | None = None,
) -> str:
    payload = {}
    if sub is not None:
        payload["sub"] = sub
    if exp is not None:
        payload["exp"] = exp

    return jwt.encode(payload, secret_key, algorithm=algorithm)


@pytest.mark.unit
def test_decode_user_id_from_token_returns_uuid_for_valid_token(
    patch_settings,
    fake_settings,
    user_id,
):
    token = make_token(
        secret_key=fake_settings.secret_key,
        algorithm=fake_settings.algorithm,
        sub=str(user_id),
        exp=datetime.now(UTC) + timedelta(minutes=5),
    )

    result = auth_module.decode_user_id_from_token(token)

    assert result == user_id


@pytest.mark.unit
def test_decode_user_id_from_token_raises_401_for_expired_token(
    patch_settings,
    fake_settings,
    user_id,
):
    token = make_token(
        secret_key=fake_settings.secret_key,
        algorithm=fake_settings.algorithm,
        sub=str(user_id),
        exp=datetime.now(UTC) - timedelta(minutes=5),
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_module.decode_user_id_from_token(token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Token expired"


@pytest.mark.unit
def test_decode_user_id_from_token_raises_401_for_invalid_token(
    patch_settings,
):
    with pytest.raises(HTTPException) as exc_info:
        auth_module.decode_user_id_from_token("not-a-real-token")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


@pytest.mark.unit
def test_decode_user_id_from_token_raises_401_when_subject_missing(
    patch_settings,
    fake_settings,
):
    token = make_token(
        secret_key=fake_settings.secret_key,
        algorithm=fake_settings.algorithm,
        exp=datetime.now(UTC) + timedelta(minutes=5),
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_module.decode_user_id_from_token(token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Token missing subject"


@pytest.mark.unit
def test_decode_user_id_from_token_raises_401_when_subject_empty(
    patch_settings,
    fake_settings,
):
    token = make_token(
        secret_key=fake_settings.secret_key,
        algorithm=fake_settings.algorithm,
        sub="",
        exp=datetime.now(UTC) + timedelta(minutes=5),
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_module.decode_user_id_from_token(token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Token missing subject"


@pytest.mark.unit
def test_decode_user_id_from_token_raises_401_when_subject_is_not_uuid(
    patch_settings,
    fake_settings,
):
    token = make_token(
        secret_key=fake_settings.secret_key,
        algorithm=fake_settings.algorithm,
        sub="definitely-not-a-uuid",
        exp=datetime.now(UTC) + timedelta(minutes=5),
    )

    with pytest.raises(HTTPException) as exc_info:
        auth_module.decode_user_id_from_token(token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Token subject is not a valid UUID"


@pytest.mark.unit
def test_get_current_user_id_returns_uuid_from_credentials(monkeypatch, user_id):
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="some-token",
    )

    monkeypatch.setattr(
        auth_module,
        "decode_user_id_from_token",
        lambda token: user_id,
    )

    result = auth_module.get_current_user_id(credentials)

    assert result == user_id


@pytest.mark.unit
def test_get_current_user_id_passes_credentials_token(monkeypatch, user_id):
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="expected-token",
    )

    captured = {}

    def fake_decode(token: str) -> uuid.UUID:
        captured["token"] = token
        return user_id

    monkeypatch.setattr(auth_module, "decode_user_id_from_token", fake_decode)

    result = auth_module.get_current_user_id(credentials)

    assert result == user_id
    assert captured["token"] == "expected-token"