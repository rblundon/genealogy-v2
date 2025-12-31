# FILE: backend/services/llm_extractor.py
# LLM-based fact extraction service for obituaries
# ============================================================================

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import openai
import json
import re
from datetime import datetime
import logging

from models import LLMCache, ExtractedFact
from utils.hash_utils import hash_prompt

logger = logging.getLogger(__name__)


# Note: All curly braces in JSON examples must be doubled ({{ and }}) to escape them
# since we use .format() to insert the obituary text
FACT_EXTRACTION_PROMPT_TEMPLATE = """
You are a genealogy expert analyzing an obituary to extract factual claims. Extract EVERY fact you can identify.

OBITUARY CONVENTIONS TO UNDERSTAND:
1. "the late X" or "late X" means X is DECEASED - extract a preceded_in_death fact
2. "Name (Spouse) Surname" pattern: the name in parentheses is the SPOUSE's first name
   Example: "Reginald (Donna) Paradowski" = Reginald Paradowski married to Donna Paradowski
3. "(nee Surname)" means MAIDEN NAME - the woman's birth surname before marriage
4. "Beloved husband/wife of X" means X is the SPOUSE
5. "Loving father/mother of X" means X is a CHILD
6. "Cherished grandfather/grandmother of X" means X is a GRANDCHILD
7. "Proud great-grandfather" or "gramps of" after grandchildren = GREAT-GRANDCHILDREN
8. "Brother-in-law/Sister-in-law of X" means X is spouse's sibling OR sibling's spouse
9. Daughters typically take husband's surname when married; sons keep birth surname
10. When only first name given for spouse (e.g., "son Robert (Amy)"), Amy is Robert's wife

FACT TYPES:
- person_name: Full name of a person mentioned (EXTRACT FOR EVERY PERSON)
- person_death_date: Date of death
- person_death_age: Age at death
- person_birth_date: Date of birth
- person_gender: Gender (male/female) - infer from relationship terms like father/mother, husband/wife
- maiden_name: Woman's birth surname before marriage
- relationship: Family relationship between two people
- preceded_in_death: Someone who died before the primary deceased
- survived_by: Someone who survived the primary deceased
- location_birth, location_death, location_residence: Places

CRITICAL - EXTRACT person_name FOR EVERYONE INCLUDING:
- The primary deceased person
- Spouses (current and former, living and deceased)
- All children, grandchildren, great-grandchildren
- Parents and siblings
- In-laws (children's spouses, spouse's siblings)
- Anyone in "preceded in death" or "survived by" lists

For each fact, provide:
- fact_type: One of the types above
- subject_name: Who this fact is about (use full name with surname if known)
- subject_role: deceased_primary, spouse, child, parent, sibling, grandchild, great_grandchild, in_law, other
- fact_value: The value/content of this fact
- related_name: (for relationships) the other person's full name
- relationship_type: DESCRIBES WHAT RELATED_NAME IS TO SUBJECT_NAME (not vice versa):
    Example: subject=Maxine, related=Patricia, type=daughter → Patricia IS Maxine's daughter
    Use: son, daughter, father, mother, brother, sister, husband, wife,
         grandfather, grandmother, grandson, granddaughter,
         great_grandson, great_granddaughter, brother_in_law, sister_in_law
- extracted_context: The exact phrase from obituary supporting this fact
- is_inferred: true if you had to infer this (not explicitly stated)
- inference_basis: (if inferred) brief explanation of your reasoning
- confidence_score: 0.00 to 1.00

CONFIDENCE SCORING:
- 1.00: Explicitly stated, unambiguous
- 0.85-0.99: Clear from context with standard conventions
- 0.70-0.84: Inferred from obituary patterns (e.g., spouse surname from marriage)
- 0.50-0.69: Reasonable inference with some uncertainty
- Below 0.50: Highly uncertain, don't extract unless clearly supported

CRITICAL SURNAME RULES:
- DO NOT assume great-grandchildren's surnames - parents are unknown
- Married women: use married surname (husband's) as primary, maiden name as separate fact
- Children of married couples: sons keep father's surname, daughters use father's surname until married
- For "grandchild Name (Spouse)" pattern: grandchild has parent's surname, spouse has their own unknown surname

EXAMPLE INPUT:
"Smith, John. December 1, 2023, age 75. Beloved husband of Mary (nee Johnson). Loving father of the late Patricia (Steve) Blundon. Grandfather of Ryan (Amy) and Megan. Proud gramps of Baby."

EXAMPLE OUTPUT showing key patterns:
{{
  "facts": [
    {{
      "fact_type": "person_name",
      "subject_name": "John Smith",
      "subject_role": "deceased_primary",
      "fact_value": "John Smith",
      "extracted_context": "Smith, John",
      "is_inferred": false,
      "confidence_score": 1.0
    }},
    {{
      "fact_type": "person_gender",
      "subject_name": "John Smith",
      "subject_role": "deceased_primary",
      "fact_value": "male",
      "extracted_context": "Beloved husband",
      "is_inferred": true,
      "inference_basis": "husband implies male",
      "confidence_score": 1.0
    }},
    {{
      "fact_type": "person_name",
      "subject_name": "Patricia Blundon",
      "subject_role": "child",
      "fact_value": "Patricia Blundon",
      "extracted_context": "Patricia (Steve) Blundon",
      "is_inferred": false,
      "confidence_score": 1.0
    }},
    {{
      "fact_type": "preceded_in_death",
      "subject_name": "John Smith",
      "subject_role": "deceased_primary",
      "related_name": "Patricia Blundon",
      "relationship_type": "daughter",
      "fact_value": "daughter died before subject",
      "extracted_context": "the late Patricia",
      "is_inferred": false,
      "confidence_score": 1.0
    }},
    {{
      "fact_type": "maiden_name",
      "subject_name": "Patricia Blundon",
      "subject_role": "child",
      "fact_value": "Smith",
      "extracted_context": "father of the late Patricia",
      "is_inferred": true,
      "inference_basis": "daughter's maiden name is father's surname",
      "confidence_score": 0.75
    }},
    {{
      "fact_type": "person_name",
      "subject_name": "Steve Blundon",
      "subject_role": "in_law",
      "fact_value": "Steve Blundon",
      "extracted_context": "Patricia (Steve) Blundon",
      "is_inferred": false,
      "confidence_score": 1.0
    }},
    {{
      "fact_type": "relationship",
      "subject_name": "Patricia Blundon",
      "subject_role": "child",
      "related_name": "Steve Blundon",
      "relationship_type": "spouse",
      "fact_value": "husband",
      "extracted_context": "Patricia (Steve) Blundon",
      "is_inferred": true,
      "inference_basis": "Name (Spouse) Surname pattern indicates marriage",
      "confidence_score": 0.95
    }},
    {{
      "fact_type": "person_name",
      "subject_name": "Ryan Blundon",
      "subject_role": "grandchild",
      "fact_value": "Ryan Blundon",
      "extracted_context": "Grandfather of Ryan",
      "is_inferred": true,
      "inference_basis": "Grandson likely has father's surname; Patricia's only child means Steve is father",
      "confidence_score": 0.75
    }},
    {{
      "fact_type": "person_name",
      "subject_name": "Amy",
      "subject_role": "in_law",
      "fact_value": "Amy",
      "extracted_context": "Ryan (Amy)",
      "is_inferred": false,
      "confidence_score": 1.0
    }},
    {{
      "fact_type": "relationship",
      "subject_name": "Ryan Blundon",
      "subject_role": "grandchild",
      "related_name": "Amy",
      "relationship_type": "spouse",
      "fact_value": "wife",
      "extracted_context": "Ryan (Amy)",
      "is_inferred": true,
      "inference_basis": "Name (Spouse) pattern indicates marriage",
      "confidence_score": 0.95
    }},
    {{
      "fact_type": "person_name",
      "subject_name": "Baby",
      "subject_role": "great_grandchild",
      "fact_value": "Baby",
      "extracted_context": "Proud gramps of Baby",
      "is_inferred": false,
      "confidence_score": 1.0
    }},
    {{
      "fact_type": "relationship",
      "subject_name": "John Smith",
      "subject_role": "deceased_primary",
      "related_name": "Baby",
      "relationship_type": "great_grandfather",
      "fact_value": "great-grandfather of Baby",
      "extracted_context": "Proud gramps of Baby",
      "is_inferred": true,
      "inference_basis": "gramps after grandchildren listing indicates great-grandchildren",
      "confidence_score": 0.90
    }}
  ]
}}

CRITICAL RELATIONSHIP EXTRACTION RULES:
1. Extract ALL persons mentioned, even if only first name is given
2. For EVERY relationship term (husband/wife, father/mother, grandfather/grandmother, etc.), create a relationship fact
3. Mark all inferred facts with is_inferred: true and explain in inference_basis
4. Watch for "the late" indicating deceased family members
5. Pay attention to generational patterns: children -> grandchildren -> great-grandchildren
6. Return ONLY valid JSON with a "facts" array, no markdown

REQUIRED RELATIONSHIP EXTRACTIONS (EXTRACT ALL OF THESE):
- "Beloved husband/wife of X" → Extract: deceased_primary is SPOUSE of X
- "Loving father/mother of X" → Extract TWO facts:
  1. deceased_primary is FATHER/MOTHER of X (relationship_type: son/daughter)
  2. X is SON/DAUGHTER of deceased_primary (relationship_type: father/mother)
- "Grandfather/grandmother of X" → Extract TWO facts:
  1. deceased_primary is GRANDFATHER of X (relationship_type: grandson/granddaughter)
  2. X is GRANDCHILD of deceased_primary (relationship_type: grandfather)
- "Proud gramps/great-grandfather of X" → Extract: deceased_primary is GREAT_GRANDPARENT of X
- "Brother-in-law/Sister-in-law of X" → Extract: deceased_primary is SIBLING_IN_LAW of X
- "Name (Spouse) Surname" → Extract: Name is married to Spouse
- Infer sibling relationships: if X is brother-in-law and spouse's maiden name matches X's surname, infer X is spouse's sibling
- Infer parent-child for grandchildren: if only one child is mentioned, grandchildren are that child's children

EXAMPLE RELATIONSHIP EXTRACTIONS from "Beloved husband of Maxine":
{{
  "fact_type": "relationship",
  "subject_name": "John Smith",
  "subject_role": "deceased_primary",
  "related_name": "Maxine Smith",
  "relationship_type": "spouse",
  "fact_value": "spouse",
  "extracted_context": "Beloved husband of Maxine",
  "is_inferred": false,
  "confidence_score": 1.0
}}

EXAMPLE from "Loving father of Patricia" - extract BOTH directions:
{{
  "fact_type": "relationship",
  "subject_name": "John Smith",
  "subject_role": "deceased_primary",
  "related_name": "Patricia Blundon",
  "relationship_type": "daughter",
  "fact_value": "daughter",
  "extracted_context": "Loving father of Patricia",
  "is_inferred": false,
  "confidence_score": 1.0
}},
{{
  "fact_type": "relationship",
  "subject_name": "Patricia Blundon",
  "subject_role": "child",
  "related_name": "John Smith",
  "relationship_type": "father",
  "fact_value": "father",
  "extracted_context": "Loving father of Patricia",
  "is_inferred": false,
  "confidence_score": 1.0
}}

EXAMPLE from "Grandfather of Ryan" - extract BOTH directions:
{{
  "fact_type": "relationship",
  "subject_name": "John Smith",
  "subject_role": "deceased_primary",
  "related_name": "Ryan Blundon",
  "relationship_type": "grandson",
  "fact_value": "grandson",
  "extracted_context": "Grandfather of Ryan",
  "is_inferred": false,
  "confidence_score": 1.0
}},
{{
  "fact_type": "relationship",
  "subject_name": "Ryan Blundon",
  "subject_role": "grandchild",
  "related_name": "John Smith",
  "relationship_type": "grandfather",
  "fact_value": "grandfather",
  "extracted_context": "Grandfather of Ryan",
  "is_inferred": false,
  "confidence_score": 1.0
}}

EXAMPLE inferred parent-child when grandchildren through single child:
{{
  "fact_type": "relationship",
  "subject_name": "Ryan Blundon",
  "subject_role": "grandchild",
  "related_name": "Patricia Blundon",
  "relationship_type": "mother",
  "fact_value": "mother",
  "extracted_context": "Grandfather of Ryan",
  "is_inferred": true,
  "inference_basis": "Patricia is the only child mentioned, so grandchild must be her child",
  "confidence_score": 0.75
}}

EXAMPLE from "Brother-in-law of Reginald Paradowski":
{{
  "fact_type": "relationship",
  "subject_name": "John Smith",
  "subject_role": "deceased_primary",
  "related_name": "Reginald Paradowski",
  "relationship_type": "brother_in_law",
  "fact_value": "brother-in-law",
  "extracted_context": "Brother-in-law of Reginald",
  "is_inferred": false,
  "confidence_score": 1.0
}}

EXAMPLE inferring sibling from brother-in-law + spouse's maiden name:
When spouse's maiden name matches brother-in-law's surname, they are siblings:
{{
  "fact_type": "relationship",
  "subject_name": "Reginald Paradowski",
  "subject_role": "in_law",
  "related_name": "Maxine Kaczmarowski",
  "relationship_type": "sister",
  "fact_value": "sister",
  "extracted_context": "Brother-in-law of Reginald Paradowski; Maxine (nee Paradowski)",
  "is_inferred": true,
  "inference_basis": "Reginald has surname Paradowski and Maxine's maiden name is Paradowski, so they are siblings",
  "confidence_score": 0.75
}}

NOW EXTRACT FACTS FROM THIS OBITUARY:

{obituary_text}
"""


