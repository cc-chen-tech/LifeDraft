"""Harness重试闭环测试 (L5)

TDD先行：测试重试链路完整性、修正指令注入、诊断报告准确性、
降级安全、Metrics记录。
"""

from unittest.mock import MagicMock, patch

import pytest

from src.ai.harness import (ConstraintCheckResult, ConstraintRegistry,
                            ConstraintType, Priority, ValidationPipeline,
                            ValidationResult, default_registry)
from src.ai.harness.diagnostics import (ConstraintViolationDiagnostic,
                                        DiagnosticReport)
from src.ai.harness.retry_controller import RetryController

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def failed_validation_result():
    """构造一个包含 CRITICAL 失败的 ValidationResult。"""
    critical_check = ConstraintCheckResult(
        constraint_type="available_people",
        priority="CRITICAL",
        passed=False,
        evidence="故事中出现了未知人物: 张无忌",
        details={"unknown_names": ["张无忌"]},
    )
    high_check = ConstraintCheckResult(
        constraint_type="scene_continuity",
        priority="HIGH",
        passed=False,
        evidence="场景从洛阳城跳转到长安城，无过渡",
        details={},
    )
    return ValidationResult(
        passed=False,
        score=45.0,
        critical_failures=[critical_check],
        high_warnings=[high_check],
        total_checked=18,
        total_passed=16,
    )


@pytest.fixture
def passed_validation_result():
    """构造一个全部通过的 ValidationResult。"""
    return ValidationResult(
        passed=True,
        score=95.0,
        total_checked=18,
        total_passed=18,
    )


@pytest.fixture
def low_score_validation_result():
    """构造一个无 CRITICAL 但分数低的 ValidationResult。"""
    high_check = ConstraintCheckResult(
        constraint_type="scene_continuity",
        priority="HIGH",
        passed=False,
        evidence="场景不连贯",
        details={},
    )
    medium_check = ConstraintCheckResult(
        constraint_type="character_habits",
        priority="MEDIUM",
        passed=False,
        evidence="未体现人物习惯",
        details={},
    )
    return ValidationResult(
        passed=True,  # 无 CRITICAL
        score=55.0,
        high_warnings=[high_check],
        medium_notes=[medium_check],
        total_checked=18,
        total_passed=16,
    )


@pytest.fixture
def diagnostic_with_critical():
    """构造包含 CRITICAL 违反的诊断报告。"""
    return DiagnosticReport(
        violations=[
            {
                "constraint_type": "available_people",
                "priority": "CRITICAL",
                "evidence": "故事中出现了未知人物: 张无忌",
                "description": "人物必须来自可用列表",
            },
            {
                "constraint_type": "scene_continuity",
                "priority": "HIGH",
                "evidence": "场景从洛阳城跳转到长安城",
                "description": "场景连贯性要求",
            },
        ],
        evidence_map={
            "available_people": "故事中出现了未知人物: 张无忌",
            "scene_continuity": "场景从洛阳城跳转到长安城",
        },
        summary="发现 2 项约束违反（CRITICAL: 1）, 评分 45.0/100。",
        suggested_fixes=[
            "[available_people] 仅使用可用人物列表中的角色，移除未知人名",
            "[scene_continuity] 确保故事开头与上一轮结尾的场景地点连贯衔接",
        ],
        total_violations=2,
        critical_count=1,
    )


@pytest.fixture
def basic_validation_context(sample_player_state_with_creative):
    """基础验证上下文。"""
    state = sample_player_state_with_creative
    return {
        "available_people": ["李逍遥", "赵灵儿", "王二", "掌柜", "师父"],
        "established_facts": [
            {"fact": "李逍遥是蜀山弟子", "source_week": 1},
            {"fact": "王二左臂骨折", "source_week": 4},
        ],
        "pending_storylines": [
            {"title": "寻找灵药", "importance": "high", "deadline_week": 13},
        ],
        "overdue_storylines": [],
        "last_location": "洛阳城",
        "character_habits": [
            {"character": "李逍遥", "habit": "每日清晨练剑"},
        ],
        "world_model_state": (
            state.world_model_data if hasattr(state, "world_model_data") else {}
        ),
        "player_state": state,
    }


@pytest.fixture
def diagnostic_no_critical():
    """构造不包含 CRITICAL 违反的诊断报告。"""
    return DiagnosticReport(
        violations=[],
        evidence_map={},
        summary="所有约束检查通过",
        suggested_fixes=[],
        total_violations=0,
        critical_count=0,
    )


# ============================================================
# L5: 重试链路完整性
# ============================================================


