-- Migration: 005_multi_pass_extraction.sql
-- Description: Add persons table, extraction passes, and multi-pass support
-- Date: 2025-12-30

-- ============================================================================
-- Canonical persons table (across all obituaries)
-- ============================================================================
CREATE TABLE persons (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- Name fields
    full_name VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    middle_name VARCHAR(100),
    last_name VARCHAR(100),
    suffix VARCHAR(20),
    maiden_name VARCHAR(100),

    -- Deceased tracking (IMMUTABLE - once TRUE, never FALSE)
    -- Application logic must enforce: only allow TRUE -> TRUE, never TRUE -> FALSE
    is_deceased BOOLEAN DEFAULT FALSE,
    deceased_date DATE NULL,
    deceased_source_obituary_id INT NULL,  -- Which obituary told us they're deceased

    -- Link to their own obituary (if they are the primary deceased)
    primary_obituary_id INT NULL,  -- FK to obituary_cache.id

    -- Gender
    gender ENUM('male', 'female', 'unknown') DEFAULT 'unknown',

    -- Gramps sync
    gramps_handle VARCHAR(64),
    gramps_id VARCHAR(20),
    sync_status ENUM('pending', 'matched', 'created', 'committed', 'rejected') DEFAULT 'pending',

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (primary_obituary_id) REFERENCES obituary_cache(id) ON DELETE SET NULL,
    FOREIGN KEY (deceased_source_obituary_id) REFERENCES obituary_cache(id) ON DELETE SET NULL,

    -- Indexes
    INDEX idx_last_name (last_name),
    INDEX idx_full_name (full_name),
    INDEX idx_deceased (is_deceased),
    INDEX idx_primary_obituary (primary_obituary_id),
    INDEX idx_gramps_handle (gramps_handle),
    INDEX idx_sync_status (sync_status)
);

-- ============================================================================
-- Track extraction passes for each obituary
-- ============================================================================
CREATE TABLE extraction_pass (
    id INT AUTO_INCREMENT PRIMARY KEY,
    obituary_cache_id INT NOT NULL,
    pass_number INT NOT NULL,  -- 1, 2, or 3
    llm_cache_id INT NULL,
    status ENUM('pending', 'running', 'completed', 'failed') DEFAULT 'pending',
    error_message TEXT NULL,

    -- Hash of input/output for cache validation
    input_hash VARCHAR(64) NULL,
    output_hash VARCHAR(64) NULL,

    -- Timestamps
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_timestamp TIMESTAMP NULL,

    -- Foreign keys
    FOREIGN KEY (obituary_cache_id) REFERENCES obituary_cache(id) ON DELETE CASCADE,
    FOREIGN KEY (llm_cache_id) REFERENCES llm_cache(id) ON DELETE SET NULL,

    -- Indexes
    INDEX idx_obituary_pass (obituary_cache_id, pass_number),
    UNIQUE KEY unique_obituary_pass (obituary_cache_id, pass_number)
);

-- ============================================================================
-- Add pass tracking to llm_cache
-- ============================================================================
ALTER TABLE llm_cache ADD COLUMN pass_number INT NULL;
ALTER TABLE llm_cache ADD COLUMN pass_input_hash VARCHAR(64) NULL;
ALTER TABLE llm_cache ADD INDEX idx_pass_number (pass_number);

-- ============================================================================
-- Link extracted_facts to persons table
-- ============================================================================
ALTER TABLE extracted_facts ADD COLUMN person_id INT NULL;
ALTER TABLE extracted_facts ADD COLUMN related_person_id INT NULL;
ALTER TABLE extracted_facts ADD COLUMN extraction_pass_id INT NULL;

ALTER TABLE extracted_facts ADD INDEX idx_person_id (person_id);
ALTER TABLE extracted_facts ADD INDEX idx_related_person_id (related_person_id);
ALTER TABLE extracted_facts ADD INDEX idx_extraction_pass_id (extraction_pass_id);

ALTER TABLE extracted_facts
    ADD CONSTRAINT fk_extracted_facts_person
    FOREIGN KEY (person_id) REFERENCES persons(id) ON DELETE SET NULL;

ALTER TABLE extracted_facts
    ADD CONSTRAINT fk_extracted_facts_related_person
    FOREIGN KEY (related_person_id) REFERENCES persons(id) ON DELETE SET NULL;

ALTER TABLE extracted_facts
    ADD CONSTRAINT fk_extracted_facts_extraction_pass
    FOREIGN KEY (extraction_pass_id) REFERENCES extraction_pass(id) ON DELETE SET NULL;
