# Genealogy Research Tool

A containerized, web-based genealogy research tool that automates the extraction and organization of family relationship data from obituaries using LLM technology.

## Overview

This tool streamlines genealogical research by:
- Automatically extracting person and relationship data from obituary URLs
- Using LLM technology (OpenAI GPT-4) for intelligent entity extraction
- Maintaining GEDCOM-compliant data in Gramps Web (Single Source of Truth)
- Providing intelligent caching to minimize API costs
- Offering manual review workflow for conflict resolution

## Features

- ✅ **Automated Obituary Processing**: Submit a URL, get structured genealogical data
- ✅ **LLM-Powered Extraction**: Uses GPT-4 to extract persons, relationships, dates, and locations
- ✅ **SSOT Architecture**: Gramps Web as authoritative database, MariaDB for caching
- ✅ **Intelligent Matching**: Fuzzy name matching with confidence scoring
- ✅ **Conflict Detection**: Validates against existing data before modifying
- ✅ **Cost Optimization**: Three-layer caching system (obituary content, LLM responses, entities)
- ✅ **Manual Review**: User interface for reviewing and resolving conflicts

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Frontend  │─────▶│   Backend    │─────▶│  Gramps Web │
│   (React)   │      │  (FastAPI)   │      │    (SSOT)   │
└─────────────┘      └──────────────┘      └─────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │   MariaDB    │
                     │   (Cache)    │
                     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  OpenAI API  │
                     │   (GPT-4)    │
                     └──────────────┘
```

## Tech Stack

- **Backend**: Python 3.11+ with FastAPI
- **Frontend**: React with Vite and TypeScript
- **Primary Database**: Gramps Web (GEDCOM-compliant)
- **Cache Database**: MariaDB 10.11
- **LLM Provider**: OpenAI (extensible to others)
- **ORM**: SQLAlchemy
- **Containers**: Podman (development), Kubernetes (production future)

## Quick Start

### Prerequisites

- **Podman Desktop** or **Docker Desktop** installed
- **Python 3.11+** (for local development)
- **Node.js 20+** (for frontend development)
- **OpenAI API Key** (for LLM extraction)
- **Git**

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd genealogy-research-tool
   ```

2. **Copy environment template**:
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env` file** with your credentials:
   ```bash
   # Required: OpenAI API key
   OPENAI_API_KEY=sk-your-key-here
   
   # Required: Database passwords
   MARIADB_ROOT_PASSWORD=your_secure_root_password
   MARIADB_PASSWORD=your_secure_db_password
   
   # Required: Gramps Web API token (generate after first startup)
   GRAMPS_API_TOKEN=your_gramps_token_here
   ```

4. **Start containers**:
   ```bash
   podman-compose -f podman-compose.dev.yml up -d
   ```

5. **Verify services are running**:
   ```bash
   podman ps
   ```
   
   You should see 4 containers:
   - `genealogy-mariadb` (port 3306)
   - `genealogy-grampsweb` (port 5555)
   - `genealogy-backend` (port 8000)
   - `genealogy-frontend` (port 3000)

6. **Initialize Gramps Web** (first time only):
   - Open http://localhost:5555 in browser
   - Create admin account
   - Generate API token in settings
   - Add token to `.env` file as `GRAMPS_API_TOKEN`
   - Restart backend: `podman-compose -f podman-compose.dev.yml restart backend`

7. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Gramps Web: http://localhost:5555

### Development Setup

#### Backend Development

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run backend with hot reload (if not using containers)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Run frontend with hot reload (if not using containers)
npm run dev
```

#### Database Migrations