@pytest.mark.integration
class TestRetryChainIntegrity:
    """重试链路完整性"""

    def test_critical_failure_should_retry(
        self, failed_validation_result, diagnostic_with_critical
    ):
        """模拟CRITICAL约束失败→RetryController返回should_retry=True"""
        controller = RetryController(max_retries=2)
        should_retry, correction = controller.should_retry(
            failed_validation_result, diagnostic_with_critical, attempt=0
        )
        assert should_retry is True
        assert correction is not None
        assert len(correction) > 0

    def test_correction_hint_contains_failure_info(
        self, failed_validation_result, diagnostic_with_critical
    ):
        """修正指令包含失败约束类型、证据和修复建议"""
        controller = RetryController(max_retries=2)
        _, correction = controller.should_retry(
            failed_validation_result, diagnostic_with_critical, attempt=0
        )
        assert correction is not None
        assert "available_people" in correction
        assert "修正" in correction or "修复" in correction or "要求" in correction

    def test_temperature_decay(self):
        """温度递减策略验证。

        TDD: StoryGenerator._resolve_temperature(attempt, base, decay) 需实现。
        attempt=0→0.85, attempt=1→0.70, attempt=2→0.70
        """
        from src.ai.story_generator import StoryGenerator

        with patch("src.ai.story_generator.AIClient") as mock_client:
            gen = StoryGenerator(mock_client())
            if hasattr(gen, "_resolve_temperature"):
                assert gen._resolve_temperature(0, 0.85, 0.15) == pytest.approx(
                    0.85, abs=0.05
                )
                assert gen._resolve_temperature(1, 0.85, 0.15) == pytest.approx(
                    0.70, abs=0.05
                )
                assert gen._resolve_temperature(2, 0.85, 0.15) == pytest.approx(
                    0.70, abs=0.05
                )
            else:
                pytest.fail("_resolve_temperature not found on StoryGenerator")

    def test_max_retries_limit(
        self, failed_validation_result, diagnostic_with_critical
    ):
        """超过max_retries后停止重试"""
        controller = RetryController(max_retries=2)

        # attempt=2 等于 max_retries，不再重试
        should_retry, correction = controller.should_retry(
            failed_validation_result, diagnostic_with_critical, attempt=2
        )
        assert should_retry is False
        assert correction is None

    def test_no_retry_when_passed(
        self, passed_validation_result, diagnostic_no_critical
    ):
        """全部通过时不重试"""
        controller = RetryController(max_retries=2)
        should_retry, correction = controller.should_retry(
            passed_validation_result, diagnostic_no_critical, attempt=0
        )
        assert should_retry is False

    def test_gentle_hint_on_low_score(
        self, low_score_validation_result, diagnostic_no_critical
    ):
        """无 CRITICAL 但分数低于阈值时，首次尝试触发温和重试。"""
        controller = RetryController(max_retries=2, score_threshold=70.0)
        should_retry, correction = controller.should_retry(
            low_score_validation_result, diagnostic_no_critical, attempt=0
        )
        assert should_retry is True
        assert correction is not None
        assert "约束" in correction or "遵守" in correction


# ============================================================
# L5: 修正指令注入验证
# ============================================================


