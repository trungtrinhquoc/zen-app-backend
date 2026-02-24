"""
Activity Suggestion Engine - SMART CONTEXT-AWARE
Implicit intent detection + Need-based matching
"""
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import re
from app.utils.logger import logger


# ============================================================
# SIGNAL PATTERNS - Implicit intent detection
# ============================================================

class PhysiologicalSignals:
    """Physiological distress signals"""
    SLEEP_ISSUES = r"\b(không ngủ|mất ngủ|ngủ không được|insomnia|can'?t sleep|thức suốt đêm)\b"
    ANXIETY_PHYSICAL = r"\b(tim đập|hồi hộp|panic|lo âu|anxiety|anxious)\b"
    BREATHING_ISSUES = r"\b(thở không ra|nghẹt thở|chest tight|khó thở|hụt hơi)\b"
    PAIN = r"\b(đầu đau|headache|migraine|nhức đầu)\b"
    FATIGUE = r"\b(mệt|exhausted|kiệt sức|tired|mệt mỏi|uể oải)\b"


class CognitiveSignals:
    """Cognitive overload signals"""
    OVERWHELM = r"\b(lộn xộn|overwhelmed|quá nhiều|too much|choáng ngợp|không kham nổi)\b"
    OVERTHINKING = r"\b(nghĩ mãi|overthink|không ngừng nghĩ|suy nghĩ quá nhiều|ruminate)\b"
    RACING_THOUGHTS = r"\b(đầu óc chạy|mind racing|thoughts racing|ý nghĩ bay)\b"


class EmotionalSignals:
    """Strong emotional signals"""
    ANGER = r"\b(giận|angry|mad|tức|bực|phẫn nộ)\b"
    SADNESS = r"\b(buồn|sad|depressed|down|tệ|tồi tệ)\b"
    FRUSTRATION = r"\b(frustrated|thất vọng|chán nản|bế tắc)\b"


class SituationalSignals:
    """Situational context"""
    WORK_STRESS = r"\b(deadline|sếp|boss|công việc|meeting|presentation|dự án)\b"
    SOCIAL_CONFLICT = r"\b(cãi|tranh cãi|mắng|argue|conflict|criticized)\b"


class DisengagementSignals:
    """User wants to disengage"""
    REFUSAL = r"\b(thôi|không muốn nói|don'?t want to talk|chưa|để sau|not now)\b"
    SHUTDOWN = r"\b(mệt rồi|đủ rồi|enough|stop)\b"


class ExplicitIntentSignals:
    """Explicit activity requests"""
    MUSIC = r"\b(nhạc|music|nghe|listen|âm thanh|sound)\b"
    BREATHING = r"\b(thở|breath|hít thở|breathing)\b"
    ROUTINE = r"\b(routine|liệu trình|tập)\b"
    JOURNALING = r"\b(viết|write|journal|nhật ký|ghi chép|diary)\b"


# ============================================================
# USER NEEDS FRAMEWORK
# ============================================================

@dataclass
class UserNeeds:
    """User needs profile at current moment"""
    need_calming: float = 0.0        # Need to calm down (0-1)
    need_distraction: float = 0.0    # Need distraction from thoughts (0-1)
    need_activation: float = 0.0     # Need to release energy (0-1)
    need_processing: float = 0.0     # Need to process emotions (0-1)
    urgency: float = 0.0             # Urgency level (0-1)
    
    def get_dominant_need(self) -> Tuple[str, float]:
        """Return dominant need"""
        needs = {
            'calming': self.need_calming,
            'distraction': self.need_distraction,
            'activation': self.need_activation,
            'processing': self.need_processing
        }
        dominant = max(needs.items(), key=lambda x: x[1])
        return dominant


# ============================================================
# ACTIVITY PROFILES
# ============================================================

