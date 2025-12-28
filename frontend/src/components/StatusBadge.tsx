import type { ResolutionStatus, SubjectRole } from '../types';

interface StatusBadgeProps {
  status: ResolutionStatus;
}

const statusColors: Record<ResolutionStatus, { bg: string; text: string }> = {
  unresolved: { bg: '#fef3c7', text: '#92400e' },
  resolved: { bg: '#d1fae5', text: '#065f46' },
  conflicting: { bg: '#fee2e2', text: '#991b1b' },
  rejected: { bg: '#e5e7eb', text: '#374151' },
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const colors = statusColors[status];
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: '9999px',
        fontSize: '12px',
        fontWeight: 500,
        backgroundColor: colors.bg,
        color: colors.text,
      }}
    >
      {status}
    </span>
  );
}

interface RoleBadgeProps {
  role: SubjectRole;
}

const roleColors: Record<SubjectRole, { bg: string; text: string }> = {
  deceased_primary: { bg: '#1e293b', text: '#f8fafc' },
  spouse: { bg: '#7c3aed', text: '#ffffff' },
  child: { bg: '#2563eb', text: '#ffffff' },
  parent: { bg: '#059669', text: '#ffffff' },
  sibling: { bg: '#0891b2', text: '#ffffff' },
  grandchild: { bg: '#4f46e5', text: '#ffffff' },
  great_grandchild: { bg: '#6366f1', text: '#ffffff' },
  grandparent: { bg: '#16a34a', text: '#ffffff' },
  in_law: { bg: '#9333ea', text: '#ffffff' },
  other: { bg: '#6b7280', text: '#ffffff' },
};

export function RoleBadge({ role }: RoleBadgeProps) {
  const colors = roleColors[role] || roleColors.other;
  const label = role.replace(/_/g, ' ');
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 8px',
        borderRadius: '9999px',
        fontSize: '11px',
        fontWeight: 500,
        backgroundColor: colors.bg,
        color: colors.text,
        textTransform: 'capitalize',
      }}
    >
      {label}
    </span>
  );
}

interface ConfidenceBadgeProps {
  score: number;
}

export function ConfidenceBadge({ score }: ConfidenceBadgeProps) {
  const percent = Math.round(score * 100);
  let bg = '#d1fae5';
  let text = '#065f46';

  if (score < 0.6) {
    bg = '#fee2e2';
    text = '#991b1b';
  } else if (score < 0.85) {
    bg = '#fef3c7';
    text = '#92400e';
  }

  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 6px',
        borderRadius: '4px',
        fontSize: '11px',
        fontWeight: 600,
        backgroundColor: bg,
        color: text,
        fontFamily: 'monospace',
      }}
    >
      {percent}%
    </span>
  );
}
