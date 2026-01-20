from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

from models import get_db, ObituaryCache, ExtractedFact, PersonCluster, GrampsCitation
from services.llm_extractor import process_obituary_full
from services.fact_clusterer import FactClusterer
from services.gramps_client import GrampsClient
from services.gramps_matcher import GrampsMatcher
from services.gramps_citation_service import CitationService
from services.gramps_person_creator import PersonCreator
from services.url_validator import URLValidator
from services.obituary_fetcher import ObituaryFetcher
from utils.hash_utils import hash_url
from sqlalchemy import func
import json

# Verify undetected-playwright installation at startup
if not ObituaryFetcher.verify_installation():
    print("WARNING: Legacy.com scraping will not work until undetected-playwright is installed")

app = FastAPI(
    title="Genealogy Research Tool API",
    version="1.0.0",
    description="Extract genealogical facts from obituaries using LLM technology"
)

# CORS - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Must be False when using allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@app.delete("/api/admin/reset-database")
async def reset_database(db: Session = Depends(get_db)):
    """Complete database reset - clears all data"""
    from models import LLMCache

    counts = {
        'obituaries': db.query(ObituaryCache).count(),
        'llm_cache': db.query(LLMCache).count(),
        'facts': db.query(ExtractedFact).count(),
        'clusters': db.query(PersonCluster).count()
    }

    db.query(LLMCache).delete()
    db.query(ExtractedFact).delete()
    db.query(PersonCluster).delete()
    db.query(ObituaryCache).delete()
    db.commit()

    return {'status': 'success', 'deleted': counts}


# ============================================================================
# MODELS
# ============================================================================

class ProcessObituaryRequest(BaseModel):
    """Request to process an obituary"""
    source_url: str
    obituary_text: Optional[str] = None  # Optional: if omitted, will fetch from URL
    verbose_mode: bool = True  # If True, adds delays between extraction steps for UI visualization


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
        "version": "2.0.0",
        "phase": "Phase 2 - Cross-Obituary Clustering",
        "endpoints": {
            "/health": "Health check",
            "/api/obituaries/process": "Process an obituary (POST)",
            "/api/obituaries/{id}/facts": "Get facts for an obituary (GET)",
            "/api/clusters/generate": "Generate person clusters (POST)",
            "/api/clusters": "List all clusters (GET)",
            "/api/clusters/{id}": "Get cluster details (GET)",
            "/api/clusters/{id}/corroboration": "Get corroboration info (GET)"
        }
    }


def update_processing_step(db, obituary_id: int, step: str):
    """Update the processing step for real-time UI feedback."""
    obituary = db.query(ObituaryCache).filter(ObituaryCache.id == obituary_id).first()
    if obituary:
        obituary.processing_step = step
        db.commit()
        print(f"[Background] Step: {step}")


def run_full_pipeline_background(obituary_id: int, url: str, site: str, verbose_mode: bool, obituary_text: str = None):
    """
    Background task to run the full pipeline: fetch + extract.
    Creates its own database session since background tasks run after response is sent.
    """
    from models import SessionLocal
    db = SessionLocal()
    try:
        obituary = db.query(ObituaryCache).filter(ObituaryCache.id == obituary_id).first()
        if not obituary:
            print(f"[Background] Obituary {obituary_id} not found")
            return

        # Step 1: Fetch (if no text provided)
        if obituary_text:
            extracted_text = obituary_text
            update_processing_step(db, obituary_id, "validating")
        else:
            update_processing_step(db, obituary_id, "fetching")

            fetcher = ObituaryFetcher()
            fetch_result = fetcher.fetch(url, site)

            if not fetch_result['success']:
                obituary.processing_status = 'failed'
                obituary.fetch_error = fetch_result['error']
                obituary.http_status_code = fetch_result['http_status_code']
                obituary.processing_step = 'failed'
                db.commit()
                print(f"[Background] Fetch failed for obituary {obituary_id}: {fetch_result['error']}")
                return

            raw_html = fetch_result['raw_html']
            extracted_text = fetch_result['extracted_text']
            http_status = fetch_result['http_status_code']
            content_hash_value = hash_url(extracted_text)

            # Update obituary with fetched content
            obituary.raw_html = raw_html
            obituary.extracted_text = extracted_text
            obituary.content_hash = content_hash_value
            obituary.http_status_code = http_status
            db.commit()

        # Step 2: Extract facts
        update_processing_step(db, obituary_id, "extracting")

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        result = loop.run_until_complete(process_obituary_full(
            db,
            obituary_id,
            extracted_text,
            verbose_mode=verbose_mode
        ))

        # Step 3: Storing (brief step before completion)
        update_processing_step(db, obituary_id, "storing")

        # Mark as completed
        obituary.processing_status = 'completed'
        obituary.processing_step = 'completed'
        db.commit()

        print(f"[Background] Completed for obituary {obituary_id}: {result.get('facts_extracted', 0)} facts")

    except Exception as e:
        import traceback
        traceback.print_exc()
        # Mark as failed
        obituary = db.query(ObituaryCache).filter(ObituaryCache.id == obituary_id).first()
        if obituary:
            obituary.processing_status = 'failed'
            obituary.processing_step = 'failed'
            obituary.fetch_error = str(e)
            db.commit()
        print(f"[Background] Failed for obituary {obituary_id}: {e}")
    finally:
        db.close()


