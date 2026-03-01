"""Scene image service - 场景插画生成服务."""
import logging
import base64
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from src.ai.image_client import ImageClient, ImageGenerationError, ContentInspectionError
from src.services.image_storage import ImageStorageService
from src.database.models import Image as ImageModel
from src.services.image import ImageServiceError, ImageContentError

logger = logging.getLogger(__name__)


class SceneImageService:
    """场景插画生成服务"""

    # 场景插画提示词模板
    SCENE_PROMPT_TEMPLATE = """电影感故事场景插画。
时代背景：{era}。
场景：{scene_desc}
{illustration_prompt}
风格：写实风格，光影自然，故事感强，电影构图。"""

    def __init__(
        self,
        db: Session,
        image_client: Optional[ImageClient] = None,
        storage_service: Optional[ImageStorageService] = None,
    ):
        self.db = db
        self.image_client = image_client or ImageClient()
        self.storage_service = storage_service or ImageStorageService()

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
        get_week_func: callable = None,
        get_player_image_func: callable = None,
    ) -> "SceneImage":
        """
        自动生成每轮场景插画

        Args:
            game_id: 游戏ID
            round_number: 轮次
            story_text: 故事文本
            character_settings: 角色设定
            player_name: 玩家角色名称
            player_image_id: 可选的玩家形象图片ID
            stage: 场景阶段
            week: 周数
            get_week_func: 获取周数的函数
            get_player_image_func: 获取玩家图片的函数

        Returns:
            SceneImage 实例
        """
        from src.database.models import SceneImage

        week_display = f"第{week + 1}周" if week is not None else "未知周"
        logger.info(f"生成场景插画: game={game_id}, {week_display}, round {round_number}, stage={stage}")

        if week is None and get_week_func:
            week = get_week_func(game_id)

        # 检查是否已存在
        existing = self.db.query(SceneImage).filter(
            SceneImage.game_id == game_id,
            SceneImage.week == week,
            SceneImage.round_number == round_number,
            SceneImage.stage == stage,
        ).first()
        if existing:
            week_display = f"第{week + 1}周" if week is not None else "未知周"
            logger.info(f"场景插画已存在: {week_display}, round {round_number}, stage={stage}, 跳过")
            return existing

        char_info = self._build_char_info(character_settings, player_name)

        try:
            # Step 1: 分析故事选择场景
            scene_desc, illustration_prompt = self.image_client.analyze_story_for_illustration(
                story_text=story_text[:2000],
                character_info=char_info,
            )

            logger.info(f"Selected scene: {scene_desc[:50]}...")

            # Step 2: 获取玩家形象图片作为参考
            reference_url = None
            referenced_image_ids = []

            if get_player_image_func:
                reference_url, img_id = get_player_image_func(game_id, player_image_id)
                if img_id:
                    referenced_image_ids.append(img_id)

            # Step 3: 生成场景插画
            final_prompt = self.SCENE_PROMPT_TEMPLATE.format(
                era=char_info['era'],
                scene_desc=scene_desc,
                illustration_prompt=illustration_prompt
            )

            def generate_image():
                if reference_url:
                    edit_prompt = f"""将人物融入以下场景：{scene_desc}。
保持人物的外貌特征和服装不变。
{illustration_prompt}"""

                    results = self.image_client.edit_image(
                        reference_image=reference_url,
                        prompt=edit_prompt,
                        size="1664*928",
                        num_images=1,
                    )

                    if results:
                        return results[0][0], edit_prompt
                    else:
                        raise ImageGenerationError("Failed to generate scene image with reference")
                else:
                    image_data, _ = self.image_client.generate_image(
                        prompt=final_prompt,
                        size="1664*928",
                        extra_params={"prompt_extend": True},
                    )
                    return image_data, final_prompt

            # 尝试生成，如果触发内容审核则改写后重试
            try:
                image_data, used_prompt = generate_image()
            except ContentInspectionError as e:
                logger.warning(f"Content inspection failed, attempting prompt rewrite and retry...")
                api_error = e.api_error_message or str(e)
                logger.info(f"API error message: {api_error}")

                new_scene_desc, new_prompt = self.image_client.rewrite_prompt_for_content_safety(
                    original_prompt=final_prompt,
                    scene_desc=scene_desc,
                    character_info=char_info,
                    api_error_message=api_error,
                )

                scene_desc = new_scene_desc
                final_prompt = new_prompt
                illustration_prompt = new_prompt

                logger.debug(f"Retrying with rewritten prompt: {new_prompt[:100]}...")

                try:
                    image_data, used_prompt = generate_image()
                except ContentInspectionError as e2:
                    logger.error(f"Content inspection still failed after rewrite: {e2}")
                    raise ImageContentError(
                        "内容审核未通过，请尝试使用其他描述方式",
                        new_prompt
                    )

            # Step 4: 保存图片
            # ★ week 从0开始，entity_name 显示时 +1，与前端一致
            display_week = (week + 1) if week is not None else 0
            storage_path, storage_type = self.storage_service.save_image(
                image_data=image_data,
                game_id=game_id,
                image_type="round_scene",
                entity_name=f"{player_name}_week_{display_week}_round_{round_number}",
                week=week,
                round_number=round_number,
                stage=stage,
            )

            # Step 5: 创建 SceneImage 记录
            new_scene = SceneImage(
                game_id=game_id,
                week=week,
                round_number=round_number,
                stage=stage,
                scene_description=scene_desc,
                final_prompt=used_prompt,
                storage_path=storage_path,
                storage_type=storage_type,
                referenced_images=referenced_image_ids,
                importance_score="medium",
            )
            self.db.add(new_scene)
            self.db.commit()
            self.db.refresh(new_scene)
            week_display = f"第{week + 1}周" if week is not None else "未知周"
            logger.info(f"场景插画创建完成: scene_id={new_scene.scene_id}, {week_display}")

            return new_scene

        except ContentInspectionError as e:
            logger.warning(f"Content inspection failed for round scene: {e}")
            raise ImageContentError(str(e), e.original_prompt)
        except ImageGenerationError as e:
            logger.error(f"Image generation failed: {e}")
            raise ImageServiceError(f"场景插画生成失败: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in generate_round_scene_image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"生成场景插画失败: {e}")

    def generate_opening_illustration(
        self,
        game_id: int,
        story_text: str,
        character_settings: Dict[str, Any],
        player_name: str,
        player_image_id: Optional[int] = None,
        get_player_image_func: callable = None,
    ) -> ImageModel:
        """
        生成开场故事插画

        Args:
            game_id: 游戏ID
            story_text: 开场故事文本
            character_settings: 角色设定
            player_name: 玩家角色名称
            player_image_id: 可选的玩家形象图片ID
            get_player_image_func: 获取玩家图片的函数

        Returns:
            ImageModel 实例
        """
        logger.info(f"Generating opening illustration for game {game_id}")

        # 停用该游戏的旧开场插画
        self.db.query(ImageModel).filter(
            ImageModel.game_id == game_id,
            ImageModel.image_type == "opening_illustration",
        ).update({"is_active": False})
        self.db.commit()

        char_info = self._build_char_info(character_settings, player_name)

        # 获取参考图片URL
        reference_url = None
        if player_image_id and get_player_image_func:
            reference_url, _ = get_player_image_func(game_id, player_image_id)

        try:
            image_data, prompt_used, scene_desc = self.image_client.generate_opening_illustration(
                story_text=story_text,
                character_info=char_info,
                reference_image_url=reference_url,
                size="1664*928",
            )

            storage_path, storage_type = self.storage_service.save_image(
                image_data=image_data,
                game_id=game_id,
                image_type="opening_illustration",
                entity_name=f"{player_name}的开场插画",
            )

            image_model = ImageModel(
                game_id=game_id,
                image_type="opening_illustration",
                entity_name=f"{player_name}的开场插画",
                entity_key="opening_illustration",
                prompt_text=prompt_used,
                storage_path=storage_path,
                storage_type=storage_type,
                metadata_json={
                    "scene_description": scene_desc,
                    "character_settings": character_settings,
                    "player_name": player_name,
                    "reference_image_id": player_image_id,
                },
                version=1,
                is_active=True,
                is_primary=True,
            )

            self.db.add(image_model)
            self.db.commit()
            self.db.refresh(image_model)

            logger.info(f"Opening illustration saved: image_id={image_model.image_id}")
            return image_model

        except ContentInspectionError as e:
            logger.warning(f"Content inspection failed for illustration: {e}")
            raise ImageContentError(str(e), e.original_prompt)
        except ImageGenerationError as e:
            logger.error(f"Image generation failed: {e}")
            raise ImageServiceError(f"插画生成失败: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in generate_opening_illustration: {e}")
            self.db.rollback()
            raise ImageServiceError(f"生成开场插画失败: {e}")

    def regenerate_opening_illustration(
        self,
        game_id: int,
        story_text: str,
        character_settings: Dict[str, Any],
        player_name: str,
        player_image_id: Optional[int],
        user_prompt: str,
        current_illustration_id: int,
        get_image_data_func: callable = None,
        get_player_image_func: callable = None,
    ) -> ImageModel:
        """
        基于用户输入重新生成开场故事插画

        Args:
            game_id: 游戏ID
            story_text: 开场故事文本
            character_settings: 角色设定
            player_name: 玩家角色名称
            player_image_id: 可选的玩家形象图片ID
            user_prompt: 用户自定义提示词
            current_illustration_id: 当前插画ID
            get_image_data_func: 获取图片数据的函数
            get_player_image_func: 获取玩家图片的函数

        Returns:
            ImageModel 实例
        """
        logger.info(f"Regenerating opening illustration for game {game_id}")

        # 停用旧开场插画
        self.db.query(ImageModel).filter(
            ImageModel.game_id == game_id,
            ImageModel.image_type == "opening_illustration",
        ).update({"is_active": False})
        self.db.commit()

        char_info = self._build_char_info(character_settings, player_name)

        # 获取当前插画作为参考
        current_illustration = self.db.query(ImageModel).filter(
            ImageModel.image_id == current_illustration_id
        ).first()

        reference_url = None
        if current_illustration and get_image_data_func:
            try:
                image_data = get_image_data_func(current_illustration)
                ext = current_illustration.storage_path.rsplit('.', 1)[-1].lower()
                mime_type = 'image/png' if ext == 'png' else 'image/jpeg'
                base64_data = base64.b64encode(image_data).decode('utf-8')
                reference_url = f"data:{mime_type};base64,{base64_data}"
                logger.info(f"Using current illustration as reference (base64, {len(image_data)} bytes)")
            except Exception as e:
                logger.warning(f"Failed to get current illustration: {e}")

        # 如果当前插画不可用，尝试使用玩家形象图片
        if not reference_url and player_image_id and get_player_image_func:
            reference_url, _ = get_player_image_func(game_id, player_image_id)

        try:
            scene_desc, illustration_prompt = self.image_client.analyze_story_for_illustration(
                story_text,
                char_info,
            )

            combined_prompt = f"""{user_prompt}

场景：{scene_desc}
{illustration_prompt}"""

            logger.debug(f"Combined prompt: {combined_prompt[:100]}...")

            if reference_url:
                results = self.image_client.edit_image(
                    reference_image=reference_url,
                    prompt=combined_prompt,
                    size="1664*928",
                    num_images=1,
                )

                if results:
                    image_data, _ = results[0]
                    prompt_used = combined_prompt
                else:
                    raise ImageGenerationError("Failed to regenerate illustration")
            else:
                image_data, prompt_used = self.image_client.generate_image(
                    prompt=combined_prompt,
                    size="1664*928",
                    extra_params={"prompt_extend": True},
                )

            storage_path, storage_type = self.storage_service.save_image(
                image_data=image_data,
                game_id=game_id,
                image_type="opening_illustration",
                entity_name=f"{player_name}的开场插画",
            )

            image_model = ImageModel(
                game_id=game_id,
                image_type="opening_illustration",
                entity_name=f"{player_name}的开场插画",
                entity_key="opening_illustration",
                prompt_text=prompt_used,
                storage_path=storage_path,
                storage_type=storage_type,
                metadata_json={
                    "scene_description": scene_desc,
                    "character_settings": character_settings,
                    "player_name": player_name,
                    "reference_image_id": player_image_id,
                    "user_prompt": user_prompt,
                    "regenerated_from": current_illustration_id,
                },
                version=1,
                is_active=True,
                is_primary=True,
            )

            self.db.add(image_model)
            self.db.commit()
            self.db.refresh(image_model)

            logger.info(f"Opening illustration regenerated: image_id={image_model.image_id}")
            return image_model

        except ContentInspectionError as e:
            logger.warning(f"Content inspection failed for illustration: {e}")
            raise ImageContentError(str(e), e.original_prompt)
        except ImageGenerationError as e:
            logger.error(f"Image generation failed: {e}")
            raise ImageServiceError(f"插画重新生成失败: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in regenerate_opening_illustration: {e}")
            self.db.rollback()
            raise ImageServiceError(f"重新生成开场插画失败: {e}")

    def _build_char_info(self, character_settings: Dict[str, Any], player_name: str) -> Dict[str, Any]:
        """构建角色信息字典"""
        char_info = {"name": player_name, "era": "现代"}

        # 提取时代
        era = character_settings.get("era")
        if era:
            if isinstance(era, dict):
                era_name = era.get("era_name") or era.get("era_description", "现代")
                if isinstance(era_name, str) and len(era_name) > 30:
                    era_name = era_name[:30]
                char_info["era"] = era_name or "现代"
            elif isinstance(era, str):
                char_info["era"] = era[:30] if len(era) > 30 else era

        # 提取性别
        gender = character_settings.get("gender")
        if gender:
            if isinstance(gender, dict):
                char_info["gender"] = gender.get("gender", "")
            elif isinstance(gender, str):
                char_info["gender"] = gender

        # 提取年龄
        age = character_settings.get("age")
        if age:
            if isinstance(age, dict):
                char_info["age"] = age.get("age", "")
            elif isinstance(age, (int, float)):
                char_info["age"] = str(age)

        return char_info