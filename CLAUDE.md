# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Genealogy Research Tool - a containerized web application that automates extraction and organization of family relationship data from obituaries using LLM technology. Uses Gramps Web as the Single Source of Truth (SSOT) with MariaDB as a staging/caching layer.

## Development Commands

### Container-based Development (Recommended)
```bash
# Start all services
podman-compose -f podman-compose.dev.yml up -d

# View logs
podman logs genealogy-backend
podman logs genealogy-frontend

# Restart/rebuild
podman-compose -f podman-compose.dev.yml restart
podman-compose -f podman-compose.dev.yml up -d --build

# Stop services
podman-compose -f podman-compose.dev.yml down
```

### Backend (Python/FastAPI)
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run with hot reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Testing
pytest                              # All tests
pytest tests/test_matcher.py        # Single file
pytest --cov=. --cov-report=html    # With coverage

# Code quality
black .                             # Format
flake8 .                            # Lint
mypy .                              # Type check

# Database migrations
alembic revision --autogenerate -m "Description"
alembic upgrade head
alembic downgrade -1
```

### Frontend (React/TypeScript/Vite)
```bash
cd frontend
npm install
npm run dev      # Dev server with hot reload
npm run build    # Production build
npm run lint     # ESLint
npm run preview  # Preview production build
```

### Service URLs
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs (Swagger): http://localhost:8000/docs
- Gramps Web: http://localhost:5555
- MariaDB: localhost:3306

## Architecture

```
Frontend (React) → Backend (FastAPI) → Gramps Web (SSOT)
                        ↓
                   MariaDB (Cache)
                        ↓
                   OpenAI API (GPT-4)
```

**Data Flow:**
1. User submits obituary URL
2. Backend fetches and caches content (SHA-256 hash for deduplication)
3. LLM extracts entities (persons, relationships, dates, locations)
4. Confidence scoring applied (auto-store ≥0.85, review 0.60-0.84, reject <0.60)
5. Fuzzy matching against Gramps Web for duplicates
6. High-confidence results auto-stored; conflicts flagged for manual review
7. Approved changes committed to Gramps Web

**Key Principle:** Gramps Web is authoritative. MariaDB cache is subordinate and used only for staging/caching. Never modify Gramps Web without validation.

## Code Structure

- `backend/models/` - SQLAlchemy ORM models (database.py, cache_models.py)
- `backend/services/` - Business logic (obituary_fetcher, llm_extractor, gramps_connector, matcher)
- `backend/api/endpoints/` - FastAPI routes
- `backend/utils/` - Config and hashing utilities
- `frontend/src/` - React components and pages
- `database/schema.sql` - MariaDB schema (9 tables + views)

## Key Database Tables

- `obituary_cache` - Raw content with URL hash deduplication
- `llm_cache` - LLM responses with prompt hash deduplication (cost optimization)
- `extracted_persons` - Person entities with confidence scores
- `extracted_relationships` - Family relationships
- `config_settings` - Runtime configuration (thresholds, LLM provider)
- `audit_log` - Complete action audit trail

## Environment Variables

Required in `.env`:
- `OPENAI_API_KEY` - For LLM extraction
- `MARIADB_ROOT_PASSWORD`, `MARIADB_PASSWORD` - Database credentials
- `GRAMPS_API_TOKEN` - Gramps Web API access

## Code Standards

- All Python functions require type hints and docstrings
- Structured JSON logging to stdout/stderr (12-factor compliant)
- Commit format: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
