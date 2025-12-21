# Product Requirements Document: Genealogy Research Tool

## 1. Overview

### 1.1 Product Vision
A containerized, web-based genealogy research tool that automates the extraction and organization of family relationship data from multiple sources, streamlining genealogical research by integrating obituaries, public records, and DNA testing data into a centralized, standards-compliant database.

### 1.2 Goals
- Reduce manual data entry time for genealogical research by 80%+
- Automatically extract and structure relationship data from unstructured sources using LLM technology
- Maintain GEDCOM compliance for data portability
- Build a scalable, cost-effective foundation for multi-source data integration
- Minimize external API costs through intelligent caching

### 1.3 Target User
Individual genealogy researchers who want to accelerate their family history research through automated data extraction and relationship mapping.

## 2. Technical Architecture

### 2.1 Technology Stack
- **Backend**: Python with Gramps Web integration
- **Frontend**: JavaScript framework (React/Vue recommended)
- **Primary Database (SSOT)**: Gramps Web (GEDCOM-compliant genealogical data)
- **Cache Database**: MariaDB (obituary content, LLM responses, extracted entities)
- **LLM Provider**: OpenAI (initial), extensible to support multiple providers
- **Containerization**: Podman (development), Kubernetes (production)
- **Container Images**: Development uses bind mounts; Production uses custom-built immutable images
- **Data Standard**: GEDCOM format for all genealogical data
- **Architecture Principles**: Twelve-Factor App methodology (https://12factor.net/)

### 2.1.1 Twelve-Factor App Compliance
The application will be built following the Twelve-Factor App principles:

1. **Codebase**: One codebase tracked in Git, multiple deploys (dev, staging, prod)
2. **Dependencies**: Explicitly declared via requirements.txt/package.json, isolated environments
3. **Config**: Environment variables for all configuration (no hardcoded secrets)
4. **Backing Services**: MariaDB, Gramps Web, OpenAI API treated as attached resources via URLs
5. **Build, Release, Run**: Strict separation using containers and CI/CD
6. **Processes**: Stateless processes; state stored in Gramps Web and MariaDB
7. **Port Binding**: Services export via port binding (no web server dependencies)
8. **Concurrency**: Scale via process model (horizontal scaling of containers)
9. **Disposability**: Fast startup/shutdown, graceful termination
10. **Dev/Prod Parity**: Containers ensure consistent environments
11. **Logs**: Treat logs as event streams (stdout/stderr to container logs)
12. **Admin Processes**: Database migrations, one-off scripts run as separate processes

### 2.1.2 Development vs Production Strategy

**Development Environment (Phase 1 - Current):**
- **Platform**: MacBook Pro with Podman
- **Container Strategy**: Standard base images with bind-mounted source code
- **Benefits**: 
  - Instant code changes without rebuilds
  - Faster iteration for AI co-pilot development
  - Easy debugging and live code modification
  - Rapid prototyping
- **Compose File**: `podman-compose.dev.yml`
- **Image Strategy**: 
  - `python:3.11-slim` base image + mounted `/app` directory
  - `node:20-alpine` base image + mounted frontend code
  - Official `mariadb:10.11` and `grampsweb` images

**Production Environment (Future State):**
- **Platform**: Kubernetes cluster (cloud or on-premise)
- **Container Strategy**: Custom-built immutable images
- **Benefits**:
  - Reproducible deployments
  - Version-tagged releases (semver)
  - Smaller attack surface
  - True 12-factor compliance
  - GitOps-ready
- **Deployment**: Kubernetes manifests or Helm charts
- **Image Strategy**:
  - Multi-stage Docker builds for optimized images
  - Images pushed to container registry (GitHub Container Registry recommended)
  - Immutable tags (never `:latest` in production)
- **CI/CD Pipeline**:
  - Automated builds on Git push
  - Automated testing
  - Automated deployment to staging
  - Manual approval for production
  
**Migration Path (Phase 1 â†’ Production):**
1. Develop with bind mounts on MacBook Pro
2. Create production Dockerfiles with multi-stage builds
3. Set up container registry (ghcr.io)
4. Create Kubernetes manifests
5. Implement CI/CD pipeline (GitHub Actions)
6. Deploy to Kubernetes cluster

### 2.2 Container Architecture

#### Container Services
1. **Frontend Container**: Web UI application
2. **Backend Container**: Python application server with business logic
3. **Gramps Web Container**: Genealogical database and API (Single Source of Truth)
4. **MariaDB Container**: Cache database with performance optimizations
5. **Network**: 
   - Development: Podman network (`genealogy-net`)
   - Production: Kubernetes service mesh

#### Container Communication
- Frontend â†” Backend: REST API
- Backend â†” Gramps Web: Gramps Web REST API
- Backend â†” MariaDB: Database connection with connection pooling
- Backend â†” OpenAI: HTTPS API calls

#### Development Container Configuration
- **Base Images**: Standard images from Docker Hub
- **Code Mounting**: Bind mounts for live code editing
- **Hot Reload**: Enabled for backend (uvicorn --reload) and frontend (Vite HMR)
- **Orchestration**: `podman-compose.dev.yml`
- **Volumes**: Named volumes for databases, bind mounts for code

#### Production Container Configuration
- **Custom Images**: Multi-stage builds for optimized size
- **No Bind Mounts**: Code baked into images (immutable)
- **Image Registry**: GitHub Container Registry (ghcr.io)
- **Image Tags**: Semantic versioning (e.g., `v1.2.3`)
- **Orchestration**: Kubernetes Deployments, Services, ConfigMaps
- **Volumes**: PersistentVolumeClaims for databases
- **Secrets**: Kubernetes Secrets for sensitive data
- **Ingress**: nginx-ingress or similar for external access
- **Scaling**: HorizontalPodAutoscaler for backend pods

### 2.2.1 Single Source of Truth (SSOT) Architecture
**Gramps Web is the authoritative source for all genealogical data.** The MariaDB cache serves only as a performance optimization and staging area for unvalidated data.

**Data Flow Principles:**
1. **Read Operations**: Always read from Gramps Web for current genealogical data
2. **Write Operations**: 
   - **New entities**: Cache â†’ Review â†’ Gramps Web
   - **Updates to existing**: Must validate against Gramps Web before applying
   - **Deletions**: Never automatic; always require explicit user confirmation
3. **Cache Role**: Temporary storage for:
   - Extracted but unvalidated entities
   - LLM responses and obituary content (performance)
   - Processing queue and metadata
4. **Conflict Resolution**: Gramps Web data always wins; cache data is subordinate

**SSOT Rules:**
- **Non-conflicting additions**: Automatically add to Gramps Web if confidence is high
  - Example: New person not in Gramps Web database
  - Example: Additional source citation for existing person
- **Modifications**: Always validate before applying
  - Check if Gramps Web has different birth date â†’ flag for review
  - Check if Gramps Web has different relationship â†’ flag for review
  - User must explicitly approve changes to existing data
- **Deletions**: Never automatic
  - Obituary suggests person is deceased, but Gramps shows living â†’ manual review required
  - Relationship contradicts Gramps data â†’ flag for manual resolution

### 2.2.2 MariaDB Caching Strategy

**Why MariaDB Over Redis:**
- Complex structured data with relationships
- Need for SQL JOINs and complex WHERE clauses
- ACID transactions for data integrity during SSOT validation
- Native JSON support for LLM responses
- Relational integrity for audit trails
- Single database technology reduces complexity

**Performance Optimizations:**
1. **InnoDB Engine**: Default for all persistent tables (ACID compliance)
2. **Proper Indexing**: 
   - URL hash lookups
   - Confidence score filtering
   - Match status queries
   - Timestamp-based queries
3. **Connection Pooling**: SQLAlchemy with 5-10 connections
4. **Query Result Caching**: MariaDB built-in query cache
5. **Optional MEMORY Tables**: For hot data in future phases if needed

**Future Caching Enhancements (Post-Phase 1):**
- Consider Redis for simple key-value lookups (LLM prompt hash â†’ cached response)
- MariaDB MEMORY tables for frequently accessed data
- Application-level caching (Python functools.lru_cache for config settings)
- CDN for frontend assets in production

### 2.3 Data Sources
- **Phase 1**: Obituaries (URL-based input)
- **Future Phases**: 23andMe API, TruePeopleSearch.com
- **Lookup Strategy**: APIs preferred, web scraping as fallback

### 2.4 Core Components

#### Input Handler
- Accept and validate obituary URLs
- Check cache before fetching
- Queue processing jobs

#### Content Fetcher
- Fetch obituary HTML from URL
- Extract clean text content
- Store raw HTML and text in MariaDB cache
- Respect robots.txt and rate limits

#### LLM Extractor
- Send obituary text to OpenAI API with structured extraction prompt
- Parse LLM JSON response for entities and relationships
- Calculate confidence scores
- Cache LLM requests and responses in MariaDB
- Track token usage and costs

#### Entity Processor
- Store extracted persons in MariaDB
- Store extracted relationships in MariaDB
- Apply confidence thresholds for auto-store vs. review

#### Gramps Web Connector
- Query existing Gramps records for potential matches
- Create new person records in Gramps Web
- Create family records linking related individuals
- Add source citations (obituary URLs)
- Update MariaDB with Gramps record IDs

#### Cache Manager
- Check cache before external calls (obituary fetch, LLM API)
- Implement cache invalidation policies
- Provide cache statistics and cost tracking

#### Review Interface
- Display extracted entities requiring manual review
- Allow editing of person data and relationships
- Approve or reject automatic matching
- Manually link to existing Gramps records

## 3. Phase 1 Requirements: Obituary Processing

### 3.1 Functional Requirements

#### FR1: URL Input
- Accept obituary URL through web interface
- Validate URL format and accessibility
- Check MariaDB cache for existing entry (by URL hash)
- Support major obituary platforms (Legacy.com, Tributes.com, funeral homes, newspapers)
- Display cache hit notification to user

#### FR2: Content Extraction
- Fetch obituary content from provided URL (if not cached)
- Extract full text of obituary
- Calculate content hash for change detection
- Store raw HTML and extracted text in `obituary_cache` table
- Record fetch timestamp, HTTP status, any errors
- Handle paywalls and access restrictions gracefully with error messaging
- Respect source websites (user-agent, rate limiting, robots.txt)

#### FR3: LLM-Based Entity Extraction
- Check `llm_cache` for existing extraction (by prompt hash)
- If not cached, send obituary text to OpenAI API with structured prompt
- Prompt LLM to return JSON with:
  - List of all persons mentioned
  - Each person's attributes (name, age, dates, locations, gender)
  - All relationships between persons
  - Confidence scores for each extraction
  - Identification of primary deceased individual
- Parse LLM JSON response
- Store in `llm_cache` table with token usage and cost
- Store extracted persons in `extracted_persons` table
- Store relationships in `extracted_relationships` table

**Entity Attributes to Extract:**
- Full name (required)
- Given names, surname, maiden name
- Age (if mentioned)
- Birth date and location (if mentioned, flag if approximate)
- Death date and location (if mentioned, flag if approximate)
- Residence location
- Gender
- Role (primary deceased vs. survivor/relative)

**Relationship Types to Identify:**
- Spouse/partner
- Parent/child (including step-, adoptive)
- Sibling (including half-, step-)
- Grandparent/grandchild
- In-laws
- Other extended family
- Preceded in death by / Survived by context

**Confidence Scoring Criteria:**
- **High confidence (0.85-1.0)**: Clear relationship terms ("survived by his wife Mary Smith"), full names, specific dates
- **Medium confidence (0.60-0.84)**: Ambiguous terms ("Mary was present"), partial information
- **Low confidence (0.0-0.59)**: Unclear mentions, potential ambiguity

#### FR4: Intelligent Matching & Linking (SSOT-Compliant)
- **Query Gramps Web** (SSOT) for potential matches based on:
  - Name similarity (exact, phonetic, nicknames)
  - Date ranges (birth/death within reasonable window)
  - Location overlap
  - Existing family connections
  
**Matching Logic:**
- For each extracted person:
  - **No match in Gramps Web**: Mark as new entity, safe for auto-create
    - Set `match_status='unmatched'`
    - Can auto-create if confidence â‰¥ threshold
  - **Exact match found**: Link to existing Gramps record
    - Set `match_status='matched'`
    - Store `gramps_person_id`
    - Check for data conflicts (see FR4.1)
  - **Possible matches (ambiguous)**: Flag for manual review
    - Set `match_status='review_needed'`
    - Present all candidates to user

**FR4.1: Conflict Detection and Handling**
When linking to existing Gramps Web records, compare extracted data with SSOT:

- **Non-conflicting additions** (auto-apply if confidence is high):
  - Adding a new source citation to existing person
  - Adding previously unknown middle name
  - Adding previously unknown residence location
  - Adding new relationship not in Gramps Web
  
- **Potential conflicts** (always flag for review):
  - Different birth dates (Gramps: 1950-01-15, Extracted: 1950-02-20)
  - Different death dates or locations
  - Contradictory relationships (Gramps: father, Extracted: stepfather)
  - Different spouse (Gramps: married to A, Extracted: married to B)
  - Gender mismatch
  
- **Conflict resolution workflow**:
  1. Detect conflict by comparing extracted data with Gramps Web data
  2. Set `match_status='review_needed'`
  3. Store both versions in cache with conflict flags
  4. Present to user with side-by-side comparison
  5. User chooses: (a) Keep Gramps data, (b) Accept extracted data, (c) Merge both
  6. Update audit log with user decision

**FR4.2: Data Integrity Safeguards**
- **Never delete from Gramps Web automatically**
- **Never modify existing Gramps Web data without explicit user approval**
- **Always add new source citations when adding/modifying data**
- **Maintain audit trail** of all Gramps Web modifications in `audit_log`

#### FR5: Data Storage with SSOT Validation and Confidence Thresholds
- Check `config_settings` for current thresholds:
  - `confidence_threshold_auto_store` (default: 0.85)
  - `confidence_threshold_review` (default: 0.60)
  - `always_review` flag (default: false)
  
**Storage Logic with SSOT Validation:**

1. **New Entities (not in Gramps Web)**:
   - If `always_review=true`: Queue for review regardless of confidence
   - If confidence â‰¥ `confidence_threshold_auto_store`:
     - Automatically create in Gramps Web
     - Set `match_status='created'`
     - Add source citation (obituary URL)
   - If confidence < `confidence_threshold_auto_store`:
     - Flag for manual review
     - Set `match_status='review_needed'`

2. **Existing Entities (found in Gramps Web - SSOT)**:
   - **Query Gramps Web** for current data (SSOT)
   - **Compare extracted data with Gramps data**:
     
     a. **Non-conflicting additions** (can auto-apply if confidence is high):
        - New source citation
        - Additional name variant
        - New location information
        - New relationship not in Gramps
        - Action: Add to Gramps Web, update `match_status='matched'`
     
     b. **Conflicting information** (always require validation):
        - Different birth/death dates
        - Different relationships
        - Gender mismatch
        - Action: Set `match_status='review_needed'`, store both versions for comparison
     
     c. **Potential deletion/removal**:
        - Obituary suggests person deceased, but Gramps shows living
        - Relationship contradicts Gramps data
        - Action: Never auto-delete, always flag for review

3. **For persons in multiple obituaries**:
   - Link all obituaries as source citations to same Gramps person record
   - If conflicting data across obituaries, flag all conflicts for review
   - Maintain provenance (which data came from which obituary)

**Gramps Web Storage Operations:**
- **CREATE**: New person/family/event records (only if not existing)
- **UPDATE**: Add citations, append notes, add alternate names (non-destructive)
- **MODIFY**: Changes to existing attributes (always require approval)
- **DELETE**: Never automated (would require future enhancement with user confirmation)

**Audit Trail:**
- Log all Gramps Web operations in `audit_log`
- Record: operation type, entity ID, old value, new value, data source (obituary URL)
- User-initiated vs. auto-applied flag
- Timestamp of all operations

#### FR6: Comprehensive Caching System
**Three-Layer Cache:**
1. **Obituary Content Cache** (`obituary_cache` table)
   - Cache raw HTML and extracted text
   - Use URL hash for lookups
   - Include fetch timestamp and content hash
   - Cache hit avoids web scraping

2. **LLM Response Cache** (`llm_cache` table)
   - Cache prompt and response for each LLM call
   - Use prompt hash for deduplication
   - Track provider, model version, tokens, cost
   - Cache hit avoids expensive API calls

3. **Extracted Entity Cache** (`extracted_persons`, `extracted_relationships` tables)
   - Store structured extraction results
   - Enable quick re-processing without LLM calls
   - Support batch operations

**Cache Policies:**
- Obituaries: 365-day expiry (configurable)
- LLM responses: No expiry (prompts rarely change)
- Regular cleanup of stale cache entries
- Track cache hit rate metrics

#### FR7: Manual Review Workflow (SSOT-Aware)
- Display list of entities flagged for review (`match_status='review_needed'`)
- For each entity show:
  - Extracted data from obituary (cached in MariaDB)
  - **Existing Gramps Web data** (if matched) - displayed as SSOT
  - Side-by-side comparison highlighting differences
  - Confidence scores
  - Potential Gramps matches (if ambiguous)
  - Source obituary context
  - Conflict type (if applicable): "Different birth date", "Relationship mismatch", etc.

**Review Actions:**
- For new entities (not in Gramps):
  - Edit extracted data
  - Approve creation in Gramps Web
  - Reject extraction

- For matched entities (in Gramps - SSOT):
  - **View conflict comparison**:
    - Gramps Web value (SSOT) in one column
    - Extracted value in another column
    - Highlight differences in red/yellow
  - **Resolution options**:
    - Keep Gramps data (ignore extraction)
    - Replace with extracted data (update Gramps)
    - Merge both (e.g., add as alternate name/date)
    - Manual edit to create custom resolution
  - **Always require explicit confirmation** for modifications to Gramps data
  
- For ambiguous matches:
  - View all potential Gramps candidates
  - Manually select correct match
  - Create new record if no match is correct
  
**After review:**
- Update `match_status` accordingly
- Apply approved changes to Gramps Web (SSOT)
- Record user decision in `audit_log`
- Add source citation for all applied data

#### FR8: Cost Tracking & Monitoring
- Track all LLM API usage in `llm_cache`:
  - Prompt tokens
  - Completion tokens
  - Total tokens
  - Estimated cost in USD
- Provide dashboard view:
  - Daily/monthly cost trends
  - Cost per obituary processed
  - Cache hit rate (cost savings)
  - Token usage by model
- Alert if daily cost exceeds threshold (configurable)

### 3.2 Non-Functional Requirements

#### NFR1: Data Quality
- Maintain GEDCOM compliance for all Gramps Web data
- Validate extracted data before storage
- Provide mechanism to review and correct extractions
- Audit trail for all automated actions in `audit_log` table
- Data integrity enforced through foreign keys

#### NFR2: Performance
- Process typical obituary (5-15 people) within 30 seconds (including LLM call)
- Cache checks complete in < 100ms
- Support batch processing via `processing_queue` table
- Concurrent processing of multiple obituaries
- Maximum 3 retry attempts for failed operations

#### NFR3: Cost Efficiency
- Target < $0.10 per obituary processed (LLM costs)
- Cache hit rate target: 70%+ for repeated processing
- Automatic batching of requests when possible
- Use GPT-3.5-turbo for initial extraction, GPT-4 only for complex cases (future enhancement)

#### NFR4: Reliability
- Handle network failures with retry logic (max 3 attempts)
- Graceful degradation when LLM API unavailable
- Clear error messages in UI
- All processing jobs tracked in `processing_queue`
- Failed jobs automatically queued for retry

#### NFR5: Scalability
- Containerized architecture supports horizontal scaling
- Database connection pooling
- Async job processing for batch operations
- Prepared for future data sources (23andMe, TruePeopleSearch)

#### NFR6: Maintainability
- Multi-LLM provider architecture (OpenAI initial, others pluggable)
- Tunable confidence thresholds via `config_settings` table
- Comprehensive logging and audit trails
- Database schema supports schema versioning/migrations

#### NFR7: Security & Privacy
- No authentication in Phase 1 (future enhancement)
- Container network isolation
- Secure storage of API keys (environment variables)
- MariaDB with strong password
- Only publicly available obituary data stored

## 4. Data Model

### 4.1 MariaDB Cache Schema
Comprehensive schema defined in separate artifact including:
- `obituary_cache`: Raw content and metadata (performance cache)
- `llm_cache`: LLM requests/responses with cost tracking (cost optimization)
- `extracted_persons`: Identified individuals (staging area for validation)
- `extracted_relationships`: Family connections (staging area)
- `gramps_record_mapping`: Links to Gramps Web records (SSOT references)
- `config_settings`: Tunable parameters
- `processing_queue`: Async job management
- `audit_log`: Complete action history

**Cache vs. SSOT Relationship:**
- MariaDB cache = **staging area** and **performance layer**
- Gramps Web = **Single Source of Truth** for all genealogical data
- Cache stores extracted data awaiting validation
- After validation and storage in Gramps Web, cache serves as reference/audit trail
- **Never query cache for authoritative genealogical data**
- Always query Gramps Web for person/family/relationship lookups

### 4.2 Gramps Web Entities

#### Person Record
- Name (primary and alternate)
- Gender
- Birth event (date, place, circa flag)
- Death event (date, place, circa flag)
- Residence
- Source citations (obituary URL via source records)
- Notes (confidence level, extraction metadata)

#### Family Record
- Relationship type (married, partnered, etc.)
- Connected person IDs (parent1, parent2, children)
- Source citations

#### Event Record
- Event type (birth, death, marriage, etc.)
- Date (with circa flag if approximate)
- Place
- Source citations

#### Source Record
- Title (obituary title or "Obituary of [Name]")
- Publication information
- URL
- Repository (newspaper, funeral home, Legacy.com, etc.)

#### Citation Record
- Links source to person/family/event
- Confidence note
- Page/section (if applicable)

## 5. User Interface Requirements

### 5.1 Phase 1 Interface

#### Home/Input Page
- Single input field for obituary URL
- "Process" button
- Checkbox: "Always require manual review before saving"
- Link to view processing queue
- Link to view entities requiring review
- Link to cost tracking dashboard

#### Processing Page
- Progress indicator with stages:
  - Checking cache...
  - Fetching obituary...
  - Extracting entities with AI...
  - Matching with existing records...
  - Storing data...
- Display cache hit notifications ("Using cached obituary - no fetch needed!")
- Show estimated cost for LLM processing
- Real-time status messages

#### Review Page (Conditional)
- Appears only if entities require review
- **Two-column comparison view** for conflicts:
  - Left column: **Gramps Web data (SSOT)** - highlighted in blue
  - Right column: **Extracted data** - highlighted in orange
  - Differences highlighted in red
- List of extracted persons with:
  - Full details
  - Confidence scores (visual indicator: green/yellow/red)
  - **Conflict indicators** (if matched to existing Gramps record)
  - Potential Gramps matches
  - Source context from obituary
- Edit controls for each person/relationship
- For conflicts with existing Gramps records:
  - **Conflict type label**: "Date mismatch", "Relationship conflict", "Name variant"
  - **Resolution buttons**:
    - "Keep Gramps Data" (ignore extraction)
    - "Use Extracted Data" (update Gramps)
    - "Merge Both" (add as alternate/note)
    - "Edit Manually" (custom resolution)
  - **Warning message**: "This will modify existing genealogical data"
- For new entities (no conflicts):
  - Simple approve/reject interface
  - Edit fields as needed
- Relationship visualization (simple tree or list)
- "Apply Changes to Gramps Web" button (requires confirmation)
- "Discard All" button to cancel
- **Confirmation dialog** before modifying SSOT data

#### Results Page
- Success confirmation
- Summary statistics:
  - X persons processed
  - Y new records created
  - Z records linked/updated
  - Cost: $X.XX (tokens used)
- Links to view new records in Gramps Web
- Cache status (hit/miss)
- "Process Another Obituary" button

#### Cost Dashboard
- Current month cost total
- Cost per obituary (average)
- Token usage chart (daily/weekly/monthly)
- Cache hit rate percentage
- LLM provider/model breakdown
- Configurable cost alert threshold

#### Review Queue Page
- List of all entities flagged for review
- Sortable by confidence score, date, obituary
- Batch review capability
- Filters: by confidence range, by match status

### 5.2 Configuration Page (Admin)
- Tunable thresholds:
  - Auto-store confidence threshold (slider: 0.0-1.0)
  - Review confidence threshold (slider: 0.0-1.0)
  - Always require review (checkbox)
  - Cache expiry days
  - Cost alert threshold
- LLM provider settings:
  - Default provider (dropdown: OpenAI, future: Claude, Ollama)
  - Default model
  - API key management
- Gramps Web connection:
  - URL/hostname
  - API credentials
  - Test connection button

## 6. API & Integration Requirements

### 6.1 Gramps Web API Integration
- Authenticate with Gramps Web instance (API token)
- REST API endpoints:
  - `GET /api/people/` - Search existing persons
  - `POST /api/people/` - Create person record
  - `GET /api/families/` - Search existing families
  - `POST /api/families/` - Create family record
  - `POST /api/events/` - Create event records
  - `POST /api/sources/` - Create source records
  - `POST /api/citations/` - Create citations
- Handle API errors and rate limits gracefully
- Batch operations where possible

### 6.2 OpenAI API Integration
- Use `gpt-4-turbo-preview` or `gpt-3.5-turbo` (configurable)
- Structured prompt engineering:
  - Clear instructions for entity extraction
  - JSON output format specification
  - Examples of desired output
  - Confidence scoring instructions
- Function calling or JSON mode for structured output
- Error handling:
  - Rate limit errors (exponential backoff)
  - Invalid API key
  - Model unavailable
  - Timeout (30s limit)
- Token usage tracking for all calls

### 6.3 Web Scraping Requirements
- Respect robots.txt for all domains
- User-agent: "GenealogyResearchBot/1.0 (+URL_TO_YOUR_REPO)"
- Rate limiting: Max 1 request per 2 seconds per domain
- Timeout: 10 seconds for fetch
- Handle common issues:
  - 404 Not Found
  - 403 Forbidden (paywall)
  - SSL certificate errors
  - Redirect loops
  - JavaScript-rendered content (use Playwright/Selenium if needed)
- Clean HTML extraction (BeautifulSoup/lxml)
- Text extraction (remove scripts, styles, navigation)

### 6.4 MariaDB Integration
- Connection pooling (min: 2, max: 10 connections)
- Parameterized queries (prevent SQL injection)
- Transaction support for multi-table operations
- Schema migration tool (Alembic recommended)
- Backup and restore procedures
- Database initialization script

## 7. Configuration Management

### 7.1 Tunable Parameters (config_settings table)
- `confidence_threshold_auto_store` (float, default: 0.85)
- `confidence_threshold_review` (float, default: 0.60)
- `always_review` (boolean, default: false)
- `cache_expiry_days` (integer, default: 365)
- `max_retry_attempts` (integer, default: 3)
- `llm_default_provider` (string, default: "openai")
- `llm_default_model` (string, default: "gpt-4-turbo-preview")
- `cost_alert_threshold_daily` (float, default: 10.00 USD)
- `enable_auto_matching` (boolean, default: true)
- `match_name_threshold` (float, default: 0.90)

### 7.2 Environment Variables
- `OPENAI_API_KEY` - OpenAI API key
- `GRAMPS_WEB_URL` - Gramps Web instance URL
- `GRAMPS_API_TOKEN` - Gramps Web authentication token
- `MARIADB_HOST` - MariaDB hostname
- `MARIADB_PORT` - MariaDB port (default: 3306)
- `MARIADB_USER` - MariaDB username
- `MARIADB_PASSWORD` - MariaDB password
- `MARIADB_DATABASE` - Database name (default: genealogy_cache)

## 8. Deployment Architecture

### 8.1 Development Deployment (Phase 1)

#### Platform
- **Host**: MacBook Pro
- **Container Runtime**: Podman Desktop
- **Orchestration**: podman-compose

#### Container Configuration
```yaml
# podman-compose.dev.yml approach
services:
  backend:
    image: python:3.11-slim
    volumes:
      - ./backend:/app:rw  # Live code editing
    command: uvicorn main:app --reload --host 0.0.0.0
    
  frontend:
    image: node:20-alpine
    volumes:
      - ./frontend:/app:rw  # Live code editing
    command: npm run dev
```

#### Benefits
- Instant code changes (no rebuild)
- Hot reload for backend and frontend
- Fast iteration with AI co-pilot
- Easy debugging
- Simple local development

#### Limitations
- Not production-ready
- Dependent on local file structure
- Potential environment inconsistencies

### 8.2 Production Deployment (Future State)

#### Platform
- **Host**: Kubernetes cluster (cloud or on-premise)
- **Container Runtime**: containerd or CRI-O
- **Orchestration**: Kubernetes (kubectl, Helm)
- **Image Registry**: GitHub Container Registry (ghcr.io)

#### Custom Image Strategy

**Multi-Stage Dockerfile (Backend Example):**
```dockerfile
# Stage 1: Build dependencies
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Production image
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Benefits:**
- Smaller image size (no build tools in final image)
- Immutable deployments
- Version-tagged releases
- Security scanning in CI/CD
- Reproducible builds

#### Kubernetes Resources

**Deployments:**
- Backend: 2-5 replicas (HorizontalPodAutoscaler)
- Frontend: 2-3 replicas
- Gramps Web: 1 replica (StatefulSet for data)
- MariaDB: 1 replica (StatefulSet with PVC)

**Services:**
- ClusterIP for internal communication
- LoadBalancer or NodePort for external access

**ConfigMaps:**
- Non-sensitive configuration
- Feature flags
- API endpoints

**Secrets:**
- API keys (OpenAI, future LLM providers)
- Database passwords
- Gramps Web API tokens

**PersistentVolumeClaims:**
- MariaDB data (20-50GB)
- Gramps Web database (10-20GB)
- Gramps Web media files (expandable)

**Ingress:**
- nginx-ingress-controller
- TLS certificates (Let's Encrypt)
- Domain routing

### 8.3 Container Orchestration

#### Development (Podman Compose)
- Use podman-compose.dev.yml for multi-container deployment
- Health checks for all services (12-factor: disposability)
- Restart policies: unless-stopped
- Resource limits (CPU, memory) - loose for development
- Logging configuration to stdout/stderr (12-factor: logs as event streams)
- Environment-based configuration (12-factor: config in environment)
- Named volumes for data persistence (12-factor: backing services)
- Bind mounts for source code (development only)

#### Production (Kubernetes)
- Helm charts for templated deployments
- Health checks (liveness, readiness, startup probes)
- Restart policies: Always (with backoff)
- Resource limits and requests (guaranteed QoS)
- Centralized logging (FluentD, Loki, or CloudWatch)
- ConfigMaps and Secrets for configuration
- PersistentVolumeClaims for data persistence
- No bind mounts (immutable images)
- NetworkPolicies for security
- PodDisruptionBudgets for availability
- HorizontalPodAutoscaler for scaling

### 8.4 Twelve-Factor Compliance Checklist

**I. Codebase**
- Single Git repository
- Multiple deployments (dev, staging, production) from same codebase
- Branch strategy: main (production), develop (staging), feature branches
- Dockerfile and Kubernetes manifests in repository

**II. Dependencies**
- Python: requirements.txt with pinned versions
- Frontend: package.json with locked dependencies
- No system-wide packages assumed
- All dependencies explicitly declared
- Multi-stage builds separate build dependencies from runtime

**III. Config**
- All configuration via environment variables (.env files for dev)
- Kubernetes Secrets and ConfigMaps for production
- No secrets in code or Git repository
- Different configurations for dev/staging/prod
- Config validation on startup

**IV. Backing Services**
- MariaDB, Gramps Web, OpenAI API as attached resources
- Connection URLs in environment variables
- Services swappable without code changes (e.g., switch OpenAI to Claude)
- Database migrations as separate admin processes

**V. Build, Release, Run**
- **Development**: 
  - Build: Pull base images
  - Release: podman-compose up with bind mounts
  - Run: Containers with live code
- **Production**:
  - Build: Custom Docker images via CI/CD
  - Release: Image + ConfigMap/Secrets = Kubernetes deployment
  - Run: Immutable containers in Kubernetes pods
- Semantic versioning for releases (v1.2.3)

**VI. Processes**
- Stateless application processes
- All state in Gramps Web (SSOT) or MariaDB (cache)
- No in-memory sessions (use database-backed sessions if needed)
- Horizontally scalable backend processes
- Kubernetes can add/remove pods without data loss

**VII. Port Binding**
- Backend exports HTTP via port 8000 (uvicorn)
- Frontend exports HTTP via port 3000 (development) or 80 (production)
- No web server dependency in development
- Optional nginx reverse proxy in production (via Ingress)
- Self-contained services

**VIII. Concurrency**
- Scale by adding more backend container instances
- Async processing via Python asyncio
- Job queue for obituary processing
- Database connection pooling
- Kubernetes HorizontalPodAutoscaler based on CPU/memory

**IX. Disposability**
- Fast startup (< 10 seconds for backend, < 5 for frontend)
- Graceful shutdown (finish processing, close connections)
- SIGTERM handling for clean shutdown
- Idempotent operations (safe to restart mid-process)
- Kubernetes readiness probes prevent traffic to non-ready pods

**X. Dev/Prod Parity**
- Containers ensure identical runtimes (Python 3.11, Node 20)
- Same database types (MariaDB) in all environments
- Minimal time gap (continuous deployment to staging)
- Same backing services (different instances)
- Development uses bind mounts, production uses baked images (acceptable difference)

**XI. Logs**
- All logs to stdout/stderr
- Structured logging (JSON format recommended)
- No log files in containers
- Development: podman logs
- Production: Kubernetes log aggregation (FluentD â†’ Elasticsearch, or CloudWatch)
- Different log levels via LOG_LEVEL env var

**XII. Admin Processes**
- Database migrations: Run as Kubernetes Jobs
- Data import/export: Separate scripts run as Jobs
- Console access: kubectl exec into containers
- One-off tasks never modify code
- Schema changes versioned with Alembic

## 9. Future Phase Considerations

### 9.1 Phase 2: TruePeopleSearch Integration
- Person lookup by name and location
- Address history extraction
- Relative identification
- Phone number and email (if available)
- Cross-reference with Gramps data
- New MariaDB tables for TruePeopleSearch cache
- Confidence scoring for public record matches

### 9.2 Phase 3: 23andMe Integration
- OAuth 2.0 authentication flow
- DNA match retrieval
- Relationship calculation from cM shared
- Haplogroup information
- Merge DNA relationships with documentary evidence
- New tables for genetic data
- Privacy considerations (explicit consent)

### 9.3 Phase 4: Enhanced Features
- Newspaper archive integration (Newspapers.com, Ancestry.com)
- Census record extraction
- Find A Grave integration
- Church record scraping
- Historical document OCR
- Photo facial recognition (identify people in photos)
- Timeline visualization
- Automated consistency checking (conflicting dates, impossible relationships)
- Collaborative features (share findings, merge trees)
- Mobile application (iOS/Android)

### 9.4 Multi-LLM Support
- Abstract LLM interface
- Provider implementations:
  - OpenAI (GPT-4, GPT-3.5)
  - Anthropic Claude
  - Local models (Ollama, LLaMA)
  - Google Gemini
  - Open-source alternatives
- Cost comparison and model selection
- Fallback chain (primary fails â†’ secondary â†’ tertiary)
- A/B testing for accuracy comparison

## 10. Security & Privacy

### 10.1 Data Privacy
- Store only publicly available information
- No authentication required (single-user system initially)
- Data retention policies for cached content
- GDPR considerations for future multi-user
- Provide data export and deletion capabilities
- Respect copyright (store minimal obituary content)

### 10.2 Container Security
- Non-root users in containers
- Read-only root filesystems where possible
- No privileged containers
- Secrets management (podman secrets)
- Regular security updates (base images)
- Vulnerability scanning (Trivy, Clair)

### 10.3 API Security
- API keys stored in environment variables (never in code)
- Secure communication (HTTPS) for external APIs
- Rate limiting to prevent abuse
- Input validation and sanitization
- SQL injection prevention (parameterized queries)
- XSS prevention (frontend sanitization)

### 10.4 Future Authentication
- OAuth 2.0 or JWT tokens
- Role-based access control (RBAC)
- User account management
- Multi-factor authentication (MFA)
- Audit logging of user actions

## 11. Success Metrics

### 11.1 Phase 1 Success Criteria
- Successfully extract and store data from 90%+ of submitted obituary URLs
- Correctly identify primary deceased individual in 95%+ of cases
- Correctly identify relationships with â‰¥80% accuracy
- Auto-store rate â‰¥60% (without manual review) for non-conflicting data
- **Zero unauthorized modifications** to Gramps Web (SSOT) data
- **100% user approval** required for conflicting data changes
- **Complete audit trail** for all Gramps Web modifications
- Average cost per obituary < $0.10
- Cache hit rate â‰¥70% for repeated processing
- Zero data loss incidents
- GEDCOM validation passes for all stored data
- Processing time < 30 seconds per obituary

### 11.2 Quality Metrics
- User correction rate (% of auto-stored records that need editing)
- False positive match rate (incorrect Gramps record linking)
- False negative match rate (missed opportunities to link)
- Average confidence score for auto-stored records
- Review queue backlog size
- LLM accuracy (precision/recall on test set)
- **Conflict detection accuracy** (% of actual conflicts flagged)
- **Data integrity score** (Gramps Web consistency maintained)

### 11.3 Performance Metrics
- Average processing time per obituary
- Cache hit rate (overall and by cache layer)
- API response times (95th percentile)
- Database query performance
- Concurrent processing capacity
- Container resource utilization

### 11.4 Cost Metrics
- Daily/monthly LLM API costs
- Cost per obituary processed
- Cost savings from caching
- Token usage trends
- Cost per successfully stored person record

## 12. Testing Strategy

### 12.1 Unit Tests
- LLM prompt/response parsing
- Entity extraction logic
- Confidence scoring algorithms
- Matching algorithms (name, date, location)
- Cache key generation
- GEDCOM export validation

### 12.2 Integration Tests
- End-to-end obituary processing
- Gramps Web API interactions
- MariaDB CRUD operations
- LLM API mocking (avoid costs in tests)
- Container startup and communication

### 12.3 Test Data
- Curated set of 50 test obituaries covering:
  - Simple cases (nuclear family)
  - Complex cases (multiple marriages, large families)
  - Edge cases (missing data, ambiguous relationships)
  - International names
  - Various obituary formats
- Known ground truth for accuracy measurement

### 12.4 Validation
- GEDCOM export from Gramps Web
- Import into other genealogy software (Ancestry, FamilySearch)
- Verify data integrity and relationship accuracy

## 13. Documentation Requirements

### 13.1 User Documentation
- Quick start guide
- How to process an obituary
- Understanding confidence scores
- Manual review workflow
- Configuration guide
- Troubleshooting common issues

### 13.2 Technical Documentation
- Architecture overview with diagrams
- Container setup and deployment
- Database schema documentation
- API endpoint documentation
- LLM prompt engineering guide
- Contribution guidelines (for future open-source)

### 13.3 Developer Documentation
- Code structure and organization
- Development environment setup
- Running tests
- Adding new LLM providers
- Adding new data sources
- Database migration procedures

## 14. Known Limitations & Constraints

### 14.1 Technical Constraints
- LLM extraction accuracy depends on obituary quality
- No access to paywalled obituaries
- JavaScript-heavy sites may require additional tools (Playwright)
- Ambiguous relationships difficult to resolve automatically
- Name variations and nicknames challenging to match
- Historical date format variations

### 14.2 Business Constraints
- LLM API costs (mitigated by caching)
- Rate limits on external services
- Copyright restrictions on obituary content
- No guarantee of obituary availability (links may break)

### 14.3 Phase 1 Limitations
- Single obituary at a time (no batch upload)
- English language only
- No image/photo processing
- No automatic source discovery
- Manual data correction required for low-confidence extractions
- No collaborative features

## 15. Open Questions & Decisions

### 15.1 Resolved Decisions
âœ… LLM Provider: OpenAI initially, multi-provider in future
âœ… Cache Storage: MariaDB
âœ… Container Platform: Podman
âœ… Backend Language: Python
âœ… Always Review: Optional checkbox, configurable auto-store
âœ… Matching Strategy: Automatic with confidence thresholds
âœ… Multi-Obituary Linking: Yes, link all sources to same person

### 15.2 Remaining Decisions
1. **Frontend Framework**: React, Vue, or Svelte? (Recommendation: React for ecosystem)
2. **Python Web Framework**: Flask or FastAPI? (Recommendation: FastAPI for async and auto-docs)
3. **ORM**: SQLAlchemy, Tortoise, or raw SQL? (Recommendation: SQLAlchemy)
4. **Task Queue**: Celery for async processing? Or simple threading?
5. **LLM Prompt Strategy**: Few-shot examples vs. zero-shot with detailed instructions?
6. **Matching Algorithm**: Exact match, fuzzy matching (fuzzywuzzy), or ML-based?
7. **Container Registry**: Docker Hub, GitHub Container Registry, or local only?
8. **Backup Strategy**: Automated database backups? Frequency?
9. **Conflict Resolution Strategy**: Default to Gramps data or require explicit choice for every conflict?

## 16. Architectural Principles Summary

### 16.1 Single Source of Truth (SSOT)
- **Gramps Web is the authoritative database** for all genealogical data
- MariaDB cache is subordinate (staging area, performance layer)
- All genealogical queries go to Gramps Web, not cache
- Cache serves extraction results awaiting validation
- **Never modify Gramps Web without validation**

### 16.2 Data Integrity Safeguards
- Non-conflicting additions: Can auto-apply if confidence is high
- Modifications to existing data: Always require user approval
- Deletions: Never automatic, always require explicit confirmation
- Complete audit trail of all Gramps Web operations
- Source citations added for all imported data

### 16.3 Twelve-Factor App Methodology
- Configuration via environment variables
- Stateless processes (state in databases)
- Logs to stdout/stderr
- Declarative dependencies
- Containerized for portability
- Dev/prod parity
- Horizontal scalability
- Graceful startup/shutdown

### 16.4 Cost Optimization
- Three-layer caching (obituary, LLM, entities)
- Target: <$0.10 per obituary
- Cache hit rate: â‰¥70%
- Minimize redundant API calls

### 16.5 User-Centered Validation
- High-confidence, non-conflicting data: Auto-apply
- Conflicts or low confidence: User review required
- Clear visual indicators of conflicts
- Side-by-side comparison of SSOT vs. extracted data
- Explicit confirmation for all modifications

## 16. Development Phases

### 16.1 Phase 1.1: Foundation (Weeks 1-2)
- Set up development environment (Podman Desktop on MacBook Pro)
- Create podman-compose.dev.yml with bind mounts
- Set up MariaDB container with schema initialization
- Set up Gramps Web container
- Basic backend API structure (FastAPI with hot reload)
- Database connection and ORM setup (SQLAlchemy)
- Configuration management (python-dotenv)
- Health check endpoints
- Basic logging to stdout

### 16.2 Phase 1.2: Core Processing (Weeks 3-4)
- Web scraping implementation (BeautifulSoup, requests)
- OpenAI API integration with structured output
- Entity extraction with LLM (persons, relationships)
- Caching logic (all three layers: obituary, LLM, entities)
- Basic Gramps Web integration (read/write API)
- Confidence scoring logic
- Testing with sample obituaries

### 16.3 Phase 1.3: Matching & Storage (Weeks 5-6)
- Matching algorithm implementation (fuzzy string matching)
- SSOT validation logic (conflict detection)
- Confidence scoring logic
- Gramps Web record creation (persons, families, events)
- Relationship mapping
- Source citation creation
- Audit logging
- Testing with diverse obituaries

### 16.4 Phase 1.4: UI & Review (Weeks 7-8)
- Frontend development (React with Vite)
- Input page (URL submission)
- Processing page with progress indicators
- Review interface for flagged entities
- Side-by-side conflict comparison view
- Results page with statistics
- Configuration page (tunable thresholds)
- Cost tracking dashboard

### 16.5 Phase 1.5: Polish & Testing (Weeks 9-10)
- Error handling improvements
- Performance optimization (query optimization, indexing)
- Comprehensive testing (unit, integration, end-to-end)
- Documentation (user guide, API docs)
- Bug fixes
- Code cleanup and refactoring

### 16.6 Phase 2: Production Preparation (Post-Phase 1)
- Create production Dockerfiles (multi-stage builds)
- Set up GitHub Container Registry
- Create Kubernetes manifests (Deployments, Services, ConfigMaps, Secrets)
- Set up CI/CD pipeline (GitHub Actions)
- Implement automated testing in CI
- Container security scanning (Trivy)
- Performance testing and optimization
- Staging environment deployment
- Production deployment preparation

### 16.7 Phase 3: Kubernetes Migration (Future)
- Deploy to Kubernetes cluster
- Set up monitoring (Prometheus, Grafana)
- Set up log aggregation (FluentD, Loki)
- Configure horizontal pod autoscaling
- Set up ingress with TLS
- Implement backup strategies
- Document production operations
- Performance tuning for production load

## 17. Out of Scope (Phase 1)

- User account management (single-user system)
- Authentication/authorization (future enhancement)
- Mobile application
- Automated source discovery
- Image/photo processing
- Social media integration
- Collaborative features (future: sharing findings)
- Advanced visualizations (beyond basic comparison view)
- Export to other formats (GEDCOM handled by Gramps Web)
- Batch processing of multiple URLs simultaneously
- Scheduled/automated processing
- Email notifications
- Public API for external integrations
- Multi-language support (English only in Phase 1)
- Historical document OCR
- Census record extraction
- DNA data integration (Phase 3)
- TruePeopleSearch integration (Phase 2)
- **Automatic deletion** of Gramps Web records (always out of scope without explicit user action)
- **Bulk modifications** without review (maintain data integrity)

---

**Document Version**: 4.0  
**Last Updated**: November 28, 2025  
**Status**: Ready for Development - SSOT and 12-Factor Compliant  
**Architecture Principles**: 
- Single Source of Truth (Gramps Web)
- Twelve-Factor App Methodology
- Development: Bind mounts on MacBook Pro with Podman
- Production: Custom images on Kubernetes
- Caching: MariaDB with performance optimizations
**Next Review**: Upon completion of Phase 1.2

## Appendix A: Twelve-Factor App Reference

For complete details on the Twelve-Factor App methodology, see: https://12factor.net/

Key principles applied to this project:
1. **Codebase**: One repo, multiple deploys
2. **Dependencies**: Explicit declaration and isolation
3. **Config**: Store in environment
4. **Backing Services**: Attached resources
5. **Build, Release, Run**: Strict separation
6. **Processes**: Stateless and share-nothing
7. **Port Binding**: Export services via port binding
8. **Concurrency**: Scale out via process model
9. **Disposability**: Fast startup and graceful shutdown
10. **Dev/Prod Parity**: Keep development, staging, and production as similar as possible
11. **Logs**: Treat logs as event streams
12. **Admin Processes**: Run admin/management tasks as one-off processes

## Appendix B: Development to Production Migration Path

### Current State (Phase 1)
- **Platform**: MacBook Pro with Podman Desktop
- **Images**: Standard base images (python:3.11-slim, node:20-alpine, etc.)
- **Code**: Bind-mounted for live editing
- **Orchestration**: podman-compose.dev.yml
- **Benefits**: Fast iteration, hot reload, easy debugging

### Future State (Post-Phase 1)
- **Platform**: Kubernetes cluster (cloud or on-premise)
- **Images**: Custom-built, multi-stage, immutable
- **Code**: Baked into images (no mounts)
- **Orchestration**: Kubernetes Deployments + Helm
- **Registry**: GitHub Container Registry (ghcr.io)
- **CI/CD**: GitHub Actions for automated builds/tests/deployments

### Migration Steps
1. **Complete Phase 1 development** with bind mounts
2. **Create production Dockerfiles**:
   - Backend: Multi-stage Python build
   - Frontend: Multi-stage Node build with nginx
3. **Test builds locally**: `podman build -t genealogy-backend:test .`
4. **Set up GitHub Container Registry**
5. **Create Kubernetes manifests**: Deployments, Services, ConfigMaps, Secrets, PVCs, Ingress
6. **Set up CI/CD pipeline** (GitHub Actions):
   - Run tests on push
   - Build images on merge to main
   - Push to ghcr.io with version tags
   - Deploy to staging automatically
   - Deploy to production manually
7. **Deploy to staging** Kubernetes cluster
8. **Load testing and optimization**
9. **Deploy to production** Kubernetes cluster
10. **Monitor and iterate**

### Caching Strategy Rationale

**Why MariaDB (Not Redis):**
- Complex structured data (persons with attributes and relationships)
- Need for SQL JOINs (person â†’ relationship â†’ obituary)
- Complex WHERE clauses (confidence scores, match statuses, date filtering)
- ACID transactions for SSOT validation integrity
- JSON support for LLM responses (MariaDB has native JSON type)
- Audit trail requires relational integrity
- Single database technology = simpler stack

**MariaDB Performance Features Used:**
- InnoDB engine with ACID compliance
- Strategic indexes on all lookup fields
- Connection pooling via SQLAlchemy
- Built-in query result caching

**Future Optimization Options:**
- Redis for simple key-value lookups (if needed)
- MariaDB MEMORY tables for hot data (if needed)
- Application-level caching with functools.lru_cache
- CDN for static assets in production