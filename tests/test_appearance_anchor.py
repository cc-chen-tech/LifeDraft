"""Tests for AppearanceAnchor - 人物外貌特征锚点测试

测试文本层面的角色一致性机制，确保角色在不同场景下保持视觉一致性。
"""

from src.services.image.appearance_anchor import (
    CharacterAppearanceAnchor,
    merge_anchors,
)


class TestCharacterAppearanceAnchor:
    """人物外貌特征锚点测试"""

    def test_create_basic_anchor(self):
        """测试创建基本锚点"""
        anchor = CharacterAppearanceAnchor(
            name="测试角色",
            face_shape="瓜子脸",
            facial_features="大眼睛、双眼皮、高鼻梁",
            hair_style="黑色中长发",
        )

        assert anchor.name == "测试角色"
        assert anchor.face_shape == "瓜子脸"
        assert anchor.facial_features == "大眼睛、双眼皮、高鼻梁"
        assert anchor.hair_style == "黑色中长发"

    def test_create_full_anchor(self):
        """测试创建完整锚点"""
        anchor = CharacterAppearanceAnchor(
            name="李逍遥",
            era="古代",
            face_shape="瓜子脸",
            facial_features="剑眉星目、英气逼人",
            expression="自信",
            skin_tone="白皙",
            hair_style="黑色长发束起",
            hair_color="乌黑",
            hair_details="发梢微卷，有红色发带",
            body_type="修长",
            height_impression="高挑",
            posture="挺拔",
            distinctive_marks=["眉间一颗痣", "左腕疤痕"],
            typical_outfit="白色长袍配青色腰带",
            clothing_style="古风侠客",
            accessories=["长剑", "玉佩"],
            aura="侠义",
            age_appearance="20岁左右",
            lighting_preference="侧逆光",
            angle_preference="45度侧面",
        )

        assert anchor.name == "李逍遥"
        assert len(anchor.distinctive_marks) == 2
        assert len(anchor.accessories) == 2
        assert anchor.version == 1

    def test_to_dict(self):
        """测试转换为字典"""
        anchor = CharacterAppearanceAnchor(
            name="测试角色",
            face_shape="圆脸",
            hair_style="短发",
        )

        data = anchor.to_dict()

        assert isinstance(data, dict)
        assert data["name"] == "测试角色"
        assert data["face_shape"] == "圆脸"
        assert data["version"] == 1

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "name": "测试角色",
            "face_shape": "鹅蛋脸",
            "facial_features": "柳叶眉",
            "hair_style": "长发",
            "era": "现代",
            "version": 2,
        }

        anchor = CharacterAppearanceAnchor.from_dict(data)

        assert anchor.name == "测试角色"
        assert anchor.face_shape == "鹅蛋脸"
        assert anchor.version == 2

    def test_build_prompt_segment_basic(self):
        """测试构建基本提示词片段"""
        anchor = CharacterAppearanceAnchor(
            name="测试角色",
            face_shape="瓜子脸",
            facial_features="大眼睛",
            hair_style="黑色长发",
            hair_color="乌黑",
        )

        prompt = anchor.build_prompt_segment()

        assert "瓜子脸" in prompt
        assert "大眼睛" in prompt
        assert "乌黑" in prompt
        assert "黑色长发" in prompt

    def test_build_prompt_segment_complete(self):
        """测试构建完整提示词片段"""
        anchor = CharacterAppearanceAnchor(
            name="赵灵儿",
            face_shape="鹅蛋脸",
            facial_features="杏眼、樱桃小嘴",
            expression="温柔",
            skin_tone="白皙",
            hair_style="及腰长发",
            hair_color="黑色",
            hair_details="刘海齐眉",
            height_impression="娇小",
            body_type="纤细",
            typical_outfit="淡绿色襦裙",
            accessories=["玉簪", "手镯"],
            aura="仙气",
        )

        prompt = anchor.build_prompt_segment()

        # 验证面部特征
        assert "鹅蛋脸" in prompt
        assert "杏眼" in prompt
        assert "温柔" in prompt

        # 验证发型
        assert "黑色" in prompt
        assert "及腰长发" in prompt

        # 验证服装
        assert "淡绿色襦裙" in prompt

        # 验证配饰
        assert "玉簪" in prompt
        assert "手镯" in prompt

        # 验证气质
        assert "仙气" in prompt

    def test_build_prompt_segment_empty_fields(self):
        """测试空字段处理"""
        anchor = CharacterAppearanceAnchor(
            name="测试角色",
            face_shape="",
            hair_style="短发",
        )

        prompt = anchor.build_prompt_segment()

        # 空字段不应出现在提示词中
        assert "脸型" not in prompt
        assert "短发" in prompt

    def test_build_scene_prompt(self):
        """测试构建场景生成提示词"""
        anchor = CharacterAppearanceAnchor(
            name="测试角色",
            face_shape="瓜子脸",
            facial_features="大眼睛",
            hair_style="黑色长发",
            typical_outfit="白色连衣裙",
            expression="微笑",
        )

        prompt = anchor.build_scene_prompt(
            scene_context="在公园散步",
            pose_hint="手插口袋",
        )

        assert "测试角色" in prompt
        assert "瓜子脸" in prompt
        assert "在公园散步" in prompt
        assert "手插口袋" in prompt
        assert "白色连衣裙" in prompt

    def test_build_scene_prompt_with_outfit_override(self):
        """测试场景提示词服装覆盖"""
        anchor = CharacterAppearanceAnchor(
            name="测试角色",
            face_shape="圆脸",
            hair_style="短发",
            typical_outfit="日常T恤",
        )

        prompt = anchor.build_scene_prompt(
            scene_context="参加晚宴",
            outfit_override="晚礼服",
        )

        # 应包含覆盖后的服装（作为场景穿着）
        assert "晚礼服" in prompt
        # 典型服装仍保留在整体外貌描述中，场景穿着单独列出
        assert "日常T恤" in prompt

    def test_validate_complete(self):
        """测试验证完整锚点"""
        anchor = CharacterAppearanceAnchor(
            name="测试角色",
            face_shape="瓜子脸",
            facial_features="大眼睛",
            facial_signature="两眼间距约为一眼宽度，鼻梁中等高度",
            hair_style="长发",
            body_type="匀称",
        )

        missing = anchor.validate()

        assert len(missing) == 0

    def test_validate_incomplete(self):
        """测试验证不完整锚点"""
        anchor = CharacterAppearanceAnchor(
            name="测试角色",
            face_shape="",
            facial_features="",
            facial_signature="",
            hair_style="",
            body_type="",
        )

        missing = anchor.validate()

        assert len(missing) == 5
        assert "脸型" in missing
        assert "五官特征" in missing
        assert "面部比例签名" in missing
        assert "发型" in missing
        assert "体型" in missing

    def test_validate_partial(self):
        """测试验证部分完整锚点"""
        anchor = CharacterAppearanceAnchor(
            name="测试角色",
            face_shape="瓜子脸",
            facial_features="",
            facial_signature="",
            hair_style="长发",
            body_type="",
        )

        missing = anchor.validate()

        assert len(missing) == 3
        assert "五官特征" in missing
        assert "面部比例签名" in missing
        assert "体型" in missing


