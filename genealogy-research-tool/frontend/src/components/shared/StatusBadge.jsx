export function StatusBadge({ status }) {
  const config = {
    completed: {
      label: 'Complete',
      icon: '✓',
      className: 'bg-green-100 text-green-800',
    },
    failed: {
      label: 'Failed',
      icon: '✗',
      className: 'bg-red-100 text-red-800',
    },
    processing: {
      label: 'Processing',
      icon: '⟳',
      className: 'bg-blue-100 text-blue-800',
    },
    pending: {
      label: 'Pending',
      icon: '⋯',
      className: 'bg-yellow-100 text-yellow-800',
    },
  };

  const { label, icon, className } = config[status] || config.pending;

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${className}`}>
      <span className="mr-1">{icon}</span>
      {label}
    </span>
  );
}
