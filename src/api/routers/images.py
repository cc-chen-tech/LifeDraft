"""Image generation router - 图片生成API路由"""

import logging
from typing import Generator, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_current_user_optional, get_db
from src.api.schemas import (BatchGenerateCharactersRequest,
                             GenerateImageRequest,
                             GenerateOpeningIllustrationRequest,
                             GenerateRoundSceneRequest, ImageListResponse,
                             ImageResponse, MessageResponse,
                             OpeningIllustrationResponse,
                             RegenerateFreshImageRequest,
                             RegenerateImageRequest,
                             RegenerateOpeningIllustrationRequest,
                             RegenerateRoundSceneRequest, RoundSceneResponse)
from src.database.models import Game
from src.database.models import Image as ImageModel
from src.database.models import SessionLocal, User
from src.services.image_service import (ImageContentError, ImageService,
                                        ImageServiceError)
from src.services.image_storage import ImageStorageError, ImageStorageService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_session() -> Generator[Session, None, None]:
    """Get a SQLAlchemy session for image operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_game_ownership(db: Session, game_id: int, user_id: int) -> Game:
    """
    验证游戏归属权

    Args:
        db: 数据库会话
        game_id: 游戏ID
        user_id: 用户ID

    Returns:
        Game对象

    Raises:
        HTTPException: 如果游戏不存在或不属于该用户
    """
    game = db.query(Game).filter(Game.game_id == game_id).first()

    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在或无权访问")

    # ★ 向后兼容：如果游戏没有user_id（旧数据），允许所有登录用户访问
    if game.user_id is not None and game.user_id != user_id:
        raise HTTPException(status_code=404, detail="游戏不存在或无权访问")

    return game


def verify_image_ownership(db: Session, image_id: int, user_id: int) -> ImageModel:
    """
    验证图片归属权（通过游戏关联）

    Args:
        db: 数据库会话
        image_id: 图片ID
        user_id: 用户ID

    Returns:
        ImageModel对象

    Raises:
        HTTPException: 如果图片不存在或不属于该用户
    """
    image = db.query(ImageModel).filter(ImageModel.image_id == image_id).first()

    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")

    # 验证游戏归属权
    verify_game_ownership(db, int(image.game_id), user_id)  # type: ignore[arg-type]

    return image


@router.post("/generate", response_model=ImageListResponse)
async def generate_image(
    req: GenerateImageRequest,
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    生成图片

    支持生成人物形象、地点、物品等图片
    人物形象默认并行生成4张不同姿势的全身像
    """
    logger.info(
        f"Generating image: type={req.image_type}, name={req.entity_name}, game={req.game_id}"
    )

    # ★ 权限验证：必须登录
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    # ★ 权限验证：验证游戏归属
    verify_game_ownership(db, req.game_id, user)  # user 已经是 user_id (int)

    try:
        service = ImageService(db)

        if req.image_type == "character":
            # 人物形象：生成1张
            image_models = service.generate_character_image(
                game_id=req.game_id,
                name=req.entity_name,
                description=req.description,
                era=req.era,
                entity_key=req.entity_key,
                metadata=req.extra_context,
                num_images=1,  # ★ 只生成1张，减少等待时间
                feedback=req.feedback,  # ★ 传递用户反馈
            )
            return ImageListResponse(
                images=[
                    ImageResponse(
                        image_id=int(img.image_id),  # type: ignore[arg-type]
                        game_id=int(img.game_id),  # type: ignore[arg-type]
                        image_type=str(img.image_type),  # type: ignore[arg-type]
                        entity_name=str(img.entity_name),  # type: ignore[arg-type]
                        entity_key=str(img.entity_key) if img.entity_key else None,  # type: ignore[arg-type]
                        image_url=service.get_image_url(img),
                        prompt_used=str(img.prompt_text),  # type: ignore[arg-type]
                        version=int(img.version),  # type: ignore[arg-type]
                        created_at=(img.created_at.isoformat() if img.created_at else None),
                    )
                    for img in image_models
                ],
                total=len(image_models),
            )
        elif req.image_type == "location":
            image_model = service.generate_location_image(
                game_id=req.game_id,
                name=req.entity_name,
                description=req.description,
                era=req.era,
                metadata=req.extra_context,
            )
            return ImageListResponse(
                images=[
                    ImageResponse(
                        image_id=int(image_model.image_id),  # type: ignore[arg-type]
                        game_id=int(image_model.game_id),  # type: ignore[arg-type]
                        image_type=str(image_model.image_type),  # type: ignore[arg-type]
                        entity_name=str(image_model.entity_name),  # type: ignore[arg-type]
                        entity_key=str(image_model.entity_key) if image_model.entity_key else None,  # type: ignore[arg-type]
                        image_url=service.get_image_url(image_model),
                        prompt_used=str(image_model.prompt_text),  # type: ignore[arg-type]
                        version=int(image_model.version),  # type: ignore[arg-type]
                        created_at=(
                            image_model.created_at.isoformat() if image_model.created_at else None
                        ),
                    )
                ],
                total=1,
            )
        elif req.image_type == "item":
            image_model = service.generate_item_image(
                game_id=req.game_id,
                name=req.entity_name,
                description=req.description,
                era=req.era,
                metadata=req.extra_context,
            )
            return ImageListResponse(
                images=[
                    ImageResponse(
                        image_id=int(image_model.image_id),  # type: ignore[arg-type]
                        game_id=int(image_model.game_id),  # type: ignore[arg-type]
                        image_type=str(image_model.image_type),  # type: ignore[arg-type]
                        entity_name=str(image_model.entity_name),  # type: ignore[arg-type]
                        entity_key=str(image_model.entity_key) if image_model.entity_key else None,  # type: ignore[arg-type]
                        image_url=service.get_image_url(image_model),
                        prompt_used=str(image_model.prompt_text),  # type: ignore[arg-type]
                        version=int(image_model.version),  # type: ignore[arg-type]
                        created_at=(
                            image_model.created_at.isoformat() if image_model.created_at else None
                        ),
                    )
                ],
                total=1,
            )
        else:
            raise HTTPException(status_code=400, detail=f"不支持的图片类型: {req.image_type}")

    except ImageContentError as e:
        # ★ 内容审核错误 - 返回 400 而不是 500，让用户知道是输入问题
        logger.warning(f"Content inspection failed: {e}")
        # 返回友好的字符串消息，前端可以直接显示
        raise HTTPException(
            status_code=400,
            detail="您的修改描述可能包含敏感内容，无法生成图片。请尝试使用其他描述方式，如：穿着简洁的衣服、换一套服装等。",
        )
    except ImageServiceError as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (ValueError, TypeError, KeyError) as e:
        logger.warning(f"Invalid data in generate_image: {e}")
        raise HTTPException(status_code=400, detail=f"参数错误: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in generate_image: {e}")
        raise HTTPException(status_code=500, detail=f"图片生成失败: {e}")


