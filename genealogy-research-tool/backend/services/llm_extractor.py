"""
Multi-pass LLM extraction service.

Pass 1: Extract person mentions with proper handling of:
  - Parenthetical notation: "Ryan (Amy)" = TWO people
  - Nicknames: "Patricia L. 'Patsy'"
  - Maiden names: "(nee Kaczmarowski)"

Pass 2: Extract facts about each person
"""

from typing import List, Dict, Optional
import openai
import json
from datetime import datetime
from sqlalchemy.orm import Session

from models import ObituaryCache, LLMCache, ExtractedFact
from utils.hash_utils import hash_prompt


# ============================================================================
# PASS 1: PERSON MENTION EXTRACTION
# ============================================================================

PERSON_MENTION_PROMPT = """You are analyzing an obituary to identify all people mentioned. Pay careful attention to genealogical notation patterns.

CRITICAL PARSING RULES:

1. PARENTHETICAL NOTATION - "Name1 (Name2)" means TWO people:
   - "Ryan (Amy)" → Ryan AND Amy (Amy is Ryan's spouse)
   - "Patricia (Steve) Blundon" → Patricia Blundon AND Steve Blundon
   - "Reginald (Donna) Paradowski" → Both are Paradowski

2. SURNAME PLACEMENT:
   - After parenthetical: "Ryan (Amy) Blundon" → Both are Blundon
   - Before parenthetical: "Reginald (Donna) Paradowski" → Both are Paradowski
   - No surname: Mark as "surname_unknown"

3. NICKNAMES:
   - "Patricia L. 'Patsy'" → Given: Patricia L., Nickname: Patsy
   - Always extract nicknames in quotes

4. MAIDEN NAMES:
   - "(nee Paradowski)" or "(NEE Paradowski)" → Maiden name, NOT a person
   - "Maxine (nee Paradowski)" → Maxine's maiden name is Paradowski

5. SPECIAL TERMS:
   - "the late" = person is deceased
   - "age X years" or "at the age of X" = extract age
   - "for X years" after marriage = marriage duration

OUTPUT FORMAT:
Return a JSON array of person objects. Each person must have:
- full_name: Complete name as stated
- given_names: First/middle names
- surname: Last name (or "UNKNOWN" if not stated)
- surname_source: "explicit" | "inferred_from_spouse" | "inferred_from_parent" | "unknown"
- maiden_name: If mentioned (otherwise null)
- nickname: If in quotes (otherwise null)
- role: deceased_primary | spouse | child | parent | sibling | grandchild | grandparent | great_grandchild | in_law | other
- is_deceased: true if "the late" or if this is the obituary subject
- spouse_of: Name of spouse if from parenthetical notation
- age: If mentioned
- notes: Any parsing notes

EXAMPLE INPUT:
"Patricia L. 'Patsy' (Nee Kaczmarowski) wife of Steven for 38 years. Mother of Ryan (Amy) and Megan (Ross) Wurz."

EXAMPLE OUTPUT:
[
  {{
    "full_name": "Patricia L. Blundon",
    "given_names": "Patricia L.",
    "surname": "Blundon",
    "surname_source": "inferred_from_spouse",
    "maiden_name": "Kaczmarowski",
    "nickname": "Patsy",
    "role": "deceased_primary",
    "is_deceased": true,
    "spouse_of": "Steven Blundon"
  }},
  {{
    "full_name": "Steven Blundon",
    "given_names": "Steven",
    "surname": "Blundon",
    "surname_source": "explicit",
    "role": "spouse"
  }},
  {{
    "full_name": "Ryan Blundon",
    "given_names": "Ryan",
    "surname": "Blundon",
    "surname_source": "inferred_from_parent",
    "role": "child",
    "spouse_of": "Amy Blundon"
  }},
  {{
    "full_name": "Amy Blundon",
    "given_names": "Amy",
    "surname": "Blundon",
    "surname_source": "inferred_from_spouse",
    "role": "child",
    "spouse_of": "Ryan Blundon"
  }},
  {{
    "full_name": "Megan Wurz",
    "given_names": "Megan",
    "surname": "Wurz",
    "surname_source": "explicit",
    "role": "child",
    "spouse_of": "Ross Wurz",
    "notes": "Maiden name likely Blundon (child of Patricia)"
  }},
  {{
    "full_name": "Ross Wurz",
    "given_names": "Ross",
    "surname": "Wurz",
    "surname_source": "explicit",
    "role": "in_law",
    "spouse_of": "Megan Wurz"
  }}
]

OBITUARY TO ANALYZE:
{obituary_text}

Return ONLY the JSON array, no explanation.
"""


# ============================================================================
# PASS 2: FACT EXTRACTION
# ============================================================================