async def extract_facts_from_obituary(
    db: Session,
    obituary_cache_id: int,
    obituary_text: str,
    llm_provider: str = "openai",
    model_version: str = "gpt-4o-mini"
) -> List[ExtractedFact]:
    """
    Extract facts from obituary text using LLM.

    Args:
        db: Database session
        obituary_cache_id: ID of obituary in cache
        obituary_text: The obituary text to analyze
        llm_provider: LLM provider name (default: openai)
        model_version: Model version to use

    Returns:
        List of ExtractedFact instances (already committed to database)
    """

    # Build prompt
    prompt = FACT_EXTRACTION_PROMPT_TEMPLATE.format(obituary_text=obituary_text)
    prompt_hash_value = hash_prompt(prompt, obituary_text, model_version)

    # Check LLM cache first
    cached_response = db.query(LLMCache).filter(
        LLMCache.prompt_hash == prompt_hash_value,
        LLMCache.llm_provider == llm_provider,
        LLMCache.model_version == model_version,
        LLMCache.api_error.is_(None)  # Only use successful cached responses
    ).first()

    llm_cache_entry = None
    facts_data = []

    if cached_response and cached_response.parsed_json:
        # Use cached response
        response_json = cached_response.parsed_json
        llm_cache_entry = cached_response
        logger.info(f"Using cached LLM response (saved ${cached_response.cost_usd:.4f})")

        # Handle both direct array and object with 'facts' key
        if isinstance(response_json, dict) and 'facts' in response_json:
            facts_data = response_json['facts']
        elif isinstance(response_json, list):
            facts_data = response_json
        else:
            logger.warning(f"Unexpected cached response format: {type(response_json)}")
            facts_data = []
    else:
        # Call OpenAI API
        start_time = datetime.now()

        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=model_version,
                messages=[
                    {"role": "system", "content": "You are a genealogy expert extracting facts from obituaries. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1  # Low temperature for consistent extraction
            )

            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # Parse response
            response_text = response.choices[0].message.content
            response_json = json.loads(response_text)

            # Handle both direct array and object with 'facts' key
            if isinstance(response_json, dict) and 'facts' in response_json:
                facts_data = response_json['facts']
            elif isinstance(response_json, list):
                facts_data = response_json
            else:
                raise ValueError(f"Unexpected response format: {type(response_json)}")

            # Calculate cost (approximate for GPT-4 Turbo)
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            # GPT-4 Turbo pricing (approximate)
            cost_per_1k_prompt = 0.01
            cost_per_1k_completion = 0.03
            cost_usd = (prompt_tokens / 1000 * cost_per_1k_prompt +
                       completion_tokens / 1000 * cost_per_1k_completion)

            # Store in LLM cache
            llm_cache_entry = LLMCache(
                obituary_cache_id=obituary_cache_id,
                llm_provider=llm_provider,
                model_version=model_version,
                prompt_hash=prompt_hash_value,
                prompt_text=prompt,
                response_text=response_text,
                parsed_json=response_json,
                token_usage_prompt=prompt_tokens,
                token_usage_completion=completion_tokens,
                token_usage_total=total_tokens,
                cost_usd=cost_usd,
                response_timestamp=end_time,
                duration_ms=duration_ms
            )
            db.add(llm_cache_entry)
            db.commit()
            db.refresh(llm_cache_entry)

            logger.info(f"LLM extraction complete: {total_tokens} tokens, ${cost_usd:.4f}")

        except Exception as e:
            # Log error
            llm_cache_entry = LLMCache(
                obituary_cache_id=obituary_cache_id,
                llm_provider=llm_provider,
                model_version=model_version,
                prompt_hash=prompt_hash_value,
                prompt_text=prompt,
                api_error=str(e)
            )
            db.add(llm_cache_entry)
            db.commit()
            logger.error(f"LLM extraction failed: {str(e)}")
            raise

    # Convert JSON facts to ExtractedFact models
    extracted_facts = []

    for fact_data in facts_data:
        try:
            # Validate required fields
            if not fact_data.get('fact_type') or not fact_data.get('subject_name'):
                logger.warning(f"Skipping invalid fact: missing required fields - {fact_data}")
                continue

            fact = ExtractedFact(
                obituary_cache_id=obituary_cache_id,
                llm_cache_id=llm_cache_entry.id if llm_cache_entry else None,
                fact_type=fact_data['fact_type'],
                subject_name=fact_data['subject_name'],
                subject_role=fact_data.get('subject_role', 'other'),
                fact_value=fact_data.get('fact_value', ''),
                related_name=fact_data.get('related_name'),
                relationship_type=fact_data.get('relationship_type'),
                extracted_context=fact_data.get('extracted_context'),
                source_sentence=fact_data.get('source_sentence'),
                is_inferred=fact_data.get('is_inferred', False),
                inference_basis=fact_data.get('inference_basis'),
                confidence_score=fact_data.get('confidence_score', 0.5)
            )
            db.add(fact)
            extracted_facts.append(fact)
        except Exception as e:
            logger.warning(f"Failed to create fact from data: {fact_data}, error: {e}")
            continue

    db.commit()

    # Refresh all facts to get IDs
    for fact in extracted_facts:
        db.refresh(fact)

    logger.info(f"Stored {len(extracted_facts)} facts in database")

    # Post-process: ensure person_name facts exist for all related people
    ensure_person_names_for_related(db, obituary_cache_id, extracted_facts)

    # Post-process: infer gender and fix gendered relationship terms
    infer_gender_and_fix_relationships(db, obituary_cache_id, extracted_facts)

    # Post-process to derive additional relationships
    derived_facts = derive_relationships(db, obituary_cache_id, extracted_facts)
    extracted_facts.extend(derived_facts)

    return extracted_facts


def ensure_person_names_for_related(
    db: Session,
    obituary_cache_id: int,
    existing_facts: List[ExtractedFact]
) -> None:
    """
    Ensure person_name facts exist for all people mentioned in relationships.

    This catches people who are only mentioned as related_name (e.g., deceased spouses)
    and creates person_name facts for them so they appear in the persons list.
    """
    # Get all subject names that have person_name facts
    existing_names = {
        f.subject_name for f in existing_facts
        if f.fact_type == 'person_name'
    }

    # Find all related_names that don't have person_name facts
    related_names_to_add = set()
    related_roles = {}  # name -> role

    for fact in existing_facts:
        if fact.related_name and fact.related_name not in existing_names:
            related_names_to_add.add(fact.related_name)
            # Infer role from relationship type
            if fact.relationship_type:
                role = _infer_role_from_relationship_type(fact.relationship_type)
                if fact.related_name not in related_roles or role != 'other':
                    related_roles[fact.related_name] = role

    # Create person_name facts for missing people
    for name in related_names_to_add:
        role = related_roles.get(name, 'other')
        person_fact = ExtractedFact(
            obituary_cache_id=obituary_cache_id,
            fact_type='person_name',
            subject_name=name,
            subject_role=role,
            fact_value=name,
            extracted_context="Mentioned in relationship",
            is_inferred=True,
            inference_basis="Person mentioned as related_name in relationship fact",
            confidence_score=0.95
        )
        db.add(person_fact)
        existing_facts.append(person_fact)
        logger.info(f"Created person_name fact for {name} (role: {role})")

    if related_names_to_add:
        db.commit()
        logger.info(f"Added {len(related_names_to_add)} person_name facts for related people")


def _infer_role_from_relationship_type(relationship_type: str) -> str:
    """Infer person's role from relationship type."""
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
        'great_grandson': 'great_grandchild',
        'great_granddaughter': 'great_grandchild',
        'brother_in_law': 'in_law',
        'sister_in_law': 'in_law',
        'son_in_law': 'in_law',
        'daughter_in_law': 'in_law',
    }
    return role_map.get(relationship_type, 'other')


