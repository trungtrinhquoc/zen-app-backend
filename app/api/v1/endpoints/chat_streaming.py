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
    Stream chat response chunk by chunk
    
    Yields SSE events:
    - event: chunk, data: {"content": "..."}
    - event: metadata, data: {"emotion": "...", "conversationId": "..."}
    - event: done, data: {}
    """
    
    try:
        service = ConversationService(db)
        
        # ============================================================
        # PHASE 1: Setup (user, conversation, context)
        # ============================================================
        
        logger.info("🔄 PHASE 1 (Streaming): Setup...")
        phase1_start = time.time()
        
        # 1. Prepare tasks
        task_user = service.getOrCreateUser(userId)
        
        # Variables to hold results
        conversation = None
        contextMessages = []
        
        # Logic: If client sends conversationId, we can fetch context in parallel
        if request.conversationId:
            task_conv = service.getOrCreateConversation(userId, conversationId=request.conversationId)
            task_context = service.getConversationContext(request.conversationId)
            
            # Run 3 tasks concurrently
            results = await asyncio.gather(task_user, task_conv, task_context, return_exceptions=True)
            
            # Handle User result
            if isinstance(results[0], Exception): raise results[0]
            user = results[0]
            
            # Handle Conversation result
            if isinstance(results[1], Exception): raise results[1]
            conversation = results[1]
            
            # Handle Context result (log warning on error, default to empty)
            if isinstance(results[2], Exception):
                logger.warning(f"⚠️ Context load error: {results[2]}")
                contextMessages = []
            else:
                contextMessages = results[2]
                
        else:
            # New Chat Case (no ID): Sequential flow required
            # 1. Get User
            user = await task_user
            # 2. Create Conversation
            conversation = await service.getOrCreateConversation(userId, None)
            # 3. Context is empty for new chat
            contextMessages = []

        contextUsed = len(contextMessages)
        phase1_elapsed = (time.time() - phase1_start) * 1000
        logger.info(f"✅ Phase 1 Complete: {phase1_elapsed:.0f}ms (Parallel) - used {contextUsed} msgs")
        
        # ============================================================
        # FAST PATH: Simple patterns
        # ============================================================
        
        if isSimplePattern(request.message):
            #logger.info("⚡ FAST PATH (Streaming): Simple pattern")
            
            aiContent, metadata = getSimpleResponse(request.message)
            emotionData = {
                "emotion_state": "neutral",
                "energy_level": 5,
                "urgency_level": "low",
                "detected_themes": ["general"],
                "method": "rule_based"
            }
            
            # Stream the response (simulate streaming for simple responses)
            words = aiContent.split()
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield format_sse("chunk", {"content": chunk})
                await asyncio.sleep(0.05)  
            # Save to database
            seqNum = len(contextMessages) + 1
            
            # Save user message
            await service.saveMessage(
                conversationId=conversation.id,
                userId=userId,
                role="user",
                content=request.message,
                sequenceNumber=seqNum,
                emotionData=emotionData,
                metadata={
                    "is_voice_input": request.isVoiceInput,
                    "voice_duration": request.voiceDuration,
                    "content_type": "voice" if request.isVoiceInput else "text"
                }
            )
            
            # Save assistant message
            await service.saveMessage(
                conversationId=conversation.id,
                userId=userId,
                role="assistant",
                content=aiContent,
                sequenceNumber=seqNum + 1,
                metadata=metadata
            )
            
            # Update emotion progression
            await service.updateEmotionProgression(
                conversationId=conversation.id,
                emotionState=emotionData['emotion_state'],
                energyLevel=emotionData['energy_level']
            )
            
            # Check suggestion
            suggestion = None
            if shouldSuggestActivity(emotionData, request.message):
                activity = getSuggestedActivity(emotionData)
                if activity:
                    suggestion = activity
                    suggestionMsg = generateSuggestionMessage(activity)
                    aiContent += f"\n\n{suggestionMsg}"
                    logger.info(f"💡 Suggested: {activity['activity_type']}")
            
            # Commit transaction
            await service.db.commit()
            
            # Send complete metadata matching ChatResponse schema
            from datetime import datetime
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
                    "content": aiContent,
                    "contentType": "text",
                    "sequenceNumber": seqNum + 1,
                    "createdAt": datetime.utcnow().isoformat() + "Z",
                    "modelUsed": metadata.get('model')
                },
                "contextUsed": contextUsed,
                "suggestion": suggestion
            }
            yield format_sse("metadata", metadata_response)
            yield format_sse("done", {})
            return
        
        # ============================================================
        # PHASE 2: Emotion Analysis (rule-based)
        # ============================================================
        
        logger.info("🔄 PHASE 2 (Streaming): Emotion analysis...")
        
        emotionData = await analyzeEmotionSimple(request.message)
        emotionState = emotionData.get("emotion_state", "neutral")
        
        # ============================================================
        # PHASE 2.5 + 3: PARALLEL Memory Search + AI Response (OPTIMIZED)
        # ============================================================
        
        logger.info("🔄 PHASE 3 (Streaming): AI response + Memory search (parallel)...")
        
        # Prepare system prompt
        systemPrompt = getSystemPrompt(
            userContext={"language": user.language},
            emotionState=emotionState
        )
        
        messages = formatMessagesForAI(contextMessages, systemPrompt)
        messages.append({
            "role": "user",
            "content": request.message
        })
        
        # ⚡ PARALLEL: Start memory search in background (don't await)
        # NOTE: Memory search is now part of saveChatTurn (Phase 4.5) which runs in background.
        
        # ⚡ PARALLEL: Stream AI response immediately (don't wait for memory)
        from app.core.config import settings
        full_content = ""
        async for chunk in openRouterService.chatStreaming(
            messages=messages,
            temperature=0.8,
            maxTokens=800,
            model=settings.OPENROUTER_CHAT_MODEL  # 🚀 Use fast chat model
        ):
            full_content += chunk
            yield format_sse("chunk", {"content": chunk})
        
        # ============================================================
        # PHASE 4: Background Save
        # ============================================================
        
        logger.info("🔄 PHASE 4 (Streaming): Scheduling background save...")
        
        # Prepare metadata
        metadata = {
            "model": settings.OPENROUTER_CHAT_MODEL,
            "promptTokens": 0,
            "completionTokens": 0,
            "responseTimeMs": 0
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
        
        # Rebuild context state
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
        # IMPORTANT: We pass copies of data or primitive types to avoid DetachedInstanceError
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
        from datetime import datetime
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


@router.post("/stream")
async def chatStream(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(getDbSession)
):
    """
    Stream chat response in real-time
    
    Returns:
        StreamingResponse with Server-Sent Events
    
    Events:
        - chunk: Text chunks as they arrive
        - metadata: Emotion and conversation info
        - done: Streaming complete
        - error: Error occurred
    """
    
    logger.info("================================================================================")
    logger.info("🚀 STREAMING CHAT REQUEST STARTED")
    logger.info(f"📍 User ID: {request.userId}")
    logger.info(f"💬 Message: {request.message}")
    logger.info("================================================================================")
    
    return StreamingResponse(
        streamChatResponse(request.userId, request, db, background_tasks),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
