"""Shared constants for the game module."""

# Generic names that should not be treated as specific characters
# These are placeholder names that AI might use in relationship effects
GENERIC_CHARACTER_NAMES = frozenset(
    {
        "同事",
        "朋友",
        "家人",
        "老板",
        "colleague",
        "friend",
        "family",
        "boss",
    }
)

# Generic option texts that indicate low-quality options
GENERIC_OPTION_TEXTS = {
    "zh": frozenset(
        {"休息", "学习", "工作", "继续前进", "思考一下", "保持现状", "随便"}
    ),
    "en": frozenset(
        {"rest", "study", "work", "continue", "think", "status quo", "whatever"}
    ),
}

# Role inference keywords for story characters
# Maps Chinese/English keywords to suggested roles
ROLE_KEYWORDS = {
    "zh": {
        "同事": "同事",
        "老板": "老板",
        "上司": "上司",
        "下属": "下属",
        "朋友": "朋友",
        "邻居": "邻居",
        "客户": "客户",
        "医生": "医生",
        "护士": "护士",
        "老师": "老师",
        "学生": "学生",
        "店员": "店员",
        "服务员": "服务员",
        "警察": "警察",
        "律师": "律师",
    },
    "en": {
        "colleague": "Colleague",
        "boss": "Boss",
        "supervisor": "Supervisor",
        "subordinate": "Subordinate",
        "friend": "Friend",
        "neighbor": "Neighbor",
        "client": "Client",
        "doctor": "Doctor",
        "nurse": "Nurse",
        "teacher": "Teacher",
        "student": "Student",
        "clerk": "Clerk",
        "waiter": "Waiter",
        "waitress": "Waitress",
        "police": "Police Officer",
        "lawyer": "Lawyer",
    },
}

# Importance levels ordering for sorting
# Used in: world_model.py, scheduled_events.py, event_generator.py, player_state.py
IMPORTANCE_ORDER = {
    "critical": 0,
    "important": 1,
    "normal": 2,
    "minor": 3,
}

# Valid career levels
VALID_CAREER_LEVELS = ["intern", "junior", "mid", "senior", "lead", "executive"]

# Default career level if invalid
DEFAULT_CAREER_LEVEL = "mid"

# Maximum lengths for various text fields
MAX_SUMMARY_LENGTH = 700
MAX_DESCRIPTION_LENGTH = 200
MAX_CHOICE_TEXT_LENGTH = 50

# Effect value sanity checks
EFFECT_SANITY_CHECKS = {
    "energy": {"min": -50, "max": 50, "warning_threshold": 30},
    "mood": {"min": -50, "max": 50, "warning_threshold": 30},
    "knowledge": {"min": -50, "max": 50, "warning_threshold": 30},
    "wealth": {"min": -50000, "max": 50000, "warning_threshold": 10000},
}

# Relationship affinity defaults
DEFAULT_INITIAL_AFFINITY = 50
MIN_AFFINITY = 0
MAX_AFFINITY = 100
