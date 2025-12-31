from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

from models import get_db, ObituaryCache, ExtractedFact
from services.llm_extractor import process_obituary_full
from utils.hash_utils import hash_url

app = FastAPI(
    title="Genealogy Research Tool API",
    version="1.0.0",
    description="Extract genealogical facts from obituaries using LLM technology"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# MODELS
# ============================================================================

class ProcessObituaryRequest(BaseModel):
    """Request to process an obituary"""
    obituary_text: str
    source_url: str = "http://test.obituary/manual"


class PersonInfo(BaseModel):
    """Person extracted from obituary"""
    full_name: str
    given_names: Optional[str] = None
    surname: Optional[str] = None
    surname_source: Optional[str] = None
    maiden_name: Optional[str] = None
    nickname: Optional[str] = None
    role: str
    is_deceased: Optional[bool] = None
    spouse_of: Optional[str] = None
    age: Optional[str] = None
    notes: Optional[str] = None


class FactInfo(BaseModel):
    """Fact extracted from obituary"""
    id: Optional[int] = None
    fact_type: str
    subject_name: str
    subject_role: Optional[str] = None
    fact_value: str
    related_name: Optional[str] = None
    relationship_type: Optional[str] = None
    extracted_context: Optional[str] = None
    is_inferred: Optional[bool] = False
    inference_basis: Optional[str] = None
    confidence_score: Optional[float] = None
    resolution_status: Optional[str] = None


class ProcessObituaryResponse(BaseModel):
    """Response from obituary processing"""
    obituary_id: int
    persons_extracted: int
    facts_extracted: int
    cache_hit: bool
    persons: List[Dict]
    facts: List[Dict]


class ObituaryFactsResponse(BaseModel):
    """Response for getting facts of an obituary"""
    obituary_id: int
    fact_count: int
    facts: List[Dict]


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "genealogy-research-tool"}


@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "service": "Genealogy Research Tool API",
        "version": "1.0.0",
        "phase": "Phase 1 - Foundation",
        "endpoints": {
            "/health": "Health check",
            "/api/obituaries/process": "Process an obituary (POST)",
            "/api/obituaries/{id}/facts": "Get facts for an obituary (GET)"
        }
    }


@app.post("/api/obituaries/process", response_model=ProcessObituaryResponse)
async def process_obituary(
    request: ProcessObituaryRequest,
    db: Session = Depends(get_db)
):
    """
    Process an obituary: extract person mentions and facts.

    Phase 1: Accepts obituary text directly (no web fetching yet)
    """

    url_hash_value = hash_url(request.source_url)

    # Check cache
    cached_obit = db.query(ObituaryCache).filter(
        ObituaryCache.url_hash == url_hash_value
    ).first()

    cache_hit = cached_obit is not None

    if cached_obit:
        obituary = cached_obit
        print(f"Cache hit for {request.source_url}")
    else:
        # Create new obituary record
        obituary = ObituaryCache(
            url=request.source_url,
            url_hash=url_hash_value,
            extracted_text=request.obituary_text,
            processing_status='processing'
        )
        db.add(obituary)
        db.commit()
        db.refresh(obituary)
        print(f"Processing new obituary: {request.source_url}")

    # Extract facts
    try:
        result = await process_obituary_full(
            db,
            obituary.id,
            obituary.extracted_text
        )

        # Update status
        obituary.processing_status = 'completed'
        db.commit()

        return ProcessObituaryResponse(
            obituary_id=obituary.id,
            persons_extracted=result['persons_extracted'],
            facts_extracted=result['facts_extracted'],
            cache_hit=cache_hit,
            persons=result['persons'],
            facts=result['facts']
        )

    except Exception as e:
        obituary.processing_status = 'failed'
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/obituaries/{obituary_id}/facts", response_model=ObituaryFactsResponse)
async def get_obituary_facts(
    obituary_id: int,
    db: Session = Depends(get_db)
):
    """Get all facts for a specific obituary"""

    # Check obituary exists
    obituary = db.query(ObituaryCache).filter(
        ObituaryCache.id == obituary_id
    ).first()

    if not obituary:
        raise HTTPException(status_code=404, detail=f"Obituary {obituary_id} not found")

    facts = db.query(ExtractedFact).filter(
        ExtractedFact.obituary_cache_id == obituary_id
    ).all()

    return ObituaryFactsResponse(
        obituary_id=obituary_id,
        fact_count=len(facts),
        facts=[fact.to_dict() for fact in facts]
    )


