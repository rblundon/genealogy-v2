"""Person sync service for managing extracted persons and syncing to Gramps."""

import logging
from dataclasses import dataclass, field
from typing import Optional
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from models import ExtractedFact, PersonResolution, GrampsRecordMapping
from services.gramps_connector import GrampsConnector, get_gramps_connector
from services.person_matcher import PersonMatcher, get_person_matcher, MatchCandidate

logger = logging.getLogger(__name__)


def parse_name(full_name: str) -> tuple:
    """
    Parse a full name into (first, middle, last, suffix).
    """
    if not full_name:
        return (None, None, None, None)

    parts = full_name.strip().split()
    if not parts:
        return (None, None, None, None)

    suffixes = ['Jr.', 'Jr', 'Sr.', 'Sr', 'II', 'III', 'IV', 'V']
    suffix = None
    if len(parts) > 1 and parts[-1] in suffixes:
        suffix = parts.pop()

    if len(parts) == 1:
        return (parts[0], None, None, suffix)
    elif len(parts) == 2:
        return (parts[0], None, parts[1], suffix)
    else:
        return (parts[0], ' '.join(parts[1:-1]), parts[-1], suffix)


def format_name_last_first(full_name: str) -> str:
    """Format name as 'Last, First M.'"""
    first, middle, last, suffix = parse_name(full_name)
    if not last:
        return first or full_name
    result = last
    if first:
        result += f", {first}"
    if middle:
        result += f" {middle[0]}."
    if suffix:
        result += f" {suffix}"
    return result


@dataclass
class PersonSummary:
    """Summary of a person across all obituaries."""
    id: int  # We'll use hash of subject_name as ID
    name: str
    name_formatted: str
    first_name: Optional[str]
    middle_name: Optional[str]
    last_name: Optional[str]
    primary_role: str
    obituary_count: int
    fact_count: int
    resolved_count: int
    unresolved_count: int
    gramps_handle: Optional[str] = None
    gramps_id: Optional[str] = None
    sync_status: str = 'pending'  # pending, matched, created, skipped


@dataclass
class ObituaryFacts:
    """Facts from a single obituary for a person."""
    obituary_id: int
    obituary_url: str
    role: str
    facts: list[dict]


@dataclass
class PersonDetail:
    """Detailed person info with facts grouped by obituary."""
    id: int
    name: str
    name_formatted: str
    first_name: Optional[str]
    middle_name: Optional[str]
    last_name: Optional[str]
    gramps_handle: Optional[str]
    gramps_id: Optional[str]
    sync_status: str
    obituary_facts: list[ObituaryFacts] = field(default_factory=list)


@dataclass
class GrampsMatch:
    """A potential Gramps match for linking."""
    handle: str
    gramps_id: str
    name: str
    first_name: str
    surname: str
    score: float
    match_details: dict


@dataclass
class SyncResult:
    """Result of syncing a person to Gramps."""
    success: bool
    person_name: str
    gramps_handle: Optional[str] = None
    gramps_id: Optional[str] = None
    action: str = ''  # 'created', 'linked', 'skipped'
    error: Optional[str] = None
    events_created: int = 0
    families_created: int = 0


