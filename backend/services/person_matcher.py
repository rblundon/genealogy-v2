"""Person matcher service for fuzzy duplicate detection."""

import logging
from dataclasses import dataclass
from typing import Optional

from rapidfuzz import fuzz

from services.gramps_connector import GrampsConnector, get_gramps_connector

logger = logging.getLogger(__name__)


@dataclass
class MatchCandidate:
    """A potential match for a person."""

    handle: str
    gramps_id: str
    first_name: str
    surname: str
    score: float  # 0.0 to 1.0
    match_details: dict  # Details about what matched


@dataclass
class MatchResult:
    """Result of matching a person against Gramps database."""

    query_first_name: str
    query_surname: str
    candidates: list[MatchCandidate]
    best_match: Optional[MatchCandidate] = None
    is_confident_match: bool = False  # Score >= threshold


class PersonMatcher:
    """Fuzzy matcher for detecting duplicate people in Gramps."""

    # Thresholds for matching
    HIGH_CONFIDENCE_THRESHOLD = 0.85  # Auto-match
    MEDIUM_CONFIDENCE_THRESHOLD = 0.60  # Needs review
    MIN_CANDIDATE_THRESHOLD = 0.40  # Don't show below this

    def __init__(self, connector: Optional[GrampsConnector] = None):
        """
        Initialize matcher.

        Args:
            connector: GrampsConnector instance (uses singleton if not provided)
        """
        self.connector = connector or get_gramps_connector()
        self._people_cache: list[dict] = []
        self._cache_loaded = False

    async def _load_people_cache(self, force_refresh: bool = False) -> None:
        """Load all people from Gramps into cache for matching."""
        if self._cache_loaded and not force_refresh:
            return

        self._people_cache = await self.connector.get_all_people()
        self._cache_loaded = True
        logger.info(f"Loaded {len(self._people_cache)} people into matcher cache")

    def _normalize_name(self, name: str) -> str:
        """Normalize a name for comparison."""
        if not name:
            return ""
        # Lowercase, strip whitespace, remove common prefixes/suffixes
        normalized = name.lower().strip()
        # Remove common name additions
        for suffix in [" jr", " sr", " ii", " iii", " iv"]:
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)]
        return normalized

    def _calculate_name_similarity(
        self,
        query_first: str,
        query_surname: str,
        target_first: str,
        target_surname: str,
    ) -> tuple[float, dict]:
        """
        Calculate similarity between two names.

        Returns:
            Tuple of (score, match_details)
        """
        # Normalize names
        q_first = self._normalize_name(query_first)
        q_surname = self._normalize_name(query_surname)
        t_first = self._normalize_name(target_first)
        t_surname = self._normalize_name(target_surname)

        # Calculate individual component scores
        first_score = fuzz.ratio(q_first, t_first) / 100.0
        surname_score = fuzz.ratio(q_surname, t_surname) / 100.0

        # Also try partial matching for first names (handles nicknames)
        first_partial = fuzz.partial_ratio(q_first, t_first) / 100.0
        first_score = max(first_score, first_partial * 0.9)  # Slight penalty for partial

        # Token-based matching catches reordered names
        full_query = f"{q_first} {q_surname}"
        full_target = f"{t_first} {t_surname}"
        token_score = fuzz.token_sort_ratio(full_query, full_target) / 100.0

        # Weighted combination: surname is more important for matching
        # Using 60% surname, 30% first name, 10% token-based
        combined_score = (surname_score * 0.6) + (first_score * 0.3) + (token_score * 0.1)

        # Bonus for exact matches
        if q_surname == t_surname:
            combined_score += 0.1
        if q_first == t_first:
            combined_score += 0.05

        # Cap at 1.0
        combined_score = min(combined_score, 1.0)

        match_details = {
            "first_name_score": round(first_score, 3),
            "surname_score": round(surname_score, 3),
            "token_score": round(token_score, 3),
            "exact_surname": q_surname == t_surname,
            "exact_first": q_first == t_first,
        }

        return combined_score, match_details

    async def find_matches(
        self,
        first_name: str,
        surname: str,
        maiden_name: Optional[str] = None,
        max_candidates: int = 5,
        force_refresh: bool = False,
    ) -> MatchResult:
        """
        Find potential matches for a person in Gramps.

        Args:
            first_name: Person's first name
            surname: Person's surname
            maiden_name: Optional maiden name to also check
            max_candidates: Maximum number of candidates to return
            force_refresh: Force refresh of people cache

        Returns:
            MatchResult with candidates and best match
        """
        await self._load_people_cache(force_refresh)

        candidates = []

        for person in self._people_cache:
            target_first, target_surname = self.connector.extract_person_name(person)

            # Calculate primary match score
            score, details = self._calculate_name_similarity(
                first_name, surname, target_first, target_surname
            )

            # If maiden name provided, also check against that
            if maiden_name:
                maiden_score, maiden_details = self._calculate_name_similarity(
                    first_name, maiden_name, target_first, target_surname
                )
                if maiden_score > score:
                    score = maiden_score
                    details = maiden_details
                    details["matched_maiden_name"] = True

            if score >= self.MIN_CANDIDATE_THRESHOLD:
                candidates.append(
                    MatchCandidate(
                        handle=person.get("handle", ""),
                        gramps_id=person.get("gramps_id", ""),
                        first_name=target_first,
                        surname=target_surname,
                        score=round(score, 3),
                        match_details=details,
                    )
                )

        # Sort by score descending
        candidates.sort(key=lambda x: x.score, reverse=True)

        # Limit candidates
        candidates = candidates[:max_candidates]

        # Determine best match
        best_match = candidates[0] if candidates else None
        is_confident = best_match is not None and best_match.score >= self.HIGH_CONFIDENCE_THRESHOLD

        return MatchResult(
            query_first_name=first_name,
            query_surname=surname,
            candidates=candidates,
            best_match=best_match,
            is_confident_match=is_confident,
        )

    async def match_extracted_facts(
        self,
        facts: list[dict],
        force_refresh: bool = False,
    ) -> dict[str, MatchResult]:
        """
        Match a list of extracted facts against Gramps database.

        Args:
            facts: List of extracted fact dictionaries with subject_name, related_name
            force_refresh: Force refresh of people cache

        Returns:
            Dictionary mapping person names to their match results
        """
        await self._load_people_cache(force_refresh)

        # Collect unique person names from facts
        persons_to_match: dict[str, dict] = {}

        for fact in facts:
            # Subject of the fact
            subject = fact.get("subject_name", "")
            if subject and subject not in persons_to_match:
                # Parse name - assuming "First Last" format
                parts = subject.split(maxsplit=1)
                first = parts[0] if parts else ""
                surname = parts[1] if len(parts) > 1 else ""
                maiden = fact.get("maiden_name")
                persons_to_match[subject] = {
                    "first_name": first,
                    "surname": surname,
                    "maiden_name": maiden,
                }

            # Related person in the fact
            related = fact.get("related_name", "")
            if related and related not in persons_to_match:
                parts = related.split(maxsplit=1)
                first = parts[0] if parts else ""
                surname = parts[1] if len(parts) > 1 else ""
                persons_to_match[related] = {
                    "first_name": first,
                    "surname": surname,
                    "maiden_name": None,
                }

        # Match each person
        results = {}
        for name, info in persons_to_match.items():
            result = await self.find_matches(
                first_name=info["first_name"],
                surname=info["surname"],
                maiden_name=info.get("maiden_name"),
                force_refresh=False,  # Cache already loaded
            )
            results[name] = result

        return results


# Singleton instance
_matcher: Optional[PersonMatcher] = None


def get_person_matcher() -> PersonMatcher:
    """Get or create PersonMatcher singleton."""
    global _matcher
    if _matcher is None:
        _matcher = PersonMatcher()
    return _matcher


def reset_person_matcher() -> None:
    """Reset the matcher singleton (useful for testing)."""
    global _matcher
    _matcher = None
