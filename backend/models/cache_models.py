# FILE: backend/models/cache_models.py
# SQLAlchemy models for cache database - FACT-BASED ARCHITECTURE
# ============================================================================

from sqlalchemy import (
    Column, Integer, String, Text, TIMESTAMP, Boolean,
    Enum, ForeignKey, Index, DECIMAL, JSON, VARCHAR, DATE
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from .database import Base


class ObituaryCache(Base):
    """Stores raw obituary content and metadata"""
    __tablename__ = 'obituary_cache'

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), unique=True, nullable=False)
    url_hash = Column(String(64), nullable=False, index=True)
    content_hash = Column(String(64))
    raw_html = Column(MEDIUMTEXT)
    extracted_text = Column(Text)
    fetch_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())
    last_accessed = Column(TIMESTAMP, server_default=func.current_timestamp(),
                          onupdate=func.current_timestamp())
    http_status_code = Column(Integer)
    fetch_error = Column(Text)
    processing_status = Column(
        Enum('pending', 'processing', 'completed', 'failed'),
        default='pending',
        index=True
    )

    # Relationships
    llm_cache_entries = relationship("LLMCache", back_populates="obituary", cascade="all, delete-orphan")
    extracted_facts = relationship("ExtractedFact", back_populates="obituary", cascade="all, delete-orphan")
    gramps_mappings = relationship("GrampsRecordMapping", back_populates="obituary", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingQueue", back_populates="obituary", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ObituaryCache(id={self.id}, url='{self.url[:50]}...', status='{self.processing_status}')>"


class LLMCache(Base):
    """Stores LLM API requests and responses"""
    __tablename__ = 'llm_cache'

    id = Column(Integer, primary_key=True, autoincrement=True)
    obituary_cache_id = Column(Integer, ForeignKey('obituary_cache.id', ondelete='CASCADE'), nullable=False)
    llm_provider = Column(String(50), nullable=False)
    model_version = Column(String(100), nullable=False)
    prompt_hash = Column(String(64), nullable=False, index=True)
    prompt_text = Column(Text, nullable=False)
    response_text = Column(MEDIUMTEXT)
    parsed_json = Column(JSON)
    token_usage_prompt = Column(Integer)
    token_usage_completion = Column(Integer)
    token_usage_total = Column(Integer)
    cost_usd = Column(DECIMAL(10, 6))
    request_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    response_timestamp = Column(TIMESTAMP)
    duration_ms = Column(Integer)
    api_error = Column(Text)

    # Relationships
    obituary = relationship("ObituaryCache", back_populates="llm_cache_entries")

    __table_args__ = (
        Index('idx_provider_model', 'llm_provider', 'model_version'),
    )

    def __repr__(self):
        return f"<LLMCache(id={self.id}, provider='{self.llm_provider}', model='{self.model_version}')>"


class ExtractedFact(Base):
    """Stores individual facts (claims) extracted from obituaries"""
    __tablename__ = 'extracted_facts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    obituary_cache_id = Column(Integer, ForeignKey('obituary_cache.id', ondelete='CASCADE'), nullable=False)
    llm_cache_id = Column(Integer, ForeignKey('llm_cache.id', ondelete='SET NULL'))

    fact_type = Column(
        Enum(
            'person_name',
            'person_death_date',
            'person_death_age',
            'person_birth_date',
            'person_gender',
            'maiden_name',
            'relationship',
            'marriage',
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
            'great_grandchild',
            'grandparent',
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

    gramps_person_id = Column(String(50), index=True)
    gramps_family_id = Column(String(50))
    gramps_event_id = Column(String(50))
    resolution_status = Column(
        Enum('unresolved', 'resolved', 'conflicting', 'rejected'),
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
    llm_cache = relationship("LLMCache")
    gramps_mappings = relationship("GrampsRecordMapping", back_populates="extracted_fact")

    def __repr__(self):
        return (f"<ExtractedFact(id={self.id}, type='{self.fact_type}', "
                f"subject='{self.subject_name}', confidence={self.confidence_score})>")

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'obituary_cache_id': self.obituary_cache_id,
            'fact_type': self.fact_type,
            'subject_name': self.subject_name,
            'subject_role': self.subject_role,
            'fact_value': self.fact_value,
            'related_name': self.related_name,
            'relationship_type': self.relationship_type,
            'extracted_context': self.extracted_context,
            'source_sentence': self.source_sentence,
            'is_inferred': self.is_inferred,
            'inference_basis': self.inference_basis,
            'confidence_score': float(self.confidence_score) if self.confidence_score else None,
            'resolution_status': self.resolution_status,
            'gramps_person_id': self.gramps_person_id,
            'gramps_family_id': self.gramps_family_id,
            'gramps_event_id': self.gramps_event_id,
            'created_timestamp': self.created_timestamp.isoformat() if self.created_timestamp else None,
        }


class GrampsRecordMapping(Base):
    """Tracks which Gramps records were created from which obituaries"""
    __tablename__ = 'gramps_record_mapping'

    id = Column(Integer, primary_key=True, autoincrement=True)
    obituary_cache_id = Column(Integer, ForeignKey('obituary_cache.id', ondelete='CASCADE'), nullable=False)
    gramps_record_type = Column(
        Enum('person', 'family', 'event', 'source', 'citation'),
        nullable=False
    )
    gramps_record_id = Column(String(50), nullable=False)
    extracted_fact_id = Column(Integer, ForeignKey('extracted_facts.id', ondelete='SET NULL'))
    created_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    obituary = relationship("ObituaryCache", back_populates="gramps_mappings")
    extracted_fact = relationship("ExtractedFact", back_populates="gramps_mappings")

    __table_args__ = (
        Index('idx_gramps_record', 'gramps_record_type', 'gramps_record_id'),
        Index('unique_gramps_mapping', 'gramps_record_type', 'gramps_record_id', 'obituary_cache_id', unique=True),
    )

    def __repr__(self):
        return f"<GrampsRecordMapping(id={self.id}, type='{self.gramps_record_type}', gramps_id='{self.gramps_record_id}')>"


class ConfigSettings(Base):
    """Stores application configuration"""
    __tablename__ = 'config_settings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(100), unique=True, nullable=False, index=True)
    setting_value = Column(Text, nullable=False)
    setting_type = Column(
        Enum('string', 'integer', 'float', 'boolean', 'json'),
        nullable=False
    )
    description = Column(Text)
    updated_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp(),
                              onupdate=func.current_timestamp())

    def __repr__(self):
        return f"<ConfigSettings(key='{self.setting_key}', value='{self.setting_value}')>"

    def get_typed_value(self):
        """Return the value with proper type conversion"""
        if self.setting_type == 'integer':
            return int(self.setting_value)
        elif self.setting_type == 'float':
            return float(self.setting_value)
        elif self.setting_type == 'boolean':
            return self.setting_value.lower() in ('true', '1', 'yes')
        elif self.setting_type == 'json':
            import json
            return json.loads(self.setting_value)
        else:
            return self.setting_value


class ProcessingQueue(Base):
    """Tracks processing jobs for async/batch processing"""
    __tablename__ = 'processing_queue'

    id = Column(Integer, primary_key=True, autoincrement=True)
    obituary_cache_id = Column(Integer, ForeignKey('obituary_cache.id', ondelete='CASCADE'), nullable=False)
    queue_status = Column(
        Enum('queued', 'processing', 'completed', 'failed', 'retry'),
        default='queued',
        index=True
    )
    priority = Column(Integer, default=5, index=True)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    queued_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    started_timestamp = Column(TIMESTAMP)
    completed_timestamp = Column(TIMESTAMP)

    # Relationships
    obituary = relationship("ObituaryCache", back_populates="processing_jobs")

    def __repr__(self):
        return f"<ProcessingQueue(id={self.id}, status='{self.queue_status}', priority={self.priority})>"


class AuditLog(Base):
    """Tracks all changes and actions for audit purposes"""
    __tablename__ = 'audit_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(50))
    entity_id = Column(Integer)
    user_action = Column(Boolean, default=False)
    details = Column(JSON)
    timestamp = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)

    __table_args__ = (
        Index('idx_entity', 'entity_type', 'entity_id'),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action_type}', entity='{self.entity_type}')>"


class PersonResolution(Base):
    """Maps extracted names to Gramps handles"""
    __tablename__ = 'person_resolution'

    id = Column(Integer, primary_key=True, autoincrement=True)
    obituary_cache_id = Column(Integer, ForeignKey('obituary_cache.id', ondelete='CASCADE'), nullable=False)

    extracted_name = Column(String(255), nullable=False, index=True)
    subject_role = Column(String(50))

    gramps_handle = Column(String(50), index=True)
    gramps_id = Column(String(50))
    match_score = Column(DECIMAL(3, 2))
    match_method = Column(
        Enum('exact', 'fuzzy', 'manual', 'created'),
        default='fuzzy'
    )

    status = Column(
        Enum('pending', 'matched', 'create_new', 'rejected', 'committed'),
        default='pending',
        index=True
    )

    user_modified = Column(Boolean, default=False)
    modified_first_name = Column(String(255))
    modified_surname = Column(String(255))
    modified_gender = Column(Integer)

    created_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())
    resolved_timestamp = Column(TIMESTAMP)
    committed_timestamp = Column(TIMESTAMP)

    # Relationships
    obituary = relationship("ObituaryCache")
    fact_resolutions = relationship("FactResolution", back_populates="person_resolution",
                                    foreign_keys="FactResolution.person_resolution_id")

    __table_args__ = (
        Index('unique_person_per_obituary', 'obituary_cache_id', 'extracted_name', unique=True),
    )

    def __repr__(self):
        return f"<PersonResolution(id={self.id}, name='{self.extracted_name}', status='{self.status}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'obituary_cache_id': self.obituary_cache_id,
            'extracted_name': self.extracted_name,
            'subject_role': self.subject_role,
            'gramps_handle': self.gramps_handle,
            'gramps_id': self.gramps_id,
            'match_score': float(self.match_score) if self.match_score else None,
            'match_method': self.match_method,
            'status': self.status,
            'user_modified': self.user_modified,
            'modified_first_name': self.modified_first_name,
            'modified_surname': self.modified_surname,
            'modified_gender': self.modified_gender,
        }


