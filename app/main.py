"""
FastAPI application entrypoint for tripplannerbackend.

New architecture: no orchestrator, no ephemeral engines. Every trip is a
persisted Cabinet (see app/db/models_furniture.py). /api/trips/* is the
entire backend contract — one endpoint per app screen.

Run locally:
    uvicorn app.main:app --reload --port 8000

Render deploys this via the start command:
    uvicorn app.main:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.trip_v2 import router as trip_router

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Africa Travel OS API",
    description="Deterministic, data-driven trip planning backend for the Africa Safari Guide app.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-Api-Key", "Content-Type"],
)

app.include_router(health_router, prefix="/api")
app.include_router(trip_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"code": "INTERNAL_ERROR", "message": "An unexpected error occurred.", "retryable": True},
    )


@app.get("/")
def root() -> dict:
    return {"service": "Africa Travel OS API", "status": "running", "docs": "/docs"}
