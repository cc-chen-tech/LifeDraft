#!/usr/bin/env python
"""
数据库迁移脚本：更新 scene_images 表的索引

将索引从 (game_id, round_number) 更新为 (game_id, round_number, stage)
以支持双阶段插画（event/result）的精准查询。

运行方式：
    python migrate_scene_images_stage_index.py
"""
import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent / "data" / "game.db"

def migrate():
    """Update scene_images index to include stage column."""
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
        
        # Add stage column if not exists
        if "stage" not in columns:
            print("Adding stage column to scene_images table...")
            cursor.execute("""
                ALTER TABLE scene_images 
                ADD COLUMN stage VARCHAR(20) DEFAULT 'result'
            """)
            print("✅ stage column added to scene_images")
        else:
            print("✅ stage column already exists in scene_images")
        
        # Drop old index
        print("\nDropping old index...")
        cursor.execute("""
            DROP INDEX IF EXISTS ix_scene_images_game_round
        """)
        print("✅ Old index ix_scene_images_game_round dropped")
        
        # Create new index with stage
        print("\nCreating new index with stage...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_scene_images_game_round_stage 
            ON scene_images(game_id, round_number, stage)
        """)
        print("✅ Index ix_scene_images_game_round_stage created")
        
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
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("数据库迁移：更新 scene_images 表索引以支持 stage 字段")
    print("=" * 60)
    migrate()