class TestMergeAnchors:
    """锚点合并测试"""

    def test_merge_basic(self):
        """测试基本合并"""
        base = CharacterAppearanceAnchor(
            name="测试角色",
            face_shape="瓜子脸",
            facial_features="大眼睛",
            hair_style="长发",
            version=1,
        )

        override = {"face_shape": "圆脸", "expression": "开心"}

        merged = merge_anchors(base, override)

        assert merged.face_shape == "圆脸"  # 被覆盖
        assert merged.facial_features == "大眼睛"  # 保留原值
        assert merged.expression == "开心"  # 新增
        assert merged.version == 2  # 版本递增

    def test_merge_preserves_unmodified(self):
        """测试合并保留未修改字段"""
        base = CharacterAppearanceAnchor(
            name="测试角色",
            face_shape="瓜子脸",
            facial_features="大眼睛",
            hair_style="黑色长发",
            hair_color="乌黑",
            typical_outfit="白T恤",
        )

        override = {"typical_outfit": "黑T恤"}

        merged = merge_anchors(base, override)

        # 验证未修改字段保留
        assert merged.name == "测试角色"
        assert merged.face_shape == "瓜子脸"
        assert merged.facial_features == "大眼睛"
        assert merged.hair_style == "黑色长发"
        assert merged.hair_color == "乌黑"

        # 验证修改字段更新
        assert merged.typical_outfit == "黑T恤"

    def test_merge_list_fields(self):
        """测试合并列表字段"""
        base = CharacterAppearanceAnchor(
            name="测试角色",
            distinctive_marks=["痣1", "痣2"],
            accessories=["手表"],
        )

        override = {"distinctive_marks": ["新痣"], "accessories": ["眼镜", "项链"]}

        merged = merge_anchors(base, override)

        # 列表应完全替换
        assert merged.distinctive_marks == ["新痣"]
        assert merged.accessories == ["眼镜", "项链"]

    def test_merge_version_increment(self):
        """测试版本号递增"""
        base = CharacterAppearanceAnchor(
            name="测试角色",
            face_shape="瓜子脸",
            version=5,
        )

        merged = merge_anchors(base, {})

        assert merged.version == 6


class TestAnchorEdgeCases:
    """锚点边界情况测试"""

    def test_empty_anchor(self):
        """测试空锚点"""
        anchor = CharacterAppearanceAnchor(name="测试角色")

        assert anchor.name == "测试角色"
        assert anchor.face_shape == ""
        assert anchor.version == 1

        prompt = anchor.build_prompt_segment()
        assert prompt == ""

    def test_special_characters_in_fields(self):
        """测试特殊字符处理"""
        anchor = CharacterAppearanceAnchor(
            name="角色·特殊",
            face_shape="瓜子脸（略带婴儿肥）",
            facial_features="大眼睛、双眼皮",
            hair_style="黑色长发，微卷",
        )

        prompt = anchor.build_prompt_segment()

        assert "瓜子脸（略带婴儿肥）" in prompt
        assert "黑色长发，微卷" in prompt

    def test_long_description(self):
        """测试长描述"""
        long_desc = "这是一段非常长的描述" * 20

        anchor = CharacterAppearanceAnchor(
            name="测试角色",
            face_shape="瓜子脸",
            facial_features=long_desc,
        )

        prompt = anchor.build_prompt_segment()

        assert long_desc in prompt

    def test_unicode_support(self):
        """测试Unicode支持"""
        anchor = CharacterAppearanceAnchor(
            name="🎭角色",
            face_shape="瓜子脸",
            expression="😊",
            typical_outfit="👘和服",
        )

        prompt = anchor.build_prompt_segment()

        # build_prompt_segment 不包含 name 字段
        # 验证表情和服装的 Unicode 支持
        assert "😊" in prompt or "开心" in prompt
        assert "👘" in prompt or "和服" in prompt
