"""No-mock gameplay behavior tests for option relevance and text cleanup."""

from types import SimpleNamespace

import pytest

from config.prompts import (
    get_opening_story_prompt,
    get_round_event_prompt,
    get_story_only_prompt,
    get_weekly_summary_prompt,
)
from src.ai.models import EventOption, GameEvent
from src.ai.option_generator import OptionGenerator
from src.ai.story_generator import StoryGenerator
from src.ai.text_quality import (normalize_chinese_punctuation,
                                 normalize_generated_story,
                                 validate_narrative_quality)

pytestmark = [pytest.mark.unit]



def test_option_generator_rejects_generic_options_for_specific_decision_point() -> None:
    event = GameEvent(
        event_description=(
            "苏小二把潮湿的账册推到桌边，压低声音问："
            "“你现在要不要跟我去码头，把交货人当场截住？”"
        ),
        options=[
            EventOption(text="保持平常心继续前进", effects={"energy": 0, "mood": 0}),
            EventOption(text="积极面对新的一天", effects={"energy": -5, "mood": 5}),
        ],
    )

    with pytest.raises(ValueError, match="generic"):
        OptionGenerator.ensure_options_consistency(
            event=event,
            story_description=event.event_description,
            available_people=["苏小二"],
            language="zh",
        )


def test_option_generator_accepts_options_tied_to_story_decision_point() -> None:
    event = GameEvent(
        event_description=(
            "苏小二把潮湿的账册推到桌边，压低声音问："
            "“你现在要不要跟我去码头，把交货人当场截住？”"
        ),
        options=[
            EventOption(text="跟苏小二去码头截人", effects={"energy": -8, "mood": 2}),
            EventOption(text="留下核对账册暗号", effects={"knowledge": 6, "mood": -2}),
        ],
    )

    OptionGenerator.ensure_options_consistency(
        event=event,
        story_description=event.event_description,
        available_people=["苏小二"],
        language="zh",
    )


def test_chinese_punctuation_normalizer_cleans_dialogue_artifacts() -> None:
    raw = '他说: "你真的要去吗?" 她停了一下, 说: "现在就走."'

    assert (
        normalize_chinese_punctuation(raw) == "他说：“你真的要去吗？” 她停了一下，说：“现在就走。”"
    )


def test_chinese_punctuation_normalizer_handles_parenthesis_endings_and_closes_quotes() -> None:
    raw = "A)开始. B)结束."

    cleaned = normalize_chinese_punctuation(raw)

    assert "（" not in cleaned
    assert "." not in cleaned
    assert "A）开始。B）结束。" == cleaned


def test_normalized_story_closes_unbalanced_dialogue_quote() -> None:
    raw = '他说:"你会来吗?'

    cleaned = normalize_generated_story(raw, language="zh", perspective="second")

    assert cleaned.startswith("他说：“你会来吗？")
    assert cleaned.endswith("”")


def test_generated_story_normalizer_removes_internal_state_leaks_and_over_fragmentation() -> None:
    raw = (
        "【状态】energy -5, mood +3\n"
        "你推开门。\n"
        "雨声停了。\n"
        "账册还在。\n"
        "你看见苏小二站在檐下。\n"
        "他把油纸伞递过来。\n"
    )

    cleaned = normalize_generated_story(raw, language="zh", perspective="second")

    assert "energy" not in cleaned
    assert "mood" not in cleaned
    assert "【状态】" not in cleaned
    assert cleaned.count("\n\n") <= 2
    assert "你推开门。雨声停了。" in cleaned


def test_generated_story_normalizer_closes_unbalanced_chinese_dialogue_quote() -> None:
    raw = (
        "苏清岚接过咖啡暖着手。\n\n"
        "陈雨桐拉过椅子坐下：“你昨晚又失眠了？黑眼圈都快掉到下巴了。"
    )

    cleaned = normalize_generated_story(raw, language="zh", perspective="third")

    assert cleaned.endswith("。”")


def test_narrative_quality_rejects_mixed_perspective_and_internal_leaks() -> None:
    text = "你走进铺子。\n\n我忽然想起系统判定：mood +5，wealth -10。"

    issues = validate_narrative_quality(text, language="zh", perspective="second")

    assert "mixed_perspective" in issues
    assert "internal_state_leak" in issues


