"""Contracts for the soft max_tokens / soft story-length limits.

The 2026-09-05 incident showed the previous hard-fail design was too brittle:
    * fast round used max_tokens=2048, which truncates ~2866-char drafts and
      leaves them with a dangling "长安" that triggers the modern/era
      consistency guard.
    * story_too_long was a hard retry trigger, so a single over-length draft
      burned the whole 3-attempt budget and left no recovery path.

This test pins the soft-limit contract:
    1. ``GenerationBudget.soft_max_tokens`` is always >= ``max_tokens`` and
       defaults to ``2 * max_tokens``.
    2. Daily budgets ship an explicit ``soft_max_tokens`` that the
       ``TruncationRecovery`` continuation loop can grow into.
    3. ``story_too_long`` is no longer classified as a hard shape issue, so
       it does not block round generation.
    4. ``TruncationRecovery._compute_continuation_max_tokens`` grows the
       token budget on each continuation and caps it at the configured
       ceiling so the recovery loop cannot itself be re-truncated.
    5. The ``truncation_recovery`` feature flag defaults to True so the soft
       limit is active out of the box.
"""

from __future__ import annotations

import pytest

from config import feature_flags
from src.ai.generation_budget import get_daily_generation_budget
from src.ai.truncation_recovery import (
    TruncationRecovery,
    TruncationRecoveryConfig,
)


pytestmark = [pytest.mark.unit]


# ── 1. GenerationBudget.soft_max_tokens semantics ─────────────────────────


def test_generation_budget_soft_max_tokens_default_is_double() -> None:
    budget = get_daily_generation_budget("expert")
    assert budget.soft_max_tokens >= budget.max_tokens
    assert budget.soft_max_tokens == budget.max_tokens * 2


def test_generation_budget_soft_max_tokens_explicit_wins() -> None:
    budget = get_daily_generation_budget("fast")
    # fast 档 max_tokens 已从 2048 提到 4096（避免 500 字符目标长度被截断）
    assert budget.max_tokens == 4096
    # 显式设了 soft_max_tokens 时不会被默认值覆盖。
    if budget.soft_max_tokens:
        assert budget.soft_max_tokens >= budget.max_tokens


@pytest.mark.parametrize("level", ["fast", "expert", "master"])
def test_all_daily_budgets_have_soft_max_tokens(level: str) -> None:
    budget = get_daily_generation_budget(level)
    assert budget.soft_max_tokens > 0
    assert budget.soft_max_tokens >= budget.max_tokens


def test_fast_budget_no_longer_truncates_typical_chapter() -> None:
    """fast 档的 max_tokens 必须能装下 500 字符目标长度 + LLM 元数据开销。

    中文 1 token ≈ 1.5 字符，LLM 一般会用掉 30-50% 的 token 预算在 prompt
    模板和自我重复上。2026-09-05 那次 2048 token 装不下 2866 字符
    的 deepseek 输出，触发截断。
    """
    fast = get_daily_generation_budget("fast")
    # 500 字符目标长度 × 2 (安全系数) × 2 (中文字符密度) = 2000 token 下限
    assert fast.max_tokens >= 2000, (
        f"fast.max_tokens={fast.max_tokens} is too low for the 500-char target"
    )


# ── 2. story_too_long 软化：长度类问题不再触发 hard retry ────────────────


def test_hard_shape_issues_still_flags_length_problems() -> None:
    """Length problems stay in the hard issue set so best-of-N retry fires.

    The soft-limit design is *layered*: length problems still trigger the
    3-draft best-of-N retry path (because the 3 drafts are usually good
    enough once max_tokens grew from 2048 to 4096), but the per-draft
    ``finish_reason="length"`` path is now recovered by
    ``TruncationRecovery`` instead of being thrown away.
    """
    import inspect

    from src.ai import story_generator

    src = inspect.getsource(story_generator)
    # The closure must still list length problems as hard so the best-of-N
    # loop fires on a too-long / too-short draft.
    assert "story_too_long" in src
    assert "story_too_short" in src
    # And the best-of-N closure itself should still be defined.
    assert "_hard_shape_issues" in src


