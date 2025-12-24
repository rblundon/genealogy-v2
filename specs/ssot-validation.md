# SSOT Validation Specification

**Document Type**: Spec Anchor (must be written before implementation)  
**Status**: Draft  
**Version**: 1.0  
**Last Updated**: 2024-12-23

## 1. Overview

This specification defines the rules and algorithms for validating all modifications to Gramps Web (the Single Source of Truth). No data may be written to Gramps Web without passing through this validation logic.

### 1.1 Core Principle

**Gramps Web is the authoritative source for all genealogical data.** The MariaDB cache is subordinate and serves only as a staging area and performance optimization. All genealogical queries must read from Gramps Web, and all writes must validate against current Gramps Web state.

### 1.2 Validation Goals

- **Data Integrity**: Prevent corruption of genealogical data
- **User Control**: Require explicit approval for all conflicts
- **Traceability**: Complete audit trail of all modifications
- **Safety**: No automated deletions or destructive updates

## 2. Write Operation Categories

### 2.1 NEW_ENTITY (Safe for Auto-Store)

**Definition**: Entity does not exist in Gramps Web

**Criteria:**
- No matching person record found in Gramps Web
- Name + date + location combination not present
- No potential duplicates flagged by matching algorithm

**Validation Steps:**
1. Query Gramps Web by name (exact, phonetic variations)
2. Query by date range (±5 years for birth/death)
3. Query by location (exact, parent locations)
4. If zero matches → `NEW_ENTITY`
5. If matches found → escalate to `AMBIGUOUS_MATCH`

**Actions:**
- If confidence ≥ `confidence_threshold_auto_store` (default: 0.85):
  - Auto-create in Gramps Web
  - Set `match_status='created'`
  - Add source citation (obituary URL)
  - Log to `audit_log` with `user_action=FALSE`
- If confidence < `confidence_threshold_auto_store`:
  - Set `match_status='review_needed'`
  - Present to user for approval

**Audit Trail:**
```json
{
  "action_type": "CREATE",
  "entity_type": "person",
  "entity_id": null,
  "gramps_record_id": "I0123",
  "user_action": false,
  "details": {
    "obituary_id": 456,
    "confidence": 0.92,
    "auto_stored": true,
    "source_citation": "https://example.com/obituary/123"
  }
}
```

### 2.2 NON_CONFLICTING_ADDITION (Safe for Auto-Apply)

**Definition**: Entity exists in Gramps Web, but extracted data adds new information without contradicting existing data

**Examples:**
- Adding a new source citation to existing person
- Adding a previously unknown middle name
- Adding a previously unknown residence location
- Adding a new relationship not in Gramps Web
- Adding alternate name spelling
- Adding previously unknown event (marriage, residence)

**Validation Steps:**
1. Query Gramps Web for person record by ID
2. Retrieve all attributes, events, relationships
3. Compare extracted data with Gramps data:
   - For each extracted attribute:
     - If attribute is NULL in Gramps → `NON_CONFLICTING_ADDITION`
     - If attribute matches Gramps → `REDUNDANT` (skip)
     - If attribute differs from Gramps → escalate to `CONFLICTING_UPDATE`
4. For relationships:
   - If relationship not in Gramps → `NON_CONFLICTING_ADDITION`
   - If relationship exists with different details → escalate to `CONFLICTING_UPDATE`

**Actions:**
- If confidence ≥ `confidence_threshold_auto_store` (default: 0.85):
  - Auto-apply to Gramps Web (add attribute, create relationship, add event)
  - Set `match_status='matched'`
  - Add source citation
  - Log to `audit_log` with `user_action=FALSE`
- If confidence < `confidence_threshold_auto_store`:
  - Set `match_status='review_needed'`
  - Present to user for approval

**Special Cases:**
- **Alternate Names**: Always add as alternate name, never replace primary name
- **Multiple Locations**: Add as additional residence/event, don't replace
- **Dates with Circa Flag**: If Gramps has exact date and extraction has circa date → flag for review

