"""
Conversation & Message Models
Map chính xác với database schema
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class Conversation(Base):
    """
    Conversation model - Phiên chat
    
    Giải thích:
    - Mỗi user có nhiều conversations
    - Mỗi conversation có nhiều messages
    - emotion_progression: Array of emotion snapshots theo thời gian
    - message_count: Auto-updated bởi trigger trong DB
    """
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Conversation Info
    title = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    
    # Emotion Summary
    dominant_emotion = Column(Text, nullable=True)
    emotion_progression = Column(JSONB, nullable=True)
    # Format: [{"timestamp": "...", "emotion": "anxious", "energy": 3}, ...]
    
    # Metadata
    message_count = Column(Integer, default=0, nullable=False)
    total_duration_seconds = Column(Integer, default=0, nullable=True)
    has_voice_messages = Column(Boolean, default=False, nullable=False)
    
    # Status: active, ended, archived
    status = Column(Text, default='active', nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    
    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        lazy="selectin",
        order_by="Message.sequence_number"
    )
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, status={self.status}, messages={self.message_count})>"


class Message(Base):
    """
    Message model - Từng tin nhắn trong conversation
    
    Giải thích:
    - role: 'user' (từ người dùng) | 'assistant' (từ AI) | 'system' (hệ thống)
    - content_type: 'text' | 'voice' | 'system'
    - sequence_number: Thứ tự tin nhắn (1, 2, 3, ...)
    
    Emotion fields (cho user messages):
    - emotion_state: anxious, sad, calm, happy, stressed...
    - energy_level: 1-10
    - urgency_level: low, medium, high, crisis
    - detected_themes: ["work", "stress", "sleep"...]
    
    AI metadata (cho assistant messages):
    - model_used: "openai/gpt-4o-mini"
    - prompt_tokens, completion_tokens: Token usage
    - response_time_ms: Response time
    """
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Message Content
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    content_type = Column(Text, default='text', nullable=False)
    
    # Voice Data (cho Module 3)
    audio_url = Column(Text, nullable=True)
    audio_duration_seconds = Column(Numeric(10, 2), nullable=True)
    transcription_confidence = Column(Numeric(4, 3), nullable=True)
    
    # Emotion Data (từ emotion analyzer)
    emotion_state = Column(Text, nullable=True)
    energy_level = Column(Integer, nullable=True)
    urgency_level = Column(Text, nullable=True)
    detected_themes = Column(ARRAY(Text), default=list, nullable=True)
    
    # AI Response Metadata
    model_used = Column(Text, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Ordering
    sequence_number = Column(Integer, nullable=False)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    
    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, seq={self.sequence_number})>"


"""
Giải thích ForeignKey:
- ForeignKey("users.id", ondelete="CASCADE")
  → Khi user bị xóa, tất cả messages của user cũng bị xóa
  
- ondelete options:
  → CASCADE: Xóa related records
  → SET NULL: Set foreign key = NULL
  → RESTRICT: Không cho xóa nếu còn related records
"""