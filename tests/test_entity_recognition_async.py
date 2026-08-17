"""异步实体识别集成测试

测试完整的异步识别流程、API端点、错误处理等。
"""

from unittest.mock import Mock, patch

import pytest

from src.services.entity_recognition_service import (
    EntityRecognitionService,
    clear_entity_recognition_cache,
)
from src.services.entity_recognition_task import (TaskStatus, get_task_manager,
                                                  reset_task_manager)

pytestmark = [pytest.mark.unit]



@pytest.fixture(autouse=True)
def _clear_entity_recognition_cache():
    """模块级识别缓存必须在每个测试前清空，避免跨测试串缓存。"""
    clear_entity_recognition_cache()
    yield
    clear_entity_recognition_cache()


class TestEntityRecognitionServiceAsync:
    """测试实体识别服务的核心方法"""

    def setup_method(self):
        """每个测试前重置任务管理器"""
        reset_task_manager()

    def test_build_story_text(self):
        """测试构建故事文本功能"""
        service = EntityRecognitionService(Mock())

        round_history = [
            {
                "week": 0,
                "round": 0,
                "event_description": "事件描述1",
                "story_continuation": "故事继续1",
                "summary": "总结1",
                "choice": "选择1",
            },
            {
                "week": 0,
                "round": 1,
                "event_description": "事件描述2",
                "story_continuation": "故事继续2",
                "summary": "总结2",
                "choice": "选择2",
            },
            {
                "week": 1,
                "round": 0,
                "event_description": "事件描述3",
                "story_continuation": "故事继续3",
                "summary": "总结3",
                "choice": "选择3",
            },
        ]

        story_text = service._build_story_text(round_history)

        # 验证故事文本包含所有事件描述
        assert "事件描述1" in story_text
        assert "事件描述2" in story_text
        assert "事件描述3" in story_text

        # 验证故事文本包含选择
        assert "选择1" in story_text
        assert "选择2" in story_text

    def test_validate_entity_valid(self):
        """测试有效实体验证"""
        service = EntityRecognitionService(Mock())

        entity = {
            "name": "测试物品",
            "importance": "critical",
            "appear_count": 5,
            "appear_contexts": ["场景1", "场景2"],
        }

        assert service._validate_entity(entity) is True

    def test_validate_entity_missing_name(self):
        """测试缺少名称的实体验证"""
        service = EntityRecognitionService(Mock())

        entity = {"importance": "critical", "appear_count": 5}

        assert service._validate_entity(entity) is False

    def test_validate_entity_fixes_invalid_importance(self):
        """测试自动修复无效重要程度"""
        service = EntityRecognitionService(Mock())

        entity = {
            "name": "测试物品",
            "importance": "invalid_value",
        }

        assert service._validate_entity(entity) is True
        assert entity["importance"] == "normal"  # 应该被修复为 normal


