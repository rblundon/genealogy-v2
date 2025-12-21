# Genealogy Research Tool - Project Plan

**Project Duration**: 10 weeks (December 2024 - February 2025)  
**Methodology**: Agile sprints (2-week iterations)  
**Platform**: Development on MacBook Pro with Podman Desktop

---

## Phase 1.1: Foundation (Weeks 1-2)
**Goal**: Infrastructure setup and database initialization

### Epic: Development Environment Setup
**Priority**: Critical | **Points**: 8

#### Tasks:
- [ ] **ENV-001**: Initialize Git repository with .gitignore for Python/Node/containers
  - Set up branch strategy (main, develop, feature branches)
  - Create README.md with quickstart guide
  - **Assignee**: Ryan | **Points**: 2

- [ ] **ENV-002**: Create podman-compose.dev.yml configuration
  - MariaDB service with named volumes
  - Gramps Web service configuration
  - Backend service with bind mounts
  - Frontend service with bind mounts
  - Network setup (genealogy-net)
  - Health checks for all services
  - **Assignee**: Ryan | **Points**: 3

- [ ] **ENV-003**: Create .env.example and .env files
  - All required environment variables
  - Secure default values
  - Documentation comments
  - **Assignee**: Ryan | **Points**: 1

- [ ] **ENV-004**: Test container orchestration
  - Verify all services start successfully
  - Test inter-container communication
  - Verify bind mounts working
  - Test hot reload (backend and frontend)
  - **Assignee**: Ryan | **Points**: 2

### Epic: Database Infrastructure
**Priority**: Critical | **Points**: 13

#### Tasks:
- [ ] **DB-001**: Initialize MariaDB schema from genealogy_cache_schema.sql
  - Create initialization script
  - Verify all tables created
  - Verify indexes created
  - Test default config_settings values
  - **Assignee**: Ryan | **Points**: 2

- [ ] **DB-002**: Set up SQLAlchemy ORM models (already defined in models.py)
  - Verify models match schema
  - Test database connection
  - Test session management
  - **Assignee**: Ryan | **Points**: 2

- [ ] **DB-003**: Create database migration system with Alembic
  - Initialize Alembic
  - Create initial migration
  - Document migration workflow
  - **Assignee**: Ryan | **Points**: 3

- [ ] **DB-004**: Implement Config helper class utilities
  - Test get/set methods
  - Test typed value conversion
  - Test convenience methods (get_confidence_threshold_auto_store, etc.)
  - **Assignee**: Ryan | **Points**: 2

- [ ] **DB-005**: Set up Gramps Web container
  - Configure environment variables
  - Create initial user account
  - Test API authentication
  - Verify health endpoint
  - **Assignee**: Ryan | **Points**: 3

- [ ] **DB-006**: Create database backup script
  - MariaDB dump script
  - Gramps Web export script
  - Document restore procedure
  - **Assignee**: Ryan | **Points**: 1

### Epic: Backend API Foundation
**Priority**: Critical | **Points**: 13

#### Tasks:
- [ ] **API-001**: Initialize FastAPI project structure
  - Create main.py with app initialization
  - Set up CORS middleware
  - Configure logging to stdout (structured JSON)
  - Create health check endpoint
  - **Assignee**: Ryan | **Points**: 3

- [ ] **API-002**: Implement database dependency injection
  - Create get_db() dependency
  - Test session lifecycle
  - Handle connection pooling
  - **Assignee**: Ryan | **Points**: 2

- [ ] **API-003**: Create Pydantic models for API contracts
  - ObituarySubmission (request)
  - ProcessingStatus (response)
  - PersonEntity (response)
  - RelationshipEntity (response)
  - ErrorResponse
  - **Assignee**: Ryan | **Points**: 3

- [ ] **API-004**: Set up environment variable validation
  - Use pydantic-settings
  - Validate all required env vars on startup
  - Fail fast if missing critical config
  - **Assignee**: Ryan | **Points**: 2

