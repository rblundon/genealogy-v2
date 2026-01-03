-- Add obituary_name column to gramps_citations for audit trail readability

ALTER TABLE gramps_citations
ADD COLUMN obituary_name VARCHAR(255) AFTER citation_type;
