"""
Conversation History Endpoints
API endpoints cho quản lý lịch sử hội thoại
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel, Field

from app.database import getDbSession
from app.modules.conversation.service import ConversationService
from app.schemas.conversation import ConversationResponse, ConversationDetailResponse
from app.utils.logger import logger
from app.utils.exceptions import NotFoundException

router = APIRouter()


class UpdateConversationRequest(BaseModel):
    """Request schema cho update conversation"""
    title: Optional[str] = Field(None, max_length=200)
    status: Optional[str] = Field(None, pattern="^(active|ended|archived)$")


class ConversationListResponse(BaseModel):
    """Response schema cho list conversations"""
    conversations: List[ConversationResponse]
    total: int
    limit: int
    offset: int


@router.get("", response_model=ConversationListResponse)
async def listConversations(
    userId: UUID = Query(..., description="User ID"),
    limit: int = Query(20, ge=1, le=100, description="Number of conversations to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(getDbSession)
):
    """
    Lấy danh sách conversations của user
    
    Args:
        userId: User ID
        limit: Số conversations tối đa (1-100, default: 20)
        offset: Offset cho pagination (default: 0)
    
    Returns:
        ConversationListResponse với list conversations và pagination info
    """
    logger.info(f"📋 List conversations: userId={userId}, limit={limit}, offset={offset}")
    
    service = ConversationService(db)
    conversations, total = await service.listUserConversations(
        userId=userId,
        limit=limit,
        offset=offset
    )
    
    return ConversationListResponse(
        conversations=[
            ConversationResponse.model_validate(conv)
            for conv in conversations
        ],
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def getConversationDetail(
    conversation_id: UUID,
    userId: UUID = Query(..., description="User ID for ownership verification"),
    db: AsyncSession = Depends(getDbSession)
):
    """
    Lấy chi tiết conversation với tất cả messages
    
    Args:
        conversation_id: Conversation ID
        userId: User ID (để verify ownership)
    
    Returns:
        ConversationDetailResponse với full conversation data
    
    Raises:
        404: Nếu conversation không tồn tại hoặc không thuộc user
    """
    logger.info(f"📖 Get conversation detail: {conversation_id}")
    
    service = ConversationService(db)
    
    try:
        conversation = await service.getConversationDetail(
            conversationId=conversation_id,
            userId=userId
        )
        
        return ConversationDetailResponse.model_validate(conversation)
        
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{conversation_id}")
async def deleteConversation(
    conversation_id: UUID,
    userId: UUID = Query(..., description="User ID for ownership verification"),
    db: AsyncSession = Depends(getDbSession)
):
    """
    Xóa conversation (soft delete)
    
    Args:
        conversation_id: Conversation ID
        userId: User ID (để verify ownership)
    
    Returns:
        Success message
    
    Raises:
        404: Nếu conversation không tồn tại hoặc không thuộc user
    """
    logger.info(f"🗑️ Delete conversation: {conversation_id}")
    
    service = ConversationService(db)
    
    try:
        await service.deleteConversation(
            conversationId=conversation_id,
            userId=userId
        )
        
        return {"message": "Conversation deleted successfully"}
        
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def updateConversation(
    conversation_id: UUID,
    request: UpdateConversationRequest,
    userId: UUID = Query(..., description="User ID for ownership verification"),
    db: AsyncSession = Depends(getDbSession)
):
    """
    Cập nhật conversation metadata
    
    Args:
        conversation_id: Conversation ID
        request: Update data (title, status)
        userId: User ID (để verify ownership)
    
    Returns:
        Updated ConversationResponse
    
    Raises:
        404: Nếu conversation không tồn tại hoặc không thuộc user
    """
    logger.info(f"✏️ Update conversation: {conversation_id}")
    
    service = ConversationService(db)
    
    try:
        conversation = await service.updateConversation(
            conversationId=conversation_id,
            userId=userId,
            title=request.title,
            status=request.status
        )
        
        return ConversationResponse.model_validate(conversation)
        
    except NotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