- [ ] **API-005**: Implement structured logging system
  - JSON formatter for logs
  - Request ID correlation
  - Log levels via environment variable
  - Context managers for operation logging
  - **Assignee**: Ryan | **Points**: 3

### Epic: Frontend Foundation
**Priority**: High | **Points**: 8

#### Tasks:
- [ ] **FE-001**: Initialize React + Vite project
  - Create project with TypeScript
  - Configure Vite for hot reload
  - Set up ESLint and Prettier
  - **Assignee**: Ryan | **Points**: 2

- [ ] **FE-002**: Set up React Router and basic page structure
  - Home page (URL input)
  - Processing page (progress)
  - Review page (entity review)
  - Results page (summary)
  - Configuration page (admin settings)
  - **Assignee**: Ryan | **Points**: 3

- [ ] **FE-003**: Create API client service
  - Axios or fetch wrapper
  - Base URL configuration from env
  - Error handling wrapper
  - Request/response interceptors
  - **Assignee**: Ryan | **Points**: 2

- [ ] **FE-004**: Design system setup (Tailwind CSS or Material-UI)
  - Install and configure
  - Create basic component library
  - Color palette and typography
  - **Assignee**: Ryan | **Points**: 1

---

## Phase 1.2: Core Processing (Weeks 3-4)
**Goal**: Obituary fetching and LLM extraction pipeline

### Epic: Web Scraping Implementation
**Priority**: Critical | **Points**: 13

#### Tasks:
- [ ] **SCRAPE-001**: Implement URL validation and caching logic
  - Validate URL format
  - Generate URL hash (SHA-256)
  - Check obituary_cache table
  - Return cached content if available
  - **Assignee**: Ryan | **Points**: 2

- [ ] **SCRAPE-002**: Build web scraper with BeautifulSoup
  - Fetch HTML with requests library
  - Handle timeouts (10s limit)
  - Respect robots.txt
  - User-agent configuration
  - Handle redirects
  - **Assignee**: Ryan | **Points**: 3

- [ ] **SCRAPE-003**: Implement HTML cleaning and text extraction
  - Remove scripts, styles, navigation
  - Extract main content area
  - Clean whitespace
  - Handle different obituary site structures
  - **Assignee**: Ryan | **Points**: 3

- [ ] **SCRAPE-004**: Store raw HTML and extracted text in cache
  - Calculate content hash
  - Store in obituary_cache table
  - Record fetch metadata (timestamp, status code)
  - Handle fetch errors gracefully
  - **Assignee**: Ryan | **Points**: 2

- [ ] **SCRAPE-005**: Implement rate limiting and retry logic
  - Max 1 request per 2 seconds per domain
  - Exponential backoff for retries
  - Max 3 retry attempts
  - Handle common HTTP errors (404, 403, 500)
  - **Assignee**: Ryan | **Points**: 3

### Epic: LLM Integration
**Priority**: Critical | **Points**: 21

#### Tasks:
- [ ] **LLM-001**: Design structured extraction prompt
  - Clear instructions for entity extraction
  - JSON output format specification
  - Examples of desired output
  - Confidence scoring guidelines
  - Relationship type taxonomy
  - **Assignee**: Ryan | **Points**: 5

- [ ] **LLM-002**: Implement OpenAI API client
  - Use openai Python library
  - API key from environment variable
  - Model selection (gpt-4-turbo-preview initially)
  - JSON mode or function calling for structured output
  - **Assignee**: Ryan | **Points**: 3

- [ ] **LLM-003**: Implement prompt hashing and cache lookup
  - Generate prompt hash (SHA-256)
  - Check llm_cache table before API call
  - Return cached response if available
  - Log cache hit/miss
  - **Assignee**: Ryan | **Points**: 2

- [ ] **LLM-004**: Build LLM response parser
  - Parse JSON response
  - Validate structure
  - Extract persons list
  - Extract relationships list
  - Handle malformed responses
  - **Assignee**: Ryan | **Points**: 3

- [ ] **LLM-005**: Implement token usage and cost tracking
  - Capture token counts from API response
  - Calculate estimated cost
  - Store in llm_cache table
  - Log cost metrics
  - **Assignee**: Ryan | **Points**: 2

