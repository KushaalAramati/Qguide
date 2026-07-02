"""
Database engine/session for Q-Guide (SQLAlchemy 2.x).

Driven by the DATABASE_URL env var:
  * unset / local  -> SQLite file `qguide_data.db`
  * Render Postgres -> `postgres://...` (normalised to `postgresql://` for SQLAlchemy)

This single switch lets the same code run on SQLite locally and managed Postgres
in production with no changes.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///qguide_data.db")
# Render/Heroku hand out `postgres://`; SQLAlchemy needs `postgresql://`.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_is_sqlite = DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True,
                       future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False,
                            future=True)
Base = declarative_base()


@contextmanager
def session_scope():
    """Transactional session: commit on success, rollback on error, always close."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