class FactResolution(Base):
    """Tracks approval status for each fact"""
    __tablename__ = 'fact_resolution'

    id = Column(Integer, primary_key=True, autoincrement=True)
    extracted_fact_id = Column(Integer, ForeignKey('extracted_facts.id', ondelete='CASCADE'), nullable=False)
    person_resolution_id = Column(Integer, ForeignKey('person_resolution.id', ondelete='SET NULL'))
    related_person_resolution_id = Column(Integer, ForeignKey('person_resolution.id', ondelete='SET NULL'))

    action = Column(
        Enum('add', 'update', 'skip', 'reject'),
        default='add',
        index=True
    )

    status = Column(
        Enum('pending', 'approved', 'rejected', 'committed'),
        default='pending',
        index=True
    )

    gramps_has_value = Column(Boolean, default=False)
    gramps_current_value = Column(Text)
    is_conflict = Column(Boolean, default=False)

    user_modified = Column(Boolean, default=False)
    modified_value = Column(Text)

    created_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())
    approved_timestamp = Column(TIMESTAMP)
    committed_timestamp = Column(TIMESTAMP)

    # Relationships
    extracted_fact = relationship("ExtractedFact")
    person_resolution = relationship("PersonResolution", foreign_keys=[person_resolution_id],
                                     back_populates="fact_resolutions")
    related_person_resolution = relationship("PersonResolution", foreign_keys=[related_person_resolution_id])

    __table_args__ = (
        Index('unique_fact_resolution', 'extracted_fact_id', unique=True),
    )

    def __repr__(self):
        return f"<FactResolution(id={self.id}, fact_id={self.extracted_fact_id}, status='{self.status}')>"

    def to_dict(self):
        return {
            'id': self.id,
            'extracted_fact_id': self.extracted_fact_id,
            'person_resolution_id': self.person_resolution_id,
            'related_person_resolution_id': self.related_person_resolution_id,
            'action': self.action,
            'status': self.status,
            'gramps_has_value': self.gramps_has_value,
            'gramps_current_value': self.gramps_current_value,
            'is_conflict': self.is_conflict,
            'user_modified': self.user_modified,
            'modified_value': self.modified_value,
        }


class GrampsCommitBatch(Base):
    """Tracks commits to Gramps"""
    __tablename__ = 'gramps_commit_batch'

    id = Column(Integer, primary_key=True, autoincrement=True)
    obituary_cache_id = Column(Integer, ForeignKey('obituary_cache.id', ondelete='CASCADE'), nullable=False)

    persons_created = Column(Integer, default=0)
    persons_updated = Column(Integer, default=0)
    families_created = Column(Integer, default=0)
    events_created = Column(Integer, default=0)
    facts_committed = Column(Integer, default=0)

    status = Column(
        Enum('pending', 'in_progress', 'completed', 'failed', 'rolled_back'),
        default='pending',
        index=True
    )
    error_message = Column(Text)

    created_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())
    started_timestamp = Column(TIMESTAMP)
    completed_timestamp = Column(TIMESTAMP)

    # Relationships
    obituary = relationship("ObituaryCache")

    def __repr__(self):
        return f"<GrampsCommitBatch(id={self.id}, status='{self.status}')>"
