import { useState } from 'react';
import { URLForm } from './components/obituary/URLForm';
import { ProgressTracker } from './components/obituary/ProgressTracker';

function App() {
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
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Genealogy Research Tool
          </h1>
          <p className="text-lg text-gray-600">
            Extract family relationships from obituaries automatically
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
              <div className="mt-6 text-center">
                <button
                  onClick={handleProcessAnother}
                  className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
                >
                  Process Another Obituary
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default App;
