"""
Activity Suggestion Engine
Gợi ý activities phù hợp dựa trên emotion
"""
from typing import Dict, Optional
from app.utils.logger import logger


# Activity database (simplified cho Module 1)
# Module 5 sẽ load từ database
ACTIVITIES = {
    "breathing": {
        "name": "Bài tập hít thở",
        "duration": 5,
        "good_for": ["anxious", "stressed", "overwhelmed"],
        "energy_required": "low",
        "description": "Hít thở sâu 4-7-8 để thư giãn"
    },
    "meditation": {
        "name": "Thiền ngắn",
        "duration": 10,
        "good_for": ["anxious", "sad", "confused"],
        "energy_required": "low",
        "description": "Thiền nhẹ nhàng để tĩnh tâm"
    },
    "journaling": {
        "name": "Viết nhật ký",
        "duration": 10,
        "good_for": ["confused", "sad", "overwhelmed"],
        "energy_required": "medium",
        "description": "Viết ra cảm xúc để hiểu rõ hơn"
    },
    "music": {
        "name": "Nghe nhạc thư giãn",
        "duration": 15,
        "good_for": ["tired", "sad", "stressed"],
        "energy_required": "low",
        "description": "Nhạc nhẹ nhàng giúp thư giãn"
    },
    "walk": {
        "name": "Đi bộ ngắn",
        "duration": 10,
        "good_for": ["stressed", "angry", "tired"],
        "energy_required": "medium",
        "description": "Vận động nhẹ để giải tỏa"
    }
}


def shouldSuggestActivity(emotionData: Dict, messageContent: str) -> bool:
    """
    Quyết định có nên gợi ý activity không
    
    Args:
        emotionData: Output từ emotion analyzer
        messageContent: User message
    
    Returns:
        True nếu nên suggest, False nếu không
    
    Giải thích Rules:
    1. User hỏi trực tiếp ("làm gì", "giúp mình")
    2. Urgency cao (high/crisis)
    3. Needs support + low energy
    4. Không suggest nếu user chỉ muốn trò chuyện
    
    Flow:
    - Check keywords trong message
    - Check urgency level
    - Check energy + themes
    - Return decision
    """
    
    # Rule 1: User hỏi trực tiếp
    keywords = ["làm gì", "giúp", "tôi nên", "gợi ý", "suggest", "help me"]
    if any(kw in messageContent.lower() for kw in keywords):
        logger.info("💡 Suggest: User asked directly")
        return True
    
    # Rule 2: High urgency
    if emotionData.get("urgency_level") in ["high", "crisis"]:
        logger.info(f"💡 Suggest: High urgency ({emotionData.get('urgency_level')})")
        return True
    
    # Rule 3: Needs support + low energy
    energyLevel = emotionData.get("energy_level", 10)
    emotionState = emotionData.get("emotion_state", "neutral")
    
    needsSupport = emotionState in ["anxious", "stressed", "overwhelmed", "sad"]
    lowEnergy = energyLevel < 5
    
    if needsSupport and lowEnergy:
        logger.info(f"💡 Suggest: {emotionState} + low energy ({energyLevel})")
        return True
    
    # Default: không suggest
    logger.info("ℹ️  No suggestion needed")
    return False


def getSuggestedActivity(emotionData: Dict) -> Optional[Dict]:
    """
    Chọn activity phù hợp nhất
    
    Args:
        emotionData: {emotion_state, energy_level, urgency_level, detected_themes}
    
    Returns:
        {
            "activity_type": "breathing",
            "activity_name": "Bài tập hít thở",
            "duration": 5,
            "reason": "Hít thở sâu giúp giảm lo âu",
            "description": "..."
        }
    
    Giải thích Logic:
    1. Filter activities phù hợp với emotion
    2. Sort theo energy_required
    3. Chọn activity phù hợp với energy_level của user
    
    Flow:
    - Get emotion_state và energy_level
    - Filter ACTIVITIES where emotion in good_for
    - If low energy → chọn activity "low" energy_required
    - Else → chọn activity đầu tiên
    """
    emotion = emotionData.get("emotion_state", "neutral")
    energyLevel = emotionData.get("energy_level", 5)
    
    # Filter activities phù hợp
    suitableActivities = []
    for actType, act in ACTIVITIES.items():
        if emotion in act["good_for"]:
            suitableActivities.append((actType, act))
    
    if not suitableActivities:
        logger.info("ℹ️  No suitable activity found")
        return None
    
    # Chọn dựa trên energy level
    if energyLevel < 4:
        # Low energy → chọn "low" energy activity
        for actType, act in suitableActivities:
            if act["energy_required"] == "low":
                logger.info(f"✅ Suggested: {actType} (low energy)")
                return {
                    "activity_type": actType,
                    "activity_name": act["name"],
                    "duration": act["duration"],
                    "reason": f"{act['name']} phù hợp khi bạn đang cảm thấy {emotion}",
                    "description": act["description"]
                }
    
    # Default: chọn activity đầu tiên
    actType, act = suitableActivities[0]
    logger.info(f"✅ Suggested: {actType}")
    return {
        "activity_type": actType,
        "activity_name": act["name"],
        "duration": act["duration"],
        "reason": f"Mình nghĩ {act['name']} có thể giúp bạn cảm thấy tốt hơn",
        "description": act["description"]
    }


def generateSuggestionMessage(activity: Dict) -> str:
    """
    Tạo message gợi ý tự nhiên
    
    Args:
        activity: Output từ getSuggestedActivity()
    
    Returns:
        "Mình có một gợi ý nhỏ: Bạn thử bài tập hít thở 5 phút nhé?
        Hít thở sâu giúp giảm lo âu hiệu quả 💙"
    
    Giải thích:
    - Format message friendly, không cứng nhắc
    - Include duration và reason
    - Emoji 💙 để soften
    """
    return (
        f"Mình có một gợi ý nhỏ: Bạn thử {activity['activity_name'].lower()} "
        f"({activity['duration']} phút) nhé? {activity['reason']} 💙"
    )


"""
Giải thích Suggestion Logic:

1. WHY suggest?
   - User explicitly asks
   - High urgency (needs immediate support)
   - Low energy + negative emotion

2. WHAT to suggest?
   - Filter by emotion (anxious → breathing)
   - Match energy level (low energy → low effort activity)
   
3. HOW to present?
   - Gentle message ("gợi ý nhỏ")
   - Include reason (why this activity)
   - Not forcing ("bạn thử... nhé?")

Flow:
User message → Emotion analysis → shouldSuggest? → getSuggestedActivity → formatMessage
"""