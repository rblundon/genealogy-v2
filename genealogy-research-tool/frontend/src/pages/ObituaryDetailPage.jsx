import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { getObituaryStatus, getObituaryFacts, deleteObituary, reprocessObituary } from '../api/client';
import { StatusBadge } from '../components/shared/StatusBadge';
import { ConfirmDialog } from '../components/shared/ConfirmDialog';
import { ExpandableSection } from '../components/shared/ExpandableSection';
import { extractNameFromURL, formatRelativeTime } from '../utils/formatters';

export function ObituaryDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [obituary, setObituary] = useState(null);
  const [facts, setFacts] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isReprocessing, setIsReprocessing] = useState(false);

  useEffect(() => {
    loadData();
  }, [id]);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const [obituaryData, factsData] = await Promise.all([
        getObituaryStatus(id),
        getObituaryFacts(id),
      ]);

      setObituary(obituaryData);
      setFacts(factsData);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);

    try {
      await deleteObituary(id);
      navigate('/obituaries');
    } catch (err) {
      alert(`Failed to delete: ${err.message}`);
      setIsDeleting(false);
      setShowDeleteDialog(false);
    }
  };

  const handleReprocess = async () => {
    setIsReprocessing(true);

    try {
      await reprocessObituary(id);
      await loadData();
    } catch (err) {
      alert(`Failed to reprocess: ${err.message}`);
    } finally {
      setIsReprocessing(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
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
          <p className="text-gray-600">Loading obituary details...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <Link
          to="/obituaries"
          className="inline-flex items-center text-sm text-blue-600 hover:text-blue-700 mb-6"
        >
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Obituaries
        </Link>

        <div className="bg-red-50 border border-red-200 rounded-md p-6">
          <div className="flex">
            <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Failed to load obituary</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!obituary) return null;

  const name = extractNameFromURL(obituary.url);

  return (
    <div>
      {/* Back Link */}
      <div className="mb-6">
        <Link
          to="/obituaries"
          className="inline-flex items-center text-sm text-blue-600 hover:text-blue-700"
        >
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Obituaries
        </Link>
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-3">
          {name}
        </h1>
        <div className="flex items-center gap-3 text-sm text-gray-600">
          <StatusBadge status={obituary.processing_status} />
          <span>•</span>
          <span>Processed {formatRelativeTime(obituary.fetch_timestamp)}</span>
        </div>
      </div>

      {/* Stats Card */}
      <div className="bg-white shadow-sm rounded-lg p-6 mb-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <div className="text-2xl font-bold text-gray-900">
              {obituary.persons_extracted || 0}
            </div>
            <div className="text-sm text-gray-500">People</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-gray-900">
              {facts?.fact_count || 0}
            </div>
            <div className="text-sm text-gray-500">Facts</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-gray-900">
              ${obituary.llm_cost_usd?.toFixed(2) || '0.00'}
            </div>
            <div className="text-sm text-gray-500">Cost</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-gray-900">
              {obituary.http_status_code || '—'}
            </div>
            <div className="text-sm text-gray-500">HTTP Status</div>
          </div>
        </div>

        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="text-sm text-gray-500 mb-1">URL:</div>
          <a
            href={obituary.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:text-blue-700 break-all"
          >
            {obituary.url}
          </a>
        </div>
      </div>

      {/* Extracted Text */}
      {obituary.extracted_text && (
        <div className="mb-6">
          <ExpandableSection
            title="Extracted Text"
            previewContent={
              <p className="whitespace-pre-wrap">
                {obituary.extracted_text.slice(0, 500)}
                {obituary.extracted_text.length > 500 && '...'}
              </p>
            }
            fullContent={
              <p className="whitespace-pre-wrap">{obituary.extracted_text}</p>
            }
          />
        </div>
      )}

      {/* Extracted Facts */}
      {facts && facts.facts && facts.facts.length > 0 && (
        <div className="mb-6">
          <ExpandableSection
            title={`Extracted Facts (${facts.fact_count})`}
            previewContent={
              <ul className="space-y-2">
                {facts.facts.slice(0, 5).map((fact, index) => (
                  <li key={index} className="flex items-start">
                    <span className="text-gray-400 mr-2">•</span>
                    <span>
                      {fact.description || `${fact.fact_type}: ${fact.fact_value}`}
                      {fact.confidence_score && fact.confidence_score < 1.0 && (
                        <span className="ml-2 text-xs text-gray-500">
                          ({(fact.confidence_score * 100).toFixed(0)}%)
                        </span>
                      )}
                      {fact.is_inferred && (
                        <span className="ml-2 text-xs text-amber-600">(inferred)</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            }
            fullContent={
              <ul className="space-y-2">
                {facts.facts.map((fact, index) => (
                  <li key={index} className="flex items-start">
                    <span className="text-gray-400 mr-2">•</span>
                    <span>
                      {fact.description || `${fact.fact_type}: ${fact.fact_value}`}
                      {fact.confidence_score && fact.confidence_score < 1.0 && (
                        <span className="ml-2 text-xs text-gray-500">
                          ({(fact.confidence_score * 100).toFixed(0)}%)
                        </span>
                      )}
                      {fact.is_inferred && (
                        <span className="ml-2 text-xs text-amber-600">(inferred)</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            }
          />
        </div>
      )}

      {/* Actions */}
      <div className="bg-white shadow-sm rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Actions</h3>
        <div className="flex gap-3">
          <button
            onClick={handleReprocess}
            disabled={isReprocessing}
            className="inline-flex items-center px-4 py-2 border border-blue-300 rounded-md text-sm font-medium text-blue-700 bg-white hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {isReprocessing ? 'Reprocessing...' : 'Reprocess Obituary'}
          </button>
          <button
            onClick={() => setShowDeleteDialog(true)}
            disabled={isDeleting}
            className="inline-flex items-center px-4 py-2 border border-red-300 rounded-md text-sm font-medium text-red-700 bg-white hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            {isDeleting ? 'Deleting...' : 'Delete Obituary'}
          </button>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showDeleteDialog}
        title="Delete Obituary?"
        message="This will permanently delete this obituary and all extracted facts. This action cannot be undone."
        confirmText="Delete"
        cancelText="Cancel"
        isDanger={true}
        onConfirm={handleDelete}
        onCancel={() => setShowDeleteDialog(false)}
      />
    </div>
  );
}
