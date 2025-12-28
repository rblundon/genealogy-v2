import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getObituaries, deleteObituary, reprocessObituary } from '../services/api';
import type { ObituarySummary } from '../types';

export function Obituaries() {
  const navigate = useNavigate();
  const [obituaries, setObituaries] = useState<ObituarySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  const loadObituaries = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getObituaries();
      setObituaries(data.obituaries);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load obituaries');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadObituaries();
  }, [loadObituaries]);

  const handleView = (obituaryId: number) => {
    navigate(`/review?id=${obituaryId}`);
  };

  const handleReprocess = async (obituaryId: number) => {
    if (!confirm('Are you sure you want to reprocess this obituary? Existing facts will be deleted.')) {
      return;
    }

    try {
      setProcessingId(obituaryId);
      await reprocessObituary(obituaryId);
      await loadObituaries();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reprocess obituary');
    } finally {
      setProcessingId(null);
    }
  };

  const handleDelete = async (obituaryId: number, url: string) => {
    if (!confirm(`Are you sure you want to delete this obituary?\n\n${url}\n\nThis will also delete all associated facts.`)) {
      return;
    }

    try {
      await deleteObituary(obituaryId);
      setObituaries(prev => prev.filter(o => o.id !== obituaryId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete obituary');
    }
  };

  // Filter obituaries by search term
  const filteredObituaries = obituaries.filter(obit => {
    const term = searchTerm.toLowerCase();
    return (
      obit.primary_name.toLowerCase().includes(term) ||
      obit.url.toLowerCase().includes(term)
    );
  });

  if (loading) {
    return (
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
        <div style={{ textAlign: 'center', padding: '48px', color: '#6b7280' }}>
          Loading obituaries...
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#111827', marginBottom: '8px' }}>
          Obituaries
        </h1>
        <p style={{ color: '#6b7280' }}>
          {obituaries.length} processed obituaries
        </p>
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
        </div>
      )}

      {/* Search */}
      <div style={{ marginBottom: '16px' }}>
        <input
          type="text"
          placeholder="Search by name or URL..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{
            width: '100%',
            maxWidth: '400px',
            padding: '10px 14px',
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            fontSize: '14px',
          }}
        />
      </div>

      {/* Table */}
      <div
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '8px',
          border: '1px solid #e5e7eb',
          overflow: 'hidden',
        }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
              <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#374151' }}>
                Name
              </th>
              <th style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: '#374151' }}>
                URL
              </th>
              <th style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 600, color: '#374151' }}>
                Facts
              </th>
              <th style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 600, color: '#374151' }}>
                Unresolved
              </th>
              <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#374151' }}>
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {filteredObituaries.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: '24px', textAlign: 'center', color: '#6b7280' }}>
                  {searchTerm ? 'No obituaries match your search' : 'No obituaries found'}
                </td>
              </tr>
            ) : (
              filteredObituaries.map((obit) => (
                <tr
                  key={obit.id}
                  style={{ borderBottom: '1px solid #e5e7eb' }}
                >
                  <td style={{ padding: '12px 16px' }}>
                    <span style={{ fontWeight: 500, color: '#111827' }}>
                      {obit.primary_name_formatted}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <a
                      href={obit.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        color: '#2563eb',
                        textDecoration: 'none',
                        fontSize: '14px',
                        maxWidth: '300px',
                        display: 'block',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={obit.url}
                    >
                      {obit.url}
                    </a>
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        backgroundColor: '#e0e7ff',
                        color: '#3730a3',
                        borderRadius: '9999px',
                        fontSize: '12px',
                        fontWeight: 500,
                      }}
                    >
                      {obit.fact_count}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                    {obit.unresolved_count > 0 ? (
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          backgroundColor: '#fef3c7',
                          color: '#92400e',
                          borderRadius: '9999px',
                          fontSize: '12px',
                          fontWeight: 500,
                        }}
                      >
                        {obit.unresolved_count}
                      </span>
                    ) : (
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          backgroundColor: '#d1fae5',
                          color: '#065f46',
                          borderRadius: '9999px',
                          fontSize: '12px',
                          fontWeight: 500,
                        }}
                      >
                        0
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                      <button
                        onClick={() => handleView(obit.id)}
                        style={{
                          padding: '6px 12px',
                          backgroundColor: '#2563eb',
                          color: '#ffffff',
                          border: 'none',
                          borderRadius: '6px',
                          fontSize: '13px',
                          fontWeight: 500,
                          cursor: 'pointer',
                        }}
                      >
                        View
                      </button>
                      <button
                        onClick={() => handleReprocess(obit.id)}
                        disabled={processingId === obit.id}
                        style={{
                          padding: '6px 12px',
                          backgroundColor: processingId === obit.id ? '#9ca3af' : '#f59e0b',
                          color: '#ffffff',
                          border: 'none',
                          borderRadius: '6px',
                          fontSize: '13px',
                          fontWeight: 500,
                          cursor: processingId === obit.id ? 'not-allowed' : 'pointer',
                        }}
                      >
                        {processingId === obit.id ? 'Processing...' : 'Reprocess'}
                      </button>
                      <button
                        onClick={() => handleDelete(obit.id, obit.url)}
                        style={{
                          padding: '6px 12px',
                          backgroundColor: '#dc2626',
                          color: '#ffffff',
                          border: 'none',
                          borderRadius: '6px',
                          fontSize: '13px',
                          fontWeight: 500,
                          cursor: 'pointer',
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
