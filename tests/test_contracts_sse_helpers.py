from types import SimpleNamespace
from unittest.mock import MagicMock

from src.api.routers.gameplay.sse_helpers import _prefetch_options


class _SyncThreadPool:
    def __init__(self):
        self.submitted = []

    def submit(self, fn, *args, **kwargs):
        self.submitted.append((fn, args, kwargs))
        fn(*args, **kwargs)


class TestPrefetchOptionsContracts:
    """Contract tests for SSE prefetch edge behavior."""

    def test_prefetch_skips_when_cached_options_exist(self, monkeypatch):
        pool = _SyncThreadPool()
        monkeypatch.setattr(
            "src.api.routers.gameplay.sse_helpers._get_background_thread_pool", lambda: pool
        )

        game_loop = MagicMock()
        game_loop.player_state = SimpleNamespace(week=3, current_round=1, to_dict=lambda: {})
        session = MagicMock()
        session.is_prefetching_options.return_value = False
        session.get_cached_options.return_value = ["cached"]
        event = SimpleNamespace(event_description="这是之前的故事")

        _prefetch_options(game_loop, 99, session, event)

        assert session.get_cached_options.called
        assert not session.start_prefetching_options.called
        assert not session.set_cached_options.called
        assert not game_loop.ai_generator.generate_options_only.called
        assert session.finish_prefetching_options.called

    def test_prefetch_generates_and_caches_options(self, monkeypatch):
        pool = _SyncThreadPool()
        monkeypatch.setattr(
            "src.api.routers.gameplay.sse_helpers._get_background_thread_pool", lambda: pool
        )

        game_loop = MagicMock()
        game_loop.player_state = SimpleNamespace(
            week=5, current_round=2, to_dict=lambda: {"foo": "bar"}, character_settings={}
        )
        game_loop.player_state.character_settings = {}
        options_event = SimpleNamespace(options=[SimpleNamespace(model_dump=lambda: {"text": "选项A"})])
        game_loop.ai_generator = SimpleNamespace(generate_options_only=MagicMock(return_value=options_event))
        game_loop.language = "zh"

        session = MagicMock()
        session.is_prefetching_options.return_value = False
        session.get_cached_options.return_value = None
        session.set_cached_options.return_value = None
        event = SimpleNamespace(event_description="主角发现了一枚旧硬币")

        _prefetch_options(game_loop, 99, session, event)

        game_loop.ai_generator.generate_options_only.assert_called_once_with(
            story_description="主角发现了一枚旧硬币",
            player_state={"foo": "bar"},
            character_settings={},
            language="zh",
        )
        session.set_cached_options.assert_called_once()
        cache_args = session.set_cached_options.call_args
        assert cache_args.args[0] == 5
        assert cache_args.args[1] == 2
        assert cache_args.args[2] == [{"text": "选项A"}]
        assert cache_args.args[3] == "主角发现了一枚旧硬币"
        assert session.finish_prefetching_options.called
        assert pool.submitted

    def test_prefetch_handles_empty_generation_as_warning_path(self, monkeypatch):
        pool = _SyncThreadPool()
        monkeypatch.setattr(
            "src.api.routers.gameplay.sse_helpers._get_background_thread_pool", lambda: pool
        )

        game_loop = MagicMock()
        game_loop.player_state = SimpleNamespace(
            week=5, current_round=2, to_dict=lambda: {"foo": "bar"}, character_settings={}
        )
        game_loop.ai_generator = SimpleNamespace(generate_options_only=MagicMock(return_value=None))
        game_loop.language = "zh"

        session = MagicMock()
        session.is_prefetching_options.return_value = False
        session.get_cached_options.return_value = None
        event = SimpleNamespace(event_description="主角发现了一枚旧硬币")

        _prefetch_options(game_loop, 99, session, event)

        assert session.start_prefetching_options.called
        assert session.set_cached_options.called is False
        assert session.finish_prefetching_options.called

    def test_prefetch_finishes_even_when_player_state_missing(self, monkeypatch):
        pool = _SyncThreadPool()
        monkeypatch.setattr(
            "src.api.routers.gameplay.sse_helpers._get_background_thread_pool", lambda: pool
        )

        game_loop = MagicMock()
        game_loop.player_state = None
        session = MagicMock()
        event = SimpleNamespace(event_description="")

        _prefetch_options(game_loop, 99, session, event)

        assert session.finish_prefetching_options.called

    def test_prefetch_finishes_when_generation_raises(self, monkeypatch):
        pool = _SyncThreadPool()
        monkeypatch.setattr(
            "src.api.routers.gameplay.sse_helpers._get_background_thread_pool", lambda: pool
        )

        game_loop = MagicMock()
        game_loop.player_state = SimpleNamespace(
            week=5, current_round=2, to_dict=lambda: {}, character_settings={}
        )
        game_loop.ai_generator = SimpleNamespace(
            generate_options_only=MagicMock(side_effect=RuntimeError("模型调用失败"))
        )
        game_loop.language = "zh"

        session = MagicMock()
        session.is_prefetching_options.return_value = False
        session.get_cached_options.return_value = None
        event = SimpleNamespace(event_description="测试失败")

        _prefetch_options(game_loop, 99, session, event)

        assert session.finish_prefetching_options.called
        assert session.start_prefetching_options.called
