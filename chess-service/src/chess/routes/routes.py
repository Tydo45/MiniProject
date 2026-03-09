import os

from dotenv import load_dotenv
from fastapi import APIRouter
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
