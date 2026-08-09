"""Provider-free round-event fallback contracts."""

from src.game.round.event_generator import RoundEventGenerator


def _generator(language: str) -> RoundEventGenerator:
    return RoundEventGenerator(
        player_state_getter=lambda: None, ai_generator=None, language_getter=lambda: language,
        character_introduction_service=None, summary_selector=None, relationship_service=None,
    )


def test_scheduled_event_fallback_preserves_all_commitments_in_chinese() -> None:
    event = _generator("zh")._generate_simple_scheduled_event(
        [{"description": "联系母亲"}, {"description": "提交档案"}], player_state=None
    )

    assert event.event_description == "到了兑现承诺的时候了。联系母亲；提交档案。你需要做出选择。"
    assert [option.text for option in event.options] == ["认真兑现承诺", "敷衍了事", "找借口推迟"]
    assert event.options[0].effects == {"mood": 10, "energy": -10}


def test_english_scheduled_fallback_and_nested_setting_extraction_are_deterministic() -> None:
    generator = _generator("en")
    event = generator._generate_simple_scheduled_event(
        [{"description": "Call Maya"}], player_state=None
    )

    assert event.event_description.startswith("It's time to fulfill your commitment. Call Maya.")
    assert event.options[0].text == "Fulfill the commitment seriously"
    assert RoundEventGenerator._extract_setting_text(
        {"identity": {"details": [{"profession": "archive editor"}]}},
        ["occupation", "profession"],
    ) == "archive editor"
    assert RoundEventGenerator._extract_setting_text({}, ["occupation"]) == ""
