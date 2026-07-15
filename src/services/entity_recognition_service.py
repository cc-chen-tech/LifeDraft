"""实体识别服务。

从历史故事中识别重复出现的物品、人物、地点。
"""

import logging
import re
from typing import Any, Callable, Dict, Iterable, List, Optional

from src.services.base_extraction import BaseExtractionService

logger = logging.getLogger(__name__)


class EntityRecognitionService(BaseExtractionService):
    """从历史故事中识别实体的服务。"""

    # 继承 BaseExtractionService.__init__

    def recognize_from_history(
        self,
        round_history: List[Dict[str, Any]],
        existing_items: List[str],
        existing_characters: List[str],
        existing_landmarks: List[str],
        min_appearances: int = 3,
        language: str = "zh",
        eligible_character_names: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """从历史记录中识别实体。

        Args:
            round_history: 回合历史记录列表
            existing_items: 已存在的物品名称列表
            existing_characters: 已存在的人物名称列表
            existing_landmarks: 已存在的地点名称列表
            min_appearances: 最少出现次数（默认3次）
            language: 语言代码

        Returns:
            {"items": [...], "characters": [...], "landmarks": [...]}
        """
        if not round_history:
            return {"items": [], "characters": [], "landmarks": []}

        try:
            # 构建完整故事文本
            story_text = self._build_story_text(round_history)

            # 使用基类的截断逻辑
            story_text = self._truncate_recognition_story(story_text)

            # 统计有效事件数量
            valid_events = sum(
                1
                for entry in round_history
                if entry.get("event_description")
                or entry.get("story_continuation")
                or entry.get("summary")
            )
            logger.info(
                f"Entity recognition: {len(round_history)} rounds, "
                f"{valid_events} valid events, story text {len(story_text)} chars, "
                f"min_appearances={min_appearances}"
            )

            from config.prompts.entity_recognition_prompt import \
                get_entity_recognition_prompt

            prompt = get_entity_recognition_prompt(
                story_text=story_text,
                existing_items=existing_items,
                existing_characters=existing_characters,
                existing_landmarks=existing_landmarks,
                min_appearances=min_appearances,
                language=language,
            )

            sys_prompt = self._get_system_prompt("story_analyzer", language)

            response = self._call_ai(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                temperature=0.3,
                max_tokens=2048,
            )

            logger.info(f"AI raw response (first 500 chars): {response[:500]}")

            result = self._parse_recognition_response(response)
            story_character_names = self._extract_named_people(story_text)
            effective_character_names = self._ordered_unique(
                [*(eligible_character_names or []), *story_character_names]
            )
            if eligible_character_names is not None:
                result["characters"] = self._filter_character_entities_by_metadata(
                    result.get("characters", []),
                    eligible_character_names=effective_character_names,
                    story_character_names=story_character_names,
                    existing_characters=existing_characters,
                )
            result = self._supplement_with_story_entities(
                result=result,
                story_text=story_text,
                existing_items=existing_items,
                existing_characters=existing_characters,
                existing_landmarks=existing_landmarks,
                min_appearances=min_appearances,
                eligible_character_names=effective_character_names,
            )
            result = self._normalize_recognized_entities(
                result,
                existing_characters=existing_characters,
                existing_landmarks=existing_landmarks,
            )
            logger.info(
                f"Parsed entities: {len(result.get('items', []))} items, "
                f"{len(result.get('characters', []))} characters, "
                f"{len(result.get('landmarks', []))} landmarks"
            )
            return result

        except Exception as e:
            logger.error(f"Entity recognition failed: {e}", exc_info=True)
            return {"items": [], "characters": [], "landmarks": []}

    def extract_item_description(
        self,
        item_name: str,
        round_history: List[Dict[str, Any]],
        language: str = "zh",
    ) -> Optional[Dict[str, Any]]:
        """从历史中提取特定物品的描述。

        Args:
            item_name: 物品名称
            round_history: 回合历史记录
            language: 语言代码

        Returns:
            物品信息字典，失败返回None
        """
        try:
            # 收集包含该物品的上下文
            contexts = []
            for entry in round_history:
                text_parts = []
                if entry.get("event_description"):
                    text_parts.append(entry["event_description"])
                if entry.get("story_continuation"):
                    text_parts.append(entry["story_continuation"])

                text = " ".join(text_parts)
                if item_name in text:
                    contexts.append(text[:800])  # 截取相关片段

            if not contexts:
                return None

            # 限制上下文数量
            contexts = contexts[:5]
            story_text = "\n\n---\n\n".join(contexts)

            from config.prompts.entity_recognition_prompt import \
                get_item_description_extraction_prompt

            prompt = get_item_description_extraction_prompt(
                item_name=item_name,
                story_text=story_text,
                language=language,
            )

            sys_prompt = self._get_system_prompt("story_analyzer", language)

            response = self._call_ai(
                system_prompt=sys_prompt,
                user_prompt=prompt,
                temperature=0.5,
                max_tokens=2048,
            )

            data = self._parse_json_response(response)
            if data and "name" in data:
                return {
                    "name": data["name"],
                    "description": data.get("description", ""),
                    "category": data.get("category", "other"),
                    "importance": data.get("importance", "normal"),
                    "acquired_context": contexts[0][:200] if contexts else "",
                    "is_key_item": data.get("importance") == "critical",
                }

            return None

        except Exception as e:
            logger.error(f"Failed to extract item description: {e}")
            return None

    def _build_story_text(self, round_history: List[Dict[str, Any]]) -> str:
        """将round_history构建成完整的故事文本。

        即使 event_description 缺失，也会从 story_continuation、summary、
        choice 等字段中尽可能构建完整的上下文。

        Args:
            round_history: 回合历史记录

        Returns:
            格式化的故事文本
        """
        story_parts = []

        # 按周和回合排序
        sorted_history = sorted(round_history, key=lambda x: (x.get("week", 0), x.get("round", 0)))

        for entry in sorted_history:
            week = entry.get("week", 0) + 1
            round_num = entry.get("round", 0)
            round_names = ["周一", "周中", "周末"]
            round_name = round_names[round_num] if round_num < 3 else f"回合{round_num}"

            # 收集本回合所有文本片段
            parts = []

            if entry.get("event_description"):
                parts.append(f"事件：{entry['event_description']}")

            if entry.get("choice"):
                parts.append(f"选择：{entry['choice']}")

            if entry.get("story_continuation"):
                parts.append(f"结果：{entry['story_continuation']}")

            if entry.get("summary"):
                parts.append(f"总结：{entry['summary']}")

            # 仅当有实际内容时才添加该回合
            if parts:
                story_parts.append(f"\n=== 第{week}周 {round_name} ===\n")
                story_parts.extend(parts)

        return "\n".join(story_parts)

    def _parse_recognition_response(self, response: str) -> Dict[str, List[Dict[str, Any]]]:
        """解析AI识别响应。

        Args:
            response: AI响应文本

        Returns:
            解析后的实体字典
        """
        try:
            data = self._parse_json_response(response)
            if not data:
                return {"items": [], "characters": [], "landmarks": []}

            result: dict[str, Any] = {"items": [], "characters": [], "landmarks": []}

            # 解析物品
            for item in data.get("items", []):
                if self._validate_entity(item):
                    result["items"].append(item)

            # 解析人物
            for char in data.get("characters", []):
                if self._validate_entity(char):
                    result["characters"].append(char)

            # 解析地点
            for landmark in data.get("landmarks", []):
                if self._validate_entity(landmark):
                    result["landmarks"].append(landmark)

            logger.info(
                f"Entity recognition completed: {len(result['items'])} items, "
                f"{len(result['characters'])} characters, "
                f"{len(result['landmarks'])} landmarks"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to parse recognition response: {e}")
            return {"items": [], "characters": [], "landmarks": []}

    def _supplement_with_story_entities(
        self,
        result: Dict[str, List[Dict[str, Any]]],
        story_text: str,
        existing_items: List[str],
        existing_characters: List[str],
        existing_landmarks: List[str],
        min_appearances: int,
        eligible_character_names: Optional[List[str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """用确定性文本识别补足 AI 漏掉的明显实体。

        AI 负责语义判断和丰富描述；这里兜底处理集合面板最不能漏的
        具体命名人物，以及少量明确道具/地点名。
        """
        supplemented = {
            "items": list(result.get("items", [])),
            "characters": list(result.get("characters", [])),
            "landmarks": list(result.get("landmarks", [])),
        }

        story_character_names = self._extract_named_people(story_text)
        character_candidates = self._ordered_unique(
            [*(eligible_character_names or []), *story_character_names]
        )
        character_candidates = [
            name for name in character_candidates if name in story_character_names
        ]
        if character_candidates:
            self._append_missing_entities(
                supplemented["characters"],
                character_candidates,
                set(existing_characters),
                self._build_character_fallback_entity,
                story_text,
                min_appearances=1,
            )
        self._append_missing_entities(
            supplemented["items"],
            self._extract_named_items(story_text),
            set(existing_items),
            self._build_item_fallback_entity,
            story_text,
            min_appearances=min_appearances,
        )
        self._append_missing_entities(
            supplemented["landmarks"],
            self._extract_named_landmarks(story_text),
            set(existing_landmarks),
            self._build_landmark_fallback_entity,
            story_text,
            min_appearances=min_appearances,
        )
        return supplemented

    def _filter_character_entities_by_metadata(
        self,
        characters: List[Dict[str, Any]],
        eligible_character_names: Optional[List[str]],
        story_character_names: List[str],
        existing_characters: List[str],
    ) -> List[Dict[str, Any]]:
        """Keep supported character candidates and reject inferred names."""
        eligible = set(eligible_character_names or [])
        story_people = set(story_character_names)
        existing = set(existing_characters)
        if not eligible or not story_people:
            return []

        filtered: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for character in characters:
            name = str(character.get("name", "")).strip()
            if (
                not name
                or name in seen
                or name in existing
                or name not in eligible
                or name not in story_people
            ):
                continue
            filtered.append(character)
            seen.add(name)
        return filtered

    def _normalize_recognized_entities(
        self,
        result: Dict[str, List[Dict[str, Any]]],
        existing_characters: List[str],
        existing_landmarks: List[str],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Remove duplicate aliases from AI and fallback recognition output."""
        character_full_names = [
            entity.get("name", "")
            for entity in result.get("characters", [])
            if entity.get("name")
        ] + existing_characters
        landmark_full_names = [
            entity.get("name", "")
            for entity in result.get("landmarks", [])
            if entity.get("name")
        ] + existing_landmarks

        return {
            "items": result.get("items", []),
            "characters": [
                entity
                for entity in result.get("characters", [])
                if not self._is_person_title_alias(entity.get("name", ""), character_full_names)
            ],
            "landmarks": [
                entity
                for entity in result.get("landmarks", [])
                if not self._is_landmark_alias(entity.get("name", ""), landmark_full_names)
            ],
        }

    def _append_missing_entities(
        self,
        entities: List[Dict[str, Any]],
        names: List[str],
        existing_names: set[str],
        build_entity: Callable[[str, str, int], Dict[str, Any]],
        story_text: str,
        min_appearances: int,
    ) -> None:
        known_names = existing_names | {entity.get("name", "") for entity in entities}
        for name in names:
            if name in known_names:
                continue
            appear_count = story_text.count(name)
            if appear_count < min_appearances:
                continue
            entities.append(build_entity(name, story_text, appear_count))
            known_names.add(name)

    def _extract_named_people(self, story_text: str) -> List[str]:
        """提取中文故事中明确命名的人物。"""
        single_surnames = (
            "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜姚"
            "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳刘鲍史唐费"
            "廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄"
            "穆萧尹林陆石"
        )
        compound_surnames = "欧阳|司马|上官|诸葛"
        name_boundary = r"(?:(?<![\u4e00-\u9fff])|(?<=[见与和向问对请找叫邀同]))"
        person_actions = (
            "说|问|答|道|提醒|递|交|带|走|来|去|把|将|在|从|与|和|向|看|笑|皱|捧|"
            "提出|要求|承认|否认|表示|解释|反驳|递来|打来|联系|签|站|沉默|扶|扶住|"
            "握|握紧|赶|赶来|守|苦笑|又|、|，|。|：|:"
        )
        titles = (
            "掌柜|先生|小姐|夫人|师傅|师父|老板|管家|姑娘|公子|大人|老师|医生|"
            "律师|副总|总监|经理|主任|助理|记者|差爷|叔|伯|婶|姨|老丈"
        )
        surname = rf"(?:{compound_surnames}|[{single_surnames}])"
        patterns = [
            rf"{name_boundary}{surname}[\u4e00-\u9fff]{{0,2}}?(?:{titles})",
            rf"阿[\u4e00-\u9fff]{{1,2}}?(?=(?:{person_actions}))",
            (
                rf"{name_boundary}{surname}[\u4e00-\u9fff]{{2}}"
                rf"(?=(?:的|当年|一直|曾经|已经|正|也|都|从|在|把|将|说|问|提醒|低声|缓缓|"
                rf"提出|承认|否认|表示|解释|反驳|联系|沉默|扶|握|赶|留下|，|。|、|：|:))"
            ),
            (
                rf"{name_boundary}{surname}[\u4e00-\u9fff]{{1,2}}?"
                rf"(?=(?:随后|接着|立即|马上|{person_actions}))"
            ),
        ]
        names = []
        for pattern in patterns:
            names.extend(re.findall(pattern, story_text))
        candidates = self._ordered_unique(
            name
            for name in (self._clean_entity_name(raw) for raw in names)
            if self._looks_like_person_name(name)
        )
        return self._prune_person_aliases(candidates)

    def _looks_like_person_name(self, name: str) -> bool:
        """过滤中文人名兜底中的常见短语误识别。"""
        if len(name) < 2 or len(name) > 5:
            return False
        false_positive_tokens = (
            "周初",
            "周中",
            "周末",
            "元增",
            "元减",
            "方才",
            "顾客",
            "水洼",
            "上扬",
            "放下",
            "收购",
            "别人",
            "平静",
            "常见",
            "郑重",
            "上传",
            "施主",
            "于是",
            "许久",
            "马蹄",
            "知道",
            "现在",
            "坐在",
            "守在",
            "苦笑",
        )
        if any(token in name for token in false_positive_tokens):
            return False
        if name.endswith(("上", "下", "前", "后", "里", "中", "处")):
            return False
        return True

    def _prune_person_aliases(self, names: List[str]) -> List[str]:
        """Drop short title aliases when a fuller explicit name is present."""
        return [name for name in names if not self._is_person_title_alias(name, names)]

    def _is_person_title_alias(self, name: str, full_names: List[str]) -> bool:
        """Return true when a title-only name duplicates a fuller same-surname name."""
        title_suffixes = ("先生", "叔", "伯", "姑娘", "公子", "大人")
        if name.endswith(title_suffixes):
            return any(
                full_name != name
                and full_name.startswith(name[0])
                and not full_name.endswith(title_suffixes)
                for full_name in full_names
            )

        verb_fragment_suffixes = (
            "知",
            "现",
            "坐",
            "扶",
            "握",
            "看",
            "问",
            "说",
            "道",
            "守",
            "苦",
            "来",
            "去",
        )
        return any(
            full_name
            and name != full_name
            and name.startswith(full_name)
            and len(name) == len(full_name) + 1
            and name.endswith(verb_fragment_suffixes)
            for full_name in full_names
        )

    def _truncate_recognition_story(
        self,
        story_text: str,
        max_length: int = 15000,
    ) -> str:
        """Keep early setup and recent/current story for recognition.

        Collection recognition needs recent visible story most. Prefix-only
        truncation makes late-week characters disappear in long games.
        """
        if len(story_text) <= max_length:
            return story_text

        logger.warning(
            f"Story text too long ({len(story_text)} chars), truncating to {max_length}"
        )
        marker = "\n...[故事过长，中间内容已截断，保留最近剧情用于识别]...\n"
        content_limit = max(0, max_length - len(marker))
        head_len = content_limit // 3
        tail_len = content_limit - head_len
        return (
            story_text[:head_len]
            + marker
            + story_text[-tail_len:]
        )

    def _is_landmark_alias(self, name: str, full_names: List[str]) -> bool:
        """Return true when a place short name is contained in a longer place name."""
        if not name:
            return False
        return any(
            full_name != name
            and len(full_name) > len(name)
            and full_name.endswith(name)
            for full_name in full_names
        )

    def _extract_named_items(self, story_text: str) -> List[str]:
        """提取明确的道具名，保持范围保守。"""
        patterns = [
            r"(?:金|银|铜|铁|玉)?钥匙",
            r"账册|账本|玉佩|印章|信件|书信|契约|地图|令牌|玉坠|匕首|短刀|长剑|宝剑|药瓶",
        ]
        names = []
        for pattern in patterns:
            names.extend(re.findall(pattern, story_text))
        return self._ordered_unique(self._clean_entity_name(name) for name in names)

    def _extract_named_landmarks(self, story_text: str) -> List[str]:
        """提取明确命名的地点。"""
        suffixes = "船行|客栈|书院|武馆|医馆|茶楼|酒楼|码头|祠堂|商行|镖局|药铺"
        raw_names = re.findall(rf"[\u4e00-\u9fff]{{2,8}}(?:{suffixes})", story_text)
        names = []
        for raw_name in raw_names:
            name = re.sub(
                r"^.*(?:在|到|回到|来到|进入|打开|前往|赶到|走进|离开|路过|提醒)",
                "",
                raw_name,
            )
            names.append(name)
        return self._ordered_unique(self._clean_entity_name(name) for name in names)

    def _ordered_unique(self, names: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        result = []
        for name in names:
            if not name or name in seen:
                continue
            seen.add(name)
            result.append(name)
        return result

    def _clean_entity_name(self, name: str) -> str:
        return name.strip(" \n\t，。、“”‘’：:；;（）()【】")

    def _build_character_fallback_entity(
        self, name: str, story_text: str, appear_count: int
    ) -> Dict[str, Any]:
        context = self._first_context(name, story_text)
        return {
            "name": name,
            "description": f"{name}是在故事中明确出现的命名人物。{context}",
            "role": "故事人物",
            "importance": "normal",
            "appear_count": appear_count,
            "appear_contexts": [context] if context else [],
        }

    def _build_item_fallback_entity(
        self, name: str, story_text: str, appear_count: int
    ) -> Dict[str, Any]:
        context = self._first_context(name, story_text)
        return {
            "name": name,
            "description": f"{name}是在故事中出现的具体物品。{context}",
            "category": self._guess_item_category(name),
            "importance": "important",
            "appear_count": appear_count,
            "appear_contexts": [context] if context else [],
        }

    def _build_landmark_fallback_entity(
        self, name: str, story_text: str, appear_count: int
    ) -> Dict[str, Any]:
        context = self._first_context(name, story_text)
        return {
            "name": name,
            "description": f"{name}是在故事中出现的明确地点。{context}",
            "category": "building",
            "importance": "important",
            "appear_count": appear_count,
            "appear_contexts": [context] if context else [],
        }

    def _first_context(self, name: str, story_text: str) -> str:
        normalized_story = re.sub(r"\s+", " ", story_text).strip()
        index = normalized_story.find(name)
        if index < 0:
            return ""

        sentence_delimiters = "。！？!?；;\n"
        start = max(
            (normalized_story.rfind(mark, 0, index) for mark in sentence_delimiters),
            default=-1,
        ) + 1
        ends = [
            position
            for mark in sentence_delimiters
            if (position := normalized_story.find(mark, index + len(name))) >= 0
        ]
        end = min(ends) + 1 if ends else len(normalized_story)
        sentence = normalized_story[start:end].strip()
        if len(sentence) <= 120:
            return sentence

        name_index = sentence.find(name)
        excerpt_start = max(0, name_index - 45)
        excerpt_end = min(len(sentence), name_index + len(name) + 65)
        excerpt = sentence[excerpt_start:excerpt_end].strip(" ，,。；;")
        if excerpt_start > 0:
            excerpt = f"…{excerpt}"
        if excerpt_end < len(sentence):
            excerpt = f"{excerpt}…"
        return excerpt

    def _guess_item_category(self, name: str) -> str:
        if any(token in name for token in ("账册", "账本", "信件", "书信", "契约", "地图")):
            return "document"
        if any(token in name for token in ("玉佩", "玉坠", "令牌", "印章")):
            return "keepsake"
        if any(token in name for token in ("钥匙", "药瓶")):
            return "tool"
        if any(token in name for token in ("匕首", "短刀", "长剑", "宝剑")):
            return "weapon"
        return "other"

    def _validate_entity(self, entity: Dict[str, Any]) -> bool:
        """验证实体数据是否有效。

        Args:
            entity: 实体数据字典

        Returns:
            是否有效
        """
        if not entity.get("name"):
            return False

        # 使用基类的验证方法
        entity["importance"] = self._validate_importance(entity.get("importance", "normal"))

        # 验证出现次数
        appear_count = entity.get("appear_count", 0)
        if not isinstance(appear_count, int) or appear_count < 1:
            entity["appear_count"] = 1

        # 确保appear_contexts是列表
        if "appear_contexts" not in entity or not isinstance(entity["appear_contexts"], list):
            entity["appear_contexts"] = []

        return True
