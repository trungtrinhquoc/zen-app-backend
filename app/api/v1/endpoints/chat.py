"""
Chat Endpoints
API cho chat conversations
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.database import getDbSession
from app.schemas import ChatRequest, ChatResponse, ConversationResponse, ConversationDetailResponse
from app.modules.conversation.service import ConversationService
from sqlalchemy import select, desc

router = APIRouter()


@router.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(getDbSession)
):
    """
    💬 Chat với AI
    
    Giải thích:
    - Main endpoint cho chat
    - Accept ChatRequest body
    - Return ChatResponse
    
    Request Body:
    {
        "message": "Hôm nay mình cảm thấy lo lắng về công việc...",
        "conversation_id": null,  // null = tạo conversation mới
        "include_context": true   // true = load 20 messages gần nhất
    }
    
    Response:
    {
        "conversation_id": "uuid-here",
        "user_message": {
            "id": "uuid",
            "role": "user",
            "content": "...",
            "emotion_state": "anxious",
            "energy_level": 3,
            "urgency_level": "medium",
            "detected_themes": ["work", "stress"],
            "sequence_number": 1,
            "created_at": "2024-01-30T10:00:00"
        },
        "assistant_message": {
            "id": "uuid",
            "role": "assistant",
            "content": "Mình hiểu bạn đang lo lắng...\n\nMình có gợi ý nhỏ: Bạn thử bài tập hít thở (5 phút) nhé? 💙",
            "model_used": "openai/gpt-4o-mini",
            "prompt_tokens": 234,
            "completion_tokens": 120,
            "response_time_ms": 1456,
            "sequence_number": 2,
            "created_at": "2024-01-30T10:00:01"
        },
        "context_used": 0,
        "suggestion": {
            "activity_type": "breathing",
            "activity_name": "Bài tập hít thở",
            "duration": 5,
            "reason": "Bài tập hít thở phù hợp khi bạn đang cảm thấy anxious",
            "description": "Hít thở sâu 4-7-8 để thư giãn"
        }
    }
    
    Flow:
    1. Validate request (Pydantic auto)
    2. Get DB session (Depends injection)
    3. Create ConversationService
    4. Call service.chat()
    5. Return response (Pydantic auto serialize)
    
    ⚠️ TODO: Get userId từ JWT token (Supabase Auth)
    Hiện tại dùng hardcoded UUID cho testing
    """
    
    # TODO: Get userId từ JWT token
    # from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    # token = credentials.credentials
    # userId = verify_token(token)
    
    # Temporary: Fixed user ID cho testing
    from uuid import UUID
    tempUserId = UUID("25f1e353-566d-4ef2-8927-32c9fddada42")
    
    service = ConversationService(db)
    return await service.chat(tempUserId, request)


@router.get("/conversations", response_model=List[ConversationResponse])
async def getConversations(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(getDbSession)
):
    """
    📚 Lấy danh sách conversations
    
    Giải thích:
    - List conversations của user
    - Pagination với limit + offset
    - Order by updated_at DESC (mới nhất trước)
    
    Query Parameters:
    - limit: Số conversations tối đa (default: 20)
    - offset: Skip bao nhiêu records (default: 0)
    
    Response:
    [
        {
            "id": "uuid",
            "user_id": "uuid",
            "title": "New Chat",
            "status": "active",
            "message_count": 4,
            "dominant_emotion": "anxious",
            "started_at": "2024-01-30T10:00:00",
            "created_at": "2024-01-30T10:00:00"
        },
        ...
    ]
    
    ⚠️ TODO: Filter by user_id từ auth token
    """
    from app.models import Conversation
    
    # TODO: Filter by real user_id
    stmt = select(Conversation).order_by(
        desc(Conversation.updated_at)
    ).limit(limit).offset(offset)
    
    result = await db.execute(stmt)
    conversations = result.scalars().all()
    
    return conversations


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def getConversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(getDbSession)
):
    """
    📖 Lấy conversation detail với messages
    
    Giải thích:
    - Get 1 conversation by ID
    - Include tất cả messages
    - Messages auto-loaded bởi SQLAlchemy relationship
    
    Path Parameter:
    - conversation_id: UUID của conversation
    
    Response:
    {
        "id": "uuid",
        "user_id": "uuid",
        "title": "Chat about work stress",
        "status": "active",
        "message_count": 10,
        "dominant_emotion": "stressed",
        "started_at": "2024-01-30T10:00:00",
        "created_at": "2024-01-30T10:00:00",
        "messages": [
            {
                "id": "uuid",
                "role": "user",
                "content": "...",
                "emotion_state": "stressed",
                "sequence_number": 1,
                ...
            },
            {
                "id": "uuid",
                "role": "assistant",
                "content": "...",
                "model_used": "openai/gpt-4o-mini",
                "sequence_number": 2,
                ...
            },
            ...
        ]
    }
    
    Raises:
    - 404: Conversation not found
    """
    from app.models import Conversation
    from app.utils.exceptions import NotFoundException
    
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise NotFoundException(f"Conversation {conversation_id} not found")
    
    return conversation


"""
Giải thích FastAPI Endpoints:

1. Decorators:
   - @router.post("/chat"): HTTP POST to /chat
   - response_model=ChatResponse: Auto serialize response
   - status_code=200: Success status code
   
2. Dependencies:
   - Depends(getDbSession): Inject DB session
   - Auto cleanup sau khi request done
   
3. Path Parameters:
   - {conversation_id}: Extract từ URL path
   - Auto parse thành UUID type
   
4. Query Parameters:
   - limit: int = 20: Default value 20
   - Extract từ ?limit=10&offset=5
   
5. Request Body:
   - request: ChatRequest: Parse từ JSON body
   - Auto validate với Pydantic
   
6. Response:
   - Return Python object (dict, list, Pydantic model)
   - FastAPI auto serialize thành JSON
   - Validate với response_model
"""