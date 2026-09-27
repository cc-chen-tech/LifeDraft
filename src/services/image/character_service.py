"""Character image service - 人物图片生成服务."""

import base64
from copy import deepcopy
import logging
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from config.prompts._helpers import _build_image_era_constraints
from src.ai.image_client import ImageClient
from src.ai.image_exceptions import (ContentInspectionError,
                                     ImageGenerationError,
                                     ImageProviderError)
from src.database.models import Image as ImageModel
from src.database.models import PortraitCandidateBatch, PortraitCandidateSlot
from src.services.image import (ImageContentError, PortraitReferenceUnavailable,
                                ImageProviderServiceError,
                                ImageServiceError)
from src.services.image_storage import ImageStorageService
from src.observability.diagnostics import emit_diagnostic

logger = logging.getLogger(__name__)

CANDIDATE_DIRECTIONS = (
    "外貌方向一：方脸、浓眉、利落的发型；穿符合身份和时代的简洁日常服装",
    "外貌方向二：清瘦长脸、细眉、柔和的发型；穿符合身份和时代的另一种层次搭配",
    "外貌方向三：圆脸、短眉、蓬松的发型；穿符合身份和时代的不同剪裁服装",
)


class CharacterImageService:
    """人物图片生成服务"""

    def __init__(
        self,
        db: Session,
        image_client: Optional[ImageClient] = None,
        storage_service: Optional[ImageStorageService] = None,
    ):
        self.db = db
        self.image_client = image_client or ImageClient()
        self.storage_service = storage_service or ImageStorageService()

    def _save_character_image(
        self, *, game_id: int, name: str, image_data: bytes, prompt: str,
        storage_name: str, entity_key: str, metadata: Dict[str, Any],
        is_active: bool, is_primary: bool,
    ) -> ImageModel:
        """Store one image and add its database record to the current transaction."""
        storage_path, storage_type = self.storage_service.save_image(
            image_data=image_data, game_id=game_id, image_type="character",
            entity_name=storage_name,
        )
        image_model = ImageModel(
            game_id=game_id, image_type="character", entity_name=name,
            entity_key=entity_key, prompt_text=prompt, storage_path=storage_path,
            storage_type=storage_type, metadata_json=metadata, version=1,
            is_active=is_active, is_primary=is_primary, primary_image_id=None,
        )
        self.db.add(image_model)
        return image_model

    def generate_character_candidate(
        self, *, game_id: int, name: str, description: str, era: str,
        character_settings: Dict[str, Any], direction: str, batch_id: int,
        slot_index: int,
    ) -> ImageModel:
        """Generate one independent portrait for a persisted candidate slot."""
        batch = self.db.get(PortraitCandidateBatch, batch_id)
        if batch is None or batch.game_id != game_id:
            raise ImageServiceError("候选形象批次不存在")

        # The shared helper's historical branch asks multiple images to retain
        # one face. Candidate slots deliberately vary faces, while retaining
        # all period, clothing, and prop restrictions.
        era_constraints = _build_image_era_constraints(character_settings, "zh")
        same_face_lines = (
            "人物一致性：", "【人物一致性要求", "同一人物的多张图片必须是同一个人",
            "仅允许服装和姿势变化，面部特征必须绝对保持一致",
        )
        constrained_style = "\n".join(
            line for line in era_constraints.splitlines()
            if not any(cue in line for cue in same_face_lines)
        )
        diagnostic_phase = "generation"
        try:
            images, _ = self.image_client.generate_character_images(
                name=name, description=f"{description}。{direction}", era=era,
                style_hint=constrained_style, num_images=1,
                reference_image_url=None, candidate_mode=True,
            )
            if not images:
                raise ImageServiceError("没有成功生成任何图片")
            diagnostic_phase = "storage"
            image = self._save_character_image(
                game_id=game_id, name=name, image_data=images[0][0],
                prompt=images[0][1], storage_name=f"{name}_{slot_index + 1}",
                entity_key="player_main", is_active=False, is_primary=False,
                metadata={
                    "batch_id": batch_id, "slot_index": slot_index,
                    "appearance_direction": direction,
                    "origin_revision": batch.origin_revision,
                    "characterSettings": deepcopy(character_settings),
                },
            )
            diagnostic_phase = "persistence"
            self.db.commit()
            self.db.refresh(image)
            emit_diagnostic("image_delivery_finished", phase="persistence", outcome="succeeded",
                            game_id=game_id, asset_id=image.image_id, batch_id=batch_id,
                            slot_index=slot_index, persisted=True)
            return image
        except ContentInspectionError as e:
            self.db.rollback()
            raise ImageContentError(str(e), e.original_prompt or "") from e
        except ImageProviderError as e:
            self.db.rollback()
            raise ImageProviderServiceError.from_provider(e) from e
        except ImageGenerationError as e:
            self.db.rollback()
            raise ImageServiceError(f"图像生成失败: {e}") from e
        except Exception as e:
            emit_diagnostic("image_delivery_finished", phase=diagnostic_phase, outcome="failed",
                            error=e, game_id=game_id, batch_id=batch_id, slot_index=slot_index, persisted=False)
            self.db.rollback()
            if isinstance(e, ImageServiceError):
                raise
            raise ImageServiceError(f"生成人物形象失败: {e}") from e

    def _delete_image_files(self, images: List[ImageModel]) -> None:
        """P3-存储修复：删除已停用图片的磁盘/OSS 文件。

        单文件删除失败只记日志，绝不影响重生成主流程。
        """
        for img in images:
            try:
                self.storage_service.delete_image(
                    str(img.storage_path),
                    str(img.storage_type or "local"),
                )
                logger.info(f"Deleted deactivated image file: {img.storage_path}")
            except Exception as exc:
                logger.warning(
                    f"Failed to delete deactivated image file {img.storage_path}: {exc}"
                )

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
        candidate_only: bool = False,
    ) -> List[ImageModel]:
        """
        生成人物全身像图片（保证人物一致性）

        Args:
            game_id: 游戏ID
            name: 人物名称
            description: 人物描述
            era: 时代背景
            entity_key: 实体唯一标识
            style_hint: 风格提示
            metadata: 额外元数据
            num_images: 总图片数量
            feedback: 用户反馈
            reference_image_url: 参考图片URL
            keep_old_active: 是否保持旧图片活跃（用于重新生成时避免闪烁）
            candidate_only: 保存未启用的候选图，等待后台任务确认后切换

        Returns:
            Image模型实例列表
        """
        logger.info(
            f"Generating {num_images} character images: {name} for game {game_id}, feedback: {feedback}, keep_old_active={keep_old_active}"
        )

        # ★ 修复：如果 keep_old_active=True，不在生成前停用旧图片
        # 这样可以避免图片生成过程中的"空窗期"
        if not (keep_old_active or candidate_only):
            # 停用该实体的所有旧图片
            self.db.query(ImageModel).filter(
                ImageModel.game_id == game_id,
                ImageModel.entity_key == (entity_key or f"character_{name}"),
            ).update({"is_active": False})
            self.db.commit()

        diagnostic_phase = "generation"
        try:
            # ★ 生成外貌特征锚点（文本层面的一致性机制）
            character_settings = metadata.get("characterSettings", {}) if metadata else {}
            logger.info(f"Generating appearance anchor for {name}...")
            anchor_data = self.image_client.generate_appearance_anchor(
                name=name,
                description=description,
                era=era,
                character_settings=character_settings,
            )
            logger.info(f"Appearance anchor generated for {name}")

            # ★ 构建并注入图像时代约束（防止科幻/赛博朋克入侵写实风格）
            era_constraints = _build_image_era_constraints(character_settings, "zh")
            combined_style_hint = style_hint or ""
            if era_constraints:
                combined_style_hint = f"{combined_style_hint}\n{era_constraints}".strip()

            # ★ 现代背景传递强反科幻 negative_prompt
            extra_params = None
            era_lower = era.lower()
            if any(kw in era_lower for kw in ("现代", "2024", "2025", "当代", "今天", "modern")):
                extra_params = {
                    "negative_prompt": (
                        "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，"
                        "画面具有AI感。构图混乱。文字模糊，扭曲。半身像，裁剪，截断，无脚。"
                        "赛博朋克，科幻，未来科技，金属质感，电路纹理，全息投影，发光效果，霓虹灯，"
                        "发光眼睛，红眼，蓝光眼睛，发光物体，飞行汽车，悬浮载具，科幻飞行器，"
                        "机械义肢，电子眼，科幻城市，未来都市，奇幻元素，超现实，"
                        "品牌Logo，星巴克，麦当劳，苹果，耐克，阿迪达斯，可口可乐。"
                    )
                }

            images_data, primary_image_url = self.image_client.generate_character_images(
                name=name,
                description=description,
                era=era,
                style_hint=combined_style_hint,
                num_images=num_images,
                reference_image_url=reference_image_url,
                feedback=feedback,
                extra_params=extra_params,
            )

            if not images_data:
                raise ImageServiceError("没有成功生成任何图片")

            image_models = []
            primary_image_model = None

            for idx, (image_data, prompt) in enumerate(images_data):
                is_primary = idx == 0 and not reference_image_url

                # ★ 将锚点数据合并到 metadata_json
                merged_metadata = {
                    **(metadata or {}),
                    "primary_image_url": primary_image_url if is_primary else None,
                    "appearance_anchor": anchor_data,  # ★ 保存外貌锚点
                }

                diagnostic_phase = "storage"
                image_model = self._save_character_image(
                    game_id=game_id, name=name, image_data=image_data,
                    prompt=prompt, storage_name=f"{name}_{idx + 1}",
                    entity_key=entity_key or f"character_{name}",
                    metadata=merged_metadata, is_active=not candidate_only,
                    is_primary=is_primary,
                )
                image_models.append(image_model)

                if is_primary:
                    primary_image_model = image_model

            diagnostic_phase = "persistence"
            self.db.commit()

            if primary_image_model:
                for model in image_models[1:]:
                    model.primary_image_id = primary_image_model.image_id
                self.db.commit()

            for model in image_models:
                self.db.refresh(model)

            logger.info(f"Character images saved: {len(image_models)} images for {name}")
            emit_diagnostic("image_delivery_finished", phase="persistence", outcome="succeeded",
                            game_id=game_id, count=len(image_models), persisted=True)
            return image_models

        except ContentInspectionError as e:
            logger.warning(f"Content inspection failed: {e}")
            raise ImageContentError(str(e), e.original_prompt or "")
        except ImageProviderError as e:
            self.db.rollback()
            raise ImageProviderServiceError.from_provider(e) from e
        except ImageGenerationError as e:
            logger.error(f"Image generation failed: {e}")
            raise ImageServiceError(f"图像生成失败: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in generate_character_image: {e}")
            emit_diagnostic("image_delivery_finished", phase=diagnostic_phase, outcome="failed",
                            error=e, game_id=game_id, persisted=False)
            self.db.rollback()
            raise ImageServiceError(f"生成人物形象失败: {e}")

    def regenerate_image(
        self,
        image_id: int,
        feedback: Optional[str] = None,
        new_description: Optional[str] = None,
        build_description_func: Optional[Callable[[Dict[str, Any]], str]] = None,
        extract_era_func: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None,
        defer_activation: bool = False,
    ) -> List[ImageModel]:
        """
        重新生成图片（保持人物一致性）

        Args:
            image_id: 原图片ID
            feedback: 用户修改意见
            new_description: 新的描述
            build_description_func: 构建描述的函数
            extract_era_func: 提取时代的函数

        Returns:
            新的Image模型实例列表
        """
        logger.info(f"Regenerating image: {image_id}, feedback: {feedback}")

        original = self.db.query(ImageModel).filter(ImageModel.image_id == image_id).first()

        if not original:
            raise ImageServiceError(f"图片不存在: {image_id}")

        metadata: Dict[str, Any] = original.metadata_json or {}  # type: ignore[assignment]
        char_settings = metadata.get("characterSettings", {})

        if new_description:
            base_description = new_description
        elif build_description_func:
            base_description = build_description_func(char_settings)
        else:
            base_description = "一个普通人"

        era = "现代"
        if extract_era_func:
            era = extract_era_func(char_settings) or "现代"

        requires_reference = bool(metadata.get("batch_id")) or self.db.query(
            PortraitCandidateSlot
        ).filter_by(image_id=image_id).first() is not None
        reference_url = None
        try:
            image_data = self._get_image_data(original)
            if requires_reference and not image_data:
                raise ImageServiceError("参考图片为空")
            ext = original.storage_path.rsplit(".", 1)[-1].lower()
            mime_type = "image/png" if ext == "png" else "image/jpeg"
            base64_data = base64.b64encode(image_data).decode("utf-8")
            reference_url = f"data:{mime_type};base64,{base64_data}"
            logger.info(f"Using current image as reference (base64, {len(image_data)} bytes)")
        except Exception as e:
            if requires_reference:
                raise PortraitReferenceUnavailable() from e
            logger.warning(
                f"Failed to convert image to base64: {e}, will generate without reference"
            )

        try:
            # ★ 修复：使用 keep_old_active=True 避免生成过程中的"空窗期"
            # 旧图片保持活跃直到新图片生成完成
            new_images = self.generate_character_image(
                game_id=int(original.game_id),  # type: ignore[arg-type]
                name=str(original.entity_name),  # type: ignore[arg-type]
                description=base_description,
                era=era,
                entity_key=str(original.entity_key) if original.entity_key else None,  # type: ignore[arg-type]
                metadata=metadata,
                num_images=1,
                feedback=feedback,
                reference_image_url=reference_url,
                keep_old_active=True,
                candidate_only=defer_activation,
            )

            if defer_activation:
                return new_images

            # ★ 新图片生成成功后，停用旧图片
            new_image_ids = [img.image_id for img in new_images]
            if original.entity_key:
                old_images = (
                    self.db.query(ImageModel)
                    .filter(
                        ImageModel.game_id == original.game_id,
                        ImageModel.entity_key == original.entity_key,
                        ImageModel.image_id.notin_(new_image_ids),
                    )
                    .all()
                )
                self.db.query(ImageModel).filter(
                    ImageModel.game_id == original.game_id,
                    ImageModel.entity_key == original.entity_key,
                    ImageModel.image_id.notin_(new_image_ids),
                ).update({"is_active": False})
            else:
                old_images = (
                    self.db.query(ImageModel)
                    .filter(
                        ImageModel.game_id == original.game_id,
                        ImageModel.image_type == original.image_type,
                        ImageModel.entity_name == original.entity_name,
                        ImageModel.image_id.notin_(new_image_ids),
                    )
                    .all()
                )
                self.db.query(ImageModel).filter(
                    ImageModel.game_id == original.game_id,
                    ImageModel.image_type == original.image_type,
                    ImageModel.entity_name == original.entity_name,
                    ImageModel.image_id.notin_(new_image_ids),
                ).update({"is_active": False})
            self.db.commit()

            # P3-存储修复：停用的旧图片不再被引用，删除其磁盘/OSS 文件。
            self._delete_image_files(old_images)

            logger.info(f"Images regenerated: {len(new_images)} new images, old images deactivated")
            return new_images

        except ImageContentError:
            raise
        except ImageProviderServiceError:
            raise
        except Exception as e:
            logger.error(f"Failed to regenerate image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"重新生成失败: {e}")

    def regenerate_fresh_image(
        self,
        image_id: int,
        build_description_func: Optional[Callable[[Dict[str, Any]], str]] = None,
        extract_era_func: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None,
        use_deepseek_prompt: bool = True,
        defer_activation: bool = False,
    ) -> List[ImageModel]:
        """
        完全重新生成图片（抛弃历史修改）

        Args:
            image_id: 原图片ID
            build_description_func: 构建描述的函数
            extract_era_func: 提取时代的函数
            use_deepseek_prompt: 是否使用 DeepSeek 生成优化的 prompt

        Returns:
            新的Image模型实例列表
        """
        logger.info(f"Fresh regenerating image: {image_id}, use_deepseek={use_deepseek_prompt}")

        original = self.db.query(ImageModel).filter(ImageModel.image_id == image_id).first()

        if not original:
            raise ImageServiceError(f"图片不存在: {image_id}")

        metadata: Dict[str, Any] = original.metadata_json or {}  # type: ignore[assignment]
        char_settings = metadata.get("characterSettings", {})

        character_info = {
            "name": original.entity_name,
            "age": char_settings.get("age", 25),
            "gender": char_settings.get("gender", "女"),
            "era": "现代",
            "appearance": char_settings.get("appearance", ""),
            "personality": char_settings.get("personality", ""),
            "occupation": char_settings.get("occupation", ""),
            "background": char_settings.get("background", ""),
        }

        if extract_era_func:
            character_info["era"] = extract_era_func(char_settings) or "现代"

        if use_deepseek_prompt:
            try:
                prompt = self.image_client.generate_image_prompt_with_deepseek(character_info)
                logger.debug(f"DeepSeek generated prompt: {prompt[:100]}...")
            except Exception as e:
                logger.warning(f"DeepSeek prompt generation failed, using fallback: {e}")
                prompt = (
                    build_description_func(char_settings)
                    if build_description_func
                    else "一个普通人"
                )
        else:
            prompt = (
                build_description_func(char_settings) if build_description_func else "一个普通人"
            )

        era = character_info["era"]

        try:
            new_images = self.generate_character_image(
                game_id=int(original.game_id),  # type: ignore[arg-type]
                name=str(original.entity_name),  # type: ignore[arg-type]
                description=prompt,
                era=era,
                entity_key=str(original.entity_key) if original.entity_key else None,  # type: ignore[arg-type]
                metadata=metadata,
                num_images=1,
                feedback=None,
                reference_image_url=None,
                keep_old_active=True,
                candidate_only=defer_activation,
            )

            if defer_activation:
                return new_images

            new_image_ids = [img.image_id for img in new_images]
            if original.entity_key:
                old_query = self.db.query(ImageModel).filter(
                    ImageModel.game_id == original.game_id,
                    ImageModel.entity_key == original.entity_key,
                    ImageModel.image_id.notin_(new_image_ids),
                )
            else:
                old_query = self.db.query(ImageModel).filter(
                    ImageModel.game_id == original.game_id,
                    ImageModel.image_type == original.image_type,
                    ImageModel.entity_name == original.entity_name,
                    ImageModel.image_id.notin_(new_image_ids),
                )
            old_images = old_query.all()
            old_query.update({"is_active": False})
            self.db.commit()
            self._delete_image_files(old_images)

            logger.info(f"Fresh images regenerated: {len(new_images)} new images")
            return new_images

        except ImageProviderServiceError:
            raise
        except Exception as e:
            logger.error(f"Failed to fresh regenerate image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"完全重新生成失败: {e}")

    def _get_image_data(self, image_model: ImageModel) -> bytes:
        """获取图片二进制数据"""
        return self.storage_service.get_image_data(
            str(image_model.storage_path),  # type: ignore[arg-type]
            str(image_model.storage_type) if image_model.storage_type else None,  # type: ignore[arg-type]
        )
