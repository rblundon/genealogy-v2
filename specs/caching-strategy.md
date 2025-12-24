# Caching Strategy Specification

**Document Type**: Spec Anchor (must be written before implementation)  
**Status**: Draft  
**Version**: 1.0  
**Last Updated**: 2024-12-23

## 1. Overview

This specification defines the three-layer caching architecture for the genealogy research tool. Proper caching is critical for cost control (LLM API calls) and performance (web scraping, database queries).

### 1.1 Caching Goals

- **Cost Reduction**: Avoid redundant LLM API calls (target: <$0.10 per obituary)
- **Performance**: Minimize external service latency (web scraping, API calls)
- **Reliability**: Graceful degradation when external services unavailable
- **Scalability**: Support batch processing without overwhelming external APIs

### 1.2 Cache Hit Rate Target

**Overall Target**: ≥70% cache hit rate across all layers

- Layer 1 (Obituary): ≥80% hit rate (same URL processed multiple times)
- Layer 2 (LLM): ≥60% hit rate (similar prompts for similar content)
- Layer 3 (Entities): ≥90% hit rate (queries for existing extractions)

## 2. Three-Layer Cache Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         LAYER 1: OBITUARY CACHE                 │
│   Purpose: Avoid re-scraping same URLs                          │
│   Storage: MariaDB obituary_cache table                         │
│   Key: URL hash (SHA-256)                                       │
│   TTL: 365 days (configurable)                                  │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                         LAYER 2: LLM CACHE                      │
│   Purpose: Avoid re-processing same content with same prompt    │
│   Storage: MariaDB llm_cache table                             │
│   Key: Prompt hash (SHA-256 of prompt + content)               │
│   TTL: No expiry (prompts rarely change)                        │
└─────────────────────────────────────────────────────────────────┐
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                       LAYER 3: ENTITY CACHE                     │
│   Purpose: Store extracted entities for quick retrieval         │
│   Storage: MariaDB extracted_persons, extracted_relationships   │
│   Key: Entity ID                                                │
│   TTL: No expiry (linked to obituary)                           │
└─────────────────────────────────────────────────────────────────┘
```

## 3. Layer 1: Obituary Content Cache

### 3.1 Purpose

Store raw HTML and extracted text from obituary URLs to avoid re-scraping.

### 3.2 Cache Key Generation

```python
def generate_obituary_cache_key(url: str) -> str:
    """
    Generate SHA-256 hash of normalized URL.
    
    Normalization:
    - Convert to lowercase
    - Remove trailing slashes
    - Remove query parameters (except essential ones like 'id')
    - Sort query parameters alphabetically
    """
    from urllib.parse import urlparse, parse_qs, urlencode
    
    parsed = urlparse(url.lower().strip())
    
    # Keep only essential query params
    essential_params = ['id', 'pid', 'obituary_id', 'person_id']
    query_dict = parse_qs(parsed.query)
    filtered_query = {k: v for k, v in query_dict.items() if k in essential_params}
    normalized_query = urlencode(sorted(filtered_query.items()))
    
    # Reconstruct normalized URL
    normalized_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if normalized_query:
        normalized_url += f"?{normalized_query}"
    
    # Generate hash
    return hashlib.sha256(normalized_url.encode('utf-8')).hexdigest()
```

### 3.3 Cache Lookup Logic

```python
def fetch_obituary_with_cache(url: str, db: Session) -> ObituaryContent:
    """
    Fetch obituary content with cache lookup.
    
    Returns:
        ObituaryContent with cache_hit flag
    """
    # Step 1: Generate cache key
    url_hash = generate_obituary_cache_key(url)
    
    # Step 2: Check cache
    cached = db.query(ObituaryCache).filter(
        ObituaryCache.url_hash == url_hash
    ).first()
    
    if cached:
        # Check if stale (exceeds TTL)
        cache_age_days = (datetime.now() - cached.fetch_timestamp).days
        max_age_days = Config.get(db, 'cache_expiry_days', 365)
        
        if cache_age_days < max_age_days:
            # Cache hit: Update last_accessed timestamp
            cached.last_accessed = datetime.now()
            db.commit()
            
            log.info(f"Obituary cache HIT: {url} (age: {cache_age_days} days)")
            return ObituaryContent(
                url=cached.url,
                raw_html=cached.raw_html,
                extracted_text=cached.extracted_text,
                cache_hit=True
            )
        else:
            log.info(f"Obituary cache STALE: {url} (age: {cache_age_days} days)")
    
    # Step 3: Cache miss - fetch from web
    log.info(f"Obituary cache MISS: {url}")
    content = scrape_obituary_from_web(url)
    
    # Step 4: Store in cache
    store_obituary_in_cache(url, url_hash, content, db)
    
    return ObituaryContent(
        url=url,
        raw_html=content.raw_html,
        extracted_text=content.extracted_text,
        cache_hit=False
    )
