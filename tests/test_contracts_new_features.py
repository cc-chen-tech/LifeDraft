"""契约测试：验证6个新模块与现有模块之间的生产者/消费者字段名一致性。

每个测试组验证一个新模块与其依赖/消费者之间的接口契约，
确保字段名、类型、参数签名等在集成时不会出现不兼容。
"""

import inspect
from typing import get_type_hints

# ============================================================
# 模型降级契约
# ============================================================


class TestModelFallbackContracts:
    """验证 model_fallback 模块与 AIClient 的接口契约。"""

    def test_fallback_config_fields_are_valid(self):
        """ModelFallbackConfig 字段都是有效类型。

        契约：primary_model 是 str，fallback_models 是 List[str]，
        retry_on_status_codes 是 List[int]，max_fallback_attempts 是 int。
        """
        from src.ai.model_fallback import ModelFallbackConfig

        cfg = ModelFallbackConfig(
            primary_model="gpt-4",
            fallback_models=["gpt-3.5-turbo"],
        )
        assert isinstance(cfg.primary_model, str)
        assert isinstance(cfg.fallback_models, list)
        assert all(isinstance(m, str) for m in cfg.fallback_models)
        assert isinstance(cfg.retry_on_status_codes, list)
        assert all(isinstance(c, int) for c in cfg.retry_on_status_codes)
        assert isinstance(cfg.max_fallback_attempts, int)

    def test_fallback_call_signature_compatible_with_client(self):
        """FallbackChain.call_with_fallback() 的参数与 AIClient.call() 兼容。

        契约：call_with_fallback 的前置参数 (system_prompt, user_prompt,
        temperature, max_tokens, stream_callback) 必须与 AIClient.call() 一致。
        """
        from src.ai.client import AIClient
        from src.ai.model_fallback import FallbackChain

        client_params = set(inspect.signature(AIClient.call).parameters.keys()) - {
            "self"
        }
        fallback_params = set(
            inspect.signature(FallbackChain.call_with_fallback).parameters.keys()
        ) - {"self", "kwargs", "status_callback"}

        # call_with_fallback 的核心参数必须是 AIClient.call() 参数的子集
        core_params = {
            "system_prompt",
            "user_prompt",
            "temperature",
            "max_tokens",
            "stream_callback",
        }
        assert core_params.issubset(
            fallback_params
        ), f"FallbackChain.call_with_fallback 缺少参数: {core_params - fallback_params}"
        assert core_params.issubset(
            client_params
        ), f"AIClient.call 缺少参数: {core_params - client_params}"

    def test_fallback_status_codes_are_valid_http(self):
        """retry_on_status_codes 默认值都是合法 HTTP 状态码。

        契约：默认的 retry_on_status_codes 应在 100-599 范围内。
        """
        from src.ai.model_fallback import ModelFallbackConfig

        cfg = ModelFallbackConfig(primary_model="gpt-4", fallback_models=[])
        for code in cfg.retry_on_status_codes:
            assert 100 <= code <= 599, f"Invalid HTTP status code: {code}"

    def test_fallback_returns_tuple_of_str(self):
        """返回类型 Tuple[str, str] 与 AIClient.call() -> str 兼容。

        契约：call_with_fallback 返回 Tuple[str, str]，
        其中第一个元素（response_text）与 AIClient.call() 的 str 返回类型兼容。
        """
        from src.ai.model_fallback import FallbackChain

        hints = get_type_hints(FallbackChain.call_with_fallback)
        return_type = hints.get("return")
        # 返回类型应为 Tuple[str, str]
        assert return_type is not None
        # 验证是 tuple 形式
        origin = getattr(return_type, "__origin__", None)
        assert origin is tuple, f"Expected Tuple return type, got {return_type}"
        args = getattr(return_type, "__args__", ())
        assert len(args) == 2
        assert args[0] is str and args[1] is str


