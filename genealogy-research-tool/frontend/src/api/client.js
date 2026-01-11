// Always use same hostname as frontend but port 8000 for API
function getApiBaseUrl() {
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return 'http://localhost:8000';
}
const API_BASE_URL = getApiBaseUrl();

/**
 * Process an obituary URL
 * @param {string} sourceUrl - The obituary URL to process
 * @returns {Promise<{obituary_id: number, processing_status: string, persons_extracted: number, facts_extracted: number}>}
 */
export async function processObituary(sourceUrl) {
  const response = await fetch(`${API_BASE_URL}/api/obituaries/process`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ source_url: sourceUrl }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to process obituary');
  }

  return response.json();
}

/**
 * Get obituary status by ID
 * @param {number} obituaryId - The obituary ID
 * @returns {Promise<{id: number, processing_status: string, persons_extracted: number, ...}>}
 */
export async function getObituaryStatus(obituaryId) {
  const response = await fetch(`${API_BASE_URL}/api/obituaries/${obituaryId}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get obituary status');
  }

  return response.json();
}
