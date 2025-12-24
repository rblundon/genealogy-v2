# Confidence Scoring Specification

**Document Type**: Spec Anchor (must be written before implementation)  
**Status**: Draft  
**Version**: 1.0  
**Last Updated**: 2024-12-23

## 1. Overview

This specification defines how confidence scores are calculated for extracted entities (persons and relationships). Confidence scores determine whether data is auto-stored, flagged for review, or rejected.

### 1.1 Scoring Goals

- **Accuracy**: High-confidence extractions should be ≥95% accurate
- **User Trust**: Clear thresholds that users can understand and tune
- **Cost Efficiency**: Minimize manual review burden without sacrificing quality
- **Safety**: Never auto-store ambiguous or conflicting data

### 1.2 Threshold Definitions

| Threshold | Default Value | Action | Expected Accuracy |
|-----------|---------------|--------|-------------------|
| **High Confidence** | ≥0.85 | Auto-store (if non-conflicting) | ≥95% accurate |
| **Medium Confidence** | 0.60-0.84 | Flag for review | 70-94% accurate |
| **Low Confidence** | <0.60 | Reject or flag for review | <70% accurate |

All thresholds are configurable via `config_settings` table.

## 2. Scoring Factors

Confidence score is calculated as a **weighted combination** of multiple factors:

### 2.1 Factor Weights

| Factor | Weight | Description |
|--------|--------|-------------|
| **Name Clarity** | 30% | How explicitly is the person named? |
| **Relationship Clarity** | 25% | How clear are relationship terms? |
| **Date Specificity** | 20% | Are dates exact or approximate? |
| **LLM Confidence** | 15% | Does LLM indicate uncertainty? |
| **Context Quality** | 10% | Is there enough context to validate? |

### 2.2 Detailed Factor Scoring

#### Factor 1: Name Clarity (30% weight)

**Score Calculation:**
```python
def score_name_clarity(person: ExtractedPerson) -> float:
    """
    Score how clearly the person is named.
    
    Returns: 0.0 to 1.0
    """
    score = 0.0
    
    # Full name with first and last (0.50 points)
    if person.given_names and person.surname:
        score += 0.50
    elif person.surname:
        score += 0.30  # Last name only
    elif person.given_names:
        score += 0.20  # First name only
    
    # Middle name or initial (0.15 points)
    if person.given_names and ' ' in person.given_names.strip():
        score += 0.15
    
    # Maiden name mentioned (0.10 points)
    if person.maiden_name:
        score += 0.10
    
    # Title/honorific (Mr., Mrs., Dr.) (0.10 points)
    if has_title(person.full_name):
        score += 0.10
    
    # Nickname in quotes (0.10 points)
    if has_nickname(person.full_name):
        score += 0.10
    
    # Suffix (Jr., Sr., III) (0.05 points)
    if has_suffix(person.full_name):
        score += 0.05
    
    return min(score, 1.0)
```

**Examples:**
- "John Michael Smith Jr." → 1.0 (full name, middle, suffix)
- "Mary Johnson" → 0.50 (first and last only)
- "Smith" → 0.30 (last name only)
- "John" → 0.20 (first name only)

#### Factor 2: Relationship Clarity (25% weight)

**Score Calculation:**
```python
def score_relationship_clarity(relationship_type: str, context: str) -> float:
    """
    Score how clearly the relationship is stated.
    
    Returns: 0.0 to 1.0
    """
    # Explicit terms (1.0 points)
    explicit_terms = {
        'wife', 'husband', 'mother', 'father', 'son', 'daughter',
        'brother', 'sister', 'grandmother', 'grandfather'
    }
    
    # Moderately clear (0.70 points)
    moderate_terms = {
        'spouse', 'parent', 'child', 'sibling', 'grandparent',
        'stepfather', 'stepmother', 'half-brother', 'half-sister'
    }
    
    # Ambiguous (0.40 points)
    ambiguous_terms = {
        'partner', 'companion', 'friend', 'relative', 'family'
    }
    
    rel_lower = relationship_type.lower()
    
    if any(term in rel_lower for term in explicit_terms):
        base_score = 1.0
    elif any(term in rel_lower for term in moderate_terms):
        base_score = 0.70
    elif any(term in rel_lower for term in ambiguous_terms):
        base_score = 0.40
    else:
        base_score = 0.20  # Very unclear
    
    # Bonus: Context contains possessive or explicit connection (0.20 points)
    possessive_patterns = ['his wife', 'her husband', 'their son', 'his mother']
    if any(pattern in context.lower() for pattern in possessive_patterns):
        base_score = min(base_score + 0.20, 1.0)
    
    return base_score
```

