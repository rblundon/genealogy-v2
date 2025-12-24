# Genealogy Research Tool

**Version**: 1.0.0-dev  
**Status**: Phase 1 Development  
**License**: GPL-3.0

A containerized, web-based genealogy research tool that automates extraction and organization of family relationship data from obituaries using LLM technology and GEDCOM-compliant storage.

## 🎯 Project Goals

- Reduce manual data entry time for genealogical research by 80%+
- Automatically extract and structure relationship data from unstructured sources
- Maintain GEDCOM compliance via Gramps Web integration
- Build cost-effective foundation with intelligent caching (<$0.10 per obituary)

## 🏗️ Architecture

### Core Principles

1. **Gramps Web is Single Source of Truth (SSOT)** - All genealogical data lives here
2. **MariaDB as Cache** - Obituary content, LLM responses, extracted entities (staging area)
3. **12-Factor App** - Configuration in environment, stateless processes, logs to stdout
4. **BMAD + Spec Anchors** - Rapid iteration with safety guardrails for critical components

### Technology Stack

- **Backend**: Python 3.11+ with FastAPI
- **Frontend**: React with Vite
- **Primary DB (SSOT)**: Gramps Web (GEDCOM-compliant)
- **Cache DB**: MariaDB (obituary content, LLM responses, entities)
- **LLM**: OpenAI API (extensible to other providers)
- **ORM**: SQLAlchemy
- **Containers**: Podman (dev), Kubernetes (future production)

## 📚 Documentation

