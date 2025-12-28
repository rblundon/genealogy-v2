# FILE: backend/api/endpoints/obituaries.py
# API endpoints for obituary processing and fact extraction
# ============================================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from pydantic import BaseModel, HttpUrl
import logging
import requests
from bs4 import BeautifulSoup

from models import get_db, ObituaryCache, ExtractedFact
from services.llm_extractor import extract_facts_from_obituary, get_facts_by_obituary
from utils.hash_utils import hash_url, hash_content

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/obituaries", tags=["obituaries"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ObituaryProcessRequest(BaseModel):
    """Request model for processing an obituary URL."""
    url: HttpUrl


class FactStatusUpdateRequest(BaseModel):
    """Request model for updating fact resolution status."""
    resolution_status: str  # 'resolved', 'rejected', 'unresolved', 'conflicting'


class BulkFactStatusUpdateRequest(BaseModel):
    """Request model for bulk updating fact resolution status."""
    fact_ids: List[int]
    resolution_status: str  # 'resolved', 'rejected', 'unresolved', 'conflicting'


class FactResponse(BaseModel):
    """Response model for a single fact."""
    id: int
    fact_type: str
    subject_name: str
    subject_role: str
    fact_value: str
    related_name: Optional[str] = None
    relationship_type: Optional[str] = None
    extracted_context: Optional[str] = None
    is_inferred: bool
    inference_basis: Optional[str] = None
    confidence_score: float
    resolution_status: str
    gramps_person_id: Optional[str] = None


class ObituaryProcessResponse(BaseModel):
    """Response model for obituary processing."""
    obituary_id: int
    url: str
    facts_extracted: int
    cache_hit: bool
    facts: List[Dict]


class ObituaryStatusResponse(BaseModel):
    """Response model for obituary status check."""
    id: int
    url: str
    processing_status: str
    facts_count: int
    fetch_timestamp: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/process", response_model=ObituaryProcessResponse)
async def process_obituary(
    request: ObituaryProcessRequest,
    db: Session = Depends(get_db)
):
    """
    Process an obituary URL: fetch content, extract facts using LLM.

    Steps:
    1. Check if URL is already cached
    2. If not cached, fetch and parse the HTML content
    3. Extract facts using LLM
    4. Store facts in database
    5. Return extracted facts
    """

    url = str(request.url)
    url_hash_value = hash_url(url)

    # Check cache first
    cached_obituary = db.query(ObituaryCache).filter(
        ObituaryCache.url_hash == url_hash_value
    ).first()

    cache_hit = cached_obituary is not None

    if cached_obituary:
        logger.info(f"Cache hit for {url}")
        obituary = cached_obituary

        # Check if we already have facts extracted
        existing_facts = get_facts_by_obituary(db, obituary.id)
        if existing_facts:
            logger.info(f"Returning {len(existing_facts)} cached facts")
            return ObituaryProcessResponse(
                obituary_id=obituary.id,
                url=obituary.url,
                facts_extracted=len(existing_facts),
                cache_hit=True,
                facts=[fact.to_dict() for fact in existing_facts]
            )
    else:
        # Fetch obituary content
        logger.info(f"Fetching obituary from {url}")

        try:
            response = requests.get(url, timeout=15, headers={
                'User-Agent': 'GenealogyResearchBot/1.0 (Educational Project)'
            })
            response.raise_for_status()

            # Extract text from HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            extracted_text = '\n'.join(chunk for chunk in chunks if chunk)

            # Store in cache
            obituary = ObituaryCache(
                url=url,
                url_hash=url_hash_value,
                content_hash=hash_content(extracted_text),
                raw_html=response.text,
                extracted_text=extracted_text,
                http_status_code=response.status_code,
                processing_status='processing'
            )
            db.add(obituary)
            db.commit()
            db.refresh(obituary)

            logger.info(f"Cached obituary content ({len(extracted_text)} chars)")

        except requests.RequestException as e:
            logger.error(f"Failed to fetch obituary: {str(e)}")
            raise HTTPException(status_code=502, detail=f"Failed to fetch obituary: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing obituary: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing obituary: {str(e)}")

    # Extract facts using LLM
    try:
        facts = await extract_facts_from_obituary(
            db=db,
            obituary_cache_id=obituary.id,
            obituary_text=obituary.extracted_text
        )

        # Update obituary status
        obituary.processing_status = 'completed'
        db.commit()

        return ObituaryProcessResponse(
            obituary_id=obituary.id,
            url=obituary.url,
            facts_extracted=len(facts),
            cache_hit=cache_hit,
            facts=[fact.to_dict() for fact in facts]
        )

    except Exception as e:
        # Update obituary status to failed
        obituary.processing_status = 'failed'
        obituary.fetch_error = str(e)
        db.commit()
        logger.error(f"LLM extraction failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LLM extraction failed: {str(e)}")


