"""
Person matching service - stub for Phase 2.

This service will handle:
- Fuzzy name matching across obituaries
- Multi-source corroboration
- Clustering same person across different obituaries
- Resolution to Gramps Web SSOT
"""

from typing import List, Dict, Optional
from fuzzywuzzy import fuzz
from metaphone import doublemetaphone


def fuzzy_name_match(name1: str, name2: str, threshold: float = 0.85) -> float:
    """
    Calculate fuzzy match score between two names.

    Uses combination of:
    - Token sort ratio (handles word order differences)
    - Phonetic matching (handles spelling variants)

    Returns score between 0.0 and 1.0
    """
    # Token sort ratio handles "John Smith" vs "Smith, John"
    token_score = fuzz.token_sort_ratio(name1.lower(), name2.lower()) / 100.0

    # Phonetic matching for spelling variants
    mp1 = doublemetaphone(name1)
    mp2 = doublemetaphone(name2)

    # Check if any metaphone codes match
    phonetic_match = 0.0
    for code1 in mp1:
        for code2 in mp2:
            if code1 and code2 and code1 == code2:
                phonetic_match = 1.0
                break

    # Combine scores (weight token score higher)
    combined_score = (token_score * 0.7) + (phonetic_match * 0.3)

    return combined_score


def find_matching_persons(
    target_name: str,
    candidate_names: List[str],
    threshold: float = 0.85
) -> List[Dict]:
    """
    Find potential matches for a target name from a list of candidates.

    Returns list of matches with scores above threshold.
    """
    matches = []

    for candidate in candidate_names:
        score = fuzzy_name_match(target_name, candidate)
        if score >= threshold:
            matches.append({
                'name': candidate,
                'score': score
            })

    # Sort by score descending
    matches.sort(key=lambda x: x['score'], reverse=True)

    return matches


# Placeholder for Phase 2 implementation
class PersonClusterService:
    """
    Service for clustering same person across multiple obituaries.

    Phase 2 implementation will:
    - Use fuzzy matching to identify candidate matches
    - Apply multi-source corroboration to increase confidence
    - Create and manage person clusters
    - Resolve clusters to Gramps Web SSOT
    """

    def __init__(self, db_session):
        self.db = db_session
        self.match_threshold = 0.85

    def find_or_create_cluster(self, name: str, obituary_id: int) -> Optional[int]:
        """
        Find existing cluster for a person name, or create new one.

        Returns cluster_id
        """
        # TODO: Implement in Phase 2
        pass

    def merge_clusters(self, cluster_id_1: int, cluster_id_2: int) -> int:
        """
        Merge two clusters that represent the same person.

        Returns the surviving cluster_id
        """
        # TODO: Implement in Phase 2
        pass

    def link_to_gramps(self, cluster_id: int, gramps_person_id: str) -> bool:
        """
        Link a cluster to a Gramps Web person ID.

        Returns True if successful
        """
        # TODO: Implement in Phase 2
        pass