**Audit Trail:**
```json
{
  "action_type": "ADD_ATTRIBUTE",
  "entity_type": "person",
  "entity_id": 123,
  "gramps_record_id": "I0123",
  "user_action": false,
  "details": {
    "obituary_id": 456,
    "confidence": 0.87,
    "attribute_added": "middle_name",
    "old_value": null,
    "new_value": "Marie",
    "source_citation": "https://example.com/obituary/123"
  }
}
```

### 2.3 CONFLICTING_UPDATE (Always Require Approval)

**Definition**: Extracted data contradicts existing Gramps Web data

**Examples:**
- Different birth dates (Gramps: 1950-01-15, Extracted: 1950-02-20)
- Different death dates or locations
- Contradictory relationships (Gramps: father, Extracted: stepfather)
- Different spouse (Gramps: married to A, Extracted: married to B)
- Gender mismatch (Gramps: M, Extracted: F)
- Conflicting name spelling (substantial difference, not minor variant)

**Validation Steps:**
1. Query Gramps Web for person record by ID
2. Retrieve all attributes, events, relationships
3. Compare extracted data with Gramps data:
   - For each extracted attribute:
     - If value differs from Gramps by more than tolerance threshold → `CONFLICTING_UPDATE`
4. Calculate conflict severity:
   - **CRITICAL**: Gender, relationship type, death date (if Gramps shows living)
   - **HIGH**: Birth date, death date, primary name
   - **MEDIUM**: Location, alternate name, relationship detail
   - **LOW**: Minor spelling variations, date formatting

**Actions:**
- **Always** set `match_status='review_needed'`
- **Never** auto-apply, regardless of confidence
- Present to user with:
  - Side-by-side comparison (Gramps vs. Extracted)
  - Conflict severity indicator
  - Source citations for both versions
  - Resolution options (see section 3)

**Audit Trail:**
```json
{
  "action_type": "CONFLICT_DETECTED",
  "entity_type": "person",
  "entity_id": 123,
  "gramps_record_id": "I0123",
  "user_action": false,
  "details": {
    "obituary_id": 456,
    "confidence": 0.88,
    "conflict_type": "birth_date_mismatch",
    "conflict_severity": "HIGH",
    "gramps_value": "1950-01-15",
    "extracted_value": "1950-02-20",
    "source_citation": "https://example.com/obituary/123"
  }
}
```

### 2.4 AMBIGUOUS_MATCH (Always Require Approval)

**Definition**: Multiple potential matches found in Gramps Web, unclear which is correct

**Criteria:**
- Matching algorithm returns 2+ candidates with similar scores
- Score difference between top candidates < 0.15
- Insufficient data to disambiguate automatically

**Validation Steps:**
1. Query Gramps Web with matching algorithm
2. If multiple candidates with score > 0.70 and score difference < 0.15 → `AMBIGUOUS_MATCH`
3. Rank candidates by:
   - Name similarity score
   - Date proximity
   - Location overlap
   - Existing relationship connections

**Actions:**
- **Always** set `match_status='review_needed'`
- Present to user with:
  - All candidate matches ranked by score
  - Comparison table (name, dates, locations, relationships)
  - Option to select correct match
  - Option to create new record if none match

**Audit Trail:**
```json
{
  "action_type": "AMBIGUOUS_MATCH",
  "entity_type": "person",
  "entity_id": null,
  "gramps_record_id": null,
  "user_action": false,
  "details": {
    "obituary_id": 456,
    "confidence": 0.75,
    "candidates": [
      {"gramps_id": "I0123", "score": 0.82},
      {"gramps_id": "I0456", "score": 0.78}
    ],
    "source_citation": "https://example.com/obituary/123"
  }
}
```

### 2.5 DELETION (Never Automated)

**Definition**: Data suggests entity should be removed (always out of scope for Phase 1)