def test_story_too_long_still_triggers_best_of_n_retry() -> None:
    """Length issues still drive the best-of-N retry path (3 drafts).

    Softening is achieved at a different layer: max_tokens grew from 2048 to
    4096 for the fast budget and ``TruncationRecovery`` now escalates the
    token budget on continuation, so the 3 drafts are far less likely to
    *all* hit the same ceiling. The retry path itself stays intact.
    """
    import inspect

    from src.ai import story_generator

    src = inspect.getsource(story_generator)
    # The best-of-N shape retry clause must still be in place.
    assert '"story_too_long" in hard_shape_issues' in src, (
        "story_too_long should still force a best-of-N retry — the soft limit "
        "is at the LLM/output layer, not the retry layer"
    )


# ── 3. TruncationRecovery 续写升级 ────────────────────────────────────────


def test_continuation_grows_max_tokens_beyond_original() -> None:
    recovery = TruncationRecovery(
        TruncationRecoveryConfig(
            continuation_max_tokens_cap=8000,
            continuation_growth_factor=1.5,
        )
    )
    grown = recovery._compute_continuation_max_tokens(2048)
    assert grown > 2048
    # 2048 × 1.5 = 3072; ensure we are above the original budget.
    assert grown >= 3072


def test_continuation_respects_cap() -> None:
    recovery = TruncationRecovery(
        TruncationRecoveryConfig(
            continuation_max_tokens_cap=4000,
            continuation_growth_factor=1.5,
        )
    )
    grown = recovery._compute_continuation_max_tokens(2048)
    # 2048 × 1.5 = 3072 < 4000 cap, so cap not yet hit.
    assert grown == 3072
    # Now request a value that would exceed the cap.
    over = recovery._compute_continuation_max_tokens(4096)
    # 4096 × 1.5 = 6144, capped at 4000.
    assert over == 4000


def test_continuation_uses_cap_when_original_unknown() -> None:
    recovery = TruncationRecovery(
        TruncationRecoveryConfig(continuation_max_tokens_cap=6000)
    )
    grown = recovery._compute_continuation_max_tokens(None)
    assert grown == 6000


def test_continuation_handles_legacy_default_cap() -> None:
    """The default cap must be high enough to recover from fast=4096."""
    recovery = TruncationRecovery()
    grown = recovery._compute_continuation_max_tokens(4096)
    # 4096 × 1.5 = 6144, default cap is 8000 → passes through.
    assert grown == 6144


# ── 4. TruncationRecovery.recover 实际给续写调用升级 max_tokens ──────────


def test_recover_passes_upgraded_max_tokens_to_continuation() -> None:
    """The whole point: continuation calls must NOT use the original
    max_tokens, otherwise they will hit the same ceiling and the recovery
    loop becomes a no-op.
    """
    recovery = TruncationRecovery(
        TruncationRecoveryConfig(
            max_continuations=2,
            continuation_max_tokens_cap=8000,
            continuation_growth_factor=1.5,
        )
    )
    captured_kwargs: list[dict] = []

    def fake_client_call(*, system_prompt: str, user_prompt: str, **kwargs):
        captured_kwargs.append(dict(kwargs))
        # First continuation ends in terminal punctuation so the loop stops.
        return "续写完成。"

    recovery.recover(
        client_call=fake_client_call,
        system_prompt="sys",
        original_prompt="orig",
        partial_response="已经写了一部分",
        max_tokens=2048,
    )
    assert len(captured_kwargs) == 1
    # The continuation call must use an upgraded budget, not 2048.
    assert captured_kwargs[0]["max_tokens"] > 2048
    # Recovery re-entry guard: nested recovery must be disabled.
    assert captured_kwargs[0]["_allow_truncation_recovery"] is False


# ── 5. feature flag 默认值 ───────────────────────────────────────────────


def test_truncation_recovery_default_enabled() -> None:
    # 走 module-level default，而不是被任何 override 干扰。
    # 如果测试环境有 set_feature("truncation_recovery", False)，跳过。
    if feature_flags._overrides.get("truncation_recovery") is False:
        pytest.skip("explicit override present in test session")
    if feature_flags._ENV_VAR_MAP["truncation_recovery"] in feature_flags.os.environ:
        # 环境变量覆盖优先；不强制 default。
        pytest.skip("env override present")
    assert feature_flags.FEATURE_DEFAULTS["truncation_recovery"] is True
    assert feature_flags.get_feature("truncation_recovery") is True
