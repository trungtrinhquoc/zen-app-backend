from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID, uuid4
import json
import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from app.database import getDbSession
from app.schemas.conversation import ChatRequest
from app.modules.conversation.service import ConversationService
from app.modules.conversation.simple_responder import isSimplePattern, getSimpleResponse
from app.modules.conversation.emotion_analyzer import analyzeEmotionSimple
from app.modules.conversation.suggestion_engine import (
    shouldSuggestActivity,
    getSuggestedActivity,
    generateSuggestionMessage,
    ConversationContext
)
from app.services.openrouter_client import openRouterService
from app.modules.conversation.prompts import getSystemPrompt, formatMessagesForAI
from app.utils.logger import logger
from app.models import Conversation
from app.modules.memory.service import MemoryService
from app.core.config import settings
from datetime import datetime

router = APIRouter()


# ============================================================
# IN-MEMORY MESSAGE CACHE
# Eliminates ~800ms Supabase query on every request
# ============================================================

@dataclass
class CachedMsg:
    """Lightweight message for cache (not SQLAlchemy model)"""
    role: str
    content: str
    metadata: Optional[Dict] = None


# conversationId (str) -> list of CachedMsg
_MSG_CACHE: Dict[str, List[CachedMsg]] = {}


def _get_cached_context(conv_id: str) -> Optional[List[CachedMsg]]:
    """Get cached messages for a conversation. Returns None if not cached."""
    return _MSG_CACHE.get(conv_id)


def _update_cache(conv_id: str, messages: List[CachedMsg]):
    """Set/replace full cache for a conversation."""
    _MSG_CACHE[conv_id] = messages


def _append_to_cache(conv_id: str, user_msg: str, ai_msg: str, suggestion: Optional[Dict] = None):
    """Append a new turn (user + assistant) to cache."""
    if conv_id not in _MSG_CACHE:
        _MSG_CACHE[conv_id] = []
    _MSG_CACHE[conv_id].append(CachedMsg(role="user", content=user_msg))
    _MSG_CACHE[conv_id].append(CachedMsg(
        role="assistant",
        content=ai_msg,
        metadata={"suggestion": suggestion} if suggestion else None
    ))


# ============================================================

def format_sse(event: str, data: dict) -> str:
    json_str = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {json_str}\n\n"