**Examples:**
- Obituary suggests person is deceased, but Gramps shows living (should add death event, not delete)
- Relationship contradicts Gramps (should flag for review, not delete)
- Duplicate person discovered (merge operation, not deletion)

**Actions:**
- **Phase 1**: No deletion operations supported
- **Future**: Would require explicit user confirmation with multiple warnings
- For now: Flag as `CONFLICTING_UPDATE` or manual action required

## 3. Conflict Resolution Workflow

### 3.1 User Resolution Options

When a `CONFLICTING_UPDATE` is flagged, present user with these options:

**Option 1: KEEP_GRAMPS**
- Ignore extracted data
- Keep Gramps Web data unchanged
- Add obituary as source citation with note "Conflicting data not applied"
- Update `match_status='matched'` (linked but not modified)

**Option 2: USE_EXTRACTED**
- Replace Gramps data with extracted data
- Add obituary as source citation with note "Replaced conflicting data"
- Log original Gramps value in audit trail
- Update `match_status='matched'` (linked and modified)

**Option 3: MERGE_BOTH**
- Keep Gramps data as primary
- Add extracted data as alternate (alternate name, alternate date, note)
- Add obituary as source citation with note "Added as alternate"
- Update `match_status='matched'` (linked and augmented)

**Option 4: MANUAL_EDIT**
- Allow user to manually create resolution
- May combine parts of both versions
- Requires free-text explanation in notes
- Add obituary as source citation with note "Manually resolved"
- Update `match_status='matched'` (linked and manually resolved)

### 3.2 Resolution Confirmation

Before applying any resolution that modifies Gramps Web:

1. Display confirmation dialog:
   - "This will modify existing genealogical data in Gramps Web"
   - Show exactly what will change (before/after)
   - Require explicit "Confirm" button click
2. Log resolution to `audit_log` with `user_action=TRUE`
3. Update `match_status` to `'matched'`
4. Create/update `gramps_record_mapping` entry

## 4. Validation Algorithm

### 4.1 Main Validation Function

```python
def validate_write_operation(
    extracted_person: ExtractedPerson,
    db: Session
) -> ValidationResult:
    """
    Validate whether extracted person can be written to Gramps Web.
    
    Returns:
        ValidationResult with operation type and required actions
    """
    # Step 1: Check for existing match in Gramps Web
    gramps_matches = query_gramps_web_for_matches(extracted_person)
    
    if len(gramps_matches) == 0:
        # NEW_ENTITY: No matches found
        return ValidationResult(
            operation_type=OperationType.NEW_ENTITY,
            requires_approval=(extracted_person.confidence_score < 
                             Config.get_confidence_threshold_auto_store(db)),
            gramps_candidates=[],
            conflicts=[]
        )
    
    if len(gramps_matches) > 1:
        # AMBIGUOUS_MATCH: Multiple potential matches
        if not is_clear_best_match(gramps_matches):
            return ValidationResult(
                operation_type=OperationType.AMBIGUOUS_MATCH,
                requires_approval=True,
                gramps_candidates=gramps_matches,
                conflicts=[]
            )
    
    # Single best match found
    best_match = gramps_matches[0]
    gramps_person = fetch_gramps_person(best_match.gramps_id)
    
    # Step 2: Compare extracted data with Gramps data
    conflicts = detect_conflicts(extracted_person, gramps_person)
    
    if conflicts:
        # CONFLICTING_UPDATE: Data contradicts Gramps
        return ValidationResult(
            operation_type=OperationType.CONFLICTING_UPDATE,
            requires_approval=True,
            gramps_candidates=[best_match],
            conflicts=conflicts
        )
    
    # Step 3: Check for non-conflicting additions
    additions = detect_additions(extracted_person, gramps_person)
    
    if additions:
        # NON_CONFLICTING_ADDITION: New data to add
        return ValidationResult(
            operation_type=OperationType.NON_CONFLICTING_ADDITION,
            requires_approval=(extracted_person.confidence_score < 
                             Config.get_confidence_threshold_auto_store(db)),
            gramps_candidates=[best_match],
            conflicts=[],
            additions=additions
        )
    
    # REDUNDANT: No new information
    return ValidationResult(
        operation_type=OperationType.REDUNDANT,
        requires_approval=False,
        gramps_candidates=[best_match],
        conflicts=[]
    )
```