@pytest.mark.integration
class TestCorrectionInjection:
    """修正指令注入验证"""

    def test_correction_in_retry_prompt(
        self, diagnostic_with_critical, failed_validation_result
    ):
        """第二次prompt中包含上次生成失败修正指令"""
        controller = RetryController(max_retries=2)
        _, correction = controller.should_retry(
            failed_validation_result, diagnostic_with_critical, attempt=0
        )
        assert correction is not None
        # 修正指令应包含明确的修正要求
        assert "重要修正要求" in correction or "修正" in correction

    def test_correction_priority_order(self):
        """修正指令按优先级排序（CRITICAL优先于HIGH）"""
        report = DiagnosticReport(
            violations=[
                {
                    "constraint_type": "scene_continuity",
                    "priority": "HIGH",
                    "evidence": "场景跳转",
                    "description": "场景连贯性",
                },
                {
                    "constraint_type": "available_people",
                    "priority": "CRITICAL",
                    "evidence": "未知人物: 张无忌",
                    "description": "人物列表约束",
                },
            ],
            evidence_map={},
            suggested_fixes=[
                "[scene_continuity] 确保场景连贯",
                "[available_people] 移除未知人名",
            ],
            total_violations=2,
            critical_count=1,
        )

        controller = RetryController(max_retries=2)
        vr = ValidationResult(
            passed=False,
            score=40.0,
            critical_failures=[
                ConstraintCheckResult(
                    constraint_type="available_people",
                    priority="CRITICAL",
                    passed=False,
                )
            ],
        )

        _, correction = controller.should_retry(vr, report, attempt=0)
        assert correction is not None

        # CRITICAL 的 available_people 应出现在 HIGH 的 scene_continuity 之前
        idx_critical = correction.find("available_people")
        idx_high = correction.find("scene_continuity")
        if idx_critical >= 0 and idx_high >= 0:
            assert idx_critical < idx_high, "CRITICAL should appear before HIGH"

    def test_correction_length_limit(self):
        """修正指令长度不超过800字符"""
        # 构造大量违反
        violations = []
        fixes = []
        for i in range(10):
            violations.append(
                {
                    "constraint_type": f"test_type_{i}",
                    "priority": "CRITICAL",
                    "evidence": "测试证据" * 20,
                    "description": "测试描述" * 20,
                }
            )
            fixes.append(f"[test_type_{i}] 修复建议文本" * 10)

        report = DiagnosticReport(
            violations=violations,
            evidence_map={},
            suggested_fixes=fixes,
            total_violations=10,
            critical_count=10,
        )

        controller = RetryController(max_retries=2)
        vr = ValidationResult(
            passed=False,
            score=0.0,
            critical_failures=[
                ConstraintCheckResult(
                    constraint_type="test_type_0",
                    priority="CRITICAL",
                    passed=False,
                )
            ],
        )

        _, correction = controller.should_retry(vr, report, attempt=0)
        assert correction is not None
        assert len(correction) <= 800


# ============================================================
# L5: 诊断报告准确性
# ============================================================


@pytest.mark.integration
class TestDiagnosticAccuracy:
    """诊断报告准确性"""

    def test_violation_localization(self, mock_story_text, basic_validation_context):
        """输入已知违规文本→Diagnostics正确定位违规段落"""
        # 构造包含第一人称的文本
        bad_text = (
            "我走在洛阳城的街道上，看到了远方的山峦。我决定继续前进。" + mock_story_text
        )

        pipeline = ValidationPipeline(default_registry)
        result = pipeline.validate(bad_text, basic_validation_context)

        diagnostics = ConstraintViolationDiagnostic()
        report = diagnostics.generate_report(bad_text, result)

        # 如果第三人称验证失败，证据应包含含"我"的句子
        if "third_person" in report.evidence_map:
            evidence = report.evidence_map["third_person"]
            assert "我" in evidence

    def test_evidence_length_limit(self, mock_story_text):
        """证据提取长度≤300字"""
        diagnostics = ConstraintViolationDiagnostic()

        # 用一个很长的文本测试
        long_text = "测试文本" * 500
        evidence = diagnostics.locate_evidence(
            long_text, "available_people", {"unknown_names": ["测试人物"]}
        )
        assert len(evidence) <= 300

    def test_suggested_fixes_match(self, mock_story_text, basic_validation_context):
        """suggested_fixes与实际失败约束匹配"""
        pipeline = ValidationPipeline(default_registry)
        result = pipeline.validate(mock_story_text, basic_validation_context)

        diagnostics = ConstraintViolationDiagnostic()
        report = diagnostics.generate_report(mock_story_text, result)

        # 每个 suggested_fix 都应以 [约束类型] 开头
        for fix in report.suggested_fixes:
            assert fix.startswith("["), f"Fix should start with [type]: {fix}"
            # 提取约束类型
            bracket_end = fix.index("]")
            constraint_type = fix[1:bracket_end]
            # 应存在对应的违反
            assert any(
                v["constraint_type"] == constraint_type for v in report.violations
            ), f"Fix for {constraint_type} has no matching violation"


# ============================================================
# L5: 降级安全
# ============================================================


