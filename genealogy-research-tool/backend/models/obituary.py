from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class ObituaryCache(Base):
    """Stores raw obituary content and metadata"""
    __tablename__ = 'obituary_cache'

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), unique=True, nullable=False)
    url_hash = Column(String(64), nullable=False, index=True)
    content_hash = Column(String(64))
    raw_html = Column(Text)
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
    extracted_facts = relationship("ExtractedFact", back_populates="obituary",
                                   cascade="all, delete-orphan")
    llm_cache_entries = relationship("LLMCache", back_populates="obituary",
                                     cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ObituaryCache(id={self.id}, url='{self.url[:50]}...', status='{self.processing_status}')>"


class LLMCache(Base):
    """Stores LLM API requests and responses"""
    __tablename__ = 'llm_cache'

    id = Column(Integer, primary_key=True, autoincrement=True)
    obituary_cache_id = Column(Integer, ForeignKey('obituary_cache.id'), nullable=False)
    llm_provider = Column(String(50), nullable=False, default='openai')
    model_version = Column(String(100), nullable=False)
    prompt_hash = Column(String(64), nullable=False, index=True)
    prompt_text = Column(Text, nullable=False)
    response_text = Column(Text)
    parsed_json = Column(Text)  # Store as JSON string
    token_usage_prompt = Column(Integer)
    token_usage_completion = Column(Integer)
    token_usage_total = Column(Integer)
    cost_usd = Column(String(20))  # Store as string to avoid float precision issues
    request_timestamp = Column(TIMESTAMP, server_default=func.current_timestamp())
    response_timestamp = Column(TIMESTAMP)
    duration_ms = Column(Integer)
    api_error = Column(Text)

    # Relationships
    obituary = relationship("ObituaryCache", back_populates="llm_cache_entries")

    def __repr__(self):
        return f"<LLMCache(id={self.id}, provider='{self.llm_provider}', model='{self.model_version}')>"