@router.post("/batch-characters", response_model=ImageListResponse)
async def batch_generate_character_images(
    req: BatchGenerateCharactersRequest,
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    批量生成关键人物画像

    从 character_settings 中提取 family_members 和 key_people，
    为每个人物生成画像。
    使用 DeepSeek 生成描述，然后用 qwen-image-max 生成图片。
    """
    logger.info(f"Batch generating character images for game {req.game_id}")

    # ★ 权限验证：必须登录
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    # ★ 权限验证：验证游戏归属
    verify_game_ownership(db, req.game_id, user)

    # 提取所有需要生成画像的人物
    characters_to_generate = []

    # 1. 从 family 中提取家庭成员
    family = req.character_settings.get("family", {})
    family_members = family.get("family_members", [])
    for member in family_members:
        if isinstance(member, dict) and member.get("name"):
            characters_to_generate.append(
                {
                    "name": member.get("name"),
                    "role": member.get("role", "家庭成员"),
                    "gender": member.get("gender"),
                    "age": member.get("age"),
                    "description": member.get("relationship", ""),
                }
            )

    # 2. 从 relationships 中提取关键人物
    relationships = req.character_settings.get("relationships", {})
    key_people = relationships.get("key_people", [])
    for person in key_people:
        if isinstance(person, dict) and person.get("name"):
            characters_to_generate.append(
                {
                    "name": person.get("name"),
                    "role": person.get("role", "关键人物"),
                    "gender": person.get("gender"),
                    "age": person.get("age"),
                    "description": person.get("relationship_desc", "")
                    or person.get("relationship", ""),
                }
            )

    if not characters_to_generate:
        logger.info("No characters found to generate images for")
        return ImageListResponse(images=[], total=0)

    logger.info(
        f"Found {len(characters_to_generate)} characters to generate: {[c['name'] for c in characters_to_generate]}"
    )

    # 提取时代背景
    era = "现代"
    era_setting = req.character_settings.get("era", {})
    if isinstance(era_setting, dict):
        era = era_setting.get("era_name") or era_setting.get("era_description") or "现代"

    # 批量生成
    service = ImageService(db)
    all_images = []

    for idx, char in enumerate(characters_to_generate):
        try:
            # ★ 如果不是第一个人，添加延迟避免速率限制
            if idx > 0:
                import asyncio

                await asyncio.sleep(3)  # 每次生成间隔3秒

            # 构建描述
            desc_parts = []
            if char.get("age"):
                desc_parts.append(f"{char['age']}岁")
            if char.get("gender"):
                desc_parts.append(str(char["gender"]))
            if char.get("description"):
                desc_parts.append(char["description"])

            description = "，".join(desc_parts) if desc_parts else "一个普通人"

            # 生成 entity_key
            entity_key = f"npc_{char['name']}"

            logger.info(f"Generating image for {char['name']} ({char['role']}): {description}")

            image_models = service.generate_character_image(
                game_id=req.game_id,
                name=char["name"],
                description=description,
                era=era,
                entity_key=entity_key,
                metadata={
                    "role": char["role"],
                    "character_settings": req.character_settings,
                },
                num_images=1,
            )

            for img in image_models:
                all_images.append(
                    ImageResponse(
                        image_id=int(img.image_id),  # type: ignore[arg-type]
                        game_id=int(img.game_id),  # type: ignore[arg-type]
                        image_type=str(img.image_type),  # type: ignore[arg-type]
                        entity_name=str(img.entity_name),  # type: ignore[arg-type]
                        entity_key=str(img.entity_key) if img.entity_key else None,  # type: ignore[arg-type]
                        image_url=service.get_image_url(img),
                        prompt_used=str(img.prompt_text),  # type: ignore[arg-type]
                        version=int(img.version),  # type: ignore[arg-type]
                        created_at=(img.created_at.isoformat() if img.created_at else None),
                    )
                )

        except ImageContentError as e:
            logger.warning(f"Content inspection failed for {char['name']}: {e}")
            # 跳过这个人物，继续生成其他人物
            continue
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Invalid data generating image for {char['name']}: {e}")
            continue
        except Exception as e:
            error_str = str(e)
            # ★ 检测 429 速率限制错误
            if "429" in error_str or "RateQuota" in error_str or "rate limit" in error_str.lower():
                logger.warning(f"Rate limit hit for {char['name']}, waiting 10 seconds...")
                import asyncio

                await asyncio.sleep(10)  # 等待10秒后重试一次
                try:
                    image_models = service.generate_character_image(
                        game_id=req.game_id,
                        name=char["name"],
                        description=description,
                        era=era,
                        entity_key=entity_key,
                        metadata={
                            "role": char["role"],
                            "character_settings": req.character_settings,
                        },
                        num_images=1,
                    )
                    for img in image_models:
                        all_images.append(
                            ImageResponse(
                                image_id=int(img.image_id),  # type: ignore[arg-type]
                                game_id=int(img.game_id),  # type: ignore[arg-type]
                                image_type=str(img.image_type),  # type: ignore[arg-type]
                                entity_name=str(img.entity_name),  # type: ignore[arg-type]
                                entity_key=str(img.entity_key) if img.entity_key else None,  # type: ignore[arg-type]
                                image_url=service.get_image_url(img),
                                prompt_used=str(img.prompt_text),  # type: ignore[arg-type]
                                version=int(img.version),  # type: ignore[arg-type]
                                created_at=(img.created_at.isoformat() if img.created_at else None),
                            )
                        )
                    logger.info(f"Retry succeeded for {char['name']}")
                    continue
                except (OSError, IOError) as retry_err:
                    logger.error(f"Retry IO error for {char['name']}: {retry_err}")
                except Exception as retry_err:
                    logger.exception(f"Retry unexpected error for {char['name']}: {retry_err}")

            logger.error(f"Failed to generate image for {char['name']}: {e}")
            # 跳过这个人物，继续生成其他人物
            continue

    logger.info(f"Batch generation complete: {len(all_images)} images generated")

    return ImageListResponse(
        images=all_images,
        total=len(all_images),
    )


@router.post("/opening-illustration", response_model=OpeningIllustrationResponse)
async def generate_opening_illustration(
    req: GenerateOpeningIllustrationRequest,
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    生成开场故事插画

    使用 DeepSeek 分析故事文本，选择重要场景，
    然后使用千问 image-edit 模型生成插画。
    如果有玩家形象图片，会将其作为参考以保持人物一致性。
    """
    logger.info(f"Generating opening illustration for game {req.game_id}")

    # ★ 权限验证：必须登录
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    # ★ 权限验证：验证游戏归属
    verify_game_ownership(db, req.game_id, user)

    try:
        service = ImageService(db)
        image_model = service.generate_opening_illustration(
            game_id=req.game_id,
            story_text=req.story_text,
            character_settings=req.character_settings,
            player_name=req.player_name,
            player_image_id=req.player_image_id,
        )

        return OpeningIllustrationResponse(
            image_id=int(image_model.image_id),  # type: ignore[arg-type]
            game_id=int(image_model.game_id),  # type: ignore[arg-type]
            image_url=service.get_image_url(image_model),
            scene_description=image_model.metadata_json.get("scene_description", ""),
            prompt_used=str(image_model.prompt_text),  # type: ignore[arg-type]
            created_at=(image_model.created_at.isoformat() if image_model.created_at else None),
        )

    except ImageContentError as e:
        logger.warning(f"Content inspection failed for opening illustration: {e}")
        raise HTTPException(
            status_code=400,
            detail="生成插画时触发了内容安全审核。请尝试使用其他描述方式。",
        )
    except ImageServiceError as e:
        logger.error(f"Opening illustration generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (ValueError, TypeError, KeyError) as e:
        logger.warning(f"Invalid data in generate_opening_illustration: {e}")
        raise HTTPException(status_code=400, detail=f"参数错误: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in generate_opening_illustration: {e}")
        raise HTTPException(status_code=500, detail=f"生成开场插画失败: {e}")


@router.post("/opening-illustration/regenerate", response_model=OpeningIllustrationResponse)
async def regenerate_opening_illustration(
    req: RegenerateOpeningIllustrationRequest,
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    基于用户输入重新生成开场故事插画

    使用当前插画作为参考，结合用户自定义提示词重新生成。
    保持场景和人物的一致性，同时应用用户的修改意见。
    """
    logger.info(f"Regenerating opening illustration for game {req.game_id}")

    # ★ 权限验证：必须登录
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    # ★ 权限验证：验证游戏归属
    verify_game_ownership(db, req.game_id, user)

    try:
        service = ImageService(db)
        image_model = service.regenerate_opening_illustration(
            game_id=req.game_id,
            story_text=req.story_text,
            character_settings=req.character_settings,
            player_name=req.player_name,
            player_image_id=req.player_image_id,
            user_prompt=req.user_prompt,
            current_illustration_id=req.current_illustration_id,
        )

        return OpeningIllustrationResponse(
            image_id=int(image_model.image_id),  # type: ignore[arg-type]
            game_id=int(image_model.game_id),  # type: ignore[arg-type]
            image_url=service.get_image_url(image_model),
            scene_description=image_model.metadata_json.get("scene_description", ""),
            prompt_used=str(image_model.prompt_text),  # type: ignore[arg-type]
            created_at=(image_model.created_at.isoformat() if image_model.created_at else None),
        )

    except ImageContentError as e:
        logger.warning(f"Content inspection failed for opening illustration: {e}")
        raise HTTPException(
            status_code=400,
            detail="重新生成插画时触发了内容安全审核。请尝试使用其他描述方式。",
        )
    except ImageServiceError as e:
        logger.error(f"Opening illustration regeneration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (ValueError, TypeError, KeyError) as e:
        logger.warning(f"Invalid data in regenerate_opening_illustration: {e}")
        raise HTTPException(status_code=400, detail=f"参数错误: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in regenerate_opening_illustration: {e}")
        raise HTTPException(status_code=500, detail=f"重新生成开场插画失败: {e}")


@router.post("/regenerate", response_model=ImageListResponse)
async def regenerate_image(
    req: RegenerateImageRequest,
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    重新生成图片（保持人物一致性）

    基于用户反馈重新生成图片，使用主图作为参考保证人物一致
    """
    logger.info(f"Regenerating image: id={req.image_id}, feedback={req.feedback}")

    # ★ 权限验证：必须登录
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    # ★ 权限验证：验证图片归属（会自动验证游戏归属）
    verify_image_ownership(db, req.image_id, user)  # user 已经是 user_id (int)

    try:
        service = ImageService(db)
        image_models = service.regenerate_image(
            image_id=req.image_id,
            feedback=req.feedback,
            new_description=req.new_description,
        )

        return ImageListResponse(
            images=[
                ImageResponse(
                    image_id=int(img.image_id),  # type: ignore[arg-type]
                    game_id=int(img.game_id),  # type: ignore[arg-type]
                    image_type=str(img.image_type),  # type: ignore[arg-type]
                    entity_name=str(img.entity_name),  # type: ignore[arg-type]
                    entity_key=str(img.entity_key) if img.entity_key else None,  # type: ignore[arg-type]
                    image_url=service.get_image_url(img),
                    prompt_used=str(img.prompt_text),  # type: ignore[arg-type]
                    version=int(img.version),  # type: ignore[arg-type]
                    created_at=img.created_at.isoformat() if img.created_at else None,
                )
                for img in image_models
            ],
            total=len(image_models),
        )

    except ImageContentError as e:
        # ★ 内容审核错误
        logger.warning(f"Content inspection failed in regenerate: {e}")
        raise HTTPException(
            status_code=400,
            detail="您的修改描述可能包含敏感内容，无法生成图片。请尝试使用其他描述方式，如：穿着简洁的衣服、换一套服装等。",
        )
    except ImageServiceError as e:
        logger.error(f"Image regeneration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (ValueError, TypeError, KeyError) as e:
        logger.warning(f"Invalid data in regenerate_image: {e}")
        raise HTTPException(status_code=400, detail=f"参数错误: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in regenerate_image: {e}")
        raise HTTPException(status_code=500, detail=f"图片重新生成失败: {e}")


@router.post("/regenerate-fresh", response_model=ImageListResponse)
async def regenerate_fresh_image(
    req: RegenerateFreshImageRequest,
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    完全重新生成图片（抛弃历史修改）

    使用 DeepSeek 生成优化的 prompt，然后用 qwen-image-max 文生图
    不使用参考图片，完全从头生成
    """
    logger.info(
        f"Fresh regenerating image: id={req.image_id}, use_deepseek={req.use_deepseek_prompt}"
    )

    # ★ 权限验证：必须登录
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    # ★ 权限验证：验证图片归属
    verify_image_ownership(db, req.image_id, user)

    try:
        service = ImageService(db)
        image_models = service.regenerate_fresh_image(
            image_id=req.image_id,
            use_deepseek_prompt=req.use_deepseek_prompt,
        )

        return ImageListResponse(
            images=[
                ImageResponse(
                    image_id=int(img.image_id),  # type: ignore[arg-type]
                    game_id=int(img.game_id),  # type: ignore[arg-type]
                    image_type=str(img.image_type),  # type: ignore[arg-type]
                    entity_name=str(img.entity_name),  # type: ignore[arg-type]
                    entity_key=str(img.entity_key) if img.entity_key else None,  # type: ignore[arg-type]
                    image_url=service.get_image_url(img),
                    prompt_used=str(img.prompt_text),  # type: ignore[arg-type]
                    version=int(img.version),  # type: ignore[arg-type]
                    created_at=img.created_at.isoformat() if img.created_at else None,
                )
                for img in image_models
            ],
            total=len(image_models),
        )

    except ImageContentError as e:
        # ★ 内容审核错误
        logger.warning(f"Content inspection failed in regenerate_fresh: {e}")
        raise HTTPException(
            status_code=400,
            detail="生成图片时触发了内容安全审核。请稍后重试，或尝试完全重新生成。",
        )
    except ImageServiceError as e:
        logger.error(f"Fresh image regeneration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (ValueError, TypeError, KeyError) as e:
        logger.warning(f"Invalid data in regenerate_fresh_image: {e}")
        raise HTTPException(status_code=400, detail=f"参数错误: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in regenerate_fresh_image: {e}")
        raise HTTPException(status_code=500, detail=f"完全重新生成失败: {e}")


# ★ 重要：具体路径必须在动态路径参数之前定义
# /game/{game_id} 和 /file/... 必须在 /{image_id} 之前


@router.get("/game/{game_id}", response_model=ImageListResponse)
async def get_game_images(
    game_id: int,
    image_type: Optional[str] = None,
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """获取游戏的所有图片"""
    # ★ 权限验证：必须登录
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    # ★ 权限验证：验证游戏归属
    verify_game_ownership(db, game_id, user)  # user 已经是 user_id (int)

    service = ImageService(db)
    images = service.get_all_images_for_game(game_id, image_type)

    return ImageListResponse(
        images=[
            ImageResponse(
                image_id=int(img.image_id),  # type: ignore[arg-type]
                game_id=int(img.game_id),  # type: ignore[arg-type]
                image_type=str(img.image_type),  # type: ignore[arg-type]
                entity_name=str(img.entity_name),  # type: ignore[arg-type]
                entity_key=str(img.entity_key) if img.entity_key else None,  # type: ignore[arg-type]
                image_url=service.get_image_url(img),
                prompt_used=str(img.prompt_text),  # type: ignore[arg-type]
                version=int(img.version),  # type: ignore[arg-type]
                created_at=img.created_at.isoformat() if img.created_at else None,
            )
            for img in images
        ],
        total=len(images),
    )


@router.get("/file/{game_id}/{image_type}/{filename}")
async def get_image_file(
    game_id: int,
    image_type: str,
    filename: str,
    db: Session = Depends(get_session),
    user: int = Depends(get_current_user),  # C-02: 添加认证依赖
):
    """
    获取图片文件

    直接返回图片二进制数据，用于前端显示
    """
    try:
        storage_service = ImageStorageService()

        # 构建存储路径
        from pathlib import Path

        # C-01: 路径遍历防护
        base_path = storage_service.local_path.resolve()
        requested_path = (
            storage_service.local_path / str(game_id) / image_type / filename
        ).resolve()
        if not requested_path.is_relative_to(base_path):
            raise HTTPException(status_code=403, detail="Access denied")

        storage_path = str(requested_path)

        # 检查文件是否存在
        if not storage_service.image_exists(storage_path, "local"):
            raise HTTPException(status_code=404, detail="图片不存在")

        # 读取图片数据
        image_data = storage_service.get_image_data(storage_path, "local")

        # 确定内容类型
        content_type = "image/png"
        if filename.endswith(".jpg") or filename.endswith(".jpeg"):
            content_type = "image/jpeg"
        elif filename.endswith(".webp"):
            content_type = "image/webp"
        elif filename.endswith(".gif"):
            content_type = "image/gif"

        return Response(
            content=image_data,
            media_type=content_type,
            headers={
                # ★ 不缓存图片文件，确保重新生成后能立即看到新图片
                # 前端通过 URL 参数 t=timestamp 实现缓存控制
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    except ImageStorageError as e:
        logger.error(f"Failed to get image file: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except FileNotFoundError as e:
        logger.warning(f"Image file not found: {e}")
        raise HTTPException(status_code=404, detail="图片文件不存在")
    except (OSError, IOError) as e:
        logger.error(f"IO error reading image file: {e}")
        raise HTTPException(status_code=500, detail=f"读取图片失败: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in get_image_file: {e}")
        raise HTTPException(status_code=500, detail=f"获取图片失败: {e}")


# ==================== 每轮场景插画 API ====================


@router.get("/scene/{game_id}/{round_number}")
async def get_round_scene_image(
    request: Request,
    game_id: int,
    round_number: int,
    week: int,  # ★ 必需：周数，防止返回错误的图片
    stage: Optional[str] = None,  # ★ 可选：指定阶段 (event/result)
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    获取指定轮次的场景插画

    参数:
    - week: 必需，指定周数。防止返回其他周次的同轮次图片
    - stage: 可选，指定阶段 (event/result)。如果不指定，返回该轮次最新的插画

    如果插画尚未生成，返回 404，前端可以轮询查询
    """
    from src.database.models import SceneImage

    # ★ 调试日志：检查认证信息
    cookie_token = request.cookies.get("auth_token") if request else None
    logger.info(
        f"[get_round_scene_image] game_id={game_id}, user={user}, has_cookie={cookie_token is not None}"
    )

    # ★ 权限验证：必须登录
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    # ★ 权限验证：验证游戏归属
    verify_game_ownership(db, game_id, user)

    # 查询场景插画 - week 现在是必需参数，总是加入过滤条件
    query = db.query(SceneImage).filter(
        SceneImage.game_id == game_id,
        SceneImage.round_number == round_number,
        SceneImage.week == week,  # ★ 必需：总是按周数过滤
    )

    if stage:
        # ★ 指定了阶段，精确查询
        scene_image = query.filter(SceneImage.stage == stage).first()
    else:
        # ★ 未指定阶段，优先返回 result，其次 event
        scene_image = query.order_by(SceneImage.created_at.desc()).first()

    if not scene_image:
        raise HTTPException(status_code=404, detail="该轮次场景插画尚未生成")

    # 构建图片URL
    storage_service = ImageStorageService()
    image_url = storage_service.get_image_url(
        str(scene_image.storage_path), str(scene_image.storage_type)  # type: ignore[arg-type]
    )

    return {
        "scene_id": scene_image.scene_id,
        "game_id": scene_image.game_id,
        "week": scene_image.week,  # ★ 返回 week
        "round_number": scene_image.round_number,
        "stage": scene_image.stage,  # ★ 返回 stage
        "image_url": image_url,
        "scene_description": scene_image.scene_description,
        "referenced_images": scene_image.referenced_images,
        "created_at": (scene_image.created_at.isoformat() if scene_image.created_at else None),
    }


@router.get("/scenes/{game_id}")
async def get_all_round_scene_images(
    request: Request,
    game_id: int,
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    获取游戏的所有场景插画
    """
    from src.database.models import SceneImage

    # ★ 调试日志：检查认证信息
    cookie_token = request.cookies.get("auth_token") if request else None
    logger.info(
        f"[get_all_round_scene_images] game_id={game_id}, user={user}, has_cookie={cookie_token is not None}"
    )

    # ★ 权限验证：必须登录
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    # ★ 权限验证：验证游戏归属
    verify_game_ownership(db, game_id, user)

    # 查询所有场景插画
    scene_images = (
        db.query(SceneImage)
        .filter(SceneImage.game_id == game_id)
        .order_by(SceneImage.week, SceneImage.round_number)
        .all()
    )

    storage_service = ImageStorageService()

    return {
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "week": scene.week,  # ★ 返回 week
                "round_number": scene.round_number,
                "stage": scene.stage,  # ★ 返回 stage
                "image_url": storage_service.get_image_url(
                    str(scene.storage_path), str(scene.storage_type)  # type: ignore[arg-type]
                ),
                "scene_description": scene.scene_description,
                "referenced_images": scene.referenced_images,
                "created_at": (scene.created_at.isoformat() if scene.created_at else None),
            }
            for scene in scene_images
        ],
        "total": len(scene_images),
    }


@router.post("/scene/generate", response_model=RoundSceneResponse)
async def generate_round_scene_image(
    req: GenerateRoundSceneRequest,
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    自动生成每轮场景插画

    流程：
    1. 使用 DeepSeek 分析故事，选择场景
    2. 如果有玩家形象图片，使用图生图
    3. 否则使用文生图
    4. 保存到数据库

    如果该轮次的场景插画已存在，直接返回现有记录。
    """
    # ★ 权限验证：必须登录
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    # ★ 权限验证：验证游戏归属
    verify_game_ownership(db, req.game_id, user)

    service = ImageService(db)

    try:
        scene_model = service.generate_round_scene_image(
            game_id=req.game_id,
            round_number=req.round_number,
            story_text=req.story_text,
            character_settings=req.character_settings,
            player_name=req.player_name,
            player_image_id=req.player_image_id,
            stage=req.stage,  # ★ 传递 stage 参数
            week=req.week,  # ★ 传递 week 参数
        )

        # 构建图片URL
        image_url = service.storage_service.get_image_url(
            str(scene_model.storage_path), str(scene_model.storage_type)  # type: ignore[arg-type]
        )

        return RoundSceneResponse(
            scene_id=int(scene_model.scene_id),  # type: ignore[arg-type]
            game_id=int(scene_model.game_id),  # type: ignore[arg-type]
            week=scene_model.week,  # ★ 返回 week
            round_number=scene_model.round_number,
            stage=scene_model.stage,  # ★ 返回 stage
            image_url=image_url,
            scene_description=scene_model.scene_description or "",
            created_at=(scene_model.created_at.isoformat() if scene_model.created_at else None),
        )

    except ImageContentError as e:
        logger.warning(f"Content inspection failed: {e}")
        raise HTTPException(status_code=400, detail=f"内容审核未通过: {e}")
    except ImageServiceError as e:
        logger.error(f"Image service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (ValueError, TypeError, KeyError) as e:
        logger.warning(f"Invalid data in generate_round_scene_image: {e}")
        raise HTTPException(status_code=400, detail=f"参数错误: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in generate_round_scene_image: {e}")
        raise HTTPException(status_code=500, detail=f"生成场景插画失败: {e}")


@router.post("/scene/regenerate", response_model=RoundSceneResponse)
async def regenerate_round_scene_image(
    req: RegenerateRoundSceneRequest,
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """
    基于用户输入重新生成每轮场景插画

    流程：
    1. 使用 DeepSeek 分析故事，选择场景
    2. 结合用户自定义提示词
    3. 使用当前场景插画作为参考（保持场景一致性）
    4. 如果有玩家形象图片，也作为参考
    5. 保存新图片到数据库
    """
    # ★ 权限验证：必须登录
    if not user:
        raise HTTPException(status_code=401, detail="未登录")

    # ★ 权限验证：验证游戏归属
    verify_game_ownership(db, req.game_id, user)

    service = ImageService(db)

    try:
        scene_model = service.regenerate_round_scene_image(
            game_id=req.game_id,
            round_number=req.round_number,
            story_text=req.story_text,
            character_settings=req.character_settings,
            player_name=req.player_name,
            user_prompt=req.user_prompt,
            current_scene_id=req.current_scene_id,
            player_image_id=req.player_image_id,
        )

        # 构建图片URL
        image_url = service.storage_service.get_image_url(
            str(scene_model.storage_path), str(scene_model.storage_type)  # type: ignore[arg-type]
        )

        # ★ 返回 RoundSceneResponse，包含 week 和 stage
        return RoundSceneResponse(
            scene_id=int(scene_model.scene_id),  # type: ignore[arg-type]
            game_id=int(scene_model.game_id),  # type: ignore[arg-type]
            week=scene_model.week,
            round_number=scene_model.round_number,
            stage=scene_model.stage,
            image_url=image_url,
            scene_description=scene_model.scene_description or "",
            created_at=(scene_model.created_at.isoformat() if scene_model.created_at else None),
        )

    except ImageContentError as e:
        logger.warning(f"Content inspection failed: {e}")
        raise HTTPException(status_code=400, detail=f"内容审核未通过: {e}")
    except ImageServiceError as e:
        logger.error(f"Image service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except (ValueError, TypeError, KeyError) as e:
        logger.warning(f"Invalid data in regenerate_round_scene_image: {e}")
        raise HTTPException(status_code=400, detail=f"参数错误: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error in regenerate_round_scene_image: {e}")
        raise HTTPException(status_code=500, detail=f"重新生成场景插画失败: {e}")


# 动态路径参数放在最后
@router.get("/{image_id}", response_model=ImageResponse)
async def get_image(
    image_id: int,
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """获取图片信息"""
    service = ImageService(db)
    image_model = service.get_image(image_id)

    if not image_model:
        raise HTTPException(status_code=404, detail="图片不存在")

    return ImageResponse(
        image_id=int(image_model.image_id),  # type: ignore[arg-type]
        game_id=int(image_model.game_id),  # type: ignore[arg-type]
        image_type=str(image_model.image_type),  # type: ignore[arg-type]
        entity_name=str(image_model.entity_name),  # type: ignore[arg-type]
        entity_key=str(image_model.entity_key) if image_model.entity_key else None,  # type: ignore[arg-type]
        image_url=service.get_image_url(image_model),
        prompt_used=str(image_model.prompt_text),  # type: ignore[arg-type]
        version=int(image_model.version),  # type: ignore[arg-type]
        created_at=(image_model.created_at.isoformat() if image_model.created_at else None),
    )


@router.delete("/{image_id}", response_model=MessageResponse)
async def delete_image(
    image_id: int,
    db: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """删除图片（软删除，标记为不活跃）"""
    service = ImageService(db)
    image_model = service.get_image(image_id)

    if not image_model:
        raise HTTPException(status_code=404, detail="图片不存在")

    # 软删除
    image_model.is_active = False  # type: ignore[assignment]
    db.commit()

    return MessageResponse(message="图片已删除", success=True)
