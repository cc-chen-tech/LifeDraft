"""Image generation client - Facade for backward compatibility.

This module provides the ImageClient class as a unified facade that delegates
to the specialized modules:
- image_generator.py: Core image generation (text-to-image, image-to-image)
- image_prompt_builder.py: Prompt construction and enhancement
- image_config.py: Configuration and constants
- image_exceptions.py: Exception classes

All existing consumers can continue to use ImageClient without modification.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

# Re-export settings for backward compatibility (needed by tests)

# Re-export utility function for backward compatibility

# Re-export exceptions for backward compatibility
from src.ai.image_exceptions import ImageGenerationError

# Import internal modules
from src.ai.image_generator import ImageGenerator
from src.ai.image_prompt_builder import DeepSeekPromptEnhancer, ImagePromptBuilder

logger = logging.getLogger(__name__)


class ImageClient:  # noqa: E303
    """图像生成客户端 - Facade 模式，委托给专门的模块

    此类作为向后兼容的统一入口，内部委托给：
    - ImageGenerator: 图像生成核心功能
    - ImagePromptBuilder: Prompt 构建
    - DeepSeekPromptEnhancer: DeepSeek 增强功能

    所有现有的消费者可以继续使用 ImageClient 而无需修改导入。
    """

    # 保留原有的类属性以保持兼容
    CHARACTER_POSES = [
        "站立姿态，正面朝向，日常便装，背景是日常生活场景，自然光线",
        "行走姿态，侧面视角，外出服装，背景是街道或户外场景，动态感",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        初始化图像生成客户端

        Args:
            api_key: API密钥（默认从settings获取）
            base_url: API基础URL（默认从settings获取）
            model: 模型名称（默认从settings获取）
        """
        # 初始化内部组件
        self._generator = ImageGenerator(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        self._prompt_builder = ImagePromptBuilder()
        self._deepseek_enhancer = DeepSeekPromptEnhancer()

        # 暴露 generator 的属性以保持兼容
        self.api_key = self._generator.api_key
        self.base_url = self._generator.base_url
        self.model = self._generator.model
        self.timeout = self._generator.timeout
        self.max_retries = self._generator.max_retries
        self.session = self._generator.session
        self.text_to_image_models = self._generator.text_to_image_models
        self.image_edit_models = self._generator.image_edit_models

    # ==================== 委托给 DeepSeekPromptEnhancer ====================

    def generate_image_prompt_with_deepseek(
        self,
        character_info: Dict[str, Any],
    ) -> str:
        """使用 DeepSeek 生成图片描述 prompt"""
        return self._deepseek_enhancer.generate_image_prompt_with_deepseek(
            character_info
        )

    def analyze_story_for_illustration(
        self,
        story_text: str,
        character_info: Dict[str, Any],
    ) -> Tuple[str, str]:
        """使用 DeepSeek 分析故事，选择最重要/最视觉化的场景"""
        return self._deepseek_enhancer.analyze_story_for_illustration(
            story_text, character_info
        )

    def rewrite_prompt_for_content_safety(
        self,
        original_prompt: str,
        scene_desc: str,
        character_info: Dict[str, Any],
        api_error_message: Optional[str] = None,
    ) -> Tuple[str, str]:
        """使用 DeepSeek 改写 prompt 以规避内容审核"""
        return self._deepseek_enhancer.rewrite_prompt_for_content_safety(
            original_prompt, scene_desc, character_info, api_error_message
        )

    def generate_appearance_anchor(
        self,
        name: str,
        description: str,
        era: str = "现代",
        character_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """生成人物外貌特征锚点（文本层面）"""
        return self._deepseek_enhancer.generate_appearance_anchor(
            name, description, era, character_settings
        )

    # ==================== 委托给 ImagePromptBuilder ====================

    def _build_fallback_prompt(self, character_info: Dict[str, Any]) -> str:
        """DeepSeek 不可用时的备选 prompt 生成"""
        return self._prompt_builder.build_fallback_prompt(character_info)

    def _build_character_prompt(
        self,
        name: str,
        description: str,
        era: str,
        style_hint: Optional[str] = None,
        pose_hint: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> str:
        """构建人物形象prompt"""
        return self._prompt_builder.build_character_prompt(
            name, description, era, style_hint, pose_hint, feedback
        )

    def _build_location_prompt(
        self,
        name: str,
        description: str,
        era: str,
        style_hint: Optional[str] = None,
    ) -> str:
        """构建地点prompt"""
        return self._prompt_builder.build_location_prompt(
            name, description, era, style_hint
        )

    def _build_item_prompt(
        self,
        name: str,
        description: str,
        era: str,
        style_hint: Optional[str] = None,
    ) -> str:
        """构建物品prompt"""
        return self._prompt_builder.build_item_prompt(
            name, description, era, style_hint
        )

    def _build_scene_prompt(
        self,
        scene_description: str,
        characters: Optional[list],
        era: str,
        style_hint: Optional[str] = None,
    ) -> str:
        """构建场景prompt"""
        return self._prompt_builder.build_scene_prompt(
            scene_description, characters, era, style_hint
        )

    def _simplify_prompt(
        self, original_prompt: str, scene_desc: str
    ) -> Tuple[str, str]:
        """简化 prompt 作为备选方案"""
        return self._prompt_builder.simplify_prompt(original_prompt, scene_desc)

    def _fallback_scene_selection(
        self,
        story_text: str,
        character_info: Dict[str, Any],
    ) -> Tuple[str, str]:
        """备选：基于规则选择场景"""
        return self._deepseek_enhancer._fallback_scene_selection(
            story_text, character_info
        )

    def _fallback_appearance_anchor(
        self,
        name: str,
        description: str,
        era: str = "现代",
        character_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """当API不可用时，从描述中提取基础锚点信息"""
        return self._deepseek_enhancer._fallback_appearance_anchor(
            name, description, era, character_settings
        )

    # ==================== 委托给 ImageGenerator ====================

    def generate_image(
        self,
        prompt: str,
        size: str = "1328*1328",
        style: Optional[str] = None,
        quality: str = "standard",
        n: int = 1,
        response_format: str = "b64_json",
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bytes, str]:
        """生成图片"""
        return self._generator.generate_image(
            prompt, size, style, quality, n, response_format, extra_params
        )

    def generate_image_with_url(
        self,
        prompt: str,
        size: str = "1328*1328",
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bytes, str, str]:
        """生成图片并返回 URL"""
        return self._generator.generate_image_with_url(prompt, size, extra_params)

    def _call_api(
        self,
        prompt: str,
        size: str = "1328*1328",
        style: Optional[str] = None,
        quality: str = "standard",
        n: int = 1,
        response_format: str = "b64_json",
        extra_params: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """调用图像生成API"""
        return self._generator._call_api(
            prompt, size, style, quality, n, response_format, extra_params, model
        )

    def _download_image(self, url: str) -> bytes:
        """下载图片"""
        return self._generator._download_image(url)

    def edit_image(
        self,
        reference_image: str,
        prompt: str,
        size: str = "928*1664",
        num_images: int = 1,
    ) -> List[Tuple[bytes, str]]:
        """图生图：基于参考图片生成新图片"""
        return self._generator.edit_image(reference_image, prompt, size, num_images)

    def _call_edit_api(
        self,
        reference_image: str,
        prompt: str,
        size: str = "928*1664",
        num_images: int = 1,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """调用图生图API"""
        return self._generator._call_edit_api(
            reference_image, prompt, size, num_images, model
        )

    def generate_character_images(
        self,
        name: str,
        description: str,
        era: str = "现代",
        style_hint: Optional[str] = None,
        num_images: int = 2,
        size: str = "928*1664",
        reference_image_url: Optional[str] = None,
        feedback: Optional[str] = None,
    ) -> Tuple[List[Tuple[bytes, str]], Optional[str]]:
        """生成人物全身像（保证人物一致性）"""
        return self._generator.generate_character_images(
            name,
            description,
            era,
            style_hint,
            num_images,
            size,
            reference_image_url,
            feedback,
            self._prompt_builder,  # 注入 prompt builder
        )

    def generate_character_images_with_reference(
        self,
        reference_image_url: str,
        name: str,
        description: str,
        era: str = "现代",
        style_hint: Optional[str] = None,
        num_variants: int = 1,
        size: str = "928*1664",
    ) -> List[Tuple[bytes, str]]:
        """基于参考图片生成人物变体"""
        return self._generator.generate_character_images_with_reference(
            reference_image_url, name, description, era, style_hint, num_variants, size
        )

    # ==================== 高层业务方法 ====================

    def generate_character_image(
        self,
        name: str,
        description: str,
        era: str = "现代",
        style_hint: Optional[str] = None,
        size: str = "1328*1328",
    ) -> Tuple[bytes, str]:
        """
        生成人物形象图片

        Args:
            name: 人物名称
            description: 人物描述
            era: 时代背景
            style_hint: 风格提示
            size: 图片尺寸

        Returns:
            Tuple[bytes, str]: (图片二进制数据, 使用的prompt)
        """
        prompt = self._build_character_prompt(name, description, era, style_hint)
        return self.generate_image(
            prompt=prompt,
            size=size,
            extra_params={"prompt_extend": True},
        )

    def generate_location_image(
        self,
        name: str,
        description: str,
        era: str = "现代",
        style_hint: Optional[str] = None,
        size: str = "1664*928",
    ) -> Tuple[bytes, str]:
        """
        生成地点/地标图片

        Args:
            name: 地点名称
            description: 地点描述
            era: 时代背景
            style_hint: 风格提示
            size: 图片尺寸

        Returns:
            Tuple[bytes, str]: (图片二进制数据, 使用的prompt)
        """
        prompt = self._build_location_prompt(name, description, era, style_hint)
        return self.generate_image(
            prompt=prompt,
            size=size,
            extra_params={"prompt_extend": True},
        )

    def generate_item_image(
        self,
        name: str,
        description: str,
        era: str = "现代",
        style_hint: Optional[str] = None,
        size: str = "1328*1328",
    ) -> Tuple[bytes, str]:
        """
        生成物品图片

        Args:
            name: 物品名称
            description: 物品描述
            era: 时代背景
            style_hint: 风格提示
            size: 图片尺寸

        Returns:
            Tuple[bytes, str]: (图片二进制数据, 使用的prompt)
        """
        prompt = self._build_item_prompt(name, description, era, style_hint)
        return self.generate_image(
            prompt=prompt,
            size=size,
            extra_params={"prompt_extend": True},
        )

    def generate_scene_image(
        self,
        scene_description: str,
        characters: Optional[list] = None,
        era: str = "现代",
        style_hint: Optional[str] = None,
        size: str = "1664*928",
    ) -> Tuple[bytes, str]:
        """
        生成场景插图

        Args:
            scene_description: 场景描述
            characters: 场景中的人物列表
            era: 时代背景
            style_hint: 风格提示
            size: 图片尺寸

        Returns:
            Tuple[bytes, str]: (图片二进制数据, 使用的prompt)
        """
        prompt = self._build_scene_prompt(
            scene_description, characters, era, style_hint
        )
        return self.generate_image(
            prompt=prompt,
            size=size,
            extra_params={"prompt_extend": True},
        )

    def generate_opening_illustration(
        self,
        story_text: str,
        character_info: Dict[str, Any],
        reference_image_url: Optional[str] = None,
        size: str = "1664*928",
    ) -> Tuple[bytes, str, str]:
        """
        生成开场故事插画

        流程：
        1. 使用 DeepSeek 分析故事，选择场景并生成提示词
        2. 如果有参考图片，使用 image-edit 模型
        3. 如果没有参考图片，使用文生图

        Args:
            story_text: 开场故事文本
            character_info: 角色信息
            reference_image_url: 可选的人物形象图片URL
            size: 图片尺寸

        Returns:
            Tuple[bytes, str, str]: (图片数据, 提示词, 场景描述)
        """
        logger.info(
            f"Generating opening illustration, has_reference={bool(reference_image_url)}"
        )

        # Step 1: 分析故事，选择场景
        scene_desc, illustration_prompt = self.analyze_story_for_illustration(
            story_text,
            character_info,
        )

        logger.info(f"Selected scene: {scene_desc[:50]}...")
        logger.debug(f"Illustration prompt: {illustration_prompt[:100]}...")

        # Step 2: 生成插画
        if reference_image_url:
            # 使用 image-edit 模型，将人物融入场景
            edit_prompt = f"""将人物融入以下场景：{scene_desc}。
保持人物的外貌特征和服装不变。
{illustration_prompt}"""

            results = self.edit_image(
                reference_image=reference_image_url,
                prompt=edit_prompt,
                size=size,
                num_images=1,
            )

            if results:
                image_data, _ = results[0]
                return image_data, edit_prompt, scene_desc
            else:
                raise ImageGenerationError(
                    "Failed to generate illustration with reference"
                )
        else:
            # 使用文生图
            image_data, prompt_used = self.generate_image(
                prompt=illustration_prompt,
                size=size,
                extra_params={"prompt_extend": True},
            )
            return image_data, prompt_used, scene_desc
