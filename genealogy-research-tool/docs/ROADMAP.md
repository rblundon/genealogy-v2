# Roadmap

Future development plans for the Genealogy Research Tool.

**Last Updated:** 2026-01-03

---

## Current Status

**Version:** 1.0.0 (Phase 3 Stage 3 Complete)

### Completed Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Foundation (LLM extraction, caching, models) | Complete |
| 2 | Clustering & Deduplication | Complete |
| 2.5 | Debugging & Fixes | Complete |
| 3.1 | Gramps Integration (Read-Only) | Complete |
| 3.2 | Citation Creation | Complete |
| 3.3 | Person Creation with Relationships | Complete |

---

## Phase 4: Enhanced Relationships

### 4.1 - Family Structure Improvements
- [ ] Create proper Family records in Gramps (not just person links)
- [ ] Handle spouse relationships with marriage events
- [ ] Support multiple marriages per person
- [ ] Add marriage date/place extraction

### 4.2 - Sibling Detection
- [ ] Infer sibling relationships from shared parents
- [ ] Cross-reference parent names across obituaries
- [ ] Create sibling links automatically

### 4.3 - Extended Family
- [ ] Grandparent relationship handling
- [ ] Aunt/Uncle/Cousin detection
- [ ] In-law relationship mapping

---

## Phase 5: Data Quality

### 5.1 - Gender Inference
- [ ] Infer gender from relationship types (wife, husband, mother, father)
- [ ] Use name databases for gender prediction
- [ ] Handle gender for existing Gramps records

### 5.2 - Place Normalization
- [ ] Link extracted places to Gramps Place records
- [ ] Geocoding for place coordinates
- [ ] Place hierarchy (city, county, state, country)

### 5.3 - Date Normalization
- [ ] Handle approximate dates ("about 1950", "circa 1920")
- [ ] Support date ranges
- [ ] Validate date consistency (birth before death, etc.)

### 5.4 - Conflict Resolution
- [ ] Detect conflicting facts across obituaries
- [ ] Present conflicts to user for resolution
- [ ] Track resolution decisions

---

## Phase 6: User Interface

### 6.1 - Web Dashboard
- [ ] Vue.js or React frontend
- [ ] Cluster review interface
- [ ] Drag-and-drop relationship editing
- [ ] Side-by-side obituary comparison

### 6.2 - Batch Processing
- [ ] Upload multiple obituaries at once
- [ ] Progress tracking for large batches
- [ ] Error handling and retry

### 6.3 - Search & Filter
- [ ] Full-text search across obituaries
- [ ] Filter by date range, location, family
- [ ] Advanced query builder

---

## Phase 7: Integration Enhancements

### 7.1 - Citation Linking Fix
- [ ] Debug Gramps API 400 errors on citation linking
- [ ] Alternative citation attachment methods
- [ ] Bulk citation updates

### 7.2 - Gramps Sync
- [ ] Bi-directional sync with Gramps
- [ ] Detect changes made in Gramps UI
- [ ] Merge external updates

### 7.3 - External Sources
- [ ] FindAGrave integration
- [ ] Newspapers.com integration
- [ ] FamilySearch hints

---

## Phase 8: AI Improvements

### 8.1 - Model Optimization
- [ ] Fine-tune extraction prompts for better accuracy
- [ ] Reduce token usage for cost savings
- [ ] Add local LLM option (Ollama)

### 8.2 - Confidence Scoring
- [ ] Improved confidence algorithms
- [ ] Source reliability weighting
- [ ] Temporal decay for old sources

### 8.3 - Relationship Inference
- [ ] AI-powered relationship suggestion
- [ ] Pattern recognition across families
- [ ] Anomaly detection (missing expected relatives)

---

## Phase 9: Production Readiness

### 9.1 - Security
- [ ] API authentication
- [ ] Rate limiting
- [ ] Input sanitization audit

### 9.2 - Performance
- [ ] Database query optimization
- [ ] Caching layer (Redis)
- [ ] Async processing for large imports

### 9.3 - Deployment
- [ ] Docker Compose for production
- [ ] Kubernetes manifests
- [ ] CI/CD pipeline

### 9.4 - Monitoring
- [ ] Health check endpoints
- [ ] Metrics collection (Prometheus)
- [ ] Alerting for errors

---

## Backlog (Unscheduled)

These items are valuable but not yet prioritized:

- [ ] GEDCOM export/import
- [ ] DNA match integration
- [ ] Photo extraction from obituary pages
- [ ] OCR for scanned obituaries
- [ ] Multi-language support
- [ ] Collaborative editing
- [ ] Version control for Gramps data
- [ ] Backup/restore functionality
- [ ] Mobile-friendly interface

---

## Contributing

Interested in contributing? Here's how:

1. **Pick an item** from the roadmap
2. **Open an issue** to discuss approach
3. **Submit a PR** with your implementation

Priority is given to items in earlier phases, but contributions to any area are welcome.

---

## Feedback

Have suggestions for the roadmap? Please open an issue with:
- Feature description
- Use case / problem it solves
- Any implementation ideas
