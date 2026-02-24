"""
Routine Models
Map với bảng activity_library, user_routines, routine_completions

KIẾN TRÚC MODULE 5:
- ActivityLibrary: Thư viện bài tập master (admin-seeded)
- UserRoutine: Routine 5 ngày của từng user (AI-generated)
- RoutineCompletion: Lịch sử hoàn thành từng step của user
"""
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Text, ForeignKey, Numeric, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class ActivityLibrary(Base):
    """
    Bảng thư viện bài tập master

    Giải thích các field quan trọng:
    - slug: Unique key dạng kebab-case để AI reference (vd: 'box-breathing')
    - category: Loại bài tập (breathing/meditation/journaling/listening/movement/reflection)
    - instructions: JSONB array các bước thực hiện
      Format: [{"step": 1, "text": "Hít vào", "duration": 4}, ...]
    - best_for_emotions: Emotions mà bài tập này phù hợp nhất
      Ví dụ: ['anxious', 'stressed', 'overwhelmed']
    - best_for_energy_level: Mức năng lượng phù hợp [1, 2, 3] = low energy
    - tags: Labels để filter (vd: ['morning', 'quick', 'anxiety'])
    """
    __tablename__ = "activity_library"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Basic Info
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False, unique=True)
    category = Column(Text, nullable=False)
    # CHECK: breathing | meditation | journaling | listening | movement | reflection

    # Content
    description = Column(Text, nullable=False)
    instructions = Column(JSONB, nullable=False, default=list)
    # Format: [{"step": 1, "text": "...", "duration": 4}]

    duration_minutes = Column(Integer, nullable=False)
    difficulty_level = Column(Text, default='beginner', nullable=False)
    # CHECK: beginner | intermediate | advanced

    # Audio Guide
    has_audio = Column(Boolean, default=False, nullable=False)
    audio_url = Column(Text, nullable=True)

    # Metadata cho AI matching
    tags = Column(ARRAY(Text), default=list, nullable=False)
    best_for_emotions = Column(ARRAY(Text), default=list, nullable=False)
    best_for_energy_level = Column(ARRAY(Integer), default=list, nullable=False)

    # Usage Stats
    total_completions = Column(Integer, default=0, nullable=False)
    average_rating = Column(Numeric(3, 2), default=0.0, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_premium = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    completions = relationship(
        "RoutineCompletion",
        back_populates="activity",
        lazy="noload"  # Don't load automatically – queried separately via RoutineCompletion
    )

    def __repr__(self):
        return f"<ActivityLibrary(slug={self.slug}, category={self.category}, duration={self.duration_minutes}m)>"


class UserRoutine(Base):
    """
    Routine 5 ngày của user - AI generated

    Giải thích field plan (JSONB):
    {
      "day_1": [
        {"activity_id": "uuid", "slug": "box-breathing", "order": 1, "duration": 5},
        {"activity_id": "uuid", "slug": "body-scan", "order": 2, "duration": 10},
        {"activity_id": "uuid", "slug": "gratitude-journal", "order": 3, "duration": 5}
      ],
      "day_2": [...],
      ...
      "day_5": [...]
    }

    Giải thích status flow:
    active → completed (tất cả 15 steps xong)
    active → abandoned (user bỏ giữa chừng)
    """
    __tablename__ = "user_routines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    # Routine Info
    title = Column(Text, nullable=False)
    theme = Column(Text, nullable=True)  # vd: 'Anxiety Relief', 'Better Sleep'

    # Plan JSONB (5 ngày × 3 steps/ngày)
    plan = Column(JSONB, nullable=False)

    # Generation Context
    generated_for_emotion = Column(Text, nullable=True)
    generated_for_energy = Column(Integer, nullable=True)
    generation_reasoning = Column(Text, nullable=True)

    # Status
    status = Column(Text, default='active', nullable=False)
    # CHECK: active | completed | abandoned
    current_day = Column(Integer, default=1, nullable=False)

    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    completions = relationship(
        "RoutineCompletion",
        back_populates="routine",
        lazy="noload",  # Don't load automatically – queried separately in _resolveRoutine
        order_by="RoutineCompletion.completed_at"
    )

    def __repr__(self):
        return f"<UserRoutine(id={self.id}, status={self.status}, day={self.current_day}/5)>"


class RoutineCompletion(Base):
    """
    Lưu lịch sử hoàn thành từng step của user

    Giải thích emotion tracking:
    - emotion_before/after: Cảm xúc trước và sau khi làm
    - energy_before/after: Năng lượng 1-10 trước/sau
    - Dùng để: AI học user thích bài tập nào, bài nào hiệu quả
    """
    __tablename__ = "routine_completions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    routine_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_routines.id", ondelete="CASCADE"),
        nullable=False
    )
    activity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("activity_library.id", ondelete="CASCADE"),
        nullable=False
    )

    # Completion Info
    day_number = Column(Integer, nullable=False)   # 1-5
    step_number = Column(Integer, nullable=False)  # 1-3

    # Metrics
    completed = Column(Boolean, default=True, nullable=False)
    actual_duration_minutes = Column(Integer, nullable=True)

    # Feedback
    user_rating = Column(Integer, nullable=True)  # 1-5
    user_notes = Column(Text, nullable=True)

    # Emotional Impact
    emotion_before = Column(Text, nullable=True)
    emotion_after = Column(Text, nullable=True)
    energy_before = Column(Integer, nullable=True)
    energy_after = Column(Integer, nullable=True)

    # Timestamps
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    routine = relationship("UserRoutine", back_populates="completions")
    activity = relationship("ActivityLibrary", back_populates="completions")

    def __repr__(self):
        return f"<RoutineCompletion(day={self.day_number}, step={self.step_number}, rating={self.user_rating})>"