@dataclass
class ActivityProfile:
    """Complete activity profile"""
    id: str
    name: str
    name_vi: str
    duration: int
    description: str
    description_vi: str
    icon: str
    visual_style: str
    action_text: str
    card_title: str
    route_path: str
    
    # Capabilities (0-1)
    provides_calming: float
    provides_distraction: float
    provides_activation: float
    provides_processing: float
    
    # Properties
    commitment_level: int      # 1=lowest, 5=highest
    immediacy: float          # 0-1, how quickly it helps
    requires_talking: bool
    energy_required: str
    base_priority: int
    good_for_emotions: List[str] = field(default_factory=list)


# Activity database
ACTIVITIES = {
    "breathing": ActivityProfile(
        id="breathing",
        name="Breathing exercise",
        name_vi="Bài tập hít thở",
        duration=1,
        description="Slow your breath for 1 minute.",
        description_vi="Thở chậm trong 1 phút.",
        icon="🌬️",
        visual_style="gradient-pink-purple",
        action_text="Try it →",
        card_title="🌸 Breathing exercise",
        route_path="/activity/breathing",
        
        provides_calming=0.9,
        provides_distraction=0.3,
        provides_activation=0.1,
        provides_processing=0.4,
        
        commitment_level=1,
        immediacy=0.95,
        requires_talking=False,
        energy_required="low",
        base_priority=10,
        good_for_emotions=["anxious", "stressed", "overwhelmed"]
    ),
    
    "release_stress": ActivityProfile(
        id="release_stress",
        name="Release stress",
        name_vi="Giải tỏa căng thẳng",
        duration=5,
        description="Name one word. Watch it fade.",
        description_vi="Nói một từ. Để nó tan dần.",
        icon="🌊",
        visual_style="gradient-purple-blue",
        action_text="Try it →",
        card_title="🌊 Release stress",
        route_path="/activity/breathing",
        
        provides_calming=0.6,
        provides_distraction=0.5,
        provides_activation=0.3,
        provides_processing=0.8,
        
        commitment_level=2,
        immediacy=0.7,
        requires_talking=True,
        energy_required="low",
        base_priority=9,
        good_for_emotions=["stressed", "sad", "angry"]
    ),
    
    "rest_sounds": ActivityProfile(
        id="rest_sounds",
        name="Rest Sounds",
        name_vi="Âm thanh thư giãn",
        duration=20,
        description="Gentle sounds to help you rest.",
        description_vi="Âm thanh nhẹ nhàng giúp bạn nghỉ ngơi.",
        icon="🎶",
        visual_style="gradient-soft-blue",
        action_text="Play →",
        card_title="🎶 Rest Sounds",
        route_path="/activity/music",
        
        provides_calming=0.8,
        provides_distraction=0.7,
        provides_activation=0.0,
        provides_processing=0.2,
        
        commitment_level=1,
        immediacy=0.9,
        requires_talking=False,
        energy_required="very_low",
        base_priority=8,
        good_for_emotions=["tired", "overwhelmed", "refuse"]
    ),
    
    "healing_studio": ActivityProfile(
        id="healing_studio",
        name="Healing Studio",
        name_vi="Studio chữa lành",
        duration=15,
        description="Less talk.... more action. / Lo-fi...",
        description_vi="Ít nói... nhiều hành động hơn.",
        icon="🎵",
        visual_style="gradient-dark-blue",
        action_text="Listen →",
        card_title="🎵 Healing Studio",
        route_path="/activity/music",
        
        provides_calming=0.7,
        provides_distraction=0.8,
        provides_activation=0.2,
        provides_processing=0.3,
        
        commitment_level=2,
        immediacy=0.8,
        requires_talking=False,
        energy_required="low",
        base_priority=7,
        good_for_emotions=["refuse", "tired", "stressed"]
    ),
    
    "healing_routine": ActivityProfile(
        id="healing_routine",
        name="Healing Routine",
        name_vi="Liệu trình chữa lành",
        duration=10,
        description="A small practice, carried gently.",
        description_vi="Thực hành nhẹ nhàng.",
        icon="🌸",
        visual_style="gradient-purple-pink",
        action_text="Continue →",
        card_title="🌸 Lộ Trình Chữa Lành",
        route_path="/activity/routine",
        
        provides_calming=0.7,
        provides_distraction=0.4,
        provides_activation=0.5,
        provides_processing=0.9,
        
        commitment_level=4,
        immediacy=0.3,
        requires_talking=False,
        energy_required="medium",
        base_priority=5,
        good_for_emotions=["calm", "happy", "hopeful", "neutral", "anxious", "stressed"]
    ),
    
    "journaling": ActivityProfile(
        id="journaling",
        name="Journaling",
        name_vi="Viết nhật ký",
        duration=10,
        description="Write down what's on your mind.",
        description_vi="Viết ra những gì bạn đang nghĩ.",
        icon="📝",
        visual_style="gradient-purple-blue",  # was gradient-warm-orange (does not exist)
        action_text="Start writing →",
        card_title="📝 Viết Nhật Ký",
        route_path="/activity/journaling",
        
        provides_calming=0.6,
        provides_distraction=0.4,
        provides_activation=0.2,
        provides_processing=0.95,  # Very high processing
        
        commitment_level=3,
        immediacy=0.5,
        requires_talking=False,
        energy_required="medium",
        base_priority=6,
        good_for_emotions=["sad", "frustrated", "overwhelmed", "anxious"]
    ),
}