- [ ] **LLM-006**: Error handling for API failures
  - Rate limit errors (429) with exponential backoff
  - Invalid API key errors
  - Model unavailable errors
  - Timeout errors (30s limit)
  - Store errors in llm_cache table
  - **Assignee**: Ryan | **Points**: 3

- [ ] **LLM-007**: Create comprehensive test suite with mock responses
  - Mock OpenAI API calls
  - Test various obituary formats
  - Test edge cases (empty, malformed)
  - Test error handling
  - **Assignee**: Ryan | **Points**: 3

### Epic: Entity Storage
**Priority**: Critical | **Points**: 13

#### Tasks:
- [ ] **ENTITY-001**: Implement ExtractedPerson storage
  - Parse person data from LLM response
  - Validate required fields
  - Store in extracted_persons table
  - Link to obituary_cache_id and llm_cache_id
  - **Assignee**: Ryan | **Points**: 3

- [ ] **ENTITY-002**: Implement ExtractedRelationship storage
  - Parse relationship data from LLM response
  - Validate person references
  - Store in extracted_relationships table
  - Handle relationship directionality
  - **Assignee**: Ryan | **Points**: 3

- [ ] **ENTITY-003**: Implement confidence score calculation
  - Parse confidence from LLM output
  - Validate score range (0.0-1.0)
  - Apply business rules (clear terms = higher confidence)
  - Store with entities
  - **Assignee**: Ryan | **Points**: 2

- [ ] **ENTITY-004**: Implement processing queue management
  - Create job in processing_queue table
  - Update status (queued → processing → completed/failed)
  - Record timestamps
  - Handle retry logic for failed jobs
  - **Assignee**: Ryan | **Points**: 3

- [ ] **ENTITY-005**: Create audit logging for all operations
  - Log to audit_log table
  - Record action type, entity type, entity ID
  - Store operation details as JSON
  - Timestamp all operations
  - **Assignee**: Ryan | **Points**: 2

### Epic: Testing & Validation
**Priority**: High | **Points**: 8

#### Tasks:
- [ ] **TEST-001**: Create test obituary dataset
  - 10 simple cases (nuclear family)
  - 5 complex cases (multiple marriages, large families)
  - 5 edge cases (missing data, ambiguous)
  - Document ground truth for each
  - **Assignee**: Ryan | **Points**: 3

- [ ] **TEST-002**: Unit tests for core functions
  - URL validation and hashing
  - HTML cleaning
  - Prompt generation
  - Response parsing
  - Confidence scoring
  - **Assignee**: Ryan | **Points**: 3

- [ ] **TEST-003**: Integration tests for end-to-end flow
  - Mock external APIs
  - Test database operations
  - Test cache hits and misses
  - Verify audit logging
  - **Assignee**: Ryan | **Points**: 2

---

## Phase 1.3: Matching & Storage (Weeks 5-6)
**Goal**: SSOT validation and Gramps Web integration

### Epic: Gramps Web Integration
**Priority**: Critical | **Points**: 21

#### Tasks:
- [ ] **GRAMPS-001**: Implement Gramps Web API client
  - Authentication with API token
  - Base request wrapper with error handling
  - Rate limit handling
  - Test connection endpoint
  - **Assignee**: Ryan | **Points**: 3

- [ ] **GRAMPS-002**: Implement person search API
  - GET /api/people/ with filters
  - Name-based search
  - Date range search
  - Location-based search
  - Parse response into internal models
  - **Assignee**: Ryan | **Points**: 3

- [ ] **GRAMPS-003**: Implement person creation API
  - POST /api/people/ with person data
  - Map internal model to Gramps schema
  - Handle API validation errors
  - Return Gramps person ID
  - **Assignee**: Ryan | **Points**: 3

- [ ] **GRAMPS-004**: Implement family creation API
  - POST /api/families/ with relationship data
  - Link parent and child person IDs
  - Handle spouse relationships
  - Return Gramps family ID
  - **Assignee**: Ryan | **Points**: 3