def infer_gender_and_fix_relationships(
    db: Session,
    obituary_cache_id: int,
    existing_facts: List[ExtractedFact]
) -> None:
    """
    Infer gender from spouse relationships and fix gendered relationship terms.

    Gender inference rules:
    - If person has a "husband" → person is female
    - If person has a "wife" → person is male
    - Pronouns "her" before husband/wife also indicate gender

    Then fix relationship terms to match gender:
    - Female: grandfather→grandmother, brother→sister
    - Male: grandmother→grandfather, sister→brother
    """
    # Build lookup by subject
    facts_by_subject: dict[str, list[ExtractedFact]] = {}
    for fact in existing_facts:
        if fact.subject_name not in facts_by_subject:
            facts_by_subject[fact.subject_name] = []
        facts_by_subject[fact.subject_name].append(fact)

    # Track inferred genders
    inferred_genders: dict[str, str] = {}

    # First pass: Check for existing gender facts
    for fact in existing_facts:
        if fact.fact_type == 'person_gender':
            inferred_genders[fact.subject_name] = fact.fact_value.lower()

    # Second pass: Infer gender from spouse relationships
    for fact in existing_facts:
        if fact.subject_name in inferred_genders:
            continue

        # Check preceded_in_death and relationship facts for spouse info
        if fact.fact_type in ('preceded_in_death', 'relationship'):
            if fact.relationship_type == 'husband':
                # Subject has a husband → subject is female
                inferred_genders[fact.subject_name] = 'female'
                logger.info(f"Inferred gender for {fact.subject_name}: female (has husband)")
            elif fact.relationship_type == 'wife':
                # Subject has a wife → subject is male
                inferred_genders[fact.subject_name] = 'male'
                logger.info(f"Inferred gender for {fact.subject_name}: male (has wife)")
            elif fact.relationship_type == 'spouse' and fact.extracted_context:
                # Check context for "her husband" or "his wife"
                ctx = fact.extracted_context.lower()
                if 'her husband' in ctx or 'her beloved husband' in ctx:
                    inferred_genders[fact.subject_name] = 'female'
                    logger.info(f"Inferred gender for {fact.subject_name}: female (from 'her husband' context)")
                elif 'his wife' in ctx or 'his beloved wife' in ctx:
                    inferred_genders[fact.subject_name] = 'male'
                    logger.info(f"Inferred gender for {fact.subject_name}: male (from 'his wife' context)")

    # Also check maiden_name - having a maiden name implies female
    for fact in existing_facts:
        if fact.fact_type == 'maiden_name' and fact.subject_name not in inferred_genders:
            inferred_genders[fact.subject_name] = 'female'
            logger.info(f"Inferred gender for {fact.subject_name}: female (has maiden name)")

    # Create gender facts for inferred genders that don't have explicit facts
    for subject_name, gender in inferred_genders.items():
        has_gender_fact = any(
            f.fact_type == 'person_gender' and f.subject_name == subject_name
            for f in existing_facts
        )
        if not has_gender_fact:
            # Find the subject_role from existing facts
            subject_role = 'other'
            for f in facts_by_subject.get(subject_name, []):
                if f.subject_role:
                    subject_role = f.subject_role
                    break

            gender_fact = ExtractedFact(
                obituary_cache_id=obituary_cache_id,
                fact_type='person_gender',
                subject_name=subject_name,
                subject_role=subject_role,
                fact_value=gender,
                extracted_context="Inferred from spouse relationship",
                is_inferred=True,
                inference_basis=f"Gender inferred from having a {'husband' if gender == 'female' else 'wife'}",
                confidence_score=1.0
            )
            db.add(gender_fact)
            existing_facts.append(gender_fact)
            logger.info(f"Created gender fact for {subject_name}: {gender}")

    # Third pass: Fix gendered relationship terms based on inferred gender
    # Only fix terms that describe the SUBJECT's role, not the related person's role
    # e.g., grandfather→grandmother (subject's role), but NOT daughter→son (related's role)
    gender_relationship_fixes = {
        # Female subject fixes - terms describing subject's role
        ('grandfather', 'female'): 'grandmother',
        ('brother', 'female'): 'sister',
        ('great_grandfather', 'female'): 'great_grandmother',
        ('father', 'female'): 'mother',
        ('uncle', 'female'): 'aunt',
        ('nephew', 'female'): 'niece',
        # Male subject fixes - terms describing subject's role
        ('grandmother', 'male'): 'grandfather',
        ('sister', 'male'): 'brother',
        ('great_grandmother', 'male'): 'great_grandfather',
        ('mother', 'male'): 'father',
        ('aunt', 'male'): 'uncle',
        ('niece', 'male'): 'nephew',
    }

    for fact in existing_facts:
        if fact.fact_type == 'relationship' and fact.relationship_type:
            subject_gender = inferred_genders.get(fact.subject_name)
            if subject_gender:
                key = (fact.relationship_type, subject_gender)
                if key in gender_relationship_fixes:
                    old_type = fact.relationship_type
                    new_type = gender_relationship_fixes[key]
                    fact.relationship_type = new_type
                    fact.fact_value = new_type
                    logger.info(f"Fixed relationship for {fact.subject_name}: {old_type} → {new_type} (gender: {subject_gender})")

    db.commit()
    logger.info(f"Gender inference complete. Inferred genders for {len(inferred_genders)} persons")


