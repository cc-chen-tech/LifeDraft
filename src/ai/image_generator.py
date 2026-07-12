"""Image generator module.

负责图像生成的核心功能，包括文生图和图生图。
"""

import base64
import binascii
import hashlib
import logging
import os
import time
from math import gcd
from typing import Any, Dict, List, Optional, Tuple

import requests
from cachetools import TTLCache

from config.settings import settings
from src.ai.image_config import (CHARACTER_VARIANTS, create_retry_session,
                                 get_image_edit_models,
                                 get_text_to_image_models)
from src.ai.image_exceptions import (ContentInspectionError,
                                     ImageGenerationError,
                                     ImageProviderCategory,
                                     ImageProviderError)

logger = logging.getLogger(__name__)

# M-09: 图片生成结果缓存 - 模块级别 TTL 缓存
# 缓存最多 100 个图片，TTL 1 小时
_image_cache: TTLCache[str, Tuple[bytes, str]] = TTLCache(maxsize=100, ttl=3600)

_LOCAL_E2E_IMAGE_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04"
    b"\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}

_MINIMAX_ASPECT_RATIOS: Tuple[Tuple[str, int, int], ...] = (
    ("1:1", 1, 1),
    ("16:9", 16, 9),
    ("4:3", 4, 3),
    ("3:2", 3, 2),
    ("2:3", 2, 3),
    ("3:4", 3, 4),
    ("9:16", 9, 16),
    ("21:9", 21, 9),
)

_MINIMAX_ERROR_POLICIES: Dict[int, Tuple[ImageProviderCategory, bool, str]] = {
    1001: ("timeout", True, "图片生成服务响应超时，请稍后再试"),
    1002: ("rate_limit", True, "图片生成请求较多，请稍后再试"),
    1004: ("authentication", False, "图片生成服务暂时不可用，请联系管理员"),
    1008: ("capacity", False, "图片生成额度暂时不可用，请稍后再试"),
    1024: ("upstream", True, "图片生成服务暂时不可用，请稍后再试"),
    1033: ("upstream", True, "图片生成服务暂时不可用，请稍后再试"),
    2013: ("invalid_request", False, "图片生成参数无效，请调整后重试"),
    2049: ("authentication", False, "图片生成服务暂时不可用，请联系管理员"),
    2056: ("capacity", False, "图片生成额度暂时不可用，请稍后再试"),
}


def _get_prompt_hash(
    prompt: str,
    size: str,
    extra_params: Optional[Dict[str, Any]] = None,
) -> str:
    """生成 prompt 的哈希值作为缓存 key"""
    cache_key = f"{prompt}|{size}|{extra_params}"
    return hashlib.md5(cache_key.encode(), usedforsecurity=False).hexdigest()