- [ ] **GRAMPS-005**: Implement source and citation creation
  - POST /api/sources/ for obituary source
  - POST /api/citations/ to link source to person/family
  - Store obituary URL in source
  - Add confidence notes to citations
  - **Assignee**: Ryan | **Points**: 3

- [ ] **GRAMPS-006**: Implement event creation API
  - POST /api/events/ for birth/death events
  - Link events to persons
  - Handle date formats (circa flags)
  - Store location data
  - **Assignee**: Ryan | **Points**: 3

- [ ] **GRAMPS-007**: Update gramps_record_mapping table
  - Store Gramps IDs after creation
  - Link to extracted entities
  - Record creation timestamp
  - Enable traceability
  - **Assignee**: Ryan | **Points**: 3

### Epic: Matching Algorithm
**Priority**: Critical | **Points**: 21

#### Tasks:
- [ ] **MATCH-001**: Implement exact name matching
  - Normalize names (lowercase, trim)
  - Exact string comparison
  - Handle name order variations
  - High confidence for exact matches
  - **Assignee**: Ryan | **Points**: 3

- [ ] **MATCH-002**: Implement fuzzy name matching with rapidfuzz
  - Install rapidfuzz library
  - Token-based comparison
  - Threshold: 0.90 for auto-match
  - Return match candidates with scores
  - **Assignee**: Ryan | **Points**: 5

- [ ] **MATCH-003**: Implement date range validation
  - Birth date ±2 years tolerance
  - Death date ±2 years tolerance
  - Handle circa dates
  - Null date handling
  - **Assignee**: Ryan | **Points**: 3

- [ ] **MATCH-004**: Implement location matching
  - Normalize location strings
  - Substring matching for cities
  - State/country validation
  - Null location handling
  - **Assignee**: Ryan | **Points**: 3

- [ ] **MATCH-005**: Implement composite matching score
  - Weight: Name (50%), Dates (30%), Location (20%)
  - Calculate overall confidence
  - Threshold logic (auto-store vs. review)
  - Return ranked candidates
  - **Assignee**: Ryan | **Points**: 3

- [ ] **MATCH-006**: Implement relationship validation
  - Check existing family relationships in Gramps
  - Detect conflicting relationships
  - Flag for review if contradictory
  - **Assignee**: Ryan | **Points**: 4

### Epic: SSOT Validation Logic
**Priority**: Critical | **Points**: 21

#### Tasks:
- [ ] **SSOT-001**: Implement conflict detection for person data
  - Compare extracted vs. Gramps birth dates
  - Compare extracted vs. Gramps death dates
  - Compare extracted vs. Gramps gender
  - Flag conflicts with specific type
  - **Assignee**: Ryan | **Points**: 5

- [ ] **SSOT-002**: Implement conflict detection for relationships
  - Query existing Gramps family relationships
  - Compare relationship types
  - Detect contradictions (father vs. stepfather)
  - Flag for manual review
  - **Assignee**: Ryan | **Points**: 5

- [ ] **SSOT-003**: Implement non-conflicting addition detection
  - Identify new data not in Gramps
  - Verify no contradictions
  - Mark safe for auto-apply
  - **Assignee**: Ryan | **Points**: 3

- [ ] **SSOT-004**: Implement confidence-based routing
  - Read thresholds from config_settings
  - High confidence + non-conflicting → auto-store
  - Conflicts or low confidence → review queue
  - Update match_status field
  - **Assignee**: Ryan | **Points**: 3

- [ ] **SSOT-005**: Implement transaction handling for Gramps writes
  - Atomic operations (all or nothing)
  - Rollback on error
  - Update audit_log for all operations
  - Record user approval flag
  - **Assignee**: Ryan | **Points**: 5

### Epic: Testing & Validation
**Priority**: High | **Points**: 8

#### Tasks:
- [ ] **TEST-004**: Test matching algorithms with known data
  - Test exact matches
  - Test fuzzy matches at various thresholds
  - Test date range validation
  - Measure precision/recall
  - **Assignee**: Ryan | **Points**: 3

