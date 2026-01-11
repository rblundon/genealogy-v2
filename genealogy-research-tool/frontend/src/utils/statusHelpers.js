/**
 * Calculate progress percentage based on processing status
 * @param {string} status - Processing status from API
 * @returns {number} Progress percentage (0-100)
 */
export function getProgressPercentage(status) {
  const statusMap = {
    'pending': 10,
    'processing': 50,
    'completed': 100,
    'failed': 0,
  };

  return statusMap[status] || 0;
}

/**
 * Get user-friendly status message
 * @param {string} status - Processing status from API
 * @param {object} data - Additional data from API response
 * @returns {string} Human-readable status message
 */
export function getStatusMessage(status, data = {}) {
  switch (status) {
    case 'pending':
      return 'Waiting to start processing...';
    case 'processing':
      return 'Processing obituary...';
    case 'completed':
      return `Successfully extracted ${data.persons_extracted || 0} people and ${data.facts_extracted || 0} facts`;
    case 'failed':
      return data.fetch_error || 'Processing failed';
    default:
      return 'Unknown status';
  }
}

/**
 * Get processing steps with completion status
 * @param {string} currentStatus - Current processing status
 * @returns {Array} Array of step objects with completion state
 */
export function getProcessingSteps(currentStatus) {
  const steps = [
    { id: 'validate', label: 'Validating URL', status: 'complete' },
    { id: 'cache', label: 'Checking cache', status: 'complete' },
    { id: 'fetch', label: 'Fetching from Legacy.com', status: 'pending' },
    { id: 'extract', label: 'Extracting facts with AI', status: 'pending' },
    { id: 'store', label: 'Storing results', status: 'pending' },
  ];

  // Mark steps as complete/active based on status
  if (currentStatus === 'processing') {
    steps[2].status = 'active'; // Fetching
  } else if (currentStatus === 'completed') {
    steps.forEach(step => step.status = 'complete');
  } else if (currentStatus === 'failed') {
    steps[2].status = 'error';
  }

  return steps;
}

/**
 * Format elapsed time
 * @param {number} seconds - Elapsed seconds
 * @returns {string} Formatted time string
 */
export function formatElapsedTime(seconds) {
  if (seconds < 60) {
    return `${seconds} second${seconds !== 1 ? 's' : ''}`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  return `${minutes}m ${remainingSeconds}s`;
}
