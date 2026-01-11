# Changelog

All notable changes to the Genealogy Research Tool are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.1] - 2026-01-10

### Undetected Playwright for Cloudflare Bypass

#### Added
- **Undetected Playwright integration** for Cloudflare bypass
  - Uses patched Chromium to avoid bot detection
  - Stealth browser settings (disable automation flags, realistic headers)
  - Startup verification with clear error messages if not installed

#### Changed
- Replaced standard `playwright` with `undetected-playwright`
- Legacy.com extraction runs inline (no subprocess needed)
- Realistic browser fingerprinting (viewport, user-agent, HTTP headers)
- Automatic `navigator.webdriver` flag removal

#### Technical Details
- Uses `--disable-blink-features=AutomationControlled` flag
- Realistic HTTP headers to mimic human browser
- 3-second wait for JavaScript content rendering
- Multiple CSS selector fallbacks for content extraction

#### Fixed
- **Cloudflare bot detection bypassed** using undetected-playwright
- JavaScript-rendered content extraction now works

---

## [1.2.0] - 2026-01-09

### Phase 3 Stage 4 - URL-Based Obituary Processing

#### Added
- **URL-Based Processing** (`/api/obituaries/process`)
  - Smart detection: URL+text or URL-only input
  - Automatic web scraping with Playwright (JavaScript support)
  - Legacy.com support with site-specific extractors

- **URL Validator Service** (`url_validator.py`)
  - Validates obituary URLs from supported sites
  - Extensible architecture for future site support

- **Obituary Fetcher Service** (`obituary_fetcher.py`)
  - Web scraping with rate limiting (2-second delay)
  - Playwright-based extraction for JavaScript-rendered content
  - Error handling for 404, 403, 429, timeouts

- **Cache Intelligence**
  - Cache hit returns existing data with zero LLM cost
  - Failed fetches automatically retry on next request
  - Status tracking: pending, processing, completed, failed

- **Source Tracking**
  - `gramps_source_id` column in `obituary_cache` table
  - Track which obituaries have Gramps sources created

- **Documentation**
  - `docs/BACKLOG.md` - Future feature backlog

#### Changed
- `ProcessObituaryRequest.obituary_text` is now optional
- If omitted, content is fetched from URL automatically

#### Fixed
- Duplicate source creation (one source per obituary URL)
- Source titles now show deceased person's name
- Cluster ID tracking in extracted facts

---

## [1.1.0] - 2026-01-04

### Phase 3 Stage 3 Fixes

#### Added
- **Cluster ID Enhancement**
  - `subject_cluster_id` and `related_cluster_id` columns in `extracted_facts`
  - Foreign key relationships to `person_clusters`
  - Direct cluster lookup instead of name-based matching

#### Fixed
- Relationship creation now uses `related_cluster_id` for reliable lookup
- API responses include cluster IDs in fact data

---

## [1.0.0] - 2026-01-03

### Phase 3 Stage 3 Complete - Person Creation in Gramps Web

#### Added
- **Person Creation Service** (`gramps_person_creator.py`)
  - Create new people in Gramps from validated clusters
  - GEDCOM-compliant naming (maiden name as primary surname)
  - Automatic birth/death event creation
  - Married name as alternate name type

- **Relationship Creation**
  - Automatic family relationship linking
  - Parent/child relationship detection
  - Spouse relationship detection
  - Fuzzy name matching for related persons

- **Debug Endpoints**
  - `GET /api/gramps/person/{id}/debug` - Full person record inspection
  - Enhanced logging for relationship creation

#### Fixed
- **Event Type Format** - Changed from dict to simple string for Gramps API
- **Name Type Format** - Changed from dict to simple string for Gramps API
- **Fact Assignment** - Facts now correctly assigned to subject's cluster
- **Relationship Matching** - Added name variant and partial matching
- **Person Lookup** - Added fallback to search by gramps_id

#### Known Issues
- Citation linking temporarily disabled due to Gramps API 400 errors

---

## [0.3.0] - 2026-01-03

