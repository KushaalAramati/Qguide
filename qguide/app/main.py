"""
Q-Guide FastAPI application entrypoint.

Run with:
    uvicorn qguide.app.main:app --reload
Then open http://127.0.0.1:8000/docs for the interactive API.
"""
from __future__ import annotations

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

# Open CORS so a future React frontend (different origin) can call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "service": "Q-Guide",
        "docs": "/docs",
        "endpoints": ["/health", "/enzymes", "/design", "/sensitivity", "/assumptions"],
    }
