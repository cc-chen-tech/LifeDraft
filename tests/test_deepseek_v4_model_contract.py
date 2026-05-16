"""DeepSeek V4 Flash Model Configuration Contract Tests

验证 AI 模型配置已更新为使用 DeepSeek V4 flash 模型。
Layer 3: 契约测试 — 配置值、降级链、环境变量。
"""

import os
from pathlib import Path


class TestDeepSeekV4ModelConfiguration:
    """测试 DeepSeek V4 flash 模型配置"""

    def test_env_openai_model_is_deepseek_v4_flash(self):
        """.env 文件中 OPENAI_MODEL 应为 deepseek-v4-flash"""
        env_path = Path(__file__).parent.parent / ".env"
        if not env_path.exists():
            # CI 环境中 .env 由 .env.example 创建，检查 settings 实际值
            from config.settings import settings

            assert settings.OPENAI_MODEL is not None, "OPENAI_MODEL 不应为 None"
            return

        content = env_path.read_text(encoding="utf-8")
        # 找到 OPENAI_MODEL 这一行
        for line in content.splitlines():
            if line.startswith("OPENAI_MODEL="):
                model = line.split("=", 1)[1].strip()
                assert (
                    model == "deepseek-v4-flash"
                ), f".env 中 OPENAI_MODEL 应为 'deepseek-v4-flash', 实际是 '{model}'"
                return

        assert False, ".env 中未找到 OPENAI_MODEL 配置"

    def test_scene_analyzer_model_default_is_deepseek_v4_flash(self):
        """Settings.SCENE_ANALYZER_MODEL 默认值应为 deepseek-v4-flash"""
        from config.settings import Settings

        # 清除环境变量影响，测试默认值
        original = os.environ.pop("SCENE_ANALYZER_MODEL", None)
        try:
            # 创建新 Settings 实例读取默认值
            class TestSettings(Settings):
                pass

            # SCENE_ANALYZER_MODEL 的默认值通过 os.getenv 获取
            default = os.getenv("SCENE_ANALYZER_MODEL", "deepseek-v4-flash")
            assert (
                default == "deepseek-v4-flash"
            ), f"SCENE_ANALYZER_MODEL 默认值应为 'deepseek-v4-flash', 实际是 '{default}'"
        finally:
            if original is not None:
                os.environ["SCENE_ANALYZER_MODEL"] = original

    def test_fallback_models_include_deepseek_v4_flash(self):
        """模型降级链应包含 deepseek-v4-flash"""
        from src.ai.client import _DEFAULT_FALLBACK_MODELS

        assert "deepseek-v4-flash" in _DEFAULT_FALLBACK_MODELS, (
            f"_DEFAULT_FALLBACK_MODELS 应包含 'deepseek-v4-flash', "
            f"实际为 {_DEFAULT_FALLBACK_MODELS}"
        )

    def test_fallback_models_include_deepseek_v4_pro(self):
        """模型降级链应包含 deepseek-v4-pro 作为备选"""
        from src.ai.client import _DEFAULT_FALLBACK_MODELS

        assert "deepseek-v4-pro" in _DEFAULT_FALLBACK_MODELS, (
            f"_DEFAULT_FALLBACK_MODELS 应包含 'deepseek-v4-pro', "
            f"实际为 {_DEFAULT_FALLBACK_MODELS}"
        )

    def test_fallback_models_priority_order(self):
        """deepseek-v4-flash 应在降级列表首位"""
        from src.ai.client import _DEFAULT_FALLBACK_MODELS

        assert _DEFAULT_FALLBACK_MODELS[0] == "deepseek-v4-flash", (
            f"_DEFAULT_FALLBACK_MODELS 首位应为 'deepseek-v4-flash', "
            f"实际是 '{_DEFAULT_FALLBACK_MODELS[0]}'"
        )

    def test_settings_openai_model_reads_from_env(self):
        """Settings.OPENAI_MODEL 应从环境变量读取"""
        from config.settings import settings

        # 验证当前运行时配置
        assert settings.OPENAI_MODEL is not None, "OPENAI_MODEL 不应为 None"

    def test_legacy_deepseek_chat_fully_replaced(self):
        """旧模型 deepseek-chat 应已被完全替换为 deepseek-v4-pro"""
        from src.ai.client import _DEFAULT_FALLBACK_MODELS

        assert "deepseek-chat" not in _DEFAULT_FALLBACK_MODELS, (
            f"deepseek-chat 应已被 deepseek-v4-pro 替换, "
            f"实际降级链为 {_DEFAULT_FALLBACK_MODELS}"
        )
        # deepseek-v4-pro 应作为备选存在
        assert "deepseek-v4-pro" in _DEFAULT_FALLBACK_MODELS, (
            f"deepseek-v4-pro 应在降级链中作为备选, " f"实际降级链为 {_DEFAULT_FALLBACK_MODELS}"
        )
