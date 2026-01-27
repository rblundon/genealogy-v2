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

/**
 * Get all identified people
 * @param {number} minConfidence - Minimum confidence score (0.0-1.0)
 * @param {number} minSources - Minimum number of source obituaries
 * @returns {Promise<{count: number, people: Array}>}
 */
export async function getPeople(minConfidence = 0.70, minSources = 1) {
  const response = await fetch(
    `${API_BASE_URL}/api/people?min_sources=${minSources}`
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch people');
  }

  const data = await response.json();

  // Filter by confidence on client side since backend only filters by min_sources
  const filteredPeople = data.people.filter(p => (p.confidence || 0) >= minConfidence);

  return {
    count: filteredPeople.length,
    people: filteredPeople
  };
}

/**
 * Get detailed information about an identified person
 * @param {number} personId - The person ID
 * @returns {Promise<Object>} Person details with facts and sources
 */
export async function getPersonDetail(personId) {
  const response = await fetch(`${API_BASE_URL}/api/people/${personId}`);

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch person details');
  }

  return response.json();
}

/**
 * Get people ready for Gramps sync
 * @param {number} minConfidence - Minimum confidence score (default: 0.80)
 * @param {number} minSources - Minimum number of sources (default: 2)
 * @returns {Promise<{count: number, people: Array}>}
 */
export async function getPeopleReadyForSync(minConfidence = 0.80, minSources = 2) {
  const response = await fetch(
    `${API_BASE_URL}/api/people/ready-for-sync?min_confidence=${minConfidence}&min_sources=${minSources}`
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch people ready for sync');
  }

  return response.json();
}

/**
 * Generate/regenerate people clusters from extracted facts
 * @returns {Promise<{status: string, clusters_created: number}>}
 */
export async function generatePeople() {
  const response = await fetch(`${API_BASE_URL}/api/people/generate`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to generate people');
  }

  return response.json();
}

/**
 * Reprocess all obituaries using their stored extracted text
 * @returns {Promise<{status: string, reprocessed_count: number}>}
 */
export async function reprocessAllObituaries() {
  const response = await fetch(`${API_BASE_URL}/api/obituaries/reprocess-all`, {
    method: 'POST',
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to reprocess obituaries');
  }

  return response.json();
}