# ============================================================
# CONVERSATION CONTEXT
# ============================================================

@dataclass
class ConversationContext:
    """Track conversation state"""
    turn_count: int = 0
    last_assistant_message: str = ""
    suggested_activities: List[str] = field(default_factory=list)
    has_suggested_in_session: bool = False  # NEW: Track if we already suggested
    
    def add_suggestion(self, activity_id: str):
        """Track suggested activity"""
        self.suggested_activities.append(activity_id)
        self.has_suggested_in_session = True  # Mark that we've suggested
    
    def was_recently_suggested(self, activity_id: str, window: int = 3) -> bool:
        """Check if activity was suggested recently"""
        if len(self.suggested_activities) < window:
            return activity_id in self.suggested_activities
        return activity_id in self.suggested_activities[-window:]


# ============================================================
# CONTEXT ANALYZER
# ============================================================

class ContextAnalyzer:
    """Analyze implicit signals from conversation"""
    
    @staticmethod
    def analyze_user_needs(
        user_message: str,
        emotion_data: Dict,
        current_hour: int = None
    ) -> UserNeeds:
        """
        Multi-layer signal analysis → UserNeeds
        """
        needs = UserNeeds()
        msg_lower = user_message.lower()
        current_hour = current_hour or datetime.now().hour
        
        emotion = emotion_data.get("emotion_state", "neutral")
        energy = emotion_data.get("energy_level", 5)
        
        # Layer 1: Physiological signals
        if re.search(PhysiologicalSignals.SLEEP_ISSUES, msg_lower):
            needs.need_calming += 0.4
            needs.urgency += 0.3
            
        if re.search(PhysiologicalSignals.ANXIETY_PHYSICAL, msg_lower):
            needs.need_calming += 0.5
            needs.urgency += 0.4
            
        if re.search(PhysiologicalSignals.BREATHING_ISSUES, msg_lower):
            needs.need_calming += 0.6
            needs.urgency += 0.5
            
        if re.search(PhysiologicalSignals.PAIN, msg_lower):
            needs.need_calming += 0.3
            needs.need_distraction += 0.3
            
        if re.search(PhysiologicalSignals.FATIGUE, msg_lower):
            needs.need_calming += 0.3
            needs.need_distraction += 0.2
        
        # Layer 2: Cognitive overload
        if re.search(CognitiveSignals.OVERWHELM, msg_lower):
            needs.need_calming += 0.4
            needs.need_distraction += 0.5
            needs.urgency += 0.3
            
        if re.search(CognitiveSignals.OVERTHINKING, msg_lower):
            needs.need_distraction += 0.6
            needs.need_calming += 0.3
            
        if re.search(CognitiveSignals.RACING_THOUGHTS, msg_lower):
            needs.need_distraction += 0.5
            needs.need_calming += 0.4
        
        # Layer 3: Emotional state
        if emotion in ["anxious", "stressed", "overwhelmed"]:
            needs.need_calming += 0.5
            needs.urgency += 0.3
            
            if energy <= 4:
                needs.need_calming += 0.3
                needs.urgency += 0.2
        
        if emotion in ["sad", "depressed"]:
            needs.need_processing += 0.4
            needs.need_distraction += 0.3
            
        if emotion in ["angry", "frustrated"]:
            needs.need_processing += 0.5
            
            if energy >= 7:
                needs.need_activation += 0.6
            else:
                needs.need_calming += 0.3
        
        if emotion == "refuse":
            needs.need_distraction += 0.6
            needs.need_processing -= 0.3
        
        # Layer 4: Situational context
        if re.search(SituationalSignals.WORK_STRESS, msg_lower):
            needs.need_distraction += 0.3
            needs.urgency += 0.2
            
        if re.search(SituationalSignals.SOCIAL_CONFLICT, msg_lower):
            needs.need_processing += 0.4
            if energy >= 6:
                needs.need_activation += 0.3
        
        # Layer 5: Disengagement signals
        if re.search(DisengagementSignals.REFUSAL, msg_lower):
            needs.need_distraction += 0.5
            needs.need_processing -= 0.4
            
        if re.search(DisengagementSignals.SHUTDOWN, msg_lower):
            needs.need_distraction += 0.6
            needs.need_calming += 0.4
        
        # Layer 6: Time-based context
        if 22 <= current_hour or current_hour <= 6:
            if emotion in ["anxious", "stressed"]:
                needs.need_calming += 0.3
                
            if re.search(PhysiologicalSignals.SLEEP_ISSUES, msg_lower):
                needs.need_calming += 0.4
                needs.urgency += 0.3
        
        # Clamp to 0-1
        needs.need_calming = min(1.0, max(0.0, needs.need_calming))
        needs.need_distraction = min(1.0, max(0.0, needs.need_distraction))
        needs.need_activation = min(1.0, max(0.0, needs.need_activation))
        needs.need_processing = min(1.0, max(0.0, needs.need_processing))
        needs.urgency = min(1.0, max(0.0, needs.urgency))
        
        return needs


