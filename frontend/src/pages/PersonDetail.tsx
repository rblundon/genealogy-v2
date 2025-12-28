import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  getPersonByName,
  updateFactStatus,
  bulkUpdateFactStatus,
  deletePerson,
} from '../services/api';
import { SyncModal } from '../components/SyncModal';
import { FactCard } from '../components/FactCard';
import type { PersonDetail as PersonDetailType, ObituaryFacts, SyncStatus } from '../types';

function SyncStatusBadge({ status, grampsId }: { status: SyncStatus; grampsId: string | null }) {
  const statusConfig: Record<SyncStatus, { bg: string; text: string; label: string }> = {
    pending: { bg: '#fef3c7', text: '#92400e', label: 'Not synced to Gramps' },
    matched: { bg: '#dbeafe', text: '#1e40af', label: 'Linked to Gramps' },
    created: { bg: '#d1fae5', text: '#065f46', label: 'Created in Gramps' },
    committed: { bg: '#d1fae5', text: '#065f46', label: 'Synced to Gramps' },
    rejected: { bg: '#e5e7eb', text: '#374151', label: 'Skipped' },
  };

  const config = statusConfig[status] || statusConfig.pending;

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        padding: '6px 12px',
        backgroundColor: config.bg,
        color: config.text,
        borderRadius: '6px',
        fontSize: '13px',
        fontWeight: 500,
      }}
    >
      {config.label}
      {grampsId && (
        <span style={{ fontSize: '12px', opacity: 0.8 }}>
          ({grampsId})
        </span>
      )}
    </div>
  );
}

