# Changelog

All notable changes to the Genealogy Research Tool are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
