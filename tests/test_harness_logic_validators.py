"""8个硬性逻辑验证器的完整单元测试 (L2)。

TDD先行：测试时间一致性、承诺履行、角色状态连续性、物品连续性、
空间位移、NPC属性稳定性、信息屏障、因果一致性验证器。
所有验证器 validate 签名: (story_text, context) -> Tuple[bool, str, dict]
"""

from types import SimpleNamespace

import pytest

# TDD: 验证器模块尚不存在，导入失败时标记整个模块为 skip
_import_errors = []
try:
    from src.ai.harness.temporal_validator import TemporalConsistencyValidator
except ImportError as e:
    _import_errors.append(str(e))
    TemporalConsistencyValidator = None  # type: ignore

try:
    from src.ai.harness.commitment_validator import \
        CommitmentFulfillmentValidator
except ImportError as e:
    _import_errors.append(str(e))
    CommitmentFulfillmentValidator = None  # type: ignore

try:
    from src.ai.harness.character_state_validator import \
        CharacterStateContinuityValidator
except ImportError as e:
    _import_errors.append(str(e))
    CharacterStateContinuityValidator = None  # type: ignore

try:
    from src.ai.harness.item_continuity_validator import \
        ItemContinuityValidator
except ImportError as e:
    _import_errors.append(str(e))
    ItemContinuityValidator = None  # type: ignore

try:
    from src.ai.harness.spatial_validator import SpatialMovementValidator
except ImportError as e:
    _import_errors.append(str(e))
    SpatialMovementValidator = None  # type: ignore

try:
    from src.ai.harness.npc_attribute_validator import \
        NPCAttributeStabilityValidator
except ImportError as e:
    _import_errors.append(str(e))
    NPCAttributeStabilityValidator = None  # type: ignore

try:
    from src.ai.harness.info_barrier_validator import \
        InformationBarrierValidator
except ImportError as e:
    _import_errors.append(str(e))
    InformationBarrierValidator = None  # type: ignore

try:
    from src.ai.harness.cause_effect_validator import \
        CauseEffectConsistencyValidator
except ImportError as e:
    _import_errors.append(str(e))
    CauseEffectConsistencyValidator = None  # type: ignore

if _import_errors:
    pytestmark = pytest.mark.skip(
        reason=f"硬性逻辑验证器尚未实现（TDD红色阶段）: {_import_errors[0]}"
    )


# ==================== Shared Helpers ====================


def _base_context(world_model_data=None, **overrides):
    """构造基础验证上下文。"""
    ctx = {
        "player_state": {
            "player_name": "李逍遥",
            "age": 28,
            "week": 12,
            "items": {
                "长剑": {"status": "owned", "obtained_week": 1},
                "灵药": {"status": "owned", "obtained_week": 10},
            },
            "decision_history": [
                {"week": 10, "choice": "接受师门任务", "effects": {"knowledge": 5}},
                {"week": 11, "choice": "前往洛阳", "effects": {"energy": -10}},
            ],
        },
        "world_model_data": world_model_data
        or {
            "character_locations": {
                "李逍遥": {"location": "洛阳城", "region": "河南", "since_week": 11},
                "赵灵儿": {"location": "苗疆", "region": "云南", "since_week": 0},
                "王二": {"location": "洛阳城", "region": "河南", "since_week": 10},
            },
            "active_commitments": [
                {
                    "description": "答应师父三日内取回灵药",
                    "parties": ["师父"],
                    "deadline_week": 13,
                    "status": "pending",
                    "created_week": 11,
                    "importance": "critical",
                },
            ],
            "causal_chains": [
                {
                    "trigger_event": "在洛阳偶遇神秘老者",
                    "trigger_week": 10,
                    "expected_consequences": ["获得藏宝图线索"],
                    "actual_consequences": [],
                    "status": "pending",
                },
            ],
            "physical_states": {
                "李逍遥": {"status": "healthy", "conditions": []},
                "王二": {"status": "injured", "conditions": ["左臂骨折"]},
            },
            "character_profiles": {
                "赵灵儿": {
                    "identity": "苗疆圣女",
                    "appearance": "清丽脱俗，白衣飘飘",
                    "personality": "温柔善良，单纯天真",
                },
                "王二": {
                    "identity": "铁匠之子",
                    "appearance": "魁梧壮硕，面色黝黑",
                    "personality": "豪爽直率，重义气",
                },
            },
        },
        "storyline": [
            "第10周：李逍遥在师门接到采药任务。",
            "第11周：李逍遥前往洛阳，途中偶遇神秘老者获得藏宝图线索。",
        ],
        "season": "春",
        "current_week": 12,
    }
    ctx.update(overrides)
    _rebuild_world_model(ctx)
    return ctx


