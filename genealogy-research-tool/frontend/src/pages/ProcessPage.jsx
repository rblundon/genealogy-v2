import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { URLForm } from '../components/obituary/URLForm';
import { ProgressTracker } from '../components/obituary/ProgressTracker';

export function ProcessPage() {
  const navigate = useNavigate();
  const [currentObituaryId, setCurrentObituaryId] = useState(null);
  const [initialResult, setInitialResult] = useState(null);
  const [showResults, setShowResults] = useState(false);

  const handleSuccess = (result) => {
    console.log('Processing complete:', result);
    setCurrentObituaryId(result.obituary_id);
    setInitialResult(result);
    setShowResults(false);
  };

  const handleComplete = (result) => {
    console.log('Processing complete:', result);
    setShowResults(true);
  };

  const handleError = (error) => {
    console.error('Error:', error);
    alert(`Error: ${error.message}`);
  };

  const handleProcessAnother = () => {
    setCurrentObituaryId(null);
    setInitialResult(null);
    setShowResults(false);
  };

  return (
    <div>
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-2">
          Process Obituary
        </h1>
        <p className="text-lg text-gray-600">
          Extract family relationships from Legacy.com obituaries
        </p>
      </div>

      {!currentObituaryId ? (
        <URLForm
          onSuccess={handleSuccess}
          onError={handleError}
        />
      ) : (
        <>
          <ProgressTracker
            obituaryId={currentObituaryId}
            initialResult={initialResult}
            onComplete={handleComplete}
            onError={handleError}
          />

          {showResults && (
            <div className="mt-6 flex justify-center gap-4">
              <button
                onClick={() => navigate(`/obituaries/${currentObituaryId}`)}
                className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
              >
                View Results
              </button>
              <button
                onClick={handleProcessAnother}
                className="px-6 py-3 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 transition-colors"
              >
                Process Another Obituary
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
