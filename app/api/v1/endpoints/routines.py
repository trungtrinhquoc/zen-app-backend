"""
Routine Endpoints
API endpoints cho Module 5 - Routine System

ENDPOINTS:
    POST /routines/generate       → Tạo routine mới
    GET  /routines/active         → Lấy routine đang active
    GET  /routines/history        → Lịch sử routines
    POST /routines/{id}/complete-step → Hoàn thành 1 step
    POST /routines/{id}/abandon   → Bỏ routine
    GET  /activities              → Browse activity library

Giải thích pattern:
- userId được truyền qua Query param (giống conversations.py)
- Service layer xử lý toàn bộ logic
- Endpoint chỉ: validate → gọi service → trả response
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional

from app.database import getDbSession
from app.modules.routine.service import RoutineService
from app.schemas.routine import (
    GenerateRoutineRequest,
    CompleteStepRequest,
    AbandonRoutineRequest,
    ActivityListResponse,
    RoutineResponse,
    RoutineListResponse,
    ActivityResponse,
)
from app.utils.logger import logger

router = APIRouter()


# ============================================================
# ACTIVITY LIBRARY
# ============================================================

@router.get("/activities", response_model=ActivityListResponse)
async def getActivities(
    category: Optional[str] = Query(None, description="Filter by category: breathing|meditation|journaling|listening|movement|reflection"),
    emotion: Optional[str] = Query(None, description="Filter by emotion suitability (vd: 'anxious', 'sad')"),
    energy_level: Optional[int] = Query(None, ge=1, le=10, description="Filter by energy level (1-10)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(getDbSession)
):
    """
    Browse activity library với optional filters

    Ví dụ:
    - GET /activities → Tất cả activities
    - GET /activities?category=breathing → Chỉ breathing
    - GET /activities?emotion=anxious&energy_level=3 → Phù hợp với anxious, low energy
    """
    logger.info(f"📚 Get activities: cat={category}, emotion={emotion}, energy={energy_level}")
    service = RoutineService(db)

    activities, total = await service.getActivityLibrary(
        category=category,
        emotion=emotion,
        energy_level=energy_level,
        limit=limit,
        offset=offset
    )

    return ActivityListResponse(
        activities=[ActivityResponse.model_validate(a) for a in activities],
        total=total,
        category=category
    )


# ============================================================
# ROUTINE MANAGEMENT
# ============================================================

@router.post("/generate", response_model=RoutineResponse)
async def generateRoutine(
    request: GenerateRoutineRequest,
    db: AsyncSession = Depends(getDbSession)
):
    """
    Tạo routine 5 ngày mới bằng AI

    Nếu user đã có active routine → trả về routine hiện tại (không tạo mới).

    Body:
    ```json
    {
      "userId": "uuid",
      "emotion": "anxious",
      "energyLevel": 3,
      "preferences": {}
    }
    ```
    """
    logger.info(
        f"🎯 Generate routine: userId={request.user_id}, "
        f"emotion={request.emotion}, energy={request.energy_level}"
    )

    service = RoutineService(db)

    try:
        routine_orm = await service.generateRoutine(
            user_id=request.user_id,
            emotion=request.emotion,
            energy_level=request.energy_level,
            preferences=request.preferences
        )

        # Resolve activities vào response
        routine_dict = await service._resolveRoutine(routine_orm, request.user_id)

        return _buildRoutineResponse(routine_dict)

    except Exception as e:
        logger.error(f"❌ Generate routine failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Không thể tạo routine: {str(e)}")


@router.get("/active", response_model=Optional[RoutineResponse])
async def getActiveRoutine(
    userId: UUID = Query(..., description="User ID"),
    db: AsyncSession = Depends(getDbSession)
):
    """
    Lấy routine đang active của user

    Returns:
    - Routine object nếu có active routine
    - null nếu không có (frontend sẽ hiển thị màn generate)
    """
    logger.info(f"🔍 Get active routine: userId={userId}")
    service = RoutineService(db)

    routine_dict = await service.getActiveRoutine(userId)

    if not routine_dict:
        return None

    return _buildRoutineResponse(routine_dict)


@router.get("/history", response_model=RoutineListResponse)
async def getRoutineHistory(
    userId: UUID = Query(..., description="User ID"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(getDbSession)
):
    """
    Lấy lịch sử routines đã completed hoặc abandoned

    Dùng để: Xem bạn đã làm những routine nào, progress của từng routine
    """
    logger.info(f"📋 Get routine history: userId={userId}")
    service = RoutineService(db)

    routines, total = await service.getRoutineHistory(
        user_id=userId,
        limit=limit,
        offset=offset
    )

    return RoutineListResponse(
        routines=[_buildRoutineResponse(r) for r in routines],
        total=total,
        limit=limit,
        offset=offset
    )


@router.post("/{routine_id}/complete-step")
async def completeStep(
    routine_id: UUID,
    request: CompleteStepRequest,
    db: AsyncSession = Depends(getDbSession)
):
    """
    Đánh dấu 1 step trong routine đã hoàn thành

    Returns:
    ```json
    {
      "success": true,
      "completionId": "uuid",
      "isRoutineCompleted": false,
      "totalCompleted": 5,
      "totalSteps": 15,
      "nextDay": 2
    }
    ```

    Nếu `isRoutineCompleted = true` → routine kết thúc, chúc mừng user!
    """
    logger.info(
        f"✅ Complete step: routine={routine_id}, "
        f"day={request.day_number}, step={request.step_number}"
    )

    service = RoutineService(db)

    try:
        result = await service.completeStep(
            user_id=request.user_id,
            routine_id=routine_id,
            day_number=request.day_number,
            step_number=request.step_number,
            actual_duration_minutes=request.actual_duration_minutes,
            emotion_before=request.emotion_before,
            emotion_after=request.emotion_after,
            energy_before=request.energy_before,
            energy_after=request.energy_after,
            user_rating=request.user_rating,
            user_notes=request.user_notes
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Complete step failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi ghi nhận completion: {str(e)}")


@router.post("/{routine_id}/abandon")
async def abandonRoutine(
    routine_id: UUID,
    request: AbandonRoutineRequest,
    db: AsyncSession = Depends(getDbSession)
):
    """
    Bỏ routine đang active

    Sau khi bỏ, user có thể generate routine mới.
    """
    logger.info(f"🚫 Abandon routine: {routine_id}")

    service = RoutineService(db)

    try:
        result = await service.abandonRoutine(
            user_id=request.user_id,
            routine_id=routine_id
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Abandon routine failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# HELPER
# ============================================================

def _buildRoutineResponse(routine_dict: dict) -> RoutineResponse:
    """
    Convert routine dict → RoutineResponse Pydantic model

    Giải thích:
    - _resolveRoutine trả về dict (dễ manipulate)
    - Cần convert sang Pydantic model để FastAPI serialize đúng
    - model_validate: Pydantic v2 method (tương đương v1's from_orm)
    """
    from app.schemas.routine import RoutineDay, RoutinePlanStep, ActivityResponse

    days = []
    for day_data in routine_dict.get("days", []):
        steps = []
        for step_data in day_data.get("steps", []):
            activity_data = step_data.get("activity")
            activity = ActivityResponse.model_validate(activity_data) if activity_data else None
            steps.append(RoutinePlanStep(
                activity_id=step_data.get("activity_id"),
                slug=step_data.get("slug", ""),
                order=step_data.get("order", 0),
                duration=step_data.get("duration"),
                activity=activity
            ))
        days.append(RoutineDay(
            day_number=day_data["day_number"],
            steps=steps
        ))

    return RoutineResponse(
        id=routine_dict["id"],
        user_id=routine_dict["user_id"],
        title=routine_dict["title"],
        theme=routine_dict.get("theme"),
        days=days,
        status=routine_dict["status"],
        current_day=routine_dict["current_day"],
        generated_for_emotion=routine_dict.get("generated_for_emotion"),
        generated_for_energy=routine_dict.get("generated_for_energy"),
        generation_reasoning=routine_dict.get("generation_reasoning"),
        completed_steps=routine_dict.get("completed_steps", []),
        progress_percent=routine_dict.get("progress_percent", 0.0),
        started_at=routine_dict["started_at"],
        completed_at=routine_dict.get("completed_at"),
        created_at=routine_dict["created_at"],
    )
