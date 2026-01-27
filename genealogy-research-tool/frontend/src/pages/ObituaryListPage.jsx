import { useState, useEffect } from 'react';
import { ObituaryTable } from '../components/obituary/ObituaryTable';
import { getAllObituaries, reprocessAllObituaries } from '../api/client';

export function ObituaryListPage() {
  const [obituaries, setObituaries] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isReprocessing, setIsReprocessing] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadObituaries();
  }, []);

  const loadObituaries = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await getAllObituaries();
      // Sort by most recent first
      const sorted = data.sort((a, b) =>
        new Date(b.fetch_timestamp) - new Date(a.fetch_timestamp)
      );
      setObituaries(sorted);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReprocessAll = async () => {
    setIsReprocessing(true);
    setError(null);

    try {
      await reprocessAllObituaries();
      await loadObituaries();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsReprocessing(false);
    }
  };

  const totalCost = obituaries?.reduce((sum, obit) =>
    sum + (obit.llm_cost_usd || 0), 0
  ) || 0;

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Obituaries
            </h1>
            <p className="text-gray-600">
              View and manage processed obituaries
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={loadObituaries}
              disabled={isLoading || isReprocessing}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            >
              <svg
                className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              Refresh
            </button>

            <button
              onClick={handleReprocessAll}
              disabled={isLoading || isReprocessing || !obituaries?.length}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            >
              <svg
                className={`w-4 h-4 mr-2 ${isReprocessing ? 'animate-spin' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                {isReprocessing ? (
                  <>
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
                  </>
                ) : (
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                )}
              </svg>
              {isReprocessing ? 'Reprocessing...' : 'Reprocess All'}
            </button>
          </div>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">
                Failed to load obituaries
              </h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && !obituaries && (
        <div className="bg-white shadow-sm rounded-lg p-12 text-center">
          <svg
            className="animate-spin mx-auto h-12 w-12 text-blue-600 mb-4"
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
          <p className="text-gray-600">Loading obituaries...</p>
        </div>
      )}

      {/* Table */}
      {!isLoading && obituaries && (
        <>
          <ObituaryTable
            obituaries={obituaries}
            onObituaryDeleted={loadObituaries}
          />

          {/* Footer Stats */}
          <div className="mt-4 text-sm text-gray-500 text-center">
            Showing {obituaries.length} obituar{obituaries.length === 1 ? 'y' : 'ies'}
            {totalCost > 0 && ` • Total cost: $${totalCost.toFixed(2)}`}
          </div>
        </>
      )}
    </div>
  );
}
