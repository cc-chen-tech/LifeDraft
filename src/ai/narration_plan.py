"""Strict narration-plan contract shared by story generation and MiniMax TTS."""

from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Any, Mapping, Optional

from src.services.minimax_story_tts_provider import MINIMAX_NATIVE_EMOTIONS

MINIMAX_VOCAL_CUES = frozenset(
    {
        "",
        "(laughs)",
        "(chuckle)",
        "(coughs)",
        "(clear-throat)",
        "(groans)",
        "(breath)",
        "(pant)",
        "(inhale)",
        "(exhale)",
        "(gasps)",
        "(sniffs)",
        "(sighs)",
        "(whispers)",
        "(humming)",
        "(hissing)",
        "(emm)",
        "(sneezes)",
        "(applause)",
        "(crying)",
    }
)

# Narration plans are a structured-output task, not prose. Keep their budget
# independent from story-generation budgets and leave enough headroom for one
# compact object per paragraph.
NARRATION_PLAN_MIN_OUTPUT_TOKENS = 2048
NARRATION_PLAN_TOKENS_PER_PARAGRAPH = 192
NARRATION_PLAN_MAX_OUTPUT_TOKENS = 8192


def narration_plan_output_tokens(paragraph_count: int, attempt: int = 0) -> int:
    """Return an independent structured-output budget for a narration plan."""
    count = max(1, int(paragraph_count))
    baseline = max(
        NARRATION_PLAN_MIN_OUTPUT_TOKENS,
        512 + count * NARRATION_PLAN_TOKENS_PER_PARAGRAPH,
    )
    return min(NARRATION_PLAN_MAX_OUTPUT_TOKENS, baseline * (max(0, attempt) + 1))


@dataclass(frozen=True)
class NarrationSegmentPlan:
    paragraph_index: int
    emotion: str
    speed: float
    pause_after_ms: int
    vocal_cue: str = ""


@dataclass(frozen=True)
class NarrationPlan:
    segments: tuple[NarrationSegmentPlan, ...]


class NarrationPlanValidationError(ValueError):
    """Structured validation failure that can be fed into a model retry."""

    def __init__(self, errors: list[str]):
        self.errors = tuple(errors)
        super().__init__("Narration plan validation failed: " + "; ".join(errors))


def parse_narration_plan(raw: Any, *, paragraph_count: int) -> NarrationPlan:
    errors: list[str] = []
    raw_segments = raw.get("segments") if isinstance(raw, Mapping) else None
    if not isinstance(raw_segments, list):
        raise NarrationPlanValidationError(["segments must be an array"])
    if len(raw_segments) != paragraph_count:
        errors.append(f"expected {paragraph_count} segments, got {len(raw_segments)}")

    parsed: list[NarrationSegmentPlan] = []
    for expected_index, raw_segment in enumerate(raw_segments[:paragraph_count]):
        if not isinstance(raw_segment, Mapping):
            errors.append(f"segment {expected_index} must be an object")
            continue
        index = raw_segment.get("paragraph_index", expected_index)
        if index != expected_index:
            errors.append(f"segment {expected_index} paragraph_index must be {expected_index}")
        emotion = raw_segment.get("emotion")
        if emotion not in MINIMAX_NATIVE_EMOTIONS:
            errors.append(
                f"segment {expected_index} emotion must be one of {sorted(MINIMAX_NATIVE_EMOTIONS)}"
            )
        speed = raw_segment.get("speed")
        if not isinstance(speed, (int, float)) or not 0.5 <= float(speed) <= 1.5:
            errors.append(f"segment {expected_index} speed must be between 0.5 and 1.5")
        pause_after_ms = raw_segment.get("pause_after_ms")
        if not isinstance(pause_after_ms, int) or not 0 <= pause_after_ms <= 3000:
            errors.append(f"segment {expected_index} pause_after_ms must be between 0 and 3000")
        vocal_cue = raw_segment.get("vocal_cue", "")
        if vocal_cue not in MINIMAX_VOCAL_CUES:
            errors.append(
                f"segment {expected_index} vocal_cue must be one of {sorted(MINIMAX_VOCAL_CUES)}"
            )
        if (
            emotion in MINIMAX_NATIVE_EMOTIONS
            and isinstance(speed, (int, float))
            and 0.5 <= float(speed) <= 1.5
            and isinstance(pause_after_ms, int)
            and 0 <= pause_after_ms <= 3000
            and vocal_cue in MINIMAX_VOCAL_CUES
        ):
            parsed.append(
                NarrationSegmentPlan(
                    paragraph_index=expected_index,
                    emotion=str(emotion),
                    speed=float(speed),
                    pause_after_ms=pause_after_ms,
                    vocal_cue=str(vocal_cue),
                )
            )
    if errors:
        raise NarrationPlanValidationError(errors)
    return NarrationPlan(segments=tuple(parsed))


def narration_plan_retry_instruction(error: NarrationPlanValidationError) -> str:
    """Give the story model the exact failure reasons, never a silent fallback."""
    return (
        "Narration plan validation failed. Regenerate only the narration_plan and "
        "return valid JSON. Fix every issue below; do not invent provider values:\n"
        + "\n".join(f"- {item}" for item in error.errors)
    )


