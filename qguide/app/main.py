"""
FastAPI application entrypoint.

Run with:
    uvicorn qguide.app.main:app --reload
Then open http://127.0.0.1:8000/docs for the interactive API.

Product identity (name, description, support address) comes from
`qguide.app.branding` -- do not hardcode it here.
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from qguide.app import auth, store
from qguide.app.branding import BRANDING
from qguide.app.routes import router

log = logging.getLogger("qguide")

app = FastAPI(
    title=BRANDING.app_name,
    version="1.0",
    description=BRANDING.app_description,
)

# CORS: allow the frontend's origin(s). Defaults to "*" for local dev; in
# production set ALLOWED_ORIGINS to the deployed web URL(s), comma-separated.
_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,          # bearer tokens, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
)


def _is_production() -> bool:
    """Production is anything not obviously local: an explicit ENVIRONMENT flag,
    or a non-SQLite database."""
    env = (os.environ.get("ENVIRONMENT") or os.environ.get("ENV") or "").lower()
    if env in ("prod", "production"):
        return True
    if env in ("dev", "development", "local", "test"):
        return False
    return not os.environ.get("DATABASE_URL", "sqlite:///").startswith("sqlite")


def _check_production_config() -> None:
    """Fail fast on configuration that would be unsafe in production."""
    problems = []
    if auth.JWT_SECRET == auth.DEV_JWT_SECRET:
        problems.append("JWT_SECRET is unset (using the insecure development key)")
    if len(auth.JWT_SECRET) < 32:
        problems.append("JWT_SECRET is shorter than 32 characters")
    if "*" in _origins:
        problems.append("ALLOWED_ORIGINS is '*' (set your web origin explicitly)")
    if os.environ.get("QGUIDE_DEV_EMAIL") == "1":
        problems.append("QGUIDE_DEV_EMAIL=1 would expose password-reset tokens")
    if not problems:
        return
    message = ("Unsafe production configuration: " + "; ".join(problems) + ".")
    if _is_production():
        raise RuntimeError(message)
    log.warning("[dev] %s", message)


@app.on_event("startup")
def _startup():
    _check_production_config()
    store.init_db()
    promoted = store.ensure_bootstrap_admins()
    if promoted:
        log.info("promoted bootstrap administrators: %s", ", ".join(promoted))


app.include_router(router)


@app.get("/")
def root():
    return {
        "service": BRANDING.app_name,
        "description": BRANDING.app_description,
        "docs": "/docs",
        "endpoints": ["/health", "/branding", "/legal", "/enzymes", "/design",
                      "/sensitivity", "/assumptions"],
    }
