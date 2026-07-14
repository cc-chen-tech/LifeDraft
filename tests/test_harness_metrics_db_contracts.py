from pathlib import Path

from src.ai.harness.metrics import HarnessMetrics


def _record_runs(metrics: HarnessMetrics) -> None:
    first = metrics.record_generation(
        game_id="game-7",
        week=3,
        attempts=1,
        preflight_result={"all_present": False, "missing_constraints": ["cast"]},
        validation_result={
            "score": 0.4,
            "passed": False,
            "detailed_checks": {
                "cast": {
                    "priority": "P0",
                    "passed": False,
                    "evidence": "required character absent",
                    "details": {"missing": "沈砚"},
                },
                "continuity": {
                    "priority": "P1",
                    "passed": True,
                    "evidence": "timeline preserved",
                    "details": {},
                },
            },
        },
        token_usage=120,
        latency_ms=35.5,
        error_message="validation rejected",
    )
    second = metrics.record_generation(
        game_id="game-7",
        week=4,
        attempts=3,
        validation_result={
            "score": 0.9,
            "passed": True,
            "detailed_checks": {
                "cast": {
                    "priority": "P0",
                    "passed": True,
                    "evidence": "cast restored",
                    "details": {},
                }
            },
        },
    )

    assert isinstance(first, int)
    assert isinstance(second, int)


def test_harness_metrics_persists_checks_and_returns_aggregates(tmp_path: Path):
    metrics = HarnessMetrics(str(tmp_path / "metrics.sqlite"))
    _record_runs(metrics)

    assert metrics.get_constraint_pass_rates() == {"cast": 0.5, "continuity": 1.0}
    assert metrics.get_retry_distribution() == {1: 1, 3: 1}
    assert metrics.get_failure_patterns() == [
        {
            "constraint_type": "cast",
            "failure_count": 1,
            "recent_evidence": ["required character absent"],
        }
    ]


def test_harness_metrics_reports_empty_and_recorded_statuses(tmp_path: Path):
    empty_metrics = HarnessMetrics(str(tmp_path / "empty.sqlite"))
    assert "暂无数据" in empty_metrics.get_summary_report()

    populated_metrics = HarnessMetrics(str(tmp_path / "populated.sqlite"))
    _record_runs(populated_metrics)
    report = populated_metrics.get_summary_report(last_n=2)

    assert "cast: 50.0% [FAIL]" in report
    assert "continuity: 100.0% [OK]" in report
    assert "3次尝试: 1次" in report
    assert "cast: 1次失败" in report
    assert "证据: required character absent..." in report