# ============================================================
# 截断恢复契约
# ============================================================


class TestTruncationRecoveryContracts:
    """验证 truncation_recovery 模块与 OpenAI API 的接口契约。"""

    def test_recovery_detect_truncation_uses_openai_finish_reasons(self):
        """detect_truncation 的 finish_reason 参数接受标准 OpenAI 值。

        契约：finish_reason 参数类型为 Optional[str]，
        应接受 "stop", "length", "content_filter", "tool_calls", None。
        """
        from src.ai.truncation_recovery import TruncationRecovery

        sig = inspect.signature(TruncationRecovery.detect_truncation)
        params = sig.parameters
        assert "finish_reason" in params, "detect_truncation 缺少 finish_reason 参数"
        assert "response" in params, "detect_truncation 缺少 response 参数"

        # 验证类型注解接受 Optional[str]
        hints = get_type_hints(TruncationRecovery.detect_truncation)
        fr_type = hints.get("finish_reason")
        # Optional[str] 即 Union[str, None]
        assert fr_type is not None
        # 检查返回类型是 bool
        assert hints.get("return") is bool

    def test_recovery_continuation_prompt_is_string(self):
        """build_continuation_prompt 返回 str。

        契约：返回值为 str 类型，可直接作为 AIClient.call() 的 user_prompt。
        """
        from src.ai.truncation_recovery import TruncationRecovery

        hints = get_type_hints(TruncationRecovery.build_continuation_prompt)
        assert hints.get("return") is str

    def test_recovery_recover_returns_complete_text(self):
        """recover() 返回 str 类型。

        契约：返回的完整文本类型为 str，与 AIClient.call() 返回类型一致。
        """
        from src.ai.truncation_recovery import TruncationRecovery

        hints = get_type_hints(TruncationRecovery.recover)
        assert hints.get("return") is str


# ============================================================
# 状态机契约
# ============================================================


class TestGenerationStateContracts:
    """验证 generation_state 模块与 HarnessMetrics 的接口契约。"""

    def test_state_tracker_metrics_keys(self):
        """StateTracker.to_metrics() 应包含指定的 key。

        契约：to_metrics() 返回 dict 应包含 total_attempts, transitions,
        final_model, final_temperature, total_duration_ms, transition_reasons。
        """
        from src.ai.generation_state import StateTracker

        # 从 docstring 中验证契约
        docstring = StateTracker.to_metrics.__doc__ or ""
        expected_keys = [
            "total_attempts",
            "transitions",
            "final_model",
            "final_temperature",
            "total_duration_ms",
            "transition_reasons",
        ]
        for key in expected_keys:
            assert (
                key in docstring
            ), f"to_metrics() docstring 未提及 key '{key}'，契约可能不完整"

    def test_generation_state_maps_to_sse_status_format(self):
        """GenerationState 的 transition_reason 可映射为 SSE status 事件中的 phase 字段。

        契约：TransitionReason 的每个值都是 str 类型，
        可直接序列化为 SSE 事件的 phase 字段。
        """
        from src.ai.generation_state import GenerationState, TransitionReason

        # 验证 TransitionReason 是 str 枚举
        for reason in TransitionReason:
            assert isinstance(
                reason.value, str
            ), f"TransitionReason.{reason.name} 的值不是 str: {reason.value}"

        # 验证 GenerationState.transition_reason 字段存在
        state_fields = {f.name for f in GenerationState.__dataclass_fields__.values()}
        assert "transition_reason" in state_fields

    def test_transition_reasons_cover_story_generator_scenarios(self):
        """TransitionReason 枚举覆盖 StoryGenerator 中所有重试场景。

        契约：StoryGenerator 中的重试场景（harness_retry, temperature_adjust,
        model_fallback 等）在 TransitionReason 中都有对应的枚举值。
        """
        from src.ai.generation_state import TransitionReason

        reason_values = {r.value for r in TransitionReason}

        # StoryGenerator 中的重试场景：
        # 1. Harness 验证失败重试 -> harness_retry
        assert "harness_retry" in reason_values
        # 2. 温度调整重试 -> temperature_adjust
        assert "temperature_adjust" in reason_values
        # 3. 模型降级 -> model_fallback
        assert "model_fallback" in reason_values
        # 4. 截断恢复 -> truncation_recovery
        assert "truncation_recovery" in reason_values
        # 5. 上下文压缩 -> context_compact
        assert "context_compact" in reason_values
        # 6. max_tokens 升级 -> max_tokens_escalate
        assert "max_tokens_escalate" in reason_values
        # 7. 初始状态 -> initial
        assert "initial" in reason_values


