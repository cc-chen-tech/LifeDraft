"""Explainable scene-fit profiles, scoring, and MiniMax prompt building."""

from __future__ import annotations

import re
from functools import lru_cache
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple, TypeVar


MUSIC_SCENE_PROMPT_VERSION = "music-scene-v1"
DEFAULT_MIN_SCENE_FIT_SCORE = 55


class MusicCandidate(Protocol):
    id: Any
    name: str
    artists: List[str]
    album: str


TCandidate = TypeVar("TCandidate", bound=MusicCandidate)


@dataclass(frozen=True)
class MusicSceneFitProfile:
    primary_emotion: str
    secondary_emotion: str
    scene_action: str
    scene_type: str
    setting: str
    era: str
    pacing: str
    energy: str
    tension: str
    instruments: List[str]
    negative_cues: List[str]
    selected_strategy: str
    search_queries: List[str] = field(default_factory=list)

    @classmethod
    def from_context(
        cls,
        analysis: Mapping[str, Any],
        story_text: str = "",
        character_settings: Optional[Mapping[str, Any]] = None,
    ) -> "MusicSceneFitProfile":
        embedded = analysis.get("scene_fit_profile") if isinstance(analysis, Mapping) else None
        if isinstance(embedded, Mapping):
            return cls.from_analysis(embedded)

        context_text = _context_text(analysis, story_text, character_settings)
        template = _select_template(context_text)

        primary_emotion = str(analysis.get("mood") or "")
        if _is_generic_emotion(primary_emotion) and template["selected_strategy"] != "generic_fallback":
            primary_emotion = str(template["primary_emotion"])
        if not primary_emotion:
            primary_emotion = str(template["primary_emotion"])
        scene_type = str(analysis.get("scene_type") or "")
        if _is_generic_scene(scene_type):
            scene_type = str(template["scene_type"])
        setting = str(
            analysis.get("era_or_environment")
            or analysis.get("environment")
            or template["setting"]
        )
        if _is_generic_scene(setting):
            setting = str(template["setting"])
        pacing = str(analysis.get("pacing") or template["pacing"])
        energy = str(analysis.get("energy") or template["energy"])

        instruments = _dedupe(
            [
                *[str(item) for item in analysis.get("instruments") or [] if item],
                *template["instruments"],
            ]
        )
        negative_cues = _dedupe(
            [
                *[str(item) for item in analysis.get("negative_cues") or [] if item],
                *template["negative_cues"],
            ]
        )

        return cls(
            primary_emotion=primary_emotion,
            secondary_emotion=str(template["secondary_emotion"]),
            scene_action=str(template["scene_action"]),
            scene_type=scene_type,
            setting=setting,
            era=_derive_era(setting, character_settings),
            pacing=pacing,
            energy=energy,
            tension=str(template["tension"]),
            instruments=instruments or ["钢琴", "弦乐"],
            negative_cues=negative_cues or ["人声", "歌词"],
            selected_strategy=str(template["selected_strategy"]),
            search_queries=list(template["search_queries"]),
        )

    @classmethod
    def from_analysis(cls, value: Mapping[str, Any]) -> "MusicSceneFitProfile":
        return cls(
            primary_emotion=str(value.get("primary_emotion") or "平静"),
            secondary_emotion=str(value.get("secondary_emotion") or ""),
            scene_action=str(value.get("scene_action") or "daily_transition"),
            scene_type=str(value.get("scene_type") or "日常过渡"),
            setting=str(value.get("setting") or value.get("environment") or "通用"),
            era=str(value.get("era") or "通用"),
            pacing=str(value.get("pacing") or "舒缓"),
            energy=str(value.get("energy") or "中低"),
            tension=str(value.get("tension") or "低"),
            instruments=[str(item) for item in value.get("instruments") or [] if item]
            or ["钢琴", "弦乐"],
            negative_cues=[str(item) for item in value.get("negative_cues") or [] if item]
            or ["人声", "歌词"],
            selected_strategy=str(value.get("selected_strategy") or "generic_fallback"),
            search_queries=[str(item) for item in value.get("search_queries") or [] if item],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_emotion": self.primary_emotion,
            "secondary_emotion": self.secondary_emotion,
            "scene_action": self.scene_action,
            "scene_type": self.scene_type,
            "setting": self.setting,
            "era": self.era,
            "pacing": self.pacing,
            "energy": self.energy,
            "tension": self.tension,
            "instruments": self.instruments,
            "negative_cues": self.negative_cues,
            "selected_strategy": self.selected_strategy,
            "search_queries": self.search_queries,
        }

    def to_analysis(self) -> Dict[str, Any]:
        return {
            "mood": self.primary_emotion,
            "scene_type": self.scene_type,
            "environment": self.setting,
            "era_or_environment": self.setting,
            "pacing": self.pacing,
            "energy": self.energy,
            "instruments": self.instruments,
            "keywords": self.search_queries,
            "search_queries": self.search_queries,
            "negative_cues": self.negative_cues,
            "prompt_version": MUSIC_SCENE_PROMPT_VERSION,
            "scene_fit_profile": self.to_dict(),
            "scene_fit_diagnostics": {
                "selected_strategy": self.selected_strategy,
                "prompt_version": MUSIC_SCENE_PROMPT_VERSION,
            },
        }


