"""Character image service - 人物图片生成服务."""
import logging
import base64
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from src.ai.image_client import ImageClient, ImageGenerationError, ContentInspectionError
from src.services.image_storage import ImageStorageService
from src.database.models import Image as ImageModel
from src.services.image import ImageServiceError, ImageContentError

logger = logging.getLogger(__name__)


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

        Returns:
            Image模型实例列表
        """
        logger.info(f"Generating {num_images} character images: {name} for game {game_id}, feedback: {feedback}")

        # 停用该实体的所有旧图片
        self.db.query(ImageModel).filter(
            ImageModel.game_id == game_id,
            ImageModel.entity_key == (entity_key or f"character_{name}")
        ).update({"is_active": False})
        self.db.commit()

        try:
            images_data, primary_image_url = self.image_client.generate_character_images(
                name=name,
                description=description,
                era=era,
                style_hint=style_hint,
                num_images=num_images,
                reference_image_url=reference_image_url,
                feedback=feedback,
            )

            if not images_data:
                raise ImageServiceError("没有成功生成任何图片")

            image_models = []
            primary_image_model = None

            for idx, (image_data, prompt) in enumerate(images_data):
                storage_path, storage_type = self.storage_service.save_image(
                    image_data=image_data,
                    game_id=game_id,
                    image_type="character",
                    entity_name=f"{name}_{idx + 1}",
                )

                is_primary = (idx == 0 and not reference_image_url)

                image_model = ImageModel(
                    game_id=game_id,
                    image_type="character",
                    entity_name=name,
                    entity_key=entity_key or f"character_{name}",
                    prompt_text=prompt,
                    storage_path=storage_path,
                    storage_type=storage_type,
                    metadata_json={
                        **(metadata or {}),
                        "primary_image_url": primary_image_url if is_primary else None,
                    },
                    version=1,
                    is_active=True,
                    is_primary=is_primary,
                    primary_image_id=None,
                )

                self.db.add(image_model)
                image_models.append(image_model)

                if is_primary:
                    primary_image_model = image_model

            self.db.commit()

            if primary_image_model:
                for model in image_models[1:]:
                    model.primary_image_id = primary_image_model.image_id
                self.db.commit()

            for model in image_models:
                self.db.refresh(model)

            logger.info(f"Character images saved: {len(image_models)} images for {name}")
            return image_models

        except ContentInspectionError as e:
            logger.warning(f"Content inspection failed: {e}")
            raise ImageContentError(str(e), e.original_prompt)
        except ImageGenerationError as e:
            logger.error(f"Image generation failed: {e}")
            raise ImageServiceError(f"图像生成失败: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in generate_character_image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"生成人物形象失败: {e}")

    def regenerate_image(
        self,
        image_id: int,
        feedback: Optional[str] = None,
        new_description: Optional[str] = None,
        build_description_func: callable = None,
        extract_era_func: callable = None,
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

        original = self.db.query(ImageModel).filter(
            ImageModel.image_id == image_id
        ).first()

        if not original:
            raise ImageServiceError(f"图片不存在: {image_id}")

        self.db.query(ImageModel).filter(
            ImageModel.game_id == original.game_id,
            ImageModel.entity_key == original.entity_key
        ).update({"is_active": False})
        self.db.commit()

        metadata = original.metadata_json or {}
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

        reference_url = None
        try:
            image_data = self._get_image_data(original)
            ext = original.storage_path.rsplit('.', 1)[-1].lower()
            mime_type = 'image/png' if ext == 'png' else 'image/jpeg'
            base64_data = base64.b64encode(image_data).decode('utf-8')
            reference_url = f"data:{mime_type};base64,{base64_data}"
            logger.info(f"Using current image as reference (base64, {len(image_data)} bytes)")
        except Exception as e:
            logger.warning(f"Failed to convert image to base64: {e}, will generate without reference")

        try:
            new_images = self.generate_character_image(
                game_id=original.game_id,
                name=original.entity_name,
                description=base_description,
                era=era,
                entity_key=original.entity_key,
                metadata=metadata,
                num_images=1,
                feedback=feedback,
                reference_image_url=reference_url,
            )

            logger.info(f"Images regenerated: {len(new_images)} new images")
            return new_images

        except ImageContentError:
            raise
        except Exception as e:
            logger.error(f"Failed to regenerate image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"重新生成失败: {e}")

    def regenerate_fresh_image(
        self,
        image_id: int,
        build_description_func: callable = None,
        extract_era_func: callable = None,
        use_deepseek_prompt: bool = True,
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

        original = self.db.query(ImageModel).filter(
            ImageModel.image_id == image_id
        ).first()

        if not original:
            raise ImageServiceError(f"图片不存在: {image_id}")

        self.db.query(ImageModel).filter(
            ImageModel.game_id == original.game_id,
            ImageModel.entity_key == original.entity_key
        ).update({"is_active": False})
        self.db.commit()

        metadata = original.metadata_json or {}
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
                prompt = build_description_func(char_settings) if build_description_func else "一个普通人"
        else:
            prompt = build_description_func(char_settings) if build_description_func else "一个普通人"

        era = character_info["era"]

        try:
            new_images = self.generate_character_image(
                game_id=original.game_id,
                name=original.entity_name,
                description=prompt,
                era=era,
                entity_key=original.entity_key,
                metadata=metadata,
                num_images=1,
                feedback=None,
                reference_image_url=None,
            )

            logger.info(f"Fresh images regenerated: {len(new_images)} new images")
            return new_images

        except Exception as e:
            logger.error(f"Failed to fresh regenerate image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"完全重新生成失败: {e}")

    def _get_image_data(self, image_model: ImageModel) -> bytes:
        """获取图片二进制数据"""
        return self.storage_service.get_image_data(
            image_model.storage_path,
            image_model.storage_type,
        )