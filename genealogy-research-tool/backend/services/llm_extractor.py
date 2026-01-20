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
- related_name: (for relationships) OTHER person's FULL NAME
- relationship_type: More specific (son, daughter, wife, husband, grandson, etc.)
- extracted_context: Exact phrase from obituary supporting this fact
- is_inferred: true if inferred (not explicitly stated), false otherwise
- inference_basis: (if inferred) brief explanation
- confidence_score: 0.00 to 1.00

**RELATIONSHIP FACT STRUCTURE (CRITICAL):**
For relationship and marriage facts, you MUST use this exact structure:
- fact_type: "relationship" or "marriage"
- fact_value: The relationship type (MUST be one of: "spouse", "child", "parent", "sibling", "grandchild", "grandparent", "great_grandchild", "in_law")
- related_name: The other person's FULL NAME (e.g., "Amy Blundon", "Patricia Blundon")
- relationship_type: More specific descriptor (e.g., "son", "daughter", "wife", "husband", "brother", "sister", "grandson", "granddaughter")

EXAMPLE - CORRECT relationship fact:
{{
  "fact_type": "relationship",
  "subject_name": "Patricia Blundon",
  "fact_value": "child",
  "related_name": "Ryan Blundon",
  "relationship_type": "son",
  "extracted_context": "Mother of Ryan (Amy)"
}}

EXAMPLE - WRONG (do NOT do this):
{{
  "fact_type": "relationship",
  "subject_name": "Patricia Blundon",
  "fact_value": "Ryan Blundon",  // WRONG - should be relationship type
  "relationship_type": "son"
}}

============================================================================
SECTION 1: MARRIAGE EXTRACTION (CRITICAL - EXTRACT ALL MARRIAGES)
============================================================================

Extract marriage facts for EVERY couple mentioned, not just the deceased's spouse.

**Parenthetical Spouse Pattern:**
"Ryan (Amy)" means Ryan is married to Amy. Extract TWO facts:
1. Ryan is married to Amy
2. Amy is married to Ryan

**Examples:**
Text: "Mother of Ryan (Amy) and Megan (Ross) Wurz"
Extract these marriage facts:
- Ryan married to Amy (from parentheses)
- Megan married to Ross Wurz (from parentheses)

Text: "Sister-in-law of Marty (Katie) Blundon and Monica (Ron) Clasen"
Extract these marriage facts:
- Marty married to Katie
- Monica married to Ron Clasen

Text: "Brother-in-law of Reginald (Donna) Paradowski and Joseph (Rose Mary) Paradowski"
Extract these marriage facts:
- Reginald married to Donna
- Joseph married to Rose Mary

**Marriage Fact Format:**
{{
  "fact_type": "marriage",
  "subject_name": "Ryan Blundon",
  "subject_role": "child",
  "fact_value": "spouse",
  "related_name": "Amy Blundon",
  "relationship_type": "wife",
  "extracted_context": "Ryan (Amy)",
  "is_inferred": false,
  "confidence_score": 1.0
}}

============================================================================
SECTION 2: SURNAME INFERENCE (CRITICAL)
============================================================================

Infer surnames based on family relationships:

**Rule 1: Children inherit parent's surname**
If Patricia Blundon is mother of Ryan, then Ryan's surname is Blundon.
{{
  "fact_type": "surname",
  "subject_name": "Ryan Blundon",
  "fact_value": "Blundon",
  "extracted_context": "Mother of Ryan",
  "is_inferred": true,
  "inference_basis": "Child of Patricia Blundon inherits surname",
  "confidence_score": 0.85
}}

**Rule 2: Spouses share surname (infer from known spouse)**
If Ryan Blundon is married to Amy, Amy's surname is Blundon.
{{
  "fact_type": "surname",
  "subject_name": "Amy Blundon",
  "fact_value": "Blundon",
  "extracted_context": "Ryan (Amy)",
  "is_inferred": true,
  "inference_basis": "Spouse of Ryan Blundon takes married name",
  "confidence_score": 0.75
}}

**Rule 3: Married daughters - infer maiden name from parents**
If Megan Wurz is daughter of Patricia Blundon, Megan's maiden name was Blundon.
{{
  "fact_type": "maiden_name",
  "subject_name": "Megan Wurz",
  "fact_value": "Blundon",
  "extracted_context": "daughter Megan (Ross) Wurz",
  "is_inferred": true,
  "inference_basis": "Daughter of Patricia Blundon, maiden name from parents",
  "confidence_score": 0.80
}}

============================================================================
SECTION 3: DECEASED STATUS EXTRACTION (CRITICAL)
============================================================================

