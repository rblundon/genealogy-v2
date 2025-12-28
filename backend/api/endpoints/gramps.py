"""Gramps Web API endpoints."""

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from services.gramps_connector import GrampsConnector, get_gramps_connector
from services.person_matcher import PersonMatcher, get_person_matcher

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


class GrampsPersonSummary(BaseModel):
    """Simplified person summary for listing."""

    handle: str
    gramps_id: str
    first_name: str
    surname: str
    gender: int  # 0=female, 1=male, 2=unknown


class GrampsPersonListResponse(BaseModel):
    """Response model for people list."""

    count: int
    people: List[GrampsPersonSummary]


class GrampsSearchResponse(BaseModel):
    """Response model for search results."""

    query: str
    count: int
    results: List[GrampsPersonSummary]


class MatchCandidateResponse(BaseModel):
    """A potential match for a person."""

    handle: str
    gramps_id: str
    first_name: str
    surname: str
    score: float
    match_details: dict


class MatchResultResponse(BaseModel):
    """Result of matching a person against Gramps database."""

    query_first_name: str
    query_surname: str
    candidates: List[MatchCandidateResponse]
    best_match: Optional[MatchCandidateResponse] = None
    is_confident_match: bool


class CreatePersonRequest(BaseModel):
    """Request model for creating a person."""

    first_name: str
    surname: str
    gender: int = 2  # 0=female, 1=male, 2=unknown
    suffix: str = ""
    gramps_id: Optional[str] = None


class CreatePersonResponse(BaseModel):
    """Response model for created person."""

    handle: str
    gramps_id: str
    first_name: str
    surname: str


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


@router.get("/people", response_model=GrampsPersonListResponse)
async def list_gramps_people(
    connector: GrampsConnector = Depends(get_gramps_connector),
) -> GrampsPersonListResponse:
    """
    Get all people from Gramps database.

    Returns a simplified list of all people with their names and handles.
    """
    people = await connector.get_all_people()

    summaries = []
    for person in people:
        first_name, surname = connector.extract_person_name(person)
        summaries.append(GrampsPersonSummary(
            handle=person.get("handle", ""),
            gramps_id=person.get("gramps_id", ""),
            first_name=first_name,
            surname=surname,
            gender=person.get("gender", 2),
        ))

    return GrampsPersonListResponse(
        count=len(summaries),
        people=summaries,
    )


@router.get("/people/{handle}")
async def get_gramps_person(
    handle: str,
    connector: GrampsConnector = Depends(get_gramps_connector),
) -> dict:
    """
    Get a single person by handle.

    Returns the full Gramps person object.
    """
    person = await connector.get_person(handle)
    if person is None:
        raise HTTPException(status_code=404, detail=f"Person {handle} not found")
    return person


@router.get("/search", response_model=GrampsSearchResponse)
async def search_gramps_people(
    query: str = Query(..., min_length=1, description="Search query"),
    connector: GrampsConnector = Depends(get_gramps_connector),
) -> GrampsSearchResponse:
    """
    Search for people in Gramps database.

    Returns matching people based on name search.
    """
    results = await connector.search_people(query)

    summaries = []
    for person in results:
        first_name, surname = connector.extract_person_name(person)
        summaries.append(GrampsPersonSummary(
            handle=person.get("handle", ""),
            gramps_id=person.get("gramps_id", ""),
            first_name=first_name,
            surname=surname,
            gender=person.get("gender", 2),
        ))

    return GrampsSearchResponse(
        query=query,
        count=len(summaries),
        results=summaries,
    )


@router.get("/families")
async def list_gramps_families(
    connector: GrampsConnector = Depends(get_gramps_connector),
) -> dict:
    """
    Get all families from Gramps database.
    """
    families = await connector.get_all_families()
    return {
        "count": len(families),
        "families": families,
    }


@router.get("/match", response_model=MatchResultResponse)
async def match_person(
    first_name: str = Query(..., description="First name to match"),
    surname: str = Query(..., description="Surname to match"),
    maiden_name: Optional[str] = Query(None, description="Optional maiden name"),
    matcher: PersonMatcher = Depends(get_person_matcher),
) -> MatchResultResponse:
    """
    Find potential matches for a person in Gramps database.

    Uses fuzzy matching to find people with similar names.
    Returns candidates sorted by match score.
    """
    result = await matcher.find_matches(
        first_name=first_name,
        surname=surname,
        maiden_name=maiden_name,
    )

    # Convert to response models
    candidates = [
        MatchCandidateResponse(
            handle=c.handle,
            gramps_id=c.gramps_id,
            first_name=c.first_name,
            surname=c.surname,
            score=c.score,
            match_details=c.match_details,
        )
        for c in result.candidates
    ]

    best_match = None
    if result.best_match:
        best_match = MatchCandidateResponse(
            handle=result.best_match.handle,
            gramps_id=result.best_match.gramps_id,
            first_name=result.best_match.first_name,
            surname=result.best_match.surname,
            score=result.best_match.score,
            match_details=result.best_match.match_details,
        )

    return MatchResultResponse(
        query_first_name=result.query_first_name,
        query_surname=result.query_surname,
        candidates=candidates,
        best_match=best_match,
        is_confident_match=result.is_confident_match,
    )


@router.post("/people", response_model=CreatePersonResponse, status_code=201)
async def create_person(
    request: CreatePersonRequest,
    connector: GrampsConnector = Depends(get_gramps_connector),
) -> CreatePersonResponse:
    """
    Create a new person in Gramps database.

    Returns the created person with their handle and Gramps ID.
    """
    person_data = connector.build_person_data(
        first_name=request.first_name,
        surname=request.surname,
        gender=request.gender,
        suffix=request.suffix,
        gramps_id=request.gramps_id,
    )

    result = await connector.create_person(person_data)
    if result is None:
        raise HTTPException(status_code=500, detail="Failed to create person")

    # Gramps API returns minimal data on create, fetch full person
    handle = result.get("handle", "")
    if handle:
        full_person = await connector.get_person(handle)
        if full_person:
            first_name, surname = connector.extract_person_name(full_person)
            return CreatePersonResponse(
                handle=handle,
                gramps_id=full_person.get("gramps_id", ""),
                first_name=first_name,
                surname=surname,
            )

    # Fallback to original data if fetch fails
    first_name, surname = connector.extract_person_name(result)
    return CreatePersonResponse(
        handle=handle,
        gramps_id=result.get("gramps_id", ""),
        first_name=first_name,
        surname=surname,
    )