class PersonSyncService:
    """Service for managing extracted persons and syncing to Gramps."""

    def __init__(
        self,
        db: Session,
        gramps_connector: Optional[GrampsConnector] = None,
        person_matcher: Optional[PersonMatcher] = None
    ):
        self.db = db
        self.gramps = gramps_connector or get_gramps_connector()
        self.matcher = person_matcher or get_person_matcher()

    def get_all_persons(self) -> list[PersonSummary]:
        """
        Get all unique persons across all obituaries.
        Includes both subject_name and related_name to capture all mentioned persons.
        Returns list sorted alphabetically by last name.
        """
        # Get distinct subject names with aggregated info
        subjects_query = self.db.query(
            ExtractedFact.subject_name,
            ExtractedFact.subject_role,
            func.count(distinct(ExtractedFact.obituary_cache_id)).label('obituary_count'),
            func.count(ExtractedFact.id).label('fact_count'),
            func.sum(
                func.IF(ExtractedFact.resolution_status == 'resolved', 1, 0)
            ).label('resolved_count'),
            func.sum(
                func.IF(ExtractedFact.resolution_status == 'unresolved', 1, 0)
            ).label('unresolved_count'),
        ).group_by(
            ExtractedFact.subject_name
        ).all()

        # Also get unique persons from related_name (e.g., spouses, deceased relatives)
        # These are people mentioned in relationships who may not have their own facts
        related_query = self.db.query(
            ExtractedFact.related_name,
            ExtractedFact.relationship_type,
            func.count(distinct(ExtractedFact.obituary_cache_id)).label('obituary_count'),
            func.count(ExtractedFact.id).label('fact_count'),
        ).filter(
            ExtractedFact.related_name.isnot(None),
            ExtractedFact.related_name != ''
        ).group_by(
            ExtractedFact.related_name
        ).all()

        # Build a set of subject names for deduplication
        subject_names = {row.subject_name for row in subjects_query}

        # Convert related persons that aren't already subjects
        related_persons = []
        for row in related_query:
            if row.related_name not in subject_names:
                # Infer role from relationship_type
                role = self._infer_role_from_relationship(row.relationship_type)
                related_persons.append((
                    row.related_name,
                    role,
                    row.obituary_count,
                    row.fact_count,
                    0,  # resolved_count
                    0   # unresolved_count
                ))

        # Combine both lists
        persons_query = list(subjects_query)

        results = []

        # Process subject-based persons
        for row in persons_query:
            name = row.subject_name
            first, middle, last, suffix = parse_name(name)

            # Check if any PersonResolution exists with a gramps_handle
            resolution = self.db.query(PersonResolution).filter(
                PersonResolution.extracted_name == name,
                PersonResolution.gramps_handle.isnot(None)
            ).first()

            gramps_handle = resolution.gramps_handle if resolution else None
            gramps_id = resolution.gramps_id if resolution else None
            sync_status = resolution.status if resolution else 'pending'

            # Generate a stable ID from the name (hash)
            person_id = hash(name) & 0x7FFFFFFF  # Positive int

            results.append(PersonSummary(
                id=person_id,
                name=name,
                name_formatted=format_name_last_first(name),
                first_name=first,
                middle_name=middle,
                last_name=last,
                primary_role=row.subject_role or 'other',
                obituary_count=row.obituary_count,
                fact_count=row.fact_count,
                resolved_count=int(row.resolved_count or 0),
                unresolved_count=int(row.unresolved_count or 0),
                gramps_handle=gramps_handle,
                gramps_id=gramps_id,
                sync_status=sync_status,
            ))

        # Process related-only persons (those mentioned only in relationships)
        for name, role, obit_count, fact_count, resolved, unresolved in related_persons:
            first, middle, last, suffix = parse_name(name)

            resolution = self.db.query(PersonResolution).filter(
                PersonResolution.extracted_name == name,
                PersonResolution.gramps_handle.isnot(None)
            ).first()

            gramps_handle = resolution.gramps_handle if resolution else None
            gramps_id = resolution.gramps_id if resolution else None
            sync_status = resolution.status if resolution else 'pending'

            person_id = hash(name) & 0x7FFFFFFF

            results.append(PersonSummary(
                id=person_id,
                name=name,
                name_formatted=format_name_last_first(name),
                first_name=first,
                middle_name=middle,
                last_name=last,
                primary_role=role,
                obituary_count=obit_count,
                fact_count=fact_count,
                resolved_count=resolved,
                unresolved_count=unresolved,
                gramps_handle=gramps_handle,
                gramps_id=gramps_id,
                sync_status=sync_status,
            ))

        # Sort by last name, then first name
        results.sort(key=lambda x: (
            (x.last_name or '').lower(),
            (x.first_name or '').lower()
        ))

        return results

    def _infer_role_from_relationship(self, relationship_type: Optional[str]) -> str:
        """Infer person's role from relationship type."""
        if not relationship_type:
            return 'other'

        role_map = {
            'husband': 'spouse',
            'wife': 'spouse',
            'spouse': 'spouse',
            'father': 'parent',
            'mother': 'parent',
            'son': 'child',
            'daughter': 'child',
            'brother': 'sibling',
            'sister': 'sibling',
            'grandfather': 'grandparent',
            'grandmother': 'grandparent',
            'grandson': 'grandchild',
            'granddaughter': 'grandchild',
            'great_grandfather': 'grandparent',
            'great_grandmother': 'grandparent',
            'brother_in_law': 'in_law',
            'sister_in_law': 'in_law',
            'son_in_law': 'in_law',
            'daughter_in_law': 'in_law',
        }
        return role_map.get(relationship_type, 'other')

    def get_person_by_name(self, name: str) -> Optional[PersonDetail]:
        """
        Get detailed person info with facts grouped by obituary.
        Includes facts where person is subject OR mentioned as related_name.
        """
        from models import ObituaryCache
        from sqlalchemy import or_

        # Get all facts where this person is subject
        subject_facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.subject_name == name
        ).all()

        # Get all facts where this person is mentioned as related_name
        related_facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.related_name == name
        ).all()

        if not subject_facts and not related_facts:
            return None

        first, middle, last, suffix = parse_name(name)

        # Check for Gramps handle
        resolution = self.db.query(PersonResolution).filter(
            PersonResolution.extracted_name == name,
            PersonResolution.gramps_handle.isnot(None)
        ).first()

        gramps_handle = resolution.gramps_handle if resolution else None
        gramps_id = resolution.gramps_id if resolution else None
        sync_status = resolution.status if resolution else 'pending'

        # Group facts by obituary
        obituary_facts_map: dict[int, ObituaryFacts] = {}

        # Track seen relationships to avoid duplicates
        # Key: (obituary_id, related_name, relationship_type)
        seen_relationships: set[tuple[int, str, str]] = set()

        # Determine primary role from subject facts
        primary_role = 'other'
        if subject_facts:
            primary_role = subject_facts[0].subject_role or 'other'
        elif related_facts:
            # Infer role from relationship
            rel_type = related_facts[0].relationship_type
            primary_role = self._infer_role_from_relationship(rel_type)

        # Process facts where person is subject
        for fact in subject_facts:
            obit_id = fact.obituary_cache_id
            if obit_id not in obituary_facts_map:
                obit = self.db.query(ObituaryCache).filter(
                    ObituaryCache.id == obit_id
                ).first()

                obituary_facts_map[obit_id] = ObituaryFacts(
                    obituary_id=obit_id,
                    obituary_url=obit.url if obit else '',
                    role=fact.subject_role or primary_role,
                    facts=[]
                )

            # For relationship facts, reverse the type to show subject's role
            # e.g., Maxine→daughter→Patricia means "Patricia is Maxine's daughter"
            # Display as: "mother of Patricia" (Maxine is mother of Patricia)
            if fact.fact_type == 'relationship' and fact.relationship_type:
                fact_dict = fact.to_dict()
                reversed_type = self._reverse_relationship(fact.relationship_type)
                fact_dict['fact_value'] = reversed_type
                fact_dict['relationship_type'] = reversed_type

                # Track this relationship to avoid duplicates from derived facts
                rel_key = (obit_id, fact.related_name or '', reversed_type)
                if rel_key not in seen_relationships:
                    seen_relationships.add(rel_key)
                    obituary_facts_map[obit_id].facts.append(fact_dict)
            else:
                obituary_facts_map[obit_id].facts.append(fact.to_dict())

        # Process facts where person is mentioned in relationship
        for fact in related_facts:
            obit_id = fact.obituary_cache_id
            if obit_id not in obituary_facts_map:
                obit = self.db.query(ObituaryCache).filter(
                    ObituaryCache.id == obit_id
                ).first()

                obituary_facts_map[obit_id] = ObituaryFacts(
                    obituary_id=obit_id,
                    obituary_url=obit.url if obit else '',
                    role=self._infer_role_from_relationship(fact.relationship_type),
                    facts=[]
                )

            # Create a derived fact representation for the related person
            # relationship_type describes what SUBJECT is to RELATED
            # e.g., Ryan→wife→Amy means "Amy is wife of Ryan"
            # For Amy's view: subject=Amy, relationship_type=wife, related=Ryan
            # This displays as "wife of Ryan" (Amy is wife of Ryan)

            # Check if we already have this relationship from direct facts
            rel_key = (obit_id, fact.subject_name or '', fact.relationship_type or '')
            if rel_key in seen_relationships:
                # Skip duplicate relationship
                continue

            seen_relationships.add(rel_key)

            derived_fact = {
                'id': fact.id,
                'obituary_cache_id': obit_id,
                'fact_type': 'relationship',
                'subject_name': name,
                'subject_role': self._infer_role_from_relationship(fact.relationship_type),
                'fact_value': fact.relationship_type,  # Keep original - describes what subject IS
                'related_name': fact.subject_name,
                'relationship_type': fact.relationship_type,  # Keep original - describes what subject IS
                'extracted_context': fact.extracted_context,
                'is_inferred': True,
                'inference_basis': f'Derived from: {fact.subject_name} has {fact.relationship_type} {name}',
                'confidence_score': fact.confidence_score,
                'resolution_status': fact.resolution_status,
            }
            obituary_facts_map[obit_id].facts.append(derived_fact)

        person_id = hash(name) & 0x7FFFFFFF

        return PersonDetail(
            id=person_id,
            name=name,
            name_formatted=format_name_last_first(name),
            first_name=first,
            middle_name=middle,
            last_name=last,
            gramps_handle=gramps_handle,
            gramps_id=gramps_id,
            sync_status=sync_status,
            obituary_facts=list(obituary_facts_map.values())
        )

    def _reverse_relationship(self, relationship_type: Optional[str]) -> str:
        """
        Get the reverse of a relationship type.

        Given what B is to A, returns what A is to B.
        e.g., if B is 'daughter' of A, then A is 'parent' of B.
        """
        if not relationship_type:
            return 'related'

        reverse_map = {
            # Spouse relationships
            'husband': 'wife',
            'wife': 'husband',
            'spouse': 'spouse',
            # Parent/child relationships
            'father': 'child',
            'mother': 'child',
            'parent': 'child',
            'son': 'parent',
            'daughter': 'parent',
            'child': 'parent',
            # Sibling relationships
            'brother': 'sibling',
            'sister': 'sibling',
            'sibling': 'sibling',
            # Grandparent/grandchild relationships
            'grandfather': 'grandchild',
            'grandmother': 'grandchild',
            'grandparent': 'grandchild',
            'grandson': 'grandparent',
            'granddaughter': 'grandparent',
            'grandchild': 'grandparent',
            # Great-grandparent relationships
            'great_grandfather': 'great_grandchild',
            'great_grandmother': 'great_grandchild',
            'great_grandparent': 'great_grandchild',
            'great_grandchild': 'great_grandparent',
            # In-law relationships
            'son-in-law': 'parent-in-law',
            'daughter-in-law': 'parent-in-law',
            'son_in_law': 'parent-in-law',
            'daughter_in_law': 'parent-in-law',
            'father-in-law': 'child-in-law',
            'mother-in-law': 'child-in-law',
            'brother-in-law': 'sibling-in-law',
            'sister-in-law': 'sibling-in-law',
            # Aunt/uncle/niece/nephew
            'uncle': 'nephew/niece',
            'aunt': 'nephew/niece',
            'nephew': 'uncle/aunt',
            'niece': 'uncle/aunt',
        }
        return reverse_map.get(relationship_type, relationship_type)

    async def get_gramps_matches(self, name: str) -> list[GrampsMatch]:
        """
        Find potential Gramps matches for a person.
        """
        first, middle, last, suffix = parse_name(name)

        if not first and not last:
            return []

        # Use the matcher to find candidates
        result = await self.matcher.find_matches(
            first_name=first or '',
            surname=last or '',
            max_candidates=10
        )

        matches = []
        for candidate in result.candidates:
            matches.append(GrampsMatch(
                handle=candidate.handle,
                gramps_id=candidate.gramps_id,
                name=f"{candidate.first_name} {candidate.surname}",
                first_name=candidate.first_name,
                surname=candidate.surname,
                score=candidate.score,
                match_details=candidate.match_details
            ))

        return matches

    async def sync_person_to_gramps(
        self,
        name: str,
        gramps_handle: Optional[str] = None,
        create_new: bool = False,
        include_relationships: bool = True
    ) -> SyncResult:
        """
        Sync a person to Gramps.

        Args:
            name: The extracted person name
            gramps_handle: If provided, link to this existing Gramps person
            create_new: If True, create a new Gramps person
            include_relationships: If True, also create family relationships

        Returns:
            SyncResult with status and details
        """
        first, middle, last, suffix = parse_name(name)

        if not gramps_handle and not create_new:
            return SyncResult(
                success=False,
                person_name=name,
                error="Must provide gramps_handle or set create_new=True"
            )

        try:
            if create_new:
                # Create new person in Gramps
                person_data = self.gramps.build_person_data(
                    first_name=f"{first or ''} {middle or ''}".strip(),
                    surname=last or first or name,
                    suffix=suffix or ''
                )

                created = await self.gramps.create_person(person_data)
                if not created:
                    return SyncResult(
                        success=False,
                        person_name=name,
                        error="Failed to create person in Gramps"
                    )

                gramps_handle = created.get('handle')
                gramps_id = created.get('gramps_id')

                # If gramps_id not in create response, fetch the person to get it
                if not gramps_id and gramps_handle:
                    person = await self.gramps.get_person(gramps_handle)
                    if person:
                        gramps_id = person.get('gramps_id')

                action = 'created'

                logger.info(f"Created Gramps person: {gramps_id} ({gramps_handle}) for {name}")
            else:
                # Linking to existing person
                person = await self.gramps.get_person(gramps_handle)
                if not person:
                    return SyncResult(
                        success=False,
                        person_name=name,
                        error=f"Gramps person {gramps_handle} not found"
                    )
                gramps_id = person.get('gramps_id')
                action = 'linked'

                logger.info(f"Linking {name} to existing Gramps person: {gramps_id}")

            # Update PersonResolution records for all obituaries with this name
            self._update_person_resolutions(name, gramps_handle, gramps_id, action)

            # Create events from resolved facts
            events_created = await self._create_events_for_person(name, gramps_handle)

            # Create family relationships if requested
            families_created = 0
            if include_relationships:
                families_created = await self._create_family_relationships(name, gramps_handle)

            return SyncResult(
                success=True,
                person_name=name,
                gramps_handle=gramps_handle,
                gramps_id=gramps_id,
                action=action,
                events_created=events_created,
                families_created=families_created
            )

        except Exception as e:
            logger.error(f"Error syncing {name} to Gramps: {e}")
            return SyncResult(
                success=False,
                person_name=name,
                error=str(e)
            )

    def _update_person_resolutions(
        self,
        name: str,
        gramps_handle: str,
        gramps_id: str,
        action: str
    ) -> None:
        """Update PersonResolution records for a person."""
        # Get all obituaries containing this person
        obituary_ids = self.db.query(distinct(ExtractedFact.obituary_cache_id)).filter(
            ExtractedFact.subject_name == name
        ).all()

        for (obit_id,) in obituary_ids:
            # Find or create PersonResolution
            resolution = self.db.query(PersonResolution).filter(
                PersonResolution.obituary_cache_id == obit_id,
                PersonResolution.extracted_name == name
            ).first()

            if resolution:
                resolution.gramps_handle = gramps_handle
                resolution.gramps_id = gramps_id
                resolution.status = 'committed' if action == 'created' else 'matched'
                resolution.match_method = 'manual' if action == 'linked' else 'created'
            else:
                resolution = PersonResolution(
                    obituary_cache_id=obit_id,
                    extracted_name=name,
                    gramps_handle=gramps_handle,
                    gramps_id=gramps_id,
                    status='committed' if action == 'created' else 'matched',
                    match_method='manual' if action == 'linked' else 'created'
                )
                self.db.add(resolution)

        self.db.commit()

    async def _create_events_for_person(self, name: str, gramps_handle: str) -> int:
        """Create Gramps events from resolved facts for a person."""
        # Get resolved facts that can become events
        event_fact_types = [
            'person_birth_date', 'person_death_date',
            'location_birth', 'location_death', 'location_residence'
        ]

        facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.subject_name == name,
            ExtractedFact.resolution_status == 'resolved',
            ExtractedFact.fact_type.in_(event_fact_types),
            ExtractedFact.gramps_event_id.is_(None)  # Not yet synced
        ).all()

        events_created = 0

        for fact in facts:
            event_type = self._map_fact_type_to_gramps_event(fact.fact_type)
            if not event_type:
                continue

            event_data = {
                'type': event_type,
                'description': fact.extracted_context or fact.fact_value,
            }

            # Add date if applicable
            if 'date' in fact.fact_type.lower():
                event_data['date'] = {'text': fact.fact_value}

            # Add place if applicable
            if 'location' in fact.fact_type.lower():
                event_data['place'] = {'name': fact.fact_value}

            created_event = await self.gramps.create_event(event_data)
            if created_event:
                fact.gramps_event_id = created_event.get('handle')
                fact.gramps_person_id = gramps_handle
                events_created += 1

                # Record mapping
                mapping = GrampsRecordMapping(
                    obituary_cache_id=fact.obituary_cache_id,
                    gramps_record_type='event',
                    gramps_record_id=created_event.get('handle'),
                    extracted_fact_id=fact.id
                )
                self.db.add(mapping)

        self.db.commit()
        return events_created

    def _map_fact_type_to_gramps_event(self, fact_type: str) -> Optional[str]:
        """Map fact type to Gramps event type."""
        mapping = {
            'person_birth_date': 'Birth',
            'person_death_date': 'Death',
            'location_birth': 'Birth',
            'location_death': 'Death',
            'location_residence': 'Residence',
        }
        return mapping.get(fact_type)

    async def _create_family_relationships(self, name: str, gramps_handle: str) -> int:
        """Create family relationships in Gramps."""
        # Get relationship facts for this person
        relationship_facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.subject_name == name,
            ExtractedFact.resolution_status == 'resolved',
            ExtractedFact.fact_type.in_(['relationship', 'marriage', 'survived_by', 'preceded_in_death']),
            ExtractedFact.gramps_family_id.is_(None)  # Not yet synced
        ).all()

        families_created = 0

        for fact in relationship_facts:
            if not fact.related_name:
                continue

            # Check if the related person is also synced to Gramps
            related_resolution = self.db.query(PersonResolution).filter(
                PersonResolution.extracted_name == fact.related_name,
                PersonResolution.gramps_handle.isnot(None)
            ).first()

            if not related_resolution:
                logger.debug(f"Related person {fact.related_name} not synced to Gramps, skipping relationship")
                continue

            related_handle = related_resolution.gramps_handle

            # Determine relationship type and create family
            rel_type = fact.relationship_type or fact.subject_role
            if rel_type in ['spouse', 'wife', 'husband']:
                # Create marriage family
                family_data = {
                    'father_handle': gramps_handle if fact.subject_role != 'spouse' else related_handle,
                    'mother_handle': related_handle if fact.subject_role != 'spouse' else gramps_handle,
                }
                created_family = await self.gramps.create_family(family_data)
                if created_family:
                    fact.gramps_family_id = created_family.get('handle')
                    families_created += 1

                    mapping = GrampsRecordMapping(
                        obituary_cache_id=fact.obituary_cache_id,
                        gramps_record_type='family',
                        gramps_record_id=created_family.get('handle'),
                        extracted_fact_id=fact.id
                    )
                    self.db.add(mapping)

            # For parent/child relationships, we'd need more complex logic
            # to find or create the appropriate family record
            # This is simplified for now

        self.db.commit()
        return families_created


def get_person_sync_service(db: Session) -> PersonSyncService:
    """Factory function to create PersonSyncService."""
    return PersonSyncService(db)
