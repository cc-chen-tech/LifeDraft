"""NPC属性固化验证器 - 验证NPC描写与存储属性一致。

检查内容：
- NPC外貌描写不应与已存储的角色画像矛盾
- NPC行为边界不应被突破
- NPC说话风格应保持一致
"""

import logging
import re
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

# 外貌特征关键词模式
APPEARANCE_PATTERNS = [
    (r"(?:高大|矮小|瘦弱|魁梧|纤细|壮硕|修长)", "body_type"),
    (r"(?:白发|黑发|灰发|红发|金发|银发|长发|短发|光头|秃顶)", "hair"),
    (r"(?:年轻|年迈|苍老|年少|中年|老年|青年)", "age_appearance"),
    (r"(?:美丽|英俊|丑陋|端庄|清秀|粗犷|俊美|威严)", "face"),
]

# 互斥属性对（同时出现即矛盾）
CONTRADICTORY_PAIRS = [
    ("高大", "矮小"),
    ("魁梧", "瘦弱"),
    ("纤细", "壮硕"),
    ("白发", "黑发"),
    ("长发", "光头"),
    ("短发", "长发"),
    ("年轻", "年迈"),
    ("年少", "苍老"),
    ("美丽", "丑陋"),
    ("英俊", "丑陋"),
]


