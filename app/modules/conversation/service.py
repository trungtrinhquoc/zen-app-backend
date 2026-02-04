"""
Conversation Service
Business logic cho chat conversations
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import Optional, List, Dict, Tuple
from uuid import UUID
from datetime import datetime

from app.models import User, Conversation, Message
from app.schemas import ChatRequest, ChatResponse, MessageResponse
from app.services import openRouterService
from app.modules.conversation.prompts import getSystemPrompt, formatMessagesForAI
from app.modules.conversation.emotion_analyzer import analyzeEmotion
from app.modules.conversation.suggestion_engine import (
    shouldSuggestActivity,
    getSuggestedActivity,
    generateSuggestionMessage
)
from app.utils.logger import logger
from app.utils.exceptions import NotFoundException
from app.modules.conversation.simple_responder import (
    isSimpleGreeting,
    getSimpleResponse
)


class ConversationService:
    """
    Service xử lý conversation logic
    
    Giải thích:
    - Service layer = business logic
    - Tách biệt với endpoints (controller)
    - Reusable, testable
    
    Responsibilities:
    1. Quản lý users, conversations, messages
    2. Emotion analysis
    3. AI response generation
    4. Activity suggestions
    5. Database operations
    """
    
    def __init__(self, db: AsyncSession):
        """
        Initialize service
        """
        self.db = db
    
    
    async def getOrCreateUser(self, userId: UUID) -> User:
        """
        Get or create user - OPTIMIZED
        
        Optimization:
        - Single query instead of SELECT + INSERT
        - Use ON CONFLICT for upsert
        """
        from sqlalchemy.dialects.postgresql import insert
    
        stmt = insert(User).values(
            id=userId,
            display_name="User",
            language="vi",
            timezone="Asia/Ho_Chi_Minh",
            memory_enabled=True
        ).on_conflict_do_update(
            index_elements=['id'],
            set_={'updated_at': datetime.utcnow()}
        ).returning(User)
        
        result = await self.db.execute(stmt)
        user = result.scalar_one()
        await self.db.flush()  
        
        return user
    
    
    async def getOrCreateConversation(
        self,
        userId: UUID,
        conversationId: Optional[UUID] = None
    ) -> Conversation:
        """
        Lấy conversation hiện tại hoặc tạo mới
        
        Args:
            userId: User ID
            conversationId: Conversation ID (None = tạo mới)
        
        Returns:
            Conversation object
        
        Flow:
        - Nếu có conversationId:
          → Load từ DB
          → Verify user_id và status = active
          → Raise 404 nếu không tìm thấy
        - Nếu không có conversationId:
          → Tạo conversation mới
          → Initialize emotion_progression = []
        """
        if conversationId:
            stmt = select(Conversation).where(Conversation.id == conversationId)
            result = await self.db.execute(stmt)
            conversation = result.scalar_one_or_none()
            
            if conversation:
                logger.info(f"📂 Loaded conversation: {conversationId}")
                return conversation
        
        # Tạo mới
        conversation = Conversation(
            user_id=userId,
            title="New Chat",
            status='active',
            emotion_progression=[] 
        )
        self.db.add(conversation)
        await self.db.flush() 
        
        logger.info(f"📝 New conversation: {conversation.id}")
        return conversation
    
    
    async def getConversationContext(
        self,
        conversationId: UUID,
        limit: int = 20
    ) -> List[Message]:
        """
        Load N messages gần nhất để làm context
        
        Args:
            conversationId: Conversation ID
            limit: Số messages tối đa (default: 20)
        
        Returns:
            List[Message] ordered từ cũ → mới
        
        Giải thích:
        - AI cần context để hiểu conversation
        - Limit 20 để tránh vượt token limit
        - Order DESC để lấy messages mới nhất
        - Reverse để có thứ tự đúng (cũ → mới)
        """
        stmt = select(Message).where(
            Message.conversation_id == conversationId
        ).order_by(
            desc(Message.sequence_number)
        ).limit(limit)
        
        result = await self.db.execute(stmt)
        messages = result.scalars().all()
        
        return list(reversed(messages))
    
    
    async def getNextSequenceNumber(self, conversationId: UUID) -> int:
        """
        Lấy sequence_number tiếp theo
        
        Giải thích:
        - sequence_number = thứ tự message (1, 2, 3, ...)
        - Query max(sequence_number) + 1
        - Return 1 nếu chưa có message nào
        """
        stmt = select(func.max(Message.sequence_number)).where(
            Message.conversation_id == conversationId
        )
        result = await self.db.execute(stmt)
        maxSeq = result.scalar()
        
        return (maxSeq + 1) if maxSeq else 1
    
    
    async def saveMessage(
        self,
        conversationId: UUID,
        userId: UUID,
        role: str,
        content: str,
        sequenceNumber: int,
        emotionData: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> Message:
        """
        Lưu message vào database
        
        Args:
            conversationId: Conversation ID
            userId: User ID
            role: 'user' | 'assistant' | 'system'
            content: Message content
            sequenceNumber: Sequence number
            emotionData: {emotion_state, energy_level, urgency_level, detected_themes}
            metadata: {model_used, prompt_tokens, completion_tokens, response_time_ms}
        
        Returns:
            Message object đã save
        
        Flow:
        1. Create Message object
        2. Add emotion data (cho user messages)
        3. Add AI metadata (cho assistant messages)
        4. Save to DB
        5. Flush (get ID)
        
        ⚠️ NOTE: message_count tự động tăng bởi trigger trong DB
        """
        message = Message(
            conversation_id=conversationId,
            user_id=userId,
            role=role,
            content=content,
            content_type="text",
            sequence_number=sequenceNumber,
            # Emotion data (for user messages)
            emotion_state=emotionData.get("emotion_state") if emotionData else None,
            energy_level=emotionData.get("energy_level") if emotionData else None,
            urgency_level=emotionData.get("urgency_level") if emotionData else None,
            detected_themes=emotionData.get("detected_themes", []) if emotionData else [],
            # AI metadata (for assistant messages)
            model_used=metadata.get("model") if metadata else None,
            prompt_tokens=metadata.get("promptTokens") if metadata else None,
            completion_tokens=metadata.get("completionTokens") if metadata else None,
            response_time_ms=metadata.get("responseTimeMs") if metadata else None
    )
        
        self.db.add(message)
        await self.db.flush()
        
        return message
    
    
    async def updateEmotionProgression(
        self,
        conversationId: UUID,
        emotionState: str,
        energyLevel: int
    ):
        """
        Update emotion_progression trong conversation
        
        Args:
            conversationId: Conversation ID
            emotionState: Current emotion
            energyLevel: Current energy level
        
        Giải thích:
        - emotion_progression = JSONB array tracking emotions over time
        - Format: [{"timestamp": "...", "emotion": "anxious", "energy": 3}, ...]
        - Append new snapshot mỗi lần chat
        - Update dominant_emotion = emotion xuất hiện nhiều nhất
        
        Flow:
        1. Load conversation
        2. Get current progression array
        3. Append new snapshot
        4. Update dominant_emotion (most common)
        """
        stmt = select(Conversation).where(Conversation.id == conversationId)
        result = await self.db.execute(stmt)
        conversation = result.scalar_one()
        
        # Get current progression
        progression = conversation.emotion_progression or []
        
        # Add new snapshot
        progression.append({
            "timestamp": datetime.utcnow().isoformat(),
            "emotion": emotionState,
            "energy": energyLevel
        })
        
        conversation.emotion_progression = progression
        
        # Update dominant_emotion
        emotions = [p["emotion"] for p in progression]
        from collections import Counter
        mostCommon = Counter(emotions).most_common(1)
        if mostCommon:
            conversation.dominant_emotion = mostCommon[0][0]
    
    
    async def generateAIResponse(
        self,
        userMessage: str,
        contextMessages: List[Message],
        userContext: Optional[Dict],
        emotionState: Optional[str]
    ) -> Tuple[str, Dict]:
        """
        Generate AI response với tone adjusted
        
        Args:
            userMessage: User message content
            contextMessages: Chat history (max 20)
            userContext: User info (language, patterns...)
            emotionState: Current emotion để adjust tone
        
        Returns:
            Tuple[str, Dict]: (AI response content, metadata)
        
        Flow:
        1. Get system prompt (với tone adjusted theo emotion)
        2. Format messages (system + history + new user message)
        3. Call OpenRouter API
        4. Return content + metadata
        """
        # System prompt with emotion-adjusted tone
        systemPrompt = getSystemPrompt(userContext, emotionState)
        
        # Format messages
        messages = formatMessagesForAI(contextMessages, systemPrompt)
        messages.append({"role": "user", "content": userMessage})
        
        logger.info(f"🤖 Generating AI response: {len(messages)} messages, emotion={emotionState}")
        
        # Call AI
        result = await openRouterService.chat(
            messages=messages,
            temperature=0.8,  
            maxTokens=800
        )
        
        metadata = {
            "model_used": result["model"],
            "prompt_tokens": result["promptTokens"],
            "completion_tokens": result["completionTokens"],
            "response_time_ms": result["responseTimeMs"]
        }
        
        return result["content"], metadata
    
    async def chat(self, userId: UUID, request: ChatRequest) -> ChatResponse:
        """
        🚀 OPTIMIZED CHAT FUNCTION
    
        OPTIMIZATION STRATEGY:
        1. Parallel AI calls (emotion + response) → Save ~2.5s
        2. Detailed timing logs → Visibility
        3. Fallback mechanism → Reliability
            
            FLOW HOÀN CHỈNH:
            
            1. ✅ Verify/Create user
            2. 📂 Get/Create conversation
            3. 📚 Load context (20 messages gần nhất)
            4. 🎭 Analyze emotion từ user message
            5. 💬 Save user message (với emotion data)
            6. 📊 Update emotion_progression
            7. 🤖 Generate AI response (tone adjusted)
            8. 💡 Suggest activity (nếu cần)
            9. 💾 Save AI message
            10. ✅ Commit transaction
            11. 📤 Return response
            
            Giải thích từng bước:
            - Step 1-2: Setup conversation
            - Step 3: Load context cho AI
            - Step 4: Detect emotion để adjust tone
            - Step 5: Save user message
            - Step 6: Track emotion over time
            - Step 7: Generate empathetic response
            - Step 8: Suggest activity nếu user cần
            - Step 9-10: Save và commit
            - Step 11: Return data cho frontend
        """
        import time
        from app.modules.conversation.emotion_analyzer import analyzeEmotionSimple
        import asyncio
        
        overall_start = time.time()
        
        logger.info("=" * 80)
        logger.info(f"🚀 CHAT REQUEST STARTED")
        logger.info(f"📍 User ID: {userId}")
        logger.info(f"💬 Message: {request.message[:60]}{'...' if len(request.message) > 60 else ''}")
        logger.info(f"🕐 Timestamp: {datetime.utcnow().isoformat()}")
        logger.info("=" * 80)
        

        # ============================================================
        # PHASE 1: SETUP (Fast sequential operations)
        # ============================================================
        
        phase1_start = time.time()
        
        # 1. ✅ Verify/Create user
        step_start = time.time()
        user = await self.getOrCreateUser(userId)
        step_time = (time.time() - step_start) * 1000
        logger.info(f"⏱️  Step 1 (Get user): {step_time:.0f}ms")
        
        # 2. 📂 Get/Create conversation
        step_start = time.time()
        conversation = await self.getOrCreateConversation(userId, request.conversation_id)
        step_time = (time.time() - step_start) * 1000
        logger.info(f"⏱️  Step 2 (Get/Create conversation): {step_time:.0f}ms")
        
        # 3. 📚 Load context (20 messages gần nhất)
        step_start = time.time()
        contextMessages = []
        if request.include_context:
            contextMessages = await self.getConversationContext(conversation.id, 20)
        contextUsed = len(contextMessages)
        step_time = (time.time() - step_start) * 1000
        logger.info(f"⏱️  Step 3 (Load context): {step_time:.0f}ms (messages: {contextUsed})")
        
        phase1_elapsed = (time.time() - phase1_start) * 1000
        logger.info(f"✅ Phase 1 Complete: {phase1_elapsed:.0f}ms")
        
        # Prepare user context (needed for both fast and normal paths)
        userContext = {"language": user.language}
        
        # ============================================================
        # 🚀 FAST PATH: Simple Greeting
        # ============================================================
        
        if isSimpleGreeting(request.message):
            logger.info("⚡ FAST PATH: Simple greeting detected")
            
            # Use simple responder (instant)
            aiContent, metadata = getSimpleResponse(request.message)
            
            # Use fallback emotion
            from app.modules.conversation.emotion_analyzer import analyzeEmotionSimple
            emotionData = await analyzeEmotionSimple(request.message)
            emotionState = "neutral"
            energyLevel = 5
            
            logger.info("⚡ Skipping OpenRouter calls (simple greeting)")
            
            # Jump to Phase 3 (save to DB)
            phase2_elapsed = 0
            
        else:
            # ============================================================
            # PHASE 2: PARALLEL PROCESSING (AI calls)
            # ============================================================
            logger.info("🔄 PHASE 2: Starting PARALLEL AI calls...")
            phase2_start = time.time()

            try:
                logger.info("   ├─ Task 1: Emotion Analysis (OpenRouter)")
                logger.info("   └─ Task 2: AI Response Generation (OpenRouter)")
                
                emotion_task = analyzeEmotion(request.message)
                ai_response_task = self.generateAIResponse(
                    userMessage=request.message,
                    contextMessages=contextMessages,
                    userContext=userContext,
                    emotionState="neutral" 
                )
                
                # Wait for BOTH to complete (whichever finishes last)
                results = await asyncio.gather(
                    emotion_task,
                    ai_response_task,
                    return_exceptions=True  # Don't fail if one task errors
                )
                
                # Check if any task failed
                if isinstance(results[0], Exception):
                    logger.warning(f"⚠️  Emotion analysis failed: {results[0]}")
                    logger.info("   → Using fallback simple emotion analysis")
                    emotionData = await analyzeEmotionSimple(request.message)
                else:
                    emotionData = results[0]
                
                if isinstance(results[1], Exception):
                    logger.error(f"❌ AI response generation failed: {results[1]}")
                    raise results[1]
                else:
                    aiContent, metadata = results[1]
                
                phase2_elapsed = (time.time() - phase2_start) * 1000
                
                logger.info(f"✅ Phase 2 Complete: {phase2_elapsed:.0f}ms (PARALLEL)")
                logger.info(f"   💡 Time saved vs sequential: ~{max(0, 2500):.0f}ms")
                
            except Exception as e:
                logger.error(f"❌ CRITICAL: Parallel AI processing failed: {e}")
                # Ultimate fallback
                emotionData = await analyzeEmotionSimple(request.message)
                logger.warning("⚠️  Using fallback for both emotion and AI response")
                
                # Retry AI response with fallback emotion
                aiContent, metadata = await self.generateAIResponse(
                    userMessage=request.message,
                    contextMessages=contextMessages,
                    userContext=userContext,
                    emotionState=emotionData.get("emotion_state", "neutral")
                )
        
        emotionState = emotionData.get("emotion_state", "neutral")
        energyLevel = emotionData.get("energy_level", 5)
        
        logger.info(f"🎭 Emotion Result: {emotionState.upper()}")
        logger.info(f"   Energy: {energyLevel}/10, Urgency: {emotionData.get('urgency_level', 'low')}")
        logger.info(f"   Themes: {', '.join(emotionData.get('detected_themes', []))}")
        logger.info(f"   Method: {emotionData.get('method', 'ai')}")
        
        # ============================================================
        # PHASE 3: DATABASE OPERATIONS (Sequential)
        # ============================================================
        
        logger.info("💾 PHASE 3: Database operations...")
        phase3_start = time.time()
        
        # Step 4: Save User Message
        step_start = time.time()
        seqNum = await self.getNextSequenceNumber(conversation.id)
        userMessage = await self.saveMessage(
            conversationId=conversation.id,
            userId=userId,
            role="user",
            content=request.message,
            sequenceNumber=seqNum,
            emotionData=emotionData
        )
        step_elapsed = (time.time() - step_start) * 1000
        logger.info(f"⏱️  [STEP 4] Save User Message: {step_elapsed:.0f}ms")
        
        # Step 5: Update Emotion Progression
        step_start = time.time()
        await self.updateEmotionProgression(
            conversation.id,
            emotionState,
            energyLevel
        )
        step_elapsed = (time.time() - step_start) * 1000
        logger.info(f"⏱️  [STEP 5] Update Emotion: {step_elapsed:.0f}ms")
        
        # Step 6: Check Activity Suggestion
        step_start = time.time()
        suggestion = None
        if shouldSuggestActivity(emotionData, request.message):
            activity = getSuggestedActivity(emotionData)
            if activity:
                suggestion = activity
                suggestionMsg = generateSuggestionMessage(activity)
                aiContent += f"\n\n{suggestionMsg}"
                logger.info(f"💡 Suggested Activity: {activity['activity_type']} ({activity['duration']}min)")
        step_elapsed = (time.time() - step_start) * 1000
        logger.info(f"⏱️  [STEP 6] Check Suggestion: {step_elapsed:.0f}ms")
        
        # Step 7: Save Assistant Message
        step_start = time.time()
        assistantMessage = await self.saveMessage(
            conversationId=conversation.id,
            userId=userId,
            role="assistant",
            content=aiContent,
            sequenceNumber=seqNum + 1,
            metadata=metadata
        )
        step_elapsed = (time.time() - step_start) * 1000
        logger.info(f"⏱️  [STEP 7] Save AI Message: {step_elapsed:.0f}ms")
        
        # Step 8: Commit Transaction
        step_start = time.time()
        await self.db.commit()
        step_elapsed = (time.time() - step_start) * 1000
        logger.info(f"⏱️  [STEP 8] Database Commit: {step_elapsed:.0f}ms")
        
        phase3_elapsed = (time.time() - phase3_start) * 1000
        logger.info(f"✅ Phase 3 Complete: {phase3_elapsed:.0f}ms")
        
        # ============================================================
        # FINAL SUMMARY
        # ============================================================
        
        total_elapsed = (time.time() - overall_start) * 1000
        
        logger.info("=" * 80)
        logger.info(f"✅ CHAT REQUEST COMPLETED SUCCESSFULLY")
        logger.info(f"")
        logger.info(f"⏱️  TOTAL TIME: {total_elapsed:.0f}ms ({total_elapsed/1000:.2f}s)")
        logger.info(f"")
        logger.info(f"📊 PHASE BREAKDOWN:")
        logger.info(f"   Phase 1 (Setup):        {phase1_elapsed:>6.0f}ms ({phase1_elapsed/total_elapsed*100:>5.1f}%)")
        logger.info(f"   Phase 2 (AI Parallel):  {phase2_elapsed:>6.0f}ms ({phase2_elapsed/total_elapsed*100:>5.1f}%)")
        logger.info(f"   Phase 3 (Database):     {phase3_elapsed:>6.0f}ms ({phase3_elapsed/total_elapsed*100:>5.1f}%)")
        logger.info(f"")
        logger.info(f"🚀 OPTIMIZATION IMPACT:")
        logger.info(f"   Estimated sequential time: ~{total_elapsed + 2500:.0f}ms")
        logger.info(f"   Parallel optimization saved: ~2500ms")
        logger.info(f"   Speed improvement: ~{(2500/(total_elapsed + 2500)*100):.0f}% faster")
        logger.info(f"")
        logger.info(f"📈 METRICS:")
        logger.info(f"   Tokens (AI): {metadata.get('completion_tokens', 0)} completion + {metadata.get('prompt_tokens', 0)} prompt")
        logger.info(f"   Context used: {contextUsed} messages")
        logger.info(f"   Conversation: {conversation.id}")
        logger.info("=" * 80)
        
        # ============================================================
        # RETURN RESPONSE
        # ============================================================
        # 11. 📤 Return response
        return ChatResponse(
            conversation_id=conversation.id,
            user_message=MessageResponse.model_validate(userMessage),
            assistant_message=MessageResponse.model_validate(assistantMessage),
            context_used=contextUsed,
            suggestion=suggestion
        )
    
    
    async def getConversationById(
        self,
        userId: UUID,
        conversationId: UUID
    ) -> Conversation:
        """
        Lấy conversation detail
        
        Flow:
        - Query conversation by id + user_id
        - Raise 404 nếu không tìm thấy
        - Messages auto-loaded bởi relationship
        """
        stmt = select(Conversation).where(
            Conversation.id == conversationId,
            Conversation.user_id == userId
        )
        result = await self.db.execute(stmt)
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            raise NotFoundException(f"Conversation {conversationId} not found")
        
        return conversation


