"""场景风格管理器 - 颜色调板和视觉风格约束.

通过预定义的色彩调板和风格参考，确保多场景之间的视觉一致性。
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class MoodType(str, Enum):
    """情感基调类型."""
    WARM_DAILY = "warm_daily"           # 温馨日常
    TENSE_CONFLICT = "tense_conflict"   # 紧张冲突
    ROMANTIC = "romantic"               # 浪漫
    MYSTERIOUS = "mysterious"           # 神秘
    JOYFUL = "joyful"                   # 欢快
    MELANCHOLY = "melancholy"           # 忧郁
    EPIC = "epic"                       # 史诗
    HORROR = "horror"                   # 恐怖


@dataclass
class ColorPalette:
    """颜色调板定义."""
    name: str
    description: str                    # 调板描述
    primary_colors: List[str]           # 主色调
    secondary_colors: List[str]        # 辅助色
    lighting: str                       # 光线描述
    saturation: str                     # 饱和度级别：高/中/低
    contrast: str                       # 对比度级别：高/中/低
    atmosphere: str                     # 整体氛围

    def build_prompt_segment(self) -> str:
        """构建用于提示词的调板描述."""
        primary = "、".join(self.primary_colors)
        secondary = "、".join(self.secondary_colors) if self.secondary_colors else ""

        parts = [
            f"色调：以{primary}为主",
        ]
        if secondary:
            parts.append(f"辅以{secondary}")
        parts.extend([
            f"光线：{self.lighting}",
            f"饱和度：{self.saturation}",
            f"对比度：{self.contrast}",
            f"氛围：{self.atmosphere}",
        ])
        return "。".join(parts)


class SceneStyleManager:
    """场景风格管理器 - 管理颜色调板和视觉风格."""

    # 预定义调板
    PALETTES: Dict[MoodType, ColorPalette] = {
        MoodType.WARM_DAILY: ColorPalette(
            name="温馨日常",
            description="适合日常生活场景，给人温暖舒适的感觉",
            primary_colors=["米黄色", "橙棕色", "暖白色"],
            secondary_colors=["浅木色", "米色"],
            lighting="柔和的自然光，金色阳光，温暖的室内灯光",
            saturation="适中",
            contrast="低到中",
            atmosphere="温馨、舒适、平和",
        ),
        MoodType.TENSE_CONFLICT: ColorPalette(
            name="紧张冲突",
            description="适合冲突、对抗场景，营造紧张感",
            primary_colors=["蓝灰色", "深绿色", "铁青色"],
            secondary_colors=["暗红色", "黑色"],
            lighting="强烈的明暗对比，戏剧性的阴影，冷硬的光线",
            saturation="低",
            contrast="高",
            atmosphere="紧张、压抑、对立",
        ),
        MoodType.ROMANTIC: ColorPalette(
            name="浪漫",
            description="适合浪漫、温情场景",
            primary_colors=["粉紫色", "玫瑰金", "淡粉色"],
            secondary_colors=["薰衣草紫", "香槟色"],
            lighting="柔和的散射光，暖色边缘光，梦幻光晕",
            saturation="中高",
            contrast="低",
            atmosphere="浪漫、温柔、梦幻",
        ),
        MoodType.MYSTERIOUS: ColorPalette(
            name="神秘",
            description="适合悬疑、未知场景",
            primary_colors=["青蓝色", "深紫色", "墨绿色"],
            secondary_colors=["银色", "暗金色"],
            lighting="低饱和度的光源，高对比度的阴影，雾感",
            saturation="低",
            contrast="高",
            atmosphere="神秘、未知、悬疑",
        ),
        MoodType.JOYFUL: ColorPalette(
            name="欢快",
            description="适合欢乐、庆祝场景",
            primary_colors=["明黄色", "天蓝色", "草绿色"],
            secondary_colors=["橙色", "粉红色"],
            lighting="明亮的自然光，充足的曝光",
            saturation="高",
            contrast="中",
            atmosphere="欢快、活力、明亮",
        ),
        MoodType.MELANCHOLY: ColorPalette(
            name="忧郁",
            description="适合悲伤、怀念场景",
            primary_colors=["灰蓝色", "褐色", "暗黄色"],
            secondary_colors=["灰色", "深棕色"],
            lighting="柔和的侧光，黄昏光线，漫射光",
            saturation="低到中",
            contrast="中",
            atmosphere="忧郁、沉思、怀旧",
        ),
        MoodType.EPIC: ColorPalette(
            name="史诗",
            description="适合宏大、壮观场景",
            primary_colors=["金色", "深红色", "皇家蓝"],
            secondary_colors=["古铜色", "象牙白"],
            lighting="戏剧性的顶光，神圣光效，强烈的光影",
            saturation="高",
            contrast="高",
            atmosphere="宏大、庄严、史诗感",
        ),
        MoodType.HORROR: ColorPalette(
            name="恐怖",
            description="适合恐怖、惊悚场景",
            primary_colors=["暗红色", "黑色", "深绿色"],
            secondary_colors=["惨白色", "暗紫色"],
            lighting="不均匀的光源，强烈的阴影，局部照明",
            saturation="低",
            contrast="极高",
            atmosphere="恐怖、压抑、不安",
        ),
    }

    def __init__(self):
        """初始化风格管理器."""
        self._game_palettes: Dict[int, MoodType] = {}  # game_id -> 当前调板
        self._style_reference_urls: Dict[int, str] = {}  # game_id -> 风格参考图URL

    def get_palette(self, mood: MoodType) -> ColorPalette:
        """获取指定情感基调的调板.

        Args:
            mood: 情感基调类型

        Returns:
            颜色调板
        """
        return self.PALETTES.get(mood, self.PALETTES[MoodType.WARM_DAILY])

    def detect_mood_from_story(self, story_text: str) -> MoodType:
        """从故事文本中检测情感基调.

        Args:
            story_text: 故事文本

        Returns:
            检测到的情感基调
        """
        text = story_text.lower()

        # 关键词映射
        mood_keywords = {
            MoodType.TENSE_CONFLICT: ["冲突", "争吵", "对抗", "紧张", "危险", "危机", "愤怒", "打架", "对峙"],
            MoodType.ROMANTIC: ["浪漫", "表白", "约会", "心动", "暧昧", "亲密", "温柔", "爱情"],
            MoodType.MYSTERIOUS: ["神秘", "未知", "悬疑", "谜", "秘密", "诡异", "奇怪", "离奇"],
            MoodType.JOYFUL: ["开心", "欢乐", "庆祝", "胜利", "成功", "喜悦", "兴奋", "派对"],
            MoodType.MELANCHOLY: ["悲伤", "失落", "离别", "怀念", "孤独", "惆怅", "遗憾", "分手"],
            MoodType.HORROR: ["恐怖", "惊悚", "害怕", "恐惧", "鬼魂", "死亡", "血腥", "噩梦"],
            MoodType.EPIC: ["宏大", "壮观", "决战", "命运", "历史", "传说", "英雄", "伟大"],
        }

        # 统计每种基调的匹配次数
        scores = {}
        for mood, keywords in mood_keywords.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[mood] = score

        if scores:
            # 返回得分最高的基调
            return max(scores.items(), key=lambda x: x[1])[0]

        # 默认返回温馨日常
        return MoodType.WARM_DAILY

    def set_game_palette(self, game_id: int, mood: MoodType):
        """为游戏设置当前调板.

        Args:
            game_id: 游戏ID
            mood: 情感基调
        """
        self._game_palettes[game_id] = mood
        logger.info(f"Set palette for game {game_id} to {mood.value}")

    def get_game_palette(self, game_id: int) -> ColorPalette:
        """获取游戏当前使用的调板.

        Args:
            game_id: 游戏ID

        Returns:
            颜色调板
        """
        mood = self._game_palettes.get(game_id, MoodType.WARM_DAILY)
        return self.get_palette(mood)

    def set_style_reference(self, game_id: int, reference_url: str):
        """设置风格参考图URL.

        Args:
            game_id: 游戏ID
            reference_url: 风格参考图URL
        """
        self._style_reference_urls[game_id] = reference_url
        logger.info(f"Set style reference for game {game_id}")

    def get_style_reference(self, game_id: int) -> Optional[str]:
        """获取风格参考图URL.

        Args:
            game_id: 游戏ID

        Returns:
            风格参考图URL或None
        """
        return self._style_reference_urls.get(game_id)

    def build_scene_prompt_with_style(
        self,
        scene_desc: str,
        era: str,
        mood: Optional[MoodType] = None,
        game_id: Optional[int] = None,
    ) -> str:
        """构建带有风格约束的场景提示词.

        Args:
            scene_desc: 场景描述
            era: 时代背景
            mood: 情感基调（可选，不提供则使用游戏当前设置）
            game_id: 游戏ID（可选，用于获取游戏当前设置）

        Returns:
            完整的场景提示词
        """
        # 确定使用的调板
        if mood is None and game_id is not None:
            palette = self.get_game_palette(game_id)
        elif mood is not None:
            palette = self.get_palette(mood)
        else:
            palette = self.get_palette(MoodType.WARM_DAILY)

        # 构建提示词
        prompt = f"""电影感故事场景插画。
