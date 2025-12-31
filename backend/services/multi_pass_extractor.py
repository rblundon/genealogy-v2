# FILE: backend/services/multi_pass_extractor.py
# Multi-pass LLM extraction pipeline for obituaries
# ============================================================================

import json
import logging
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session
import openai

from models import (
    ObituaryCache, LLMCache, ExtractedFact, Person, ExtractionPass
)
from services.person_service import PersonService, parse_name
from utils.hash_utils import hash_prompt

logger = logging.getLogger(__name__)

# OpenAI configuration
MODEL_NAME = "gpt-4o-mini"
MODEL_TEMPERATURE = 0.1


# =============================================================================
# Data Classes for Pass Results
# =============================================================================

@dataclass
class PersonInfo:
    """Person identified in Pass 1"""
    full_name: str
    first_name: Optional[str] = None
    surname: Optional[str] = None
    is_primary_deceased: bool = False
    source_context: Optional[str] = None


@dataclass
class Pass1Result:
    """Result of Pass 1: Person Identification"""
    primary_deceased: Optional[PersonInfo] = None
    other_persons: List[PersonInfo] = field(default_factory=list)

    def all_persons(self) -> List[PersonInfo]:
        """Get all persons including primary deceased"""
        result = []
        if self.primary_deceased:
            result.append(self.primary_deceased)
        result.extend(self.other_persons)
        return result


@dataclass
class RelationshipInfo:
    """Relationship identified in Pass 2"""
    person_a: str  # Subject
    person_b: str  # Related person
    relationship_type: str  # What B is to A
    person_a_gender: Optional[str] = None
    person_b_gender: Optional[str] = None
    is_explicit: bool = True
    source_context: Optional[str] = None


@dataclass
class GenderInfo:
    """Gender fact from Pass 2"""
    person: str
    gender: str  # 'male' or 'female'
    inference_basis: str


@dataclass
class DeceasedInfo:
    """Deceased status from Pass 2"""
    person: str
    is_deceased: bool = True
    source_context: Optional[str] = None


@dataclass
class Pass2Result:
    """Result of Pass 2: Direct Relationships + Gender"""
    relationships: List[RelationshipInfo] = field(default_factory=list)
    gender_facts: List[GenderInfo] = field(default_factory=list)
    deceased_status: List[DeceasedInfo] = field(default_factory=list)


@dataclass
class InferredRelationship:
    """Inferred relationship from Pass 3"""
    person_a: str
    person_b: str
    relationship_type: str
    inference_basis: str
    confidence_score: float = 0.75


@dataclass
class InferredFact:
    """Other inferred fact from Pass 3"""
    person: str
    fact_type: str
    fact_value: str
    inference_basis: str


@dataclass
class Pass3Result:
    """Result of Pass 3: Inferred Relationships"""
    inferred_relationships: List[InferredRelationship] = field(default_factory=list)
    inferred_facts: List[InferredFact] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """Combined result of all passes"""
    pass1: Pass1Result
    pass2: Pass2Result
    pass3: Pass3Result
    persons_created: List[Person] = field(default_factory=list)
    facts_created: List[ExtractedFact] = field(default_factory=list)


# =============================================================================
# Relationship Reciprocals
# =============================================================================

# Maps relationship type to what the SUBJECT is to RELATED
# Given: A has relationship X to B (B is X of A)
# Reciprocal: B has relationship Y to A (B is Y of A, i.e., A is X of B)
# Example: Maxine's daughter is Patricia → Patricia's mother is Maxine
RECIPROCAL_RELATIONSHIPS = {
    'husband': 'wife',        # If B is husband of A, then A is wife of B
    'wife': 'husband',        # If B is wife of A, then A is husband of B
    'spouse': 'spouse',
    'father': 'son/daughter', # If B is father of A, then A is son/daughter of B
    'mother': 'son/daughter', # If B is mother of A, then A is son/daughter of B
    'son': 'father/mother',   # If B is son of A, then A is father/mother of B
    'daughter': 'father/mother',
    'child': 'parent',
    'parent': 'child',
    'brother': 'brother/sister',
    'sister': 'brother/sister',
    'sibling': 'sibling',
    'grandfather': 'grandson/granddaughter',
    'grandmother': 'grandson/granddaughter',
    'grandson': 'grandfather/grandmother',
    'granddaughter': 'grandfather/grandmother',
    'grandchild': 'grandparent',
    'grandparent': 'grandchild',
    'son-in-law': 'father-in-law/mother-in-law',
    'daughter-in-law': 'father-in-law/mother-in-law',
    'father-in-law': 'son-in-law/daughter-in-law',
    'mother-in-law': 'son-in-law/daughter-in-law',
    'brother-in-law': 'brother-in-law/sister-in-law',
    'sister-in-law': 'brother-in-law/sister-in-law',
    'uncle': 'nephew/niece',
    'aunt': 'nephew/niece',
    'nephew': 'uncle/aunt',
    'niece': 'uncle/aunt',
}

