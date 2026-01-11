-- Add gramps_source_id to obituary_cache for tracking sync status
ALTER TABLE obituary_cache
  ADD COLUMN gramps_source_id VARCHAR(50) AFTER processing_status,
  ADD INDEX idx_gramps_source (gramps_source_id);

-- Update comment
ALTER TABLE obituary_cache
  MODIFY COLUMN gramps_source_id VARCHAR(50)
  COMMENT 'Gramps source ID when obituary source is created in Gramps Web';
