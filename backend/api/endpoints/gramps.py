"""Gramps Web API endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from services.gramps_connector import GrampsConnector, get_gramps_connector

router = APIRouter(prefix="/api/gramps", tags=["gramps"])


class GrampsStatusResponse(BaseModel):
    """Response model for Gramps Web status check."""

    connected: bool
    url: str
    error: Optional[str] = None
    api_version: Optional[str] = None
    tree_name: Optional[str] = None
    database_id: Optional[str] = None
    locale: Optional[dict] = None
    people_count: Optional[int] = None


@router.get("/status", response_model=GrampsStatusResponse)
async def check_gramps_status(
    connector: GrampsConnector = Depends(get_gramps_connector),
) -> GrampsStatusResponse:
    """
    Check Gramps Web connectivity and return status.

    Returns connection status, API version, tree name, and people count
    if connected successfully.
    """
    status = await connector.check_connection()

    response = GrampsStatusResponse(
        connected=status.connected,
        url=status.url,
        error=status.error,
        api_version=status.api_version,
        tree_name=status.tree_name,
        database_id=status.database_id,
        locale=status.locale,
    )

    # If connected, also get people count
    if status.connected:
        response.people_count = await connector.get_people_count()

    return response
