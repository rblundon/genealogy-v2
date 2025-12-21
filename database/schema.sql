-- Genealogy Research Tool - Cache Database Schema
-- Database: genealogy_cache

-- ============================================================================
-- OBITUARY CACHE TABLES
-- ============================================================================

-- Stores raw obituary content and metadata
CREATE TABLE obituary_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    url VARCHAR(2048) UNIQUE NOT NULL,
    url_hash VARCHAR(64) NOT NULL,  -- SHA-256 hash for quick lookups
    content_hash VARCHAR(64),  -- SHA-256 of content for change detection
    raw_html MEDIUMTEXT,  -- Raw HTML content
    extracted_text TEXT,  -- Cleaned text content
    fetch_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    http_status_code INT,
    fetch_error TEXT,  -- Error message if fetch failed
    processing_status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
    INDEX idx_url_hash (url_hash),
    INDEX idx_processing_status (processing_status),
    INDEX idx_fetch_timestamp (fetch_timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- LLM INTERACTION CACHE
-- ============================================================================

-- Stores LLM API requests and responses
CREATE TABLE llm_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    obituary_cache_id INT NOT NULL,
    llm_provider VARCHAR(50) NOT NULL,  -- 'openai', 'claude', 'ollama', etc.
    model_version VARCHAR(100) NOT NULL,  -- 'gpt-4', 'gpt-3.5-turbo', etc.
    prompt_hash VARCHAR(64) NOT NULL,  -- Hash of the prompt for deduplication
    prompt_text TEXT NOT NULL,  -- The actual prompt sent
    response_text MEDIUMTEXT,  -- Raw LLM response
    parsed_json JSON,  -- Parsed structured output from LLM
    token_usage_prompt INT,  -- Tokens used in prompt
    token_usage_completion INT,  -- Tokens used in completion
    token_usage_total INT,  -- Total tokens
    cost_usd DECIMAL(10, 6),  -- Estimated cost in USD
    request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_timestamp TIMESTAMP NULL,
    duration_ms INT,  -- Request duration in milliseconds
    api_error TEXT,  -- Error message if API call failed
    FOREIGN KEY (obituary_cache_id) REFERENCES obituary_cache(id) ON DELETE CASCADE,
    INDEX idx_prompt_hash (prompt_hash),
    INDEX idx_provider_model (llm_provider, model_version),
    INDEX idx_request_timestamp (request_timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- EXTRACTED ENTITIES
-- ============================================================================

-- Stores extracted person entities from obituaries
CREATE TABLE extracted_persons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    obituary_cache_id INT NOT NULL,
    llm_cache_id INT,  -- Link to specific LLM extraction that found this person
    full_name VARCHAR(255) NOT NULL,
    given_names VARCHAR(255),
    surname VARCHAR(255),
    maiden_name VARCHAR(255),
    age INT,
    birth_date DATE,
    birth_date_circa BOOLEAN DEFAULT FALSE,  -- Approximate date
    death_date DATE,
    death_date_circa BOOLEAN DEFAULT FALSE,
    birth_location VARCHAR(500),
    death_location VARCHAR(500),
    residence_location VARCHAR(500),
    gender ENUM('M', 'F', 'U') DEFAULT 'U',  -- Male, Female, Unknown
    is_deceased_primary BOOLEAN DEFAULT FALSE,  -- The main subject of obituary
    confidence_score DECIMAL(3, 2),  -- 0.00 to 1.00
    extraction_notes TEXT,  -- Any notes from extraction process
    gramps_person_id VARCHAR(50),  -- Gramps Web person ID if matched/created
    match_status ENUM('unmatched', 'matched', 'created', 'review_needed') DEFAULT 'unmatched',
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (obituary_cache_id) REFERENCES obituary_cache(id) ON DELETE CASCADE,
    FOREIGN KEY (llm_cache_id) REFERENCES llm_cache(id) ON DELETE SET NULL,
    INDEX idx_full_name (full_name),
    INDEX idx_surname (surname),
    INDEX idx_gramps_id (gramps_person_id),
    INDEX idx_match_status (match_status),
    INDEX idx_confidence (confidence_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Stores extracted relationships between persons
CREATE TABLE extracted_relationships (
    id INT AUTO_INCREMENT PRIMARY KEY,
    obituary_cache_id INT NOT NULL,
    llm_cache_id INT,
    person1_id INT NOT NULL,  -- extracted_persons.id
    person2_id INT NOT NULL,  -- extracted_persons.id
    relationship_type VARCHAR(100) NOT NULL,  -- 'spouse', 'parent', 'child', 'sibling', etc.
    relationship_detail VARCHAR(255),  -- 'mother', 'stepfather', 'half-sister', etc.
    confidence_score DECIMAL(3, 2),  -- 0.00 to 1.00
    extracted_context TEXT,  -- The text snippet that indicated this relationship
    gramps_family_id VARCHAR(50),  -- Gramps Web family ID if created
    match_status ENUM('unmatched', 'matched', 'created', 'review_needed') DEFAULT 'unmatched',
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (obituary_cache_id) REFERENCES obituary_cache(id) ON DELETE CASCADE,
    FOREIGN KEY (llm_cache_id) REFERENCES llm_cache(id) ON DELETE SET NULL,
    FOREIGN KEY (person1_id) REFERENCES extracted_persons(id) ON DELETE CASCADE,
    FOREIGN KEY (person2_id) REFERENCES extracted_persons(id) ON DELETE CASCADE,
    INDEX idx_person1 (person1_id),
    INDEX idx_person2 (person2_id),
    INDEX idx_relationship_type (relationship_type),
    INDEX idx_confidence (confidence_score),
    INDEX idx_match_status (match_status),
    UNIQUE KEY unique_relationship (person1_id, person2_id, relationship_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- GRAMPS WEB INTEGRATION
-- ============================================================================

-- Tracks which Gramps records were created from which obituaries
CREATE TABLE gramps_record_mapping (
    id INT AUTO_INCREMENT PRIMARY KEY,
    obituary_cache_id INT NOT NULL,
    gramps_record_type ENUM('person', 'family', 'event', 'source', 'citation') NOT NULL,
    gramps_record_id VARCHAR(50) NOT NULL,  -- The Gramps internal ID
    extracted_person_id INT,  -- Link to extracted_persons if applicable
    extracted_relationship_id INT,  -- Link to extracted_relationships if applicable
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (obituary_cache_id) REFERENCES obituary_cache(id) ON DELETE CASCADE,
    FOREIGN KEY (extracted_person_id) REFERENCES extracted_persons(id) ON DELETE SET NULL,
    FOREIGN KEY (extracted_relationship_id) REFERENCES extracted_relationships(id) ON DELETE SET NULL,
    INDEX idx_gramps_record (gramps_record_type, gramps_record_id),
    INDEX idx_obituary (obituary_cache_id),
    UNIQUE KEY unique_gramps_mapping (gramps_record_type, gramps_record_id, obituary_cache_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- CONFIGURATION AND SETTINGS
-- ============================================================================

-- Stores application configuration (including tunable confidence thresholds)
CREATE TABLE config_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT NOT NULL,
    setting_type ENUM('string', 'integer', 'float', 'boolean', 'json') NOT NULL,
    description TEXT,
    updated_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_setting_key (setting_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert default configuration values
INSERT INTO config_settings (setting_key, setting_value, setting_type, description) VALUES
('confidence_threshold_auto_store', '0.85', 'float', 'Minimum confidence score for automatic storage without review'),
('confidence_threshold_review', '0.60', 'float', 'Minimum confidence score to flag for review (below this = rejected)'),
('llm_default_provider', 'openai', 'string', 'Default LLM provider to use'),
('llm_default_model', 'gpt-4', 'string', 'Default LLM model version'),
('always_review', 'false', 'boolean', 'Always require manual review before storing'),
('cache_expiry_days', '365', 'integer', 'Days before cached obituary content is considered stale'),
('max_retry_attempts', '3', 'integer', 'Maximum number of retry attempts for failed fetches');

-- ============================================================================
-- PROCESSING QUEUE
-- ============================================================================

-- Tracks processing jobs for async/batch processing
CREATE TABLE processing_queue (
    id INT AUTO_INCREMENT PRIMARY KEY,
    obituary_cache_id INT NOT NULL,
    queue_status ENUM('queued', 'processing', 'completed', 'failed', 'retry') DEFAULT 'queued',
    priority INT DEFAULT 5,  -- 1-10, lower = higher priority
    retry_count INT DEFAULT 0,
    error_message TEXT,
    queued_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_timestamp TIMESTAMP NULL,
    completed_timestamp TIMESTAMP NULL,
    FOREIGN KEY (obituary_cache_id) REFERENCES obituary_cache(id) ON DELETE CASCADE,
    INDEX idx_queue_status (queue_status),
    INDEX idx_priority (priority),
    INDEX idx_queued_timestamp (queued_timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- AUDIT LOG
-- ============================================================================

-- Tracks all changes and actions for audit purposes
CREATE TABLE audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action_type VARCHAR(50) NOT NULL,  -- 'fetch', 'extract', 'store', 'update', 'delete', etc.
    entity_type VARCHAR(50),  -- 'obituary', 'person', 'relationship', etc.
    entity_id INT,
    user_action BOOLEAN DEFAULT FALSE,  -- TRUE if user-initiated, FALSE if automated
    details JSON,  -- Additional context about the action
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_action_type (action_type),
    INDEX idx_entity (entity_type, entity_id),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- View for obituaries ready for processing
CREATE VIEW obituaries_pending_processing AS
SELECT 
    oc.id,
    oc.url,
    oc.fetch_timestamp,
    oc.processing_status,
    COUNT(ep.id) as extracted_persons_count,
    COUNT(er.id) as extracted_relationships_count
FROM obituary_cache oc
LEFT JOIN extracted_persons ep ON oc.id = ep.obituary_cache_id
LEFT JOIN extracted_relationships er ON oc.id = er.obituary_cache_id
WHERE oc.processing_status IN ('pending', 'processing')
GROUP BY oc.id, oc.url, oc.fetch_timestamp, oc.processing_status;

-- View for entities requiring review
CREATE VIEW entities_requiring_review AS
SELECT 
    ep.id,
    ep.full_name,
    ep.confidence_score,
    ep.match_status,
    oc.url as source_obituary_url,
    ep.extraction_notes
FROM extracted_persons ep
JOIN obituary_cache oc ON ep.obituary_cache_id = oc.id
WHERE ep.match_status = 'review_needed' 
   OR (ep.confidence_score < (SELECT CAST(setting_value AS DECIMAL(3,2)) FROM config_settings WHERE setting_key = 'confidence_threshold_auto_store'))
ORDER BY ep.confidence_score ASC;

-- View for LLM usage statistics
CREATE VIEW llm_usage_stats AS
SELECT 
    llm_provider,
    model_version,
    COUNT(*) as request_count,
    SUM(token_usage_total) as total_tokens,
    SUM(cost_usd) as total_cost_usd,
    AVG(duration_ms) as avg_duration_ms,
    DATE(request_timestamp) as date
FROM llm_cache
GROUP BY llm_provider, model_version, DATE(request_timestamp)
ORDER BY date DESC, total_cost_usd DESC;