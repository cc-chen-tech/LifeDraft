"""Image generator module.

负责图像生成的核心功能，包括文生图和图生图。
"""

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import requests  # type: ignore[import-untyped]
from cachetools import TTLCache  # type: ignore[import-untyped]

from config.settings import settings
from src.ai.image_config import (
    CHARACTER_VARIANTS,
    DEFAULT_EDIT_NEGATIVE_PROMPT,
    DEFAULT_NEGATIVE_PROMPT,
    create_retry_session,
    get_image_edit_models,
    get_text_to_image_models,
)
from src.ai.image_exceptions import ContentInspectionError, ImageGenerationError

logger = logging.getLogger(__name__)

# M-09: 图片生成结果缓存 - 模块级别 TTL 缓存
# 缓存最多 100 个图片，TTL 1 小时
_image_cache: TTLCache = TTLCache(maxsize=100, ttl=3600)


def _get_prompt_hash(
    prompt: str, size: str, extra_params: Optional[Dict] = None
) -> str:
    """生成 prompt 的哈希值作为缓存 key"""
    cache_key = f"{prompt}|{size}|{extra_params}"
    return hashlib.md5(cache_key.encode()).hexdigest()


class ImageGenerator:
    """图像生成器 - 支持文生图和图生图，支持模型降级"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        初始化图像生成器

        Args:
            api_key: API密钥（默认从settings获取）
            base_url: API基础URL（默认从settings获取）
            model: 模型名称（默认从settings获取）
        """
        self.api_key = api_key or settings.get_image_api_key()
        self.base_url = base_url or settings.get_image_api_base_url()
        self.model = model or settings.IMAGE_MODEL
        self.timeout = settings.IMAGE_GENERATION_TIMEOUT
        self.max_retries = settings.IMAGE_MAX_RETRIES

        # 使用带重试策略的 session 来改善 SSL 连接稳定性
        self.session = create_retry_session(retries=self.max_retries)

        # 从配置解析模型降级列表
        self.text_to_image_models = get_text_to_image_models()
        self.image_edit_models = get_image_edit_models()

        if not self.api_key:
            raise ValueError(
                "Image API key is required. Set IMAGE_API_KEY or OPENAI_API_KEY in environment."
            )

        if not self.base_url:
            raise ValueError(
                "Image API base URL is required. Set IMAGE_API_BASE_URL or OPENAI_BASE_URL in environment."
            )

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
        """
        生成图片

        支持 DashScope API（阿里云千问图像模型），支持模型降级
        M-09: 支持基于 prompt 的缓存，避免重复调用 API

        Args:
            prompt: 图片描述prompt
            size: 图片尺寸 (DashScope支持: 1664*928, 1472*1104, 1328*1328, 1104*1472, 928*1664)
            style: 风格（DashScope不支持）
            quality: 质量（DashScope不支持）
            n: 生成数量 - DashScope固定为1
            response_format: 返回格式 - DashScope返回URL
            extra_params: 额外参数（如 negative_prompt, seed）

        Returns:
            Tuple[bytes, str]: (图片二进制数据, 使用的prompt)

        Raises:
            ImageGenerationError: 生成失败
        """
        # M-09: 检查缓存
        cache_key = _get_prompt_hash(prompt, size, extra_params)
        cached_result = _image_cache.get(cache_key)
        if cached_result is not None:
            logger.info(f"[ImageCache] Cache hit for prompt hash: {cache_key[:8]}...")
            return cached_result

        last_error = None

        # 支持模型降级：尝试每个模型
        is_last_model = False
        for model_idx, fallback_model in enumerate(self.text_to_image_models):
            is_last_model = model_idx == len(self.text_to_image_models) - 1

            if model_idx > 0:
                logger.warning(
                    f"[Model Fallback] Switching to fallback model: {fallback_model}"
                )

            for attempt in range(self.max_retries):
                try:
                    result = self._call_api(
                        prompt=prompt,
                        size=size,
                        style=style,
                        quality=quality,
                        n=n,
                        response_format=response_format,
                        extra_params=extra_params,
                        model=fallback_model,
                    )

                    # 解析 DashScope API 响应
                    output = result.get("output", {})
                    choices = output.get("choices", [])

                    if not choices:
                        raise ImageGenerationError("No choices in response")

                    content = choices[0].get("message", {}).get("content", [])
                    if not content:
                        raise ImageGenerationError("No content in response")

                    image_url = content[0].get("image")
                    if not image_url:
                        raise ImageGenerationError("No image URL in response")

                    # 从 URL 下载图片
                    logger.info(
                        f"Got image URL from DashScope (model={fallback_model}), downloading..."
                    )
                    image_bytes = self._download_image(image_url)
                    logger.info(
                        f"Successfully downloaded image: {len(image_bytes)} bytes"
                    )

                    # M-09: 存入缓存
                    cached_result = (image_bytes, prompt)
                    _image_cache[cache_key] = cached_result
                    logger.debug(
                        f"[ImageCache] Cached image with key: {cache_key[:8]}..."
                    )

                    return cached_result

                except (
                    requests.exceptions.RequestException,
                    requests.exceptions.Timeout,
                ) as e:
                    last_error = e
                    error_str = str(e)
                    logger.warning(
                        f"Image generation attempt {attempt + 1}/{self.max_retries} with model {fallback_model} failed: {e}"
                    )

                    # 检测 429 速率限制错误
                    is_rate_limit = (
                        "429" in error_str
                        or "RateQuota" in error_str
                        or "rate limit" in error_str.lower()
                    )

                    if is_rate_limit:
                        if not is_last_model:
                            # 不是最后一个模型：直接换模型，不等待
                            logger.warning(
                                "[Model Fallback] Rate limit detected, switching to next model immediately..."
                            )
                            break  # 跳出重试循环，进入下一个模型
                        else:
                            # 是最后一个模型：只能等待重试
                            wait_time = 15 * (attempt + 1)  # 15, 30, 45 秒递增
                            logger.warning(
                                f"Rate limit detected on last model, waiting {wait_time} seconds before retry..."
                            )
                            if attempt < self.max_retries - 1:
                                time.sleep(wait_time)
                    elif attempt < self.max_retries - 1:
                        time.sleep(2**attempt)  # 指数退避
                    else:
                        # 非速率限制错误，不尝试其他模型
                        break
                except Exception as e:
                    last_error = e
                    logger.exception(
                        f"Unexpected error in image generation attempt {attempt + 1}/{self.max_retries} with model {fallback_model}: {e}"
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(2**attempt)
                    else:
                        break

        raise ImageGenerationError(
            f"Failed to generate image after trying all models: {last_error}"
        )

    def generate_image_with_url(
        self,
        prompt: str,
        size: str = "1328*1328",
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bytes, str, str]:
        """
        生成图片并返回 URL（用于后续图生图）

        Args:
            prompt: 图片描述
            size: 图片尺寸
            extra_params: 额外参数

        Returns:
            Tuple[bytes, str, str]: (图片二进制数据, prompt, 图片URL)
        """
        result = self._call_api(
            prompt=prompt,
            size=size,
            extra_params=extra_params,
        )

        output = result.get("output", {})
        choices = output.get("choices", [])

        if not choices:
            raise ImageGenerationError("No choices in response")

        content = choices[0].get("message", {}).get("content", [])
        if not content:
            raise ImageGenerationError("No content in response")

        image_url = content[0].get("image")
        if not image_url:
            raise ImageGenerationError("No image URL in response")

        # 下载图片
        logger.info(f"Got image URL: {image_url}")
        image_bytes = self._download_image(image_url)

        return image_bytes, prompt, image_url

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
        """
        调用图像生成API

        Args:
            prompt: 图片描述
            size: 图片尺寸
            style: 风格
            quality: 质量
            n: 生成数量
            response_format: 返回格式
            extra_params: 额外参数
            model: 可选模型名称

        Returns:
            API响应字典
        """
        # 构建请求URL
        url = f"{(self.base_url or '').rstrip('/')}/generation"

        # DashScope API 格式 - 尺寸格式确保是 "W*H"
        dashscope_size = size if "*" in size else size.replace("x", "*")

        # 使用传入的模型或默认模型
        use_model = model or self.model

        # 构建请求体 (DashScope 格式)
        payload = {
            "model": use_model,
            "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
            "parameters": {
                "size": dashscope_size,
                "n": n,
                "prompt_extend": True,  # 开启智能改写
                "watermark": False,
            },
        }

        # 添加反向提示词
        params: Dict[str, Any] = payload["parameters"]  # type: ignore[assignment]
        if extra_params and extra_params.get("negative_prompt"):
            params["negative_prompt"] = extra_params["negative_prompt"]
        else:
            params["negative_prompt"] = DEFAULT_NEGATIVE_PROMPT

        # 合并额外参数
        if extra_params:
            for key in ["seed", "prompt_extend"]:
                if key in extra_params:
                    params[key] = extra_params[key]

        # 构建请求头
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.debug(
            f"Calling DashScope image API: {url}, model: {self.model}, size: {dashscope_size}"
        )

        response = self.session.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )

        if response.status_code != 200:
            error_msg = f"API returned {response.status_code}: {response.text}"
            logger.error(error_msg)
            raise ImageGenerationError(error_msg)

        return response.json()

    def _download_image(self, url: str) -> bytes:
        """下载图片"""
        response = self.session.get(url, timeout=self.timeout)
        if response.status_code != 200:
            raise ImageGenerationError(
                f"Failed to download image: {response.status_code}"
            )
        return response.content

    def edit_image(
        self,
        reference_image: str,
        prompt: str,
        size: str = "928*1664",
        num_images: int = 1,
    ) -> List[Tuple[bytes, str]]:
        """
        图生图：基于参考图片生成新图片

        使用千问图像编辑模型，保证人物一致性，支持模型降级

        Args:
            reference_image: 参考图片URL（必须是可访问的URL）
            prompt: 编辑指令
            size: 图片尺寸
            num_images: 生成数量（1-6）

        Returns:
            List of (图片二进制数据, prompt) 元组

        Raises:
            ContentInspectionError: 内容审核失败
            ImageGenerationError: 其他生成错误
        """
        logger.debug(f"Editing image with prompt: {prompt}")

        last_error = None

        # 支持模型降级：尝试每个图生图模型
        is_last_model = False
        for model_idx, fallback_model in enumerate(self.image_edit_models):
            is_last_model = model_idx == len(self.image_edit_models) - 1

            if model_idx > 0:
                logger.warning(
                    f"[Model Fallback] Switching to fallback edit model: {fallback_model}"
                )

            for attempt in range(self.max_retries):
                try:
                    result = self._call_edit_api(
                        reference_image=reference_image,
                        prompt=prompt,
                        size=size,
                        num_images=num_images,
                        model=fallback_model,
                    )

                    # 解析响应
                    output = result.get("output", {})
                    choices = output.get("choices", [])

                    if not choices:
                        raise ImageGenerationError("No choices in response")

                    content = choices[0].get("message", {}).get("content", [])
                    if not content:
                        raise ImageGenerationError("No content in response")

                    results = []
                    for i, item in enumerate(content):
                        image_url = item.get("image")
                        if image_url:
                            image_bytes = self._download_image(image_url)
                            results.append((image_bytes, f"{prompt} (variant {i+1})"))
                            logger.info(f"Downloaded edited image {i+1}/{len(content)}")

                    return results

                except ContentInspectionError:
                    # 内容审核错误不重试，直接抛出
                    raise
                except (
                    requests.exceptions.RequestException,
                    requests.exceptions.Timeout,
                ) as e:
                    last_error = e
                    error_str = str(e)
                    logger.warning(
                        f"Image edit attempt {attempt + 1}/{self.max_retries} with model {fallback_model} failed: {e}"
                    )

                    # 检测 429 速率限制错误
                    is_rate_limit = (
                        "429" in error_str
                        or "RateQuota" in error_str
                        or "rate limit" in error_str.lower()
                    )

                    if is_rate_limit:
                        if not is_last_model:
                            # 不是最后一个模型：直接换模型，不等待
                            logger.warning(
                                "[Model Fallback] Rate limit detected, switching to next model immediately..."
                            )
                            break  # 跳出重试循环，进入下一个模型
                        else:
                            # 是最后一个模型：只能等待重试
                            wait_time = 15 * (attempt + 1)  # 15, 30, 45 秒递增
                            logger.warning(
                                f"Rate limit detected on last model, waiting {wait_time} seconds before retry..."
                            )
                            if attempt < self.max_retries - 1:
                                time.sleep(wait_time)
                    elif attempt < self.max_retries - 1:
                        time.sleep(2**attempt)
                    else:
                        # 非速率限制错误，不尝试其他模型
                        break
                except Exception as e:
                    last_error = e
                    logger.exception(
                        f"Unexpected error in image edit attempt {attempt + 1}/{self.max_retries} with model {fallback_model}: {e}"
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(2**attempt)
                    else:
                        break

        raise ImageGenerationError(
            f"Failed to edit image after trying all models: {last_error}"
        )

    def _call_edit_api(
        self,
        reference_image: str,
        prompt: str,
        size: str = "928*1664",
        num_images: int = 1,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        调用图生图API

        Args:
            reference_image: 参考图片URL
            prompt: 编辑指令
            size: 图片尺寸
            num_images: 生成数量
            model: 可选模型名称

        Returns:
            API响应
        """
        url = f"{(self.base_url or '').rstrip('/')}/generation"

        # 尺寸格式
        dashscope_size = size if "*" in size else size.replace("x", "*")

        # 使用传入的模型或默认模型
        use_model = model or self.image_edit_models[0]

        # 构建请求体 - 图生图格式
        payload = {
            "model": use_model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"image": reference_image},  # 参考图片
                            {"text": prompt},  # 编辑指令
                        ],
                    }
                ]
            },
            "parameters": {
                "n": min(max(1, num_images), 6),  # 1-6张
                "size": dashscope_size,
                "negative_prompt": DEFAULT_EDIT_NEGATIVE_PROMPT,
                "prompt_extend": True,
                "watermark": False,
            },
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.debug(
            f"Calling image edit API: model={use_model}, size={dashscope_size}"
        )

        response = self.session.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )

        if response.status_code != 200:
            error_msg = f"Edit API returned {response.status_code}: {response.text}"
            logger.error(error_msg)

            # 检测内容审核错误
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    error_code = error_data.get("code", "")
                    if error_code == "DataInspectionFailed":
                        # 提取阿里云返回的完整错误信息
                        api_message = error_data.get("message", "")
                        full_error = f"{error_code}: {api_message}"
                        logger.warning(f"Content inspection failed: {full_error}")
                        raise ContentInspectionError(
                            "您的修改请求触发了内容安全审核，请尝试使用其他描述方式",
                            original_prompt=prompt,
                            api_error_message=full_error,
                        )
                except ContentInspectionError:
                    raise
                except (KeyError, TypeError) as e:
                    logger.warning(
                        f"Failed to parse content inspection error response: {e}"
                    )
                except Exception as e:
                    logger.exception(
                        f"Unexpected error parsing API error response: {e}"
                    )

            raise ImageGenerationError(error_msg)

        return response.json()

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
        prompt_builder=None,  # 注入 prompt builder
    ) -> Tuple[List[Tuple[bytes, str]], Optional[str]]:
        """
        生成人物全身像（保证人物一致性）

        流程：
        1. 如果有参考图片URL，直接基于它生成变体
        2. 如果没有，先生成1张主图，再基于主图生成变体

        Args:
            name: 人物名称
            description: 人物描述
            era: 时代背景
            style_hint: 风格提示
            num_images: 总图片数量（1-6，包含主图）
            size: 图片尺寸
            reference_image_url: 已有的参考图片URL（用于重新生成）
            feedback: 用户修改意见（会被特别强调）
            prompt_builder: Prompt 构建器实例

        Returns:
            Tuple[List of (图片数据, prompt), 主图URL]
            主图URL用于后续重新生成
        """
        # 延迟导入避免循环依赖
        if prompt_builder is None:
            from src.ai.image_prompt_builder import ImagePromptBuilder

            prompt_builder = ImagePromptBuilder()

        results = []
        primary_image_url = reference_image_url

        if reference_image_url:
            # 有参考图片，prompt应该简洁，重点是用户的修改要求
            logger.info(
                f"Generating {num_images} image(s) from reference image, feedback: {feedback}"
            )

            for i in range(num_images):
                # 图生图prompt：简洁，只关注修改要求
                prompt_parts = []

                # 用户修改要求 - 这是最重要的
                if feedback:
                    prompt_parts.append(f"{feedback}。")

                # 只保留基本要求：全身像
                prompt_parts.append("全身像，脚部可见。")

                prompt = "".join(prompt_parts)

                logger.debug(f"Edit prompt: {prompt}")

                try:
                    edited = self.edit_image(
                        reference_image=reference_image_url,
                        prompt=prompt,
                        size=size,
                        num_images=1,
                    )
                    results.extend(edited)
                    logger.info(f"Generated variant {i + 1}/{num_images}")
                except (
                    requests.exceptions.RequestException,
                    ImageGenerationError,
                ) as e:
                    logger.warning(f"Failed to generate variant {i + 1}: {e}")
                except Exception as e:
                    logger.exception(
                        f"Unexpected error generating variant {i + 1}: {e}"
                    )
        else:
            # 没有参考图片，先生成主图
            logger.info(f"Generating primary image for {name}, feedback: {feedback}")

            # 生成主图
            main_prompt = prompt_builder.build_character_prompt(
                name,
                description,
                era,
                style_hint,
                "站立姿态，正面朝向，自然光线",
                feedback,
            )
            try:
                main_image_bytes, main_prompt_used, primary_image_url = (
                    self.generate_image_with_url(
                        prompt=main_prompt,
                        size=size,
                    )
                )
                results.append((main_image_bytes, main_prompt_used))
                logger.info(f"Generated primary image, URL: {primary_image_url}")

                # 基于主图生成变体
                num_variants = num_images - 1
                if num_variants > 0:
                    logger.info(
                        f"Generating {num_variants} variants from primary image"
                    )

                    for i in range(num_variants):
                        variant = CHARACTER_VARIANTS[i % len(CHARACTER_VARIANTS)]
                        prompt = f"{variant}。保持人物的外貌特征不变，时代背景：{era}。"
                        if style_hint:
                            prompt += f"风格：{style_hint}。"

                        try:
                            edited = self.edit_image(
                                reference_image=primary_image_url,
                                prompt=prompt,
                                size=size,
                                num_images=1,
                            )
                            results.extend(edited)
                            logger.info(f"Generated variant {i + 1}/{num_variants}")
                        except (
                            requests.exceptions.RequestException,
                            ImageGenerationError,
                        ) as e:
                            logger.warning(f"Failed to generate variant {i + 1}: {e}")
                        except Exception as e:
                            logger.exception(
                                f"Unexpected error generating variant {i + 1}: {e}"
                            )

            except (requests.exceptions.RequestException, ImageGenerationError) as e:
                logger.error(f"Failed to generate primary image: {e}")
                raise
            except Exception as e:
                logger.exception(f"Unexpected error generating primary image: {e}")
                raise

        logger.info(f"Total images generated: {len(results)}")
        return results, primary_image_url

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
        """
        基于参考图片生成人物变体（保证人物一致性）

        Args:
            reference_image_url: 参考图片URL
            name: 人物名称
            description: 人物描述
            era: 时代背景
            style_hint: 风格提示
            num_variants: 变体数量（1-5）
            size: 图片尺寸

        Returns:
            List of (图片二进制数据, prompt) 元组
        """
        # 预设的场景变体
        VARIANTS = [
            "这个人站在街道上，正面朝向，自然光线",
            "这个人正在行走，侧面视角，动态感",
            "这个人坐在室内，休闲姿态，温馨氛围",
            "这个人在户外场景，远景构图，环境清晰",
            "这个人的半身特写，突出表情和气质",
        ]

        variants = VARIANTS[:num_variants]
        results = []

        for i, variant in enumerate(variants):
            prompt = f"{variant}。保持人物的外貌特征不变，时代背景：{era}。"
            if style_hint:
                prompt += f"风格：{style_hint}。"

            try:
                # 每次生成1张变体
                edited = self.edit_image(
                    reference_image=reference_image_url,
                    prompt=prompt,
                    size=size,
                    num_images=1,
                )
                results.extend(edited)
                logger.info(f"Generated character variant {i + 1}/{num_variants}")
            except (requests.exceptions.RequestException, ImageGenerationError) as e:
                logger.warning(f"Failed to generate variant {i + 1}: {e}")
            except Exception as e:
                logger.exception(f"Unexpected error generating variant {i + 1}: {e}")

        return results
