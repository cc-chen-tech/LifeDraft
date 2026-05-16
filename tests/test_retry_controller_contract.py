"""Retry controller contract tests.

No mocks. Uses hand-rolled stub diagnostic reports and validation results.
"""

from src.ai.harness.retry_controller import RetryController


class FakeValidationResult:
    """Stub validation result."""

    def __init__(self, score=100.0, high_warnings=None, medium_notes=None, low_notes=None):
        self.score = score
        self.high_warnings = high_warnings or []
        self.medium_notes = medium_notes or []
        self.low_notes = low_notes or []


class FakeDiagnosticReport:
    """Stub diagnostic report."""

    def __init__(self, critical_count=0, violations=None, suggested_fixes=None):
        self.critical_count = critical_count
        self.violations = violations or []
        self.suggested_fixes = suggested_fixes or []
        self.summary = ""


class TestRetryControllerContract:
    """Contract tests for retry controller."""

    def test_should_retry_exceeds_max(self):
        """Attempt >= max_retries should not retry."""
        controller = RetryController()
        result = FakeValidationResult(score=50)
        report = FakeDiagnosticReport()

        should, hint = controller.should_retry(result, report, attempt=3)
        assert should is False
        assert hint is None

    def test_should_retry_critical_failure(self):
        """Critical failures should always trigger retry."""
        controller = RetryController()
        result = FakeValidationResult(score=100)
        report = FakeDiagnosticReport(
            critical_count=2,
            violations=[
                {
                    "priority": "CRITICAL",
                    "constraint_type": "test",
                    "description": "bad",
                    "evidence": "x",
                }
            ],
        )

        should, hint = controller.should_retry(result, report, attempt=0)
        assert should is True
        assert hint is not None
        assert "修正要求" in hint

    def test_should_retry_low_score(self):
        """Score below threshold should trigger retry."""
        controller = RetryController()
        result = FakeValidationResult(score=50)
        report = FakeDiagnosticReport()

        should, hint = controller.should_retry(result, report, attempt=0)
        assert should is True
        assert hint is not None

    def test_should_retry_high_score_no_issues(self):
        """High score with no issues should not retry."""
        controller = RetryController()
        result = FakeValidationResult(score=95)
        report = FakeDiagnosticReport()

        should, hint = controller.should_retry(result, report, attempt=0)
        assert should is False
        assert hint is None

    def test_should_retry_master_high_warnings(self):
        """MASTER profile with high warnings should retry."""
        from src.ai.harness.quality_level import PROFILES, QualityLevel

        controller = RetryController(profile=PROFILES[QualityLevel.MASTER])
        # Create fake high warning
        fw = type("FW", (), {"constraint_type": "test", "passed": False})()
        result = FakeValidationResult(score=95, high_warnings=[fw])
        report = FakeDiagnosticReport()

        should, hint = controller.should_retry(result, report, attempt=0)
        assert should is True

    def test_build_correction_prompt(self):
        """Correction prompt should contain violation details."""
        controller = RetryController()
        report = FakeDiagnosticReport(
            violations=[
                {
                    "priority": "CRITICAL",
                    "constraint_type": "length",
                    "description": "too long",
                    "evidence": "text is 2000 chars",
                },
            ],
            suggested_fixes=["[length] shorten it"],
        )

        prompt = controller._build_correction_prompt(report)
        assert "修正要求" in prompt
        assert "too long" in prompt
        assert "shorten it" in prompt

    def test_build_correction_prompt_truncates_evidence(self):
        """Long evidence should be truncated."""
        controller = RetryController()
        report = FakeDiagnosticReport(
            violations=[
                {
                    "priority": "CRITICAL",
                    "constraint_type": "test",
                    "description": "bad",
                    "evidence": "x" * 200,
                },
            ]
        )

        prompt = controller._build_correction_prompt(report)
        assert "..." in prompt or len(prompt) < 900

    def test_build_correction_prompt_max_length(self):
        """Prompt should not exceed max length."""
        controller = RetryController()
        report = FakeDiagnosticReport(
            violations=[
                {
                    "priority": "CRITICAL",
                    "constraint_type": "test",
                    "description": "bad" + "!" * 500,
                    "evidence": "x" * 500,
                }
                for _ in range(10)
            ]
        )

        prompt = controller._build_correction_prompt(report)
        assert len(prompt) <= 800

    def test_get_fix_for_type(self):
        """Should extract fix matching constraint type."""
        controller = RetryController()
        report = FakeDiagnosticReport(suggested_fixes=["[length] shorten", "[style] fix tone"])
        fix = controller._get_fix_for_type("length", report)
        assert fix == "shorten"

    def test_get_fix_for_type_missing(self):
        """Missing fix should return empty string."""
        controller = RetryController()
        report = FakeDiagnosticReport(suggested_fixes=[])
        fix = controller._get_fix_for_type("length", report)
        assert fix == ""

    def test_build_gentle_hint_with_failures(self):
        """Gentle hint should list failed constraint types."""
        controller = RetryController()
        fw = type("FW", (), {"constraint_type": "length", "passed": False})()
        result = FakeValidationResult(high_warnings=[fw])

        hint = controller._build_gentle_hint(result)
        assert "length" in hint

    def test_build_gentle_hint_no_failures(self):
        """No failures should give generic hint."""
        controller = RetryController()
        result = FakeValidationResult()

        hint = controller._build_gentle_hint(result)
        assert "遵守" in hint

    def test_should_retry_exception_safety(self):
        """Exception in should_retry should return False, None."""
        controller = RetryController()
        # Pass something that will cause exception
        should, hint = controller.should_retry(None, None, attempt=0)
        assert should is False
        assert hint is None

    def test_build_correction_prompt_exception_safety(self):
        """Exception in build_correction_prompt should return fallback."""
        controller = RetryController()
        prompt = controller._build_correction_prompt(None)
        assert "重要修正要求" in prompt
