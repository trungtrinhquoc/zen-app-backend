from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID, uuid4
import json
import asyncio
import time

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

def format_sse(event: str, data: dict) -> str:
    """Format SSE event with single-line JSON for proper parsing"""
    json_str = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {json_str}\n\n"


async def streamChatResponse(
    userId: UUID,
    request: ChatRequest,
    db: AsyncSession,
    background_tasks: BackgroundTasks
):
    """
    Stream chat response - OPTIMIZED: Fire AI immediately, don't wait for DB
    
    NEW FLOW:
    0ms:   Emotion analysis (rule-based, instant)
    0ms:   Fire DB tasks + AI streaming IN PARALLEL
    ~500ms: AI first token arrives → yield to user immediately
    ~1000ms: DB tasks complete (needed for background save later)
    """
    
    try:
        service = ConversationService(db)
        
        # ============================================================
        # STEP 0: Instant checks (< 1ms)
        # ============================================================
        
        # Fast path check BEFORE any async work
        if isSimplePattern(request.message):
            # Handle simple patterns - need DB for save though
            async for _ in _handleSimplePath(service, userId, request, db):
                yield _
            return
        
        # Rule-based emotion
        emotionData = await analyzeEmotionSimple(request.message)
        emotionState = emotionData.get("emotion_state", "neutral")
        
        # ============================================================
        # STEP 1: BUILD AI REQUEST IMMEDIATELY 
        # ============================================================
        
        systemPrompt = getSystemPrompt(
            userContext={"language": "vi"}, 
            emotionState=emotionState
        )
        
        messages_for_ai = [
            {"role": "system", "content": systemPrompt},
            {"role": "user", "content": request.message}
        ]
        
        # ============================================================
        # STEP 2: PARALLEL — Fire AI + DB simultaneously
        # ============================================================
        
        logger.info("🔄 PARALLEL: Starting AI stream + DB setup simultaneously...")
        parallel_start = time.time()
        
        db_ready = asyncio.Event()
        db_results = {}  
        
        async def _db_setup():
            """Run all DB setup in background"""
            try:
                phase1_start = time.time()
                
                task_user = service.getOrCreateUser(userId)
                
                if request.conversationId:
                    task_conv = service.getOrCreateConversation(userId, conversationId=request.conversationId)
                    task_context = service.getConversationContext(request.conversationId, limit=10)  # Reduced from 20
                    
                    results = await asyncio.gather(task_user, task_conv, task_context, return_exceptions=True)
                    
                    if isinstance(results[0], Exception): raise results[0]
                    db_results["user"] = results[0]
                    
                    if isinstance(results[1], Exception): raise results[1]
                    db_results["conversation"] = results[1]
                    
                    if isinstance(results[2], Exception):
                        logger.warning(f"⚠️ Context load error: {results[2]}")
                        db_results["contextMessages"] = []
                    else:
                        db_results["contextMessages"] = results[2]
                else:
                    user = await task_user
                    db_results["user"] = user
                    conversation = await service.getOrCreateConversation(userId, None)
                    db_results["conversation"] = conversation
                    db_results["contextMessages"] = []
                
                phase1_elapsed = (time.time() - phase1_start) * 1000
                logger.info(f"✅ DB Setup Complete: {phase1_elapsed:.0f}ms")
                
            except Exception as e:
                db_results["error"] = e
                logger.error(f"❌ DB setup error: {e}")
            finally:
                db_ready.set()
        
        db_task = asyncio.create_task(_db_setup())
        
        # ============================================================
        # STEP 3: STREAM AI RESPONSE IMMEDIATELY
        # ============================================================
        contextMessages_for_ai = []
        if request.conversationId:
            pass
        
        ttft_logged = False
        stream_start = time.time()
        full_content = ""
        chunk_count = 0
        
        chunk_count = 0
        
        async for chunk in openRouterService.chatStreaming(
            messages=messages_for_ai,
            temperature=0.8,
            maxTokens=500,
            model=settings.OPENROUTER_CHAT_MODEL
        ):
            if not ttft_logged:
                ttft = (time.time() - stream_start) * 1000
                total_ttfc = (time.time() - parallel_start) * 1000
                logger.info(f"⚡ AI TTFT: {ttft:.0f}ms | Total TTFC: {total_ttfc:.0f}ms")
                ttft_logged = True
            
            full_content += chunk
            chunk_count += 1
            yield format_sse("chunk", {"content": chunk})
        
        stream_elapsed = (time.time() - stream_start) * 1000
        
        # ============================================================
        # STEP 4: WAIT FOR DB (should already be done by now)
        # ============================================================
        
        if not db_ready.is_set():
            logger.info("⏳ Waiting for DB setup to complete...")
            await asyncio.wait_for(db_ready.wait(), timeout=10.0)
        
        # Check for DB errors
        if "error" in db_results:
            raise db_results["error"]
        
        user = db_results["user"]
        conversation = db_results["conversation"]
        contextMessages = db_results.get("contextMessages", [])
        contextUsed = len(contextMessages)
        
        # ============================================================
        # STEP 5: SUGGESTION + BACKGROUND SAVE 
        # ============================================================
        
        logger.info("🔄 Scheduling background save...")
        
        metadata = {
            "model": settings.OPENROUTER_CHAT_MODEL,
            "promptTokens": 0,
            "completionTokens": 0,
            "responseTimeMs": int(stream_elapsed)
        }
        
        seqNum = len(contextMessages) + 1
        
        # Suggestion Logic
        lastAssistantMsg = ""
        for msg in reversed(contextMessages):
            if msg.role == "assistant": 
                lastAssistantMsg = msg.content
                break
        
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
            emotionData, 
            request.message,
            conversationTurnCount=seqNum,
            lastAssistantMessage=lastAssistantMsg,
            context=context
        ):
            activity = getSuggestedActivity(
                emotionData, 
                userMessage=request.message,
                userLanguage=user.language or "vi",
                context=context
            )
            if activity:
                suggestion = activity
                suggestionMsg = generateSuggestionMessage(activity)
                full_content += f"\n\n{suggestionMsg}"
                logger.info(f"💡 Suggested: {activity['activity_type']}")
        
        # Schedule Background Task
        background_tasks.add_task(
            service.saveChatTurn,
            conversationId=conversation.id,
            userId=userId,
            requestMessage=request.message,
            aiContent=full_content,
            seqNum=seqNum,
            emotionData=emotionData,
            metadata=metadata,
            contextMessages=contextMessages, 
            suggestion=suggestion,
            conversationTitle=conversation.title
        )

        logger.info("✅ Background save scheduled.")

        # Send metadata
        metadata_response = {
            "conversationId": str(conversation.id),
            "userMessage": {
                "id": str(uuid4()), 
                "role": "user",
                "content": request.message,
                "contentType": "text",
                "sequenceNumber": seqNum,
                "createdAt": datetime.utcnow().isoformat() + "Z",
                "emotionState": emotionData['emotion_state'],
                "energyLevel": emotionData['energy_level'],
                "urgencyLevel": emotionData['urgency_level'],
                "detectedThemes": emotionData['detected_themes']
            },
            "assistantMessage": {
                "id": str(uuid4()),  
                "role": "assistant",
                "content": full_content,
                "contentType": "text",
                "sequenceNumber": seqNum + 1,
                "createdAt": datetime.utcnow().isoformat() + "Z",
                "modelUsed": metadata.get('model'),
                "promptTokens": metadata.get('promptTokens'),
                "completionTokens": metadata.get('completionTokens'),
                "responseTimeMs": metadata.get('responseTimeMs')
            },
            "contextUsed": contextUsed,
            "suggestion": suggestion
        }
        yield format_sse("metadata", metadata_response)
        yield format_sse("done", {})
        
    except Exception as e:
        logger.error(f"❌ Streaming error: {e}")
        yield format_sse("error", {'error': str(e)})
        yield format_sse("done", {})