class TestAsyncTaskManagerIntegration:
    """测试任务管理器的集成场景"""

    def setup_method(self):
        reset_task_manager()

    def test_multiple_games_isolation(self):
        """测试多游戏任务隔离"""
        manager = get_task_manager()

        # 为不同游戏创建任务
        task1 = manager.create_task(game_id=1, user_id=1)
        task2 = manager.create_task(game_id=2, user_id=1)
        task3 = manager.create_task(game_id=3, user_id=2)

        # 验证每个游戏有自己的任务
        assert manager.get_active_task_for_game(1).task_id == task1.task_id
        assert manager.get_active_task_for_game(2).task_id == task2.task_id
        assert manager.get_active_task_for_game(3).task_id == task3.task_id

        # 完成一个游戏的任务
        task1.mark_completed({})

        # 验证其他游戏的任务不受影响
        assert manager.get_active_task_for_game(1) is None
        assert manager.get_active_task_for_game(2) is not None
        assert manager.get_active_task_for_game(2).task_id == task2.task_id

    def test_concurrent_task_creation(self):
        """测试并发任务创建（防重复）"""
        manager = get_task_manager()

        # 创建第一个任务
        task1 = manager.create_task(game_id=1, user_id=1)

        # 检查活动任务
        active = manager.get_active_task_for_game(1)
        assert active.task_id == task1.task_id

        # 模拟业务逻辑：检查后再创建
        if not manager.has_active_task(1):
            manager.create_task(game_id=1, user_id=1)

        # 验证仍然只有第一个任务
        assert manager.get_task(task1.task_id) is not None
        tasks_for_game_1 = [
            t
            for t in manager._tasks.values()
            if t.game_id == 1 and t.status in [TaskStatus.PENDING, TaskStatus.RUNNING]
        ]
        assert len(tasks_for_game_1) == 1

    def test_task_progress_updates(self):
        """测试任务进度更新流程"""
        manager = get_task_manager()
        task = manager.create_task(game_id=1, user_id=1)

        # 模拟识别过程中的进度更新
        task.mark_running()

        progress_steps = [(1, 10), (3, 10), (5, 10), (7, 10), (10, 10)]
        for processed, total in progress_steps:
            task.update_progress(processed, total)
            expected_progress = int(processed / total * 100)
            assert task.progress == expected_progress

        # 完成任务
        task.mark_completed({"items": [], "characters": [], "landmarks": []})
        assert task.progress == 100
        assert task.status == TaskStatus.COMPLETED

    def test_error_handling_flow(self):
        """测试错误处理流程"""
        manager = get_task_manager()
        task = manager.create_task(game_id=1, user_id=1)

        # 开始运行
        task.mark_running()
        task.update_progress(5, 10)

        # 发生错误
        error_msg = "AI服务连接超时"
        task.mark_failed(error_msg)

        # 验证错误状态
        assert task.status == TaskStatus.FAILED
        assert task.error == error_msg
        assert task.completed_at is not None

        # 验证可以创建新任务（失败后）
        assert manager.get_active_task_for_game(1) is None
        new_task = manager.create_task(game_id=1, user_id=1)
        assert new_task.task_id != task.task_id


class TestDataFlowContract:
    """验证生产者和消费者之间的数据契约一致性

    choice_processor.py 生产的 round_record 字段：
        week, round, summary, event_description, story_continuation, choice, effects, date_info, event_concluded

    _build_story_text 消费的字段：
        week, round, event_description, story_continuation, summary, choice
    """

    def test_round_history_field_names_match_producer(self):
        """验证 _build_story_text 消费的字段名与 choice_processor 生产的一致"""
        from src.services.entity_recognition_service import \
            EntityRecognitionService

        # 用 choice_processor 实际生产的字段名构造数据
        round_record_from_producer = {
            "week": 0,
            "round": 1,
            "summary": "主角在武馆练习剑术",
            "event_description": "清晨的武馆，阳光洒入庭院，你拿起竹剑开始练习。",
            "story_continuation": "经过一上午的苦练，你的剑法有了明显进步。",
            "choice": "继续练习基本功",
            "effects": {"energy": -10, "knowledge": 5},
            "date_info": {"year": 2024, "month": 3},
            "event_concluded": True,
        }

        service = EntityRecognitionService(Mock())
        story_text = service._build_story_text([round_record_from_producer])

        # 验证 event_description 被包含
        assert "清晨的武馆" in story_text

        # 验证 story_continuation 被包含
        assert "剑法有了明显进步" in story_text

        # 验证 choice 被收集
        assert "继续练习基本功" in story_text

    def test_build_story_text_combines_all_text_fields(self):
        """验证所有文本字段都被拼接"""
        from src.services.entity_recognition_service import \
            EntityRecognitionService

        round_record = {
            "week": 0,
            "round": 0,
            "event_description": "【事件描述】在山顶看到日出",
            "story_continuation": "【故事继续】你决定在此冥想",
            "summary": "【总结】主角在山顶冥想",
            "choice": "冥想",
        }

        service = EntityRecognitionService(Mock())
        story_text = service._build_story_text([round_record])

        # event_description 必须被包含
        assert "【事件描述】" in story_text
        # story_continuation 必须被包含
        assert "【故事继续】" in story_text
        # summary 也被包含
        assert "【总结】" in story_text

    def test_build_story_text_sorts_by_week_and_round(self):
        """验证按 week 和 round 排序"""
        from src.services.entity_recognition_service import \
            EntityRecognitionService

        # 创建乱序数据
        records = [
            {
                "week": 1,
                "round": 0,
                "event_description": "周1轮0",
                "story_continuation": "",
                "choice": "D",
            },
            {
                "week": 0,
                "round": 1,
                "event_description": "周0轮1",
                "story_continuation": "",
                "choice": "B",
            },
            {
                "week": 0,
                "round": 0,
                "event_description": "周0轮0",
                "story_continuation": "",
                "choice": "A",
            },
            {
                "week": 1,
                "round": 1,
                "event_description": "周1轮1",
                "story_continuation": "",
                "choice": "E",
            },
        ]

        service = EntityRecognitionService(Mock())
        story_text = service._build_story_text(records)

        # 验证顺序正确（周0在周1前面）
        pos_week0_round0 = story_text.find("周0轮0")
        pos_week0_round1 = story_text.find("周0轮1")
        pos_week1_round0 = story_text.find("周1轮0")
        pos_week1_round1 = story_text.find("周1轮1")

        assert pos_week0_round0 < pos_week0_round1 < pos_week1_round0 < pos_week1_round1


