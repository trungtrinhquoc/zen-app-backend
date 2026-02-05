"""
Activity Suggestion Engine - SMART CONTEXT-AWARE
Gợi ý activities với visual cards đẹp như trong ảnh
"""
from typing import Dict, Optional, List
from app.utils.logger import logger


# Enhanced Activity database - MATCH VỚI ẢNH MẪU
ACTIVITIES = {
    "breathing": {
        "name": "Breathing exercise",
        "name_vi": "Bài tập hít thở",
        "duration": 1,
        "description": "Slow your breath for 1 minute.",
        "description_vi": "Thở chậm trong 1 phút.",
        "good_for": ["anxious", "stressed", "overwhelmed"],
        "energy_required": "low",
        "icon": "🌬️",
        "visual_style": "gradient-pink-purple",  # For card design
        "action_text": "Try it →",
        "card_title": "🌸 Breathing exercise"
    },
    "release_stress": {
        "name": "Release stress",
        "name_vi": "Giải tỏa căng thẳng",
        "duration": 5,
        "description": "Name one word. Watch it fade.",
        "description_vi": "Nói một từ. Để nó tan dần.",
        "good_for": ["stressed", "sad", "angry"],
        "energy_required": "low",
        "icon": "🌊",
        "visual_style": "gradient-purple-blue",
        "action_text": "Try it →",
        "card_title": "🌊 Release stress"
    },
    "healing_routine": {
        "name": "Healing Routine",
        "name_vi": "Liệu trình chữa lành",
        "duration": 10,
        "description": "A small practice, carried gently.",
        "description_vi": "Thực hành nhẹ nhàng.",
        "good_for": ["calm", "happy", "neutral"],
        "energy_required": "medium",
        "icon": "🌸",
        "visual_style": "gradient-purple-pink",
        "action_text": "Continue →",
        "card_title": "🌸 Healing Routine"
    },
    "healing_studio": {
        "name": "Healing Studio",
        "name_vi": "Studio chữa lành",
        "duration": 15,
        "description": "Less talk.... more action. / Lo-fi...",
        "description_vi": "Ít nói... nhiều hành động hơn.",
        "good_for": ["refuse", "tired", "overwhelmed"],
        "energy_required": "low",
        "icon": "🎵",
        "visual_style": "gradient-dark-blue",
        "action_text": "Listen →",
        "card_title": "🎵 Healing Studio"
    },
    "rest_sounds": {
        "name": "Rest Sounds",
        "name_vi": "Âm thanh thư giãn",
        "duration": 20,
        "description": "Gentle sounds to help you rest.",
        "description_vi": "Âm thanh nhẹ nhàng giúp bạn nghỉ ngơi.",
        "good_for": ["tired", "overwhelmed", "refuse"],
        "energy_required": "very_low",
        "icon": "🎶",
        "visual_style": "gradient-soft-blue",
        "action_text": "Play →",
        "card_title": "🎶 Rest Sounds"
    }
}


def shouldSuggestActivity(
    emotionData: Dict, 
    messageContent: str, 
    conversationTurnCount: int = 0,
    lastAssistantMessage: str = ""
) -> bool:
    """
    SMART decision về khi nào suggest - MATCH PATTERN TRONG ẢNH
    
    Args:
        emotionData: Emotion analysis
        messageContent: User message
        conversationTurnCount: Số lượt đã chat trong conversation này
        lastAssistantMessage: Message cuối của assistant
    
    Returns:
        True nếu đã đến lúc suggest
    """
    
    # Rule 1: KHÔNG suggest ở turn 1 (proactive greeting)
    if conversationTurnCount <= 1:
        logger.info("ℹ️  Too early - no suggestion yet")
        return False
    
    # Rule 2: Đã invite trong message trước → Giờ suggest card
    invitation_keywords = [
        "would you like", "có muốn", "bạn thử", "we can try",
        "would a", "có giúp", "help right now", "giúp được không"
    ]
    if any(kw in lastAssistantMessage.lower() for kw in invitation_keywords):
        logger.info("💡 Suggest: After invitation in previous message")
        return True
    
    # Rule 3: User đồng ý ("yes", "ok", "okay", "có")
    agreement_keywords = ["yes", "ok", "okay", "yeah", "sure", "có", "được", "ừ"]
    if any(kw in messageContent.lower() for kw in agreement_keywords):
        logger.info("💡 Suggest: User agreed")
        return True
    
    # Rule 4: User hỏi trực tiếp
    direct_ask = ["làm gì", "giúp", "tôi nên", "gợi ý", "suggest", "help me", "what should"]
    if any(kw in messageContent.lower() for kw in direct_ask):
        logger.info("💡 Suggest: User asked directly")
        return True
    
    # Rule 5: Sau 2-3 turns validation, giờ có thể suggest
    if conversationTurnCount >= 3:
        emotionState = emotionData.get("emotion_state", "neutral")
        if emotionState in ["anxious", "stressed", "sad", "overwhelmed", "refuse"]:
            logger.info(f"💡 Suggest: Turn {conversationTurnCount}, emotion={emotionState}")
            return True
    
    # Default: chưa đến lúc
    logger.info(f"ℹ️  Not yet - turn {conversationTurnCount}")
    return False