# ============================================================
# SMART ACTIVITY SELECTOR
# ============================================================

class SmartActivitySelector:
    """Need-based activity matching"""
    
    @staticmethod
    def select_best_activity(
        user_message: str,
        user_needs: UserNeeds,
        context: ConversationContext,
        language: str = "vi"
    ) -> Optional[Dict]:
        """
        Select best activity based on needs
        """
        msg_lower = user_message.lower()
        
        # ============================================================
        # PRIORITY 0: Context from previous message (when user agrees)
        # ============================================================
        # If user says "yes/ok/được" AND last message mentioned an activity
        agreement_keywords = ["yes", "ok", "okay", "yeah", "sure", "có", "được", "ừ", "uhm"]
        if any(kw in msg_lower for kw in agreement_keywords):
            last_msg = context.last_assistant_message.lower()
            
            # Check what was offered in previous message
            if any(kw in last_msg for kw in ["nhạc", "music", "nghe", "listen", "âm thanh", "sound", "lo-fi", "lofi"]):
                logger.info("🎵 Context: User agreed to MUSIC from previous message")
                for act_id in ["healing_studio", "rest_sounds"]:
                    if act_id in ACTIVITIES:
                        context.add_suggestion(act_id)
                        return SmartActivitySelector._format_activity(ACTIVITIES[act_id], language)
            
            if any(kw in last_msg for kw in ["thở", "breath", "breathing", "hít thở"]):
                logger.info("🌬️  Context: User agreed to BREATHING from previous message")
                for act_id in ["breathing", "release_stress"]:
                    if act_id in ACTIVITIES:
                        context.add_suggestion(act_id)
                        return SmartActivitySelector._format_activity(ACTIVITIES[act_id], language)
            
            if any(kw in last_msg for kw in ["viết", "write", "journal", "nhật ký", "ghi chép"]):
                logger.info("📝 Context: User agreed to JOURNALING from previous message")
                if "journaling" in ACTIVITIES:
                    context.add_suggestion("journaling")
                    return SmartActivitySelector._format_activity(ACTIVITIES["journaling"], language)
            
            if any(kw in last_msg for kw in ["routine", "liệu trình", "practice", "thực hành"]):
                logger.info("🌸 Context: User agreed to ROUTINE from previous message")
                if "healing_routine" in ACTIVITIES:
                    context.add_suggestion("healing_routine")
                    return SmartActivitySelector._format_activity(ACTIVITIES["healing_routine"], language)
        
        # ============================================================
        # PRIORITY 1: Explicit intent (user directly asks)
        # ============================================================
        if re.search(ExplicitIntentSignals.MUSIC, msg_lower):
            logger.info("🎵 Explicit intent: MUSIC")
            for act_id in ["healing_studio", "rest_sounds"]:
                if act_id in ACTIVITIES:
                    context.add_suggestion(act_id)
                    return SmartActivitySelector._format_activity(ACTIVITIES[act_id], language)
        
        if re.search(ExplicitIntentSignals.BREATHING, msg_lower):
            logger.info("🌬️  Explicit intent: BREATHING")
            for act_id in ["breathing", "release_stress"]:
                if act_id in ACTIVITIES:
                    context.add_suggestion(act_id)
                    return SmartActivitySelector._format_activity(ACTIVITIES[act_id], language)
        
        if re.search(ExplicitIntentSignals.JOURNALING, msg_lower):
            logger.info("📝 Explicit intent: JOURNALING")
            if "journaling" in ACTIVITIES:
                context.add_suggestion("journaling")
                return SmartActivitySelector._format_activity(ACTIVITIES["journaling"], language)
        
        # ============================================================
        # PRIORITY 2: Need-based scoring
        # ============================================================
        scored_activities = []
        
        for activity_id, activity in ACTIVITIES.items():
            score = SmartActivitySelector._calculate_match_score(
                activity=activity,
                needs=user_needs,
                context=context
            )
            
            if score > 0:
                scored_activities.append((score, activity))
        
        if not scored_activities:
            logger.info("❌ No suitable activity found")
            return None
        
        # Sort by score, select best
        scored_activities.sort(reverse=True, key=lambda x: x[0])
        best_activity = scored_activities[0][1]
        
        logger.info(f"✅ Selected: {best_activity.id} (score: {scored_activities[0][0]:.1f})")
        
        # Track suggestion
        context.add_suggestion(best_activity.id)
        
        return SmartActivitySelector._format_activity(best_activity, language)
    
    @staticmethod
    def _calculate_match_score(
        activity: ActivityProfile,
        needs: UserNeeds,
        context: ConversationContext
    ) -> float:
        """
        Scoring: Need-capability matching
        """
        score = 0.0
        
        # Core matching
        if needs.need_calming > 0.3:
            score += needs.need_calming * activity.provides_calming * 100
        
        if needs.need_distraction > 0.3:
            score += needs.need_distraction * activity.provides_distraction * 80
        
        if needs.need_activation > 0.3:
            score += needs.need_activation * activity.provides_activation * 70
        
        if needs.need_processing > 0.3:
            score += needs.need_processing * activity.provides_processing * 60
        
        # Urgency modifier
        if needs.urgency > 0.6:
            score *= (1 + activity.immediacy * 0.5)
            score -= activity.commitment_level * 15
        
        # Early turns → avoid high commitment
        if context.turn_count < 5:
            score -= activity.commitment_level * 10
        
        # Disengagement → avoid talking
        if needs.need_distraction > 0.7 and activity.requires_talking:
            score -= 20
        
        # Recency penalty
        if context.was_recently_suggested(activity.id, window=3):
            score -= 30
        
        # Base priority
        score += activity.base_priority
        
        return max(0.0, score)
    
    @staticmethod
    def _format_activity(activity: ActivityProfile, language: str) -> Dict:
        """Format for API response"""
        return {
            "activity_type": activity.id,
            "card_title": activity.card_title,
            "description": activity.description_vi if language == "vi" else activity.description,
            "duration": activity.duration,
            "action_text": activity.action_text,
            "visual_style": activity.visual_style,
            "icon": activity.icon,
            "name": activity.name_vi if language == "vi" else activity.name,
            "route_path": activity.route_path
        }


