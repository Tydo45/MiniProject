import os

from dotenv import load_dotenv
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

database_url = os.getenv("DATABASE_URL")

if database_url is None:
    raise RuntimeError("DATABASE_URL is not set")

router = APIRouter()

engine = create_engine(database_url, echo=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


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