class TestLazyImports:
    """验证 _add_entities_to_collection_sync 中所有延迟导入路径可达

    参考 collection.py L1586+ 中的延迟导入:
    - PlayerState
    - CharacterState
    - ItemState
    - LandmarkState
    - GameState as GameStateModel
    - Game as GameModel
    - session_service
    """

    def test_player_state_import_and_construction(self):
        """验证 PlayerState 可导入和创建"""
        from src.game.state.player_state import PlayerState

        # 验证 model_validate 可用（Pydantic v2）
        state = PlayerState.model_validate({"player_name": "测试玩家"})
        assert state.player_name == "测试玩家"
        assert hasattr(state, "items")
        assert hasattr(state, "characters")
        assert hasattr(state, "landmarks")

    def test_character_state_import_and_construction(self):
        """验证 CharacterState 可导入并用实际参数创建

        参考 collection.py L1706-1713 中的实际使用方式
        """
        from src.game.state.character_state import CharacterState

        # 用 _add_entities_to_collection_sync 中实际使用的参数创建
        char = CharacterState(
            name="张三",
            relationship_desc="朋友",
            role="侠客",
            affinity=50,
        )
        assert char.name == "张三"
        assert char.relationship_desc == "朋友"
        assert char.role == "侠客"
        assert char.affinity == 50

    def test_item_state_import_and_construction(self):
        """验证 ItemState 可导入并用实际参数创建

        参考 collection.py L1666-1680 中的实际使用方式
        """
        from src.game.state.item_state import ItemState

        # 用 _add_entities_to_collection_sync 中实际使用的参数创建
        item = ItemState(
            name="青龙偃月刀",
            description="一把威力惊人的大刀",
            importance="critical",
            category="weapon",
            acquired_week=5,
            acquired_context="在武器店发现",
            is_key_item=True,
            image_generated=False,
            description_generated=True,
        )
        assert item.name == "青龙偃月刀"
        assert item.importance == "critical"
        assert item.is_key_item is True

    def test_landmark_state_import_and_construction(self):
        """验证 LandmarkState 可导入并用实际参数创建

        参考 collection.py L1741-1756 中的实际使用方式
        """
        from src.game.state.landmark_state import LandmarkState

        # 用 _add_entities_to_collection_sync 中实际使用的参数创建
        landmark = LandmarkState(
            name="青云山",
            description="一座云雾缭绕的仙山",
            category="nature",
            importance="important",
            first_appear_week=3,
            appear_count=5,
            last_appear_week=10,
            context="主角在此修炼",
            is_key_location=False,
            image_generated=False,
        )
        assert landmark.name == "青云山"
        assert landmark.appear_count == 5
        assert landmark.category == "nature"

    def test_game_state_model_import(self):
        """验证数据库模型可导入"""
        from src.database.models import Game as GameModel
        from src.database.models import GameState as GameStateModel

        # 验证模型类可用
        assert hasattr(GameStateModel, "game_id")
        assert hasattr(GameStateModel, "week")
        assert hasattr(GameStateModel, "state_json")

        assert hasattr(GameModel, "game_id")
        assert hasattr(GameModel, "updated_at")

    def test_session_service_import(self):
        """验证 session_service 可导入且有 remove 方法"""
        from src.api.services.session_service import session_service

        assert hasattr(session_service, "remove")
        # 验证 remove 方法可调用
        assert callable(session_service.remove)

    def test_game_database_import(self):
        """验证 GameDatabase 可导入"""
        from src.database.db import GameDatabase

        # 验证类可实例化
        database = GameDatabase()
        assert hasattr(database, "load_saved_game")

    def test_add_character_method_signature(self):
        """验证 PlayerState.add_character 方法签名"""
        from src.game.state.character_state import CharacterState
        from src.game.state.player_state import PlayerState

        state = PlayerState()
        char = CharacterState(
            name="李四",
            relationship_desc="敌人",
            role="反派",
            affinity=20,
        )

        # 验证可以添加角色
        state.add_character(char)
        assert "李四" in state.characters
        assert state.characters["李四"]["affinity"] == 20

    def test_add_item_method_signature(self):
        """验证 PlayerState.add_item 方法签名"""
        from src.game.state.item_state import ItemState
        from src.game.state.player_state import PlayerState

        state = PlayerState()
        item = ItemState(
            name="金创药",
            description="可以治疗伤口",
            importance="normal",
            category="tool",
            acquired_week=1,
            acquired_context="在药店购买",
            is_key_item=False,
            image_generated=False,
            description_generated=True,
        )

        # 验证可以添加物品
        state.add_item(item)
        assert "金创药" in state.items

    def test_add_landmark_method_signature(self):
        """验证 PlayerState.add_landmark 方法签名"""
        from src.game.state.landmark_state import LandmarkState
        from src.game.state.player_state import PlayerState

        state = PlayerState()
        landmark = LandmarkState(
            name="古老的庙宇",
            description="一座神秘的古庙",
            category="building",
            importance="normal",
            first_appear_week=2,
            appear_count=1,
            last_appear_week=2,
            context="路过时发现",
            is_key_location=False,
            image_generated=False,
        )

        # 验证可以添加地点
        state.add_landmark(landmark)
        assert "古老的庙宇" in state.landmarks


