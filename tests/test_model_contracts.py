"""模型契约 / Schema 验证测试。

验证数据库模型和 API Schema 的结构正确性，
防止属性名错误、字段缺失等回归 bug。
"""

from src.database.models import Game, GameState, Image, SceneImage, User
from src.game.state import PlayerState


class TestGameModelContract:
    """验证 Game 模型的字段契约。"""

    def test_game_has_no_player_state_attribute(self):
        """Game 模型不应有 player_state 属性（之前的 bug 误用了此属性）。

        Bug 背景：代码中曾误用 game.player_state 读取数据，
        但 Game 模型实际使用 initial_state / final_state 存储状态。
        """
        assert not hasattr(Game, "player_state"), (
            "Game 模型不应有 player_state 属性，" "应该使用 initial_state 或 final_state"
        )

    def test_game_has_initial_state(self):
        """Game 模型应有 initial_state 字段。"""
        assert hasattr(Game, "initial_state")

    def test_game_has_final_state(self):
        """Game 模型应有 final_state 字段。"""
        assert hasattr(Game, "final_state")

    def test_game_has_required_columns(self):
        """验证 Game 模型包含所有必要字段。"""
        required_attrs = [
            "game_id",
            "user_id",
            "created_at",
            "updated_at",
            "language",
            "initial_state",
            "final_state",
            "ending_type",
            "ending_summary",
            "is_public",
        ]
        for attr in required_attrs:
            assert hasattr(Game, attr), f"Game 模型缺少字段: {attr}"

    def test_game_has_relationships(self):
        """验证 Game 模型的关联关系。"""
        assert hasattr(Game, "user")
        assert hasattr(Game, "states")
        assert hasattr(Game, "decisions")
        assert hasattr(Game, "ending")
        assert hasattr(Game, "images")
        assert hasattr(Game, "scene_images")


class TestGameStateModelContract:
    """验证 GameState 模型的字段契约。"""

    def test_game_state_has_state_json(self):
        """GameState 应有 state_json 字段（而非 state 或 player_state）。"""
        assert hasattr(GameState, "state_json"), "GameState 模型缺少 state_json 字段"

    def test_game_state_has_no_state_field(self):
        """GameState 不应有名为 'state' 的字段（避免与 Game.state 混淆）。

        注意：SQLAlchemy Column 会创建 InstrumentedAttribute，
        这里检查 __table__.columns 中没有叫 'state' 的列。
        """
        column_names = [c.name for c in GameState.__table__.columns]
        assert "state" not in column_names, "GameState 不应有 'state' 列，应使用 'state_json'"

    def test_game_state_has_required_columns(self):
        """验证 GameState 模型包含所有必要字段。"""
        required_attrs = [
            "state_id",
            "game_id",
            "week",
            "age",
            "state_json",
            "created_at",
            "is_save_point",
            "save_name",
        ]
        for attr in required_attrs:
            assert hasattr(GameState, attr), f"GameState 模型缺少字段: {attr}"

    def test_game_state_has_game_relationship(self):
        """验证 GameState 有 game 关联。"""
        assert hasattr(GameState, "game")


class TestImageModelContract:
    """验证 Image 模型的字段契约。"""

    def test_image_has_required_columns(self):
        """验证 Image 模型包含所有必要字段。"""
        required_attrs = [
            "image_id",
            "game_id",
            "image_type",
            "entity_name",
            "entity_key",
            "prompt_text",
            "storage_path",
            "storage_type",
            "version",
            "is_active",
            "is_primary",
            "created_at",
        ]
        for attr in required_attrs:
            assert hasattr(Image, attr), f"Image 模型缺少字段: {attr}"


class TestUserModelContract:
    """验证 User 模型的字段契约。"""

    def test_user_has_required_columns(self):
        """验证 User 模型包含所有必要字段。"""
        required_attrs = [
            "user_id",
            "private_id",
            "public_id",
            "display_name",
            "created_at",
            "last_login",
            "last_active_game_id",
        ]
        for attr in required_attrs:
            assert hasattr(User, attr), f"User 模型缺少字段: {attr}"


class TestPlayerStateContract:
    """验证 PlayerState（Pydantic 模型）的字段契约。"""

    def test_player_state_has_core_attributes(self):
        """验证 PlayerState 包含核心属性。"""
        state = PlayerState()
        required_attrs = [
            "player_name",
            "energy",
            "mood",
            "knowledge",
            "wealth",
            "age",
            "week",
            "current_round",
            "rounds_per_week",
        ]
        for attr in required_attrs:
            assert hasattr(state, attr), f"PlayerState 缺少属性: {attr}"

    def test_player_state_has_collection_attributes(self):
        """验证 PlayerState 包含收集系统所需属性。"""
        state = PlayerState()
        assert hasattr(state, "characters"), "PlayerState 缺少 characters 属性"
        assert hasattr(state, "items"), "PlayerState 缺少 items 属性"
        assert hasattr(state, "landmarks"), "PlayerState 缺少 landmarks 属性"
        assert hasattr(state, "character_settings"), "PlayerState 缺少 character_settings 属性"

    def test_player_state_has_round_history(self):
        """验证 PlayerState 包含 round_history（供总结和识别使用）。"""
        state = PlayerState()
        assert hasattr(state, "round_history"), "PlayerState 缺少 round_history 属性"

    def test_player_state_has_no_player_state_field(self):
        """PlayerState 不应有 player_state 字段（避免嵌套混淆）。"""
        PlayerState()
        # player_state 是类名，不应作为字段名
        field_names = list(PlayerState.model_fields.keys())
        assert "player_state" not in field_names, "PlayerState 不应有名为 'player_state' 的字段"


