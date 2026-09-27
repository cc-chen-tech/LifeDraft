"""Keyword absence is an editorial signal, not proof that a story is unplayable."""

import logging

import pytest

from src.ai.daily_opening import split_daily_opening_issues, validate_daily_first_opening
from src.ai.harness import default_registry
from src.ai.harness.constraint_registry import ConstraintRegistry, ConstraintType
from src.ai.harness.diagnostics import ConstraintViolationDiagnostic
from src.ai.harness.quality_level import PROFILES, QualityLevel
from src.ai.harness.retry_controller import RetryController
from src.ai.harness.validation_pipeline import ValidationPipeline


@pytest.mark.parametrize('language,name,vision,story', [
    ('zh', '林岚', '开一间社区书店',
     '林岚想开一间社区书店，租约上的押金是她积蓄的三倍。\n\n'
     '房东把钢笔推到桌沿，林岚的手停在签名栏上方。'),
    ('en', 'Mira', 'open a bookshop',
     'Mira hoped to open a bookshop; the deposit was three times her savings.\n\n'
     'The landlord pushed a pen across the table; Mira held her hand over the signature line.'),
])
def test_implicit_opening_conflict_is_advisory(language, name, vision, story):
    state = {'player_name': name, 'life_vision': vision, 'timeline': {'version': 2, 'day_index': 0}}
    issues = validate_daily_first_opening(story, state, {'name': name}, language)
    assert 'daily_opening_missing_core_conflict' in issues
    hard, warnings = split_daily_opening_issues(issues)
    assert hard == []
    assert 'daily_opening_missing_core_conflict' in warnings
    # Placement of the name is editorial; identity drift has shared checks.
    missing = validate_daily_first_opening(story.replace(name, '旅人'), state, {'name': name}, language)
    assert 'daily_opening_missing_protagonist' in split_daily_opening_issues(missing)[1]


@pytest.mark.parametrize('quality', list(QualityLevel))
@pytest.mark.parametrize('story', [
    '房东把钢笔推到桌沿，林岚的手停在签名栏上方。',
    'Mira held the unsigned lease beside the return ticket, her hand suspended above the table.',
])
def test_implicit_decision_never_rejects_deducts_score_or_retries(quality, story, caplog):
    registry = ConstraintRegistry()
    rule = default_registry.get(ConstraintType.DECISION_POINT_ENDING)
    assert rule is not None
    registry.register(rule)
    profile = PROFILES[quality]
    with caplog.at_level(logging.INFO, logger='diagnostic'):
        result = ValidationPipeline(registry).validate(story, {}, profile=profile)
    assert result.passed
    assert result.critical_failures == []
    assert result.score == 100
    report = ConstraintViolationDiagnostic().generate_report(story, result)
    assert RetryController(profile=profile).should_retry(result, report, 0) == (False, None)
    if quality is not QualityLevel.FAST:
        assert result.low_notes[0].constraint_type == 'decision_point_ending'
        events = [r.event_data for r in caplog.records if hasattr(r, 'event_data')]
        assert any(e['finding_codes'] == ['decision_point_ending'] and e['outcome'] == 'warning' for e in events)


@pytest.mark.parametrize('language', ['zh', 'en'])
@pytest.mark.parametrize('quality', ['fast', 'expert', 'master'])
def test_first_day_prompt_has_guidance_without_extra_hard_requirements(language, quality):
    from config.prompts.story_prompts import build_daily_story_mode_constraint
    from config.prompts._helpers import _build_common_story_constraints

    state = {'player_name': 'Mira', 'life_vision': 'open a bookshop',
             'timeline': {'version': 2, 'day_index': 0, 'day_number': 1, 'current_date': '2026-08-13'}}
    opening = build_daily_story_mode_constraint(state, {}, language)
    assert '[MUST]' not in opening and '[SHOULD]' in opening
    assert 'Mira' in opening and 'open a bookshop' in opening
    assert '第一段只能有一句' not in opening
    assert 'first paragraph must be exactly one sentence' not in opening
    ending = _build_common_story_constraints(language, quality)
    heading = '**故事结尾要求**' if language == 'zh' else '**STORY ENDING REQUIREMENT**'
    assert f'[SHOULD] {heading}' in ending
    assert f'[MUST] {heading}' not in ending


@pytest.mark.parametrize('language,name,vision,story', [
    ('zh', '林岚', '开一间社区书店', '清晨的门扉轻响，来客把租约放在桌上。\n\n林岚抬起头，指尖停在签名栏前。'),
    ('zh', '林岚', '开一间社区书店', '林岚望着租约，手中的笔悬在纸上。'),
    ('zh', '林岚', '开一间社区书店', '命运的齿轮开始转动，林岚推开门。\n\n这笔押金足以耗尽积蓄。'),
    ('en', 'Mira', 'open a bookshop', 'The visitor laid a lease on the desk.\n\nMira held her pen above the page.'),
    ('en', 'Mira', 'open a bookshop', 'Mira held her pen above the unsigned lease.'),
    ('en', 'Mira', 'open a bookshop', 'A new journey awaited Mira.\n\nThe deposit would consume her savings.'),
    ('zh', '林岚', '开一间社区书店', ''),
    ('zh', '林岚', '开一间社区书店', '# 第一章\n\n林岚推开门。'),
])
def test_first_and_later_days_have_identical_hard_opening_checks(language, name, vision, story):
    hard_by_day = []
    for day in (0, 1, 30):
        state = {'player_name': name, 'life_vision': vision, 'timeline': {'version': 2, 'day_index': day}}
        hard, _ = split_daily_opening_issues(validate_daily_first_opening(story, state, {'name': name}, language))
        hard_by_day.append(hard)
    assert hard_by_day[0] == hard_by_day[1] == hard_by_day[2]
    if story and not story.startswith('#'):
        assert hard_by_day[0] == []
    else:
        assert hard_by_day[0]


@pytest.mark.parametrize('code', [
    'daily_opening_missing_protagonist', 'daily_opening_not_single_sentence',
    'daily_opening_cliche', 'daily_opening_missing_vision_anchor',
    'daily_opening_missing_core_conflict', 'daily_opening_missing_second_paragraph',
    'daily_opening_second_paragraph_not_scene',
])
def test_first_day_advisories_keep_specific_diagnostic_codes(code):
    from src.ai.story_validation import findings_from_legacy, FindingSeverity
    hard, warnings = split_daily_opening_issues([code])
    findings = findings_from_legacy(issues=hard, warnings=warnings, source='quick')
    assert [(f.code, f.severity) for f in findings] == [(code, FindingSeverity.WARNING)]
