"""Durability and fail-closed regressions at production story boundaries."""
from types import SimpleNamespace

import pytest

from src.ai.harness.constraint_registry import ConstraintDefinition, ConstraintRegistry, ConstraintType, Priority
from src.ai.harness.validation_pipeline import ValidationPipeline
from src.ai.story_exceptions import StoryGenerationFailure
from src.api.routers.gameplay import sse_helpers
from src.api.services.event_generation_operation import EventGenerationKey, EventGenerationOperation
from src.game.state import PlayerState


@pytest.mark.parametrize('priority', list(Priority))
def test_validator_implementation_error_never_passes(priority):
    registry = ConstraintRegistry()
    def broken(_story, _context):
        raise RuntimeError('private draft and credential must never be emitted')
    registry.register(ConstraintDefinition(ConstraintType.ERA_CONSISTENCY, priority, 'era', broken))
    with pytest.raises(StoryGenerationFailure) as caught:
        ValidationPipeline(registry).validate('private story', {})
    assert caught.value.failure_code.value == 'VALIDATION_SERVICE_ERROR'
    assert 'private' not in str(caught.value)


@pytest.mark.parametrize('save_outcome', [False, OSError('private database details')])
def test_event_save_failure_never_completes_or_retains_uncommitted_event(monkeypatch, save_outcome):
    state = PlayerState(player_name='林岚')
    state.current_event_data = None
    old = state.model_dump()
    event = SimpleNamespace(event_description='candidate', options=[])
    def generate(**_kwargs):
        state.current_event_data = {'event_description': 'candidate'}
        return event
    loop = SimpleNamespace(player_state=state, current_event=None, quality_level='expert',
                           generate_round_event=generate, get_state=lambda: loop.player_state)
    def save(*args):
        if isinstance(save_outcome, Exception):
            raise save_outcome
        return save_outcome
    monkeypatch.setattr(sse_helpers, 'get_db', lambda: SimpleNamespace(save_game_progress=save))
    operation = EventGenerationOperation(EventGenerationKey(game_id=761, week=0, round_number=0))
    sse_helpers._run_event_generation_operation(operation, loop, 761, SimpleNamespace(user_id=12))
    snapshot = operation.snapshot_after(-1)
    assert snapshot.status == 'failed'
    assert snapshot.failure['code'] == 'PERSISTENCE_FAILED'
    assert loop.player_state.current_event_data == old['current_event_data']


def test_failure_resume_save_exception_still_terminates_and_is_logged(monkeypatch, caplog):
    loop = SimpleNamespace(player_state=PlayerState(player_name='林岚'), current_event=None,
                           quality_level='expert', generate_round_event=lambda **kwargs: None)
    def broken(*args, **kwargs):
        raise OSError('private failing database')
    monkeypatch.setattr(sse_helpers, '_set_generation_resume_view', broken)
    operation = EventGenerationOperation(EventGenerationKey(game_id=762, week=0, round_number=0))
    with caplog.at_level('INFO', logger='diagnostic'):
        sse_helpers._run_event_generation_operation(operation, loop, 762, SimpleNamespace(user_id=13))
    assert operation.status == 'failed'
    records = [r.event_data for r in caplog.records if hasattr(r, 'event_data')]
    assert any(r['event'] == 'story_failure_persistence' and r['game_id'] == 762 and r['user_id'] == 13 for r in records)
    assert 'private failing database' not in str(records)