@app.get("/api/obituaries")
async def list_obituaries(
    db: Session = Depends(get_db),
    limit: int = 10,
    offset: int = 0
):
    """List all processed obituaries"""

    obituaries = db.query(ObituaryCache).offset(offset).limit(limit).all()

    return {
        "count": len(obituaries),
        "obituaries": [
            {
                "id": o.id,
                "url": o.url,
                "processing_status": o.processing_status,
                "fetch_timestamp": o.fetch_timestamp.isoformat() if o.fetch_timestamp else None
            }
            for o in obituaries
        ]
    }


@app.get("/api/facts/by-person/{person_name}")
async def get_facts_by_person(
    person_name: str,
    db: Session = Depends(get_db)
):
    """Get all facts about a specific person across all obituaries"""

    facts = db.query(ExtractedFact).filter(
        ExtractedFact.subject_name.ilike(f"%{person_name}%")
    ).all()

    return {
        "person_name": person_name,
        "fact_count": len(facts),
        "facts": [fact.to_dict() for fact in facts]
    }

@app.get("/api/analysis/cross-obituary")
async def cross_obituary_analysis(db: Session = Depends(get_db)):
    """
    Analyze facts across multiple obituaries to identify:
    - People mentioned in multiple obituaries
    - Potential name variants needing fuzzy matching
    """
    from sqlalchemy import func, distinct
    from collections import defaultdict

    # Find people in multiple obituaries
    multi_obit_people = db.query(
        ExtractedFact.subject_name,
        func.count(distinct(ExtractedFact.obituary_cache_id)).label('obit_count')
    ).group_by(
        ExtractedFact.subject_name
    ).having(
        func.count(distinct(ExtractedFact.obituary_cache_id)) > 1
    ).order_by(
        func.count(distinct(ExtractedFact.obituary_cache_id)).desc()
    ).all()

    people_in_multiple_obits = []
    for name, count in multi_obit_people:
        facts = db.query(ExtractedFact).filter(
            ExtractedFact.subject_name == name
        ).all()

        obit_ids = list(set(f.obituary_cache_id for f in facts))
        obits = db.query(ObituaryCache).filter(
            ObituaryCache.id.in_(obit_ids)
        ).all()

        people_in_multiple_obits.append({
            'name': name,
            'obituary_count': count,
            'obituaries': [o.url for o in obits]
        })

    # Detect potential name variants
    all_names = db.query(distinct(ExtractedFact.subject_name)).all()
    all_names = [n[0] for n in all_names]

    surname_groups = defaultdict(list)
    for name in all_names:
        parts = name.split()
        if len(parts) >= 2:
            surname = parts[-1]
            surname_groups[surname].append(name)

    potential_variants = []
    for surname, names in surname_groups.items():
        if len(names) > 1:
            first_names = [' '.join(n.split()[:-1]) for n in names]
            unique_firsts = set(first_names)
            if len(unique_firsts) > 1:
                potential_variants.append({
                    'surname': surname,
                    'variants': names
                })

    return {
        'people_in_multiple_obituaries': people_in_multiple_obits,
        'potential_name_variants': potential_variants,
        'total_obituaries_processed': db.query(ObituaryCache).filter(
            ObituaryCache.processing_status == 'completed'
        ).count(),
        'total_facts': db.query(ExtractedFact).count()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
