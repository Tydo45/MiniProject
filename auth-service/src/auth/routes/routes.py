from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class User(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(user: User) -> dict[str, str]:
    # TODO:
    # - Enforce Username uniqueness
    # - Generate Password Hash
    # - Put new user in users table {username,passHash}
    # - Return JWT

    return {"JWT": "TOKEN", "Username": user.username}


@router.post("/login")
def login(user: User) -> dict[str, str]:
    # TODO:
    # - Check Username / Password against stored hash
    # - Return JWT

    return {"JWT": "TOKEN", "Username": user.username}


@router.post("/refresh")
def refresh() -> dict[str, str]:
    # TODO:
    # - Refresh JWT
    # - Return JWT

    return {"JWT": "TOKEN"}