def test_narrative_quality_can_enforce_story_shape_bounds() -> None:
    too_short = "她推开会议室的门，发现白板上还留着昨晚的需求优先级。"
    too_long = "她把用户反馈重新贴到白板上。" * 260
    fragmented = "\n".join(["她停下。", "灯亮着。", "风很冷。", "门开了。", "他没说话。", "她抬头。"])

    assert "story_too_short" in validate_narrative_quality(
        too_short,
        language="zh",
        perspective="third",
        min_chars=800,
        max_chars=1200,
    )
    assert "story_too_long" in validate_narrative_quality(
        too_long,
        language="zh",
        perspective="third",
        min_chars=800,
        max_chars=1200,
    )
    assert "over_fragmented_paragraphs" in validate_narrative_quality(
        fragmented,
        language="zh",
        perspective="third",
        min_chars=10,
        max_chars=1200,
    )


def test_story_prompt_includes_world_model_location_career_and_repetition_constraints() -> None:
    player_state = {
        "player_name": "林舟",
        "week": 8,
        "world_model_data": {
            "character_locations": {
                "林舟": {
                    "location": "上海徐汇区的工作室",
                    "region": "上海",
                    "since_week": 4,
                    "travel_mode": "resident",
                },
                "周岚": {
                    "location": "杭州西湖边的住处",
                    "region": "杭州",
                    "since_week": 6,
                    "travel_mode": "resident",
                },
            },
            "career_records": {
                "林舟": {
                    "current_job": "初级产品经理",
                    "employer": "海桐科技",
                    "level": "junior",
                    "since_week": 2,
                    "history": [],
                }
            },
        },
    }

    world_model = StoryGenerator._build_world_model_from_state_dict(player_state)
    prompt = get_story_only_prompt(
        player_state=player_state,
        language="zh",
        character_settings={"relationships": {"key_people": [{"name": "周岚", "role": "朋友"}]}},
        world_model=world_model,
        overused_phrases="【动态禁用】不要再用“晨光熹微”。",
    )

    assert "林舟 当前位置：上海徐汇区的工作室" in prompt
    assert "周岚 当前位置：杭州西湖边的住处" in prompt
    assert "两个在不同地点的角色不能在同一物理场景中对话或互动" in prompt
    assert "林舟：初级产品经理（海桐科技），级别=junior" in prompt
    assert "职位变动必须合理递进" in prompt
    assert "不要再用“晨光熹微”" in prompt


def test_story_prompts_pin_player_identity_from_state_and_character_settings() -> None:
    player_state = {
        "player_name": "林见微",
        "age": 23,
        "week": 0,
        "current_round": 0,
        "rounds_per_week": 3,
    }
    character_settings = {
        "era": {"year": 690, "era_description": "唐代神都洛阳"},
        "gender": {"gender": "女", "gender_description": "女性"},
        "world": {"world_description": "古代宫廷与市井交错"},
        "family": {"family_description": "书香门第"},
        "traits": {"traits_description": "谨慎敏锐"},
    }

    story_prompt = get_story_only_prompt(
        player_state=player_state,
        language="zh",
        character_settings=character_settings,
    )
    round_prompt = get_round_event_prompt(
        player_state=player_state,
        language="zh",
        round_number=0,
        round_context="",
        character_settings=character_settings,
    )

    for prompt in (story_prompt, round_prompt):
        assert "主角名称是：林见微" in prompt
        assert "禁止编造其他名字" in prompt
        assert "性别：女" in prompt


def test_story_prompts_limit_each_round_to_one_main_event() -> None:
    player_state = {
        "player_name": "顾晨曦",
        "age": 24,
        "week": 2,
        "current_round": 1,
        "rounds_per_week": 3,
        "energy": 70,
        "mood": 62,
        "knowledge": 58,
        "wealth": 18000,
    }
    character_settings = {
        "era": {"year": 2024, "era_description": "2024年中国互联网行业"},
        "identity": {"identity_description": "初级产品经理"},
        "world": {"world_description": "杭州AI协作工具创业公司"},
        "relationships": {"key_people": [{"name": "周岚", "role": "直属导师"}]},
    }

    story_prompt = get_story_only_prompt(
        player_state=player_state,
        language="zh",
        character_settings=character_settings,
        last_event_description="上周她完成了需求评审。",
    )
    round_prompt = get_round_event_prompt(
        player_state=player_state,
        language="zh",
        round_number=1,
        round_context="周一她收到导师周岚的原型反馈。",
        character_settings=character_settings,
    )

    for prompt in (story_prompt, round_prompt):
        assert "每个回合只推进一个主事件" in prompt
        assert "只设置一个核心决策点" in prompt
        assert "禁止在同一回合塞入多个会议、评审、复盘、预热" in prompt
        assert "禁止把下一周或下一个回合的实际剧情提前写完" in prompt


