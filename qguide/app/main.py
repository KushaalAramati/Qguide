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
from qguide.app.research import router as research_router

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
    """Fail fast on configuration that would be outright dangerous in production
    (a public dev signing key, or reset tokens surfaced in API responses); warn
    loudly about the rest so a first deployment cannot take the service down."""
    fatal, warn = [], []
    if auth.JWT_SECRET == auth.DEV_JWT_SECRET:
        fatal.append("JWT_SECRET is unset (using the insecure development key)")
    elif len(auth.JWT_SECRET) < 32:
        warn.append("JWT_SECRET is shorter than 32 characters")
    if os.environ.get("QGUIDE_DEV_EMAIL") == "1":
        fatal.append("QGUIDE_DEV_EMAIL=1 would expose password-reset tokens")
    if "*" in _origins:
        warn.append("ALLOWED_ORIGINS is '*' (set your web origin explicitly)")
    if not os.environ.get("ADMIN_EMAILS", "").strip():
        warn.append("ADMIN_EMAILS is empty (no account will be promoted to admin)")
    if not os.environ.get("SMTP_HOST"):
        warn.append("no SMTP_HOST: password-reset and invitation emails go to the log only")
    prod = _is_production()
    if fatal:
        message = "Unsafe production configuration: " + "; ".join(fatal) + "."
        if prod:
            raise RuntimeError(message)
        log.warning("[dev] %s", message)
    for w in warn:
        log.warning("[%s] configuration: %s", "production" if prod else "dev", w)


@app.on_event("startup")
def _startup():
    _check_production_config()
    store.init_db()
    promoted = store.ensure_bootstrap_admins()
    if promoted:
        log.info("promoted bootstrap administrators: %s", ", ".join(promoted))


app.include_router(router)
app.include_router(research_router)


@app.get("/")
def root():
    return {
        "service": BRANDING.app_name,
        "description": BRANDING.app_description,
        "docs": "/docs",
        "endpoints": ["/health", "/branding", "/legal", "/enzymes", "/design",
                      "/sensitivity", "/assumptions"],
    }
