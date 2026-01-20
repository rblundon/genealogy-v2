/**
 * Calculate progress percentage based on processing status and step
 * @param {string} status - Processing status from API
 * @param {string} processingStep - Current processing step from backend
 * @returns {number} Progress percentage (0-100)
 */
export function getProgressPercentage(status, processingStep = null) {
  // If completed, return 100%
  if (status === 'completed' || processingStep === 'completed') {
    return 100;
  }

  // If failed, show progress at failure point
  if (status === 'failed') {
    return 0;
  }

  // Use processing step for more accurate progress
  if (processingStep) {
    const stepProgress = {
      'validating': 10,
      'fetching': 30,
      'extracting': 60,
      'storing': 90,
    };
    return stepProgress[processingStep] || 50;
  }

  // Fallback to status-based progress
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
 * Get processing steps with completion status based on real backend step
 * @param {string} currentStatus - Current processing status
 * @param {string} processingStep - Current processing step from backend
 * @returns {Array} Array of step objects with completion state
 */
export function getProcessingSteps(currentStatus, processingStep = null) {
  // Step order: validating -> fetching -> extracting -> storing -> completed
  const stepOrder = ['validating', 'fetching', 'extracting', 'storing', 'completed'];

  const steps = [
    { id: 'validating', label: 'Validating URL', status: 'pending' },
    { id: 'fetching', label: 'Fetching from Legacy.com', status: 'pending' },
    { id: 'extracting', label: 'Extracting facts', status: 'pending' },
    { id: 'storing', label: 'Storing results', status: 'pending' },
  ];

  // If completed or failed, mark all steps appropriately
  if (currentStatus === 'completed' || processingStep === 'completed') {
    steps.forEach(step => step.status = 'complete');
    return steps;
  }

  if (currentStatus === 'failed' || processingStep === 'failed') {
    // Mark steps up to the failure point
    const currentIndex = stepOrder.indexOf(processingStep);
    steps.forEach((step, index) => {
      if (index < currentIndex) {
        step.status = 'complete';
      } else if (index === currentIndex || (currentIndex === -1 && index === 0)) {
        step.status = 'error';
      }
    });
    return steps;
  }

  // Mark steps based on current processing step
  if (processingStep) {
    const currentIndex = stepOrder.indexOf(processingStep);
    steps.forEach((step, index) => {
      const stepIndex = stepOrder.indexOf(step.id);
      if (stepIndex < currentIndex) {
        step.status = 'complete';
      } else if (stepIndex === currentIndex) {
        step.status = 'active';
      }
    });
  } else if (currentStatus === 'processing') {
    // Fallback: if no processingStep, show first step as active
    steps[0].status = 'active';
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
