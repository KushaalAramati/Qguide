"""
Versioned, idempotent schema migrations.

The project deliberately does not take an Alembic dependency (it ships as a
single deployable and runs on SQLite locally / Postgres on Render), but "best
effort ALTER on every boot" is not a migration system either. This module is the
middle ground:

  * every change is a numbered, described step,
  * applied steps are recorded in the `schema_migrations` table,
  * steps are additive and re-runnable, so a partially migrated database heals,
  * SQL is written to work on both SQLite and PostgreSQL.

Adding a migration: append a `Migration` to `MIGRATIONS` with the next version
number. Never edit or renumber a migration that has shipped -- add a new one.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine

log = logging.getLogger("qguide.migrations")

# Errors that mean "this step was already applied" rather than "this failed".
_ALREADY_APPLIED_MARKERS = (
    "duplicate column",
    "already exists",
    "duplicate key name",
    "duplicatecolumn",
)


@dataclass
class Migration:
    version: int
    description: str
    statements: Sequence[str] = field(default_factory=tuple)
    #: Optional python callable for data backfills: fn(engine) -> None
    callable_step: Optional[Callable[[Engine], None]] = None


def _is_already_applied(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(m in msg for m in _ALREADY_APPLIED_MARKERS)


def _ensure_ledger(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version INTEGER PRIMARY KEY,"
            " description VARCHAR(255),"
            " applied_at VARCHAR(32))"
        ))


def _applied_versions(engine: Engine) -> set:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
    return {int(r[0]) for r in rows}


def run_migrations(engine: Engine) -> List[int]:
    """Apply every pending migration in order. Returns the versions applied."""
    from datetime import datetime

    _ensure_ledger(engine)
    done = _applied_versions(engine)
    applied: List[int] = []

    for m in sorted(MIGRATIONS, key=lambda x: x.version):
        if m.version in done:
            continue
        for stmt in m.statements:
            try:
                with engine.begin() as conn:
                    conn.execute(text(stmt))
            except Exception as exc:                      # noqa: BLE001
                if _is_already_applied(exc):
                    continue
                log.warning("migration %04d statement failed (%s): %s",
                            m.version, exc.__class__.__name__, stmt)
        if m.callable_step is not None:
            try:
                m.callable_step(engine)
            except Exception as exc:                      # noqa: BLE001
                log.warning("migration %04d data step failed: %s", m.version, exc)
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO schema_migrations (version, description, applied_at)"
                     " VALUES (:v, :d, :t)"),
                {"v": m.version, "d": m.description[:255],
                 "t": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")},
            )
        applied.append(m.version)
        log.info("applied migration %04d - %s", m.version, m.description)

    return applied


# --------------------------------------------------------------------------- #
# Migrations                                                                    #
# --------------------------------------------------------------------------- #
MIGRATIONS: List[Migration] = [
    Migration(
        version=1,
        description="Legacy additive columns (folders, archive, last_login)",
        statements=(
            "ALTER TABLE users ADD COLUMN last_login VARCHAR(32)",
            "ALTER TABLE users ADD COLUMN fcounter INTEGER DEFAULT 0",
            "ALTER TABLE projects ADD COLUMN folder_id VARCHAR(32)",
            "ALTER TABLE projects ADD COLUMN archived INTEGER DEFAULT 0",
        ),
    ),
    Migration(
        version=2,
        description="Role-based access control + account status + profile fields",
        statements=(
            "ALTER TABLE users ADD COLUMN role VARCHAR(32) DEFAULT 'USER'",
            "ALTER TABLE users ADD COLUMN status VARCHAR(16) DEFAULT 'active'",
            "ALTER TABLE users ADD COLUMN institution VARCHAR(255)",
            "ALTER TABLE users ADD COLUMN research_area VARCHAR(255)",
            "ALTER TABLE users ADD COLUMN terms_accepted_at VARCHAR(32)",
            "ALTER TABLE users ADD COLUMN terms_version VARCHAR(16)",
            "UPDATE users SET role = 'USER' WHERE role IS NULL",
            "UPDATE users SET status = 'active' WHERE status IS NULL",
        ),
    ),
    Migration(
        version=3,
        description="Onboarding state on the user profile",
        statements=(
            "ALTER TABLE users ADD COLUMN onboarding_completed INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN onboarding_step INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN onboarding_completed_at VARCHAR(32)",
            "UPDATE users SET onboarding_completed = 0 WHERE onboarding_completed IS NULL",
            "UPDATE users SET onboarding_step = 0 WHERE onboarding_step IS NULL",
        ),
    ),
]
