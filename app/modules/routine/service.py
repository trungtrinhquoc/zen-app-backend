"""
Routine Service
Business logic cho Module 5 - Routine System

ARCHITECTURE:
    RoutineService(db)
        ├── getActivityLibrary()   → query & filter activities
        ├── generateRoutine()      → AI-powered 5-day plan
        ├── getActiveRoutine()     → lấy routine đang active
        ├── completeStep()         → record step completion
        ├── abandonRoutine()       → soft-abandon
        └── getRoutineHistory()    → past routines

FLOW KHI GENERATE:
    1. Check active routine tồn tại → trả về ngay nếu có
    2. Query available activities từ DB
    3. Build prompt với context (emotion, energy, history)
    4. Call GPT-4o-mini → JSON plan
    5. Resolve slugs → UUIDs từ DB
    6. Insert UserRoutine → DB
    7. Return full response với activities resolved
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, text
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
import json

from app.models.routine import ActivityLibrary, UserRoutine, RoutineCompletion
from app.services.openrouter_client import openRouterService
from app.utils.logger import logger


# ============================================================
# SYSTEM PROMPT CHO AI ROUTINE GENERATOR
# ============================================================

ROUTINE_GENERATOR_PROMPT = """Bạn là chuyên gia thiết kế lộ trình chăm sóc sức khỏe tâm lý.

Nhiệm vụ: Tạo routine 5 ngày, mỗi ngày 3 activities, phù hợp với trạng thái hiện tại của user.

THÔNG TIN USER:
- Cảm xúc hiện tại: {emotion}
- Mức năng lượng: {energy_level}/10
- Activities đã làm gần đây: {recent_activities}
- Preferences: {preferences}

DANH SÁCH ACTIVITIES CÓ SẴN (chỉ dùng các slug này):
{available_activities}

QUY TẮC BẮT BUỘC:
1. Mỗi ngày ĐÚNG 3 activities, order 1→2→3
2. Ngày 1-2: activities nhẹ nhàng và ngắn (≤5 phút) nếu energy thấp
3. Ngày 3-4: tăng dần độ phức tạp
4. Ngày 5: tổng hợp, nhấn mạnh progress
5. Không lặp cùng activity trong cùng một ngày
6. Cân bằng categories: breathing + meditation/journaling + listening/movement
7. Nếu energy ≤ 3: ưu tiên breathing, listening, body scan
8. Nếu emotion là 'sad'/'lonely': ưu tiên loving-kindness, gratitude, forest sounds

