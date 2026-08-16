from src.ai.story_validation import (
    FindingSeverity,
    ValidationFinding,
    findings_from_legacy,
)
from src.ai.quick_validator import quick_validate_story


def test_coverage_diagnostic_is_a_warning_finding() -> None:
    findings = findings_from_legacy(
        issues=[],
        warnings=["上一版故事预设关系网覆盖低于建议值（已使用2/3）"],
        source="quick_validator",
    )

    assert findings == [
        ValidationFinding(
            code="CAST_COVERAGE_LOW",
            severity=FindingSeverity.WARNING,
            confidence=0.35,
            source="quick_validator",
            message="上一版故事预设关系网覆盖低于建议值（已使用2/3）",
            evidence="",
            repair_instruction="",
        )
    ]


def test_high_confidence_role_alias_is_a_hard_finding() -> None:
    findings = findings_from_legacy(
        issues=["上一版故事出现名单外命名角色（马老板）"],
        warnings=[],
        source="quick_validator",
    )

    assert findings[0].code == "HIGH_CONFIDENCE_UNKNOWN_PERSON"
    assert findings[0].severity is FindingSeverity.HARD
    assert findings[0].confidence == 0.95
    assert findings[0].fingerprint


def test_finding_fingerprint_is_stable_for_equivalent_whitespace() -> None:
    first = ValidationFinding(
        code="REQUIRED_CAST_MISSING",
        severity=FindingSeverity.HARD,
        confidence=1.0,
        source="quick_validator",
        message="玄奘  没有登场",
        evidence="玄奘",
        repair_instruction="让玄奘登场",
    )
    second = ValidationFinding(
        code="REQUIRED_CAST_MISSING",
        severity=FindingSeverity.HARD,
        confidence=1.0,
        source="quick_validator",
        message="玄奘 没有登场",
        evidence="玄奘",
        repair_instruction="换一种措辞",
    )

    assert first.fingerprint == second.fingerprint


def test_english_named_person_with_role_and_responsibility_is_hard() -> None:
    result = quick_validate_story(
        "John Smith, her new mentor, took over the project and told Alice what to do.",
        available_people=["Alice Chen"],
        language="en",
    )

    assert result.passed is False
    assert any(
        finding.code == "HIGH_CONFIDENCE_UNKNOWN_PERSON"
        and finding.severity is FindingSeverity.HARD
        for finding in result.findings
    )


def test_english_capitalized_place_without_person_semantics_is_not_hard() -> None:
    result = quick_validate_story(
        "Alice Chen watched the sunrise over Golden Gate Bridge before work.",
        available_people=["Alice Chen"],
        language="en",
    )

    assert all(finding.severity is not FindingSeverity.HARD for finding in result.findings)


def test_english_capitalized_time_or_place_is_not_bound_to_nearby_person_action() -> None:
    result = quick_validate_story(
        "On Monday Morning, the team gathered at The New York office. "
        "John Smith, her approved mentor, said hello.",
        available_people=["John Smith"],
        language="en",
    )

    assert all(finding.severity is not FindingSeverity.HARD for finding in result.findings)