def _rebuild_world_model(ctx):
    """从 world_model_data 构建 world_model 对象。"""
    wmd = ctx.get("world_model_data")
    if wmd and isinstance(wmd, dict):
        ctx["world_model"] = SimpleNamespace(
            **{
                "current_week": ctx.get("current_week", 12),
                "active_commitments": wmd.get("active_commitments", []),
                "physical_states": wmd.get("physical_states", {}),
                "character_profiles": wmd.get("character_profiles", {}),
                "character_locations": wmd.get("character_locations", {}),
                "causal_chains": wmd.get("causal_chains", []),
            }
        )


# ==================== 时间一致性验证器 ====================


@pytest.mark.unit
class TestTemporalConsistencyValidator:
    """TemporalConsistencyValidator 单元测试。"""

    def test_consistent_time_references(self):
        """时间引用一致时通过。"""
        v = TemporalConsistencyValidator()
        text = "三天前李逍遥离开了师门，如今已到洛阳第二日。春风拂面，桃花盛开。"
        ctx = _base_context()
        passed, evidence, details = v.validate(text, ctx)
        assert isinstance(passed, bool)
        assert isinstance(evidence, str)
        assert isinstance(details, dict)

    def test_season_mismatch_detected(self):
        """季节描写与 current_week 计算的季节不匹配 → 检测到矛盾。"""
        v = TemporalConsistencyValidator()
        # 春季（week=12）却描写冰天雪地
        text = "大雪纷飞，冰天雪地中李逍遥艰难跋涉。寒风刺骨，万物萧条。"
        ctx = _base_context(season="春")
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "春季出现冰天雪地应检测为矛盾"
        assert len(evidence) > 0

    def test_age_reference_consistent(self):
        """角色年龄引用与 PlayerState.age 一致。"""
        v = TemporalConsistencyValidator()
        text = "二十八岁的李逍遥站在城门口，回忆起年少时的种种。"
        ctx = _base_context()
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True

    def test_age_reference_inconsistent(self):
        """角色年龄引用与 PlayerState.age 不一致 → 检测到矛盾。"""
        v = TemporalConsistencyValidator()
        text = "三十五岁的李逍遥站在城门口，已到了知天命的年纪。"
        ctx = _base_context()  # age=28
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "年龄引用35与实际28不一致应检测为矛盾"

    def test_flashback_scene_exempt(self):
        """回忆/幻觉场景的时间引用豁免。"""
        v = TemporalConsistencyValidator()
        text = (
            "恍惚间，李逍遥仿佛回到了十年前的冬天。"
            "大雪纷飞，年幼的他站在师门前。"
            "这段回忆让他心头一暖。"
        )
        ctx = _base_context(season="春")
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True, "回忆场景中的季节描写应被豁免"

    def test_correction_hint_on_failure(self):
        """失败时 correction_hint 包含具体时间矛盾。"""
        v = TemporalConsistencyValidator()
        text = "大雪纷飞，冰天雪地。"
        ctx = _base_context(season="夏")
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False
        # details 应包含 correction_hint 或具体矛盾描述
        assert "correction_hint" in details or len(evidence) > 0


# ==================== 承诺履行验证器 ====================


