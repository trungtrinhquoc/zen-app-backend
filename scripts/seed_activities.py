"""
Seed Script — Activity Library
Nhập 20 activities vào bảng activity_library

CÁCH CHẠY:
    cd d:\Project_AI\zen-app\zen-app-backend
    python scripts/seed_activities.py

Giải thích cấu trúc activities:
- instructions: Array steps, mỗi step có text + duration (giây)
- best_for_emotions: Danh sách emotions phù hợp
- best_for_energy_level: Array mức năng lượng phù hợp [1,2,3] = low energy
- tags: Labels để filter (morning, quick, stress, sleep...)
"""
import asyncio
import sys
import os

# Thêm project root vào Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.core.config import settings

# ============================================================
# ACTIVITY DATA
# ============================================================

ACTIVITIES = [
    # ─────────────────────────────────────────────
    # CATEGORY: BREATHING (4)
    # ─────────────────────────────────────────────
    {
        "name": "Box Breathing",
        "slug": "box-breathing",
        "category": "breathing",
        "description": "Kỹ thuật thở hộp 4 nhịp giúp cân bằng hệ thần kinh, giảm lo âu ngay lập tức.",
        "instructions": [
            {"step": 1, "text": "Ngồi thẳng lưng, thả lỏng vai. Nhắm mắt nhẹ.", "duration": 5},
            {"step": 2, "text": "Hít vào chậm trong 4 giây — cảm nhận bụng phồng lên.", "duration": 4},
            {"step": 3, "text": "Nín thở trong 4 giây — giữ yên, đừng căng.", "duration": 4},
            {"step": 4, "text": "Thở ra hoàn toàn trong 4 giây — bụng xẹp xuống.", "duration": 4},
            {"step": 5, "text": "Nín thở trong 4 giây — cảm nhận sự tĩnh lặng.", "duration": 4},
            {"step": 6, "text": "Lặp lại 4-6 lần. Mỗi lần thở làm bạn bình tĩnh hơn.", "duration": 60}
        ],
        "duration_minutes": 5,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["anxiety", "stress", "quick", "anytime", "focus"],
        "best_for_emotions": ["anxious", "stressed", "overwhelmed", "nervous"],
        "best_for_energy_level": [1, 2, 3, 4, 5]
    },
    {
        "name": "4-7-8 Breathing",
        "slug": "4-7-8-breathing",
        "category": "breathing",
        "description": "Bài thở 4-7-8 của Dr. Andrew Weil — kích hoạt phản ứng thư giãn tự nhiên của cơ thể, giúp ngủ nhanh hơn.",
        "instructions": [
            {"step": 1, "text": "Đặt đầu lưỡi chạm vào vòm miệng trên, sau hàm răng trên.", "duration": 5},
            {"step": 2, "text": "Thở ra hoàn toàn qua miệng, tạo âm thanh 'whoosh'.", "duration": 4},
            {"step": 3, "text": "Ngậm miệng, hít vào qua mũi trong 4 giây.", "duration": 4},
            {"step": 4, "text": "Nín thở trong 7 giây.", "duration": 7},
            {"step": 5, "text": "Thở ra qua miệng trong 8 giây, tạo âm 'whoosh'.", "duration": 8},
            {"step": 6, "text": "Lặp lại 4 lần. Dừng nếu cảm thấy chóng mặt.", "duration": 80}
        ],
        "duration_minutes": 5,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["sleep", "anxiety", "relaxation", "evening", "night"],
        "best_for_emotions": ["anxious", "stressed", "tired", "overwhelmed"],
        "best_for_energy_level": [1, 2, 3, 4]
    },
    {
        "name": "Belly Breathing",
        "slug": "belly-breathing",
        "category": "breathing",
        "description": "Thở bụng sâu — kỹ thuật cơ bản nhất để reset hệ thần kinh và giảm cortisol.",
        "instructions": [
            {"step": 1, "text": "Đặt 1 tay lên ngực, 1 tay lên bụng.", "duration": 5},
            {"step": 2, "text": "Hít vào từ từ qua mũi — chỉ bụng phồng, ngực không động.", "duration": 4},
            {"step": 3, "text": "Thở ra chậm qua miệng — cảm nhận bụng xẹp xuống.", "duration": 6},
            {"step": 4, "text": "Tiếp tục nhịp 4 giây vào, 6 giây ra trong 5 phút.", "duration": 240}
        ],
        "duration_minutes": 5,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["beginner", "stress", "morning", "anytime", "anxiety"],
        "best_for_emotions": ["anxious", "stressed", "confused", "sad"],
        "best_for_energy_level": [1, 2, 3, 4, 5, 6]
    },
    {
        "name": "Coherent Breathing",
        "slug": "coherent-breathing",
        "category": "breathing",
        "description": "Thở đều 5 nhịp/phút — tần số tối ưu để đồng bộ tim và hô hấp, tạo trạng thái cân bằng sâu.",
        "instructions": [
            {"step": 1, "text": "Ngồi hoặc nằm thoải mái. Nhắm mắt.", "duration": 5},
            {"step": 2, "text": "Hít vào từ từ trong 6 giây — đếm thầm 1...2...3...4...5...6", "duration": 6},
            {"step": 3, "text": "Thở ra trong 6 giây — đếm thầm 1...2...3...4...5...6", "duration": 6},
            {"step": 4, "text": "Duy trì nhịp 6-6 này liên tục trong 10 phút.", "duration": 600}
        ],
        "duration_minutes": 10,
        "difficulty_level": "intermediate",
        "has_audio": False,
        "tags": ["meditation", "deep", "calm", "heart-coherence", "stress"],
        "best_for_emotions": ["stressed", "anxious", "angry", "overwhelmed"],
        "best_for_energy_level": [2, 3, 4, 5, 6, 7]
    },

    # ─────────────────────────────────────────────
    # CATEGORY: MEDITATION (4)
    # ─────────────────────────────────────────────
    {
        "name": "Body Scan",
        "slug": "body-scan",
        "category": "meditation",
        "description": "Quét cơ thể từ đầu đến chân — giải phóng căng thẳng ở từng vùng cơ thể, cực kỳ hiệu quả trước khi ngủ.",
        "instructions": [
            {"step": 1, "text": "Nằm xuống hoặc ngồi thoải mái. Nhắm mắt.", "duration": 10},
            {"step": 2, "text": "Bắt đầu từ đỉnh đầu — chú ý cảm giác, không cố thay đổi.", "duration": 30},
            {"step": 3, "text": "Di chuyển xuống trán, mắt, mũi, miệng, hàm — thả lỏng mỗi vùng.", "duration": 60},
            {"step": 4, "text": "Tiếp tục xuống cổ, vai, tay, ngực, bụng.", "duration": 90},
            {"step": 5, "text": "Quét xuống lưng, hông, đùi, gối, bắp chân, bàn chân.", "duration": 90},
            {"step": 6, "text": "Cảm nhận toàn thân — nặng, ấm, thư giãn. Hít thở sâu.", "duration": 20}
        ],
        "duration_minutes": 10,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["sleep", "evening", "relaxation", "body", "tension"],
        "best_for_emotions": ["stressed", "anxious", "tired", "overwhelmed"],
        "best_for_energy_level": [1, 2, 3, 4]
    },
    {
        "name": "Mindfulness Meditation",
        "slug": "mindfulness-meditation",
        "category": "meditation",
        "description": "Thiền chánh niệm — quan sát suy nghĩ mà không phán xét. Hiện diện với khoảnh khắc hiện tại.",
        "instructions": [
            {"step": 1, "text": "Ngồi thoải mái, lưng thẳng. Nhắm mắt hoặc nhìn xuống.", "duration": 10},
            {"step": 2, "text": "Tập trung vào hơi thở — cảm nhận không khí vào ra.", "duration": 30},
            {"step": 3, "text": "Khi có suy nghĩ xuất hiện — nhận ra nó, đặt tên 'đang suy nghĩ', thả đi.", "duration": 120},
            {"step": 4, "text": "Quay về hơi thở — không gắng sức, nhẹ nhàng trở lại.", "duration": 120},
            {"step": 5, "text": "Tiếp tục quan sát mà không phán xét bản thân.", "duration": 120}
        ],
        "duration_minutes": 10,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["mindfulness", "focus", "awareness", "morning", "anytime"],
        "best_for_emotions": ["anxious", "confused", "overwhelmed", "stressed"],
        "best_for_energy_level": [3, 4, 5, 6, 7]
    },
    {
        "name": "Loving Kindness Meditation",
        "slug": "loving-kindness-meditation",
        "category": "meditation",
        "description": "Thiền từ bi — gửi tình yêu thương đến bản thân và người khác. Giảm cô đơn và tự phê phán.",
        "instructions": [
            {"step": 1, "text": "Ngồi thoải mái. Đặt tay lên tim. Hít thở sâu 3 lần.", "duration": 20},
            {"step": 2, "text": "Tự nói với mình: 'Mong mình được bình yên. Mong mình được hạnh phúc. Mong mình được khỏe mạnh.'", "duration": 60},
            {"step": 3, "text": "Nghĩ đến người thân yêu. Gửi cùng lời chúc đó đến họ.", "duration": 60},
            {"step": 4, "text": "Nghĩ đến người bình thường. Gửi tình yêu thương đến họ.", "duration": 60},
            {"step": 5, "text": "Cuối cùng, gửi đến tất cả mọi người trên thế giới.", "duration": 60}
        ],
        "duration_minutes": 5,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["compassion", "loneliness", "self-love", "morning", "wellbeing"],
        "best_for_emotions": ["sad", "lonely", "angry", "frustrated"],
        "best_for_energy_level": [2, 3, 4, 5, 6]
    },
    {
        "name": "Visualization Meditation",
        "slug": "visualization-meditation",
        "category": "meditation",
        "description": "Thiền hình dung — tạo ra không gian an toàn trong tâm trí. Thoát khỏi stress bằng cách du lịch trong tưởng tượng.",
        "instructions": [
            {"step": 1, "text": "Nhắm mắt. Hít thở sâu 3 lần để ổn định.", "duration": 15},
            {"step": 2, "text": "Hình dung một nơi bình yên — biển, rừng, núi, hay phòng bạn thích.", "duration": 20},
            {"step": 3, "text": "Nhìn xung quanh trong tưởng tượng — màu sắc, ánh sáng, không gian.", "duration": 60},
            {"step": 4, "text": "Nghe âm thanh nơi đó — sóng biển, tiếng chim, gió thổi.", "duration": 60},
            {"step": 5, "text": "Cảm nhận cơ thể trong không gian đó — ấm áp, an toàn, nhẹ nhàng.", "duration": 60},
            {"step": 6, "text": "Hít thở sâu, ghi nhớ cảm giác này. Từ từ mở mắt.", "duration": 15}
        ],
        "duration_minutes": 5,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["relaxation", "creativity", "escape", "stress", "afternoon"],
        "best_for_emotions": ["anxious", "stressed", "overwhelmed", "tired"],
        "best_for_energy_level": [2, 3, 4, 5]
    },

    # ─────────────────────────────────────────────
    # CATEGORY: JOURNALING (5)
    # ─────────────────────────────────────────────
    {
        "name": "Gratitude Journal",
        "slug": "gratitude-journal",
        "category": "journaling",
        "description": "Viết 3 điều biết ơn hôm nay — khoa học chứng minh thay đổi mạch thần kinh não bộ sau 21 ngày.",
        "instructions": [
            {"step": 1, "text": "Lấy bút và giấy (hoặc gõ vào điện thoại).", "duration": 10},
            {"step": 2, "text": "Viết 3 điều bạn biết ơn hôm nay — càng cụ thể càng tốt.", "duration": 120},
            {"step": 3, "text": "Với mỗi điều — viết tại sao nó có ý nghĩa với bạn.", "duration": 120},
            {"step": 4, "text": "Đọc lại những gì bạn viết. Cảm nhận cảm xúc đó.", "duration": 30}
        ],
        "duration_minutes": 5,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["gratitude", "morning", "evening", "positive", "wellbeing"],
        "best_for_emotions": ["sad", "stressed", "anxious", "overwhelmed", "neutral"],
        "best_for_energy_level": [3, 4, 5, 6, 7, 8]
    },
    {
        "name": "Emotion Dump",
        "slug": "emotion-dump",
        "category": "journaling",
        "description": "Viết tất cả ra giấy không kiểm duyệt — xả tải cảm xúc nặng nề, không cần đúng ngữ pháp hay logic.",
        "instructions": [
            {"step": 1, "text": "Chuẩn bị viết và đặt hẹn giờ 5-10 phút.", "duration": 10},
            {"step": 2, "text": "Bắt đầu viết bất cứ điều gì trong đầu — đừng kiểm duyệt.", "duration": 240},
            {"step": 3, "text": "Khi hết giờ — đọc lại không đánh giá bản thân.", "duration": 30},
            {"step": 4, "text": "Xé giấy (nếu muốn) — một nghi thức thả đi cảm xúc.", "duration": 10}
        ],
        "duration_minutes": 10,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["emotional-release", "processing", "stress", "anger", "sadness"],
        "best_for_emotions": ["angry", "sad", "overwhelmed", "frustrated", "anxious"],
        "best_for_energy_level": [2, 3, 4, 5, 6]
    },
    {
        "name": "Three Good Things",
        "slug": "three-good-things",
        "category": "journaling",
        "description": "Ghi lại 3 điều tốt xảy ra hôm nay, dù nhỏ — tập não bộ chú ý tích cực.",
        "instructions": [
            {"step": 1, "text": "Trước khi ngủ, ngồi yên lặng 1 phút, nhìn lại ngày hôm nay.", "duration": 60},
            {"step": 2, "text": "Điều tốt thứ nhất: Bạn đã làm được gì? Có gì vui? Dù nhỏ nhoi.", "duration": 60},
            {"step": 3, "text": "Điều tốt thứ hai: Ai đó tử tế với bạn? Bạn giúp được ai không?", "duration": 60},
            {"step": 4, "text": "Điều tốt thứ ba: Khoảnh khắc nào tạm thời bạn cảm thấy ổn?", "duration": 60}
        ],
        "duration_minutes": 5,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["evening", "sleep", "positive-thinking", "gratitude", "night"],
        "best_for_emotions": ["sad", "tired", "neutral", "stressed"],
        "best_for_energy_level": [1, 2, 3, 4, 5]
    },
    {
        "name": "Dear Future Me",
        "slug": "dear-future-me",
        "category": "journaling",
        "description": "Viết thư cho bản thân trong tương lai — tạo kết nối với phiên bản tốt hơn của bạn, xây hy vọng.",
        "instructions": [
            {"step": 1, "text": "Bắt đầu: 'Dear [tên bạn] trong 1 năm nữa,'", "duration": 10},
            {"step": 2, "text": "Kể về cảm xúc hiện tại — bạn đang trải qua gì?", "duration": 90},
            {"step": 3, "text": "Hỏi bản thân tương lai — bạn muốn biết điều gì?", "duration": 60},
            {"step": 4, "text": "Gửi lời động viên đến bản thân tương lai.", "duration": 60},
            {"step": 5, "text": "Ký tên và ngày tháng. Lưu lại để đọc sau.", "duration": 20}
        ],
        "duration_minutes": 5,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["hope", "future", "self-compassion", "processing", "reflection"],
        "best_for_emotions": ["sad", "lost", "confused", "hopeless"],
        "best_for_energy_level": [3, 4, 5, 6, 7]
    },
    {
        "name": "What I Need Right Now",
        "slug": "what-i-need-right-now",
        "category": "journaling",
        "description": "Khám phá nhu cầu thực sự của bạn lúc này — thường chúng ta không rõ mình cần gì.",
        "instructions": [
            {"step": 1, "text": "Viết: 'Ngay lúc này, tôi đang cảm thấy...'", "duration": 60},
            {"step": 2, "text": "Viết: 'Điều tôi thực sự cần là...' (không kiểm duyệt)", "duration": 60},
            {"step": 3, "text": "Viết: 'Một điều nhỏ tôi có thể làm cho mình ngay bây giờ là...'", "duration": 60},
            {"step": 4, "text": "Đọc lại. Thực hiện điều nhỏ đó nếu có thể.", "duration": 30}
        ],
        "duration_minutes": 5,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["self-care", "needs", "emotional-intelligence", "awareness"],
        "best_for_emotions": ["confused", "overwhelmed", "sad", "lost"],
        "best_for_energy_level": [2, 3, 4, 5, 6]
    },

    # ─────────────────────────────────────────────
    # CATEGORY: LISTENING (4)
    # ─────────────────────────────────────────────
    {
        "name": "Rain & Thunder Sounds",
        "slug": "rain-thunder-sounds",
        "category": "listening",
        "description": "Âm thanh mưa và sấm tự nhiên — pink noise che lấp tiếng ồn, giúp não tập trung và ngủ dễ hơn.",
        "instructions": [
            {"step": 1, "text": "Đeo tai nghe hoặc mở loa nhỏ.", "duration": 5},
            {"step": 2, "text": "Nhắm mắt, để âm thanh mưa bao phủ xung quanh.", "duration": 10},
            {"step": 3, "text": "Nghe trong 10-20 phút. Không cần làm gì cả.", "duration": 600}
        ],
        "duration_minutes": 10,
        "difficulty_level": "beginner",
        "has_audio": True,
        "tags": ["sleep", "focus", "ambient", "nature", "night"],
        "best_for_emotions": ["anxious", "stressed", "tired", "overwhelmed"],
        "best_for_energy_level": [1, 2, 3, 4]
    },
    {
        "name": "Forest Ambience",
        "slug": "forest-ambience",
        "category": "listening",
        "description": "Tiếng rừng xanh — chim hót, gió qua lá, suối chảy. Shinrin-yoku (tắm rừng) số hóa giảm cortisol.",
        "instructions": [
            {"step": 1, "text": "Ngồi hoặc nằm thoải mái.", "duration": 5},
            {"step": 2, "text": "Nhắm mắt. Tưởng tượng bạn đang ở trong rừng.", "duration": 10},
            {"step": 3, "text": "Nghe và cảm nhận từng âm thanh riêng biệt.", "duration": 585}
        ],
        "duration_minutes": 10,
        "difficulty_level": "beginner",
        "has_audio": True,
        "tags": ["nature", "calm", "morning", "stress-relief", "healing"],
        "best_for_emotions": ["stressed", "anxious", "angry", "overwhelmed"],
        "best_for_energy_level": [2, 3, 4, 5, 6]
    },
    {
        "name": "Ocean Waves",
        "slug": "ocean-waves",
        "category": "listening",
        "description": "Sóng biển nhịp nhàng — nhịp điệu tự nhiên giúp đồng bộ sóng não, tạo trạng thái thư giãn sâu.",
        "instructions": [
            {"step": 1, "text": "Tìm tư thế thoải mái nhất của bạn.", "duration": 10},
            {"step": 2, "text": "Nhắm mắt. Để tiếng sóng cuốn trôi suy nghĩ.", "duration": 10},
            {"step": 3, "text": "Theo dõi nhịp vào-ra của sóng. Hít thở cùng nhịp sóng.", "duration": 580}
        ],
        "duration_minutes": 10,
        "difficulty_level": "beginner",
        "has_audio": True,
        "tags": ["sleep", "relaxation", "nature", "evening", "meditation"],
        "best_for_emotions": ["anxious", "tired", "stressed", "sad"],
        "best_for_energy_level": [1, 2, 3, 4, 5]
    },
    {
        "name": "Binaural Beats Focus",
        "slug": "binaural-beats-focus",
        "category": "listening",
        "description": "Âm thanh binaural 40Hz — kích thích sóng não gamma, tăng sự tập trung và sáng suốt.",
        "instructions": [
            {"step": 1, "text": "Bắt buộc dùng tai nghe stereo để hiệu quả.", "duration": 10},
            {"step": 2, "text": "Ngồi thẳng ở bàn làm việc hoặc không gian học.", "duration": 10},
            {"step": 3, "text": "Nghe trong 15-20 phút. Có thể làm việc nhẹ song song.", "duration": 900}
        ],
        "duration_minutes": 20,
        "difficulty_level": "beginner",
        "has_audio": True,
        "tags": ["focus", "productivity", "work", "morning", "afternoon"],
        "best_for_emotions": ["confused", "tired", "neutral", "stressed"],
        "best_for_energy_level": [4, 5, 6, 7, 8]
    },

    # ─────────────────────────────────────────────
    # CATEGORY: MOVEMENT (3)
    # ─────────────────────────────────────────────
    {
        "name": "Neck & Shoulder Release",
        "slug": "neck-shoulder-release",
        "category": "movement",
        "description": "Xả căng cổ và vai — vùng cơ thể tích lũy stress nhiều nhất. Có thể làm ngay tại bàn làm việc.",
        "instructions": [
            {"step": 1, "text": "Ngồi thẳng. Thả lỏng tay. Hít thở sâu.", "duration": 10},
            {"step": 2, "text": "Chầm chậm nghiêng đầu sang phải, giữ 20 giây.", "duration": 20},
            {"step": 3, "text": "Quay sang trái, giữ 20 giây.", "duration": 20},
            {"step": 4, "text": "Xoay vai ra sau 5 lần. Xoay ra trước 5 lần.", "duration": 30},
            {"step": 5, "text": "Ép 2 tay ra sau lưng, nâng ngực lên, giữ 10 giây.", "duration": 10},
            {"step": 6, "text": "Lắc nhẹ đầu, thả lỏng cổ. Hít thở sâu.", "duration": 10}
        ],
        "duration_minutes": 5,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["desk-worker", "quick", "office", "tension", "anytime"],
        "best_for_emotions": ["stressed", "tired", "anxious"],
        "best_for_energy_level": [3, 4, 5, 6, 7]
    },
    {
        "name": "Progressive Muscle Relaxation",
        "slug": "progressive-muscle-relaxation",
        "category": "movement",
        "description": "Căng-thả từng nhóm cơ toàn thân — phương pháp Edmund Jacobson giảm lo âu, cực hiệu quả trước ngủ.",
        "instructions": [
            {"step": 1, "text": "Nằm xuống, nhắm mắt. Hít thở sâu 3 lần.", "duration": 20},
            {"step": 2, "text": "Bàn chân: Căng cứng 5 giây → thả ra đột ngột. Cảm nhận sự khác biệt.", "duration": 10},
            {"step": 3, "text": "Bắp chân: Căng 5 giây → thả ra. Tiếp tục thả lỏng.", "duration": 10},
            {"step": 4, "text": "Đùi → Bụng → Tay → Vai → Mặt — mỗi nhóm cơ căng rồi thả.", "duration": 120},
            {"step": 5, "text": "Cảm nhận toàn thân hoàn toàn thả lỏng trên sàn/giường.", "duration": 30}
        ],
        "duration_minutes": 10,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["sleep", "evening", "anxiety", "tension", "body"],
        "best_for_emotions": ["anxious", "stressed", "tired", "overwhelmed"],
        "best_for_energy_level": [1, 2, 3, 4]
    },
    {
        "name": "Walking Meditation",
        "slug": "walking-meditation",
        "category": "movement",
        "description": "Thiền khi đi bộ — mỗi bước là một hơi thở có ý thức. Chuyển đổi trạng thái tâm lý bằng vận động.",
        "instructions": [
            {"step": 1, "text": "Tìm nơi có thể đi bộ yên tĩnh — trong nhà hoặc ngoài trời.", "duration": 10},
            {"step": 2, "text": "Bắt đầu đi chậm hơn bình thường 50%.", "duration": 10},
            {"step": 3, "text": "Chú ý từng bước chân — gót chạm đất, lòng bàn chân, ngón chân.", "duration": 120},
            {"step": 4, "text": "Đồng bộ hơi thở với bước chân — 2 bước hít, 2 bước thở.", "duration": 120},
            {"step": 5, "text": "Nếu tâm trí lạc — nhẹ nhàng quay lại cảm giác bàn chân.", "duration": 140}
        ],
        "duration_minutes": 10,
        "difficulty_level": "beginner",
        "has_audio": False,
        "tags": ["movement", "mindfulness", "outdoor", "energy", "afternoon"],
        "best_for_emotions": ["stressed", "anxious", "angry", "restless"],
        "best_for_energy_level": [4, 5, 6, 7, 8]
    }
]


