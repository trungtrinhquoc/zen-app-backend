"""
Memory Service
Handles semantic memory storage and search using existing database schema
"""
from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.models.memory import SemanticMemory
from app.services.embedding_service import createEmbedding
from app.services.openrouter_client import openRouterService
from app.utils.logger import logger
from datetime import datetime


class MemoryService:
    """
    Service for managing semantic memories
    Works with existing semantic_memories table
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def saveSemanticMemory(
        self,
        userId: UUID,
        conversationId: Optional[UUID],
        content: str,
        memoryType: str = "conversation",
        emotionalContext: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
        importanceScore: float = 0.5
    ) -> SemanticMemory:
        """
        Save content to semantic memory with vector embedding
        
        Args:
            userId: User ID
            conversationId: Conversation ID (optional)
            content: Content to save (will be used for embedding)
            memoryType: Type of memory (conversation, insight, preference, trigger)
            emotionalContext: Dict with emotion and energy
            tags: List of tags
            importanceScore: 0-1, higher = more important
        
        Returns:
            SemanticMemory object
        """
        try:
            logger.info(f"💾 Saving semantic memory for user {userId}...")
            
            # 1. Create embedding from content
            embedding = await createEmbedding(content)
            logger.info(f"🧠 Embedding created: {len(embedding)} dimensions")
            
            # 2. Save to database
            memory = SemanticMemory(
                user_id=userId,
                conversation_id=conversationId,
                content=content,
                memory_type=memoryType,
                embedding=embedding,
                importance_score=importanceScore,
                emotional_context=emotionalContext or {},
                tags=tags or [],
                access_count=0
            )
            
            self.db.add(memory)
            await self.db.commit()
            await self.db.refresh(memory)
            
            logger.info(
                f"✅ Memory saved: {memory.id} "
                f"(type: {memoryType}, importance: {importanceScore})"
            )
            
            return memory
            
        except Exception as e:
            logger.error(f"❌ Failed to save memory: {e}")
            await self.db.rollback()
            raise
    
    async def searchSemanticMemories(
        self,
        userId: UUID,
        query: str,
        limit: int = 5,
        minImportance: float = 0.3,
        minSimilarity: float = 0.7
    ) -> List[Dict]:
        """
        Semantic search using vector similarity
        
        Args:
            userId: User ID
            query: Search query
            limit: Max results
            minImportance: Minimum importance score
            minSimilarity: Minimum similarity threshold
        
        Returns:
            List of relevant memories with similarity scores
        """
        try:
            # OPTIMIZATION: Check if user has any memories first
            # This avoids expensive embedding call if no memories exist
            count_result = await self.db.execute(
                select(SemanticMemory.id)
                .where(SemanticMemory.user_id == userId)
                .limit(1)
            )
            
            if not count_result.scalar_one_or_none():
                logger.info("🧠 No memories found for user (skipped embedding)")
                return []
            
            logger.info(f"🔍 Searching semantic memories for user {userId}...")
            
            # 1. Create query embedding
            queryEmbedding = await createEmbedding(query)
            
            # 2. Use cosine similarity search
            result = await self.db.execute(
                select(
                    SemanticMemory,
                    (1 - SemanticMemory.embedding.cosine_distance(queryEmbedding)).label('similarity')
                )
                .where(SemanticMemory.user_id == userId)
                .where(SemanticMemory.importance_score >= minImportance)
                .order_by(SemanticMemory.embedding.cosine_distance(queryEmbedding))
                .limit(limit * 2)
            )
            
            rows = result.all()
            
            # 3. Filter by similarity and format
            memories = []
            for memory, similarity in rows:
                if similarity >= minSimilarity:
                    # Update access tracking
                    memory.access_count += 1
                    memory.last_accessed_at = datetime.utcnow()
                    
                    memories.append({
                        "id": str(memory.id),
                        "content": memory.content,
                        "memory_type": memory.memory_type,
                        "emotional_context": memory.emotional_context,
                        "tags": memory.tags,
                        "importance": memory.importance_score,
                        "created_at": memory.created_at.isoformat(),
                        "similarity": round(similarity, 3)
                    })
                    
                    if len(memories) >= limit:
                        break
            
            await self.db.commit()
            
            logger.info(f"✅ Found {len(memories)} memories (similarity >= {minSimilarity})")
            
            return memories
            
        except Exception as e:
            logger.error(f"❌ Memory search failed: {e}")
            return []
    
    async def saveConversationSummary(
        self,
        userId: UUID,
        conversationId: UUID,
        messages: List[Dict],
        emotionState: str,
        themes: List[str]
    ) -> Optional[SemanticMemory]:
        """
        Save important conversation as semantic memory
        
        Args:
            userId: User ID
            conversationId: Conversation ID
            messages: List of recent messages
            emotionState: Primary emotion
            themes: Detected themes
        
        Returns:
            SemanticMemory or None
        """
        try:
            # 1. Create conversation summary
            conversationText = "\n".join([
                f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                for msg in messages[-5:]  # Last 5 messages
            ])
            
            # 2. Generate concise summary
            summary = await self._summarizeConversation(conversationText)
            
            # 3. Save as semantic memory
            memory = await self.saveSemanticMemory(
                userId=userId,
                conversationId=conversationId,
                content=summary,
                memoryType="conversation",
                emotionalContext={
                    "emotion": emotionState,
                    "themes": themes
                },
                tags=themes,
                importanceScore=self._calculateImportance(emotionState, themes)
            )
            
            return memory
            
        except Exception as e:
            logger.error(f"❌ Failed to save conversation summary: {e}")
            return None
    
    async def _summarizeConversation(self, content: str) -> str:
        """Generate concise summary from conversation"""
        try:
            truncated = content[:2000]
            
            prompt = f"""Tóm tắt cuộc trò chuyện sau trong 2-3 câu ngắn gọn.
QUAN TRỌNG: Giữ NGUYÊN các từ khóa cảm xúc của user (ví dụ: mệt, sợ hãi, stress, buồn, lo lắng).

Tập trung vào:
1. Cảm xúc chính của user (dùng CHÍNH XÁC từ khóa của user)
2. Vấn đề/chủ đề chính
3. Phản ứng/nhu cầu của user

Conversation:
{truncated}

Ví dụ tốt: "User cảm thấy mệt mỏi và sợ hãi về công việc. Từ chối breathing exercises, muốn nghỉ ngơi."
Ví dụ XẤU: "Cuộc trò chuyện thể hiện sự quan tâm và hỗ trợ..."

CHỈ trả về summary, KHÔNG giải thích."""
            
            result = await openRouterService.chat(
                messages=[
                    {"role": "system", "content": "You are a summarization assistant. Preserve user's exact emotional keywords."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                maxTokens=150
            )
            
            summary = result["content"].strip()
            return summary[:400] if len(summary) > 400 else summary
            
        except Exception as e:
            logger.error(f"❌ Summarization failed: {e}")
            return content[:200] + "..."
    
    def _calculateImportance(self, emotionState: str, themes: List[str]) -> float:
        """Calculate importance score based on emotion and themes"""
        score = 0.5  # Base
        
        # Strong emotions = higher importance
        if emotionState in ["anxious", "sad", "angry", "overwhelmed"]:
            score += 0.2
        elif emotionState in ["stressed", "frustrated"]:
            score += 0.1
        
        # Multiple themes = higher importance
        if len(themes) >= 2:
            score += 0.1
        
        return min(1.0, score)
