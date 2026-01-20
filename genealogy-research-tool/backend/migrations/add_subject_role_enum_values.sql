-- Add new values to subject_role enum
-- MariaDB/MySQL syntax for modifying enum column

ALTER TABLE extracted_facts
MODIFY COLUMN subject_role ENUM(
    'deceased_primary',
    'spouse',
    'child',
    'parent',
    'sibling',
    'grandchild',
    'grandparent',
    'great_grandchild',
    'niece_nephew',
    'grand_niece_nephew',
    'in_law',
    'other'
) DEFAULT 'other';