async def streamChatResponse(
    userId: UUID,
    request: ChatRequest,
    db: AsyncSession,
    background_tasks: BackgroundTasks
):
    """
    Stream chat response - ULTRA OPTIMIZED

    FLOW:
    1. Emotion analysis (rule-based, <1ms)
    2. User lookup (in-memory cache, <1ms after first)
    3. Conversation lookup (in-memory cache, <1ms after first)
    4. Context messages:
       - FIRST TIME: query DB (~800ms) then cache
       - SUBSEQUENT: read from in-memory cache (<1ms!)
    5. Build AI messages WITH full context
    6. Stream AI response immediately
    7. After stream: update cache + schedule background DB save
    """

    try:
        service = ConversationService(db)
        start_time = time.time()

        # ============================================================
        # STEP 0: Simple pattern fast path
        # ============================================================
        if isSimplePattern(request.message):
            async for event in _handleSimplePath(service, userId, request, db, background_tasks):
                yield event
            return

        emotionData = await analyzeEmotionSimple(request.message)
        emotionState = emotionData.get("emotion_state", "neutral")

        # ============================================================
        # STEP 1: User + Conversation (cached in-memory, ~0ms)
        # ============================================================
        setup_start = time.time()
        user = await service.getOrCreateUser(userId)

        if request.conversationId:
            conversation = await service.getOrCreateConversation(userId, conversationId=request.conversationId)
        else:
            conversation = await service.getOrCreateConversation(userId, None)

        conv_id_str = str(conversation.id)

        # ============================================================
        # STEP 2: Context messages - USE CACHE FIRST
        # ============================================================
        cached = _get_cached_context(conv_id_str)

        if cached is not None:
            # CACHE HIT → 0ms, no DB query!
            contextMessages = cached
            cache_source = "cache"
        elif request.conversationId:
            # CACHE MISS (first request for this conv) → query DB
            db_messages = await service.getConversationContext(request.conversationId, limit=8)
            # Convert to CachedMsg and store
            contextMessages = [
                CachedMsg(
                    role=msg.role,
                    content=msg.content,
                    metadata=msg.metadata if hasattr(msg, 'metadata') else None
                )
                for msg in db_messages
            ]
            _update_cache(conv_id_str, contextMessages)
            cache_source = "db"
        else:
            # New conversation → empty, start caching
            contextMessages = []
            _update_cache(conv_id_str, [])
            cache_source = "new"

        setup_ms = (time.time() - setup_start) * 1000
        logger.info(f"Setup: {setup_ms:.0f}ms | History: {len(contextMessages)} msgs [{cache_source}]")

        # ============================================================
        # STEP 3: Build AI messages WITH context
        # ============================================================
        lastAssistantMsg_for_prompt = ""
        for msg in reversed(contextMessages):
            if msg.role == "assistant":
                lastAssistantMsg_for_prompt = msg.content
                break

        systemPrompt = getSystemPrompt(
            userContext={"language": user.language or "vi"},
            emotionState=emotionState,
            lastAssistantMessage=lastAssistantMsg_for_prompt,
            currentUserMessage=request.message
        )

        messages_for_ai = [{"role": "system", "content": systemPrompt}]
        for msg in contextMessages[-6:]:
            if msg.role in ["user", "assistant"]:
                content = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
                messages_for_ai.append({"role": msg.role, "content": content})
        messages_for_ai.append({"role": "user", "content": request.message})

        logger.info(f"AI: {len(messages_for_ai)} msgs (1 sys + {min(len(contextMessages), 6)} hist + 1 cur)")

        # ============================================================
        # STEP 4: Stream AI response
        # ============================================================
        ttft_logged = False
        stream_start = time.time()
        full_content = ""
        chunk_count = 0

        async for chunk in openRouterService.chatStreaming(
            messages=messages_for_ai,
            temperature=0.8,
            maxTokens=400,
            model=settings.OPENROUTER_CHAT_MODEL
        ):
            if not ttft_logged:
                ttft_ms = (time.time() - stream_start) * 1000
                total_ms = (time.time() - start_time) * 1000
                logger.info(f"TTFT: {ttft_ms:.0f}ms | Total-to-first-token: {total_ms:.0f}ms")
                ttft_logged = True

            full_content += chunk
            chunk_count += 1
            yield format_sse("chunk", {"content": chunk})

        stream_ms = (time.time() - stream_start) * 1000
        total_time = (time.time() - start_time) * 1000
        logger.info(f"Stream: {stream_ms:.0f}ms, {chunk_count} chunks | Total: {total_time:.0f}ms")

        # ============================================================
        # STEP 5: Update in-memory cache immediately
        # ============================================================
        seqNum = len(contextMessages) + 1

        # Suggestion logic
        lastAssistantMsg = lastAssistantMsg_for_prompt
        context = ConversationContext(
            turn_count=seqNum,
            last_assistant_message=lastAssistantMsg
        )
        for msg in contextMessages:
            if msg.role == "assistant" and msg.metadata:
                if isinstance(msg.metadata, dict) and msg.metadata.get("suggestion"):
                    context.has_suggested_in_session = True
                    suggested_type = msg.metadata["suggestion"].get("activity_type")
                    if suggested_type:
                        context.suggested_activities.append(suggested_type)

        suggestion = None
        if shouldSuggestActivity(
            emotionData, request.message,
            conversationTurnCount=seqNum,
            lastAssistantMessage=lastAssistantMsg,
            context=context
        ):
            activity = getSuggestedActivity(
                emotionData, userMessage=request.message,
                userLanguage=user.language or "vi", context=context
            )
            if activity:
                suggestion = activity
                logger.info(f"Suggested: {activity['activity_type']}")

        # Update cache with this turn (instant, for next request)
        _append_to_cache(conv_id_str, request.message, full_content, suggestion)

        # ============================================================
        # STEP 6: Schedule background DB save
        # ============================================================
        metadata = {
            "model": settings.OPENROUTER_CHAT_MODEL,
            "promptTokens": 0,
            "completionTokens": 0,
            "responseTimeMs": int(stream_ms)
        }

        background_tasks.add_task(
            service.saveChatTurn,
            conversationId=conversation.id,
            userId=userId,
            requestMessage=request.message,
            aiContent=full_content,
            seqNum=seqNum,
            emotionData=emotionData,
            metadata=metadata,
            contextMessages=contextMessages,  # Pass cached context for memory save logic
            suggestion=suggestion,
            conversationTitle=conversation.title
        )

        # ============================================================
        # STEP 7: Send metadata + done
        # ============================================================
        metadata_response = {
            "conversationId": str(conversation.id),
            "userMessage": {
                "id": str(uuid4()),
                "role": "user",
                "content": request.message,
                "contentType": "text",
                "sequenceNumber": seqNum,
                "createdAt": datetime.utcnow().isoformat() + "Z",
                "emotionState": emotionData["emotion_state"],
                "energyLevel": emotionData["energy_level"],
                "urgencyLevel": emotionData["urgency_level"],
                "detectedThemes": emotionData["detected_themes"]
            },
            "assistantMessage": {
                "id": str(uuid4()),
                "role": "assistant",
                "content": full_content,
                "contentType": "text",
                "sequenceNumber": seqNum + 1,
                "createdAt": datetime.utcnow().isoformat() + "Z",
                "modelUsed": metadata.get("model"),
                "promptTokens": metadata.get("promptTokens"),
                "completionTokens": metadata.get("completionTokens"),
                "responseTimeMs": metadata.get("responseTimeMs")
            },
            "contextUsed": len(contextMessages),
            "suggestion": suggestion
        }
        yield format_sse("metadata", metadata_response)
        yield format_sse("done", {})

    except Exception as e:
        logger.error(f"Streaming error: {e}", exc_info=True)
        yield format_sse("error", {"error": str(e)})
        yield format_sse("done", {})


