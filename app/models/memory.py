"""
Memory Models
SQLAlchemy models for semantic_memories (adapts to existing schema)
"""
from sqlalchemy import Column, String, Float, ARRAY, Text, ForeignKey, DateTime, Integer, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
import uuid
from datetime import datetime
from app.database import Base


class SemanticMemory(Base):
    """
    Semantic memory storage with vector embeddings
    Maps to existing 'semantic_memories' table in database
    """
    __tablename__ = "semantic_memories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"))
    
    # Content
    content = Column(Text, nullable=False)
    memory_type = Column(String, nullable=False)  # conversation, insight, preference, trigger
    
    # Vector embedding (1536 dimensions for text-embedding-3-small)
    embedding = Column(Vector(1536))
    
    # Metadata
    importance_score = Column(Float, default=0.5)  # 0-1
    emotional_context = Column(JSONB, default=dict)
    tags = Column(ARRAY(String), default=list)
    
    # Access tracking
    access_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<SemanticMemory(id={self.id}, user_id={self.user_id}, type={self.memory_type})>"


class UserPattern(Base):
    """
    User behavioral patterns
    Maps to existing 'user_patterns' table
    """
    __tablename__ = "user_patterns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Pattern info
    pattern_type = Column(String, nullable=False)  # trigger, preference, cycle, effectiveness
    category = Column(String, nullable=False)  # work, sleep, relationships
    
    # Pattern data
    pattern_data = Column(JSONB, nullable=False)
    
    # Confidence
    confidence_score = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False)
    
    # Status
    is_active = Column(Integer, default=True)
    
    # Timestamps
    first_detected_at = Column(DateTime, default=datetime.utcnow)
    last_updated_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<UserPattern(user_id={self.user_id}, type={self.pattern_type})>"
