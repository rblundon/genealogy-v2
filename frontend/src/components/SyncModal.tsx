import { useState, useEffect, useCallback } from 'react';
import { getGrampsMatches, syncPerson, skipPersonSync } from '../services/api';
import type { GrampsMatch } from '../types';

interface SyncModalProps {
  personName: string;
  onClose: () => void;
  onSyncComplete: () => void;
}

function MatchScoreBadge({ score }: { score: number }) {
  let bg: string;
  let text: string;

  if (score >= 0.85) {
    bg = '#d1fae5';
    text = '#065f46';
  } else if (score >= 0.60) {
    bg = '#fef3c7';
    text = '#92400e';
  } else {
    bg = '#fee2e2';
    text = '#991b1b';
  }

  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        backgroundColor: bg,
        color: text,
        borderRadius: '9999px',
        fontSize: '12px',
        fontWeight: 600,
      }}
    >
      {Math.round(score * 100)}%
    </span>
  );
}

export function SyncModal({ personName, onClose, onSyncComplete }: SyncModalProps) {
  const [matches, setMatches] = useState<GrampsMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [selectedHandle, setSelectedHandle] = useState<string | null>(null);
  const [createNew, setCreateNew] = useState(false);
  const [includeRelationships, setIncludeRelationships] = useState(true);

  const loadMatches = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getGrampsMatches(personName);
      setMatches(data.matches);

      // Auto-select if there's a high-confidence match
      if (data.matches.length > 0 && data.matches[0].score >= 0.85) {
        setSelectedHandle(data.matches[0].handle);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load matches');
    } finally {
      setLoading(false);
    }
  }, [personName]);

  useEffect(() => {
    loadMatches();
  }, [loadMatches]);

  const handleSync = async () => {
    if (!selectedHandle && !createNew) {
      setError('Please select a match or choose to create a new person');
      return;
    }

    try {
      setSyncing(true);
      setError(null);

      await syncPerson(personName, {
        gramps_handle: createNew ? undefined : selectedHandle || undefined,
        create_new: createNew,
        include_relationships: includeRelationships,
      });

      onSyncComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sync failed');
      setSyncing(false);
    }
  };

  const handleSkip = async () => {
    try {
      setSyncing(true);
      await skipPersonSync(personName);
      onSyncComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to skip');
      setSyncing(false);
    }
  };

  const handleSelectMatch = (handle: string) => {
    setSelectedHandle(handle);
    setCreateNew(false);
  };

  const handleCreateNew = () => {
    setSelectedHandle(null);
    setCreateNew(true);
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '12px',
          width: '100%',
          maxWidth: '600px',
          maxHeight: '80vh',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid #e5e7eb',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <h2 style={{ fontSize: '20px', fontWeight: 700, color: '#111827', marginBottom: '4px' }}>
              Sync to Gramps
            </h2>
            <p style={{ fontSize: '14px', color: '#6b7280' }}>
              Link <strong>{personName}</strong> to an existing Gramps person or create a new one.
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '24px',
              color: '#6b7280',
              cursor: 'pointer',
              padding: '4px',
            }}
          >
            x
          </button>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
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

          {loading ? (
            <div style={{ textAlign: 'center', padding: '24px', color: '#6b7280' }}>
              Searching for matches in Gramps...
            </div>
          ) : (
            <>
              {/* Matches */}
              <div style={{ marginBottom: '24px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#111827', marginBottom: '12px' }}>
                  Potential Matches ({matches.length})
                </h3>

                {matches.length === 0 ? (
                  <div
                    style={{
                      padding: '16px',
                      backgroundColor: '#f9fafb',
                      borderRadius: '8px',
                      color: '#6b7280',
                      textAlign: 'center',
                    }}
                  >
                    No matching people found in Gramps. You can create a new person below.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {matches.map((match) => (
                      <div
                        key={match.handle}
                        onClick={() => handleSelectMatch(match.handle)}
                        style={{
                          padding: '12px 16px',
                          backgroundColor: selectedHandle === match.handle ? '#eff6ff' : '#ffffff',
                          border: `2px solid ${selectedHandle === match.handle ? '#2563eb' : '#e5e7eb'}`,
                          borderRadius: '8px',
                          cursor: 'pointer',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 500, color: '#111827' }}>
                            {match.name}
                          </div>
                          <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '2px' }}>
                            ID: {match.gramps_id} | Handle: {match.handle}
                          </div>
                        </div>
                        <MatchScoreBadge score={match.score} />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Create New Option */}
              <div style={{ marginBottom: '24px' }}>
                <div
                  onClick={handleCreateNew}
                  style={{
                    padding: '12px 16px',
                    backgroundColor: createNew ? '#f0fdf4' : '#ffffff',
                    border: `2px solid ${createNew ? '#22c55e' : '#e5e7eb'}`,
                    borderRadius: '8px',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ fontWeight: 500, color: createNew ? '#166534' : '#111827' }}>
                    Create New Person in Gramps
                  </div>
                  <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '2px' }}>
                    This will create a new person record with the name "{personName}"
                  </div>
                </div>
              </div>

              {/* Options */}
              <div style={{ marginBottom: '16px' }}>
                <label
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '14px',
                    color: '#374151',
                    cursor: 'pointer',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={includeRelationships}
                    onChange={(e) => setIncludeRelationships(e.target.checked)}
                    style={{ width: '16px', height: '16px' }}
                  />
                  Include family relationships
                  <span style={{ fontSize: '12px', color: '#6b7280' }}>
                    (will create family records if related people are also synced)
                  </span>
                </label>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '16px 24px',
            borderTop: '1px solid #e5e7eb',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <button
            onClick={handleSkip}
            disabled={syncing}
            style={{
              padding: '10px 16px',
              backgroundColor: '#e5e7eb',
              color: '#374151',
              border: 'none',
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: 500,
              cursor: syncing ? 'not-allowed' : 'pointer',
            }}
          >
            Skip Sync
          </button>

          <div style={{ display: 'flex', gap: '12px' }}>
            <button
              onClick={onClose}
              disabled={syncing}
              style={{
                padding: '10px 16px',
                backgroundColor: '#ffffff',
                color: '#374151',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: 500,
                cursor: syncing ? 'not-allowed' : 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleSync}
              disabled={syncing || (!selectedHandle && !createNew)}
              style={{
                padding: '10px 20px',
                backgroundColor:
                  syncing || (!selectedHandle && !createNew) ? '#9ca3af' : '#2563eb',
                color: '#ffffff',
                border: 'none',
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: 600,
                cursor:
                  syncing || (!selectedHandle && !createNew) ? 'not-allowed' : 'pointer',
              }}
            >
              {syncing ? 'Syncing...' : createNew ? 'Create & Sync' : 'Link & Sync'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