### Phase 3 Stage 2 - Citation Creation

#### Added
- **Citation Service** (`gramps_citation_service.py`)
  - Create sources and citations in Gramps
  - Link obituaries to Gramps people
  - Audit trail with readable obituary names

- **Cluster-Gramps Linking**
  - `POST /api/clusters/{id}/link-to-gramps` - Link existing cluster to Gramps person
  - `DELETE /api/clusters/{id}/gramps-link` - Unlink cluster from Gramps

- **Audit Trail**
  - `GET /api/gramps/audit-trail` - View all citation operations
  - Denormalized `obituary_name` field for readability

---

## [0.2.5] - 2026-01-03

### Phase 2.5 - Debugging & Fixes

#### Fixed
- Maiden name extraction enhanced with detailed LLM prompt
- "(Nee Surname)" pattern extraction improved
- Cross-obituary clustering includes `related_name` from relationship facts

---

## [0.2.0] - 2026-01-02

### Phase 2 - Clustering & Deduplication

#### Added
- **Person Clustering** (`fact_clusterer.py`)
  - Fuzzy name matching using rapidfuzz
  - Cross-obituary person identification
  - Confidence scoring based on multiple sources

- **Cluster Management APIs**
  - `POST /api/clusters/generate` - Generate clusters from all facts
  - `GET /api/clusters` - List all clusters
  - `GET /api/clusters/{id}` - Get cluster details
  - `GET /api/clusters/ready-for-creation` - Get high-confidence clusters

- **Cross-Obituary Analysis**
  - `GET /api/analysis/cross-obituary` - Find people in multiple obituaries

---

## [0.1.0] - 2026-01-01

### Phase 1 - Foundation

#### Added
- **Obituary Processing**
  - `POST /api/obituaries/process` - Process obituary text
  - LLM-based fact extraction using OpenAI GPT-4o
  - Multi-pass extraction (facts, relationships, dates)

- **Data Models**
  - `ObituaryCache` - Stores fetched obituary content
  - `LLMCache` - Caches LLM responses
  - `ExtractedFact` - Individual facts with confidence scores
  - `PersonCluster` - Grouped facts for same person

- **Gramps Integration**
  - `GrampsClient` - API client for Gramps Web
  - JWT authentication
  - Person search and retrieval

- **Infrastructure**
  - FastAPI backend
  - MariaDB database with SQLAlchemy 2.0
  - Podman containerization

---

## Version History Summary

| Version | Date | Phase | Description |
|---------|------|-------|-------------|
| 1.2.1 | 2026-01-10 | 3.4+ | Undetected Playwright for Cloudflare bypass |
| 1.2.0 | 2026-01-09 | 3.4 | URL-based obituary processing |
| 1.1.0 | 2026-01-04 | 3.3+ | Cluster ID tracking fixes |
| 1.0.0 | 2026-01-03 | 3.3 | Person creation with relationships |
| 0.3.0 | 2026-01-03 | 3.2 | Citation creation |
| 0.2.5 | 2026-01-03 | 2.5 | Debugging & fixes |
| 0.2.0 | 2026-01-02 | 2 | Clustering & deduplication |
| 0.1.0 | 2026-01-01 | 1 | Foundation |

---

## Migration Notes

### Upgrading to 1.0.0

No database migrations required. The following changes may affect existing code:

1. **Event Type Format Change**
   - Old: `{'_class': 'EventType', 'string': 'Death'}`
   - New: `'Death'`

2. **Name Type Format Change**
   - Old: `{'_class': 'NameType', 'string': 'Married Name'}`
   - New: `'Married Name'`

3. **Fact Assignment**
   - Relationship facts are now assigned to the subject's cluster
   - Previously assigned to the related person's cluster

### Upgrading to 0.3.0

1. Run database migration to add `obituary_name` field:
   ```sql
   ALTER TABLE gramps_citations ADD COLUMN obituary_name VARCHAR(255);
   ```

---

## Contributors

- Development assisted by Claude Code (Anthropic)
