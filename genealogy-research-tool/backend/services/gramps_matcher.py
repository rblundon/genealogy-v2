"""
Match person clusters to Gramps Web people.

Uses multiple criteria:
- Name matching (fuzzy)
- Date matching (birth, death)
- Relationship matching
- Location matching
"""

from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from models import PersonCluster, ExtractedFact
from services.gramps_client import GrampsClient
from services.person_matcher import PersonMatcher
import json


class GrampsMatcher:
    """
    Matches person clusters to Gramps Web people.
    """

    def __init__(self, db: Session, gramps_client: GrampsClient = None):
        self.db = db
        self.gramps = gramps_client or GrampsClient()
        self.fuzzy_matcher = PersonMatcher()

    def find_matches_for_cluster(self, cluster_id: int) -> List[Dict]:
        """
        Find potential Gramps matches for a person cluster.

        Args:
            cluster_id: PersonCluster ID

        Returns:
            List of potential matches with confidence scores
        """
        # Get cluster
        cluster = self.db.query(PersonCluster).filter(
            PersonCluster.id == cluster_id
        ).first()

        if not cluster:
            return []

        # Get all facts for this cluster
        facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.person_cluster_id == cluster_id
        ).all()

        # Extract key facts
        cluster_facts = self._extract_cluster_facts(cluster, facts)

        # Search Gramps using name
        name_variants = json.loads(cluster.name_variants)

        potential_matches = []
        searched_ids = set()  # Avoid duplicate searches

        for name in name_variants:
            # Split into given/surname
            parts = name.split()
            if len(parts) >= 2:
                given = ' '.join(parts[:-1])
                surname = parts[-1]

                # Search Gramps
                gramps_people = self.gramps.search_people(
                    given_name=given,
                    surname=surname,
                    limit=5
                )

                for gramps_person in gramps_people:
                    gramps_id = gramps_person.get('gramps_id')

                    if gramps_id in searched_ids:
                        continue
                    searched_ids.add(gramps_id)

                    # Extract Gramps facts
                    gramps_facts = self.gramps.extract_person_facts(gramps_person)

                    # Calculate match score
                    match_result = self._calculate_match_score(
                        cluster_facts,
                        gramps_facts
                    )

                    if match_result['confidence'] > 0.5:
                        potential_matches.append({
                            'gramps_id': gramps_id,
                            'gramps_person': gramps_person,
                            'gramps_facts': gramps_facts,
                            'match_confidence': match_result['confidence'],
                            'match_reasons': match_result['reasons'],
                            'conflicts': match_result['conflicts']
                        })

        # Sort by confidence
        potential_matches.sort(key=lambda x: x['match_confidence'], reverse=True)

        return potential_matches

    def _extract_cluster_facts(
        self,
        cluster: PersonCluster,
        facts: List[ExtractedFact]
    ) -> Dict:
        """
        Extract structured facts from cluster for matching.
        """
        cluster_facts = {
            'canonical_name': cluster.canonical_name,
            'name_variants': json.loads(cluster.name_variants),
            'nicknames': json.loads(cluster.nicknames) if cluster.nicknames else [],
            'maiden_names': json.loads(cluster.maiden_names) if cluster.maiden_names else [],
            'death_date': None,
            'death_age': None,
            'birth_date': None,
            'relationships': []
        }

        for fact in facts:
            if fact.fact_type == 'person_death_date':
                cluster_facts['death_date'] = fact.fact_value
            elif fact.fact_type == 'person_death_age':
                cluster_facts['death_age'] = fact.fact_value
            elif fact.fact_type == 'person_birth_date':
                cluster_facts['birth_date'] = fact.fact_value
            elif fact.fact_type in ['relationship', 'marriage']:
                cluster_facts['relationships'].append({
                    'type': fact.relationship_type or fact.fact_value,
                    'related_name': fact.related_name,
                    'confidence': float(fact.confidence_score) if fact.confidence_score else 0
                })

        return cluster_facts

    def _calculate_match_score(
        self,
        cluster_facts: Dict,
        gramps_facts: Dict
    ) -> Dict:
        """
        Calculate match confidence between cluster and Gramps person.

        Returns:
            {
                'confidence': float (0-1),
                'reasons': List[str],
                'conflicts': List[str]
            }
        """
        score = 0.0
        max_score = 0.0
        reasons = []
        conflicts = []

        # Name matching (weight: 40%) - always included
        max_score += 40
        name_match = self._match_names(cluster_facts, gramps_facts)
        score += name_match['score'] * 40
        if name_match['matched']:
            reasons.append(f"Name match: {name_match['method']}")

        # Death date matching (weight: 30%) - only if we have data to compare
        if cluster_facts.get('death_date') or gramps_facts.get('death_date'):
            max_score += 30
            if cluster_facts.get('death_date') and gramps_facts.get('death_date'):
                if cluster_facts['death_date'] == gramps_facts['death_date']:
                    score += 30
                    reasons.append("Death date matches exactly")
                else:
                    conflicts.append(
                        f"Death date mismatch: extracted={cluster_facts['death_date']}, "
                        f"gramps={gramps_facts['death_date']}"
                    )
            elif cluster_facts.get('death_date'):
                # We have death date, Gramps doesn't - not a conflict, just missing data
                reasons.append("Extracted death date not yet in Gramps")
        # Birth date matching (weight: 20%) - only if we have data to compare
        if cluster_facts.get('birth_date') or gramps_facts.get('birth_date'):
            max_score += 20
            if cluster_facts.get('birth_date') and gramps_facts.get('birth_date'):
                if cluster_facts['birth_date'] == gramps_facts['birth_date']:
                    score += 20
                    reasons.append("Birth date matches exactly")
                else:
                    conflicts.append(
                        f"Birth date mismatch: extracted={cluster_facts['birth_date']}, "
                        f"gramps={gramps_facts['birth_date']}"
                    )
            elif cluster_facts.get('birth_date'):
                reasons.append("Extracted birth date not yet in Gramps")

        # Calculate final confidence (based only on factors where we have data)
        confidence = score / max_score if max_score > 0 else 0.0

        return {
            'confidence': round(confidence, 2),
            'reasons': reasons,
            'conflicts': conflicts
        }

    def _match_names(self, cluster_facts: Dict, gramps_facts: Dict) -> Dict:
        """
        Match names using fuzzy matching.
        """
        cluster_names = cluster_facts['name_variants']
        gramps_names = [n['full'] for n in gramps_facts.get('names', [])]

        best_match = {'score': 0, 'matched': False, 'method': 'none'}

        for c_name in cluster_names:
            for g_name in gramps_names:
                match_result = self.fuzzy_matcher.match_score(c_name, g_name)

                if match_result['confidence'] > best_match['score']:
                    best_match = {
                        'score': match_result['confidence'],
                        'matched': match_result['confidence'] > 0.85,
                        'method': match_result['method']
                    }

        return best_match