def run_fact_extraction_background(obituary_id: int, extracted_text: str, verbose_mode: bool):
    """
    Background task to run fact extraction only (for reprocessing).
    Creates its own database session since background tasks run after response is sent.
    """
    from models import SessionLocal
    db = SessionLocal()
    try:
        update_processing_step(db, obituary_id, "extracting")

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        result = loop.run_until_complete(process_obituary_full(
            db,
            obituary_id,
            extracted_text,
            verbose_mode=verbose_mode
        ))

        # Step: Storing (brief step before completion)
        update_processing_step(db, obituary_id, "storing")

        # Mark as completed
        obituary = db.query(ObituaryCache).filter(ObituaryCache.id == obituary_id).first()
        if obituary:
            obituary.processing_status = 'completed'
            obituary.processing_step = 'completed'
            db.commit()

        print(f"[Background] Completed extraction for obituary {obituary_id}: {result.get('facts_extracted', 0)} facts")

    except Exception as e:
        import traceback
        traceback.print_exc()
        # Mark as failed
        obituary = db.query(ObituaryCache).filter(ObituaryCache.id == obituary_id).first()
        if obituary:
            obituary.processing_status = 'failed'
            obituary.processing_step = 'failed'
            obituary.fetch_error = str(e)
            db.commit()
        print(f"[Background] Failed extraction for obituary {obituary_id}: {e}")
    finally:
        db.close()