- [ ] **TEST-005**: Test SSOT validation with conflict scenarios
  - Create test Gramps data
  - Test non-conflicting additions
  - Test conflicting data detection
  - Test routing logic
  - **Assignee**: Ryan | **Points**: 3

- [ ] **TEST-006**: Integration test end-to-end with Gramps Web
  - Test person creation
  - Test family creation
  - Test source citation
  - Verify data in Gramps Web UI
  - **Assignee**: Ryan | **Points**: 2

---

## Phase 1.4: UI & Review (Weeks 7-8)
**Goal**: User interface for submission, review, and results

### Epic: Input & Processing UI
**Priority**: Critical | **Points**: 13

#### Tasks:
- [ ] **UI-001**: Build Home/Input page component
  - URL input field with validation
  - "Process" button
  - "Always require review" checkbox
  - Links to queue, review, dashboard
  - **Assignee**: Ryan | **Points**: 3

- [ ] **UI-002**: Build Processing page with progress indicators
  - Stage indicators (fetching, extracting, matching, storing)
  - Real-time status messages via polling or WebSocket
  - Cache hit notifications
  - Estimated LLM cost display
  - Error display if processing fails
  - **Assignee**: Ryan | **Points**: 5

- [ ] **UI-003**: Implement API endpoints for processing
  - POST /api/obituaries (submit URL)
  - GET /api/obituaries/{id}/status (poll status)
  - Background task for async processing
  - Return processing job ID
  - **Assignee**: Ryan | **Points**: 3

- [ ] **UI-004**: Add loading states and error handling
  - Skeleton loaders
  - Error boundaries
  - User-friendly error messages
  - Retry button for failed operations
  - **Assignee**: Ryan | **Points**: 2

### Epic: Review Interface
**Priority**: Critical | **Points**: 21

#### Tasks:
- [ ] **UI-005**: Build Review page list view
  - Display all entities with match_status='review_needed'
  - Sort by confidence score
  - Filter controls
  - Batch selection capability
  - **Assignee**: Ryan | **Points**: 3

- [ ] **UI-006**: Build entity detail component
  - Show full extracted data
  - Confidence score visualization (color-coded)
  - Source context from obituary
  - Edit controls for all fields
  - **Assignee**: Ryan | **Points**: 3

- [ ] **UI-007**: Build conflict comparison component
  - Two-column layout (Gramps vs. Extracted)
  - Highlight differences in red
  - Conflict type labels
  - Resolution button group
  - **Assignee**: Ryan | **Points**: 5

- [ ] **UI-008**: Build potential match selector
  - List of candidate Gramps persons
  - Match score display
  - Side-by-side comparison
  - Manual match selection
  - "Create new" option
  - **Assignee**: Ryan | **Points**: 5

- [ ] **UI-009**: Implement review API endpoints
  - GET /api/review/queue (list entities)
  - PUT /api/review/entities/{id} (update entity)
  - POST /api/review/entities/{id}/approve (approve creation)
  - POST /api/review/entities/{id}/resolve (resolve conflict)
  - POST /api/review/entities/{id}/reject (reject entity)
  - **Assignee**: Ryan | **Points**: 3

- [ ] **UI-010**: Add confirmation dialogs for destructive actions
  - Confirm before modifying Gramps data
  - Confirm before rejecting entities
  - Show what will change
  - **Assignee**: Ryan | **Points**: 2

### Epic: Results & Dashboard UI
**Priority**: High | **Points**: 13

#### Tasks:
- [ ] **UI-011**: Build Results page component
  - Success confirmation message
  - Summary statistics (persons, relationships, cost)
  - Links to new Gramps Web records
  - Cache status (hit/miss)
  - "Process Another" button
  - **Assignee**: Ryan | **Points**: 3

- [ ] **UI-012**: Build Cost Dashboard page
  - Current month total cost
  - Cost per obituary average
  - Token usage chart (Chart.js or Recharts)
  - Cache hit rate percentage
  - Provider/model breakdown table
  - **Assignee**: Ryan | **Points**: 5

