"""项目统一异常定义"""

from typing import Any, Dict, Optional


class GameException(Exception):
    """游戏系统基础异常"""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.context = context or {}


class AIGenerationError(GameException):
    """AI生成失败"""

    pass


class AIClientError(GameException):
    """AI客户端调用错误"""

    pass


class DataExtractionError(GameException):
    """数据提取/解析失败"""

    pass


class DatabaseError(GameException):
    """数据库操作错误"""

    pass


class ValidationError(GameException):
    """输入验证错误"""

    pass


class ImageProcessingError(GameException):
    """图片处理错误"""

    pass


class SSEStreamError(GameException):
    """SSE流式传输错误"""

    pass


class AuthenticationError(GameException):
    """认证错误"""

    pass
