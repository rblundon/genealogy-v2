# Development Methodology Guide

**Version**: 1.0  
**Last Updated**: 2024-12-23  
**Status**: Active

## Overview

This project uses **BMAD (Best Matching Artifact Design)** as the primary development methodology, supplemented with **Spec Anchors** for critical architectural components.

## What is BMAD?

BMAD is an artifact-first development approach where working code informs specification refinement, rather than requiring complete specifications before implementation.

### Core Principles

1. **Build to Learn**: Create working artifacts to discover real constraints
2. **Rapid Iteration**: Test with actual data immediately
3. **Spec Refinement**: Update specifications based on what artifacts teach us
4. **Vertical Slices**: Implement end-to-end features to validate architecture

### When BMAD Works Best

- AI co-pilot development (rapid code generation)
- Integration with unpredictable external systems (LLMs, web scraping, third-party APIs)
- Exploratory work where requirements emerge through building
- MVP/prototype development with clear success criteria

## What are Spec Anchors?

Spec Anchors are components that **must be specified before implementation** because they are:

1. **Critical for data integrity** (e.g., SSOT validation)
2. **Architectural foundations** (e.g., caching strategy)
3. **Cross-cutting concerns** (e.g., confidence scoring)

### Our Three Spec Anchors

1. **`specs/ssot-validation.md`**: Rules for writing to Gramps Web (SSOT)
   - **Why**: Data corruption is unacceptable
   - **Spec First**: Conflict detection, approval workflows, audit trails

2. **`specs/caching-strategy.md`**: Three-layer caching architecture
   - **Why**: Wrong decisions affect cost and performance
   - **Spec First**: Cache keys, invalidation, TTLs

3. **`specs/confidence-scoring.md`**: Confidence scoring algorithm
   - **Why**: Affects UX and data quality
   - **Spec First**: Scoring factors, thresholds, penalties

## Development Workflow

### Phase 1.1: Foundation (Weeks 1-2)

**SPEC ANCHORS (Write First):**
1. Review and approve all three spec documents
2. Ensure team alignment on approach
3. Identify any missing specs

**ARTIFACTS (Build After Specs):**
1. Development environment (Podman Desktop)
2. Container setup (MariaDB, Gramps Web, FastAPI, React)
3. Database connection and basic CRUD
4. Health checks and logging

**Exit Criteria:**
- [ ] All spec anchors approved
- [ ] Containers running successfully
- [ ] Can insert/query test data
- [ ] Health checks return 200 OK

### Phase 1.2: Core Processing (Weeks 3-4)

**BMAD ITERATION:**
1. **Build**: Web scraping, LLM integration, caching
2. **Test**: Process 5-10 diverse obituaries
3. **Measure**: LLM accuracy, cache hit rates
4. **Learn**: What does LLM get right/wrong?
5. **Refine**: Tune prompts based on results

**Exit Criteria:**
- [ ] Can fetch and cache obituaries (≥80% hit rate)
- [ ] LLM extracts persons (≥70% accuracy)
- [ ] No duplicate API calls for same content

**Spec Updates:**
- Document LLM behavior patterns in `specs/llm-behavior-patterns.md`
- Update confidence thresholds if needed

### Phase 1.3: Matching & Storage (Weeks 5-6)

**SSOT-GUIDED IMPLEMENTATION:**
1. **Build**: Matching algorithm, SSOT validation, Gramps connector
2. **Test**: Process obituaries with people already in Gramps Web
3. **Measure**: False positive/negative match rates
4. **Validate**: SSOT validation catches all conflicts

**Exit Criteria:**
- [ ] Matching accuracy ≥80%
- [ ] No unauthorized Gramps modifications (100% validation)
- [ ] All conflicts flagged (0% missed)
- [ ] Complete audit trail

**Spec Updates:**
- Formalize matching algorithm based on accuracy
- Document edge cases found

### Phase 1.4: UI & Review (Weeks 7-8)

**UX ITERATION:**
1. **Build**: React components, review workflow
2. **Test**: Process and review real obituaries
3. **Measure**: Time to review entity (<2 minutes target)
4. **Refine**: Improve clarity of conflict displays

**Exit Criteria:**
- [ ] End-to-end processing works
- [ ] Conflicts clearly displayed
- [ ] User can approve/reject/edit
- [ ] Changes persist correctly

**Spec Updates:**
- Document UX patterns in `docs/ui-guidelines.md`

### Phase 1.5: Polish & Testing (Weeks 9-10)

**REFINEMENT:**
1. Error handling improvements
2. Performance optimization
3. Comprehensive testing (≥90% coverage)
4. Documentation completion

**Exit Criteria:**
- [ ] All tests pass
- [ ] Performance targets met (<30s processing)
- [ ] Cache hit rate ≥70%
- [ ] Cost per obituary <$0.10