- [ ] **UI-013**: Build Configuration page
  - Threshold sliders (auto-store, review)
  - "Always review" checkbox
  - LLM provider dropdown
  - LLM model selection
  - Cost alert threshold input
  - Cache expiry days input
  - Save button with validation
  - **Assignee**: Ryan | **Points**: 5

### Epic: API Endpoints for UI
**Priority**: Critical | **Points**: 8

#### Tasks:
- [ ] **API-006**: Implement statistics endpoints
  - GET /api/stats/cost (cost metrics)
  - GET /api/stats/processing (processing metrics)
  - GET /api/stats/cache (cache hit rates)
  - **Assignee**: Ryan | **Points**: 3

- [ ] **API-007**: Implement configuration endpoints
  - GET /api/config (all settings)
  - PUT /api/config (update settings)
  - Validate threshold ranges
  - Update config_settings table
  - **Assignee**: Ryan | **Points**: 3

- [ ] **API-008**: Implement queue management endpoints
  - GET /api/queue (processing queue status)
  - DELETE /api/queue/{id} (cancel job)
  - POST /api/queue/{id}/retry (retry failed job)
  - **Assignee**: Ryan | **Points**: 2

---

## Phase 1.5: Polish & Testing (Weeks 9-10)
**Goal**: Production-ready Phase 1 release

### Epic: Error Handling & Resilience
**Priority**: Critical | **Points**: 13

#### Tasks:
- [ ] **ERR-001**: Comprehensive error handling for all API endpoints
  - Try/except for all operations
  - Specific exception types
  - Log errors with context
  - Return appropriate HTTP status codes
  - User-friendly error messages
  - **Assignee**: Ryan | **Points**: 5

- [ ] **ERR-002**: Implement retry logic for transient failures
  - Network errors
  - Database connection errors
  - LLM API rate limits
  - Exponential backoff
  - Max retry attempts from config
  - **Assignee**: Ryan | **Points**: 3

- [ ] **ERR-003**: Add input validation for all endpoints
  - URL format validation
  - Confidence score ranges
  - Date format validation
  - Required field validation
  - SQL injection prevention
  - **Assignee**: Ryan | **Points**: 3

- [ ] **ERR-004**: Implement graceful degradation
  - Continue processing if non-critical steps fail
  - Partial results when possible
  - Clear indication of what succeeded/failed
  - **Assignee**: Ryan | **Points**: 2

### Epic: Performance Optimization
**Priority**: High | **Points**: 13

#### Tasks:
- [ ] **PERF-001**: Database query optimization
  - Add missing indexes
  - Analyze slow queries with EXPLAIN
  - Optimize JOIN operations
  - Use connection pooling effectively
  - **Assignee**: Ryan | **Points**: 3

- [ ] **PERF-002**: Implement database connection pooling tuning
  - Adjust pool_size and max_overflow
  - Test under load
  - Monitor connection utilization
  - **Assignee**: Ryan | **Points**: 2

- [ ] **PERF-003**: Frontend performance optimization
  - Code splitting for route-based bundles
  - Lazy loading for components
  - Image optimization
  - Minimize bundle size
  - **Assignee**: Ryan | **Points**: 3

- [ ] **PERF-004**: Add caching headers for API responses
  - Cache static configuration
  - ETags for conditional requests
  - Appropriate cache-control headers
  - **Assignee**: Ryan | **Points**: 2

- [ ] **PERF-005**: Load testing and bottleneck identification
  - Use locust or k6 for load testing
  - Test concurrent obituary processing
  - Identify slow operations
  - Document performance baseline
  - **Assignee**: Ryan | **Points**: 3

### Epic: Documentation
**Priority**: High | **Points**: 13

#### Tasks:
- [ ] **DOC-001**: User documentation (README.md)
  - Quickstart guide
  - Environment setup instructions
  - How to process an obituary
  - Understanding confidence scores
  - Manual review workflow
  - Troubleshooting section
  - **Assignee**: Ryan | **Points**: 3

