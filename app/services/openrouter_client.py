"""
OpenRouter API Client
Sử dụng OpenAI SDK để gọi OpenRouter API
"""
from typing import List, Dict
from openai import AsyncOpenAI
from app.core.config import settings
from app.utils.logger import logger
from app.utils.exceptions import OpenAIException


class OpenRouterService:
    def __init__(self):
        """
        Initialize OpenRouter service
        
        OpenRouter API:
        - Base URL: https://openrouter.ai/api/v1
        - API Key: From settings
        - Compatible với OpenAI SDK
        """
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL
        
        if not self.api_key:
            logger.warning("⚠️  OpenRouter API key not configured")
            self.client = None
        else:
            # Initialize AsyncOpenAI client with OpenRouter base URL
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://openrouter.ai/api/v1"
            )
            #logger.info(f"✅ OpenRouter client initialized: {self.model}")
    
    
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        maxTokens: int = 1000,
        model: str = None  # 🆕 Allow override model per request
    ) -> Dict:
        import time
        
        # ============================================================
        # VALIDATE CLIENT
        # ============================================================
        
        if not self.client:
            logger.error("❌ OpenRouter client not initialized (missing API key)")
            raise OpenAIException(
                "OpenRouter API key not configured. "
                "Please set OPENROUTER_API_KEY in .env file"
            )
        
        # Use specified model or fall back to default
        selected_model = model or self.model
        
        # ============================================================
        # DETERMINE CALL TYPE
        # ============================================================
        
        call_type = "UNKNOWN"
        if len(messages) >= 2:
            system_msg = messages[0].get("content", "").lower()
            if "phân tích" in system_msg or "emotion" in system_msg or "analyze" in system_msg:
                call_type = "EMOTION_ANALYSIS"
            else:
                call_type = "AI_RESPONSE"
        
        # ============================================================
        # MAKE API CALL WITH TIMING
        # ============================================================
        
        try:
            start_time = time.time()
            
            # logger.info(f"🤖 OpenRouter [{call_type}] - Starting...")
            # logger.info(f"   Model: {selected_model}")
            # logger.info(f"   Messages: {len(messages)}")
            # logger.info(f"   Max tokens: {maxTokens}")
            # logger.info(f"   Temperature: {temperature}")
            
            # Call OpenRouter via OpenAI SDK
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
            
            end_time = time.time()
            response_time = int((end_time - start_time) * 1000)
            
            # ============================================================
            # EXTRACT DATA
            # ============================================================
            
            content = response.choices[0].message.content
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = prompt_tokens + completion_tokens
            
            # ============================================================
            # LOG SUCCESS
            # ============================================================
            
            logger.info(f"✅ OpenRouter [{call_type}] - Complete")
            logger.info(f"   Time: {response_time}ms")
            logger.info(f"   Tokens: {completion_tokens} completion / {prompt_tokens} prompt / {total_tokens} total")
            logger.info(f"   Response: {len(content)} chars")
            
            # Performance warning
            if response_time > 5000:
                logger.warning(f"⚠️  Slow response: {response_time}ms (>5s)")
            
            return {
                "content": content,
                "model": selected_model,  # Return actual model used
                "promptTokens": prompt_tokens,
                "completionTokens": completion_tokens,
                "responseTimeMs": response_time
            }
            
        except Exception as e:
            logger.error(f"❌ OpenRouter [{call_type}] - Failed")
            logger.error(f"   Error: {str(e)}")
            logger.error(f"   Type: {type(e).__name__}")
            
            # Handle specific OpenAI errors
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                raise OpenAIException("Invalid OpenRouter API key")
            elif "429" in error_msg or "Rate limit" in error_msg:
                raise OpenAIException("OpenRouter rate limit exceeded")
            elif "timeout" in error_msg.lower():
                raise OpenAIException("OpenRouter request timed out")
            else:
                raise OpenAIException(f"OpenRouter error: {error_msg}")
    
    
    async def chatStreaming(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        maxTokens: int = 1000,
        model: str = None  # 🆕 Allow override model per request
    ):
        """
        Stream AI response chunk by chunk (for real-time display)
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            maxTokens: Max tokens to generate
            model: Optional model override
        
        Yields:
            str: Content chunks as they arrive
        
        Usage:
            async for chunk in service.chatStreaming(messages):
                print(chunk, end='', flush=True)
        """
        import time
        
        if not self.client:
            logger.error("❌ OpenRouter client not initialized")
            raise OpenAIException("OpenRouter API key not configured")
        
        # Use specified model or fall back to default
        selected_model = model or self.model
        
        start_time = time.time()
        call_type = "STREAMING"
        
        # logger.info(f"🤖 OpenRouter [{call_type}] - Starting...")
        # logger.info(f"   Model: {selected_model}")
        # logger.info(f"   Messages: {len(messages)}")
        # logger.info(f"   Max tokens: {maxTokens}")
        # logger.info(f"   Temperature: {temperature}")
        
        try:
            response = await self.client.chat.completions.create(
                model=selected_model,
                messages=messages,
                temperature=temperature,
                max_tokens=maxTokens,
                stream=True 
            )
            
            total_content = ""
            chunk_count = 0
            
            async for chunk in response:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        total_content += delta.content
                        chunk_count += 1
                        yield delta.content
            
            response_time = int((time.time() - start_time) * 1000)
            
            logger.info(f"✅ OpenRouter [{call_type}] - Complete")
            logger.info(f"   Time: {response_time}ms")
            logger.info(f"   Chunks: {chunk_count}")
            logger.info(f"   Total chars: {len(total_content)}")
            
        except Exception as e:
            logger.error(f"❌ OpenRouter [{call_type}] - Failed")
            logger.error(f"   Error: {str(e)}")
            
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                raise OpenAIException("Invalid OpenRouter API key")
            elif "429" in error_msg or "Rate limit" in error_msg:
                raise OpenAIException("OpenRouter rate limit exceeded")
            elif "timeout" in error_msg.lower():
                raise OpenAIException("OpenRouter request timed out")
            else:
                raise OpenAIException(f"OpenRouter error: {error_msg}")


# ============================================================
# SINGLETON INSTANCE
# ============================================================

openRouterService = OpenRouterService()