@dataclass(frozen=True)
class MusicSceneFitDecision:
    candidate_id: str
    score: int
    reason_codes: List[str]
    rejected: bool = False


class MusicSceneFitScorer:
    """Deterministic scorer for explainable metadata-level music fit."""

    def score_candidate(
        self,
        candidate: MusicCandidate,
        profile: MusicSceneFitProfile,
    ) -> MusicSceneFitDecision:
        text = _candidate_text(candidate)
        reason_codes: List[str] = []
        score = 0

        if _matches_negative_cue(text, profile.negative_cues):
            return MusicSceneFitDecision(
                candidate_id=str(candidate.id),
                score=-100,
                reason_codes=["negative_cue_conflict"],
                rejected=True,
            )

        for term in _positive_terms(profile):
            if len(term.strip()) < 2:
                continue
            if term and term.casefold() in text:
                score += 8
                reason_codes.append(f"term:{term}")

        for instrument in profile.instruments:
            if instrument and instrument.casefold() in text:
                score += 12
                reason_codes.append(f"instrument:{instrument}")

        if _has_safe_background_cue(text):
            score += 16
            reason_codes.append("safe_background")

        if profile.selected_strategy != "generic_fallback":
            for cue in _strategy_cues(profile.selected_strategy):
                if cue.casefold() in text:
                    score += 14
                    reason_codes.append(f"strategy:{cue}")

        if not reason_codes:
            reason_codes.append("weak_metadata_match")

        return MusicSceneFitDecision(
            candidate_id=str(candidate.id),
            score=min(score, 100),
            reason_codes=_dedupe(reason_codes),
            rejected=False,
        )

    def rank_candidates(
        self,
        candidates: Sequence[TCandidate],
        profile: MusicSceneFitProfile,
    ) -> List[TCandidate]:
        scored = [
            (self.score_candidate(candidate, profile), index, candidate)
            for index, candidate in enumerate(candidates)
        ]
        return [
            candidate
            for _decision, _index, candidate in sorted(
                scored,
                key=lambda item: (item[0].score, -item[1]),
                reverse=True,
            )
        ]

    def select_safe_candidates(
        self,
        candidates: Sequence[TCandidate],
        profile: MusicSceneFitProfile,
        min_score: int = DEFAULT_MIN_SCENE_FIT_SCORE,
    ) -> Tuple[List[TCandidate], Dict[str, Any]]:
        selected: List[TCandidate] = []
        safe_fallbacks: List[TCandidate] = []
        rejection_reasons: List[str] = []
        fit_score_by_id: Dict[str, int] = {}

        for candidate in candidates:
            decision = self.score_candidate(candidate, profile)
            fit_score_by_id[str(candidate.id)] = decision.score
            if decision.rejected:
                rejection_reasons.extend(decision.reason_codes)
                continue
            if decision.score >= min_score:
                selected.append(candidate)
            elif _has_safe_background_cue(_candidate_text(candidate)):
                safe_fallbacks.append(candidate)

        fallback_reason = None
        if not selected and safe_fallbacks:
            selected = safe_fallbacks[:3]
            fallback_reason = "low_confidence_candidate_pool"
        elif not selected:
            fallback_reason = "no_safe_music_candidate"

        return selected, {
            "selected_strategy": profile.selected_strategy,
            "fallback_reason": fallback_reason,
            "rejection_reasons": _dedupe(rejection_reasons),
            "fit_score_by_id": fit_score_by_id,
        }

    def diagnose(
        self,
        candidates: Sequence[MusicCandidate],
        profile: MusicSceneFitProfile,
    ) -> Dict[str, Any]:
        fit_score_by_id: Dict[str, int] = {}
        rejection_reasons_by_id: Dict[str, List[str]] = {}
        for candidate in candidates:
            decision = self.score_candidate(candidate, profile)
            fit_score_by_id[str(candidate.id)] = decision.score
            rejection_reasons_by_id[str(candidate.id)] = (
                decision.reason_codes if decision.rejected else []
            )
        return {
            "selected_strategy": profile.selected_strategy,
            "fit_score_by_id": fit_score_by_id,
            "rejection_reasons_by_id": rejection_reasons_by_id,
        }


