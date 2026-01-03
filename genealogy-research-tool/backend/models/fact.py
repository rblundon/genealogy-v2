from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Boolean, Enum, DECIMAL, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class ExtractedFact(Base):
    """Individual factual claims extracted from obituaries"""
    __tablename__ = 'extracted_facts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    obituary_cache_id = Column(Integer, ForeignKey('obituary_cache.id'), nullable=False)
    llm_cache_id = Column(Integer, ForeignKey('llm_cache.id'))

    fact_type = Column(
        Enum(
            'person_name',
            'person_nickname',
            'person_death_date',
            'person_death_age',
            'person_birth_date',
            'person_gender',
            'maiden_name',
            'relationship',
            'marriage',
            'marriage_duration',
            'location_birth',
            'location_death',
            'location_residence',
            'survived_by',
            'preceded_in_death'
        ),
        nullable=False,
        index=True
    )

    subject_name = Column(String(255), nullable=False, index=True)
    subject_role = Column(
        Enum(
            'deceased_primary',
            'spouse',
            'child',
            'parent',
            'sibling',
            'grandchild',
            'grandparent',
            'great_grandchild',
            'in_law',
            'other'
        ),
        default='other',
        index=True
    )

    fact_value = Column(Text, nullable=False)

    related_name = Column(String(255))
    relationship_type = Column(String(100))

    extracted_context = Column(Text)
    source_sentence = Column(Text)

    is_inferred = Column(Boolean, default=False)
    inference_basis = Column(Text)

    confidence_score = Column(DECIMAL(3, 2), nullable=False, index=True)

    person_cluster_id = Column(Integer, index=True)
    gramps_person_id = Column(String(50), index=True)
    resolution_status = Column(
        Enum('unresolved', 'clustered', 'resolved', 'conflicting', 'rejected'),
        default='unresolved',
        index=True
    )
    resolution_notes = Column(Text)
    resolved_timestamp = Column(TIMESTAMP)

    created_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp(),
                              onupdate=func.current_timestamp())

    # Relationships
    obituary = relationship("ObituaryCache", back_populates="extracted_facts")

    def __repr__(self):
        return (f"<ExtractedFact(id={self.id}, type='{self.fact_type}', "
                f"subject='{self.subject_name}', confidence={self.confidence_score})>")

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'fact_type': self.fact_type,
            'subject_name': self.subject_name,
            'subject_role': self.subject_role,
            'fact_value': self.fact_value,
            'related_name': self.related_name,
            'relationship_type': self.relationship_type,
            'extracted_context': self.extracted_context,
            'is_inferred': self.is_inferred,
            'inference_basis': self.inference_basis,
            'confidence_score': float(self.confidence_score) if self.confidence_score else None,
            'resolution_status': self.resolution_status,
        }


class PersonCluster(Base):
    """Represents the same person across multiple obituaries"""
    __tablename__ = 'person_clusters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_name = Column(String(255), nullable=False, index=True)
    name_variants = Column(Text, nullable=False)  # JSON string
    nicknames = Column(Text)  # JSON string
    maiden_names = Column(Text)  # JSON string

    gramps_person_id = Column(String(50), unique=True, index=True)

    confidence_score = Column(DECIMAL(3, 2))
    source_count = Column(Integer, default=1, index=True)
    fact_count = Column(Integer, default=0)

    cluster_status = Column(
        Enum('unverified', 'verified', 'conflicting', 'resolved'),
        default='unverified'
    )

    created_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp(),
                              onupdate=func.current_timestamp())

    def __repr__(self):
        return f"<PersonCluster(id={self.id}, name='{self.canonical_name}', sources={self.source_count})>"


class GrampsCitation(Base):
    """
    Tracks citations created in Gramps Web from obituaries.

    Maintains audit trail of all writes to SSOT.
    """
    __tablename__ = 'gramps_citations'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Link to our data
    obituary_cache_id = Column(Integer, ForeignKey('obituary_cache.id', ondelete='CASCADE'), nullable=False)
    person_cluster_id = Column(Integer, ForeignKey('person_clusters.id', ondelete='CASCADE'))

    # Gramps identifiers
    gramps_person_id = Column(String(50), nullable=False, index=True)  # e.g., "I0071"
    gramps_source_id = Column(String(50), index=True)  # e.g., "S0001"
    gramps_citation_id = Column(String(50), index=True)  # e.g., "C0001"

    # Citation details
    citation_type = Column(String(50), default='obituary')
    obituary_name = Column(String(255))  # Denormalized for audit trail readability
    confidence = Column(Enum('very_high', 'high', 'medium', 'low'), default='high')

    # Metadata
    created_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())
    created_by = Column(String(100), default='genealogy_tool')

    # Relationships
    obituary = relationship("ObituaryCache")
    person_cluster = relationship("PersonCluster")

    def __repr__(self):
        return f"<GrampsCitation(person={self.gramps_person_id}, citation={self.gramps_citation_id})>"
