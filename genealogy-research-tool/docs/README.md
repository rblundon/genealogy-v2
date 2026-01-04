# Genealogy Research Tool - Documentation

**Version:** 1.0.0
**Last Updated:** 2026-01-03

---

## Overview

The Genealogy Research Tool automates family history research by extracting facts from obituaries using LLM technology and building GEDCOM-compliant family trees in Gramps Web.

### Key Features

- **Multi-pass LLM Extraction** - Intelligent fact extraction from obituary text
- **GEDCOM-compliant Naming** - Maiden names as primary surnames per genealogy standards
- **Cross-obituary Clustering** - Fuzzy matching to identify same person across sources
- **Multi-source Corroboration** - Higher confidence when facts appear in multiple obituaries
- **Gramps Web Integration** - Direct synchronization with Gramps as Single Source of Truth
- **Automatic Relationships** - Family relationship creation from extracted facts
- **Complete Audit Trail** - Full traceability of all data sources

---

## Quick Start

### Process an Obituary in 3 Commands

```bash
# 1. Process obituary text
curl -X POST "http://localhost:8000/api/obituaries/process" \
  -H "Content-Type: application/json" \
  -d '{"obituary_text": "...", "source_url": "http://example.com/obit"}' | python3 -m json.tool

# 2. Generate person clusters
curl -X POST http://localhost:8000/api/clusters/generate | python3 -m json.tool

# 3. Create person in Gramps with relationships
curl -X POST "http://localhost:8000/api/clusters/{ID}/create-in-gramps?create_relationships=true" | \
  python3 -m json.tool
```

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [API Reference](API_REFERENCE.md) | Complete API documentation with examples |
| [Changelog](CHANGELOG.md) | Version history and release notes |
| [Roadmap](ROADMAP.md) | Future development plans |

---

## Architecture

```
+------------------+     +------------------+     +------------------+
|   Obituary Text  | --> |   LLM Extractor  | --> |  Extracted Facts |
+------------------+     +------------------+     +------------------+
                                                          |
                                                          v
+------------------+     +------------------+     +------------------+
|   Gramps Web     | <-- |  Person Creator  | <-- |  Person Clusters |
|   (SSOT)         |     |                  |     |  (Corroborated)  |
+------------------+     +------------------+     +------------------+
```

### Components

1. **Obituary Cache** - Stores fetched obituary text and metadata
2. **LLM Cache** - Caches LLM responses to avoid redundant API calls
3. **Extracted Facts** - Individual facts with confidence scores
4. **Person Clusters** - Groups of facts representing the same person
5. **Gramps Citations** - Links between clusters and Gramps records

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11+, FastAPI |
| Database | MariaDB (SQLAlchemy 2.0) |
| LLM | OpenAI GPT-4o |
| Genealogy | Gramps Web API |
| Containers | Podman / Podman Compose |

---

## Project Structure

```
genealogy-research-tool/
├── backend/
│   ├── main.py                 # FastAPI application
│   ├── models.py               # SQLAlchemy models
│   └── services/
│       ├── gramps_client.py         # Gramps Web API client
│       ├── gramps_person_creator.py # Person creation service
│       ├── gramps_citation_service.py # Citation management
│       ├── fact_clusterer.py        # Cross-obituary clustering
│       └── llm_extractor.py         # LLM fact extraction
├── docs/
│   ├── README.md               # This file
│   ├── API_REFERENCE.md        # Complete API documentation
│   ├── CHANGELOG.md            # Version history
│   └── ROADMAP.md              # Future plans
├── podman-compose.yaml         # Container orchestration
└── .env                        # Environment configuration
```

---

## Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for LLM | `sk-...` |
| `GRAMPS_WEB_URL` | Gramps Web base URL | `http://gramps.local:80` |
| `GRAMPS_API_TOKEN` | Gramps Web API token | `eyJ...` |
| `MARIADB_HOST` | Database host | `genealogy-mariadb` |
| `MARIADB_DATABASE` | Database name | `genealogy_cache` |

---

## Common Workflows

### View All Clusters
```bash
curl -s http://localhost:8000/api/clusters | python3 -m json.tool | \
  jq '.clusters[] | {cluster_id, canonical_name, source_count, gramps_person_id}'
```

### Check Gramps Connectivity
```bash
curl http://localhost:8000/api/gramps/health | python3 -m json.tool
```

### View Audit Trail
```bash
curl http://localhost:8000/api/gramps/audit-trail | python3 -m json.tool
```

### Debug a Cluster
```bash
curl http://localhost:8000/api/clusters/85 | python3 -m json.tool
```

---

## Known Limitations

1. **Citation Linking** - Currently disabled due to Gramps API 400 errors
2. **Gender Inference** - Not yet implemented (all persons created with Unknown gender)
3. **Place Normalization** - Places are stored as raw text, not linked to Gramps places

See [ROADMAP.md](ROADMAP.md) for planned improvements.

---

## Support

- **Issues:** Report bugs and feature requests on GitHub
- **Documentation:** See [API_REFERENCE.md](API_REFERENCE.md) for detailed API docs

---

## License

GNU General Public License v3.0 - See LICENSE file for details.