```

### 3.4 Cache Storage

```python
def store_obituary_in_cache(
    url: str,
    url_hash: str,
    content: ScrapedContent,
    db: Session
) -> ObituaryCache:
    """
    Store obituary content in cache.
    
    Handles:
    - Duplicate URL detection (UPSERT)
    - Content hash for change detection
    - Error storage (if fetch failed)
    """
    content_hash = hashlib.sha256(
        content.extracted_text.encode('utf-8')
    ).hexdigest()
    
    # Check if already exists
    existing = db.query(ObituaryCache).filter(
        ObituaryCache.url_hash == url_hash
    ).first()
    
    if existing:
        # Update existing entry
        existing.raw_html = content.raw_html
        existing.extracted_text = content.extracted_text
        existing.content_hash = content_hash
        existing.fetch_timestamp = datetime.now()
        existing.http_status_code = content.status_code
        existing.fetch_error = content.error_message
        existing.processing_status = 'pending'
        cache_entry = existing
    else:
        # Create new entry
        cache_entry = ObituaryCache(
            url=url,
            url_hash=url_hash,
            content_hash=content_hash,
            raw_html=content.raw_html,
            extracted_text=content.extracted_text,
            http_status_code=content.status_code,
            fetch_error=content.error_message,
            processing_status='pending'
        )
        db.add(cache_entry)
    
    db.commit()
    db.refresh(cache_entry)
    return cache_entry
```

### 3.5 Cache Invalidation

**Triggers for invalidation:**
- User explicitly requests "Refresh" or "Re-fetch"
- Content hash changes (obituary updated on source website)
- TTL exceeded (configurable, default: 365 days)

**Invalidation process:**
```python
def invalidate_obituary_cache(obituary_id: int, db: Session) -> None:
    """
    Invalidate obituary cache and all dependent caches.
    
    Cascades to:
    - LLM cache entries linked to this obituary
    - Extracted entities linked to this obituary
    """
    obituary = db.query(ObituaryCache).get(obituary_id)
    if not obituary:
        return
    
    # Mark for re-processing
    obituary.processing_status = 'pending'
    obituary.fetch_timestamp = None  # Force re-fetch
    
    # Delete dependent LLM cache (will be regenerated)
    db.query(LLMCache).filter(
        LLMCache.obituary_cache_id == obituary_id
    ).delete()
    
    # Mark extracted entities as needing re-validation
    db.query(ExtractedPerson).filter(
        ExtractedPerson.obituary_cache_id == obituary_id
    ).update({'match_status': 'unmatched'})
    
    db.commit()
```

## 4. Layer 2: LLM Response Cache

### 4.1 Purpose

Cache LLM API responses to avoid redundant (expensive) calls for same content + prompt combination.

### 4.2 Cache Key Generation

```python
def generate_llm_cache_key(
    prompt: str,
    content: str,
    model: str
) -> str:
    """
    Generate SHA-256 hash of prompt + content + model.
    
    Includes:
    - System prompt
    - User prompt template
    - Obituary content
    - Model version (prompts may work differently per model)
    """
    combined = f"{prompt}|{content}|{model}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()
```

### 4.3 Cache Lookup Logic

```python
def call_llm_with_cache(
    prompt: str,
    obituary_text: str,
    obituary_id: int,
    db: Session
) -> LLMResponse:
    """
    Call LLM API with cache lookup.
    
    Returns:
        LLMResponse with cache_hit flag and cost info
    """
    provider = Config.get(db, 'llm_default_provider', 'openai')
    model = Config.get(db, 'llm_default_model', 'gpt-4-turbo-preview')
    
    # Step 1: Generate cache key
    prompt_hash = generate_llm_cache_key(prompt, obituary_text, model)
    
    # Step 2: Check cache
    cached = db.query(LLMCache).filter(
        LLMCache.prompt_hash == prompt_hash,
        LLMCache.llm_provider == provider,
        LLMCache.model_version == model
    ).first()
    
    if cached and cached.response_text:
        # Cache hit
        log.info(f"LLM cache HIT: {prompt_hash[:8]}... (saved ${cached.cost_usd:.4f})")
        return LLMResponse(
            text=cached.response_text,
            parsed_json=cached.parsed_json,
            cache_hit=True,
            cost_usd=0.0,  # No cost for cache hit
            tokens_used=0
        )
    
    # Step 3: Cache miss - call API
    log.info(f"LLM cache MISS: {prompt_hash[:8]}...")
    start_time = time.time()
    
    response = call_openai_api(prompt, obituary_text, model)
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Step 4: Store in cache
    store_llm_response_in_cache(
        obituary_id=obituary_id,
        prompt_hash=prompt_hash,
        prompt=prompt,
        response=response,
        provider=provider,
        model=model,
        duration_ms=duration_ms,
        db=db
    )
    
    return LLMResponse(
        text=response.text,
        parsed_json=response.parsed_json,
        cache_hit=False,
        cost_usd=response.cost_usd,
        tokens_used=response.tokens_used
    )
