"""Migration script to add user_id, is_public, and updated_at columns, and create indexes."""
import sqlite3
from pathlib import Path
from datetime import datetime

# Database path
DB_PATH = Path(__file__).parent / "data" / "game.db"

def migrate():
    """Add user_id, is_public, and updated_at columns to games table, and create indexes."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check existing columns in games table
        cursor.execute("PRAGMA table_info(games)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add user_id column to games
        if "user_id" not in columns:
            print("Adding user_id column to games table...")
            cursor.execute("""
                ALTER TABLE games 
                ADD COLUMN user_id INTEGER 
                REFERENCES users(user_id)
            """)
            print("✅ user_id column added to games")
        else:
            print("✅ user_id column already exists in games")
        
        # Add is_public column to games
        if "is_public" not in columns:
            print("Adding is_public column to games table...")
            cursor.execute("""
                ALTER TABLE games 
                ADD COLUMN is_public INTEGER DEFAULT 0
            """)
            print("✅ is_public column added to games")
        else:
            print("✅ is_public column already exists in games")
        
        # Add updated_at column to games
        if "updated_at" not in columns:
            print("Adding updated_at column to games table...")
            current_time = datetime.utcnow().isoformat()
            cursor.execute(f"""
                ALTER TABLE games 
                ADD COLUMN updated_at DATETIME DEFAULT '{current_time}'
            """)
            print("✅ updated_at column added to games")
        else:
            print("✅ updated_at column already exists in games")
        
        # Create indexes
        print("\nCreating indexes...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_games_user_id 
            ON games(user_id)
        """)
        print("✅ Index ix_games_user_id created")
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_character_presets_user_id 
            ON character_presets(user_id)
        """)
        print("✅ Index ix_character_presets_user_id created")
        
        conn.commit()
        print("\n✅ Migration completed successfully")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