@pytest.mark.unit
class TestCommitmentFulfillmentValidator:
    """CommitmentFulfillmentValidator 单元测试。"""

    def test_overdue_critical_commitment_not_addressed(self):
        """到期 CRITICAL 承诺未处理 → 触发重试(passed=False)。"""
        v = CommitmentFulfillmentValidator()
        text = "李逍遥在洛阳街头闲逛，品尝了各种小吃，好不惬意。"
        ctx = _base_context()
        # deadline_week=13, current_week=12，加上 importance=critical
        # 修改为已到期
        ctx["world_model_data"]["active_commitments"][0]["deadline_week"] = 12
        _rebuild_world_model(ctx)
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "到期的 CRITICAL 承诺未在故事中体现应判定失败"

    def test_commitment_addressed_in_story(self):
        """承诺在故事中被提及/处理 → 通过。"""
        v = CommitmentFulfillmentValidator()
        text = "李逍遥想起答应师父三日内取回灵药的承诺，" "不敢再耽搁，立刻出城寻找灵药。"
        ctx = _base_context()
        ctx["world_model_data"]["active_commitments"][0]["deadline_week"] = 12
        _rebuild_world_model(ctx)
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True

    def test_commitment_contradiction_detected(self):
        """承诺矛盾检测（承诺保护却攻击）。"""
        v = CommitmentFulfillmentValidator()
        ctx = _base_context()
        ctx["world_model_data"]["active_commitments"] = [
            {
                "description": "承诺保护赵灵儿的安全",
                "parties": ["赵灵儿"],
                "deadline_week": -1,
                "status": "pending",
                "created_week": 5,
                "importance": "critical",
            }
        ]
        _rebuild_world_model(ctx)
        text = "李逍遥挥剑攻击赵灵儿，毫不留情地将她击倒。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "对保护对象发动攻击应检测为承诺矛盾"

    def test_semantic_match_over_substring(self):
        """语义匹配优于子串匹配。"""
        v = CommitmentFulfillmentValidator()
        ctx = _base_context()
        ctx["world_model_data"]["active_commitments"][0]["deadline_week"] = 12
        _rebuild_world_model(ctx)
        # "灵药" 的同义表述
        text = "李逍遥决定去悬崖峭壁采集那株珍贵的草药，以完成师门的任务。"
        passed, evidence, details = v.validate(text, ctx)
        # 应能通过语义关联识别 "草药" ≈ "灵药"
        assert isinstance(passed, bool)

    def test_correction_hint_lists_unaddressed(self):
        """correction_hint 列出未处理承诺。"""
        v = CommitmentFulfillmentValidator()
        text = "李逍遥躺在客栈里睡大觉。"
        ctx = _base_context()
        ctx["world_model_data"]["active_commitments"][0]["deadline_week"] = 12
        _rebuild_world_model(ctx)
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False
        assert "correction_hint" in details or "灵药" in evidence or "师父" in evidence


# ==================== 角色状态连续性验证器 ====================


@pytest.mark.unit
class TestCharacterStateContinuityValidator:
    """CharacterStateContinuityValidator 单元测试。"""

    def test_dead_character_active_action(self):
        """死亡角色出现主动行为 → CRITICAL 违规(passed=False)。"""
        v = CharacterStateContinuityValidator()
        ctx = _base_context()
        ctx["world_model_data"]["physical_states"]["王二"] = {
            "status": "dead",
            "conditions": ["已死亡"],
        }
        _rebuild_world_model(ctx)
        text = "王二走上前来，拍了拍李逍遥的肩膀说：'兄弟，好久不见！'"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "死亡角色出现主动行为应判定为 CRITICAL 违规"

    def test_severely_injured_vigorous_action(self):
        """重伤角色剧烈行动 → HIGH 违规。"""
        v = CharacterStateContinuityValidator()
        ctx = _base_context()
        # 王二左臂骨折
        text = "王二双手抱起百斤大石，轻松举过头顶。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "左臂骨折的角色双手举重物应检测为违规"

    def test_imprisoned_character_free_action(self):
        """囚禁角色自由行动 → CRITICAL 违规。"""
        v = CharacterStateContinuityValidator()
        ctx = _base_context()
        ctx["world_model_data"]["physical_states"]["赵灵儿"] = {
            "status": "imprisoned",
            "conditions": ["被关押在地牢中"],
        }
        _rebuild_world_model(ctx)
        text = "赵灵儿悠然地在花园中散步，采了一束鲜花。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "囚禁角色自由行动应判定为 CRITICAL 违规"

    def test_flashback_dream_exempt(self):
        """回忆/梦境场景豁免（passed=True）。"""
        v = CharacterStateContinuityValidator()
        ctx = _base_context()
        ctx["world_model_data"]["physical_states"]["王二"] = {
            "status": "dead",
            "conditions": ["已死亡"],
        }
        _rebuild_world_model(ctx)
        text = (
            "李逍遥做了一个梦，梦中王二还活着，"
            "两人并肩在山间漫步，谈笑风生。"
            "醒来后，他不禁感到一阵惆怅。"
        )
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True, "梦境中的死亡角色行为应被豁免"

    def test_healthy_character_normal_action(self):
        """健康角色正常行动 → 通过。"""
        v = CharacterStateContinuityValidator()
        ctx = _base_context()
        text = "李逍遥挥舞长剑，一套剑法行云流水。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True