FACT_EXTRACTION_PROMPT = """You are extracting factual claims from an obituary. You have already identified these people:

{person_list}

Now extract ALL facts about these people. For each fact, provide:
- fact_type: Type of claim (see below)
- subject_name: Full name of who this fact is about
- subject_role: Role from person list above
- fact_value: The value of this fact
- related_name: (for relationships) the other person's name
- relationship_type: (for relationships) spouse, parent, child, son, daughter, brother, sister, etc.
- extracted_context: Exact phrase from obituary supporting this fact
- is_inferred: true if inferred (not explicitly stated), false otherwise
- inference_basis: (if inferred) brief explanation
- confidence_score: 0.00 to 1.00

FACT TYPES:
- person_name: Full name
- person_nickname: Nickname or alternate name
- person_death_date: Date of death
- person_death_age: Age at death
- person_birth_date: Birth date (rare in obituaries)
- person_gender: M or F
- maiden_name: Maiden name (before marriage)
- relationship: A relationship between two people
- marriage: Marriage relationship (use for spouses)
- marriage_duration: Years married
- location_birth: Birthplace
- location_death: Place of death
- location_residence: Where person lived
- survived_by: Listed in "survived by" section
- preceded_in_death: Listed in "preceded in death by" section

CONFIDENCE SCORING:
- 1.00: Explicitly stated, unambiguous ("died December 18, 2008")
- 0.90-0.99: Clearly stated with minor ambiguity
- 0.75-0.89: Inferred from clear context ("his wife Mary" → Mary is spouse)
- 0.60-0.74: Inferred with assumptions (child's surname from parent)
- Below 0.60: Highly uncertain

CRITICAL RULES:
1. Extract EVERY fact you can identify
2. For relationships, create facts for BOTH directions when appropriate
3. Always mark inferred facts as is_inferred: true
4. Include exact supporting text in extracted_context
5. Use confidence scores honestly
6. Return ONLY valid JSON, no markdown

OBITUARY TEXT:
{obituary_text}

Extract all facts as a JSON array:
"""