@dataclass(frozen=True)
class MiniMaxMusicPrompt:
    prompt: str
    prompt_version: str
    diagnostics: Dict[str, Any]


class MiniMaxMusicPromptBuilder:
    """Build bounded English scene directions for MiniMax music generation."""

    def build(
        self,
        *,
        story_text: str,
        brief: Any,
        profile: MusicSceneFitProfile,
        max_chars: int,
    ) -> MiniMaxMusicPrompt:
        negative = _negative_instructions(profile.negative_cues)
        summary_budget = max(40, min(120, max_chars // 3))
        summary = _compact_story_summary(story_text, summary_budget)
        prompt = _join_prompt(
            summary=summary,
            brief=brief,
            profile=profile,
            negative=negative,
        )
        if len(prompt) > max_chars:
            prompt = _join_prompt(
                summary=_compact_story_summary(story_text, 48),
                brief=brief,
                profile=profile,
                negative=negative,
            )
        if len(prompt) > max_chars:
            prompt = _join_prompt(
                summary="",
                brief=brief,
                profile=profile,
                negative=negative,
            )
        if len(prompt) > max_chars:
            prompt = prompt[: max_chars - 1].rstrip(" ,;.") + "."
        return MiniMaxMusicPrompt(
            prompt=prompt,
            prompt_version=MUSIC_SCENE_PROMPT_VERSION,
            diagnostics={
                "prompt_version": MUSIC_SCENE_PROMPT_VERSION,
                "selected_strategy": profile.selected_strategy,
                "scene_action": profile.scene_action,
            },
        )



_NON_WORD_PUNCT_RE = re.compile(r"[\s\-—_·.。…!！?？,，、:：;；'\"“”‘’《》\[\]【】/\\]+")
_WHITESPACE_RE = re.compile(r"\s+")

def _context_text(
    analysis: Mapping[str, Any],
    story_text: str,
    character_settings: Optional[Mapping[str, Any]],
) -> str:
    parts: List[str] = [story_text]
    for value in analysis.values():
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif isinstance(value, Mapping):
            parts.extend(str(item) for item in value.values())
        else:
            parts.append(str(value))
    if character_settings:
        for value in character_settings.values():
            if isinstance(value, Mapping):
                parts.extend(str(item) for item in value.values())
            else:
                parts.append(str(value))
    return " ".join(parts)


def _select_template(context_text: str) -> Mapping[str, Any]:
    text = context_text.casefold()
    for template in SCENE_TEMPLATES:
        if any(cue.casefold() in text for cue in template["cues"]):
            return template
    return GENERIC_TEMPLATE


def _is_generic_scene(value: str) -> bool:
    normalized = str(value or "").strip()
    return normalized in {"", "未知", "通用", "叙事", "场景", "日常"}


def _is_generic_emotion(value: str) -> bool:
    normalized = str(value or "").strip().casefold()
    return normalized in {"", "未知", "通用", "平静", "普通", "中性", "neutral"}


def _derive_era(
    setting: str,
    character_settings: Optional[Mapping[str, Any]],
) -> str:
    if character_settings:
        era = character_settings.get("era")
        if isinstance(era, Mapping):
            era_name = str(era.get("era_name") or "")
            if era_name:
                return era_name
    if "民国" in setting:
        return "民国"
    if any(cue in setting for cue in ["现代", "当代", "互联网", "都市"]):
        return "现代"
    if any(cue in setting for cue in ["古风", "古代", "江湖"]):
        return "古代"
    return "通用"


def _dedupe(items: Iterable[str]) -> List[str]:
    result: List[str] = []
    for item in items:
        value = str(item).strip()
        if value and value not in result:
            result.append(value)
    return result


def _candidate_text(candidate: MusicCandidate) -> str:
    return " ".join(
        [
            str(candidate.name),
            str(candidate.album),
            *[str(item) for item in candidate.artists],
        ]
    ).casefold()


def _positive_terms(profile: MusicSceneFitProfile) -> List[str]:
    return _dedupe(
        [
            profile.primary_emotion,
            profile.secondary_emotion,
            profile.scene_type,
            profile.setting,
            profile.era,
            profile.pacing,
            profile.energy,
            profile.tension,
            *profile.search_queries,
            *_strategy_cues(profile.selected_strategy),
        ]
    )


@lru_cache(maxsize=32)
def _strategy_cues(strategy: str) -> List[str]:
    return {
        "investigative_suspense": ["调查", "悬疑", "旧案", "档案", "数据隐私", "科技公司", "证据", "冷色"],
        "modern_workplace": ["办公室", "职场", "产品", "数据", "科技", "电子", "专注"],
        "suspense_chase": ["悬疑", "追逐", "追捕", "紧张", "低音", "鼓", "影视配乐"],
        "quiet_recovery": ["康复", "病房", "清晨", "钢琴", "治愈", "安静"],
        "family_conflict": ["家庭", "冲突", "弦乐", "低沉", "情绪"],
        "restrained_romance": ["浪漫", "黄昏", "钢琴", "克制", "温柔"],
        "action_conflict": ["动作", "冲突", "打击乐", "警报", "紧张"],
        "reflective_ending": ["反思", "结尾", "钢琴", "回忆", "温和"],
        "generic_fallback": ["背景音乐", "纯音乐", "轻音乐", "钢琴"],
    }.get(strategy, [])


def _matches_negative_cue(text: str, negative_cues: Sequence[str]) -> bool:
    for cue in negative_cues:
        normalized = str(cue).strip().casefold()
        if not normalized:
            continue
        if normalized in text and not _cue_is_negated_in_candidate_text(normalized, text):
            return True
    if any(str(cue).casefold() in {"人声", "歌词", "流行人声", "no vocals", "no lyrics"} for cue in negative_cues):
        vocal_pop_cues = ["告白", "情歌", "甜蜜流行", "流行", "vocal", "lyrics", "dj"]
        return any(
            cue in text and not _cue_is_negated_in_candidate_text(cue, text)
            for cue in vocal_pop_cues
        )
    return False


def _cue_is_negated_in_candidate_text(cue: str, text: str) -> bool:
    compact_text = _NON_WORD_PUNCT_RE.sub("", text)
    if cue == "歌词":
        return "无歌词" in compact_text or "没有歌词" in compact_text or "纯音乐" in compact_text
    if cue == "人声":
        return "无人声" in compact_text or "没有人声" in compact_text or "纯音乐" in compact_text
    if cue in {"lyrics", "lyric"}:
        return "nolyrics" in compact_text or "instrumental" in compact_text
    if cue in {"vocal", "vocals"}:
        return "novocal" in compact_text or "novocals" in compact_text or "instrumental" in compact_text
    return False


def _has_safe_background_cue(text: str) -> bool:
    return any(
        cue in text
        for cue in ["纯音乐", "背景音乐", "配乐", "氛围", "轻音乐", "instrumental", "ambient", "score", "ost"]
    )


def _negative_instructions(negative_cues: Sequence[str]) -> str:
    translated: List[str] = ["No vocals", "No lyrics", "no dominant pop singing"]
    mapping = {
        "人声": "No vocals",
        "歌词": "No lyrics",
        "流行人声": "avoid vocal pop",
        "甜蜜流行": "avoid sweet pop ballads",
        "甜蜜情歌": "avoid sweet love ballads",
        "强烈舞曲": "avoid dance beats",
        "强节拍舞曲": "avoid dance beats",
        "搞笑梗曲": "avoid meme or comedy tracks",
        "舒缓民谣": "avoid soft folk songs",
    }
    for cue in negative_cues:
        translated.append(mapping.get(str(cue), f"avoid {cue}"))
    return ", ".join(_dedupe(translated))


def _compact_story_summary(story_text: str, max_chars: int) -> str:
    normalized = _WHITESPACE_RE.sub(" ", story_text).strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip(" ,，。.;；") + "."


def _join_prompt(
    *,
    summary: str,
    brief: Any,
    profile: MusicSceneFitProfile,
    negative: str,
) -> str:
    parts = [
        "Instrumental narrative gameplay background.",
        f"Scene action: {profile.scene_action}.",
        f"Mood: {profile.primary_emotion}; tension: {profile.tension}.",
        f"Scene: {profile.scene_type}; setting: {profile.setting}.",
        f"Pacing: {profile.pacing}; energy: {profile.energy}.",
        f"Instrumentation priority: {', '.join(profile.instruments[:4])}.",
        "Loopable 45-90 seconds, supportive under dialogue, cinematic but not busy.",
        negative + ".",
    ]
    if summary:
        parts.insert(1, f"Story context: {summary}")
    generation_prompt = str(getattr(brief, "generation_prompt", "") or "")
    if generation_prompt and "no vocals" not in generation_prompt.casefold():
        parts.append(generation_prompt[:80])
    return " ".join(parts)


GENERIC_TEMPLATE: Mapping[str, Any] = {
    "selected_strategy": "generic_fallback",
    "cues": [],
    "primary_emotion": "平静",
    "secondary_emotion": "过渡",
    "scene_action": "daily_transition",
    "scene_type": "日常过渡",
    "setting": "通用叙事场景",
    "pacing": "舒缓",
    "energy": "中低",
    "tension": "低",
    "instruments": ["钢琴", "弦乐"],
    "negative_cues": ["人声", "歌词", "强节拍流行"],
    "search_queries": ["轻音乐", "背景音乐", "纯音乐"],
}


SCENE_TEMPLATES: Sequence[Mapping[str, Any]] = [
    {
        "selected_strategy": "investigative_suspense",
        "cues": [
            "调查记者",
            "数据隐私",
            "数据黑幕",
            "旧案卷",
            "无人机巡逻",
            "加密云端",
            "数据泄露",
        ],
        "primary_emotion": "悬疑",
        "secondary_emotion": "克制紧张",
        "scene_action": "investigative_suspense",
        "scene_type": "都市调查悬疑",
        "setting": "现代都市调查现场",
        "pacing": "紧凑",
        "energy": "中",
        "tension": "中高",
        "instruments": ["冷色合成器", "低音脉冲", "弦乐纹理", "钢琴"],
        "negative_cues": ["治愈轻音乐", "甜蜜流行", "人声", "歌词", "轻快民谣"],
        "search_queries": ["都市调查 悬疑配乐", "科技公司 数据隐私 纯音乐", "旧案档案室 冷色氛围"],
    },
    {
        "selected_strategy": "modern_workplace",
        "cues": ["互联网公司", "会议室", "用户数据", "AI 协作", "AI协作", "白板", "产品经理"],
        "primary_emotion": "专注焦虑",
        "secondary_emotion": "克制紧张",
        "scene_action": "workplace_conflict",
        "scene_type": "现代职场冲突",
        "setting": "2020年代互联网公司会议室",
        "pacing": "紧凑",
        "energy": "中高",
        "tension": "中高",
        "instruments": ["电子合成器", "钢琴", "低频脉冲"],
        "negative_cues": ["流行人声", "歌词", "甜蜜流行", "热门金曲"],
        "search_queries": ["办公室 轻电子 氛围", "数据分析 纯音乐", "现代职场 配乐"],
    },
    {
        "selected_strategy": "suspense_chase",
        "cues": ["追捕", "逃亡", "雨夜码头", "旧账册", "汽笛", "江边"],
        "primary_emotion": "紧张",
        "secondary_emotion": "悬疑",
        "scene_action": "suspense_chase",
        "scene_type": "悬疑追逐",
        "setting": "雨夜码头",
        "pacing": "急促",
        "energy": "高",
        "tension": "高",
        "instruments": ["低音鼓", "弦乐", "合成器纹理"],
        "negative_cues": ["甜蜜流行", "人声", "歌词", "情歌"],
        "search_queries": ["悬疑追逐 纯音乐", "雨夜追捕 影视配乐", "紧张氛围 低音鼓"],
    },
    {
        "selected_strategy": "quiet_recovery",
        "cues": ["手术后", "病房", "康复", "练习行走", "窗帘"],
        "primary_emotion": "温柔",
        "secondary_emotion": "希望",
        "scene_action": "quiet_recovery",
        "scene_type": "安静康复",
        "setting": "现代病房清晨",
        "pacing": "舒缓",
        "energy": "低",
        "tension": "低",
        "instruments": ["钢琴", "轻弦乐", "柔和合成器"],
        "negative_cues": ["强烈舞曲", "人声", "歌词", "爆发打击乐"],
        "search_queries": ["康复 病房 钢琴", "清晨 治愈 纯音乐", "安静希望 配乐"],
    },
    {
        "selected_strategy": "family_conflict",
        "cues": ["晚饭桌", "父亲", "母亲", "兄妹", "欠款", "旧怨"],
        "primary_emotion": "压抑",
        "secondary_emotion": "亲情冲突",
        "scene_action": "family_conflict",
        "scene_type": "家庭冲突",
        "setting": "现代家庭餐桌",
        "pacing": "中速",
        "energy": "中",
        "tension": "中高",
        "instruments": ["弦乐", "低音钢琴", "暖色垫底"],
        "negative_cues": ["甜蜜情歌", "人声", "歌词", "轻快流行"],
        "search_queries": ["家庭冲突 弦乐", "压抑亲情 纯音乐", "低沉钢琴 配乐"],
    },
    {
        "selected_strategy": "restrained_romance",
        "cues": ["误会", "天桥", "伞面", "黄昏", "雨后"],
        "primary_emotion": "温柔",
        "secondary_emotion": "释然",
        "scene_action": "restrained_romance",
        "scene_type": "克制浪漫",
        "setting": "雨后城市黄昏",
        "pacing": "舒缓",
        "energy": "中低",
        "tension": "低",
        "instruments": ["钢琴", "弦乐", "柔和电钢"],
        "negative_cues": ["强节拍舞曲", "人声", "歌词", "甜腻流行"],
        "search_queries": ["克制浪漫 钢琴", "雨后城市 纯音乐", "温柔释然 配乐"],
    },
    {
        "selected_strategy": "action_conflict",
        "cues": ["保安", "追兵", "警报", "撞开", "货架"],
        "primary_emotion": "紧张",
        "secondary_emotion": "对抗",
        "scene_action": "action_conflict",
        "scene_type": "动作冲突",
        "setting": "夜色仓库",
        "pacing": "急促",
        "energy": "高",
        "tension": "高",
        "instruments": ["打击乐", "低音鼓", "弦乐断奏"],
        "negative_cues": ["舒缓民谣", "人声", "歌词", "轻快流行"],
        "search_queries": ["动作冲突 打击乐", "仓库追逐 配乐", "紧张动作 纯音乐"],
    },
    {
        "selected_strategy": "reflective_ending",
        "cues": ["多年以后", "旧办公室", "产品草图", "关灯离开", "抽屉"],
        "primary_emotion": "释然",
        "secondary_emotion": "怀旧",
        "scene_action": "reflective_ending",
        "scene_type": "反思结尾",
        "setting": "旧办公室夜晚",
        "pacing": "舒缓",
        "energy": "低",
        "tension": "低",
        "instruments": ["钢琴", "弦乐", "柔和环境音"],
        "negative_cues": ["搞笑梗曲", "人声", "歌词", "强节拍流行"],
        "search_queries": ["反思结尾 钢琴", "怀旧办公室 纯音乐", "安静告别 配乐"],
    },
]