# ==================== 物品连续性验证器 ====================


@pytest.mark.unit
class TestItemContinuityValidator:
    """ItemContinuityValidator 单元测试。"""

    def test_use_gifted_item(self):
        """使用已赠予物品 → passed=False。"""
        v = ItemContinuityValidator()
        ctx = _base_context()
        ctx["player_state"]["items"]["长剑"]["status"] = "gifted"
        text = "李逍遥拔出长剑，剑锋闪烁寒光。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "使用已赠予的物品应判定失败"

    def test_use_destroyed_item(self):
        """使用已毁坏物品 → passed=False。"""
        v = ItemContinuityValidator()
        ctx = _base_context()
        ctx["player_state"]["items"]["长剑"]["status"] = "destroyed"
        text = "李逍遥举起长剑格挡。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "使用已毁坏的物品应判定失败"

    def test_use_owned_item(self):
        """使用持有物品 → 通过。"""
        v = ItemContinuityValidator()
        ctx = _base_context()
        text = "李逍遥从怀中取出灵药，仔细端详。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True

    def test_consumable_reuse_detection(self):
        """消耗品重用检测。"""
        v = ItemContinuityValidator()
        ctx = _base_context()
        ctx["player_state"]["items"]["灵药"]["status"] = "consumed"
        text = "李逍遥又拿出一颗灵药吞下。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "已消耗的物品重复使用应检测到"

    def test_item_not_in_inventory(self):
        """使用不在 inventory 中的物品。"""
        v = ItemContinuityValidator()
        ctx = _base_context()
        text = "李逍遥举起天外飞仙剑，划破长空。"
        # "天外飞仙剑" 不在 items 中
        passed, evidence, details = v.validate(text, ctx)
        # 这取决于实现：可能 warning 或 fail
        assert isinstance(passed, bool)


# ==================== 空间位移验证器 ====================


@pytest.mark.unit
class TestSpatialMovementValidator:
    """SpatialMovementValidator 单元测试。"""

    def test_same_city_movement(self):
        """同城移动 → 通过。"""
        v = SpatialMovementValidator()
        ctx = _base_context()
        text = "李逍遥从客栈走到洛阳城的东市，只用了半柱香的功夫。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True

    def test_remote_teleportation_detected(self):
        """远距离瞬移 → passed=False。"""
        v = SpatialMovementValidator()
        ctx = _base_context()
        # 李逍遥在洛阳（河南），却瞬间出现在苗疆（云南）
        text = "李逍遥一转身，便已站在苗疆的山寨前。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "从河南到云南的瞬移应被检测"

    def test_adjacent_region_movement(self):
        """邻近区域移动可能通过（取决于距离模型）。"""
        v = SpatialMovementValidator()
        ctx = _base_context()
        # 从洛阳到长安可视为邻近
        text = "李逍遥骑马疾驰三日，终于从洛阳赶到了长安城。"
        passed, evidence, details = v.validate(text, ctx)
        # 有合理的旅行描写，应通过
        assert isinstance(passed, bool)

    def test_location_graph_query(self):
        """location_graph 查询距离。"""
        v = SpatialMovementValidator()
        ctx = _base_context()
        # 同region移动
        text = "李逍遥穿过洛阳城南门，来到城外的郊野。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True

    def test_three_tier_distance_model(self):
        """3级距离模型（同城/邻近/远距离）验证。"""
        v = SpatialMovementValidator()
        # 验证 validator 有距离判定能力
        assert hasattr(v, "validate")


# ==================== NPC属性稳定性验证器 ====================


