import { useState } from 'react';

export function ExpandableSection({
  title,
  previewContent,
  fullContent,
  defaultExpanded = false
}) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div className="bg-white shadow-sm rounded-lg p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">{title}</h3>

      <div className="text-sm text-gray-700">
        {isExpanded ? fullContent : previewContent}
      </div>

      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="mt-3 text-sm font-medium text-blue-600 hover:text-blue-700 flex items-center"
      >
        {isExpanded ? (
          <>
            Show less
            <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
          </>
        ) : (
          <>
            Show full {title.toLowerCase()}
            <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </>
        )}
      </button>
    </div>
  );
}