@app.post("/api/obituaries/process")
async def process_obituary(
    request: ProcessObituaryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Process an obituary from URL or text.

    Smart detection:
    - If obituary_text provided: Use text (skip fetch)
    - If obituary_text omitted: Fetch from source_url

    Cache behavior:
    - If URL already processed (status=completed): Return cached data
    - If URL failed before (status=failed): Retry processing
    - If URL is processing: Return current status
    - If new URL: Fetch, extract, store

    In verbose mode, returns immediately and extracts facts in background
    so the frontend can poll and see facts appear in real-time.
    """
    try:
        # Validate URL
        validator = URLValidator()
        validation = validator.validate_url(request.source_url)

        if not validation['valid']:
            return {
                'status': 'error',
                'error': validation['error']
            }

        site = validation['site']
        url = validation['url']
        url_hash_value = hash_url(url)

        # Check cache
        cached = db.query(ObituaryCache).filter(
            ObituaryCache.url_hash == url_hash_value
        ).first()

        # CACHE HIT - Status: completed
        if cached and cached.processing_status == 'completed':
            # Count extracted facts
            fact_count = db.query(ExtractedFact).filter(
                ExtractedFact.obituary_cache_id == cached.id
            ).count()

            person_count = db.query(func.count(func.distinct(ExtractedFact.subject_name))).filter(
                ExtractedFact.obituary_cache_id == cached.id
            ).scalar()

            return {
                'status': 'success',
                'cache_hit': True,
                'obituary_id': cached.id,
                'processing_status': 'completed',
                'persons_extracted': person_count or 0,
                'facts_extracted': fact_count,
                'llm_cost_usd': 0.00,
                'message': 'Using cached obituary - no fetch or processing needed'
            }

        # CACHE HIT - Status: processing
        if cached and cached.processing_status == 'processing':
            return {
                'status': 'info',
                'cache_hit': True,
                'obituary_id': cached.id,
                'processing_status': 'processing',
                'message': 'Obituary is currently being processed. Please check back shortly.'
            }

        # NEW or FAILED - Process obituary

        # Determine if text was provided or we need to fetch
        has_text = request.obituary_text and request.obituary_text.strip()

        # Create or update cache entry with 'processing' status
        if cached:
            # Update existing (retry after failure)
            cached.processing_status = 'processing'
            cached.processing_step = 'validating'
            cached.fetch_error = None
            if has_text:
                cached.extracted_text = request.obituary_text
        else:
            # Create new
            cached = ObituaryCache(
                url=url,
                url_hash=url_hash_value,
                processing_status='processing',
                processing_step='validating',
                extracted_text=request.obituary_text if has_text else None
            )
            db.add(cached)

        db.commit()
        db.refresh(cached)

        obituary_id = cached.id

        # In verbose mode, run FULL pipeline (fetch + extract) in background
        if request.verbose_mode:
            background_tasks.add_task(
                run_full_pipeline_background,
                obituary_id,
                url,
                site,
                request.verbose_mode,
                request.obituary_text if has_text else None
            )

            # Return immediately so frontend can start polling
            return {
                'status': 'success',
                'cache_hit': False,
                'obituary_id': obituary_id,
                'processing_status': 'processing',
                'processing_step': 'validating',
                'persons_extracted': 0,
                'facts_extracted': 0,
                'llm_cost_usd': 0.0,
                'message': 'Processing started. Poll for updates to see progress in real-time.'
            }

        # Non-verbose mode: run synchronously (original behavior)
        # This path is used when verbose_mode=False
        if not has_text:
            fetcher = ObituaryFetcher()
            fetch_result = fetcher.fetch(url, site)

            if not fetch_result['success']:
                cached.processing_status = 'failed'
                cached.fetch_error = fetch_result['error']
                cached.http_status_code = fetch_result['http_status_code']
                db.commit()
                return {
                    'status': 'error',
                    'error': fetch_result['error'],
                    'http_status_code': fetch_result['http_status_code']
                }

            cached.raw_html = fetch_result['raw_html']
            cached.extracted_text = fetch_result['extracted_text']
            cached.content_hash = fetch_result['content_hash']
            cached.http_status_code = fetch_result['http_status_code']
            db.commit()

        result = await process_obituary_full(
            db,
            obituary_id,
            cached.extracted_text,
            verbose_mode=False
        )

        # Success!
        cached.processing_status = 'completed'
        cached.processing_step = 'completed'
        db.commit()

        return {
            'status': 'success',
            'cache_hit': False,
            'obituary_id': obituary_id,
            'processing_status': 'completed',
            'persons_extracted': result.get('persons_extracted', 0),
            'facts_extracted': result.get('facts_extracted', 0),
            'llm_cost_usd': result.get('cost_usd', 0.0),
            'processing_time_ms': result.get('processing_time_ms', 0)
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        if 'cached' in locals() and cached:
            cached.processing_status = 'failed'
            cached.fetch_error = str(e)
            db.commit()
        return {
            'status': 'error',
            'error': f'Unexpected error: {str(e)}'
        }


@app.get("/api/obituaries/{obituary_id}")
async def get_obituary(
    obituary_id: int,
    db: Session = Depends(get_db)
):
    """Get obituary status and details by ID"""

    obituary = db.query(ObituaryCache).filter(
        ObituaryCache.id == obituary_id
    ).first()

    if not obituary:
        raise HTTPException(status_code=404, detail=f"Obituary {obituary_id} not found")

    # Get facts (for verbose mode - show facts as they're extracted)
    facts = db.query(ExtractedFact).filter(
        ExtractedFact.obituary_cache_id == obituary_id
    ).order_by(ExtractedFact.id).all()

    facts_count = len(facts)

    persons_count = db.query(func.count(func.distinct(ExtractedFact.subject_name))).filter(
        ExtractedFact.obituary_cache_id == obituary_id
    ).scalar() or 0

    return {
        "id": obituary.id,
        "url": obituary.url,
        "processing_status": obituary.processing_status or "completed",
        "processing_step": obituary.processing_step,  # Real-time step for UI
        "fetch_error": obituary.fetch_error,
        "persons_extracted": persons_count,
        "facts_extracted": facts_count,
        "fetch_timestamp": obituary.fetch_timestamp.isoformat() if obituary.fetch_timestamp else None,
        "llm_cost_usd": 0.0,  # TODO: Track actual LLM costs
        "extracted_text": obituary.extracted_text,
        "http_status_code": obituary.http_status_code,
        # Verbose mode: include facts for live display during processing
        "facts": [fact.to_dict() for fact in facts],
    }


@app.delete("/api/obituaries/{obituary_id}")
async def delete_obituary(
    obituary_id: int,
    db: Session = Depends(get_db)
):
    """Delete an obituary and all associated data"""
    obituary = db.query(ObituaryCache).filter(ObituaryCache.id == obituary_id).first()

    if not obituary:
        raise HTTPException(status_code=404, detail="Obituary not found")

    # Delete related facts first
    db.query(ExtractedFact).filter(ExtractedFact.obituary_cache_id == obituary_id).delete()

    # Delete the obituary
    db.delete(obituary)
    db.commit()

    return {"status": "success", "message": "Obituary deleted"}


@app.post("/api/obituaries/{obituary_id}/reprocess")
async def reprocess_obituary(
    obituary_id: int,
    verbose_mode: bool = True,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Reprocess an obituary using its stored extracted text.
    Deletes existing facts and re-runs the rules engine extraction.

    Args:
        obituary_id: The obituary ID to reprocess
        verbose_mode: If True, adds delays between extraction steps for UI visualization
    """
    # Get obituary
    obituary = db.query(ObituaryCache).filter(
        ObituaryCache.id == obituary_id
    ).first()

    if not obituary:
        raise HTTPException(status_code=404, detail=f"Obituary {obituary_id} not found")

    if not obituary.extracted_text:
        raise HTTPException(status_code=400, detail="No extracted text available for reprocessing")

    extracted_text = obituary.extracted_text

    try:
        # Delete existing facts
        db.query(ExtractedFact).filter(
            ExtractedFact.obituary_cache_id == obituary_id
        ).delete()
        db.commit()

        # Set status to processing
        obituary.processing_status = 'processing'
        db.commit()

        # In verbose mode, run extraction in background for real-time display
        if verbose_mode and background_tasks:
            background_tasks.add_task(
                run_fact_extraction_background,
                obituary_id,
                extracted_text,
                verbose_mode
            )

            return {
                'status': 'success',
                'obituary_id': obituary_id,
                'processing_status': 'processing',
                'persons_extracted': 0,
                'facts_extracted': 0,
                'message': 'Reprocessing started. Poll for updates to see facts appear in real-time.'
            }

        # Non-verbose mode: run synchronously
        result = await process_obituary_full(
            db,
            obituary_id,
            extracted_text,
            verbose_mode=False
        )

        # Update status to completed
        obituary.processing_status = 'completed'
        db.commit()

        return {
            'status': 'success',
            'obituary_id': obituary_id,
            'processing_status': 'completed',
            'persons_extracted': result.get('persons_extracted', 0),
            'facts_extracted': result.get('facts_extracted', 0),
            'message': 'Obituary reprocessed successfully'
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        obituary.processing_status = 'failed'
        obituary.fetch_error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Reprocessing failed: {str(e)}")


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
    limit: int = 100,
    offset: int = 0
):
    """List all processed obituaries"""

    obituaries = db.query(ObituaryCache).offset(offset).limit(limit).all()

    result = []
    for o in obituaries:
        # Count persons for this obituary
        persons_count = db.query(func.count(func.distinct(ExtractedFact.subject_name))).filter(
            ExtractedFact.obituary_cache_id == o.id
        ).scalar() or 0

        result.append({
            "id": o.id,
            "url": o.url,
            "processing_status": o.processing_status,
            "fetch_timestamp": o.fetch_timestamp.isoformat() if o.fetch_timestamp else None,
            "persons_extracted": persons_count,
            "llm_cost_usd": 0.0  # TODO: Track actual LLM costs
        })

    return result


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

# ============================================================================
# CLUSTERING ENDPOINTS (Phase 2)
# ============================================================================

@app.post("/api/clusters/generate")
async def generate_clusters(db: Session = Depends(get_db)):
    """
    Generate person clusters across all obituaries.

    This performs fuzzy matching to identify name variants and
    creates PersonCluster records linking facts about the same person.
    """
    clusterer = FactClusterer(db, fuzzy_threshold=0.85)

    # Find cross-obituary clusters
    clusters = clusterer.find_cross_obituary_clusters()

    # Create database records
    cluster_records = clusterer.create_person_cluster_records(clusters)

    return {
        'clusters_created': len(cluster_records),
        'summary': {
            'total_clusters': len(clusters),
            'multi_source_clusters': sum(1 for c in clusters if c['obituary_count'] > 1),
            'clusters_with_variants': sum(1 for c in clusters if len(c['name_variants']) > 1),
            'total_facts_clustered': sum(c['fact_count'] for c in clusters)
        },
        'clusters': [
            {
                'cluster_id': rec.id,
                'canonical_name': rec.canonical_name,
                'name_variants': json.loads(rec.name_variants),
                'source_count': rec.source_count,
                'fact_count': rec.fact_count,
                'confidence': float(rec.confidence_score) if rec.confidence_score else None
            }
            for rec in cluster_records[:20]  # First 20 clusters
        ]
    }


@app.get("/api/clusters")
async def list_clusters(
    min_sources: int = 1,
    db: Session = Depends(get_db)
):
    """
    List all person clusters, optionally filtered by minimum source count.
    """
    query = db.query(PersonCluster)

    if min_sources > 1:
        query = query.filter(PersonCluster.source_count >= min_sources)

    clusters = query.order_by(
        PersonCluster.source_count.desc(),
        PersonCluster.fact_count.desc()
    ).all()

    return {
        'cluster_count': len(clusters),
        'clusters': [
            {
                'cluster_id': c.id,
                'canonical_name': c.canonical_name,
                'name_variants': json.loads(c.name_variants),
                'source_count': c.source_count,
                'fact_count': c.fact_count,
                'confidence': float(c.confidence_score) if c.confidence_score else None,
                'cluster_status': c.cluster_status,
                'gramps_person_id': c.gramps_person_id
            }
            for c in clusters
        ]
    }


@app.get("/api/clusters/ready-for-creation")
async def get_clusters_ready_for_creation(
    min_confidence: float = 0.80,
    min_sources: int = 2,
    db: Session = Depends(get_db)
):
    """
    Get clusters that are good candidates for person creation.

    Filters:
    - Not already linked to Gramps
    - Meets minimum confidence threshold
    - Has minimum number of sources

    Args:
        min_confidence: Minimum confidence score (default: 0.80)
        min_sources: Minimum number of sources (default: 2)
    """
    clusters = db.query(PersonCluster).filter(
        PersonCluster.gramps_person_id.is_(None),
        PersonCluster.confidence_score >= min_confidence,
        PersonCluster.source_count >= min_sources
    ).order_by(
        PersonCluster.source_count.desc(),
        PersonCluster.confidence_score.desc()
    ).all()

    results = []
    for cluster in clusters:
        results.append({
            'cluster_id': cluster.id,
            'canonical_name': cluster.canonical_name,
            'confidence': float(cluster.confidence_score) if cluster.confidence_score else None,
            'source_count': cluster.source_count,
            'fact_count': cluster.fact_count
        })

    return {
        'count': len(results),
        'clusters': results
    }


@app.get("/api/clusters/{cluster_id}")
async def get_cluster_details(
    cluster_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific person cluster,
    including all facts and sources.
    """
    clusterer = FactClusterer(db)

    summary = clusterer.get_cluster_summary(cluster_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # Add conflict detection
    conflicts = clusterer.detect_conflicts(cluster_id)
    summary['conflicts'] = conflicts

    return summary


@app.get("/api/clusters/{cluster_id}/corroboration")
async def get_cluster_corroboration(
    cluster_id: int,
    db: Session = Depends(get_db)
):
    """
    Show multi-source corroboration for a person cluster.

    Displays facts that appear in multiple obituaries,
    which increases confidence.
    """
    clusterer = FactClusterer(db)
    corroborated = clusterer.get_corroborated_facts(cluster_id)

    return {
        'cluster_id': cluster_id,
        'corroborated_facts': corroborated,
        'corroboration_summary': {
            'total_corroborated_facts': len(corroborated),
            'max_source_count': max((c['source_count'] for c in corroborated), default=0)
        }
    }


@app.get("/api/matching/test")
async def test_matching(
    name1: str,
    name2: str,
    db: Session = Depends(get_db)
):
    """
    Test fuzzy matching between two names.

    Useful for debugging and tuning match thresholds.
    """
    from services.person_matcher import PersonMatcher

    matcher = PersonMatcher(fuzzy_threshold=0.85)
    result = matcher.match_score(name1, name2)

    return {
        'name1': name1,
        'name2': name2,
        'match_result': result
    }


# ============================================================================
# GRAMPS WEB INTEGRATION (Phase 3 - Read-Only)
# ============================================================================

@app.get("/api/gramps/health")
async def gramps_health_check():
    """
    Check if Gramps Web is accessible.
    """
    gramps = GrampsClient()
    is_healthy = gramps.health_check()

    return {
        'status': 'healthy' if is_healthy else 'unhealthy',
        'gramps_url': gramps.base_url,
        'connected': is_healthy
    }


@app.get("/api/gramps/search")
async def search_gramps_people(
    query: str = None,
    surname: str = None,
    given_name: str = None,
    limit: int = 10
):
    """
    Search Gramps Web for people.

    Direct passthrough to Gramps API for testing.
    """
    gramps = GrampsClient()

    results = gramps.search_people(
        query=query,
        surname=surname,
        given_name=given_name,
        limit=limit
    )

    return {
        'count': len(results),
        'results': results
    }


@app.get("/api/clusters/{cluster_id}/gramps-matches")
async def find_gramps_matches(
    cluster_id: int,
    db: Session = Depends(get_db)
):
    """
    Find potential Gramps Web matches for a person cluster.

    READ-ONLY: Does not modify Gramps data.
    """
    matcher = GrampsMatcher(db)

    matches = matcher.find_matches_for_cluster(cluster_id)

    return {
        'cluster_id': cluster_id,
        'matches_found': len(matches),
        'matches': [
            {
                'gramps_id': m['gramps_id'],
                'gramps_handle': m['gramps_person'].get('handle'),
                'name': m['gramps_facts']['names'][0]['full'] if m['gramps_facts']['names'] else 'Unknown',
                'match_confidence': m['match_confidence'],
                'match_reasons': m['match_reasons'],
                'conflicts': m['conflicts'],
                'birth_date': m['gramps_facts'].get('birth_date'),
                'death_date': m['gramps_facts'].get('death_date')
            }
            for m in matches
        ]
    }


# ============================================================================
# GRAMPS CITATION ENDPOINTS (Phase 3 Stage 2 - Write Operations)
# ============================================================================

class LinkGrampsRequest(BaseModel):
    """Request to link a cluster to a Gramps person"""
    gramps_person_id: str
    gramps_handle: str
    confidence: str = 'high'


@app.post("/api/clusters/{cluster_id}/link-gramps")
async def link_cluster_to_gramps(
    cluster_id: int,
    request: LinkGrampsRequest,
    db: Session = Depends(get_db)
):
    """
    Link a person cluster to a Gramps person and create citations.

    This is the main write operation that:
    1. Updates the cluster with gramps_person_id
    2. Creates source records in Gramps for each obituary
    3. Creates citation records linking persons to sources
    4. Records all writes in local gramps_citations table
    """
    citation_service = CitationService(db)

    result = citation_service.link_cluster_to_gramps(
        cluster_id=cluster_id,
        gramps_person_id=request.gramps_person_id,
        gramps_handle=request.gramps_handle,
        confidence=request.confidence
    )

    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('error', 'Unknown error'))

    return result


@app.get("/api/clusters/{cluster_id}/citations")
async def get_cluster_citations(
    cluster_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all citations created for a person cluster.
    """
    citation_service = CitationService(db)

    citations = citation_service.get_cluster_citations(cluster_id)

    return {
        'cluster_id': cluster_id,
        'citation_count': len(citations),
        'citations': citations
    }


@app.delete("/api/clusters/{cluster_id}/gramps-link")
async def unlink_cluster_from_gramps(
    cluster_id: int,
    db: Session = Depends(get_db)
):
    """
    Remove Gramps link from a cluster.

    Note: This does NOT delete data from Gramps Web.
    It only removes the link in our local database.
    """
    citation_service = CitationService(db)

    result = citation_service.unlink_cluster(cluster_id)

    if not result.get('success'):
        raise HTTPException(status_code=400, detail=result.get('error', 'Unknown error'))

    return result


@app.get("/api/gramps/person/{gramps_person_id}/citations")
async def get_gramps_person_citations(
    gramps_person_id: str,
    db: Session = Depends(get_db)
):
    """
    Get all citations we've created for a Gramps person.
    """
    citation_service = CitationService(db)

    citations = citation_service.get_person_citations(gramps_person_id)

    return {
        'gramps_person_id': gramps_person_id,
        'citation_count': len(citations),
        'citations': citations
    }


@app.get("/api/gramps/audit-trail")
async def get_gramps_audit_trail(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get audit trail of all citations created in Gramps.

    Shows recent citations with readable obituary names for easy review.
    """
    citation_service = CitationService(db)

    citations = citation_service.get_audit_trail(limit=limit)

    return {
        'citation_count': len(citations),
        'citations': citations
    }


@app.get("/api/gramps/person/{person_id}/debug")
async def debug_gramps_person(person_id: str):
    """
    Get full Gramps person record for debugging.

    Shows all names, events, and raw data to debug issues.
    """
    gramps = GrampsClient()
    person = gramps.get_person(person_id)

    if not person:
        raise HTTPException(status_code=404, detail=f"Person {person_id} not found")

    # Get events from event_ref_list
    events = []
    for event_ref in person.get('event_ref_list', []):
        event_handle = event_ref.get('ref')
        if event_handle:
            try:
                event = gramps._request('GET', f'/events/{event_handle}')
                events.append({
                    'handle': event_handle,
                    'type': event.get('type'),
                    'date': event.get('date'),
                    'place': event.get('place'),
                    'raw': event
                })
            except:
                events.append({'handle': event_handle, 'error': 'Failed to fetch'})

    return {
        'person_id': person_id,
        'handle': person.get('handle'),
        'gramps_id': person.get('gramps_id'),
        'primary_name': person.get('primary_name'),
        'alternate_names': person.get('alternate_names'),
        'event_ref_list': person.get('event_ref_list'),
        'events_resolved': events,
        'full_record': person
    }


# ============================================================================
# PERSON CREATION ENDPOINTS (Phase 3 Stage 3)
# ============================================================================

@app.get("/api/clusters/{cluster_id}/creation-preview")
async def preview_person_creation(
    cluster_id: int,
    db: Session = Depends(get_db)
):
    """
    Preview what would be created in Gramps for this cluster.

    Shows:
    - Person data (name, dates, etc.)
    - Which relationships can be created
    - Source citations

    Does NOT create anything (read-only).
    """
    creator = PersonCreator(db)

    try:
        preview = creator.preview_person_creation(cluster_id)
        return preview
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/clusters/{cluster_id}/create-in-gramps")
async def create_person_in_gramps(
    cluster_id: int,
    create_relationships: bool = True,
    db: Session = Depends(get_db)
):
    """
    Create a new person in Gramps Web from this cluster.

    PERFORMS WRITES TO GRAMPS WEB:
    - Creates new person record
    - Adds birth/death events
    - Creates family relationships (if requested)
    - Creates source citations
    - Updates cluster.gramps_person_id

    Args:
        cluster_id: PersonCluster ID
        create_relationships: Whether to create family links (default: true)

    Returns:
        Summary of creation operation
    """
    creator = PersonCreator(db)

    try:
        result = creator.create_person_from_cluster(
            cluster_id=cluster_id,
            create_relationships=create_relationships
        )

        return {
            'status': 'success',
            **result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
