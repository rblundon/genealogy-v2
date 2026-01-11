import { useState, useEffect, useRef } from 'react';

/**
 * Custom hook for polling an API endpoint
 * @param {Function} fetchFn - Async function to call for polling
 * @param {number} interval - Poll interval in milliseconds
 * @param {Function} shouldStop - Function that returns true when polling should stop
 * @returns {{data: any, error: Error|null, isPolling: boolean}}
 */
export function usePolling(fetchFn, interval = 1000, shouldStop = () => false) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [isPolling, setIsPolling] = useState(true);
  const intervalRef = useRef(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const result = await fetchFn();
        setData(result);

        // Check if we should stop polling
        if (shouldStop(result)) {
          setIsPolling(false);
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
          }
        }
      } catch (err) {
        setError(err);
        setIsPolling(false);
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      }
    };

    // Initial poll
    poll();

    // Set up interval
    if (isPolling) {
      intervalRef.current = setInterval(poll, interval);
    }

    // Cleanup
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchFn, interval, shouldStop, isPolling]);

  return { data, error, isPolling };
}
