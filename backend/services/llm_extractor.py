# FILE: backend/services/llm_extractor.py
# LLM-based fact extraction service for obituaries
# ============================================================================

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import openai
import json
from datetime import datetime
import logging

from models import LLMCache, ExtractedFact
from utils.hash_utils import hash_prompt

logger = logging.getLogger(__name__)


# Note: All curly braces in JSON examples must be doubled ({{ and }}) to escape them
# since we use .format() to insert the obituary text
FACT_EXTRACTION_PROMPT_TEMPLATE = """
You are analyzing an obituary to extract factual claims. Extract EVERY fact you can identify.

For each fact, provide:
- fact_type: Type of claim (person_name, person_death_date, person_death_age, person_birth_date, person_gender, maiden_name, relationship, marriage, location_birth, location_death, location_residence, survived_by, preceded_in_death)
- subject_name: Who this fact is about (full name as stated in obituary)
- subject_role: deceased_primary, spouse, child, parent, sibling, grandchild, grandparent, in_law, other
- fact_value: The value/content of this fact
- related_name: (for relationships only) the other person's name
- relationship_type: (for relationships only) spouse, parent, child, son, daughter, brother, sister, etc.
- extracted_context: The exact phrase from obituary supporting this fact
- is_inferred: true if you had to infer this (not explicitly stated), false otherwise
- inference_basis: (if inferred) brief explanation of your reasoning
- confidence_score: 0.00 to 1.00 based on clarity and certainty

CONFIDENCE SCORING GUIDE:
- 1.00: Explicitly stated, unambiguous (e.g., "died December 18, 2008")
- 0.90-0.99: Clearly stated but minor ambiguity possible
- 0.75-0.89: Inferred from clear context (e.g., "his wife Mary" -> Mary is spouse)
- 0.60-0.74: Inferred with some assumptions (e.g., child's surname from parent)
- Below 0.60: Highly uncertain, multiple interpretations possible

EXAMPLE OBITUARY:
"John Smith, 75, died December 1, 2023. Survived by his wife Mary (nee Johnson) and son Robert."

EXAMPLE OUTPUT:
{{
  "facts": [
    {{
      "fact_type": "person_name",
      "subject_name": "John Smith",
      "subject_role": "deceased_primary",
      "fact_value": "John Smith",
      "extracted_context": "John Smith, 75, died December 1, 2023",
      "is_inferred": false,
      "confidence_score": 1.0
    }},
    {{
      "fact_type": "person_death_age",
      "subject_name": "John Smith",
      "subject_role": "deceased_primary",
      "fact_value": "75",
      "extracted_context": "John Smith, 75",
      "is_inferred": false,
      "confidence_score": 1.0
    }},
    {{
      "fact_type": "person_death_date",
      "subject_name": "John Smith",
      "subject_role": "deceased_primary",
      "fact_value": "December 1, 2023",
      "extracted_context": "died December 1, 2023",
      "is_inferred": false,
      "confidence_score": 1.0
    }},
    {{
      "fact_type": "person_name",
      "subject_name": "Mary Smith",
      "subject_role": "spouse",
      "fact_value": "Mary Smith",
      "extracted_context": "his wife Mary",
      "is_inferred": false,
      "confidence_score": 1.0
    }},
    {{
      "fact_type": "maiden_name",
      "subject_name": "Mary Smith",
      "subject_role": "spouse",
      "fact_value": "Johnson",
      "extracted_context": "(nee Johnson)",
      "is_inferred": false,
      "confidence_score": 1.0
    }},
    {{
      "fact_type": "relationship",
      "subject_name": "John Smith",
      "subject_role": "deceased_primary",
      "related_name": "Mary Smith",
      "relationship_type": "spouse",
      "fact_value": "wife",
      "extracted_context": "his wife Mary",
      "is_inferred": false,
      "confidence_score": 1.0
    }},
    {{
      "fact_type": "survived_by",
      "subject_name": "John Smith",
      "subject_role": "deceased_primary",
      "related_name": "Mary Smith",
      "relationship_type": "spouse",
      "fact_value": "survived by wife",
      "extracted_context": "Survived by his wife Mary",
      "is_inferred": false,
      "confidence_score": 1.0
    }},
    {{
      "fact_type": "person_name",
      "subject_name": "Robert Smith",
      "subject_role": "child",
      "fact_value": "Robert Smith",
      "extracted_context": "son Robert",
      "is_inferred": true,
      "inference_basis": "Inferred surname Smith from father John Smith",
      "confidence_score": 0.75
    }},
    {{
      "fact_type": "relationship",
      "subject_name": "John Smith",
      "subject_role": "deceased_primary",
      "related_name": "Robert Smith",
      "relationship_type": "child",
      "fact_value": "son",
      "extracted_context": "son Robert",
      "is_inferred": false,
      "confidence_score": 1.0
    }}
  ]
}}

IMPORTANT RULES:
1. Extract EVERY fact you can identify, even if confidence is low
2. For relationships, create facts for BOTH people (A->B and B->A if appropriate)
3. Always mark inferred facts as is_inferred: true with inference_basis
4. Include the exact text that supports each fact in extracted_context
5. Return ONLY valid JSON object with a "facts" array, no markdown formatting
6. Use subject_role to categorize the person's role in relation to the deceased

NOW EXTRACT FACTS FROM THIS OBITUARY:

{obituary_text}
"""


async def extract_facts_from_obituary(
    db: Session,
    obituary_cache_id: int,
    obituary_text: str,
    llm_provider: str = "openai",
    model_version: str = "gpt-3.5-turbo"
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

    return extracted_facts


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
