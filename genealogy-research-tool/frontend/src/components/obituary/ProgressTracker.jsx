import { useState, useEffect, useCallback } from 'react';
import { usePolling } from '../../hooks/usePolling';
import { getObituaryStatus } from '../../api/client';
import {
  getProgressPercentage,
  getStatusMessage,
  getProcessingSteps,
  formatElapsedTime,
} from '../../utils/statusHelpers';

export function ProgressTracker({ obituaryId, initialResult, onComplete, onError }) {
  const [startTime] = useState(Date.now());
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [showFacts, setShowFacts] = useState(initialResult?.verbose_mode ?? true);

  // If we have initial result with completed status, use it directly
  // Note: Don't check status === 'success' alone, as async processing returns
  // {status: 'success', processing_status: 'processing'} for background tasks
  const alreadyComplete = initialResult?.processing_status === 'completed';

  // Polling function
  const fetchStatus = useCallback(
    () => getObituaryStatus(obituaryId),
    [obituaryId]
  );

  // Stop polling when completed or failed, or if already complete
  const shouldStopPolling = useCallback(
    (data) => {
      if (alreadyComplete) return true;
      if (!data) return false;
      return data.processing_status === 'completed' || data.processing_status === 'failed';
    },
    [alreadyComplete]
  );

  // Poll for status updates (skip if already complete)
  const { data: polledData, error, isPolling } = usePolling(
    fetchStatus,
    1000,  // Poll every 1 second
    shouldStopPolling
  );

  // Use initial result if available and complete, otherwise use polled data
  const obituary = alreadyComplete ? {
    id: initialResult.obituary_id,
    url: initialResult.url || 'Processing complete',
    processing_status: 'completed',
    persons_extracted: initialResult.persons_extracted || 0,
    facts_extracted: initialResult.facts_extracted || 0,
    llm_cost_usd: initialResult.llm_cost_usd || 0,
    processing_time_ms: initialResult.processing_time_ms || 0,
  } : polledData;

  // Update elapsed time (stop when not polling or already complete)
  useEffect(() => {
    if (!isPolling || alreadyComplete) return;

    const timer = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    return () => clearInterval(timer);
  }, [startTime, isPolling, alreadyComplete]);

  // Handle completion
  useEffect(() => {
    if (obituary?.processing_status === 'completed' && onComplete) {
      onComplete(obituary);
    }
  }, [obituary, onComplete]);

  // Handle errors
  useEffect(() => {
    if (error && onError) {
      onError(error);
    }

    if (obituary?.processing_status === 'failed' && onError) {
      onError(new Error(obituary.fetch_error || 'Processing failed'));
    }
  }, [error, obituary, onError]);

  if (!obituary) {
    return (
      <div className="w-full max-w-2xl mx-auto">
        <div className="bg-white shadow-sm rounded-lg p-6">
          <div className="flex items-center justify-center">
            <svg
              className="animate-spin h-8 w-8 text-blue-600"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <span className="ml-3 text-gray-600">Loading status...</span>
          </div>
        </div>
      </div>
    );
  }

  const progress = getProgressPercentage(obituary.processing_status);
  const statusMessage = getStatusMessage(obituary.processing_status, obituary);
  const steps = getProcessingSteps(obituary.processing_status);
  const isComplete = obituary.processing_status === 'completed';
  const isFailed = obituary.processing_status === 'failed';

  // Use processing_time_ms from result if available, otherwise use elapsed timer
  const displayTime = obituary.processing_time_ms
    ? Math.ceil(obituary.processing_time_ms / 1000)
    : elapsedSeconds;

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="bg-white shadow-sm rounded-lg p-6">
        {/* Header */}
        <div className="mb-6">
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">
            {isComplete ? 'Processing Complete' : isFailed ? 'Processing Failed' : 'Processing Obituary'}
          </h2>

          {/* URL */}
          <div className="text-sm text-gray-500 break-all">
            {obituary.url}
          </div>
        </div>

        {/* Status Message */}
        <div className={`mb-4 p-3 rounded-md ${
          isComplete ? 'bg-green-50 text-green-800' :
          isFailed ? 'bg-red-50 text-red-800' :
          'bg-blue-50 text-blue-800'
        }`}>
          <div className="flex items-center">
            {isComplete && (
              <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            )}
            {isFailed && (
              <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            )}
            {isPolling && (
              <svg className="animate-spin w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
              </svg>
            )}
            <span className="font-medium">{statusMessage}</span>
          </div>
        </div>

        {/* Progress Bar */}
        {!isFailed && (
          <div className="mb-6">
            <div className="relative pt-1">
              <div className="flex mb-2 items-center justify-between">
                <div>
                  <span className="text-xs font-semibold inline-block text-blue-600">
                    Progress
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-xs font-semibold inline-block text-blue-600">
                    {progress}%
                  </span>
                </div>
              </div>
              <div className="overflow-hidden h-2 mb-4 text-xs flex rounded bg-blue-100">
                <div
                  style={{ width: `${progress}%` }}
                  className="shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center bg-blue-600 transition-all duration-500"
                />
              </div>
            </div>
          </div>
        )}

        {/* Processing Steps */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-gray-700 mb-3">Processing Steps:</h3>
          <div className="space-y-2">
            {steps.map((step) => (
              <div key={step.id} className="flex items-center">
                {step.status === 'complete' && (
                  <svg className="w-5 h-5 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                )}
                {step.status === 'active' && (
                  <svg className="animate-spin w-5 h-5 text-blue-600 mr-2" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
                  </svg>
                )}
                {step.status === 'pending' && (
                  <svg className="w-5 h-5 text-gray-300 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12z" clipRule="evenodd" />
                  </svg>
                )}
                {step.status === 'error' && (
                  <svg className="w-5 h-5 text-red-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                )}
                <span className={`text-sm ${
                  step.status === 'complete' ? 'text-gray-900' :
                  step.status === 'active' ? 'text-blue-600 font-medium' :
                  step.status === 'error' ? 'text-red-600' :
                  'text-gray-400'
                }`}>
                  {step.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Live Facts Display - show during processing */}
        {obituary.facts && obituary.facts.length > 0 && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center">
                <h3 className="text-sm font-medium text-gray-700">
                  Facts Extracted ({obituary.facts.length}):
                </h3>
                {isPolling && (
                  <span className="ml-2 text-xs text-blue-600 animate-pulse">Live updating...</span>
                )}
              </div>
              <button
                onClick={() => setShowFacts(!showFacts)}
                className="text-sm text-blue-600 hover:text-blue-800 focus:outline-none"
              >
                {showFacts ? 'Hide' : 'Show'}
              </button>
            </div>
            {showFacts && (
              <div className="max-h-64 overflow-y-auto border border-gray-200 rounded-md bg-gray-50">
                <div className="divide-y divide-gray-200">
                  {obituary.facts.map((fact, index) => (
                    <div
                      key={fact.id || index}
                      className={`p-3 text-sm ${
                        index === obituary.facts.length - 1 && isPolling
                          ? 'bg-blue-50 animate-pulse'
                          : ''
                      }`}
                    >
                      <div className="flex items-start">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium mr-2 ${
                          fact.is_inferred
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-green-100 text-green-800'
                        }`}>
                          {fact.fact_type?.replace(/_/g, ' ')}
                        </span>
                        <span className="text-gray-900 flex-1">
                          {fact.description}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Elapsed Time */}
        <div className="text-sm text-gray-500">
          Elapsed: {formatElapsedTime(displayTime)}
        </div>

        {/* Results Summary (only show when complete) */}
        {isComplete && (
          <div className="mt-6 pt-6 border-t border-gray-200">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Results:</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-2xl font-bold text-gray-900">
                  {obituary.persons_extracted || 0}
                </div>
                <div className="text-sm text-gray-500">People Found</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900">
                  {obituary.facts_extracted || 0}
                </div>
                <div className="text-sm text-gray-500">Facts Extracted</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900">
                  ${obituary.llm_cost_usd?.toFixed(2) || '0.00'}
                </div>
                <div className="text-sm text-gray-500">Processing Cost</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900">
                  {displayTime}s
                </div>
                <div className="text-sm text-gray-500">Total Time</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
