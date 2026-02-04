"""
Emotion Analyzer
Phân tích cảm xúc từ text của user
"""
from typing import Dict
from app.services import openRouterService
from app.utils.logger import logger
import json


EMOTION_ANALYSIS_PROMPT = """Phân tích cảm xúc từ message của user.

Message: "{message}"

Trả về JSON với format chính xác:
{{
    "emotion_state": "calm/happy/sad/anxious/stressed/angry/tired/overwhelmed/confused/neutral",
    "energy_level": 1-10,
    "urgency_level": "low/medium/high/crisis",
    "detected_themes": ["work", "sleep", "relationships", "health", ...]
}}

CHỈ trả về JSON, KHÔNG giải thích thêm."""


async def analyzeEmotion(message: str) -> Dict:
    """
    Phân tích emotion từ user message
    
    Args:
        message: User message content
    
    Returns:
        {
            "emotion_state": "anxious",
            "energy_level": 3,
            "urgency_level": "medium",
            "detected_themes": ["work", "stress"]
        }
    
    Giải thích:
    - Dùng AI để detect emotion (không rule-based)
    - emotion_state: Primary emotion
    - energy_level: 1 (very low) → 10 (very high)
    - urgency_level: Mức độ cần support
    - detected_themes: Topics detected
    
    Flow:
    1. Gọi AI với prompt analysis
    2. Parse JSON response
    3. Validate và return
    4. Fallback nếu error
    """
    try:
        prompt = EMOTION_ANALYSIS_PROMPT.format(message=message)
        
        result = await openRouterService.chat(
            messages=[
                {"role": "system", "content": "You are emotion analyzer. Return only JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,  
            maxTokens=150
        )
        
        # Parse JSON
        content = result["content"].strip()
        
        # Remove markdown code blocks nếu có
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        
        emotionData = json.loads(content.strip())
        
        logger.info(
            f"🎭 Emotion: {emotionData.get('emotion_state')}, "
            f"energy={emotionData.get('energy_level')}, "
            f"urgency={emotionData.get('urgency_level')}"
        )
        
        return emotionData
        
    except Exception as e:
        logger.error(f"❌ Emotion analysis failed: {e}")
        # Fallback: neutral emotion
        return {
            "emotion_state": "neutral",
            "energy_level": 5,
            "urgency_level": "low",
            "detected_themes": []
        }

    """
Simple Rule-Based Emotion Analyzer
Dùng làm fallback hoặc cho messages ngắn
"""

async def analyzeEmotionSimple(message: str) -> Dict:
    """
    🚀 FAST emotion analysis - Rule-based
    
    Tại sao cần:
    - Không cần call OpenRouter (instant ~1ms)
    - Fallback khi OpenRouter fail
    - Đủ tốt cho messages đơn giản
    
    How it works:
    - Keyword matching cho emotions
    - Rule-based urgency detection
    - Theme extraction từ keywords
    
    Args:
        message: User message text
    
    Returns:
        {
            "emotion_state": "calm",
            "energy_level": 5,
            "urgency_level": "low",
            "detected_themes": ["work"],
            "method": "rule_based"
        }
    """
    message_lower = message.lower()
    
    # Emotion keywords (multi-language support)
    emotion_keywords = {
        "anxious": ["lo lắng", "anxiety", "căng thẳng", "stress", "anxious", "lo au", "bồn chồn", "nervous"],
        "sad": ["buồn", "sad", "depressed", "tủi thân", "thất vọng", "hopeless", "lonely", "cô đơn", "chán đời"],
        "happy": ["vui", "happy", "excited", "tuyệt vời", "행복", "great", "vui vẻ", "hạnh phúc", "wonderful"],
        "angry": ["tức", "angry", "giận", "mad", "bực mình", "annoyed", "phẫn nộ", "furious"],
        "tired": ["mệt", "tired", "exhausted", "kiệt sức", "mệt mỏi", "đuối", "uể oải", "fatigue"],
        "stressed": ["stress", "áp lực", "pressure", "overwhelmed", "nặng nề", "quá tải"],
        "calm": ["bình tĩnh", "calm", "peaceful", "thư giãn", "relaxed", "nhẹ nhõm", "an yên"],
        "confused": ["confused", "bối rối", "hoang mang", "không biết làm sao", "mông lung", "lost"],
    }
    
    # Urgency indicators
    urgent_keywords = [
        "cấp bách", "urgent", "help", "giúp", "emergency", "cứu", 
        "muốn chết", "suicide", "tự tử", "hoảng loạn", "panic attack"
    ]
    
    # Initialize defaults
    detected_emotion = "neutral"
    urgency = "low"
    energy = 5
    themes = []
    
    # 1. Detect emotion
    for emotion, keywords in emotion_keywords.items():
        if any(kw in message_lower for kw in keywords):
            detected_emotion = emotion
            break
    
    # 2. Detect urgency
    if any(kw in message_lower for kw in urgent_keywords):
        urgency = "high"
        energy = 3
    elif "?" in message or "help" in message_lower:
        urgency = "medium"
    
    # 3. Energy level based on emotion
    energy_map = {
        "happy": 8, "excited": 9, "calm": 6, "peaceful": 7,
        "tired": 3, "sad": 4, "anxious": 4, "depressed": 2,
        "stressed": 3, "angry": 6, "overwhelmed": 2,
        "neutral": 5, "confused": 4
    }
    energy = energy_map.get(detected_emotion, 5)
    
    # 4. Theme detection
    theme_keywords = {
        "work": ["công việc", "work", "job", "deadline", "boss", "meeting", "sếp", "đồng nghiệp", "văn phòng"],
        "health": ["sức khỏe", "health", "sick", "pain", "doctor", "đau", "ốm", "bệnh", "mệt trong người"],
        "relationship": ["relationship", "bạn bè", "gia đình", "love", "người yêu", "chia tay", "breakup", "family", "friends"],
        "sleep": ["ngủ", "sleep", "insomnia", "mất ngủ", "thức đêm", "khó ngủ"],
        "money": ["tiền", "money", "financial", "lương", "nợ", "kinh tế", "finance"],
        "study": ["học", "study", "exam", "school", "thi cử", "điểm số", "trường học", "university"],
    }
    
    for theme, keywords in theme_keywords.items():
        if any(kw in message_lower for kw in keywords):
            themes.append(theme)
    
    return {
        "emotion_state": detected_emotion,
        "energy_level": energy,
        "urgency_level": urgency,
        "detected_themes": themes if themes else ["general"],
        "method": "rule_based"
    }