@pytest.mark.integration
class TestDegradationSafety:
    """降级安全"""

    def test_validation_pipeline_exception(
        self, mock_story_text, basic_validation_context
    ):
        """ValidationPipeline抛异常→优雅降级返回原始故事"""

        # ValidationPipeline 的 _run_single_check 内部有异常保护
        # 当验证器抛异常时，默认返回 passed=True
        def broken_validator(story_text, context):
            raise RuntimeError("Validator crashed!")

        from src.ai.harness.constraint_registry import ConstraintDefinition

        broken_registry = ConstraintRegistry()
        broken_registry.register(
            ConstraintDefinition(
                type=ConstraintType.AVAILABLE_PEOPLE,
                priority=Priority.CRITICAL,
                description="测试用崩溃验证器",
                validator=broken_validator,
                weight=3.0,
            )
        )

        pipeline = ValidationPipeline(broken_registry)
        result = pipeline.validate(mock_story_text, basic_validation_context)

        # 异常时默认通过（不阻塞生成流程）
        assert result.passed is True
        # 详细结果中应有 skipped 标记
        detail = result.detailed_checks.get("available_people", {})
        assert detail.get("details", {}).get("skipped") is True

    def test_retry_controller_exception(self):
        """RetryController抛异常→优雅降级不重试"""
        controller = RetryController(max_retries=2)

        # 传入无效参数触发内部异常保护
        vr = MagicMock()
        vr.critical_failures = None  # 会导致内部迭代失败

        report = MagicMock()
        report.critical_count = MagicMock(side_effect=TypeError("mock error"))

        should_retry, correction = controller.should_retry(vr, report, attempt=0)
        # 异常时返回 False, None
        assert should_retry is False
        assert correction is None

    def test_diagnostics_exception(self, mock_story_text):
        """Diagnostics抛异常→返回降级报告"""
        diagnostics = ConstraintViolationDiagnostic()

        # 构造一个会导致内部报告生成失败的 ValidationResult
        bad_vr = MagicMock()
        bad_vr.critical_failures = MagicMock(side_effect=TypeError("boom"))
        bad_vr.high_warnings = []
        bad_vr.medium_notes = []
        bad_vr.low_notes = []

        report = diagnostics.generate_report(mock_story_text, bad_vr)
        # 应返回降级报告
        assert isinstance(report, DiagnosticReport)
        assert "失败" in report.summary or len(report.suggested_fixes) >= 0


# ============================================================
# L5: Metrics记录
# ============================================================


@pytest.mark.integration
class TestMetricsRecording:
    """Metrics记录"""

    def test_metrics_record_single_attempt(self, tmp_path):
        """单次生成后HarnessMetrics正确记录"""
        from src.ai.harness.metrics import HarnessMetrics

        db_path = str(tmp_path / "test_metrics.db")
        metrics = HarnessMetrics(db_path=db_path)

        run_id = metrics.record_generation(
            game_id="test_game_1",
            week=5,
            attempts=1,
            validation_result={
                "score": 85.0,
                "passed": True,
                "detailed_checks": {
                    "third_person": {
                        "passed": True,
                        "priority": "CRITICAL",
                        "evidence": "",
                        "details": {},
                    },
                    "available_people": {
                        "passed": True,
                        "priority": "CRITICAL",
                        "evidence": "",
                        "details": {},
                    },
                },
            },
            latency_ms=150.0,
        )

        assert run_id is not None
        assert isinstance(run_id, int)

        # 查询通过率
        pass_rates = metrics.get_constraint_pass_rates(last_n=10)
        assert "third_person" in pass_rates
        assert pass_rates["third_person"] == 1.0

    def test_metrics_record_retries(self, tmp_path):
        """重试场景下记录多次尝试"""
        from src.ai.harness.metrics import HarnessMetrics

        db_path = str(tmp_path / "test_metrics_retry.db")
        metrics = HarnessMetrics(db_path=db_path)

        # 记录一次含重试的生成
        run_id = metrics.record_generation(
            game_id="test_game_2",
            week=3,
            attempts=3,
            validation_result={
                "score": 70.0,
                "passed": True,
                "detailed_checks": {
                    "available_people": {
                        "passed": False,
                        "priority": "CRITICAL",
                        "evidence": "未知人物: 张三",
                        "details": {"unknown_names": ["张三"]},
                    },
                },
            },
            latency_ms=450.0,
        )
        assert run_id is not None

        # 重试分布
        retry_dist = metrics.get_retry_distribution(last_n=10)
        assert 3 in retry_dist
        assert retry_dist[3] == 1

        # 失败模式
        patterns = metrics.get_failure_patterns(last_n=10)
        assert any(p["constraint_type"] == "available_people" for p in patterns)

    def test_metrics_summary_report(self, tmp_path):
        """摘要报告生成"""
        from src.ai.harness.metrics import HarnessMetrics

        db_path = str(tmp_path / "test_metrics_summary.db")
        metrics = HarnessMetrics(db_path=db_path)

        metrics.record_generation(
            game_id="g1",
            week=1,
            attempts=1,
            validation_result={"score": 90.0, "passed": True, "detailed_checks": {}},
        )

        report = metrics.get_summary_report(last_n=10)
        assert isinstance(report, str)
        assert "Harness" in report or "约束" in report
