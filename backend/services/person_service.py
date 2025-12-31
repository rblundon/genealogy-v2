# FILE: backend/services/person_service.py
# Service for managing canonical Person records
# ============================================================================

import re
import logging
from typing import Optional, Tuple
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Person, ObituaryCache

logger = logging.getLogger(__name__)


def parse_name(full_name: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Parse a full name into first, middle, last, suffix components.

    Returns: (first_name, middle_name, last_name, suffix)
    """
    if not full_name:
        return None, None, None, None

    # Common suffixes
    suffix_pattern = r'\b(Jr\.?|Sr\.?|III|II|IV|Esq\.?|MD|PhD)\s*$'
    suffix = None
    suffix_match = re.search(suffix_pattern, full_name, re.IGNORECASE)
    if suffix_match:
        suffix = suffix_match.group(1)
        full_name = full_name[:suffix_match.start()].strip()

    # Handle "Last, First Middle" format
    if ',' in full_name:
        parts = full_name.split(',', 1)
        last_name = parts[0].strip()
        first_middle = parts[1].strip() if len(parts) > 1 else ''
        first_middle_parts = first_middle.split()
        first_name = first_middle_parts[0] if first_middle_parts else None
        middle_name = ' '.join(first_middle_parts[1:]) if len(first_middle_parts) > 1 else None
    else:
        # Handle "First Middle Last" format
        parts = full_name.split()
        if len(parts) == 1:
            first_name = parts[0]
            middle_name = None
            last_name = None
        elif len(parts) == 2:
            first_name = parts[0]
            middle_name = None
            last_name = parts[1]
        else:
            first_name = parts[0]
            last_name = parts[-1]
            middle_name = ' '.join(parts[1:-1]) if len(parts) > 2 else None

    return first_name, middle_name, last_name, suffix


def normalize_name(name: str) -> str:
    """Normalize a name for comparison (lowercase, remove extra spaces)."""
    if not name:
        return ''
    return ' '.join(name.lower().split())


class PersonService:
    """
    Service for managing canonical Person records.

    Key responsibilities:
    - Create/find Person records
    - Enforce immutable deceased flag
    - Link obituaries to primary deceased persons
    """

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_person(
        self,
        full_name: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        middle_name: Optional[str] = None,
        suffix: Optional[str] = None
    ) -> Tuple[Person, bool]:
        """
        Find an existing person or create a new one.

        Name matching is case-insensitive.

        Returns: (person, created) where created is True if new person was created
        """
        # Parse name if components not provided
        if not first_name and not last_name:
            first_name, middle_name, last_name, suffix = parse_name(full_name)

        # Try to find existing person by full name (case-insensitive)
        normalized = normalize_name(full_name)
        existing = self.db.query(Person).filter(
            func.lower(Person.full_name) == normalized
        ).first()

        if existing:
            logger.debug(f"Found existing person: {existing.full_name} (id={existing.id})")
            return existing, False

        # Create new person
        person = Person(
            full_name=full_name,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            suffix=suffix
        )
        self.db.add(person)
        self.db.flush()  # Get ID without committing

        logger.info(f"Created new person: {person.full_name} (id={person.id})")
        return person, True

    def find_person_by_name(self, name: str) -> Optional[Person]:
        """Find a person by name (case-insensitive)."""
        normalized = normalize_name(name)
        return self.db.query(Person).filter(
            func.lower(Person.full_name) == normalized
        ).first()

    def mark_deceased(
        self,
        person_id: int,
        source_obituary_id: int,
        deceased_date: Optional[date] = None
    ) -> bool:
        """
        Mark a person as deceased.

        IMPORTANT: This is an IMMUTABLE operation.
        Once is_deceased is True, it cannot be set back to False.

        Args:
            person_id: ID of the person
            source_obituary_id: ID of the obituary that indicates they're deceased
            deceased_date: Optional date of death

        Returns: True if the person was updated, False if already deceased
        """
        person = self.db.query(Person).filter(Person.id == person_id).first()
        if not person:
            logger.warning(f"Person not found: id={person_id}")
            return False

        if person.is_deceased:
            # Already deceased - don't change anything
            logger.debug(f"Person already marked deceased: {person.full_name}")
            return False

        # Mark as deceased
        person.is_deceased = True
        person.deceased_source_obituary_id = source_obituary_id
        if deceased_date:
            person.deceased_date = deceased_date

        logger.info(f"Marked person as deceased: {person.full_name} (source obituary={source_obituary_id})")
        return True

    def link_obituary(self, person_id: int, obituary_id: int) -> bool:
        """
        Link an obituary as this person's primary obituary.

        This indicates that the obituary is ABOUT this person (they are the primary deceased).

        Args:
            person_id: ID of the person
            obituary_id: ID of their obituary

        Returns: True if linked successfully
        """
        person = self.db.query(Person).filter(Person.id == person_id).first()
        if not person:
            logger.warning(f"Person not found: id={person_id}")
            return False

        if person.primary_obituary_id:
            logger.warning(
                f"Person {person.full_name} already has obituary linked "
                f"(existing={person.primary_obituary_id}, new={obituary_id})"
            )
            # Allow overwriting for now
            pass

        person.primary_obituary_id = obituary_id
        logger.info(f"Linked obituary {obituary_id} to person: {person.full_name}")
        return True

    def update_gender(self, person_id: int, gender: str) -> bool:
        """
        Update a person's gender.

        Only updates if current gender is 'unknown'.

        Args:
            person_id: ID of the person
            gender: 'male', 'female', or 'unknown'

        Returns: True if updated
        """
        if gender not in ('male', 'female', 'unknown'):
            logger.warning(f"Invalid gender value: {gender}")
            return False

        person = self.db.query(Person).filter(Person.id == person_id).first()
        if not person:
            return False

        if person.gender != 'unknown':
            logger.debug(f"Person {person.full_name} already has gender: {person.gender}")
            return False

        person.gender = gender
        logger.info(f"Updated gender for {person.full_name}: {gender}")
        return True

    def update_maiden_name(self, person_id: int, maiden_name: str) -> bool:
        """
        Update a person's maiden name.

        Only updates if maiden_name is not already set.

        Args:
            person_id: ID of the person
            maiden_name: The maiden name (surname before marriage)

        Returns: True if updated
        """
        person = self.db.query(Person).filter(Person.id == person_id).first()
        if not person:
            return False

        if person.maiden_name:
            logger.debug(f"Person {person.full_name} already has maiden name: {person.maiden_name}")
            return False

        person.maiden_name = maiden_name
        logger.info(f"Updated maiden name for {person.full_name}: {maiden_name}")
        return True

    def get_deceased_without_obituary(self) -> list[Person]:
        """
        Get all deceased people who don't have their own obituary linked.

        Useful for finding obituaries to process.
        """
        return self.db.query(Person).filter(
            Person.is_deceased == True,
            Person.primary_obituary_id.is_(None)
        ).order_by(Person.last_name, Person.first_name).all()

    def get_people_by_obituary(self, obituary_id: int) -> list[Person]:
        """Get all people who are the primary deceased in a specific obituary."""
        return self.db.query(Person).filter(
            Person.primary_obituary_id == obituary_id
        ).all()


# Convenience function for getting service instance
def get_person_service(db: Session) -> PersonService:
    return PersonService(db)
