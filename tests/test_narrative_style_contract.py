"""风格配置契约测试 - 参数化自动扫描所有 .style.json (L1)。

TDD先行：对 config/styles/ 目录下所有风格配置文件进行契约验证，
确保每个文件满足 schema 规范。
"""

import glob
import json
from pathlib import Path

import pytest

from src.ai.narrative.style_manifest import StyleLoader


def get_all_style_files():
    """获取所有风格配置文件路径。"""
    return sorted(glob.glob("config/styles/*.style.json"))


# 若目录为空则跳过整个模块
_style_files = get_all_style_files()


@pytest.mark.unit
@pytest.mark.skipif(len(_style_files) == 0, reason="config/styles/ 目录下无 .style.json 文件")
class TestStyleContract:
    """对每个 .style.json 文件进行契约验证。"""

    @pytest.mark.parametrize("style_file", _style_files, ids=lambda f: Path(f).stem)
    def test_required_sections(self, style_file):
        """五维子配置完整存在。"""
        with open(style_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        required_top = {"style_id", "style_name"}
        missing_top = required_top - set(data.keys())
        assert not missing_top, f"缺少顶级字段: {missing_top}"

        # 五维子配置
        for section in ["philosophy", "structure", "techniques", "language", "global_parameters"]:
            assert section in data, f"缺少子配置段: {section}"
            assert isinstance(data[section], dict), f"{section} 应为 dict"

    @pytest.mark.parametrize("style_file", _style_files, ids=lambda f: Path(f).stem)
    def test_temperature_range(self, style_file):
        """temperature 在 0.3-1.0 范围。"""
        with open(style_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        gp = data.get("global_parameters", {})
        temp = gp.get("temperature", 0.85)
        assert 0.3 <= temp <= 1.0, f"temperature={temp} 超出 [0.3, 1.0] 范围"

    @pytest.mark.parametrize("style_file", _style_files, ids=lambda f: Path(f).stem)
    def test_style_id_matches_filename(self, style_file):
        """style_id 与文件名一致。"""
        with open(style_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        expected_id = Path(style_file).stem.replace(".style", "")
        actual_id = data.get("style_id", "")
        assert actual_id == expected_id, (
            f"style_id '{actual_id}' 与文件名 '{expected_id}' 不匹配"
        )

    @pytest.mark.parametrize("style_file", _style_files, ids=lambda f: Path(f).stem)
    def test_loadable_by_style_loader(self, style_file):
        """能被 StyleLoader 正确加载。"""
        style_dir = str(Path(style_file).parent)
        loader = StyleLoader(styles_dir=style_dir)
        loader.load_all()

        with open(style_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        style_id = data.get("style_id", "")

        m = loader.get_style(style_id)
        assert m is not None, f"StyleLoader 无法加载 style_id='{style_id}'"
        assert m.style_id == style_id


# ==================== 无文件时的兜底测试 ====================


@pytest.mark.unit
class TestStyleContractFallback:
    """当没有风格文件时的基本验证。"""

    def test_style_directory_structure(self):
        """config/styles 目录应存在（即使为空）或将被创建。"""
        styles_dir = Path("config/styles")
        # 目录可能尚不存在（TDD先行），这是预期的
        # 我们只验证 StyleLoader 能优雅处理
        loader = StyleLoader(styles_dir=str(styles_dir))
        loader.load_all()  # 不应崩溃
        assert isinstance(loader.get_all_style_ids(), list)