Extract deceased facts from these patterns:

**Pattern 1: "the late [Name]"**
"the late Patricia" → Patricia is deceased
{{
  "fact_type": "deceased",
  "subject_name": "Patricia Blundon",
  "fact_value": "true",
  "extracted_context": "the late Patricia",
  "is_inferred": false,
  "confidence_score": 1.0
}}

**Pattern 2: "preceded in death by [Name]"**
"preceded in death by her mother Mary" → Mary is deceased
{{
  "fact_type": "deceased",
  "subject_name": "Mary",
  "fact_value": "true",
  "extracted_context": "preceded in death by her mother Mary",
  "is_inferred": false,
  "confidence_score": 1.0
}}

**Pattern 3: "reunited with [Name]"**
"now reunited with her husband John" → John is deceased
{{
  "fact_type": "deceased",
  "subject_name": "John",
  "fact_value": "true",
  "extracted_context": "reunited with her husband John",
  "is_inferred": true,
  "inference_basis": "Reunited implies previously deceased",
  "confidence_score": 0.95
}}

**Pattern 4: The obituary subject is always deceased**
Always create a deceased fact for the primary person.

============================================================================
SECTION 4: GRANDCHILD RELATIONSHIPS AND AGES
============================================================================

Extract ALL grandchild and great-grandchild relationships comprehensively.

**When ages appear in parentheses, extract approximate birth year:**
Text: "grandma of Autumn (5) and Caralyn (3)" (deceased died 2008)
Extract:
1. Grandchild relationship for Autumn
2. Grandchild relationship for Caralyn
3. Autumn's approximate birth year: 2003 (2008 - 5)
4. Caralyn's approximate birth year: 2005 (2008 - 3)

{{
  "fact_type": "person_birth_year_approx",
  "subject_name": "Autumn",
  "fact_value": "2003",
  "extracted_context": "Autumn (5)",
  "is_inferred": true,
  "inference_basis": "Age 5 at time of death (2008), birth year = 2008 - 5",
  "confidence_score": 0.75
}}

**Grandchild relationship format:**
{{
  "fact_type": "relationship",
  "subject_name": "Patricia Blundon",
  "fact_value": "grandchild",
  "related_name": "Autumn",
  "relationship_type": "granddaughter",
  "extracted_context": "grandma of Autumn (5)",
  "is_inferred": false,
  "confidence_score": 1.0
}}

============================================================================
SECTION 5: IN-LAW INFERENCE (IMPORTANT)
============================================================================

When someone has in-laws, infer the sibling relationship to the spouse:

**Pattern: "Sister-in-law of Marty" + Patricia married to Steven**
→ Marty is Steven's sibling (brother or sister)

{{
  "fact_type": "relationship",
  "subject_name": "Marty Blundon",
  "fact_value": "sibling",
  "related_name": "Steven Blundon",
  "relationship_type": "brother",
  "extracted_context": "Sister-in-law of Marty (Katie) Blundon",
  "is_inferred": true,
  "inference_basis": "Patricia's sister-in-law is spouse's sibling, Marty is Steven's brother",
  "confidence_score": 0.85
}}

**Pattern: "Brother-in-law of Reginald" + Terrence married to Maxine**
→ Reginald is Maxine's sibling

{{
  "fact_type": "relationship",
  "subject_name": "Reginald Paradowski",
  "fact_value": "sibling",
  "related_name": "Maxine Kaczmarowski",
  "relationship_type": "brother",
  "extracted_context": "Brother-in-law of Reginald (Donna) Paradowski",
  "is_inferred": true,
  "inference_basis": "Terrence's brother-in-law is Maxine's brother",
  "confidence_score": 0.85
}}

============================================================================
SECTION 6: BIDIRECTIONAL RELATIONSHIPS
============================================================================

For every parent-child relationship, create facts in BOTH directions:

If Patricia is mother of Ryan, extract:
1. Patricia → Ryan (child relationship)
2. Ryan → Patricia (parent relationship)

{{
  "fact_type": "relationship",
  "subject_name": "Patricia Blundon",
  "fact_value": "child",
  "related_name": "Ryan Blundon",
  "relationship_type": "son"
}}

{{
  "fact_type": "relationship",
  "subject_name": "Ryan Blundon",
  "fact_value": "parent",
  "related_name": "Patricia Blundon",
  "relationship_type": "mother"
}}

Similarly for grandparent/grandchild, sibling relationships, etc.

============================================================================
MAIDEN NAME EXTRACTION (CRITICAL)
============================================================================