def getSuggestedActivity(emotionData: Dict, userLanguage: str = "vi") -> Optional[Dict]:
    """
    Chọn activity phù hợp - TRẢ VỀ VISUAL CARD DATA
    
    Returns:
        {
            "activity_type": "breathing",
            "card_title": "🌸 Breathing exercise",
            "description": "Slow your breath for 1 minute.",
            "duration": 1,
            "action_text": "Try it →",
            "visual_style": "gradient-pink-purple",
            "icon": "🌬️"
        }
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
    
    # Ưu tiên dựa trên energy
    if energyLevel <= 3:
        # Very low energy → passive activities
        for actType, act in suitableActivities:
            if act["energy_required"] in ["very_low", "low"]:
                return _formatActivityCard(actType, act, userLanguage)
    
    # Default: first suitable
    actType, act = suitableActivities[0]
    return _formatActivityCard(actType, act, userLanguage)


def _formatActivityCard(actType: str, act: Dict, userLanguage: str = "vi") -> Dict:
    """
    Format activity thành visual card data
    """
    return {
        "activity_type": actType,
        "card_title": act["card_title"],
        "description": act["description_vi"] if userLanguage == "vi" else act["description"],
        "duration": act["duration"],
        "action_text": act["action_text"],
        "visual_style": act["visual_style"],
        "icon": act["icon"],
        "name": act["name_vi"] if userLanguage == "vi" else act["name"]
    }


def generateSuggestionMessage(activity: Dict) -> str:
    """
    Generate message đi kèm suggestion card
    
    Trong ảnh: Message này đi TRƯỚC card
    """
    templates = [
        "This is something gentle you can try.",
        "Đây là một thứ nhẹ nhàng bạn có thể thử.",
    ]
    
    import random
    return random.choice(templates)


def getFollowUpMessage(activity: Dict) -> str:
    """
    Message ĐI SAU suggestion card (reassurance)
    
    Trong ảnh mẫu: "There's no rush. Just notice, then let it fade."
    """
    reassurances = [
        "There's no rush. Just notice, then let it fade.",
        "You can stop anytime. Go at your own pace.",
        "There's no rush. We'll take it one step at a time.",
        "Không vội đâu. Chúng ta làm từng bước một thôi.",
        "Bạn có thể dừng bất cứ lúc nào. Theo nhịp của bạn."
    ]
    
    import random
    return random.choice(reassurances)


"""
ENHANCED Suggestion Logic - MATCH ẢNH MẪU:

1. TIMING (Khi nào suggest):
   ❌ Turn 1: Greeting - No suggestion
   ❌ Turn 2: Validation - No suggestion  
   ✅ Turn 3: Invitation message ("Would...?")
   ✅ Turn 4: User agrees → SHOW CARD
   
2. CARD STRUCTURE (Match ảnh):
   • Visual card với gradient background
   • Icon + Title
   • Short description
   • Action button ("Try it →", "Continue →")
   
3. MESSAGE FLOW:
   Message BEFORE card: "This is something gentle you can try."
   [VISUAL CARD]
   Message AFTER card: "There's no rush. Just notice, then let it fade."
"""