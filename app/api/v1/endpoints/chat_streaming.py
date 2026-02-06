"""
Streaming Chat Endpoint
Handles real-time streaming responses using Server-Sent Events (SSE)
"""

from fastapi import APIRouter, Depends, HTTPException
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
    ConversationContext  # NEW: For smart suggestions
)
from app.services.openrouter_client import openRouterService
from app.modules.conversation.prompts import getSystemPrompt, formatMessagesForAI
from app.utils.logger import logger
from app.models import Conversation
from datetime import datetime

router = APIRouter()

def format_sse(event: str, data: dict) -> str:
    """Format SSE event with single-line JSON for proper parsing"""
    json_str = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {json_str}\n\n"

async def streamChatResponse(
    userId: UUID,
    request: ChatRequest,
    db: AsyncSession
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
        
        step_start = time.time()
        user = await service.getOrCreateUser(userId)
        step_time = (time.time() - step_start) * 1000
        logger.info(f"⏱️  Step 1 (Get user): {step_time:.0f}ms")
        
        step_start = time.time()
        conversation = await service.getOrCreateConversation(
            userId=userId,
            conversationId=request.conversationId
        )
        step_time = (time.time() - step_start) * 1000
        logger.info(f"⏱️  Step 2 (Get/Create conversation): {step_time:.0f}ms")
        
        step_start = time.time()
        contextMessages = await service.getConversationContext(conversation.id)
        contextUsed = len(contextMessages)
        step_time = (time.time() - step_start) * 1000
        logger.info(f"⏱️  Step 3 (Load context): {step_time:.0f}ms (messages: {contextUsed})")
        
        phase1_elapsed = (time.time() - phase1_start) * 1000
        logger.info(f"✅ Phase 1 Complete: {phase1_elapsed:.0f}ms")
        
        # ============================================================
        # FAST PATH: Simple patterns
        # ============================================================
        
        if isSimplePattern(request.message):
            logger.info("⚡ FAST PATH (Streaming): Simple pattern")
            
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
                emotionData=emotionData
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
        # PHASE 3: Stream AI Response
        # ============================================================
        
        logger.info("🔄 PHASE 3 (Streaming): AI response...")
        
        systemPrompt = getSystemPrompt(
            userContext={"language": user.language},
            emotionState=emotionState
        )
        
        messages = formatMessagesForAI(contextMessages, systemPrompt)
        messages.append({
            "role": "user",
            "content": request.message
        })
        
        # Stream chunks
        full_content = ""
        async for chunk in openRouterService.chatStreaming(
            messages=messages,
            temperature=0.8,
            maxTokens=800
        ):
            full_content += chunk
            yield format_sse("chunk", {"content": chunk})
        # ============================================================
        # PHASE 4: Save to Database
        # ============================================================
        
        logger.info("🔄 PHASE 4 (Streaming): Saving to DB...")
        
        metadata = {
            "model": "openai/gpt-4o-mini",
            "promptTokens": 0,
            "completionTokens": 0,
            "responseTimeMs": 0
        }
        
        seqNum = len(contextMessages) + 1
        
        # Get last assistant message for suggestion logic
        lastAssistantMsg = ""
        for msg in reversed(contextMessages):
            if msg.role == "assistant":  # Direct attribute access for SQLAlchemy object
                lastAssistantMsg = msg.content
                break
        
        # Create conversation context for smart suggestions
        context = ConversationContext(
            turn_count=seqNum,
            last_assistant_message=lastAssistantMsg
        )
        
        # Rebuild context state: check if we already suggested in this conversation
        # by looking for suggestion metadata in previous assistant messages
        for msg in contextMessages:
            if msg.role == "assistant" and msg.metadata:
                # Check if this message had a suggestion
                if isinstance(msg.metadata, dict) and msg.metadata.get("suggestion"):
                    context.has_suggested_in_session = True
                    suggested_type = msg.metadata["suggestion"].get("activity_type")
                    if suggested_type:
                        context.suggested_activities.append(suggested_type)
        
        logger.info(f"📊 Context: turn={seqNum}, has_suggested={context.has_suggested_in_session}, suggested={context.suggested_activities}")
        
        # Check suggestion BEFORE saving
        suggestion = None
        if shouldSuggestActivity(
            emotionData, 
            request.message,
            conversationTurnCount=seqNum,
            lastAssistantMessage=lastAssistantMsg,
            context=context  # Pass context to check if already suggested
        ):
            activity = getSuggestedActivity(
                emotionData, 
                userMessage=request.message,
                userLanguage=user.language or "vi",
                context=context  # Pass context for smart matching
            )
            if activity:
                suggestion = activity
                suggestionMsg = generateSuggestionMessage(activity)
                full_content += f"\n\n{suggestionMsg}"
                logger.info(f"💡 Suggested: {activity['activity_type']}")
        
        
        
        # Save user message
        await service.saveMessage(
            conversationId=conversation.id,
            userId=userId,
            role="user",
            content=request.message,
            sequenceNumber=seqNum,
            emotionData=emotionData
        )
        
        # Save assistant message (with suggestion if any)
        await service.saveMessage(
            conversationId=conversation.id,
            userId=userId,
            role="assistant",
            content=full_content,
            sequenceNumber=seqNum + 1,
            metadata=metadata
        )
        
        # Update emotion progression
        await service.updateEmotionProgression(
            conversationId=conversation.id,
            emotionState=emotionData['emotion_state'],
            energyLevel=emotionData['energy_level']
        )
        
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
                "id": str(uuid4()),  # Generate temp ID for display
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
        streamChatResponse(request.userId, request, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