```

### 4.4 Cache Storage

```python
def store_llm_response_in_cache(
    obituary_id: int,
    prompt_hash: str,
    prompt: str,
    response: OpenAIResponse,
    provider: str,
    model: str,
    duration_ms: int,
    db: Session
) -> LLMCache:
    """
    Store LLM response in cache with token usage and cost.
    """
    cache_entry = LLMCache(
        obituary_cache_id=obituary_id,
        llm_provider=provider,
        model_version=model,
        prompt_hash=prompt_hash,
        prompt_text=prompt,
        response_text=response.text,
        parsed_json=response.parsed_json,
        token_usage_prompt=response.prompt_tokens,
        token_usage_completion=response.completion_tokens,
        token_usage_total=response.total_tokens,
        cost_usd=response.cost_usd,
        request_timestamp=datetime.now(),
        response_timestamp=datetime.now(),
        duration_ms=duration_ms,
        api_error=response.error_message
    )
    
    db.add(cache_entry)
    db.commit()
    db.refresh(cache_entry)
    
    # Log cost for tracking
    log.info(f"LLM API call: ${response.cost_usd:.4f}, {response.total_tokens} tokens")
    
    return cache_entry
```

### 4.5 Cache Invalidation

**Triggers for invalidation:**
- Prompt template changes (rare, requires manual invalidation)
- Model upgrade (new model version, requires manual invalidation)
- User requests "Re-process with latest model"

**Invalidation is RARE** because:
- Prompts are stable once tuned
- Model responses are deterministic for same input
- Historical responses remain valid

```python
def invalidate_llm_cache_for_prompt_change(
    old_prompt_template: str,
    db: Session
) -> int:
    """
    Invalidate all LLM cache entries using old prompt template.
    
    Returns:
        Number of entries invalidated
    """
    # This is expensive - only do when prompt fundamentally changes
    count = db.query(LLMCache).filter(
        LLMCache.prompt_text.like(f"%{old_prompt_template}%")
    ).delete()
    
    db.commit()
    log.warning(f"Invalidated {count} LLM cache entries due to prompt change")
    return count
```

## 5. Layer 3: Entity Cache

### 5.1 Purpose

Store extracted entities (persons, relationships) for quick retrieval without re-parsing LLM responses.

### 5.2 Cache Characteristics

- **No TTL**: Entities persist as long as obituary is cached
- **Fast Queries**: Indexed by name, date, location, match_status
- **Linked to Source**: Foreign key to `obituary_cache` and `llm_cache`

### 5.3 Cache Lookup Patterns

**Pattern 1: Get all entities for obituary**
```python
def get_entities_for_obituary(obituary_id: int, db: Session) -> List[ExtractedPerson]:
    """
    Retrieve all extracted persons for a given obituary.
    """
    return db.query(ExtractedPerson).filter(
        ExtractedPerson.obituary_cache_id == obituary_id
    ).order_by(
        ExtractedPerson.is_deceased_primary.desc(),
        ExtractedPerson.confidence_score.desc()
    ).all()
```

**Pattern 2: Get entities requiring review**
```python
def get_entities_requiring_review(db: Session, limit: int = 50) -> List[ExtractedPerson]:
    """
    Retrieve entities flagged for manual review.
    """
    return db.query(ExtractedPerson).filter(
        ExtractedPerson.match_status == 'review_needed'
    ).order_by(
        ExtractedPerson.confidence_score.asc()  # Lowest confidence first
    ).limit(limit).all()
```

**Pattern 3: Search by name**
```python
def search_entities_by_name(name: str, db: Session) -> List[ExtractedPerson]:
    """
    Search cached entities by name (for duplicate detection).
    """
    return db.query(ExtractedPerson).filter(
        or_(
            ExtractedPerson.full_name.ilike(f"%{name}%"),
            ExtractedPerson.surname.ilike(f"%{name}%")
        )
    ).all()