**SPECIAL ATTENTION TO MAIDEN NAMES:**
Look very carefully at the deceased person's name line for maiden name indicators:
- Parentheses with "Nee", "née", "born", or "formerly"
- These are CRITICAL for GEDCOM compliance
- Example: "Smith, Jane (Nee Jones)" → maiden_name fact with value "Jones"

Maiden names appear in several patterns - extract from ANY of these:
1. "(Nee Surname)" or "(née Surname)" → maiden name is "Surname"
2. "(Born Surname)" → maiden name is "Surname"
3. "maiden name Surname" or "née Surname" → maiden name is "Surname"
4. "(formerly Surname)" → maiden name is "Surname"
5. In formal format: "Married-Name, Given (Nee Maiden-Name)" → extract "Maiden-Name"

**MAIDEN NAME EXAMPLES:**

Text: "Blundon, Patricia L. (Nee Kaczmarowski)"
Extract:
{{
  "fact_type": "maiden_name",
  "subject_name": "Patricia L. Blundon",
  "subject_role": "deceased",
  "fact_value": "Kaczmarowski",
  "extracted_context": "(Nee Kaczmarowski)",
  "is_inferred": false,
  "confidence_score": 1.0
}}

Text: "Johnson, Mary Elizabeth (née Smith)"
Extract:
{{
  "fact_type": "maiden_name",
  "subject_name": "Mary Elizabeth Johnson",
  "subject_role": "deceased",
  "fact_value": "Smith",
  "extracted_context": "(née Smith)",
  "is_inferred": false,
  "confidence_score": 1.0
}}

Text: "Kaczmarowski, Maxine V. (NEE Paradowski)"
Extract:
{{
  "fact_type": "maiden_name",
  "subject_name": "Maxine V. Kaczmarowski",
  "subject_role": "deceased",
  "fact_value": "Paradowski",
  "extracted_context": "(NEE Paradowski)",
  "is_inferred": false,
  "confidence_score": 1.0
}}

**IMPORTANT:**
- Maiden names are ALWAYS surnames only (not full names)
- Extract from parenthetical notations in the person's name line
- High confidence (1.0) when explicitly stated with "Nee", "née", or "born"
- Only extract for the person whose name contains the notation
- Case insensitive: "Nee", "NEE", "née" all indicate maiden name

============================================================================
FACT TYPES REFERENCE
============================================================================

- person_name: Full name
- person_nickname: Nickname or alternate name
- person_death_date: Date of death
- person_death_age: Age at death
- person_birth_date: Birth date (rare in obituaries)
- person_birth_year_approx: Approximate birth year (inferred from age)
- person_gender: M or F
- maiden_name: Maiden name (surname before marriage)
- surname: Last name (can be inferred)
- deceased: Whether a person is deceased (true/false)
- relationship: A relationship between two people
- marriage: Marriage relationship (use for spouses)
- marriage_duration: Years married
- location_birth: Birthplace
- location_death: Place of death
- location_residence: Where person lived
- survived_by: Listed in "survived by" section
- preceded_in_death: Listed in "preceded in death by" section

============================================================================
CONFIDENCE SCORING
============================================================================

