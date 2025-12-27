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