function ObituaryFactsSection({
  obituaryFacts,
  onApprove,
  onReject,
  onApproveAll,
}: {
  obituaryFacts: ObituaryFacts;
  onApprove: (factId: number) => void;
  onReject: (factId: number) => void;
  onApproveAll: (factIds: number[]) => void;
}) {
  const [expanded, setExpanded] = useState(true);

  const unresolvedFacts = obituaryFacts.facts.filter(f => f.resolution_status === 'unresolved');
  const resolvedCount = obituaryFacts.facts.filter(f => f.resolution_status === 'resolved').length;

  return (
    <div
      style={{
        backgroundColor: '#ffffff',
        borderRadius: '8px',
        border: '1px solid #e5e7eb',
        marginBottom: '16px',
      }}
    >
      <div
        style={{
          padding: '16px',
          borderBottom: expanded ? '1px solid #e5e7eb' : 'none',
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '16px', color: expanded ? '#111827' : '#6b7280' }}>
              {expanded ? '▼' : '▶'}
            </span>
            <span style={{ fontWeight: 600, color: '#111827' }}>
              Obituary #{obituaryFacts.obituary_id}
            </span>
            <span
              style={{
                padding: '2px 8px',
                backgroundColor: '#e0e7ff',
                color: '#3730a3',
                borderRadius: '9999px',
                fontSize: '12px',
                fontWeight: 500,
              }}
            >
              {obituaryFacts.facts.length} facts
            </span>
            {resolvedCount > 0 && (
              <span
                style={{
                  padding: '2px 8px',
                  backgroundColor: '#d1fae5',
                  color: '#065f46',
                  borderRadius: '9999px',
                  fontSize: '12px',
                  fontWeight: 500,
                }}
              >
                {resolvedCount} resolved
              </span>
            )}
          </div>
          <a
            href={obituaryFacts.obituary_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            style={{
              fontSize: '12px',
              color: '#2563eb',
              textDecoration: 'none',
              marginTop: '4px',
              display: 'block',
              maxWidth: '500px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {obituaryFacts.obituary_url}
          </a>
        </div>

        {unresolvedFacts.length > 1 && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onApproveAll(unresolvedFacts.map(f => f.id));
            }}
            style={{
              padding: '6px 12px',
              backgroundColor: '#059669',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            Approve All ({unresolvedFacts.length})
          </button>
        )}
      </div>

      {expanded && (
        <div style={{ padding: '16px' }}>
          {obituaryFacts.facts.map((fact) => (
            <FactCard
              key={fact.id}
              fact={fact}
              onApprove={onApprove}
              onReject={onReject}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function PersonDetail() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const decodedName = name ? decodeURIComponent(name) : '';

  const [person, setPerson] = useState<PersonDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showSyncModal, setShowSyncModal] = useState(false);

  const loadPerson = useCallback(async () => {
    if (!decodedName) return;

    try {
      setLoading(true);
      setError(null);
      const data = await getPersonByName(decodedName);
      setPerson(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load person');
    } finally {
      setLoading(false);
    }
  }, [decodedName]);

  useEffect(() => {
    loadPerson();
  }, [loadPerson]);

  const handleApprove = async (factId: number) => {
    try {
      await updateFactStatus(factId, 'resolved');
      // Update local state
      setPerson(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          obituary_facts: prev.obituary_facts.map(of => ({
            ...of,
            facts: of.facts.map(f =>
              f.id === factId ? { ...f, resolution_status: 'resolved' as const } : f
            ),
          })),
        };
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve fact');
    }
  };

  const handleReject = async (factId: number) => {
    try {
      await updateFactStatus(factId, 'rejected');
      setPerson(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          obituary_facts: prev.obituary_facts.map(of => ({
            ...of,
            facts: of.facts.map(f =>
              f.id === factId ? { ...f, resolution_status: 'rejected' as const } : f
            ),
          })),
        };
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reject fact');
    }
  };

  const handleApproveAll = async (factIds: number[]) => {
    try {
      await bulkUpdateFactStatus(factIds, 'resolved');
      setPerson(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          obituary_facts: prev.obituary_facts.map(of => ({
            ...of,
            facts: of.facts.map(f =>
              factIds.includes(f.id) ? { ...f, resolution_status: 'resolved' as const } : f
            ),
          })),
        };
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve facts');
    }
  };

  const handleSyncComplete = () => {
    setShowSyncModal(false);
    loadPerson(); // Reload to get updated sync status
  };

  const handleDelete = async () => {
    if (!person) return;

    if (!confirm(`Are you sure you want to delete "${person.name}" and all their facts?\n\nThis action cannot be undone.`)) {
      return;
    }

    try {
      await deletePerson(person.name);
      navigate('/people');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete person');
    }
  };

  if (loading) {
    return (
      <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '24px' }}>
        <div style={{ textAlign: 'center', padding: '48px', color: '#6b7280' }}>
          Loading person details...
        </div>
      </div>
    );
  }

  if (error || !person) {
    return (
      <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '24px' }}>
        <div
          style={{
            padding: '16px',
            backgroundColor: '#fee2e2',
            color: '#991b1b',
            borderRadius: '8px',
          }}
        >
          {error || 'Person not found'}
        </div>
        <button
          onClick={() => navigate('/people')}
          style={{
            marginTop: '16px',
            padding: '8px 16px',
            backgroundColor: '#6b7280',
            color: '#ffffff',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
          }}
        >
          Back to People
        </button>
      </div>
    );
  }

  const totalFacts = person.obituary_facts.reduce((sum, of) => sum + of.facts.length, 0);
  const resolvedFacts = person.obituary_facts.reduce(
    (sum, of) => sum + of.facts.filter(f => f.resolution_status === 'resolved').length,
    0
  );
  const unresolvedFacts = person.obituary_facts.reduce(
    (sum, of) => sum + of.facts.filter(f => f.resolution_status === 'unresolved').length,
    0
  );

  const canSync = person.sync_status === 'pending' || person.sync_status === 'rejected';

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '24px' }}>
      {/* Breadcrumb */}
      <div style={{ marginBottom: '16px' }}>
        <Link
          to="/people"
          style={{
            color: '#6b7280',
            textDecoration: 'none',
            fontSize: '14px',
          }}
        >
          People
        </Link>
        <span style={{ color: '#6b7280', margin: '0 8px' }}>/</span>
        <span style={{ color: '#111827', fontSize: '14px' }}>{person.name}</span>
      </div>

      {/* Header */}
      <div
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '8px',
          border: '1px solid #e5e7eb',
          padding: '24px',
          marginBottom: '24px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 style={{ fontSize: '28px', fontWeight: 700, color: '#111827', marginBottom: '8px' }}>
              {person.name_formatted}
            </h1>
            <div style={{ display: 'flex', gap: '16px', color: '#6b7280', fontSize: '14px' }}>
              <span>
                <strong>{person.obituary_facts.length}</strong> obituaries
              </span>
              <span>
                <strong>{totalFacts}</strong> facts
              </span>
              <span style={{ color: '#059669' }}>
                <strong>{resolvedFacts}</strong> resolved
              </span>
              {unresolvedFacts > 0 && (
                <span style={{ color: '#d97706' }}>
                  <strong>{unresolvedFacts}</strong> unresolved
                </span>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '12px' }}>
            <SyncStatusBadge status={person.sync_status} grampsId={person.gramps_id} />

            <div style={{ display: 'flex', gap: '8px' }}>
              {canSync && (
                <button
                  onClick={() => setShowSyncModal(true)}
                  style={{
                    padding: '10px 20px',
                    backgroundColor: '#2563eb',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '6px',
                    fontSize: '14px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Sync to Gramps
                </button>
              )}
              <button
                onClick={handleDelete}
                style={{
                  padding: '10px 20px',
                  backgroundColor: '#dc2626',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      </div>

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
          <button
            onClick={() => setError(null)}
            style={{
              marginLeft: '8px',
              background: 'none',
              border: 'none',
              color: '#991b1b',
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Facts by Obituary */}
      <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#111827', marginBottom: '16px' }}>
        Facts by Obituary
      </h2>

      {person.obituary_facts.length === 0 ? (
        <div
          style={{
            padding: '24px',
            backgroundColor: '#f9fafb',
            borderRadius: '8px',
            textAlign: 'center',
            color: '#6b7280',
          }}
        >
          No facts found for this person.
        </div>
      ) : (
        person.obituary_facts.map((of) => (
          <ObituaryFactsSection
            key={of.obituary_id}
            obituaryFacts={of}
            onApprove={handleApprove}
            onReject={handleReject}
            onApproveAll={handleApproveAll}
          />
        ))
      )}

      {/* Sync Modal */}
      {showSyncModal && (
        <SyncModal
          personName={person.name}
          onClose={() => setShowSyncModal(false)}
          onSyncComplete={handleSyncComplete}
        />
      )}
    </div>
  );
}
