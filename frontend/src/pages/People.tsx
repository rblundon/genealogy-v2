import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getPersons, deletePerson } from '../services/api';
import type { PersonSummary, SubjectRole, SyncStatus } from '../types';

function RoleBadge({ role }: { role: SubjectRole }) {
  const roleColors: Record<SubjectRole, { bg: string; text: string }> = {
    deceased_primary: { bg: '#1e293b', text: '#ffffff' },
    spouse: { bg: '#7c3aed', text: '#ffffff' },
    child: { bg: '#2563eb', text: '#ffffff' },
    parent: { bg: '#059669', text: '#ffffff' },
    sibling: { bg: '#0891b2', text: '#ffffff' },
    grandchild: { bg: '#6366f1', text: '#ffffff' },
    great_grandchild: { bg: '#8b5cf6', text: '#ffffff' },
    grandparent: { bg: '#16a34a', text: '#ffffff' },
    in_law: { bg: '#ca8a04', text: '#ffffff' },
    other: { bg: '#6b7280', text: '#ffffff' },
  };

  const colors = roleColors[role] || roleColors.other;
  const label = role.replace(/_/g, ' ');

  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        backgroundColor: colors.bg,
        color: colors.text,
        borderRadius: '9999px',
        fontSize: '11px',
        fontWeight: 500,
        textTransform: 'capitalize',
      }}
    >
      {label}
    </span>
  );
}

function SyncBadge({ status }: { status: SyncStatus }) {
  const statusColors: Record<SyncStatus, { bg: string; text: string; label: string }> = {
    pending: { bg: '#fef3c7', text: '#92400e', label: 'Pending' },
    matched: { bg: '#dbeafe', text: '#1e40af', label: 'Matched' },
    created: { bg: '#d1fae5', text: '#065f46', label: 'Created' },
    committed: { bg: '#d1fae5', text: '#065f46', label: 'Synced' },
    rejected: { bg: '#e5e7eb', text: '#374151', label: 'Skipped' },
  };

  const colors = statusColors[status] || statusColors.pending;

  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        backgroundColor: colors.bg,
        color: colors.text,
        borderRadius: '9999px',
        fontSize: '11px',
        fontWeight: 500,
      }}
    >
      {colors.label}
    </span>
  );
}

export function People() {
  const navigate = useNavigate();
  const [persons, setPersons] = useState<PersonSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState<SubjectRole | 'all'>('all');
  const [syncFilter, setSyncFilter] = useState<SyncStatus | 'all'>('all');

  const loadPersons = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getPersons();
      setPersons(data.persons);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load persons');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPersons();
  }, [loadPersons]);

  const handleView = (personName: string) => {
    navigate(`/people/${encodeURIComponent(personName)}`);
  };

  const handleDelete = async (personName: string) => {
    if (!confirm(`Are you sure you want to delete "${personName}" and all their facts?\n\nThis action cannot be undone.`)) {
      return;
    }

    try {
      await deletePerson(personName);
      setPersons(prev => prev.filter(p => p.name !== personName));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete person');
    }
  };

  // Filter persons
  const filteredPersons = persons.filter(person => {
    // Search term filter
    const term = searchTerm.toLowerCase();
    const matchesSearch = person.name.toLowerCase().includes(term);

    // Role filter
    const matchesRole = roleFilter === 'all' || person.primary_role === roleFilter;

    // Sync status filter
    const matchesSync = syncFilter === 'all' || person.sync_status === syncFilter;

    return matchesSearch && matchesRole && matchesSync;
  });

  // Get unique roles for filter
  const uniqueRoles = [...new Set(persons.map(p => p.primary_role))];

  if (loading) {
    return (
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
        <div style={{ textAlign: 'center', padding: '48px', color: '#6b7280' }}>
          Loading people...
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#111827', marginBottom: '8px' }}>
          People
        </h1>
        <p style={{ color: '#6b7280' }}>
          {persons.length} people extracted from obituaries
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

      {/* Filters */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Search by name..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{
            padding: '10px 14px',
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            fontSize: '14px',
            width: '250px',
          }}
        />
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value as SubjectRole | 'all')}
          style={{
            padding: '10px 14px',
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            fontSize: '14px',
            backgroundColor: '#ffffff',
          }}
        >
          <option value="all">All Roles</option>
          {uniqueRoles.map(role => (
            <option key={role} value={role}>
              {role.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
        <select
          value={syncFilter}
          onChange={(e) => setSyncFilter(e.target.value as SyncStatus | 'all')}
          style={{
            padding: '10px 14px',
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            fontSize: '14px',
            backgroundColor: '#ffffff',
          }}
        >
          <option value="all">All Sync Status</option>
          <option value="pending">Pending</option>
          <option value="matched">Matched</option>
          <option value="created">Created</option>
          <option value="committed">Synced</option>
          <option value="rejected">Skipped</option>
        </select>
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
                Role
              </th>
              <th style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 600, color: '#374151' }}>
                Obituaries
              </th>
              <th style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 600, color: '#374151' }}>
                Facts
              </th>
              <th style={{ padding: '12px 16px', textAlign: 'center', fontWeight: 600, color: '#374151' }}>
                Sync Status
              </th>
              <th style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600, color: '#374151' }}>
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {filteredPersons.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ padding: '24px', textAlign: 'center', color: '#6b7280' }}>
                  {searchTerm || roleFilter !== 'all' || syncFilter !== 'all'
                    ? 'No people match your filters'
                    : 'No people found'}
                </td>
              </tr>
            ) : (
              filteredPersons.map((person) => (
                <tr
                  key={person.id}
                  style={{ borderBottom: '1px solid #e5e7eb' }}
                >
                  <td style={{ padding: '12px 16px' }}>
                    <button
                      onClick={() => handleView(person.name)}
                      style={{
                        background: 'none',
                        border: 'none',
                        padding: 0,
                        color: '#2563eb',
                        fontWeight: 500,
                        cursor: 'pointer',
                        textAlign: 'left',
                      }}
                    >
                      {person.name_formatted}
                    </button>
                    {person.gramps_id && (
                      <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '2px' }}>
                        Gramps: {person.gramps_id}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <RoleBadge role={person.primary_role} />
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                    <span style={{ color: '#374151' }}>{person.obituary_count}</span>
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
                      {person.fact_count}
                    </span>
                    {person.unresolved_count > 0 && (
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          backgroundColor: '#fef3c7',
                          color: '#92400e',
                          borderRadius: '9999px',
                          fontSize: '12px',
                          fontWeight: 500,
                          marginLeft: '4px',
                        }}
                      >
                        {person.unresolved_count} unresolved
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                    <SyncBadge status={person.sync_status} />
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                      <button
                        onClick={() => handleView(person.name)}
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
                        onClick={() => handleDelete(person.name)}
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
