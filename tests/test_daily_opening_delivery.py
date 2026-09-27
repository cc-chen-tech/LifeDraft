"""First-day formatting must not exhaust the prose budget for a playable story."""

from unittest.mock import MagicMock

import pytest

from src.ai.daily_opening import validate_daily_first_opening
from src.ai.generator import EventGenerator
from src.ai.harness.quality_level import QualityLevel
from src.ai.models import EventOption, GameEvent
from src.ai.system_prompts import STORY_NOVELIST_ZH
from src.ai.story_exceptions import StoryGenerationFailure
from src.ai.story_generator import StoryGenerator
from src.ai.text_quality import normalize_generated_story
from src.game.daily_timeline import build_daily_timeline
from src.game.round.character_introduction import CharacterIntroductionService
from src.game.round.event_generator import RoundEventGenerator
from src.game.state import PlayerState

pytestmark = [pytest.mark.unit]

STYLE_VARIANT_STORY = (
    "林岚想开一间社区书店，却还凑不齐租金。她决定先把账目理清。\n\n"
    "父亲的承诺与积蓄都悬在心头，她反复盘算手中能用的筹码。\n\n"
    "清晨她来到旧街的店面，翻看租约上的期限和押金条款。"
    "房东催她当场答复，她必须决定先争取宽限，还是放弃这间合适的店面。"
)


def _first_day_state() -> dict:
    return {
        "game_id": 1,
        "week": 0,
        "current_round": 0,
        "player_name": "林岚",
        "life_vision": "开一间社区书店",
        "timeline": {"version": 2, "day_index": 0, "day_number": 1},
    }


def _generate_first_day(story: str, quality: QualityLevel = QualityLevel.EXPERT) -> tuple[GameEvent, MagicMock, MagicMock]:
    client = MagicMock()
    client.call.return_value = story
    generator = StoryGenerator(client, quality_level=quality)
    generator._harness_enabled = False
    generator._soft_narrative_lengths = True
    options = MagicMock()
    options.generate_options_only.return_value = GameEvent(
        event_description=story,
        options=[EventOption(text="继续", effects={}) for _ in range(3)],
    )
    options.validate_options_consistency.return_value = []

    event = generator.generate_round_event(
        player_state=_first_day_state(),
        character_settings={"name": "林岚"},
        language="zh",
        round_number=0,
        round_context="",
        option_generator=options,
    )
    return event, client, options


def test_chinese_punctuation_cleanup_preserves_story_paragraphs() -> None:
    story = "林岚还要筹措租金。\n\n清晨，她走进旧街的店面。"

    assert normalize_generated_story(story, language="zh") == story


def test_first_day_style_variance_keeps_playable_story_after_one_prose_call() -> None:
    assert validate_daily_first_opening(
        STYLE_VARIANT_STORY, _first_day_state(), {"name": "林岚"}, "zh"
    ) == [
        "daily_opening_not_single_sentence",
        "daily_opening_second_paragraph_not_scene",
    ]
    event, client, options = _generate_first_day(STYLE_VARIANT_STORY)

    assert event.event_description == STYLE_VARIANT_STORY
    assert client.call.call_count == 1
    options.generate_options_only.assert_called_once()


