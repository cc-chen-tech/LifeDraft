"""Image service - 图像生成调度服务.

协调图像生成、存储和数据库记录。
重构版本：委托给专门的子服务处理。
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.ai.image_client import ImageClient
from src.ai.image_exceptions import ContentInspectionError, ImageGenerationError
from src.database.models import Image as ImageModel
from src.services.image.character_service import CharacterImageService
from src.services.image.scene_service import SceneImageService
from src.services.image_storage import ImageStorageService

logger = logging.getLogger(__name__)

# C-05: 模块级线程池，替代裸线程使用
_image_thread_pool = ThreadPoolExecutor(max_workers=10, thread_name_prefix="image-gen")


def get_image_thread_pool() -> ThreadPoolExecutor:
    """获取共享的图片生成线程池"""
    return _image_thread_pool


def shutdown_image_thread_pool(wait: bool = True) -> None:
    """关闭线程池（用于应用退出时清理）"""
    global _image_thread_pool
    _image_thread_pool.shutdown(wait=wait)
    _image_thread_pool = ThreadPoolExecutor(max_workers=10, thread_name_prefix="image-gen")


class ImageServiceError(Exception):
    """图像服务错误"""


class ImageContentError(ImageServiceError):
    """图像内容审核错误"""

    def __init__(self, message: str, original_prompt: Optional[str] = None):
        super().__init__(message)
        self.original_prompt = original_prompt


class ImageService:
    """图像生成调度服务

    整合各个子服务，提供统一的图像生成接口。
    """

    def __init__(
        self,
        db: Session,
        image_client: Optional[ImageClient] = None,
        storage_service: Optional[ImageStorageService] = None,
    ):
        """
        初始化图像服务

        Args:
            db: 数据库会话
            image_client: 图像生成客户端
            storage_service: 存储服务
        """
        self.db = db
        self.image_client = image_client or ImageClient()
        self.storage_service = storage_service or ImageStorageService()

        # 初始化子服务
        self._character_service = CharacterImageService(
            db=db,
            image_client=self.image_client,
            storage_service=self.storage_service,
        )
        self._scene_service = SceneImageService(
            db=db,
            image_client=self.image_client,
            storage_service=self.storage_service,
        )

    # ==================== 人物图片方法 ====================

    def generate_character_image(
        self,
        game_id: int,
        name: str,
        description: str,
        era: str = "现代",
        entity_key: Optional[str] = None,
        style_hint: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        num_images: int = 1,
        feedback: Optional[str] = None,
        reference_image_url: Optional[str] = None,
        keep_old_active: bool = False,
    ) -> List[ImageModel]:
        """生成人物全身像图片"""
        return self._character_service.generate_character_image(
            game_id=game_id,
            name=name,
            description=description,
            era=era,
            entity_key=entity_key,
            style_hint=style_hint,
            metadata=metadata,
            num_images=num_images,
            feedback=feedback,
            reference_image_url=reference_image_url,
            keep_old_active=keep_old_active,
        )

    def regenerate_image(
        self,
        image_id: int,
        feedback: Optional[str] = None,
        new_description: Optional[str] = None,
    ) -> List[ImageModel]:
        """重新生成图片（保持人物一致性）"""
        return self._character_service.regenerate_image(
            image_id=image_id,
            feedback=feedback,
            new_description=new_description,
            build_description_func=self._build_description_from_settings,
            extract_era_func=self._extract_era_from_settings,
        )

    def regenerate_fresh_image(
        self,
        image_id: int,
        use_deepseek_prompt: bool = True,
    ) -> List[ImageModel]:
        """完全重新生成图片（抛弃历史修改）"""
        return self._character_service.regenerate_fresh_image(
            image_id=image_id,
            use_deepseek_prompt=use_deepseek_prompt,
            build_description_func=self._build_description_from_settings,
            extract_era_func=self._extract_era_from_settings,
        )

    # ==================== 场景插画方法 ====================

    def generate_round_scene_image(
        self,
        game_id: int,
        round_number: int,
        story_text: str,
        character_settings: Dict[str, Any],
        player_name: str,
        player_image_id: Optional[int] = None,
        stage: str = "result",
        week: Optional[int] = None,
    ):
        """自动生成每轮场景插画"""
        return self._scene_service.generate_round_scene_image(
            game_id=game_id,
            round_number=round_number,
            story_text=story_text,
            character_settings=character_settings,
            player_name=player_name,
            player_image_id=player_image_id,
            stage=stage,
            week=week,
            get_week_func=self._get_current_week_from_db,  # type: ignore[arg-type]
            get_player_image_func=self._get_player_image_base64,
        )

    def generate_opening_illustration(
        self,
        game_id: int,
        story_text: str,
        character_settings: Dict[str, Any],
        player_name: str,
        player_image_id: Optional[int] = None,
    ) -> ImageModel:
        """生成开场故事插画"""
        return self._scene_service.generate_opening_illustration(
            game_id=game_id,
            story_text=story_text,
            character_settings=character_settings,
            player_name=player_name,
            player_image_id=player_image_id,
            get_player_image_func=self._get_player_image_base64,
        )

    def regenerate_opening_illustration(
        self,
        game_id: int,
        story_text: str,
        character_settings: Dict[str, Any],
        player_name: str,
        player_image_id: Optional[int],
        user_prompt: str,
        current_illustration_id: int,
    ) -> ImageModel:
        """基于用户输入重新生成开场故事插画"""
        return self._scene_service.regenerate_opening_illustration(
            game_id=game_id,
            story_text=story_text,
            character_settings=character_settings,
            player_name=player_name,
            player_image_id=player_image_id,
            user_prompt=user_prompt,
            current_illustration_id=current_illustration_id,
            get_image_data_func=self.get_image_data,
            get_player_image_func=self._get_player_image_base64,
        )

    def regenerate_round_scene_image(
        self,
        game_id: int,
        round_number: int,
        story_text: str,
        character_settings: Dict[str, Any],
        player_name: str,
        user_prompt: str,
        current_scene_id: int,
        player_image_id: Optional[int] = None,
    ) -> ImageModel:
        """基于用户输入重新生成每轮场景插画"""
        from src.database.models import SceneImage

        logger.info(f"Regenerating round {round_number} scene for game {game_id}")
        logger.debug(f"User prompt: {user_prompt[:100]}...")

        # 从数据库获取 character_settings
        db_character_settings, db_player_name = self._get_character_settings_from_db(game_id)
        effective_character_settings = db_character_settings or character_settings
        effective_player_name = db_player_name or player_name

        char_info = self._build_char_info(effective_character_settings, effective_player_name)

        try:
            # 分析故事选择场景
            scene_desc, illustration_prompt = self.image_client.analyze_story_for_illustration(
                story_text=story_text[:2000],
                character_info=char_info,
            )

            combined_prompt = f"""{user_prompt}

