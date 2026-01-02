from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

from models import get_db, ObituaryCache, ExtractedFact, PersonCluster
from services.llm_extractor import process_obituary_full
from services.fact_clusterer import FactClusterer
from services.gramps_client import GrampsClient
from services.gramps_matcher import GrampsMatcher
from utils.hash_utils import hash_url
import json

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
