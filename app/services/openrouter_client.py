"""
OpenRouter API Client - OPTIMIZED
Sử dụng OpenAI SDK để gọi OpenRouter API
"""
import time
import httpx
from typing import List, Dict
from openai import AsyncOpenAI
from app.core.config import settings
from app.utils.logger import logger
from app.utils.exceptions import OpenAIException


class OpenRouterService:
    def __init__(self):
        """
        Initialize OpenRouter service - OPTIMIZED
        - Persistent HTTP client (connection reuse)
        - Timeout config
        """
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL

        if not self.api_key:
            logger.warning("⚠️  OpenRouter API key not configured")
            self.client = None
        else:
            # ⚡ OPTIMIZATION: Persistent HTTP client with connection pooling
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://openrouter.ai/api/v1",
                timeout=httpx.Timeout(
                    connect=5.0,     # 5s to connect
                    read=30.0,       # 30s to read (streaming)
                    write=10.0,      # 10s to write
                    pool=5.0         # 5s to get connection from pool
                ),
                max_retries=1,       # 1 retry on transient errors
                http_client=httpx.AsyncClient(
                    limits=httpx.Limits(
                        max_connections=20,
                        max_keepalive_connections=10,
                        keepalive_expiry=60  # Keep connections alive 60s
                    )
                )
            )


    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        maxTokens: int = 1000,
        model: str = None
    ) -> Dict:

        if not self.client:
            raise OpenAIException("OpenRouter API key not configured")

        selected_model = model or self.model
        start_time = time.time()

        try:
            response = await self.client.chat.completions.create(
                model=selected_model,
                messages=messages,
                temperature=temperature,
                max_tokens=maxTokens,
                extra_headers={
                    "HTTP-Referer": "https://zenapp.com",
                    "X-Title": "Zen APP"
                }
            )

            response_time = int((time.time() - start_time) * 1000)

            content = response.choices[0].message.content
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0

            logger.info(
                f"✅ OpenRouter Complete: {response_time}ms, "
                f"{completion_tokens}tok, {len(content)}chars"
            )

            if response_time > 5000:
                logger.warning(f"⚠️  Slow response: {response_time}ms")

            return {
                "content": content,
                "model": selected_model,
                "promptTokens": prompt_tokens,
                "completionTokens": completion_tokens,
                "responseTimeMs": response_time
            }

        except Exception as e:
            logger.error(f"❌ OpenRouter Failed: {e}")
            self._handle_error(e)


    async def chatStreaming(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        maxTokens: int = 1000,
        model: str = None
    ):
        """
        Stream AI response - OPTIMIZED
        - Removed string concat tracking (O(n²) → O(1))
        - Better error handling
        """
        if not self.client:
            raise OpenAIException("OpenRouter API key not configured")

        selected_model = model or self.model
        start_time = time.time()

        try:
            response = await self.client.chat.completions.create(
                model=selected_model,
                messages=messages,
                temperature=temperature,
                max_tokens=maxTokens,
                stream=True
            )

            chunk_count = 0
            total_chars = 0

            async for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        chunk_count += 1
                        total_chars += len(delta.content)
                        yield delta.content

            response_time = int((time.time() - start_time) * 1000)
            logger.info(
                f"✅ Stream Complete: {response_time}ms, "
                f"{chunk_count} chunks, {total_chars} chars"
            )

        except Exception as e:
            logger.error(f"❌ Stream Failed: {e}")
            self._handle_error(e)


    def _handle_error(self, e: Exception):
        """Centralized error handling"""
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            raise OpenAIException("Invalid OpenRouter API key")
        elif "429" in error_msg or "Rate limit" in error_msg:
            raise OpenAIException("OpenRouter rate limit exceeded")
        elif "timeout" in error_msg.lower():
            raise OpenAIException("OpenRouter request timed out")
        else:
            raise OpenAIException(f"OpenRouter error: {error_msg}")


# Singleton
openRouterService = OpenRouterService()