"""Image generation configuration and constants.

集中管理图像生成的配置、常量和工具函数。
"""

import logging
from typing import List

import requests  # type: ignore[import-untyped]
from requests.adapters import HTTPAdapter  # type: ignore[import-untyped]
from urllib3.util.retry import Retry

from config.settings import settings

logger = logging.getLogger(__name__)


def create_retry_session(
    retries: int = 3,
    backoff_factor: float = 1,
    status_forcelist: tuple = (500, 502, 503, 504),
) -> requests.Session:
    """Create a requests session with retry strategy.

    Args:
        retries: 重试次数
        backoff_factor: 退避系数
        status_forcelist: 需要重试的 HTTP 状态码

    Returns:
        配置好重试策略的 Session
    """
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


# ==================== 图片尺寸常量 ====================

# DashScope 支持的尺寸
SIZE_SQUARE = "1328*1328"  # 1:1 正方形
SIZE_PORTRAIT = "928*1664"  # 9:16 竖版（适合人物全身像）
SIZE_LANDSCAPE = "1664*928"  # 16:9 横版（适合场景）
SIZE_4_3 = "1472*1104"  # 4:3
SIZE_3_4 = "1104*1472"  # 3:4


# ==================== 人物姿势常量 ====================

CHARACTER_POSES = [
    "站立姿态，正面朝向，日常便装，背景是日常生活场景，自然光线",
    "行走姿态，侧面视角，外出服装，背景是街道或户外场景，动态感",
]

# 人物变体场景 - 强调全身像
CHARACTER_VARIANTS = [
    "这个人的全身像，站立姿态，正面朝向，自然光线，脚部可见",
    "这个人正在行走，侧面视角，全身展示，动态感",
    "这个人站在室内，休闲姿态，全身构图，温馨氛围",
    "这个人在户外场景，全身远景构图，环境清晰",
    "这个人的全身像，突出气质和姿态，双脚可见",
]


# ==================== 默认反向提示词 ====================

DEFAULT_NEGATIVE_PROMPT = (
    "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，"
    "蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲。"
    "半身像，裁剪，截断，无脚，没有脚，脚被裁剪，只显示上半身，"
    "膝盖以下被裁剪，腰部以上，胸部以上，头部特写，"
    "肖像画，大头照，证件照。"
)

DEFAULT_EDIT_NEGATIVE_PROMPT = (
    "低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲。"
    "半身像，裁剪，截断，无脚，没有脚，脚被裁剪，只显示上半身，"
    "膝盖以下被裁剪，腰部以上，胸部以上，头部特写，肖像画，大头照。"
)


# ==================== 敏感词过滤 ====================

SENSITIVE_WORDS = [
    "网吧",
    "酒吧",
    "深夜",
    "赌博",
    "暴力",
    "血腥",
    "性感",
    "诱惑",
]


# ==================== 配置获取工具函数 ====================


def get_text_to_image_models() -> List[str]:
    """获取文生图模型降级列表"""
    return [m.strip() for m in settings.TEXT_TO_IMAGE_MODELS.split(",") if m.strip()]


def get_image_edit_models() -> List[str]:
    """获取图生图模型降级列表"""
    return [m.strip() for m in settings.IMAGE_EDIT_MODELS.split(",") if m.strip()]


def get_scene_analyzer_config() -> tuple:
    """获取场景分析器配置（用于 DeepSeek）

    Returns:
        (api_key, base_url, model)
    """
    api_key = settings.SCENE_ANALYZER_API_KEY or settings.OPENAI_API_KEY
    base_url = settings.SCENE_ANALYZER_BASE_URL or settings.OPENAI_BASE_URL
    model = settings.SCENE_ANALYZER_MODEL
    return api_key, base_url, model
