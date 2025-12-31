"""
Fuzzy matching service for identifying name variants across obituaries.

Handles:
- Name normalization (whitespace, case, punctuation)
- Fuzzy string matching (Levenshtein distance)
- Phonetic matching (Double Metaphone)
- Nickname detection
- Middle initial differences
"""

from typing import List, Dict, Tuple, Optional
from fuzzywuzzy import fuzz
from metaphone import doublemetaphone
import json
import re
from pathlib import Path


class PersonMatcher:
    """
    Multi-level person matching for cross-obituary name resolution.
    """

    def __init__(self, fuzzy_threshold: float = 0.85):
        self.fuzzy_threshold = fuzzy_threshold
        self.nickname_db = self._load_nicknames()

    def _load_nicknames(self) -> Dict[str, List[str]]:
        """Load nickname database from JSON file"""
        nicknames_path = Path(__file__).parent.parent / "data" / "nicknames.json"

        if nicknames_path.exists():
            with open(nicknames_path) as f:
                return json.load(f)
        else:
            print(f"Warning: Nickname database not found at {nicknames_path}")
            return {}

    def normalize_name(self, name: str) -> str:
        """
        Normalize name for comparison.

        - Remove middle initials (single letters followed by period)
        - Normalize whitespace
        - Remove suffixes (Jr, Sr, II, III, IV)
        - Lowercase
        """
        # Remove middle initials
        name = re.sub(r'\b[A-Z]\.\s*', '', name)

        # Normalize whitespace
        name = ' '.join(name.split())

        # Remove suffixes
        name = re.sub(r'\s+(Jr|Sr|II|III|IV)\.?$', '', name, flags=re.IGNORECASE)

        # Lowercase
        return name.lower().strip()

    def get_phonetic_codes(self, name: str) -> Tuple[str, str]:
        """
        Get Double Metaphone phonetic codes.
        Returns (primary_code, secondary_code)
        """
        primary, secondary = doublemetaphone(name)
        return (primary or '', secondary or '')

    def is_known_nickname(self, name1: str, name2: str) -> bool:
        """
        Check if name2 is a known nickname for name1.

        Examples:
            is_known_nickname("Patricia", "Patsy") -> True
            is_known_nickname("Steven", "Steve") -> True
        """
        name1_lower = name1.lower()
        name2_lower = name2.lower()

        # Check both directions
        for formal_name, nicknames in self.nickname_db.items():
            nicknames_lower = [n.lower() for n in nicknames]
            formal_lower = formal_name.lower()

            # Check if one is formal and other is nickname
            if name1_lower == formal_lower and name2_lower in nicknames_lower:
                return True
            if name2_lower == formal_lower and name1_lower in nicknames_lower:
                return True

            # Check if both are nicknames of same formal name
            if name1_lower in nicknames_lower and name2_lower in nicknames_lower:
                return True
            if (name1_lower == formal_lower or name1_lower in nicknames_lower) and \
               (name2_lower == formal_lower or name2_lower in nicknames_lower):
                return True

        return False

    def extract_first_last(self, full_name: str) -> Tuple[str, str]:
        """
        Extract first name and last name from full name.
        Returns (first_name, last_name)
        """
        parts = full_name.split()
        if len(parts) == 0:
            return ('', '')
        elif len(parts) == 1:
            return (parts[0], '')
        else:
            # First word is first name, last word is last name
            return (parts[0], parts[-1])

    def match_score(self, name1: str, name2: str) -> Dict:
        """
        Calculate comprehensive match score between two names.

        Returns:
            {
                'score': float (0-100),
                'method': str,
                'confidence': float (0.0-1.0),
                'details': dict
            }
        """
        # Exact match after normalization
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)

        if norm1 == norm2:
            return {
                'score': 100,
                'method': 'exact_normalized',
                'confidence': 1.0,
                'details': {
                    'normalized_name': norm1
                }
            }

        # Extract first and last names
        first1, last1 = self.extract_first_last(name1)
        first2, last2 = self.extract_first_last(name2)

        # Different surnames = not a match (unless one is empty)
        if last1 and last2:
            last1_norm = self.normalize_name(last1)
            last2_norm = self.normalize_name(last2)
            if last1_norm != last2_norm:
                # Check if surnames are phonetically similar (e.g., typos)
                phone_last1 = self.get_phonetic_codes(last1)
                phone_last2 = self.get_phonetic_codes(last2)
                surnames_phonetically_similar = (
                    phone_last1[0] == phone_last2[0] or
                    phone_last1[0] == phone_last2[1] or
                    phone_last1[1] == phone_last2[0]
                )
                if not surnames_phonetically_similar:
                    return {
                        'score': 0,
                        'method': 'different_surname',
                        'confidence': 0.0,
                        'details': {
                            'surname1': last1,
                            'surname2': last2
                        }
                    }

        # Check nickname match
        if first1 and first2 and self.is_known_nickname(first1, first2):
            return {
                'score': 95,
                'method': 'known_nickname',
                'confidence': 0.95,
                'details': {
                    'first_name1': first1,
                    'first_name2': first2,
                    'surname': last1 or last2
                }
            }

        # Fuzzy string matching
        ratio = fuzz.ratio(norm1, norm2)
        token_sort = fuzz.token_sort_ratio(name1, name2)
        partial = fuzz.partial_ratio(name1, name2)

        fuzzy_score = max(ratio, token_sort, partial)

        # Phonetic matching
        phone1_primary, phone1_secondary = self.get_phonetic_codes(first1 if first1 else name1)
        phone2_primary, phone2_secondary = self.get_phonetic_codes(first2 if first2 else name2)

        phonetic_match = (
            (phone1_primary and phone2_primary and phone1_primary == phone2_primary) or
            (phone1_primary and phone2_secondary and phone1_primary == phone2_secondary) or
            (phone1_secondary and phone2_primary and phone1_secondary == phone2_primary) or
            (phone1_secondary and phone2_secondary and phone1_secondary == phone2_secondary)
        )

        # Combined scoring
        if phonetic_match and fuzzy_score >= self.fuzzy_threshold * 100:
            return {
                'score': fuzzy_score,
                'method': 'fuzzy_with_phonetic',
                'confidence': fuzzy_score / 100,
                'details': {
                    'ratio': ratio,
                    'token_sort': token_sort,
                    'partial': partial,
                    'phonetic_match': True,
                    'phonetic_codes1': (phone1_primary, phone1_secondary),
                    'phonetic_codes2': (phone2_primary, phone2_secondary)
                }
            }
        elif fuzzy_score >= 90:
            return {
                'score': fuzzy_score,
                'method': 'fuzzy_high_confidence',
                'confidence': fuzzy_score / 100,
                'details': {
                    'ratio': ratio,
                    'token_sort': token_sort,
                    'partial': partial,
                    'phonetic_match': phonetic_match
                }
            }
        else:
            return {
                'score': fuzzy_score,
                'method': 'no_match',
                'confidence': 0.0,
                'details': {
                    'ratio': ratio,
                    'token_sort': token_sort,
                    'partial': partial
                }
            }

    def find_potential_matches(
        self,
        target_name: str,
        candidate_names: List[str],
        min_confidence: float = 0.85
    ) -> List[Tuple[str, Dict]]:
        """
        Find all potential matches for a name from a list of candidates.

        Args:
            target_name: Name to match
            candidate_names: List of candidate names
            min_confidence: Minimum confidence threshold (default: 0.85)

        Returns:
            List of (candidate_name, match_result) tuples, sorted by score descending
        """
        matches = []

        for candidate in candidate_names:
            if candidate == target_name:
                continue

            match_result = self.match_score(target_name, candidate)

            if match_result['confidence'] >= min_confidence:
                matches.append((candidate, match_result))

        # Sort by score descending
        matches.sort(key=lambda x: x[1]['score'], reverse=True)

        return matches


# Legacy functions for backward compatibility
def fuzzy_name_match(name1: str, name2: str, threshold: float = 0.85) -> float:
    """
    Calculate fuzzy match score between two names.
    Legacy function - use PersonMatcher.match_score() instead.
    """
    matcher = PersonMatcher(fuzzy_threshold=threshold)
    result = matcher.match_score(name1, name2)
    return result['confidence']


def find_matching_persons(
    target_name: str,
    candidate_names: List[str],
    threshold: float = 0.85
) -> List[Dict]:
    """
    Find potential matches for a target name from a list of candidates.
    Legacy function - use PersonMatcher.find_potential_matches() instead.
    """
    matcher = PersonMatcher(fuzzy_threshold=threshold)
    matches = matcher.find_potential_matches(target_name, candidate_names, threshold)

    return [
        {'name': name, 'score': result['confidence']}
        for name, result in matches
    ]
