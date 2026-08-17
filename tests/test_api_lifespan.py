import pytest

pytestmark = [pytest.mark.api]



@pytest.mark.asyncio
async def test_lifespan_does_not_start_projection_service_when_flag_is_off(
    monkeypatch,
) -> None:
    import src.api.main as main

    calls: list[str] = []
    monkeypatch.setattr(main, "init_db", lambda: calls.append("init"))
    monkeypatch.setattr(main, "get_feature", lambda _name: False, raising=False)

    async with main.lifespan(main.app):
        assert calls == ["init"]


@pytest.mark.asyncio
async def test_lifespan_starts_after_database_and_stops_before_shared_pools(
    monkeypatch,
) -> None:
    import src.api.main as main
    import src.api.routers.gameplay.sse_helpers as sse_helpers
    import src.api.routers.images as images
    import src.services.daily_world_projection as projection
    import src.services.image_service as image_service
    import src.services.portrait_image_jobs as portrait_jobs

    calls: list[str] = []

    class Service:
        def start(self) -> None:
            calls.append("start")

        def stop(self, *, wait: bool) -> None:
            assert wait is False
            calls.append("stop")

    monkeypatch.setattr(main, "init_db", lambda: calls.append("init"))
    monkeypatch.setattr(main, "get_feature", lambda _name: True)
    monkeypatch.setattr(
        projection, "get_daily_world_projection_service", lambda: Service()
    )
    monkeypatch.setattr(
        portrait_jobs, "recover_pending_portrait_image_jobs", lambda: []
    )

    async def drain() -> None:
        return None

    monkeypatch.setattr(images, "_drain_pending_events", drain)
    monkeypatch.setattr(
        sse_helpers,
        "shutdown_sse_thread_pool",
        lambda **_kwargs: calls.append("sse"),
    )
    monkeypatch.setattr(
        image_service,
        "shutdown_image_thread_pool",
        lambda **_kwargs: calls.append("image"),
    )

    async with main.lifespan(main.app):
        assert calls == ["init", "start"]

    assert calls == ["init", "start", "stop", "sse", "image"]


@pytest.mark.asyncio
async def test_lifespan_stops_projection_when_later_startup_raises(monkeypatch) -> None:
    import src.api.main as main
    import src.api.routers.gameplay.sse_helpers as sse_helpers
    import src.services.daily_world_projection as projection
    import src.services.image_service as image_service
    import src.services.portrait_image_jobs as portrait_jobs

    calls: list[str] = []

    class Service:
        def start(self) -> None:
            calls.append("start")

        def stop(self, *, wait: bool) -> None:
            calls.append("stop")

    monkeypatch.setattr(main, "init_db", lambda: calls.append("init"))
    monkeypatch.setattr(main, "get_feature", lambda _name: True)
    monkeypatch.setattr(
        projection, "get_daily_world_projection_service", lambda: Service()
    )
    monkeypatch.setattr(
        portrait_jobs,
        "recover_pending_portrait_image_jobs",
        lambda: (_ for _ in ()).throw(RuntimeError("startup broke")),
    )
    monkeypatch.setattr(
        sse_helpers,
        "shutdown_sse_thread_pool",
        lambda **_kwargs: calls.append("sse"),
    )
    monkeypatch.setattr(
        image_service,
        "shutdown_image_thread_pool",
        lambda **_kwargs: calls.append("image"),
    )

    with pytest.raises(RuntimeError, match="startup broke"):
        async with main.lifespan(main.app):
            pass

    assert calls == ["init", "start", "stop", "sse", "image"]
