# FILE: backend/models/cache_models.py
# SQLAlchemy models for cache database
# ============================================================================

from sqlalchemy import (
    Column, Integer, String, Text, TIMESTAMP, Boolean, 
    Enum, ForeignKey, Index, DECIMAL, JSON, VARCHAR, DATE, MEDIUMTEXT
)
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
    extracted_persons = relationship("ExtractedPerson", back_populates="obituary", cascade="all, delete-orphan")
    extracted_relationships = relationship("ExtractedRelationship", back_populates="obituary", cascade="all, delete-orphan")
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


class ExtractedPerson(Base):
    """Stores extracted person entities from obituaries"""
    __tablename__ = 'extracted_persons'

    id = Column(Integer, primary_key=True, autoincrement=True)
    obituary_cache_id = Column(Integer, ForeignKey('obituary_cache.id', ondelete='CASCADE'), nullable=False)
    llm_cache_id = Column(Integer, ForeignKey('llm_cache.id', ondelete='SET NULL'))
    full_name = Column(String(255), nullable=False, index=True)
    given_names = Column(String(255))
    surname = Column(String(255), index=True)
    maiden_name = Column(String(255))
    age = Column(Integer)
    birth_date = Column(DATE)
    birth_date_circa = Column(Boolean, default=False)
    death_date = Column(DATE)
    death_date_circa = Column(Boolean, default=False)
    birth_location = Column(String(500))
    death_location = Column(String(500))
    residence_location = Column(String(500))
    gender = Column(Enum('M', 'F', 'U'), default='U')
    is_deceased_primary = Column(Boolean, default=False)
    confidence_score = Column(DECIMAL(3, 2), index=True)
    extraction_notes = Column(Text)
    gramps_person_id = Column(String(50), index=True)
    match_status = Column(
        Enum('unmatched', 'matched', 'created', 'review_needed'),
        default='unmatched',
        index=True
    )
    created_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())
    updated_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp(),
                              onupdate=func.current_timestamp())

    # Relationships
    obituary = relationship("ObituaryCache", back_populates="extracted_persons")
    llm_cache = relationship("LLMCache")
    relationships_as_person1 = relationship(
        "ExtractedRelationship",
        foreign_keys="ExtractedRelationship.person1_id",
        back_populates="person1"
    )
    relationships_as_person2 = relationship(
        "ExtractedRelationship",
        foreign_keys="ExtractedRelationship.person2_id",
        back_populates="person2"
    )
    gramps_mappings = relationship("GrampsRecordMapping", back_populates="extracted_person")

    def __repr__(self):
        return f"<ExtractedPerson(id={self.id}, name='{self.full_name}', confidence={self.confidence_score})>"


class ExtractedRelationship(Base):
    """Stores extracted relationships between persons"""
    __tablename__ = 'extracted_relationships'

    id = Column(Integer, primary_key=True, autoincrement=True)
    obituary_cache_id = Column(Integer, ForeignKey('obituary_cache.id', ondelete='CASCADE'), nullable=False)
    llm_cache_id = Column(Integer, ForeignKey('llm_cache.id', ondelete='SET NULL'))
    person1_id = Column(Integer, ForeignKey('extracted_persons.id', ondelete='CASCADE'), nullable=False, index=True)
    person2_id = Column(Integer, ForeignKey('extracted_persons.id', ondelete='CASCADE'), nullable=False, index=True)
    relationship_type = Column(String(100), nullable=False, index=True)
    relationship_detail = Column(String(255))
    confidence_score = Column(DECIMAL(3, 2), index=True)
    extracted_context = Column(Text)
    gramps_family_id = Column(String(50))
    match_status = Column(
        Enum('unmatched', 'matched', 'created', 'review_needed'),
        default='unmatched',
        index=True
    )
    created_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    obituary = relationship("ObituaryCache", back_populates="extracted_relationships")
    llm_cache = relationship("LLMCache")
    person1 = relationship("ExtractedPerson", foreign_keys=[person1_id], back_populates="relationships_as_person1")
    person2 = relationship("ExtractedPerson", foreign_keys=[person2_id], back_populates="relationships_as_person2")

    __table_args__ = (
        Index('unique_relationship', 'person1_id', 'person2_id', 'relationship_type', unique=True),
    )

    def __repr__(self):
        return f"<ExtractedRelationship(id={self.id}, type='{self.relationship_type}', confidence={self.confidence_score})>"


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
    extracted_person_id = Column(Integer, ForeignKey('extracted_persons.id', ondelete='SET NULL'))
    extracted_relationship_id = Column(Integer, ForeignKey('extracted_relationships.id', ondelete='SET NULL'))
    created_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())

    # Relationships
    obituary = relationship("ObituaryCache", back_populates="gramps_mappings")
    extracted_person = relationship("ExtractedPerson", back_populates="gramps_mappings")

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

