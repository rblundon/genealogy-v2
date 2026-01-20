-- Add processing_step column to obituary_cache table
-- This tracks the current processing step for real-time UI updates

ALTER TABLE obituary_cache
ADD COLUMN IF NOT EXISTS processing_step VARCHAR(50) DEFAULT NULL;

-- Comment: Possible values are 'validating', 'fetching', 'extracting', 'storing', 'completed', 'failed'