- 1.00: Explicitly stated, unambiguous ("died December 18, 2008")
- 0.90-0.99: Clearly stated with minor ambiguity
- 0.85-0.89: Inferred from clear context with high confidence
- 0.75-0.84: Inferred from clear context ("his wife Mary" → Mary is spouse)
- 0.60-0.74: Inferred with assumptions (child's surname from parent)
- Below 0.60: Highly uncertain

============================================================================
CRITICAL RULES - READ CAREFULLY
============================================================================

1. Extract EVERY fact you can identify - be comprehensive
2. For relationships, create facts for BOTH directions
3. Extract marriage facts for ALL couples (not just deceased's spouse)
4. Infer surnames from family relationships
5. Extract deceased facts from "the late", "preceded in death by", etc.
6. Extract grandchild relationships AND approximate birth years from ages
7. Infer sibling relationships from in-law mentions
8. Always mark inferred facts as is_inferred: true with inference_basis
9. Include exact supporting text in extracted_context
10. Use confidence scores honestly
11. Return ONLY valid JSON, no markdown

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

    # Convert to ExtractedFact objects with deduplication
    extracted_facts = []
    seen_facts = set()  # Track unique facts to prevent duplicates
    duplicates_skipped = 0

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

        # Create deduplication key from core fact attributes
        dedup_key = (
            fact_data['fact_type'],
            fact_data['subject_name'],
            fact_value,
            fact_data.get('related_name'),
            fact_data.get('relationship_type')
        )

        # Skip if we've already seen this exact fact
        if dedup_key in seen_facts:
            duplicates_skipped += 1
            continue

        seen_facts.add(dedup_key)

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

    print(f"Stored {len(extracted_facts)} unique facts ({duplicates_skipped} duplicates skipped)")

    return extracted_facts


async def process_obituary_full(
    db: Session,
    obituary_cache_id: int,
    obituary_text: str,
    verbose_mode: bool = True
) -> Dict:
    """
    Hybrid extraction pipeline: Rules engine + LLM fallback.

    Phase 1: Rules engine extracts deterministic patterns (~95% of facts)
    Phase 2: LLM can be used for ambiguous cases (optional)

    Args:
        db: Database session
        obituary_cache_id: ID of the obituary in the cache
        obituary_text: The obituary text to extract from
        verbose_mode: If True, add delays between extraction steps for UI visualization

    Returns summary of extraction.
    """
    from services.rules_extractor import RulesExtractor

    # Track facts we've already saved (for incremental saving)
    saved_fact_keys = set()
    extracted_facts = []

    def save_facts_incrementally(facts, step_name):
        """Callback to save facts after each extraction step."""
        nonlocal saved_fact_keys, extracted_facts

        for fact in facts:
            fact_dict = fact.to_dict()

            # Create deduplication key
            dedup_key = (
                fact_dict['fact_type'],
                fact_dict['subject_name'],
                fact_dict['fact_value'],
                fact_dict.get('related_name'),
                fact_dict.get('relationship_type')
            )

            if dedup_key in saved_fact_keys:
                continue
            saved_fact_keys.add(dedup_key)

            db_fact = ExtractedFact(
                obituary_cache_id=obituary_cache_id,
                llm_cache_id=None,  # Rules-based, no LLM cache
                fact_type=fact_dict['fact_type'],
                subject_name=fact_dict['subject_name'],
                subject_role=fact_dict.get('subject_role', 'other'),
                fact_value=fact_dict['fact_value'],
                related_name=fact_dict.get('related_name'),
                relationship_type=fact_dict.get('relationship_type'),
                extracted_context=fact_dict.get('extracted_context'),
                is_inferred=fact_dict.get('is_inferred', False),
                inference_basis=fact_dict.get('inference_basis'),
                confidence_score=fact_dict.get('confidence_score', 1.0)
            )
            db.add(db_fact)
            extracted_facts.append(db_fact)

        # Commit after each step so facts are visible to polling
        if extracted_facts:
            db.commit()
            print(f"[Rules] {step_name}: saved {len(extracted_facts)} facts so far")

    # Phase 1: Rules-based extraction (deterministic, fast, free)
    # Use 1 second delay in verbose mode for UI visualization
    step_delay = 1.0 if verbose_mode else 0.0
    extractor = RulesExtractor(
        step_delay=step_delay,
        on_facts_extracted=save_facts_incrementally if verbose_mode else None
    )
    rules_result = extractor.extract_all(obituary_text)

    # If not in verbose mode, save all facts at once (original behavior)
    if not verbose_mode:
        seen_facts = set()
        for fact_data in rules_result['facts']:
            dedup_key = (
                fact_data['fact_type'],
                fact_data['subject_name'],
                fact_data['fact_value'],
                fact_data.get('related_name'),
                fact_data.get('relationship_type')
            )

            if dedup_key in seen_facts:
                continue
            seen_facts.add(dedup_key)

            fact = ExtractedFact(
                obituary_cache_id=obituary_cache_id,
                llm_cache_id=None,
                fact_type=fact_data['fact_type'],
                subject_name=fact_data['subject_name'],
                subject_role=fact_data.get('subject_role', 'other'),
                fact_value=fact_data['fact_value'],
                related_name=fact_data.get('related_name'),
                relationship_type=fact_data.get('relationship_type'),
                extracted_context=fact_data.get('extracted_context'),
                is_inferred=fact_data.get('is_inferred', False),
                inference_basis=fact_data.get('inference_basis'),
                confidence_score=fact_data.get('confidence_score', 1.0)
            )
            db.add(fact)
            extracted_facts.append(fact)

        db.commit()

    # Refresh to get IDs
    for fact in extracted_facts:
        db.refresh(fact)

    print(f"[Rules] Extracted {len(rules_result['persons'])} persons, {len(extracted_facts)} facts")

    return {
        'persons_extracted': len(rules_result['persons']),
        'facts_extracted': len(extracted_facts),
        'persons': rules_result['persons'],
        'facts': [f.to_dict() for f in extracted_facts]
    }
