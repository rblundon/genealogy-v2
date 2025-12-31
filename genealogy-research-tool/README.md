# Genealogy Research Tool

Extract genealogical facts from obituaries using LLM technology with multi-source corroboration.

## Phase 1: Foundation

Current capabilities:
- Multi-pass LLM extraction (person mentions -> facts)
- Proper handling of parenthetical notation: "Ryan (Amy)" -> 2 people
- Nickname extraction: "Patricia L. 'Patsy'"
- Maiden name parsing: "(nee Kaczmarowski)"
- Confidence scoring with inference tracking
- LLM response caching (cost optimization)
- Fact-based architecture (not entity-based)

## Quick Start

1. **Setup environment:**
```bash
cp .env.example .env
# Edit .env with your OpenAI API key and database password
```

2. **Start containers:**
```bash
podman-compose up -d
```

3. **Run tests:**
```bash
cd backend
python -m pytest tests/test_extraction.py -v -s
```

4. **Process an obituary via API:**
```bash
curl -X POST http://localhost:8000/api/obituaries/process \
  -H "Content-Type: application/json" \
  -d '{
    "obituary_text": "Your obituary text here...",
    "source_url": "http://example.com/obituary"
  }'
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/obituaries/process` | POST | Process an obituary |
| `/api/obituaries/{id}/facts` | GET | Get facts for an obituary |
| `/api/obituaries` | GET | List all obituaries |
| `/api/facts/by-person/{name}` | GET | Get facts by person name |

## Test Data

Three real obituaries are included in `backend/tests/test_data/`:
- `patricia_obit.txt` - Patricia L. "Patsy" Blundon (2008)
- `terrence_obit.txt` - Terrence E. Kaczmarowski (2008)
- `maxine_obit.txt` - Maxine V. Kaczmarowski (2018)

These demonstrate:
- Name variants across obituaries
- Fuzzy matching needs (Rose Mary vs Rosemary)
- Timeline validation (Patricia died before Terrence)
- Multi-source corroboration

## Architecture

**Fact-Based Approach:**
- Extract atomic facts (claims with confidence scores)
- Never bundle facts into entities prematurely
- Enable multi-source corroboration
- Gramps Web is Single Source of Truth (SSOT)

**Multi-Pass Extraction:**
1. Pass 1: Extract person mentions (handle parenthetical notation)
2. Pass 2: Extract facts about each person

**Database:**
- `obituary_cache` - Raw obituary content
- `llm_cache` - LLM requests/responses (cost optimization)
- `extracted_facts` - THE core table (atomic claims)
- `person_clusters` - Same person across obituaries (Phase 2)

## Project Structure

```
genealogy-research-tool/
├── backend/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── obituary.py
│   │   ├── fact.py
│   │   └── config.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_extractor.py
│   │   └── person_matcher.py (stub for Phase 2)
│   ├── utils/
│   │   ├── __init__.py
│   │   └── hash_utils.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_data/
│   │   │   ├── terrence_obit.txt
│   │   │   ├── maxine_obit.txt
│   │   │   └── patricia_obit.txt
│   │   ├── test_extraction.py
│   │   └── expected_facts.py
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── database/
│   └── schema.sql
├── podman-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## Next Steps (Phase 2)

- [ ] Cross-obituary clustering (fuzzy matching)
- [ ] Multi-source corroboration
- [ ] Gramps Web integration (SSOT resolution)
- [ ] Conflict detection
- [ ] Review UI

## License

MIT
