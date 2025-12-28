import type { Fact } from '../types';
import { StatusBadge, ConfidenceBadge } from './StatusBadge';

interface FactCardProps {
  fact: Fact;
  onApprove?: (factId: number) => void;
  onReject?: (factId: number) => void;
  showSubject?: boolean;
}

const factTypeLabels: Record<string, string> = {
  person_name: 'Name',
  person_death_date: 'Death Date',
  person_death_age: 'Age at Death',
  person_birth_date: 'Birth Date',
  person_gender: 'Gender',
  maiden_name: 'Maiden Name',
  relationship: 'Relationship',
  marriage: 'Marriage',
  location_birth: 'Birth Location',
  location_death: 'Death Location',
  location_residence: 'Residence',
  survived_by: 'Survived By',
  preceded_in_death: 'Preceded in Death',
};

export function FactCard({ fact, onApprove, onReject, showSubject = false }: FactCardProps) {
  const isRelationship = fact.fact_type === 'relationship' ||
                         fact.fact_type === 'survived_by' ||
                         fact.fact_type === 'preceded_in_death';

  return (
    <div
      style={{
        padding: '12px',
        backgroundColor: fact.is_inferred ? '#fffbeb' : '#ffffff',
        borderRadius: '6px',
        border: '1px solid #e5e7eb',
        marginBottom: '8px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontWeight: 600, color: '#374151', fontSize: '13px' }}>
            {factTypeLabels[fact.fact_type] || fact.fact_type}
          </span>
          <ConfidenceBadge score={fact.confidence_score} />
          {fact.is_inferred && (
            <span style={{ fontSize: '11px', color: '#d97706', fontStyle: 'italic' }}>
              inferred
            </span>
          )}
        </div>
        <StatusBadge status={fact.resolution_status} />
      </div>

      {showSubject && (
        <div style={{ fontSize: '12px', color: '#6b7280', marginBottom: '4px' }}>
          Subject: <strong>{fact.subject_name}</strong>
        </div>
      )}

      <div style={{ fontSize: '14px', color: '#111827', marginBottom: '8px' }}>
        {isRelationship && fact.related_name ? (
          <>
            <strong>{fact.fact_value}</strong>
            <span style={{ color: '#6b7280' }}> of </span>
            <strong>{fact.related_name}</strong>
            {fact.relationship_type && (
              <span style={{ color: '#6b7280' }}> ({fact.relationship_type})</span>
            )}
          </>
        ) : (
          <strong>{fact.fact_value}</strong>
        )}
      </div>

      {fact.extracted_context && (
        <div
          style={{
            fontSize: '12px',
            color: '#6b7280',
            fontStyle: 'italic',
            backgroundColor: '#f9fafb',
            padding: '6px 8px',
            borderRadius: '4px',
            borderLeft: '3px solid #d1d5db',
          }}
        >
          "{fact.extracted_context}"
        </div>
      )}

      {fact.is_inferred && fact.inference_basis && (
        <div style={{ fontSize: '11px', color: '#d97706', marginTop: '6px' }}>
          Inference: {fact.inference_basis}
        </div>
      )}

      {fact.resolution_status === 'unresolved' && (onApprove || onReject) && (
        <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
          {onApprove && (
            <button
              onClick={() => onApprove(fact.id)}
              style={{
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: 500,
                backgroundColor: '#059669',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Approve
            </button>
          )}
          {onReject && (
            <button
              onClick={() => onReject(fact.id)}
              style={{
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: 500,
                backgroundColor: '#dc2626',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              Reject
            </button>
          )}
        </div>
      )}
    </div>
  );
}