def test_first_day_style_variance_is_safe_to_resume() -> None:
    generator = RoundEventGenerator(
        lambda: None,
        MagicMock(),
        lambda: "zh",
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    assert generator._existing_story_satisfies_quick_constraints(
        existing_story=STYLE_VARIANT_STORY,
        player_state=_first_day_state(),
        character_settings={"name": "林岚"},
        language="zh",
        resume_source="test",
    )


@pytest.mark.parametrize('story', [
    STYLE_VARIANT_STORY.replace('林岚想开一间社区书店，却还凑不齐租金。她决定先把账目理清。',
                                '清晨的门扉轻响，来客把租约放在桌上。') + '林岚拿起了笔。',
    STYLE_VARIANT_STORY.replace('\n\n', ''),
])
@pytest.mark.parametrize('quality', list(QualityLevel))
def test_first_day_placement_and_paragraph_variants_generate_once_and_resume(story, quality):
    event, client, options = _generate_first_day(story, quality)
    assert event.event_description == story
    assert client.call.call_count == 1
    options.generate_options_only.assert_called_once()
    generator = RoundEventGenerator(lambda: None, MagicMock(), lambda: 'zh', MagicMock(), MagicMock(), MagicMock())
    for day in (0, 1):
        state = _first_day_state()
        state['timeline']['day_index'] = day
        assert generator._existing_story_satisfies_quick_constraints(
            existing_story=story, player_state=state, character_settings={'name': '林岚'},
            language='zh', resume_source='test')


def test_harness_rejection_then_judge_budget_exhaustion_keeps_first_day_playable(monkeypatch):
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "true")
    story = (
        "林岚想开一间社区书店，却还凑不齐租金。\n\n清晨，她坐在书桌前核对租约。\n\n"
        + "".join(f"她把第{i}条租约抄进本子，记下押金金额与交付期限，窗外的脚步声渐渐远去。" for i in range(38))
        + "\n\n林岚合上本子，望着窗外的灯火。"
    )
    client = MagicMock()
    client.call.side_effect = lambda **kwargs: (
        story if kwargs["system_prompt"].startswith(STORY_NOVELIST_ZH)
        else '{"issues": [], "should_retry": false}'
    )
    generator = StoryGenerator(client, quality_level=QualityLevel.MASTER)
    # Decision keyword absence is now advisory. Inject a genuine hard gate
    # here so this independent budget-exhaustion/fallback regression survives.
    from src.ai.harness.constraint_registry import ConstraintDefinition, ConstraintRegistry, ConstraintType, Priority
    from src.ai.harness.validation_pipeline import ValidationPipeline
    registry = ConstraintRegistry()
    registry.register(ConstraintDefinition(
        ConstraintType.ESTABLISHED_FACTS, Priority.CRITICAL, "fixture fact conflict",
        lambda story, context: (False, "fixture fact conflict", {}),
    ))
    generator._validation_pipeline = ValidationPipeline(registry)
    emitted = []
    event = generator.generate_round_event(
        player_state=_first_day_state(), character_settings={"name": "林岚"}, language="zh",
        round_number=0, round_context="", option_generator=MagicMock(),
        world_model=MagicMock(continuity_ledger=None), stream_callback=emitted.append,
    )
    assert event.delivery_notice.code == "SAFE_FIRST_DAY_FALLBACK"
    assert event.event_description != story
    assert len(event.options) == 3
    assert emitted == [event.event_description]
    assert client.call.call_count <= 6


def test_failed_first_day_master_retry_accepts_style_variance_with_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "true")
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "false")
    state = _first_day_state()
    state["resume_view"] = {
        "phase": "failed",
        "failure": {"code": "RETRY_EXHAUSTED", "summary": "故事生成未能完成"},
    }
    client = MagicMock()
    client.call.return_value = STYLE_VARIANT_STORY
    generator = StoryGenerator(client, quality_level=QualityLevel.MASTER)
    assert generator._harness_enabled
    assert generator._soft_narrative_lengths
    options = MagicMock()
    options.generate_options_only.return_value = GameEvent(
        event_description=STYLE_VARIANT_STORY,
        options=[EventOption(text="继续", effects={}) for _ in range(3)],
    )
    options.validate_options_consistency.return_value = []

    event = generator.generate_round_event(
        player_state=state,
        character_settings={"name": "林岚"},
        language="zh",
        round_number=0,
        round_context="",
        option_generator=options,
    )

    assert event.event_description == STYLE_VARIANT_STORY
    assert client.call.call_count == 1
    assert generator._validation_pipeline is not None
    options.generate_options_only.assert_called_once()