### 4.2 Conflict Detection Function

```python
def detect_conflicts(
    extracted: ExtractedPerson,
    gramps: GrampsPerson
) -> List[Conflict]:
    """
    Compare extracted person with Gramps person and identify conflicts.
    
    Returns:
        List of Conflict objects with severity and details
    """
    conflicts = []
    
    # Birth date conflict
    if extracted.birth_date and gramps.birth_date:
        if not dates_match_within_tolerance(
            extracted.birth_date, 
            gramps.birth_date,
            tolerance_days=30
        ):
            conflicts.append(Conflict(
                attribute='birth_date',
                severity=ConflictSeverity.HIGH,
                gramps_value=gramps.birth_date,
                extracted_value=extracted.birth_date
            ))
    
    # Death date conflict
    if extracted.death_date and gramps.death_date:
        if not dates_match_within_tolerance(
            extracted.death_date,
            gramps.death_date,
            tolerance_days=7  # Death dates more precise
        ):
            conflicts.append(Conflict(
                attribute='death_date',
                severity=ConflictSeverity.HIGH,
                gramps_value=gramps.death_date,
                extracted_value=extracted.death_date
            ))
    
    # Gender conflict
    if extracted.gender != 'U' and gramps.gender != 'U':
        if extracted.gender != gramps.gender:
            conflicts.append(Conflict(
                attribute='gender',
                severity=ConflictSeverity.CRITICAL,
                gramps_value=gramps.gender,
                extracted_value=extracted.gender
            ))
    
    # Name conflict (substantial difference)
    if not names_are_compatible(extracted.full_name, gramps.full_name):
        conflicts.append(Conflict(
            attribute='name',
            severity=ConflictSeverity.HIGH,
            gramps_value=gramps.full_name,
            extracted_value=extracted.full_name
        ))
    
    # Relationship conflicts (compare with existing relationships)
    for extracted_rel in extracted.relationships:
        gramps_rel = find_matching_relationship(extracted_rel, gramps.relationships)
        if gramps_rel and gramps_rel.type != extracted_rel.type:
            conflicts.append(Conflict(
                attribute='relationship',
                severity=ConflictSeverity.CRITICAL,
                gramps_value=f"{gramps_rel.type} to {gramps_rel.person2_name}",
                extracted_value=f"{extracted_rel.type} to {extracted_rel.person2_name}"
            ))
    
    return conflicts
```

### 4.3 Addition Detection Function

```python
def detect_additions(
    extracted: ExtractedPerson,
    gramps: GrampsPerson
) -> List[Addition]:
    """
    Identify new information that can be added without conflict.
    
    Returns:
        List of Addition objects describing what can be added
    """
    additions = []
    
    # Middle name addition
    if extracted.given_names and not gramps.given_names:
        additions.append(Addition(
            attribute='given_names',
            value=extracted.given_names,
            addition_type=AdditionType.NEW_ATTRIBUTE
        ))
    
    # Maiden name addition
    if extracted.maiden_name and not gramps.maiden_name:
        additions.append(Addition(
            attribute='maiden_name',
            value=extracted.maiden_name,
            addition_type=AdditionType.NEW_ATTRIBUTE
        ))
    
    # Birth location addition
    if extracted.birth_location and not gramps.birth_location:
        additions.append(Addition(
            attribute='birth_location',
            value=extracted.birth_location,
            addition_type=AdditionType.NEW_ATTRIBUTE
        ))
    
    # Death location addition
    if extracted.death_location and not gramps.death_location:
        additions.append(Addition(
            attribute='death_location',
            value=extracted.death_location,
            addition_type=AdditionType.NEW_ATTRIBUTE
        ))
    
    # Residence addition
    if extracted.residence_location and extracted.residence_location not in gramps.residences:
        additions.append(Addition(
            attribute='residence_location',
            value=extracted.residence_location,
            addition_type=AdditionType.NEW_EVENT
        ))
    
    # New relationship addition
    for extracted_rel in extracted.relationships:
        if not find_matching_relationship(extracted_rel, gramps.relationships):
            additions.append(Addition(
                attribute='relationship',
                value=f"{extracted_rel.type} to {extracted_rel.person2_name}",
                addition_type=AdditionType.NEW_RELATIONSHIP
            ))
    
    # Source citation (always an addition)
    additions.append(Addition(
        attribute='source_citation',
        value=extracted.obituary_url,
        addition_type=AdditionType.SOURCE_CITATION
    ))
    
    return additions
```

