"""Resolution workflow API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from sqlalchemy.orm import Session

from models.database import get_db
from services.resolution_service import ResolutionService
from services.commit_service import CommitService

router = APIRouter(prefix="/api/resolution", tags=["resolution"])


# Request/Response Models

class PersonResolutionUpdate(BaseModel):
    """Request to update a person resolution."""
    status: Optional[str] = None  # pending, matched, create_new, rejected
    gramps_handle: Optional[str] = None
    modified_first_name: Optional[str] = None
    modified_surname: Optional[str] = None
    modified_gender: Optional[int] = None


class FactResolutionUpdate(BaseModel):
    """Request to update a fact resolution."""
    action: Optional[str] = None  # add, update, skip, reject
    status: Optional[str] = None  # pending, approved, rejected
    modified_value: Optional[str] = None


class ResolutionSummary(BaseModel):
    """Summary of resolution status."""
    obituary_id: int
    persons: dict
    facts: dict


class CommitResult(BaseModel):
    """Result of committing to Gramps."""
    batch_id: int
    status: str
    persons_created: int
    families_created: int
    facts_committed: int
    error_message: Optional[str] = None


# Endpoints

@router.post("/{obituary_id}/resolve")
async def resolve_obituary(
    obituary_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Resolve all extracted facts for an obituary against Gramps.

    This matches persons to existing Gramps records and prepares
    facts for approval before committing.
    """
    service = ResolutionService(db)
    result = await service.resolve_obituary(obituary_id)
    return result


@router.get("/{obituary_id}")
async def get_resolution_status(
    obituary_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Get the current resolution status for an obituary.

    Returns all person and fact resolutions with their current status.
    """
    service = ResolutionService(db)
    return service.get_resolution_status(obituary_id)


@router.put("/person/{resolution_id}")
async def update_person_resolution(
    resolution_id: int,
    update: PersonResolutionUpdate,
    db: Session = Depends(get_db),
) -> dict:
    """
    Update a person resolution (user action).

    Allows matching to a different Gramps record, creating new,
    or modifying the name to be created.
    """
    service = ResolutionService(db)
    try:
        resolution = service.update_person_resolution(
            resolution_id=resolution_id,
            status=update.status,
            gramps_handle=update.gramps_handle,
            modified_first_name=update.modified_first_name,
            modified_surname=update.modified_surname,
            modified_gender=update.modified_gender,
        )
        return resolution.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/fact/{resolution_id}")
async def update_fact_resolution(
    resolution_id: int,
    update: FactResolutionUpdate,
    db: Session = Depends(get_db),
) -> dict:
    """
    Update a fact resolution (user action).

    Allows approving, rejecting, or modifying the value to be committed.
    """
    service = ResolutionService(db)
    try:
        resolution = service.update_fact_resolution(
            resolution_id=resolution_id,
            action=update.action,
            status=update.status,
            modified_value=update.modified_value,
        )
        return resolution.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{obituary_id}/approve-all")
async def approve_all_facts(
    obituary_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Approve all pending fact resolutions for an obituary.

    This is a convenience endpoint to quickly approve all facts
    before committing.
    """
    service = ResolutionService(db)
    count = service.approve_all_pending(obituary_id)
    return {
        "obituary_id": obituary_id,
        "facts_approved": count,
    }


@router.post("/{obituary_id}/commit")
async def commit_to_gramps(
    obituary_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Commit all approved resolutions to Gramps Web.

    This creates new persons, families, and events in Gramps
    based on the approved resolutions.
    """
    service = CommitService(db)
    batch = await service.commit_obituary(obituary_id)

    return {
        "batch_id": batch.id,
        "status": batch.status,
        "persons_created": batch.persons_created,
        "persons_updated": batch.persons_updated,
        "families_created": batch.families_created,
        "events_created": batch.events_created,
        "facts_committed": batch.facts_committed,
        "error_message": batch.error_message,
    }


@router.get("/{obituary_id}/commit-status")
async def get_commit_status(
    obituary_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """
    Get the status of the latest commit batch for an obituary.
    """
    service = CommitService(db)
    status = service.get_commit_status(obituary_id)

    if not status:
        raise HTTPException(
            status_code=404,
            detail=f"No commit batch found for obituary {obituary_id}"
        )

    return status