时代背景：{era}。
场景：{scene_desc}

视觉风格约束（必须严格遵守）：
{palette.build_prompt_segment()}

整体色彩饱和度保持一致，画面色调统一，光影风格连贯。"""

        return prompt

    def apply_temporal_progression(
        self,
        game_id: int,
        week: int,
        total_weeks: int,
    ) -> ColorPalette:
        """根据游戏进度应用时序色彩变化.

        随着游戏进行，色调会逐渐变化，反映时间的流逝。

        Args:
            game_id: 游戏ID
            week: 当前周数
            total_weeks: 总周数

        Returns:
            调整后的颜色调板
        """
        progress = week / max(total_weeks, 1)

        # 根据进度选择基础调板
        if progress < 0.25:
            base_mood = MoodType.WARM_DAILY
            season_hint = "早春，万物复苏，嫩绿色调"
        elif progress < 0.5:
            base_mood = MoodType.JOYFUL
            season_hint = "盛夏，阳光明媚，高饱和度"
        elif progress < 0.75:
            base_mood = MoodType.MELANCHOLY
            season_hint = "深秋，金黄色落叶，温暖而略带忧伤"
        else:
            base_mood = MoodType.MYSTERIOUS
            season_hint = "初冬，寒意初现，冷色调，清冽的空气感"

        palette = self.get_palette(base_mood)

        # 创建调整后的调板
        adjusted = ColorPalette(
            name=f"{palette.name} (第{week}周)",
            description=f"{palette.description}。{season_hint}",
            primary_colors=palette.primary_colors,
            secondary_colors=palette.secondary_colors,
            lighting=palette.lighting,
            saturation=palette.saturation,
            contrast=palette.contrast,
            atmosphere=f"{palette.atmosphere}。{season_hint}",
        )

        return adjusted


# 全局风格管理器实例
style_manager = SceneStyleManager()