CHỈ trả về JSON, không viết thêm:
{{
  "title": "Tên routine ngắn gọn (tiếng Việt, ≤40 ký tự)",
  "theme": "Chủ đề (vd: Giảm lo âu, Phục hồi năng lượng)",
  "reasoning": "Giải thích ngắn tại sao chọn routine này (1-2 câu tiếng Việt)",
  "plan": {{
    "day_1": [
      {{"slug": "box-breathing", "order": 1, "duration": 5}},
      {{"slug": "body-scan", "order": 2, "duration": 10}},
      {{"slug": "gratitude-journal", "order": 3, "duration": 5}}
    ],
    "day_2": [...],
    "day_3": [...],
    "day_4": [...],
    "day_5": [...]
  }}
}}"""


class RoutineService:
    """
    Service xử lý toàn bộ logic của Module 5 — Routine System

    Giải thích:
    - Nhận db (AsyncSession) qua constructor
    - Mỗi request tạo 1 instance mới (stateless)
    - Query trực tiếp qua SQLAlchemy ORM
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─────────────────────────────────────────────────────────
    # PUBLIC METHODS
    # ─────────────────────────────────────────────────────────

    async def getActivityLibrary(
        self,
        category: Optional[str] = None,
        emotion: Optional[str] = None,
        energy_level: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[ActivityLibrary], int]:
        """
        Lấy danh sách activities từ library với optional filters

        Args:
            category: Loại bài tập (breathing/meditation/journaling/listening/movement)
            emotion: Lọc theo emotion phù hợp
            energy_level: Lọc theo energy level
            limit, offset: Pagination

        Returns:
            (list of activities, total count)

        Giải thích query:
        - is_active=True: Chỉ lấy activities đang active
        - ARRAY @> ARRAY: PostgreSQL operator "chứa"
          vd: tags @> ARRAY['anxiety'] = tags phải chứa 'anxiety'
        """
        query = select(ActivityLibrary).where(ActivityLibrary.is_active == True)

        if category:
            query = query.where(ActivityLibrary.category == category)

        if emotion:
            # PostgreSQL: array contains operator
            query = query.where(
                ActivityLibrary.best_for_emotions.contains([emotion])
            )

        if energy_level is not None:
            query = query.where(
                ActivityLibrary.best_for_energy_level.contains([energy_level])
            )

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.order_by(ActivityLibrary.total_completions.desc()).offset(offset).limit(limit)
        result = await self.db.execute(query)
        activities = result.scalars().all()

        logger.info(f"📚 Activity library: {len(activities)}/{total} activities (cat={category}, emotion={emotion})")
        return list(activities), total

    async def generateRoutine(
        self,
        user_id: UUID,
        emotion: str,
        energy_level: int,
        preferences: Optional[Dict[str, Any]] = None
    ) -> UserRoutine:
        """
        Tạo routine 5 ngày mới bằng AI

        Flow:
        1. Check active routine → return existing nếu có
        2. Load all available activities từ DB (để build prompt)
        3. Load recent activity history (để tránh lặp lại)
        4. Build prompt và call GPT-4o-mini
        5. Parse JSON response → resolve slugs thành UUIDs
        6. Insert UserRoutine vào DB
        7. Return (với activities resolved riêng)

        Args:
            user_id: User UUID
            emotion: Cảm xúc hiện tại (từ emotion analyzer)
            energy_level: 1-10
            preferences: Optional user preferences

        Returns:
            UserRoutine object (chưa có activities resolved — caller dùng _resolveRoutine)
        """
        # Step 1: Check existing active routine
        existing = await self._getActiveRoutineRaw(user_id)
        if existing:
            logger.info(f"♻️  User {user_id} already has active routine {existing.id}")
            return existing

        # Step 2: Load all activities
        all_activities, _ = await self.getActivityLibrary(limit=100)

        # Guard: nếu DB trống → không gọi AI, báo lỗi ngay
        if not all_activities:
            raise ValueError(
                "Activity library is empty. Please run: python scripts/seed_activities.py"
            )

        # Step 3: Load recent history
        recent_slugs = await self._getRecentActivitySlugs(user_id, limit=10)

        # Step 4: Build prompt với danh sách slug thật từ DB
        activity_list_str = "\n".join([
            f"  - {a.slug} [{a.category}] {a.duration_minutes}min — {a.description[:50]}..."
            for a in all_activities
        ])

        prompt = ROUTINE_GENERATOR_PROMPT.format(
            emotion=emotion,
            energy_level=energy_level,
            recent_activities=", ".join(recent_slugs) if recent_slugs else "Chưa có",
            preferences=json.dumps(preferences or {}, ensure_ascii=False),
            available_activities=activity_list_str
        )

        # Step 5: Call GPT-4o-mini
        logger.info(f"🤖 Generating routine for user {user_id} (emotion={emotion}, energy={energy_level})")
        ai_response = await openRouterService.chat(
            messages=[
                {"role": "system", "content": "You are a mental wellness routine designer. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            maxTokens=800
        )

        # Step 6: Parse JSON
        plan_data = await self._parseAIRoutinePlan(ai_response["content"])

        # Step 7: Build slug → UUID map
        slug_to_id = {a.slug: str(a.id) for a in all_activities}
        resolved_plan = {}

        for day_key, steps in plan_data["plan"].items():
            resolved_steps = []
            for step in steps:
                slug = step["slug"]
                activity_uuid = slug_to_id.get(slug)
                if not activity_uuid:
                    logger.warning(f"⚠️  Slug '{slug}' not found in library, skipping")
                    continue
                resolved_steps.append({
                    "activity_id": activity_uuid,
                    "slug": slug,
                    "order": step["order"],
                    "duration": step.get("duration")
                })
            # Reassign order 1,2,3 sau khi lọc slug không hợp lệ
            for i, s in enumerate(resolved_steps, start=1):
                s["order"] = i
            if resolved_steps:
                resolved_plan[day_key] = resolved_steps

        # Guard: mỗi ngày phải có ít nhất 1 step
        if not resolved_plan:
            raise ValueError(
                "AI generated only invalid slugs — none matched activity library. "
                "Check that seed data is loaded correctly."
            )

        # Log bao nhiêu slugs được resolve thành công
        total_resolved = sum(len(v) for v in resolved_plan.values())
        logger.info(f"✅ Resolved {total_resolved} steps across {len(resolved_plan)} days")

        # Step 8: Insert to DB
        new_routine = UserRoutine(
            user_id=user_id,
            title=plan_data.get("title", f"Routine {emotion.capitalize()}"),
            theme=plan_data.get("theme"),
            plan=resolved_plan,
            generated_for_emotion=emotion,
            generated_for_energy=energy_level,
            generation_reasoning=plan_data.get("reasoning"),
            status="active",
            current_day=1
        )
        self.db.add(new_routine)
        await self.db.commit()
        await self.db.refresh(new_routine)

        logger.info(f"✅ Routine generated: {new_routine.id} — '{new_routine.title}'")
        return new_routine

    async def getActiveRoutine(self, user_id: UUID) -> Optional[Dict]:
        """
        Lấy routine đang active của user với activities resolved

        Returns:
            Dict với full routine data kèm activity details
            hoặc None nếu không có active routine

        Giải thích "resolved":
        - Plan JSONB chỉ lưu activity_id (UUID)
        - "Resolve" = join với activity_library để lấy name, instructions...
        - Kết quả: mỗi step có đầy đủ activity info để frontend render
        """
        routine = await self._getActiveRoutineRaw(user_id)
        if not routine:
            return None

        return await self._resolveRoutine(routine, user_id)

    async def getRoutineHistory(
        self,
        user_id: UUID,
        limit: int = 10,
        offset: int = 0
    ) -> tuple[List[Dict], int]:
        """
        Lấy lịch sử routines đã completed hoặc abandoned

        Returns:
            (list of resolved routines, total count)
        """
        query = select(UserRoutine).where(
            UserRoutine.user_id == user_id,
            UserRoutine.status.in_(["completed", "abandoned"])
        ).order_by(UserRoutine.created_at.desc())

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        routines = result.scalars().all()

        resolved = [await self._resolveRoutine(r, user_id) for r in routines]
        return resolved, total

    async def completeStep(
        self,
        user_id: UUID,
        routine_id: UUID,
        day_number: int,
        step_number: int,
        actual_duration_minutes: Optional[int] = None,
        emotion_before: Optional[str] = None,
        emotion_after: Optional[str] = None,
        energy_before: Optional[int] = None,
        energy_after: Optional[int] = None,
        user_rating: Optional[int] = None,
        user_notes: Optional[str] = None
    ) -> Dict:
        """
        Ghi nhận user đã hoàn thành 1 step

        Flow:
        1. Verify ownership (routine thuộc user này không)
        2. Tìm activity_id từ plan[day_N][step_N]
        3. Insert RoutineCompletion
        4. Increment activity_library.total_completions
        5. Check nếu tất cả 15 steps xong → mark routine completed
        6. Return result với is_routine_completed flag

        Args:
            user_id: Để verify ownership
            routine_id: Routine ID
            day_number: 1-5
            step_number: 1-3

        Returns:
            {
                "success": True,
                "completion_id": "uuid",
                "is_routine_completed": False,
                "next_day": 2
            }
        """
        # Step 1: Verify ownership
        routine = await self._getRoutineById(routine_id, user_id)

        # Step 2: Find activity_id từ plan
        day_key = f"day_{day_number}"
        day_plan = routine.plan.get(day_key, [])
        target_step = next(
            (s for s in day_plan if s.get("order") == step_number),
            None
        )
        if not target_step:
            raise ValueError(f"Step {step_number} không tồn tại trong ngày {day_number}")

        activity_id = UUID(target_step["activity_id"])

        # Step 3: Check duplicate (prevent double submission)
        existing = await self.db.execute(
            select(RoutineCompletion).where(
                RoutineCompletion.routine_id == routine_id,
                RoutineCompletion.day_number == day_number,
                RoutineCompletion.step_number == step_number
            )
        )
        if existing.scalar():
            raise ValueError(f"Step này đã được hoàn thành rồi")

        # Step 4: Insert completion
        completion = RoutineCompletion(
            user_id=user_id,
            routine_id=routine_id,
            activity_id=activity_id,
            day_number=day_number,
            step_number=step_number,
            completed=True,
            actual_duration_minutes=actual_duration_minutes,
            emotion_before=emotion_before,
            emotion_after=emotion_after,
            energy_before=energy_before,
            energy_after=energy_after,
            user_rating=user_rating,
            user_notes=user_notes
        )
        self.db.add(completion)

        # Step 5: Increment total_completions
        await self.db.execute(
            update(ActivityLibrary)
            .where(ActivityLibrary.id == activity_id)
            .values(total_completions=ActivityLibrary.total_completions + 1)
        )

        # Step 6: Check routine completion
        # Count total completions cho routine này
        count_result = await self.db.execute(
            select(func.count()).where(
                RoutineCompletion.routine_id == routine_id
            )
        )
        # +1 vì record vừa add chưa commit
        total_completed = (count_result.scalar() or 0) + 1
        total_steps = sum(len(steps) for steps in routine.plan.values())
        is_routine_completed = total_completed >= total_steps

        if is_routine_completed:
            await self.db.execute(
                update(UserRoutine)
                .where(UserRoutine.id == routine_id)
                .values(status="completed", completed_at=datetime.utcnow())
            )
            logger.info(f"🎉 Routine {routine_id} COMPLETED!")

        await self.db.commit()
        await self.db.refresh(completion)

        # Calculate next_day
        next_day = day_number if step_number < 3 else min(day_number + 1, 5)

        logger.info(
            f"✅ Step complete: routine={routine_id}, day={day_number}, "
            f"step={step_number}, rating={user_rating}"
        )

        return {
            "success": True,
            "completion_id": str(completion.id),
            "is_routine_completed": is_routine_completed,
            "total_completed": total_completed,
            "total_steps": total_steps,
            "next_day": next_day if not is_routine_completed else None
        }

    async def abandonRoutine(self, user_id: UUID, routine_id: UUID) -> Dict:
        """
        Bỏ routine giữa chừng (soft update status='abandoned')

        Returns:
            {"success": True, "message": "..."}
        """
        routine = await self._getRoutineById(routine_id, user_id)

        if routine.status != "active":
            raise ValueError(f"Routine không ở trạng thái active (status={routine.status})")

        await self.db.execute(
            update(UserRoutine)
            .where(UserRoutine.id == routine_id)
            .values(status="abandoned", updated_at=datetime.utcnow())
        )
        await self.db.commit()

        logger.info(f"🚫 Routine {routine_id} abandoned by user {user_id}")
        return {
            "success": True,
            "message": "Routine đã được bỏ qua. Bạn có thể tạo routine mới bất cứ lúc nào."
        }

    # ─────────────────────────────────────────────────────────
    # PRIVATE HELPER METHODS
    # ─────────────────────────────────────────────────────────

    async def _getActiveRoutineRaw(self, user_id: UUID) -> Optional[UserRoutine]:
        """Query active routine raw (không resolve activities)"""
        result = await self.db.execute(
            select(UserRoutine).where(
                UserRoutine.user_id == user_id,
                UserRoutine.status == "active"
            ).order_by(UserRoutine.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def _getRoutineById(self, routine_id: UUID, user_id: UUID) -> UserRoutine:
        """
        Lấy routine theo ID và verify ownership

        Raises ValueError nếu không tìm thấy hoặc không thuộc user
        """
        result = await self.db.execute(
            select(UserRoutine).where(
                UserRoutine.id == routine_id,
                UserRoutine.user_id == user_id
            )
        )
        routine = result.scalar_one_or_none()
        if not routine:
            raise ValueError(f"Routine {routine_id} không tồn tại hoặc không thuộc user này")
        return routine

    async def _resolveRoutine(self, routine: UserRoutine, user_id: UUID) -> Dict:
        """
        Convert UserRoutine → Dict với activities resolved từ DB

        Giải thích:
        - plan JSONB chỉ có activity_id (UUID string)
        - Ta query activity_library để lấy full info
        - Batch query tất cả UUIDs 1 lần (không query từng cái)

        Returns:
            Dict theo format RoutineResponse schema
        """
        # Collect all activity IDs from plan
        all_activity_ids = []
        for day_key, steps in routine.plan.items():
            for step in steps:
                activity_id = step.get("activity_id")
                if activity_id:
                    all_activity_ids.append(UUID(activity_id))

        # Batch query activities
        activities_map = {}
        if all_activity_ids:
            result = await self.db.execute(
                select(ActivityLibrary).where(
                    ActivityLibrary.id.in_(all_activity_ids)
                )
            )
            for activity in result.scalars().all():
                activities_map[str(activity.id)] = activity

        # Build resolved days
        days = []
        for day_num in range(1, 6):
            day_key = f"day_{day_num}"
            steps_raw = routine.plan.get(day_key, [])
            steps = []
            for step_raw in sorted(steps_raw, key=lambda x: x.get("order", 0)):
                activity_id = step_raw.get("activity_id")
                activity = activities_map.get(activity_id) if activity_id else None
                steps.append({
                    "activity_id": activity_id,
                    "slug": step_raw.get("slug", ""),
                    "order": step_raw.get("order", 0),
                    "duration": step_raw.get("duration"),
                    "activity": self._activityToDict(activity) if activity else None
                })
            days.append({"day_number": day_num, "steps": steps})

        # Load completed steps
        completions_result = await self.db.execute(
            select(RoutineCompletion).where(
                RoutineCompletion.routine_id == routine.id
            )
        )
        completions = completions_result.scalars().all()
        completed_steps = [
            f"day_{c.day_number}_step_{c.step_number}"
            for c in completions
        ]

        # Calculate progress
        total_steps = sum(len(routine.plan.get(f"day_{d}", [])) for d in range(1, 6))
        progress_percent = (len(completed_steps) / total_steps * 100) if total_steps > 0 else 0.0

        return {
            "id": routine.id,
            "user_id": routine.user_id,
            "title": routine.title,
            "theme": routine.theme,
            "days": days,
            "status": routine.status,
            "current_day": routine.current_day,
            "generated_for_emotion": routine.generated_for_emotion,
            "generated_for_energy": routine.generated_for_energy,
            "generation_reasoning": routine.generation_reasoning,
            "completed_steps": completed_steps,
            "progress_percent": round(progress_percent, 1),
            "started_at": routine.started_at,
            "completed_at": routine.completed_at,
            "created_at": routine.created_at,
        }

    def _activityToDict(self, activity: ActivityLibrary) -> Dict:
        """Convert ActivityLibrary ORM → Dict"""
        return {
            "id": activity.id,
            "name": activity.name,
            "slug": activity.slug,
            "category": activity.category,
            "description": activity.description,
            "instructions": activity.instructions,
            "duration_minutes": activity.duration_minutes,
            "difficulty_level": activity.difficulty_level,
            "has_audio": activity.has_audio,
            "audio_url": activity.audio_url,
            "tags": activity.tags or [],
            "best_for_emotions": activity.best_for_emotions or [],
            "best_for_energy_level": activity.best_for_energy_level or [],
            "total_completions": activity.total_completions,
            "is_premium": activity.is_premium,
        }

    async def _getRecentActivitySlugs(self, user_id: UUID, limit: int = 10) -> List[str]:
        """
        Lấy slugs của activities user đã làm gần đây
        Dùng để AI tránh suggest lại quá nhiều

        Returns:
            List of slugs (có thể rỗng nếu user mới)
        """
        try:
            result = await self.db.execute(
                select(ActivityLibrary.slug)
                .join(RoutineCompletion, RoutineCompletion.activity_id == ActivityLibrary.id)
                .where(RoutineCompletion.user_id == user_id)
                .order_by(RoutineCompletion.completed_at.desc())
                .limit(limit)
            )
            return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.warning(f"⚠️  Could not load recent activities: {e}")
            return []

    async def _parseAIRoutinePlan(self, ai_content: str) -> Dict:
        """
        Parse JSON response từ AI

        Giải thích:
        - AI có thể trả về markdown ```json...```
        - Cần strip markdown trước khi parse
        - Fallback nếu JSON invalid
        """
        content = ai_content.strip()

        # Strip markdown code block
        if content.startswith("```"):
            lines = content.split("\n")
            # Remove first line (```json) and last line (```)
            content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        try:
            data = json.loads(content)

            # Validate structure
            if "plan" not in data:
                raise ValueError("Missing 'plan' key in AI response")

            # Ensure all 5 days exist
            for day in range(1, 6):
                if f"day_{day}" not in data["plan"]:
                    data["plan"][f"day_{day}"] = []

            return data

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse AI routine JSON: {e}\nContent: {content[:200]}")
            # Return minimal fallback
            return {
                "title": "Routine Thư Giãn",
                "theme": "Bình Tĩnh",
                "reasoning": "Lộ trình cơ bản để bắt đầu.",
                "plan": {
                    "day_1": [
                        {"slug": "belly-breathing", "order": 1, "duration": 5},
                        {"slug": "body-scan", "order": 2, "duration": 10},
                        {"slug": "gratitude-journal", "order": 3, "duration": 5}
                    ],
                    "day_2": [
                        {"slug": "box-breathing", "order": 1, "duration": 5},
                        {"slug": "mindfulness-meditation", "order": 2, "duration": 10},
                        {"slug": "three-good-things", "order": 3, "duration": 5}
                    ],
                    "day_3": [
                        {"slug": "4-7-8-breathing", "order": 1, "duration": 5},
                        {"slug": "visualization-meditation", "order": 2, "duration": 10},
                        {"slug": "what-i-need-right-now", "order": 3, "duration": 5}
                    ],
                    "day_4": [
                        {"slug": "coherent-breathing", "order": 1, "duration": 10},
                        {"slug": "loving-kindness-meditation", "order": 2, "duration": 10},
                        {"slug": "emotion-dump", "order": 3, "duration": 10}
                    ],
                    "day_5": [
                        {"slug": "belly-breathing", "order": 1, "duration": 5},
                        {"slug": "body-scan", "order": 2, "duration": 10},
                        {"slug": "dear-future-me", "order": 3, "duration": 5}
                    ]
                }
            }