@pytest.fixture
def file_story_database(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.database import models, state_repository, game_repository, session_repository
    from src.database.db import GameDatabase
    from src.api.session_store import session_store
    from src.ai.client import AIClient
    # Restored API loops create their own clients for optional enrichment.
    # Keep those workers offline as well as the explicit per-test generator.
    monkeypatch.setattr(AIClient, 'call', lambda self, **kwargs: '{}')
    # Temporary databases reuse small integer IDs. Keep their restored API
    # sessions isolated from the process-wide cache for the normal test DB.
    monkeypatch.setattr(session_store, '_sessions', {})
    engine = create_engine(f"sqlite:///{tmp_path / 'story-durability.sqlite'}")
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(models, 'SessionLocal', factory)
    monkeypatch.setattr(state_repository, 'SessionLocal', factory)
    monkeypatch.setattr(game_repository, 'SessionLocal', factory)
    monkeypatch.setattr(session_repository, 'SessionLocal', factory)
    monkeypatch.setenv('ENABLE_SOFT_NARRATIVE_LENGTHS', 'true')
    monkeypatch.setenv('ENABLE_CONSTRAINT_HARNESS', 'true')
    monkeypatch.setenv('ENABLE_UNIFIED_NARRATIVE_BUDGETS', 'false')
    database = GameDatabase()
    try:
        yield database
    finally:
        for session in list(session_store._sessions.values()):
            session.game_loop.shutdown()
            # Production shutdown is deliberately non-blocking. Tests must
            # drain writes before the next fixture rebinds SessionLocal and
            # reuses game_id=1 in a different temporary database.
            session.game_loop._daily_postprocessor.shutdown(wait=True, cancel_futures=True)
        session_store._sessions.clear()
        engine.dispose()


def test_safe_first_day_reloads_from_file_database_and_owned_api(file_story_database, monkeypatch):
    from fastapi.testclient import TestClient
    from src.ai.generator import EventGenerator
    from src.api.main import app
    from src.api.deps import create_token
    from src.database.models import User, SessionLocal
    from src.game.game_loop import GameLoop
    from src.game.daily_timeline import build_daily_timeline
    from src.api import deps
    from src.api.routers import games
    from src.services import daily_recommended_prefetch
    from src.ai.harness.quality_level import QualityLevel
    with SessionLocal() as db:
        user = User(private_id='durability-private', public_id='durable1', display_name='Tester')
        db.add(user); db.commit(); user_id = int(user.user_id)
    state = PlayerState(player_name='于谦', life_vision='占领蒙古',
                        character_settings={'name': '于谦', 'era': {'era_description': '明永乐十九年'}, 'relationships': {'key_people': []}},
                        timeline=build_daily_timeline(start_date='1421-04-15', day_index=0), timeline_version=2)
    game_id = file_story_database.create_game(language='zh', initial_state=state.to_dict(), user_id=user_id)
    ai = EventGenerator(api_key='test-key', use_cache=False, quality_level=QualityLevel.EXPERT)
    monkeypatch.setattr(ai.ai_client, 'call', lambda **kwargs: '于谦端起一杯拿铁，却未考虑远方。\n\n他打算先休息。')
    loop = GameLoop(language='zh', ai_generator=ai, quality_level='expert')
    loop.load_game(state.to_dict())
    loop.game_id = game_id
    monkeypatch.setattr(sse_helpers, 'get_db', lambda: file_story_database)
    monkeypatch.setattr(games, 'get_db', lambda: file_story_database)
    monkeypatch.setattr(deps, 'get_db', lambda: file_story_database)
    monkeypatch.setattr(sse_helpers, '_enqueue_accepted_daily_projection', lambda *args: None)
    monkeypatch.setattr(sse_helpers, '_trigger_round_illustration_generation', lambda *args, **kwargs: None)
    monkeypatch.setattr(daily_recommended_prefetch, 'ensure_daily_recommended_prefetch', lambda **kwargs: None)
    operation = EventGenerationOperation(EventGenerationKey(game_id=game_id, week=0, round_number=0, resolved_mode='generate_missing'))
    try:
        sse_helpers._run_event_generation_operation(operation, loop, game_id, SimpleNamespace(user_id=user_id))
        assert operation.status == 'completed'
        persisted = file_story_database.load_saved_game(game_id, user_id)
        assert persisted['current_event_data']['delivery_notice']['code'] == 'SAFE_FIRST_DAY_FALLBACK'
        assert len(persisted['current_event_data']['options']) == 3
        assert persisted['current_event_data']['story_date'] == '1421-04-15'
        with TestClient(app) as client:
            response = client.get(f'/api/games/{game_id}', headers={'Authorization': f'Bearer {create_token(user_id)}'})
            assert response.status_code == 200
            assert response.json()['current_event'] == persisted['current_event_data']
    finally:
        loop.shutdown()


@pytest.mark.parametrize('rejection', ['none', 'judge', 'ledger'])
def test_model_smoke_daily_opening_uses_production_generation_and_file_readback(file_story_database, monkeypatch, tmp_path, rejection, caplog):
    caplog.set_level('INFO', logger='diagnostic')
    from scripts import model_smoke
    from src.ai.generator import EventGenerator
    from src.ai.harness.quality_level import QualityLevel
    from src.ai.system_prompts import STORY_NOVELIST_ZH, get_system_prompt
    import json
    ai = EventGenerator(api_key='test-key', use_cache=False, quality_level=QualityLevel.EXPERT)
    calls = []
    prose = ('于谦想要占领蒙古，却还没有可行的筹划，眼下只能先核对边地记载。\n\n'
             '清晨于谦走进书房，把卷册摊在木桌上，窗外传来车轮碾过石板的声音。他发现关隘之间的路程记载相互矛盾，先把存疑之处逐条圈出。\n\n'
             '于谦重新理清案头文书，记下仍待查证的粮道与行程。他必须决定先核对旧图，还是走访熟悉边地的人。')
    def provider(**kwargs):
        calls.append(kwargs)
        if kwargs['system_prompt'].startswith(STORY_NOVELIST_ZH):
            return prose.replace('于谦想要', '四十岁的于谦想要') if rejection == 'ledger' else prose
        if kwargs['system_prompt'] == get_system_prompt('consistency_validator', 'zh') and rejection == 'judge':
            return json.dumps({'should_retry': True, 'issues': [{'dimension': 'identity', 'severity': 'CRITICAL',
                'description': 'private fixture conflict', 'fix_suggestion': 'remove conflicting identity'}]})
        if kwargs['system_prompt'] != get_system_prompt('option_generator', 'zh'):
            return '{"issues":[],"should_retry":false}'
        return json.dumps({'event_description': prose, 'options': [
            {'text': '核对旧图关隘记载，标出疑点', 'effects': {}, 'is_recommended': True},
            {'text': '整理粮道文书，列出待查问题', 'effects': {}},
            {'text': '走访熟悉边地的人，询问行程', 'effects': {}}]}, ensure_ascii=False)
    monkeypatch.setattr(ai.ai_client, 'call', provider)
    result = model_smoke._run_daily_opening_check(ai, tmp_path, None)
    assert result['delivery_mode'] == ('model' if rejection == 'none' else 'safe_first_day')
    if rejection != 'none':
        checks = [r.event_data for r in caplog.records if hasattr(r, 'event_data')
                  and r.event_data.get('event') == 'story_consistency_check']
        expected = 'age_mismatch' if rejection == 'ledger' else 'consistency_identity'
        assert [r['phase'] for r in checks] == ['initial', 'repair']
        assert all(expected in r['finding_codes'] for r in checks)
    assert result['quality_level'] == 'master'
    assert result['story_date'] == '1421-04-15'
    assert result['persisted'] is True
    assert result['options'] == 3
    assert result['paragraphs'] >= 2
    assert result['provider_calls'] >= 2
    assert result['provider_calls'] <= 8
    assert len(calls) >= 2
    assert 'auth_token' not in json.dumps(result)
    session_file = tmp_path / 'smoke-browser-session.json'
    assert session_file.stat().st_mode & 0o077 == 0
    # Resume the saved opener through the owned API, settle a choice, then read
    # durable day 2. This uses the production choice route and database writes.
    from fastapi.testclient import TestClient
    from src.api.main import app
    from src.api import deps
    from src.api.routers import games
    from src.api.routers.gameplay import choices
    from src.services import daily_recommended_prefetch
    session = json.loads(session_file.read_text())
    for module in (deps, games, choices, sse_helpers):
        monkeypatch.setattr(module, 'get_db', lambda: file_story_database)
    monkeypatch.setattr(daily_recommended_prefetch, 'ensure_daily_recommended_prefetch', lambda **kwargs: None)
    monkeypatch.setattr(daily_recommended_prefetch, 'resolve_choice_prefetch_for_game', lambda **kwargs: None)
    headers = {'Authorization': f"Bearer {session['auth_token']}"}
    with TestClient(app) as client:
        before = client.get(f"/api/games/{result['game_id']}", headers=headers)
        assert before.status_code == 200
        event = before.json()['current_event']
        chosen = client.post(f"/api/games/{result['game_id']}/choice-sync", headers=headers, json={
            'option_index': 0, 'event_id': event['event_id'], 'revision': event['revision'],
        })
        assert chosen.status_code == 200, chosen.text
        assert chosen.json()['next_timeline']['day_index'] == 1
        after = client.get(f"/api/games/{result['game_id']}", headers=headers)
        assert after.status_code == 200
        assert after.json()['player_state']['timeline']['day_index'] == 1
        assert after.json()['player_state']['day_history'][-1]['event_id'] == event['event_id']



def test_prefetch_double_database_failure_still_logs_terminal_identity(monkeypatch, caplog):
    from src.services import daily_recommended_prefetch as prefetch
    from src.database import models
    from src.ai.models import GameEvent, EventOption
    class ClaimSession:
        def commit(self): pass
        def close(self): pass
        def rollback(self): pass
    attempts = []
    def sessions():
        attempts.append(1)
        if len(attempts) > 1:
            raise OSError('private persistence detail')
        return ClaimSession()
    monkeypatch.setattr(models, 'SessionLocal', sessions)
    monkeypatch.setattr(prefetch.DailyRecommendedPrefetchRepository, 'claim', lambda self, task_id: 'claim-token')
    def fail(*args, **kwargs):
        raise ValueError('private rejected story')
    monkeypatch.setattr(prefetch, 'project_daily_choice', fail)
    with caplog.at_level('INFO', logger='diagnostic'):
        prefetch._run_prefetch_worker(task_id=871, game_id=81, user_id=19, source_loop=object(),
            snapshot_state=object(), snapshot_event=GameEvent(event_description='private', options=[EventOption(text='go', effects={}), EventOption(text='stay', effects={})]), option_index=0, language='zh')
    records = [r.event_data for r in caplog.records if hasattr(r, 'event_data')]
    assert any(r['event'] == 'prefetch_operation' and r['outcome'] == 'failed' and r['job_id'] == 871 and r['user_id'] == 19 for r in records)
    assert any(r['phase'] == 'save_failure' and r['outcome'] == 'failed' for r in records)
    assert 'private' not in str(records)


@pytest.mark.parametrize('stage', ['quick', 'harness', 'consistency'])
def test_validator_crash_cannot_become_a_retry_or_safe_fallback(monkeypatch, caplog, stage):
    caplog.set_level("INFO", logger="diagnostic")
    from unittest.mock import MagicMock
    from src.ai.story_generator import StoryGenerator
    from src.ai.harness.quality_level import QualityLevel
    from src.ai import quick_validator
    monkeypatch.setenv('ENABLE_SOFT_NARRATIVE_LENGTHS', 'true')
    monkeypatch.setenv('ENABLE_CONSTRAINT_HARNESS', 'true')
    client = MagicMock()
    client.call.return_value = ('林岚想开一间社区书店，却还凑不齐租金。她决定先把账目理清。\n\n'
                               '清晨林岚走进旧街店面，翻开租约。房东催她答复，她必须决定是争取宽限，还是先放弃店面。')
    generator = StoryGenerator(client, quality_level=QualityLevel.EXPERT)
    def broken(*args, **kwargs):
        raise RuntimeError('private validator context')
    if stage == 'quick':
        monkeypatch.setattr(quick_validator, 'quick_validate_story', broken)
    elif stage == 'consistency':
        monkeypatch.setattr('src.ai.consistency_validator.ConsistencyValidator.validate_story', broken)
    else:
        generator._validation_pipeline = SimpleNamespace(validate=broken)
    with pytest.raises(StoryGenerationFailure) as caught:
        generator.generate_round_event(player_state={'game_id': 99, 'player_name': '林岚', 'life_vision': '开一间社区书店',
            'week': 0, 'current_round': 0, 'timeline': {'version': 2, 'day_index': 0, 'day_number': 1}},
            character_settings={'name': '林岚'}, language='zh', round_number=0, round_context='', option_generator=MagicMock(),
            world_model=MagicMock(continuity_ledger=None) if stage == 'consistency' else None)
    assert caught.value.failure_code.value == 'VALIDATION_SERVICE_ERROR'
    assert client.call.call_count == 1
    failures = [record.event_data for record in caplog.records if hasattr(record, 'event_data')
                and record.event_data.get('error_code') == 'VALIDATION_SERVICE_ERROR']
    assert failures
    assert all(record['attempt'] == 1 and record['attempt_id'].endswith(':1') for record in failures)


def test_generation_facade_preserves_durable_identity(monkeypatch):
    from src.ai.generator import EventGenerator
    from src.observability.request_context import RequestContext, request_context, current_request_context
    ai = EventGenerator(api_key='test-key', use_cache=False)
    observed = []
    def delegated(**kwargs):
        observed.append(current_request_context())
        return SimpleNamespace()
    monkeypatch.setattr(ai.story_gen, 'generate_round_event', delegated)
    parent = RequestContext(request_id='request-identity', operation_id='daily-prefetch:32',
        user_id=13, game_id=42, job_id=32, job_type='daily_recommended_prefetch', attempt_id='attempt-2')
    with request_context(parent):
        ai.generate_round_event(player_state={}, language='zh', round_number=0, round_context='')
        assert current_request_context() is parent
    actual = observed[0]
    assert (actual.user_id, actual.game_id, actual.job_id, actual.job_type, actual.attempt_id) == (13, 42, 32, 'daily_recommended_prefetch', 'attempt-2')
    assert actual.operation_id == parent.operation_id


def test_committed_daily_replacement_survives_optional_prefetch_failure(monkeypatch):
    from src.game import daily_event_revision
    from src.services import daily_recommended_prefetch as prefetch
    from src.ai.models import GameEvent, EventOption
    event = GameEvent(event_description='committed story', options=[EventOption(text='go', effects={}), EventOption(text='stay', effects={})])
    loop = SimpleNamespace(player_state=PlayerState(player_name='林岚'), quality_level='expert')
    monkeypatch.setattr(daily_event_revision, 'regenerate_daily_event_atomically', lambda *args, **kwargs: event)
    monkeypatch.setattr(prefetch, 'invalidate_daily_recommended_prefetch_for_current_event', lambda **kwargs: None)
    monkeypatch.setattr(sse_helpers, 'invalidate_daily_media_after_event_replacement', lambda *args: None)
    monkeypatch.setattr(sse_helpers, '_enqueue_accepted_daily_projection', lambda *args, **kwargs: None)
    monkeypatch.setattr(sse_helpers, 'get_db', lambda: object())
    def broken(**kwargs):
        raise RuntimeError('optional queue unavailable')
    monkeypatch.setattr(prefetch, 'ensure_daily_recommended_prefetch', broken)
    monkeypatch.setattr(sse_helpers, '_set_generation_resume_view', lambda *args, **kwargs: True)
    operation = EventGenerationOperation(EventGenerationKey(game_id=769, week=0, round_number=0))
    sse_helpers._run_daily_regeneration_operation(operation, loop, 769, SimpleNamespace(user_id=16))
    assert operation.status == 'completed'
    assert operation.snapshot_after(-1).result is event


def test_real_sqlite_save_failure_retains_original_and_safe_root_cause(file_story_database, caplog):
    from sqlalchemy import event
    from src.database import state_repository
    state = PlayerState(player_name='林岚')
    game_id = file_story_database.create_game(language='zh', initial_state=state.to_dict())
    engine = state_repository.SessionLocal.kw['bind']
    def fail_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith('INSERT INTO game_states'):
            raise OSError('private story in database parameters')
    event.listen(engine, 'before_cursor_execute', fail_insert)
    state.current_event_data = {'event_description': 'uncommitted story'}
    try:
        with caplog.at_level('INFO', logger='diagnostic'):
            assert file_story_database.save_game_progress(game_id, state) is False
        restored = file_story_database.load_game_state(game_id)
        assert restored['current_event_data'] is None
        records = [r.event_data for r in caplog.records if hasattr(r, 'event_data')]
        failure = next(r for r in records if r['event'] == 'game_state_persistence')
        assert failure['game_id'] == game_id
        assert failure['root_exception_type'] == 'OSError'
        assert failure['exception_frames']
        assert 'private story' not in str(records)
    finally:
        event.remove(engine, 'before_cursor_execute', fail_insert)


@pytest.mark.asyncio
async def test_legacy_regeneration_save_failure_never_emits_complete_and_restores_event(monkeypatch):
    from src.ai.models import GameEvent, EventOption
    old = GameEvent(event_description='old accepted story', options=[EventOption(text='go', effects={}), EventOption(text='stay', effects={})])
    new = old.model_copy(update={'event_description': 'uncommitted candidate'})
    state = PlayerState(player_name='林岚', current_event_data=old.model_dump())
    loop = SimpleNamespace(player_state=state, current_event=old, get_state=lambda: state)
    def generate(**kwargs):
        kwargs['stream_callback'](new.event_description)
        state.current_event_data = new.model_dump()
        loop.current_event = new
        return new
    loop.generate_round_event = generate
    monkeypatch.setattr(sse_helpers, 'get_db', lambda: SimpleNamespace(save_game_progress=lambda *args: False))
    frames = [frame async for frame in sse_helpers.stream_regenerate(loop, 772)]
    assert all('event: complete' not in frame and 'uncommitted candidate' not in frame for frame in frames)
    assert any('PERSISTENCE_FAILED' in frame for frame in frames)
    assert loop.current_event == old
    assert state.current_event_data == old.model_dump()
