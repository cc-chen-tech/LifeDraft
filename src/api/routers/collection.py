"""收集系统API路由 - 人物和物品收集"""

import logging
from typing import Any, Dict, Generator, List, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_optional, get_session
from src.api.routers.image_failures import image_failure_http_exception
from src.api.schemas import (AddEntitiesRequest, CollectionResponse, MessageResponse,
                             RegenerateCharacterImageRequest,
                             RegenerateItemImageRequest)
from src.api.services.session_service import session_service
from src.database.models import SessionLocal
from src.database.singletons import get_game_db
from src.game.state import PlayerState
from src.services.collection_service import (CollectionService,
                                             EntityNotFoundError,
                                             ImageGenerationError,
                                             PermissionDeniedError)
from src.services.image_service import (ImageContentError,
                                        ImageProviderServiceError,
                                        ImageServiceError)
from src.services.item_extraction_service import ItemExtractionService
from src.services.landmark_extraction_service import LandmarkExtractionService

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_user(user_id: Optional[int]) -> int:
    """验证用户已登录。"""
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    return user_id


def _get_player_state(game_id: int, user_id: int) -> tuple:  # type: ignore
    """获取游戏会话和玩家状态。"""
    session = session_service.get_or_restore(game_id, user_id)
    player_state = session.game_loop.get_state()
    if not player_state:
        raise HTTPException(status_code=400, detail="游戏状态不存在")
    return session, player_state


def _save_player_state(game_id: int, player_state: PlayerState) -> None:
    """将玩家状态持久化到数据库。"""
    try:
        db = get_game_db()
        db.save_game_progress(game_id, player_state)
    except Exception as e:
        logger.warning(f"保存游戏状态失败 (非阻塞): {e}")


def _build_entity_recognition_history(player_state: Any) -> List[Dict[str, Any]]:
    """构建实体识别输入，包含当前未选择但已展示的故事。"""
    history = list(getattr(player_state, "round_history", None) or [])
    current_event_data = getattr(player_state, "current_event_data", None) or {}
    if not isinstance(current_event_data, dict):
        return history

    event_description = (
        current_event_data.get("event_description")
        or current_event_data.get("story_text")
        or ""
    )
    if not event_description:
        return history

    current_week = getattr(player_state, "week", 0)
    current_round = getattr(player_state, "current_round", 0)
    has_current_round_story = any(
        entry.get("week") == current_week
        and entry.get("round") == current_round
        and (entry.get("event_description") or entry.get("story_continuation"))
        for entry in history
        if isinstance(entry, dict)
    )
    if has_current_round_story:
        return history

    history.append(
        {
            "week": current_week,
            "round": current_round,
            "event_description": event_description,
        }
    )
    return history


def _extract_named_entities_from_settings(values: Any) -> List[str]:
    """Extract explicit entity names from structured character settings."""
    names: List[str] = []
    if isinstance(values, dict):
        if any(key in values for key in ("name", "person_name", "character_name")):
            values = [values]
        else:
            values = [
                value if isinstance(value, dict) and value.get("name") else key
                for key, value in values.items()
            ]
    if not isinstance(values, list):
        return names

    for value in values:
        if isinstance(value, str):
            name = value.strip()
        elif isinstance(value, dict):
            name = str(
                value.get("name")
                or value.get("person_name")
                or value.get("character_name")
                or ""
            ).strip()
        else:
            name = ""
        if name and name not in names:
            names.append(name)
    return names


def _extend_unique_names(names: List[str], candidates: Any) -> None:
    """Append non-empty candidate names while preserving first-seen order."""
    for name in _extract_named_entities_from_settings(candidates):
        if name and name not in names:
            names.append(name)


def _extend_relationship_effect_names(names: List[str], effects: Any) -> None:
    if not isinstance(effects, dict):
        return
    relationships = effects.get("relationships")
    if not isinstance(relationships, dict):
        return
    for name in relationships.keys():
        clean_name = str(name).strip()
        if clean_name and clean_name not in names:
            names.append(clean_name)


