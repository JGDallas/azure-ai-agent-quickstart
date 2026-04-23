"""FastAPI entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .persistence import init as init_db
from .routers import budget, chat, evaluations, runs, traces
from .telemetry import init_app_insights

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_app_insights()
    yield


app = FastAPI(
    title="Azure AI Agent Quickstart API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS wide open — this demo runs on localhost only and the UI
# lives on a different port than the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> dict[str, object]:
    return {
        "status": "ok",
        "features": settings.flags,
        "deployment": settings.azure_openai_deployment,
    }


app.include_router(chat.router, tags=["chat"])
app.include_router(runs.router, tags=["runs"])
app.include_router(budget.router, tags=["budget"])
app.include_router(evaluations.router, tags=["evaluations"])
app.include_router(traces.router, tags=["traces"])