# Gender implied by relationship type (the person WITH this relationship)
RELATIONSHIP_GENDER = {
    'husband': 'male',
    'wife': 'female',
    'father': 'male',
    'mother': 'female',
    'son': 'male',
    'daughter': 'female',
    'brother': 'male',
    'sister': 'female',
    'grandfather': 'male',
    'grandmother': 'female',
    'grandson': 'male',
    'granddaughter': 'female',
    'son-in-law': 'male',
    'daughter-in-law': 'female',
    'father-in-law': 'male',
    'mother-in-law': 'female',
    'brother-in-law': 'male',
    'sister-in-law': 'female',
    'uncle': 'male',
    'aunt': 'female',
    'nephew': 'male',
    'niece': 'female',
}


# =============================================================================
# Prompt Templates
# =============================================================================

PASS1_PROMPT_TEMPLATE = """
You are a genealogy expert. Extract all people mentioned in this obituary.

TASK: List every person mentioned by name.

SURNAME PATTERNS TO RECOGNIZE:
1. "Surname, First Name" at the start = primary deceased
2. "First (SpouseName) Surname" = both First and SpouseName share the surname
   Example: "Ryan (Amy) Blundon" means Ryan Blundon and Amy (spouse of Ryan)
3. Explicit "First Surname" format - surname is the last word

OUTPUT FORMAT (JSON):
{{
  "primary_deceased": {{
    "full_name": "Full Name as best determined",
    "first_name": "First",
    "surname": "Last or null if unknown",
    "source_context": "exact phrase identifying primary deceased"
  }},
  "other_persons": [
    {{
      "full_name": "Full Name",
      "first_name": "First",
      "surname": "Last or null if unknown",
      "source_context": "exact phrase mentioning this person"
    }}
  ]
}}

RULES:
- Extract EVERY person mentioned (spouses, children, grandchildren, siblings, in-laws, etc.)
- Only assign surname if explicitly stated or determinable from obituary patterns
- For "Name (Spouse) Surname" pattern: Name gets Surname, Spouse gets null surname (we don't know their maiden/birth name)
- Do NOT infer relationships yet - that's Pass 2
- Do NOT infer gender yet - that's Pass 2
- First names only (no surname) are acceptable when surname is unknown

OBITUARY:
{obituary_text}
"""

PASS2_PROMPT_TEMPLATE = """
You are a genealogy expert. Extract relationships and gender from this obituary.

PEOPLE IDENTIFIED IN PASS 1:
{people_json}

PRIMARY DECEASED: {primary_deceased_name}

TASK: For each relationship phrase in the obituary, extract:
1. Who is related to whom
2. What the relationship type is (what PERSON_B is to PERSON_A)
3. Gender inference from relationship terms
4. Who is deceased (mentioned in "preceded in death by", "the late", "reunited with")

RELATIONSHIP TYPE MEANING:
- relationship_type describes what PERSON_B is to PERSON_A
- "Maxine's daughter Patricia" → person_a=Maxine, person_b=Patricia, type=daughter (Patricia IS Maxine's daughter)

GENDER INFERENCE RULES:
- "husband" implies the husband is male, the one WITH the husband is female
- "wife" implies the wife is female, the one WITH the wife is male
- "father", "grandfather", "brother", "son" → male
- "mother", "grandmother", "sister", "daughter" → female
- "(nee Surname)" → this person is female (maiden name indicates woman)

OUTPUT FORMAT (JSON):
{{
  "relationships": [
    {{
      "person_a": "Full Name of subject",
      "person_b": "Full Name of related person",
      "relationship_type": "what B is to A (daughter, son, husband, wife, father, mother, grandfather, grandmother, brother, sister, grandson, granddaughter, great_grandchild, son_in_law, daughter_in_law, brother_in_law, sister_in_law)",
      "person_a_gender": "male/female/unknown",
      "person_b_gender": "male/female/unknown",
      "is_explicit": true,
      "source_context": "exact phrase from obituary"
    }}
  ],
  "gender_facts": [
    {{
      "person": "Full Name",
      "gender": "male/female",
      "inference_basis": "relationship term that implies gender"
    }}
  ],
  "deceased_status": [
    {{
      "person": "Full Name",
      "is_deceased": true,
      "source_context": "phrase indicating deceased (e.g., 'preceded in death by', 'the late', 'reunited with')"
    }}
  ]
}}

RULES:
- Use EXACT names from the people list when possible
- Include the primary deceased in deceased_status
- "preceded in death by X" or "reunited with X" means X is deceased
- "the late X" means X is deceased
- Extract ALL explicit relationships mentioned
- son-in-law = spouse of one's child
- daughter-in-law = spouse of one's child
- brother-in-law = spouse's sibling OR sibling's spouse
- sister-in-law = spouse's sibling OR sibling's spouse

IMPORTANT - SINGLE DIRECTION ONLY:
- For each relationship, only create ONE entry from the PRIMARY DECEASED's perspective
- If "Maxine's grandson is Ryan", create: person_a=Maxine, person_b=Ryan, type=grandson
- Do NOT also create: person_a=Ryan, person_b=Maxine, type=grandmother (this is redundant!)
- All relationships should have the primary deceased as person_a when possible

IMPORTANT - SPOUSE PATTERN DETECTION:
- "Name (Spouse) Surname" pattern indicates marriage:
  - "Ryan (Amy) Blundon" means Ryan and Amy are married
  - Create: person_a=Ryan Blundon, person_b=Amy, relationship_type=wife
  - The person in parentheses is typically the wife
  - Infer gender: Amy is female (wife), Ryan is male (husband)
- Similarly for other "(Spouse)" patterns in the obituary

OBITUARY:
{obituary_text}
"""