async def seed_activities():
    """
    Seed activities vào DB — fully self-contained, không import từ app/
    Chỉ cần: pip install sqlalchemy asyncpg python-dotenv
    """
    import uuid as uuid_module
    from sqlalchemy import (
        Column, Text, Integer, Boolean, DateTime, Numeric
    )
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB, ARRAY
    from sqlalchemy.orm import declarative_base
    from sqlalchemy import select as sa_select
    from datetime import datetime

    SeedBase = declarative_base()

    class ActivityLibraryLocal(SeedBase):
        __tablename__ = "activity_library"
        id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid_module.uuid4)
        name = Column(Text, nullable=False)
        slug = Column(Text, nullable=False, unique=True)
        category = Column(Text, nullable=False)
        description = Column(Text, nullable=False)
        instructions = Column(JSONB, nullable=False, default=list)
        duration_minutes = Column(Integer, nullable=False)
        difficulty_level = Column(Text, default='beginner', nullable=False)
        has_audio = Column(Boolean, default=False, nullable=False)
        audio_url = Column(Text, nullable=True)
        tags = Column(ARRAY(Text), default=list, nullable=False)
        best_for_emotions = Column(ARRAY(Text), default=list, nullable=False)
        best_for_energy_level = Column(ARRAY(Integer), default=list, nullable=False)
        total_completions = Column(Integer, default=0, nullable=False)
        average_rating = Column(Numeric(3, 2), default=0.0, nullable=False)
        is_active = Column(Boolean, default=True, nullable=False)
        is_premium = Column(Boolean, default=False, nullable=False)
        created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
        updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Must convert to asyncpg driver URL
    db_url = settings.DATABASE_URL.replace(
        "postgresql://", "postgresql+asyncpg://"
    ).split("?")[0]

    engine = create_async_engine(
        db_url,
        echo=False,
        connect_args={"statement_cache_size": 0}  # Required for Supabase PgBouncer
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print(f"🌱 Seeding {len(ACTIVITIES)} activities...")
        seeded = 0
        skipped = 0

        for activity_data in ACTIVITIES:
            # Check if slug already exists
            result = await session.execute(
                sa_select(ActivityLibraryLocal).where(
                    ActivityLibraryLocal.slug == activity_data["slug"]
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  ⏭️  Skip: '{activity_data['slug']}' (already exists)")
                skipped += 1
                continue

            # Insert using ORM
            activity = ActivityLibraryLocal(
                name=activity_data["name"],
                slug=activity_data["slug"],
                category=activity_data["category"],
                description=activity_data["description"],
                instructions=activity_data["instructions"],
                duration_minutes=activity_data["duration_minutes"],
                difficulty_level=activity_data["difficulty_level"],
                has_audio=activity_data["has_audio"],
                audio_url=activity_data.get("audio_url"),
                tags=activity_data["tags"],
                best_for_emotions=activity_data["best_for_emotions"],
                best_for_energy_level=activity_data["best_for_energy_level"],
                total_completions=0,
                average_rating=0.0,
                is_active=True,
                is_premium=False,
            )
            session.add(activity)
            print(f"  ✅ Added: [{activity_data['category']}] {activity_data['name']}")
            seeded += 1

        await session.commit()
        print(f"\n🎉 Done! Seeded: {seeded}, Skipped: {skipped}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_activities())


if __name__ == "__main__":
    asyncio.run(seed_activities())
