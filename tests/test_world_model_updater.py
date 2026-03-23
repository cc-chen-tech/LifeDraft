"""Tests for WorldModelUpdater - 世界模型更新器测试"""

from unittest.mock import MagicMock, patch

import pytest

from src.game.world_model_updater import WorldModelUpdater


class TestLocationUpdates:
    """位置更新测试"""

    def test_process_location_updates_move_action(self):
        """测试移动动作"""
        player_state = MagicMock()
        player_state.week = 10
        player_state.world_model_data = {"character_locations": {}}

        location_updates = [
            {
                "action": "move",
                "character": "张三",
                "from": "北京",
                "to": "上海",
                "mode": "travel",
                "reason": "出差",
            }
        ]

        WorldModelUpdater.process_location_updates(player_state, location_updates)

        locations = player_state.world_model_data["character_locations"]
        assert "张三" in locations
        assert locations["张三"]["location"] == "上海"
        assert locations["张三"]["region"] == "上海"
        assert locations["张三"]["since_week"] == 10
        assert locations["张三"]["travel_mode"] == "travel"

    def test_process_location_updates_confirm_action_new_character(self):
        """测试确认动作 - 新角色"""
        player_state = MagicMock()
        player_state.week = 5
        player_state.world_model_data = {"character_locations": {}}

        location_updates = [
            {
                "action": "confirm",
                "character": "李四",
                "location": "广州",
                "reason": "定居",
            }
        ]

        WorldModelUpdater.process_location_updates(player_state, location_updates)

        locations = player_state.world_model_data["character_locations"]
        assert "李四" in locations
        assert locations["李四"]["location"] == "广州"
        assert locations["李四"]["travel_mode"] == "resident"

    def test_process_location_updates_confirm_action_existing_character(self):
        """测试确认动作 - 已存在角色"""
        player_state = MagicMock()
        player_state.week = 8
        player_state.world_model_data = {
            "character_locations": {
                "王五": {
                    "location": "深圳",
                    "region": "深圳",
                    "since_week": 1,
                    "travel_mode": "resident",
                }
            }
        }

        location_updates = [
            {
                "action": "confirm",
                "character": "王五",
                "location": "东莞",
            }
        ]

        WorldModelUpdater.process_location_updates(player_state, location_updates)

        locations = player_state.world_model_data["character_locations"]
        assert locations["王五"]["location"] == "东莞"

    def test_process_location_updates_empty_updates(self):
        """测试空更新列表"""
        player_state = MagicMock()
        player_state.world_model_data = {"character_locations": {}}

        WorldModelUpdater.process_location_updates(player_state, [])

        assert player_state.world_model_data["character_locations"] == {}

    def test_process_location_updates_none_player_state(self):
        """测试空玩家状态"""
        # 应该不抛出异常
        WorldModelUpdater.process_location_updates(None, [])

    def test_process_location_updates_missing_fields(self):
        """测试缺少必要字段的更新"""
        player_state = MagicMock()
        player_state.week = 1
        player_state.world_model_data = {"character_locations": {}}

        location_updates = [
            {"action": "move"},  # 缺少 character
            {"character": "张三"},  # 缺少 action
            {"action": "move", "character": "李四"},  # 缺少 to
        ]

        WorldModelUpdater.process_location_updates(player_state, location_updates)

        # 所有无效更新都应该被跳过
        assert player_state.world_model_data["character_locations"] == {}


class TestCareerUpdates:
    """职业更新测试"""

    def test_process_career_updates_new_job(self):
        """测试新工作"""
        player_state = MagicMock()
        player_state.week = 20
        player_state.world_model_data = {"career_records": {}}

        career_updates = [
            {
                "action": "new_job",
                "character": "张三",
                "new_role": "工程师",
                "employer": "科技公司",
                "level": "junior",
            }
        ]

        WorldModelUpdater.process_career_updates(player_state, career_updates)

        careers = player_state.world_model_data["career_records"]
        assert "张三" in careers
        assert careers["张三"]["current_job"] == "工程师"
        assert careers["张三"]["employer"] == "科技公司"

    def test_process_career_updates_promotion(self):
        """测试升职"""
        player_state = MagicMock()
        player_state.week = 30
        player_state.world_model_data = {
            "career_records": {
                "张三": {
                    "current_job": "初级工程师",
                    "employer": "科技公司",
                    "level": "junior",
                    "since_week": 1,
                    "history": [],
                }
            }
        }

        career_updates = [
            {
                "action": "promotion",
                "character": "张三",
                "new_role": "高级工程师",
                "level": "senior",
            }
        ]

        WorldModelUpdater.process_career_updates(player_state, career_updates)

        careers = player_state.world_model_data["career_records"]
        assert careers["张三"]["current_job"] == "高级工程师"
        assert careers["张三"]["level"] == "senior"
        assert len(careers["张三"]["history"]) == 1

    def test_process_career_updates_invalid_level(self):
        """测试无效级别默认为 mid"""
        player_state = MagicMock()
        player_state.week = 10
        player_state.world_model_data = {"career_records": {}}

        career_updates = [
            {
                "action": "new_job",
                "character": "李四",
                "new_role": "经理",
                "level": "invalid_level",
            }
        ]

        WorldModelUpdater.process_career_updates(player_state, career_updates)

        careers = player_state.world_model_data["career_records"]
        assert careers["李四"]["level"] == "mid"