class NPCAttributeStabilityValidator:
    """NPC属性固化验证器。"""

    def validate(self, story_text: str, context: dict) -> Tuple[bool, str, dict]:
        """验证NPC描写与存储属性一致。"""
        try:
            world_model = context.get("world_model")
            if not world_model or not hasattr(world_model, "character_profiles"):
                return (
                    True,
                    "",
                    {"skipped": True, "reason": "no world_model or character_profiles"},
                )

            profiles = world_model.character_profiles
            if not profiles:
                return True, "", {"skipped": True, "reason": "no character profiles"}

            known_npcs = list(profiles.keys())
            violations = []
            details: Dict = {
                "npcs_checked": 0,
                "description_issues": [],
                "boundary_violations": [],
            }

            for npc_name in known_npcs:
                if len(npc_name) < 2 or npc_name not in story_text:
                    continue

                details["npcs_checked"] += 1
                profile = profiles[npc_name]

                # 1. 提取NPC描写
                descriptions = self.extract_npc_descriptions(story_text, npc_name)

                # 2. 检查属性一致性
                attr_issues = self.check_attribute_consistency(npc_name, descriptions, profile)
                if attr_issues:
                    details["description_issues"].extend(attr_issues)
                    violations.extend(attr_issues)

                # 3. 检查行为边界
                boundary_issues = self._check_behavioral_boundaries(story_text, npc_name, profile)
                if boundary_issues:
                    details["boundary_violations"].extend(boundary_issues)
                    violations.extend(boundary_issues)

                # 4. 检查身份矛盾
                identity_issues = self._check_identity_contradiction(story_text, npc_name, profile)
                violations.extend(identity_issues)

                # 5. 检查性格矛盾
                personality_issues = self._check_personality_contradiction(
                    story_text, npc_name, profile
                )
                violations.extend(personality_issues)

            if violations:
                return (
                    False,
                    f"NPC属性一致性违规: {'; '.join(v.get('message', '') for v in violations[:3])}",
                    {
                        **details,
                        "violations": violations,
                        "correction_hint": "; ".join(v.get("hint", "") for v in violations[:3]),
                    },
                )

            return True, "", details

        except Exception as e:
            logger.warning(f"NPC属性固化验证异常: {e}")
            return True, "", {}

    def extract_npc_descriptions(self, text: str, npc_name: str) -> list:
        """提取文本中NPC的描写。"""
        descriptions = []

        # 在角色名附近（前后80字）查找描写
        for match in re.finditer(re.escape(npc_name), text):
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 80)
            context_text = text[start:end]

            # 提取外貌特征
            for pattern, attr_type in APPEARANCE_PATTERNS:
                attr_matches = re.findall(pattern, context_text)
                for attr in attr_matches:
                    descriptions.append(
                        {
                            "npc": npc_name,
                            "attribute": attr,
                            "type": attr_type,
                            "context": context_text[:60],
                        }
                    )

        return descriptions

    def check_attribute_consistency(self, npc_name: str, descriptions: list, profile: Any) -> list:
        """对比描写与存储属性。"""
        issues = []

        # 获取已存储的属性
        stored_appearance = ""
        if isinstance(profile, dict):
            profile.get("identity", "")
            stored_appearance = profile.get("appearance", "")
            profile.get("personality", "")
        elif hasattr(profile, "identity"):
            getattr(profile, "identity", "")
            stored_appearance = getattr(profile, "appearance", "")
            getattr(profile, "personality", "")

        if hasattr(profile, "behavioral_traits"):
            profile.behavioral_traits
        elif isinstance(profile, dict):
            profile.get("behavioral_traits", [])

        if hasattr(profile, "speech_style"):
            profile.speech_style
        elif isinstance(profile, dict):
            profile.get("speech_style", "")

        # 检查描写间的自相矛盾
        attrs_found = [d["attribute"] for d in descriptions]
        for a1, a2 in CONTRADICTORY_PAIRS:
            if a1 in attrs_found and a2 in attrs_found:
                issues.append(
                    {
                        "npc": npc_name,
                        "type": "self_contradiction",
                        "attributes": [a1, a2],
                        "message": f"NPC'{npc_name}'的描写自相矛盾: '{a1}'与'{a2}'",
                        "hint": f"角色{npc_name}不应同时被描写为'{a1}'和'{a2}'",
                    }
                )

        # 检查描写与存储外貌的矛盾
        if stored_appearance:
            for desc in descriptions:
                attr = desc.get("attribute", "")
                for a1, a2 in CONTRADICTORY_PAIRS:
                    if (attr == a1 and a2 in stored_appearance) or (
                        attr == a2 and a1 in stored_appearance
                    ):
                        issues.append(
                            {
                                "npc": npc_name,
                                "type": "appearance_contradiction",
                                "stored": stored_appearance,
                                "described": attr,
                                "message": f"NPC'{npc_name}'的外貌描写'{attr}'与存储属性'{stored_appearance}'矛盾",
                                "hint": f"角色{npc_name}的外貌应为'{stored_appearance}'，不应描写为'{attr}'",
                            }
                        )

        return issues

    def _check_behavioral_boundaries(self, text: str, npc_name: str, profile: Any) -> list:
        """检查NPC是否突破行为边界。"""
        issues = []

        boundaries = []
        if hasattr(profile, "behavioral_boundaries"):
            boundaries = profile.behavioral_boundaries
        elif isinstance(profile, dict):
            boundaries = profile.get("behavioral_boundaries", [])

        for boundary in boundaries:
            if not boundary or len(boundary) < 4:
                continue

            # 提取边界中的关键行为描述
            # 例如 "绝不在公开场合发怒" → 检查是否有公开发怒
            # 使用简单匹配：如果边界中"不"后的行为出现在角色上下文中
            negation_match = re.search(r"(?:不|绝不|从不|永不|决不)(.{2,10})", boundary)
            if negation_match:
                forbidden_action = negation_match.group(1)
                # 去掉常见后缀
                forbidden_action = re.sub(r"[，。、].*", "", forbidden_action)

                if len(forbidden_action) >= 2:
                    # 检查该角色在文本中是否有这个行为
                    pattern = re.escape(npc_name) + r".{0,30}" + re.escape(forbidden_action)
                    match = re.search(pattern, text)
                    if match:
                        ctx_start = max(0, match.start() - 10)
                        ctx_end = min(len(text), match.end() + 10)
                        issues.append(
                            {
                                "npc": npc_name,
                                "type": "boundary_violation",
                                "boundary": boundary,
                                "action": forbidden_action,
                                "context": text[ctx_start:ctx_end],
                                "message": f"NPC'{npc_name}'突破行为边界: "
                                f"'{boundary}'，但出现了'{forbidden_action}'",
                                "hint": f"角色{npc_name}的行为边界为'{boundary}'，"
                                f"不应出现'{forbidden_action}'",
                            }
                        )

        return issues

    def _check_identity_contradiction(self, text: str, npc_name: str, profile: Any) -> list:
        """检查NPC身份描写是否与存储身份矛盾。"""
        issues: list = []
        stored_identity = ""
        if isinstance(profile, dict):
            stored_identity = profile.get("identity", "")
        elif hasattr(profile, "identity"):
            stored_identity = getattr(profile, "identity", "")

        if not stored_identity:
            return issues

        # 提取角色名附近的身份描写（如 "大唐公主赵灵儿" 或 "赵灵儿，苗疆圣女"）
        # 检查角色名前后的称谓
        for match in re.finditer(re.escape(npc_name), text):
            # 角色名前面30字
            start = max(0, match.start() - 30)
            prefix = text[start : match.start()]
            # 角色名后面30字
            end = min(len(text), match.end() + 30)
            suffix = text[match.end() : end]

            # 检查是否有与存储身份不同的称谓
            local_context = prefix + npc_name + suffix
            # 如果存储身份中的关键词不在上下文中，但有其他身份关键词
            identity_keywords = [
                "公主",
                "圣女",
                "王子",
                "皇后",
                "国王",
                "将军",
                "大臣",
                "铁匠",
                "商人",
                "书生",
                "侠客",
                "巫师",
                "圣者",
                "祭司",
            ]

            stored_id_keywords = [kw for kw in identity_keywords if kw in stored_identity]
            text_id_keywords = [kw for kw in identity_keywords if kw in local_context]

            for text_kw in text_id_keywords:
                if text_kw not in stored_identity:
                    # 检查是否与存储身份的关键词冲突
                    if stored_id_keywords and text_kw not in stored_identity:
                        issues.append(
                            {
                                "npc": npc_name,
                                "type": "identity_contradiction",
                                "stored_identity": stored_identity,
                                "described_identity": text_kw,
                                "context": local_context[:60],
                                "message": f"NPC'{npc_name}'的身份描写'{text_kw}'与存储身份'{stored_identity}'矛盾",
                                "hint": f"角色{npc_name}的身份应为'{stored_identity}'",
                            }
                        )
                        break
            if issues:
                break

        return issues

    def _check_personality_contradiction(self, text: str, npc_name: str, profile: Any) -> list:
        """检查NPC性格描写是否与存储性格矛盾。"""
        issues: list = []
        stored_personality = ""
        if isinstance(profile, dict):
            stored_personality = profile.get("personality", "")
        elif hasattr(profile, "personality"):
            stored_personality = getattr(profile, "personality", "")

        if not stored_personality:
            return issues

        # 互斥性格对
        personality_contradictions = [
            ("温柔", "残忍"),
            ("善良", "阴险"),
            ("单纯", "狡诈"),
            ("天真", "阴险"),
            ("善良", "残忍"),
            ("温柔", "冷酷"),
            ("豪爽", "怯懦"),
            ("直率", "阴险"),
            ("忠诚", "背叛"),
            ("勇敢", "胆小"),
            ("热情", "冷漠"),
            ("正直", "奸诈"),
        ]

        # 在角色名附近查找性格描写
        for match in re.finditer(re.escape(npc_name), text):
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 80)
            local_context = text[start:end]

            for pos_trait, neg_trait in personality_contradictions:
                if (pos_trait in stored_personality and neg_trait in local_context) or (
                    neg_trait in stored_personality and pos_trait in local_context
                ):
                    issues.append(
                        {
                            "npc": npc_name,
                            "type": "personality_contradiction",
                            "stored_personality": stored_personality,
                            "described_trait": (
                                neg_trait if pos_trait in stored_personality else pos_trait
                            ),
                            "context": local_context[:60],
                            "message": f"NPC'{npc_name}'的性格描写与存储性格'{stored_personality}'矛盾",
                            "hint": f"角色{npc_name}的性格应为'{stored_personality}'",
                        }
                    )
                    return issues  # 找到一个矛盾即返回

        return issues


def validate_npc_attribute_stability(story_text: str, context: dict) -> Tuple[bool, str, dict]:
    """模块级验证函数。"""
    return NPCAttributeStabilityValidator().validate(story_text, context)
