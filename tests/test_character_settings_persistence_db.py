"""DB 集成测试 - character_settings 持久化完整性

验证真实数据库中 character_settings 的完整保存→读取链路。
模拟真实流程：先用 partial settings 创建 game，再更新补充 auto-generated settings，
最后直接从数据库加载验证所有字段完整存在。

注意：此测试使用 db_session fixture 直接操作和查询内存数据库，
不通过 GameDatabase/StateRepository（它们使用全局 SessionLocal）。
"""

import pytest

from src.database.models import Game, User

pytestmark = pytest.mark.integration


class TestCharacterSettingsPersistence:
    """character_settings 完整持久化测试"""

    def test_partial_settings_create_then_full_update_round_trip(self, db_session):
        """模拟真实流程：partial 创建 → full 更新 → 直接查询验证所有 key 存在"""
        # 创建测试用户
        user = User(
            private_id="CS-TEST-001",
            public_id="CSTEST01",
            display_name="PersistenceTest",
        )
        db_session.add(user)
        db_session.commit()

        # Step 1: 用 partial settings 创建 game（模拟 "world" 步骤）
        partial_settings = {
            "era": {"era_name": "现代", "era_description": "当代社会"},
            "age": {"age": 25, "birth_year": 2000},
            "gender": {"gender": "male"},
            "world": {"world_name": "现代都市", "description": "繁华的大都市"},
        }

        initial_state = {
            "player_name": "李逍遥",
            "life_vision": "成为一代大侠",
            "character_settings": partial_settings,
            "age": 25,
            "week": 0,
        }

        game = Game(
            language="zh",
            initial_state=initial_state,
            user_id=user.user_id,
            constraint_level="expert",
        )
        db_session.add(game)
        db_session.commit()
        game_id = game.game_id

        # Step 2: 模拟 PATCH 更新（补充 auto-generated settings）
        auto_generated = {
            "family": {
                "family_background": "中产家庭",
                "family_members": ["父亲 - 工程师", "母亲 - 教师"],
            },
            "relationships": {
                "relationships_description": "有几个知心朋友",
                "key_people": [
                    {"name": "李明", "relationship": "好友", "personality": "开朗"},
                    {"name": "王芳", "relationship": "同事", "personality": "细心"},
                ],
            },
            "traits": {
                "personality": ["好奇", "有野心", "坚韧"],
                "strengths": ["学习能力强", "善于沟通"],
            },
            "wealth": {
                "initial_wealth": "middle",
                "description": "小康水平",
                "monthly_income": 8000,
            },
        }

        # 直接操作数据库模拟 PATCH 端点的 merge 行为
        game = db_session.query(Game).filter(Game.game_id == game_id).first()
        assert game is not None

        current_state = dict(game.initial_state or {})
        existing_settings = current_state.get("character_settings", {})
        merged_settings = {**existing_settings, **auto_generated}
        current_state["character_settings"] = merged_settings
        game.initial_state = current_state
        db_session.commit()

        # Step 3: 重新从数据库查询验证
        game = db_session.query(Game).filter(Game.game_id == game_id).first()
        assert game is not None

        cs = game.initial_state.get("character_settings", {})
        assert isinstance(cs, dict), "character_settings 应为 dict"

        # 所有手动步骤的 setting key 必须存在
        manual_keys = ["era", "age", "gender", "world"]
        for key in manual_keys:
            assert key in cs, f"character_settings 必须包含手动步骤 {key}"

        # 所有自动生成步骤的 setting key 必须存在
        auto_keys = ["family", "relationships", "traits", "wealth"]
        for key in auto_keys:
            assert key in cs, f"character_settings 必须包含自动生成步骤 {key}"

        # 验证内容完整性
        assert cs["family"]["family_background"] == "中产家庭"
        assert len(cs["family"]["family_members"]) == 2

        assert len(cs["relationships"]["key_people"]) == 2
        assert cs["relationships"]["key_people"][0]["name"] == "李明"

        assert "好奇" in cs["traits"]["personality"]
        assert "学习能力强" in cs["traits"]["strengths"]

        assert cs["wealth"]["initial_wealth"] == "middle"
        assert cs["wealth"]["monthly_income"] == 8000

    def test_key_people_survive_round_trip(self, db_session):
        """relationships.key_people 数组在完整 save→load 链路中必须完整保留"""
        user = User(
            private_id="CS-TEST-002",
            public_id="CSTEST02",
            display_name="KeyPeopleTest",
        )
        db_session.add(user)
        db_session.commit()

        key_people = [
            {"name": "张三", "relationship": "父亲", "affinity": 80},
            {"name": "李四", "relationship": "母亲", "affinity": 85},
            {"name": "王五", "relationship": "好友", "affinity": 70},
        ]

        game = Game(
            language="zh",
            initial_state={
                "player_name": "测试角色",
                "life_vision": "测试愿景",
                "character_settings": {"relationships": {"key_people": key_people}},
                "age": 20,
                "week": 0,
            },
            user_id=user.user_id,
            constraint_level="expert",
        )
        db_session.add(game)
        db_session.commit()
        game_id = game.game_id

        # 模拟更新（添加更多 settings）
        game = db_session.query(Game).filter(Game.game_id == game_id).first()
        current_state = dict(game.initial_state or {})
        cs = current_state.get("character_settings", {})
        cs["era"] = {"era_name": "现代"}
        cs["traits"] = {"personality": ["开朗"]}
        current_state["character_settings"] = cs
        game.initial_state = current_state
        db_session.commit()

        # 从数据库重新查询验证
        game = db_session.query(Game).filter(Game.game_id == game_id).first()
        loaded_cs = game.initial_state["character_settings"]

        assert "relationships" in loaded_cs
        loaded_key_people = loaded_cs["relationships"]["key_people"]
        assert len(loaded_key_people) == 3
        assert loaded_key_people[0]["name"] == "张三"
        assert loaded_key_people[1]["affinity"] == 85

    def test_empty_character_settings_loads_gracefully(self, db_session):
        """空 character_settings 不应导致加载失败"""
        user = User(
            private_id="CS-TEST-003",
            public_id="CSTEST03",
            display_name="EmptyTest",
        )
        db_session.add(user)
        db_session.commit()

        game = Game(
            language="zh",
            initial_state={
                "player_name": "EmptySettings",
                "character_settings": {},
                "age": 20,
                "week": 0,
            },
            user_id=user.user_id,
            constraint_level="expert",
        )
        db_session.add(game)
        db_session.commit()
        game_id = game.game_id

        game = db_session.query(Game).filter(Game.game_id == game_id).first()
        assert game is not None
        assert game.initial_state.get("character_settings") == {}
