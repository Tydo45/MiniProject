from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from auth.config import get_database_url

database_url = get_database_url()

engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass
