"""SceneImage unique constraint contract test.

验证 SceneImage 模型在 (game_id, week, round_number, stage) 上具有唯一约束。
"""

from src.database.models import SceneImage


class TestSceneImageConstraintContract:
    """SceneImage 唯一约束契约测试。"""

    def test_scene_image_has_unique_index(self):
        """SceneImage 表应在 (game_id, week, round_number, stage) 上有唯一索引。"""
        table = SceneImage.__table__
        indexes = list(table.indexes)

        target_index = None
        for idx in indexes:
            col_names = [c.name for c in idx.columns]
            if (
                "game_id" in col_names
                and "week" in col_names
                and "round_number" in col_names
                and "stage" in col_names
            ):
                target_index = idx
                break

        assert target_index is not None, (
            f"未找到 (game_id, week, round_number, stage) 索引。"
            f"现有索引: {[i.name for i in indexes]}"
        )
        assert (
            target_index.unique is True
        ), f"索引 {target_index.name} 应为唯一索引，但 unique={target_index.unique}"

    def test_unique_constraint_columns(self):
        """唯一约束应包含正确的列顺序。"""
        table = SceneImage.__table__

        target_index = None
        for idx in table.indexes:
            col_names = [c.name for c in idx.columns]
            if set(col_names) == {"game_id", "week", "round_number", "stage"}:
                target_index = idx
                break

        assert target_index is not None
        col_names = [c.name for c in target_index.columns]
        assert col_names == ["game_id", "week", "round_number", "stage"]
