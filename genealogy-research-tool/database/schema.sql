-- ============================================================================
-- GENEALOGY RESEARCH TOOL - FACT-BASED SCHEMA
-- ============================================================================

-- Stores raw obituary content (performance cache)
CREATE TABLE obituary_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    url VARCHAR(2048) UNIQUE NOT NULL,
    url_hash VARCHAR(64) NOT NULL,
    content_hash VARCHAR(64),
    raw_html MEDIUMTEXT,
    extracted_text TEXT,
    fetch_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    http_status_code INT,
    fetch_error TEXT,
    processing_status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',

    INDEX idx_url_hash (url_hash),
    INDEX idx_processing_status (processing_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Stores LLM API requests and responses (cost optimization)
CREATE TABLE llm_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    obituary_cache_id INT NOT NULL,
    llm_provider VARCHAR(50) NOT NULL DEFAULT 'openai',
    model_version VARCHAR(100) NOT NULL,
    prompt_hash VARCHAR(64) NOT NULL,
    prompt_text TEXT NOT NULL,
    response_text MEDIUMTEXT,
    parsed_json JSON,
    token_usage_prompt INT,
    token_usage_completion INT,
    token_usage_total INT,
    cost_usd DECIMAL(10, 6),
    request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_timestamp TIMESTAMP NULL,
    duration_ms INT,
    api_error TEXT,

    FOREIGN KEY (obituary_cache_id) REFERENCES obituary_cache(id) ON DELETE CASCADE,
    INDEX idx_prompt_hash (prompt_hash),
    INDEX idx_provider_model (llm_provider, model_version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- THE CORE TABLE: Individual factual claims from obituaries
CREATE TABLE extracted_facts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    obituary_cache_id INT NOT NULL,
    llm_cache_id INT,

    -- Type of fact
    fact_type ENUM(
        'person_name',
        'person_nickname',
        'person_death_date',
        'person_death_age',
        'person_birth_date',
        'person_gender',
        'maiden_name',
        'relationship',
        'marriage',
        'marriage_duration',
        'location_birth',
        'location_death',
        'location_residence',
        'survived_by',
        'preceded_in_death'
    ) NOT NULL,

    -- Subject of the fact (who this is about)
    subject_name VARCHAR(255) NOT NULL,
    subject_role ENUM(
        'deceased_primary',
        'spouse',
        'child',
        'parent',
        'sibling',
        'grandchild',
        'grandparent',
        'great_grandchild',
        'in_law',
        'other'
    ) DEFAULT 'other',

    -- The fact value/content
    fact_value TEXT NOT NULL,

    -- For relationships
    related_name VARCHAR(255),
    relationship_type VARCHAR(100),

    -- Evidence and context
    extracted_context TEXT,
    source_sentence TEXT,

    -- Inference tracking
    is_inferred BOOLEAN DEFAULT FALSE,
    inference_basis TEXT,

    -- Confidence score (0.00 to 1.00)
    confidence_score DECIMAL(3, 2) NOT NULL,

    -- Resolution to person clusters and Gramps
    person_cluster_id INT,
    gramps_person_id VARCHAR(50),
    resolution_status ENUM('unresolved', 'clustered', 'resolved', 'conflicting', 'rejected')
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
    INDEX idx_cluster (person_cluster_id),
    INDEX idx_gramps (gramps_person_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Person clusters: Same person across multiple obituaries
CREATE TABLE person_clusters (
    id INT AUTO_INCREMENT PRIMARY KEY,
    canonical_name VARCHAR(255) NOT NULL,
    name_variants JSON NOT NULL,  -- ["Patricia Blundon", "Patsy Blundon", "Patricia L. Blundon"]
    nicknames JSON,               -- ["Patsy"]
    maiden_names JSON,            -- ["Kaczmarowski"]

    -- Gramps SSOT link
    gramps_person_id VARCHAR(50) UNIQUE,

    -- Cluster metadata
    confidence_score DECIMAL(3, 2),
    source_count INT DEFAULT 1,   -- How many obituaries mention this person
    fact_count INT DEFAULT 0,     -- Total facts in cluster

    -- Status
    cluster_status ENUM('unverified', 'verified', 'conflicting', 'resolved') DEFAULT 'unverified',

    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_canonical_name (canonical_name),
    INDEX idx_gramps (gramps_person_id),
    INDEX idx_source_count (source_count)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Configuration settings (tunable parameters)
CREATE TABLE config_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT NOT NULL,
    setting_type ENUM('string', 'integer', 'float', 'boolean', 'json') NOT NULL,
    description TEXT,
    updated_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_setting_key (setting_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert default configuration
INSERT INTO config_settings (setting_key, setting_value, setting_type, description) VALUES
('confidence_threshold_auto_store', '0.85', 'float', 'Minimum confidence for automatic storage without review'),
('confidence_threshold_review', '0.60', 'float', 'Minimum confidence to flag for review'),
('llm_default_provider', 'openai', 'string', 'Default LLM provider'),
('llm_default_model', 'gpt-4-turbo-preview', 'string', 'Default LLM model'),
('fuzzy_match_threshold', '0.85', 'float', 'Minimum fuzzy match score to cluster persons'),
('cache_expiry_days', '365', 'integer', 'Days before cached content is stale');

-- Audit log for all operations
CREATE TABLE audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action_type VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50),
    entity_id INT,
    user_action BOOLEAN DEFAULT FALSE,
    details JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_action_type (action_type),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Facts grouped by subject within obituaries
CREATE VIEW fact_clusters_by_subject AS
SELECT
    subject_name,
    obituary_cache_id,
    COUNT(*) as fact_count,
    AVG(confidence_score) as avg_confidence,
    MAX(CASE WHEN fact_type = 'person_death_date' THEN fact_value END) as death_date,
    MAX(CASE WHEN fact_type = 'person_death_age' THEN fact_value END) as death_age,
    MAX(CASE WHEN fact_type = 'maiden_name' THEN fact_value END) as maiden_name,
    person_cluster_id,
    gramps_person_id
FROM extracted_facts
GROUP BY subject_name, obituary_cache_id, person_cluster_id, gramps_person_id;

-- Unresolved facts requiring attention
CREATE VIEW facts_requiring_review AS
SELECT
    ef.*,
    oc.url as source_url
FROM extracted_facts ef
JOIN obituary_cache oc ON ef.obituary_cache_id = oc.id
WHERE ef.resolution_status IN ('unresolved', 'conflicting')
ORDER BY ef.confidence_score ASC, ef.created_timestamp DESC;

-- Multi-source corroboration view
CREATE VIEW corroborated_facts AS
SELECT
    subject_name,
    fact_type,
    fact_value,
    COUNT(DISTINCT obituary_cache_id) as source_count,
    AVG(confidence_score) as avg_confidence,
    GROUP_CONCAT(DISTINCT obituary_cache_id) as obituary_ids
FROM extracted_facts
GROUP BY subject_name, fact_type, fact_value
HAVING source_count > 1
ORDER BY source_count DESC, avg_confidence DESC;
