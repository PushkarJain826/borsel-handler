"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from borsel.api.demo import router as demo_router
from borsel.db.session import dispose_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle."""
    # Startup: nothing extra needed — engine is created at import time.
    yield
    # Shutdown: release all database connections.
    await dispose_engine()


app = FastAPI(
    title="Borsel Handler",
    description="Financial data collection and management platform.",
    version="0.1.0",
    lifespan=lifespan,
)

# Register API routers
app.include_router(demo_router)


@app.get("/health")
async def health() -> dict:
    """Basic liveness check, independent of external services."""
    return {"status": "ok"}
