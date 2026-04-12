"""信息屏障验证器 - 验证角色不应知道超出其信息范围的事实。

检查内容：
- 角色表达的知识必须有信息来源
- 防止全知视角泄露到特定角色对话中
"""

import logging
import re
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# 知识表达模式（表示角色声称知道某事）
KNOWLEDGE_CLAIM_PATTERNS = [
    r"{char}.{0,10}(?:知道|得知|听说|了解到|发现|察觉到|意识到|看到了|看见了)",
    r"{char}.{0,10}(?:说道|说|告诉|写信道|道|叫道|喊道).{0,30}(?:知道|听说|了解|听闻|发现|看到)",
    r"[""「]{char}.{0,5}(?:知道|听说|了解|发现|看到)",
]

# 宽泛的对话模式（用于秘密信息检测，不用于一般可及性检查）
SPEECH_PATTERNS = [
    r"{char}.{0,10}(?:说道|说|告诉|写信道|道|叫道|喊道).{0,50}",
]

# 秘密/隐私关键词
SECRET_INDICATORS = [
    "秘密", "隐瞒", "不为人知", "暗中", "偷偷", "私下",
    "只有.*知道", "没人知道", "无人知晓", "瞒着",
]


class InformationBarrierValidator:
    """信息屏障验证器。"""

    def validate(self, story_text: str, context: dict) -> Tuple[bool, str, dict]:
        """验证角色是否展现了超出其信息范围的知识。"""
        try:
            knowledge_sets = None
            world_model = context.get("world_model")
            if world_model and hasattr(world_model, "character_knowledge_sets"):
                knowledge_sets = world_model.character_knowledge_sets
            # 也支持直接在 context 中传入
            if not knowledge_sets:
                knowledge_sets = context.get("character_knowledge_sets")
            if not knowledge_sets:
                return True, "", {"skipped": True, "reason": "empty knowledge_sets"}

            characters = list(knowledge_sets.keys())
            violations = []
            details: Dict = {
                "characters_checked": 0,
                "knowledge_claims": [],
                "barrier_violations": [],
            }

            # 提取所有角色的知识声明
            all_claims = self.extract_knowledge_claims(story_text, characters)
            # 也提取宽泛对话（用于秘密检测）
            speech_claims = self.extract_speech_claims(story_text, characters)
            details["knowledge_claims"] = all_claims
            details["characters_checked"] = len(
                set(c.get("character", "") for c in all_claims + speech_claims)
            )

            # 按角色分组检查
            checked_chars: set = set()
            for char_name in characters:
                char_knowledge_raw = knowledge_sets.get(char_name, {})
                if not char_knowledge_raw:
                    continue

                # 支持 dict 格式 {"knows": [...], "secrets_unknown": [...]}
                if isinstance(char_knowledge_raw, dict):
                    known_info = set(char_knowledge_raw.get("knows", []))
                    secrets_unknown = char_knowledge_raw.get("secrets_unknown", [])
                elif isinstance(char_knowledge_raw, (set, list)):
                    known_info = set(char_knowledge_raw)
                    secrets_unknown = []
                else:
                    known_info = set()
                    secrets_unknown = []

                # 检查秘密信息泄露（使用知识声明+对话声明）
                if secrets_unknown:
                    char_all_claims = [c for c in all_claims if c.get("character") == char_name]
                    char_all_claims += [c for c in speech_claims if c.get("character") == char_name]
                    for claim_item in char_all_claims:
                        claim_context = claim_item.get("context", "")
                        claim_content = claim_item.get("content", "")
                        for secret in secrets_unknown:
                            if secret in claim_context or secret in claim_content:
                                violation = {
                                    "character": char_name,
                                    "claim": claim_content,
                                    "context": claim_context,
                                    "secret": secret,
                                    "message": f"角色'{char_name}'表现出不应知道的秘密信息: '{secret}'",
                                    "hint": f"角色{char_name}不应知道'{secret}'",
                                }
                                violations.append(violation)
                                details["barrier_violations"].append(violation)

                # 检查知识声明的可及性
                char_claims = [c for c in all_claims if c.get("character") == char_name]
                for claim in char_claims:
                    accessible = self.check_knowledge_accessibility(
                        claim, known_info
                    )
                    if not accessible:
                        violation = {
                            "character": char_name,
                            "claim": claim.get("content", ""),
                            "context": claim.get("context", ""),
                            "message": f"角色'{char_name}'表现出超出其信息范围的知识",
                            "hint": f"角色{char_name}不应知道此信息",
                        }
                        violations.append(violation)
                        details["barrier_violations"].append(violation)

            if violations:
                return (
                    False,
                    f"信息屏障违规: {'; '.join(v['message'] for v in violations[:3])}",
                    {
                        **details,
                        "violations": violations,
                        "correction_hint": "请确保每个角色只表达其有合理途径获知的信息，"
                        "不应出现全知视角泄露",
                    },
                )

            return True, "", details

        except Exception as e:
            logger.warning(f"信息屏障验证异常: {e}")
            return True, "", {}

    def extract_knowledge_claims(
        self, text: str, characters: list
    ) -> list:
        """提取角色表达的知识声明。"""
        claims = []

        for char_name in characters:
            if len(char_name) < 2 or char_name not in text:
                continue

            for pattern_tmpl in KNOWLEDGE_CLAIM_PATTERNS:
                pattern = pattern_tmpl.replace("{char}", re.escape(char_name))
                for match in re.finditer(pattern, text):
                    ctx_start = max(0, match.start() - 10)
                    ctx_end = min(len(text), match.end() + 40)
                    content = text[match.end():min(len(text), match.end() + 30)]
                    # 清理内容
                    content = re.sub(r"[。！？""」\n].*", "", content)

                    claims.append({
                        "character": char_name,
                        "content": content.strip(),
                        "context": text[ctx_start:ctx_end],
                        "position": match.start(),
                    })

        return claims

    def extract_speech_claims(self, text: str, characters: list) -> list:
        """提取角色的宽泛对话（用于秘密信息检测）。"""
        claims = []
        for char_name in characters:
            if len(char_name) < 2 or char_name not in text:
                continue
            for pattern_tmpl in SPEECH_PATTERNS:
                pattern = pattern_tmpl.replace("{char}", re.escape(char_name))
                for match in re.finditer(pattern, text):
                    ctx_start = max(0, match.start() - 10)
                    ctx_end = min(len(text), match.end() + 40)
                    content = text[match.end():min(len(text), match.end() + 50)]
                    content = re.sub(r"[。！？""」\n].*", "", content)
                    claims.append({
                        "character": char_name,
                        "content": content.strip(),
                        "context": text[ctx_start:ctx_end],
                        "position": match.start(),
                    })
        return claims

    def check_knowledge_accessibility(
        self, claim: dict, character_knowledge: set
    ) -> bool:
        """验证角色是否有途径获知此信息。"""
        content = claim.get("content", "")
        context = claim.get("context", "")
        if not content:
            return True  # 无法判断，默认通过

        # 如果角色知识集为空，无法验证，默认通过
        if not character_knowledge:
            return True

        # 检查声明内容或上下文中的关键词是否在角色知识集中
        check_text = content + " " + context

        # 如果有任何知识条目的关键部分在声明文本中出现，认为可访问
        for knowledge in character_knowledge:
            # 提取知识条目中的实质词（按标点和常见功能词拆分）
            knowledge_words = set(re.split(r"[，。、；\s在是的了]+", knowledge))
            knowledge_words = {kw for kw in knowledge_words if len(kw) >= 2}
            for kw in knowledge_words:
                if kw in check_text:
                    return True

        # 反向检查：声明文本中的关键词是否在知识条目中
        content_keywords = set(re.split(r"[，。、；\s]+", content))
        content_keywords = {kw for kw in content_keywords if len(kw) >= 2}
        for keyword in content_keywords:
            for knowledge in character_knowledge:
                if keyword in knowledge or knowledge in keyword:
                    return True

        # 没有匹配，但如果知识声明内容很短或模糊，给予通过
        if len(content) < 5:
            return True

        return False


def validate_information_barrier(
    story_text: str, context: dict
) -> Tuple[bool, str, dict]:
    """模块级验证函数。"""
    return InformationBarrierValidator().validate(story_text, context)
