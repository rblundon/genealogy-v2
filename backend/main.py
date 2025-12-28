"""FastAPI application entry point."""

import logging
import sys
import json
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from models.database import engine, Base, get_db, SessionLocal
from api.endpoints import gramps, obituaries, resolution, persons


# Configure structured JSON logging
class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def setup_logging():
    """Configure structured JSON logging to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# Setup logging before app initialization
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Genealogy Research Tool API")

    # Initialize database tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Genealogy Research Tool API")


app = FastAPI(
    title="Genealogy Research Tool API",
    description="API for extracting genealogical data from obituaries",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative frontend port
        "http://scrim.local.mk-labs.cloud:5173",  # Remote dev access
        "http://scrim.local.mk-labs.cloud:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(gramps.router)
app.include_router(obituaries.router)
app.include_router(resolution.router)
app.include_router(persons.router)


@app.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint for container orchestration.

    Returns basic health status without checking dependencies.
    Use /ready for full readiness check including database.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "genealogy-backend",
    }


@app.get("/ready")
async def readiness_check() -> dict:
    """
    Readiness check endpoint that verifies database connectivity.

    Use this endpoint to determine if the service is ready to accept requests.
    """
    db_status = "connected"
    db_error = None

    try:
        # Test database connection
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        db_status = "disconnected"
        db_error = str(e)
        logger.error(f"Database connection failed: {e}")

    status = "ready" if db_status == "connected" else "not_ready"

    response = {
        "status": status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "database": db_status,
    }

    if db_error:
        response["database_error"] = db_error

    return response


@app.get("/")
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "message": "Genealogy Research Tool API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
        "gramps_status": "/api/gramps/status",
        "obituaries_process": "/api/obituaries/process",
        "obituaries_facts": "/api/obituaries/facts/{obituary_id}",
    }
