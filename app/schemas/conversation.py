"""
Conversation Schemas
Request/Response validation với Pydantic
"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional, List, Literal, Dict


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase"""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


class MessageResponse(BaseModel):
    """
    Message response schema
    
    Giải thích:
    - Dùng để serialize Message model → JSON response
    - model_config từ ORM objects
    - Optional fields có thể None
    - alias_generator: Convert snake_case → camelCase for JSON
    """
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True
    )
    
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


class ChatRequest(BaseModel):
    """
    Chat request schema
    
    Giải thích:
    - Validate input từ client
    - Field(...): Required field
    - min_length, max_length: String validation
    - Accepts both camelCase and snake_case input
    """
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    userId: UUID = Field(
        ...,
        description="User ID"
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User message content"
    )
    conversationId: Optional[UUID] = Field(
        None,
        description="Conversation ID (null = create new)"
    )
    includeContext: bool = Field(
        True,
        description="Include chat history for context"
    )
    
    isVoiceInput: bool = Field(
        False,
        description="Flag to indicate if message came from voice input"
    )
    voiceDuration: Optional[float] = Field(
        None,
        description="Duration of voice recording in seconds (for analytics)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "userId": "25f1e353-566d-4ef2-8927-32c9fddada42",
                "message": "Hôm nay tôi cảm thấy hơi buồn",
                "conversationId": None,
                "includeContext": True,
                "isVoiceInput": False,
                "voiceDuration": 0.0
            }
        }
    )


class ChatResponse(BaseModel):

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    conversation_id: UUID
    user_message: MessageResponse
    assistant_message: MessageResponse
    context_used: int
    suggestion: Optional[Dict] = None


class ConversationResponse(BaseModel):
    """Conversation summary response"""
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    id: UUID
    user_id: UUID
    title: Optional[str]
    status: str
    message_count: int
    dominant_emotion: Optional[str]
    started_at: datetime
    created_at: datetime


class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageResponse]