def test_opening_story_prompt_forbids_replacing_player_with_template_hero() -> None:
    prompt = get_opening_story_prompt(
        character_settings={
            "era": {"year": 690, "era_description": "唐代神都洛阳"},
            "gender": {"gender": "女", "gender_description": "女性"},
            "world": {"world_description": "古代宫廷与市井交错"},
        },
        player_name="林见微",
        life_vision="查明家族旧案",
        formatted_family_members="母亲：林夫人",
        language="zh",
    )

    assert "主角姓名必须是：林见微" in prompt
    assert "绝对禁止把主角改名为狄仁杰" in prompt
    assert "主角性别必须是：女" in prompt


def test_opening_story_prompt_anchors_first_week_date_and_season() -> None:
    prompt = get_opening_story_prompt(
        character_settings={
            "era": {"year": 2024, "era_description": "2024年中国互联网行业"},
            "gender": {"gender": "女"},
            "world": {"world_description": "杭州AI协作工具创业公司"},
        },
        player_name="顾晨曦",
        life_vision="2020年代中国互联网公司，成为AI协作工具产品经理",
        formatted_family_members="母亲：周梅",
        language="zh",
    )

    assert "2024年1月第1周" in prompt
    assert "冬季" in prompt
    assert "禁止写成夏季" in prompt


def test_realistic_modern_prompts_forbid_unrequested_cyberpunk_ip_drift() -> None:
    character_settings = {
        "era": {"year": 2024, "era_description": "2024年中国现代都市"},
        "age": {"age": 28},
        "gender": {"gender": "男"},
        "world": {
            "world_description": "现实中的上海互联网公司，普通产品经理成长线",
            "technology_level": "2020年代常见办公软件、手机、电脑",
            "social_system": "现代法治社会",
        },
        "career": {"occupation": "产品经理"},
    }
    player_state = {
        "player_name": "张若虚",
        "age": 28,
        "week": 0,
        "current_round": 0,
        "rounds_per_week": 3,
        "wealth": 50000,
    }

    prompts = [
        get_opening_story_prompt(
            character_settings=character_settings,
            player_name="张若虚",
            life_vision="在2020年代中国互联网公司成为成熟产品经理",
            formatted_family_members="",
            language="zh",
        ),
        get_story_only_prompt(
            player_state=player_state,
            language="zh",
            character_settings=character_settings,
        ),
        get_round_event_prompt(
            player_state=player_state,
            language="zh",
            round_number=0,
            round_context="",
            character_settings=character_settings,
        ),
    ]

    for prompt in prompts:
        assert "现实主义世界边界" in prompt
        assert "禁止赛博朋克" in prompt
        assert "夜之城" in prompt
        assert "荒坂集团" in prompt
        assert "Cyberpunk 2077" in prompt


def test_explicit_cyberpunk_settings_do_not_get_realistic_modern_drift_block() -> None:
    prompt = get_story_only_prompt(
        player_state={
            "player_name": "V",
            "age": 28,
            "week": 0,
            "current_round": 0,
            "rounds_per_week": 3,
        },
        language="zh",
        character_settings={
            "era": {"year": 2077, "era_description": "赛博朋克未来都市"},
            "world": {"world_description": "高科技低生活的原创赛博朋克世界"},
        },
    )

    assert "现实主义世界边界" not in prompt


def test_weekly_summary_prompt_forbids_next_week_day_mismatch() -> None:
    prompt = get_weekly_summary_prompt(
        rounds=[
            {"round": 0, "summary": "周一完成需求澄清", "choice": "继续推进", "effects": {}},
            {"round": 1, "summary": "周中评审原型", "choice": "找同事复盘", "effects": {}},
            {"round": 2, "summary": "周末整理白皮书", "choice": "修改计划", "effects": {}},
        ],
        character_settings={},
        language="zh",
        game_date_info={
            "date_string": "2024年1月第1周",
            "season": "冬",
            "age": 24,
            "total_week": 1,
        },
    )

    assert "2024年1月第1周" in prompt
    assert "禁止写成“周日（第2周）”" in prompt
    assert "不得把下一周" in prompt