# ============================================================
# TIMING LOGIC
# ============================================================

def shouldSuggestActivity(
    emotionData: Dict, 
    messageContent: str, 
    conversationTurnCount: int = 0,
    lastAssistantMessage: str = "",
    context: Optional[ConversationContext] = None
) -> bool:
    """
    Determine when to show suggestion
    
    Rules:
    1. Never suggest if already suggested in this session (unless explicit request)
    2. Only suggest after AI invitation + user agreement
    3. Or when user explicitly asks
    """
    
    # Rule 1: Too early (need at least 2 turns of context)
    if conversationTurnCount <= 2:
        logger.info(f"ℹ️  Too early - no suggestion yet (turn {conversationTurnCount})")
        return False
    
    msg_lower = messageContent.lower()
    
    # Rule 2: Explicit intent → ALWAYS suggest (even if already suggested)
    explicit_keywords = ["nhạc", "music", "nghe", "listen", "thở", "breath", "hít thở", "breathing", 
                        "routine", "liệu trình", "tập", "exercise", "viết", "write", "journal", "nhật ký"]
    if any(kw in msg_lower for kw in explicit_keywords):
        logger.info("💡 Suggest: Explicit activity request")
        return True
    
    # Rule 3: Already suggested in this session → DON'T suggest again
    if context and context.has_suggested_in_session:
        logger.info("🚫 Already suggested in this session - no more suggestions")
        return False
    
    # Rule 4: User agreement after invitation
    invitation_keywords = [
        "would you like", "có muốn", "bạn thử", "we can try",
        "would a", "có giúp", "help right now", "giúp được không", "muốn thử",
        "để mình", "mình có thể", "bạn có muốn"
    ]
    agreement_keywords = ["yes", "ok", "okay", "yeah", "sure", "có", "được", "ừ", "uhm"]
    
    has_invitation = any(kw in lastAssistantMessage.lower() for kw in invitation_keywords)
    user_agreed = any(kw in msg_lower for kw in agreement_keywords)
    
    if has_invitation and user_agreed:
        logger.info("💡 Suggest: User agreed after invitation")
        return True
    
    logger.info(f"ℹ️  Not suggesting - turn {conversationTurnCount}")
    return False


