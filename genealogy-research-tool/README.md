# Genealogy Research Tool

Automated genealogy research using LLM technology to extract facts from obituaries and build GEDCOM-compliant family trees in Gramps Web.

## Quick Start

See [docs/README.md](docs/README.md) for complete documentation.

**Process an obituary in 3 commands:**
```bash
# 1. Process obituary
curl -X POST "http://localhost:8000/api/obituaries/process" \
  -H "Content-Type: application/json" \
  -d '{"obituary_text": "...", "source_url": "..."}' | python3 -m json.tool

# 2. Generate clusters
curl -X POST http://localhost:8000/api/clusters/generate | python3 -m json.tool

# 3. Create people in Gramps
curl -X POST "http://localhost:8000/api/clusters/{ID}/create-in-gramps?create_relationships=true" | \
  python3 -m json.tool
```

## Documentation

| Document | Description |
|----------|-------------|
| [Documentation Index](docs/README.md) | Overview and quick start |
| [API Reference](docs/API_REFERENCE.md) | Complete API documentation |
| [Changelog](docs/CHANGELOG.md) | Version history |
| [Roadmap](docs/ROADMAP.md) | Future plans |

## Features

- Multi-pass LLM fact extraction
- Maiden name extraction (GEDCOM-compliant)
- Cross-obituary clustering with fuzzy matching
- Multi-source corroboration
- Gramps Web SSOT integration
- GEDCOM-compliant person creation
- Automatic relationship linking
- Complete audit trail

## Status

**Version:** 1.0.0 (Phase 3 Stage 3 Complete)
**Last Updated:** 2026-01-03

### Completed Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Foundation (LLM extraction, caching) | Complete |
| 2 | Clustering & Deduplication | Complete |
| 3.1 | Gramps Integration (Read-Only) | Complete |
| 3.2 | Citation Creation | Complete |
| 3.3 | Person Creation with Relationships | Complete |

See [CHANGELOG.md](docs/CHANGELOG.md) for details.

## Setup

1. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

2. **Start containers:**
```bash
podman-compose up -d
```

3. **Verify health:**
```bash
curl http://localhost:8000/health | python3 -m json.tool
curl http://localhost:8000/api/gramps/health | python3 -m json.tool
```

## Architecture

```
Obituary Text --> LLM Extractor --> Extracted Facts
                                          |
                                          v
Gramps Web <-- Person Creator <-- Person Clusters
  (SSOT)                         (Corroborated)
```

### Key Concepts

- **Fact-Based Architecture** - Extract atomic facts, never bundle prematurely
- **Multi-Source Corroboration** - Higher confidence when facts appear in multiple obituaries
- **Gramps as SSOT** - Gramps Web is the Single Source of Truth
- **GEDCOM Compliance** - Maiden names as primary surnames per genealogy standards

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11+, FastAPI |
| Database | MariaDB (SQLAlchemy 2.0) |
| LLM | OpenAI GPT-4o |
| Genealogy | Gramps Web API |
| Containers | Podman / Podman Compose |

## Test Data

Three real obituaries are included in `backend/tests/test_data/`:
- `patricia_obit.txt` - Patricia L. "Patsy" Blundon (2008)
- `terrence_obit.txt` - Terrence E. Kaczmarowski (2008)
- `maxine_obit.txt` - Maxine V. Kaczmarowski (2018)

## License

GNU General Public License v3.0 - See LICENSE file for details.
