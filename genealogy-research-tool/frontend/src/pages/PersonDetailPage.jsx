import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getPersonDetail } from '../api/client';
import { ConfidenceBadge } from '../components/shared/ConfidenceBadge';
import { PersonStatusBadge } from '../components/shared/PersonStatusBadge';
import { extractNameFromURL, formatRelativeTime } from '../utils/formatters';

export function PersonDetailPage() {
  const { id } = useParams();

  const [person, setPerson] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadPerson();
  }, [id]);

  const loadPerson = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await getPersonDetail(id);
      setPerson(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Group facts into person facts and relationships
  const groupFacts = () => {
    if (!person || !person.facts_by_type) {
      return { personFacts: [], relationships: {} };
    }

    const personFactTypes = [
      'person_name', 'person_nickname', 'person_death_date', 'person_death_age',
      'person_birth_date', 'person_birth_year_approx', 'person_gender',
      'maiden_name', 'surname', 'deceased', 'location_birth', 'location_death',
      'location_residence'
    ];

    const relationshipCategories = {
      spouse: ['marriage', 'marriage_duration'],
      parent: [],
      child: [],
      sibling: [],
      extended: ['survived_by', 'preceded_in_death']
    };

    // Build person facts list
    const personFacts = [];
    for (const [factType, facts] of Object.entries(person.facts_by_type)) {
      if (personFactTypes.includes(factType)) {
        facts.forEach(f => personFacts.push({ ...f, fact_type: factType }));
      }
    }

    // Build relationships from 'relationship' type facts
    const relationships = {
      spouse: [],
      parent: [],
      child: [],
      sibling: [],
      extended: []
    };

    // Process relationship facts
    const relationshipFacts = person.facts_by_type['relationship'] || [];
    relationshipFacts.forEach(fact => {
      const relType = (fact.related_name || '').toLowerCase();
      // Categorize by relationship type keywords
      if (['spouse', 'wife', 'husband'].some(t => fact.fact_value?.toLowerCase().includes(t))) {
        relationships.spouse.push(fact);
      } else if (['father', 'mother', 'parent'].some(t => fact.fact_value?.toLowerCase().includes(t))) {
        relationships.parent.push(fact);
      } else if (['son', 'daughter', 'child'].some(t => fact.fact_value?.toLowerCase().includes(t))) {
        relationships.child.push(fact);
      } else if (['brother', 'sister', 'sibling'].some(t => fact.fact_value?.toLowerCase().includes(t))) {
        relationships.sibling.push(fact);
      } else {
        relationships.extended.push(fact);
      }
    });

    // Also add marriage facts to spouse
    (person.facts_by_type['marriage'] || []).forEach(f => relationships.spouse.push({ ...f, fact_type: 'marriage' }));
    (person.facts_by_type['marriage_duration'] || []).forEach(f => relationships.spouse.push({ ...f, fact_type: 'marriage_duration' }));

    // Add survived_by and preceded_in_death to extended
    (person.facts_by_type['survived_by'] || []).forEach(f => relationships.extended.push({ ...f, fact_type: 'survived_by' }));
    (person.facts_by_type['preceded_in_death'] || []).forEach(f => relationships.extended.push({ ...f, fact_type: 'preceded_in_death' }));

    return { personFacts, relationships };
  };

  // Format fact type for display
  const formatFactType = (factType) => {
    return factType
      .replace(/_/g, ' ')
      .replace(/person /g, '')
      .replace(/\b\w/g, l => l.toUpperCase());
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <svg
            className="animate-spin mx-auto h-12 w-12 text-blue-600 mb-4"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <p className="text-gray-600">Loading person details...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <Link
          to="/people"
          className="inline-flex items-center text-sm text-blue-600 hover:text-blue-700 mb-6"
        >
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to People
        </Link>

        <div className="bg-red-50 border border-red-200 rounded-md p-6">
          <div className="flex">
            <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Failed to load person</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!person) return null;

  const { personFacts, relationships } = groupFacts();

  // Get source obituary info from the person's sources
  const sources = person.sources || [];

  return (
    <div>
      {/* Back Link */}
      <div className="mb-6">
        <Link
          to="/people"
          className="inline-flex items-center text-sm text-blue-600 hover:text-blue-700"
        >
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to People
        </Link>
      </div>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-3">
          {person.canonical_name}
        </h1>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <PersonStatusBadge person={person} />
          <ConfidenceBadge score={person.confidence} />
          <span className="text-gray-500">
            {person.source_count} {person.source_count === 1 ? 'source' : 'sources'}
          </span>
          <span className="text-gray-400">|</span>
          <span className="text-gray-500">
            {person.fact_count} {person.fact_count === 1 ? 'fact' : 'facts'}
          </span>
          {person.gramps_person_id && (
            <>
              <span className="text-gray-400">|</span>
              <span className="text-green-600">Gramps: {person.gramps_person_id}</span>
            </>
          )}
        </div>

        {/* Name Variants */}
        {person.name_variants && person.name_variants.length > 1 && (
          <div className="mt-3 text-sm text-gray-600">
            <span className="font-medium">Also known as: </span>
            {person.name_variants.filter(v => v !== person.canonical_name).join(', ')}
          </div>
        )}

        {/* Maiden Names */}
        {person.maiden_names && person.maiden_names.length > 0 && (
          <div className="mt-1 text-sm text-gray-600">
            <span className="font-medium">Maiden name: </span>
            {person.maiden_names.join(', ')}
          </div>
        )}

        {/* Nicknames */}
        {person.nicknames && person.nicknames.length > 0 && (
          <div className="mt-1 text-sm text-gray-600">
            <span className="font-medium">Nickname: </span>
            {person.nicknames.join(', ')}
          </div>
        )}
      </div>

      {/* Person Facts */}
      <div className="bg-white shadow-sm rounded-lg p-6 mb-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Person Facts</h2>

        {personFacts.length === 0 ? (
          <p className="text-gray-500">No person facts available.</p>
        ) : (
          <div className="space-y-3">
            {personFacts.map((fact, index) => (
              <div key={index} className="border-l-4 border-blue-500 pl-4 py-2">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <span className="font-medium text-gray-900">
                      {formatFactType(fact.fact_type)}:
                    </span>
                    <span className="ml-2 text-gray-700">{fact.fact_value}</span>
                    {fact.is_inferred && (
                      <span className="ml-2 text-xs text-amber-600">(inferred)</span>
                    )}
                  </div>
                  <ConfidenceBadge score={fact.confidence} />
                </div>
                {fact.obituary_id && (
                  <Link
                    to={`/obituaries/${fact.obituary_id}`}
                    className="text-sm text-blue-600 hover:text-blue-800 mt-1 inline-block"
                  >
                    Source: Obituary #{fact.obituary_id}
                  </Link>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Relationships */}
      <div className="bg-white shadow-sm rounded-lg p-6 mb-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Relationships</h2>

        {Object.entries(relationships).every(([_, facts]) => facts.length === 0) ? (
          <p className="text-gray-500">No relationships found.</p>
        ) : (
          <div className="space-y-6">
            {Object.entries(relationships).map(([relType, facts]) => (
              facts.length > 0 && (
                <div key={relType}>
                  <h3 className="font-medium text-gray-700 capitalize mb-3 text-lg">
                    {relType === 'extended' ? 'Other Relatives' : `${relType}s`}
                  </h3>
                  <div className="space-y-2">
                    {facts.map((fact, index) => (
                      <div key={index} className="border-l-4 border-green-500 pl-4 py-2">
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <span className="text-gray-900">
                              {fact.related_name || fact.fact_value}
                            </span>
                            {fact.fact_type && fact.fact_type !== 'relationship' && (
                              <span className="ml-2 text-xs text-gray-500">
                                ({formatFactType(fact.fact_type)})
                              </span>
                            )}
                            {fact.is_inferred && (
                              <span className="ml-2 text-xs text-amber-600">(inferred)</span>
                            )}
                          </div>
                          <ConfidenceBadge score={fact.confidence} />
                        </div>
                        {fact.obituary_id && (
                          <Link
                            to={`/obituaries/${fact.obituary_id}`}
                            className="text-sm text-blue-600 hover:text-blue-800 mt-1 inline-block"
                          >
                            Source: Obituary #{fact.obituary_id}
                          </Link>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )
            ))}
          </div>
        )}
      </div>

      {/* Source Obituaries */}
      <div className="bg-white shadow-sm rounded-lg p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Source Obituaries</h2>

        {sources.length === 0 ? (
          <p className="text-gray-500">No source obituaries available.</p>
        ) : (
          <ul className="space-y-3">
            {sources.map((source) => (
              <li key={source.obituary_id} className="flex items-start justify-between">
                <div>
                  <Link
                    to={`/obituaries/${source.obituary_id}`}
                    className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                  >
                    {extractNameFromURL(source.url)}
                  </Link>
                  <div className="text-sm text-gray-500 mt-1">
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-blue-600"
                    >
                      {source.url.length > 60 ? source.url.slice(0, 60) + '...' : source.url}
                    </a>
                  </div>
                </div>
                <span className="text-sm text-gray-500">
                  {source.fetch_timestamp ? formatRelativeTime(source.fetch_timestamp) : ''}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
