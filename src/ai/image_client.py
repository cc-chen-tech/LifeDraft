"""Image generation client - OpenAI compatible interface.

Supports various image generation APIs that follow OpenAI-compatible interface:
- DashScope (阿里云通义万象)
- Other OpenAI-compatible image services
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import settings

logger = logging.getLogger(__name__)


def create_retry_session(
    retries=3,
    backoff_factor=1,
    status_forcelist=(500, 502, 503, 504),
):
    """Create a requests session with retry strategy."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class ImageGenerationError(Exception):
    """图像生成错误"""

    pass


class ContentInspectionError(ImageGenerationError):
    """内容审核错误 - 触发了平台的内容安全检测"""

    def __init__(
        self, message: str, original_prompt: str = None, api_error_message: str = None
    ):
        super().__init__(message)
        self.original_prompt = original_prompt
        self.api_error_message = api_error_message  # ★ 阿里云返回的原始错误信息


class ImageClient:
    """图像生成客户端 - 支持文生图和图生图，支持模型降级"""

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
        self.api_key = api_key or settings.get_image_api_key()
        self.base_url = base_url or settings.get_image_api_base_url()
        self.model = model or settings.IMAGE_MODEL
        self.timeout = settings.IMAGE_GENERATION_TIMEOUT
        self.max_retries = settings.IMAGE_MAX_RETRIES

        # ★ 使用带重试策略的 session 来改善 SSL 连接稳定性
        self.session = create_retry_session(retries=self.max_retries)

        # ★ 从配置解析模型降级列表
        self.text_to_image_models = [
            m.strip() for m in settings.TEXT_TO_IMAGE_MODELS.split(",") if m.strip()
        ]
        self.image_edit_models = [
            m.strip() for m in settings.IMAGE_EDIT_MODELS.split(",") if m.strip()
        ]

        if not self.api_key:
            raise ValueError(
                "Image API key is required. Set IMAGE_API_KEY or OPENAI_API_KEY in environment."
            )

        if not self.base_url:
            raise ValueError(
                "Image API base URL is required. Set IMAGE_API_BASE_URL or OPENAI_BASE_URL in environment."
            )

    def generate_image_prompt_with_deepseek(
        self,
        character_info: Dict[str, Any],
    ) -> str:
        """
        使用 DeepSeek 生成图片描述 prompt

        将人物信息喂给 deepseek，生成一个优化的图片生成 prompt

        Args:
            character_info: 人物信息字典，包含：
                - name: 姓名
                - age: 年龄
                - gender: 性别
                - era: 时代背景
                - appearance: 外貌描述
                - personality: 性格特点
                - occupation: 职业
                - background: 背景故事
                等

        Returns:
            优化后的图片生成 prompt
        """
        import openai

        # 使用 deepseek 配置
        api_key = settings.SCENE_ANALYZER_API_KEY or settings.OPENAI_API_KEY
        base_url = settings.SCENE_ANALYZER_BASE_URL or settings.OPENAI_BASE_URL
        model = settings.SCENE_ANALYZER_MODEL  # deepseek-chat

        if not api_key:
            logger.warning("No DeepSeek API key, using fallback prompt")
            return self._build_fallback_prompt(character_info)

        # 构建 system prompt
        system_prompt = """你是一个专业的图片描述生成专家。你的任务是将人物信息转换为一个详细、生动的图片生成提示词。

要求：
1. 描述人物的外貌特征（面部、发型、体型、肤色等）
2. 描述人物的服装和穿着风格
3. 描述人物的气质和神态
4. 确保描述适合 AI 绘画模型理解
5. 输出格式为纯文本描述，不要包含任何 JSON 或其他格式
6. 描述应该足够详细，让 AI 能够生成高质量的图片
7. 强调全身像、脚部可见

输出应该是一段连贯的中文描述，约100-200字。"""

        # 构建 user prompt
        user_prompt = f"""请为以下人物生成一个详细的图片描述：

姓名：{character_info.get('name', '未知')}
年龄：{character_info.get('age', '25')}岁
性别：{character_info.get('gender', '女')}
时代背景：{character_info.get('era', '现代')}
外貌描述：{character_info.get('appearance', '')}
性格特点：{character_info.get('personality', '')}
职业：{character_info.get('occupation', '')}
背景故事：{character_info.get('background', '')}

请生成一段适合 AI 绘画的详细人物描述。"""

        try:
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
                max_tokens=500,
            )

            prompt = response.choices[0].message.content.strip()
            logger.debug(f"DeepSeek generated prompt: {prompt[:100]}...")
            return prompt

        except Exception as e:
            logger.error(f"DeepSeek prompt generation failed: {e}")
            return self._build_fallback_prompt(character_info)

    def _build_fallback_prompt(self, character_info: Dict[str, Any]) -> str:
        """DeepSeek 不可用时的备选 prompt 生成"""
        name = character_info.get("name", "人物")
        age = character_info.get("age", "25")
        gender = character_info.get("gender", "女")
        era = character_info.get("era", "现代")
        appearance = character_info.get("appearance", "")

        return f"{era}，{age}岁{gender}性，{name}。{appearance}。人物全身像，脚部可见，写实风格。"

    def generate_image(
        self,
        prompt: str,
        size: str = "1328*1328",  # DashScope 1:1 正方形
        style: Optional[str] = None,
        quality: str = "standard",
        n: int = 1,
        response_format: str = "b64_json",
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bytes, str]:
        """
        生成图片

        支持 DashScope API（阿里云千问图像模型），支持模型降级

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
        last_error = None

        # ★ 支持模型降级：尝试每个模型
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
                        model=fallback_model,  # ★ 使用降级模型
                    )

                    # ★ 解析 DashScope API 响应
                    # 响应格式: {"output": {"choices": [{"message": {"content": [{"image": "url"}]}]}}, "usage": {...}}
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
                    return image_bytes, prompt

                except Exception as e:
                    last_error = e
                    error_str = str(e)
                    logger.warning(
                        f"Image generation attempt {attempt + 1}/{self.max_retries} with model {fallback_model} failed: {e}"
                    )

                    # ★ 检测 429 速率限制错误
                    is_rate_limit = (
                        "429" in error_str
                        or "RateQuota" in error_str
                        or "rate limit" in error_str.lower()
                    )

                    if is_rate_limit:
                        if not is_last_model:
                            # ★ 不是最后一个模型：直接换模型，不等待
                            logger.warning(
                                "[Model Fallback] Rate limit detected, switching to next model immediately..."
                            )
                            break  # 跳出重试循环，进入下一个模型
                        else:
                            # ★ 是最后一个模型：只能等待重试
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
        model: Optional[str] = None,  # ★ 可选：指定模型（支持降级）
    ) -> Dict[str, Any]:
        """
        调用图像生成API

        支持 DashScope API 格式（阿里云千问图像模型）

        Args:
            prompt: 图片描述
            size: 图片尺寸 (DashScope支持: 1664*928, 1472*1104, 1328*1328, 1104*1472, 928*1664)
            style: 风格（DashScope不支持）
            quality: 质量（DashScope不支持）
            n: 生成数量
            response_format: 返回格式
            extra_params: 额外参数
            model: 可选模型名称（不指定则使用默认模型）

        Returns:
            API响应字典
        """
        # 构建请求URL
        url = f"{self.base_url.rstrip('/')}/generation"

        # ★ DashScope API 格式
        # 尺寸格式确保是 "W*H"
        dashscope_size = size if "*" in size else size.replace("x", "*")

        # ★ 使用传入的模型或默认模型
        use_model = model or self.model

        # 构建请求体 (DashScope 格式)
        payload = {
            "model": use_model,  # ★ 使用指定的模型
            "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
            "parameters": {
                "size": dashscope_size,
                "n": n,
                "prompt_extend": True,  # 开启智能改写
                "watermark": False,
            },
        }

        # 添加反向提示词
        if extra_params and extra_params.get("negative_prompt"):
            payload["parameters"]["negative_prompt"] = extra_params["negative_prompt"]
        else:
            # ★ 默认反向提示词 - 强调全身像
            payload["parameters"]["negative_prompt"] = (
                "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，"
                "蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲。"
                "半身像，裁剪，截断，无脚，没有脚，脚被裁剪，只显示上半身，"
                "膝盖以下被裁剪，腰部以上，胸部以上，头部特写，"
                "肖像画，大头照，证件照。"
            )

        # 合并额外参数
        if extra_params:
            for key in ["seed", "prompt_extend"]:
                if key in extra_params:
                    payload["parameters"][key] = extra_params[key]

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

    def generate_character_image(
        self,
        name: str,
        description: str,
        era: str = "现代",
        style_hint: Optional[str] = None,
        size: str = "1328*1328",  # DashScope 1:1 正方形
    ) -> Tuple[bytes, str]:
        """
        生成人物形象图片

        Args:
            name: 人物名称
            description: 人物描述（年龄、性别、外貌特征等）
            era: 时代背景
            style_hint: 风格提示
            size: 图片尺寸 (DashScope支持: 1664*928, 1472*1104, 1328*1328, 1104*1472, 928*1664)

        Returns:
            Tuple[bytes, str]: (图片二进制数据, 使用的prompt)
        """
        # 构建人物形象prompt
        prompt = self._build_character_prompt(name, description, era, style_hint)

        return self.generate_image(
            prompt=prompt,
            size=size,
            extra_params={"prompt_extend": True},
        )

    def _build_character_prompt(
        self,
        name: str,
        description: str,
        era: str,
        style_hint: Optional[str] = None,
        pose_hint: Optional[str] = None,
        feedback: Optional[str] = None,  # ★ 用户修改意见
    ) -> str:
        """
        构建人物形象prompt（优化版本 - 更细致的描述）

        Args:
            name: 人物名称
            description: 人物描述
            era: 时代背景
            style_hint: 风格提示
            pose_hint: 姿势提示（如：站立、行走、坐姿等）
            feedback: 用户修改意见（会被特别强调）

        Returns:
            构建好的prompt
        """
        parts = []

        # ★★★ 最重要：用户的修改意见放在最前面
        if feedback:
            parts.append(
                f"【必须执行的修改】{feedback}。这是最重要的要求，必须严格体现在图片中。"
            )

        # 基础信息
        parts.extend(
            [
                f"【人物】{name}",
                f"【时代背景】{era}",
            ]
        )

        # 外貌描述（更细致）
        parts.extend(
            [
                f"【外貌特征】{description}",
                "【服装】根据时代背景设计的典型服饰，款式细节丰富，材质纹理清晰可见",
                "【表情】自然平和，眼神有故事感，符合人物性格特征",
                "【光线】柔和的自然光，从左侧45度角打光，突出面部立体感和轮廓",
            ]
        )

        # 构图要求（更精确）
        parts.extend(
            [
                "【构图要求】",
                "- 全身像，人物占画面75%-85%",
                "- 头顶留白约8%-12%，脚底留白约5%-8%",
                "- 人物纵向居中，左右适当留白",
                "- 纵向构图（竖版），突出人物全身",
                "- 背景简洁虚化，突出人物主体",
            ]
        )

        # 姿势
        if pose_hint:
            parts.append(f"【姿势】{pose_hint}")
        else:
            parts.append(
                "【姿势】自然站立姿态，双脚与肩同宽，身体略微侧向15-30度，避免完全正面呆板"
            )

        # 风格提示（更详细）
        if style_hint:
            parts.append(f"【风格】{style_hint}")
        else:
            parts.extend(
                [
                    "【风格】写实风格，电影质感",
                    "- 细节丰富：面部特征、服装纹理、头发丝都清晰可见",
                    "- 光影自然：柔和过渡，避免过度平滑的AI感",
                    "- 色彩适中：饱和度适中，肤色自然真实",
                    "- 画面质感：有真实照片感，避免蜡像或塑料质感",
                ]
            )

        # 质量要求（强化）
        parts.extend(
            [
                "【质量要求】",
                "- 全身完整展示：头部、躯干、四肢、脚部全部可见",
                "- 面部清晰：五官比例协调，特征鲜明可辨",
                "- 服装细节：款式、颜色、褶皱、材质都清晰呈现",
                "- 光影立体：有明显的主光源方向，阴影柔和有层次",
                "- 避免畸形：手指、五官比例正确，没有明显的AI畸变",
            ]
        )

        return "。".join(parts)

    # 预设的姿势和场景（确保是同一个人的不同场景）
    CHARACTER_POSES = [
        "站立姿态，正面朝向，日常便装，背景是日常生活场景，自然光线",
        "行走姿态，侧面视角，外出服装，背景是街道或户外场景，动态感",
    ]

    def generate_character_images(
        self,
        name: str,
        description: str,
        era: str = "现代",
        style_hint: Optional[str] = None,
        num_images: int = 2,  # ★ 默认生成2张（1张主图 + 1张变体）
        size: str = "928*1664",  # 9:16 竖版适合全身像
        reference_image_url: Optional[str] = None,  # ★ 可选：已有的参考图片URL
        feedback: Optional[str] = None,  # ★ 用户修改意见（单独传入以强调）
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

        Returns:
            Tuple[List of (图片数据, prompt), 主图URL]
            主图URL用于后续重新生成
        """
        results = []
        primary_image_url = reference_image_url

        # ★ 变体场景 - 全部强调全身像
        VARIANTS = [
            "这个人的全身像，站立姿态，正面朝向，自然光线，脚部可见",
            "这个人正在行走，侧面视角，全身展示，动态感",
            "这个人站在室内，休闲姿态，全身构图，温馨氛围",
            "这个人在户外场景，全身远景构图，环境清晰",
            "这个人的全身像，突出气质和姿态，双脚可见",
        ]

        if reference_image_url:
            # ★ 有参考图片，prompt应该简洁，重点是用户的修改要求
            # 参考图片已包含：时代背景、构图等，不需要重复
            logger.info(
                f"Generating {num_images} image(s) from reference image, feedback: {feedback}"
            )

            for i in range(num_images):
                # ★ 图生图prompt：简洁，只关注修改要求
                prompt_parts = []

                # ★★★ 用户修改要求 - 这是最重要的
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
                except Exception as e:
                    logger.error(f"Failed to generate variant {i + 1}: {e}")
        else:
            # ★ 没有参考图片，先生成主图
            logger.info(f"Generating primary image for {name}, feedback: {feedback}")

            # 生成主图
            main_prompt = self._build_character_prompt(
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
                        variant = VARIANTS[i % len(VARIANTS)]
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
                        except Exception as e:
                            logger.error(f"Failed to generate variant {i + 1}: {e}")

            except Exception as e:
                logger.error(f"Failed to generate primary image: {e}")
                raise

        logger.info(f"Total images generated: {len(results)}")
        return results, primary_image_url

    def generate_location_image(
        self,
        name: str,
        description: str,
        era: str = "现代",
        style_hint: Optional[str] = None,
        size: str = "1664*928",  # DashScope 16:9 宽屏
    ) -> Tuple[bytes, str]:
        """
        生成地点/地标图片

        Args:
            name: 地点名称
            description: 地点描述
            era: 时代背景
            style_hint: 风格提示
            size: 图片尺寸 (DashScope支持: 1664*928, 1472*1104, 1328*1328, 1104*1472, 928*1664)

        Returns:
            Tuple[bytes, str]: (图片二进制数据, 使用的prompt)
        """
        prompt = self._build_location_prompt(name, description, era, style_hint)

        return self.generate_image(
            prompt=prompt,
            size=size,
            extra_params={"prompt_extend": True},
        )

    def _build_location_prompt(
        self,
        name: str,
        description: str,
        era: str,
        style_hint: Optional[str] = None,
    ) -> str:
        """构建地点prompt"""
        parts = [
            f"一张高质量的场景插画，地点：{name}。",
            f"时代背景：{era}。",
            f"场景描述：{description}。",
        ]

        if style_hint:
            parts.append(f"风格：{style_hint}。")
        else:
            parts.append("风格：写实风格，细节丰富，氛围感强。")

        parts.append(
            "要求：场景清晰、构图美观、有代入感。画面中不要出现任何人物，仅展示场景本身。"
        )

        return "".join(parts)

    def generate_item_image(
        self,
        name: str,
        description: str,
        era: str = "现代",
        style_hint: Optional[str] = None,
        size: str = "1328*1328",  # DashScope 1:1 正方形
    ) -> Tuple[bytes, str]:
        """
        生成物品图片

        Args:
            name: 物品名称
            description: 物品描述
            era: 时代背景
            style_hint: 风格提示
            size: 图片尺寸 (DashScope支持: 1664*928, 1472*1104, 1328*1328, 1104*1472, 928*1664)

        Returns:
            Tuple[bytes, str]: (图片二进制数据, 使用的prompt)
        """
        prompt = self._build_item_prompt(name, description, era, style_hint)

        return self.generate_image(
            prompt=prompt,
            size=size,
            extra_params={"prompt_extend": True},
        )

    def _build_item_prompt(
        self,
        name: str,
        description: str,
        era: str,
        style_hint: Optional[str] = None,
    ) -> str:
        """构建物品prompt"""
        parts = [
            f"一张高质量的物品图片，物品：{name}。",
            f"时代背景：{era}。",
            f"物品描述：{description}。",
        ]

        if style_hint:
            parts.append(f"风格：{style_hint}。")
        else:
            parts.append("风格：写实风格，细节清晰。")

        parts.append("要求：物品居中、背景简洁、光影自然。")

        return "".join(parts)

    def generate_scene_image(
        self,
        scene_description: str,
        characters: Optional[list] = None,
        era: str = "现代",
        style_hint: Optional[str] = None,
        size: str = "1664*928",  # DashScope 16:9 宽屏，适合场景
    ) -> Tuple[bytes, str]:
        """
        生成场景插图

        Args:
            scene_description: 场景描述
            characters: 场景中的人物列表 [{"name": "...", "description": "..."}, ...]
            era: 时代背景
            style_hint: 风格提示
            size: 图片尺寸 (DashScope支持: 1664*928, 1472*1104, 1328*1328, 1104*1472, 928*1664)

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

    def _build_scene_prompt(
        self,
        scene_description: str,
        characters: Optional[list],
        era: str,
        style_hint: Optional[str] = None,
    ) -> str:
        """构建场景prompt"""
        parts = [
            "一张高质量的故事场景插画。",
            f"时代背景：{era}。",
            f"场景描述：{scene_description}",
        ]

        if characters:
            char_desc = "、".join(
                [f"{c.get('name', '')}({c.get('description', '')})" for c in characters]
            )
            parts.append(f"场景中的人物：{char_desc}。")

        if style_hint:
            parts.append(f"风格：{style_hint}。")
        else:
            parts.append("风格：电影感，写实风格，氛围感强。")

        parts.append("要求：画面有故事感、人物表情生动、场景细节丰富。")

        return "".join(parts)

    # ==================== 图生图功能 ====================

    def edit_image(
        self,
        reference_image: str,  # 图片URL或本地路径
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

        # ★ 支持模型降级：尝试每个图生图模型
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
                        model=fallback_model,  # ★ 使用降级模型
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
                    # ★ 内容审核错误不重试，直接抛出
                    raise
                except Exception as e:
                    last_error = e
                    error_str = str(e)
                    logger.warning(
                        f"Image edit attempt {attempt + 1}/{self.max_retries} with model {fallback_model} failed: {e}"
                    )

                    # ★ 检测 429 速率限制错误
                    is_rate_limit = (
                        "429" in error_str
                        or "RateQuota" in error_str
                        or "rate limit" in error_str.lower()
                    )

                    if is_rate_limit:
                        if not is_last_model:
                            # ★ 不是最后一个模型：直接换模型，不等待
                            logger.warning(
                                "[Model Fallback] Rate limit detected, switching to next model immediately..."
                            )
                            break  # 跳出重试循环，进入下一个模型
                        else:
                            # ★ 是最后一个模型：只能等待重试
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

        raise ImageGenerationError(
            f"Failed to edit image after trying all models: {last_error}"
        )

    def _call_edit_api(
        self,
        reference_image: str,
        prompt: str,
        size: str = "928*1664",
        num_images: int = 1,
        model: Optional[str] = None,  # ★ 可选：指定模型（支持降级）
    ) -> Dict[str, Any]:
        """
        调用图生图API

        Args:
            reference_image: 参考图片URL
            prompt: 编辑指令
            size: 图片尺寸
            num_images: 生成数量
            model: 可选模型名称（不指定则使用第一个降级模型）

        Returns:
            API响应
        """
        url = f"{self.base_url.rstrip('/')}/generation"

        # 尺寸格式
        dashscope_size = size if "*" in size else size.replace("x", "*")

        # ★ 使用传入的模型或默认模型
        use_model = model or self.image_edit_models[0]

        # 构建请求体 - 图生图格式
        payload = {
            "model": use_model,  # ★ 使用指定的模型
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
                "negative_prompt": (
                    "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲。"
                    "半身像，裁剪，截断，无脚，没有脚，脚被裁剪，只显示上半身，"
                    "膝盖以下被裁剪，腰部以上，胸部以上，头部特写，肖像画，大头照。"
                ),
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

            # ★ 检测内容审核错误
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    error_code = error_data.get("code", "")
                    if error_code == "DataInspectionFailed":
                        # ★ 提取阿里云返回的完整错误信息
                        api_message = error_data.get("message", "")
                        full_error = f"{error_code}: {api_message}"
                        logger.warning(f"Content inspection failed: {full_error}")
                        raise ContentInspectionError(
                            "您的修改请求触发了内容安全审核，请尝试使用其他描述方式",
                            original_prompt=prompt,
                            api_error_message=full_error,  # ★ 传递阿里云的错误信息
                        )
                except ContentInspectionError:
                    raise
                except (KeyError, TypeError) as e:
                    logger.warning(
                        f"Failed to parse content inspection error response: {e}"
                    )
                except Exception as e:
                    logger.warning(f"Unexpected error parsing API error response: {e}")

            raise ImageGenerationError(error_msg)

        return response.json()

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
            except Exception as e:
                logger.error(f"Failed to generate variant {i + 1}: {e}")

        return results

    # ==================== 开场插画生成 ====================

    def analyze_story_for_illustration(
        self,
        story_text: str,
        character_info: Dict[str, Any],
    ) -> Tuple[str, str]:
        """
        使用 DeepSeek 分析故事，选择最重要/最视觉化的场景

        Args:
            story_text: 开场故事文本
            character_info: 角色信息（姓名、外貌、时代等）

        Returns:
            Tuple[str, str]: (场景描述, 插画生成提示词)
        """
        import openai

        # 使用 deepseek 配置
        api_key = settings.SCENE_ANALYZER_API_KEY or settings.OPENAI_API_KEY
        base_url = settings.SCENE_ANALYZER_BASE_URL or settings.OPENAI_BASE_URL
        model = settings.SCENE_ANALYZER_MODEL  # deepseek-chat

        if not api_key:
            logger.warning("No DeepSeek API key, using fallback")
            return self._fallback_scene_selection(story_text, character_info)

        player_name = character_info.get("name", "主角")
        era = character_info.get("era", "现代")
        gender = character_info.get("gender", "")
        age = character_info.get("age", "")

        system_prompt = """你是一个专业的电影场景设计师和插画指导。你的任务是分析故事文本，选择最适合绘制的视觉场景。

选择标准：
1. 场景应该有强烈的视觉感（环境、光影、动作）
2. 场景应该能够展现主角的性格或处境
3. 避免选择过于抽象或内心独白的片段
4. 优先选择有明确动作和环境描述的场景

输出格式（严格遵守）：
【场景描述】简短描述你选择的场景（50字以内）
【画面构图】详细描述画面构图、人物姿态、环境细节、光影效果（100-200字）
【氛围】描述画面应传达的情感氛围

请只输出上述格式内容，不要添加其他解释。"""

        user_prompt = f"""请分析以下开场故事，选择最适合绘制插画的场景：

故事文本：
{story_text}

主角信息：
- 姓名：{player_name}
- 性别：{gender}
- 年龄：{age}
- 时代：{era}

请选择一个最能展现故事氛围和主角特点的场景，并生成插画指导。"""

        try:
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=800,
            )

            result = response.choices[0].message.content.strip()
            logger.info(f"DeepSeek scene analysis: {result[:200]}...")

            # 解析结果
            scene_desc = ""
            composition = ""
            atmosphere = ""

            for line in result.split("\n"):
                line = line.strip()
                if line.startswith("【场景描述】"):
                    scene_desc = line.replace("【场景描述】", "").strip()
                elif line.startswith("【画面构图】"):
                    composition = line.replace("【画面构图】", "").strip()
                elif line.startswith("【氛围】"):
                    atmosphere = line.replace("【氛围】", "").strip()

            # 构建插画提示词
            prompt_parts = []
            if era:
                prompt_parts.append(f"时代背景：{era}。")
            if scene_desc:
                prompt_parts.append(f"场景：{scene_desc}。")
            if composition:
                prompt_parts.append(f"画面描述：{composition}。")
            if atmosphere:
                prompt_parts.append(f"氛围：{atmosphere}。")

            # 添加风格指导
            prompt_parts.append("风格：电影感，写实风格，光影自然，故事感强。")

            illustration_prompt = "".join(prompt_parts)

            if not scene_desc:
                scene_desc = story_text[:100] + "..."

            return scene_desc, illustration_prompt

        except Exception as e:
            logger.error(f"DeepSeek scene analysis failed: {e}")
            return self._fallback_scene_selection(story_text, character_info)

    def _fallback_scene_selection(
        self,
        story_text: str,
        character_info: Dict[str, Any],
    ) -> Tuple[str, str]:
        """备选：基于规则选择场景"""
        player_name = character_info.get("name", "主角")
        era = character_info.get("era", "现代")

        # 简单截取故事开头作为场景
        scene_desc = story_text[:150] if len(story_text) > 150 else story_text

        illustration_prompt = f"""{era}场景插画。
场景描述：{scene_desc}
画面中展现{player_name}在故事中的关键时刻。
风格：电影感，写实风格，光影自然，故事感强。"""

        return scene_desc, illustration_prompt

    def rewrite_prompt_for_content_safety(
        self,
        original_prompt: str,
        scene_desc: str,
        character_info: Dict[str, Any],
        api_error_message: str = None,  # ★ 阿里云返回的审核错误信息
    ) -> Tuple[str, str]:
        """
        使用 DeepSeek 改写 prompt 以规避内容审核

        当图片生成触发内容审核时，调用此方法改写 prompt。
        会将阿里云返回的具体审核失败原因传递给 DeepSeek，让它针对性地改写。

        Args:
            original_prompt: 原始 prompt
            scene_desc: 场景描述
            character_info: 角色信息
            api_error_message: 阿里云返回的审核错误信息（如 "DataInspectionFailed: Input data may contain inappropriate content"）

        Returns:
            Tuple[str, str]: (改写后的场景描述, 改写后的完整 prompt)
        """
        import openai

        # 使用 deepseek 配置
        api_key = settings.SCENE_ANALYZER_API_KEY or settings.OPENAI_API_KEY
        base_url = settings.SCENE_ANALYZER_BASE_URL or settings.OPENAI_BASE_URL
        model = settings.SCENE_ANALYZER_MODEL

        if not api_key:
            logger.warning(
                "No DeepSeek API key for prompt rewrite, using simplified prompt"
            )
            return self._simplify_prompt(original_prompt, scene_desc)

        player_name = character_info.get("name", "主角")
        era = character_info.get("era", "现代")

        # ★ 根据是否有具体错误信息，构建不同的 system prompt
        if api_error_message:
            system_prompt = """你是一个专业的内容安全审核专家和图片提示词优化师。你的任务是分析图片生成API返回的内容审核失败原因，然后改写提示词使其能够通过审核。

重要：图片生成API已经明确拒绝了原始提示词，你需要根据具体的错误信息来判断问题所在并修复。

改写原则：
1. 仔细分析API返回的错误信息，理解被拒绝的具体原因
2. 移除或替换可能触发审核的内容（如敏感场所、敏感行为、敏感词汇等）
3. 保持场景的核心视觉元素和故事感
4. 使用更中性、安全的描述方式
5. 常见的敏感内容包括：网吧、酒吧、深夜场景、赌博相关、暴力血腥、性暗示等

输出格式（严格遵守）：
【场景描述】改写后的简短场景描述（50字以内）
【提示词】改写后的完整图片生成提示词

请只输出上述格式内容，不要添加其他解释。"""

            user_prompt = f"""图片生成API拒绝了以下提示词，请根据错误信息改写：

【API返回的错误信息】
{api_error_message}

【原始场景描述】
{scene_desc}

【原始提示词】
{original_prompt}

【主角信息】
- 姓名：{player_name}
- 时代：{era}

请根据API的错误信息，改写提示词使其能够通过内容审核。"""
        else:
            # 没有具体错误信息时，使用通用策略
            system_prompt = """你是一个专业的内容安全审核专家和图片提示词优化师。你的任务是改写图片生成提示词，使其能够通过内容安全审核，同时保持原有的视觉表达效果。

改写原则：
1. 移除可能触发审核的敏感词汇（如：网吧、深夜、酒吧、赌博、暴力、血腥、性暗示等）
2. 将敏感场景替换为安全的替代场景（如：网吧→图书馆/书房，深夜→傍晚，酒吧→咖啡厅）
3. 保持场景的核心视觉元素（人物动作、环境氛围、光影效果）
4. 使用更中性、描述性的语言
5. 保持画面的艺术感和故事感

输出格式（严格遵守）：
【场景描述】改写后的简短场景描述（50字以内）
【提示词】改写后的完整图片生成提示词

请只输出上述格式内容，不要添加其他解释。"""

            user_prompt = f"""请改写以下图片生成提示词，使其能够通过内容安全审核：

原始场景描述：
{scene_desc}

原始提示词：
{original_prompt}

主角信息：
- 姓名：{player_name}
- 时代：{era}

请改写提示词，移除敏感内容，保持视觉表达效果。"""

        try:
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=800,
            )

            result = response.choices[0].message.content.strip()
            logger.debug(
                f"DeepSeek prompt rewrite (api_error={bool(api_error_message)}): {result[:200]}..."
            )

            # 解析结果
            new_scene_desc = scene_desc  # 默认保持原场景
            new_prompt = original_prompt  # 默认保持原 prompt

            for line in result.split("\n"):
                line = line.strip()
                if line.startswith("【场景描述】"):
                    new_scene_desc = line.replace("【场景描述】", "").strip()
                elif line.startswith("【提示词】"):
                    new_prompt = line.replace("【提示词】", "").strip()

            logger.info(f"Rewritten scene: {new_scene_desc}")
            logger.debug(f"Rewritten prompt: {new_prompt[:100]}...")

            return new_scene_desc, new_prompt

        except Exception as e:
            logger.error(f"DeepSeek prompt rewrite failed: {e}")
            return self._simplify_prompt(original_prompt, scene_desc)

    def _simplify_prompt(
        self, original_prompt: str, scene_desc: str
    ) -> Tuple[str, str]:
        """简化 prompt 作为备选方案"""
        # 移除一些常见的敏感词
        sensitive_words = [
            "网吧",
            "酒吧",
            "深夜",
            "赌博",
            "暴力",
            "血腥",
            "性感",
            "诱惑",
        ]

        simplified_prompt = original_prompt
        simplified_scene = scene_desc

        for word in sensitive_words:
            if word in simplified_prompt:
                simplified_prompt = simplified_prompt.replace(word, "室内")
            if word in simplified_scene:
                simplified_scene = simplified_scene.replace(word, "室内")

        logger.debug(f"Simplified prompt: {simplified_prompt[:100]}...")
        return simplified_scene, simplified_prompt

    def generate_opening_illustration(
        self,
        story_text: str,
        character_info: Dict[str, Any],
        reference_image_url: Optional[str] = None,
        size: str = "1664*928",  # 16:9 宽屏，适合场景
    ) -> Tuple[bytes, str, str]:
        """
        生成开场故事插画

        流程：
        1. 使用 DeepSeek 分析故事，选择场景并生成提示词
        2. 如果有参考图片（人物形象），使用 image-edit 模型
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
            # 提示词需要强调保持人物特征
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

    # ==================== 外貌锚点生成 ====================

    def generate_appearance_anchor(
        self,
        name: str,
        description: str,
        era: str = "现代",
        character_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """生成人物外貌特征锚点（文本层面）.

        基于原始描述和角色设定，生成结构化的外貌特征描述，
        用于后续场景生成时保持人物视觉一致性。

        Args:
            name: 人物名称
            description: 原始人物描述
            era: 时代背景
            character_settings: 角色设定字典（可选）

        Returns:
            锚点字典，可直接存入 metadata_json
        """
        import openai

        # 使用 deepseek 配置
        api_key = settings.SCENE_ANALYZER_API_KEY or settings.OPENAI_API_KEY
        base_url = settings.SCENE_ANALYZER_BASE_URL or settings.OPENAI_BASE_URL
        model = settings.SCENE_ANALYZER_MODEL  # deepseek-chat

        if not api_key:
            logger.warning("No API key for anchor generation, using fallback")
            return self._fallback_appearance_anchor(
                name, description, era, character_settings
            )

        # 提取额外的角色信息
        age = ""
        gender = ""
        personality = ""
        if character_settings:
            age_info = character_settings.get("age", {})
            if isinstance(age_info, dict):
                age = str(age_info.get("age", ""))
            gender_info = character_settings.get("gender", {})
            if isinstance(gender_info, dict):
                gender = gender_info.get("gender", "")
            traits = character_settings.get("traits", {})
            if isinstance(traits, dict):
                personality = traits.get("personality", "")

        system_prompt = """你是一个专业的角色设计师和视觉描述专家。
你的任务是基于给定的角色描述，生成一个详细、结构化的外貌特征锚点（Appearance Anchor）。

这个锚点将被用于：
1. 在后续不同场景生成时，确保角色外貌保持一致
2. 作为图片生成的详细描述依据

输出要求：
1. 每个字段都要具体、可视觉化，避免抽象词汇
2. 面部特征要详细（脸型、五官具体形状）
3. 发型要具体到长度、颜色、造型细节
4. 体型和体态要描述到位
5. 服装要符合时代背景，具体到款式、颜色、材质
6. 配饰要具体（如果有）
7. 整体气质要与性格描述匹配

输出格式（JSON）：
{
    "face_shape": "脸型描述，如：标准的鹅蛋脸",
    "facial_features": "五官详细描述，如：单眼皮但眼睛有神，鼻梁挺直，嘴唇薄而线条分明",
    "expression": "常设表情，如：温和中带着一丝坚毅",
    "skin_tone": "肤色，如：健康的小麦色",
    "hair_style": "发型，如：黑色中长发，自然垂落至肩部",
    "hair_color": "发色，如：乌黑发亮",
    "hair_details": "发型细节，如：刘海自然向右侧分开，发梢微微内卷",
    "body_type": "体型，如：中等偏瘦的身材，身形修长",
    "height_impression": "身高印象，如：看起来比实际年龄显高挑",
    "posture": "体态，如：站姿挺拔， shoulders放松",
    "distinctive_marks": ["独特标记1", "独特标记2"],
    "typical_outfit": "典型服装，如：深蓝色修身牛仔裤，白色简约T恤，外搭一件浅灰色休闲西装外套",
    "clothing_style": "服装风格，如：简约休闲中带点文艺气息",
    "accessories": ["配饰1", "配饰2"],
    "aura": "整体气质，如：书卷气与都市感并存，给人可靠而温和的印象",
    "age_appearance": "年龄感，如：看起来比实际年龄年轻两三岁",
    "lighting_preference": "适合的光线，如：柔和的侧光能突出面部轮廓",
    "angle_preference": "适合的角度，如：略微侧脸比正面更有立体感"
}

要求：
- 所有描述必须是视觉化的，能看到的外貌特征
- 避免模糊词汇如"美丽""帅气"，要具体描述是什么让角色好看
- distinctive_marks 是可选的，但如果有要特别注明（如疤痕、痣、胎记等）
- 服装要具体到可以画出来的程度"""

        user_prompt = f"""请为以下角色生成外貌特征锚点：

角色名称：{name}
时代背景：{era}
原始描述：{description}
"""
        if age:
            user_prompt += f"年龄：{age}\n"
        if gender:
            user_prompt += f"性别：{gender}\n"
        if personality:
            user_prompt += f"性格特点：{personality}\n"

        user_prompt += """
请生成详细的外貌特征锚点，确保描述足够具体，可以用于指导后续所有场景的图片生成。
"""

        try:
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=1500,
                response_format={"type": "json_object"},
            )

            result = response.choices[0].message.content.strip()
            logger.info(f"Generated appearance anchor for {name}")
            logger.debug(f"Anchor content: {result[:300]}...")

            # 解析 JSON
            import json

            anchor_data = json.loads(result)

            # 添加元信息
            anchor_data["name"] = name
            anchor_data["era"] = era
            anchor_data["generated_from"] = description[:200]  # 保存原始描述的前200字
            anchor_data["version"] = 1

            return anchor_data

        except Exception as e:
            logger.error(f"Failed to generate appearance anchor: {e}")
            return self._fallback_appearance_anchor(
                name, description, era, character_settings
            )

    def _fallback_appearance_anchor(
        self,
        name: str,
        description: str,
        era: str = "现代",
        character_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """当API不可用时，从描述中提取基础锚点信息."""
        logger.warning(f"Using fallback anchor generation for {name}")

        # 简单的关键词提取逻辑
        anchor = {
            "name": name,
            "era": era,
            "face_shape": "",
            "facial_features": description,  # 直接使用原始描述
            "expression": "",
            "skin_tone": "",
            "hair_style": "",
            "hair_color": "",
            "hair_details": "",
            "body_type": "",
            "height_impression": "",
            "posture": "",
            "distinctive_marks": [],
            "typical_outfit": "",
            "clothing_style": "",
            "accessories": [],
            "aura": "",
            "age_appearance": "",
            "lighting_preference": "",
            "angle_preference": "",
            "generated_from": description[:200],
            "version": 1,
            "is_fallback": True,  # 标记为fallback生成的
        }

        # 简单的关键词匹配
        desc_lower = description.lower()

        # 脸型
        if any(w in desc_lower for w in ["圆脸", "圆脸"]):
            anchor["face_shape"] = "圆脸"
        elif any(w in desc_lower for w in ["瓜子脸", "瓜子臉"]):
            anchor["face_shape"] = "瓜子脸"
        elif any(w in desc_lower for w in ["方脸", "方臉"]):
            anchor["face_shape"] = "方脸"

        # 发型/发色
        if "长发" in desc_lower:
            anchor["hair_style"] = "长发"
        elif "短发" in desc_lower:
            anchor["hair_style"] = "短发"

        if any(w in desc_lower for w in ["黑发", "黑色头发", "乌黑"]):
            anchor["hair_color"] = "黑色"
        elif any(w in desc_lower for w in ["金发", "金色"]):
            anchor["hair_color"] = "金色"
        elif "棕发" in desc_lower or "棕色头发" in desc_lower:
            anchor["hair_color"] = "棕色"

        return anchor
