-- ============================================================================
-- FACT-BASED EXTRACTION SCHEMA
-- Replaces entity-based approach (extracted_persons, extracted_relationships)
-- ============================================================================

-- Disable foreign key checks to allow dropping tables with dependencies
SET FOREIGN_KEY_CHECKS = 0;

-- Drop old views first (they depend on the tables)
DROP VIEW IF EXISTS entities_requiring_review;
DROP VIEW IF EXISTS obituaries_pending_processing;

-- Drop old entity tables if they exist (from previous approach)
DROP TABLE IF EXISTS extracted_relationships;
DROP TABLE IF EXISTS extracted_persons;

-- Re-enable foreign key checks
SET FOREIGN_KEY_CHECKS = 1;

-- Update gramps_record_mapping to remove references to old tables
ALTER TABLE gramps_record_mapping
    DROP FOREIGN KEY IF EXISTS gramps_record_mapping_ibfk_2,
    DROP FOREIGN KEY IF EXISTS gramps_record_mapping_ibfk_3;

ALTER TABLE gramps_record_mapping
    DROP COLUMN IF EXISTS extracted_person_id,
    DROP COLUMN IF EXISTS extracted_relationship_id;

-- Add new column for fact reference
ALTER TABLE gramps_record_mapping
    ADD COLUMN extracted_fact_id INT AFTER gramps_record_id;

-- Main fact table: stores individual claims from obituaries
CREATE TABLE extracted_facts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    obituary_cache_id INT NOT NULL,
    llm_cache_id INT,

    -- The claim itself
    fact_type ENUM(
        'person_name',
        'person_death_date',
        'person_death_age',
        'person_birth_date',
        'person_gender',
        'maiden_name',
        'relationship',
        'marriage',
        'location_birth',
        'location_death',
        'location_residence',
        'survived_by',
        'preceded_in_death'
    ) NOT NULL,

    -- Subject of the fact (who/what this is about)
    subject_name VARCHAR(255) NOT NULL,
    subject_role ENUM(
        'deceased_primary',
        'spouse',
        'child',
        'parent',
        'sibling',
        'grandchild',
        'grandparent',
        'in_law',
        'other'
    ) DEFAULT 'other',

    -- The fact value/object
    fact_value TEXT NOT NULL,

    -- For relationships: the other person
    related_name VARCHAR(255),
    relationship_type VARCHAR(100),  -- 'spouse', 'parent', 'child', 'son', 'daughter', etc.

    -- Context from obituary
    extracted_context TEXT,
    source_sentence TEXT,  -- Exact sentence from obituary

    -- Inference tracking
    is_inferred BOOLEAN DEFAULT FALSE,
    inference_basis TEXT,

    -- Confidence (0.00 to 1.00)
    confidence_score DECIMAL(3,2) NOT NULL,

    -- Resolution to Gramps Web (SSOT)
    gramps_person_id VARCHAR(50),
    gramps_family_id VARCHAR(50),
    gramps_event_id VARCHAR(50),
    resolution_status ENUM('unresolved', 'resolved', 'conflicting', 'rejected')
                      DEFAULT 'unresolved',
    resolution_notes TEXT,
    resolved_timestamp TIMESTAMP NULL,

    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (obituary_cache_id) REFERENCES obituary_cache(id) ON DELETE CASCADE,
    FOREIGN KEY (llm_cache_id) REFERENCES llm_cache(id) ON DELETE SET NULL,

    INDEX idx_subject_name (subject_name),
    INDEX idx_fact_type (fact_type),
    INDEX idx_confidence (confidence_score),
    INDEX idx_resolution (resolution_status),
    INDEX idx_gramps_person (gramps_person_id),
    INDEX idx_obituary (obituary_cache_id),
    INDEX idx_subject_role (subject_role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add foreign key to gramps_record_mapping
ALTER TABLE gramps_record_mapping
    ADD CONSTRAINT fk_gramps_mapping_fact
    FOREIGN KEY (extracted_fact_id) REFERENCES extracted_facts(id) ON DELETE SET NULL;

-- ============================================================================
-- VIEWS FOR FACT-BASED QUERIES
-- ============================================================================

-- View: Group facts by subject for easy analysis
CREATE VIEW fact_clusters AS
SELECT
    subject_name,
    obituary_cache_id,
    COUNT(*) as fact_count,
    AVG(confidence_score) as avg_confidence,
    MAX(CASE WHEN fact_type = 'person_death_date' THEN fact_value END) as death_date,
    MAX(CASE WHEN fact_type = 'maiden_name' THEN fact_value END) as maiden_name,
    MAX(gramps_person_id) as gramps_person_id,
    GROUP_CONCAT(DISTINCT subject_role) as roles
FROM extracted_facts
GROUP BY subject_name, obituary_cache_id;

-- View: Unresolved facts requiring review
CREATE VIEW facts_requiring_review AS
SELECT
    ef.*,
    oc.url as source_url,
    oc.fetch_timestamp
FROM extracted_facts ef
JOIN obituary_cache oc ON ef.obituary_cache_id = oc.id
WHERE ef.resolution_status IN ('unresolved', 'conflicting')
ORDER BY ef.confidence_score ASC, ef.created_timestamp DESC;

-- View: Potential duplicates (same subject name across obituaries)
CREATE VIEW potential_same_person AS
SELECT
    ef1.subject_name,
    ef1.obituary_cache_id as obituary1_id,
    ef2.obituary_cache_id as obituary2_id,
    ef1.gramps_person_id as gramps_id_1,
    ef2.gramps_person_id as gramps_id_2,
    COUNT(*) as shared_fact_types
FROM extracted_facts ef1
JOIN extracted_facts ef2
    ON ef1.subject_name = ef2.subject_name
    AND ef1.obituary_cache_id < ef2.obituary_cache_id
    AND ef1.fact_type = ef2.fact_type
WHERE ef1.subject_role = 'deceased_primary'
   OR ef2.subject_role = 'deceased_primary'
GROUP BY ef1.subject_name, ef1.obituary_cache_id, ef2.obituary_cache_id,
         ef1.gramps_person_id, ef2.gramps_person_id
HAVING shared_fact_types >= 2;

-- Recreate obituaries_pending_processing view (updated for facts)
CREATE VIEW obituaries_pending_processing AS
SELECT
    oc.id,
    oc.url,
    oc.fetch_timestamp,
    oc.processing_status,
    COUNT(ef.id) as extracted_facts_count
FROM obituary_cache oc
LEFT JOIN extracted_facts ef ON oc.id = ef.obituary_cache_id
WHERE oc.processing_status IN ('pending', 'processing')
GROUP BY oc.id, oc.url, oc.fetch_timestamp, oc.processing_status;
