# Genealogy Research Tool - API Reference

**Version:** 1.0.0
**Last Updated:** 2026-01-03
**Base URL:** http://localhost:8000

---

## Table of Contents
1. [Core Processing APIs](#core-processing-apis)
2. [Cluster Management APIs](#cluster-management-apis)
3. [Gramps Integration APIs](#gramps-integration-apis)
4. [Person Creation APIs](#person-creation-apis)
5. [Citation & Audit APIs](#citation--audit-apis)
6. [Admin & Debug APIs](#admin--debug-apis)
7. [Database Inspection Commands](#database-inspection-commands)
8. [Container Management](#container-management)
9. [Common Workflows](#common-workflows)

---

## Core Processing APIs

### Process an Obituary

**Endpoint:** `POST /api/obituaries/process`

**Description:** Extract facts from obituary text using LLM

**Request:**
```bash
curl -X POST "http://localhost:8000/api/obituaries/process" \
  -H "Content-Type: application/json" \
  -d '{
    "obituary_text": "Your obituary text here...",
    "source_url": "http://example.com/obituary"
  }' | python3 -m json.tool
```

**Response:**
```json
{
  "status": "success",
  "obituary_id": 18,
  "persons_extracted": 12,
  "facts_extracted": 45,
  "processing_time_ms": 2345,
  "llm_cost_usd": 0.08
}
```

---

### List All Obituaries

**Endpoint:** `GET /api/obituaries`

**Description:** Get all processed obituaries

**Request:**
```bash
# Get all obituaries
curl http://localhost:8000/api/obituaries | python3 -m json.tool

# Filter by status
curl "http://localhost:8000/api/obituaries?status=completed" | python3 -m json.tool
```

**Response:**
```json
{
  "count": 3,
  "obituaries": [
    {
      "id": 18,
      "url": "http://test.obituary/terrence",
      "processing_status": "completed",
      "fetch_timestamp": "2026-01-03T20:00:00Z"
    }
  ]
}
```

---

### Get Obituary Facts

**Endpoint:** `GET /api/obituaries/{obituary_id}/facts`

**Description:** Get all facts extracted from a specific obituary

**Request:**
```bash
curl http://localhost:8000/api/obituaries/18/facts | python3 -m json.tool
```

**Response:**
```json
{
  "obituary_id": 18,
  "fact_count": 45,
  "facts": [
    {
      "id": 123,
      "fact_type": "person_name",
      "subject_name": "Terrence E. Kaczmarowski",
      "fact_value": "Terrence E. Kaczmarowski",
      "confidence_score": 1.0
    }
  ]
}
```

---

## Cluster Management APIs

### Generate Clusters

**Endpoint:** `POST /api/clusters/generate`

**Description:** Cluster all extracted facts across obituaries using fuzzy matching

**Request:**
```bash
curl -X POST http://localhost:8000/api/clusters/generate | python3 -m json.tool
```

**Response:**
```json
{
  "status": "success",
  "clusters_created": 12,
  "summary": {
    "total_clusters": 12,
    "multi_source_clusters": 8,
    "clusters_with_variants": 3
  }
}
```

---

### List All Clusters

**Endpoint:** `GET /api/clusters`

**Description:** Get all person clusters with summary information

**Request:**
```bash
# Get all clusters
curl http://localhost:8000/api/clusters | python3 -m json.tool

# Pretty format with jq
curl -s http://localhost:8000/api/clusters | python3 -m json.tool | \
  jq '.clusters[] | {cluster_id, canonical_name, source_count, fact_count, gramps_person_id}'
```

**Response:**
```json
{
  "cluster_count": 12,
  "clusters": [
    {
      "cluster_id": 85,
      "canonical_name": "Patricia L. Blundon",
      "name_variants": ["Patricia Blundon", "Patricia L. Blundon"],
      "source_count": 3,
      "fact_count": 19,
      "confidence": 0.93,
      "cluster_status": "verified",
      "gramps_person_id": "I0085"
    }
  ]
}
```

---

### Get Cluster Details

**Endpoint:** `GET /api/clusters/{cluster_id}`

**Description:** Get detailed information about a specific cluster including all facts grouped by type

**Request:**
```bash
curl http://localhost:8000/api/clusters/85 | python3 -m json.tool

# Save to file for inspection
curl -s http://localhost:8000/api/clusters/85 | python3 -m json.tool > cluster_85.json
```

**Response:**
```json
{
  "cluster_id": 85,
  "canonical_name": "Patricia L. Blundon",
  "name_variants": ["Patricia Blundon", "Patricia L. Blundon"],
  "maiden_names": ["Kaczmarowski"],
  "nicknames": ["Patsy"],
  "source_count": 3,
  "fact_count": 19,
  "confidence": 0.93,
  "gramps_person_id": "I0085",
  "facts_by_type": {
    "person_name": [...],
    "maiden_name": [...],
    "person_death_date": [...],
    "relationship": [...]
  }
}
```

---

### Get Clusters Ready for Creation

**Endpoint:** `GET /api/clusters/ready-for-creation`

**Description:** Get clusters that meet criteria for automatic person creation

**Parameters:**
- `min_confidence` (float, default: 0.80) - Minimum confidence score
- `min_sources` (int, default: 2) - Minimum number of source obituaries

**Request:**
```bash
# Default thresholds (confidence >= 0.80, sources >= 2)
curl http://localhost:8000/api/clusters/ready-for-creation | python3 -m json.tool

# Custom thresholds
curl "http://localhost:8000/api/clusters/ready-for-creation?min_confidence=0.70&min_sources=1" | \
  python3 -m json.tool

# High-confidence only
curl "http://localhost:8000/api/clusters/ready-for-creation?min_confidence=0.90&min_sources=3" | \
  python3 -m json.tool
```

**Response:**
```json
{
  "count": 6,
  "clusters": [
    {
      "cluster_id": 85,
      "canonical_name": "Patricia L. Blundon",
      "confidence": 0.93,
      "source_count": 3,
      "fact_count": 19
    }
  ]
}
```

---

### Cross-Obituary Analysis

**Endpoint:** `GET /api/analysis/cross-obituary`

**Description:** Analyze which people appear in multiple obituaries

**Request:**
```bash
curl http://localhost:8000/api/analysis/cross-obituary | python3 -m json.tool
```

**Response:**
```json
{
  "people_in_multiple_obituaries": [
    {
      "name": "Ryan Blundon",
      "obituary_count": 3,
      "obituaries": [
        "http://test.obituary/terrence",
        "http://test.obituary/maxine",
        "http://test.obituary/patricia"
      ]
    }
  ]
}
```

---

## Gramps Integration APIs

### Check Gramps Health

**Endpoint:** `GET /api/gramps/health`

**Description:** Verify Gramps Web connectivity and authentication

**Request:**
```bash
curl http://localhost:8000/api/gramps/health | python3 -m json.tool
```

**Response:**
```json
{
  "status": "healthy",
  "gramps_web_url": "http://swiss-family-treehouse.local.mk-labs.cloud:80",
  "connected": true,
  "authenticated": true
}
```

---

### Search Gramps People

**Endpoint:** `GET /api/gramps/search`

**Description:** Search for people in Gramps Web by name

**Parameters:**
- `surname` (string) - Search by surname
- `given_name` (string) - Search by given name
- `name` (string) - Free text name search

**Request:**
```bash
# Search by surname
curl "http://localhost:8000/api/gramps/search?surname=Blundon" | python3 -m json.tool

# Search by given name and surname
curl "http://localhost:8000/api/gramps/search?given_name=Patricia&surname=Blundon" | \
  python3 -m json.tool

# Search by name (free text)
curl "http://localhost:8000/api/gramps/search?name=Ryan" | python3 -m json.tool
```

**Response:**
```json
[
  {
    "gramps_id": "I0071",
    "handle": "...",
    "primary_name": {
      "first_name": "Ryan",
      "surname_list": [{"surname": "Blundon"}]
    },
    "birth_ref_index": 0,
    "death_ref_index": -1
  }
]
```

---

### Get Gramps Person Details

**Endpoint:** `GET /api/gramps/person/{person_id}`

**Description:** Get complete person record from Gramps

**Request:**
```bash
# Get person by Gramps ID
curl "http://localhost:8000/api/gramps/person/I0071" | python3 -m json.tool
```

**Response:**
```json
{
  "gramps_id": "I0071",
  "handle": "...",
  "primary_name": {...},
  "alternate_names": [...],
  "event_ref_list": [...],
  "family_list": [...],
  "citation_list": [...]
}
```

---

### Find Gramps Matches for Cluster

**Endpoint:** `GET /api/clusters/{cluster_id}/gramps-matches`

**Description:** Find potential matching people in Gramps for a cluster

**Request:**
```bash
curl http://localhost:8000/api/clusters/85/gramps-matches | python3 -m json.tool
```

**Response:**
```json
{
  "cluster_id": 85,
  "cluster_name": "Patricia L. Blundon",
  "matches_found": 1,
  "matches": [
    {
      "gramps_id": "I0085",
      "gramps_handle": "...",
      "name": "Patricia L. Kaczmarowski",
      "match_confidence": 0.95,
      "match_reasons": ["Name match: fuzzy (0.95)", "Date match: birth"],
      "conflicts": []
    }
  ]
}
```

---

## Person Creation APIs

### Preview Person Creation

**Endpoint:** `GET /api/clusters/{cluster_id}/creation-preview`

**Description:** Preview what would be created in Gramps without making changes

**Request:**
```bash
curl http://localhost:8000/api/clusters/85/creation-preview | python3 -m json.tool
```

**Response:**
```json
{
  "cluster_id": 85,
  "cluster_name": "Patricia L. Blundon",
  "confidence": 0.93,
  "source_count": 3,
  "person_data": {
    "given_name": "Patricia L.",
    "surname": "Kaczmarowski",
    "married_surnames": ["Blundon"],
    "nicknames": ["Patsy"],
    "death_date": "2008-08-07",
    "death_age": "57",
    "birth_date": "1951"
  },
  "relationships": [
    {
      "type": "parent",
      "related_name": "Terrence E. Kaczmarowski",
      "related_in_gramps": "I0062",
      "will_create_link": true
    }
  ],
  "sources": [
    {
      "obituary_id": 18,
      "url": "http://test.obituary/terrence",
      "fetch_date": "2026-01-03T20:00:00Z"
    }
  ]
}
```

---

### Create Person in Gramps

**Endpoint:** `POST /api/clusters/{cluster_id}/create-in-gramps`

**Description:** Create a new person in Gramps Web from cluster data

**Parameters:**
- `create_relationships` (boolean, default: true) - Whether to create family relationships

**Request:**
```bash
# Create person with relationships
curl -X POST "http://localhost:8000/api/clusters/85/create-in-gramps?create_relationships=true" | \
  python3 -m json.tool

# Create person without relationships
curl -X POST "http://localhost:8000/api/clusters/85/create-in-gramps?create_relationships=false" | \
  python3 -m json.tool
```

**Response:**
```json
{
  "status": "success",
  "cluster_id": 85,
  "cluster_name": "Patricia L. Blundon",
  "gramps_person_id": "I0085",
  "gramps_handle": "...",
  "created": true,
  "citations_created": 3,
  "person_data": {
    "given_name": "Patricia L.",
    "surname": "Kaczmarowski",
    "married_surnames": ["Blundon"],
    "death_date": "2008-08-07"
  },
  "relationships_created": [
    {
      "type": "child_of",
      "related_person_id": "I0062",
      "family_id": "F0001"
    }
  ]
}
```

---

### Link Cluster to Existing Gramps Person

**Endpoint:** `POST /api/clusters/{cluster_id}/link-to-gramps`

**Description:** Link cluster to an existing person in Gramps and create citations

**Parameters:**
- `gramps_person_id` (string, required) - Gramps person ID (e.g., "I0071")
- `confidence` (string, default: "high") - Citation confidence level

**Request:**
```bash
curl -X POST "http://localhost:8000/api/clusters/52/link-to-gramps?gramps_person_id=I0071&confidence=high" | \
  python3 -m json.tool
```

**Response:**
```json
{
  "status": "success",
  "cluster_id": 52,
  "cluster_name": "Ryan Blundon",
  "gramps_person_id": "I0071",
  "obituaries_processed": 3,
  "citations_created": 3,
  "citations_skipped": 0,
  "errors": []
}
```

---

### Unlink Cluster from Gramps

**Endpoint:** `DELETE /api/clusters/{cluster_id}/gramps-link`

**Description:** Remove Gramps link from cluster (does not delete from Gramps)

**Request:**
```bash
curl -X DELETE "http://localhost:8000/api/clusters/85/gramps-link" | python3 -m json.tool
```

**Response:**
```json
{
  "status": "success",
  "cluster_id": 85,
  "cluster_name": "Patricia L. Blundon",
  "unlinked": true,
  "gramps_person_id": null
}
```

---

## Citation & Audit APIs

### Get Cluster Citations

**Endpoint:** `GET /api/clusters/{cluster_id}/citations`

**Description:** Get all citations created for a cluster

**Request:**
```bash
curl http://localhost:8000/api/clusters/52/citations | python3 -m json.tool
```

**Response:**
```json
{
  "cluster_id": 52,
  "citation_count": 3,
  "citations": [
    {
      "citation_id": 1,
      "gramps_citation_id": "C0001",
      "gramps_source_id": "S0006",
      "obituary_url": "http://test.obituary/terrence",
      "created": "2026-01-03T21:00:00Z"
    }
  ]
}
```

---

### Get Gramps Audit Trail

**Endpoint:** `GET /api/gramps/audit-trail`

**Description:** Get audit trail of all Gramps operations

**Parameters:**
- `limit` (int, default: 50) - Maximum number of entries to return

**Request:**
```bash
# Get recent audit trail (default: 50 entries)
curl http://localhost:8000/api/gramps/audit-trail | python3 -m json.tool

# Get more entries
curl "http://localhost:8000/api/gramps/audit-trail?limit=100" | python3 -m json.tool

# Format for readability
curl -s http://localhost:8000/api/gramps/audit-trail | python3 -m json.tool | \
  jq '.citations[] | {created, person_name, gramps_person_id, obituary_url}'
```

**Response:**
```json
{
  "total": 18,
  "citations": [
    {
      "id": 1,
      "created": "2026-01-03T21:00:00Z",
      "person_name": "Ryan Blundon",
      "gramps_person_id": "I0071",
      "obituary_name": "Obituary of Terrence E. Kaczmarowski",
      "obituary_url": "http://test.obituary/terrence",
      "gramps_citation_id": "C0001",
      "confidence": "high"
    }
  ]
}
```

---

## Admin & Debug APIs

### Health Check

**Endpoint:** `GET /health`

**Description:** Check API health status

**Request:**
```bash
curl http://localhost:8000/health | python3 -m json.tool
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-03T21:00:00Z"
}
```

---

### Debug Gramps Person

**Endpoint:** `GET /api/gramps/person/{person_id}/debug`

**Description:** Get full Gramps person record with resolved events for debugging

**Request:**
```bash
curl "http://localhost:8000/api/gramps/person/I0085/debug" | python3 -m json.tool
```

**Response:**
```json
{
  "person_id": "I0085",
  "handle": "...",
  "gramps_id": "I0085",
  "primary_name": {...},
  "alternate_names": [...],
  "event_ref_list": [...],
  "events_resolved": [
    {
      "handle": "...",
      "type": "Birth",
      "date": {"year": 1951},
      "place": ""
    },
    {
      "handle": "...",
      "type": "Death",
      "date": {"year": 2008, "month": 8, "day": 7},
      "place": ""
    }
  ],
  "full_record": {...}
}
```

---

### Reset Database

**Endpoint:** `DELETE /api/admin/reset-database`

**Description:** Deletes all cached data (does NOT delete Gramps data)

**Request:**
```bash
curl -X DELETE http://localhost:8000/api/admin/reset-database | python3 -m json.tool
```

**Response:**
```json
{
  "status": "success",
  "deleted": {
    "obituaries": 3,
    "llm_cache_entries": 12,
    "facts": 156,
    "clusters": 12,
    "citations": 18
  }
}
```

---

## Database Inspection Commands

### Direct MariaDB Access
```bash
# Connect to MariaDB
podman exec -it genealogy-mariadb mysql -u genealogy -p genealogy_cache

# Or with password in command (less secure)
podman exec -it genealogy-mariadb mysql -u genealogy -pgenealogypass genealogy_cache
```

---

### Common SQL Queries
```sql
-- Show all clusters
SELECT id, canonical_name, source_count, fact_count, gramps_person_id
FROM person_clusters
ORDER BY source_count DESC;

-- Show clusters with name variants
SELECT id, canonical_name, name_variants
FROM person_clusters
WHERE name_variants IS NOT NULL;

-- Show all relationship facts
SELECT subject_name, relationship_type, related_name, confidence_score
FROM extracted_facts
WHERE fact_type = 'relationship'
ORDER BY subject_name;

-- Show audit trail
SELECT created_timestamp, obituary_name, gramps_person_id
FROM gramps_citations
ORDER BY created_timestamp DESC
LIMIT 20;

-- Show processing status
SELECT processing_status, COUNT(*) as count
FROM obituary_cache
GROUP BY processing_status;

-- Show LLM costs
SELECT
    llm_provider,
    model_version,
    COUNT(*) as request_count,
    SUM(cost_usd) as total_cost,
    SUM(token_usage_total) as total_tokens
FROM llm_cache
GROUP BY llm_provider, model_version;

-- Show clusters linked to Gramps
SELECT
    pc.canonical_name,
    pc.gramps_person_id,
    pc.source_count,
    COUNT(gc.id) as citation_count
FROM person_clusters pc
LEFT JOIN gramps_citations gc ON pc.id = gc.person_cluster_id
WHERE pc.gramps_person_id IS NOT NULL
GROUP BY pc.id;
```

---

### Python Database Inspection
```bash
# Run Python commands in backend container
podman exec genealogy-backend python3 -c "
from models import get_db, PersonCluster, ExtractedFact
from sqlalchemy import func

db = next(get_db())

# Count clusters
cluster_count = db.query(PersonCluster).count()
print(f'Total clusters: {cluster_count}')

# Show clusters with Gramps links
gramps_linked = db.query(PersonCluster).filter(
    PersonCluster.gramps_person_id.isnot(None)
).all()

print(f'\nClusters in Gramps: {len(gramps_linked)}')
for cluster in gramps_linked:
    print(f'  {cluster.canonical_name} -> {cluster.gramps_person_id}')

# Count facts by type
fact_counts = db.query(
    ExtractedFact.fact_type,
    func.count(ExtractedFact.id)
).group_by(ExtractedFact.fact_type).all()

print('\nFacts by type:')
for fact_type, count in fact_counts:
    print(f'  {fact_type}: {count}')
"
```

---

## Container Management

### View Logs
```bash
# Backend logs (all)
podman logs genealogy-backend

# Backend logs (last 100 lines)
podman logs genealogy-backend --tail=100

# Backend logs (follow/live)
podman logs genealogy-backend -f

# Search logs for errors
podman logs genealogy-backend | grep -i "error\|exception\|failed"

# Search logs for debug output
podman logs genealogy-backend | grep "DEBUG:"

# MariaDB logs
podman logs genealogy-mariadb --tail=50
```

---

### Container Status
```bash
# List all containers
podman ps -a

# Check container health
podman inspect genealogy-backend | jq '.[0].State.Health'
podman inspect genealogy-mariadb | jq '.[0].State.Health'

# Restart containers
podman restart genealogy-backend
podman restart genealogy-mariadb

# Stop all containers
podman-compose down

# Start all containers
podman-compose up -d
```

---

## Common Workflows

### Complete Processing Workflow
```bash
# 1. Process obituary
curl -X POST "http://localhost:8000/api/obituaries/process" \
  -H "Content-Type: application/json" \
  -d '{"obituary_text": "...", "source_url": "..."}' | python3 -m json.tool

# 2. Generate clusters
curl -X POST http://localhost:8000/api/clusters/generate | python3 -m json.tool

# 3. View ready for creation
curl http://localhost:8000/api/clusters/ready-for-creation | python3 -m json.tool

# 4. Preview specific person
curl http://localhost:8000/api/clusters/85/creation-preview | python3 -m json.tool

# 5. Create person
curl -X POST "http://localhost:8000/api/clusters/85/create-in-gramps?create_relationships=true" | \
  python3 -m json.tool

# 6. Verify in Gramps
curl http://localhost:8000/api/gramps/audit-trail | python3 -m json.tool
```

---

### Build Complete Family Tree
```bash
#!/bin/bash
# Script to create complete family tree in proper order

# Get cluster IDs
CLUSTERS=$(curl -s http://localhost:8000/api/clusters | python3 -m json.tool)

# Extract specific cluster IDs
TERRENCE_ID=$(echo "$CLUSTERS" | jq '.clusters[] | select(.canonical_name | contains("Terrence")) | .cluster_id')
MAXINE_ID=$(echo "$CLUSTERS" | jq '.clusters[] | select(.canonical_name | contains("Maxine")) | .cluster_id')
PATRICIA_ID=$(echo "$CLUSTERS" | jq '.clusters[] | select(.canonical_name | contains("Patricia")) | .cluster_id')

echo "Creating Generation 1: Grandparents..."
curl -X POST "http://localhost:8000/api/clusters/$TERRENCE_ID/create-in-gramps?create_relationships=true" | \
  python3 -m json.tool
sleep 1

curl -X POST "http://localhost:8000/api/clusters/$MAXINE_ID/create-in-gramps?create_relationships=true" | \
  python3 -m json.tool
sleep 1

echo "Creating Generation 2: Parents..."
curl -X POST "http://localhost:8000/api/clusters/$PATRICIA_ID/create-in-gramps?create_relationships=true" | \
  python3 -m json.tool

echo "Complete! Check Gramps Web to see your family tree."
```

---

### Debug Relationship Creation
```bash
# 1. Check cluster has relationship facts
curl -s http://localhost:8000/api/clusters/85 | python3 -m json.tool | \
  jq '.facts_by_type.relationship'

# 2. Check related people exist in Gramps
curl "http://localhost:8000/api/gramps/search?surname=Kaczmarowski" | python3 -m json.tool

# 3. Look at backend logs for debug output
podman logs genealogy-backend --tail=200 | grep -A 50 "DEBUG: _create_relationships"

# 4. Check what relationships were created
curl http://localhost:8000/api/gramps/audit-trail | python3 -m json.tool | \
  jq '.citations[] | select(.person_name | contains("Patricia"))'
```

---

### Clean Slate Reset
```bash
# WARNING: This destroys all data

# 1. Stop containers
podman-compose down

# 2. Remove volumes
podman volume rm genealogy-mariadb-data

# 3. Start fresh
podman-compose up -d

# 4. Wait for health
sleep 10

# 5. Verify health
curl http://localhost:8000/health | python3 -m json.tool
```

---

## Quick Reference

### Most Common Commands
```bash
# Process -> Cluster -> Create workflow
curl -X POST "http://localhost:8000/api/obituaries/process" \
  -H "Content-Type: application/json" \
  -d '{"obituary_text":"...","source_url":"..."}' | python3 -m json.tool

curl -X POST http://localhost:8000/api/clusters/generate | python3 -m json.tool

curl http://localhost:8000/api/clusters/ready-for-creation | python3 -m json.tool

curl -X POST "http://localhost:8000/api/clusters/{ID}/create-in-gramps?create_relationships=true" | \
  python3 -m json.tool

# View results
curl http://localhost:8000/api/gramps/audit-trail | python3 -m json.tool

curl -s http://localhost:8000/api/clusters | python3 -m json.tool | \
  jq '.clusters[] | {cluster_id, canonical_name, source_count, gramps_person_id}'

# Debug
podman logs genealogy-backend --tail=100 | grep "DEBUG:\|ERROR:"
curl http://localhost:8000/api/gramps/health | python3 -m json.tool
```

---

## Error Codes

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | Success | Request completed successfully |
| 400 | Bad Request | Invalid input data, missing required fields |
| 404 | Not Found | Cluster/obituary/person not found |
| 500 | Server Error | Database error, Gramps API error, LLM API error |

### Common Error Messages

**"Cluster not found"**
- Cluster ID doesn't exist
- Check: `curl http://localhost:8000/api/clusters | jq '.clusters[] | .cluster_id'`

**"Person already linked to Gramps"**
- Trying to create person that already has `gramps_person_id`
- Unlink first: `curl -X DELETE http://localhost:8000/api/clusters/{id}/gramps-link`

**"Failed to add citation to person: 400 Bad Request"**
- Known issue with Gramps API
- Citations are created but not linked to people
- **Workaround:** Temporarily disabled

**"Gramps Web unreachable"**
- Gramps container not running or not healthy
- Check: `podman ps | grep grampsweb`
- Check: `curl http://localhost:8000/api/gramps/health`

---

## Troubleshooting

### Backend won't start
```bash
# Check logs
podman logs genealogy-backend --tail=100

# Check if MariaDB is healthy
podman ps | grep mariadb
podman inspect genealogy-mariadb | jq '.[0].State.Health'

# Restart
podman restart genealogy-backend
```

### Database connection errors
```bash
# Check MariaDB is running
podman exec -it genealogy-mariadb mysql -u genealogy -p -e "SELECT 1;"

# Check environment variables
podman exec genealogy-backend env | grep MARIADB

# Restart MariaDB
podman restart genealogy-mariadb
sleep 5
podman restart genealogy-backend
```

### Gramps integration not working
```bash
# Test Gramps health
curl http://localhost:8000/api/gramps/health | python3 -m json.tool

# Check Gramps Web directly
curl http://swiss-family-treehouse.local.mk-labs.cloud/api/metadata

# Check API token
podman exec genealogy-backend env | grep GRAMPS_API_TOKEN
```

---

**Last Updated:** 2026-01-03
**Version:** 1.0.0