```

### 5.4 Cache Invalidation

**Triggers:**
- Obituary re-processed (cascade delete via foreign key)
- User manually deletes extraction
- Entity matched/stored to Gramps Web (update `match_status`)

**No automatic invalidation** - entities are historical record of extraction.

## 6. Cache Performance Monitoring

### 6.1 Metrics to Track

**Overall Metrics:**
```python
def get_cache_statistics(db: Session, days: int = 30) -> CacheStats:
    """
    Calculate cache hit rates and performance metrics.
    """
    cutoff = datetime.now() - timedelta(days=days)
    
    # Obituary cache stats
    total_requests = count_obituary_requests(db, cutoff)
    cache_hits = count_obituary_cache_hits(db, cutoff)
    
    # LLM cache stats
    total_llm_calls = count_llm_calls(db, cutoff)
    llm_cache_hits = count_llm_cache_hits(db, cutoff)
    total_cost = calculate_total_llm_cost(db, cutoff)
    saved_cost = calculate_saved_llm_cost(db, cutoff)
    
    return CacheStats(
        obituary_hit_rate=cache_hits / total_requests if total_requests > 0 else 0,
        llm_hit_rate=llm_cache_hits / total_llm_calls if total_llm_calls > 0 else 0,
        total_cost_usd=total_cost,
        saved_cost_usd=saved_cost,
        total_requests=total_requests,
        period_days=days
    )
```

**Per-Layer Metrics:**
- Layer 1: Hit rate, average age of cached content, stale entry count
- Layer 2: Hit rate, total cost, saved cost, average tokens per call
- Layer 3: Total entities, entities by match_status, average confidence

### 6.2 Cache Health Checks

```python
def check_cache_health(db: Session) -> CacheHealth:
    """
    Check cache health and identify issues.
    """
    issues = []
    
    # Check for stale obituaries
    stale_count = db.query(ObituaryCache).filter(
        ObituaryCache.fetch_timestamp < datetime.now() - timedelta(days=365)
    ).count()
    if stale_count > 100:
        issues.append(f"{stale_count} stale obituaries (>365 days old)")
    
    # Check for failed fetches
    failed_count = db.query(ObituaryCache).filter(
        ObituaryCache.processing_status == 'failed'
    ).count()
    if failed_count > 0:
        issues.append(f"{failed_count} failed obituary fetches")
    
    # Check LLM cache size
    llm_cache_size = db.query(LLMCache).count()
    if llm_cache_size > 10000:
        issues.append(f"Large LLM cache ({llm_cache_size} entries)")
    
    # Check for entities stuck in review
    stuck_review = db.query(ExtractedPerson).filter(
        ExtractedPerson.match_status == 'review_needed',
        ExtractedPerson.created_timestamp < datetime.now() - timedelta(days=30)
    ).count()
    if stuck_review > 50:
        issues.append(f"{stuck_review} entities in review >30 days")
    
    return CacheHealth(
        healthy=(len(issues) == 0),
        issues=issues
    )
```

## 7. Cache Cleanup & Maintenance

### 7.1 Automatic Cleanup (Scheduled Job)

```python
def cleanup_stale_cache_entries(db: Session, dry_run: bool = True) -> CleanupReport:
    """
    Remove stale cache entries to free space.
    
    Run daily as background job.
    """
    max_age_days = Config.get(db, 'cache_expiry_days', 365)
    cutoff = datetime.now() - timedelta(days=max_age_days)
    
    # Find stale obituaries
    stale_obituaries = db.query(ObituaryCache).filter(
        ObituaryCache.fetch_timestamp < cutoff,
        ObituaryCache.processing_status != 'pending'  # Don't delete if pending
    ).all()
    
    if dry_run:
        log.info(f"DRY RUN: Would delete {len(stale_obituaries)} stale obituaries")
        return CleanupReport(deleted_count=0, dry_run=True)
    
    # Delete stale entries (cascades to LLM cache and entities)
    deleted_count = 0
    for obituary in stale_obituaries:
        db.delete(obituary)
        deleted_count += 1
    
    db.commit()
    log.info(f"Deleted {deleted_count} stale cache entries")
    
    return CleanupReport(deleted_count=deleted_count, dry_run=False)
```

### 7.2 Manual Cleanup (Admin Action)

```python
def cleanup_failed_entries(db: Session) -> int:
    """
    Remove obituaries that failed to fetch after max retries.
    """
    max_retries = Config.get(db, 'max_retry_attempts', 3)
    
    failed = db.query(ObituaryCache).join(ProcessingQueue).filter(
        ProcessingQueue.queue_status == 'failed',
        ProcessingQueue.retry_count >= max_retries
    ).all()
    
    for obituary in failed:
        db.delete(obituary)
    
    db.commit()
    return len(failed)