async def extract_person_mentions(
    db: Session,
    obituary_cache_id: int,
    obituary_text: str,
    llm_provider: str = "openai",
    model_version: str = "gpt-3.5-turbo"
) -> tuple[List[Dict], int]:
    """
    PASS 1: Extract person mentions from obituary.

    Returns:
        (list of person dicts, llm_cache_id)
    """

    prompt = PERSON_MENTION_PROMPT.format(obituary_text=obituary_text)
    prompt_hash_value = hash_prompt(prompt)

    # Check cache
    cached = db.query(LLMCache).filter(
        LLMCache.prompt_hash == prompt_hash_value,
        LLMCache.llm_provider == llm_provider
    ).first()

    if cached and cached.parsed_json:
        print(f"Using cached person mention extraction")
        persons = json.loads(cached.parsed_json)
        return persons, cached.id

    # Call OpenAI
    print(f"Extracting person mentions with {model_version}...")
    start_time = datetime.now()

    try:
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=model_version,
            messages=[
                {"role": "system", "content": "You are a genealogy expert extracting person mentions from obituaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )

        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        response_text = response.choices[0].message.content

        # Parse JSON (handle markdown code blocks)
        cleaned = response_text.strip()
        if cleaned.startswith('```'):
            # Remove markdown code fences
            lines = cleaned.split('\n')
            cleaned = '\n'.join(lines[1:-1])

        persons = json.loads(cleaned)

        # Calculate cost
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens

        # GPT-4 Turbo pricing
        cost_usd = (prompt_tokens / 1000 * 0.01 + completion_tokens / 1000 * 0.03)

        # Store in cache
        llm_cache = LLMCache(
            obituary_cache_id=obituary_cache_id,
            llm_provider=llm_provider,
            model_version=model_version,
            prompt_hash=prompt_hash_value,
            prompt_text=prompt,
            response_text=response_text,
            parsed_json=json.dumps(persons),
            token_usage_prompt=prompt_tokens,
            token_usage_completion=completion_tokens,
            token_usage_total=total_tokens,
            cost_usd=str(cost_usd),
            response_timestamp=end_time,
            duration_ms=duration_ms
        )
        db.add(llm_cache)
        db.commit()
        db.refresh(llm_cache)

        print(f"Extracted {len(persons)} person mentions (${cost_usd:.4f}, {total_tokens} tokens)")

        return persons, llm_cache.id

    except Exception as e:
        print(f"LLM extraction failed: {e}")
        # Store error
        llm_cache = LLMCache(
            obituary_cache_id=obituary_cache_id,
            llm_provider=llm_provider,
            model_version=model_version,
            prompt_hash=prompt_hash_value,
            prompt_text=prompt,
            api_error=str(e)
        )
        db.add(llm_cache)
        db.commit()
        raise


async def extract_facts_from_obituary(
    db: Session,
    obituary_cache_id: int,
    obituary_text: str,
    person_mentions: List[Dict],
    llm_provider: str = "openai",
    model_version: str = "gpt-3.5-turbo"
) -> List[ExtractedFact]:
    """
    PASS 2: Extract facts about each person.

    Returns:
        List of ExtractedFact objects (already saved to DB)
    """

    # Format person list for prompt
    person_list = "\n".join([
        f"- {p['full_name']} ({p['role']})"
        for p in person_mentions
    ])

    prompt = FACT_EXTRACTION_PROMPT.format(
        person_list=person_list,
        obituary_text=obituary_text
    )
    prompt_hash_value = hash_prompt(prompt)

    # Check cache
    cached = db.query(LLMCache).filter(
        LLMCache.prompt_hash == prompt_hash_value,
        LLMCache.llm_provider == llm_provider
    ).first()

    if cached and cached.parsed_json:
        print(f"Using cached fact extraction")
        facts_data = json.loads(cached.parsed_json)
        llm_cache_id = cached.id
    else:
        # Call OpenAI
        print(f"Extracting facts with {model_version}...")
        start_time = datetime.now()

        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=model_version,
                messages=[
                    {"role": "system", "content": "You are a genealogy expert extracting facts from obituaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )

            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            response_text = response.choices[0].message.content

            # Parse JSON
            cleaned = response_text.strip()
            if cleaned.startswith('```'):
                lines = cleaned.split('\n')
                cleaned = '\n'.join(lines[1:-1])

            facts_data = json.loads(cleaned)

            # Calculate cost
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens
            cost_usd = (prompt_tokens / 1000 * 0.01 + completion_tokens / 1000 * 0.03)

            # Store in cache
            llm_cache = LLMCache(
                obituary_cache_id=obituary_cache_id,
                llm_provider=llm_provider,
                model_version=model_version,
                prompt_hash=prompt_hash_value,
                prompt_text=prompt,
                response_text=response_text,
                parsed_json=json.dumps(facts_data),
                token_usage_prompt=prompt_tokens,
                token_usage_completion=completion_tokens,
                token_usage_total=total_tokens,
                cost_usd=str(cost_usd),
                response_timestamp=end_time,
                duration_ms=duration_ms
            )
            db.add(llm_cache)
            db.commit()
            db.refresh(llm_cache)

            llm_cache_id = llm_cache.id

            print(f"Extracted {len(facts_data)} facts (${cost_usd:.4f}, {total_tokens} tokens)")

        except Exception as e:
            print(f"Fact extraction failed: {e}")
            llm_cache = LLMCache(
                obituary_cache_id=obituary_cache_id,
                llm_provider=llm_provider,
                model_version=model_version,
                prompt_hash=prompt_hash_value,
                prompt_text=prompt,
                api_error=str(e)
            )
            db.add(llm_cache)
            db.commit()
            raise

    # Convert to ExtractedFact objects
    extracted_facts = []
    for fact_data in facts_data:
        # Skip facts without required fields
        if not fact_data.get('fact_type') or not fact_data.get('subject_name'):
            print(f"Skipping invalid fact: {fact_data}")
            continue

        # Get fact_value, default to subject_name for person_name facts
        fact_value = fact_data.get('fact_value')
        if not fact_value:
            if fact_data.get('fact_type') == 'person_name':
                fact_value = fact_data.get('subject_name')
            elif fact_data.get('fact_type') == 'relationship':
                fact_value = fact_data.get('relationship_type', 'related')
            else:
                fact_value = 'unknown'

        fact = ExtractedFact(
            obituary_cache_id=obituary_cache_id,
            llm_cache_id=llm_cache_id,
            fact_type=fact_data['fact_type'],
            subject_name=fact_data['subject_name'],
            subject_role=fact_data.get('subject_role', 'other'),
            fact_value=fact_value,
            related_name=fact_data.get('related_name'),
            relationship_type=fact_data.get('relationship_type'),
            extracted_context=fact_data.get('extracted_context'),
            source_sentence=fact_data.get('source_sentence'),
            is_inferred=fact_data.get('is_inferred', False),
            inference_basis=fact_data.get('inference_basis'),
            confidence_score=fact_data.get('confidence_score', 0.80)
        )
        db.add(fact)
        extracted_facts.append(fact)

    db.commit()

    # Refresh to get IDs
    for fact in extracted_facts:
        db.refresh(fact)

    print(f"Stored {len(extracted_facts)} facts in database")

    return extracted_facts


async def process_obituary_full(
    db: Session,
    obituary_cache_id: int,
    obituary_text: str
) -> Dict:
    """
    Complete multi-pass extraction pipeline.

    Returns summary of extraction.
    """

    # Pass 1: Person mentions
    persons, person_llm_id = await extract_person_mentions(
        db, obituary_cache_id, obituary_text
    )

    # Pass 2: Facts
    facts = await extract_facts_from_obituary(
        db, obituary_cache_id, obituary_text, persons
    )

    return {
        'persons_extracted': len(persons),
        'facts_extracted': len(facts),
        'persons': persons,
        'facts': [f.to_dict() for f in facts]
    }