- [ ] **DOC-002**: API documentation (OpenAPI/Swagger)
  - FastAPI auto-generated docs
  - Add descriptions to all endpoints
  - Example requests/responses
  - Error response documentation
  - **Assignee**: Ryan | **Points**: 2

- [ ] **DOC-003**: Developer documentation
  - Code structure overview
  - Development environment setup
  - Running tests
  - Database migration procedures
  - Adding new LLM providers (architecture)
  - **Assignee**: Ryan | **Points**: 3

- [ ] **DOC-004**: Architecture documentation with diagrams
  - System architecture diagram
  - Data flow diagram
  - SSOT validation flow diagram
  - Container architecture diagram
  - **Assignee**: Ryan | **Points**: 3

- [ ] **DOC-005**: Database schema documentation
  - Table descriptions
  - Relationship diagrams
  - Index strategy explanation
  - **Assignee**: Ryan | **Points**: 2

### Epic: Comprehensive Testing
**Priority**: Critical | **Points**: 21

#### Tasks:
- [ ] **TEST-007**: Complete unit test coverage
  - Target: >80% coverage
  - All business logic functions
  - Edge cases and error paths
  - Mock external dependencies
  - **Assignee**: Ryan | **Points**: 5

- [ ] **TEST-008**: Integration test suite
  - Database operations
  - Gramps Web integration
  - Cache behavior
  - Transaction handling
  - **Assignee**: Ryan | **Points**: 5

- [ ] **TEST-009**: End-to-end test scenarios
  - Simple obituary processing
  - Complex obituary with conflicts
  - Review workflow
  - Configuration changes
  - Error scenarios
  - **Assignee**: Ryan | **Points**: 5

- [ ] **TEST-010**: Manual testing with real obituaries
  - Test with 20 real obituaries
  - Verify Gramps Web data accuracy
  - Test UI workflows
  - Document bugs and edge cases
  - **Assignee**: Ryan | **Points**: 3

- [ ] **TEST-011**: GEDCOM export validation
  - Export from Gramps Web
  - Import into Ancestry.com or FamilySearch
  - Verify data integrity
  - Verify relationships intact
  - **Assignee**: Ryan | **Points**: 3

### Epic: Bug Fixes & Refinement
**Priority**: High | **Points**: 8

#### Tasks:
- [ ] **BUG-001**: Create bug tracking workflow
  - GitHub Issues setup
  - Bug report template
  - Prioritization labels
  - **Assignee**: Ryan | **Points**: 1

- [ ] **BUG-002**: Fix critical bugs from testing
  - Triage and prioritize
  - Fix data corruption issues
  - Fix SSOT validation bugs
  - **Assignee**: Ryan | **Points**: 5

- [ ] **BUG-003**: Code cleanup and refactoring
  - Remove dead code
  - Improve naming consistency
  - Add type hints where missing
  - Format with Black
  - **Assignee**: Ryan | **Points**: 2

### Epic: Release Preparation
**Priority**: High | **Points**: 5

#### Tasks:
- [ ] **REL-001**: Version tagging and changelog
  - Create v1.0.0 tag
  - Write CHANGELOG.md
  - Document breaking changes
  - **Assignee**: Ryan | **Points**: 1

- [ ] **REL-002**: Production deployment preparation (documentation only)
  - Document production Dockerfile creation
  - Document Kubernetes manifest requirements
  - Document CI/CD pipeline plan
  - Document migration path from dev to prod
  - **Assignee**: Ryan | **Points**: 2

- [ ] **REL-003**: Security review
  - No hardcoded secrets
  - SQL injection prevention verified
  - XSS prevention verified
  - Container security best practices
  - **Assignee**: Ryan | **Points**: 2

---

## Success Metrics (Phase 1)

### Functional Metrics
- [ ] Successfully extract data from 90%+ of test obituaries
- [ ] Correctly identify primary deceased in 95%+ of cases
- [ ] Relationship extraction accuracy ≥80%
- [ ] Auto-store rate ≥60% for non-conflicting data
- [ ] Zero unauthorized Gramps Web modifications

