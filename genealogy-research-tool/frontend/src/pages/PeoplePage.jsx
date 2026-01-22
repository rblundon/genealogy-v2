import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getPeople } from '../api/client';
import { ConfidenceBadge } from '../components/shared/ConfidenceBadge';
import { PersonStatusBadge } from '../components/shared/PersonStatusBadge';

export function PeoplePage() {
  const navigate = useNavigate();
  const [people, setPeople] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [minConfidence, setMinConfidence] = useState(0.70);
  const [minSources, setMinSources] = useState(1);

  useEffect(() => {
    loadPeople();
  }, [minConfidence, minSources]);

  const loadPeople = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await getPeople(minConfidence, minSources);
      // Sort by source count (most sources first), then by confidence
      const sorted = data.people.sort((a, b) => {
        if (b.source_count !== a.source_count) {
          return b.source_count - a.source_count;
        }
        return (b.confidence || 0) - (a.confidence || 0);
      });
      setPeople(sorted);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              Identified People
            </h1>
            <p className="text-gray-600">
              Review people extracted from obituaries before syncing to Gramps
            </p>
          </div>

          {/* Filters */}
          <div className="flex gap-4 items-end">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Min Confidence
              </label>
              <select
                value={minConfidence}
                onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
                className="block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              >
                <option value={0.50}>50%</option>
                <option value={0.60}>60%</option>
                <option value={0.70}>70%</option>
                <option value={0.80}>80%</option>
                <option value={0.90}>90%</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Min Sources
              </label>
              <select
                value={minSources}
                onChange={(e) => setMinSources(parseInt(e.target.value))}
                className="block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              >
                <option value={1}>1+</option>
                <option value={2}>2+</option>
                <option value={3}>3+</option>
              </select>
            </div>

            <button
              onClick={loadPeople}
              disabled={isLoading}
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
                Failed to load people
              </h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && !people && (
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
          <p className="text-gray-600">Loading people...</p>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && people && people.length === 0 && (
        <div className="bg-white shadow-sm rounded-lg p-12 text-center">
          <svg
            className="mx-auto h-12 w-12 text-gray-400 mb-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
            />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            No people found
          </h3>
          <p className="text-gray-500">
            Try adjusting the confidence or source filters, or process more obituaries.
          </p>
        </div>
      )}

      {/* People Table */}
      {!isLoading && people && people.length > 0 && (
        <>
          <div className="bg-white shadow-sm rounded-lg overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Confidence
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Sources
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Facts
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {people.map((person) => (
                  <tr
                    key={person.person_id}
                    onClick={() => navigate(`/people/${person.person_id}`)}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {person.canonical_name}
                      </div>
                      {person.name_variants && person.name_variants.length > 1 && (
                        <div className="text-xs text-gray-500">
                          +{person.name_variants.length - 1} variant{person.name_variants.length > 2 ? 's' : ''}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <ConfidenceBadge score={person.confidence} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {person.source_count}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {person.fact_count}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <PersonStatusBadge person={person} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Footer Stats */}
          <div className="mt-4 text-sm text-gray-500 text-center">
            Showing {people.length} {people.length === 1 ? 'person' : 'people'}
          </div>
        </>
      )}
    </div>
  );
}
