-- Migration: Add cluster ID columns to extracted_facts
-- Purpose: Replace fragile name-based matching with direct foreign key relationships
-- Date: 2026-01-04

-- Add cluster ID columns
ALTER TABLE extracted_facts
  ADD COLUMN subject_cluster_id INT AFTER subject_name,
  ADD COLUMN related_cluster_id INT AFTER related_name;

-- Add foreign key constraints
ALTER TABLE extracted_facts
  ADD CONSTRAINT fk_subject_cluster
    FOREIGN KEY (subject_cluster_id)
    REFERENCES person_clusters(id)
    ON DELETE SET NULL;

ALTER TABLE extracted_facts
  ADD CONSTRAINT fk_related_cluster
    FOREIGN KEY (related_cluster_id)
    REFERENCES person_clusters(id)
    ON DELETE SET NULL;

-- Add indexes for performance
CREATE INDEX idx_subject_cluster ON extracted_facts(subject_cluster_id);
CREATE INDEX idx_related_cluster ON extracted_facts(related_cluster_id);