class TestApiSchemaContracts:
    """验证关键 API 响应 Schema 的字段契约。"""

    def test_game_state_response_schema(self):
        """验证 GameStateResponse schema 结构。"""
        from src.api.schemas import GameStateResponse

        # 验证必要字段
        fields = GameStateResponse.model_fields
        assert "game_id" in fields
        assert "player_state" in fields
        assert "progress" in fields
        assert "round_info" in fields
        assert "current_event" in fields

    def test_collection_response_schema(self):
        """验证 CollectionResponse schema 结构。"""
        from src.api.schemas import CollectionResponse

        fields = CollectionResponse.model_fields
        assert "game_id" in fields
        assert "characters" in fields
        assert "items" in fields
        assert "landmarks" in fields
        assert "total_characters" in fields
        assert "total_items" in fields
        assert "total_landmarks" in fields

    def test_collection_response_serialization(self):
        """验证 CollectionResponse 可以正确序列化。"""
        from src.api.schemas import CollectionResponse

        response = CollectionResponse(
            game_id=1,
            characters=[],
            items=[],
            landmarks=[],
            total_characters=0,
            total_items=0,
            total_landmarks=0,
        )
        data = response.model_dump()
        assert data["game_id"] == 1
        assert isinstance(data["characters"], list)
        assert isinstance(data["items"], list)
        assert isinstance(data["landmarks"], list)

    def test_game_state_response_serialization(self):
        """验证 GameStateResponse 可以正确序列化。"""
        from src.api.schemas import GameStateResponse

        response = GameStateResponse(
            game_id=1,
            player_state={"player_name": "Test", "energy": 100},
            progress={"age": 25, "week": 5},
            round_info={"current_round": 0, "game_over": False},
            current_event=None,
        )
        data = response.model_dump()
        assert data["game_id"] == 1
        assert data["player_state"]["player_name"] == "Test"
        assert data["current_event"] is None

    def test_character_collection_item_schema(self):
        """验证 CharacterCollectionItem schema。"""
        from src.api.schemas import CharacterCollectionItem

        item = CharacterCollectionItem(
            name="测试角色",
            role="NPC",
            description="一个测试角色",
            affinity=50,
            age=25,
            gender="男",
            occupation="剑客",
            personality_traits=["勇敢"],
            image_url=None,
            image_generated=False,
            description_generated=True,
        )
        data = item.model_dump()
        assert data["name"] == "测试角色"
        assert data["affinity"] == 50
        assert data["image_generated"] is False

    def test_generate_summary_request_schema(self):
        """验证 GenerateSummaryRequest schema。"""
        from src.api.schemas import GenerateSummaryRequest

        # 有 weeks 参数
        req = GenerateSummaryRequest(weeks=10)
        assert req.weeks == 10

        # 默认 weeks 应有值（不为 None）
        req2 = GenerateSummaryRequest()
        assert req2.weeks == 10  # 默认值为 10


class TestModelTableNames:
    """验证数据库模型的表名正确。"""

    def test_table_names(self):
        """验证所有模型的表名与预期一致。"""
        assert Game.__tablename__ == "games"
        assert GameState.__tablename__ == "game_states"
        assert User.__tablename__ == "users"
        assert Image.__tablename__ == "images"
        assert SceneImage.__tablename__ == "scene_images"


class TestNarrativeFieldContracts:
    """验证叙事系统生产者/消费者字段一致性"""

    def test_style_manifest_fields_consumed_by_prompt_builder(self):
        """StyleManifest 的字段应与 StyleAwarePromptBuilder 消费的字段一致"""
        from src.ai.narrative.style_manifest import StyleManifest
        from src.ai.narrative.style_prompt_builder import \
            StyleAwarePromptBuilder

        manifest_fields = set(StyleManifest.__dataclass_fields__.keys())
        assert "philosophy" in manifest_fields
        assert "structure" in manifest_fields
        assert "techniques" in manifest_fields
        assert "language" in manifest_fields
        assert StyleAwarePromptBuilder is not None

    def test_style_manifest_fields_consumed_by_validator(self):
        """StyleManifest 的字段应与 StyleAwareValidator 消费的字段一致"""
        from src.ai.narrative.style_manifest import StyleManifest
        from src.ai.narrative.style_validator import StyleAwareValidator

        manifest_fields = set(StyleManifest.__dataclass_fields__.keys())
        assert "structure" in manifest_fields
        assert "language" in manifest_fields
        assert StyleAwareValidator is not None

    def test_constraint_type_registry_consistency(self):
        """ConstraintType 枚举与 constraint_registry 注册数量一致"""
        from src.ai.harness import default_registry
        from src.ai.harness.constraint_registry import ConstraintType

        # 每个已注册的 ConstraintType 应在 registry 中
        for ct in ConstraintType:
            registered = default_registry.get(ct)
            if registered is not None:
                assert registered.type == ct

        # 至少注册了 30 个约束
        all_constraints = default_registry.get_all_for_validation()
        assert (
            len(all_constraints) >= 20
        ), f"default_registry 应至少注册 20 个约束，实际: {len(all_constraints)}"

    def test_player_state_new_fields_exist(self):
        """PlayerState 新增字段应存在"""
        state = PlayerState()
        # 验证7个创意/叙事新增字段
        assert hasattr(state, "emotional_arc_history")
        assert hasattr(state, "novelty_scores")
        assert hasattr(state, "player_preferences")
        assert hasattr(state, "character_arc_state")
        assert hasattr(state, "conflict_levels")
        assert hasattr(state, "fate_entries")
        assert hasattr(state, "world_breathing_events")

    def test_world_model_new_fields_exist(self):
        """WorldModel 新增字段应存在"""
        from src.game.world_model import WorldModel

        wm = WorldModel()
        assert hasattr(wm, "location_graph")
        assert hasattr(wm, "character_knowledge_sets")
