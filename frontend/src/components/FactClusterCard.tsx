import { useState } from 'react';
import type { Fact, SubjectRole } from '../types';
import { RoleBadge } from './StatusBadge';
import { FactCard } from './FactCard';

interface FactClusterCardProps {
  subjectName: string;
  subjectRole: SubjectRole;
  facts: Fact[];
  onApprove?: (factId: number) => void;
  onReject?: (factId: number) => void;
  onApproveAll?: (factIds: number[]) => void;
}

export function FactClusterCard({
  subjectName,
  subjectRole,
  facts,
  onApprove,
  onReject,
  onApproveAll,
}: FactClusterCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  const unresolvedCount = facts.filter(f => f.resolution_status === 'unresolved').length;
  const resolvedCount = facts.filter(f => f.resolution_status === 'resolved').length;
  const avgConfidence = facts.reduce((sum, f) => sum + f.confidence_score, 0) / facts.length;

  const unresolvedFactIds = facts
    .filter(f => f.resolution_status === 'unresolved')
    .map(f => f.id);

  return (
    <div
      style={{
        backgroundColor: '#ffffff',
        borderRadius: '8px',
        border: '1px solid #e5e7eb',
        marginBottom: '16px',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '16px',
          backgroundColor: subjectRole === 'deceased_primary' ? '#f1f5f9' : '#ffffff',
          borderBottom: '1px solid #e5e7eb',
          cursor: 'pointer',
        }}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '18px', fontWeight: 600, color: '#111827' }}>
              {subjectName}
            </span>
            <RoleBadge role={subjectRole} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ fontSize: '13px', color: '#6b7280' }}>
              <span style={{ color: '#059669', fontWeight: 500 }}>{resolvedCount}</span>
              {' / '}
              <span style={{ color: '#d97706', fontWeight: 500 }}>{unresolvedCount}</span>
              {' / '}
              {facts.length} facts
            </div>
            <div
              style={{
                fontSize: '12px',
                padding: '2px 8px',
                borderRadius: '4px',
                backgroundColor: avgConfidence >= 0.85 ? '#d1fae5' : avgConfidence >= 0.6 ? '#fef3c7' : '#fee2e2',
                color: avgConfidence >= 0.85 ? '#065f46' : avgConfidence >= 0.6 ? '#92400e' : '#991b1b',
                fontFamily: 'monospace',
              }}
            >
              avg {Math.round(avgConfidence * 100)}%
            </div>
            <span style={{ color: '#9ca3af', fontSize: '18px' }}>
              {isExpanded ? '▼' : '▶'}
            </span>
          </div>
        </div>
      </div>

      {/* Facts list */}
      {isExpanded && (
        <div style={{ padding: '16px' }}>
          {/* Bulk actions */}
          {unresolvedCount > 1 && onApproveAll && (
            <div style={{ marginBottom: '12px', display: 'flex', gap: '8px' }}>
              <button
                onClick={() => onApproveAll(unresolvedFactIds)}
                style={{
                  padding: '8px 16px',
                  fontSize: '13px',
                  fontWeight: 500,
                  backgroundColor: '#059669',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                }}
              >
                Approve All ({unresolvedCount})
              </button>
            </div>
          )}

          {facts.map(fact => (
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