def _build_eligible_recognition_characters(player_state: Any) -> List[str]:
    """Characters eligible for smart recognition based on relationship metadata."""
    character_settings = getattr(player_state, "character_settings", None) or {}
    if not isinstance(character_settings, dict):
        character_settings = {}

    relationships = character_settings.get("relationships") or {}
    family = character_settings.get("family") or {}

    eligible: List[str] = []
    if isinstance(relationships, list):
        _extend_unique_names(eligible, relationships)
    elif isinstance(relationships, dict):
        _extend_unique_names(eligible, relationships.get("key_people"))
        _extend_unique_names(eligible, relationships.get("important_people"))
    if isinstance(family, dict):
        _extend_unique_names(eligible, family.get("family_members"))

    relationship_scores = getattr(player_state, "relationships", None)
    if isinstance(relationship_scores, dict):
        for name in relationship_scores.keys():
            clean_name = str(name).strip()
            if clean_name and clean_name not in eligible:
                eligible.append(clean_name)

    for entry in getattr(player_state, "round_history", None) or []:
        if isinstance(entry, dict):
            _extend_relationship_effect_names(eligible, entry.get("effects"))

    current_event_data = getattr(player_state, "current_event_data", None) or {}
    if isinstance(current_event_data, dict):
        for option in current_event_data.get("options") or []:
            if isinstance(option, dict):
                _extend_relationship_effect_names(eligible, option.get("effects"))

    for storyline in getattr(player_state, "pending_storylines", None) or []:
        if isinstance(storyline, dict):
            _extend_unique_names(eligible, storyline.get("related_characters"))

    for seed in getattr(player_state, "foreshadowing_seeds", None) or []:
        if isinstance(seed, dict):
            _extend_unique_names(eligible, seed.get("related_characters"))

    for habit in getattr(player_state, "character_habits", None) or []:
        if isinstance(habit, dict):
            _extend_unique_names(eligible, [habit.get("character")])

    character_arc_state = getattr(player_state, "character_arc_state", None)
    if isinstance(character_arc_state, dict):
        _extend_unique_names(eligible, list(character_arc_state.keys()))

    for world_event in getattr(player_state, "world_breathing_events", None) or []:
        if isinstance(world_event, dict):
            _extend_unique_names(eligible, world_event.get("affected_npcs"))

    player_name = getattr(player_state, "player_name", "") or character_settings.get(
        "player_name", ""
    )
    return [name for name in dict.fromkeys(eligible) if name and name != player_name]


# ==================== 获取收集数据 ====================


