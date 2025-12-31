"""Resolution service for matching extracted facts to Gramps records."""

import logging
from datetime import datetime
from typing import Optional
from decimal import Decimal

from sqlalchemy.orm import Session

from models.cache_models import (
    ExtractedFact, PersonResolution, FactResolution, ObituaryCache
)
from services.person_matcher import PersonMatcher, get_person_matcher
from services.gramps_connector import GrampsConnector, get_gramps_connector

logger = logging.getLogger(__name__)


class ResolutionService:
    """Service for resolving extracted facts against Gramps database."""

    HIGH_CONFIDENCE_THRESHOLD = 0.85
    MEDIUM_CONFIDENCE_THRESHOLD = 0.60

    def __init__(
        self,
        db: Session,
        matcher: Optional[PersonMatcher] = None,
        connector: Optional[GrampsConnector] = None,
    ):
        self.db = db
        self.matcher = matcher or get_person_matcher()
        self.connector = connector or get_gramps_connector()

    async def resolve_obituary(self, obituary_id: int) -> dict:
        """
        Resolve all extracted facts for an obituary against Gramps.

        1. Collect unique person names from facts
        2. Match each person against Gramps
        3. Create person_resolution entries
        4. Create fact_resolution entries

        Returns:
            Summary of resolution results
        """
        # Get obituary
        obituary = self.db.query(ObituaryCache).filter_by(id=obituary_id).first()
        if not obituary:
            raise ValueError(f"Obituary {obituary_id} not found")

        # Get all facts for this obituary
        facts = self.db.query(ExtractedFact).filter_by(
            obituary_cache_id=obituary_id
        ).all()

        if not facts:
            return {
                "obituary_id": obituary_id,
                "status": "no_facts",
                "persons_resolved": 0,
                "facts_resolved": 0,
            }

        # Step 1: Collect unique person names with their roles
        persons_to_resolve = {}
        for fact in facts:
            # Subject of the fact
            if fact.subject_name and fact.subject_name not in persons_to_resolve:
                persons_to_resolve[fact.subject_name] = {
                    "role": fact.subject_role,
                    "facts": [],
                }
            if fact.subject_name:
                persons_to_resolve[fact.subject_name]["facts"].append(fact)

            # Related person (if any)
            if fact.related_name and fact.related_name not in persons_to_resolve:
                persons_to_resolve[fact.related_name] = {
                    "role": "other",
                    "facts": [],
                }

        # Step 2: Match each person against Gramps
        person_resolutions = {}
        for name, info in persons_to_resolve.items():
            person_res = await self._resolve_person(
                obituary_id=obituary_id,
                name=name,
                role=info["role"],
            )
            person_resolutions[name] = person_res

        # Step 3: Create fact resolutions
        facts_created = 0
        for fact in facts:
            fact_res = await self._resolve_fact(
                fact=fact,
                person_resolutions=person_resolutions,
            )
            if fact_res:
                facts_created += 1

        self.db.commit()

        return {
            "obituary_id": obituary_id,
            "status": "resolved",
            "persons_resolved": len(person_resolutions),
            "facts_resolved": facts_created,
            "persons": [pr.to_dict() for pr in person_resolutions.values()],
        }

    async def _resolve_person(
        self,
        obituary_id: int,
        name: str,
        role: str,
    ) -> PersonResolution:
        """Resolve a single person against Gramps."""
        # Check if already resolved
        existing = self.db.query(PersonResolution).filter_by(
            obituary_cache_id=obituary_id,
            extracted_name=name,
        ).first()

        if existing:
            return existing

        # Parse name
        parts = name.split(maxsplit=1)
        first_name = parts[0] if parts else ""
        surname = parts[1] if len(parts) > 1 else ""

        # Match against Gramps
        match_result = await self.matcher.find_matches(
            first_name=first_name,
            surname=surname,
        )

        # Create resolution record
        resolution = PersonResolution(
            obituary_cache_id=obituary_id,
            extracted_name=name,
            subject_role=role,
        )

        if match_result.best_match:
            resolution.gramps_handle = match_result.best_match.handle
            resolution.gramps_id = match_result.best_match.gramps_id
            resolution.match_score = Decimal(str(match_result.best_match.score))
            resolution.match_method = "exact" if match_result.best_match.score >= 0.99 else "fuzzy"

            if match_result.is_confident_match:
                resolution.status = "matched"
                resolution.resolved_timestamp = datetime.utcnow()
            else:
                resolution.status = "pending"  # Needs review
        else:
            resolution.status = "create_new"
            resolution.resolved_timestamp = datetime.utcnow()

        self.db.add(resolution)
        self.db.flush()  # Get ID

        return resolution

    async def _resolve_fact(
        self,
        fact: ExtractedFact,
        person_resolutions: dict[str, PersonResolution],
    ) -> Optional[FactResolution]:
        """Resolve a single fact."""
        # Check if already resolved
        existing = self.db.query(FactResolution).filter_by(
            extracted_fact_id=fact.id
        ).first()

        if existing:
            return existing

        # Get person resolutions
        subject_res = person_resolutions.get(fact.subject_name)
        related_res = person_resolutions.get(fact.related_name) if fact.related_name else None

        # Create fact resolution
        resolution = FactResolution(
            extracted_fact_id=fact.id,
            person_resolution_id=subject_res.id if subject_res else None,
            related_person_resolution_id=related_res.id if related_res else None,
            action="add",
            status="pending",
        )

        # Check if Gramps already has this value (for matched persons)
        if subject_res and subject_res.gramps_handle:
            gramps_value = await self._get_gramps_value(
                handle=subject_res.gramps_handle,
                fact_type=fact.fact_type,
            )
            if gramps_value is not None:
                resolution.gramps_has_value = True
                resolution.gramps_current_value = str(gramps_value)
                # Check for conflict
                if str(gramps_value) != str(fact.fact_value):
                    resolution.is_conflict = True
                    resolution.action = "update"
                else:
                    resolution.action = "skip"  # Already has same value

        self.db.add(resolution)
        return resolution

    async def _get_gramps_value(self, handle: str, fact_type: str) -> Optional[str]:
        """Get current value from Gramps for a specific fact type."""
        person = await self.connector.get_person(handle)
        if not person:
            return None

        # Map fact types to Gramps person fields
        if fact_type == "person_death_date":
            # Look for death event
            events = person.get("event_ref_list", [])
            for event_ref in events:
                # Would need to fetch event details
                pass
            return None  # TODO: Implement event lookup

        elif fact_type == "person_birth_date":
            return None  # TODO: Implement

        elif fact_type == "person_gender":
            gender = person.get("gender", 2)
            return str(gender)

        return None

    def get_resolution_status(self, obituary_id: int) -> dict:
        """Get resolution status for an obituary."""
        person_resolutions = self.db.query(PersonResolution).filter_by(
            obituary_cache_id=obituary_id
        ).all()

        fact_resolutions = self.db.query(FactResolution).join(
            ExtractedFact
        ).filter(
            ExtractedFact.obituary_cache_id == obituary_id
        ).all()

        return {
            "obituary_id": obituary_id,
            "persons": {
                "total": len(person_resolutions),
                "pending": sum(1 for p in person_resolutions if p.status == "pending"),
                "matched": sum(1 for p in person_resolutions if p.status == "matched"),
                "create_new": sum(1 for p in person_resolutions if p.status == "create_new"),
                "committed": sum(1 for p in person_resolutions if p.status == "committed"),
            },
            "facts": {
                "total": len(fact_resolutions),
                "pending": sum(1 for f in fact_resolutions if f.status == "pending"),
                "approved": sum(1 for f in fact_resolutions if f.status == "approved"),
                "rejected": sum(1 for f in fact_resolutions if f.status == "rejected"),
                "committed": sum(1 for f in fact_resolutions if f.status == "committed"),
                "conflicts": sum(1 for f in fact_resolutions if f.is_conflict),
            },
            "person_details": [p.to_dict() for p in person_resolutions],
            "fact_details": [
                {
                    **f.to_dict(),
                    "fact": f.extracted_fact.to_dict() if f.extracted_fact else None,
                }
                for f in fact_resolutions
            ],
        }

    def update_person_resolution(
        self,
        resolution_id: int,
        status: Optional[str] = None,
        gramps_handle: Optional[str] = None,
        modified_first_name: Optional[str] = None,
        modified_surname: Optional[str] = None,
        modified_gender: Optional[int] = None,
    ) -> PersonResolution:
        """Update a person resolution (user action)."""
        resolution = self.db.query(PersonResolution).filter_by(id=resolution_id).first()
        if not resolution:
            raise ValueError(f"PersonResolution {resolution_id} not found")

        if status:
            resolution.status = status
            resolution.resolved_timestamp = datetime.utcnow()

        if gramps_handle is not None:
            resolution.gramps_handle = gramps_handle
            resolution.match_method = "manual"

        if any([modified_first_name, modified_surname, modified_gender is not None]):
            resolution.user_modified = True
            if modified_first_name:
                resolution.modified_first_name = modified_first_name
            if modified_surname:
                resolution.modified_surname = modified_surname
            if modified_gender is not None:
                resolution.modified_gender = modified_gender

        self.db.commit()
        return resolution

    def update_fact_resolution(
        self,
        resolution_id: int,
        action: Optional[str] = None,
        status: Optional[str] = None,
        modified_value: Optional[str] = None,
    ) -> FactResolution:
        """Update a fact resolution (user action)."""
        resolution = self.db.query(FactResolution).filter_by(id=resolution_id).first()
        if not resolution:
            raise ValueError(f"FactResolution {resolution_id} not found")

        if action:
            resolution.action = action

        if status:
            resolution.status = status
            if status == "approved":
                resolution.approved_timestamp = datetime.utcnow()

        if modified_value is not None:
            resolution.user_modified = True
            resolution.modified_value = modified_value

        self.db.commit()
        return resolution

    def approve_all_pending(self, obituary_id: int) -> int:
        """Approve all pending fact resolutions for an obituary."""
        # Get fact IDs for this obituary
        fact_ids = self.db.query(ExtractedFact.id).filter(
            ExtractedFact.obituary_cache_id == obituary_id
        ).subquery()

        # Update fact resolutions
        count = self.db.query(FactResolution).filter(
            FactResolution.extracted_fact_id.in_(fact_ids),
            FactResolution.status == "pending",
            FactResolution.action.in_(["add", "update"]),
        ).update(
            {
                "status": "approved",
                "approved_timestamp": datetime.utcnow(),
            },
            synchronize_session=False
        )
        self.db.commit()
        return count
