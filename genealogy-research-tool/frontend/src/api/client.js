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
 * @param {Object} options - Processing options
 * @param {boolean} options.verboseMode - If true, adds delays between extraction steps for live visualization
 * @returns {Promise<{obituary_id: number, processing_status: string, persons_extracted: number, facts_extracted: number}>}
 */
export async function processObituary(sourceUrl, options = {}) {
  const { verboseMode = true } = options;

  const response = await fetch(`${API_BASE_URL}/api/obituaries/process`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      source_url: sourceUrl,
      verbose_mode: verboseMode,
    }),
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

/**
 * Get all obituaries
 * @returns {Promise<Array>} List of obituaries
 */
export async function getAllObituaries() {
  const response = await fetch(`${API_BASE_URL}/api/obituaries`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch obituaries');
  }

  return response.json();
}

/**
 * Get facts for an obituary
 * @param {number} obituaryId - The obituary ID
 * @returns {Promise<{obituary_id: number, fact_count: number, facts: Array}>}
 */
export async function getObituaryFacts(obituaryId) {
  const response = await fetch(`${API_BASE_URL}/api/obituaries/${obituaryId}/facts`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch facts');
  }

  return response.json();
}

/**
 * Delete an obituary
 * @param {number} obituaryId - The obituary ID
 * @returns {Promise<void>}
 */
export async function deleteObituary(obituaryId) {
  const response = await fetch(`${API_BASE_URL}/api/obituaries/${obituaryId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to delete obituary');
  }

  return response.json();
}

/**
 * Reprocess an obituary using its stored extracted text
 * @param {number} obituaryId - The obituary ID
 * @param {Object} options - Processing options
 * @param {boolean} options.verboseMode - If true, adds delays between extraction steps for live visualization
 * @returns {Promise<{status: string, obituary_id: number, persons_extracted: number, facts_extracted: number}>}
 */
export async function reprocessObituary(obituaryId, options = {}) {
  const { verboseMode = true } = options;

  const response = await fetch(`${API_BASE_URL}/api/obituaries/${obituaryId}/reprocess?verbose_mode=${verboseMode}`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to reprocess obituary');
  }

  return response.json();
}