def test_failed_first_day_retry_commits_playable_event_with_real_validators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "true")
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "false")
    state = PlayerState(
        player_name="林岚",
        life_vision="开一间社区书店",
        character_settings={
            "name": "林岚",
            "life_vision": "开一间社区书店",
            "relationships": {"key_people": []},
        },
        timeline=build_daily_timeline(start_date="2026-08-13", day_index=0),
        timeline_version=2,
        resume_view={
            "phase": "failed",
            "failure": {"code": "RETRY_EXHAUSTED", "retryable": True},
        },
    )
    ai = EventGenerator(api_key="test-key", use_cache=False, quality_level=QualityLevel.MASTER)
    prose_requests: list[str] = []

    def provider_response(**kwargs: object) -> str:
        system_prompt = str(kwargs["system_prompt"])
        if system_prompt.startswith(STORY_NOVELIST_ZH):
            prose_requests.append(system_prompt)
            return STYLE_VARIANT_STORY
        return '{"issues":[],"should_retry":false}'

    ai.ai_client.call = MagicMock(side_effect=provider_response)
    ai.option_gen.generate_options_only = MagicMock(
        return_value=GameEvent(
            event_description=STYLE_VARIANT_STORY,
            options=[EventOption(text="继续", effects={}) for _ in range(3)],
        )
    )
    ai.option_gen.validate_options_consistency = MagicMock(return_value=[])
    introductions = CharacterIntroductionService(
        player_state_getter=lambda: state, character_creator=MagicMock()
    )
    relationships = MagicMock()
    relationships.get_triggered_events.return_value = []
    committed: list[GameEvent] = []
    generator = RoundEventGenerator(
        player_state_getter=lambda: state,
        ai_generator=ai,
        language_getter=lambda: "zh",
        character_introduction_service=introductions,
        summary_selector=MagicMock(),
        relationship_service=relationships,
        event_callback=lambda event, _state: committed.append(event),
    )
    streamed: list[str] = []

    event = generator.generate_round_event(force_regenerate=True, stream_callback=streamed.append)

    assert event is not None
    assert event.event_description == STYLE_VARIANT_STORY
    assert len(event.options) == 3
    assert event.story_date == "2026-08-13"
    assert event.event_id.startswith("day-0-")
    assert state.current_event_data == event.model_dump()
    assert committed == [event]
    assert streamed == [STYLE_VARIANT_STORY]
    assert len(prose_requests) == 1
    assert ai.ai_client.call.call_count == 2  # prose plus the real consistency judge


def test_first_day_pronoun_opening_is_accepted_like_later_days() -> None:
    story = (
        "她想开一间社区书店，却还凑不齐租金。她决定先把账目理清。\n\n"
        "父亲的承诺与积蓄都悬在心头，她反复盘算手中能用的筹码。\n\n"
        "清晨她来到旧街的店面，翻看租约上的期限和押金条款。"
    )

    event, client, _ = _generate_first_day(story)

    assert event.event_description == story
    assert client.call.call_count == 1


def test_first_day_hard_rejections_deliver_only_a_valid_safe_opening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "true")
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "false")
    invalid_draft = "于谦端起一杯拿铁，却未考虑远方。\n\n他打算先休息。"
    state = {
        "game_id": 157,
        "week": 0,
        "current_round": 0,
        "player_name": "于谦",
        "life_vision": "占领蒙古",
        "timeline": {"version": 2, "day_index": 0, "day_number": 1},
    }
    settings = {
        "name": "于谦",
        "era": {"era_description": "明永乐十九年"},
    }
    client = MagicMock()
    client.call.return_value = invalid_draft
    generator = StoryGenerator(client, quality_level=QualityLevel.MASTER)
    options = MagicMock()

    event = generator.generate_round_event(
        player_state=state,
        character_settings=settings,
        language="zh",
        round_number=0,
        round_context="",
        option_generator=options,
    )

    assert "拿铁" not in event.event_description
    assert "于谦" in event.event_description
    assert "占领蒙古" in event.event_description
    assert len(event.options) == 3
    assert event.delivery_notice is not None
    assert event.delivery_notice.code == "SAFE_FIRST_DAY_FALLBACK"
    assert client.call.call_count <= 3
    options.generate_options_only.assert_not_called()