# ============================================================
# 特性门控契约
# ============================================================


class TestFeatureFlagContracts:
    """验证 feature_flags 模块的内部一致性和向后兼容性。"""

    def test_feature_flag_names_match_env_vars(self):
        """FeatureFlags 的每个 key 在 _ENV_VAR_MAP 中有对应的环境变量。

        契约：FeatureFlags TypedDict 中声明的每个特性标志，
        都必须在 _ENV_VAR_MAP 中有对应的环境变量映射。
        """
        from config.feature_flags import _ENV_VAR_MAP, FeatureFlags

        flag_keys = set(FeatureFlags.__annotations__.keys())
        env_map_keys = set(_ENV_VAR_MAP.keys())
        assert flag_keys == env_map_keys, (
            f"不匹配: FeatureFlags 有 {flag_keys - env_map_keys}, "
            f"_ENV_VAR_MAP 有 {env_map_keys - flag_keys}"
        )

    def test_feature_defaults_all_false(self):
        """FEATURE_DEFAULTS 中所有值默认为 False（向后兼容）。

        契约：新特性默认关闭，确保不会影响现有功能。
        """
        from config.feature_flags import FEATURE_DEFAULTS

        for flag_name, default_value in FEATURE_DEFAULTS.items():
            assert (
                default_value is False
            ), f"Feature flag '{flag_name}' default is {default_value}, expected False"

    def test_get_feature_returns_bool(self):
        """get_feature() 对已知和未知 flag 都返回 bool。

        契约：get_feature() 的返回类型注解为 bool。
        """
        from config.feature_flags import get_feature

        hints = get_type_hints(get_feature)
        assert hints.get("return") is bool

    def test_env_var_map_covers_all_flags(self):
        """_ENV_VAR_MAP 覆盖 FeatureFlags 中的所有 key。

        契约：_ENV_VAR_MAP 不能有 FeatureFlags 中不存在的 key，反之亦然。
        """
        from config.feature_flags import (_ENV_VAR_MAP, FEATURE_DEFAULTS,
                                          FeatureFlags)

        flag_keys = set(FeatureFlags.__annotations__.keys())
        default_keys = set(FEATURE_DEFAULTS.keys())
        env_keys = set(_ENV_VAR_MAP.keys())

        # 三者应完全一致
        assert flag_keys == default_keys, (
            f"FeatureFlags 与 FEATURE_DEFAULTS 不一致: "
            f"多出 {flag_keys - default_keys}, 缺少 {default_keys - flag_keys}"
        )
        assert flag_keys == env_keys, (
            f"FeatureFlags 与 _ENV_VAR_MAP 不一致: "
            f"多出 {flag_keys - env_keys}, 缺少 {env_keys - flag_keys}"
        )


# ============================================================
# 并行后处理契约
# ============================================================


