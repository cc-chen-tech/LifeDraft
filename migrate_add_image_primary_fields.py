#!/usr/bin/env python
"""
数据库迁移脚本：添加 is_primary 和 primary_image_id 字段到 images 表

用于支持主图/变体关系管理。

运行方式：
    python migrate_add_image_primary_fields.py
"""
import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent / "data" / "game.db"

def migrate():
    """Add is_primary and primary_image_id columns to images table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check existing columns in images table
        cursor.execute("PRAGMA table_info(images)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add is_primary column
        if "is_primary" not in columns:
            print("Adding is_primary column to images table...")
            cursor.execute("""
                ALTER TABLE images 
                ADD COLUMN is_primary INTEGER DEFAULT 0
            """)
            print("✅ is_primary column added to images")
        else:
            print("✅ is_primary column already exists in images")
        
        # Add primary_image_id column
        if "primary_image_id" not in columns:
            print("Adding primary_image_id column to images table...")
            cursor.execute("""
                ALTER TABLE images 
                ADD COLUMN primary_image_id INTEGER
            """)
            print("✅ primary_image_id column added to images")
        else:
            print("✅ primary_image_id column already exists in images")
        
        # Create index for primary_image_id
        print("\nCreating index...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_images_primary_image_id 
            ON images(primary_image_id)
        """)
        print("✅ Index ix_images_primary_image_id created")
        
        conn.commit()
        print("\n✅ Migration completed successfully")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 50)
    print("数据库迁移：添加图片主图关系字段")
    print("=" * 50)
    migrate()
