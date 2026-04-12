"""ForeshadowingTechniqueLibrary + HookInjector 伏笔技法库与钩子注入。

L3 创意增强层 - 伏笔回收技法匹配与选项钩子注入。
支持 4 种基础伏笔类型 × 风格变体回收。
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.ai.narrative.style_manifest import StyleManifest, get_style

logger = logging.getLogger(__name__)


@dataclass
class RecoveryTechnique:
    """伏笔回收技巧。"""

    name: str = ""
    description: str = ""
    prompt_hint: str = ""
    style: str = ""  # 关联风格标识


class ForeshadowingTechniqueLibrary:
    """伏笔技法库，管理 4 种基础类型的回收技巧及风格变体。"""

    TECHNIQUE_MAP: Dict[str, RecoveryTechnique] = {
        "item": RecoveryTechnique(
            name="功能反转",
            description="物品在新场景中展现意外用途",
            prompt_hint="让此物品在当前场景中发挥出乎意料的新功能，揭示其隐藏价值。",
        ),
        "dialogue": RecoveryTechnique(
            name="弦外之音",
            description="早期对话的深层含义在此刻揭示",
            prompt_hint="回顾早期对话中的关键台词，在当前情节中揭示其真正含义。",
        ),
        "character": RecoveryTechnique(
            name="成长映照",
            description="人物当前行为与早期伏笔形成对照",
            prompt_hint="让人物的当前行为与早期表现形成鲜明对比，体现成长或转变。",
        ),
        "event": RecoveryTechnique(
            name="因果延迟",
            description="早期事件的后果终于显现",
            prompt_hint="让早期事件的连锁反应在此刻爆发，揭示因果链条。",
        ),
    }

    # 风格变体回收方式
    STYLE_VARIANTS: Dict[str, Dict] = {
        "chinese_classic": {
            "name": "草蛇灰线",
            "description": "以含蓄隐晦的方式回收伏笔，讲究'伏脉千里'的叙事艺术",
            "prompt_hint": "以草蛇灰线之法，让伏笔如暗流涌动般自然浮现，不着痕迹地揭示前因。",
        },
        "western": {
            "name": "麦格芬揭露",
            "description": "以戏剧性的方式揭露关键物件/信息的真正意义",
            "prompt_hint": "以充满戏剧张力的方式揭示这一伏笔的真正意义，制造震撼的揭露时刻。",
        },
        "honkaku": {
            "name": "线索伏笔",
            "description": "以严谨的逻辑链条回收伏笔，讲究公平推理",
            "prompt_hint": "以严密的逻辑推理回收此伏笔，确保读者回顾时能发现线索一直存在。",
        },
    }

    DEFAULT_MAX_DORMANT_WEEKS = 8

    def match_technique(self, foreshadowing: Dict) -> RecoveryTechnique:
        """根据伏笔类型匹配回收技巧。"""
        try:
            seed_type = foreshadowing.get("type", "")
            technique = self.TECHNIQUE_MAP.get(seed_type)
            if technique:
                return technique
            # 未知类型返回默认
            logger.warning("Unknown foreshadowing type: %s, using default.", seed_type)
            return RecoveryTechnique(
                name="通用回收",
                description="以自然的方式将伏笔融入当前情节",
                prompt_hint="将此伏笔自然地融入当前场景中。",
            )
        except Exception as e:
            logger.warning("Error in match_technique: %s", e)
            return RecoveryTechnique(name="通用回收")

    def get_style_recovery(
        self, foreshadowing: Dict, style: str = ""
    ) -> RecoveryTechnique:
        """根据伏笔类型+风格匹配带风格变体的回收技巧。"""
        try:
            variant = self.STYLE_VARIANTS.get(style)
            if variant:
                return RecoveryTechnique(
                    name=variant["name"],
                    description=variant["description"],
                    prompt_hint=variant["prompt_hint"],
                    style=style,
                )
            # 无匹配风格时，退回基础技巧
            base = self.match_technique(foreshadowing)
            base.style = style
            return base
        except Exception as e:
            logger.warning("Error in get_style_recovery: %s", e)
            return RecoveryTechnique(name="通用回收", style=style)

    def build_recovery_hint(
        self, foreshadowing: Dict, style: str = ""
    ) -> str:
        """生成伏笔回收的 Prompt 提示。"""
        try:
            name = foreshadowing.get("name", "未知伏笔")
            description = foreshadowing.get("description", "")
            seed_type = foreshadowing.get("type", "")

            # 获取风格回收技巧
            if style:
                technique = self.get_style_recovery(foreshadowing, style)
            else:
                technique = self.match_technique(foreshadowing)

            hint = (
                f"【伏笔回收】{name}\n"
                f"伏笔内容：{description}\n"
                f"回收技法：{technique.name} - {technique.description}\n"
                f"提示：{technique.prompt_hint}"
            )
            return hint
        except Exception as e:
            logger.warning("Error in build_recovery_hint: %s", e)
            return f"请回收伏笔：{foreshadowing.get('name', '未知')}"

    def check_overdue(
        self,
        foreshadowings: List[Dict],
        current_week: int,
        max_dormant_weeks: Optional[int] = None,
    ) -> List[str]:
        """检查超期未回收的伏笔，返回提醒字符串列表。"""
        if max_dormant_weeks is None:
            max_dormant_weeks = self.DEFAULT_MAX_DORMANT_WEEKS
        try:
            if not foreshadowings:
                return []

            reminders = []
            for seed in foreshadowings:
                planted_week = seed.get("planted_week", current_week)
                dormant = current_week - planted_week
                if dormant > max_dormant_weeks:
                    name = seed.get("name", "未知伏笔")
                    reminders.append(
                        f"伏笔「{name}」已埋设 {dormant} 周（超过 {max_dormant_weeks} 周上限），"
                        f"建议尽快回收或明确放弃。"
                    )
            return reminders
        except Exception as e:
            logger.warning("Error in check_overdue: %s", e)
            return []


class HookInjector:
    """在选项中植入信息缺口钩子，激发玩家好奇心。"""

    # 钩子模板
    HOOK_TEMPLATES = [
        "（你隐约感到这条路上藏着某个秘密……）",
        "（直觉告诉你，这个选择背后还有未知的故事。）",
        "（一个模糊的记忆闪过脑海，似乎与此有关……）",
    ]

    def inject_hooks(
        self, options: Optional[List[Dict]], context: Optional[str] = None
    ) -> List[Dict]:
        """在选项文本中植入信息缺口钩子。"""
        try:
            if options is None:
                return []

            if not options:
                return []

            enhanced = []
            for i, opt in enumerate(options):
                new_opt = dict(opt)  # shallow copy
                # 为第一个有 text 的选项注入钩子
                if i == 0 and context:
                    new_opt["hook"] = f"（{context}……这条路似乎与之相关。）"
                    new_opt["curiosity_gap"] = True
                elif i == 0:
                    new_opt["hook"] = self.HOOK_TEMPLATES[0]
                    new_opt["curiosity_gap"] = True
                enhanced.append(new_opt)

            return enhanced
        except Exception as e:
            logger.warning("Error in inject_hooks: %s, returning original options.", e)
            if options is None:
                return []
            return list(options) if options else []