### Performance Metrics
- [ ] Average processing time <30 seconds per obituary
- [ ] Cache hit rate ≥70%
- [ ] Database query p95 <100ms
- [ ] API response p95 <500ms

### Cost Metrics
- [ ] Average cost per obituary <$0.10
- [ ] Cache providing measurable cost savings

### Quality Metrics
- [ ] Unit test coverage >80%
- [ ] All integration tests passing
- [ ] GEDCOM validation passes
- [ ] Manual testing with 20 real obituaries successful

---

## Risk Management

### Technical Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| LLM extraction accuracy lower than expected | High | Medium | Comprehensive prompt engineering, test with diverse obituaries, iterate on prompt |
| Gramps Web API limitations | High | Low | Review API docs early, test all required operations, plan workarounds |
| Matching algorithm false positives | Medium | Medium | Conservative thresholds, always allow manual review, comprehensive testing |
| Performance issues with MariaDB | Medium | Low | Proper indexing, connection pooling, load testing |
| Container orchestration complexity | Low | Low | Start simple with podman-compose, document thoroughly |

### Project Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Scope creep beyond Phase 1 | Medium | Medium | Strict adherence to PRD, defer enhancements to Phase 2 |
| Timeline delays | Medium | Medium | 2-week sprints with clear deliverables, adjust scope if needed |
| Testing gaps | High | Medium | Allocate full 2 weeks for testing and polish |
| Documentation incomplete | Medium | Low | Document as you build, allocate dedicated time in Phase 1.5 |

---

## Definition of Done

### For Each Task
- [ ] Code written and committed
- [ ] Unit tests written and passing
- [ ] Code reviewed (self-review minimum)
- [ ] Documentation updated
- [ ] No new warnings or errors

### For Each Epic
- [ ] All tasks completed
- [ ] Integration tests passing
- [ ] Manual testing completed
- [ ] Acceptance criteria met

### For Each Phase
- [ ] All epics completed
- [ ] Phase-level testing completed
- [ ] Documentation complete
- [ ] Demo-ready for stakeholder review

### For Phase 1 Overall
- [ ] All success metrics met
- [ ] Production deployment plan documented
- [ ] User documentation complete
- [ ] Technical documentation complete
- [ ] Known issues documented
- [ ] v1.0.0 tagged and released

---

## Notes

### Development Workflow
1. Work in feature branches
2. Merge to `develop` after self-review
3. Merge to `main` for releases
4. Use conventional commits (feat:, fix:, docs:, test:, refactor:)

### Sprint Cadence (2-week sprints)
- **Week 1**: Development and unit testing
- **Week 2**: Integration testing, bug fixes, documentation

### Tools
- **Project Management**: Plane.so (this plan)
- **Version Control**: Git + GitHub
- **CI/CD**: GitHub Actions (future)
- **Testing**: pytest (backend), Jest (frontend)
- **Code Quality**: Black, flake8, ESLint, Prettier

### Communication
- Daily: Self-check progress against plan
- Weekly: Review completed tasks, adjust priorities
- End of Sprint: Demo and retrospective

---

## Future Phases (Out of Scope for Phase 1)

### Phase 2: TruePeopleSearch Integration
- Person lookup API
- Address history extraction
- Cross-referencing with Gramps data
- Estimated: 4-6 weeks

### Phase 3: 23andMe Integration
- OAuth 2.0 flow
- DNA match retrieval
- Relationship calculation
- Privacy considerations
- Estimated: 6-8 weeks

### Phase 4: Production Deployment
- Custom Docker images (multi-stage builds)
- Kubernetes manifests
- CI/CD pipeline (GitHub Actions)
- Monitoring and logging (Prometheus, Grafana)
- Estimated: 3-4 weeks

---

**Total Phase 1 Effort Estimate**: 235 story points across 10 weeks  
**Average Velocity Target**: 23-24 points per week

This plan is living document and will be updated as needed based on progress and learning.
