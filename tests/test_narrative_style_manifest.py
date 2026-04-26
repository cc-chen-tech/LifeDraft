"""StyleManifest 数据模型 + StyleLoader 测试 (L1)。

TDD先行：测试 StyleManifest 数据结构的序列化/反序列化，
以及 StyleLoader 的目录扫描、缓存、容错等行为。
"""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from src.ai.narrative.style_manifest import (GlobalParameters, LanguageConfig,
                                             PhilosophyConfig, StructureConfig,
                                             StyleLoader, StyleManifest,
                                             TechniqueConfig, get_style)

# ==================== Helper ====================


def _write_style_json(directory: Path, style_id: str, extra: dict = None) -> Path:
    """在指定目录写入一个最小合法的 .style.json 文件。"""
    data = {
        "style_id": style_id,
        "style_name": f"风格-{style_id}",
        "version": "1.0",
        "description": f"描述-{style_id}",
        "philosophy": {
            "narrative_voice": "全知视角",
            "thematic_core": ["命运"],
            "worldview": "现实",
        },
        "structure": {"macro": "三幕式", "arc": "起承转合"},
        "techniques": {"core_techniques": ["白描"]},
        "language": {"prose_style": "简练", "rhetoric": ["比喻"]},
        "global_parameters": {"temperature": 0.85},
    }
    if extra:
        data.update(extra)
    fp = directory / f"{style_id}.style.json"
    fp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return fp


# ==================== StyleManifest 数据模型测试 ====================


@pytest.mark.unit
class TestStyleManifestDataModel:
    """StyleManifest dataclass 的构造与序列化。"""

    def test_style_manifest_creation(self, sample_style_manifest):
        """创建完整 StyleManifest 验证所有字段存在。"""
        m = sample_style_manifest
        assert m.style_id == "test_style"
        assert m.style_name == "测试风格"
        assert m.version == "1.0"
        assert isinstance(m.philosophy, PhilosophyConfig)
        assert isinstance(m.structure, StructureConfig)
        assert isinstance(m.techniques, TechniqueConfig)
        assert isinstance(m.language, LanguageConfig)
        assert isinstance(m.global_parameters, GlobalParameters)

    def test_style_manifest_defaults(self):
        """默认值正确（全部子配置为空默认值）。"""
        m = StyleManifest()
        assert m.style_id == ""
        assert m.style_name == ""
        assert m.version == "1.0"
        assert m.philosophy.narrative_voice == ""
        assert m.philosophy.thematic_core == []
        assert m.structure.macro == ""
        assert m.techniques.core_techniques == []
        assert m.language.prose_style == ""
        assert m.global_parameters.temperature == 0.85

    def test_style_manifest_serialization(self, sample_style_manifest):
        """JSON 序列化/反序列化往返不丢数据。"""
        m = sample_style_manifest
        d = asdict(m)
        json_str = json.dumps(d, ensure_ascii=False)
        loaded = json.loads(json_str)
        assert loaded["style_id"] == "test_style"
        assert loaded["philosophy"]["narrative_voice"] == "全知视角，冷静克制"
        assert "白描" in loaded["techniques"]["core_techniques"]
        assert loaded["global_parameters"]["temperature"] == 0.85

    def test_philosophy_config_fields(self):
        """PhilosophyConfig 字段验证。"""
        p = PhilosophyConfig(
            narrative_voice="冷叙述",
            thematic_core=["宿命", "自由"],
            worldview="存在主义",
        )
        assert p.narrative_voice == "冷叙述"
        assert len(p.thematic_core) == 2

    def test_global_parameters_temperature_schedule(self):
        """GlobalParameters 含 temperature_schedule 字典。"""
        gp = GlobalParameters(
            temperature=0.9,
            temperature_schedule={"opening": 0.7, "climax": 1.0, "ending": 0.6},
        )
        assert gp.temperature_schedule["climax"] == 1.0


# ==================== StyleLoader 测试 ====================


