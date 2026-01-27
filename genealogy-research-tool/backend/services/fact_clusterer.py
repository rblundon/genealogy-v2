"""
Fact clustering service - Identity matching across obituaries.

This module handles linking the same person across multiple obituaries.
All relationship extraction and inference happens during obituary processing.
Clustering simply:
1. Identifies unique people by name matching
2. Links extracted facts to person records
3. Aggregates facts for display
"""

import re
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import distinct
from collections import defaultdict
import json

from models import ExtractedFact, PersonCluster, ObituaryCache
from services.person_matcher import PersonMatcher


class FactClusterer:
    """
    Links people across obituaries using name matching.

    All relationship logic is handled during extraction.
    This class only handles identity matching.
    """

    def __init__(self, db: Session, fuzzy_threshold: float = 0.85):
        self.db = db
        self.person_matcher = PersonMatcher(fuzzy_threshold=fuzzy_threshold)

    def find_cross_obituary_clusters(self) -> List[Dict]:
        """
        Find unique people across all obituaries.

        Uses exact and normalized name matching to identify
        the same person mentioned in different obituaries.
        """
        # Get all unique subject names
        subject_names_result = self.db.query(distinct(ExtractedFact.subject_name)).all()
        all_subject_names = [name[0] for name in subject_names_result if name[0]]

        # Get all unique related names from relationship facts
        relationship_fact_types = ['relationship', 'marriage', 'survived_by', 'preceded_in_death']
        related_names_result = self.db.query(distinct(ExtractedFact.related_name)).filter(
            ExtractedFact.related_name.isnot(None),
            ExtractedFact.fact_type.in_(relationship_fact_types)
        ).all()
        all_related_names = [name[0] for name in related_names_result if name[0]]

        # Combine all names
        all_names = list(set(all_subject_names + all_related_names))
        print(f"Found {len(all_names)} unique names across obituaries...")

        # Build normalized name index for matching variants
        normalized_index = self._build_normalized_name_index(all_names)

        clusters = []
        processed = set()

        for target_name in all_names:
            if target_name in processed:
                continue

            # Start cluster with this name
            cluster_variants = {target_name}
            processed.add(target_name)

            # Find normalized name matches (e.g., "Patricia L. Blundon" = "Patricia Blundon")
            normalized = self._normalize_name(target_name)
            if normalized in normalized_index:
                for variant_name in normalized_index[normalized]:
                    if variant_name not in processed:
                        cluster_variants.add(variant_name)
                        processed.add(variant_name)

            # Get facts where this person is mentioned
            subject_facts = self.db.query(ExtractedFact).filter(
                ExtractedFact.subject_name.in_(cluster_variants)
            ).all()

            related_facts = self.db.query(ExtractedFact).filter(
                ExtractedFact.related_name.in_(cluster_variants),
                ExtractedFact.fact_type.in_(relationship_fact_types)
            ).all()

            # Combine and deduplicate
            fact_ids_seen = set()
            all_facts = []
            for fact in subject_facts + related_facts:
                if fact.id not in fact_ids_seen:
                    fact_ids_seen.add(fact.id)
                    all_facts.append(fact)

            if not all_facts:
                continue

            # Count unique obituaries
            obituary_ids = set(f.obituary_cache_id for f in all_facts)

            # Calculate confidence (average)
            avg_confidence = sum(float(f.confidence_score) for f in all_facts) / len(all_facts)

            # Canonical name = longest variant
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

        # Apply additional merge strategies
        print(f"Initial clusters: {len(clusters)}")

        # Merge by relationship context (first-name-only to full-name)
        clusters = self._merge_by_relationship_context(clusters)
        print(f"After relationship merge: {len(clusters)}")

        # Merge by maiden name links
        clusters = self._merge_by_maiden_name(clusters)
        print(f"After maiden name merge: {len(clusters)}")

        # Merge by spelling variants (Rose Mary = Rosemary)
        clusters = self._merge_by_spelling_variants(clusters)
        print(f"After spelling merge: {len(clusters)}")

        # Merge by fuzzy matching (nicknames, phonetic similarity)
        clusters = self._merge_by_fuzzy_matching(clusters)
        print(f"After fuzzy merge: {len(clusters)}")

        # Clean up: remove first-name-only entries from name_variants
        # when the canonical name is a full name (has surname).
        # "Ryan Blundon" should NOT have "Ryan" as "Also known as".
        for cluster in clusters:
            canonical = cluster['canonical_name']
            if ' ' in canonical:  # Full name with surname
                # Filter out first-name-only variants
                cluster['name_variants'] = sorted([
                    v for v in cluster['name_variants'] if ' ' in v
                ])

        # Sort by obituary count (people in multiple obits first)
        clusters.sort(key=lambda c: (c['obituary_count'], c['fact_count']), reverse=True)

        print(f"Created {len(clusters)} person clusters")
        print(f"  - {sum(1 for c in clusters if c['obituary_count'] > 1)} people in multiple obituaries")

        return clusters

    def _normalize_name(self, name: str) -> str:
        """Normalize name for matching (removes middle initials, lowercase)."""
        if not name:
            return ""
        # Remove middle initials
        name = re.sub(r'\s+[A-Z]\.?\s+', ' ', name)
        # Keep only first and last name
        parts = name.split()
        if len(parts) > 2:
            name = f"{parts[0]} {parts[-1]}"
        return ' '.join(name.lower().split())

    def _normalize_given_name(self, name: str) -> str:
        """Normalize given name for fuzzy matching (handles Rose Mary vs Rosemary)."""
        if not name:
            return ""
        # Remove spaces to handle "Rose Mary" = "Rosemary"
        return name.lower().replace(" ", "").replace("-", "")

    def _get_first_name(self, full_name: str) -> str:
        """Extract first name from full name."""
        if not full_name:
            return ""
        parts = full_name.split()
        return parts[0].lower() if parts else ""

    def _build_normalized_name_index(self, names: List[str]) -> Dict[str, List[str]]:
        """Build index mapping normalized names to original variants."""
        index = defaultdict(list)
        for name in names:
            normalized = self._normalize_name(name)
            if normalized:
                index[normalized].append(name)
        return dict(index)

    def _build_first_name_index(self, names: List[str]) -> Dict[str, List[str]]:
        """Build index mapping first names to full names."""
        index = defaultdict(list)
        for name in names:
            first = self._get_first_name(name)
            if first:
                index[first].append(name)
        return dict(index)

    def _find_maiden_name_links(self) -> Dict[str, str]:
        """
        Find links between married names and maiden names.
        Returns mapping of maiden_name_full -> married_name_full
        """
        links = {}

        # Get all maiden_name facts
        maiden_facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.fact_type == 'maiden_name'
        ).all()

        for fact in maiden_facts:
            # fact.subject_name = "Patricia Blundon" (married name)
            # fact.fact_value = "Kaczmarowski" (maiden surname)
            married_name = fact.subject_name
            maiden_surname = fact.fact_value

            # Get first name from married name
            parts = married_name.split()
            if parts:
                first_name = parts[0]
                maiden_full = f"{first_name} {maiden_surname}"
                links[maiden_full.lower()] = married_name

        return links

    def _merge_by_relationship_context(self, clusters: List[Dict]) -> List[Dict]:
        """
        Merge clusters where a first-name-only person matches a full-name person
        within the SAME obituary (e.g., "Ryan" mentioned as grandchild is same as
        "Ryan Blundon" mentioned elsewhere in same obituary).

        IMPORTANT: Only merges within same obituary to avoid false matches across
        hundreds of obituaries where common first names appear frequently.

        Does NOT add first-name-only as a name variant (e.g., "Ryan Blundon"
        should not have "Ryan" as "Also known as").
        """
        # Build index of first-name-only clusters
        first_name_only = {}  # first_name -> cluster
        full_name_clusters = []  # clusters with surnames

        for cluster in clusters:
            canonical = cluster['canonical_name']
            if ' ' not in canonical:  # Single name (no surname)
                first_name_only[canonical.lower()] = cluster
            else:
                full_name_clusters.append(cluster)

        # Try to merge first-name-only with full-name clusters
        merged_clusters = []
        merged_first_names = set()

        for cluster in full_name_clusters:
            canonical = cluster['canonical_name']
            first_name = self._get_first_name(canonical)

            # Check if there's a matching first-name-only cluster
            if first_name in first_name_only and first_name not in merged_first_names:
                first_only_cluster = first_name_only[first_name]

                # CRITICAL: Only merge if they share at least one obituary
                # This prevents merging "Ryan" from obituary A with "Ryan Smith" from obituary B
                cluster_obits = set(cluster['obituary_ids'])
                first_only_obits = set(first_only_cluster['obituary_ids'])
                shared_obits = cluster_obits & first_only_obits

                if not shared_obits:
                    # Different obituaries - don't merge, these are likely different people
                    merged_clusters.append(cluster)
                    continue

                # Same obituary - check relationship context for additional validation
                cluster_relations = set()
                for fact in cluster['facts']:
                    if fact.related_name:
                        cluster_relations.add(fact.related_name)
                    cluster_relations.add(fact.subject_name)

                first_only_relations = set()
                for fact in first_only_cluster['facts']:
                    if fact.related_name:
                        first_only_relations.add(fact.related_name)
                    first_only_relations.add(fact.subject_name)

                # Check for exact match in relations (within same obituary context)
                common_exact = cluster_relations & first_only_relations

                if common_exact:
                    # Merge the clusters, but DON'T add first-name-only as a variant
                    # Filter out first-name-only entries from variants
                    full_name_variants = [v for v in first_only_cluster['name_variants'] if ' ' in v]
                    cluster['name_variants'] = sorted(list(
                        set(cluster['name_variants']) | set(full_name_variants)
                    ))
                    cluster['facts'] = list({f.id: f for f in cluster['facts'] + first_only_cluster['facts']}.values())
                    cluster['fact_count'] = len(cluster['facts'])
                    cluster['obituary_ids'] = list(set(cluster['obituary_ids']) | set(first_only_cluster['obituary_ids']))
                    cluster['obituary_count'] = len(cluster['obituary_ids'])
                    merged_first_names.add(first_name)

            merged_clusters.append(cluster)

        # Add unmerged first-name-only clusters
        for first_name, cluster in first_name_only.items():
            if first_name not in merged_first_names:
                merged_clusters.append(cluster)

        return merged_clusters

    def _merge_by_maiden_name(self, clusters: List[Dict]) -> List[Dict]:
        """Merge clusters where maiden name links to married name."""
        maiden_links = self._find_maiden_name_links()

        if not maiden_links:
            return clusters

        # Build index of clusters by normalized canonical name
        cluster_by_name = {}
        for cluster in clusters:
            for variant in cluster['name_variants']:
                cluster_by_name[variant.lower()] = cluster

        # Find clusters to merge
        merge_map = {}  # cluster_id -> target_cluster

        for maiden_name, married_name in maiden_links.items():
            maiden_cluster = cluster_by_name.get(maiden_name)
            married_cluster = cluster_by_name.get(married_name.lower())

            if maiden_cluster and married_cluster and maiden_cluster != married_cluster:
                # Merge maiden into married
                maiden_id = id(maiden_cluster)
                married_id = id(married_cluster)
                merge_map[maiden_id] = married_cluster

        # Apply merges
        merged_ids = set()
        result = []

        for cluster in clusters:
            cluster_id = id(cluster)

            if cluster_id in merge_map:
                target = merge_map[cluster_id]
                # Merge into target
                target['name_variants'] = sorted(list(
                    set(target['name_variants']) | set(cluster['name_variants'])
                ))
                target['facts'] = list({f.id: f for f in target['facts'] + cluster['facts']}.values())
                target['fact_count'] = len(target['facts'])
                target['obituary_ids'] = list(set(target['obituary_ids']) | set(cluster['obituary_ids']))
                target['obituary_count'] = len(target['obituary_ids'])
                merged_ids.add(cluster_id)
            elif cluster_id not in merged_ids:
                result.append(cluster)

        return result

    def _merge_by_spelling_variants(self, clusters: List[Dict]) -> List[Dict]:
        """Merge clusters with spelling variants like Rose Mary / Rosemary."""
        # Build index by normalized given name (no spaces)
        given_name_index = defaultdict(list)

        for cluster in clusters:
            canonical = cluster['canonical_name']
            parts = canonical.split()
            if len(parts) >= 2:
                # Get given name(s) - everything except last word (surname)
                given = ' '.join(parts[:-1])
                surname = parts[-1]
                normalized_given = self._normalize_given_name(given)
                key = (normalized_given, surname.lower())
                given_name_index[key].append(cluster)

        # Merge clusters with same normalized given name + surname
        merged_ids = set()
        result = []

        for key, matching_clusters in given_name_index.items():
            if len(matching_clusters) > 1:
                # Merge all into the first one (longest canonical name)
                matching_clusters.sort(key=lambda c: len(c['canonical_name']), reverse=True)
                target = matching_clusters[0]

                for cluster in matching_clusters[1:]:
                    target['name_variants'] = sorted(list(
                        set(target['name_variants']) | set(cluster['name_variants'])
                    ))
                    target['facts'] = list({f.id: f for f in target['facts'] + cluster['facts']}.values())
                    target['fact_count'] = len(target['facts'])
                    target['obituary_ids'] = list(set(target['obituary_ids']) | set(cluster['obituary_ids']))
                    target['obituary_count'] = len(target['obituary_ids'])
                    merged_ids.add(id(cluster))

        for cluster in clusters:
            if id(cluster) not in merged_ids:
                result.append(cluster)

        return result

    def _merge_by_fuzzy_matching(self, clusters: List[Dict]) -> List[Dict]:
        """
        Merge clusters where canonical names are fuzzy matches.

        Uses PersonMatcher to detect:
        - Nicknames (Patricia vs Pat vs Patsy)
        - Phonetically similar names (typos, alternate spellings)
        - High-confidence fuzzy matches
        """
        if len(clusters) < 2:
            return clusters

        # Build index of canonical names to cluster index
        name_to_cluster_idx = {}
        for idx, cluster in enumerate(clusters):
            name_to_cluster_idx[cluster['canonical_name']] = idx

        # Track which clusters should be merged
        # merge_map[idx] = target_idx means cluster at idx should merge into target_idx
        merge_map = {}

        canonical_names = [c['canonical_name'] for c in clusters]

        for i, cluster in enumerate(clusters):
            if i in merge_map:
                continue  # Already being merged into another

            canonical = cluster['canonical_name']

            # Find fuzzy matches among remaining clusters
            remaining_names = canonical_names[i+1:]
            if not remaining_names:
                continue

            matches = self.person_matcher.find_potential_matches(
                canonical,
                remaining_names,
                min_confidence=0.85
            )

            for matched_name, match_result in matches:
                matched_idx = name_to_cluster_idx.get(matched_name)
                if matched_idx is None or matched_idx in merge_map:
                    continue

                # Additional validation: same surname required for fuzzy matches
                _, surname1 = self.person_matcher.extract_first_last(canonical)
                _, surname2 = self.person_matcher.extract_first_last(matched_name)

                if surname1.lower() != surname2.lower():
                    # Only merge different surnames if it's a known nickname match
                    # (PersonMatcher checks phonetic similarity for surnames)
                    if match_result['method'] not in ['known_nickname', 'exact_normalized']:
                        continue

                print(f"  Fuzzy merge: '{canonical}' <- '{matched_name}' "
                      f"(method={match_result['method']}, score={match_result['score']})")
                merge_map[matched_idx] = i

        # Apply merges
        if not merge_map:
            return clusters

        # Merge clusters
        for source_idx, target_idx in merge_map.items():
            source = clusters[source_idx]
            target = clusters[target_idx]

            # Merge name variants
            target['name_variants'] = sorted(list(
                set(target['name_variants']) | set(source['name_variants'])
            ))

            # Merge facts (deduplicate by ID)
            target['facts'] = list({f.id: f for f in target['facts'] + source['facts']}.values())
            target['fact_count'] = len(target['facts'])

            # Merge obituary IDs
            target['obituary_ids'] = list(set(target['obituary_ids']) | set(source['obituary_ids']))
            target['obituary_count'] = len(target['obituary_ids'])

            # Update canonical name to longest variant
            all_variants = target['name_variants']
            target['canonical_name'] = max(all_variants, key=len)

        # Return clusters that weren't merged away
        result = [c for i, c in enumerate(clusters) if i not in merge_map]

        return result

    def create_person_cluster_records(self, clusters: List[Dict]) -> List[PersonCluster]:
        """Create PersonCluster records and link facts."""
        # Clear existing assignments
        self.db.query(ExtractedFact).update({
            ExtractedFact.person_cluster_id: None,
            ExtractedFact.subject_cluster_id: None,
            ExtractedFact.related_cluster_id: None,
            ExtractedFact.resolution_status: 'unresolved'
        })

        # Delete existing clusters
        self.db.query(PersonCluster).delete()
        self.db.commit()

        cluster_records = []

        for cluster_data in clusters:
            # Extract metadata from facts
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
            self.db.flush()

            # Link facts to this cluster
            cluster_name_variants = list(cluster_data['name_variants'])

            # Facts where this person is the subject
            self.db.query(ExtractedFact).filter(
                ExtractedFact.subject_name.in_(cluster_name_variants)
            ).update({
                ExtractedFact.person_cluster_id: cluster.id,
                ExtractedFact.subject_cluster_id: cluster.id,
                ExtractedFact.resolution_status: 'clustered'
            }, synchronize_session=False)

            # Facts where this person is mentioned as related
            self.db.query(ExtractedFact).filter(
                ExtractedFact.related_name.in_(cluster_name_variants)
            ).update({
                ExtractedFact.related_cluster_id: cluster.id
            }, synchronize_session=False)

            cluster_records.append(cluster)

        self.db.commit()
        print(f"Created {len(cluster_records)} PersonCluster records")

        return cluster_records

    def get_cluster_summary(self, cluster_id: int) -> Optional[Dict]:
        """
        Get person details aggregated from all obituaries.

        Shows facts where this person is:
        1. The subject (their own facts)
        2. Related to someone else (inverted to show from their perspective)
        """
        cluster = self.db.query(PersonCluster).filter(
            PersonCluster.id == cluster_id
        ).first()

        if not cluster:
            return None

        # Facts where this person is the subject
        subject_facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.person_cluster_id == cluster_id
        ).all()

        # Facts where this person is related (need to invert perspective)
        related_facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.related_cluster_id == cluster_id,
            ExtractedFact.fact_type.in_(['relationship', 'marriage'])
        ).all()

        # Group facts by type
        facts_by_type = defaultdict(list)

        for fact in subject_facts:
            facts_by_type[fact.fact_type].append(fact)

        # Add inverted relationship facts (avoid duplicates)
        for fact in related_facts:
            # Skip if we already have this relationship from subject side
            dominated = False
            for existing in facts_by_type.get(fact.fact_type, []):
                if isinstance(existing, dict):
                    if existing.get('related_name') == fact.subject_name:
                        dominated = True
                        break
                elif existing.related_name == fact.subject_name:
                    dominated = True
                    break

            if dominated:
                continue

            # Create inverted view
            inverted = {
                'fact_value': self._get_inverse_relationship(fact.fact_value) or fact.fact_value,
                'confidence': float(fact.confidence_score),
                'is_inferred': fact.is_inferred,
                'extracted_context': fact.extracted_context,
                'obituary_id': fact.obituary_cache_id,
                'subject_cluster_id': cluster_id,
                'related_name': fact.subject_name,
                'related_cluster_id': fact.subject_cluster_id,
            }
            facts_by_type[fact.fact_type].append(inverted)

        # Get source obituaries
        all_facts = subject_facts + related_facts
        obituary_ids = list(set(f.obituary_cache_id for f in all_facts))
        obituaries = self.db.query(ObituaryCache).filter(
            ObituaryCache.id.in_(obituary_ids)
        ).all() if obituary_ids else []

        def format_fact(f):
            if isinstance(f, dict):
                return f
            return {
                'fact_value': f.fact_value,
                'confidence': float(f.confidence_score),
                'is_inferred': f.is_inferred,
                'extracted_context': f.extracted_context,
                'obituary_id': f.obituary_cache_id,
                'subject_cluster_id': f.subject_cluster_id,
                'related_name': f.related_name,
                'related_cluster_id': f.related_cluster_id
            }

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
                fact_type: [format_fact(f) for f in facts_list]
                for fact_type, facts_list in facts_by_type.items()
            }
        }

    def _get_inverse_relationship(self, relationship: str) -> Optional[str]:
        """Get the inverse of a relationship type."""
        inverse_map = {
            'child': 'parent',
            'parent': 'child',
            'sibling': 'sibling',
            'spouse': 'spouse',
            'grandchild': 'grandparent',
            'grandparent': 'grandchild',
        }
        return inverse_map.get(relationship)

    def detect_conflicts(self, cluster_id: int) -> List[Dict]:
        """Detect conflicting facts within a cluster."""
        facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.person_cluster_id == cluster_id
        ).all()

        conflicts = []
        facts_by_type = defaultdict(list)

        for fact in facts:
            if fact.fact_type in ['person_death_date', 'person_birth_date', 'person_death_age']:
                facts_by_type[fact.fact_type].append(fact)

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
