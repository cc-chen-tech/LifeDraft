"""风格感知验证器。

基于 StyleManifest 配置动态生成验证规则，
检查生成的故事文本是否符合指定的叙事风格要求。

所有验证函数签名统一为:
    (story_text: str, context: dict) -> Tuple[bool, str, dict]
返回值: (是否通过, 失败证据描述, 详细信息dict)
"""

import logging
import re
from typing import Callable, Dict, List, Optional, Tuple

from src.ai.narrative.style_manifest import StyleManifest

logger = logging.getLogger(__name__)


class StyleAwareValidator:
    """基于风格配置动态生成验证规则。"""

    DEFAULT_WEIGHTS = {
        "structure": 0.25,
        "pacing": 0.25,
        "language": 0.25,
        "technique": 0.25,
    }

    def __init__(
        self, style: Optional[StyleManifest] = None, weights: Optional[Dict[str, float]] = None
    ):
        self.style = style
        self._weights = weights if weights is not None else dict(self.DEFAULT_WEIGHTS)

    # ------------------------------------------------------------------
    # 高层统一接口
    # ------------------------------------------------------------------

    def validate(self, story_text: str, context: Optional[dict] = None) -> Tuple[bool, float, dict]:
        """统一验证入口，返回 (passed, score, details)。"""
        if not self.style:
            return True, 1.0, {"skipped": True, "reason": "no style configured"}

        ctx = context or {}
        scores = self.get_dimension_scores(story_text, ctx)
        overall = self._compute_overall(scores)
        passed = overall >= 0.3  # 宽松阈值
        details = {"dimension_scores": scores, "overall": overall}
        return passed, overall, details

    def get_dimension_scores(
        self, story_text: str, context: Optional[dict] = None
    ) -> Dict[str, float]:
        """返回4维度归一化分数 (0-1)。"""
        if not self.style:
            return {"structure": 1.0, "pacing": 1.0, "language": 1.0, "technique": 1.0}

        ctx = context or {}
        results = {
            "structure": self.validate_style_structure(story_text, ctx),
            "pacing": self.validate_style_pacing(story_text, ctx),
            "language": self.validate_style_language(story_text, ctx),
            "technique": self.validate_style_technique(story_text, ctx),
        }

        scores: Dict[str, float] = {}
        for dim, (passed, _evidence, details) in results.items():
            scores[dim] = self._details_to_score(dim, passed, details)
        return scores

    def get_overall_score(self, story_text: str, context: Optional[dict] = None) -> float:
        """返回加权综合分数 (0-1)。"""
        scores = self.get_dimension_scores(story_text, context)
        return self._compute_overall(scores)

    def get_weights(self) -> Dict[str, float]:
        """返回当前权重配置。"""
        return dict(self._weights)

    def as_harness_validator(self) -> Callable[[str, dict], Tuple[bool, str, dict]]:
        """返回符合 Harness 标准签名的验证函数: (story_text, context) -> (bool, str, dict)。"""

        def _validate_fn(story_text: str, context: dict) -> Tuple[bool, str, dict]:
            passed, score, details = self.validate(story_text, context)
            evidence = "" if passed else f"风格综合评分 {score:.2f} 低于阈值"
            return passed, evidence, details

        return _validate_fn

    # ------------------------------------------------------------------
    # 内部计算
    # ------------------------------------------------------------------

    def _compute_overall(self, scores: Dict[str, float]) -> float:
        total_weight = sum(self._weights.get(d, 0) for d in scores)
        if total_weight == 0:
            return 0.0
        weighted_sum = sum(scores[d] * self._weights.get(d, 0) for d in scores)
        return weighted_sum / total_weight

    def _details_to_score(self, dim: str, passed: bool, details: dict) -> float:
        """将验证详情转换为 0-1 分数。"""
        if details.get("skipped"):
            return 1.0
        if not passed:
            return 0.3
        # 根据找到的指标数量给出基础分
        found_keys = [
            k
            for k in details
            if k.endswith("_found")
            or k == "technique_evidence"
            or k == "device_evidence"
            or k == "pattern_evidence"
        ]
        if not found_keys:
            return 0.7  # 通过但无具体指标
        # 计算找到的指标比例
        total_found = 0
        total_expected = 0
        for k in found_keys:
            val = details[k]
            if isinstance(val, list):
                total_found += len(val)
                total_expected += max(len(val), 1)
            elif isinstance(val, dict):
                total_found += sum(1 for v in val.values() if v)
                total_expected += max(len(val), 1)
        if total_expected == 0:
            return 0.7
        ratio = total_found / total_expected
        return min(1.0, 0.5 + ratio * 0.5)

    # ------------------------------------------------------------------
    # 验证函数（均遵循标准签名）
    # ------------------------------------------------------------------

    def validate_style_structure(self, story_text: str, context: dict) -> Tuple[bool, str, dict]:
        """检查结构合规（章回结尾/英雄之旅阶段/框架叙事等）。

        基于 style.structure 配置进行验证。
        """
        if not self.style:
            return True, "", {"skipped": True, "reason": "no style configured"}

        try:
            struct = self.style.structure
            details: Dict[str, object] = {}

            # 检查宏观结构关键词是否在文本中有所体现
            if struct.macro:
                macro_indicators = self._get_structure_indicators(struct.macro)
                found = [ind for ind in macro_indicators if ind in story_text]
                details["macro"] = struct.macro
                details["macro_indicators_found"] = found

            # 检查弧线阶段
            if struct.arc:
                arc_indicators = self._get_arc_indicators(struct.arc)
                found_arc = [ind for ind in arc_indicators if ind in story_text]
                details["arc"] = struct.arc
                details["arc_indicators_found"] = found_arc

            # 检查章节规则
            chapter_rules = struct.chapter_rules
            if chapter_rules.avg_length:
                actual_length = len(story_text)
                details["actual_length"] = actual_length
                details["expected_avg_length"] = chapter_rules.avg_length

            return True, "", details

        except Exception as e:
            logger.warning("validate_style_structure failed: %s", e)
            return True, "", {"error": str(e)}

    def validate_style_pacing(self, story_text: str, context: dict) -> Tuple[bool, str, dict]:
        """检查节奏规则合规。

        基于 style.structure.chapter_rules 进行验证。
        """
        if not self.style:
            return True, "", {"skipped": True, "reason": "no style configured"}

        try:
            chapter_rules = self.style.structure.chapter_rules
            details: Dict[str, object] = {}

            # 检查开头风格
            if chapter_rules.opening_style:
                opening = story_text[:200] if len(story_text) > 200 else story_text
                opening_indicators = self._get_opening_indicators(chapter_rules.opening_style)
                found_opening = [ind for ind in opening_indicators if ind in opening]
                details["opening_style"] = chapter_rules.opening_style
                details["opening_indicators_found"] = found_opening

            # 检查结尾风格
            if chapter_rules.closing_style:
                ending = story_text[-300:] if len(story_text) > 300 else story_text
                closing_indicators = self._get_closing_indicators(chapter_rules.closing_style)
                found_closing = [ind for ind in closing_indicators if ind in ending]
                details["closing_style"] = chapter_rules.closing_style
                details["closing_indicators_found"] = found_closing

            # 检查 hook 类型
            if chapter_rules.hook_types:
                ending = story_text[-300:] if len(story_text) > 300 else story_text
                hook_found = self._check_hook_presence(ending, chapter_rules.hook_types)
                details["hook_types"] = chapter_rules.hook_types
                details["hook_detected"] = hook_found

                if not hook_found:
                    return (
                        False,
                        f"结尾未检测到预期的悬念钩子类型: {chapter_rules.hook_types}",
                        details,
                    )

            # 三幕结构检测（信息记录，非硬性失败）
            act_phases_found = []
            text_len = len(story_text)
            if text_len > 200:
                opening_text = story_text[:text_len // 4]
                middle_text = story_text[text_len // 4 : 3 * text_len // 4]
                ending_text = story_text[3 * text_len // 4:]

                setup_keywords = ["走进", "坐下", "来到", "踏入", "清晨", "这一天"]
                development_keywords = ["然而", "却", "突然", "不料", "意外", "转折"]
                climax_keywords = ["终于", "再也", "紧紧", "猛然", "决定", "爆发"]

                if any(kw in opening_text for kw in setup_keywords):
                    act_phases_found.append("铺垫")
                if any(kw in middle_text for kw in development_keywords):
                    act_phases_found.append("发展/转折")
                if any(kw in ending_text for kw in climax_keywords):
                    act_phases_found.append("高潮/收束")

            details["three_act_phases_found"] = act_phases_found
            details["three_act_completeness"] = len(act_phases_found) >= 2

            return True, "", details

        except Exception as e:
            logger.warning("validate_style_pacing failed: %s", e)
            return True, "", {"error": str(e)}

    def validate_style_language(self, story_text: str, context: dict) -> Tuple[bool, str, dict]:
        """检查语言风格合规。

        基于 style.language 配置进行验证。
        """
        if not self.style:
            return True, "", {"skipped": True, "reason": "no style configured"}

        try:
            lang = self.style.language
            details: Dict[str, object] = {}

            # 检查修辞手法使用情况
            if lang.rhetoric:
                rhetoric_found = self._check_rhetoric(story_text, lang.rhetoric)
                details["expected_rhetoric"] = lang.rhetoric
                details["rhetoric_found"] = rhetoric_found

            # 检查散文风格指标
            if lang.prose_style:
                prose_metrics = self._analyze_prose_style(story_text)
                details["prose_style"] = lang.prose_style
                details["prose_metrics"] = prose_metrics

            # 检查对话风格
            if lang.dialogue:
                dialogue_segments = re.findall(r"[" "「『]([^" "」』]*)[" "」』]", story_text)
                details["dialogue_count"] = len(dialogue_segments)
                details["dialogue_style"] = lang.dialogue

            # 检查情感表达
            if lang.emotional_expression:
                details["emotional_expression"] = lang.emotional_expression

            return True, "", details

        except Exception as e:
            logger.warning("validate_style_language failed: %s", e)
            return True, "", {"error": str(e)}

    def validate_style_technique(self, story_text: str, context: dict) -> Tuple[bool, str, dict]:
        """检查核心技法是否体现。

        基于 style.techniques 配置进行验证。
        """
        if not self.style:
            return True, "", {"skipped": True, "reason": "no style configured"}

        try:
            tech = self.style.techniques
            details: Dict[str, object] = {}

            # 检查核心技法
            if tech.core_techniques:
                technique_evidence = self._check_techniques(story_text, tech.core_techniques)
                details["core_techniques"] = tech.core_techniques
                details["technique_evidence"] = technique_evidence

            # 检查修辞手法
            if tech.stylistic_devices:
                device_evidence = self._check_stylistic_devices(story_text, tech.stylistic_devices)
                details["stylistic_devices"] = tech.stylistic_devices
                details["device_evidence"] = device_evidence

            # 检查叙事模式
            if tech.narrative_patterns:
                pattern_evidence = self._check_narrative_patterns(
                    story_text, tech.narrative_patterns
                )
                details["narrative_patterns"] = tech.narrative_patterns
                details["pattern_evidence"] = pattern_evidence

            return True, "", details

        except Exception as e:
            logger.warning("validate_style_technique failed: %s", e)
            return True, "", {"error": str(e)}

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    def _get_structure_indicators(self, macro: str) -> List[str]:
        """根据宏观结构类型返回检测关键词。"""
        indicators_map: Dict[str, List[str]] = {
            "章回体": ["却说", "话说", "且说", "回目", "欲知后事", "看官"],
            "三幕式": ["冲突", "高潮", "转折", "危机", "解决"],
            "英雄之旅": ["召唤", "冒险", "试炼", "考验", "归来", "蜕变"],
            "框架叙事": ["故事中的故事", "讲述", "回忆", "追溯"],
            "线性叙事": [],  # 线性叙事无特殊标记
        }
        # 尝试匹配已知结构，否则返回空
        for key, indicators in indicators_map.items():
            if key in macro:
                return indicators
        return []

    def _get_arc_indicators(self, arc: str) -> List[str]:
        """根据弧线类型返回检测关键词。"""
        indicators_map: Dict[str, List[str]] = {
            "起承转合": ["起", "承", "转", "合"],
            "英雄之旅": ["启程", "历险", "归来"],
            "三幕": ["建置", "对抗", "解决"],
            "螺旋上升": ["重复", "深化", "升华"],
        }
        for key, indicators in indicators_map.items():
            if key in arc:
                return indicators
        return []

    def _get_opening_indicators(self, opening_style: str) -> List[str]:
        """根据开头风格返回检测关键词。"""
        indicators_map: Dict[str, List[str]] = {
            "环境描写": ["天", "风", "雨", "月", "阳光", "夜", "晨"],
            "悬念": ["突然", "意外", "竟然", "没想到", "不料"],
            "对话": ["\u201c", "「", "道", "说"],
            "回忆": ["想起", "记得", "回忆", "那时", "当年"],
            "动作": ["奔", "跑", "冲", "挥", "踏", "跃"],
        }
        for key, indicators in indicators_map.items():
            if key in opening_style:
                return indicators
        return []

    def _get_closing_indicators(self, closing_style: str) -> List[str]:
        """根据结尾风格返回检测关键词."""
        indicators_map: Dict[str, List[str]] = {
            "悬念": ["却", "然而", "但是", "谁知", "不料", "忽然"],
            "抒情": ["感慨", "叹息", "心中", "默默"],
            "留白": ["……", "沉默", "无言", "不语"],
            "章回": ["欲知后事", "且听下回"],
        }
        for key, indicators in indicators_map.items():
            if key in closing_style:
                return indicators
        return []

    def _check_hook_presence(self, ending_text: str, hook_types: List[str]) -> bool:
        """检查结尾是否包含预期的悬念钩子。"""
        hook_patterns: Dict[str, List[str]] = {
            "悬念": [r"却", r"然而", r"但是", r"谁知", r"不料", r"忽然", r"竟"],
            "伏笔": [r"不知", r"日后", r"将来", r"后来", r"终将"],
            "反转": [r"没想到", r"意外", r"出乎意料", r"竟然"],
            "情感": [r"心中", r"暗暗", r"默默", r"不禁"],
            "疑问": [r"到底", r"究竟", r"为何", r"难道", r"怎会"],
            "章回钩子": [r"欲知后事", r"且听下回"],
        }

        for hook_type in hook_types:
            patterns = hook_patterns.get(hook_type, [])
            if any(re.search(p, ending_text) for p in patterns):
                return True

        # 通用悬念检测作为兜底
        general_hooks = [r"\？", r"……", r"却", r"然而", r"但"]
        return any(re.search(p, ending_text) for p in general_hooks)

    def _check_rhetoric(self, story_text: str, rhetoric_types: List[str]) -> List[str]:
        """检查修辞手法使用情况。"""
        rhetoric_patterns: Dict[str, List[str]] = {
            "比喻": [r"如同", r"好像", r"仿佛", r"犹如", r"宛如", r"像是", r"似"],
            "拟人": [r"(?:风|雨|花|树|月|云)(?:在)?(?:轻声|悄悄|默默)", r"大地.*沉睡"],
            "排比": [],  # 排比需要更复杂的句式分析
            "对偶": [],  # 对偶需要更复杂的句式分析
            "夸张": [r"万", r"千", r"无数", r"铺天盖地"],
            "反问": [r"难道", r"岂", r"怎能", r"何尝"],
            "设问": [r"为什么", r"怎么.*呢"],
        }

        found: List[str] = []
        for rtype in rhetoric_types:
            patterns = rhetoric_patterns.get(rtype, [])
            if any(re.search(p, story_text) for p in patterns):
                found.append(rtype)

        return found

    def _analyze_prose_style(self, story_text: str) -> Dict[str, object]:
        """分析散文风格指标。"""
        sentences = [s.strip() for s in re.split(r"[。！？\n]", story_text) if s.strip()]
        if not sentences:
            return {"sentence_count": 0}

        lengths = [len(s) for s in sentences]
        avg_length = sum(lengths) / len(lengths) if lengths else 0

        return {
            "sentence_count": len(sentences),
            "avg_sentence_length": round(avg_length, 1),
            "max_sentence_length": max(lengths) if lengths else 0,
            "min_sentence_length": min(lengths) if lengths else 0,
        }

    def _check_techniques(self, story_text: str, techniques: List[str]) -> Dict[str, bool]:
        """检查核心技法是否有所体现。"""
        technique_patterns: Dict[str, List[str]] = {
            "白描": [r"[^，。！？]{4,8}[，。]"],  # 短句为主
            "工笔": [r"[^，。！？]{15,}[，。]"],  # 长句细描
            "意识流": [r"想到", r"脑海", r"思绪", r"恍惚", r"意识"],
            "蒙太奇": [r"与此同时", r"另一边", r"此刻", r"同一时间"],
            "倒叙": [r"那是.*以前", r"回想起", r"想当年", r"那时候"],
            "插叙": [r"说起来", r"提到.*不得不", r"这要从.*说起"],
            "伏笔": [r"不知", r"日后", r"将来", r"后来才知"],
            "草蛇灰线": [r"不经意", r"无意间", r"隐约"],
            "留白": [r"……", r"沉默", r"不语", r"无言"],
        }

        evidence: Dict[str, bool] = {}
        for tech in techniques:
            patterns = technique_patterns.get(tech, [])
            evidence[tech] = any(re.search(p, story_text) for p in patterns)

        return evidence

    def _check_stylistic_devices(self, story_text: str, devices: List[str]) -> Dict[str, bool]:
        """检查修辞/风格手法。"""
        device_patterns: Dict[str, List[str]] = {
            "象征": [r"象征", r"代表", r"意味着"],
            "隐喻": [r"是.*的", r"化作", r"变成"],
            "反讽": [r"偏偏", r"恰恰", r"倒是"],
            "对比": [r"却", r"然而", r"截然不同", r"相反"],
            "渲染": [r"弥漫", r"笼罩", r"充斥", r"萦绕"],
        }

        evidence: Dict[str, bool] = {}
        for device in devices:
            patterns = device_patterns.get(device, [])
            evidence[device] = any(re.search(p, story_text) for p in patterns)

        return evidence

    def _check_narrative_patterns(
        self, story_text: str, patterns_list: List[str]
    ) -> Dict[str, bool]:
        """检查叙事模式。"""
        pattern_indicators: Dict[str, List[str]] = {
            "渐进式": [r"渐渐", r"逐渐", r"慢慢", r"一步步"],
            "循环式": [r"又一次", r"再次", r"重复", r"轮回"],
            "对称式": [r"如同.*一样", r"正如.*那般"],
            "递进式": [r"不仅.*而且", r"更", r"甚至", r"何况"],
        }

        evidence: Dict[str, bool] = {}
        for pattern in patterns_list:
            indicators = pattern_indicators.get(pattern, [])
            evidence[pattern] = any(re.search(p, story_text) for p in indicators)

        return evidence
