"""生产环境日志配置"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


_BUILTIN_LOG_RECORD_FIELDS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)
_MODEL_LOGGER_PREFIXES = (
    "src.ai",
    "src.services",
    "src.api.routers",
    "src.api.services",
    "src.game",
)
_SENSITIVE_LOG_FIELD_NAMES = {
    "prompt",
    "user_prompt",
    "system_prompt",
    "messages",
    "content",
    "response",
    "output",
    "story",
    "story_text",
    "api_key",
    "authorization",
    "token",
    "secret",
}


class JsonLogFormatter(logging.Formatter):
    """Render one machine-readable JSON object per application log line."""

    def format(self, record: logging.LogRecord) -> str:
        is_model_subsystem_log = record.name.startswith(_MODEL_LOGGER_PREFIXES)
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": (
                "model_subsystem_log_suppressed"
                if is_model_subsystem_log
                else record.getMessage()
            ),
        }
        for key, value in record.__dict__.items():
            if key in _BUILTIN_LOG_RECORD_FIELDS or key.startswith("_"):
                continue
            if key in {"message", "asctime", "exc_info", "exc_text", "stack_info"}:
                continue
            if is_model_subsystem_log and key.lower() in _SENSITIVE_LOG_FIELD_NAMES:
                continue
            try:
                json.dumps(value, ensure_ascii=False)
            except (TypeError, ValueError):
                payload[key] = str(value)
            else:
                payload[key] = value
        if is_model_subsystem_log:
            # AI-adjacent modules historically logged prompt/response snippets and
            # provider exception text.  Keep production logs queryable without
            # allowing those free-form messages to cross the persistence boundary.
            payload["message_suppressed"] = True
        if record.exc_info:
            payload["exception_type"] = type(record.exc_info[1]).__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_file: str = "app.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    json_output: bool = False,
):
    """
    配置应用日志

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: 是否写入文件
        log_file: 日志文件名
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的备份文件数量
    """
    # 获取日志级别
    level = getattr(logging, log_level.upper(), logging.INFO)

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # 清除已有的处理器
    for existing_handler in root_logger.handlers[:]:
        root_logger.removeHandler(existing_handler)
        existing_handler.close()

    # 日志格式
    formatter: logging.Formatter
    if json_output:
        formatter = JsonLogFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # 控制台处理器（总是启用）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器（生产环境）
    if log_to_file:
        log_path = LOG_DIR / log_file
        file_handler = RotatingFileHandler(
            log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # 设置第三方库的日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return root_logger


# 自动设置（如果环境变量设置了）
if os.getenv("ENVIRONMENT") == "production":
    setup_logging(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_to_file=True,
        json_output=True,
    )