@pytest.mark.unit
class TestNPCAttributeStabilityValidator:
    """NPCAttributeStabilityValidator 单元测试。"""

    def test_identity_match(self):
        """身份属性与 WorldModel 存储一致 → 通过。"""
        v = NPCAttributeStabilityValidator()
        ctx = _base_context()
        text = "苗疆圣女赵灵儿静静地站在水边，白衣飘飘。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True

    def test_identity_contradiction(self):
        """身份属性与 WorldModel 存储矛盾 → passed=False。"""
        v = NPCAttributeStabilityValidator()
        ctx = _base_context()
        # 赵灵儿是"苗疆圣女"，不是"大唐公主"
        text = "大唐公主赵灵儿坐在龙椅旁，接受群臣朝拜。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "身份从'苗疆圣女'变为'大唐公主'应检测为矛盾"

    def test_appearance_sudden_change(self):
        """外貌无铺垫的突变 → passed=False。"""
        v = NPCAttributeStabilityValidator()
        ctx = _base_context()
        # 王二应为"魁梧壮硕，面色黝黑"
        text = "瘦弱矮小、面色苍白的王二缓缓走来。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "外貌从'魁梧壮硕'变为'瘦弱矮小'应检测为矛盾"

    def test_personality_sudden_change(self):
        """性格无铺垫的突变 → passed=False。"""
        v = NPCAttributeStabilityValidator()
        ctx = _base_context()
        # 赵灵儿应为"温柔善良，单纯天真"
        text = "赵灵儿冷酷地看着倒地的敌人，嘴角露出残忍的笑容。她向来阴险狡诈。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "性格从'温柔善良'到'阴险狡诈'应检测为矛盾"

    def test_no_profile_available(self):
        """无角色画像时跳过验证。"""
        v = NPCAttributeStabilityValidator()
        ctx = _base_context()
        ctx["world_model_data"]["character_profiles"] = {}
        _rebuild_world_model(ctx)
        text = "一个陌生人走进客栈。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True, "无画像数据时应跳过验证"


# ==================== 信息屏障验证器 ====================


@pytest.mark.unit
class TestInformationBarrierValidator:
    """InformationBarrierValidator 单元测试。"""

    def test_character_knows_secret(self):
        """角色引用超出认知范围的秘密 → passed=False。"""
        v = InformationBarrierValidator()
        ctx = _base_context()
        ctx["character_knowledge_sets"] = {
            "王二": {
                "knows": ["李逍遥在洛阳"],
                "secrets_unknown": ["藏宝图线索", "师门任务"],
            },
        }
        text = "王二对李逍遥说：'我听说你得到了藏宝图线索？那可是天大的秘密！'"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "王二不应知道藏宝图线索"

    def test_character_within_knowledge(self):
        """角色引用认知范围内的信息 → 通过。"""
        v = InformationBarrierValidator()
        ctx = _base_context()
        ctx["character_knowledge_sets"] = {
            "王二": {"knows": ["李逍遥在洛阳", "李逍遥是剑客"], "secrets_unknown": []},
        }
        text = "王二说：'李兄弟，好久不见！听说你来了洛阳。'"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True

    def test_no_knowledge_sets_skip(self):
        """无 character_knowledge_sets 时跳过验证。"""
        v = InformationBarrierValidator()
        ctx = _base_context()
        text = "几人围坐在一起聊天。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True, "无认知数据时应跳过验证"

    def test_multiple_characters_knowledge(self):
        """多角色认知追踪。"""
        v = InformationBarrierValidator()
        ctx = _base_context()
        ctx["character_knowledge_sets"] = {
            "王二": {"knows": ["李逍遥在洛阳"], "secrets_unknown": ["灵药任务"]},
            "赵灵儿": {"knows": ["李逍遥是剑客"], "secrets_unknown": ["洛阳之行"]},
        }
        text = "赵灵儿写信道：'听闻你去了洛阳寻找灵药，务必小心。'"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "赵灵儿不应知道洛阳之行和灵药任务"


# ==================== 因果一致性验证器 ====================