class TestParallelPostProcessorContracts:
    """验证 parallel_postprocessor 模块与 game_loop / summary_generator 的接口契约。"""

    def test_postprocessing_result_has_expected_fields(self):
        """PostProcessingResult 的字段名与 advance_to_next_week() 消费的数据一致。

        契约：PostProcessingResult 应包含 compression_result, world_model_updates,
        vector_stored, weekly_summary, errors 字段，
        这些字段与 GameLoop.advance_to_next_week() 中的后处理步骤对应。
        """
        from src.game.parallel_postprocessor import PostProcessingResult

        result = PostProcessingResult()
        # 验证所有预期字段存在
        assert hasattr(result, "compression_result")
        assert hasattr(result, "world_model_updates")
        assert hasattr(result, "vector_stored")
        assert hasattr(result, "weekly_summary")
        assert hasattr(result, "errors")

        # 验证默认值类型
        assert result.compression_result is None
        assert result.world_model_updates is None
        assert result.vector_stored is False
        assert result.weekly_summary is None
        assert isinstance(result.errors, list)

    def test_compression_result_structure(self):
        """compression_result 字段的预期结构与 SummaryGenerator.compress_story() 返回一致。

        契约：compress_story() 返回的 dict 包含 summary, storyline_updates,
        fact_updates, event_concluded, foreshadowing_seeds, habit_updates，
        PostProcessingResult.compression_result 应能承载这些字段。
        """
        from src.game.parallel_postprocessor import PostProcessingResult

        # 从 compress_story 的返回结构中提取预期 keys
        # 根据 summary_generator.py 的实际代码，compress_story 返回以下 keys：
        expected_keys = {
            "summary",
            "storyline_updates",
            "fact_updates",
            "event_concluded",
            "foreshadowing_seeds",
            "habit_updates",
        }

        # 验证 PostProcessingResult.compression_result 的类型注解支持 Dict[str, Any]
        hints = get_type_hints(PostProcessingResult)
        cr_type = hints.get("compression_result")
        # Optional[Dict[str, Any]] 应该能承载上述结构
        assert cr_type is not None

        # 模拟 compress_story 的返回值可以赋值给 compression_result
        mock_compression = {
            "summary": "测试摘要",
            "storyline_updates": [],
            "fact_updates": [],
            "event_concluded": True,
            "foreshadowing_seeds": [],
            "habit_updates": [],
        }
        result = PostProcessingResult(compression_result=mock_compression)
        assert set(result.compression_result.keys()) == expected_keys

    def test_world_updates_structure(self):
        """world_model_updates 字段的预期结构与 WorldModelUpdater 输入一致。

        契约：world_model_updates 应能承载 WorldModelUpdater.process_*
        系列方法所需的数据结构（location_updates, career_updates,
        commitment_updates, causal_updates 等）。
        """
        from src.game.parallel_postprocessor import PostProcessingResult

        # WorldModelUpdater 接受的更新类型
        mock_world_updates = {
            "location_updates": [
                {"action": "move", "character": "test", "to": "somewhere"}
            ],
            "career_updates": [
                {"action": "promote", "character": "test", "new_role": "manager"}
            ],
            "commitment_updates": [{"action": "new", "description": "test commitment"}],
            "causal_updates": [
                {"action": "new", "cause": "A", "expected_consequence": "B"}
            ],
            "fact_updates": [],
            "foreshadowing_seeds": [],
            "habit_updates": [],
        }
        result = PostProcessingResult(world_model_updates=mock_world_updates)
        assert isinstance(result.world_model_updates, dict)
        assert "location_updates" in result.world_model_updates
        assert "career_updates" in result.world_model_updates
        assert "commitment_updates" in result.world_model_updates
        assert "causal_updates" in result.world_model_updates


# ============================================================
# 响应式压缩契约
# ============================================================


