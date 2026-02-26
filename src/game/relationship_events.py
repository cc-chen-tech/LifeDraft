"""
关系事件定义系统
定义15种关系触发事件及其时代适配
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum


class EventCategory(Enum):
    """事件类别"""
    ROMANCE = "romance"           # 浪漫关系
    FRIENDSHIP = "friendship"     # 友谊信任
    NEGATIVE = "negative"         # 负面关系
    SPECIAL = "special"           # 特殊关系


@dataclass
class RelationshipEventDef:
    """
    关系事件定义
    """
    event_type: str                           # 事件类型标识
    category: EventCategory                   # 事件类别
    display_name: str                         # 中文显示名
    
    # 触发条件阈值
    required_affinity: int = 0                # 亲密度阈值（正向事件用>=，负向用<=）
    required_trust: int = 0                   # 信任度阈值
    required_respect: int = 0                 # 尊重度阈值
    min_interaction_count: int = 0            # 最少互动次数
    
    # 特殊条件
    require_orientation_match: bool = False   # 需要性倾向匹配
    require_single: bool = False              # 需要单身状态
    require_dating: bool = False              # 需要恋爱状态
    require_married: bool = False             # 需要已婚状态
    require_external_obstacle: bool = False   # 需要有外部阻力
    require_high_competence: bool = False     # 需要对方高能力
    require_high_influence: bool = False      # 需要对方高影响力
    check_peak_affinity: bool = False         # 需要检查历史最高亲密度
    peak_affinity_threshold: int = 60         # 曾经亲密度阈值
    is_negative_threshold: bool = False       # 阈值是否为负向（<=）
    
    # 时代适配
    era_variations: Dict[str, str] = field(default_factory=dict)
    
    # 事件描述模板
    description_template: str = ""
    
    def get_era_name(self, era: str, language: str = "zh") -> str:
        """
        根据时代获取事件名称
        
        Args:
            era: 时代标识
            language: 语言
        
        Returns:
            适配时代的事件名称
        """
        # 时代映射
        era_key = self._normalize_era(era)
        
        if era_key in self.era_variations:
            return self.era_variations[era_key]
        
        # 默认返回显示名
        return self.display_name
    
    def _normalize_era(self, era: str) -> str:
        """标准化时代标识"""
        era_lower = era.lower() if era else ""
        
        # 现代
        if any(k in era_lower for k in ["modern", "contemporary", "2000", "2010", "2020", "现代", "当代"]):
            return "modern"
        # 古代中国
        if any(k in era_lower for k in ["ancient_china", "tang", "song", "ming", "qing", "han", 
                                         "唐", "宋", "明", "清", "汉", "古代", "战国", "三国"]):
            return "ancient_china"
        # 古代西方
        if any(k in era_lower for k in ["medieval", "renaissance", "ancient_west", "roman", "greek",
                                         "中世纪", "罗马", "希腊"]):
            return "ancient_west"
        # 近代
        if any(k in era_lower for k in ["近代", "民国", "1900", "1800", "victorian"]):
            return "modern_early"
        
        return "modern"  # 默认现代


# ==================== 事件定义 ====================

RELATIONSHIP_EVENTS: Dict[str, RelationshipEventDef] = {
    # ===== 浪漫关系事件 =====
    "romance_spark": RelationshipEventDef(
        event_type="romance_spark",
        category=EventCategory.ROMANCE,
        display_name="恋爱萌芽",
        required_affinity=75,
        required_trust=60,
        require_orientation_match=True,
        require_single=True,
        era_variations={
            "modern": "开始约会",
            "modern_early": "情愫暗生",
            "ancient_china": "定情",
            "ancient_west": "Courtship begins",
        },
        description_template="经过长期相处，{character}与主角之间产生了微妙的情感变化，双方都感受到了彼此的心意。"
    ),
    
    "marriage_proposal": RelationshipEventDef(
        event_type="marriage_proposal",
        category=EventCategory.ROMANCE,
        display_name="求婚/成婚",
        required_affinity=85,
        required_trust=80,
        require_dating=True,
        era_variations={
            "modern": "求婚",
            "modern_early": "提亲",
            "ancient_china": "成亲",
            "ancient_west": "Marriage proposal",
        },
        description_template="{character}与主角的感情水到渠成，终于迎来了人生的重要时刻。"
    ),
    
    "breakup": RelationshipEventDef(
        event_type="breakup",
        category=EventCategory.ROMANCE,
        display_name="分手/离婚",
        required_affinity=25,
        required_trust=20,
        require_dating=True,  # 需要恋爱或已婚状态
        is_negative_threshold=True,
        era_variations={
            "modern": "分手",
            "modern_early": "解除婚约",
            "ancient_china": "和离",
            "ancient_west": "Separation",
        },
        description_template="曾经的情感已经消磨殆尽，{character}与主角之间的关系走向了终点。"
    ),
    
    "elopement": RelationshipEventDef(
        event_type="elopement",
        category=EventCategory.ROMANCE,
        display_name="私奔",
        required_affinity=90,
        required_trust=85,
        require_orientation_match=True,
        require_external_obstacle=True,
        era_variations={
            "modern": "私奔",
            "modern_early": "出走",
            "ancient_china": "私奔",
            "ancient_west": "Elopement",
        },
        description_template="尽管有重重阻力，{character}与主角决定不顾一切，远走高飞。"
    ),
    
    # ===== 友谊信任事件 =====
    "sworn_siblings": RelationshipEventDef(
        event_type="sworn_siblings",
        category=EventCategory.FRIENDSHIP,
        display_name="结拜",
        required_affinity=85,
        required_trust=80,
        required_respect=75,
        era_variations={
            "modern": "结拜",
            "modern_early": "结为异姓兄弟/姐妹",
            "ancient_china": "义结金兰",
            "ancient_west": "Blood oath",
        },
        description_template="{character}与主角肝胆相照，决定结为异姓兄弟（姐妹），誓言生死与共。"
    ),
    
    "soulmate": RelationshipEventDef(
        event_type="soulmate",
        category=EventCategory.FRIENDSHIP,
        display_name="知己",
        required_affinity=80,
        required_trust=75,
        min_interaction_count=10,
        era_variations={
            "modern": "成为挚友",
            "modern_early": "引为知己",
            "ancient_china": "知己",
            "ancient_west": "Soulmate",
        },
        description_template="经过无数次的交流与陪伴，{character}已成为主角生命中不可或缺的知己。"
    ),
    
    "business_partner": RelationshipEventDef(
        event_type="business_partner",
        category=EventCategory.FRIENDSHIP,
        display_name="创业合伙",
        required_trust=70,
        require_high_competence=True,
        era_variations={
            "modern": "创业合伙",
            "modern_early": "合伙经商",
            "ancient_china": "合股经营",
            "ancient_west": "Business partnership",
        },
        description_template="{character}与主角志同道合，决定携手共创事业。"
    ),
    
    "entrust": RelationshipEventDef(
        event_type="entrust",
        category=EventCategory.FRIENDSHIP,
        display_name="托付",
        required_trust=90,
        required_respect=85,
        era_variations={
            "modern": "托付后事",
            "modern_early": "托付重任",
            "ancient_china": "托付后事",
            "ancient_west": "Entrusting legacy",
        },
        description_template="{character}对主角无比信任，将最重要的事情托付给了主角。"
    ),
    
    # ===== 负面关系事件 =====
    "become_enemy": RelationshipEventDef(
        event_type="become_enemy",
        category=EventCategory.NEGATIVE,
        display_name="反目成仇",
        required_affinity=15,
        is_negative_threshold=True,
        check_peak_affinity=True,
        peak_affinity_threshold=60,
        era_variations={
            "modern": "反目成仇",
            "modern_early": "反目成仇",
            "ancient_china": "割袍断义",
            "ancient_west": "Became enemies",
        },
        description_template="曾经的情谊已成往事，{character}与主角之间只剩下怨恨与敌意。"
    ),
    
    "betrayal": RelationshipEventDef(
        event_type="betrayal",
        category=EventCategory.NEGATIVE,
        display_name="背叛",
        required_trust=20,
        is_negative_threshold=True,
        era_variations={
            "modern": "背叛",
            "modern_early": "出卖",
            "ancient_china": "背主",
            "ancient_west": "Betrayal",
        },
        description_template="{character}在关键时刻选择了背叛，给主角造成了巨大的伤害。"
    ),
    
    "severance": RelationshipEventDef(
        event_type="severance",
        category=EventCategory.NEGATIVE,
        display_name="决裂",
        required_affinity=10,
        required_trust=15,
        is_negative_threshold=True,
        era_variations={
            "modern": "绝交",
            "modern_early": "断绝往来",
            "ancient_china": "恩断义绝",
            "ancient_west": "Complete severance",
        },
        description_template="{character}与主角之间的关系已经无法挽回，从此形同陌路。"
    ),
    
    "sabotage": RelationshipEventDef(
        event_type="sabotage",
        category=EventCategory.NEGATIVE,
        display_name="暗中陷害",
        required_affinity=25,
        required_trust=30,
        is_negative_threshold=True,
        require_high_influence=True,
        era_variations={
            "modern": "暗中使坏",
            "modern_early": "暗中陷害",
            "ancient_china": "暗施毒计",
            "ancient_west": "Sabotage",
        },
        description_template="{character}暗中对主角下手，企图破坏主角的前程或声誉。"
    ),
    
    # ===== 特殊关系事件 =====
    "apprenticeship": RelationshipEventDef(
        event_type="apprenticeship",
        category=EventCategory.SPECIAL,
        display_name="师徒传承",
        required_respect=75,
        require_high_competence=True,
        era_variations={
            "modern": "成为导师/学徒",
            "modern_early": "拜师学艺",
            "ancient_china": "拜师",
            "ancient_west": "Apprenticeship",
        },
        description_template="{character}被主角的潜力所打动，决定倾囊相授，传授毕生所学。"
    ),
    
    "patron": RelationshipEventDef(
        event_type="patron",
        category=EventCategory.SPECIAL,
        display_name="贵人提携",
        required_affinity=70,
        require_high_influence=True,
        era_variations={
            "modern": "推荐提携",
            "modern_early": "提携举荐",
            "ancient_china": "贵人相助",
            "ancient_west": "Patronage",
        },
        description_template="{character}欣赏主角的才华，决定动用自己的人脉和资源来帮助主角。"
    ),
    
    "childbirth": RelationshipEventDef(
        event_type="childbirth",
        category=EventCategory.SPECIAL,
        display_name="生育子女",
        required_affinity=90,
        require_married=True,
        era_variations={
            "modern": "迎来新生命",
            "modern_early": "添丁进口",
            "ancient_china": "添丁",
            "ancient_west": "Childbirth",
        },
        description_template="{character}与主角的爱情结晶即将到来，家庭将迎来新成员。"
    ),
}


def get_event_by_type(event_type: str) -> Optional[RelationshipEventDef]:
    """根据事件类型获取事件定义"""
    return RELATIONSHIP_EVENTS.get(event_type)


def get_events_by_category(category: EventCategory) -> List[RelationshipEventDef]:
    """根据类别获取所有事件"""
    return [e for e in RELATIONSHIP_EVENTS.values() if e.category == category]


def get_all_event_types() -> List[str]:
    """获取所有事件类型"""
    return list(RELATIONSHIP_EVENTS.keys())
