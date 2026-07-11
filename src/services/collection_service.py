"""收集系统服务层。

负责人物、物品、标志物收集的业务逻辑。
从 collection.py 路由层提取，实现关注点分离。
"""

import base64
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

from sqlalchemy.orm import Session

from src.api.schemas import (CharacterCollectionItem, CollectionResponse,
                             ItemCollectionItem, LandmarkCollectionItem)
from src.ai.image_exceptions import ImageProviderError
from src.database.models import Game
from src.database.models import Image as ImageModel
from src.game.state import CharacterState, PlayerState
from src.game.state.item_state import ItemState
from src.game.state.landmark_state import LandmarkState
from src.services.image_service import (ImageProviderServiceError,
                                        ImageService)
from src.services.image_storage import ImageStorageService

logger = logging.getLogger(__name__)


class CollectionError(Exception):
    """收集系统业务逻辑异常基类"""


class EntityNotFoundError(CollectionError):
    """实体不存在"""


class PermissionDeniedError(CollectionError):
    """权限不足"""


class ImageGenerationError(CollectionError):
    """图片生成失败"""


@dataclass
class CharacterInfo:
    """人物信息结构"""

    name: str
    description: str
    is_player: bool
    era: str


class CollectionService:
    """收集系统服务类。

    处理人物、物品、标志物的收集和管理业务逻辑。
    """

    def __init__(self, db: Session):
        """
        Args:
            db: SQLAlchemy 数据库会话
        """
        self.db = db
        self.image_service = ImageService(db)
        self.storage_service = ImageStorageService()

    def verify_game_ownership(self, game_id: int, user_id: int) -> Game:
        """验证游戏归属权。

        Args:
            game_id: 游戏ID
            user_id: 用户ID

        Returns:
            Game 对象

        Raises:
            EntityNotFoundError: 游戏不存在或无权访问
        """
        game = self.db.query(Game).filter(Game.game_id == game_id).first()
        if not game:
            raise EntityNotFoundError("游戏不存在或无权访问")
        if game.user_id is not None and game.user_id != user_id:
            raise EntityNotFoundError("游戏不存在或无权访问")
        return game

    # ==================== 获取收集数据 ====================

    def get_collection(
        self,
        game_id: int,
        player_state: PlayerState,
    ) -> CollectionResponse:
        """获取游戏的收集数据。

        Args:
            game_id: 游戏ID
            player_state: 玩家状态

        Returns:
            CollectionResponse 包含人物、物品、标志物列表
        """
        characters = self._build_character_list(game_id, player_state)
        items = self._build_item_list(game_id, player_state)
        landmarks = self._build_landmark_list(game_id, player_state)

        return CollectionResponse(
            game_id=game_id,
            characters=characters,
            items=items,
            landmarks=landmarks,
            total_characters=len(characters),
            total_items=len(items),
            total_landmarks=len(landmarks),
        )

    def _build_character_list(
        self,
        game_id: int,
        player_state: PlayerState,
    ) -> List[CharacterCollectionItem]:
        """构建人物列表。"""
        characters = []
        added_names: set[str] = set()
        character_settings = player_state.character_settings or {}

        # 批量获取所有 character 图片，避免 N+1 查询
        image_cache = self._get_entity_images_batch(game_id, "character")

        # 0. 添加主角
        player_char = self._build_player_character(
            game_id, player_state, character_settings, added_names, image_cache
        )
        if player_char:
            characters.append(player_char)

        # 1. 从 player_state.characters 获取 NPC 角色
        for name, char_data in player_state.characters.items():
            if name in added_names:
                continue
            added_names.add(name)
            image_url, image_generated = image_cache.get(name, (None, False))
            characters.append(
                CharacterCollectionItem(
                    name=name,
                    role=char_data.get("role", ""),
                    description=char_data.get("relationship_desc", "")
                    or char_data.get("relationship", ""),
                    affinity=char_data.get("affinity", 50),
                    age=char_data.get("age"),
                    gender=char_data.get("gender"),
                    occupation=char_data.get("occupation"),
                    personality_traits=char_data.get("personality_traits", []),
                    image_url=image_url,
                    image_generated=image_generated,
                    description_generated=True,
                )
            )

        # 2. 从 key_people 获取关键人物
        key_people = self._extract_key_people(character_settings.get("relationships", {}))
        for person in key_people:
            if isinstance(person, dict):
                char = self._build_key_person(game_id, person, added_names, image_cache)
                if char:
                    characters.append(char)

        # 3. 从 family_members 获取家庭成员
        family_members = character_settings.get("family", {}).get("family_members", [])
        for member in family_members:
            if isinstance(member, dict):
                char = self._build_family_member(game_id, member, added_names, image_cache)
                if char:
                    characters.append(char)

        return characters

    def _extract_key_people(self, relationships: Any) -> List[Dict[str, Any]]:
        """Return key people from both canonical and legacy relationship payloads."""
        if isinstance(relationships, list):
            return [person for person in relationships if isinstance(person, dict)]
        if isinstance(relationships, dict):
            key_people = relationships.get("key_people", [])
            return [person for person in key_people if isinstance(person, dict)]
        return []

    def _build_player_character(
        self,
        game_id: int,
        player_state: PlayerState,
        character_settings: Dict[str, Any],
        added_names: set,
        image_cache: Optional[Dict[str, Tuple[Optional[str], bool]]] = None,
    ) -> Optional[CharacterCollectionItem]:
        """构建主角信息。"""
        player_name = player_state.player_name or character_settings.get("player_name", "")
        if not player_name:
            return None

        added_names.add(player_name)
        if image_cache is not None:
            image_url, image_generated = image_cache.get(player_name, (None, False))
        else:
            image_url, image_generated = self._get_entity_image(game_id, "character", player_name)

        # 处理可能的嵌套字典
        age_val = self._extract_nested_value(character_settings.get("age"), "age")
        gender_val = self._extract_nested_value(character_settings.get("gender"), "gender")
        occupation_val = self._extract_nested_value(
            character_settings.get("occupation"), "occupation"
        )

        # 构建主角描述
        player_desc_parts = []
        if age_val:
            player_desc_parts.append(f"{age_val}岁")
        if gender_val:
            player_desc_parts.append(str(gender_val))
        if occupation_val:
            player_desc_parts.append(occupation_val)
        player_desc = "，".join(player_desc_parts) if player_desc_parts else "主角"

        return CharacterCollectionItem(
            name=player_name,
            role="主角",
            description=player_desc,
            affinity=100,
            age=age_val,
            gender=gender_val,
            occupation=occupation_val,
            personality_traits=character_settings.get("personality_traits", []),
            image_url=image_url,
            image_generated=image_generated,
            description_generated=True,
        )

    def _build_key_person(
        self,
        game_id: int,
        person: Dict[str, Any],
        added_names: set,
        image_cache: Optional[Dict[str, Tuple[Optional[str], bool]]] = None,
    ) -> Optional[CharacterCollectionItem]:
        """构建关键人物信息。"""
        name = person.get("name", "")
        if not name or name in added_names:
            return None
        added_names.add(name)

        if image_cache is not None:
            image_url, image_generated = image_cache.get(name, (None, False))
        else:
            image_url, image_generated = self._get_entity_image(game_id, "character", name)

        return CharacterCollectionItem(
            name=name,
            role=person.get("role", ""),
            description=person.get("relationship_desc", "") or person.get("relationship", ""),
            affinity=person.get("affinity", 50),
            age=person.get("age"),
            gender=person.get("gender"),
            occupation=None,
            personality_traits=(
                [person.get("personality", "")] if person.get("personality") else []
            ),
            image_url=image_url,
            image_generated=image_generated,
            description_generated=True,
        )

    def _build_family_member(
        self,
        game_id: int,
        member: Dict[str, Any],
        added_names: set,
        image_cache: Optional[Dict[str, Tuple[Optional[str], bool]]] = None,
    ) -> Optional[CharacterCollectionItem]:
        """构建家庭成员信息。"""
        name = member.get("name", "")
        if not name or name in added_names:
            return None
        added_names.add(name)

        if image_cache is not None:
            image_url, image_generated = image_cache.get(name, (None, False))
        else:
            image_url, image_generated = self._get_entity_image(game_id, "character", name)

        return CharacterCollectionItem(
            name=name,
            role=member.get("role", "家庭成员"),
            description=member.get("relationship", ""),
            affinity=80,
            age=member.get("age"),
            gender=member.get("gender"),
            occupation=None,
            personality_traits=[],
            image_url=image_url,
            image_generated=image_generated,
            description_generated=True,
        )

    def _build_item_list(
        self,
        game_id: int,
        player_state: PlayerState,
    ) -> List[ItemCollectionItem]:
        """构建物品列表。"""
        items = []
        # 批量获取所有 item 图片，避免 N+1 查询
        image_cache = self._get_entity_images_batch(game_id, "item")
        for name, item_data in player_state.items.items():
            image_url, image_generated = image_cache.get(name, (None, False))
            items.append(
                ItemCollectionItem(
                    name=name,
                    description=item_data.get("description", ""),
                    importance=item_data.get("importance", "normal"),
                    category=item_data.get("category", "other"),
                    acquired_week=item_data.get("acquired_week", 0),
                    acquired_context=item_data.get("acquired_context", ""),
                    is_key_item=item_data.get("is_key_item", False),
                    image_url=image_url,
                    image_generated=image_generated,
                    description_generated=item_data.get("description_generated", False),
                    metadata=item_data.get("metadata", {}),
                )
            )
        return items

    def _build_landmark_list(
        self,
        game_id: int,
        player_state: PlayerState,
    ) -> List[LandmarkCollectionItem]:
        """构建标志物列表。"""
        landmarks = []
        # 批量获取所有 landmark 图片，避免 N+1 查询
        image_cache = self._get_entity_images_batch(game_id, "landmark")
        for name, landmark_data in player_state.landmarks.items():
            image_url, image_generated = image_cache.get(name, (None, False))
            landmarks.append(
                LandmarkCollectionItem(
                    name=name,
                    description=landmark_data.get("description", ""),
                    category=landmark_data.get("category", "other"),
                    importance=landmark_data.get("importance", "normal"),
                    first_appear_week=landmark_data.get("first_appear_week", 0),
                    appear_count=landmark_data.get("appear_count", 1),
                    last_appear_week=landmark_data.get("last_appear_week", 0),
                    context=landmark_data.get("context", ""),
                    is_key_location=landmark_data.get("is_key_location", False),
                    image_url=image_url,
                    image_generated=image_generated,
                    metadata=landmark_data.get("metadata", {}),
                )
            )
        return landmarks

    def _get_entity_images_batch(
        self,
        game_id: int,
        image_type: str,
    ) -> Dict[str, Tuple[Optional[str], bool]]:
        """批量获取某类型所有实体的图片信息。

        一次性查询 game_id + image_type 下所有 is_active=True 的图片，
        避免在循环中逐个查询导致 N+1 问题。

        Args:
            game_id: 游戏ID
            image_type: 图片类型 (character/item/landmark)

        Returns:
            Dict[entity_name, (image_url, image_generated)]
        """
        images = (
            self.db.query(ImageModel)
            .filter(
                ImageModel.game_id == game_id,
                ImageModel.image_type == image_type,
                ImageModel.is_active.is_(True),
            )
            .order_by(ImageModel.created_at.desc())
            .all()
        )

        result: Dict[str, Tuple[Optional[str], bool]] = {}
        for img in images:
            entity_name = str(img.entity_name)
            # 只保留每个实体最新的一张（已按 created_at desc 排序）
            if entity_name not in result:
                result[entity_name] = (self.image_service.get_image_url(img), True)
        return result

    def _get_entity_image(
        self,
        game_id: int,
        image_type: str,
        entity_name: str,
    ) -> Tuple[Optional[str], bool]:
        """获取实体图片信息。

        保留此方法以兼容其他调用点。

        Returns:
            (image_url, image_generated) 元组
        """
        images = (
            self.db.query(ImageModel)
            .filter(
                ImageModel.game_id == game_id,
                ImageModel.image_type == image_type,
                ImageModel.entity_name == entity_name,
                ImageModel.is_active.is_(True),
            )
            .order_by(ImageModel.created_at.desc())
            .all()
        )
        if images:
            return self.image_service.get_image_url(images[0]), True
        return None, False

    def _extract_nested_value(self, value: Any, key: str) -> Any:
        """提取可能嵌套在字典中的值。"""
        if isinstance(value, dict):
            return value.get(key)
        return value

    def _get_era_from_settings(self, character_settings: Dict[str, Any]) -> str:
        """从角色设定中获取时代背景。"""
        era_setting = character_settings.get("era", {})
        if isinstance(era_setting, dict):
            return era_setting.get("era_name") or era_setting.get("era_description") or "现代"
        return "现代"

    # ==================== 生成图片 ====================

    def get_character_info_for_image(
        self,
        name: str,
        player_state: PlayerState,
    ) -> CharacterInfo:
        """获取用于生成图片的人物信息。"""
        character_settings = player_state.character_settings or {}
        description_parts = []

        # 检查是否是主角
        player_name = player_state.player_name or character_settings.get("player_name", "")
        is_player = name == player_name

        if is_player:
            # 主角信息
            age_val = self._extract_nested_value(character_settings.get("age"), "age")
            gender_val = self._extract_nested_value(character_settings.get("gender"), "gender")
            occupation_val = self._extract_nested_value(
                character_settings.get("occupation"), "occupation"
            )

            if age_val:
                description_parts.append(f"{age_val}岁")
            if gender_val:
                description_parts.append(str(gender_val))
            if occupation_val:
                description_parts.append(occupation_val)

            life_vision = character_settings.get("life_vision")
            if life_vision and isinstance(life_vision, str):
                description_parts.append(life_vision[:50])
        else:
            # 从 key_people 中查找
            key_people = character_settings.get("relationships", {}).get("key_people", [])
            for person in key_people:
                if isinstance(person, dict) and person.get("name") == name:
                    if person.get("age"):
                        description_parts.append(f"{person['age']}岁")
                    if person.get("gender"):
                        description_parts.append(str(person["gender"]))
                    if person.get("relationship"):
                        description_parts.append(person["relationship"])
                    break

            # 从 family_members 中查找
            if not description_parts:
                family_members = character_settings.get("family", {}).get("family_members", [])
                for member in family_members:
                    if isinstance(member, dict) and member.get("name") == name:
                        if member.get("age"):
                            description_parts.append(f"{member['age']}岁")
                        if member.get("gender"):
                            description_parts.append(str(member["gender"]))
                        if member.get("relationship"):
                            description_parts.append(member["relationship"])
                        break

        description = "，".join(description_parts) if description_parts else f"一个叫{name}的人"
        era = self._get_era_from_settings(character_settings)

        return CharacterInfo(
            name=name,
            description=description,
            is_player=is_player,
            era=era,
        )

    def generate_character_image(
        self,
        game_id: int,
        name: str,
        player_state: PlayerState,
    ) -> Optional[int]:
        """生成人物图片。

        Returns:
            生成的图片ID
        """
        char_info = self.get_character_info_for_image(name, player_state)

        image_models = self.image_service.generate_character_image(
            game_id=game_id,
            name=name,
            description=char_info.description,
            era=char_info.era,
            entity_key=f"npc_{name}",
            num_images=1,
        )

        return int(image_models[0].image_id) if image_models else None  # type: ignore[return-value]

    def generate_item_image(
        self,
        game_id: int,
        item_name: str,
        player_state: PlayerState,
    ) -> int:
        """生成物品图片。

        Returns:
            生成的图片ID
        """
        item_data = player_state.items.get(item_name)
        if not item_data:
            raise EntityNotFoundError(f"物品 {item_name} 不存在")

        description = item_data.get("description", "") or f"一个叫{item_name}的物品"
        character_settings = player_state.character_settings or {}
        era = self._get_era_from_settings(character_settings)

        image_model = self.image_service.generate_item_image(
            game_id=game_id,
            name=item_name,
            description=description,
            era=era,
        )

        player_state.update_item(item_name, image_generated=True)
        return int(image_model.image_id)

    def generate_landmark_image(
        self,
        game_id: int,
        landmark_name: str,
        player_state: PlayerState,
    ) -> int:
        """生成标志物图片。

        Returns:
            生成的图片ID
        """
        landmark_data = player_state.landmarks.get(landmark_name)
        if not landmark_data:
            raise EntityNotFoundError(f"标志物 {landmark_name} 不存在")

        description = landmark_data.get("description", "") or f"一个叫{landmark_name}的地点"
        character_settings = player_state.character_settings or {}
        era = self._get_era_from_settings(character_settings)

        image_model = self.image_service.generate_location_image(
            game_id=game_id,
            name=landmark_name,
            description=description,
            era=era,
        )

        player_state.update_landmark(landmark_name, image_generated=True)
        return int(image_model.image_id)

    # ==================== 重新生成图片 ====================

    def validate_character_for_regenerate(
        self,
        name: str,
        player_state: PlayerState,
    ) -> None:
        """验证人物是否可以重新生成图片。

        Raises:
            EntityNotFoundError: 人物不存在
            PermissionDeniedError: 亲密度不足
        """
        character_settings = player_state.character_settings or {}
        player_name = player_state.player_name or character_settings.get("player_name", "")
        is_player = name == player_name

        if is_player:
            return  # 主角始终可以修改

        # 在 characters 中查找
        char_data = player_state.characters.get(name)
        if char_data:
            affinity = char_data.get("affinity", 50)
            if affinity < 50:
                raise PermissionDeniedError("亲密度不足50，无法修改画像")
            return

        # 在 key_people 中查找
        key_people = character_settings.get("relationships", {}).get("key_people", [])
        for person in key_people:
            if isinstance(person, dict) and person.get("name") == name:
                return  # key_people 中的人物没有亲密度限制

        # 在 family_members 中查找
        family_members = character_settings.get("family", {}).get("family_members", [])
        for member in family_members:
            if isinstance(member, dict) and member.get("name") == name:
                return  # family_members 中的人物没有亲密度限制

        raise EntityNotFoundError(f"人物 {name} 不存在")

    def regenerate_character_image(
        self,
        game_id: int,
        name: str,
        feedback: str,
        image_id: Optional[int] = None,
    ) -> Optional[int]:
        """重新生成人物图片。

        Returns:
            新生成的图片ID
        """
        if image_id:
            current_image = (
                self.db.query(ImageModel)
                .filter(
                    ImageModel.image_id == image_id,
                    ImageModel.game_id == game_id,
                    ImageModel.image_type == "character",
                )
                .first()
            )
            if not current_image:
                raise EntityNotFoundError("指定图片不存在")
        else:
            current_image = (
                self.db.query(ImageModel)
                .filter(
                    ImageModel.game_id == game_id,
                    ImageModel.image_type == "character",
                    ImageModel.entity_name == name,
                    ImageModel.is_active.is_(True),
                )
                .order_by(ImageModel.created_at.desc())
                .first()
            )

        if not current_image:
            raise EntityNotFoundError(f"人物 {name} 暂无图片，请先生成图片")

        image_models = self.image_service.regenerate_image(
            image_id=int(current_image.image_id),
            feedback=feedback,
        )

        return int(image_models[0].image_id) if image_models else None  # type: ignore[return-value]

    def regenerate_item_image(
        self,
        game_id: int,
        item_name: str,
        feedback: str,
        player_state: PlayerState,
    ) -> int:
        """重新生成物品图片。

        Returns:
            新生成的图片ID
        """
        item_data = player_state.items.get(item_name)
        if not item_data:
            raise EntityNotFoundError(f"物品 {item_name} 不存在")

        current_image = (
            self.db.query(ImageModel)
            .filter(
                ImageModel.game_id == game_id,
                ImageModel.image_type == "item",
                ImageModel.entity_name == item_name,
                ImageModel.is_active.is_(True),
            )
            .order_by(ImageModel.created_at.desc())
            .first()
        )

        if not current_image:
            raise EntityNotFoundError(f"物品 {item_name} 暂无图片，请先生成图片")

        # 获取参考图片数据
        reference_url = self._get_image_reference_url(current_image)
        if not reference_url:
            raise EntityNotFoundError("无法获取当前物品图片")

        description = item_data.get("description", "") or f"一个叫{item_name}的物品"

        from src.ai.image_client import ImageClient

        image_client = ImageClient()

        edit_prompt = f"""基于参考图片，重新绘制物品：
{description}
用户修改意见：{feedback}
保持物品的基本特征，根据修改意见调整外观。"""

        try:
            results = image_client.edit_image(
                reference_image=reference_url,
                prompt=edit_prompt,
                size="1024*1024",
                num_images=1,
            )
        except ImageProviderError as error:
            raise ImageProviderServiceError.from_provider(error) from error

        if not results:
            raise ImageGenerationError("图片生成失败")

        image_data, prompt = results[0]

        # 保存新图片
        storage_path, storage_type = self.storage_service.save_image(
            image_data=image_data,
            game_id=game_id,
            image_type="item",
            entity_name=item_name,
        )

        # 停用旧图片
        self.db.query(ImageModel).filter(
            ImageModel.game_id == game_id,
            ImageModel.image_type == "item",
            ImageModel.entity_name == item_name,
        ).update({"is_active": False})

        # 创建新图片记录
        new_image = ImageModel(
            game_id=game_id,
            image_type="item",
            entity_name=item_name,
            entity_key=f"item_{item_name}",
            prompt_text=prompt,
            storage_path=storage_path,
            storage_type=storage_type,
            is_active=True,
        )
        self.db.add(new_image)
        self.db.commit()
        self.db.refresh(new_image)

        return int(new_image.image_id)

    def _get_image_reference_url(self, image: ImageModel) -> Optional[str]:
        """获取图片的 base64 data URL。"""
        try:
            image_data = self.storage_service.get_image_data(
                str(image.storage_path), str(image.storage_type)
            )
            ext = image.storage_path.rsplit(".", 1)[-1].lower()
            mime_type = "image/png" if ext == "png" else "image/jpeg"
            base64_data = base64.b64encode(image_data).decode("utf-8")
            return f"data:{mime_type};base64,{base64_data}"
        except (OSError, IOError) as e:
            logger.warning(f"IO error getting image: {e}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error getting image: {e}")
            return None

    # ==================== 实体管理 ====================

    def add_entities(
        self,
        player_state: PlayerState,
        items: List[Dict[str, Any]],
        landmarks: List[Dict[str, Any]],
        characters: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, List[str]]:
        """批量添加实体到收集系统。

        Returns:
            {"added_items": [...], "added_characters": [...], "added_landmarks": [...]}
        """
        added_items = []
        added_characters = []
        added_landmarks = []

        character_settings = player_state.character_settings or {}
        player_name = player_state.player_name or character_settings.get("player_name", "")

        # 添加人物
        for character_data in characters or []:
            character_name = character_data.get("name")
            if (
                character_name
                and character_name != player_name
                and character_name not in player_state.characters
            ):
                character = CharacterState(
                    name=character_name,
                    role=character_data.get("role", "故事人物"),
                    relationship_desc=character_data.get("description", ""),
                    affinity=character_data.get("affinity", 50),
                )
                player_state.add_character(character)
                added_characters.append(character_name)
                logger.info(f"Added character from recognition: {character_name}")

        # 添加物品
        for item_data in items:
            item_name = item_data.get("name")
            if item_name and item_name not in player_state.items:
                item = ItemState(
                    name=item_name,
                    description=item_data.get("description", ""),
                    importance=item_data.get("importance", "normal"),
                    category=item_data.get("category", "other"),
                    acquired_week=player_state.week,
                    acquired_context=(
                        item_data.get("appear_contexts", [""])[0]
                        if item_data.get("appear_contexts")
                        else ""
                    ),
                    is_key_item=(item_data.get("importance") == "critical"),
                    image_generated=False,
                    description_generated=True,
                )
                player_state.add_item(item)
                added_items.append(item_name)
                logger.info(f"Added item from recognition: {item_name}")

        # 添加地点
        for landmark_data in landmarks:
            landmark_name = landmark_data.get("name")
            if landmark_name and landmark_name not in player_state.landmarks:
                landmark = LandmarkState(
                    name=landmark_name,
                    description=landmark_data.get("description", ""),
                    category=landmark_data.get("category", "other"),
                    importance=landmark_data.get("importance", "normal"),
                    first_appear_week=player_state.week,
                    appear_count=landmark_data.get("appear_count", 1),
                    last_appear_week=player_state.week,
                    context=(
                        landmark_data.get("appear_contexts", [""])[0]
                        if landmark_data.get("appear_contexts")
                        else ""
                    ),
                    is_key_location=(landmark_data.get("importance") == "critical"),
                    image_generated=False,
                )
                player_state.add_landmark(landmark)
                added_landmarks.append(landmark_name)
                logger.info(f"Added landmark from recognition: {landmark_name}")

        return {
            "added_items": added_items,
            "added_characters": added_characters,
            "added_landmarks": added_landmarks,
        }

    def create_item(
        self,
        player_state: PlayerState,
        item_name: str,
        ai_client=None,
        language: str = "zh",
        generate_description: bool = False,
    ) -> Dict[str, Any]:
        """手动创建物品。

        Returns:
            创建的物品信息
        """
        item_name = item_name.strip()
        if not item_name:
            raise ValueError("物品名称不能为空")

        if item_name in player_state.items:
            raise ValueError(f"物品 '{item_name}' 已存在")

        description = ""
        category = "other"
        importance = "normal"
        acquired_context = ""

        # 如果需要从历史中提取描述
        if generate_description and player_state.round_history and ai_client:
            from src.services.entity_recognition_service import \
                EntityRecognitionService

            recognition_service = EntityRecognitionService(ai_client)
            item_info = recognition_service.extract_item_description(
                item_name=item_name,
                round_history=player_state.round_history,
                language=language,
            )
            if item_info:
                description = item_info.get("description", "")
                category = item_info.get("category", "other")
                importance = item_info.get("importance", "normal")
                acquired_context = item_info.get("acquired_context", "")[:200]

        # 创建物品
        item = ItemState(
            name=item_name,
            description=description,
            importance=importance,
            category=category,
            acquired_week=player_state.week,
            acquired_context=acquired_context,
            is_key_item=(importance == "critical"),
            image_generated=False,
            description_generated=bool(description),
        )
        player_state.add_item(item)

        return {
            "name": item_name,
            "description": description,
            "importance": importance,
            "category": category,
            "acquired_week": player_state.week,
            "acquired_context": acquired_context,
            "is_key_item": (importance == "critical"),
            "image_generated": False,
            "description_generated": bool(description),
        }

    def delete_item(
        self,
        game_id: int,
        item_name: str,
        player_state: PlayerState,
    ) -> bool:
        """删除物品。"""
        item_name = unquote(item_name)
        if item_name not in player_state.items:
            raise EntityNotFoundError(f"物品 '{item_name}' 不存在")

        success = player_state.remove_item(item_name)
        if not success:
            return False

        # 删除关联的图片记录
        self.db.query(ImageModel).filter(
            ImageModel.game_id == game_id,
            ImageModel.image_type == "item",
            ImageModel.entity_name == item_name,
        ).delete()
        self.db.commit()

        return True

    def delete_character(
        self,
        game_id: int,
        character_name: str,
        player_state: PlayerState,
    ) -> bool:
        """删除人物。"""
        character_name = unquote(character_name)

        # 检查是否是主角
        character_settings = player_state.character_settings or {}
        player_name = player_state.player_name or character_settings.get("player_name", "")
        if character_name == player_name:
            raise PermissionDeniedError("不能删除主角")

        if character_name not in player_state.characters:
            raise EntityNotFoundError(f"人物 '{character_name}' 不存在或无法删除")

        success = player_state.remove_character(character_name)
        if not success:
            return False

        # 删除关联的图片记录
        self.db.query(ImageModel).filter(
            ImageModel.game_id == game_id,
            ImageModel.image_type == "character",
            ImageModel.entity_name == character_name,
        ).delete()
        self.db.commit()

        return True

    def delete_landmark(
        self,
        game_id: int,
        landmark_name: str,
        player_state: PlayerState,
    ) -> bool:
        """删除标志物。"""
        landmark_name = unquote(landmark_name)
        if landmark_name not in player_state.landmarks:
            raise EntityNotFoundError(f"地点 '{landmark_name}' 不存在")

        success = player_state.remove_landmark(landmark_name)
        if not success:
            return False

        # 删除关联的图片记录
        self.db.query(ImageModel).filter(
            ImageModel.game_id == game_id,
            ImageModel.image_type == "landmark",
            ImageModel.entity_name == landmark_name,
        ).delete()
        self.db.commit()

        return True
