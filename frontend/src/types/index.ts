// Types for the Genealogy Research Tool

export interface Fact {
  id: number;
  obituary_cache_id: number;
  fact_type: FactType;
  subject_name: string;
  subject_role: SubjectRole;
  fact_value: string;
  related_name: string | null;
  relationship_type: string | null;
  extracted_context: string | null;
  source_sentence: string | null;
  is_inferred: boolean;
  inference_basis: string | null;
  confidence_score: number;
  resolution_status: ResolutionStatus;
  gramps_person_id: string | null;
  gramps_family_id: string | null;
  gramps_event_id: string | null;
  created_timestamp: string | null;
}

export type FactType =
  | 'person_name'
  | 'person_death_date'
  | 'person_death_age'
  | 'person_birth_date'
  | 'person_gender'
  | 'maiden_name'
  | 'relationship'
  | 'marriage'
  | 'location_birth'
  | 'location_death'
  | 'location_residence'
  | 'survived_by'
  | 'preceded_in_death';

export type SubjectRole =
  | 'deceased_primary'
  | 'spouse'
  | 'child'
  | 'parent'
  | 'sibling'
  | 'grandchild'
  | 'great_grandchild'
  | 'grandparent'
  | 'in_law'
  | 'other';

export type ResolutionStatus = 'unresolved' | 'resolved' | 'conflicting' | 'rejected';

export interface Obituary {
  id: number;
  url: string;
  processing_status: 'pending' | 'processing' | 'completed' | 'failed';
  facts_count: number;
  fetch_timestamp: string | null;
}

export interface ObituaryWithFacts extends Obituary {
  facts: Fact[];
}

// Grouped facts by subject name
export interface FactCluster {
  subject_name: string;
  subject_role: SubjectRole;
  facts: Fact[];
}

// API Response types
export interface ProcessObituaryResponse {
  obituary_id: number;
  url: string;
  facts_extracted: number;
  cache_hit: boolean;
  facts: Fact[];
}

export interface FactsResponse {
  obituary_id: number;
  url: string;
  processing_status: string;
  facts_count: number;
  facts: Fact[];
}
