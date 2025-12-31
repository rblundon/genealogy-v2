-- ============================================================================
-- RESOLUTION WORKFLOW SCHEMA
-- Tracks person matching and fact approval for committing to Gramps Web
-- ============================================================================

-- Person Resolution: maps extracted names to Gramps handles
CREATE TABLE IF NOT EXISTS person_resolution (
    id INT AUTO_INCREMENT PRIMARY KEY,
    obituary_cache_id INT NOT NULL,

    -- The extracted name to resolve
    extracted_name VARCHAR(255) NOT NULL,
    subject_role VARCHAR(50),  -- deceased_primary, spouse, child, etc.

    -- Match results
    gramps_handle VARCHAR(50),  -- NULL = create new person
    gramps_id VARCHAR(50),      -- Gramps display ID (I0001, etc.)
    match_score DECIMAL(3,2),   -- Fuzzy match score (0.00-1.00)
    match_method ENUM('exact', 'fuzzy', 'manual', 'created') DEFAULT 'fuzzy',

    -- Resolution status
    status ENUM('pending', 'matched', 'create_new', 'rejected', 'committed')
           DEFAULT 'pending',

    -- User modifications
    user_modified BOOLEAN DEFAULT FALSE,
    modified_first_name VARCHAR(255),
    modified_surname VARCHAR(255),
    modified_gender INT,  -- 0=female, 1=male, 2=unknown

    -- Tracking
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_timestamp TIMESTAMP NULL,
    committed_timestamp TIMESTAMP NULL,

    FOREIGN KEY (obituary_cache_id) REFERENCES obituary_cache(id) ON DELETE CASCADE,

    INDEX idx_obituary (obituary_cache_id),
    INDEX idx_extracted_name (extracted_name),
    INDEX idx_gramps_handle (gramps_handle),
    INDEX idx_status (status),
    UNIQUE KEY unique_person_per_obituary (obituary_cache_id, extracted_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Fact Resolution: tracks approval status for each fact
CREATE TABLE IF NOT EXISTS fact_resolution (
    id INT AUTO_INCREMENT PRIMARY KEY,
    extracted_fact_id INT NOT NULL,
    person_resolution_id INT,  -- Links to person resolution for subject
    related_person_resolution_id INT,  -- Links to person resolution for related_name

    -- What action to take
    action ENUM('add', 'update', 'skip', 'reject') DEFAULT 'add',

    -- Approval status
    status ENUM('pending', 'approved', 'rejected', 'committed') DEFAULT 'pending',

    -- Comparison with Gramps (populated during resolution)
    gramps_has_value BOOLEAN DEFAULT FALSE,
    gramps_current_value TEXT,  -- Current value in Gramps (if any)
    is_conflict BOOLEAN DEFAULT FALSE,  -- Extracted value differs from Gramps

    -- User modifications
    user_modified BOOLEAN DEFAULT FALSE,
    modified_value TEXT,  -- User-edited value

    -- Tracking
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_timestamp TIMESTAMP NULL,
    committed_timestamp TIMESTAMP NULL,

    FOREIGN KEY (extracted_fact_id) REFERENCES extracted_facts(id) ON DELETE CASCADE,
    FOREIGN KEY (person_resolution_id) REFERENCES person_resolution(id) ON DELETE SET NULL,
    FOREIGN KEY (related_person_resolution_id) REFERENCES person_resolution(id) ON DELETE SET NULL,

    INDEX idx_fact (extracted_fact_id),
    INDEX idx_person_resolution (person_resolution_id),
    INDEX idx_status (status),
    INDEX idx_action (action),
    UNIQUE KEY unique_fact_resolution (extracted_fact_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Commit batches: tracks commits to Gramps
CREATE TABLE IF NOT EXISTS gramps_commit_batch (
    id INT AUTO_INCREMENT PRIMARY KEY,
    obituary_cache_id INT NOT NULL,

    -- Summary
    persons_created INT DEFAULT 0,
    persons_updated INT DEFAULT 0,
    families_created INT DEFAULT 0,
    events_created INT DEFAULT 0,
    facts_committed INT DEFAULT 0,

    -- Status
    status ENUM('pending', 'in_progress', 'completed', 'failed', 'rolled_back')
           DEFAULT 'pending',
    error_message TEXT,

    -- Tracking
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_timestamp TIMESTAMP NULL,
    completed_timestamp TIMESTAMP NULL,

    FOREIGN KEY (obituary_cache_id) REFERENCES obituary_cache(id) ON DELETE CASCADE,

    INDEX idx_obituary (obituary_cache_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- View: Resolution summary per obituary
CREATE OR REPLACE VIEW resolution_summary AS
SELECT
    oc.id as obituary_id,
    oc.url,
    COUNT(DISTINCT pr.id) as total_persons,
    SUM(CASE WHEN pr.status = 'pending' THEN 1 ELSE 0 END) as persons_pending,
    SUM(CASE WHEN pr.status = 'matched' THEN 1 ELSE 0 END) as persons_matched,
    SUM(CASE WHEN pr.status = 'create_new' THEN 1 ELSE 0 END) as persons_new,
    SUM(CASE WHEN pr.status = 'committed' THEN 1 ELSE 0 END) as persons_committed,
    COUNT(DISTINCT fr.id) as total_facts,
    SUM(CASE WHEN fr.status = 'pending' THEN 1 ELSE 0 END) as facts_pending,
    SUM(CASE WHEN fr.status = 'approved' THEN 1 ELSE 0 END) as facts_approved,
    SUM(CASE WHEN fr.status = 'committed' THEN 1 ELSE 0 END) as facts_committed,
    SUM(CASE WHEN fr.is_conflict = TRUE THEN 1 ELSE 0 END) as facts_conflicting
FROM obituary_cache oc
LEFT JOIN person_resolution pr ON oc.id = pr.obituary_cache_id
LEFT JOIN extracted_facts ef ON oc.id = ef.obituary_cache_id
LEFT JOIN fact_resolution fr ON ef.id = fr.extracted_fact_id
GROUP BY oc.id, oc.url;
