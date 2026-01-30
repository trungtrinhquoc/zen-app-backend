"""
Conversation Schemas
Request/Response validation với Pydantic
"""
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Optional, List, Literal, Dict


class MessageResponse(BaseModel):
    """
    Message response schema
    
    Giải thích:
    - Dùng để serialize Message model → JSON response
    - model_config từ ORM objects
    - Optional fields có thể None
    """
    id: UUID
    role: Literal["user", "assistant", "system"]
    content: str
    content_type: str
    sequence_number: int
    created_at: datetime
    
    # Emotion data (có trong user messages)
    emotion_state: Optional[str] = None
    energy_level: Optional[int] = None
    urgency_level: Optional[str] = None
    detected_themes: Optional[List[str]] = None
    
    # AI metadata (có trong assistant messages)
    model_used: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    response_time_ms: Optional[int] = None
    
    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    """
    Chat request schema
    
    Giải thích:
    - Validate input từ client
    - Field(...): Required field
    - min_length, max_length: String validation
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User message content"
    )
    conversation_id: Optional[UUID] = Field(
        None,
        description="Conversation ID (null = create new)"
    )
    include_context: bool = Field(
        True,
        description="Include chat history for context"
    )


class ChatResponse(BaseModel):
    """
    Chat response schema
    
    Giải thích:
    - conversation_id: Để frontend track conversation
    - user_message: Message user vừa gửi (đã có emotion analysis)
    - assistant_message: AI response
    - context_used: Số messages đã dùng làm context
    - suggestion: Activity suggestion (nếu có)
    """
    conversation_id: UUID
    user_message: MessageResponse
    assistant_message: MessageResponse
    context_used: int
    suggestion: Optional[Dict] = None


class ConversationResponse(BaseModel):
    """Conversation summary response"""
    id: UUID
    user_id: UUID
    title: Optional[str]
    status: str
    message_count: int
    dominant_emotion: Optional[str]
    started_at: datetime
    created_at: datetime
    
    model_config = {"from_attributes": True}


class ConversationDetailResponse(ConversationResponse):
    """Conversation detail với messages"""
    messages: List[MessageResponse]


"""
Giải thích Pydantic:
- BaseModel: Base class cho schemas
- Field: Define field với validation
- Optional[T]: Field có thể None
- Literal["a", "b"]: Field chỉ accept exact values
- model_config = {"from_attributes": True}
  → Cho phép parse từ ORM objects (SQLAlchemy models)
  
Example:
    message = Message(role="user", content="Hello")
    response = MessageResponse.model_validate(message)
    # response là dict có thể serialize thành JSON
"""