#!/usr/bin/env python3
"""旧游戏风格自动匹配迁移脚本

用法:
    # 预览匹配结果（不修改数据库）
    python scripts/migrate_old_games_style.py --preview

    # 应用迁移
    python scripts/migrate_old_games_style.py --apply

    # 指定最低置信度
    python scripts/migrate_old_games_style.py --apply --min-confidence 0.5
"""

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

# 添加项目根目录到 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.ai.narrative.style_matcher import StyleMatcher


def get_old_games(db_path: str):
    """获取所有 narrative_style_id 为 NULL 的游戏"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT game_id, initial_state FROM games WHERE narrative_style_id IS NULL"
    )
    games = []
    for row in cursor.fetchall():
        game_id = row[0]
        initial_state = json.loads(row[1]) if row[1] else {}
        character_settings = initial_state.get("character_settings", {})
        games.append((game_id, character_settings))
    conn.close()
    return games


def preview(db_path: str, min_confidence: float):
    """预览模式：显示匹配结果"""
    matcher = StyleMatcher()
    games = get_old_games(db_path)

    print(f"\n{'='*70}")
    print(f"旧游戏风格自动匹配预览")
    print(f"{'='*70}")
    print(f"总计旧游戏: {len(games)}")
    print(f"最低置信度: {min_confidence}")
    print(f"{'='*70}\n")

    style_counter = Counter()
    confidence_buckets = {
        "high (>=0.8)": 0,
        "medium (0.5-0.8)": 0,
        "low (0.3-0.5)": 0,
        "skip (<0.3)": 0,
    }
    matched = 0
    skipped = 0

    for game_id, settings in games:
        result = matcher.match(settings)

        if result.confidence >= min_confidence:
            matched += 1
            style_counter[result.style_id] += 1
            status = "MATCH"
        else:
            skipped += 1
            status = "SKIP "

        if result.confidence >= 0.8:
            confidence_buckets["high (>=0.8)"] += 1
        elif result.confidence >= 0.5:
            confidence_buckets["medium (0.5-0.8)"] += 1
        elif result.confidence >= 0.3:
            confidence_buckets["low (0.3-0.5)"] += 1
        else:
            confidence_buckets["skip (<0.3)"] += 1

        # 简要描述
        era_desc = ""
        era = settings.get("era", {})
        if isinstance(era, dict):
            era_desc = str(era.get("era_description", ""))[:30]

        print(
            f"  [{status}] Game #{game_id:>4d} → {result.style_id:40s} "
            f"(conf={result.confidence:.3f}) {era_desc}"
        )

    # 统计汇总
    print(f"\n{'='*70}")
    print(f"匹配统计")
    print(f"{'='*70}")
    if games:
        print(
            f"  将匹配: {matched}/{len(games)} ({matched/len(games)*100:.1f}%)"
        )
        print(f"  将跳过: {skipped}/{len(games)}")
    else:
        print("  无旧游戏")

    print(f"\n置信度分布:")
    for bucket, count in confidence_buckets.items():
        bar = "█" * (count * 2)
        print(f"  {bucket:20s}: {count:>3d} {bar}")

    print(f"\n风格分布 (Top 10):")
    for style_id, count in style_counter.most_common(10):
        bar = "█" * count
        print(f"  {style_id:40s}: {count:>3d} {bar}")


def apply(db_path: str, min_confidence: float):
    """应用模式：更新数据库"""
    matcher = StyleMatcher()
    games = get_old_games(db_path)

    print(f"\n正在应用迁移... (min_confidence={min_confidence})")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    updated = 0
    skipped = 0

    for game_id, settings in games:
        result = matcher.match(settings)

        if result.confidence >= min_confidence:
            cursor.execute(
                "UPDATE games SET narrative_style_id = ? WHERE game_id = ?",
                (result.style_id, game_id),
            )
            updated += 1
            print(
                f"  ✓ Game #{game_id} → {result.style_id} "
                f"(conf={result.confidence:.3f})"
            )
        else:
            skipped += 1
            print(
                f"  ✗ Game #{game_id} → skipped "
                f"(conf={result.confidence:.3f})"
            )

    conn.commit()
    conn.close()

    print(f"\n迁移完成: {updated} 更新, {skipped} 跳过")


def main():
    parser = argparse.ArgumentParser(description="旧游戏风格自动匹配迁移工具")
    parser.add_argument(
        "--preview", action="store_true", help="预览模式，不修改数据库"
    )
    parser.add_argument(
        "--apply", action="store_true", help="应用迁移，更新数据库"
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.3,
        help="最低置信度阈值 (默认 0.3)",
    )
    parser.add_argument(
        "--db", type=str, default=None, help="数据库路径 (默认 data/game.db)"
    )

    args = parser.parse_args()

    if not args.preview and not args.apply:
        parser.error("请指定 --preview 或 --apply")

    db_path = args.db or str(project_root / "data" / "game.db")

    if not os.path.exists(db_path):
        print(f"错误: 数据库不存在 {db_path}")
        sys.exit(1)

    if args.preview:
        preview(db_path, args.min_confidence)
    elif args.apply:
        # 安全确认
        print(f"即将修改数据库: {db_path}")
        print(f"最低置信度: {args.min_confidence}")
        apply(db_path, args.min_confidence)


if __name__ == "__main__":
    main()
