"""
OpenRouter Client Service
Gọi AI models qua OpenRouter API
"""
from openai import AsyncOpenAI
from typing import List, Dict, Any, Optional
import time

from app.core.config import settings
from app.utils.logger import logger
from app.utils.exceptions import OpenAIException


class OpenRouterService:
    """
    OpenRouter service
    """
    
    def __init__(self):
        """
        Initialize OpenRouter client
        """
        self.client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
        self.model = settings.OPENROUTER_MODEL
        self.requestCount = 0
        
        logger.info(f"✅ OpenRouter initialized: {self.model}")
    
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        maxTokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Gọi AI chat completion
        
        Args:
            messages: [
                {"role": "system", "content": "You are..."},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ]
            temperature: 0.0-2.0
                - 0.0-0.3: Deterministic, factual
                - 0.7-0.9: Balanced (best cho chat)
                - 1.5-2.0: Creative, varied
            maxTokens: Max length của response
        
        Returns:
            {
                "content": "AI response text",
                "promptTokens": 100,
                "completionTokens": 50,
                "totalTokens": 150,
                "model": "openai/gpt-4o-mini",
                "responseTimeMs": 1234
            }
        """
        startTime = time.time()
        self.requestCount += 1
        
        try:
            logger.info(
                f"🤖 OpenRouter call #{self.requestCount}: "
                f"{len(messages)} messages, model={self.model}"
            )
            
            # Call API
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=maxTokens or 1000,
                extra_headers={
                    "HTTP-Referer": "https://zen-app.com",
                    "X-Title": "Zen APP"
                }
            )
            
            # Calculate response time
            responseTimeMs = int((time.time() - startTime) * 1000)
            
            # Parse result
            result = {
                "content": response.choices[0].message.content,
                "promptTokens": response.usage.prompt_tokens if response.usage else 0,
                "completionTokens": response.usage.completion_tokens if response.usage else 0,
                "totalTokens": response.usage.total_tokens if response.usage else 0,
                "model": response.model,
                "responseTimeMs": responseTimeMs
            }
            
            logger.info(
                f"✅ Response: {result['totalTokens']} tokens, "
                f"{responseTimeMs}ms"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"❌ OpenRouter error: {e}")
            raise OpenAIException(f"OpenRouter failed: {str(e)}")


# Singleton instance
openRouterService = OpenRouterService()

"""
Giải thích Singleton:
- Chỉ tạo 1 instance duy nhất
- Chia sẻ giữa tất cả requests
- Tránh tạo connection mới liên tục
"""