**Examples:**
- "his wife Mary Smith" → 1.0 (explicit + possessive)
- "mother, Jane Doe" → 1.0 (explicit)
- "stepfather John" → 0.70 (moderate)
- "partner Chris" → 0.40 (ambiguous)
- "friend Bob" → 0.20 (unclear relationship)

#### Factor 3: Date Specificity (20% weight)

**Score Calculation:**
```python
def score_date_specificity(person: ExtractedPerson) -> float:
    """
    Score how specific dates are.
    
    Returns: 0.0 to 1.0
    """
    score = 0.0
    
    # Birth date specificity
    if person.birth_date:
        if not person.birth_date_circa:
            score += 0.35  # Exact date
        else:
            score += 0.20  # Approximate date
    elif person.age:
        score += 0.15  # Age mentioned (can calculate approximate birth year)
    
    # Death date specificity
    if person.death_date:
        if not person.death_date_circa:
            score += 0.35  # Exact date
        else:
            score += 0.20  # Approximate date
    
    # Locations add context (0.15 points each)
    if person.birth_location:
        score += 0.10
    if person.death_location:
        score += 0.10
    if person.residence_location:
        score += 0.10
    
    return min(score, 1.0)
```

**Examples:**
- "Born March 15, 1950; Died December 1, 2024" → 0.70 (exact dates)
- "Born circa 1950; Died December 1, 2024" → 0.55 (one circa)
- "Age 74; Died December 1, 2024" → 0.50 (age + exact death)
- "Died December 1, 2024, Springfield" → 0.45 (death date + location)

#### Factor 4: LLM Confidence (15% weight)

**Score Calculation:**
```python
def score_llm_confidence(llm_response: dict) -> float:
    """
    Extract confidence from LLM response metadata.
    
    LLM should return confidence in JSON:
    {
        "persons": [
            {
                "name": "John Smith",
                "confidence": 0.95,
                "uncertainty_factors": []
            }
        ]
    }
    
    Returns: 0.0 to 1.0
    """
    # If LLM provides explicit confidence, use it
    if 'confidence' in llm_response:
        llm_confidence = llm_response['confidence']
    else:
        # Otherwise, infer from uncertainty factors
        uncertainty_factors = llm_response.get('uncertainty_factors', [])
        if not uncertainty_factors:
            llm_confidence = 0.90  # No uncertainties mentioned
        else:
            # Deduct 0.15 per uncertainty factor
            llm_confidence = max(0.0, 0.90 - (len(uncertainty_factors) * 0.15))
    
    return llm_confidence
```

**LLM Prompt Guidance:**
```
For each person, provide a confidence score (0.0-1.0) and list any uncertainty factors:
- Missing key information (age, dates, relationships)
- Ambiguous pronouns or references
- Contradictory statements
- Unclear relationship terms
- Potential name misspellings
```

#### Factor 5: Context Quality (10% weight)

**Score Calculation:**
```python
def score_context_quality(obituary_text: str, person: ExtractedPerson) -> float:
    """
    Score the quality of context around the person.
    
    Returns: 0.0 to 1.0
    """
    score = 0.0
    
    # Length of obituary (more context = higher confidence)
    word_count = len(obituary_text.split())
    if word_count > 500:
        score += 0.30
    elif word_count > 300:
        score += 0.20
    elif word_count > 150:
        score += 0.10
    
    # Number of relationships mentioned
    relationship_count = len(person.relationships)
    if relationship_count >= 3:
        score += 0.30
    elif relationship_count >= 2:
        score += 0.20
    elif relationship_count >= 1:
        score += 0.10
    
    # Structured sections (Born:, Survived by:, Preceded by:)
    structured_keywords = ['survived by', 'preceded by', 'born', 'died', 'married']
    if sum(1 for kw in structured_keywords if kw in obituary_text.lower()) >= 3:
        score += 0.20
    elif sum(1 for kw in structured_keywords if kw in obituary_text.lower()) >= 2:
        score += 0.10
    
    # Multiple specific details (education, career, military, hobbies)
    detail_keywords = ['graduated', 'served', 'worked', 'retired', 'enjoyed', 'loved']
    if sum(1 for kw in detail_keywords if kw in obituary_text.lower()) >= 2:
        score += 0.20
    
    return min(score, 1.0)
```

