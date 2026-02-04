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