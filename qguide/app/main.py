"""
Q-Guide FastAPI application entrypoint.

Run with:
    uvicorn qguide.app.main:app --reload
Then open http://127.0.0.1:8000/docs for the interactive API.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from qguide.app.routes import router

app = FastAPI(
    title="Q-Guide",
    version="1.0",
    description=(
        "Context-aware, explainable, quantum-assisted guide RNA recommendation "
        "platform. Optimises for predicted biological outcome, not just cutting."
    ),
)

# CORS: allow the React frontend's origin(s). Defaults to "*" for local dev;
# in production set ALLOWED_ORIGINS to the Vercel URL(s), comma-separated.
_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

from qguide.app import store


@app.on_event("startup")
def _startup():
    store.init_db()


app.include_router(router)


@app.get("/")
def root():
    return {
        "service": "Q-Guide",
        "docs": "/docs",
        "endpoints": ["/health", "/enzymes", "/design", "/sensitivity", "/assumptions"],
    }