def test_round_event_generation_surfaces_failure_when_provider_is_unavailable() -> None:
    from src.ai.story_exceptions import StoryGenerationFailure

    class FailingClient:
        def call(self, **_kwargs):
            raise RuntimeError("AI unavailable")

    with pytest.raises(StoryGenerationFailure, match="AI unavailable"):
        StoryGenerator(FailingClient()).generate_round_event(
            player_state={
                "player_name": "林见微",
                "age": 22,
                "week": 1,
                "current_round": 0,
            },
            language="zh",
            round_number=0,
            round_context="",
            character_settings={
                "era": {"era_description": "唐代神都洛阳"},
                "traits": {"traits_description": "谨慎敏锐"},
            },
            option_generator=OptionGenerator(FailingClient()),
        )


def test_round_event_retries_when_ai_story_is_too_short_for_quality_budget(
    constraint_harness_disabled,
) -> None:
    short_story = (
        "顾晨曦推开会议室的门，发现陆昊然已经把访谈记录贴在白板上。"
        "陈晓雨递来一杯咖啡，提醒她今天必须先决定需求优先级。"
    )
    repaired_story = (
        "第2周·周中，顾晨曦走进会议室时，投影幕还停在昨晚的用户访谈表。"
        "雨水沿着玻璃往下滑，屏幕上的红色标记把她没处理完的问题照得格外刺眼。"
        "陆昊然没有立刻催她汇报，只把三份打印稿推到桌边，让她先看最上面那一页。"
        "那是一个老用户凌晨两点发来的长反馈，语气克制，却把试用流程里最卡人的步骤逐条列了出来。"
        "顾晨曦越看越沉默，她原本准备在评审会上强调增长入口，现在却发现基础体验还没有站稳。"
        "陈晓雨坐在她旁边，低声提醒她别急着把所有责任揽到自己身上，先把问题拆成今天能处理的部分。"
        "窗外的雨声压住了走廊里的脚步声，会议室里只剩白板笔划过纸面的细响。"
        "陆昊然问她，如果只能在今天推进一件事，是先说服团队暂停新入口，还是先补一轮用户复盘。"
        "顾晨曦捏着那份反馈，意识到这不是一次普通汇报，而是她第一次要为自己的判断承担节奏。"
        "她抬头看向白板，等着自己把答案说出口。"
        "她先把所有反馈按影响范围分成三列，又把昨晚临时写下的增长方案折到笔记本后页。"
        "这个动作让她心里稳了一点，因为她终于承认，真正的问题不是入口不够显眼，而是新用户还没有被顺利带到核心流程。"
        "陈晓雨帮她把几条最刺眼的评论圈出来，提醒她不要只看数字下降，也要看用户在哪一步开始失去耐心。"
        "陆昊然则把会议日程往后推了十分钟，给她留出一小段重新组织表达的时间。"
        "顾晨曦听见自己的呼吸慢下来，开始把原本准备好的汇报顺序一项项划掉。"
        "她知道这样会让今天的评审变得更难看，却也明白如果继续粉饰问题，明天只会在更大的会上被迫解释。"
        "当研发负责人推门进来时，她没有急着展示新入口草图，而是把那页用户反馈递了过去。"
        "她说自己想先暂停增长入口一天，用这一天补齐用户复盘和流程修正，再决定下个版本是否继续推进。"
        "会议室安静下来，所有人的目光都落在她手里的笔上。"
        "陆昊然问她：\"如果团队要求你今天就给出上线结论，你准备坚持这个判断吗？\""
        "顾晨曦没有立刻回答，她先看了看陈晓雨递来的圈注，又看向还没擦掉的流程图。"
        "这一刻，她必须决定是守住刚刚形成的判断，还是重新回到更稳妥的汇报稿。"
    )

    class ShortThenValidClient:
        def __init__(self):
            self.calls = []

        def call(self, **kwargs):
            self.calls.append(kwargs)
            return short_story if len(self.calls) == 1 else repaired_story

    class RecordingOptionGenerator:
        def __init__(self):
            self.generate_options_only_kwargs = None

        def generate_options_only(self, **kwargs):
            self.generate_options_only_kwargs = kwargs
            return GameEvent(
                event_description=kwargs["story_description"],
                options=[
                    EventOption(text="暂停新入口", effects={"knowledge": 5}),
                    EventOption(text="补用户复盘", effects={"energy": -4}),
                ],
            )

        def validate_and_fix_relationships(self, *args, **kwargs):
            return None

        def validate_event_quality(self, *args, **kwargs):
            return None

        def validate_options_consistency(self, *args, **kwargs):
            return []

        def ensure_options_consistency(self, *args, **kwargs):
            return None

    client = ShortThenValidClient()
    option_generator = RecordingOptionGenerator()

    event = StoryGenerator(client).generate_round_event(
        player_state={
            "game_id": 10,
            "player_name": "顾晨曦",
            "age": 25,
            "week": 1,
            "current_round": 1,
        },
        language="zh",
        round_number=1,
        round_context="周初她收到了导师的评审反馈。",
        character_settings={
            "relationships": {
                "key_people": [
                    {"name": "陆昊然", "role": "导师"},
                    {"name": "陈晓雨", "role": "闺蜜"},
                ]
            }
        },
        option_generator=option_generator,
    )

    assert len(client.calls) == 2
    retry_prompt = client.calls[1]["user_prompt"]
    assert "故事太短" in retry_prompt
    assert option_generator.generate_options_only_kwargs is not None
    expected_story = normalize_generated_story(repaired_story, language="zh", perspective="third")
    story_for_options = option_generator.generate_options_only_kwargs["story_description"]
    assert story_for_options == expected_story
    assert event.event_description == expected_story


