"""Commit service for applying approved resolutions to Gramps Web."""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from models.cache_models import (
    ExtractedFact, PersonResolution, FactResolution,
    GrampsCommitBatch, GrampsRecordMapping
)
from services.gramps_connector import GrampsConnector, get_gramps_connector

logger = logging.getLogger(__name__)


class CommitService:
    """Service for committing approved resolutions to Gramps Web."""

    def __init__(
        self,
        db: Session,
        connector: Optional[GrampsConnector] = None,
    ):
        self.db = db
        self.connector = connector or get_gramps_connector()

    async def commit_obituary(self, obituary_id: int) -> GrampsCommitBatch:
        """
        Commit all approved resolutions for an obituary to Gramps.

        Execution order:
        1. Create new persons (get handles)
        2. Update existing persons
        3. Create families for relationships
        4. Add events (birth, death, etc.)

        Returns:
            GrampsCommitBatch with results
        """
        # Create batch record
        batch = GrampsCommitBatch(
            obituary_cache_id=obituary_id,
            status="in_progress",
            started_timestamp=datetime.utcnow(),
        )
        self.db.add(batch)
        self.db.flush()

        try:
            # Step 1: Create new persons
            persons_created = await self._create_new_persons(obituary_id)
            batch.persons_created = persons_created

            # Step 2: Commit approved facts
            facts_committed = await self._commit_facts(obituary_id)
            batch.facts_committed = facts_committed

            # Step 3: Create families (relationships)
            families_created = await self._create_families(obituary_id)
            batch.families_created = families_created

            batch.status = "completed"
            batch.completed_timestamp = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error committing obituary {obituary_id}: {e}")
            batch.status = "failed"
            batch.error_message = str(e)
            batch.completed_timestamp = datetime.utcnow()

        self.db.commit()
        return batch

    async def _create_new_persons(self, obituary_id: int) -> int:
        """Create new persons in Gramps for 'create_new' resolutions."""
        resolutions = self.db.query(PersonResolution).filter_by(
            obituary_cache_id=obituary_id,
            status="create_new",
        ).all()

        created = 0
        for res in resolutions:
            # Parse name
            if res.user_modified and res.modified_first_name:
                first_name = res.modified_first_name
                surname = res.modified_surname or ""
            else:
                parts = res.extracted_name.split(maxsplit=1)
                first_name = parts[0] if parts else ""
                surname = parts[1] if len(parts) > 1 else ""

            # Determine gender
            gender = 2  # Unknown
            if res.user_modified and res.modified_gender is not None:
                gender = res.modified_gender
            elif res.subject_role in ("spouse",):
                # Could infer from relationship context
                pass

            # Create in Gramps
            person_data = self.connector.build_person_data(
                first_name=first_name,
                surname=surname,
                gender=gender,
            )

            result = await self.connector.create_person(person_data)
            if result:
                # Update resolution with new handle
                res.gramps_handle = result.get("handle")
                res.gramps_id = result.get("gramps_id")
                res.status = "committed"
                res.committed_timestamp = datetime.utcnow()
                res.match_method = "created"

                # Add to mapping
                mapping = GrampsRecordMapping(
                    obituary_cache_id=obituary_id,
                    gramps_record_type="person",
                    gramps_record_id=res.gramps_handle,
                )
                self.db.add(mapping)

                created += 1
                logger.info(f"Created person {first_name} {surname} -> {res.gramps_id}")

        self.db.flush()
        return created

    async def _commit_facts(self, obituary_id: int) -> int:
        """Commit approved facts to Gramps."""
        # Get approved fact resolutions
        fact_resolutions = self.db.query(FactResolution).join(
            ExtractedFact
        ).filter(
            ExtractedFact.obituary_cache_id == obituary_id,
            FactResolution.status == "approved",
            FactResolution.action.in_(["add", "update"]),
        ).all()

        committed = 0
        for fact_res in fact_resolutions:
            fact = fact_res.extracted_fact
            person_res = fact_res.person_resolution

            if not person_res or not person_res.gramps_handle:
                logger.warning(f"No Gramps handle for fact {fact.id}, skipping")
                continue

            # Get value to commit
            value = fact_res.modified_value if fact_res.user_modified else fact.fact_value

            # Commit based on fact type
            success = await self._commit_fact_to_gramps(
                handle=person_res.gramps_handle,
                fact_type=fact.fact_type,
                value=value,
                fact=fact,
            )

            if success:
                fact_res.status = "committed"
                fact_res.committed_timestamp = datetime.utcnow()
                fact.resolution_status = "resolved"
                fact.resolved_timestamp = datetime.utcnow()
                committed += 1

        self.db.flush()
        return committed

    async def _commit_fact_to_gramps(
        self,
        handle: str,
        fact_type: str,
        value: str,
        fact: ExtractedFact,
    ) -> bool:
        """Commit a single fact to Gramps."""
        # Get current person data
        person = await self.connector.get_person(handle)
        if not person:
            logger.error(f"Person {handle} not found in Gramps")
            return False

        # Handle different fact types
        if fact_type == "person_death_date":
            # Create death event
            event = await self._create_event(
                event_type="Death",
                date_str=value,
                person_handle=handle,
            )
            if event:
                fact.gramps_event_id = event.get("handle")
                return True

        elif fact_type == "person_birth_date":
            event = await self._create_event(
                event_type="Birth",
                date_str=value,
                person_handle=handle,
            )
            if event:
                fact.gramps_event_id = event.get("handle")
                return True

        elif fact_type == "person_gender":
            # Update person gender
            gender_map = {"male": 1, "female": 0, "m": 1, "f": 0}
            gender = gender_map.get(value.lower(), 2)
            person["gender"] = gender
            result = await self.connector.update_person(handle, person)
            return result is not None

        elif fact_type == "maiden_name":
            # Add alternate name
            # TODO: Implement adding maiden name to person
            logger.info(f"Would add maiden name {value} to {handle}")
            return True

        elif fact_type in ("location_birth", "location_death", "location_residence"):
            # TODO: Add place reference
            logger.info(f"Would add location {value} to {handle}")
            return True

        # For relationship facts, handled in _create_families
        elif fact_type in ("relationship", "survived_by", "preceded_in_death"):
            return True  # Will be handled by family creation

        logger.warning(f"Unhandled fact type: {fact_type}")
        return False

    async def _create_event(
        self,
        event_type: str,
        date_str: str,
        person_handle: str,
    ) -> Optional[dict]:
        """Create an event in Gramps and link to person."""
        # Parse date string to Gramps date format
        date_obj = self._parse_date(date_str)
        if not date_obj:
            logger.warning(f"Could not parse date: {date_str}")
            return None

        event_data = {
            "type": {"_class": "EventType", "string": event_type},
            "date": date_obj,
        }

        event = await self.connector.create_event(event_data)
        if event:
            # Link event to person
            event_handle = event.get("handle")
            person = await self.connector.get_person(person_handle)
            if person:
                event_ref_list = person.get("event_ref_list", [])
                event_ref_list.append({
                    "ref": event_handle,
                    "role": {"_class": "EventRoleType", "string": "Primary"},
                })
                person["event_ref_list"] = event_ref_list
                await self.connector.update_person(person_handle, person)

            return event
        return None

    def _parse_date(self, date_str: str) -> Optional[dict]:
        """Parse date string to Gramps date object format."""
        # Gramps date format
        try:
            # Try common formats
            from datetime import datetime as dt

            for fmt in ["%Y-%m-%d", "%B %d, %Y", "%m/%d/%Y", "%d %B %Y"]:
                try:
                    parsed = dt.strptime(date_str, fmt)
                    return {
                        "_class": "Date",
                        "dateval": [parsed.day, parsed.month, parsed.year, False],
                        "modifier": 0,
                        "quality": 0,
                    }
                except ValueError:
                    continue

            # Try year only
            if date_str.isdigit() and len(date_str) == 4:
                return {
                    "_class": "Date",
                    "dateval": [0, 0, int(date_str), False],
                    "modifier": 0,
                    "quality": 0,
                }

        except Exception as e:
            logger.error(f"Error parsing date {date_str}: {e}")

        return None

    async def _create_families(self, obituary_id: int) -> int:
        """Create family relationships in Gramps."""
        # Get relationship facts that are approved
        relationship_facts = self.db.query(FactResolution).join(
            ExtractedFact
        ).filter(
            ExtractedFact.obituary_cache_id == obituary_id,
            FactResolution.status.in_(["approved", "committed"]),
            ExtractedFact.fact_type.in_(["relationship", "survived_by", "preceded_in_death"]),
        ).all()

        created = 0
        processed_pairs = set()

        for fact_res in relationship_facts:
            fact = fact_res.extracted_fact

            # Get both person handles
            subject_res = fact_res.person_resolution
            related_res = fact_res.related_person_resolution

            if not subject_res or not related_res:
                continue
            if not subject_res.gramps_handle or not related_res.gramps_handle:
                continue

            # Avoid duplicates
            pair_key = tuple(sorted([subject_res.gramps_handle, related_res.gramps_handle]))
            if pair_key in processed_pairs:
                continue

            rel_type = fact.relationship_type or ""

            # Handle spouse relationships
            if rel_type.lower() in ("spouse", "husband", "wife"):
                family = await self._create_spouse_family(
                    person1_handle=subject_res.gramps_handle,
                    person2_handle=related_res.gramps_handle,
                    obituary_id=obituary_id,
                )
                if family:
                    created += 1
                    processed_pairs.add(pair_key)

            # Handle parent-child relationships
            elif rel_type.lower() in ("parent", "father", "mother", "child", "son", "daughter"):
                family = await self._create_parent_child_family(
                    parent_handle=subject_res.gramps_handle if rel_type.lower() in ("parent", "father", "mother") else related_res.gramps_handle,
                    child_handle=related_res.gramps_handle if rel_type.lower() in ("parent", "father", "mother") else subject_res.gramps_handle,
                    obituary_id=obituary_id,
                )
                if family:
                    created += 1
                    processed_pairs.add(pair_key)

        return created

    async def _create_spouse_family(
        self,
        person1_handle: str,
        person2_handle: str,
        obituary_id: int,
    ) -> Optional[dict]:
        """Create a family for spouses."""
        # Check if family already exists
        existing_families = await self.connector.get_all_families()
        for fam in existing_families:
            father = fam.get("father_handle")
            mother = fam.get("mother_handle")
            if {father, mother} == {person1_handle, person2_handle}:
                logger.info(f"Family already exists for {person1_handle} and {person2_handle}")
                return fam

        # Determine which is father/mother based on gender
        person1 = await self.connector.get_person(person1_handle)
        person2 = await self.connector.get_person(person2_handle)

        if person1.get("gender") == 1:  # Male
            father_handle, mother_handle = person1_handle, person2_handle
        else:
            father_handle, mother_handle = person2_handle, person1_handle

        family_data = {
            "father_handle": father_handle,
            "mother_handle": mother_handle,
            "child_ref_list": [],
        }

        family = await self.connector.create_family(family_data)
        if family:
            # Add mapping if not already exists
            family_handle = family.get("handle")
            existing_mapping = self.db.query(GrampsRecordMapping).filter_by(
                obituary_cache_id=obituary_id,
                gramps_record_type="family",
                gramps_record_id=family_handle,
            ).first()
            if not existing_mapping:
                mapping = GrampsRecordMapping(
                    obituary_cache_id=obituary_id,
                    gramps_record_type="family",
                    gramps_record_id=family_handle,
                )
                self.db.add(mapping)
            logger.info(f"Created family for spouses: {family.get('gramps_id')}")

        return family

    async def _create_parent_child_family(
        self,
        parent_handle: str,
        child_handle: str,
        obituary_id: int,
    ) -> Optional[dict]:
        """Create or update a family for parent-child relationship."""
        # Get parent's gender
        parent = await self.connector.get_person(parent_handle)
        is_father = parent.get("gender") == 1

        # Look for existing family where this parent is father/mother
        existing_families = await self.connector.get_all_families()
        for fam in existing_families:
            parent_key = "father_handle" if is_father else "mother_handle"
            if fam.get(parent_key) == parent_handle:
                # Add child to this family
                child_refs = fam.get("child_ref_list", [])
                if not any(ref.get("ref") == child_handle for ref in child_refs):
                    child_refs.append({
                        "ref": child_handle,
                        "_class": "ChildRef",
                    })
                    fam["child_ref_list"] = child_refs
                    # TODO: Update family in Gramps
                    logger.info(f"Would add child {child_handle} to existing family")
                return fam

        # Create new family
        family_data = {
            "father_handle": parent_handle if is_father else None,
            "mother_handle": parent_handle if not is_father else None,
            "child_ref_list": [{
                "ref": child_handle,
                "_class": "ChildRef",
            }],
        }

        family = await self.connector.create_family(family_data)
        if family:
            # Add mapping if not already exists
            family_handle = family.get("handle")
            existing_mapping = self.db.query(GrampsRecordMapping).filter_by(
                obituary_cache_id=obituary_id,
                gramps_record_type="family",
                gramps_record_id=family_handle,
            ).first()
            if not existing_mapping:
                mapping = GrampsRecordMapping(
                    obituary_cache_id=obituary_id,
                    gramps_record_type="family",
                    gramps_record_id=family_handle,
                )
                self.db.add(mapping)
            logger.info(f"Created parent-child family: {family.get('gramps_id')}")

        return family

    def get_commit_status(self, obituary_id: int) -> Optional[dict]:
        """Get the latest commit batch status for an obituary."""
        batch = self.db.query(GrampsCommitBatch).filter_by(
            obituary_cache_id=obituary_id
        ).order_by(GrampsCommitBatch.created_timestamp.desc()).first()

        if not batch:
            return None

        return {
            "batch_id": batch.id,
            "status": batch.status,
            "persons_created": batch.persons_created,
            "persons_updated": batch.persons_updated,
            "families_created": batch.families_created,
            "events_created": batch.events_created,
            "facts_committed": batch.facts_committed,
            "error_message": batch.error_message,
            "started": batch.started_timestamp.isoformat() if batch.started_timestamp else None,
            "completed": batch.completed_timestamp.isoformat() if batch.completed_timestamp else None,
        }
