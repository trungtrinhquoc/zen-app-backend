"""
Embedding Service
Generate vector embeddings using OpenRouter (OpenAI compatible)
"""
from openai import AsyncOpenAI
from typing import List
from app.core.config import settings
from app.utils.logger import logger


# Initialize OpenAI client with OpenRouter base URL
client = AsyncOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)


async def createEmbedding(text: str) -> List[float]:
    """
    Create embedding vector from text using OpenRouter
    
    Args:
        text: Text to embed (max 8191 tokens)
    
    Returns:
        List of 1536 floats (embedding vector)
    
    Cost: ~$0.00002 per 1K tokens via OpenRouter
    
    Example:
        >>> embedding = await createEmbedding("Tôi cảm thấy buồn về công việc")
        >>> len(embedding)
        1536
    """
    try:
        # Truncate text to avoid token limit
        truncated_text = text[:8000]
        
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=truncated_text,
            encoding_format="float"
        )
        
        embedding = response.data[0].embedding
        
        logger.info(
            f"✅ Created embedding: {len(embedding)} dimensions, "
            f"text length: {len(text)} chars"
        )
        
        return embedding
        
    except Exception as e:
        logger.error(f"❌ Embedding generation failed: {e}")
        raise


async def createBatchEmbeddings(texts: List[str]) -> List[List[float]]:
    """
    Create embeddings for multiple texts (batch processing)
    More efficient than calling createEmbedding multiple times
    
    Args:
        texts: List of texts to embed
    
    Returns:
        List of embedding vectors
    """
    try:
        truncated_texts = [t[:8000] for t in texts]
        
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=truncated_texts,
            encoding_format="float"
        )
        
        embeddings = [item.embedding for item in response.data]
        
        logger.info(f"✅ Created {len(embeddings)} embeddings in batch")
        
        return embeddings
        
    except Exception as e:
        logger.error(f"❌ Batch embedding generation failed: {e}")
        raise
