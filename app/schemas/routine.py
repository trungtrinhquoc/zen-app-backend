"""
Routine Schemas
Pydantic models cho Module 5 - Routine System

Giải thích:
- Request schemas: Validate data từ client gửi lên
- Response schemas: Serialize data từ DB trả về client
- Dùng to_camel để convert snake_case → camelCase
  (Frontend React thường dùng camelCase)
"""
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional, List, Dict, Any


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase for JSON output"""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


# ============================================================
# ACTIVITY SCHEMAS
# ============================================================

class ActivityResponse(BaseModel):
    """
    Response cho 1 bài tập trong library

    Trả về đầy đủ để frontend render:
    - instructions: Array steps để hiển thị step-by-step
    - best_for_emotions: Để user biết phù hợp với mood nào
    - has_audio: Để frontend hiện audio player nếu có
    """
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True
    )

    id: UUID
    name: str
    slug: str
    category: str
    description: str
    instructions: List[Dict[str, Any]]
    duration_minutes: int
    difficulty_level: str
    has_audio: bool
    audio_url: Optional[str] = None
    tags: List[str]
    best_for_emotions: List[str]
    best_for_energy_level: List[int]
    total_completions: int
    is_premium: bool


class ActivityListResponse(BaseModel):
    """Response cho danh sách activities"""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    activities: List[ActivityResponse]
    total: int
    category: Optional[str] = None


# ============================================================
# ROUTINE PLAN SCHEMAS
# ============================================================

class RoutinePlanStep(BaseModel):
    """
    1 step trong plan JSONB

    Giải thích:
    - activity_id: UUID từ activity_library
    - slug: Dùng để AI generate (vd: 'box-breathing')
    - order: Thứ tự trong ngày (1, 2, 3)
    - duration: Override duration nếu khác default
    - activity: Resolved activity data (populated khi query)
    """
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    activity_id: Optional[UUID] = None
    slug: str
    order: int
    duration: Optional[int] = None
    activity: Optional[ActivityResponse] = None


class RoutineDay(BaseModel):
    """1 ngày trong routine với list steps"""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    day_number: int
    steps: List[RoutinePlanStep]


class RoutineCompletionInfo(BaseModel):
    """Info về 1 step đã hoàn thành"""
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True
    )

    id: UUID
    day_number: int
    step_number: int
    completed: bool
    actual_duration_minutes: Optional[int] = None
    user_rating: Optional[int] = None
    emotion_before: Optional[str] = None
    emotion_after: Optional[str] = None
    energy_before: Optional[int] = None
    energy_after: Optional[int] = None
    completed_at: datetime


# ============================================================
# ROUTINE RESPONSE SCHEMAS
# ============================================================

class RoutineResponse(BaseModel):
    """
    Full routine response với days resolved

    Giải thích days field:
    - days là list 5 ngày, mỗi ngày có steps[] với activity details
    - completed_steps: Set tracking những steps đã xong
      Format: "day_1_step_2" → dễ check trên frontend
    - progress_percent: Để hiển thị progress bar
    """
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True
    )

    id: UUID
    user_id: UUID
    title: str
    theme: Optional[str] = None
    days: List[RoutineDay]
    status: str
    current_day: int
    generated_for_emotion: Optional[str] = None
    generated_for_energy: Optional[int] = None
    generation_reasoning: Optional[str] = None
    completed_steps: List[str] = []  # ["day_1_step_1", "day_1_step_2", ...]
    progress_percent: float = 0.0
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime


class RoutineListResponse(BaseModel):
    """Response cho danh sách routines (history)"""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    routines: List[RoutineResponse]
    total: int
    limit: int
    offset: int


# ============================================================
# REQUEST SCHEMAS
# ============================================================

class GenerateRoutineRequest(BaseModel):
    """
    Request tạo routine mới

    Giải thích:
    - emotion: Từ emotion analyzer, vd: 'anxious', 'tired', 'sad'
    - energy_level: 1-10, lấy từ emotion analysis
    - preferences: Optional, user có thể override
      vd: {"preferred_duration": 15, "avoid": ["journaling"]}
    """
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "userId": "25f1e353-566d-4ef2-8927-32c9fddada42",
                "emotion": "anxious",
                "energyLevel": 3,
                "preferences": {}
            }
        }
    )

    user_id: UUID = Field(..., description="User ID")
    emotion: str = Field(
        "neutral",
        description="Current emotion từ emotion analyzer"
    )
    energy_level: int = Field(
        5,
        ge=1, le=10,
        description="Energy level 1-10"
    )
    preferences: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional user preferences"
    )


class CompleteStepRequest(BaseModel):
    """
    Request hoàn thành 1 step trong routine

    Giải thích optional fields:
    - emotion_before/after: User có thể chọn emoji mood
    - user_rating: 1-5 stars sau khi xong
    - Nếu không có → DB lưu NULL, vẫn count là completed
    """
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "userId": "25f1e353-566d-4ef2-8927-32c9fddada42",
                "dayNumber": 1,
                "stepNumber": 1,
                "actualDurationMinutes": 5,
                "emotionBefore": "anxious",
                "emotionAfter": "calm",
                "energyBefore": 3,
                "energyAfter": 6,
                "userRating": 4
            }
        }
    )

    user_id: UUID = Field(..., description="User ID để verify ownership")
    day_number: int = Field(..., ge=1, le=5, description="Ngày thứ mấy (1-5)")
    step_number: int = Field(..., ge=1, le=3, description="Bước thứ mấy (1-3)")
    actual_duration_minutes: Optional[int] = Field(None, description="Thời gian thực tế")
    emotion_before: Optional[str] = Field(None, description="Cảm xúc trước khi làm")
    emotion_after: Optional[str] = Field(None, description="Cảm xúc sau khi làm")
    energy_before: Optional[int] = Field(None, ge=1, le=10)
    energy_after: Optional[int] = Field(None, ge=1, le=10)
    user_rating: Optional[int] = Field(None, ge=1, le=5, description="Rating 1-5 sao")
    user_notes: Optional[str] = Field(None, max_length=500)


class AbandonRoutineRequest(BaseModel):
    """Request bỏ routine"""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    user_id: UUID = Field(..., description="User ID để verify ownership")
