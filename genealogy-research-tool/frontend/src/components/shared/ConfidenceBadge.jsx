export function ConfidenceBadge({ score }) {
  const getColor = (score) => {
    if (score >= 0.85) return 'bg-green-100 text-green-800 border-green-300';
    if (score >= 0.70) return 'bg-yellow-100 text-yellow-800 border-yellow-300';
    return 'bg-red-100 text-red-800 border-red-300';
  };

  const displayScore = score != null ? (score * 100).toFixed(0) : '?';

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${getColor(score || 0)}`}>
      {displayScore}%
    </span>
  );
}
