# FILE: backend/api/endpoints/persons.py
# API endpoints for person management and Gramps sync
# ============================================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Optional
from pydantic import BaseModel
import logging
import urllib.parse

from models import get_db
from services.person_sync_service import (
    PersonSyncService,
    get_person_sync_service,
    PersonSummary,
    PersonDetail,
    GrampsMatch,
    SyncResult
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/persons", tags=["persons"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SyncPersonRequest(BaseModel):
    """Request model for syncing a person to Gramps."""
    gramps_handle: Optional[str] = None
    create_new: bool = False
    include_relationships: bool = True


class PersonSummaryResponse(BaseModel):
    """Response model for a person summary."""
    id: int
    name: str
    name_formatted: str
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    primary_role: str
    obituary_count: int
    fact_count: int
    resolved_count: int
    unresolved_count: int
    gramps_handle: Optional[str] = None
    sync_status: str


class GrampsMatchResponse(BaseModel):
    """Response model for a Gramps match candidate."""
    handle: str
    gramps_id: str
    name: str
    first_name: str
    surname: str
    score: float
    match_details: dict


class SyncResultResponse(BaseModel):
    """Response model for sync operation result."""
    success: bool
    person_name: str
    gramps_handle: Optional[str] = None
    gramps_id: Optional[str] = None
    action: str
    error: Optional[str] = None
    events_created: int
    families_created: int


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/")
async def list_persons(
    db: Session = Depends(get_db)
) -> Dict:
    """
    List all unique persons across all obituaries.
    Sorted alphabetically by last name.
    """
    service = get_person_sync_service(db)
    persons = service.get_all_persons()

    return {
        'count': len(persons),
        'persons': [
            {
                'id': p.id,
                'name': p.name,
                'name_formatted': p.name_formatted,
                'first_name': p.first_name,
                'middle_name': p.middle_name,
                'last_name': p.last_name,
                'primary_role': p.primary_role,
                'obituary_count': p.obituary_count,
                'fact_count': p.fact_count,
                'resolved_count': p.resolved_count,
                'unresolved_count': p.unresolved_count,
                'gramps_handle': p.gramps_handle,
                'gramps_id': p.gramps_id,
                'sync_status': p.sync_status,
            }
            for p in persons
        ]
    }


@router.get("/by-name/gramps-matches")
async def get_gramps_matches(
    name: str,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Get potential Gramps matches for a person.
    Uses fuzzy matching to find candidates.
    Name passed as query parameter.
    """
    service = get_person_sync_service(db)
    matches = await service.get_gramps_matches(name)

    return {
        'person_name': name,
        'matches': [
            {
                'handle': m.handle,
                'gramps_id': m.gramps_id,
                'name': m.name,
                'first_name': m.first_name,
                'surname': m.surname,
                'score': m.score,
                'match_details': m.match_details
            }
            for m in matches
        ]
    }


@router.post("/by-name/sync")
async def sync_person(
    name: str,
    request: SyncPersonRequest,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Sync a person to Gramps.
    Name passed as query parameter.

    Options:
    - gramps_handle: Link to an existing Gramps person by handle
    - create_new: Create a new Gramps person
    - include_relationships: Also create family relationships
    """
    if not request.gramps_handle and not request.create_new:
        raise HTTPException(
            status_code=400,
            detail="Must provide gramps_handle or set create_new=true"
        )

    service = get_person_sync_service(db)
    result = await service.sync_person_to_gramps(
        name=name,
        gramps_handle=request.gramps_handle,
        create_new=request.create_new,
        include_relationships=request.include_relationships
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return {
        'success': result.success,
        'person_name': result.person_name,
        'gramps_handle': result.gramps_handle,
        'gramps_id': result.gramps_id,
        'action': result.action,
        'events_created': result.events_created,
        'families_created': result.families_created
    }


@router.post("/by-name/skip")
async def skip_person_sync(
    name: str,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Mark a person as skipped for Gramps sync.
    They won't appear as pending for sync.
    Name passed as query parameter.
    """
    from models import PersonResolution, ExtractedFact
    from sqlalchemy import distinct

    # Get all obituaries containing this person
    obituary_ids = db.query(distinct(ExtractedFact.obituary_cache_id)).filter(
        ExtractedFact.subject_name == name
    ).all()

    if not obituary_ids:
        raise HTTPException(status_code=404, detail=f"Person '{name}' not found")

    for (obit_id,) in obituary_ids:
        resolution = db.query(PersonResolution).filter(
            PersonResolution.obituary_cache_id == obit_id,
            PersonResolution.extracted_name == name
        ).first()

        if resolution:
            resolution.status = 'rejected'
        else:
            resolution = PersonResolution(
                obituary_cache_id=obit_id,
                extracted_name=name,
                status='rejected'
            )
            db.add(resolution)

    db.commit()

    return {
        'success': True,
        'person_name': name,
        'action': 'skipped'
    }


@router.delete("/by-name/delete")
async def delete_person(
    name: str,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Delete a person and all their associated facts from the cache.
    This removes all ExtractedFact records where subject_name matches,
    as well as any PersonResolution records.
    Name passed as query parameter.
    """
    from models import PersonResolution, ExtractedFact, FactResolution, GrampsRecordMapping

    # Get all facts for this person
    facts = db.query(ExtractedFact).filter(
        ExtractedFact.subject_name == name
    ).all()

    if not facts:
        raise HTTPException(status_code=404, detail=f"Person '{name}' not found")

    fact_ids = [f.id for f in facts]
    facts_deleted = len(fact_ids)

    # Delete related FactResolution records
    db.query(FactResolution).filter(
        FactResolution.extracted_fact_id.in_(fact_ids)
    ).delete(synchronize_session='fetch')

    # Delete related GrampsRecordMapping records
    db.query(GrampsRecordMapping).filter(
        GrampsRecordMapping.extracted_fact_id.in_(fact_ids)
    ).delete(synchronize_session='fetch')

    # Delete PersonResolution records for this name
    resolutions_deleted = db.query(PersonResolution).filter(
        PersonResolution.extracted_name == name
    ).delete(synchronize_session='fetch')

    # Delete the facts themselves
    db.query(ExtractedFact).filter(
        ExtractedFact.subject_name == name
    ).delete(synchronize_session='fetch')

    db.commit()

    logger.info(f"Deleted person '{name}': {facts_deleted} facts, {resolutions_deleted} resolutions")

    return {
        'deleted': True,
        'person_name': name,
        'facts_deleted': facts_deleted,
        'resolutions_deleted': resolutions_deleted
    }


@router.get("/by-name/detail")
async def get_person_by_name(
    name: str,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Get detailed person info with facts grouped by obituary.
    Name passed as query parameter.
    """
    service = get_person_sync_service(db)
    person = service.get_person_by_name(name)

    if not person:
        raise HTTPException(status_code=404, detail=f"Person '{name}' not found")

    return {
        'id': person.id,
        'name': person.name,
        'name_formatted': person.name_formatted,
        'first_name': person.first_name,
        'middle_name': person.middle_name,
        'last_name': person.last_name,
        'gramps_handle': person.gramps_handle,
        'gramps_id': person.gramps_id,
        'sync_status': person.sync_status,
        'obituary_facts': [
            {
                'obituary_id': of.obituary_id,
                'obituary_url': of.obituary_url,
                'role': of.role,
                'facts': of.facts
            }
            for of in person.obituary_facts
        ]
    }