def test_unsafe_first_day_fallback_does_not_bypass_era_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "true")
    state = {
        "game_id": 158,
        "week": 0,
        "current_round": 0,
        "player_name": "于谦",
        "life_vision": "喝一杯拿铁",
        "timeline": {"version": 2, "day_index": 0, "day_number": 1},
    }
    settings = {"name": "于谦", "era": {"era_description": "明永乐十九年"}}
    client = MagicMock()
    client.call.return_value = "于谦点了一杯拿铁。\n\n他走进星巴克。"

    with pytest.raises(StoryGenerationFailure):
        StoryGenerator(client, quality_level=QualityLevel.EXPERT).generate_round_event(
            player_state=state,
            character_settings=settings,
            language="zh",
            round_number=0,
            round_context="",
            option_generator=MagicMock(),
        )


def test_safe_first_day_fallback_is_saved_with_three_playable_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_CONSTRAINT_HARNESS", "true")
    monkeypatch.setenv("ENABLE_SOFT_NARRATIVE_LENGTHS", "true")
    monkeypatch.setenv("ENABLE_UNIFIED_NARRATIVE_BUDGETS", "false")
    state = PlayerState(
        player_name="于谦",
        life_vision="占领蒙古",
        character_settings={
            "name": "于谦",
            "era": {"era_description": "明永乐十九年"},
            "relationships": {"key_people": []},
        },
        timeline=build_daily_timeline(start_date="1421-04-15", day_index=0),
        timeline_version=2,
    )
    ai = EventGenerator(api_key="test-key", use_cache=False, quality_level=QualityLevel.EXPERT)
    rejected_draft = "于谦端起一杯拿铁，却未考虑远方。\n\n他打算先休息。"
    ai.ai_client.call = MagicMock(return_value=rejected_draft)
    introductions = CharacterIntroductionService(
        player_state_getter=lambda: state, character_creator=MagicMock()
    )
    relationships = MagicMock()
    relationships.get_triggered_events.return_value = []
    committed: list[GameEvent] = []
    generator = RoundEventGenerator(
        player_state_getter=lambda: state,
        ai_generator=ai,
        language_getter=lambda: "zh",
        character_introduction_service=introductions,
        summary_selector=MagicMock(),
        relationship_service=relationships,
        event_callback=lambda event, _state: committed.append(event),
    )
    streamed: list[str] = []

    event = generator.generate_round_event(stream_callback=streamed.append)

    assert event is not None
    assert "拿铁" not in event.event_description
    assert "于谦" in event.event_description
    assert "占领蒙古" in event.event_description
    assert len(event.options) == 3
    assert event.delivery_notice is not None
    assert event.story_date == "1421-04-15"
    assert state.current_event_data == event.model_dump()
    assert committed == [event]
    assert streamed == [event.event_description]


@pytest.mark.parametrize(('language', 'name', 'vision'), [
    ('zh', '林岚', '开一间书店'),
    ('zh', '林岚', '我想开一间书店'),
    ('zh', '林岚', '我想开一间书店。也想让家人安心。'),
    ('zh', '林岚', '我想开一间书店。\n\n也想让家人安心。'),
    ('en', 'Alice', 'open a shop'),
    ('en', 'Alice', 'I want a shop called "Home". I want to help my family.'),
    ('zh', '林岚', '我想开一间叫“归家”的书店。也想让家人安心。'),
    ('en', 'Alice', 'I want to open a shop'),
    ('en', 'Alice', 'I want to open a shop. I also want to support my family.'),
    ('en', 'Alice', 'I want to open a shop.\n\nI also want to support my family.'),
])
def test_fallback_treats_free_form_vision_as_standalone_words(language, name, vision):
    from src.ai.daily_opening import build_first_day_fallback_candidate, split_daily_opening_issues
    state = {**_first_day_state(), 'player_name': name, 'life_vision': vision}
    candidate = build_first_day_fallback_candidate(state, {'name': name}, language)
    paragraphs = candidate.split('\n\n')
    assert len(paragraphs) == 2
    assert '\n' not in paragraphs[0]
    assert '想要我想' not in candidate
    assert 'wants to I want' not in candidate
    # Retain all supplied intent, as a quotation rather than a verb complement.
    normalized = ' '.join(vision.split()).strip('。！？.!? ')
    normalized = normalized.replace('"', "'").replace("“", "‘").replace("”", "’")
    quoted = f'“{normalized}”' if language == 'zh' else f'"{normalized}"'
    assert quoted in paragraphs[0]
    hard, _ = split_daily_opening_issues(validate_daily_first_opening(candidate, state, {'name': name}, language))
    assert hard == []