### Getting Started
- **[Quick Start Guide](#quick-start)** - Get running in 10 minutes
- **[Development Setup](#development-setup)** - Full development environment

### Methodology & Specs
- **[DEVELOPMENT_METHODOLOGY.md](./DEVELOPMENT_METHODOLOGY.md)** - BMAD + Spec Anchors approach
- **[specs/ssot-validation.md](./specs/ssot-validation.md)** - ⚓ SSOT write validation rules
- **[specs/caching-strategy.md](./specs/caching-strategy.md)** - ⚓ Three-layer caching architecture
- **[specs/confidence-scoring.md](./specs/confidence-scoring.md)** - ⚓ Confidence algorithm

### Product & Architecture
- **[genealogy-prd.md](./genealogy-prd.md)** - Complete product requirements
- **[docs/architecture-decisions.md](./docs/architecture-decisions.md)** - ADRs (coming soon)

## 🚀 Quick Start

### Prerequisites

- Podman Desktop installed (or Docker)
- Python 3.11+
- Node.js 20+
- OpenAI API key

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/genealogy-research-tool.git
cd genealogy-research-tool
```

### 2. Configure Environment

```bash
cp env.example .env
# Edit .env with your credentials:
# - MARIADB_PASSWORD
# - OPENAI_API_KEY
# - GRAMPS_API_TOKEN (if using external Gramps Web)
```

### 3. Start Containers

```bash
podman-compose -f podman-compose.yml up -d
```

### 4. Verify Services

```bash
# Check health
curl http://localhost:8000/health  # Backend
curl http://localhost:3000          # Frontend
curl http://localhost:5555/api/metadata  # Gramps Web
```

### 5. Process Your First Obituary

1. Open browser: http://localhost:3000
2. Paste obituary URL
3. Click "Process"
4. Review extracted entities
5. Approve/edit as needed

## 🛠️ Development Setup

### Development Philosophy

This project uses **BMAD (Best Matching Artifact Design)** with **Spec Anchors** for critical components. Read [DEVELOPMENT_METHODOLOGY.md](./DEVELOPMENT_METHODOLOGY.md) before contributing.

### Required Reading (Before Coding)

If you're implementing code that touches these areas, **read the specs first**:

1. **Writing to Gramps Web?** → Read `specs/ssot-validation.md`
2. **Implementing caching?** → Read `specs/caching-strategy.md`
3. **Scoring confidence?** → Read `specs/confidence-scoring.md`

### Development Container Setup

```bash
# Development uses bind mounts for live code editing
podman-compose -f podman-compose.dev.yml up -d

# Backend hot reload (uvicorn --reload)
# Frontend hot reload (Vite HMR)
```

### Project Structure

```
genealogy-research-tool/
├── backend/
│   ├── models/
│   │   ├── database.py          # SQLAlchemy setup
│   │   └── cache_models.py      # ORM models
│   ├── services/
│   │   ├── obituary_fetcher.py  # Web scraping
│   │   ├── llm_extractor.py     # OpenAI integration
│   │   ├── gramps_connector.py  # Gramps Web API
│   │   └── matcher.py           # Entity matching
│   ├── api/
│   │   └── endpoints/           # FastAPI routes
│   ├── utils/
│   │   ├── config.py            # Config helper
│   │   └── hash_utils.py        # Cache key generation
│   └── main.py
├── frontend/
│   └── src/
│       ├── components/          # React components
│       └── pages/               # Page components
├── specs/                       # ⚓ Spec Anchors (read first!)
│   ├── ssot-validation.md
│   ├── caching-strategy.md
│   └── confidence-scoring.md
├── docs/
│   └── architecture-decisions.md
├── database/
│   └── schema.sql               # MariaDB schema
├── podman-compose.yml           # Production-like
├── podman-compose.dev.yml       # Development (bind mounts)
└── .env.example
```

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test

# Integration tests
pytest tests/integration/
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migration
alembic upgrade head
```

## 🔒 Data Integrity & SSOT

**Critical**: Gramps Web is the Single Source of Truth for all genealogical data.

### Rules

1. **Never write to Gramps Web without validation** (see `specs/ssot-validation.md`)
2. **Always query Gramps Web for current data** (never rely on cache as authority)
3. **All modifications require audit logging** (complete trail)
4. **Conflicts always require user approval** (no auto-apply)

### Validation Flow

```
Extracted Entity
      ↓
Query Gramps Web (SSOT)
      ↓
Detect Conflicts? → Yes → Flag for Review
      ↓ No
Non-conflicting? → Yes → Auto-store (if high confidence)
      ↓ No
Ambiguous Match? → Yes → Flag for Review
```

## 💰 Cost Management

### Target: <$0.10 per obituary

### Cost Optimization

- **Three-layer caching** (obituary, LLM, entities)
- **Cache hit rate target**: ≥70%
- **Avoid redundant API calls**
- **Use GPT-3.5-turbo for simple extractions** (future)

### Monitoring

```bash
# Check cost dashboard
curl http://localhost:8000/api/cost/dashboard

# Daily cost summary
curl http://localhost:8000/api/cost/daily
```

## 🎛️ Configuration

All thresholds are tunable via UI or database:

| Setting | Default | Description |
|---------|---------|-------------|
| `confidence_threshold_auto_store` | 0.85 | Min confidence for auto-store |
| `confidence_threshold_review` | 0.60 | Min confidence for review |
| `always_review` | false | Require review even for high confidence |
| `cache_expiry_days` | 365 | Obituary cache TTL |

## 📊 Success Metrics (Phase 1)

- [ ] Extract data from 90%+ obituaries
- [ ] Identify deceased person in 95%+ cases
- [ ] Relationship accuracy ≥80%
- [ ] Auto-store rate ≥60% (non-conflicting)
- [ ] **Zero unauthorized SSOT modifications**
- [ ] **100% user approval for conflicts**
- [ ] Cost per obituary <$0.10
- [ ] Cache hit rate ≥70%
- [ ] Processing time <30s per obituary

## 🚧 Current Status: Phase 1 Development

### Completed
- [x] PRD with BMAD methodology
- [x] Three spec anchors written
- [x] Database schema designed
- [x] Development methodology documented

### In Progress
- [ ] Phase 1.1: Foundation (Weeks 1-2)
  - [ ] Spec anchors approved
  - [ ] Container setup
  - [ ] Basic FastAPI structure
  - [ ] Database connection

### Upcoming
- [ ] Phase 1.2: Core Processing (Weeks 3-4)
- [ ] Phase 1.3: Matching & Storage (Weeks 5-6)
- [ ] Phase 1.4: UI & Review (Weeks 7-8)
- [ ] Phase 1.5: Polish & Testing (Weeks 9-10)

## 🤝 Contributing

### Before Contributing

1. Read [DEVELOPMENT_METHODOLOGY.md](./DEVELOPMENT_METHODOLOGY.md)
2. Review relevant spec anchors for your work
3. Understand SSOT validation rules
4. Test with real obituaries

### Development Workflow

1. Create feature branch
2. Read specs if implementing anchored code
3. Write tests
4. Implement with real data testing
5. Document learnings
6. Update specs if constraints discovered
7. Submit PR with spec references

### Code Quality

- Type hints for all Python functions
- Docstrings for all functions/classes
- Structured logging (JSON format)
- No hardcoded credentials
- SQLAlchemy ORM (no raw SQL unless necessary)
- Error handling with try/except

## 📝 License

GNU General Public License v3.0 - see [LICENSE](./LICENSE) for details.

## 🆘 Troubleshooting

### Containers won't start

```bash
# Check logs
podman-compose logs

# Rebuild
podman-compose down
podman-compose up --build
```

### Database connection errors

```bash
# Check MariaDB health
podman exec genealogy-mariadb healthcheck.sh

# Reinitialize schema
podman exec genealogy-mariadb mysql -u root -p genealogy_cache < database/schema.sql
```

### LLM API errors

```bash
# Check API key in .env
cat .env | grep OPENAI_API_KEY

# Test API directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Cache not working

```bash
# Check cache statistics
curl http://localhost:8000/api/cache/stats

# Clear cache (if needed)
curl -X POST http://localhost:8000/api/cache/clear
```

## 📧 Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: [Your Email]

## 🙏 Acknowledgments

- **Gramps Web**: GEDCOM-compliant genealogy platform
- **OpenAI**: LLM technology for entity extraction
- **12-Factor App**: Architecture principles

---

**Ready to start?** Read [DEVELOPMENT_METHODOLOGY.md](./DEVELOPMENT_METHODOLOGY.md) and then dive into Phase 1.1!
