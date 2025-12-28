import { useState, useCallback } from 'react';
import type { Fact, FactsResponse, SubjectRole } from '../types';
import { getObituaryFacts, processObituary, updateFactStatus, bulkUpdateFactStatus } from '../services/api';
import { FactClusterCard } from '../components/FactClusterCard';

interface FactCluster {
  subject_name: string;
  subject_role: SubjectRole;
  facts: Fact[];
}

export function Review() {
  const [obituaryId, setObituaryId] = useState<number | null>(null);
  const [obituaryUrl, setObituaryUrl] = useState('');
  const [urlInput, setUrlInput] = useState('');
  const [idInput, setIdInput] = useState('');
  const [clusters, setClusters] = useState<FactCluster[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [processingStatus, setProcessingStatus] = useState<string | null>(null);

  // Group facts by subject name
  const groupFactsBySubject = useCallback((facts: Fact[]): FactCluster[] => {
    const groups: Record<string, FactCluster> = {};

    facts.forEach(fact => {
      if (!groups[fact.subject_name]) {
        groups[fact.subject_name] = {
          subject_name: fact.subject_name,
          subject_role: fact.subject_role,
          facts: [],
        };
      }
      groups[fact.subject_name].facts.push(fact);
    });

    // Sort: deceased_primary first, then by number of facts
    return Object.values(groups).sort((a, b) => {
      if (a.subject_role === 'deceased_primary') return -1;
      if (b.subject_role === 'deceased_primary') return 1;
      return b.facts.length - a.facts.length;
    });
  }, []);

  // Load facts for an obituary
  const loadFacts = useCallback(async (id: number) => {
    setLoading(true);
    setError(null);

    try {
      const response: FactsResponse = await getObituaryFacts(id);
      setObituaryId(response.obituary_id);
      setObituaryUrl(response.url);
      setProcessingStatus(response.processing_status);
      setClusters(groupFactsBySubject(response.facts));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load facts');
      setClusters([]);
    } finally {
      setLoading(false);
    }
  }, [groupFactsBySubject]);

  // Process a new obituary URL
  const handleProcessUrl = async () => {
    if (!urlInput.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const response = await processObituary(urlInput.trim());
      setObituaryId(response.obituary_id);
      setObituaryUrl(response.url);
      setClusters(groupFactsBySubject(response.facts));
      setUrlInput('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process obituary');
    } finally {
      setLoading(false);
    }
  };

  // Load by ID
  const handleLoadById = () => {
    const id = parseInt(idInput);
    if (isNaN(id)) return;
    loadFacts(id);
    setIdInput('');
  };

  // Handle approve/reject - calls API and updates local state
  const handleApprove = async (factId: number) => {
    try {
      await updateFactStatus(factId, 'resolved');
      // Update local state after successful API call
      setClusters(prev =>
        prev.map(cluster => ({
          ...cluster,
          facts: cluster.facts.map(f =>
            f.id === factId ? { ...f, resolution_status: 'resolved' as const } : f
          ),
        }))
      );
    } catch (err) {
      console.error('Failed to approve fact:', err);
      setError(err instanceof Error ? err.message : 'Failed to approve fact');
    }
  };

  const handleReject = async (factId: number) => {
    try {
      await updateFactStatus(factId, 'rejected');
      setClusters(prev =>
        prev.map(cluster => ({
          ...cluster,
          facts: cluster.facts.map(f =>
            f.id === factId ? { ...f, resolution_status: 'rejected' as const } : f
          ),
        }))
      );
    } catch (err) {
      console.error('Failed to reject fact:', err);
      setError(err instanceof Error ? err.message : 'Failed to reject fact');
    }
  };

  const handleApproveAll = async (factIds: number[]) => {
    try {
      await bulkUpdateFactStatus(factIds, 'resolved');
      setClusters(prev =>
        prev.map(cluster => ({
          ...cluster,
          facts: cluster.facts.map(f =>
            factIds.includes(f.id) ? { ...f, resolution_status: 'resolved' as const } : f
          ),
        }))
      );
    } catch (err) {
      console.error('Failed to approve facts:', err);
      setError(err instanceof Error ? err.message : 'Failed to approve facts');
    }
  };

  // Stats
  const totalFacts = clusters.reduce((sum, c) => sum + c.facts.length, 0);
  const unresolvedFacts = clusters.reduce(
    (sum, c) => sum + c.facts.filter(f => f.resolution_status === 'unresolved').length,
    0
  );

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '24px' }}>
      <h1 style={{ fontSize: '24px', fontWeight: 700, marginBottom: '24px', color: '#111827' }}>
        Fact Review
      </h1>

      {/* Input controls */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '16px',
          marginBottom: '24px',
        }}
      >
        {/* Process URL */}
        <div
          style={{
            padding: '16px',
            backgroundColor: '#f9fafb',
            borderRadius: '8px',
            border: '1px solid #e5e7eb',
          }}
        >
          <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
            Process New Obituary URL
          </label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="url"
              value={urlInput}
              onChange={e => setUrlInput(e.target.value)}
              placeholder="https://..."
              style={{
                flex: 1,
                padding: '8px 12px',
                fontSize: '14px',
                border: '1px solid #d1d5db',
                borderRadius: '4px',
              }}
            />
            <button
              onClick={handleProcessUrl}
              disabled={loading || !urlInput.trim()}
              style={{
                padding: '8px 16px',
                fontSize: '14px',
                fontWeight: 500,
                backgroundColor: loading ? '#9ca3af' : '#2563eb',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              {loading ? 'Processing...' : 'Process'}
            </button>
          </div>
        </div>

        {/* Load by ID */}
        <div
          style={{
            padding: '16px',
            backgroundColor: '#f9fafb',
            borderRadius: '8px',
            border: '1px solid #e5e7eb',
          }}
        >
          <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
            Load Existing Obituary by ID
          </label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input
              type="number"
              value={idInput}
              onChange={e => setIdInput(e.target.value)}
              placeholder="Obituary ID"
              style={{
                flex: 1,
                padding: '8px 12px',
                fontSize: '14px',
                border: '1px solid #d1d5db',
                borderRadius: '4px',
              }}
            />
            <button
              onClick={handleLoadById}
              disabled={loading || !idInput}
              style={{
                padding: '8px 16px',
                fontSize: '14px',
                fontWeight: 500,
                backgroundColor: loading ? '#9ca3af' : '#059669',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              Load
            </button>
          </div>
        </div>
      </div>

      {/* Error display */}
      {error && (
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: '#fee2e2',
            color: '#991b1b',
            borderRadius: '8px',
            marginBottom: '16px',
          }}
        >
          {error}
        </div>
      )}

      {/* Current obituary info */}
      {obituaryId && (
        <div
          style={{
            padding: '16px',
            backgroundColor: '#eff6ff',
            borderRadius: '8px',
            marginBottom: '24px',
            border: '1px solid #bfdbfe',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: '14px', color: '#1e40af', fontWeight: 500 }}>
                Obituary #{obituaryId}
              </div>
              <div style={{ fontSize: '13px', color: '#3b82f6', marginTop: '4px' }}>
                <a href={obituaryUrl} target="_blank" rel="noopener noreferrer">
                  {obituaryUrl.length > 80 ? obituaryUrl.substring(0, 80) + '...' : obituaryUrl}
                </a>
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '14px', color: '#374151' }}>
                <strong>{totalFacts}</strong> facts from <strong>{clusters.length}</strong> people
              </div>
              <div style={{ fontSize: '13px', color: '#6b7280' }}>
                <span style={{ color: '#d97706' }}>{unresolvedFacts} unresolved</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '48px', color: '#6b7280' }}>
          Loading...
        </div>
      )}

      {/* Fact clusters */}
      {!loading && clusters.length > 0 && (
        <div>
          {clusters.map(cluster => (
            <FactClusterCard
              key={cluster.subject_name}
              subjectName={cluster.subject_name}
              subjectRole={cluster.subject_role}
              facts={cluster.facts}
              onApprove={handleApprove}
              onReject={handleReject}
              onApproveAll={handleApproveAll}
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && clusters.length === 0 && !error && (
        <div
          style={{
            textAlign: 'center',
            padding: '48px',
            color: '#6b7280',
            backgroundColor: '#f9fafb',
            borderRadius: '8px',
          }}
        >
          <p style={{ marginBottom: '8px' }}>No facts to display.</p>
          <p style={{ fontSize: '14px' }}>
            Enter an obituary URL above to extract facts, or load an existing obituary by ID.
          </p>
        </div>
      )}
    </div>
  );
}
