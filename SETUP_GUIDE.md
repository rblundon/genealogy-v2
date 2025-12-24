# Phase 1.1 Foundation - Setup Guide

## ✅ What We've Created

### Container Infrastructure
- ✅ `podman-compose.dev.yml` - Development container orchestration for Ubuntu VM
- ✅ `backend/Dockerfile.dev` - Backend container with hot reload
- ✅ `backend/requirements.txt` - Python dependencies
- ✅ `env.example.updated` - Environment variables template (external Gramps Web)

### Backend Structure
- ✅ `backend/main.py` - FastAPI application with health checks
- ✅ `backend/models/database.py` - SQLAlchemy database setup
- ✅ `backend/models/cache_models.py` - All ORM models
- ✅ `backend/models/__init__.py` - Package initialization
- ✅ `database/schema.sql` - MariaDB schema with indexes

### Directory Structure
```
genealogy-research-tool/
├── backend/
│   ├── Dockerfile.dev
│   ├── requirements.txt
│   ├── main.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   └── cache_models.py
│   ├── api/
│   │   └── endpoints/      (to be created)
│   ├── services/           (to be created)
│   └── utils/              (to be created)
├── frontend/               (to be created)
├── database/
│   └── schema.sql
├── specs/
│   ├── ssot-validation.md
│   ├── caching-strategy.md
│   └── confidence-scoring.md
├── podman-compose.dev.yml
├── env.example.updated
└── README.md
```

## 🚀 Next Steps

### Step 1: Complete Backend Utilities
Need to create:
1. `backend/utils/config.py` - Configuration helper class
2. `backend/utils/hash_utils.py` - Hashing functions for cache keys
3. `backend/utils/__init__.py` - Package initialization

### Step 2: Create Basic Frontend
Need to create:
1. `frontend/Dockerfile.dev` - Frontend container
2. `frontend/package.json` - React + Vite dependencies  
3. `frontend/src/App.jsx` - Main React app
4. `frontend/src/main.jsx` - Entry point
5. `frontend/vite.config.js` - Vite configuration
6. `frontend/index.html` - HTML template

### Step 3: Test Container Setup
1. Copy `.env.example.updated` to `.env`
2. Fill in environment variables (MariaDB password, Gramps Web URL, OpenAI key)
3. Run: `podman-compose -f podman-compose.dev.yml up --build`
4. Verify health checks:
   - Backend: http://localhost:8000/health
   - Frontend: http://localhost:5173
   - Database: `podman exec genealogy-mariadb-dev mysql -u genealogy -p`

### Step 4: Create Initial API Endpoints
Following your program flow:
1. `backend/api/endpoints/obituaries.py`:
   - `POST /api/obituaries/process` - Main processing endpoint
   - `GET /api/obituaries/{id}` - Get obituary details
   - `POST /api/obituaries/{id}/force-refresh` - Force cache invalidation
2. `backend/services/url_validator.py` - Validate obituary URLs (security)
3. `backend/services/obituary_fetcher.py` - Fetch obituary content with caching

## 📋 Additional Requirements Captured

### Security
- ✅ Input validation for obituary URLs (prevent injection)
- ✅ Sanitization of user input
- ✅ Legacy.com as initial source (more can be added later)

### UI/UX
- ✅ Real-time progress feedback:
  - "Validating obituary URL..."
  - "Found person: [name]..."
  - "Determining relationships for [name]..."
  - "Creating Gramps Web entry..."

### Program Flow
```
1. Check if obituary cached
2. Validate obituary URL (security check)
3. Fetch obituary text
4. Determine deceased person's name from obituary
5. Check with Gramps Web if person exists
6. Process obituary (extract entities, determine relationships)
7. Display results to user for review/approval
```

### Cache Invalidation
- ✅ "Force Refresh" button in UI (future enhancement)
- ✅ Will call: `POST /api/obituaries/{id}/force-refresh`

## 🛠️ Commands for Development

### Start Development Environment
```bash
# Create .env file
cp env.example.updated .env
# Edit .env with your actual credentials

# Start all containers
podman-compose -f podman-compose.dev.yml up -d

# View logs
podman-compose -f podman-compose.dev.yml logs -f

# Stop containers
podman-compose -f podman-compose.dev.yml down
```

### Backend Development
```bash
# Install dependencies locally (for IDE)
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
pytest

# Database migrations (when ready)
alembic revision --autogenerate -m "Description"
alembic upgrade head
```

### Frontend Development
```bash
# Install dependencies
cd frontend
npm install

# Run dev server (outside container for faster iteration)
npm run dev
```

## 📊 Phase 1.1 Checklist

### Infrastructure
- [x] podman-compose.dev.yml created
- [x] Backend Dockerfile.dev created
- [x] MariaDB schema in place
- [x] Environment variables template
- [ ] Frontend Dockerfile.dev
- [ ] Frontend package.json

### Backend
- [x] FastAPI main app with health checks
- [x] SQLAlchemy models
- [x] Database connection setup
- [ ] Config utility
- [ ] Hash utility
- [ ] URL validator service
- [ ] Obituary fetcher service

### Testing
- [ ] Backend health check returns 200
- [ ] Database connection works
- [ ] Can insert/query test data
- [ ] Frontend loads successfully

### Documentation
- [x] Setup guide (this document)
- [x] README.md
- [x] Development methodology
- [x] Spec anchors

## 🎯 Ready to Proceed?

The foundation is in place. We can now:

**Option A**: Finish the backend utilities and test the containers
**Option B**: Create the frontend structure simultaneously
**Option C**: Create the first API endpoint (obituary processing) with real functionality

Which would you like to tackle next?
