"""添加性能优化索引到现有数据库。

在应用启动时调用，安全地创建不存在的索引。
"""

import logging

from sqlalchemy import inspect, text

from src.database.models import engine

logger = logging.getLogger(__name__)

# ★ 需要创建的索引列表
# 格式: (表名, 索引名, 列列表)
PERFORMANCE_INDEXES = [
    ("game_states", "ix_game_state_game_created", ["game_id", "created_at"]),
    ("games", "ix_games_user_ending_updated", ["user_id", "ending_type", "updated_at"]),
]


def create_performance_indexes():
    """安全地创建性能索引（如果已存在则跳过）。"""
    inspector = inspect(engine)
    created = []
    skipped = []

    for table_name, index_name, columns in PERFORMANCE_INDEXES:
        existing = inspector.get_indexes(table_name)
        existing_names = {idx["name"] for idx in existing}

        if index_name in existing_names:
            skipped.append(index_name)
            continue

        # 构建 CREATE INDEX 语句
        cols_str = ", ".join(columns)
        sql = (
            f"CREATE INDEX IF NOT EXISTS {index_name} " f"ON {table_name} ({cols_str})"
        )

        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
            created.append(index_name)
            logger.info(
                f"[DB Index] Created: {index_name} on " f"{table_name}({cols_str})"
            )
        except Exception as e:
            logger.warning(f"[DB Index] Failed to create {index_name}: {e}")

    if created:
        logger.info(f"[DB Index] Created {len(created)} indexes: {created}")
    if skipped:
        logger.info(f"[DB Index] Skipped {len(skipped)} existing indexes: {skipped}")

    return created, skipped


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_performance_indexes()