**Final Spec Update:**
- Update PRD with lessons learned
- Create CHANGELOG.md with v1.0.0 release notes

## Key Decision Principle

> **Spec what you can't afford to get wrong. Build what you need to learn.**

### Spec First (Before Building)
- Data integrity rules
- SSOT validation logic
- Audit trail requirements
- Caching architecture
- Confidence scoring algorithm

### Build First (To Learn)
- LLM prompt engineering
- Matching algorithm tuning
- Web scraping implementation
- UI components
- Gramps Web API integration

## When to Update Specs

### Trigger Conditions
1. **LLM Behavior Discovery**: After 20+ obituaries, document accuracy patterns
2. **Edge Cases Found**: Artifacts reveal scenarios not in original spec
3. **Performance Data**: Cache hits or costs differ from assumptions
4. **Matching Tuning**: False positive/negative rates measured
5. **User Feedback**: Manual review reveals UX issues

### Update Process
1. Document constraint in artifact comments
2. Create GitHub issue linking artifact to spec gap
3. Update relevant spec document
4. Update PRD section 15 (Open Questions & Decisions)
5. Add to CHANGELOG.md with version bump

## Why Not Open Spec?

Open Spec would be **too rigid** for this project because:

- **External System Constraints**: Gramps Web, OpenAI impose limitations discovered through integration
- **LLM Unpredictability**: Cannot fully specify LLM behavior without experimentation
- **Rapid Prototyping**: AI co-pilot thrives on fast iteration
- **Third-Party APIs**: Cannot control external changes

Open Spec is ideal for greenfield projects with full control. We're integrating existing systems that reveal constraints through building.

## Tools & Practices

### Version Control
- Git with feature branches
- Commit messages reference specs when implementing anchors
- Tag releases with semantic versioning

### Documentation
- **Living Documents**: PRD, spec anchors (update as we learn)
- **Artifact Documentation**: Docstrings, inline comments
- **Decision Records**: `docs/architecture-decisions.md`

### Testing Strategy
- Unit tests for business logic
- Integration tests for database/API
- Mock external services (OpenAI, web scraping)
- Test with curated obituary set

### Code Review
- All spec anchor implementations require review
- BMAD artifacts can be reviewed post-merge
- Focus reviews on SSOT validation and data integrity

## Success Metrics

### Phase 1 Success Criteria
- Extract data from 90%+ obituaries
- Identify deceased person in 95%+ cases
- Relationship accuracy ≥80%
- Auto-store rate ≥60% (non-conflicting)
- **Zero unauthorized SSOT modifications**
- **100% user approval for conflicts**
- Cost per obituary <$0.10
- Cache hit rate ≥70%

### Quality Metrics
- User correction rate
- False positive/negative match rates
- Average confidence score for auto-stored
- Conflict detection accuracy
- Data integrity score

## Team Guidelines

### For Developers
1. **Read spec anchors before implementing** dependent code
2. **Document learnings** as you build (comments, notes)
3. **Update specs** when you discover constraints
4. **Test with real data** as early as possible
5. **Don't bypass SSOT validation** for convenience

### For Reviewers
1. **Verify spec anchor compliance** (critical)
2. **Check SSOT validation** (no shortcuts)
3. **Ensure audit logging** (complete trail)
4. **Review error handling** (graceful degradation)
5. **Validate with test data** (not just code review)

### For AI Co-Pilot (Claude)
1. **Always read specs first** for anchored components
2. **Build working code** for exploratory work
3. **Document assumptions** in comments
4. **Suggest spec updates** when discovering constraints
5. **Prioritize data integrity** over convenience

## Common Pitfalls to Avoid

### ❌ Don't Do This
- Skip reading spec anchors before implementation
- Build SSOT validation without specification
- Modify Gramps Web without validation
- Cache without considering invalidation
- Hardcode confidence thresholds
- Implement without testing with real obituaries

### ✅ Do This
- Review specs before building dependent code
- Validate all writes against current Gramps state
- Always use configuration for thresholds
- Test with diverse, real obituaries early
- Document what you learn as you build
- Update specs when artifacts teach you something

## Resources

### Specs
- `specs/ssot-validation.md` - SSOT validation rules
- `specs/caching-strategy.md` - Caching architecture
- `specs/confidence-scoring.md` - Confidence algorithm

### Documentation
- `genealogy-prd.md` - Product requirements
- `README.md` - Quick start guide
- `docs/architecture-decisions.md` - ADRs

### Example Code
- `models/cache_models.py` - Database models
- `utils/config.py` - Configuration management
- `utils/hash_utils.py` - Hashing utilities

---

**Remember**: The goal isn't perfect specs upfront. It's to spec what matters most (data integrity, architecture), then learn through building.

**Questions?** Review PRD Section 2 (Development Methodology) or ask the team.
