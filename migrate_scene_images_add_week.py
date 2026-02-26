#!/usr/bin/env python
"""
数据库迁移脚本：为 scene_images 表添加 week 字段

将索引从 (game_id, round_number, stage) 更新为 (game_id, week, round_number, stage)
以支持完整的游戏层级结构查询。

运行方式：
    python migrate_scene_images_add_week.py
"""
import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent / "data" / "game.db"


def migrate():
    """Add week column to scene_images table and update index."""
    if not DB_PATH.exists():
        print(f"⚠️  Database not found at {DB_PATH}")
        print("   Migration will be applied when database is created.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if scene_images table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='scene_images'
        """)
        if not cursor.fetchone():
            print("⚠️  scene_images table not found, skipping migration")
            return
        
        # Check existing columns in scene_images table
        cursor.execute("PRAGMA table_info(scene_images)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add week column if not exists
        if "week" not in columns:
            print("Adding week column to scene_images table...")
            cursor.execute("""
                ALTER TABLE scene_images 
                ADD COLUMN week INTEGER DEFAULT 0
            """)
            print("✅ week column added to scene_images")
        else:
            print("✅ week column already exists in scene_images")
        
        # Drop old indexes
        print("\nDropping old indexes...")
        cursor.execute("""
            DROP INDEX IF EXISTS ix_scene_images_game_round
        """)
        cursor.execute("""
            DROP INDEX IF EXISTS ix_scene_images_game_round_stage
        """)
        print("✅ Old indexes dropped")
        
        # Create new index with week
        print("\nCreating new index with week...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_scene_images_game_week_round_stage 
            ON scene_images(game_id, week, round_number, stage)
        """)
        print("✅ Index ix_scene_images_game_week_round_stage created")
        
        conn.commit()
        print("\n✅ Migration completed successfully")
        
        # Show current indexes
        print("\nCurrent indexes on scene_images:")
        cursor.execute("""
            SELECT name, sql FROM sqlite_master 
            WHERE type='index' AND tbl_name='scene_images'
        """)
        for name, sql in cursor.fetchall():
            print(f"  - {name}")
        
        # Show column info
        print("\nCurrent columns in scene_images:")
        cursor.execute("PRAGMA table_info(scene_images)")
        for col in cursor.fetchall():
            print(f"  - {col[1]} ({col[2]})")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("数据库迁移：为 scene_images 表添加 week 字段")
    print("=" * 60)
    migrate()
