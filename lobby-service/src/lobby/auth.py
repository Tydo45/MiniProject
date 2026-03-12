import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lobby.config import get_settings

security = HTTPBearer()


def decode_user_id_from_token(token: str) -> uuid.UUID:
    """
    Decode a JWT and extract the authenticated user's UUID from the `sub` claim.

    Args:
        token: Encoded JWT bearer token.

    Returns:
        uuid.UUID: Authenticated user ID from the token subject.

    Raises:
        HTTPException: If the token is expired, invalid, missing a subject,
        or contains a non-UUID subject.
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except jwt.ExpiredSignatureError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from err
    except jwt.InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from err

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    try:
        return uuid.UUID(subject)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject is not a valid UUID",
        ) from err


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> uuid.UUID:
    """
    Extract and validate the authenticated user's UUID from a bearer token.

    Args:
        credentials: Bearer token credentials provided by FastAPI security.

    Returns:
        uuid.UUID: Authenticated user ID.
    """
    return decode_user_id_from_token(credentials.credentials)
