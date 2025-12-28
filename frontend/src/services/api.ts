import axios from 'axios';
import type {
  Fact,
  FactsResponse,
  ProcessObituaryResponse,
  Obituary,
  ObituarySummary,
  PersonSummary,
  PersonDetail,
  GrampsMatch,
  SyncResult,
} from '../types';

// Use same hostname as frontend, but port 8000 for backend
const getApiUrl = () => {
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }
  // In browser, use same host but backend port
  if (typeof window !== 'undefined' && window.location.hostname !== 'localhost') {
    return `http://${window.location.hostname}:8000`;
  }
  return 'http://localhost:8000';
};

const API_URL = getApiUrl();

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Health check
export async function checkHealth(): Promise<{ status: string }> {
  const response = await api.get('/health');
  return response.data;
}

// Process a new obituary URL
export async function processObituary(url: string): Promise<ProcessObituaryResponse> {
  const response = await api.post('/api/obituaries/process', { url });
  return response.data;
}

// Get facts for a specific obituary
export async function getObituaryFacts(obituaryId: number): Promise<FactsResponse> {
  const response = await api.get(`/api/obituaries/facts/${obituaryId}`);
  return response.data;
}

// Get obituary status
export async function getObituaryStatus(obituaryId: number): Promise<Obituary> {
  const response = await api.get(`/api/obituaries/status/${obituaryId}`);
  return response.data;
}

// Get pending obituaries
export async function getPendingObituaries(): Promise<{ count: number; obituaries: Obituary[] }> {
  const response = await api.get('/api/obituaries/pending');
  return response.data;
}

// Get unresolved facts
export async function getUnresolvedFacts(limit = 100): Promise<{ count: number; facts: Fact[] }> {
  const response = await api.get(`/api/obituaries/unresolved-facts?limit=${limit}`);
  return response.data;
}

// Reprocess an obituary
export async function reprocessObituary(obituaryId: number): Promise<ProcessObituaryResponse> {
  const response = await api.post(`/api/obituaries/reprocess/${obituaryId}`);
  return response.data;
}

// Update fact resolution status
export async function updateFactStatus(
  factId: number,
  status: 'resolved' | 'rejected' | 'unresolved' | 'conflicting'
): Promise<{ id: number; old_status: string; new_status: string; fact: Fact }> {
  const response = await api.patch(`/api/obituaries/facts/${factId}/status`, {
    resolution_status: status,
  });
  return response.data;
}

// Bulk update fact statuses
export async function bulkUpdateFactStatus(
  factIds: number[],
  status: 'resolved' | 'rejected' | 'unresolved' | 'conflicting'
): Promise<{ updated_count: number; requested_ids: number[]; new_status: string }> {
  const response = await api.patch('/api/obituaries/facts/bulk-status', {
    fact_ids: factIds,
    resolution_status: status,
  });
  return response.data;
}

// ============================================================================
// Obituaries List Endpoints
// ============================================================================

// Get all obituaries
export async function getObituaries(): Promise<{ count: number; obituaries: ObituarySummary[] }> {
  const response = await api.get('/api/obituaries/');
  return response.data;
}

// Delete an obituary
export async function deleteObituary(
  obituaryId: number
): Promise<{ deleted: boolean; obituary_id: number; url: string }> {
  const response = await api.delete(`/api/obituaries/${obituaryId}`);
  return response.data;
}

// ============================================================================
// Persons Endpoints
// ============================================================================

// Get all persons
export async function getPersons(): Promise<{ count: number; persons: PersonSummary[] }> {
  const response = await api.get('/api/persons/');
  return response.data;
}

// Get person by name
export async function getPersonByName(name: string): Promise<PersonDetail> {
  const response = await api.get('/api/persons/by-name/detail', { params: { name } });
  return response.data;
}

// Get Gramps match suggestions for a person
export async function getGrampsMatches(
  name: string
): Promise<{ person_name: string; matches: GrampsMatch[] }> {
  const response = await api.get('/api/persons/by-name/gramps-matches', { params: { name } });
  return response.data;
}

// Sync person to Gramps
export async function syncPerson(
  name: string,
  options: {
    gramps_handle?: string;
    create_new?: boolean;
    include_relationships?: boolean;
  }
): Promise<SyncResult> {
  const response = await api.post('/api/persons/by-name/sync', options, { params: { name } });
  return response.data;
}

// Skip person sync
export async function skipPersonSync(
  name: string
): Promise<{ success: boolean; person_name: string; action: string }> {
  const response = await api.post('/api/persons/by-name/skip', {}, { params: { name } });
  return response.data;
}

// Delete person and their facts
export async function deletePerson(
  name: string
): Promise<{ deleted: boolean; person_name: string; facts_deleted: number; resolutions_deleted: number }> {
  const response = await api.delete('/api/persons/by-name/delete', { params: { name } });
  return response.data;
}

export default api;