@router.get("/facts/{obituary_id}")
async def get_obituary_facts(
    obituary_id: int,
    db: Session = Depends(get_db)
) -> Dict:
    """Get all facts for a specific obituary."""

    # Verify obituary exists
    obituary = db.query(ObituaryCache).filter(
        ObituaryCache.id == obituary_id
    ).first()

    if not obituary:
        raise HTTPException(status_code=404, detail=f"Obituary {obituary_id} not found")

    facts = get_facts_by_obituary(db, obituary_id)

    return {
        'obituary_id': obituary_id,
        'url': obituary.url,
        'processing_status': obituary.processing_status,
        'facts_count': len(facts),
        'facts': [fact.to_dict() for fact in facts]
    }


@router.get("/status/{obituary_id}", response_model=ObituaryStatusResponse)
async def get_obituary_status(
    obituary_id: int,
    db: Session = Depends(get_db)
):
    """Get processing status for a specific obituary."""

    obituary = db.query(ObituaryCache).filter(
        ObituaryCache.id == obituary_id
    ).first()

    if not obituary:
        raise HTTPException(status_code=404, detail=f"Obituary {obituary_id} not found")

    facts_count = db.query(ExtractedFact).filter(
        ExtractedFact.obituary_cache_id == obituary_id
    ).count()

    return ObituaryStatusResponse(
        id=obituary.id,
        url=obituary.url,
        processing_status=obituary.processing_status,
        facts_count=facts_count,
        fetch_timestamp=obituary.fetch_timestamp.isoformat() if obituary.fetch_timestamp else None
    )


@router.get("/pending")
async def get_pending_obituaries(
    db: Session = Depends(get_db)
) -> Dict:
    """Get list of obituaries pending processing or review."""

    pending = db.query(ObituaryCache).filter(
        ObituaryCache.processing_status.in_(['pending', 'processing'])
    ).all()

    return {
        'count': len(pending),
        'obituaries': [
            {
                'id': obit.id,
                'url': obit.url,
                'status': obit.processing_status,
                'fetch_timestamp': obit.fetch_timestamp.isoformat() if obit.fetch_timestamp else None
            }
            for obit in pending
        ]
    }


@router.get("/unresolved-facts")
async def get_unresolved_facts(
    limit: int = 100,
    db: Session = Depends(get_db)
) -> Dict:
    """Get facts that need resolution/review."""

    facts = db.query(ExtractedFact).filter(
        ExtractedFact.resolution_status.in_(['unresolved', 'conflicting'])
    ).order_by(
        ExtractedFact.confidence_score.asc()
    ).limit(limit).all()

    return {
        'count': len(facts),
        'facts': [fact.to_dict() for fact in facts]
    }