@pytest.mark.parametrize(('language', 'name', 'vision', 'draft', 'anchors'), [
    ('zh', '林岚', '我想开一间书店。\n\n也想让家人安心。',
     '# 第一章\n\n清晨，他停在门边。', ('我想开一间书店', '也想让家人安心')),
    ('en', 'Alice', 'I want to open a shop.\n\nI also want to support my family.',
     '# Chapter One\n\nIn the morning, he stood by the door.',
     ('I want to open a shop', 'I also want to support my family')),
])
def test_full_sentence_vision_survives_actual_retry_exhaustion(monkeypatch, language, name, vision, draft, anchors):
    monkeypatch.setenv('ENABLE_CONSTRAINT_HARNESS', 'true')
    monkeypatch.setenv('ENABLE_SOFT_NARRATIVE_LENGTHS', 'true')
    monkeypatch.setenv('ENABLE_UNIFIED_NARRATIVE_BUDGETS', 'false')
    state = {**_first_day_state(), 'player_name': name, 'life_vision': vision}
    client = MagicMock()
    client.call.return_value = draft
    generator = StoryGenerator(client, quality_level=QualityLevel.MASTER)
    event = generator.generate_round_event(player_state=state, character_settings={'name': name},
        language=language, round_number=0, round_context='', option_generator=MagicMock())
    assert event.delivery_notice.code == 'SAFE_FIRST_DAY_FALLBACK'
    assert len(event.options) == 3
    assert len(event.event_description.split('\n\n')) == 2
    assert '想要我想' not in event.event_description
    assert 'wants to I want' not in event.event_description
    assert all(anchor in event.event_description for anchor in anchors)


@pytest.mark.parametrize('unified_budget', ['false', 'true'])
def test_first_day_consistency_circuit_reaches_safe_opening(monkeypatch, caplog, unified_budget):
    """Repeated CRITICAL judge findings stop repairs, then deliver a checked opener."""
    import json
    import logging
    from config.logging_config import JsonLogFormatter
    monkeypatch.setenv('ENABLE_CONSTRAINT_HARNESS', 'true')
    monkeypatch.setenv('ENABLE_SOFT_NARRATIVE_LENGTHS', 'true')
    monkeypatch.setenv('ENABLE_UNIFIED_NARRATIVE_BUDGETS', unified_budget)
    caplog.set_level(logging.INFO)
    rejection = json.dumps({'should_retry': True, 'issues': [{
        'dimension': 'identity', 'severity': 'CRITICAL',
        'description': 'private rejected identity conflict',
        'evidence': 'private story excerpt', 'fix_suggestion': 'private fix',
    }]})
    client = MagicMock()
    client.call.side_effect = [STYLE_VARIANT_STORY, rejection, STYLE_VARIANT_STORY, rejection]
    generator = StoryGenerator(client, quality_level=QualityLevel.MASTER)
    emitted = []
    from src.observability.diagnostics import diagnostic_context
    from src.observability.validation_evidence import decrypt_validation_evidence
    with diagnostic_context(user_id=111):
        event = generator.generate_round_event(
            player_state=_first_day_state(), character_settings={'name': '林岚'}, language='zh',
            round_number=0, round_context='', option_generator=MagicMock(),
            world_model=MagicMock(continuity_ledger=None), stream_callback=emitted.append,
        )
    assert event.delivery_notice.code == 'SAFE_FIRST_DAY_FALLBACK'
    assert event.event_description != STYLE_VARIANT_STORY
    assert emitted == [event.event_description]
    assert len(event.options) == 3
    assert event.delivery_notice.attempts_used == 2
    assert client.call.call_count == 4
    records = [json.loads(JsonLogFormatter().format(r)) for r in caplog.records]
    checks = [r for r in records if r.get('event') == 'story_consistency_check']
    assert [r['phase'] for r in checks] == ['initial', 'repair']
    assert all(r['finding_codes'] == ['consistency_identity'] for r in checks)
    assert all(r['outcome'] == 'rejected' for r in checks)
    assert 'private rejected' not in json.dumps(records)
    assert 'private story excerpt' not in json.dumps(records)
    evidence = [r for r in records if r.get('event') == 'story_validation_evidence'
                and r.get('phase') in {'consistency_initial', 'consistency_repair'}]
    assert [r['phase'] for r in evidence] == ['consistency_initial', 'consistency_repair']
    assert all(r.get('encrypted_evidence') for r in evidence)
    decoded = [decrypt_validation_evidence(r, user_id=111, operation_id=r['operation_id']) for r in evidence]
    assert all(r['issues'][0]['description'] == 'private rejected identity conflict' for r in decoded)
    assert decoded[0]['attempt_id'] != decoded[1]['attempt_id']
    assert all(r['game_id'] == 1 for r in decoded)


