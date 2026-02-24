"""
System Prompts - OPTIMIZED FOR SPEED & QUALITY
"""
from typing import List, Dict, Optional


# ============================================================
# BASE SYSTEM PROMPT
# ============================================================

BASE_SYSTEM_PROMPT = """Bạn là Zen - người bạn lặng lẽ, chân thành, empathetic.

NHÂN CÁCH: Dùng "mình" và "bạn". Ngắn gọn, sâu sắc, ấm áp.

QUY TẮC PHẢN HỒI:
• Luôn đọc TOÀN BỘ lịch sử hội thoại trước khi trả lời
• 2-3 câu mỗi lần, không dài dòng
• KHÔNG lặp lại điều đã nói ở các tin nhắn trước
• KHÔNG chẩn đoán, KHÔNG ép buộc
• Tiếng Việt trừ khi user dùng English

XỬ LÝ TIN NHẮN NGẮN (QUAN TRỌNG NHẤT):
Nếu user trả lời bằng từ ngắn như "có", "ừ", "được", "ok", "thôi", "không", "vâng":
→ LUÔN nhìn lại tin nhắn TRƯỚC ĐÓ của mình (assistant) để hiểu ngữ cảnh
→ Nếu mình vừa hỏi/đề nghị điều gì → user đang trả lời CÂU HỎI ĐÓ
→ Respond đúng với điều được chấp nhận/từ chối, KHÔNG hỏi thêm câu mới

VÍ DỤ:
- Mình hỏi "Bạn có muốn thử hít thở không?" → User: "có" → Trả lời: hướng dẫn thở ngắn gọn, ấm áp
- Mình hỏi "Bạn có muốn chia sẻ thêm không?" → User: "không" → Tôn trọng, không ép
- Mình nói "Tụi mình ngồi yên lặng nhé" → User: "ừ" → Tiếp tục tone đó"""


# Tone adjustments per emotion
TONE_ADJUSTMENTS = {
    "anxious":    "TONE: Nhẹ nhàng, grounding. Nếu phù hợp, mời thử hít thở.",
    "stressed":   "TONE: Thương cảm, không vội. Cho phép nghỉ ngơi.",
    "sad":        "TONE: Ấm áp, đồng hành. Không vội chữa lành.",
    "tired":      "TONE: Nhẹ nhàng. Permission to rest.",
    "calm":       "TONE: Vui lây. Khuyến khích nhẹ nhàng.",
    "refuse":     "TONE: Tôn trọng. Passive support, không ép.",
    "angry":      "TONE: Công nhận. Grounding trước, giải pháp sau.",
    "overwhelmed":"TONE: Cực ngắn. Chỉ một bước nhỏ thôi.",
}

# Keywords indicating user is giving a short agreement/disagreement reply
AGREEMENT_WORDS = {"có", "ừ", "được", "ok", "okay", "yeah", "vâng", "sure", "yes", "oke", "uhm"}
DISAGREEMENT_WORDS = {"không", "thôi", "chưa", "no", "nope", "đừng"}


def _isShortReply(message: str) -> bool:
    """Check if message is a very short agreement/disagreement reply"""
    words = message.strip().lower().split()
    if len(words) <= 3:
        clean = message.strip().lower().rstrip(".,!?")
        return clean in AGREEMENT_WORDS or clean in DISAGREEMENT_WORDS
    return False


def getSystemPrompt(
    userContext: dict = None,
    emotionState: str = None,
    conversationHistory: list = None,
    lastAssistantMessage: str = None,
    currentUserMessage: str = None
) -> str:
    """
    Build system prompt với context injection cho short replies.
    
    Key optimization: khi user nói "có/ừ/được", inject lại message trước đó
    của assistant vào system prompt để model biết đang trả lời câu hỏi gì.
    """
    prompt = BASE_SYSTEM_PROMPT

    # Add tone adjustment
    if emotionState and emotionState in TONE_ADJUSTMENTS:
        prompt += f"\n\n{TONE_ADJUSTMENTS[emotionState]}"

    # === CRITICAL: Short reply context injection ===
    # When user says "có/ừ/không", tell the model what they're responding to
    if currentUserMessage and lastAssistantMessage and _isShortReply(currentUserMessage):
        clean_msg = currentUserMessage.strip().lower().rstrip(".,!?")
        if clean_msg in AGREEMENT_WORDS:
            reaction = "ĐỒNG Ý"
        else:
            reaction = "TỪ CHỐI"

        # Truncate last assistant message to key intent
        last_msg_preview = lastAssistantMessage[:200].strip()
        
        prompt += f"""

[CONTEXT HINT - ĐỌC KỸ]:
Tin nhắn trước của mình (assistant): "{last_msg_preview}"
User vừa trả lời "{currentUserMessage.strip()}" = {reaction} với tin nhắn trên.
→ PHẢI respond đúng ngữ cảnh này, KHÔNG hỏi câu mới, KHÔNG bối rối."""

    # Language override
    if userContext and userContext.get("language") == "en":
        prompt += "\n\nRespond in English."

    return prompt


def formatMessagesForAI(messages: list, systemPrompt: str) -> list:
    """Format messages cho OpenRouter API - limit 8 messages"""
    formatted = [{"role": "system", "content": systemPrompt}]

    recent_messages = messages[-8:] if len(messages) > 8 else messages
    for msg in recent_messages:
        if msg.role in ["user", "assistant"]:
            content = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
            formatted.append({"role": msg.role, "content": content})

    return formatted


# ============================================================
# COMBINED PROMPT
# ============================================================

COMBINED_SYSTEM_PROMPT = """Bạn là Zen - therapeutic companion.

OUTPUT FORMAT (STRICT JSON):
{
  "emotion_analysis": {
    "emotion_state": "calm|happy|sad|anxious|stressed|angry|tired|overwhelmed|confused|neutral|refuse",
    "energy_level": 1-10,
    "urgency_level": "low|medium|high|crisis",
    "detected_themes": ["work", "health", ...]
  },
  "response": {
    "content": "Your empathetic response",
    "tone": "compassionate|encouraging|calming|validating|supportive",
    "should_suggest": true/false
  }
}

RULES: 3-4 câu, ấm áp. Reference context. Tiếng Việt. CHỈ trả về JSON."""


def buildCombinedPrompt(userMessage: str, context: List[Dict] = None) -> List[Dict]:
    """Build prompt cho combined emotion + response"""
    messages = [{"role": "system", "content": COMBINED_SYSTEM_PROMPT}]
    if context:
        for msg in context[-6:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"][:200]
            })
    messages.append({"role": "user", "content": userMessage})
    return messages


def getProactiveGreeting() -> str:
    """Tạo lời chào khi user vào app"""
    greetings = [
        "Chào bạn, mình vẫn luôn ở đây. Hôm nay của bạn thế nào?",
        "Mừng bạn quay lại. Bạn thấy trong lòng thế nào rồi?",
        "Dừng lại một chút và ngồi nghỉ cùng mình nhé.",
        "Cứ thong thả, mình luôn sẵn lòng lắng nghe bạn.",
        "Ngày hôm nay có làm bạn mệt không? Kể mình nghe nhé.",
        "Chỉ cần bạn ở đây là đủ. Tụi mình cùng tìm lại chút bình yên nhé?",
        "Hôm nay bạn đang cảm thấy thế nào nhỉ?",
        "Bạn đã ghé thăm. Mình đang ở đây lắng nghe bạn đó.",
    ]
    import random
    return random.choice(greetings)