```

## 8. Configuration Settings

All cache behavior is configurable via `config_settings` table:

| Setting Key | Default Value | Description |
|-------------|---------------|-------------|
| `cache_expiry_days` | 365 | Days before obituary cache is considered stale |
| `enable_llm_cache` | true | Enable/disable LLM response caching |
| `enable_obituary_cache` | true | Enable/disable obituary content caching |
| `cache_cleanup_schedule` | "daily" | How often to run cleanup job |
| `max_llm_cache_entries` | 100000 | Max LLM cache entries (prevents unbounded growth) |
| `max_obituary_cache_size_mb` | 10000 | Max storage for obituary HTML (10GB) |

## 9. Cost Tracking & Reporting

### 9.1 Cost Dashboard Queries

**Daily Cost:**
```sql
SELECT 
    DATE(request_timestamp) as date,
    llm_provider,
    model_version,
    COUNT(*) as request_count,
    SUM(token_usage_total) as total_tokens,
    SUM(cost_usd) as total_cost_usd
FROM llm_cache
WHERE request_timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(request_timestamp), llm_provider, model_version
ORDER BY date DESC;
```

**Cost Savings from Cache:**
```sql
-- Estimate: Cache hits * average cost per call
SELECT 
    COUNT(*) as cache_hits,
    AVG(cost_usd) as avg_cost_per_call,
    COUNT(*) * AVG(cost_usd) as estimated_savings
FROM llm_cache
WHERE request_timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY);
```

### 9.2 Cost Alerts

```python
def check_cost_threshold(db: Session) -> Optional[CostAlert]:
    """
    Check if daily cost exceeds threshold.
    
    Send alert if exceeded.
    """
    threshold = Config.get(db, 'cost_alert_threshold_daily', 10.00)
    
    today_cost = db.query(func.sum(LLMCache.cost_usd)).filter(
        func.date(LLMCache.request_timestamp) == datetime.now().date()
    ).scalar() or 0.0
    
    if today_cost > threshold:
        return CostAlert(
            threshold=threshold,
            actual_cost=today_cost,
            message=f"Daily LLM cost (${today_cost:.2f}) exceeded threshold (${threshold:.2f})"
        )
    
    return None
```

## 10. Implementation Checklist

Before implementing cache managers:

- [ ] This specification is reviewed and approved
- [ ] Database indexes created on:
  - `obituary_cache.url_hash`
  - `obituary_cache.content_hash`
  - `llm_cache.prompt_hash`
  - `llm_cache.llm_provider, llm_cache.model_version`
  - `extracted_persons.obituary_cache_id`
  - `extracted_persons.match_status`
- [ ] Configuration settings added to `config_settings` table
- [ ] Logging configured for cache hit/miss tracking
- [ ] Cost tracking queries tested
- [ ] Cleanup job scheduled (cron or similar)

## 11. Testing Requirements

### 11.1 Unit Test Cases

- [ ] `test_obituary_cache_hit()` - Should return cached content
- [ ] `test_obituary_cache_miss()` - Should fetch from web and cache
- [ ] `test_obituary_cache_stale()` - Should re-fetch if expired
- [ ] `test_llm_cache_hit()` - Should return cached response, cost=0
- [ ] `test_llm_cache_miss()` - Should call API and cache
- [ ] `test_llm_cache_different_model()` - Should miss cache if model differs
- [ ] `test_entity_cache_lookup()` - Should retrieve by various criteria
- [ ] `test_cache_invalidation_cascade()` - Should cascade delete

### 11.2 Integration Test Cases

- [ ] `test_full_pipeline_with_cache()` - Second run should be faster, cheaper
- [ ] `test_cache_hit_rate_measurement()` - Should calculate correctly
- [ ] `test_cost_tracking()` - Should accumulate costs accurately

## 12. Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Obituary cache hit rate | ≥80% | `cache_hits / total_requests` |
| LLM cache hit rate | ≥60% | `llm_cache_hits / total_llm_calls` |
| Entity cache hit rate | ≥90% | `entity_queries_from_cache / total_entity_queries` |
| Cache lookup time | <100ms | p95 query time |
| Cost per obituary (with cache) | <$0.10 | `total_cost / obituaries_processed` |
| Cost savings from cache | ≥60% | `saved_cost / (saved_cost + actual_cost)` |

---

**Approval Status**: [ ] Approved by Ryan  
**Implementation Dependencies**: Database schema, configuration management  
**Related Specs**: `ssot-validation.md`, `confidence-scoring.md`
