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
        Lấy hoặc tạo user
        
        ⚠️ QUAN TRỌNG:
        - Trong production: userId từ Supabase Auth JWT token
        - User đã tồn tại trong auth.users (Supabase managed)
        - Function này chỉ tạo extended profile trong bảng 'users'
        
        Flow:
        1. Query user by id
        2. Nếu tồn tại → return
        3. Nếu không → create new (chỉ cho testing)
        """
        stmt = select(User).where(User.id == userId)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            # Tạo user mới (testing only)
            user = User(
                id=userId,
                display_name="User",
                language="vi",
                timezone="UTC"
            )
            self.db.add(user)
            await self.db.flush()
            logger.info(f"👤 Created user: {userId}")
        
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
            stmt = select(Conversation).where(
                Conversation.id == conversationId,
                Conversation.user_id == userId,
                Conversation.status == 'active'
            )
            result = await self.db.execute(stmt)
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                raise NotFoundException(f"Conversation {conversationId} not found")
            
            logger.info(f"📂 Loaded conversation: {conversation.id}")
            return conversation
        
        # Tạo mới
        conversation = Conversation(
            user_id=userId,
            title="New Chat",
            status='active',
            emotion_progression=[]  # Initialize empty array
        )
        self.db.add(conversation)
        await self.db.flush()  # Get ID without committing
        
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
            sequence_number=sequenceNumber,
            content_type='text'
        )
        
        # Add emotion data (cho user messages)
        if emotionData:
            message.emotion_state = emotionData.get("emotion_state")
            message.energy_level = emotionData.get("energy_level")
            message.urgency_level = emotionData.get("urgency_level")
            message.detected_themes = emotionData.get("detected_themes", [])
        
        # Add AI metadata (cho assistant messages)
        if metadata:
            message.model_used = metadata.get("model_used")
            message.prompt_tokens = metadata.get("prompt_tokens")
            message.completion_tokens = metadata.get("completion_tokens")
            message.response_time_ms = metadata.get("response_time_ms")
        
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
        🎯 MAIN CHAT FUNCTION - Core logic của Module 1
        With detailed timing logs
        🎯 MAIN CHAT FUNCTION - Core logic của Module 1
            
            Args:
                userId: User ID (từ auth token)
                request: ChatRequest schema
            
            Returns:
                ChatResponse với full data
            
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
        
        overall_start = time.time()
        
        logger.info("=" * 70)
        logger.info(f"🚀 CHAT REQUEST START")
        logger.info(f"   User: {userId}")
        logger.info(f"   Message: {request.message[:50]}...")
        logger.info("=" * 70)
        
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
        
        # 4. 🎭 ANALYZE EMOTION
        step_start = time.time()
        emotionData = await analyzeEmotion(request.message)
        emotion_time = (time.time() - step_start) * 1000
        
        emotionState = emotionData.get("emotion_state", "neutral")
        energyLevel = emotionData.get("energy_level", 5)
        
        logger.info(f"⏱️  Step 4 (Emotion analysis): {emotion_time:.0f}ms")
        logger.info(
            f"💭 Emotion detected: {emotionState}, "
            f"energy={energyLevel}, "
            f"urgency={emotionData.get('urgency_level', 'low')}"
        )
        
        # 5. 💬 Save user message (với emotion data)
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
        step_time = (time.time() - step_start) * 1000
        logger.info(f"⏱️  Step 5 (Save user message): {step_time:.0f}ms")
        
        # 6. 📊 Update emotion progression
        step_start = time.time()
        await self.updateEmotionProgression(
            conversation.id,
            emotionState,
            energyLevel
        )
        step_time = (time.time() - step_start) * 1000
        logger.info(f"⏱️  Step 6 (Update emotion progression): {step_time:.0f}ms")
        
        # 7. 🤖 Generate AI response (tone adjusted)
        step_start = time.time()
        userContext = {"language": user.language}
        aiContent, metadata = await self.generateAIResponse(
            userMessage=request.message,
            contextMessages=contextMessages,
            userContext=userContext,
            emotionState=emotionState
        )
        ai_time = (time.time() - step_start) * 1000
        logger.info(f"⏱️  Step 7 (AI response generation): {ai_time:.0f}ms")
        logger.info(f"   Model: {metadata['model_used']}, Tokens: {metadata['completion_tokens']}")
        
        # 8. 💡 SUGGEST ACTIVITY (nếu cần)
        step_start = time.time()
        suggestion = None
        if shouldSuggestActivity(emotionData, request.message):
            activity = getSuggestedActivity(emotionData)
            if activity:
                suggestion = activity
                suggestionMsg = generateSuggestionMessage(activity)
                aiContent += f"\n\n{suggestionMsg}"
                logger.info(f"💡 Suggested activity: {activity['activity_type']}")
        step_time = (time.time() - step_start) * 1000
        logger.info(f"⏱️  Step 8 (Suggestion check): {step_time:.0f}ms")
        
        # 9. 💾 Save assistant message
        step_start = time.time()
        assistantMessage = await self.saveMessage(
            conversationId=conversation.id,
            userId=userId,
            role="assistant",
            content=aiContent,
            sequenceNumber=seqNum + 1,
            metadata=metadata
        )
        step_time = (time.time() - step_start) * 1000
        logger.info(f"⏱️  Step 9 (Save assistant message): {step_time:.0f}ms")
        
        # 10. ✅ Commit transaction
        step_start = time.time()
        await self.db.commit()
        step_time = (time.time() - step_start) * 1000
        logger.info(f"⏱️  Step 10 (Database commit): {step_time:.0f}ms")
        
        # SUMMARY
        total_time = (time.time() - overall_start) * 1000
        other_time = total_time - emotion_time - ai_time
        
        logger.info("=" * 70)
        logger.info(f"✅ CHAT REQUEST COMPLETE")
        logger.info(f"⏱️  TOTAL TIME: {total_time:.0f}ms ({total_time/1000:.2f}s)")
        logger.info(f"📊 TIME BREAKDOWN:")
        logger.info(f"   - Emotion Analysis:  {emotion_time:>6.0f}ms ({emotion_time/total_time*100:>5.1f}%)")
        logger.info(f"   - AI Response:       {ai_time:>6.0f}ms ({ai_time/total_time*100:>5.1f}%)")
        logger.info(f"   - Other (DB/Logic):  {other_time:>6.0f}ms ({other_time/total_time*100:>5.1f}%)")
        logger.info("=" * 70)
        
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