## 5. Audit Logging Requirements

Every operation that touches Gramps Web must be logged to the `audit_log` table.

### 5.1 Required Fields

```python
@dataclass
class AuditLogEntry:
    action_type: str  # CREATE, ADD_ATTRIBUTE, UPDATE, DELETE, CONFLICT_DETECTED, etc.
    entity_type: str  # person, family, event, source, citation
    entity_id: int | None  # MariaDB extracted_persons.id
    gramps_record_id: str | None  # Gramps internal ID (e.g., "I0123")
    user_action: bool  # TRUE if user-initiated, FALSE if automated
    details: dict  # JSON with operation specifics
    timestamp: datetime  # Auto-set by database
```

### 5.2 Example Audit Log Entries

**Auto-Created Person:**
```python
AuditLogEntry(
    action_type="CREATE",
    entity_type="person",
    entity_id=None,
    gramps_record_id="I0789",
    user_action=False,
    details={
        "obituary_id": 123,
        "confidence": 0.91,
        "auto_stored": True,
        "name": "John Michael Smith",
        "birth_date": "1950-03-15",
        "death_date": "2024-12-01"
    }
)
```

**User-Resolved Conflict:**
```python
AuditLogEntry(
    action_type="CONFLICT_RESOLVED",
    entity_type="person",
    entity_id=456,
    gramps_record_id="I0123",
    user_action=True,
    details={
        "obituary_id": 789,
        "conflict_type": "birth_date_mismatch",
        "resolution": "USE_EXTRACTED",
        "gramps_old_value": "1950-01-15",
        "extracted_value": "1950-02-20",
        "user_note": "Newspaper birth announcement confirms Feb 20"
    }
)
```

**Non-Conflicting Addition:**
```python
AuditLogEntry(
    action_type="ADD_ATTRIBUTE",
    entity_type="person",
    entity_id=456,
    gramps_record_id="I0123",
    user_action=False,
    details={
        "obituary_id": 789,
        "confidence": 0.88,
        "attribute_added": "maiden_name",
        "old_value": None,
        "new_value": "Johnson"
    }
)
```

## 6. Configuration Settings

All thresholds are configurable via the `config_settings` table:

| Setting Key | Default Value | Description |
|-------------|---------------|-------------|
| `confidence_threshold_auto_store` | 0.85 | Minimum confidence for automatic storage without review |
| `confidence_threshold_review` | 0.60 | Minimum confidence to flag for review (below = reject) |
| `always_review` | false | If true, require review even for high-confidence NEW_ENTITY |
| `date_tolerance_birth_days` | 30 | Days tolerance for birth date conflicts (±1 month) |
| `date_tolerance_death_days` | 7 | Days tolerance for death date conflicts (±1 week) |
| `enable_auto_matching` | true | Enable automatic matching algorithm |
| `match_name_threshold` | 0.90 | Fuzzy name match threshold (0.0-1.0) |
| `ambiguous_match_score_diff` | 0.15 | Max score difference to consider match ambiguous |

## 7. Error Handling

### 7.1 Gramps Web API Failures

If Gramps Web API is unreachable or returns errors:

