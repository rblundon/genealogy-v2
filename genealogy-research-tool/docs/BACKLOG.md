# Product Backlog

## Phase 4: Production Features

### High Priority

**Remove obituary_text Parameter**
- **Status:** Future enhancement
- **Description:** Once UI is built, remove `obituary_text` parameter from API. URL-only input.
- **Effort:** Small (1-2 hours)
- **Depends on:** UI completion

**Obituary Report UI**
- **Status:** Planned for Phase 5
- **Description:** UI view for each obituary with options to:
  - View extracted facts
  - Re-process obituary (retry extraction)
  - Delete obituary from cache
- **Effort:** Medium (1-2 days)
- **Depends on:** Basic UI framework

**Interactive Processing Workflow**
- **Status:** Planned for Phase 5
- **Description:** Step-by-step UI workflow:
  1. Submit obituary URL
  2. Review extracted facts
  3. Approve/edit person clusters
  4. Create in Gramps with confirmation
- **Effort:** Large (1 week)
- **Depends on:** Obituary Report UI

### Medium Priority

**Batch Processing UI**
- **Status:** Future
- **Description:** Process multiple obituaries at once
- **Effort:** Medium

**Source Management**
- **Status:** Future
- **Description:** View all sources, see which are in Gramps, bulk operations
- **Effort:** Small

### Low Priority

**Playwright Integration**
- **Status:** Optional upgrade
- **Description:** Replace BeautifulSoup with Playwright for JavaScript-heavy sites
- **Effort:** Medium
- **Trigger:** If Legacy.com blocks BeautifulSoup

**Additional Site Support**
- **Status:** Future
- **Description:** Add extractors for Tributes.com, funeral homes, newspapers
- **Effort:** Medium per site

---

Last Updated: 2026-01-09
