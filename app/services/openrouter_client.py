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
        maxTokens: int = 1000
    ) -> Dict:
        """
        Call OpenRouter API via OpenAI-compatible SDK
        """
        try:
            start_time = time.time()
            self.requestCount += 1

            logger.info("🤖 OpenRouter API call starting...")
            logger.info(f"   Messages: {len(messages)}, Model: {self.model}, Max tokens: {maxTokens}")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=maxTokens,
            )

            end_time = time.time()
            response_time = int((end_time - start_time) * 1000)

            content = response.choices[0].message.content
            promptTokens = response.usage.prompt_tokens
            completionTokens = response.usage.completion_tokens

            logger.info("✅ OpenRouter API response received")
            logger.info(f"   Time: {response_time}ms")
            logger.info(f"   Tokens: {completionTokens} completion, {promptTokens} prompt")

            return {
                "content": content,
                "model": self.model,
                "promptTokens": promptTokens,
                "completionTokens": completionTokens,
                "responseTimeMs": response_time
            }

        except Exception as e:
            logger.error(f"❌ OpenRouter error: {str(e)}")
            raise OpenAIException(f"OpenRouter request failed: {str(e)}")


# Singleton instance
openRouterService = OpenRouterService()

"""
Giải thích Singleton:
- Chỉ tạo 1 instance duy nhất
- Chia sẻ giữa tất cả requests
- Tránh tạo connection mới liên tục
"""