def test_round_event_repairs_length_after_a_quick_validation_retry(
    monkeypatch,
    constraint_harness_disabled,
) -> None:
    """A quick retry must not bypass the configured story-length contract."""
    quick_failure = "林清忽略了预设关系网。"
    overlong_retry = "林清在会议室整理项目风险。" * 100
    repaired_story = "林清和陆昊然复核风险清单，陈晓雨记录需要当天确认的三项决策。" * 20

    class Client:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def call(self, **kwargs):
            self.calls.append(kwargs)
            return [quick_failure, overlong_retry, repaired_story][len(self.calls) - 1]

    class OptionGenerator:
        def generate_options_only(self, **kwargs):
            return GameEvent(
                event_description=kwargs["story_description"],
                options=[
                    EventOption(text="确认风险清单", effects={}),
                    EventOption(text="请陆昊然复核优先级", effects={}),
                ],
            )

        def validate_and_fix_relationships(self, *args, **kwargs):
            return None

        def validate_options_consistency(self, *args, **kwargs):
            return []

    quick_results = iter(
        [
            SimpleNamespace(passed=False, issues=["名单外人物"], warnings=[]),
            SimpleNamespace(passed=True, issues=[], warnings=[]),
            SimpleNamespace(passed=True, issues=[], warnings=[]),
        ]
    )
    shape_results = iter([["story_too_long"], []])
    monkeypatch.setattr(
        "src.ai.quick_validator.quick_validate_story",
        lambda **_kwargs: next(quick_results),
    )
    monkeypatch.setattr(
        "src.ai.story_generator.validate_narrative_quality",
        lambda *_args, **_kwargs: next(shape_results),
    )

    client = Client()
    event = StoryGenerator(client).generate_round_event(
        player_state={"player_name": "林清", "week": 1, "current_round": 0},
        language="zh",
        round_number=0,
        round_context="",
        character_settings={},
        option_generator=OptionGenerator(),
    )

    assert len(client.calls) == 3
    assert "故事太长" in str(client.calls[2]["user_prompt"])
    assert event.event_description == repaired_story


