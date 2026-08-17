"""No-double public contracts for constraint diagnostics."""

from src.ai.harness.diagnostics import ConstraintViolationDiagnostic
from src.ai.harness.validation_pipeline import ConstraintCheckResult, ValidationResult
import pytest

pytestmark = [pytest.mark.unit]



def test_unknown_person_failure_has_evidence_and_critical_fix():
    result = ValidationResult(
        passed=False,
        score=85.0,
        critical_failures=[
            ConstraintCheckResult(
                constraint_type="available_people",
                priority="CRITICAL",
                passed=False,
                evidence="出现未知人物",
                details={"unknown_names": ["王五"]},
            )
        ],
    )

    report = ConstraintViolationDiagnostic().generate_report("王五走进了客栈。", result)

    assert report.total_violations == 1
    assert report.critical_count == 1
    assert "王五" in report.evidence_map["available_people"]
    assert report.suggested_fixes[0].startswith("[available_people]")
    assert "关键违反: available_people" in report.summary


def test_first_person_and_meta_evidence_are_located():
    diagnostic = ConstraintViolationDiagnostic()

    first_person = diagnostic.locate_evidence("我走进房间。他随后离开。", "third_person", {})
    meta = diagnostic.locate_evidence(
        "任意故事", "no_meta_narration", {"violations": ["作为AI，我不能这样写"]}
    )

    assert "我走进房间" in first_person
    assert "作为AI" in meta


def test_passing_result_has_empty_report_and_score_summary():
    report = ConstraintViolationDiagnostic().generate_report(
        "李逍遥走进洛阳城。", ValidationResult(passed=True, score=100.0)
    )

    assert report.total_violations == 0
    assert report.critical_count == 0
    assert report.violations == []
    assert report.summary == "所有约束检查通过，评分 100.0/100"