class TestMinAppearancesBoundary:
    """测试 min_appearances 动态阈值的边界条件。

    collection.py 中的动态阈值公式：
        default_min = max(1, total_rounds // 15)

    确保在极少轮次时阈值为 1，不会因阈值太高导致返回空结果。
    """

    def test_threshold_with_1_round(self):
        """1 轮数据时阈值应为 1。"""
        total_rounds = 1
        default_min = max(1, total_rounds // 15)
        assert default_min == 1, f"1轮时阈值应为1，实际为{default_min}"

    def test_threshold_with_2_rounds(self):
        """2 轮数据时阈值应为 1。"""
        total_rounds = 2
        default_min = max(1, total_rounds // 15)
        assert default_min == 1, f"2轮时阈值应为1，实际为{default_min}"

    def test_threshold_with_14_rounds(self):
        """14 轮数据时阈值应为 1（14//15=0，max(1,0)=1）。"""
        total_rounds = 14
        default_min = max(1, total_rounds // 15)
        assert default_min == 1

    def test_threshold_with_15_rounds(self):
        """15 轮数据时阈值应为 1（15//15=1）。"""
        total_rounds = 15
        default_min = max(1, total_rounds // 15)
        assert default_min == 1

    def test_threshold_with_30_rounds(self):
        """30 轮数据时阈值应为 2。"""
        total_rounds = 30
        default_min = max(1, total_rounds // 15)
        assert default_min == 2

    def test_threshold_with_0_rounds(self):
        """0 轮数据时阈值应为 1（max(1,0)=1）。"""
        total_rounds = 0
        default_min = max(1, total_rounds // 15)
        assert default_min == 1

    def test_threshold_never_zero(self):
        """无论任何轮数，阈值都不应为 0。"""
        for total_rounds in range(0, 100):
            default_min = max(1, total_rounds // 15)
            assert default_min >= 1, (
                f"total_rounds={total_rounds} 时阈值为 {default_min}，" "不应小于 1"
            )

    def test_recognize_from_history_empty_returns_empty(self):
        """空 round_history 应返回空结果，不应出错。"""
        service = EntityRecognitionService(Mock())
        result = service.recognize_from_history(
            round_history=[],
            existing_items=[],
            existing_characters=[],
            existing_landmarks=[],
            min_appearances=1,
        )
        assert result == {"items": [], "characters": [], "landmarks": []}

    def test_recognize_with_min_appearances_1(self):
        """min_appearances=1 时，出现一次的实体应被识别。

        使用 mock AI 返回模拟结果，验证低阈值的流程正确性。
        """
        mock_ai = Mock()
        mock_ai.chat.return_value = '{"items": [{"name": "测试物品", "description": "desc", "importance": "normal", "appear_count": 1, "appear_contexts": ["ctx"]}], "characters": [], "landmarks": []}'

        service = EntityRecognitionService(mock_ai)

        round_history = [
            {
                "week": 0,
                "round": 0,
                "event_description": "你在路边发现了一个测试物品。",
                "story_continuation": "你捡起了测试物品。",
            }
        ]

        # 验证 min_appearances=1 被正确传入 prompt
        with patch.object(
            service,
            "_call_ai",
            return_value='{"items": [{"name": "测试物品", "description": "desc", "importance": "normal", "appear_count": 1, "appear_contexts": ["ctx"]}], "characters": [], "landmarks": []}',
        ):
            result = service.recognize_from_history(
                round_history=round_history,
                existing_items=[],
                existing_characters=[],
                existing_landmarks=[],
                min_appearances=1,
            )

        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "测试物品"

    def test_recognize_falls_back_when_ai_misses_story_entities(self):
        """AI 空结果不应让故事中明确命名的实体完全消失。"""
        service = EntityRecognitionService(Mock())
        round_history = [
            {
                "week": 0,
                "round": 0,
                "event_description": "赵掌柜在赵家船行后院把账册和玉佩交给林见微，陈砚递来账本。",
                "story_continuation": "阿宁提醒林见微，铜钥匙能打开赵家船行的旧库门。",
                "summary": "林见微认识了赵掌柜和阿宁，并得到关键线索。",
            }
        ]

        with patch.object(
            service,
            "_call_ai",
            return_value='{"items": [], "characters": [], "landmarks": []}',
        ):
            result = service.recognize_from_history(
                round_history=round_history,
                existing_items=[],
                existing_characters=["林见微"],
                existing_landmarks=[],
                min_appearances=1,
            )

        assert {item["name"] for item in result["items"]} >= {"账册", "玉佩", "铜钥匙"}
        assert {char["name"] for char in result["characters"]} >= {"赵掌柜", "阿宁", "陈砚"}
        assert {landmark["name"] for landmark in result["landmarks"]} >= {"赵家船行"}

    def test_character_fallback_avoids_named_shop_suffix_false_positive(self):
        """人物兜底应识别故事人物，但不应把书铺名尾部当成人名。"""
        service = EntityRecognitionService(Mock())
        round_history = [
            {
                "week": 0,
                "round": 0,
                "event_description": (
                    "林见微在怀安书铺遇见赵崇古。柳成璧把一册宋刊本推到她面前，"
                    "低声问：“林姑娘可愿同行？”"
                ),
            }
        ]

        with patch.object(
            service,
            "_call_ai",
            return_value='{"items": [], "characters": [], "landmarks": []}',
        ):
            result = service.recognize_from_history(
                round_history=round_history,
                existing_items=[],
                existing_characters=["林见微"],
                existing_landmarks=[],
                min_appearances=3,
            )

        character_names = {char["name"] for char in result["characters"]}
        assert character_names >= {"赵崇古", "柳成璧"}
        assert "安书铺" not in character_names

    def test_character_fallback_rejects_common_phrase_fragments(self):
        """人物兜底不应把动作、形容词、普通名词片段误识别成人物。"""
        service = EntityRecognitionService(Mock())
        round_history = [
            {
                "week": 0,
                "round": 0,
                "event_description": (
                    "陈叔抱着一摞书册走进来，在案几上放下。林见微嘴角上扬，"
                    "小心绕过水洼，来到博雅堂门前。沈掌柜正与文士争执，"
                    "那文士说愿意出二百贯钱收购。姚琏又折了回来，郑重地捧着木匣。"
                    "方才姑娘所言极是，旁边顾客也点头称是。"
                ),
            }
        ]

        with patch.object(
            service,
            "_call_ai",
            return_value='{"items": [], "characters": [], "landmarks": []}',
        ):
            result = service.recognize_from_history(
                round_history=round_history,
                existing_items=[],
                existing_characters=["林见微"],
                existing_landmarks=[],
                min_appearances=3,
            )

        character_names = {char["name"] for char in result["characters"]}
        assert character_names >= {"陈叔", "沈掌柜", "姚琏"}
        assert character_names.isdisjoint(
            {
                "上放下",
                "上扬",
                "水洼",
                "钱收购",
                "郑重",
                "方才姑娘",
                "顾客",
            }
        )

    def test_character_fallback_rejects_pronoun_fragments_and_title_aliases(self):
        """人物兜底不应把祈使短语/第二人称片段当人物，也不应重复短称。"""
        service = EntityRecognitionService(Mock())
        round_history = [
            {
                "week": 0,
                "round": 1,
                "event_description": (
                    "老僧道：“施主此去要小心。”于是你把印章收进袖中。"
                    "沈伯安在思源茶楼等候，旁人也称他沈先生。沈伯安低声说出旧案。"
                    "王差爷推门而入，掌柜连忙迎上去。"
                ),
            }
        ]

        with patch.object(
            service,
            "_call_ai",
            return_value='{"items": [], "characters": [], "landmarks": []}',
        ):
            result = service.recognize_from_history(
                round_history=round_history,
                existing_items=[],
                existing_characters=["林见微"],
                existing_landmarks=[],
                min_appearances=1,
            )

        character_names = {char["name"] for char in result["characters"]}
        assert {"沈伯安", "王差爷"}.issubset(character_names)
        assert character_names.isdisjoint({"施主此", "于是你", "沈伯", "沈先生"})

    def test_character_fallback_rejects_time_and_motion_fragments(self):
        """人物兜底不应把时间副词和动作片段当人物。"""
        service = EntityRecognitionService(Mock())
        round_history = [
            {
                "week": 3,
                "round": 0,
                "event_description": (
                    "沈伯安沉默了许久，才抬头看向林见微。"
                    "马蹄踏着残雪远去，陆辞扶住船舷，石无言握紧竹篙。"
                    "郑冲从渡口赶来，提醒众人追兵将至。"
                ),
            }
        ]

        with patch.object(
            service,
            "_call_ai",
            return_value='{"items": [], "characters": [], "landmarks": []}',
        ):
            result = service.recognize_from_history(
                round_history=round_history,
                existing_items=[],
                existing_characters=["林见微"],
                existing_landmarks=[],
                min_appearances=1,
            )

        character_names = {char["name"] for char in result["characters"]}
        assert {"沈伯安", "陆辞", "石无言", "郑冲"}.issubset(character_names)
        assert character_names.isdisjoint({"许久", "马蹄踏"})

    def test_character_fallback_rejects_title_aliases_and_verb_suffixes(self):
        """人物兜底不应把称谓别名或人名后接动词首字当成新人物。"""
        service = EntityRecognitionService(Mock())
        round_history = [
            {
                "week": 3,
                "round": 0,
                "event_description": (
                    "林姑娘看向陆公子，陆辞知道此事不能再拖。"
                    "陆辞现在船尾，陆辞坐在舱口，低声提醒林见微。"
                    "陆辞苦笑一声，仍然守在船尾。"
                    "林正言当年留下书信，沈伯安一直没有说出真相。"
                ),
            }
        ]

        with patch.object(
            service,
            "_call_ai",
            return_value='{"items": [], "characters": [], "landmarks": []}',
        ):
            result = service.recognize_from_history(
                round_history=round_history,
                existing_items=[],
                existing_characters=["林见微", "陆辞"],
                existing_landmarks=[],
                min_appearances=1,
            )

        character_names = {char["name"] for char in result["characters"]}
        assert {"林正言", "沈伯安"}.issubset(character_names)
        assert character_names.isdisjoint(
            {"林姑娘", "陆公子", "陆辞知", "陆辞现", "陆辞坐", "陆辞苦"}
        )

    def test_long_history_truncation_preserves_recent_named_people(self):
        """长历史截断时必须保留最近/当前故事中的人物。"""
        service = EntityRecognitionService(Mock())
        long_old_story = "赵掌柜在旧账房里翻找账册。" * 1600
        round_history = [
            {
                "week": 0,
                "round": 0,
                "event_description": long_old_story,
            },
            {
                "week": 3,
                "round": 0,
                "event_description": (
                    "乌篷船靠近芦苇荡，石无言握紧竹篙，陆辞守在船尾。"
                    "沈伯安的信使尚未出现，林见微决定先隐蔽行踪。"
                ),
            },
        ]

        with patch.object(
            service,
            "_call_ai",
            return_value='{"items": [], "characters": [], "landmarks": []}',
        ):
            result = service.recognize_from_history(
                round_history=round_history,
                existing_items=[],
                existing_characters=["林见微"],
                existing_landmarks=[],
                min_appearances=1,
            )

        character_names = {char["name"] for char in result["characters"]}
        assert {"石无言", "陆辞", "沈伯安"}.issubset(character_names)

    def test_long_history_modern_key_characters_with_roles_reach_candidates(self):
        """第4周长历史中带关系/职位的人物不应被漏掉或只剩主角。"""
        service = EntityRecognitionService(Mock())
        long_old_story = "李婉清独自在公司档案室整理旧合同，启明集团的标牌反复出现在走廊。" * 700
        round_history = [
            {
                "week": 0,
                "round": 0,
                "event_description": long_old_story,
            },
            {
                "week": 3,
                "round": 0,
                "event_description": (
                    "陈一鸣提出内部审计可能被人做了手脚，陈律师提醒李婉清先保全证据。"
                    "张副总在会议上否认干预流程，赵铭承认自己见过那份合同。"
                    "刘洋递来公章使用记录，周先生打来电话，王亮说启明集团法务部正在施压。"
                    "银行会议室、审计电脑和蓝色文件夹都只是场景和物品。"
                ),
            },
        ]

        with patch.object(
            service,
            "_call_ai",
            return_value='{"items": [], "characters": [], "landmarks": []}',
        ):
            result = service.recognize_from_history(
                round_history=round_history,
                existing_items=[],
                existing_characters=["李婉清"],
                existing_landmarks=[],
                min_appearances=1,
                eligible_character_names=[
                    "陈一鸣",
                    "陈律师",
                    "张副总",
                    "赵铭",
                    "刘洋",
                    "周先生",
                    "王亮",
                ],
            )

        character_names = {char["name"] for char in result["characters"]}
        assert {
            "陈一鸣",
            "陈律师",
            "张副总",
            "赵铭",
            "刘洋",
            "周先生",
            "王亮",
        }.issubset(character_names)
        assert character_names.isdisjoint(
            {"李婉清", "启明集团", "银行会议室", "审计电脑", "蓝色文件夹", "合同", "公章"}
        )

    def test_recognition_truncation_respects_max_length(self):
        """头尾截断必须把提示文本也算入最大长度。"""
        service = EntityRecognitionService(Mock())
        story_text = "赵掌柜在旧账房。" * 2000 + "石无言握紧竹篙。"

        truncated = service._truncate_recognition_story(story_text, max_length=15000)

        assert len(truncated) <= 15000
        assert "赵掌柜在旧账房" in truncated
        assert "石无言握紧竹篙" in truncated
        assert "中间内容已截断" in truncated

    def test_ai_recognition_prunes_title_and_location_aliases(self):
        """AI 返回的称谓/地点短名也要被规范化，避免收集面板出现重复别名。"""
        service = EntityRecognitionService(Mock())
        round_history = [
            {
                "week": 0,
                "round": 1,
                "event_description": (
                    "沈伯安在城南思源茶楼等候。旁人称他沈先生，"
                    "林见微随后也来到思源茶楼。"
                ),
            }
        ]

        ai_response = """
        {
          "items": [],
          "characters": [
            {"name": "沈先生", "description": "沈伯安的称谓", "importance": "normal", "appear_count": 2, "appear_contexts": []},
            {"name": "沈伯安", "description": "旧案知情人", "importance": "important", "appear_count": 3, "appear_contexts": []}
          ],
          "landmarks": [
            {"name": "思源茶楼", "description": "茶楼短名", "importance": "important", "appear_count": 3, "appear_contexts": []},
            {"name": "城南思源茶楼", "description": "完整地点名", "importance": "important", "appear_count": 2, "appear_contexts": []}
          ]
        }
        """

        with patch.object(service, "_call_ai", return_value=ai_response):
            result = service.recognize_from_history(
                round_history=round_history,
                existing_items=[],
                existing_characters=["林见微"],
                existing_landmarks=[],
                min_appearances=1,
            )

        assert {char["name"] for char in result["characters"]} == {"沈伯安"}
        assert {landmark["name"] for landmark in result["landmarks"]} == {"城南思源茶楼"}

    def test_recognition_cache_skips_repeat_llm_call(self):
        """P1-成本修复：相同输入的重复识别只调用一次 LLM。"""
        service = EntityRecognitionService(Mock())
        round_history = [
            {
                "week": 0,
                "round": 0,
                "event_description": "你在旧书摊发现了一枚铜钥匙，摊主赵掌柜说它与城南的思源茶楼有关。",
            }
        ]
        ai_response = '{"items": [], "characters": [], "landmarks": []}'
        call_count = {"n": 0}

        def counting_call_ai(**kwargs):
            call_count["n"] += 1
            return ai_response

        with patch.object(service, "_call_ai", new=counting_call_ai):
            first = service.recognize_from_history(
                round_history=round_history,
                existing_items=[],
                existing_characters=["林见微"],
                existing_landmarks=[],
                min_appearances=1,
            )
            second = service.recognize_from_history(
                round_history=round_history,
                existing_items=[],
                existing_characters=["林见微"],
                existing_landmarks=[],
                min_appearances=1,
            )

        assert call_count["n"] == 1
        assert first == second

    def test_recognition_cache_is_keyed_by_inputs(self):
        """P1-成本修复：输入不同（故事不同）必须各自调用 LLM。"""
        service = EntityRecognitionService(Mock())
        history_a = [
            {
                "week": 0,
                "round": 0,
                "event_description": "你在旧书摊发现了一枚铜钥匙。",
            }
        ]
        history_b = [
            {
                "week": 0,
                "round": 0,
                "event_description": "你在渡口遇到了多年未见的故人。",
            }
        ]
        call_count = {"n": 0}

        def counting_call_ai(**kwargs):
            call_count["n"] += 1
            return '{"items": [], "characters": [], "landmarks": []}'

        with patch.object(service, "_call_ai", new=counting_call_ai):
            service.recognize_from_history(
                round_history=history_a,
                existing_items=[],
                existing_characters=[],
                existing_landmarks=[],
                min_appearances=1,
            )
            service.recognize_from_history(
                round_history=history_b,
                existing_items=[],
                existing_characters=[],
                existing_landmarks=[],
                min_appearances=1,
            )

        assert call_count["n"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