def derive_relationships(
    db: Session,
    obituary_cache_id: int,
    existing_facts: List[ExtractedFact]
) -> List[ExtractedFact]:
    """
    Derive additional relationships from existing facts through logical inference.

    This handles cases where the LLM may not have explicitly extracted all relationships,
    but they can be logically derived (e.g., preceded_in_death implies parent-child).
    """
    derived = []

    # Build lookup structures
    facts_by_type = {}
    for fact in existing_facts:
        if fact.fact_type not in facts_by_type:
            facts_by_type[fact.fact_type] = []
        facts_by_type[fact.fact_type].append(fact)

    # Get existing relationship pairs to avoid duplicates
    existing_pairs = set()
    for fact in facts_by_type.get('relationship', []):
        if fact.related_name:
            existing_pairs.add((fact.subject_name, fact.related_name, fact.relationship_type))

    # Get maiden names for sibling inference
    maiden_names = {}
    for fact in facts_by_type.get('maiden_name', []):
        maiden_names[fact.subject_name] = fact.fact_value

    # Get spouse relationships
    spouses = {}
    for fact in facts_by_type.get('relationship', []):
        if fact.relationship_type == 'spouse' and fact.related_name:
            spouses[fact.subject_name] = fact.related_name

    # Find the primary deceased and their gender
    primary_deceased = None
    primary_deceased_gender = None
    for fact in facts_by_type.get('person_name', []):
        if fact.subject_role == 'deceased_primary':
            primary_deceased = fact.subject_name
            break

    # Check for gender of primary deceased
    for fact in facts_by_type.get('person_gender', []):
        if fact.subject_name == primary_deceased:
            primary_deceased_gender = fact.fact_value.lower()
            break

    # 0. Fix incorrect relationship directions (gender-aware)
    # relationship_type should describe what SUBJECT is to RELATED
    # e.g., if Maxine (female) -> Ryan and relationship is "grandchild",
    # then Maxine IS grandmother OF Ryan

    # Gender-neutral fixes (apply regardless of gender)
    neutral_fixes = {
        'child': {
            'father': 'daughter',  # If child -> parent with "father", child is daughter
            'mother': 'daughter',
        },
        'grandchild': {
            'grandfather': 'grandchild',
            'grandmother': 'grandchild',
        },
    }

    # Gender-specific fixes for deceased_primary
    # Maps: (relationship_type, gender) -> correct_type
    #
    # NOTE: relationship_type should describe what RELATED person is to SUBJECT
    # e.g., "daughter" means related IS subject's daughter (correct, don't change)
    # But sometimes LLM outputs what SUBJECT is to RELATED (e.g., "grandfather")
    # which needs gender-based correction
    #
    # We only fix terms that describe SUBJECT's role (grandfather, brother, etc.)
    # We do NOT fix terms that describe RELATED's role (daughter, son, grandchild)
    gendered_deceased_fixes = {
        # Female deceased - fix terms where LLM described subject's role incorrectly
        ('grandfather', 'female'): 'grandmother',
        ('great_grandfather', 'female'): 'great_grandmother',
        ('brother', 'female'): 'sister',
        ('sibling', 'female'): 'sister',
        ('father', 'female'): 'mother',  # If LLM said subject IS father, fix to mother
        ('uncle', 'female'): 'aunt',
        # Male deceased
        ('grandmother', 'male'): 'grandfather',
        ('great_grandmother', 'male'): 'great_grandfather',
        ('sister', 'male'): 'brother',
        ('sibling', 'male'): 'brother',
        ('mother', 'male'): 'father',  # If LLM said subject IS mother, fix to father
        ('aunt', 'male'): 'uncle',
    }

    for fact in existing_facts:
        if fact.fact_type != 'relationship':
            continue

        # Apply neutral fixes first
        if fact.subject_role in neutral_fixes:
            fixes = neutral_fixes[fact.subject_role]
            if fact.relationship_type in fixes:
                old_type = fact.relationship_type
                fact.relationship_type = fixes[fact.relationship_type]
                fact.fact_value = fact.relationship_type
                logger.info(f"Fixed relationship type: {old_type} -> {fact.relationship_type}")

        # Apply gender-specific fixes for deceased_primary
        if fact.subject_role == 'deceased_primary' and primary_deceased_gender:
            key = (fact.relationship_type, primary_deceased_gender)
            if key in gendered_deceased_fixes:
                old_type = fact.relationship_type
                fact.relationship_type = gendered_deceased_fixes[key]
                fact.fact_value = fact.relationship_type
                logger.info(f"Fixed relationship type (gender-aware): {old_type} -> {fact.relationship_type} (subject is {primary_deceased_gender})")

    # 1. Derive parent-child from preceded_in_death
    for fact in facts_by_type.get('preceded_in_death', []):
        if fact.related_name and fact.relationship_type in ['daughter', 'son']:
            # Check if we already have the parent-child relationship
            pair = (fact.subject_name, fact.related_name, fact.relationship_type)
            if pair not in existing_pairs:
                derived_fact = ExtractedFact(
                    obituary_cache_id=obituary_cache_id,
                    fact_type='relationship',
                    subject_name=fact.subject_name,
                    subject_role='deceased_primary',
                    fact_value=fact.relationship_type,
                    related_name=fact.related_name,
                    relationship_type=fact.relationship_type,
                    extracted_context=f"Derived from: {fact.extracted_context}",
                    is_inferred=True,
                    inference_basis="Derived from preceded_in_death fact",
                    confidence_score=0.95
                )
                db.add(derived_fact)
                derived.append(derived_fact)
                existing_pairs.add(pair)
                logger.info(f"Derived parent-child: {fact.subject_name} -> {fact.related_name}")

    # 2. Derive spouse relationships from person_name pairs with "(Spouse)" pattern
    # Look for patterns where we have both "X Surname" and "Y Surname" or "X" with known role
    person_names = {f.subject_name: f for f in facts_by_type.get('person_name', [])}

    # Get children and their spouses from naming patterns
    for name, fact in person_names.items():
        if fact.subject_role == 'child':
            # Look for spouse in in_law category with same surname
            surname = name.split()[-1] if ' ' in name else None
            if surname:
                for other_name, other_fact in person_names.items():
                    if other_fact.subject_role == 'in_law' and surname in other_name:
                        pair = (name, other_name, 'spouse')
                        if pair not in existing_pairs:
                            derived_fact = ExtractedFact(
                                obituary_cache_id=obituary_cache_id,
                                fact_type='relationship',
                                subject_name=name,
                                subject_role='child',
                                fact_value='spouse',
                                related_name=other_name,
                                relationship_type='spouse',
                                extracted_context=f"Derived from: {name} is child, {other_name} is in-law with same surname",
                                is_inferred=True,
                                inference_basis=f"Both share surname {surname}, child + in_law roles suggest marriage",
                                confidence_score=0.85
                            )
                            db.add(derived_fact)
                            derived.append(derived_fact)
                            existing_pairs.add(pair)
                            logger.info(f"Derived spouse: {name} married to {other_name}")

    # Also check grandchildren spouse patterns from context
    # Look for "Name (Spouse)" pattern in grandchild contexts
    for name, fact in person_names.items():
        if fact.subject_role == 'grandchild' and fact.extracted_context:
            ctx = fact.extracted_context
            # Pattern like "Ryan (Amy)" - grandchild with spouse
            match = re.search(r'(\w+)\s*\((\w+)\)', ctx)
            if match:
                first_name = match.group(1)
                spouse_first = match.group(2)
                if first_name.lower() in name.lower():
                    # The spouse might only have first name
                    spouse_full = spouse_first
                    # Check if spouse exists in person_names
                    if spouse_full in person_names:
                        pair = (name, spouse_full, 'spouse')
                        pair_reverse = (spouse_full, name, 'spouse')
                        if pair not in existing_pairs and pair_reverse not in existing_pairs:
                            derived_fact = ExtractedFact(
                                obituary_cache_id=obituary_cache_id,
                                fact_type='relationship',
                                subject_name=name,
                                subject_role='grandchild',
                                fact_value='spouse',
                                related_name=spouse_full,
                                relationship_type='spouse',
                                extracted_context=f"Derived from pattern: {ctx}",
                                is_inferred=True,
                                inference_basis=f"Name (Spouse) pattern: {first_name} ({spouse_first})",
                                confidence_score=0.90
                            )
                            db.add(derived_fact)
                            derived.append(derived_fact)
                            existing_pairs.add(pair)
                            logger.info(f"Derived grandchild spouse: {name} married to {spouse_full}")

    # Check for brother-in-law spouse patterns:
    # If X is brother-in-law and "X (Y) Surname" pattern exists, X married to Y
    # We need to check the extracted_context for the "(Spouse)" pattern
    for name, fact in person_names.items():
        if fact.subject_role == 'in_law' and fact.extracted_context:
            # Look for "(Spouse)" pattern in context
            ctx = fact.extracted_context
            # Pattern like "Reginald (Donna) Paradowski" means Reginald married Donna
            match = re.search(r'(\w+)\s*\((\w+(?:\s+\w+)?)\)\s+(\w+)', ctx)
            if match:
                first_name = match.group(1)
                spouse_first = match.group(2)
                surname = match.group(3)
                # Check if this person matches the pattern
                if first_name.lower() in name.lower():
                    # Find the spouse
                    spouse_full = f"{spouse_first} {surname}"
                    if spouse_full in person_names:
                        pair = (name, spouse_full, 'spouse')
                        pair_reverse = (spouse_full, name, 'spouse')
                        if pair not in existing_pairs and pair_reverse not in existing_pairs:
                            derived_fact = ExtractedFact(
                                obituary_cache_id=obituary_cache_id,
                                fact_type='relationship',
                                subject_name=name,
                                subject_role='in_law',
                                fact_value='spouse',
                                related_name=spouse_full,
                                relationship_type='spouse',
                                extracted_context=f"Derived from pattern: {ctx}",
                                is_inferred=True,
                                inference_basis=f"Name (Spouse) Surname pattern: {first_name} ({spouse_first}) {surname}",
                                confidence_score=0.90
                            )
                            db.add(derived_fact)
                            derived.append(derived_fact)
                            existing_pairs.add(pair)
                            logger.info(f"Derived spouse: {name} married to {spouse_full}")

    # 3. Derive maiden name from "(nee Surname)" pattern in context (MUST come before sibling derivation)
    for fact in existing_facts:
        if fact.extracted_context and 'nee' in fact.extracted_context.lower():
            match = re.search(r'\(nee\s+(\w+)\)', fact.extracted_context, re.IGNORECASE)
            if match:
                maiden = match.group(1)
                # Find the person this applies to - usually the related_name in spouse relationships
                if fact.fact_type == 'relationship' and fact.relationship_type == 'spouse' and fact.related_name:
                    person_name = fact.related_name
                    # Check if we already have a maiden_name for this person
                    existing_maiden = any(
                        f.fact_type == 'maiden_name' and f.subject_name == person_name
                        for f in existing_facts
                    )
                    if not existing_maiden:
                        derived_fact = ExtractedFact(
                            obituary_cache_id=obituary_cache_id,
                            fact_type='maiden_name',
                            subject_name=person_name,
                            subject_role='spouse',
                            fact_value=maiden,
                            extracted_context=f"Derived from: {fact.extracted_context}",
                            is_inferred=True,
                            inference_basis=f"Extracted from (nee {maiden}) pattern",
                            confidence_score=1.0
                        )
                        db.add(derived_fact)
                        derived.append(derived_fact)
                        # Update the maiden_names dict for sibling derivation
                        maiden_names[person_name] = maiden
                        logger.info(f"Derived maiden name: {person_name}'s maiden name is {maiden}")

    # 4. Derive sibling relationships from brother-in-law + maiden name
    if primary_deceased:
        spouse_name = spouses.get(primary_deceased)
        if spouse_name:
            spouse_maiden = maiden_names.get(spouse_name)
            if spouse_maiden:
                # Check for brother-in-law relationships
                for fact in facts_by_type.get('relationship', []):
                    if fact.relationship_type == 'brother_in_law' and fact.related_name:
                        # Check if brother-in-law's surname matches spouse's maiden name
                        bil_name = fact.related_name
                        if spouse_maiden.lower() in bil_name.lower():
                            # This brother-in-law is likely spouse's sibling
                            pair = (bil_name, spouse_name, 'sister')
                            if pair not in existing_pairs:
                                derived_fact = ExtractedFact(
                                    obituary_cache_id=obituary_cache_id,
                                    fact_type='relationship',
                                    subject_name=bil_name,
                                    subject_role='in_law',
                                    fact_value='brother',
                                    related_name=spouse_name,
                                    relationship_type='brother',
                                    extracted_context=f"Derived from: {bil_name} is brother-in-law, {spouse_name}'s maiden name is {spouse_maiden}",
                                    is_inferred=True,
                                    inference_basis=f"{bil_name} has surname {spouse_maiden} matching {spouse_name}'s maiden name",
                                    confidence_score=0.75
                                )
                                db.add(derived_fact)
                                derived.append(derived_fact)
                                existing_pairs.add(pair)
                                logger.info(f"Derived sibling: {bil_name} is brother of {spouse_name}")

    # 5. Derive daughter's maiden name from father's surname
    if primary_deceased:
        # Get the primary deceased's surname
        deceased_surname = primary_deceased.split()[-1] if ' ' in primary_deceased else None
        if deceased_surname:
            # Check for daughters
            for fact in facts_by_type.get('relationship', []) + derived:
                if fact.relationship_type == 'daughter' and fact.related_name:
                    daughter_name = fact.related_name
                    # Check if we already have a maiden_name for this daughter
                    existing_maiden = any(
                        f.fact_type == 'maiden_name' and f.subject_name == daughter_name
                        for f in existing_facts
                    )
                    if not existing_maiden:
                        derived_fact = ExtractedFact(
                            obituary_cache_id=obituary_cache_id,
                            fact_type='maiden_name',
                            subject_name=daughter_name,
                            subject_role='child',
                            fact_value=deceased_surname,
                            extracted_context=f"Derived from: {daughter_name} is daughter of {primary_deceased}",
                            is_inferred=True,
                            inference_basis=f"Daughter's maiden name is father's surname ({deceased_surname})",
                            confidence_score=0.75
                        )
                        db.add(derived_fact)
                        derived.append(derived_fact)
                        logger.info(f"Derived maiden name: {daughter_name}'s maiden name is {deceased_surname}")

    db.commit()
    for fact in derived:
        db.refresh(fact)

    logger.info(f"Derived {len(derived)} additional facts")
    return derived