@router.post("/reprocess/{obituary_id}")
async def reprocess_obituary(
    obituary_id: int,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Reprocess an existing obituary to extract facts again.

    This will delete existing facts and re-run LLM extraction.
    Useful if the extraction prompt or logic has been updated.
    """

    obituary = db.query(ObituaryCache).filter(
        ObituaryCache.id == obituary_id
    ).first()

    if not obituary:
        raise HTTPException(status_code=404, detail=f"Obituary {obituary_id} not found")

    if not obituary.extracted_text:
        raise HTTPException(status_code=400, detail="Obituary has no extracted text")

    # Delete existing facts
    deleted_count = db.query(ExtractedFact).filter(
        ExtractedFact.obituary_cache_id == obituary_id
    ).delete()

    logger.info(f"Deleted {deleted_count} existing facts for obituary {obituary_id}")

    # Update status
    obituary.processing_status = 'processing'
    db.commit()

    # Re-extract facts
    try:
        facts = await extract_facts_from_obituary(
            db=db,
            obituary_cache_id=obituary.id,
            obituary_text=obituary.extracted_text
        )

        obituary.processing_status = 'completed'
        db.commit()

        return {
            'obituary_id': obituary_id,
            'deleted_facts': deleted_count,
            'new_facts_extracted': len(facts),
            'facts': [fact.to_dict() for fact in facts]
        }

    except Exception as e:
        obituary.processing_status = 'failed'
        obituary.fetch_error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Reprocessing failed: {str(e)}")


@router.patch("/facts/{fact_id}/status")
async def update_fact_status(
    fact_id: int,
    request: FactStatusUpdateRequest,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Update the resolution status of a specific fact.

    Valid statuses:
    - 'resolved': Fact has been approved
    - 'rejected': Fact has been rejected as incorrect
    - 'unresolved': Fact needs review (default)
    - 'conflicting': Fact conflicts with other data
    """

    valid_statuses = ['unresolved', 'resolved', 'conflicting', 'rejected']
    if request.resolution_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    fact = db.query(ExtractedFact).filter(ExtractedFact.id == fact_id).first()

    if not fact:
        raise HTTPException(status_code=404, detail=f"Fact {fact_id} not found")

    old_status = fact.resolution_status
    fact.resolution_status = request.resolution_status
    db.commit()
    db.refresh(fact)

    logger.info(f"Updated fact {fact_id} status: {old_status} -> {request.resolution_status}")

    return {
        'id': fact_id,
        'old_status': old_status,
        'new_status': fact.resolution_status,
        'fact': fact.to_dict()
    }


@router.patch("/facts/bulk-status")
async def bulk_update_fact_status(
    request: BulkFactStatusUpdateRequest,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Update the resolution status of multiple facts at once.
    """

    valid_statuses = ['unresolved', 'resolved', 'conflicting', 'rejected']
    if request.resolution_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    updated_count = db.query(ExtractedFact).filter(
        ExtractedFact.id.in_(request.fact_ids)
    ).update(
        {'resolution_status': request.resolution_status},
        synchronize_session='fetch'
    )

    db.commit()

    logger.info(f"Bulk updated {updated_count} facts to status: {request.resolution_status}")

    return {
        'updated_count': updated_count,
        'requested_ids': request.fact_ids,
        'new_status': request.resolution_status
    }


# ============================================================================
# List and Delete Endpoints
# ============================================================================

def parse_name(full_name: str) -> tuple:
    """
    Parse a full name into (first, middle, last, suffix).

    Examples:
        "John Smith" -> ("John", None, "Smith", None)
        "John Michael Smith" -> ("John", "Michael", "Smith", None)
        "John Smith Jr." -> ("John", None, "Smith", "Jr.")
    """
    if not full_name:
        return (None, None, None, None)

    parts = full_name.strip().split()
    if not parts:
        return (None, None, None, None)

    # Check for suffix
    suffixes = ['Jr.', 'Jr', 'Sr.', 'Sr', 'II', 'III', 'IV', 'V']
    suffix = None
    if len(parts) > 1 and parts[-1] in suffixes:
        suffix = parts.pop()

    if len(parts) == 1:
        return (parts[0], None, None, suffix)
    elif len(parts) == 2:
        return (parts[0], None, parts[1], suffix)
    else:
        # First name, middle name(s), last name
        return (parts[0], ' '.join(parts[1:-1]), parts[-1], suffix)


def format_name_last_first(full_name: str) -> str:
    """
    Format name as "Last, First M." (Last, First Middle-initial).

    Examples:
        "John Smith" -> "Smith, John"
        "John Michael Smith" -> "Smith, John M."
        "Jane" -> "Jane"
    """
    first, middle, last, suffix = parse_name(full_name)

    if not last:
        return first or full_name

    result = last
    if first:
        result += f", {first}"
    if middle:
        # Use initial
        result += f" {middle[0]}."
    if suffix:
        result += f" {suffix}"

    return result


@router.get("/")
async def list_obituaries(
    db: Session = Depends(get_db)
) -> Dict:
    """
    List all obituaries with primary deceased person name.
    Sorted alphabetically by last name.
    """
    from sqlalchemy import func, case

    # Get all completed obituaries with their facts
    obituaries = db.query(ObituaryCache).filter(
        ObituaryCache.processing_status == 'completed'
    ).all()

    results = []
    for obit in obituaries:
        # Get the primary deceased person's name
        primary_fact = db.query(ExtractedFact).filter(
            ExtractedFact.obituary_cache_id == obit.id,
            ExtractedFact.subject_role == 'deceased_primary',
            ExtractedFact.fact_type == 'person_name'
        ).first()

        primary_name = primary_fact.subject_name if primary_fact else "Unknown"

        # Count facts
        fact_count = db.query(ExtractedFact).filter(
            ExtractedFact.obituary_cache_id == obit.id
        ).count()

        # Count unresolved facts
        unresolved_count = db.query(ExtractedFact).filter(
            ExtractedFact.obituary_cache_id == obit.id,
            ExtractedFact.resolution_status == 'unresolved'
        ).count()

        # Parse name for sorting
        first, middle, last, suffix = parse_name(primary_name)

        results.append({
            'id': obit.id,
            'url': obit.url,
            'primary_name': primary_name,
            'primary_name_formatted': format_name_last_first(primary_name),
            'last_name': last or '',
            'first_name': first or '',
            'status': obit.processing_status,
            'fact_count': fact_count,
            'unresolved_count': unresolved_count,
            'created_at': obit.fetch_timestamp.isoformat() if obit.fetch_timestamp else None,
        })

    # Sort by last name, then first name
    results.sort(key=lambda x: (x['last_name'].lower(), x['first_name'].lower()))

    return {
        'count': len(results),
        'obituaries': results
    }


@router.delete("/{obituary_id}")
async def delete_obituary(
    obituary_id: int,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Delete an obituary and all associated facts.
    """
    obituary = db.query(ObituaryCache).filter(
        ObituaryCache.id == obituary_id
    ).first()

    if not obituary:
        raise HTTPException(status_code=404, detail=f"Obituary {obituary_id} not found")

    # Facts will be cascade deleted due to relationship setup
    url = obituary.url
    db.delete(obituary)
    db.commit()

    logger.info(f"Deleted obituary {obituary_id}: {url}")

    return {
        'deleted': True,
        'obituary_id': obituary_id,
        'url': url
    }
