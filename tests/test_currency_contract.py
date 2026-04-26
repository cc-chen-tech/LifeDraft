"""契约测试：验证货币单位在生产者(角色创建)和消费者(故事生成prompt/前端显示)之间一致。

生产者：角色创建时 AI 生成 character_settings.wealth.currency_name
消费者：story_prompts.py 中的 prompt 模板 + 前端 StatusBar/ChoiceImpactDisplay
"""


def test_story_prompts_no_hardcoded_carbon_credits():
    """story_prompts.py 中不应有硬编码的'碳信用'。"""
    with open("config/prompts/story_prompts.py", "r") as f:
        content = f.read()
    # 排除注释行
    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if (
            stripped.startswith("#")
            or stripped.startswith('"""')
            or stripped.startswith("'''")
        ):
            continue
        assert (
            "碳信用" not in line
        ), f"story_prompts.py 第{i}行仍包含硬编码的'碳信用': {line.strip()}"


def test_character_wealth_prompt_requires_currency_field():
    """角色创建prompt中必须要求返回currency_name字段。"""
    with open("config/prompts/character_prompts.py", "r") as f:
        content = f.read()
    assert "currency_name" in content, "角色创建prompt必须要求返回currency_name字段"


def test_frontend_statusbar_no_hardcoded_carbon_credits():
    """StatusBar.tsx 中不应有硬编码的'碳信用'。"""
    with open("frontend/src/components/game/StatusBar.tsx", "r") as f:
        content = f.read()
    assert "碳信用" not in content, "StatusBar.tsx 仍包含硬编码的'碳信用'"


def test_frontend_choice_impact_no_hardcoded_carbon_credits():
    """ChoiceImpactDisplay.tsx 中不应有硬编码的'碳信用'。"""
    with open("frontend/src/components/game/ChoiceImpactDisplay.tsx", "r") as f:
        content = f.read()
    assert "碳信用" not in content, "ChoiceImpactDisplay.tsx 仍包含硬编码的'碳信用'"


def test_story_prompts_importable():
    """story_prompts模块可以正常导入。"""
    from config.prompts import story_prompts

    assert hasattr(story_prompts, "get_story_only_prompt")
    assert hasattr(story_prompts, "get_round_event_prompt")


def test_currency_name_used_in_prompt_output():
    """验证 prompt 输出中使用了动态 currency_name 而非硬编码。"""
    from config.prompts.story_prompts import _get_chinese_prompt

    # 模拟北宋角色
    player_state = {
        "age": 25,
        "energy": 70,
        "mood": 60,
        "knowledge": 50,
        "wealth": 10000,
        "week": 0,
        "current_round": 0,
        "rounds_per_week": 3,
        "relationships": {},
    }
    character_settings = {
        "era": {"year": 1066, "era_description": "北宋时期"},
        "wealth": {
            "wealth": 10000,
            "currency": "贯",
            "currency_name": "贯",
            "wealth_description": "中等官宦家庭",
        },
    }

    prompt = _get_chinese_prompt(
        player_state=player_state,
        current_phase="early_career",
        character_settings=character_settings,
    )

    assert "碳信用" not in prompt, "prompt 中不应包含硬编码的'碳信用'"
    assert "10,000贯" in prompt, "prompt 中应包含动态货币单位'贯'，实际输出中未找到"


def test_story_only_prompt_uses_dynamic_currency():
    """验证 get_story_only_prompt 使用动态货币单位。"""
    from config.prompts.story_prompts import get_story_only_prompt

    player_state = {
        "age": 25,
        "energy": 70,
        "mood": 60,
        "knowledge": 50,
        "wealth": 5000,
        "week": 2,
        "current_round": 0,
        "rounds_per_week": 3,
        "relationships": {},
    }
    character_settings = {
        "era": {"year": 1066, "era_description": "北宋时期"},
        "wealth": {
            "wealth": 5000,
            "currency": "两",
            "currency_name": "两",
            "wealth_description": "商贾之家",
        },
    }

    prompt = get_story_only_prompt(
        player_state=player_state,
        language="zh",
        current_phase="early_career",
        character_settings=character_settings,
    )

    assert "碳信用" not in prompt, "story_only prompt 中不应包含硬编码的'碳信用'"
    assert "5,000两" in prompt, "story_only prompt 中应使用动态货币单位'两'"


def test_round_event_prompt_uses_dynamic_currency():
    """验证 get_round_event_prompt 使用动态货币单位。"""
    from config.prompts.story_prompts import get_round_event_prompt

    player_state = {
        "age": 30,
        "energy": 80,
        "mood": 70,
        "knowledge": 60,
        "wealth": 20000,
        "week": 5,
        "current_round": 1,
        "rounds_per_week": 3,
        "relationships": {"张三": 50},
    }
    character_settings = {
        "era": {"year": 1066, "era_description": "北宋时期"},
        "wealth": {
            "wealth": 20000,
            "currency": "贯",
            "currency_name": "贯",
            "wealth_description": "官宦世家",
        },
    }

    prompt = get_round_event_prompt(
        player_state=player_state,
        language="zh",
        round_number=1,
        round_context="",
        character_settings=character_settings,
    )

    assert "碳信用" not in prompt, "round_event prompt 中不应包含硬编码的'碳信用'"
    assert "20,000贯" in prompt, "round_event prompt 中应使用动态货币单位'贯'"


def test_fallback_currency_for_missing_settings():
    """当 character_settings 没有 wealth.currency_name 时，应有合理的 fallback。"""
    from config.prompts.story_prompts import _get_chinese_prompt

    player_state = {
        "age": 25,
        "energy": 70,
        "mood": 60,
        "knowledge": 50,
        "wealth": 10000,
        "week": 0,
        "current_round": 0,
        "rounds_per_week": 3,
        "relationships": {},
    }

    # 无 character_settings
    prompt = _get_chinese_prompt(
        player_state=player_state,
        current_phase="early_career",
        character_settings=None,
    )

    # 应该使用默认货币单位，不崩溃
    assert "10,000" in prompt, "prompt 中应包含格式化的财富数值"