PASS3_PROMPT_TEMPLATE = """
You are a genealogy expert. Derive additional relationships through logical inference.

PEOPLE IDENTIFIED:
{people_json}

DIRECT RELATIONSHIPS FROM PASS 2:
{relationships_json}

GENDER FACTS:
{gender_json}

TASK: Infer additional relationships that can be logically derived.

INFERENCE RULES TO APPLY:
1. SPOUSE FROM PATTERN: If "Name (Spouse) Surname" pattern exists, Name and Spouse are married
2. IN-LAW TO SPOUSE: If X is son-in-law of Y, then X is spouse of Y's child
3. IN-LAW SIBLINGS: If X is brother-in-law of Y, and Y's spouse's maiden name matches X's surname, X is Y's spouse's sibling
4. MAIDEN NAME: Unmarried daughters have father's surname as maiden name
5. RECIPROCAL: If A is parent of B, then B is child of A (but don't duplicate if already explicit)

OUTPUT FORMAT (JSON):
{{
  "inferred_relationships": [
    {{
      "person_a": "Full Name",
      "person_b": "Full Name",
      "relationship_type": "what B is to A",
      "inference_basis": "explanation of how this was inferred",
      "confidence_score": 0.75
    }}
  ],
  "inferred_facts": [
    {{
      "person": "Full Name",
      "fact_type": "maiden_name",
      "fact_value": "Surname",
      "inference_basis": "explanation"
    }}
  ]
}}

RULES:
- Only infer what can be logically derived from the explicit relationships
- Use confidence scores: 0.60-0.80 for inferences
- Don't duplicate relationships already explicit in Pass 2
- Be conservative - only infer when there's strong logical basis
"""


# =============================================================================
# Multi-Pass Extractor Class
# =============================================================================

