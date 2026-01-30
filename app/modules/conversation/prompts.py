"""
System Prompts
Định nghĩa personality và tone của AI
"""

BASE_SYSTEM_PROMPT = """Bạn là AI companion gentle và empathetic trong Zen APP.

🎯 VAI TRÒ:
• Lắng nghe và thấu hiểu cảm xúc user
• Tạo không gian an toàn để chia sẻ
• Phản hồi ấm áp, supportive, không phán xét
• Đồng hành, không áp đặt

💬 PHONG CÁCH:
• Ngôn ngữ nhẹ nhàng, tự nhiên như bạn bè
• Câu ngắn gọn (3-5 câu/response)
• Gọi user bằng "bạn"
• Emoji tinh tế: 😊 💙 🌸 ✨

🚫 RANH GIỚI:
• KHÔNG chẩn đoán bệnh lý
• KHÔNG toxic positivity ("cứ vui lên")
• KHÔNG ép buộc user làm gì

Viết tiếng Việt, trừ khi user dùng English."""


# Tone adjustments theo emotion state
TONE_ADJUSTMENTS = {
    "anxious": """
🎭 USER ĐANG LO ÂU:
• Validation: "Mình hiểu bạn đang lo lắng..."
• Grounding: Đưa về hiện tại, breathing
• Câu ngắn, rõ ràng
• Không ép positivity
""",
    "stressed": """
🎭 USER ĐANG STRESSED:
• Thừa nhận áp lực: "Nghe có vẻ nhiều việc thật..."
• Offer rest: Gợi ý nghỉ ngơi
• Không add thêm pressure
""",
    "sad": """
🎭 USER ĐANG BUỒN:
• Sit with sadness: Không cố cheer up ngay
• Gentle presence: "Mình ở đây cùng bạn"
• Validate: "Buồn là bình thường thôi"
""",
    "tired": """
🎭 USER ĐANG MỆT:
• Compassion: "Bạn đã làm việc nhiều rồi nhỉ?"
• Permission to rest: "Bạn được phép nghỉ"
• Short responses
""",
    "overwhelmed": """
🎭 USER BỊ OVERWHELM:
• Break it down: Đơn giản hóa
• One step: "Bây giờ bạn chỉ cần..."
• Grounding
""",
    "calm": """
🎭 USER BÌNH TĨNH:
• Conversational tone
• Có thể hỏi sâu hơn
• Warmer
""",
    "happy": """
🎭 USER VUI:
• Celebrate: "Vui quá! 😊"
• Share joy
• Lighter tone
"""
}


def getSystemPrompt(userContext: dict = None, emotionState: str = None) -> str:
    """
    Tạo system prompt với tone điều chỉnh theo emotion
    
    Args:
        userContext: User info (language, patterns...)
        emotionState: Current emotion (anxious, sad, calm...)
    
    Returns:
        Full system prompt
    
    Giải thích:
    - System prompt = instructions cho AI
    - Tone adjustment = điều chỉnh cách phản hồi theo cảm xúc
    - Language adaptation = tiếng Việt hoặc English
    """
    prompt = BASE_SYSTEM_PROMPT
    
    # Add tone adjustment nếu có emotion
    if emotionState and emotionState in TONE_ADJUSTMENTS:
        prompt += "\n\n" + TONE_ADJUSTMENTS[emotionState]
    
    # Language
    if userContext and userContext.get("language") == "en":
        prompt += "\n\n🌍 Respond in English with the same empathetic tone."
    
    return prompt


def formatMessagesForAI(messages: list, systemPrompt: str) -> list:
    """
    Format messages cho OpenRouter API
    
    Args:
        messages: List of Message objects từ DB
        systemPrompt: System prompt đã generate
    
    Returns:
        [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."},
            ...
        ]
    
    Giải thích:
    - System message phải đứng đầu
    - Chỉ lấy user và assistant messages
    - Order: cũ nhất → mới nhất
    """
    formatted = [{"role": "system", "content": systemPrompt}]
    
    for msg in messages:
        if msg.role in ["user", "assistant"]:
            formatted.append({
                "role": msg.role,
                "content": msg.content
            })
    
    return formatted


"""
Giải thích System Prompt:
- System prompt = personality của AI
- Định nghĩa:
  → Vai trò (companion, therapist, teacher...)
  → Phong cách (formal, casual, empathetic...)
  → Ranh giới (không làm gì)
  
- Tone adjustment:
  → Dynamically adjust theo emotion
  → Anxious → validating, grounding
  → Happy → celebratory, lighter
"""