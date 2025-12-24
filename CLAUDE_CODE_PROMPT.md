# Claude Code Prompt - Phase 1.1 Foundation Implementation

## Project Context

I'm building a genealogy research tool that automates extraction of family relationship data from obituaries using LLM technology. The system integrates with Gramps Web (GEDCOM-compliant genealogy software) as the Single Source of Truth (SSOT).

## Development Methodology

We're following **BMAD (Best Matching Artifact Design) + Spec Anchors**:
- **Spec Anchors**: Critical components with specifications written BEFORE implementation
- **BMAD Artifacts**: Everything else built iteratively with rapid feedback
- **Key Principle**: "Spec what you can't afford to get wrong. Build what you need to learn."

## Required Reading

**Before starting, please read these files in the repository:**

1. **docs/DEVELOPMENT_METHODOLOGY.md** - Our development approach
2. **SETUP_GUIDE.md** - Phase 1.1 objectives and checklist
3. **specs/ssot-validation.md** - ⚓ Data integrity rules (READ BEFORE implementing Gramps integration)
4. **specs/caching-strategy.md** - ⚓ Three-layer cache architecture
5. **specs/confidence-scoring.md** - ⚓ Confidence scoring algorithm
6. **docs/genealogy-prd.md** - Full product requirements (reference as needed)

## Current State

**Already in repository:**
- `models.py` - SQLAlchemy models (needs to be organized into backend/ structure)
- `genealogy_cache_schema.sql` - MariaDB schema
- All documentation and specs

**Platform:**
- Ubuntu VM with Podman (not Docker)
- External Gramps Web instance (already running, not containerized)
- Development environment with bind mounts for hot reload

## Phase 1.1 Foundation - Your Tasks

### Task 1: Create Development Container Infrastructure

**Files to create:**

1. **`podman-compose.dev.yml`** - Development orchestration
   - MariaDB service (mariadb:10.11)
   - Backend service (FastAPI with hot reload)
   - Frontend service (React + Vite) - basic structure
   - Network: genealogy-net-dev
   - Volumes: Use bind mounts for source code (development mode)
   - Health checks for all services
   - Expose ports: 3306 (MariaDB), 8000 (Backend), 5173 (Frontend)
   - **IMPORTANT**: No Gramps Web container (it's external)

2. **`env.example`** - Environment variables template
   - MARIADB_ROOT_PASSWORD
   - MARIADB_DATABASE=genealogy_cache
   - MARIADB_USER=genealogy
   - MARIADB_PASSWORD
   - GRAMPS_WEB_URL (external instance, e.g., http://192.168.1.100:5000)
   - GRAMPS_API_TOKEN
   - OPENAI_API_KEY
   - VITE_API_URL=http://localhost:8000
   - LOG_LEVEL=DEBUG
   - ENVIRONMENT=development

3. **`.gitignore`** - Add:
   - .env
   - __pycache__/
   - *.pyc
   - venv/
   - node_modules/
   - .pytest_cache/
   - *.log
   - .vscode/ (optional)

### Task 2: Organize Backend Structure

**Directory structure to create:**
```
backend/
├── Dockerfile.dev          # Python 3.11-slim with hot reload
├── requirements.txt        # Python dependencies
├── main.py                 # FastAPI application
├── models/
│   ├── __init__.py
│   ├── database.py         # Database connection & session
│   └── cache_models.py     # All ORM models
├── api/
│   ├── __init__.py
│   └── endpoints/
│       └── __init__.py
├── services/
│   ├── __init__.py
│   └── (will be created in Phase 1.2)
└── utils/
    ├── __init__.py
    ├── config.py           # Config helper class
    └── hash_utils.py       # Cache key generation
```

**Actions:**
1. Move `models.py` content into `backend/models/` (split into database.py and cache_models.py)
2. Move `genealogy_cache_schema.sql` to `database/schema.sql`
3. Create all directory structure and `__init__.py` files

### Task 3: Create Backend Files

#### 3.1 `backend/Dockerfile.dev`
```dockerfile
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl gcc default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

#### 3.2 `backend/requirements.txt`
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
sqlalchemy==2.0.23
pymysql==1.1.0
cryptography==41.0.7
alembic==1.13.0
python-dotenv==1.0.0
pydantic==2.5.0
pydantic-settings==2.1.0
openai==1.3.7
requests==2.31.0
beautifulsoup4==4.12.2
lxml==4.9.3
httpx==0.25.2
python-dateutil==2.8.2
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
```

#### 3.3 `backend/main.py`
Create FastAPI application with:
- CORS middleware (allow localhost:5173 for Vite dev server)
- Health check endpoint: `GET /health`
- Readiness check endpoint: `GET /ready` (tests database connection)
- Root endpoint: `GET /` (API information)
- Structured JSON logging to stdout
- Database initialization on startup (Base.metadata.create_all)
- Import models from models/__init__.py

#### 3.4 `backend/utils/config.py`
Implement the Config helper class from the specs:
- Static methods: get(), set()
- Typed value conversion (integer, float, boolean, json)
- Convenience methods: get_confidence_threshold_auto_store(), get_confidence_threshold_review(), etc.
- Reference: See caching-strategy.md for configuration keys

#### 3.5 `backend/utils/hash_utils.py`
Implement hashing utilities from caching-strategy.md:
```python
import hashlib

def hash_url(url: str) -> str:
    """Generate SHA-256 hash of a URL"""
    # Normalize URL (lowercase, remove trailing slash, sort query params)
    # Return hex digest

def hash_content(content: str) -> str:
    """Generate SHA-256 hash of content"""
    # Return hex digest

def hash_prompt(prompt: str) -> str:
    """Generate SHA-256 hash of an LLM prompt"""
    # Return hex digest
```

### Task 4: Create Basic Frontend Structure

#### 4.1 `frontend/Dockerfile.dev`
```dockerfile
FROM node:20-alpine
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm install

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
```

#### 4.2 `frontend/package.json`
```json
{
  "name": "genealogy-frontend",
  "version": "1.0.0-dev",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.0.8"
  }
}
```

#### 4.3 `frontend/vite.config.js`
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173
  }
})
```

#### 4.4 `frontend/index.html`
Basic HTML template with `<div id="root"></div>`

#### 4.5 `frontend/src/main.jsx`
React entry point

#### 4.6 `frontend/src/App.jsx`
Simple React app with:
- Title: "Genealogy Research Tool"
- Placeholder for obituary URL input
- "Coming soon" message

### Task 5: Testing & Validation

After creating all files:

1. **Create `.env` file**:
   ```bash
   cp env.example .env
   # Note: User will need to fill in actual credentials
   ```

2. **Test container build**:
   ```bash
   podman-compose -f podman-compose.dev.yml build
   ```

3. **Start containers**:
   ```bash
   podman-compose -f podman-compose.dev.yml up -d
   ```

4. **Verify health checks**:
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status": "healthy", ...}
   
   curl http://localhost:8000/ready
   # Should return: {"status": "ready", "database": "connected", ...}
   
   curl http://localhost:5173
   # Should return: Frontend HTML
   ```