async def _handleSimplePath(service, userId, request, db):
    """Handle simple pattern messages with fast response"""
    phase1_start = time.time()
    
    # Still need DB for saving
    user = await service.getOrCreateUser(userId)
    conversation = await service.getOrCreateConversation(userId, request.conversationId)
    contextMessages = []
    if request.conversationId:
        contextMessages = await service.getConversationContext(request.conversationId, limit=10)
    
    aiContent, metadata = getSimpleResponse(request.message)
    emotionData = {
        "emotion_state": "neutral",
        "energy_level": 5,
        "urgency_level": "low",
        "detected_themes": ["general"],
        "method": "rule_based"
    }
    
    # Stream immediately (no simulated delay for simple responses — instant!)
    yield format_sse("chunk", {"content": aiContent})
    
    seqNum = len(contextMessages) + 1
    
    # Save in background-ish (after yield)
    await service.saveMessage(
        conversationId=conversation.id, userId=userId, role="user",
        content=request.message, sequenceNumber=seqNum,
        emotionData=emotionData,
        metadata={"is_voice_input": request.isVoiceInput, "voice_duration": request.voiceDuration, "content_type": "voice" if request.isVoiceInput else "text"}
    )
    await service.saveMessage(
        conversationId=conversation.id, userId=userId, role="assistant",
        content=aiContent, sequenceNumber=seqNum + 1, metadata=metadata
    )
    await service.updateEmotionProgression(
        conversationId=conversation.id, emotionState=emotionData['emotion_state'], energyLevel=emotionData['energy_level']
    )
    await service.db.commit()
    
    metadata_response = {
        "conversationId": str(conversation.id),
        "userMessage": {"id": str(uuid4()), "role": "user", "content": request.message, "contentType": "text", "sequenceNumber": seqNum, "createdAt": datetime.utcnow().isoformat() + "Z", "emotionState": emotionData['emotion_state'], "energyLevel": emotionData['energy_level'], "urgencyLevel": emotionData['urgency_level'], "detectedThemes": emotionData['detected_themes']},
        "assistantMessage": {"id": str(uuid4()), "role": "assistant", "content": aiContent, "contentType": "text", "sequenceNumber": seqNum + 1, "createdAt": datetime.utcnow().isoformat() + "Z", "modelUsed": metadata.get('model')},
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
    logger.info("🚀 STREAMING CHAT REQUEST STARTED")
    logger.info(f"📍 User ID: {request.userId}")
    logger.info(f"💬 Message: {request.message}")
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