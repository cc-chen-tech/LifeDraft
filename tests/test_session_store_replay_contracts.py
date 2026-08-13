"""Deterministic contracts for reconnectable gameplay session state."""

import time

from src.api.session_store import SESSION_TIMEOUT, GameLoopSession, SessionStore


def test_sse_replay_keeps_tail_event_ids_after_cache_trimming() -> None:
    session = GameLoopSession(object(), game_id=7, user_id=3)

    for index in range(session.MAX_SSE_CACHE_SIZE + 2):
        assert session.cache_sse_chunk("chunk-{}".format(index)) == index

    assert session.get_cached_chunks_after(498) == [
        (499, "chunk-499"),
        (500, "chunk-500"),
        (501, "chunk-501"),
    ]
    assert session.get_cached_chunks_after(-1)[0] == (2, "chunk-2")

    session.clear_sse_cache()

    assert session.get_cached_chunks_after(-1) == []


def test_options_cache_requires_matching_story_and_resets_prefetch_lifecycle() -> None:
    session = GameLoopSession(object(), game_id=8)
    options = [{"id": "investigate", "text": "Inspect the letter"}]

    session.set_cached_options(
        week=4,
        round_num=2,
        options=options,
        story_content="first story",
    )

    assert session.get_cached_options(4, 2, "first story") == options
    assert session.get_cached_options(4, 2, "rewritten story") is None
    assert session.is_prefetching_options() is False

    session.start_prefetching_options()
    assert session.is_prefetching_options() is True

    session.finish_prefetching_options()
    session.clear_options_cache()

    assert session.is_prefetching_options() is False
    assert session.get_cached_options(4, 2, "first story") is None


def test_store_isolates_owner_keys_preserves_cache_and_cleans_expired_sessions() -> None:
    store = SessionStore()
    first = store.put(15, object(), user_id=1)
    first.set_cached_options(week=1, round_num=1, options=[{"id": "a"}])

    second_owner = store.put(15, object(), user_id=2)
    updated = store.put(15, object(), user_id=1)

    assert SessionStore.make_key(15, 1) != SessionStore.make_key(15, 2)
    assert store.get(15, user_id=2) is second_owner
    assert updated is first
    assert updated.get_cached_options(1, 1) == [{"id": "a"}]
    assert store.get_user_sessions(1) == [first]

    updated.last_access = time.time() - SESSION_TIMEOUT - 1
    store._cleanup_interval = 0

    assert store.get(15, user_id=1) is None
    assert store.active_count == 1