# ============================================================
# PUBLIC API
# ============================================================

def getSuggestedActivity(
    emotionData: Dict, 
    userMessage: str = "", 
    userLanguage: str = "vi",
    context: Optional[ConversationContext] = None
) -> Optional[Dict]:
    """
    Main function - Smart activity suggestion
    
    Args:
        emotionData: {"emotion_state": "anxious", "energy_level": 4}
        userMessage: User's message
        userLanguage: "vi" or "en"
        context: ConversationContext (optional, for tracking)
    
    Returns:
        Activity dict or None
    """
    
    # Create context if not provided (backward compatibility)
    if context is None:
        context = ConversationContext()
    
    # Step 1: Analyze user needs
    needs = ContextAnalyzer.analyze_user_needs(
        user_message=userMessage,
        emotion_data=emotionData
    )
    
    dominant_need, strength = needs.get_dominant_need()
    logger.info(f"🔍 Needs: {dominant_need}={strength:.2f}, urgency={needs.urgency:.2f}")
    
    # Step 2: Select best activity
    activity = SmartActivitySelector.select_best_activity(
        user_message=userMessage,
        user_needs=needs,
        context=context,
        language=userLanguage
    )
    
    return activity


def generateSuggestionMessage(activity: Dict) -> str:
    """Generate text message for suggestion"""
    return f"Đây là điều bạn có thể thử: {activity['name']}"