1. Set `processing_status='failed'` in `obituary_cache`
2. Store error details in `processing_queue.error_message`
3. Queue for retry with exponential backoff
4. After `max_retry_attempts` (default: 3), set to `'failed'` permanently
5. Notify user with actionable error message

**Do NOT:**
- Auto-store to cache and bypass Gramps Web validation
- Assume cache is current
- Skip conflict detection

### 7.2 Database Transaction Failures

All Gramps Web write operations must be wrapped in database transactions:

```python
try:
    with db.begin():
        # 1. Validate operation
        validation = validate_write_operation(extracted_person, db)
        
        # 2. Apply to Gramps Web (if approved)
        if not validation.requires_approval:
            gramps_id = create_gramps_person(extracted_person)
            
            # 3. Update cache with Gramps ID
            extracted_person.gramps_person_id = gramps_id
            extracted_person.match_status = 'created'
            db.add(extracted_person)
            
            # 4. Create mapping
            mapping = GrampsRecordMapping(
                obituary_cache_id=extracted_person.obituary_cache_id,
                gramps_record_type='person',
                gramps_record_id=gramps_id,
                extracted_person_id=extracted_person.id
            )
            db.add(mapping)
            
            # 5. Log to audit trail
            log_audit_entry(db, "CREATE", extracted_person, gramps_id)
            
        db.commit()
except IntegrityError as e:
    db.rollback()
    log.error(f"Database integrity error: {e}")
    raise
except GrampsAPIError as e:
    db.rollback()
    log.error(f"Gramps Web API error: {e}")
    raise
```

## 8. Implementation Checklist

Before implementing `services/gramps_connector.py`, ensure:

- [ ] This specification is reviewed and approved
- [ ] `config_settings` table has all required configuration keys
- [ ] `audit_log` table is created and indexed
- [ ] `gramps_record_mapping` table is created with foreign keys
- [ ] Gramps Web API wrapper functions exist (`query_gramps_web_for_matches`, `fetch_gramps_person`, `create_gramps_person`)
- [ ] Matching algorithm is implemented (see `specs/matching-algorithm.md`)
- [ ] Confidence scoring is implemented (see `specs/confidence-scoring.md`)
- [ ] Unit tests are written for validation logic
- [ ] Integration tests are written for Gramps Web API calls

## 9. Testing Requirements

### 9.1 Unit Test Cases

- [ ] `test_new_entity_high_confidence()` - Should auto-store
- [ ] `test_new_entity_low_confidence()` - Should flag for review
- [ ] `test_non_conflicting_addition_middle_name()` - Should auto-add
- [ ] `test_conflicting_birth_date()` - Should flag for review
- [ ] `test_conflicting_relationship()` - Should flag for review (CRITICAL)
- [ ] `test_ambiguous_match_two_candidates()` - Should flag for review
- [ ] `test_redundant_data()` - Should skip, add citation only
- [ ] `test_date_within_tolerance()` - Should not flag as conflict
- [ ] `test_date_outside_tolerance()` - Should flag as conflict

### 9.2 Integration Test Cases

- [ ] `test_gramps_api_unavailable()` - Should queue for retry
- [ ] `test_transaction_rollback_on_error()` - Should not corrupt data
- [ ] `test_audit_log_created_on_all_operations()` - Should have complete trail
- [ ] `test_user_approval_required_for_conflicts()` - Should not auto-apply

## 10. Future Enhancements

**Phase 2+:**
- Batch approval for similar conflicts (e.g., "Apply to all similar cases")
- Machine learning for conflict resolution suggestions
- Confidence score adjustment based on historical accuracy
- Automatic date normalization (e.g., "abt 1950" → 1950 with circa flag)
- Relationship inference (e.g., if A is parent of B, and B is parent of C, then A is grandparent of C)

---

**Approval Status**: [ ] Approved by Ryan  
**Implementation Dependencies**: Matching algorithm, Confidence scoring, Gramps Web API wrapper  
**Related Specs**: `caching-strategy.md`, `confidence-scoring.md`
