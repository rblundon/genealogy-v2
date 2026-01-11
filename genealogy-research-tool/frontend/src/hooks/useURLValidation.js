import { useState, useEffect } from 'react';

/**
 * Validates URLs with real-time feedback
 * @param {string} url - URL to validate
 * @returns {{isValid: boolean, error: string|null, warning: string|null}}
 */
export function useURLValidation(url) {
  const [validation, setValidation] = useState({
    isValid: false,
    error: null,
    warning: null,
  });

  useEffect(() => {
    // Empty URL is not an error (user hasn't typed yet)
    if (!url.trim()) {
      setValidation({ isValid: false, error: null, warning: null });
      return;
    }

    // Check URL format
    try {
      const urlObj = new URL(url);

      // Valid URL, but check if it's Legacy.com
      if (!urlObj.hostname.includes('legacy.com')) {
        setValidation({
          isValid: true,
          error: null,
          warning: 'This doesn\'t appear to be a Legacy.com URL. Processing may fail.',
        });
      } else {
        setValidation({
          isValid: true,
          error: null,
          warning: null,
        });
      }
    } catch (e) {
      setValidation({
        isValid: false,
        error: 'Please enter a valid URL (e.g., https://www.legacy.com/...)',
        warning: null,
      });
    }
  }, [url]);

  return validation;
}