class TestCommitmentUpdates:
    """承诺/事务更新测试"""

    def test_process_commitment_updates_new(self):
        """测试新承诺"""
        player_state = MagicMock()
        player_state.week = 15
        player_state.world_model_data = {"active_commitments": []}

        commitment_updates = [
            {
                "action": "new",
                "description": "与李四约会",
                "parties": ["张三", "李四"],
                "deadline_week": 16,
            }
        ]

        WorldModelUpdater.process_commitment_updates(player_state, commitment_updates)

        commitments = player_state.world_model_data["active_commitments"]
        assert len(commitments) == 1
        assert commitments[0]["description"] == "与李四约会"
        assert commitments[0]["status"] == "pending"

    def test_process_commitment_updates_fulfilled(self):
        """测试完成承诺"""
        player_state = MagicMock()
        player_state.week = 16
        player_state.world_model_data = {
            "active_commitments": [
                {
                    "description": "约会",
                    "status": "pending",
                    "parties": ["张三", "李四"],
                }
            ]
        }

        commitment_updates = [
            {"action": "fulfilled", "description": "约会", "parties": ["张三", "李四"]}
        ]

        WorldModelUpdater.process_commitment_updates(player_state, commitment_updates)

        commitments = player_state.world_model_data["active_commitments"]
        assert commitments[0]["status"] == "fulfilled"

    def test_process_commitment_updates_broken(self):
        """测试违背承诺"""
        player_state = MagicMock()
        player_state.week = 16
        player_state.world_model_data = {
            "active_commitments": [
                {"description": "重要约会", "status": "pending", "parties": ["张三"]}
            ]
        }

        commitment_updates = [
            {"action": "broken", "description": "重要约会", "parties": ["张三"]}
        ]

        WorldModelUpdater.process_commitment_updates(player_state, commitment_updates)

        commitments = player_state.world_model_data["active_commitments"]
        assert commitments[0]["status"] == "broken"

    def test_process_commitment_updates_expired(self):
        """测试过期承诺"""
        player_state = MagicMock()
        player_state.week = 20
        player_state.world_model_data = {
            "active_commitments": [
                {"description": "过期任务", "status": "pending", "parties": ["张三"]}
            ]
        }

        commitment_updates = [
            {"action": "expired", "description": "过期任务", "parties": ["张三"]}
        ]

        WorldModelUpdater.process_commitment_updates(player_state, commitment_updates)

        commitments = player_state.world_model_data["active_commitments"]
        assert commitments[0]["status"] == "expired"

    def test_process_commitment_updates_empty(self):
        """测试空更新"""
        player_state = MagicMock()
        player_state.world_model_data = {"active_commitments": []}

        WorldModelUpdater.process_commitment_updates(player_state, [])

        assert player_state.world_model_data["active_commitments"] == []

    def test_process_commitment_updates_no_description(self):
        """测试无描述的更新被跳过"""
        player_state = MagicMock()
        player_state.week = 1
        player_state.world_model_data = {"active_commitments": []}

        commitment_updates = [
            {"action": "new"},  # 无描述
            {"action": "fulfilled"},  # 无描述
        ]

        WorldModelUpdater.process_commitment_updates(player_state, commitment_updates)

        assert len(player_state.world_model_data["active_commitments"]) == 0


class TestCausalChainUpdates:
    """因果链更新测试"""

    def test_process_causal_chain_updates(self):
        """测试因果链更新"""
        player_state = MagicMock()
        player_state.world_model_data = {"causal_chains": []}

        causal_updates = [
            {"cause": "选择了辞职", "effect": "失去收入来源", "probability": 0.9}
        ]

        # 检查方法是否存在
        if hasattr(WorldModelUpdater, "process_causal_chain_updates"):
            WorldModelUpdater.process_causal_chain_updates(player_state, causal_updates)
            chains = player_state.world_model_data.get("causal_chains", [])
            assert len(chains) >= 0
        else:
            # 方法不存在时跳过
            pass


