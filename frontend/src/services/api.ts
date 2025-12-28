import axios from 'axios';
import type { Fact, FactsResponse, ProcessObituaryResponse, Obituary } from '../types';

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

export default api;