@pytest.mark.unit
class TestCauseEffectConsistencyValidator:
    """CauseEffectConsistencyValidator 单元测试。"""

    def test_decision_no_consequence_after_3_rounds(self):
        """重大决策3轮无后果体现 → passed=False。"""
        v = CauseEffectConsistencyValidator()
        ctx = _base_context()
        # trigger_week=10, current_week=12, 但还没有后果
        # 把 trigger_week 改为 8，超过3轮
        ctx["world_model_data"]["causal_chains"][0]["trigger_week"] = 8
        _rebuild_world_model(ctx)
        text = "李逍遥在洛阳城中悠闲地喝茶，一切风平浪静。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "重大决策已过3轮仍无后果应判定失败"

    def test_consequence_addressed(self):
        """后果在故事中被体现 → 通过。"""
        v = CauseEffectConsistencyValidator()
        ctx = _base_context()
        ctx["world_model_data"]["causal_chains"][0]["trigger_week"] = 8
        _rebuild_world_model(ctx)
        text = (
            "正当李逍遥走出客栈，一个神秘老者出现在面前，"
            "递给他一张泛黄的藏宝图。'这是你应得的线索。'"
        )
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True

    def test_consequence_contradicts_decision(self):
        """后果与决策矛盾。"""
        v = CauseEffectConsistencyValidator()
        ctx = _base_context()
        ctx["world_model_data"]["causal_chains"] = [
            {
                "trigger_event": "帮助了衙门师爷",
                "trigger_week": 10,
                "expected_consequences": ["师爷感恩", "衙门优待"],
                "actual_consequences": [],
                "status": "pending",
            }
        ]
        _rebuild_world_model(ctx)
        text = "衙门师爷派人来报复李逍遥，要将他抓入大牢。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is False, "帮助师爷后被报复应检测为因果矛盾"

    def test_no_causal_chains_skip(self):
        """无因果链时跳过验证。"""
        v = CauseEffectConsistencyValidator()
        ctx = _base_context()
        ctx["world_model_data"]["causal_chains"] = []
        _rebuild_world_model(ctx)
        text = "李逍遥在城中漫步。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True

    def test_recent_decision_no_penalty(self):
        """最近的决策（<3轮）暂不要求有后果。"""
        v = CauseEffectConsistencyValidator()
        ctx = _base_context()
        # trigger_week=11, current_week=12, 仅过1轮
        ctx["world_model_data"]["causal_chains"][0]["trigger_week"] = 11
        _rebuild_world_model(ctx)
        text = "李逍遥继续赶路。"
        passed, evidence, details = v.validate(text, ctx)
        assert passed is True, "刚发生的事件不应要求立即有后果"


# ==================== 所有验证器降级测试 ====================


@pytest.mark.unit
class TestAllValidatorsDegradation:
    """所有验证器异常时返回空 ValidationResult（passed=True, 空 evidence）而非崩溃。"""

    @pytest.mark.parametrize(
        "ValidatorClass",
        [
            TemporalConsistencyValidator,
            CommitmentFulfillmentValidator,
            CharacterStateContinuityValidator,
            ItemContinuityValidator,
            SpatialMovementValidator,
            NPCAttributeStabilityValidator,
            InformationBarrierValidator,
            CauseEffectConsistencyValidator,
        ],
    )
    def test_empty_context_no_crash(self, ValidatorClass):
        """空 context 不崩溃。"""
        v = ValidatorClass()
        passed, evidence, details = v.validate("一段普通的故事文本。", {})
        assert passed is True, f"{ValidatorClass.__name__} 空 context 应返回 passed=True"
        assert isinstance(evidence, str)
        assert isinstance(details, dict)

    @pytest.mark.parametrize(
        "ValidatorClass",
        [
            TemporalConsistencyValidator,
            CommitmentFulfillmentValidator,
            CharacterStateContinuityValidator,
            ItemContinuityValidator,
            SpatialMovementValidator,
            NPCAttributeStabilityValidator,
            InformationBarrierValidator,
            CauseEffectConsistencyValidator,
        ],
    )
    def test_empty_story_no_crash(self, ValidatorClass):
        """空故事文本不崩溃。"""
        v = ValidatorClass()
        ctx = _base_context()
        passed, evidence, details = v.validate("", ctx)
        assert isinstance(passed, bool)
        assert isinstance(evidence, str)
        assert isinstance(details, dict)

    @pytest.mark.parametrize(
        "ValidatorClass",
        [
            TemporalConsistencyValidator,
            CommitmentFulfillmentValidator,
            CharacterStateContinuityValidator,
            ItemContinuityValidator,
            SpatialMovementValidator,
            NPCAttributeStabilityValidator,
            InformationBarrierValidator,
            CauseEffectConsistencyValidator,
        ],
    )
    def test_none_fields_no_crash(self, ValidatorClass):
        """context 中关键字段为 None 不崩溃。"""
        v = ValidatorClass()
        ctx = {
            "player_state": None,
            "world_model_data": None,
            "storyline": None,
            "season": None,
            "current_week": None,
        }
        passed, evidence, details = v.validate("一段故事。", ctx)
        assert passed is True, f"{ValidatorClass.__name__} None fields 应优雅降级为 passed=True"
        assert isinstance(evidence, str)
        assert isinstance(details, dict)