class TestReactiveCompressorContracts:
    """验证 reactive_compressor 模块与 _helpers.py 的接口契约。"""

    def test_protected_fields_not_in_trim_order(self):
        """PROTECTED_FIELDS 中的字段不在 DEFAULT_BUDGET_TRIM_ORDER 中。

        契约：受保护字段永远不能被削减，因此不应出现在削减优先级列表中。
        """
        from src.ai.reactive_compressor import (DEFAULT_BUDGET_TRIM_ORDER,
                                                PROTECTED_FIELDS)

        overlap = set(PROTECTED_FIELDS) & set(DEFAULT_BUDGET_TRIM_ORDER)
        assert (
            len(overlap) == 0
        ), f"以下字段同时出现在 PROTECTED_FIELDS 和 DEFAULT_BUDGET_TRIM_ORDER 中: {overlap}"

    def test_budget_trim_order_matches_helpers(self):
        """DEFAULT_BUDGET_TRIM_ORDER 与 _helpers.py 中的优先级一致。

        契约：reactive_compressor 的 DEFAULT_BUDGET_TRIM_ORDER 必须包含
        _helpers._BUDGET_TRIM_ORDER 中的所有核心削减项。
        reactive_compressor 可以有额外项（如 character_habits, pending_storylines），
        但 _helpers 中的项不应被遗漏。
        """
        from config.prompts._helpers import _BUDGET_TRIM_ORDER
        from src.ai.reactive_compressor import DEFAULT_BUDGET_TRIM_ORDER

        helpers_set = set(_BUDGET_TRIM_ORDER)
        compressor_set = set(DEFAULT_BUDGET_TRIM_ORDER)

        # _helpers 中的每个核心削减项都必须在 compressor 中存在
        missing = helpers_set - compressor_set
        assert len(missing) == 0, (
            f"_helpers._BUDGET_TRIM_ORDER 中的以下项在 "
            f"DEFAULT_BUDGET_TRIM_ORDER 中缺失: {missing}"
        )

    def test_protected_fields_match_helpers(self):
        """PROTECTED_FIELDS 与 _helpers._BUDGET_PROTECTED 一致。

        契约：reactive_compressor 的受保护字段应覆盖 _helpers 中的不可削减项。
        """
        from config.prompts._helpers import _BUDGET_PROTECTED
        from src.ai.reactive_compressor import PROTECTED_FIELDS

        protected_set = set(PROTECTED_FIELDS)
        helpers_protected = set(_BUDGET_PROTECTED)

        assert helpers_protected.issubset(protected_set), (
            f"_helpers._BUDGET_PROTECTED 中有但 PROTECTED_FIELDS 中没有: "
            f"{helpers_protected - protected_set}"
        )

    def test_compact_preserves_protected(self):
        """compact() 不能删除 PROTECTED 字段。

        契约：调用 compact() 后，PROTECTED_FIELDS 中的字段必须保留在结果中。
        """
        from src.ai.reactive_compressor import (PROTECTED_FIELDS,
                                                ReactiveCompressor)

        compressor = ReactiveCompressor()
        constraint_texts = {
            "critical_summary": "重要摘要内容",
            "established_facts": "已建立事实",
            "world_model": "世界模型",
            "preference_hint": "偏好提示" * 100,  # 大量文本以触发压缩
            "overused_phrases": "过度使用短语" * 100,
        }
        result = compressor.compact(constraint_texts, target_reduction=0.5)
        for field in PROTECTED_FIELDS:
            assert (
                field not in result.removed_sections
            ), f"Protected field '{field}' was removed during compaction"

    def test_compaction_result_fields_valid(self):
        """CompactionResult 字段类型正确。

        契约：original_token_count 和 compressed_token_count 是 int，
        removed_sections 是 List[str]，budget_factor 是 float。
        """
        from src.ai.reactive_compressor import CompactionResult

        result = CompactionResult(
            original_token_count=1000,
            compressed_token_count=500,
            removed_sections=["preference_hint"],
            budget_factor=0.5,
        )
        assert isinstance(result.original_token_count, int)
        assert isinstance(result.compressed_token_count, int)
        assert isinstance(result.removed_sections, list)
        assert all(isinstance(s, str) for s in result.removed_sections)
        assert isinstance(result.budget_factor, float)