@router.get("/{game_id}", response_model=CollectionResponse)
async def get_collection(  # type: ignore
    game_id: int,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """获取游戏的收集数据（人物和物品）"""
    user_id = _require_user(user_id)
    _, player_state = _get_player_state(game_id, user_id)

    db = SessionLocal()
    try:
        service = CollectionService(db)
        return service.get_collection(game_id, player_state)
    finally:
        db.close()


@router.get("/{game_id}/details", response_model=CollectionResponse)
async def get_collection_details(  # type: ignore
    game_id: int,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """获取游戏的收集数据 - 与 /{game_id} 相同，为兼容前端路径"""
    return await get_collection(game_id, user_id)


# ==================== 生成图片 ====================


@router.post("/{game_id}/characters/{name}/generate-image", response_model=MessageResponse)
async def generate_character_image(  # type: ignore
    game_id: int,
    name: str,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """生成人物图片"""
    user_id = _require_user(user_id)
    _, player_state = _get_player_state(game_id, user_id)

    db = SessionLocal()
    try:
        service = CollectionService(db)
        service.verify_game_ownership(game_id, user_id)
        image_id = service.generate_character_image(game_id, name, player_state)

        return MessageResponse(
            message=f"人物 {name} 图片生成成功",
            success=True,
            data={"image_id": image_id},
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ImageProviderServiceError as e:
        logger.warning(
            "Image provider failure: route=collection-character-generate code=%s category=%s trace_id=%s",
            e.code,
            e.category,
            e.provider_trace_id,
        )
        raise image_failure_http_exception(e)
    except ImageContentError:
        raise HTTPException(status_code=400, detail="生成图片时触发了内容安全审核，请稍后重试")
    except ImageServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/{game_id}/characters/{name}/generate-description", response_model=MessageResponse)
async def generate_character_description(  # type: ignore
    game_id: int,
    name: str,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """生成人物描述（人物描述已存在于角色设定中）"""
    _require_user(user_id)
    return MessageResponse(message=f"人物 {name} 描述已存在", success=True)


@router.post("/{game_id}/items/{item_name}/generate-image", response_model=MessageResponse)
async def generate_item_image(  # type: ignore
    game_id: int,
    item_name: str,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """生成物品图片"""
    user_id = _require_user(user_id)
    _, player_state = _get_player_state(game_id, user_id)
    item_name = unquote(item_name)

    db = SessionLocal()
    try:
        service = CollectionService(db)
        service.verify_game_ownership(game_id, user_id)
        image_id = service.generate_item_image(game_id, item_name, player_state)

        # 持久化状态变更
        _save_player_state(game_id, player_state)

        return MessageResponse(
            message=f"物品 {item_name} 图片生成成功",
            success=True,
            data={"image_id": image_id},
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ImageProviderServiceError as e:
        logger.warning(
            "Image provider failure: route=collection-item-generate code=%s category=%s trace_id=%s",
            e.code,
            e.category,
            e.provider_trace_id,
        )
        raise image_failure_http_exception(e)
    except ImageContentError:
        raise HTTPException(status_code=400, detail="生成图片时触发了内容安全审核，请稍后重试")
    except ImageServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/{game_id}/items/{item_name}/generate-description", response_model=MessageResponse)
async def generate_item_description(  # type: ignore
    game_id: int,
    item_name: str,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """生成物品描述"""
    user_id = _require_user(user_id)
    session, player_state = _get_player_state(game_id, user_id)
    item_name = unquote(item_name)

    item_data = player_state.items.get(item_name)
    if not item_data:
        raise HTTPException(status_code=404, detail=f"物品 {item_name} 不存在")

    if item_data.get("description") and len(item_data.get("description", "")) > 50:
        return MessageResponse(message=f"物品 {item_name} 描述已存在", success=True)

    try:
        item_service = ItemExtractionService(session.game_loop.ai_generator.ai_client)
        new_description = item_service.generate_item_description(
            item_name=item_name,
            item_category=item_data.get("category", "other"),
            acquired_context=item_data.get("acquired_context", ""),
            story_context=item_data.get("acquired_context", ""),
            language=session.language,
        )

        if new_description:
            player_state.update_item(
                item_name, description=new_description, description_generated=True
            )
            # 持久化状态变更
            _save_player_state(game_id, player_state)
            return MessageResponse(
                message=f"物品 {item_name} 描述生成成功",
                success=True,
                data={"description": new_description},
            )
        raise HTTPException(status_code=500, detail="描述生成失败")

    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"描述生成失败: {e}")
    except Exception as e:
        logger.exception(f"Failed to generate item description: {e}")
        raise HTTPException(status_code=500, detail=f"描述生成失败: {e}")


# ==================== 标志物端点 ====================


@router.post(
    "/{game_id}/landmarks/{landmark_name}/generate-image",
    response_model=MessageResponse,
)
async def generate_landmark_image(  # type: ignore
    game_id: int,
    landmark_name: str,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """生成标志物图片"""
    user_id = _require_user(user_id)
    _, player_state = _get_player_state(game_id, user_id)
    landmark_name = unquote(landmark_name)

    db = SessionLocal()
    try:
        service = CollectionService(db)
        service.verify_game_ownership(game_id, user_id)
        image_id = service.generate_landmark_image(game_id, landmark_name, player_state)

        # 持久化状态变更
        _save_player_state(game_id, player_state)

        return MessageResponse(
            message=f"标志物 {landmark_name} 图片生成成功",
            success=True,
            data={"image_id": image_id},
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ImageProviderServiceError as e:
        logger.warning(
            "Image provider failure: route=collection-landmark-generate code=%s category=%s trace_id=%s",
            e.code,
            e.category,
            e.provider_trace_id,
        )
        raise image_failure_http_exception(e)
    except ImageContentError:
        raise HTTPException(status_code=400, detail="生成图片时触发了内容安全审核，请稍后重试")
    except ImageServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post(
    "/{game_id}/landmarks/{landmark_name}/generate-description",
    response_model=MessageResponse,
)
async def generate_landmark_description(  # type: ignore
    game_id: int,
    landmark_name: str,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """生成标志物描述"""
    user_id = _require_user(user_id)
    session, player_state = _get_player_state(game_id, user_id)
    landmark_name = unquote(landmark_name)

    landmark_data = player_state.landmarks.get(landmark_name)
    if not landmark_data:
        raise HTTPException(status_code=404, detail=f"标志物 {landmark_name} 不存在")

    if landmark_data.get("description") and len(landmark_data.get("description", "")) > 50:
        return MessageResponse(message=f"标志物 {landmark_name} 描述已存在", success=True)

    try:
        landmark_service = LandmarkExtractionService(session.game_loop.ai_generator.ai_client)
        new_description = landmark_service.generate_landmark_description(
            landmark_name=landmark_name,
            landmark_category=landmark_data.get("category", "other"),
            context=landmark_data.get("context", ""),
            story_context=landmark_data.get("context", ""),
            language=session.language,
        )

        if new_description:
            player_state.update_landmark(landmark_name, description=new_description)
            # 持久化状态变更
            _save_player_state(game_id, player_state)
            return MessageResponse(
                message=f"标志物 {landmark_name} 描述生成成功",
                success=True,
                data={"description": new_description},
            )
        raise HTTPException(status_code=500, detail="描述生成失败")

    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"描述生成失败: {e}")
    except Exception as e:
        logger.exception(f"Failed to generate landmark description: {e}")
        raise HTTPException(status_code=500, detail=f"描述生成失败: {e}")


# ==================== 重新生成图片 ====================


@router.post("/{game_id}/characters/{name}/regenerate-image", response_model=MessageResponse)
async def regenerate_character_image(  # type: ignore
    game_id: int,
    name: str,
    request: RegenerateCharacterImageRequest,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """基于用户文字描述重新生成人物画像"""
    user_id = _require_user(user_id)
    _, player_state = _get_player_state(game_id, user_id)

    db = SessionLocal()
    try:
        service = CollectionService(db)
        service.verify_game_ownership(game_id, user_id)
        service.validate_character_for_regenerate(name, player_state)

        image_id = service.regenerate_character_image(
            game_id, name, request.feedback, request.image_id
        )

        return MessageResponse(
            message=f"人物 {name} 画像修改成功",
            success=True,
            data={"image_id": image_id},
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ImageProviderServiceError as e:
        logger.warning(
            "Image provider failure: route=collection-character-regenerate code=%s category=%s trace_id=%s",
            e.code,
            e.category,
            e.provider_trace_id,
        )
        raise image_failure_http_exception(e)
    except ImageContentError:
        raise HTTPException(status_code=400, detail="生成图片时触发了内容安全审核，请稍后重试")
    except ImageServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/{game_id}/items/{item_name}/regenerate-image", response_model=MessageResponse)
async def regenerate_item_image(  # type: ignore
    game_id: int,
    item_name: str,
    request: RegenerateItemImageRequest,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """基于用户文字描述重新生成物品图片"""
    user_id = _require_user(user_id)
    _, player_state = _get_player_state(game_id, user_id)
    item_name = unquote(item_name)

    db = SessionLocal()
    try:
        service = CollectionService(db)
        service.verify_game_ownership(game_id, user_id)
        image_id = service.regenerate_item_image(game_id, item_name, request.feedback, player_state)

        return MessageResponse(
            message=f"物品 {item_name} 图片修改成功",
            success=True,
            data={"image_id": image_id},
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ImageProviderServiceError as e:
        logger.warning(
            "Image provider failure: route=collection-item-regenerate code=%s category=%s trace_id=%s",
            e.code,
            e.category,
            e.provider_trace_id,
        )
        raise image_failure_http_exception(e)
    except ImageGenerationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ImageContentError:
        raise HTTPException(status_code=400, detail="生成图片时触发了内容安全审核，请稍后重试")
    except ImageServiceError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"参数错误: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in regenerate_item_image: {e}")
        raise HTTPException(status_code=500, detail=f"图片修改失败: {e}")
    finally:
        db.close()


# ==================== 实体识别 ====================


@router.post("/{game_id}/recognize-entities")
async def recognize_entities(  # type: ignore
    game_id: int,
    request: dict,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """从历史故事中识别重复出现的实体（物品、人物、地点）"""
    user_id = _require_user(user_id)
    session, player_state = _get_player_state(game_id, user_id)

    # 获取现有实体名称列表
    existing_items = list(player_state.items.keys())
    existing_characters = list(player_state.characters.keys())
    existing_landmarks = list(player_state.landmarks.keys())

    # 添加主角到已存在人物中（避免识别主角）
    character_settings = player_state.character_settings or {}
    player_name = player_state.player_name or character_settings.get("player_name", "")
    if player_name:
        existing_characters.append(player_name)

    try:
        from src.services.entity_recognition_service import \
            EntityRecognitionService

        # 根据游戏进度动态计算阈值
        recognition_history = _build_entity_recognition_history(player_state)
        total_rounds = len(recognition_history)
        default_min = max(1, total_rounds // 15)  # 每15回合+1，最低1
        min_appearances = request.get("min_appearances") or default_min

        recognition_service = EntityRecognitionService(session.game_loop.ai_generator.ai_client)
        return recognition_service.recognize_from_history(
            round_history=recognition_history,
            existing_items=existing_items,
            existing_characters=existing_characters,
            existing_landmarks=existing_landmarks,
            min_appearances=min_appearances,
            language=session.language,
            eligible_character_names=_build_eligible_recognition_characters(player_state),
        )
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"实体识别失败: {e}")
    except Exception as e:
        logger.exception(f"实体识别失败: {e}")
        raise HTTPException(status_code=500, detail=f"实体识别失败: {e}")


@router.post("/{game_id}/add-entities")
async def add_entities(  # type: ignore
    game_id: int,
    request: AddEntitiesRequest,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """批量添加识别出的实体到收集系统"""
    user_id = _require_user(user_id)
    _, player_state = _get_player_state(game_id, user_id)

    db = SessionLocal()
    try:
        service = CollectionService(db)
        result = service.add_entities(
            player_state,
            [entity.model_dump() for entity in request.items],
            [entity.model_dump() for entity in request.landmarks],
            [entity.model_dump() for entity in request.characters],
        )

        # 持久化状态变更
        _save_player_state(game_id, player_state)

        return {
            "message": (
                f"成功添加 {len(result['added_items'])} 个物品, "
                f"{len(result['added_characters'])} 个人物, "
                f"{len(result['added_landmarks'])} 个地点"
            ),
            "success": True,
            "added_items": result["added_items"],
            "added_characters": result["added_characters"],
            "added_landmarks": result["added_landmarks"],
        }
    except (ValueError, TypeError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"添加实体失败: {e}")
    except Exception as e:
        logger.exception(f"添加实体失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加实体失败: {e}")
    finally:
        db.close()


# ==================== 物品管理 ====================


@router.post("/{game_id}/items/create")
async def create_item(  # type: ignore
    game_id: int,
    request: dict,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """手动创建物品，可选从历史中提取描述"""
    user_id = _require_user(user_id)
    session, player_state = _get_player_state(game_id, user_id)

    db = SessionLocal()
    try:
        service = CollectionService(db)
        item_info = service.create_item(
            player_state,
            request.get("name", ""),
            ai_client=session.game_loop.ai_generator.ai_client,
            language=session.language,
            generate_description=request.get("generate_description", False),
        )

        # 持久化状态变更
        _save_player_state(game_id, player_state)

        return {
            "message": f"物品 '{item_info['name']}' 创建成功",
            "success": True,
            "item": item_info,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (TypeError, KeyError) as e:
        raise HTTPException(status_code=400, detail=f"创建物品失败: {e}")
    except Exception as e:
        logger.exception(f"创建物品失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建物品失败: {e}")
    finally:
        db.close()


@router.delete("/{game_id}/items/{item_name}")
async def delete_item(  # type: ignore
    game_id: int,
    item_name: str,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """删除物品"""
    user_id = _require_user(user_id)
    _, player_state = _get_player_state(game_id, user_id)

    db = SessionLocal()
    try:
        service = CollectionService(db)
        success = service.delete_item(game_id, item_name, player_state)
        if not success:
            raise HTTPException(status_code=500, detail="删除失败")

        # 持久化状态变更
        _save_player_state(game_id, player_state)

        return {"message": f"物品 '{item_name}' 已删除", "success": True}
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    except Exception as e:
        logger.exception(f"删除物品失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    finally:
        db.close()


@router.delete("/{game_id}/characters/{character_name}")
async def delete_character(  # type: ignore
    game_id: int,
    character_name: str,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """删除人物"""
    user_id = _require_user(user_id)
    _, player_state = _get_player_state(game_id, user_id)

    db = SessionLocal()
    try:
        service = CollectionService(db)
        success = service.delete_character(game_id, character_name, player_state)
        if not success:
            raise HTTPException(status_code=500, detail="删除失败")

        # 持久化状态变更
        _save_player_state(game_id, player_state)

        return {"message": f"人物 '{character_name}' 已删除", "success": True}
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    except Exception as e:
        logger.exception(f"删除人物失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    finally:
        db.close()


@router.delete("/{game_id}/landmarks/{landmark_name}")
async def delete_landmark(  # type: ignore
    game_id: int,
    landmark_name: str,
    user_id: Optional[int] = Depends(get_current_user_optional),
):
    """删除地点/标志物"""
    user_id = _require_user(user_id)
    _, player_state = _get_player_state(game_id, user_id)

    db = SessionLocal()
    try:
        service = CollectionService(db)
        success = service.delete_landmark(game_id, landmark_name, player_state)
        if not success:
            raise HTTPException(status_code=500, detail="删除失败")

        # 持久化状态变更
        _save_player_state(game_id, player_state)

        return {"message": f"地点 '{landmark_name}' 已删除", "success": True}
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (OSError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    except Exception as e:
        logger.exception(f"删除地点失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {e}")
    finally:
        db.close()
