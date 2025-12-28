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

// Obituary summary for list view
export interface ObituarySummary {
  id: number;
  url: string;
  primary_name: string;
  primary_name_formatted: string;
  last_name: string;
  first_name: string;
  status: string;
  fact_count: number;
  unresolved_count: number;
  created_at: string | null;
}

// Person types
export type SyncStatus = 'pending' | 'matched' | 'created' | 'committed' | 'rejected';

export interface PersonSummary {
  id: number;
  name: string;
  name_formatted: string;
  first_name: string | null;
  middle_name: string | null;
  last_name: string | null;
  primary_role: SubjectRole;
  obituary_count: number;
  fact_count: number;
  resolved_count: number;
  unresolved_count: number;
  gramps_handle: string | null;
  gramps_id: string | null;
  sync_status: SyncStatus;
}

export interface ObituaryFacts {
  obituary_id: number;
  obituary_url: string;
  role: SubjectRole;
  facts: Fact[];
}

export interface PersonDetail {
  id: number;
  name: string;
  name_formatted: string;
  first_name: string | null;
  middle_name: string | null;
  last_name: string | null;
  gramps_handle: string | null;
  gramps_id: string | null;
  sync_status: SyncStatus;
  obituary_facts: ObituaryFacts[];
}

export interface GrampsMatch {
  handle: string;
  gramps_id: string;
  name: string;
  first_name: string;
  surname: string;
  score: number;
  match_details: {
    first_name_score: number;
    surname_score: number;
    token_score: number;
    exact_surname: boolean;
    exact_first: boolean;
  };
}

export interface SyncResult {
  success: boolean;
  person_name: string;
  gramps_handle: string | null;
  gramps_id: string | null;
  action: 'created' | 'linked' | 'skipped';
  events_created: number;
  families_created: number;
}
