"""
Service for creating new people in Gramps Web from clusters.

Handles:
- Person creation with validation
- Event creation (birth, death)
- Relationship linking
- Citation creation
- Audit trail
"""

from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from models import PersonCluster, ExtractedFact, ObituaryCache, GrampsCitation
from services.gramps_client import GrampsClient
from services.gramps_citation_service import CitationService
import json


class PersonCreator:
    """
    Creates new people in Gramps from validated clusters.
    """

    def __init__(self, db: Session, gramps_client: GrampsClient = None):
        self.db = db
        self.gramps = gramps_client or GrampsClient()
        self.citation_service = CitationService(db, self.gramps)

    def create_person_from_cluster(
        self,
        cluster_id: int,
        create_relationships: bool = True
    ) -> Dict:
        """
        Create a new person in Gramps from a cluster.

        Args:
            cluster_id: PersonCluster ID
            create_relationships: Whether to create family relationships

        Returns:
            Summary of creation operation
        """
        # Get cluster
        cluster = self.db.query(PersonCluster).filter(
            PersonCluster.id == cluster_id
        ).first()

        if not cluster:
            raise ValueError(f"Cluster {cluster_id} not found")

        # Check if already linked
        if cluster.gramps_person_id:
            raise ValueError(f"Cluster already linked to Gramps person {cluster.gramps_person_id}")

        # Get all facts for cluster
        facts = self._get_cluster_facts(cluster)

        # Extract key facts
        person_data = self._extract_person_data(cluster, facts)

        # Validate minimum requirements
        if not person_data['given_name'] or not person_data['surname']:
            raise ValueError("Cannot create person without name")

        # Create person in Gramps
        gramps_person = self.gramps.create_person(
            given_name=person_data['given_name'],
            surname=person_data['surname'],
            gender=person_data.get('gender', 'U'),
            birth_date=person_data.get('birth_date'),
            death_date=person_data.get('death_date'),
            birth_place=person_data.get('birth_place'),
            death_place=person_data.get('death_place')
        )

        if not gramps_person:
            raise Exception("Failed to create person in Gramps")

        gramps_person_id = gramps_person.get('gramps_id')
        gramps_handle = gramps_person.get('handle')

        # Add alternate names (nicknames, married names)
        # Note: We no longer add maiden_names as alternates since maiden name is now PRIMARY
        for nickname in person_data.get('nicknames', []):
            if nickname != person_data['given_name']:
                self.gramps.add_alternate_name(
                    person_handle=gramps_handle,
                    given_name=nickname,
                    surname=person_data['surname'],
                    name_type='Also Known As'
                )

        # Add married surname(s) as alternate "Married Name" (GEDCOM convention)
        for married_surname in person_data.get('married_surnames', []):
            if married_surname != person_data['surname']:
                self.gramps.add_alternate_name(
                    person_handle=gramps_handle,
                    given_name=person_data['given_name'],
                    surname=married_surname,
                    name_type='Married Name'
                )

        # Create citations linking obituaries to this person
        citation_result = self.citation_service.link_cluster_to_gramps(
            cluster_id=cluster_id,
            gramps_person_id=gramps_person_id,
            gramps_handle=gramps_handle,
            confidence='high'
        )

        result = {
            'cluster_id': cluster_id,
            'cluster_name': cluster.canonical_name,
            'gramps_person_id': gramps_person_id,
            'gramps_handle': gramps_handle,
            'created': True,
            'citations_created': citation_result.get('citations_created', 0),
            'person_data': person_data,
            'relationships_created': []
        }

        # Create relationships if requested
        if create_relationships:
            rel_results = self._create_relationships(
                cluster_id=cluster_id,
                gramps_person_id=gramps_person_id,
                gramps_handle=gramps_handle,
                facts=facts
            )
            result['relationships_created'] = rel_results

        return result

    def _get_cluster_facts(self, cluster: PersonCluster) -> List[ExtractedFact]:
        """Get all facts for a cluster, trying multiple methods."""
        print(f"\n=== DEBUG: _get_cluster_facts for cluster {cluster.id} ({cluster.canonical_name}) ===")

        # Try by cluster ID first
        facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.person_cluster_id == cluster.id
        ).all()

        print(f"Facts found by person_cluster_id: {len(facts)}")

        if facts:
            fact_types = list(set(f.fact_type for f in facts))
            print(f"Fact types: {fact_types}")
            rel_facts = [f for f in facts if f.fact_type in ['relationship', 'marriage']]
            print(f"Relationship facts: {len(rel_facts)}")
            for rf in rel_facts:
                print(f"  - {rf.relationship_type} to {rf.related_name}")
            return facts

        # Fallback: find facts by name variants
        name_variants = json.loads(cluster.name_variants) if cluster.name_variants else [cluster.canonical_name]
        print(f"No facts found by cluster ID, trying name variants: {name_variants}")
        facts = self.db.query(ExtractedFact).filter(
            ExtractedFact.subject_name.in_(name_variants)
        ).all()

        print(f"Facts found by name variants: {len(facts)}")

        return facts

    def _extract_person_data(
        self,
        cluster: PersonCluster,
        facts: List[ExtractedFact]
    ) -> Dict:
        """
        Extract structured person data from cluster facts.
        """
        # Parse name from canonical_name
        name_parts = cluster.canonical_name.split()
        given_name = ' '.join(name_parts[:-1]) if len(name_parts) > 1 else name_parts[0]
        canonical_surname = name_parts[-1] if len(name_parts) > 1 else ''

        # Get maiden names from cluster
        maiden_names_list = json.loads(cluster.maiden_names) if cluster.maiden_names else []

        # GEDCOM convention: Use maiden/birth name as primary surname if available
        # Married name becomes alternate name
        if maiden_names_list:
            # Use first maiden name as primary surname (birth name)
            primary_surname = maiden_names_list[0]
            # If canonical surname differs from maiden name, it's a married name
            married_surnames = [canonical_surname] if canonical_surname != primary_surname else []
        else:
            # No maiden name available, use canonical surname
            primary_surname = canonical_surname
            married_surnames = []

        data = {
            'given_name': given_name,
            'surname': primary_surname,  # Birth/maiden name per GEDCOM standard
            'nicknames': json.loads(cluster.nicknames) if cluster.nicknames else [],
            'maiden_names': maiden_names_list,
            'married_surnames': married_surnames,  # Will become alternate "Married Name" entries
            'gender': None,
            'birth_date': None,
            'death_date': None,
            'death_age': None,
            'birth_place': None,
            'death_place': None
        }

        # Extract from facts
        for fact in facts:
            if fact.fact_type == 'person_death_date':
                data['death_date'] = self._normalize_date(fact.fact_value)
            elif fact.fact_type == 'person_death_age':
                data['death_age'] = fact.fact_value
            elif fact.fact_type == 'person_birth_date':
                data['birth_date'] = self._normalize_date(fact.fact_value)
            elif fact.fact_type == 'person_gender':
                data['gender'] = self._normalize_gender(fact.fact_value)
            elif fact.fact_type == 'location_birth':
                data['birth_place'] = fact.fact_value
            elif fact.fact_type == 'location_death':
                data['death_place'] = fact.fact_value

        # Infer birth date from death date and age if missing
        if not data['birth_date'] and data['death_date'] and data['death_age']:
            try:
                death_year = int(data['death_date'].split('-')[0])
                age = int(''.join(filter(str.isdigit, str(data['death_age']))))
                birth_year = death_year - age
                data['birth_date'] = f"{birth_year}"  # Year only (approximate)
            except:
                pass

        return data

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalize date string to ISO format if possible."""
        if not date_str:
            return None

        # Already ISO format
        if '-' in date_str and len(date_str.split('-')[0]) == 4:
            return date_str

        # Strip day-of-week prefix if present (e.g., "Thursday, August 7, 2008")
        import re
        date_str = re.sub(r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s*', '', date_str.strip(), flags=re.IGNORECASE)

        # Try common formats
        from datetime import datetime
        formats = [
            '%B %d, %Y',      # August 7, 2008
            '%b %d, %Y',      # Aug 7, 2008
            '%m/%d/%Y',       # 08/07/2008
            '%Y-%m-%d',       # 2008-08-07
            '%d %B %Y',       # 7 August 2008
            '%B %Y',          # August 2008
            '%Y',             # 2008
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime('%Y-%m-%d')
            except:
                continue

        return date_str  # Return as-is if can't parse

    def _normalize_gender(self, gender_str: str) -> str:
        """Normalize gender string to M/F/U."""
        if not gender_str:
            return 'U'

        g = gender_str.lower().strip()
        if g in ['m', 'male', 'man']:
            return 'M'
        elif g in ['f', 'female', 'woman']:
            return 'F'
        return 'U'

    def _create_relationships(
        self,
        cluster_id: int,
        gramps_person_id: str,
        gramps_handle: str,
        facts: List[ExtractedFact]
    ) -> List[Dict]:
        """
        Create family relationships for the person.

        Only creates relationships to people already in Gramps.
        """
        print(f"\n=== DEBUG: _create_relationships ===")
        print(f"Cluster ID: {cluster_id}")
        print(f"Gramps Person ID: {gramps_person_id}")
        print(f"Total facts provided: {len(facts)}")

        relationships = []

        # Get relationship facts
        rel_facts = [f for f in facts if f.fact_type in ['relationship', 'marriage', 'survived_by', 'preceded_in_death']]

        print(f"Relationship facts found: {len(rel_facts)}")
        for fact in rel_facts:
            print(f"  - {fact.fact_type}: {fact.relationship_type} to '{fact.related_name}'")

        for fact in rel_facts:
            if not fact.related_name:
                print(f"  SKIP: No related_name for fact {fact.id}")
                continue

            print(f"\nProcessing: {fact.relationship_type} to '{fact.related_name}'")

            # Find if related person is in Gramps
            related_cluster = None

            # First, use related_cluster_id if set (most reliable)
            if fact.related_cluster_id:
                related_cluster = self.db.query(PersonCluster).filter(
                    PersonCluster.id == fact.related_cluster_id
                ).first()
                if related_cluster:
                    print(f"  Found via related_cluster_id: {related_cluster.canonical_name}")

            # Fallback: try exact canonical_name match
            if not related_cluster:
                related_cluster = self.db.query(PersonCluster).filter(
                    PersonCluster.canonical_name == fact.related_name
                ).first()
                if related_cluster:
                    print(f"  Found via canonical_name match")

            # Fallback: try matching against name_variants
            if not related_cluster:
                all_clusters = self.db.query(PersonCluster).all()
                for cluster in all_clusters:
                    name_variants = json.loads(cluster.name_variants) if cluster.name_variants else [cluster.canonical_name]
                    if fact.related_name in name_variants:
                        related_cluster = cluster
                        print(f"  Found via name_variants: {cluster.canonical_name}")
                        break
                    # Also try partial match (e.g., "Terrence Kaczmarowski" in "Terrence E. Kaczmarowski")
                    for variant in name_variants:
                        if fact.related_name.lower() in variant.lower() or variant.lower() in fact.related_name.lower():
                            related_cluster = cluster
                            print(f"  Found via partial match: '{fact.related_name}' ~ '{variant}'")
                            break
                    if related_cluster:
                        break

            if not related_cluster:
                print(f"  NOT FOUND: No cluster matches '{fact.related_name}'")
                continue

            if not related_cluster.gramps_person_id:
                print(f"  SKIP: Cluster found but no gramps_person_id (not in Gramps yet)")
                continue

            print(f"  FOUND: Cluster {related_cluster.id} with gramps_person_id = {related_cluster.gramps_person_id}")

            # Get related person's handle
            related_person = self.gramps.get_person(related_cluster.gramps_person_id)
            if not related_person:
                continue

            related_handle = related_person.get('handle')

            # Determine relationship type and create family
            rel_type = (fact.relationship_type or fact.fact_value or '').lower()

            if rel_type in ['spouse', 'wife', 'husband', 'married']:
                # Create spousal family
                family = self.gramps.create_family(
                    parent1_handle=gramps_handle,
                    parent2_handle=related_handle,
                    relationship_type='Married'
                )

                if family:
                    relationships.append({
                        'type': 'spouse',
                        'related_name': fact.related_name,
                        'related_person_id': related_cluster.gramps_person_id,
                        'family_id': family.get('gramps_id')
                    })

            elif rel_type in ['child', 'son', 'daughter']:
                # This person is parent of related person
                family = self.gramps.create_family(
                    parent1_handle=gramps_handle,
                    child_handles=[related_handle]
                )

                if family:
                    relationships.append({
                        'type': 'parent_of',
                        'related_name': fact.related_name,
                        'related_person_id': related_cluster.gramps_person_id,
                        'family_id': family.get('gramps_id')
                    })

            elif rel_type in ['parent', 'mother', 'father']:
                # This person is child of related person
                family = self.gramps.create_family(
                    parent1_handle=related_handle,
                    child_handles=[gramps_handle]
                )

                if family:
                    relationships.append({
                        'type': 'child_of',
                        'related_name': fact.related_name,
                        'related_person_id': related_cluster.gramps_person_id,
                        'family_id': family.get('gramps_id')
                    })

        return relationships

    def preview_person_creation(self, cluster_id: int) -> Dict:
        """
        Preview what would be created without actually creating.

        Returns structured data showing what will be created.
        """
        cluster = self.db.query(PersonCluster).filter(
            PersonCluster.id == cluster_id
        ).first()

        if not cluster:
            raise ValueError(f"Cluster {cluster_id} not found")

        if cluster.gramps_person_id:
            raise ValueError(f"Cluster already linked to Gramps person {cluster.gramps_person_id}")

        facts = self._get_cluster_facts(cluster)
        person_data = self._extract_person_data(cluster, facts)

        # Find relationship facts
        rel_facts = [f for f in facts if f.fact_type in ['relationship', 'marriage', 'survived_by', 'preceded_in_death']]

        relationships = []
        for fact in rel_facts:
            if not fact.related_name:
                continue

            related_cluster = self.db.query(PersonCluster).filter(
                PersonCluster.canonical_name == fact.related_name
            ).first()

            relationships.append({
                'type': fact.relationship_type or fact.fact_value,
                'related_name': fact.related_name,
                'related_in_gramps': related_cluster.gramps_person_id if related_cluster else None,
                'will_create_link': bool(related_cluster and related_cluster.gramps_person_id)
            })

        # Get obituary sources
        obituary_ids = list(set(f.obituary_cache_id for f in facts))
        obituaries = self.db.query(ObituaryCache).filter(
            ObituaryCache.id.in_(obituary_ids)
        ).all()

        return {
            'cluster_id': cluster_id,
            'cluster_name': cluster.canonical_name,
            'confidence': float(cluster.confidence_score) if cluster.confidence_score else None,
            'source_count': cluster.source_count,
            'fact_count': len(facts),
            'person_data': person_data,
            'relationships': relationships,
            'sources': [
                {
                    'obituary_id': obit.id,
                    'url': obit.url,
                    'fetch_date': obit.fetch_timestamp.isoformat() if obit.fetch_timestamp else None
                }
                for obit in obituaries
            ],
            'warnings': self._get_creation_warnings(person_data, relationships)
        }

    def _get_creation_warnings(self, person_data: Dict, relationships: List[Dict]) -> List[str]:
        """Generate warnings about potential issues."""
        warnings = []

        if not person_data.get('birth_date') and not person_data.get('death_date'):
            warnings.append("No dates found - person will be created without birth/death dates")

        if not person_data.get('gender'):
            warnings.append("Gender not determined - will be set to Unknown")

        unlinked_rels = [r for r in relationships if not r.get('will_create_link')]
        if unlinked_rels:
            names = [r['related_name'] for r in unlinked_rels]
            warnings.append(f"Relationships cannot be created (not in Gramps): {', '.join(names)}")

        return warnings