class MultiPassExtractor:
    """
    Orchestrates multi-pass LLM extraction pipeline.

    Pipeline:
    - Pass 1: Identify all people mentioned
    - Pass 2: Extract explicit relationships and infer gender
    - Pass 3: Derive additional relationships through logic
    """

    def __init__(self, db: Session):
        self.db = db
        self.person_service = PersonService(db)
        self.client = openai.OpenAI()

    async def extract_all(
        self,
        obituary_cache_id: int,
        obituary_text: str,
        force_reprocess: bool = False
    ) -> ExtractionResult:
        """
        Run all 3 passes and return combined results.

        Args:
            obituary_cache_id: ID of the obituary in cache
            obituary_text: The obituary text to process
            force_reprocess: If True, ignore cached results

        Returns:
            ExtractionResult with all extracted data
        """
        logger.info(f"Starting multi-pass extraction for obituary {obituary_cache_id}")

        # Pass 1: Person Identification
        pass1_result = await self.run_pass1(obituary_cache_id, obituary_text, force_reprocess)
        logger.info(f"Pass 1 complete: {len(pass1_result.all_persons())} people identified")

        # Pass 2: Direct Relationships + Gender
        pass2_result = await self.run_pass2(
            obituary_cache_id, obituary_text, pass1_result, force_reprocess
        )
        logger.info(
            f"Pass 2 complete: {len(pass2_result.relationships)} relationships, "
            f"{len(pass2_result.gender_facts)} gender facts"
        )

        # Pass 3: Inferred Relationships
        pass3_result = await self.run_pass3(
            obituary_cache_id, pass1_result, pass2_result, force_reprocess
        )
        logger.info(f"Pass 3 complete: {len(pass3_result.inferred_relationships)} inferred relationships")

        # Create/update Person records and ExtractedFacts
        result = await self._store_results(
            obituary_cache_id, obituary_text, pass1_result, pass2_result, pass3_result
        )

        logger.info(
            f"Extraction complete: {len(result.persons_created)} persons, "
            f"{len(result.facts_created)} facts"
        )

        return result

    async def run_pass1(
        self,
        obituary_cache_id: int,
        obituary_text: str,
        force_reprocess: bool = False
    ) -> Pass1Result:
        """Pass 1: Person Identification"""

        # Create or get extraction pass record
        pass_record = self._get_or_create_pass(obituary_cache_id, 1)

        # Check for cached result
        if not force_reprocess and pass_record.status == 'completed':
            cached = self._get_cached_pass_result(obituary_cache_id, 1)
            if cached:
                logger.info("Using cached Pass 1 result")
                return self._parse_pass1_result(cached)

        pass_record.status = 'running'
        self.db.commit()

        # Build prompt
        prompt = PASS1_PROMPT_TEMPLATE.format(obituary_text=obituary_text)

        # Call LLM
        try:
            response = await self._call_llm(obituary_cache_id, 1, prompt)
            result = self._parse_pass1_result(response)

            # Update pass record
            pass_record.status = 'completed'
            pass_record.completed_timestamp = datetime.utcnow()
            self.db.commit()

            return result

        except Exception as e:
            logger.error(f"Pass 1 failed: {e}")
            pass_record.status = 'failed'
            pass_record.error_message = str(e)
            self.db.commit()
            raise

    async def run_pass2(
        self,
        obituary_cache_id: int,
        obituary_text: str,
        pass1_result: Pass1Result,
        force_reprocess: bool = False
    ) -> Pass2Result:
        """Pass 2: Direct Relationships + Gender"""

        pass_record = self._get_or_create_pass(obituary_cache_id, 2)

        if not force_reprocess and pass_record.status == 'completed':
            cached = self._get_cached_pass_result(obituary_cache_id, 2)
            if cached:
                logger.info("Using cached Pass 2 result")
                return self._parse_pass2_result(cached)

        pass_record.status = 'running'
        self.db.commit()

        # Build people JSON for prompt
        people_list = [
            {
                "name": p.full_name,
                "surname": p.surname
            }
            for p in pass1_result.all_persons()
        ]
        people_json = json.dumps(people_list, indent=2)

        primary_name = pass1_result.primary_deceased.full_name if pass1_result.primary_deceased else "Unknown"

        prompt = PASS2_PROMPT_TEMPLATE.format(
            people_json=people_json,
            primary_deceased_name=primary_name,
            obituary_text=obituary_text
        )

        try:
            response = await self._call_llm(obituary_cache_id, 2, prompt)
            result = self._parse_pass2_result(response)

            pass_record.status = 'completed'
            pass_record.completed_timestamp = datetime.utcnow()
            self.db.commit()

            return result

        except Exception as e:
            logger.error(f"Pass 2 failed: {e}")
            pass_record.status = 'failed'
            pass_record.error_message = str(e)
            self.db.commit()
            raise

    async def run_pass3(
        self,
        obituary_cache_id: int,
        pass1_result: Pass1Result,
        pass2_result: Pass2Result,
        force_reprocess: bool = False
    ) -> Pass3Result:
        """Pass 3: Inferred Relationships"""

        pass_record = self._get_or_create_pass(obituary_cache_id, 3)

        if not force_reprocess and pass_record.status == 'completed':
            cached = self._get_cached_pass_result(obituary_cache_id, 3)
            if cached:
                logger.info("Using cached Pass 3 result")
                return self._parse_pass3_result(cached)

        pass_record.status = 'running'
        self.db.commit()

        # Build context for Pass 3
        people_list = [{"name": p.full_name, "surname": p.surname} for p in pass1_result.all_persons()]
        people_json = json.dumps(people_list, indent=2)

        relationships_list = [
            {
                "person_a": r.person_a,
                "person_b": r.person_b,
                "type": r.relationship_type
            }
            for r in pass2_result.relationships
        ]
        relationships_json = json.dumps(relationships_list, indent=2)

        gender_list = [{"person": g.person, "gender": g.gender} for g in pass2_result.gender_facts]
        gender_json = json.dumps(gender_list, indent=2)

        prompt = PASS3_PROMPT_TEMPLATE.format(
            people_json=people_json,
            relationships_json=relationships_json,
            gender_json=gender_json
        )

        try:
            response = await self._call_llm(obituary_cache_id, 3, prompt)
            result = self._parse_pass3_result(response)

            pass_record.status = 'completed'
            pass_record.completed_timestamp = datetime.utcnow()
            self.db.commit()

            return result

        except Exception as e:
            logger.error(f"Pass 3 failed: {e}")
            pass_record.status = 'failed'
            pass_record.error_message = str(e)
            self.db.commit()
            raise

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    def _get_or_create_pass(self, obituary_cache_id: int, pass_number: int) -> ExtractionPass:
        """Get existing or create new extraction pass record."""
        existing = self.db.query(ExtractionPass).filter(
            ExtractionPass.obituary_cache_id == obituary_cache_id,
            ExtractionPass.pass_number == pass_number
        ).first()

        if existing:
            return existing

        new_pass = ExtractionPass(
            obituary_cache_id=obituary_cache_id,
            pass_number=pass_number,
            status='pending'
        )
        self.db.add(new_pass)
        self.db.flush()
        return new_pass

    def _get_cached_pass_result(self, obituary_cache_id: int, pass_number: int) -> Optional[dict]:
        """Get cached LLM result for a pass."""
        cached = self.db.query(LLMCache).filter(
            LLMCache.obituary_cache_id == obituary_cache_id,
            LLMCache.pass_number == pass_number,
            LLMCache.api_error.is_(None)
        ).order_by(LLMCache.request_timestamp.desc()).first()

        if cached and cached.parsed_json:
            return cached.parsed_json
        return None

    async def _call_llm(
        self,
        obituary_cache_id: int,
        pass_number: int,
        prompt: str
    ) -> dict:
        """Call LLM and cache result."""
        prompt_hash = hash_prompt(prompt, str(pass_number), MODEL_NAME)

        # Check cache
        cached = self.db.query(LLMCache).filter(
            LLMCache.prompt_hash == prompt_hash,
            LLMCache.pass_number == pass_number,
            LLMCache.api_error.is_(None)
        ).first()

        if cached and cached.parsed_json:
            logger.info(f"LLM cache hit for pass {pass_number}")
            return cached.parsed_json

        # Make API call
        logger.info(f"Calling LLM for pass {pass_number}")
        start_time = datetime.utcnow()

        response = self.client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a genealogy expert. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=MODEL_TEMPERATURE,
            response_format={"type": "json_object"}
        )

        end_time = datetime.utcnow()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        response_text = response.choices[0].message.content
        parsed_json = json.loads(response_text)

        # Cache the result
        llm_cache = LLMCache(
            obituary_cache_id=obituary_cache_id,
            llm_provider='openai',
            model_version=MODEL_NAME,
            prompt_hash=prompt_hash,
            prompt_text=prompt,
            response_text=response_text,
            parsed_json=parsed_json,
            token_usage_prompt=response.usage.prompt_tokens if response.usage else None,
            token_usage_completion=response.usage.completion_tokens if response.usage else None,
            token_usage_total=response.usage.total_tokens if response.usage else None,
            request_timestamp=start_time,
            response_timestamp=end_time,
            duration_ms=duration_ms,
            pass_number=pass_number
        )
        self.db.add(llm_cache)
        self.db.commit()

        return parsed_json

    def _parse_pass1_result(self, data: dict) -> Pass1Result:
        """Parse Pass 1 LLM response into Pass1Result."""
        result = Pass1Result()

        if 'primary_deceased' in data and data['primary_deceased']:
            pd = data['primary_deceased']
            result.primary_deceased = PersonInfo(
                full_name=pd.get('full_name', ''),
                first_name=pd.get('first_name'),
                surname=pd.get('surname'),
                is_primary_deceased=True,
                source_context=pd.get('source_context')
            )

        for person in data.get('other_persons', []):
            result.other_persons.append(PersonInfo(
                full_name=person.get('full_name', ''),
                first_name=person.get('first_name'),
                surname=person.get('surname'),
                is_primary_deceased=False,
                source_context=person.get('source_context')
            ))

        return result

    def _parse_pass2_result(self, data: dict) -> Pass2Result:
        """Parse Pass 2 LLM response into Pass2Result."""
        result = Pass2Result()

        for rel in data.get('relationships', []):
            result.relationships.append(RelationshipInfo(
                person_a=rel.get('person_a', ''),
                person_b=rel.get('person_b', ''),
                relationship_type=rel.get('relationship_type', ''),
                person_a_gender=rel.get('person_a_gender'),
                person_b_gender=rel.get('person_b_gender'),
                is_explicit=rel.get('is_explicit', True),
                source_context=rel.get('source_context')
            ))

        for gf in data.get('gender_facts', []):
            result.gender_facts.append(GenderInfo(
                person=gf.get('person', ''),
                gender=gf.get('gender', ''),
                inference_basis=gf.get('inference_basis', '')
            ))

        for ds in data.get('deceased_status', []):
            result.deceased_status.append(DeceasedInfo(
                person=ds.get('person', ''),
                is_deceased=ds.get('is_deceased', True),
                source_context=ds.get('source_context')
            ))

        return result

    def _parse_pass3_result(self, data: dict) -> Pass3Result:
        """Parse Pass 3 LLM response into Pass3Result."""
        result = Pass3Result()

        for rel in data.get('inferred_relationships', []):
            result.inferred_relationships.append(InferredRelationship(
                person_a=rel.get('person_a', ''),
                person_b=rel.get('person_b', ''),
                relationship_type=rel.get('relationship_type', ''),
                inference_basis=rel.get('inference_basis', ''),
                confidence_score=rel.get('confidence_score', 0.75)
            ))

        for fact in data.get('inferred_facts', []):
            result.inferred_facts.append(InferredFact(
                person=fact.get('person', ''),
                fact_type=fact.get('fact_type', ''),
                fact_value=fact.get('fact_value', ''),
                inference_basis=fact.get('inference_basis', '')
            ))

        return result

    async def _store_results(
        self,
        obituary_cache_id: int,
        obituary_text: str,
        pass1: Pass1Result,
        pass2: Pass2Result,
        pass3: Pass3Result
    ) -> ExtractionResult:
        """Store extraction results in database."""
        result = ExtractionResult(pass1=pass1, pass2=pass2, pass3=pass3)

        # Create Person records for all identified people
        person_map: Dict[str, Person] = {}  # name -> Person

        for person_info in pass1.all_persons():
            person, created = self.person_service.get_or_create_person(
                full_name=person_info.full_name,
                first_name=person_info.first_name,
                last_name=person_info.surname
            )
            person_map[person_info.full_name.lower()] = person

            if created:
                result.persons_created.append(person)

            # Link obituary if primary deceased
            if person_info.is_primary_deceased:
                self.person_service.link_obituary(person.id, obituary_cache_id)
                self.person_service.mark_deceased(person.id, obituary_cache_id)

        # Apply gender facts and create ExtractedFact records
        for gf in pass2.gender_facts:
            person = person_map.get(gf.person.lower())
            if person:
                self.person_service.update_gender(person.id, gf.gender)

                # Create person_gender ExtractedFact
                gender_fact = ExtractedFact(
                    obituary_cache_id=obituary_cache_id,
                    fact_type='person_gender',
                    subject_name=gf.person,
                    subject_role='other',
                    fact_value=gf.gender,
                    extracted_context=gf.inference_basis,
                    is_inferred=True,
                    inference_basis=gf.inference_basis,
                    confidence_score=0.95,
                    person_id=person.id
                )
                self.db.add(gender_fact)
                result.facts_created.append(gender_fact)

        # Apply deceased status
        for ds in pass2.deceased_status:
            person = person_map.get(ds.person.lower())
            if person and ds.is_deceased:
                self.person_service.mark_deceased(person.id, obituary_cache_id)

        # Create ExtractedFact records for relationships
        for rel in pass2.relationships:
            person = person_map.get(rel.person_a.lower())
            related_person = person_map.get(rel.person_b.lower())

            fact = ExtractedFact(
                obituary_cache_id=obituary_cache_id,
                fact_type='relationship',
                subject_name=rel.person_a,
                subject_role='other',  # Deprecated field
                fact_value=rel.relationship_type,
                related_name=rel.person_b,
                relationship_type=rel.relationship_type,
                extracted_context=rel.source_context,
                is_inferred=not rel.is_explicit,
                confidence_score=1.0 if rel.is_explicit else 0.85,
                person_id=person.id if person else None,
                related_person_id=related_person.id if related_person else None
            )
            self.db.add(fact)
            result.facts_created.append(fact)

        # Create facts for inferred relationships (Pass 3)
        for rel in pass3.inferred_relationships:
            person = person_map.get(rel.person_a.lower())
            related_person = person_map.get(rel.person_b.lower())

            fact = ExtractedFact(
                obituary_cache_id=obituary_cache_id,
                fact_type='relationship',
                subject_name=rel.person_a,
                subject_role='other',
                fact_value=rel.relationship_type,
                related_name=rel.person_b,
                relationship_type=rel.relationship_type,
                is_inferred=True,
                inference_basis=rel.inference_basis,
                confidence_score=rel.confidence_score,
                person_id=person.id if person else None,
                related_person_id=related_person.id if related_person else None
            )
            self.db.add(fact)
            result.facts_created.append(fact)

        # Create facts for inferred facts (like maiden names)
        for inf_fact in pass3.inferred_facts:
            person = person_map.get(inf_fact.person.lower())

            fact = ExtractedFact(
                obituary_cache_id=obituary_cache_id,
                fact_type=inf_fact.fact_type,
                subject_name=inf_fact.person,
                subject_role='other',
                fact_value=inf_fact.fact_value,
                is_inferred=True,
                inference_basis=inf_fact.inference_basis,
                confidence_score=0.75,
                person_id=person.id if person else None
            )
            self.db.add(fact)
            result.facts_created.append(fact)

            # Update person record if it's a maiden name
            if inf_fact.fact_type == 'maiden_name' and person:
                self.person_service.update_maiden_name(person.id, inf_fact.fact_value)

        # =====================================================================
        # Post-processing: Gender, surnames, and spouse pattern detection
        # =====================================================================
        # Note: We don't create explicit bidirectional relationships because
        # the API automatically transforms relationships when displaying from
        # the related person's perspective (see person_sync_service._reverse_relationship)

        self._infer_spouse_details(
            obituary_cache_id, pass1, pass2, pass3, person_map, result
        )
        self._detect_spouse_patterns(
            obituary_cache_id, obituary_text, pass1, person_map, result
        )

        self.db.commit()
        return result

    def _create_bidirectional_relationships(
        self,
        obituary_cache_id: int,
        pass2: Pass2Result,
        pass3: Pass3Result,
        person_map: Dict[str, Person],
        result: ExtractionResult
    ) -> None:
        """Create reciprocal relationship facts for bidirectional relationships."""

        # Track existing relationships to avoid duplicates
        existing_rels = set()
        for rel in pass2.relationships:
            existing_rels.add((rel.person_a.lower(), rel.person_b.lower(), rel.relationship_type))
            existing_rels.add((rel.person_b.lower(), rel.person_a.lower(),
                             RECIPROCAL_RELATIONSHIPS.get(rel.relationship_type, rel.relationship_type)))
        for rel in pass3.inferred_relationships:
            existing_rels.add((rel.person_a.lower(), rel.person_b.lower(), rel.relationship_type))

        # Create reciprocals for Pass 2 relationships
        for rel in pass2.relationships:
            reciprocal_type = RECIPROCAL_RELATIONSHIPS.get(rel.relationship_type)
            if not reciprocal_type:
                continue

            # Check if reciprocal already exists
            key = (rel.person_b.lower(), rel.person_a.lower(), reciprocal_type)
            if key in existing_rels:
                continue
            existing_rels.add(key)

            person = person_map.get(rel.person_b.lower())
            related_person = person_map.get(rel.person_a.lower())

            fact = ExtractedFact(
                obituary_cache_id=obituary_cache_id,
                fact_type='relationship',
                subject_name=rel.person_b,
                subject_role='other',
                fact_value=reciprocal_type,
                related_name=rel.person_a,
                relationship_type=reciprocal_type,
                is_inferred=True,
                inference_basis=f"Reciprocal of: {rel.person_a} → {rel.relationship_type} → {rel.person_b}",
                confidence_score=0.95,
                person_id=person.id if person else None,
                related_person_id=related_person.id if related_person else None
            )
            self.db.add(fact)
            result.facts_created.append(fact)

        # Create reciprocals for Pass 3 inferred relationships
        for rel in pass3.inferred_relationships:
            reciprocal_type = RECIPROCAL_RELATIONSHIPS.get(rel.relationship_type)
            if not reciprocal_type:
                continue

            key = (rel.person_b.lower(), rel.person_a.lower(), reciprocal_type)
            if key in existing_rels:
                continue
            existing_rels.add(key)

            person = person_map.get(rel.person_b.lower())
            related_person = person_map.get(rel.person_a.lower())

            fact = ExtractedFact(
                obituary_cache_id=obituary_cache_id,
                fact_type='relationship',
                subject_name=rel.person_b,
                subject_role='other',
                fact_value=reciprocal_type,
                related_name=rel.person_a,
                relationship_type=reciprocal_type,
                is_inferred=True,
                inference_basis=f"Reciprocal of: {rel.person_a} → {rel.relationship_type} → {rel.person_b}",
                confidence_score=rel.confidence_score * 0.95,
                person_id=person.id if person else None,
                related_person_id=related_person.id if related_person else None
            )
            self.db.add(fact)
            result.facts_created.append(fact)

    def _infer_spouse_details(
        self,
        obituary_cache_id: int,
        pass1: Pass1Result,
        pass2: Pass2Result,
        pass3: Pass3Result,
        person_map: Dict[str, Person],
        result: ExtractionResult
    ) -> None:
        """
        Infer gender and surname for spouses from the "Name (Spouse) Surname" pattern.

        For pattern "Ryan (Amy) Blundon":
        - Amy is female (spouse role typically indicates wife in this pattern)
        - Amy's married surname is Blundon
        - Ryan is male
        """
        # Collect all spouse relationships
        spouse_rels = []
        for rel in pass2.relationships:
            if rel.relationship_type in ('spouse', 'wife', 'husband'):
                spouse_rels.append(rel)
        for rel in pass3.inferred_relationships:
            if rel.relationship_type in ('spouse', 'wife', 'husband'):
                spouse_rels.append(rel)

        # Track which persons already have gender facts
        existing_gender = set()
        for gf in pass2.gender_facts:
            existing_gender.add(gf.person.lower())

        for rel in spouse_rels:
            person_a = person_map.get(rel.person_a.lower())
            person_b = person_map.get(rel.person_b.lower())

            # Get surnames from Pass 1
            person_a_info = None
            person_b_info = None
            for p in pass1.all_persons():
                if p.full_name.lower() == rel.person_a.lower():
                    person_a_info = p
                if p.full_name.lower() == rel.person_b.lower():
                    person_b_info = p

            # Infer gender from relationship type
            if rel.relationship_type == 'wife' and person_b and rel.person_b.lower() not in existing_gender:
                self.person_service.update_gender(person_b.id, 'female')
                existing_gender.add(rel.person_b.lower())

                gender_fact = ExtractedFact(
                    obituary_cache_id=obituary_cache_id,
                    fact_type='person_gender',
                    subject_name=rel.person_b,
                    subject_role='other',
                    fact_value='female',
                    is_inferred=True,
                    inference_basis=f"Identified as wife of {rel.person_a}",
                    confidence_score=0.95,
                    person_id=person_b.id
                )
                self.db.add(gender_fact)
                result.facts_created.append(gender_fact)

            elif rel.relationship_type == 'husband' and person_b and rel.person_b.lower() not in existing_gender:
                self.person_service.update_gender(person_b.id, 'male')
                existing_gender.add(rel.person_b.lower())

                gender_fact = ExtractedFact(
                    obituary_cache_id=obituary_cache_id,
                    fact_type='person_gender',
                    subject_name=rel.person_b,
                    subject_role='other',
                    fact_value='male',
                    is_inferred=True,
                    inference_basis=f"Identified as husband of {rel.person_a}",
                    confidence_score=0.95,
                    person_id=person_b.id
                )
                self.db.add(gender_fact)
                result.facts_created.append(gender_fact)

            elif rel.relationship_type == 'spouse':
                # For generic "spouse", infer from the "(Spouse)" pattern
                # The person in parentheses is typically the wife
                # Check if person_b has no surname (indicating they were in parentheses)
                if person_b_info and not person_b_info.surname and person_a_info and person_a_info.surname:
                    # person_b was likely in parentheses - infer as wife
                    if rel.person_b.lower() not in existing_gender:
                        self.person_service.update_gender(person_b.id, 'female')
                        existing_gender.add(rel.person_b.lower())

                        gender_fact = ExtractedFact(
                            obituary_cache_id=obituary_cache_id,
                            fact_type='person_gender',
                            subject_name=rel.person_b,
                            subject_role='other',
                            fact_value='female',
                            is_inferred=True,
                            inference_basis=f"In parentheses pattern with {rel.person_a} - typically indicates wife",
                            confidence_score=0.85,
                            person_id=person_b.id if person_b else None
                        )
                        self.db.add(gender_fact)
                        result.facts_created.append(gender_fact)

                    # Infer married surname for spouse
                    if person_b and person_a_info and person_a_info.surname:
                        # Create married_name fact
                        surname_fact = ExtractedFact(
                            obituary_cache_id=obituary_cache_id,
                            fact_type='married_name',
                            subject_name=rel.person_b,
                            subject_role='other',
                            fact_value=person_a_info.surname,
                            is_inferred=True,
                            inference_basis=f"Spouse of {rel.person_a} who has surname {person_a_info.surname}",
                            confidence_score=0.85,
                            person_id=person_b.id
                        )
                        self.db.add(surname_fact)
                        result.facts_created.append(surname_fact)

                        # Update person's last_name if not set
                        if person_b and not person_b.last_name:
                            person_b.last_name = person_a_info.surname
                            logger.info(f"Inferred surname for {rel.person_b}: {person_a_info.surname}")

    def _detect_spouse_patterns(
        self,
        obituary_cache_id: int,
        obituary_text: str,
        pass1: Pass1Result,
        person_map: Dict[str, Person],
        result: ExtractionResult
    ) -> None:
        """
        Detect "Name (Spouse) Surname" patterns directly from obituary text.

        This catches cases the LLM might miss, like "Ryan (Amy) Blundon".
        Creates spouse relationships, gender facts, and married surname facts.
        """
        # Pattern: "FirstName (SpouseName) Surname" - captures all three parts
        # Examples: "Ryan (Amy) Blundon", "Reginald (Donna) Paradowski"
        pattern = r'\b([A-Z][a-z]+)\s+\(([A-Z][a-z]+)\)\s+([A-Z][a-z]+)\b'

        # Track what we've already processed
        existing_rels = set()
        for fact in result.facts_created:
            if fact.fact_type == 'relationship':
                existing_rels.add((fact.subject_name.lower(), fact.related_name.lower() if fact.related_name else ''))

        existing_gender = set()
        for fact in result.facts_created:
            if fact.fact_type == 'person_gender':
                existing_gender.add(fact.subject_name.lower())

        for match in re.finditer(pattern, obituary_text):
            first_name = match.group(1)
            spouse_name = match.group(2)
            surname = match.group(3)

            # Find the person with surname in person_map
            person_with_surname = None
            spouse_person = None

            # Look for "FirstName Surname" in person_map
            full_name_key = f"{first_name} {surname}".lower()
            if full_name_key in person_map:
                person_with_surname = person_map[full_name_key]

            # Look for spouse (first name only) in person_map
            spouse_key = spouse_name.lower()
            if spouse_key in person_map:
                spouse_person = person_map[spouse_key]

            if not person_with_surname or not spouse_person:
                logger.debug(f"Spouse pattern found but persons not in map: {first_name} ({spouse_name}) {surname}")
                continue

            logger.info(f"Detected spouse pattern: {first_name} ({spouse_name}) {surname}")

            # First, update spouse's name to include surname (do this BEFORE creating facts)
            spouse_full_name = spouse_name  # Default to first name only
            if spouse_person and not spouse_person.last_name:
                spouse_person.last_name = surname
                spouse_person.full_name = f"{spouse_name} {surname}"
                spouse_full_name = f"{spouse_name} {surname}"
                logger.info(f"Updated name: {spouse_name} -> {spouse_full_name}")

                # Create married_name fact
                surname_fact = ExtractedFact(
                    obituary_cache_id=obituary_cache_id,
                    fact_type='married_name',
                    subject_name=spouse_full_name,
                    subject_role='other',
                    fact_value=surname,
                    is_inferred=True,
                    inference_basis=f"Spouse of {first_name} {surname}",
                    confidence_score=0.90,
                    person_id=spouse_person.id
                )
                self.db.add(surname_fact)
                result.facts_created.append(surname_fact)

            # Create spouse relationship using updated names
            rel_key = (full_name_key, spouse_full_name.lower())
            if rel_key not in existing_rels:
                existing_rels.add(rel_key)

                fact = ExtractedFact(
                    obituary_cache_id=obituary_cache_id,
                    fact_type='relationship',
                    subject_name=f"{first_name} {surname}",
                    subject_role='other',
                    fact_value='wife',
                    related_name=spouse_full_name,  # Use updated name
                    relationship_type='wife',
                    is_inferred=True,
                    inference_basis=f"Pattern: '{first_name} ({spouse_name}) {surname}' indicates marriage",
                    confidence_score=0.95,
                    person_id=person_with_surname.id,
                    related_person_id=spouse_person.id
                )
                self.db.add(fact)
                result.facts_created.append(fact)

            # Note: We don't create an explicit reciprocal here because the API
            # automatically transforms relationships when displaying from the
            # related person's perspective

            # Infer gender using updated name
            if spouse_full_name.lower() not in existing_gender:
                existing_gender.add(spouse_full_name.lower())
                self.person_service.update_gender(spouse_person.id, 'female')

                gender_fact = ExtractedFact(
                    obituary_cache_id=obituary_cache_id,
                    fact_type='person_gender',
                    subject_name=spouse_full_name,  # Use updated name
                    subject_role='other',
                    fact_value='female',
                    is_inferred=True,
                    inference_basis=f"In parentheses pattern with {first_name} {surname} - indicates wife",
                    confidence_score=0.90,
                    person_id=spouse_person.id
                )
                self.db.add(gender_fact)
                result.facts_created.append(gender_fact)


# =============================================================================
# Convenience Function
# =============================================================================

def get_multi_pass_extractor(db: Session) -> MultiPassExtractor:
    """Get a MultiPassExtractor instance."""
    return MultiPassExtractor(db)
