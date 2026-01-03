"""
Service for creating and managing citations in Gramps Web.

Links person clusters to Gramps people with proper source/citation records.
"""

from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models import PersonCluster, ObituaryCache, GrampsCitation, ExtractedFact
from services.gramps_client import GrampsClient


class CitationService:
    """
    Manages citation creation and linking between clusters and Gramps.
    """

    # Confidence mapping from our system to Gramps (0=very low, 4=very high)
    CONFIDENCE_MAP = {
        'very_high': 4,
        'high': 3,
        'medium': 2,
        'low': 1
    }

    def __init__(self, db: Session, gramps_client: GrampsClient = None):
        self.db = db
        self.gramps = gramps_client or GrampsClient()

    def link_cluster_to_gramps(
        self,
        cluster_id: int,
        gramps_person_id: str,
        gramps_handle: str,
        confidence: str = 'high'
    ) -> Dict:
        """
        Link a person cluster to a Gramps person and create citations.

        This is the main method for establishing the connection between
        our extracted data and the Gramps SSOT.

        Args:
            cluster_id: PersonCluster ID
            gramps_person_id: Gramps person ID (e.g., "I0071")
            gramps_handle: Gramps person handle
            confidence: Match confidence level

        Returns:
            Dict with results including citations created
        """
        # Get cluster
        cluster = self.db.query(PersonCluster).filter(
            PersonCluster.id == cluster_id
        ).first()

        if not cluster:
            return {'success': False, 'error': 'Cluster not found'}

        # Update cluster with Gramps ID
        cluster.gramps_person_id = gramps_person_id
        cluster.cluster_status = 'verified'

        # Update all facts in this cluster with gramps_person_id
        self.db.query(ExtractedFact).filter(
            ExtractedFact.person_cluster_id == cluster_id
        ).update({
            'gramps_person_id': gramps_person_id,
            'resolution_status': 'resolved'
        })

        # Get all obituaries that contributed facts to this cluster
        obituary_ids = self.db.query(ExtractedFact.obituary_cache_id).filter(
            ExtractedFact.person_cluster_id == cluster_id
        ).distinct().all()

        obituary_ids = [oid[0] for oid in obituary_ids]

        # Create citations for each obituary
        citations_created = []
        citations_skipped = []

        for obit_id in obituary_ids:
            result = self._create_citation_for_obituary(
                obituary_cache_id=obit_id,
                cluster_id=cluster_id,
                gramps_person_id=gramps_person_id,
                gramps_handle=gramps_handle,
                confidence=confidence
            )

            if result.get('success'):
                citations_created.append(result)
            elif result.get('skipped'):
                citations_skipped.append(result)
            else:
                # Log error but continue
                print(f"Failed to create citation for obituary {obit_id}: {result.get('error')}")

        self.db.commit()

        return {
            'success': True,
            'cluster_id': cluster_id,
            'gramps_person_id': gramps_person_id,
            'citations_created': len(citations_created),
            'citations_skipped': len(citations_skipped),
            'details': citations_created
        }

    def _create_citation_for_obituary(
        self,
        obituary_cache_id: int,
        cluster_id: int,
        gramps_person_id: str,
        gramps_handle: str,
        confidence: str = 'high'
    ) -> Dict:
        """
        Create a citation linking an obituary to a Gramps person.

        Args:
            obituary_cache_id: ObituaryCache ID
            cluster_id: PersonCluster ID
            gramps_person_id: Gramps person ID
            gramps_handle: Gramps person handle
            confidence: Confidence level

        Returns:
            Dict with citation details or error
        """
        # Check if citation already exists
        existing = self.db.query(GrampsCitation).filter(
            and_(
                GrampsCitation.gramps_person_id == gramps_person_id,
                GrampsCitation.obituary_cache_id == obituary_cache_id
            )
        ).first()

        if existing:
            return {
                'skipped': True,
                'reason': 'Citation already exists',
                'citation_id': existing.id
            }

        # Get obituary
        obituary = self.db.query(ObituaryCache).filter(
            ObituaryCache.id == obituary_cache_id
        ).first()

        if not obituary:
            return {'success': False, 'error': 'Obituary not found'}

        # Get the deceased primary person name from facts
        primary_fact = self.db.query(ExtractedFact).filter(
            and_(
                ExtractedFact.obituary_cache_id == obituary_cache_id,
                ExtractedFact.subject_role == 'deceased_primary',
                ExtractedFact.fact_type == 'person_name'
            )
        ).first()

        deceased_name = primary_fact.fact_value if primary_fact else "Unknown"

        # Create or find source in Gramps
        source_title = f"Obituary of {deceased_name}"
        source_result = self.gramps.find_or_create_source(
            title=source_title,
            url=obituary.url,
            author=None,
            pubinfo=None
        )

        if not source_result:
            return {'success': False, 'error': 'Failed to create source in Gramps'}

        gramps_source_id, source_handle = source_result

        # Create citation in Gramps
        citation_note = f"Extracted from obituary: {deceased_name}"

        gramps_confidence = self.CONFIDENCE_MAP.get(confidence, 2)

        gramps_citation = self.gramps.create_citation(
            source_handle=source_handle,
            page=obituary.url,
            confidence=gramps_confidence,
            note=citation_note
        )

        if not gramps_citation:
            return {'success': False, 'error': 'Failed to create citation in Gramps'}

        gramps_citation_id = gramps_citation.get('gramps_id')
        citation_handle = gramps_citation.get('handle')

        # Add citation to person in Gramps
        if citation_handle:
            self.gramps.add_citation_to_person(
                person_handle=gramps_handle,
                citation_handle=citation_handle
            )

        # Record in our database (with denormalized obituary_name for audit trail)
        local_citation = GrampsCitation(
            obituary_cache_id=obituary_cache_id,
            person_cluster_id=cluster_id,
            gramps_person_id=gramps_person_id,
            gramps_source_id=gramps_source_id,
            gramps_citation_id=gramps_citation_id,
            citation_type='obituary',
            obituary_name=f"Obituary of {deceased_name}",
            confidence=confidence
        )

        self.db.add(local_citation)

        return {
            'success': True,
            'obituary_id': obituary_cache_id,
            'gramps_source_id': gramps_source_id,
            'gramps_citation_id': gramps_citation_id,
            'local_citation_id': local_citation.id if local_citation.id else 'pending'
        }

    def get_cluster_citations(self, cluster_id: int) -> List[Dict]:
        """
        Get all citations for a cluster.

        Args:
            cluster_id: PersonCluster ID

        Returns:
            List of citation records
        """
        citations = self.db.query(GrampsCitation).filter(
            GrampsCitation.person_cluster_id == cluster_id
        ).all()

        result = []
        for citation in citations:
            # Get obituary URL
            obituary = self.db.query(ObituaryCache).filter(
                ObituaryCache.id == citation.obituary_cache_id
            ).first()

            # Use denormalized obituary_name, fallback to lookup for legacy records
            obituary_name = citation.obituary_name
            if not obituary_name and obituary:
                primary_fact = self.db.query(ExtractedFact).filter(
                    and_(
                        ExtractedFact.obituary_cache_id == obituary.id,
                        ExtractedFact.subject_role == 'deceased_primary',
                        ExtractedFact.fact_type == 'person_name'
                    )
                ).first()
                obituary_name = f"Obituary of {primary_fact.fact_value}" if primary_fact else None

            result.append({
                'id': citation.id,
                'obituary_cache_id': citation.obituary_cache_id,
                'obituary_name': obituary_name,
                'obituary_url': obituary.url if obituary else None,
                'gramps_person_id': citation.gramps_person_id,
                'gramps_source_id': citation.gramps_source_id,
                'gramps_citation_id': citation.gramps_citation_id,
                'citation_type': citation.citation_type,
                'confidence': citation.confidence,
                'created_timestamp': citation.created_timestamp.isoformat() if citation.created_timestamp else None
            })

        return result

    def get_person_citations(self, gramps_person_id: str) -> List[Dict]:
        """
        Get all citations for a Gramps person ID.

        Args:
            gramps_person_id: Gramps person ID (e.g., "I0071")

        Returns:
            List of citation records
        """
        citations = self.db.query(GrampsCitation).filter(
            GrampsCitation.gramps_person_id == gramps_person_id
        ).all()

        result = []
        for citation in citations:
            obituary = self.db.query(ObituaryCache).filter(
                ObituaryCache.id == citation.obituary_cache_id
            ).first()

            # Use denormalized obituary_name, fallback to lookup for legacy records
            obituary_name = citation.obituary_name
            if not obituary_name and obituary:
                primary_fact = self.db.query(ExtractedFact).filter(
                    and_(
                        ExtractedFact.obituary_cache_id == obituary.id,
                        ExtractedFact.subject_role == 'deceased_primary',
                        ExtractedFact.fact_type == 'person_name'
                    )
                ).first()
                obituary_name = f"Obituary of {primary_fact.fact_value}" if primary_fact else None

            result.append({
                'id': citation.id,
                'obituary_cache_id': citation.obituary_cache_id,
                'obituary_name': obituary_name,
                'obituary_url': obituary.url if obituary else None,
                'cluster_id': citation.person_cluster_id,
                'gramps_source_id': citation.gramps_source_id,
                'gramps_citation_id': citation.gramps_citation_id,
                'citation_type': citation.citation_type,
                'confidence': citation.confidence,
                'created_timestamp': citation.created_timestamp.isoformat() if citation.created_timestamp else None
            })

        return result

    def unlink_cluster(self, cluster_id: int) -> Dict:
        """
        Remove Gramps link from a cluster (does NOT delete Gramps data).

        Args:
            cluster_id: PersonCluster ID

        Returns:
            Dict with results
        """
        cluster = self.db.query(PersonCluster).filter(
            PersonCluster.id == cluster_id
        ).first()

        if not cluster:
            return {'success': False, 'error': 'Cluster not found'}

        old_gramps_id = cluster.gramps_person_id

        # Clear Gramps ID from cluster
        cluster.gramps_person_id = None
        cluster.cluster_status = 'unverified'

        # Clear from facts
        self.db.query(ExtractedFact).filter(
            ExtractedFact.person_cluster_id == cluster_id
        ).update({
            'gramps_person_id': None,
            'resolution_status': 'clustered'
        })

        # Delete local citation records (Gramps citations remain)
        deleted_count = self.db.query(GrampsCitation).filter(
            GrampsCitation.person_cluster_id == cluster_id
        ).delete()

        self.db.commit()

        return {
            'success': True,
            'cluster_id': cluster_id,
            'previous_gramps_id': old_gramps_id,
            'citations_removed': deleted_count
        }

    def get_audit_trail(self, limit: int = 50) -> List[Dict]:
        """
        Get recent citation audit trail with readable obituary names.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of citation records ordered by creation date (newest first)
        """
        citations = self.db.query(GrampsCitation).order_by(
            GrampsCitation.created_timestamp.desc()
        ).limit(limit).all()

        result = []
        for citation in citations:
            # Get cluster name if available
            cluster_name = None
            if citation.person_cluster_id:
                cluster = self.db.query(PersonCluster).filter(
                    PersonCluster.id == citation.person_cluster_id
                ).first()
                cluster_name = cluster.canonical_name if cluster else None

            # Use denormalized obituary_name, fallback to lookup for legacy records
            obituary_name = citation.obituary_name
            if not obituary_name:
                obituary = self.db.query(ObituaryCache).filter(
                    ObituaryCache.id == citation.obituary_cache_id
                ).first()
                if obituary:
                    # Try deceased_primary first
                    primary_fact = self.db.query(ExtractedFact).filter(
                        and_(
                            ExtractedFact.obituary_cache_id == obituary.id,
                            ExtractedFact.subject_role == 'deceased_primary',
                            ExtractedFact.fact_type == 'person_name'
                        )
                    ).first()
                    # Fallback to first person_name fact
                    if not primary_fact:
                        primary_fact = self.db.query(ExtractedFact).filter(
                            and_(
                                ExtractedFact.obituary_cache_id == obituary.id,
                                ExtractedFact.fact_type == 'person_name'
                            )
                        ).first()
                    obituary_name = f"Obituary of {primary_fact.subject_name}" if primary_fact else None

            result.append({
                'id': citation.id,
                'obituary_name': obituary_name,
                'cluster_name': cluster_name,
                'gramps_person_id': citation.gramps_person_id,
                'gramps_source_id': citation.gramps_source_id,
                'gramps_citation_id': citation.gramps_citation_id,
                'confidence': citation.confidence,
                'created_timestamp': citation.created_timestamp.isoformat() if citation.created_timestamp else None,
                'created_by': citation.created_by
            })

        return result