def _parse_size(size: str) -> Optional[Tuple[int, int]]:
    normalized = size.lower().replace("x", "*")
    parts = normalized.split("*")
    if len(parts) != 2:
        return None
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def _closest_aspect_ratio(width: int, height: int) -> str:
    simplified = (width // gcd(width, height), height // gcd(width, height))
    for label, ratio_width, ratio_height in _MINIMAX_ASPECT_RATIOS:
        if simplified == (ratio_width, ratio_height):
            return label

    actual = width / height
    return min(
        _MINIMAX_ASPECT_RATIOS,
        key=lambda item: abs(actual - (item[1] / item[2])),
    )[0]


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
            logger.warning(
                "Image API key is not configured; image generation calls will fail until configured"
            )
        if not self.base_url:
            logger.warning(
                "Image API base URL is not configured; image generation calls will fail until configured"
            )

    def require_generation_config(self) -> None:
        """Fail only when a real image generation provider call is requested."""
        if not self.api_key or not self.base_url:
            raise ImageProviderError(
                code="image_provider_not_configured",
                category="configuration",
                retryable=False,
                public_message="图片生成服务尚未配置，请联系管理员",
            )

    def _e2e_local_image_enabled(self) -> bool:
        return _truthy_env("MINIMAX_E2E_LOCAL_IMAGE")

    def _local_e2e_image_url(self) -> str:
        encoded = base64.b64encode(_LOCAL_E2E_IMAGE_BYTES).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    def _image_generation_url(self) -> str:
        """Return the MiniMax image generation endpoint for flexible base URLs."""
        base_url = (self.base_url or "").rstrip("/")
        if base_url.endswith("/v1/image_generation") or base_url.endswith("/image_generation"):
            return base_url
        if base_url.endswith("/v1"):
            return f"{base_url}/image_generation"
        return f"{base_url}/v1/image_generation"

    def _response_format_for_minimax(
        self,
        response_format: str,
        extra_params: Optional[Dict[str, Any]],
    ) -> str:
        if extra_params and extra_params.get("response_format") in {"url", "base64"}:
            return str(extra_params["response_format"])
        if response_format in {"url", "base64"}:
            return response_format
        return "url"

    def _prompt_for_minimax(
        self,
        prompt: str,
        extra_params: Optional[Dict[str, Any]],
    ) -> str:
        negative_prompt = (extra_params or {}).get("negative_prompt")
        if not negative_prompt:
            return prompt[:1500]

        suffix = f"\nAvoid: {negative_prompt}"
        max_prompt_length = 1500
        if len(prompt) + len(suffix) <= max_prompt_length:
            return f"{prompt}{suffix}"

        remaining = max_prompt_length - len(prompt) - len("\nAvoid: ")
        if remaining <= 0:
            return prompt[:max_prompt_length]
        return f"{prompt}\nAvoid: {str(negative_prompt)[:remaining]}"

    def _minimax_size_fields(self, size: str, model: str) -> Dict[str, Any]:
        parsed = _parse_size(size)
        if parsed is None:
            return {"aspect_ratio": "1:1"}

        width, height = parsed
        aspect_ratio = _closest_aspect_ratio(width, height)

        if model == "image-01-live":
            return {"aspect_ratio": aspect_ratio}

        exact_dimensions_supported = (
            512 <= width <= 2048
            and 512 <= height <= 2048
            and width % 8 == 0
            and height % 8 == 0
        )
        if exact_dimensions_supported and aspect_ratio == "1:1" and width != height:
            return {"width": width, "height": height}
        return {"aspect_ratio": aspect_ratio}

    def _build_minimax_payload(
        self,
        prompt: str,
        size: str,
        n: int,
        response_format: str,
        model: str,
        extra_params: Optional[Dict[str, Any]],
        subject_reference: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": self._prompt_for_minimax(prompt, extra_params),
            "response_format": self._response_format_for_minimax(response_format, extra_params),
            "n": min(max(1, n), 9),
            "prompt_optimizer": bool((extra_params or {}).get("prompt_optimizer", True)),
        }
        payload.update(self._minimax_size_fields(size, model))

        if subject_reference:
            payload["subject_reference"] = subject_reference

        if extra_params:
            for key in ("seed", "style"):
                if key in extra_params:
                    payload[key] = extra_params[key]
            for key in ("aspect_ratio", "width", "height"):
                if key in extra_params:
                    payload.pop("aspect_ratio", None)
                    payload[key] = extra_params[key]

        return payload

    def _raise_for_minimax_error(self, result: Dict[str, Any], prompt: str) -> None:
        base_resp = result.get("base_resp")
        if not isinstance(base_resp, dict):
            return

        raw_status = base_resp.get("status_code", 0)
        try:
            status_code = int(raw_status)
        except (TypeError, ValueError):
            status_code = -1
        if status_code == 0:
            return

        status_msg = str(base_resp.get("status_msg", ""))
        full_error = f"{status_code}: {status_msg}"
        if status_code == 1026:
            raise ContentInspectionError(
                "您的图片请求触发了内容安全审核，请尝试使用其他描述方式",
                original_prompt=prompt,
                api_error_message=full_error,
            )
        if status_code == 1027:
            raise ContentInspectionError(
                "图片生成结果触发了内容安全审核，请尝试使用其他描述方式",
                original_prompt=prompt,
                api_error_message=full_error,
            )

        category, retryable, public_message = _MINIMAX_ERROR_POLICIES.get(
            status_code,
            ("upstream", True, "图片生成服务暂时不可用，请稍后再试"),
        )
        trace_id = result.get("trace_id") or result.get("id")
        raise ImageProviderError(
            code=f"minimax_{status_code}",
            category=category,
            retryable=retryable,
            public_message=public_message,
            provider_trace_id=str(trace_id) if trace_id else None,
        )

    def _provider_error_for_http(
        self,
        status_code: int,
        *,
        operation: str,
    ) -> ImageProviderError:
        """Translate transport status codes into safe provider failures."""
        if status_code in {401, 403}:
            category: ImageProviderCategory = "authentication"
            retryable = False
            public_message = "图片生成服务暂时不可用，请联系管理员"
        elif status_code == 429:
            category = "rate_limit"
            retryable = True
            public_message = "图片生成请求较多，请稍后再试"
        elif status_code >= 500:
            category = "upstream"
            retryable = True
            public_message = "图片生成服务暂时不可用，请稍后再试"
        else:
            category = "invalid_request"
            retryable = False
            public_message = "图片生成参数无效，请调整后重试"

        return ImageProviderError(
            code=f"image_provider_http_{status_code}_{operation}",
            category=category,
            retryable=retryable,
            public_message=public_message,
        )

    def _provider_timeout_error(self) -> ImageProviderError:
        return ImageProviderError(
            code="image_provider_timeout",
            category="timeout",
            retryable=True,
            public_message="图片生成服务响应超时，请稍后再试",
        )

    def _provider_network_error(self) -> ImageProviderError:
        return ImageProviderError(
            code="image_provider_network_error",
            category="upstream",
            retryable=True,
            public_message="图片生成服务暂时不可用，请稍后再试",
        )

    def _provider_invalid_response_error(self) -> ImageProviderError:
        return ImageProviderError(
            code="image_provider_invalid_response",
            category="invalid_response",
            retryable=False,
            public_message="图片生成服务返回了无效结果，请稍后再试",
        )

    def _minimax_image_sources(self, result: Dict[str, Any]) -> Tuple[str, List[str]]:
        data = result.get("data")
        if not isinstance(data, dict):
            raise ImageProviderError(
                code="image_provider_invalid_response",
                category="invalid_response",
                retryable=False,
                public_message="图片生成服务返回了无效结果，请稍后再试",
            )

        image_urls = data.get("image_urls")
        if isinstance(image_urls, list) and image_urls:
            sources = [str(url) for url in image_urls if url]
            if sources:
                return "url", sources

        image_base64 = data.get("image_base64")
        if isinstance(image_base64, list) and image_base64:
            sources = [str(encoded) for encoded in image_base64 if encoded]
            if sources:
                return "base64", sources

        raise ImageProviderError(
            code="image_provider_invalid_response",
            category="invalid_response",
            retryable=False,
            public_message="图片生成服务返回了无效结果，请稍后再试",
        )

    def _decode_base64_image(self, encoded: str) -> bytes:
        payload = encoded.split(",", 1)[1] if encoded.startswith("data:") and "," in encoded else encoded
        try:
            return base64.b64decode(payload, validate=True)
        except binascii.Error as exc:
            raise ImageProviderError(
                code="image_provider_invalid_response",
                category="invalid_response",
                retryable=False,
                public_message="图片生成服务返回了无效结果，请稍后再试",
            ) from exc

    def _resolve_minimax_image_source(self, kind: str, source: str) -> bytes:
        if kind == "url":
            return self._download_image(source)
        if kind == "base64":
            return self._decode_base64_image(source)
        raise ImageProviderError(
            code="image_provider_invalid_response",
            category="invalid_response",
            retryable=False,
            public_message="图片生成服务返回了无效结果，请稍后再试",
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

        支持 MiniMax 图片生成 API，支持模型降级
        M-09: 支持基于 prompt 的缓存，避免重复调用 API

        Args:
            prompt: 图片描述prompt
            size: 图片尺寸，会映射为 MiniMax aspect_ratio 或 width/height
            style: 保留兼容参数
            quality: 保留兼容参数
            n: 生成数量
            response_format: 返回格式，MiniMax 支持 url/base64，默认保持 URL 下载链路
            extra_params: 额外参数（如 negative_prompt, seed）

        Returns:
            Tuple[bytes, str]: (图片二进制数据, 使用的prompt)

        Raises:
            ImageGenerationError: 生成失败
        """
        if self._e2e_local_image_enabled():
            logger.info("MINIMAX_E2E_LOCAL_IMAGE enabled; returning deterministic local image")
            return _LOCAL_E2E_IMAGE_BYTES, prompt

        # M-09: 检查缓存
        cache_key = _get_prompt_hash(prompt, size, extra_params)
        cached_result = _image_cache.get(cache_key)
        if cached_result is not None:
            logger.info(f"[ImageCache] Cache hit for prompt hash: {cache_key[:8]}...")
            return cached_result

        last_error: Optional[Exception] = None

        # 支持模型降级：尝试每个模型
        is_last_model = False
        for model_idx, fallback_model in enumerate(self.text_to_image_models):
            is_last_model = model_idx == len(self.text_to_image_models) - 1

            if model_idx > 0:
                logger.warning(f"[Model Fallback] Switching to fallback model: {fallback_model}")

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

                    kind, sources = self._minimax_image_sources(result)
                    image_bytes = self._resolve_minimax_image_source(kind, sources[0])
                    logger.info(f"Successfully downloaded image: {len(image_bytes)} bytes")

                    # M-09: 存入缓存
                    cached_result = (image_bytes, prompt)
                    _image_cache[cache_key] = cached_result
                    logger.debug(f"[ImageCache] Cached image with key: {cache_key[:8]}...")

                    return cached_result

                except ContentInspectionError:
                    raise
                except ImageProviderError as e:
                    last_error = e
                    logger.warning(
                        "Image provider failure: provider=minimax code=%s category=%s "
                        "retryable=%s trace_id=%s model=%s attempt=%s/%s",
                        e.code,
                        e.category,
                        e.retryable,
                        e.provider_trace_id,
                        fallback_model,
                        attempt + 1,
                        self.max_retries,
                    )
                    if not e.retryable:
                        raise
                    if attempt < self.max_retries - 1:
                        time.sleep(2**attempt)
                    else:
                        break
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

        if isinstance(last_error, ImageProviderError):
            raise last_error
        raise ImageGenerationError(f"Failed to generate image after trying all models: {last_error}")

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
        if self._e2e_local_image_enabled():
            logger.info("MINIMAX_E2E_LOCAL_IMAGE enabled; returning deterministic local image URL")
            return _LOCAL_E2E_IMAGE_BYTES, prompt, self._local_e2e_image_url()

        result = self._call_api(
            prompt=prompt,
            size=size,
            extra_params=extra_params,
            response_format="url",
        )

        kind, sources = self._minimax_image_sources(result)
        if kind != "url":
            raise ImageGenerationError("MiniMax response did not include an image URL")
        image_url = sources[0]

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
        self.require_generation_config()

        # 使用传入的模型或默认模型
        use_model = model or self.model

        provider_params = dict(extra_params or {})
        payload = self._build_minimax_payload(
            prompt=prompt,
            size=size,
            n=n,
            response_format=response_format,
            model=use_model,
            extra_params=provider_params,
        )

        # 构建请求头
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = self._image_generation_url()

        logger.debug(f"Calling MiniMax image API: {url}, model: {use_model}, size: {size}")

        try:
            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise self._provider_timeout_error() from exc
        except requests.exceptions.RequestException as exc:
            raise self._provider_network_error() from exc

        if response.status_code != 200:
            logger.error(
                "MiniMax image API HTTP failure: status=%s operation=generate",
                response.status_code,
            )
            raise self._provider_error_for_http(
                response.status_code,
                operation="generate",
            )

        try:
            result = response.json()
        except (TypeError, ValueError) as exc:
            raise self._provider_invalid_response_error() from exc
        if not isinstance(result, dict):
            raise self._provider_invalid_response_error()
        self._raise_for_minimax_error(result, str(payload["prompt"]))
        return result

    def _download_image(self, url: str) -> bytes:
        """下载图片"""
        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise self._provider_timeout_error() from exc
        except requests.exceptions.RequestException as exc:
            raise self._provider_network_error() from exc
        if response.status_code != 200:
            raise self._provider_error_for_http(
                response.status_code,
                operation="download",
            )
        return response.content  # type: ignore[no-any-return]

    def edit_image(
        self,
        reference_image: str,
        prompt: str,
        size: str = "928*1664",
        num_images: int = 1,
        extra_params: Optional[Dict[str, Any]] = None,
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
        if self._e2e_local_image_enabled():
            logger.info("MINIMAX_E2E_LOCAL_IMAGE enabled; returning deterministic local edit image")
            return [(_LOCAL_E2E_IMAGE_BYTES, prompt) for _ in range(max(1, num_images))]

        logger.debug(f"Editing image with prompt: {prompt}")

        last_error: Optional[Exception] = None

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
                        extra_params=extra_params,
                    )

                    kind, sources = self._minimax_image_sources(result)
                    results = []
                    for i, source in enumerate(sources):
                        image_bytes = self._resolve_minimax_image_source(kind, source)
                        results.append((image_bytes, f"{prompt} (variant {i+1})"))
                        logger.info(f"Downloaded edited image {i+1}/{len(sources)}")

                    return results

                except ContentInspectionError:
                    # 内容审核错误不重试，直接抛出
                    raise
                except ImageProviderError as e:
                    last_error = e
                    logger.warning(
                        "Image edit provider failure: provider=minimax code=%s category=%s "
                        "retryable=%s trace_id=%s model=%s attempt=%s/%s",
                        e.code,
                        e.category,
                        e.retryable,
                        e.provider_trace_id,
                        fallback_model,
                        attempt + 1,
                        self.max_retries,
                    )
                    if not e.retryable:
                        raise
                    if attempt < self.max_retries - 1:
                        time.sleep(2**attempt)
                    else:
                        break
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

        if isinstance(last_error, ImageProviderError):
            raise last_error
        raise ImageGenerationError(f"Failed to edit image after trying all models: {last_error}")

    def _call_edit_api(
        self,
        reference_image: str,
        prompt: str,
        size: str = "928*1664",
        num_images: int = 1,
        model: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        调用图生图API

        Args:
            reference_image: 参考图片URL
            prompt: 编辑指令
            size: 图片尺寸
            num_images: 生成数量
            model: 可选模型名称
            extra_params: 额外参数（如 negative_prompt）

        Returns:
            API响应
        """
        self.require_generation_config()

        # 使用传入的模型或默认模型
        use_model = model or self.image_edit_models[0]

        provider_params = dict(extra_params or {})
        payload = self._build_minimax_payload(
            prompt=prompt,
            size=size,
            n=num_images,
            response_format="url",
            model=use_model,
            extra_params=provider_params,
            subject_reference=[{"type": "character", "image_file": reference_image}],
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = self._image_generation_url()

        logger.debug(f"Calling MiniMax image edit API: model={use_model}, size={size}")

        try:
            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise self._provider_timeout_error() from exc
        except requests.exceptions.RequestException as exc:
            raise self._provider_network_error() from exc

        if response.status_code != 200:
            logger.error(
                "MiniMax image API HTTP failure: status=%s operation=edit",
                response.status_code,
            )

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
                    logger.warning(f"Failed to parse content inspection error response: {e}")
                except Exception as e:
                    logger.exception(f"Unexpected error parsing API error response: {e}")

            raise self._provider_error_for_http(
                response.status_code,
                operation="edit",
            )

        try:
            result = response.json()
        except (TypeError, ValueError) as exc:
            raise self._provider_invalid_response_error() from exc
        if not isinstance(result, dict):
            raise self._provider_invalid_response_error()
        self._raise_for_minimax_error(result, str(payload["prompt"]))
        return result

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
        prompt_builder: Any = None,  # 注入 prompt builder
        extra_params: Optional[Dict[str, Any]] = None,
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
            extra_params: 额外参数（如 negative_prompt, seed）

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
                except ImageProviderError:
                    raise
                except (
                    requests.exceptions.RequestException,
                    ImageGenerationError,
                ) as e:
                    logger.warning(f"Failed to generate variant {i + 1}: {e}")
                except Exception as e:
                    logger.exception(f"Unexpected error generating variant {i + 1}: {e}")
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
                        extra_params=extra_params,
                    )
                )
                results.append((main_image_bytes, main_prompt_used))
                logger.info(f"Generated primary image, URL: {primary_image_url}")

                # 基于主图生成变体
                num_variants = num_images - 1
                if num_variants > 0:
                    logger.info(f"Generating {num_variants} variants from primary image")

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
                        except ImageProviderError:
                            raise
                        except (
                            requests.exceptions.RequestException,
                            ImageGenerationError,
                        ) as e:
                            logger.warning(f"Failed to generate variant {i + 1}: {e}")
                        except Exception as e:
                            logger.exception(f"Unexpected error generating variant {i + 1}: {e}")

            except ImageProviderError:
                raise
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
            except ImageProviderError:
                raise
            except (requests.exceptions.RequestException, ImageGenerationError) as e:
                logger.warning(f"Failed to generate variant {i + 1}: {e}")
            except Exception as e:
                logger.exception(f"Unexpected error generating variant {i + 1}: {e}")

        return results
