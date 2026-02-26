"""Image service - 图像生成调度服务.

协调图像生成、存储和数据库记录。
"""
import logging
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from config.settings import settings
from src.ai.image_client import ImageClient, ImageGenerationError, ContentInspectionError
from src.services.image_storage import ImageStorageService, ImageStorageError
from src.database.models import Image as ImageModel

logger = logging.getLogger(__name__)


class ImageServiceError(Exception):
    """图像服务错误"""
    pass


class ImageContentError(ImageServiceError):
    """图像内容审核错误"""
    def __init__(self, message: str, original_prompt: str = None):
        super().__init__(message)
        self.original_prompt = original_prompt


class ImageService:
    """图像生成调度服务"""
    
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
    
    def generate_character_image(
        self,
        game_id: int,
        name: str,
        description: str,
        era: str = "现代",
        entity_key: Optional[str] = None,
        style_hint: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        num_images: int = 1,  # ★ 默认生成1张
        feedback: Optional[str] = None,  # ★ 用户反馈
        reference_image_url: Optional[str] = None,  # ★ 参考图片URL（用于重新生成）
    ) -> List[ImageModel]:
        """
        生成人物全身像图片（保证人物一致性）
        
        流程：
        1. 如果有参考图片URL，基于它生成变体
        2. 如果没有，先生成1张主图，再生成变体
        
        Args:
            game_id: 游戏ID
            name: 人物名称
            description: 人物描述
            era: 时代背景
            entity_key: 实体唯一标识（如 player_main, npc_1）
            style_hint: 风格提示
            metadata: 额外元数据
            num_images: 总图片数量（默认2张）
            feedback: 用户反馈（追加到描述中）
            reference_image_url: 参考图片URL（用于重新生成）
        
        Returns:
            Image模型实例列表
        
        Raises:
            ImageServiceError: 生成失败
        """
        logger.info(f"Generating {num_images} character images: {name} for game {game_id}, feedback: {feedback}")
        
        # ★ 停用该实体的所有旧图片（避免重复显示）
        self.db.query(ImageModel).filter(
            ImageModel.game_id == game_id,
            ImageModel.entity_key == (entity_key or f"character_{name}")
        ).update({"is_active": False})
        self.db.commit()
        
        try:
            # ★ 使用新的图生图逻辑，feedback单独传递以强调
            images_data, primary_image_url = self.image_client.generate_character_images(
                name=name,
                description=description,
                era=era,
                style_hint=style_hint,
                num_images=num_images,
                reference_image_url=reference_image_url,
                feedback=feedback,  # ★ 单独传递feedback以强调
            )
            
            if not images_data:
                raise ImageServiceError("没有成功生成任何图片")
            
            image_models = []
            primary_image_model = None
            
            for idx, (image_data, prompt) in enumerate(images_data):
                # 保存图片
                storage_path, storage_type = self.storage_service.save_image(
                    image_data=image_data,
                    game_id=game_id,
                    image_type="character",
                    entity_name=f"{name}_{idx + 1}",
                )
                
                # ★ 第一张是主图
                is_primary = (idx == 0 and not reference_image_url)
                
                # 创建数据库记录
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
                    primary_image_id=None,  # 后续更新
                )
                
                self.db.add(image_model)
                image_models.append(image_model)
                
                if is_primary:
                    primary_image_model = image_model
            
            self.db.commit()
            
            # ★ 更新变体图片的主图关联
            if primary_image_model:
                for model in image_models[1:]:
                    model.primary_image_id = primary_image_model.image_id
                self.db.commit()
            
            # 刷新所有模型
            for model in image_models:
                self.db.refresh(model)
            
            logger.info(f"Character images saved: {len(image_models)} images for {name}")
            return image_models
            
        except ContentInspectionError as e:
            # ★ 内容审核错误 - 直接传递，不回滚（因为还没做任何修改）
            logger.warning(f"Content inspection failed: {e}")
            raise ImageContentError(str(e), e.original_prompt)
        except ImageGenerationError as e:
            logger.error(f"Image generation failed: {e}")
            raise ImageServiceError(f"图像生成失败: {e}")
        except ImageStorageError as e:
            logger.error(f"Image storage failed: {e}")
            raise ImageServiceError(f"图像存储失败: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in generate_character_image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"生成人物形象失败: {e}")
    
    def regenerate_image(
        self,
        image_id: int,
        feedback: Optional[str] = None,
        new_description: Optional[str] = None,
    ) -> List[ImageModel]:
        """
        重新生成图片（保持人物一致性）
        
        流程：
        1. 获取主图
        2. 使用主图的静态 URL 作为参考
        3. 基于参考生成变体
        
        Args:
            image_id: 原图片ID（任意一张图片的ID）
            feedback: 用户修改意见
            new_description: 新的描述（可选，覆盖原描述）
        
        Returns:
            新的Image模型实例列表
        """
        logger.info(f"Regenerating image: {image_id}, feedback: {feedback}")
        
        # 获取原图片记录
        original = self.db.query(ImageModel).filter(
            ImageModel.image_id == image_id
        ).first()
        
        if not original:
            raise ImageServiceError(f"图片不存在: {image_id}")
        
        # ★ 使用当前图片作为参考（因为现在只生成1张，每次都是独立的图片）
        reference_source_image = original
        
        # ★ 停用该实体的所有旧图片
        self.db.query(ImageModel).filter(
            ImageModel.game_id == original.game_id,
            ImageModel.entity_key == original.entity_key
        ).update({"is_active": False})
        self.db.commit()
        
        # ★ 从 metadata 中提取角色设定
        metadata = original.metadata_json or {}
        char_settings = metadata.get("characterSettings", {})
        
        # 构建角色描述
        if new_description:
            base_description = new_description
        else:
            base_description = self._build_description_from_settings(char_settings)
        
        # 获取时代
        era = self._extract_era_from_settings(char_settings) or "现代"
        
        # ★ 使用当前图片作为参考图片（保持人物一致性）
        reference_url = None
        try:
            image_data = self.get_image_data(reference_source_image)
            import base64
            # 从 storage_path 获取文件扩展名
            ext = reference_source_image.storage_path.rsplit('.', 1)[-1].lower()
            mime_type = 'image/png' if ext == 'png' else 'image/jpeg'
            base64_data = base64.b64encode(image_data).decode('utf-8')
            reference_url = f"data:{mime_type};base64,{base64_data}"
            logger.info(f"Using current image as reference (base64, {len(image_data)} bytes)")
        except Exception as e:
            logger.warning(f"Failed to convert image to base64: {e}, will generate without reference")
        
        try:
            # ★ 使用 generate_character_image 支持参考图片
            # ★ 重新生成1张图片，参考图片已保证人物一致性，只用当前feedback
            new_images = self.generate_character_image(
                game_id=original.game_id,
                name=original.entity_name,
                description=base_description,
                era=era,
                entity_key=original.entity_key,
                metadata=metadata,
                num_images=1,  # ★ 只生成1张
                feedback=feedback,  # ★ 只用当前feedback，参考图片已保证一致性
                reference_image_url=reference_url,
            )
            
            logger.info(f"Images regenerated: {len(new_images)} new images")
            return new_images
            
        except ImageContentError:
            # ★ 内容审核错误直接传递
            raise
        except Exception as e:
            logger.error(f"Failed to regenerate image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"重新生成失败: {e}")
    
    def regenerate_fresh_image(
        self,
        image_id: int,
        use_deepseek_prompt: bool = True,
    ) -> List[ImageModel]:
        """
        完全重新生成图片（抛弃历史修改）
        
        流程：
        1. 获取原图片的角色设定信息
        2. 使用 DeepSeek 生成优化的图片 prompt
        3. 使用 qwen-image-max 文生图（不使用参考图片）
        
        Args:
            image_id: 原图片ID
            use_deepseek_prompt: 是否使用 DeepSeek 生成优化的 prompt
        
        Returns:
            新的Image模型实例列表
        """
        logger.info(f"Fresh regenerating image: {image_id}, use_deepseek={use_deepseek_prompt}")
        
        # 获取原图片记录
        original = self.db.query(ImageModel).filter(
            ImageModel.image_id == image_id
        ).first()
        
        if not original:
            raise ImageServiceError(f"图片不存在: {image_id}")
        
        # ★ 停用该实体的所有旧图片
        self.db.query(ImageModel).filter(
            ImageModel.game_id == original.game_id,
            ImageModel.entity_key == original.entity_key
        ).update({"is_active": False})
        self.db.commit()
        
        # ★ 从 metadata 中提取角色设定
        metadata = original.metadata_json or {}
        char_settings = metadata.get("characterSettings", {})
        
        # 提取人物信息
        character_info = {
            "name": original.entity_name,
            "age": char_settings.get("age", 25),
            "gender": char_settings.get("gender", "女"),
            "era": self._extract_era_from_settings(char_settings) or "现代",
            "appearance": char_settings.get("appearance", ""),
            "personality": char_settings.get("personality", ""),
            "occupation": char_settings.get("occupation", ""),
            "background": char_settings.get("background", ""),
        }
        
        # ★ 使用 DeepSeek 生成优化的 prompt
        if use_deepseek_prompt:
            try:
                prompt = self.image_client.generate_image_prompt_with_deepseek(character_info)
                logger.info(f"DeepSeek generated prompt: {prompt[:100]}...")
            except Exception as e:
                logger.warning(f"DeepSeek prompt generation failed, using fallback: {e}")
                prompt = self._build_description_from_settings(char_settings)
        else:
            prompt = self._build_description_from_settings(char_settings)
        
        era = character_info["era"]
        
        try:
            # ★ 使用文生图（不传入 reference_image_url）
            new_images = self.generate_character_image(
                game_id=original.game_id,
                name=original.entity_name,
                description=prompt,  # 使用 DeepSeek 生成的 prompt
                era=era,
                entity_key=original.entity_key,
                metadata=metadata,
                num_images=1,
                feedback=None,  # ★ 不使用 feedback
                reference_image_url=None,  # ★ 不使用参考图片
            )
            
            logger.info(f"Fresh images regenerated: {len(new_images)} new images")
            return new_images
            
        except Exception as e:
            logger.error(f"Failed to fresh regenerate image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"完全重新生成失败: {e}")
    
    def get_image(self, image_id: int) -> Optional[ImageModel]:
        """获取图片记录"""
        return self.db.query(ImageModel).filter(
            ImageModel.image_id == image_id
        ).first()
    
    def get_active_image(
        self,
        game_id: int,
        image_type: str,
        entity_name: str,
    ) -> Optional[ImageModel]:
        """
        获取活跃的图片记录
        
        Args:
            game_id: 游戏ID
            image_type: 图片类型
            entity_name: 实体名称
        
        Returns:
            活跃的Image模型，如果不存在返回None
        """
        return self.db.query(ImageModel).filter(
            ImageModel.game_id == game_id,
            ImageModel.image_type == image_type,
            ImageModel.entity_name == entity_name,
            ImageModel.is_active == True,
        ).order_by(ImageModel.version.desc()).first()
    
    def get_all_images_for_game(
        self,
        game_id: int,
        image_type: Optional[str] = None,
    ) -> List[ImageModel]:
        """
        获取游戏的所有图片
        
        Args:
            game_id: 游戏ID
            image_type: 可选的类型过滤
        
        Returns:
            图片列表
        """
        query = self.db.query(ImageModel).filter(
            ImageModel.game_id == game_id,
            ImageModel.is_active == True,
        )
        
        if image_type:
            query = query.filter(ImageModel.image_type == image_type)
        
        return query.all()
    
    def get_image_url(self, image_model: ImageModel) -> str:
        """获取图片访问URL"""
        return self.storage_service.get_image_url(
            image_model.storage_path,
            image_model.storage_type,
        )
    
    def get_image_data(self, image_model: ImageModel) -> bytes:
        """获取图片二进制数据"""
        return self.storage_service.get_image_data(
            image_model.storage_path,
            image_model.storage_type,
        )
    
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
            
        except Exception as e:
            logger.error(f"Failed to generate location image: {e}")
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
            
        except Exception as e:
            logger.error(f"Failed to generate item image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"生成物品图片失败: {e}")
    
    def _extract_description_from_prompt(self, prompt: str) -> str:
        """从prompt中提取描述"""
        # 简单提取，可以改进
        if "人物描述：" in prompt:
            start = prompt.find("人物描述：") + 5
            end = prompt.find("。", start)
            if end > start:
                return prompt[start:end]
        return prompt
    
    def _extract_era_from_metadata(self, metadata: Optional[Dict[str, Any]]) -> str:
        """从元数据中提取时代"""
        if metadata and "era" in metadata:
            return metadata["era"]
        return "现代"
    
    def _build_description_from_settings(self, char_settings: Dict[str, Any]) -> str:
        """
        从角色设定构建人物描述
        
        Args:
            char_settings: 角色设定字典，包含 era, age, gender, world 等
        
        Returns:
            人物描述字符串
        """
        parts = []
        
        # 年龄
        age = char_settings.get("age")
        if age:
            if isinstance(age, dict):
                if age.get("age"):
                    parts.append(f"{age['age']}岁")
                elif age.get("age_range"):
                    parts.append(str(age["age_range"]))
            elif isinstance(age, (int, float)):
                parts.append(f"{age}岁")
        
        # 性别
        gender = char_settings.get("gender")
        if gender:
            if isinstance(gender, dict) and gender.get("gender"):
                parts.append(str(gender["gender"]))
            elif isinstance(gender, str):
                parts.append(gender)
        
        # 世界观
        world = char_settings.get("world")
        if world and isinstance(world, dict):
            if world.get("cultural_context"):
                parts.append(str(world["cultural_context"]))
            if world.get("special_features"):
                parts.append(str(world["special_features"]))
        
        return "，".join(parts) if parts else "一个普通人"
    
    def _extract_era_from_settings(self, char_settings: Dict[str, Any]) -> Optional[str]:
        """
        从角色设定中提取时代名称（用于图片生成）
        
        Args:
            char_settings: 角色设定字典
        
        Returns:
            简短的时代名称，如果不存在返回 None
            
        Note:
            图片生成需要简短的时代描述，不能使用完整的 era_description。
            era_description 可能包含详细的背景设定（如"2008年社交媒体萌芽期..."），
            这会导致图片 prompt 混乱。
        """
        era = char_settings.get("era")
        if era:
            if isinstance(era, dict):
                # ★ 优先使用 era_name（简短名称）
                era_name = era.get("era_name")
                if era_name and era_name.strip():
                    return era_name.strip()
                
                # ★ 如果只有 era_description，提取第一句话或前30字
                era_desc = era.get("era_description")
                if era_desc and era_desc.strip():
                    # 截取第一句话或前30字，避免 prompt 过长
                    desc = era_desc.strip()
                    # 按句号、逗号截断
                    for sep in ["。", "，", ",", "."]:
                        if sep in desc:
                            desc = desc.split(sep)[0]
                            break
                    # 限制长度
                    if len(desc) > 30:
                        desc = desc[:30]
                    return desc
                
                return None
            elif isinstance(era, str):
                # 如果是字符串，同样限制长度
                if len(era) > 30:
                    return era[:30]
                return era
        return None
    
    def generate_opening_illustration(
        self,
        game_id: int,
        story_text: str,
        character_settings: Dict[str, Any],
        player_name: str,
        player_image_id: Optional[int] = None,
    ) -> ImageModel:
        """
        生成开场故事插画
        
        流程：
        1. 使用 DeepSeek 分析故事，选择场景并生成提示词
        2. 如果有玩家形象图片，使用 image-edit 模型生成插画
        3. 保存图片到数据库
        
        Args:
            game_id: 游戏ID
            story_text: 开场故事文本
            character_settings: 角色设定
            player_name: 玩家角色名称
            player_image_id: 可选的玩家形象图片ID
        
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
        
        # 准备角色信息
        char_info = {
            "name": player_name,
            "era": self._extract_era_from_settings(character_settings) or "现代",
        }
        
        # 提取性别和年龄
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
        
        # 获取参考图片URL（如果有）
        reference_url = None
        if player_image_id:
            try:
                # ★ 必须验证 player_image_id 属于当前游戏，避免跨游戏数据泄漏
                player_image = self.db.query(ImageModel).filter(
                    ImageModel.image_id == player_image_id,
                    ImageModel.game_id == game_id  # ★ 必须属于当前游戏
                ).first()
                if player_image:
                    # ★ 转换为 Base64 格式（图生图API需要公开URL或Base64）
                    image_data = self.get_image_data(player_image)
                    import base64
                    ext = player_image.storage_path.rsplit('.', 1)[-1].lower()
                    mime_type = 'image/png' if ext == 'png' else 'image/jpeg'
                    base64_data = base64.b64encode(image_data).decode('utf-8')
                    reference_url = f"data:{mime_type};base64,{base64_data}"
                    logger.info(f"Using player image as reference (base64, {len(image_data)} bytes)")
            except Exception as e:
                logger.warning(f"Failed to get player image: {e}")
        
        try:
            # 生成插画
            image_data, prompt_used, scene_desc = self.image_client.generate_opening_illustration(
                story_text=story_text,
                character_info=char_info,
                reference_image_url=reference_url,
                size="1664*928",  # 16:9 宽屏
            )
            
            # 保存图片
            storage_path, storage_type = self.storage_service.save_image(
                image_data=image_data,
                game_id=game_id,
                image_type="opening_illustration",
                entity_name=f"{player_name}的开场插画",
            )
            
            # 创建数据库记录
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
    ) -> ImageModel:
        """
        基于用户输入重新生成开场故事插画
        
        流程：
        1. 使用 DeepSeek 分析故事，选择场景
        2. 结合用户自定义提示词
        3. 使用当前插画作为参考（保持场景一致性）
        4. 如果有玩家形象图片，也作为参考
        5. 保存新图片到数据库
        
        Args:
            game_id: 游戏ID
            story_text: 开场故事文本
            character_settings: 角色设定
            player_name: 玩家角色名称
            player_image_id: 可选的玩家形象图片ID
            user_prompt: 用户自定义提示词/修改意见
            current_illustration_id: 当前插画ID，作为参考
        
        Returns:
            ImageModel 实例
        """
        logger.info(f"Regenerating opening illustration for game {game_id} with user prompt: {user_prompt}")
        
        # 停用该游戏的旧开场插画
        self.db.query(ImageModel).filter(
            ImageModel.game_id == game_id,
            ImageModel.image_type == "opening_illustration",
        ).update({"is_active": False})
        self.db.commit()
        
        # 准备角色信息
        char_info = {
            "name": player_name,
            "era": self._extract_era_from_settings(character_settings) or "现代",
        }
        
        # 提取性别和年龄
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
        
        # 获取当前插画作为参考
        current_illustration = self.db.query(ImageModel).filter(
            ImageModel.image_id == current_illustration_id
        ).first()
        
        reference_url = None
        if current_illustration:
            try:
                image_data = self.get_image_data(current_illustration)
                import base64
                ext = current_illustration.storage_path.rsplit('.', 1)[-1].lower()
                mime_type = 'image/png' if ext == 'png' else 'image/jpeg'
                base64_data = base64.b64encode(image_data).decode('utf-8')
                reference_url = f"data:{mime_type};base64,{base64_data}"
                logger.info(f"Using current illustration as reference (base64, {len(image_data)} bytes)")
            except Exception as e:
                logger.warning(f"Failed to get current illustration: {e}")
        
        # 如果当前插画不可用，尝试使用玩家形象图片
        if not reference_url and player_image_id:
            try:
                # ★ 必须验证 player_image_id 属于当前游戏，避免跨游戏数据泄漏
                player_image = self.db.query(ImageModel).filter(
                    ImageModel.image_id == player_image_id,
                    ImageModel.game_id == game_id  # ★ 必须属于当前游戏
                ).first()
                if player_image:
                    image_data = self.get_image_data(player_image)
                    import base64
                    ext = player_image.storage_path.rsplit('.', 1)[-1].lower()
                    mime_type = 'image/png' if ext == 'png' else 'image/jpeg'
                    base64_data = base64.b64encode(image_data).decode('utf-8')
                    reference_url = f"data:{mime_type};base64,{base64_data}"
                    logger.info(f"Using player image as reference (base64, {len(image_data)} bytes)")
            except Exception as e:
                logger.warning(f"Failed to get player image: {e}")
        
        try:
            # 分析故事选择场景
            scene_desc, illustration_prompt = self.image_client.analyze_story_for_illustration(
                story_text,
                char_info,
            )
            
            # 结合用户提示词
            combined_prompt = f"""{user_prompt}

场景：{scene_desc}
{illustration_prompt}"""
            
            logger.info(f"Combined prompt: {combined_prompt[:100]}...")
            
            # 使用图生图重新生成
            if reference_url:
                results = self.image_client.edit_image(
                    reference_image=reference_url,
                    prompt=combined_prompt,
                    size="1664*928",  # 16:9 宽屏
                    num_images=1,
                )
                
                if results:
                    image_data, _ = results[0]
                    prompt_used = combined_prompt
                else:
                    raise ImageGenerationError("Failed to regenerate illustration")
            else:
                # 没有参考图片，使用文生图
                image_data, prompt_used = self.image_client.generate_image(
                    prompt=combined_prompt,
                    size="1664*928",
                    extra_params={"prompt_extend": True},
                )
            
            # 保存图片
            storage_path, storage_type = self.storage_service.save_image(
                image_data=image_data,
                game_id=game_id,
                image_type="opening_illustration",
                entity_name=f"{player_name}的开场插画",
            )
            
            # 创建数据库记录
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

    def generate_round_scene_image(
        self,
        game_id: int,
        round_number: int,
        story_text: str,
        character_settings: Dict[str, Any],
        player_name: str,
        player_image_id: Optional[int] = None,
        stage: str = "result",  # ★ event | result
        week: Optional[int] = None,  # ★ 新增：周数
    ) -> "SceneImage":
        """
        自动生成每轮场景插画
        
        流程：
        1. 使用 DeepSeek 分析故事，选择场景并生成提示词
        2. 如果有玩家形象图片，使用图生图
        3. 否则使用文生图
        4. 保存到 SceneImage 表
        
        Args:
            game_id: 游戏ID
            round_number: 轮次
            story_text: 故事文本
            character_settings: 角色设定
            player_name: 玩家角色名称
            player_image_id: 可选的玩家形象图片ID
            stage: 场景阶段 (event=事件故事, result=结果故事)
            week: 周数
        
        Returns:
            SceneImage 实例
        """
        from src.database.models import SceneImage
        
        logger.info(f"Generating round {round_number} scene for game {game_id}, week={week}, stage={stage}")
        
        # ★ 如果没有传入 week，尝试从数据库获取
        if week is None:
            week = self._get_current_week_from_db(game_id)
        
        # 检查是否已存在（同一周同一轮次同一阶段）
        existing = self.db.query(SceneImage).filter(
            SceneImage.game_id == game_id,
            SceneImage.week == week,  # ★ 加入 week 条件
            SceneImage.round_number == round_number,
            SceneImage.stage == stage,  # ★ 区分阶段
        ).first()
        if existing:
            logger.info(f"Scene image already exists for week {week} round {round_number} stage={stage}, skipping")
            return existing
        
        # 准备角色信息
        char_info = {
            "name": player_name,
            "era": self._extract_era_from_settings(character_settings) or "现代",
        }
        
        # 提取性别和年龄
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
        
        try:
            # Step 1: 使用 DeepSeek 分析故事选择场景
            scene_desc, illustration_prompt = self.image_client.analyze_story_for_illustration(
                story_text=story_text[:2000],
                character_info=char_info,
            )
            
            logger.info(f"Selected scene: {scene_desc[:50]}...")
            
            # Step 2: 获取玩家形象图片作为参考
            reference_url = None
            referenced_image_ids = []
            
            # ★ 优先使用传入的 player_image_id，但必须验证属于当前游戏
            player_image = None
            if player_image_id:
                player_image = self.db.query(ImageModel).filter(
                    ImageModel.image_id == player_image_id,
                    ImageModel.game_id == game_id  # ★ 必须属于当前游戏，避免跨游戏数据泄漏
                ).first()
                if not player_image:
                    logger.warning(f"player_image_id={player_image_id} does not belong to game_id={game_id}, will auto-select")
            
            # ★ 如果没有传入或找不到，自动获取该游戏的主要人物画像
            if not player_image:
                player_image = self.db.query(ImageModel).filter(
                    ImageModel.game_id == game_id,
                    ImageModel.image_type == "character",
                    ImageModel.is_primary == True
                ).order_by(ImageModel.image_id.desc()).first()
                if player_image:
                    logger.info(f"Auto-selected primary player image: {player_image.image_id}")
            
            if player_image:
                try:
                    image_data = self.get_image_data(player_image)
                    import base64
                    ext = player_image.storage_path.rsplit('.', 1)[-1].lower()
                    mime_type = 'image/png' if ext == 'png' else 'image/jpeg'
                    base64_data = base64.b64encode(image_data).decode('utf-8')
                    reference_url = f"data:{mime_type};base64,{base64_data}"
                    referenced_image_ids.append(player_image.image_id)
                    logger.info(f"Using player image {player_image.image_id} as reference (base64, {len(image_data)} bytes)")
                except Exception as e:
                    logger.warning(f"Failed to get player image: {e}")
            
            # Step 3: 生成场景插画
            final_prompt = f"""电影感故事场景插画。
时代背景：{char_info['era']}。
场景：{scene_desc}
{illustration_prompt}
风格：写实风格，光影自然，故事感强，电影构图。"""
            
            # ★ 定义生成函数，方便重试
            def generate_image():
                if reference_url:
                    # 使用图生图，将人物融入场景
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
                    # 文生图
                    image_data, _ = self.image_client.generate_image(
                        prompt=final_prompt,
                        size="1664*928",
                        extra_params={"prompt_extend": True},
                    )
                    return image_data, final_prompt
            
            # ★ 尝试生成，如果触发内容审核则改写后重试
            try:
                image_data, used_prompt = generate_image()
            except ContentInspectionError as e:
                logger.warning(f"Content inspection failed, attempting prompt rewrite and retry...")
                
                # ★ 获取阿里云返回的具体错误信息
                api_error = e.api_error_message or str(e)
                logger.info(f"API error message: {api_error}")
                
                # 使用 DeepSeek 改写 prompt，传递具体的审核失败原因
                new_scene_desc, new_prompt = self.image_client.rewrite_prompt_for_content_safety(
                    original_prompt=final_prompt,
                    scene_desc=scene_desc,
                    character_info=char_info,
                    api_error_message=api_error,  # ★ 传递阿里云的错误信息
                )
                
                # 更新场景描述和 prompt
                scene_desc = new_scene_desc
                final_prompt = new_prompt
                illustration_prompt = new_prompt  # 用于后续保存
                
                logger.info(f"Retrying with rewritten prompt: {new_prompt[:100]}...")
                
                # 重试生成
                try:
                    image_data, used_prompt = generate_image()
                except ContentInspectionError as e2:
                    # 改写后仍然失败，抛出错误
                    logger.error(f"Content inspection still failed after rewrite: {e2}")
                    raise ImageContentError(
                        "内容审核未通过，请尝试使用其他描述方式",
                        new_prompt
                    )
            
            # Step 4: 保存图片 - 包含完整层级信息
            storage_path, storage_type = self.storage_service.save_image(
                image_data=image_data,
                game_id=game_id,
                image_type="round_scene",
                entity_name=f"{player_name}_week_{week}_round_{round_number}",
                week=week,
                round_number=round_number,
                stage=stage,
            )
            
            # Step 5: 创建 SceneImage 记录 - 包含 week 字段
            new_scene = SceneImage(
                game_id=game_id,
                week=week,  # ★ 新增：周数
                round_number=round_number,
                stage=stage,  # ★ 区分阶段
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
            logger.info(f"Round scene created: scene_id={new_scene.scene_id}, week={week}")
            
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
        """
        基于用户输入重新生成每轮场景插画
        
        流程：
        1. 使用 DeepSeek 分析故事，选择场景
        2. 结合用户自定义提示词
        3. 使用当前场景插画作为参考（保持场景一致性）
        4. 如果有玩家形象图片，也作为参考
        5. 保存新图片到数据库，更新 SceneImage 记录
        
        Args:
            game_id: 游戏ID
            round_number: 轮次
            story_text: 故事文本
            character_settings: 角色设定（前端传入，可能过期，会被数据库值覆盖）
            player_name: 玩家角色名称
            user_prompt: 用户自定义提示词/修改意见
            current_scene_id: 当前场景插画ID，作为参考
            player_image_id: 可选的玩家形象图片ID
        
        Returns:
            ImageModel 实例
        """
        from src.database.models import SceneImage, GameState, Game
        
        logger.info(f"Regenerating round {round_number} scene for game {game_id} with user prompt: {user_prompt}")
        
        # ★ 从数据库获取该游戏的 player_state，确保 character_settings 正确
        # 前端传入的 character_settings 可能是旧游戏的值，必须以数据库为准
        db_character_settings = None
        db_player_name = None
        
        try:
            # 尝试从最新的 GameState 获取
            game_state = self.db.query(GameState).filter(
                GameState.game_id == game_id
            ).order_by(GameState.state_id.desc()).first()
            
            if game_state and game_state.state_json:
                db_character_settings = game_state.state_json.get("character_settings")
                db_player_name = game_state.state_json.get("player_name")
                logger.info(f"Loaded character_settings from GameState (state_id={game_state.state_id})")
            
            # 如果没有 GameState，从 Game.initial_state 获取
            if not db_character_settings:
                game = self.db.query(Game).filter(Game.game_id == game_id).first()
                if game and game.initial_state:
                    db_character_settings = game.initial_state.get("character_settings")
                    db_player_name = game.initial_state.get("player_name")
                    logger.info(f"Loaded character_settings from Game.initial_state (game_id={game_id})")
        except Exception as e:
            logger.warning(f"Failed to load character_settings from database: {e}, using frontend value")
        
        # ★ 使用数据库中的值覆盖前端传入的值
        effective_character_settings = db_character_settings or character_settings
        effective_player_name = db_player_name or player_name
        
        # 准备角色信息
        char_info = {
            "name": effective_player_name,
            "era": self._extract_era_from_settings(effective_character_settings) or "现代",
        }
        
        logger.info(f"Using era from database: {char_info['era']}")
        
        # 提取性别和年龄
        gender = effective_character_settings.get("gender")
        if gender:
            if isinstance(gender, dict):
                char_info["gender"] = gender.get("gender", "")
            elif isinstance(gender, str):
                char_info["gender"] = gender
        
        age = effective_character_settings.get("age")
        if age:
            if isinstance(age, dict):
                char_info["age"] = age.get("age", "")
            elif isinstance(age, (int, float)):
                char_info["age"] = str(age)
        
        try:
            # Step 1: 使用 DeepSeek 分析故事选择场景
            scene_desc, illustration_prompt = self.image_client.analyze_story_for_illustration(
                story_text=story_text[:2000],
                character_info=char_info,
            )
            
            # 结合用户提示词
            combined_prompt = f"""{illustration_prompt}
用户修改意见：{user_prompt}"""
            
            logger.info(f"Selected scene: {scene_desc[:50]}...")
            
            # Step 2: 获取参考图片
            reference_urls = []
            referenced_image_ids = []
            
            # 获取当前场景插画作为参考
            current_scene = self.db.query(SceneImage).filter(
                SceneImage.scene_id == current_scene_id
            ).first()
            
            if current_scene:
                try:
                    image_data = self.storage_service.get_image_data(
                        current_scene.storage_path,
                        current_scene.storage_type
                    )
                    if image_data:
                        import base64
                        ext = current_scene.storage_path.rsplit('.', 1)[-1].lower()
                        mime_type = 'image/png' if ext == 'png' else 'image/jpeg'
                        base64_data = base64.b64encode(image_data).decode('utf-8')
                        reference_urls.append(f"data:{mime_type};base64,{base64_data}")
                        referenced_image_ids.append(current_scene_id)
                        logger.info(f"Using current scene as reference (base64, {len(image_data)} bytes)")
                except Exception as e:
                    logger.warning(f"Failed to get current scene: {e}")
            
            # 获取玩家形象图片作为参考
            # ★ 验证 player_image_id 是否属于当前 game_id，避免跨游戏数据泄漏
            if player_image_id:
                try:
                    player_image = self.db.query(ImageModel).filter(
                        ImageModel.image_id == player_image_id,
                        ImageModel.game_id == game_id  # ★ 必须属于当前游戏
                    ).first()
                    if player_image:
                        image_data = self.get_image_data(player_image)
                        import base64
                        ext = player_image.storage_path.rsplit('.', 1)[-1].lower()
                        mime_type = 'image/png' if ext == 'png' else 'image/jpeg'
                        base64_data = base64.b64encode(image_data).decode('utf-8')
                        reference_urls.append(f"data:{mime_type};base64,{base64_data}")
                        referenced_image_ids.append(player_image_id)
                        logger.info(f"Using player image {player_image_id} as reference (base64, {len(image_data)} bytes)")
                    else:
                        # ★ player_image_id 不属于当前游戏，尝试自动获取该游戏的主图
                        logger.warning(f"player_image_id={player_image_id} does not belong to game_id={game_id}, auto-selecting primary image")
                        auto_player_image = self.db.query(ImageModel).filter(
                            ImageModel.game_id == game_id,
                            ImageModel.image_type == "character",
                            ImageModel.is_primary == True
                        ).order_by(ImageModel.image_id.desc()).first()
                        if auto_player_image:
                            image_data = self.get_image_data(auto_player_image)
                            import base64
                            ext = auto_player_image.storage_path.rsplit('.', 1)[-1].lower()
                            mime_type = 'image/png' if ext == 'png' else 'image/jpeg'
                            base64_data = base64.b64encode(image_data).decode('utf-8')
                            reference_urls.append(f"data:{mime_type};base64,{base64_data}")
                            referenced_image_ids.append(auto_player_image.image_id)
                            logger.info(f"Auto-selected primary player image {auto_player_image.image_id} for game {game_id}")
                except Exception as e:
                    logger.warning(f"Failed to get player image: {e}")
            
            # Step 3: 生成场景插画
            final_prompt = f"""电影感故事场景插画。
时代背景：{char_info['era']}。
场景：{scene_desc}
{combined_prompt}
风格：写实风格，光影自然，故事感强，电影构图。"""
            
            if reference_urls:
                # 使用图生图
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
                # 文生图
                image_data, _ = self.image_client.generate_image(
                    prompt=final_prompt,
                    size="1664*928",
                    extra_params={"prompt_extend": True},
                )
            
            # Step 4: 保存图片
            storage_path, storage_type = self.storage_service.save_image(
                image_data=image_data,
                game_id=game_id,
                image_type="round_scene",
                entity_name=f"{effective_player_name}_round_{round_number}",
            )
            
            # Step 5: 更新或创建 SceneImage 记录
            if current_scene:
                # 更新现有记录
                current_scene.scene_description = scene_desc
                current_scene.final_prompt = final_prompt
                current_scene.storage_path = storage_path
                current_scene.storage_type = storage_type
                current_scene.referenced_images = referenced_image_ids
                current_scene.importance_score = "high"
                self.db.commit()
                self.db.refresh(current_scene)
                logger.info(f"Round scene updated: scene_id={current_scene.scene_id}")
                
                # 返回一个 ImageModel 兼容的对象
                return ImageModel(
                    image_id=current_scene.scene_id,
                    game_id=game_id,
                    image_type="round_scene",
                    entity_name=f"{effective_player_name}_round_{round_number}",
                    entity_key=f"round_{round_number}",
                    prompt_text=final_prompt,
                    storage_path=storage_path,
                    storage_type=storage_type,
                    metadata_json={
                        "scene_description": scene_desc,
                        "round_number": round_number,
                        "user_prompt": user_prompt,
                        "referenced_images": referenced_image_ids,
                    },
                    version=1,
                    is_active=True,
                    is_primary=True,
                )
            else:
                # 创建新记录
                new_scene = SceneImage(
                    game_id=game_id,
                    round_number=round_number,
                    scene_description=scene_desc,
                    final_prompt=final_prompt,
                    storage_path=storage_path,
                    storage_type=storage_type,
                    referenced_images=referenced_image_ids,
                    importance_score="high",
                )
                self.db.add(new_scene)
                self.db.commit()
                self.db.refresh(new_scene)
                logger.info(f"Round scene created: scene_id={new_scene.scene_id}")
                
                return ImageModel(
                    image_id=new_scene.scene_id,
                    game_id=game_id,
                    image_type="round_scene",
                    entity_name=f"{effective_player_name}_round_{round_number}",
                    entity_key=f"round_{round_number}",
                    prompt_text=final_prompt,
                    storage_path=storage_path,
                    storage_type=storage_type,
                    metadata_json={
                        "scene_description": scene_desc,
                        "round_number": round_number,
                        "user_prompt": user_prompt,
                        "referenced_images": referenced_image_ids,
                    },
                    version=1,
                    is_active=True,
                    is_primary=True,
                )
            
        except ContentInspectionError as e:
            logger.warning(f"Content inspection failed for round scene: {e}")
            raise ImageContentError(str(e), e.original_prompt)
        except ImageGenerationError as e:
            logger.error(f"Image generation failed: {e}")
            raise ImageServiceError(f"场景插画重新生成失败: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in regenerate_round_scene_image: {e}")
            self.db.rollback()
            raise ImageServiceError(f"重新生成场景插画失败: {e}")

    def _get_current_week_from_db(self, game_id: int) -> int:
        """
        从数据库获取游戏当前的周数
        
        Args:
            game_id: 游戏ID
        
        Returns:
            当前周数，默认返回 0
        """
        from src.database.models import GameState, Game
        
        try:
            # 尝试从最新的 GameState 获取
            game_state = self.db.query(GameState).filter(
                GameState.game_id == game_id
            ).order_by(GameState.state_id.desc()).first()
            
            if game_state and game_state.state_json:
                week = game_state.state_json.get("week")
                if week is not None:
                    return week
            
            # 如果没有 GameState，从 Game.initial_state 获取
            game = self.db.query(Game).filter(Game.game_id == game_id).first()
            if game and game.initial_state:
                week = game.initial_state.get("week")
                if week is not None:
                    return week
        except Exception as e:
            logger.warning(f"Failed to get current week from database: {e}")
        
        return 0  # 默认返回 0
