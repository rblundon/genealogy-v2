"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Genealogy Research Tool API",
    description="API for extracting genealogical data from obituaries",
    version="1.0.0",
)

# CORS configuration for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint for container orchestration."""
    return {"status": "healthy"}


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {"message": "Genealogy Research Tool API", "docs": "/docs"}
