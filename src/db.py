from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base
from .utils import DATA_DIR, DB_PATH

DATA_DIR.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Session:
    init_db()
    return SessionLocal()
