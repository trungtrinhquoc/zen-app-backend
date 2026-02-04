"""
Simple Responder
Fast responses for common patterns without AI
"""
import re
from typing import Optional, Tuple


GREETING_PATTERNS = [
    # Vietnamese
    r'\b(xin chào|chào|hello|hi|hey)\b',
    r'\b(buổi sáng|buổi chiều|buổi tối)\b',
    # English
    r'\b(good morning|good afternoon|good evening)\b',
]

GREETING_RESPONSES = [
    "Xin chào! Mình rất vui được nói chuyện với bạn hôm nay. Bạn có muốn chia sẻ điều gì không? 💙",
    "Chào bạn! Mình ở đây để lắng nghe bạn. Bạn cảm thấy thế nào hôm nay? 🌸",
    "Hello! Rất vui được gặp bạn. Hãy thoải mái chia sẻ bất cứ điều gì bạn muốn nhé. ✨",
]


def isSimpleGreeting(message: str) -> bool:
    """
    Check if message is a simple greeting
    
    Args:
        message: User message
    
    Returns:
        True if simple greeting
    """
    message_lower = message.lower().strip()
    
    # Short message check
    if len(message_lower) > 30:
        return False
    
    # Pattern matching
    for pattern in GREETING_PATTERNS:
        if re.search(pattern, message_lower, re.IGNORECASE):
            # Ensure it's ONLY greeting (no other content)
            words = message_lower.split()
            if len(words) <= 3:
                return True
    
    return False


def getSimpleResponse(message: str) -> Tuple[str, dict]:
    """
    Get simple response for greeting
    
    Returns:
        Tuple[content, metadata]
    """
    import random
    import time
    
    start = time.time()
    response = random.choice(GREETING_RESPONSES)
    elapsed = int((time.time() - start) * 1000)
    
    metadata = {
        "model": "simple-responder",
        "promptTokens": 0,
        "completionTokens": 0,
        "responseTimeMs": elapsed
    }
    
    return response, metadata