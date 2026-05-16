"""契约测试：故事风格 API 端点和前端 UI。"""


def test_games_router_has_narrative_style_list_endpoint():
    """games.py 应有 narrative-style-options 端点。"""
    with open("src/api/routers/games.py", "r") as f:
        content = f.read()
    assert (
        "narrative-style-options" in content or "narrative_style_options" in content
    ), "games.py 缺少 narrative-style-options 端点"


def test_games_router_has_narrative_style_get_endpoint():
    """games.py 应有 GET narrative-style 端点。"""
    with open("src/api/routers/games.py", "r") as f:
        content = f.read()
    assert "narrative-style" in content, "games.py 缺少 GET narrative-style 端点"


def test_games_router_has_narrative_style_update_endpoint():
    """games.py 应有 PUT narrative-style 端点。"""
    with open("src/api/routers/games.py", "r") as f:
        content = f.read()
    # 应有 PUT 方法
    assert any(
        kw in content for kw in ['put("', "put('/", "@router.put"]
    ), "games.py 缺少 PUT narrative-style 端点"


def test_frontend_settings_has_story_style_option():
    """前端设置菜单应包含故事风格选项。"""
    with open("frontend/src/app/play/page.tsx", "r") as f:
        content = f.read()
    assert any(
        kw in content for kw in ["故事风格", "storyStyle", "narrativeStyle", "narrative-style"]
    ), "前端设置菜单缺少故事风格选项"


def test_narrative_style_api_importable():
    """games 路由模块可以正常导入。"""
    from src.api.routers import games

    assert games is not None
