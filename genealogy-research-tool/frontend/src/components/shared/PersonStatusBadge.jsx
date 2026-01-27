export function PersonStatusBadge({ person }) {
  const getStatus = () => {
    if (person.gramps_person_id) {
      return {
        label: 'In Gramps',
        className: 'bg-green-100 text-green-800 border-green-300',
        icon: '✓'
      };
    }
    if ((person.confidence || 0) >= 0.80 && (person.source_count || 0) >= 2) {
      return {
        label: 'Ready',
        className: 'bg-blue-100 text-blue-800 border-blue-300',
        icon: '●'
      };
    }
    return {
      label: 'Needs Review',
      className: 'bg-yellow-100 text-yellow-800 border-yellow-300',
      icon: '!'
    };
  };

  const status = getStatus();

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${status.className}`}>
      <span className="mr-1">{status.icon}</span>
      {status.label}
    </span>
  );
}
