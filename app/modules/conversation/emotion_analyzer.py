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
Giải thích Emotion Analysis:
- Tại sao dùng AI thay vì rule-based?
  → AI hiểu context tốt hơn
  → Detect nuanced emotions
  → Multilingual support
  
- Temperature = 0.2:
  → Low temp = consistent output
  → Quan trọng cho JSON parsing
  
- Fallback mechanism:
  → Nếu AI fail → return neutral
  → App không crash
"""