5. **Test database connection**:
   ```bash
   podman exec genealogy-mariadb-dev mysql -u genealogy -pPASSWORD -e "SHOW TABLES;" genealogy_cache
   # Should show all tables from schema.sql
   ```

6. **Check logs**:
   ```bash
   podman-compose -f podman-compose.dev.yml logs backend
   # Should show startup messages and health check logs
   ```

## Phase 1.1 Exit Criteria

Before moving to Phase 1.2, verify:
- [ ] All containers start successfully
- [ ] Backend health check returns 200 OK
- [ ] Backend readiness check confirms database connection
- [ ] Database schema is initialized (all tables exist)
- [ ] Frontend loads in browser
- [ ] Can insert/query test data via backend
- [ ] Logs are structured JSON format
- [ ] Hot reload works (change backend/main.py, see auto-reload)

## Important Notes

### Security (from requirements)
- Input validation will be added in Phase 1.2
- For now, basic URL validation is enough
- No authentication in Phase 1 (single-user system)

### SSOT Architecture
- Gramps Web is external and authoritative
- MariaDB is cache/staging only
- Never write to Gramps Web without validation (Phase 1.3)
- See specs/ssot-validation.md for complete rules

### Caching Strategy
- Three layers: Obituary → LLM → Entities
- See specs/caching-strategy.md for key generation
- Hash functions in utils/hash_utils.py

### Development Flow
- Bind mounts enable hot reload
- Code changes reflect immediately (no rebuild)
- This is BMAD in action: iterate quickly

## Questions to Ask

If anything is unclear:
1. Check the relevant spec anchor first
2. Check SETUP_GUIDE.md for Phase 1.1 details
3. Check DEVELOPMENT_METHODOLOGY.md for approach
4. Ask specific questions about specs if still unclear

## Common Issues

**If MariaDB won't start:**
- Check port 3306 isn't already in use
- Check MARIADB_ROOT_PASSWORD is set in .env

**If backend can't connect to database:**
- Verify MariaDB health check passes first
- Check environment variables match .env file
- Check network: genealogy-net-dev exists

**If frontend won't start:**
- Run `npm install` in frontend/ directory first
- Check port 5173 isn't in use

## Success Looks Like

When Phase 1.1 is complete:
- You can run `podman-compose -f podman-compose.dev.yml up`
- All 3 containers start and stay healthy
- Backend responds to health checks
- Frontend loads in browser
- Database has all tables
- You can start Phase 1.2 (Core Processing)

## Next Phase Preview

Phase 1.2 will add:
- Web scraping (obituary_fetcher.py)
- LLM integration (llm_extractor.py)
- Caching logic (implement from specs)
- First API endpoint (POST /api/obituaries/process)

But that's for later. Focus on Phase 1.1 foundation first.

---

**Ready to begin? Start with Task 1 (container infrastructure) and work through sequentially. Ask questions if any spec is unclear!**
