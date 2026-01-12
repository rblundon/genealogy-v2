/**
 * Extract deceased person's name from URL
 * @param {string} url - Obituary URL
 * @returns {string} Extracted name or "Unknown"
 */
export function extractNameFromURL(url) {
  try {
    const urlObj = new URL(url);
    const pathParts = urlObj.pathname.split('/');

    // Legacy.com format: /us/obituaries/source/name/firstname-lastname-obituary
    const nameIndex = pathParts.findIndex(part => part === 'name');
    if (nameIndex !== -1 && pathParts[nameIndex + 1]) {
      const namePart = pathParts[nameIndex + 1];
      // Convert "maxine-kaczmarowski-obituary" to "Maxine Kaczmarowski"
      return namePart
        .replace(/-obituary.*$/, '')
        .split('-')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
    }

    return 'Unknown';
  } catch {
    return 'Unknown';
  }
}

/**
 * Format timestamp as relative time (e.g., "2 hours ago")
 * @param {string} timestamp - ISO timestamp
 * @returns {string} Relative time string
 */
export function formatRelativeTime(timestamp) {
  if (!timestamp) return 'Never';

  const now = new Date();
  const date = new Date(timestamp);
  const seconds = Math.floor((now - date) / 1000);

  if (seconds < 60) return 'Just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;

  return date.toLocaleDateString();
}

/**
 * Truncate text to specified length
 * @param {string} text - Text to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} Truncated text with ellipsis
 */
export function truncate(text, maxLength = 50) {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}
