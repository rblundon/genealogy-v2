"""
Rules-based fact extraction for obituaries.

Deterministic extraction using regex patterns and inference rules.
Handles the ~95% of facts that follow standard obituary patterns.
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Person:
    """Represents a person extracted from an obituary."""
    given_names: str
    surname: Optional[str] = None
    maiden_name: Optional[str] = None
    nickname: Optional[str] = None
    role: str = "other"
    is_deceased: bool = False
    death_date: Optional[str] = None
    death_age: Optional[int] = None
    birth_year_approx: Optional[int] = None
    spouse_name: Optional[str] = None  # Given name of spouse from parenthetical
    surname_source: str = "unknown"  # explicit, inferred_from_spouse, inferred_from_parent

    @property
    def full_name(self) -> str:
        if self.surname:
            return f"{self.given_names} {self.surname}"
        return self.given_names


@dataclass
class Fact:
    """Represents an extracted fact."""
    fact_type: str
    subject_name: str
    subject_role: str
    fact_value: str
    related_name: Optional[str] = None
    relationship_type: Optional[str] = None
    extracted_context: Optional[str] = None
    is_inferred: bool = False
    inference_basis: Optional[str] = None
    confidence_score: float = 1.0

    def to_dict(self) -> Dict:
        return {
            'fact_type': self.fact_type,
            'subject_name': self.subject_name,
            'subject_role': self.subject_role,
            'fact_value': self.fact_value,
            'related_name': self.related_name,
            'relationship_type': self.relationship_type,
            'extracted_context': self.extracted_context,
            'is_inferred': self.is_inferred,
            'inference_basis': self.inference_basis,
            'confidence_score': self.confidence_score,
            'description': self._human_readable()
        }

    def _human_readable(self) -> str:
        """Generate a human-readable description of the fact."""
        if self.fact_type == 'relationship':
            # e.g., "Patricia L. Blundon's parent is Terrence Kaczmarowski"
            if self.relationship_type:
                return f"{self.subject_name}'s {self.fact_value} is {self.related_name} ({self.relationship_type})"
            return f"{self.subject_name}'s {self.fact_value} is {self.related_name}"

        elif self.fact_type == 'marriage':
            return f"{self.subject_name} married to {self.related_name}"

        elif self.fact_type == 'marriage_duration':
            return f"{self.subject_name} married to {self.related_name} for {self.fact_value}"

        elif self.fact_type == 'maiden_name':
            return f"{self.subject_name}'s maiden name is {self.fact_value}"

        elif self.fact_type == 'person_death_date':
            return f"{self.subject_name} died on {self.fact_value}"

        elif self.fact_type == 'person_death_age':
            return f"{self.subject_name} died at age {self.fact_value}"

        elif self.fact_type == 'person_nickname':
            return f"{self.subject_name}'s nickname is {self.fact_value}"

        elif self.fact_type == 'person_birth_year_approx':
            return f"{self.subject_name} born approximately {self.fact_value}"

        elif self.fact_type == 'deceased':
            return f"{self.subject_name} is deceased"

        elif self.fact_type == 'preceded_in_death':
            return f"{self.subject_name} died before the obituary subject"

        elif self.fact_type == 'surname':
            return f"{self.subject_name}'s surname is {self.fact_value}"

        else:
            return f"{self.subject_name}: {self.fact_type} = {self.fact_value}"


class RulesExtractor:
    """
    Deterministic fact extraction using regex patterns and inference rules.
    """

    # ========================================================================
    # REGEX PATTERNS
    # ========================================================================

    # Header patterns - try full pattern first (with nickname and maiden name)
    HEADER_FULL = re.compile(
        r'^([A-Z][a-z\'-]+),\s+'  # Surname
        r'([A-Z][a-zA-Z.\s]+)\s+'  # Given names (greedy)
        r'"([^"]+)"\s+'  # Nickname in quotes
        r'\((?:Nee|NEE|née|nee)\s+([A-Z][a-z\'-]+)\)\s*'  # Maiden name
        r'(.+)',  # Rest
        re.IGNORECASE
    )

    # Header with nickname only (no maiden name)
    HEADER_NICK_ONLY = re.compile(
        r'^([A-Z][a-z\'-]+),\s+'  # Surname
        r'([A-Z][a-zA-Z.\s]+)\s+'  # Given names
        r'"([^"]+)"\s+'  # Nickname
        r'(.+)',  # Rest
        re.IGNORECASE
    )

    # Header with maiden name only (no nickname)
    HEADER_MAIDEN_ONLY = re.compile(
        r'^([A-Z][a-z\'-]+),\s+'  # Surname
        r'([A-Z][a-zA-Z.\s]+?)\s*'  # Given names
        r'\((?:Nee|NEE|née|nee)\s+([A-Z][a-z\'-]+)\)\s*'  # Maiden name
        r'(.+)',  # Rest
        re.IGNORECASE
    )

    # Basic header (surname and given names only)
    # Given names end at a day of week or common obituary phrase
    HEADER_BASIC = re.compile(
        r'^([A-Z][a-z\'-]+),\s+'  # Surname
        r'([A-Z][a-zA-Z.\s]+?)\s+'  # Given names
        r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Taken|Reunited|Beloved|Passed|Loving|On\s+\w+day|Peacefully)',  # Boundary
        re.IGNORECASE
    )

    # Death date patterns
    DEATH_DATE_PATTERNS = [
        # "on Thursday, August 7, 2008"
        re.compile(r'on\s+\w+,\s+(\w+\s+\d{1,2},\s+\d{4})', re.IGNORECASE),
        # "Thursday, December 18, 2008" at start after name
        re.compile(r'(?:^|,\s+)(\w+day),?\s+(\w+\s+\d{1,2},\s+\d{4})', re.IGNORECASE),
        # "on May 24, 2018"
        re.compile(r'on\s+(\w+\s+\d{1,2},\s+\d{4})', re.IGNORECASE),
        # "December 18, 2008" standalone date
        re.compile(r'(?:^|\s)(\w+\s+\d{1,2},\s+\d{4})', re.IGNORECASE),
    ]

    # Death age patterns
    DEATH_AGE_PATTERNS = [
        re.compile(r'at\s+the\s+age\s+of\s+(\d+)\s+years?', re.IGNORECASE),
        re.compile(r'age\s+(\d+)\s+years?', re.IGNORECASE),
        re.compile(r',\s+age\s+(\d+)', re.IGNORECASE),
    ]

    # Relationship patterns - for detecting relationship blocks
    RELATIONSHIP_PATTERNS = {
        'spouse': re.compile(
            r'(?:Beloved\s+)?(?:wife|husband|spouse)\s+'
            r'(?:and\s+["\'][^"\']+["\']\s+)?'  # Optional "Koochie" type terms
            r'of\s+([A-Z][a-zA-Z.\'-]+)'
            r'(?:\s*\((?:nee|Nee|NEE|née)\s+([A-Z][a-z\'-]+)\))?'  # Optional maiden name
            r'(?:[,\s]+for\s+(\d+)\s+years?)?',
            re.IGNORECASE
        ),
        'parent': re.compile(
            r'(?:Loving\s+|Cherished\s+)?(?:mother|father|parent)\s+of\s+(.+?)(?=\.|Sister|Brother|Also|Visitation|$)',
            re.IGNORECASE
        ),
        'child': re.compile(
            r'(?:Dearest\s+|Loving\s+)?(?:daughter|son|child)\s+of\s+([A-Z][a-zA-Z.\'\s-]+?)(?:\.|,|Sister|Brother|Also|$)',
            re.IGNORECASE
        ),
        'grandparent': re.compile(
            r'(?:Proud\s+(?:and\s+loving\s+)?)?(?:grandma|grandpa|grandmother|grandfather|gramps)\s+of\s+(.+?)(?=\.|Dearest|Sister|Brother|Also|Visitation|$)',
            re.IGNORECASE
        ),
        'grandchild': re.compile(
            r'(?:Cherished\s+)?(?:grandchildren?|grandson|granddaughter)\s+(.+?)(?=;|great-grand|Also|$)',
            re.IGNORECASE
        ),
        'great_grandchild': re.compile(
            r'great-grandchildren?\s+(.+?)(?=;|and\s+brothers?|and\s+sisters?|Also|$)',
            re.IGNORECASE
        ),
        'sibling': re.compile(
            r'(?:and\s+)?(?:brothers?|sisters?|siblings?)\s+([A-Z][a-zA-Z.\'\s\(\)-]+?)(?=\.|Also|$)',
            re.IGNORECASE
        ),
        'in_law': re.compile(
            r'(?:Brother|Sister|Son|Daughter|Father|Mother)-in-law\s+of\s+(.+?)(?=\.|Also|Visitation|$)',
            re.IGNORECASE
        ),
        'son_in_law': re.compile(
            r'(?:faithful\s+)?son-in-law\s+([A-Z][a-zA-Z.\'\s-]+?)(?=;|,|$)',
            re.IGNORECASE
        ),
    }

    # Pattern for name with parenthetical (spouse or age)
    # Note: spouse name can be multi-word like "Rose Mary"
    NAME_WITH_PAREN = re.compile(
        r'([A-Z][a-zA-Z.\'-]+)\s+\(([A-Za-z][a-zA-Z.\'\s-]*|[0-9]+)\)(?:\s+([A-Z][a-zA-Z.\'-]+))?'
    )

    # Pattern for simple name (just given name)
    SIMPLE_NAME = re.compile(r'([A-Z][a-zA-Z\.\'-]+)')

    # Pattern for "the late X"
    THE_LATE = re.compile(r'the\s+late\s+([A-Z][a-zA-Z.\'\s\(\)-]+?)(?=\.|,|;|$)', re.IGNORECASE)

    # Pattern for "Reunited with X"
    REUNITED_WITH = re.compile(
        r'Reunited\s+with\s+(?:her|his)\s+(.+?)(?=on\s+\w+\s+\d|at\s+the\s+age|$)',
        re.IGNORECASE
    )

    # Pattern for "Survived by"
    SURVIVED_BY = re.compile(
        r'Survived\s+by\s+(.+?)(?=\.\s+[A-Z]|\.\s*$|Also\s+survived)',
        re.IGNORECASE | re.DOTALL
    )

    def __init__(self, death_year: Optional[int] = None):
        """
        Initialize the rules extractor.

        Args:
            death_year: Year of death for the primary deceased (for age calculations)
        """
        self.death_year = death_year
        self.persons: Dict[str, Person] = {}  # name -> Person
        self.facts: List[Fact] = []
        self.deceased_person: Optional[Person] = None
        self.deceased_spouse_name: Optional[str] = None

    def extract_all(self, obituary_text: str) -> Dict:
        """
        Extract all facts from obituary text.

        Returns:
            Dict with 'persons' and 'facts' lists
        """
        # Reset state
        self.persons = {}
        self.facts = []
        self.deceased_person = None
        self.deceased_spouse_name = None

        # Step 1: Parse header (deceased info)
        self._parse_header(obituary_text)

        # Step 2: Extract spouse relationship
        self._extract_spouse(obituary_text)

        # Step 3: Extract parent relationships (children of deceased)
        self._extract_children(obituary_text)

        # Step 4: Extract child relationships (parents of deceased)
        self._extract_parents(obituary_text)

        # Step 5: Extract grandchild relationships
        self._extract_grandchildren(obituary_text)

        # Step 6: Extract great-grandchild relationships
        self._extract_great_grandchildren(obituary_text)

        # Step 7: Extract sibling relationships (siblings of deceased)
        self._extract_siblings(obituary_text)

        # Step 8: Extract in-law relationships
        self._extract_in_laws(obituary_text)

        # Step 9: Extract deceased markers ("the late", "Reunited with")
        self._extract_deceased_markers(obituary_text)

        # Step 10: Apply surname inference
        self._apply_surname_inference()

        # Step 11: Apply sibling inference from in-laws
        self._apply_sibling_inference()

        # Step 12: Generate all facts
        self._generate_facts()

        return {
            'persons': [self._person_to_dict(p) for p in self.persons.values()],
            'facts': [f.to_dict() for f in self.facts]
        }

    def _parse_header(self, text: str) -> None:
        """Parse the obituary header for deceased info."""
        surname = None
        given_names = None
        nickname = None
        maiden_name = None
        rest_of_text = None

        # Try patterns in order of specificity
        match = self.HEADER_FULL.match(text)
        if match:
            surname = match.group(1)
            given_names = match.group(2).strip()
            nickname = match.group(3)
            maiden_name = match.group(4)
            rest_of_text = match.group(5)
        else:
            match = self.HEADER_NICK_ONLY.match(text)
            if match:
                surname = match.group(1)
                given_names = match.group(2).strip()
                nickname = match.group(3)
                rest_of_text = match.group(4)
            else:
                match = self.HEADER_MAIDEN_ONLY.match(text)
                if match:
                    surname = match.group(1)
                    given_names = match.group(2).strip()
                    maiden_name = match.group(3)
                    rest_of_text = match.group(4)
                else:
                    match = self.HEADER_BASIC.match(text)
                    if match:
                        surname = match.group(1)
                        given_names = match.group(2).strip()
                        # Group 3 is the boundary word; rest is everything from boundary onward
                        boundary_pos = text.find(match.group(3))
                        rest_of_text = text[boundary_pos:]

        if match:

            # Create deceased person
            self.deceased_person = Person(
                given_names=given_names,
                surname=surname,
                maiden_name=maiden_name,
                nickname=nickname,
                role="deceased_primary",
                is_deceased=True,
                surname_source="explicit"
            )

            # Extract death date
            for pattern in self.DEATH_DATE_PATTERNS:
                date_match = pattern.search(rest_of_text)
                if date_match:
                    # Get the full date (may be in multiple groups)
                    if date_match.lastindex and date_match.lastindex > 1:
                        self.deceased_person.death_date = date_match.group(2)
                    else:
                        self.deceased_person.death_date = date_match.group(1)
                    # Extract year for age calculations
                    year_match = re.search(r'(\d{4})', self.deceased_person.death_date)
                    if year_match:
                        self.death_year = int(year_match.group(1))
                    break

            # Extract death age
            for pattern in self.DEATH_AGE_PATTERNS:
                age_match = pattern.search(rest_of_text)
                if age_match:
                    self.deceased_person.death_age = int(age_match.group(1))
                    break

            # Add to persons dict
            self.persons[self.deceased_person.full_name] = self.deceased_person

    def _extract_spouse(self, text: str) -> None:
        """Extract spouse relationship."""
        match = self.RELATIONSHIP_PATTERNS['spouse'].search(text)
        if match:
            spouse_given = match.group(1).strip()
            spouse_maiden = match.group(2) if match.lastindex >= 2 and match.group(2) else None
            marriage_years = match.group(3) if match.lastindex >= 3 and match.group(3) else None

            # Store spouse's given name for later inference
            self.deceased_spouse_name = spouse_given

            # Create spouse person
            spouse = Person(
                given_names=spouse_given,
                surname=self.deceased_person.surname if self.deceased_person else None,
                maiden_name=spouse_maiden,
                role="spouse",
                surname_source="inferred_from_spouse" if self.deceased_person else "unknown"
            )

            # Use full name as key
            spouse_full = spouse.full_name
            self.persons[spouse_full] = spouse

            # Add maiden name fact for spouse if present
            if spouse_maiden:
                self.facts.append(Fact(
                    fact_type="maiden_name",
                    subject_name=spouse_full,
                    subject_role="spouse",
                    fact_value=spouse_maiden,
                    extracted_context=match.group(0),
                    confidence_score=1.0
                ))

            # Create marriage fact
            if self.deceased_person:
                self.facts.append(Fact(
                    fact_type="marriage",
                    subject_name=self.deceased_person.full_name,
                    subject_role="deceased_primary",
                    fact_value="spouse",
                    related_name=spouse_full,
                    relationship_type="husband" if "wife" in text.lower()[:text.lower().find(spouse_given)] else "wife",
                    extracted_context=match.group(0),
                    confidence_score=1.0
                ))

                # Bidirectional marriage
                self.facts.append(Fact(
                    fact_type="marriage",
                    subject_name=spouse_full,
                    subject_role="spouse",
                    fact_value="spouse",
                    related_name=self.deceased_person.full_name,
                    relationship_type="wife" if "wife" in text.lower()[:text.lower().find(spouse_given)] else "husband",
                    extracted_context=match.group(0),
                    confidence_score=1.0
                ))

                # Marriage duration fact
                if marriage_years:
                    self.facts.append(Fact(
                        fact_type="marriage_duration",
                        subject_name=self.deceased_person.full_name,
                        subject_role="deceased_primary",
                        fact_value=f"{marriage_years} years",
                        related_name=spouse_full,
                        extracted_context=match.group(0),
                        confidence_score=1.0
                    ))

    def _extract_children(self, text: str) -> None:
        """Extract children of the deceased (parent relationship)."""
        match = self.RELATIONSHIP_PATTERNS['parent'].search(text)
        if not match:
            return

        children_text = match.group(1)
        self._parse_name_list(children_text, "child", self.deceased_person)

    def _extract_parents(self, text: str) -> None:
        """Extract parents of the deceased (child relationship)."""
        match = self.RELATIONSHIP_PATTERNS['child'].search(text)
        if not match:
            return

        parents_text = match.group(1)

        # Parents often listed as "Terrence and Maxine Kaczmarowski"
        # Pattern: "FirstName and FirstName Surname"
        parents_pattern = re.compile(
            r'([A-Z][a-zA-Z\.\'-]+)\s+and\s+([A-Z][a-zA-Z\.\'-]+)\s+([A-Z][a-zA-Z\.\'-]+)'
        )

        parent_match = parents_pattern.search(parents_text)
        if parent_match:
            parent1_given = parent_match.group(1)
            parent2_given = parent_match.group(2)
            shared_surname = parent_match.group(3)

            for parent_given in [parent1_given, parent2_given]:
                parent = Person(
                    given_names=parent_given,
                    surname=shared_surname,
                    role="parent",
                    surname_source="explicit"
                )
                self.persons[parent.full_name] = parent

                # Create relationship facts (deceased is child of parent)
                if self.deceased_person:
                    self.facts.append(Fact(
                        fact_type="relationship",
                        subject_name=self.deceased_person.full_name,
                        subject_role="deceased_primary",
                        fact_value="parent",
                        related_name=parent.full_name,
                        relationship_type="father" if parent_given == parent1_given else "mother",
                        extracted_context=parent_match.group(0),
                        confidence_score=1.0
                    ))

                    # Bidirectional
                    self.facts.append(Fact(
                        fact_type="relationship",
                        subject_name=parent.full_name,
                        subject_role="parent",
                        fact_value="child",
                        related_name=self.deceased_person.full_name,
                        relationship_type="daughter" if self.deceased_person.maiden_name else "child",
                        extracted_context=parent_match.group(0),
                        confidence_score=1.0
                    ))

    def _extract_grandchildren(self, text: str) -> None:
        """Extract grandchildren of the deceased."""
        # Try grandparent pattern first (e.g., "grandma of X")
        match = self.RELATIONSHIP_PATTERNS['grandparent'].search(text)
        if match:
            gc_text = match.group(1)
            self._parse_grandchildren_list(gc_text, "grandchild")
            return

        # Try grandchild pattern (e.g., "grandchildren X")
        match = self.RELATIONSHIP_PATTERNS['grandchild'].search(text)
        if match:
            gc_text = match.group(1)
            self._parse_grandchildren_list(gc_text, "grandchild")

    def _extract_great_grandchildren(self, text: str) -> None:
        """Extract great-grandchildren of the deceased."""
        match = self.RELATIONSHIP_PATTERNS['great_grandchild'].search(text)
        if not match:
            return

        ggc_text = match.group(1)
        self._parse_name_list_simple(ggc_text, "great_grandchild")

    def _extract_siblings(self, text: str) -> None:
        """Extract siblings of the deceased."""
        match = self.RELATIONSHIP_PATTERNS['sibling'].search(text)
        if not match:
            return

        siblings_text = match.group(1)
        self._parse_name_list(siblings_text, "sibling", self.deceased_person)

    def _extract_in_laws(self, text: str) -> None:
        """Extract in-law relationships."""
        # Check for sister-in-law/brother-in-law
        match = self.RELATIONSHIP_PATTERNS['in_law'].search(text)
        if match:
            in_laws_text = match.group(1)

            # Determine type of in-law from the prefix
            prefix_match = re.search(r'(Brother|Sister|Son|Daughter|Father|Mother)-in-law', text, re.IGNORECASE)
            in_law_type = prefix_match.group(1).lower() if prefix_match else "in_law"

            self._parse_name_list(in_laws_text, "in_law", self.deceased_person, in_law_type=in_law_type)

        # Check for son-in-law (standalone)
        son_match = self.RELATIONSHIP_PATTERNS['son_in_law'].search(text)
        if son_match:
            sil_name = son_match.group(1).strip()
            # Parse the name (may include surname)
            parts = sil_name.split()
            if len(parts) >= 2:
                given = parts[0]
                surname = parts[-1]
            else:
                given = sil_name
                surname = None

            person = Person(
                given_names=given,
                surname=surname,
                role="in_law",
                surname_source="explicit" if surname else "unknown"
            )
            self.persons[person.full_name] = person

            if self.deceased_person:
                self.facts.append(Fact(
                    fact_type="relationship",
                    subject_name=self.deceased_person.full_name,
                    subject_role="deceased_primary",
                    fact_value="in_law",
                    related_name=person.full_name,
                    relationship_type="son-in-law",
                    extracted_context=son_match.group(0),
                    confidence_score=1.0
                ))

    def _extract_deceased_markers(self, text: str) -> None:
        """Extract markers indicating someone is deceased."""
        # "the late X" - indicates person died before the obituary subject
        for match in self.THE_LATE.finditer(text):
            name_text = match.group(1).strip()
            # Parse the name
            parsed = self._parse_single_name_with_spouse(name_text)
            if parsed:
                name_key = parsed['full_name']
                if name_key in self.persons:
                    self.persons[name_key].is_deceased = True
                    # Add preceded_in_death fact
                    self.facts.append(Fact(
                        fact_type="preceded_in_death",
                        subject_name=name_key,
                        subject_role=self.persons[name_key].role,
                        fact_value="deceased before primary",
                        extracted_context=match.group(0),
                        is_inferred=True,
                        inference_basis="'the late' indicates person died before obituary subject",
                        confidence_score=1.0
                    ))
                else:
                    # Create person as deceased
                    person = Person(
                        given_names=parsed['given'],
                        surname=parsed.get('surname'),
                        role="other",
                        is_deceased=True
                    )
                    self.persons[person.full_name] = person
                    # Add preceded_in_death fact
                    self.facts.append(Fact(
                        fact_type="preceded_in_death",
                        subject_name=person.full_name,
                        subject_role="other",
                        fact_value="deceased before primary",
                        extracted_context=match.group(0),
                        is_inferred=True,
                        inference_basis="'the late' indicates person died before obituary subject",
                        confidence_score=1.0
                    ))

        # "Reunited with X" - indicates person died before the obituary subject
        reunited_match = self.REUNITED_WITH.search(text)
        if reunited_match:
            reunited_text = reunited_match.group(1)
            # Parse "her husband Terrence and daughter Patricia"
            # Split by " and "
            parts = re.split(r'\s+and\s+', reunited_text)
            for part in parts:
                # Extract role and name (possessive may or may not be present)
                role_match = re.search(r'(?:(?:her|his)\s+)?(husband|wife|daughter|son|father|mother)\s+([A-Z][a-zA-Z.\'-]+)', part, re.IGNORECASE)
                if role_match:
                    role_type = role_match.group(1).lower()
                    given_name = role_match.group(2)

                    # Find or create person
                    found_name = None
                    for name, person in self.persons.items():
                        if person.given_names == given_name or given_name in name:
                            person.is_deceased = True
                            found_name = name
                            break

                    if found_name:
                        # Add preceded_in_death fact
                        self.facts.append(Fact(
                            fact_type="preceded_in_death",
                            subject_name=found_name,
                            subject_role=self.persons[found_name].role,
                            fact_value="deceased before primary",
                            extracted_context=reunited_match.group(0),
                            is_inferred=True,
                            inference_basis="'Reunited with' indicates person died before obituary subject",
                            confidence_score=0.95
                        ))
                    else:
                        # Infer surname based on relationship
                        inferred_surname = None
                        if self.deceased_person:
                            if role_type in ["husband", "wife"]:
                                # Spouse shares surname with deceased
                                inferred_surname = self.deceased_person.surname
                            elif role_type in ["daughter", "son"]:
                                # Child might have different surname if married, but if no other info assume deceased's maiden/surname
                                inferred_surname = self.deceased_person.maiden_name or self.deceased_person.surname

                        person = Person(
                            given_names=given_name,
                            surname=inferred_surname,
                            surname_source="inferred_from_spouse" if inferred_surname and role_type in ["husband", "wife"] else "inferred_from_parent" if inferred_surname else "unknown",
                            role="spouse" if role_type in ["husband", "wife"] else "child" if role_type in ["daughter", "son"] else "parent",
                            is_deceased=True
                        )
                        self.persons[person.full_name] = person
                        # Add preceded_in_death fact
                        self.facts.append(Fact(
                            fact_type="preceded_in_death",
                            subject_name=person.full_name,
                            subject_role=person.role,
                            fact_value="deceased before primary",
                            extracted_context=reunited_match.group(0),
                            is_inferred=True,
                            inference_basis="'Reunited with' indicates person died before obituary subject",
                            confidence_score=0.95
                        ))

    def _parse_name_list(self, text: str, role: str, parent_person: Optional[Person], in_law_type: str = None) -> None:
        """
        Parse a list of names with parenthetical spouses.

        E.g., "Ryan (Amy) and Megan (Ross) Wurz"
        """
        # Split by " and " to get individual entries
        entries = re.split(r'\s+and\s+', text)

        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue

            # Try to match "Name (Spouse) Surname" or "Name (Spouse)"
            match = self.NAME_WITH_PAREN.search(entry)
            if match:
                given = match.group(1)
                paren_content = match.group(2)
                surname = match.group(3) if match.lastindex >= 3 else None

                # Check if paren_content is age (digits) or name
                if paren_content.isdigit():
                    # It's an age
                    person = Person(
                        given_names=given,
                        surname=surname,
                        role=role,
                        birth_year_approx=self.death_year - int(paren_content) if self.death_year else None
                    )
                    self.persons[person.full_name] = person
                else:
                    # It's a spouse name
                    # Main person
                    person = Person(
                        given_names=given,
                        surname=surname,
                        role=role,
                        spouse_name=paren_content
                    )
                    self.persons[person.full_name] = person

                    # Spouse
                    spouse = Person(
                        given_names=paren_content,
                        surname=surname,  # Spouse shares surname if present
                        role="in_law" if role in ["child", "sibling"] else role,
                        spouse_name=given
                    )
                    self.persons[spouse.full_name] = spouse

                    # Create marriage facts
                    self.facts.append(Fact(
                        fact_type="marriage",
                        subject_name=person.full_name,
                        subject_role=role,
                        fact_value="spouse",
                        related_name=spouse.full_name,
                        extracted_context=entry,
                        confidence_score=1.0
                    ))
                    self.facts.append(Fact(
                        fact_type="marriage",
                        subject_name=spouse.full_name,
                        subject_role="in_law" if role in ["child", "sibling"] else role,
                        fact_value="spouse",
                        related_name=person.full_name,
                        extracted_context=entry,
                        confidence_score=1.0
                    ))

                # Create relationship to parent_person
                if parent_person:
                    if role == "child":
                        self.facts.append(Fact(
                            fact_type="relationship",
                            subject_name=parent_person.full_name,
                            subject_role="deceased_primary",
                            fact_value="child",
                            related_name=person.full_name,
                            relationship_type="son" if not self._is_female_name(given) else "daughter",
                            extracted_context=entry,
                            confidence_score=1.0
                        ))
                        # Bidirectional
                        self.facts.append(Fact(
                            fact_type="relationship",
                            subject_name=person.full_name,
                            subject_role=role,
                            fact_value="parent",
                            related_name=parent_person.full_name,
                            relationship_type="mother" if parent_person.maiden_name else "parent",
                            extracted_context=entry,
                            confidence_score=1.0
                        ))
                    elif role == "in_law" and in_law_type in ["brother", "sister"]:
                        self.facts.append(Fact(
                            fact_type="relationship",
                            subject_name=parent_person.full_name,
                            subject_role="deceased_primary",
                            fact_value="in_law",
                            related_name=person.full_name,
                            relationship_type=f"{in_law_type}-in-law",
                            extracted_context=entry,
                            confidence_score=1.0
                        ))
            else:
                # Simple name without parenthetical
                simple_match = self.SIMPLE_NAME.search(entry)
                if simple_match:
                    given = simple_match.group(1)
                    # Check if there's a surname after
                    rest = entry[simple_match.end():].strip()
                    surname = rest.split()[0] if rest else None

                    person = Person(
                        given_names=given,
                        surname=surname,
                        role=role
                    )
                    self.persons[person.full_name] = person

                    if parent_person and role == "child":
                        self.facts.append(Fact(
                            fact_type="relationship",
                            subject_name=parent_person.full_name,
                            subject_role="deceased_primary",
                            fact_value="child",
                            related_name=person.full_name,
                            extracted_context=entry,
                            confidence_score=1.0
                        ))

    def _parse_grandchildren_list(self, text: str, role: str) -> None:
        """Parse grandchildren list with ages in parentheses."""
        # Split by " and " or commas
        entries = re.split(r'\s+and\s+|,\s*', text)

        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue

            # Try "Name (age)" pattern
            match = re.match(r'([A-Z][a-zA-Z\.\'-]+)\s*\((\d+)\)', entry)
            if match:
                given = match.group(1)
                age = int(match.group(2))

                person = Person(
                    given_names=given,
                    role=role,
                    birth_year_approx=self.death_year - age if self.death_year else None
                )
                self.persons[person.full_name] = person

                # Create grandchild relationship
                if self.deceased_person:
                    self.facts.append(Fact(
                        fact_type="relationship",
                        subject_name=self.deceased_person.full_name,
                        subject_role="deceased_primary",
                        fact_value="grandchild",
                        related_name=person.full_name,
                        extracted_context=entry,
                        confidence_score=1.0
                    ))
                    # Bidirectional
                    self.facts.append(Fact(
                        fact_type="relationship",
                        subject_name=person.full_name,
                        subject_role=role,
                        fact_value="grandparent",
                        related_name=self.deceased_person.full_name,
                        relationship_type="grandmother" if self.deceased_person.maiden_name else "grandparent",
                        extracted_context=entry,
                        confidence_score=1.0
                    ))

                    # Birth year fact
                    if person.birth_year_approx:
                        self.facts.append(Fact(
                            fact_type="person_birth_year_approx",
                            subject_name=person.full_name,
                            subject_role=role,
                            fact_value=str(person.birth_year_approx),
                            extracted_context=entry,
                            is_inferred=True,
                            inference_basis=f"Age {age} at time of death ({self.death_year})",
                            confidence_score=0.75
                        ))
            else:
                # Just a name
                self._parse_name_list_simple(entry, role)

    def _parse_name_list_simple(self, text: str, role: str) -> None:
        """Parse a simple list of names (comma or 'and' separated)."""
        entries = re.split(r'\s+and\s+|,\s*', text)

        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue

            # Try "Name (Spouse) Surname" pattern first
            match = self.NAME_WITH_PAREN.search(entry)
            if match:
                given = match.group(1)
                paren_content = match.group(2)
                surname = match.group(3) if match.lastindex >= 3 else None

                if not paren_content.isdigit():
                    # Has spouse
                    person = Person(
                        given_names=given,
                        surname=surname,
                        role=role,
                        spouse_name=paren_content
                    )
                    self.persons[person.full_name] = person

                    spouse = Person(
                        given_names=paren_content,
                        surname=surname,
                        role="in_law" if role != "in_law" else role,
                        spouse_name=given
                    )
                    self.persons[spouse.full_name] = spouse

                    # Marriage facts
                    self.facts.append(Fact(
                        fact_type="marriage",
                        subject_name=person.full_name,
                        subject_role=role,
                        fact_value="spouse",
                        related_name=spouse.full_name,
                        extracted_context=entry,
                        confidence_score=1.0
                    ))
                    self.facts.append(Fact(
                        fact_type="marriage",
                        subject_name=spouse.full_name,
                        subject_role="in_law",
                        fact_value="spouse",
                        related_name=person.full_name,
                        extracted_context=entry,
                        confidence_score=1.0
                    ))
                else:
                    # Age
                    person = Person(
                        given_names=given,
                        surname=surname,
                        role=role
                    )
                    self.persons[person.full_name] = person
            else:
                # Simple name
                simple_match = self.SIMPLE_NAME.search(entry)
                if simple_match:
                    given = simple_match.group(1)
                    person = Person(
                        given_names=given,
                        role=role
                    )
                    # Only add if not already present (avoid duplicates)
                    if person.full_name not in self.persons:
                        self.persons[person.full_name] = person

            # Create relationship to deceased
            if entry and self.deceased_person:
                person_name = None
                if match:
                    person_name = f"{match.group(1)} {match.group(3)}" if match.lastindex >= 3 and match.group(3) else match.group(1)
                elif simple_match:
                    person_name = simple_match.group(1)

                if person_name and person_name in self.persons:
                    rel_type = "great_grandchild" if role == "great_grandchild" else role
                    self.facts.append(Fact(
                        fact_type="relationship",
                        subject_name=self.deceased_person.full_name,
                        subject_role="deceased_primary",
                        fact_value=rel_type,
                        related_name=person_name,
                        extracted_context=entry,
                        confidence_score=1.0
                    ))

    def _parse_single_name_with_spouse(self, text: str) -> Optional[Dict]:
        """Parse a single name that may have a spouse in parentheses."""
        match = self.NAME_WITH_PAREN.search(text)
        if match:
            given = match.group(1)
            spouse = match.group(2) if not match.group(2).isdigit() else None
            surname = match.group(3) if match.lastindex >= 3 else None
            return {
                'given': given,
                'surname': surname,
                'spouse': spouse,
                'full_name': f"{given} {surname}" if surname else given
            }

        # Try simple name
        simple_match = self.SIMPLE_NAME.search(text)
        if simple_match:
            return {
                'given': simple_match.group(1),
                'surname': None,
                'spouse': None,
                'full_name': simple_match.group(1)
            }

        return None

    def _apply_surname_inference(self) -> None:
        """Apply surname inference rules."""
        if not self.deceased_person:
            return

        deceased_surname = self.deceased_person.surname
        deceased_maiden = self.deceased_person.maiden_name

        # Collect updates to apply after iteration
        updates = []

        for name, person in list(self.persons.items()):  # Copy to list to allow modification
            if person.role == "deceased_primary":
                continue

            # Rule 1: Children inherit deceased's surname
            if person.role == "child" and not person.surname:
                person.surname = deceased_surname
                person.surname_source = "inferred_from_parent"
                updates.append((name, person))

            # Rule 2: Spouses in parentheses share surname
            if person.spouse_name and not person.surname:
                # Find spouse
                for other_name, other_person in list(self.persons.items()):
                    if other_person.given_names == person.spouse_name and other_person.surname:
                        person.surname = other_person.surname
                        person.surname_source = "inferred_from_spouse"
                        updates.append((name, person))
                        break

            # Rule 3: Married daughters get maiden name from parent
            if person.role == "child" and person.surname and person.surname != deceased_surname:
                # Different surname = married, maiden name = parent's surname
                if not person.maiden_name and deceased_surname:
                    person.maiden_name = deceased_surname
                    self.facts.append(Fact(
                        fact_type="maiden_name",
                        subject_name=person.full_name,
                        subject_role="child",
                        fact_value=deceased_surname,
                        is_inferred=True,
                        inference_basis=f"Daughter of {self.deceased_person.full_name}, maiden name from parent",
                        confidence_score=0.80
                    ))

        # Apply name updates after iteration
        for old_name, person in updates:
            self._update_person_name(old_name, person)

    def _update_person_name(self, old_name: str, person: Person) -> None:
        """Update person dict when name changes due to surname inference."""
        new_name = person.full_name
        if old_name != new_name and old_name in self.persons:
            del self.persons[old_name]
            self.persons[new_name] = person

            # Update any facts that referenced the old name
            for fact in self.facts:
                if fact.subject_name == old_name:
                    fact.subject_name = new_name
                if fact.related_name == old_name:
                    fact.related_name = new_name

    def _apply_sibling_inference(self) -> None:
        """
        Infer sibling relationships from in-law mentions.

        If deceased married to X, and deceased is "sister-in-law of Y",
        then Y is sibling of X.
        """
        if not self.deceased_person or not self.deceased_spouse_name:
            return

        # Find spouse's full name
        spouse_full = None
        for name, person in self.persons.items():
            if person.given_names == self.deceased_spouse_name and person.role == "spouse":
                spouse_full = name
                break

        if not spouse_full:
            return

        # Find in-laws marked as brother-in-law or sister-in-law
        for fact in self.facts[:]:  # Copy list to allow modification
            if fact.fact_type == "relationship" and fact.fact_value == "in_law":
                if "brother-in-law" in (fact.relationship_type or "") or "sister-in-law" in (fact.relationship_type or ""):
                    in_law_name = fact.related_name

                    # This in-law is a sibling of the spouse
                    rel_type = "brother" if "brother" in fact.relationship_type else "sister"

                    self.facts.append(Fact(
                        fact_type="relationship",
                        subject_name=in_law_name,
                        subject_role="in_law",
                        fact_value="sibling",
                        related_name=spouse_full,
                        relationship_type=rel_type,
                        is_inferred=True,
                        inference_basis=f"{self.deceased_person.full_name}'s {fact.relationship_type} is {spouse_full}'s sibling",
                        confidence_score=0.85
                    ))

                    # Bidirectional
                    self.facts.append(Fact(
                        fact_type="relationship",
                        subject_name=spouse_full,
                        subject_role="spouse",
                        fact_value="sibling",
                        related_name=in_law_name,
                        relationship_type="sister" if rel_type == "brother" else "brother",
                        is_inferred=True,
                        inference_basis=f"Sibling of {in_law_name} (inferred from in-law relationship)",
                        confidence_score=0.85
                    ))

    def _generate_facts(self) -> None:
        """Generate facts for all extracted data."""
        if not self.deceased_person:
            return

        # Deceased facts
        deceased = self.deceased_person

        # Death date
        if deceased.death_date:
            self.facts.append(Fact(
                fact_type="person_death_date",
                subject_name=deceased.full_name,
                subject_role="deceased_primary",
                fact_value=deceased.death_date,
                confidence_score=1.0
            ))

        # Death age
        if deceased.death_age:
            self.facts.append(Fact(
                fact_type="person_death_age",
                subject_name=deceased.full_name,
                subject_role="deceased_primary",
                fact_value=str(deceased.death_age),
                confidence_score=1.0
            ))

        # Maiden name
        if deceased.maiden_name:
            self.facts.append(Fact(
                fact_type="maiden_name",
                subject_name=deceased.full_name,
                subject_role="deceased_primary",
                fact_value=deceased.maiden_name,
                confidence_score=1.0
            ))

        # Nickname
        if deceased.nickname:
            self.facts.append(Fact(
                fact_type="person_nickname",
                subject_name=deceased.full_name,
                subject_role="deceased_primary",
                fact_value=deceased.nickname,
                confidence_score=1.0
            ))

        # Deceased status for all deceased persons
        for name, person in self.persons.items():
            if person.is_deceased:
                self.facts.append(Fact(
                    fact_type="deceased",
                    subject_name=name,
                    subject_role=person.role,
                    fact_value="true",
                    confidence_score=1.0
                ))

    def _is_female_name(self, name: str) -> bool:
        """Simple heuristic for female names."""
        female_endings = ['a', 'ie', 'y', 'yn', 'en']
        female_names = ['megan', 'amy', 'patricia', 'patricia', 'maxine', 'katie', 'monica', 'donna', 'rose', 'rosemary', 'autumn', 'caralyn']

        name_lower = name.lower()
        if name_lower in female_names:
            return True

        for ending in female_endings:
            if name_lower.endswith(ending):
                return True

        return False

    def _person_to_dict(self, person: Person) -> Dict:
        """Convert Person to dictionary for API response."""
        return {
            'full_name': person.full_name,
            'given_names': person.given_names,
            'surname': person.surname,
            'surname_source': person.surname_source,
            'maiden_name': person.maiden_name,
            'nickname': person.nickname,
            'role': person.role,
            'is_deceased': person.is_deceased,
            'spouse_of': f"{person.spouse_name} {person.surname}" if person.spouse_name and person.surname else person.spouse_name,
            'age': str(self.death_year - person.birth_year_approx) if person.birth_year_approx and self.death_year else None
        }


def extract_facts_with_rules(obituary_text: str) -> Dict:
    """
    Convenience function to extract facts from obituary text.

    Returns:
        Dict with 'persons' and 'facts' lists
    """
    extractor = RulesExtractor()
    return extractor.extract_all(obituary_text)
