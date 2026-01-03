-- Add gramps_citations table for tracking citations created in Gramps Web

CREATE TABLE IF NOT EXISTS gramps_citations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    obituary_cache_id INT NOT NULL,
    person_cluster_id INT,
    gramps_person_id VARCHAR(50) NOT NULL,
    gramps_source_id VARCHAR(50),
    gramps_citation_id VARCHAR(50),
    citation_type VARCHAR(50) DEFAULT 'obituary',
    confidence ENUM('very_high', 'high', 'medium', 'low') DEFAULT 'high',
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) DEFAULT 'genealogy_tool',

    FOREIGN KEY (obituary_cache_id) REFERENCES obituary_cache(id) ON DELETE CASCADE,
    FOREIGN KEY (person_cluster_id) REFERENCES person_clusters(id) ON DELETE CASCADE,

    INDEX idx_gramps_person (gramps_person_id),
    INDEX idx_gramps_source (gramps_source_id),
    UNIQUE KEY unique_citation (gramps_person_id, obituary_cache_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