async def _handleSimplePath(service, userId, request, db, background_tasks: BackgroundTasks):
    """Handle simple patterns with instant response, background save"""
    user = await service.getOrCreateUser(userId)
    if request.conversationId:
        conversation = await service.getOrCreateConversation(userId, conversationId=request.conversationId)
    else:
        conversation = await service.getOrCreateConversation(userId, None)

    conv_id_str = str(conversation.id)

    # Use cache for context
    cached = _get_cached_context(conv_id_str)
    if cached is not None:
        contextMessages = cached
    elif request.conversationId:
        db_msgs = await service.getConversationContext(request.conversationId, limit=4)
        contextMessages = [CachedMsg(role=m.role, content=m.content, metadata=m.metadata if hasattr(m, 'metadata') else None) for m in db_msgs]
        _update_cache(conv_id_str, contextMessages)
    else:
        contextMessages = []
        _update_cache(conv_id_str, [])

    aiContent, metadata_info = getSimpleResponse(request.message)
    emotionData = {
        "emotion_state": "neutral", "energy_level": 5,
        "urgency_level": "low", "detected_themes": ["general"], "method": "rule_based"
    }

    yield format_sse("chunk", {"content": aiContent})

    seqNum = len(contextMessages) + 1
    _append_to_cache(conv_id_str, request.message, aiContent)

    background_tasks.add_task(
        service.saveChatTurn,
        conversationId=conversation.id, userId=userId,
        requestMessage=request.message, aiContent=aiContent,
        seqNum=seqNum, emotionData=emotionData,
        metadata={"model": "simple-responder", "promptTokens": 0, "completionTokens": 0, "responseTimeMs": 0},
        contextMessages=[], suggestion=None, conversationTitle=conversation.title
    )

    metadata_response = {
        "conversationId": str(conversation.id),
        "userMessage": {
            "id": str(uuid4()), "role": "user", "content": request.message,
            "contentType": "text", "sequenceNumber": seqNum,
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "emotionState": "neutral", "energyLevel": 5,
            "urgencyLevel": "low", "detectedThemes": ["general"]
        },
        "assistantMessage": {
            "id": str(uuid4()), "role": "assistant", "content": aiContent,
            "contentType": "text", "sequenceNumber": seqNum + 1,
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "modelUsed": "simple-responder"
        },
        "contextUsed": len(contextMessages),
        "suggestion": None
    }
    yield format_sse("metadata", metadata_response)
    yield format_sse("done", {})


@router.post("/stream")
async def chatStream(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(getDbSession)
):
    logger.info("=" * 80)
    logger.info(f"STREAMING CHAT | User: {request.userId} | Conv: {request.conversationId}")
    logger.info(f"Message: {request.message}")
    logger.info("=" * 80)

    return StreamingResponse(
        streamChatResponse(request.userId, request, db, background_tasks),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )