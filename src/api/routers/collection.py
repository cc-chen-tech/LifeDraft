"""收集系统API路由 - 人物和物品收集"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_optional
from src.api.schemas import (
    CharacterCollectionItem,
    CollectionResponse,
    ItemCollectionItem,
    LandmarkCollectionItem,
    MessageResponse,
    RegenerateCharacterImageRequest,
    RegenerateItemImageRequest,
)
from src.api.services.session_service import session_service
from src.database.models import Game
from src.database.models import Image as ImageModel
from src.database.models import SessionLocal, User
from src.services.image_service import (
    ImageContentError,
    ImageService,
    ImageServiceError,
)
from src.services.item_extraction_service import ItemExtractionService
from src.services.landmark_extraction_service import LandmarkExtractionService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_session() -> Session:
    """Get a SQLAlchemy session for collection operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_game_ownership(db: Session, game_id: int, user_id: int) -> Game:
    """验证游戏归属权"""
    game = db.query(Game).filter(Game.game_id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在或无权访问")
    if game.user_id is not None and game.user_id != user_id:
        raise HTTPException(status_code=404, detail="游戏不存在或无权访问")
    return game


@router.get("/{game_id}", response_model=CollectionResponse)
async def get_collection(
    game_id: int,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """获取游戏的收集数据（人物和物品）"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    session = session_service.get_or_restore(game_id, user)
    player_state = session.game_loop.get_state()

    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")

    db = SessionLocal()

    try:
        image_service = ImageService(db)

        # ========== 构建人物列表 ==========
        characters = []
        added_names = set()
        character_settings = player_state.character_settings or {}

        # 0. 添加主角（放在最前面）
        player_name = player_state.player_name or character_settings.get(
            "player_name", ""
        )
        if player_name:
            added_names.add(player_name)

            # 获取主角图片
            player_images = (
                db.query(ImageModel)
                .filter(
                    ImageModel.game_id == game_id,
                    ImageModel.image_type == "character",
                    ImageModel.entity_name == player_name,
                    ImageModel.is_active.is_(True),
                )
                .order_by(ImageModel.created_at.desc())
                .all()
            )

            player_image_url = (
                image_service.get_image_url(player_images[0]) if player_images else None
            )

            # 构建主角描述 - 处理可能的嵌套字典
            age_val = character_settings.get("age")
            gender_val = character_settings.get("gender")
            occupation_val = character_settings.get("occupation")

            # 提取嵌套字典中的值
            if isinstance(age_val, dict):
                age_val = age_val.get("age")
            if isinstance(gender_val, dict):
                gender_val = gender_val.get("gender")
            if isinstance(occupation_val, dict):
                occupation_val = occupation_val.get("occupation")

            player_desc_parts = []
            if age_val:
                player_desc_parts.append(f"{age_val}岁")
            if gender_val:
                player_desc_parts.append(str(gender_val))
            if occupation_val:
                player_desc_parts.append(occupation_val)
            player_desc = "，".join(player_desc_parts) if player_desc_parts else "主角"

            characters.append(
                CharacterCollectionItem(
                    name=player_name,
                    role="主角",
                    description=player_desc,
                    affinity=100,
                    age=age_val,
                    gender=gender_val,
                    occupation=occupation_val,
                    personality_traits=character_settings.get("personality_traits", []),
                    image_url=player_image_url,
                    image_generated=bool(player_images),
                    description_generated=True,
                )
            )

        # 1. 从 player_state.characters 获取 NPC 角色
        for name, char_data in player_state.characters.items():
            if name in added_names:
                continue
            added_names.add(name)

            images = (
                db.query(ImageModel)
                .filter(
                    ImageModel.game_id == game_id,
                    ImageModel.image_type == "character",
                    ImageModel.entity_name == name,
                    ImageModel.is_active.is_(True),
                )
                .order_by(ImageModel.created_at.desc())
                .all()
            )

            image_url = image_service.get_image_url(images[0]) if images else None

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
                    image_generated=bool(images),
                    description_generated=True,
                )
            )

        # 2. 从 character_settings.relationships.key_people 获取关键人物
        key_people = character_settings.get("relationships", {}).get("key_people", [])

        for person in key_people:
            if isinstance(person, dict):
                name = person.get("name", "")
                if not name or name in added_names:
                    continue
                added_names.add(name)

                images = (
                    db.query(ImageModel)
                    .filter(
                        ImageModel.game_id == game_id,
                        ImageModel.image_type == "character",
                        ImageModel.entity_name == name,
                        ImageModel.is_active.is_(True),
                    )
                    .order_by(ImageModel.created_at.desc())
                    .all()
                )

                image_url = image_service.get_image_url(images[0]) if images else None

                characters.append(
                    CharacterCollectionItem(
                        name=name,
                        role=person.get("role", ""),
                        description=person.get("relationship_desc", "")
                        or person.get("relationship", ""),
                        affinity=person.get("affinity", 50),
                        age=person.get("age"),
                        gender=person.get("gender"),
                        occupation=None,
                        personality_traits=(
                            [person.get("personality", "")]
                            if person.get("personality")
                            else []
                        ),
                        image_url=image_url,
                        image_generated=bool(images),
                        description_generated=True,
                    )
                )

        # 3. 从 character_settings.family.family_members 获取家庭成员
        family_members = character_settings.get("family", {}).get("family_members", [])

        for member in family_members:
            if isinstance(member, dict):
                name = member.get("name", "")
                if not name or name in added_names:
                    continue
                added_names.add(name)

                images = (
                    db.query(ImageModel)
                    .filter(
                        ImageModel.game_id == game_id,
                        ImageModel.image_type == "character",
                        ImageModel.entity_name == name,
                        ImageModel.is_active.is_(True),
                    )
                    .order_by(ImageModel.created_at.desc())
                    .all()
                )

                image_url = image_service.get_image_url(images[0]) if images else None

                characters.append(
                    CharacterCollectionItem(
                        name=name,
                        role=member.get("role", "家庭成员"),
                        description=member.get("relationship", ""),
                        affinity=80,
                        age=member.get("age"),
                        gender=member.get("gender"),
                        occupation=None,
                        personality_traits=[],
                        image_url=image_url,
                        image_generated=bool(images),
                        description_generated=True,
                    )
                )

        # ========== 构建物品列表 ==========
        items = []

        for name, item_data in player_state.items.items():
            images = (
                db.query(ImageModel)
                .filter(
                    ImageModel.game_id == game_id,
                    ImageModel.image_type == "item",
                    ImageModel.entity_name == name,
                    ImageModel.is_active.is_(True),
                )
                .order_by(ImageModel.created_at.desc())
                .all()
            )

            image_url = image_service.get_image_url(images[0]) if images else None

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
                    image_generated=bool(images),
                    description_generated=item_data.get("description_generated", False),
                    metadata=item_data.get("metadata", {}),
                )
            )

        # ========== 构建标志物列表 ==========
        landmarks = []

        for name, landmark_data in player_state.landmarks.items():
            images = (
                db.query(ImageModel)
                .filter(
                    ImageModel.game_id == game_id,
                    ImageModel.image_type == "landmark",
                    ImageModel.entity_name == name,
                    ImageModel.is_active.is_(True),
                )
                .order_by(ImageModel.created_at.desc())
                .all()
            )

            image_url = image_service.get_image_url(images[0]) if images else None

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
                    image_generated=bool(images),
                    metadata=landmark_data.get("metadata", {}),
                )
            )

        return CollectionResponse(
            game_id=game_id,
            characters=characters,
            items=items,
            landmarks=landmarks,
            total_characters=len(characters),
            total_items=len(items),
            total_landmarks=len(landmarks),
        )

    finally:
        db.close()


@router.get("/{game_id}/details", response_model=CollectionResponse)
async def get_collection_details(
    game_id: int,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """获取游戏的收集数据（人物和物品）- 与 /{game_id} 相同，为兼容前端路径"""
    # 复用 get_collection 逻辑
    return await get_collection(game_id, user)


@router.post(
    "/{game_id}/characters/{name}/generate-image", response_model=MessageResponse
)
async def generate_character_image(
    game_id: int,
    name: str,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """生成人物图片"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    session = session_service.get_or_restore(game_id, user)
    player_state = session.game_loop.get_state()

    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")

    # 构建描述
    character_settings = player_state.character_settings or {}
    description_parts = []

    # 检查是否是主角
    player_name = player_state.player_name or character_settings.get("player_name", "")
    is_player = name == player_name

    if is_player:
        # 主角信息从 character_settings 获取
        age_val = character_settings.get("age")
        gender_val = character_settings.get("gender")
        occupation_val = character_settings.get("occupation")

        # 处理可能的字典类型（age 可能是 {'age': 19, 'birth_year': ...}）
        if isinstance(age_val, dict):
            age_val = age_val.get("age")
        if isinstance(gender_val, dict):
            gender_val = gender_val.get("gender")
        if isinstance(occupation_val, dict):
            occupation_val = occupation_val.get("occupation")

        if age_val:
            description_parts.append(f"{age_val}岁")
        if gender_val:
            description_parts.append(str(gender_val))
        if occupation_val:
            description_parts.append(occupation_val)
        # 添加更多描述
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
            family_members = character_settings.get("family", {}).get(
                "family_members", []
            )
            for member in family_members:
                if isinstance(member, dict) and member.get("name") == name:
                    if member.get("age"):
                        description_parts.append(f"{member['age']}岁")
                    if member.get("gender"):
                        description_parts.append(str(member["gender"]))
                    if member.get("relationship"):
                        description_parts.append(member["relationship"])
                    break

    description = (
        "，".join(description_parts) if description_parts else f"一个叫{name}的人"
    )

    # 获取时代背景
    era = "现代"
    era_setting = character_settings.get("era", {})
    if isinstance(era_setting, dict):
        era = (
            era_setting.get("era_name") or era_setting.get("era_description") or "现代"
        )

    db = SessionLocal()
    try:
        verify_game_ownership(db, game_id, user)

        image_service = ImageService(db)
        image_models = image_service.generate_character_image(
            game_id=game_id,
            name=name,
            description=description,
            era=era,
            entity_key=f"npc_{name}",
            num_images=1,
        )

        return MessageResponse(
            message=f"人物 {name} 图片生成成功",
            success=True,
            data={"image_id": image_models[0].image_id if image_models else None},
        )

    except ImageContentError as e:
        logger.warning(f"Content inspection failed: {e}")
        raise HTTPException(
            status_code=400, detail="生成图片时触发了内容安全审核，请稍后重试"
        )
    except ImageServiceError as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post(
    "/{game_id}/characters/{name}/generate-description", response_model=MessageResponse
)
async def generate_character_description(
    game_id: int,
    name: str,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """生成人物描述（人物描述已存在于角色设定中）"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    return MessageResponse(message=f"人物 {name} 描述已存在", success=True)


@router.post(
    "/{game_id}/items/{item_name}/generate-image", response_model=MessageResponse
)
async def generate_item_image(
    game_id: int,
    item_name: str,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """生成物品图片"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    session = session_service.get_or_restore(game_id, user)
    player_state = session.game_loop.get_state()

    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")

    item_data = player_state.items.get(item_name)

    if not item_data:
        raise HTTPException(status_code=404, detail=f"物品 {item_name} 不存在")

    description = item_data.get("description", "") or f"一个叫{item_name}的物品"

    era = "现代"
    character_settings = player_state.character_settings or {}
    era_setting = character_settings.get("era", {})
    if isinstance(era_setting, dict):
        era = (
            era_setting.get("era_name") or era_setting.get("era_description") or "现代"
        )

    db = SessionLocal()
    try:
        verify_game_ownership(db, game_id, user)

        image_service = ImageService(db)
        image_model = image_service.generate_item_image(
            game_id=game_id,
            name=item_name,
            description=description,
            era=era,
        )

        player_state.update_item(item_name, image_generated=True)

        return MessageResponse(
            message=f"物品 {item_name} 图片生成成功",
            success=True,
            data={"image_id": image_model.image_id},
        )

    except ImageContentError as e:
        logger.warning(f"Content inspection failed: {e}")
        raise HTTPException(
            status_code=400, detail="生成图片时触发了内容安全审核，请稍后重试"
        )
    except ImageServiceError as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post(
    "/{game_id}/items/{item_name}/generate-description", response_model=MessageResponse
)
async def generate_item_description(
    game_id: int,
    item_name: str,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """生成物品描述"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    session = session_service.get_or_restore(game_id, user)
    player_state = session.game_loop.get_state()

    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")

    item_data = player_state.items.get(item_name)

    if not item_data:
        raise HTTPException(status_code=404, detail=f"物品 {item_name} 不存在")

    if item_data.get("description") and len(item_data.get("description", "")) > 50:
        return MessageResponse(message=f"物品 {item_name} 描述已存在", success=True)

    story_context = item_data.get("acquired_context", "")

    try:
        item_service = ItemExtractionService(session.game_loop.ai_generator.ai_client)

        new_description = item_service.generate_item_description(
            item_name=item_name,
            item_category=item_data.get("category", "other"),
            acquired_context=story_context,
            story_context=story_context,
            language=session.language,
        )

        if new_description:
            player_state.update_item(
                item_name, description=new_description, description_generated=True
            )

            return MessageResponse(
                message=f"物品 {item_name} 描述生成成功",
                success=True,
                data={"description": new_description},
            )
        else:
            raise HTTPException(status_code=500, detail="描述生成失败")

    except Exception as e:
        logger.error(f"Failed to generate item description: {e}")
        raise HTTPException(status_code=500, detail=f"描述生成失败: {e}")


# ==================== 标志物端点 ====================


@router.post(
    "/{game_id}/landmarks/{landmark_name}/generate-image",
    response_model=MessageResponse,
)
async def generate_landmark_image(
    game_id: int,
    landmark_name: str,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """生成标志物图片"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    session = session_service.get_or_restore(game_id, user)
    player_state = session.game_loop.get_state()

    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")

    landmark_data = player_state.landmarks.get(landmark_name)

    if not landmark_data:
        raise HTTPException(status_code=404, detail=f"标志物 {landmark_name} 不存在")

    description = landmark_data.get("description", "") or f"一个叫{landmark_name}的地点"

    era = "现代"
    character_settings = player_state.character_settings or {}
    era_setting = character_settings.get("era", {})
    if isinstance(era_setting, dict):
        era = (
            era_setting.get("era_name") or era_setting.get("era_description") or "现代"
        )

    db = SessionLocal()
    try:
        verify_game_ownership(db, game_id, user)

        image_service = ImageService(db)

        # 使用 generate_location_image 方法生成地点图片
        image_model = image_service.generate_location_image(
            game_id=game_id,
            name=landmark_name,
            description=description,
            era=era,
        )

        player_state.update_landmark(landmark_name, image_generated=True)

        return MessageResponse(
            message=f"标志物 {landmark_name} 图片生成成功",
            success=True,
            data={"image_id": image_model.image_id},
        )

    except ImageContentError as e:
        logger.warning(f"Content inspection failed: {e}")
        raise HTTPException(
            status_code=400, detail="生成图片时触发了内容安全审核，请稍后重试"
        )
    except ImageServiceError as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post(
    "/{game_id}/landmarks/{landmark_name}/generate-description",
    response_model=MessageResponse,
)
async def generate_landmark_description(
    game_id: int,
    landmark_name: str,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """生成标志物描述"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    session = session_service.get_or_restore(game_id, user)
    player_state = session.game_loop.get_state()

    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")

    landmark_data = player_state.landmarks.get(landmark_name)

    if not landmark_data:
        raise HTTPException(status_code=404, detail=f"标志物 {landmark_name} 不存在")

    if (
        landmark_data.get("description")
        and len(landmark_data.get("description", "")) > 50
    ):
        return MessageResponse(
            message=f"标志物 {landmark_name} 描述已存在", success=True
        )

    context = landmark_data.get("context", "")

    try:
        landmark_service = LandmarkExtractionService(
            session.game_loop.ai_generator.ai_client
        )

        new_description = landmark_service.generate_landmark_description(
            landmark_name=landmark_name,
            landmark_category=landmark_data.get("category", "other"),
            context=context,
            story_context=context,
            language=session.language,
        )

        if new_description:
            player_state.update_landmark(landmark_name, description=new_description)

            return MessageResponse(
                message=f"标志物 {landmark_name} 描述生成成功",
                success=True,
                data={"description": new_description},
            )
        else:
            raise HTTPException(status_code=500, detail="描述生成失败")

    except Exception as e:
        logger.error(f"Failed to generate landmark description: {e}")
        raise HTTPException(status_code=500, detail=f"描述生成失败: {e}")


@router.post(
    "/{game_id}/characters/{name}/regenerate-image", response_model=MessageResponse
)
async def regenerate_character_image(
    game_id: int,
    name: str,
    request: RegenerateCharacterImageRequest,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """基于用户文字描述重新生成人物画像"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    session = session_service.get_or_restore(game_id, user)
    player_state = session.game_loop.get_state()

    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")

    # 检查是否是主角
    character_settings = player_state.character_settings or {}
    player_name = player_state.player_name or character_settings.get("player_name", "")
    is_player = name == player_name

    # 验证人物存在性和亲密度
    # 人物可能存在于多个位置：player_state.characters, key_people, family_members
    if not is_player:
        # 1. 先在 player_state.characters 中查找
        char_data = player_state.characters.get(name)

        if char_data:
            # 存在于 characters 中，检查亲密度
            affinity = char_data.get("affinity", 50)
            if affinity < 50:
                raise HTTPException(
                    status_code=403, detail="亲密度不足50，无法修改画像"
                )
        else:
            # 2. 在 key_people 中查找
            key_people = character_settings.get("relationships", {}).get(
                "key_people", []
            )
            found_in_key_people = False
            for person in key_people:
                if isinstance(person, dict) and person.get("name") == name:
                    found_in_key_people = True
                    # key_people 中的人物没有亲密度限制
                    break

            if not found_in_key_people:
                # 3. 在 family_members 中查找
                family_members = character_settings.get("family", {}).get(
                    "family_members", []
                )
                found_in_family = False
                for member in family_members:
                    if isinstance(member, dict) and member.get("name") == name:
                        found_in_family = True
                        # family_members 中的人物没有亲密度限制
                        break

                if not found_in_family:
                    raise HTTPException(status_code=404, detail=f"人物 {name} 不存在")

    db = SessionLocal()
    try:
        verify_game_ownership(db, game_id, user)

        # 获取当前活跃图片或指定图片
        if request.image_id:
            current_image = (
                db.query(ImageModel)
                .filter(
                    ImageModel.image_id == request.image_id,
                    ImageModel.game_id == game_id,
                    ImageModel.image_type == "character",
                )
                .first()
            )
            if not current_image:
                raise HTTPException(status_code=404, detail="指定图片不存在")
        else:
            current_image = (
                db.query(ImageModel)
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
            raise HTTPException(
                status_code=404, detail=f"人物 {name} 暂无图片，请先生成图片"
            )

        image_service = ImageService(db)
        image_models = image_service.regenerate_image(
            image_id=current_image.image_id,
            feedback=request.feedback,
        )

        return MessageResponse(
            message=f"人物 {name} 画像修改成功",
            success=True,
            data={"image_id": image_models[0].image_id if image_models else None},
        )

    except ImageContentError as e:
        logger.warning(f"Content inspection failed: {e}")
        raise HTTPException(
            status_code=400, detail="生成图片时触发了内容安全审核，请稍后重试"
        )
    except ImageServiceError as e:
        logger.error(f"Image regeneration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post(
    "/{game_id}/items/{item_name}/regenerate-image", response_model=MessageResponse
)
async def regenerate_item_image(
    game_id: int,
    item_name: str,
    request: RegenerateItemImageRequest,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """基于用户文字描述重新生成物品图片"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    session = session_service.get_or_restore(game_id, user)
    player_state = session.game_loop.get_state()

    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")

    item_data = player_state.items.get(item_name)
    if not item_data:
        raise HTTPException(status_code=404, detail=f"物品 {item_name} 不存在")

    db = SessionLocal()
    try:
        verify_game_ownership(db, game_id, user)

        # 获取当前活跃图片
        current_image = (
            db.query(ImageModel)
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
            raise HTTPException(
                status_code=404, detail=f"物品 {item_name} 暂无图片，请先生成图片"
            )

        # 物品图片重新生成：使用当前图片作为参考
        import base64

        from src.services.image_storage import ImageStorageService

        storage_service = ImageStorageService()

        try:
            image_data = storage_service.get_image_data(
                current_image.storage_path, current_image.storage_type
            )
            ext = current_image.storage_path.rsplit(".", 1)[-1].lower()
            mime_type = "image/png" if ext == "png" else "image/jpeg"
            base64_data = base64.b64encode(image_data).decode("utf-8")
            reference_url = f"data:{mime_type};base64,{base64_data}"
        except Exception as e:
            logger.warning(f"Failed to get current item image: {e}")
            reference_url = None

        description = item_data.get("description", "") or f"一个叫{item_name}的物品"

        # 使用 ImageClient.edit_image 进行图生图
        from src.ai.image_client import ImageClient

        image_client = ImageClient()

        if reference_url:
            edit_prompt = f"""基于参考图片，重新绘制物品：
{description}
用户修改意见：{request.feedback}
保持物品的基本特征，根据修改意见调整外观。"""

            results = image_client.edit_image(
                reference_image=reference_url,
                prompt=edit_prompt,
                size="1024*1024",
                num_images=1,
            )

            if results:
                image_data, prompt = results[0]

                # 保存新图片
                storage_path, storage_type = storage_service.save_image(
                    image_data=image_data,
                    game_id=game_id,
                    image_type="item",
                    entity_name=item_name,
                )

                # 停用旧图片
                db.query(ImageModel).filter(
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
                db.add(new_image)
                db.commit()
                db.refresh(new_image)

                return MessageResponse(
                    message=f"物品 {item_name} 图片修改成功",
                    success=True,
                    data={"image_id": new_image.image_id},
                )
            else:
                raise HTTPException(status_code=500, detail="图片生成失败")
        else:
            raise HTTPException(status_code=404, detail="无法获取当前物品图片")

    except ImageContentError as e:
        logger.warning(f"Content inspection failed: {e}")
        raise HTTPException(
            status_code=400, detail="生成图片时触发了内容安全审核，请稍后重试"
        )
    except ImageServiceError as e:
        logger.error(f"Image regeneration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in regenerate_item_image: {e}")
        raise HTTPException(status_code=500, detail=f"图片修改失败: {e}")
    finally:
        db.close()


# ==================== Entity Recognition (实体识别) ====================


@router.post("/{game_id}/recognize-entities")
async def recognize_entities(
    game_id: int,
    request: dict,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """从历史故事中识别重复出现的实体（物品、人物、地点）"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    session = session_service.get_or_restore(game_id, user)
    player_state = session.game_loop.get_state()

    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")

    # 获取现有实体名称列表
    existing_items = list(player_state.items.keys())
    existing_characters = list(player_state.characters.keys())
    existing_landmarks = list(player_state.landmarks.keys())

    # 获取主角名字，添加到已存在人物中（避免识别主角）
    character_settings = player_state.character_settings or {}
    player_name = player_state.player_name or character_settings.get("player_name", "")
    if player_name:
        existing_characters.append(player_name)

    try:
        from src.services.entity_recognition_service import EntityRecognitionService

        recognition_service = EntityRecognitionService(
            session.game_loop.ai_generator.ai_client
        )

        min_appearances = request.get("min_appearances", 3)

        result = recognition_service.recognize_from_history(
            round_history=player_state.round_history,
            existing_items=existing_items,
            existing_characters=existing_characters,
            existing_landmarks=existing_landmarks,
            min_appearances=min_appearances,
            language=session.language,
        )

        return result

    except Exception as e:
        logger.error(f"实体识别失败: {e}")
        raise HTTPException(status_code=500, detail=f"实体识别失败: {e}")


@router.post("/{game_id}/add-entities")
async def add_entities(
    game_id: int,
    request: dict,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """批量添加识别出的实体到收集系统"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    session = session_service.get_or_restore(game_id, user)
    player_state = session.game_loop.get_state()

    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")

    added_items = []
    added_landmarks = []

    try:
        # 添加物品
        for item_data in request.get("items", []):
            item_name = item_data.get("name")
            if item_name and item_name not in player_state.items:
                from src.game.state.item_state import ItemState

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
        for landmark_data in request.get("landmarks", []):
            landmark_name = landmark_data.get("name")
            if landmark_name and landmark_name not in player_state.landmarks:
                from src.game.state.landmark_state import LandmarkState

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
            "message": f"成功添加 {len(added_items)} 个物品, {len(added_landmarks)} 个地点",
            "success": True,
            "added_items": added_items,
            "added_characters": [],
            "added_landmarks": added_landmarks,
        }

    except Exception as e:
        logger.error(f"添加实体失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加实体失败: {e}")


@router.post("/{game_id}/items/create")
async def create_item(
    game_id: int,
    request: dict,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """手动创建物品，可选从历史中提取描述"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    session = session_service.get_or_restore(game_id, user)
    player_state = session.game_loop.get_state()

    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")

    item_name = request.get("name", "").strip()
    if not item_name:
        raise HTTPException(status_code=400, detail="物品名称不能为空")

    # 检查是否已存在
    if item_name in player_state.items:
        raise HTTPException(status_code=400, detail=f"物品 '{item_name}' 已存在")

    try:
        description = ""
        category = "other"
        importance = "normal"
        acquired_context = ""

        # 如果需要从历史中提取描述
        if request.get("generate_description") and player_state.round_history:
            from src.services.entity_recognition_service import EntityRecognitionService

            recognition_service = EntityRecognitionService(
                session.game_loop.ai_generator.ai_client
            )

            item_info = recognition_service.extract_item_description(
                item_name=item_name,
                round_history=player_state.round_history,
                language=session.language,
            )

            if item_info:
                description = item_info.get("description", "")
                category = item_info.get("category", "other")
                importance = item_info.get("importance", "normal")
                acquired_context = item_info.get("acquired_context", "")[:200]

        # 创建物品
        from src.game.state.item_state import ItemState

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
            "message": f"物品 '{item_name}' 创建成功",
            "success": True,
            "item": {
                "name": item_name,
                "description": description,
                "importance": importance,
                "category": category,
                "acquired_week": player_state.week,
                "acquired_context": acquired_context,
                "is_key_item": (importance == "critical"),
                "image_generated": False,
                "description_generated": bool(description),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建物品失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建物品失败: {e}")


@router.delete("/{game_id}/items/{item_name}")
async def delete_item(
    game_id: int,
    item_name: str,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """删除物品"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    session = session_service.get_or_restore(game_id, user)
    player_state = session.game_loop.get_state()

    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")

    # 解码URL编码的物品名称
    from urllib.parse import unquote

    item_name = unquote(item_name)

    if item_name not in player_state.items:
        raise HTTPException(status_code=404, detail=f"物品 '{item_name}' 不存在")

    try:
        # 删除物品
        success = player_state.remove_item(item_name)

        if not success:
            raise HTTPException(status_code=500, detail="删除失败")

        # 同时删除关联的图片记录
        db = SessionLocal()
        try:
            db.query(ImageModel).filter(
                ImageModel.game_id == game_id,
                ImageModel.image_type == "item",
                ImageModel.entity_name == item_name,
            ).delete()
            db.commit()
        finally:
            db.close()

        return {"message": f"物品 '{item_name}' 已删除", "success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除物品失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")


@router.delete("/{game_id}/characters/{character_name}")
async def delete_character(
    game_id: int,
    character_name: str,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """删除人物"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    session = session_service.get_or_restore(game_id, user)
    player_state = session.game_loop.get_state()

    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")

    # 解码URL编码的人物名称
    from urllib.parse import unquote

    character_name = unquote(character_name)

    # 检查是否是主角
    character_settings = player_state.character_settings or {}
    player_name = player_state.player_name or character_settings.get("player_name", "")
    if character_name == player_name:
        raise HTTPException(status_code=400, detail="不能删除主角")

    if character_name not in player_state.characters:
        raise HTTPException(
            status_code=404, detail=f"人物 '{character_name}' 不存在或无法删除"
        )

    try:
        # 删除人物
        success = player_state.remove_character(character_name)

        if not success:
            raise HTTPException(status_code=500, detail="删除失败")

        # 同时删除关联的图片记录
        db = SessionLocal()
        try:
            db.query(ImageModel).filter(
                ImageModel.game_id == game_id,
                ImageModel.image_type == "character",
                ImageModel.entity_name == character_name,
            ).delete()
            db.commit()
        finally:
            db.close()

        return {"message": f"人物 '{character_name}' 已删除", "success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除人物失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")


@router.delete("/{game_id}/landmarks/{landmark_name}")
async def delete_landmark(
    game_id: int,
    landmark_name: str,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """删除地点/标志物"""
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    session = session_service.get_or_restore(game_id, user)
    player_state = session.game_loop.get_state()

    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")

    # 解码URL编码的地点名称
    from urllib.parse import unquote

    landmark_name = unquote(landmark_name)

    if landmark_name not in player_state.landmarks:
        raise HTTPException(status_code=404, detail=f"地点 '{landmark_name}' 不存在")

    try:
        # 删除地点
        success = player_state.remove_landmark(landmark_name)

        if not success:
            raise HTTPException(status_code=500, detail="删除失败")

        # 同时删除关联的图片记录
        db = SessionLocal()
        try:
            db.query(ImageModel).filter(
                ImageModel.game_id == game_id,
                ImageModel.image_type == "landmark",
                ImageModel.entity_name == landmark_name,
            ).delete()
            db.commit()
        finally:
            db.close()

        return {"message": f"地点 '{landmark_name}' 已删除", "success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除地点失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