## 3. Combined Confidence Score

### 3.1 Final Score Calculation

```python
def calculate_confidence_score(
    person: ExtractedPerson,
    llm_response: dict,
    obituary_text: str
) -> float:
    """
    Calculate final weighted confidence score.
    
    Returns: 0.0 to 1.0
    """
    weights = {
        'name_clarity': 0.30,
        'relationship_clarity': 0.25,
        'date_specificity': 0.20,
        'llm_confidence': 0.15,
        'context_quality': 0.10
    }
    
    scores = {
        'name_clarity': score_name_clarity(person),
        'relationship_clarity': score_relationship_clarity_average(person),
        'date_specificity': score_date_specificity(person),
        'llm_confidence': score_llm_confidence(llm_response),
        'context_quality': score_context_quality(obituary_text, person)
    }
    
    # Weighted sum
    final_score = sum(scores[k] * weights[k] for k in weights)
    
    # Apply penalties (see section 3.2)
    final_score = apply_penalties(final_score, person)
    
    # Round to 2 decimal places
    return round(final_score, 2)
```

### 3.2 Confidence Penalties

**Penalty Conditions:**

1. **Missing Critical Info** (-0.20)
   - No surname for non-deceased person
   - No relationship type specified
   - No dates and no age

2. **Conflicting Data Detected** (-0.30)
   - Gender ambiguity (pronouns don't match extracted gender)
   - Date inconsistencies (death before birth, age doesn't match dates)
   - Relationship contradictions

3. **Ambiguous Pronouns** (-0.10)
   - Excessive use of "he", "she", "they" without clear antecedent
   - Multiple people with same first name

4. **Poor Source Quality** (-0.15)
   - Very short obituary (<100 words)
   - Missing key sections ("Survived by", "Born", etc.)
   - Scanned text with OCR errors

```python
def apply_penalties(score: float, person: ExtractedPerson) -> float:
    """
    Apply penalties for various issues.
    """
    # Missing critical info
    if not person.surname and not person.is_deceased_primary:
        score -= 0.20
    
    # No dates and no age
    if not person.birth_date and not person.death_date and not person.age:
        score -= 0.20
    
    # Conflicting data (dates don't make sense)
    if person.birth_date and person.death_date:
        if person.death_date < person.birth_date:
            score -= 0.30
    
    if person.age and person.birth_date and person.death_date:
        calculated_age = (person.death_date - person.birth_date).days // 365
        if abs(calculated_age - person.age) > 2:  # More than 2 years off
            score -= 0.20
    
    return max(score, 0.0)
```

## 4. Relationship Confidence Scoring

Relationships have separate confidence scores from persons.

```python
def calculate_relationship_confidence(
    relationship: ExtractedRelationship,
    person1: ExtractedPerson,
    person2: ExtractedPerson,
    context: str
) -> float:
    """
    Calculate confidence score for a relationship.
    
    Factors:
    - Relationship term clarity
    - Both persons well-identified
    - Context supports relationship
    """
    # Base score from relationship clarity
    base_score = score_relationship_clarity(relationship.relationship_type, context)
    
    # Adjust based on person confidence
    avg_person_confidence = (person1.confidence_score + person2.confidence_score) / 2
    combined_score = (base_score * 0.70) + (avg_person_confidence * 0.30)
    
    # Bonus: Relationship is reciprocal (parent-child pair detected both ways)
    if relationship.reciprocal_found:
        combined_score = min(combined_score + 0.10, 1.0)
    
    # Bonus: Multiple sources mention same relationship
    if relationship.mention_count > 1:
        combined_score = min(combined_score + 0.05, 1.0)
    
    return round(combined_score, 2)
```

## 5. Threshold-Based Actions

### 5.1 Decision Matrix

```python
def determine_action(
    confidence_score: float,
    match_status: str,
    db: Session
) -> Action:
    """
    Determine action based on confidence score and match status.
    """
    auto_threshold = Config.get_confidence_threshold_auto_store(db)
    review_threshold = Config.get_confidence_threshold_review(db)
    always_review = Config.get_always_review(db)
    
    # Check if user wants to review everything
    if always_review:
        return Action.REVIEW_REQUIRED
    
    # High confidence
    if confidence_score >= auto_threshold:
        if match_status in ['NEW_ENTITY', 'NON_CONFLICTING_ADDITION']:
            return Action.AUTO_STORE
        else:
            # Conflicts always require review regardless of confidence
            return Action.REVIEW_REQUIRED
    
    # Medium confidence
    elif confidence_score >= review_threshold:
        return Action.REVIEW_REQUIRED
    
    # Low confidence
    else:
        return Action.REJECT
```

### 5.2 Action Descriptions

| Action | Description | User Notification |
|--------|-------------|-------------------|
| **AUTO_STORE** | Automatically create in Gramps Web | "Created 5 new records automatically" |
| **REVIEW_REQUIRED** | Flag for manual review | "3 entities require review" |
| **REJECT** | Discard extraction | "2 low-confidence extractions rejected" |

## 6. LLM Prompt Engineering for Confidence

### 6.1 Prompt Template

```python
EXTRACTION_PROMPT = """
Extract all persons mentioned in this obituary and their relationships.

For each person, provide:
- full_name (required)
- given_names, surname, maiden_name (if mentioned)
- age, birth_date, death_date (if mentioned)
- locations (birth, death, residence)
- gender (M/F/U if uncertain)
- is_deceased_primary (true for main subject of obituary)
- confidence (0.0-1.0, based on clarity of information)
- uncertainty_factors (list any ambiguities or missing info)

For each relationship, provide:
- person1_name, person2_name
- relationship_type (spouse, parent, child, sibling, etc.)
- relationship_detail (wife, stepfather, half-sister, etc.)
- confidence (0.0-1.0)
- context (the text snippet that indicates this relationship)

Confidence scoring guidelines:
- 0.90-1.0: Full name with dates, explicit relationship terms
- 0.70-0.89: Full name but approximate dates, or clear relationships
- 0.50-0.69: Partial names, ambiguous relationships
- Below 0.50: Very unclear, missing critical info

Return JSON with this structure:
{
    "deceased_primary": {...},
    "survivors": [...],
    "predeceased": [...],
    "relationships": [...]
}
"""
```

### 6.2 Few-Shot Examples

Include 2-3 examples in the prompt showing how to score confidence:

**Example 1: High Confidence**
```json
{
    "full_name": "Mary Elizabeth Johnson",
    "given_names": "Mary Elizabeth",
    "surname": "Johnson",
    "maiden_name": "Smith",
    "age": 74,
    "birth_date": "1950-03-15",
    "death_date": "2024-12-01",
    "confidence": 0.95,
    "uncertainty_factors": []
}
```

**Example 2: Medium Confidence**
```json
{
    "full_name": "John",
    "given_names": "John",
    "surname": null,
    "relationship_to_deceased": "brother",
    "confidence": 0.65,
    "uncertainty_factors": [
        "No last name provided",
        "No dates or age mentioned"
    ]
}
```

## 7. Confidence Score Tuning

### 7.1 Measuring Accuracy

After processing 50+ obituaries, measure actual accuracy:

```python
def measure_confidence_accuracy(db: Session) -> AccuracyReport:
    """
    Compare predicted confidence with actual user corrections.
    
    Returns: Calibration data for tuning thresholds
    """
    # Get all reviewed entities
    reviewed = db.query(ExtractedPerson).filter(
        ExtractedPerson.match_status.in_(['matched', 'created', 'rejected'])
    ).all()
    
    # Group by confidence buckets
    buckets = {
        'high': [p for p in reviewed if p.confidence_score >= 0.85],
        'medium': [p for p in reviewed if 0.60 <= p.confidence_score < 0.85],
        'low': [p for p in reviewed if p.confidence_score < 0.60]
    }
    
    # Calculate accuracy per bucket
    def calc_accuracy(persons):
        if not persons:
            return 0.0
        correct = len([p for p in persons if p.match_status != 'rejected'])
        return correct / len(persons)
    
    return AccuracyReport(
        high_confidence_accuracy=calc_accuracy(buckets['high']),
        medium_confidence_accuracy=calc_accuracy(buckets['medium']),
        low_confidence_accuracy=calc_accuracy(buckets['low']),
        total_reviewed=len(reviewed)
    )
```

### 7.2 Threshold Adjustment

If measured accuracy doesn't meet targets:

- **High confidence <95% accurate**: Increase `confidence_threshold_auto_store` (e.g., 0.85 → 0.90)
- **Too many false positives**: Increase penalties for missing info
- **Too many false negatives**: Reduce penalties or adjust weights

**Tuning Process:**
1. Process 50 obituaries
2. Measure accuracy with `measure_confidence_accuracy()`
3. Adjust thresholds/weights in `config_settings`
4. Process another 50 obituaries
5. Repeat until targets met

## 8. User Interface Presentation

### 8.1 Visual Indicators

**Color Coding:**
- 🟢 Green (≥0.85): "High confidence - Auto-stored"
- 🟡 Yellow (0.60-0.84): "Medium confidence - Review recommended"
- 🔴 Red (<0.60): "Low confidence - Rejected"

**Progress Bars:**
```
John Michael Smith
Confidence: 87% ████████████████████░░░░░ (High)

Mary Johnson
Confidence: 72% ███████████████░░░░░░░░░░ (Medium)

Bob
Confidence: 45% ██████████░░░░░░░░░░░░░░░ (Low)
```

### 8.2 Confidence Explanation

When user hovers over confidence score, show breakdown:

```
Confidence Score: 87%

Name Clarity:          95% (Full name with middle initial)
Relationship Clarity:  85% (Explicit term: "wife")
Date Specificity:      90% (Exact birth and death dates)
LLM Confidence:        88% (No uncertainty factors)
Context Quality:       75% (Well-structured obituary)

Action: Auto-stored to Gramps Web
```

## 9. Configuration Settings

| Setting Key | Default Value | Description |
|-------------|---------------|-------------|
| `confidence_threshold_auto_store` | 0.85 | Min confidence for auto-store |
| `confidence_threshold_review` | 0.60 | Min confidence for review |
| `always_review` | false | Require review even for high confidence |
| `name_weight` | 0.30 | Weight for name clarity factor |
| `relationship_weight` | 0.25 | Weight for relationship clarity factor |
| `date_weight` | 0.20 | Weight for date specificity factor |
| `llm_weight` | 0.15 | Weight for LLM confidence factor |
| `context_weight` | 0.10 | Weight for context quality factor |

## 10. Implementation Checklist

- [ ] This specification is reviewed and approved
- [ ] Scoring functions implemented (`score_name_clarity`, etc.)
- [ ] Combined score calculation implemented
- [ ] Penalty logic implemented
- [ ] LLM prompt updated with confidence instructions
- [ ] Configuration settings added to database
- [ ] Unit tests for all scoring functions
- [ ] Integration test with real obituaries
- [ ] UI components for confidence visualization

## 11. Testing Requirements

### 11.1 Unit Test Cases

- [ ] `test_name_clarity_full_name()` - Should score 0.50+
- [ ] `test_name_clarity_first_only()` - Should score 0.20
- [ ] `test_relationship_explicit_term()` - Should score 1.0
- [ ] `test_relationship_ambiguous()` - Should score 0.40
- [ ] `test_date_exact()` - Should score 0.70
- [ ] `test_date_circa()` - Should score 0.40
- [ ] `test_penalty_missing_surname()` - Should deduct 0.20
- [ ] `test_penalty_date_conflict()` - Should deduct 0.30
- [ ] `test_combined_score()` - Should weight factors correctly

### 11.2 Accuracy Validation

After processing 50 obituaries:
- [ ] High confidence (≥0.85) accuracy ≥95%
- [ ] Medium confidence (0.60-0.84) accuracy 70-94%
- [ ] Low confidence (<0.60) accuracy <70%

If not met, tune weights and thresholds.

---

**Approval Status**: [ ] Approved by Ryan  
**Implementation Dependencies**: LLM extractor, entity models  
**Related Specs**: `ssot-validation.md`, `caching-strategy.md`
