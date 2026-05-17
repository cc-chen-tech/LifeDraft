"""Scene analyzer era consistency contract tests."""

from types import SimpleNamespace

import openai

from src.ai.image_prompt_builder import DeepSeekPromptEnhancer


class _FakeChatCompletions:
    def __init__(self, captured, content: str):
        self._captured = captured
        self._content = content

    def create(self, **kwargs):
        self._captured["messages"] = kwargs["messages"]
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=self._content)),
            ]
        )


class _FakeOpenAI:
    def __init__(self, captured, content: str):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(captured, content))


def _patch_scene_analyzer(monkeypatch, content: str):
    captured = {}

    monkeypatch.setattr(
        "src.ai.image_prompt_builder.get_scene_analyzer_config",
        lambda: ("test-key", "https://example.invalid", "test-model"),
    )
    monkeypatch.setattr(
        openai,
        "OpenAI",
        lambda **_: _FakeOpenAI(captured, content),
    )
    return captured


def test_ancient_scene_analyzer_prompt_contains_visual_era_red_line(monkeypatch) -> None:
    captured = _patch_scene_analyzer(
        monkeypatch,
        "【场景描述】林见微在汴京茶楼听闻旧案\n"
        "【画面构图】木桌、油灯、茶盏，窗外是汴京街巷\n"
        "【氛围】悬疑",
    )

    DeepSeekPromptEnhancer().analyze_story_for_illustration(
        story_text="林见微在北宋汴京的思源茶楼听闻旧案。",
        character_info={"name": "林见微", "gender": "女", "age": 25, "era": "北宋汴京，古代中国"},
    )

    prompt_text = "\n".join(message["content"] for message in captured["messages"])
    assert "画面时代红线" in prompt_text
    assert "羽绒服" in prompt_text
    assert "咖啡厅" in prompt_text
    assert "人物服装必须是日常便装（衬衫、T恤、外套、牛仔裤等）" not in prompt_text


def test_ancient_scene_analyzer_rejects_modern_visual_output(monkeypatch) -> None:
    _patch_scene_analyzer(
        monkeypatch,
        "【场景描述】雪夜中，林见微在公路旁的小餐馆歇脚\n"
        "【画面构图】她穿黑色羽绒服，旁边有电暖器和钥匙\n"
        "【氛围】宁静",
    )

    scene_desc, illustration_prompt = DeepSeekPromptEnhancer().analyze_story_for_illustration(
        story_text="林见微在北宋汴京的思源茶楼外拓印印章，听茶客议论旧案。",
        character_info={"name": "林见微", "gender": "女", "age": 25, "era": "北宋汴京，古代中国"},
    )

    combined = scene_desc + illustration_prompt
    assert "羽绒服" not in combined
    assert "电暖器" not in combined
    assert "公路" not in combined
    assert "小餐馆" not in combined
