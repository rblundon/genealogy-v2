"""
Fact clustering service for grouping facts about the same person.

Two-level clustering:
1. Intra-obituary: Group facts by subject within a single obituary
2. Cross-obituary: Link same person across multiple obituaries using fuzzy matching
"""

from typing import List, Dict, Set, Optional
from sqlalchemy.orm import Session
from sqlalchemy import distinct
from collections import defaultdict
import json

from models import ExtractedFact, PersonCluster, ObituaryCache
from services.person_matcher import PersonMatcher


class FactClusterer:
    """
    Clusters facts about the same person across obituaries.
    """

    def __init__(self, db: Session, fuzzy_threshold: float = 0.85):
        self.db = db
        self.matcher = PersonMatcher(fuzzy_threshold=fuzzy_threshold)

    def cluster_facts_within_obituary(self, obituary_cache_id: int) -> Dict[str, List[ExtractedFact]]:
        """
        Group facts by subject within a single obituary.

        Returns:
            {subject_name: [facts]}
        """
        facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.obituary_cache_id == obituary_cache_id
        ).all()

        clusters = defaultdict(list)
        for fact in facts:
            clusters[fact.subject_name].append(fact)

        return dict(clusters)

    def find_cross_obituary_clusters(self) -> List[Dict]:
        """
        Find people mentioned in multiple obituaries and cluster their facts.

        Uses fuzzy matching to identify name variants.

        Returns:
            List of cluster dicts with:
            - canonical_name
            - name_variants
            - facts
            - obituary_count
            - confidence
        """
        # Get all unique subject names
        all_names_result = self.db.query(distinct(ExtractedFact.subject_name)).all()
        all_names = [name[0] for name in all_names_result]

        print(f"Clustering {len(all_names)} unique names across obituaries...")

        clusters = []
        processed = set()

        for target_name in all_names:
            if target_name in processed:
                continue

            # Start new cluster
            cluster_variants = {target_name}
            processed.add(target_name)

            # Find fuzzy matches
            remaining_names = [n for n in all_names if n not in processed]
            matches = self.matcher.find_potential_matches(
                target_name,
                remaining_names,
                min_confidence=0.85
            )

            # Add high-confidence matches to cluster
            for matched_name, match_result in matches:
                if match_result['confidence'] >= 0.85:
                    cluster_variants.add(matched_name)
                    processed.add(matched_name)

            # Get all facts for all variants in this cluster
            all_facts = self.db.query(ExtractedFact).filter(
                ExtractedFact.subject_name.in_(cluster_variants)
            ).all()

            if not all_facts:
                continue

            # Count unique obituaries
            obituary_ids = set(f.obituary_cache_id for f in all_facts)

            # Calculate cluster confidence (average of all facts)
            avg_confidence = sum(float(f.confidence_score) for f in all_facts) / len(all_facts)

            # Determine canonical name (longest/most complete)
            canonical = max(cluster_variants, key=len)

            clusters.append({
                'canonical_name': canonical,
                'name_variants': sorted(list(cluster_variants)),
                'facts': all_facts,
                'fact_count': len(all_facts),
                'obituary_count': len(obituary_ids),
                'obituary_ids': list(obituary_ids),
                'confidence': round(avg_confidence, 2)
            })

        # Sort by obituary count (most corroborated first)
        clusters.sort(key=lambda c: (c['obituary_count'], c['fact_count']), reverse=True)

        print(f"Created {len(clusters)} person clusters")
        print(f"  - {sum(1 for c in clusters if c['obituary_count'] > 1)} people in multiple obituaries")
        print(f"  - {sum(1 for c in clusters if len(c['name_variants']) > 1)} clusters with name variants")

        return clusters

    def create_person_cluster_records(self, clusters: List[Dict]) -> List[PersonCluster]:
        """
        Create PersonCluster records in database from cluster data.

        Links all facts in each cluster via person_cluster_id.
        """
        # First, clear any existing cluster assignments
        self.db.query(ExtractedFact).update({
            ExtractedFact.person_cluster_id: None,
            ExtractedFact.resolution_status: 'unresolved'
        })

        # Delete existing clusters
        self.db.query(PersonCluster).delete()
        self.db.commit()

        cluster_records = []

        for cluster_data in clusters:
            # Extract nicknames and maiden names from facts
            nicknames = set()
            maiden_names = set()

            for fact in cluster_data['facts']:
                if fact.fact_type == 'person_nickname':
                    nicknames.add(fact.fact_value)
                elif fact.fact_type == 'maiden_name':
                    maiden_names.add(fact.fact_value)

            # Create cluster record
            cluster = PersonCluster(
                canonical_name=cluster_data['canonical_name'],
                name_variants=json.dumps(cluster_data['name_variants']),
                nicknames=json.dumps(list(nicknames)) if nicknames else None,
                maiden_names=json.dumps(list(maiden_names)) if maiden_names else None,
                confidence_score=cluster_data['confidence'],
                source_count=cluster_data['obituary_count'],
                fact_count=cluster_data['fact_count'],
                cluster_status='verified' if cluster_data['obituary_count'] > 1 else 'unverified'
            )

            self.db.add(cluster)
            self.db.flush()  # Get the ID

            # Link all facts to this cluster
            for fact in cluster_data['facts']:
                fact.person_cluster_id = cluster.id
                fact.resolution_status = 'clustered'

            cluster_records.append(cluster)

        self.db.commit()

        print(f"Created {len(cluster_records)} PersonCluster records in database")

        return cluster_records

    def get_cluster_summary(self, cluster_id: int) -> Optional[Dict]:
        """
        Get detailed summary of a person cluster.
        """
        cluster = self.db.query(PersonCluster).filter(
            PersonCluster.id == cluster_id
        ).first()

        if not cluster:
            return None

        facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.person_cluster_id == cluster_id
        ).all()

        # Group facts by type
        facts_by_type = defaultdict(list)
        for fact in facts:
            facts_by_type[fact.fact_type].append(fact)

        # Get obituary sources
        obituary_ids = list(set(f.obituary_cache_id for f in facts))
        obituaries = self.db.query(ObituaryCache).filter(
            ObituaryCache.id.in_(obituary_ids)
        ).all()

        return {
            'cluster_id': cluster.id,
            'canonical_name': cluster.canonical_name,
            'name_variants': json.loads(cluster.name_variants),
            'nicknames': json.loads(cluster.nicknames) if cluster.nicknames else [],
            'maiden_names': json.loads(cluster.maiden_names) if cluster.maiden_names else [],
            'confidence': float(cluster.confidence_score) if cluster.confidence_score else None,
            'source_count': cluster.source_count,
            'fact_count': cluster.fact_count,
            'cluster_status': cluster.cluster_status,
            'gramps_person_id': cluster.gramps_person_id,
            'sources': [
                {
                    'obituary_id': obit.id,
                    'url': obit.url,
                    'fetch_timestamp': obit.fetch_timestamp.isoformat() if obit.fetch_timestamp else None
                }
                for obit in obituaries
            ],
            'facts_by_type': {
                fact_type: [
                    {
                        'fact_value': f.fact_value,
                        'confidence': float(f.confidence_score),
                        'is_inferred': f.is_inferred,
                        'extracted_context': f.extracted_context,
                        'obituary_id': f.obituary_cache_id
                    }
                    for f in facts_list
                ]
                for fact_type, facts_list in facts_by_type.items()
            }
        }

    def detect_conflicts(self, cluster_id: int) -> List[Dict]:
        """
        Detect conflicting facts within a cluster.

        Examples:
        - Same fact type with different values from different sources
        - Death dates that don't match
        - Conflicting relationships
        """
        facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.person_cluster_id == cluster_id
        ).all()

        conflicts = []

        # Group by fact type
        facts_by_type = defaultdict(list)
        for fact in facts:
            if fact.fact_type in ['person_death_date', 'person_birth_date', 'person_death_age']:
                facts_by_type[fact.fact_type].append(fact)

        # Check for conflicting values
        for fact_type, fact_list in facts_by_type.items():
            if len(fact_list) <= 1:
                continue

            values = set(f.fact_value for f in fact_list)
            if len(values) > 1:
                conflicts.append({
                    'fact_type': fact_type,
                    'conflicting_values': list(values),
                    'sources': [
                        {
                            'value': f.fact_value,
                            'obituary_id': f.obituary_cache_id,
                            'confidence': float(f.confidence_score)
                        }
                        for f in fact_list
                    ]
                })

        return conflicts

    def get_corroborated_facts(self, cluster_id: int) -> List[Dict]:
        """
        Get facts that appear in multiple obituaries for a cluster.

        Multi-source corroboration increases confidence.
        """
        facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.person_cluster_id == cluster_id
        ).all()

        # Group identical facts from different sources
        # For relationships, include related_name in the key
        fact_groups = defaultdict(list)

        for fact in facts:
            if fact.fact_type in ['relationship', 'marriage']:
                # For relationships, group by (type, relationship_type, related_name)
                rel = fact.relationship_type or fact.fact_value or 'unknown'
                person = fact.related_name or 'unknown'
                key = (fact.fact_type, rel, person)
            else:
                key = (fact.fact_type, fact.fact_value, None)
            fact_groups[key].append(fact)

        # Find corroborated facts (same fact from multiple sources)
        corroborated = []
        for key, fact_list in fact_groups.items():
            source_count = len(set(f.obituary_cache_id for f in fact_list))

            if source_count > 1:
                fact_type = key[0]
                if fact_type in ['relationship', 'marriage']:
                    corroborated.append({
                        'fact_type': fact_type,
                        'relationship_type': key[1],
                        'related_name': key[2],
                        'fact_value': fact_list[0].fact_value,
                        'source_count': source_count,
                        'avg_confidence': sum(float(f.confidence_score) for f in fact_list) / len(fact_list),
                        'sources': [
                            {
                                'obituary_id': f.obituary_cache_id,
                                'confidence': float(f.confidence_score),
                                'extracted_context': f.extracted_context
                            }
                            for f in fact_list
                        ]
                    })
                else:
                    corroborated.append({
                        'fact_type': fact_type,
                        'fact_value': key[1],
                        'source_count': source_count,
                        'avg_confidence': sum(float(f.confidence_score) for f in fact_list) / len(fact_list),
                        'sources': [
                            {
                                'obituary_id': f.obituary_cache_id,
                                'confidence': float(f.confidence_score),
                                'extracted_context': f.extracted_context
                            }
                            for f in fact_list
                        ]
                    })

        # Sort by source count (most corroborated first)
        corroborated.sort(key=lambda x: x['source_count'], reverse=True)

        return corroborated
