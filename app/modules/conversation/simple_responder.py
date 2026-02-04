"""
Simple Responder
Fast responses for common patterns without AI
"""
import re
from typing import Optional, Tuple


# ============================================================
# FAST PATH PATTERNS (Skip AI for common messages)
# ============================================================

GREETING_PATTERNS = [
    # Vietnamese
    r'\b(xin chào|chào|hello|hi|hey|hii|hiii)\b',
    r'\b(buổi sáng|buổi chiều|buổi tối|chào buổi)\b',
    # English
    r'\b(good morning|good afternoon|good evening)\b',
]

THANKS_PATTERNS = [
    r'\b(cảm ơn|cám ơn|thanks|thank you|thank|thks|tks)\b',
]

BYE_PATTERNS = [
    r'\b(tạm biệt|bye|goodbye|see you|hẹn gặp lại)\b',
]

YES_NO_PATTERNS = [
    r'^(có|không|ok|okay|oke|yes|no|yep|nope|yeah|nah)$',
]

GREETING_RESPONSES = [
    "Xin chào! Mình rất vui được nói chuyện với bạn hôm nay. Bạn có muốn chia sẻ điều gì không? 💙",
    "Chào bạn! Mình ở đây để lắng nghe bạn. Bạn cảm thấy thế nào hôm nay? 🌸",
    "Hello! Rất vui được gặp bạn. Hãy thoải mái chia sẻ bất cứ điều gì bạn muốn nhé. ✨",
]

THANKS_RESPONSES = [
    "Không có gì đâu bạn! Mình luôn ở đây khi bạn cần. 💙",
    "Rất vui được giúp bạn! Bạn cảm thấy thế nào rồi? 🌸",
    "Bạn không cần cảm ơn đâu. Mình luôn sẵn sàng lắng nghe bạn nhé. ✨",
]

BYE_RESPONSES = [
    "Tạm biệt bạn! Hãy chăm sóc bản thân nhé. Mình luôn ở đây khi bạn cần. 💙",
    "Hẹn gặp lại bạn! Chúc bạn một ngày tốt lành. 🌸",
    "Bye bye! Nhớ nghỉ ngơi đầy đủ nhé. See you soon! ✨",
]

YES_NO_RESPONSES = [
    "Mình hiểu rồi. Bạn có muốn chia sẻ thêm gì không? 💙",
    "Okay! Bạn cảm thấy thế nào về điều đó? 🌸",
    "Được rồi. Mình đang lắng nghe bạn đây. ✨",
]


def isSimplePattern(message: str) -> bool:
    """
    Check if message matches any simple pattern
    
    Args:
        message: User message
    
    Returns:
        True if matches simple pattern
    """
    message_lower = message.lower().strip()
    
    # Short message check (max 30 chars for fast path)
    if len(message_lower) > 30:
        return False
    
    # Check all pattern types
    all_patterns = [
        GREETING_PATTERNS,
        THANKS_PATTERNS,
        BYE_PATTERNS,
        YES_NO_PATTERNS
    ]
    
    for patterns in all_patterns:
        for pattern in patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                # Ensure it's simple (max 4 words)
                words = message_lower.split()
                if len(words) <= 4:
                    return True
    
    return False


# Backward compatibility
def isSimpleGreeting(message: str) -> bool:
    """Alias for isSimplePattern"""
    return isSimplePattern(message)


def getSimpleResponse(message: str) -> Tuple[str, dict]:
    """
    Get simple response based on pattern type
    
    Returns:
        Tuple[content, metadata]
    """
    import random
    import time
    
    start = time.time()
    message_lower = message.lower().strip()
    
    # Determine pattern type and select appropriate response
    if any(re.search(p, message_lower, re.IGNORECASE) for p in THANKS_PATTERNS):
        response = random.choice(THANKS_RESPONSES)
    elif any(re.search(p, message_lower, re.IGNORECASE) for p in BYE_PATTERNS):
        response = random.choice(BYE_RESPONSES)
    elif any(re.search(p, message_lower, re.IGNORECASE) for p in YES_NO_PATTERNS):
        response = random.choice(YES_NO_RESPONSES)
    else:
        # Default to greeting
        response = random.choice(GREETING_RESPONSES)
    
    elapsed = int((time.time() - start) * 1000)
    
    metadata = {
        "model": "simple-responder",
        "promptTokens": 0,
        "completionTokens": 0,
        "responseTimeMs": elapsed
    }
    
    return response, metadata