def build_legacy_narration_plan(paragraphs: list[str]) -> dict[str, Any]:
    """Create a valid migration plan for stories generated before this feature."""
    segments = []
    for index, paragraph in enumerate(paragraphs):
        text = paragraph.lower()
        emotion = "fearful" if re.search(r"危险|恐惧|黑暗|danger|fear|dark", text) else "calm"
        if re.search(r"笑|喜悦|开心|laugh|joy|happy", text):
            emotion = "happy"
        segments.append(
            {
                "paragraph_index": index,
                "emotion": emotion,
                "speed": 0.96 if emotion == "fearful" else 1.0,
                "pause_after_ms": 420 if index < len(paragraphs) - 1 else 0,
                "vocal_cue": "",
            }
        )
    return {"segments": segments, "source": "deterministic-fallback"}


class NarrationPlanGenerator:
    """Ask the story model for a plan and retry with validation feedback."""

    def __init__(self, client: Any):
        self.client = client
        self.last_metrics: dict[str, Any] = {
            "source": "ai",
            "fallback_reason": None,
            "ai_attempts": 0,
            "output_token_budgets": [],
            "duration_ms": 0,
        }

    def generate(
        self,
        story_text: str,
        *,
        language: str = "zh",
        max_attempts: int = 2,
        generation_tracker: Optional[Any] = None,
    ) -> dict[str, Any]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", story_text) if part.strip()]
        system_prompt = (
            "You are a narration director. Return compact JSON only. Do not return "
            "prose, explanations, paragraph text, Markdown, SSML, or extra keys. "
            "Use exactly one segment per paragraph and only the listed MiniMax values."
        )
        user_prompt = self._prompt(story_text, language)
        started_at = time.monotonic()
        output_token_budgets: list[int] = []
        attempts = 0
        last_error: Optional[Exception] = None
        last_reason: Optional[str] = None
        attempt_limit = max(1, int(max_attempts))
        from src.ai.client import AIResponseTruncatedError
        from src.ai.utils import extract_json

        for attempt in range(attempt_limit):
            budget = narration_plan_output_tokens(len(paragraphs), attempt)
            output_token_budgets.append(budget)
            attempts += 1
            try:
                response = self.client.call(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=0.2,
                    max_tokens=budget,
                    stream_callback=None,
                    generation_tracker=generation_tracker,
                    response_format={"type": "json_object"},
                    thinking=False,
                    _allow_truncation_recovery=False,
                )
                raw = extract_json(response)
                if raw is None:
                    raise NarrationPlanValidationError(["response did not contain valid JSON"])
                plan = parse_narration_plan(raw, paragraph_count=len(paragraphs))
                self.last_metrics = self._metrics(
                    fallback_reason=None,
                    attempts=attempts,
                    output_token_budgets=output_token_budgets,
                    started_at=started_at,
                )
                return {
                    "segments": [segment.__dict__ for segment in plan.segments],
                    "source": "story-model",
                }
            except AIResponseTruncatedError as error:
                last_error = error
                last_reason = "truncated"
                if attempt + 1 < attempt_limit:
                    continue
                break
            except NarrationPlanValidationError as error:
                last_error = error
                last_reason = (
                    "json_parse_error" if "valid JSON" in str(error) else "validation_error"
                )
                if attempt + 1 >= attempt_limit:
                    break
                user_prompt = (
                    self._prompt(story_text, language)
                    + "\n\n"
                    + narration_plan_retry_instruction(error)
                )
            except Exception as error:
                self.last_metrics = self._metrics(
                    fallback_reason=self._classify_error(error),
                    attempts=attempts,
                    output_token_budgets=output_token_budgets,
                    started_at=started_at,
                )
                raise

        if last_error is None:
            last_error = RuntimeError("narration plan generation made no attempts")
            last_reason = "api_error"
        self.last_metrics = self._metrics(
            fallback_reason=last_reason or self._classify_error(last_error),
            attempts=attempts,
            output_token_budgets=output_token_budgets,
            started_at=started_at,
        )
        raise last_error

    @staticmethod
    def _classify_error(error: Exception) -> str:
        name = type(error).__name__.lower()
        if isinstance(error, TimeoutError) or "timeout" in name:
            return "timeout"
        if "truncated" in name:
            return "truncated"
        return "api_error"

    @staticmethod
    def _metrics(
        *,
        fallback_reason: Optional[str],
        attempts: int,
        output_token_budgets: list[int],
        started_at: float,
    ) -> dict[str, Any]:
        return {
            "source": "ai",
            "fallback_reason": fallback_reason,
            "ai_attempts": attempts,
            "output_token_budgets": list(output_token_budgets),
            "duration_ms": max(0, int((time.monotonic() - started_at) * 1000)),
        }

    @staticmethod
    def _prompt(story_text: str, language: str) -> str:
        return (
            f"Language: {language}\n"
            'Return exactly {"segments":[{"paragraph_index":0,'
            '"emotion":"calm","speed":1.0,"pause_after_ms":0,'
            '"vocal_cue":""}]} for this story. Native emotions are: '
            + ", ".join(sorted(MINIMAX_NATIVE_EMOTIONS))
            + ". Allowed vocal cues are the MiniMax inline cues; use empty string when none. "
            "Return no keys other than the five fields shown above.\n\n" + story_text
        )
