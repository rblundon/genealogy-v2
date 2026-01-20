import { useState, useEffect } from 'react';
import { useURLValidation } from '../../hooks/useURLValidation';
import { processObituary } from '../../api/client';

const PROCESSING_STEPS = [
  { id: 'validate', label: 'Validating URL' },
  { id: 'cache', label: 'Checking cache' },
  { id: 'fetch', label: 'Fetching obituary' },
  { id: 'extract', label: 'Extracting facts' },
  { id: 'store', label: 'Storing results' },
];

export function URLForm({ onSuccess, onError }) {
  const [url, setUrl] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [currentStep, setCurrentStep] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [verboseMode, setVerboseMode] = useState(true);

  const { isValid, error: validationError, warning } = useURLValidation(url);

  // Animate through steps while submitting
  useEffect(() => {
    if (!isSubmitting) {
      setCurrentStep(0);
      setElapsedSeconds(0);
      return;
    }

    // Progress through steps
    const stepInterval = setInterval(() => {
      setCurrentStep(prev => {
        // Cycle through steps 2-4 (fetch, extract, store) while waiting
        if (prev < 2) return prev + 1;
        if (prev >= PROCESSING_STEPS.length - 1) return 2;
        return prev + 1;
      });
    }, 1500);

    // Update elapsed time
    const timeInterval = setInterval(() => {
      setElapsedSeconds(prev => prev + 1);
    }, 1000);

    return () => {
      clearInterval(stepInterval);
      clearInterval(timeInterval);
    };
  }, [isSubmitting]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Don't submit if invalid or already submitting
    if (!isValid || isSubmitting) return;

    setIsSubmitting(true);
    setSubmitError(null);

    const startTime = Date.now();

    try {
      const result = await processObituary(url, { verboseMode });

      // Add processing time to result
      const processingTimeMs = Date.now() - startTime;

      // Call success callback with full result including processing time
      if (onSuccess) {
        onSuccess({
          ...result,
          processing_time_ms: processingTimeMs,
          verbose_mode: verboseMode,
        });
      }
    } catch (err) {
      const errorMessage = err.message || 'Failed to process obituary';
      setSubmitError(errorMessage);

      if (onError) {
        onError(errorMessage);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <div className="bg-white shadow-sm rounded-lg p-6">
        <h2 className="text-2xl font-semibold text-gray-900 mb-6">
          Process Obituary
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* URL Input */}
          <div>
            <label
              htmlFor="obituary-url"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Obituary URL
            </label>

            <input
              id="obituary-url"
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.legacy.com/us/obituaries/..."
              disabled={isSubmitting}
              className={`
                w-full px-4 py-2 border rounded-md shadow-sm
                focus:outline-none focus:ring-2 focus:ring-blue-500
                disabled:bg-gray-100 disabled:cursor-not-allowed
                ${validationError ? 'border-red-500' : 'border-gray-300'}
              `}
            />

            {/* Validation Error */}
            {validationError && (
              <p className="mt-2 text-sm text-red-600 flex items-center">
                <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                {validationError}
              </p>
            )}

            {/* Warning */}
            {warning && !validationError && (
              <p className="mt-2 text-sm text-yellow-600 flex items-center">
                <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                {warning}
              </p>
            )}

            {/* Info */}
            {!validationError && !warning && (
              <p className="mt-2 text-sm text-gray-500 flex items-center">
                <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                Currently supports Legacy.com obituaries
              </p>
            )}

            {/* Submit Error */}
            {submitError && (
              <p className="mt-2 text-sm text-red-600 flex items-center">
                <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
                {submitError}
              </p>
            )}
          </div>

          {/* Verbose Mode Toggle */}
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center">
              <label htmlFor="verbose-mode" className="text-sm font-medium text-gray-700">
                Verbose Mode
              </label>
              <span className="ml-2 text-xs text-gray-500">
                (Show live fact extraction)
              </span>
            </div>
            <button
              type="button"
              onClick={() => setVerboseMode(!verboseMode)}
              disabled={isSubmitting}
              className={`
                relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
                transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                ${verboseMode ? 'bg-blue-600' : 'bg-gray-200'}
                ${isSubmitting ? 'opacity-50 cursor-not-allowed' : ''}
              `}
              role="switch"
              aria-checked={verboseMode}
              aria-labelledby="verbose-mode"
            >
              <span
                className={`
                  pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0
                  transition duration-200 ease-in-out
                  ${verboseMode ? 'translate-x-5' : 'translate-x-0'}
                `}
              />
            </button>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={!isValid || isSubmitting}
            className={`
              w-full px-4 py-2 rounded-md font-medium
              focus:outline-none focus:ring-2 focus:ring-offset-2
              transition-colors duration-200
              ${
                !isValid || isSubmitting
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500'
              }
            `}
          >
            {isSubmitting ? (
              <span className="flex items-center justify-center">
                <svg
                  className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
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
                Processing...
              </span>
            ) : (
              'Process Obituary'
            )}
          </button>

          {/* Processing Progress */}
          {isSubmitting && (
            <div className="mt-6 pt-6 border-t border-gray-200">
              <div className="space-y-3">
                {PROCESSING_STEPS.map((step, index) => {
                  const isComplete = index < currentStep;
                  const isActive = index === currentStep;
                  const isPending = index > currentStep;

                  return (
                    <div key={step.id} className="flex items-center">
                      {isComplete && (
                        <svg className="w-5 h-5 text-green-500 mr-3" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                      )}
                      {isActive && (
                        <svg className="animate-spin w-5 h-5 text-blue-600 mr-3" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"/>
                        </svg>
                      )}
                      {isPending && (
                        <svg className="w-5 h-5 text-gray-300 mr-3" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm0-2a6 6 0 100-12 6 6 0 000 12z" clipRule="evenodd" />
                        </svg>
                      )}
                      <span className={`text-sm ${
                        isComplete ? 'text-gray-900' :
                        isActive ? 'text-blue-600 font-medium' :
                        'text-gray-400'
                      }`}>
                        {step.label}
                      </span>
                    </div>
                  );
                })}
              </div>
              <div className="mt-4 text-sm text-gray-500">
                Elapsed: {elapsedSeconds} second{elapsedSeconds !== 1 ? 's' : ''}
              </div>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