场景：{scene_desc}
{illustration_prompt}"""

            logger.debug(f"Combined prompt: {combined_prompt[:100]}...")

            # 获取参考图片
            reference_urls = []
            referenced_image_ids = []

            # 获取当前场景插画作为参考
            current_scene = (
                self.db.query(SceneImage).filter(SceneImage.scene_id == current_scene_id).first()
            )

            if current_scene:
                try:
                    image_data = self.storage_service.get_image_data(
                        str(current_scene.storage_path),  # type: ignore[arg-type]
                        str(current_scene.storage_type) if current_scene.storage_type else None,  # type: ignore[arg-type]
                    )
                    if image_data:
                        import base64

                        ext = current_scene.storage_path.rsplit(".", 1)[-1].lower()
                        mime_type = "image/png" if ext == "png" else "image/jpeg"
                        base64_data = base64.b64encode(image_data).decode("utf-8")
                        reference_urls.append(f"data:{mime_type};base64,{base64_data}")
                        referenced_image_ids.append(current_scene_id)
                        logger.info(
                            f"Using current scene as reference (base64, {len(image_data)} bytes)"
                        )
                except (OSError, IOError) as e:
                    logger.warning(f"IO error getting current scene: {e}")
                except Exception as e:
                    logger.exception(f"Unexpected error getting current scene: {e}")

            # 获取玩家形象图片
            if player_image_id:
                ref_url, img_id = self._get_player_image_base64(game_id, player_image_id)
                if ref_url:
                    reference_urls.append(ref_url)
                    if img_id:
                        referenced_image_ids.append(img_id)

            # 生成场景插画
            if reference_urls:
                edit_prompt = f"""基于参考图片，重新绘制以下场景：
{scene_desc}
{combined_prompt}
保持人物的外貌特征和服装不变，融入新的场景环境中。"""

                results = self.image_client.edit_image(
                    reference_image=reference_urls[0],
                    prompt=edit_prompt,
                    size="1664*928",
                    num_images=1,
                )

                if results:
                    image_data, _ = results[0]
                else:
                    raise ImageGenerationError("Failed to generate scene image with reference")
            else:
                image_data, _ = self.image_client.generate_image(
                    prompt=combined_prompt,
                    size="1664*928",
                    extra_params={"prompt_extend": True},
                )

            # 保存图片 - ★ 传递 week 和 stage 参数，确保文件名格式一致
            # ★ 使用当前场景的 week 和 stage，保持一致性
            current_week = (
                current_scene.week if current_scene else self._get_current_week_from_db(game_id)
            )
            current_stage = current_scene.stage if current_scene else "result"

            storage_path, storage_type = self.storage_service.save_image(
                image_data=image_data,
                game_id=game_id,
                image_type="round_scene",
                entity_name=f"{effective_player_name}_round_{round_number}",
                week=int(current_week) if current_week else None,  # type: ignore[arg-type]
                round_number=round_number,
                stage=str(current_stage) if current_stage else None,  # type: ignore[arg-type]
            )

            # 更新或创建 SceneImage 记录
            if current_scene:
                from datetime import datetime

                # ★ 删除旧图片文件，避免磁盘空间浪费
                old_storage_path = current_scene.storage_path
                if old_storage_path:
                    try:
                        self.storage_service.delete_image(
                            str(old_storage_path),  # type: ignore[arg-type]
                            str(current_scene.storage_type) if current_scene.storage_type else None,  # type: ignore[arg-type]
                        )
                        logger.info(f"Deleted old scene image: {old_storage_path}")
                    except (OSError, IOError) as e:
                        logger.warning(f"IO error deleting old scene image: {e}")
                    except Exception as e:
                        logger.exception(f"Unexpected error deleting old scene image: {e}")

                current_scene.scene_description = scene_desc  # type: ignore[assignment]
                current_scene.final_prompt = combined_prompt  # type: ignore[assignment]
                current_scene.storage_path = storage_path  # type: ignore[assignment]
                current_scene.storage_type = storage_type  # type: ignore[assignment]
                current_scene.referenced_images = referenced_image_ids  # type: ignore[assignment]
                current_scene.importance_score = "high"  # type: ignore[assignment]
                current_scene.created_at = datetime.utcnow()  # type: ignore[assignment]  # ★ 更新时间戳，用于缓存破坏
                self.db.commit()
                self.db.refresh(current_scene)
                logger.info(
                    f"Round scene updated: scene_id={current_scene.scene_id}, new_path={storage_path}"
                )

                # ★ 返回 SceneImage 对象
                return current_scene
            else:
                # ★ 获取当前 week
                week = self._get_current_week_from_db(game_id)

                new_scene = SceneImage(
                    game_id=game_id,
                    week=week,
                    round_number=round_number,
                    scene_description=scene_desc,
                    final_prompt=combined_prompt,
                    storage_path=storage_path,
                    storage_type=storage_type,
                    referenced_images=referenced_image_ids,
                    importance_score="high",
                )
                self.db.add(new_scene)
                self.db.commit()
                self.db.refresh(new_scene)
                logger.info(f"Round scene created: scene_id={new_scene.scene_id}")

                # ★ 返回 SceneImage 对象
                return new_scene

        except ContentInspectionError as e:
            logger.warning(f"Content inspection failed for round scene: {e}")
            raise ImageContentError(str(e), e.original_prompt)
        except ImageGenerationError as e:
            logger.error(f"Image generation failed: {e}")
            raise ImageServiceError(f"场景插画重新生成失败: {e}")
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Invalid data in regenerate_round_scene_image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"重新生成场景插画失败（数据错误）: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error in regenerate_round_scene_image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"重新生成场景插画失败: {e}")

    # ==================== 查询方法 ====================

    def get_image(self, image_id: int) -> Optional[ImageModel]:
        """获取图片记录"""
        return self.db.query(ImageModel).filter(ImageModel.image_id == image_id).first()

    def get_active_image(
        self,
        game_id: int,
        image_type: str,
        entity_name: str,
    ) -> Optional[ImageModel]:
        """获取活跃的图片记录"""
        return (
            self.db.query(ImageModel)
            .filter(
                ImageModel.game_id == game_id,
                ImageModel.image_type == image_type,
                ImageModel.entity_name == entity_name,
                ImageModel.is_active == True,  # noqa: E712
            )
            .order_by(ImageModel.version.desc())
            .first()
        )

    def get_all_images_for_game(
        self,
        game_id: int,
        image_type: Optional[str] = None,
    ) -> List[ImageModel]:
        """获取游戏的所有图片"""
        query = self.db.query(ImageModel).filter(
            ImageModel.game_id == game_id,
            ImageModel.is_active == True,  # noqa: E712
        )

        if image_type:
            query = query.filter(ImageModel.image_type == image_type)

        return query.all()

    def get_image_url(self, image_model: ImageModel) -> str:
        """获取图片访问URL"""
        return self.storage_service.get_image_url(
            str(image_model.storage_path),  # type: ignore[arg-type]
            str(image_model.storage_type) if image_model.storage_type else None,  # type: ignore[arg-type]
        )

    def get_image_data(self, image_model: ImageModel) -> bytes:
        """获取图片二进制数据"""
        return self.storage_service.get_image_data(
            str(image_model.storage_path),  # type: ignore[arg-type]
            str(image_model.storage_type) if image_model.storage_type else None,  # type: ignore[arg-type]
        )

    # ==================== 简单生成方法 ====================

    def generate_location_image(
        self,
        game_id: int,
        name: str,
        description: str,
        era: str = "现代",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ImageModel:
        """生成地点图片"""
        logger.info(f"Generating location image: {name} for game {game_id}")

        try:
            image_data, prompt = self.image_client.generate_location_image(
                name=name,
                description=description,
                era=era,
            )

            storage_path, storage_type = self.storage_service.save_image(
                image_data=image_data,
                game_id=game_id,
                image_type="location",
                entity_name=name,
            )

            image_model = ImageModel(
                game_id=game_id,
                image_type="location",
                entity_name=name,
                entity_key=f"location_{name}",
                prompt_text=prompt,
                storage_path=storage_path,
                storage_type=storage_type,
                metadata_json=metadata,
            )

            self.db.add(image_model)
            self.db.commit()
            self.db.refresh(image_model)

            return image_model

        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Invalid data in generate_location_image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"生成地点图片失败（数据错误）: {e}")
        except Exception as e:
            logger.exception(f"Failed to generate location image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"生成地点图片失败: {e}")

    def generate_item_image(
        self,
        game_id: int,
        name: str,
        description: str,
        era: str = "现代",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ImageModel:
        """生成物品图片"""
        logger.info(f"Generating item image: {name} for game {game_id}")

        try:
            image_data, prompt = self.image_client.generate_item_image(
                name=name,
                description=description,
                era=era,
            )

            storage_path, storage_type = self.storage_service.save_image(
                image_data=image_data,
                game_id=game_id,
                image_type="item",
                entity_name=name,
            )

            image_model = ImageModel(
                game_id=game_id,
                image_type="item",
                entity_name=name,
                entity_key=f"item_{name}",
                prompt_text=prompt,
                storage_path=storage_path,
                storage_type=storage_type,
                metadata_json=metadata,
            )

            self.db.add(image_model)
            self.db.commit()
            self.db.refresh(image_model)

            return image_model

        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Invalid data in generate_item_image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"生成物品图片失败（数据错误）: {e}")
        except Exception as e:
            logger.exception(f"Failed to generate item image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"生成物品图片失败: {e}")

    # ==================== 辅助方法 ====================

    def _extract_description_from_prompt(self, prompt: str) -> str:
        """从prompt中提取描述"""
        if "人物描述：" in prompt:
            start = prompt.find("人物描述：") + 5
            end = prompt.find("。", start)
            if end > start:
                return prompt[start:end]
        return prompt

    def _extract_era_from_metadata(self, metadata: Optional[Dict[str, Any]]) -> str:
        """从元数据中提取时代"""
        if metadata and "era" in metadata:
            return metadata["era"]  # type: ignore[no-any-return]
        return "现代"

    def _build_description_from_settings(self, char_settings: Dict[str, Any]) -> str:
        """从角色设定构建人物描述"""
        parts = []

        age = char_settings.get("age")
        if age:
            if isinstance(age, dict):
                if age.get("age"):
                    parts.append(f"{age['age']}岁")
                elif age.get("age_range"):
                    parts.append(str(age["age_range"]))
            elif isinstance(age, (int, float)):
                parts.append(f"{age}岁")

        gender = char_settings.get("gender")
        if gender:
            if isinstance(gender, dict) and gender.get("gender"):
                parts.append(str(gender["gender"]))
            elif isinstance(gender, str):
                parts.append(gender)

        world = char_settings.get("world")
        if world and isinstance(world, dict):
            if world.get("cultural_context"):
                parts.append(str(world["cultural_context"]))
            if world.get("special_features"):
                parts.append(str(world["special_features"]))

        return "，".join(parts) if parts else "一个普通人"

    def _extract_era_from_settings(self, char_settings: Dict[str, Any]) -> Optional[str]:
        """从角色设定中提取时代名称"""
        era = char_settings.get("era")
        if era:
            if isinstance(era, dict):
                era_name = era.get("era_name")
                if era_name and era_name.strip():
                    return era_name.strip()  # type: ignore[no-any-return]

                era_desc = era.get("era_description")
                if era_desc and era_desc.strip():
                    desc = era_desc.strip()
                    for sep in ["。", "，", ",", "."]:
                        if sep in desc:
                            desc = desc.split(sep)[0]
                            break
                    if len(desc) > 30:
                        desc = desc[:30]
                    return desc  # type: ignore[no-any-return]

                return None
            elif isinstance(era, str):
                if len(era) > 30:
                    return era[:30]
                return era
        return None

    def _get_current_week_from_db(self, game_id: int) -> int:
        """从数据库获取游戏当前的周数"""
        from src.database.models import Game, GameState

        try:
            game_state = (
                self.db.query(GameState)
                .filter(GameState.game_id == game_id)
                .order_by(GameState.state_id.desc())
                .first()
            )

            if game_state and game_state.state_json:
                week = game_state.state_json.get("week")
                if week is not None:
                    return week  # type: ignore[no-any-return]

            game = self.db.query(Game).filter(Game.game_id == game_id).first()
            if game and game.initial_state:
                week = game.initial_state.get("week")
                if week is not None:
                    return week  # type: ignore[no-any-return]
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Invalid data getting current week from database: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error getting current week from database: {e}")

        return 0

    def _build_char_info(
        self, character_settings: Dict[str, Any], player_name: str
    ) -> Dict[str, Any]:
        """构建角色信息字典"""
        char_info = {
            "name": player_name,
            "era": self._extract_era_from_settings(character_settings) or "现代",
        }

        gender = character_settings.get("gender")
        if gender:
            if isinstance(gender, dict):
                char_info["gender"] = gender.get("gender", "")
            elif isinstance(gender, str):
                char_info["gender"] = gender

        age = character_settings.get("age")
        if age:
            if isinstance(age, dict):
                char_info["age"] = age.get("age", "")
            elif isinstance(age, (int, float)):
                char_info["age"] = str(age)

        return char_info

    def _get_player_image_base64(self, game_id: int, player_image_id: Optional[int]) -> tuple:
        """获取玩家形象的 Base64 编码"""
        import base64

        player_image = None
        if player_image_id:
            player_image = (
                self.db.query(ImageModel)
                .filter(
                    ImageModel.image_id == player_image_id,
                    ImageModel.game_id == game_id,
                )
                .first()
            )
            if not player_image:
                logger.warning(
                    f"player_image_id={player_image_id} does not belong to game_id={game_id}"
                )

        if not player_image:
            player_image = (
                self.db.query(ImageModel)
                .filter(
                    ImageModel.game_id == game_id,
                    ImageModel.image_type == "character",
                    ImageModel.is_primary == True,  # noqa: E712
                )
                .order_by(ImageModel.image_id.desc())
                .first()
            )
            if player_image:
                logger.info(f"Auto-selected primary player image: {player_image.image_id}")

        if player_image:
            try:
                image_data = self.get_image_data(player_image)
                ext = player_image.storage_path.rsplit(".", 1)[-1].lower()
                mime_type = "image/png" if ext == "png" else "image/jpeg"
                base64_data = base64.b64encode(image_data).decode("utf-8")
                return f"data:{mime_type};base64,{base64_data}", player_image.image_id
            except (OSError, IOError) as e:
                logger.warning(f"IO error getting player image: {e}")
            except Exception as e:
                logger.exception(f"Unexpected error getting player image: {e}")

        return None, None

    def _get_character_settings_from_db(self, game_id: int) -> tuple:
        """从数据库获取角色设定"""
        from src.database.models import Game, GameState

        db_character_settings = None
        db_player_name = None

        try:
            game_state = (
                self.db.query(GameState)
                .filter(GameState.game_id == game_id)
                .order_by(GameState.state_id.desc())
                .first()
            )

            if game_state and game_state.state_json:
                db_character_settings = game_state.state_json.get("character_settings")
                db_player_name = game_state.state_json.get("player_name")
                logger.info(
                    f"Loaded character_settings from GameState (state_id={game_state.state_id})"
                )

            if not db_character_settings:
                game = self.db.query(Game).filter(Game.game_id == game_id).first()
                if game and game.initial_state:
                    db_character_settings = game.initial_state.get("character_settings")
                    db_player_name = game.initial_state.get("player_name")
                    logger.info(
                        f"Loaded character_settings from Game.initial_state (game_id={game_id})"
                    )
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Invalid data loading character_settings from database: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error loading character_settings from database: {e}")

        return db_character_settings, db_player_name