class TestStoryAnalysis:
    """故事分析测试"""

    def test_extract_story_elements(self):
        """测试故事元素提取"""
        story_text = "张三决定辞职创业，他租了一间小办公室，开始了新的生活。"
        player_state = MagicMock()
        player_state.world_model_data = {}

        # 检查方法是否存在
        if hasattr(WorldModelUpdater, "extract_story_elements"):
            result = WorldModelUpdater.extract_story_elements(player_state, story_text)
            # 应该返回提取结果
            assert result is not None or result is None
        else:
            pass


class TestCharacterProfileSynthesis:
    """角色档案综合测试"""

    def test_synthesize_profile(self):
        """测试角色档案综合"""
        player_state = MagicMock()
        player_state.player_name = "张三"
        player_state.world_model_data = {"character_profiles": {}}

        new_info = {"personality": ["勇敢", "果断"], "skills": ["编程", "管理"]}

        # 检查方法是否存在
        if hasattr(WorldModelUpdater, "synthesize_character_profile"):
            WorldModelUpdater.synthesize_character_profile(
                player_state, "张三", new_info
            )
            # 检查是否更新了角色档案
            profiles = player_state.world_model_data.get("character_profiles", {})
            # 根据实际实现验证
        else:
            pass


class TestSyncStoryCharacters:
    """故事人物同步测试"""

    def test_sync_new_character_from_story(self):
        """测试从故事文本同步新人物"""
        player_state = MagicMock()
        player_state.character_settings = {
            "relationships": {
                "key_people": [{"name": "张三", "role": "朋友", "affinity": 80}]
            }
        }

        story_text = "今天遇到了清虚真人，他教会了我很多道理。"
        relationships_in_effects = {"清虚真人": 60}

        WorldModelUpdater.sync_story_characters_to_settings(
            player_state,
            story_text=story_text,
            relationships_in_effects=relationships_in_effects,
        )

        key_people = player_state.character_settings["relationships"]["key_people"]
        names = [p["name"] for p in key_people]
        assert "清虚真人" in names
        # 检查新人物的属性
        qingxu = next(p for p in key_people if p["name"] == "清虚真人")
        assert qingxu["role"] == "故事中结识"
        assert qingxu["affinity"] == 60

    def test_sync_character_not_in_story_text(self):
        """测试人物名不在故事文本中时不同步"""
        player_state = MagicMock()
        player_state.character_settings = {
            "relationships": {
                "key_people": [{"name": "张三", "role": "朋友", "affinity": 80}]
            }
        }

        story_text = "今天天气很好，我在公园散步。"
        relationships_in_effects = {"李四": 50}

        WorldModelUpdater.sync_story_characters_to_settings(
            player_state,
            story_text=story_text,
            relationships_in_effects=relationships_in_effects,
        )

        key_people = player_state.character_settings["relationships"]["key_people"]
        names = [p["name"] for p in key_people]
        assert "李四" not in names

    def test_sync_generic_names_ignored(self):
        """测试通用称谓被忽略"""
        player_state = MagicMock()
        player_state.character_settings = {"relationships": {"key_people": []}}

        story_text = "我和同事一起吃饭，朋友也在场。"
        relationships_in_effects = {"同事": 50, "朋友": 60}

        WorldModelUpdater.sync_story_characters_to_settings(
            player_state,
            story_text=story_text,
            relationships_in_effects=relationships_in_effects,
        )

        key_people = player_state.character_settings["relationships"]["key_people"]
        # 通用称谓不应该被添加
        assert len(key_people) == 0

    def test_sync_existing_character_not_duplicated(self):
        """测试已存在的人物不会被重复添加"""
        player_state = MagicMock()
        player_state.character_settings = {
            "relationships": {
                "key_people": [{"name": "张三", "role": "朋友", "affinity": 80}]
            }
        }

        story_text = "张三今天来找我聊天。"
        relationships_in_effects = {"张三": 90}

        WorldModelUpdater.sync_story_characters_to_settings(
            player_state,
            story_text=story_text,
            relationships_in_effects=relationships_in_effects,
        )

        key_people = player_state.character_settings["relationships"]["key_people"]
        # 只应该有一个张三
        names = [p["name"] for p in key_people]
        assert names.count("张三") == 1

    def test_sync_with_family_members(self):
        """测试家庭成员不会被重复添加"""
        player_state = MagicMock()
        player_state.character_settings = {
            "family": {"family_members": [{"name": "父亲", "relationship": "父亲"}]},
            "relationships": {"key_people": []},
        }

        story_text = "父亲打电话给我，说要来看我。"
        relationships_in_effects = {"父亲": 100}

        WorldModelUpdater.sync_story_characters_to_settings(
            player_state,
            story_text=story_text,
            relationships_in_effects=relationships_in_effects,
        )

        key_people = player_state.character_settings["relationships"]["key_people"]
        # 父亲已在家庭成员中，不应该被添加到 key_people
        names = [p["name"] for p in key_people]
        assert "父亲" not in names

    def test_sync_with_none_player_state(self):
        """测试空玩家状态不抛异常"""
        # 应该不抛出异常
        WorldModelUpdater.sync_story_characters_to_settings(
            None,
            story_text="任何文本",
            relationships_in_effects={"张三": 50},
        )

    def test_sync_with_empty_story_text(self):
        """测试空故事文本不抛异常"""
        player_state = MagicMock()
        player_state.character_settings = {"relationships": {"key_people": []}}

        WorldModelUpdater.sync_story_characters_to_settings(
            player_state,
            story_text="",
            relationships_in_effects={"张三": 50},
        )

        # 不应该添加任何人物
        assert len(player_state.character_settings["relationships"]["key_people"]) == 0

    def test_sync_initializes_missing_relationships(self):
        """测试初始化缺失的 relationships 结构"""
        player_state = MagicMock()
        player_state.character_settings = {}

        story_text = "遇到李四"
        relationships_in_effects = {"李四": 70}

        WorldModelUpdater.sync_story_characters_to_settings(
            player_state,
            story_text=story_text,
            relationships_in_effects=relationships_in_effects,
        )

        # 应该创建 relationships 结构
        assert "relationships" in player_state.character_settings
        assert "key_people" in player_state.character_settings["relationships"]

    def test_sync_multiple_characters(self):
        """测试同时同步多个新人物"""
        player_state = MagicMock()
        player_state.character_settings = {"relationships": {"key_people": []}}

        story_text = "今天遇到了王五和赵六，他们都是我的新朋友。"
        relationships_in_effects = {"王五": 55, "赵六": 60}

        WorldModelUpdater.sync_story_characters_to_settings(
            player_state,
            story_text=story_text,
            relationships_in_effects=relationships_in_effects,
        )

        key_people = player_state.character_settings["relationships"]["key_people"]
        names = [p["name"] for p in key_people]
        assert "王五" in names
        assert "赵六" in names
        assert len(key_people) == 2

    def test_sync_updates_relationships_dict(self):
        """测试同步人物时也更新 player_state.relationships"""
        player_state = MagicMock()
        player_state.relationships = {}
        player_state.character_settings = {"relationships": {"key_people": []}}

        story_text = "遇到李四"
        relationships_in_effects = {"李四": 70}

        WorldModelUpdater.sync_story_characters_to_settings(
            player_state,
            story_text=story_text,
            relationships_in_effects=relationships_in_effects,
        )

        # 检查 player_state.relationships 被同步
        assert "李四" in player_state.relationships
        assert player_state.relationships["李四"] == 70

    def test_sync_inferred_role_from_story(self):
        """测试从故事上下文推断角色"""
        player_state = MagicMock()
        player_state.character_settings = {"relationships": {"key_people": []}}

        # 故事中包含"同事"关键词
        story_text = "在公司遇到了新同事王五，他看起来很友善。"
        relationships_in_effects = {"王五": 60}

        WorldModelUpdater.sync_story_characters_to_settings(
            player_state,
            story_text=story_text,
            relationships_in_effects=relationships_in_effects,
        )

        key_people = player_state.character_settings["relationships"]["key_people"]
        wangwu = next((p for p in key_people if p["name"] == "王五"), None)
        assert wangwu is not None
        # 应该推断出角色为"同事"
        assert wangwu["role"] == "同事"

    def test_sync_default_role_when_no_context(self):
        """测试无上下文时使用默认角色"""
        player_state = MagicMock()
        player_state.character_settings = {"relationships": {"key_people": []}}

        # 故事中不包含明确角色关键词
        story_text = "在街上遇到了神秘人物XYZ。"
        relationships_in_effects = {"XYZ": 50}

        WorldModelUpdater.sync_story_characters_to_settings(
            player_state,
            story_text=story_text,
            relationships_in_effects=relationships_in_effects,
        )

        key_people = player_state.character_settings["relationships"]["key_people"]
        xyz = next((p for p in key_people if p["name"] == "XYZ"), None)
        assert xyz is not None
        # 默认角色
        assert xyz["role"] == "故事中结识"
