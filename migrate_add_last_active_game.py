#!/usr/bin/env python
"""
数据库迁移脚本：添加 last_active_game_id 字段到 users 表

用于服务端会话管理，支持 iPad 等设备上的自动恢复功能。

运行方式：
    python migrate_add_last_active_game.py
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from src.database.models import engine, SessionLocal

def migrate():
    """添加 last_active_game_id 字段到 users 表"""
    db = SessionLocal()
    try:
        # 检查字段是否已存在
        result = db.execute(text("PRAGMA table_info(users)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'last_active_game_id' in columns:
            print("✓ 字段 last_active_game_id 已存在，无需迁移")
            return
        
        # 添加新字段
        print("正在添加 last_active_game_id 字段...")
        db.execute(text("""
            ALTER TABLE users 
            ADD COLUMN last_active_game_id INTEGER 
            REFERENCES games(game_id)
        """))
        
        # 创建索引
        print("正在创建索引...")
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_users_last_active_game_id 
            ON users(last_active_game_id)
        """))
        
        db.commit()
        print("✓ 迁移完成！")
        
    except Exception as e:
        db.rollback()
        print(f"✗ 迁移失败: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 50)
    print("数据库迁移：添加 last_active_game_id 字段")
    print("=" * 50)
    migrate()
