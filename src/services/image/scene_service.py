"""Scene image service - 场景插画生成服务."""

import base64
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.ai.image_client import (ContentInspectionError, ImageClient,
                                 ImageGenerationError)
from src.database.models import Image as ImageModel
from src.database.models import SceneImage
from src.services.image import ImageContentError, ImageServiceError
from src.services.image.appearance_anchor import CharacterAppearanceAnchor
from src.services.image.style_manager import style_manager
from src.services.image_storage import ImageStorageService

logger = logging.getLogger(__name__)


class SceneImageService:
    """场景插画生成服务"""

    # 场景插画提示词模板 - 优化版本（更细致的描述）
    SCENE_PROMPT_TEMPLATE = """电影感故事场景插画，高质量，细节丰富。

【时代背景】
{era}

【场景描述】
{scene_desc}

【画面构图】
- 构图：电影级构图，视觉焦点明确，景深自然
- 人物位置：黄金分割点或画面中心偏左/右，避免呆板居中
- 镜头角度：略高于人物视线的俯视角度，增强代入感

【光线与氛围】
{lighting_desc}
- 主光源：自然光或场景光源，方向明确
- 阴影：层次分明，柔和过渡，面部阴影不掩盖特征
- 光比：适中，保留亮部和暗部细节

{illustration_prompt}

【色彩调性】
{color_palette}

【质量要求】
- 写实风格，细节清晰，纹理丰富
- 光影自然，过渡柔和，避免过度后期感
- 色彩饱和度适中，整体色调统一协调
- 电影质感，故事感强，氛围渲染到位"""

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
        logger.info(
            f"生成场景插画: game={game_id}, {week_display}, round {round_number}, stage={stage}"
        )

        if week is None and get_week_func:
            week = get_week_func(game_id)

        # 检查是否已存在
        existing = (
            self.db.query(SceneImage)
            .filter(
                SceneImage.game_id == game_id,
                SceneImage.week == week,
                SceneImage.round_number == round_number,
                SceneImage.stage == stage,
            )
            .first()
        )
        if existing:
            # ★ 验证文件是否真实存在，如果不存在则删除记录并重新生成
            if existing.storage_path and self.storage_service.image_exists(
                existing.storage_path, existing.storage_type
            ):
                week_display = f"第{week + 1}周" if week is not None else "未知周"
                logger.info(
                    f"场景插画已存在: {week_display}, round {round_number}, stage={stage}, 跳过"
                )
                return existing
            else:
                # 文件不存在，删除数据库记录并重新生成
                week_display = f"第{week + 1}周" if week is not None else "未知周"
                logger.warning(
                    f"场景插画记录存在但文件丢失: {week_display}, round {round_number}, stage={stage}, 重新生成"
                )
                self.db.delete(existing)
                self.db.commit()

        char_info = self._build_char_info(character_settings, player_name)

        # ★ 从故事文本检测情感基调
        detected_mood = style_manager.detect_mood_from_story(story_text)
        logger.info(f"Detected mood from story: {detected_mood.value}")

        # ★ 获取或应用颜色调板（如果已设置游戏调板，则优先使用）
        if game_id in style_manager._game_palettes:
            palette = style_manager.get_game_palette(game_id)
            logger.info(f"Using game palette: {palette.name}")
        else:
            palette = style_manager.get_palette(detected_mood)
            style_manager.set_game_palette(game_id, detected_mood)
            logger.info(f"Setting new palette for game: {palette.name}")

        # ★ 应用时序色彩变化（如果有周数信息）
        temporal_hint = ""
        if week is not None:
            # 假设总共52周（一年）
            total_weeks = 52
            temporal_palette = style_manager.apply_temporal_progression(game_id, week, total_weeks)
            temporal_hint = temporal_palette.atmosphere
            logger.info(f"Applied temporal progression: week {week}, hint: {temporal_hint[:50]}...")

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
            appearance_anchor = None

            if get_player_image_func:
                reference_url, img_id = get_player_image_func(game_id, player_image_id)
                if img_id:
                    referenced_image_ids.append(img_id)
                    # ★ 获取外貌锚点数据
                    appearance_anchor = self._get_appearance_anchor(img_id)

            # Step 3: 生成场景插画
            # ★ 构建光线描述（基于调板）
            lighting_desc = palette.lighting
            if temporal_hint:
                lighting_desc += f"。{temporal_hint}"

            # ★ 使用锚点构建更详细的角色描述
            if appearance_anchor:
                # 使用锚点数据构建详细的角色外貌描述
                anchor_desc = appearance_anchor.build_prompt_segment()
                logger.info(f"Using appearance anchor for scene generation: {anchor_desc[:100]}...")

                # 将锚点描述融入场景提示词
                enhanced_illustration = f"""{illustration_prompt}

人物外貌特征（必须严格保持一致）：
{anchor_desc}

重要：人物的面部特征、发型、体型必须与上述描述完全一致，仅姿势和场景环境可以改变。"""
            else:
                enhanced_illustration = illustration_prompt
                logger.warning("No appearance anchor found, using basic character info")

            # ★ 使用优化后的模板生成最终提示词
            final_prompt = self.SCENE_PROMPT_TEMPLATE.format(
                era=char_info["era"],
                scene_desc=scene_desc,
                lighting_desc=lighting_desc,
                illustration_prompt=enhanced_illustration,
                color_palette=palette.build_prompt_segment(),
            )

            def generate_image():
                if reference_url:
                    # ★ 使用锚点构建更精确的编辑提示词
                    if appearance_anchor:
                        anchor_desc = appearance_anchor.build_prompt_segment()
                        edit_prompt = f"""将人物融入以下场景：{scene_desc}。

人物必须具有以下外貌特征（严格保持一致）：
{anchor_desc}

场景动作和氛围：{illustration_prompt}

光线要求：{lighting_desc}
色彩调性：{palette.build_prompt_segment()}

重要：
- 保持人物的面部特征、发型、体型完全一致
- 人物与新场景的光影要自然融合，投影方向一致
- 色调要与场景整体调性协调
- 只改变姿势和融入新场景，不改变外貌特征"""
                    else:
                        edit_prompt = f"""将人物融入以下场景：{scene_desc}。

场景动作和氛围：{illustration_prompt}
光线要求：{lighting_desc}
色彩调性：{palette.build_prompt_segment()}

保持人物的外貌特征和服装不变，确保光影融合自然。"""

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
                logger.warning("Content inspection failed, attempting prompt rewrite and retry...")
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
                    raise ImageContentError("内容审核未通过，请尝试使用其他描述方式", new_prompt)

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
        current_illustration = (
            self.db.query(ImageModel).filter(ImageModel.image_id == current_illustration_id).first()
        )

        reference_url = None
        if current_illustration and get_image_data_func:
            try:
                image_data = get_image_data_func(current_illustration)
                ext = current_illustration.storage_path.rsplit(".", 1)[-1].lower()
                mime_type = "image/png" if ext == "png" else "image/jpeg"
                base64_data = base64.b64encode(image_data).decode("utf-8")
                reference_url = f"data:{mime_type};base64,{base64_data}"
                logger.info(
                    f"Using current illustration as reference (base64, {len(image_data)} bytes)"
                )
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

    def _build_char_info(
        self, character_settings: Dict[str, Any], player_name: str
    ) -> Dict[str, Any]:
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

    def _get_appearance_anchor(self, image_id: int) -> Optional[CharacterAppearanceAnchor]:
        """从人物图片记录中获取外貌锚点.

        Args:
            image_id: 人物图片ID

        Returns:
            CharacterAppearanceAnchor 实例，如果不存在则返回 None
        """
        try:
            image = self.db.query(ImageModel).filter(ImageModel.image_id == image_id).first()
            if not image or not image.metadata_json:
                return None

            anchor_data = image.metadata_json.get("appearance_anchor")
            if not anchor_data:
                return None

            return CharacterAppearanceAnchor.from_dict(anchor_data)
        except Exception as e:
            logger.warning(f"Failed to get appearance anchor for image {image_id}: {e}")
            return None