```bash
cd backend

# Create new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## Usage

### Processing an Obituary

1. Navigate to http://localhost:3000
2. Enter obituary URL in the input field
3. Click "Process"
4. Monitor progress through stages:
   - Checking cache
   - Fetching obituary content
   - Extracting entities with LLM
   - Matching with existing records
   - Storing data
5. Review results:
   - Auto-stored entities (high confidence, non-conflicting)
   - Entities flagged for review (conflicts or low confidence)

### Manual Review Workflow

1. Click "Review Queue" from homepage
2. For each entity:
   - View extracted data with confidence scores
   - See side-by-side comparison if conflict exists
   - Choose resolution:
     - Keep Gramps Web data (ignore extraction)
     - Use extracted data (update Gramps)
     - Merge both
     - Edit manually
3. Approve changes
4. Data is committed to Gramps Web with source citations

### Configuration

Access configuration page at http://localhost:3000/config

Tunable parameters:
- **Auto-store confidence threshold**: Minimum score for automatic storage (default: 0.85)
- **Review confidence threshold**: Minimum score to flag for review (default: 0.60)
- **Always require review**: Force manual review for all extractions
- **Cache expiry days**: How long to cache obituary content (default: 365)
- **Cost alert threshold**: Daily cost limit before alert

## Project Structure

```
genealogy-research-tool/
├── backend/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py          # SQLAlchemy setup
│   │   └── cache_models.py      # ORM models
│   ├── services/
│   │   ├── obituary_fetcher.py  # Web scraping
│   │   ├── llm_extractor.py     # OpenAI integration
│   │   ├── gramps_connector.py  # Gramps Web API
│   │   └── matcher.py           # Entity matching
│   ├── api/
│   │   ├── endpoints/           # FastAPI routes
│   │   └── dependencies.py      # Dependency injection
│   ├── utils/
│   │   ├── config.py            # Config helper
│   │   └── hash_utils.py        # Hashing utilities
│   ├── tests/                   # Test suite
│   ├── main.py                  # FastAPI application
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── pages/               # Page components
│   │   ├── services/            # API client
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── database/
│   └── schema.sql               # MariaDB schema
├── docs/
│   ├── architecture.md
│   ├── api.md
│   └── development.md
├── podman-compose.dev.yml       # Development compose file
├── .env.example                 # Environment template
├── .gitignore
└── README.md
```

## Key Concepts

### Single Source of Truth (SSOT)

- **Gramps Web** is the authoritative database for all genealogical data
- **MariaDB cache** is subordinate - used for staging and performance only
- All genealogical queries read from Gramps Web
- Cache stores extraction results awaiting validation
- Never modify Gramps Web without validation against SSOT

### Confidence Scoring

- **High (≥0.85)**: Auto-store if non-conflicting
- **Medium (0.60-0.84)**: Flag for manual review
- **Low (<0.60)**: Reject or flag for review

### Conflict Detection

The system detects conflicts by comparing extracted data with Gramps Web:
- Different birth/death dates
- Contradictory relationships
- Gender mismatches
- Conflicting spouse information

All conflicts require manual review before modifying Gramps Web.

### Caching Strategy

Three-layer cache minimizes costs:
1. **Obituary content cache**: Avoid re-fetching HTML
2. **LLM response cache**: Avoid duplicate API calls
3. **Entity cache**: Store structured extraction results

Target cache hit rate: ≥70%

## Development Guidelines

### Code Quality

- **Type hints**: All Python functions must have type hints
- **Docstrings**: All functions/classes must have docstrings
- **Error handling**: Comprehensive try/except with specific exceptions
- **Logging**: Structured JSON logs to stdout/stderr
- **Testing**: Unit tests for all business logic

### Git Workflow

- **main**: Production-ready code
- **develop**: Integration branch
- **feature/\***: Feature branches

Commit message format:
```
feat: Add fuzzy name matching
fix: Handle null dates in entity extraction
docs: Update API documentation
test: Add unit tests for matcher
refactor: Simplify LLM prompt logic
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_matcher.py

# Run with verbose output
pytest -v
```

## Troubleshooting

### Containers won't start

```bash
# Check container logs
podman logs genealogy-backend
podman logs genealogy-mariadb

# Restart all containers
podman-compose -f podman-compose.dev.yml restart

# Rebuild containers
podman-compose -f podman-compose.dev.yml up -d --build
```

### Database connection errors

```bash
# Verify MariaDB is running
podman exec -it genealogy-mariadb mysql -u genealogy -p

# Check connection string in .env file
# Verify MARIADB_HOST=mariadb (not localhost)
```

### Gramps Web API errors

```bash
# Verify API token is valid
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:5555/api/metadata

# Regenerate token in Gramps Web UI if needed
```

### LLM extraction fails

```bash
# Verify OpenAI API key is valid
# Check OpenAI account has credits
# Review logs for specific error: podman logs genealogy-backend
```

## Cost Monitoring

Track LLM API costs at http://localhost:3000/dashboard

- Daily/monthly cost trends
- Cost per obituary average
- Token usage breakdown
- Cache hit rate (cost savings)

Target: <$0.10 per obituary

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'feat: Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

## License

GNU General Public License v3.0 - See LICENSE file for details

## Roadmap

### Phase 1 (Current)
- ✅ Obituary processing
- ✅ LLM extraction
- ✅ Gramps Web integration
- ✅ Manual review UI

### Phase 2 (Future)
- TruePeopleSearch integration
- Enhanced matching algorithms
- Batch processing

### Phase 3 (Future)
- 23andMe DNA integration
- Census record extraction
- Newspaper archives

### Phase 4 (Future)
- Production Kubernetes deployment
- Multi-user support
- Authentication/authorization
- Collaborative features

## Support

- **Documentation**: See `/docs` folder
- **API Docs**: http://localhost:8000/docs
- **Issues**: GitHub Issues
- **PRD**: See `genealogy-prd.md` for complete requirements

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Uses [Gramps Web](https://www.grampsweb.org/) for GEDCOM-compliant storage
- Powered by [OpenAI GPT-4](https://openai.com/)
- Containerized with [Podman](https://podman.io/)

---

**Status**: Phase 1 Development  
**Version**: 1.0.0-alpha  
**Last Updated**: December 2024
