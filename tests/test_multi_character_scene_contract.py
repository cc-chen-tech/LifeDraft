"""Multi-character scene generation contract tests.

验证场景生成时正确提取故事中的所有角色并注入提示词。
"""


class TestMultiCharacterSceneContract:
    """测试多角色场景生成功能"""

    def test_scene_prompt_template_has_character_manifest_placeholder(self):
        """SCENE_PROMPT_TEMPLATE 必须包含 {character_manifest} 占位符"""
        from src.services.image.scene_service import SceneImageService

        template = SceneImageService.SCENE_PROMPT_TEMPLATE
        assert (
            "{character_manifest}" in template
        ), "SCENE_PROMPT_TEMPLATE 必须包含 {character_manifest} 占位符"

    def test_scene_prompt_requires_all_characters_visible(self):
        """场景提示词模板必须明确要求所有角色同时出现且可见"""
        from src.services.image.scene_service import SceneImageService

        template = SceneImageService.SCENE_PROMPT_TEMPLATE
        assert (
            "以下所有人物必须在场景中同时出现" in template
        ), "模板必须包含'以下所有人物必须在场景中同时出现'"
        assert (
            "每一个人物都必须在画面中清晰可见" in template
        ), "模板必须包含'每一个人物都必须在画面中清晰可见'"
        assert "不得遗漏任何一人" in template, "模板必须包含'不得遗漏任何一人'"

    def test_scene_prompt_requires_differentiation(self):
        """场景提示词模板必须要求多人物有明显不同特征"""
        from src.services.image.scene_service import SceneImageService

        template = SceneImageService.SCENE_PROMPT_TEMPLATE
        assert (
            "同性别同年龄段的人物必须有至少3处明显不同的外貌特征" in template
        ), "模板必须包含同性别同年龄段人物的区分要求"
        assert (
            "不同脸型、不同五官、不同发型、不同肤色、不同身高体型" in template
        ), "模板必须包含具体的区分维度"

    def test_extract_story_characters_finds_player(self):
        """_extract_story_characters 必须始终包含玩家角色"""
        from src.services.image.scene_service import SceneImageService

        svc = SceneImageService.__new__(SceneImageService)
        character_settings = {
            "age": {"age": 28},
            "gender": {"gender": "男"},
            "appearance": {"face": "圆脸", "hair": "短发"},
        }
        story_text = "李逍遥走在街上。"

        chars = svc._extract_story_characters(story_text, character_settings, "李逍遥")
        names = [c["name"] for c in chars]
        assert "李逍遥" in names, f"玩家角色必须在列表中，实际得到: {names}"

    def test_extract_story_characters_finds_key_people_in_story(self):
        """_extract_story_characters 必须找到故事中提到的关键人物"""
        from src.services.image.scene_service import SceneImageService

        svc = SceneImageService.__new__(SceneImageService)
        character_settings = {
            "relationships": {
                "key_people": [
                    {
                        "name": "林小鹿",
                        "relationship": "同事",
                        "age": 26,
                        "gender": "女",
                    },
                    {
                        "name": "赵敏敏",
                        "relationship": "朋友",
                        "age": 25,
                        "gender": "女",
                    },
                ]
            }
        }
        story_text = "李逍遥和林小鹿在咖啡厅聊天。"

        chars = svc._extract_story_characters(story_text, character_settings, "李逍遥")
        names = [c["name"] for c in chars]
        assert "林小鹿" in names, f"故事中提到的关键人物必须在列表中，实际得到: {names}"
        assert (
            "赵敏敏" not in names
        ), f"故事中未提到的关键人物不应在列表中，实际得到: {names}"

    def test_extract_story_characters_finds_family_members_in_story(self):
        """_extract_story_characters 必须找到故事中提到的家庭成员"""
        from src.services.image.scene_service import SceneImageService

        svc = SceneImageService.__new__(SceneImageService)
        character_settings = {
            "family": {
                "family_members": [
                    {"name": "李父", "relationship": "父亲", "age": 55},
                ]
            }
        }
        story_text = "李逍遥和父亲李父一起吃饭。"

        chars = svc._extract_story_characters(story_text, character_settings, "李逍遥")
        names = [c["name"] for c in chars]
        assert "李父" in names, f"故事中提到的家庭成员必须在列表中，实际得到: {names}"

    def test_extract_story_characters_dedupes_family_and_relationships(self):
        """_extract_story_characters 必须去重 family 和 relationships 中的同名人物"""
        from src.services.image.scene_service import SceneImageService

        svc = SceneImageService.__new__(SceneImageService)
        character_settings = {
            "relationships": {
                "key_people": [
                    {"name": "王叔", "relationship": "叔叔"},
                ]
            },
            "family": {
                "family_members": [
                    {"name": "王叔", "relationship": "叔叔"},
                ]
            },
        }
        story_text = "李逍遥和王叔一起钓鱼。"

        chars = svc._extract_story_characters(story_text, character_settings, "李逍遥")
        names = [c["name"] for c in chars]
        assert (
            names.count("王叔") == 1
        ), f"同名人物应只出现一次，实际出现 {names.count('王叔')} 次: {names}"

    def test_build_character_manifest_includes_position_hints(self):
        """_build_character_manifest 必须为每个人物分配画面位置"""
        from src.services.image.scene_service import SceneImageService

        svc = SceneImageService.__new__(SceneImageService)
        characters = [
            {"name": "李逍遥", "description": "28岁男性"},
            {"name": "林小鹿", "description": "26岁女性"},
        ]
        manifest = svc._build_character_manifest(characters, player_name="李逍遥")

        assert (
            "画面左侧" in manifest or "画面中央" in manifest or "画面右侧" in manifest
        ), f"人物清单必须包含画面位置提示，实际: {manifest}"

    def test_build_character_manifest_requires_distinct_faces(self):
        """多人物时 _build_character_manifest 必须包含面部区分要求"""
        from src.services.image.scene_service import SceneImageService

        svc = SceneImageService.__new__(SceneImageService)
        characters = [
            {"name": "李逍遥", "description": "28岁男性"},
            {"name": "林小鹿", "description": "26岁女性"},
        ]
        manifest = svc._build_character_manifest(characters, player_name="李逍遥")

        assert (
            "明显不同的面部特征" in manifest
        ), f"多人物清单必须包含面部区分要求，实际: {manifest}"
        assert (
            "禁止任何两个人物看起来像同一张脸" in manifest
        ), f"多人物清单必须禁止撞脸，实际: {manifest}"

    def test_build_character_manifest_single_character_no_differentiation(self):
        """单人物时 _build_character_manifest 不应包含区分要求"""
        from src.services.image.scene_service import SceneImageService

        svc = SceneImageService.__new__(SceneImageService)
        characters = [
            {"name": "李逍遥", "description": "28岁男性"},
        ]
        manifest = svc._build_character_manifest(characters, player_name="李逍遥")

        assert (
            "禁止任何两个人物看起来像同一张脸" not in manifest
        ), f"单人物清单不应包含撞脸禁令，实际: {manifest}"

    def test_get_character_position_hint_two_people(self):
        """两个人物的位置提示应分配左右"""
        from src.services.image.scene_service import SceneImageService

        assert SceneImageService._get_character_position_hint(0, 2) == "画面左侧"
        assert SceneImageService._get_character_position_hint(1, 2) == "画面右侧"

    def test_get_character_position_hint_three_people(self):
        """三个人物的位置提示应分配左中右"""
        from src.services.image.scene_service import SceneImageService

        assert SceneImageService._get_character_position_hint(0, 3) == "画面左侧"
        assert SceneImageService._get_character_position_hint(1, 3) == "画面中央"
        assert SceneImageService._get_character_position_hint(2, 3) == "画面右侧"

    def test_build_character_manifest_with_appearance_anchor(self):
        """玩家角色有外貌锚点时，清单必须包含锚点描述"""
        from src.services.image.appearance_anchor import \
            CharacterAppearanceAnchor
        from src.services.image.scene_service import SceneImageService

        svc = SceneImageService.__new__(SceneImageService)
        anchor = CharacterAppearanceAnchor(
            name="李逍遥",
            face_shape="瓜子脸",
            facial_features="双眼皮、高鼻梁",
            distinctive_marks=["左眉有一颗痣"],
        )
        characters = [
            {"name": "李逍遥", "description": "28岁男性"},
        ]
        manifest = svc._build_character_manifest(
            characters, appearance_anchor=anchor, player_name="李逍遥"
        )

        assert "外貌锚点" in manifest, f"清单必须包含外貌锚点，实际: {manifest}"
        assert "瓜子脸" in manifest, f"清单必须包含锚点中的脸型，实际: {manifest}"
        assert (
            "左眉有一颗痣" in manifest
        ), f"清单必须包含锚点中的标志性特征，实际: {manifest}"
