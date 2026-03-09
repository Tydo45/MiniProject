from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from pydantic import BaseModel
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth.config import Settings, get_settings
from auth.db import get_db
from auth.models import User

router = APIRouter()
password_hash = PasswordHash.recommended()


class RefreshTokenRequest(BaseModel):
    refresh_token: str


def _create_jwt_token(
    *,
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    secret_key: str,
    algorithm: str,
) -> str:
    return jwt.encode(
        {
            "sub": subject,
            "typ": token_type,
            "exp": datetime.now(UTC) + expires_delta,
        },
        secret_key,
        algorithm=algorithm,
    )


def _create_token_pair(subject: str, settings: Settings) -> tuple[str, str]:
    access_token = _create_jwt_token(
        subject=subject,
        token_type="access",
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        secret_key=settings.secret_key,
        algorithm=settings.algorithm,
    )
    refresh_token = _create_jwt_token(
        subject=subject,
        token_type="refresh",
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
        secret_key=settings.secret_key,
        algorithm=settings.algorithm,
    )
    return access_token, refresh_token


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    settings = get_settings()

    stmt = select(User).where(User.username == form_data.username)
    user = db.execute(stmt).scalar_one_or_none()

    if user is None or not password_hash.verify(form_data.password, user.pass_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token, refresh_token = _create_token_pair(str(user.id), settings)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/create-user")
async def create_user(
    form_data: OAuth2PasswordRequestForm = Depends(),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> dict[str, str]:
    settings = get_settings()

    try:
        insert_stmt = (
            insert(User)
            .values(
                username=form_data.username,
                pass_hash=password_hash.hash(form_data.password),
            )
            .returning(User.id)
        )
        user_id = db.execute(insert_stmt).scalar_one()
        db.commit()
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already in use.") from err

    access_token, refresh_token = _create_token_pair(str(user_id), settings)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh")
def refresh(request: RefreshTokenRequest) -> dict[str, str]:
    settings = get_settings()

    try:
        payload = jwt.decode(
            request.refresh_token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except jwt.PyJWTError as err:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from err

    subject = payload.get("sub")
    token_type = payload.get("typ")
    if not subject or token_type != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token, refresh_token = _create_token_pair(str(subject), settings)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