def get_facts_by_obituary(db: Session, obituary_cache_id: int) -> List[ExtractedFact]:
    """
    Get all facts for a specific obituary.

    Args:
        db: Database session
        obituary_cache_id: ID of obituary in cache

    Returns:
        List of ExtractedFact instances
    """
    return db.query(ExtractedFact).filter(
        ExtractedFact.obituary_cache_id == obituary_cache_id
    ).order_by(ExtractedFact.subject_name, ExtractedFact.fact_type).all()


def get_facts_by_subject(db: Session, subject_name: str) -> List[ExtractedFact]:
    """
    Get all facts for a specific subject across all obituaries.

    Args:
        db: Database session
        subject_name: Name of the subject to search for

    Returns:
        List of ExtractedFact instances
    """
    return db.query(ExtractedFact).filter(
        ExtractedFact.subject_name == subject_name
    ).order_by(ExtractedFact.obituary_cache_id, ExtractedFact.fact_type).all()


def get_unresolved_facts(db: Session) -> List[ExtractedFact]:
    """
    Get all unresolved facts requiring review.

    Args:
        db: Database session

    Returns:
        List of ExtractedFact instances with unresolved status
    """
    return db.query(ExtractedFact).filter(
        ExtractedFact.resolution_status.in_(['unresolved', 'conflicting'])
    ).order_by(ExtractedFact.confidence_score.asc()).all()
