"""
User Model
Map với bảng 'users' trong Supabase
"""
from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class User(Base):

    __tablename__ = "users"
    
    # Primary Key (reference auth.users)
    id = Column(UUID(as_uuid=True), primary_key=True)
    
    # Basic Info
    display_name = Column(Text, nullable=True)
    avatar_url = Column(Text, nullable=True)
    
    # Onboarding
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    onboarding_data = Column(JSONB, default=dict, nullable=False)
    
    # Privacy Settings
    memory_enabled = Column(Boolean, default=True, nullable=False)
    data_collection_consent = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_active_at = Column(DateTime, nullable=True)
    timezone = Column(Text, default='UTC', nullable=False)
    language = Column(Text, default='vi', nullable=False)
    
    # Soft Delete
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    conversations = relationship(
        "Conversation",
        back_populates="user",
        lazy="selectin"  
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, display_name={self.display_name})>"


"""
Giải thích Relationships:
- back_populates: Two-way relationship
  → user.conversations = list of Conversation objects
  → conversation.user = User object
  
- lazy="selectin": Load strategy
  → "selectin": Separate query (efficient)
  → "joined": JOIN query (1 query nhưng có thể slow)
  → "dynamic": Query object (chưa execute)
"""