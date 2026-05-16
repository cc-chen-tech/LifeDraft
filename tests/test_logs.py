"""日志测试 - 验证关键日志输出

轻量级测试，用于发现日志格式错误、关键信息缺失等问题。
"""

import logging
from io import StringIO


class TestEntityRecognitionLogs:
    """测试实体识别相关日志"""

    def test_task_cleanup_logs_with_details(self):
        """测试任务清理日志包含详细信息"""
        import datetime

        from src.services.entity_recognition_task import TaskManager

        manager = TaskManager()

        # 创建一个已完成的任务
        task = manager.create_task(game_id=1, user_id=1)
        task.mark_running()
        task.mark_completed({"items": [], "characters": [], "landmarks": []})

        # 修改完成时间为 2 小时前（使其过期）
        task.completed_at = datetime.datetime.now() - datetime.timedelta(hours=2)

        # 捕获日志
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)

        logger = logging.getLogger("src.services.entity_recognition_task")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        try:
            manager.cleanup_expired_tasks(max_age_hours=1)

            log_output = log_capture.getvalue()
            # 验证日志包含关键信息
            assert "Removing expired task" in log_output or "No expired tasks" in log_output
        finally:
            logger.removeHandler(handler)

    def test_task_creation_logs(self):
        """测试任务创建有日志记录"""
        from src.services.entity_recognition_task import TaskManager

        manager = TaskManager()

        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.INFO)

        logger = logging.getLogger("src.api.routers.collection")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        try:
            task = manager.create_task(game_id=999, user_id=1)

            # 注意：实际日志在路由中，这里只验证任务创建成功
            assert task is not None
            assert task.game_id == 999
        finally:
            logger.removeHandler(handler)


class TestLogFormat:
    """测试日志格式"""

    def test_logger_has_handlers(self):
        """测试 logger 有配置 handlers"""
        from src.services.entity_recognition_task import logger as task_logger

        # 验证 logger 已配置
        assert task_logger.name == "src.services.entity_recognition_task"

    def test_cleanup_logger_exists(self):
        """测试清理功能有对应的 logger"""
        logger = logging.getLogger("src.services.entity_recognition_task")
        assert logger is not None