def test_round_event_retries_when_story_ignores_all_key_people_and_fabricates_new_cast(
    constraint_harness_disabled,
) -> None:
    class DriftClient:
        def __init__(self):
            self.calls = []

        def call(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return (
                    "马老板把欠条拍在桌上，方蕾和赵子豪站在苏州贸易公司的门口，"
                    "王丽华低声催促主角马上接管父亲留下的债务。"
                )
            return (
                "陆昊然把产品评审文档推到林见微面前，陈晓雨提醒她先确认用户反馈，"
                "林一凡则把远程会议链接发进群里。"
            ) * 20

    class RecordingOptionGenerator:
        def __init__(self):
            self.generate_options_only_kwargs = None

        def generate_options_only(self, **kwargs):
            self.generate_options_only_kwargs = kwargs
            return GameEvent(
                event_description="",
                options=[
                    EventOption(text="先和陆昊然核对需求", effects={"knowledge": 5}),
                    EventOption(text="请陈晓雨一起复盘用户反馈", effects={"mood": 2}),
                ],
            )

        def validate_and_fix_relationships(self, *args, **kwargs):
            return None

        def validate_options_consistency(self, *args, **kwargs):
            return []

    client = DriftClient()
    gen = StoryGenerator(client)
    option_generator = RecordingOptionGenerator()

    gen.generate_round_event(
        player_state={
            "game_id": 7,
            "player_name": "林见微",
            "age": 22,
            "week": 1,
            "current_round": 0,
        },
        language="zh",
        round_number=0,
        round_context="第一周周一，产品新人入职后的第一次需求评审。",
        character_settings={
            "relationships": {
                "key_people": [
                    {"name": "陆昊然", "role": "导师"},
                    {"name": "陈晓雨", "role": "同事"},
                    {"name": "林一凡", "role": "朋友"},
                ]
            }
        },
        option_generator=option_generator,
    )

    assert len(client.calls) == 2
    retry_prompt = client.calls[1]["user_prompt"]
    assert "名单外命名角色" in retry_prompt
    assert option_generator.generate_options_only_kwargs is not None
    story_for_options = option_generator.generate_options_only_kwargs["story_description"]
    assert "陆昊然" in story_for_options
    assert "马老板" not in story_for_options


def test_quick_validator_flags_key_people_dilution_with_invented_cast() -> None:
    from src.ai.quick_validator import quick_validate_story

    result = quick_validate_story(
        story_text=(
            "陆昊然在会议室门口只匆匆露了一面。随后马老板、方蕾、赵子豪、"
            "王丽华、张建国律师轮番要求林见微处理苏州贸易公司的债务。"
        ),
        available_people=["陆昊然", "陈晓雨", "林一凡"],
        language="zh",
    )

    assert not result.passed
    assert any("名单外命名角色" in issue for issue in result.issues)
    assert any("覆盖低于建议值" in warning for warning in result.warnings)


def test_event_generation_retries_when_story_dilutes_key_people_with_invented_cast() -> None:
    class DriftClient:
        def __init__(self):
            self.calls = []

        def call(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return (
                    "陆昊然在会议室门口只匆匆露了一面。随后马老板、方蕾、赵子豪、"
                    "王丽华、张建国律师轮番要求林见微处理苏州贸易公司的债务。"
                )
            return (
                "陆昊然把产品评审文档推到林见微面前，陈晓雨提醒她先确认用户反馈，"
                "林一凡则把远程会议链接发进群里。"
            )

    client = DriftClient()
    gen = StoryGenerator(client)

    class RecordingOptionGenerator:
        def __init__(self):
            self.generate_options_only_kwargs = None

        def generate_options_only(self, **kwargs):
            self.generate_options_only_kwargs = kwargs
            return GameEvent(
                event_description="",
                options=[
                    EventOption(text="先和陆昊然核对需求", effects={"knowledge": 5}),
                    EventOption(text="请陈晓雨一起复盘用户反馈", effects={"mood": 2}),
                    EventOption(text="找林一凡确认技术边界", effects={"knowledge": 4}),
                ],
            )

        def validate_and_fix_relationships(self, *args, **kwargs):
            return None

        def validate_event_quality(self, *args, **kwargs):
            return None

        def validate_options_consistency(self, *args, **kwargs):
            return []

        def ensure_options_consistency(self, *args, **kwargs):
            return None

    option_generator = RecordingOptionGenerator()

    gen.generate_event(
        player_state={
            "game_id": 8,
            "player_name": "林见微",
            "age": 22,
            "week": 1,
            "current_round": 0,
        },
        language="zh",
        retry_count=2,
        character_settings={
            "relationships": {
                "key_people": [
                    {"name": "陆昊然", "role": "导师"},
                    {"name": "陈晓雨", "role": "同事"},
                    {"name": "林一凡", "role": "朋友"},
                ]
            }
        },
        option_generator=option_generator,
    )

    assert len(client.calls) == 2
    retry_prompt = client.calls[1]["user_prompt"]
    assert "名单外命名角色" in retry_prompt
    assert option_generator.generate_options_only_kwargs is not None
    story_for_options = option_generator.generate_options_only_kwargs["story_description"]
    assert "陈晓雨" in story_for_options
    assert "马老板" not in story_for_options


def test_round_event_retries_when_modern_story_drifts_into_cyberpunk_ip_world() -> None:
    class DriftClient:
        def __init__(self):
            self.calls = []

        def call(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return (
                    "夜之城的霓虹灯照在张若虚脸上，荒坂集团的安全员追着V穿过Viktor的诊所，"
                    "义体医生让他准备植入新的神经接口。"
                )
            return "张若虚在上海办公室复盘用户反馈，决定先和研发同事确认需求边界。" * 30

    class RecordingOptionGenerator:
        def __init__(self):
            self.generate_options_only_kwargs = None

        def generate_options_only(self, **kwargs):
            self.generate_options_only_kwargs = kwargs
            return GameEvent(
                event_description="",
                options=[
                    EventOption(text="复盘用户反馈", effects={"knowledge": 5}),
                    EventOption(text="确认需求边界", effects={"energy": -3}),
                ],
            )

        def validate_and_fix_relationships(self, *args, **kwargs):
            return None

        def validate_event_quality(self, *args, **kwargs):
            return None

        def validate_options_consistency(self, *args, **kwargs):
            return []

        def ensure_options_consistency(self, *args, **kwargs):
            return None

    client = DriftClient()
    option_generator = RecordingOptionGenerator()

    StoryGenerator(client).generate_round_event(
        player_state={
            "game_id": 9,
            "player_name": "张若虚",
            "age": 28,
            "week": 1,
            "current_round": 0,
        },
        language="zh",
        round_number=0,
        round_context="现代上海互联网公司的一周开始。",
        character_settings={
            "era": {"year": 2024, "era_description": "2024年中国现代都市"},
            "world": {"world_description": "现实中的上海互联网公司，普通产品经理成长线"},
            "career": {"occupation": "产品经理"},
        },
        option_generator=option_generator,
    )

    assert len(client.calls) == 2
    retry_prompt = client.calls[1]["user_prompt"]
    assert "赛博朋克" in retry_prompt or "外部IP" in retry_prompt
    assert option_generator.generate_options_only_kwargs is not None
    story_for_options = option_generator.generate_options_only_kwargs["story_description"]
    assert "上海办公室" in story_for_options
    assert "夜之城" not in story_for_options
    assert "荒坂" not in story_for_options


def test_round_event_does_not_return_drift_story_after_quick_validation_retry_fails() -> None:
    from src.ai.story_exceptions import StoryGenerationFailure

    class AlwaysDriftClient:
        def __init__(self):
            self.calls = []

        def call(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return (
                    "夜之城的雨落在荒坂集团楼下，Viktor让V准备植入新的神经接口。"
                    "马老板、方蕾、赵子豪又在旁边逼林见微接手苏州贸易公司的债务。"
                )
            return (
                "荒坂集团的安保继续追着V穿过夜之城，马老板把欠条拍在诊所桌上，"
                "方蕾和赵子豪要求林见微立刻处理一笔陌生债务。"
            )

    class UnusedOptionGenerator:
        def generate_options_only(self, **kwargs):
            raise AssertionError("drift story should not be passed to option generation")

    with pytest.raises(StoryGenerationFailure):
        StoryGenerator(AlwaysDriftClient()).generate_round_event(
            player_state={
                "game_id": 10,
                "player_name": "林见微",
                "age": 25,
                "week": 1,
                "current_round": 0,
            },
            language="zh",
            round_number=0,
            round_context="现代上海互联网公司，产品经理新人的第一周。",
            character_settings={
                "era": {"year": 2024, "era_description": "2024年中国现代都市"},
                "world": {"world_description": "现实中的上海互联网公司，普通产品经理成长线"},
                "career": {"occupation": "产品经理"},
                "relationships": {
                    "key_people": [
                        {"name": "陆昊然", "role": "导师"},
                        {"name": "陈晓雨", "role": "闺蜜"},
                        {"name": "林一凡", "role": "同期"},
                    ]
                },
            },
            option_generator=UnusedOptionGenerator(),
        )
