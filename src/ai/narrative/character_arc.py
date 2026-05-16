"""CharacterArcEngine 人物弧光追踪引擎。

5阶段弧光模型：稳态→触发→挣扎→转折→新稳态
支持风格感知：中国古典=天命觉醒弧，西方=英雄之旅弧，日本=无常接受弧
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.ai.narrative.style_manifest import StyleManifest

logger = logging.getLogger(__name__)

# ==================== Phase Definitions ====================

DEFAULT_PHASES = ["稳态", "触发", "挣扎", "转折", "新稳态"]

STYLE_ARC_TYPES = {
    "chinese_classic": "天命觉醒",
    "western": "英雄之旅",
    "japanese": "无常接受",
}


@dataclass
class ArcPhase:
    """弧光阶段。"""

    name: str = ""
    index: int = 0


@dataclass
class CharacterArc:
    """角色弧光数据。"""

    character_name: str = ""
    initial_flaw: str = ""
    desire: str = ""
    arc_type: str = "成长"
    current_phase: ArcPhase = field(
        default_factory=lambda: ArcPhase(name="稳态", index=0)
    )
    phases: List[ArcPhase] = field(default_factory=list)
    growth_score: float = 0.0
    phase_history: List[str] = field(default_factory=list)
    endpoint: str = ""
    personality: Dict[str, float] = field(default_factory=dict)


class CharacterArcEngine:
    """人物弧光追踪引擎 - 5阶段弧光模型。"""

    def __init__(self, style: Optional[StyleManifest] = None):
        self.style = style
        self.arcs: Dict[str, CharacterArc] = {}

    def create_arc(
        self, character_data: Optional[dict], style: Optional[str] = None
    ) -> CharacterArc:
        """创建角色弧光。"""
        try:
            if not character_data or not isinstance(character_data, dict):
                logger.warning("Invalid character data, creating default arc.")
                return self._create_default_arc(style)

            name = character_data.get("name", "未知角色")
            flaw = character_data.get("initial_flaw", "")
            desire = character_data.get("desire", "")

            arc_type = STYLE_ARC_TYPES.get(style, "成长") if style else "成长"
            phases = [ArcPhase(name=p, index=i) for i, p in enumerate(DEFAULT_PHASES)]

            arc = CharacterArc(
                character_name=name,
                initial_flaw=flaw,
                desire=desire,
                arc_type=arc_type,
                current_phase=phases[0],
                phases=phases,
                growth_score=0.0,
                phase_history=["稳态"],
                endpoint=f"克服{flaw}，实现{desire}" if flaw and desire else "完成成长",
                personality={"勇气": 0.5, "智慧": 0.5, "仁慈": 0.5},
            )

            self.arcs[name] = arc
            logger.info("Created arc for character '%s' (type=%s)", name, arc_type)
            return arc
        except Exception as e:
            logger.warning("Error creating arc: %s", e)
            return self._create_default_arc(style)

    def process_event(self, arc: CharacterArc, event: dict) -> Optional[CharacterArc]:
        """处理事件，判断是否推进阶段。"""
        try:
            if arc is None or event is None:
                logger.warning("Invalid arc or event for process_event.")
                return arc

            intensity = event.get("intensity", 0.5)
            current_idx = arc.current_phase.index

            if intensity >= 0.5 and current_idx < len(arc.phases) - 1:
                next_phase = arc.phases[current_idx + 1]
                arc.current_phase = next_phase
                arc.phase_history.append(next_phase.name)
                arc.growth_score = min(1.0, arc.growth_score + 0.2)
                logger.info(
                    "Arc '%s' advanced to phase '%s'",
                    arc.character_name,
                    next_phase.name,
                )

            return arc
        except Exception as e:
            logger.warning("Error processing event: %s", e)
            return arc

    def compute_personality_shift(
        self, arc: CharacterArc, event: dict
    ) -> Dict[str, float]:
        """计算性格维度微小偏移。"""
        try:
            if arc is None or event is None:
                return {}

            intensity = event.get("intensity", 0.3)
            shift = {}
            for dim in arc.personality:
                delta = intensity * 0.2
                if arc.current_phase.name in ("触发", "挣扎"):
                    delta = -delta  # 困境中某些维度下降
                shift[dim] = round(max(-0.3, min(0.3, delta)), 3)

            return shift
        except Exception as e:
            logger.warning("Error computing personality shift: %s", e)
            return {}

    def generate_constraint(self, arc: Optional[CharacterArc]) -> str:
        """生成弧光进度约束注入Prompt。"""
        try:
            if arc is None:
                return "角色弧光信息不可用，请自由发展角色。"

            phase_name = arc.current_phase.name
            name = arc.character_name or "角色"
            flaw = arc.initial_flaw
            desire = arc.desire

            parts = [f"【角色弧光约束】{name}当前处于「{phase_name}」阶段。"]

            if phase_name == "稳态":
                parts.append(f"角色尚处于日常状态，性格缺陷「{flaw}」尚未被触发。")
            elif phase_name == "触发":
                parts.append("角色刚经历重大事件冲击，内心开始动摇。")
            elif phase_name == "挣扎":
                parts.append(f"角色在「{flaw}」与成长之间反复挣扎。")
            elif phase_name == "转折":
                parts.append("角色即将迎来关键转折，请安排突破性场景。")
            elif phase_name == "新稳态":
                parts.append(
                    f"角色已完成成长弧，新的自我认知已建立，朝向「{desire}」迈进。"
                )

            return " ".join(parts)
        except Exception as e:
            logger.warning("Error generating constraint: %s", e)
            return "角色弧光约束生成失败，请自由发展。"

    def to_state_dict(self) -> Dict:
        """序列化为可存入PlayerState.character_arc_state的dict。"""
        try:
            result = {}
            for name, arc in self.arcs.items():
                result[name] = {
                    "character_name": arc.character_name,
                    "initial_flaw": arc.initial_flaw,
                    "desire": arc.desire,
                    "arc_type": arc.arc_type,
                    "current_phase": arc.current_phase.name,
                    "current_phase_index": arc.current_phase.index,
                    "growth_score": arc.growth_score,
                    "phase_history": arc.phase_history,
                    "endpoint": arc.endpoint,
                    "personality": arc.personality,
                }
            return result
        except Exception as e:
            logger.warning("Error serializing arc state: %s", e)
            return {}

    @classmethod
    def from_state_dict(
        cls, data: Dict, style: Optional[StyleManifest] = None
    ) -> "CharacterArcEngine":
        """从PlayerState.character_arc_state恢复。"""
        engine = cls(style=style)
        try:
            if not data or not isinstance(data, dict):
                return engine

            for name, arc_data in data.items():
                if not isinstance(arc_data, dict):
                    continue
                phases = [
                    ArcPhase(name=p, index=i) for i, p in enumerate(DEFAULT_PHASES)
                ]
                phase_idx = arc_data.get("current_phase_index", 0)
                phase_idx = max(0, min(phase_idx, len(phases) - 1))

                arc = CharacterArc(
                    character_name=arc_data.get("character_name", name),
                    initial_flaw=arc_data.get("initial_flaw", ""),
                    desire=arc_data.get("desire", ""),
                    arc_type=arc_data.get("arc_type", "成长"),
                    current_phase=phases[phase_idx],
                    phases=phases,
                    growth_score=arc_data.get("growth_score", 0.0),
                    phase_history=arc_data.get("phase_history", []),
                    endpoint=arc_data.get("endpoint", ""),
                    personality=arc_data.get("personality", {}),
                )
                engine.arcs[name] = arc
        except Exception as e:
            logger.warning("Error restoring arc state: %s", e)
        return engine

    def _create_default_arc(self, style: Optional[str] = None) -> CharacterArc:
        """创建默认弧光。"""
        arc_type = STYLE_ARC_TYPES.get(style, "成长") if style else "成长"
        phases = [ArcPhase(name=p, index=i) for i, p in enumerate(DEFAULT_PHASES)]
        return CharacterArc(
            character_name="未知角色",
            arc_type=arc_type,
            current_phase=phases[0],
            phases=phases,
            endpoint="完成成长",
            personality={"勇气": 0.5, "智慧": 0.5, "仁慈": 0.5},
        )
