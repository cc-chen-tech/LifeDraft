#!/usr/bin/env python3
"""将数据库中的图片绝对路径迁移为相对路径。

此脚本将 images 和 scene_images 表中的 storage_path 从绝对路径
（如 /Users/luicy/AI/story2/data/images/296/character/xxx.png）
转换为相对路径（如 296/character/xxx.png），相对于 data/images/ 目录。

仅处理 storage_type='local' 的记录，不影响 OSS 存储。

用法:
    # 预览模式（不实际修改）
    python3 scripts/migrate_image_paths.py --dry-run

    # 执行迁移
    python3 scripts/migrate_image_paths.py
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from src.database.models import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

MARKER = "data/images/"


def extract_relative_path(storage_path: str) -> str | None:
    """从绝对路径中提取相对路径。

    Args:
        storage_path: 存储路径

    Returns:
        相对路径，如果已经是相对路径则返回 None（表示无需迁移）
    """
    if not os.path.isabs(storage_path):
        # 已经是相对路径，无需迁移
        return None

    marker_idx = storage_path.find(MARKER)
    if marker_idx != -1:
        return storage_path[marker_idx + len(MARKER) :]

    # 无法识别的绝对路径格式，跳过
    logger.warning(f"  无法识别的路径格式，跳过: {storage_path}")
    return None


def migrate_table(
    db,
    table_name: str,
    id_column: str,
    dry_run: bool = False,
) -> dict:
    """迁移指定表的 storage_path 列。

    Args:
        db: 数据库会话
        table_name: 表名
        id_column: 主键列名
        dry_run: 是否为预览模式

    Returns:
        迁移统计 dict
    """
    stats = {"total": 0, "migrated": 0, "skipped": 0, "errors": 0}

    # 查询所有 local 类型的记录
    rows = db.execute(
        text(
            f"SELECT {id_column}, storage_path FROM {table_name} "
            f"WHERE storage_type = 'local' OR storage_type IS NULL"
        )
    ).fetchall()

    stats["total"] = len(rows)
    logger.info(f"[{table_name}] 共 {len(rows)} 条 local 记录")

    for row in rows:
        row_id = row[0]
        old_path = row[1]

        if not old_path:
            stats["skipped"] += 1
            continue

        new_path = extract_relative_path(old_path)

        if new_path is None:
            # 已经是相对路径或无法识别
            stats["skipped"] += 1
            continue

        if dry_run:
            logger.info(f"  [DRY-RUN] {id_column}={row_id}: {old_path} -> {new_path}")
            stats["migrated"] += 1
        else:
            try:
                db.execute(
                    text(
                        f"UPDATE {table_name} SET storage_path = :new_path "
                        f"WHERE {id_column} = :row_id"
                    ),
                    {"new_path": new_path, "row_id": row_id},
                )
                logger.info(f"  {id_column}={row_id}: {old_path} -> {new_path}")
                stats["migrated"] += 1
            except Exception as e:
                logger.error(f"  {id_column}={row_id}: 更新失败 - {e}")
                stats["errors"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="迁移图片存储路径：绝对路径 -> 相对路径")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际修改数据库",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("=" * 60)
        logger.info("预览模式（DRY-RUN）- 不会修改数据库")
        logger.info("=" * 60)
    else:
        logger.info("=" * 60)
        logger.info("执行迁移 - 将修改数据库")
        logger.info("=" * 60)

    db = SessionLocal()
    try:
        # 迁移 images 表
        logger.info("\n--- 迁移 images 表 ---")
        images_stats = migrate_table(db, "images", "image_id", dry_run=args.dry_run)

        # 迁移 scene_images 表
        logger.info("\n--- 迁移 scene_images 表 ---")
        scenes_stats = migrate_table(db, "scene_images", "scene_id", dry_run=args.dry_run)

        if not args.dry_run:
            db.commit()
            logger.info("\n数据库已提交。")
        else:
            logger.info("\n预览完成，未修改数据库。")

        # 输出统计
        logger.info("\n" + "=" * 60)
        logger.info("迁移统计:")
        logger.info(f"  images 表: 总计 {images_stats['total']} 条, "
                     f"迁移 {images_stats['migrated']} 条, "
                     f"跳过 {images_stats['skipped']} 条, "
                     f"错误 {images_stats['errors']} 条")
        logger.info(f"  scene_images 表: 总计 {scenes_stats['total']} 条, "
                     f"迁移 {scenes_stats['migrated']} 条, "
                     f"跳过 {scenes_stats['skipped']} 条, "
                     f"错误 {scenes_stats['errors']} 条")
        logger.info("=" * 60)

    except Exception as e:
        logger.exception(f"迁移失败: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