@pytest.mark.unit
class TestStyleLoader:
    """StyleLoader 文件扫描、缓存、容错。"""

    def test_style_loader_empty_dir(self, tmp_path):
        """空目录不崩溃，返回空列表。"""
        loader = StyleLoader(styles_dir=str(tmp_path))
        loader.load_all()
        assert loader.get_all_style_ids() == []

    def test_style_loader_nonexistent_dir(self, tmp_path):
        """不存在的目录自动创建，不崩溃。"""
        non_exist = tmp_path / "does_not_exist"
        loader = StyleLoader(styles_dir=str(non_exist))
        loader.load_all()
        assert loader.get_all_style_ids() == []

    def test_style_loader_single_file(self, tmp_path):
        """单文件加载成功。"""
        _write_style_json(tmp_path, "classic_saga")
        loader = StyleLoader(styles_dir=str(tmp_path))
        loader.load_all()
        ids = loader.get_all_style_ids()
        assert "classic_saga" in ids
        m = loader.get_style("classic_saga")
        assert m is not None
        assert m.style_name == "风格-classic_saga"

    def test_style_loader_multiple_files(self, tmp_path):
        """多文件加载。"""
        for i in range(5):
            _write_style_json(tmp_path, f"style_{i}")
        loader = StyleLoader(styles_dir=str(tmp_path))
        loader.load_all()
        assert len(loader.get_all_style_ids()) == 5

    def test_style_loader_50_files(self, tmp_path):
        """50个文件批量加载。"""
        for i in range(50):
            _write_style_json(tmp_path, f"bulk_{i:03d}")
        loader = StyleLoader(styles_dir=str(tmp_path))
        loader.load_all()
        assert len(loader.get_all_style_ids()) == 50

    def test_style_loader_cache(self, tmp_path):
        """缓存命中：二次 get_style 不重新加载。"""
        _write_style_json(tmp_path, "cached")
        loader = StyleLoader(styles_dir=str(tmp_path))
        m1 = loader.get_style("cached")
        m2 = loader.get_style("cached")
        assert m1 is m2  # 同一对象，证明走了缓存

    def test_style_loader_hot_reload(self, tmp_path):
        """热插拔：reload 后新增文件被发现。"""
        _write_style_json(tmp_path, "original")
        loader = StyleLoader(styles_dir=str(tmp_path))
        loader.load_all()
        assert len(loader.get_all_style_ids()) == 1

        _write_style_json(tmp_path, "newly_added")
        loader.reload()
        assert "newly_added" in loader.get_all_style_ids()
        assert len(loader.get_all_style_ids()) == 2

    def test_style_loader_corrupted_file(self, tmp_path):
        """损坏文件跳过不崩溃。"""
        _write_style_json(tmp_path, "good")
        bad_file = tmp_path / "bad.style.json"
        bad_file.write_text("{invalid json content!!!", encoding="utf-8")
        loader = StyleLoader(styles_dir=str(tmp_path))
        loader.load_all()
        assert "good" in loader.get_all_style_ids()
        assert len(loader.get_all_style_ids()) == 1

    def test_style_loader_invalid_json(self, tmp_path):
        """无效 JSON（不是对象）跳过。"""
        _write_style_json(tmp_path, "good")
        arr_file = tmp_path / "array.style.json"
        arr_file.write_text("[1,2,3]", encoding="utf-8")
        loader = StyleLoader(styles_dir=str(tmp_path))
        loader.load_all()
        assert len(loader.get_all_style_ids()) == 1

    def test_style_loader_missing_fields(self, tmp_path):
        """缺必填字段（style_id）跳过。"""
        _write_style_json(tmp_path, "good")
        missing = tmp_path / "missing.style.json"
        missing.write_text(json.dumps({"style_name": "no_id"}), encoding="utf-8")
        loader = StyleLoader(styles_dir=str(tmp_path))
        loader.load_all()
        assert len(loader.get_all_style_ids()) == 1

    def test_style_loader_special_chars(self, tmp_path):
        """特殊字符 style_id。"""
        _write_style_json(tmp_path, "style-with-dashes_and_123")
        loader = StyleLoader(styles_dir=str(tmp_path))
        loader.load_all()
        assert "style-with-dashes_and_123" in loader.get_all_style_ids()

    def test_style_loader_unicode_style_name(self, tmp_path):
        """Unicode 风格名正确处理。"""
        _write_style_json(
            tmp_path, "unicode_test", extra={"style_name": "中华古典叙事风格🎭"}
        )
        loader = StyleLoader(styles_dir=str(tmp_path))
        loader.load_all()
        m = loader.get_style("unicode_test")
        assert m is not None
        assert "古典" in m.style_name

    def test_get_style_not_found(self, tmp_path):
        """查询不存在的 style_id 返回 None。"""
        loader = StyleLoader(styles_dir=str(tmp_path))
        assert loader.get_style("nonexistent") is None


# ==================== get_style 全局接口测试 ====================


@pytest.mark.unit
class TestGetStyleGlobal:
    """全局 get_style 接口。"""

    def test_get_style_global(self):
        """get_style 接口可调用，不存在的 id 返回 None。"""
        result = get_style("definitely_not_exists_xyz")
        assert result is None