@pytest.mark.parametrize(('day_index', 'soft_lengths'), [(1, True), (0, False)])
def test_consistency_circuit_cannot_enable_fallback_outside_first_day_policy(monkeypatch, day_index, soft_lengths):
    import json
    monkeypatch.setenv('ENABLE_CONSTRAINT_HARNESS', 'true')
    monkeypatch.setenv('ENABLE_SOFT_NARRATIVE_LENGTHS', str(soft_lengths).lower())
    monkeypatch.setenv('ENABLE_UNIFIED_NARRATIVE_BUDGETS', 'false')
    # Long enough for strict MASTER shape checks to reach consistency validation.
    story = STYLE_VARIANT_STORY + '\n\n' + ''.join(f'林岚仔细核对租约第{i}条，把尚待核实的事项逐一记下。' for i in range(60))
    rejection = json.dumps({'should_retry': True, 'issues': [{
        'dimension': 'identity', 'severity': 'CRITICAL', 'description': 'identity conflict',
        'fix_suggestion': 'repair identity',
    }]})
    client = MagicMock()
    client.call.side_effect = [story, rejection, story, rejection]
    generator = StoryGenerator(client, quality_level=QualityLevel.MASTER)
    state = _first_day_state()
    state['timeline']['day_index'] = day_index
    with pytest.raises(StoryGenerationFailure, match='repeated consistency'):
        generator.generate_round_event(player_state=state, character_settings={'name': '林岚'}, language='zh',
            round_number=0, round_context='', option_generator=MagicMock(), world_model=MagicMock(continuity_ledger=None))


@pytest.mark.parametrize('day', [0, 1])
@pytest.mark.parametrize('story', [
    '清晨的门扉轻响，来客把租约放在桌上。\n\n林岚拿起了笔，决定先核对押金。',
    '林岚拿起了笔，决定先核对租约上的押金条款。',
])
def test_scheduled_story_uses_same_acceptance_on_first_and_later_days(day, story):
    import json
    from types import SimpleNamespace
    state = PlayerState(player_name='林岚', age=28, character_settings={'name': '林岚'},
                        life_vision='开一间社区书店',
                        timeline=build_daily_timeline(start_date='2026-08-13', day_index=day))
    state.timeline['day_index'] = day
    client = MagicMock()
    client.call.return_value = json.dumps({'event_description': story, 'options': [
        {'text': '核对租约条款', 'effects': {}},
        {'text': '整理押金账目', 'effects': {}},
        {'text': '询问交付期限', 'effects': {}},
    ]}, ensure_ascii=False)
    generator = RoundEventGenerator(lambda: state, SimpleNamespace(ai_client=client, quality_level='expert'),
                                    lambda: 'zh', MagicMock(), MagicMock(), MagicMock())
    event = generator._generate_scheduled_event(
        scheduled_events=[{'description': '核对租约', 'parties': ['林岚']}], player_state=state)
    assert event.event_description == story
    assert client.call.call_count == 1
    assert len(event.options) == 3
